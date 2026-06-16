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
    
    client = build_university_gpt_connection()
    
    for user_profile in user_profiles_json["user_profiles"]:
        
        try:
    
            user_id = user_profile["user_id"]
            user_subscription = user_subscriptions[user_subscriptions["user_id"] == user_id]
            user_subscription_json = dataframe_to_json(user_subscription, "user_subscription")
            
            print("#" * 80)
            print("User: ", user_id)
            print("#" * 80)
            
            print("Generating trips")
        
            # Trip
            messages = build_ai_messages(
                prompt_root="./prompts",
                prompt_group="user_trips",
                context={
                    "user_profile_json": user_profile,
                    "user_mobility_subscriptions_json": user_subscription_json,
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-15",
                    "num_trips": "15",
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
    
    df_user_trips.to_csv("./data/generated/test_user_trips.csv")
    save_json_file(json_user_trips, "./data/generated/json_user_trips.json")
    
    df_user_trip_legs.to_csv("./data/generated/test_user_trip_legs.csv")
    save_json_file(json_user_trip_legs, "./data/generated/json_user_trip_legs.json")

