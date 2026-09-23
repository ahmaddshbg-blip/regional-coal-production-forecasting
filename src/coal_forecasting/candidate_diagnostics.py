"""Selection-only diagnostics for the frozen candidate procedure."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from coal_forecasting.eda import period_start


class DiagnosticBoundaryError(ValueError):
    """Raised when selection diagnostics receive confirmation rows."""


def validate_selection_frame(
    forecasts: pd.DataFrame,
    *,
    selection_end: str,
) -> pd.DataFrame:
    required = {"origin_date", "state_code", "horizon", "forecast", "actual", "scored"}
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Diagnostic frame is missing: {', '.join(sorted(missing))}")
    frame = forecasts.copy()
    frame["origin_date"] = pd.to_datetime(frame["origin_date"])
    if frame["origin_date"].gt(period_start(selection_end)).any():
        raise DiagnosticBoundaryError(
            "Selection diagnostics received confirmation-period candidate results"
        )
    frame["error"] = frame["forecast"] - frame["actual"]
    frame["absolute_error"] = frame["error"].abs()
    return frame


def residual_autocorrelation(
    forecasts: pd.DataFrame,
    *,
    lags: Iterable[int] = (1, 4),
    minimum_pairs: int = 12,
) -> pd.DataFrame:
    """Compute calendar-aligned residual correlations within state and horizon."""
    required = {"origin_date", "state_code", "horizon", "forecast", "actual", "scored"}
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Forecasts are missing: {', '.join(sorted(missing))}")
    frame = forecasts.loc[forecasts["scored"]].copy()
    frame["origin_date"] = pd.to_datetime(frame["origin_date"])
    frame["error"] = frame["forecast"] - frame["actual"]
    records: list[dict[str, object]] = []
    for (state, horizon), group in frame.groupby(["state_code", "horizon"], sort=True):
        current = group[["origin_date", "error"]].dropna().copy()
        for lag in lags:
            previous = current.rename(columns={"error": "lagged_error"}).copy()
            previous["origin_date"] += pd.DateOffset(months=3 * int(lag))
            pairs = current.merge(previous, on="origin_date", how="inner")
            count = len(pairs)
            correlation = (
                pairs["error"].corr(pairs["lagged_error"])
                if count >= minimum_pairs
                and pairs["error"].nunique(dropna=True) > 1
                and pairs["lagged_error"].nunique(dropna=True) > 1
                else np.nan
            )
            records.append(
                {
                    "state_code": state,
                    "horizon": int(horizon),
                    "lag": int(lag),
                    "pairs": count,
                    "correlation": correlation,
                }
            )
    return pd.DataFrame.from_records(records).sort_values(
        ["horizon", "state_code", "lag"]
    ).reset_index(drop=True)


def binned_residual_summary(
    forecasts: pd.DataFrame,
    *,
    column: str,
    bins: int = 10,
) -> pd.DataFrame:
    """Summarize signed and absolute errors across robust rank-based bins."""
    if bins < 2:
        raise ValueError("Residual diagnostics require at least two bins")
    if column not in forecasts:
        raise ValueError(f"Diagnostic column is missing: {column}")
    frame = forecasts.loc[forecasts["scored"] & forecasts[column].notna()].copy()
    frame["error"] = frame["forecast"] - frame["actual"]
    frame["absolute_error"] = frame["error"].abs()
    if frame.empty:
        return pd.DataFrame(
            columns=["horizon", "diagnostic", "bin", "rows", "mean_error", "mean_absolute_error"]
        )
    rank = frame.groupby("horizon")[column].rank(method="first", pct=True)
    frame["bin"] = np.minimum(bins, np.ceil(rank * bins)).astype(int)
    summary = frame.groupby(["horizon", "bin"], as_index=False).agg(
        rows=("error", "size"),
        mean_error=("error", "mean"),
        mean_absolute_error=("absolute_error", "mean"),
        diagnostic_min=(column, "min"),
        diagnostic_max=(column, "max"),
    )
    summary.insert(1, "diagnostic", column)
    return summary
