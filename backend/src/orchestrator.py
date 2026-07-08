import json
import logging
import uuid
from datetime import datetime

from database import get_connection
from agent.context import load_context
from agent.pipeline import run_analysis as run_pipeline

logger = logging.getLogger(__name__)


class Orchestrator:
    """API/session layer over the deterministic analyze pipeline.

    The pipeline computes the agent outputs (numbers deterministic, memo via the
    Analyst agent); this class owns DB context persistence (recommendations + audit)
    and shapes the exact response payload the frontend consumes. That separation is
    the backend merge: agentic engine inside, stable session/contract API outside.

    Latency guards:
    * **Read-through cache** — ``/api/analyze`` auto-runs on every dashboard mount, so
      an unforced call reuses the user's most recent ``recommendations`` row (rebuilt
      from stored JSON + a cheap ``load_context``) instead of re-running the pipeline.
      Pass ``force=True`` to recompute.
    * **Lazy LLM memo** — a fresh run defers the (slow) Analyst memo: it returns the
      deterministic numbers with the template memo immediately, and the caller schedules
      :meth:`generate_memo` as a background task. The next (cached) mount serves the
      upgraded LLM prose.
    """

    def run_analysis(self, user_id: str, force: bool = False) -> dict:
        # --- CACHE: reuse the latest recommendation unless a refresh is forced ---
        if not force:
            cached = self._load_cached(user_id)
            if cached is not None:
                return cached

        # --- FRESH RUN (load_context → analyze → forecast → template memo) ---
        # include_memo=False: defer the slow LLM memo to a background task (see main.py);
        # the deterministic numbers + template memo return immediately.
        state = run_pipeline(user_id, include_memo=False)

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
        # LLM call, so approval can attach a `recommendation-accepted` score to it. On a
        # fresh (lazy) run the memo hasn't run yet, so it starts NULL and generate_memo
        # fills it in.
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
        # Signals main.py to schedule the background LLM memo. Popped before the
        # response is returned to the client.
        payload["_fresh"] = True
        return payload

    def _load_cached(self, user_id: str):
        """Rebuild the frontend payload from the user's most recent recommendation.

        Returns ``None`` (→ caller runs a fresh analysis) when there is no prior row or
        the stored JSON can't be parsed / is pre-pivot. The agent outputs come from the
        row; the display fields (name / preferences / active subscriptions) come from a
        cheap ``load_context`` — no engines, no LLM.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT recommendation_id, analyst_output, forecaster_output,
                   optimizer_scenarios, analysis_status, created_at
            FROM recommendations
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        row = dict(row)

        try:
            analyst_out = json.loads(row["analyst_output"]) if row["analyst_output"] else {}
            forecaster_out = json.loads(row["forecaster_output"]) if row["forecaster_output"] else {}
            stored = json.loads(row["optimizer_scenarios"]) if row["optimizer_scenarios"] else {}
        except (TypeError, json.JSONDecodeError):
            return None
        # Post-pivot payloads store the per-category analysis. A row without it is a
        # stale pre-pivot record — force a fresh run rather than shape a broken payload.
        if "category_subscription_analysis" not in stored:
            return None

        ctx = load_context(user_id)
        if ctx.get("error"):
            return None

        return self._shape_payload(
            rec_id=row["recommendation_id"],
            created_at=str(row["created_at"]),
            status=row["analysis_status"] or "ready",
            user=ctx["user"],
            preferences=ctx["user_preferences"],
            subscriptions=ctx["subscriptions"],
            travel_history_len=len(ctx["travel_history"]),
            pricing_catalog_size=len(ctx["pricing_catalog"]),
            analyst_out=analyst_out,
            forecaster_out=forecaster_out,
            total_actual_annual_cost=stored.get("total_actual_annual_cost_eur", 0.0),
            total_estimated_savings=stored.get("total_estimated_savings_eur", 0.0),
            actions_required=stored.get("actions_required", []),
            memos=stored.get("memos", {}),
            memo_source=stored.get("memo_source", "template"),
        )

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
            "current_subscriptions": subscriptions,
            "summary": {
                "total_actual_annual_cost_eur": total_actual_annual_cost,
                "total_co2_kg": analyst_out.get("total_co2_kg"),
                "total_estimated_savings_eur": total_estimated_savings,
                "category_subscription_analysis": analyst_out.get(
                    "category_subscription_analysis", []
                ),
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

    def generate_memo(self, rec_id: str, user_id: str) -> None:
        """Upgrade an already-persisted recommendation with the LLM forecast + memo.

        Runs as a background task after a fresh ``/api/analyze`` returns its deterministic
        forecast + template memo. Reloads the stored agent outputs + context, regenerates
        the (slow) LLM forecast and the grounded Analyst memo, and updates the row in place
        (memo_source → "llm"). Doing both here keeps the synchronous ``/api/analyze`` fast
        (neither LLM call blocks it) and persists them together so the next cached mount
        serves the upgraded forecast and prose. Best-effort: any failure leaves the
        deterministic forecast + template memo standing.
        """
        from agent.llm import llm_available

        if not llm_available():
            return

        ctx = load_context(user_id)
        if ctx.get("error"):
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT analyst_output, forecaster_output, optimizer_scenarios "
            "FROM recommendations WHERE recommendation_id = ?",
            (rec_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        row = dict(row)
        try:
            analyst_out = json.loads(row["analyst_output"])
            forecaster_out = json.loads(row["forecaster_output"])
            stored = json.loads(row["optimizer_scenarios"])
        except (TypeError, json.JSONDecodeError):
            conn.close()
            return

        # Upgrade the forecast with the LLM now that we're off the request path. forecast()
        # self-falls-back to the deterministic result on any LLM error, so this is safe.
        try:
            from agent.engines import forecast

            forecaster_out = forecast(
                analyst_out.get("forecaster_summary", {}),
                raw_calendar_entries=ctx["raw_calendar_entries"],
                forecast_horizon_days=90,
                use_llm=True,
            )
        except Exception:
            logger.exception("Background forecast upgrade failed; deterministic forecast stands")

        name = ctx["user"]["name"]
        try:
            from agent.analyst_agent import run_briefing

            memo_en, memo_de, memo_trace_id = run_briefing(
                name,
                analyst_out,
                forecaster_out,
                ctx["pricing_catalog"],
                user_id=user_id,
            )
        except Exception:
            logger.exception("Background memo generation failed; template memo stands")
            conn.close()
            return

        stored["memos"] = {"english": memo_en, "german": memo_de}
        stored["memo_source"] = "llm"
        cursor.execute(
            "UPDATE recommendations SET optimizer_scenarios = ?, forecaster_output = ?, "
            "memo_trace_id = ? WHERE recommendation_id = ?",
            (json.dumps(stored), json.dumps(forecaster_out), memo_trace_id, rec_id),
        )
        conn.commit()
        conn.close()

    def save_revision(self, user_id: str, analyst_out: dict, revision: dict) -> str:
        """Persist a chat-driven re-optimisation as a new ``recommendations`` row.

        ``revision`` is the output of ``agent.engines.reoptimize.reoptimize_from_analysis``.
        The revised per-category analysis is folded back into a copy of ``analyst_out`` so
        the stored row stays shape-compatible with a fresh ``/api/analyze`` run, and the
        dashboard's read-through cache serves it on the next mount. Returns the new
        recommendation id.
        """
        revised_analyst = dict(analyst_out)
        revised_analyst["category_subscription_analysis"] = revision["category_subscription_analysis"]

        stored_payload = {
            "category_subscription_analysis": revision["category_subscription_analysis"],
            "total_actual_annual_cost_eur": revision["total_actual_annual_cost_eur"],
            "total_co2_kg": analyst_out.get("total_co2_kg"),
            "total_estimated_savings_eur": revision["total_estimated_savings_eur"],
            "actions_required": revision["actions_required"],
            "memo_source": "chat_revision",
            "memos": {"english": "", "german": ""},
            "applied_constraints": revision.get("applied_constraints", {}),
        }

        rec_id = str(uuid.uuid4())
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
                json.dumps(revised_analyst),
                json.dumps({}),
                json.dumps(stored_payload),
                "ready",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return rec_id

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
    orchestrator = Orchestrator()
    print("Orchestrator ready.")
