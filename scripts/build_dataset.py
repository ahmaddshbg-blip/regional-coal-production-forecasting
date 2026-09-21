"""Command-line entry point for the validated Gate 4 data build."""

from __future__ import annotations

import argparse
import json

from coal_forecasting.pipeline import build_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build validated mine-quarter and state-quarter checkpoints."
    )
    parser.add_argument(
        "--config",
        default="configs/project.json",
        help="Path to the versioned project JSON configuration.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Intentionally replace existing checkpoints after validation passes.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    manifest = build_dataset(arguments.config, overwrite=arguments.overwrite)
    summary = {
        "run_id": manifest["run_id"],
        "manifest_path": manifest["manifest_path"],
        "outputs": {
            name: {
                "path": details["path"],
                "rows": details["rows"],
                "bytes": details["bytes"],
                "sha256": details["sha256"],
            }
            for name, details in manifest["outputs"].items()
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
