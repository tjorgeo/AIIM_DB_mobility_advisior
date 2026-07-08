"""LLM-as-a-Judge evaluators for the recommendation memo.

Two judges, both returning a Langfuse ``Evaluation`` (BOOLEAN 0/1 + reason):

* ``memo-groundedness`` — the headline eval. Enforces the analyst invariant that
  every number/plan in the memo must come from the provided grounding data
  (see prompts/analyst_system.md). This is objectively checkable, which is what
  makes it a good automated eval for this app.
* ``memo-bilingual-complete`` — the German memo must be a faithful, complete
  translation of the English one (same figures, no dropped sections).

The judge uses its own LLM client (``JUDGE_MODEL`` / University GPT by default).
Using the same model family to judge itself is a known limitation — calibrate the
judge against human labels before trusting it (see ``calibrate.py``).
"""

import json
import os

from langfuse import Evaluation

# Judge model config — defaults to the same University GPT endpoint as the app,
# overridable so a stronger/independent judge model can be swapped in.
_JUDGE_BASE_URL = os.getenv("JUDGE_BASE_URL") or os.getenv("UNI_GPT_BASE_URL", "https://chat.kiconnect.nrw/api/v1")
_JUDGE_MODEL = os.getenv("JUDGE_MODEL") or os.getenv("UNI_GPT_MODEL", "OpenAI GPT OSS 120b KI:Inferenz.nrw")
_JUDGE_API_KEY = os.getenv("JUDGE_API_KEY") or os.getenv("UNI_GPT_API_KEY", "")

_judge_llm = None


def get_judge_llm():
    """Lazily build the judge LLM (temperature 0 for stable verdicts)."""
    global _judge_llm
    if _judge_llm is None:
        from langchain_openai import ChatOpenAI

        _judge_llm = ChatOpenAI(
            model=_JUDGE_MODEL,
            openai_api_key=_JUDGE_API_KEY,
            openai_api_base=_JUDGE_BASE_URL,
            temperature=0.0,
        )
    return _judge_llm


def _extract_json(text: str):
    """Pull the first JSON object out of an LLM reply (tolerates prose/fences)."""
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return None


_GROUNDEDNESS_PROMPT = """You are a strict evaluator for a mobility consulting memo.

You are given GROUNDING_DATA (JSON: the customer's analysis, forecast and optimizer \
results) and a MEMO written for the customer.

Decide whether the MEMO is fully grounded: every euro amount, CO2 figure, trip/leg \
count, percentage and subscription/plan name stated in the MEMO must be present in \
GROUNDING_DATA. If the memo states any number or plan name that does not appear in \
GROUNDING_DATA (invented, mis-rounded, or estimated), it is NOT grounded.

Respond with STRICT JSON and nothing else:
{"grounded": true|false, "reason": "<one sentence, cite the first offending value if any>"}
"""

_BILINGUAL_PROMPT = """You are a strict bilingual evaluator.

You are given an ENGLISH memo and a GERMAN memo that are meant to be the same \
recommendation in two languages.

Decide whether the GERMAN memo is a faithful, complete translation of the ENGLISH \
memo: it must convey the same facts, the same figures (euro amounts, CO2, savings) \
and cover the same sections. If the German omits a section, changes a number, or \
adds claims not in the English, it is NOT faithful.

Respond with STRICT JSON and nothing else:
{"faithful": true|false, "reason": "<one sentence>"}
"""


def _judge(system_prompt: str, user_payload: str, key: str):
    """Run one judge call and return (verdict_bool, reason). On any failure returns
    (None, reason) so the caller can mark the row invalid rather than pass/fail."""
    from langchain_core.messages import SystemMessage, HumanMessage

    try:
        resp = get_judge_llm().invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_payload)]
        )
    except Exception as e:  # noqa: BLE001 — surface as invalid, never crash the run
        return None, f"judge call failed: {e}"
    data = _extract_json(resp.content)
    if not data or key not in data:
        return None, "judge returned unparseable output"
    return bool(data[key]), str(data.get("reason", ""))


def groundedness_evaluation(memo_english: str, grounding: dict) -> Evaluation:
    """`memo-groundedness` BOOLEAN score for one memo."""
    payload = (
        "GROUNDING_DATA:\n"
        + json.dumps(grounding, ensure_ascii=False, default=str)
        + "\n\nMEMO:\n"
        + (memo_english or "")
    )
    verdict, reason = _judge(_GROUNDEDNESS_PROMPT, payload, "grounded")
    return Evaluation(
        name="memo-groundedness",
        value=None if verdict is None else int(verdict),
        data_type="BOOLEAN",
        comment=reason,
    )


def bilingual_evaluation(memo_english: str, memo_german: str) -> Evaluation:
    """`memo-bilingual-complete` BOOLEAN score for one memo pair."""
    payload = f"ENGLISH:\n{memo_english or ''}\n\nGERMAN:\n{memo_german or ''}"
    verdict, reason = _judge(_BILINGUAL_PROMPT, payload, "faithful")
    return Evaluation(
        name="memo-bilingual-complete",
        value=None if verdict is None else int(verdict),
        data_type="BOOLEAN",
        comment=reason,
    )


# --- Experiment evaluator adapters (task output -> Evaluation) ---------------
# The experiment task returns {"memo_english", "memo_german", "grounding"}; these
# adapters match the Langfuse evaluator signature (*, input, output, expected_output).


def groundedness_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    output = output or {}
    return groundedness_evaluation(output.get("memo_english", ""), output.get("grounding", {}))


def bilingual_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    output = output or {}
    return bilingual_evaluation(output.get("memo_english", ""), output.get("memo_german", ""))
