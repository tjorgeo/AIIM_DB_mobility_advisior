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
from graph.llm import get_llm
from graph.tools import lookup_subscriptions


def _load_user_context(user_id: str) -> str:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name, db_customer_id, preferences FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return "No profile found for this user."

    cursor.execute(
        "SELECT service, monthly_cost_eur FROM subscriptions WHERE user_id = ? AND status = 'active'",
        (user_id,),
    )
    subs = [dict(s) for s in cursor.fetchall()]

    cursor.execute(
        "SELECT scenarios FROM recommendations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    rec_row = cursor.fetchone()
    conn.close()

    lines = [
        f"Customer: {user['name']} (DB id {user['db_customer_id']})",
        f"Preferences: {user['preferences']}",
        f"Active subscriptions: {', '.join(s['service'] for s in subs) or 'none'}",
    ]
    if rec_row:
        data = json.loads(rec_row["scenarios"])
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
