import os, glob
from dataclasses import dataclass, asdict
from .extract import extract_snippets

@dataclass
class Finding:
    file: str
    index: int
    line: int
    status: str            # ok | stale_fixed | stale_unfixed
    error: str = ""
    diagnosis: str = ""
    fixed_code: str = ""

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

def scan_repo(repo_dir, runner, model, doc_globs=("README.md", "docs/*.md")):
    findings = []
    ctx = repo_context(repo_dir)
    for path in _doc_paths(repo_dir, doc_globs):
        rel = os.path.relpath(path, repo_dir)
        with open(path, errors="replace") as f:
            text = f.read()
        for s in extract_snippets(rel, text):
            r = runner.run(s.code, repo_dir)
            if r.ok:
                findings.append(Finding(rel, s.index, s.line, "ok"))
                continue
            diag = model.diagnose(s.code, r.stderr, ctx)
            fix = model.propose_fix(s.code, r.stderr, ctx)
            v = runner.run(fix, repo_dir) if fix != s.code else r
            findings.append(Finding(rel, s.index, s.line,
                "stale_fixed" if v.ok else "stale_unfixed", r.stderr.strip()[-200:], diag, fix if v.ok else ""))
    return findings

def to_dicts(fs):
    return [asdict(f) for f in fs]
