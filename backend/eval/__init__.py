"""Offline evaluation for the DB MoveOptimizer memo generator.

Contains the LLM-as-a-Judge evaluators (``judges.py``) used both by the Langfuse
dataset experiment (``scripts/run_experiment.py``) and the calibration harness
(``calibrate.py``). Kept out of ``src/agent`` because none of it runs on the
app's request path — it is evaluation/CI tooling.
"""
