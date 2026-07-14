"""University GPT (OpenAI-compatible) LLM access.

A single place that knows how to reach the model and whether it is configured.
When ``UNI_GPT_API_KEY`` is absent every LLM-backed feature degrades gracefully
(memos fall back to deterministic templates; chat/onboarding return 503), so the
app stays fully usable without a key.
"""

import os

UNI_GPT_BASE_URL = os.getenv("UNI_GPT_BASE_URL", "https://chat.kiconnect.nrw/api/v1")
# Exact model id as listed by GET /api/v1/models on the kiconnect endpoint.
# Override via UNI_GPT_MODEL if the catalogue changes.
UNI_GPT_MODEL = os.getenv("UNI_GPT_MODEL", "OpenAI GPT OSS 120b KI:Inferenz.nrw")
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")


def llm_available() -> bool:
    """True when an API key is configured, i.e. LLM features can run."""
    return bool(UNI_GPT_API_KEY.strip())


_llm = None


def get_llm(temperature: float = 0.0):
    """Lazily build a shared ChatOpenAI client pointed at University GPT.

    ``timeout``/``max_retries`` are set explicitly: without them a stalled or
    rate-limited call to the shared university endpoint hangs indefinitely — the chat
    request (and the frontend's "typing…" indicator) never resolves into either a
    reply or an error. Capping it means a stuck call surfaces as an error within
    ~30s, which /api/chat and /api/chat/stream already turn into a 500 / SSE error
    event that the frontend falls back on.
    """
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI

        _llm = ChatOpenAI(
            model=UNI_GPT_MODEL,
            openai_api_key=UNI_GPT_API_KEY,
            openai_api_base=UNI_GPT_BASE_URL,
            temperature=temperature,
            timeout=30,
            max_retries=1,
        )
    return _llm
