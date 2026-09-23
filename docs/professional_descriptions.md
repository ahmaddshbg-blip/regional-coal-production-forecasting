# Professional Project Descriptions

These descriptions compress the same evidence for different platforms. They
must be updated from the repository source of truth rather than edited into
inconsistent independent claims.

## GitHub short description

Leakage-safe quarterly coal-production forecasting with MSHA data, DuckDB/SQL,
rolling-origin backtesting, baseline and Ridge governance, uncertainty audits,
and reproducible Colab/Python workflows.

## Portfolio card

**Regional Coal Production Forecasting**

Built a reproducible state-quarter forecasting workflow from 2.76 million
public MSHA records. DuckDB and versioned SQL reduce the data to a validated
panel; rolling-origin evaluation, dynamic eligibility, embargoed holdout, and
54 tests protect temporal validity. Two Ridge candidates failed predeclared
promotion criteria, so the simpler horizon-specific baseline was retained. It
achieved 9.04 percent H1 WAPE and approximately 10.5 percent H2-H4 WAPE with
100 percent prediction coverage. Prediction intervals over-covered and are
reported honestly as conservative rather than retuned after holdout.

## LinkedIn post

I completed a forecasting portfolio project using public U.S. Mine Safety and
Health Administration coal-production data.

The work began with 2.76 million source rows and used DuckDB plus versioned SQL
to build a validated state-quarter panel. I froze the forecast target,
information set, dynamic state-eligibility rules, 54 rolling development
origins, an embargo, and a 12-origin final holdout before candidate modeling.

The most important result was methodological rather than algorithmic. Two
regularized-regression candidates did not establish enough reliable improvement
over strong naive forecasts, so I retained a transparent horizon-specific
baseline. Final WAPE was 9.04 percent at one quarter ahead and about 10.5
percent at two to four quarters, with complete prediction coverage.

The uncertainty audit also produced a useful negative result: nominal 80 and
95 percent intervals over-covered at 94.16 and 98.97 percent and were too wide.
I documented that limitation instead of recalibrating after seeing the final
holdout.

The repository includes tested temporal logic, immutable snapshot and run
lineage, clean Colab notebooks, SQL transformations, decision records, and
explicit boundaries between production forecasts and operational decisions.

Repository: https://github.com/ahmaddshbg-blip/regional-coal-production-forecasting

## CV version

**Regional Coal Production Forecasting | Python, DuckDB, SQL, pandas,
scikit-learn, Google Colab**

- Engineered a reproducible pipeline from 2.76M public MSHA records to 183K
  mine-quarter and 2,718 state-quarter observations using validated DuckDB/SQL
  transformations, Parquet checkpoints, configuration hashes, and run
  manifests.
- Designed leakage-safe H1-H4 rolling-origin evaluation with dynamic state
  eligibility, 54 development origins, an embargo, a one-time 12-origin
  holdout, and 54 deterministic tests; achieved 100% prediction coverage and
  9.04% H1 WAPE with a transparent baseline after two Ridge candidates failed
  predeclared promotion criteria.
- Audited forecast uncertainty and documented interval overcoverage instead of
  post-holdout retuning; translated latest state forecasts into bounded regional
  review priorities without claiming direct equipment, workforce, or financial
  impact.

## Interview narrative

### 30-second version

I built an end-to-end quarterly coal-production forecasting project from public
MSHA data. The main technical challenge was preventing leakage across a panel
of changing state series, not choosing the most complex model. I used DuckDB
and SQL for validation and aggregation, rolling-origin backtesting with dynamic
eligibility, and a final one-time holdout. Two Ridge candidates failed the
predeclared improvement rules, so I retained a simple horizon-specific naive
method. It reached 9.04 percent H1 WAPE with complete prediction coverage, while
its intervals were too conservative, which I reported without retuning.

### Two-minute version

The business question was whether public production history could support
regional capacity review one to four quarters ahead for a mining contractor or
equipment-service context. The target was quarterly coal production by U.S.
state, not equipment demand itself.

I first froze the data and forecast contracts. The 2.76 million-row MSHA export
contains coal and metal/nonmetal records, so DuckDB and versioned SQL validate
the raw snapshot and reduce only the relevant coal history to a small panel.
State eligibility is recalculated at every origin, which avoids survivorship
leakage. Evaluation uses 54 rolling development origins, a four-origin embargo,
and 12 final origins with H1-H4 forecasts.

Persistence and annual seasonal naive were strong. I tested two direct pooled
Ridge designs under the same origins and cells. The first was materially worse;
the second improved mean WAPE by only 0.63 percent, below the frozen 5 percent
threshold, with bootstrap uncertainty crossing zero. I stopped model search
and retained the simple baseline before opening the holdout.

On final holdout, WAPE was 9.04 percent at H1 and around 10.5 percent at H2-H4
with 100 percent prediction coverage. The point forecast was useful, but the
development-calibrated intervals over-covered and were too wide. That split
result is important: the project demonstrates disciplined model selection and
honest uncertainty evaluation, not a claim that every component succeeded.

## Questions to defend

**Why use U.S. data for an Indonesia-focused career portfolio?**

The source offers traceable public production history and realistic revision,
missingness, panel, and forecasting constraints. The demonstrated capabilities
are transferable; the project does not claim that U.S. state forecasts directly
describe an Indonesian company's operations.

**Why stop at a naive model?**

The advanced candidates did not earn their complexity under predeclared
criteria. Keeping the baseline is evidence of model governance, not failure to
use machine learning.

**Why is the final method called predictive analytics if it is simple?**

Predictive work includes contract design, time-valid evaluation, baselines,
candidate testing, error analysis, uncertainty, and decision output. Algorithm
complexity is only one part and was explicitly tested.

**What failed?**

Both Ridge candidates failed promotion, and final intervals were too wide and
over-covered. The point procedure remained stable. No failed component was
hidden or repaired with final-holdout information.

**What would be needed before operational use?**

Historical data vintages, publication-lag monitoring, current mine plans,
contracts, fleet and maintenance data, commodity context, cost-sensitive loss
functions, ownership of forecast review, and prospective monitoring after each
new quarter.
