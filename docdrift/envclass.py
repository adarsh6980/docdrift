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


import ast

_NAME_ERROR = re.compile(r"NameError: name '([^']+)' is not defined")

SERVICE_PATTERNS = (
    "Can't load plugin: sqlalchemy.dialects",
    "could not connect",
    "Connection refused",
    "ConnectionError",
    "OperationalError",
    "Temporary failure in name resolution",
    "Name or service not known",
)


def is_service_failure(stderr):
    """Snippet needs an external service (database, network API) to run."""
    err = stderr or ""
    return any(p in err for p in SERVICE_PATTERNS)


def name_error_name(stderr):
    m = _NAME_ERROR.search(stderr or "")
    return m.group(1) if m else None


def assigned_names(code):
    """Names a snippet would bind: assignments, imports, defs, with/for targets."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
    return names


def is_cascade_failure(stderr, earlier_codes, earlier_failed):
    """NameError whose name an earlier FAILED snippet in the same file would
    have bound. Prose-defined names (no code assigns them) do NOT match."""
    name = name_error_name(stderr)
    if name is None:
        return False
    for i in earlier_failed:
        if i < len(earlier_codes) and name in assigned_names(earlier_codes[i]):
            return True
    return False
