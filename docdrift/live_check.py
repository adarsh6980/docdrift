"""Minimal live Token Factory check - run this where NEBIUS_API_KEY is set:

    python3 -m docdrift.live_check [model_id]

Lists available models containing "nemotron", then makes one tiny chat call
(about a dozen tokens) and prints the reply and token usage. The API key never
leaves your machine. Exit code 0 only if the live call succeeds."""
import json, os, sys, urllib.request, urllib.error

BASE = "https://api.tokenfactory.nebius.com/v1"


def _req(path, key, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method="POST" if body is not None else "GET",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        hint = {401: "key rejected - check NEBIUS_API_KEY", 404: "endpoint not found - API path may have changed"}.get(e.code, "")
        raise SystemExit(f"HTTP {e.code} on {path}. {hint}\n{e.read()[:300]!r}")
    except urllib.error.URLError as e:
        raise SystemExit(f"cannot reach {BASE}: {e.reason}")


def main():
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise SystemExit("NEBIUS_API_KEY is not set. Export it first (never paste it anywhere else).")

    model = sys.argv[1] if len(sys.argv) > 1 else None
    if not model:
        models = _req("/models", key)
        ids = [m.get("id", "") for m in models.get("data", [])]
        nem = [i for i in ids if "nemotron" in i.lower()]
        print(f"models containing 'nemotron': {len(nem)}")
        for i in nem:
            print("  " + i)
        if not nem:
            raise SystemExit(f"no nemotron models listed. First few available: {ids[:10]}")
        model = min(nem, key=len)  # shortest id is usually the smallest tier
        print(f"using model: {model}")

    out = _req("/chat/completions", key, {
        "model": model, "max_tokens": 16, "temperature": 0,
        "messages": [{"role": "user", "content": "Reply with exactly the word: ok"}]})
    reply = out["choices"][0]["message"]["content"]
    usage = out.get("usage", {})
    print(f"reply: {reply!r}")
    print(f"tokens: prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')}")
    print("LIVE CHECK PASSED")


if __name__ == "__main__":
    main()
