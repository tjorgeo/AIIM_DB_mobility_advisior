"""Single-call, structured-output LLM steps — pure-in → pure-out.

Each module here makes exactly one LLM completion over a fixed payload, validates
the reply (pydantic + ``agent.json_extract``), and returns plain data — no tool
loop, no persistence. They are the honest home for the "one structured LLM call +
deterministic fallback" pattern that used to live *inside* ``agent/engines/`` (whose
contract is now genuinely LLM-free again).

* ``forecast_reasoner`` — LLM demand reasoning over calendar text; falls back to the
  deterministic ``engines.forecasting.seasonal_projection``.
* ``feasibility_judge`` — LLM free-text feasibility judgment for modal-shift
  candidates; injected into ``engines.modal_shift.build_modal_shift_suggestions``.
"""
