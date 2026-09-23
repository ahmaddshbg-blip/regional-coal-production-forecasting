# Final Baseline Procedure

Status: Frozen and implemented on 2026-09-23; final holdout remains unopened

Decision record: `DEC-018`

Procedure identifier: `horizon_specific_naive_baseline_v1`

## Purpose

The project did not establish material incremental value from either locked
Ridge candidate. The final forecasting procedure therefore retains the
predeclared simple baselines. This is a forecasting result, not a fallback
hidden after holdout inspection: the method, uncertainty calibration, output
schema, and one-time access rule are fixed while the holdout remains unopened.

The procedure prioritizes reproducibility, transparent theory, low compute,
and useful regional planning evidence. It does not claim methodological
novelty.

## Point forecast

Use one fixed rule per horizon:

| Horizon | Rule | Formula |
| ---: | --- | --- |
| H1 | Persistence | `forecast(t+1) = y(t)` |
| H2 | Persistence | `forecast(t+2) = y(t)` |
| H3 | Annual seasonal naive | `forecast(t+3) = y(t-1)` |
| H4 | Persistence | `forecast(t+4) = y(t)` |

H4 is also algebraically identical to annual seasonal naive. H3 retains the
primary comparator frozen before candidate modeling. No holdout result may
change these assignments.

State eligibility, the 20-observation minimum, the four recent consecutive
observations, reported-zero semantics, and scoring rules remain those in the
forecasting contract. There is no target imputation or entity fallback.

## Development-only uncertainty calibration

Use the selected horizon-specific baseline residuals from all 54 development
origins, `2007Q4` through `2021Q1`. For each scored cell define:

```text
normalized_score = abs(forecast - actual) / origin_time_state_MASE_scale
```

For each horizon and nominal coverage of 80 and 95 percent, freeze the finite-
sample conformal order statistic with rank
`ceil((n + 1) * coverage)`, capped at `n`. Also freeze the corresponding
unscaled absolute-error quantile.

For a holdout or latest-origin forecast, multiply the normalized quantile by
the state seasonal MASE scale available at that origin and form a symmetric
interval around the point forecast. Floor the lower bound at zero. If the
current state scale is undefined or non-positive, use the frozen unscaled
quantile and mark the fallback source. Holdout residuals never update either
quantile.

This method does not claim exact exchangeability under temporal dependence.
The holdout report must show empirical coverage, mean and median width,
relative width where defined, Winkler score, and evaluable cell count by
horizon and nominal level.

## One-time final holdout

The final holdout consists of 12 origins from `2022Q2` through `2025Q1`, with
targets no later than `2026Q1`. The implementation must require an explicit
`open_holdout = true` action and write a durable opening marker before reading
holdout target magnitudes.

If a passed manifest already exists for the same snapshot and procedure, a
rerun must validate and reuse its artifacts rather than rescore the holdout. If
an opening marker exists without a passed run, automatic retry is prohibited;
the failure and recovery decision must be documented first.

The holdout report includes point metrics by horizon, state, origin, and
actual-volume band; signed bias; prediction coverage; interval metrics; and
common-cell counts. It estimates final out-of-sample performance only. It does
not trigger model, horizon, threshold, or interval changes.

## Latest-origin forecast

After holdout evaluation, produce unscored forecasts from origin `2026Q2` for
targets `2026Q3` through `2027Q2` using the same locked point and interval
rules. The output must identify snapshot `20260920_1b3a8424_38776a23` and state
that `2026Q2` is the latest available quarter and may be revised by MSHA.

Decision-facing summaries may rank states by near-term H1–H2 forecast volume
and uncertainty width. They are review priorities, not direct forecasts of
headcount, equipment demand, maintenance work, revenue, or causal effects.

## Interpretation boundary

H1 and H2 are the primary operating-planning horizons. H3 and H4 remain in the
report because the project froze a one-to-four-quarter objective before model
results were observed. Longer-horizon deterioration must be disclosed rather
than hidden by shortening the evaluation after the fact.

The final narrative must distinguish:

- observed historical production;
- out-of-sample holdout accuracy;
- latest-origin point forecasts and intervals;
- regional prioritization signals; and
- decisions that still require operational, commercial, or engineering data.

## Required implementation tests

Before Notebook 05 may open the holdout, tests must verify:

- the horizon-to-rule mapping is exact and deterministic;
- holdout origins and target cutoff match the frozen contract;
- development calibration contains no holdout residual;
- finite-sample interval quantiles are fixed before holdout scoring;
- holdout residuals cannot update intervals;
- latest-origin forecasts contain no future actual target;
- every eligible cell receives a finite non-negative point forecast;
- reruns reuse a validated passed run;
- an opening marker without a passed run blocks automatic retry; and
- manifests distinguish `holdout_opened` from candidate confirmation, which
  remains unopened.
