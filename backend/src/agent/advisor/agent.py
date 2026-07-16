"""The Advisor — the single conversational surface (POST /api/chat/{session_id}).

One ReAct agent that both delivers the customer's **opening briefing** (turn 0 — what used
to be the separately-generated memo) and answers every follow-up, grounded in the analysis
**session snapshot** (numbers + category recommendations + modal-shift + forecast, all
already computed by /api/analyze — no re-query, no recompute). It reads the live catalogue
and the tariff knowledge base, surfaces the demand outlook / modal-shift suggestions, and
runs the safe simulate → confirm → apply loop for plan changes.

Only the LLM turns need a key; ``opening_briefing`` degrades to the deterministic template
memo when none is configured, so the dashboard always gets an opening message.
"""

import json
import logging
from pathlib import Path

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from agent.llm import get_llm, llm_available
from agent.observability import get_prompt, trace
from agent.session import append_message, get_session
from agent.tools.apply import apply_change
from agent.tools.catalog import lookup_subscriptions
from agent.tools.insights import get_demand_outlook, get_modal_shift
from agent.tools.knowledge import list_tariff_docs, read_tariff_doc
from agent.tools.simulate import simulate_change

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "advisor_system.md"
# Local copy, used as the offline fallback for the Langfuse-managed "advisor-chat"
# prompt. The {{context}} placeholder is filled per turn from the session snapshot.
_SYSTEM_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_RECURSION_LIMIT = 12
_TOOLS = [
    lookup_subscriptions,
    list_tariff_docs,
    read_tariff_doc,
    get_demand_outlook,
    get_modal_shift,
    simulate_change,
    apply_change,
]

_agent = None


def _get_agent():
    """Built once per process (tools + llm are static) and reused across turns."""
    global _agent
    if _agent is None:
        _agent = create_react_agent(get_llm(), _TOOLS)
    return _agent


def _ground_from_session(snapshot: dict) -> str:
    """The CURRENT ANALYSIS block: the already-computed figures the advisor narrates,
    taken straight from the session snapshot — no DB re-query, no recompute."""
    user = snapshot.get("user") or {}
    analyst_out = snapshot.get("analyst_out") or {}
    grounding = {
        "customer": {
            "name": user.get("name"),
            "home_city": user.get("home_city"),
            "preferences_0_100": snapshot.get("user_preferences"),
        },
        "active_subscriptions": [
            s.get("provider_plan_name")
            for s in (snapshot.get("subscriptions") or [])
            if s.get("subscription_status") == "active" and s.get("provider_plan_name")
        ],
        "category_subscription_analysis": analyst_out.get("category_subscription_analysis", []),
        "modal_shift_suggestions": analyst_out.get("modal_shift_suggestions", []),
        "forecast": snapshot.get("forecaster_out", {}),
        "total_actual_annual_cost_eur": snapshot.get("total_actual_annual_cost_eur"),
        "total_estimated_savings_eur": snapshot.get("total_estimated_savings_eur"),
        "actions_required": snapshot.get("actions_required", []),
    }
    return json.dumps(grounding, ensure_ascii=False, default=str)


def _system_prompt(snapshot: dict):
    """Return ``(prompt_obj, compiled_system_prompt)`` — the versioned Langfuse prompt
    (or the local fallback) filled with this session's grounding."""
    context = _ground_from_session(snapshot)
    prompt = get_prompt("advisor-chat", fallback=_SYSTEM_TEMPLATE, type="text")
    system_prompt = (
        prompt.compile(context=context)
        if prompt is not None
        else _SYSTEM_TEMPLATE.replace("{{context}}", context)
    )
    return prompt, system_prompt


def _run_config(user_id: str, session_id: str, prompt, tr):
    config = {"recursion_limit": _RECURSION_LIMIT}
    config.update(tr.config(prompt=prompt))
    # Inject the authenticated user id + session id for the tools (simulate/apply/insights),
    # not exposed to the LLM, so they always act on the real caller and session.
    config["configurable"] = {
        **config.get("configurable", {}),
        "user_id": user_id,
        "session_id": session_id,
    }
    return config


def _to_lc_messages(messages: list):
    out = []
    for m in messages:
        content = m.get("content", "")
        out.append(AIMessage(content=content) if m.get("role") == "assistant" else HumanMessage(content=content))
    return out


def _template_briefing(snapshot: dict, lang: str) -> str:
    """Deterministic opening briefing (the template memo) — the guaranteed fallback when
    no LLM is configured or the agent errors."""
    from agent.engines import template_memos

    name = (snapshot.get("user") or {}).get("name") or ""
    tm = template_memos(name, snapshot.get("analyst_out") or {}, snapshot.get("forecaster_out") or {})
    return tm.get("memo_german" if lang == "de" else "memo_english") or ""


def opening_briefing(session_id: str, lang: str = "de") -> tuple[str, str | None]:
    """Turn 0: the customer's personalised opening briefing, grounded in the session
    snapshot. Returns ``(text, trace_id)``. Falls back to the deterministic template memo
    when no LLM key is configured or the agent errors, so a briefing always comes back."""
    session = get_session(session_id)
    if session is None:
        return "", None
    snapshot = session["snapshot"]
    if not llm_available():
        return _template_briefing(snapshot, lang), None

    user_id = (snapshot.get("user") or {}).get("user_id")
    name = (snapshot.get("user") or {}).get("name") or "the customer"
    lang_name = "German" if lang == "de" else "English"
    try:
        prompt, system_prompt = _system_prompt(snapshot)
        seed = HumanMessage(content=f"Give {name} their opening briefing now, in {lang_name}.")
        with trace(
            "advisor-briefing", user_id=user_id, session_id=session_id,
            tags=["advisor", "briefing"],
        ) as tr:
            config = _run_config(user_id, session_id, prompt, tr)
            result = _get_agent().invoke(
                {"messages": [SystemMessage(content=system_prompt), seed]}, config=config,
            )
            trace_id = tr.trace_id
        reply = result["messages"][-1].content
        append_message(session_id, "assistant", reply, trace_id)
        return reply, trace_id
    except Exception:
        logger.exception("Advisor briefing failed; using template memo")
        return _template_briefing(snapshot, lang), None


def _persist_turn(session_id: str, messages: list, reply: str, trace_id: str | None) -> None:
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if last_user:
        append_message(session_id, "user", last_user.get("content", ""))
    append_message(session_id, "assistant", reply, trace_id)


def run_turn(session_id: str, messages: list) -> tuple[str, str | None]:
    """Answer one follow-up turn, grounded in the session snapshot. Returns
    ``(reply, trace_id)``. Requires an LLM (callers guard with ``llm_available()``)."""
    session = get_session(session_id)
    if session is None:
        return "", None
    snapshot = session["snapshot"]
    user_id = (snapshot.get("user") or {}).get("user_id")
    prompt, system_prompt = _system_prompt(snapshot)
    lc_messages = [SystemMessage(content=system_prompt)] + _to_lc_messages(messages)
    with trace(
        "advisor-chat", user_id=user_id, session_id=session_id, tags=["advisor", "chat"],
    ) as tr:
        config = _run_config(user_id, session_id, prompt, tr)
        result = _get_agent().invoke({"messages": lc_messages}, config=config)
        trace_id = tr.trace_id
    reply = result["messages"][-1].content
    _persist_turn(session_id, messages, reply, trace_id)
    return reply, trace_id


def stream_turn(session_id: str, messages: list):
    """Answer one follow-up turn as a stream of Server-Sent-Event dicts:
    ``{"type": "token", "text": ...}`` per token, then ``{"type": "done", "trace_id": ...}``.
    The assistant reply is persisted once the stream completes."""
    session = get_session(session_id)
    if session is None:
        yield {"type": "error", "detail": f"Session {session_id} not found."}
        return
    snapshot = session["snapshot"]
    user_id = (snapshot.get("user") or {}).get("user_id")
    prompt, system_prompt = _system_prompt(snapshot)
    lc_messages = [SystemMessage(content=system_prompt)] + _to_lc_messages(messages)
    with trace(
        "advisor-chat", user_id=user_id, session_id=session_id,
        tags=["advisor", "chat", "stream"],
    ) as tr:
        config = _run_config(user_id, session_id, prompt, tr)
        parts: list[str] = []
        for chunk, _meta in _get_agent().stream(
            {"messages": lc_messages}, config=config, stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                parts.append(chunk.content)
                yield {"type": "token", "text": chunk.content}
        trace_id = tr.trace_id
    _persist_turn(session_id, messages, "".join(parts), trace_id)
    yield {"type": "done", "trace_id": trace_id}
