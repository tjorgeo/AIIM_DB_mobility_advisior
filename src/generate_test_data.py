"""
user_profiles
      ↓
Python liest User-Profil
      ↓
OpenAI erzeugt synthetische Trip-Vorschläge als JSON
      ↓
Python validiert / bereinigt / ergänzt technische Felder
      ↓
INSERT in mobility_trips
"""

from db_manager import get_db_connection, load_user_profile
from university_api_connection import call_university_gpt, build_university_gpt_connection

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from typing import Any
from pathlib import Path
import csv
from uuid import uuid4

import university_api_connection

PROMPT_VERSION = "mobility_trips_v1"

ALLOWED_ORIGIN_DESTINATION_TYPES = [
    "home",
    "work",
    "education",
    "shopping",
    "leisure",
    "errand",
    "healthcare",
    "station",
    "other",
]

ALLOWED_TRIP_PURPOSES = [
    "commute",
    "education",
    "shopping",
    "leisure",
    "errand",
    "healthcare",
    "return_home",
    "other",
]

ALLOWED_TRANSPORT_MODES = [
    "walking",
    "bike",
    "e_scooter",
    "car",
    "public_transport",
    "bus",
    "tram",
    "subway",
    "train",
    "taxi",
    "shared_mobility",
    "mixed",
    "other",
]

def make_json_serializable(value: Any) -> Any:
    """
    Wandelt typische DB-Werte in JSON-kompatible Werte um.
    psycopg2 liefert z. B. UUID, date, datetime oder Decimal.
    """
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {key: make_json_serializable(val) for key, val in value.items()}

    if isinstance(value, list):
        return [make_json_serializable(item) for item in value]

    return value


def build_user_generation_context(user_profile: dict[str, Any]) -> dict[str, Any]:
    """
    Reduziert das vollständige User-Profil auf die Informationen,
    die für synthetische Mobility-Trips relevant sind.

    Keine Koordinaten.
    Keine exakten Adressen.
    """
    context = {
        "user_id": user_profile.get("user_id"),
        "home_city": user_profile.get("home_city"),
        "home_postal_code": user_profile.get("home_postal_code"),
        "home_country_code": user_profile.get("home_country_code"),
        "work_name": user_profile.get("work_name"),
        "work_pattern": user_profile.get("work_pattern"),
        "mobility_profile": user_profile.get("mobility_profile"),
        "owns_car": user_profile.get("owns_car"),
        "owns_bike": user_profile.get("owns_bike"),
        "has_driving_license": user_profile.get("has_driving_license"),
        "preferred_transport_modes": user_profile.get("preferred_transport_modes"),
        "avoided_transport_modes": user_profile.get("avoided_transport_modes"),
        "accessibility_needs": user_profile.get("accessibility_needs"),
        "max_walking_distance_m": user_profile.get("max_walking_distance_m"),
        "budget_preference": user_profile.get("budget_preference"),
        "prefers_low_emission": user_profile.get("prefers_low_emission"),
        "prefers_fewer_transfers": user_profile.get("prefers_fewer_transfers"),
        "prefers_short_travel_time": user_profile.get("prefers_short_travel_time"),
        "preferences": user_profile.get("preferences"),
    }

    return make_json_serializable(context)


def build_trip_generation_messages(
    user_context: dict[str, Any],
    number_of_trips: int = 10,
    start_date: str = "2026-06-01",
    end_date: str = "2026-06-07",
) -> list[dict[str, str]]:
    """
    Baut die Messages für den OpenAI-Call.

    Das Modell soll ausschließlich JSON zurückgeben.
    Keine Koordinaten.
    Keine SQL-Statements.
    """
    system_message = """
        You are a generator for synthetic mobility test data.

        You generate realistic mobility trips for a test database.
        The data must realistically match the user profile and its preferences.

        Important rules:
        - Return only valid JSON.
        - Do not return any Markdown code blocks.
        - Do not generate SQL statements.
        - Do not generate latitude or longitude fields.
        - Do not generate exact addresses.
        - ended_at must always be after started_at.
        - trip_date must match the date of started_at.
        - distance_m and duration_min are plausible estimates.
        - Use only permitted values for origin_type, destination_type, trip_purpose and transport_mode.
        - Most outbound trips must have a corresponding return trip (mostly same day).
        - The return trip must start after the outbound trip ended.
        - The return trip should reverse origin and destination.
        - Use trip_purpose = "return_home" for trips returning to home.
        - If a trip does not return home, create a plausible chain, for example home → work → shopping → home.
        - Avoid unrealistic one-way trips unless the purpose clearly explains it.
    """.strip()

    user_message = {
        "task": "Generate synthetic mobility trips for this user profile.",
        "number_of_trips": number_of_trips,
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "instructions": [
            "Return exactly one JSON object.",
            "The JSON object must contain one key: trips.",
            "trips must be a list of trip objects.",
            "Do not copy the example values literally.",
            "Generate varied but plausible trips based on the user profile.",
            "Do not generate latitude or longitude.",
            "Do not generate exact addresses.",
            "Use city-level location information only.",
        ],
        "allowed_values": {
            "origin_type": ALLOWED_ORIGIN_DESTINATION_TYPES,
            "destination_type": ALLOWED_ORIGIN_DESTINATION_TYPES,
            "trip_purpose": ALLOWED_TRIP_PURPOSES,
            "transport_mode": ALLOWED_TRANSPORT_MODES,
        },
        "output_fields": {
            "trip_date": "string, format YYYY-MM-DD",
            "started_at": "string, ISO-8601 timestamp",
            "ended_at": "string, ISO-8601 timestamp",
            "origin_type": "string, one of allowed_values.origin_type",
            "origin_city": "string",
            "destination_type": "string, one of allowed_values.destination_type",
            "destination_city": "string",
            "trip_purpose": "string, one of allowed_values.trip_purpose",
            "transport_mode": "string, one of allowed_values.transport_mode",
            "distance_m": "integer, estimated distance in meters",
            "duration_min": "integer, estimated trip duration in minutes",
            "transfer_count": "integer, number of transfers",
            "estimated_cost_eur": "number, estimated direct user cost in EUR",
            "estimated_co2_g": "integer, estimated CO2 emissions in grams",
            "notes": "string, short plausibility explanation"
        },
        "example_output": {
            "trips": [
                {
                    "trip_date": "2026-06-01",
                    "started_at": "2026-06-01T08:05:00",
                    "ended_at": "2026-06-01T08:42:00",
                    "origin_type": "home",
                    "origin_city": "Berlin",
                    "destination_type": "work",
                    "destination_city": "Berlin",
                    "trip_purpose": "commute",
                    "transport_mode": "public_transport",
                    "distance_m": 8500,
                    "duration_min": 37,
                    "transfer_count": 1,
                    "estimated_cost_eur": 0.0,
                    "estimated_co2_g": 450,
                    "notes": "Example only. Do not copy this exact trip or use exact values too often."
                }
            ]
        },
        "user_profile": user_context,
    }

    return [
        {
            "role": "system",
            "content": system_message,
        },
        {
            "role": "user",
            "content": json.dumps(user_message, ensure_ascii=False, indent=2),
        },
    ]

def parse_openai_json_response(response_text: str) -> dict[str, Any]:
    """
    Parsed die OpenAI-Antwort als JSON.

    Funktioniert auch, falls versehentlich Markdown-Codeblöcke zurückkommen.
    Erwartet am Ende ein Objekt mit dem Key 'trips'.
    """
    cleaned = response_text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()

    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI-Antwort ist kein gültiges JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("OpenAI-Antwort muss ein JSON-Objekt sein.")

    if "trips" not in data:
        raise ValueError("OpenAI-Antwort muss den Key 'trips' enthalten.")

    if not isinstance(data["trips"], list):
        raise ValueError("'trips' muss eine Liste sein.")

    return data

def parse_iso_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} muss ein ISO-8601 String sein.")

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} ist kein gültiger ISO-8601 Zeitstempel: {value}") from exc


def validate_allowed_value(
    value: Any,
    field_name: str,
    allowed_values: list[str],
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} muss ein String sein.")

    if value not in allowed_values:
        raise ValueError(
            f"{field_name} hat ungültigen Wert '{value}'. "
            f"Erlaubt sind: {allowed_values}"
        )

    return value


def validate_non_negative_int(value: Any, field_name: str, required: bool = True) -> int | None:
    if value is None and not required:
        return None

    if not isinstance(value, int):
        raise ValueError(f"{field_name} muss ein Integer sein.")

    if value < 0:
        raise ValueError(f"{field_name} darf nicht negativ sein.")

    return value


def validate_non_negative_number(value: Any, field_name: str, required: bool = False) -> float | None:
    if value is None and not required:
        return None

    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} muss eine Zahl sein.")

    if value < 0:
        raise ValueError(f"{field_name} darf nicht negativ sein.")

    return float(value)


def validate_and_normalize_trip(
    trip: dict[str, Any],
    row_number: int,
    user_id: str,
    generation_batch_id: str,
    generation_model: str,
    generation_prompt_version: str,
) -> dict[str, Any]:
    """
    Prüft einen Trip und gibt eine CSV-kompatible Zeile zurück.
    Keine Koordinaten.
    Keine exakten Adressen.
    """
    if not isinstance(trip, dict):
        raise ValueError(f"Trip #{row_number} ist kein JSON-Objekt.")

    forbidden_fields = {
        "origin_latitude",
        "origin_longitude",
        "destination_latitude",
        "destination_longitude",
        "latitude",
        "longitude",
        "lat",
        "lon",
    }

    found_forbidden = forbidden_fields.intersection(trip.keys())
    if found_forbidden:
        raise ValueError(
            f"Trip #{row_number} enthält verbotene Koordinatenfelder: {found_forbidden}"
        )

    started_at_dt = parse_iso_datetime(trip.get("started_at"), "started_at")
    ended_at_dt = parse_iso_datetime(trip.get("ended_at"), "ended_at")

    if ended_at_dt <= started_at_dt:
        raise ValueError(f"Trip #{row_number}: ended_at muss nach started_at liegen.")

    trip_date = trip.get("trip_date")
    if not isinstance(trip_date, str):
        raise ValueError(f"Trip #{row_number}: trip_date muss ein String sein.")

    if trip_date != started_at_dt.date().isoformat():
        raise ValueError(
            f"Trip #{row_number}: trip_date passt nicht zu started_at. "
            f"trip_date={trip_date}, started_at_date={started_at_dt.date().isoformat()}"
        )

    origin_type = validate_allowed_value(
        trip.get("origin_type"),
        "origin_type",
        ALLOWED_ORIGIN_DESTINATION_TYPES,
    )

    destination_type = validate_allowed_value(
        trip.get("destination_type"),
        "destination_type",
        ALLOWED_ORIGIN_DESTINATION_TYPES,
    )

    trip_purpose = validate_allowed_value(
        trip.get("trip_purpose"),
        "trip_purpose",
        ALLOWED_TRIP_PURPOSES,
    )

    transport_mode = validate_allowed_value(
        trip.get("transport_mode"),
        "transport_mode",
        ALLOWED_TRANSPORT_MODES,
    )

    distance_m = validate_non_negative_int(trip.get("distance_m"), "distance_m", required=False)
    duration_min = validate_non_negative_int(trip.get("duration_min"), "duration_min", required=False)
    transfer_count = validate_non_negative_int(trip.get("transfer_count", 0), "transfer_count")

    estimated_cost_eur = validate_non_negative_number(
        trip.get("estimated_cost_eur"),
        "estimated_cost_eur",
        required=False,
    )

    estimated_co2_g = validate_non_negative_int(
        trip.get("estimated_co2_g"),
        "estimated_co2_g",
        required=False,
    )

    metadata = {
        "trip_group_id": trip.get("trip_group_id"),
        "notes": trip.get("notes"),
        "synthetic_generator": "openai",
    }

    row = {
        "user_id": user_id,
        "trip_date": trip_date,
        "started_at": started_at_dt.isoformat(),
        "ended_at": ended_at_dt.isoformat(),

        "origin_type": origin_type,
        "origin_city": trip.get("origin_city"),

        "destination_type": destination_type,
        "destination_city": trip.get("destination_city"),

        "trip_purpose": trip_purpose,
        "transport_mode": transport_mode,
        "distance_m": distance_m,
        "duration_min": duration_min,
        "transfer_count": transfer_count,

        "estimated_cost_eur": estimated_cost_eur,
        "estimated_co2_g": estimated_co2_g,

        "data_source": "synthetic_openai",
        "generation_batch_id": generation_batch_id,
        "generation_model": generation_model,
        "generation_prompt_version": generation_prompt_version,
        "metadata": json.dumps(metadata, ensure_ascii=False),
    }

    return row

def validate_and_normalize_openai_trips_response(
    response_text: str,
    user_id: str,
    generation_model: str,
    generation_prompt_version: str,
) -> list[dict[str, Any]]:
    """
    Parsed und validiert die komplette OpenAI-Antwort.
    Gibt eine Liste von CSV-kompatiblen Zeilen zurück.
    """
    parsed = parse_openai_json_response(response_text)
    generation_batch_id = str(uuid4())

    rows = []

    for index, trip in enumerate(parsed["trips"], start=1):
        try:
            row = validate_and_normalize_trip(
                trip=trip,
                row_number=index,
                user_id=user_id,
                generation_batch_id=generation_batch_id,
                generation_model=generation_model,
                generation_prompt_version=generation_prompt_version,
            )
            rows.append(row)
        except ValueError as exc:
            raise ValueError(f"Validierung fehlgeschlagen bei Trip #{index}: {exc}") from exc

    if not rows:
        raise ValueError("Die OpenAI-Antwort enthält keine Trips.")

    rows.sort(key=lambda row: row["started_at"])

    return rows

def write_trips_to_csv(
    rows: list[dict[str, Any]],
    output_path: str | Path = "data/generated/mobility_trips.csv",
) -> Path:
    """
    Schreibt validierte mobility_trips in eine CSV-Datei.
    """
    
    MOBILITY_TRIPS_CSV_COLUMNS = [
        "user_id",
        "trip_date",
        "started_at",
        "ended_at",

        "origin_type",
        "origin_city",

        "destination_type",
        "destination_city",

        "trip_purpose",
        "transport_mode",
        "distance_m",
        "duration_min",
        "transfer_count",

        "estimated_cost_eur",
        "estimated_co2_g",

        "data_source",
        "generation_batch_id",
        "generation_model",
        "generation_prompt_version",
        "metadata",
    ]
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=MOBILITY_TRIPS_CSV_COLUMNS,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)

    return output_path

def parse_ts(value: str | datetime, field_name: str) -> datetime:
    """
    Akzeptiert entweder datetime oder ISO-8601-String.
    Beispiel: '2026-06-01T00:00:00+02:00'
    """
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} ist kein gültiger ISO-8601 Timestamp: {value}"
            ) from exc

    raise TypeError(f"{field_name} muss str oder datetime sein.")

def generate_full_trip_history(
    db,
    client,
    user_id: str,
    start_ts: str | datetime,
    interval: timedelta,
    num_trips: int,
    batch_size: int = 10,
    output_path: str | Path = "data/generated/mobility_trips.csv",
) -> list[dict[str, Any]]:
    """
    Erzeugt eine synthetische Trip-Historie für einen User.

    Parameter:
    - user_id: User-ID aus user_profiles
    - start_ts: Startzeitpunkt der ersten Periode
    - interval: Größe einer Periode, z. B. timedelta(weeks=1)
    - num_trips: Gesamtanzahl gewünschter Trips
    - batch_size: Anzahl Trips pro OpenAI-Aufruf
    - output_path: Zielpfad für die CSV

    Beispiel:
    start_ts = '2026-06-01T00:00:00+02:00'
    interval = timedelta(weeks=1)
    num_trips = 50

    Dann werden erzeugt:
    - 10 Trips für Woche 1
    - 10 Trips für Woche 2
    - 10 Trips für Woche 3
    - ...
    """

    if num_trips <= 0:
        raise ValueError("num_trips muss größer als 0 sein.")

    if batch_size <= 0:
        raise ValueError("batch_size muss größer als 0 sein.")

    if interval <= timedelta(0):
        raise ValueError("interval muss größer als 0 sein.")

    current_start = parse_ts(start_ts, "start_ts")

    user_profile = load_user_profile(db, user_id)
    user_context = build_user_generation_context(user_profile)

    all_rows: list[dict[str, Any]] = []

    batch_number = 1

    while len(all_rows) < num_trips:
        remaining_trips = num_trips - len(all_rows)
        current_batch_size = min(batch_size, remaining_trips)

        current_end = current_start + interval

        print(
            f"Batch {batch_number}: "
            f"erzeuge {current_batch_size} Trips "
            f"für Zeitraum {current_start.isoformat()} bis {current_end.isoformat()}"
        )

        messages = build_trip_generation_messages(
            user_context=user_context,
            number_of_trips=current_batch_size,
            start_date=current_start.date().isoformat(),
            end_date=(current_end - timedelta(seconds=1)).date().isoformat(),
        )

        response_text = call_university_gpt(
            client,
            messages=messages,
            max_new_tokens=4000,
            temperature=0.3,
        )

        rows = validate_and_normalize_openai_trips_response(
            response_text=response_text,
            user_id=str(user_id),
            generation_model="UNI_GPT",
            generation_prompt_version=PROMPT_VERSION,
        )

        if not rows:
            raise ValueError(f"Batch {batch_number} hat keine validen Trips erzeugt.")

        rows_needed = num_trips - len(all_rows)
        all_rows.extend(rows[:rows_needed])

        current_start = current_end
        batch_number += 1

    all_rows.sort(key=lambda row: row["started_at"])

    output_path = write_trips_to_csv(
        rows=all_rows,
        output_path=output_path,
    )

    print(f"{len(all_rows)} Trips erzeugt und validiert.")
    print(f"CSV geschrieben nach: {output_path}")

    return all_rows

def main():

    db = get_db_connection()     
    client = build_university_gpt_connection()

    rows = generate_full_trip_history(
        db,
        client,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        start_ts="2026-06-01T00:00:00",
        interval=timedelta(weeks=1),
        num_trips=100,
        batch_size=20,
        output_path="data/generated/mobility_trips_test.csv",
    )

    print(f"Fertig. Anzahl Trips: {len(rows)}")
    print(f"{len(rows)} Trips validiert.")


if __name__ == "__main__":
    main()