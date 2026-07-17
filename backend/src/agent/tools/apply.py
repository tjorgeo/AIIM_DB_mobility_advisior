"""``apply_change`` — the ONLY state-mutating tool.

Commits a change the user has explicitly confirmed. It takes a ``proposal_id`` minted by
a prior ``simulate_change`` (a valid id can't be fabricated, so applying is structurally
gated behind a proposal the user has already seen), re-derives the revision
**deterministically** against that proposal's own analysis snapshot, and persists it via
the session layer (``session.commit_revision`` — no ``AnalysisService`` import in a tool),
promoting the proposal to ``applied``. The dashboard's read-through cache then serves the
revised plan.

``user_id`` is injected from the run config and checked against the proposal's owner, so
the tool can never apply another user's proposal.
"""

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agent.engines.reoptimize import reoptimize_from_analysis
from agent.engines.scoring import resolve_weights
from agent.session import apply_revision, commit_revision, get_revision, get_session


def _user_id_from_config(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    return (config.get("configurable") or {}).get("user_id")


@tool
def apply_change(proposal_id: str, config: RunnableConfig = None) -> str:
    """Apply a portfolio change the user has EXPLICITLY confirmed. This is the only tool
    that changes the saved plan — never call it until the user has clearly said yes to a
    proposal you showed them via ``simulate_change``.

    Args:
        proposal_id: the id returned by the ``simulate_change`` call whose numbers the
            user just confirmed.

    Returns:
        JSON: the applied per-category analysis, the revised totals and savings, the
        concrete actions, and a ``session_id`` for the new saved recommendation.
    """
    user_id = _user_id_from_config(config)
    if not user_id:
        return json.dumps({"error": "No user in context; cannot apply a change."})

    proposal = get_revision(proposal_id)
    if not proposal or proposal["user_id"] != user_id:
        return json.dumps({
            "error": "Unknown or unauthorized proposal_id. Run simulate_change first and "
                     "apply the proposal_id it returns.",
        })

    # Re-derive against the proposal's OWN analysis snapshot (the numbers the user saw and
    # confirmed), deterministically — consistent with a fresh /api/analyze.
    session = get_session(proposal["session_id"])
    snapshot = session.get("snapshot") if session else None
    analyst_out = (snapshot or {}).get("analyst_out")
    if not analyst_out:
        return json.dumps({"error": "The analysis this proposal was based on is no longer available."})

    forecaster_out = snapshot.get("forecaster_out")
    prefs = analyst_out.get("preferences") or snapshot.get("user_preferences") or {}
    weights = resolve_weights(
        prefs.get("cost_priority"), prefs.get("co2_priority"), prefs.get("convenience_priority"),
    )
    result = reoptimize_from_analysis(
        analyst_out.get("category_subscription_analysis", []),
        proposal["constraints"], forecaster_out, weights,
    )

    result["session_id"] = commit_revision(user_id, analyst_out, result)
    apply_revision(proposal_id)  # mark the proposal committed
    result["applied"] = True
    return json.dumps(result, ensure_ascii=False, default=str)
