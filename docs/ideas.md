# Ideas Backlog

Ideas that came up during development but are out of scope for now. Each entry notes why it was deferred and what it depends on.

## Data model

### Shared soil component reference data
A `soil_components` reference list describing each component's properties: drainage, aeration, moisture retention, stability, nutrients.
- **Why:** the UI could explain why a group's soil mix is put together the way it is.
- **Depends on:** Groups with soil mixes (roadmap step 1).

### Weight or volume basis for liquid concentrations
Liquid labels may state nutrient percentages by weight (w/w) or by weight per volume (w/v). Australia's labelling code requires w/v for liquids; the EU allows either mass or volume. Add a `concentration_basis` (`w/w` / `w/v`) to `Npk`.
- **Why:** turning a dose in ml into grams of a nutrient needs w/v, or w/w plus the liquid's density. It does not affect NPK range checks.
- **When:** when dose math is added (e.g., nutrients delivered per watering).

## Input checks

### NPK soft warnings
The schema only rejects impossible NPK values (each 0-100). Values that are possible but unusual should ask the user to confirm instead of being rejected. Write this as a pure function (e.g. `npk_warnings(npk) -> list[str]`), not as a schema rule, since a schema can only accept or reject. Compare in oxide basis, converting elemental values first (EU factors: P = P2O5 × 0.436, K = K2O × 0.830).
- **Thresholds, each just above the strongest known single material** (sources were read in full):
  - N > 46: urea is 45-46 (UMD Table B-5, UMass, NMSU A-133). Only anhydrous and aqua ammonia are higher, and they are not used indoors.
  - P2O5 > 61: water-soluble monoammonium phosphate is 12-61-0 (Haifa MAP).
  - K2O > 63: potassium chloride is 60-63 (UMD Table B-5).
  - N + P2O5 + K2O > 100: the highest total found was potassium metaphosphate, 0-59-39 (UMass).
  - All three are 0 for a fertilizer: probably not filled in.
- **Limit:** these catch typos like 90 for 9, not "too strong for houseplants"; that needs label data for houseplant products, and no reliable source was found.
- **When:** after the core API works; the API then returns warnings and saves only after the user confirms.

## User features

### Environment conditions per group (e.g., humidity)
Plants in the same family can need different humidity (Philodendron and Anthurium more than Monstera and pothos), which is one reason groups are defined by care rather than taxonomy. Plans and logs cover care actions (fertilize, repot, water), not conditions.
- **Idea:** a target humidity range (and maybe light) on each group, shown alongside its plans.
- **When:** after the core works.

### Copy a group
Create "Variegated aroids" from "Aroids" with the same taxa, soil mix, and plans, then lower the fertilizer dose.
- **Depends on:** CarePlans.


### Plant experiments (citizen science)
Users run controlled experiments with their own plants, e.g. two plants of the same cultivar, same spot, different fertilizer, and record the results over time.
- **Experiment design guidance:** same cultivar and size, same location, change one variable only.
- **Measurable outcomes:** new leaf count, fenestration count, leaf length, plus periodic photos. Avoid subjective ratings alone.
- **Aggregation:** results are only meaningful across many users running the same experiment.
- **Feeding back into care data:** never overwrite sourced data. Add aggregated results as a separate source type (`community_experiment`) shown alongside other sources.
- **Privacy:** photos and location need explicit consent.
- **Depends on:** optional individual plant profiles, which are out of the MVP; groups are too coarse to compare two plants.
- **Scope:** after roadmap steps 1-6. A first version could be single-user only (no aggregation).

## Testing

### Automated mutation testing with mutmut (roadmap step 3)
So far every test was verified by hand: break the code with a targeted change, confirm the test fails, restore. These scripts are not kept in the repo. Automate it once Docker exists.
- **Tool: mutmut.** Most widely used Python mutation tester, actively maintained. It needs `fork()`, so it does not run natively on Windows ("you must run inside WSL"); run it inside the backend Docker container instead.
- **Keep it separate from the normal test run.** It reruns the suite once per mutant, so it is far slower. Run it on demand (later: nightly in CI), not on every `pytest`.
- **Keep doing targeted manual mutations too.** Tools make mechanical changes (`<` to `<=`); cases like a test passing because a different rule rejects the data ("two locks") need knowledge of the business rules.
- **Alternatives considered:** cosmic-ray (mature, works on Windows, more setup steps); pytest-gremlins (simplest, a pytest plugin, but alpha and first released Jan 2026); mutatest (unmaintained since 2022).

## AI drafting from web sources (AI feature 2)

Notes for drafting a care plan and soil mix for a new genus group from multiple sources.

### Source rules
- Read every source in full before citing it; never cite a claim seen only in a search summary.
- Record disagreements between sources as disputed points instead of picking one silently.

### Source type
Give each source a `kind` (e.g. `peer_reviewed`, `extension`, `grower`, `commercial`, `community_experiment`).
- **Why:** source reliability varies widely. The UI could show "backed by research", and disputed points could show which side has stronger sources.

### Sourcing from published research
Prefer open-access papers via scholarly APIs (OpenAlex, Semantic Scholar, PubMed Central OA subset) over scraping publisher sites, which usually prohibit it. Papers suit measured values (e.g. nutrient rates, substrate properties); most study commercial production, so home-care advice still comes mainly from extension services.

### Copyright and scraping
Store facts (numbers, ratios, component names) and write our own descriptions; never copy source text. Respect each site's terms and `robots.txt`, and rate-limit requests.

## API

### Prevent lost updates (optimistic locking)
PUT replaces a whole resource. If a product is edited in two tabs, the second save silently overwrites the first. Add a version (or `updated_at`) that PUT must send back; on mismatch return 409 and ask the user to reload. Same idea as JPA `@Version`.
- **When:** with multiple users, or if the frontend makes concurrent edits likely.

### Precise error location for cross-field rules
Rules that look at a whole list (e.g., "several label directions each need a `use`") report their error at `body`, not at the field. A form cannot highlight the right row.
- **Idea:** raise the error with a location such as `label_directions[0].use`.
- **When:** when the frontend shows validation errors per field.
