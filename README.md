# DocDrift

Finds code snippets in your README/docs that no longer match the repo's code or library versions, proposes a fix with NVIDIA Nemotron via Nebius Token Factory, and re-runs each fix so only verified fixes are reported.

## Status, plainly
- Working: snippet extraction, pipeline, scoring, 3 seeded fixture repos - 63 tests pass.
- Live-verified on Token Factory (Oct 29, nvidia/Nemotron-3_5-Lightning): end-to-end run over the 3 fixture repos produced one model fix that passed its sandbox rerun (reported stale_fixed) and one that failed its rerun (rejected, reported stale_unfixed). The verify-by-rerun guardrail works against a live model.
- Extraction (`extract.py`): Markdown fenced blocks, reStructuredText `code-block`/`code` directives (including whitespace-blank separators), `pycon` fences, and bare `>>>` doctest blocks. Doctest-style snippets are normalized to runnable code (prompt/output lines stripped, dedented). Covers `README.md`, `README.rst`, `docs/*.md`, `docs/*.rst`.
- Session execution (`session.py`): docs build state across blocks, so snippets from one file run in order in a single driver process with a shared namespace, and across a repo's doc set in reading order (README first). Per-snippet ok/stdout/stderr is still reported individually.
- Execution, two runners:
  - `BwrapRunner` (default for untrusted repos): Linux namespace isolation via bubblewrap. No network, filesystem bounded to a read-only bind of the target repo plus a private scratch dir, host home and credentials not visible, CPU/memory limits, timeout. Verified by tests.
  - `ConstrainedSubprocessRunner` (trusted fixtures only): scrubbed environment so API keys never leak into snippet processes, CPU/memory limits, private temp dir. NOT a sandbox - shares host filesystem and network.
- Honest outcomes: environment (missing deps), service (needs a live DB/network) and cascade (a name an earlier failed snippet would have bound) failures are classified separately and never counted as stale docs. A model reply with no parseable fix is `stale_no_fix` - a generation/format outcome, not a fix evaluation. Report categories are disjoint: `executed = evaluated + environment + service + cascade`, with an explicit `execution_mode` label stating that repo-wide shared state in reading order is an execution assumption, not ground truth about example independence.
- Real-repo benchmarking (`benchmark_real.py` + `prepare_env.py`): dependency venvs installed inside bwrap (network only for fetching, only the venv writable, repo mounted as a disposable copy), offline execution against the read-only venv. A live real-repo benchmark is future work - so far the live evidence covers the seeded fixtures.
- Spend guard: the Token Factory client sends a per-call output cap on every request and supports an opt-in run-wide token budget (`NEBIUS_TOKEN_BUDGET`) that refuses the next call before billing when its reservation would cross the budget. `NEBIUS_NO_THINK=1` tries NVIDIA's documented concise mode for reasoning models (unverified effect on Token Factory).
- Demo page (`demo_page.py`): renders a benchmark report as a self-contained static HTML page showing original snippets, verified fixes, rejected fixes with the rerun error that rejected them, measured token usage, and a visible banner stating whether the report is an offline dry run or a recorded live run.
- NOT built: GitHub Action, hosted demo, live real-repo benchmark.

## Setup
Python 3.10+, no dependencies for offline use.

    python3 -m unittest discover -s tests

## How it uses Nebius and NVIDIA
All model calls go through the Nebius Token Factory inference API (OpenAI-compatible chat completions) using NVIDIA Nemotron open models for failure diagnosis and fix proposals; extraction, sandboxing and verification are deterministic local code. The client counts prompt/completion tokens per run so cost per fix can be measured by model tier.

## Live check (one tiny call, a few tokens)
The key is read from your environment and sent only to Token Factory to authenticate requests; never commit or paste it anywhere:

    export NEBIUS_API_KEY=...        # never commit or paste it anywhere
    python3 -m docdrift.live_check   # lists Nemotron models, makes one tiny call
    python3 -m docdrift.live_check MODEL_ID

The PASS line proves authentication, model access and the billing path with one bounded call. It is not a task-correctness test.

## Benchmark
    python3 -m docdrift.benchmark_real REPO [REPO ...]            # offline dry run (mock model)
    python3 -m docdrift.benchmark_real REPO --live MODEL_ID       # real run

Writes `docdrift-benchmark-report.json`: per-snippet findings, disjoint outcome categories, precision/recall where a repo has `truth.json`, model provenance and token usage. Map tokens to cost using the current Token Factory pricing page; prices are deliberately not hardcoded.

## Design
`Runner` and `Model` are interfaces (`interfaces.py`): the fixture runner, bwrap runner and future Token Factory Sandboxes runner are interchangeable, as are the mock model and Nemotron. Benchmark truth maps `file#index` to `ok`/`stale`; metrics are precision, recall, and verified-fix rate.
