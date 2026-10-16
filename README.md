# Plant Care Guide

A lightweight care-management tool for experienced indoor plant growers. It keeps track of the fertilizers and care products you use, reusable care plans grouped by plant genus, and a low-effort log of what you actually did.

It deliberately does not ask you to register every plant. People with dozens or hundreds of plants think in groups (usually by genus, with variegated plants handled separately), and the products they use matter more than per-plant profiles.

> **Status:** in progress. The backend foundation is in place (FastAPI, SQLAlchemy, Alembic, pytest). Next: Products, then Groups, Care plans and the Care log (see [Roadmap](#roadmap)).

## Tech stack

| Layer | Now | Planned |
|---|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2 | |
| Database | SQLite, SQLAlchemy 2.0, Alembic migrations | PostgreSQL |
| Tests | pytest (unit + API), manual mutation testing | mutmut in Docker, Playwright E2E |
| Frontend | — | React + Vite PWA |
| Infra | — | Docker Compose, GitHub Actions CI/CD, Prometheus + Grafana |

## Data model (planned)

- **Product:** brand, name, type (e.g. liquid fertilizer), NPK ratio, label dilution and frequency. Label data, not personal data.
- **Group:** name, genus, variegated flag, and a soil mix (components with parts). No list of individual plants.
- **Care plan:** belongs to a group; a product, a dose (amount per volume of water), a trigger (every N days, or an event such as repotting), and a status (active, paused, archived). A group can have several plans.
- **Care log:** what was done to a group and when, with an optional link to the plan and a snapshot of the product and dose actually used.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |

Interactive docs are served at `/docs` once the server is running.

## Run locally

```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
alembic upgrade head        # create or update the SQLite database
fastapi dev app/main.py     # http://127.0.0.1:8000/docs
python -m pytest -v         # run the test suite
```

## Design decisions

### Product
- **Plans and history are separate.** A care log stores a snapshot of the product and dose used, so editing or archiving a plan never rewrites what was done in the past.
- **AI only drafts.** Planned AI features (reading a fertilizer label photo, drafting a plan for a new genus) produce drafts that the user confirms before anything is saved. Deterministic math, such as the dilution for a given volume of water, is done in code, never by AI.
- **Data minimization.** Product label data is shared and non-personal; personal plans and logs are the only private data.

### Engineering
- **Strict input.** All Pydantic schemas reject unknown fields (`extra="forbid"`), so a typo like `"dilutoin"` is an error, not silently ignored data.
- **Time is stored in UTC.** A custom column type converts every datetime to UTC on write and rejects naive datetimes, because nothing could tell which time zone they meant.
- **Foreign keys actually enforced.** SQLite ignores foreign keys and `ON DELETE CASCADE` unless `PRAGMA foreign_keys = ON` is set, and it must be set on every new connection. The engine factory does this, and a test checks it.
- **Migrations run by hand.** `alembic upgrade head` is a deliberate step, never run at app startup, and every generated migration is reviewed (autogenerate misses some changes, such as CHECK constraints). A test checks that the migrations produce exactly the tables the models define.

## Testing

- **Unit tests** for schema and database rules, including the edge cases at each boundary. The UTC column type is tested on a test-only table, so it does not depend on any app table.
- **Migration tests:** upgrade to head and compare against the models; downgrade to base and check no tables are left.
- **Mutation testing:** each test was checked by deliberately breaking the code it covers and confirming the test fails. This exposed a test that passed for the wrong reason: its data was being rejected by a different rule, so the rule it was meant to test was never exercised. Automating this with mutmut inside Docker is planned.

## Project structure

```
backend/
  app/
    main.py            # FastAPI app and endpoints
    schemas.py         # Pydantic models and validation rules
    models.py          # SQLAlchemy tables and shared column types
    database.py        # engine setup (SQLite foreign keys)
  migrations/          # Alembic migrations
  tests/
docs/
  ideas.md             # backlog of deferred ideas and why they were deferred
```

## Roadmap

1. **Core:** Products, Groups, Care plans, Care log and history as a backend API with SQLite, then a simple frontend
2. **Tests:** API tests including "editing a plan does not change past logs"; Playwright end-to-end test for the main flow
3. **Docker:** frontend, backend and database with Docker Compose; automated mutation testing with mutmut
4. **CI/CD and deployment:** GitHub Actions runs tests on every push and deploys on success; Upcoming reminders via PWA push
5. **Monitoring:** the four golden signals, Prometheus + Grafana dashboards and alerts
6. **Failure drill:** break something on purpose, verify alerts, write an RCA and runbook

After the core works: AI features to read a fertilizer label photo into a Product draft (with an evaluation set for extraction accuracy), draft a care plan for a new genus from multiple sources, and log care in natural language.

## Project history

The project started as a library of sourced, per-species care guides (light in PPFD, watering, soil, fertilizer), with each user registering their own plants. Rethinking who the app is for changed the direction: growers with dozens of plants manage care by group and by product, not plant by plant. The per-species library was removed; the strict-validation approach, the soil mix model, and the database foundation carried over. The earlier version is still in the git history.

## Development notes

Built with Claude Code as a pair programmer. Schema design, data modeling choices and test design were decided and reviewed by me; `CLAUDE.md` records the working agreement and project context.

## License

MIT
