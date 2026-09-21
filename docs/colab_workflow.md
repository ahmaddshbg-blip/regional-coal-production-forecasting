# Google Colab Workflow

Status: Gate 3 engineering design frozen; notebook implementation begins at Gate 4

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
4. `04_candidate_models.ipynb`; and
5. `05_error_uncertainty_decision_output.ipynb`.

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

Gate 4 will add the package metadata. Development runs will install the checked
out package from `pyproject.toml`; the final reproducibility run will use the
exact tested lock file. Notebook cells must not install unrecorded packages.

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
