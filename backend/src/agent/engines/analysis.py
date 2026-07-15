"""Deterministic mobility analyst agent.

Ingests leg-level travel history and active subscription records, computes
factual usage statistics, detects temporal patterns, and produces a structured
summary. No LLM, no hardcoded thresholds — inefficiencies are flagged only
when the math is unambiguous (e.g. a subscription cost more than it saved).

It also evaluates, per travel category, whether the currently-held subscription
(if any), a cheaper catalog alternative, or no subscription at all (pure
pay-as-you-go) would have been cheapest for how the user actually traveled —
see ``category_subscription_analysis`` in :func:`analyze_portfolio`'s return
value and ``_estimate_alternative_remainder`` for exactly which catalog plans
can be priced this way and which can't.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

from agent import mode_factors
from agent.engines.scoring import pick_best_category_option, resolve_weights
from agent.schema_map import category_covers_mode

logger = logging.getLogger(__name__)


_MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

_ALL_CATEGORIES = {"public_transport", "bike_sharing", "car_sharing", "e_scooter"}

_CATEGORY_LABEL = {
    "public_transport": "Public-transport pass",
    "bike_sharing": "Bike-sharing pass",
    "car_sharing": "Car-sharing membership",
    "e_scooter": "E-scooter pass",
}

# BahnCard-style catalog rows encode their eligibility band as free text in
# subscription_type_other, e.g. "Ages 27-64", "Youth variant; ages 6-26", "Senior
# variant; ages 65+". Parsed so an ineligible age-gated variant is never proposed as
# a cheaper alternative.
_AGE_RANGE_RE = re.compile(r"ages?\s+(\d+)\s*-\s*(\d+)", re.IGNORECASE)
_AGE_MIN_RE = re.compile(r"ages?\s+(\d+)\s*\+", re.IGNORECASE)
# Discount variants gated on a condition we have no data field to verify (disability /
# reduced earning capacity pension) — excluded outright rather than assumed, since
# recommending a plan we can't confirm eligibility for is worse than not recommending it.
_UNVERIFIABLE_ELIGIBILITY_RE = re.compile(r"disability|reduced earning capacity|pension", re.IGNORECASE)
# Employer-sponsored (e.g. Deutschlandticket Jobticket) and student-benefit plans are
# gated on a condition no user-profile field can confirm (does this employer actually
# offer it? is this person enrolled?) — excluded from alternatives for the same reason
# as the disability/pension cards above. A user who already holds one still shows up
# under current_subscriptions; this only stops proposing one as a switch/new pickup.
_UNVERIFIABLE_SUBSCRIPTION_TYPES = {"employer_benefit", "student_benefit"}
# BahnCard 25/50/100 are percentage-discount cards (25%/50% off regular fares), not
# flat-rate passes — the discount % isn't a structured catalog field (only prose in
# the tariff markdown states it), so it's parsed from the well-known product name.
# This is a hardcoded domain assumption, same spirit as the age-range parsing above.
_BAHNCARD_DISCOUNT_RE = re.compile(r"bahncard\s*(\d+)", re.IGNORECASE)
# BahnCard 1st-class variants cost more than their 2nd-class siblings for the *same*
# discount percentage. Trip legs never record which class a historical fare was
# actually priced in (ticket_class is unpopulated in production data), so there is no
# per-leg evidence of whether reference_cost_eur reflects a 1st- or 2nd-class fare —
# only the class of a currently-held BahnCard (parsed from its own name) can anchor
# that. Comparing a 1st-class card's price against fares that might be 2nd-class (or
# vice versa) would silently mix the two, understating or overstating the real
# saving. See the class-matching filter in _build_category_entry below.
_TRAVEL_CLASS_RE = re.compile(r"(\d)\.\s*klasse", re.IGNORECASE)
# BahnCard-family products are split out of the "public_transport" catalog category
# into their own analysis bucket, scoped to long_distance_train only — see the
# "8b." comment below for why regional_train stays exclusively Deutschlandticket
# territory instead of being shared between the two (BahnCard does technically
# discount regional fares too, but modeling that overlap correctly would require
# knowing which of two products a user would use for a given regional trip; scoping
# BahnCard to long-distance only keeps every number unambiguous).
_LONG_DISTANCE_RAIL_CATEGORY = "long_distance_rail"
_LONG_DISTANCE_RAIL_MODE = "long_distance_train"


def _is_bahncard_plan(name: str) -> bool:
    return bool(_BAHNCARD_DISCOUNT_RE.search(name or ""))


def _travel_class(name: str) -> int | None:
    """1 or 2 if ``name`` names its travel class (e.g. "BahnCard 50, 1. Klasse"),
    else None (no class distinction — e.g. Deutschlandticket, or a non-rail plan)."""
    match = _TRAVEL_CLASS_RE.search(name or "")
    return int(match.group(1)) if match else None


def _display_category(db_category: str, name: str) -> str:
    """The category a subscription is *reported* under, as opposed to its raw
    ``subscription_category`` DB value. A BahnCard is stored under the same
    "public_transport" catalog row as a Deutschlandticket, but it's a long-distance
    product — reporting it as "public_transport" would read as if it covered local/
    regional trips, which it doesn't (see the "8b." comment below). Everywhere a
    subscription's category is surfaced in output (not used as an internal lookup
    key), it should go through this so a BahnCard is never labeled "public_transport"."""
    if db_category == "public_transport" and _is_bahncard_plan(name):
        return _LONG_DISTANCE_RAIL_CATEGORY
    return db_category


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_eligible(plan: dict, user_age) -> bool:
    """Whether ``plan`` may be proposed to a customer of ``user_age`` (``None`` if
    unknown, in which case age-gated plans are not excluded — there's nothing to check
    them against)."""
    if (plan.get("subscription_type") or "").lower() in _UNVERIFIABLE_SUBSCRIPTION_TYPES:
        return False
    text = plan.get("subscription_type_other") or ""
    if _UNVERIFIABLE_ELIGIBILITY_RE.search(text):
        return False
    if user_age is None:
        return True
    match = _AGE_RANGE_RE.search(text)
    if match:
        lo, hi = int(match.group(1)), int(match.group(2))
        return lo <= user_age <= hi
    match = _AGE_MIN_RE.search(text)
    if match:
        return user_age >= int(match.group(1))
    return True


def _is_ongoing_candidate(plan: dict) -> bool:
    """Excludes one-time trial cards (e.g. "Probe BahnCard") from the candidate space.

    Their introductory one-time price (``billing_cycle == "one_time"``) isn't a real
    ongoing annual cost, so it can't be fairly compared to what a year of holding an
    alternative subscription would actually cost.
    """
    return plan.get("billing_cycle") != "one_time"


def _plan_annual(plan: dict) -> float:
    """Annual cost of a catalog plan — prefer an explicit annual price, else 12x
    the monthly price."""
    annual = plan.get("annual_cost")
    if annual is not None:
        return float(annual)
    return float(plan.get("monthly_cost") or 0.0) * 12


def _simulate_consumption_annual_cost(
    plan: dict, legs: list[dict], months_of_data: float
) -> float | None:
    """Annualized pay-as-you-go cost of ``plan`` simulated leg-by-leg from each leg's
    actual distance/duration, for consumption-based plans (per-minute/per-km/
    per-km-and-time/hybrid) that carry a linear rate in the catalog (``per_km_eur``/
    ``per_hour_eur``/``per_minute_eur``). Returns ``None`` when none of those is set —
    e.g. a tiered plan like Lime Prime (a flat price per ride-duration *band*, not a
    linear rate) or a plan whose tariff doc gives no exploitable number at all (MILES
    Pass' "varies by tier", Bolt's bare pay-as-you-go with no published rate) — these
    stay "not comparable" rather than being approximated by a formula they don't
    actually follow.

    Legs are grouped by calendar day first so an optional ``daily_cap_eur`` (e.g. Call
    a Bike Starter's "max 13 EUR/day") caps each day's total before summing, instead of
    capping (or not capping) each leg independently.
    """
    per_km = plan.get("per_km_eur")
    per_hour = plan.get("per_hour_eur")
    per_minute = plan.get("per_minute_eur")
    if not any(v not in (None, 0, 0.0) for v in (per_km, per_hour, per_minute)):
        return None

    unlock = float(plan.get("unlock_fee_eur") or 0.0)
    per_km = float(per_km or 0.0)
    per_hour = float(per_hour or 0.0)
    per_minute = float(per_minute or 0.0)
    free_minutes = float(plan.get("free_minutes_included") or 0.0)
    daily_cap = plan.get("daily_cap_eur")
    daily_cap = float(daily_cap) if daily_cap not in (None, "") else None

    by_day: dict = defaultdict(float)
    for leg in legs:
        distance = leg.get("distance") or 0.0
        duration = leg.get("duration") or 0.0
        billed_minutes = max(0.0, duration - free_minutes)
        cost = unlock + per_km * distance + per_hour * (duration / 60.0) + per_minute * billed_minutes
        by_day[leg.get("day")] += cost

    total = sum(
        min(cost, daily_cap) if daily_cap is not None else cost
        for cost in by_day.values()
    )
    return round(total / months_of_data * 12, 2)


def _flat_or_discount_remainder(
    plan: dict, no_subscription_annual_cost: float
) -> tuple[float, str] | None:
    """Tiers 1-2 of ``_estimate_alternative_remainder``'s pricing hierarchy — the two
    tiers that need no per-leg data at all, so they're shared with the forecast-demand
    projection (see ``_estimate_projected_alternative_remainder``) which only ever has
    aggregate trip/km totals, never real legs.

    1. Flat-rate pass (``pricing_model == "flat_monthly"``) — remainder is 0.
    2. Recognized %-discount card (BahnCard 25/50/100, matched by name) — remainder is
       a fixed fraction of ``no_subscription_annual_cost`` (valid because both figures
       are denominated in the same fare basis: this category's own reference pricing).

    Returns ``None`` when neither tier applies.
    """
    if (plan.get("pricing_model") or "").lower() == "flat_monthly":
        return 0.0, "flat-rate pass (fully covered)"

    match = _BAHNCARD_DISCOUNT_RE.search(plan.get("name") or "")
    if match:
        pct = int(match.group(1))
        if 0 < pct <= 100:
            fraction = round(1 - pct / 100, 4)
            remainder = round(no_subscription_annual_cost * fraction, 2)
            return remainder, f"{pct}% discount card (estimated from plan name)"

    return None


def _estimate_alternative_remainder(
    plan: dict,
    no_subscription_annual_cost: float,
    category_legs: list[dict],
    months_of_data: float,
) -> tuple[float, str] | None:
    """The annualized pay-as-you-go remainder ``plan`` would leave the user paying —
    i.e. the part of ``estimated_annual_cost_eur`` not covered by the plan's own fixed
    price. Returns ``(annual_remainder_eur, basis_label)``, or ``None`` when the plan
    can't be honestly priced this way (surfaced as "not comparable" rather than
    silently guessed at). Three cases, in order of confidence — the first two via
    ``_flat_or_discount_remainder``, the third only reachable here since it needs real
    per-leg data:

    1. Flat-rate pass — remainder is 0.
    2. Recognized %-discount card — remainder is a fraction of ``no_subscription_annual_cost``.
    3. Linear consumption-based plan (a per-km/per-hour/per-minute rate is on file) —
       remainder is simulated leg-by-leg from ``category_legs``' actual distance/
       duration (see ``_simulate_consumption_annual_cost``), *not* derived as a
       fraction of a cost that was priced under a different provider's benchmark rate
       — car-/bike-sharing and e-scooter reference prices are anchored to one specific
       provider's PAYG rate, so a percentage of that number wouldn't mean anything for
       a different provider's own rate structure.

    Returns ``None`` for tiered or undocumented pricing that can't be honestly
    reconstructed from the catalog's structured fields.
    """
    result = _flat_or_discount_remainder(plan, no_subscription_annual_cost)
    if result is not None:
        return result

    simulated = _simulate_consumption_annual_cost(plan, category_legs, months_of_data)
    if simulated is not None:
        return simulated, "simulated from the plan's per-km/per-hour/per-minute rate on file"

    return None


def _active_subscriptions(current_subscriptions: list) -> dict:
    """Pure function of ``current_subscriptions`` — no travel_history dependency, so
    it can be reused by both the historical analysis and a forecast-demand projection
    without re-deriving anything from real trip legs.

    Returns a dict with ``annual_sub_cost``, ``active_subs_by_id``,
    ``active_categories``, ``current_contracts`` and ``held_subs_by_category`` (the
    last grouped independent of the >0-cost filter ``subscription_coverage`` applies —
    a €0 employer-sponsored sub should still count as "already held", not show up as a
    switchable alternative).
    """
    annual_sub_cost = 0.0
    active_subs_by_id: dict[str, dict] = {}
    active_categories: set[str] = set()
    current_contracts: list[str] = []
    held_subs_by_category: dict[str, list[dict]] = defaultdict(list)

    for sub in current_subscriptions:
        if sub.get("subscription_status") != "active":
            continue
        monthly = float(sub.get("monthly_cost_eur") or 0.0)
        annual = float(sub.get("annual_cost_eur") or 0.0) or monthly * 12
        annual_sub_cost += annual
        sub_id = sub.get("user_subscription_id")
        if sub_id:
            active_subs_by_id[sub_id] = {**sub, "_annual_cost": annual}
        category = (sub.get("subscription_category") or "").lower()
        if category:
            active_categories.add(category)
            held_subs_by_category[category].append({**sub, "_annual_cost": annual})
        name = sub.get("provider_plan_name") or sub.get("provider_name") or "Subscription"
        cost_label = f"€{monthly:.0f}/mo" if monthly else (f"€{annual:.0f}/yr" if annual else "")
        current_contracts.append(f"{name} ({cost_label})" if cost_label else name)

    return {
        "annual_sub_cost": annual_sub_cost,
        "active_subs_by_id": active_subs_by_id,
        "active_categories": active_categories,
        "current_contracts": current_contracts,
        "held_subs_by_category": held_subs_by_category,
    }


def _rank_alternatives(
    pricing_catalog: list[dict],
    db_category: str,
    plan_filter,
    user_age,
    held_ids: set,
    held_travel_class: int | None,
    no_subscription_annual_cost: float | None,
    remainder_fn,
    actual_annual_cost: float | None,
) -> tuple[list[dict], list[str]]:
    """Search ``pricing_catalog`` for this category's eligible alternatives, price
    each via ``remainder_fn(plan) -> (remainder_eur, basis_label) | None``, and rank
    them cheapest-first. Shared by the historical analysis (``remainder_fn`` bound to
    ``_estimate_alternative_remainder`` with real legs) and the forecast-demand
    projection (bound to ``_estimate_projected_alternative_remainder``, no legs) — the
    eligibility/travel-class filtering and ranking logic is identical either way, only
    how a plan's remainder gets priced differs.

    ``actual_annual_cost`` is what the customer is really paying today in this
    category — a real number whether or not they hold a subscription there (pure
    pay-as-you-go is still "what they're actually paying"). Only the forecast
    projection can leave it ``None`` (a currently-held metered plan whose cost can't
    be projected without duration data) — never withhold
    ``annual_savings_vs_current_eur`` just because no subscription is held; that's a
    real, known comparison either way.

    ``no_subscription_annual_cost`` may be ``None`` when the caller has no reference
    cost basis at all for this category (e.g. a forecast scenario introducing a mode
    with no historical rate to project from) — in that case there is nothing to rank
    alternatives against, so this returns ``([], [])`` rather than guessing.

    Returns ``(alternatives_sorted_by_cost, non_comparable_plan_names)``.
    """
    if no_subscription_annual_cost is None:
        return [], []

    alternatives = []
    non_comparable_alternatives = []
    for plan in pricing_catalog:
        if (plan.get("category") or "").lower() != db_category:
            continue
        if not plan_filter(plan.get("name")):
            continue
        if plan.get("id") in held_ids:
            continue
        if not _is_ongoing_candidate(plan) or not _is_eligible(plan, user_age):
            continue
        plan_class = _travel_class(plan.get("name"))
        # Default to a 2nd-class baseline when nothing is currently held (there's
        # no per-leg class evidence to fall back on otherwise) — never silently
        # compare a 1st-class card's price against fares that might be 2nd-class.
        if plan_class is not None and plan_class != (held_travel_class or 2):
            non_comparable_alternatives.append(plan.get("name"))
            continue
        pricing = remainder_fn(plan)
        if pricing is None:
            non_comparable_alternatives.append(plan.get("name"))
            continue
        pay_as_you_go_remainder, basis = pricing
        plan_annual_cost = round(_plan_annual(plan), 2)
        estimated_annual_cost = round(plan_annual_cost + pay_as_you_go_remainder, 2)
        alternatives.append({
            "provider_plan_name": plan.get("name"),
            "estimated_annual_cost_eur": estimated_annual_cost,
            "pricing_basis": basis,
            # Breakdown of how estimated_annual_cost_eur was derived: the plan's
            # own fixed price, plus whatever pay-as-you-go cost remains after its
            # discount (0 for a true flat-rate pass).
            "plan_annual_cost_eur": plan_annual_cost,
            "estimated_pay_as_you_go_remainder_eur": pay_as_you_go_remainder,
            "annual_savings_vs_no_subscription_eur": round(
                no_subscription_annual_cost - estimated_annual_cost, 2
            ),
            "annual_savings_vs_current_eur": (
                round(actual_annual_cost - estimated_annual_cost, 2)
                if actual_annual_cost is not None
                else None
            ),
        })
    alternatives.sort(key=lambda a: a["estimated_annual_cost_eur"])
    return alternatives, non_comparable_alternatives


def _pick_recommendation(
    actual_annual_cost: float | None,
    no_subscription_annual_cost: float | None,
    alternatives: list[dict],
    has_held_subs: bool,
    category_co2_kg: float | None,
    category_time_minutes: float | None,
    weights: dict[str, float],
) -> tuple[float | None, dict | None, dict | None, str]:
    """Pick the best of the three options — current setup, pure pay-as-you-go, and
    every priceable alternative (not just the cheapest) — by a weighted cost/CO2/time
    score (see ``scoring.pick_best_category_option``), rather than only checking the
    cheapest alternative against the current setup. Considering every alternative
    (not just the cheapest) matters once CO2/time can outweigh a small cost gap: a
    pricier-but-greener alternative can now win even when the cheapest one wouldn't.

    ``category_co2_kg``/``category_time_minutes`` are the SAME real, already-computed
    category totals applied to current/no-subscription/every alternative alike —
    switching which plan pays for this category's trips doesn't change which
    physical mode/trips those are, only the price. This is not a no-op: it's what
    keeps the score in the common case reducing to the historical pure-cost
    ranking (see scoring.py's module docstring on degenerate-range handling), while
    staying meaningful once real per-mode CO2/time variance exists (the
    cross-category modal-shift comparison in modal_shift.py uses this same primitive
    with genuinely different CO2/time per candidate).

    Any of the three costs may be ``None`` (unknown — only possible for the forecast
    projection, e.g. a currently-held metered plan whose cost can't be projected
    without duration data). A ``None`` cost simply can't win; if every cost is
    ``None``, the recommendation is ``"insufficient_cost_data"`` rather than silently
    defaulting to "keep current" with no actual number behind it.

    Returns ``(best_known_cost, winning_alternative, score_breakdown, recommendation)``.
    """
    current = (
        {
            "annual_cost_eur": actual_annual_cost,
            "annual_co2_kg": category_co2_kg,
            "annual_time_minutes": category_time_minutes,
        }
        if actual_annual_cost is not None else None
    )
    no_subscription = (
        {
            "annual_cost_eur": no_subscription_annual_cost,
            "annual_co2_kg": category_co2_kg,
            "annual_time_minutes": category_time_minutes,
        }
        if no_subscription_annual_cost is not None else None
    )
    scored_alternatives = [
        {
            "annual_cost_eur": alt["estimated_annual_cost_eur"],
            "annual_co2_kg": category_co2_kg,
            "annual_time_minutes": category_time_minutes,
            "_ref": alt,
        }
        for alt in alternatives
    ]

    result = pick_best_category_option(current, no_subscription, scored_alternatives, has_held_subs, weights)
    return (
        result["best_cost"],
        result["winning_alternative"],
        result["score_breakdown"],
        result["recommendation"],
    )


def _category_definitions() -> list[tuple]:
    """The 5 (key, db_category, mode_filter, plan_filter) combinations
    ``category_subscription_analysis`` iterates — factored out so the forecast-demand
    projection (``project_category_subscription_analysis``) uses the exact same
    category/mode/plan carve-up and the two can't silently drift apart. See the "8b."
    comment in ``analyze_portfolio`` for why public_transport/long_distance_rail split
    out of one shared DB category.
    """
    return [
        ("bike_sharing", "bike_sharing", lambda m: category_covers_mode("bike_sharing", m), lambda name: True),
        ("car_sharing", "car_sharing", lambda m: category_covers_mode("car_sharing", m), lambda name: True),
        ("e_scooter", "e_scooter", lambda m: category_covers_mode("e_scooter", m), lambda name: True),
        (
            "public_transport", "public_transport",
            lambda m: category_covers_mode("public_transport", m),
            lambda name: not _is_bahncard_plan(name),
        ),
        (
            _LONG_DISTANCE_RAIL_CATEGORY, "public_transport",
            lambda m: m == _LONG_DISTANCE_RAIL_MODE,
            _is_bahncard_plan,
        ),
    ]


def analyze_portfolio(
    travel_history: list,
    current_subscriptions: list,
    pricing_catalog: list | None = None,
    user_age: int | None = None,
    preferences: dict | None = None,
) -> dict:
    """
    Parameters
    ----------
    travel_history:
        List of trip_leg dicts from the DB (production column names, values
        already coerced by ``clean_row``).
    current_subscriptions:
        List of user_subscriptions rows joined to subscription_catalogs
        (production column names).
    pricing_catalog:
        List of subscription_catalogs rows (see agent/context.py), used only to
        evaluate untried alternatives per category in ``category_subscription_analysis``.
        Optional — omitting it just skips that section (no alternatives to compare).
    user_age:
        The user's age, for filtering out age-gated catalog plans they're not
        eligible for when proposing alternatives (e.g. a Senioren BahnCard for a
        30-year-old). ``None`` (unknown) doesn't exclude age-gated plans.
    preferences:
        ``schema_map.preferences_from_onboarding``'s output (``cost_priority``/
        ``co2_priority``/``convenience_priority``, 0-100), used to weight the
        keep/switch/cancel decision (see ``scoring.resolve_weights``). ``None``
        (or all-zero/unknown) falls back to an equal three-way weighting.

    Returns a dict with two logical sections:
    - Full output — usage stats, subscription value audit, and the per-category
      current-vs-alternative-vs-no-subscription comparison — stored in recommendations.
    - ``forecaster_summary`` — a nested dict already shaped to the
      AnalystSummary schema that ``forecast()`` in forecasting.py expects.
    """
    pricing_catalog = pricing_catalog or []
    preferences = preferences or {}
    weights = resolve_weights(
        preferences.get("cost_priority"),
        preferences.get("co2_priority"),
        preferences.get("convenience_priority"),
    )

    # ------------------------------------------------------------------ #
    # 1. Data window — capped to the last 12 months                      #
    # ------------------------------------------------------------------ #
    all_dates = [dt for leg in travel_history if (dt := _parse_dt(leg.get("started_at")))]

    if all_dates:
        date_max = max(all_dates)
        window_start = date_max - timedelta(days=365)
        travel_history = [
            leg for leg in travel_history
            if (dt := _parse_dt(leg.get("started_at"))) and dt >= window_start
        ]
        dates = [dt for leg in travel_history if (dt := _parse_dt(leg.get("started_at")))]
        date_min = min(dates)
        data_window_days = max((date_max - date_min).days, 1)
        analysis_period_start = date_min.date().isoformat()
        analysis_period_end = date_max.date().isoformat()
    else:
        data_window_days = 0
        analysis_period_start = analysis_period_end = ""

    months_of_data = max(data_window_days, 1) / 30.44
    data_warning = "too little data for reliable annualization" if data_window_days < 14 else None

    # ------------------------------------------------------------------ #
    # 2. Active subscriptions                                              #
    # ------------------------------------------------------------------ #
    _subs = _active_subscriptions(current_subscriptions)
    annual_sub_cost = _subs["annual_sub_cost"]
    active_subs_by_id = _subs["active_subs_by_id"]
    active_categories = _subs["active_categories"]
    current_contracts = _subs["current_contracts"]
    held_subs_by_category = _subs["held_subs_by_category"]

    # ------------------------------------------------------------------ #
    # 3. Per-leg aggregation                                               #
    # ------------------------------------------------------------------ #
    total_intrinsic = 0.0
    total_effective = 0.0
    total_distance = 0.0
    total_co2 = 0.0

    # raw_mode_stats: production transport_mode (for uncovered-category checks,
    # mode_breakdown, and dominant_patterns — every mode-keyed output reports the
    # raw production transport_mode individually, e.g. regional_train and
    # long_distance_train are never merged into one "train" figure)
    raw_mode_stats: dict[str, dict] = defaultdict(
        lambda: {
            "trips": 0, "intrinsic": 0.0, "effective": 0.0, "distance": 0.0, "co2": 0.0,
            "duration": 0.0,
        }
    )
    # sub_stats: per-subscription attribution, keyed by user_subscription_id.
    # Drives subscription_coverage directly from what each leg actually used,
    # rather than inferring coverage from category+mode. This correctly
    # distinguishes flat passes (paid €0) from discount cards like a BahnCard
    # (paid a reduced price) — both report a real "realized_savings" figure.
    sub_stats: dict[str, dict] = defaultdict(
        lambda: {"trips": 0, "reference": 0.0, "paid": 0.0, "distance": 0.0}
    )
    # monthly_total[(year, month)] = trip count (for seasonality)
    monthly_total: dict[tuple, int] = defaultdict(int)
    # monthly_mode_stats[(year, month)][raw_mode] = per-mode stats for that month.
    # Keyed on the raw production transport_mode (not group_mode()'s display bucket)
    # so regional_train and long_distance_train stay distinct in the monthly view,
    # for monthly_mode_breakdown below.
    monthly_mode_stats: dict[tuple, dict[str, dict]] = defaultdict(
        lambda: defaultdict(
            lambda: {"trips": 0, "intrinsic": 0.0, "effective": 0.0, "distance": 0.0, "co2": 0.0}
        )
    )
    # legs_by_raw_mode[raw_mode] = [{"distance", "duration", "day"}, ...] — the raw
    # per-leg inputs _simulate_consumption_annual_cost needs to price an untried
    # consumption-based alternative (a per-km/per-hour/per-minute rate can't be
    # applied to an aggregate total the way a flat-rate or %-discount card can; it
    # needs each leg's own distance/duration, and calendar day for daily-cap grouping).
    legs_by_raw_mode: dict[str, list[dict]] = defaultdict(list)

    for leg in travel_history:
        # reference_cost_eur is the pay-as-you-go price for this leg regardless
        # of any subscription held. Falls back to estimated_cost_eur for legs
        # that predate the field or where no subscription applies.
        intrinsic = float(
            leg.get("reference_cost_eur") or leg.get("estimated_cost_eur") or 0.0
        )
        paid = float(leg.get("estimated_cost_eur") or 0.0)
        dist = float(leg.get("estimated_distance_km") or 0.0)
        duration = float(leg.get("duration_minutes") or 0.0)
        co2 = float(leg.get("estimated_co2_emissions") or 0.0)
        raw_mode = (leg.get("transport_mode") or "other").lower()

        leg_sub_id = leg.get("user_subscription_id")
        attributed = leg_sub_id in active_subs_by_id
        effective = paid if attributed else intrinsic

        if attributed:
            st = sub_stats[leg_sub_id]
            st["trips"] += 1
            st["reference"] += intrinsic
            st["paid"] += paid
            st["distance"] += dist

        total_intrinsic += intrinsic
        total_effective += effective
        total_distance += dist
        total_co2 += co2

        raw_mode_stats[raw_mode]["trips"] += 1
        raw_mode_stats[raw_mode]["intrinsic"] += intrinsic
        raw_mode_stats[raw_mode]["effective"] += effective
        raw_mode_stats[raw_mode]["distance"] += dist
        raw_mode_stats[raw_mode]["co2"] += co2
        raw_mode_stats[raw_mode]["duration"] += duration

        dt = _parse_dt(leg.get("started_at"))
        legs_by_raw_mode[raw_mode].append({
            "distance": dist, "duration": duration, "day": dt.date() if dt else None,
        })
        if dt:
            monthly_total[(dt.year, dt.month)] += 1
            mst = monthly_mode_stats[(dt.year, dt.month)][raw_mode]
            mst["trips"] += 1
            mst["intrinsic"] += intrinsic
            mst["effective"] += effective
            mst["distance"] += dist
            mst["co2"] += co2

    total_trips = len(travel_history)

    # ------------------------------------------------------------------ #
    # 4. Mode breakdown                                                    #
    #                                                                      #
    # Keyed on the raw production transport_mode, same granularity as     #
    # dominant_patterns/monthly_mode_breakdown below — regional_train and  #
    # long_distance_train are reported as separate entries, never merged   #
    # into one "train" figure.                                            #
    #                                                                      #
    # All "_total" fields are sums over the last 12-month window.         #
    # "_per_month" fields are the average monthly rate over that window.  #
    # ------------------------------------------------------------------ #
    mode_breakdown: dict[str, dict] = {}
    for mode, st in raw_mode_stats.items():
        n = st["trips"]
        trips_pm = round(n / months_of_data, 2)
        avg_dist_per_trip = round(st["distance"] / max(n, 1), 2)
        mode_breakdown[mode] = {
            "trips": n,
            "trips_per_month": trips_pm,
            "distance_km": round(st["distance"], 2),
            "distance_km_per_month": round(st["distance"] / months_of_data, 2),
            "avg_distance_km_per_trip": avg_dist_per_trip,
            "co2_kg": round(st["co2"], 2),
            "co2_kg_per_month": round(st["co2"] / months_of_data, 2),
            "intrinsic_cost_eur": round(st["intrinsic"], 2),
            "effective_cost_eur": round(st["effective"], 2),
        }

    # ------------------------------------------------------------------ #
    # 4b. Monthly mode breakdown — same per-mode fields as mode_breakdown,#
    #     but split by calendar month over the 12-month window. Only     #
    #     modes actually used in a given month appear under it.          #
    # ------------------------------------------------------------------ #
    monthly_mode_breakdown: dict[str, dict] = {}
    for (year, month), stats_by_mode in sorted(monthly_mode_stats.items()):
        month_key = f"{year:04d}-{month:02d}"
        monthly_mode_breakdown[month_key] = {
            mode: {
                "trips": st["trips"],
                "distance_km": round(st["distance"], 2),
                "co2_kg": round(st["co2"], 2),
                "intrinsic_cost_eur": round(st["intrinsic"], 2),
                "effective_cost_eur": round(st["effective"], 2),
            }
            for mode, st in sorted(stats_by_mode.items())
        }

    # ------------------------------------------------------------------ #
    # 5. Dominant patterns (sorted by trips/month desc)                   #
    #    Same raw-mode granularity as mode_breakdown/monthly_mode_breakdown#
    #    above — regional_train and long_distance_train stay distinct     #
    #    patterns instead of being merged into one "train" figure.        #
    # ------------------------------------------------------------------ #
    dominant_patterns = sorted(
        [
            {
                "mode": mode,
                "avg_trips_per_month": round(st["trips"] / months_of_data, 2),
                "avg_distance_km": round(st["distance"] / max(st["trips"], 1), 2),
            }
            for mode, st in raw_mode_stats.items()
        ],
        key=lambda x: -x["avg_trips_per_month"],
    )

    # ------------------------------------------------------------------ #
    # 6. Seasonality detection (purely statistical)                        #
    # ------------------------------------------------------------------ #
    detected_seasonality = _detect_seasonality(monthly_total)

    # ------------------------------------------------------------------ #
    # 7. Subscription coverage vs. actual value (threshold-free math)     #
    #                                                                       #
    # Attribution is per-leg via user_subscription_id (set when a leg was   #
    # actually used with that subscription), not inferred from category+    #
    # mode. This means a flat pass (paid €0) and a discount card like a     #
    # BahnCard (paid a reduced price) both produce a correct                #
    # realized_savings_eur = reference_cost - amount_paid, annualized.      #
    # ------------------------------------------------------------------ #
    subscription_coverage = []
    for sub_id, sub in active_subs_by_id.items():
        category = (sub.get("subscription_category") or "").lower()
        plan_name = sub.get("provider_plan_name") or sub.get("provider_name", "")
        annual_cost = sub["_annual_cost"]
        if annual_cost <= 0:
            continue
        st = sub_stats.get(sub_id, {"trips": 0, "reference": 0.0, "paid": 0.0, "distance": 0.0})
        covered_value = round(st["reference"] / months_of_data * 12, 2)
        realized_savings = round((st["reference"] - st["paid"]) / months_of_data * 12, 2)
        net_savings = round(realized_savings - annual_cost, 2)
        subscription_coverage.append({
            "provider_plan_name": plan_name,
            # Reported category, not the raw DB one — a BahnCard is stored under
            # "public_transport" in subscription_catalogs but is long-distance-only
            # (see _display_category above), so it's relabeled here to match how
            # category_subscription_analysis (below) already splits the two.
            "subscription_category": _display_category(category, plan_name),
            "subscription_id": sub.get("subscription_id"),
            "annual_cost_eur": round(annual_cost, 2),
            "covered_value_eur": covered_value,
            "realized_savings_eur": realized_savings,
            "net_savings_eur": net_savings,
            "trips": st["trips"],
            "distance_km": round(st["distance"], 2),
        })

    # ------------------------------------------------------------------ #
    # 8. Per-category annualized stats.                                    #
    #                                                                      #
    # For each of the 4 subscribable categories, the annualized cost/CO2/  #
    # trip count of every leg whose raw mode falls under it — regardless   #
    # of whether the user currently holds a subscription there — plus the  #
    # annualized *effective* (actually paid) cost of those same legs. This  #
    # is the building block category_subscription_analysis (below) prices   #
    # every current/alternative/no-subscription comparison from, so those   #
    # numbers can't drift out of sync with this engine's 12-month window.   #
    #                                                                      #
    # Legs whose raw mode isn't covered by *any* of these 4 categories       #
    # (long-distance rail, car, taxi, walking, ...) go into                 #
    # uncategorized_annual_stats — except long_distance_train, which gets    #
    # its own analysis bucket below (see "8b."), not lumped in here.        #
    # ------------------------------------------------------------------ #
    def _category_annual_stats(mode_filter) -> dict:
        trips = intrinsic = effective = co2 = distance = duration = 0.0
        for raw_mode, st in raw_mode_stats.items():
            if mode_filter(raw_mode):
                trips += st["trips"]
                intrinsic += st["intrinsic"]
                effective += st["effective"]
                co2 += st["co2"]
                distance += st["distance"]
                duration += st["duration"]
        return {
            "annual_trips": round(trips / months_of_data * 12, 1),
            "annual_cost_eur": round(intrinsic / months_of_data * 12, 2),
            "annual_effective_cost_eur": round(effective / months_of_data * 12, 2),
            "annual_co2_kg": round(co2 / months_of_data * 12, 2),
            "annual_distance_km": round(distance / months_of_data * 12, 2),
            "annual_time_minutes": round(duration / months_of_data * 12, 1),
        }

    category_annual_stats = {
        cat: _category_annual_stats(lambda raw_mode, cat=cat: category_covers_mode(cat, raw_mode))
        for cat in _ALL_CATEGORIES
    }
    uncategorized_annual_stats = _category_annual_stats(
        lambda raw_mode: raw_mode != _LONG_DISTANCE_RAIL_MODE
        and not any(category_covers_mode(cat, raw_mode) for cat in _ALL_CATEGORIES)
    )

    # Uncovered spend (raw fact for the memo/UI, not a rec) — a view over
    # category_annual_stats restricted to categories with no active subscription.
    uncovered_spend_by_category: dict[str, float] = {}
    for cat in _ALL_CATEGORIES:
        if cat not in active_categories:
            annual_eur = category_annual_stats[cat]["annual_cost_eur"]
            if annual_eur > 0:
                uncovered_spend_by_category[cat] = annual_eur

    # ------------------------------------------------------------------ #
    # 8b. Per-category subscription verdict: current vs. cheapest priceable #
    # alternative vs. no subscription at all (pure pay-as-you-go) — all     #
    # three grounded in how the user actually traveled this window, never   #
    # in a hypothetical "holding any plan makes the category free" guess.   #
    #                                                                      #
    # actual_annual_cost_eur = what really happened: the annualized cost    #
    # of legs not attributed to a subscription (still their pay-as-you-go   #
    # price) plus whatever active subscription(s) are held in this bucket   #
    # (their fixed annual cost, regardless of the discount they apply per   #
    # leg — that discount already shows up in the legs' own effective cost).#
    #                                                                      #
    # "public_transport" is split into TWO independent buckets here, not     #
    # one: "public_transport" itself (local bus/tram + regional_train — a    #
    # Deutschlandticket-style flat pass) and "long_distance_rail"             #
    # (long_distance_train only — a BahnCard's territory). Both share the    #
    # same underlying DB category (subscription_catalogs has no separate      #
    # "long_distance_rail" row), so plans and held subscriptions are routed   #
    # into whichever bucket matches _is_bahncard_plan(name). This keeps the   #
    # two products independent — Deutschlandticket and a BahnCard are          #
    # complements a customer can hold *both* of, not mutually-exclusive        #
    # alternatives — and avoids double-counting regional_train, which stays   #
    # exclusively Deutschlandticket territory (a BahnCard's regional discount  #
    # is real, but only matters when nothing else already covers it for free; #
    # modeling that overlap correctly needs knowing which product covers a     #
    # given regional trip, so it's scoped out rather than guessed at).         #
    #                                                                      #
    # alternatives only ever includes plans _estimate_alternative_remainder() can    #
    # actually price (flat-rate passes, a recognized %-discount card, or a           #
    # consumption-based plan with a linear per-km/per-hour/per-minute rate on file)  #
    # — see that function's docstring for exactly which car-/bike-sharing/e-scooter  #
    # plans still can't be evaluated this way (tiered or undocumented pricing) and   #
    # land in non_comparable_alternatives instead. A BahnCard in a different travel  #
    # class than the one already held (or, with none held, any 1st-class      #
    # card) lands there too — see _TRAVEL_CLASS_RE above. The full ranked     #
    # list is exposed (not just the cheapest) so a rejected alternative like  #
    # "BahnCard 25" is visibly considered-and-rejected, not silently dropped, #
    # and each entry breaks its estimated_annual_cost_eur down into the       #
    # plan's own fixed price vs. the pay-as-you-go remainder it doesn't       #
    # cover, plus the savings that number implies against both pay-as-you-go  #
    # and whatever's currently held (see the alternatives.append(...) below). #
    # ------------------------------------------------------------------ #
    def _build_category_entry(key, db_category, mode_filter, plan_filter):
        stats = _category_annual_stats(mode_filter)
        if stats["annual_trips"] <= 0:
            return None  # nothing to evaluate — no trips in this bucket this window

        no_subscription_annual_cost = stats["annual_cost_eur"]
        # Raw per-leg distance/duration/day for this bucket's modes — the input
        # _simulate_consumption_annual_cost needs to price a consumption-based
        # alternative (see _estimate_alternative_remainder below).
        category_legs = [
            leg for raw_mode, legs in legs_by_raw_mode.items() if mode_filter(raw_mode)
            for leg in legs
        ]
        held_subs = [
            s for s in held_subs_by_category.get(db_category, [])
            if plan_filter(s.get("provider_plan_name"))
        ]
        held_ids = {s.get("subscription_id") for s in held_subs if s.get("subscription_id")}
        held_annual_cost = sum(s["_annual_cost"] for s in held_subs)
        actual_annual_cost = round(stats["annual_effective_cost_eur"] + held_annual_cost, 2)

        current_subscriptions_detail = [
            {
                "provider_plan_name": cov["provider_plan_name"],
                "annual_cost_eur": cov["annual_cost_eur"],
                "annual_net_savings_eur": cov["net_savings_eur"],
            }
            for cov in subscription_coverage
            # subscription_coverage's category is the *display* category (see
            # _display_category) — matches "key" here, not the raw db_category both
            # buckets share (public_transport and long_distance_rail both come from
            # the same DB row, so plan_filter alone can't disambiguate against the
            # raw category).
            if cov["subscription_category"] == key and plan_filter(cov["provider_plan_name"])
        ]

        # The class a currently-held BahnCard (if any) is already anchored to — see
        # _TRAVEL_CLASS_RE above for why this is the only reliable class baseline we
        # have. None if nothing held here, or what's held has no class distinction.
        held_travel_class = next(
            (tc for s in held_subs if (tc := _travel_class(s.get("provider_plan_name"))) is not None),
            None,
        )

        alternatives, non_comparable_alternatives = _rank_alternatives(
            pricing_catalog, db_category, plan_filter, user_age, held_ids, held_travel_class,
            no_subscription_annual_cost,
            lambda plan: _estimate_alternative_remainder(
                plan, no_subscription_annual_cost, category_legs, months_of_data
            ),
            actual_annual_cost,
        )
        cheapest_alternative = alternatives[0] if alternatives else None

        _, winning_alternative, score_breakdown, recommendation = _pick_recommendation(
            actual_annual_cost, no_subscription_annual_cost, alternatives, bool(held_subs),
            stats["annual_co2_kg"], stats["annual_time_minutes"], weights,
        )

        return {
            "category": key,
            "annual_trips": stats["annual_trips"],
            "no_subscription_annual_cost_eur": no_subscription_annual_cost,
            "actual_annual_cost_eur": actual_annual_cost,
            "annual_co2_kg": stats["annual_co2_kg"],
            "annual_time_minutes": stats["annual_time_minutes"],
            "annual_distance_km": stats["annual_distance_km"],
            "applies_to_modes": sorted(m for m in raw_mode_stats if mode_filter(m)),
            "current_subscriptions": current_subscriptions_detail,
            # Full ranked comparison (cheapest first) — cheapest_alternative is just
            # alternatives[0], kept alongside for transparency/the "all alternatives"
            # table even though it may not be the plan actually recommended (see
            # recommended_alternative — the multi-criteria scoring winner, which
            # every switch_to_alternative/consider_subscribing recommendation and the
            # memo now refer to).
            "alternatives": alternatives,
            "cheapest_alternative": cheapest_alternative,
            "recommended_alternative": winning_alternative,
            "non_comparable_alternatives": non_comparable_alternatives,
            "recommendation": recommendation,
            "score_breakdown": score_breakdown,
        }

    category_subscription_analysis = []
    for key, db_category, mode_filter, plan_filter in _category_definitions():
        entry = _build_category_entry(key, db_category, mode_filter, plan_filter)
        if entry:
            category_subscription_analysis.append(entry)

    # ------------------------------------------------------------------ #
    # 9. Inefficiencies — only when math is unambiguous                   #
    # ------------------------------------------------------------------ #
    inefficiencies = []
    savings_potential = 0.0

    for cov in subscription_coverage:
        if cov["net_savings_eur"] < 0:
            waste = abs(cov["net_savings_eur"])
            inefficiencies.append({
                "type": "overpaid_subscription",
                "service": cov["provider_plan_name"],
                "annual_waste_eur": round(waste, 2),
                # kept for backward compat (communicator reads "annual_waste")
                "annual_waste": round(waste, 2),
                "details": (
                    f"{cov['provider_plan_name']} costs €{cov['annual_cost_eur']:.2f}/year "
                    f"but only saved €{cov['realized_savings_eur']:.2f}/year versus paying "
                    f"pay-as-you-go on the trips it was used for — a net overpayment of "
                    f"€{waste:.2f}/year."
                ),
            })
            savings_potential += waste

    # ------------------------------------------------------------------ #
    # 10. Forecaster summary (matches AnalystSummary in forecaster.py)    #
    # ------------------------------------------------------------------ #
    forecaster_summary = {
        "dominant_patterns": dominant_patterns,
        "detected_seasonality": detected_seasonality,
        "current_contracts": current_contracts,
        "monthly_mode_breakdown": monthly_mode_breakdown,
    }

    current_annual_spend = round(total_effective + annual_sub_cost, 2)

    return {
        # Data window
        "data_window_days": data_window_days,
        "months_of_data": round(months_of_data, 2),
        "analysis_period_start": analysis_period_start,
        "analysis_period_end": analysis_period_end,
        "data_warning": data_warning,
        # Aggregates (sums over the last-12-month window)
        "total_trips": total_trips,
        "total_distance_km": round(total_distance, 2),
        "total_co2_kg": round(total_co2, 2),
        "total_intrinsic_spend_eur": round(total_intrinsic, 2),
        "total_effective_spend_eur": round(total_effective, 2),
        "subscription_costs_annual_eur": round(annual_sub_cost, 2),
        "current_annual_spend_eur": current_annual_spend,
        # Breakdowns
        "mode_breakdown": mode_breakdown,
        "monthly_mode_breakdown": monthly_mode_breakdown,
        "subscription_coverage": subscription_coverage,
        "uncovered_spend_by_category": uncovered_spend_by_category,
        # Per-category annualized cost/CO2/trips (building blocks)
        "category_annual_stats": category_annual_stats,
        "uncategorized_annual_stats": uncategorized_annual_stats,
        # Per-category current-vs-alternative-vs-no-subscription verdict
        "category_subscription_analysis": category_subscription_analysis,
        # Patterns
        "dominant_patterns": dominant_patterns,
        "detected_seasonality": detected_seasonality,
        # Inefficiencies
        "inefficiencies": inefficiencies,
        "savings_potential_estimate_eur": round(savings_potential, 2),
        # Forecaster-ready summary (consumed by forecast() via pipeline.py)
        "forecaster_summary": forecaster_summary,
    }


# --------------------------------------------------------------------------- #
# Forecast-demand cost projection                                             #
#                                                                              #
# The same current-vs-alternative-vs-no-subscription comparison as             #
# category_subscription_analysis above, but computed from a forecast          #
# scenario's *projected* demand (see forecasting.py's PredictedDemand)        #
# instead of real travel_history. forecast() itself never touches money — it  #
# only predicts trips/km per mode — so all cost math here stays deterministic #
# and lives next to the analysis it mirrors, invoked as a separate pipeline   #
# step (see attach_projected_category_analysis) after both analyze_portfolio  #
# and forecast() have run.                                                   #
#                                                                              #
# PredictedDemand carries no per-leg duration or per-day distribution (by      #
# design — see forecasting.py's module docstring), so a catalog plan billed   #
# by duration (per_hour_eur/per_minute_eur) or with a daily_cap_eur can't be   #
# honestly simulated here the way _simulate_consumption_annual_cost does for   #
# real legs — those land in non_comparable_alternatives instead of being       #
# guessed at with an assumed duration. Only flat-rate passes, recognized       #
# %-discount cards, and plans with a pure uncapped per_km_eur rate are         #
# projectable — see _estimate_projected_alternative_remainder.                #
# --------------------------------------------------------------------------- #

def implied_rate_by_mode(mode_breakdown: dict) -> dict[str, tuple[float, str]]:
    """mode -> (rate, basis) where basis is "per_km" or "per_trip", implied from real
    historical mode_breakdown figures (intrinsic_cost_eur / distance_km, falling back
    to /trips for a mode with no meaningful distance signal). Modes absent from
    mode_breakdown (never used historically) are absent from the returned dict
    entirely — callers must treat that as "no cost basis to project from", not "$0
    to travel this much". Not underscore-prefixed: also imported by modal_shift.py
    to price a hypothetical cross-category candidate off the same real historical
    rate, rather than inventing a second pricing formula.
    """
    rates: dict[str, tuple[float, str]] = {}
    for mode, st in mode_breakdown.items():
        distance_km = st.get("distance_km") or 0.0
        trips = st.get("trips") or 0
        cost = st.get("intrinsic_cost_eur") or 0.0
        if distance_km > 0:
            rates[mode] = (cost / distance_km, "per_km")
        elif trips > 0:
            rates[mode] = (cost / trips, "per_trip")
    return rates


def _estimate_projected_alternative_remainder(
    plan: dict,
    no_subscription_annual_cost: float,
    projected_annual_trips: float,
    projected_annual_km: float,
) -> tuple[float, str] | None:
    """Forecast-projection analogue of ``_estimate_alternative_remainder``. Shares the
    flat-rate/%-discount tiers via ``_flat_or_discount_remainder`` — neither needs
    per-leg data. The third tier is narrower than the historical version: only a plan
    with a pure, uncapped per-km rate (``per_km_eur`` set, ``per_hour_eur``/
    ``per_minute_eur`` unset, no ``daily_cap_eur``) can be honestly priced from an
    annual trips/km total alone — a duration-billed or daily-capped plan needs data a
    forecast scenario doesn't have (see module note above) and returns ``None``
    ("not comparable") here rather than being simulated with a guessed duration.
    """
    result = _flat_or_discount_remainder(plan, no_subscription_annual_cost)
    if result is not None:
        return result

    per_km = plan.get("per_km_eur")
    has_duration_component = any(
        v not in (None, 0, 0.0) for v in (plan.get("per_hour_eur"), plan.get("per_minute_eur"))
    )
    has_daily_cap = plan.get("daily_cap_eur") not in (None, "")
    if per_km in (None, 0, 0.0) or has_duration_component or has_daily_cap:
        return None

    unlock = float(plan.get("unlock_fee_eur") or 0.0)
    remainder = unlock * projected_annual_trips + float(per_km) * projected_annual_km
    return (
        round(remainder, 2),
        "projected from the plan's per-km rate on file, applied to this scenario's forecasted annual km/trips",
    )


def project_category_subscription_analysis(
    predicted_demand: list,
    forecast_horizon_days: int,
    mode_breakdown: dict,
    current_subscriptions: list,
    pricing_catalog: list | None = None,
    user_age: int | None = None,
    preferences: dict | None = None,
) -> list[dict]:
    """Forecast-scenario analogue of ``category_subscription_analysis``: the same
    current-vs-alternative-vs-no-subscription comparison, computed from one forecast
    scenario's projected demand (a list of ``{"mode", "estimated_trips",
    "estimated_km", ...}`` dicts, i.e. one scenario's ``predicted_demand``) instead of
    real ``travel_history``.

    Every total is rescaled to a 365-day-equivalent annual figure (regardless of
    ``forecast_horizon_days``) so it's directly comparable to the historical
    ``category_subscription_analysis`` — that comparability is the entire point of
    this function existing.

    See the module note above for exactly which catalog plans can be projected this
    way; anything that can't lands in ``non_comparable_alternatives`` with a reason,
    never silently mispriced.

    ``preferences``: same as ``analyze_portfolio``'s — weights the projected
    keep/switch/cancel verdict the same way, so a forecast scenario can't recommend
    something the historical analysis wouldn't under the same preferences.
    """
    pricing_catalog = pricing_catalog or []
    preferences = preferences or {}
    weights = resolve_weights(
        preferences.get("cost_priority"),
        preferences.get("co2_priority"),
        preferences.get("convenience_priority"),
    )
    horizon_days = forecast_horizon_days or 365
    annual_factor = 365.0 / horizon_days

    # held_subs entries carry the user_subscriptions record's own field names
    # (provider_plan_name, monthly_cost_eur, ...), not the pricing_catalog plan
    # shape (pricing_model, name, per_km_eur, ...) that
    # _estimate_projected_alternative_remainder expects — resolve each held sub to
    # its catalog row (by subscription_id == catalog id) before pricing it, or a
    # flat-rate pass like the Deutschlandticket would wrongly come back
    # unprojectable (neither field name matches, so every tier of
    # _flat_or_discount_remainder falls through to None).
    catalog_by_id = {p.get("id"): p for p in pricing_catalog if p.get("id")}

    held_subs_by_category = _active_subscriptions(current_subscriptions)["held_subs_by_category"]
    rates = implied_rate_by_mode(mode_breakdown)
    demand_by_mode = {d["mode"]: d for d in predicted_demand if d.get("mode")}

    projected_category_analysis = []
    for key, db_category, mode_filter, plan_filter in _category_definitions():
        matching_modes = sorted(m for m in demand_by_mode if mode_filter(m))
        projected_trips = sum(
            (demand_by_mode[m].get("estimated_trips") or 0) for m in matching_modes
        ) * annual_factor
        projected_km = sum(
            (demand_by_mode[m].get("estimated_km") or 0) for m in matching_modes
        ) * annual_factor
        if projected_trips <= 0:
            continue

        # Projected CO2/time from mode_factors' distance-based estimate, applied to
        # this scenario's own projected per-mode trips/km — the same estimation
        # model modal_shift.py uses for a hypothetical mode, here applied to a
        # hypothetical *future* volume on already-used modes instead. co2/time are
        # None (not guessed at) when any matching mode isn't in mode_factors' tables.
        category_co2_kg = 0.0
        category_time_minutes = 0.0
        co2_computable = True
        time_computable = True
        for m in matching_modes:
            mode_trips = (demand_by_mode[m].get("estimated_trips") or 0) * annual_factor
            mode_km = (demand_by_mode[m].get("estimated_km") or 0) * annual_factor
            if mode_trips <= 0:
                continue
            mode_co2 = mode_factors.estimate_co2_kg(m, mode_km)
            if mode_co2 is None:
                co2_computable = False
            else:
                category_co2_kg += mode_co2
            per_trip_minutes = mode_factors.estimate_time_minutes(m, mode_km / mode_trips)
            if per_trip_minutes is None:
                time_computable = False
            else:
                category_time_minutes += per_trip_minutes * mode_trips
        category_co2_kg = round(category_co2_kg, 2) if co2_computable else None
        category_time_minutes = round(category_time_minutes, 1) if time_computable else None

        no_subscription_annual_cost = 0.0
        modes_without_rate = []
        priced_any_mode = False
        for m in matching_modes:
            mode_trips = (demand_by_mode[m].get("estimated_trips") or 0) * annual_factor
            mode_km = (demand_by_mode[m].get("estimated_km") or 0) * annual_factor
            if mode_trips <= 0:
                continue
            rate = rates.get(m)
            if rate is None:
                modes_without_rate.append(m)
                continue
            value, basis = rate
            no_subscription_annual_cost += value * (mode_km if basis == "per_km" else mode_trips)
            priced_any_mode = True
        no_subscription_annual_cost = round(no_subscription_annual_cost, 2) if priced_any_mode else None
        incomplete_cost_basis = bool(modes_without_rate)

        held_subs = [
            s for s in held_subs_by_category.get(db_category, [])
            if plan_filter(s.get("provider_plan_name"))
        ]
        held_ids = {s.get("subscription_id") for s in held_subs if s.get("subscription_id")}
        held_travel_class = next(
            (tc for s in held_subs if (tc := _travel_class(s.get("provider_plan_name"))) is not None),
            None,
        )

        # Price the currently-held subscription(s) the same way an alternative would
        # be priced — there's no real per-leg "effective cost" to sum for future
        # trips, so the held plan's projected cost has to come from the same
        # remainder-estimation logic as any other candidate plan.
        current_subscriptions_detail = []
        actual_annual_cost = None
        actual_annual_cost_note = None
        if not held_subs:
            actual_annual_cost = no_subscription_annual_cost
        elif no_subscription_annual_cost is None:
            actual_annual_cost_note = (
                "no historical €/km or €/trip rate for at least one forecasted mode in this "
                "category, so the held plan's projected cost can't be anchored to a reference cost"
            )
            for s in held_subs:
                current_subscriptions_detail.append({
                    "provider_plan_name": s.get("provider_plan_name") or s.get("provider_name"),
                    "annual_cost_eur": round(s["_annual_cost"], 2),
                    "projected_annual_net_savings_eur": None,
                })
        else:
            held_total = 0.0
            all_priced = True
            for s in held_subs:
                sub_annual = s["_annual_cost"]
                catalog_plan = catalog_by_id.get(s.get("subscription_id"))
                remainder = (
                    _estimate_projected_alternative_remainder(
                        catalog_plan, no_subscription_annual_cost, projected_trips, projected_km
                    )
                    if catalog_plan is not None else None
                )
                if remainder is None:
                    all_priced = False
                    current_subscriptions_detail.append({
                        "provider_plan_name": s.get("provider_plan_name") or s.get("provider_name"),
                        "annual_cost_eur": round(sub_annual, 2),
                        "projected_annual_net_savings_eur": None,
                    })
                    continue
                remainder_eur, _basis = remainder
                projected_cost = round(sub_annual + remainder_eur, 2)
                held_total += projected_cost
                current_subscriptions_detail.append({
                    "provider_plan_name": s.get("provider_plan_name") or s.get("provider_name"),
                    "annual_cost_eur": round(sub_annual, 2),
                    "projected_annual_net_savings_eur": round(no_subscription_annual_cost - projected_cost, 2),
                })
            if all_priced:
                actual_annual_cost = round(held_total, 2)
            else:
                actual_annual_cost_note = (
                    "currently-held plan's pricing model needs duration/day data this "
                    "scenario doesn't forecast"
                )

        alternatives, non_comparable_alternatives = _rank_alternatives(
            pricing_catalog, db_category, plan_filter, user_age, held_ids, held_travel_class,
            no_subscription_annual_cost,
            lambda plan: _estimate_projected_alternative_remainder(
                plan, no_subscription_annual_cost, projected_trips, projected_km
            ),
            actual_annual_cost,
        )
        cheapest_alternative = alternatives[0] if alternatives else None

        _, winning_alternative, score_breakdown, recommendation = _pick_recommendation(
            actual_annual_cost, no_subscription_annual_cost, alternatives, bool(held_subs),
            category_co2_kg, category_time_minutes, weights,
        )

        projected_category_analysis.append({
            "category": key,
            "annual_trips": round(projected_trips, 1),
            "annual_distance_km": round(projected_km, 2),
            "annual_co2_kg": category_co2_kg,
            "annual_time_minutes": category_time_minutes,
            "no_subscription_annual_cost_eur": no_subscription_annual_cost,
            "actual_annual_cost_eur": actual_annual_cost,
            "actual_annual_cost_note": actual_annual_cost_note,
            "applies_to_modes": matching_modes,
            "current_subscriptions": current_subscriptions_detail,
            "alternatives": alternatives,
            "cheapest_alternative": cheapest_alternative,
            "recommended_alternative": winning_alternative,
            "non_comparable_alternatives": non_comparable_alternatives,
            "recommendation": recommendation,
            "score_breakdown": score_breakdown,
            "pricing_basis_note": (
                "Costs projected from this scenario's forecasted trips/km using historical "
                "€/km (or €/trip) rates per mode observed in the last 12 months — not measured "
                "spend. Plans billed by duration or with a daily cap can't be projected this way "
                "and are listed under non_comparable_alternatives instead."
            ),
            "incomplete_cost_basis": incomplete_cost_basis,
            "modes_without_historical_rate": modes_without_rate,
            "forecast_horizon_days": forecast_horizon_days,
        })

    return projected_category_analysis


def attach_projected_category_analysis(
    forecaster_out: dict,
    mode_breakdown: dict,
    current_subscriptions: list,
    pricing_catalog: list | None,
    user_age: int | None,
    preferences: dict | None = None,
) -> None:
    """Mutates ``forecaster_out["scenarios"]`` in place, adding
    ``projected_category_analysis`` to each scenario — the forecast-demand analogue of
    ``category_subscription_analysis``. Best-effort per scenario: a malformed/partial
    scenario (e.g. missing ``predicted_demand``) must not break the whole pipeline, so
    a failure is logged and that scenario's field is set to an empty list rather than
    raising.
    """
    horizon = forecaster_out.get("forecast_horizon_days", 365)
    for scenario in forecaster_out.get("scenarios", []):
        try:
            scenario["projected_category_analysis"] = project_category_subscription_analysis(
                scenario.get("predicted_demand", []),
                horizon, mode_breakdown, current_subscriptions, pricing_catalog, user_age,
                preferences=preferences,
            )
        except Exception:
            logger.exception(
                "Projected category-cost analysis failed for scenario %r", scenario.get("label")
            )
            scenario["projected_category_analysis"] = []


def _detect_seasonality(monthly_total: dict[tuple, int]) -> str:
    if len(monthly_total) < 3:
        return "insufficient data for seasonality detection"

    # Average trips per calendar month across all years in the data
    by_cal_month: dict[int, list[int]] = defaultdict(list)
    for (_, month), count in monthly_total.items():
        by_cal_month[month].append(count)

    avg_by_cal_month = {m: sum(v) / len(v) for m, v in by_cal_month.items()}
    overall_avg = sum(avg_by_cal_month.values()) / len(avg_by_cal_month)

    if overall_avg == 0:
        return "no trips recorded"

    peak_month = max(avg_by_cal_month, key=avg_by_cal_month.get)
    trough_month = min(avg_by_cal_month, key=avg_by_cal_month.get)
    peak_ratio = avg_by_cal_month[peak_month] / overall_avg
    trough_ratio = avg_by_cal_month[trough_month] / overall_avg

    if peak_ratio < 1.2 and trough_ratio > 0.8:
        return "no significant seasonal variation detected"

    parts = []
    if peak_ratio >= 1.2:
        parts.append(
            f"peak travel in {_MONTH_NAMES[peak_month]} ({peak_ratio:.1f}× monthly average)"
        )
    if trough_ratio <= 0.8:
        parts.append(
            f"lowest activity in {_MONTH_NAMES[trough_month]} ({trough_ratio:.1f}× monthly average)"
        )
    return "; ".join(parts)