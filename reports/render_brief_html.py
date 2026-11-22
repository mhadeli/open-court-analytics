"""Build an interactive, multi-tab HTML dashboard & analytical brief from real pipeline outputs.

Output: docs/index.html (GitHub Pages entry point: Branch main -> /docs)

Tables, charts and KPIs are loaded from the Phase 1–3 CSV and PNG outputs.
The explanatory prose quotes figures from the Apr–Sep 2026 snapshot (cutoff 2026-09-30);
re-check it after re-fetching data with src/db/00_fetch_court_data.py.
Zero external CDN dependencies — works offline and on GitHub Pages.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TABLEAU_DIR = OUTPUTS_DIR / "tableau"
OUT_PAGES = PROJECT_ROOT / "docs" / "index.html"


def img_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to JSON-safe list of dicts (NaN -> None)."""
    clean = df.where(pd.notna(df), None)
    records = clean.to_dict(orient="records")
    # Ensure native Python types (avoid numpy bool/int64)
    out = []
    for r in records:
        row = {}
        for k, v in r.items():
            if v is None:
                row[k] = None
            elif hasattr(v, "item"):
                row[k] = v.item()
            else:
                row[k] = v
        out.append(row)
    return out


def main() -> None:
    qa_df = pd.read_csv(OUTPUTS_DIR / "qa_audit_summary.csv")
    ttd_df = pd.read_csv(OUTPUTS_DIR / "time_to_disposition_summary.csv")
    coef_df = pd.read_csv(OUTPUTS_DIR / "model_coefficients.csv")
    bench_df = pd.read_csv(OUTPUTS_DIR / "benchmark_metrics.csv")
    county_df = pd.read_csv(TABLEAU_DIR / "court_dashboard_county_overall.csv")
    monthly_df = pd.read_csv(TABLEAU_DIR / "court_dashboard_monthly.csv")

    # Keep substantive non-FE regression terms for clean UI display
    coef_clean = coef_df[
        ~coef_df["term"].str.startswith("cty_")
        & ~coef_df["term"].str.startswith("C(filing_month")
        & (coef_df["term"] != "Intercept")
    ].copy()
    coef_clean["term"] = (
        coef_clean["term"]
        .str.replace("C(case_category, Treatment(reference='Failure to Pay Rent'))[T.", "Category: ", regex=False)
        .str.replace("]", "", regex=False)
        .str.replace("cat_", "Category: ", regex=False)
        .str.replace("batch_efiler", "Institutional Batch E-Filer", regex=False)
    )

    payload = {
        "qa": df_to_records(qa_df),
        "ttd": df_to_records(ttd_df),
        "coefs": df_to_records(coef_clean),
        "bench": df_to_records(bench_df),
        "counties": df_to_records(county_df),
        "monthly": df_to_records(monthly_df[monthly_df["is_suppressed"] == False]),  # noqa: E712
    }

    km_uri = img_data_uri(OUTPUTS_DIR / "km_curves.png")
    map_uri = img_data_uri(OUTPUTS_DIR / "county_bottlenecks_map.png")
    payload_json = json.dumps(payload, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Open Court Analytics — Maryland Court Timelines &amp; Responsible AI Dashboard</title>
<style>
  :root {{
    --navy: #102a43;
    --slate: #1b4965;
    --teal: #2a9d8f;
    --amber: #d97706;
    --crimson: #b91c1c;
    --bg: #f8fafc;
    --card: #ffffff;
    --border: #d9e2ec;
    --muted: #486581;
    --text: #1f2933;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.55;
  }}
  header {{
    background: linear-gradient(135deg, var(--navy) 0%, var(--slate) 100%);
    color: #fff;
    padding: 1.75rem 1.5rem 0;
  }}
  .header-inner {{
    max-width: 1160px;
    margin: 0 auto;
  }}
  .header-top {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    padding-bottom: 1.25rem;
  }}
  header h1 {{
    margin: 0;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }}
  header p {{
    margin: 0.35rem 0 0;
    color: #bcccdc;
    font-size: 0.95rem;
  }}
  .header-links {{
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }}
  .btn-ghost {{
    color: #fff;
    text-decoration: none;
    border: 1px solid rgba(255,255,255,0.35);
    padding: 0.42rem 0.85rem;
    border-radius: 6px;
    font-size: 0.84rem;
    font-weight: 500;
    transition: background 0.15s;
  }}
  .btn-ghost:hover {{ background: rgba(255,255,255,0.14); }}
  nav.tabs {{
    display: flex;
    gap: 0.25rem;
    overflow-x: auto;
    border-bottom: 1px solid rgba(255,255,255,0.18);
  }}
  nav.tabs button {{
    background: transparent;
    border: none;
    color: #bcccdc;
    padding: 0.75rem 1.1rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
  }}
  nav.tabs button:hover {{ color: #fff; }}
  nav.tabs button.active {{
    color: #fff;
    border-bottom-color: #38bdf8;
  }}
  main {{
    max-width: 1160px;
    margin: 1.5rem auto 3rem;
    padding: 0 1.25rem;
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(195px, 1fr));
    gap: 0.9rem;
    margin-bottom: 1.4rem;
  }}
  .kpi {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.1rem;
    box-shadow: 0 1px 2px rgba(16,42,67,0.04);
  }}
  .kpi-label {{
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    font-weight: 600;
  }}
  .kpi-val {{
    font-size: 1.65rem;
    font-weight: 700;
    color: var(--navy);
    margin: 0.25rem 0 0.15rem;
  }}
  .kpi-sub {{
    font-size: 0.8rem;
    color: var(--muted);
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 2px rgba(16,42,67,0.04);
  }}
  .card h2 {{
    margin: 0 0 0.75rem;
    font-size: 1.15rem;
    color: var(--navy);
    border-bottom: 1px solid #edf2f7;
    padding-bottom: 0.45rem;
  }}
  .card h3 {{
    margin: 1rem 0 0.5rem;
    font-size: 0.98rem;
    color: var(--slate);
  }}
  .explainer {{
    margin: 0 0 0.85rem;
    font-size: 0.9rem;
    color: var(--muted);
  }}
  .caption {{
    margin: 0.55rem 0 0.25rem;
    font-size: 0.84rem;
    color: var(--muted);
    background: #f8fafc;
    border-left: 3px solid var(--slate);
    padding: 0.55rem 0.85rem;
    border-radius: 3px;
  }}
  .q-box {{
    background: #f0f9ff;
    border-left: 4px solid var(--slate);
    padding: 0.9rem 1.15rem;
    border-radius: 4px;
    margin-bottom: 1.15rem;
  }}
  .q-box h3 {{
    margin: 0 0 0.45rem;
    color: var(--navy);
    font-size: 0.96rem;
  }}
  .q-box ul {{
    margin: 0;
    padding-left: 1.2rem;
    font-size: 0.9rem;
  }}
  .method-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 0.85rem;
    margin-bottom: 1.15rem;
  }}
  .method-card {{
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    font-size: 0.86rem;
  }}
  .method-card strong {{
    display: block;
    color: var(--navy);
    margin-bottom: 0.25rem;
    font-size: 0.9rem;
  }}
  .viz-img {{
    width: 100%;
    height: auto;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
    display: block;
    margin: 0.5rem 0;
  }}
  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.9rem;
  }}
  .controls label {{
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--muted);
  }}
  .controls select, .controls input {{
    padding: 0.42rem 0.65rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 0.86rem;
    background: #fff;
    color: var(--text);
  }}
  .table-wrap {{
    overflow-x: auto;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.86rem;
  }}
  th, td {{
    padding: 0.55rem 0.7rem;
    border-bottom: 1px solid #e2e8f0;
    text-align: right;
  }}
  th:first-child, td:first-child, th.left, td.left {{ text-align: left; }}
  th {{
    background: #f1f5f9;
    color: var(--navy);
    font-weight: 600;
    white-space: nowrap;
  }}
  th.sortable {{ cursor: pointer; user-select: none; }}
  th.sortable:hover {{ background: #e2e8f0; }}
  tr:hover td {{ background: #f8fafc; }}
  .badge {{
    display: inline-block;
    padding: 0.15rem 0.52rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }}
  .b-green {{ background: #dcfce7; color: #166534; }}
  .b-yellow {{ background: #fef3c7; color: #92400e; }}
  .b-red {{ background: #fee2e2; color: #991b1b; }}
  .b-gray {{ background: #e2e8f0; color: #475569; }}
  .callout {{
    background: #fffbeb;
    border-left: 4px solid var(--amber);
    padding: 1rem 1.2rem;
    border-radius: 4px;
    margin-top: 1rem;
  }}
  .callout h3 {{ margin-top: 0; color: #92400e; }}
  .two-col {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.1rem;
  }}
  .chart-box {{
    width: 100%;
    overflow-x: auto;
  }}
  .legend {{
    display: flex;
    gap: 1.25rem;
    flex-wrap: wrap;
    font-size: 0.83rem;
    color: var(--muted);
    margin-bottom: 0.4rem;
  }}
  .legend span {{ display: inline-flex; align-items: center; gap: 0.35rem; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; display: inline-block; }}
  footer {{
    max-width: 1160px;
    margin: 0 auto 2rem;
    padding: 0 1.25rem;
    font-size: 0.8rem;
    color: var(--muted);
    border-top: 1px solid var(--border);
    padding-top: 1rem;
  }}
  code {{
    background: #edf2f7;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    font-size: 0.83rem;
  }}
</style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="header-top">
      <div>
        <h1>Open Court Analytics — Interactive Dashboard &amp; Brief</h1>
        <p>Maryland District Court Eviction Warrant Timelines (Apr–Sep 2026 snapshot, data cutoff Sep 30, 2026) &amp; Responsible LLM Document Extraction Benchmark</p>
      </div>
      <div class="header-links">
        <a class="btn-ghost" href="https://github.com/mhadeli/open-court-analytics" target="_blank" rel="noopener">GitHub Repo</a>
        <a class="btn-ghost" href="https://github.com/mhadeli/open-court-analytics/blob/main/docs/AI_EVALUATION_SCORECARD.md" target="_blank" rel="noopener">AI Scorecard</a>
        <a class="btn-ghost" href="https://github.com/mhadeli/open-court-analytics/blob/main/docs/LIMITATIONS_MEMO.md" target="_blank" rel="noopener">Limitations Memo</a>
      </div>
    </div>
    <nav class="tabs" role="tablist">
      <button class="active" data-tab="brief">1. Executive Brief</button>
      <button data-tab="timelines">2. Timelines &amp; Models</button>
      <button data-tab="counties">3. County Explorer &amp; Map</button>
      <button data-tab="ai">4. AI Benchmark &amp; Scorecard</button>
      <button data-tab="governance">5. Governance &amp; QA</button>
    </nav>
  </div>
</header>

<main>
  <!-- TAB 1: EXECUTIVE BRIEF -->
  <section id="tab-brief" class="tab-panel active">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="kpi-label">Valid Warrant Petitions</div>
        <div class="kpi-val">51,948</div>
        <div class="kpi-sub">All 24 MD jurisdictions (100k raw events)</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Censor-Adjusted Median</div>
        <div class="kpi-val">65.0 days</div>
        <div class="kpi-sub">vs. 46.0d naive closed median (+41% bias)</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Overall Clearance Rate</div>
        <div class="kpi-val">47.0%</div>
        <div class="kpi-sub">24,406 closed | 27,542 open (53.0%)</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Executed Eviction Rate</div>
        <div class="kpi-val">8.7%</div>
        <div class="kpi-sub">4,526 warrants returned evicted</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">LLM Unsupported Quotes</div>
        <div class="kpi-val">0.0%</div>
        <div class="kpi-sub">60 held-out MD court orders verified</div>
      </div>
    </div>

    <div class="card">
      <div class="q-box">
        <h3>What Questions Does This Dashboard Answer?</h3>
        <ul>
          <li><strong>Case Timelines:</strong> How long do housing and eviction cases actually take across Maryland—and why can simple averages be misleading?</li>
          <li><strong>County Differences:</strong> Where are cases moving fastest or slowest across Maryland's 24 jurisdictions, and how does local clerk record-keeping affect the numbers?</li>
          <li><strong>Responsible AI in Courts:</strong> Where can courts safely use AI to read legal orders, and where are simple rules or human review more reliable?</li>
        </ul>
      </div>

      <h2>Three Headline Findings (In Plain English)</h2>
      <ol>
        <li><strong>Counting only finished cases hides real wait times.</strong> More than half of eviction petitions (<strong>53%</strong>, or 27,542 cases) were still open at the cutoff date. Looking only at finished cases makes the typical wait look like <strong>46 days</strong>—but properly including open cases shows the real midpoint is <strong>65 days</strong> (nearly three weeks longer).</li>
        <li><strong>Counties vary widely—and local record-keeping matters.</strong> Rural counties close warrants much faster (Allegany <strong>12 days</strong>, Cecil <strong>15 days</strong>) than high-volume urban courts (Anne Arundel <strong>55 days</strong>, Baltimore City <strong>54 days</strong>, Prince George's <strong>53 days</strong>). Just as important, Baltimore City logs almost no <code>Cancelled</code> (61) or <code>Expired</code> (0) warrants in this public feed, so raw county clearance rates cannot be compared fairly without checking local clerk reporting practices.</li>
        <li><strong>Combining simple rules with AI beats using AI alone.</strong> Tested on <strong>60 real Maryland court orders</strong>, simple text rules were instant, free, and just as accurate for predictable items like case numbers and standard rulings. AI (<code>gemini-3.8-flash</code>) proved its value on trickier legal wording—like spotting whether a case was sent back for further court action—boosting accuracy by <strong>+24.5 F1 points</strong> with <strong>0% made-up quotes</strong>.</li>
      </ol>

      <div class="callout">
        <h3>What This Data Can and Cannot Support</h3>
        <ul>
          <li><strong>Can support:</strong> Measuring how much open cases distort court timelines, spotting county-level bottlenecks and record-keeping gaps, and deciding which document fields are safe to automate vs. review by staff.</li>
          <li><strong>Cannot support:</strong> Proving why a court or landlord acted a certain way. Public records do not include tenant legal representation, rent owed, private payment agreements, or Baltimore City's cancelled warrants.</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- TAB 2: TIMELINES & MODELS -->
  <section id="tab-timelines" class="tab-panel">
    <div class="card">
      <h2>Kaplan–Meier Time-to-Disposition &amp; Survivorship Bias</h2>
      <p class="explainer">
        <strong>What this measures:</strong> Because 53% of petitions in this window are still open, simply averaging finished cases leaves out the longest-running cases and makes courts look artificially fast (<em>survivorship bias</em>). <strong>Kaplan–Meier survival analysis</strong> fixes this by including both closed cases and still-open cases up to the September 30 cutoff date to estimate a realistic timeline.
      </p>
      <img class="viz-img" src="{km_uri}" alt="Kaplan-Meier Survival Curves and Survivorship Bias" />
      <div class="caption">
        <strong>How to read these two charts:</strong>
        <strong>Left (Panel A)</strong> tracks the share of cases still open as days pass—curves that drop faster mean cases close quicker, with dashed lines at 30, 60, and 90 days.
        <strong>Right (Panel B)</strong> compares the misleading closed-case median (gray) against the Kaplan–Meier adjusted median (dark blue); for Public Housing cases, 90% are still open, so the true midpoint has not even been reached yet.
      </div>
    </div>

    <div class="card">
      <h2>Survival Benchmarks by Cohort</h2>
      <p class="explainer">
        Summarizes petition counts, the share still open (right-censored), naive vs. adjusted median days, and what percentage of cases resolve within 30, 60, and 90 days—broken down by housing case type and filer type (large batch e-filers vs. standard filers).
      </p>
      <div class="controls">
        <label for="ttd-filter">Group Type:</label>
        <select id="ttd-filter">
          <option value="all">All Groups</option>
          <option value="overall">Overall</option>
          <option value="case_category">Case Category</option>
          <option value="filer_type">Filer Type</option>
        </select>
      </div>
      <div class="table-wrap">
        <table id="ttd-table">
          <thead>
            <tr>
              <th class="left">Cohort</th>
              <th>Petitions</th>
              <th>Closed</th>
              <th>Right-Censored %</th>
              <th>Naive Median (d)</th>
              <th>KM Median (d)</th>
              <th>30d Resolved %</th>
              <th>60d Resolved %</th>
              <th>90d Resolved %</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>Fixed-Effects Survival &amp; Clustered Logistic Regression Estimates (95% CIs)</h2>
      <p class="explainer">
        Tests how case type and filer type relate to <strong>closing speed</strong> (Cox model: Hazard Ratio above 1.0 = closes faster; below 1.0 = closes slower) and <strong>executed eviction likelihood</strong> (Logit model: Odds Ratio above 1.0 = higher odds of eviction; below 1.0 = lower odds), while controlling for county and month differences.
      </p>
      <div class="controls">
        <label for="model-filter">Model:</label>
        <select id="model-filter">
          <option value="all">All Models</option>
          <option value="cox_ph_time_to_disposition">Cox PH — Time to Disposition (County-Stratified)</option>
          <option value="logit_eviction_executed_full">Logit — Executed Eviction (Full Cohort, Clustered SEs)</option>
          <option value="logit_eviction_mature_60d_cohort">Logit — Executed Eviction (60d Mature Cohort Sensitivity)</option>
        </select>
      </div>
      <div class="table-wrap">
        <table id="coef-table">
          <thead>
            <tr>
              <th class="left">Model</th>
              <th class="left">Predictor (Ref: Failure to Pay Rent)</th>
              <th>HR / OR</th>
              <th>95% CI Lower</th>
              <th>95% CI Upper</th>
              <th>p-value</th>
              <th>N</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- TAB 3: COUNTY EXPLORER & MAP -->
  <section id="tab-counties" class="tab-panel">
    <div class="card">
      <h2>Maryland 24-Jurisdiction Choropleth Map (Small-Cell &lt;10 Suppressed)</h2>
      <p class="explainer">
        Compares all 23 Maryland counties plus Baltimore City side-by-side on typical time to resolve closed petitions (left) and the percentage of petitions that end in an executed eviction (right). Any count under 10, and any rate built from it, is hidden for privacy.
      </p>
      <img class="viz-img" src="{map_uri}" alt="Maryland County Bottlenecks and Eviction Rate Map" />
      <div class="caption">
        <strong>Map takeaway:</strong> Darker blue regions (Central and Capital urban courts) take longest to close petitions (~46–55 days), while darker red regions (smaller Western/rural counties) show higher executed-eviction shares. Hatched areas are hidden for privacy: Garrett County (far west) on both maps, and Kent and Queen Anne's on the eviction map, because those counts are under 10.
      </div>
    </div>

    <div class="card">
      <h2>Interactive County &amp; Region Explorer</h2>
      <p class="explainer">
        Filter by Maryland region or search for any jurisdiction below—the summary cards, monthly trend chart, and county breakdown table all update dynamically.
      </p>
      <div class="controls">
        <label for="region-filter">Region:</label>
        <select id="region-filter">
          <option value="ALL">All Maryland Regions (24)</option>
          <option value="Central">Central</option>
          <option value="Capital">Capital</option>
          <option value="Eastern Shore">Eastern Shore</option>
          <option value="Southern">Southern</option>
          <option value="Western">Western</option>
        </select>
        <label for="county-search">Search County:</label>
        <input id="county-search" type="text" placeholder="e.g., Baltimore, Garrett..." />
      </div>

      <div class="kpi-grid" id="filtered-kpis"></div>

      <h3>Monthly Filings vs. Dispositions vs. Executed Evictions (Filtered by Region)</h3>
      <p class="explainer">
        Tracks incoming eviction petitions each month alongside completed dispositions and executed evictions. Dispositions dip in August–September because recent filings have had less time to conclude before the September 30 extract cutoff. County-month counts under 10 are hidden for privacy, so these totals run slightly low.
      </p>
      <div class="legend">
        <span><i class="dot" style="background:#1b4965"></i>Filings</span>
        <span><i class="dot" style="background:#2a9d8f"></i>Dispositions</span>
        <span><i class="dot" style="background:#b91c1c"></i>Executed Evictions</span>
      </div>
      <div class="chart-box" id="monthly-svg-box"></div>

      <h3>Jurisdiction Breakdown (Click Column Headers to Sort)</h3>
      <p class="explainer">
        County-level case volume, clearance rate, executed eviction rate, closed-case median days, and share resolved within 60 days. Click any column header to sort; <code>&lt;10 supp.</code> tags indicate privacy-suppressed values.
      </p>
      <div class="table-wrap">
        <table id="county-table">
          <thead>
            <tr>
              <th class="left sortable" data-col="county_name">Jurisdiction</th>
              <th class="left sortable" data-col="region">Region</th>
              <th class="sortable" data-col="total_cases">Petitions</th>
              <th class="sortable" data-col="closed_cases">Closed</th>
              <th class="sortable" data-col="clearance_rate_pct">Clearance %</th>
              <th class="sortable" data-col="eviction_rate_pct">Eviction %</th>
              <th class="sortable" data-col="median_days_closed">Median Days</th>
              <th class="sortable" data-col="pct_disposed_within_60d">&le;60d %</th>
              <th class="sortable" data-col="batch_efiler_pct">Batch E-Filer %</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- TAB 4: AI BENCHMARK & SCORECARD -->
  <section id="tab-ai" class="tab-panel">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="kpi-label">Rules (Regex)</div>
        <div class="kpi-val">0.871 F1</div>
        <div class="kpi-sub">89.7% acc | 0.15 ms | $0.00 / 1k</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Classical NLP (spaCy/TF-IDF)</div>
        <div class="kpi-val">0.499 F1</div>
        <div class="kpi-sub">68.9% acc | 80.9 ms | $0.00 / 1k</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Gemini 3.8 Flash (Schema)</div>
        <div class="kpi-val">0.862 F1</div>
        <div class="kpi-sub">92.2% acc | 6,968 ms | $0.39 / 1k</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Remand Detection Lift</div>
        <div class="kpi-val">+24.5 F1</div>
        <div class="kpi-sub">LLM 0.983 vs. Rules 0.738</div>
      </div>
    </div>

    <div class="card">
      <h2>Three Document-Reading Approaches Compared</h2>
      <div class="method-grid">
        <div class="method-card">
          <strong>1. Deterministic Rules (Regex)</strong>
          Hand-written text patterns and keyword lookups (e.g., matching <code>No. 1332</code>). Instant and free—ideal for standardized fields, but misses varied or messy wording.
        </div>
        <div class="method-card">
          <strong>2. Classical NLP (spaCy + TF-IDF)</strong>
          Traditional lightweight machine learning trained on 20 labeled examples. Strong at spotting dollar entities, but struggles on multi-category legal text without large labeled datasets.
        </div>
        <div class="method-card">
          <strong>3. Structured LLM (Gemini 3.8 Flash)</strong>
          Modern AI constrained to a strict JSON form, told to answer <code>UNKNOWN</code> when unsure, and required to copy an exact supporting quote from the text so staff can verify every answer.
        </div>
      </div>

      <h2>Pre-Deployment AI Readiness Scorecard (Non-Technical Decision Matrix)</h2>
      <p class="explainer">
        A plain-language deployment guide for court administrators. <strong>Green</strong> fields can be automated safely with simple rules; <strong>Yellow</strong> fields benefit from AI assistance with clerk review; <strong>Red</strong> fields carry high financial/legal risk and should never be auto-posted without human sign-off.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="left">Status</th>
              <th class="left">Extraction Field</th>
              <th class="left">Recommended Engine</th>
              <th class="left">Operational Guidance</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="left"><span class="badge b-green">GREEN</span></td>
              <td class="left"><code>case_number</code></td>
              <td class="left">Deterministic Regex</td>
              <td class="left">0.950 F1 at 0.15 ms and $0.00. Add multi-docket regex to close the remaining 3% gap without LLM latency.</td>
            </tr>
            <tr>
              <td class="left"><span class="badge b-green">GREEN</span></td>
              <td class="left"><code>disposition_outcome</code></td>
              <td class="left">Deterministic Rules + LLM fallback</td>
              <td class="left">1.000 F1 on standardized appellate decretal lines. Route unstructured trial-court orders to Yellow review.</td>
            </tr>
            <tr>
              <td class="left"><span class="badge b-yellow">YELLOW</span></td>
              <td class="left"><code>remand_or_procedural_stay_flag</code></td>
              <td class="left">LLM (<code>UNKNOWN</code> + Quote Check)</td>
              <td class="left">0.983 F1 (2.3% OCR drop vs. 12.5% for rules). Ideal for human-in-the-loop triage with verbatim quote highlighting.</td>
            </tr>
            <tr>
              <td class="left"><span class="badge b-yellow">YELLOW</span></td>
              <td class="left"><code>case_category</code></td>
              <td class="left">LLM + Human Tie-Break Rules</td>
              <td class="left">0.744 F1 (76.7% acc). Real disputes straddle civil/property boundaries; suitable for draft tagging, not binding routing.</td>
            </tr>
            <tr>
              <td class="left"><span class="badge b-yellow">YELLOW</span></td>
              <td class="left"><code>self_represented_flag</code></td>
              <td class="left">Structured Counsel Parser + Clerk Check</td>
              <td class="left">LLMs can misread solo attorneys without firm names as <em>pro se</em>; cross-check against CMS attorney/bar tables.</td>
            </tr>
            <tr>
              <td class="left"><span class="badge b-red">RED</span></td>
              <td class="left"><code>monetary_judgment_amount</code></td>
              <td class="left">Do Not Automate Binding Entry</td>
              <td class="left">Rules dropped unit multipliers ($147M &rarr; $147); LLM abstained on 39% of real amounts. Assistive highlight only.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>Per-Field Extraction Benchmark (n = 60 Held-Out Maryland Orders)</h2>
      <p class="explainer">
        Detailed accuracy scores on 60 unseen Maryland court orders (44 with legacy scan/OCR noise). <strong>Macro-F1</strong> balances precision and recall (1.000 = perfect); <strong>OCR Drop</strong> shows accuracy loss on noisy scans vs. clean text; <strong>Unsupported</strong> measures how often the LLM cited a quote not found verbatim in the order (0.0% across all fields).
      </p>
      <div class="controls">
        <label for="method-filter">Method:</label>
        <select id="method-filter">
          <option value="all">All 3 Methods</option>
          <option value="rules">Deterministic Rules (regex)</option>
          <option value="classical_nlp">Classical NLP (spaCy + TF-IDF)</option>
          <option value="llm_gemini">Structured LLM (gemini-3.8-flash)</option>
        </select>
      </div>
      <div class="table-wrap">
        <table id="bench-table">
          <thead>
            <tr>
              <th class="left">Method</th>
              <th class="left">Field</th>
              <th>Precision</th>
              <th>Recall</th>
              <th>Macro-F1</th>
              <th>Exact Acc</th>
              <th>Abstain %</th>
              <th>OCR Drop</th>
              <th>Unsupported</th>
              <th>Latency (ms)</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- TAB 5: GOVERNANCE & QA -->
  <section id="tab-governance" class="tab-panel">
    <div class="two-col">
      <div class="card">
        <h2>Phase 1 Warehouse QA &amp; Privacy Audit</h2>
        <p class="explainer">
          Tracks every automated quality and privacy check run when loading 100,000 raw public court records into DuckDB—showing how incomplete early records and invalid dates are separated out before analysis, and how many small groups are suppressed for privacy.
        </p>
        <div class="table-wrap">
          <table id="qa-table">
            <thead>
              <tr>
                <th class="left">Audit Metric</th>
                <th>Count</th>
                <th class="left">Notes</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2>Local Clerk Logging Audit (Major Jurisdictions)</h2>
        <p class="explainer">
          Compares how Maryland's four largest jurisdictions record warrant outcomes in this public dataset. Notice Baltimore City logs almost no <code>Cancelled</code> or <code>Expired</code> warrants—proving why raw cross-county clearance comparisons must account for local record-keeping practices.
        </p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="left">Jurisdiction</th>
                <th>Evicted</th>
                <th>Cancelled</th>
                <th>Expired</th>
                <th>Pending</th>
              </tr>
            </thead>
            <tbody>
              <tr><td class="left"><strong>Baltimore County</strong></td><td>1,119</td><td>6,717</td><td>2,281</td><td>5,189</td></tr>
              <tr><td class="left"><strong>Montgomery County</strong></td><td>235</td><td>1,884</td><td>165</td><td>1,100</td></tr>
              <tr><td class="left"><strong>Prince George's County</strong></td><td>696</td><td>3,654</td><td>0</td><td>3,890</td></tr>
              <tr><td class="left"><strong>Baltimore City</strong></td><td>1,197</td><td>61</td><td>0</td><td>13,487</td></tr>
            </tbody>
          </table>
        </div>
        <h3>Privacy Controls Enforced in SQL</h3>
        <ul style="font-size:0.86rem; padding-left:1.2rem;">
          <li>Downstream scripts query only <code>v_analyst_cases</code> (salted SHA-256 <code>case_id_hash</code>, raw city &amp; 5-digit ZIP removed, coarsened to 3-digit <code>tenant_zip3</code>).</li>
          <li>Public county/monthly exports enforce strict <strong>small-cell suppression (&lt; 10 cases)</strong>: every published count under 10 is hidden, along with any rate that multiplies back to it. This removes 38 small county-category rows entirely and hides Garrett County's closed and eviction figures.</li>
          <li>Automated assertions in <code>build_warehouse.py</code> fail the build if any PII column or unsuppressed cell leaks.</li>
        </ul>
      </div>
    </div>
  </section>
</main>

<footer>
  <strong>Sources:</strong> District Court of Maryland Eviction Case Data (Maryland Open Data, <code>mvqb-b4hf</code>); Harvard Caselaw Access Project (<code>static.case.law/md-app/</code>); U.S. Census TIGER/Line 2023. All figures are descriptive operational analyses, not causal claims.
</footer>

<script>
const DATA = {payload_json};

// Tab navigation with URL hash persistence
const tabButtons = document.querySelectorAll('nav.tabs button');
const tabPanels = document.querySelectorAll('.tab-panel');
function activateTab(name) {{
  tabButtons.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  tabPanels.forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  history.replaceState(null, '', '#' + name);
}}
tabButtons.forEach(b => b.addEventListener('click', () => activateTab(b.dataset.tab)));
const initHash = location.hash.replace('#', '');
if (['brief','timelines','counties','ai','governance'].includes(initHash)) activateTab(initHash);

const fmtInt = v => (v === null || v === undefined) ? '<span class="badge b-gray">&lt;10 supp.</span>' : Number(v).toLocaleString();
const fmtNum = (v, d=1) => (v === null || v === undefined) ? '<span class="badge b-gray">&lt;10 supp.</span>' : Number(v).toFixed(d);
const fmtPct = (v, d=1) => (v === null || v === undefined) ? '<span class="badge b-gray">&lt;10 supp.</span>' : Number(v).toFixed(d) + '%';

// Tab 2: TTD table
function renderTTD() {{
  const f = document.getElementById('ttd-filter').value;
  const rows = DATA.ttd.filter(r => f === 'all' || r.group_type === f);
  document.querySelector('#ttd-table tbody').innerHTML = rows.map(r => `
    <tr>
      <td class="left"><strong>${{r.group_name}}</strong></td>
      <td>${{Number(r.n_total).toLocaleString()}}</td>
      <td>${{Number(r.n_closed).toLocaleString()}}</td>
      <td>${{Number(r.pct_right_censored).toFixed(1)}}%</td>
      <td>${{r.naive_closed_median_days !== null ? r.naive_closed_median_days.toFixed(1) : '—'}}</td>
      <td><strong>${{r.km_median_days !== null ? r.km_median_days.toFixed(1) : 'Not reached'}}</strong></td>
      <td>${{Number(r.km_pct_resolved_30d).toFixed(1)}}%</td>
      <td>${{Number(r.km_pct_resolved_60d).toFixed(1)}}%</td>
      <td>${{Number(r.km_pct_resolved_90d).toFixed(1)}}%</td>
    </tr>`).join('');
}}
document.getElementById('ttd-filter').addEventListener('change', renderTTD);
renderTTD();

// Tab 2: Regression coefficients table
function renderCoefs() {{
  const f = document.getElementById('model-filter').value;
  const labels = {{
    cox_ph_time_to_disposition: 'Cox PH (Time)',
    logit_eviction_executed_full: 'Logit (Full Cohort)',
    logit_eviction_mature_60d_cohort: 'Logit (60d Mature)'
  }};
  const rows = DATA.coefs.filter(r => f === 'all' || r.model === f);
  document.querySelector('#coef-table tbody').innerHTML = rows.map(r => `
    <tr>
      <td class="left">${{labels[r.model] || r.model}}</td>
      <td class="left">${{r.term}}</td>
      <td><strong>${{Number(r.ratio_hr_or).toFixed(3)}}</strong></td>
      <td>${{Number(r.ci_lower_95).toFixed(3)}}</td>
      <td>${{Number(r.ci_upper_95).toFixed(3)}}</td>
      <td>${{Number(r.p_value) < 0.001 ? '<0.001' : Number(r.p_value).toFixed(4)}}</td>
      <td>${{Number(r.n_obs).toLocaleString()}}</td>
    </tr>`).join('');
}}
document.getElementById('model-filter').addEventListener('change', renderCoefs);
renderCoefs();

// Tab 3: Interactive County Explorer + Monthly SVG Chart
let sortCol = 'total_cases';
let sortAsc = false;

function renderMonthlySVG(region) {{
  const box = document.getElementById('monthly-svg-box');
  const filtered = DATA.monthly.filter(r => region === 'ALL' || r.region === region);
  const byMonth = {{}};
  filtered.forEach(r => {{
    const m = String(r.month_start).slice(0, 7);
    if (!byMonth[m]) byMonth[m] = {{ month: m, filings: 0, disp: 0, evict: 0 }};
    byMonth[m].filings += Number(r.filings_count || 0);
    byMonth[m].disp += Number(r.dispositions_count || 0);
    byMonth[m].evict += Number(r.evictions_count || 0);
  }});
  const pts = Object.values(byMonth).sort((a,b) => a.month.localeCompare(b.month));
  if (!pts.length) {{ box.innerHTML = '<p style="color:#64748b">No unsuppressed monthly data for this selection.</p>'; return; }}

  const W = 820, H = 250, padL = 62, padR = 24, padT = 18, padB = 34;
  const maxY = Math.max(...pts.map(p => Math.max(p.filings, p.disp, p.evict)), 10) * 1.12;
  const x = i => padL + (pts.length === 1 ? (W - padL - padR) / 2 : i * (W - padL - padR) / (pts.length - 1));
  const y = v => H - padB - (v / maxY) * (H - padT - padB);
  const line = key => pts.map((p, i) => `${{i===0?'M':'L'}}${{x(i).toFixed(1)}},${{y(p[key]).toFixed(1)}}`).join(' ');

  let grid = '';
  for (let g = 0; g <= 4; g++) {{
    const val = (maxY * g) / 4;
    const yy = y(val).toFixed(1);
    grid += `<line x1="${{padL}}" y1="${{yy}}" x2="${{W-padR}}" y2="${{yy}}" stroke="#e2e8f0" stroke-width="1"/>`;
    grid += `<text x="${{padL-8}}" y="${{Number(yy)+4}}" text-anchor="end" font-size="11" fill="#64748b">${{Math.round(val).toLocaleString()}}</text>`;
  }}
  const xLabels = pts.map((p,i) => `<text x="${{x(i).toFixed(1)}}" y="${{H-10}}" text-anchor="middle" font-size="11" fill="#475569">${{p.month}}</text>`).join('');
  const circles = (key, color) => pts.map((p,i) => `<circle cx="${{x(i).toFixed(1)}}" cy="${{y(p[key]).toFixed(1)}}" r="4" fill="${{color}}"><title>${{p.month}}: ${{Math.round(p[key]).toLocaleString()}}</title></circle>`).join('');

  box.innerHTML = `
    <svg viewBox="0 0 ${{W}} ${{H}}" style="width:100%; max-width:860px; height:auto;">
      ${{grid}}
      <path d="${{line('filings')}}" fill="none" stroke="#1b4965" stroke-width="2.6"/>
      <path d="${{line('disp')}}" fill="none" stroke="#2a9d8f" stroke-width="2.6"/>
      <path d="${{line('evict')}}" fill="none" stroke="#b91c1c" stroke-width="2.2" stroke-dasharray="5,3"/>
      ${{circles('filings', '#1b4965')}}
      ${{circles('disp', '#2a9d8f')}}
      ${{circles('evict', '#b91c1c')}}
      ${{xLabels}}
    </svg>`;
}}

function renderCounties() {{
  const region = document.getElementById('region-filter').value;
  const q = document.getElementById('county-search').value.trim().toLowerCase();
  let rows = DATA.counties.filter(r =>
    (region === 'ALL' || r.region === region) &&
    (!q || r.county_name.toLowerCase().includes(q) || r.region.toLowerCase().includes(q))
  );

  // Filtered KPI rollup
  const sum = (list, col) => list.reduce((s, r) => s + (r[col] || 0), 0);
  // Rates use only counties whose numerator is published, so hidden counts don't drag them down
  const rate = col => {{
    const shown = rows.filter(r => r[col] !== null);
    const den = sum(shown, 'total_cases');
    return den > 0 ? (sum(shown, col) / den * 100).toFixed(1) + '%' : '—';
  }};
  const tot = sum(rows, 'total_cases');
  const cls = sum(rows, 'closed_cases');
  const evc = sum(rows, 'evicted_cases');
  const clr = rate('closed_cases');
  const evr = rate('evicted_cases');
  document.getElementById('filtered-kpis').innerHTML = `
    <div class="kpi"><div class="kpi-label">Jurisdictions Shown</div><div class="kpi-val">${{rows.length}}</div><div class="kpi-sub">Filter: ${{region}}</div></div>
    <div class="kpi"><div class="kpi-label">Petitions (Filtered)</div><div class="kpi-val">${{tot.toLocaleString()}}</div><div class="kpi-sub">Public suppressed rollup</div></div>
    <div class="kpi"><div class="kpi-label">Clearance Rate</div><div class="kpi-val">${{clr}}</div><div class="kpi-sub">${{cls.toLocaleString()}} closed</div></div>
    <div class="kpi"><div class="kpi-label">Executed Eviction Rate</div><div class="kpi-val">${{evr}}</div><div class="kpi-sub">${{evc.toLocaleString()}} evicted</div></div>
  `;

  rows.sort((a, b) => {{
    const va = a[sortCol], vb = b[sortCol];
    if (va === null && vb === null) return 0;
    if (va === null) return 1;
    if (vb === null) return -1;
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  }});

  document.querySelector('#county-table tbody').innerHTML = rows.map(r => `
    <tr>
      <td class="left"><strong>${{r.county_name}}</strong></td>
      <td class="left">${{r.region}}</td>
      <td>${{fmtInt(r.total_cases)}}</td>
      <td>${{fmtInt(r.closed_cases)}}</td>
      <td>${{fmtPct(r.clearance_rate_pct)}}</td>
      <td>${{fmtPct(r.eviction_rate_pct)}}</td>
      <td>${{fmtNum(r.median_days_closed, 1)}}</td>
      <td>${{fmtPct(r.pct_disposed_within_60d)}}</td>
      <td>${{fmtPct(r.batch_efiler_pct)}}</td>
    </tr>`).join('');

  renderMonthlySVG(region);
}}
document.getElementById('region-filter').addEventListener('change', renderCounties);
document.getElementById('county-search').addEventListener('input', renderCounties);
document.querySelectorAll('#county-table th.sortable').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if (sortCol === col) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = (col === 'county_name' || col === 'region'); }}
    renderCounties();
  }});
}});
renderCounties();

// Tab 4: Benchmark table
function renderBench() {{
  const f = document.getElementById('method-filter').value;
  const rows = DATA.bench.filter(r => f === 'all' || r.method === f);
  document.querySelector('#bench-table tbody').innerHTML = rows.map(r => `
    <tr>
      <td class="left"><code>${{r.method}}</code></td>
      <td class="left">${{r.field}}</td>
      <td>${{Number(r.precision).toFixed(3)}}</td>
      <td>${{Number(r.recall).toFixed(3)}}</td>
      <td><strong>${{Number(r.macro_f1).toFixed(3)}}</strong></td>
      <td>${{(Number(r.exact_accuracy) * 100).toFixed(1)}}%</td>
      <td>${{(Number(r.abstention_rate) * 100).toFixed(1)}}%</td>
      <td>${{r.ocr_accuracy_drop !== null ? (Number(r.ocr_accuracy_drop) * 100).toFixed(1) + '%' : '—'}}</td>
      <td>${{r.unsupported_claim_rate !== null ? (Number(r.unsupported_claim_rate) * 100).toFixed(1) + '%' : 'N/A'}}</td>
      <td>${{Number(r.median_latency_ms).toFixed(1)}}</td>
    </tr>`).join('');
}}
document.getElementById('method-filter').addEventListener('change', renderBench);
renderBench();

// Tab 5: QA Audit table
document.querySelector('#qa-table tbody').innerHTML = DATA.qa.map(r => `
  <tr>
    <td class="left"><code>${{r.metric}}</code></td>
    <td><strong>${{Number(r.value).toLocaleString()}}</strong></td>
    <td class="left">${{r.notes}}</td>
  </tr>`).join('');
</script>
</body>
</html>
"""

    OUT_PAGES.write_text(html, encoding="utf-8")
    print(f"[ok] Rendered interactive 5-tab dashboard -> {OUT_PAGES} ({OUT_PAGES.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
