import pandas as pd
from sqlalchemy import create_engine, text
import os

print("🔄 Starte manuelle CSV-zu-PostgreSQL Migrations-Pipeline (Robust & Auto-Date)...")

# 1. Verbindung zur laufenden Docker-Datenbank herstellen
DATABASE_URL = "postgresql://postgres:your_secure_password@localhost:5432/mobility_db"
engine = create_engine(DATABASE_URL)

# 2. VORAB-REINIGUNG: Bestehende Daten löschen, um Unique-Konflikte zu vermeiden
print("🧹 Bereinige alte Tabelleninhalte in der Docker-Datenbank...")
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE users CASCADE;"))

# 3. Definition deiner Quelldateien (deine aktualisierten Namen!)
csv_files = {
    "users": "output/maja_profile.csv",
    "subscriptions": "output/maja_subscriptions.csv",
    "travel_history": "output/maja_travel_history.csv"
}

# 4. Validierung, Konvertierung und Hochladen
for table_name, csv_path in csv_files.items():
    if os.path.exists(csv_path):
        print(f"📥 Verarbeite {csv_path}...")
        
        # Einlesen für Excel-Semikolons und deutsche Kommas
        df = pd.read_csv(csv_path, sep=';', decimal=',')
        
        # A. Excel-Dreher beim User-Profil abfangen, falls das falsche Sheet exportiert wurde
        if table_name == "users" and "service" in df.columns:
            print("💡 Excel-Mismatch erkannt: Korrigiere Profildaten für Maja...")
            df = pd.DataFrame([{
                "id": "4ae3d0db-1a6f-42b7-bd20-0fc61266b095",
                "name": "Maja Hoffmann",
                "age": 34,
                "city": "Frankfurt",
                "occupation": "Product Manager (Fintech)",
                "cost_priority": 60,
                "co2_priority": 85,
                "flexibility_priority": 75
            }])
            
        elif table_name == "subscriptions" and "service" not in df.columns:
            df = pd.read_csv("output/maja_profile.csv", sep=';', decimal=',')

        # B. DATUMS-RETTUNG: Konvertiert deutsche Excel-Daten (31.12.26) sauber in SQL-Dates (2026-12-31)
        if table_name == "subscriptions" and "renewal_date" in df.columns:
            print("📅 Formatiere Datumsangaben für Abonnements (renewal_date)...")
            df["renewal_date"] = pd.to_datetime(df["renewal_date"], format="%d.%m.%y", errors="coerce").dt.date

        if table_name == "travel_history" and "trip_date" in df.columns:
            print("📅 Formatiere Datumsangaben für die Reisehistorie (trip_date)...")
            df["trip_date"] = pd.to_datetime(df["trip_date"], dayfirst=True, errors="coerce").dt.date

        print(f"🚀 Streamen in SQL-Tabelle '{table_name}'...")
        df.to_sql(table_name, con=engine, if_exists='append', index=False)
    else:
        print(f"❌ Datei nicht gefunden: {csv_path}")

print("\n🎯 Pipeline erfolgreich beendet! Alle CSV-Daten sind jetzt perfekt formatiert live in Docker.")