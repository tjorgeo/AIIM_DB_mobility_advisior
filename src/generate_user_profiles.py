from pathlib import Path
import pandas as pd

from db_manager import get_db_connection, load_user_profile
from utils.university_api_connection import call_university_gpt, build_university_gpt_connection
import json
from datetime import date
from typing import Any, Optional
import uuid

"""
1. use persona to generate user profiles
2. use user profiles to generate trips
3. use trips to generate purchases 

"""

SYSTEM_PROMPT_GENERATE_USER_PROFILE = """
You generate synthetic test data for a mobility advisor application.

Your task:
Create exactly one unique user_profile JSON object from the provided persona. 

Important rules:
- The persona is an archetype, not a fixed user.
- Convert broad persona attributes into concrete user-profile values.
- Use the persona's travel_statement and activity_statement as behavioral guidance.
- Do not copy vague statements into structured fields.
- Make plausible assumptions where needed.
- Keep the result realistic for Germany.
- Generate only fictional people.
- Return only valid JSON.
- Do not include markdown.
- Do not include explanations outside the JSON object.
"""


def build_user_profile_prompt(
    persona: dict[str, Any],
    profiles_created,
    profile_index: int = 1,
    allowed_home_locations: Optional[list[dict[str, str]]] = None,
    reference_date: Optional[str] = None,
) -> str:
    """
    Builds the user prompt for generating one concrete user profile from one persona.
    """

    if reference_date is None:
        reference_date = date.today().isoformat()

    if allowed_home_locations:
        location_instruction = (
            "Choose exactly one home location from this allowed_home_locations list:\n"
            f"{json.dumps(allowed_home_locations, ensure_ascii=False, indent=2)}"
        )
    else:
        location_instruction = (
            "No fixed home locations are provided. Choose a plausible German city "
            "and postal code that match the persona's city_type."
        )

    return f"""
Generate one unique user_profile from the following persona. 
If there are already profiles created from this persona, make sure you create a unique user_profile, which
is distinct from the one already created. Come up with something new then, especially for the travel statement.


Reference date for age and date_of_birth calculations:
{reference_date}

Profile index:
{profile_index}

Profiles created from this persona:
{profiles_created}

Location instruction:
{location_instruction}

Persona:
{json.dumps(persona, ensure_ascii=False, indent=2)}

Return exactly one JSON object with this structure:

{{
  "source_persona_id": "string",
  "profile_variant": "string",

  "account": {{
    "email": "string, example.com",
    "username": "string",
    "external_auth_id": "string"
  }},

  "person_information": {{
    "first_name": "string",
    "last_name": "string",
    "display_name": "string",
    "date_of_birth": "YYYY-MM-DD",
    "age": "integer",
    "gender": "female | male | diverse | not_specified",
    "life_stage": "string",
    "home_city": "string",
    "home_postal_code": "string, must match home_city",
    "home_country_code": "DE",
    "city_type": "big_city | medium_city | small_city | town | rural, must match home_city"
  }},

  "job_related": {{
    "job_industry": "string",
    "employment_status": "employed_full_time | employed_part_time | self_employed | student | retired | unemployed",
    "income_range": "low | medium_low | medium | medium_high | high",
    "working_pattern": "on_site | hybrid | remote | shift_work | irregular | not_working",
    "commute_frequency": "never | 1_day_per_week | 2_days_per_week | 3_days_per_week | 4_days_per_week | 5_days_per_week | irregular"
  }},

  "mobility_profile": {{
    "has_car": bool,
    "has_bike": bool,
    "has_driving_license": bool,
    "public_transport_affinity": "low | medium | high",
    "preferred_modes": [
      "walking",
      "bike",
      "public_transport",
      "subway",
      "tram",
      "bus",
      "regional_train",
      "long_distance_train",
      "car",
      "car_sharing",
      "ride_hailing",
      "shared_bike",
      "shared_scooter"
    ],
    "avoided_modes": [
      "walking",
      "bike",
      "public_transport",
      "subway",
      "tram",
      "bus",
      "regional_train",
      "long_distance_train",
      "car",
      "car_sharing",
      "ride_hailing",
      "shared_bike",
      "shared_scooter"
    ],
    "typical_weekday_trip_level": "low | medium | high",
    "typical_weekend_trip_level": "low | medium | high"
  }},

  "activity_profile": {{
    "leisure_intensity": "low | medium | high",
    "preferred_activity_types": [
      "restaurants",
      "cafes",
      "fitness",
      "sports",
      "cinema",
      "culture",
      "shopping",
      "parks",
      "family_visits",
      "nightlife",
      "education",
      "errands",
      "weekend_trips",
      "friends_visits",
      "vacation"
    ],
    "evening_activity_frequency": "rare | sometimes | often",
    "weekend_activity_frequency": "rare | sometimes | often"
  }},

  "ticketing_profile": {{
    "subscription_likelihood": "low | medium | high",
    "current_ticket_product": "none | single_ticket | day_ticket | weekly_pass | monthly_pass | subscription | student_pass | job_ticket",
    "likely_ticket_products": [
      "single_ticket",
      "short_trip_ticket",
      "day_ticket",
      "weekly_pass",
      "monthly_pass",
      "subscription",
      "student_pass",
      "job_ticket"
    ],
    "price_sensitivity": "low | medium | high",
    "purchase_channel_preference": "mobile_app | website | ticket_machine | service_center",
    "employer_reimbursement_available": true
  }},
  
    "user_statements": {{
    "travel_and_priorities": "string, 3-5 sentences written from the user's first-person perspective"
  }},

  "generation_rationale": "string"
}}

Generation requirements:
- Respect the persona's age_range, gender, city_type, job_industry, income_range and working_pattern.
- Pick one concrete age inside the age_range.
- Generate date_of_birth so that it roughly matches the selected age.
- Use the travel_behavior text to infer mobility_profile and ticketing_profile.
- Use the activity_behavior text to infer activity_profile.
- Include occasional out-of-city trips when consistent with the user profile (e. g. weekend_trips, family_visits, friend_visits).
- For out-of-city trips use transportation_mode according to preferences.
- Add variation for this profile_index, but do not contradict the persona.
- preferred_modes should contain the most likely modes for this user.
- avoided_modes may be empty if there is no strong avoidance.
- Add user_statements.travel_and_priorities.
- The statement must be 3 to 5 sentences long.
- Write the statement in first-person perspective as if the generated user is speaking.
- The statement must mention travel behavior and personal mobility priorities.
- The statement should be consistent with mobility_profile, activity_profile and ticketing_profile.
- Do not mention that this is synthetic test data.
- The result must be suitable for later generating trips and ticket purchases.
- Return only the JSON object. No markdown. No code block.
"""


def parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Parses a JSON response from the model.

    This is intentionally tolerant in case the model accidentally wraps JSON
    in text or a markdown code block.
    """

    cleaned = response_text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()

    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"No JSON object found in response:\n{response_text}")

        json_part = cleaned[start:end + 1]
        return json.loads(json_part)


def validate_generated_user_profile(user_profile: dict[str, Any]) -> None:
    """
    Lightweight validation for the generated user profile.

    This does not replace a full JSON schema validation, but catches the most
    important structural problems early.
    """

    required_top_level_keys = [
        "source_persona_id",
        "profile_variant",
        "account",
        "person_information",
        "job_related",
        "mobility_profile",
        "activity_profile",
        "ticketing_profile",
        "user_statements",
        "generation_rationale",
    ]

    missing_keys = [
        key for key in required_top_level_keys
        if key not in user_profile
    ]

    if missing_keys:
        raise ValueError(f"Generated user_profile is missing keys: {missing_keys}")

    email = user_profile["account"].get("email", "")
    if not email.endswith("@example.com"):
        raise ValueError(
            f"Synthetic email must use example.com, got: {email}"
        )

    gender = user_profile["person_information"].get("gender")
    if gender not in ["female", "male", "diverse", "not_specified"]:
        raise ValueError(f"Invalid gender value: {gender}")

    home_country_code = user_profile["person_information"].get("home_country_code")
    if home_country_code != "DE":
        raise ValueError(f"Expected home_country_code DE, got: {home_country_code}")


def generate_user_profile_from_persona(
    client: Any,
    persona: dict[str, Any],
    profiles_created,
    profile_index: int = 1,
    allowed_home_locations: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """
    Generates one concrete user_profile from one persona.

    Uses the existing call_university_gpt function for the model call.
    """

    user_prompt = build_user_profile_prompt(
        persona,
        profiles_created,
        profile_index=profile_index,
        allowed_home_locations=allowed_home_locations,
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT_GENERATE_USER_PROFILE,
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
        temperature=0.5,
    )

    user_profile = parse_json_response(response_text)

    validate_generated_user_profile(user_profile)

    return user_profile

def load_personas_from_file(file_path: str | Path) -> list[dict[str, Any]]:
    """
    Loads personas from a JSON file.

    Expected structure:
    {
      "personas": [
        {...},
        {...}
      ]
    }
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Persona file must contain a JSON object.")

    personas = data.get("personas")

    if not isinstance(personas, list):
        raise ValueError("Persona file must contain a 'personas' list.")

    if not personas:
        raise ValueError("Persona file contains no personas.")

    return personas

def generate_user_profiles_from_personas(
    client: Any,
    personas: list[dict[str, Any]],
    profiles_per_persona: int = 1,
    allowed_home_locations: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Generates concrete user profiles for all personas.

    Example:
    - 3 personas
    - profiles_per_persona = 5
    => 15 generated user profiles
    """

    if profiles_per_persona < 1:
        raise ValueError("profiles_per_persona must be >= 1")

    all_user_profiles = []

    for persona in personas:
        persona_id = persona.get("persona_id", "unknown_persona")

        for profile_index in range(1, profiles_per_persona + 1):
            print(
                f"Generating user profile {profile_index}/{profiles_per_persona} "
                f"for persona '{persona_id}'..."
            )

            user_profile = generate_user_profile_from_persona(
                client=client,
                persona=persona,
                profiles_created=all_user_profiles,
                profile_index=profile_index,
                allowed_home_locations=allowed_home_locations,
            )

            all_user_profiles.append(user_profile)

    return all_user_profiles

def save_user_profiles_to_file(
    user_profiles: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    """
    Saves generated user profiles to a JSON file.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "user_profiles": user_profiles
    }

    with path.open("w", encoding="utf-8") as file:
        json.dump(output_data, file, ensure_ascii=False, indent=2)

    print(f"Saved {len(user_profiles)} user profiles to: {path}")
    

USER_PROFILE_DB_COLUMNS = [
    "user_id",

    # Persona / Generierung
    "source_persona_id",
    "profile_variant",
    "generation_rationale",

    # Account
    "email",
    "username",
    "external_auth_id",

    # Person Information
    "first_name",
    "last_name",
    "display_name",
    "date_of_birth",
    "age",
    "gender",
    "life_stage",
    "home_city",
    "home_postal_code",
    "home_country_code",
    "city_type",

    # Job Related
    "job_industry",
    "employment_status",
    "income_range",
    "working_pattern",
    "commute_frequency",

    # Mobility Profile
    "has_car",
    "has_bike",
    "has_driving_license",
    "public_transport_affinity",
    "preferred_modes",
    "avoided_modes",
    "typical_weekday_trip_level",
    "typical_weekend_trip_level",

    # Activity Profile
    "leisure_intensity",
    "preferred_activity_types",
    "evening_activity_frequency",
    "weekend_activity_frequency",

    # Ticketing Profile
    "subscription_likelihood",
    "current_ticket_product",
    "likely_ticket_products",
    "price_sensitivity",
    "purchase_channel_preference",
    "employer_reimbursement_available",

    # User Statements
    "travel_and_priorities",
]


def to_postgres_text_array(value: Any) -> str:
    """
    Converts a Python list into a PostgreSQL TEXT[] array literal.

    Example:
    ["walking", "subway"] -> {"walking","subway"}
    """

    if value is None:
        return "{}"

    if not isinstance(value, list):
        return "{}"

    if not value:
        return "{}"

    escaped_values = []

    for item in value:
        item_str = str(item)

        # Escape backslashes and double quotes for PostgreSQL array literal
        item_str = item_str.replace("\\", "\\\\").replace('"', '\\"')

        escaped_values.append(f'"{item_str}"')

    return "{" + ",".join(escaped_values) + "}"


def user_profile_to_db_row(user_profile: dict[str, Any]) -> dict[str, Any]:
    """
    Maps one nested generated user_profile JSON object to one flat DB row
    matching the user_profiles DDL.
    """

    account = user_profile.get("account", {})
    person = user_profile.get("person_information", {})
    job = user_profile.get("job_related", {})
    mobility = user_profile.get("mobility_profile", {})
    activity = user_profile.get("activity_profile", {})
    ticketing = user_profile.get("ticketing_profile", {})
    statements = user_profile.get("user_statements", {})

    row = {
        "user_id": user_profile.get("user_id") or str(uuid.uuid4()),

        # Persona / Generierung
        "source_persona_id": user_profile.get("source_persona_id"),
        "profile_variant": user_profile.get("profile_variant"),
        "generation_rationale": user_profile.get("generation_rationale"),

        # Account
        "email": account.get("email"),
        "username": account.get("username"),
        "external_auth_id": account.get("external_auth_id"),

        # Person Information
        "first_name": person.get("first_name"),
        "last_name": person.get("last_name"),
        "display_name": person.get("display_name"),
        "date_of_birth": person.get("date_of_birth"),
        "age": person.get("age"),
        "gender": person.get("gender", "not_specified"),
        "life_stage": person.get("life_stage"),
        "home_city": person.get("home_city"),
        "home_postal_code": person.get("home_postal_code"),
        "home_country_code": person.get("home_country_code", "DE"),
        "city_type": person.get("city_type"),

        # Job Related
        "job_industry": job.get("job_industry"),
        "employment_status": job.get("employment_status"),
        "income_range": job.get("income_range"),
        "working_pattern": job.get("working_pattern"),
        "commute_frequency": job.get("commute_frequency"),

        # Mobility Profile
        "has_car": mobility.get("has_car"),
        "has_bike": mobility.get("has_bike"),
        "has_driving_license": mobility.get("has_driving_license"),
        "public_transport_affinity": mobility.get("public_transport_affinity"),
        "preferred_modes": to_postgres_text_array(
            mobility.get("preferred_modes")
        ),
        "avoided_modes": to_postgres_text_array(
            mobility.get("avoided_modes")
        ),
        "typical_weekday_trip_level": mobility.get("typical_weekday_trip_level"),
        "typical_weekend_trip_level": mobility.get("typical_weekend_trip_level"),

        # Activity Profile
        "leisure_intensity": activity.get("leisure_intensity"),
        "preferred_activity_types": to_postgres_text_array(
            activity.get("preferred_activity_types")
        ),
        "evening_activity_frequency": activity.get("evening_activity_frequency"),
        "weekend_activity_frequency": activity.get("weekend_activity_frequency"),

        # Ticketing Profile
        "subscription_likelihood": ticketing.get("subscription_likelihood"),
        "current_ticket_product": ticketing.get("current_ticket_product"),
        "likely_ticket_products": to_postgres_text_array(
            ticketing.get("likely_ticket_products")
        ),
        "price_sensitivity": ticketing.get("price_sensitivity"),
        "purchase_channel_preference": ticketing.get("purchase_channel_preference"),
        "employer_reimbursement_available": ticketing.get(
            "employer_reimbursement_available"
        ),

        # User Statements
        "travel_and_priorities": statements.get("travel_and_priorities"),
    }

    return row


def load_user_profiles_json(input_path: str | Path) -> list[dict[str, Any]]:
    """
    Loads user profiles from JSON.

    Supports both:
    {
      "user_profiles": [...]
    }

    and:
    [...]
    """

    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"User profiles JSON file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        user_profiles = data.get("user_profiles")
    elif isinstance(data, list):
        user_profiles = data
    else:
        raise ValueError("Input JSON must be either an object or a list.")

    if not isinstance(user_profiles, list):
        raise ValueError("Input JSON must contain a 'user_profiles' list.")

    if not user_profiles:
        raise ValueError("No user profiles found in input JSON.")

    return user_profiles


def save_user_profiles_json_as_db_csv(
    input_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """
    Loads generated user profiles from JSON, maps them to the columns of the
    user_profiles PostgreSQL DDL, and saves them as CSV.
    """

    user_profiles = load_user_profiles_json(input_path)

    rows = [
        user_profile_to_db_row(user_profile)
        for user_profile in user_profiles
    ]

    df = pd.DataFrame(rows)

    # Ensure exact column order
    df = df[USER_PROFILE_DB_COLUMNS]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Saved {len(df)} user profiles to CSV: {output_path}")

    return df