# Ideas Backlog

Ideas that came up during development but are out of scope for now. Each entry notes why it was deferred and what it depends on.

## Data model

### Shared soil component reference data
A `soil_components` reference list describing each component's properties: drainage, aeration, moisture retention, stability, nutrients.
- **Why:** the UI could explain why a group's soil mix is put together the way it is.
- **Depends on:** Groups with soil mixes (roadmap step 1).

## User features

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
