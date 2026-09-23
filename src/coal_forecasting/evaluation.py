"""Development-only rolling-origin evaluation for frozen baselines."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from coal_forecasting.baselines import generate_baseline_forecasts
from coal_forecasting.config import config_sha256, load_config
from coal_forecasting.eda import (
    add_quarters,
    origin_eligibility,
    period_label,
    period_start,
    prepare_state_panel,
    quarter_starts,
)
from coal_forecasting.metrics import (
    assert_complete_prediction_coverage,
    summarize_origin_metrics,
    summarize_overall_metrics,
    summarize_state_metrics,
    summarize_volume_metrics,
)
from coal_forecasting.paths import project_root, resolve_pipeline_paths
from coal_forecasting.pipeline import load_latest_validated_manifest
from coal_forecasting.validation import sha256_file


TARGET_COLUMN = "coal_production_short_tons"
FROZEN_BASELINE_AUDIT = {
    ("persistence", 1): (1391, 8.48, 0.709),
    ("persistence", 2): (1390, 11.04, 0.921),
    ("persistence", 3): (1389, 11.28, 1.086),
    ("persistence", 4): (1388, 11.39, 1.192),
    ("seasonal_naive", 1): (1391, 11.02, 1.238),
    ("seasonal_naive", 2): (1390, 11.13, 1.223),
    ("seasonal_naive", 3): (1389, 11.26, 1.198),
    ("seasonal_naive", 4): (1388, 11.39, 1.192),
}


class EvaluationGuardError(ValueError):
    """Raised when evaluation would cross a frozen development boundary."""


def development_origin_labels(evaluation: dict[str, Any]) -> list[str]:
    specification = evaluation["validation_origins"]
    origins = [
        period_label(date)
        for date in quarter_starts(specification["start"], specification["end"])
    ]
    if len(origins) != specification["count"]:
        raise EvaluationGuardError(
            f"Expected {specification['count']} development origins, found {len(origins)}"
        )
    latest_target = add_quarters(specification["end"], max(evaluation["forecast_horizons"]))
    if period_start(latest_target) >= period_start(evaluation["holdout_origins"]["start"]):
        raise EvaluationGuardError("Development targets overlap the holdout origin window")
    return origins


def seasonal_scale_at_origins(
    panel: pd.DataFrame,
    eligibility: pd.DataFrame,
    *,
    modeling_start: str,
) -> pd.DataFrame:
    start = period_start(modeling_start)
    latest_origin = eligibility["origin_date"].max()
    history = panel.loc[
        panel["quarter_start_date"].between(start, latest_origin),
        ["state_code", "quarter_start_date", TARGET_COLUMN],
    ].copy()
    lagged = history.copy()
    lagged["quarter_start_date"] += pd.DateOffset(months=12)
    lagged = lagged.rename(columns={TARGET_COLUMN: "lag4_target"})
    history = history.merge(
        lagged,
        on=["state_code", "quarter_start_date"],
        how="left",
        validate="one_to_one",
    )
    history["seasonal_absolute_difference"] = (
        history[TARGET_COLUMN] - history["lag4_target"]
    ).abs()
    valid = history["seasonal_absolute_difference"].notna()
    history["scale_sum"] = history["seasonal_absolute_difference"].fillna(0).groupby(
        history["state_code"]
    ).cumsum()
    history["scale_observations"] = valid.astype(int).groupby(
        history["state_code"]
    ).cumsum()
    history["mase_scale"] = history["scale_sum"].div(
        history["scale_observations"].replace(0, np.nan)
    )
    scales = history.rename(columns={"quarter_start_date": "origin_date"})[
        ["state_code", "origin_date", "mase_scale", "scale_observations"]
    ].rename(columns={"scale_observations": "mase_scale_observations"})
    return eligibility.merge(
        scales,
        on=["state_code", "origin_date"],
        how="left",
        validate="one_to_one",
    )


def build_forecast_cells_for_origins(
    panel: pd.DataFrame,
    evaluation: dict[str, Any],
    *,
    origins: list[str],
    target_end: str,
) -> pd.DataFrame:
    prepared = prepare_state_panel(panel)
    if prepared["quarter_start_date"].max() > period_start(target_end):
        raise EvaluationGuardError(
            f"Evaluator received target values after {target_end}"
        )

    eligibility = origin_eligibility(
        prepared,
        origins,
        modeling_start=evaluation["modeling_start"],
        minimum_history=evaluation["eligibility"]["minimum_non_null_history"],
        recent_quarters=evaluation["eligibility"][
            "required_consecutive_recent_observations"
        ],
    )
    eligibility = eligibility.loc[eligibility["eligible"]].copy()
    eligibility = seasonal_scale_at_origins(
        prepared,
        eligibility,
        modeling_start=evaluation["modeling_start"],
    )

    horizons = pd.DataFrame({"horizon": evaluation["forecast_horizons"]})
    cells = eligibility.merge(horizons, how="cross")
    cells["target_date"] = cells.apply(
        lambda row: row["origin_date"] + pd.DateOffset(months=3 * int(row["horizon"])),
        axis=1,
    )
    cells["target_period"] = cells["target_date"].map(period_label)
    if cells["target_date"].max() > period_start(target_end):
        raise EvaluationGuardError("A development forecast target crossed its cutoff")

    actuals = prepared[
        ["state_code", "quarter_start_date", TARGET_COLUMN]
    ].rename(
        columns={
            "quarter_start_date": "target_date",
            TARGET_COLUMN: "actual",
        }
    )
    cells = cells.merge(
        actuals,
        on=["state_code", "target_date"],
        how="left",
        validate="many_to_one",
    )
    return cells[
        [
            "state_code",
            "origin",
            "origin_date",
            "target_period",
            "target_date",
            "horizon",
            "eligible",
            "history_observations",
            "recent_observations",
            "actual",
            "mase_scale",
            "mase_scale_observations",
        ]
    ].sort_values(["origin_date", "state_code", "horizon"]).reset_index(drop=True)


def build_development_forecast_cells(
    panel: pd.DataFrame,
    evaluation: dict[str, Any],
) -> pd.DataFrame:
    origins = development_origin_labels(evaluation)
    target_end = add_quarters(
        evaluation["validation_origins"]["end"],
        max(evaluation["forecast_horizons"]),
    )
    return build_forecast_cells_for_origins(
        panel,
        evaluation,
        origins=origins,
        target_end=target_end,
    )


def verify_frozen_baseline_audit(metrics: pd.DataFrame) -> None:
    indexed = metrics.set_index(["model", "horizon"])
    failures = []
    for key, (expected_cells, expected_wape_percent, expected_median_mase) in (
        FROZEN_BASELINE_AUDIT.items()
    ):
        if key not in indexed.index:
            failures.append(f"missing metric row {key}")
            continue
        row = indexed.loc[key]
        observed = (
            int(row["scored_cells"]),
            round(float(row["wape"]) * 100, 2),
            round(float(row["median_state_mase"]), 3),
        )
        expected = (expected_cells, expected_wape_percent, expected_median_mase)
        if observed != expected:
            failures.append(f"{key}: expected {expected}, observed {observed}")
    if failures:
        raise ValueError("Frozen baseline audit mismatch: " + "; ".join(failures))


def evaluate_development_baselines(
    panel: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    cells = build_development_forecast_cells(panel, config["evaluation"])
    forecasts = generate_baseline_forecasts(cells, panel)

    horizon_four = forecasts.loc[forecasts["horizon"].eq(4)].pivot(
        index=["state_code", "origin_date"], columns="model", values="forecast"
    )
    if not horizon_four["persistence"].equals(horizon_four["seasonal_naive"]):
        raise ValueError("Frozen baselines disagree at horizon 4")

    state_metrics = summarize_state_metrics(forecasts)
    metrics = summarize_overall_metrics(forecasts, state_metrics)
    assert_complete_prediction_coverage(metrics)
    verify_frozen_baseline_audit(metrics)
    return {
        "forecasts": forecasts,
        "metrics": metrics,
        "state_metrics": state_metrics,
        "origin_metrics": summarize_origin_metrics(forecasts),
        "volume_metrics": summarize_volume_metrics(forecasts),
    }


def _git_state(root: Path) -> dict[str, Any]:
    def run_git(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None
        return completed.stdout.strip()

    commit = run_git("rev-parse", "HEAD")
    status = run_git("status", "--porcelain")
    return {"commit": commit, "dirty": bool(status) if status is not None else None}


def _package_version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _write_parquet(frame: pd.DataFrame, path: Path, order_by: str) -> None:
    with duckdb.connect() as connection:
        connection.register("artifact", frame)
        escaped = path.as_posix().replace("'", "''")
        connection.execute(
            f"COPY (SELECT * FROM artifact ORDER BY {order_by}) "
            f"TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )


def run_development_baseline_evaluation(
    config_path: str | Path = "configs/project.json",
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate lineage, evaluate baselines, and write a versioned run."""
    started_at = datetime.now(timezone.utc)
    repository_root = Path(root).expanduser().resolve() if root else project_root()
    candidate_config = Path(config_path).expanduser()
    if not candidate_config.is_absolute():
        candidate_config = repository_root / candidate_config
    config = load_config(candidate_config)
    paths = resolve_pipeline_paths(config, repository_root)
    data_manifest = load_latest_validated_manifest(candidate_config, root=repository_root)

    target_end = add_quarters(
        config["evaluation"]["validation_origins"]["end"],
        max(config["evaluation"]["forecast_horizons"]),
    )
    with duckdb.connect() as connection:
        panel = connection.execute(
            """
            SELECT *
            FROM read_parquet(?)
            WHERE quarter_start_date <= CAST(? AS DATE)
            ORDER BY state_code, quarter_start_date
            """,
            [str(paths["state_quarter"]), period_start(target_end).date()],
        ).fetchdf()

    result = evaluate_development_baselines(panel, config)
    finished_at = datetime.now(timezone.utc)
    git = _git_state(repository_root)
    commit_label = git["commit"][:8] if git["commit"] else "nogit"
    run_id = (
        finished_at.strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + commit_label
        + "_"
        + uuid.uuid4().hex[:6]
    )
    run_directory = paths["runs_root"] / run_id
    run_directory.mkdir(parents=True, exist_ok=False)

    artifact_specs = {
        "forecasts": ("baseline_forecasts.parquet", "model, origin_date, state_code, horizon"),
        "metrics": ("baseline_metrics.parquet", "model, horizon"),
        "state_metrics": (
            "baseline_state_metrics.parquet",
            "model, horizon, state_code",
        ),
        "origin_metrics": (
            "baseline_origin_metrics.parquet",
            "model, horizon, origin_date",
        ),
        "volume_metrics": (
            "baseline_volume_metrics.parquet",
            "model, horizon, actual_volume_band",
        ),
    }
    outputs: dict[str, dict[str, Any]] = {}
    for name, (filename, order_by) in artifact_specs.items():
        path = run_directory / filename
        _write_parquet(result[name], path, order_by)
        outputs[name] = {
            "path": path.relative_to(paths["runs_root"]).as_posix(),
            "rows": len(result[name]),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    manifest_path = run_directory / "manifest.json"
    manifest = {
        "run_id": run_id,
        "stage": "development_baselines",
        "entry_point": "coal_forecasting.evaluation.run_development_baseline_evaluation",
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "project": config["project"],
        "schema_version": config["schema_version"],
        "checkpoint_id": config["snapshot"]["checkpoint_id"],
        "config_sha256": config_sha256(config),
        "git": git,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "duckdb": duckdb.__version__,
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
        },
        "parameters": {
            "modeling_start": config["evaluation"]["modeling_start"],
            "development_origins": config["evaluation"]["validation_origins"],
            "forecast_horizons": config["evaluation"]["forecast_horizons"],
            "target_end": target_end,
            "models": ["persistence", "seasonal_naive"],
        },
        "source_data_run": data_manifest["run_id"],
        "source_state_checkpoint": data_manifest["outputs"]["state_quarter"],
        "checks": {
            "frozen_baseline_audit": "passed",
            "prediction_coverage": "passed",
            "horizon_four_equality": "passed",
            "holdout_opened": False,
        },
        "outputs": outputs,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        **result,
        "manifest": {**manifest, "manifest_path": str(manifest_path)},
    }
