"""The process-wide cap on in-flight model calls (``agent.llm``).

Context: the shared university endpoint rejects bursts with
``429 too_many_concurrent_requests``. That used to be prevented by accident — the
analyze path blocked for ~30s and ran its two LLM steps sequentially, so one user could
not have more than one call in flight. Once it started answering immediately and
enriching on background workers, a few quick persona switches fired a dozen concurrent
calls and every one of them lost its LLM output to the deterministic fallback. These
tests pin the explicit cap that replaced the accident.

The queueing is exercised through ``ConcurrencyLimited`` over a plain stub — the same
mixin the real client is built from, with no pydantic model or network client needed.
Separate tests below check that the real client is in fact built from it.
"""

import threading
import time

import pytest

from agent import llm as llm_mod
from agent.llm import ConcurrencyLimited


@pytest.fixture(autouse=True)
def cap_of_two(monkeypatch):
    """Reset the module's semaphore to a known size for every test here."""
    monkeypatch.setattr(llm_mod, "_MAX_CONCURRENCY", 2)
    monkeypatch.setattr(llm_mod, "_llm_slots", threading.BoundedSemaphore(2))


class _Tracker:
    """Records the high-water mark of simultaneous calls."""

    def __init__(self):
        self.lock = threading.Lock()
        self.live = 0
        self.peak = 0

    def enter(self):
        with self.lock:
            self.live += 1
            self.peak = max(self.peak, self.live)

    def exit(self):
        with self.lock:
            self.live -= 1


class _Endpoint:
    """Stands in for ChatOpenAI: records overlap, optionally fails."""

    def __init__(self, tracker, hold=0.15, error=None):
        self.tracker = tracker
        self.hold = hold
        self.error = error

    def _generate(self, *_a, **_k):
        self.tracker.enter()
        try:
            if self.error:
                raise self.error
            time.sleep(self.hold)
            return "result"
        finally:
            self.tracker.exit()

    def _stream(self, *_a, **_k):
        self.tracker.enter()
        try:
            time.sleep(self.hold)
            yield "chunk"
        finally:
            self.tracker.exit()


class _Client(ConcurrencyLimited, _Endpoint):
    """The mixin over the stub — the same composition as the real client."""


# Real waits here are fractions of a second, so anything still running after this has
# genuinely wedged. Kept short on purpose: a leaked slot blocks every later acquire, and
# a generous timeout turns that into a suite that stalls for minutes instead of failing.
_WEDGED_AFTER_S = 5


def _run_concurrently(fn, n, timeout=_WEDGED_AFTER_S):
    threads = [threading.Thread(target=fn, daemon=True) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout)
    assert not any(t.is_alive() for t in threads), "a call never released its slot"


# --------------------------------------------------------------------------- #
# The cap holds                                                                #
# --------------------------------------------------------------------------- #

def test_never_more_than_the_cap_in_flight():
    """Eight callers, a cap of two — the endpoint must never see more than two."""
    tracker = _Tracker()
    client = _Client(tracker)

    _run_concurrently(lambda: client._generate(), 8)

    assert tracker.peak <= 2
    assert tracker.live == 0


def test_the_cap_is_actually_used():
    """The necessary complement: a cap of two must still let two run at once. Without
    this, 'never exceeded' would also pass on a fully serialized implementation — and
    pipeline.run_enrichment's parallel forecast/feasibility pair would be lost."""
    tracker = _Tracker()
    client = _Client(tracker)

    _run_concurrently(lambda: client._generate(), 4)

    assert tracker.peak == 2


def test_calls_queue_rather_than_being_dropped():
    """Every caller must eventually get through. Queueing is the whole point — a
    rejected call falls back to deterministic output and loses its LLM result."""
    tracker = _Tracker()
    done = []
    lock = threading.Lock()
    client = _Client(tracker, hold=0.05)

    def call():
        client._generate()
        with lock:
            done.append(1)

    _run_concurrently(call, 10)
    assert len(done) == 10


# --------------------------------------------------------------------------- #
# Slots come back                                                              #
# --------------------------------------------------------------------------- #

def test_streaming_holds_and_releases_its_slot():
    """The SSE chat path goes through _stream, not _generate. A generator that never
    released would wedge the whole app after two chats."""
    tracker = _Tracker()
    client = _Client(tracker)

    _run_concurrently(lambda: list(client._stream()), 6)

    assert tracker.peak <= 2
    assert tracker.live == 0


def test_an_abandoned_stream_still_releases():
    """A client that disconnects mid-stream leaves the generator unexhausted. Closing it
    must give the slot back, or every dropped SSE connection would leak one."""
    tracker = _Tracker()
    client = _Client(tracker)

    gen = client._stream()
    next(gen)      # take a slot
    gen.close()    # disconnect without exhausting

    # Both slots must be free again — this blocks until the timeout if one leaked.
    assert llm_mod._llm_slots.acquire(timeout=2)
    assert llm_mod._llm_slots.acquire(timeout=2)
    llm_mod._llm_slots.release()
    llm_mod._llm_slots.release()


def test_an_exception_releases_the_slot():
    """A 429 that exhausts its retries propagates. The slot must not go with it —
    otherwise a run of failures would permanently shrink the pool to zero."""
    tracker = _Tracker()
    client = _Client(tracker, error=RuntimeError("429 too_many_concurrent_requests"))

    for _ in range(5):
        with pytest.raises(RuntimeError):
            client._generate()

    assert llm_mod._llm_slots.acquire(timeout=2)
    llm_mod._llm_slots.release()


def test_separate_client_objects_share_one_cap():
    """get_llm(max_tokens=…) builds a *separate* client (the forecast reasoner does
    this). The cap counts calls in flight, not client objects, so a caller must not be
    able to escape it by asking for its own."""
    tracker = _Tracker()
    clients = [_Client(tracker) for _ in range(6)]

    threads = [threading.Thread(target=c._generate, daemon=True) for c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_WEDGED_AFTER_S)

    assert tracker.peak <= 2


# --------------------------------------------------------------------------- #
# The real client is wired to it                                               #
# --------------------------------------------------------------------------- #

@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(llm_mod, "UNI_GPT_API_KEY", "test-key")
    monkeypatch.setattr(llm_mod, "_llm", None)


def test_both_get_llm_shapes_return_a_capped_client(with_key):
    """Neither shape may hand back a bare ChatOpenAI — that would be a hole in the cap
    for whichever caller got it."""
    shared = llm_mod.get_llm()
    dedicated = llm_mod.get_llm(max_tokens=2000)

    assert isinstance(shared, ConcurrencyLimited)
    assert isinstance(dedicated, ConcurrencyLimited)
    assert shared is not dedicated  # dedicated clients stay separate objects


def test_the_shared_client_is_reused(with_key):
    assert llm_mod.get_llm() is llm_mod.get_llm()


def test_the_mixin_precedes_chatopenai_in_the_mro(with_key):
    """Order matters: ConcurrencyLimited must come first, or its _generate would never
    be reached and the cap would silently do nothing."""
    cls = llm_mod._throttled_chat_openai()
    names = [c.__name__ for c in cls.__mro__]
    assert names.index("ConcurrencyLimited") < names.index("ChatOpenAI")


def test_dedicated_clients_carry_the_retry_budget(with_key):
    """Residual 429s (from other users of the shared endpoint) should back off and
    retry rather than fall straight through to the deterministic path."""
    client = llm_mod.get_llm(max_tokens=100)
    assert client.max_retries >= 2


# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw, expected", [("1", 1), ("4", 4), ("0", 1), ("-3", 1)])
def test_concurrency_is_configurable_and_never_zero(monkeypatch, raw, expected):
    """A misconfigured LLM_MAX_CONCURRENCY=0 would block every call forever."""
    import importlib

    monkeypatch.setenv("LLM_MAX_CONCURRENCY", raw)
    try:
        assert importlib.reload(llm_mod).max_concurrency() == expected
    finally:
        monkeypatch.delenv("LLM_MAX_CONCURRENCY", raising=False)
        importlib.reload(llm_mod)


def test_enrichment_pool_is_sized_against_the_cap():
    """Each enrichment job fans out to two model calls, so the pool must not be sized as
    if it were one call per job — extra workers just park on the semaphore."""
    import analysis_service

    assert analysis_service._ENRICHMENT_WORKERS <= llm_mod.max_concurrency() * 2
