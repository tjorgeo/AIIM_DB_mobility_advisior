"""
DB MoveOptimizer — Travel Pattern Analyst Agent
Reads user profile and trip data from SQLite and produces a concise mobility
behaviour summary. Runs as a two-node pipeline: load_data → analyze.
"""

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# db_utils lives one level up from this file
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.db_utils import get_trips, get_user, get_user_by_username, get_user_subscriptions, init_db

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


class TravelAnalystState(TypedDict):
    # Input: UUID or username (e.g. "mia.schmidt")
    user_id: str
    # Internal
    data_summary: Optional[str]
    # Output
    messages: Annotated[list, add_messages]


# ---------------------------------------------------------------------------
# LLM — lazy init
# ---------------------------------------------------------------------------

_llm = None


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


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

ANALYST_SYSTEM_PROMPT = """
You are a mobility data analyst for DB MoveOptimizer.
You receive a structured data dump of a user's profile and travel statistics.
Your task: write a concise, insightful analysis of that person's mobility behaviour.

Structure your response exactly as follows:

**1. Person Overview**
Two to three sentences on who this person is (demographics, lifestyle context).

**2. Key Travel Patterns**
Four to five bullet points with specific observations drawn from the numbers
(dominant modes, commute rhythm, most frequent routes, planning style, etc.).

**3. Cost & Ticket Behaviour**
Two to three sentences on what they spend, which ticket products they use, and
whether there is an obvious optimisation opportunity.

**4. Mobility Profile Label**
One short tag that captures their travel identity.
Example: "Sustainable Long-Distance Commuter" or "Flexible Urban Explorer".

Rules:
- Be specific — reference names, numbers, and cities from the data.
- Keep total response under 350 words.
- Do not invent information not present in the data.
"""

# ---------------------------------------------------------------------------
# Node 1 — Load & summarise data from SQLite
# ---------------------------------------------------------------------------


def load_data_node(state: TravelAnalystState) -> dict:
    """Query SQLite for the requested user and compute key statistics."""
    raw_id = state["user_id"].strip()

    # LangSmith Studio sometimes passes the whole JSON object as the field value
    if raw_id.startswith("{"):
        try:
            raw_id = json.loads(raw_id).get("user_id", raw_id).strip()
        except json.JSONDecodeError:
            pass

    # Support UUID or username lookup
    p = get_user(raw_id) or get_user_by_username(raw_id)
    if not p:
        return {"data_summary": f"ERROR: No user found for identifier '{raw_id}'."}

    resolved_id = p["user_id"]
    trips = get_trips(resolved_id)
    active_subs = get_user_subscriptions(resolved_id, status="active")

    lines: list[str] = []

    # ── Profile ──────────────────────────────────────────────────────────────
    lines += [
        "## User Profile",
        f"- Name: {p['first_name']} {p['last_name']}",
        f"- Age: {p.get('date_of_birth', 'unknown')} | Gender: {p['gender']} | Life stage: {p['life_stage']}",
        f"- Home city: {p['home_city']} ({p['city_type']}, {p['home_country_code']})",
        f"- Occupation: {p['job_industry']} | Status: {p['employment_status']}",
        f"- Work pattern: {p['working_pattern']} | Commute frequency: {p['commute_frequency']}",
        f"- Income range: {p['income_range']}",
        f"- Has car: {bool(p['has_car'])} | Has bike: {bool(p['has_bike'])} | Licence: {bool(p['has_driving_license'])}",
        f"- PT affinity: {p['public_transport_affinity']}",
        f"- Preferred modes: {p['preferred_modes']}",
        f"- Avoided modes: {p['avoided_modes']}",
        f"- Price sensitivity: {p['price_sensitivity']}",
        f"- Employer reimbursement: {bool(p['employer_reimbursement_available'])}",
        f"- Leisure intensity: {p['leisure_intensity']}",
    ]

    if active_subs:
        sub_names = ", ".join(s["product_name"] for s in active_subs)
        lines.append(f"- Active subscriptions: {sub_names}")
    else:
        lines.append("- Active subscriptions: none")

    if not trips:
        lines.append("\n## Trip Data: No trips recorded for this user.")
        return {"data_summary": "\n".join(lines)}

    # ── Trip statistics ───────────────────────────────────────────────────────
    n = len(trips)
    total_cost = sum(t["estimated_cost_eur"] or 0 for t in trips)
    total_dist = sum(t["distance_km"] or 0 for t in trips)
    total_co2 = sum(t["co2_kg"] or 0 for t in trips)
    total_dur = sum(t["duration_min"] or 0 for t in trips)
    commute_n = sum(1 for t in trips if t["is_commute"])

    lines += [
        f"\n## Trip Statistics ({n} trips total)",
        f"- Total distance: {total_dist:.1f} km",
        f"- Total duration: {total_dur:.0f} min ({total_dur / 60:.1f} h)",
        f"- Total estimated cost: €{total_cost:.2f}",
        f"- Average cost per trip: €{total_cost / n:.2f}",
        f"- Total CO₂: {total_co2:.1f} kg",
        f"- Commute trips: {commute_n} ({commute_n / n * 100:.0f}%)",
        f"- Non-commute trips: {n - commute_n} ({(n - commute_n) / n * 100:.0f}%)",
    ]

    # Mode distribution
    from collections import Counter
    mode_counts = Counter(t["main_mode"] for t in trips)
    lines.append("\n### Mode Distribution (by trip count):")
    for mode, count in mode_counts.most_common():
        lines.append(f"  - {mode}: {count} trips ({count / n * 100:.0f}%)")

    # Trip purposes
    purpose_counts = Counter(t["trip_purpose"] for t in trips)
    lines.append("\n### Trip Purposes:")
    for purpose, count in purpose_counts.most_common():
        lines.append(f"  - {purpose}: {count}")

    # Ticket products with cost
    ticket_cost: dict[str, list] = {}
    for t in trips:
        key = t["ticket_product_used"] or "none"
        ticket_cost.setdefault(key, [0, 0])
        ticket_cost[key][0] += 1
        ticket_cost[key][1] += t["estimated_cost_eur"] or 0
    lines.append("\n### Ticket Products Used:")
    for ticket, (count, cost) in sorted(ticket_cost.items(), key=lambda x: -x[1][0]):
        lines.append(f"  - {ticket}: {count} trips | total cost €{cost:.2f}")

    # Weekday pattern
    weekday_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    weekday_counts = Counter(t["weekday"] for t in trips)
    lines.append("\n### Trips by Weekday:")
    for day in weekday_order:
        if day in weekday_counts:
            lines.append(f"  - {day}: {weekday_counts[day]}")

    # Top 5 routes
    route_counts = Counter(
        f"{t['origin_city']} → {t['destination_city']}" for t in trips
    )
    lines.append("\n### Top 5 Routes:")
    for route, count in route_counts.most_common(5):
        lines.append(f"  - {route}: {count} trips")

    # Planning style
    style_counts = Counter(t["planning_style"] for t in trips if t["planning_style"])
    lines.append("\n### Planning Style:")
    for style, count in style_counts.most_common():
        lines.append(f"  - {style}: {count} trips")

    return {"data_summary": "\n".join(lines)}


# ---------------------------------------------------------------------------
# Node 2 — LLM analysis
# ---------------------------------------------------------------------------


def analyze_node(state: TravelAnalystState) -> dict:
    summary = state.get("data_summary") or "No data available."
    response = _get_llm().invoke([
        SystemMessage(content=ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=f"Analyse this user's travel data:\n\n{summary}"),
    ])
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    workflow = StateGraph(TravelAnalystState)
    workflow.add_node("load_data", load_data_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_edge(START, "load_data")
    workflow.add_edge("load_data", "analyze")
    workflow.add_edge("analyze", END)
    return workflow.compile()


graph = build_graph()
