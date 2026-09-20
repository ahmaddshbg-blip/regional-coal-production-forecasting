# Architecture

Status: Design-level architecture; implementation begins after Gate 2

Last reviewed: 2026-09-20

## Design goals

- keep raw source snapshots immutable;
- avoid hard-coded personal paths;
- reduce data by business relevance before modeling;
- use SQL where relational filtering and aggregation are natural;
- keep forecasting and evaluation logic in tested Python modules;
- reuse validated checkpoints rather than rescanning raw files in every
  notebook; and
- support Google Colab notebook execution while keeping local development,
  validation, and tests efficient.

## Data flow

```text
MSHA ZIP archives
    |
    v
immutable extracted TXT snapshots
    |
    v
schema and snapshot validation
    |
    v
SQL column projection and coal-only filter
    |
    +--> mine-quarter checkpoint and quality diagnostics
    |
    v
SQL state-quarter aggregation
    |
    v
validated forecasting panel
    |
    v
Python rolling-origin evaluation
    |
    v
metrics, forecasts, figures, and decision output
```

## Data reduction strategy

The raw file contains 2,761,471 rows because it combines coal and
metal/nonmetal reporting. The approved forecasting target uses coal only.
Filtering `COAL_METAL_IND = 'C'` reduces the relevant input to 344,473 rows;
aggregating by mine-quarter reduces it to 183,301 rows; the state-quarter
forecasting table contains at most 27 states by 106 quarters.

Therefore, the pipeline will preserve the full temporal snapshot and reduce
the working set through:

1. reading only required columns;
2. applying the coal filter before other transformations;
3. aggregating once into validated checkpoints; and
4. loading only those checkpoints in EDA and modeling notebooks.

Deleting older quarters solely to meet a row-count target would weaken the
seasonality, structural-change, and rolling-origin evidence without producing
a meaningful computational benefit.

This reduction preserves the approved objective. State-quarter production is
the forecast target because the supported decision is regional. The
mine-quarter checkpoint remains available to explain regional composition,
entry and exit, missingness, and concentration without turning mine-level
forecasting into the primary task.

## SQL boundary

SQL will own operations that are naturally tabular and auditable:

- coal filtering;
- type and period normalization;
- mine-subunit to mine-quarter aggregation;
- mine-quarter to state-quarter aggregation;
- record, null, zero, and entity counts; and
- duplicate and referential-integrity checks where practical.

The intended transformation shape is:

```sql
WITH coal_records AS (
    SELECT
        mine_id,
        state,
        cal_yr,
        cal_qtr,
        coal_production,
        avg_employee_cnt,
        hours_worked
    FROM quarterly_source
    WHERE coal_metal_ind = 'C'
),
mine_quarter AS (
    SELECT
        mine_id,
        state,
        cal_yr,
        cal_qtr,
        SUM(coal_production) AS coal_production,
        COUNT(coal_production) AS reported_production_rows
    FROM coal_records
    GROUP BY mine_id, state, cal_yr, cal_qtr
)
SELECT
    state,
    cal_yr,
    cal_qtr,
    SUM(coal_production) AS coal_production,
    COUNT(*) AS mine_quarter_count,
    SUM(CASE WHEN reported_production_rows = 0 THEN 1 ELSE 0 END)
        AS missing_mine_quarter_count
FROM mine_quarter
GROUP BY state, cal_yr, cal_qtr;
```

The final SQL engine will be chosen at Gate 3. An embedded analytical engine is
preferred over a database service because the data volume does not justify
operational infrastructure. SQL is included for transparent transformation,
not as decoration.

## Python boundary

Python will own:

- orchestration and configuration;
- file and schema validation around the SQL stage;
- checkpoint metadata and checksums;
- temporal feature construction;
- rolling-origin split generation;
- baselines and later candidate models;
- metrics, uncertainty, and error analysis; and
- figures and decision-facing outputs.

Notebooks will call reusable Python functions and display evidence. They will
not contain the only implementation of ingestion, transformation, or
evaluation logic.

The principal analytical workflow will remain in `.ipynb` notebooks executed
in Google Colab. Supporting `.py` modules and scripts will contain reusable,
testable logic. This keeps the notebooks readable and interactive without
making hidden notebook state the only way to reproduce the analysis.

## Execution and storage

| Asset | Primary location | Synchronization rule |
| --- | --- | --- |
| Code, tests, notebooks, configs, and documentation | Git repository | Git commit/push/pull |
| Raw source snapshot | Private Drive archive plus local cache | Copy only for a deliberate version change; verify hashes |
| Rebuildable interim and processed data | Local by default | Regenerate; store externally only when reuse is valuable |
| Expensive run checkpoints | Private Drive, versioned by run | Reuse only after metadata validation |
| Final lightweight metrics and figures | Git repository | Update with the code and configuration that produced them |

The current local repository is the active development workspace. A private
Git remote should become the code synchronization mechanism once established;
periodic full-folder copying to Drive is only a temporary fallback.

## Path contract

Code will resolve a project-relative `data/` directory by default and permit an
environment-variable override such as `PROJECT_DATA_ROOT`. Local and Colab
physical paths may differ while preserving the same logical structure:

```text
data/raw/MinesProdQuarterly.txt
data/raw/Mines.txt
```

No public code or notebook may depend on a personal Windows or Google Drive
path.

## Colab boundary

Google Colab is the primary environment in which the author will execute the
main analytical notebooks. Local execution remains the development and
verification environment for source modules, SQL, scripts, and tests.

Each Colab notebook must use repository code, mount Drive only for external data
or checkpoints, and record the data snapshot, configuration, dependency
versions, and code revision for material runs. Small validation tasks may still
run locally; this is an execution choice, not a second analytical workflow.
