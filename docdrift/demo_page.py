"""Render a benchmark report as a self-contained static HTML demo page.

    python3 -m docdrift.demo_page [docdrift-benchmark-report.json] [-o demo.html]

The page is the candidate public demo URL artifact: what DocDrift found, which
fixes were verified by re-running, and what the model calls cost in tokens.
Hosting it anywhere public is a separate, user-approved step."""
import argparse, html, json, os

CSS = "body{font-family:system-ui,sans-serif;max-width:1150px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}" \
      "table{border-collapse:collapse;width:100%;margin:1rem 0}td,th{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;font-size:.9rem;vertical-align:top}" \
      ".ok{color:#067a3f}.stale_fixed{color:#0b5cad}.stale_unfixed{color:#b3261e}.stale_no_fix{color:#b45309}" \
      ".environment,.service,.cascade{color:#666}code,pre{background:#f4f4f4;padding:.1rem .3rem;font-size:.85rem}" \
      "pre{padding:.6rem;overflow-x:auto;white-space:pre-wrap;word-break:break-word;margin:.2rem 0}" \
      "details{margin:.1rem 0}details>summary{cursor:pointer;color:#555;font-size:.85rem}" \
      "details[open]>summary{margin-bottom:.3rem}" \
      ".card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}"

def render(report, title="DocDrift demo"):
    rows = []
    n_repos = len(report.get("repos", []))
    n_exec = (report.get("totals") or {}).get("executed", 0)
    for repo in report.get("repos", []):
        # Display a clean repo name; absolute local paths add nothing and leak layout.
        rows.append(f"<h2>{html.escape(os.path.basename(repo['repo'].rstrip('/')) or repo['repo'])}</h2>")
        if "score" in repo:
            sc = repo["score"]
            rows.append(f"<p>precision {sc['precision']:.2f} - recall {sc['recall']:.2f} - "
                        f"verified fixes {sc['verified_fixed']} of {sc['stale_total']} stale</p>")
        rows.append("<table><tr><th>snippet</th><th>status</th><th>original code</th><th>error</th><th>fix evidence</th></tr>")
        # New disjoint report schema: evaluated findings carry full detail; the
        # environment/service/cascade lists carry brief entries and are shown
        # under their classification, never as stale-doc candidates.
        def expandable(text, summary=None):
            # Full evidence, readable: short text inline; long text in an
            # expandable block whose summary is the actionable line. Never
            # truncate: a cut-off error conceals the failure it reports.
            text = text or ""
            if not text:
                return ""
            esc = html.escape(text)
            if len(text) <= 160 and "\n" not in text:
                return f"<code>{esc}</code>"
            if summary is None:
                lines = [l for l in text.splitlines() if l.strip()]
                summary = lines[-1] if lines else "details"
            return (f"<details><summary>{html.escape(summary)}</summary>"
                    f"<pre>{esc}</pre></details>")

        def row(f, status):
            orig = f"<pre>{html.escape(f['code'])}</pre>" if f.get("code") else ""
            if f.get("fixed_code"):
                ev = f"<b>verified by rerun:</b>{expandable(f['fixed_code'], 'show verified fix')}"
            elif f.get("fix_attempt"):
                ev = (f"<b>rejected - rerun failed:</b>{expandable(f['fix_attempt'], 'show rejected fix')}"
                      f"{expandable(f.get('fix_error'), 'show rerun error that rejected it')}")
            elif status == "stale_no_fix":
                ev = "<i>model produced no parseable fix (generation/format outcome; nothing reran)</i>"
            else:
                ev = ""
            rows.append(f"<tr><td><code>{html.escape(f['file'])}#{f['index']}</code> (line {f['line']})</td>"
                        f"<td class='{status}'>{status.replace('_',' ')}</td>"
                        f"<td>{orig}</td>"
                        f"<td>{expandable(f.get('error'))}</td><td>{ev}</td></tr>")
        for f in repo.get("evaluated", repo.get("findings", [])):
            row(f, f.get("status", "ok"))
        for key, status in (("environment_failures", "environment"),
                            ("service_failures", "service"),
                            ("cascade_failures", "cascade")):
            for f in repo.get(key, []):
                row(f, status)
        rows.append("</table>")
    t = report.get("model_tokens", {})
    # Provenance is the recorded model execution in the report, never the
    # token fields: mock or supplied counts must not create live evidence.
    mp = report.get("model") or {}
    tf = mp.get("provider") == "nebius-token-factory" and bool(mp.get("model_id"))
    # Live requires recorded successful provider generations this run, not
    # merely a constructed client: zero-call or all-failed runs are not Live.
    live = tf and bool(mp.get("successful_calls"))
    if live:
        provenance = (f"<p style='border:1px solid #067a3f;color:#067a3f;padding:.6rem;border-radius:8px'>"
                      f"<b>Live run.</b> Model calls went through Nebius Token Factory "
                      f"(model <code>{html.escape(str(mp['model_id']))}</code>); token usage below is measured.</p>")
        footer = (f"ran live on Nebius Token Factory with the NVIDIA Nemotron open model "
                  f"<code>{html.escape(str(mp['model_id']))}</code>.")
    elif tf:
        provenance = (f"<p style='border:1px solid #b45309;color:#b45309;padding:.6rem;border-radius:8px'>"
                      f"<b>Live integration unverified.</b> Nebius Token Factory was configured "
                      f"(model <code>{html.escape(str(mp['model_id']))}</code>) but no successful model call "
                      f"completed in this run. Treat the live path as unverified.</p>")
        footer = (f"configured for Nebius Token Factory with NVIDIA Nemotron model "
                  f"<code>{html.escape(str(mp['model_id']))}</code>, but no successful live model call "
                  f"completed for this report.")
    else:
        provenance = ("<p style='border:1px solid #b3261e;color:#b3261e;padding:.6rem;border-radius:8px'>"
                      "<b>Offline dry run (MockModel).</b> No live Nemotron/Token Factory calls produced "
                      "this report; token fields are null. A live run replaces this banner with measured token usage.</p>")
        footer = ("designed to run on Nebius Token Factory with NVIDIA Nemotron open models; "
                  "this report was produced offline without live model calls.")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head><body>"
            f"<h1>{html.escape(title)}</h1>"
            f"<p>DocDrift finds doc code snippets that no longer match the code, proposes fixes, and re-runs "
            f"each fix. Only fixes that pass the re-run are shown as verified.</p>"
            f"<p><b>Scope:</b> {n_repos} synthetic seeded fixture repos, {n_exec} snippets executed. "
            f"Fixtures exist to demonstrate the pipeline end to end; scores on them are not a measure "
            f"of real-world performance. A real open-source-repo benchmark is separate future work.</p>"
            + provenance + "".join(rows) +
            f"<div class='card'><b>Model usage</b>: calls={t.get('calls')}, "
            f"prompt tokens={t.get('prompt')}, completion tokens={t.get('completion')}</div>"
            f"<p><a href='https://github.com/adarsh6980/docdrift'>Source code</a> - {footer}</p></body></html>")

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
