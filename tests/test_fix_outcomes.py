import unittest
from types import SimpleNamespace

from docdrift.pipeline import scan_repo
from docdrift.nemotron import NemotronModel


class StubRunner:
    """Runs nothing real: fails originals, passes or fails reruns on demand."""
    def __init__(self, rerun_ok=True):
        self.rerun_ok = rerun_ok
        self.reruns = 0
    def run_file(self, codes, repo_dir):
        return [SimpleNamespace(ok=False, stderr="ImportError: cannot import name 'add_numbers'") for _ in codes]
    def run(self, code, repo_dir):
        self.reruns += 1
        return SimpleNamespace(ok=self.rerun_ok, stderr="" if self.rerun_ok else "still broken")


class StubModel:
    def __init__(self, fix):
        self.fix = fix
    def diagnose(self, code, error, ctx):
        return "stub diagnosis"
    def propose_fix(self, code, error, ctx):
        return self.fix


def make_repo(tmp):
    import os
    os.makedirs(os.path.join(tmp, "docs"), exist_ok=True)
    with open(os.path.join(tmp, "docs", "README.md"), "w") as f:
        f.write("```python\nfrom fastcalc import add_numbers\n```\n")
    return tmp


class FixOutcomeTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        make_repo(self.tmp)

    def test_good_fix_verified_by_rerun(self):
        runner = StubRunner(rerun_ok=True)
        fs = scan_repo(self.tmp, runner, StubModel("from fastcalc import add\n"))
        self.assertEqual(fs[0].status, "stale_fixed")
        self.assertEqual(fs[0].fixed_code, "from fastcalc import add\n")
        self.assertEqual(runner.reruns, 1)

    def test_bad_fix_fails_rerun(self):
        runner = StubRunner(rerun_ok=False)
        fs = scan_repo(self.tmp, runner, StubModel("from fastcalc import addd\n"))
        self.assertEqual(fs[0].status, "stale_unfixed")
        self.assertEqual(fs[0].fixed_code, "")
        self.assertEqual(runner.reruns, 1)

    def test_no_parseable_fix_is_generation_outcome_not_rerun(self):
        runner = StubRunner(rerun_ok=True)
        fs = scan_repo(self.tmp, runner, StubModel(None))
        self.assertEqual(fs[0].status, "stale_no_fix")
        self.assertEqual(fs[0].fixed_code, "")
        self.assertEqual(runner.reruns, 0)  # nothing reran - must not look like a fix evaluation

    def test_fix_identical_to_original_is_no_fix(self):
        runner = StubRunner(rerun_ok=True)
        original = "from fastcalc import add_numbers\n"
        fs = scan_repo(self.tmp, runner, StubModel(original))
        self.assertEqual(fs[0].status, "stale_no_fix")
        self.assertEqual(runner.reruns, 0)


class ProposeFixParsingTest(unittest.TestCase):
    def model_returning(self, text):
        def transport(url, headers, body):
            return {"choices": [{"message": {"content": text}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        return NemotronModel("m", api_key="k", transport=transport)

    def test_fenced_block_parsed(self):
        m = self.model_returning("Some reasoning...\n```python\nfrom x import y\n```\n")
        self.assertEqual(m.propose_fix("c", "e", "ctx"), "from x import y\n")

    def test_reasoning_only_returns_none(self):
        m = self.model_returning("Let me think about this step by step... (no code block)")
        self.assertIsNone(m.propose_fix("c", "e", "ctx"))

    def test_truncated_unterminated_fence_returns_none(self):
        m = self.model_returning("```python\nfrom x import")  # cut off mid-block
        self.assertIsNone(m.propose_fix("c", "e", "ctx"))

    def test_no_think_prefix_when_enabled(self):
        seen = {}
        def transport(url, headers, body):
            seen["system"] = body["messages"][0]["content"]
            return {"choices": [{"message": {"content": "```python\nx=1\n```"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        import os
        os.environ["NEBIUS_NO_THINK"] = "1"
        try:
            m = NemotronModel("m", api_key="k", transport=transport)
            m.propose_fix("c", "e", "ctx")
            self.assertTrue(seen["system"].startswith("/no_think"))
        finally:
            os.environ.pop("NEBIUS_NO_THINK", None)


if __name__ == "__main__":
    unittest.main()
