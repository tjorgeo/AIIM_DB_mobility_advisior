from src.utils.prompt_builder import build_ai_messages
from src.utils.json_handler import load_json_file, json_to_dataframe
from src.utils.university_api_connection import build_university_gpt_connection, call_university_gpt 
import pandas as pd

from pathlib import Path

def generate_user_subscriptions():
    
    user_profiles_json = load_json_file("./data/generated/json_user_profiles.json")
    
    print("#" * 80)
    print("Generating user subscriptions")
    print("#" * 80)

    messages = build_ai_messages(
        prompt_root="./prompts",
        prompt_group="user_subscriptions",
        context={
            "user_profiles_json": user_profiles_json,
        },
        group_files=[
            "user_subscriptions/prompt.md",
            "user_subscriptions/output_schema.md",
            "user_subscriptions/generation_rules.md",
            "user_subscriptions/provider_catalog.md",
        ],
    )
    
    client = build_university_gpt_connection()

    response = call_university_gpt(client, messages, max_new_tokens=4000, temperature=0.5)
    
    df = json_to_dataframe(response, "user_mobility_subscriptions")
    df.to_csv("./data/generated/test_user_subscriptions.csv")