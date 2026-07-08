"""The Analyst — writes the customer-facing consulting memo in a single grounded LLM call.

``pipeline.py`` computes ``analyst_out``/``forecaster_out``/``optimizer_out``
deterministically before this module ever runs. This used to re-derive that same data
through a multi-hop ReAct tool loop (analyze -> forecast -> optimize -> tariff lookups),
paying one LLM round-trip per tool call on the synchronous ``/api/analyze`` critical
path. It now makes exactly one LLM call: every figure is injected into the prompt
verbatim instead of re-fetched, so the LLM never computes money — see the "never state
a number you did not get from the provided data" rule in the system prompt. The one
piece of retrieval this still does itself is pulling the tariff/AGB documents relevant
to the recommended plans, so the memo can keep citing real conditions without needing
an agentic search loop to find them.

Used by :mod:`agent.pipeline` for the ``/analyze`` memo. Requires an LLM key (``pipeline``
guards with ``llm_available()`` and falls back to the deterministic template memo). The
``/analyze`` contract numbers are assembled separately from direct engine calls, so a
misbehaving memo call can never corrupt the figures the dashboard reads.
"""

import json
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage

from agent.llm import get_llm
from agent.tools.knowledge import list_tariff_docs, read_tariff_doc

_PROMPT_PATH = Path(__file__).with_name("prompts") / "analyst_system.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Cap how many tariff documents get pulled into one grounding payload, and how much
# of each — some AGB files run 40k-100k characters of legalese, which would blow up
# the single call's context (and its latency/cost) far worse than the tool loop did.
# Per-plan-name cap keeps one plan's fare-class/discount variants (e.g. BahnCard 25
# has separate docs per class x normal/reduced/senior/probe) from eating the whole
# budget and starving the other recommended plan(s) of any doc at all.
_MAX_TARIFF_DOCS = 6
_MAX_DOCS_PER_PLAN = 2
_MAX_DOC_CHARS = 4000


def _extract_json(text: str):
    """Pull the first complete JSON object out of an LLM reply (tolerates prose or
    ```json fences before/after it). Uses raw_decode from the first ``{`` so it stops
    at that object's actual matching closing brace, instead of a greedy regex that
    would span to the *last* ``}`` in the whole text if any stray braces follow."""
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return None


def _relevant_tariff_docs(plan_names: list) -> list:
    """Deterministically pull the tariff/AGB docs matching the recommended plan names
    (via the same catalog ``list_tariff_docs``/``read_tariff_doc`` search the ReAct
    agent used to drive itself), so the single grounded call still cites real tariff
    conditions instead of losing that context."""
    seen_ids: set = set()
    docs: list = []
    for name in plan_names:
        if not name or len(docs) >= _MAX_TARIFF_DOCS:
            break
        try:
            matches = json.loads(list_tariff_docs.invoke({"query": name}))
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(matches, list):
            continue
        added_for_plan = 0
        for m in matches:
            if added_for_plan >= _MAX_DOCS_PER_PLAN:
                break
            if m["id"] in seen_ids:
                continue
            seen_ids.add(m["id"])
            text = read_tariff_doc.invoke({"doc_id": m["id"]})
            if len(text) > _MAX_DOC_CHARS:
                text = text[:_MAX_DOC_CHARS].rstrip() + "\n…(truncated)"
            docs.append({"id": m["id"], "title": m["title"], "text": text})
            added_for_plan += 1
            if len(docs) >= _MAX_TARIFF_DOCS:
                break
    return docs


def run_briefing(
    name: str, analyst_out: dict, forecaster_out: dict, optimizer_out: dict
) -> tuple[str, str]:
    """Write the (english, german) memo from the already-computed engine outputs.

    Every euro/CO2/trip figure is handed in verbatim from the deterministic pipeline
    step; the only work done here is fetching the tariff documents relevant to the
    recommended portfolio and making one grounded LLM call. Raises on malformed output
    so the caller can fall back to the template memo.
    """
    plan_names = sorted(
        {
            plan_name
            for scenario in optimizer_out.get("scenarios", [])
            for plan_name in scenario.get("portfolio", [])
        }
    )
    grounding = {
        "analysis": analyst_out,
        "forecast": forecaster_out,
        "optimizer": optimizer_out,
        "tariff_documents": _relevant_tariff_docs(plan_names),
    }

    response = get_llm().invoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"The customer is {name}. Below is the complete grounded data — the "
                    "analysis, forecast, optimizer results and the tariff documents "
                    "relevant to the recommended plans, all as JSON. Write the "
                    "recommendation memo using only these figures.\n\n"
                    + json.dumps(grounding, ensure_ascii=False, default=str)
                )
            ),
        ]
    )

    data = _extract_json(response.content)
    if not data or "english" not in data or "german" not in data:
        raise ValueError("Analyst memo response missing english/german keys")
    return data["english"], data["german"]
