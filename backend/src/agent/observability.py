"""Optional Langfuse observability for the LangChain/LangGraph agent calls.

A single place that knows whether Langfuse is configured and provides the three
things the agents need:

* :func:`trace` — a context manager that opens one Langfuse trace (a root span)
  around a block of LangChain calls, sets trace attributes (user/session/tags),
  and exposes the ``trace_id`` so callers can later attach feedback scores to it.
* :func:`get_prompt` — fetch a Langfuse-managed, versioned prompt, with the local
  prompt text as an offline fallback.
* :func:`create_score` — attach a feedback score (thumbs, acceptance) to a trace.

Mirrors the ``agent.llm`` philosophy: when the ``LANGFUSE_*`` keys are absent
every function here is a no-op, so observability is purely additive and the app
runs exactly as before without a Langfuse account. The LangChain callback
integration is preferred over manual spans for the LLM steps themselves — it
captures the model name, token usage, tool calls and generation hierarchy
automatically; the enclosing span only exists to own the trace id and attributes.

Env (see .env.example):
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY  — required to enable observability
    LANGFUSE_BASE_URL / LANGFUSE_HOST         — server URL (defaults to EU cloud)
    LANGFUSE_TRACING_ENVIRONMENT              — e.g. development / production
    LANGFUSE_RELEASE                          — release/version tag for traces
"""

import contextvars
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Trace attributes (user/session/tags) of the innermost active :func:`trace` block.
#
# Attributes reach a trace through the LangChain config's ``langfuse_*`` metadata keys,
# not through an SDK trace-update call (the client has no ``update_current_trace`` and
# 4.x dropped ``span.update_trace`` — see :class:`_Trace`). A nested LLM step that
# builds its own config therefore has no way to know the enclosing trace's attributes
# unless they are published here; without this, an ``analyze-pipeline`` trace ends up
# with ``user_id=None`` and no tags, and cannot be attributed to a customer at all.
_trace_meta: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "langfuse_trace_meta", default=None
)

# The Python SDK reads LANGFUSE_HOST; the Langfuse CLI/docs also use
# LANGFUSE_BASE_URL. Accept either so a single .env works for both.
if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

# Optional release/version tag stamped on every trace, for filtering by build.
_RELEASE = os.getenv("LANGFUSE_RELEASE") or None


def langfuse_enabled() -> bool:
    """True when both Langfuse keys are configured, i.e. observability can run."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    )


_handler = None
_handler_failed = False


def get_callback_handler():
    """Lazily build a shared Langfuse ``CallbackHandler`` (or ``None`` if disabled)."""
    global _handler, _handler_failed
    if not langfuse_enabled() or _handler_failed:
        return None
    if _handler is None:
        try:
            from langfuse.langchain import CallbackHandler

            _handler = CallbackHandler()
        except Exception:
            # Never let observability wiring break an LLM call.
            logger.exception("Langfuse init failed; continuing without observability")
            _handler_failed = True
            return None
    return _handler


def llm_config(name: str) -> dict:
    """LangChain ``config`` for a standalone LLM step that is not already inside a
    :func:`trace` block.

    Returns ``{}`` when Langfuse is disabled, so spreading it into ``.invoke()``
    changes nothing — the same degradation contract as :meth:`_Trace.config`.

    Use this for the deterministic pipeline's small LLM steps (forecast reasoning,
    modal-shift feasibility). They are called both from ``pipeline.run_analysis``
    and directly from tests, so they cannot rely on an enclosing trace existing.
    When one does exist the callback nests the generation under it; when it does
    not, the step becomes its own root trace instead of going unrecorded — which
    is what previously left these two steps with no token usage at all.
    """
    handler = get_callback_handler()
    if handler is None:
        return {}
    config: dict = {"callbacks": [handler], "run_name": name}
    inherited = _trace_meta.get()
    if inherited:
        config["metadata"] = dict(inherited)
    return config


# --- Tracing -----------------------------------------------------------------


class _NoTrace:
    """No-op trace handle used when Langfuse is disabled."""

    trace_id = None

    def config(self, prompt=None) -> dict:
        return {}


class _Trace:
    """Live trace handle. ``trace_id`` is only valid while the enclosing span is
    active (i.e. inside the ``with trace(...)`` block).

    Trace attributes (user/session/tags) and the linked prompt are carried on the
    LangChain ``config`` metadata rather than set via SDK trace-update calls, so
    the same code works across Langfuse SDK 3.x and 4.x (4.x dropped
    ``span.update_trace``); the ``CallbackHandler`` reads these ``langfuse_*`` keys
    and applies them to the trace."""

    def __init__(self, client, handler, name, user_id, session_id, tags):
        self._client = client
        self._handler = handler
        self._name = name
        self._user_id = user_id
        self._session_id = session_id
        self._tags = tags

    @property
    def trace_id(self):
        return self._client.get_current_trace_id()

    def config(self, prompt=None) -> dict:
        """LangChain ``config`` for calls that should nest under this trace.

        Pass the Langfuse ``prompt`` object to link the managed prompt version to
        the generation it produced (shows in the trace's Generation → Prompt).
        """
        meta: dict = {}
        if self._user_id:
            meta["langfuse_user_id"] = self._user_id
        if self._session_id:
            meta["langfuse_session_id"] = self._session_id
        if self._tags:
            meta["langfuse_tags"] = self._tags
        if prompt is not None:
            meta["langfuse_prompt"] = prompt
        config: dict = {"callbacks": [self._handler], "run_name": self._name}
        if meta:
            config["metadata"] = meta
        return config


@contextmanager
def trace(
    name: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
):
    """Open one Langfuse trace around a block of LangChain calls.

    Yields a handle exposing ``.trace_id`` (read it *inside* the block) and
    ``.config(prompt=...)`` to spread into ``.invoke(config=...)`` so the LLM
    steps nest under this trace. No-op when Langfuse is disabled: yields a handle
    whose ``trace_id`` is ``None`` and whose ``config()`` is ``{}``.

    Only non-PII identifiers (the user's UUID) are set as trace attributes.
    ``metadata['memo_source']`` and the configured release are surfaced as tags
    (``memo_source:llm``, ``release:<sha>``) for dashboard filtering; the trace
    environment comes from ``LANGFUSE_TRACING_ENVIRONMENT`` automatically.
    """
    handler = get_callback_handler()
    if handler is None:
        yield _NoTrace()
        return

    from langfuse import get_client

    client = get_client()
    all_tags = list(tags or [])
    if _RELEASE:
        all_tags.append(f"release:{_RELEASE}")
    source = (metadata or {}).get("memo_source")
    if source:
        all_tags.append(f"memo_source:{source}")

    # Publish the attributes so LLM steps nested inside this block that build their own
    # config (via llm_config) carry them too — otherwise the trace has no user or tags.
    meta: dict = {}
    if user_id:
        meta["langfuse_user_id"] = user_id
    if session_id:
        meta["langfuse_session_id"] = session_id
    if all_tags:
        meta["langfuse_tags"] = all_tags
    token = _trace_meta.set(meta or None)

    # start_as_current_observation exists in both SDK 3.x and 4.x and makes the
    # trace id retrievable via get_current_trace_id() inside the block.
    try:
        with client.start_as_current_observation(as_type="span", name=name):
            yield _Trace(client, handler, name, user_id, session_id, all_tags)
    finally:
        _trace_meta.reset(token)


# --- Prompt management -------------------------------------------------------


def get_prompt(name: str, *, fallback: str, label: str = "production", type: str = "text"):
    """Fetch a Langfuse-managed, versioned prompt.

    Returns a prompt client (use ``.compile(**vars)`` for the text, and pass the
    object to :meth:`_Trace.config` to link it to the trace) or ``None`` when
    Langfuse is disabled — callers then use their local ``fallback`` text.

    ``fallback`` is also handed to the SDK so that if Langfuse is *enabled* but
    unreachable, the returned client still compiles the local text instead of
    raising, keeping the app fully functional offline.
    """
    if not langfuse_enabled():
        return None
    try:
        from langfuse import get_client

        return get_client().get_prompt(name, label=label, type=type, fallback=fallback)
    except Exception:
        logger.exception("Langfuse get_prompt(%s) failed; using local fallback", name)
        return None


# --- Scores / feedback -------------------------------------------------------


def create_score(
    *,
    trace_id: str | None,
    name: str,
    value,
    data_type: str = "BOOLEAN",
    comment: str | None = None,
) -> None:
    """Attach a feedback score to a trace. No-op when disabled or ``trace_id`` is
    missing. Always pass ``data_type`` explicitly (a bare ``1`` would infer as
    NUMERIC instead of BOOLEAN)."""
    if not langfuse_enabled() or not trace_id:
        return
    try:
        from langfuse import get_client

        get_client().create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            data_type=data_type,
            comment=comment,
        )
    except Exception:
        logger.exception("Langfuse create_score(%s) failed", name)


def flush() -> None:
    """Flush buffered events to Langfuse (call on shutdown). No-op when disabled."""
    if not langfuse_enabled():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.exception("Langfuse flush failed")
