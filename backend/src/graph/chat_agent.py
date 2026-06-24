"""Conversational mobility advisor for POST /api/chat (Phase 4).

A genuinely agentic ReAct loop: the LLM can call `lookup_subscriptions` to read
the live catalogue before answering. Grounded in the caller's persona and their
most recent recommendation so it can explain/defend the plan the dashboard shows.

Only invoked when an API key is configured (main.py guards with llm_available()),
so the frontend's scripted fallback covers the no-key case.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from database import get_connection
from schema_map import preferences_from_onboarding
from graph.llm import get_llm
from graph.tools import lookup_subscriptions


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

    cursor.execute(
        "SELECT * FROM user_onboardings WHERE user_id = ?", (user_id,)
    )
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


def _system_prompt(context: str) -> str:
    return (
        "You are the DB MoveOptimizer assistant — a friendly, concise mobility advisor "
        "for Deutsche Bahn customers. Help the user understand and act on their personalised "
        "subscription recommendation. Use the lookup_subscriptions tool when you need exact "
        "product pricing or coverage. Answer in the user's language (German or English). "
        "Keep replies short and practical.\n\n"
        f"=== CURRENT USER CONTEXT ===\n{context}"
    )


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
    agent = create_react_agent(get_llm(), [lookup_subscriptions])
    lc_messages = [SystemMessage(content=_system_prompt(context))] + _to_lc_messages(messages)
    result = agent.invoke({"messages": lc_messages})
    return result["messages"][-1].content
