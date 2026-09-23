# Google Colab Workflow

Status: notebooks 01 through 05 reproduced successfully in Colab; final
holdout reviewed and model evaluation closed

## Roles of Colab and Python files

The main analytical workflow will be presented and executed through `.ipynb`
notebooks in Google Colab. Supporting `.py` files are required where logic must
be reusable, testable, or called consistently from more than one notebook.

Notebooks own:

- setup and configuration;
- analytical narrative;
- explicit calls to pipeline and evaluation functions;
- inspection tables and figures;
- interpretation and limitations; and
- links to generated artifacts.

Python modules and scripts own:

- schema and snapshot validation;
- SQL execution and checkpoint construction;
- temporal feature construction;
- rolling-origin split logic;
- baseline and candidate-model interfaces;
- metrics and uncertainty calculations;
- reusable visualization functions; and
- artifact metadata and run manifests.

## Planned notebook sequence

Notebook files are created only when their analytical stage begins. The frozen
sequence is:

1. `01_data_validation_and_panel.ipynb`;
2. `02_time_series_eda.ipynb`;
3. `03_baseline_backtesting.ipynb`;
4. `04_candidate_selection_and_diagnostics.ipynb`; and
5. `05_final_holdout_and_latest_forecast.ipynb`.

These are separate analytical stages, not five independent implementations of
the pipeline.

## Recommended Drive layout

Use a path without spaces or special characters:

```text
MyDrive/ds_portfolio/project_02_coal_production_forecasting/
|-- data/
|   `-- raw/
|       |-- MinesProdQuarterly.txt
|       `-- Mines.txt
`-- runs/
```

The corresponding Colab data path is:

```text
/content/drive/MyDrive/ds_portfolio/project_02_coal_production_forecasting/data
```

Drive stores private raw snapshots and selected expensive checkpoints. It is
not the source of truth for code once a Git remote exists.

## Notebook bootstrap contract

A notebook will perform the equivalent of:

```python
from google.colab import drive
drive.mount("/content/drive")

import os
os.environ["PROJECT_DATA_ROOT"] = (
    "/content/drive/MyDrive/ds_portfolio/"
    "project_02_coal_production_forecasting/data"
)
```

The repository code will then resolve input files beneath
`PROJECT_DATA_ROOT/raw/`. No reusable source file will contain the author's
personal Drive path.

The public GitHub repository is established. Colab should clone or pull that
repository and install its recorded dependencies. Drive is used for raw data
and selected checkpoints, not for full-folder code synchronization. Every run
must use one checked-out code revision rather than mixing local and Drive
copies.

Package metadata is defined in `pyproject.toml`. Development runs may install
the checked-out package from that file. The clean Gate 4 Colab run is recorded
in `requirements-lock.txt`, and notebook 01 now installs that lock before the
editable project package. Notebook cells must not install unrecorded packages.

The notebook also writes `requirements-lock-candidate.txt` beside each run
manifest.
It resolves only the installed runtime dependency closure of DuckDB,
Matplotlib, NumPy, and pandas; it deliberately excludes unrelated packages
preinstalled by Colab.

## Notebook 01 execution

Open `notebooks/01_data_validation_and_panel.ipynb` in Colab and run it from a
fresh runtime. Edit only `DRIVE_PROJECT_ROOT` if the recommended Drive layout
is not used. The notebook then:

1. clones or fast-forwards the public repository;
2. installs the checked-out package;
3. records the exact Git revision;
4. confirms both private raw files exist;
5. executes the synthetic unit tests;
6. calls the reusable validated pipeline; and
7. displays the panel summary and a non-modeling production time series.

Leave `OVERWRITE_EXISTING_CHECKPOINTS = False` on the first run. A later
rerun will reuse existing checkpoints only after the current raw files,
configuration hash, matching passed manifest, output sizes, and output hashes
are validated. Set the flag to `True` only for an intentional rebuild after
confirming that the snapshot and configuration have not changed.

## Notebook 02 execution

Open `notebooks/02_time_series_eda.ipynb` in a fresh Colab runtime after
notebook 01 has produced a passed run manifest and both checkpoints. The
notebook validates that lineage before loading data. Production magnitudes are
available to EDA only from `2003Q1` through `2022Q1`; later quarters retain
row-presence and non-null availability signals but are masked in the DuckDB
query before entering pandas.

Notebook 02 examines structural coverage, state scale and zeros, aggregate and
state trajectories, seasonality, concentration, calendar-aligned changes,
mine-level contributors to flagged changes, and dynamic eligibility. It does
not impute or remove observations, select transformations, implement a
baseline, choose a model, or calculate holdout performance.

## Notebook 03 execution

Open `notebooks/03_baseline_backtesting.ipynb` in a fresh Colab runtime after
the reviewed notebook 02 run. The notebook validates the passed data manifest,
loads target values only through `2022Q1`, executes the complete test suite,
and calls the reusable development-only evaluator.

Each execution writes a new versioned run directory containing baseline
forecasts plus overall, state, origin, and actual-volume-band metrics. Its
manifest records code, runtime, configuration, source-checkpoint lineage,
artifact hashes, frozen-audit status, and that holdout performance was not
opened. Re-running the notebook creates another auditable run rather than
silently overwriting prior evidence.

Notebook 03 must reproduce 100 percent prediction coverage and the scored-cell,
WAPE, and median-state MASE values frozen at Gate 2. It may compare the two
fixed baselines, but it does not authorize a candidate model or holdout run.

The accepted Colab execution used code revision
`62a3b84d8d7a7617ac8fc3798b053adb9ac97e7d` and baseline run
`20260921T144811Z_62a3b84d_41560a`. All tests passed, every frozen audit check
passed, all 11,144 forecast rows were written, prediction coverage was 100
percent, and the manifest records `holdout_opened = false`. These results close
the baseline-reproduction gate only. Notebook 04 must not be created until the
candidate procedure and its information-availability rules are frozen.

## Notebook 04 boundary

`DEC-014` and `DEC-016` reject both frozen candidate procedures on the
36-origin selection block. Confirmation and holdout were never opened.
Notebook 04 may now be created only as a readable reproduction of those failed
selection experiments and their diagnostic return path. It must not search
additional features, transformations, model families, intervals, or later
outcomes.

The notebook must run the complete tests, validate data and baseline lineage,
call the reusable selection-only evaluator, display alpha selection, point
metrics, residual diagnostics, interval calibration, paired bootstrap results,
and the frozen rejection criteria. Every generated manifest must retain
`diagnostic_gate_status = awaiting_review`, `confirmation_opened = false`, and
`holdout_opened = false`. The v1 and v2 review decisions live in the decision
log rather than being inferred automatically by notebook code.

The exact candidate dependency lock must be refreshed from a clean Colab
runtime after this notebook succeeds. The existing lock remains the accepted
data-pipeline environment and must not be relabelled as candidate evidence.

The accepted Colab execution used revision
`7a441b6d77b12d0dfca02908d95b4931d001d57a`. V1 run
`20260923T131252Z_7a441b6d_22fd1d` and v2 run
`20260923T131621Z_7a441b6d_528dfc` reproduced the local results with a clean
worktree and retained `confirmation_opened = false` and
`holdout_opened = false`. This closes candidate selection only. It does not
authorize final holdout access.

## Notebook 05 boundary

`DEC-018` freezes `horizon_specific_naive_baseline_v1`: persistence at H1, H2,
and H4, and annual seasonal naive at H3. Its 80 and 95 percent intervals use
only residuals from the 54 development origins. The point rules, calibration,
holdout origins, metrics, outputs, and interpretation boundaries cannot change
after the final holdout is opened.

Open `notebooks/05_final_holdout_and_latest_forecast.ipynb` in a fresh Colab
runtime. Run through the tests first. On the authorized first execution, review
the boundary text and deliberately change `OPEN_FINAL_HOLDOUT = False` to
`True`. The runner writes `runs/final_holdout_opened.json` before reading
holdout target magnitudes, evaluates the 12 origins once, writes hashed
artifacts and a passed manifest, then marks the opening record complete.

A normal rerun validates and reuses a matching passed run rather than scoring
the holdout again. If the opening marker exists without a passed manifest, do
not delete it or rerun automatically; record and review the failure first.
Notebook 05 reports H1-H4 point and interval performance and creates unscored
forecasts from `2026Q2` through `2027Q2`. H1-H2 rankings are review priorities,
not direct predictions of fleet, workforce, service demand, revenue, or causal
effects.

The accepted final run is `20260923T152725Z_8c9ab4d8_e93091` at revision
`8c9ab4d8aefc45d45ce63b3b2cbb528b54038054`. The reviewed executed notebook
ran all 54 tests without error and displayed `access_mode = reuse`, confirming
that the passed run and its hashed artifacts were validated rather than
rescored. Point WAPE is 9.04 percent at H1 and approximately 10.5 percent at
H2-H4. Both nominal interval levels over-cover beyond their upper guardrails;
this limitation is final and must not trigger recalibration. See
[`final_results.md`](final_results.md).

## Raw snapshot policy

The complete raw snapshot remains available even though the analytical pipeline
reduces it to coal records and state-quarter output. The notebook must not edit
raw files. Before a material run, it should verify expected filenames and
checksums or call a supporting validation function that does so.

## Output policy

Material Colab runs should write a versioned run directory containing, where
applicable:

- run manifest;
- data snapshot hashes;
- configuration;
- dependency and code versions;
- forecasts and metrics; and
- reusable figures.

Only reviewed lightweight outputs should return to Git. Rebuildable or large
checkpoints remain outside the repository with a documented regeneration path.
