# DB MoveOptimizer / AIIM Mobility Advisor

An AI mobility-subscription advisor. It reads a customer's real travel history
out of PostgreSQL, works out what their journeys actually cost, and recommends
which mobility subscriptions to keep, drop or take up — then explains the
reasoning in a chat advisor.

The repository is a monorepo of three services that run together under Docker
Compose: a React frontend, a FastAPI backend, and a PostgreSQL database.

**This file covers getting the stack running.** For anything deeper, follow the
chain:

| Document | Covers |
| --- | --- |
| **README.md** (this file) | running the stack, repo layout, Docker troubleshooting |
| [`frontend/README.md`](frontend/README.md) | UI architecture, view state, the chat widget, dev server |
| [`backend/README.md`](backend/README.md) | architecture, data model, the analysis pipeline, HTTP API, testing |
| [`data/README.md`](data/README.md) | the tariff knowledge base and CO₂ reference figures |
| [`backend/eval/README.md`](backend/eval/README.md) | Langfuse tracing, LLM judges, the baseline-vs-agent experiment and its measured results |
| [`report/README.md`](report/README.md) | building the managerial report PDFs from those results |

One further reference sits outside that chain:
[`database/seed/PERSONAS.md`](database/seed/PERSONAS.md) documents the ten seed
personas and the decision path each one exercises.

---

## Quick start

### Prerequisites

Docker with Docker Compose:

```bash
docker --version
docker compose version
```

Nothing else is needed locally — no Python, no Node. Everything builds inside
the containers.

### 1. Clone and configure

```bash
git clone <repo-url>
cd AIIM_DB_mobility_advisior
cp .env.example .env
```

> [!IMPORTANT]
> `.env` holds local configuration and secrets and is git-ignored — never commit
> it. The app runs without any API key, using deterministic fallbacks; add
> `UNI_GPT_API_KEY` to enable the LLM features. See
> [Environment variables](#environment-variables) below.

### 2. Start

```bash
./run.sh
```

If the script is not executable yet:

```bash
chmod +x run.sh
./run.sh
```

`run.sh` is the recommended wrapper around Docker Compose. Beyond
`docker compose up --build`, it waits for the Docker daemon to be ready, builds
with fixed local image tags, and retries requests that Docker Desktop drops
mid-flight. Plain `docker compose up --build` works too, but without those
safeguards.

### 3. Open

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| PostgreSQL | localhost:5432 |

Sign in with any seeded user's username or email and the shared demo password
`mobility` — for example `jank_frankfurt` / `mobility`. The seeded personas are
described in [`database/seed/PERSONAS.md`](database/seed/PERSONAS.md); the login
mechanism is documented in [`backend/README.md`](backend/README.md).

### 4. Stop

`Ctrl+C` if started via `run.sh`, otherwise:

```bash
docker compose down       # keeps the database volume
docker compose down -v    # also deletes the database volume
```

---

## Repository layout

```text
.
├── run.sh                  # start script (wraps docker compose)
├── docker-compose.yml      # the three services: frontend, backend, db
├── .env / .env.example     # local configuration and secrets
│
├── frontend/               # Vite + React UI; /api proxied to the backend  → README
├── backend/                # FastAPI service, analysis pipeline, chat advisor
│   ├── src/                #   application code
│   ├── tests/              #   pytest suite (no DB, no LLM)
│   ├── scripts/            #   one-off seed and experiment scripts
│   └── eval/               #   Langfuse judges and calibration harness
│
├── database/
│   ├── init/               # schema + seed SQL, auto-loaded by Postgres on first boot
│   └── seed/               # persona CSVs, generator, PERSONAS.md
│
├── data/                   # tariff knowledge base, CO₂ factors            → README
└── report/                 # Quarto sources for the managerial report PDFs   → README
```

---

## Environment variables

Configuration lives in `.env` at the repo root; Docker Compose passes it into
the backend via `env_file`.

```env
# Database — set automatically for the backend container by docker-compose
DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db

# University GPT — enables the LLM features (memos, chat advisor).
# Without a key the backend stays functional using deterministic fallbacks.
UNI_GPT_API_KEY=your_api_key_here
UNI_GPT_BASE_URL=https://chat.kiconnect.nrw/api/v1
UNI_GPT_MODEL=OpenAI GPT OSS 120b KI:Inferenz.nrw

# Optional — Langfuse observability; every hook is a no-op without these
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

The full variable table, including defaults and which module reads each one, is
in [`backend/README.md`](backend/README.md). Langfuse setup is in
[`backend/eval/README.md`](backend/eval/README.md).

Two things worth knowing:

- **Inside the Docker network the database host is `db`, not `localhost`.**
  `localhost` in a container refers to the container itself.
- **Frontend variables must be prefixed `VITE_`** to be visible to browser code,
  where they are read as `import.meta.env.VITE_API_BASE_URL`.

---

## Working on the code

`frontend/` and `backend/` are bind-mounted into their containers, so local
edits are visible immediately. The frontend hot-reloads; the backend process may
need a restart for changes to take effect.

The frontend container also mounts an anonymous volume at `/app/node_modules` so
that local `node_modules` never shadow the ones installed in the image.

PostgreSQL data lives in the named volume `postgres_data` and survives container
restarts and rebuilds. It is only removed by `docker compose down -v`.

> [!WARNING]
> **Database schema changes only apply to a fresh volume.** The SQL in
> `database/init/` runs the first time the volume is created and never again, so
> re-applying a schema change means recreating it — which **deletes all local
> database data**:
>
> ```bash
> docker compose down -v && docker compose up --build
> ```

### Useful commands

```bash
docker compose up --build -d          # start detached
docker compose ps                     # what is running
docker compose logs backend           # logs for one service
docker compose build --no-cache backend   # force a rebuild
docker compose exec backend bash      # shell into the backend
docker compose exec db psql -U postgres -d app_db   # psql prompt
```

Running the backend test suite (dev dependencies are baked into the image):

```bash
docker compose exec backend pytest -q
```

---

## Troubleshooting

### `unable to get image ...: unexpected end of JSON input`

This comes from Docker Compose, not the app. Compose expected a JSON response
from the Docker daemon and the connection closed early — typically during a
Docker Desktop update or restart.

`./run.sh` already checks the daemon first and retries this specific transient
failure. If Docker Desktop stays unresponsive, restart it, wait for "Engine
running", and run `./run.sh` again. The PostgreSQL volume is not affected.

### `services.depends_on must be a mapping`

`depends_on` is indented at the wrong level in `docker-compose.yml` — it belongs
inside a service, not beside it. Validate with:

```bash
docker compose config
```

### The frontend is not reachable in the browser

Check the service is up and the port is published as `0.0.0.0:5173->5173/tcp`:

```bash
docker compose ps
docker compose logs frontend
```

A `curl: (56) Recv failure: Connection reset by peer` points at the same cause:
the port is published but nothing inside the container is answering. Vite must
bind `0.0.0.0` rather than `localhost`, which the frontend Dockerfile sets:

```dockerfile
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
```

### `npm error Exit handler never called!`

Occurs during the frontend image build. The Dockerfile uses `npm ci` on a
Debian-based Node image (`node:22-bookworm-slim`) to avoid it. If it appears
anyway, rebuild without cache:

```bash
docker compose build --no-cache frontend
```

### The backend cannot reach the database

Check that `DATABASE_URL` uses the Compose service name `db` as the host, not
`localhost`.

### Resetting the database

Deletes all local database data and re-runs `database/init/`:

```bash
docker compose down -v && docker compose up --build
```
