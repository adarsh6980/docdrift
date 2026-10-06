import json, os

def score(findings, truth):
    """truth: {"file#index": "ok"|"stale"}. Returns precision/recall on stale detection and verified-fix rate."""
    tp = fp = fn = fixed = 0
    for f in findings:
        key = f"{f.file}#{f.index}"
        t = truth.get(key)
        flagged = f.status != "ok"
        if t == "stale" and flagged: tp += 1
        elif t == "ok" and flagged: fp += 1
        elif t == "stale" and not flagged: fn += 1
        if t == "stale" and f.status == "stale_fixed": fixed += 1
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"precision": p, "recall": r, "stale_total": tp + fn, "verified_fixed": fixed}

def load_truth(repo_dir):
    return json.load(open(os.path.join(repo_dir, "truth.json")))
