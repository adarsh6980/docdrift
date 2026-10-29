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

    def __init__(self, model_id, api_key=None, transport=_http, base_url=BASE_URL):
        self.model_id = model_id
        self.key = api_key or os.environ.get("NEBIUS_API_KEY")
        self.transport, self.base_url = transport, base_url
        self.calls = 0
        self.ok_calls = 0
        self.prompt_tokens = self.completion_tokens = 0

    def _chat(self, system, user):
        if not self.key:
            raise RuntimeError("NEBIUS_API_KEY not set")
        body = {"model": self.model_id, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        out = self.transport(self.base_url, {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}, body)
        self.calls += 1
        u = out.get("usage", {})
        self.prompt_tokens += u.get("prompt_tokens", 0)
        self.completion_tokens += u.get("completion_tokens", 0)
        content = out["choices"][0]["message"]["content"]
        self.ok_calls += 1  # incremented only after a response parsed successfully
        return content

    def diagnose(self, code, error, repo_context):
        return self._chat("You debug stale documentation snippets. Answer in one sentence: why does this snippet fail against the current code?",
                          f"Snippet:\n{code}\nError:\n{error}\nContext:\n{repo_context}")

    def propose_fix(self, code, error, repo_context):
        text = self._chat("Rewrite the Python snippet so it works with the current library. Output only one ```python block.",
                          f"Snippet:\n{code}\nError:\n{error}\nContext:\n{repo_context}")
        m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
        return m.group(1) if m else code
