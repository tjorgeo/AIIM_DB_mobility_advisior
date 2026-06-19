from src.data_generator.user_profiles import generate_user_profiles
from src.data_generator.user_subscriptions import generate_user_subscriptions
from src.data_generator.user_trips import generate_user_trips

from pathlib import Path

def main() -> None:
    
    # generate_user_profiles()
    # generate_user_subscriptions()
    generate_user_trips()
    

if __name__ == "__main__":
    main()