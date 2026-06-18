"""
DB MoveOptimizer — Analyst + Forecaster → Optimizer Pipeline

Analyst and Forecaster run in parallel (same LangGraph superstep).
Their outputs are merged by a combine node, then passed to the Optimizer's
ReAct tool loop.

Graph topology:
    START
      ↓
    load_context          (SQLite — no LLM)
      ↓          ↘
    analyst    forecaster  (LLM — parallel)
      ↓          ↙
    combine               (no LLM — fan-in, builds optimizer prompt)
      ↓
    optimizer  ←→  tools   (LLM + ReAct loop)
      ↓
    END

LangSmith Studio:
    Graph: analyst_forecaster_pipeline
    Input field: user_id = "jan.schulz"   (username or UUID)
    Leave all other fields empty.
"""

import json
import os
import sys
from collections import Counter, defaultdict
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


class FullPipelineState(TypedDict):
    user_id: str                                    # input
    travel_data: Optional[dict]                     # load_context → analyst + forecaster
    analyst_summary: str                            # analyst → combine
    forecaster_summary: str                         # forecaster → combine
    messages: Annotated[list, add_messages]         # combine → optimizer ⇄ tools


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

FORECASTER_PROMPT = """You are a Deutsche Bahn mobility demand forecaster.
Today's date is June 2026. The next 6 months are July 2026 – December 2026.

Review the user's month-by-month travel history and respond with exactly these four sections:
1. HISTORICAL PATTERN — average trips per month and the dominant transport mode, grouped by season if relevant
2. SEASONALITY — any peaks, dips, or trends detected (e.g. fewer trips in August, holiday spikes in December)
3. 6-MONTH FORECAST — one line per month in this exact format:
   MONTH YEAR: N trips | mode: MODE | confidence: high/medium/low
4. DEMAND OUTLOOK — one sentence: is travel demand rising, stable, or declining, and why?

Base the forecast on patterns observed in the same calendar months in prior years.
Be quantitative. Do not make subscription recommendations."""

OPTIMIZER_PROMPT = """You are a Deutsche Bahn mobility optimizer.
You receive a combined analyst report (current inefficiencies) and a 6-month demand forecast.
The catalogue includes: DB cards (BahnCard 25/50/100), public transport subscriptions
(Deutschlandticket, Jobticket), bike sharing (Call a Bike, Nextbike, Swapfiets),
e-scooter passes (Dott, Voi, Lime, Bolt) and car sharing (Miles, Sixt Share, teilAuto).
Use the lookup_subscriptions tool with a targeted filter (e.g. 'bahncard', 'bike',
'scooter', 'carsharing', 'deutschlandticket') to retrieve only the relevant products.
Recommend the single best subscription change for this user — or the best combination
of two products if clearly beneficial. Factor in the demand forecast: only recommend
a subscription that makes sense given predicted trip volume over the next 6 months.
Explain the expected annual saving or convenience gain. Be concise — five sentences maximum."""

# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool
def lookup_subscriptions(filter_type: str = "all") -> str:
    """Look up mobility subscription products from the catalogue.

    Args:
        filter_type: 'all', 'card', 'subscription', 'pass',
                     'bahncard', 'deutschlandticket',
                     'bike', 'scooter', or 'carsharing'.

    Returns:
        JSON string with pricing and conditions per matching product.
    """
    from db.db_utils import get_subscription_products
    import json as _json

    products = get_subscription_products("all")

    ft = filter_type.lower().strip()
    if ft == "bahncard":
        products = [p for p in products if p["product_id"].startswith(("BC", "MY-BC"))]
    elif ft == "deutschlandticket":
        products = [p for p in products if p["product_id"].startswith("DT")]
    elif ft == "bike":
        products = [p for p in products if "shared_bike" in (p.get("valid_modes") or "")]
    elif ft == "scooter":
        products = [p for p in products if "shared_scooter" in (p.get("valid_modes") or "")]
    elif ft == "carsharing":
        products = [p for p in products if "car_sharing" in (p.get("valid_modes") or "")]
    elif ft in ("card", "subscription", "pass"):
        products = [p for p in products if p.get("type") == ft]

    if not products:
        return f"No products found for filter '{filter_type}'."

    slim = [
        {
            "product_id":            p["product_id"],
            "product_name":          p["product_name"],
            "type":                  p["type"],
            "monthly_cost_eur":      p["monthly_cost_eur"],
            "annual_cost_eur":       p["annual_cost_eur"],
            "discount_pct":          p["discount_pct"],
            "pricing_model":         p.get("pricing_model"),
            "cost_per_minute_eur":   p.get("cost_per_minute_eur"),
            "cost_per_km_eur":       p.get("cost_per_km_eur"),
            "unlock_fee_eur":        p.get("unlock_fee_eur"),
            "free_minutes_per_ride": p.get("free_minutes_per_ride"),
            "period_days":           p.get("period_days"),
            "valid_modes":           p.get("valid_modes"),
            "coverage_scope":        p["coverage_scope"],
            "min_commitment_months": p["min_commitment_months"],
            "auto_renews":           p["auto_renews"],
            "combinable_with":       p.get("combinable_with"),
            "eligibility_min_age":   p.get("eligibility_min_age"),
            "eligibility_max_age":   p.get("eligibility_max_age"),
            "eligibility_notes":     p.get("eligibility_notes"),
            "city_availability":     p.get("city_availability"),
            "notes":                 p["notes"],
        }
        for p in products
    ]
    return _json.dumps(slim, ensure_ascii=False, indent=2)


_tools = [lookup_subscriptions]

# ---------------------------------------------------------------------------
# LLM — lazy init
# ---------------------------------------------------------------------------

_llm: Optional[ChatOpenAI] = None
_llm_with_tools: Optional[ChatOpenAI] = None


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
        _llm_with_tools = _get_llm().bind_tools(_tools)
    return _llm_with_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_for_analyst(data: dict) -> str:
    """Compact trip summary for the analyst LLM."""
    subs = ", ".join(data.get("current_subscriptions") or ["none"])
    trips = data.get("travel_log", [])
    n = len(trips)
    total_cost = sum(t.get("cost_eur") or 0 for t in trips)
    total_co2 = sum(t.get("co2_kg") or 0 for t in trips)
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


def _format_for_forecaster(data: dict) -> str:
    """Month-by-month trip breakdown for the forecaster LLM."""
    subs = ", ".join(data.get("current_subscriptions") or ["none"])
    trips = data.get("travel_log", [])

    # Group trips by year-month
    monthly: dict[str, list] = defaultdict(list)
    for t in trips:
        date = t.get("date")
        if date:
            monthly[date[:7]].append(t)

    lines = [
        f"User: {data['name']} | Home: {data['home_city']}",
        f"Current subscriptions: {subs}",
        "",
        "Month-by-month trip history:",
    ]
    for ym in sorted(monthly.keys()):
        month_trips = monthly[ym]
        modes = Counter(t["mode"] for t in month_trips).most_common(2)
        top_modes = ", ".join(f"{m}×{n}" for m, n in modes)
        spend = sum(t.get("cost_eur") or 0 for t in month_trips)
        is_commute = sum(1 for t in month_trips if t.get("is_commute"))
        lines.append(
            f"  {ym}: {len(month_trips):3d} trips | modes: {top_modes} "
            f"| commute: {is_commute} | spend: €{spend:.2f}"
        )

    if not monthly:
        lines.append("  (no dated trip records found)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Node 0 — Load user context
# ---------------------------------------------------------------------------


def load_context_node(state: FullPipelineState) -> dict:
    """Resolve user_id and build the shared travel_data dict from SQLite."""
    raw_id = state["user_id"].strip()

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

    trip_log = [
        {
            "date":        t["start_ts"][:10] if t["start_ts"] else None,
            "from":        t["origin_city"],
            "to":          t["destination_city"],
            "mode":        t["main_mode"],
            "distance_km": t["distance_km"],
            "cost_eur":    t["estimated_cost_eur"],
            "co2_kg":      t["co2_kg"],
            "ticket":      t["ticket_product_used"],
            "purpose":     t["trip_purpose"],
            "is_commute":  bool(t["is_commute"]),
        }
        for t in trips
    ]

    return {
        "travel_data": {
            "name":                  f"{user['first_name']} {user['last_name']}",
            "user_id":               resolved_id,
            "home_city":             user["home_city"],
            "occupation":            user["job_industry"],
            "income_range":          user["income_range"],
            "price_sensitivity":     user["price_sensitivity"],
            "employer_reimbursement": bool(user.get("employer_reimbursement_available")),
            "current_subscriptions": [s["product_name"] for s in active_subs],
            "travel_log":            trip_log,
        }
    }


# ---------------------------------------------------------------------------
# Node 1a — Analyst  (runs in parallel with forecaster)
# ---------------------------------------------------------------------------


def analyst_node(state: FullPipelineState) -> dict:
    data = state.get("travel_data") or {}
    if "error" in data:
        return {"analyst_summary": f"Cannot analyse: {data['error']}"}
    response = _get_llm().invoke([
        SystemMessage(content=ANALYST_PROMPT),
        HumanMessage(content=_format_for_analyst(data)),
    ])
    return {"analyst_summary": response.content}


# ---------------------------------------------------------------------------
# Node 1b — Forecaster  (runs in parallel with analyst)
# ---------------------------------------------------------------------------


def forecaster_node(state: FullPipelineState) -> dict:
    data = state.get("travel_data") or {}
    if "error" in data:
        return {"forecaster_summary": f"Cannot forecast: {data['error']}"}
    response = _get_llm().invoke([
        SystemMessage(content=FORECASTER_PROMPT),
        HumanMessage(content=_format_for_forecaster(data)),
    ])
    return {"forecaster_summary": response.content}


# ---------------------------------------------------------------------------
# Node 2 — Combine  (fan-in: waits for both analyst + forecaster)
# ---------------------------------------------------------------------------


def combine_node(state: FullPipelineState) -> dict:
    """Merge analyst + forecaster outputs into the optimizer's first message."""
    data = state.get("travel_data") or {}
    subs = ", ".join(data.get("current_subscriptions") or ["none"])

    context = (
        f"## Analyst Report\n{state.get('analyst_summary', 'N/A')}\n\n"
        f"## 6-Month Demand Forecast\n{state.get('forecaster_summary', 'N/A')}\n\n"
        f"## Current subscriptions: {subs}\n\n"
        "Based on the analyst report AND the demand forecast above, recommend the best "
        "subscription change. Use the lookup_subscriptions tool to check the catalogue first."
    )
    return {"messages": [HumanMessage(content=context)]}


# ---------------------------------------------------------------------------
# Node 3 — Optimizer  (ReAct loop with lookup_subscriptions tool)
# ---------------------------------------------------------------------------


def optimizer_node(state: FullPipelineState) -> dict:
    response = _get_llm_with_tools().invoke(
        [SystemMessage(content=OPTIMIZER_PROMPT)] + state["messages"]
    )
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph():
    tool_node = ToolNode(_tools)
    workflow = StateGraph(FullPipelineState)

    workflow.add_node("load_context", load_context_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("forecaster", forecaster_node)
    workflow.add_node("combine", combine_node)
    workflow.add_node("optimizer", optimizer_node)
    workflow.add_node("tools", tool_node)

    # load_context fans out to analyst and forecaster — they run in parallel
    workflow.add_edge(START, "load_context")
    workflow.add_edge("load_context", "analyst")
    workflow.add_edge("load_context", "forecaster")

    # combine is the fan-in — runs once after BOTH analyst and forecaster finish
    workflow.add_edge("analyst", "combine")
    workflow.add_edge("forecaster", "combine")

    # optimizer ReAct loop
    workflow.add_edge("combine", "optimizer")
    workflow.add_conditional_edges("optimizer", tools_condition)
    workflow.add_edge("tools", "optimizer")

    return workflow.compile()


graph = build_graph()
