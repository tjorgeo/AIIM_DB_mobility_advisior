"""Baseline pipeline — one LLM call over the raw data, nothing else.

The evaluation baseline for the main analyze pipeline (:mod:`agent.pipeline`):
where the main pipeline computes every figure with deterministic engines and only
lets the LLM write prose, this baseline hands the LLM the same raw context
``load_context`` produces (profile, preferences, subscriptions, full leg-level
travel history, subscription catalog, upcoming calendar entries) and asks it to
derive the recommended portfolio changes itself in a single call. No analysis
engine, no forecaster, no tool loop, no number guard.

The output schema deliberately mirrors the main pipeline's recommendation
vocabulary (``category_subscription_analysis[*].recommendation`` /
``actions_required``) so a judge can score both against the same rubric. Not
wired into any API endpoint or frontend — run it via
``backend/scripts/run_baseline.py``.
"""

import json
import logging
from pathlib import Path

from agent.context import load_context
from agent.llm import get_llm, llm_available
from agent.observability import trace

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).with_name("prompts") / "baseline_system.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Same action vocabulary the deterministic engine emits (see _pick_recommendation
# in agent/engines/analysis.py), so baseline and main pipeline outputs are
# directly comparable in an eval.
VALID_ACTIONS = {
    "keep_current",
    "switch_to_alternative",
    "cancel_current_go_pay_as_you_go",
    "consider_subscribing",
    "no_subscription_needed",
    "insufficient_cost_data",
}

# Leg columns handed to the LLM, in CSV order. CSV instead of a JSON list because
# the largest seed persona has ~550 legs — per-row key repetition would roughly
# triple the prompt for zero information gain.
_LEG_COLUMNS = [
    "started_at",
    "transport_mode",
    "ticket_type",
    "estimated_distance_km",
    "duration_minutes",
    "estimated_cost_eur",
    "reference_cost_eur",
    "estimated_co2_emissions",
    "user_subscription_id",
]


def _legs_as_csv(travel_history: list) -> str:
    """Serialize the leg-level history as a compact CSV block (header + one line
    per leg). Values come straight from the DB rows; None becomes an empty field."""
    header = ",".join(_LEG_COLUMNS).replace("estimated_co2_emissions", "estimated_co2_kg")
    lines = [header]
    for leg in travel_history:
        lines.append(
            ",".join("" if leg.get(col) is None else str(leg.get(col)) for col in _LEG_COLUMNS)
        )
    return "\n".join(lines)


def build_grounding(ctx: dict) -> dict:
    """Shape ``load_context`` output into the raw-data payload the baseline prompt
    documents. Everything the main pipeline's engines consume is included, un-derived:
    the only transformation is the compact CSV serialization of the travel history."""
    return {
        "user": {
            "name": ctx["user"].get("name"),
            "age": ctx["user"].get("age"),
            "gender": ctx["user"].get("gender"),
            "life_stage": ctx["user"].get("life_stage"),
            "home_city": ctx["user"].get("home_city"),
        },
        "preferences": ctx["user_preferences"],
        "current_subscriptions": ctx["subscriptions"],
        "travel_history_csv": _legs_as_csv(ctx["travel_history"]),
        "subscription_catalog": ctx["pricing_catalog"],
        "upcoming_calendar_entries": ctx["raw_calendar_entries"],
    }


def _extract_json(text: str):
    """First complete JSON object in an LLM reply (tolerates prose / ```json fences
    around it) — same approach as agent/analyst_agent.py."""
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return None


def parse_baseline_response(text: str) -> dict:
    """Validate the LLM reply into the baseline output contract.

    Shape-validates only — actions outside the known vocabulary or figures that
    don't add up are kept verbatim (flagged, not fixed), because the baseline's
    job is to show what a bare LLM actually produces, not to paper over it.
    Raises ``ValueError`` when the reply isn't usable at all.
    """
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise ValueError("Baseline response contains no JSON object")
    changes = data.get("recommended_changes")
    if not isinstance(changes, list):
        raise ValueError("Baseline response missing 'recommended_changes' list")

    invalid_actions = sorted(
        {
            str(c.get("action"))
            for c in changes
            if isinstance(c, dict) and c.get("action") not in VALID_ACTIONS
        }
    )
    return {
        "recommended_changes": changes,
        "total_estimated_savings_eur": data.get("total_estimated_savings_eur"),
        "summary": data.get("summary", ""),
        "invalid_actions": invalid_actions,
    }


def run_baseline(user_id: str) -> dict:
    """Run the baseline for one user: load raw context, make exactly one LLM call,
    return the recommended portfolio changes.

    Returns ``{"error": ...}`` when the user is missing or no LLM key is
    configured (the baseline has no deterministic fallback — without an LLM there
    is nothing to evaluate). Raises ``ValueError`` on an unusable LLM reply.
    """
    if not llm_available():
        return {"error": "No LLM configured (UNI_GPT_API_KEY missing); the baseline requires one."}

    ctx = load_context(user_id)
    if ctx.get("error"):
        return {"error": ctx["error"]}

    grounding = build_grounding(ctx)

    from langchain_core.messages import HumanMessage, SystemMessage

    with trace(
        "baseline-recommendation",
        user_id=user_id,
        tags=["baseline", "analyze-pipeline-baseline"],
        metadata={"pipeline": "baseline"},
    ) as tr:
        response = get_llm().invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Here is the customer's complete raw mobility data as JSON. "
                        "Analyze it and respond with the recommended portfolio changes "
                        "in the required JSON format.\n\n"
                        + json.dumps(grounding, ensure_ascii=False, default=str)
                    )
                ),
            ],
            config=tr.config(),
        )
        trace_id = tr.trace_id

    result = parse_baseline_response(response.content)
    if result["invalid_actions"]:
        logger.warning(
            "Baseline for user %s produced actions outside the vocabulary: %s",
            user_id,
            result["invalid_actions"],
        )
    result["pipeline"] = "baseline"
    result["user_id"] = user_id
    result["trace_id"] = trace_id
    return result
