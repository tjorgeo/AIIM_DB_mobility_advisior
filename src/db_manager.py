import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def get_db_connection():
    """
    Erstellt eine Verbindung zur Postgres-Datenbank über DATABASE_URL.

    Beispiel:
    postgresql://postgres:postgres@db:5432/aiim
    """
    return psycopg2.connect(DATABASE_URL)

def read_table(table_name: str, limit: int = 10):
    engine = create_engine(DATABASE_URL)

    query = text(f"""
        SELECT *
        FROM {table_name}
        LIMIT :limit;
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit})

        return result
  
def load_user_profile(conn, user_id: str | UUID | None = None) -> dict[str, Any]:
    """
    Lädt ein User-Profil.

    Wenn user_id None ist, wird der erste aktive User genommen.
    Für Tests ist das praktisch.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if user_id is None:
            cur.execute(
                """
                SELECT *
                FROM user_profiles
                WHERE is_active = TRUE
                ORDER BY created_at
                LIMIT 1;
                """
            )
        else:
            cur.execute(
                """
                SELECT *
                FROM user_profiles
                WHERE user_id = %s
                  AND is_active = TRUE;
                """,
                (str(user_id),),
            )

        user = cur.fetchone()

    if user is None:
        raise ValueError("Kein aktiver User in user_profiles gefunden.")

    return dict(user)

def get_data_files():
    supported_extensions = {".csv", ".xlsx", ".xls"}

    return sorted(
        file
        for file in DATA_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in supported_extensions
    )
    
def read_data_file(file: Path) -> pd.DataFrame:
    if file.suffix.lower() == ".csv":
        return pd.read_csv(file)

    if file.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(file)

    raise ValueError(f"Nicht unterstützter Dateityp: {file}")

def get_table_name(file: Path) -> str:
    return file.stem.lower()

def import_dataframe(df: pd.DataFrame, table_name: str, engine):
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="append",
        index=False,
        method="multi",
    )

    print(f"Importiert: {len(df)} Zeilen nach {table_name}")
    
def run_import():
    engine = create_engine(DATABASE_URL)

    for file in get_data_files():
        table_name = get_table_name(file)
        df = read_data_file(file)

        import_dataframe(df, table_name, engine)
    