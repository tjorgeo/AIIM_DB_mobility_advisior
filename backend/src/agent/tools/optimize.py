"""Re-optimisation tool — closes the chat → optimizer feedback loop.

The Communicator agent calls this when the user wishes to change the recommended
portfolio ("keep my car", "drop the BahnCard", "what if I switch to the
Deutschlandticket"). It re-runs the *deterministic* per-category optimisation under the
parsed constraints (``agent.engines.reoptimize``) so every figure stays engine-grounded,
also folding in a forecast-based "Looking ahead" note when the user's latest forecast
detected a life event, and — only when ``apply=True`` — persists the revision as a new
``recommendations`` row so the dashboard reflects it.

``user_id`` is injected from the run config (not exposed to the LLM), so the tool always
acts on the authenticated caller and the agent can be built once and reused.
"""

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agent.engines.reoptimize import reoptimize_from_analysis
from agent.engines.scoring import resolve_weights


def _user_id_from_config(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    return (config.get("configurable") or {}).get("user_id")


def _confirmed_turn_from_config(config: RunnableConfig | None) -> bool:
    if not config:
        return False
    return bool((config.get("configurable") or {}).get("confirmed_turn"))


def _latest_recommendation_row(user_id: str) -> dict | None:
    from database import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT analyst_output, forecaster_output FROM recommendations WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _latest_analyst_out(user_id: str, row: dict | None) -> dict | None:
    """Reuse the user's most recent persisted ``analyst_output`` (which carries the
    fully-priced per-category ``alternatives``) rather than recomputing. Falls back to a
    fresh deterministic analysis if there is no prior recommendation row."""
    if row and row.get("analyst_output"):
        try:
            return json.loads(row["analyst_output"])
        except (TypeError, json.JSONDecodeError):
            pass

    # No usable prior analysis — compute one deterministically.
    from agent.context import load_context
    from agent.engines import analyze_portfolio

    ctx = load_context(user_id)
    if ctx.get("error"):
        return None
    analyst_out = analyze_portfolio(
        ctx["travel_history"], ctx["subscriptions"], ctx["pricing_catalog"],
        user_age=ctx["user"].get("age"), preferences=ctx["user_preferences"],
    )
    analyst_out["preferences"] = ctx["user_preferences"]
    return analyst_out


def _latest_forecaster_out(row: dict | None) -> dict | None:
    """The user's most recent persisted ``forecaster_output``, if any — best-effort, a
    missing/unparseable forecast just means no forecast-based note gets added."""
    if not row or not row.get("forecaster_output"):
        return None
    try:
        return json.loads(row["forecaster_output"])
    except (TypeError, json.JSONDecodeError):
        return None


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
            "what if" without changing their saved recommendation. Ignored (forced to
            False) on the conversation's first user message — see ``applied`` in the
            response for what actually happened.

    Returns:
        JSON: the revised per-category analysis (each category may carry a
        ``forecast_note`` when the user's latest forecast detected a life event that
        would change that category's verdict under these same constraints — a
        forward-looking heads-up, not part of today's numbers), revised total cost,
        estimated savings vs. their current setup, and the concrete actions. When the
        revision was actually applied, also a ``session_id`` for the new recommendation.
    """
    user_id = _user_id_from_config(config)
    if not user_id:
        return json.dumps({"error": "No user in context; cannot re-optimise."})

    row = _latest_recommendation_row(user_id)
    analyst_out = _latest_analyst_out(user_id, row)
    if not analyst_out:
        return json.dumps({"error": "No analysis available for this user."})
    forecaster_out = _latest_forecaster_out(row)

    # Same preferences the original analysis weighted its recommendation by (persisted
    # on analyst_out since pipeline.py sets it there) — a chat-driven re-optimisation
    # without explicit keep/drop/prefer constraints must stay consistent with what a
    # fresh /api/analyze would have recommended, not silently reset to equal weights.
    prefs = analyst_out.get("preferences") or {}
    weights = resolve_weights(
        prefs.get("cost_priority"), prefs.get("co2_priority"), prefs.get("convenience_priority"),
    )

    constraints = {
        "keep": keep or [],
        "drop": drop or [],
        "prefer_plans": prefer_plans or [],
        "exclude_plans": exclude_plans or [],
    }
    result = reoptimize_from_analysis(
        analyst_out.get("category_subscription_analysis", []), constraints, forecaster_out, weights,
    )

    # Code-level confirmation gate: a change can only ever be applied starting from the
    # conversation's second user message, regardless of what the LLM requests — closes
    # the gap where a model call skips the "wait for explicit confirmation" instruction
    # and applies a change straight from an ambiguous first message like "optimize my
    # portfolio".
    if apply and not _confirmed_turn_from_config(config):
        apply = False
        result["applied"] = False
        result["note"] = (
            "apply was requested but not carried out: this is the first message in the "
            "conversation, so there has been no chance for the user to confirm yet. The "
            "revision above was computed but NOT saved. Present it and ask the user to "
            "confirm before calling reoptimize again with apply=True."
        )

    if apply:
        from orchestrator import Orchestrator

        session_id = Orchestrator().save_revision(user_id, analyst_out, result)
        result["session_id"] = session_id
        result["applied"] = True

    return json.dumps(result, ensure_ascii=False, default=str)
