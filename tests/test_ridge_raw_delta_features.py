from __future__ import annotations

import unittest

import pandas as pd

from coal_forecasting.candidate_features import (
    build_raw_delta_prediction_features,
    build_raw_delta_training_examples,
)


def panel_frame() -> pd.DataFrame:
    periods = pd.period_range("2019Q1", "2021Q4", freq="Q")
    values = [10.0, 20.0, 15.0, 0.0, 5.0, 15.0, 25.0, 30.0, 28.0, 35.0, 40.0, 42.0]
    return pd.DataFrame(
        {
            "state_code": "AA",
            "cal_year": periods.year,
            "cal_quarter": periods.quarter,
            "period": [f"{p.year}Q{p.quarter}" for p in periods],
            "quarter_start_date": periods.start_time,
            "coal_production_short_tons": values,
        }
    )


class RawDeltaFeatureTests(unittest.TestCase):
    def test_features_use_calendar_raw_changes(self) -> None:
        cells = pd.DataFrame(
            {
                "state_code": ["AA"],
                "origin_date": [pd.Timestamp("2020-04-01")],
                "horizon": [2],
            }
        )
        result = build_raw_delta_prediction_features(
            panel_frame(), cells, modeling_start="2019Q1"
        ).iloc[0]

        self.assertEqual(result["level_t"], 15.0)
        self.assertEqual(result["raw_change_1"], 10.0)
        self.assertEqual(result["raw_change_2"], 5.0)
        self.assertEqual(result["raw_change_3"], -15.0)
        self.assertEqual(result["recent_zero_count"], 1)

    def test_training_response_is_raw_delta_and_origin_safe(self) -> None:
        result = build_raw_delta_training_examples(
            panel_frame(),
            outer_origin="2021Q2",
            horizon=2,
            modeling_start="2019Q1",
        )

        self.assertTrue(result["target_date"].le(pd.Timestamp("2021-04-01")).all())
        self.assertTrue(
            result["response"].eq(result["label"] - result["level_t"]).all()
        )


if __name__ == "__main__":
    unittest.main()
