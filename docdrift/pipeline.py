import os, glob
from dataclasses import dataclass, asdict
from .extract import extract_snippets

@dataclass
class Finding:
    file: str
    index: int
    line: int
    status: str            # ok | stale_fixed | stale_unfixed | stale_no_fix
                           # stale_no_fix = model produced no parseable fix
                           # (generation/format outcome); no fix rerun happened,
                           # so it says nothing about any model-produced fix.
    error: str = ""
    diagnosis: str = ""
    fixed_code: str = ""   # verified fix (only when its rerun passed)
    code: str = ""         # original snippet as executed
    fix_attempt: str = ""  # model fix that FAILED its rerun (stale_unfixed)
    fix_error: str = ""    # that rerun's error - the rejection reason

def repo_context(repo_dir, max_chars=800):
    """Grounding for the model: top-level layout plus dependency manifests."""
    parts = []
    try:
        parts.append("top-level: " + ", ".join(sorted(os.listdir(repo_dir))[:30]))
    except OSError:
        pass
    for name in ("requirements.txt", "pyproject.toml", "setup.py", "environment.yml"):
        p = os.path.join(repo_dir, name)
        if os.path.exists(p):
            with open(p, errors="replace") as f:
                parts.append(f"{name}:\n" + f.read()[:400])
    return "\n".join(parts)[:max_chars]

def _doc_paths(repo_dir, doc_globs):
    seen = []
    for g in doc_globs:
        for p in sorted(glob.glob(os.path.join(repo_dir, g))):
            if os.path.isfile(p) and p not in seen:
                seen.append(p)
    return seen

def scan_repo(repo_dir, runner, model, doc_globs=("README.md", "README.rst", "docs/*.md", "docs/*.rst")):
    findings = []
    ctx = repo_context(repo_dir)
    # Repo-wide session in doc-reading order (README first): doc files routinely
    # state imports once and reuse them across the whole doc set, so one shared
    # namespace for the repo's snippets matches how the docs are meant to be read.
    all_snippets = []
    for path in _doc_paths(repo_dir, doc_globs):
        rel = os.path.relpath(path, repo_dir)
        with open(path, errors="replace") as f:
            text = f.read()
        all_snippets.extend(extract_snippets(rel, text))
    if hasattr(runner, "run_file"):
        all_results = runner.run_file([s.code for s in all_snippets], repo_dir)
    else:
        all_results = [runner.run(s.code, repo_dir) for s in all_snippets]
    for s, r in zip(all_snippets, all_results):
        if r.ok:
            findings.append(Finding(s.file, s.index, s.line, "ok", code=s.code))
            continue
        diag = model.diagnose(s.code, r.stderr, ctx)
        fix = model.propose_fix(s.code, r.stderr, ctx)
        if fix is None or fix == s.code:
            # No parseable/effective fix produced: record the generation/format
            # outcome distinctly. The original failure stands; nothing reran.
            findings.append(Finding(s.file, s.index, s.line,
                "stale_no_fix", r.stderr.strip()[-200:], diag, "", code=s.code))
            continue
        v = runner.run(fix, repo_dir)
        if v.ok:
            findings.append(Finding(s.file, s.index, s.line,
                "stale_fixed", r.stderr.strip()[-200:], diag, fix, code=s.code))
        else:
            findings.append(Finding(s.file, s.index, s.line,
                "stale_unfixed", r.stderr.strip()[-200:], diag, "", code=s.code,
                fix_attempt=fix, fix_error=(v.stderr or "").strip()[-200:]))
    return findings

def to_dicts(fs):
    return [asdict(f) for f in fs]
