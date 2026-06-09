"""
DB MoveOptimizer - Analyst → Optimizer Pipeline
Notebook 04 workflow adapted for LangGraph Studio / langgraph dev

Pipeline flow:
    travel_data
        ↓
    analyst_node   (LLM: pattern summary, no tools)
        ↓ analyst_summary
    optimizer_node (LLM + lookup_subscriptions tool, ReAct loop)
        ↓
    messages[-1].content  (final recommendation)
"""

import json
import os
from pathlib import Path
from typing import Annotated, TypedDict

import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

# Configuration
UNI_GPT_BASE_URL = "https://chat.kiconnect.nrw/api/v1"
UNI_GPT_MODEL = "Openai GPT OSS 120B"
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")

# Resolve CSV path relative to this file so it works from any working directory
CATALOG_PATH = Path(__file__).parent.parent / "data" / "subscriptions.csv"
catalog_df = pd.read_csv(CATALOG_PATH)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class PipelineState(TypedDict):
    travel_data: dict                           # input: user profile + travel log
    analyst_summary: str                        # analyst → optimizer handoff
    messages: Annotated[list, add_messages]     # optimizer ReAct loop history


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ANALYST_PROMPT = """You are a Deutsche Bahn mobility analyst.
Review the user's travel log and respond with exactly these four sections:
1. DOMINANT ROUTE — most frequent origin-destination pair
2. TICKET MIX — breakdown of ticket types used
3. SPEND SUMMARY — total spend and average cost per trip
4. ONE OBSERVATION — a single sentence noting an inefficiency or opportunity
Be factual and brief. Do not make recommendations."""

OPTIMIZER_PROMPT = """You are a Deutsche Bahn mobility optimizer.
You receive an analyst summary of a user's travel behaviour.
Use the lookup_subscriptions tool to retrieve the current product catalog,
then recommend the single best subscription change for this user.
Show the expected annual saving. Be concise — three sentences maximum."""


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def lookup_subscriptions(filter_type: str = "all") -> str:
    """Look up Deutsche Bahn subscription products from the catalog.

    Args:
        filter_type: 'card', 'subscription', or 'all'.

    Returns:
        Formatted table of matching DB products with prices and conditions.
    """
    df = catalog_df.copy()
    if filter_type != "all":
        df = df[df["type"] == filter_type]
    return df.to_string(index=False) if not df.empty else f"No products for '{filter_type}'."


tools = [lookup_subscriptions]


# ---------------------------------------------------------------------------
# LLM setup — lazy so import succeeds even before .env is fully resolved
# ---------------------------------------------------------------------------

_llm = None
_llm_with_tools = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=UNI_GPT_MODEL,
            openai_api_key=UNI_GPT_API_KEY,
            openai_api_base=UNI_GPT_BASE_URL,
            temperature=0.0,
        )
    return _llm


def _get_llm_with_tools() -> ChatOpenAI:
    global _llm_with_tools
    if _llm_with_tools is None:
        _llm_with_tools = _get_llm().bind_tools(tools)
    return _llm_with_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_travel_data(user: dict) -> str:
    subs = ", ".join(user.get("current_subscriptions", []))
    trips = json.dumps(user.get("travel_log", []), indent=2, ensure_ascii=False)
    return (
        f"Analyse the travel log for {user['name']} ({user['user_id']}).\n"
        f"Current subscriptions: {subs}\n\n"
        f"Travel log (JSON):\n{trips}"
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def analyst_node(state: PipelineState) -> dict:
    """Analyse travel patterns and write a structured summary."""
    response = _get_llm().invoke([
        SystemMessage(content=ANALYST_PROMPT),
        HumanMessage(content=_format_travel_data(state["travel_data"])),
    ])
    return {"analyst_summary": response.content}


def optimizer_node(state: PipelineState) -> dict:
    """Recommend the best subscription using the catalog tool (ReAct loop)."""
    if not state["messages"]:
        # First entry into the optimizer: build the initial message from the analyst handoff
        initial_msg = HumanMessage(content=(
            "Based on the analyst summary below, recommend the best DB subscription.\n"
            "Use the lookup_subscriptions tool to check the catalog before answering.\n\n"
            f"ANALYST SUMMARY:\n{state['analyst_summary']}"
        ))
        history = [initial_msg]
        response = _get_llm_with_tools().invoke(
            [SystemMessage(content=OPTIMIZER_PROMPT)] + history
        )
        # Return both the seeding message and the LLM response so the full
        # conversation is visible in Studio's message trace.
        return {"messages": history + [response]}
    else:
        # Subsequent calls (after a tool result): continue from existing history
        response = _get_llm_with_tools().invoke(
            [SystemMessage(content=OPTIMIZER_PROMPT)] + state["messages"]
        )
        return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph():
    tool_node = ToolNode(tools)
    workflow = StateGraph(PipelineState)

    workflow.add_node("analyst", analyst_node)
    workflow.add_node("optimizer", optimizer_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "analyst")
    workflow.add_edge("analyst", "optimizer")
    workflow.add_conditional_edges("optimizer", tools_condition)  # ReAct loop
    workflow.add_edge("tools", "optimizer")

    return workflow.compile()


graph = build_graph()
