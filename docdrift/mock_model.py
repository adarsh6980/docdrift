class MockModel:
    provider = "mock-offline"

    """Deterministic stand-in. Looks up canned fixes by exact snippet text. No network. Not Nemotron."""
    def __init__(self, fixes=None):
        self.fixes = fixes or {}
        self.calls = 0
    def diagnose(self, code, error, repo_context):
        self.calls += 1
        last = error.strip().splitlines()[-1] if error.strip() else "unknown"
        return f"mock-diagnosis: {last}"
    def propose_fix(self, code, error, repo_context):
        self.calls += 1
        return self.fixes.get(code, code)
