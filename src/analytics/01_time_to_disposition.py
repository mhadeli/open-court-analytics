"""Phase 3.1: Time-to-Disposition Survival Analysis & Survivorship Bias Audit.

Queries ONLY the masked `v_analyst_cases` view from DuckDB.
Contrasts naive closed-case averages against right-censored Kaplan-Meier curves (lifelines).
"""

from __future__ import annotations

from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "court_warehouse.duckdb"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def km_cumulative_resolved_at(kmf: KaplanMeierFitter, day: int) -> float:
    """Return % of cohort resolved (1 - S(t)) by `day`."""
    try:
        surv = float(kmf.predict(day))
        return round((1.0 - surv) * 100.0, 2)
    except Exception:
        return np.nan


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("SELECT * FROM v_analyst_cases").df()
    con.close()

    df["event_observed"] = (df["case_status"] == "Closed").astype(int)
    df["duration_days"] = df["days_observed"].astype(float)

    # Overall naive vs. Kaplan-Meier comparison
    closed_only = df[df["event_observed"] == 1]
    km_all = KaplanMeierFitter()
    km_all.fit(df["duration_days"], event_observed=df["event_observed"], label="All Housing Petitions")

    summary_rows = [
        {
            "group_type": "overall",
            "group_name": "All Maryland Housing Petitions",
            "n_total": len(df),
            "n_closed": int(df["event_observed"].sum()),
            "pct_right_censored": round((1.0 - df["event_observed"].mean()) * 100.0, 2),
            "naive_closed_mean_days": round(float(closed_only["duration_days"].mean()), 1),
            "naive_closed_median_days": round(float(closed_only["duration_days"].median()), 1),
            "km_median_days": round(float(km_all.median_survival_time_), 1)
            if np.isfinite(km_all.median_survival_time_)
            else np.nan,
            "km_pct_resolved_30d": km_cumulative_resolved_at(km_all, 30),
            "km_pct_resolved_60d": km_cumulative_resolved_at(km_all, 60),
            "km_pct_resolved_90d": km_cumulative_resolved_at(km_all, 90),
            "km_pct_resolved_120d": km_cumulative_resolved_at(km_all, 120),
        }
    ]

    # Stratify by case_category and batch_efiler_flag
    cat_kmfs: dict[str, KaplanMeierFitter] = {}
    for cat, grp in df.groupby("case_category"):
        kmf = KaplanMeierFitter()
        kmf.fit(grp["duration_days"], event_observed=grp["event_observed"], label=cat)
        cat_kmfs[cat] = kmf
        c_only = grp[grp["event_observed"] == 1]
        summary_rows.append(
            {
                "group_type": "case_category",
                "group_name": cat,
                "n_total": len(grp),
                "n_closed": int(grp["event_observed"].sum()),
                "pct_right_censored": round((1.0 - grp["event_observed"].mean()) * 100.0, 2),
                "naive_closed_mean_days": round(float(c_only["duration_days"].mean()), 1) if len(c_only) else np.nan,
                "naive_closed_median_days": round(float(c_only["duration_days"].median()), 1) if len(c_only) else np.nan,
                "km_median_days": round(float(kmf.median_survival_time_), 1)
                if np.isfinite(kmf.median_survival_time_)
                else np.nan,
                "km_pct_resolved_30d": km_cumulative_resolved_at(kmf, 30),
                "km_pct_resolved_60d": km_cumulative_resolved_at(kmf, 60),
                "km_pct_resolved_90d": km_cumulative_resolved_at(kmf, 90),
                "km_pct_resolved_120d": km_cumulative_resolved_at(kmf, 120),
            }
        )

    for flag_val, label in [(True, "Institutional Batch E-Filer"), (False, "Standard Filer")]:
        grp = df[df["batch_efiler_flag"] == flag_val]
        kmf = KaplanMeierFitter()
        kmf.fit(grp["duration_days"], event_observed=grp["event_observed"], label=label)
        c_only = grp[grp["event_observed"] == 1]
        summary_rows.append(
            {
                "group_type": "filer_type",
                "group_name": label,
                "n_total": len(grp),
                "n_closed": int(grp["event_observed"].sum()),
                "pct_right_censored": round((1.0 - grp["event_observed"].mean()) * 100.0, 2),
                "naive_closed_mean_days": round(float(c_only["duration_days"].mean()), 1) if len(c_only) else np.nan,
                "naive_closed_median_days": round(float(c_only["duration_days"].median()), 1) if len(c_only) else np.nan,
                "km_median_days": round(float(kmf.median_survival_time_), 1)
                if np.isfinite(kmf.median_survival_time_)
                else np.nan,
                "km_pct_resolved_30d": km_cumulative_resolved_at(kmf, 30),
                "km_pct_resolved_60d": km_cumulative_resolved_at(kmf, 60),
                "km_pct_resolved_90d": km_cumulative_resolved_at(kmf, 90),
                "km_pct_resolved_120d": km_cumulative_resolved_at(kmf, 120),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUTPUTS_DIR / "time_to_disposition_summary.csv", index=False)

    # Plot 2-panel publication visual: (A) KM Survival Curves, (B) Naive vs. KM Median Bias
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), dpi=160)

    ax = axes[0]
    palette = ["#1b4965", "#ca6702", "#2a9d8f", "#9b2226", "#6c757d"]
    for color, (cat, kmf) in zip(palette, sorted(cat_kmfs.items(), key=lambda kv: -len(kv[1].durations))):
        kmf.plot_survival_function(ax=ax, ci_show=True, color=color, linewidth=2.0)
    for thresh, lbl in [(30, "30d"), (60, "60d"), (90, "90d")]:
        ax.axvline(thresh, color="#666666", linestyle="--", linewidth=0.9, alpha=0.7)
        ax.text(thresh + 1.5, 0.94, lbl, fontsize=8.5, color="#444444")
    ax.set_title("A. Kaplan-Meier Probability Case Remains Open\n(Right-Censored at Extract Cutoff)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Days Since Warrant Petition Filed")
    ax.set_ylabel("Proportion Still Open — S(t)")
    ax.set_xlim(0, 150)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.25)
    ax.legend(frameon=True, fontsize=8.5, loc="lower left")

    ax2 = axes[1]
    cat_df = summary_df[summary_df["group_type"] == "case_category"].sort_values("km_median_days", ascending=True)
    y = np.arange(len(cat_df))
    h = 0.36
    ax2.barh(y - h / 2, cat_df["naive_closed_median_days"], height=h, color="#adb5bd", label="Naive Closed-Case Median (Biased)")
    ax2.barh(y + h / 2, cat_df["km_median_days"], height=h, color="#1b4965", label="Kaplan-Meier Median (Censor-Adjusted)")
    for i, (_, row) in enumerate(cat_df.iterrows()):
        if pd.notna(row["naive_closed_median_days"]):
            ax2.text(row["naive_closed_median_days"] + 1.2, i - h / 2, f"{row['naive_closed_median_days']:.0f}d", va="center", fontsize=8.5, color="#495057")
        if pd.notna(row["km_median_days"]):
            ax2.text(row["km_median_days"] + 1.2, i + h / 2, f"{row['km_median_days']:.0f}d", va="center", fontsize=8.5, color="#1b4965", fontweight="bold")
        else:
            ax2.text(2.0, i + h / 2, f"Not reached ({row['pct_right_censored']:.0f}% still open)", va="center", fontsize=8.2, color="#9b2226", style="italic")
    ax2.set_yticks(y)
    ax2.set_yticklabels(cat_df["group_name"], fontsize=9)
    ax2.set_xlim(0, 78)
    ax2.set_ylim(-0.6, len(cat_df) - 0.15)
    ax2.set_xlabel("Median Days to Warrant Resolution")
    ax2.set_title("B. Survivorship Bias: Naive vs. Censor-Adjusted Median\n(Ignoring Open Cases Understates Processing Time)", fontsize=11, fontweight="bold")
    ax2.grid(axis="x", alpha=0.25)
    ax2.legend(frameon=True, fontsize=8.2, loc="lower right", bbox_to_anchor=(0.99, 0.02))

    fig.suptitle("Maryland District Court Eviction Warrant Timelines (n = 51,948 Petitions, Apr–Sep 2026)", fontsize=12.5, fontweight="bold", y=0.99)
    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    fig.text(
        0.01, 0.005,
        "Source: Maryland Open Data (mvqb-b4hf) via masked v_analyst_cases view. Descriptive operational analysis; does not imply causal effects.",
        fontsize=8, color="#555555",
    )
    plt.savefig(OUTPUTS_DIR / "km_curves.png", dpi=160)
    plt.close(fig)

    print("=== Phase 3.1 Time-to-Disposition Summary ===")
    print(summary_df.to_string(index=False))
    print(f"[ok] Saved {OUTPUTS_DIR / 'km_curves.png'} and {OUTPUTS_DIR / 'time_to_disposition_summary.csv'}")


if __name__ == "__main__":
    main()
