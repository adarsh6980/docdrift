"""Benchmark DocDrift on real repos.

    python3 -m docdrift.benchmark_real REPO_DIR [REPO_DIR ...] [--live MODEL_ID]

Without --live it uses the deterministic MockModel (offline dry run of the harness).
Snippets from the given repos are treated as untrusted and run under BwrapRunner
(Linux namespace isolation: no network, bounded filesystem, read-only repo).
With --live it calls Token Factory through NemotronModel; NEBIUS_API_KEY must be set.
Writes docdrift-benchmark-report.json (or --report PATH) in the current directory.

Repos with a truth.json ({"file#index": "ok"|"stale"}) also get precision/recall.
Model token usage is reported; map tokens to cost using the current pricing page
before drawing conclusions - prices are deliberately not hardcoded here."""
import argparse, json, os
from .pipeline import scan_repo
from .benchmark import score, load_truth
from .bwrap_runner import BwrapRunner
from .mock_model import MockModel
from .envclass import is_environment_failure, is_service_failure, is_cascade_failure
from .pipeline import _doc_paths
from .extract import extract_snippets


def _load_env(repo_dir):
    path = os.path.join(repo_dir, "docdrift-env.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def run_benchmark(repo_dirs, model, runner=None, doc_globs=("README.md", "README.rst", "docs/*.md", "docs/*.rst"),
                  report_path=None):
    default_runner = runner or BwrapRunner()
    repos = []
    # Disjoint categories: every executed snippet lands in exactly one bucket.
    # executed = evaluated + environment + service + cascade failures;
    # evaluated = ok + stale_fixed + stale_unfixed.
    totals = {"executed": 0, "evaluated": 0, "ok": 0, "stale_fixed": 0, "stale_unfixed": 0, "stale_no_fix": 0,
              "environment_failures": 0, "service_failures": 0, "cascade_failures": 0}
    for d in repo_dirs:
        env = _load_env(d)
        repo_runner = default_runner
        venv = env.get("venv")
        if venv:
            from .prepare_env import site_packages
            repo_runner = BwrapRunner(env_site_packages=site_packages(venv))
            entry_venv = venv
        else:
            entry_venv = None
        findings = scan_repo(d, repo_runner, model, doc_globs=doc_globs)
        repo_codes, key_to_pos = [], {}
        for path in _doc_paths(d, doc_globs):
            rel = os.path.relpath(path, d)
            with open(path, errors="replace") as fh:
                for sn in extract_snippets(rel, fh.read()):
                    key_to_pos[(rel, sn.index)] = len(repo_codes)
                    repo_codes.append(sn.code)
        evaluated, env_failed, svc_failed, casc_failed = [], [], [], []
        failed_positions = {key_to_pos.get((f.file, f.index)) for f in findings if f.status != "ok"}
        for f in findings:
            if f.status == "ok":
                evaluated.append(f)
            elif is_environment_failure(f.error, d):
                env_failed.append(f)
            elif is_service_failure(f.error):
                svc_failed.append(f)
            elif is_cascade_failure(f.error, repo_codes,
                                    [i for i in failed_positions
                                     if i is not None and i < key_to_pos.get((f.file, f.index), 0)]):
                casc_failed.append(f)
            else:
                evaluated.append(f)
        def _brief(f):
            return {"file": f.file, "line": f.line, "index": f.index,
                    "error": f.error.strip().splitlines()[-1][:120] if f.error.strip() else ""}
        entry = {"repo": os.path.abspath(d), "venv": entry_venv,
                 "evaluated": [f.__dict__ for f in evaluated],
                 "environment_failures": [_brief(f) for f in env_failed],
                 "service_failures": [_brief(f) for f in svc_failed],
                 "cascade_failures": [_brief(f) for f in casc_failed]}
        truth_path = os.path.join(d, "truth.json")
        if os.path.exists(truth_path):
            entry["score"] = score(evaluated, load_truth(d))
        repos.append(entry)
        for f in evaluated:
            totals["evaluated"] += 1
            totals[f.status] += 1
        totals["environment_failures"] += len(env_failed)
        totals["service_failures"] += len(svc_failed)
        totals["cascade_failures"] += len(casc_failed)
        totals["executed"] += len(evaluated) + len(env_failed) + len(svc_failed) + len(casc_failed)
    # Provenance of the model execution that produced this report. Taken from
    # the model object's own recorded identity, never inferred from token
    # fields: a mock or hand-edited token count must not read as a live run.
    provider = getattr(model, "provider", "unknown")
    model_prov = {"provider": provider}
    if provider == "nebius-token-factory":
        model_prov["model_id"] = getattr(model, "model_id", None)
        # Successful generations recorded by the model object this run; a
        # configured-but-never-succeeded run must not read as Live downstream.
        model_prov["successful_calls"] = getattr(model, "ok_calls", None)
    report = {"execution_mode": ("repo-wide shared namespace in doc-reading order "
                                 "(README first) - an execution assumption, not ground "
                                 "truth about example independence"),
              "repos": repos, "totals": totals, "model": model_prov,
              "model_tokens": {"prompt": getattr(model, "prompt_tokens", None),
                               "completion": getattr(model, "completion_tokens", None),
                               "calls": getattr(model, "calls", None)}}
    path = report_path or "docdrift-benchmark-report.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--live", metavar="MODEL_ID", help="use Token Factory with this model id")
    ap.add_argument("--report", default="docdrift-benchmark-report.json",
                    help="report output path - point it somewhere durable for live runs")
    args = ap.parse_args()
    if args.live:
        from .nemotron import NemotronModel
        model = NemotronModel(args.live)
    else:
        model = MockModel()
        print("offline dry run (MockModel). Pass --live MODEL_ID for a real run.")
    report = run_benchmark(args.repos, model, report_path=args.report)
    print(json.dumps({"totals": report["totals"], "model_tokens": report["model_tokens"]}, indent=2))
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
