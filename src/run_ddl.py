import os
import psycopg2
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL")

SQL_DIR = Path(__file__).resolve().parent.parent / "SQL/create_table"

def get_sql_files():
    return sorted(SQL_DIR.glob("*.sql"))

def execute_sql_file(conn, sql_file: Path):
    sql = sql_file.read_text(encoding="utf-8").strip()

    if not sql:
        print(f"Übersprungen, leer: {sql_file}")
        return

    with conn.cursor() as cur:
    
        cur.execute(sql)

    print(f"Ausgeführt: {sql_file}")
    
def run_all_ddl_files():
    sql_files = get_sql_files()

    with psycopg2.connect(DATABASE_URL) as conn:
        for sql_file in sql_files:
            execute_sql_file(conn, sql_file)

        conn.commit()
        
run_all_ddl_files()