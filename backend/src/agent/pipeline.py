"""Deterministic analyze pipeline — the number guard.

Topology, in two halves:

    run_analysis:     load_context → analyze → communicate          (deterministic, ~5 ms)
    run_enrichment:   ┌ modal-shift feasibility ┐ → project → re-communicate
                      └ forecast reasoning      ┘   (the two LLM steps, concurrent)

**Every euro, gram of CO₂, minute and trip the dashboard shows comes out of the first
half**, which touches no model and no network. ``analyze`` computes, per travel
category, whether the currently-held subscription (if any), a comparable catalog
alternative, or paying as you go would be cheapest — see
``category_subscription_analysis`` in agent/engines/analysis.py — and ``template_memos``
derives ``actions_required`` / ``total_estimated_savings_eur`` from that verdict alone.

The second half adds only things no number depends on: the demand forecast and its
projected per-category view, the cross-category modal-shift suggestions, and the
forecast caveats in the memo prose. It is therefore safe to run *after* the response
has already gone out — which is what :class:`analysis_service.AnalysisService` does, so
the dashboard fills with real figures immediately instead of waiting out two model
calls (see that module's docstring). ``run_full_analysis`` keeps both halves in one
synchronous call for callers that want a complete result in one shot (``?wait=true``,
the ``/api/forecaster*`` debug endpoints, the evaluation harness).

The two LLM steps inside ``run_enrichment`` have no data dependency on each other —
the feasibility judge reads ``mode_breakdown`` + ``category_subscription_analysis``,
the forecast reasoner reads ``forecaster_summary``, and both are ready the moment
``analyze_portfolio`` returns — so they run concurrently rather than back to back.
"""

import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor

from agent.context import load_context
from agent.engines import analyze_portfolio, attach_projected_category_analysis, template_memos
from agent.engines.modal_shift import build_modal_shift_suggestions
from agent.llm_steps.feasibility_judge import judge as feasibility_judge
from agent.llm_steps.forecast_reasoner import forecast
from agent.observability import trace

logger = logging.getLogger(__name__)


def run_analysis(user_id: str) -> dict:
    """The deterministic half, synchronously: every figure the dashboard renders, and
    nothing that needs a model.

    Returns a dict with ``user``, ``user_preferences``, ``subscriptions``,
    ``travel_history``, ``pricing_catalog``, ``raw_calendar_entries`` and the agent
    outputs, or ``{"error": ...}`` if the user is not found. ``forecaster_out`` is
    ``None`` and ``analyst_out`` carries no ``modal_shift_suggestions`` until
    :func:`run_enrichment` has run over the same state.
    """
    ctx = load_context(user_id)
    if ctx.get("error"):
        return {"error": ctx["error"]}

    preferences = ctx["user_preferences"]

    # --- deterministic engine: the authoritative, reproducible numbers ---
    # category_subscription_analysis prices every current/alternative/no-subscription
    # comparison off the user's actual travel history, never off a "holding any plan
    # makes the category free" assumption — see analysis.py's _pricing_basis.
    analyst_out = analyze_portfolio(
        ctx["travel_history"], ctx["subscriptions"], ctx["pricing_catalog"],
        user_age=ctx["user"].get("age"), preferences=preferences,
    )
    analyst_out["preferences"] = preferences  # referenced by the memo, and re-derived from
    # in tools/simulate.py + tools/apply.py so a chat re-optimisation stays weighted the same way

    # --- communicate: deterministic template memo, forecast-free ---
    # actions_required and total_estimated_savings_eur come only from today's
    # category_subscription_analysis verdict, so they are already final here — the
    # enrichment pass re-runs this purely to fold in the forward-looking caveats.
    communicator_out = template_memos(ctx["user"]["name"], analyst_out, None)
    communicator_out["memo_source"] = "template"

    return {
        "user": ctx["user"],
        "user_preferences": preferences,
        "onboarding_raw": ctx.get("onboarding_raw") or {},
        "subscriptions": ctx["subscriptions"],
        "travel_history": ctx["travel_history"],
        "pricing_catalog": ctx["pricing_catalog"],
        "raw_calendar_entries": ctx["raw_calendar_entries"],
        "analyst_out": analyst_out,
        "forecaster_out": None,
        "communicator_out": communicator_out,
        # Langfuse trace id of the memo LLM call — None here and after enrichment,
        # since the memo on this path is the deterministic template. Kept because
        # recommendation approval attaches its feedback score to this id when a
        # future LLM-written memo does populate it.
        "memo_trace_id": None,
    }


def run_enrichment(state: dict, lang: str = "de") -> dict:
    """The LLM half, over a state :func:`run_analysis` already produced.

    Returns ``{"modal_shift_suggestions", "forecaster_out", "communicator_out"}``.
    Never raises: each step already degrades to a deterministic fallback on its own
    (``seasonal_projection``, feasible/low judgments), and a failure of the whole pass
    leaves the caller's deterministic result untouched.

    ``lang`` selects the language the forecaster narrates in — see
    ``llm_steps/forecast_reasoner.reason_demand``.
    """
    analyst_out = state["analyst_out"]
    preferences = state["user_preferences"]

    # One trace per analysis, so the two LLM steps below nest under it and a run has a
    # single, countable token total. No-op without Langfuse keys.
    with trace("analyze-pipeline", user_id=state["user"].get("user_id"),
               tags=["analyze", "main-pipeline"]):
        # Cross-category modal-shift comparison (deterministic candidate pricing/CO2/
        # time plus one batched LLM call judging free-text feasibility) and the demand
        # forecast (LLM reasoning, falling back to the deterministic seasonal
        # projection) read disjoint inputs, so they run at the same time rather than
        # one after the other.
        #
        # contextvars.copy_context() is load-bearing, not decoration: the enclosing
        # trace publishes its attributes through a ContextVar (observability._trace_meta,
        # read by llm_config) and Langfuse's own span context is contextvar-backed too.
        # A bare worker thread starts with a fresh, empty context, so both steps would
        # silently detach into their own root traces and a run would no longer have one
        # countable token total.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="analyze-enrich") as pool:
            shift_future = pool.submit(
                contextvars.copy_context().run,
                build_modal_shift_suggestions,
                analyst_out["mode_breakdown"], analyst_out["category_subscription_analysis"],
                state.get("onboarding_raw") or {}, preferences, feasibility_judge,
            )
            forecast_future = pool.submit(
                contextvars.copy_context().run,
                lambda: forecast(
                    analyst_out["forecaster_summary"],
                    raw_calendar_entries=state["raw_calendar_entries"],
                    forecast_horizon_days=365,
                    use_llm=True,
                    lang=lang,
                ),
            )
            modal_shift_suggestions = shift_future.result()
            forecaster_out = forecast_future.result()

    # Project the same current-vs-alternative-vs-no-subscription comparison onto each
    # scenario's forecasted demand — deterministic, reuses analyze_portfolio's own
    # pricing/eligibility logic, never lets the forecaster (or its LLM) touch money.
    attach_projected_category_analysis(
        forecaster_out, analyst_out["mode_breakdown"], state["subscriptions"],
        state["pricing_catalog"], state["user"].get("age"), preferences=preferences,
    )

    # Re-draft the template memo now that the forecast exists, so it carries the
    # forward-looking caveats. Its numbers are unchanged by construction: both
    # actions_required and total_estimated_savings_eur derive from
    # category_subscription_analysis, which the enrichment never touches.
    communicator_out = template_memos(state["user"]["name"], analyst_out, forecaster_out)
    communicator_out["memo_source"] = "template"

    return {
        "modal_shift_suggestions": modal_shift_suggestions,
        "forecaster_out": forecaster_out,
        "communicator_out": communicator_out,
    }


def apply_enrichment(state: dict, enrichment: dict) -> dict:
    """Fold :func:`run_enrichment`'s result back into a :func:`run_analysis` state,
    in place. Kept next to the two so the field names can't drift apart."""
    state["analyst_out"]["modal_shift_suggestions"] = enrichment["modal_shift_suggestions"]
    state["forecaster_out"] = enrichment["forecaster_out"]
    state["communicator_out"] = enrichment["communicator_out"]
    return state


def run_full_analysis(user_id: str, lang: str = "de") -> dict:
    """Both halves in one synchronous call — the pre-split behaviour of
    ``run_analysis``. Used by ``?wait=true``, the debug endpoints and the evaluation
    harness, where a complete result matters more than a fast first paint."""
    state = run_analysis(user_id)
    if state.get("error"):
        return state
    return apply_enrichment(state, run_enrichment(state, lang=lang))
