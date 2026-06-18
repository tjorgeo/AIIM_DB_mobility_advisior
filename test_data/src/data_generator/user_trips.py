from datetime import date, timedelta

from src.utils.prompt_builder import build_ai_messages
from src.utils.json_handler import concat_json_responses, load_json_file, json_to_dataframe, dataframe_to_json, save_json_file
from src.utils.university_api_connection import build_university_gpt_connection, call_university_gpt 
import pandas as pd
import json

from pathlib import Path

def generate_user_trips():
    
    user_profiles_json = load_json_file("./data/generated/json_user_profiles.json")
    user_subscriptions = pd.read_csv("./data/generated/test_user_subscriptions.csv")
    
    df_user_trips = pd.DataFrame()
    json_user_trips = None
    
    df_user_trip_legs = pd.DataFrame()
    json_user_trip_legs = None
    
    date_intervals = iter_date_intervals(
        start_date="2026-01-01",
        end_date="2026-06-30",
        interval_days=7,
    )
    
    client = build_university_gpt_connection()
    
    for user_profile in user_profiles_json["user_profiles"]:
        
        if user_profile["user_id"] not in ["e5f6g7h8-1111-2222-3333-444455556670", "c3d4e5f6-cccc-dddd-eeee-ffff22223333", "f9c2d5b3-1e8a-4f6c-9b0d-2a7e3c4d5f6a"]: # TODO remove later, selected 3 users from each persona
            
            continue
        
        user_id = user_profile["user_id"]
        user_subscription = user_subscriptions[user_subscriptions["user_id"] == user_id]
        user_subscription_json = dataframe_to_json(user_subscription, "user_subscription")
        
        print("#" * 80)
        print("User: ", user_id)
        print("#" * 80)
        
        for interval_start_date, interval_end_date in date_intervals:
            
            print("-" * 80)
            print(f"Generating interval: {interval_start_date} to {interval_end_date}")
            print("-" * 80)
            
            try:
                
                print("Generating trips")
    
                # Trip
                messages = build_ai_messages(
                    prompt_root="./prompts",
                    prompt_group="user_trips",
                    context={
                        "user_profile_json": user_profile,
                        "user_mobility_subscriptions_json": user_subscription_json,
                        "start_date": interval_start_date,
                        "end_date": interval_end_date,
                        "num_trips": "10-12",
                    }
                )

                response = call_university_gpt(client, messages, max_new_tokens=4000, temperature=0.5)
                
                response_json = json.loads(response)

                df = json_to_dataframe(response_json, "user_trips")
        
                if df_user_trips.empty:
                    
                    df_user_trips = df
                    json_user_trips = response_json
                    
                else:
                    
                    df_user_trips = pd.concat([df_user_trips, df])
                    json_user_trips = concat_json_responses(
                        responses=[json_user_trips, response_json],
                        root_key="user_trips",
                    )
            
                print("Generating trip legs")
                    
                # Trip leg
                messages = build_ai_messages(
                    prompt_root="./prompts",
                    prompt_group="user_trip_legs",
                    context={
                        "user_profile_json": user_profile,
                        "user_mobility_subscriptions_json": user_subscription_json,
                        "user_trips_json": response_json,
                    }
                )

                response = call_university_gpt(client, messages, max_new_tokens=4000, temperature=0.5)
                
                response_json = json.loads(response)

                df = json_to_dataframe(response_json, "trip_legs")
                
                if df_user_trip_legs.empty:
                    
                    df_user_trip_legs = df
                    json_user_trip_legs = response_json
                    
                else:
                    
                    df_user_trip_legs = pd.concat([df_user_trip_legs, df])
                    json_user_trip_legs = concat_json_responses(
                        responses=[json_user_trip_legs, response_json],
                        root_key="trip_legs",
                    )
                
            except Exception as e:
                
                print("Error, skipping user: ", user_id)
                print(str(e))
                continue
    
    df_user_trips.to_csv("./data/generated/user_trips_v1.csv")
    save_json_file(json_user_trips, "./data/generated/user_trips_v1.json")
    
    df_user_trip_legs.to_csv("./data/generated/user_trip_legs_v1.csv")
    save_json_file(json_user_trip_legs, "./data/generated/user_trip_legs_v1.json")


def iter_date_intervals(
    start_date: str,
    end_date: str,
    interval_days: int = 7,
) -> list[tuple[str, str]]:
    """
    Creates inclusive date intervals.

    Example:
        start_date="2026-01-01"
        end_date="2026-01-15"
        interval_days=7

    Returns:
        [
            ("2026-01-01", "2026-01-07"),
            ("2026-01-08", "2026-01-14"),
            ("2026-01-15", "2026-01-15"),
        ]
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    if start > end:
        raise ValueError("start_date must be before or equal to end_date")

    intervals = []
    current_start = start

    while current_start <= end:
        current_end = min(
            current_start + timedelta(days=interval_days - 1),
            end,
        )

        intervals.append(
            (
                current_start.isoformat(),
                current_end.isoformat(),
            )
        )

        current_start = current_end + timedelta(days=1)

    return intervals
