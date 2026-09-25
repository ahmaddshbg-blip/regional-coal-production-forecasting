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
Python modules make important logic testable and reusable without requiring
the complete project folder to be manually synchronized after every change.

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
empty subpackages. JSON provides a compact configuration format without an
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

## DEC-013: Freeze model-specific diagnostics and the iteration boundary

Date: 2026-09-23

Status: Accepted before candidate implementation

Decision:

Add a formal diagnostic gate to `pooled_direct_ridge_log_change_v1`. Separate
hard temporal and data-validity requirements from model-working assumptions
and uncertainty assumptions. Run model diagnostics on the 36-origin selection
block after alpha selection but before opening candidate results from the
18-origin confirmation block.

Hard failures include leakage, preprocessing outside the training boundary,
post-development targets, missing required features, incomplete or non-finite
predictions, target imputation, nondeterminism, and recursive candidate inputs.
They must be fixed before evaluation continues.

The selection diagnostic report must examine transformed functional form,
raw-scale bias, residual dependence at origin lags one and four,
heteroskedasticity and scale normalization, state pooling, coefficient
stability, zero-floor frequency, and feature conditioning. Residual normality,
constant variance, stationarity of target levels, and serial independence are
not universal point-forecast rejection rules for this regularized direct
model. They are interpreted according to their effect on forecast adequacy,
coefficient claims, or interval calibration.

Reason:

The project already follows a systematic problem, data, EDA, baseline, and
candidate-design sequence, but `DEC-012` did not state an explicit diagnostic
return path. Model-specific assumptions must be examined without either
forcing classical inference assumptions onto a predictive model or ignoring
residual evidence that can invalidate uncertainty claims.

Consequence:

A hard implementation failure returns to the relevant engineering stage. A
material specification problem found on the selection block may be accepted as
a documented limitation or may create a new procedure identifier and dated
decision before confirmation is opened. After confirmation results are seen,
they cannot be used for retuning; failure is reported. Holdout results can
never revise the procedure. The full diagnostic specification is part of
[`candidate_procedure.md`](candidate_procedure.md).

## DEC-014: Reject the log-change Ridge candidate before confirmation

Date: 2026-09-23

Status: Rejected at the selection diagnostic gate

Decision:

Reject `pooled_direct_ridge_log_change_v1` using selection run
`20260923T062835Z_3831181d_38d675`. Do not open its confirmation results and do
not patch its transformation, bias, features, or alpha grid under the same
procedure identifier.

Evidence:

- All 41 implementation tests passed and every one of the 3,744 candidate
  forecasts was finite and scored. No confirmation or holdout origin was read.
- Alpha `100` was best among the four frozen values, but all values had
  negative mean WAPE skill. The selected mean skill was `-0.5271`.
- Paired four-quarter moving-block bootstrap intervals were negative for H3,
  H4, and the equal-weight horizon mean. The mean-skill 95 percent interval was
  `[-1.0076, -0.0209]`.
- Candidate WAPE was 8.93, 13.99, 17.19, and 20.12 percent for H1 through H4,
  versus comparator WAPE of 7.85, 10.27, 10.32, and 10.35 percent.
- Aggregate signed bias was `-3.10`, `-9.53`, `-12.72`, and `-15.44` percent.
  Under the frozen `forecast - actual` convention, v1 increasingly
  underforecast production.
- Underforecasting concentrated in the highest fitted-value and level deciles.
  Median within-state lag-one residual correlation was `0.459`, `0.640`, and
  `0.764` at H2 through H4, indicating remaining dynamics.
- Zero-floor rates stayed below 0.6 percent, all states were represented in
  training, numeric condition numbers stayed below 2.9, and feature exclusion
  counts were negligible. These checks do not support blaming the failure on
  coverage, unseen categories, or numerical instability.

Interpretation:

The unweighted squared-error fit on `log1p` changes is misaligned with the
raw-ton WAPE decision metric. Inverse transformation also converts an adequate
conditional log forecast into a systematically low raw-scale point forecast
when dispersion is material. Regularized common dynamics do not remove the
long-horizon dependence left in residuals.

Consequence:

V1 is a completed failed experiment. Its artifacts remain reproducible, but it
cannot enter confirmation. One successor may be specified from this diagnosed
mechanism; it must be frozen under a new identifier before implementation and
must stop permanently at the selection gate if it does not improve on the
frozen comparator.

## DEC-015: Freeze a raw-delta persistence-anchored Ridge successor

Date: 2026-09-23

Status: Accepted before v2 implementation

Decision:

Freeze `pooled_direct_ridge_raw_delta_v2` as the single authorized successor.
Fit four direct pooled Ridge models to raw-ton changes from persistence, with
no intercept so complete shrinkage returns exactly to persistence. Use origin-
safe raw level, three raw quarterly changes, recent zero count, calendar time,
target quarter, and state. Standardize numeric features within each outer
training boundary and retain equal row weights.

Use the fixed alpha grid `1`, `100`, `10000`, and `1000000`, selecting one
shared alpha on the same 36-origin selection block with the existing WAPE-skill
and tie rule. Keep the same prequential interval and paired moving-block
bootstrap procedures. The complete specification is recorded in
[`candidate_procedure_v2.md`](candidate_procedure_v2.md).

Reason:

This is a mechanism-based correction, not an unrestricted model search. Raw-
delta fitting removes the inverse-log point-forecast bias and makes the loss
sensitive to tonnage errors that drive WAPE. The zero-intercept correction
nests persistence as alpha becomes large, so the candidate cannot invent a
global drift when all learned corrections should shrink away.

Consequence:

V2 must be implemented test-first and evaluated only on the selection block.
Its raw-scale linearity, volume concentration, coefficient stability, residual
dependence, and interval calibration require the same explicit review. If v2
fails the selection gate, retain the frozen baseline and stop candidate-family
iteration; do not create v3. Confirmation and holdout remain closed.

## DEC-016: Reject v2 and stop candidate-family iteration

Date: 2026-09-23

Status: Rejected at the selection diagnostic gate

Decision:

Reject `pooled_direct_ridge_raw_delta_v2` using selection run
`20260923T065208Z_3831181d_e59ae8`. Retain the frozen horizon-specific baseline
and stop candidate-family iteration. Do not open candidate confirmation or
holdout results, and do not create a v3 to search for a favorable result.

Evidence:

- All 46 tests passed, prediction coverage was 100 percent, and all 3,744
  selection forecasts were scored without reading later origins.
- Alpha `10000` maximized the frozen selection objective. Mean horizon WAPE
  skill was `0.0063`, below the required `0.05` materiality threshold.
- The paired moving-block bootstrap 95 percent interval for mean skill was
  `[-0.0220, 0.0294]`; improvement was not robustly distinguishable from zero.
- Skill was `0.0061`, `0.0290`, `-0.0115`, and `0.0017` at H1 through H4.
  The three-of-four positive-skill condition passed exactly, but H3 remained
  negative and the materiality and state-balanced criteria failed.
- The equal-weight mean of horizon median state MASE was `1.1112`, worse than
  the fixed comparator value of `1.0796`.
- Nominal 80 percent interval coverage ranged from 78.2 to 81.2 percent and 95
  percent coverage ranged from 95.2 to 95.6 percent. Interval calibration
  passed, but it cannot compensate for immaterial point skill.
- Median within-state lag-one residual correlation was `0.398` at H3 and
  `0.503` at H4. Zero-floor use rose from 5.9 percent at H1 to 10.0 percent at
  H4, concentrated in low-output cases.

Interpretation:

The raw-delta response fixed v1's scale mismatch and returned performance close
to persistence, as intended by its nested design. It did not establish useful
incremental forecasting value. The result supports the simple baseline rather
than another model-family search on the same selection data.

Consequence:

The project may publish the two failed, leakage-safe candidate experiments as
evidence of disciplined model governance and retain persistence at H1, H2, and
H4 and seasonal naive at H3 for the current planning forecast. Candidate
confirmation and the final comparative holdout remain unopened because no
candidate qualified to enter them. A future new experiment would require a
newly dated research question, procedure, and evaluation policy rather than a
continuation of this search.

## DEC-017: Accept Colab candidate reproduction and retain the baseline

Date: 2026-09-23

Status: Accepted after clean Colab reproduction of notebook 04

Decision:

Accept the clean Colab reproduction of both selection-only candidate
experiments at code revision `7a441b6d77b12d0dfca02908d95b4931d001d57a`.
Retain the frozen horizon-specific baseline as the forecasting method to carry
forward. Close candidate selection without opening confirmation or holdout and
without authorizing another candidate family.

Evidence:

- The notebook completed all cells without an error and the test subprocess
  returned zero.
- The v1 run was `20260923T131252Z_7a441b6d_22fd1d`; the v2 run was
  `20260923T131621Z_7a441b6d_528dfc`.
- Both manifests use validated data run
  `20260921T130122Z_770aedae_bbefbe` and accepted baseline run
  `20260921T144811Z_62a3b84d_41560a`.
- Both manifests record a clean Git worktree, `confirmation_opened = false`,
  and `holdout_opened = false`.
- Selected alphas, point metrics, bootstrap intervals, residual diagnostics,
  interval coverage, and promotion decisions reproduce the local results.
- Six NumPy warnings came from correlations with constant residual sequences;
  the affected correlations were already undefined and did not change model
  metrics. A later guarded implementation removes those warnings.

Consequence:

The candidate-selection stage is complete. Before any final holdout values are
read, the project must freeze a simple final-baseline procedure, its
development-only uncertainty calibration, the one-time holdout report, and the
latest-origin forecast outputs. The final method will emphasize H1 and H2 for
near-term operating decisions while preserving H1 through H4 to avoid changing
the evaluation horizon after observing results.

## DEC-018: Freeze the final simple-baseline forecasting procedure

Date: 2026-09-23

Status: Accepted before final-holdout implementation

Decision:

Freeze `horizon_specific_naive_baseline_v1` as the final method. Use
persistence at H1, H2, and H4 and annual seasonal naive at H3. Emphasize H1 and
H2 for near-term planning while continuing to report all four horizons.

Calibrate 80 and 95 percent state-scale-normalized conformal intervals using
only the selected baseline residuals from all 54 development origins. Freeze
the horizon-specific normalized and unscaled quantiles before any holdout
target is read. Evaluate the method once on the 12 holdout origins and then
produce unscored forecasts from `2026Q2` through `2027Q2`. The complete
specification is recorded in
[`final_baseline_procedure.md`](final_baseline_procedure.md).

Reason:

The objective is to produce a defensible forecasting workflow with clear data,
documentation, and business interpretation rather than propose a novel or
computationally heavy model. Both candidate experiments failed the
predeclared improvement criteria, while the simple baselines remained strong,
transparent, inexpensive, and operationally interpretable.

Alternatives:

No new ARIMA search, tree ensemble, neural model, or hybrid candidate is
authorized. Reducing the report to H1 and H2 after seeing model results was
also rejected because it would change the frozen evaluation contract. H1 and
H2 receive interpretation priority without hiding H3 and H4.

Consequence:

The holdout remains unopened at this decision. Implementation must be
test-first, require an explicit one-time opening action, and preserve a durable
marker that prevents silent rescoring. Notebook 05 may be created only as the
interface to this exact procedure. Holdout results cannot revise the method.

## DEC-019: Accept the final holdout result without retuning

Date: 2026-09-23

Status: Accepted after reviewed Colab execution of notebook 05

Decision:

Accept final run `20260923T152725Z_8c9ab4d8_e93091` as the one-time holdout
evidence for `horizon_specific_naive_baseline_v1`. Close model evaluation and
retain the point procedure unchanged. Publish the uncertainty result as a
conservative interval failure rather than recalibrating it after holdout.

Evidence:

- All 54 tests passed and the executed notebook contains no error output.
- The run used code revision
  `8c9ab4d8aefc45d45ce63b3b2cbb528b54038054`, the accepted data run, baseline
  run, and frozen snapshot, with a clean worktree.
- The manifest records `holdout_opened = true`,
  `candidate_confirmation_opened = false`, and unscored latest forecasts.
- Prediction coverage is 100 percent at every horizon. WAPE is 9.04 percent at
  H1 and between 10.46 and 10.66 percent at H2-H4.
- Aggregate signed bias is positive and rises from 1.04 percent at H1 to about
  4.2 percent at H3-H4.
- Pooled empirical interval coverage is 94.16 percent for the nominal 80
  percent interval and 98.97 percent for the nominal 95 percent interval. Both
  exceed the frozen upper guardrail and the intervals are excessively wide.
- The reviewed notebook was a validated reuse of the passed run rather than a
  second scoring attempt.

Reason:

The point forecast provides transparent, reproducible baseline-level accuracy
for the stated regional planning use. The interval result does not meet
its nominal calibration objective, but hiding that failure or tuning after the
holdout would invalidate the project governance. Honest limitation reporting
is more valuable than forcing a cosmetically successful uncertainty result.

Consequence:

The forecasting workflow is complete. Final claims must use the point
metrics and regional forecasts with the limits in
[`final_results.md`](final_results.md). Intervals may be described only as
conservative review ranges. Candidate confirmation stays closed, and no model,
interval, threshold, or interpretation may be revised from this holdout. A new
method would require a new dated experiment and a genuinely untouched future
evaluation period.
