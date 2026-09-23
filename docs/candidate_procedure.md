# Candidate Procedure

Status: Rejected at the selection diagnostic gate on 2026-09-23

Decision record: `DEC-012`

Diagnostic governance: `DEC-013`

Procedure identifier: `pooled_direct_ridge_log_change_v1`

Selection run: `20260923T062835Z_3831181d_38d675`

This file remains the immutable specification of v1. The result-driven review
is recorded in `DEC-014`; no confirmation origin was opened.

## Purpose

This document freezes the first and only candidate procedure authorized for
the current development experiment. It fixes the hypothesis, information set,
feature schema, fitting rule, hyperparameter selection, uncertainty procedure,
and failure behavior before candidate code or notebook 04 exists.

Freezing the procedure does not claim that it will outperform the baselines.
It prevents feature or model changes from being made in response to candidate
or holdout results.

## Selection outcome

The implementation validity checks passed, but the model-working diagnostic
gate failed. Alpha `100` was the best frozen setting, yet equal-weight mean
WAPE skill against the horizon-specific comparators was `-0.5271`. Its paired
four-quarter moving-block bootstrap 95 percent interval was `[-1.0076,
-0.0209]`. Horizon skill deteriorated from `-0.1377` at H1 to `-0.9440` at H4.

Raw-scale signed bias was negative at every horizon and worsened from `-3.10`
percent at H1 to `-15.44` percent at H4. The largest fitted-value decile
accounted for severe underforecasting, and within-state lag-one residual
correlation increased materially at longer horizons. Prediction coverage was
100 percent, zero flooring was below 0.6 percent, no state was unseen, and
numeric condition numbers remained below 2.9. The failure is therefore a
model-scale and dynamic-specification problem, not an engineering-validity or
conditioning failure.

The confirmation block and holdout remain unopened. V1 cannot be promoted or
patched. Any successor requires a new procedure identifier and dated decision.

## Candidate hypothesis

Persistence overforecasts increasingly at longer horizons during a generally
declining and disrupted production period. A small global panel model may
improve on it by learning recent direction and common dynamics across states,
while regularized state indicators retain persistent regional differences.

The candidate is a direct, target-only, pooled Ridge regression. One separate
model is fitted for each horizon. Each model predicts the future change from
the persistence forecast on a `log1p` scale. This is an incremental test of a
specific hypothesis, not a general model search.

## Alternatives considered

| Family | Decision | Reason |
| --- | --- | --- |
| Local damped-trend or ETS models | Not selected | They address trend but do not borrow strength across states, can be unstable for short or interrupted regional histories, and add local fit and interval failure modes. The EDA also does not support a strong common seasonal component. |
| Per-state ARIMA or SARIMA | Not selected | State-specific order selection would create many low-sample model choices and a large maintenance surface without stronger evidence. |
| Global tree boosting | Deferred | It could capture nonlinear interactions, but its feature and tuning flexibility is not yet earned by the baseline evidence. |
| Exogenous employment, hours, mine status, or ownership | Excluded | Employment and hours are approved only as diagnostics, and current mine-master attributes are not point-in-time historical fields. |
| Pooled direct Ridge correction | Selected | It is deterministic, interpretable, computationally small, compatible with dynamic entity eligibility, and directly tests whether recent trend plus regularized cross-state pooling corrects the observed baseline bias. |

Failure of this candidate is a valid result. It does not automatically
authorize a second model family.

## Forecast strategy

- Forecast unit: eligible state, origin, and horizon.
- Horizons: one, two, three, and four quarters.
- Strategy: four separate direct models, one per horizon.
- Refit rule: refit every horizon model at every forecast origin.
- Estimation window: expanding from `2003Q1` through the applicable origin, as
  required by the forecasting contract.
- Cross-state rule: pool all valid historical state examples in one model for
  each horizon.
- Forecast eligibility and scoring cells remain exactly those produced by the
  frozen evaluation contract.

Recursive forecasts are prohibited. A prediction for horizon two through four
must not consume an earlier candidate prediction as an input.

## Origin-safe supervised rows

For an outer forecast origin `t` and horizon `h`, a historical pseudo-origin
`u` may enter training only when:

1. `u` is no earlier than `2003Q4`;
2. target values at `u`, `u-1`, `u-2`, and `u-3` are all observed;
3. the direct label at `u+h` is observed; and
4. `u+h <= t`, so the label would have been available at outer origin `t`.

The 20-observation rule determines which states receive forecasts; it is not
an additional filter on historical pooled training rows. Reported zeros remain
valid values. Rows with an absent target are excluded rather than imputed.

Every training record must retain its pseudo-origin, label date, state, and
horizon so tests can verify temporal alignment.

## Response and point forecast

For state `s`, pseudo-origin `u`, and horizon `h`, define:

```text
z(s, q) = log1p(production(s, q))
response(s, u, h) = z(s, u + h) - z(s, u)
```

The model predicts a change relative to the persistence forecast. For a real
forecast origin `t`:

```text
predicted_log_level = max(0, z(s, t) + predicted_change)
forecast = expm1(predicted_log_level)
```

The zero floor enforces the physical non-negativity of production. Forecasts
are not rounded, winsorized, or capped at a historical maximum. A non-finite
prediction is a hard evaluation failure, not a reason to substitute a
baseline silently.

## Frozen feature set

All features are computed independently for each state and use information no
later than the pseudo-origin or forecast origin.

| Feature | Definition | Availability |
| --- | --- | --- |
| `log_level_t` | `log1p(y_t)` | Observed at the origin |
| `log_change_1` | `log1p(y_t) - log1p(y_t-1)` | Last four observations are guaranteed by eligibility |
| `log_change_2` | `log1p(y_t-1) - log1p(y_t-2)` | Last four observations are guaranteed by eligibility |
| `log_change_3` | `log1p(y_t-2) - log1p(y_t-3)` | Last four observations are guaranteed by eligibility |
| `recent_zero_count` | Number of reported zeros among `t` through `t-3` | Known at the origin |
| `origin_index` | Quarters elapsed since `2003Q1` | Calendar-known |
| `target_quarter` | Calendar quarter of `t+h` | Known in advance |
| `state_code` | Forecasting entity identifier | Known at the origin |

The three changes and current level reconstruct the four guaranteed lagged
levels. No longer lag is required, so every eligible forecast cell has the
complete numeric information set.

Explicitly excluded are future or contemporaneous unknown production,
employment and hours, mine counts, actual-volume bands, final-holdout values,
current mine-master attributes treated as history, future-informed entity
selection, and any imputed target.

## Preprocessing and model specification

- Numeric features are standardized using means and standard deviations fitted
  only on the outer-origin training rows.
- `state_code` and `target_quarter` use deterministic one-hot encoding fitted
  only on those rows.
- An unseen state category at prediction time is encoded with zero state
  indicators and recorded with `state_seen_in_training = false`; numeric
  origin features still produce a forecast.
- All rows have equal fitting weight. No future or actual-volume-derived weight
  is permitted.
- The estimator is Ridge regression with an intercept and L2 penalty.
- The implementation must use a deterministic dense SVD solution. Ridge has no
  random initialization; project seed `20260920` remains the seed for
  resampling procedures.
- Scaling, encoding, fitting, and prediction must occur inside each outer
  origin and horizon boundary. Cached matrices must include the outer cutoff
  and procedure hash in their identity.

No alternate transformation, feature subset, interaction search, training
window, loss, or solver may be selected after candidate results are seen.

## Assumptions and diagnostic gate

This candidate is a forecasting procedure, not a classical coefficient-
inference exercise. Its validity therefore does not depend on importing every
ordinary least-squares or ARIMA diagnostic as a universal rejection rule.
Assumptions are classified by the consequence of a violation.

### Hard validity requirements

The run must stop and the implementation must be corrected when any of the
following occurs:

- a feature or training label crosses its outer forecast origin;
- scaling or encoding uses rows outside the outer training boundary;
- a development entry point receives a target after `2022Q1`;
- an eligible forecast row lacks a required four-quarter feature;
- prediction coverage is below 100 percent or a point forecast is non-finite;
- reported zero is changed to missing or an absent target is imputed;
- repeated runs with the same inputs and configuration are not deterministic;
  or
- candidate generation uses a prior candidate prediction recursively.

These are data and evaluation validity failures. They cannot be accepted as
mere model limitations.

### Model-working assumptions

The Ridge candidate makes the following approximations:

1. Future `log1p` change is approximately additive and linear in the frozen
   numeric and categorical feature representation.
2. Dynamic coefficients can be shared across states after including
   regularized state indicators and each state's own recent values.
3. Relationships estimated from the expanding history remain sufficiently
   transportable to later origins.
4. `log1p` is an adequate scale for fitting even though selection and final
   evaluation occur in raw tons.
5. L2 shrinkage trades coefficient bias for lower forecast variance; individual
   coefficients are not unbiased structural effects.

Stationarity of the target level is not a prerequisite for this direct model,
and no unit-root test is used as an automatic model gate. Predictor
multicollinearity is expected and controlled by Ridge; it limits isolated
coefficient interpretation but does not make the forecast undefined.
Residual normality, constant variance, and serial independence are not required
for coefficient p-values because no coefficient hypothesis tests or causal
claims will be reported. Their violations still matter for forecast error
patterns and uncertainty calibration and must be diagnosed.

### Selection-block diagnostics

Diagnostics are computed using candidate predictions from the 36-origin
selection block only, after the alpha rule is applied and before candidate
results from the 18-origin confirmation block are opened.

Required outputs by horizon are:

- signed bias and absolute error by origin, state, and actual-volume band;
- residual and absolute-residual summaries by fitted-value decile;
- mean residual by decile of `log_level_t`, each recent log change,
  `recent_zero_count`, and `origin_index`;
- within-state residual autocorrelation at origin lags one and four when at
  least 12 paired residuals exist, with the number of eligible states shown;
- residual scale before and after division by the origin-time seasonal MASE
  scale;
- standardized coefficient paths across origins and horizons;
- numeric-feature correlation and condition diagnostics, interpreted in the
  presence of L2 regularization;
- zero-floor frequency and raw-scale bias after inverse transformation; and
- state-seen-in-training and training-row exclusion counts.

Quarterly rolling-origin errors overlap for horizons above one, so residual
autocorrelation is evidence about remaining temporal structure and interval
dependence, not an automatic proof that point forecasts are invalid.
Heteroskedasticity is handled similarly: it motivates scale diagnostics and
may invalidate pooled intervals even when point forecasts remain useful.

### Uncertainty assumptions

The conformal procedure assumes that horizon-specific residual scores are
sufficiently stable over time after state-scale normalization. Serial
dependence and regime change mean exact finite-sample exchangeability is not
claimed. Empirical prequential coverage, width, Winkler score, normalized-score
drift, and coverage by state and origin are therefore mandatory.

Failure of the frozen 80 or 95 percent coverage guardrail is an interval-
procedure failure. It does not retroactively invalidate point forecasts, but
the candidate cannot enter the holdout as the retained complete procedure with
uncalibrated intervals.

### Iteration boundary

The process is iterative without allowing result-driven model chasing:

1. implementation validity tests run first;
2. alpha is selected on the selection block;
3. the diagnostics above are reviewed before confirmation metrics are opened;
4. a hard failure is fixed without changing the statistical procedure;
5. a material specification problem may lead to either an explicitly accepted
   limitation or a new procedure identifier and dated decision; and
6. only an accepted, newly frozen specification may open confirmation results.

Once candidate confirmation metrics have been inspected, the confirmation
block is no longer available for tuning. A confirmation failure is reported as
a failure of the current experiment. Holdout results can never be used to
revise the model, features, thresholds, or interval procedure.

This gate implements model-specific diagnosis without pretending that every
warning has the same consequence. The diagnostic review and its decision must
be written to the run manifest and decision log.

## Hyperparameter selection

The only tuned parameter is the Ridge penalty. Its frozen grid is:

```text
alpha in {0.1, 1.0, 10.0, 100.0}
```

One alpha is shared by all four horizon models.

The 54 development origins are partitioned before implementation:

- selection block: `2007Q4` through `2016Q3`, 36 origins;
- confirmation block: `2016Q4` through `2021Q1`, 18 origins.

For every alpha, origin-safe forecasts are generated on the selection block.
Any alpha without 100 percent prediction coverage is ineligible. Among the
remaining values, select the alpha with the largest equal-weight mean of the
four horizon-level WAPE skills against the frozen horizon-specific
comparators. If scores differ by no more than `0.0001` absolute skill, choose
the larger alpha to prefer stronger regularization.

After selection, the alpha is fixed. The confirmation block is evaluated
only after the selection-block diagnostic gate is accepted, and without
retuning, feature changes, or model-family substitution. Formal
candidate promotion metrics are also reported over all 54 development origins
as required by the forecasting contract. The confirmation split is a
stability diagnostic and does not replace or weaken the frozen promotion
criteria.

## Prediction coverage and failure behavior

- The candidate must produce a finite point forecast for every
  baseline-comparable eligible state-origin-horizon cell.
- Missing forecast features at an eligible cell are a hard failure because the
  frozen feature set requires only the four observations already guaranteed by
  eligibility.
- There is no silent persistence, seasonal-naive, zero, or mean fallback.
- Actual targets may remain unavailable. Those forecasts stay in the artifact
  and are unscored with the existing reason flag.
- Training-row exclusions and unseen state categories are counted and written
  to the run manifest.

## Uncertainty procedure

Use pooled-by-horizon, state-scale-normalized conformal residual intervals.
For a scored development forecast, define:

```text
score = abs(candidate forecast - actual) / seasonal MASE scale at the origin
```

Development interval evaluation is prequential:

1. The first eight development origins are an interval-calibration warm-up.
2. Starting at `2009Q4`, each origin uses only candidate residuals from earlier
   development origins at the same horizon.
3. Compute separate finite-sample conformal quantiles for nominal 80 and 95
   percent intervals using rank `ceil((n + 1) * coverage)`, capped at `n`.
4. Multiply the quantile by the current state's origin-time seasonal MASE
   scale and place a symmetric interval around the point forecast.
5. Floor the lower bound at zero; do not cap the upper bound.

If a current state scale is non-positive or undefined, use the corresponding
unscaled absolute-residual quantile for that horizon and mark
`interval_scale_source = pooled_unscaled`. No future target is imputed.

After development evaluation, freeze horizon and nominal-level quantiles using
all scored development residuals from the selected alpha. Those fixed
quantiles are used for every final-holdout origin. Holdout residuals must not
update or recalibrate the intervals.

Report empirical coverage, mean and median width, width relative to actual
volume where defined, Winkler score, interval-evaluable cell counts, and the
frozen coverage guardrails. Early warm-up cells are excluded from interval
coverage summaries but remain in point-forecast evaluation.

## Skill uncertainty

Apply the forecasting contract's paired moving-block bootstrap to candidate
and comparator forecasts:

- block length: four consecutive forecast origins;
- replications: 2,000;
- seed: `20260920`;
- sample contiguous non-circular blocks with replacement until the required
  origin count is reached, then truncate; and
- use the same sampled origins for the candidate and comparator.

Report percentile 95 percent confidence intervals for each horizon's WAPE
skill and for the equal-weight mean horizon skill. A point estimate that passes
while its mean-skill interval includes zero remains labelled promising but not
robustly superior.

## Evaluation and stop rule

The candidate is evaluated against both frozen baselines, with the fixed
horizon-specific comparator used for promotion. All WAPE, state MASE, bias,
origin, state, actual-volume-band, regime, coverage, and common-state
diagnostics remain required.

The untouched holdout stays closed until the selected alpha, preprocessing,
feature schema, refit policy, and conformal quantiles are written to a locked
development manifest and every frozen promotion criterion passes. Passing
development does not open the holdout automatically; it triggers a separate
gate review.

If the candidate fails, publish the failure analysis and retain the appropriate
baseline. Do not change this procedure or search another model in the same
experiment merely to obtain a win.

## Required implementation tests

Before notebook 04 may run, tests must verify:

- all lag and change features point backward from the origin;
- each training label date is no later than the outer origin;
- direct horizons do not consume candidate predictions;
- scaling and encoding are fitted within each outer training boundary;
- reported zeros survive feature construction;
- incomplete training rows are excluded without target imputation;
- every eligible prediction row has all required numeric features;
- unknown state encoding remains finite and is flagged;
- inverse transformation and flooring never produce a negative forecast;
- alpha selection, tie breaking, and development-block dates are exact;
- repeated runs are deterministic;
- conformal calibration uses prior development residuals only;
- paired bootstrap resamples origins rather than individual state cells; and
- all development entry points reject holdout target values and origins.

Diagnostic tests must additionally verify fitted-value binning, within-state
lag pairing, minimum-pair guards, zero-floor counts, coefficient-path schema,
and that no confirmation prediction enters the selection diagnostic frame.

## Reproducibility record

The implementation must add the justified model dependency to
`pyproject.toml`, update the exact Colab lock after a clean run, and record at
least the following in its manifest:

- procedure identifier and specification hash;
- source checkpoint and baseline run lineage;
- Git revision and dirty-worktree state;
- feature names and preprocessing policy;
- alpha grid, selection block, selected alpha, and tie rule;
- candidate and interval calibration origin ranges;
- dependency versions and random seed;
- point, interval, and bootstrap artifact hashes;
- selection diagnostic artifact hashes and diagnostic-gate status;
- prediction and interval coverage checks; and
- `holdout_opened = false`.
