"""University GPT (OpenAI-compatible) LLM access.

A single place that knows how to reach the model and whether it is configured.
When ``UNI_GPT_API_KEY`` is absent every LLM-backed feature degrades gracefully
(memos fall back to deterministic templates; chat/onboarding return 503), so the
app stays fully usable without a key.

It is also the single place that limits how many calls are in flight at once — see
``_llm_slots`` below. Every model call in the app is built here, so the cap cannot be
bypassed by adding a caller.
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

UNI_GPT_BASE_URL = os.getenv("UNI_GPT_BASE_URL", "https://chat.kiconnect.nrw/api/v1")
# Exact model id as listed by GET /api/v1/models on the kiconnect endpoint.
# Override via UNI_GPT_MODEL if the catalogue changes.
UNI_GPT_MODEL = os.getenv("UNI_GPT_MODEL", "OpenAI GPT OSS 120b KI:Inferenz.nrw")
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")

# --------------------------------------------------------------------------- #
# Concurrency cap                                                              #
# --------------------------------------------------------------------------- #
#
# The university endpoint is shared and rejects bursts with
# `429 too_many_concurrent_requests`. It used to be throttled by accident: /api/analyze
# blocked for ~30s and ran its two LLM steps one after the other, so a user could not
# have more than one call in flight. Once the analyze path started answering
# immediately and finishing the LLM half on background workers, that backpressure
# disappeared and a few quick persona switches would fire a dozen calls at once.
#
# So the limit is now explicit. Every call blocks here until a slot is free rather than
# being rejected — a queued call is slower, a 429'd one loses its LLM output entirely
# and silently falls back to the deterministic path.
#
# The default of 2 is what one analysis needs to keep its forecast and feasibility
# steps running in parallel (see pipeline.run_enrichment). Raise LLM_MAX_CONCURRENCY if
# the endpoint tolerates more; lower it to 1 to serialize everything.
_MAX_CONCURRENCY = max(1, int(os.getenv("LLM_MAX_CONCURRENCY", "2")))
_llm_slots = threading.BoundedSemaphore(_MAX_CONCURRENCY)

# Only worth a log line when the wait is long enough for someone to notice it.
_SLOW_WAIT_SECONDS = 5.0

# Retries are the second line of defence: the cap bounds *our* concurrency, but the
# endpoint is university-wide, so someone else's burst can still 429 us. The OpenAI
# client retries 429s and honours Retry-After. Note it does so *inside* the call, while
# this process still holds its slot — which is what we want, since releasing it during a
# backoff would just let another call in to be rejected as well.
#
# Kept low because the same budget also covers timeouts: a genuinely stuck endpoint
# costs timeout x (retries + 1), and the chat path has a user waiting on it.
_DEFAULT_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "30"))
_DEFAULT_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


def llm_available() -> bool:
    """True when an API key is configured, i.e. LLM features can run."""
    return bool(UNI_GPT_API_KEY.strip())


def max_concurrency() -> int:
    """The configured in-flight cap. Exposed for tests and diagnostics."""
    return _MAX_CONCURRENCY


class _Slot:
    """Holds one of ``_llm_slots`` for the duration of a model call.

    A context manager rather than a bare ``with _llm_slots`` so the wait can be timed
    and reported: when calls start queueing, that is the explanation for latency that
    would otherwise look like a slow endpoint.
    """

    def __enter__(self):
        started = time.perf_counter()
        _llm_slots.acquire()
        waited = time.perf_counter() - started
        if waited >= _SLOW_WAIT_SECONDS:
            logger.info(
                "LLM call waited %.1fs for one of %d concurrency slots",
                waited, _MAX_CONCURRENCY,
            )
        return self

    def __exit__(self, *_exc):
        _llm_slots.release()
        return False


class ConcurrencyLimited:
    """Mixin that holds a concurrency slot for the length of each model call.

    Applied at the client rather than the call sites, which is what makes the cap
    airtight: asking every caller to take the semaphore would miss the advisor, whose
    calls are issued by LangGraph inside ``create_react_agent`` rather than by our own
    code.

    Both entry points are covered — ``_generate`` for ordinary invocations and
    ``_stream`` for the SSE chat endpoint. The generator holds its slot until it is
    exhausted or closed, so a client that disconnects mid-stream releases it too.

    Kept separate from the ``ChatOpenAI`` subclass below so the queueing behaviour can
    be tested against a plain stub, with no pydantic model and no network client to
    stand up.
    """

    def _generate(self, *args, **kwargs):
        with _Slot():
            return super()._generate(*args, **kwargs)

    def _stream(self, *args, **kwargs):
        with _Slot():
            yield from super()._stream(*args, **kwargs)


_throttled_cls = None


def _throttled_chat_openai():
    """The concurrency-capped ``ChatOpenAI`` subclass, built lazily and cached.

    Lazy because this module deliberately imports langchain only when a model is
    actually needed — the app runs, and the tests import, without it.
    """
    global _throttled_cls
    if _throttled_cls is None:
        from langchain_openai import ChatOpenAI

        class _ThrottledChatOpenAI(ConcurrencyLimited, ChatOpenAI):
            pass

        _throttled_cls = _ThrottledChatOpenAI
    return _throttled_cls


_llm = None


def get_llm(
    temperature: float = 0.0,
    timeout: int | None = None,
    max_retries: int | None = None,
    max_tokens: int | None = None,
):
    """Lazily build a shared ChatOpenAI client pointed at University GPT.

    Every client returned here is concurrency-capped (see ``_llm_slots``): calls queue
    rather than overwhelming the shared endpoint.

    ``timeout``/``max_retries`` are set explicitly: without them a stalled or
    rate-limited call to the shared university endpoint hangs indefinitely — the chat
    request (and the frontend's "typing…" indicator) never resolves into either a
    reply or an error. Capping it means a stuck call surfaces as an error within
    ~30s, which /api/chat and /api/chat/stream already turn into a 500 / SSE error
    event that the frontend falls back on.

    The 30s default is an *interactive* budget. Callers with a much larger prompt and
    no user waiting on them — the baseline pipeline, which sends a persona's whole leg
    history in one call — pass their own ``timeout``/``max_retries``; doing so builds a
    dedicated client rather than reconfiguring the shared one out from under the app.

    ``max_tokens`` caps the *reply*, for steps whose output schema is bounded and whose
    generation time is the thing the user waits on (the forecast reasoner — see
    ``llm_steps/forecast_reasoner``). Like the other two, passing it builds a dedicated
    client so the shared one keeps its uncapped default for open-ended chat.

    A dedicated client is still throttled by the same process-wide semaphore — the cap
    is on calls in flight, not on how many client objects exist.
    """
    global _llm
    cls = _throttled_chat_openai()

    if timeout is not None or max_retries is not None or max_tokens is not None:
        return cls(
            model=UNI_GPT_MODEL,
            openai_api_key=UNI_GPT_API_KEY,
            openai_api_base=UNI_GPT_BASE_URL,
            temperature=temperature,
            timeout=_DEFAULT_TIMEOUT_S if timeout is None else timeout,
            max_retries=_DEFAULT_MAX_RETRIES if max_retries is None else max_retries,
            max_tokens=max_tokens,
        )

    if _llm is None:
        _llm = cls(
            model=UNI_GPT_MODEL,
            openai_api_key=UNI_GPT_API_KEY,
            openai_api_base=UNI_GPT_BASE_URL,
            temperature=temperature,
            timeout=_DEFAULT_TIMEOUT_S,
            max_retries=_DEFAULT_MAX_RETRIES,
        )
    return _llm
