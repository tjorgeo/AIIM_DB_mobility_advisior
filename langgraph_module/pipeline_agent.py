"""
DB MoveOptimizer — Analyst → Optimizer Pipeline
Loads user context from SQLite, analyses travel patterns, then recommends
the best subscription change using a ReAct tool loop.

Pipeline flow:
    load_context_node  (SQLite query — no LLM)
        ↓ travel_data populated in state
    analyst_node       (LLM: pattern summary, no tools)
        ↓ analyst_summary
    optimizer_node     (LLM + lookup_subscriptions tool, ReAct loop)
        ↓
    messages[-1].content  (final recommendation)
"""

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.db_utils import (
    get_subscription_products,
    get_trips,
    get_user,
    get_user_by_username,
    get_user_subscriptions,
    init_db,
)

load_dotenv()
init_db()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNI_GPT_BASE_URL = "https://chat.kiconnect.nrw/api/v1"
UNI_GPT_MODEL = "Openai GPT OSS 120B"
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class PipelineState(TypedDict):
    # Input: UUID or username
    user_id: str
    # Populated by load_context_node
    travel_data: Optional[dict]
    # Analyst → optimizer handoff
    analyst_summary: str
    # Optimizer ReAct loop history
    messages: Annotated[list, add_messages]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ANALYST_PROMPT = """You are a Deutsche Bahn mobility analyst.
Review the user's travel log and respond with exactly these four sections:
1. DOMINANT ROUTE — most frequent origin-destination pair and how often
2. TICKET MIX — breakdown of ticket types used and their total costs
3. SPEND SUMMARY — total spend, average cost per trip, and estimated CO₂
4. ONE OBSERVATION — a single sentence noting an inefficiency or opportunity
Be factual and brief. Do not make recommendations."""

OPTIMIZER_PROMPT = """You are a Deutsche Bahn mobility optimizer.
You receive an analyst summary of a user's travel behaviour and their current subscriptions.
Use the lookup_subscriptions tool to retrieve the current product catalog,
then recommend the single best subscription change for this user.
Explain the expected annual saving and why it fits their travel pattern.
Be concise — four sentences maximum."""

# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool
def lookup_subscriptions(filter_type: str = "all") -> str:
    """Look up Deutsche Bahn subscription products from the catalog.

    Args:
        filter_type: 'card', 'subscription', or 'all'.

    Returns:
        JSON string of matching DB products with prices and conditions.
    """
    products = get_subscription_products(filter_type)
    if not products:
        return f"No products found for type '{filter_type}'."
    # Return compact JSON so the LLM can reason over structured data
    return json.dumps(products, ensure_ascii=False, indent=2)


tools = [lookup_subscriptions]

# ---------------------------------------------------------------------------
# LLM — lazy init
# ---------------------------------------------------------------------------

_llm = None
_llm_with_tools = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=UNI_GPT_MODEL,
            openai_api_key=UNI_GPT_API_KEY,
            openai_api_base=UNI_GPT_BASE_URL,
            temperature=0.0,
        )
    return _llm


def _get_llm_with_tools() -> ChatOpenAI:
    global _llm_with_tools
    if _llm_with_tools is None:
        _llm_with_tools = _get_llm().bind_tools(tools)
    return _llm_with_tools


# ---------------------------------------------------------------------------
# Node 0 — Load user context from SQLite
# ---------------------------------------------------------------------------


def load_context_node(state: PipelineState) -> dict:
    """Resolve the user_id and build the travel_data dict from SQLite."""
    raw_id = state["user_id"].strip()

    # Defensive: unwrap if LangSmith passes full JSON as the field value
    if raw_id.startswith("{"):
        try:
            raw_id = json.loads(raw_id).get("user_id", raw_id).strip()
        except json.JSONDecodeError:
            pass

    user = get_user(raw_id) or get_user_by_username(raw_id)
    if not user:
        return {"travel_data": {"error": f"No user found for '{raw_id}'"}}

    resolved_id = user["user_id"]
    trips = get_trips(resolved_id)
    active_subs = get_user_subscriptions(resolved_id, status="active")

    # Compact trip log — keep only what the analyst needs
    trip_log = [
        {
            "date": t["start_ts"][:10] if t["start_ts"] else None,
            "from": t["origin_city"],
            "to": t["destination_city"],
            "mode": t["main_mode"],
            "distance_km": t["distance_km"],
            "cost_eur": t["estimated_cost_eur"],
            "co2_kg": t["co2_kg"],
            "ticket": t["ticket_product_used"],
            "purpose": t["trip_purpose"],
            "is_commute": bool(t["is_commute"]),
        }
        for t in trips
    ]

    travel_data = {
        "name": f"{user['first_name']} {user['last_name']}",
        "user_id": resolved_id,
        "home_city": user["home_city"],
        "occupation": user["job_industry"],
        "income_range": user["income_range"],
        "price_sensitivity": user["price_sensitivity"],
        "employer_reimbursement": bool(user.get("employer_reimbursement_available")),
        "current_subscriptions": [s["product_name"] for s in active_subs],
        "travel_log": trip_log,
    }

    return {"travel_data": travel_data}


# ---------------------------------------------------------------------------
# Node 1 — Analyst
# ---------------------------------------------------------------------------


def _format_travel_data(data: dict) -> str:
    subs = ", ".join(data.get("current_subscriptions") or ["none"])
    # Keep trip log compact: summarise rather than dump all 150+ rows
    trips = data.get("travel_log", [])
    n = len(trips)
    total_cost = sum(t.get("cost_eur") or 0 for t in trips)
    total_co2 = sum(t.get("co2_kg") or 0 for t in trips)
    from collections import Counter
    modes = Counter(t["mode"] for t in trips).most_common(5)
    routes = Counter(f"{t['from']} → {t['to']}" for t in trips).most_common(5)
    tickets = Counter(t.get("ticket") or "none" for t in trips).most_common()

    return (
        f"User: {data['name']} | Home: {data['home_city']} | Job: {data['occupation']}\n"
        f"Income: {data['income_range']} | Price sensitivity: {data['price_sensitivity']}\n"
        f"Employer reimbursement available: {data['employer_reimbursement']}\n"
        f"Current subscriptions: {subs}\n\n"
        f"Total trips: {n} | Total spend: €{total_cost:.2f} | Total CO₂: {total_co2:.1f} kg\n"
        f"Avg cost/trip: €{total_cost / n:.2f}\n\n"
        f"Top modes: {dict(modes)}\n"
        f"Top routes: {dict(routes)}\n"
        f"Ticket types: {dict(tickets)}"
    )


def analyst_node(state: PipelineState) -> dict:
    data = state.get("travel_data") or {}
    if "error" in data:
        return {"analyst_summary": f"Cannot analyse: {data['error']}"}
    response = _get_llm().invoke([
        SystemMessage(content=ANALYST_PROMPT),
        HumanMessage(content=_format_travel_data(data)),
    ])
    return {"analyst_summary": response.content}


# ---------------------------------------------------------------------------
# Node 2 — Optimizer (ReAct loop)
# ---------------------------------------------------------------------------


def optimizer_node(state: PipelineState) -> dict:
    if not state["messages"]:
        data = state.get("travel_data") or {}
        subs = ", ".join(data.get("current_subscriptions") or ["none"])
        initial_msg = HumanMessage(content=(
            f"Current subscriptions: {subs}\n\n"
            "Based on the analyst summary below, recommend the best DB subscription change.\n"
            "Use the lookup_subscriptions tool to check the catalog first.\n\n"
            f"ANALYST SUMMARY:\n{state['analyst_summary']}"
        ))
        response = _get_llm_with_tools().invoke(
            [SystemMessage(content=OPTIMIZER_PROMPT), initial_msg]
        )
        return {"messages": [initial_msg, response]}
    else:
        response = _get_llm_with_tools().invoke(
            [SystemMessage(content=OPTIMIZER_PROMPT)] + state["messages"]
        )
        return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph():
    tool_node = ToolNode(tools)
    workflow = StateGraph(PipelineState)

    workflow.add_node("load_context", load_context_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("optimizer", optimizer_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "load_context")
    workflow.add_edge("load_context", "analyst")
    workflow.add_edge("analyst", "optimizer")
    workflow.add_conditional_edges("optimizer", tools_condition)
    workflow.add_edge("tools", "optimizer")

    return workflow.compile()


graph = build_graph()
