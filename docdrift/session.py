"""Run a file's snippets sequentially in ONE python process with a shared namespace.

Docs build state across blocks (`rows = ...` in block 1, `rows[0]` in block 3).
Per-snippet isolation mislabels those as broken. The driver execs each snippet in
order in shared globals and reports per-snippet ok/stdout/stderr as JSON lines.

The driver itself is plain python with no imports beyond stdlib; the same driver
runs inside bwrap for untrusted repos."""
import json, os, subprocess, sys, tempfile, shutil
from .interfaces import RunResult

DRIVER = r'''
import json, sys, io, contextlib, traceback
snippets = json.load(open(sys.argv[1]))
g = {"__name__": "__main__"}
out = []
for s in snippets:
    so, se = io.StringIO(), io.StringIO()
    ok = True
    with contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
        try:
            exec(compile(s, "<snippet>", "exec"), g)
        except Exception:
            ok = False
            traceback.print_exc(file=se)
    out.append({"ok": ok, "stdout": so.getvalue(), "stderr": se.getvalue()})
print(json.dumps(out))
'''

def run_session(codes, repo_dir, timeout, argv_for, env=None):
    """argv_for(workdir) must return the full argv executing the driver inside any sandbox."""
    workdir = tempfile.mkdtemp(prefix="docdrift-ses-")
    try:
        with open(os.path.join(workdir, "driver.py"), "w") as f:
            f.write(DRIVER)
        with open(os.path.join(workdir, "snippets.json"), "w") as f:
            json.dump(codes, f)
        try:
            r = subprocess.run(argv_for(workdir), capture_output=True, text=True,
                               timeout=timeout * max(1, len(codes)), env=env)
        except subprocess.TimeoutExpired:
            return [RunResult(False, "", f"timeout after {timeout * max(1, len(codes))}s")] * len(codes) or [RunResult(False, "", "timeout")]
        if r.returncode != 0 or not r.stdout.strip():
            err = (r.stderr or "session driver failed").strip()[-300:]
            return [RunResult(False, "", err)] * len(codes)
        results = json.loads(r.stdout)
        return [RunResult(x["ok"], x["stdout"], x["stderr"]) for x in results]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
