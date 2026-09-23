from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from coal_forecasting.candidate_uncertainty import (
    add_prequential_intervals,
    finite_sample_quantile,
    moving_block_origin_samples,
    paired_moving_block_bootstrap_skill,
    summarize_interval_metrics,
)


class CandidateUncertaintyTests(unittest.TestCase):
    def test_finite_sample_quantile_uses_conformal_rank(self) -> None:
        self.assertEqual(finite_sample_quantile([1.0, 2.0, 3.0, 4.0], 0.80), 4.0)

    def test_prequential_interval_uses_prior_origins_only(self) -> None:
        origins = pd.period_range("2010Q1", periods=4, freq="Q").to_timestamp()
        forecasts = pd.DataFrame(
            {
                "origin_date": origins,
                "state_code": ["AA"] * 4,
                "horizon": [1] * 4,
                "forecast": [10.0, 10.0, 10.0, 1000.0],
                "actual": [11.0, 12.0, 13.0, 1.0],
                "scored": [True] * 4,
                "mase_scale": [1.0] * 4,
            }
        )

        result = add_prequential_intervals(
            forecasts,
            warmup_origins=3,
            coverages=(0.80,),
        )

        self.assertFalse(result.loc[:2, "interval_available_80"].any())
        self.assertTrue(result.loc[3, "interval_available_80"])
        self.assertEqual(result.loc[3, "lower_80"], 997.0)
        self.assertEqual(result.loc[3, "upper_80"], 1003.0)

    def test_origin_block_samples_are_deterministic_and_origin_level(self) -> None:
        origins = pd.period_range("2010Q1", periods=8, freq="Q").to_timestamp()
        first = moving_block_origin_samples(
            origins,
            block_length=4,
            replications=3,
            seed=7,
        )
        second = moving_block_origin_samples(
            origins,
            block_length=4,
            replications=3,
            seed=7,
        )

        np.testing.assert_array_equal(first, second)
        self.assertEqual(first.shape, (3, 8))
        self.assertTrue(np.isin(first, origins.to_numpy()).all())

    def test_interval_metrics_include_coverage_width_and_winkler_score(self) -> None:
        forecasts = pd.DataFrame(
            {
                "horizon": [1, 1],
                "actual": [10.0, 20.0],
                "lower_80": [8.0, 12.0],
                "upper_80": [12.0, 18.0],
                "interval_available_80": [True, True],
            }
        )

        metrics = summarize_interval_metrics(forecasts, coverages=(0.80,)).iloc[0]

        self.assertEqual(metrics["interval_cells"], 2)
        self.assertEqual(metrics["empirical_coverage"], 0.5)
        self.assertEqual(metrics["mean_width"], 5.0)
        self.assertGreater(metrics["mean_winkler_score"], metrics["mean_width"])

    def test_paired_bootstrap_returns_zero_skill_for_identical_forecasts(self) -> None:
        origins = pd.period_range("2010Q1", periods=8, freq="Q").to_timestamp()
        records = []
        for horizon in (1, 2):
            for origin_index, origin in enumerate(origins, start=1):
                actual = float(100 + origin_index)
                records.append(
                    {
                        "origin_date": origin,
                        "state_code": "AA",
                        "horizon": horizon,
                        "actual": actual,
                        "candidate_forecast": actual + 1.0,
                        "comparator_forecast": actual + 1.0,
                    }
                )
        paired = pd.DataFrame.from_records(records)

        result = paired_moving_block_bootstrap_skill(
            paired,
            block_length=4,
            replications=50,
            seed=7,
        )

        self.assertTrue(result["point_wape_skill"].eq(0.0).all())
        self.assertTrue(result["lower_95"].eq(0.0).all())
        self.assertTrue(result["upper_95"].eq(0.0).all())


if __name__ == "__main__":
    unittest.main()
