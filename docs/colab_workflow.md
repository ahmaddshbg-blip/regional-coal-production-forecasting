# Google Colab Workflow

Status: Approved execution design; notebook implementation begins after Gate 2

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

The exact files will be created only after the forecasting contract and
evaluation design are frozen. The planned sequence is:

1. data validation and state-quarter panel construction;
2. time-series exploratory analysis;
3. baseline and rolling-origin evaluation;
4. candidate-model comparison; and
5. error, uncertainty, and decision-output analysis.

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

Once a private Git remote is established, Colab should clone or pull the
repository and install its recorded dependencies. Until then, full-folder Drive
synchronization may be used temporarily, but every run must use one deliberate
project copy rather than mixing code from local and Drive locations.

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
