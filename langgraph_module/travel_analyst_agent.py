"""
DB MoveOptimizer — Travel Pattern Analyst Agent
Reads synthetic CSV data for a given user_id and produces a concise mobility
behaviour summary. Runs as a two-node pipeline: load_data → analyze.
"""

import os
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNI_GPT_BASE_URL = "https://chat.kiconnect.nrw/api/v1"
UNI_GPT_MODEL = "Openai GPT OSS 120B"
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")

DATA_DIR = Path(__file__).parent.parent / "data"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TravelAnalystState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    # Accepts either an exact user_id UUID or a username (e.g. "mia.schmidt").
    user_id: str
    # ── Internal ───────────────────────────────────────────────────────────
    data_summary: Optional[str]   # structured stats built by load_data_node
    # ── Output ─────────────────────────────────────────────────────────────
    messages: Annotated[list, add_messages]  # LLM response accumulated here


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
# Node 1 — Load & summarise data
# ---------------------------------------------------------------------------


def load_data_node(state: TravelAnalystState) -> dict:
    """Load CSVs, filter for the requested user, and compute key statistics."""
    raw_id = state["user_id"].strip()

    # LangSmith Studio sometimes passes the entire JSON object as the field value.
    # If that happens, unwrap it.
    if raw_id.startswith("{"):
        import json as _json
        try:
            raw_id = _json.loads(raw_id).get("user_id", raw_id).strip()
        except _json.JSONDecodeError:
            pass

    profiles = pd.read_csv(DATA_DIR / "user_profiles.csv")
    trips_df = pd.read_csv(DATA_DIR / "user_trips.csv")

    # Support lookup by UUID or by username
    profile_row = profiles[profiles["user_id"] == raw_id]
    if profile_row.empty:
        profile_row = profiles[profiles["username"] == raw_id]
    if profile_row.empty:
        return {"data_summary": f"ERROR: No user found for identifier '{raw_id}'."}

    p = profile_row.iloc[0]
    resolved_id = p["user_id"]
    user_trips = trips_df[trips_df["user_id"] == resolved_id].copy()

    lines: list[str] = []

    # ── Profile section ─────────────────────────────────────────────────────
    lines += [
        "## User Profile",
        f"- Name: {p['first_name']} {p['last_name']}",
        f"- Age: {p['age']} | Gender: {p['gender']} | Life stage: {p['life_stage']}",
        f"- Home city: {p['home_city']} ({p['city_type']}, {p['home_country_code']})",
        f"- Occupation: {p['job_industry']} | Status: {p['employment_status']}",
        f"- Work pattern: {p['working_pattern']} | Commute frequency: {p['commute_frequency']}",
        f"- Income range: {p['income_range']}",
        f"- Has car: {p['has_car']} | Has bike: {p['has_bike']} | Driving licence: {p['has_driving_license']}",
        f"- PT affinity: {p['public_transport_affinity']}",
        f"- Preferred modes: {p['preferred_modes']}",
        f"- Avoided modes: {p['avoided_modes']}",
        f"- Current ticket product: {p['current_ticket_product']}",
        f"- Subscription likelihood: {p['subscription_likelihood']}",
        f"- Price sensitivity: {p['price_sensitivity']}",
        f"- Purchase channel: {p['purchase_channel_preference']}",
        f"- Employer reimbursement: {p['employer_reimbursement_available']}",
        f"- Leisure intensity: {p['leisure_intensity']}",
        f"- Preferred activities: {p['preferred_activity_types']}",
        f"- Travel statement: {p['travel_and_priorities']}",
    ]

    if user_trips.empty:
        lines.append("\n## Trip Data: No trips recorded for this user.")
        return {"data_summary": "\n".join(lines)}

    # Normalise boolean column (CSV stores "true"/"false" as strings)
    user_trips["is_commute"] = user_trips["is_commute"].astype(str).str.lower() == "true"

    n = len(user_trips)
    total_cost = user_trips["estimated_cost_eur"].sum()
    total_dist = user_trips["distance_km"].sum()
    total_dur_min = user_trips["duration_min"].sum()
    commute_n = user_trips["is_commute"].sum()

    lines += [
        f"\n## Trip Statistics ({n} trips total)",
        f"- Total distance: {total_dist:.1f} km",
        f"- Total duration: {total_dur_min:.0f} min ({total_dur_min / 60:.1f} h)",
        f"- Total estimated cost: €{total_cost:.2f}",
        f"- Average cost per trip: €{total_cost / n:.2f}",
        f"- Commute trips: {commute_n} ({commute_n / n * 100:.0f}%)",
        f"- Non-commute trips: {n - commute_n} ({(n - commute_n) / n * 100:.0f}%)",
    ]

    # Mode distribution
    mode_dist = user_trips["main_mode"].value_counts()
    lines.append("\n### Mode Distribution (by trip count):")
    for mode, count in mode_dist.items():
        lines.append(f"  - {mode}: {count} trips ({count / n * 100:.0f}%)")

    # Trip purposes
    purpose_dist = user_trips["trip_purpose"].value_counts()
    lines.append("\n### Trip Purposes:")
    for purpose, count in purpose_dist.items():
        lines.append(f"  - {purpose}: {count}")

    # Ticket products
    ticket_dist = user_trips["ticket_product_used"].value_counts()
    lines.append("\n### Ticket Products Used:")
    for ticket, count in ticket_dist.items():
        cost_for_ticket = user_trips[user_trips["ticket_product_used"] == ticket]["estimated_cost_eur"].sum()
        lines.append(f"  - {ticket}: {count} trips | total cost €{cost_for_ticket:.2f}")

    # Weekday pattern
    weekday_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    weekday_dist = user_trips["weekday"].value_counts().reindex(weekday_order).dropna().astype(int)
    lines.append("\n### Trips by Weekday:")
    for day, count in weekday_dist.items():
        lines.append(f"  - {day}: {count}")

    # Top 5 routes
    user_trips["route"] = user_trips["origin_city"] + " → " + user_trips["destination_city"]
    top_routes = user_trips["route"].value_counts().head(5)
    lines.append("\n### Top 5 Routes:")
    for route, count in top_routes.items():
        lines.append(f"  - {route}: {count} trips")

    # Planning style
    plan_dist = user_trips["planning_style"].value_counts()
    lines.append("\n### Planning Style:")
    for style, count in plan_dist.items():
        lines.append(f"  - {style}: {count} trips")

    return {"data_summary": "\n".join(lines)}


# ---------------------------------------------------------------------------
# Node 2 — LLM analysis
# ---------------------------------------------------------------------------


def analyze_node(state: TravelAnalystState) -> dict:
    """Send the pre-computed statistics to the LLM for a readable summary."""
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
