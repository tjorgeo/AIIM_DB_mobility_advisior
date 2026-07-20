"""Deterministic analyze pipeline — the number guard.

Topology (plain sequential Python, no StateGraph):
    load_context → analyze → forecast → communicate

Steps 1–2 are pure deterministic engines, so every euro / CO₂ figure is exact and
reproducible. ``analyze`` computes, per travel category, whether the currently-held
subscription (if any), a comparable catalog alternative, or paying as you go would be
cheapest — see ``category_subscription_analysis`` in agent/engines/analysis.py. The
communicate step produces the deterministic template memo only; the rich, LLM-written
briefing is now the Advisor agent's opening turn (agent/advisor), fetched on demand via
``POST /api/chat/{session_id}`` rather than generated on this synchronous path.

``run_analysis`` returns the computed components; :class:`analysis_service.AnalysisService`
persists them and shapes the exact response payload the frontend consumes.
"""

import logging

from agent.context import load_context
from agent.engines import analyze_portfolio, attach_projected_category_analysis, template_memos
from agent.engines.modal_shift import build_modal_shift_suggestions
from agent.llm_steps.feasibility_judge import judge as feasibility_judge
from agent.llm_steps.forecast_reasoner import forecast

logger = logging.getLogger(__name__)


def run_analysis(user_id: str) -> dict:
    """Run the full pipeline for one user, synchronously — including the LLM forecast
    and the Analyst memo when an LLM is configured.

    Returns a dict with ``user``, ``user_preferences``, ``subscriptions``,
    ``travel_history``, ``pricing_catalog`` and the agent outputs, or
    ``{"error": ...}`` if the user is not found.
    """
    ctx = load_context(user_id)
    if ctx.get("error"):
        return {"error": ctx["error"]}

    travel_history = ctx["travel_history"]
    subscriptions = ctx["subscriptions"]
    preferences = ctx["user_preferences"]

    # --- deterministic engine: the authoritative, reproducible numbers ---
    # category_subscription_analysis prices every current/alternative/no-subscription
    # comparison off the user's actual travel history, never off a "holding any plan
    # makes the category free" assumption — see analysis.py's _pricing_basis.
    analyst_out = analyze_portfolio(
        travel_history, subscriptions, ctx["pricing_catalog"], user_age=ctx["user"].get("age"),
        preferences=preferences,
    )
    analyst_out["preferences"] = preferences  # referenced by the memo, and re-derived from
    # in tools/simulate.py + tools/apply.py so a chat re-optimisation stays weighted the same way

    # Cross-category modal-shift comparison — deterministic candidate pricing/CO2/time
    # plus one batched LLM call judging free-text feasibility (see modal_shift.py's
    # module docstring). Runs fresh every analysis, no caching.
    analyst_out["modal_shift_suggestions"] = build_modal_shift_suggestions(
        analyst_out["mode_breakdown"], analyst_out["category_subscription_analysis"],
        ctx.get("onboarding_raw") or {}, preferences, judge=feasibility_judge,
    )

    # Forecaster consumes the analyst's forecaster_summary (dominant patterns +
    # seasonality) plus the user's upcoming calendar entries (see context.py).
    # Falls back to the deterministic baseline itself when no LLM is configured, so
    # numbers stay guarded either way.
    forecaster_out = forecast(
        analyst_out["forecaster_summary"],
        raw_calendar_entries=ctx["raw_calendar_entries"],
        forecast_horizon_days=365,
        use_llm=True,
    )

    # Project the same current-vs-alternative-vs-no-subscription comparison onto each
    # scenario's forecasted demand — deterministic, reuses analyze_portfolio's own
    # pricing/eligibility logic, never lets the forecaster (or its LLM) touch money.
    attach_projected_category_analysis(
        forecaster_out, analyst_out["mode_breakdown"], subscriptions,
        ctx["pricing_catalog"], ctx["user"].get("age"), preferences=preferences,
    )

    # --- communicate: deterministic template memo only ---
    # The rich, LLM-written briefing is now the Advisor agent's opening turn (agent/advisor),
    # fetched on demand via POST /api/chat/{session_id}, not generated on the synchronous
    # analyze path. The template memo stays as the dashboard's structured fallback text.
    name = ctx["user"]["name"]
    communicator_out = template_memos(name, analyst_out, forecaster_out)
    communicator_out["memo_source"] = "template"
    memo_trace_id = None

    return {
        "user": ctx["user"],
        "user_preferences": preferences,
        "onboarding_raw": ctx.get("onboarding_raw") or {},
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": ctx["pricing_catalog"],
        "analyst_out": analyst_out,
        "forecaster_out": forecaster_out,
        "communicator_out": communicator_out,
        # Langfuse trace id of the memo LLM call (None when tracing disabled or the
        # memo fell back to the template) — persisted so recommendation approval can
        # attach a feedback score to the exact trace that produced the memo.
        "memo_trace_id": memo_trace_id,
    }
