"""Conversational onboarding agent for POST /api/onboarding (Phase 4).

A LangGraph workflow that interviews a new user and, once it emits the final
profile JSON, persists a row into the Postgres `users` table (this project's
schema). Adapted from Maike's onboarding agent; the prompt is kept, the persist
step is rewritten for our schema.

Note (provisional): the frontend currently logs in via fixed demo personas, so
onboarded users are not yet surfaced in the UI — this endpoint makes the agent
usable/testable ahead of that wiring. Requires an API key (main.py guards it).
"""

import json
import re
import uuid
from datetime import datetime
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import SystemMessage
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages

from database import get_connection
from graph.llm import get_llm

ONBOARDING_SYSTEM_PROMPT = """
You are the DB MoveOptimizer Onboarding Assistant.

Run a friendly, structured interview to build the user's mobility profile, in 6 steps,
asking ONE step at a time and waiting for the answer before moving on:
1. Basic profile: age, home city/postal code, occupation.
2. Preferences (scale 0-10): cost savings, CO2 savings, flexibility.
3. Current mobility subscriptions (BahnCard 25/50/100, Deutschlandticket, car/bike sharing, ...).
4. (Only if they hold a Deutschlandticket) days per month they use it.
5. Owned vehicles: private car (and usage: commute/intercity/both), bicycle.
6. Expected travel changes in the next 6-12 months.

Respond in the user's language. Never invent answers; use null for anything skipped.

When step 6 is done, send a short closing message, then output the completed profile
as a ```json code block with exactly these fields:
{
  "age": null,
  "home_location": null,
  "occupation": null,
  "preferences": { "cost_savings": null, "co2_savings": null, "flexibility": null },
  "future_travel_plans": null,
  "current_subscriptions": [],
  "owns_car": null,
  "car_usage": null,
  "owns_bike": null,
  "deutschlandticket_days_per_month": null
}
"""

# Onboarding free-text subscription name -> tjorge pricing_catalog product id.
SUBSCRIPTION_NAME_MAP = {
    "deutschlandticket": "deutschlandticket",
    "deutschland ticket": "deutschlandticket",
    "49-euro-ticket": "deutschlandticket",
    "bahncard 25": "bahncard_25_2nd",
    "bc25": "bahncard_25_2nd",
    "bahncard 50": "bahncard_50_2nd",
    "bc50": "bahncard_50_2nd",
    "bahncard 100": "bahncard_100_2nd",
    "bc100": "bahncard_100_2nd",
    "miles": "miles_sharing",
    "car sharing": "miles_sharing",
    "car-sharing": "miles_sharing",
}


class OnboardingState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_id: Optional[str]
    profile_saved: bool


def _onboarding_node(state: OnboardingState) -> dict:
    response = get_llm().invoke(
        [SystemMessage(content=ONBOARDING_SYSTEM_PROMPT)] + state["messages"]
    )
    return {"messages": [response]}


def _extract_profile_json(text: str):
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL) or re.search(
        r"(\{.*\})", text, re.DOTALL
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _pref_to_priority(value, default=50):
    """Map an onboarding 0-10 score to tjorge's 0-100 priority weight."""
    if value is None:
        return default
    try:
        return int(round(float(value) * 10))
    except (TypeError, ValueError):
        return default


def save_profile(profile: dict, user_id: Optional[str] = None) -> str:
    """Persist an onboarding profile to the users table. Returns the user_id."""
    uid = user_id or str(uuid.uuid4())
    db_customer_id = "DB-" + uid[:8].upper()
    prefs = profile.get("preferences") or {}
    preferences = {
        "cost_priority": _pref_to_priority(prefs.get("cost_savings")),
        "co2_priority": _pref_to_priority(prefs.get("co2_savings")),
        "convenience_priority": _pref_to_priority(prefs.get("flexibility")),
        "class_preference": "2nd",
    }
    consent = {"email_opted_in": False, "calendar_shared": False, "data_sharing_approved": True}
    name = profile.get("occupation") or "New User"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (id, db_customer_id, name, created_at, preferences, consent_status)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE
          SET preferences = EXCLUDED.preferences,
              consent_status = EXCLUDED.consent_status
        """,
        (
            uid,
            db_customer_id,
            name,
            datetime.now().isoformat(),
            json.dumps(preferences),
            json.dumps(consent),
        ),
    )

    for raw in profile.get("current_subscriptions") or []:
        service = SUBSCRIPTION_NAME_MAP.get(str(raw).lower().strip())
        if not service:
            continue
        cursor.execute("SELECT monthly_cost FROM pricing_catalog WHERE id = ?", (service,))
        row = cursor.fetchone()
        monthly = float(row["monthly_cost"]) if row else 0.0
        cursor.execute(
            """INSERT INTO subscriptions (id, user_id, service, status, monthly_cost_eur, renewal_date)
               VALUES (?, ?, ?, 'active', ?, NULL)""",
            (str(uuid.uuid4()), uid, service, monthly),
        )

    conn.commit()
    conn.close()
    return uid


def _save_profile_node(state: OnboardingState) -> dict:
    if state.get("profile_saved"):
        return {}
    profile = _extract_profile_json(state["messages"][-1].content)
    if not profile:
        return {}
    uid = save_profile(profile, state.get("user_id"))
    return {"user_id": uid, "profile_saved": True}


def _route(state: OnboardingState) -> str:
    last = state["messages"][-1] if state.get("messages") else None
    if last is not None and "```json" in getattr(last, "content", ""):
        return "save_profile"
    return END


def build_graph():
    workflow = StateGraph(OnboardingState)
    workflow.add_node("onboarding", _onboarding_node)
    workflow.add_node("save_profile", _save_profile_node)
    workflow.add_edge(START, "onboarding")
    workflow.add_conditional_edges("onboarding", _route)
    workflow.add_edge("save_profile", END)
    return workflow.compile()


graph = build_graph()


def run_onboarding(messages: list, user_id: Optional[str] = None) -> dict:
    from langchain_core.messages import HumanMessage, AIMessage

    lc_messages = [
        AIMessage(content=m["content"]) if m.get("role") == "assistant"
        else HumanMessage(content=m["content"])
        for m in messages
    ]
    result = graph.invoke({"messages": lc_messages, "user_id": user_id})
    return {
        "reply": result["messages"][-1].content,
        "profile_saved": bool(result.get("profile_saved")),
        "user_id": result.get("user_id"),
    }
