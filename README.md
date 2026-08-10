# DB MoveOptimizer / AIIM Mobility Advisor

Dieses Repository enthält eine lokale Docker-basierte Entwicklungsumgebung für den DB MoveOptimizer / AIIM Mobility Advisor. Das Projekt besteht aus einem Frontend, einem Backend und einer PostgreSQL-Datenbank, die gemeinsam über Docker Compose gestartet werden.

---

## Projekt ausführen

### Voraussetzungen

Auf dem Rechner muss Docker inklusive Docker Compose verfügbar sein.

Prüfen:

```bash
docker --version
docker compose version
```

### 1. Repository klonen

```bash
git clone <repo-url>
cd <repo-name>
```

### 2. Environment-Datei anlegen

Falls noch keine `.env` existiert, eine neue Datei im Root-Verzeichnis anlegen:

```bash
touch .env
```

Falls eine `.env.example` vorhanden ist, kann diese kopiert werden:

```bash
cp .env.example .env
```

Typische Inhalte können z. B. sein:

```env
UNI_GPT_API_KEY=your_api_key_here
DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db
```

Wichtig: Die `.env` enthält lokale Konfiguration und Secrets. Sie sollte nicht ins Git Repository committed werden.

### 3. Services starten

Das gesamte Projekt wird über das Startscript ausgeführt:

```bash
./run.sh
```

Falls das Script noch nicht ausführbar ist:

```bash
chmod +x run.sh
./run.sh
```

Alternativ kann Docker Compose direkt verwendet werden. Dabei entfallen allerdings
die Bereitschaftsprüfung und die Wiederholung bei kurzzeitig unterbrochenen
Docker-Desktop-Antworten aus `run.sh`:

```bash
docker compose up --build
```

### 4. Anwendung öffnen

Nach erfolgreichem Start sind die Services unter folgenden URLs erreichbar:

| Service    | URL                   |
| ---------- | --------------------- |
| Frontend   | http://localhost:5173 |
| Backend    | http://localhost:8000 |
| PostgreSQL | localhost:5432        |

Das Frontend ist im Browser unter folgender Adresse erreichbar:

```text
http://localhost:5173
```

### 5. Services stoppen

Wenn das Projekt über `run.sh` gestartet wurde, können alle Services mit `Ctrl+C` gestoppt werden.

Alternativ:

```bash
docker compose down
```

Die PostgreSQL-Daten bleiben dabei im Docker Volume erhalten. Erst dieser Befehl würde das Datenbank-Volume löschen:

```bash
docker compose down -v
```

---

## Projektstruktur

Die empfohlene Struktur des Repositories ist:

```text
.
├── README.md
├── run.sh
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
│
├── frontend/                 # Vite + React UI (final)
│   ├── dockerfile
│   ├── vite.config.js        # /api proxied to backend (BACKEND_URL in Docker)
│   └── src/
│
├── backend/                  # single merged service (FastAPI + agentic LangGraph)
│   ├── dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py           # API: /api/personas, /api/analyze, /api/.../approve, /api/chat, /api/onboarding
│       ├── database.py       # Postgres access layer
│       ├── seed_data.py      # demo personas + pricing catalogue seed
│       ├── analysis_service.py # /api/analyze request lifecycle (cache/persist/shape)
│       ├── agents/           # deterministic analyst/forecaster/optimizer/communicator
│       └── graph/            # LangGraph pipeline, LLM, tools, chat & onboarding agents
│
├── database/
│   └── init/                 # canonical Postgres schema (target for Phase 3+; not yet loaded)
│
├── data/                     # raw + generated mobility data, subscription markdown/AGB
├── data_generator/           # synthetic data generation
├── scripts/                  # helper scripts (e.g. Jira backlog import)
└── DELIVERABLES/             # architecture, contract & merge report
```

---

## Services

Das Projekt läuft lokal über Docker Compose mit mehreren Services.

### Frontend

Das Frontend basiert auf Vite und wird in einem Node.js-Container ausgeführt.

Typischer Service in `docker-compose.yml`:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  container_name: aiim_frontend
  volumes:
    - ./frontend:/app
    - /app/node_modules
  depends_on:
    - backend
  environment:
    VITE_API_BASE_URL: http://localhost:8000
  ports:
    - "5173:5173"
```

Das Frontend wird lokal unter folgender URL geöffnet:

```text
http://localhost:5173
```

Wichtig für Vite im Docker-Container ist, dass der Dev Server auf `0.0.0.0` läuft. Deshalb sollte das Frontend-Dockerfile ungefähr so aussehen:

```dockerfile
FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
```

### Backend

Das Backend läuft in einem Python-Container. Es enthält die API, Business Logic, Datenbankzugriffe und ggf. die Anbindung an externe GPT-Services.

Typischer Service in `docker-compose.yml`:

```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile
  container_name: aiim_backend
  volumes:
    - ./backend:/app
    - ./data:/app/data
    - ./database:/app/database
  depends_on:
    - db
  env_file:
    - .env
  environment:
    DATABASE_URL: postgresql://postgres:postgres@db:5432/app_db
  ports:
    - "8000:8000"
```

Innerhalb des Docker-Netzwerks ist die Datenbank nicht über `localhost`, sondern über den Service-Namen erreichbar:

```text
db:5432
```

Beispiel:

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db
```

### Datenbank

Die Datenbank verwendet das offizielle PostgreSQL-Image. Deshalb benötigt der Ordner `database/` normalerweise kein eigenes Dockerfile.

Typischer Service in `docker-compose.yml`:

```yaml
db:
  image: postgres:16
  container_name: aiim_postgres
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: app_db
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

Das Volume `postgres_data` sorgt dafür, dass Datenbankdaten erhalten bleiben, auch wenn Container gestoppt oder neu gebaut werden.

---

## Docker Compose

Die zentrale Datei zum Starten aller Services ist:

```text
docker-compose.yml
```

Ein vollständiges Beispiel:

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: aiim_backend
    volumes:
      - ./backend:/app
      - ./data:/app/data
      - ./database:/app/database
    depends_on:
      - db
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/app_db
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: aiim_frontend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
    environment:
      VITE_API_BASE_URL: http://localhost:8000
    ports:
      - "5173:5173"

  db:
    image: postgres:16
    container_name: aiim_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: app_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Startscript `run.sh`

Das Script `run.sh` ist der empfohlene Wrapper um Docker Compose. Es installiert
keine lokalen Python- oder Node-Abhängigkeiten. Zusätzlich prüft es, ob der
Docker-Daemon bereit ist, baut die Anwendung mit festen lokalen Image-Tags und
wiederholt vorübergehend abgebrochene Docker-Desktop-Anfragen. Die Datei
`run.sh` im Repository ist dabei die maßgebliche Version.

Ausführbar machen:

```bash
chmod +x run.sh
```

Starten:

```bash
./run.sh
```

---

## Nützliche Docker-Befehle

Alle Services starten:

```bash
docker compose up --build
```

Services im Hintergrund starten:

```bash
docker compose up --build -d
```

Services stoppen:

```bash
docker compose down
```

Services inklusive Volumes löschen:

```bash
docker compose down -v
```

Laufende Services anzeigen:

```bash
docker compose ps
```

Logs aller Services anzeigen:

```bash
docker compose logs
```

Logs des Frontends anzeigen:

```bash
docker compose logs frontend
```

Logs des Backends anzeigen:

```bash
docker compose logs backend
```

Nur das Frontend neu bauen:

```bash
docker compose build --no-cache frontend
```

Nur das Backend neu bauen:

```bash
docker compose build --no-cache backend
```

In den Backend-Container wechseln:

```bash
docker compose exec backend bash
```

In den Frontend-Container wechseln:

```bash
docker compose exec frontend sh
```

In die PostgreSQL-Datenbank wechseln:

```bash
docker compose exec db psql -U postgres -d app_db
```

---

## Entwicklung

### Frontend-Entwicklung

Der Ordner `frontend/` ist als Volume in den Frontend-Container eingebunden:

```yaml
volumes:
  - ./frontend:/app
  - /app/node_modules
```

Dadurch werden Änderungen am lokalen Frontend-Code direkt im Container sichtbar.

Das zweite Volume verhindert, dass lokale `node_modules` die im Container installierten Dependencies überschreiben:

```yaml
- /app/node_modules
```

### Backend-Entwicklung

Der Ordner `backend/` ist als Volume in den Backend-Container eingebunden:

```yaml
volumes:
  - ./backend:/app
```

Dadurch sind Änderungen am Backend-Code direkt im Container sichtbar. Je nach Backend-Framework muss der Backend-Prozess eventuell neu gestartet werden, damit Änderungen aktiv werden.

### Datenbankdaten

PostgreSQL-Daten werden im Docker Volume gespeichert:

```yaml
volumes:
  postgres_data:
```

Dieses Volume bleibt erhalten, wenn Container gestoppt oder neu gebaut werden.

---

## Environment-Variablen

Lokale Konfiguration erfolgt über `.env`.

Beispiel:

```env
# Database (set automatically for the backend container by docker-compose)
DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db

# University GPT — enables the LLM features (memos, /api/chat, /api/onboarding).
# Without a key the backend stays fully functional using deterministic fallbacks.
UNI_GPT_API_KEY=your_api_key_here
# Optional overrides (defaults shown). Model id must match GET /api/v1/models exactly.
UNI_GPT_BASE_URL=https://chat.kiconnect.nrw/api/v1
UNI_GPT_MODEL=OpenAI GPT OSS 120b KI:Inferenz.nrw
```

> Hinweis: `.env` enthält Secrets und ist in `.gitignore` — nicht committen.

### Backend — deterministische Analyse + agentischer Advisor

Das Backend vereint die Session-/User-API (FastAPI, für das Frontend) mit einer
deterministischen Analyse-Pipeline und einem agentischen LangGraph-Advisor:

- `POST /api/analyze` — sequenzielle Pipeline (`load_context → analyze → forecast → communicate`);
  deterministische Engines bleiben die Quelle aller Kosten- und CO₂-Zahlen.
- `POST /api/chat/{session_id}` — konversationeller Advisor mit Tools und optionalem LLM.
- `POST /api/register` — erstellt zunächst nur das essentielle Nutzerkonto.
- `POST /api/onboarding/{user_id}/complete` — speichert das anschließend optionale Onboarding.
- `GET /api/profile/{user_id}` — lädt die strukturierten Onboarding- und Profildaten samt
  aktiven und inaktiven Abos zur reinen Anzeige.
- `PUT /api/profile/{user_id}` — aktualisiert Profildaten und simulierte Verbindungen zu
  Mobilitäts-Konten; Abos werden über diesen Endpunkt nicht verändert.

Chat-Folgeturns benötigen einen API-Key (sonst `503`, Frontend nutzt seinen Fallback).
`/api/analyze`, Registrierung und Profilverwaltung funktionieren auch ohne LLM.

Für Vite-Frontend-Variablen gilt: Variablen, die im Frontend-Code verfügbar sein sollen, müssen mit `VITE_` beginnen.

Beispiel:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Im Frontend-Code kann darauf so zugegriffen werden:

```js
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
```

---

## Git-Hinweise

Die `.env` sollte nicht committed werden. Stattdessen sollte eine `.env.example` mit Platzhaltern versioniert werden.

Empfohlene `.gitignore`-Einträge:

```gitignore
# Environment
.env
.env.local
.env.local.backup

# Python
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/

# Node
node_modules/
dist/

# Logs
*.log

# OS
.DS_Store
```

---

## Troubleshooting

### `unable to get image ...: unexpected end of JSON input`

Diese Meldung stammt von Docker Compose, nicht aus dem Frontend. Compose erwartet
beim Prüfen eines Images eine JSON-Antwort vom Docker-Daemon, die Verbindung wurde
aber vor dem vollständigen Empfang beendet. Das kann insbesondere während eines
Docker-Desktop-Updates oder -Neustarts auftreten.

`./run.sh` prüft deshalb zuerst den Daemon, verwendet feste lokale Image-Namen und
wiederholt Build beziehungsweise Start bei diesem vorübergehenden Verbindungsfehler
automatisch. Falls Docker Desktop dauerhaft nicht antwortet, Docker Desktop einmal
neu starten, auf „Engine running“ warten und `./run.sh` erneut ausführen. Das
PostgreSQL-Volume wird dabei nicht gelöscht.

### `services.depends_on must be a mapping`

Diese Fehlermeldung bedeutet meistens, dass `depends_on` in der `docker-compose.yml` falsch eingerückt ist.

Richtig:

```yaml
frontend:
  build:
    context: ./frontend
  depends_on:
    - backend
```

Falsch:

```yaml
services:
  frontend:
    build:
      context: ./frontend

  depends_on:
    - backend
```

Die Compose-Datei kann geprüft werden mit:

```bash
docker compose config
```

### Frontend ist im Browser nicht erreichbar

Zuerst prüfen, ob der Frontend-Service läuft:

```bash
docker compose ps
```

Die Ports sollten ungefähr so aussehen:

```text
0.0.0.0:5173->5173/tcp
```

Dann Logs prüfen:

```bash
docker compose logs frontend
```

Außerdem muss Vite im Container auf `0.0.0.0` lauschen:

```dockerfile
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
```

Browser-URL:

```text
http://localhost:5173
```

### `curl: (56) Recv failure: Connection reset by peer`

Das bedeutet häufig, dass Docker den Port zwar veröffentlicht, aber der Prozess im Container nicht korrekt darauf antwortet.

Prüfen:

```bash
docker compose logs frontend
```

Danach sicherstellen, dass das Frontend-Dockerfile Host und Port explizit setzt:

```dockerfile
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
```

Anschließend neu bauen:

```bash
docker compose down
docker compose build --no-cache frontend
docker compose up
```

### `npm error Exit handler never called!`

Dieser Fehler kann beim Docker-Build im Schritt `npm install` auftreten. Empfohlen ist, im Dockerfile `npm ci` zu verwenden und ein Debian-basiertes Node-Image zu nutzen:

```dockerfile
FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
```

Danach neu bauen:

```bash
docker compose build --no-cache frontend
```

### Backend kann die Datenbank nicht erreichen

Innerhalb von Docker darf das Backend nicht `localhost` als Datenbank-Host verwenden. Stattdessen muss der Service-Name aus `docker-compose.yml` verwendet werden:

```text
db
```

Beispiel:

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db
```

### Datenbank zurücksetzen

Achtung: Dieser Befehl löscht die lokalen Datenbankdaten im Docker Volume.

```bash
docker compose down -v
docker compose up --build
```

---

## Branch- und Integrationshinweise

Die bisher getrennten Branches für Datenbank, Backend und Frontend sollten in einem Integrationsbranch zusammengeführt werden, z. B.:

```text
integration/docker
```

Die Zielstruktur ist ein Monorepo mit getrennten Services:

```text
frontend/   → Frontend-Code
backend/    → Backend-Code und Business Logic
database/   → SQL, Migrationen und Seed-Daten
data/       → Rohdaten, generierte Daten und Testdaten
scripts/    → Hilfsskripte für Import, Export und Daten-Generierung
```

Alle Services werden gemeinsam über Docker Compose gestartet.
