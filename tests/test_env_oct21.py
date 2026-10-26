import json, os, shutil, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docdrift.envclass import missing_module, module_in_repo, is_environment_failure
from docdrift.bwrap_runner import BwrapRunner


class EnvClassTest(unittest.TestCase):
    def test_missing_module_parse(self):
        err = "Traceback...\nModuleNotFoundError: No module named 'jaraco.context'\n"
        self.assertEqual(missing_module(err), "jaraco.context")
        self.assertIsNone(missing_module("NameError: name 'p' is not defined"))

    def test_module_in_repo(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "calc"))
            self.assertTrue(module_in_repo("calc.helpers", d))
            self.assertFalse(module_in_repo("tablib", d))

    def test_environment_vs_stale(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "calc"))
            # third-party dep absent from repo tree -> environment, excluded
            self.assertTrue(is_environment_failure("ModuleNotFoundError: No module named 'tablib'", d))
            # repo's own submodule missing -> genuine stale-doc candidate
            self.assertFalse(is_environment_failure("ModuleNotFoundError: No module named 'calc.helpers'", d))
            self.assertFalse(is_environment_failure("SyntaxError: invalid syntax", d))


class BenchmarkExclusionTest(unittest.TestCase):
    def test_environment_failures_excluded_from_stale_counts(self):
        from docdrift.benchmark_real import run_benchmark
        from docdrift.mock_model import MockModel
        from docdrift.constrained_runner import ConstrainedSubprocessRunner
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "README.md"), "w") as f:
                f.write('```python\nimport totally_absent_dep_xyz\n```\n'
                        '```python\nraise ValueError("real bug")\n```\n')
            cwd = os.getcwd()
            os.chdir(d)
            try:
                rep = run_benchmark([d], MockModel(), runner=ConstrainedSubprocessRunner())
            finally:
                os.chdir(cwd)
            t = rep["totals"]
            self.assertEqual(t["environment_failures"], 1)
            self.assertEqual(t["snippets"], 1)  # only the real finding counts
            self.assertEqual(t["stale_unfixed"], 1)
            self.assertEqual(len(rep["repos"][0]["environment_failures"]), 1)


class PreparedVenvTest(unittest.TestCase):
    def test_isolated_install_and_offline_import(self):
        from docdrift.prepare_env import create_venv, install_isolated, site_packages
        base = tempfile.mkdtemp(prefix="docdrift-venvtest-")
        self.addCleanup(shutil.rmtree, base, True)
        venv = os.path.join(base, "venv")
        create_venv(venv)
        ok, log = install_isolated(venv, packages=["six==1.16.0"], timeout=180)
        if not ok:
            self.skipTest("network/pip unavailable in this environment: " + log[-200:])
        sp = site_packages(venv)
        self.assertTrue(os.path.isfile(os.path.join(sp, "six.py")))
        runner = BwrapRunner(env_site_packages=sp)
        r = runner.run("import six; print(six.__version__)", base)
        self.assertTrue(r.ok, r.stderr[-300:])
        self.assertIn("1.16.0", r.stdout)
        # the mounted venv must be read-only inside the offline run
        r2 = runner.run("open('/env-lib/evil.py','w').write('x')", base)
        self.assertFalse(r2.ok)


if __name__ == "__main__":
    unittest.main()


class ServiceCascadeTest(unittest.TestCase):
    def test_service_failure(self):
        from docdrift.envclass import is_service_failure
        self.assertTrue(is_service_failure(
            "sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres"))
        self.assertTrue(is_service_failure("psycopg2.OperationalError: could not connect to server"))
        self.assertFalse(is_service_failure("NameError: name 'rows' is not defined"))

    def test_cascade_only_when_earlier_failed_snippet_binds_name(self):
        from docdrift.envclass import is_cascade_failure
        codes = ["import records\nrows = db.query('select 1')", "print(rows)", "print(N)"]
        err = "NameError: name 'rows' is not defined"
        # earlier snippet 0 failed and assigns rows -> cascade
        self.assertTrue(is_cascade_failure(err, codes, [0]))
        # snippet 0 succeeded -> not cascade
        self.assertFalse(is_cascade_failure(err, codes, []))
        # N is never assigned in code (prose-defined) -> not cascade
        self.assertFalse(is_cascade_failure("NameError: name 'N' is not defined", codes, [0, 1]))

    def test_assigned_names(self):
        from docdrift.envclass import assigned_names
        self.assertEqual(assigned_names("import os\nx, y = 1, 2\ndef f(): pass\n"), {"os", "x", "y", "f"})
        self.assertEqual(assigned_names("not python ((("), set())
