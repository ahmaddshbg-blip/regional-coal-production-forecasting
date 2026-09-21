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

Status: Accepted in principle; engine selection deferred to Gate 3

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

The SQL query will be versioned and tested. The engine will be selected only
after compatibility, null behavior, dependency cost, and reproducible execution
are assessed at the engineering-design gate.

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
