# Unified agent package (replaces the old agents/ + graph/ split).
#
# Layout:
#   engines/    — deterministic compute; the ONLY source of every euro / CO2 number (no LLM)
#   llm_steps/  — single structured-output LLM calls (forecast reasoner, feasibility judge)
#   tools/      — @tool wrappers the Advisor calls (engines + catalog + OKF knowledge + insights)
#   prompts/    — system prompts (advisor-chat)
#   context.py  — DB read that shapes the context the engines consume
#   session.py  — analysis-session store (snapshot + chat transcript + revisions)
#   pipeline.py — deterministic /analyze driver (numbers guaranteed, no LLM prose)
#   advisor/    — the single conversational agent (opening briefing + chat follow-ups);
#                 also exposes briefing_from_snapshot for the eval experiment
