# Data Dictionary

Status: Gate 4 checkpoint contract, snapshot `20260920_1b3a8424_38776a23`

## Scope

The pipeline reads the complete MSHA quarterly production snapshot, keeps only
records whose `COAL_METAL_IND` is `C`, and produces two private, rebuildable
Parquet checkpoints. Raw and checkpoint files are intentionally excluded from
Git.

The MSHA TXT exports use pipe delimiters and contain malformed internal quote
characters in free-text fields. The frozen snapshot has a constant delimiter
count on every physical row and no embedded pipe delimiters. The executable
parser therefore disables quote semantics, validates the delimiter count of
every row, and removes surrounding quote characters from fields used by the
pipeline. `Mines.txt` is losslessly transcoded from Latin-1 byte mappings to a
temporary UTF-8 file because it contains C1 control bytes rejected by DuckDB's
Latin-1 reader. The original file and its SHA-256 hash are never modified.

## Mine-quarter checkpoint

Path:
`data/interim/mine_quarter_20260920_1b3a8424_38776a23.parquet`

Grain: one row per `mine_id`, `state_code`, `cal_year`, and `cal_quarter` for
coal records in the source.

| Field | Type | Meaning |
| --- | --- | --- |
| `mine_id` | string | MSHA mine identifier, retained as text to preserve leading zeros. |
| `state_code` | string | Two-character state or territory code reported on the quarterly record. |
| `cal_year` | integer | Calendar year. |
| `cal_quarter` | integer | Calendar quarter, 1 through 4. |
| `period` | string | Human-readable period in `YYYYQn` form. |
| `quarter_start_date` | date | First calendar day of the quarter; used for chronological sorting. |
| `coal_production_short_tons` | double, nullable | Sum of reported subunit production in short tons. Remains null when every contributing value is null. |
| `average_employee_count` | double, nullable | Sum of reported average employee counts across mine subunits. Diagnostic only. |
| `hours_worked` | double, nullable | Sum of reported hours across mine subunits. Diagnostic only. |
| `source_row_count` | integer | Number of quarterly subunit records contributing to the row. |
| `reported_production_row_count` | integer | Contributing subunit records with a non-null production value. |
| `missing_production_row_count` | integer | Contributing subunit records with null production. |
| `production_all_null` | boolean | True when no contributing subunit reports production. |
| `production_partially_null` | boolean | True when reported and null subunit values coexist. |

## State-quarter checkpoint

Path:
`data/processed/state_quarter_20260920_1b3a8424_38776a23.parquet`

Grain: one row per observed `state_code`, `cal_year`, and `cal_quarter` after
mine-quarter aggregation. The frozen snapshot contains 2,718 rows across 27
states or territories from 2000Q1 through 2026Q2.

| Field | Type | Meaning |
| --- | --- | --- |
| `state_code` | string | Forecasting entity. |
| `cal_year` | integer | Calendar year. |
| `cal_quarter` | integer | Calendar quarter, 1 through 4. |
| `period` | string | Human-readable period in `YYYYQn` form. |
| `quarter_start_date` | date | First calendar day of the quarter. |
| `coal_production_short_tons` | double, nullable | Regional target: sum of non-null mine-quarter production. Null if every mine-quarter value in the row is null. |
| `mine_quarter_row_count` | integer | Mine-quarter records contributing to the region and quarter. |
| `observed_mine_count` | integer | Contributing mines with non-null production. |
| `all_null_mine_count` | integer | Contributing mines whose production is entirely null. |
| `positive_mine_count` | integer | Contributing mines with production above zero. |
| `zero_mine_count` | integer | Contributing mines reporting exactly zero production. |
| `partially_null_mine_count` | integer | Contributing mines with mixed reported and null subunit values. |
| `source_row_count` | integer | Original quarterly subunit records represented by the row. |
| `average_employee_count` | double, nullable | Regional sum of reported employee counts; diagnostic only. |
| `hours_worked` | double, nullable | Regional sum of reported hours; diagnostic only. |

## Missingness rules

- Reported zero production is an observed value and is never converted to
  missing.
- An all-null mine-quarter remains null; it is not imputed to zero.
- A partially reported mine-quarter sums available production and carries an
  explicit partial-null flag.
- A state-quarter absent from the checkpoint is not evidence of zero
  production. Regular-panel completion and any imputation decision belong to
  the later feature/evaluation stage and must use training information only.
- `2026Q2` is retained for the latest forecast origin but is not a scored
  target period.

## Non-target fields

Employment and hours are retained only for data-quality and explanatory
analysis at Gate 4. They are not approved forecasting features. Current mine
status, owner, controller, and operator fields from `Mines.txt` are not joined
into historical observations because the master file is a current snapshot
and would create temporal leakage if treated as historical truth.
