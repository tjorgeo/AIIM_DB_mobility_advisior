# Backend To-Be — Remaining Work

> **The To-Be migration shipped.** Phases A–E of the `pipeline_reengineering` branch are
> implemented and merged, so the design that used to live in this document **is now the
> architecture** — described (as the current state) in
> [BACKEND_ARCHITECTURE_REPORT.md](BACKEND_ARCHITECTURE_REPORT.md). Everything already built
> has been removed from this doc; what stays below is only the handful of items that were
> **deliberately deferred**.

## What shipped (for reference)

- **A** — `engines/` purified: the two in-engine LLM calls extracted to
  `agent/llm_steps/` (`forecast_reasoner`, `feasibility_judge`); engines are LLM-free.
- **B** — session model (`analysis_sessions` / `chat_messages` / `revisions`); the
  read-through cache rebuilds the dashboard from the snapshot alone.
- **C** — `reoptimize` split into `simulate_change` (read-only) + `apply_change` (only
  writer, ownership-checked); persistence moved to the session layer (no `Orchestrator`
  import in tools).
- **D** — one **Advisor** agent + single `POST /api/chat/{session_id}`; **memo = turn 0**
  (idempotent, cached in the transcript); `get_demand_outlook` / `get_modal_shift` tools;
  `communicator_agent` deleted.
- **E** — frontend on the session endpoint; the briefing is the first chat message; the
  static memo panel removed.

Shared invariant, preserved throughout: **every number comes from a deterministic engine;
the LLM only narrates, forecasts demand, and judges free-text feasibility.**

---

## Remaining / deferred

### 1. Drive `/api/analyze` to **zero** synchronous LLM calls

**Now:** `/api/analyze` is deterministic for the memo (removed → turn 0), but still makes
**two** LLM calls on the synchronous path — the **forecast reasoner** and the **modal-shift
feasibility judge** (both were deliberately kept on-analyze during the migration, matching
the "extract but keep on analyze" decision). The `get_demand_outlook` / `get_modal_shift`
tools currently only *surface* what analyze already computed.

**Target:** move both LLM steps off the critical path so analyze is 100% deterministic:

| Seam | Now | Target |
|---|---|---|
| memo prose | ✅ Advisor turn 0 | done |
| demand forecast | 🟨 on the analyze path | `get_demand_outlook` computes the LLM outlook **on demand** (the deterministic `seasonal_projection` still ships in the snapshot for the dashboard) |
| modal-shift feasibility | 🟨 on the analyze path | **fold into the Advisor** — the feasibility judgment is free-text reasoning over `onboarding_raw`, which the one agent can do inline when it narrates a shift; or keep a lazy `feasibility_judge` step called only when the modal-shift section is actually shown |

Result: `/api/analyze` returns numbers only; every LLM touch is the Advisor or a tool it
triggers. (Watch the interactions: the memo/`simulate` `forecast_note` and the "Looking
ahead" narration read `forecaster_out` from the snapshot — if the forecast goes fully
on-demand, those consumers need the outlook fetched/threaded through, not assumed present.)

### 2. Formal human-in-the-loop **interrupt** for `apply_change`

**Now:** confirmation is **structural** — `apply_change` requires a `proposal_id` that only a
prior `simulate_change` can mint, and checks the proposal's owner. That already prevents an
un-previewed change, but the gate lives in the tool contract rather than the graph.

**Target:** a LangGraph human-in-the-loop **interrupt** (or an explicit
`POST /api/chat/{session_id}/apply`) so the write pauses for an out-of-band user
confirmation the runtime enforces, not just the prompt + proposal-id convention.

### 3. Retire `analyst_agent.py`

**Now:** the single-call memo writer (`run_briefing`, with its deterministic tariff
pre-fetch) is **off the production path** but **kept** because the eval memo-comparison
experiment (`scripts/run_experiment.py`) still calls it.

**Target:** once the eval track is repointed at the Advisor's briefing (or the experiment is
retired), delete `analyst_agent.py` and its prompt so there is genuinely one narrative
code path. Low priority — it is eval-only and clearly scoped.

---

*Rationale and the full As-Is→To-Be reasoning that produced this plan are preserved in git
history (this file's earlier revisions); the current architecture is the As-Is report.*
