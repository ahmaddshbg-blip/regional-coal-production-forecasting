"""Holdout-safe exploratory analysis for the state-quarter forecasting panel."""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd


REQUIRED_PANEL_COLUMNS = {
    "state_code",
    "cal_year",
    "cal_quarter",
    "period",
    "quarter_start_date",
    "coal_production_short_tons",
}


class LeakageGuardError(ValueError):
    """Raised when target-value analysis crosses the approved development window."""


def period_start(period: str) -> pd.Timestamp:
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(period))
    if not match:
        raise ValueError(f"Invalid quarter label: {period}")
    year, quarter = (int(value) for value in match.groups())
    return pd.Timestamp(year=year, month=((quarter - 1) * 3) + 1, day=1)


def period_label(value: pd.Timestamp) -> str:
    timestamp = pd.Timestamp(value)
    quarter = ((timestamp.month - 1) // 3) + 1
    return f"{timestamp.year}Q{quarter}"


def add_quarters(period: str, quarters: int) -> str:
    shifted = period_start(period) + pd.offsets.QuarterBegin(startingMonth=1, n=quarters)
    return period_label(shifted)


def quarter_starts(start_period: str, end_period: str) -> pd.DatetimeIndex:
    start = period_start(start_period)
    end = period_start(end_period)
    if end < start:
        raise ValueError("End period precedes start period")
    return pd.period_range(start=start, end=end, freq="Q").to_timestamp(how="start")


def prepare_state_panel(panel: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_PANEL_COLUMNS.difference(panel.columns)
    if missing:
        raise ValueError(f"State panel is missing columns: {', '.join(sorted(missing))}")

    prepared = panel.copy()
    prepared["quarter_start_date"] = pd.to_datetime(prepared["quarter_start_date"])
    if prepared.duplicated(["state_code", "quarter_start_date"]).any():
        raise ValueError("State panel contains duplicate state-quarter keys")
    invalid_dates = (
        prepared["quarter_start_date"].dt.day.ne(1)
        | ~prepared["quarter_start_date"].dt.month.isin([1, 4, 7, 10])
    )
    if invalid_dates.any():
        raise ValueError("State panel contains invalid quarter-start dates")
    if (prepared["coal_production_short_tons"].dropna() < 0).any():
        raise ValueError("State panel contains negative production")

    expected_periods = prepared["quarter_start_date"].map(period_label)
    if not expected_periods.equals(prepared["period"].astype(str)):
        raise ValueError("Period labels disagree with quarter_start_date")
    return prepared.sort_values(["state_code", "quarter_start_date"]).reset_index(drop=True)


def development_values(
    panel: pd.DataFrame,
    *,
    start_period: str,
    end_period: str,
) -> pd.DataFrame:
    prepared = prepare_state_panel(panel)
    start = period_start(start_period)
    end = period_start(end_period)
    development = prepared.loc[
        prepared["quarter_start_date"].between(start, end)
    ].copy()
    assert_value_window(development, end_period=end_period)
    return development


def assert_value_window(frame: pd.DataFrame, *, end_period: str) -> None:
    cutoff = period_start(end_period)
    dates = pd.to_datetime(frame["quarter_start_date"])
    if dates.gt(cutoff).any():
        latest = period_label(dates.max())
        raise LeakageGuardError(
            f"Target-value EDA crossed {end_period}; latest row is {latest}"
        )


def build_coverage_grid(
    panel: pd.DataFrame,
    *,
    start_period: str,
    end_period: str,
    value_end_period: str,
) -> pd.DataFrame:
    """Complete the structural grid while masking post-development magnitudes."""
    prepared = prepare_state_panel(panel)
    dates = quarter_starts(start_period, end_period)
    cutoff = period_start(value_end_period)
    states = sorted(prepared["state_code"].dropna().unique())
    grid = pd.MultiIndex.from_product(
        [states, dates], names=["state_code", "quarter_start_date"]
    ).to_frame(index=False)
    source = prepared[
        ["state_code", "quarter_start_date", "coal_production_short_tons"]
    ]
    grid = grid.merge(
        source,
        on=["state_code", "quarter_start_date"],
        how="left",
        indicator=True,
        validate="one_to_one",
    )
    grid["row_present"] = grid["_merge"].eq("both")
    grid = grid.drop(columns="_merge")
    grid["target_observed"] = (
        grid["row_present"] & grid["coal_production_short_tons"].notna()
    )

    present = grid.loc[grid["row_present"]]
    bounds = present.groupby("state_code")["quarter_start_date"].agg(
        first_present="min", last_present="max"
    )
    grid = grid.join(bounds, on="state_code")

    status = pd.Series("internal_absence", index=grid.index, dtype="string")
    absent = ~grid["row_present"]
    status.loc[absent & grid["quarter_start_date"].lt(grid["first_present"])] = (
        "leading_absence"
    )
    status.loc[absent & grid["quarter_start_date"].gt(grid["last_present"])] = (
        "trailing_absence"
    )
    post_cutoff = grid["row_present"] & grid["quarter_start_date"].gt(cutoff)
    status.loc[post_cutoff] = "observed_masked"
    in_window = grid["row_present"] & grid["quarter_start_date"].le(cutoff)
    status.loc[in_window & grid["coal_production_short_tons"].isna()] = "observed_null"
    status.loc[in_window & grid["coal_production_short_tons"].eq(0)] = "observed_zero"
    status.loc[in_window & grid["coal_production_short_tons"].gt(0)] = (
        "observed_positive"
    )
    grid["coverage_status"] = status
    grid["eda_target"] = grid["coal_production_short_tons"].where(
        grid["quarter_start_date"].le(cutoff)
    )
    grid["period"] = grid["quarter_start_date"].map(period_label)
    return grid.drop(columns="coal_production_short_tons").sort_values(
        ["state_code", "quarter_start_date"]
    ).reset_index(drop=True)


def state_coverage_summary(coverage_grid: pd.DataFrame) -> pd.DataFrame:
    counts = (
        coverage_grid.groupby(["state_code", "coverage_status"], observed=True)
        .size()
        .unstack(fill_value=0)
    )
    for status in (
        "leading_absence",
        "internal_absence",
        "trailing_absence",
        "observed_null",
        "observed_zero",
        "observed_positive",
        "observed_masked",
    ):
        if status not in counts:
            counts[status] = 0
    bounds = coverage_grid.loc[coverage_grid["row_present"]].groupby("state_code").agg(
        first_present=("period", "min"),
        last_present=("period", "max"),
        observed_rows=("row_present", "size"),
    )
    return bounds.join(counts).reset_index().sort_values("state_code")


def state_target_summary(
    development: pd.DataFrame,
    *,
    value_end_period: str,
) -> pd.DataFrame:
    assert_value_window(development, end_period=value_end_period)
    summary = development.groupby("state_code").agg(
        first_period=("period", "min"),
        last_period=("period", "max"),
        observed_periods=("coal_production_short_tons", "count"),
        zero_periods=("coal_production_short_tons", lambda values: values.eq(0).sum()),
        positive_periods=("coal_production_short_tons", lambda values: values.gt(0).sum()),
        total_production=("coal_production_short_tons", "sum"),
        mean_production=("coal_production_short_tons", "mean"),
        median_production=("coal_production_short_tons", "median"),
        standard_deviation=("coal_production_short_tons", "std"),
        minimum_production=("coal_production_short_tons", "min"),
        maximum_production=("coal_production_short_tons", "max"),
    )
    summary["zero_share"] = summary["zero_periods"].div(summary["observed_periods"])
    return summary.reset_index().sort_values("total_production", ascending=False)


def temporal_change_diagnostics(
    development: pd.DataFrame,
    *,
    value_end_period: str,
    robust_threshold: float = 3.5,
) -> pd.DataFrame:
    assert_value_window(development, end_period=value_end_period)
    base = development[
        ["state_code", "quarter_start_date", "period", "coal_production_short_tons"]
    ].copy()
    base["quarter_start_date"] = pd.to_datetime(base["quarter_start_date"])

    lag1 = base[["state_code", "quarter_start_date", "coal_production_short_tons"]].copy()
    lag1["quarter_start_date"] += pd.DateOffset(months=3)
    lag1 = lag1.rename(columns={"coal_production_short_tons": "lag1_production"})
    lag4 = base[["state_code", "quarter_start_date", "coal_production_short_tons"]].copy()
    lag4["quarter_start_date"] += pd.DateOffset(months=12)
    lag4 = lag4.rename(columns={"coal_production_short_tons": "lag4_production"})

    diagnostics = base.merge(
        lag1,
        on=["state_code", "quarter_start_date"],
        how="left",
        validate="one_to_one",
    ).merge(
        lag4,
        on=["state_code", "quarter_start_date"],
        how="left",
        validate="one_to_one",
    )
    target = diagnostics["coal_production_short_tons"]
    diagnostics["qoq_change"] = target - diagnostics["lag1_production"]
    diagnostics["yoy_change"] = target - diagnostics["lag4_production"]
    diagnostics["log_yoy_change"] = np.log1p(target) - np.log1p(
        diagnostics["lag4_production"]
    )

    def robust_z(values: pd.Series) -> pd.Series:
        median = values.median()
        mad = (values - median).abs().median()
        if pd.isna(mad) or mad == 0:
            return pd.Series(np.nan, index=values.index)
        return 0.67448975 * (values - median) / mad

    diagnostics["robust_log_yoy_z"] = diagnostics.groupby(
        "state_code", group_keys=False
    )["log_yoy_change"].transform(robust_z)
    diagnostics["outlier_flag"] = diagnostics["robust_log_yoy_z"].abs().ge(
        robust_threshold
    )
    diagnostics["absolute_yoy_change"] = diagnostics["yoy_change"].abs()
    return diagnostics.sort_values(["state_code", "quarter_start_date"]).reset_index(
        drop=True
    )


def seasonal_quarter_share(
    development: pd.DataFrame,
    *,
    value_end_period: str,
) -> pd.DataFrame:
    assert_value_window(development, end_period=value_end_period)
    frame = development.copy()
    complete_years = frame.groupby(["state_code", "cal_year"]).agg(
        observed_quarters=("coal_production_short_tons", "count"),
        annual_production=("coal_production_short_tons", "sum"),
    )
    complete_years = complete_years.loc[
        complete_years["observed_quarters"].eq(4)
        & complete_years["annual_production"].gt(0)
    ].reset_index()
    frame = frame.merge(
        complete_years[["state_code", "cal_year", "annual_production"]],
        on=["state_code", "cal_year"],
        how="inner",
        validate="many_to_one",
    )
    frame["annual_share"] = frame["coal_production_short_tons"].div(
        frame["annual_production"]
    )
    return frame.groupby("cal_quarter")["annual_share"].agg(
        median="median",
        q25=lambda values: values.quantile(0.25),
        q75=lambda values: values.quantile(0.75),
        state_years="count",
    ).reset_index()


def quarterly_concentration(
    development: pd.DataFrame,
    *,
    value_end_period: str,
) -> pd.DataFrame:
    assert_value_window(development, end_period=value_end_period)
    frame = development.dropna(subset=["coal_production_short_tons"]).copy()
    totals = frame.groupby("quarter_start_date")["coal_production_short_tons"].transform(
        "sum"
    )
    frame["production_share"] = frame["coal_production_short_tons"].div(totals)

    def summarize(group: pd.DataFrame) -> pd.Series:
        shares = group["production_share"].sort_values(ascending=False)
        return pd.Series(
            {
                "period": group["period"].iloc[0],
                "total_production": group["coal_production_short_tons"].sum(),
                "observed_states": group["state_code"].nunique(),
                "top5_share": shares.head(5).sum(),
                "hhi": shares.pow(2).sum(),
            }
        )

    return (
        frame.groupby("quarter_start_date", sort=True)
        .apply(summarize, include_groups=False)
        .reset_index()
    )


def origin_eligibility(
    panel: pd.DataFrame,
    origins: Iterable[str],
    *,
    modeling_start: str,
    minimum_history: int,
    recent_quarters: int,
) -> pd.DataFrame:
    prepared = prepare_state_panel(panel)
    modeling_start_date = period_start(modeling_start)
    states = sorted(prepared["state_code"].dropna().unique())
    observed_dates = {
        state: set(group.loc[group["coal_production_short_tons"].notna(), "quarter_start_date"])
        for state, group in prepared.groupby("state_code")
    }
    records: list[dict[str, object]] = []
    for origin in origins:
        origin_date = period_start(origin)
        if origin_date < modeling_start_date:
            raise ValueError(f"Origin {origin} precedes modeling start {modeling_start}")
        recent = set(
            pd.period_range(end=origin_date, periods=recent_quarters, freq="Q").to_timestamp(
                how="start"
            )
        )
        for state in states:
            dates = observed_dates[state]
            history_count = sum(
                modeling_start_date <= date <= origin_date for date in dates
            )
            recent_count = len(recent.intersection(dates))
            meets_history = history_count >= minimum_history
            meets_recent = recent_count == recent_quarters
            records.append(
                {
                    "origin": origin,
                    "origin_date": origin_date,
                    "state_code": state,
                    "history_observations": history_count,
                    "recent_observations": recent_count,
                    "meets_history": meets_history,
                    "meets_recent": meets_recent,
                    "eligible": meets_history and meets_recent,
                }
            )
    return pd.DataFrame.from_records(records).sort_values(
        ["origin_date", "state_code"]
    ).reset_index(drop=True)


def eligibility_transitions(eligibility: pd.DataFrame) -> pd.DataFrame:
    ordered = eligibility.sort_values(["state_code", "origin_date"]).copy()
    ordered["previous_eligible"] = ordered.groupby("state_code")["eligible"].shift()
    changed = ordered["previous_eligible"].notna() & ordered["eligible"].ne(
        ordered["previous_eligible"]
    )
    transitions = ordered.loc[changed].copy()
    transitions["transition"] = np.where(transitions["eligible"], "entered", "exited")
    return transitions[
        [
            "origin",
            "origin_date",
            "state_code",
            "transition",
            "history_observations",
            "recent_observations",
        ]
    ].reset_index(drop=True)
