import json
import uuid
from datetime import datetime
from database import get_connection
from agents.analyst import AnalystAgent
from agents.forecaster import ForecasterAgent
from agents.optimizer import OptimizerAgent
from agents.communicator import CommunicatorAgent

class Orchestrator:
    def __init__(self):
        self.analyst = AnalystAgent()
        self.forecaster = ForecasterAgent()
        self.optimizer = OptimizerAgent()
        self.communicator = CommunicatorAgent()

    def run_analysis(self, user_id: str) -> dict:
        """
        Coordinates the end-to-end synchronous flow:
        Database Query -> Analyst -> Forecaster -> Optimizer -> Communicator -> Save State
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch User details
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            raise ValueError(f"User with ID {user_id} not found in database.")
            
        user = dict(user_row)
        user_preferences = json.loads(user["preferences"])
        user_consent = json.loads(user["consent_status"])
        
        # 2. Fetch active subscriptions
        cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
        subscriptions = [dict(row) for row in cursor.fetchall()]
        
        # 3. Fetch travel history for past 12 months
        cursor.execute("SELECT * FROM travel_history WHERE user_id = ? ORDER BY trip_date ASC", (user_id,))
        travel_history = [dict(row) for row in cursor.fetchall()]
        
        # 4. Fetch the entire pricing catalog
        cursor.execute("SELECT * FROM pricing_catalog")
        pricing_catalog = [dict(row) for row in cursor.fetchall()]
        
        conn.close()

        # --- EXECUTE AGENT PIPELINE ---
        
        # Agent 1: Analyst
        # Ingests logs & active subscriptions, outputs efficiency audit
        analyst_out = self.analyst.run(travel_history, subscriptions)
        # Store preferences inside analyst output for reference in communicator
        analyst_out["preferences"] = user_preferences
        
        # Agent 2: Forecaster
        # Ingests logs, outputs 6-month seasonal projection
        forecaster_out = self.forecaster.run(travel_history)
        
        # Agent 3: Optimizer
        # Ingests analyst metrics, forecaster predictions, pricing catalog, and preferences.
        # Outputs Scenario A (Cost-Optimized) and Scenario B (Balanced).
        optimizer_out = self.optimizer.run(travel_history, subscriptions, pricing_catalog, user_preferences)
        
        # Agent 4: Communicator
        # Ingests analyst and optimizer outputs, drafts consulting memos
        communicator_out = self.communicator.run(user["name"], analyst_out, optimizer_out)
        
        # --- STATE MANAGEMENT & PERSISTENCE ---
        
        rec_id = str(uuid.uuid4())
        created_at_str = datetime.now().isoformat()
        
        # Bundle the scenarios into a JSON string
        scenarios_payload = {
            "scenarios": optimizer_out["scenarios"],
            "baseline_annual_cost": optimizer_out["baseline_annual_cost"],
            "baseline_co2_kg": optimizer_out["baseline_co2_kg"],
            "best_recommendation_id": optimizer_out["best_recommendation_id"],
            "memos": {
                "english": communicator_out["memo_english"],
                "german": communicator_out["memo_german"]
            }
        }
        
        # Save recommendation to database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO recommendations (id, user_id, created_at, scenarios, status, approval_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (rec_id, user_id, created_at_str, json.dumps(scenarios_payload), "ready", None))
        
        # Add an audit log entry
        cursor.execute("""
        INSERT INTO audit_log (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            user_id,
            "generate_recommendation",
            json.dumps({"recommendation_id": rec_id, "best_scenario": optimizer_out["best_recommendation_id"]}),
            created_at_str
        ))
        
        conn.commit()
        conn.close()

        # --- ORCHESTRATION PIPELINE SUMMARY ---
        # Returns high-fidelity payload containing both summary results and raw agent IOs.
        pipeline_payload = {
            "session_id": rec_id,
            "status": "ready",
            "timestamp": created_at_str,
            "user_id": user_id,
            "customer_name": user["name"],
            "db_customer_id": user["db_customer_id"],
            "preferences": user_preferences,
            "current_subscriptions": subscriptions,
            "summary": {
                "baseline_cost": optimizer_out["baseline_annual_cost"],
                "baseline_co2": optimizer_out["baseline_co2_kg"],
                "recommended_scenario": optimizer_out["best_recommendation_id"],
                "scenarios": optimizer_out["scenarios"],
                "memos": {
                    "english": communicator_out["memo_english"],
                    "german": communicator_out["memo_german"]
                }
            },
            # Raw payloads for the bottom Technical Inspector
            "raw_agent_payloads": {
                "analyst": {
                    "input": {
                        "travel_history_length": len(travel_history),
                        "subscriptions": [s["service"] for s in subscriptions if s["status"] == "active"]
                    },
                    "output": analyst_out
                },
                "forecaster": {
                    "input": {
                        "travel_history_length": len(travel_history),
                        "modes_present": list(analyst_out["mode_breakdown"].keys())
                    },
                    "output": forecaster_out
                },
                "optimizer": {
                    "input": {
                        "baseline_spend": optimizer_out["baseline_annual_cost"],
                        "pricing_catalog_size": len(pricing_catalog),
                        "preferences": user_preferences
                    },
                    "output": optimizer_out
                },
                "communicator": {
                    "input": {
                        "best_recommendation": optimizer_out["best_recommendation_id"],
                        "savings": communicator_out["annual_savings_eur"]
                    },
                    "output": communicator_out
                }
            }
        }
        
        return pipeline_payload

    def approve_recommendation(self, rec_id: str, scenario_id: str) -> bool:
        """
        Updates recommendation status to approved and logs the transaction.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch recommendation to confirm existence
        cursor.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
            
        rec = dict(row)
        user_id = rec["user_id"]
        
        approval_time = datetime.now().isoformat()
        
        # Update recommendation
        cursor.execute("""
        UPDATE recommendations 
        SET status = 'approved', approval_timestamp = ?
        WHERE id = ?
        """, (approval_time, rec_id))
        
        # Log to audit trail
        cursor.execute("""
        INSERT INTO audit_log (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            user_id,
            "approve_recommendation",
            json.dumps({"recommendation_id": rec_id, "approved_scenario": scenario_id}),
            approval_time
        ))
        
        conn.commit()
        conn.close()
        return True

if __name__ == "__main__":
    # In-module testing
    orchestrator = Orchestrator()
    print("Orchestrator ready.")
