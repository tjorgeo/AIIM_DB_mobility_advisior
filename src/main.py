import os
import time
import psycopg2


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


if __name__ == "__main__":
    main()