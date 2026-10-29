# DocDrift

DocDrift checks the code examples in your README and docs against reality. It runs every snippet, asks an NVIDIA Nemotron model on Nebius Token Factory to fix the genuinely stale ones, and then re-runs each proposed fix - so only verified fixes are ever reported.

**Live demo:** https://adarsh6980.github.io/docdrift/ · **License:** MIT · **Dependencies:** none for offline use

## Why

README examples quietly rot: an argument gets renamed, an import moves, a dependency drops an overload, and the docs keep lying. AI fix suggestions look convincing and are often wrong. DocDrift's core rule: a fix is only a fix if it executes.

## How it works

1. **Extract** every runnable snippet from `README.md`, `README.rst`, and `docs/*.md|.rst`: Markdown fences, RST `code-block` directives, `pycon` fences, and bare `>>>` doctests, normalized to runnable code.
2. **Execute** snippets the way a reader follows them: in reading order, with a shared namespace across each file's blocks, under bubblewrap isolation (no network, read-only repo bind, CPU/memory/time limits).
3. **Classify honestly.** Missing dependencies, live-service needs, and cascade effects are reported in their own categories - never counted as stale docs. A model reply with no parseable fix is recorded as a generation/format outcome, not a fix evaluation.
4. **Fix and verify.** Genuine stale candidates go to Nemotron. Each proposed fix re-runs in the same sandbox: pass and it is reported with the verified code; fail and it is rejected with the rejection error.
5. **Report** as JSON plus a self-contained HTML page (the demo above), with per-snippet evidence, model provenance, measured token usage, and a banner stating plainly whether the report is a live run or an offline dry run.

## Live evidence (October 29, 2026)

End-to-end live run on Token Factory (`nvidia/Nemotron-3_5-Lightning`) over the three seeded fixture repos:

- One proposed fix passed its sandbox rerun: reported `stale_fixed`, with the verified code.
- One proposed fix failed its rerun: rejected, reported `stale_unfixed`. That rejection is the product working, not failing.
- Measured cost: $0.0013 for the 4-call run.

Scope, stated plainly: this evidence covers small synthetic fixtures, not real open-source repos yet.

## Status

- 65 tests passing, public repo, MIT license
- Public demo page (above) rendered from the recorded live run
- Next: a live benchmark on real open-source repos, and a GitHub Action that checks docs on every pull request

## Setup

Requires Python 3.10+. No dependencies for offline use.

```bash
python3 -m unittest discover -s tests
```

## Usage

Offline dry run (mock model, no API key needed):

```bash
python3 -m docdrift.benchmark_real REPO [REPO ...]
```

Live run:

```bash
export NEBIUS_API_KEY=...        # read from your environment, sent only to Token Factory to authenticate
python3 -m docdrift.live_check   # one tiny call: proves auth, model access, billing path
python3 -m docdrift.benchmark_real REPO --live MODEL_ID
```

Both modes write `docdrift-benchmark-report.json`: per-snippet findings, disjoint outcome categories (`executed = evaluated + environment + service + cascade`), precision/recall where a repo has `truth.json`, and model provenance with token usage. Map tokens to cost using the current Token Factory pricing page; prices are deliberately not hardcoded.

### Spend guard

The client sends a per-call output cap on every request and supports an opt-in run-wide token budget (`NEBIUS_TOKEN_BUDGET`) that refuses the next call when its reservation would cross the budget. `NEBIUS_NO_THINK=1` tries NVIDIA's documented concise mode for reasoning models (unverified effect on Token Factory). The guard reduces overspend risk; it is not a billing guarantee.

## Execution isolation

Two runners, interchangeable behind the `Runner` interface:

- **`BwrapRunner`** (default for untrusted repos): Linux namespace isolation via bubblewrap. No network, filesystem bounded to a read-only bind of the repo plus a private scratch dir, host home and credentials not visible, CPU/memory limits, timeout. Verified by tests.
- **`ConstrainedSubprocessRunner`** (trusted fixtures only): scrubbed environment so API keys never leak into snippet processes, plus CPU/memory limits and a private temp dir. Not a sandbox - shares the host filesystem and network.

Real-repo benchmarking (`benchmark_real.py` + `prepare_env.py`) installs dependency venvs inside bwrap (network only for fetching, only the venv writable, repo mounted as a disposable copy) and executes offline against the read-only venv.

## How it uses Nebius and NVIDIA

All model calls go through the Nebius Token Factory inference API (OpenAI-compatible chat completions) using NVIDIA Nemotron open models for failure diagnosis and fix proposals. Extraction, sandboxing, and verification are deterministic local code. The client records provider, model, and token usage per run, so cost per fix can be measured by model tier.

## Design

`Runner` and `Model` are interfaces (`interfaces.py`): the fixture runner, bwrap runner, and a future Token Factory Sandboxes runner are interchangeable, as are the mock model and Nemotron. Benchmark truth maps `file#index` to `ok`/`stale`; metrics are precision, recall, and verified-fix rate.
