from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coal_forecasting.config import config_sha256, load_config
from coal_forecasting.paths import resolve_pipeline_paths


class ConfigAndPathTests(unittest.TestCase):
    def test_config_hash_ignores_runtime_path(self) -> None:
        config = {
            "project": "example",
            "schema_version": "1",
            "random_seed": 1,
            "snapshot": {},
            "paths": {},
            "raw_files": {},
            "quality_expectations": {},
            "evaluation": {},
            "_config_path": "one/place.json",
        }
        first_hash = config_sha256(config)
        config["_config_path"] = "another/place.json"
        self.assertEqual(first_hash, config_sha256(config))

    def test_load_config_reports_missing_contract_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "project.json"
            config_path.write_text(json.dumps({"project": "incomplete"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required keys"):
                load_config(config_path)

    def test_environment_paths_override_repository_defaults(self) -> None:
        config = {
            "paths": {
                "default_data_root": "data",
                "default_runs_root": "runs",
                "raw_dir": "raw",
                "interim_dir": "interim",
                "processed_dir": "processed",
                "mine_quarter_checkpoint": "mine.parquet",
                "state_quarter_checkpoint": "state.parquet",
            },
            "raw_files": {
                "quarterly_production": {"filename": "quarterly.txt"},
                "mine_master": {"filename": "mines.txt"},
            },
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            data_root = temporary_root / "drive-data"
            runs_root = temporary_root / "drive-runs"
            with patch.dict(
                os.environ,
                {
                    "PROJECT_DATA_ROOT": str(data_root),
                    "PROJECT_RUNS_ROOT": str(runs_root),
                },
                clear=False,
            ):
                paths = resolve_pipeline_paths(config, temporary_root / "repository")

            self.assertEqual(paths["data_root"], data_root.resolve())
            self.assertEqual(paths["runs_root"], runs_root.resolve())
            self.assertEqual(paths["quarterly_raw"], data_root / "raw" / "quarterly.txt")
            self.assertEqual(paths["state_quarter"], data_root / "processed" / "state.parquet")


if __name__ == "__main__":
    unittest.main()
