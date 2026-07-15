"""Shared multi-criteria (cost + CO2 + time) scoring — deterministic, no LLM.

Used by both the within-category keep/switch/cancel decision
(``analysis.py::_pick_recommendation``, ``reoptimize.py::_rederive_entry``) and the
cross-category modal-shift ranking (``modal_shift.py``), so both share one scoring
primitive instead of two independently-tuned implementations.

Normalization is per-decision (min-max across the candidate set actually being
compared), not against a fixed global reference scale — cost/CO2/time have no shared
natural unit that wouldn't need constant manual re-tuning, and per-decision min-max
self-scales without any of that. When a decision's candidates have (near-)identical
values on one axis — the common case *within* one category today, since the same
physical trips/mode happen regardless of which plan pays for them — that axis
contributes a neutral 0.5 to every candidate instead of an unstable ordering driven by
rounding noise. This is also why, absent real CO2/time variance, this module's output
reduces to a pure-cost ranking in practice: the cost axis alone still separates the
candidates once CO2/time go neutral.
"""

from __future__ import annotations

# An axis's spread must be at least this fraction of its own scale to be treated as
# real variance rather than rounding noise — below it, every candidate gets a neutral
# 0.5 on that axis instead of an arbitrary ordering.
_DEGENERATE_RANGE_FRACTION = 0.01
_EPSILON = 1e-9


def resolve_weights(
    cost_priority, co2_priority, convenience_priority
) -> dict[str, float]:
    """0-100 onboarding scores -> {"cost", "co2", "time"} weights summing to 1.

    ``convenience_priority`` (the onboarding's ``score_flexibility``) maps directly
    onto the time axis — there is no other quantifiable "convenience" signal in the
    data model (no transfer counts, no reliability metric), so treating it as an
    independent 4th axis would only add a synthetic, redundant one.

    All-``None``/non-numeric/all-zero priorities fall back to an equal three-way
    split (neutral default, matches today's behaviour when no preferences are known).
    """
    def _num(value) -> float:
        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            return 0.0

    cost, co2, time = _num(cost_priority), _num(co2_priority), _num(convenience_priority)
    total = cost + co2 + time
    if total <= 0:
        return {"cost": 1 / 3, "co2": 1 / 3, "time": 1 / 3}
    return {"cost": cost / total, "co2": co2 / total, "time": time / total}


def score_candidates(
    candidates: list[dict],
    weights: dict[str, float],
    cost_key: str = "annual_cost_eur",
    co2_key: str = "annual_co2_kg",
    time_key: str = "annual_time_minutes",
) -> list[dict]:
    """Shallow-copies each candidate and attaches ``"score"`` (0..1, higher = better)
    and ``"score_breakdown"`` (``{"cost", "co2", "time"}`` -> 0..1 each, only the axes
    actually scored).

    An axis is scored only when EVERY candidate carries a non-``None`` value for it —
    a partially-missing axis is dropped for the whole decision rather than mixing
    real and absent values, and its weight is redistributed proportionally across the
    remaining present axes (never silently treated as 0/worst for the candidates that
    do have it).
    """
    axis_keys = {"cost": cost_key, "co2": co2_key, "time": time_key}

    axis_values: dict[str, list[float]] = {}
    for axis, key in axis_keys.items():
        if not candidates:
            continue
        raw = [c.get(key) for c in candidates]
        if all(v is not None for v in raw):
            axis_values[axis] = [float(v) for v in raw]

    present_weight = sum(weights.get(axis, 0.0) for axis in axis_values)
    if not axis_values:
        eff_weights: dict[str, float] = {}
    elif present_weight <= 0:
        eff_weights = {axis: 1.0 / len(axis_values) for axis in axis_values}
    else:
        eff_weights = {axis: weights.get(axis, 0.0) / present_weight for axis in axis_values}

    norm_by_axis: dict[str, list[float]] = {}
    for axis, values in axis_values.items():
        lo, hi = min(values), max(values)
        rng = hi - lo
        scale = max(abs(hi), abs(lo), _EPSILON)
        if rng / scale < _DEGENERATE_RANGE_FRACTION:
            norm_by_axis[axis] = [0.5] * len(values)
        else:
            norm_by_axis[axis] = [(hi - v) / rng for v in values]

    scored = []
    for i, candidate in enumerate(candidates):
        breakdown = {axis: round(norm_by_axis[axis][i], 4) for axis in axis_values}
        score = sum(eff_weights[axis] * norm_by_axis[axis][i] for axis in axis_values)
        out = dict(candidate)
        out["score"] = round(score, 6)
        out["score_breakdown"] = breakdown
        scored.append(out)
    return scored


def pick_best_category_option(
    current: dict | None,
    no_subscription: dict | None,
    alternatives: list[dict] | None,
    has_held_subs: bool,
    weights: dict[str, float],
) -> dict:
    """The shared N-way keep/cancel/switch chooser.

    ``current``/``no_subscription``: ``{"annual_cost_eur", "annual_co2_kg",
    "annual_time_minutes"}`` or ``None``/cost ``None`` when that option can't be
    priced (only possible today on the forecast-projection path). ``alternatives``:
    same shape, each additionally carrying an opaque ``"_ref"`` pointing back to the
    caller's own richer alternative object (so the caller gets the winning object
    back without this module needing to know its shape) — pass them pre-sorted
    cheapest-first so cost ties among alternatives resolve to the cheapest one,
    matching how ``analysis.py`` already ranks them.

    Every candidate with an unknown (``None``) cost is excluded before scoring — a
    ``None`` cost can never win. If nothing is priced at all, the recommendation is
    ``"insufficient_cost_data"`` rather than silently defaulting to "keep current"
    with no real number behind it.

    Ties (equal score) break toward the earlier candidate in evaluation order
    (current, then no-subscription, then alternatives cheapest-first) — this is also
    a lower-cost tiebreak in the common case where CO2/time are neutral (see module
    docstring), reproducing the historical pure-cost tie-break exactly.

    Returns ``{"best_cost", "winning_alternative", "recommendation", "score_breakdown"}``.
    """
    entries: list[tuple[str, dict]] = []
    if current is not None and current.get("annual_cost_eur") is not None:
        entries.append(("current", current))
    if no_subscription is not None and no_subscription.get("annual_cost_eur") is not None:
        entries.append(("no_subscription", no_subscription))
    for alt in alternatives or []:
        if alt.get("annual_cost_eur") is not None:
            entries.append(("alternative", alt))

    if not entries:
        return {
            "best_cost": None,
            "winning_alternative": None,
            "recommendation": "insufficient_cost_data",
            "score_breakdown": None,
        }

    scored = score_candidates([entry[1] for entry in entries], weights)

    best_idx = 0
    for i in range(1, len(entries)):
        candidate, best = scored[i], scored[best_idx]
        if candidate["score"] > best["score"] + _EPSILON:
            best_idx = i
        elif (
            abs(candidate["score"] - best["score"]) <= _EPSILON
            and candidate["annual_cost_eur"] < best["annual_cost_eur"] - _EPSILON
        ):
            best_idx = i

    kind, _ = entries[best_idx]
    winner = scored[best_idx]
    if kind == "current":
        recommendation = "keep_current" if has_held_subs else "no_subscription_needed"
        winning_alternative = None
    elif kind == "no_subscription":
        recommendation = "cancel_current_go_pay_as_you_go" if has_held_subs else "no_subscription_needed"
        winning_alternative = None
    else:
        recommendation = "switch_to_alternative" if has_held_subs else "consider_subscribing"
        winning_alternative = winner.get("_ref")

    return {
        "best_cost": winner["annual_cost_eur"],
        "winning_alternative": winning_alternative,
        "recommendation": recommendation,
        "score_breakdown": winner["score_breakdown"],
    }
