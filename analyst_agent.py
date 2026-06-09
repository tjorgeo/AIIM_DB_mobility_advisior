import pandas as pd
import json
from sqlalchemy import create_engine

class AnalystAgent:
    def __init__(self, database_url: str):
        # Establish connection to the PostgreSQL database running inside the Docker container
        self.engine = create_engine(database_url)

    def analyze_user_mobility(self, user_id: str) -> str:
        """
        Fetches live data from the PostgreSQL Docker sandbox and evaluates inefficiencies.
        """
        # Query data using SQL statements from the active container
        query_trips = f"SELECT * FROM travel_history WHERE user_id = '{user_id}';"
        query_subs = f"SELECT * FROM subscriptions WHERE user_id = '{user_id}';"
        
        df_user_trips = pd.read_sql_query(query_trips, con=self.engine)
        df_user_subs = pd.read_sql_query(query_subs, con=self.engine)

        if df_user_trips.empty:
            return json.dumps({"error": "No data found for this user_id in the SQL sandbox."})

        # Aggregate core metrics
        total_trips = len(df_user_trips)
        total_subscription_fixed_costs = float((df_user_subs['monthly_cost_eur'] * 12).sum())
        mode_counts = df_user_trips['mode'].value_counts().to_dict()

        # Inefficiency auditing (The core consulting value for the BCG case)
        car_sharing_trips = mode_counts.get('car_sharing', 0)
        miles_fixed_cost_annual = float(df_user_subs[df_user_subs['service'] == 'miles_carsharing']['monthly_cost_eur'].sum() * 12)
        
        efficiency_scores = {}
        savings_potential = 0.0

        # Heuristic: Evaluating the business case for Maja's Miles base fee
        if car_sharing_trips < 12:
            efficiency_scores["miles_carsharing"] = f"Inefficient (Used only {car_sharing_trips}x. Annual fixed costs of €{miles_fixed_cost_annual:.2f} represent unutilized 'Wasted Spend')."
            savings_potential += miles_fixed_cost_annual
        else:
            efficiency_scores["miles_carsharing"] = "Optimal utilization"

        # Validating Deutschlandticket subscription value
        regional_train_trips = mode_counts.get('train_regional', 0)
        if regional_train_trips > 24:
            efficiency_scores["deutschlandticket"] = f"Excellent utilization ({regional_train_trips} regional trips highly amortized by the subscription)."
        else:
            efficiency_scores["deutschlandticket"] = "Underutilized subscription"

        # Build structured JSON payload for the multi-agent system
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
    # Connection credentials for your Docker container
    DATABASE_URL = "postgresql://postgres:your_secure_password@localhost:5432/mobility_db"
    
    analyst = AnalystAgent(database_url=DATABASE_URL)
    
    # Maja's fixed UUID from the SQL seed script
    maja_uuid = "4ae3d0db-1a6f-42b7-bd20-0fc61266b095"
    
    print("🚀 Querying Analyst Agent against Docker PostgreSQL...\n")
    print(analyst.analyze_user_mobility(user_id=maja_uuid))