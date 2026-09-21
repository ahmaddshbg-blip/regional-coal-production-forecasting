from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from coal_forecasting.baselines import generate_baseline_forecasts
from coal_forecasting.evaluation import (
    EvaluationGuardError,
    build_development_forecast_cells,
    development_origin_labels,
)
from coal_forecasting.metrics import (
    assert_complete_prediction_coverage,
    summarize_overall_metrics,
    summarize_state_metrics,
)


def synthetic_panel(*, constant: bool = False) -> pd.DataFrame:
    periods = pd.period_range("2019Q1", "2021Q4", freq="Q")
    records = []
    for index, period in enumerate(periods, start=1):
        timestamp = period.start_time
        records.append(
            {
                "state_code": "AA",
                "cal_year": timestamp.year,
                "cal_quarter": period.quarter,
                "period": f"{timestamp.year}Q{period.quarter}",
                "quarter_start_date": timestamp,
                "coal_production_short_tons": 1.0 if constant else float(index),
            }
        )
    return pd.DataFrame.from_records(records)


def evaluation_config() -> dict[str, object]:
    return {
        "modeling_start": "2019Q1",
        "forecast_horizons": [1, 2, 3, 4],
        "validation_origins": {"start": "2020Q4", "end": "2020Q4", "count": 1},
        "embargo_origins": {"start": "2021Q1", "end": "2021Q4", "count": 4},
        "holdout_origins": {"start": "2022Q1", "end": "2022Q4", "count": 4},
        "latest_forecast_origin": "2023Q1",
        "eligibility": {
            "minimum_non_null_history": 4,
            "required_consecutive_recent_observations": 2,
        },
    }


class EvaluationTests(unittest.TestCase):
    def test_development_origin_count_and_overlap_guard(self) -> None:
        config = evaluation_config()
        self.assertEqual(development_origin_labels(config), ["2020Q4"])

        config["holdout_origins"] = {
            "start": "2021Q4",
            "end": "2022Q3",
            "count": 4,
        }
        with self.assertRaises(EvaluationGuardError):
            development_origin_labels(config)

    def test_baseline_formulas_and_calendar_alignment(self) -> None:
        panel = synthetic_panel()
        cells = build_development_forecast_cells(panel, evaluation_config())
        forecasts = generate_baseline_forecasts(cells, panel)
        indexed = forecasts.set_index(["model", "horizon"])

        self.assertEqual(indexed.loc[("persistence", 1), "forecast"], 8.0)
        self.assertEqual(indexed.loc[("persistence", 4), "forecast"], 8.0)
        self.assertEqual(indexed.loc[("seasonal_naive", 1), "forecast"], 5.0)
        self.assertEqual(indexed.loc[("seasonal_naive", 4), "forecast"], 8.0)
        self.assertEqual(indexed.loc[("persistence", 1), "actual"], 9.0)
        self.assertEqual(indexed.loc[("persistence", 4), "actual"], 12.0)
        self.assertEqual(indexed.loc[("persistence", 1), "mase_scale"], 4.0)
        self.assertTrue(forecasts["prediction_available"].all())

    def test_horizon_four_baselines_are_identical(self) -> None:
        panel = synthetic_panel()
        cells = build_development_forecast_cells(panel, evaluation_config())
        forecasts = generate_baseline_forecasts(cells, panel)
        horizon_four = forecasts.loc[forecasts["horizon"].eq(4)].set_index("model")
        self.assertEqual(
            horizon_four.loc["persistence", "forecast"],
            horizon_four.loc["seasonal_naive", "forecast"],
        )

    def test_metrics_follow_frozen_error_conventions(self) -> None:
        panel = synthetic_panel()
        cells = build_development_forecast_cells(panel, evaluation_config())
        forecasts = generate_baseline_forecasts(cells, panel)
        state_metrics = summarize_state_metrics(forecasts)
        metrics = summarize_overall_metrics(forecasts, state_metrics).set_index(
            ["model", "horizon"]
        )

        horizon_one = metrics.loc[("persistence", 1)]
        self.assertAlmostEqual(horizon_one["wape"], 1 / 9)
        self.assertAlmostEqual(horizon_one["mae"], 1.0)
        self.assertAlmostEqual(horizon_one["rmse"], 1.0)
        self.assertAlmostEqual(horizon_one["signed_mean_error"], -1.0)
        self.assertAlmostEqual(horizon_one["aggregate_signed_bias"], -1 / 9)
        self.assertAlmostEqual(horizon_one["median_state_mase"], 0.25)

    def test_zero_seasonal_scale_remains_undefined(self) -> None:
        panel = synthetic_panel(constant=True)
        cells = build_development_forecast_cells(panel, evaluation_config())
        forecasts = generate_baseline_forecasts(cells, panel)
        metrics = summarize_overall_metrics(forecasts).set_index(["model", "horizon"])

        self.assertTrue(np.isnan(metrics.loc[("persistence", 1), "median_state_mase"]))
        self.assertEqual(metrics.loc[("persistence", 1), "defined_mase_states"], 0)

    def test_missing_actual_is_unscored_not_replaced_by_zero(self) -> None:
        panel = synthetic_panel()
        panel = panel.loc[~panel["period"].eq("2021Q1")].copy()
        cells = build_development_forecast_cells(panel, evaluation_config())
        forecasts = generate_baseline_forecasts(cells, panel)
        horizon_one = forecasts.loc[forecasts["horizon"].eq(1)]

        self.assertTrue(horizon_one["actual"].isna().all())
        self.assertFalse(horizon_one["scored"].any())
        self.assertTrue(horizon_one["prediction_available"].all())
        self.assertTrue(horizon_one["unscored_reason"].eq("actual_missing").all())

    def test_incomplete_prediction_coverage_fails(self) -> None:
        panel = synthetic_panel()
        cells = build_development_forecast_cells(panel, evaluation_config())
        forecasts = generate_baseline_forecasts(cells, panel)
        row = forecasts.index[0]
        forecasts.loc[row, "forecast"] = np.nan
        forecasts.loc[row, "prediction_available"] = False
        forecasts.loc[row, "scored"] = False
        metrics = summarize_overall_metrics(forecasts)

        with self.assertRaisesRegex(ValueError, "Incomplete baseline prediction coverage"):
            assert_complete_prediction_coverage(metrics)

    def test_post_cutoff_values_are_rejected(self) -> None:
        panel = synthetic_panel()
        extra = panel.iloc[[-1]].copy()
        extra["cal_year"] = 2022
        extra["cal_quarter"] = 1
        extra["period"] = "2022Q1"
        extra["quarter_start_date"] = pd.Timestamp("2022-01-01")
        panel = pd.concat([panel, extra], ignore_index=True)

        with self.assertRaisesRegex(EvaluationGuardError, "after 2021Q4"):
            build_development_forecast_cells(panel, evaluation_config())


if __name__ == "__main__":
    unittest.main()
