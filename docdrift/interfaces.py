from dataclasses import dataclass
from typing import Protocol

@dataclass
class RunResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""

class Runner(Protocol):
    def run(self, code: str, repo_dir: str) -> RunResult: ...

class Model(Protocol):
    def diagnose(self, code: str, error: str, repo_context: str) -> str: ...
    def propose_fix(self, code: str, error: str, repo_context: str) -> str: ...
