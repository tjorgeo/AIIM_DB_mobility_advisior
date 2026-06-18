"""
DB MoveOptimizer — Onboarding Agent
Conversational agent that collects a new user's mobility profile after login/registration.
On completion it persists the profile to SQLite so the downstream pipeline can read it.

How memory works (no database required for testing):
  LangGraph's `add_messages` reducer accumulates the full conversation history inside
  the graph state. Within a single LangSmith Studio thread the agent remembers every
  prior exchange automatically. No external store is needed at this stage.

Graph flow:
    onboarding_node  (conversational, multi-turn)
        ↓ (conditional: only when JSON profile block detected in last reply)
    save_profile_node  (persists profile to SQLite, no LLM)
        ↓
       END
    (if no JSON yet → loops back to END to wait for next user message)
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.db_utils import add_user_subscription, init_db, upsert_user

load_dotenv()
init_db()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNI_GPT_BASE_URL = "https://chat.kiconnect.nrw/api/v1"
UNI_GPT_MODEL = "Openai GPT OSS 120B"
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")

# Map free-text subscription names from onboarding to product_ids in the catalogue
SUBSCRIPTION_NAME_MAP: dict[str, str] = {
    "deutschlandticket": "DT-49",
    "deutschland ticket": "DT-49",
    "49-euro-ticket": "DT-49",
    "bahncard 25 (2nd class)": "BC25-2",
    "bahncard 25": "BC25-2",
    "bc25": "BC25-2",
    "bahncard 50 (2nd class)": "BC50-2",
    "bahncard 50": "BC50-2",
    "bc50": "BC50-2",
    "bahncard 100 (2nd class)": "BC100-2",
    "bahncard 100": "BC100-2",
    "bc100": "BC100-2",
    "bahncard 25 (1st class)": "BC25-1",
    "bahncard 50 (1st class)": "BC50-1",
    "bahncard 100 (1st class)": "BC100-1",
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

ONBOARDING_SYSTEM_PROMPT = """
You are the DB MoveOptimizer Onboarding Assistant.

=== STRICT RULES — FOLLOW THESE BEFORE ANYTHING ELSE ===

1. You run a structured interview with exactly 6 steps. Follow them in order.
2. In each step, ask ONLY the questions listed for that step. Nothing more.
3. After sending a step's questions, STOP and wait for the user to reply.
4. Only move to the next step after the user has answered the current one.
5. NEVER skip ahead, combine multiple steps, or anticipate future answers.
6. NEVER assume or infer anything about the user. Record only what they explicitly say.
7. If the user skips a question or is unsure, accept it and move on. Do not press.
8. The JSON OUTPUT TEMPLATE at the bottom of this prompt contains NO user data.
   It is a blank template with field names only. Do not read it as information about
   the current user.

=== YOUR INTRODUCTION ===

When the user first contacts you, send this before asking any questions:

- Greet them warmly and introduce yourself as the DB MoveOptimizer assistant.
- Explain in one sentence what MoveOptimizer does: it analyses travel history from
  Deutsche Bahn and mobility partners to recommend the most cost-effective and
  personalised subscription portfolio.
- Tell them the profile setup takes about 2-3 minutes and their data is stored
  securely.
- Then immediately ask Step 1.

Respond in the same language the user writes in (German or English).

=== STEP 1 — Basic Profile ===

Ask these three questions together in one message:
  - How old are you?
  - Which city or postal code do you live in? (City name or PLZ is enough — no street needed.)
  - What is your current occupation or job?

Then move to Step 2.

=== STEP 2 — Mobility Preferences ===

Open with one sentence explaining the scale: 0 = not important at all, 10 = extremely important.

Then ask all three preference questions together in one message:
  - Cost savings: how important is it to you to reduce your travel costs? (0-10)
  - CO2 savings: how important is reducing the environmental impact of your travel? (0-10)
  - Flexibility: how important is it to travel on your own schedule, without being tied
    to timetables, booking windows, or fixed zones? (0-10)

Wait for the user to give three numbers, then move to Step 3.

=== STEP 3 — Current Subscriptions ===

Ask in one message:
  - Which mobility subscriptions do you currently hold?

If the user seems unsure what counts, offer these examples as a prompt
(do not list them unprompted on the first ask):
  BahnCard 25 / 50 / 100 (1st or 2nd class),
  Deutschlandticket (49 EUR/month),
  regional season tickets (e.g. NRW-Ticket Abo, Bayern-Ticket Abo),
  car-sharing or bike-sharing memberships (e.g. SHARE NOW, nextbike),
  other local public transport subscriptions.

After the user answers, move to Step 4.

=== STEP 4 — Deutschlandticket Usage ===

ONLY ask this step if the user mentioned holding a Deutschlandticket in Step 3.
If they did not mention it, skip directly to Step 5.

Ask in one message:
  - On how many days per month do you typically use your Deutschlandticket?

After the user answers (or if skipped), move to Step 5.

=== STEP 5 — Owned Vehicles ===

Ask in one message:
  - Do you own or regularly use a private car? If yes, do you mainly use it for
    commuting, intercity trips, or both?
  - Do you own a bicycle (standard or e-bike)?

After the user answers, move to Step 6.

=== STEP 6 — Future Travel Plans ===

Ask in one message:
  - Do you expect any significant changes to your travel behaviour in the next
    6-12 months?

If the user seems unsure, you may offer these as examples to jog their memory:
  starting a new job, relocating, a new recurring long-distance route, extended
  remote work, or any other life event that would change how often or where they travel.

After the user answers, proceed to PROFILE OUTPUT.

=== PROFILE OUTPUT ===

Once Step 6 is complete:
1. Send a short, friendly closing message summarising what was collected and confirming
   the profile is being saved.
2. Immediately after that message, output the completed profile as a JSON code block
   tagged with "json".

--- JSON OUTPUT TEMPLATE (blank — contains NO user data) ---

Fill every field with the value the user gave you. Use null for anything they skipped.

```json
{
  "age": null,
  "home_location": null,
  "occupation": null,
  "preferences": {
    "cost_savings": null,
    "co2_savings": null,
    "flexibility": null
  },
  "future_travel_plans": null,
  "current_subscriptions": [],
  "owns_car": null,
  "car_usage": null,
  "owns_bike": null,
  "deutschlandticket_days_per_month": null
}
```

Field types for reference (do not include this comment in output):
  age                              — integer
  home_location                    — string (city or postal code)
  occupation                       — string
  preferences.*                    — integer 0-10
  future_travel_plans              — string (free text summary)
  current_subscriptions            — list of strings
  owns_car / owns_bike             — true or false
  car_usage                        — "commute", "intercity", or "both"
  deutschlandticket_days_per_month — integer
"""

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class OnboardingState(TypedDict):
    messages: Annotated[list, add_messages]
    # Optional: pre-fill user_id from auth system; generated if absent
    user_id: Optional[str]
    # Set to True once the profile has been saved to avoid double-writes
    profile_saved: bool


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
# Helpers
# ---------------------------------------------------------------------------

def _extract_profile_json(text: str) -> dict | None:
    """Return parsed profile dict if the message contains a ```json block."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _map_profile_to_db(profile: dict, user_id: str) -> dict:
    """Translate the onboarding JSON schema to the users table column names."""
    prefs = profile.get("preferences") or {}
    return {
        "user_id": user_id,
        "username": f"user_{user_id[:8]}",   # placeholder; overwrite if auth provides it
        "home_city": profile.get("home_location"),
        "job_industry": profile.get("occupation"),
        "has_car": 1 if profile.get("owns_car") else 0,
        "has_bike": 1 if profile.get("owns_bike") else 0,
        "pref_cost_savings": prefs.get("cost_savings"),
        "pref_co2_savings": prefs.get("co2_savings"),
        "pref_flexibility": prefs.get("flexibility"),
        "future_travel_plans": profile.get("future_travel_plans"),
        "onboarding_completed_at": datetime.utcnow().isoformat(),
    }


def _save_subscriptions(profile: dict, user_id: str) -> None:
    """Write any recognised subscription names to user_subscriptions."""
    for name in profile.get("current_subscriptions") or []:
        product_id = SUBSCRIPTION_NAME_MAP.get(name.lower().strip())
        if not product_id:
            continue
        add_user_subscription({
            "user_subscription_id": str(uuid.uuid4()),
            "user_id": user_id,
            "product_id": product_id,
            "status": "active",
            "start_date": datetime.utcnow().date().isoformat(),
            "source": "onboarding",
        })


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def onboarding_node(state: OnboardingState) -> dict:
    """Single-node conversational loop. Runs on every user message."""
    response = _get_llm().invoke(
        [SystemMessage(content=ONBOARDING_SYSTEM_PROMPT)] + state["messages"]
    )
    return {"messages": [response]}


def save_profile_node(state: OnboardingState) -> dict:
    """Extract the JSON from the last assistant message and persist to SQLite."""
    if state.get("profile_saved"):
        return {}

    last_content = state["messages"][-1].content
    profile = _extract_profile_json(last_content)
    if not profile:
        return {}

    user_id = state.get("user_id") or str(uuid.uuid4())
    db_row = _map_profile_to_db(profile, user_id)
    upsert_user(db_row)
    _save_subscriptions(profile, user_id)

    return {"user_id": user_id, "profile_saved": True}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def _should_save(state: OnboardingState) -> str:
    """Route to save_profile only when the LLM has emitted the final JSON block."""
    if state.get("profile_saved"):
        return END
    last_msg = state["messages"][-1] if state["messages"] else None
    if last_msg and hasattr(last_msg, "content") and "```json" in last_msg.content:
        return "save_profile"
    return END


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    workflow = StateGraph(OnboardingState)
    workflow.add_node("onboarding", onboarding_node)
    workflow.add_node("save_profile", save_profile_node)
    workflow.add_edge(START, "onboarding")
    workflow.add_conditional_edges("onboarding", _should_save)
    workflow.add_edge("save_profile", END)
    return workflow.compile()


graph = build_graph()
