# Reproducibility Guide

## Reproduction boundaries

Project 02 has three distinct verification paths.

1. **Public code path:** install dependencies and run 54 synthetic tests. This
   verifies parsing contracts, transformations, temporal alignment, leakage
   guards, metrics, candidate behavior, interval construction, and one-time
   holdout access without requiring private data.
2. **Frozen snapshot rebuild:** manually obtain the two official MSHA archives
   and use files whose sizes and SHA-256 hashes match `configs/project.json`.
   This can rebuild the reviewed checkpoints and development analyses.
3. **Fresh source rebuild:** download the current MSHA archives and create a new
   dated configuration. MSHA may revise history, so current files must not be
   represented as the frozen 2026-09-20 snapshot or expected to reproduce its
   exact metrics.

The one-time final holdout is not a routine rerun target. Its reviewed manifest,
configuration, code revision, artifact hashes, and executed-notebook hash are
the evidence for the published result. Reopening or recalibrating from final
targets would violate the evaluation contract.

## Public test path

Use Python 3.13 from the repository root:

```text
python -m pip install -r requirements-lock.txt
python -m pip install scikit-learn==1.9.1
python -m pip install -e . --no-deps
python -m unittest discover -s tests -v
```

`requirements-lock.txt` records the accepted data-pipeline Colab dependency
closure. Scikit-learn 1.9.1 is installed explicitly because candidate and final
notebooks froze that version later. The project metadata allows Python 3.11
through 3.13 and constrains direct dependency families; transitive package
resolution can still differ across operating systems.

GitHub Actions runs this path on Linux with Python 3.13. It does not download
raw MSHA data, read private Drive files, or recalculate the final holdout.

## Frozen snapshot rebuild

Download `MinesProdQuarterly.zip` and `Mines.zip` from the
[MSHA Open Government Data portal](https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp),
then place the extracted text files here:

```text
data/raw/MinesProdQuarterly.txt
data/raw/Mines.txt
```

Before building, compare file sizes and SHA-256 values with
`configs/project.json`. A mismatch means the source is a different vintage and
must not overwrite or impersonate the accepted snapshot.

Run:

```text
python scripts/build_dataset.py
python scripts/evaluate_baselines.py
python scripts/evaluate_candidate_selection.py --candidate-config configs/candidate.json
python scripts/evaluate_candidate_selection.py --candidate-config configs/candidate_v2.json
```

The default local layout uses `data/` and `runs/`. Set `PROJECT_DATA_ROOT` and
`PROJECT_RUNS_ROOT` to use external storage. The Colab workflow uses these
variables to keep raw data, Parquet checkpoints, and versioned runs in private
Drive storage while code remains in Git.

## Expected reviewed lineage

| Evidence | Accepted value |
| --- | --- |
| Snapshot | `20260920_1b3a8424_38776a23` |
| Data run | `20260921T130122Z_770aedae_bbefbe` |
| Baseline run | `20260921T144811Z_62a3b84d_41560a` |
| Final run | `20260923T152725Z_8c9ab4d8_e93091` |
| Final code revision | `8c9ab4d8aefc45d45ce63b3b2cbb528b54038054` |
| Final executed notebook SHA-256 | `7b2c546464c98119c8c0ffb3609f01d465ec39116389513d3502442c0f1ba81d` |

## Verification status

| Check | Status |
| --- | --- |
| Local unit tests | 54 passed on Windows with Python 3.12 |
| Separate clean checkout | 54 passed using the accepted local dependency environment |
| Final Colab unit tests | 54 passed with Python 3.13 |
| Final notebook | Completed without error; passed run artifacts reused after validation |
| Final manifest lineage | Clean Git revision; accepted data and baseline runs |
| Candidate confirmation | Unopened |
| Public CI | 54 tests passed on Linux/Python 3.13 at commit `aff7200` ([run 35886875632](https://github.com/ahmaddshbg-blip/regional-coal-production-forecasting/actions/runs/35886875632)) |
| Exact frozen raw snapshot in Git | Excluded because of size; hashes and acquisition instructions published |
| Exact final run artifacts in Git | Excluded; private Drive artifacts are hash-recorded in the run manifest |

Passing public tests proves code behavior, not possession of the frozen source
files. Matching final metrics requires the exact frozen snapshot and accepted
lineage. See `docs/final_results.md` for the reviewed analytical result and
`docs/colab_workflow.md` for the author's hybrid execution sequence.
