from __future__ import annotations

import unittest

import pandas as pd

from coal_forecasting.candidate_features import (
    CandidateFeatureError,
    build_prediction_features,
    build_training_examples,
)


def panel_frame(
    *,
    states: tuple[str, ...] = ("AA",),
    start: str = "2003Q1",
    periods: int = 16,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    quarters = pd.period_range(start=start, periods=periods, freq="Q")
    for state_index, state in enumerate(states, start=1):
        for index, period in enumerate(quarters):
            value = float(state_index * 100 + index)
            records.append(
                {
                    "state_code": state,
                    "cal_year": period.year,
                    "cal_quarter": period.quarter,
                    "period": f"{period.year}Q{period.quarter}",
                    "quarter_start_date": period.start_time,
                    "coal_production_short_tons": value,
                }
            )
    return pd.DataFrame.from_records(records)


class CandidateFeatureTests(unittest.TestCase):
    def test_training_labels_never_cross_outer_origin(self) -> None:
        examples = build_training_examples(
            panel_frame(),
            outer_origin="2006Q4",
            horizon=4,
            modeling_start="2003Q1",
        )

        self.assertFalse(examples.empty)
        self.assertTrue(
            examples["target_date"].le(pd.Timestamp("2006-10-01")).all()
        )
        self.assertTrue(
            examples["pseudo_origin_date"].ge(pd.Timestamp("2003-10-01")).all()
        )
        self.assertTrue(examples["horizon"].eq(4).all())

    def test_features_follow_calendar_lags_and_preserve_zero(self) -> None:
        panel = panel_frame(periods=8)
        panel.loc[panel["period"].eq("2003Q3"), "coal_production_short_tons"] = 0.0
        cells = pd.DataFrame(
            {
                "state_code": ["AA"],
                "origin_date": [pd.Timestamp("2003-10-01")],
                "horizon": [1],
            }
        )

        features = build_prediction_features(
            panel,
            cells,
            modeling_start="2003Q1",
        ).iloc[0]

        self.assertEqual(features["recent_zero_count"], 1)
        self.assertEqual(features["target_quarter"], 1)
        self.assertEqual(features["origin_index"], 3)
        self.assertAlmostEqual(features["log_level_t"], 4.644390899, places=6)
        self.assertLess(features["log_change_2"], 0.0)

    def test_missing_required_calendar_lag_is_a_hard_failure(self) -> None:
        panel = panel_frame(periods=8)
        panel = panel.loc[~panel["period"].eq("2003Q2")].copy()
        cells = pd.DataFrame(
            {
                "state_code": ["AA"],
                "origin_date": [pd.Timestamp("2003-10-01")],
                "horizon": [1],
            }
        )

        with self.assertRaisesRegex(CandidateFeatureError, "four-quarter"):
            build_prediction_features(panel, cells, modeling_start="2003Q1")

    def test_training_excludes_incomplete_rows_without_imputation(self) -> None:
        panel = panel_frame(periods=12)
        panel.loc[panel["period"].eq("2004Q2"), "coal_production_short_tons"] = pd.NA
        examples = build_training_examples(
            panel,
            outer_origin="2005Q4",
            horizon=1,
            modeling_start="2003Q1",
        )

        self.assertFalse(examples.isna().any().any())
        self.assertNotIn(pd.Timestamp("2004-04-01"), set(examples["pseudo_origin_date"]))


if __name__ == "__main__":
    unittest.main()
