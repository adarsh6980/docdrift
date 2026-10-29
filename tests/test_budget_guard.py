import os, unittest

from docdrift.nemotron import NemotronModel


def fake_transport(url, headers, body):
    return {"choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class BudgetGuardTest(unittest.TestCase):
    def test_per_call_output_cap_in_request(self):
        m = NemotronModel("m", api_key="k", transport=fake_transport, max_output_tokens=128)
        seen = {}
        def cap(url, headers, body):
            seen["max_tokens"] = body["max_tokens"]
            return fake_transport(url, headers, body)
        m.transport = cap
        m.diagnose("c", "e", "ctx")
        self.assertEqual(seen["max_tokens"], 128)

    def test_budget_refuses_before_billing(self):
        # reservation per diagnose call = utf8 bytes (~150) + 128 overhead + 100
        # output cap ~= 378. Budget 380: first call fits, second is refused.
        m = NemotronModel("m", api_key="k", transport=fake_transport,
                          max_output_tokens=100, token_budget=380)
        m.diagnose("ab", "cd", "ef")   # charged measured 15
        calls = m.calls
        with self.assertRaises(RuntimeError):
            m.diagnose("ab", "cd", "ef")
        self.assertEqual(m.calls, calls)

    def test_missing_usage_charges_full_reservation(self):
        # A response without usage must not reset spend: the reserved worst
        # case stands, so the next call is refused.
        def no_usage(url, headers, body):
            return {"choices": [{"message": {"content": "ok"}}]}
        m = NemotronModel("m", api_key="k", transport=no_usage,
                          max_output_tokens=100, token_budget=700)
        m.diagnose("ab", "cd", "ef")   # no usage -> charged ~378 reservation
        self.assertGreater(m._spent, 350)  # ~= bytes + 128 overhead + 100 cap
        with self.assertRaises(RuntimeError):
            m.diagnose("ab", "cd", "ef")  # 378 + ~378 > 700

    def test_cap_violation_aborts_run(self):
        def cheating(url, headers, body):
            return {"choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 5000}}
        m = NemotronModel("m", api_key="k", transport=cheating, max_output_tokens=100)
        with self.assertRaises(RuntimeError):
            m.diagnose("ab", "cd", "ef")

    def test_unbounded_by_default_only_without_env(self):
        os.environ.pop("NEBIUS_TOKEN_BUDGET", None)
        m = NemotronModel("m", api_key="k", transport=fake_transport)
        self.assertIsNone(m.token_budget)
        self.assertEqual(m.max_output_tokens, 2048)


if __name__ == "__main__":
    unittest.main()
