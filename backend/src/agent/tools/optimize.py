"""Re-optimisation tool — closes the chat → optimizer feedback loop.

The Communicator agent calls this when the user wishes to change the recommended
portfolio ("keep my car", "drop the BahnCard", "what if I switch to the
Deutschlandticket"). It re-runs the *deterministic* per-category optimisation under the
parsed constraints (``agent.engines.reoptimize``) so every figure stays engine-grounded,
and — only when ``apply=True`` — persists the revision as a new ``recommendations`` row
so the dashboard reflects it.

``user_id`` is injected from the run config (not exposed to the LLM), so the tool always
acts on the authenticated caller and the agent can be built once and reused.
"""

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agent.engines.reoptimize import reoptimize_from_analysis


def _user_id_from_config(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    return (config.get("configurable") or {}).get("user_id")


def _latest_analyst_out(user_id: str) -> dict | None:
    """Reuse the user's most recent persisted ``analyst_output`` (which carries the
    fully-priced per-category ``alternatives``) rather than recomputing. Falls back to a
    fresh deterministic analysis if there is no prior recommendation row."""
    from database import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT analyst_output FROM recommendations WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row and dict(row).get("analyst_output"):
        try:
            return json.loads(dict(row)["analyst_output"])
        except (TypeError, json.JSONDecodeError):
            pass

    # No usable prior analysis — compute one deterministically.
    from agent.context import load_context
    from agent.engines import analyze_portfolio

    ctx = load_context(user_id)
    if ctx.get("error"):
        return None
    return analyze_portfolio(
        ctx["travel_history"], ctx["subscriptions"], ctx["pricing_catalog"],
        user_age=ctx["user"].get("age"),
    )


@tool
def reoptimize(
    keep: list[str] | None = None,
    drop: list[str] | None = None,
    prefer_plans: list[str] | None = None,
    exclude_plans: list[str] | None = None,
    apply: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Recompute the customer's subscription recommendation under their requested changes.

    Call this whenever the user wants to change the plan (keep something, drop something,
    switch to or avoid a specific product) or asks a "what if" question about their
    portfolio. All numbers are computed deterministically — never estimate them yourself.

    Args:
        keep: travel-category names whose current subscription the user wants to keep
            (e.g. "car_sharing", "public_transport", "long_distance_rail").
        drop: travel-category names whose current subscription the user wants to cancel.
        prefer_plans: product names the user wants chosen where available
            (e.g. "Deutschlandticket"), even if not the strict cost winner.
        exclude_plans: product names the user does not want offered.
        apply: set True ONLY when the user has clearly confirmed they want to apply the
            revised plan (e.g. "yes, update my plan"). False (default) just answers a
            "what if" without changing their saved recommendation.

    Returns:
        JSON: the revised per-category analysis, revised total cost, estimated savings vs.
        their current setup, and the concrete actions. When apply=True, also a
        ``session_id`` for the newly saved recommendation.
    """
    user_id = _user_id_from_config(config)
    if not user_id:
        return json.dumps({"error": "No user in context; cannot re-optimise."})

    analyst_out = _latest_analyst_out(user_id)
    if not analyst_out:
        return json.dumps({"error": "No analysis available for this user."})

    constraints = {
        "keep": keep or [],
        "drop": drop or [],
        "prefer_plans": prefer_plans or [],
        "exclude_plans": exclude_plans or [],
    }
    result = reoptimize_from_analysis(
        analyst_out.get("category_subscription_analysis", []), constraints
    )

    if apply:
        from orchestrator import Orchestrator

        session_id = Orchestrator().save_revision(user_id, analyst_out, result)
        result["session_id"] = session_id
        result["applied"] = True

    return json.dumps(result, ensure_ascii=False, default=str)
