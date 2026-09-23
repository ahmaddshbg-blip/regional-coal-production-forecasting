from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from coal_forecasting.baselines import generate_baseline_forecasts
from coal_forecasting.evaluation import build_forecast_cells_for_origins
from coal_forecasting.final_baseline import (
    HoldoutGuardError,
    apply_frozen_intervals,
    build_latest_forecasts,
    calibrate_baseline_intervals,
    claim_holdout_once,
    complete_holdout_marker,
    evaluate_final_frames,
    holdout_origin_labels,
    select_final_forecasts,
    validate_final_config,
)


MODELS_BY_HORIZON = {
    "1": "persistence",
    "2": "persistence",
    "3": "seasonal_naive",
    "4": "persistence",
}


def project_config() -> dict[str, object]:
    return {
        "snapshot": {"checkpoint_id": "test-checkpoint"},
        "evaluation": {
            "modeling_start": "2019Q1",
            "forecast_horizons": [1, 2, 3, 4],
            "validation_origins": {
                "start": "2020Q1",
                "end": "2020Q2",
                "count": 2,
            },
            "embargo_origins": {
                "start": "2020Q3",
                "end": "2021Q2",
                "count": 4,
            },
            "holdout_origins": {
                "start": "2021Q3",
                "end": "2022Q2",
                "count": 4,
            },
            "scored_target_end": "2023Q2",
            "latest_forecast_origin": "2023Q3",
            "eligibility": {
                "minimum_non_null_history": 4,
                "required_consecutive_recent_observations": 2,
            },
        },
    }


def final_config() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "procedure_id": "horizon_specific_naive_baseline_v1",
        "models_by_horizon": MODELS_BY_HORIZON,
        "development_calibration_origins": {
            "start": "2020Q1",
            "end": "2020Q2",
            "count": 2,
        },
        "holdout_origins": {
            "start": "2021Q3",
            "end": "2022Q2",
            "count": 4,
            "target_end": "2023Q2",
        },
        "latest_forecast": {
            "origin": "2023Q3",
            "target_end": "2024Q3",
            "revision_status": "subject_to_revision",
        },
        "intervals": {
            "coverages": [0.8, 0.95],
            "normalization": "origin_time_state_seasonal_mase_scale",
            "fallback": "pooled_unscaled_absolute_error",
            "lower_bound": 0.0,
        },
        "reporting": {
            "operational_focus_horizons": [1, 2],
            "reported_horizons": [1, 2, 3, 4],
            "primary_metric": "WAPE",
            "secondary_metric": "seasonal_MASE",
        },
    }


def latest_panel() -> pd.DataFrame:
    periods = pd.period_range("2019Q1", "2023Q3", freq="Q")
    return pd.DataFrame.from_records(
        [
            {
                "state_code": "AA",
                "cal_year": period.year,
                "cal_quarter": period.quarter,
                "period": f"{period.year}Q{period.quarter}",
                "quarter_start_date": period.start_time,
                "coal_production_short_tons": float(index),
            }
            for index, period in enumerate(periods, start=1)
        ]
    )


def baseline_forecasts() -> pd.DataFrame:
    records = []
    for horizon in (1, 2, 3, 4):
        for model, offset in (("persistence", 1.0), ("seasonal_naive", 2.0)):
            records.append(
                {
                    "state_code": "AA",
                    "origin": "2020Q1",
                    "origin_date": pd.Timestamp("2020-01-01"),
                    "target_period": f"2020Q{horizon + 1}" if horizon < 4 else "2021Q1",
                    "target_date": pd.Timestamp("2020-01-01")
                    + pd.DateOffset(months=3 * horizon),
                    "horizon": horizon,
                    "model": model,
                    "forecast": 100.0 + offset,
                    "actual": 100.0,
                    "mase_scale": 10.0,
                    "prediction_available": True,
                    "actual_observed": True,
                    "scored": True,
                    "unscored_reason": "",
                }
            )
    return pd.DataFrame.from_records(records)


class FinalBaselineTests(unittest.TestCase):
    def test_final_contract_matches_project_boundaries(self) -> None:
        validated = validate_final_config(final_config(), project_config())
        self.assertEqual(validated["procedure_id"], "horizon_specific_naive_baseline_v1")
        self.assertEqual(
            holdout_origin_labels(validated, project_config()),
            ["2021Q3", "2021Q4", "2022Q1", "2022Q2"],
        )

        invalid = final_config()
        invalid["holdout_origins"] = {
            **invalid["holdout_origins"],
            "target_end": "2023Q3",
        }
        with self.assertRaisesRegex(HoldoutGuardError, "target cutoff"):
            validate_final_config(invalid, project_config())

    def test_horizon_specific_mapping_is_exact(self) -> None:
        selected = select_final_forecasts(
            baseline_forecasts(),
            MODELS_BY_HORIZON,
        )

        self.assertEqual(len(selected), 4)
        self.assertEqual(
            selected.set_index("horizon")["source_model"].to_dict(),
            {1: "persistence", 2: "persistence", 3: "seasonal_naive", 4: "persistence"},
        )
        self.assertEqual(
            set(selected["model"]), {"horizon_specific_naive_baseline_v1"}
        )

    def test_calibration_rejects_post_development_origin(self) -> None:
        selected = select_final_forecasts(
            baseline_forecasts(),
            MODELS_BY_HORIZON,
        )
        selected.loc[0, "origin_date"] = pd.Timestamp("2021-04-01")

        with self.assertRaisesRegex(HoldoutGuardError, "development boundary"):
            calibrate_baseline_intervals(
                selected,
                development_end="2021Q1",
                coverages=(0.80, 0.95),
            )

    def test_frozen_intervals_do_not_use_holdout_actuals(self) -> None:
        development = pd.concat(
            [
                select_final_forecasts(baseline_forecasts(), MODELS_BY_HORIZON),
                select_final_forecasts(baseline_forecasts(), MODELS_BY_HORIZON).assign(
                    origin="2020Q2",
                    origin_date=pd.Timestamp("2020-04-01"),
                    actual=110.0,
                ),
            ],
            ignore_index=True,
        )
        quantiles = calibrate_baseline_intervals(
            development,
            development_end="2021Q1",
            coverages=(0.80, 0.95),
        )
        future = select_final_forecasts(
            baseline_forecasts(), MODELS_BY_HORIZON
        ).assign(actual=np.nan, actual_observed=False, scored=False)
        first = apply_frozen_intervals(future, quantiles)
        second = apply_frozen_intervals(future.assign(actual=999999.0), quantiles)

        interval_columns = ["lower_80", "upper_80", "lower_95", "upper_95"]
        pd.testing.assert_frame_equal(
            first[interval_columns],
            second[interval_columns],
        )

    def test_holdout_marker_requires_explicit_open_and_blocks_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_root = Path(directory)
            with self.assertRaisesRegex(HoldoutGuardError, "explicit"):
                claim_holdout_once(
                    runs_root,
                    procedure_sha256="abc",
                    open_holdout=False,
                    passed_run_id=None,
                )

            opened = claim_holdout_once(
                runs_root,
                procedure_sha256="abc",
                open_holdout=True,
                passed_run_id=None,
            )
            self.assertEqual(opened["mode"], "new")

            with self.assertRaisesRegex(HoldoutGuardError, "without a passed run"):
                claim_holdout_once(
                    runs_root,
                    procedure_sha256="abc",
                    open_holdout=True,
                    passed_run_id=None,
                )

            reused = claim_holdout_once(
                runs_root,
                procedure_sha256="abc",
                open_holdout=False,
                passed_run_id="accepted-run",
            )
            self.assertEqual(reused["mode"], "reuse")
            self.assertEqual(reused["run_id"], "accepted-run")

            complete_holdout_marker(
                Path(reused["marker_path"]),
                procedure_sha256="abc",
                run_id="accepted-run",
                manifest_path="accepted-run/manifest.json",
            )
            marker = claim_holdout_once(
                runs_root,
                procedure_sha256="abc",
                open_holdout=False,
                passed_run_id="accepted-run",
            )["marker"]
            self.assertEqual(marker["status"], "passed")
            self.assertEqual(marker["run_id"], "accepted-run")
            with self.assertRaisesRegex(HoldoutGuardError, "different runs"):
                claim_holdout_once(
                    runs_root,
                    procedure_sha256="abc",
                    open_holdout=False,
                    passed_run_id="different-run",
                )

    def test_latest_forecasts_are_unscored_and_have_no_future_actuals(self) -> None:
        quantiles = pd.DataFrame.from_records(
            [
                {
                    "horizon": horizon,
                    "nominal_coverage": coverage,
                    "normalized_quantile": 1.0,
                    "unscaled_quantile": 2.0,
                }
                for coverage in (0.80, 0.95)
                for horizon in (1, 2, 3, 4)
            ]
        )
        forecasts = build_latest_forecasts(
            latest_panel(),
            project_config(),
            final_config(),
            quantiles,
        )

        self.assertEqual(len(forecasts), 4)
        self.assertTrue(forecasts["actual"].isna().all())
        self.assertFalse(forecasts["actual_observed"].any())
        self.assertFalse(forecasts["scored"].any())
        self.assertTrue(forecasts["prediction_available"].all())
        self.assertTrue(np.isfinite(forecasts["forecast"]).all())
        self.assertTrue(forecasts["forecast"].ge(0).all())

    def test_integrated_frames_keep_holdout_and_latest_outputs_separate(self) -> None:
        project = project_config()
        final = final_config()
        panel = latest_panel()
        development_cells = build_forecast_cells_for_origins(
            panel.loc[panel["period"].le("2021Q2")],
            project["evaluation"],
            origins=["2020Q1", "2020Q2"],
            target_end="2021Q2",
        )
        development = generate_baseline_forecasts(development_cells, panel)
        result = evaluate_final_frames(
            panel.loc[panel["period"].le("2023Q2")],
            panel,
            development,
            project,
            final,
        )

        self.assertEqual(
            set(result["holdout_forecasts"]["origin"]),
            {"2021Q3", "2021Q4", "2022Q1", "2022Q2"},
        )
        self.assertEqual(len(result["holdout_forecasts"]), 16)
        self.assertEqual(len(result["latest_forecasts"]), 4)
        self.assertEqual(len(result["holdout_interval_metrics"]), 10)
        self.assertEqual(
            set(result["holdout_interval_metrics"]["evaluation_scope"]),
            {"horizon", "pooled"},
        )
        self.assertTrue(result["latest_forecasts"]["actual"].isna().all())
        self.assertEqual(
            set(result["latest_forecasts"]["source_snapshot"]),
            {"test-checkpoint"},
        )


if __name__ == "__main__":
    unittest.main()
