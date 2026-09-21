from __future__ import annotations

import argparse
from pathlib import Path

from coal_forecasting.evaluation import run_development_baseline_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run frozen development-only coal-production baselines."
    )
    parser.add_argument("--config", default="configs/project.json")
    parser.add_argument("--root", type=Path, default=None)
    arguments = parser.parse_args()

    result = run_development_baseline_evaluation(
        arguments.config,
        root=arguments.root,
    )
    print(f"Run: {result['manifest']['run_id']}")
    print(f"Manifest: {result['manifest']['manifest_path']}")
    print(result["metrics"].to_string(index=False))


if __name__ == "__main__":
    main()
