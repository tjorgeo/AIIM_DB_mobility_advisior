from pathlib import Path
import pandas as pd
from generate_user_profiles import generate_user_profiles_from_personas, load_personas_from_file, save_user_profiles_to_file
from university_api_connection import build_university_gpt_connection, call_university_gpt
from generate_user_trips import ensure_user_ids, save_trips_and_legs_to_csv, generate_trip_history_for_user_profile, generate_trips_for_user_profiles, generate_full_trip_history_for_user_profiles

def main() -> None:
    client = build_university_gpt_connection()

    DATA_DIR = Path(__file__).resolve().parent.parent / "data/input"
    personas = load_personas_from_file(
        DATA_DIR / "personas.json"
    )

    user_profiles = generate_user_profiles_from_personas(
        client=client,
        personas=personas,
        profiles_per_persona=2,
        allowed_home_locations=None,
    )

    user_profiles = ensure_user_ids(user_profiles)

    save_user_profiles_to_file(
        user_profiles=user_profiles,
        output_path=DATA_DIR / "generated_user_profiles.json",
    )
    
    all_trips = generate_full_trip_history_for_user_profiles(
        client=client,
        user_profiles=user_profiles,
        start_ts="2026-01-01T00:00:00",
        num_trips_per_user=30, # TODO hochsetzen
        interval_days=7,
        trips_per_interval=15,
    )

    df_trips, df_trip_legs = save_trips_and_legs_to_csv(
        trips=all_trips,
        trips_output_path=DATA_DIR / "generated_trips.csv",
        legs_output_path=DATA_DIR / "generated_trip_legs.csv",
    )

    print(df_trips.head())
    print(df_trip_legs.head())

    print(df_trips.head())


if __name__ == "__main__":
    main()


