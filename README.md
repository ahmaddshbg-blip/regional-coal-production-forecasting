# Regional Coal Production Forecasting

This project studies quarterly coal-production forecasting across U.S. mining
regions using public data from the Mine Safety and Health Administration
(MSHA). The intended analytical use is regional capacity planning and market
prioritization for a mining contractor, equipment supplier, or industrial
services provider.

## Project status

The project has completed problem definition, data feasibility, chronological
evaluation design, engineering design, and the validated data pipeline. Gate 4
passed locally and in a clean Google Colab runtime against the frozen snapshot.

- The business problem and decision context are approved.
- Gate 1 data feasibility is complete for the frozen 2026-09-20 snapshot.
- Gate 2 is complete and the forecasting contract is frozen as version 1.0.
- Development validation, an evaluation embargo, and the final untouched
  holdout are fixed before model development.
- Gate 3 selected DuckDB, Parquet checkpoints, a minimal Python package,
  machine-readable configuration, run manifests, and a risk-based test plan.
- Gate 4 reproduced all frozen source and transformation counts, built 183,301
  mine-quarter rows and 2,718 state-quarter rows, passed ten synthetic tests,
  and produced identical Parquet hashes on Windows and Colab.
- The exact Colab runtime dependency closure is frozen in
  `requirements-lock.txt`.
- Gate 5 holdout-safe time-series EDA passed in a clean Colab runtime. The
  reviewed evidence supports retaining the validated panel without imputation,
  outlier removal, winsorization, or a preselected target transformation.
- Gate 5 baseline backtesting passed in a clean Colab runtime at code revision
  `62a3b84d8d7a7617ac8fc3798b053adb9ac97e7d`. The versioned run reproduced
  every frozen Gate 2 scored-cell, WAPE, and median-state MASE audit value with
  100 percent prediction coverage and without opening the holdout.
- `DEC-012` and `DEC-013` froze the first candidate and its model-specific
  diagnostic return path before implementation. The log-change Ridge passed
  engineering checks but failed selection with mean WAPE skill of `-52.71%`.
- `DEC-015` authorized one diagnosis-driven raw-delta Ridge successor. It
  passed 100 percent prediction coverage and interval calibration, but mean
  WAPE skill was only `0.63%`, below the frozen `5%` materiality threshold;
  its paired bootstrap interval also crossed zero.
- `DEC-016` rejects v2, stops candidate-family iteration, and retains the
  frozen horizon-specific baseline. Candidate confirmation and the final
  holdout remain unopened.
- Notebook 04 reproduced both decisions in a clean Colab runtime at revision
  `7a441b6d77b12d0dfca02908d95b4931d001d57a`; both runs matched local results,
  used the accepted data and baseline lineage, and kept later blocks closed.
- No claim of incremental model performance or business impact is made.

## Problem statement

Quarterly coal production varies substantially across mining regions. A
planning team needs a defensible view of expected production one to four
quarters ahead so that it can prioritize contractor capacity review, market
attention, workforce planning, and heavy-equipment service readiness without
treating the latest observed quarter as a reliable forecast.

The proposed target is total operator-reported coal production, in tons, for
each U.S. state and calendar quarter. The main output will be a multi-horizon
forecast with uncertainty information and errors evaluated chronologically.

See [the project brief](docs/project_brief.md) and
[the forecasting contract](docs/forecasting_contract.md) for the current
scope. The planned local, Git, Drive, and SQL boundaries are described in
[the architecture](docs/architecture.md), with major choices recorded in
[the decision log](docs/decisions.md). The main analytical notebooks will run
in Google Colab using the documented [Colab workflow](docs/colab_workflow.md).

## Dataset

The approved source is the official
[MSHA Open Government Data portal](https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp).
The local snapshot contains quarterly operator-reported employment and coal
production from 2000Q1 through 2026Q2, joined by `MINE_ID` to the MSHA mine
master.

Raw data are kept outside version control. Source URLs, expected filenames,
snapshot hashes, and the initial audit are documented in
[the dataset decision record](docs/data_decision.md) and
[the raw-data manifest](data/raw/README.md). Missing-value treatment and
latest-quarter evidence are documented in
[the data-quality policy](docs/data_quality_policy.md). Source generation,
revision, and availability semantics are documented in
[data provenance](docs/data_provenance.md). Derived checkpoint fields and
missingness semantics are defined in the [data dictionary](docs/data_dictionary.md).

The 2.76 million raw rows include coal and metal/nonmetal records. The first
domain filter reduces the relevant coal input to 344,473 rows without removing
historical quarters. Forecasting will use a state-quarter table containing no
more than 27 states by 106 observed quarters. Notebooks will consume validated
checkpoints instead of repeatedly loading the complete raw files.

This reduction does not change the forecasting objective. The raw snapshot is
preserved in full, the transformation scans all relevant coal history, and the
mine-quarter checkpoint remains available for regional composition and data
quality diagnostics.

Gate 3 selected DuckDB for the versioned SQL transformation and Parquet for
rebuildable mine-quarter and state-quarter checkpoints. pandas is used only
after the relational reduction reaches an appropriate analytical scale.

## Reproduce Gate 4

Place the two manually downloaded files under `data/raw/`, install the project,
run the tests, and build the checkpoints:

```text
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/build_dataset.py
```

The frozen Colab environment can be reproduced with:

```text
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
```

The command validates filenames, byte sizes, headers, row structure, SHA-256
hashes, source counts, keys, numeric fields, mine-master coverage, and
missing-value totals before writing either checkpoint. Existing checkpoints
are not overwritten unless `--overwrite` is supplied deliberately. For the
primary notebook workflow, open
[`01_data_validation_and_panel.ipynb`](notebooks/01_data_validation_and_panel.ipynb)
in Colab and set its single private Drive root.

Development-only baseline evaluation can also be run from the command line:

```text
python scripts/evaluate_baselines.py
```

The command validates checkpoint lineage, evaluates only the frozen 54
development origins, verifies the pre-implementation audit table, and writes
versioned forecast and metric artifacts under the configured runs root.

The selection-only candidate evaluator can be reproduced with either frozen
configuration:

```text
python scripts/evaluate_candidate_selection.py --candidate-config configs/candidate.json
python scripts/evaluate_candidate_selection.py --candidate-config configs/candidate_v2.json
```

Both commands stop with `diagnostic_gate_status = awaiting_review` and write
versioned point, diagnostic, interval, and bootstrap artifacts. They do not
open confirmation or holdout data.

## Analytical boundaries

- This is a public-data demonstration of a realistic mining-planning problem.
- It does not represent an internal system or operating recommendation for a
  specific company.
- State is an aggregation level, not a claim that spatial modeling is the
  project's central contribution.
- Current mine status, owner, and operator fields are point-in-time attributes
  and will not be used as if they were historically available.
- Causal effects, mine scheduling, equipment dispatch, and financial impact
  estimation are outside the approved scope.

## Next gate

Data validation, holdout-safe EDA, baseline backtesting, candidate
implementation, and clean Colab selection reproduction are complete. Neither
locked candidate qualified for confirmation, and the horizon-specific baseline
is retained. The next gate must freeze that baseline's final point forecast,
development-only uncertainty calibration, one-time holdout report, and latest-
origin outputs before any final holdout value is read. See the [v1
procedure](docs/candidate_procedure.md), [v2
procedure](docs/candidate_procedure_v2.md), and [decision
log](docs/decisions.md) for the exact boundary.

## License and attribution

Project code and documentation are released under the [MIT License](LICENSE).
MSHA and U.S. Department of Labor data attribution and reuse boundaries are
documented separately in [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md).
