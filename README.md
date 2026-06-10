# Docker Python + Postgres Setup

This project runs a Python app and a Postgres database using Docker.

## Project Structure

```text
your-project/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── src/
    └── main.py
```

## Requirements

To run this project, docker must be installed.

## Start the Environment

```bash
docker compose up --build
```

This will:

1. build the Python Docker image
2. start the Postgres container
3. start the Python app container
4. run `src/main.py`

The app container stops automatically when `main.py` finishes.

## Run the Python App Again

Recommended during development:

```bash
docker compose up -d db
docker compose run --rm app python src/main.py
```

This keeps Postgres running in the background and runs `main.py` whenever needed.

## Postgres Data

Postgres data is stored in a Docker volume:

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
```

This means the database data survives when containers are stopped or deleted.

```bash
docker compose down
```

Stops and removes containers, but keeps the database data.

```bash
docker compose down -v
```

Stops containers and deletes the database volume. This removes all database data.

Summary:

```text
Container stopped      → data stays
Container deleted      → data stays
Volume deleted         → data is gone
```

## Adding Python Packages

Add new packages to `requirements.txt`:

```txt
psycopg2-binary
pandas
sqlalchemy
```

Then rebuild the app image:

```bash
docker compose up --build
```

Changing Python files in `src/` does not require rebuilding, because the folder is mounted into the container.

Changing `requirements.txt` does require rebuilding.

## Useful Commands

Start everything:

```bash
docker compose up --build
```

Start only Postgres in the background:

```bash
docker compose up -d db
```

Run the Python script:

```bash
docker compose run --rm app python src/main.py
```

Stop containers:

```bash
docker compose down
```

Stop containers and delete database data:

```bash
docker compose down -v
```

## Connect with DBeaver

Make sure the Postgres container is running:

```bash
docker compose ps
```

if you do not see something like: "db postgres:16 ... 0.0.0.0:5432->5432/tcp", run:

```bash
docker compose up -d db
```

In DBeaver, create a new PostgreSQL connection with:
Host: localhost
Port: 5432
Database: app_db
Username: postgres
Password: postgres

Important distinction:
From another Docker container: host = db
From your Mac / DBeaver: host = localhost
