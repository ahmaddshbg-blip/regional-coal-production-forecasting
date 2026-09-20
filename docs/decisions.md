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
obtain code through Git when the remote is established and read private raw data
through a configurable Drive path.
