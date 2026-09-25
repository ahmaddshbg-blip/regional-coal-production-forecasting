from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from coal_forecasting.candidate import fit_predict_raw_delta_ridge


class RawDeltaRidgeModelTests(unittest.TestCase):
    def test_model_is_deterministic_nonnegative_and_has_zero_intercept(self) -> None:
        training = pd.DataFrame(
            {
                "level_t": [0.0, 10.0, 20.0, 30.0, 40.0, 50.0],
                "raw_change_1": [0.0, 10.0, 10.0, 10.0, 10.0, 10.0],
                "raw_change_2": [0.0, 0.0, 10.0, 10.0, 10.0, 10.0],
                "raw_change_3": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0],
                "recent_zero_count": [4, 3, 2, 1, 0, 0],
                "origin_index": [3, 4, 5, 6, 7, 8],
                "state_code": ["AA"] * 6,
                "target_quarter": [1, 2, 3, 4, 1, 2],
                "response": [-10.0, -20.0, -30.0, -40.0, -50.0, -60.0],
            }
        )
        prediction = training.drop(columns="response").iloc[[0, 5]].copy()
        first = fit_predict_raw_delta_ridge(training, prediction, alpha=100.0)
        second = fit_predict_raw_delta_ridge(training, prediction, alpha=100.0)

        self.assertEqual(first.intercept, 0.0)
        self.assertTrue(first.predictions["forecast"].ge(0).all())
        np.testing.assert_allclose(
            first.predictions["forecast"], second.predictions["forecast"]
        )

    def test_large_alpha_shrinks_toward_persistence(self) -> None:
        training = pd.DataFrame(
            {
                "level_t": [10.0, 20.0, 30.0, 40.0],
                "raw_change_1": [1.0, 2.0, 3.0, 4.0],
                "raw_change_2": [0.0, 1.0, 2.0, 3.0],
                "raw_change_3": [-1.0, 0.0, 1.0, 2.0],
                "recent_zero_count": [0, 0, 0, 0],
                "origin_index": [3, 4, 5, 6],
                "state_code": ["AA"] * 4,
                "target_quarter": [1, 2, 3, 4],
                "response": [5.0, 5.0, 5.0, 5.0],
            }
        )
        prediction = training.drop(columns="response").iloc[[3]].copy()
        small = fit_predict_raw_delta_ridge(training, prediction, alpha=1.0)
        large = fit_predict_raw_delta_ridge(
            training, prediction, alpha=1_000_000.0
        )
        persistence = float(prediction.iloc[0]["level_t"])

        self.assertLess(
            abs(float(large.predictions.iloc[0]["forecast"]) - persistence),
            abs(float(small.predictions.iloc[0]["forecast"]) - persistence),
        )


if __name__ == "__main__":
    unittest.main()
