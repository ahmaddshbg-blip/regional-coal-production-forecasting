"""Locked final-baseline selection, uncertainty, and holdout guards."""

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
from coal_forecasting.candidate_uncertainty import finite_sample_quantile
from coal_forecasting.candidate_uncertainty import summarize_interval_metrics
from coal_forecasting.config import config_sha256, load_config
from coal_forecasting.eda import add_quarters, period_label, period_start, quarter_starts
from coal_forecasting.evaluation import build_forecast_cells_for_origins
from coal_forecasting.metrics import (
    add_error_columns,
    assert_complete_prediction_coverage,
    summarize_origin_metrics,
    summarize_overall_metrics,
    summarize_state_metrics,
    summarize_volume_metrics,
)
from coal_forecasting.paths import project_root, resolve_pipeline_paths
from coal_forecasting.pipeline import load_latest_validated_manifest
from coal_forecasting.validation import sha256_file


PROCEDURE_ID = "horizon_specific_naive_baseline_v1"
OPENING_MARKER = "final_holdout_opened.json"


class HoldoutGuardError(ValueError):
    """Raised when final-holdout access violates the frozen procedure."""


def validate_final_config(
    final_config: dict[str, Any],
    project_config: dict[str, Any],
) -> dict[str, Any]:
    """Validate the final procedure against the already-frozen project contract."""
    required = {
        "schema_version",
        "procedure_id",
        "models_by_horizon",
        "development_calibration_origins",
        "holdout_origins",
        "latest_forecast",
        "intervals",
        "reporting",
    }
    missing = required.difference(final_config)
    if missing:
        raise ValueError(f"Final config is missing: {', '.join(sorted(missing))}")
    if final_config["procedure_id"] != PROCEDURE_ID:
        raise ValueError("Final procedure identifier is not frozen")

    evaluation = project_config["evaluation"]
    if final_config["development_calibration_origins"] != evaluation[
        "validation_origins"
    ]:
        raise HoldoutGuardError(
            "Development calibration origins do not match the frozen contract"
        )
    expected_mapping = {
        "1": "persistence",
        "2": "persistence",
        "3": "seasonal_naive",
        "4": "persistence",
    }
    if final_config["models_by_horizon"] != expected_mapping:
        raise HoldoutGuardError("Final horizon-to-model mapping is not frozen")

    holdout = final_config["holdout_origins"]
    for key in ("start", "end", "count"):
        if holdout.get(key) != evaluation["holdout_origins"].get(key):
            raise HoldoutGuardError(
                "Final holdout origins do not match the frozen contract"
            )
    if holdout.get("target_end") != evaluation["scored_target_end"]:
        raise HoldoutGuardError(
            "Final holdout target cutoff does not match the frozen contract"
        )

    latest = final_config["latest_forecast"]
    if latest.get("origin") != evaluation["latest_forecast_origin"]:
        raise HoldoutGuardError("Latest forecast origin is not frozen")
    expected_latest_end = add_quarters(
        evaluation["latest_forecast_origin"],
        max(evaluation["forecast_horizons"]),
    )
    if latest.get("target_end") != expected_latest_end:
        raise HoldoutGuardError("Latest forecast target cutoff is not frozen")
    if final_config["reporting"].get("reported_horizons") != evaluation[
        "forecast_horizons"
    ]:
        raise HoldoutGuardError("Reported horizons do not match the frozen contract")
    if tuple(final_config["intervals"].get("coverages", ())) != (0.8, 0.95):
        raise HoldoutGuardError("Final interval coverages are not frozen")
    return final_config


def load_final_config(
    path: str | Path,
    project_config: dict[str, Any],
) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    validate_final_config(config, project_config)
    config["_config_path"] = str(config_path)
    return config


def final_config_sha256(config: dict[str, Any]) -> str:
    public = {key: value for key, value in config.items() if not key.startswith("_")}
    canonical = json.dumps(
        public,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def holdout_origin_labels(
    final_config: dict[str, Any],
    project_config: dict[str, Any],
) -> list[str]:
    validate_final_config(final_config, project_config)
    specification = final_config["holdout_origins"]
    origins = [
        period_label(date)
        for date in quarter_starts(specification["start"], specification["end"])
    ]
    if len(origins) != int(specification["count"]):
        raise HoldoutGuardError(
            f"Expected {specification['count']} holdout origins, found {len(origins)}"
        )
    return origins


def select_final_forecasts(
    baseline_forecasts: pd.DataFrame,
    models_by_horizon: dict[str, str],
) -> pd.DataFrame:
    """Select the frozen baseline rule for every horizon and forecast cell."""
    required = {"state_code", "origin_date", "target_date", "horizon", "model"}
    missing = required.difference(baseline_forecasts.columns)
    if missing:
        raise ValueError(
            f"Baseline forecasts are missing: {', '.join(sorted(missing))}"
        )
    expected_horizons = {1, 2, 3, 4}
    configured_horizons = {int(value) for value in models_by_horizon}
    if configured_horizons != expected_horizons:
        raise ValueError("Final baseline mapping must define horizons one through four")

    frames = []
    for horizon in sorted(expected_horizons):
        source_model = models_by_horizon[str(horizon)]
        selected = baseline_forecasts.loc[
            baseline_forecasts["horizon"].eq(horizon)
            & baseline_forecasts["model"].eq(source_model)
        ].copy()
        if selected.empty:
            raise ValueError(
                f"Final baseline is missing {source_model} forecasts for H{horizon}"
            )
        selected["source_model"] = source_model
        selected["model"] = PROCEDURE_ID
        frames.append(selected)

    result = pd.concat(frames, ignore_index=True)
    keys = ["state_code", "origin_date", "target_date", "horizon"]
    if result.duplicated(keys).any():
        raise ValueError("Final baseline contains duplicate forecast cells")
    return result.sort_values(
        ["origin_date", "state_code", "horizon"]
    ).reset_index(drop=True)


def calibrate_baseline_intervals(
    development_forecasts: pd.DataFrame,
    *,
    development_end: str,
    coverages: tuple[float, ...] = (0.80, 0.95),
) -> pd.DataFrame:
    """Freeze horizon-specific interval quantiles from development only."""
    required = {
        "origin_date",
        "horizon",
        "forecast",
        "actual",
        "scored",
        "mase_scale",
    }
    missing = required.difference(development_forecasts.columns)
    if missing:
        raise ValueError(
            f"Development forecasts are missing: {', '.join(sorted(missing))}"
        )
    frame = development_forecasts.copy()
    frame["origin_date"] = pd.to_datetime(frame["origin_date"])
    if frame["origin_date"].gt(period_start(development_end)).any():
        raise HoldoutGuardError(
            "Interval calibration crossed the frozen development boundary"
        )
    scored = frame.loc[frame["scored"] & frame["actual"].notna()].copy()
    scored["absolute_error"] = (scored["forecast"] - scored["actual"]).abs()
    valid_scale = scored["mase_scale"].gt(0) & scored["mase_scale"].notna()
    scored["normalized_error"] = scored["absolute_error"].div(
        scored["mase_scale"].where(valid_scale)
    )

    records: list[dict[str, object]] = []
    for horizon, group in scored.groupby("horizon", sort=True):
        absolute = group["absolute_error"].dropna()
        normalized = group["normalized_error"].dropna()
        if absolute.empty or normalized.empty:
            raise ValueError(f"Interval calibration is empty for H{horizon}")
        for coverage in coverages:
            records.append(
                {
                    "horizon": int(horizon),
                    "nominal_coverage": float(coverage),
                    "normalized_quantile": finite_sample_quantile(
                        normalized, float(coverage)
                    ),
                    "unscaled_quantile": finite_sample_quantile(
                        absolute, float(coverage)
                    ),
                    "normalized_cells": len(normalized),
                    "unscaled_cells": len(absolute),
                    "calibration_origin_start": frame["origin_date"].min(),
                    "calibration_origin_end": frame["origin_date"].max(),
                }
            )
    return pd.DataFrame.from_records(records).sort_values(
        ["nominal_coverage", "horizon"]
    ).reset_index(drop=True)


def apply_frozen_intervals(
    forecasts: pd.DataFrame,
    quantiles: pd.DataFrame,
) -> pd.DataFrame:
    """Apply fixed development quantiles without consulting forecast actuals."""
    required_forecasts = {"horizon", "forecast", "mase_scale"}
    missing = required_forecasts.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Forecasts are missing: {', '.join(sorted(missing))}")
    required_quantiles = {
        "horizon",
        "nominal_coverage",
        "normalized_quantile",
        "unscaled_quantile",
    }
    missing_quantiles = required_quantiles.difference(quantiles.columns)
    if missing_quantiles:
        raise ValueError(
            f"Interval quantiles are missing: {', '.join(sorted(missing_quantiles))}"
        )

    frame = forecasts.copy().reset_index(drop=True)
    frame["interval_scale_source"] = ""
    for coverage in sorted(float(value) for value in quantiles["nominal_coverage"].unique()):
        suffix = str(int(round(coverage * 100)))
        lookup = quantiles.loc[
            quantiles["nominal_coverage"].eq(coverage),
            ["horizon", "normalized_quantile", "unscaled_quantile"],
        ]
        if lookup["horizon"].duplicated().any():
            raise ValueError(f"Duplicate interval quantiles for coverage {coverage}")
        joined = frame[["horizon", "mase_scale"]].merge(
            lookup,
            on="horizon",
            how="left",
            validate="many_to_one",
        )
        if joined[["normalized_quantile", "unscaled_quantile"]].isna().any().any():
            raise ValueError(f"Missing frozen interval quantile for coverage {coverage}")
        scaled = joined["mase_scale"].gt(0) & joined["mase_scale"].notna()
        margin = joined["unscaled_quantile"].where(
            ~scaled,
            joined["normalized_quantile"] * joined["mase_scale"],
        )
        frame[f"lower_{suffix}"] = np.maximum(0.0, frame["forecast"] - margin)
        frame[f"upper_{suffix}"] = frame["forecast"] + margin
        frame[f"interval_available_{suffix}"] = True
        frame.loc[scaled, "interval_scale_source"] = "state_mase_scale"
        frame.loc[~scaled, "interval_scale_source"] = "pooled_unscaled"
    return frame


def claim_holdout_once(
    runs_root: Path,
    *,
    procedure_sha256: str,
    open_holdout: bool,
    passed_run_id: str | None,
) -> dict[str, Any]:
    """Create or validate the durable marker guarding final-holdout access."""
    root = Path(runs_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    marker_path = root / OPENING_MARKER
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HoldoutGuardError("Final holdout marker is unreadable") from error
        if marker.get("procedure_sha256") != procedure_sha256:
            raise HoldoutGuardError(
                "Final holdout was opened under a different procedure hash"
            )
        if passed_run_id is None:
            raise HoldoutGuardError(
                "Final holdout was opened without a passed run; automatic retry is blocked"
            )
        marker_run_id = marker.get("run_id")
        if marker_run_id is not None and marker_run_id != passed_run_id:
            raise HoldoutGuardError(
                "Final holdout marker and passed manifest identify different runs"
            )
        return {
            "mode": "reuse",
            "run_id": passed_run_id,
            "marker_path": str(marker_path),
            "marker": marker,
        }

    if not open_holdout:
        raise HoldoutGuardError(
            "Final holdout requires an explicit open_holdout=True action"
        )
    marker = {
        "status": "opened",
        "opened_at_utc": datetime.now(timezone.utc).isoformat(),
        "procedure_sha256": procedure_sha256,
    }
    temporary = marker_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(marker_path)
    return {
        "mode": "new",
        "run_id": None,
        "marker_path": str(marker_path),
        "marker": marker,
    }


def complete_holdout_marker(
    marker_path: Path,
    *,
    procedure_sha256: str,
    run_id: str,
    manifest_path: str,
) -> None:
    """Mark a successfully persisted holdout run without weakening the guard."""
    path = Path(marker_path).expanduser().resolve()
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HoldoutGuardError("Final holdout marker is unreadable") from error
    if marker.get("procedure_sha256") != procedure_sha256:
        raise HoldoutGuardError("Final holdout marker procedure hash changed")
    if marker.get("run_id") not in (None, run_id):
        raise HoldoutGuardError("Final holdout marker already names another run")
    marker.update(
        {
            "status": "passed",
            "run_id": run_id,
            "manifest_path": manifest_path,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _assert_forecast_integrity(forecasts: pd.DataFrame, *, latest: bool) -> None:
    if forecasts.empty:
        raise ValueError("Final forecast table is empty")
    if not forecasts["prediction_available"].all():
        raise ValueError("An eligible final forecast is unavailable")
    values = forecasts["forecast"].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Final forecasts must be finite and non-negative")
    if latest and (
        forecasts["actual"].notna().any()
        or forecasts["actual_observed"].any()
        or forecasts["scored"].any()
    ):
        raise HoldoutGuardError("Latest-origin forecasts contain future actuals")


def build_latest_forecasts(
    panel: pd.DataFrame,
    project_config: dict[str, Any],
    final_config: dict[str, Any],
    quantiles: pd.DataFrame,
) -> pd.DataFrame:
    """Create the locked, unscored latest-origin forecast."""
    validate_final_config(final_config, project_config)
    latest = final_config["latest_forecast"]
    cells = build_forecast_cells_for_origins(
        panel,
        project_config["evaluation"],
        origins=[latest["origin"]],
        target_end=latest["target_end"],
    )
    baseline = generate_baseline_forecasts(cells, panel)
    selected = select_final_forecasts(
        baseline,
        final_config["models_by_horizon"],
    )
    forecasts = apply_frozen_intervals(selected, quantiles)
    forecasts = add_error_columns(forecasts)
    forecasts["source_snapshot"] = project_config["snapshot"]["checkpoint_id"]
    forecasts["revision_status"] = latest["revision_status"]
    _assert_forecast_integrity(forecasts, latest=True)
    return forecasts


def build_latest_planning_summary(
    latest_forecasts: pd.DataFrame,
    *,
    focus_horizons: tuple[int, ...] = (1, 2),
) -> pd.DataFrame:
    """Rank states using only locked near-term point forecasts and widths."""
    records: list[dict[str, object]] = []
    focus = latest_forecasts.loc[
        latest_forecasts["horizon"].isin(focus_horizons)
    ]
    for state, group in focus.groupby("state_code", sort=True):
        if set(group["horizon"].astype(int)) != set(focus_horizons):
            raise ValueError(f"Incomplete near-term forecast for state {state}")
        record: dict[str, object] = {"state_code": state}
        for row in group.itertuples(index=False):
            horizon = int(row.horizon)
            record[f"h{horizon}_target_period"] = row.target_period
            record[f"h{horizon}_forecast"] = float(row.forecast)
            record[f"h{horizon}_lower_80"] = float(row.lower_80)
            record[f"h{horizon}_upper_80"] = float(row.upper_80)
        record["near_term_mean_forecast"] = float(group["forecast"].mean())
        record["near_term_mean_width_80"] = float(
            (group["upper_80"] - group["lower_80"]).mean()
        )
        records.append(record)
    summary = pd.DataFrame.from_records(records)
    summary["review_priority_rank"] = (
        summary["near_term_mean_forecast"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    return summary.sort_values(
        ["review_priority_rank", "state_code"]
    ).reset_index(drop=True)


def evaluate_final_frames(
    holdout_panel: pd.DataFrame,
    latest_panel: pd.DataFrame,
    development_baseline_forecasts: pd.DataFrame,
    project_config: dict[str, Any],
    final_config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Evaluate the frozen holdout once and create the latest forecast."""
    validate_final_config(final_config, project_config)
    development = select_final_forecasts(
        development_baseline_forecasts,
        final_config["models_by_horizon"],
    )
    quantiles = calibrate_baseline_intervals(
        development,
        development_end=final_config["development_calibration_origins"]["end"],
        coverages=tuple(final_config["intervals"]["coverages"]),
    )

    holdout_cells = build_forecast_cells_for_origins(
        holdout_panel,
        project_config["evaluation"],
        origins=holdout_origin_labels(final_config, project_config),
        target_end=final_config["holdout_origins"]["target_end"],
    )
    holdout_baselines = generate_baseline_forecasts(holdout_cells, holdout_panel)
    holdout = select_final_forecasts(
        holdout_baselines,
        final_config["models_by_horizon"],
    )
    holdout = apply_frozen_intervals(holdout, quantiles)
    holdout = add_error_columns(holdout)
    holdout["source_snapshot"] = project_config["snapshot"]["checkpoint_id"]
    holdout["revision_status"] = "frozen_latest_vintage_evaluation"
    _assert_forecast_integrity(holdout, latest=False)
    state_metrics = summarize_state_metrics(holdout)
    metrics = summarize_overall_metrics(holdout, state_metrics)
    assert_complete_prediction_coverage(metrics)

    latest = build_latest_forecasts(
        latest_panel,
        project_config,
        final_config,
        quantiles,
    )
    interval_by_horizon = summarize_interval_metrics(
        holdout,
        coverages=tuple(final_config["intervals"]["coverages"]),
    )
    interval_by_horizon["evaluation_scope"] = "horizon"
    interval_pooled = summarize_interval_metrics(
        holdout.assign(horizon=0),
        coverages=tuple(final_config["intervals"]["coverages"]),
    )
    interval_pooled["horizon"] = pd.NA
    interval_pooled["evaluation_scope"] = "pooled"
    interval_metrics = pd.concat(
        [interval_by_horizon, interval_pooled],
        ignore_index=True,
    )
    interval_metrics["horizon"] = interval_metrics["horizon"].astype("Int64")

    return {
        "calibration_quantiles": quantiles,
        "holdout_forecasts": holdout,
        "holdout_metrics": metrics,
        "holdout_state_metrics": state_metrics,
        "holdout_origin_metrics": summarize_origin_metrics(holdout),
        "holdout_volume_metrics": summarize_volume_metrics(holdout),
        "holdout_interval_metrics": interval_metrics,
        "latest_forecasts": latest,
        "latest_planning_summary": build_latest_planning_summary(
            latest,
            focus_horizons=tuple(
                final_config["reporting"]["operational_focus_horizons"]
            ),
        ),
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


def _validated_artifact_path(
    runs_root: Path,
    details: dict[str, Any],
) -> Path:
    root = runs_root.resolve()
    path = (root / details["path"]).resolve()
    if not path.is_relative_to(root):
        raise HoldoutGuardError("Artifact path escapes the runs root")
    if not path.is_file():
        raise HoldoutGuardError(f"Expected artifact is missing: {details['path']}")
    if path.stat().st_size != int(details["bytes"]):
        raise HoldoutGuardError(f"Artifact byte size changed: {details['path']}")
    if sha256_file(path) != details["sha256"]:
        raise HoldoutGuardError(f"Artifact hash changed: {details['path']}")
    return path


def _load_latest_baseline_manifest(
    runs_root: Path,
    project_config: dict[str, Any],
    data_manifest: dict[str, Any],
) -> dict[str, Any]:
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
            forecast_details = candidate.get("outputs", {}).get("forecasts")
            if not forecast_details:
                raise HoldoutGuardError("Baseline manifest has no forecast artifact")
            _validated_artifact_path(runs_root, forecast_details)
            return {**candidate, "manifest_path": str(path)}
    raise HoldoutGuardError(
        "No passed development baseline manifest matches the validated data lineage"
    )


def _load_passed_final_manifest(
    runs_root: Path,
    *,
    project_config: dict[str, Any],
    final_config_hash: str,
    data_run_id: str,
    baseline_run_id: str,
) -> dict[str, Any] | None:
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
        matches = (
            candidate.get("stage") == "final_baseline_holdout"
            and candidate.get("status") == "passed"
            and candidate.get("checkpoint_id")
            == project_config["snapshot"]["checkpoint_id"]
            and candidate.get("project_config_sha256")
            == config_sha256(project_config)
            and candidate.get("final_config_sha256") == final_config_hash
            and candidate.get("procedure_id") == PROCEDURE_ID
            and candidate.get("source_data_run") == data_run_id
            and candidate.get("source_baseline_run") == baseline_run_id
            and checks.get("holdout_opened") is True
            and checks.get("candidate_confirmation_opened") is False
        )
        if matches:
            expected_outputs = {
                "calibration_quantiles",
                "holdout_forecasts",
                "holdout_metrics",
                "holdout_state_metrics",
                "holdout_origin_metrics",
                "holdout_volume_metrics",
                "holdout_interval_metrics",
                "latest_forecasts",
                "latest_planning_summary",
            }
            outputs = candidate.get("outputs", {})
            if set(outputs) != expected_outputs:
                raise HoldoutGuardError(
                    "Passed final manifest has an incomplete artifact set"
                )
            for details in outputs.values():
                _validated_artifact_path(runs_root, details)
            return {**candidate, "manifest_path": str(path)}
    return None


def _read_parquet(path: Path) -> pd.DataFrame:
    with duckdb.connect() as connection:
        return connection.execute(
            "SELECT * FROM read_parquet(?)",
            [str(path)],
        ).fetchdf()


def _load_run_outputs(
    runs_root: Path,
    manifest: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    return {
        name: _read_parquet(_validated_artifact_path(runs_root, details))
        for name, details in manifest["outputs"].items()
    }


def run_final_baseline_evaluation(
    project_config_path: str | Path = "configs/project.json",
    final_config_path: str | Path = "configs/final_baseline.json",
    *,
    open_holdout: bool = False,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Open the final holdout once, or reuse its validated passed artifacts."""
    started_at = datetime.now(timezone.utc)
    repository_root = Path(root).expanduser().resolve() if root else project_root()
    project_path = Path(project_config_path).expanduser()
    if not project_path.is_absolute():
        project_path = repository_root / project_path
    final_path = Path(final_config_path).expanduser()
    if not final_path.is_absolute():
        final_path = repository_root / final_path

    project_config = load_config(project_path)
    final_config = load_final_config(final_path, project_config)
    procedure_hash = final_config_sha256(final_config)
    paths = resolve_pipeline_paths(project_config, repository_root)
    data_manifest = load_latest_validated_manifest(project_path, root=repository_root)
    baseline_manifest = _load_latest_baseline_manifest(
        paths["runs_root"], project_config, data_manifest
    )
    passed_manifest = _load_passed_final_manifest(
        paths["runs_root"],
        project_config=project_config,
        final_config_hash=procedure_hash,
        data_run_id=data_manifest["run_id"],
        baseline_run_id=baseline_manifest["run_id"],
    )
    if passed_manifest:
        access = claim_holdout_once(
            paths["runs_root"],
            procedure_sha256=procedure_hash,
            open_holdout=open_holdout,
            passed_run_id=passed_manifest["run_id"],
        )
        result = _load_run_outputs(paths["runs_root"], passed_manifest)
        return {
            **result,
            "access_mode": "reuse",
            "manifest": passed_manifest,
        }

    baseline_forecast_path = _validated_artifact_path(
        paths["runs_root"], baseline_manifest["outputs"]["forecasts"]
    )
    development_forecasts = _read_parquet(baseline_forecast_path)
    development = select_final_forecasts(
        development_forecasts,
        final_config["models_by_horizon"],
    )
    calibrate_baseline_intervals(
        development,
        development_end=final_config["development_calibration_origins"]["end"],
        coverages=tuple(final_config["intervals"]["coverages"]),
    )

    # The durable marker is created only after development artifacts pass, and
    # immediately before any holdout target magnitudes can be queried.
    access = claim_holdout_once(
        paths["runs_root"],
        procedure_sha256=procedure_hash,
        open_holdout=open_holdout,
        passed_run_id=None,
    )

    holdout_cutoff = final_config["holdout_origins"]["target_end"]
    latest_cutoff = final_config["latest_forecast"]["origin"]
    with duckdb.connect() as connection:
        holdout_panel = connection.execute(
            """
            SELECT *
            FROM read_parquet(?)
            WHERE quarter_start_date <= CAST(? AS DATE)
            ORDER BY state_code, quarter_start_date
            """,
            [str(paths["state_quarter"]), period_start(holdout_cutoff).date()],
        ).fetchdf()
        latest_panel = connection.execute(
            """
            SELECT *
            FROM read_parquet(?)
            WHERE quarter_start_date <= CAST(? AS DATE)
            ORDER BY state_code, quarter_start_date
            """,
            [str(paths["state_quarter"]), period_start(latest_cutoff).date()],
        ).fetchdf()

    result = evaluate_final_frames(
        holdout_panel,
        latest_panel,
        development_forecasts,
        project_config,
        final_config,
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
        "calibration_quantiles": (
            "final_calibration_quantiles.parquet",
            "nominal_coverage, horizon",
        ),
        "holdout_forecasts": (
            "final_holdout_forecasts.parquet",
            "origin_date, state_code, horizon",
        ),
        "holdout_metrics": ("final_holdout_metrics.parquet", "horizon"),
        "holdout_state_metrics": (
            "final_holdout_state_metrics.parquet",
            "horizon, state_code",
        ),
        "holdout_origin_metrics": (
            "final_holdout_origin_metrics.parquet",
            "horizon, origin_date",
        ),
        "holdout_volume_metrics": (
            "final_holdout_volume_metrics.parquet",
            "horizon, actual_volume_band",
        ),
        "holdout_interval_metrics": (
            "final_holdout_interval_metrics.parquet",
            "nominal_coverage, horizon",
        ),
        "latest_forecasts": (
            "latest_state_forecasts.parquet",
            "state_code, horizon",
        ),
        "latest_planning_summary": (
            "latest_planning_summary.parquet",
            "review_priority_rank, state_code",
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
        "stage": "final_baseline_holdout",
        "entry_point": (
            "coal_forecasting.final_baseline.run_final_baseline_evaluation"
        ),
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "project": project_config["project"],
        "schema_version": final_config["schema_version"],
        "checkpoint_id": project_config["snapshot"]["checkpoint_id"],
        "project_config_sha256": config_sha256(project_config),
        "final_config_sha256": procedure_hash,
        "procedure_id": PROCEDURE_ID,
        "git": git,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "duckdb": duckdb.__version__,
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
        },
        "parameters": {
            "development_calibration_origins": final_config[
                "development_calibration_origins"
            ],
            "holdout_origins": final_config["holdout_origins"],
            "latest_forecast": final_config["latest_forecast"],
            "models_by_horizon": final_config["models_by_horizon"],
            "intervals": final_config["intervals"],
            "reporting": final_config["reporting"],
        },
        "source_data_run": data_manifest["run_id"],
        "source_state_checkpoint": data_manifest["outputs"]["state_quarter"],
        "source_baseline_run": baseline_manifest["run_id"],
        "source_baseline_forecasts": baseline_manifest["outputs"]["forecasts"],
        "holdout_marker": Path(access["marker_path"])
        .relative_to(paths["runs_root"])
        .as_posix(),
        "checks": {
            "prediction_coverage": "passed",
            "latest_forecasts_unscored": True,
            "holdout_opened": True,
            "candidate_confirmation_opened": False,
        },
        "outputs": outputs,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    complete_holdout_marker(
        Path(access["marker_path"]),
        procedure_sha256=procedure_hash,
        run_id=run_id,
        manifest_path=manifest_path.relative_to(paths["runs_root"]).as_posix(),
    )
    return {
        **result,
        "access_mode": "new",
        "manifest": {**manifest, "manifest_path": str(manifest_path)},
    }
