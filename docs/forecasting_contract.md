# Forecasting Contract

Version: 0.1 draft

Date: 2026-09-20

Status: Must be frozen at Gate 2 before feature engineering

## Target

- Variable: total quarterly coal production by state.
- Unit: reported tons.
- Construction: sum operator-reported `COAL_PRODUCTION` for coal mines across
  subunits and mines within each state-quarter, with explicit null handling.
- Frequency: calendar quarter.

## Forecast structure

- Unit of analysis: state-quarter.
- Structure: grouped panel of state series with a natural national aggregate.
- Primary horizons: 1, 2, 3, and 4 quarters ahead.
- Forecast schedule: quarterly, after the latest quarter's data are available.
- Action lead time: approximately one quarter to one year, subject to the
  publication lag of the source.

Whether forecasts will be reconciled to the national aggregate is an evaluation
question, not a preselected method.

## Information set at each origin

Allowed in principle:

- target history published by the forecast origin;
- calendar information known in advance;
- lagged employment and hours from already published quarters;
- static mine or state attributes that can be shown to have been valid at the
  origin; and
- quality indicators derived only from records available at the origin.

Not allowed:

- future production, employment, hours, or reporting status;
- current master attributes treated as historical snapshots;
- future-informed imputation or scaling;
- selecting entities because they survive to the latest quarter;
- revised values presented as if they were necessarily the first values
  available historically, unless revision limitations are disclosed.

## Output contract

Each forecast record should contain at least:

- forecast origin;
- target quarter;
- horizon;
- state;
- point forecast;
- lower and upper uncertainty bounds when supported;
- actual value when it becomes available;
- baseline and candidate error fields; and
- data-quality or eligibility flags.

The decision-facing output should rank or summarize regions requiring capacity
review while retaining the underlying forecast and uncertainty evidence.

## Decision boundary

The forecast supports regional contractor-capacity planning, market
prioritization, workforce review, and heavy-equipment service readiness. Its
target remains coal production. It must not be presented as a direct forecast
of headcount, fleet requirements, spare-parts demand, or maintenance workload
unless those quantities later receive their own valid data and target contract.

## Evaluation design to freeze

Required design:

- expanding-window or rolling-origin backtesting;
- identical origins and horizons for every compared method;
- errors reported separately for horizons 1 through 4;
- aggregate and state-level performance;
- naive and seasonal-naive baselines before advanced candidates;
- a final untouched recent holdout; and
- explicit treatment of states entering or leaving the reporting panel.

Provisional choices requiring evidence before freeze:

- modeling start date, with 2003Q1 as the leading candidate because most raw
  production nulls occur in 2000-2002;
- minimum history per state at an origin;
- number and placement of validation origins;
- exact final holdout quarters;
- whether latest-quarter data are complete enough for final evaluation; and
- primary and secondary metric definitions.

The modeling start date will not be chosen to force the input below a row-count
threshold. The coal-only input is already below 500,000 rows; any temporal
restriction must be justified by forecast validity.

## Candidate metric logic

No final metric is selected yet. The evaluation design must represent both:

- volume-weighted planning accuracy, because large producing states dominate
  capacity exposure; and
- scale-normalized state accuracy, so performance is not determined by only the
  largest state.

Signed error must also be reported because overprediction and underprediction
have different operational interpretations even though no monetary cost ratio
is currently justified.

## Baseline requirement

At minimum, evaluation must include persistence and annual seasonal persistence
benchmarks. Their exact implementation will be frozen with the evaluation
design. No advanced forecasting model is selected by this contract.

## Change control

After Gate 2, any change to the target, horizon, origin semantics, entity
eligibility, metric set, or holdout requires a dated decision explaining why
the change was necessary and which artifacts must be regenerated.
