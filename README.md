# DocDrift (private prep, not published)

Finds README/doc code snippets that no longer match the repo's code or library versions, proposes a fix, and re-runs it to prove the fix works.

## Status, plainly
- Working locally: snippet extractor, pipeline, scoring, 3 seeded fixture repos, deterministic tests.
- MOCKED: the model (`mock_model.py`) and the runner (`LocalFixtureRunner`, trusted fixtures only, not a sandbox).
- NOT built: Nemotron integration, Token Factory Sandboxes, Tavily lookup, GitHub Action, UI, real-repo benchmark, licence file (add MIT/Apache before publishing).

## Run
    python3 -m unittest discover -s tests

## Design
Runner and Model are interfaces (`interfaces.py`). Swap in a Token Factory Sandbox runner and a Nemotron model later without touching `pipeline.py`.
Benchmark: each repo has `truth.json` mapping `file#index` to `ok` or `stale`. Metrics: precision, recall, verified-fix rate; later cost per fix by model tier.
