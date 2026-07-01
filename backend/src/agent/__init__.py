# Unified agent package (replaces the old agents/ + graph/ split).
#
# Layout:
#   engines/   — deterministic compute; the ONLY source of every euro / CO2 number
#   tools/     — @tool wrappers the LLM agents call (engines + catalog + OKF knowledge)
#   prompts/   — system prompts for the Analyst and Communicator agents
#   context.py — DB read that shapes the context the engines consume
#   pipeline.py — deterministic /analyze driver (numbers guaranteed, LLM only writes prose)
#   analyst_agent.py / communicator_agent.py — the two LLM agents
