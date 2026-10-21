"""Constrained subprocess runner for TRUSTED snippets (our fixtures, our own repos).

This is NOT a sandbox: the snippet shares the host filesystem and network. It only
bounds environment (scrubbed, so API keys do not leak into snippet processes),
CPU/memory rlimits, a wall-clock timeout, and a private temp cwd.

For untrusted snippets from arbitrary repos use BwrapRunner (bwrap_runner.py),
which actually bounds filesystem and network."""
import os, shutil, subprocess, sys, tempfile
from .interfaces import RunResult

try:
    import resource
except ImportError:
    resource = None


def _limits(cpu_seconds, mem_bytes):
    if resource is None:
        return None
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 5))
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    return apply


class ConstrainedSubprocessRunner:
    def __init__(self, timeout=10, cpu_seconds=10, mem_mb=512):
        self.timeout, self.cpu_seconds, self.mem_bytes = timeout, cpu_seconds, mem_mb * 1024 * 1024

    def run(self, code, repo_dir):
        workdir = tempfile.mkdtemp(prefix="docdrift-sub-")
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": os.path.abspath(os.path.join(repo_dir, "lib")),
            "HOME": workdir,
            "PYTHONHASHSEED": "0",
        }
        snippet = os.path.join(workdir, "snippet.py")
        with open(snippet, "w") as f:
            f.write(code)
        try:
            r = subprocess.run(
                [sys.executable, snippet], capture_output=True, text=True,
                timeout=self.timeout, env=env, cwd=workdir,
                preexec_fn=_limits(self.cpu_seconds, self.mem_bytes),
            )
            return RunResult(r.returncode == 0, r.stdout, r.stderr)
        except subprocess.TimeoutExpired:
            return RunResult(False, "", f"timeout after {self.timeout}s")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
