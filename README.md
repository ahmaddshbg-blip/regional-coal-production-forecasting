# Regional Coal Production Forecasting

This project studies quarterly coal-production forecasting across U.S. mining
regions using public data from the Mine Safety and Health Administration
(MSHA). The intended analytical use is regional capacity planning and market
prioritization for a mining contractor, equipment supplier, or industrial
services provider.

## Project status

The project has completed problem definition, data feasibility, chronological
evaluation design, and engineering design. Gate 4 pipeline implementation is
next.

- The business problem and decision context are approved.
- Gate 1 data feasibility is complete for the frozen 2026-09-20 snapshot.
- Gate 2 is complete and the forecasting contract is frozen as version 1.0.
- Development validation, an evaluation embargo, and the final untouched
  holdout are fixed before model development.
- Gate 3 selected DuckDB, Parquet checkpoints, a minimal Python package,
  machine-readable configuration, run manifests, and a risk-based test plan.
- No candidate forecasting model has been selected or evaluated.
- No performance or business-impact claim is made yet.

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
[data provenance](docs/data_provenance.md).

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

Gate 4 will implement and validate configuration, raw snapshot checks, DuckDB
SQL transformations, versioned checkpoints, run metadata, tests, and the first
Colab notebook. It will not select a forecasting model.

## License and attribution

Project code and documentation are released under the [MIT License](LICENSE).
MSHA and U.S. Department of Labor data attribution and reuse boundaries are
documented separately in [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md).
