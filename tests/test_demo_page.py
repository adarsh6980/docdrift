import unittest

from docdrift.demo_page import render


class DemoPageRenderTest(unittest.TestCase):
    def test_renders_disjoint_report_schema(self):
        report = {
            "execution_mode": "repo-wide shared state in reading order",
            "repos": [{
                "repo": "/tmp/example",
                "venv": None,
                "evaluated": [
                    {"file": "README.md", "index": 0, "line": 4, "status": "ok",
                     "error": "", "diagnosis": "", "fixed_code": ""},
                    {"file": "README.md", "index": 1, "line": 9, "status": "stale_fixed",
                     "error": "ImportError: no add_numbers", "diagnosis": "renamed",
                     "fixed_code": "from fastcalc import add\n"},
                ],
                "environment_failures": [
                    {"file": "docs/a.md", "index": 0, "line": 3, "error": "ModuleNotFoundError: requests"}
                ],
                "service_failures": [
                    {"file": "docs/b.md", "index": 0, "line": 7, "error": "Connection refused"}
                ],
                "cascade_failures": [
                    {"file": "docs/b.md", "index": 1, "line": 11, "error": "NameError: name 'db'"}
                ],
                "score": {"precision": 1.0, "recall": 1.0, "verified_fixed": 1, "stale_total": 1},
            }],
            "totals": {"executed": 5, "evaluated": 2},
            "model_tokens": {"prompt": 10, "completion": 5, "calls": 2},
        }
        page = render(report)
        for needle in ("README.md#0", "stale fixed", "environment", "service", "cascade",
                       "from fastcalc import add", "prompt tokens=10"):
            self.assertIn(needle, page)
        # classified failures must not be presented as stale statuses
        self.assertNotIn("class='stale_unfixed'", page)

    def test_renders_legacy_findings_schema(self):
        report = {"repos": [{"repo": "/tmp/old", "findings": [
            {"file": "README.md", "index": 0, "line": 2, "status": "ok", "error": "", "fixed_code": ""}]}],
            "model_tokens": {"calls": 0, "prompt": None, "completion": None}}
        self.assertIn("README.md#0", render(report))


if __name__ == "__main__":
    unittest.main()
