"""Forecast metrics for development-only chronological evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_FORECAST_COLUMNS = {
    "model",
    "state_code",
    "origin",
    "origin_date",
    "horizon",
    "forecast",
    "actual",
    "prediction_available",
    "actual_observed",
    "scored",
    "mase_scale",
}


def add_error_columns(forecasts: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_FORECAST_COLUMNS.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Forecast table is missing: {', '.join(sorted(missing))}")
    frame = forecasts.copy()
    frame["error"] = frame["forecast"] - frame["actual"]
    frame["absolute_error"] = frame["error"].abs()
    frame["squared_error"] = frame["error"].pow(2)
    valid_scale = frame["mase_scale"].gt(0) & frame["mase_scale"].notna()
    frame["scaled_absolute_error"] = frame["absolute_error"].div(
        frame["mase_scale"].where(valid_scale)
    )
    return frame


def assign_actual_volume_bands(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Assign development-only actual-volume quartiles consistently by cell."""
    frame = forecasts.copy()
    cell_keys = ["state_code", "origin_date", "horizon"]
    cells = frame.loc[frame["actual_observed"], cell_keys + ["actual"]].drop_duplicates(
        cell_keys
    )
    percent_rank = cells["actual"].rank(method="average", pct=True)
    cells["actual_volume_band"] = pd.cut(
        percent_rank,
        bins=[0.0, 0.25, 0.5, 0.75, 1.0],
        labels=["low", "medium", "high", "very_high"],
        include_lowest=True,
    ).astype("string")
    return frame.merge(cells[cell_keys + ["actual_volume_band"]], on=cell_keys, how="left")


def _metric_record(group: pd.DataFrame) -> dict[str, float | int]:
    scored = group.loc[group["scored"]]
    actual_volume = scored["actual"].sum()
    predicted_rows = int(group["prediction_available"].sum())
    forecast_rows = len(group)
    scored_cells = len(scored)
    return {
        "forecast_rows": forecast_rows,
        "predicted_rows": predicted_rows,
        "scored_cells": scored_cells,
        "prediction_coverage": predicted_rows / forecast_rows if forecast_rows else np.nan,
        "target_availability": scored_cells / forecast_rows if forecast_rows else np.nan,
        "actual_volume": actual_volume,
        "wape": (
            scored["absolute_error"].sum() / actual_volume
            if actual_volume > 0
            else np.nan
        ),
        "mae": scored["absolute_error"].mean(),
        "rmse": np.sqrt(scored["squared_error"].mean()),
        "signed_mean_error": scored["error"].mean(),
        "aggregate_signed_bias": (
            scored["error"].sum() / actual_volume
            if actual_volume > 0
            else np.nan
        ),
        "defined_mase_cells": int(scored["scaled_absolute_error"].notna().sum()),
    }


def summarize_state_metrics(forecasts: pd.DataFrame) -> pd.DataFrame:
    frame = add_error_columns(forecasts)
    records = []
    for (model, horizon, state), group in frame.groupby(
        ["model", "horizon", "state_code"], sort=True
    ):
        scored = group.loc[group["scored"]]
        actual_volume = scored["actual"].sum()
        records.append(
            {
                "model": model,
                "horizon": int(horizon),
                "state_code": state,
                "forecast_rows": len(group),
                "scored_cells": len(scored),
                "actual_volume": actual_volume,
                "wape": (
                    scored["absolute_error"].sum() / actual_volume
                    if actual_volume > 0
                    else np.nan
                ),
                "mae": scored["absolute_error"].mean(),
                "rmse": np.sqrt(scored["squared_error"].mean()),
                "signed_mean_error": scored["error"].mean(),
                "mase": scored["scaled_absolute_error"].mean(),
                "defined_mase_cells": int(
                    scored["scaled_absolute_error"].notna().sum()
                ),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(
        ["model", "horizon", "state_code"]
    ).reset_index(drop=True)


def summarize_overall_metrics(
    forecasts: pd.DataFrame,
    state_metrics: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frame = add_error_columns(forecasts)
    states = state_metrics if state_metrics is not None else summarize_state_metrics(frame)
    records = []
    for (model, horizon), group in frame.groupby(["model", "horizon"], sort=True):
        record: dict[str, object] = {
            "model": model,
            "horizon": int(horizon),
            **_metric_record(group),
        }
        state_group = states.loc[
            states["model"].eq(model) & states["horizon"].eq(horizon)
        ]
        record.update(
            {
                "mean_state_mase": state_group["mase"].mean(),
                "median_state_mase": state_group["mase"].median(),
                "defined_mase_states": int(state_group["mase"].notna().sum()),
            }
        )
        records.append(record)
    return pd.DataFrame.from_records(records).sort_values(
        ["model", "horizon"]
    ).reset_index(drop=True)


def summarize_origin_metrics(forecasts: pd.DataFrame) -> pd.DataFrame:
    frame = add_error_columns(forecasts)
    records = []
    for (model, horizon, origin, origin_date), group in frame.groupby(
        ["model", "horizon", "origin", "origin_date"], sort=True
    ):
        records.append(
            {
                "model": model,
                "horizon": int(horizon),
                "origin": origin,
                "origin_date": origin_date,
                **_metric_record(group),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(
        ["model", "horizon", "origin_date"]
    ).reset_index(drop=True)


def summarize_volume_metrics(forecasts: pd.DataFrame) -> pd.DataFrame:
    frame = add_error_columns(assign_actual_volume_bands(forecasts))
    scored = frame.loc[frame["scored"] & frame["actual_volume_band"].notna()]
    records = []
    for (model, horizon, band), group in scored.groupby(
        ["model", "horizon", "actual_volume_band"], observed=True, sort=True
    ):
        records.append(
            {
                "model": model,
                "horizon": int(horizon),
                "actual_volume_band": str(band),
                **_metric_record(group),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(
        ["model", "horizon", "actual_volume_band"]
    ).reset_index(drop=True)


def assert_complete_prediction_coverage(metrics: pd.DataFrame) -> None:
    incomplete = metrics.loc[~metrics["prediction_coverage"].eq(1.0)]
    if not incomplete.empty:
        labels = ", ".join(
            f"{row.model}/h{row.horizon}" for row in incomplete.itertuples()
        )
        raise ValueError(f"Incomplete baseline prediction coverage: {labels}")
