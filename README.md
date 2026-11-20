# Open Court Analytics

Reproducible Python and SQL pipeline for state court case processing analytics, **National Open Court Data Standards (NODS)** alignment with PII governance, structured court-order extraction benchmarking (regex vs. classical NLP vs. LLM), survival and fixed-effects statistical modeling, and public-safe Tableau reporting.

## Architecture Overview

1. **Data Warehouse & PII Governance (`sql/`, `src/db/`):** Local DuckDB warehouse aligning raw state court records to core NODS tables, exposing only masked analyst views (`v_analyst_cases`) and small-cell suppressed (`< 10`) county aggregates (`v_public_county_summary`).
2. **Unstructured Document Extraction Benchmark (`src/nlp/`):** Side-by-side evaluation of deterministic rules, classical NLP (`spaCy` + `scikit-learn`), and schema-validated LLM extraction with mandatory `UNKNOWN` abstention and verbatim `evidence_span` verification.
3. **Statistical Analysis & Mapping (`src/analytics/`):** Right-censored time-to-disposition survival analysis (`lifelines`), fixed-effects logistic regression with county-clustered standard errors (`statsmodels`), county choropleth mapping (`geopandas`), and suppressed `.hyper` / CSV exports for Tableau Public.
4. **Decision-Ready Reporting (`reports/`, `docs/`):** Concise Quarto brief, non-technical pre-deployment AI Readiness Scorecard, and methodological limitations memo.

> **Language note:** Implemented in Python + SQL for a single reproducible environment. Equivalent R workflows map directly to `survival`, `fixest`, and `sf`.

## Quickstart

```bash
# Activate the uv virtual environment
source .venv/bin/activate

# Install project dependencies
uv sync
```
