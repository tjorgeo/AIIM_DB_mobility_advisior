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
import os
import queue
import threading
from pathlib import Path

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from psycopg_pool import ConnectionPool

from database import DATABASE_URL
from agent.llm import get_llm, llm_available
from agent.observability import get_prompt, trace
from agent.session import append_message, get_messages, get_session
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
_saver = None


def _get_saver() -> PostgresSaver:
    """Lazily build the shared ``PostgresSaver`` checkpointer and create its tables.

    Persists the ReAct message history *and* the intermediate tool/observation steps
    across turns, keyed by ``thread_id`` (the chat ``session_id``), in the same Postgres
    the app already uses. Runs on psycopg3 (autocommit + no prepared statements, as the
    checkpointer requires) via its own small pool — independent of the psycopg2 pool in
    ``database.py``. ``setup()`` is idempotent, so calling it on every process is safe.
    """
    global _saver
    if _saver is None:
        pool = ConnectionPool(
            conninfo=DATABASE_URL,
            max_size=int(os.getenv("CHECKPOINT_POOL_MAX", "5")),
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=True,
        )
        saver = PostgresSaver(pool)
        saver.setup()
        _saver = saver
    return _saver


def _agent_prompt(state: dict, config: RunnableConfig) -> list:
    """Inject the per-session, snapshot-grounded system prompt fresh each run — read from
    the run config, not persisted into the checkpointed history — then the running
    messages. Refreshing it per turn means the grounding reflects the *latest* snapshot
    (e.g. after ``apply_change`` revised the plan)."""
    configurable = (config or {}).get("configurable") or {}
    system_prompt = configurable.get("system_prompt") or _SYSTEM_TEMPLATE
    return [SystemMessage(content=system_prompt), *state["messages"]]


def _get_agent():
    """Built once per process (tools + llm are static) and reused across turns. Carries a
    Postgres checkpointer so each ``session_id`` thread remembers its own conversation."""
    global _agent
    if _agent is None:
        _agent = create_react_agent(
            get_llm(), _TOOLS, prompt=_agent_prompt, checkpointer=_get_saver(),
        )
    return _agent


def setup_agent() -> None:
    """Eagerly create the checkpointer tables (and build the agent when an LLM key is set)
    so failures surface at startup rather than on the first chat turn. Safe to call
    without an LLM key — the checkpointer needs only Postgres, which startup already
    verified — so table creation still happens and the briefing template fallback works."""
    _get_saver()
    if llm_available():
        _get_agent()


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


def _run_config(user_id: str, session_id: str, prompt, tr, system_prompt: str):
    config = {"recursion_limit": _RECURSION_LIMIT}
    config.update(tr.config(prompt=prompt))
    # ``thread_id`` keys the checkpointer to this chat session (its durable memory).
    # ``user_id`` / ``session_id`` are injected for the tools (simulate/apply/insights),
    # not exposed to the LLM, so they always act on the real caller and session.
    # ``system_prompt`` is read by ``_agent_prompt`` to prepend the grounded system turn.
    config["configurable"] = {
        **config.get("configurable", {}),
        "thread_id": session_id,
        "user_id": user_id,
        "session_id": session_id,
        "system_prompt": system_prompt,
    }
    return config


def _to_lc_messages(messages: list):
    out = []
    for m in messages:
        content = m.get("content", "")
        out.append(AIMessage(content=content) if m.get("role") == "assistant" else HumanMessage(content=content))
    return out


def _latest_user_text(messages: list) -> str:
    """The newest user message from the client request — the only new input a turn adds;
    the checkpointer supplies everything before it."""
    last = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    return last.get("content", "") if last else ""


def _turn_input(session_id: str, config: dict, latest_user: str) -> dict:
    """The messages to feed the graph this turn. Normally just the new user message — the
    checkpointer holds prior turns (including intermediate tool/observation steps). If the
    thread has no state yet (a brand-new session, or one created before the checkpointer
    existed), prime it from the server-authoritative ``chat_messages`` transcript so
    earlier context isn't lost and the client-sent history is never trusted for it."""
    new_msg = HumanMessage(content=latest_user)
    try:
        state = _get_agent().get_state(config)
        if state.values.get("messages"):
            return {"messages": [new_msg]}
    except Exception:
        logger.exception("Checkpointer get_state failed; priming thread from transcript")
    return {"messages": _to_lc_messages(get_messages(session_id)) + [new_msg]}


def _template_briefing(snapshot: dict, lang: str) -> str:
    """Deterministic opening briefing (the template memo) — the guaranteed fallback when
    no LLM is configured or the agent errors."""
    from agent.engines import template_memos

    name = (snapshot.get("user") or {}).get("name") or ""
    tm = template_memos(name, snapshot.get("analyst_out") or {}, snapshot.get("forecaster_out") or {})
    return tm.get("memo_german" if lang == "de" else "memo_english") or ""


def opening_briefing(session_id: str, lang: str = "de") -> tuple[str, str | None]:
    """Turn 0: the customer's personalised opening briefing, grounded in the session
    snapshot. Returns ``(text, trace_id)``.

    Idempotent: the briefing is generated once per session and cached in the chat
    transcript, so a dashboard re-mount reuses it instead of paying for another LLM call.
    Falls back to the deterministic template memo when no LLM key is configured or the
    agent errors, so a briefing always comes back."""
    session = get_session(session_id)
    if session is None:
        return "", None
    existing = next((m for m in get_messages(session_id) if m["role"] == "assistant"), None)
    if existing:
        return existing["content"], existing.get("trace_id")

    reply, trace_id = _generate_briefing(session["snapshot"], session_id, lang)
    append_message(session_id, "assistant", reply, trace_id)
    return reply, trace_id


def _generate_briefing(snapshot: dict, session_id: str, lang: str) -> tuple[str, str | None]:
    """Produce the opening briefing via the agent (LLM), or the deterministic template
    when no key is configured or the agent errors."""
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
            # Turn 0 seeds the checkpointer thread; the system prompt is injected by
            # _agent_prompt from the config, so it is not persisted into the history.
            config = _run_config(user_id, session_id, prompt, tr, system_prompt)
            result = _get_agent().invoke({"messages": [seed]}, config=config)
            trace_id = tr.trace_id
        return result["messages"][-1].content, trace_id
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
    latest_user = _latest_user_text(messages)
    with trace(
        "advisor-chat", user_id=user_id, session_id=session_id, tags=["advisor", "chat"],
    ) as tr:
        config = _run_config(user_id, session_id, prompt, tr, system_prompt)
        result = _get_agent().invoke(_turn_input(session_id, config, latest_user), config=config)
        trace_id = tr.trace_id
    reply = result["messages"][-1].content
    _persist_turn(session_id, messages, reply, trace_id)
    return reply, trace_id


def stream_turn(session_id: str, messages: list):
    """Answer one follow-up turn as a stream of Server-Sent-Event dicts:
    ``{"type": "token", "text": ...}`` per token, then ``{"type": "done", "trace_id": ...}``.
    The assistant reply is persisted once the stream completes.

    The Langfuse/OTel span is contextvar-based, so it must not straddle the outward
    ``yield``s: FastAPI drives this SSE generator across a threadpool, entering and
    exiting the span in *different* contexts, which makes OTel raise on detach. We keep
    the whole span on one worker thread that owns it end-to-end and hand tokens to the
    caller through a queue, so the outer (yielding) generator never touches OTel context.
    """
    session = get_session(session_id)
    if session is None:
        yield {"type": "error", "detail": f"Session {session_id} not found."}
        return
    snapshot = session["snapshot"]
    user_id = (snapshot.get("user") or {}).get("user_id")
    prompt, system_prompt = _system_prompt(snapshot)
    latest_user = _latest_user_text(messages)

    tokens: "queue.Queue[str | None]" = queue.Queue()
    result: dict = {}

    def _produce():
        parts: list[str] = []
        try:
            with trace(
                "advisor-chat", user_id=user_id, session_id=session_id,
                tags=["advisor", "chat", "stream"],
            ) as tr:
                config = _run_config(user_id, session_id, prompt, tr, system_prompt)
                for chunk, _meta in _get_agent().stream(
                    _turn_input(session_id, config, latest_user), config=config,
                    stream_mode="messages",
                ):
                    if isinstance(chunk, AIMessageChunk) and chunk.content:
                        parts.append(chunk.content)
                        tokens.put(chunk.content)
                result["trace_id"] = tr.trace_id
        except Exception as e:
            logger.exception("Advisor streaming turn failed")
            result["error"] = str(e)
        finally:
            result["reply"] = "".join(parts)
            tokens.put(None)  # sentinel: producer done

    worker = threading.Thread(target=_produce, name="advisor-stream", daemon=True)
    worker.start()

    while (text := tokens.get()) is not None:
        yield {"type": "token", "text": text}
    worker.join()

    reply = result.get("reply", "")
    trace_id = result.get("trace_id")
    if "error" in result:
        yield {"type": "error", "detail": result["error"]}
        return
    _persist_turn(session_id, messages, reply, trace_id)
    yield {"type": "done", "trace_id": trace_id}
