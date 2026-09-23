from __future__ import annotations

import unittest

import pandas as pd

from coal_forecasting.candidate_diagnostics import (
    DiagnosticBoundaryError,
    residual_autocorrelation,
    validate_selection_frame,
)


class CandidateDiagnosticTests(unittest.TestCase):
    def test_selection_diagnostics_reject_confirmation_rows(self) -> None:
        forecasts = pd.DataFrame(
            {
                "origin_date": [pd.Timestamp("2016-07-01"), pd.Timestamp("2016-10-01")],
                "state_code": ["AA", "AA"],
                "horizon": [1, 1],
                "forecast": [1.0, 1.0],
                "actual": [1.0, 1.0],
                "scored": [True, True],
            }
        )

        with self.assertRaisesRegex(DiagnosticBoundaryError, "confirmation"):
            validate_selection_frame(forecasts, selection_end="2016Q3")

    def test_residual_autocorrelation_pairs_within_state_and_horizon(self) -> None:
        origins = pd.period_range("2010Q1", periods=8, freq="Q").to_timestamp()
        forecasts = pd.DataFrame(
            {
                "origin_date": list(origins) * 2,
                "state_code": ["AA"] * 8 + ["BB"] * 8,
                "horizon": [1] * 16,
                "forecast": [float(i) for i in range(8)] * 2,
                "actual": [0.0] * 16,
                "scored": [True] * 16,
            }
        )

        result = residual_autocorrelation(
            forecasts,
            lags=(1, 4),
            minimum_pairs=4,
        )

        self.assertEqual(set(result["state_code"]), {"AA", "BB"})
        self.assertEqual(set(result["lag"]), {1, 4})
        self.assertTrue(result["correlation"].eq(1.0).all())


if __name__ == "__main__":
    unittest.main()
