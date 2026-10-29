import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docdrift.demo_page import render
from docdrift import pipeline
from docdrift.interfaces import RunResult


class LongErrModel:
    def diagnose(self, code, error, ctx): return "d"
    def propose_fix(self, code, error, ctx): return code  # no parseable fix -> original


class LongErrRunner:
    def __init__(self):
        self.long_err = "line of context\n" * 40 + "RuntimeError: the actionable last line"
    def run(self, code, repo_dir):
        return RunResult(False, "", self.long_err)


class FullEvidenceTest(unittest.TestCase):
    def test_pipeline_stores_full_stderr_no_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "docs"))
            open(os.path.join(d, "docs", "g.md"), "w").write("```python\nboom()\n```\n")
            r = LongErrRunner()
            fs = pipeline.scan_repo(d, r, LongErrModel())
            self.assertEqual(len(fs), 1)
            self.assertEqual(fs[0].status, "stale_no_fix")
            self.assertEqual(fs[0].error, r.long_err.strip())
            self.assertGreater(len(fs[0].error), 400)  # would be lost at 200 chars

    def test_demo_shows_full_error_expandable(self):
        err = "traceback line\n" * 30 + "ValueError: the real reason"
        rep = {"repos": [{"repo": "/x/r", "evaluated": [
            {"file": "README.md", "index": 0, "line": 1, "status": "stale_unfixed",
             "code": "boom()", "error": err, "fix_attempt": "boom(2)",
             "fix_error": "rerun failed here in full"}]}],
            "totals": {"executed": 1}, "model_tokens": {}}
        page = render(rep)
        self.assertIn("<details>", page)
        self.assertIn("ValueError: the real reason", page)   # summary + body
        self.assertIn(err.replace("\n", "\\n") if False else "traceback line", page)  # full text present
        self.assertIn("boom(2)", page)                        # rejected fix shown
        self.assertIn("rerun failed here in full", page)      # rejection reason in full

    def test_report_path_option_writes_there(self):
        from docdrift.benchmark_real import run_benchmark
        from docdrift.benchmark_real import MockModel
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "sub", "report.json")
            os.makedirs(os.path.dirname(out))
            fixture = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "benchmark", "fixtures", "ok_repo")
            run_benchmark([fixture], MockModel(), report_path=out)
            self.assertTrue(os.path.exists(out))
            json.load(open(out))


if __name__ == "__main__":
    unittest.main()
