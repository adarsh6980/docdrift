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

def scan_repo(repo_dir, runner, model, doc_glob="docs/*.md"):
    findings = []
    for path in sorted(glob.glob(os.path.join(repo_dir, doc_glob))):
        rel = os.path.relpath(path, repo_dir)
        text = open(path).read()
        for s in extract_snippets(rel, text):
            r = runner.run(s.code, repo_dir)
            if r.ok:
                findings.append(Finding(rel, s.index, s.line, "ok"))
                continue
            diag = model.diagnose(s.code, r.stderr, "")
            fix = model.propose_fix(s.code, r.stderr, "")
            v = runner.run(fix, repo_dir) if fix != s.code else r
            findings.append(Finding(rel, s.index, s.line,
                "stale_fixed" if v.ok else "stale_unfixed", r.stderr.strip()[-200:], diag, fix if v.ok else ""))
    return findings

def to_dicts(fs):
    return [asdict(f) for f in fs]
