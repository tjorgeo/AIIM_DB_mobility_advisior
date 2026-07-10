"""Generator for the 4-persona replacement seed dataset.

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


REF_FN = {
    "public_transport": lambda km, minutes: ref_public_transport(km),
    "regional_train": lambda km, minutes: ref_regional_train(km),
    "long_distance_train": lambda km, minutes: ref_long_distance_train(km),
    "bike_sharing": lambda km, minutes: ref_bike_sharing(minutes),
    "car_sharing": lambda km, minutes: ref_car_sharing(km),
    "e_scooter": lambda km, minutes: ref_e_scooter(minutes),
}

# ---------------------------------------------------------------------------
# Subscription catalog references (subscription_catalogs_v1.csv, unchanged)
# ---------------------------------------------------------------------------
SUB_DT = "a1111111-1111-1111-1111-111111111111"          # Deutschlandticket, 63/mo, flat
SUB_BC25_2KL = "a3333333-3333-3333-3333-333333333333"     # BahnCard 25, 2. Klasse, 62.90/yr
SUB_BC50_2KL = "d1111111-1111-1111-1111-111111111111"     # BahnCard 50, 2. Klasse, 244.00/yr
SUB_CAB_MEMBER_PLUS = "m1111111-1111-1111-1111-111111111111"  # Call a Bike Member Plus, 8/mo (96/yr)
SUB_TEILAUTO_VIELFAHRER = "x1111111-1111-1111-1111-111111111111"  # teilAuto Vielfahrertarif, 30/mo (360/yr)

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
                      is_recurring, user_subscription_id, paid_override=None):
    """Creates one trip + one leg (1:1, matching existing dataset convention).
    paid_override: if given, use this as estimated_cost_eur instead of the
    reference price (subscription-covered legs)."""
    tz = tz_for(day)
    started_at = datetime.combine(day, start_time, tzinfo=tz)
    ended_at = started_at + timedelta(minutes=duration_min)

    seq_key = (user_id, day.isoformat())
    _trip_seq[seq_key] = _trip_seq.get(seq_key, 0) + 1
    trip_id = uid(f"trip:{user_id}:{started_at.isoformat()}:{_trip_seq[seq_key]}")
    leg_id = uid(f"leg:{trip_id}")

    reference_cost = REF_FN[mode](distance_km, duration_min)
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
        mode, ticket_type, "", "", distance_km, estimated_cost, reference_cost, co2,
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

print(f"Julia trips so far: {len(trip_rows)}")


# ===========================================================================
# Persona 2: Jonas Keller — holds no subscription at all, pure pay-as-you-go.
# Moved apartment further from the office partway through the window, which
# increased his commute distance/frequency from that point on - a calendar
# life-event that explains the trip-history trend and reinforces that a
# Deutschlandticket would pay off going forward, not just in hindsight.
# ===========================================================================
JONAS = uid("user:jonas.keller")
add_user(JONAS, "jonas.keller@example.com", "jonaskeller28", "Jonas", "Keller",
          "1998-03-14", 28, "male", "single", "Hamburg", "22850")
add_onboarding(
    JONAS, "employed_full_time", "Junior Data Analyst", "Hamburg", "20095", "in_office", 0.05,
    1, "single", "medium", 90.0, True, "none", "none",
    ["public_transport", "regional_train"], ["car"],
    ["recently_relocated", "no_fixed_pass"],
    50, 70, 45,
    "Commutes into the Hamburg office by bus/S-Bahn most days, buying single tickets each time.",
    "Occasional single-ticket trips into the city, biweekly regional-train visit to his parents.",
    "I've never bothered with a pass since I used to live close to the office - now that I've moved "
    "further out the single tickets are adding up fast.",
    "Regular commuter footprint that recently got noticeably longer after a move.",
)
# No subscriptions at all for Jonas.

MOVE_DATE = date(2026, 1, 10)
PARENTS_TOWN = ("Lüneburg", 55)

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    moved = d >= MOVE_DATE
    if weekday < 5:
        commute_prob = (0.90 if moved else 0.80) * sf
        if random.random() < commute_prob:
            if moved:
                # Longer commute post-move: regional train from the new, farther-out address.
                dist = round(random.uniform(16.0, 19.0), 2)
                dur = round(dist / 0.65)
                mode = "regional_train"
            else:
                # Short in-city commute pre-move: bus/S-Bahn within Hamburg.
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

# Life-event + trip-affecting calendar: the move itself, plus recurring items
# that explain/forecast the post-move commute pattern.
add_calendar(JONAS, datetime(2026, 1, 10, 9, 0, tzinfo=TZ), datetime(2026, 1, 10, 18, 0, tzinfo=TZ),
             "Umzug - neue Wohnung in Norderstedt", "Moving day into the new, farther-out apartment.",
             "Hamburg", "")
add_calendar(JONAS, datetime(2025, 12, 20, 12, 0, tzinfo=TZ), datetime(2025, 12, 20, 13, 0, tzinfo=TZ),
             "Wohnungsbesichtigung Norderstedt", "Apartment viewing ahead of the move.", "Hamburg", "")
add_calendar(JONAS, datetime(2025, 7, 13, 9, 0, tzinfo=TZ_SUMMER), datetime(2025, 7, 13, 19, 0, tzinfo=TZ_SUMMER),
             "Besuch bei den Eltern", "Biweekly weekend visit to parents in Lüneburg by regional train.",
             "Lüneburg", "FREQ=WEEKLY;INTERVAL=2;BYDAY=SU")
add_calendar(JONAS, datetime(2026, 2, 2, 9, 0, tzinfo=TZ), datetime(2026, 2, 2, 17, 30, tzinfo=TZ),
             "Team onboarding new office wing", "Full-day in-office event, no working from home that day.",
             "Hamburg", "")

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

print(f"After Simone: {len(trip_rows)}")


# ===========================================================================
# Persona 4: Elif Yildiz — car-free freelancer whose mobility centers on a
# heavily-used car-sharing membership, topped up with pay-as-you-go e-scooter
# and bike-share for short hops. Currently mid-way through a home renovation,
# which is driving a burst of extra car-sharing hauling trips visible in both
# the calendar and the trip history.
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

RENOVATION_START, RENOVATION_END = date(2026, 4, 1), date(2026, 5, 31)
PARENTS_TOWN_2 = ("Oldenburg", 45)

for d in daterange(WINDOW_START, WINDOW_END):
    sf = season_factor(d)
    weekday = d.weekday()
    in_renovation = RENOVATION_START <= d <= RENOVATION_END

    # Car-sharing trips for client visits/supply runs, several times/week.
    base_prob = 0.55 if weekday < 5 else 0.35
    if in_renovation:
        base_prob += 0.35  # extra hardware-store / hauling runs during the renovation
    if random.random() < base_prob * sf:
        dist = round(random.uniform(5.0, 14.0), 2)
        dur = round(dist / 0.35 + random.uniform(5, 15))
        purpose = "errands" if in_renovation else random.choice(["business", "shopping", "errands"])
        dest = "hardware store" if in_renovation else random.choice(["client studio", "supplier", "print shop"])
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

# Life-event / trip-affecting calendar: the renovation project plus a recurring
# family visit, both of which show up as extra trips in the history above.
add_calendar(ELIF, datetime(2026, 4, 1, 8, 0, tzinfo=TZ_SUMMER), datetime(2026, 5, 31, 18, 0, tzinfo=TZ_SUMMER),
             "Studio renovation project", "Home studio renovation - frequent hardware-store runs by "
             "car-sharing for the next two months.", "Bremen", "")
add_calendar(ELIF, datetime(2026, 3, 25, 14, 0, tzinfo=TZ_SUMMER), datetime(2026, 3, 25, 15, 0, tzinfo=TZ_SUMMER),
             "Contractor walkthrough", "Meeting the contractor to scope the studio renovation.", "Bremen", "")
add_calendar(ELIF, datetime(2025, 7, 20, 10, 0, tzinfo=TZ_SUMMER), datetime(2025, 7, 20, 18, 0, tzinfo=TZ_SUMMER),
             "Family visit - Oldenburg", "Monthly weekend visit to parents in Oldenburg.", "Oldenburg",
             "FREQ=MONTHLY")
add_calendar(ELIF, datetime(2025, 9, 6, 11, 0, tzinfo=TZ_SUMMER), datetime(2025, 9, 6, 15, 0, tzinfo=TZ_SUMMER),
             "Design fair - client booth", "Staffing a client's booth at the local design fair.", "Bremen", "")

print(f"After Elif: {len(trip_rows)}")
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
