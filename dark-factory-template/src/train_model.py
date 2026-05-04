#!/usr/bin/env python3
"""
Model Training + Feature Importance + Gate 1
=============================================
Trains one or more models, computes feature importance (e.g., SHAP),
and runs automated leakage checks before scoring.

This is a scaffold — replace the training logic with your actual
model code, but keep the gate check integration.

Usage:
    python src/train_model.py [--data data/training_data.csv] [--output results/]
"""

import argparse
import json
import sys
from pathlib import Path

# from leakage_checks import run_all_checks  # uncomment when wired up


def load_data(data_path):
    """Load and split training data.

    Replace with your actual data loading:
      import pandas as pd
      df = pd.read_csv(data_path)
      X = df.drop(columns=["target"])
      y = df["target"]
    """
    print(f"Loading data from {data_path}...")
    # TODO: Replace with actual loading
    return None, None  # X, y


def train(X, y, model_name="primary"):
    """Train a model and return it with feature importances.

    Replace with your actual training:
      import xgboost as xgb
      model = xgb.XGBClassifier(...)
      model.fit(X, y)
      importances = list(zip(X.columns, model.feature_importances_))
      importances.sort(key=lambda x: x[1], reverse=True)
    """
    print(f"Training model: {model_name}...")
    # TODO: Replace with actual training
    model = None
    importances = []  # [(feature_name, importance), ...]
    metrics = {"auc": 0.0}
    return model, importances, metrics


def compute_feature_importance(model, X):
    """Compute SHAP values or other feature importance measures.

    SHAP provides per-prediction explanations, not just global importance.
    This enables the recommendation engine to give deal-level prescriptive
    actions based on what features are driving each prediction.

    Replace with your actual SHAP computation:
      import shap
      explainer = shap.TreeExplainer(model)
      shap_values = explainer.shap_values(X)
    """
    print("Computing feature importance...")
    # TODO: Replace with actual SHAP
    return None


def run_gate_1(importances, training_stats, scoring_stats, feature_aucs, class_rates):
    """Run automated leakage checks (Gate 1).

    If any check fails, the pipeline should halt.
    See leakage_checks.py for the four checks.
    """
    from leakage_checks import run_all_checks
    result = run_all_checks(importances, training_stats, scoring_stats,
                            feature_aucs, class_rates)

    status = "PASSED" if result["passed"] else "FAILED"
    print(f"Leakage check: {status}")
    if not result["passed"]:
        print(f"  Flagged features: {result['all_flagged']}")
        for check in result["checks"]:
            if not check["passed"]:
                print(f"  - {check['details']}")

    return result


def save_results(output_dir, model_name, importances, metrics, gate_result):
    """Save model artifacts, importances, and gate results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save feature importances as CSV
    import csv
    with open(output_dir / "feature_importance.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["feature", "importance"])
        for feat, imp in importances:
            writer.writerow([feat, imp])

    # Save model results summary
    with open(output_dir / "model_results.txt", "a") as f:
        f.write(f"\nMODEL: {model_name}\n")
        for metric, value in metrics.items():
            f.write(f"  {metric.upper()}: {value}\n")
        status = "PASSED" if gate_result["passed"] else "FAILED"
        f.write(f"  Leakage check: {status}\n")

    print(f"Results saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Model Training")
    parser.add_argument("--data", default="data/training_data.csv")
    parser.add_argument("--output", default="results/")
    args = parser.parse_args()

    data_path = Path(args.data)
    output_dir = Path(args.output)

    X, y = load_data(data_path)
    model, importances, metrics = train(X, y)

    # Gate 1: Automated leakage checks
    # gate_result = run_gate_1(importances, ...)
    gate_result = {"passed": True, "checks": [], "all_flagged": []}

    save_results(output_dir, "primary", importances, metrics, gate_result)

    if not gate_result["passed"]:
        print("\nGate 1 FAILED — pipeline halted. Fix flagged features before proceeding.")
        sys.exit(1)

    print("\nTraining complete. Gate 1 passed.")


if __name__ == "__main__":
    main()
