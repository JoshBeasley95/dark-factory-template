#!/usr/bin/env python3
"""
End-to-End Orchestration
=========================
Coordinates the full pipeline: extract -> train -> score.
Three modes for different refresh cadences.

Usage:
    python src/refresh_scores.py --mode full          # Full retrain (monthly)
    python src/refresh_scores.py --mode score-only    # Re-score with existing model (weekly)
    python src/refresh_scores.py --mode skip-extract  # Dev mode (from cached data)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent


def run_step(description, command):
    """Run a pipeline step and halt on failure."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")

    result = subprocess.run(
        command, cwd=REPO_DIR,
        capture_output=False  # Stream output to terminal
    )

    if result.returncode != 0:
        print(f"\nFAILED: {description}")
        sys.exit(1)


def save_refresh_metadata(results_dir, mode):
    """Record what was run and when, for the coverage eval check."""
    results_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    }

    # Count predictions if they exist
    predictions_file = results_dir / "predictions.json"
    if predictions_file.exists():
        with open(predictions_file) as f:
            data = json.load(f)
        metadata["record_count"] = len(data)

    with open(results_dir / "last_refresh.json", "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Pipeline Orchestration")
    parser.add_argument("--mode", choices=["full", "score-only", "skip-extract"],
                        default="full", help="Refresh mode")
    args = parser.parse_args()

    results_dir = REPO_DIR / "results"
    python = sys.executable

    if args.mode == "full":
        run_step("Step 1/3: Extract data",
                 [python, "src/extract_data.py"])
        run_step("Step 2/3: Train model",
                 [python, "src/train_model.py"])
        run_step("Step 3/3: Score pipeline",
                 [python, "src/score_pipeline.py"])

    elif args.mode == "score-only":
        run_step("Step 1/1: Score pipeline (using existing model)",
                 [python, "src/score_pipeline.py"])

    elif args.mode == "skip-extract":
        run_step("Step 1/2: Train model (from cached data)",
                 [python, "src/train_model.py"])
        run_step("Step 2/2: Score pipeline",
                 [python, "src/score_pipeline.py"])

    save_refresh_metadata(results_dir, args.mode)

    # Run quality gate
    print(f"\n{'='*60}")
    print("  Running quality gate...")
    print(f"{'='*60}")
    gate_result = subprocess.run(
        [python, "tests/gate_review.py", "--all"],
        cwd=REPO_DIR
    )

    if gate_result.returncode != 0:
        print("\nQuality gate FAILED — results are NOT ready for delivery.")
        sys.exit(1)

    print("\nPipeline complete. Quality gate PASSED. Results ready for delivery.")


if __name__ == "__main__":
    main()
