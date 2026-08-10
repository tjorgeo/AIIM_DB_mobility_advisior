import json
import logging
import uuid
from datetime import datetime

from database import get_connection
from agent.pipeline import run_analysis as run_pipeline
from agent.session import create_session, latest_session_for_user

logger = logging.getLogger(__name__)


class AnalysisService:
    """The ``/api/analyze`` request lifecycle over the deterministic analyze pipeline.

    Despite the old name (``Orchestrator``) this orchestrates no agents — agentic control
    flow is the Advisor (``agent/advisor``) and deterministic sequencing is
    ``agent/pipeline.py``. This class owns the request lifecycle: read-through cache → run
    the pipeline → persist (recommendations row + session snapshot) → shape the exact
    response payload the frontend consumes, plus ``/approve``. Deterministic plumbing that
    stays off the LLM/agent path, so the numbers stay guarded and analyze stays LLM-free.

    Latency guard:
    * **Read-through cache** — ``/api/analyze`` auto-runs on every dashboard mount, so an
      unforced call rebuilds the payload from the user's most recent **session snapshot**
      (no ``load_context``, no engines, no LLM). A missing/partial snapshot falls through
      to a fresh forced run. Pass ``force=True`` to recompute. A forced/fresh run is fully
      synchronous — it waits for the LLM forecast before returning, so the response always
      reflects the final result, calendar-driven life events included, with no follow-up
      call needed.

    Session model: a fresh run persists both a ``recommendations`` row (approval trail)
    and an ``analysis_sessions`` row (the full snapshot) sharing one id — the session is
    the read-through source of truth; the recommendations row keeps ``/approve`` working.
    """

    def run_analysis(self, user_id: str, force: bool = False) -> dict:
        # --- CACHE: reuse the latest analysis unless a refresh is forced ---
        # The session snapshot is the sole read-through cache (self-contained, no
        # re-query); a missing/partial snapshot falls through to a fresh forced run.
        if not force:
            cached = self._load_cached_session(user_id)
            if cached is not None:
                return cached

        # --- FRESH RUN (load_context → analyze → forecast → communicate), synchronous ---
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

        memos = {
            "english": communicator_out["memo_english"],
            "german": communicator_out["memo_german"],
        }
        memo_source = communicator_out.get("memo_source", "template")

        category_analysis = analyst_out["category_subscription_analysis"]
        # Sum of what the user is actually paying today across every category we
        # analyzed — the post-pivot equivalent of the old optimizer's baseline cost,
        # built from the same per-category figures the memo and category_analysis use.
        total_actual_annual_cost = round(
            sum(c["actual_annual_cost_eur"] for c in category_analysis), 2
        )
        total_estimated_savings = communicator_out["total_estimated_savings_eur"]
        actions_required = communicator_out["actions_required"]

        # --- STATE MANAGEMENT & PERSISTENCE ---
        rec_id = str(uuid.uuid4())
        created_at_str = datetime.now().isoformat()

        # Column name kept as `optimizer_scenarios` (see database/init/01_create_table.sql)
        # to avoid a schema migration; the payload it stores is now the per-category
        # current-vs-alternative-vs-no-subscription analysis, not portfolio scenarios.
        stored_payload = {
            "category_subscription_analysis": category_analysis,
            "total_actual_annual_cost_eur": total_actual_annual_cost,
            "total_co2_kg": analyst_out["total_co2_kg"],
            "total_estimated_savings_eur": total_estimated_savings,
            "actions_required": actions_required,
            "memo_source": memo_source,
            "memos": memos,
        }

        # Persist into the production recommendations table (one row per analysis run).
        # memo_trace_id links this recommendation to the Langfuse trace of the memo
        # LLM call, so approval can attach a `recommendation-accepted` score to it.
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
        INSERT INTO recommendations (
            recommendation_id, user_id,
            analyst_output, forecaster_output, optimizer_scenarios,
            analysis_status, memo_trace_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                rec_id,
                user_id,
                json.dumps(analyst_out),
                json.dumps(forecaster_out),
                json.dumps(stored_payload),
                "ready",
                state.get("memo_trace_id"),
                created_at_str,
            ),
        )
        conn.commit()
        conn.close()

        # Persist the full analysis snapshot as a session (same id as the recommendations
        # row) so the read-through cache can rebuild the dashboard payload without a
        # load_context / engine / LLM re-run, and the advisor can ground from it later.
        snapshot = {
            "created_at": created_at_str,
            "status": "ready",
            "user": user,
            "user_preferences": user_preferences,
            "onboarding_raw": state.get("onboarding_raw") or {},
            "subscriptions": subscriptions,
            "travel_history_len": len(travel_history),
            "pricing_catalog_size": len(pricing_catalog),
            "analyst_out": analyst_out,
            "forecaster_out": forecaster_out,
            "total_actual_annual_cost_eur": total_actual_annual_cost,
            "total_estimated_savings_eur": total_estimated_savings,
            "actions_required": actions_required,
            "memos": memos,
            "memo_source": memo_source,
        }
        create_session(rec_id, user_id, snapshot)

        payload = self._shape_payload(
            rec_id=rec_id,
            created_at=created_at_str,
            status="ready",
            user=user,
            preferences=user_preferences,
            subscriptions=subscriptions,
            travel_history_len=len(travel_history),
            pricing_catalog_size=len(pricing_catalog),
            analyst_out=analyst_out,
            forecaster_out=forecaster_out,
            total_actual_annual_cost=total_actual_annual_cost,
            total_estimated_savings=total_estimated_savings,
            actions_required=actions_required,
            memos=memos,
            memo_source=memo_source,
        )
        return payload

    def _load_cached_session(self, user_id: str):
        """Rebuild the frontend payload purely from the user's most recent **session
        snapshot** — no ``load_context``, no engines, no LLM. Returns ``None`` (→ caller
        runs a fresh analysis) when there is no session or its snapshot is missing/partial.

        The session shares its id with the ``recommendations`` row from the same run, so
        the current approval status is read from there (a trivial indexed lookup) to keep
        an approved recommendation showing as approved without a full re-derivation.
        """
        session = latest_session_for_user(user_id)
        if session is None:
            return None
        snap = session["snapshot"]
        if not isinstance(snap, dict) or "analyst_out" not in snap or "user" not in snap:
            return None  # partial/pre-session snapshot — fall through

        status = self._recommendation_status(session["session_id"]) or snap.get("status", "ready")
        return self._shape_payload(
            rec_id=session["session_id"],
            created_at=snap.get("created_at", session["created_at"]),
            status=status,
            user=snap["user"],
            preferences=snap.get("user_preferences", {}),
            subscriptions=snap.get("subscriptions", []),
            travel_history_len=snap.get("travel_history_len", 0),
            pricing_catalog_size=snap.get("pricing_catalog_size", 0),
            analyst_out=snap["analyst_out"],
            forecaster_out=snap.get("forecaster_out", {}),
            total_actual_annual_cost=snap.get("total_actual_annual_cost_eur", 0.0),
            total_estimated_savings=snap.get("total_estimated_savings_eur", 0.0),
            actions_required=snap.get("actions_required", []),
            memos=snap.get("memos", {}),
            memo_source=snap.get("memo_source", "template"),
        )

    def _recommendation_status(self, rec_id: str):
        """Current ``analysis_status`` of the recommendations row sharing this id, or
        ``None`` if there isn't one. Trivial indexed lookup — no engines/LLM."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT analysis_status FROM recommendations WHERE recommendation_id = ?",
            (rec_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row).get("analysis_status") if row else None

    def _shape_payload(
        self,
        *,
        rec_id,
        created_at,
        status,
        user,
        preferences,
        subscriptions,
        travel_history_len,
        pricing_catalog_size,
        analyst_out,
        forecaster_out,
        total_actual_annual_cost,
        total_estimated_savings,
        actions_required,
        memos,
        memo_source,
    ) -> dict:
        """The exact response contract the frontend consumes. Shared by the fresh-run
        and cache paths so they can never drift."""
        communicator_out = {
            "memo_english": memos.get("english"),
            "memo_german": memos.get("german"),
            "memo_source": memo_source,
            "total_estimated_savings_eur": total_estimated_savings,
            "actions_required": actions_required,
        }
        return {
            "session_id": rec_id,
            "status": status,
            "timestamp": created_at,
            "user_id": user["user_id"],
            "customer_name": user["name"],
            "db_customer_id": user["user_id"],
            "preferences": preferences,
            "current_subscriptions": [
                item for item in subscriptions
                if item.get("subscription_status") == "active"
            ],
            "summary": {
                "total_actual_annual_cost_eur": total_actual_annual_cost,
                "total_co2_kg": analyst_out.get("total_co2_kg"),
                "total_estimated_savings_eur": total_estimated_savings,
                "category_subscription_analysis": analyst_out.get(
                    "category_subscription_analysis", []
                ),
                "modal_shift_suggestions": analyst_out.get("modal_shift_suggestions", []),
                "memos": {
                    "english": communicator_out["memo_english"],
                    "german": communicator_out["memo_german"],
                },
            },
            "raw_agent_payloads": {
                "analyst": {
                    "input": {
                        "travel_history_length": travel_history_len,
                        "subscriptions": [
                            s.get("provider_plan_name")
                            for s in subscriptions
                            if s.get("subscription_status") == "active"
                        ],
                        "pricing_catalog_size": pricing_catalog_size,
                    },
                    "output": analyst_out,
                },
                "forecaster": {
                    "input": {
                        "travel_history_length": travel_history_len,
                        "modes_present": list(analyst_out.get("mode_breakdown", {}).keys()),
                    },
                    "output": forecaster_out,
                },
                "communicator": {
                    "input": {
                        "total_estimated_savings_eur": total_estimated_savings,
                        "memo_source": memo_source,
                    },
                    "output": communicator_out,
                },
            },
        }

    def approve_recommendation(self, rec_id: str, scenario_id: str) -> bool:
        """Marks a recommendation approved and records the selected scenario.

        Approval is the app's strongest quality signal, so it is also recorded in
        Langfuse as a `recommendation-accepted` score on the memo's trace (when
        tracing was enabled at analyze time). Best-effort: scoring never blocks the
        approval.
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT memo_trace_id FROM recommendations WHERE recommendation_id = ?",
            (rec_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        memo_trace_id = dict(row).get("memo_trace_id")

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

        from agent.observability import create_score

        create_score(
            trace_id=memo_trace_id,
            name="recommendation-accepted",
            value=1,
            data_type="BOOLEAN",
            comment=f"Scenario {scenario_id} approved",
        )
        return True


if __name__ == "__main__":
    service = AnalysisService()
    print("AnalysisService ready.")
