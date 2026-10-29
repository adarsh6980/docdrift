import json, os, tempfile, unittest
from docdrift.constrained_runner import ConstrainedSubprocessRunner
from docdrift.pipeline import scan_repo, repo_context
from docdrift.mock_model import MockModel
from docdrift.benchmark_real import run_benchmark

FX = os.path.join(os.path.dirname(__file__), "..", "benchmark", "fixtures")
def repo(n): return os.path.join(FX, n)

class TestConstrainedSubprocess(unittest.TestCase):
    def test_ok_and_failing_code(self):
        r = ConstrainedSubprocessRunner()
        self.assertTrue(r.run("print('hi')", repo("ok_repo")).ok)
        bad = r.run("import nonexistent_lib_xyz", repo("ok_repo"))
        self.assertFalse(bad.ok); self.assertIn("nonexistent_lib_xyz", bad.stderr)
    def test_lib_on_path(self):
        r = ConstrainedSubprocessRunner()
        out = r.run("from shapes import area\nprint(area(2, 3))", repo("ok_repo"))
        self.assertTrue(out.ok, out.stderr)
    def test_timeout(self):
        r = ConstrainedSubprocessRunner(timeout=1)
        res = r.run("while True: pass", repo("ok_repo"))
        self.assertFalse(res.ok); self.assertIn("timeout", res.stderr)
    def test_env_is_scrubbed(self):
        os.environ["NEBIUS_API_KEY"] = "secret-marker-123"
        try:
            out = ConstrainedSubprocessRunner().run("import os; print(os.environ.get('NEBIUS_API_KEY'))", repo("ok_repo"))
        finally:
            del os.environ["NEBIUS_API_KEY"]
        self.assertTrue(out.ok)
        self.assertEqual(out.stdout.strip(), "None")
        self.assertNotIn("secret-marker-123", out.stdout)

class TestPipelineContext(unittest.TestCase):
    def test_context_lists_layout(self):
        c = repo_context(repo("calc_repo"))
        self.assertIn("top-level:", c); self.assertIn("lib", c)
    def test_scan_still_works_with_root_readme_glob(self):
        fs = scan_repo(repo("calc_repo"), ConstrainedSubprocessRunner(), MockModel())
        self.assertEqual([f.status for f in fs], ["ok", "stale_no_fix"])

class TestBenchmarkReal(unittest.TestCase):
    def test_offline_dry_run_report(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            try:
                rep = run_benchmark([repo("calc_repo"), repo("ok_repo")], MockModel(), runner=ConstrainedSubprocessRunner())
                self.assertTrue(os.path.exists("docdrift-benchmark-report.json"))
                self.assertEqual(rep["totals"]["evaluated"], 3)
                self.assertEqual(rep["totals"]["executed"], 3)
                self.assertEqual(rep["totals"]["stale_no_fix"], 1)  # bare MockModel produces no fix
                self.assertIn("score", rep["repos"][0])
            finally:
                os.chdir(cwd)
    def test_disjoint_totals_and_execution_mode_label(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            try:
                rep = run_benchmark([repo("calc_repo"), repo("ok_repo")], MockModel(), runner=ConstrainedSubprocessRunner())
                self.assertIn("assumption", rep["execution_mode"])
                t = rep["totals"]
                self.assertEqual(t["executed"],
                                 t["evaluated"] + t["environment_failures"]
                                 + t["service_failures"] + t["cascade_failures"])
            finally:
                os.chdir(cwd)

from docdrift import live_check
class TestLiveCheck(unittest.TestCase):
    def test_base_url_and_paths(self):
        self.assertEqual(live_check.BASE, "https://api.tokenfactory.nebius.com/v1")
    def test_http_error_is_loud(self):
        import urllib.error, io
        def boom(*a, **k):
            raise urllib.error.HTTPError("u", 401, "unauthorized", {}, io.BytesIO(b"bad key"))
        orig = urllib.request.urlopen
        urllib.request.urlopen = boom
        try:
            with self.assertRaises(SystemExit) as cm:
                live_check._req("/models", "k")
            self.assertIn("401", str(cm.exception))
        finally:
            urllib.request.urlopen = orig

if __name__ == "__main__":
    unittest.main()

from docdrift.bwrap_runner import BwrapRunner
class TestBwrapRunner(unittest.TestCase):
    def setUp(self):
        self.r = BwrapRunner()
    def test_ok_and_fail(self):
        self.assertTrue(self.r.run("print('x')", repo("ok_repo")).ok)
        self.assertFalse(self.r.run("raise ValueError('boom')", repo("ok_repo")).ok)
    def test_repo_lib_importable(self):
        out = self.r.run("from shapes import area\nprint(area(2, 3))", repo("ok_repo"))
        self.assertTrue(out.ok, out.stderr); self.assertIn("6", out.stdout)
    def test_no_network(self):
        code = "import urllib.request\ntry:\n urllib.request.urlopen('https://example.com', timeout=3)\n print('NET-OPEN')\nexcept Exception:\n print('NET-BLOCKED')"
        out = self.r.run(code, repo("ok_repo"))
        self.assertTrue(out.ok, out.stderr); self.assertIn("NET-BLOCKED", out.stdout)
    def test_home_and_secrets_not_visible(self):
        out = self.r.run("import os\nprint(sorted(os.listdir('/')))", repo("ok_repo"))
        self.assertTrue(out.ok, out.stderr)
        self.assertNotIn("home", out.stdout)
    def test_repo_is_read_only(self):
        out = self.r.run("open('/repo/README.md','a').write('x')", repo("ok_repo"))
        self.assertFalse(out.ok)

from docdrift.demo_page import render
class TestDemoPage(unittest.TestCase):
    def test_render_has_findings_and_escapes(self):
        rep = {"repos": [{"repo": "<b>x</b>", "findings": [
            {"file": "README.md", "index": 0, "line": 3, "status": "stale_fixed",
             "error": "NameError", "diagnosis": "d", "fixed_code": "print(1)\n"}],
            "score": {"precision": 1.0, "recall": 1.0, "verified_fixed": 1, "stale_total": 1}}],
            "model_tokens": {"calls": 2, "prompt": 100, "completion": 50}}
        out = render(rep)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", out)      # escaped, not injected
        self.assertIn("stale fixed", out)
        self.assertIn("print(1)", out)
        self.assertIn("prompt tokens=100", out)
        self.assertIn("github.com/adarsh6980/docdrift", out)

from docdrift.extract import extract_snippets
class TestRstExtract(unittest.TestCase):
    def test_rst_code_block(self):
        text = "Intro\n\n.. code-block:: python\n\n   print(1)\n   print(2)\n\nOutro no indent\n"
        s = extract_snippets("README.rst", text)
        self.assertEqual(len(s), 1)
        self.assertIn("print(1)", s[0].code)
        self.assertNotIn("Outro", s[0].code)
    def test_mixed_md_and_rst(self):
        text = ".. code:: python\n\n   a = 1\n\n```python\nb = 2\n```\n"
        s = extract_snippets("README.rst", text)
        self.assertEqual(len(s), 2)
        self.assertIn("a = 1", s[0].code)   # sorted by position
        self.assertIn("b = 2", s[1].code)
    def test_rst_other_lang_skipped(self):
        s = extract_snippets("r.rst", ".. code-block:: javascript\n\n   x()\n")
        self.assertEqual(s, [])

class TestNormalize(unittest.TestCase):
    def test_dedent_deep_rst(self):
        text = ".. code-block:: python\n\n      p.defnoun(1)\n      p.defnoun(2)\n"
        s = extract_snippets("r.rst", text)
        self.assertEqual(s[0].code, "p.defnoun(1)\np.defnoun(2)\n")
    def test_doctest_conversion(self):
        text = "```python\n>>> rows[0]\n'x'\n>>> print(1)\n1\n```\n"
        s = extract_snippets("r.md", text)
        self.assertEqual(s[0].code, "rows[0]\nprint(1)\n")

class TestSessionState(unittest.TestCase):
    def test_state_carries_across_snippets(self):
        r = BwrapRunner()
        res = r.run_file(["rows = [1, 2, 3]\n", "print(rows[0])\n"], repo("ok_repo"))
        self.assertEqual(len(res), 2)
        self.assertTrue(res[0].ok, res[0].stderr)
        self.assertTrue(res[1].ok, res[1].stderr)
        self.assertIn("1", res[1].stdout)
    def test_late_failure_keeps_earlier_ok(self):
        res = BwrapRunner().run_file(["x = 1\n", "import nonexistent_xyz\n"], repo("ok_repo"))
        self.assertTrue(res[0].ok); self.assertFalse(res[1].ok)

class TestSessionEnvScrub(unittest.TestCase):
    def test_session_env_is_scrubbed(self):
        os.environ["NEBIUS_API_KEY"] = "secret-marker-456"
        try:
            res = ConstrainedSubprocessRunner().run_file(
                ["import os\nprint(os.environ.get('NEBIUS_API_KEY'))\n"], repo("ok_repo"))
        finally:
            del os.environ["NEBIUS_API_KEY"]
        self.assertTrue(res[0].ok, res[0].stderr)
        self.assertEqual(res[0].stdout.strip(), "None")
        self.assertNotIn("secret-marker-456", res[0].stdout)
