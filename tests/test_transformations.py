from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb

from coal_forecasting.pipeline import build_dataset, load_latest_validated_manifest
from coal_forecasting.validation import ValidationError, sha256_file


QUARTERLY_COLUMNS = [
    "MINE_ID",
    "CURR_MINE_NM",
    "STATE",
    "SUBUNIT_CD",
    "SUBUNIT",
    "CAL_YR",
    "CAL_QTR",
    "FISCAL_YR",
    "FISCAL_QTR",
    "AVG_EMPLOYEE_CNT",
    "HOURS_WORKED",
    "COAL_PRODUCTION",
    "COAL_METAL_IND",
]
MASTER_COLUMNS = ["MINE_ID", "STATE", "COAL_METAL_IND"]


def write_pipe_file(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.writer(handle, delimiter="|", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(columns)
        writer.writerows(rows)


def raw_spec(path: Path, columns: list[str]) -> dict[str, object]:
    return {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "delimiter": "|",
        "encoding": "latin-1",
        "quotechar": '"',
        "columns": columns,
        "column_types": {column: "VARCHAR" for column in columns},
    }


class TransformationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.data_root = self.temp_root / "data"
        self.runs_root = self.temp_root / "runs"
        raw_dir = self.data_root / "raw"
        raw_dir.mkdir(parents=True)

        quarterly_path = raw_dir / "MinesProdQuarterly.txt"
        write_pipe_file(
            quarterly_path,
            QUARTERLY_COLUMNS,
            [
                ["0000001", "Niño | Mine", "KY", "01", "UNDERGROUND", "2020", "1", "2020", "2", "2", "100", "10", "C"],
                ["0000001", "Niño | Mine", "KY", "02", "SURFACE", "2020", "1", "2020", "2", "1", "50", "", "C"],
                ["0000002", "Zero Mine", "WV", "01", "UNDERGROUND", "2020", "1", "2020", "2", "3", "120", "0", "C"],
                ["0000002", "Zero Mine", "WV", "01", "UNDERGROUND", "2020", "2", "2020", "3", "3", "110", "", "C"],
                ["0000003", "Metal Mine", "PA", "01", "SURFACE", "2020", "1", "2020", "2", "4", "130", "99", "M"],
            ],
        )

        master_path = raw_dir / "Mines.txt"
        write_pipe_file(
            master_path,
            MASTER_COLUMNS,
            [
                ["0000001", "KY", "C"],
                ["0000002", "WV", "C"],
                ["0000003", "PA", "M"],
            ],
        )

        self.config = {
            "project": "pipeline-test",
            "schema_version": "1.0.0",
            "random_seed": 1,
            "snapshot": {"checkpoint_id": "fixture"},
            "paths": {
                "default_data_root": "data",
                "default_runs_root": "runs",
                "raw_dir": "raw",
                "interim_dir": "interim",
                "processed_dir": "processed",
                "mine_quarter_checkpoint": "mine_fixture.parquet",
                "state_quarter_checkpoint": "state_fixture.parquet",
            },
            "raw_files": {
                "quarterly_production": raw_spec(quarterly_path, QUARTERLY_COLUMNS),
                "mine_master": raw_spec(master_path, MASTER_COLUMNS),
            },
            "quality_expectations": {
                "raw_quarterly_rows": 5,
                "coal_source_rows": 4,
                "coal_distinct_mines": 2,
                "duplicate_source_keys": 0,
                "invalid_coal_mine_ids": 0,
                "invalid_coal_periods": 0,
                "invalid_coal_production_values": 0,
                "negative_coal_production_rows": 0,
                "duplicate_master_mine_ids": 0,
                "unmatched_coal_mine_ids": 0,
                "mine_quarter_rows": 3,
                "mine_quarter_positive_rows": 1,
                "mine_quarter_zero_rows": 1,
                "mine_quarter_all_null_rows": 1,
                "state_count": 2,
                "state_quarter_rows": 3,
                "missing_state_mine_quarters": 0,
                "period_min": "2020Q1",
                "period_max": "2020Q2",
            },
            "evaluation": {},
        }
        self.config_path = self.temp_root / "project.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def test_pipeline_preserves_zero_null_and_partial_missing_semantics(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with patch.dict(
            os.environ,
            {
                "PROJECT_DATA_ROOT": str(self.data_root),
                "PROJECT_RUNS_ROOT": str(self.runs_root),
            },
            clear=False,
        ):
            manifest = build_dataset(self.config_path, root=repository_root)

        mine_path = self.data_root / "interim" / "mine_fixture.parquet"
        state_path = self.data_root / "processed" / "state_fixture.parquet"
        self.assertTrue(mine_path.is_file())
        self.assertTrue(state_path.is_file())
        self.assertEqual(manifest["outputs"]["mine_quarter"]["rows"], 3)
        self.assertEqual(manifest["outputs"]["state_quarter"]["rows"], 3)

        with patch.dict(
            os.environ,
            {
                "PROJECT_DATA_ROOT": str(self.data_root),
                "PROJECT_RUNS_ROOT": str(self.runs_root),
            },
            clear=False,
        ):
            reused_manifest = load_latest_validated_manifest(
                self.config_path,
                root=repository_root,
            )
        self.assertEqual(reused_manifest["run_id"], manifest["run_id"])

        connection = duckdb.connect(database=":memory:")
        try:
            mine_rows = connection.execute(
                """
                SELECT mine_id, period, quarter_start_date, coal_production_short_tons,
                       production_all_null, production_partially_null
                FROM read_parquet(?)
                ORDER BY mine_id, period
                """,
                [str(mine_path)],
            ).fetchall()
            state_null = connection.execute(
                """
                SELECT coal_production_short_tons
                FROM read_parquet(?)
                WHERE state_code = 'WV' AND period = '2020Q2'
                """,
                [str(state_path)],
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(str(mine_rows[0][2]), "2020-01-01")
        self.assertEqual(mine_rows[0][3:], (10.0, False, True))
        self.assertEqual(mine_rows[1][3], 0.0)
        self.assertIsNone(mine_rows[2][3])
        self.assertTrue(mine_rows[2][4])
        self.assertIsNone(state_null)

        with patch.dict(
            os.environ,
            {
                "PROJECT_DATA_ROOT": str(self.data_root),
                "PROJECT_RUNS_ROOT": str(self.runs_root),
            },
            clear=False,
        ):
            rebuilt_manifest = build_dataset(
                self.config_path,
                overwrite=True,
                root=repository_root,
            )
        self.assertEqual(
            manifest["outputs"]["mine_quarter"]["sha256"],
            rebuilt_manifest["outputs"]["mine_quarter"]["sha256"],
        )
        self.assertEqual(
            manifest["outputs"]["state_quarter"]["sha256"],
            rebuilt_manifest["outputs"]["state_quarter"]["sha256"],
        )

        with patch.dict(
            os.environ,
            {
                "PROJECT_DATA_ROOT": str(self.data_root),
                "PROJECT_RUNS_ROOT": str(self.runs_root),
            },
            clear=False,
        ):
            with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
                build_dataset(self.config_path, root=repository_root)

    def test_duplicate_invalid_period_and_negative_production_are_blocking(self) -> None:
        quarterly_path = self.data_root / "raw" / "MinesProdQuarterly.txt"
        with quarterly_path.open("a", encoding="latin-1", newline="") as handle:
            writer = csv.writer(handle, delimiter="|", quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerows(
                [
                    ["0000001", "Duplicate", "KY", "01", "UNDERGROUND", "2020", "1", "2020", "2", "1", "10", "-5", "C"],
                    ["0000002", "Bad Quarter", "WV", "09", "UNDERGROUND", "2020", "5", "2020", "1", "1", "10", "2", "C"],
                    ["BAD-ID", "Bad ID", "WV", "01", "UNDERGROUND", "2020", "3", "2020", "4", "1", "10", "2", "C"],
                ]
            )
        self.config["raw_files"]["quarterly_production"] = raw_spec(
            quarterly_path,
            QUARTERLY_COLUMNS,
        )
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

        repository_root = Path(__file__).resolve().parents[1]
        with patch.dict(
            os.environ,
            {
                "PROJECT_DATA_ROOT": str(self.data_root),
                "PROJECT_RUNS_ROOT": str(self.runs_root),
            },
            clear=False,
        ):
            with self.assertRaises(ValidationError) as raised:
                build_dataset(self.config_path, root=repository_root)

        message = str(raised.exception)
        self.assertIn("duplicate_source_keys", message)
        self.assertIn("invalid_coal_mine_ids", message)
        self.assertIn("invalid_coal_periods", message)
        self.assertIn("negative_coal_production_rows", message)


if __name__ == "__main__":
    unittest.main()
