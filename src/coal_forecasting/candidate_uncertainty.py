"""Development-only uncertainty helpers for the frozen candidate."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


def finite_sample_quantile(values: Iterable[float], coverage: float) -> float:
    """Return the finite-sample conformal order statistic."""
    if not 0 < coverage < 1:
        raise ValueError("Coverage must lie strictly between zero and one")
    array = np.asarray(list(values), dtype=float)
    array = np.sort(array[np.isfinite(array)])
    if not len(array):
        raise ValueError("Conformal calibration values are empty")
    rank = min(len(array), math.ceil((len(array) + 1) * coverage))
    return float(array[rank - 1])


def add_prequential_intervals(
    forecasts: pd.DataFrame,
    *,
    warmup_origins: int = 8,
    coverages: tuple[float, ...] = (0.80, 0.95),
) -> pd.DataFrame:
    """Build intervals from strictly earlier development residuals."""
    required = {
        "origin_date",
        "state_code",
        "horizon",
        "forecast",
        "actual",
        "scored",
        "mase_scale",
    }
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Forecasts are missing: {', '.join(sorted(missing))}")
    if warmup_origins < 1:
        raise ValueError("Interval warm-up must contain at least one origin")

    frame = forecasts.copy().reset_index(drop=True)
    frame["origin_date"] = pd.to_datetime(frame["origin_date"])
    origins = sorted(frame["origin_date"].unique())
    warmup = set(origins[:warmup_origins])
    frame["interval_scale_source"] = ""
    for coverage in coverages:
        suffix = str(int(round(coverage * 100)))
        frame[f"lower_{suffix}"] = np.nan
        frame[f"upper_{suffix}"] = np.nan
        frame[f"interval_available_{suffix}"] = False

    scored = frame.loc[frame["scored"] & frame["actual"].notna()].copy()
    scored["absolute_error"] = (scored["forecast"] - scored["actual"]).abs()
    valid_scale = scored["mase_scale"].gt(0) & scored["mase_scale"].notna()
    scored["normalized_error"] = scored["absolute_error"].div(
        scored["mase_scale"].where(valid_scale)
    )

    for row_index, row in frame.iterrows():
        if row["origin_date"] in warmup:
            continue
        calibration = scored.loc[
            scored["horizon"].eq(row["horizon"])
            & scored["origin_date"].lt(row["origin_date"])
        ]
        if calibration.empty:
            continue
        scaled = pd.notna(row["mase_scale"]) and float(row["mase_scale"]) > 0
        source = "state_mase_scale" if scaled else "pooled_unscaled"
        for coverage in coverages:
            suffix = str(int(round(coverage * 100)))
            if scaled:
                values = calibration["normalized_error"].dropna()
                if values.empty:
                    continue
                margin = finite_sample_quantile(values, coverage) * float(
                    row["mase_scale"]
                )
            else:
                margin = finite_sample_quantile(
                    calibration["absolute_error"], coverage
                )
            frame.at[row_index, f"lower_{suffix}"] = max(
                0.0, float(row["forecast"]) - margin
            )
            frame.at[row_index, f"upper_{suffix}"] = float(row["forecast"]) + margin
            frame.at[row_index, f"interval_available_{suffix}"] = True
            frame.at[row_index, "interval_scale_source"] = source
    return frame


def moving_block_origin_samples(
    origins: Iterable[pd.Timestamp],
    *,
    block_length: int,
    replications: int,
    seed: int,
) -> np.ndarray:
    """Sample non-circular contiguous origin blocks with replacement."""
    ordered = np.sort(
        pd.DatetimeIndex(pd.to_datetime(list(origins)))
        .unique()
        .to_numpy(dtype="datetime64[ns]")
    )
    if block_length < 1 or block_length > len(ordered):
        raise ValueError("Block length must be between one and the origin count")
    if replications < 1:
        raise ValueError("Bootstrap replications must be positive")
    rng = np.random.default_rng(seed)
    starts = np.arange(0, len(ordered) - block_length + 1)
    samples = np.empty((replications, len(ordered)), dtype=ordered.dtype)
    for replication in range(replications):
        pieces: list[np.ndarray] = []
        size = 0
        while size < len(ordered):
            start = int(rng.choice(starts))
            block = ordered[start : start + block_length]
            pieces.append(block)
            size += len(block)
        samples[replication] = np.concatenate(pieces)[: len(ordered)]
    return samples


def summarize_interval_metrics(
    forecasts: pd.DataFrame,
    *,
    coverages: tuple[float, ...] = (0.80, 0.95),
) -> pd.DataFrame:
    """Summarize empirical interval coverage, width, and Winkler score."""
    required = {"horizon", "actual"}
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Interval forecasts are missing: {', '.join(sorted(missing))}")
    records: list[dict[str, object]] = []
    for coverage in coverages:
        suffix = str(int(round(coverage * 100)))
        lower = f"lower_{suffix}"
        upper = f"upper_{suffix}"
        available = f"interval_available_{suffix}"
        interval_columns = {lower, upper, available}
        missing_interval = interval_columns.difference(forecasts.columns)
        if missing_interval:
            raise ValueError(
                "Interval forecasts are missing: "
                + ", ".join(sorted(missing_interval))
            )
        for horizon, group in forecasts.groupby("horizon", sort=True):
            evaluated = group.loc[
                group[available]
                & group["actual"].notna()
                & group[lower].notna()
                & group[upper].notna()
            ].copy()
            if evaluated.empty:
                records.append(
                    {
                        "horizon": int(horizon),
                        "nominal_coverage": coverage,
                        "interval_cells": 0,
                        "empirical_coverage": np.nan,
                        "mean_width": np.nan,
                        "median_width": np.nan,
                        "mean_relative_width": np.nan,
                        "mean_winkler_score": np.nan,
                    }
                )
                continue
            width = evaluated[upper] - evaluated[lower]
            inside = evaluated["actual"].between(
                evaluated[lower], evaluated[upper], inclusive="both"
            )
            alpha = 1.0 - coverage
            below = evaluated["actual"].lt(evaluated[lower])
            above = evaluated["actual"].gt(evaluated[upper])
            winkler = width.copy()
            winkler.loc[below] += (2.0 / alpha) * (
                evaluated.loc[below, lower] - evaluated.loc[below, "actual"]
            )
            winkler.loc[above] += (2.0 / alpha) * (
                evaluated.loc[above, "actual"] - evaluated.loc[above, upper]
            )
            relative = width.div(evaluated["actual"].where(evaluated["actual"].gt(0)))
            records.append(
                {
                    "horizon": int(horizon),
                    "nominal_coverage": coverage,
                    "interval_cells": len(evaluated),
                    "empirical_coverage": inside.mean(),
                    "mean_width": width.mean(),
                    "median_width": width.median(),
                    "mean_relative_width": relative.mean(),
                    "mean_winkler_score": winkler.mean(),
                }
            )
    return pd.DataFrame.from_records(records).sort_values(
        ["nominal_coverage", "horizon"]
    ).reset_index(drop=True)


def _wape_skill(group: pd.DataFrame, weights: pd.Series | None = None) -> float:
    row_weights = (
        weights.reindex(group.index).astype(float)
        if weights is not None
        else pd.Series(1.0, index=group.index)
    )
    actual_volume = (group["actual"] * row_weights).sum()
    if actual_volume <= 0:
        return np.nan
    candidate_wape = (
        (group["candidate_forecast"] - group["actual"]).abs() * row_weights
    ).sum() / actual_volume
    comparator_wape = (
        (group["comparator_forecast"] - group["actual"]).abs() * row_weights
    ).sum() / actual_volume
    if comparator_wape <= 0:
        return np.nan
    return float(1.0 - candidate_wape / comparator_wape)


def paired_moving_block_bootstrap_skill(
    paired_forecasts: pd.DataFrame,
    *,
    block_length: int,
    replications: int,
    seed: int,
) -> pd.DataFrame:
    """Bootstrap paired WAPE skill by resampling complete forecast origins."""
    required = {
        "origin_date",
        "state_code",
        "horizon",
        "actual",
        "candidate_forecast",
        "comparator_forecast",
    }
    missing = required.difference(paired_forecasts.columns)
    if missing:
        raise ValueError(f"Paired forecasts are missing: {', '.join(sorted(missing))}")
    frame = paired_forecasts.dropna(
        subset=["actual", "candidate_forecast", "comparator_forecast"]
    ).copy()
    frame["origin_date"] = pd.to_datetime(frame["origin_date"])
    horizons = sorted(int(value) for value in frame["horizon"].unique())
    origins = sorted(frame["origin_date"].unique())
    samples = moving_block_origin_samples(
        origins,
        block_length=block_length,
        replications=replications,
        seed=seed,
    )
    point = {
        horizon: _wape_skill(frame.loc[frame["horizon"].eq(horizon)])
        for horizon in horizons
    }
    bootstrap = np.full((replications, len(horizons)), np.nan, dtype=float)
    for replication, sample in enumerate(samples):
        counts = pd.Series(pd.to_datetime(sample)).value_counts()
        weights = frame["origin_date"].map(counts).fillna(0).astype(float)
        for horizon_index, horizon in enumerate(horizons):
            group = frame.loc[frame["horizon"].eq(horizon)]
            bootstrap[replication, horizon_index] = _wape_skill(group, weights)

    records: list[dict[str, object]] = []
    for horizon_index, horizon in enumerate(horizons):
        values = bootstrap[:, horizon_index]
        records.append(
            {
                "summary": f"horizon_{horizon}",
                "horizon": horizon,
                "point_wape_skill": point[horizon],
                "lower_95": np.nanpercentile(values, 2.5),
                "upper_95": np.nanpercentile(values, 97.5),
                "replications": replications,
            }
        )
    mean_values = np.nanmean(bootstrap, axis=1)
    records.append(
        {
            "summary": "equal_weight_mean",
            "horizon": pd.NA,
            "point_wape_skill": np.nanmean(list(point.values())),
            "lower_95": np.nanpercentile(mean_values, 2.5),
            "upper_95": np.nanpercentile(mean_values, 97.5),
            "replications": replications,
        }
    )
    return pd.DataFrame.from_records(records)
