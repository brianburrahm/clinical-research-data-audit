"""Reproducible research-data QA, descriptive analysis and reporting.

Uses the public-domain RAND Health Insurance Experiment extract shipped with
statsmodels.  No clinical records, credentials or private research data are used.

Run: python src/pipeline.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
FIGURES = ROOT / "figures"
DATA = ROOT / "data"
SOURCE = "statsmodels.datasets.randhie (RAND Health Insurance Experiment)"
COLUMNS = ["mdvis", "lncoins", "idp", "lpi", "fmde", "physlm", "disea", "hlthg", "hlthf", "hlthp"]
HEALTH = ["hlthg", "hlthf", "hlthp"]


def load_and_reconcile() -> tuple[pd.DataFrame, dict]:
    """Demonstrate validated record linkage using two views of one source.

    Important: coverage and encounter tables below are intentionally separated
    views of a SINGLE public dataset, not independently collected systems.
    """
    source = sm.datasets.randhie.load_pandas().data.loc[:, COLUMNS].copy()
    source.insert(0, "record_id", np.arange(1, len(source) + 1))
    coverage = source[["record_id", "lncoins", "idp", "lpi", "fmde"]].copy()
    outcomes = source[["record_id", "mdvis", "physlm", "disea", *HEALTH]].copy()
    assert coverage.record_id.is_unique and outcomes.record_id.is_unique
    merged = coverage.merge(outcomes, on="record_id", how="outer", validate="one_to_one", indicator=True)
    join_counts = {str(k): int(v) for k, v in merged["_merge"].value_counts().items()}
    assert join_counts.get("left_only", 0) == 0 and join_counts.get("right_only", 0) == 0
    merged = merged.drop(columns="_merge").sort_values("record_id").reset_index(drop=True)
    assert len(merged) == len(source)
    audit = {
        "source": SOURCE, "source_record_count": len(source),
        "linked_record_count": len(merged), "record_id_unique": bool(merged.record_id.is_unique),
        "linkage": join_counts,
        "missing_by_field": {c: int(merged[c].isna().sum()) for c in COLUMNS},
        "invalid_visits": int((merged.mdvis.notna() & ((merged.mdvis < 0) | (merged.mdvis % 1 != 0))).sum()),
        "nonbinary_physical_limitation_values": int((~merged.physlm.isin([0, 1]) & merged.physlm.notna()).sum()),
        "fractional_disease_burden_values": int(((merged.disea % 1 != 0) & merged.disea.notna()).sum()),
        "invalid_deductible_flag": int((~merged.idp.isin([0, 1]) & merged.idp.notna()).sum()),
        "overlapping_health_categories": int((merged[HEALTH].fillna(0).sum(axis=1) > 1).sum()),
        "zero_visit_records": int((merged.mdvis == 0).sum()),
        "notes": [
            "The two linked inputs are pedagogical views split from one public source; this is NOT a real cross-system linkage.",
            "record_id is a row surrogate, NOT a participant identifier; repeated person-years cannot be identified.",
            "Health-status flags refer to good, fair or poor; all zero indicates the omitted excellent category, provided the fields are complete.",
            "Published data dictionary describes physlm as binary and disea as count, but supplied values include fractions. Retain and flag them as source coding ambiguities; do not silently recode.",
        ],
    }
    assert audit["invalid_visits"] == 0, "Outpatient visit counts outside valid range"
    assert audit["invalid_deductible_flag"] == 0
    assert audit["overlapping_health_categories"] == 0
    return merged, audit


def analyze(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Descriptive reporting and exploratory count models, no causal inference."""
    d = df.dropna(subset=["mdvis", "lncoins", "idp", "physlm", "disea", *HEALTH]).copy()
    # This arithmetic only reverses the documented transform log(coinsurance+1).
    d["coinsurance_pct"] = np.expm1(d.lncoins).clip(0, 100).round(1)
    d["coinsurance_band"] = pd.cut(
        d.coinsurance_pct, bins=[-0.001, 0.001, 25, 50, 100.01],
        labels=["0%", ">0–25%", ">25–50%", ">50–100%"], include_lowest=True,
    )
    d["health_status"] = np.select(
        [d.hlthp.eq(1), d.hlthf.eq(1), d.hlthg.eq(1)],
        ["Poor", "Fair", "Good"], default="Excellent",
    )
    assert d.coinsurance_band.notna().all(), "Unexpected coinsurance outside documented range"
    group = (d.groupby(["coinsurance_band", "health_status"], observed=True)
             .agg(records=("mdvis", "size"), mean_visits=("mdvis", "mean"),
                  pct_zero_visits=("mdvis", lambda x: 100 * x.eq(0).mean()))
             .reset_index())
    group["mean_visits"] = group.mean_visits.round(3)
    group["pct_zero_visits"] = group.pct_zero_visits.round(2)
    by_band = (d.groupby("coinsurance_band", observed=True)
               .agg(records=("mdvis", "size"), mean_visits=("mdvis", "mean"))
               .reset_index())
    by_band["mean_visits"] = by_band.mean_visits.round(3)

    # Parsimonious, pre-specified exploratory associations, not causal effects.
    # Because the extract omits individual IDs, valid person-clustered standard
    # errors and group-aware validation are unavailable. Do NOT report p-values.
    x = sm.add_constant(d[["lncoins", "idp", "disea", *HEALTH]])
    y = d["mdvis"]
    poisson = sm.GLM(y, x, family=sm.families.Poisson()).fit()
    nb = sm.NegativeBinomial(y, x, loglike_method="nb2").fit(disp=False, maxiter=300)
    pred_p = poisson.predict(x)
    pred_nb = nb.predict(x)
    summary = {
        "dataset": SOURCE,
        "unit_of_analysis": "Record / person-year; cannot identify repeated people in this extract",
        "source_records": int(len(df)), "analyzed_records": int(len(d)),
        "excluded_for_missing_key_variables": int(len(df) - len(d)),
        "mean_visits": round(float(y.mean()), 3),
        "median_visits": round(float(y.median()), 3),
        "zero_visit_percent": round(float(y.eq(0).mean() * 100), 2),
        "visit_count_variance_to_mean": round(float(y.var(ddof=1) / y.mean()), 2),
        "mean_by_health_status": {str(k): round(float(v), 3) for k, v in d.groupby("health_status").mdvis.mean().items()},
        "model_comparison": {
            "poisson_aic_in_sample": round(float(poisson.aic), 2),
            "negative_binomial_aic_in_sample": round(float(nb.aic), 2),
            "negative_binomial_alpha": round(float(nb.params.get("alpha", float("nan"))), 4),
            "poisson_mae_in_sample": round(float(np.mean(abs(y - pred_p))), 3),
            "negative_binomial_mae_in_sample": round(float(np.mean(abs(y - pred_nb))), 3),
        },
        "negative_binomial_coinsurance_coefficient": round(float(nb.params["lncoins"]), 4),
        "warnings": [
            "Observational model associations must not be interpreted as estimated randomized treatment effects.",
            "The subset lacks original participant ID, study year, site, and family cluster; person-clustered uncertainty cannot be computed.",
            "AIC and MAE are in-sample model-fit diagnostics, not validation or clinical performance.",
            "This historical experiment is not representative of current utilization or care delivery.",
        ],
    }
    return summary, group, by_band


def sql_quality_check(df: pd.DataFrame) -> dict:
    """Execute actual SQL checks against an in-memory research data mart."""
    con = sqlite3.connect(":memory:")
    df.to_sql("study_records", con, index=False, if_exists="replace")
    query = (ROOT / "sql" / "qa_checks.sql").read_text()
    row = con.execute(query).fetchone()
    fields = [x[0] for x in con.execute(query).description]
    result = {k: int(v) for k, v in zip(fields, row)}
    con.close()
    assert result["records"] == len(df)
    assert result["distinct_record_ids"] == len(df)
    assert result["negative_visit_counts"] == 0
    assert result["health_flag_conflicts"] == 0
    return result


def make_figures(df: pd.DataFrame, by_band: pd.DataFrame) -> None:
    FIGURES.mkdir(exist_ok=True, parents=True)
    counts = df.mdvis.clip(upper=15).value_counts().reindex(range(16), fill_value=0)
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.bar(range(16), counts.values)
    ax.set(xlabel="Outpatient physician visits (15 includes 15+)", ylabel="Number of records",
           title="RAND HIE: distribution of physician visit counts")
    fig.tight_layout()
    fig.savefig(FIGURES / "visit_distribution.png", dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.bar(by_band.coinsurance_band.astype(str), by_band.mean_visits)
    for i, r in enumerate(by_band.itertuples()):
        ax.text(i, r.mean_visits + 0.035, f"n={r.records:,}", ha="center", fontsize=9)
    ax.set(xlabel="Documented coinsurance rate band", ylabel="Mean physician visits per record",
           title="Descriptive utilization by coinsurance band")
    ax.set_ylim(0, float(by_band.mean_visits.max()) * 1.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "visits_by_coinsurance.png", dpi=170)
    plt.close(fig)


def write_report(metrics: dict, audit: dict, sql: dict, bands: pd.DataFrame) -> None:
    b = "\n".join(f"| {r.coinsurance_band} | {r.records:,} | {r.mean_visits:.3f} |" for r in bands.itertuples())
    model = metrics["model_comparison"]
    status = "PASS" if not any((audit["invalid_visits"], audit["invalid_deductible_flag"], audit["overlapping_health_categories"])) else "REVIEW"
    report = f"""# Research data quality and analytic progress report

**Dataset:** RAND Health Insurance Experiment (HIE), public 10-variable subset shipped with `statsmodels`  
**Purpose:** Demonstrate clinical-research data management, reproducible analysis, SQL QA, and report-ready visualization.  
**Status:** {status} (automated checks)  
**Scope:** Historical observational summaries of records from a randomized insurance experiment; **not** a causal effect analysis.

## Executive summary

- **{metrics['source_records']:,}** public records loaded; **{metrics['analyzed_records']:,}** used for complete-case exploration.
- Average outpatient physician visits per record: **{metrics['mean_visits']:.3f}**; median **{metrics['median_visits']:.0f}**.
- **{metrics['zero_visit_percent']:.2f}%** of records show zero outpatient physician visits.
- Count variance / mean: **{metrics['visit_count_variance_to_mean']:.2f}**, indicating substantial overdispersion relative to a simple Poisson count model.
- Duplicate synthetic record IDs, negative visit counts, and contradictory health-status flags: **{sql['records'] - sql['distinct_record_ids']}**, **{sql['negative_visit_counts']}**, **{sql['health_flag_conflicts']}**, respectively.

## Deliverable 1: Reconciled analytical extract

The original public dataset was separated **for demonstration purposes** into coverage and outcome views, then rejoined on a generated *row surrogate* with one-to-one validation. This is a reproducible reconciliation exercise, **not** linkage of independently collected clinical data. Missingness, coverage, key uniqueness and field constraints are logged in `outputs/quality_audit.json`.

## Deliverable 2: Descriptive results

| Coinsurance band | Records | Mean physician visits |
|---|---:|---:|
{b}

The grouped data in `data/dashboard_table.csv` includes health-status strata, record counts, mean visits, and percentage of records with zero visits. Differences are descriptive, not estimates of causal benefit or harm.

![Visit distribution](../figures/visit_distribution.png)

![Utilization by coinsurance](../figures/visits_by_coinsurance.png)

## Deliverable 3: Exploratory model checks

Two count models were fit to the **same complete-case records** with documented covariates: log(coinsurance + 1), deductible-plan indicator, the documented disease-burden measure, and self-rated-health indicators. The ambiguous `physlm` field is omitted from modeling.

| Model | In-sample AIC | In-sample MAE |
|---|---:|---:|
| Poisson GLM | {model['poisson_aic_in_sample']:,.2f} | {model['poisson_mae_in_sample']:.3f} |
| Negative binomial NB2 | {model['negative_binomial_aic_in_sample']:,.2f} | {model['negative_binomial_mae_in_sample']:.3f} |

Estimated NB2 dispersion parameter alpha: **{model['negative_binomial_alpha']:.4f}**. These are **in-sample** fit diagnostics, not external validation. No clinical predictive accuracy, p-values, or causal effects are claimed.

## Data-definition exception detected

The source documentation calls `physlm` a binary flag and `disea` a chronic-disease count, yet **{audit["nonbinary_physical_limitation_values"]:,}** physical-limitation values are nonbinary and **{audit["fractional_disease_burden_values"]:,}** disease-burden values are fractional. The pipeline flags these for source-owner clarification instead of silently coercing data. `physlm` is excluded from modeling. `disea` is treated as a continuous source-coded covariate, not interpreted as a literal count.

## Audit and interpretation limitations

1. The public 10-variable extract omits individual, family, site, and study-year identifiers. Repeated person-year observations may exist and cannot be identified. Consequently, standard errors, cluster-robust inference, and subject-wise train/test splits would be inappropriate here.
2. The experiment is historical and the analytic extract is a subset of the original RAND HIE. Results do not describe contemporary patients.
3. Coinsurance bands are derived by reversing the documented log transformation and are presented descriptively. Differences across bands can reflect covariates and design effects.
4. No inference about intervention effectiveness, disease progression, or individualized care is supported.
5. The demonstration intentionally tests linked *views of the same dataset*. A production study would use source-system lineage and independent key validation.

## Recommended next study iteration

Obtain a permitted version with unique participant IDs, year, site, and randomization unit; then write a prespecified analysis plan, estimate person/family-clustered uncertainty, document missing-data assumptions, and conduct appropriate sensitivity analyses. For a laboratory deployment, replace the illustrative views with actual separate extracts and reconcile them under a data-use agreement.

## Reproduction and deliverable checklist

- [x] Public source documented and reloadable from a pinned Python package
- [x] Record-level join audit and missingness inventory
- [x] Schema checks and executable SQL validation
- [x] Descriptive table with denominators and data lineage
- [x] Predeclared exploratory model specification, diagnostics, and limitations
- [x] PNG exhibits and Tableau/Power BI-importable aggregate CSV
- [x] Unit tests and GitHub Actions CI configuration
"""
    (OUTPUT / "research_progress_report.md").write_text(report, encoding="utf-8")


def run() -> None:
    for folder in (OUTPUT, FIGURES, DATA): folder.mkdir(parents=True, exist_ok=True)
    df, audit = load_and_reconcile()
    sql = sql_quality_check(df)
    metrics, grouped, band = analyze(df)
    make_figures(df, band)
    (OUTPUT / "quality_audit.json").write_text(json.dumps({**audit, "sql_checks": sql}, indent=2))
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(metrics, indent=2))
    grouped.to_csv(DATA / "dashboard_table.csv", index=False)
    band.to_csv(OUTPUT / "coinsurance_summary.csv", index=False)
    write_report(metrics, audit, sql, band)
    print(f"PASS: {audit['source_record_count']:,} records, {metrics['analyzed_records']:,} analyzed. AIC Poisson={metrics['model_comparison']['poisson_aic_in_sample']}, NB={metrics['model_comparison']['negative_binomial_aic_in_sample']}")


if __name__ == "__main__":
    run()
