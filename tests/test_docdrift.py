import os, unittest
from docdrift.extract import extract_snippets
from docdrift.runners import LocalFixtureRunner
from docdrift.mock_model import MockModel
from docdrift.pipeline import scan_repo
from docdrift.benchmark import score, load_truth

FX = os.path.join(os.path.dirname(__file__), "..", "benchmark", "fixtures")
def repo(n): return os.path.join(FX, n)

class T(unittest.TestCase):
    def test_extract(self):
        s = extract_snippets("a.md", "x\n```python\nprint(1)\n```\n```js\n1\n```\n")
        self.assertEqual(len(s), 1); self.assertEqual(s[0].line, 3)
    def test_no_false_alarm(self):
        fs = scan_repo(repo("ok_repo"), LocalFixtureRunner(), MockModel())
        self.assertTrue(all(f.status == "ok" for f in fs))
    def test_detects_stale_unfixed_without_fix(self):
        fs = scan_repo(repo("calc_repo"), LocalFixtureRunner(), MockModel())
        self.assertEqual([f.status for f in fs], ["ok", "stale_unfixed"])
    def test_fix_is_verified_by_rerun(self):
        bad = 'from fastcalc import add_numbers\nprint(add_numbers(1, 2))\n'
        good = 'from fastcalc import add\nprint(add(1, 2))\n'
        fs = scan_repo(repo("calc_repo"), LocalFixtureRunner(), MockModel({bad: good}))
        self.assertEqual(fs[1].status, "stale_fixed")
    def test_wrong_fix_not_counted(self):
        bad = 'from fastcalc import add_numbers\nprint(add_numbers(1, 2))\n'
        fs = scan_repo(repo("calc_repo"), LocalFixtureRunner(), MockModel({bad: "raise SystemExit(1)\n"}))
        self.assertEqual(fs[1].status, "stale_unfixed")
    def test_score_all_repos(self):
        for n in ("calc_repo", "greet_repo", "ok_repo"):
            fs = scan_repo(repo(n), LocalFixtureRunner(), MockModel())
            sc = score(fs, load_truth(repo(n)))
            self.assertEqual(sc["precision"], 1.0); self.assertEqual(sc["recall"], 1.0)

if __name__ == "__main__": unittest.main()
