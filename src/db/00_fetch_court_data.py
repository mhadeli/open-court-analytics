"""Fetch public Maryland District Court eviction records and U.S. Census county boundaries.

Data sources (zero authentication required):
1. District Court of Maryland Eviction Case Data (Maryland Open Data / Socrata ID: mvqb-b4hf)
   https://opendata.maryland.gov/Housing/District-Court-of-Maryland-Eviction-Case-Data/mvqb-b4hf
2. U.S. Census Bureau 2023 Cartographic Boundary County Shapefile (20m resolution)
   https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip
"""

from __future__ import annotations

import argparse
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

MD_EVICTION_URL = "https://opendata.maryland.gov/resource/mvqb-b4hf.csv"
CENSUS_COUNTIES_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip"


def fetch_maryland_eviction_data(limit: int = 100_000, force: bool = False) -> Path:
    """Download public Maryland District Court case-event records as CSV."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "md_eviction_cases.csv"
    if out_path.exists() and not force:
        print(f"[skip] {out_path} already exists ({out_path.stat().st_size:,} bytes)")
        return out_path

    # Fetch recent records in clean batches via Socrata SODA API
    batch_size = 25_000
    chunks: list[bytes] = []
    offset = 0
    while offset < limit:
        take = min(batch_size, limit - offset)
        params = {
            "$limit": str(take),
            "$offset": str(offset),
            "$order": "eventdate DESC, casenumber ASC",
        }
        print(f"Fetching Maryland court records: offset={offset:,}, limit={take:,}...")
        resp = requests.get(MD_EVICTION_URL, params=params, timeout=60)
        resp.raise_for_status()
        lines = resp.content.splitlines(keepends=True)
        if len(lines) <= 1:
            break
        if offset == 0:
            chunks.extend(lines)
        else:
            chunks.extend(lines[1:])  # skip repeated header
        fetched = len(lines) - 1
        if fetched < take:
            break
        offset += fetched

    out_path.write_bytes(b"".join(chunks))
    row_count = sum(1 for _ in out_path.open("rb")) - 1
    print(f"[ok] Saved {row_count:,} Maryland court rows to {out_path}")
    return out_path


def fetch_census_counties(force: bool = False) -> Path:
    """Download Census TIGER/Line generalized county boundaries zip."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "cb_2023_us_county_20m.zip"
    if out_path.exists() and not force:
        print(f"[skip] {out_path} already exists ({out_path.stat().st_size:,} bytes)")
        return out_path

    print(f"Downloading Census county shapefile from {CENSUS_COUNTIES_URL}...")
    resp = requests.get(CENSUS_COUNTIES_URL, timeout=60)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    print(f"[ok] Saved shapefile zip ({out_path.stat().st_size:,} bytes) to {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public court and boundary datasets.")
    parser.add_argument("--limit", type=int, default=100_000, help="Max court rows to fetch")
    parser.add_argument("--force", action="store_true", help="Overwrite existing downloads")
    args = parser.parse_args()

    fetch_maryland_eviction_data(limit=args.limit, force=args.force)
    fetch_census_counties(force=args.force)


if __name__ == "__main__":
    main()
