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

## DEC-008: Close Gate 4 on cross-environment reproduction

Date: 2026-09-21

Status: Accepted; Gate 4 complete

Decision:

Accept clean Colab run `20260921T130122Z_770aedae_bbefbe` as the Gate 4
reproduction and freeze its project dependency closure in
`requirements-lock.txt`. Keep the executed notebook and private run manifest
outside Git; retain the clean notebook, lock, configuration, SQL, tests, and
rebuild instructions publicly.

Evidence:

- code revision `770aedae8d2308e2b757a6713ad0bf8b05d99b62`;
- all ten synthetic tests returned success;
- 183,301 mine-quarter rows, 1,142,527 bytes, SHA-256
  `8d757383289b59de1d297b4ab1df578d2d87f5e30a5650ff519ce1a7cd92a78f`;
- 2,718 state-quarter rows, 46,910 bytes, SHA-256
  `f18fcfaac7fbeb87c180a89de9077a67b8ab36846824e39bd56bc1712c5782ea`;
- identical checkpoint hashes in local Windows and Google Colab runs; and
- 27 states or territories, 2000Q1 through 2026Q2, with zero null regional
  targets in the observed state-quarter checkpoint.

Consequence:

Gate 5 may implement only the already frozen persistence and seasonal-naive
baselines plus their chronological evaluation tests. This decision does not
authorize a candidate model, holdout evaluation, or performance claim.

## DEC-009: Guard exploratory target values at the development boundary

Date: 2026-09-21

Status: Accepted before time-series EDA

Decision:

Limit every exploratory use of production magnitude to `2003Q1` through
`2022Q1`, the latest target used by the frozen development origins. Permit
structural coverage and eligibility checks through `2026Q2` only when later
production magnitudes are masked before entering pandas. Treat reported zero
as observed, preserve null and absent-row distinctions, and flag unusual
changes without removing, winsorizing, or imputing them. Trace flags to the
mine-quarter checkpoint only within the development target window.

Disclosure:

The Gate 4 notebook initially rendered one national aggregate production
series through `2026Q2` before model or candidate work began. This exposed the
aggregate path of later target values, so the project will not claim that no
post-development magnitude was ever viewed. No state-level holdout values,
baseline or candidate holdout errors, or holdout performance were inspected,
and no evaluation choice was changed in response. Notebook 01 is truncated at
`2022Q1`, and Notebook 02 prevents later magnitudes from entering its Python
analysis frame.

Reason:

EDA is necessary before baseline implementation, but inspecting later target
magnitudes could influence transformations, anomaly treatment, feature design,
or model choice. The explicit boundary preserves the intended development-only
workflow while recording the limited aggregate exposure honestly.

Consequence:

The final holdout-performance gate remains closed. Public claims must
distinguish an unopened holdout evaluation from the stronger and no longer
accurate claim that every aggregate post-development target value remained
unseen.

## DEC-010: Close pre-baseline EDA without target correction

Date: 2026-09-21

Status: Accepted after clean Colab reproduction of notebook 02

Decision:

Retain the validated state-quarter target exactly as constructed. Do not
impute absent quarters, replace reported zeros, remove flagged changes,
winsorize production, or select a target transformation before baseline
evaluation. Continue to determine state eligibility independently at each
forecast origin under the frozen rule. Proceed next to tested persistence and
annual seasonal-persistence backtesting; do not select a candidate model from
EDA alone.

Evidence:

- Colab executed code revision
  `82f901965e780e79324d25d6c0f566a31025bb02` with all 16 tests passing and
  validated run `20260921T130122Z_770aedae_bbefbe`.
- The full structural grid has 144 absent state-quarter cells. The development
  value window contains 1,988 rows, 27 represented states, zero null targets,
  and 114 reported-zero targets.
- Wyoming contributes approximately 39.3 percent of development-window volume.
  The quarterly top-five state share ranges from 68.1 to 75.0 percent, which
  reinforces the need to report both pooled WAPE and state-balanced MASE.
- Median calendar-quarter shares range only from 24.8 to 25.4 percent across
  467 complete state-years. This does not justify discarding the frozen annual
  seasonal baseline, but it provides no evidence for assuming strong common
  seasonality across states.
- Average national quarterly production in 2021 was approximately 46 percent
  below 2003, with visible structural declines and a large 2020 disruption.
  Baselines must therefore be characterized by origin and regime, not only by
  one aggregate score.
- The robust diagnostic retains 91 flagged state-quarter changes across 18
  states, including 26 in 2020 and 21 whose current target is zero. The 3,728
  associated mine-quarter rows contain no all-null or partially-null production
  aggregates, so the flags do not provide evidence of a missing-value defect.
- Development eligibility remains within the frozen range of 24 to 26 states,
  and the observed entry and exit transitions reproduce the forecasting
  contract.

Consequence:

EDA creates no data-remediation blocker and does not authorize model or feature
selection. Notebook 03 may implement the two frozen baselines, prediction-cell
coverage checks, horizon-level metrics, and origin/state diagnostics using only
development origins. Final holdout performance remains unopened.

## DEC-011: Close the development baseline gate before candidate design

Date: 2026-09-21

Status: Accepted after clean Colab reproduction of notebook 03

Decision:

Accept baseline run `20260921T144811Z_62a3b84d_41560a` at code revision
`62a3b84d8d7a7617ac8fc3798b053adb9ac97e7d` as the development benchmark.
Keep the holdout closed. Before implementing a candidate model or creating
notebook 04, freeze one complete candidate procedure: forecast strategy by
horizon, information set available at each origin, feature construction,
state-pooling rule, fitting and tuning boundary, deterministic settings, and
uncertainty method. Actual-volume bands remain diagnostic outputs and cannot
be used as prediction-time features because their labels depend on future
actuals.

Evidence:

- The executed notebook completed without cell errors, ran the full test suite,
  recorded a clean worktree, and wrote passed manifests and hashed artifacts.
- The evaluator produced 11,144 forecast rows over 54 development origins and
  horizons one through four with 100 percent prediction coverage. Scored cells
  were 1,391, 1,390, 1,389, and 1,388 as frozen at Gate 2.
- Persistence WAPE was 8.48, 11.04, 11.28, and 11.39 percent. Annual seasonal
  persistence WAPE was 11.02, 11.13, 11.26, and 11.39 percent. The corresponding
  median state MASE values also reproduced the frozen audit exactly.
- Persistence is the reference comparator at horizon 1, remains marginally
  better at horizon 2, seasonal persistence is marginally better at horizon 3,
  and both formulas are identical at horizon 4. The near ties do not justify
  choosing a candidate from a single aggregate comparison.
- Mean signed error is positive for both methods and grows with horizon. Under
  the frozen `forecast - actual` convention, this is systematic overforecasting
  during a generally declining and disrupted development period.
- Origin-level WAPE contains pronounced spikes, average state MASE varies
  materially, and low-volume state-quarters have much larger relative error
  than very-high-volume state-quarters. A candidate must therefore be assessed
  across origins, states, and volume diagnostics rather than only pooled WAPE.

Consequence:

The baseline implementation and reproduction stage is complete, but no
candidate has been selected. The next work product is a documented candidate
design that responds to trend or regime change and cross-state heterogeneity
without using unavailable future information. Promotion thresholds and the
untouched holdout policy remain unchanged.

## DEC-012: Freeze one pooled direct Ridge candidate procedure

Date: 2026-09-23

Status: Accepted before candidate implementation

Decision:

Freeze `pooled_direct_ridge_log_change_v1` as the only candidate procedure for
the current development experiment. Fit four direct global Ridge regressions,
one per horizon, to predict the `log1p` production change from the persistence
forecast. Use only the current and preceding three observed state targets,
recent log changes, recent zero count, calendar time, target quarter, and state
identifier. Pool historical states, regularize state indicators, refit at every
origin, and prohibit recursive candidate inputs.

Freeze the alpha grid at `0.1`, `1.0`, `10.0`, and `100.0`. Select one shared
alpha using development origins `2007Q4` through `2016Q3`; use `2016Q4` through
`2021Q1` only as an unrevised confirmation diagnostic. Use origin-safe pooled
conformal residual intervals normalized by the state seasonal MASE scale, with
the first eight development origins as calibration warm-up. Use 2,000 paired
four-quarter moving-block bootstrap replications with seed `20260920` for skill
uncertainty. The complete executable specification is recorded in
[`candidate_procedure.md`](candidate_procedure.md).

Evidence:

- Persistence's positive `forecast - actual` bias grows with horizon, so a
  baseline-relative trend correction tests a failure visible before candidate
  modeling.
- EDA finds weak common aggregate seasonality, long-run decline, a major 2020
  disruption, and substantial cross-state scale and error heterogeneity.
- The four most recent targets are guaranteed for every eligible forecast
  cell. Longer fixed lags are not guaranteed and would threaten the required
  100 percent prediction coverage.
- A global regularized model borrows information across the 24 to 26 eligible
  states while state indicators and state-specific lag values preserve regional
  differences. It remains simpler and more auditable than local order search or
  nonlinear tree boosting.
- Employment, hours, mine counts, and current mine-master fields do not yet
  have an approved prediction-time role. Excluding them keeps the first
  candidate's information set defensible.

Alternatives:

Local damped-trend or ETS models were not selected because they do not pool
information and create state-level fit and interval failure modes for short or
interrupted histories. Per-state ARIMA order search would multiply low-sample
choices. Global tree boosting is deferred because its nonlinear flexibility
and larger tuning surface are not yet justified. No alternate family is
authorized automatically if Ridge fails.

Consequence:

Candidate design is now frozen, but no model has been implemented or scored.
The next gate may add the model dependency, tested feature and candidate
modules, development-only evaluation artifacts, and notebook 04. Any change to
the transformation, features, pooling, window, alpha policy, interval method,
or bootstrap after candidate results requires a new dated decision. The final
holdout remains unopened, and all promotion thresholds remain unchanged.
