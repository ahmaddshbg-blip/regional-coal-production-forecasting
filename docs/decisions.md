# Decision Log

## DEC-001: Local-first hybrid execution

Date: 2026-09-20

Status: Accepted

Decision:

Use the local repository as the active development workspace, Git as the source
of truth for code and documentation, and private Google Drive storage for raw
archives and expensive checkpoints. Colab is the main notebook execution
environment, not the primary project filesystem.

Reason:

Manual full-folder synchronization can create conflicting code, notebook, and
artifact versions. Git provides explicit code history, while Drive remains
appropriate for large private files that should not be committed.

Consequence:

The project must use project-relative paths and an environment-variable data
root override. Colab will pull repository code and mount Drive for notebook
runs without becoming a second source of truth for the project.

## DEC-002: Reduce by domain relevance, not arbitrary date truncation

Date: 2026-09-20

Status: Accepted

Decision:

Retain the complete raw snapshot. Project only required columns, filter to coal
records first, and aggregate to mine-quarter and state-quarter checkpoints. Do
not remove older periods solely to keep the working table below 500,000 rows.

Reason:

The complete source has 2,761,471 rows, but only 344,473 are coal records and
the mine-quarter panel has 183,301 rows. The approved state-quarter target is
smaller still. The relevant working set already meets the intended size while
the long history strengthens seasonal and chronological evaluation.

Consequence:

A later modeling start date remains possible, especially because production
missingness is concentrated in 2000-2002. It must be justified by data quality
or forecast validity rather than computational appearance.

## DEC-003: Use SQL for the relational transformation layer

Date: 2026-09-20

Status: Accepted; DuckDB selected at Gate 3

Decision:

Implement coal filtering, aggregation, and core data-quality summaries in SQL.
Use Python for orchestration, testing, temporal evaluation, forecasting, and
reporting.

Reason:

The source is relational, the required transformations are concise in SQL, and
the resulting query can independently document how raw subunit records become
the forecasting target. An embedded engine is sufficient; a database server is
not justified.

Consequence:

DuckDB will execute versioned SQL against explicit Latin-1 pipe-delimited raw
schemas and write validated Parquet checkpoints. The transformation and null
semantics will be protected by synthetic SQL tests and an optional frozen-
snapshot integration test.

## DEC-004: Colab notebooks are the main analytical interface

Date: 2026-09-20

Status: Accepted

Decision:

Use Google Colab to execute the principal `.ipynb` notebooks. Keep reusable
data, SQL, feature, backtesting, metric, and visualization logic in `.py`
modules or scripts that the notebooks import.

Reason:

The notebook remains the primary interactive analytical narrative, while
Python modules make important logic testable and reusable. This follows the
effective separation used in Project 01 without requiring the complete project
folder to be manually synchronized after every change.

Consequence:

Notebooks must contain setup, orchestration, analysis narrative, and displayed
evidence, but not the only implementation of core pipeline logic. Colab will
pull code from the public GitHub repository and read private raw data through a
configurable Drive path.

## DEC-005: Freeze chronological evaluation before engineering

Date: 2026-09-21

Status: Accepted; Gate 2 complete

Decision:

Use an expanding window beginning `2003Q1`. Development validation uses 54
quarterly origins from `2007Q4` through `2021Q1`. Origins `2021Q2` through
`2022Q1` form a four-quarter evaluation embargo, and the final untouched
holdout uses 12 origins from `2022Q2` through `2025Q1`, with targets ending at
`2026Q1`. Reserve `2026Q2` as the latest forward-forecast origin.

Determine state eligibility at each origin using at least 20 observed quarters
and four consecutive observed quarters ending at the origin. Compare every
method on identical eligible cells against persistence and annual seasonal
persistence. Use horizon-level WAPE as the primary volume metric and
state-balanced seasonal MASE as the secondary metric. Freeze candidate
promotion, uncertainty, and failure criteria in `forecasting_contract.md`.

Reason:

The 2003 start removes the broad early missing-data regime while retaining 54
development origins. A 2013 start would leave only 14 such origins and is more
appropriate as a post-selection sensitivity test. The embargo prevents the
latest horizon-4 development targets from overlapping holdout targets. Dynamic
eligibility avoids survivorship selection and preserves reported zeros.

Consequence:

Holdout performance must remain unseen until one complete candidate procedure
is locked. Gate 3 may now design the implementation, but it cannot change the
target, split, eligibility, baselines, metrics, or thresholds without a dated
change-control decision.

## DEC-006: Freeze the minimal engineering architecture

Date: 2026-09-21

Status: Accepted; Gate 3 complete

Decision:

Use DuckDB 1.5.5 as the embedded SQL engine, explicit raw schemas, and
Zstandard-compressed Parquet checkpoints. Use a flat `src/coal_forecasting`
package, JSON configuration, `PROJECT_DATA_ROOT` and `PROJECT_RUNS_ROOT` path
overrides, standard-library unit tests, and JSON run manifests. Use
`pyproject.toml` for supported direct dependencies and create an exact lock
file only after the first clean Colab implementation passes.

Create files by analytical stage rather than generating the full final tree at
once. Gate 4 creates data and validation code only. Baseline, model, and
uncertainty modules are added when their gates begin.

Reason:

DuckDB reads the source delimiter and Latin-1 encoding directly, expresses the
relational reduction in reviewable SQL, and writes Parquet without a database
server. SQLite would require an unnecessary import stage. A pandas-only raw
transformation would weaken the SQL evidence and use more memory. Adding
Polars, Spark, Docker, orchestration, or experiment-tracking infrastructure
would duplicate capabilities or exceed the project's scale.

The flat package is sufficient for a single forecasting workflow and avoids
empty subpackages. JSON follows the established Project 01 pattern without an
extra parser dependency. Synthetic fixtures keep CI independent of the 301 MB
raw snapshot, while local integration checks preserve confidence in the frozen
data contract.

Consequence:

Gate 4 must implement the configuration and checkpoint contracts in
`architecture.md`, including atomic writes, hashes, schema fingerprints,
deterministic ordering, and failure on raw-snapshot mismatch. Holdout execution
must require an explicit flag and a matching locked-candidate manifest. A model
library cannot be added without a later documented model-class decision.

## DEC-007: Parse the frozen MSHA text exports without quote semantics

Date: 2026-09-21

Status: Accepted during Gate 4 implementation

Decision:

Validate that every physical row has the expected number of pipe delimiters,
then parse the frozen files with quote semantics disabled and remove surrounding
quote characters from fields used by the transformation. Continue reading
`MinesProdQuarterly.txt` directly as Latin-1. Losslessly transcode `Mines.txt`
from Latin-1 byte mappings to temporary UTF-8 before DuckDB ingestion. Do not
persist or publish the temporary copy.

Reason:

The official export contains unescaped internal quotes, so standards-compliant
CSV quote parsing fails on valid source rows. All 2,761,471 quarterly rows have
exactly 12 pipes and all 92,017 mine-master rows have exactly 58 pipes, so no
field relies on quoted embedded delimiters. The mine master also contains C1
bytes that DuckDB rejects under its built-in Latin-1 reader. A streaming UTF-8
transcode preserves every original byte as the corresponding Latin-1 code
point and avoids a network-installed DuckDB extension.

Consequence:

The original file sizes and SHA-256 hashes remain the identity contract. Any
future source snapshot that changes row shape, header, size, or hash fails
before transformation and requires a new dated decision rather than silently
reusing this parser assumption. This decision refines DEC-006's expectation
that both files could be read directly as Latin-1.
