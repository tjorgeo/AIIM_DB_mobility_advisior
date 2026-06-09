import pandas as pd
import json
from sqlalchemy import create_engine

class AnalystAgent:
    def __init__(self, database_url: str):
        # Verbindung zur PostgreSQL-Datenbank im Docker-Container herstellen
        self.engine = create_engine(database_url)

    def analyze_user_mobility(self, user_id: str) -> str:
        """
        Zieht Live-Daten aus der PostgreSQL Docker-Sandbox und berechnet Ineffizienzen.
        """
        # Daten über SQL-Queries aus dem laufenden Container abfragen
        query_trips = f"SELECT * FROM travel_history WHERE user_id = '{user_id}';"
        query_subs = f"SELECT * FROM subscriptions WHERE user_id = '{user_id}';"
        
        df_user_trips = pd.read_sql_query(query_trips, con=self.engine)
        df_user_subs = pd.read_sql_query(query_subs, con=self.engine)

        if df_user_trips.empty:
            return json.dumps({"error": "Keine Daten für diese User-ID in der SQL-Sandbox gefunden."})

        # Metriken aggregieren
        total_trips = len(df_user_trips)
        total_subscription_fixed_costs = float((df_user_subs['monthly_cost_eur'] * 12).sum())
        mode_counts = df_user_trips['mode'].value_counts().to_dict()

        # Ineffizienz-Auditing (Der eigentliche Consulting-Value für den BCG-Case)
        car_sharing_trips = mode_counts.get('car_sharing', 0)
        miles_fixed_cost_annual = float(df_user_subs[df_user_subs['service'] == 'miles_carsharing']['monthly_cost_eur'].sum() * 12)
        
        efficiency_scores = {}
        savings_potential = 0.0

        # Heuristik: Wann lohnt sich die Miles-Grundgebühr für Maja?
        if car_sharing_trips < 12:
            efficiency_scores["miles_carsharing"] = f"Ineffizient (Nur {car_sharing_trips}x genutzt. Jährliche Fixkosten von €{miles_fixed_cost_annual:.2f} sind ungenutzter 'Wasted Spend')."
            savings_potential += miles_fixed_cost_annual
        else:
            efficiency_scores["miles_carsharing"] = "Gute Auslastung"

        # Auslastung Deutschlandticket validieren
        regional_train_trips = mode_counts.get('train_regional', 0)
        if regional_train_trips > 24:
            efficiency_scores["deutschlandticket"] = f"Hervorragende Auslastung ({regional_train_trips} Regionalfahrten über das Abo hochgradig amortisiert)."
        else:
            efficiency_scores["deutschlandticket"] = "Unterdurchschnittliche Nutzung"

        # Strukturiertes JSON-Output für das Multi-Agenten-System bauen
        output_payload = {
            "user_id": user_id,
            "data_source": "PostgreSQL_Docker_Sandbox",
            "audit_metrics": {
                "total_historical_trips": total_trips,
                "annual_fixed_subscription_spend_eur": round(total_subscription_fixed_costs, 2),
                "trip_distribution_by_mode": mode_counts
            },
            "efficiency_audit": efficiency_scores,
            "detected_annual_savings_potential_eur": round(savings_potential, 2)
        }

        return json.dumps(output_payload, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # Verbindungsdaten zu deinem Docker-Container
    DATABASE_URL = "postgresql://postgres:your_secure_password@localhost:5432/mobility_db"
    
    analyst = AnalystAgent(database_url=DATABASE_URL)
    
    # Majas feste UUID aus dem SQL-Skript
    maja_uuid = "4ae3d0db-1a6f-42b7-bd20-0fc61266b095"
    
    print("🚀 Starte Analyst Agent Query gegen Docker-PostgreSQL...\n")
    print(analyst.analyze_user_mobility(user_id=maja_uuid))