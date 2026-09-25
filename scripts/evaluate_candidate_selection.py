from __future__ import annotations

import argparse
from pathlib import Path

from coal_forecasting.candidate_selection import run_candidate_selection_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen selection-only Ridge candidate evaluation."
    )
    parser.add_argument("--project-config", default="configs/project.json")
    parser.add_argument(
        "--candidate-config", default="configs/ridge_log_change.json"
    )
    parser.add_argument("--root", type=Path, default=None)
    arguments = parser.parse_args()

    result = run_candidate_selection_evaluation(
        arguments.project_config,
        arguments.candidate_config,
        root=arguments.root,
    )
    print(f"Run: {result['manifest']['run_id']}")
    print(f"Manifest: {result['manifest']['manifest_path']}")
    print(f"Selected alpha: {result['selected_alpha']}")
    print(result["candidate_metrics"].to_string(index=False))
    print("Diagnostic gate: awaiting review")


if __name__ == "__main__":
    main()
