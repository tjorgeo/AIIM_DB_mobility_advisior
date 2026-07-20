"""Read-only tools that surface already-computed analysis from the session snapshot.

Both return figures the deterministic pipeline already produced on ``/api/analyze`` (no
recomputation, no LLM) — they just expose them to the Advisor agent so it can narrate the
demand outlook or a cross-category modal-shift suggestion on demand instead of having
every number pre-stuffed into its prompt.

``user_id`` is injected from the run config; the tools read that user's latest session.
"""

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agent.session import latest_session_for_user


def _snapshot_for(config: RunnableConfig | None) -> dict | None:
    user_id = (config.get("configurable") or {}).get("user_id") if config else None
    if not user_id:
        return None
    session = latest_session_for_user(user_id)
    return session.get("snapshot") if session else None


@tool
def get_demand_outlook(config: RunnableConfig = None) -> str:
    """Get the customer's forecasted travel-demand outlook for the coming months
    (baseline scenario, and a life-event scenario when the calendar implies one). Use it
    when the user asks about the future, an upcoming move/trip, or how their travel might
    change. All figures are precomputed — report them, never invent them.

    Returns:
        JSON: the forecast (scenarios with per-mode predicted demand, plus
        ``uncertainty_flags`` and a bilingual rationale), or an error if unavailable.
    """
    snapshot = _snapshot_for(config)
    if not snapshot:
        return json.dumps({"error": "No analysis available for this user."})
    forecast = snapshot.get("forecaster_out")
    if not forecast:
        return json.dumps({"error": "No demand outlook available."})
    return json.dumps(forecast, ensure_ascii=False, default=str)


@tool
def get_modal_shift(config: RunnableConfig = None) -> str:
    """Get cross-category modal-shift suggestions — whether shifting some trips onto a
    *different* transport category (e.g. car-sharing trips onto public transport) would
    score better on the customer's weighted cost/CO2/time priorities than staying. Use it
    when the user asks how to save more, travel greener, or change how they get around.
    Only mention a shift where ``suggested_shift`` is not null; all figures are precomputed.

    Returns:
        JSON: one entry per travel category with a ``suggested_shift`` (or null) plus the
        stay-vs-shift cost/CO2/time figures, or an error if unavailable.
    """
    snapshot = _snapshot_for(config)
    if not snapshot:
        return json.dumps({"error": "No analysis available for this user."})
    analyst_out = snapshot.get("analyst_out") or {}
    suggestions = analyst_out.get("modal_shift_suggestions") or []
    return json.dumps(suggestions, ensure_ascii=False, default=str)
