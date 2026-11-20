"""Phase 3.2: Fixed-Effects Survival (Cox PH) & Clustered Logistic Regression Models.

Queries ONLY `v_analyst_cases` from DuckDB.
Reports point estimates, hazard/odds ratios, 95% confidence intervals, and a
late-cohort censoring sensitivity check.
"""

from __future__ import annotations

from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from lifelines import CoxPHFitter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "court_warehouse.duckdb"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def fit_cox_model(df: pd.DataFrame) -> pd.DataFrame:
    """Stratified Cox Proportional Hazards model (stratified by county) for time-to-resolution.

    Stratifying baseline hazards by county absorbs jurisdiction-level operational differences
    without imposing a rigid proportional-hazards assumption across counties.
    """
    model_df = df[["days_observed", "case_status", "case_category", "batch_efiler_flag", "county_name"]].copy()
    model_df["event_observed"] = (model_df["case_status"] == "Closed").astype(int)
    model_df["batch_efiler"] = model_df["batch_efiler_flag"].astype(int)
    # Shift zero-day same-day dispositions to 0.5 days for clean continuous-time partial likelihood
    model_df["duration_days"] = model_df["days_observed"].astype(float).clip(lower=0.5)

    county_counts = model_df["county_name"].value_counts()
    major_counties = set(county_counts[county_counts >= 150].index)
    model_df["county_stratum"] = model_df["county_name"].where(
        model_df["county_name"].isin(major_counties), "Smaller MD Counties (<150)"
    )

    # Create clean dummy matrix (reference: Failure to Pay Rent)
    X_cat = pd.get_dummies(model_df["case_category"], prefix="cat", dtype=float)
    X_cat = X_cat.drop(columns=["cat_Failure to Pay Rent"], errors="ignore")

    cox_df = pd.concat(
        [
            model_df[["duration_days", "event_observed", "batch_efiler", "county_stratum"]].reset_index(drop=True),
            X_cat.reset_index(drop=True),
        ],
        axis=1,
    )

    cph = CoxPHFitter(penalizer=0.01)
    cph.fit(
        cox_df,
        duration_col="duration_days",
        event_col="event_observed",
        strata=["county_stratum"],
    )

    summ = cph.summary.reset_index().rename(columns={"covariate": "term"})
    out = pd.DataFrame(
        {
            "model": "cox_ph_time_to_disposition",
            "term": summ["term"],
            "estimate_log_scale": summ["coef"].round(4),
            "ratio_hr_or": summ["exp(coef)"].round(4),
            "ci_lower_95": summ["exp(coef) lower 95%"].round(4),
            "ci_upper_95": summ["exp(coef) upper 95%"].round(4),
            "p_value": summ["p"].round(5),
            "n_obs": len(cox_df),
            "notes": f"County-stratified Cox PH; Concordance={cph.concordance_index_:.3f}; ref=Failure to Pay Rent",
        }
    )
    return out


def fit_clustered_logit(df: pd.DataFrame, model_label: str = "logit_eviction_executed_full") -> pd.DataFrame:
    """Logistic regression for warrant execution (evicted_flag) with county fixed effects & clustered SEs."""
    sub = df.copy()
    sub["evicted_int"] = sub["evicted_flag"].astype(int)
    sub["batch_efiler"] = sub["batch_efiler_flag"].astype(int)
    sub["filing_month_str"] = pd.to_datetime(sub["filing_month"]).dt.strftime("%Y-%m")

    # Keep counties that have >= 100 observations and variation in outcome for valid fixed-effect logit
    grp_stats = sub.groupby("jurisdiction_fips")["evicted_int"].agg(["count", "sum"])
    valid_fips = set(grp_stats[(grp_stats["count"] >= 100) & (grp_stats["sum"] >= 5)].index)
    sub = sub[sub["jurisdiction_fips"].isin(valid_fips)].copy()

    formula = (
        "evicted_int ~ batch_efiler "
        "+ C(case_category, Treatment(reference='Failure to Pay Rent')) "
        "+ C(filing_month_str) "
        "+ C(jurisdiction_fips)"
    )
    res = smf.logit(formula=formula, data=sub).fit(
        disp=False,
        cov_type="cluster",
        cov_kwds={"groups": sub["jurisdiction_fips"]},
    )

    ci = res.conf_int()
    rows = []
    for term in res.params.index:
        # Report key substantive predictors + clean county FE summary
        if term.startswith("C(jurisdiction_fips)"):
            continue
        coef = float(res.params[term])
        lo, hi = float(ci.loc[term, 0]), float(ci.loc[term, 1])
        rows.append(
            {
                "model": model_label,
                "term": term,
                "estimate_log_scale": round(coef, 4),
                "ratio_hr_or": round(float(np.exp(coef)), 4),
                "ci_lower_95": round(float(np.exp(lo)), 4),
                "ci_upper_95": round(float(np.exp(hi)), 4),
                "p_value": round(float(res.pvalues[term]), 5),
                "n_obs": int(res.nobs),
                "notes": f"Pseudo-R2={res.prsquared:.3f}; county-clustered SEs ({len(valid_fips)} counties, county & month FEs included)",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("SELECT * FROM v_analyst_cases").df()
    con.close()

    cox_df = fit_cox_model(df)
    logit_full = fit_clustered_logit(df, model_label="logit_eviction_executed_full")

    # Sensitivity check: exclude late-filing petitions (<60 days before extract cutoff) to verify censoring robustness
    cutoff = pd.Timestamp(df["extract_cutoff_date"].max())
    mature_cutoff = cutoff - pd.Timedelta(days=60)
    mature_df = df[pd.to_datetime(df["filing_date"]) <= mature_cutoff].copy()
    logit_mature = fit_clustered_logit(mature_df, model_label="logit_eviction_mature_60d_cohort")

    all_models = pd.concat([cox_df, logit_full, logit_mature], ignore_index=True)
    all_models.to_csv(OUTPUTS_DIR / "model_coefficients.csv", index=False)

    # Print key non-FE coefficients cleanly
    key_terms = all_models[~all_models["term"].str.startswith("cty_") & ~all_models["term"].str.startswith("C(filing_month")]
    print("=== Phase 3.2 Key Model Estimates (HR / OR with 95% CIs) ===")
    print(key_terms[["model", "term", "ratio_hr_or", "ci_lower_95", "ci_upper_95", "p_value", "n_obs"]].to_string(index=False))
    print(f"\n[ok] Saved full coefficients to {OUTPUTS_DIR / 'model_coefficients.csv'}")


if __name__ == "__main__":
    main()
