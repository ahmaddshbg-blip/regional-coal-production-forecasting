"""Build validated mine-quarter and state-quarter Parquet checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import duckdb

from coal_forecasting.config import config_sha256, load_config
from coal_forecasting.paths import project_root, resolve_pipeline_paths
from coal_forecasting.validation import ValidationError, sha256_file, validate_raw_file


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _read_csv_view_sql(view_name: str, path: Path, spec: dict[str, Any]) -> str:
    column_types = spec.get("column_types", {})
    fields = []
    for column in spec["columns"]:
        column_type = column_types.get(column, "VARCHAR")
        fields.append(f"{_sql_literal(column)}: {_sql_literal(column_type)}")
    columns_sql = "{" + ", ".join(fields) + "}"
    quotechar = spec.get("quotechar", '"')
    strict_mode = "true" if spec.get("strict_mode", True) else "false"

    return f"""
        CREATE OR REPLACE TEMP VIEW {view_name} AS
        SELECT *
        FROM read_csv(
            {_sql_literal(path.as_posix())},
            delim = {_sql_literal(spec['delimiter'])},
            header = true,
            quote = {_sql_literal(quotechar)},
            escape = {_sql_literal(quotechar)},
            encoding = {_sql_literal(spec['encoding'])},
            auto_detect = false,
            columns = {columns_sql},
            nullstr = '',
            strict_mode = {strict_mode}
        );
    """


def _read_sql(name: str, root: Path) -> str:
    return (root / "sql" / name).read_text(encoding="utf-8")


def _transcode_latin1_to_utf8(source: Path, destination: Path) -> None:
    """Preserve every source byte as its Latin-1 code point in valid UTF-8."""
    with source.open("r", encoding="latin-1", newline="") as input_handle:
        with destination.open("w", encoding="utf-8", newline="") as output_handle:
            for chunk in iter(lambda: input_handle.read(1024 * 1024), ""):
                output_handle.write(chunk)


def _duckdb_input(
    source: Path,
    spec: dict[str, Any],
    staging_directory: Path,
) -> tuple[Path, dict[str, Any]]:
    parser_spec = dict(spec)
    if spec.get("duckdb_encoding") != "utf-8-transcoded":
        return source, parser_spec

    staged_path = staging_directory / f"{source.name}.utf8"
    _transcode_latin1_to_utf8(source, staged_path)
    parser_spec["encoding"] = "utf-8"
    return staged_path, parser_spec


def _quality_results(connection: duckdb.DuckDBPyConnection, root: Path) -> dict[str, str]:
    rows = connection.execute(_read_sql("quality_checks.sql", root)).fetchall()
    return {str(name): str(value) for name, value in rows}


def _validate_quality(
    observed: dict[str, str],
    expected: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    failures: list[str] = []

    for check_name, expected_value in expected.items():
        if check_name not in observed:
            raise ValidationError(f"Quality query did not return required check: {check_name}")
        passed = observed[check_name] == str(expected_value)
        results[check_name] = {
            "expected": expected_value,
            "observed": observed[check_name],
            "status": "passed" if passed else "failed",
        }
        if not passed:
            failures.append(
                f"{check_name}: expected {expected_value}, observed {observed[check_name]}"
            )

    for check_name, observed_value in observed.items():
        if check_name not in results:
            results[check_name] = {
                "expected": None,
                "observed": observed_value,
                "status": "diagnostic",
            }

    if failures:
        raise ValidationError("Quality checks failed: " + "; ".join(failures))
    return results


def _git_state(root: Path) -> dict[str, Any]:
    def run_git(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None
        return completed.stdout.strip()

    commit = run_git("rev-parse", "HEAD")
    status = run_git("status", "--porcelain")
    return {
        "commit": commit,
        "dirty": bool(status) if status is not None else None,
    }


def _package_version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _parquet_metadata(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    data_root: Path,
) -> dict[str, Any]:
    path_sql = _sql_literal(path.as_posix())
    row_count = connection.execute(
        f"SELECT COUNT(*) FROM read_parquet({path_sql})"
    ).fetchone()[0]
    schema_rows = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet({path_sql})"
    ).fetchall()
    schema = [
        {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
        for row in schema_rows
    ]
    schema_fingerprint = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "path": path.relative_to(data_root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "rows": int(row_count),
        "schema": schema,
        "schema_sha256": schema_fingerprint,
    }


def _copy_table_to_parquet(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    path: Path,
    order_by: str,
) -> None:
    destination = _sql_literal(path.as_posix())
    connection.execute(
        f"COPY (SELECT * FROM {table_name} ORDER BY {order_by}) "
        f"TO {destination} (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def build_dataset(
    config_path: str | Path = "configs/project.json",
    *,
    overwrite: bool = False,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the frozen inputs and build deterministic data checkpoints."""
    started_at = datetime.now(timezone.utc)
    repository_root = Path(root).expanduser().resolve() if root else project_root()
    candidate_config = Path(config_path).expanduser()
    if not candidate_config.is_absolute():
        candidate_config = repository_root / candidate_config
    config = load_config(candidate_config)
    try:
        manifest_config_path = candidate_config.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        manifest_config_path = candidate_config.name
    paths = resolve_pipeline_paths(config, repository_root)

    destinations = [paths["mine_quarter"], paths["state_quarter"]]
    existing = [path for path in destinations if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(
            f"Refusing to overwrite existing checkpoint(s): {names}. "
            "Use overwrite=True only for an intentional rebuild."
        )

    raw_validations = {
        "quarterly_production": validate_raw_file(
            paths["quarterly_raw"], config["raw_files"]["quarterly_production"]
        ),
        "mine_master": validate_raw_file(
            paths["mine_master_raw"], config["raw_files"]["mine_master"]
        ),
    }

    for destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
    paths["runs_root"].mkdir(parents=True, exist_ok=True)

    temporary_paths = {
        "mine_quarter": paths["mine_quarter"].with_name(
            f".{paths['mine_quarter'].name}.{uuid.uuid4().hex}.tmp"
        ),
        "state_quarter": paths["state_quarter"].with_name(
            f".{paths['state_quarter'].name}.{uuid.uuid4().hex}.tmp"
        ),
    }

    staging = tempfile.TemporaryDirectory(prefix="coal_forecasting_")
    staging_directory = Path(staging.name)
    quarterly_input, quarterly_parser_spec = _duckdb_input(
        paths["quarterly_raw"],
        config["raw_files"]["quarterly_production"],
        staging_directory,
    )
    mine_master_input, mine_master_parser_spec = _duckdb_input(
        paths["mine_master_raw"],
        config["raw_files"]["mine_master"],
        staging_directory,
    )

    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute(
            _read_csv_view_sql(
                "quarterly_source",
                quarterly_input,
                quarterly_parser_spec,
            )
        )
        connection.execute(
            _read_csv_view_sql(
                "mine_master",
                mine_master_input,
                mine_master_parser_spec,
            )
        )
        connection.execute(_read_sql("build_mine_quarter.sql", repository_root))
        connection.execute(_read_sql("build_state_quarter.sql", repository_root))

        observed_quality = _quality_results(connection, repository_root)
        quality = _validate_quality(
            observed_quality,
            config["quality_expectations"],
        )

        _copy_table_to_parquet(
            connection,
            "mine_quarter",
            temporary_paths["mine_quarter"],
            "state_code, mine_id, cal_year, cal_quarter",
        )
        _copy_table_to_parquet(
            connection,
            "state_quarter",
            temporary_paths["state_quarter"],
            "state_code, cal_year, cal_quarter",
        )

        output_metadata = {
            name: _parquet_metadata(connection, temporary_paths[name], paths["data_root"])
            for name in ("mine_quarter", "state_quarter")
        }

        expected_mine_rows = int(observed_quality["mine_quarter_rows"])
        expected_state_rows = int(observed_quality["state_quarter_rows"])
        if output_metadata["mine_quarter"]["rows"] != expected_mine_rows:
            raise ValidationError("Mine-quarter Parquet row count changed during serialization")
        if output_metadata["state_quarter"]["rows"] != expected_state_rows:
            raise ValidationError("State-quarter Parquet row count changed during serialization")

        for name in ("mine_quarter", "state_quarter"):
            os.replace(temporary_paths[name], paths[name])
            output_metadata[name]["path"] = paths[name].relative_to(
                paths["data_root"]
            ).as_posix()
            output_metadata[name]["bytes"] = paths[name].stat().st_size
            output_metadata[name]["sha256"] = sha256_file(paths[name])
    finally:
        connection.close()
        staging.cleanup()
        for temporary_path in temporary_paths.values():
            temporary_path.unlink(missing_ok=True)

    finished_at = datetime.now(timezone.utc)
    git_state = _git_state(repository_root)
    commit_label = git_state["commit"][:8] if git_state["commit"] else "nogit"
    run_id = (
        finished_at.strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + commit_label
        + "_"
        + uuid.uuid4().hex[:6]
    )
    run_directory = paths["runs_root"] / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    manifest_path = run_directory / "manifest.json"

    manifest = {
        "run_id": run_id,
        "stage": "validated_data_pipeline",
        "entry_point": "coal_forecasting.pipeline.build_dataset",
        "parameters": {
            "config": manifest_config_path,
            "overwrite": overwrite,
        },
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "project": config["project"],
        "schema_version": config["schema_version"],
        "checkpoint_id": config["snapshot"]["checkpoint_id"],
        "config_sha256": config_sha256(config),
        "git": git_state,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "duckdb": duckdb.__version__,
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
        },
        "inputs": raw_validations,
        "quality_checks": quality,
        "outputs": output_metadata,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {**manifest, "manifest_path": str(manifest_path)}


def load_latest_validated_manifest(
    config_path: str | Path = "configs/project.json",
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Reuse the newest matching run only after validating its full lineage."""
    repository_root = Path(root).expanduser().resolve() if root else project_root()
    candidate_config = Path(config_path).expanduser()
    if not candidate_config.is_absolute():
        candidate_config = repository_root / candidate_config
    config = load_config(candidate_config)
    paths = resolve_pipeline_paths(config, repository_root)
    expected_config_hash = config_sha256(config)

    candidates = sorted(
        paths["runs_root"].glob("*/manifest.json"),
        key=lambda path: path.parent.name,
        reverse=True,
    )
    selected_path: Path | None = None
    selected_manifest: dict[str, Any] | None = None
    for manifest_path in candidates:
        try:
            candidate = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            candidate.get("stage") == "validated_data_pipeline"
            and candidate.get("status") == "passed"
            and candidate.get("checkpoint_id") == config["snapshot"]["checkpoint_id"]
            and candidate.get("config_sha256") == expected_config_hash
        ):
            selected_path = manifest_path
            selected_manifest = candidate
            break

    if selected_path is None or selected_manifest is None:
        raise ValidationError(
            "Existing checkpoints have no passed run manifest matching the current "
            "snapshot and configuration. Rebuild with overwrite=True only after review."
        )

    current_inputs = {
        "quarterly_production": validate_raw_file(
            paths["quarterly_raw"], config["raw_files"]["quarterly_production"]
        ),
        "mine_master": validate_raw_file(
            paths["mine_master_raw"], config["raw_files"]["mine_master"]
        ),
    }
    for name, current in current_inputs.items():
        recorded = selected_manifest.get("inputs", {}).get(name, {})
        if (
            recorded.get("sha256") != current["sha256"]
            or recorded.get("bytes") != current["bytes"]
        ):
            raise ValidationError(f"Recorded input identity does not match: {name}")

    expected_outputs = {
        "mine_quarter": paths["mine_quarter"],
        "state_quarter": paths["state_quarter"],
    }
    for name, output_path in expected_outputs.items():
        recorded = selected_manifest.get("outputs", {}).get(name, {})
        expected_relative_path = output_path.relative_to(paths["data_root"]).as_posix()
        if recorded.get("path") != expected_relative_path:
            raise ValidationError(f"Recorded output path does not match: {name}")
        if not output_path.is_file():
            raise ValidationError(f"Recorded checkpoint is missing: {output_path.name}")
        if recorded.get("bytes") != output_path.stat().st_size:
            raise ValidationError(f"Recorded checkpoint size does not match: {name}")
        if recorded.get("sha256") != sha256_file(output_path):
            raise ValidationError(f"Recorded checkpoint SHA-256 does not match: {name}")

    return {**selected_manifest, "manifest_path": str(selected_path)}
