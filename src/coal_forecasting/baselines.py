"""Frozen baseline forecasts for quarterly state production."""

from __future__ import annotations

import numpy as np
import pandas as pd

from coal_forecasting.eda import period_label, prepare_state_panel


BASELINE_NAMES = ("persistence", "seasonal_naive")
TARGET_COLUMN = "coal_production_short_tons"


def generate_baseline_forecasts(
    forecast_cells: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """Attach persistence and annual seasonal-naive forecasts to cells."""
    required = {
        "state_code",
        "origin",
        "origin_date",
        "target_period",
        "target_date",
        "horizon",
        "eligible",
        "actual",
        "mase_scale",
        "mase_scale_observations",
    }
    missing = required.difference(forecast_cells.columns)
    if missing:
        raise ValueError(f"Forecast cells are missing: {', '.join(sorted(missing))}")
    if forecast_cells.duplicated(
        ["state_code", "origin_date", "horizon"]
    ).any():
        raise ValueError("Forecast cells contain duplicate state-origin-horizon keys")
    if not forecast_cells["eligible"].all():
        raise ValueError("Baseline forecasts may be generated only for eligible cells")

    prepared = prepare_state_panel(panel)
    source = prepared[
        ["state_code", "quarter_start_date", TARGET_COLUMN]
    ].rename(
        columns={
            "quarter_start_date": "forecast_source_date",
            TARGET_COLUMN: "forecast",
        }
    )

    frames: list[pd.DataFrame] = []
    for model in BASELINE_NAMES:
        frame = forecast_cells.copy()
        frame["model"] = model
        if model == "persistence":
            frame["forecast_source_date"] = frame["origin_date"]
        else:
            frame["forecast_source_date"] = frame["target_date"] - pd.DateOffset(
                months=12
            )
        frame = frame.merge(
            source,
            on=["state_code", "forecast_source_date"],
            how="left",
            validate="many_to_one",
        )
        frame["forecast_source_period"] = frame["forecast_source_date"].map(
            period_label
        )
        frames.append(frame)

    forecasts = pd.concat(frames, ignore_index=True)
    if forecasts["forecast_source_date"].gt(forecasts["origin_date"]).any():
        raise ValueError("A baseline forecast uses information after its origin")

    forecasts["prediction_available"] = forecasts["forecast"].notna()
    forecasts["actual_observed"] = forecasts["actual"].notna()
    forecasts["scored"] = (
        forecasts["prediction_available"] & forecasts["actual_observed"]
    )
    forecasts["unscored_reason"] = np.select(
        [
            ~forecasts["actual_observed"] & ~forecasts["prediction_available"],
            ~forecasts["actual_observed"],
            ~forecasts["prediction_available"],
        ],
        ["actual_and_forecast_missing", "actual_missing", "forecast_missing"],
        default="",
    )
    return forecasts.sort_values(
        ["model", "origin_date", "state_code", "horizon"]
    ).reset_index(drop=True)
