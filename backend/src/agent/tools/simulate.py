"""``simulate_change`` — the read-only "what if" tool.

Re-derives the customer's per-category recommendation under requested constraints,
**deterministically** (``engines.reoptimize`` over the session snapshot's already-priced
alternatives — the LLM never computes money) and **without touching the canonical
analysis**: it records the result as a *proposed* revision (scratch, non-canonical, so
the dashboard is unchanged) and hands back a ``proposal_id`` the user can later confirm
via ``apply_change``. This is the read half of the old ``reoptimize`` tool; the write
half is ``apply_change``.

``user_id`` is injected from the run config (not exposed to the LLM), so the tool always
acts on the authenticated caller.
"""

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agent.engines.reoptimize import reoptimize_from_analysis
from agent.engines.scoring import resolve_weights
from agent.session import add_revision, latest_session_for_user


def _user_id_from_config(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    return (config.get("configurable") or {}).get("user_id")


@tool
def simulate_change(
    keep: list[str] | None = None,
    drop: list[str] | None = None,
    prefer_plans: list[str] | None = None,
    exclude_plans: list[str] | None = None,
    config: RunnableConfig = None,
) -> str:
    """Recompute the customer's subscription recommendation under their requested changes —
    READ-ONLY. Use for any "what if" or change request (keep something, drop something,
    switch to or avoid a specific product). All numbers are computed deterministically —
    never estimate them yourself. This tool changes nothing on its own; it returns the
    revised numbers and a ``proposal_id``. Present the numbers and ask the user to confirm;
    only if they explicitly do, call ``apply_change`` with that ``proposal_id``.

    Args:
        keep: travel-category names whose current subscription to keep
            (e.g. "car_sharing", "public_transport", "long_distance_rail").
        drop: travel-category names whose current subscription to cancel.
        prefer_plans: product names to choose where available (e.g. "Deutschlandticket"),
            even if not the strict cost winner.
        exclude_plans: product names the user does not want offered.

    Returns:
        JSON: the revised per-category analysis (each category may carry a ``forecast_note``
        when the user's latest forecast detected a life event that would change that
        category's verdict — a forward-looking heads-up, not today's numbers), the revised
        total cost, the estimated savings vs. their current setup, the concrete actions,
        and a ``proposal_id`` to pass to ``apply_change`` on explicit confirmation.
    """
    user_id = _user_id_from_config(config)
    if not user_id:
        return json.dumps({"error": "No user in context; cannot simulate a change."})

    session = latest_session_for_user(user_id)
    snapshot = session.get("snapshot") if session else None
    analyst_out = (snapshot or {}).get("analyst_out")
    if not analyst_out:
        return json.dumps({"error": "No analysis available for this user."})

    forecaster_out = snapshot.get("forecaster_out")
    # Weight the re-derivation the same way the original analysis did (preferences persisted
    # on analyst_out by pipeline.py, with the snapshot's own preferences as a fallback), so a
    # constraint-free simulate reproduces what a fresh /api/analyze recommended.
    prefs = analyst_out.get("preferences") or snapshot.get("user_preferences") or {}
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

    # Record as a PROPOSED revision — scratch only, does not touch the canonical session or
    # the dashboard. apply_change later references it by id (a valid id can't be fabricated,
    # so applying is structurally gated behind a prior simulate).
    result["proposal_id"] = add_revision(session["session_id"], result, status="proposed")
    result["applied"] = False
    return json.dumps(result, ensure_ascii=False, default=str)
