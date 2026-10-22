# Product

A **product** is a fertilizer or care product as its label describes it: who makes it, what it contains, and how the label says to use it. Products are shared, non-personal reference data; how a particular user feeds a particular group belongs to a care plan (not built yet).

This document covers the whole Product feature: the API shape, the validation rules, the tables, the endpoints, and the AI draft from a label photo.

```
                    ┌──────────────────────────────┐
  label photo ────► │ POST /products/draft          │  AI 1: Claude reads the label,
                    │ (nothing saved)               │  the server checks the result
                    └──────────────┬───────────────┘
                                   │ draft + problems
                                   ▼
                          user checks and fixes
                                   │
                                   ▼
  form / JSON  ───► POST /products ───► ProductCreate ───► products
                    PUT  /products/{id}  (validation)       product_label_directions
                    GET  /products[/{id}] ◄── ProductRead ◄──┘
                    DELETE /products/{id}
```

## 1. Shape (API)

Defined in `backend/app/schemas.py`. `ProductCreate` is what the API accepts; `ProductRead` adds `id` and `created_at`.

```json
{
  "brand": "Dyna-Gro",
  "name": "Foliage-Pro",
  "type": "liquid_fertilizer",
  "npk": {"n": 9, "p": 3, "k": 6, "basis": "oxide"},
  "label_directions": [
    {"amount": 0.25, "amount_unit": "tsp", "water_volume": 1, "water_unit": "gal",
     "frequency": {"kind": "every_watering"}, "use": "maintenance"},
    {"amount": 1, "amount_unit": "tsp", "water_volume": 1, "water_unit": "gal",
     "frequency": {"kind": "interval", "days": 30}, "use": "monthly"}
  ],
  "notes": "Urea-free."
}
```

| Field | Type | Rules |
|---|---|---|
| `brand`, `name` | text | Required; surrounding spaces are stripped; may not be blank |
| `type` | `liquid_fertilizer` / `soluble_powder` / `additive` | Required |
| `npk` | object or `null` | Required unless `type` is `additive` |
| `npk.n`, `npk.p`, `npk.k` | decimal | 0-100, at most 2 decimal places |
| `npk.basis` | `oxide` / `elemental` | Required, no default |
| `label_directions` | list | At least one |
| `notes` | text | Optional, defaults to `""` |

Each **label direction** is one dose and how often to apply it, in the units printed on the label:

| Field | Type | Rules |
|---|---|---|
| `amount` | number | Greater than 0 |
| `amount_unit` | `ml` / `g` / `tsp` / `tbsp` | |
| `water_volume` | number | Greater than 0 |
| `water_unit` | `L` / `gal` | |
| `frequency` | `{"kind": "interval", "days": N}` or `{"kind": "every_watering"}` | `days` is a whole number greater than 0, and only allowed for `interval` |
| `use` | text or `null` | What the direction is for, e.g. "maintenance" |

Rule across directions: when there are **several** directions, each needs a `use`, and no two may share one (ignoring case), so the user can tell them apart.

All objects reject unknown fields, so a typo such as `"dilutoin"` is an error rather than silently ignored.

## 2. Design decisions

**NPK is stored as printed.** Each number is the percent on the label (9-3-6 means 9 % N), so 9-3-6 and 3-1-2 stay different products even though their ratio is the same; a ratio would lose the concentration.

**`Decimal`, not float.** With floats, a valid label such as 0.2-83.9-15.9 adds up to slightly more than 100, and values pick up binary rounding error. `Decimal` keeps each value exactly as printed. In JSON the values are numbers (`9`, `0.25`), not Pydantic's default strings.

**The NPK total is not checked.** P and K are usually printed as oxide equivalents (P2O5, K2O), so the three numbers do not add up to a share of the product, and no rule says they cannot exceed 100. Each value is only checked against 0-100. Values that are possible but unusual (above the strongest known materials) are planned as soft warnings; thresholds and sources are in `docs/ideas.md`.

**`basis` is required, with no default.** The US and Canada print P and K as oxides; the EU defaults to oxides but allows elements; Australia prints elements. A default would silently mislabel data from the other countries. Sources: Canada's Fertilizers Regulations, EU Regulation 2019/1009 Annex III, Australia's National Code of Practice for Fertilizer Description and Labelling.

**Dose and frequency stay together.** Labels often give several pairs ("1/4 tsp per gallon every watering, or 1 tsp per gallon monthly"); separate fields would lose which dose goes with which frequency.

**Frequency is a discriminated union.** `kind` decides which shape applies, like a sealed interface with two records in Java. "Every watering" is not a number of days, so it is its own kind instead of `days: null`.

**Units are stored as printed.** Entering what the label says is less error-prone; converting (tsp per gallon to ml per litre) belongs in code when doses are calculated.

## 3. Tables

Defined in `backend/app/models.py`; migrations in `backend/migrations/versions/`.

**`products`**

| Column | Notes |
|---|---|
| `id` | Primary key |
| `brand`, `name`, `type`, `notes` | |
| `npk_n`, `npk_p`, `npk_k` | Integer hundredths (9.25 is stored as 925) through `HundredthsDecimal`, because SQLite stores NUMERIC as floating point |
| `npk_basis` | |
| `created_at` | UTC |

CHECK constraints repeat the single-row schema rules, so writers other than the API (scripts, imports) cannot break them either: brand and name not blank; type and basis from their lists; the four NPK columns all set or all empty; each value 0-10000 hundredths; a fertilizer has NPK. A unique index on `lower(brand), lower(name)` makes the same product entered twice, in any case, a conflict.

**`product_label_directions`**: one row per direction, linked to its product.

| Column | Notes |
|---|---|
| `product_id` | Foreign key, `ON DELETE CASCADE`: a product takes its directions with it |
| `position` | The order on the label; a table has no order of its own |
| `amount`, `amount_unit`, `water_volume`, `water_unit` | |
| `frequency_kind`, `frequency_days` | The union in table form: days only for `interval`, and then greater than 0 (guarded with `IS NOT NULL`, since a NULL result passes a CHECK) |
| `use` | Not blank when set; unique per product ignoring case (`lower(use)`); several NULLs are allowed |

"Several directions each need a `use`" spans rows, which a CHECK cannot see, so only Pydantic enforces it.

## 4. Endpoints

In `backend/app/routers/products.py`.

| Method | Path | Result |
|---|---|---|
| `POST` | `/products` | `201` with the product; `409` if brand and name already exist (ignoring case); `422` if invalid |
| `GET` | `/products` | All products, sorted by brand, then name, ignoring case; directions are loaded in one extra query, not one per product |
| `GET` | `/products/{id}` | `404` if not found |
| `PUT` | `/products/{id}` | Replaces every field and all directions; `id` and `created_at` stay; `409` when renamed into another product |
| `DELETE` | `/products/{id}` | `204`; the directions go with it |

**Conversion.** The API nests what the tables keep flat (`npk` is four columns; `frequency` is two), so `fill_product` and `product_to_read` convert by hand in both directions.

**Duplicates are decided by the unique index**, not by a lookup before the insert, which two concurrent requests could both pass. `commit_or_conflict` (in `routers/common.py`) turns that index's violation into `409`; any other integrity error means validation let bad data through, so it becomes a `500`.

**Replacing directions on PUT.** SQLAlchemy inserts new rows before deleting old ones, so directions that keep their `use` or position would hit the unique indexes. The old directions are removed with one direct `DELETE ... WHERE product_id = ?`, inside `session.no_autoflush`, so no field change is sent early and a duplicate name still fails at commit as `409`.

## 5. AI draft from a label photo

`POST /products/draft` (in `backend/app/routers/product_drafts.py`) uploads a photo and returns a draft. **Nothing is saved**: the user checks the draft and saves it with `POST /products`.

```
photo ─► size and format check ─► read_label (Claude) ─► LabelExtraction ─► draft_from_extraction ─► LabelDraftResponse
          413 / 415, no model call    422 / 502 / 503                          ProductCreate validates
```

**Upload checks**, before the model is called so a wrong file costs nothing: at most 7 MB (the API's 10 MB limit applies after base64 encoding, which adds a third), and JPEG, PNG, GIF, or WebP as told by the file's first bytes, not its name or declared type.

**`LabelExtraction`** is what the model returns (structured output). It is looser than `ProductCreate` on purpose: a field the label does not show, or that cannot be read, is `null` rather than guessed. Each direction keeps its `source_text` (the instruction as printed), and the model lists `uncertain_fields` it read but is not sure of.

**The draft.** `draft_from_extraction` leaves empty fields out and lets `ProductCreate` validate. If everything passes, `product` is the ready draft; otherwise `product` is `null` and `problems` lists each missing or invalid field with its location (e.g. `npk.basis`, `label_directions.0.amount_unit`). No default is filled in and no value is rounded, so nothing is invented on the model's behalf.

**The call record.** Each response includes the model requested and the model that served it (a server-side fallback can re-run a declined request on another model), the prompt version, input and output tokens, latency, and cost at list price. Every call also logs one line with these, without the image.

**Errors.** The model declining to read the image is `422` (try another photo); an answer that is cut off or not a valid extraction is `502`; the API being busy, unreachable, or rejecting our key or billing is `503`.

Code: `backend/app/label_reader.py` (prompt, model call, cost), `backend/app/label_drafts.py` (draft), `backend/app/schemas.py` (`LabelExtraction`, `LabelDraftResponse`).

## 6. Tests

| File | Covers |
|---|---|
| `tests/test_product_schema.py` | Every validation rule, including boundaries |
| `tests/test_product_table.py`, `tests/test_label_direction_table.py` | Every CHECK, unique index, and cascade |
| `tests/test_product_conversion.py` | API shape to tables and back, including replacing directions |
| `tests/test_products_api.py` | The five endpoints and their status codes |
| `tests/test_label_drafts.py` | LabelExtraction to draft: every gap becomes a problem, never a guess |
| `tests/test_label_reader.py`, `tests/test_product_draft_api.py` | The model call and the draft endpoint, against a fake Claude client (no network, no cost) |

Every rule was also checked by a targeted mutation: break the code, confirm the test for that rule fails, restore.

## 7. Open questions and work in progress

- **How a direction is applied.** Directions do not yet say whether they are for watering a soil mix, a hydroponic reservoir, or a foliar spray. A future care plan needs to pick the direction that fits a group's growing medium, which free text in `use` cannot do reliably. Under discussion: a required `application` field (`watering` / `hydroponic` / `foliar`), with `use` becoming an optional note and its uniqueness rule removed.
- **Prompt `label-v2`** (not committed yet): ranges on the label are filled with the lower dose and the longer interval (underfeeding is safer) and listed in `lower_end_fields`; a direction that leaves out the water volume or frequency takes it from the instruction just before it; directions that are not read (outdoor, equipment) are listed in `skipped_directions` with a reason, so the UI can show what was left out.
- **Eval set**: real label photos with owner-checked answers, measuring per-field accuracy, cost, and latency by prompt version and model.
- **Deferred**: NPK soft warnings, w/w vs. w/v basis for liquids (needed for dose math), optimistic locking for concurrent edits, per-field error locations for list-wide rules. See `docs/ideas.md`.
