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



    def test_offline_banner_visible_on_mock_run(self):
        report = {"repos": [{"repo": "/tmp/x", "evaluated": [], "environment_failures": [],
                             "service_failures": [], "cascade_failures": []}],
                  "model": {"provider": "mock-offline"},
                  "model_tokens": {"prompt": None, "completion": None, "calls": 4}}
        page = render(report)
        self.assertIn("Offline dry run (MockModel)", page)
        self.assertIn("designed to run on Nebius Token Factory", page)
        self.assertNotIn(">Live run.<", page)

    def test_live_banner_on_measured_run(self):
        report = {"repos": [{"repo": "/tmp/x", "evaluated": [], "environment_failures": [],
                             "service_failures": [], "cascade_failures": []}],
                  "model": {"provider": "nebius-token-factory", "model_id": "nvidia/nemotron-3-nano",
                            "successful_calls": 3},
                  "model_tokens": {"prompt": 12, "completion": 4, "calls": 2}}
        page = render(report)
        self.assertIn("Live run", page)
        self.assertIn("ran live on Nebius Token Factory", page)
        self.assertIn("nvidia/nemotron-3-nano", page)
        self.assertNotIn("Offline dry run", page)

    def test_nonnull_token_counts_without_provider_are_not_live(self):
        # Mock or hand-edited token counts must not create live evidence.
        report = {"repos": [{"repo": "/tmp/x", "evaluated": [], "environment_failures": [],
                             "service_failures": [], "cascade_failures": []}],
                  "model": {"provider": "mock-offline"},
                  "model_tokens": {"prompt": 999, "completion": 999, "calls": 9}}
        page = render(report)
        self.assertIn("Offline dry run (MockModel)", page)
        self.assertNotIn("Live run", page)



    def test_configured_but_zero_successful_calls_is_not_live(self):
        # A constructed Token Factory client with no successful generation
        # this run must render as unverified, never as Live.
        report = {"repos": [{"repo": "/tmp/x", "evaluated": [], "environment_failures": [],
                             "service_failures": [], "cascade_failures": []}],
                  "model": {"provider": "nebius-token-factory", "model_id": "nvidia/nemotron-3-nano",
                            "successful_calls": 0},
                  "model_tokens": {"prompt": 0, "completion": 0, "calls": 0}}
        page = render(report)
        self.assertIn("Live integration unverified", page)
        self.assertNotIn("<b>Live run.</b>", page)
        self.assertNotIn("Offline dry run", page)

if __name__ == "__main__":
    unittest.main()
