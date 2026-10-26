"""Separate environment/setup failures from actual stale-doc findings.

A snippet failing with ModuleNotFoundError usually means the prepared
environment lacks a dependency - that is a setup failure, NOT evidence the
documentation is stale, and it must not inflate stale counts. Only when the
missing module should exist inside the repo itself (a top-level package or
module present in the repo tree is fine; a reference to one that is absent is
a genuine stale-doc candidate) do we count it as a finding.
"""
import os, re

_MOD_NOT_FOUND = re.compile(r"No module named '([^']+)'")


def missing_module(stderr):
    m = _MOD_NOT_FOUND.search(stderr or "")
    return m.group(1) if m else None


def module_in_repo(module, repo_dir):
    """True if the module's top level plausibly lives in the repo tree."""
    top = (module or "").split(".")[0]
    if not top:
        return False
    for base in (repo_dir, os.path.join(repo_dir, "src"), os.path.join(repo_dir, "lib")):
        if (os.path.isdir(os.path.join(base, top))
                or os.path.isfile(os.path.join(base, top + ".py"))):
            return True
    return False


def is_environment_failure(stderr, repo_dir):
    """ModuleNotFoundError for a module NOT in the repo = missing dependency."""
    mod = missing_module(stderr)
    if mod is None:
        return False
    return not module_in_repo(mod, repo_dir)
