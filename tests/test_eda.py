from __future__ import annotations

import unittest

import pandas as pd

from coal_forecasting.eda import (
    LeakageGuardError,
    add_quarters,
    build_coverage_grid,
    development_values,
    origin_eligibility,
    state_target_summary,
    temporal_change_diagnostics,
)


def panel_frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    records = []
    for state, period, production in rows:
        year = int(period[:4])
        quarter = int(period[-1])
        records.append(
            {
                "state_code": state,
                "cal_year": year,
                "cal_quarter": quarter,
                "period": period,
                "quarter_start_date": pd.Timestamp(
                    year=year, month=((quarter - 1) * 3) + 1, day=1
                ),
                "coal_production_short_tons": production,
            }
        )
    return pd.DataFrame.from_records(records)


class EdaTests(unittest.TestCase):
    def test_add_quarters_preserves_quarter_origin_semantics(self) -> None:
        self.assertEqual(add_quarters("2021Q1", 4), "2022Q1")

    def test_coverage_grid_classifies_absence_and_masks_later_values(self) -> None:
        panel = panel_frame(
            [
                ("AA", "2020Q2", 10.0),
                ("AA", "2020Q3", 0.0),
                ("AA", "2021Q1", 5.0),
                ("AA", "2021Q2", 7.0),
            ]
        )
        grid = build_coverage_grid(
            panel,
            start_period="2020Q1",
            end_period="2021Q2",
            value_end_period="2020Q4",
        ).set_index("period")

        self.assertEqual(grid.loc["2020Q1", "coverage_status"], "leading_absence")
        self.assertEqual(grid.loc["2020Q2", "coverage_status"], "observed_positive")
        self.assertEqual(grid.loc["2020Q3", "coverage_status"], "observed_zero")
        self.assertEqual(grid.loc["2020Q4", "coverage_status"], "internal_absence")
        self.assertEqual(grid.loc["2021Q1", "coverage_status"], "observed_masked")
        self.assertTrue(pd.isna(grid.loc["2021Q1", "eda_target"]))

    def test_target_summary_rejects_post_cutoff_rows(self) -> None:
        panel = panel_frame(
            [("AA", "2020Q4", 10.0), ("AA", "2021Q1", 11.0)]
        )
        with self.assertRaises(LeakageGuardError):
            state_target_summary(panel, value_end_period="2020Q4")

    def test_temporal_lags_follow_calendar_quarters_not_row_positions(self) -> None:
        panel = panel_frame(
            [
                ("AA", "2020Q1", 10.0),
                ("AA", "2020Q3", 15.0),
                ("AA", "2021Q1", 20.0),
            ]
        )
        diagnostics = temporal_change_diagnostics(
            panel,
            value_end_period="2021Q1",
        ).set_index("period")

        self.assertTrue(pd.isna(diagnostics.loc["2020Q3", "lag1_production"]))
        self.assertEqual(diagnostics.loc["2021Q1", "lag4_production"], 10.0)
        self.assertEqual(diagnostics.loc["2021Q1", "yoy_change"], 10.0)

    def test_dynamic_eligibility_counts_zero_as_observed(self) -> None:
        panel = panel_frame(
            [
                ("AA", "2020Q1", 1.0),
                ("AA", "2020Q2", 0.0),
                ("AA", "2020Q3", 2.0),
                ("AA", "2020Q4", 3.0),
                ("BB", "2020Q1", 1.0),
                ("BB", "2020Q3", 2.0),
                ("BB", "2020Q4", 3.0),
            ]
        )
        eligibility = origin_eligibility(
            panel,
            ["2020Q3", "2020Q4"],
            modeling_start="2020Q1",
            minimum_history=3,
            recent_quarters=2,
        )
        indexed = eligibility.set_index(["origin", "state_code"])

        self.assertTrue(indexed.loc[("2020Q3", "AA"), "eligible"])
        self.assertEqual(indexed.loc[("2020Q3", "AA"), "history_observations"], 3)
        self.assertFalse(indexed.loc[("2020Q3", "BB"), "eligible"])
        self.assertTrue(indexed.loc[("2020Q4", "BB"), "eligible"])

    def test_development_values_applies_both_window_bounds(self) -> None:
        panel = panel_frame(
            [
                ("AA", "2019Q4", 1.0),
                ("AA", "2020Q1", 2.0),
                ("AA", "2020Q2", 3.0),
                ("AA", "2020Q3", 4.0),
            ]
        )
        development = development_values(
            panel,
            start_period="2020Q1",
            end_period="2020Q2",
        )
        self.assertEqual(development["period"].tolist(), ["2020Q1", "2020Q2"])


if __name__ == "__main__":
    unittest.main()
