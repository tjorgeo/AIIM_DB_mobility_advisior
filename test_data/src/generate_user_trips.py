import uuid
from typing import Any
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import ast
from utils.university_api_connection import call_university_gpt
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

def load_checkpoint(checkpoint_path: str | Path) -> dict[str, Any]:
    path = Path(checkpoint_path)

    if not path.exists():
        return {
            "completed_batches": [],
            "trips": [],
            "errors": []
        }

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_checkpoint(
    checkpoint: dict[str, Any],
    checkpoint_path: str | Path,
) -> None:
    """
    Saves checkpoint atomically to avoid corrupt files.
    """

    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")

    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(checkpoint, file, ensure_ascii=False, indent=2)

    tmp_path.replace(path)


def make_batch_key(user_id: str, batch_index: int) -> str:
    return f"{user_id}__batch_{batch_index}"

def validate_single_trip(
    trip: dict[str, Any],
    expected_user_id: str,
) -> list[str]:
    """
    Returns a list of validation errors.
    Empty list means the trip is valid.
    """

    errors = []

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

    for key in required_trip_keys:
        if key not in trip:
            errors.append(f"Missing trip key: {key}")

    if errors:
        return errors

    if trip["user_id"] != expected_user_id:
        errors.append(
            f"Wrong user_id: expected {expected_user_id}, got {trip['user_id']}"
        )

    try:
        trip_start = datetime.fromisoformat(trip["start_ts"])
        trip_end = datetime.fromisoformat(trip["end_ts"])

        if trip_end <= trip_start:
            errors.append("trip.end_ts must be after trip.start_ts")

    except Exception as exc:
        errors.append(f"Invalid trip timestamps: {exc}")

    legs = trip.get("legs")

    if not isinstance(legs, list) or not legs:
        errors.append("Trip must contain at least one leg")
        return errors

    previous_leg_end = None
    leg_modes = []

    for expected_sequence_no, leg in enumerate(legs, start=1):
        for key in required_leg_keys:
            if key not in leg:
                errors.append(
                    f"Leg {expected_sequence_no} missing key: {key}"
                )

        if errors:
            continue

        if leg["trip_id"] != trip["trip_id"]:
            errors.append(
                f"Leg {leg.get('leg_id')} has wrong trip_id"
            )

        if leg["sequence_no"] != expected_sequence_no:
            errors.append(
                f"Leg {leg.get('leg_id')} has wrong sequence_no"
            )

        try:
            leg_start = datetime.fromisoformat(leg["start_ts"])
            leg_end = datetime.fromisoformat(leg["end_ts"])

            if leg_end <= leg_start:
                errors.append(
                    f"Leg {leg.get('leg_id')} end_ts must be after start_ts"
                )

            if previous_leg_end and leg_start < previous_leg_end:
                errors.append(
                    f"Leg {leg.get('leg_id')} overlaps with previous leg"
                )

            previous_leg_end = leg_end

        except Exception as exc:
            errors.append(
                f"Invalid leg timestamps in {leg.get('leg_id')}: {exc}"
            )

        if leg.get("duration_min", 0) <= 0:
            errors.append(
                f"Leg {leg.get('leg_id')} has non-positive duration_min"
            )

        if float(leg.get("distance_km", 0)) < 0:
            errors.append(
                f"Leg {leg.get('leg_id')} has negative distance_km"
            )

        leg_modes.append(leg["mode"])

    if legs:
        if trip["start_ts"] != legs[0]["start_ts"]:
            errors.append("trip.start_ts must equal first leg start_ts")

        if trip["end_ts"] != legs[-1]["end_ts"]:
            errors.append("trip.end_ts must equal last leg end_ts")

        if trip["modes_used"] != leg_modes:
            errors.append(
                f"trip.modes_used must equal leg modes. Expected {leg_modes}, got {trip['modes_used']}"
            )

    if trip.get("duration_min", 0) <= 0:
        errors.append("Trip has non-positive duration_min")

    if float(trip.get("distance_km", 0)) < 0:
        errors.append("Trip has negative distance_km")

    return errors

def filter_valid_trips(
    trips: list[dict[str, Any]],
    expected_user_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Splits trips into valid trips and invalid trip error records.
    """

    valid_trips = []
    invalid_trip_errors = []

    for trip in trips:
        trip_id = trip.get("trip_id", "unknown_trip")

        errors = validate_single_trip(
            trip=trip,
            expected_user_id=expected_user_id,
        )

        if errors:
            invalid_trip_errors.append({
                "trip_id": trip_id,
                "user_id": expected_user_id,
                "errors": errors,
                "raw_trip": trip,
            })
        else:
            valid_trips.append(trip)

    return valid_trips, invalid_trip_errors

def safe_generate_trip_batch(
    client: Any,
    user_profile: dict[str, Any],
    batch_start_ts: str,
    batch_end_ts: str,
    batch_num_trips: int,
    batch_index: int,
    max_retries: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Generates one trip batch safely.

    Returns:
    - valid_trips
    - errors
    """

    user_id = user_profile["user_id"]
    all_errors = []

    for attempt in range(1, max_retries + 1):
        try:
            batch_trips = generate_trip_history_for_user_profile(
                client=client,
                user_profile=user_profile,
                start_ts=batch_start_ts,
                end_ts=batch_end_ts,
                num_trips=batch_num_trips,
            )

            batch_trips = normalize_trip_parent_fields(batch_trips)

            valid_trips, invalid_trip_errors = filter_valid_trips(
                trips=batch_trips,
                expected_user_id=user_id,
            )

            for error in invalid_trip_errors:
                error["batch_index"] = batch_index
                error["attempt"] = attempt
                error["error_type"] = "invalid_trip"

            all_errors.extend(invalid_trip_errors)

            return valid_trips, all_errors

        except Exception as exc:
            all_errors.append({
                "user_id": user_id,
                "batch_index": batch_index,
                "attempt": attempt,
                "error_type": "batch_generation_failed",
                "error_message": str(exc),
                "interval_start_ts": batch_start_ts,
                "interval_end_ts": batch_end_ts,
            })

            print(
                f"Batch {batch_index} failed for user {user_id}, "
                f"attempt {attempt}/{max_retries}: {exc}"
            )

    return [], all_errors


def generate_full_trip_history_with_checkpoint(
    client: Any,
    user_profile: dict[str, Any],
    start_ts: str,
    num_trips: int,
    checkpoint_path: str | Path,
    interval_days: int = 7,
    trips_per_interval: int = 15,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """
    Generates a full trip history for one user profile with checkpointing.

    If a batch fails, the process continues.
    If individual trips are invalid, only those trips are discarded.
    """

    if not user_profile.get("user_id"):
        raise ValueError("user_profile must contain user_id. Run ensure_user_ids first.")

    if num_trips < 1:
        raise ValueError("num_trips must be >= 1")

    user_id = user_profile["user_id"]

    checkpoint = load_checkpoint(checkpoint_path)

    completed_batch_keys = {
        batch["batch_key"]
        for batch in checkpoint.get("completed_batches", [])
    }

    existing_trips = [
        trip for trip in checkpoint.get("trips", [])
        if trip.get("user_id") == user_id
    ]

    current_start_dt = datetime.fromisoformat(start_ts)

    remaining_trips = num_trips
    batch_index = 1

    while remaining_trips > 0:
        batch_num_trips = min(trips_per_interval, remaining_trips)

        batch_key = make_batch_key(user_id, batch_index)

        current_end_dt = (
            current_start_dt
            + timedelta(days=interval_days)
            - timedelta(seconds=1)
        )

        batch_start_ts = current_start_dt.isoformat(timespec="seconds")
        batch_end_ts = current_end_dt.isoformat(timespec="seconds")

        if batch_key in completed_batch_keys:
            print(f"Skipping completed batch: {batch_key}")

        else:
            print(
                f"Generating batch {batch_index}: "
                f"{batch_num_trips} trips from {batch_start_ts} to {batch_end_ts}"
            )

            valid_batch_trips, batch_errors = safe_generate_trip_batch(
                client=client,
                user_profile=user_profile,
                batch_start_ts=batch_start_ts,
                batch_end_ts=batch_end_ts,
                batch_num_trips=batch_num_trips,
                batch_index=batch_index,
                max_retries=max_retries,
            )

            existing_trip_count = len([
                trip for trip in checkpoint["trips"]
                if trip.get("user_id") == user_id
            ])

            valid_batch_trips = reassign_trip_and_leg_ids(
                trips=valid_batch_trips,
                user_id=user_id,
                start_trip_index=existing_trip_count + 1,
            )

            for trip in valid_batch_trips:
                trip["generation_batch_index"] = batch_index
                trip["generation_interval_start_ts"] = batch_start_ts
                trip["generation_interval_end_ts"] = batch_end_ts

            checkpoint["trips"].extend(valid_batch_trips)
            checkpoint["errors"].extend(batch_errors)

            checkpoint["completed_batches"].append({
                "batch_key": batch_key,
                "user_id": user_id,
                "batch_index": batch_index,
                "interval_start_ts": batch_start_ts,
                "interval_end_ts": batch_end_ts,
                "requested_trips": batch_num_trips,
                "valid_trips": len(valid_batch_trips),
                "errors": len(batch_errors),
            })

            save_checkpoint(
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
            )

            print(
                f"Checkpoint saved. Batch {batch_index}: "
                f"{len(valid_batch_trips)} valid trips, {len(batch_errors)} errors."
            )

        remaining_trips -= batch_num_trips
        batch_index += 1
        current_start_dt = current_start_dt + timedelta(days=interval_days)

    user_trips = [
        trip for trip in checkpoint["trips"]
        if trip.get("user_id") == user_id
    ]

    user_trips = sorted(
        user_trips,
        key=lambda trip: trip.get("start_ts", "")
    )

    return user_trips


def generate_full_trip_history_for_user_profiles_with_checkpoint(
    client: Any,
    user_profiles: list[dict[str, Any]],
    start_ts: str,
    num_trips_per_user: int,
    checkpoint_path: str | Path,
    interval_days: int = 7,
    trips_per_interval: int = 15,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """
    Generates full trip histories for multiple user profiles with checkpointing.
    """

    user_profiles = ensure_user_ids(user_profiles)

    all_trips = []

    for user_index, user_profile in enumerate(user_profiles, start=1):
        display_name = user_profile.get("person_information", {}).get(
            "display_name",
            "unknown user"
        )

        print(
            f"Generating trip history for user "
            f"{user_index}/{len(user_profiles)}: {display_name}"
        )

        try:
            user_trips = generate_full_trip_history_with_checkpoint(
                client=client,
                user_profile=user_profile,
                start_ts=start_ts,
                num_trips=num_trips_per_user,
                checkpoint_path=checkpoint_path,
                interval_days=interval_days,
                trips_per_interval=trips_per_interval,
                max_retries=max_retries,
            )

            all_trips.extend(user_trips)

        except Exception as exc:
            checkpoint = load_checkpoint(checkpoint_path)

            checkpoint["errors"].append({
                "user_id": user_profile.get("user_id"),
                "user_index": user_index,
                "error_type": "user_generation_failed",
                "error_message": str(exc),
            })

            save_checkpoint(
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
            )

            print(
                f"User-level failure for {display_name}. "
                f"Continuing with next user. Error: {exc}"
            )

    checkpoint = load_checkpoint(checkpoint_path)

    all_trips = checkpoint.get("trips", [])

    all_trips = sorted(
        all_trips,
        key=lambda trip: (
            trip.get("user_id", ""),
            trip.get("start_ts", "")
        )
    )

    return all_trips

USER_TRIPS_DB_COLUMNS = [
    "trip_id",
    "user_id",

    "start_ts",
    "end_ts",
    "weekday",

    "origin_city",
    "origin_place_type",
    "origin_label",

    "destination_city",
    "destination_place_type",
    "destination_label",

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
    "priority_reason",

    "generation_batch_index",
    "generation_interval_start_ts",
    "generation_interval_end_ts",
]


def is_missing(value: Any) -> bool:
    return value is None or pd.isna(value)


def get_value(row: pd.Series, *column_names: str, default: Any = None) -> Any:
    """
    Returns the first available non-null value from a row.
    Useful because generated CSVs may use either:
    - origin.city
    - origin_city
    """

    for column_name in column_names:
        if column_name in row.index:
            value = row[column_name]
            if not is_missing(value):
                return value

    return default


def to_postgres_text_array(value: Any) -> str:
    """
    Converts values into PostgreSQL TEXT[] array literals.

    Examples:
    "walking|subway|walking" -> {"walking","subway","walking"}
    ["walking", "subway"]    -> {"walking","subway"}
    """

    if value is None:
        return "{}"

    if isinstance(value, float) and pd.isna(value):
        return "{}"

    if isinstance(value, list):
        values = value

    elif isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return "{}"

        # Already PostgreSQL array literal
        if cleaned.startswith("{") and cleaned.endswith("}"):
            return cleaned

        # Python-list-like string, e.g. "['walking', 'subway']"
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                parsed = ast.literal_eval(cleaned)
                values = parsed if isinstance(parsed, list) else []
            except Exception:
                values = []

        # Pipe-separated from earlier CSV export
        elif "|" in cleaned:
            values = cleaned.split("|")

        # Fallback: single value
        else:
            values = [cleaned]

    else:
        values = [str(value)]

    escaped_values = []

    for item in values:
        item_str = str(item).strip()

        if not item_str:
            continue

        item_str = item_str.replace("\\", "\\\\").replace('"', '\\"')
        escaped_values.append(f'"{item_str}"')

    return "{" + ",".join(escaped_values) + "}"


def to_postgres_bool(value: Any) -> str | None:
    """
    Converts booleans to lowercase strings accepted by PostgreSQL COPY.
    """

    if is_missing(value):
        return None

    if isinstance(value, bool):
        return "true" if value else "false"

    value_str = str(value).strip().lower()

    if value_str in ["true", "t", "1", "yes", "y"]:
        return "true"

    if value_str in ["false", "f", "0", "no", "n"]:
        return "false"

    return None


def to_optional_float(value: Any) -> float | None:
    if is_missing(value):
        return None

    try:
        return float(value)
    except ValueError:
        return None


def to_optional_int(value: Any) -> int | None:
    if is_missing(value):
        return None

    try:
        return int(float(value))
    except ValueError:
        return None


def user_trip_csv_row_to_db_row(row: pd.Series) -> dict[str, Any]:
    """
    Maps one generated trip CSV row to the user_trips DB format.
    """

    db_row = {
        "trip_id": get_value(row, "trip_id"),
        "user_id": get_value(row, "user_id"),

        "start_ts": get_value(row, "start_ts"),
        "end_ts": get_value(row, "end_ts"),
        "weekday": get_value(row, "weekday"),

        "origin_city": get_value(row, "origin_city", "origin.city"),
        "origin_place_type": get_value(row, "origin_place_type", "origin.place_type"),
        "origin_label": get_value(row, "origin_label", "origin.label"),

        "destination_city": get_value(row, "destination_city", "destination.city"),
        "destination_place_type": get_value(
            row,
            "destination_place_type",
            "destination.place_type",
        ),
        "destination_label": get_value(row, "destination_label", "destination.label"),

        "trip_purpose": get_value(row, "trip_purpose"),
        "main_mode": get_value(row, "main_mode"),
        "modes_used": to_postgres_text_array(
            get_value(row, "modes_used")
        ),

        "distance_km": to_optional_float(
            get_value(row, "distance_km")
        ),
        "duration_min": to_optional_int(
            get_value(row, "duration_min")
        ),
        "estimated_cost_eur": to_optional_float(
            get_value(row, "estimated_cost_eur")
        ),

        "ticket_product_used": get_value(row, "ticket_product_used"),

        "is_commute": to_postgres_bool(
            get_value(row, "is_commute")
        ),
        "is_recurring_pattern": to_postgres_bool(
            get_value(row, "is_recurring_pattern")
        ),

        "planning_style": get_value(row, "planning_style"),
        "priority_reason": get_value(row, "priority_reason"),

        "generation_batch_index": to_optional_int(
            get_value(row, "generation_batch_index")
        ),
        "generation_interval_start_ts": get_value(
            row,
            "generation_interval_start_ts",
        ),
        "generation_interval_end_ts": get_value(
            row,
            "generation_interval_end_ts",
        ),
    }

    return db_row


def save_user_trips_csv_as_db_csv(
    input_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """
    Reads the generated user trips CSV, maps it to the user_trips DB schema,
    and saves a DB-compatible CSV.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"User trips CSV not found: {input_path}")

    df_input = pd.read_csv(input_path)

    if df_input.empty:
        raise ValueError(f"User trips CSV is empty: {input_path}")

    rows = [
        user_trip_csv_row_to_db_row(row)
        for _, row in df_input.iterrows()
    ]

    df_output = pd.DataFrame(rows)

    df_output = df_output[USER_TRIPS_DB_COLUMNS]

    required_columns = [
        "trip_id",
        "user_id",
        "start_ts",
        "end_ts",
        "origin_city",
        "destination_city",
        "trip_purpose",
        "main_mode",
    ]

    missing_required = []

    for column in required_columns:
        if df_output[column].isna().any() or (df_output[column].astype(str).str.strip() == "").any():
            missing_required.append(column)

    if missing_required:
        raise ValueError(
            f"DB CSV contains missing required values in columns: {missing_required}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_output.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Saved {len(df_output)} user trips to DB-compatible CSV: {output_path}")

    return df_output


from pathlib import Path
from typing import Any

import pandas as pd


TRIP_LEGS_DB_COLUMNS = [
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


def trip_leg_csv_row_to_db_row(row: pd.Series) -> dict[str, Any]:
    """
    Maps one generated trip leg CSV row to the trip_legs DB format.
    """

    db_row = {
        "leg_id": get_value(row, "leg_id"),
        "trip_id": get_value(row, "trip_id"),

        "sequence_no": to_optional_int(
            get_value(row, "sequence_no")
        ),

        "start_ts": get_value(row, "start_ts"),
        "end_ts": get_value(row, "end_ts"),

        "mode": get_value(row, "mode"),

        "origin_label": get_value(row, "origin_label"),
        "destination_label": get_value(row, "destination_label"),

        "distance_km": to_optional_float(
            get_value(row, "distance_km")
        ),
        "duration_min": to_optional_int(
            get_value(row, "duration_min")
        ),

        "ticket_required": to_postgres_bool(
            get_value(row, "ticket_required")
        ),
        "ticket_product_used": get_value(row, "ticket_product_used"),

        "leg_note": get_value(row, "leg_note"),
    }

    return db_row


def save_trip_legs_csv_as_db_csv(
    input_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """
    Reads the generated trip legs CSV, maps it to the trip_legs DB schema,
    and saves a DB-compatible CSV.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Trip legs CSV not found: {input_path}")

    df_input = pd.read_csv(input_path)

    if df_input.empty:
        raise ValueError(f"Trip legs CSV is empty: {input_path}")

    rows = [
        trip_leg_csv_row_to_db_row(row)
        for _, row in df_input.iterrows()
    ]

    df_output = pd.DataFrame(rows)

    # Ensure exact column order
    df_output = df_output[TRIP_LEGS_DB_COLUMNS]

    required_columns = [
        "leg_id",
        "trip_id",
        "sequence_no",
        "start_ts",
        "end_ts",
        "mode",
    ]

    missing_required = []

    for column in required_columns:
        if (
            df_output[column].isna().any()
            or (df_output[column].astype(str).str.strip() == "").any()
        ):
            missing_required.append(column)

    if missing_required:
        raise ValueError(
            f"DB CSV contains missing required values in columns: {missing_required}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_output.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Saved {len(df_output)} trip legs to DB-compatible CSV: {output_path}")

    return df_output