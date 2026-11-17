# Study data dictionary and validation rules

This case study uses the ten fields shipped with `statsmodels.datasets.randhie` (20,190 rows). All original values are loaded from the package; `record_id` and `coinsurance_band` are explicitly derived in the pipeline.

| Field | Documented source meaning | Role / QC considerations |
|---|---|---|
| `mdvis` | Number of outpatient physician visits | Nonnegative integer count; response variable |
| `lncoins` | Natural log of `(coinsurance percentage + 1)` | Reversed with `expm1` for reporting bands; retained on original scale in models |
| `idp` | Indicator for individual deductible plan | Must be 0 or 1 |
| `lpi` | Log of participation incentive | Preserved in source audit; not included in parsimonious count models |
| `fmde` | Maximum expenditure-related transformed variable | Preserved; not used in models |
| `physlm` | Documented as physical limitation indicator | **1,052 nonbinary values** detected; excluded from models pending source clarification |
| `disea` | Documented as number of chronic diseases | **18,396 fractional values** detected; interpreted only as source-coded continuous covariate, not a literal integer count |
| `hlthg` | Health status good | Binary, mutually exclusive with other health flags |
| `hlthf` | Health status fair | Binary, mutually exclusive with other health flags |
| `hlthp` | Health status poor | Binary, mutually exclusive with other health flags |
| `record_id` | **Derived** sequential surrogate row key | Used for pedagogical view reconciliation only; **not** person identifier |
| `health_status` | **Derived** category | Poor / Fair / Good / Excellent omitted category |
| `coinsurance_band` | **Derived** cost-sharing group | 0%, >0–25%, >25–50%, >50–100% |

## Severity classification

- **Blocking:** missing join keys, row-count mismatch, duplicate derived keys, negative visits, contradictory self-rated health categories, invalid deductible indicator.
- **Documented exception:** nonbinary `physlm`, fractional `disea`. The source is kept intact. Do not impute or coerce without a trusted codebook.
- **Nonblocking warning:** row IDs cannot be used for person-level longitudinal inference; the upstream 10-variable subset lacks study year and family/person identifiers.

Source codebook: https://www.statsmodels.org/stable/datasets/generated/randhie.html
