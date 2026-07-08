import json
import uuid
from datetime import datetime

from database import get_connection
from agent.pipeline import run_analysis as run_pipeline


class Orchestrator:
    """API/session layer over the deterministic analyze pipeline.

    The pipeline computes the agent outputs (numbers deterministic, memo via the
    Analyst agent); this class owns DB context persistence (recommendations + audit)
    and shapes the exact response payload the frontend consumes. That separation is
    the backend merge: agentic engine inside, stable session/contract API outside.
    """

    def run_analysis(self, user_id: str) -> dict:
        # --- RUN PIPELINE (load_context → analyze → forecast → communicate) ---
        state = run_pipeline(user_id)

        if state.get("error"):
            raise ValueError(state["error"])

        user = state["user"]
        user_preferences = state["user_preferences"]
        subscriptions = state["subscriptions"]
        travel_history = state["travel_history"]
        pricing_catalog = state["pricing_catalog"]

        analyst_out = state["analyst_out"]
        forecaster_out = state["forecaster_out"]
        communicator_out = state["communicator_out"]

        # --- STATE MANAGEMENT & PERSISTENCE ---
        rec_id = str(uuid.uuid4())
        created_at_str = datetime.now().isoformat()

        category_analysis = analyst_out["category_subscription_analysis"]
        # Sum of what the user is actually paying today across every category we
        # analyzed (each category's own current sub cost + out-of-pocket spend) — the
        # closest equivalent to the old optimizer's "baseline_annual_cost", but built
        # from the same per-category figures the memo and category_analysis use.
        total_actual_annual_cost = round(sum(c["actual_annual_cost_eur"] for c in category_analysis), 2)

        # Column name kept as `optimizer_scenarios` (see database/init/01_create_table.sql)
        # to avoid a schema migration; the payload it stores is now the per-category
        # current-vs-alternative-vs-no-subscription analysis, not portfolio scenarios.
        scenarios_payload = {
            "category_subscription_analysis": category_analysis,
            "total_actual_annual_cost_eur": total_actual_annual_cost,
            "total_co2_kg": analyst_out["total_co2_kg"],
            "total_estimated_savings_eur": communicator_out["total_estimated_savings_eur"],
            "actions_required": communicator_out["actions_required"],
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
                "total_actual_annual_cost_eur": total_actual_annual_cost,
                "total_co2_kg": analyst_out["total_co2_kg"],
                "total_estimated_savings_eur": communicator_out["total_estimated_savings_eur"],
                "category_subscription_analysis": category_analysis,
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
                        "pricing_catalog_size": len(pricing_catalog),
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
                "communicator": {
                    "input": {
                        "total_estimated_savings_eur": communicator_out["total_estimated_savings_eur"],
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
