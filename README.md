# Indoor Plant Care

A plant care app that gives precise, **sourced** care guides for each plant (light, watering, soil, fertilizer) and will remind you when to water.

Most plant apps give generic advice ("bright indirect light, water when dry"). This project goes down to the cultivar level, because a variegated Monstera needs different care than a plain green one, and every recommendation links to the sources it came from.

> **Status:** in progress. The backend API and plant library schema are done; user features, the frontend and infrastructure are next (see [Roadmap](#roadmap)).

## Tech stack

| Layer | Now | Planned |
|---|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2 | SQLite → PostgreSQL |
| Tests | pytest (unit + API), manual mutation testing | mutmut in Docker, Playwright E2E |
| Frontend | — | React + Vite PWA |
| Infra | — | Docker Compose, GitHub Actions CI/CD, Prometheus + Grafana |

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/plants` | List all plant care guides |
| `GET` | `/plants/{plant_id}` | Get one guide (e.g. `monstera-deliciosa`); `404` if not found |

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
fastapi dev app/main.py     # http://127.0.0.1:8000/docs
pytest                      # run the test suite
```

## Design decisions

### Fail fast on bad data
The plant library is plain JSON files, validated against a strict Pydantic schema **when the service starts**. If any file is invalid, the app refuses to start, so a bad entry is caught at deploy time instead of on a user's request.

- All models reject unknown fields (`extra="forbid"`), so a typo like `"watring"` is an error, not silently ignored data.
- Cross-field rules are enforced, e.g. the ideal light range must sit inside the tolerable range, and distance ranges must have `min <= max`.
- Every care section cites sources by id, and every cited id must exist in the plant's `sources` list.
- Duplicate plant ids across files are rejected.

### Data that works anywhere in the world
- **Light in PPFD (µmol/m²/s), not lux.** PPFD measures the light plants actually use for photosynthesis; lux is weighted for the human eye. Capped at 2,000 (midsummer noon sun).
- **Window exposure levels instead of compass directions.** "South-facing" means opposite things in the two hemispheres, so placement uses levels users can observe (strong / gentle / no direct sun).
- **Seasons instead of months.** Watering and feeding schedules use `spring_summer` / `fall_winter`, so the same data holds in both hemispheres.

### Shared reference data
Window exposure levels and watering check methods (e.g. checking pot weight) are defined once in `backend/data/` and referenced by id, so every plant uses the same definitions.

### Sourced, not generated at runtime
The library is built ahead of time from published sources (university extension services, horticultural societies, and commercial and gardening sites), with sources recorded per section. The app reads the JSON at runtime and makes no AI calls, so answers are fast, reproducible and checkable. Disagreements between sources are recorded instead of hidden.

## Testing

- **Unit tests** for every schema rule, including the edge cases at each boundary.
- **API tests** for all endpoints, with the library dependency overridden so tests use fixture data.
- **Mutation testing:** each test was checked by deliberately breaking the code it covers and confirming the test fails. This exposed a test that passed for the wrong reason: its data was being rejected by a different rule, so the rule it was meant to test was never exercised. Automating this with mutmut inside Docker is planned.

## Project structure

```
backend/
  app/
    main.py            # FastAPI app, endpoints, startup validation
    schemas.py         # Pydantic models and validation rules
    plant_library.py   # loads and validates the plant JSON files
  data/
    plants/            # one care guide per plant (file name = id)
    window_exposures.json
    watering_checks.json
  tests/
docs/
  ideas.md             # backlog of deferred ideas and why they were deferred
```

## Roadmap

1. **Core features:** add my plants, log watering, compute which plants need water today (SQLite); simple React frontend
2. **Tests:** Playwright end-to-end test for "add a plant → log watering → reminder list updates"
3. **Docker:** containerize frontend, backend and database with Docker Compose; automated mutation testing with mutmut
4. **CI/CD and deployment:** GitHub Actions runs tests on every push and deploys on success; PWA push reminders
5. **Monitoring:** the four golden signals, Prometheus + Grafana dashboards and alerts
6. **Failure drill:** break something on purpose, verify alerts, write an RCA and runbook

## Development notes

Built with Claude Code as a pair programmer. Schema design, data modeling choices and test design were decided and reviewed by me; `CLAUDE.md` records the working agreement and project context.

## License

MIT
