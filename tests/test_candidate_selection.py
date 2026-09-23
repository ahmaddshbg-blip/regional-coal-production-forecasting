from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

import pandas as pd

from coal_forecasting.candidate_selection import (
    SelectionGuardError,
    load_candidate_config,
    evaluate_candidate_selection,
    selection_origin_labels,
)


def project_config() -> dict[str, object]:
    return {
        "random_seed": 7,
        "evaluation": {
            "modeling_start": "2019Q1",
            "forecast_horizons": [1, 2, 3, 4],
            "eligibility": {
                "minimum_non_null_history": 8,
                "required_consecutive_recent_observations": 4,
            },
        },
    }


def candidate_config() -> dict[str, object]:
    return {
        "procedure_id": "pooled_direct_ridge_log_change_v1",
        "alpha_grid": [0.1, 1.0],
        "tie_tolerance": 0.0001,
        "selection_origins": {"start": "2020Q4", "end": "2021Q1", "count": 2},
        "confirmation_origins": {
            "start": "2021Q2",
            "end": "2021Q3",
            "count": 2,
        },
        "intervals": {"warmup_origins": 1, "coverages": [0.8, 0.95]},
        "bootstrap": {"block_length": 1, "replications": 20, "seed": 7},
    }


def candidate_v2_config() -> dict[str, object]:
    return {
        "procedure_id": "pooled_direct_ridge_raw_delta_v2",
        "alpha_grid": [1.0, 100.0, 10000.0, 1000000.0],
        "tie_tolerance": 0.0001,
        "selection_origins": {"start": "2020Q4", "end": "2021Q1", "count": 2},
        "confirmation_origins": {
            "start": "2021Q2",
            "end": "2021Q3",
            "count": 2,
        },
        "features": {
            "numeric": [
                "level_t",
                "raw_change_1",
                "raw_change_2",
                "raw_change_3",
                "recent_zero_count",
                "origin_index",
            ],
            "categorical": ["state_code", "target_quarter"],
        },
        "intervals": {"warmup_origins": 1, "coverages": [0.8, 0.95]},
        "bootstrap": {"block_length": 1, "replications": 20, "seed": 7},
    }


def panel_frame() -> pd.DataFrame:
    records = []
    periods = pd.period_range("2019Q1", "2022Q1", freq="Q")
    for state_index, state in enumerate(("AA", "BB"), start=1):
        for index, period in enumerate(periods, start=1):
            value = float(state_index * 100 + index * 2)
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


class CandidateSelectionTests(unittest.TestCase):
    def test_candidate_config_rejects_feature_contract_drift(self) -> None:
        invalid = candidate_config()
        invalid["features"] = {
            "numeric": ["log_level_t"],
            "categorical": ["state_code", "target_quarter"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "feature contract"):
                load_candidate_config(path)

    def test_selection_origin_contract_and_overlap_guard(self) -> None:
        self.assertEqual(selection_origin_labels(candidate_config()), ["2020Q4", "2021Q1"])
        invalid = candidate_config()
        invalid["confirmation_origins"] = {
            "start": "2021Q1",
            "end": "2021Q2",
            "count": 2,
        }
        with self.assertRaisesRegex(SelectionGuardError, "overlap"):
            selection_origin_labels(invalid)

    def test_selection_evaluation_never_opens_confirmation(self) -> None:
        result = evaluate_candidate_selection(
            panel_frame(),
            project_config(),
            candidate_config(),
        )

        self.assertIn(result["selected_alpha"], {0.1, 1.0})
        self.assertTrue(result["candidate_metrics"]["prediction_coverage"].eq(1.0).all())
        self.assertEqual(
            set(result["interval_metrics"]["nominal_coverage"]), {0.8, 0.95}
        )
        self.assertEqual(
            set(result["bootstrap_skill"]["summary"]),
            {"horizon_1", "horizon_2", "horizon_3", "horizon_4", "equal_weight_mean"},
        )
        self.assertEqual(result["checks"]["diagnostic_gate_status"], "awaiting_review")
        self.assertFalse(result["checks"]["confirmation_opened"])
        self.assertFalse(result["checks"]["holdout_opened"])
        self.assertLessEqual(
            result["candidate_forecasts"]["origin_date"].max(),
            pd.Timestamp("2021-01-01"),
        )
        self.assertLessEqual(
            result["candidate_forecasts"]["target_date"].max(),
            pd.Timestamp("2022-01-01"),
        )

    def test_v2_selection_uses_frozen_procedure_without_opening_confirmation(self) -> None:
        result = evaluate_candidate_selection(
            panel_frame(),
            project_config(),
            candidate_v2_config(),
        )

        self.assertIn(result["selected_alpha"], {1.0, 100.0, 10000.0, 1000000.0})
        self.assertEqual(
            set(result["candidate_forecasts"]["model"]),
            {"pooled_direct_ridge_raw_delta_v2"},
        )
        self.assertFalse(result["checks"]["confirmation_opened"])
        self.assertFalse(result["checks"]["holdout_opened"])

    def test_selection_evaluation_rejects_values_after_selection_target_end(self) -> None:
        panel = panel_frame()
        extra = panel.loc[panel["period"].eq("2022Q1")].copy()
        extra["cal_quarter"] = 2
        extra["period"] = "2022Q2"
        extra["quarter_start_date"] = pd.Timestamp("2022-04-01")
        panel = pd.concat([panel, extra], ignore_index=True)
        with self.assertRaisesRegex(SelectionGuardError, "after selection target end"):
            evaluate_candidate_selection(
                panel,
                project_config(),
                candidate_config(),
                require_truncated_panel=True,
            )


if __name__ == "__main__":
    unittest.main()
