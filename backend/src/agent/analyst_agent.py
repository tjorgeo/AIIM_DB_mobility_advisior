"""The Analyst agent — sequences the analyze → forecast → optimize workflow and writes
the customer-facing consulting memo.

It is a genuine tool-using ReAct agent: its system prompt (``prompts/analyst_system.md``)
walks it through calling the deterministic engine tools (``analyze_history`` /
``forecast_demand`` / ``optimize_portfolio``) and the OKF tariff knowledge base, then
writing the memo. Because the numbers come verbatim from the engine tools, the LLM never
computes money — see the "never state a number you did not get from a tool" rule.

Used by :mod:`agent.pipeline` for the ``/analyze`` memo. Requires an LLM key (``pipeline``
guards with ``llm_available()`` and falls back to the deterministic template memo). The
``/analyze`` contract numbers are assembled separately from direct engine calls, so a
misbehaving agent can never corrupt the figures the dashboard reads.
"""

import json
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from agent.llm import get_llm
from agent.tools.analysis_tools import make_analysis_tools
from agent.tools.catalog import lookup_subscriptions
from agent.tools.knowledge import list_tariff_docs, read_tariff_doc

_PROMPT_PATH = Path(__file__).with_name("prompts") / "analyst_system.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Bound the tool-use loop so a misbehaving model can't run away (analyze → forecast →
# optimize + a few tariff lookups fit comfortably below this).
_RECURSION_LIMIT = 20


def _extract_json(text: str):
    """Pull the first complete JSON object out of an LLM reply (tolerates prose or
    ```json fences before/after it). Uses raw_decode from the first ``{`` so it stops
    at that object's actual matching closing brace, instead of a greedy regex that
    would span to the *last* ``}`` in the whole text if any stray braces follow."""
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return None


def run_briefing(ctx: dict, name: str) -> tuple[str, str]:
    """Run the analyze→forecast→optimize workflow and write the (english, german) memo.

    ``ctx`` is the loaded context from :func:`agent.context.load_context`; the engine
    tools are bound to it so every number is engine-computed. Raises on malformed output
    so the caller can fall back to the template memo.
    """
    tools = make_analysis_tools(ctx) + [
        lookup_subscriptions,
        list_tariff_docs,
        read_tariff_doc,
    ]
    agent = create_react_agent(get_llm(), tools)
    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"The customer is {name}. Run the full workflow with your tools, "
                        "then write the recommendation memo as strict JSON."
                    )
                ),
            ]
        },
        config={"recursion_limit": _RECURSION_LIMIT},
    )

    data = _extract_json(result["messages"][-1].content)
    if not data or "english" not in data or "german" not in data:
        raise ValueError("Analyst memo response missing english/german keys")
    return data["english"], data["german"]
