"""The Analyst — writes the customer-facing consulting memo in a single grounded LLM call.

``pipeline.py`` computes ``analyst_out`` (which includes the per-category
current-vs-alternative-vs-no-subscription comparison, ``category_subscription_analysis``)
and ``forecaster_out`` deterministically before this module ever runs. This used to
re-derive that same data through a multi-hop ReAct tool loop (analyze -> forecast ->
optimize -> tariff lookups), paying one LLM round-trip per tool call on the synchronous
``/api/analyze`` critical path. It now makes exactly one LLM call: every figure is
injected into the prompt verbatim instead of re-fetched, so the LLM never computes
money — see the "never state a number you did not get from the provided data" rule in
the system prompt. The one piece of retrieval this still does itself is pulling the
tariff/AGB documents relevant to the plans named in ``category_subscription_analysis``,
so the memo can keep citing real conditions without needing an agentic search loop to
find them.

Used by :mod:`agent.pipeline` for the ``/analyze`` memo. Requires an LLM key (``pipeline``
guards with ``llm_available()`` and falls back to the deterministic template memo). The
``/analyze`` contract numbers are assembled separately from direct engine calls, so a
misbehaving memo call can never corrupt the figures the dashboard reads.
"""

import json
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agent.json_extract import extract_json
from agent.llm import get_llm
from agent.observability import get_prompt, trace
from agent.tools.knowledge import list_tariff_docs, read_tariff_doc

_PROMPT_PATH = Path(__file__).with_name("prompts") / "analyst_system.md"
# Local copy of the system prompt, used as the offline fallback when the
# Langfuse-managed "analyst-memo" prompt cannot be fetched (or is disabled).
_SYSTEM_PROMPT_FALLBACK = _PROMPT_PATH.read_text(encoding="utf-8")

# Cap how many tariff documents get pulled into one grounding payload, and how much
# of each — some AGB files run 40k-100k characters of legalese, which would blow up
# the single call's context (and its latency/cost) far worse than the tool loop did.
# The per-plan-name cap only matters for the fuzzy-search fallback below: one plan's
# fare-class/discount variants (e.g. BahnCard 25 has separate docs per class x
# normal/reduced/senior/probe) could otherwise eat the whole budget and starve the
# other recommended plan(s) of any doc at all.
_MAX_TARIFF_DOCS = 6
_MAX_DOCS_PER_PLAN = 2
_MAX_DOC_CHARS = 4000


def _looks_like_language_mix(english: str, german: str) -> bool:
    """Cheap heuristic for the failure mode seen in live testing: one field holds both
    languages (joined by a markdown separator) and the other is a duplicate of the
    English text. Doesn't attempt real language detection — just catches the two
    concrete symptoms observed: a stray "---" divider inside a field, and the german
    field being byte-identical (or near-identical) to the english one."""
    if not english.strip() or not german.strip():
        return True
    if "---" in english or "---" in german:
        return True
    return english.strip() == german.strip()


def _read_doc_by_markdown_ref(markdown_ref: str):
    """Read a tariff doc via its catalog ``markdown_ref`` (e.g.
    ``"ÖPNV_Bahncards/2. Klasse/Bahncard 25/bahncard25_2klasse.md"``). Resolves by the
    filename stem rather than the full path, since ``read_tariff_doc`` matches on the
    scanned doc ``id`` (= ``Path(path).stem``) and doing so sidesteps any '/' vs '\\'
    path-separator mismatch between the catalog's forward-slash paths and a scanned
    Windows path."""
    doc_id = Path(markdown_ref).stem
    text = read_tariff_doc.invoke({"doc_id": doc_id})
    if text.startswith("No tariff document") or text.startswith("Could not read"):
        return None
    return doc_id, text


def _fuzzy_tariff_docs(plan_names: list, seen_ids: set) -> list:
    """Fallback for plans with no ``markdown_ref`` in the catalog: search
    ``list_tariff_docs`` by plan name instead of resolving an exact doc."""
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
            docs.append({"id": m["id"], "title": m["title"], "text": text})
            added_for_plan += 1
            if len(docs) >= _MAX_TARIFF_DOCS:
                break
    return docs


def _relevant_tariff_docs(plan_names: list, catalog_by_name: dict) -> list:
    """Pull the tariff/AGB docs for the recommended plans, capped and truncated so the
    grounding payload stays bounded.

    Prefers the catalog's ``markdown_ref`` — an exact 1:1 pointer to the right doc for
    that specific plan variant (e.g. the right BahnCard 25 age band/class), set by
    whichever catalog row the optimizer actually picked. Falls back to a fuzzy
    ``list_tariff_docs`` name search only for plans with no ``markdown_ref`` on file.
    """
    seen_ids: set = set()
    docs: list = []
    fuzzy_names: list = []
    for name in plan_names:
        plan = catalog_by_name.get(name)
        markdown_ref = plan.get("markdown_ref") if plan else None
        if not markdown_ref:
            fuzzy_names.append(name)
            continue
        resolved = _read_doc_by_markdown_ref(markdown_ref)
        if resolved is None:
            fuzzy_names.append(name)
            continue
        doc_id, text = resolved
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)
        docs.append({"id": doc_id, "title": name, "text": text})

    if len(docs) < _MAX_TARIFF_DOCS and fuzzy_names:
        docs += _fuzzy_tariff_docs(fuzzy_names, seen_ids)

    for doc in docs:
        if len(doc["text"]) > _MAX_DOC_CHARS:
            doc["text"] = doc["text"][:_MAX_DOC_CHARS].rstrip() + "\n…(truncated)"
    return docs[:_MAX_TARIFF_DOCS]


def run_briefing(
    name: str,
    analyst_out: dict,
    forecaster_out: dict,
    pricing_catalog: list,
    user_id: str | None = None,
) -> tuple[str, str, str | None]:
    """Write the (english, german, trace_id) memo from the already-computed engine outputs.

    Every euro/CO2/trip figure is handed in verbatim from the deterministic pipeline
    step; the only work done here is fetching the tariff documents relevant to the
    plans named in analyst_out's category_subscription_analysis (currently-held
    subscriptions plus each category's cheapest priceable alternative, if any) and
    making one grounded LLM call. Raises on malformed output so the caller can fall
    back to the template memo.

    ``user_id`` (a non-PII UUID) is attached to the Langfuse trace for the memo call
    when tracing is enabled, so memo generations are attributable per user. The third
    return value is the Langfuse ``trace_id`` (or ``None`` when tracing is disabled) so
    the caller can later attach a ``recommendation-accepted`` feedback score to it.
    """
    plan_names = sorted({
        plan_name
        for entry in analyst_out.get("category_subscription_analysis", [])
        for plan_name in (
            [c["provider_plan_name"] for c in entry.get("current_subscriptions", [])]
            # recommended_alternative is the plan the memo actually narrates as the
            # switch/consider-subscribing suggestion (the multi-criteria scoring
            # winner, not necessarily the cheapest — see analysis.py); cheapest_
            # alternative is included too since the memo may still cite it for
            # comparison, and older persisted rows won't carry recommended_alternative.
            + ([entry["recommended_alternative"]["provider_plan_name"]] if entry.get("recommended_alternative") else [])
            + ([entry["cheapest_alternative"]["provider_plan_name"]] if entry.get("cheapest_alternative") else [])
        )
        if plan_name
    })
    catalog_by_name = {p["name"]: p for p in pricing_catalog if p.get("name")}
    grounding = {
        "analysis": analyst_out,
        "forecast": forecaster_out,
        "tariff_documents": _relevant_tariff_docs(plan_names, catalog_by_name),
    }

    # Fetch the versioned system prompt from Langfuse (falls back to the local
    # copy when Langfuse is disabled or unreachable); link it to the trace so the
    # Generation shows exactly which prompt version produced the memo.
    prompt = get_prompt("analyst-memo", fallback=_SYSTEM_PROMPT_FALLBACK, type="text")
    system_prompt = prompt.compile() if prompt is not None else _SYSTEM_PROMPT_FALLBACK

    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
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

    # One retry: the LLM occasionally merges english/german into one field instead of
    # keeping them separate (see backend-review addendum 2026-07-08). Re-prompting once
    # with the bad reply in context reliably re-separates them; a second failure falls
    # back to the deterministic template memo via the caller's except-clause.
    with trace(
        "analyst-memo",
        user_id=user_id,
        tags=["analyst", "memo", "analyze-pipeline"],
        metadata={"memo_source": "llm"},
    ) as tr:
        trace_id = tr.trace_id
        for attempt in range(2):
            response = llm.invoke(messages, config=tr.config(prompt=prompt))
            data = extract_json(response.content)
            if not data or "english" not in data or "german" not in data:
                raise ValueError("Analyst memo response missing english/german keys")
            
            english, german = data["english"], data["german"]
            if not _looks_like_language_mix(english, german):
                return english, german, trace_id
                
            if attempt == 0:
                messages += [
                    AIMessage(content=response.content),
                    HumanMessage(
                        content=(
                            "Your reply mixed the two languages into one field (or "
                            "duplicated one field's content into the other). Reply again "
                            "with STRICT JSON only: {\"english\": \"<memo>\", "
                            "\"german\": \"<memo>\"} where each field is a complete, "
                            "self-contained memo in exactly one language, with no "
                            "separators or repeated content."
                        )
                    ),
                ]

    raise ValueError("Analyst memo mixed english/german after retry")