# Ideas Backlog

Ideas that came up during development but are out of scope for now. Each entry notes why it was deferred and what it depends on.

## Data model

### Source type
Add a `kind` to `Source` (e.g. `peer_reviewed`, `extension`, `grower`, `commercial`, `community_experiment`).
- **Why:** source reliability varies widely. The UI could show "backed by research", and `disputed` entries could show which side has stronger sources.
- **When:** after the first plant JSON file is written.

### Shared soil component reference data
A `soil_components.json` (like `window_exposures.json`) describing each component's properties: drainage, aeration, moisture retention, stability, nutrients.
- **Why:** the UI could explain why a mix is put together the way it is.

### Watering instructions per watering style
`soil.mixes` already varies by `watering_style` (`top` / `bottom`). `watering.how_to_water` is still a single text.
- **When:** when the UI lets users choose their watering style.

### Light exposure duration
Sources limit direct sun by hours ("no more than 2-3 hours"), but the schema only stores intensity (PPFD). Consider DLI (daily light integral, mol/m²/day = PPFD × hours) or a max direct-sun-hours field.

## User features

### Per-user overrides for fertilizer
The plant library stores default feeding frequency and dilution, relative to the product label. When users add "my plant", let them set their own product, label dose, and feeding style (periodic vs. "weakly weekly" at 1/4 strength every watering). The app can then compute the actual dose.
- **Depends on:** "add my plant" (roadmap step 1).

### Compare a spot's light to the plant's needs
Let users enter a light meter or app reading for a spot, and compare it to the plant's PPFD range ("bright enough?").

### Plant experiments (citizen science)
Users run controlled experiments with their own plants, e.g. two plants of the same cultivar, same spot, different fertilizer, and record the results over time.
- **Experiment design guidance:** same cultivar and size, same location, change one variable only.
- **Measurable outcomes:** new leaf count, fenestration count, leaf length, plus periodic photos. Avoid subjective ratings alone.
- **Aggregation:** results are only meaningful across many users running the same experiment.
- **Feeding back into care data:** never overwrite verified sources. Add aggregated results as a separate source type (`community_experiment`) shown alongside other sources.
- **Privacy:** photos and location need explicit consent.
- **Scope:** after roadmap steps 1-6. A first version could be single-user only (no aggregation).

## Testing

### Automated mutation testing with mutmut (roadmap step 3)
So far every test was verified by hand: break the code with a targeted change, confirm the test fails, restore. These scripts are not kept in the repo. Automate it once Docker exists.
- **Tool: mutmut.** Most widely used Python mutation tester, actively maintained. It needs `fork()`, so it does not run natively on Windows ("you must run inside WSL"); run it inside the backend Docker container instead.
- **Keep it separate from the normal test run.** It reruns the suite once per mutant, so it is far slower. Run it on demand (later: nightly in CI), not on every `pytest`.
- **Keep doing targeted manual mutations too.** Tools make mechanical changes (`<` to `<=`); cases like a test passing because a different rule rejects the data ("two locks") need knowledge of the business rules.
- **Alternatives considered:** cosmic-ray (mature, works on Windows, more setup steps); pytest-gremlins (simplest, a pytest plugin, but alpha and first released Jan 2026); mutatest (unmaintained since 2022).

## Library generation

### Sourcing from published research
Prefer open-access papers via scholarly APIs (OpenAlex, Semantic Scholar, PubMed Central OA subset) over scraping publisher sites, which usually prohibit it. Papers suit measured values (PPFD, DLI, temperature); most study commercial production, so home-care advice still comes mainly from extension services.

### Copyright and scraping
Store facts (numbers, ratios, component names) and write our own descriptions; never copy source text. Respect each site's terms and `robots.txt`, and rate-limit requests.
