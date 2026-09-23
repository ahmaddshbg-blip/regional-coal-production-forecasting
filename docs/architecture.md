# Architecture

Status: Gate 5 complete; candidate procedure frozen before implementation

Last reviewed: 2026-09-23

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

## Gate 3 technology decisions

- Embedded SQL engine: DuckDB Python client.
- Raw ingestion: DuckDB `read_csv` with an explicit schema, pipe delimiter,
  header, quote rules, empty-string null handling, and `latin-1` encoding.
- Checkpoint format: Parquet with Zstandard compression.
- Data-frame interface: pandas after the relational transformation is reduced
  to mine-quarter or state-quarter scale.
- Configuration: one versioned JSON file plus environment-variable path
  overrides; no YAML dependency.
- Packaging: a small `src/coal_forecasting` Python package installed from a
  `pyproject.toml` file.
- Tests: standard-library `unittest`, synthetic fixtures in Git, and optional
  local snapshot checks when raw data are available.
- Orchestration: ordinary Python scripts and notebook calls. No workflow
  platform, database server, Docker image, Spark cluster, or experiment
  tracking service is justified at this scale.

DuckDB is selected over SQLite because it can scan the source files directly
and write Parquet without first importing 2.76 million rows into a persistent
database. It is selected over a pandas-only transformation because the
filtering, grouped aggregation, and data-quality summaries are clearer and
independently reviewable as SQL. Polars is not added because it would introduce
a second data-frame API without removing a requirement.

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

DuckDB is the selected SQL engine. The pipeline will use an in-memory
connection and versioned SQL files rather than a persistent database file. Raw
CSV options and column types must be explicit; production runs may use the CSV
sniffer only as a diagnostic, never as the executable schema contract.

The frozen MSHA exports contain malformed internal quote characters. Every
physical row nevertheless has the exact expected pipe-delimiter count, with no
embedded pipes. Gate 4 therefore disables quote semantics, validates every
row's delimiter count, and strips surrounding quotes only from fields used by
the transformation. `Mines.txt` also contains C1 bytes that DuckDB rejects as
Latin-1; Python performs a temporary, lossless Latin-1-code-point to UTF-8
transcode before DuckDB reads it. Raw bytes and hashes remain unchanged.

SQL files will be separated by responsibility:

```text
sql/
|-- build_mine_quarter.sql
|-- build_state_quarter.sql
`-- quality_checks.sql
```

Python supplies validated paths and parameters, executes the SQL, checks query
outputs, and writes checkpoint metadata. SQL must not contain a personal local
or Drive path.

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

## Minimal repository layout

Files and directories will be created only when their stage begins. The target
layout is:

```text
configs/
`-- project.json
sql/
|-- build_mine_quarter.sql
|-- build_state_quarter.sql
`-- quality_checks.sql
src/
`-- coal_forecasting/
    |-- __init__.py
    |-- config.py
    |-- paths.py
    |-- validation.py
    |-- pipeline.py
    |-- evaluation.py
    |-- baselines.py
    `-- metrics.py
scripts/
|-- build_dataset.py
`-- evaluate_baselines.py
tests/
|-- fixtures/
|-- test_config_paths.py
|-- test_validation.py
|-- test_transformations.py
`-- test_evaluation.py
notebooks/
|-- 01_data_validation_and_panel.ipynb
|-- 02_time_series_eda.ipynb
|-- 03_baseline_backtesting.ipynb
|-- 04_candidate_models.ipynb
`-- 05_error_uncertainty_decision_output.ipynb
```

This is a creation sequence, not permission to add empty folders. Gate 4
created configuration, data validation, SQL transformation, pipeline, the
first notebook, and their tests. Gate 5 added the EDA and baseline stages.
Candidate-model code and notebook 04 do not exist until one complete candidate
procedure has been justified and frozen.

The package stays flat because the project is not large enough to justify
nested `data`, `features`, `models`, and `evaluation` subpackages. A new module
is added only when one existing module would otherwise own unrelated logic.

## Configuration contract

`configs/project.json` will be the machine-readable execution contract. It will
contain only stable values used by code:

- raw filenames, byte sizes, SHA-256 hashes, delimiter, encoding, and expected
  headers;
- relative interim, processed, metadata, and run-output paths;
- expected snapshot counts and temporal coverage;
- modeling start, validation origins, embargo, holdout origins, latest forecast
  origin, horizons, and eligibility thresholds from the frozen forecasting
  contract; and
- deterministic seed and schema-version identifiers.

Rationale stays in documentation rather than being duplicated as comments in
configuration. Tests must detect disagreement between configuration values and
the implemented split or schema.

Only two environment-variable overrides are planned:

- `PROJECT_DATA_ROOT`: external root containing `raw`, `interim`, and
  `processed` directories;
- `PROJECT_RUNS_ROOT`: optional external root for versioned run outputs.

Path precedence is environment override first, then the project-relative
default. An unset variable is normal. `.env.example` documents variable names,
but the project will use `os.environ` directly and will not add a dotenv
dependency.

## Dependency policy

`pyproject.toml` will be the authoritative direct dependency specification.
The initial runtime set is deliberately small:

- Python 3.11 through 3.13;
- DuckDB 1.5.5 for SQL execution and Parquet I/O;
- pandas 2.2 or newer but below 3.1 for labeled panel operations;
- NumPy 2.x for numerical metric logic; and
- Matplotlib 3.8 or newer but below 4 for reproducible figures.

No model library was included before a candidate class was justified.
`DEC-012` now selects deterministic Ridge regression for the first candidate;
its implementation may add scikit-learn as one recorded dependency. The
standard library supplies JSON, hashing, logging, argument parsing, and unit
testing.

The project metadata uses compatible version bounds. The clean Gate 4 Colab run
is frozen in `requirements-lock.txt`, which records the tested transitive
environment. `pyproject.toml` defines what the project supports;
the lock file defines the exact published reproduction environment. Every
material run manifest records Python, DuckDB, pandas, NumPy, and platform
versions.

## Checkpoint contract

The frozen snapshot identifier is:

```text
20260920_1b3a8424_38776a23
```

It combines the acquisition date with the first eight characters of the
quarterly and mine-master SHA-256 hashes. Planned checkpoints are:

```text
data/interim/mine_quarter_20260920_1b3a8424_38776a23.parquet
data/processed/state_quarter_20260920_1b3a8424_38776a23.parquet
```

Checkpoint rules:

- write Parquet with Zstandard compression;
- use stable snake-case column names and deterministic sort order;
- retain quarter year, quarter number, a sortable quarter-start date, target,
  entity counts, null counts, reported-zero counts, and coverage flags;
- compute output SHA-256 hashes and schema fingerprints;
- write to a temporary file, validate it, and move it into place only after all
  checks pass;
- refuse silent overwrite; and
- record source hashes, config hash, code commit, row count, schema version,
  and output hash in the run manifest.

Interim and processed checkpoints remain outside Git. A reviewer can rebuild
them from the documented raw files, SQL, configuration, and command.

## Run manifest

Each material execution receives a UTC run identifier containing a timestamp
and short Git commit. Its JSON manifest records:

- command and stage;
- Git commit and dirty-worktree flag;
- configuration hash;
- raw and checkpoint hashes;
- dependency and Python versions;
- start/end timestamps and status;
- row counts, schema versions, and validation summary; and
- paths expressed relative to the configured data or runs root.

Run directories are ignored by Git and may live on private Drive. Only reviewed
lightweight summaries, metrics, and figures return to the public repository.

## Test plan

Tests protect project-specific failure modes rather than package syntax.

Data and SQL tests must cover:

- missing or changed raw files, hashes, headers, and types;
- fixed-width pipe-delimited ingestion with malformed quotes and C1 bytes;
- coal filtering and complete mine-master joins;
- duplicate mine-quarter-subunit keys and invalid quarter values;
- negative production;
- reported zero versus null production;
- all-null and mixed-null subunit aggregation;
- mine-quarter and state-quarter counts, keys, and sort order; and
- deterministic Parquet schema and metadata.

Evaluation tests must cover:

- the 54 development, four embargo, and 12 holdout origins;
- no development/holdout target overlap;
- dynamic state entry, exit, and re-entry;
- minimum-history and four-consecutive-quarter eligibility;
- persistence and annual seasonal-persistence formulas;
- equality of the two baselines at horizon 4;
- forecast/actual alignment and horizon labels;
- WAPE, seasonal MASE, signed bias, and undefined denominators;
- prediction-coverage failures; and
- an explicit guard against accidental holdout evaluation.

CI uses tiny synthetic fixtures and never requires the 301 MB raw snapshot.
An optional local integration test validates the exact frozen snapshot when the
raw files are available. The standard test command will be:

```text
python -m unittest discover -s tests -v
```

Holdout execution will require an explicit holdout flag and a locked-candidate
manifest whose config hash matches the current configuration. Development
commands must not evaluate holdout rows accidentally.

## Execution and storage

| Asset | Primary location | Synchronization rule |
| --- | --- | --- |
| Code, tests, notebooks, configs, and documentation | Git repository | Git commit/push/pull |
| Raw source snapshot | Private Drive archive plus local cache | Copy only for a deliberate version change; verify hashes |
| Rebuildable interim and processed data | Local or private Drive | Regenerate from raw data; verify manifest before reuse |
| Expensive run checkpoints | Private Drive, versioned by run | Reuse only after metadata validation |
| Final lightweight metrics and figures | Git repository | Update with the code and configuration that produced them |

The current local repository is the active development workspace. The public
GitHub repository is the code synchronization mechanism. Raw data and selected
large checkpoints remain private and outside Git; periodic full-folder copying
to Drive is not part of the normal workflow.

## Path contract

Code will resolve a project-relative `data/` directory by default and permit
the `PROJECT_DATA_ROOT` override. Run outputs similarly use a project-relative
`runs/` directory unless `PROJECT_RUNS_ROOT` is set. Local and Colab physical
paths may differ while preserving the same logical structure:

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

The notebook bootstrap will clone or pull one Git revision, install the package
from `pyproject.toml`, set the data and runs roots, and call source functions.
The final reproducibility run will install the exact lock file. Notebooks do not
silently install unrecorded packages or contain alternate implementations of
SQL, validation, split, or metric logic.
