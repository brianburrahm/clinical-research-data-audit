# Analysis plan, governance and limitations

## Objective

Build a reproducible miniature clinical-research operations deliverable: audited data ingestion, reconciled reporting views, SQL checks, descriptive measures, exploratory models, tables and a progress report.

## Dataset and provenance

The RAND Health Insurance Experiment was a historical randomized insurance-policy study. `statsmodels` distributes a public-domain **20,190-record, 10-variable extract**. The public extract does **not** supply individual and family IDs, site, year or complete original study design fields. It is not a clinical dataset collected or maintained by the portfolio author.

## Data-management workflow

1. Load source from the installed `statsmodels` package and preserve all values.
2. Generate a unique **row** surrogate (`record_id`), explicitly not an individual identifier.
3. Split the single extract into illustrative coverage and clinical-outcome views to demonstrate a one-to-one keyed reconciliation. These are **not** genuinely independent data systems.
4. Audit one-to-one coverage, unexpected nulls, data ranges, mutually exclusive flags and source-codebook discrepancies.
5. Execute SQL validation in SQLite and stop for blocking anomalies.
6. Produce descriptive grouped tables, quality artifacts, figures and an analyst progress report.

## Exploratory analysis

- Outcome: outpatient physician-visit count (`mdvis`).
- Descriptive dimensions: derived coinsurance percentage bands and self-rated health category.
- Predictors in exploratory models: `lncoins`, `idp`, source-coded `disea`, `hlthg`, `hlthf`, `hlthp` with an intercept. `physlm` is excluded because its fractional coding conflicts with the binary documentation.
- Models: Poisson GLM and negative binomial NB2, compared via **in-sample** AIC and absolute error. No p-values are interpreted.
- No patient-level train/test split is attempted because repeated people cannot be identified and a row-level split would leak information across subjects.

## Interpretation boundaries

**The model is descriptive/exploratory, not causal.** This historical source comes from a randomized experiment, but the necessary assignment, family clustering, site and time information for a valid treatment-effects analysis is unavailable in the 10-variable extract. These results cannot establish what changing insurance design would do to patient use. No clinical claims or current utilization forecasts are made. Counts are person-year records, not demonstrated independent patients.

**Data-definition ambiguity is substantive:** some `physlm` values are fractional and most `disea` values are fractional, despite short source descriptions suggesting an indicator and literal count. We intentionally flag rather than coerce those values. This is a limitation of a condensed teaching extract, not evidence of a clinical source error.

## What a production lab deployment would require

A signed data-use agreement, authorized secure workspace, controlled clinical dictionary, verified patient/visit IDs, documented exclusion rules and missingness rationale, prespecified analysis plan, cluster-aware models, audit trail, code review, and sponsor-specific reporting templates.
