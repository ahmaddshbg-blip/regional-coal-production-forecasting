# Candidate Procedure V2

Status: Rejected at the selection diagnostic gate on 2026-09-23

Decision record: `DEC-015`

Procedure identifier: `pooled_direct_ridge_raw_delta_v2`

Selection run: `20260923T065208Z_3831181d_e59ae8`

## Selection outcome

V2 passed all implementation-validity and coverage checks but did not pass the
frozen promotion criteria. The selected alpha was `10000`. Equal-weight mean
WAPE skill was only `0.0063`, below the required `0.05`, and its paired block-
bootstrap 95 percent interval was `[-0.0220, 0.0294]`. H3 skill was negative,
and the candidate's equal-weight mean horizon median state MASE was `1.1112`,
worse than the comparator's `1.0796`.

The raw-delta specification removed v1's severe underforecasting and produced
well-calibrated prequential intervals, but its point improvement was not
material or robust. Zero flooring also rose from 5.9 percent at H1 to 10.0
percent at H4, and lag-one residual dependence remained material at H3 and H4.
No confirmation or holdout origin was opened. Per `DEC-016`, the candidate
search stops and the appropriate baseline is retained.

## Purpose and hypothesis

V1 failed before confirmation because an equally weighted log-change loss
produced severe raw-ton underforecasting in high-volume states and left strong
long-horizon residual dependence. V2 tests one bounded response to that
diagnosis: learn a direct raw-ton correction to persistence while retaining a
strongly regularized global linear model.

This is the last candidate-family iteration authorized before confirmation.
It is not a search over transformations or model families.

## Forecast and training contract

- Forecast eligible state-origin cells at horizons one through four.
- Fit one separate direct pooled model per horizon and refit at every origin.
- Use an expanding history beginning at `2003Q1`.
- A pseudo-origin `u` enters training only when its current and preceding three
  targets are observed, its label at `u+h` is observed, and `u+h <= t` for the
  outer origin `t`.
- Preserve reported zeros and exclude incomplete training rows without target
  imputation.
- Prohibit recursive candidate inputs.

## Response and forecast

For production `y`, fit:

```text
response(s, u, h) = y(s, u + h) - y(s, u)
forecast(s, t, h) = max(0, y(s, t) + predicted_delta(s, t, h))
```

The Ridge estimator uses `fit_intercept = false`. As alpha approaches infinity,
all learned corrections approach zero and the forecast approaches persistence
exactly. There is no log inverse transformation, smearing correction, cap, or
silent fallback.

## Frozen features

Numeric features, all known at the origin:

- `level_t = y_t`;
- `raw_change_1 = y_t - y_t-1`;
- `raw_change_2 = y_t-1 - y_t-2`;
- `raw_change_3 = y_t-2 - y_t-3`;
- `recent_zero_count` over `t` through `t-3`; and
- `origin_index`, quarters elapsed since `2003Q1`.

Categorical features are `state_code` and the calendar quarter of `t+h`.
Employment, hours, mine counts, actual-volume bands, mine-master attributes,
future targets, and candidate predictions remain excluded.

## Preprocessing and estimator

- Fit numeric means and standard deviations only on the outer-origin training
  rows.
- Fit deterministic one-hot state and target-quarter encoding only on those
  rows, with unknown categories encoded as all zeros and flagged.
- Keep equal row weights. Raw squared error intentionally gives large absolute
  tonnage misses more influence, while state MASE remains a required secondary
  diagnostic against excessive large-state dominance.
- Use deterministic dense-SVD Ridge with no intercept.
- Use one shared alpha selected from `{1, 100, 10000, 1000000}`.
- Any missing eligible feature, non-finite forecast, incomplete prediction
  coverage, temporal leakage, or nondeterminism is a hard failure.

## Selection and diagnostics

Use origins `2007Q4` through `2016Q3` only. An alpha without 100 percent
coverage is ineligible. Select the largest equal-weight mean horizon WAPE skill
against persistence at H1, H2, and H4 and seasonal naive at H3. Within an
absolute skill tie of `0.0001`, choose the larger alpha.

Before opening confirmation, review by horizon:

- WAPE skill and paired bootstrap interval;
- raw-scale signed bias and errors by origin, state, and volume band;
- residual bins against fitted value, raw level, and each raw change;
- within-state residual correlation at origin lags one and four;
- coefficient paths, numeric condition numbers, training exclusions, unseen
  states, and zero-floor frequency;
- state-balanced MASE alongside volume-weighted WAPE; and
- prequential interval coverage, width, Winkler score, and temporal drift.

Raw-delta linearity, shared cross-state dynamics, temporal transportability,
and stable scale are working assumptions, not causal claims. Residual
normality and homoscedasticity are not automatic point-forecast rejection
rules, but patterned bias, material residual dependence, or unusable interval
calibration blocks promotion.

## Uncertainty and stop rule

Keep v1's prequential horizon-specific conformal intervals: eight-origin
warm-up, state seasonal-MASE normalization where defined, 80 and 95 percent
levels, and prior-origin residuals only. Keep 2,000 paired non-circular moving-
block bootstrap replications, four-origin blocks, and seed `20260920`.

Confirmation origins `2016Q4` through `2021Q1` remain closed until the
selection diagnostic gate is explicitly accepted. Holdout origins remain
closed. If v2 does not materially improve on the frozen comparator or exposes
a material model-working failure, retain the baseline and stop; no v3 is
authorized.
