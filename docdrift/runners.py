import subprocess, sys, os, tempfile
from .interfaces import RunResult

class LocalFixtureRunner:
    """Runs a snippet in a subprocess with repo_dir/lib on the path.
    FOR TRUSTED FIXTURES ONLY. Not a sandbox. Real runs go through Token Factory Sandboxes (not built)."""
    def run(self, code, repo_dir, timeout=10):
        env = dict(os.environ, PYTHONPATH=os.path.join(repo_dir, "lib"))
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            p = f.name
        try:
            r = subprocess.run([sys.executable, p], capture_output=True, text=True, timeout=timeout, env=env)
            return RunResult(r.returncode == 0, r.stdout, r.stderr)
        except subprocess.TimeoutExpired:
            return RunResult(False, "", "timeout")
        finally:
            os.unlink(p)
