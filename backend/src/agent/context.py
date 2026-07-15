"""Read the production schema for one user and shape the context the engines consume.

Records keep their production column names; the engines translate the transport-mode
and subscription vocabularies via ``schema_map``. Returns ``{"error": ...}`` when the
user is missing so callers can surface a clean 404.
"""

from datetime import datetime, timedelta, timezone

from dateutil.rrule import rrulestr

from database import get_connection
from agent.schema_map import clean_row, preferences_from_onboarding

# How far ahead to look for calendar occurrences — roughly 2x the forecaster's
# 365-day horizon so a stray far-future entry doesn't dominate.
_CALENDAR_LOOKAHEAD_DAYS = 730


def _next_occurrence(dtstart, rrule_str, exdate_raw, window_start, window_end):
    """Earliest occurrence of one user_calendars row that falls within
    ``[window_start, window_end]``, or ``None`` if none does.

    Non-recurring rows (``rrule_str`` falsy) just check their own ``dtstart``. For
    recurring rows, the RRULE is expanded with ``dateutil`` (dtstart anchors the
    series) so a series that started long before the window still surfaces its
    future occurrences — a plain ``dtstart >= NOW()`` filter would otherwise hide
    every recurring event whose first occurrence has already passed. Dates listed
    in ``exdate`` (expected as a JSON list of ISO date/datetime strings) are
    excluded. RDATE (extra ad-hoc occurrences beyond the rule) is not handled.
    Malformed rrule/exdate data falls back to treating the row as a single
    non-recurring event rather than raising.
    """
    if not dtstart:
        return None

    if not rrule_str:
        return dtstart if window_start <= dtstart <= window_end else None

    try:
        occurrences = rrulestr(rrule_str, dtstart=dtstart).between(
            window_start, window_end, inc=True
        )
    except (ValueError, TypeError):
        return dtstart if window_start <= dtstart <= window_end else None

    if not occurrences:
        return None

    excluded_dates = set()
    for value in exdate_raw or []:
        try:
            excluded_dates.add(
                datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
            )
        except ValueError:
            continue

    for occ in occurrences:
        if occ.date() not in excluded_dates:
            return occ
    return None


def load_context(user_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return {"error": f"User with ID {user_id} not found in database."}

    user = clean_row(user_row)
    user["name"] = f"{user['first_name']} {user['last_name']}".strip()

    # Preferences live in user_onboardings (0-100 scores).
    cursor.execute(
        "SELECT * FROM user_onboardings WHERE user_id = ?", (user_id,)
    )
    onboarding_row = cursor.fetchone()
    preferences = preferences_from_onboarding(onboarding_row)
    # Full onboarding row (structured constraints + free text) the modal-shift engine
    # needs (avoided_transport_modes, car_access, has_driving_license,
    # mobility_constraints, travel_statement, activity_statement) — preferences_from_
    # onboarding above only extracts the 3 priority scores, so this is read
    # separately rather than growing that function's return shape for a use case it
    # isn't otherwise involved in.
    onboarding_raw = clean_row(onboarding_row) if onboarding_row else {}

    # Subscriptions joined to the catalog. The engines key on the catalog PK
    # (subscription_id) and the subscription category, not on a service slug.
    cursor.execute(
        """
        SELECT s.user_subscription_id, s.subscription_status,
               s.is_primary_mobility_option, s.estimated_usage_frequency,
               c.subscription_id, c.provider_name, c.provider_plan_name,
               c.subscription_category, c.monthly_cost_eur, c.annual_cost_eur
        FROM user_subscriptions s
        LEFT JOIN subscription_catalogs c ON c.subscription_id = s.subscription_id
        WHERE s.user_id = ?
        """,
        (user_id,),
    )
    subscriptions = []
    for row in cursor.fetchall():
        sub = clean_row(row)
        sub["monthly_cost_eur"] = sub.get("monthly_cost_eur") or 0.0
        subscriptions.append(sub)

    # Travel history is leg-level (legs carry distance, duration, cost, CO2 and mode),
    # ordered chronologically for the forecaster's monthly grouping.
    # reference_cost_eur is the pay-as-you-go price for a leg regardless of any
    # subscription held; the analysis engine uses it to compute discount-card
    # (e.g. BahnCard) realized savings, falling back to estimated_cost_eur when NULL.
    # duration_minutes feeds the consumption-based alternative simulator (per-minute/
    # per-hour car-/bike-sharing and e-scooter plans) alongside estimated_distance_km —
    # see agent/engines/analysis.py's _simulate_consumption_annual_cost.
    cursor.execute(
        """
        SELECT leg_id, trip_id, user_subscription_id, started_at, transport_mode, ticket_type, ticket_class,
               estimated_distance_km, duration_minutes, estimated_cost_eur, reference_cost_eur, estimated_co2_emissions
        FROM trip_legs
        WHERE user_id = ?
        ORDER BY started_at ASC
        """,
        (user_id,),
    )
    travel_history = [clean_row(r) for r in cursor.fetchall()]

    # Upcoming calendar entries, fed to the forecaster's raw-ICS LLM path (see
    # raw_calendar_entries in forecast()) so it can factor in known future plans
    # (e.g. a relocation, a trip already on the calendar). Only VEVENT rows are
    # considered — matches _parse_ics's own VEVENT-only filter, excluding VTODO/
    # VJOURNAL/VFREEBUSY/VTIMEZONE/OTHER rows that aren't really "something
    # happening on a date". Date filtering happens in Python (via
    # _next_occurrence), not SQL, since a recurring row's own dtstart can be far
    # in the past even though it still has future occurrences.
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=_CALENDAR_LOOKAHEAD_DAYS)
    cursor.execute(
        """
        SELECT summary, dtstart, location, description, rrule, exdate
        FROM user_calendars
        WHERE user_id = ? AND component_type = 'VEVENT'
        """,
        (user_id,),
    )
    raw_calendar_entries = []
    for row in cursor.fetchall():
        row = dict(row)
        occurrence = _next_occurrence(
            row.get("dtstart"), row.get("rrule"), row.get("exdate"), now, window_end
        )
        if occurrence is None:
            continue
        raw_calendar_entries.append(
            {
                "summary": row.get("summary") or "",
                "date": occurrence.date().isoformat(),
                "location": row.get("location") or "",
                "description": row.get("description") or "",
            }
        )
    raw_calendar_entries.sort(key=lambda e: e["date"])

    # The analysis engine's candidate catalog comes straight from subscription_catalogs,
    # keyed by the real PK. subscription_type_other/billing_cycle feed its eligibility
    # filter (age-gated BahnCard variants, one-time trial cards); pricing_model tells it
    # which plans are true flat-rate passes it can safely price as "trip costs nothing"
    # (see agent/engines/analysis.py's category_subscription_analysis); markdown_ref lets
    # the memo step cite the exact tariff doc for a recommended plan instead of guessing
    # from its name. unlock_fee_eur/per_km_eur/per_hour_eur/per_minute_eur/
    # free_minutes_included/daily_cap_eur feed the consumption-based alternative
    # simulator for car-/bike-sharing and e-scooter plans that aren't flat-rate passes —
    # NULL (absent) for plans whose tariff doc gives no exploitable linear rate (tiered
    # per-ride pricing, "varies by tier/city" with no representative number).
    cursor.execute("SELECT * FROM subscription_catalogs")
    pricing_catalog = []
    for row in cursor.fetchall():
        item = clean_row(row)
        pricing_catalog.append(
            {
                "id": item.get("subscription_id"),
                "name": item.get("provider_plan_name"),
                "category": item.get("subscription_category"),
                "monthly_cost": item.get("monthly_cost_eur") or 0.0,
                "annual_cost": item.get("annual_cost_eur"),
                "subscription_type": item.get("subscription_type"),
                "subscription_type_other": item.get("subscription_type_other"),
                "pricing_model": item.get("pricing_model"),
                "billing_cycle": item.get("billing_cycle"),
                "travel_class": item.get("travel_class"),
                "unlock_fee_eur": item.get("unlock_fee_eur"),
                "per_km_eur": item.get("per_km_eur"),
                "per_hour_eur": item.get("per_hour_eur"),
                "per_minute_eur": item.get("per_minute_eur"),
                "free_minutes_included": item.get("free_minutes_included"),
                "daily_cap_eur": item.get("daily_cap_eur"),
                "markdown_ref": item.get("markdown_ref"),
            }
        )

    conn.close()
    return {
        "user": user,
        "user_preferences": preferences,
        "onboarding_raw": onboarding_raw,
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": pricing_catalog,
        "raw_calendar_entries": raw_calendar_entries,
    }
