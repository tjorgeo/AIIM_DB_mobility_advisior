"""Engine tools for the Analyst agent.

These wrap the deterministic engines and are **bound to a pre-loaded context** so
the agent can sequence the workflow (analyze → forecast → optimize) while every
number it reports comes verbatim from the engines — the LLM never computes money.

``make_analysis_tools(ctx)`` returns fresh closures per request; ``ctx`` is the dict
from :func:`agent.context.load_context`. The analysis is memoised across the closures
so ``forecast_demand`` can reuse the analyst's ``forecaster_summary`` without
recomputing.
"""

import json

from langchain_core.tools import tool

from agent.engines import analyze_portfolio, forecast, optimize


def make_analysis_tools(ctx: dict) -> list:
    """Build the three engine tools bound to one user's loaded context."""

    cache: dict = {}

    def _analysis() -> dict:
        if "analysis" not in cache:
            out = analyze_portfolio(ctx["travel_history"], ctx["subscriptions"])
            out["preferences"] = ctx["user_preferences"]
            cache["analysis"] = out
        return cache["analysis"]

    @tool
    def analyze_history() -> str:
        """Audit the customer's past travel: totals (trips, distance, CO₂, spend), a
        per-mode breakdown, per-subscription coverage/value, detected seasonality and
        inefficiencies. Returns the exact analysis JSON."""
        return json.dumps(_analysis(), ensure_ascii=False)

    @tool
    def forecast_demand() -> str:
        """Forecast the customer's trip demand for the next 90 days by mode, from their
        historical patterns and seasonality. Returns the exact forecast JSON."""
        return json.dumps(
            forecast(_analysis()["forecaster_summary"], calendar_events=[], forecast_horizon_days=90),
            ensure_ascii=False,
        )

    @tool
    def optimize_portfolio() -> str:
        """Compute the cost-optimal and balanced subscription portfolios over the DB
        catalogue for how this customer travels, with baseline cost, annual savings and
        the exact contract changes. Returns the exact optimizer JSON — the authoritative
        source of every recommended plan and savings figure."""
        return json.dumps(
            optimize(
                ctx["travel_history"],
                ctx["subscriptions"],
                ctx["pricing_catalog"],
                ctx["user_preferences"],
            ),
            ensure_ascii=False,
        )

    return [analyze_history, forecast_demand, optimize_portfolio]
