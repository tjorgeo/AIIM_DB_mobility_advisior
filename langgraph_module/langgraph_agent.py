"""
DB MoveOptimizer - University GPT Workflow Module
This module defines the LangGraph workflow that can be used with `langgraph dev`
"""

import os
from typing import List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
UNI_GPT_BASE_URL = "https://chat.kiconnect.nrw/api/v1"
UNI_GPT_MODEL = "Openai GPT OSS 120B"
UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")

# Initialize OpenAI client (lazy initialization)
_client = None

def get_client():
    """Get or initialize the OpenAI client."""
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=UNI_GPT_BASE_URL,
            api_key=UNI_GPT_API_KEY
        )
    return _client

# Define state schema
class ChatState(TypedDict):
    messages: List[dict]
    response: str
    status: str

def _normalize_message(m) -> dict:
    if isinstance(m, str):
        return {"role": "user", "content": m}
    if isinstance(m, dict):
        return {"role": m.get("role", "user"), "content": m.get("content", "")}
    # LangChain BaseMessage objects
    role = getattr(m, "type", "user")
    if role == "human":
        role = "user"
    return {"role": role, "content": getattr(m, "content", str(m))}

def call_university_gpt(messages, max_new_tokens=512, temperature=0.0):
    """Call the University of Cologne GPT endpoint."""
    client = get_client()
    plain_messages = [_normalize_message(m) for m in messages]
    response = client.chat.completions.create(
        model=UNI_GPT_MODEL,
        messages=plain_messages,
        max_tokens=max_new_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()

# Define node functions
def process_user_input(state: ChatState) -> ChatState:
    print(f"Processing {len(state['messages'])} messages...")
    return {"status": "processing"}

def call_api(state: ChatState) -> ChatState:
    try:
        response = call_university_gpt(
            messages=state["messages"],
            max_new_tokens=512,
            temperature=0.0
        )
        return {"response": response, "status": "complete"}
    except Exception as e:
        return {"response": f"Error: {str(e)}", "status": "error"}

def format_output(state: ChatState) -> ChatState:
    if state["status"] == "complete":
        print("Output formatted successfully")
    return {}

# Build the workflow
def build_graph():
    """Build and return the LangGraph workflow."""
    workflow = StateGraph(ChatState)

    # Add nodes
    workflow.add_node("input_processor", process_user_input)
    workflow.add_node("api_caller", call_api)
    workflow.add_node("output_formatter", format_output)

    # Define edges
    workflow.add_edge(START, "input_processor")
    workflow.add_edge("input_processor", "api_caller")
    workflow.add_edge("api_caller", "output_formatter")
    workflow.add_edge("output_formatter", END)

    return workflow.compile()

# Export the graph for langgraph dev
graph = build_graph()
