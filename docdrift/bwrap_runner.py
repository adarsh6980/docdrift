"""Bubblewrap-isolated runner for UNTRUSTED doc snippets from arbitrary repos.

Uses Linux namespaces via bwrap to bound the actual risks:
- no network (--unshare-all: no net, pid, ipc, uts namespaces)
- filesystem bounded to a read-only bind of the target repo plus a private /work
  scratch dir - host home, credentials and other repos are not visible at all
- repo mounted read-only, so snippets cannot modify the code they document
- CPU/address-space rlimits and a wall-clock timeout on top

Verified by tests: DNS fails inside, /home is not visible, repo writes fail.
Requires bwrap on PATH (Linux)."""
import os, shutil, subprocess, tempfile
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


class BwrapRunner:
    def __init__(self, timeout=15, cpu_seconds=15, mem_mb=768, env_site_packages=None):
        self.timeout, self.cpu_seconds, self.mem_bytes = timeout, cpu_seconds, mem_mb * 1024 * 1024
        # Optional prepared dependency venv (see prepare_env.py): mounted
        # READ-ONLY so offline snippets can import installed deps. Never
        # writable, never network-enabled inside a snippet run.
        self.env_site_packages = env_site_packages
        if shutil.which("bwrap") is None:
            raise RuntimeError("bwrap not found; cannot isolate untrusted snippets")

    def _env_args(self):
        if not self.env_site_packages:
            return [], "/repo/lib:/repo/src:/repo"
        return (["--ro-bind", self.env_site_packages, "/env-lib"],
                "/env-lib:/repo/lib:/repo/src:/repo")

    def run(self, code, repo_dir):
        workdir = tempfile.mkdtemp(prefix="docdrift-bwrap-")
        with open(os.path.join(workdir, "snippet.py"), "w") as f:
            f.write(code)
        env_binds, pythonpath = self._env_args()
        argv = [
            "bwrap", "--unshare-all", "--die-with-parent", "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "PYTHONPATH", pythonpath,
            "--setenv", "PYTHONHASHSEED", "0",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", os.path.abspath(repo_dir), "/repo",
        ] + env_binds + [
            "--bind", workdir, "/work", "--chdir", "/work",
            "--", "python3", "/work/snippet.py",
        ]
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=self.timeout,
                               preexec_fn=_limits(self.cpu_seconds, self.mem_bytes))
            return RunResult(r.returncode == 0, r.stdout, r.stderr)
        except subprocess.TimeoutExpired:
            return RunResult(False, "", f"timeout after {self.timeout}s")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def run_file(self, codes, repo_dir):
        from .session import run_session
        repo_abs = os.path.abspath(repo_dir)
        env_binds, pythonpath = self._env_args()
        def argv_for(workdir):
            return [
                "bwrap", "--unshare-all", "--die-with-parent", "--clearenv",
                "--setenv", "PATH", "/usr/bin:/bin",
                "--setenv", "PYTHONPATH", pythonpath,
                "--setenv", "PYTHONHASHSEED", "0",
                "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
                "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
                "--ro-bind", repo_abs, "/repo",
            ] + env_binds + [
                "--bind", workdir, "/work", "--chdir", "/work",
                "--", "python3", "/work/driver.py", "/work/snippets.json",
            ]
        return run_session(codes, repo_dir, self.timeout, argv_for)
