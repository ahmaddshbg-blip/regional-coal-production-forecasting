"""Selection-only evaluation for the frozen pooled Ridge candidate."""

from __future__ import annotations

import hashlib
import json
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
from coal_forecasting.candidate import (
    ALPHA_GRID,
    PROCEDURE_ID,
    V2_ALPHA_GRID,
    V2_PROCEDURE_ID,
    fit_predict_ridge,
    fit_predict_v2_ridge,
    select_shared_alpha,
)
from coal_forecasting.candidate_diagnostics import (
    binned_residual_summary,
    residual_autocorrelation,
    validate_selection_frame,
)
from coal_forecasting.candidate_features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    V2_NUMERIC_FEATURES,
    build_prediction_features,
    build_training_examples,
    build_v2_prediction_features,
    build_v2_training_examples,
)
from coal_forecasting.candidate_uncertainty import (
    add_prequential_intervals,
    paired_moving_block_bootstrap_skill,
    summarize_interval_metrics,
)
from coal_forecasting.config import config_sha256, load_config
from coal_forecasting.eda import add_quarters, period_label, period_start, quarter_starts
from coal_forecasting.evaluation import build_forecast_cells_for_origins
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


class SelectionGuardError(ValueError):
    """Raised when candidate selection would cross its frozen boundary."""


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


def load_candidate_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "procedure_id",
        "alpha_grid",
        "tie_tolerance",
        "selection_origins",
        "confirmation_origins",
        "features",
        "intervals",
        "bootstrap",
    }
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Candidate config is missing: {', '.join(sorted(missing))}")
    if config["procedure_id"] == PROCEDURE_ID:
        numeric_features = NUMERIC_FEATURES
        alpha_grid = ALPHA_GRID
    elif config["procedure_id"] == V2_PROCEDURE_ID:
        numeric_features = V2_NUMERIC_FEATURES
        alpha_grid = V2_ALPHA_GRID
    else:
        raise ValueError("Candidate config procedure identifier is not frozen")
    expected_features = {
        "numeric": list(numeric_features),
        "categorical": list(CATEGORICAL_FEATURES),
    }
    if config["features"] != expected_features:
        raise ValueError("Candidate feature contract does not match frozen v1")
    if tuple(float(value) for value in config["alpha_grid"]) != alpha_grid:
        raise ValueError("Candidate alpha grid does not match its frozen procedure")
    config["_config_path"] = str(config_path)
    return config


def candidate_config_sha256(config: dict[str, Any]) -> str:
    public = {key: value for key, value in config.items() if not key.startswith("_")}
    canonical = json.dumps(
        public,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def selection_origin_labels(candidate_config: dict[str, Any]) -> list[str]:
    selection = candidate_config["selection_origins"]
    confirmation = candidate_config["confirmation_origins"]
    origins = [
        period_label(date)
        for date in quarter_starts(selection["start"], selection["end"])
    ]
    if len(origins) != int(selection["count"]):
        raise SelectionGuardError(
            f"Expected {selection['count']} selection origins, found {len(origins)}"
        )
    if period_start(selection["end"]) >= period_start(confirmation["start"]):
        raise SelectionGuardError("Selection and confirmation origins overlap")
    return origins


def _candidate_forecasts_for_alpha(
    panel: pd.DataFrame,
    cells: pd.DataFrame,
    *,
    modeling_start: str,
    alpha: float,
    procedure_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if procedure_id == PROCEDURE_ID:
        training_builder = build_training_examples
        prediction_builder = build_prediction_features
        fit_predict = fit_predict_ridge
        numeric_features = NUMERIC_FEATURES
    elif procedure_id == V2_PROCEDURE_ID:
        training_builder = build_v2_training_examples
        prediction_builder = build_v2_prediction_features
        fit_predict = fit_predict_v2_ridge
        numeric_features = V2_NUMERIC_FEATURES
    else:
        raise ValueError(f"Unsupported candidate procedure: {procedure_id}")

    forecast_frames: list[pd.DataFrame] = []
    coefficient_frames: list[pd.DataFrame] = []
    training_diagnostics: list[dict[str, object]] = []
    grouped = cells.groupby(["origin_date", "horizon"], sort=True)
    for (origin_date, horizon), group in grouped:
        origin = period_label(pd.Timestamp(origin_date))
        training = training_builder(
            panel,
            outer_origin=pd.Timestamp(origin_date),
            horizon=int(horizon),
            modeling_start=modeling_start,
        )
        prediction = prediction_builder(
            panel,
            group,
            modeling_start=modeling_start,
        )
        fitted = fit_predict(training, prediction, alpha=alpha)
        forecasts = fitted.predictions.copy()
        forecasts["model"] = procedure_id
        forecasts["alpha"] = float(alpha)
        forecasts["prediction_available"] = forecasts["forecast"].notna()
        forecasts["actual_observed"] = forecasts["actual"].notna()
        forecasts["scored"] = (
            forecasts["prediction_available"] & forecasts["actual_observed"]
        )
        forecasts["unscored_reason"] = np.select(
            [
                ~forecasts["actual_observed"]
                & ~forecasts["prediction_available"],
                ~forecasts["actual_observed"],
                ~forecasts["prediction_available"],
            ],
            ["actual_and_forecast_missing", "actual_missing", "forecast_missing"],
            default="",
        )
        forecast_frames.append(forecasts)

        coefficients = fitted.coefficients.copy()
        coefficients["alpha"] = float(alpha)
        coefficients["origin"] = origin
        coefficients["origin_date"] = pd.Timestamp(origin_date)
        coefficients["horizon"] = int(horizon)
        coefficients["intercept"] = fitted.intercept
        coefficient_frames.append(coefficients)

        numeric = training[list(numeric_features)].astype(float)
        standard_deviation = numeric.std(ddof=0).replace(0, np.nan)
        standardized = (numeric - numeric.mean()).div(standard_deviation)
        complete_columns = standardized.columns[standard_deviation.notna()]
        matrix = standardized[complete_columns].to_numpy(dtype=float)
        condition = float(np.linalg.cond(matrix)) if matrix.size else np.nan
        correlation = numeric[list(complete_columns)].corr().abs()
        upper = correlation.where(
            np.triu(np.ones(correlation.shape), k=1).astype(bool)
        )
        training_diagnostics.append(
            {
                "alpha": float(alpha),
                "origin": origin,
                "origin_date": pd.Timestamp(origin_date),
                "horizon": int(horizon),
                "training_rows": fitted.training_rows,
                "candidate_training_rows": training.attrs.get(
                    "candidate_rows", fitted.training_rows
                ),
                "excluded_training_rows": training.attrs.get("excluded_rows", 0),
                "numeric_condition_number": condition,
                "maximum_absolute_numeric_correlation": upper.max().max(),
            }
        )
    return (
        pd.concat(forecast_frames, ignore_index=True).sort_values(
            ["origin_date", "state_code", "horizon"]
        ).reset_index(drop=True),
        pd.concat(coefficient_frames, ignore_index=True).sort_values(
            ["origin_date", "horizon", "feature"]
        ).reset_index(drop=True),
        pd.DataFrame.from_records(training_diagnostics).sort_values(
            ["origin_date", "horizon"]
        ).reset_index(drop=True),
    )


def _comparator_metrics(baseline_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon in sorted(baseline_metrics["horizon"].unique()):
        model = "seasonal_naive" if int(horizon) == 3 else "persistence"
        row = baseline_metrics.loc[
            baseline_metrics["model"].eq(model)
            & baseline_metrics["horizon"].eq(horizon)
        ]
        if len(row) != 1:
            raise ValueError(f"Missing frozen comparator for horizon {horizon}")
        rows.append(
            {
                "horizon": int(horizon),
                "comparator_model": model,
                "comparator_wape": float(row.iloc[0]["wape"]),
            }
        )
    return pd.DataFrame.from_records(rows)


def _diagnostic_summary(forecasts: pd.DataFrame) -> pd.DataFrame:
    frame = forecasts.copy()
    frame["error"] = frame["forecast"] - frame["actual"]
    frame["absolute_error"] = frame["error"].abs()
    valid_scale = frame["mase_scale"].gt(0) & frame["mase_scale"].notna()
    frame["normalized_absolute_error"] = frame["absolute_error"].div(
        frame["mase_scale"].where(valid_scale)
    )
    records = []
    for horizon, group in frame.groupby("horizon", sort=True):
        scored = group.loc[group["scored"]]
        actual_volume = scored["actual"].sum()
        records.append(
            {
                "horizon": int(horizon),
                "forecast_rows": len(group),
                "scored_cells": len(scored),
                "aggregate_signed_bias": (
                    scored["error"].sum() / actual_volume
                    if actual_volume > 0
                    else np.nan
                ),
                "mean_absolute_error": scored["absolute_error"].mean(),
                "mean_normalized_absolute_error": scored[
                    "normalized_absolute_error"
                ].mean(),
                "zero_floor_rate": group["zero_floor_applied"].mean(),
                "unseen_state_rows": int((~group["state_seen_in_training"]).sum()),
            }
        )
    return pd.DataFrame.from_records(records)


def _paired_comparator_forecasts(
    candidate_forecasts: pd.DataFrame,
    baseline_forecasts: pd.DataFrame,
) -> pd.DataFrame:
    """Pair candidate forecasts with the frozen horizon-specific comparator."""
    keys = ["state_code", "origin_date", "target_date", "horizon"]
    candidate = candidate_forecasts[
        keys + ["actual", "forecast"]
    ].rename(columns={"forecast": "candidate_forecast"})
    baseline = baseline_forecasts.copy()
    comparator_mask = (
        baseline["horizon"].eq(3) & baseline["model"].eq("seasonal_naive")
    ) | (
        ~baseline["horizon"].eq(3) & baseline["model"].eq("persistence")
    )
    comparator = baseline.loc[
        comparator_mask, keys + ["forecast"]
    ].rename(columns={"forecast": "comparator_forecast"})
    paired = candidate.merge(
        comparator,
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if paired["comparator_forecast"].isna().any():
        raise ValueError("Frozen comparator forecasts are incomplete")
    return paired


def evaluate_candidate_selection(
    panel: pd.DataFrame,
    project_config: dict[str, Any],
    candidate_config: dict[str, Any],
    *,
    require_truncated_panel: bool = True,
) -> dict[str, Any]:
    """Evaluate alpha selection and diagnostics without confirmation results."""
    evaluation = project_config["evaluation"]
    procedure_id = candidate_config["procedure_id"]
    numeric_features = (
        NUMERIC_FEATURES if procedure_id == PROCEDURE_ID else V2_NUMERIC_FEATURES
    )
    origins = selection_origin_labels(candidate_config)
    target_end = add_quarters(
        candidate_config["selection_origins"]["end"],
        max(evaluation["forecast_horizons"]),
    )
    latest = pd.to_datetime(panel["quarter_start_date"]).max()
    if require_truncated_panel and latest > period_start(target_end):
        raise SelectionGuardError(
            f"Panel contains target values after selection target end {target_end}"
        )

    cells = build_forecast_cells_for_origins(
        panel,
        evaluation,
        origins=origins,
        target_end=target_end,
    )
    baseline_forecasts = generate_baseline_forecasts(cells, panel)
    baseline_state_metrics = summarize_state_metrics(baseline_forecasts)
    baseline_metrics = summarize_overall_metrics(
        baseline_forecasts, baseline_state_metrics
    )
    comparators = _comparator_metrics(baseline_metrics)

    alpha_forecasts: list[pd.DataFrame] = []
    alpha_coefficients: list[pd.DataFrame] = []
    alpha_training_diagnostics: list[pd.DataFrame] = []
    alpha_metric_frames: list[pd.DataFrame] = []
    for alpha in candidate_config["alpha_grid"]:
        forecasts, coefficients, training_diagnostics = _candidate_forecasts_for_alpha(
            panel,
            cells,
            modeling_start=evaluation["modeling_start"],
            alpha=float(alpha),
            procedure_id=procedure_id,
        )
        state_metrics = summarize_state_metrics(forecasts)
        metrics = summarize_overall_metrics(forecasts, state_metrics)
        metrics["alpha"] = float(alpha)
        metrics = metrics.merge(comparators, on="horizon", validate="one_to_one")
        alpha_forecasts.append(forecasts)
        alpha_coefficients.append(coefficients)
        alpha_training_diagnostics.append(training_diagnostics)
        alpha_metric_frames.append(metrics)

    alpha_metrics = pd.concat(alpha_metric_frames, ignore_index=True)
    selected_alpha, alpha_summary = select_shared_alpha(
        alpha_metrics[
            [
                "alpha",
                "horizon",
                "wape",
                "comparator_wape",
                "prediction_coverage",
            ]
        ],
        tie_tolerance=float(candidate_config["tie_tolerance"]),
    )
    all_forecasts = pd.concat(alpha_forecasts, ignore_index=True)
    all_coefficients = pd.concat(alpha_coefficients, ignore_index=True)
    all_training_diagnostics = pd.concat(
        alpha_training_diagnostics, ignore_index=True
    )
    candidate_forecasts = all_forecasts.loc[
        all_forecasts["alpha"].eq(selected_alpha)
    ].copy()
    candidate_forecasts = add_prequential_intervals(
        candidate_forecasts,
        warmup_origins=int(candidate_config["intervals"]["warmup_origins"]),
        coverages=tuple(float(value) for value in candidate_config["intervals"]["coverages"]),
    )
    candidate_state_metrics = summarize_state_metrics(candidate_forecasts)
    candidate_metrics = summarize_overall_metrics(
        candidate_forecasts, candidate_state_metrics
    )
    assert_complete_prediction_coverage(candidate_metrics)
    selected_coefficients = all_coefficients.loc[
        all_coefficients["alpha"].eq(selected_alpha)
    ].copy()
    selected_training_diagnostics = all_training_diagnostics.loc[
        all_training_diagnostics["alpha"].eq(selected_alpha)
    ].copy()
    selection_frame = validate_selection_frame(
        candidate_forecasts,
        selection_end=candidate_config["selection_origins"]["end"],
    )
    bin_frames = [
        binned_residual_summary(selection_frame, column="forecast")
    ]
    for feature in numeric_features:
        bin_frames.append(
            binned_residual_summary(selection_frame, column=feature)
        )
    paired_forecasts = _paired_comparator_forecasts(
        candidate_forecasts,
        baseline_forecasts,
    )
    bootstrap_config = candidate_config["bootstrap"]
    coverages = tuple(
        float(value) for value in candidate_config["intervals"]["coverages"]
    )

    return {
        "selected_alpha": selected_alpha,
        "target_end": target_end,
        "cells": cells,
        "baseline_forecasts": baseline_forecasts,
        "baseline_metrics": baseline_metrics,
        "alpha_metrics": alpha_metrics,
        "alpha_summary": alpha_summary,
        "candidate_forecasts": candidate_forecasts,
        "candidate_metrics": candidate_metrics,
        "candidate_state_metrics": candidate_state_metrics,
        "candidate_origin_metrics": summarize_origin_metrics(candidate_forecasts),
        "candidate_volume_metrics": summarize_volume_metrics(candidate_forecasts),
        "coefficient_paths": selected_coefficients,
        "training_diagnostics": selected_training_diagnostics,
        "diagnostic_summary": _diagnostic_summary(candidate_forecasts),
        "diagnostic_bins": pd.concat(bin_frames, ignore_index=True),
        "diagnostic_autocorrelation": residual_autocorrelation(
            selection_frame,
            lags=(1, 4),
            minimum_pairs=12,
        ),
        "interval_metrics": summarize_interval_metrics(
            candidate_forecasts,
            coverages=coverages,
        ),
        "bootstrap_skill": paired_moving_block_bootstrap_skill(
            paired_forecasts,
            block_length=int(bootstrap_config["block_length"]),
            replications=int(bootstrap_config["replications"]),
            seed=int(bootstrap_config["seed"]),
        ),
        "checks": {
            "prediction_coverage": "passed",
            "diagnostic_gate_status": "awaiting_review",
            "confirmation_opened": False,
            "holdout_opened": False,
        },
    }


def _load_latest_baseline_manifest(
    runs_root: Path,
    project_config: dict[str, Any],
    data_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Find a passed, unopened baseline run on the current data lineage."""
    expected_config_hash = config_sha256(project_config)
    expected_checkpoint = project_config["snapshot"]["checkpoint_id"]
    expected_state_hash = data_manifest["outputs"]["state_quarter"]["sha256"]
    for path in sorted(
        runs_root.glob("*/manifest.json"),
        key=lambda candidate: candidate.parent.name,
        reverse=True,
    ):
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        checks = candidate.get("checks", {})
        state_checkpoint = candidate.get("source_state_checkpoint", {})
        if (
            candidate.get("stage") == "development_baselines"
            and candidate.get("status") == "passed"
            and candidate.get("checkpoint_id") == expected_checkpoint
            and candidate.get("config_sha256") == expected_config_hash
            and candidate.get("source_data_run") == data_manifest["run_id"]
            and state_checkpoint.get("sha256") == expected_state_hash
            and checks.get("frozen_baseline_audit") == "passed"
            and checks.get("prediction_coverage") == "passed"
            and checks.get("holdout_opened") is False
        ):
            return {**candidate, "manifest_path": str(path)}
    raise SelectionGuardError(
        "No passed development baseline manifest matches the validated data lineage"
    )


def run_candidate_selection_evaluation(
    project_config_path: str | Path = "configs/project.json",
    candidate_config_path: str | Path = "configs/candidate.json",
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Run the frozen selection block and write auditable development artifacts."""
    started_at = datetime.now(timezone.utc)
    repository_root = Path(root).expanduser().resolve() if root else project_root()

    project_path = Path(project_config_path).expanduser()
    if not project_path.is_absolute():
        project_path = repository_root / project_path
    candidate_path = Path(candidate_config_path).expanduser()
    if not candidate_path.is_absolute():
        candidate_path = repository_root / candidate_path

    project_config = load_config(project_path)
    candidate_config = load_candidate_config(candidate_path)
    paths = resolve_pipeline_paths(project_config, repository_root)
    data_manifest = load_latest_validated_manifest(project_path, root=repository_root)
    baseline_manifest = _load_latest_baseline_manifest(
        paths["runs_root"], project_config, data_manifest
    )

    target_end = add_quarters(
        candidate_config["selection_origins"]["end"],
        max(project_config["evaluation"]["forecast_horizons"]),
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

    result = evaluate_candidate_selection(
        panel,
        project_config,
        candidate_config,
        require_truncated_panel=True,
    )
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
        "baseline_forecasts": (
            "selection_baseline_forecasts.parquet",
            "model, origin_date, state_code, horizon",
        ),
        "baseline_metrics": (
            "selection_baseline_metrics.parquet",
            "model, horizon",
        ),
        "alpha_metrics": ("candidate_alpha_metrics.parquet", "alpha, horizon"),
        "alpha_summary": ("candidate_alpha_summary.parquet", "alpha"),
        "candidate_forecasts": (
            "candidate_forecasts.parquet",
            "origin_date, state_code, horizon",
        ),
        "candidate_metrics": ("candidate_metrics.parquet", "model, horizon"),
        "candidate_state_metrics": (
            "candidate_state_metrics.parquet",
            "model, horizon, state_code",
        ),
        "candidate_origin_metrics": (
            "candidate_origin_metrics.parquet",
            "model, horizon, origin_date",
        ),
        "candidate_volume_metrics": (
            "candidate_volume_metrics.parquet",
            "model, horizon, actual_volume_band",
        ),
        "coefficient_paths": (
            "candidate_coefficient_paths.parquet",
            "origin_date, horizon, feature",
        ),
        "training_diagnostics": (
            "candidate_training_diagnostics.parquet",
            "origin_date, horizon",
        ),
        "diagnostic_summary": (
            "candidate_diagnostic_summary.parquet",
            "horizon",
        ),
        "diagnostic_bins": (
            "candidate_diagnostic_bins.parquet",
            "diagnostic, horizon, bin",
        ),
        "diagnostic_autocorrelation": (
            "candidate_diagnostic_autocorrelation.parquet",
            "horizon, state_code, lag",
        ),
        "interval_metrics": (
            "candidate_interval_metrics.parquet",
            "nominal_coverage, horizon",
        ),
        "bootstrap_skill": (
            "candidate_bootstrap_skill.parquet",
            "summary",
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
        "stage": "candidate_selection_diagnostics",
        "entry_point": (
            "coal_forecasting.candidate_selection."
            "run_candidate_selection_evaluation"
        ),
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "project": project_config["project"],
        "schema_version": candidate_config["schema_version"],
        "checkpoint_id": project_config["snapshot"]["checkpoint_id"],
        "project_config_sha256": config_sha256(project_config),
        "candidate_config_sha256": candidate_config_sha256(candidate_config),
        "procedure_id": candidate_config["procedure_id"],
        "git": git,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "duckdb": duckdb.__version__,
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
            "scikit_learn": _package_version("scikit-learn"),
            "scipy": _package_version("scipy"),
        },
        "parameters": {
            "modeling_start": project_config["evaluation"]["modeling_start"],
            "selection_origins": candidate_config["selection_origins"],
            "forecast_horizons": project_config["evaluation"]["forecast_horizons"],
            "selection_target_end": target_end,
            "alpha_grid": candidate_config["alpha_grid"],
            "selected_alpha": result["selected_alpha"],
            "intervals": candidate_config["intervals"],
            "bootstrap": candidate_config["bootstrap"],
        },
        "source_data_run": data_manifest["run_id"],
        "source_state_checkpoint": data_manifest["outputs"]["state_quarter"],
        "source_baseline_run": baseline_manifest["run_id"],
        "source_baseline_manifest": Path(
            baseline_manifest["manifest_path"]
        ).relative_to(paths["runs_root"]).as_posix(),
        "checks": result["checks"],
        "outputs": outputs,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        **result,
        "manifest": {**manifest, "manifest_path": str(manifest_path)},
    }
