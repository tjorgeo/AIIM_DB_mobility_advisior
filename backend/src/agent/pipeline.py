"""Deterministic analyze pipeline — the number guard.

Topology (plain sequential Python, no StateGraph):
    load_context → analyze → forecast → optimize → communicate

Steps 1–3 are pure deterministic engines, so every euro / CO₂ figure is exact and
reproducible and the frontend contract is guaranteed. The communicate step runs the
deterministic template memo first (the fallback), then — when an LLM is configured —
replaces the memo prose with the Analyst agent's version (which may consult the OKF
tariff knowledge base). If the LLM is missing or errors, the template memo stands.

``run_analysis`` returns the computed components; :class:`orchestrator.Orchestrator`
persists them and shapes the exact response payload the frontend consumes.
"""

import logging

from agent.context import load_context
from agent.engines import analyze_portfolio, forecast, optimize, template_memos
from agent.llm import llm_available

logger = logging.getLogger(__name__)


def run_analysis(user_id: str) -> dict:
    """Run the deterministic pipeline for one user.

    Returns a dict with ``user``, ``user_preferences``, ``subscriptions``,
    ``travel_history``, ``pricing_catalog`` and the four agent outputs, or
    ``{"error": ...}`` if the user is not found.
    """
    ctx = load_context(user_id)
    if ctx.get("error"):
        return {"error": ctx["error"]}

    travel_history = ctx["travel_history"]
    subscriptions = ctx["subscriptions"]
    preferences = ctx["user_preferences"]

    # --- deterministic engines: the authoritative, reproducible numbers ---
    analyst_out = analyze_portfolio(travel_history, subscriptions)
    analyst_out["preferences"] = preferences  # referenced by the memo

    # Forecaster consumes the analyst's forecaster_summary (dominant patterns +
    # seasonality) plus the user's upcoming calendar entries (see context.py).
    # Demand-only + deterministic fallback, so numbers stay guarded.
    forecaster_out = forecast(
        analyst_out["forecaster_summary"],
        raw_calendar_entries=ctx["raw_calendar_entries"],
        forecast_horizon_days=90,
    )

    optimizer_out = optimize(
        travel_history, subscriptions, ctx["pricing_catalog"], preferences
    )
    # Hand the already-computed result to the memo step so the Analyst agent's
    # optimize_portfolio tool reuses it instead of re-running the optimizer.
    ctx["optimizer_out"] = optimizer_out

    # --- communicate: template memo, upgraded to LLM prose when available ---
    name = ctx["user"]["name"]
    communicator_out = template_memos(name, analyst_out, optimizer_out)
    communicator_out["memo_source"] = "template"

    if llm_available():
        try:
            from agent.analyst_agent import run_briefing

            memo_en, memo_de = run_briefing(ctx, name)
            communicator_out["memo_english"] = memo_en
            communicator_out["memo_german"] = memo_de
            communicator_out["memo_source"] = "llm"
        except Exception:
            logger.exception("Analyst memo generation failed; using template memo")
            communicator_out["memo_source"] = "template_fallback"

    return {
        "user": ctx["user"],
        "user_preferences": preferences,
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": ctx["pricing_catalog"],
        "analyst_out": analyst_out,
        "forecaster_out": forecaster_out,
        "optimizer_out": optimizer_out,
        "communicator_out": communicator_out,
    }
