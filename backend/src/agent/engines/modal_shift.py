"""Cross-category modal-shift comparison — the one place this pipeline compares
travel *across* subscription categories rather than within one.

For every category the user actually travels in, evaluates whether shifting those
same trips onto a *different* category's mode (e.g. car-sharing trips onto public
transport) would score better on the same weighted cost/CO2/time scale as the
within-category recommendation (``engines/scoring.py``), against a "stay" baseline of
the category's own real numbers.

Money, CO2 and time all stay strictly deterministic:
* Cost is priced off ``analysis.py::implied_rate_by_mode`` — the same real historical
  €/km-or-€/trip rate used elsewhere, never a second invented pricing formula. A mode
  with no historical rate (the user has never actually used it) can't be honestly
  priced and the candidate is excluded rather than guessed at.
* CO2/time are priced off ``mode_factors.py``'s distance-based reference tables (see
  that module for why this, not an LLM, estimates them).

The one place an LLM is used is judging whether a structurally-eligible candidate
shift is realistic given the user's own free-text onboarding answers
(``mobility_constraints``/``travel_statement``/``activity_statement``) — a
health condition, a caregiving responsibility, a stated need for a car — the kind of
real-world constraint no fixed rule set can reliably catch, but which the user has
often already told the app about in their own words and which currently goes unused
by every other engine. The LLM never computes a euro/CO2/minute figure and never
overrides the deterministic hard-filter below; it only returns feasible/not-feasible
plus a reason, mirroring forecasting.py's structured-output pattern (pydantic-
validated JSON via ``json_extract.extract_json``, a deterministic fallback when no
LLM key is configured or the call/parse fails — this call runs fresh on every
``/api/analyze``, no caching).
"""

import json
from typing import Literal, Optional

from pydantic import BaseModel

from agent import mode_factors
from agent.engines.analysis import implied_rate_by_mode
from agent.engines.scoring import resolve_weights, score_candidates
from agent.json_extract import extract_json

# category key -> the one raw transport_mode used to price/estimate a shift INTO that
# category (and to check against avoided_transport_modes). Mirrors
# analysis.py::_category_definitions()'s category/mode carve-up — public_transport's
# bucket actually covers two raw modes (public_transport + regional_train, see
# schema_map.category_covers_mode), but a single representative mode is a deliberate
# simplification here: the category, not the raw mode, is this module's unit of
# comparison, same as everywhere else category_subscription_analysis is consumed.
_SHIFT_TARGET_MODE = {
    "bike_sharing": "bike_sharing",
    "car_sharing": "car_sharing",
    "e_scooter": "e_scooter",
    "public_transport": "public_transport",
    "long_distance_rail": "long_distance_train",
}


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


def _hard_exclusion_reason(
    to_category: str, to_mode: str, onboarding: dict, avg_trip_km: float,
) -> str | None:
    """Deterministic, structural eligibility — no LLM needed. Returns the reason a
    candidate is excluded, or ``None`` when it's feasible.

    Deliberately does NOT gate on ``car_access``/``bike_access``: those describe what
    the user already owns, not whether they're allowed to use a *shared* vehicle/bike
    — excluding on them would wrongly rule out car-sharing for exactly the person
    car-sharing is for (someone without their own car).

    The distance check exists because ``_price_candidate``'s linear cost/CO2/time
    model will happily price ANY distance on ANY mode (see mode_factors.py's module
    note) — e.g. it would otherwise let a customer's short bike-share hops get
    "priced" onto long-distance rail, which doesn't serve trips that short at all.
    """
    avoided = {str(m).lower() for m in (onboarding.get("avoided_transport_modes") or [])}
    if to_mode.lower() in avoided:
        return "customer's onboarding lists this as an avoided transport mode"
    if to_category == "car_sharing" and not onboarding.get("has_driving_license"):
        return "no driving license on file"
    if not mode_factors.is_plausible_trip_distance(to_mode, avg_trip_km):
        return f"average trip distance ({avg_trip_km:.1f} km) isn't realistic for this mode"
    return None


def _price_candidate(
    from_category: str,
    to_category: str,
    to_mode: str,
    annual_trips: float,
    annual_distance_km: float,
    rates: dict[str, tuple[float, str]],
) -> dict | None:
    """Deterministic annual cost/CO2/time for shifting ``annual_trips``/
    ``annual_distance_km`` worth of ``from_category`` trips onto ``to_mode`` instead —
    ``None`` when there's no honest way to price it (no historical €/km or €/trip
    rate for ``to_mode`` in ``rates``, i.e. the user has never actually used it, or an
    unknown mode in ``mode_factors``) rather than guessed at.

    The priced cost is ``to_mode``'s pay-as-you-go rate applied to this volume — it
    does not model a hypothetical new subscription discount on the target category
    (that would need re-running the full catalog-matching logic
    ``analysis.py::_rank_alternatives`` already does for the *current* category, for a
    category the user isn't necessarily subscribed to at all); the "stay" baseline it
    gets compared against is the category's own real ``actual_annual_cost_eur``,
    which DOES already reflect any subscription discount held there today.
    """
    if annual_trips <= 0:
        return None
    rate = rates.get(to_mode)
    if rate is None:
        return None
    rate_value, basis = rate
    cost = rate_value * (annual_distance_km if basis == "per_km" else annual_trips)

    co2 = mode_factors.estimate_co2_kg(to_mode, annual_distance_km)
    per_trip_minutes = mode_factors.estimate_time_minutes(to_mode, annual_distance_km / annual_trips)
    if co2 is None or per_trip_minutes is None:
        return None

    return {
        "candidate_id": f"{from_category}->{to_category}",
        "from_category": from_category,
        "to_category": to_category,
        "to_mode": to_mode,
        "annual_trips": round(annual_trips, 1),
        "annual_cost_eur": round(cost, 2),
        "annual_co2_kg": round(co2, 2),
        "annual_time_minutes": round(per_trip_minutes * annual_trips, 1),
        "pricing_basis": f"projected from {to_mode}'s historical €{'/km' if basis == 'per_km' else '/trip'} rate",
    }


def _fallback_judgment(candidate_id: str, reason: str) -> FeasibilityJudgment:
    return FeasibilityJudgment(
        candidate_id=candidate_id, feasible=True, confidence="low", reasoning=reason,
    )


def _judge_feasibility(candidates: list[dict], onboarding: dict) -> dict[str, FeasibilityJudgment]:
    """One batched structured-output LLM call judging every candidate's free-text
    feasibility, mirroring ``forecasting.py``'s pattern (pydantic-validated
    ``extract_json``, deterministic fallback). Always returns exactly one judgment per
    candidate passed in, so callers never need to handle a missing entry.
    """
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
        from agent.llm import llm_available, get_llm
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
        response = get_llm().invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ])
        data = extract_json(response.content)
        if not data:
            return fallback
        parsed = ModalShiftFeasibilityOutput(**data)
        by_id = {j.candidate_id: j for j in parsed.judgments}
        # A partial reply (LLM dropped a candidate) is still useful for the ones it
        # did cover — fall back only for the specific candidate(s) missing, not the
        # whole batch.
        return {
            c["candidate_id"]: by_id.get(c["candidate_id"]) or fallback[c["candidate_id"]]
            for c in candidates
        }
    except Exception:
        return fallback


def build_modal_shift_suggestions(
    mode_breakdown: dict,
    category_subscription_analysis: list[dict],
    onboarding: dict,
    preferences: dict | None,
    use_llm: bool = True,
) -> list[dict]:
    """For each category the user actually travels in, evaluate whether shifting
    those trips onto one of the other categories would beat staying, on the shared
    weighted cost/CO2/time score. Returns one entry per FROM category with
    ``annual_trips > 0`` (every one of the other 4 categories is always either priced
    or excluded with a reason, so there's always something to report).
    """
    onboarding = onboarding or {}
    preferences = preferences or {}
    weights = resolve_weights(
        preferences.get("cost_priority"),
        preferences.get("co2_priority"),
        preferences.get("convenience_priority"),
    )
    rates = implied_rate_by_mode(mode_breakdown)

    from_categories = [
        e for e in category_subscription_analysis if (e.get("annual_trips") or 0) > 0
    ]

    # Pass 1: deterministic hard-filter + pricing for every (from, to) pair.
    priced_by_from: dict[str, list[dict]] = {}
    excluded_by_from: dict[str, list[dict]] = {}
    for entry in from_categories:
        from_category = entry["category"]
        annual_trips = entry["annual_trips"]
        annual_distance_km = entry.get("annual_distance_km") or 0.0
        avg_trip_km = annual_distance_km / annual_trips if annual_trips > 0 else 0.0
        priced, excluded = [], []
        for to_category, to_mode in _SHIFT_TARGET_MODE.items():
            if to_category == from_category:
                continue
            exclusion_reason = _hard_exclusion_reason(to_category, to_mode, onboarding, avg_trip_km)
            if exclusion_reason is not None:
                excluded.append({
                    "from_category": from_category, "to_category": to_category, "to_mode": to_mode,
                    "excluded_reason": exclusion_reason,
                })
                continue
            candidate = _price_candidate(
                from_category, to_category, to_mode, annual_trips, annual_distance_km, rates,
            )
            if candidate is None:
                excluded.append({
                    "from_category": from_category, "to_category": to_category, "to_mode": to_mode,
                    "excluded_reason": "no historical cost/CO2/time basis to price this mode",
                })
                continue
            priced.append(candidate)
        priced_by_from[from_category] = priced
        excluded_by_from[from_category] = excluded

    # Pass 2: one batched LLM feasibility call across every from-category's priced
    # candidates this run (never per-category — one call total per /api/analyze).
    all_priced = [c for candidates in priced_by_from.values() for c in candidates]
    if use_llm:
        judgments = _judge_feasibility(all_priced, onboarding)
    else:
        judgments = {
            c["candidate_id"]: _fallback_judgment(c["candidate_id"], "LLM feasibility check skipped (use_llm=False).")
            for c in all_priced
        }

    # Pass 3: score feasible candidates plus the category's own real "stay" baseline,
    # pick a winner per from-category.
    suggestions = []
    for entry in from_categories:
        from_category = entry["category"]
        priced = priced_by_from.get(from_category) or []
        excluded_candidates = list(excluded_by_from.get(from_category) or [])

        feasible_candidates = []
        for c in priced:
            judgment = judgments.get(c["candidate_id"])
            if judgment is not None and not judgment.feasible:
                excluded_candidates.append({
                    "from_category": c["from_category"], "to_category": c["to_category"],
                    "to_mode": c["to_mode"],
                    "excluded_reason": judgment.excluded_reason or judgment.reasoning,
                })
                continue
            enriched = dict(c)
            enriched["feasibility"] = judgment.model_dump() if judgment else None
            feasible_candidates.append(enriched)

        stay = {
            "candidate_id": "stay",
            "to_category": from_category,
            "annual_cost_eur": entry.get("actual_annual_cost_eur"),
            "annual_co2_kg": entry.get("annual_co2_kg"),
            "annual_time_minutes": entry.get("annual_time_minutes"),
        }
        scored = score_candidates([stay] + feasible_candidates, weights)

        best_idx = 0
        for i in range(1, len(scored)):
            if scored[i]["score"] > scored[best_idx]["score"] + 1e-9:
                best_idx = i
        winner = scored[best_idx]
        suggested_shift = None if winner["candidate_id"] == "stay" else winner

        suggestions.append({
            "from_category": from_category,
            "stay_annual_cost_eur": stay["annual_cost_eur"],
            "stay_annual_co2_kg": stay["annual_co2_kg"],
            "stay_annual_time_minutes": stay["annual_time_minutes"],
            "candidates": scored,
            "suggested_shift": suggested_shift,
            "excluded_candidates": excluded_candidates,
        })

    return suggestions
