"""Origin-safe features for the frozen pooled Ridge candidate."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from coal_forecasting.eda import period_label, period_start, prepare_state_panel


TARGET_COLUMN = "coal_production_short_tons"
NUMERIC_FEATURES = (
    "log_level_t",
    "log_change_1",
    "log_change_2",
    "log_change_3",
    "recent_zero_count",
    "origin_index",
)
RAW_DELTA_NUMERIC_FEATURES = (
    "level_t",
    "raw_change_1",
    "raw_change_2",
    "raw_change_3",
    "recent_zero_count",
    "origin_index",
)
CATEGORICAL_FEATURES = ("state_code", "target_quarter")


class CandidateFeatureError(ValueError):
    """Raised when candidate features violate their temporal contract."""


def _quarter_index(values: Iterable[pd.Timestamp], start: pd.Timestamp) -> np.ndarray:
    dates = pd.DatetimeIndex(pd.to_datetime(list(values)))
    return (dates.year - start.year) * 4 + ((dates.month - 1) // 3) - (
        (start.month - 1) // 3
    )


def _feature_rows(
    panel: pd.DataFrame,
    points: pd.DataFrame,
    *,
    date_column: str,
    modeling_start: str,
) -> pd.DataFrame:
    required = {"state_code", date_column, "horizon"}
    missing = required.difference(points.columns)
    if missing:
        raise CandidateFeatureError(
            f"Feature points are missing: {', '.join(sorted(missing))}"
        )
    if points.duplicated(["state_code", date_column, "horizon"]).any():
        raise CandidateFeatureError("Feature points contain duplicate keys")

    prepared = prepare_state_panel(panel)
    frame = points.copy()
    frame[date_column] = pd.to_datetime(frame[date_column])
    if not frame["horizon"].isin([1, 2, 3, 4]).all():
        raise CandidateFeatureError("Candidate horizons must be one through four")

    source = prepared[["state_code", "quarter_start_date", TARGET_COLUMN]]
    for lag in range(4):
        lookup = source.copy()
        lookup[date_column] = lookup["quarter_start_date"] + pd.DateOffset(
            months=3 * lag
        )
        lookup = lookup.rename(columns={TARGET_COLUMN: f"target_lag_{lag}"})
        frame = frame.merge(
            lookup[["state_code", date_column, f"target_lag_{lag}"]],
            on=["state_code", date_column],
            how="left",
            validate="many_to_one",
        )

    log_lags = [np.log1p(frame[f"target_lag_{lag}"]) for lag in range(4)]
    frame["log_level_t"] = log_lags[0]
    frame["log_change_1"] = log_lags[0] - log_lags[1]
    frame["log_change_2"] = log_lags[1] - log_lags[2]
    frame["log_change_3"] = log_lags[2] - log_lags[3]
    lag_columns = [f"target_lag_{lag}" for lag in range(4)]
    frame["recent_zero_count"] = frame[lag_columns].eq(0).sum(axis=1).astype(int)
    frame["origin_index"] = _quarter_index(
        frame[date_column], period_start(modeling_start)
    ).astype(int)
    frame["target_date"] = frame.apply(
        lambda row: row[date_column]
        + pd.DateOffset(months=3 * int(row["horizon"])),
        axis=1,
    )
    frame["target_quarter"] = (
        ((frame["target_date"].dt.month - 1) // 3) + 1
    ).astype(int)
    frame["feature_complete"] = frame[lag_columns].notna().all(axis=1)
    return frame


def build_training_examples(
    panel: pd.DataFrame,
    *,
    outer_origin: str | pd.Timestamp,
    horizon: int,
    modeling_start: str,
) -> pd.DataFrame:
    """Build direct supervised rows whose labels are known at the outer origin."""
    prepared = prepare_state_panel(panel)
    outer_date = (
        period_start(outer_origin)
        if isinstance(outer_origin, str)
        else pd.Timestamp(outer_origin)
    )
    earliest = period_start(modeling_start) + pd.DateOffset(months=9)
    latest = outer_date - pd.DateOffset(months=3 * int(horizon))
    points = prepared.loc[
        prepared["quarter_start_date"].between(earliest, latest),
        ["state_code", "quarter_start_date"],
    ].rename(columns={"quarter_start_date": "pseudo_origin_date"})
    points["horizon"] = int(horizon)

    featured = _feature_rows(
        prepared,
        points,
        date_column="pseudo_origin_date",
        modeling_start=modeling_start,
    )
    labels = prepared[["state_code", "quarter_start_date", TARGET_COLUMN]].rename(
        columns={"quarter_start_date": "target_date", TARGET_COLUMN: "label"}
    )
    featured = featured.merge(
        labels,
        on=["state_code", "target_date"],
        how="left",
        validate="many_to_one",
    )
    valid = (
        featured["feature_complete"]
        & featured["label"].notna()
        & featured["target_date"].le(outer_date)
    )
    candidate_rows = len(featured)
    featured = featured.loc[valid].copy()
    featured["response"] = np.log1p(featured["label"]) - featured["log_level_t"]
    featured["pseudo_origin"] = featured["pseudo_origin_date"].map(period_label)
    featured.attrs["candidate_rows"] = candidate_rows
    featured.attrs["excluded_rows"] = candidate_rows - len(featured)
    columns = [
        "state_code",
        "pseudo_origin",
        "pseudo_origin_date",
        "target_date",
        "horizon",
        *NUMERIC_FEATURES,
        "target_quarter",
        "response",
    ]
    return featured[columns].sort_values(
        ["pseudo_origin_date", "state_code"]
    ).reset_index(drop=True)


def build_prediction_features(
    panel: pd.DataFrame,
    forecast_cells: pd.DataFrame,
    *,
    modeling_start: str,
) -> pd.DataFrame:
    """Attach the guaranteed four-quarter feature set to forecast cells."""
    cells = forecast_cells.copy()
    cells["origin_date"] = pd.to_datetime(cells["origin_date"])
    featured = _feature_rows(
        panel,
        cells,
        date_column="origin_date",
        modeling_start=modeling_start,
    )
    incomplete = featured.loc[~featured["feature_complete"]]
    if not incomplete.empty:
        keys = ", ".join(
            f"{row.state_code}/{period_label(row.origin_date)}/h{row.horizon}"
            for row in incomplete.head(5).itertuples()
        )
        raise CandidateFeatureError(
            "Eligible candidate rows lack the required four-quarter features: "
            + keys
        )
    return featured.drop(columns=["feature_complete"]).reset_index(drop=True)


def _add_raw_delta_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["level_t"] = result["target_lag_0"]
    result["raw_change_1"] = result["target_lag_0"] - result["target_lag_1"]
    result["raw_change_2"] = result["target_lag_1"] - result["target_lag_2"]
    result["raw_change_3"] = result["target_lag_2"] - result["target_lag_3"]
    return result


def build_raw_delta_training_examples(
    panel: pd.DataFrame,
    *,
    outer_origin: str | pd.Timestamp,
    horizon: int,
    modeling_start: str,
) -> pd.DataFrame:
    """Build origin-safe training rows for the raw-delta Ridge candidate."""
    prepared = prepare_state_panel(panel)
    outer_date = (
        period_start(outer_origin)
        if isinstance(outer_origin, str)
        else pd.Timestamp(outer_origin)
    )
    earliest = period_start(modeling_start) + pd.DateOffset(months=9)
    latest = outer_date - pd.DateOffset(months=3 * int(horizon))
    points = prepared.loc[
        prepared["quarter_start_date"].between(earliest, latest),
        ["state_code", "quarter_start_date"],
    ].rename(columns={"quarter_start_date": "pseudo_origin_date"})
    points["horizon"] = int(horizon)

    featured = _add_raw_delta_features(
        _feature_rows(
            prepared,
            points,
            date_column="pseudo_origin_date",
            modeling_start=modeling_start,
        )
    )
    labels = prepared[["state_code", "quarter_start_date", TARGET_COLUMN]].rename(
        columns={"quarter_start_date": "target_date", TARGET_COLUMN: "label"}
    )
    featured = featured.merge(
        labels,
        on=["state_code", "target_date"],
        how="left",
        validate="many_to_one",
    )
    valid = (
        featured["feature_complete"]
        & featured["label"].notna()
        & featured["target_date"].le(outer_date)
    )
    candidate_rows = len(featured)
    featured = featured.loc[valid].copy()
    featured["response"] = featured["label"] - featured["level_t"]
    featured["pseudo_origin"] = featured["pseudo_origin_date"].map(period_label)
    featured.attrs["candidate_rows"] = candidate_rows
    featured.attrs["excluded_rows"] = candidate_rows - len(featured)
    columns = [
        "state_code",
        "pseudo_origin",
        "pseudo_origin_date",
        "target_date",
        "horizon",
        *RAW_DELTA_NUMERIC_FEATURES,
        "target_quarter",
        "label",
        "response",
    ]
    return featured[columns].sort_values(
        ["pseudo_origin_date", "state_code"]
    ).reset_index(drop=True)


def build_raw_delta_prediction_features(
    panel: pd.DataFrame,
    forecast_cells: pd.DataFrame,
    *,
    modeling_start: str,
) -> pd.DataFrame:
    """Attach the frozen raw-level and raw-change feature set."""
    cells = forecast_cells.copy()
    cells["origin_date"] = pd.to_datetime(cells["origin_date"])
    featured = _add_raw_delta_features(
        _feature_rows(
            panel,
            cells,
            date_column="origin_date",
            modeling_start=modeling_start,
        )
    )
    incomplete = featured.loc[~featured["feature_complete"]]
    if not incomplete.empty:
        keys = ", ".join(
            f"{row.state_code}/{period_label(row.origin_date)}/h{row.horizon}"
            for row in incomplete.head(5).itertuples()
        )
        raise CandidateFeatureError(
            "Eligible candidate rows lack the required four-quarter features: "
            + keys
        )
    return featured.drop(columns=["feature_complete"]).reset_index(drop=True)
