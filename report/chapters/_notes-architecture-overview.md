# Notes: "Architecture Overview" section (Ch. 3, `03-system-architecture-implementation.qmd`)

Working notes only — not rendered by Quarto (leading `_`, not included in `report.qmd`).
Source: `DELIVERABLES/BACKEND_ARCHITECTURE_REPORT.md` (verified against commit `b7424c2`,
2026-07-20, 134 backend tests passing).

**Budget reality check — corrected 2026-08-05:** the template's own instructions say *"The*
*document should NOT EXCEED 10 pages,"* with no carve-out for appendices. So Ch. 8's
"## Appendix" subsection almost certainly counts toward the same 10 pages as everything
else — moving a diagram there does **not** create free space, it only relocates the cost.
(The BCG-appendix might be a genuinely separate case — it's independently required and also
rendered as its own standalone PDF — but it's scoped to BCG-specific content per its own
placeholder text, so it's not a legitimate place to park our architecture diagrams either
way.)

Net effect: back to a tight budget. Chapter 3 alone already carries 7 ADR tables below this
section, plus "Agentic Behavior" and "Error Handling & Robustness" still to come, inside a
10-page document shared with 7 other chapters. Realistically **~½–¾ page** for Architecture
Overview itself, diagram included if one is used at all. The "cut first" list at the bottom
is the real release valve — treat it as such.

---

## Code verification pass — 2026-08-10 (corrections to this file)

Re-checked every factual claim below against the backend source on `main` (working tree at
`8dc49d4`). Most of the file holds up. These do not, and the drafted section was corrected
accordingly:

1. **"LLM-STEP: never a number" is wrong.** `forecast_reasoner` returns
   `predicted_demand[].estimated_trips` / `estimated_km` — those *are* numbers, and they
   reach the user: `frontend/src/pages/PortfolioDetail.jsx:622` renders the trip counts in
   the demand table. The defensible claim is narrower: **no LLM ever produces a €, CO₂ or
   time figure.** The forecaster's trip counts go straight back into
   `project_category_subscription_analysis` (`engines/analysis.py:1341`), which prices them
   with the same engine that prices today's plan. ADR-02's "any number that reaches the
   user" had the same overreach and was corrected in the chapter too.
2. **"exactly one structured-output completion" is wrong.** Both steps call plain
   `get_llm().invoke([...])` with strict-JSON instructions in the system prompt, then parse
   with the tolerant `agent/json_extract.extract_json` and validate through Pydantic. No
   `with_structured_output` anywhere. Matters for **Error Handling**: a no-parse is a
   *normal, handled* path (`reason_demand` returns `None` → deterministic fallback), not an
   exception path.
3. **"apply_change is the only writer" is only true of the saved plan.** `simulate_change`
   does write — `session.add_revision(..., status="proposed")` inserts a `revisions` row.
   And `commit_revision` (`agent/session.py:183`) does not mutate the existing snapshot: it
   writes a *new* `recommendations` + mirrored `analysis_sessions` pair with a fresh id.
   Phrase it as "only the applying step changes the saved plan", never "only it writes".
4. **`revisions` is a third store**, alongside `analysis_sessions`/`chat_messages` and the
   checkpointer tables. The "two stores, two jobs" point stays (it is about transcript vs.
   working memory), but "two other stores exist" as a total count was wrong.
5. **"No other third-party service in the request path" is wrong as stated.** Langfuse is
   called inline on the chat path — `get_prompt("advisor-chat")` is fetched per turn in
   `advisor/agent.py:_system_prompt`, plus trace/score writes. It is genuinely optional and
   no-ops without a key, but it must be named as the one *other* outbound call rather than
   denied.
6. **The confirmation is a separate HTTP request**, not a reply inside the same turn:
   `POST /api/chat/{id}/confirm` → `Command(resume=…)`. Also worth knowing but cut for
   space: `apply_change` is *structurally* gated too — it needs a `proposal_id` minted by a
   prior `simulate_change`, and checks that proposal's owner against the `user_id` injected
   from the run config (`tools/apply.py`).
7. **"the tariff catalog" in the pipeline-inputs list was ambiguous** — `load_context` reads
   `subscription_catalogs` (the *pricing* catalog). The 62-doc tariff knowledge base is
   never touched by the analyze path; only the Advisor's tools read it.
8. **The chat surface is three endpoints**, not one: `/api/chat/{id}` (briefing +
   follow-up), `/api/chat/{id}/stream` (SSE, what the frontend actually uses for
   follow-ups), `/api/chat/{id}/confirm`. "Two ways in" stays valid as an *architectural*
   split; just don't write it as "two endpoints".
9. **"Three deterministic layers" was an unsupported count.** The three named packages are
   `engines/`, `llm_steps/`, `tools/` — and `llm_steps/` is by definition not deterministic.
   Dropped the count from the draft rather than inventing a defensible triple.

Confirmed correct, no change needed: the 7 tools; 62 concept docs (excluding the reserved
`index.md`/`log.md`); `engines/` importing no `agent.llm` (grep-verified, and `modal_shift`
takes the judge as an injected callable); psycopg2 for app data vs. psycopg3 pool for the
checkpointer; the read-through cache; the per-turn system-prompt re-injection; the
idempotent turn-0 briefing; single LLM endpoint via `agent/llm.py`; the pipeline stage order.

---

## Diagram — back to inline-or-skip, not Appendix

Correction from the previous version of this note: since Appendix placement doesn't save
page budget, there's no reason left to send the reader to the back of the document for the
primary architecture figure — inline costs the same and reads better. Two real options:

1. **One diagram, inline, small.** Adapt the Chapter 1 topology diagram from the backend
   report (client → both API surfaces → three layers → the Advisor → stores → externals),
   simplified hard from its ~20-node mermaid source. Distinct from Ch. 2's `fig-pipeline`
   (which only shows the four-stage number-guard flow), so it's additive, not redundant —
   but it still costs real space, so cap it at roughly half a page.
2. **No new diagram.** Let `fig-pipeline` in Ch. 2 stay the report's one architecture figure;
   cover the topology/taxonomy points below as text plus the compact legend instead. The
   DET/LLM-STEP/AGENT legend reads fine as three lines of text — it doesn't need a rendered
   graph to land.

Recommendation: **(2)**, unless the team specifically wants a full-system topology the reader
can follow without flipping back to Ch. 2 — a chapter that already carries 7 ADR tables isn't
the place to spend a second diagram if a compact legend does the same job. Either way, drop
the separate taxonomy diagram (Ch. 13 in the backend report) — the legend below covers the
same ground at zero page cost.

---

## The taxonomy — good organizing device for the whole section

Three kinds of component, color-coded consistently through the whole backend report:

- 🟩 **DET (deterministic):** pure Python engines or thin adapters. No LLM. Source of every
  €/CO₂/minute/trip figure.
- 🟨 **LLM-STEP:** exactly one completion over a fixed payload, no tools, strict-JSON
  prompt + tolerant parse + Pydantic validation (*not* `with_structured_output` — see
  correction 2). Never a €/CO₂/time figure; always has a deterministic fallback.
- 🟪 **AGENT:** tool-using ReAct loop that autonomously calls tools until it answers. There is
  **exactly one** — the Advisor.
- The one-line rule: *"an agent runs a tool loop; everything else is a pure engine, a single
  LLM step, or a thin tool."* Worth quoting directly — it's the cleanest sentence in the
  source doc and pre-empts the reader's "wait, is the forecaster an agent?" question.
- Bottom-line count worth stating explicitly: **three deterministic layers, two single-call
  LLM steps, one agent.** Not "an LLM system with some checks" — the LLM surface is small and
  named.

---

## System surfaces & orchestration (factual, not the "why")

- Two backend surfaces on FastAPI (`src/main.py`): `POST /api/analyze` (opens a session,
  fully deterministic pipeline + 2 embedded LLM steps) and `POST /api/chat/{session_id}`
  (the one agent — delivers the turn-0 opening briefing *and* handles every follow-up).
- `/api/analyze` = a plain sequential Python function chain (`agent/pipeline.py`, wrapped by
  `AnalysisService`) — no graph runtime involved.
- `/api/chat` = one LangGraph `create_react_agent` (the Advisor).
- State this as fact here; the *justification* for splitting orchestration this way is
  already ADR-01 immediately below — don't re-argue it twice in the same chapter.
- Analyze-pipeline stages, in order: `load_context` → `analyze_portfolio` (weighted
  optimizer; per category: keep / switch / cancel / consider / no-subscription /
  insufficient-data) → modal-shift pricing + feasibility (🟨 one batched LLM call) →
  `forecast` (🟩 seasonal projection or 🟨 `forecast_reasoner`) → attach projected analysis →
  template memo (🟩 deterministic) → persist as a session snapshot.
- Read-through cache: an unforced repeat call rebuilds the dashboard payload straight from
  the stored snapshot — no recompute, no LLM call at all.
- Fuller endpoint surface, worth a compact one-liner now that space allows: alongside
  `/api/analyze` and `/api/chat`, `src/main.py` also exposes login/register, an approval
  endpoint (writes a Langfuse acceptance score), a feedback endpoint (thumbs → Langfuse
  score), and per-stage debug endpoints (`/api/analyst/{id}`, `/api/forecaster/{id}`,
  `/api/forecaster/test`). Not worth a full list in the body — one sentence naming the
  categories (auth, approval/feedback telemetry, debug) is enough; full table can live next
  to the topology figure in the Appendix if useful.

---

## Key components / tech stack (suggestion #3)

- **Backend:** Python 3.12, FastAPI + Uvicorn.
- **Persistence:** PostgreSQL 16 only — psycopg2 for app data, psycopg3 for the LangGraph
  checkpointer. No Redis, no vector DB.
- **LLM orchestration:** LangChain / `langchain-openai` for the two LLM steps; LangGraph
  `create_react_agent` for the Advisor.
- **Observability:** Langfuse — optional.
- **Frontend:** React 18 + Vite — a dashboard of structured cards plus one chat panel.
- **The three layers, concretely:**
  - `engines/` (🟩): `analysis.py` + `scoring.py` (weighted optimizer), `modal_shift.py`
    (cross-category pricing), `forecasting.py` (seasonal projection), `reoptimize.py`,
    template memo. Guardrail worth naming: `engines/` imports no `agent.llm` — the "no LLM,
    no I/O" contract is enforced, not just claimed.
  - Now affordable to name concretely (previously trimmed): both engines apply hard,
    deterministic filters before anything gets scored — `analysis.py` checks eligibility
    (age bands, class matching, unverifiable plans), `modal_shift.py` checks plausibility
    (avoided modes, licence requirements, plausible distance). Useful line for the report:
    the LLM never even *sees* an option the deterministic filters have already ruled out.
  - `agent/llm_steps/` (🟨): `forecast_reasoner` (reads calendar text, flags life events,
    returns demand scenarios), `feasibility_judge` (judges free-text modal-shift feasibility).
  - `agent/tools/` (🟩, used by the Advisor): catalog lookup, tariff RAG (list/read doc),
    insights (demand outlook, modal shift), `simulate_change`, `apply_change` — 7 tools total.

---

## Data & inputs (suggestion #3/4)

- Minimal request surface: `/api/analyze` needs only `user_id`; `/api/chat` needs
  `session_id` + the message list.
- Everything else comes from **one canonical loader**, `load_context(user_id)`, reading
  Postgres: user profile, onboarding priority scores (0–100) + free-text constraints, held
  subscriptions joined to the pricing catalog, travel history (trip legs: cost, reference
  cost, CO₂, duration, mode), the pricing catalog itself, upcoming calendar entries
  (VEVENT/RRULE-expanded).
- Worth stating plainly for the "how stable is the integration" question: the "travel
  history" is **seeded database data, not a live third-party API** — there is no brittle
  external mobility feed in the serving path.
- Tariff knowledge base: 62 markdown files under `data/Markdownfiles Abos/`, Open Knowledge
  Format (YAML front-matter: type/title/description/tags). Retrieval is **agentic navigation
  over the file tree, not embeddings/vector search** — the Advisor calls `list_tariff_docs` →
  `read_tariff_doc` itself.

---

## State management (suggestion #2 — this is the part easiest to get wrong)

- **Session snapshot** (`analysis_sessions` table) is the single read-through source of
  truth: carries the analysis, preference weights, `onboarding_raw`, subscriptions, and
  display totals. The dashboard, the Advisor's grounding, chat turns, and revisions all
  attach to it. A separate `recommendations` row (same shared id) is only the approval trail.
- **Two stores, two different jobs — don't conflate them:**
  - `chat_messages`: human-readable transcript for the UI, and the `trace_id` map for
    feedback scoring. Display/audit only.
  - LangGraph **Postgres checkpointer** (`checkpoints` / `checkpoint_writes` /
    `checkpoint_blobs`, keyed by `thread_id = session_id`): the agent's *actual* working
    memory — the full message list including every intermediate tool/observation step. This
    is what lets the ReAct loop genuinely remember earlier tool calls across separate HTTP
    requests, instead of reconstructing state by replaying flattened text history.
- System prompt is re-injected **per turn** from the latest snapshot (so it reflects any
  change applied since the last turn) rather than baked into the checkpointed history.
- Turn 0 = the opening briefing (what used to be a separate "memo" LLM call, now folded into
  the same Advisor). Idempotent — generated once per session, cached in `chat_messages`, so a
  dashboard remount doesn't re-spend an LLM call. Falls back to the deterministic template
  memo with no key configured.
- The change-execution flow as a small state machine, worth one diagram line or a short list:
  `simulate_change` (read-only, re-derives via `engines/reoptimize.py` over the snapshot,
  records a scratch "proposed" revision, returns a `proposal_id`) → Advisor asks the user to
  confirm → `apply_change` (the **only** writer) is gated by a runtime LangGraph `interrupt()`
  that pauses the graph before any write; only an explicit `POST .../confirm {confirm:true}`
  resumes and commits — and the commit *appends* a new snapshot rather than editing the old
  one (correction 3). State the mechanism here as fact; ADR-03 and Ch. 2 already carry *why*
  it needs to be a runtime gate and not just a prompt instruction — don't repeat that framing.

---

## External integrations & stability (suggestion #4)

- Exactly **one** LLM endpoint — University GPT — reached through a single thin module
  (`agent/llm.py`) shared by both LLM steps and the Advisor. No provider fan-out.
- Langfuse is optional and purely additive: a missing key makes every trace/prompt/score call
  a no-op, never a failure.
- No other third-party APIs sit in the serving path — no live routing/mobility API, no
  external vector-DB service. The single external-dependency surface of any consequence is
  that one LLM endpoint.
- Keep this section to the *fact* of "one endpoint, one access module, small blast radius."
  The specific fallback behaviors (forecast → seasonal, feasibility → feasible/low, briefing
  → template, chat → 503) belong in **Error Handling & Robustness**, not here — don't
  pre-empt that section.

---

## Already covered elsewhere in the report — do not repeat here

- **Ch. 2 (Solution Concept & Originality)** already narrates: the number-guard rationale +
  its own pipeline figure, the `interrupt()` human-oversight rationale (incl. the EU AI Act
  Art. 14/50 framing), and the shared scoring-weight rationale. Architecture Overview should
  state *structure*, not re-argue these.
- **The ADR table directly below this section, same chapter** already carries the "why" for:
  pipeline-vs-agent split (ADR-01), the number guard (ADR-02), the interrupt gate (ADR-03),
  Postgres-only persistence (ADR-04), the shared scoring primitive (ADR-05), the shared LLM
  endpoint with fallback (ADR-06), and calendar-LLM-with-fallback (ADR-07). If a sentence
  here starts explaining *why* one of these choices was made, it's probably ADR content
  leaking upward — cut it back to *what exists*.
- **Agentic Behavior** (next section) owns: how the Advisor reasons step-by-step, asks
  clarifying questions, iterates. Overview only needs to establish *that* the Advisor is the
  one ReAct agent and name its tools — not how it uses them.
- **Error Handling & Robustness** (next section) owns: the specific degradation paths and
  timeout/retry caps. Overview gets one line acknowledging the single-endpoint surface.

---

## If cutting for space, cut in this order

Space is tight again — the Appendix does not give free room (see corrected budget above).
In priority order:

1. The commit-hash / test-count verification footnote.
2. The full endpoint-surface note (auth/approval/debug endpoints) — most skippable fact in
   this file for an *overview* section; cut to zero before touching anything else.
3. The eligibility/plausibility hard-filter detail — a good line, not an essential one; no
   ADR depends on the reader having seen it here.
4. The read-through-cache detail under "System surfaces."
5. The exact onboarding data-field list — collapse to "onboarding preferences and free-text
   constraints."
6. The OKF front-matter schema detail — collapse to "62 tariff markdown files, agentic
   retrieval, no embeddings."
7. The diagram itself, if one was used — falls back to option (2) above (no new diagram).

Do **not** cut regardless of space: the two-surface split, the DET/LLM-STEP/AGENT taxonomy +
the one-rule sentence, the two-stores-two-jobs state management point, and the
single-LLM-endpoint fact. Those four are load-bearing for the ADRs and the later sections to
make sense.
