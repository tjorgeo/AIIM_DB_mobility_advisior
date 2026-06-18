from src.utils.prompt_builder import build_ai_messages
from src.utils.json_handler import load_json_file, json_to_dataframe, concat_json_responses, save_json_file
from src.utils.university_api_connection import build_university_gpt_connection, call_university_gpt 
import pandas as pd
import json

from pathlib import Path

def generate_user_profiles():
    
    persona_seed_contexts = load_json_file(Path("./data/input/personas.json"))
    
    df_user_profiles = pd.DataFrame()
    json_user_profiles = None
    
    client = build_university_gpt_connection()
    
    for persona_seed_context in persona_seed_contexts["personas"]:
        
        print("=" * 80)
        print("Generating profiles for persona: ", persona_seed_context["persona_id"])
        print("=" * 80)
   
        context = {
            "num_profiles": 5,
            "target_locations": ["Berlin", "Cologne", "Frankfurt", "Düsseldorf", "Essen", "Bochum", "Munich"],
            "persona_seed_context": persona_seed_context
        }

        messages = build_ai_messages(
            prompt_root="./prompts",
            prompt_group="user_profiles",
            context=context,
        )

        response = call_university_gpt(client, messages, max_new_tokens=4000, temperature=0.5)
        response_json = json.loads(response)

        df = json_to_dataframe(response_json, "user_profiles")
        
        if df_user_profiles.empty:
            
            df_user_profiles = df
            json_user_profiles = response_json
            
        else:
            
            df_user_profiles = pd.concat([df_user_profiles, df])
            json_user_profiles = concat_json_responses(
                responses=[json_user_profiles, response_json],
                root_key="user_profiles",
            )
            

    df_user_profiles.to_csv("./data/generated/test:user_profiles.csv")
    save_json_file(json_user_profiles, "./data/generated/json_user_profiles.json")
