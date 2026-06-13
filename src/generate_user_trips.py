import uuid
from typing import Any
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
from university_api_connection import call_university_gpt
from generate_user_profiles import parse_json_response

def ensure_user_ids(user_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Ensures that every generated user profile has a stable user_id.
    This user_id can later be used as foreign key for trips and purchases.
    """

    for user_profile in user_profiles:
        if not user_profile.get("user_id"):
            user_profile["user_id"] = str(uuid.uuid4())

    return user_profiles

import json
from typing import Any


SYSTEM_PROMPT_GENERATE_TRIPS = """
You generate synthetic trip history data for a mobility advisor application.

Your task:
Create realistic trip records for exactly one user profile and one time interval.

Important rules:
- Use the concrete user_profile as the source of truth.
- Trips must be consistent with the user's mobility_profile, job_related profile, activity_profile, ticketing_profile and user statements.
- Generate plausible German mobility behavior.
- Create realistic timestamps within the requested interval.
- Weekday trips should reflect commute frequency and working pattern.
- Evening and weekend trips should reflect the activity profile.
- Ticket usage should be consistent with the user's ticketing profile.
- Do not create impossible or contradictory trips.
- Return only valid JSON.
- Do not include markdown.
- Do not include explanations outside the JSON object.
"""


def build_trip_history_prompt(
    user_profile: dict[str, Any],
    start_ts: str,
    end_ts: str,
    num_trips: int,
) -> str:
    """
    Builds a prompt for generating trip history for one user profile.
    """

    return f"""
Generate a realistic trip history for the following user profile.

Time interval:
- start_ts: {start_ts}
- end_ts: {end_ts}

Number of trips to generate:
{num_trips}

Important:
- A main trip represents a complete door-to-door journey, for example Home to Work.
- Each main trip must contain one or more trip legs.
- Trip legs represent the individual movement segments within the main trip, for example walking to a station, subway ride, walking to the office.
- Do not count legs as separate main trips.
- Generate exactly {num_trips} main trips.



User profile:
{json.dumps(user_profile, ensure_ascii=False, indent=2)}

Return exactly one JSON object with this structure:

{{
  "user_id": "string",
  "source_persona_id": "string",
  "trip_generation_summary": "string",
  "trips": [
    {{
      "trip_id": "string",
      "user_id": "string",

      "start_ts": "YYYY-MM-DDTHH:MM:SS",
      "end_ts": "YYYY-MM-DDTHH:MM:SS",
      "weekday": "monday | tuesday | wednesday | thursday | friday | saturday | sunday",

      "origin": {{
        "city": "string",
        "place_type": "home | work | education | restaurant | cafe | fitness | shopping | park | cinema | culture | family_visit | errands | station | other",
        "label": "short realistic place label"
      }},

      "destination": {{
        "city": "string",
        "place_type": "home | work | education | restaurant | cafe | fitness | shopping | park | cinema | culture | family_visit | errands | station | other",
        "label": "short realistic place label"
      }},

      "trip_purpose": "commute | work_related | education | shopping | leisure | errands | family | return_home | other",

      "main_mode": "walking | bike | public_transport | subway | tram | bus | regional_train | car | car_sharing | ride_hailing | shared_bike | shared_scooter",

      "modes_used": [
        "walking",
        "bike",
        "public_transport",
        "subway",
        "tram",
        "bus",
        "regional_train",
        "car",
        "car_sharing",
        "ride_hailing",
        "shared_bike",
        "shared_scooter"
      ],

      "distance_km": 0.0,
      "duration_min": 0,
      "estimated_cost_eur": 0.0,

      "ticket_product_used": "none | single_ticket | short_trip_ticket | day_ticket | weekly_pass | monthly_pass | subscription | student_pass | job_ticket",

      "is_commute": true,
      "is_recurring_pattern": true,

      "planning_style": "planned | spontaneous | routine",
      "priority_reason": "short explanation why this trip fits the user's travel behavior and priorities",
      
      "legs": [
        {{
          "leg_id": "string",
          "trip_id": "string",
          "sequence_no": 1,

          "start_ts": "YYYY-MM-DDTHH:MM:SS",
          "end_ts": "YYYY-MM-DDTHH:MM:SS",

          "mode": "walking | bike | public_transport | subway | tram | bus | regional_train | car | car_sharing | ride_hailing | shared_bike | shared_scooter",

          "origin_label": "string",
          "destination_label": "string",

          "distance_km": 0.0,
          "duration_min": 0,

          "ticket_required": true,
          "ticket_product_used": "none | single_ticket | short_trip_ticket | day_ticket | weekly_pass | monthly_pass | subscription | student_pass | job_ticket",

          "leg_note": "short explanation of this segment"
        }}
      ],

      "priority_reason": "short explanation why this trip fits the user's travel behavior and priorities"
    }}
  ]
}}

Generation requirements:
- Generate exactly {num_trips} main trips.
- Every trip.user_id must equal the user_profile.user_id.
- Every leg.trip_id must equal its parent trip.trip_id.
- Every trip must contain at least one leg.
- Single-mode trips should have exactly one leg.
- Public transport trips should usually have 2 to 4 legs, for example walking → subway → walking.
- Car trips should usually have one leg, unless walking from parking to destination is relevant.
- Bike trips should usually have one leg.
- Shared mobility trips may have walking access or egress legs.
- main_mode must be the dominant mode by distance or importance.
- modes_used must be derived from the leg modes in sequence.
- trip.start_ts must equal the start_ts of the first leg.
- trip.end_ts must equal the end_ts of the last leg.
- trip.distance_km should approximately equal the sum of leg distances.
- trip.duration_min should approximately equal the full door-to-door duration including transfers or short waits.
- Leg sequence_no must start at 1 and increase without gaps.
- Leg timestamps must be chronological and non-overlapping.
- All start_ts and end_ts values must be inside the requested interval.
- end_ts must be after start_ts.
- Use realistic trip durations and distances.
- Use the user's home city as the main city unless the profile clearly supports regional trips.
- For hybrid workers, do not generate daily office commutes unless commute_frequency supports it.
- For remote workers, generate few or no commute trips.
- For users with high public transport affinity, public transport should appear often.
- For users with bike ownership and bike preference, include bike trips where plausible.
- For users with car ownership and suburban or family behavior, include car trips where plausible.
- For users with subscriptions, monthly passes, student passes or job tickets, most public transport legs should use that product and have low or zero marginal cost.
- For users without a subscription, use single tickets, day tickets or short-trip tickets when public transport is used.
- Include return-home trips where realistic.
- Use activity_profile and user_statements.travel_and_priorities to determine leisure and evening trips.
- Do not mention synthetic data in the output.
- Return only the JSON object. No markdown. No code block.

Trip-leg consistency rules:
- Generate the legs first, then derive the parent trip fields from the legs.
- trip.start_ts must be copied exactly from legs[0].start_ts.
- trip.end_ts must be copied exactly from legs[-1].end_ts.
- trip.modes_used must be exactly the list of leg.mode values in sequence.
- trip.distance_km must approximately equal the sum of leg.distance_km values.
- trip.duration_min must represent the full door-to-door duration from trip.start_ts to trip.end_ts, including transfer or waiting time.
- Do not invent a separate trip.start_ts or trip.end_ts after generating the legs.
- Before returning the JSON, verify every trip with this checklist:
  1. Does trip.start_ts equal the first leg start_ts exactly?
  2. Does trip.end_ts equal the last leg end_ts exactly?
  3. Does every leg.trip_id equal the parent trip_id?
  4. Do sequence_no values start at 1 and increase without gaps?
  5. Does modes_used equal the ordered leg modes?
- If any checklist item fails, fix the parent trip fields before returning the JSON.
"""


def generate_trip_history_for_user_profile(
    client: Any,
    user_profile: dict[str, Any],
    start_ts: str,
    end_ts: str,
    num_trips: int,
) -> list[dict[str, Any]]:
    """
    Generates trip history for one user profile and one time interval.
    """

    if not user_profile.get("user_id"):
        raise ValueError("user_profile must contain user_id. Run ensure_user_ids first.")

    user_prompt = build_trip_history_prompt(
        user_profile=user_profile,
        start_ts=start_ts,
        end_ts=end_ts,
        num_trips=num_trips,
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT_GENERATE_TRIPS,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    response_text = call_university_gpt(
        client,
        messages=messages,
        max_new_tokens=4000,
        temperature=0.3,
    )

    parsed_response = parse_json_response(response_text)

    trips = parsed_response.get("trips")

    if not isinstance(trips, list):
        raise ValueError(f"Response does not contain a valid trips list:\n{response_text}")
    
    trips = normalize_trip_parent_fields(trips)

    validate_generated_trips(
        trips=trips,
        expected_user_id=user_profile["user_id"],
        expected_num_trips=num_trips,
    )

    return trips


def validate_generated_trips(
    trips: list[dict[str, Any]],
    expected_user_id: str,
    expected_num_trips: int,
) -> None:
    """
    Lightweight validation for generated main trips and nested trip legs.
    """

    if len(trips) != expected_num_trips:
        raise ValueError(
            f"Expected {expected_num_trips} main trips, got {len(trips)}."
        )

    required_trip_keys = [
        "trip_id",
        "user_id",
        "start_ts",
        "end_ts",
        "weekday",
        "origin",
        "destination",
        "trip_purpose",
        "main_mode",
        "modes_used",
        "distance_km",
        "duration_min",
        "estimated_cost_eur",
        "ticket_product_used",
        "is_commute",
        "is_recurring_pattern",
        "planning_style",
        "legs",
        "priority_reason",
    ]

    required_leg_keys = [
        "leg_id",
        "trip_id",
        "sequence_no",
        "start_ts",
        "end_ts",
        "mode",
        "origin_label",
        "destination_label",
        "distance_km",
        "duration_min",
        "ticket_required",
        "ticket_product_used",
        "leg_note",
    ]

    for trip_index, trip in enumerate(trips, start=1):
        missing_trip_keys = [
            key for key in required_trip_keys
            if key not in trip
        ]

        if missing_trip_keys:
            raise ValueError(
                f"Trip at index {trip_index} is missing keys: {missing_trip_keys}"
            )

        if trip["user_id"] != expected_user_id:
            raise ValueError(
                f"Trip at index {trip_index} has wrong user_id: {trip['user_id']}"
            )

        trip_start = datetime.fromisoformat(trip["start_ts"])
        trip_end = datetime.fromisoformat(trip["end_ts"])

        if trip_end <= trip_start:
            raise ValueError(
                f"Trip at index {trip_index} has end_ts before or equal start_ts."
            )

        legs = trip["legs"]

        if not isinstance(legs, list) or not legs:
            raise ValueError(
                f"Trip at index {trip_index} must contain at least one leg."
            )

        previous_leg_end = None
        leg_modes = []

        for expected_sequence_no, leg in enumerate(legs, start=1):
            missing_leg_keys = [
                key for key in required_leg_keys
                if key not in leg
            ]

            if missing_leg_keys:
                raise ValueError(
                    f"Leg {expected_sequence_no} in trip {trip['trip_id']} "
                    f"is missing keys: {missing_leg_keys}"
                )

            if leg["trip_id"] != trip["trip_id"]:
                raise ValueError(
                    f"Leg {leg['leg_id']} has wrong trip_id: {leg['trip_id']}"
                )

            if leg["sequence_no"] != expected_sequence_no:
                raise ValueError(
                    f"Leg {leg['leg_id']} has sequence_no {leg['sequence_no']}, "
                    f"expected {expected_sequence_no}."
                )

            leg_start = datetime.fromisoformat(leg["start_ts"])
            leg_end = datetime.fromisoformat(leg["end_ts"])

            if leg_end <= leg_start:
                raise ValueError(
                    f"Leg {leg['leg_id']} has end_ts before or equal start_ts."
                )

            if previous_leg_end and leg_start < previous_leg_end:
                raise ValueError(
                    f"Leg {leg['leg_id']} overlaps with the previous leg."
                )

            previous_leg_end = leg_end
            leg_modes.append(leg["mode"])

            if leg["duration_min"] <= 0:
                raise ValueError(
                    f"Leg {leg['leg_id']} has non-positive duration_min."
                )

            if leg["distance_km"] < 0:
                raise ValueError(
                    f"Leg {leg['leg_id']} has negative distance_km."
                )

        if trip["start_ts"] != legs[0]["start_ts"]:
            raise ValueError(
                f"Trip {trip['trip_id']} start_ts must equal first leg start_ts."
            )

        if trip["end_ts"] != legs[-1]["end_ts"]:
            raise ValueError(
                f"Trip {trip['trip_id']} end_ts must equal last leg end_ts."
            )

        if trip["modes_used"] != leg_modes:
            raise ValueError(
                f"Trip {trip['trip_id']} modes_used must equal leg modes in sequence. "
                f"Expected {leg_modes}, got {trip['modes_used']}."
            )

def generate_trips_for_user_profiles(
    client: Any,
    user_profiles: list[dict[str, Any]],
    start_ts: str,
    end_ts: str,
    trips_per_user: int,
) -> list[dict[str, Any]]:
    """
    Generates trips for multiple user profiles.
    """

    if trips_per_user < 1:
        raise ValueError("trips_per_user must be >= 1")

    user_profiles = ensure_user_ids(user_profiles)

    all_trips: list[dict[str, Any]] = []

    for user_index, user_profile in enumerate(user_profiles, start=1):
        user_id = user_profile["user_id"]
        display_name = user_profile.get("person_information", {}).get("display_name", "unknown user")

        print(
            f"Generating {trips_per_user} trips for user "
            f"{user_index}/{len(user_profiles)}: {display_name} ({user_id})"
        )

        trips = generate_trip_history_for_user_profile(
            client=client,
            user_profile=user_profile,
            start_ts=start_ts,
            end_ts=end_ts,
            num_trips=trips_per_user,
        )

        all_trips.extend(trips)

    return all_trips


def save_trips_and_legs_to_csv(
    trips: list[dict[str, Any]],
    trips_output_path: str | Path,
    legs_output_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Saves main trips and trip legs into two separate CSV files.
    """

    if not trips:
        raise ValueError("trips list is empty.")

    trip_rows, leg_rows = split_trips_and_legs(trips)

    df_trips = pd.json_normalize(trip_rows)
    df_legs = pd.json_normalize(leg_rows)

    for df in [df_trips, df_legs]:
        list_columns = [
            column for column in df.columns
            if df[column].apply(lambda value: isinstance(value, list)).any()
        ]

        for column in list_columns:
            df[column] = df[column].apply(
                lambda value: "|".join(value) if isinstance(value, list) else value
            )

    trips_path = Path(trips_output_path)
    legs_path = Path(legs_output_path)

    trips_path.parent.mkdir(parents=True, exist_ok=True)
    legs_path.parent.mkdir(parents=True, exist_ok=True)

    df_trips.to_csv(trips_path, index=False, encoding="utf-8")
    df_legs.to_csv(legs_path, index=False, encoding="utf-8")

    print(f"Saved {len(df_trips)} trips to CSV: {trips_path}")
    print(f"Saved {len(df_legs)} trip legs to CSV: {legs_path}")

    return df_trips, df_legs

def split_trips_and_legs(
    trips: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Splits nested trip history into flat trip rows and trip leg rows.
    """

    trip_rows: list[dict[str, Any]] = []
    leg_rows: list[dict[str, Any]] = []

    for trip in trips:
        trip_copy = trip.copy()
        legs = trip_copy.pop("legs", [])

        trip_rows.append(trip_copy)

        for leg in legs:
            leg_rows.append(leg)

    return trip_rows, leg_rows

from datetime import datetime
from typing import Any


def normalize_trip_parent_fields(trips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalizes parent trip fields based on nested trip legs.

    This fixes common LLM inconsistencies such as:
    - trip.end_ts != last leg end_ts
    - trip.start_ts != first leg start_ts
    - modes_used not matching leg modes
    - duration_min not matching door-to-door duration
    """

    for trip in trips:
        legs = trip.get("legs", [])

        if not legs:
            continue

        legs = sorted(legs, key=lambda leg: leg["sequence_no"])
        trip["legs"] = legs

        first_leg = legs[0]
        last_leg = legs[-1]

        trip["start_ts"] = first_leg["start_ts"]
        trip["end_ts"] = last_leg["end_ts"]

        trip["modes_used"] = [
            leg["mode"]
            for leg in legs
        ]

        start = datetime.fromisoformat(trip["start_ts"])
        end = datetime.fromisoformat(trip["end_ts"])

        trip["duration_min"] = int((end - start).total_seconds() / 60)

        trip["distance_km"] = round(
            sum(float(leg.get("distance_km", 0)) for leg in legs),
            2
        )

    return trips

from datetime import datetime, timedelta
from typing import Any


def reassign_trip_and_leg_ids(
    trips: list[dict[str, Any]],
    user_id: str,
    start_trip_index: int = 1,
) -> list[dict[str, Any]]:
    """
    Reassigns unique trip_id and leg_id values after batch generation.

    This is important because the model may generate trip_001, trip_002, ...
    in every batch, which would create duplicate IDs when batches are combined.
    """

    safe_user_id = user_id.replace("-", "")[:12]

    trips = sorted(
        trips,
        key=lambda trip: trip.get("start_ts", "")
    )

    for offset, trip in enumerate(trips):
        trip_index = start_trip_index + offset
        new_trip_id = f"trip_{safe_user_id}_{trip_index:05d}"

        trip["trip_id"] = new_trip_id
        trip["user_id"] = user_id

        legs = trip.get("legs", [])

        legs = sorted(
            legs,
            key=lambda leg: leg.get("sequence_no", 0)
        )

        for leg_index, leg in enumerate(legs, start=1):
            leg["trip_id"] = new_trip_id
            leg["sequence_no"] = leg_index
            leg["leg_id"] = f"{new_trip_id}_leg_{leg_index:03d}"

        trip["legs"] = legs

    return trips


def generate_full_trip_history(
    client: Any,
    user_profile: dict[str, Any],
    start_ts: str,
    num_trips: int,
    interval_days: int = 7,
    trips_per_interval: int = 15,
) -> list[dict[str, Any]]:
    """
    Generates a full trip history for one user profile.

    The function generates trips in smaller time intervals instead of one large call.

    Example:
    - start_ts = "2026-01-01T00:00:00"
    - num_trips = 60
    - interval_days = 7
    - trips_per_interval = 15

    Result:
    - 4 calls
    - each call generates 15 trips
    - each call covers one week
    """

    if not user_profile.get("user_id"):
        raise ValueError("user_profile must contain user_id. Run ensure_user_ids first.")

    if num_trips < 1:
        raise ValueError("num_trips must be >= 1")

    if interval_days < 1:
        raise ValueError("interval_days must be >= 1")

    if trips_per_interval < 1:
        raise ValueError("trips_per_interval must be >= 1")

    user_id = user_profile["user_id"]

    current_start_dt = datetime.fromisoformat(start_ts)

    remaining_trips = num_trips
    all_trips: list[dict[str, Any]] = []

    batch_index = 1
    next_trip_index = 1

    while remaining_trips > 0:
        batch_num_trips = min(trips_per_interval, remaining_trips)

        current_end_dt = (
            current_start_dt
            + timedelta(days=interval_days)
            - timedelta(seconds=1)
        )

        batch_start_ts = current_start_dt.isoformat(timespec="seconds")
        batch_end_ts = current_end_dt.isoformat(timespec="seconds")

        print(
            f"Generating batch {batch_index}: "
            f"{batch_num_trips} trips from {batch_start_ts} to {batch_end_ts}"
        )

        batch_trips = generate_trip_history_for_user_profile(
            client=client,
            user_profile=user_profile,
            start_ts=batch_start_ts,
            end_ts=batch_end_ts,
            num_trips=batch_num_trips,
        )

        # Optional but recommended if you already implemented this function
        batch_trips = normalize_trip_parent_fields(batch_trips)

        batch_trips = reassign_trip_and_leg_ids(
            trips=batch_trips,
            user_id=user_id,
            start_trip_index=next_trip_index,
        )

        for trip in batch_trips:
            trip["generation_batch_index"] = batch_index
            trip["generation_interval_start_ts"] = batch_start_ts
            trip["generation_interval_end_ts"] = batch_end_ts

        all_trips.extend(batch_trips)

        remaining_trips -= batch_num_trips
        next_trip_index += batch_num_trips
        batch_index += 1

        current_start_dt = current_start_dt + timedelta(days=interval_days)

    all_trips = sorted(
        all_trips,
        key=lambda trip: trip.get("start_ts", "")
    )

    if len(all_trips) != num_trips:
        raise ValueError(
            f"Expected {num_trips} trips, got {len(all_trips)}."
        )

    return all_trips

def generate_full_trip_history_for_user_profiles(
    client: Any,
    user_profiles: list[dict[str, Any]],
    start_ts: str,
    num_trips_per_user: int,
    interval_days: int = 7,
    trips_per_interval: int = 15,
) -> list[dict[str, Any]]:
    """
    Generates full trip histories for multiple user profiles.
    """

    user_profiles = ensure_user_ids(user_profiles)

    all_trips: list[dict[str, Any]] = []

    for user_index, user_profile in enumerate(user_profiles, start=1):
        display_name = user_profile.get("person_information", {}).get(
            "display_name",
            "unknown user"
        )

        print(
            f"Generating full trip history for user "
            f"{user_index}/{len(user_profiles)}: {display_name}"
        )

        trips = generate_full_trip_history(
            client=client,
            user_profile=user_profile,
            start_ts=start_ts,
            num_trips=num_trips_per_user,
            interval_days=interval_days,
            trips_per_interval=trips_per_interval,
        )

        all_trips.extend(trips)

    return all_trips