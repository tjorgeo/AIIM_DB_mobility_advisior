import json
import uuid
from datetime import datetime

from database import get_connection
from graph.pipeline import graph


class Orchestrator:
    """API/session layer over the agentic LangGraph pipeline.

    The pipeline (graph) does the agent reasoning; this class owns DB context
    persistence (recommendations + audit) and shapes the exact response payload
    the frontend consumes. That separation is the backend merge: agentic engine
    inside, stable session/contract API outside.
    """

    def run_analysis(self, user_id: str) -> dict:
        # --- RUN AGENTIC PIPELINE (load_context → analyst∥forecaster∥optimizer → communicator) ---
        state = graph.invoke({"user_id": user_id})

        if state.get("error"):
            raise ValueError(state["error"])

        user = state["user"]
        user_preferences = state["user_preferences"]
        subscriptions = state["subscriptions"]
        travel_history = state["travel_history"]
        pricing_catalog = state["pricing_catalog"]

        analyst_out = state["analyst_out"]
        forecaster_out = state["forecaster_out"]
        optimizer_out = state["optimizer_out"]
        communicator_out = state["communicator_out"]

        # --- STATE MANAGEMENT & PERSISTENCE ---
        rec_id = str(uuid.uuid4())
        created_at_str = datetime.now().isoformat()

        scenarios_payload = {
            "scenarios": optimizer_out["scenarios"],
            "baseline_annual_cost": optimizer_out["baseline_annual_cost"],
            "baseline_co2_kg": optimizer_out["baseline_co2_kg"],
            "best_recommendation_id": optimizer_out["best_recommendation_id"],
            "memos": {
                "english": communicator_out["memo_english"],
                "german": communicator_out["memo_german"],
            },
        }

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
        INSERT INTO recommendations (id, user_id, created_at, scenarios, status, approval_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
            (rec_id, user_id, created_at_str, json.dumps(scenarios_payload), "ready", None),
        )
        cursor.execute(
            """
        INSERT INTO audit_log (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
            (
                str(uuid.uuid4()),
                user_id,
                "generate_recommendation",
                json.dumps(
                    {
                        "recommendation_id": rec_id,
                        "best_scenario": optimizer_out["best_recommendation_id"],
                        "memo_source": communicator_out.get("memo_source", "template"),
                    }
                ),
                created_at_str,
            ),
        )
        conn.commit()
        conn.close()

        # --- ORCHESTRATION PIPELINE SUMMARY (frontend contract) ---
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
                    "german": communicator_out["memo_german"],
                },
            },
            "raw_agent_payloads": {
                "analyst": {
                    "input": {
                        "travel_history_length": len(travel_history),
                        "subscriptions": [
                            s["service"] for s in subscriptions if s["status"] == "active"
                        ],
                    },
                    "output": analyst_out,
                },
                "forecaster": {
                    "input": {
                        "travel_history_length": len(travel_history),
                        "modes_present": list(analyst_out["mode_breakdown"].keys()),
                    },
                    "output": forecaster_out,
                },
                "optimizer": {
                    "input": {
                        "baseline_spend": optimizer_out["baseline_annual_cost"],
                        "pricing_catalog_size": len(pricing_catalog),
                        "preferences": user_preferences,
                    },
                    "output": optimizer_out,
                },
                "communicator": {
                    "input": {
                        "best_recommendation": optimizer_out["best_recommendation_id"],
                        "savings": communicator_out["annual_savings_eur"],
                        "memo_source": communicator_out.get("memo_source", "template"),
                    },
                    "output": communicator_out,
                },
            },
        }

        return pipeline_payload

    def approve_recommendation(self, rec_id: str, scenario_id: str) -> bool:
        """Updates recommendation status to approved and logs the transaction."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        rec = dict(row)
        user_id = rec["user_id"]
        approval_time = datetime.now().isoformat()

        cursor.execute(
            """
        UPDATE recommendations
        SET status = 'approved', approval_timestamp = ?
        WHERE id = ?
        """,
            (approval_time, rec_id),
        )
        cursor.execute(
            """
        INSERT INTO audit_log (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
            (
                str(uuid.uuid4()),
                user_id,
                "approve_recommendation",
                json.dumps({"recommendation_id": rec_id, "approved_scenario": scenario_id}),
                approval_time,
            ),
        )
        conn.commit()
        conn.close()
        return True


if __name__ == "__main__":
    orchestrator = Orchestrator()
    print("Orchestrator ready.")
