from pathlib import Path
import pandas as pd
from generate_user_profiles import generate_user_profiles_from_personas, load_personas_from_file, save_user_profiles_to_file, save_user_profiles_json_as_db_csv
from university_api_connection import build_university_gpt_connection
from generate_user_trips import ensure_user_ids, save_trips_and_legs_to_csv, generate_full_trip_history_for_user_profiles_with_checkpoint, save_user_trips_csv_as_db_csv, save_trip_legs_csv_as_db_csv

generate_mode = False

def main() -> None:
    
    DATA_DIR = Path(__file__).resolve().parent.parent / "data/input"
  
    if generate_mode:
        client = build_university_gpt_connection()
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
        
        trip_checkpoint_path = DATA_DIR / "checkpoints" / "trip_generation_checkpoint.json"

        all_trips = generate_full_trip_history_for_user_profiles_with_checkpoint(
            client=client,
            user_profiles=user_profiles,
            start_ts="2026-01-01T00:00:00",
            num_trips_per_user=150,
            checkpoint_path=trip_checkpoint_path,
            interval_days=7,
            trips_per_interval=12,
            max_retries=2,
        )

        df_trips, df_trip_legs = save_trips_and_legs_to_csv(
            trips=all_trips,
            trips_output_path=DATA_DIR / "generated_trips.csv",
            legs_output_path=DATA_DIR / "generated_trip_legs.csv",
        )
        
        print(df_trips.head())
        print(df_trip_legs.head())

        print(df_trips.head())

    else:
        df_user_profiles = save_user_profiles_json_as_db_csv(
            input_path=DATA_DIR / "generated_user_profiles.json",
            output_path=DATA_DIR / "user_profiles.csv",
        )

        print(df_user_profiles.head())
        
        df_user_trips = save_user_trips_csv_as_db_csv(
            input_path=DATA_DIR / "generated_trips.csv",
            output_path=DATA_DIR / "user_trips.csv",
        )

        print(df_user_trips.head())
        
        df_trip_legs = save_trip_legs_csv_as_db_csv(
            input_path=DATA_DIR / "generated_trip_legs.csv",
            output_path=DATA_DIR / "trip_legs.csv",
        )

        print(df_trip_legs.head())


if __name__ == "__main__":
    main()


