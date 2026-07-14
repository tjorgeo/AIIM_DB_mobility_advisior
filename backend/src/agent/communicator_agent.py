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

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AIMessageChunk
from langgraph.prebuilt import create_react_agent

from database import get_connection
from agent.context import load_context
from agent.llm import get_llm
from agent.observability import get_prompt, trace
from agent.tools.catalog import lookup_subscriptions
from agent.tools.knowledge import list_tariff_docs, read_tariff_doc
from agent.tools.optimize import reoptimize

_PROMPT_PATH = Path(__file__).with_name("prompts") / "communicator_system.md"
# Local copy, used as the offline fallback for the Langfuse-managed
# "communicator-chat" prompt. The {{context}} placeholder is filled per request.
_SYSTEM_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_RECURSION_LIMIT = 12
_TOOLS = [lookup_subscriptions, list_tariff_docs, read_tariff_doc, reoptimize]


def _load_user_context(user_id: str) -> str:
    # Reuse the single canonical context loader (user + preferences + subscriptions)
    # rather than re-querying those tables here — one source of truth, no drift. The
    # only thing load_context doesn't carry is the latest recommendation, so that stays
    # a single extra query below.
    ctx = load_context(user_id)
    if ctx.get("error"):
        return "No profile found for this user."

    user = ctx["user"]
    preferences = ctx["user_preferences"]
    services = [
        s.get("provider_plan_name")
        for s in ctx["subscriptions"]
        if s.get("subscription_status") == "active" and s.get("provider_plan_name")
    ]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT optimizer_scenarios FROM recommendations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    rec_row = cursor.fetchone()
    conn.close()

    lines = [
        f"Customer: {user['name']} (id {user['user_id']}, home city {user.get('home_city')})",
        f"Preferences (0-100): {preferences}",
        f"Active subscriptions: {', '.join(services) or 'none'}",
    ]
    if rec_row and rec_row["optimizer_scenarios"]:
        # Despite the column name (kept to avoid a schema migration), this stores the
        # per-category current-vs-alternative-vs-no-subscription analysis, not
        # portfolio scenarios — see agent/engines/analysis.py's category_subscription_analysis.
        data = json.loads(rec_row["optimizer_scenarios"])
        savings = data.get("total_estimated_savings_eur")
        if savings:
            lines.append(f"Latest recommendation: potential additional savings of €{savings}/yr across categories.")
        for action in data.get("actions_required") or []:
            lines.append(
                f"- {action['category']}: {action['action']} "
                f"(from {action.get('from') or 'no subscription'} to {action.get('to') or 'pay-as-you-go'}), "
                f"estimated €{action['estimated_annual_savings_eur']}/yr"
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


_agent = None


def _get_agent():
    """The ReAct agent is stateless across turns (tools + llm are static), so build it
    once per process and reuse it, rather than reconstructing it on every request."""
    global _agent
    if _agent is None:
        _agent = create_react_agent(get_llm(), _TOOLS)
    return _agent


def _build_run_config(user_id: str, prompt, tr, messages: list):
    config = {"recursion_limit": _RECURSION_LIMIT}
    config.update(tr.config(prompt=prompt))
    # Inject the authenticated user id for tools (e.g. reoptimize) via the run config —
    # not exposed to the LLM, so it always acts on the real caller.
    #
    # confirmed_turn: whether the user has sent more than one message in this
    # conversation — i.e. there was at least one earlier turn where a proposal could
    # have been shown before this one. The reoptimize tool uses this as a code-level
    # gate on apply=True, since a model call can otherwise ignore the system prompt's
    # "only apply after explicit confirmation" instruction and commit a change straight
    # off an ambiguous first message like "optimize my portfolio".
    user_turns = sum(1 for m in messages if m.get("role") == "user")
    config["configurable"] = {
        **config.get("configurable", {}),
        "user_id": user_id,
        "confirmed_turn": user_turns > 1,
    }
    return config


def _prepare(user_id: str, messages: list):
    """Shared setup for a chat turn: user context, versioned system prompt, LC messages."""
    context = _load_user_context(user_id)
    prompt = get_prompt("communicator-chat", fallback=_SYSTEM_TEMPLATE, type="text")
    system_prompt = (
        prompt.compile(context=context)
        if prompt is not None
        else _SYSTEM_TEMPLATE.replace("{{context}}", context)
    )
    lc_messages = [SystemMessage(content=system_prompt)] + _to_lc_messages(messages)
    return prompt, lc_messages


def run_chat(user_id: str, messages: list) -> tuple[str, str | None]:
    """Answer one chat turn. Returns ``(reply, trace_id)`` — ``trace_id`` is the
    Langfuse trace of this turn (or ``None`` when tracing is disabled) so the
    frontend can attach a thumbs up/down feedback score to it."""
    prompt, lc_messages = _prepare(user_id, messages)
    # Trace the whole ReAct turn (LLM steps + tool calls) as one "chat-response"
    # trace. user_id doubles as the session id so a user's chat turns group into
    # one Sessions-view conversation (there is no separate conversation id yet).
    with trace(
        "chat-response",
        user_id=user_id,
        session_id=user_id,
        tags=["communicator", "chat"],
    ) as tr:
        config = _build_run_config(user_id, prompt, tr, messages)
        result = _get_agent().invoke({"messages": lc_messages}, config=config)
        trace_id = tr.trace_id
    return result["messages"][-1].content, trace_id


def stream_chat(user_id: str, messages: list):
    """Answer one chat turn as a stream of events for Server-Sent Events.

    Yields ``{"type": "token", "text": ...}`` for each assistant token as it is
    generated, then a final ``{"type": "done", "trace_id": ...}``. Same grounded
    ReAct agent as :func:`run_chat`; only the delivery differs. Any exception is
    surfaced as an ``{"type": "error"}`` event so the endpoint can close cleanly and
    the frontend can fall back.
    """
    prompt, lc_messages = _prepare(user_id, messages)
    with trace(
        "chat-response",
        user_id=user_id,
        session_id=user_id,
        tags=["communicator", "chat", "stream"],
    ) as tr:
        config = _build_run_config(user_id, prompt, tr, messages)
        # stream_mode="messages" emits (message_chunk, metadata) tuples; we forward the
        # text of assistant token chunks and skip tool-call / tool-result chunks.
        for chunk, _meta in _get_agent().stream(
            {"messages": lc_messages}, config=config, stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                yield {"type": "token", "text": chunk.content}
        yield {"type": "done", "trace_id": tr.trace_id}
