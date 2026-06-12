import os
import time
import psycopg2
from university_api_connection import build_university_gpt_connection, call_university_gpt


DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    # Give Postgres a few seconds to become ready
    time.sleep(3)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()

    print("Connected to Postgres!")
    print(db_version[0])

    cursor.close()
    conn.close()
    
    # Test the basic connection
    client = build_university_gpt_connection()
    print("Testing basic API connection...")
    try:
        test_response = call_university_gpt(
            client,
            [{"role": "user", "content": "Say 'Hello from University GPT' and nothing else."}],
            max_new_tokens=50,
            temperature=0.0
        )
        print(f"✓ API Connection successful!")
        print(f"Response: {test_response}")
    except Exception as e:
        print(f"✗ API Connection failed: {e}")


if __name__ == "__main__":
    main()