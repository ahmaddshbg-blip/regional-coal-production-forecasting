# Forecasting Contract

Version: 1.0

Date frozen: 2026-09-21

Status: Frozen at Gate 2 before feature engineering

## Target

- Variable: total quarterly coal production by state.
- Unit: reported tons.
- Construction: sum operator-reported `COAL_PRODUCTION` for coal mines across
  subunits and mines within each state-quarter, with the null-preserving rules
  in `data_quality_policy.md`.
- Frequency: calendar quarter.

## Forecast structure

- Unit of analysis: state-quarter.
- Structure: grouped panel of state series with a natural aggregate.
- Primary horizons: 1, 2, 3, and 4 quarters ahead.
- Forecast schedule: quarterly, after the latest quarterly snapshot is
  available.
- Action lead time: approximately one quarter to one year, subject to source
  publication lag.

Whether forecasts should later be reconciled to an aggregate remains an
evaluation question, not a preselected method.

## Forecast-origin semantics

An origin labelled quarter `t` means that the forecasting method may use only
records through quarter `t`. The actual operational forecast would be created
after MSHA publishes the corresponding snapshot, not on the final calendar day
of quarter `t`.

The portal does not expose historical vintages. Backtesting therefore uses the
frozen 2026-09-20 snapshot and must be described as latest-vintage
chronological evaluation, not true vintage or pseudo-real-time evaluation.

## Information set at each origin

Allowed in principle:

- target history through the origin;
- calendar information known in advance;
- lagged employment and hours from quarters available by the origin;
- static mine or state attributes shown to have been valid at the origin; and
- quality indicators derived only from records available at the origin.

Not allowed:

- future production, employment, hours, or reporting status;
- current master attributes treated as historical snapshots;
- future-informed imputation, scaling, or entity selection;
- selecting entities because they survive to the latest quarter; and
- revised values presented as original historical vintages.

Every future feature must document when it would have been known. Features
without defensible prediction-time availability are excluded.

## Modeling window

The primary modeling window begins at `2003Q1`.

Evidence:

- 5,997 of 6,018 all-null mine-quarter observations occur during 2000-2002;
- the broad missing-production regime ends after `2002Q4`;
- the 2003 start retains 94 quarters through `2026Q2`; and
- it provides 54 quarterly development origins under the eligibility rule
  below.

A `2013Q1` start is reserved as a post-selection robustness check. It is not
the primary design because the same 20-quarter minimum would leave only 14
development origins before the evaluation embargo. The sensitivity result
must not be used to retune a model after the final holdout is opened.

## State eligibility

Eligibility is determined independently at every forecast origin. A state is
eligible when:

1. it has at least 20 non-null state-quarter targets from `2003Q1` through the
   origin;
2. its target is non-null in each of the four consecutive quarters ending at
   the origin; and
3. all methods being compared can receive the same allowed information set.

Twenty observations provide five annual seasonal cycles while preserving 54
development origins. The four-quarter continuity rule ensures that both fixed
baselines are defined without imputing the target.

The rule is dynamic and does not use future survival. A state can enter after
it accumulates sufficient history, leave when recent reporting is absent, and
re-enter after four consecutive observed quarters. Reported zero remains an
observation and does not make a state ineligible.

Forecasts must be produced for every eligible state-origin-horizon cell. A cell
is scored only when its future target is non-null. Unscored forecasts remain in
the output with a reason flag; their actual is never replaced by zero. A method
that fails to predict an otherwise baseline-comparable cell fails the required
100 percent prediction-coverage check.

Observed eligibility transitions in the frozen snapshot include:

- 26 eligible states at the first development origin, `2007Q4`;
- 24 to 26 eligible states across development origins;
- Arkansas leaving at `2018Q4` and re-entering at `2023Q1`;
- Arizona leaving at `2021Q1` and re-entering at `2022Q1`;
- Kansas leaving at `2023Q1`; and
- Oklahoma leaving at `2024Q2`.

Nevada has only one observed zero-production quarter and never qualifies.
These transitions are evidence for dynamic eligibility, not a manually fixed
state list.

## Chronological split

All estimation windows expand from `2003Q1` through the applicable origin.
Every compared method uses identical origins, horizons, eligible states, and
scoring cells.

### Development validation

- Origins: every quarter from `2007Q4` through `2021Q1`.
- Number of origins: 54.
- Latest validation target: `2022Q1` at horizon 4.
- Purpose: baseline characterization, feature and candidate selection,
  hyperparameter selection, and pre-holdout acceptance checks.

### Evaluation embargo

Origins `2021Q2` through `2022Q1` are not scored as development or holdout
origins. This four-origin gap prevents targets used by horizon-4 development
forecasts from overlapping the final holdout target period. Observations in
the gap may still become training history at a later holdout origin.

### Final untouched holdout

- Origins: every quarter from `2022Q2` through `2025Q1`.
- Number of origins: 12.
- Forecast targets: up to `2026Q1` at horizon 4.
- Access rule: do not calculate candidate holdout performance until one method,
  feature set, hyperparameter policy, and interval procedure are locked from
  development validation.
- Only timestamp availability and origin-time eligibility were inspected while
  defining the split. No holdout target magnitudes, baseline errors, or
  candidate errors were used.
- After opening the holdout, no model or threshold may be changed because of a
  holdout result. Any later change creates a new experiment and a newly dated
  holdout policy.

### Latest production origin

`2026Q2` is excluded from scored evaluation and retained as the latest
available origin for the eventual forward forecast of `2026Q3` through
`2027Q2`. Its values may be revised by MSHA, so the final output must identify
the source snapshot and revision caveat.

## Baselines

Two baselines are mandatory and fixed before candidate modeling.

### Persistence

For origin `t` and horizon `h`:

```text
forecast(t + h) = actual(t)
```

### Annual seasonal persistence

For quarterly data:

```text
forecast(t + h) = actual(t + h - 4)
```

All required seasonal values are known at origin `t` for horizons 1 through 4.
At horizon 4, annual seasonal persistence is algebraically identical to the
persistence baseline because both use `actual(t)`.

## Pre-holdout baseline evidence

The following results use only the 54 development origins. They are Gate 2
design-audit values used to freeze the evaluation rules, not final published
benchmark artifacts. Gate 5 must reproduce them with tested, versioned
evaluation code before candidate modeling. Holdout performance has not been
calculated.

| Horizon | Scored cells | Persistence WAPE | Seasonal WAPE | Persistence median state MASE | Seasonal median state MASE |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1,391 | 8.48% | 11.02% | 0.709 | 1.238 |
| 2 | 1,390 | 11.04% | 11.13% | 0.921 | 1.223 |
| 3 | 1,389 | 11.28% | 11.26% | 1.086 | 1.198 |
| 4 | 1,388 | 11.39% | 11.39% | 1.192 | 1.192 |

The fixed primary WAPE comparator is persistence for horizons 1 and 2,
seasonal persistence for horizon 3, and their common forecast for horizon 4.
The fixed secondary MASE comparator is persistence for horizons 1 through 3
and the common horizon-4 forecast.
Both baselines must still be shown in final results. The near ties at horizons
2 and 3 are a reason not to claim that either simple rule is universally
superior.

## Metrics

### Primary volume metric

Report WAPE separately for every horizon:

```text
WAPE = sum(abs(forecast - actual)) / sum(actual)
```

WAPE is computed across eligible scored state cells. It is defined with a
pooled denominator, so individual zero-production observations do not cause
division by zero. The overall summary is the unweighted mean of the four
horizon-level WAPE values; horizons are not pooled into one observation set.

Forecast skill against the fixed horizon-specific comparator is:

```text
WAPE skill = 1 - candidate WAPE / comparator WAPE
```

### State-balanced metric

Use quarterly seasonal MASE. For each state and origin, the scale is the mean
absolute `lag-4` difference in the training history available at that origin.
Absolute forecast error is divided by that scale, then averaged within each
state and horizon. Report the median and mean across states.

If a state has a zero seasonal scale, its MASE is undefined rather than forced
to zero; report the number and share of defined values. MASE was defined for
100 percent of development baseline cells in the frozen snapshot.

### Required diagnostics

Also report:

- MAE and RMSE in tons;
- signed mean error in tons;
- aggregate signed bias as a percentage of actual volume;
- errors by horizon, state, origin, volume band, and relevant operating regime;
- prediction coverage and unscored-cell reasons; and
- aggregate error over the common eligible-state set.

MAPE and sMAPE are not primary metrics because genuine zeros and low-volume
states can make percentage errors unstable or misleading.

## Candidate promotion and failure criteria

A candidate may enter the untouched holdout only if development validation
shows all of the following:

1. 100 percent predictions for baseline-comparable cells;
2. at least 5 percent mean WAPE skill when the four horizons are weighted
   equally;
3. positive WAPE skill in at least three of four horizons;
4. no horizon with WAPE skill below -5 percent; and
5. an equal-weight mean of horizon-level median state MASE no worse than the
   fixed secondary comparator.

The 5 percent threshold is a practical materiality guardrail, not a financial
cost claim. It is larger than the less-than-1-percent relative WAPE separation
between the two baselines at horizons 2 and 3, preventing promotion for a
negligible ranking change.

Use a paired moving-block bootstrap over forecast origins, with four-quarter
blocks, to report a 95 percent confidence interval for WAPE skill. A candidate
whose point estimate passes but interval includes zero is labelled promising
but not robustly superior.

Only one locked candidate procedure enters the final holdout. The same
thresholds are interpreted on holdout without retuning. If no candidate passes,
or if holdout skill is non-positive overall, retain the appropriate baseline
and state clearly that added predictive value was not established. That is a
valid project result, not a reason to search models until one wins.

## Uncertainty evaluation

The final retained method must provide uncertainty intervals or document why a
defensible interval could not be produced. Interval construction and any
calibration may use training and development residuals only, never holdout
residuals.

Evaluate nominal 80 and 95 percent intervals by horizon using:

- empirical coverage;
- mean and median interval width;
- width relative to actual volume where defined; and
- Winkler interval score.

As calibration guardrails, pooled coverage should fall between 75 and 85
percent for the nominal 80 percent interval and between 90 and 98 percent for
the nominal 95 percent interval. State-level coverage is descriptive when a
state has fewer than 20 scored intervals. Passing coverage with excessively
wide intervals is not sufficient; width and interval score must be reported.

## Output contract

Each forecast record must contain at least:

- forecast origin and source snapshot;
- target quarter and horizon;
- state;
- eligibility and scoring flags;
- point forecast;
- lower and upper uncertainty bounds when supported;
- actual value when available;
- baseline and candidate error fields; and
- data-quality or exclusion reason flags.

The decision-facing output may rank or summarize regions requiring capacity
review, but it must retain the forecast, uncertainty, and error evidence.

## Decision boundary

The forecast supports regional contractor-capacity planning, market
prioritization, workforce review, and heavy-equipment service readiness. Its
target remains coal production. It must not be presented as a direct forecast
of headcount, fleet requirements, spare-parts demand, maintenance workload,
financial impact, or causal effects.

## Change control

Any change to the target, modeling start, origin schedule, embargo, holdout,
entity eligibility, baseline definitions, metric set, promotion thresholds, or
uncertainty criteria requires a dated decision explaining:

- why the change is necessary;
- whether holdout information was already seen;
- which code, notebooks, metrics, figures, and reports must be regenerated;
  and
- whether a new untouched evaluation period is required.
