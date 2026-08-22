import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from database import get_connection
from agent.pipeline import apply_enrichment, run_analysis as run_pipeline, run_enrichment
from agent.session import (
    create_session,
    latest_session_for_user,
    update_session_snapshot,
)

logger = logging.getLogger(__name__)

# Background workers for the LLM enrichment pass. Small on purpose, and smaller than it
# looks: each job fans out to two threads of its own for the two model calls (see
# pipeline.run_enrichment), so N workers means up to 2N calls wanting the endpoint.
#
# What actually bounds the load is the concurrency cap in agent.llm — extra workers
# beyond it just park on the semaphore. Two is enough to keep the cap saturated while
# leaving a queue for bursts of persona switches; the rest of a burst waits its turn
# instead of arriving as a dozen simultaneous requests and being rejected.
_ENRICHMENT_WORKERS = int(os.getenv("ENRICHMENT_WORKERS", "2"))
_enrichment_pool = ThreadPoolExecutor(
    max_workers=_ENRICHMENT_WORKERS, thread_name_prefix="enrichment"
)

# How long a session may sit at enrichment_status "pending" before readers treat it as
# lost. A worker that dies mid-pass (process restart, OOM) would otherwise leave the
# dashboard polling a session that will never complete.
#
# It has to sit *above* the worst case the enrichment can legitimately take, or a slow
# forecast gets declared dead while it is still running and its result lands after the
# dashboard already gave up. That worst case is the forecast reasoner's own budget —
# FORECAST_TIMEOUT_S x (FORECAST_MAX_RETRIES + 1), 300s at the defaults — plus however
# long the call waited for one of the LLM_MAX_CONCURRENCY slots. Hence the wide margin:
# this is a liveness backstop, not a deadline anyone is meant to hit.
_ENRICHMENT_TIMEOUT_SECONDS = float(os.getenv("ENRICHMENT_TIMEOUT_SECONDS", "600"))

# enrichment_status values carried on the session snapshot and the analyze payload.
ENRICHMENT_PENDING = "pending"
ENRICHMENT_READY = "ready"
ENRICHMENT_FAILED = "failed"
# A run that never had an enrichment pass to wait for — the cached-session path for a
# snapshot persisted before this field existed.
ENRICHMENT_UNKNOWN = "unknown"


class AnalysisService:
    """The ``/api/analyze`` request lifecycle over the deterministic analyze pipeline.

    Despite the old name (``Orchestrator``) this orchestrates no agents — agentic control
    flow is the Advisor (``agent/advisor``) and deterministic sequencing is
    ``agent/pipeline.py``. This class owns the request lifecycle: read-through cache →
    run the deterministic pipeline → persist (recommendations row + session snapshot) →
    shape the exact response payload the frontend consumes, plus ``/approve``.

    Latency model
    -------------
    A fresh run returns as soon as the **deterministic** half of the pipeline is done —
    a few milliseconds — and finishes the two LLM steps on a background worker. That is
    the whole point: every euro, gram of CO₂, trip count and recommended action is
    already final in that first response (``template_memos`` derives
    ``actions_required`` and ``total_estimated_savings_eur`` from
    ``category_subscription_analysis`` alone), while the forecast, the modal-shift
    suggestions and the memo's forward-looking caveats — none of which any figure
    depends on — arrive a beat later. Waiting for them synchronously cost a median 28 s
    for numbers that were ready in 3 ms.

    Consumers see this as ``enrichment_status`` on the payload:
    ``pending`` → ``ready`` (or ``failed``). The dashboard renders the numbers straight
    away and polls ``GET /api/analyze/{session_id}/enrichment`` for the rest.
    Pass ``wait=True`` to keep the old fully-synchronous behaviour (the evaluation
    harness and ``?wait=true`` do), which returns only once everything is in.

    * **Read-through cache** — ``/api/analyze`` auto-runs on every dashboard mount, so an
      unforced call rebuilds the payload from the user's most recent **session snapshot**
      (no ``load_context``, no engines, no LLM). A missing/partial snapshot falls through
      to a fresh forced run. Pass ``force=True`` to recompute.

    Session model: a fresh run persists both a ``recommendations`` row (approval trail)
    and an ``analysis_sessions`` row (the full snapshot) sharing one id — the session is
    the read-through source of truth; the recommendations row keeps ``/approve`` working.
    The recommendation is approvable immediately, because approval acts on the
    deterministic verdict that is already final.
    """

    def run_analysis(
        self, user_id: str, force: bool = False, lang: str = "de", wait: bool = False
    ) -> dict:
        # --- CACHE: reuse the latest analysis unless a refresh is forced ---
        # The session snapshot is the sole read-through cache (self-contained, no
        # re-query); a missing/partial snapshot falls through to a fresh forced run.
        if not force:
            cached = self._load_cached_session(user_id)
            if cached is not None:
                return cached

        # --- FRESH RUN: deterministic half only (load_context → analyze → communicate) ---
        state = run_pipeline(user_id)

        if state.get("error"):
            raise ValueError(state["error"])

        if wait:
            # Fully synchronous: finish the LLM half before responding. Used by
            # ?wait=true and the evaluation harness, where a complete result matters
            # more than a fast first paint.
            try:
                apply_enrichment(state, run_enrichment(state, lang=lang))
                enrichment_status = ENRICHMENT_READY
            except Exception:
                logger.exception("Synchronous enrichment failed for user %s", user_id)
                enrichment_status = ENRICHMENT_FAILED
        else:
            enrichment_status = ENRICHMENT_PENDING

        rec_id, created_at_str = self._persist(state, user_id, enrichment_status)

        if not wait:
            # Hand the LLM half to a worker. The response below goes out without it.
            _enrichment_pool.submit(
                self._enrich_in_background, rec_id, state, created_at_str, lang
            )

        return self._payload_from_state(state, rec_id, created_at_str, "ready", enrichment_status)

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def _persist(self, state: dict, user_id: str, enrichment_status: str) -> tuple[str, str]:
        """Write the ``recommendations`` row and the ``analysis_sessions`` snapshot for
        one run, sharing a single id. Returns ``(rec_id, created_at_iso)``."""
        rec_id = str(uuid.uuid4())
        created_at_str = datetime.now().isoformat()

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
                json.dumps(state["analyst_out"]),
                json.dumps(state["forecaster_out"] or {}),
                json.dumps(self._stored_payload(state)),
                # Approvable straight away: the verdict this row records is the
                # deterministic one, which the enrichment never changes.
                "ready",
                state.get("memo_trace_id"),
                created_at_str,
            ),
        )
        conn.commit()
        conn.close()

        create_session(rec_id, user_id, self._snapshot(state, created_at_str, enrichment_status))
        return rec_id, created_at_str

    def _stored_payload(self, state: dict) -> dict:
        """The ``optimizer_scenarios`` column's contents.

        Column name kept as ``optimizer_scenarios`` (see
        database/init/01_create_table.sql) to avoid a schema migration; the payload it
        stores is now the per-category current-vs-alternative-vs-no-subscription
        analysis, not portfolio scenarios.
        """
        analyst_out = state["analyst_out"]
        communicator_out = state["communicator_out"]
        return {
            "category_subscription_analysis": analyst_out["category_subscription_analysis"],
            "total_actual_annual_cost_eur": self._total_actual_annual_cost(analyst_out),
            "total_co2_kg": analyst_out["total_co2_kg"],
            "total_estimated_savings_eur": communicator_out["total_estimated_savings_eur"],
            "actions_required": communicator_out["actions_required"],
            "memo_source": communicator_out.get("memo_source", "template"),
            "memos": self._memos(communicator_out),
        }

    def _snapshot(self, state: dict, created_at_str: str, enrichment_status: str) -> dict:
        """The full analysis snapshot persisted as a session, so the read-through cache
        can rebuild the dashboard payload without a load_context / engine / LLM re-run,
        and the advisor can ground from it later."""
        analyst_out = state["analyst_out"]
        communicator_out = state["communicator_out"]
        return {
            "created_at": created_at_str,
            "status": "ready",
            "enrichment_status": enrichment_status,
            "user": state["user"],
            "user_preferences": state["user_preferences"],
            "onboarding_raw": state.get("onboarding_raw") or {},
            "subscriptions": state["subscriptions"],
            "travel_history_len": len(state["travel_history"]),
            "pricing_catalog_size": len(state["pricing_catalog"]),
            "analyst_out": analyst_out,
            "forecaster_out": state["forecaster_out"] or {},
            "total_actual_annual_cost_eur": self._total_actual_annual_cost(analyst_out),
            "total_estimated_savings_eur": communicator_out["total_estimated_savings_eur"],
            "actions_required": communicator_out["actions_required"],
            "memos": self._memos(communicator_out),
            "memo_source": communicator_out.get("memo_source", "template"),
        }

    @staticmethod
    def _memos(communicator_out: dict) -> dict:
        return {
            "english": communicator_out["memo_english"],
            "german": communicator_out["memo_german"],
        }

    @staticmethod
    def _total_actual_annual_cost(analyst_out: dict) -> float:
        """Sum of what the user is actually paying today across every category we
        analyzed — the post-pivot equivalent of the old optimizer's baseline cost,
        built from the same per-category figures the memo and category_analysis use."""
        return round(
            sum(
                c["actual_annual_cost_eur"]
                for c in analyst_out["category_subscription_analysis"]
            ),
            2,
        )

    # ------------------------------------------------------------------ #
    # Background enrichment                                                #
    # ------------------------------------------------------------------ #

    def _enrich_in_background(
        self, rec_id: str, state: dict, created_at: str, lang: str
    ) -> None:
        """Run the LLM half for an already-answered request and fold the result into the
        persisted session, flipping ``enrichment_status`` to ``ready``.

        Never raises — it runs detached, with nobody to catch it. A failure is logged
        and recorded as ``failed`` so the dashboard stops waiting; the deterministic
        analysis the user already has stays exactly as it was.

        ``created_at`` is the original run's timestamp, carried through rather than
        re-taken, so the session keeps reporting when the analysis was run and not when
        it finished enriching.
        """
        try:
            apply_enrichment(state, run_enrichment(state, lang=lang))
            status = ENRICHMENT_READY
        except Exception:
            logger.exception("Background enrichment failed for session %s", rec_id)
            status = ENRICHMENT_FAILED

        try:
            update_session_snapshot(rec_id, self._snapshot(state, created_at, status))
            if status == ENRICHMENT_READY:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE recommendations SET forecaster_output = ? WHERE recommendation_id = ?",
                    (json.dumps(state["forecaster_out"] or {}), rec_id),
                )
                conn.commit()
                conn.close()
        except Exception:
            logger.exception("Persisting enrichment result failed for session %s", rec_id)

    def get_enrichment(self, session_id: str) -> dict | None:
        """The LLM-derived half of one analysis, for the frontend to poll after the
        deterministic payload has already rendered. ``None`` when the session is unknown.

        Returns ``{status, forecaster_out, modal_shift_suggestions, memos}``. A session
        still ``pending`` past ``ENRICHMENT_TIMEOUT_SECONDS`` is reported ``failed``
        rather than left to be polled forever — a worker that died mid-pass will never
        write its result.
        """
        from agent.session import get_session

        session = get_session(session_id)
        if session is None:
            return None
        snap = session["snapshot"] if isinstance(session["snapshot"], dict) else {}
        status = snap.get("enrichment_status", ENRICHMENT_UNKNOWN)

        if status == ENRICHMENT_PENDING and self._is_stale(snap.get("created_at")):
            status = ENRICHMENT_FAILED

        analyst_out = snap.get("analyst_out") or {}
        return {
            "session_id": session_id,
            "status": status,
            "forecaster_out": snap.get("forecaster_out") or {},
            "modal_shift_suggestions": analyst_out.get("modal_shift_suggestions", []),
            "memos": snap.get("memos", {}),
        }

    @staticmethod
    def _is_stale(created_at) -> bool:
        try:
            started = datetime.fromisoformat(str(created_at))
        except (TypeError, ValueError):
            return False
        return datetime.now() - started > timedelta(seconds=_ENRICHMENT_TIMEOUT_SECONDS)

    # ------------------------------------------------------------------ #
    # Read-through cache                                                   #
    # ------------------------------------------------------------------ #

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
        enrichment_status = snap.get("enrichment_status", ENRICHMENT_UNKNOWN)
        if enrichment_status == ENRICHMENT_PENDING and self._is_stale(snap.get("created_at")):
            enrichment_status = ENRICHMENT_FAILED

        return self._shape_payload(
            rec_id=session["session_id"],
            created_at=snap.get("created_at", session["created_at"]),
            status=status,
            enrichment_status=enrichment_status,
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

    # ------------------------------------------------------------------ #
    # Response shaping                                                     #
    # ------------------------------------------------------------------ #

    def _payload_from_state(
        self, state: dict, rec_id: str, created_at: str, status: str, enrichment_status: str
    ) -> dict:
        """Shape a fresh run's state into the response payload — the same
        :meth:`_shape_payload` the cache path uses, so the two can never drift."""
        analyst_out = state["analyst_out"]
        communicator_out = state["communicator_out"]
        return self._shape_payload(
            rec_id=rec_id,
            created_at=created_at,
            status=status,
            enrichment_status=enrichment_status,
            user=state["user"],
            preferences=state["user_preferences"],
            subscriptions=state["subscriptions"],
            travel_history_len=len(state["travel_history"]),
            pricing_catalog_size=len(state["pricing_catalog"]),
            analyst_out=analyst_out,
            forecaster_out=state["forecaster_out"] or {},
            total_actual_annual_cost=self._total_actual_annual_cost(analyst_out),
            total_estimated_savings=communicator_out["total_estimated_savings_eur"],
            actions_required=communicator_out["actions_required"],
            memos=self._memos(communicator_out),
            memo_source=communicator_out.get("memo_source", "template"),
        )

    def _shape_payload(
        self,
        *,
        rec_id,
        created_at,
        status,
        enrichment_status,
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
            # Where the LLM half of this analysis stands: "pending" (still running in
            # the background — every figure below is nonetheless final), "ready",
            # "failed", or "unknown" for a snapshot written before the split. The
            # dashboard polls /api/analyze/{session_id}/enrichment while pending.
            "enrichment_status": enrichment_status,
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
                # Empty until the background enrichment lands (see enrichment_status).
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
                    # Empty until the background enrichment lands.
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
