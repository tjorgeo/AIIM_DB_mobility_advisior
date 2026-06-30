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

        # Persist into the production recommendations table (one row per analysis run).
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
        INSERT INTO recommendations (
            recommendation_id, user_id,
            analyst_output, forecaster_output, optimizer_scenarios,
            analysis_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                rec_id,
                user_id,
                json.dumps(analyst_out),
                json.dumps(forecaster_out),
                json.dumps(scenarios_payload),
                "ready",
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
            "db_customer_id": user["user_id"],
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
                            s.get("provider_plan_name")
                            for s in subscriptions
                            if s["subscription_status"] == "active"
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
        """Marks a recommendation approved and records the selected scenario."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT recommendation_id FROM recommendations WHERE recommendation_id = ?",
            (rec_id,),
        )
        if not cursor.fetchone():
            conn.close()
            return False

        approval_time = datetime.now().isoformat()
        cursor.execute(
            """
        UPDATE recommendations
        SET analysis_status = 'approved',
            selected_scenario_id = ?,
            approved_at = ?
        WHERE recommendation_id = ?
        """,
            (scenario_id, approval_time, rec_id),
        )
        conn.commit()
        conn.close()
        return True


if __name__ == "__main__":
    orchestrator = Orchestrator()
    print("Orchestrator ready.")
