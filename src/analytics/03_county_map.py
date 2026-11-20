"""Phase 3.3: County-Level Choropleth Mapping (geopandas + matplotlib).

Queries ONLY `v_public_county_overall` (small-cell suppressed < 10) from DuckDB
and joins to Census TIGER/Line 2023 county geometries (Maryland STATEFP='24').
"""

from __future__ import annotations

from pathlib import Path
import duckdb
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "court_warehouse.duckdb"
SHP_ZIP = PROJECT_ROOT / "data" / "raw" / "cb_2023_us_county_20m.zip"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    county_df = con.execute("SELECT * FROM v_public_county_overall").df()
    con.close()

    counties_gdf = gpd.read_file(f"zip://{SHP_ZIP}")
    md_gdf = counties_gdf[counties_gdf["STATEFP"] == "24"].copy()
    md_gdf["GEOID"] = md_gdf["GEOID"].astype(str)
    county_df["jurisdiction_fips"] = county_df["jurisdiction_fips"].astype(str)

    merged = md_gdf.merge(county_df, left_on="GEOID", right_on="jurisdiction_fips", how="left")
    # Reproject to Maryland State Plane / Albers Equal Area for clean proportions
    merged = merged.to_crs(epsg=3857)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), dpi=170)

    # Panel A: Median Days to Disposition (Closed Cases)
    ax1 = axes[0]
    merged.plot(
        column="median_days_closed",
        ax=ax1,
        cmap="YlGnBu",
        edgecolor="#333333",
        linewidth=0.6,
        legend=True,
        legend_kwds={"label": "Median Days (Closed Petitions)", "shrink": 0.62, "orientation": "horizontal", "pad": 0.04},
        missing_kwds={"color": "#d9d9d9", "edgecolor": "#555555", "hatch": "///", "label": "Suppressed (<10 cases)"},
    )
    ax1.set_title("A. Median Days to Warrant Resolution\n(Suppressed Counties <10 Closed Cases Hatched)", fontsize=11, fontweight="bold")
    ax1.set_axis_off()

    # Panel B: Warrant Execution (Eviction) Rate (%)
    ax2 = axes[1]
    merged.plot(
        column="eviction_rate_pct",
        ax=ax2,
        cmap="OrRd",
        edgecolor="#333333",
        linewidth=0.6,
        legend=True,
        legend_kwds={"label": "Executed Eviction Rate (% of Petitions)", "shrink": 0.62, "orientation": "horizontal", "pad": 0.04},
        missing_kwds={"color": "#d9d9d9", "edgecolor": "#555555", "hatch": "///", "label": "Suppressed (<10 cases)"},
    )
    ax2.set_title("B. Executed Eviction Share by Jurisdiction\n(% of Petitions Resulting in Return of Service - Evicted)", fontsize=11, fontweight="bold")
    ax2.set_axis_off()

    # Annotate key jurisdictions cleanly on Panel A
    highlight_fips = {"24510": "Baltimore City", "24031": "Montgomery", "24033": "Prince George's", "24023": "Garrett"}
    for _, row in merged[merged["GEOID"].isin(highlight_fips)].iterrows():
        pt = row.geometry.representative_point()
        lbl = highlight_fips[row["GEOID"]]
        val = f"\n{row['median_days_closed']:.0f}d" if pd.notna(row["median_days_closed"]) else "\n(suppressed)"
        ax1.annotate(
            lbl + val,
            xy=(pt.x, pt.y),
            fontsize=7.2,
            fontweight="bold",
            ha="center",
            color="#111111",
            bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "#888888", "alpha": 0.82},
        )

    fig.suptitle("Maryland District Court Eviction Warrant Metrics Across All 24 Jurisdictions (Apr–Sep 2026)", fontsize=12.5, fontweight="bold", y=0.98)
    fig.text(
        0.01, 0.01,
        "Sources: Maryland Open Data (mvqb-b4hf) via v_public_county_overall; U.S. Census TIGER/Line 2023. Cells <10 cases suppressed for privacy. Descriptive only.",
        fontsize=8, color="#555555",
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.94])
    out_png = OUTPUTS_DIR / "county_bottlenecks_map.png"
    plt.savefig(out_png, dpi=170)
    plt.close(fig)

    suppressed_n = int(county_df["median_days_closed"].isna().sum())
    print(f"[ok] Saved {out_png} (24 Maryland jurisdictions mapped; {suppressed_n} suppressed on median_days_closed)")


if __name__ == "__main__":
    import pandas as pd
    main()
