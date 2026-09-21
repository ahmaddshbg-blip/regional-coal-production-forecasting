"""Load and validate the project's versioned JSON configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {
    "project",
    "schema_version",
    "random_seed",
    "snapshot",
    "paths",
    "raw_files",
    "quality_expectations",
    "evaluation",
}


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a project config and fail early when its contract is incomplete."""
    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    missing = REQUIRED_TOP_LEVEL_KEYS.difference(config)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Config is missing required keys: {missing_list}")

    for file_key in ("quarterly_production", "mine_master"):
        try:
            file_config = config["raw_files"][file_key]
        except KeyError as exc:
            raise ValueError(f"Config is missing raw_files.{file_key}") from exc
        required = {"filename", "bytes", "sha256", "delimiter", "encoding", "columns"}
        missing_file_keys = required.difference(file_config)
        if missing_file_keys:
            fields = ", ".join(sorted(missing_file_keys))
            raise ValueError(f"raw_files.{file_key} is missing: {fields}")

    config["_config_path"] = str(config_path)
    return config


def config_sha256(config: dict[str, Any]) -> str:
    """Return a stable hash while excluding runtime-only metadata."""
    public_config = {key: value for key, value in config.items() if not key.startswith("_")}
    canonical = json.dumps(
        public_config,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
