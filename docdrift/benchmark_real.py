"""Benchmark DocDrift on real repos.

    python3 -m docdrift.benchmark_real REPO_DIR [REPO_DIR ...] [--live MODEL_ID]

Without --live it uses the deterministic MockModel (offline dry run of the harness).
Snippets from the given repos are treated as untrusted and run under BwrapRunner
(Linux namespace isolation: no network, bounded filesystem, read-only repo).
With --live it calls Token Factory through NemotronModel; NEBIUS_API_KEY must be set.
Writes docdrift-benchmark-report.json in the current directory.

Repos with a truth.json ({"file#index": "ok"|"stale"}) also get precision/recall.
Model token usage is reported; map tokens to cost using the current pricing page
before drawing conclusions - prices are deliberately not hardcoded here."""
import argparse, json, os
from .pipeline import scan_repo
from .benchmark import score, load_truth
from .bwrap_runner import BwrapRunner
from .mock_model import MockModel
from .envclass import is_environment_failure


def _load_env(repo_dir):
    path = os.path.join(repo_dir, "docdrift-env.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def run_benchmark(repo_dirs, model, runner=None, doc_globs=("README.md", "README.rst", "docs/*.md", "docs/*.rst")):
    default_runner = runner or BwrapRunner()
    repos = []
    totals = {"snippets": 0, "ok": 0, "stale_fixed": 0, "stale_unfixed": 0,
              "environment_failures": 0}
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
        evaluated, env_failed = [], []
        for f in findings:
            if f.status != "ok" and is_environment_failure(f.error, d):
                env_failed.append(f)
            else:
                evaluated.append(f)
        entry = {"repo": os.path.abspath(d), "venv": entry_venv,
                 "evaluated": [f.__dict__ for f in evaluated],
                 "environment_failures": [
                     {"file": f.file, "line": f.line, "index": f.index,
                      "missing_module": f.error.strip().splitlines()[-1] if f.error.strip() else ""}
                     for f in env_failed]}
        truth_path = os.path.join(d, "truth.json")
        if os.path.exists(truth_path):
            entry["score"] = score(evaluated, load_truth(d))
        repos.append(entry)
        for f in evaluated:
            totals["snippets"] += 1
            totals[f.status] += 1
        totals["environment_failures"] += len(env_failed)
    report = {"repos": repos, "totals": totals,
              "model_tokens": {"prompt": getattr(model, "prompt_tokens", None),
                               "completion": getattr(model, "completion_tokens", None),
                               "calls": getattr(model, "calls", None)}}
    with open("docdrift-benchmark-report.json", "w") as f:
        json.dump(report, f, indent=2)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--live", metavar="MODEL_ID", help="use Token Factory with this model id")
    args = ap.parse_args()
    if args.live:
        from .nemotron import NemotronModel
        model = NemotronModel(args.live)
    else:
        model = MockModel()
        print("offline dry run (MockModel). Pass --live MODEL_ID for a real run.")
    report = run_benchmark(args.repos, model)
    print(json.dumps({"totals": report["totals"], "model_tokens": report["model_tokens"]}, indent=2))
    print("wrote docdrift-benchmark-report.json")


if __name__ == "__main__":
    main()
