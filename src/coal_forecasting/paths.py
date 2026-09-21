"""Resolve portable repository, data, and run paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _environment_path(variable: str) -> Path | None:
    value = os.environ.get(variable, "").strip()
    return Path(value).expanduser().resolve() if value else None


def resolve_data_root(config: dict[str, Any], root: Path | None = None) -> Path:
    override = _environment_path("PROJECT_DATA_ROOT")
    if override:
        return override
    base = (root or project_root()).resolve()
    return (base / config["paths"]["default_data_root"]).resolve()


def resolve_runs_root(config: dict[str, Any], root: Path | None = None) -> Path:
    override = _environment_path("PROJECT_RUNS_ROOT")
    if override:
        return override
    base = (root or project_root()).resolve()
    return (base / config["paths"]["default_runs_root"]).resolve()


def resolve_pipeline_paths(
    config: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Path]:
    data_root = resolve_data_root(config, root)
    runs_root = resolve_runs_root(config, root)
    path_config = config["paths"]
    raw_dir = data_root / path_config["raw_dir"]
    interim_dir = data_root / path_config["interim_dir"]
    processed_dir = data_root / path_config["processed_dir"]

    return {
        "data_root": data_root,
        "runs_root": runs_root,
        "quarterly_raw": raw_dir / config["raw_files"]["quarterly_production"]["filename"],
        "mine_master_raw": raw_dir / config["raw_files"]["mine_master"]["filename"],
        "mine_quarter": interim_dir / path_config["mine_quarter_checkpoint"],
        "state_quarter": processed_dir / path_config["state_quarter_checkpoint"],
    }
