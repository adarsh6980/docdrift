"""Token Factory chat client (OpenAI-compatible). UNVERIFIED: written from docs, never called live.
Key comes from env NEBIUS_API_KEY. Model ids are config, not hardcoded guesses."""
import json, os, re, urllib.request

BASE_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"

def _http(url, headers, body, timeout=60):
    req = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

class NemotronModel:
    provider = "nebius-token-factory"

    def __init__(self, model_id, api_key=None, transport=_http, base_url=BASE_URL,
                 max_output_tokens=None, token_budget=None):
        self.model_id = model_id
        self.key = api_key or os.environ.get("NEBIUS_API_KEY")
        self.transport, self.base_url = transport, base_url
        self.calls = 0
        self.ok_calls = 0
        self.prompt_tokens = self.completion_tokens = 0
        # Enforceable spend bounds, not estimates. max_output_tokens is sent on
        # every request (reasoning models included; observed live: completion
        # was capped exactly at the requested value with reasoning inline).
        # token_budget is a hard run-wide limit accounted by RESERVATION: each
        # call reserves a conservative worst case up front (see _chat), and
        # spend is charged as the measured usage when returned, else the full
        # reservation - a response without usage can never reset spend. The
        # next call is refused before billing when it would cross the budget.
        self.max_output_tokens = int(max_output_tokens or os.environ.get("NEBIUS_MAX_OUTPUT_TOKENS", "2048"))
        self.token_budget = int(token_budget or os.environ.get("NEBIUS_TOKEN_BUDGET", "0")) or None
        self._spent = 0  # run-wide accounted spend in tokens (measured or reserved)
        # NVIDIA NIM documents the "/no_think" system prompt for Nemotron
        # reasoning models (concise responses, no extended chain-of-thought,
        # temperature=0 recommended). Not documented by Nebius for Token
        # Factory, so it stays opt-in via NEBIUS_NO_THINK=1 and its effect
        # must be verified from measured completion tokens on a live call.
        self.no_think = os.environ.get("NEBIUS_NO_THINK", "").lower() in ("1", "true", "yes")

    def _chat(self, system, user):
        if not self.key:
            raise RuntimeError("NEBIUS_API_KEY not set")
        # Conservative reservation: a BPE token spans at least one byte, so the
        # UTF-8 byte length of all message content is a true upper bound on
        # content tokens; +128 covers chat-template/role/special-token
        # overhead with wide margin; + the full requested output cap.
        if self.no_think:
            system = "/no_think\n" + system
        reserved = (len(system.encode("utf-8")) + len(user.encode("utf-8"))
                    + 128 + self.max_output_tokens)
        if self.token_budget is not None and self._spent + reserved > self.token_budget:
            raise RuntimeError(f"token budget {self.token_budget} would be exceeded "
                               f"(accounted {self._spent}, this call reserves {reserved}); refused before any billable call")
        body = {"model": self.model_id, "temperature": 0, "max_tokens": self.max_output_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        out = self.transport(self.base_url, {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}, body)
        self.calls += 1
        u = out.get("usage") or {}
        measured = u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
        if u.get("completion_tokens") is not None and u["completion_tokens"] > self.max_output_tokens:
            raise RuntimeError(f"provider returned {u['completion_tokens']} completion tokens, above the "
                               f"requested cap {self.max_output_tokens}; aborting run - cap not honored")
        self._spent += measured if measured > 0 else reserved
        self.prompt_tokens += u.get("prompt_tokens", 0)
        self.completion_tokens += u.get("completion_tokens", 0)
        content = out["choices"][0]["message"]["content"]
        self.ok_calls += 1  # incremented only after a response parsed successfully
        return content

    def diagnose(self, code, error, repo_context):
        return self._chat("You debug stale documentation snippets. Answer in one sentence: why does this snippet fail against the current code?",
                          f"Snippet:\n{code}\nError:\n{error}\nContext:\n{repo_context}")

    def propose_fix(self, code, error, repo_context):
        """Return the model's fenced fix, or None when no complete ```python
        block is present (reasoning consumed the output cap, truncated or
        unfenced reply). None is a generation/format outcome, never a fix."""
        text = self._chat("Rewrite the Python snippet so it works with the current library. Output only one ```python block.",
                          f"Snippet:\n{code}\nError:\n{error}\nContext:\n{repo_context}")
        m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
        return m.group(1) if m else None
