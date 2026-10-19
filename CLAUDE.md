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
- Testing is the owner's strength: she leads test design. Claude drafts tests and, before committing, lists every test with its cases for her review.
- Never commit secrets. API keys and other config go in `.env` (git-ignored) and are read from environment variables. Keep a `.env.example` with placeholder values.
- Run tests from `backend/` with the virtual environment active: `python -m pytest -v`.

## Product principles

- Products and plans first; individual plant profiles are optional and out of the MVP.
- Plans attach to groups. A group is whatever set of plants the user cares for the same way, not a fixed taxonomy level: one genus, several genera, or a family. Variegated plants usually get their own group because they are fed more weakly, but the user decides.
- Logging takes one or two steps.
- Plans and history are separate: editing a plan never changes past logs.
- Product label data is shared and non-personal; personal plans and logs are the only private data (data minimization).
- AI only drafts; the user confirms before anything is saved. Deterministic math (e.g., dilution for a given volume) is done in code, never by AI.

## Data model

- **Product**: brand, name, type (liquid fertilizer, soluble powder, additive), NPK with its basis (oxide or elemental), label directions (dose per volume of water, frequency, and a `use` name when there are several), notes. Shared across users.
- **Group**: name (unique ignoring case; the UI pre-fills it from the chosen taxa and variegation, and the user may edit it), one or more taxa (genus or family, from the reference list or `other`), variegation (`none` / `variegated` / `mixed`), an optional growing medium, notes (e.g. a moss pole). No list of individual plants.
  - Why not one group per genus or family: care dimensions group differently. Aroids (Monstera, Philodendron, Anthurium) share a growing medium, but Philodendron and Anthurium want more humidity than Monstera and pothos.
- **GrowingMedium**: name (unique), method (`soil` / `semi_hydro` / `hydro`), components with parts (a fixed list of ids plus `other` with a name), notes. Defined once and shared by any number of groups, the way plans share products.
  - `method` is separate from components: the same LECA can loosen a soil mix or be the whole semi-hydro medium, and those are cared for differently (reservoir, feeding at every watering).
  - `soil` and `semi_hydro` need at least one component; `hydro` may have none (water only). Sphagnum moss alone (e.g. for orchids) is `soil` with one component.
  - Each component appears at most once per medium; `other` names are compared ignoring case, with spaces and hyphens treated as underscores, and may not repeat a listed id (use the listed id instead).
- **Taxa reference list** (`backend/data/taxa.json`, reference data versioned in git, not in the database; loaded and validated once at startup): genera and families with each genus's family, aliases, and common names (en / zh). The user picks a genus by its scientific or common name and the family follows, so nobody needs to know families. The app may suggest an existing group with the same family, but never assigns a group by itself (same family does not mean same care).
  - Genera whose names changed recently keep the familiar name as the entry and list the new name as an alias (Calathea / Goeppertia, Sansevieria / Dracaena, Saintpaulia / Streptocarpus, Schefflera arboricola / Heptapleurum).
  - Family per genus is checked against a taxonomic database (GBIF) and candidate genera come from extension houseplant lists; every entry needs a source.
- **CarePlan**: belongs to a group; product, dose (amount per volume of water), trigger, status (active, paused, archived).
  - Trigger is either `interval` (every N days; shows in Upcoming) or an event such as `repot` (shown when that event is logged).
  - A group can have several plans, e.g., a routine fertilizer plus a repotting fertilizer.
- **CareLog**: group, action (fertilize, repot, water, ...), timestamp, notes, optional plan reference, and a snapshot of the product and actual dose used. Logs must stay correct after the plan is edited.

## Conventions

- All Pydantic schemas reject unknown fields (`StrictModel`, `extra="forbid"`), so typos are errors instead of silently ignored data.
- Datetimes are stored in UTC (`UtcDateTime` rejects naive datetimes).
- Decimals are stored exactly as integer hundredths (`HundredthsDecimal`), since SQLite stores NUMERIC as floating point.
- The database repeats single-row rules from the Pydantic schemas as CHECK constraints. In a CHECK, guard nullable columns with `IS NOT NULL`: a NULL result passes the check.
- SQLite needs `PRAGMA foreign_keys = ON` on every connection for foreign keys and `ON DELETE CASCADE` to work; `create_db_engine` does this.
- Migrations run by hand (`alembic upgrade head`), never at app startup. Generated migrations must be reviewed; autogenerate does not detect CHECK constraint changes and skips expression indexes (e.g. `lower(brand)`) on SQLite. `test_migrations_match_models_checks_and_indexes` compares both against the models.
- Deletes cascade from parent to child only (a product takes its label directions with it; deleting a direction keeps the product).
- When replacing child rows that have unique constraints, delete the old rows with one direct `DELETE ... WHERE parent_id = ?` (a flush would insert the new rows before deleting the old ones), and do the whole update inside `session.no_autoflush`, so no field change is sent before commit, where the caller turns conflicts into 409. Test that other parents' rows are untouched.
- Every rule is checked by a targeted mutation (break the code, confirm the test for that rule fails, restore). Mutants that change no behavior are noted as equivalent rather than "fixed" with tests.
- Taxa ids are never removed or renamed once released: groups refer to them and the database cannot enforce it (no foreign key). A renamed genus keeps its entry and gets the new name as an alias. Keep families and genera sorted by name.
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
3. **Docker**: containerize frontend, backend, and database; start everything with docker-compose. Then run mutation testing (mutmut) inside the backend container; see `docs/ideas.md`.
4. **CI/CD and deployment**: GitHub Actions runs tests on every push and deploys on success to a public URL. Adopt a feature-branch + pull request workflow here. Then add Upcoming reminders via PWA push (needs HTTPS).
5. **Monitoring**: four golden signals from the backend; Prometheus + Grafana dashboards; one or two alerts.
6. **Failure drill and docs**: intentionally break something (e.g., stop the database), verify alerts and dashboards, write an RCA and a runbook; finish README and architecture diagram.

AI features, in order, after the core works:

1. Read a fertilizer label photo and draft a Product (validated by the Pydantic schema, confirmed by the user), with an evaluation set measuring extraction accuracy.
2. Draft a care plan and growing medium for a new genus group from multiple web sources, with sources, consensus, and disputed points.
3. Natural-language quick logging (e.g., "fertilized variegated Monstera, 1 ml").

## Current status

- Dev environment ready: Python 3.13, Git, VS Code, Claude Code. Repo: `indoor-plant-care`.
- Backend foundation: FastAPI with `/health`; SQLAlchemy and Alembic; `get_session` request dependency; pytest with shared fixtures (`product` data, `session` on an in-memory database, `client` with `get_session` overridden).
- The previous direction (per-species care guides, per-plant tables) was removed and the migration chain reset, since nothing was ever deployed.
- **Product: done.**
  - Schema `ProductCreate` / `ProductRead`: NPK as `Decimal` (0-100, at most 2 decimal places, JSON numbers) with a required `basis`; the total is not checked, since P and K may be oxide equivalents. Frequency is `interval` (days) or `every_watering`. Several label directions each need a distinct `use` (case-insensitive).
  - Tables `products` (NPK in four columns, unique brand + name ignoring case) and `product_label_directions` (ordered by `position`, deleted with their product), with CHECK constraints mirroring the schema.
  - API: `POST /products` (201, 409 on duplicate brand + name), `GET /products` (sorted by brand, then name, ignoring case), `GET /products/{id}`, `PUT /products/{id}` (replaces fields and all label directions), `DELETE /products/{id}` (204). Conversion between the nested API shape and the flat tables is in `app/routers/products.py`.
  - NPK soft warnings are deferred until the core works; thresholds and sources are in `docs/ideas.md`.
- Medium components (`MediumComponent`) are a fixed list of ids (matched exactly, like an enum, including `pon` and `leca` for semi-hydro) plus `other` with a user-given name; schema done, to be used by GrowingMedium.
- Group design agreed (see Data model).
- Taxa list done: 72 genera in 31 families, each with a source; families checked with GBIF. Ctenanthe was left out until a source is found.
- Next: GrowingMedium, then Groups (schema, tables, API, `GET /taxa` for search), then CarePlans.
