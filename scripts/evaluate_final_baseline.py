from __future__ import annotations

import argparse
from pathlib import Path

from coal_forecasting.final_baseline import run_final_baseline_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate or reuse the frozen final baseline holdout."
    )
    parser.add_argument("--project-config", default="configs/project.json")
    parser.add_argument("--final-config", default="configs/final_baseline.json")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--open-holdout",
        action="store_true",
        help="Irreversibly open the final holdout if no passed run exists.",
    )
    arguments = parser.parse_args()

    result = run_final_baseline_evaluation(
        arguments.project_config,
        arguments.final_config,
        open_holdout=arguments.open_holdout,
        root=arguments.root,
    )
    manifest = result["manifest"]
    print(f"Access mode: {result['access_mode']}")
    print(f"Run: {manifest['run_id']}")
    print(f"Manifest: {manifest['manifest_path']}")
    print(result["holdout_metrics"].to_string(index=False))


if __name__ == "__main__":
    main()
