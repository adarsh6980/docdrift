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


from docdrift.nemotron import NemotronModel
class TestClient(unittest.TestCase):
    def fake(self, url, headers, body):
        self.seen = (headers, body)
        return {"choices": [{"message": {"content": "x\n```python\nprint(2)\n```"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}
    def test_parses_fix_and_counts_tokens(self):
        m = NemotronModel("model-x", api_key="k", transport=self.fake)
        self.assertEqual(m.propose_fix("print(1)", "err", ""), "print(2)\n")
        self.assertEqual((m.prompt_tokens, m.completion_tokens), (5, 3))
        self.assertEqual(self.seen[1]["model"], "model-x")
    def test_no_key_fails_loudly(self):
        import os; os.environ.pop("NEBIUS_API_KEY", None)
        with self.assertRaises(RuntimeError): NemotronModel("m", transport=self.fake).diagnose("a", "b", "")

if __name__ == "__main__": unittest.main()
