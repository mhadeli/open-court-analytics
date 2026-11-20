"""Render reports/court_data_brief.qmd into a clean self-contained HTML brief
(useful when Quarto CLI is not installed locally; `quarto render` works natively too).
"""

from __future__ import annotations

import base64
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_HTML = PROJECT_ROOT / "reports" / "court_data_brief.html"


def img_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main() -> None:
    km_uri = img_data_uri(PROJECT_ROOT / "outputs" / "km_curves.png")
    map_uri = img_data_uri(PROJECT_ROOT / "outputs" / "county_bottlenecks_map.png")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Maryland District Court Eviction Warrant Timelines &amp; Responsible AI Extraction</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 980px; margin: 2rem auto; padding: 0 1.25rem; color: #1f2933; line-height: 1.55; }}
  h1 {{ font-size: 1.75rem; color: #102a43; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #486581; font-size: 1.02rem; margin-bottom: 1.5rem; }}
  h2 {{ font-size: 1.25rem; color: #1b4965; border-bottom: 1px solid #d9e2ec; padding-bottom: 0.3rem; margin-top: 2rem; }}
  img {{ width: 100%; height: auto; border: 1px solid #d9e2ec; border-radius: 6px; margin: 0.75rem 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.93rem; }}
  th, td {{ border: 1px solid #d9e2ec; padding: 0.55rem 0.75rem; text-align: center; }}
  th {{ background: #f0f4f8; color: #102a43; }}
  td:first-child, th:first-child {{ text-align: left; }}
  .callout {{ background: #fffbeb; border-left: 4px solid #d97706; padding: 1rem 1.25rem; border-radius: 4px; margin-top: 1.5rem; }}
  .callout h3 {{ margin-top: 0; color: #92400e; font-size: 1.05rem; }}
  code {{ background: #f0f4f8; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.88rem; }}
</style>
</head>
<body>
  <h1>Maryland District Court Eviction Warrant Timelines &amp; Responsible AI Extraction</h1>
  <div class="subtitle">Analytical Brief — Open Court Analytics (Public Maryland Court Records &amp; CAP Benchmark)</div>

  <h2>Executive Summary</h2>
  <p>Using <strong>100,000 public Maryland District Court eviction event records</strong> (Apr–Sep 2026, covering <strong>51,948 valid warrant petitions</strong> across all 24 jurisdictions) and <strong>80 real Maryland state court opinions</strong>, this brief highlights three operational takeaways:</p>
  <ol>
    <li><strong>Ignoring open cases understates processing time by 41%.</strong> Naive closed-case medians report <strong>46.0 days</strong>, whereas Kaplan–Meier survival analysis right-censoring the <strong>27,542 open petitions (53.0%)</strong> yields a <strong>65.0-day</strong> median (+19 days).</li>
    <li><strong>Cross-county disparities reflect both operational pace and local clerk logging practices.</strong> Rural counties resolve closed petitions fastest (Allegany 12d, Cecil 15d) while urban dockets take longest (Anne Arundel 55d, Baltimore City 54d, Prince George's 53d). Crucially, Baltimore City records almost no <code>Cancelled</code> (61) or <code>Expired</code> (0) returns in this feed—making raw county clearance comparisons misleading without schema audits.</li>
    <li><strong>Hybrid rule + LLM extraction outperforms "LLM-only" pipelines.</strong> On 60 held-out court orders, regex matched or beat the LLM on structured docket IDs and standard decretals at <strong>$0.00 cost and 0.15 ms/doc</strong>, while <code>gemini-3.8-flash</code> delivered a <strong>+24.5 Macro-F1 lift</strong> on nuanced remand detection (<strong>0.983 vs. 0.738</strong>) with <strong>0.0% unsupported citations</strong>.</li>
  </ol>

  <h2>1. Case Processing Timelines &amp; Survivorship Bias</h2>
  <img src="{km_uri}" alt="Kaplan-Meier Survival Curves and Survivorship Bias" />
  <ul>
    <li>Kaplan–Meier cumulative resolution benchmarks across all 51,948 petitions: <strong>13.6% within 30 days</strong>, <strong>45.6% within 60 days</strong>, and <strong>66.2% within 90 days</strong>.</li>
    <li>County-stratified Cox models show <strong>Wrongful Detainer</strong> resolves ~16% faster (<code>HR = 1.16, 95% CI: 1.05–1.28</code>) while <strong>Public Housing FTPR</strong> resolves slower (<code>HR = 0.73, 95% CI: 0.60–0.89</code>).</li>
    <li>County-clustered fixed-effects logistic models (<code>n = 51,500</code>) find institutional batch e-filers have <strong>42% lower odds of executed eviction</strong> (<code>OR = 0.58, 95% CI: 0.52–0.65</code>), confirmed in a 60-day mature-cohort check (<code>OR = 0.60, n = 31,451</code>).</li>
  </ul>

  <h2>2. Geographic Variation Across All 24 Maryland Jurisdictions</h2>
  <img src="{map_uri}" alt="Maryland County Bottlenecks and Eviction Rate Map" />
  <p>Public aggregates enforce strict <strong>small-cell suppression (&lt; 10 cases)</strong>—automatically suppressing Garrett County's closed-case median (<code>n_closed = 7</code>) and 38 county-category cells. Suppressed tables are exported to <code>outputs/tableau/court_dashboard.hyper</code> and CSV fallbacks per <code>outputs/tableau/dashboard_spec.md</code>.</p>

  <h2>3. Responsible LLM Document Extraction Benchmark (n = 60 Held-Out Orders)</h2>
  <table>
    <thead>
      <tr><th>Method</th><th>Mean Precision</th><th>Mean Recall</th><th>Mean Macro-F1</th><th>Exact Accuracy</th><th>Median Latency</th><th>Cost / 1k Docs</th></tr>
    </thead>
    <tbody>
      <tr><td>Deterministic Rules (<code>regex</code>)</td><td><strong>0.906</strong></td><td>0.865</td><td><strong>0.871</strong></td><td>89.7%</td><td><strong>0.15 ms</strong></td><td><strong>$0.00</strong></td></tr>
      <tr><td>Classical NLP (<code>spaCy</code> + <code>TF-IDF</code>)</td><td>0.515</td><td>0.544</td><td>0.499</td><td>68.9%</td><td>80.9 ms</td><td><strong>$0.00</strong></td></tr>
      <tr><td>Structured LLM (<code>gemini-3.8-flash</code>)</td><td>0.891</td><td><strong>0.879</strong></td><td>0.862</td><td><strong>92.2%</strong></td><td>6,968 ms</td><td>$0.39</td></tr>
    </tbody>
  </table>

  <div class="callout">
    <h3>What This Data Can and Cannot Support</h3>
    <ul>
      <li><strong>Can support:</strong> Diagnosing survivorship bias in court time standards, identifying cross-county operational bottlenecks and clerk event-logging differences, and setting field-level rule vs. LLM deployment guardrails.</li>
      <li><strong>Cannot support:</strong> Causal claims about judicial bias, landlord behavior, or tenant outcomes. Public records omit tenant counsel status, rent arrears, informal settlements, and Baltimore City warrant cancellations (see <code>docs/LIMITATIONS_MEMO.md</code>).</li>
    </ul>
  </div>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"[ok] Rendered self-contained analytical brief -> {OUT_HTML}")


if __name__ == "__main__":
    main()
