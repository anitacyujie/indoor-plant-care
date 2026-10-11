# Plant Care App

A plant care PWA that gives precise, sourced care guides for each plant (soil mix, fertilizer, light, watering) and reminds the user when to water and fertilize.

This is a portfolio project. The owner will put it on her resume and explain it in interviews, so code quality, tests, and her understanding of every design decision matter more than speed.

## Working agreement

- Reply in Chinese. Keep code, identifiers, commit messages, and docs in English.
- The owner has backend experience in Java and is new to Python and React. Explain new concepts briefly, using Java comparisons where helpful.
- Before any non-trivial change, propose the approach and wait for approval.
- After each change, explain what was done and why, so she can defend it in an interview.
- Keep changes small and focused; one logical change per commit.
- Testing is the owner's strength: suggest test cases, but let her lead test design.
- Never commit secrets. API keys and other config go in `.env` (git-ignored) and are read from environment variables. Keep a `.env.example` with placeholder values.

## Tech stack

- Backend: Python + FastAPI, in `backend/`, virtual environment at `backend/.venv`, dependencies in `backend/requirements.txt`
- Database: SQLite to start, PostgreSQL later
- Frontend: React + Vite, PWA (later, in `frontend/`)
- Tests: pytest (unit and API), Playwright (end-to-end)
- Infra (later): Docker + docker-compose, GitHub Actions CI/CD, cloud deployment, Prometheus + Grafana
- Dev machine: Windows, PowerShell, VS Code

## Roadmap

Each step ends in a working, demoable state.

1. **Core features**: plant library (JSON), backend API (list plants, add my plant, log watering, compute who needs water today), simple frontend, SQLite storage. Build the backend first, then the frontend.
2. **Tests**: pytest unit and API tests; Playwright E2E for "add a plant → log watering → reminder list updates".
3. **Docker**: containerize frontend, backend, and database; start everything with docker-compose.
4. **CI/CD and deployment**: GitHub Actions runs tests on every push and deploys on success to a public URL. Then add PWA push reminders (need HTTPS).
5. **Monitoring**: expose the four golden signals from the backend; Prometheus + Grafana dashboards; one or two alerts.
6. **Failure drill and docs**: intentionally break something (e.g., stop the database), verify alerts and dashboards, write an RCA and a runbook; finish README and architecture diagram.

## Plant library

The library is generated once by a script that searches the web, merges what it finds, and records sources. The app reads the generated JSON at runtime and makes no AI calls. Live generation for plants missing from the library may come later as an extension.

Each entry should be specific down to the cultivar (e.g., variegated varieties need different fertilizing than plain green ones).

- Schema: `backend/app/schemas.py`. Reference entry: `backend/data/plants/monstera-deliciosa.json` (one file per plant, file name = `id`).
- Shared reference data (stored once, plants refer to it by id): `backend/data/window_exposures.json`, `backend/data/watering_checks.json`.
- Key design decisions:
  - Light in PPFD (µmol/m²/s), not lux: `ideal_ppfd` must fall within `tolerable_ppfd`, capped at 2,000 (midsummer noon sun).
  - Window placement uses exposure levels (strong / gentle / none) users can observe, not compass directions, so it works in both hemispheres.
  - Seasons (`spring_summer` / `fall_winter`) instead of months, for the same reason.
  - Every care section cites sources by `source_ids`; cited ids must exist in `sources`.
  - Soil has one mix per watering style (top / bottom).
  - All models reject unknown fields (`StrictModel`, `extra="forbid"`).
- Data rules: read every source in full before citing it; never cite a claim seen only in a search summary. Store facts and our own wording, never copied text. Record disagreements in `disputed`.
- Deferred ideas: `docs/ideas.md`.

## Current status

- Dev environment ready: Python 3.13, Git, VS Code, Claude Code.
- Repo cloned with README, Python .gitignore, MIT license.
- FastAPI backend running with /health endpoint, first commit pushed.
- Plant library schema done, with tests; every test verified by mutation testing (break the code, confirm the test fails).
- First plant entry: Monstera deliciosa (plain green).
- API: `GET /plants`, `GET /plants/{plant_id}`; the library loads and validates at startup.
- Next: user data in SQLite — add my plant, log watering, compute who needs water today. Then a simple frontend.
