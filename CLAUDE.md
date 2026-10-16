# Plant Care Guide

A lightweight care-management tool for experienced indoor plant growers. It organizes fertilizer and care products, reusable care plans grouped by plant genus, and a low-effort log of what was actually done.

It deliberately does not ask users to register every plant. People with dozens or hundreds of plants think in groups (usually by genus, with variegated plants handled separately), and the products they use matter more than per-plant profiles.

This is a portfolio project. The owner will put it on her resume and explain it in interviews, so code quality, tests, and her understanding of every design decision matter more than speed.

## Working agreement

- Reply in Chinese. Keep code, identifiers, commit messages, and docs in English.
- The owner has backend experience in Java and is new to Python and React. Explain new concepts briefly, using Java comparisons where helpful.
- Before any non-trivial change, propose the approach and wait for approval.
- After each change, explain what was done and why, so she can defend it in an interview.
- Keep changes small and focused; one logical change per commit.
- Testing is the owner's strength: suggest test cases, but let her lead test design.
- Never commit secrets. API keys and other config go in `.env` (git-ignored) and are read from environment variables. Keep a `.env.example` with placeholder values.
- Run tests from `backend/` with the virtual environment active: `python -m pytest -v`.

## Product principles

- Products and plans first; individual plant profiles are optional and out of the MVP.
- Plans attach to groups (usually a genus; variegated plants get their own group).
- Logging takes one or two steps.
- Plans and history are separate: editing a plan never changes past logs.
- Product label data is shared and non-personal; personal plans and logs are the only private data (data minimization).
- AI only drafts; the user confirms before anything is saved. Deterministic math (e.g., dilution for a given volume) is done in code, never by AI.

## Data model

- **Product**: brand, name, type (e.g., liquid fertilizer, additive), NPK ratio, label dilution, label frequency, notes. Shared across users.
- **Group**: name, genus, variegated flag, soil mix (components with parts). No list of individual plants.
- **CarePlan**: belongs to a group; product, dose (amount per volume of water), trigger, status (active, paused, archived).
  - Trigger is either `interval` (every N days; shows in Upcoming) or an event such as `repot` (shown when that event is logged).
  - A group can have several plans, e.g., a routine fertilizer plus a repotting fertilizer.
- **CareLog**: group, action (fertilize, repot, water, ...), timestamp, notes, optional plan reference, and a snapshot of the product and actual dose used. Logs must stay correct after the plan is edited.

## Conventions

- All Pydantic schemas reject unknown fields (`StrictModel`, `extra="forbid"`), so typos are errors instead of silently ignored data.
- Datetimes are stored in UTC (`UtcDateTime` rejects naive datetimes).
- SQLite needs `PRAGMA foreign_keys = ON` on every connection for foreign keys and `ON DELETE CASCADE` to work; `create_db_engine` does this.
- Migrations run by hand (`alembic upgrade head`), never at app startup. Generated migrations must be reviewed; autogenerate does not detect CHECK constraint changes.
- Deferred ideas: `docs/ideas.md`.

## Tech stack

- Backend: Python + FastAPI, in `backend/`, virtual environment at `backend/.venv`, dependencies in `backend/requirements.txt` and `backend/requirements-dev.txt`
- Validation: Pydantic schemas in `backend/app/schemas.py`
- Database: SQLite to start, PostgreSQL later; SQLAlchemy 2.0 ORM (models in `backend/app/models.py`), Alembic migrations in `backend/migrations/`
- Frontend: React + Vite, PWA (later, in `frontend/`)
- Tests: pytest (unit and API), Playwright (end-to-end)
- Infra (later): Docker + docker-compose, GitHub Actions CI/CD, cloud deployment, Prometheus + Grafana
- Single user, no accounts, for now
- Dev machine: Windows, PowerShell, VS Code

## Roadmap

Each step ends in a working, demoable state.

1. **Core (P0)**: Products, Groups, CarePlans, CareLogs and History as backend API with SQLite, then a simple frontend. Build the backend first.
2. **Tests**: pytest unit and API tests (including "editing a plan does not change past logs"); Playwright E2E for the main flow.
3. **Docker**: containerize frontend, backend, and database; start everything with docker-compose.
4. **CI/CD and deployment**: GitHub Actions runs tests on every push and deploys on success to a public URL. Adopt a feature-branch + pull request workflow here. Then add Upcoming reminders via PWA push (needs HTTPS).
5. **Monitoring**: four golden signals from the backend; Prometheus + Grafana dashboards; one or two alerts.
6. **Failure drill and docs**: intentionally break something (e.g., stop the database), verify alerts and dashboards, write an RCA and a runbook; finish README and architecture diagram.

AI features, in order, after the core works:

1. Read a fertilizer label photo and draft a Product (validated by the Pydantic schema, confirmed by the user), with an evaluation set measuring extraction accuracy.
2. Draft a care plan and soil mix for a new genus group from multiple web sources, with sources, consensus, and disputed points.
3. Natural-language quick logging (e.g., "fertilized variegated Monstera, 1 ml").

## Current status

- Dev environment ready: Python 3.13, Git, VS Code, Claude Code. Repo: `indoor-plant-care`.
- FastAPI backend with a `/health` endpoint.
- pytest set up (`pytest.ini`, shared fixtures in `conftest.py`, parametrized tests).
- SQLAlchemy and Alembic set up, with tests for models and migrations.
- Code from the previous direction (per-species care guides) is being removed:
  - Done: the `PlantCareGuide` schema (PPFD-based light, window exposures, watering), the JSON plant library in `backend/data/`, and the `/plants` endpoints.
  - Still to remove: the `user_settings`, `my_plants`, and `watering_events` tables. Nothing was ever deployed, so the migration chain is reset instead of adding a migration that drops them.
  - Kept for reuse: `StrictModel`, `NonEmptyStr`, `Slug`, `Days`, `SoilComponent` (for group soil mixes), `create_db_engine`, `UtcDateTime`.
- Next: Product schema and validation tests, then Product API endpoints.
