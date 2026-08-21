# data — tariff knowledge base and reference figures

Static reference material the backend reads at runtime, plus source documents
behind the CO₂ model. This is **not** the seed data for the database — that
lives in [`database/seed/`](../database/seed/).

| Path | What it is | Read at runtime? |
| --- | --- | --- |
| `Markdownfiles Abos/` | tariff, pricing and AGB documents for 63 mobility products — the RAG corpus | **yes**, by the advisor |
| `co2_emissions.md` | Umweltbundesamt CO₂ figures per passenger-kilometre | no — provenance for the factor table |
| `test_data/` | superseded persona CSVs and a forecaster test fixture | no — legacy |

---

## The tariff knowledge base

`Markdownfiles Abos/` is the corpus the chat advisor consults when a customer
asks what a tariff actually covers. 63 markdown documents across four
categories:

```text
Markdownfiles Abos/
├── index.md                 # generated listing — the entry point
├── Bike Sharing/            # callabike, nextbike, swapfiets
├── Car Sharing/             # free2move, miles, sixt, teilauto
├── E-Scooter/               # bolt, dott, lime, voi
└── ÖPNV_Bahncards/          # Deutschlandticket + BahnCard 25/50/100, 1st and 2nd class
```

Each product folder holds its terms (`*_agb.md`) and its prices
(`*_pricing.md`, `*_preise.md`, `*_tarife.md`). The documents are in German,
as published by the providers.

### How retrieval works

Retrieval is **by navigation, not embeddings** — there is no vector store and no
embedding dependency anywhere in the project. The advisor:

1. calls `list_tariff_docs` to see every document's title, type, tags and a
   short description;
2. picks the ones it needs and calls `read_tariff_doc` with the document id.

Both tools are in
[`backend/src/agent/tools/knowledge.py`](../backend/src/agent/tools/knowledge.py).
This keeps the corpus greppable and diffable in git, at the cost of the agent
spending a turn choosing documents.

### Open Knowledge Format

The corpus follows Google Cloud's
[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog)
(OKF v0.1, Apache-2.0). Each document carries YAML front matter whose only
required field is `type`, plus the recommended `title`, `description`, `tags`
and `timestamp`. `index.md` is reserved by the spec, carries no front matter,
and exists for progressive disclosure.

**Front matter is the source of truth** for a document's metadata. `index.md` is
generated from it.

> [!TIP]
> The tools scan the tree directly and fall back to a prose heuristic for any
> document still missing front matter, so retrieval keeps working even if
> `index.md` is stale or a document was added by hand.

### Adding or updating a document

1. Drop the markdown file into the right category and provider folder, following
   the `<provider>_<kind>.md` naming.
2. Regenerate the metadata and index from `backend/`:

   ```python
   from agent.tools.knowledge import seed_frontmatter, build_index
   seed_frontmatter()   # writes conformant front matter into any doc lacking it
   build_index()        # regenerates index.md from the front matter
   ```

   `seed_frontmatter()` infers `type` and `tags` from the folder and filename, so
   correct placement matters more than hand-writing metadata.

3. Check the new entry appears in `index.md`.

> [!NOTE]
> The knowledge directory is located at runtime by trying `KNOWLEDGE_DIR`, then
> `./data/Markdownfiles Abos` relative to the working directory, then two
> repo-relative fallbacks. Set `KNOWLEDGE_DIR` to point the advisor at a
> different corpus.

---

## CO₂ reference figures

`co2_emissions.md` holds the Umweltbundesamt's 2022 greenhouse-gas figures per
passenger-kilometre, with methane and nitrous oxide converted to CO₂
equivalents — from zero for walking and cycling up to 123 g/Pkm for a ferry.

> [!IMPORTANT]
> No code reads this file. It is the **provenance** for the hand-maintained
> factor tables in
> [`backend/src/agent/mode_factors.py`](../backend/src/agent/mode_factors.py)
> and [`database/seed/gen_personas.py`](../database/seed/gen_personas.py). Those
> two must stay numerically in sync, which
> `backend/tests/test_mode_factors.py` enforces as a drift guard. If you revise
> the figures here, update both tables and re-run that test.

The factors are only used to price a **hypothetical** trip on a mode the
customer did not actually take — the cross-category comparison in
`engines/modal_shift.py`. A real per-leg `estimated_co2_emissions` from the
database is always preferred and is never overridden.

---

## Legacy test data

`test_data/` holds earlier persona CSVs (`user_profiles_v1`–`v2`,
`user_trips_v1`–`v3`, and so on) plus `forecaster_test_personas.md`. No backend
code references any of it.

The live seed set is [`database/seed/`](../database/seed/) — currently
`user_profiles_v4.csv`, `user_onboardings_v4.csv`, `user_subscriptions_v5.csv`,
`user_trips_v5.csv`, `trip_legs_v8.csv` and `user_calendars_v2.csv`, documented
in [`database/seed/PERSONAS.md`](../database/seed/PERSONAS.md).

> [!WARNING]
> Keep these apart when editing seed data. Changing a file in `test_data/` has
> no effect on the running app; `database/init/02_insert_data.sql` loads from
> `database/seed/`.
