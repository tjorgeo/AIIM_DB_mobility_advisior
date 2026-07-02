"""The Communicator agent — customer-facing chat for POST /api/chat.

A ReAct loop grounded in the caller's persona and their most recent recommendation
(produced by the Analyst), so it can explain and defend the plan the dashboard shows.
It can read the live catalogue and the OKF tariff knowledge base to answer pricing and
tariff-condition questions accurately.

Only invoked when an API key is configured (main.py guards with llm_available()), so the
frontend's scripted fallback covers the no-key case.
"""

import json
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from database import get_connection
from agent.schema_map import preferences_from_onboarding
from agent.llm import get_llm
from agent.tools.catalog import lookup_subscriptions
from agent.tools.knowledge import list_tariff_docs, read_tariff_doc

_PROMPT_PATH = Path(__file__).with_name("prompts") / "communicator_system.md"
_SYSTEM_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_RECURSION_LIMIT = 12
_TOOLS = [lookup_subscriptions, list_tariff_docs, read_tariff_doc]


def _load_user_context(user_id: str) -> str:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id, first_name, last_name, home_city FROM users WHERE user_id = ?",
        (user_id,),
    )
    user = cursor.fetchone()
    if not user:
        conn.close()
        return "No profile found for this user."

    cursor.execute("SELECT * FROM user_onboardings WHERE user_id = ?", (user_id,))
    preferences = preferences_from_onboarding(cursor.fetchone())

    cursor.execute(
        """
        SELECT c.provider_plan_name
        FROM user_subscriptions s
        LEFT JOIN subscription_catalogs c ON c.subscription_id = s.subscription_id
        WHERE s.user_id = ? AND s.subscription_status = 'active'
        """,
        (user_id,),
    )
    services = [r["provider_plan_name"] for r in cursor.fetchall() if r["provider_plan_name"]]

    cursor.execute(
        "SELECT optimizer_scenarios FROM recommendations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    rec_row = cursor.fetchone()
    conn.close()

    name = f"{user['first_name']} {user['last_name']}".strip()
    lines = [
        f"Customer: {name} (id {user['user_id']}, home city {user['home_city']})",
        f"Preferences (0-100): {preferences}",
        f"Active subscriptions: {', '.join(services) or 'none'}",
    ]
    if rec_row and rec_row["optimizer_scenarios"]:
        data = json.loads(rec_row["optimizer_scenarios"])
        best = data.get("best_recommendation_id")
        scen = next((s for s in data.get("scenarios", []) if s["id"] == best), None)
        if scen:
            lines.append(
                f"Latest recommendation: {scen['label']} — annual cost €{scen['annual_cost']}, "
                f"saving €{scen['annual_savings']}/yr, changes: {scen['changes']}"
            )
    return "\n".join(lines)


def _to_lc_messages(messages: list):
    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def run_chat(user_id: str, messages: list) -> str:
    context = _load_user_context(user_id)
    system_prompt = _SYSTEM_TEMPLATE.replace("{context}", context)
    agent = create_react_agent(get_llm(), _TOOLS)
    lc_messages = [SystemMessage(content=system_prompt)] + _to_lc_messages(messages)
    result = agent.invoke(
        {"messages": lc_messages}, config={"recursion_limit": _RECURSION_LIMIT}
    )
    return result["messages"][-1].content
