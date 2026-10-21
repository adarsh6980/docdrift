# DocDrift

Finds code snippets in your README/docs that no longer match the repo's code or library versions, proposes a fix with NVIDIA Nemotron via Nebius Token Factory, and re-runs each fix so only verified fixes are reported.

## Status, plainly
- Working offline: snippet extractor (README.md and docs/*.md), pipeline, scoring, 3 seeded fixture repos - 22 tests pass.
- Live integration: `nemotron.py` (Token Factory chat client, OpenAI-compatible) is written to the current API docs but still needs a verified live run - see "Live check" below.
- Execution, two runners:
  - `BwrapRunner` (default for untrusted repos): Linux namespace isolation via bubblewrap. No network, filesystem bounded to a read-only bind of the target repo plus a private scratch dir, host home and credentials not visible, CPU/memory limits, timeout. Verified by tests.
  - `ConstrainedSubprocessRunner` (trusted fixtures only): scrubbed environment so API keys never leak into snippet processes, CPU/memory limits, private temp dir. NOT a sandbox - shares host filesystem and network.
- NOT built: GitHub Action, demo UI, hosted demo.

## Setup
Python 3.10+, no dependencies for offline use.

    python3 -m unittest discover -s tests

## How it uses Nebius and NVIDIA
All model calls go through the Nebius Token Factory inference API (OpenAI-compatible chat completions) using NVIDIA Nemotron open models: fast tiers for extraction, reasoning tiers for fixes. The client counts prompt/completion tokens per run so cost per fix can be measured by model tier.

## Live check (one tiny call, a few tokens)
Run where your key lives - the key never leaves your machine:

    export NEBIUS_API_KEY=...        # never commit or paste it anywhere
    python3 -m docdrift.live_check   # lists Nemotron models, makes one tiny call
    python3 -m docdrift.live_check MODEL_ID

## Benchmark
    python3 -m docdrift.benchmark_real REPO [REPO ...]            # offline dry run (mock model)
    python3 -m docdrift.benchmark_real REPO --live MODEL_ID       # real run

Writes `docdrift-benchmark-report.json`: per-snippet findings, precision/recall where a repo has `truth.json`, and model token usage. Map tokens to cost using the current Token Factory pricing page; prices are deliberately not hardcoded.

## Design
`Runner` and `Model` are interfaces (`interfaces.py`): the fixture runner, bwrap runner and future Token Factory Sandboxes runner are interchangeable, as are the mock model and Nemotron. Benchmark truth maps `file#index` to `ok`/`stale`; metrics are precision, recall, and verified-fix rate.
