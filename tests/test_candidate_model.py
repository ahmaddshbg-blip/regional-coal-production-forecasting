from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from coal_forecasting.candidate import fit_predict_ridge, select_shared_alpha


def training_frame() -> pd.DataFrame:
    records = []
    for index in range(16):
        records.append(
            {
                "state_code": "AA" if index % 2 == 0 else "BB",
                "target_quarter": (index % 4) + 1,
                "log_level_t": 3.0 + index / 10,
                "log_change_1": 0.05,
                "log_change_2": 0.02,
                "log_change_3": -0.01,
                "recent_zero_count": 0,
                "origin_index": index,
                "response": -0.03 + index / 1000,
            }
        )
    return pd.DataFrame.from_records(records)


class CandidateModelTests(unittest.TestCase):
    def test_ridge_is_deterministic_nonnegative_and_flags_unknown_state(self) -> None:
        prediction = training_frame().iloc[[0]].drop(columns="response").copy()
        prediction["state_code"] = "CC"
        prediction["log_level_t"] = 0.0

        first = fit_predict_ridge(training_frame(), prediction, alpha=1.0)
        second = fit_predict_ridge(training_frame(), prediction, alpha=1.0)

        np.testing.assert_allclose(
            first.predictions["forecast"], second.predictions["forecast"]
        )
        self.assertGreaterEqual(first.predictions.loc[0, "forecast"], 0.0)
        self.assertFalse(first.predictions.loc[0, "state_seen_in_training"])
        self.assertIn("coefficient", first.coefficients.columns)

    def test_alpha_selection_requires_coverage_and_uses_larger_tie(self) -> None:
        metrics = pd.DataFrame(
            {
                "alpha": [0.1, 0.1, 1.0, 1.0, 10.0, 10.0],
                "horizon": [1, 2, 1, 2, 1, 2],
                "wape": [0.09, 0.09, 0.09, 0.09, 0.08, 0.08],
                "comparator_wape": [0.10] * 6,
                "prediction_coverage": [1.0, 1.0, 1.0, 1.0, 0.99, 1.0],
            }
        )

        selected, summary = select_shared_alpha(metrics, tie_tolerance=0.0001)

        self.assertEqual(selected, 1.0)
        self.assertFalse(summary.loc[summary["alpha"].eq(10.0), "eligible"].item())


if __name__ == "__main__":
    unittest.main()
