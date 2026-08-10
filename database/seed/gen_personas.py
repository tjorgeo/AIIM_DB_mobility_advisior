"""Generator for the 10-persona seed dataset.

Produces: user_profiles_v4.csv, user_onboardings_v4.csv, user_subscriptions_v5.csv,
user_trips_v5.csv, trip_legs_v8.csv, user_calendars_v2.csv

Cost/CO2 model matches database/seed/PERSONAS.md's "Cost / CO2 model used by the
generator" table so realized_savings / net_savings computed by
backend/src/agent/engines/analysis.py::analyze_portfolio stay internally consistent.
"""
import csv
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

random.seed(20260710)

NS = uuid.UUID("2f6a1a1a-0000-4000-8000-000000000000")


def uid(seed: str) -> str:
    return str(uuid.uuid5(NS, seed))


def fmt_ts(d: datetime) -> str:
    """Matches the existing dataset's timestamp style, e.g. '2024-07-01 07:54:00+01:00'
    (space separator, colon in the UTC offset) rather than Python's default 'T'/'+0200'."""
    offset = d.utcoffset()
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hh, mm = divmod(abs(total_minutes), 60)
    return d.strftime("%Y-%m-%d %H:%M:%S") + f"{sign}{hh:02d}:{mm:02d}"


# Regenerating overwrites the checked-in v4/v5/v8/v2 seed CSVs in this same
# directory (database/seed/) - re-point database/init/02_insert_data.sql if you
# bump any of the version suffixes below.
OUT_DIR = Path(__file__).resolve().parent

TZ = timezone(timedelta(hours=1))
TZ_SUMMER = timezone(timedelta(hours=2))

WINDOW_START = date(2025, 7, 1)
WINDOW_END = date(2026, 6, 30)  # inclusive, 12 full calendar months

# ---------------------------------------------------------------------------
# Cost / CO2 model (see PERSONAS.md)
# ---------------------------------------------------------------------------
CO2_FACTOR = {
    "public_transport": 0.04,
    "regional_train": 0.035,
    "long_distance_train": 0.03,
    "bike_sharing": 0.005,
    "car_sharing": 0.15,
    "e_scooter": 0.02,
}


def tz_for(d: date):
    return TZ_SUMMER if 3 <= d.month <= 10 else TZ


def season_factor(d: date) -> float:
    """65% reduction during summer holidays (Jul/Aug) and the Dec20-Jan5 lull,
    matching the existing dataset's convention (see PERSONAS.md)."""
    if d.month in (7, 8):
        return 0.35
    if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 5):
        return 0.35
    return 1.0


def ref_public_transport(km):
    return 2.90


def ref_regional_train(km):
    return round(2.50 + 0.20 * km, 2)


def ref_long_distance_train(km):
    return round(max(19.90, 0.16 * km), 2)


def ref_bike_sharing(minutes):
    return round(1.00 + 0.12 * minutes, 2)


def paid_bike_sharing_member_plus(minutes):
    extra = max(0, minutes - 30)
    return round(0.10 * extra, 2)


def ref_car_sharing(km):
    return round(1.00 + 0.79 * km, 2)


def paid_car_sharing_teilauto(km, minutes):
    return round(1.68 * (minutes / 60.0) + 0.224 * km, 2)


def ref_e_scooter(minutes):
    return round(1.00 + 0.25 * minutes, 2)


def paid_e_scooter_bolt_unlimited(minutes):
    return round(0.22 * minutes, 2)


REF_FN = {
    "public_transport": lambda km, minutes: ref_public_transport(km),
    "regional_train": lambda km, minutes: ref_regional_train(km),
    "long_distance_train": lambda km, minutes: ref_long_distance_train(km),
    "bike_sharing": lambda km, minutes: ref_bike_sharing(minutes),
    "car_sharing": lambda km, minutes: ref_car_sharing(km),
    "e_scooter": lambda km, minutes: ref_e_scooter(minutes),
}

# 1st-class fare multiplier. None of the REF_FN formulas above take a class
# parameter (the whole dataset before this was implicitly 2nd class), and
# ticket_class is never read back by the analyst engine (see agent/engines/
# analysis.py's module comments on why — no per-leg evidence of fare class exists
# in real production data either). This exists solely so a 1st-class persona's
# reference_cost_eur is itself priced higher, the way a real 1st-class Flexpreis
# fare actually costs more than 2nd class — otherwise only her BahnCard's own
# (already correctly class-priced) annual fee would look more expensive, while the
# fare it discounts stayed priced as if she rode 2nd class, understating her real
# savings. ~1.5x roughly matches DB's real 1st/2nd-class Flexpreis ratio.
CLASS_1_MULTIPLIER = 1.5

# ---------------------------------------------------------------------------
# Subscription catalog references (subscription_catalogs_v2.csv)
# ---------------------------------------------------------------------------
SUB_DT = "a1111111-1111-1111-1111-111111111111"          # Deutschlandticket, 63/mo, flat
SUB_BC25_2KL = "a3333333-3333-3333-3333-333333333333"     # BahnCard 25, 2. Klasse, 62.90/yr
SUB_BC50_2KL = "d1111111-1111-1111-1111-111111111111"     # BahnCard 50, 2. Klasse, 244.00/yr
SUB_CAB_MEMBER_PLUS = "m1111111-1111-1111-1111-111111111111"  # Call a Bike Member Plus, 8/mo (96/yr)
SUB_TEILAUTO_VIELFAHRER = "x1111111-1111-1111-1111-111111111111"  # teilAuto Vielfahrertarif, 30/mo (360/yr)
SUB_BOLT_UNLIMITED = "t1111111-1111-1111-1111-111111111111"       # Bolt Unbegrenzte Freischaltungen, 1.99/mo (23.88/yr)
SUB_BC50_1KL = "i1111111-1111-1111-1111-111111111111"      # BahnCard 50, 1. Klasse, 487.00/yr

# ---------------------------------------------------------------------------
# Output accumulators
# ---------------------------------------------------------------------------
users_rows = []
onboarding_rows = []
subscription_rows = []
trip_rows = []
leg_rows = []
calendar_rows = []


def add_user(user_id, email, username, first_name, last_name, dob, age, gender, life_stage,
             home_city, home_postal, home_country="DE"):
    users_rows.append([
        user_id, email, username, "", first_name, last_name, dob, age, gender, life_stage,
        home_city, home_postal, home_country,
    ])


def add_onboarding(user_id, employment_status, occupation, work_city, work_postal, work_arrangement,
                    remote_share, household_size, household_type, income_band, budget,
                    has_license, car_access, bike_access, preferred, avoided, constraints,
                    score_emission, score_money, score_flexibility, weekday_pattern, weekend_pattern,
                    travel_statement, activity_statement, work_country="DE"):
    def pg_array(values):
        return "{" + ",".join(f'"{v}"' for v in values) + "}"

    onboarding_rows.append([
        f"onboarding_{user_id}", user_id, employment_status, occupation, work_city, work_postal,
        work_country, work_arrangement, remote_share, household_size, household_type, income_band,
        budget, has_license, car_access, bike_access,
        pg_array(preferred), pg_array(avoided), pg_array(constraints),
        score_emission, score_money, score_flexibility, weekday_pattern, weekend_pattern,
        travel_statement, activity_statement,
    ])


def add_subscription(user_id, subscription_id, valid_from, primary, freq, valid_until=""):
    usub_id = uid(f"usersub:{user_id}:{subscription_id}")
    subscription_rows.append([
        usub_id, user_id, subscription_id, valid_from, valid_until, "active", primary, freq,
    ])
    return usub_id


def add_calendar(user_id, dtstart, dtend, summary, description, location, rrule=""):
    cal_id = uid(f"cal:{user_id}:{summary}:{dtstart.isoformat()}")
    stamp = "2026-07-10 00:00:00+00:00"
    calendar_rows.append([
        cal_id,                              # calendar_id
        user_id,                             # user_id
        "VEVENT",                            # component_type
        f"{cal_id}@dbmoveoptimizer.local",   # uid
        stamp,                               # dtstamp
        fmt_ts(dtstart),                     # dtstart
        fmt_ts(dtend) if dtend else "",      # dtend
        "",                                  # duration
        summary,                             # summary
        description,                         # description
        location,                            # location
        "",                                  # url
        "",                                  # class
        "CONFIRMED",                         # status
        "",                                  # transp
        "",                                  # priority
        stamp,                               # created
        "",                                  # last_modified
        0,                                   # sequence
        rrule,                               # rrule
        "",                                  # rdate
        "",                                  # exdate
        "",                                  # recurrence_id
        "",                                  # organizer
        "",                                  # attendee
        "",                                  # categories
        "",                                  # comment
        "",                                  # contact
        "",                                  # related_to
        "",                                  # resources
        "",                                  # request_status
        "",                                  # geo
        "",                                  # attach
        "",                                  # valarm
        "",                                  # parameters
        "",                                  # x_properties
        "",                                  # raw_icalendar
        stamp,                               # inserted_at
        stamp,                               # updated_at
    ])


_trip_seq = {}


def add_trip_and_leg(user_id, day, start_time, duration_min, origin_label, origin_city,
                      dest_label, dest_city, purpose, mode, distance_km, is_commute,
                      is_recurring, user_subscription_id, paid_override=None,
                      ticket_class=None, class_multiplier=1.0):
    """Creates one trip + one leg (1:1, matching existing dataset convention).
    paid_override: if given, use this as estimated_cost_eur instead of the
    reference price (subscription-covered legs).
    ticket_class: 1 or 2 to record this leg's fare class (the ``ticket_class``
    column) — None (the default, used by every persona before Claudia) leaves it
    blank, matching real production data (see analysis.py's module comments on why
    the analyst engine never reads it back regardless).
    class_multiplier: scales the computed reference_cost (and, unless paid_override
    is given, estimated_cost too) — used only to price a 1st-class fare, which none
    of the REF_FN formulas otherwise know how to do (see CLASS_1_MULTIPLIER)."""
    tz = tz_for(day)
    started_at = datetime.combine(day, start_time, tzinfo=tz)
    ended_at = started_at + timedelta(minutes=duration_min)

    seq_key = (user_id, day.isoformat())
    _trip_seq[seq_key] = _trip_seq.get(seq_key, 0) + 1
    trip_id = uid(f"trip:{user_id}:{started_at.isoformat()}:{_trip_seq[seq_key]}")
    leg_id = uid(f"leg:{trip_id}")

    reference_cost = round(REF_FN[mode](distance_km, duration_min) * class_multiplier, 2)
    estimated_cost = reference_cost if paid_override is None else paid_override
    co2 = round(distance_km * CO2_FACTOR[mode], 3)

    ticket_type = "subscription" if user_subscription_id else (
        "single_ticket" if mode == "public_transport" else "pay-as-you-go"
    )

    trip_rows.append([
        trip_id, user_id, fmt_ts(started_at), fmt_ts(ended_at), duration_min,
        origin_label, origin_city, "", "DE", dest_label, dest_city, "", "DE",
        purpose, "", mode, "", distance_km, is_commute, False, is_recurring,
    ])
    leg_rows.append([
        leg_id, trip_id, user_id, user_subscription_id or "", 1,
        fmt_ts(started_at), fmt_ts(ended_at), duration_min,
        origin_label, origin_city, "", "DE", dest_label, dest_city, "", "DE",
        mode, ticket_type, ticket_class if ticket_class is not None else "", "",
        distance_km, estimated_cost, reference_cost, co2,
        False, True, False, False, "", 0,
    ])


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# ===========================================================================
# Persona 1: Julia Berger — BahnCard 25 -> should upgrade to BahnCard 50,
# plus a Deutschlandticket that clearly pays off.
# ===========================================================================
JULIA = uid("user:julia.berger")
add_user(JULIA, "julia.berger@example.com", "juliaberger35", "Julia", "Berger",
          "1990-08-22", 35, "female", "single", "Leipzig", "04109")
add_onboarding(
    JULIA, "employed_full_time", "Key Account Manager", "Leipzig", "04103", "hybrid", 0.2,
    1, "single", "high", 220.0, True, "none", "none",
    ["long_distance_train", "regional_train", "public_transport"], ["car"],
    ["frequent_travel", "time_efficiency"],
    60, 65, 60,
    "Regional-train commute into the Leipzig office most days, long-distance train to client sites "
    "1-2x/week on the BahnCard.",
    "Mostly local errands, occasional weekend trip to see family.",
    "Between the Deutschlandticket for the daily commute and my BahnCard 25 for client trips, I'm "
    "never without a ticket - I just want to know if the BahnCard is still the right one.",
    "Steady routine punctuated by frequent business travel to client sites.",
)
julia_dt = add_subscription(JULIA, SUB_DT, "2023-06-01", True, "daily")
julia_bc25 = add_subscription(JULIA, SUB_BC25_2KL, "2022-01-15", False, "several_times_per_week")

JULIA_CLIENT_CITIES = [
    ("Berlin", 190), ("Munich", 400), ("Frankfurt", 400), ("Hamburg", 410), ("Cologne", 570),
]

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()  # 0=Mon .. 6=Sun
    if weekday < 5:
        # Daily DT-covered regional-train commute into the Leipzig office.
        if random.random() < 0.92 * sf:
            dist = round(random.uniform(7.5, 9.5), 2)
            dur = round(dist / 0.55)  # ~33km/h avg incl. stops
            add_trip_and_leg(JULIA, d, datetime.min.time().replace(hour=7, minute=random.randint(40, 58)),
                              dur, "home", "Leipzig", "office", "Leipzig", "commute",
                              "regional_train", dist, True, True, julia_dt, paid_override=0.0)
            add_trip_and_leg(JULIA, d, datetime.min.time().replace(hour=17, minute=random.randint(30, 55)),
                              dur, "office", "Leipzig", "home", "Leipzig", "home_return",
                              "regional_train", dist, True, True, julia_dt, paid_override=0.0)
        # Long-distance client trips, BC25-covered (25% of reference), ~1.4x/week.
        if random.random() < 0.28 * sf:
            city, dist = random.choice(JULIA_CLIENT_CITIES)
            dist = round(dist * random.uniform(0.95, 1.05), 2)
            ref = ref_long_distance_train(dist)
            paid = round(ref * 0.75, 2)
            dur = round(dist / 3.1)
            add_trip_and_leg(JULIA, d, datetime.min.time().replace(hour=6, minute=random.randint(30, 55)),
                              dur, "home", "Leipzig", "client site", city, "business",
                              "long_distance_train", dist, False, True, julia_bc25, paid_override=paid)
            add_trip_and_leg(JULIA, d, datetime.min.time().replace(hour=17, minute=random.randint(0, 40)),
                              dur, "client site", city, "home", "Leipzig", "home_return",
                              "long_distance_train", dist, False, True, julia_bc25, paid_override=paid)
    else:
        # Occasional DT-covered weekend leisure trip within Leipzig.
        if random.random() < 0.30 * sf:
            dist = round(random.uniform(3.0, 7.0), 2)
            dur = round(dist / 0.5)
            add_trip_and_leg(JULIA, d, datetime.min.time().replace(hour=random.randint(10, 16)),
                              dur, "home", "Leipzig", random.choice(["city center", "market square"]),
                              "Leipzig", random.choice(["leisure", "social", "shopping"]),
                              "public_transport", dist, False, False, julia_dt, paid_override=0.0)

# Local-only calendar - routine life, no subscription implications.
add_calendar(JULIA, datetime(2025, 8, 4, 18, 30, tzinfo=TZ_SUMMER), datetime(2025, 8, 4, 19, 45, tzinfo=TZ_SUMMER),
             "Pilates class", "Weekly evening pilates class at the studio near home.", "Leipzig",
             "FREQ=WEEKLY;BYDAY=MO")
add_calendar(JULIA, datetime(2025, 9, 12, 9, 0, tzinfo=TZ_SUMMER), datetime(2025, 9, 12, 9, 45, tzinfo=TZ_SUMMER),
             "Dentist checkup", "Routine dental checkup.", "Leipzig", "")
add_calendar(JULIA, datetime(2025, 10, 3, 19, 0, tzinfo=TZ_SUMMER), datetime(2025, 10, 3, 22, 0, tzinfo=TZ_SUMMER),
             "Book club", "Monthly book club meeting at a member's apartment.", "Leipzig",
             "FREQ=MONTHLY;BYDAY=1FR")
add_calendar(JULIA, datetime(2026, 3, 14, 12, 0, tzinfo=TZ), datetime(2026, 3, 14, 14, 0, tzinfo=TZ),
             "Haircut appointment", "Trim and color at the salon.", "Leipzig", "")

# Life-event calendar: an *upcoming* job change (dated ahead of WINDOW_END/today so
# the forecaster's forward-looking scan picks it up - see the NOTE in Jonas's
# section below) that ends her frequent long-distance client travel entirely, not
# yet reflected in the trip history above. Meant to flip category_subscription_
# analysis's long_distance_rail recommendation forward (today: switch_to_alternative
# to BahnCard 50, driven by her current ~113 trips/yr) once the forecaster projects
# that volume collapsing to near zero.
JOB_OFFER_DATE = date(2026, 8, 10)
NEW_JOB_START = date(2026, 9, 1)
add_calendar(JULIA, datetime(JOB_OFFER_DATE.year, JOB_OFFER_DATE.month, JOB_OFFER_DATE.day, 15, 0, tzinfo=TZ_SUMMER),
             datetime(JOB_OFFER_DATE.year, JOB_OFFER_DATE.month, JOB_OFFER_DATE.day, 16, 0, tzinfo=TZ_SUMMER),
             "Neues Jobangebot angenommen - vollständig remote", "Accepted a new, fully remote Account "
             "Manager role starting next month - no more client site visits once she starts.", "Leipzig", "")
add_calendar(JULIA, datetime(NEW_JOB_START.year, NEW_JOB_START.month, NEW_JOB_START.day, 9, 0, tzinfo=TZ_SUMMER),
             datetime(NEW_JOB_START.year, NEW_JOB_START.month, NEW_JOB_START.day, 17, 0, tzinfo=TZ_SUMMER),
             "Neuer Job beginnt - vollständig remote", "First day in the new, fully remote position - works "
             "exclusively from her home office in Leipzig from here on. The weekly long-distance client trips "
             "to Munich, Cologne, Frankfurt, Berlin and Hamburg stop completely.", "Leipzig", "")

print(f"Julia trips so far: {len(trip_rows)}")


# ===========================================================================
# Persona 2: Jonas Keller — holds no subscription at all, pure pay-as-you-go.
# His trip history is a plain, unchanging short in-city commute (no
# subscription needed to make DT worth it even on that alone) - the twist is
# an *upcoming* move to a farther-out apartment on his calendar, which the
# forecaster picks up as a life event and factors into the forward-looking
# forecast even though it isn't reflected in the historical baseline yet.
#
# NOTE: the forecaster only ever sees calendar entries whose next occurrence
# falls within [now, now+180 days] (see _CALENDAR_LOOKAHEAD_DAYS in
# agent/context.py) - it's a forward-looking "known future plans" signal, not
# a historical one. Keep MOVE_DATE / VIEWING_DATE below in the future relative
# to whenever this dataset is loaded, or the forecaster will never see them.
# ===========================================================================
JONAS = uid("user:jonas.keller")
add_user(JONAS, "jonas.keller@example.com", "jonaskeller28", "Jonas", "Keller",
          "1998-03-14", 28, "male", "single", "Hamburg", "20095")
add_onboarding(
    JONAS, "employed_full_time", "Junior Data Analyst", "Hamburg", "20095", "in_office", 0.05,
    1, "single", "medium", 90.0, True, "none", "none",
    ["public_transport", "regional_train"], ["car"],
    ["upcoming_relocation", "no_fixed_pass"],
    50, 70, 45,
    "Commutes into the Hamburg office by bus/S-Bahn most days, buying single tickets each time.",
    "Occasional single-ticket trips into the city, biweekly regional-train visit to his parents.",
    "I've never bothered with a pass since I live close to the office - but I'm moving further out "
    "soon, so the single tickets are about to get a lot more expensive.",
    "Regular commuter footprint about to get noticeably longer once he moves.",
)
# No subscriptions at all for Jonas.

VIEWING_DATE = date(2026, 7, 25)
MOVE_DATE = date(2026, 8, 22)
PARENTS_TOWN = ("Lüneburg", 55)

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        # Short in-city commute, unchanged throughout the whole 12-month history
        # (he hasn't moved yet - the move is still ahead, see calendar below).
        if random.random() < 0.85 * sf:
            dist = round(random.uniform(4.0, 6.0), 2)
            dur = round(dist / 0.45)
            mode = "public_transport"
            add_trip_and_leg(JONAS, d, datetime.min.time().replace(hour=7, minute=random.randint(35, 55)),
                              dur, "home", "Hamburg", "office", "Hamburg", "commute",
                              mode, dist, True, True, "")
            add_trip_and_leg(JONAS, d, datetime.min.time().replace(hour=17, minute=random.randint(15, 50)),
                              dur, "office", "Hamburg", "home", "Hamburg", "home_return",
                              mode, dist, True, True, "")
    else:
        if random.random() < 0.25 * sf:
            dist = round(random.uniform(3.0, 6.0), 2)
            dur = round(dist / 0.45)
            add_trip_and_leg(JONAS, d, datetime.min.time().replace(hour=random.randint(11, 17)),
                              dur, "home", "Hamburg", random.choice(["shopping street", "harbor front"]),
                              "Hamburg", random.choice(["shopping", "leisure", "social"]),
                              "public_transport", dist, False, False, "")

# Biweekly regional-train visit to parents (pay-as-you-go, single ticket).
d = WINDOW_START + timedelta(days=5)
while d <= WINDOW_END:
    if random.random() < 0.85 * season_factor(d):
        town, dist = PARENTS_TOWN
        dist = round(dist * random.uniform(0.95, 1.05), 2)
        dur = round(dist / 0.8)
        add_trip_and_leg(JONAS, d, datetime.min.time().replace(hour=9, minute=random.randint(0, 30)),
                          dur, "home", "Hamburg", "parents' home", town, "social",
                          "regional_train", dist, False, False, "")
        add_trip_and_leg(JONAS, d, datetime.min.time().replace(hour=19, minute=random.randint(0, 30)),
                          dur, "parents' home", town, "home", "Hamburg", "home_return",
                          "regional_train", dist, False, False, "")
    d += timedelta(days=14)

# Life-event + trip-affecting calendar: an *upcoming* move (both events dated
# ahead of WINDOW_END/today so the forecaster's forward-looking calendar scan
# actually picks them up - see the NOTE above), plus a recurring item that's
# already part of his routine.
add_calendar(JONAS, datetime(VIEWING_DATE.year, VIEWING_DATE.month, VIEWING_DATE.day, 12, 0, tzinfo=TZ_SUMMER),
             datetime(VIEWING_DATE.year, VIEWING_DATE.month, VIEWING_DATE.day, 13, 0, tzinfo=TZ_SUMMER),
             "Wohnungsbesichtigung Norderstedt", "Apartment viewing in Norderstedt - noticeably farther "
             "from the office than his current place.", "Hamburg", "")
add_calendar(JONAS, datetime(MOVE_DATE.year, MOVE_DATE.month, MOVE_DATE.day, 9, 0, tzinfo=TZ_SUMMER),
             datetime(MOVE_DATE.year, MOVE_DATE.month, MOVE_DATE.day, 18, 0, tzinfo=TZ_SUMMER),
             "Umzug - neue Wohnung in Norderstedt", "Moving day into the new, farther-out apartment - "
             "commute to the Hamburg office gets noticeably longer from here on.", "Hamburg", "")
add_calendar(JONAS, datetime(2025, 7, 13, 9, 0, tzinfo=TZ_SUMMER), datetime(2025, 7, 13, 19, 0, tzinfo=TZ_SUMMER),
             "Besuch bei den Eltern", "Biweekly weekend visit to parents in Lüneburg by regional train.",
             "Lüneburg", "FREQ=WEEKLY;INTERVAL=2;BYDAY=SU")
add_calendar(JONAS, datetime(MOVE_DATE.year, MOVE_DATE.month, MOVE_DATE.day - 7, 10, 0, tzinfo=TZ_SUMMER),
             datetime(MOVE_DATE.year, MOVE_DATE.month, MOVE_DATE.day - 7, 17, 0, tzinfo=TZ_SUMMER),
             "Packing weekend", "Packing up the old apartment ahead of next week's move.", "Hamburg", "")

print(f"After Jonas: {len(trip_rows)}")


# ===========================================================================
# Persona 3: Simone Wagner — holds three subscriptions from a busier, more
# travel-heavy period of her job that never got cleaned up. Her Deutschland-
# ticket still earns its keep on the hybrid commute, but the BahnCard 25 (kept
# from when she used to see a since-ended client) and the Call a Bike Member
# Plus (kept from a fitness kick two years ago) barely get touched anymore -
# both should be cancelled.
# ===========================================================================
SIMONE = uid("user:simone.wagner")
add_user(SIMONE, "simone.wagner@example.com", "simonewagner46", "Simone", "Wagner",
          "1979-11-05", 46, "female", "single_or_couple_without_children", "Dresden", "01067")
add_onboarding(
    SIMONE, "employed_full_time", "Project Manager", "Dresden", "01097", "hybrid", 0.4,
    2, "couple_without_children", "high", 160.0, True, "none", "none",
    ["public_transport", "regional_train"], ["car"],
    ["signed_up_for_perks", "low_usage"],
    55, 45, 55,
    "In the office by regional train about three days a week; works from home the rest.",
    "Rarely travels beyond the neighbourhood; the BahnCard and bike-share membership mostly sit unused.",
    "I picked up the BahnCard 25 and the Call a Bike membership years ago and just never got around to "
    "cancelling either, even though I barely use them anymore.",
    "Low, settled mobility footprint outside of the regular hybrid commute.",
)
simone_dt = add_subscription(SIMONE, SUB_DT, "2021-09-01", True, "several_times_per_week")
simone_bc25 = add_subscription(SIMONE, SUB_BC25_2KL, "2022-04-01", False, "rarely")
simone_cab = add_subscription(SIMONE, SUB_CAB_MEMBER_PLUS, "2023-05-01", False, "rarely")

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        # DT-covered hybrid commute, ~3 days/week in office.
        if random.random() < 0.55 * sf:
            dist = round(random.uniform(9.0, 12.0), 2)
            dur = round(dist / 0.5)
            add_trip_and_leg(SIMONE, d, datetime.min.time().replace(hour=8, minute=random.randint(0, 25)),
                              dur, "home", "Dresden", "office", "Dresden", "commute",
                              "regional_train", dist, True, True, simone_dt, paid_override=0.0)
            add_trip_and_leg(SIMONE, d, datetime.min.time().replace(hour=16, minute=random.randint(30, 55)),
                              dur, "office", "Dresden", "home", "Dresden", "home_return",
                              "regional_train", dist, True, True, simone_dt, paid_override=0.0)
    else:
        if random.random() < 0.18 * sf:
            dist = round(random.uniform(3.0, 6.0), 2)
            dur = round(dist / 0.45)
            add_trip_and_leg(SIMONE, d, datetime.min.time().replace(hour=random.randint(11, 16)),
                              dur, "home", "Dresden", random.choice(["farmers market", "city center"]),
                              "Dresden", random.choice(["shopping", "errands"]),
                              "public_transport", dist, False, False, simone_dt, paid_override=0.0)

# Two rare long-distance trips a year on the BahnCard 25 (barely justifies its cost).
for month, day in [(9, 18), (3, 6)]:
    yr = 2025 if month >= 7 else 2026
    d = date(yr, month, day)
    dist = round(305 * random.uniform(0.97, 1.03), 2)
    ref = ref_long_distance_train(dist)
    paid = round(ref * 0.75, 2)
    dur = round(dist / 3.1)
    add_trip_and_leg(SIMONE, d, datetime.min.time().replace(hour=8, minute=10),
                      dur, "home", "Dresden", "conference venue", "Leipzig", "business",
                      "long_distance_train", dist, False, False, simone_bc25, paid_override=paid)
    add_trip_and_leg(SIMONE, d, datetime.min.time().replace(hour=18, minute=20),
                      dur, "conference venue", "Leipzig", "home", "Dresden", "home_return",
                      "long_distance_train", dist, False, False, simone_bc25, paid_override=paid)

# ~15 short Call a Bike rides/year, each well under the 30 free minutes -> paid 0,
# but the membership fee (96/yr) still isn't earned back by the reference savings.
cab_dates = sorted(random.sample(
    [WINDOW_START + timedelta(days=i) for i in range(0, (WINDOW_END - WINDOW_START).days)], 15
))
for d in cab_dates:
    dur = random.randint(10, 25)
    dist = round(dur * 0.2, 2)
    add_trip_and_leg(SIMONE, d, datetime.min.time().replace(hour=random.randint(12, 19)),
                      dur, "home", "Dresden", "riverside path", "Dresden", "leisure",
                      "bike_sharing", dist, False, False, simone_cab,
                      paid_override=paid_bike_sharing_member_plus(dur))

# Local-only calendar - settled routine, no subscription implications.
add_calendar(SIMONE, datetime(2025, 7, 22, 19, 0, tzinfo=TZ_SUMMER), datetime(2025, 7, 22, 21, 0, tzinfo=TZ_SUMMER),
             "Choir rehearsal", "Weekly evening choir rehearsal at the community hall.", "Dresden",
             "FREQ=WEEKLY;BYDAY=TU")
add_calendar(SIMONE, datetime(2025, 8, 14, 10, 0, tzinfo=TZ_SUMMER), datetime(2025, 8, 14, 10, 45, tzinfo=TZ_SUMMER),
             "Annual health checkup", "Routine checkup with the GP.", "Dresden", "")
add_calendar(SIMONE, datetime(2025, 11, 9, 18, 30, tzinfo=TZ), datetime(2025, 11, 9, 21, 30, tzinfo=TZ),
             "Dinner with old colleagues", "Catching up with former coworkers at a restaurant nearby.",
             "Dresden", "")
add_calendar(SIMONE, datetime(2026, 4, 18, 9, 0, tzinfo=TZ_SUMMER), datetime(2026, 4, 18, 9, 30, tzinfo=TZ_SUMMER),
             "Hairdresser appointment", "Trim appointment at the salon around the corner.", "Dresden", "")

# Life-event calendar: her partner's *upcoming* relocation to Berlin for a new job
# (dated ahead of WINDOW_END/today so the forecaster's forward-looking scan picks it
# up - see the NOTE in Jonas's section above), plus the recurring monthly weekend
# visits that follow - not yet reflected in the two-trips-a-year baseline above.
# Meant to flip category_subscription_analysis's long_distance_rail recommendation
# forward (today: cancel_current_go_pay_as_you_go, since her BahnCard 25 barely
# breaks even at ~4 trips/yr) once the forecaster projects that volume rising
# sharply - well past the point where the BahnCard pays off again.
PARTNER_MOVE_DATE = date(2026, 8, 15)
FIRST_VISIT_DATE = date(2026, 8, 29)
add_calendar(SIMONE, datetime(PARTNER_MOVE_DATE.year, PARTNER_MOVE_DATE.month, PARTNER_MOVE_DATE.day, 9, 0, tzinfo=TZ_SUMMER),
             datetime(PARTNER_MOVE_DATE.year, PARTNER_MOVE_DATE.month, PARTNER_MOVE_DATE.day, 18, 0, tzinfo=TZ_SUMMER),
             "Partner zieht nach Berlin", "Her partner has accepted a new job in Berlin and is relocating "
             "there - regular weekend visits by long-distance train start from here on.", "Berlin", "")
add_calendar(SIMONE, datetime(FIRST_VISIT_DATE.year, FIRST_VISIT_DATE.month, FIRST_VISIT_DATE.day, 8, 0, tzinfo=TZ_SUMMER),
             datetime(FIRST_VISIT_DATE.year, FIRST_VISIT_DATE.month, FIRST_VISIT_DATE.day + 1, 20, 0, tzinfo=TZ_SUMMER),
             "Wochenendbesuch in Berlin", "Monthly weekend visit to see her partner in Berlin by "
             "long-distance train (ICE) - a new recurring routine now that he lives there.", "Berlin",
             "FREQ=MONTHLY;BYDAY=-1SA")

print(f"After Simone: {len(trip_rows)}")


# ===========================================================================
# Persona 4: Elif Yildiz — car-free freelancer whose mobility centers on a
# heavily-used car-sharing membership, topped up with pay-as-you-go e-scooter
# and bike-share for short hops. Her trip history is her ordinary baseline;
# an *upcoming* home-renovation project on her calendar (not yet reflected in
# that history) will drive a burst of extra car-sharing hauling trips ahead -
# a forward-looking signal for the forecaster (see the NOTE in Jonas's
# section above about why calendar life-events must be dated in the future).
# ===========================================================================
ELIF = uid("user:elif.yildiz")
add_user(ELIF, "elif.yildiz@example.com", "elifyildiz33", "Elif", "Yildiz",
          "1993-06-30", 33, "female", "single", "Bremen", "28195")
add_onboarding(
    ELIF, "self_employed", "Freelance UX Designer", "Bremen", "28195", "remote", 0.85,
    1, "single", "medium", 140.0, True, "none", "none",
    ["car_sharing", "e_scooter", "bike_sharing"], ["public_transport"],
    ["avoids_subscription_contracts", "prefers_flexibility"],
    45, 60, 80,
    "Works from her home studio; car-sharing for client visits and supply runs, e-scooter for "
    "quick hops across town.",
    "Weekend flea markets and hardware-store runs by car-sharing, occasional bike-share ride.",
    "I gave up owning a car years ago - teilAuto covers the trips that actually need a car, "
    "and I scoot or bike everywhere else.",
    "Car-free, multi-modal footprint built around one heavily-used car-sharing membership.",
)
elif_teilauto = add_subscription(ELIF, SUB_TEILAUTO_VIELFAHRER, "2024-03-01", True, "several_times_per_week")

RENOVATION_START, RENOVATION_END = date(2026, 8, 1), date(2026, 9, 30)
PARENTS_TOWN_2 = ("Oldenburg", 45)

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    # NOTE: RENOVATION_START/END are both after WINDOW_END - the renovation is
    # upcoming, not yet reflected in this trip history (see calendar below).

    # Car-sharing trips for client visits/supply runs, several times/week.
    base_prob = 0.55 if weekday < 5 else 0.35
    if random.random() < base_prob * sf:
        dist = round(random.uniform(5.0, 14.0), 2)
        dur = round(dist / 0.35 + random.uniform(5, 15))
        purpose = random.choice(["business", "shopping", "errands"])
        dest = random.choice(["client studio", "supplier", "print shop"])
        add_trip_and_leg(ELIF, d, datetime.min.time().replace(hour=random.randint(9, 17)),
                          dur, "home", "Bremen", dest, "Bremen", purpose,
                          "car_sharing", dist, False, weekday < 5,
                          elif_teilauto, paid_override=paid_car_sharing_teilauto(dist, dur))

    # Pay-as-you-go e-scooter for quick last-mile hops.
    if random.random() < 0.35 * sf:
        dur = random.randint(5, 18)
        dist = round(dur * 0.18, 2)
        add_trip_and_leg(ELIF, d, datetime.min.time().replace(hour=random.randint(10, 20)),
                          dur, "home", "Bremen", random.choice(["cafe", "co-working space", "studio"]),
                          "Bremen", random.choice(["social", "leisure", "business"]),
                          "e_scooter", dist, False, False, "")

    # Occasional pay-as-you-go bike-share ride.
    if random.random() < 0.15 * sf:
        dur = random.randint(10, 30)
        dist = round(dur * 0.22, 2)
        add_trip_and_leg(ELIF, d, datetime.min.time().replace(hour=random.randint(9, 19)),
                          dur, "home", "Bremen", "riverside promenade", "Bremen", "leisure",
                          "bike_sharing", dist, False, False, "")

# Monthly regional-train visit to parents (pay-as-you-go, no PT subscription held).
d = WINDOW_START + timedelta(days=10)
while d <= WINDOW_END:
    if random.random() < 0.8 * season_factor(d):
        town, dist = PARENTS_TOWN_2
        dist = round(dist * random.uniform(0.95, 1.05), 2)
        dur = round(dist / 0.8)
        add_trip_and_leg(ELIF, d, datetime.min.time().replace(hour=10, minute=0),
                          dur, "home", "Bremen", "parents' home", town, "social",
                          "regional_train", dist, False, False, "")
        add_trip_and_leg(ELIF, d, datetime.min.time().replace(hour=18, minute=0),
                          dur, "parents' home", town, "home", "Bremen", "home_return",
                          "regional_train", dist, False, False, "")
    d += timedelta(days=30)

# Life-event / trip-affecting calendar: an *upcoming* renovation project (see
# the NOTE above - dated ahead of WINDOW_END/today, not behind it, so the
# forecaster's forward-looking calendar scan actually picks it up) plus a
# recurring family visit that's already part of her routine.
add_calendar(ELIF, datetime(2026, 8, 1, 8, 0, tzinfo=TZ_SUMMER), datetime(2026, 9, 30, 18, 0, tzinfo=TZ_SUMMER),
             "Studio renovation project", "Home studio renovation starting soon - expect frequent "
             "hardware-store runs by car-sharing for about two months.", "Bremen", "")
add_calendar(ELIF, datetime(2026, 7, 20, 14, 0, tzinfo=TZ_SUMMER), datetime(2026, 7, 20, 15, 0, tzinfo=TZ_SUMMER),
             "Contractor walkthrough", "Meeting the contractor to scope the upcoming studio renovation.",
             "Bremen", "")
add_calendar(ELIF, datetime(2025, 7, 20, 10, 0, tzinfo=TZ_SUMMER), datetime(2025, 7, 20, 18, 0, tzinfo=TZ_SUMMER),
             "Family visit - Oldenburg", "Monthly weekend visit to parents in Oldenburg.", "Oldenburg",
             "FREQ=MONTHLY")
add_calendar(ELIF, datetime(2025, 9, 6, 11, 0, tzinfo=TZ_SUMMER), datetime(2025, 9, 6, 15, 0, tzinfo=TZ_SUMMER),
             "Design fair - client booth", "Staffing a client's booth at the local design fair.", "Bremen", "")

print(f"After Elif: {len(trip_rows)}")


# ===========================================================================
# Persona 5: Maja Hoffmann — showcase demo persona built to cover every major
# engine capability in one profile:
#   - a subscription to CANCEL (BahnCard 25, barely used — same math shape as
#     Simone's cancel case above)
#   - a subscription to SWITCH (a Bolt Unbegrenzte Freischaltungen e-scooter
#     plan that's a worse fit for her ride pattern than Dott Pro's free-
#     minutes structure, at her actual ride volume)
#   - a cross-category MODAL-SHIFT trigger: frequent, short (~4-8km, well
#     under bike-sharing's 15km plausibility ceiling) car-sharing errands
#     despite a stated high CO2 priority in her onboarding — exactly the
#     "says she cares about CO2 but drives a lot" case the modal-shift engine
#     exists to catch, and she has enough real bike-sharing usage of her own
#     to give the engine a historical rate to price the shift with (see
#     modal_shift.py::_price_candidate's "no historical rate -> not
#     comparable" rule).
#   - an *upcoming* life event (dated ahead of WINDOW_END/today so the
#     forecaster's forward-looking calendar scan picks it up — see the NOTE
#     in Jonas's section above) that should flip today's "cancel the
#     BahnCard" call forward once the forecaster projects her long-distance
#     volume rising from 2x/yr toward monthly.
# ===========================================================================
NORA = uid("user:nora.fischer")
add_user(NORA, "nora.fischer@example.com", "norafischer29", "Maja", "Hoffmann",
          "1996-04-12", 29, "female", "single", "Cologne", "50667")
add_onboarding(
    NORA, "employed_full_time", "Marketing Manager", "Cologne", "50667", "hybrid", 0.4,
    1, "single", "medium", 130.0, True, "none", "none",
    ["public_transport", "bike_sharing"], ["car"],
    ["climate_conscious", "habit_driven_car_sharing"],
    85, 40, 45,
    "Commutes into the Cologne office by Deutschlandticket most days, with the occasional remote "
    "day; grabs a car-sharing car for errands and short client hops in between.",
    "Occasional bike-share ride along the Rhine on weekends, light e-scooter hops to meet friends.",
    "I commute in on the Deutschlandticket, but for errands in between I almost automatically grab "
    "the car-sharing car - even though most of those short hops would work just as well by bike.",
    "Climate-friendly travel matters a lot to me, but if I'm honest, car-sharing is just the "
    "convenient habit I've fallen into, even though I could bike almost everywhere I actually go.",
)
nora_dt = add_subscription(NORA, SUB_DT, "2023-09-01", True, "several_times_per_week")
nora_bc25 = add_subscription(NORA, SUB_BC25_2KL, "2022-11-01", False, "rarely")
nora_bolt = add_subscription(NORA, SUB_BOLT_UNLIMITED, "2024-06-01", False, "several_times_per_week")

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        # DT-covered hybrid commute, most office days/week (frequent enough that the
        # Deutschlandticket's flat 63/mo actually beats paying single-ticket fares one
        # by one — at lower frequency the flat-fare pass stops paying for itself, same
        # break-even logic as everywhere else in this dataset).
        if random.random() < 0.75 * sf:
            dist = round(random.uniform(6.0, 8.0), 2)
            dur = round(dist / 0.45)
            add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=8, minute=random.randint(0, 20)),
                              dur, "home", "Cologne", "office", "Cologne", "commute",
                              "public_transport", dist, True, True, nora_dt, paid_override=0.0)
            add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=17, minute=random.randint(15, 45)),
                              dur, "office", "Cologne", "home", "Cologne", "home_return",
                              "public_transport", dist, True, True, nora_dt, paid_override=0.0)
        # Car-sharing errands, no subscription (pay-as-you-go) - deliberately short
        # (avg ~6km, well under bike-sharing's 15km plausibility ceiling), a couple
        # times a month rather than several times a week (~30/yr total).
        if random.random() < 0.11 * sf:
            dist = round(random.uniform(4.0, 8.0), 2)
            dur = round(dist / 0.45 + random.uniform(5, 10))
            add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=random.randint(11, 18)),
                              dur, "home", "Cologne", random.choice(["supermarket", "client office", "print shop"]),
                              "Cologne", random.choice(["errands", "business", "shopping"]),
                              "car_sharing", dist, False, False, "")
    else:
        # Weekend car-sharing errand, same short-hop pattern.
        if random.random() < 0.065 * sf:
            dist = round(random.uniform(4.0, 8.0), 2)
            dur = round(dist / 0.45 + random.uniform(5, 10))
            add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=random.randint(10, 17)),
                              dur, "home", "Cologne", random.choice(["supermarket", "hardware store"]),
                              "Cologne", "errands", "car_sharing", dist, False, False, "")
    # Light e-scooter hops on the Bolt subscription, most days - always short (well
    # under e-scooter's 8km plausibility ceiling too).
    if random.random() < 0.3 * sf:
        dur = random.randint(6, 16)
        dist = round(dur * 0.18, 2)
        add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=random.randint(10, 21)),
                          dur, "home", "Cologne", random.choice(["cafe", "friend's place", "gym"]),
                          "Cologne", random.choice(["social", "leisure"]),
                          "e_scooter", dist, False, False, nora_bolt,
                          paid_override=paid_e_scooter_bolt_unlimited(dur))

# Two rare long-distance trips a year on the BahnCard 25 (barely justifies its cost) -
# same shape as Simone's case above.
for month, day, city, base_dist in [(9, 25, "Berlin", 220), (2, 12, "Munich", 355)]:
    yr = 2025 if month >= 7 else 2026
    d = date(yr, month, day)
    dist = round(base_dist * random.uniform(0.97, 1.03), 2)
    ref = ref_long_distance_train(dist)
    paid = round(ref * 0.75, 2)
    dur = round(dist / 3.1)
    add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=8, minute=15),
                      dur, "home", "Cologne", "conference venue", city, "business",
                      "long_distance_train", dist, False, False, nora_bc25, paid_override=paid)
    add_trip_and_leg(NORA, d, datetime.min.time().replace(hour=18, minute=30),
                      dur, "conference venue", city, "home", "Cologne", "home_return",
                      "long_distance_train", dist, False, False, nora_bc25, paid_override=paid)

# Local-only calendar - routine life, no subscription implications.
add_calendar(NORA, datetime(2025, 8, 6, 18, 30, tzinfo=TZ_SUMMER), datetime(2025, 8, 6, 19, 30, tzinfo=TZ_SUMMER),
             "Yoga class", "Weekly evening yoga class at the studio near home.", "Cologne",
             "FREQ=WEEKLY;BYDAY=WE")
add_calendar(NORA, datetime(2025, 10, 9, 9, 30, tzinfo=TZ_SUMMER), datetime(2025, 10, 9, 10, 15, tzinfo=TZ_SUMMER),
             "Dentist checkup", "Routine dental checkup.", "Cologne", "")
add_calendar(NORA, datetime(2026, 1, 16, 19, 0, tzinfo=TZ), datetime(2026, 1, 16, 22, 0, tzinfo=TZ),
             "Team dinner", "Quarterly team dinner with the marketing agency.", "Cologne", "")
add_calendar(NORA, datetime(2026, 4, 11, 12, 0, tzinfo=TZ_SUMMER), datetime(2026, 4, 11, 13, 30, tzinfo=TZ_SUMMER),
             "Haircut appointment", "Trim and color at the salon.", "Cologne", "")

# Life-event calendar: an *upcoming* promotion requiring a monthly on-site day at the
# Munich HQ (dated ahead of WINDOW_END/today so the forecaster's forward-looking scan
# picks it up - see the NOTE in Jonas's section above), not yet reflected in the
# twice-a-year baseline above. Meant to flip category_subscription_analysis's
# long_distance_rail recommendation forward (today: cancel_current_go_pay_as_you_go,
# since her BahnCard 25 barely breaks even at 2 trips/yr) once the forecaster projects
# that volume rising toward monthly - a deliberate contrast with today's cancel call.
PROMOTION_DATE = date(2026, 8, 5)
MUNICH_ROLE_START = date(2026, 9, 1)
add_calendar(NORA, datetime(PROMOTION_DATE.year, PROMOTION_DATE.month, PROMOTION_DATE.day, 15, 0, tzinfo=TZ_SUMMER),
             datetime(PROMOTION_DATE.year, PROMOTION_DATE.month, PROMOTION_DATE.day, 16, 0, tzinfo=TZ_SUMMER),
             "Beförderung angenommen - Senior Marketing Manager", "Accepted a promotion to Senior "
             "Marketing Manager starting next month - the role requires a monthly on-site day at the "
             "Munich HQ.", "Cologne", "")
add_calendar(NORA, datetime(MUNICH_ROLE_START.year, MUNICH_ROLE_START.month, MUNICH_ROLE_START.day, 9, 0, tzinfo=TZ_SUMMER),
             datetime(MUNICH_ROLE_START.year, MUNICH_ROLE_START.month, MUNICH_ROLE_START.day, 17, 0, tzinfo=TZ_SUMMER),
             "Neue Rolle beginnt - erster Munich-Tag", "First day in the new Senior Marketing Manager "
             "role - starts the recurring monthly on-site day at the Munich HQ from here on.", "Munich", "")
add_calendar(NORA, datetime(2026, 9, 28, 7, 0, tzinfo=TZ_SUMMER), datetime(2026, 9, 28, 20, 0, tzinfo=TZ_SUMMER),
             "Munich HQ Tag", "Monthly on-site day at the Munich HQ - now a recurring routine as part of "
             "the new role.", "Munich", "FREQ=MONTHLY;BYDAY=4MO")

print(f"After Maja: {len(trip_rows)}")


# ===========================================================================
# Persona 6: Michael Voss — BahnCard-only regional commuter. His only
# subscription is a BahnCard 50 (no Deutschlandticket at all), covering a
# regular regional-train commute plus a handful of long-distance trips a
# year. Exists specifically to exercise the BahnCard-on-regional-train credit
# in agent/engines/analysis.py's _build_category_entry (see PERSONAS.md's
# "BahnCard-on-regional-train rule" note) with real persona data — none of
# personas 1-5 holds a BahnCard without also holding a Deutschlandticket.
# ===========================================================================
MICHAEL = uid("user:michael.voss")
add_user(MICHAEL, "michael.voss@example.com", "michaelvoss41", "Michael", "Voss",
          "1984-09-10", 41, "male", "single", "Stuttgart", "70173")
add_onboarding(
    MICHAEL, "employed_full_time", "Sales Consultant", "Tübingen", "72070", "hybrid", 0.3,
    1, "single", "medium", 120.0, True, "none", "none",
    ["regional_train", "long_distance_train"], ["car"],
    ["no_fixed_local_pass", "regional_commuter"],
    50, 65, 50,
    "Regional-train commute from Stuttgart into the Tübingen office most days on my BahnCard 50; "
    "a handful of long-distance trips a year on the same card.",
    "Rarely uses local buses or trams, so never bothered with a Deutschlandticket.",
    "I commute by regional train several times a week and use my BahnCard for the occasional "
    "long-distance trip too — I've just never needed a Deutschlandticket on top of it.",
    "Weekends are mostly on foot or with friends; barely ever uses local public transport.",
)
michael_bc50 = add_subscription(MICHAEL, SUB_BC50_2KL, "2021-05-01", True, "several_times_per_week")
# No Deutschlandticket — that's the whole point of the persona.

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        # BahnCard-covered regional commute, most weekdays.
        if random.random() < 0.8 * sf:
            dist = round(random.uniform(28.0, 34.0), 2)
            ref = ref_regional_train(dist)
            paid = round(ref * 0.5, 2)  # BahnCard 50, 50% off
            dur = round(dist / 0.8)
            add_trip_and_leg(MICHAEL, d, datetime.min.time().replace(hour=7, minute=random.randint(0, 20)),
                              dur, "home", "Stuttgart", "office", "Tübingen", "commute",
                              "regional_train", dist, True, True, michael_bc50, paid_override=paid)
            add_trip_and_leg(MICHAEL, d, datetime.min.time().replace(hour=17, minute=random.randint(30, 55)),
                              dur, "office", "Tübingen", "home", "Stuttgart", "home_return",
                              "regional_train", dist, True, True, michael_bc50, paid_override=paid)
        # Occasional local errand, pay-as-you-go, undiscounted — BahnCard never
        # covers local bus/tram — deliberately modest so the regional-train
        # credit's effect stays easy to see against a small local baseline.
        if random.random() < 0.12 * sf:
            dist = round(random.uniform(2.0, 4.0), 2)
            dur = round(dist / 0.35 + random.uniform(3, 8))
            add_trip_and_leg(MICHAEL, d, datetime.min.time().replace(hour=random.randint(12, 19)),
                              dur, "home", "Stuttgart", "supermarket", "Stuttgart", "errands",
                              "public_transport", dist, False, False, "")

# A handful of long-distance client/training trips a year, same BahnCard 50.
for month, day, city, base_dist in [(9, 9, "Frankfurt", 155), (11, 18, "Munich", 220),
                                     (3, 4, "Frankfurt", 155), (5, 20, "Cologne", 320)]:
    yr = 2025 if month >= 7 else 2026
    d = date(yr, month, day)
    dist = round(base_dist * random.uniform(0.97, 1.03), 2)
    ref = ref_long_distance_train(dist)
    paid = round(ref * 0.5, 2)
    dur = round(dist / 3.1)
    add_trip_and_leg(MICHAEL, d, datetime.min.time().replace(hour=8, minute=0),
                      dur, "home", "Stuttgart", "client site", city, "business",
                      "long_distance_train", dist, False, False, michael_bc50, paid_override=paid)
    add_trip_and_leg(MICHAEL, d, datetime.min.time().replace(hour=18, minute=0),
                      dur, "client site", city, "home", "Stuttgart", "home_return",
                      "long_distance_train", dist, False, False, michael_bc50, paid_override=paid)

print(f"After Michael: {len(trip_rows)}")


# ===========================================================================
# Persona 7: Vera Neumann — brand-new user, thin data. Only ~9 days of trip
# history near the end of the window (she just started using the app) and no
# subscriptions at all. Exists to exercise analyze_portfolio's data_warning
# ("too little data for reliable annualization", triggered when
# data_window_days < 14) with real persona data — every other persona's
# trip history spans close to the full 12-month window.
# ===========================================================================
VERA = uid("user:vera.neumann")
add_user(VERA, "vera.neumann@example.com", "veraneumann30", "Vera", "Neumann",
          "1995-12-02", 30, "female", "single", "Munich", "80331")
add_onboarding(
    VERA, "employed_full_time", "Product Marketing Manager", "Munich", "80331", "hybrid", 0.4,
    1, "single", "medium", 110.0, True, "none", "none",
    ["public_transport"], [],
    ["new_user", "no_established_pattern"],
    50, 50, 50,
    "Just moved to Munich and started commuting by bus/U-Bahn, buying single tickets so far.",
    "One or two bike-share rides while exploring the new neighbourhood.",
    "I just moved here and I'm still getting a feel for how I'll get around day to day.",
    "Too early to tell — only a week and a half of trips on record so far.",
)
# No subscriptions — too new to have picked one yet.

VERA_START = WINDOW_END - timedelta(days=8)
for d in daterange(VERA_START, WINDOW_END):
    weekday = d.weekday()
    if weekday < 5:
        dist = round(random.uniform(4.0, 7.0), 2)
        dur = round(dist / 0.45)
        add_trip_and_leg(VERA, d, datetime.min.time().replace(hour=8, minute=random.randint(0, 20)),
                          dur, "home", "Munich", "office", "Munich", "commute",
                          "public_transport", dist, True, False, "")
        add_trip_and_leg(VERA, d, datetime.min.time().replace(hour=17, minute=random.randint(15, 45)),
                          dur, "office", "Munich", "home", "Munich", "home_return",
                          "public_transport", dist, True, False, "")
    elif random.random() < 0.6:
        dur = random.randint(8, 18)
        dist = round(dur * 0.14, 2)
        add_trip_and_leg(VERA, d, datetime.min.time().replace(hour=random.randint(11, 17)),
                          dur, "home", "Munich", "neighbourhood", "Munich", "leisure",
                          "bike_sharing", dist, False, False, "")

print(f"After Vera: {len(trip_rows)}")


# ===========================================================================
# Persona 8: Claudia Herrmann — 1st-class business traveler. Her only
# subscription is a BahnCard 50, 1. Klasse; every long-distance and regional
# trip is priced with CLASS_1_MULTIPLIER and tagged ticket_class=1. Exists to
# exercise (a) travel-class matching end-to-end (never compared against a
# 2nd-class alternative) and (b) a 1st-class fare actually costing more than
# 2nd class in the reference/no-subscription baseline, not just her
# BahnCard's own (already correctly class-priced) annual fee looking more
# expensive — see CLASS_1_MULTIPLIER's module note.
# ===========================================================================
CLAUDIA = uid("user:claudia.herrmann")
add_user(CLAUDIA, "claudia.herrmann@example.com", "claudiaherrmann44", "Claudia", "Herrmann",
          "1981-02-17", 44, "female", "single", "Düsseldorf", "40213")
add_onboarding(
    CLAUDIA, "employed_full_time", "Management Consultant", "Düsseldorf", "40213", "hybrid", 0.1,
    1, "single", "high", 350.0, True, "none", "none",
    ["long_distance_train"], ["car"],
    ["frequent_travel", "values_comfort"],
    40, 55, 75,
    "Client visits across the country several times a week, always 1st class on the BahnCard 50 — "
    "the extra quiet and space is worth it for the work she gets done on the train.",
    "Local errands around Düsseldorf by bus/tram, pay-as-you-go.",
    "I travel to clients nationwide constantly, always 1st class — it's how I get real work done "
    "between meetings, so the comfort more than pays for itself.",
    "Heavy long-distance travel footprint, always 1st class, light local-only footprint at home.",
)
claudia_bc50_1kl = add_subscription(CLAUDIA, SUB_BC50_1KL, "2020-02-01", True, "several_times_per_week")

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        # Local Düsseldorf errands/short hops, pay-as-you-go, no class distinction
        # (bus/tram fares don't have a 1st/2nd-class split in this taxonomy).
        if random.random() < 0.3 * sf:
            dist = round(random.uniform(2.0, 5.0), 2)
            dur = round(dist / 0.35 + random.uniform(3, 8))
            add_trip_and_leg(CLAUDIA, d, datetime.min.time().replace(hour=random.randint(9, 20)),
                              dur, "home", "Düsseldorf", random.choice(["office", "gym", "restaurant"]),
                              "Düsseldorf", random.choice(["business", "leisure", "social"]),
                              "public_transport", dist, False, False, "")
        # 1st-class long-distance client trip, roughly 1.3 round-trips/week.
        if random.random() < 0.26 * sf:
            city, base_dist = random.choice([
                ("Frankfurt", 225), ("Munich", 610), ("Berlin", 565),
                ("Hamburg", 400), ("Stuttgart", 375), ("Cologne", 45),
            ])
            dist = round(base_dist * random.uniform(0.97, 1.03), 2)
            ref = round(ref_long_distance_train(dist) * CLASS_1_MULTIPLIER, 2)
            paid = round(ref * 0.5, 2)
            dur = round(dist / 3.1)
            add_trip_and_leg(CLAUDIA, d, datetime.min.time().replace(hour=7, minute=random.randint(0, 30)),
                              dur, "home", "Düsseldorf", "client site", city, "business",
                              "long_distance_train", dist, False, False, claudia_bc50_1kl,
                              paid_override=paid, ticket_class=1, class_multiplier=CLASS_1_MULTIPLIER)
            add_trip_and_leg(CLAUDIA, d, datetime.min.time().replace(hour=18, minute=random.randint(0, 45)),
                              dur, "client site", city, "home", "Düsseldorf", "home_return",
                              "long_distance_train", dist, False, False, claudia_bc50_1kl,
                              paid_override=paid, ticket_class=1, class_multiplier=CLASS_1_MULTIPLIER)
        # Occasional 1st-class regional trip to a nearby satellite office — also
        # BahnCard-50-covered, exercising the BahnCard-on-regional-train credit
        # for a 1st-class fare specifically (no Deutschlandticket held).
        if random.random() < 0.08 * sf:
            dist = round(random.uniform(30.0, 45.0), 2)
            ref = round(ref_regional_train(dist) * CLASS_1_MULTIPLIER, 2)
            paid = round(ref * 0.5, 2)
            dur = round(dist / 0.8)
            add_trip_and_leg(CLAUDIA, d, datetime.min.time().replace(hour=8, minute=random.randint(0, 20)),
                              dur, "home", "Düsseldorf", "satellite office", "Wuppertal", "business",
                              "regional_train", dist, False, False, claudia_bc50_1kl,
                              paid_override=paid, ticket_class=1, class_multiplier=CLASS_1_MULTIPLIER)
            add_trip_and_leg(CLAUDIA, d, datetime.min.time().replace(hour=17, minute=random.randint(0, 30)),
                              dur, "satellite office", "Wuppertal", "home", "Düsseldorf", "home_return",
                              "regional_train", dist, False, False, claudia_bc50_1kl,
                              paid_override=paid, ticket_class=1, class_multiplier=CLASS_1_MULTIPLIER)

print(f"After Claudia: {len(trip_rows)}")


# ===========================================================================
# Persona 9: Sabine Krüger — a real, stated mobility constraint (a knee
# condition ruling out cycling/standing e-scooters). Her Deutschlandticket
# covers the commute; car-sharing (pay-as-you-go, no membership) covers
# whatever public transport doesn't reach well. Exists to check that
# modal_shift.py's candidate filtering actually respects avoided_transport_
# modes/mobility_constraints (build_modal_shift_suggestions in
# agent/engines/modal_shift.py) rather than suggesting a switch to bike-
# sharing/e-scooter on cost or CO2 grounds alone — every other persona's
# mobility_constraints is "none".
# ===========================================================================
SABINE = uid("user:sabine.krueger")
add_user(SABINE, "sabine.krueger@example.com", "sabinekrueger52", "Sabine", "Krüger",
          "1973-06-25", 52, "female", "single", "Hannover", "30159")
add_onboarding(
    SABINE, "employed_full_time", "Office Administrator", "Hannover", "30159", "in_office", 0.0,
    1, "single", "medium", 100.0, True, "none", "none",
    ["public_transport", "car_sharing"], ["bike_sharing", "e_scooter"],
    ["mobility_impairment", "cannot_cycle"],
    55, 60, 55,
    "Deutschlandticket to the office every day; grabs a car-sharing car for anything public "
    "transport doesn't reach well, like the monthly physio appointment out in the suburbs.",
    "Rarely goes far outside the daily commute and the occasional car-sharing errand.",
    "I take the Deutschlandticket to work every day and use car-sharing for anything transit "
    "doesn't cover well — cycling and standing scooters aren't an option for me because of a "
    "long-standing knee condition.",
    "Steady commute footprint; car-sharing fills in the gaps transit can't reach.",
)
sabine_dt = add_subscription(SABINE, SUB_DT, "2022-08-01", True, "several_times_per_week")

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        if random.random() < 0.85 * sf:
            dist = round(random.uniform(5.0, 7.0), 2)
            dur = round(dist / 0.45)
            add_trip_and_leg(SABINE, d, datetime.min.time().replace(hour=8, minute=random.randint(0, 15)),
                              dur, "home", "Hannover", "office", "Hannover", "commute",
                              "public_transport", dist, True, True, sabine_dt, paid_override=0.0)
            add_trip_and_leg(SABINE, d, datetime.min.time().replace(hour=16, minute=random.randint(45, 59)),
                              dur, "office", "Hannover", "home", "Hannover", "home_return",
                              "public_transport", dist, True, True, sabine_dt, paid_override=0.0)
        # Car-sharing errands, pay-as-you-go, no membership — trips public
        # transport doesn't reach well.
        if random.random() < 0.09 * sf:
            dist = round(random.uniform(6.0, 12.0), 2)
            dur = round(dist / 0.45 + random.uniform(5, 10))
            add_trip_and_leg(SABINE, d, datetime.min.time().replace(hour=random.randint(10, 17)),
                              dur, "home", "Hannover", random.choice(["physio clinic", "garden centre"]),
                              "Hannover", random.choice(["healthcare", "errands"]),
                              "car_sharing", dist, False, False, "")
    elif random.random() < 0.15 * sf:
        dist = round(random.uniform(2.0, 4.0), 2)
        dur = round(dist / 0.35 + random.uniform(3, 8))
        add_trip_and_leg(SABINE, d, datetime.min.time().replace(hour=random.randint(11, 17)),
                          dur, "home", "Hannover", "market square", "Hannover", "shopping",
                          "public_transport", dist, False, False, sabine_dt, paid_override=0.0)

print(f"After Sabine: {len(trip_rows)}")


# ===========================================================================
# Persona 10: Jan Albrecht — mobility maximalist. Holds a subscription in
# every one of the 5 category buckets the system tracks (public_transport,
# long_distance_rail, bike_sharing, car_sharing, e_scooter) at once — no
# other persona holds more than 3 simultaneously. Exists to stress-test the
# full category_subscription_analysis output shape (5 populated entries,
# richest possible current_contracts list) and give modal_shift.py's
# cross-category comparison the fullest baseline to work from.
# ===========================================================================
JAN = uid("user:jan.albrecht")
add_user(JAN, "jan.albrecht@example.com", "janalbrecht37", "Jan", "Albrecht",
          "1988-11-03", 37, "male", "single", "Berlin", "10115")
add_onboarding(
    JAN, "employed_full_time", "Software Engineer", "Berlin", "10115", "hybrid", 0.5,
    1, "single", "high", 250.0, True, "none", "none",
    ["public_transport", "bike_sharing", "car_sharing", "e_scooter"], [],
    ["values_optionality", "low_cost_sensitivity"],
    55, 45, 70,
    "Deutschlandticket for the commute, BahnCard for weekend trips out of the city, a bike-share "
    "and car-share membership for whatever's fastest that day, plus an e-scooter pass for short hops.",
    "Mixes all five — whichever's quickest for the errand at hand.",
    "I like having every option available rather than optimizing hard for one — Deutschlandticket, "
    "BahnCard, bike-share, car-share, e-scooter, I hold all of them and just grab whichever fits.",
    "Broad, even footprint across every mode — options matter more to him than shaving cost.",
)
jan_dt = add_subscription(JAN, SUB_DT, "2023-01-01", True, "several_times_per_week")
jan_bc25 = add_subscription(JAN, SUB_BC25_2KL, "2023-06-01", False, "several_times_per_month")
jan_bike = add_subscription(JAN, SUB_CAB_MEMBER_PLUS, "2023-06-01", False, "several_times_per_week")
jan_car = add_subscription(JAN, SUB_TEILAUTO_VIELFAHRER, "2023-06-01", False, "several_times_per_week")
jan_scooter = add_subscription(JAN, SUB_BOLT_UNLIMITED, "2023-06-01", False, "several_times_per_week")

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    if weekday < 5:
        # DT-covered commute, most weekdays.
        if random.random() < 0.75 * sf:
            dist = round(random.uniform(5.0, 8.0), 2)
            dur = round(dist / 0.45)
            add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=8, minute=random.randint(0, 20)),
                              dur, "home", "Berlin", "office", "Berlin", "commute",
                              "public_transport", dist, True, True, jan_dt, paid_override=0.0)
            add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=17, minute=random.randint(15, 45)),
                              dur, "office", "Berlin", "home", "Berlin", "home_return",
                              "public_transport", dist, True, True, jan_dt, paid_override=0.0)
        # Car-sharing errand, teilAuto-covered.
        if random.random() < 0.1 * sf:
            dist = round(random.uniform(5.0, 12.0), 2)
            dur = round(dist / 0.45 + random.uniform(5, 15))
            paid = paid_car_sharing_teilauto(dist, dur)
            add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=random.randint(11, 18)),
                              dur, "home", "Berlin", random.choice(["hardware store", "supermarket"]),
                              "Berlin", "errands", "car_sharing", dist, False, False, jan_car,
                              paid_override=paid)
        # E-scooter hop, Bolt-covered.
        if random.random() < 0.25 * sf:
            dur = random.randint(6, 16)
            dist = round(dur * 0.18, 2)
            paid = paid_e_scooter_bolt_unlimited(dur)
            add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=random.randint(10, 21)),
                              dur, "home", "Berlin", random.choice(["cafe", "gym", "friend's place"]),
                              "Berlin", random.choice(["social", "leisure"]), "e_scooter", dist,
                              False, False, jan_scooter, paid_override=paid)
    elif random.random() < 0.35 * sf:
        # Weekend bike-share ride, Call a Bike Member Plus-covered (first 30 min
        # free, matching Simone's persona).
        dur = random.randint(10, 28)
        dist = round(dur * 0.22, 2)
        paid = paid_bike_sharing_member_plus(dur)
        add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=random.randint(10, 18)),
                          dur, "home", "Berlin", "park", "Berlin", "leisure",
                          "bike_sharing", dist, False, False, jan_bike, paid_override=paid)

# Roughly-monthly BahnCard-covered weekend trip out of the city — checked on
# Saturdays only (~52/yr) at a probability tuned for ~12 trips/yr, rather than
# stepping the date by a fixed 14 days: 14 is a multiple of 7, so a fixed-step
# loop would keep landing on the same weekday every time and (if that first
# weekday isn't a Sat/Sun) never fire at all.
for d in daterange(WINDOW_START, WINDOW_END):
    if d.weekday() == 5 and random.random() < 0.23 * season_factor(d):
        city, base_dist = random.choice([("Leipzig", 190), ("Dresden", 195), ("Hamburg", 290)])
        dist = round(base_dist * random.uniform(0.97, 1.03), 2)
        ref = ref_long_distance_train(dist)
        paid = round(ref * 0.75, 2)  # BahnCard 25, 25% off
        dur = round(dist / 3.1)
        add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=9, minute=0),
                          dur, "home", "Berlin", "weekend trip", city, "leisure",
                          "long_distance_train", dist, False, False, jan_bc25, paid_override=paid)
        add_trip_and_leg(JAN, d, datetime.min.time().replace(hour=19, minute=0),
                          dur, "weekend trip", city, "home", "Berlin", "home_return",
                          "long_distance_train", dist, False, False, jan_bc25, paid_override=paid)

print(f"After Jan: {len(trip_rows)}")
print(f"Total trips: {len(trip_rows)}, total legs: {len(leg_rows)}")


# ===========================================================================
# Write CSVs
# ===========================================================================
def write_csv(filename, header, rows):
    for i, row in enumerate(rows):
        if len(row) != len(header):
            raise ValueError(
                f"{filename}: row {i} has {len(row)} fields, header has {len(header)} "
                f"({header[0]}={row[0] if row else '?'})"
            )
    path = OUT_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


write_csv("user_profiles_v4.csv", [
    "user_id", "email", "username", "external_auth_id", "first_name", "last_name",
    "date_of_birth", "age", "gender", "life_stage", "home_city", "home_postal_code",
    "home_country_code",
], users_rows)

write_csv("user_onboardings_v4.csv", [
    "onboarding_id", "user_id", "employment_status", "occupation", "work_city",
    "work_postal_code", "work_country_code", "work_arrangement", "remote_work_share",
    "household_size", "household_type", "income_band", "mobility_budget_monthly_eur",
    "has_driving_license", "car_access", "bike_access", "preferred_transport_modes",
    "avoided_transport_modes", "mobility_constraints", "score_emission", "score_money",
    "score_flexibility", "typical_weekday_pattern", "typical_weekend_pattern",
    "travel_statement", "activity_statement",
], onboarding_rows)

write_csv("user_subscriptions_v5.csv", [
    "user_subscription_id", "user_id", "subscription_id", "valid_from", "valid_until",
    "subscription_status", "is_primary_mobility_option", "estimated_usage_frequency",
], subscription_rows)

write_csv("user_trips_v5.csv", [
    "trip_id", "user_id", "started_at", "ended_at", "duration_minutes", "origin_label",
    "origin_city", "origin_postal_code", "origin_country_code", "destination_label",
    "destination_city", "destination_postal_code", "destination_country_code",
    "trip_purpose", "trip_purpose_other", "main_transport_mode", "main_transport_mode_other",
    "estimated_distance_km", "is_commute", "is_intermodal", "is_recurring_pattern",
], trip_rows)

write_csv("trip_legs_v8.csv", [
    "leg_id", "trip_id", "user_id", "user_subscription_id", "leg_sequence_number",
    "started_at", "ended_at", "duration_minutes", "origin_label", "origin_city",
    "origin_postal_code", "origin_country_code", "destination_label", "destination_city",
    "destination_postal_code", "destination_country_code", "transport_mode", "ticket_type",
    "ticket_class", "ticket_purchased_at", "estimated_distance_km", "estimated_cost_eur",
    "reference_cost_eur", "estimated_co2_emissions", "is_access_leg", "is_main_leg",
    "is_egress_leg", "is_transfer_leg", "wait_time_minutes", "transfer_count_before_leg",
], leg_rows)

write_csv("user_calendars_v2.csv", [
    "calendar_id", "user_id", "component_type", "uid", "dtstamp", "dtstart", "dtend",
    "duration", "summary", "description", "location", "url", "class", "status", "transp",
    "priority", "created", "last_modified", "sequence", "rrule", "rdate", "exdate",
    "recurrence_id", "organizer", "attendee", "categories", "comment", "contact",
    "related_to", "resources", "request_status", "geo", "attach", "valarm", "parameters",
    "x_properties", "raw_icalendar", "inserted_at", "updated_at",
], calendar_rows)

print("\nPersona user_ids:")
print("Julia Berger:", JULIA)
print("Jonas Keller:", JONAS)
print("Simone Wagner:", SIMONE)
print("Elif Yildiz:", ELIF)
print("Maja Hoffmann:", NORA)
print("Michael Voss:", MICHAEL)
print("Vera Neumann:", VERA)
print("Claudia Herrmann:", CLAUDIA)
print("Sabine Krüger:", SABINE)
print("Jan Albrecht:", JAN)
