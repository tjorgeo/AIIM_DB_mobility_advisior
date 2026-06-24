"""Agentic analyze pipeline (LangGraph).

Topology:
    START → load_context → { analyst ∥ forecaster ∥ optimizer } → communicator → END

The analyst / forecaster / optimizer nodes wrap the deterministic agents and are
the authoritative source of every number the frontend reads, so the API contract
is guaranteed stable. The communicator node runs the deterministic agent for its
structured fields, then — when an LLM is configured — replaces the memo prose with
an LLM-written version. If the LLM is missing or errors, the template memo stands.
"""

import json
import re
from typing import TypedDict

from langgraph.graph import START, END, StateGraph

from database import get_connection
from agents.analyst import AnalystAgent
from agents.forecaster import ForecasterAgent
from agents.optimizer import OptimizerAgent
from agents.communicator import CommunicatorAgent
from graph.llm import llm_available, get_llm


class AnalyzeState(TypedDict, total=False):
    user_id: str
    user: dict
    user_preferences: dict
    user_consent: dict
    subscriptions: list
    travel_history: list
    pricing_catalog: list
    analyst_out: dict
    forecaster_out: dict
    optimizer_out: dict
    communicator_out: dict
    memos: dict
    error: str


_analyst = AnalystAgent()
_forecaster = ForecasterAgent()
_optimizer = OptimizerAgent()
_communicator = CommunicatorAgent()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def load_context_node(state: AnalyzeState) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (state["user_id"],))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return {"error": f"User with ID {state['user_id']} not found in database."}

    user = dict(user_row)
    preferences = json.loads(user["preferences"])
    consent = json.loads(user["consent_status"])

    cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (state["user_id"],))
    subscriptions = [dict(r) for r in cursor.fetchall()]

    cursor.execute(
        "SELECT * FROM travel_history WHERE user_id = ? ORDER BY trip_date ASC",
        (state["user_id"],),
    )
    travel_history = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM pricing_catalog")
    pricing_catalog = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "user": user,
        "user_preferences": preferences,
        "user_consent": consent,
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": pricing_catalog,
    }


def analyst_node(state: AnalyzeState) -> dict:
    if state.get("error"):
        return {}
    out = _analyst.run(state["travel_history"], state["subscriptions"])
    out["preferences"] = state["user_preferences"]  # referenced by communicator
    return {"analyst_out": out}


def forecaster_node(state: AnalyzeState) -> dict:
    if state.get("error"):
        return {}
    return {"forecaster_out": _forecaster.run(state["travel_history"])}


def optimizer_node(state: AnalyzeState) -> dict:
    if state.get("error"):
        return {}
    out = _optimizer.run(
        state["travel_history"],
        state["subscriptions"],
        state["pricing_catalog"],
        state["user_preferences"],
    )
    return {"optimizer_out": out}


def communicator_node(state: AnalyzeState) -> dict:
    if state.get("error"):
        return {}
    name = state["user"]["name"]
    analyst_out = state["analyst_out"]
    optimizer_out = state["optimizer_out"]

    # Deterministic baseline: structured fields + template memos (the fallback).
    comm = _communicator.run(name, analyst_out, optimizer_out)
    comm["memo_source"] = "template"

    if llm_available():
        try:
            memo_en, memo_de = _llm_memos(name, analyst_out, optimizer_out)
            comm["memo_english"] = memo_en
            comm["memo_german"] = memo_de
            comm["memo_source"] = "llm"
        except Exception:
            comm["memo_source"] = "template_fallback"

    return {
        "communicator_out": comm,
        "memos": {"english": comm["memo_english"], "german": comm["memo_german"]},
    }


# ---------------------------------------------------------------------------
# LLM memo generation
# ---------------------------------------------------------------------------

_MEMO_SYSTEM = (
    "You are the DB MoveOptimizer strategy advisor. Write a concise, warm consulting "
    "memo to the customer recommending the chosen mobility subscription plan. Explain "
    "the annual savings, the CO2 impact, and the concrete contract changes required, "
    "grounded ONLY in the data provided. Use short markdown sections.\n"
    'Respond with STRICT JSON and nothing else: {"english": "<memo>", "german": "<memo>"}. '
    "The german value must be a natural German translation of the english memo."
)


def _llm_memos(name: str, analyst_out: dict, optimizer_out: dict):
    from langchain_core.messages import SystemMessage, HumanMessage

    best_id = optimizer_out["best_recommendation_id"]
    scenario = next(
        (s for s in optimizer_out["scenarios"] if s["id"] == best_id),
        optimizer_out["scenarios"][0],
    )
    payload = {
        "customer_name": name,
        "baseline_annual_cost_eur": optimizer_out["baseline_annual_cost"],
        "recommended_plan": scenario["label"],
        "annual_cost_eur": scenario["annual_cost"],
        "annual_savings_eur": scenario["annual_savings"],
        "co2_savings_kg": scenario["co2_savings_kg"],
        "changes": scenario["changes"],
        "detected_inefficiencies": analyst_out.get("inefficiencies", []),
        "preferences": analyst_out.get("preferences", {}),
    }

    response = get_llm().invoke([
        SystemMessage(content=_MEMO_SYSTEM),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
    ])
    data = _extract_json(response.content)
    if not data or "english" not in data or "german" not in data:
        raise ValueError("LLM memo response missing english/german keys")
    return data["english"], data["german"]


def _extract_json(text: str):
    """Pull the first JSON object out of an LLM reply (handles ```json fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(AnalyzeState)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("forecaster", forecaster_node)
    workflow.add_node("optimizer", optimizer_node)
    workflow.add_node("communicator", communicator_node)

    workflow.add_edge(START, "load_context")
    # fan-out: analyst, forecaster, optimizer run in parallel
    workflow.add_edge("load_context", "analyst")
    workflow.add_edge("load_context", "forecaster")
    # workflow.add_edge("load_context", "optimizer")
    # fan-in: communicator waits for all three
    workflow.add_edge("analyst", "optimizer")
    workflow.add_edge("forecaster", "optimizer")
    workflow.add_edge("optimizer", "communicator")
    workflow.add_edge("communicator", END)

    return workflow.compile()


graph = build_graph()
