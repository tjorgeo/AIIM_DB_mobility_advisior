"""Deterministic mobility analyst agent.

Ingests leg-level travel history and active subscription records, computes
factual usage statistics, detects temporal patterns, and produces a structured
summary. No LLM, no hardcoded thresholds — inefficiencies are flagged only
when the math is unambiguous (e.g. a subscription cost more than it saved).

It also evaluates, per travel category, whether the currently-held subscription
(if any), a cheaper catalog alternative, or no subscription at all (pure
pay-as-you-go) would have been cheapest for how the user actually traveled —
see ``category_subscription_analysis`` in :func:`analyze_portfolio`'s return
value and ``_pricing_basis`` for exactly which catalog plans can be priced this
way and which can't.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta

from agent.schema_map import group_mode, category_covers_mode


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


def _pricing_basis(plan: dict) -> tuple[float, str] | None:
    """How confidently we can price ``plan``'s effect on a leg's cost.

    Returns ``(fraction_of_intrinsic_still_paid, basis_label)``: 0.0 for a true
    flat-rate pass (``pricing_model == "flat_monthly"`` — the trip costs nothing),
    or ``1 - discount`` for a recognized percentage-discount card (BahnCard 25/50/100,
    matched by name). Returns ``None`` for everything else — car-/bike-sharing and
    e-scooter plans are almost all consumption-based (per-minute/per-km/hybrid) and
    the catalog has no per-unit rate field, only prose tariff docs, so we cannot
    honestly simulate what an untried plan like that would have cost on a specific
    historical leg. Plans this returns ``None`` for are surfaced as "not comparable"
    rather than silently guessed at.
    """
    if (plan.get("pricing_model") or "").lower() == "flat_monthly":
        return 0.0, "flat-rate pass (fully covered)"
    match = _BAHNCARD_DISCOUNT_RE.search(plan.get("name") or "")
    if match:
        pct = int(match.group(1))
        if 0 < pct <= 100:
            return round(1 - pct / 100, 4), f"{pct}% discount card (estimated from plan name)"
    return None


def analyze_portfolio(
    travel_history: list,
    current_subscriptions: list,
    pricing_catalog: list | None = None,
    user_age: int | None = None,
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

    Returns a dict with two logical sections:
    - Full output — usage stats, subscription value audit, and the per-category
      current-vs-alternative-vs-no-subscription comparison — stored in recommendations.
    - ``forecaster_summary`` — a nested dict already shaped to the
      AnalystSummary schema that ``forecast()`` in forecasting.py expects.
    """
    pricing_catalog = pricing_catalog or []

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
    annual_sub_cost = 0.0
    active_subs_by_id: dict[str, dict] = {}
    active_categories: set[str] = set()
    current_contracts: list[str] = []
    # Active subs grouped by category — used by category_subscription_analysis to
    # know which catalog plans are already held (so they're never re-offered as an
    # "alternative") and their combined annual cost, independent of the >0-cost
    # filter subscription_coverage below applies (a €0 employer-sponsored sub should
    # still count as "already held", not show up as a switchable alternative).
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

    # ------------------------------------------------------------------ #
    # 3. Per-leg aggregation                                               #
    # ------------------------------------------------------------------ #
    total_intrinsic = 0.0
    total_effective = 0.0
    total_distance = 0.0
    total_co2 = 0.0

    # raw_mode_stats: production transport_mode (for uncovered-category checks)
    raw_mode_stats: dict[str, dict] = defaultdict(
        lambda: {"trips": 0, "intrinsic": 0.0, "effective": 0.0, "distance": 0.0, "co2": 0.0}
    )
    # disp_mode_stats: grouped display mode (for mode_breakdown output)
    disp_mode_stats: dict[str, dict] = defaultdict(
        lambda: {"trips": 0, "intrinsic": 0.0, "effective": 0.0, "distance": 0.0, "co2": 0.0}
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

    for leg in travel_history:
        # reference_cost_eur is the pay-as-you-go price for this leg regardless
        # of any subscription held. Falls back to estimated_cost_eur for legs
        # that predate the field or where no subscription applies.
        intrinsic = float(
            leg.get("reference_cost_eur") or leg.get("estimated_cost_eur") or 0.0
        )
        paid = float(leg.get("estimated_cost_eur") or 0.0)
        dist = float(leg.get("estimated_distance_km") or 0.0)
        co2 = float(leg.get("estimated_co2_emissions") or 0.0)
        raw_mode = (leg.get("transport_mode") or "other").lower()
        disp = group_mode(raw_mode)

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

        disp_mode_stats[disp]["trips"] += 1
        disp_mode_stats[disp]["intrinsic"] += intrinsic
        disp_mode_stats[disp]["effective"] += effective
        disp_mode_stats[disp]["distance"] += dist
        disp_mode_stats[disp]["co2"] += co2

        dt = _parse_dt(leg.get("started_at"))
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
    # All "_total" fields are sums over the last 12-month window.         #
    # "_per_month" fields are the average monthly rate over that window.  #
    # ------------------------------------------------------------------ #
    mode_breakdown: dict[str, dict] = {}
    for mode, st in disp_mode_stats.items():
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
    #     but split by calendar month over the 12-month window, keyed on #
    #     the raw production transport_mode (regional_train and          #
    #     long_distance_train stay distinct here, unlike mode_breakdown).#
    #     Only modes actually used in a given month appear under it.     #
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
    #    Keyed on the raw production transport_mode (not group_mode()'s   #
    #    display bucket) so e.g. regional_train and long_distance_train   #
    #    are reported as separate patterns instead of merged into "train".#
    #    mode_breakdown above stays grouped — the frontend's TravelModes  #
    #    component reads it and expects those display buckets.           #
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
        trips = intrinsic = effective = co2 = distance = 0.0
        for raw_mode, st in raw_mode_stats.items():
            if mode_filter(raw_mode):
                trips += st["trips"]
                intrinsic += st["intrinsic"]
                effective += st["effective"]
                co2 += st["co2"]
                distance += st["distance"]
        return {
            "annual_trips": round(trips / months_of_data * 12, 1),
            "annual_cost_eur": round(intrinsic / months_of_data * 12, 2),
            "annual_effective_cost_eur": round(effective / months_of_data * 12, 2),
            "annual_co2_kg": round(co2 / months_of_data * 12, 2),
            "annual_distance_km": round(distance / months_of_data * 12, 2),
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
    # alternatives only ever includes plans _pricing_basis() can actually    #
    # price (flat-rate passes, or a recognized %-discount card) — see that   #
    # function's docstring for exactly why most car-/bike-sharing and        #
    # e-scooter plans can't be evaluated this way and land in                #
    # non_comparable_alternatives instead. A BahnCard in a different travel   #
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
            pricing = _pricing_basis(plan)
            if pricing is None:
                non_comparable_alternatives.append(plan.get("name"))
                continue
            multiplier, basis = pricing
            plan_annual_cost = round(_plan_annual(plan), 2)
            pay_as_you_go_remainder = round(no_subscription_annual_cost * multiplier, 2)
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
                    round(actual_annual_cost - estimated_annual_cost, 2) if held_subs else None
                ),
            })
        alternatives.sort(key=lambda a: a["estimated_annual_cost_eur"])
        cheapest_alternative = alternatives[0] if alternatives else None

        # Pick the genuinely cheapest of the three options — current setup, pure
        # pay-as-you-go, and the cheapest priceable alternative — rather than only
        # checking the alternative against the current setup. Without this, a case
        # where pay-as-you-go actually beats *both* the current subscription and the
        # best alternative would still recommend switching to that (pricier-than-payg)
        # alternative instead of dropping subscriptions in this bucket entirely.
        best_cost = actual_annual_cost
        recommendation = "keep_current" if held_subs else "no_subscription_needed"

        if no_subscription_annual_cost < best_cost:
            best_cost = no_subscription_annual_cost
            recommendation = "cancel_current_go_pay_as_you_go" if held_subs else "no_subscription_needed"

        if cheapest_alternative and cheapest_alternative["estimated_annual_cost_eur"] < best_cost:
            recommendation = "switch_to_alternative" if held_subs else "consider_subscribing"

        return {
            "category": key,
            "annual_trips": stats["annual_trips"],
            "no_subscription_annual_cost_eur": no_subscription_annual_cost,
            "actual_annual_cost_eur": actual_annual_cost,
            "applies_to_modes": sorted(m for m in raw_mode_stats if mode_filter(m)),
            "current_subscriptions": current_subscriptions_detail,
            # Full ranked comparison (cheapest first) — cheapest_alternative is just
            # alternatives[0], kept alongside for convenience since most callers only
            # care about the winner.
            "alternatives": alternatives,
            "cheapest_alternative": cheapest_alternative,
            "non_comparable_alternatives": non_comparable_alternatives,
            "recommendation": recommendation,
        }

    category_subscription_analysis = []
    for cat in sorted(_ALL_CATEGORIES):
        if cat == "public_transport":
            entry = _build_category_entry(
                "public_transport", "public_transport",
                lambda m: category_covers_mode("public_transport", m),
                lambda name: not _is_bahncard_plan(name),
            )
            if entry:
                category_subscription_analysis.append(entry)
            entry = _build_category_entry(
                _LONG_DISTANCE_RAIL_CATEGORY, "public_transport",
                lambda m: m == _LONG_DISTANCE_RAIL_MODE,
                _is_bahncard_plan,
            )
            if entry:
                category_subscription_analysis.append(entry)
            continue

        entry = _build_category_entry(
            cat, cat, lambda m, cat=cat: category_covers_mode(cat, m), lambda name: True
        )
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
        "detected_inefficiencies": [i["details"] for i in inefficiencies],
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