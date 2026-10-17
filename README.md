# Plant Care Guide

A lightweight care-management tool for experienced indoor plant growers. It keeps track of the fertilizers and care products you use, reusable care plans for groups of plants, and a low-effort log of what you actually did.

It deliberately does not ask you to register every plant. People with dozens or hundreds of plants think in groups, and the products they use matter more than per-plant profiles.

> **Status:** in progress. Products are done end to end (schema, tables, API). A sourced reference list of 72 houseplant genera is in place. Next: growing media, then groups, care plans and the care log (see [Roadmap](#roadmap)).

## Tech stack

| Layer | Now | Planned |
|---|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2 | |
| Database | SQLite, SQLAlchemy 2.0, Alembic migrations | PostgreSQL |
| Tests | pytest (unit + API), manual mutation testing | mutmut in Docker, Playwright E2E |
| Frontend | — | React + Vite PWA |
| Infra | — | Docker Compose, GitHub Actions CI/CD, Prometheus + Grafana |

## Data model

**Done**
- **Product:** brand, name, type (liquid fertilizer, soluble powder, additive), NPK with its basis (oxide or elemental), and one or more label directions (dose per volume of water, how often, and a name when there are several). Label data, not personal data.
- **Taxa reference list** (`backend/data/taxa.json`): 72 genera in 31 families, each genus with its family, aliases, English and Chinese common names, and the sources that put it on the list.

**Planned**
- **Group:** plants you care for the same way. One or more genera or a family, variegation (none, variegated, or mixed), and an optional growing medium. No list of individual plants.
- **Growing medium:** a method (soil, semi-hydro, or water culture) and its components with parts, shared by any number of groups.
- **Care plan:** belongs to a group; a product, a dose, a trigger (every N days, or an event such as repotting), and a status (active, paused, archived).
- **Care log:** what was done to a group and when, with a snapshot of the product and dose actually used.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/products` | Create a product: `201`, `409` if brand and name already exist, `422` if invalid |
| `GET` | `/products` | List products, sorted by brand then name, ignoring case |
| `GET` | `/products/{id}` | Get one product, `404` if not found |
| `PUT` | `/products/{id}` | Replace a product, including all label directions |
| `DELETE` | `/products/{id}` | Delete a product and its label directions: `204` |

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
- **Groups follow care, not taxonomy.** Aroids share a growing medium, but Philodendron and Anthurium want more humidity than Monstera. So a group is whatever the user cares for the same way: one genus, several, or a whole family. The app can suggest a group by family but never assigns one.
- **Plans and history are separate.** A care log stores a snapshot of the product and dose used, so editing a plan never rewrites the past.
- **AI only drafts.** Planned AI features (reading a fertilizer label photo, drafting a plan for a new genus) produce drafts the user confirms before anything is saved. Deterministic math, such as dilution for a given volume, is done in code.
- **Data minimization.** Product label data is shared and non-personal; personal plans and logs are the only private data.

### Data
- **NPK as printed.** Values are `Decimal`, not float: with floats, a valid label like 0.2-83.9-15.9 adds up to slightly more than 100. Their total is not checked, because P and K are usually oxide equivalents (P2O5, K2O) and do not add up to a share of the product.
- **Labeling differs by country.** The US and Canada print P and K as oxides; Australia prints the elements. Each product records which, with no default, since a wrong guess would silently mislabel the data.
- **Sourced reference data.** Every genus in the taxa list cites why it is there (university extension houseplant lists, trend sources), and its family was checked against GBIF. Renamed genera keep their familiar name, with the new name as an alias (Sansevieria, alias Dracaena).
- **Reference data in git, user data in the database.** The taxa list changes only through reviewed commits and is validated at startup; a bad edit stops the app from starting.

### Engineering
- **Strict input.** All Pydantic schemas reject unknown fields, so a typo like `"dilutoin"` is an error, not silently ignored data.
- **The database repeats the rules.** Single-row rules from the schemas are also CHECK constraints, so other writers (scripts, imports) cannot break them. In a CHECK, nullable columns are guarded with `IS NOT NULL`, because a NULL result passes the check; a test caught exactly that bug.
- **Exact decimals in SQLite.** SQLite stores NUMERIC as floating point, so decimals are stored as integer hundredths (9.25 as 925) by a custom column type.
- **Uniqueness decided by the database.** A duplicate product name is caught by a unique index and returned as `409`, rather than looked up first, which would race under concurrent requests.
- **Replacing child rows safely.** SQLAlchemy inserts before it deletes, so replacing label directions that keep their names hit the unique index. Old rows are deleted and flushed first, before any other field changes.
- **Time is stored in UTC**, and naive datetimes are rejected.
- **Migrations run by hand and are reviewed.** Autogenerate misses CHECK constraints and skips expression indexes on SQLite, so a test builds one database from the migrations and one from the models and compares their constraints and indexes.

## Testing

- **Unit, database, and API tests** for every rule, including the edge cases at each boundary. Tests use a fresh in-memory database.
- **Mutation testing:** every rule was checked by deliberately breaking the code and confirming that the test for that rule fails, not just any test. This found tests that passed for the wrong reason (their data was rejected by a different rule), rules no test could tell apart from redundant code, and real bugs: a CHECK that let NULL through, a replace that collided with a unique index, and a rename conflict that returned `500` instead of `409`. Automating this with mutmut inside Docker is planned.

## Project structure

```
backend/
  app/
    main.py            # FastAPI app; loads the taxa list at startup
    routers/
      products.py      # product endpoints and API <-> table conversion
    schemas.py         # Pydantic models and validation rules
    models.py          # SQLAlchemy tables and shared column types
    database.py        # engine setup (SQLite foreign keys), session dependency
    taxa.py            # loads and validates the taxa list
  data/
    taxa.json          # reference list of genera and families, with sources
  migrations/          # Alembic migrations
  tests/
docs/
  ideas.md             # backlog of deferred ideas and why they were deferred
```

## Roadmap

1. **Core:** Products, growing media, groups, care plans, care log and history as a backend API with SQLite, then a simple frontend
2. **Tests:** API tests including "editing a plan does not change past logs"; Playwright end-to-end test for the main flow
3. **Docker:** frontend, backend and database with Docker Compose; automated mutation testing with mutmut
4. **CI/CD and deployment:** GitHub Actions runs tests on every push and deploys on success; upcoming reminders via PWA push
5. **Monitoring:** the four golden signals, Prometheus + Grafana dashboards and alerts
6. **Failure drill:** break something on purpose, verify alerts, write an RCA and runbook

After the core works: AI features to read a fertilizer label photo into a Product draft (with an evaluation set for extraction accuracy), draft a care plan for a new genus from multiple sources, and log care in natural language.

## Project history

The project started as a library of sourced, per-species care guides (light in PPFD, watering, soil, fertilizer), with each user registering their own plants. Rethinking who the app is for changed the direction: growers with dozens of plants manage care by group and by product, not plant by plant. The per-species library was removed; the strict-validation approach, the soil mix model, and the database foundation carried over. The earlier version is still in the git history.

## Development notes

Built with Claude Code as a pair programmer. Product and data-model decisions were made by me; tests are drafted with Claude, and I review every test case before it is committed. `CLAUDE.md` records the working agreement and project context.

## License

MIT
