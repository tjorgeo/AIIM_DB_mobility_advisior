"""LLM free-text feasibility judgment for modal-shift candidates.

Given candidate category shifts that have ALREADY passed the deterministic structural
filter in ``engines.modal_shift``, this makes one batched LLM call judging whether each
shift is realistic given the customer's own free-text onboarding answers
(``mobility_constraints`` / ``travel_statement`` / ``activity_statement``) — a stated
health condition, a caregiving responsibility, an explicit need for a car — the kind of
real-world constraint no fixed rule set can catch. It never computes a euro/CO₂/minute
figure and never overrides the deterministic hard-filter; it only returns feasible/not
plus a reason.

``judge`` is injected into ``engines.modal_shift.build_modal_shift_suggestions`` so the
engine itself stays LLM-free. It returns plain dicts (one per candidate) so the engine
has no dependency on this module's pydantic types.
"""

import json
from typing import Literal, Optional

from pydantic import BaseModel

from agent.json_extract import extract_json


class FeasibilityJudgment(BaseModel):
    candidate_id: str
    feasible: bool
    confidence: Literal["high", "medium", "low"]
    reasoning: str
    excluded_reason: Optional[str] = None


class ModalShiftFeasibilityOutput(BaseModel):
    judgments: list[FeasibilityJudgment]
    rationale: str


_SYSTEM_PROMPT = """\
You are judging whether it is realistic for a mobility customer to shift a set of \
trips from one transport category to another, based ONLY on the customer's own \
free-text onboarding answers in the payload below.

Every candidate you are given has ALREADY passed structural eligibility checks \
(avoided transport modes, driving license) — your job is to catch real-world \
constraints that only free text can reveal (a stated health condition, a caregiving \
responsibility, an explicit need for a car, etc.), not to re-derive cost, CO2 or \
time — those are not shown to you and are not your job.

Default every candidate to feasible=true unless the free text gives a CONCRETE reason \
against it. Never invent a constraint that is not actually stated. Use confidence \
"low" when the text is vague or does not mention anything relevant to that specific \
candidate. excluded_reason is required only when feasible is false, and must
reference the actual free text, not a generic assumption.

Respond with STRICT JSON matching this schema — no markdown fences, no prose outside \
the JSON:
{
  "judgments": [
    {"candidate_id": <str>, "feasible": <bool>, "confidence": "high" | "medium" | "low",
     "reasoning": <str>, "excluded_reason": <str | null>}
  ],
  "rationale": <str>
}
"""


def _fallback_judgment(candidate_id: str, reason: str) -> dict:
    """Feasible/low judgment used whenever the LLM can't be consulted — surfaced as
    such rather than silently dropping the candidate. Returned as a plain dict (same
    shape as ``FeasibilityJudgment.model_dump()``) so the engine stays type-free."""
    return {
        "candidate_id": candidate_id,
        "feasible": True,
        "confidence": "low",
        "reasoning": reason,
        "excluded_reason": None,
    }


def judge(candidates: list[dict], onboarding: dict) -> dict[str, dict]:
    """One batched structured-output LLM call judging every candidate's free-text
    feasibility. Always returns exactly one judgment (a plain dict) per candidate
    passed in, so callers never need to handle a missing entry. Falls back to a
    feasible/low judgment for any candidate when the LLM is unavailable, the reply
    can't be parsed, or the call errors."""
    if not candidates:
        return {}

    fallback = {
        c["candidate_id"]: _fallback_judgment(
            c["candidate_id"],
            "LLM not available; free-text onboarding constraints were not checked.",
        )
        for c in candidates
    }

    try:
        from agent.llm import get_llm, llm_available
        from langchain_core.messages import HumanMessage, SystemMessage
        if not llm_available():
            return fallback
    except ImportError:
        return fallback

    payload = {
        "candidates": [
            {
                "candidate_id": c["candidate_id"],
                "from_category": c["from_category"],
                "to_category": c["to_category"],
                "annual_trips": c["annual_trips"],
            }
            for c in candidates
        ],
        "mobility_constraints": onboarding.get("mobility_constraints") or [],
        "travel_statement": onboarding.get("travel_statement"),
        "activity_statement": onboarding.get("activity_statement"),
    }
    try:
        from agent.observability import llm_config

        response = get_llm().invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
            config=llm_config("feasibility-judge"),
        )
        data = extract_json(response.content)
        if not data:
            return fallback
        parsed = ModalShiftFeasibilityOutput(**data)
        by_id = {j.candidate_id: j.model_dump() for j in parsed.judgments}
        # A partial reply (LLM dropped a candidate) is still useful for the ones it did
        # cover — fall back only for the specific candidate(s) missing, not the batch.
        return {
            c["candidate_id"]: by_id.get(c["candidate_id"]) or fallback[c["candidate_id"]]
            for c in candidates
        }
    except Exception:
        return fallback
