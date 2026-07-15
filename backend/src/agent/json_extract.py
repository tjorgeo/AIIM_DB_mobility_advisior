"""Shared helper for pulling a JSON object out of an LLM's free-text reply.

Every structured-output LLM call in this codebase (forecasting.py, analyst_agent.py,
modal_shift.py) writes STRICT JSON in the prompt but still gets prose/code-fence
wrapped replies back often enough that this can't be a bare ``json.loads``.
"""

import json


def extract_json(text: str):
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
