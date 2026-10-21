"""Render a benchmark report as a self-contained static HTML demo page.

    python3 -m docdrift.demo_page [docdrift-benchmark-report.json] [-o demo.html]

The page is the candidate public demo URL artifact: what DocDrift found, which
fixes were verified by re-running, and what the model calls cost in tokens.
Hosting it anywhere public is a separate, user-approved step."""
import argparse, html, json

CSS = "body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}" \
      "table{border-collapse:collapse;width:100%;margin:1rem 0}td,th{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;font-size:.9rem}" \
      ".ok{color:#067a3f}.stale_fixed{color:#0b5cad}.stale_unfixed{color:#b3261e}code,pre{background:#f4f4f4;padding:.1rem .3rem;font-size:.85rem}" \
      "pre{padding:.6rem;overflow-x:auto}.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}"

def render(report, title="DocDrift demo"):
    rows = []
    for repo in report.get("repos", []):
        rows.append(f"<h2>{html.escape(repo['repo'])}</h2>")
        if "score" in repo:
            sc = repo["score"]
            rows.append(f"<p>precision {sc['precision']:.2f} - recall {sc['recall']:.2f} - "
                        f"verified fixes {sc['verified_fixed']} of {sc['stale_total']} stale</p>")
        rows.append("<table><tr><th>snippet</th><th>status</th><th>error</th><th>verified fix</th></tr>")
        for f in repo["findings"]:
            fix = f"<pre>{html.escape(f['fixed_code'])}</pre>" if f.get("fixed_code") else ""
            rows.append(f"<tr><td><code>{html.escape(f['file'])}#{f['index']}</code> (line {f['line']})</td>"
                        f"<td class='{f['status']}'>{f['status'].replace('_',' ')}</td>"
                        f"<td><code>{html.escape((f.get('error') or '')[:120])}</code></td><td>{fix}</td></tr>")
        rows.append("</table>")
    t = report.get("model_tokens", {})
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head><body>"
            f"<h1>{html.escape(title)}</h1>"
            f"<p>DocDrift finds doc code snippets that no longer match the code, proposes fixes, and re-runs "
            f"each fix. Only fixes that pass the re-run are shown as verified.</p>"
            + "".join(rows) +
            f"<div class='card'><b>Model usage</b>: calls={t.get('calls')}, "
            f"prompt tokens={t.get('prompt')}, completion tokens={t.get('completion')}</div>"
            f"<p><a href='https://github.com/adarsh6980/docdrift'>Source code</a> - built on Nebius Token Factory "
            f"with NVIDIA Nemotron open models.</p></body></html>")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?", default="docdrift-benchmark-report.json")
    ap.add_argument("-o", "--out", default="demo.html")
    args = ap.parse_args()
    with open(args.report) as f:
        report = json.load(f)
    with open(args.out, "w") as f:
        f.write(render(report))
    print(f"wrote {args.out}")

if __name__ == "__main__":
    main()
