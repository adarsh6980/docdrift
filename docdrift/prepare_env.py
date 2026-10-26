"""Prepare a dependency venv for a benchmark repo WITHOUT trusting the repo.

Threat model: installing a repo (pip install ., setup.py, build hooks) runs
arbitrary code, so installation is isolated the same way snippet runs are -
but with network enabled, because fetching packages is the point.

- create_venv(): plain `python3 -m venv` on the host. No repo code runs.
- install_isolated(): pip executes INSIDE bwrap. Network is shared
  (--share-net) but the filesystem is bounded: the only writable host path is
  the venv directory itself, the repo (if given) is read-only, $HOME and the
  host environment (credentials, tokens, SSH keys) are not visible at all.
- Offline snippet runs then mount the venv's site-packages READ-ONLY via
  BwrapRunner(env_site_packages=...), with no network - so network-enabled
  fetching is fully separated from offline snippet execution.
"""
import glob, os, shutil, subprocess, sys, tempfile

try:
    import resource
except ImportError:
    resource = None


def create_venv(path):
    if os.path.exists(path):
        raise FileExistsError(path)
    subprocess.run([sys.executable, "-m", "venv", path], check=True)
    return path


def site_packages(venv):
    hits = glob.glob(os.path.join(venv, "lib", "python3*", "site-packages"))
    if not hits:
        raise RuntimeError(f"no site-packages under {venv}")
    return hits[0]


def _limits(cpu_seconds, mem_bytes):
    if resource is None:
        return None
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 5))
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    return apply


def install_isolated(venv, repo_dir=None, packages=(), timeout=300, cpu_seconds=240, mem_mb=2048):
    """Run pip inside bwrap: network on, filesystem bounded, env scrubbed.

    repo_dir: pip-install this repo - its setup.py/build hooks run in the
    sandbox, unable to see host credentials or other paths. The repo is
    copied on the host (plain file copy, no code execution) and the COPY is
    mounted writable for the build's egg-info artifacts; the original repo
    tree is never modified and never writable inside the sandbox.
    packages: PyPI requirement strings to install instead (or in addition).
    """
    if shutil.which("bwrap") is None:
        raise RuntimeError("bwrap not found; cannot isolate dependency installation")
    if not repo_dir and not packages:
        raise ValueError("nothing to install")
    argv = [
        "bwrap", "--unshare-all", "--share-net", "--die-with-parent", "--clearenv",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "HOME", "/tmp",
        "--setenv", "TMPDIR", "/tmp",
        "--setenv", "PIP_DISABLE_PIP_VERSION_CHECK", "1",
        "--setenv", "PIP_NO_INPUT", "1",
        "--setenv", "PYTHONNOUSERSITE", "1",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",
        # minimal devtmpfs (null/urandom/...) - pip and TLS need it
        "--dev", "/dev",
        # writable scratch first: the venv bind must come AFTER the /tmp tmpfs,
        # because a venv created under /tmp would otherwise be shadowed by it
        "--tmpfs", "/tmp",
        "--bind", os.path.abspath(venv), os.path.abspath(venv),
    ]
    build_copy = None
    if repo_dir:
        # setuptools-scm based builds need .git metadata; only include it when
        # the clone carries no credentials (https URL without a userinfo part,
        # no credential helper configured).
        git_cfg = os.path.join(os.path.abspath(repo_dir), ".git", "config")
        include_git = False
        if os.path.isfile(git_cfg):
            cfg = open(git_cfg, errors="replace").read()
            if "credential" not in cfg and ":@" not in cfg:
                include_git = True
        ignore = [] if include_git else [".git"]
        build_copy = tempfile.mkdtemp(prefix="docdrift-build-")
        shutil.rmtree(build_copy)
        shutil.copytree(os.path.abspath(repo_dir), build_copy,
                        ignore=shutil.ignore_patterns("docdrift-env.json", *ignore))
        argv += ["--bind", build_copy, "/build"]
    argv += ["--", os.path.join(os.path.abspath(venv), "bin", "python"), "-m", "pip", "install"]
    if repo_dir:
        argv.append("/build")
    argv += list(packages)
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           preexec_fn=_limits(cpu_seconds, mem_mb * 1024 * 1024))
        return r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"
    finally:
        if build_copy:
            shutil.rmtree(build_copy, ignore_errors=True)
