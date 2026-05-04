#!/usr/bin/env python3
"""
ML Pipeline Eval — Machine-Readable Quality Checks
====================================================
Scores pipeline outputs on a 100-point scale across 6 checks.
Designed to be consumed by AI coding agents and review gates.

Adapt each check function to your domain:
  - check_leakage_pass: parse your training output for leakage flags
  - check_metric_floor: set your metric (AUC, RMSE, F1) and threshold
  - check_feature_stability: compare top features against baseline
  - check_score_distribution: validate prediction values are sane
  - check_coverage: ensure deal/record count hasn't drifted
  - check_calibration: verify calibration parameters are in bounds

Usage:
    python tests/eval_pipeline.py [--results path/to/results] [--baselines path/to/baselines]

Output:
    results/eval_score.json — {"score": int, "passed": bool, "checks": [...]}
    Exit code 0 = passed (score >= 70), exit code 1 = failed.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────
# Check 1: Leakage Detection (30 points)
# Verifies that automated leakage checks passed during training.
# Adapt: change the file name and search patterns to match your
#        training script's output format.
# ──────────────────────────────────────────────────────
def check_leakage_pass(results_dir):
    results_file = results_dir / "model_results.txt"
    if not results_file.exists():
        return {"name": "leakage_pass", "passed": False, "points": 0,
                "max_points": 30, "detail": "model_results.txt not found"}

    text = results_file.read_text()
    passes = text.count("Leakage check: PASSED")
    fails = text.count("Leakage check: FAILED")

    if fails > 0:
        return {"name": "leakage_pass", "passed": False, "points": 0,
                "max_points": 30, "detail": f"{fails} model(s) failed leakage checks"}
    if passes >= 1:
        return {"name": "leakage_pass", "passed": True, "points": 30,
                "max_points": 30, "detail": f"{passes} model(s) passed leakage checks"}

    # Fallback: check if model sections exist (implies checks ran without flags)
    model_count = len(re.findall(r"^MODEL:\s+", text, re.MULTILINE))
    if model_count >= 1:
        return {"name": "leakage_pass", "passed": True, "points": 30,
                "max_points": 30, "detail": f"{model_count} model(s) trained (no leakage flags)"}
    return {"name": "leakage_pass", "passed": False, "points": 0,
            "max_points": 30, "detail": "No model sections found in model_results.txt"}


# ──────────────────────────────────────────────────────
# Check 2: Metric Floor (20 points)
# Verifies the primary evaluation metric meets a minimum threshold.
# Adapt: change `floor` value, metric name, and regex pattern
#        to match your domain (e.g., RMSE < 0.5, F1 > 0.7).
# ──────────────────────────────────────────────────────
def check_metric_floor(results_dir, floor=0.80, metric_name="AUC"):
    results_file = results_dir / "model_results.txt"
    if not results_file.exists():
        return {"name": "metric_floor", "passed": False, "points": 0,
                "max_points": 20, "detail": "model_results.txt not found"}

    text = results_file.read_text()
    # Adapt this regex to match your metric output format
    values = re.findall(r"(?:Overall CV )?" + metric_name + r":\s+([\d.]+)", text)
    if not values:
        return {"name": "metric_floor", "passed": False, "points": 0,
                "max_points": 20, "detail": f"No {metric_name} values found"}

    values = [float(v) for v in values]
    all_pass = all(v >= floor for v in values)
    points = 20 if all_pass else (10 if any(v >= floor for v in values) else 0)
    detail = f"{metric_name}s: {', '.join(f'{v:.3f}' for v in values)} (floor={floor})"
    return {"name": "metric_floor", "passed": all_pass, "points": points,
            "max_points": 20, "detail": detail}


# ──────────────────────────────────────────────────────
# Check 3: Feature Stability (15 points)
# Compares current top-N features against a saved baseline.
# First run creates the baseline. Subsequent runs flag drift.
# Adapt: change `max_changes` threshold and feature file format.
# ──────────────────────────────────────────────────────
def check_feature_stability(results_dir, baselines_dir, max_changes=3):
    baseline_file = baselines_dir / "feature_baseline.json"

    # Load current top features from CSV (one row per feature, ranked)
    current = {}
    for model_key, filename in [("primary", "feature_importance.csv")]:
        feat_file = results_dir / filename
        if not feat_file.exists():
            continue
        with open(feat_file) as f:
            reader = csv.DictReader(f)
            features = [row["feature"] for row in reader]
        current[model_key] = features[:10]

    if not current:
        return {"name": "feature_stability", "passed": False, "points": 0,
                "max_points": 15, "detail": "No feature importance files found"}

    # First run: create baseline and pass
    if not baseline_file.exists():
        baselines_dir.mkdir(parents=True, exist_ok=True)
        with open(baseline_file, "w") as f:
            json.dump(current, f, indent=2)
        return {"name": "feature_stability", "passed": True, "points": 15,
                "max_points": 15, "detail": "Baseline created (first run)"}

    # Compare against baseline
    with open(baseline_file) as f:
        baseline = json.load(f)

    changes = {}
    for model_key in current:
        if model_key not in baseline:
            changes[model_key] = len(current[model_key])
            continue
        new_features = set(current[model_key]) - set(baseline[model_key])
        changes[model_key] = len(new_features)

    total_changes = sum(changes.values())
    passed = total_changes <= max_changes
    points = 15 if passed else (7 if total_changes <= max_changes * 2 else 0)
    detail_parts = [f"{k}: {v} new" for k, v in changes.items()]
    detail = f"{total_changes} top-10 changes ({', '.join(detail_parts)})"
    return {"name": "feature_stability", "passed": passed, "points": points,
            "max_points": 15, "detail": detail}


# ──────────────────────────────────────────────────────
# Check 4: Score Distribution (15 points)
# Validates that predictions are numeric, in [0,1], no NaN,
# and have a non-extreme median.
# Adapt: change the scores file format and value range for
#        your domain (e.g., regression targets may not be [0,1]).
# ──────────────────────────────────────────────────────
def check_score_distribution(results_dir):
    scores_file = results_dir / "predictions.json"
    if not scores_file.exists():
        return {"name": "score_distribution", "passed": False, "points": 0,
                "max_points": 15, "detail": "predictions.json not found"}

    with open(scores_file) as f:
        data = json.load(f)

    probs = []
    issues = []
    for key, val in data.items():
        if isinstance(val, dict) and "prob" in val:
            p = val["prob"]
        elif isinstance(val, (int, float)):
            p = val
        else:
            continue

        if p is None:
            issues.append("null")
            continue
        if not isinstance(p, (int, float)):
            issues.append(f"non_numeric:{type(p).__name__}")
            continue
        if p != p:  # NaN check
            issues.append("NaN")
            continue
        if p < 0 or p > 1:
            issues.append(f"out_of_range:{p}")
        probs.append(p)

    if not probs:
        return {"name": "score_distribution", "passed": False, "points": 0,
                "max_points": 15, "detail": "No valid probability values found"}

    probs.sort()
    median = probs[len(probs) // 2]
    extreme = median < 0.01 or median > 0.99

    points = 15
    problems = []

    if issues:
        problems.append(f"{len(issues)} invalid values")
        points -= 5
    if extreme:
        problems.append(f"extreme median={median:.4f}")
        points -= 5
    out_of_range = [p for p in probs if p < 0 or p > 1]
    if out_of_range:
        problems.append(f"{len(out_of_range)} out of [0,1]")
        points -= 5

    points = max(0, points)
    passed = points >= 10
    detail = f"{len(probs)} scores, median={median:.4f}"
    if problems:
        detail += f" — issues: {', '.join(problems)}"

    return {"name": "score_distribution", "passed": passed, "points": points,
            "max_points": 15, "detail": detail}


# ──────────────────────────────────────────────────────
# Check 5: Coverage (10 points)
# Ensures the number of scored records hasn't drifted more
# than `tolerance` from the prior run.
# Adapt: change tolerance for your data volatility.
# ──────────────────────────────────────────────────────
def check_coverage(results_dir, tolerance=0.20):
    scores_file = results_dir / "predictions.json"
    refresh_file = results_dir / "last_refresh.json"

    if not scores_file.exists():
        return {"name": "coverage", "passed": False, "points": 0,
                "max_points": 10, "detail": "predictions.json not found"}

    with open(scores_file) as f:
        data = json.load(f)
    current_count = len(data)

    if not refresh_file.exists():
        return {"name": "coverage", "passed": True, "points": 10,
                "max_points": 10, "detail": f"{current_count} records (no prior baseline)"}

    with open(refresh_file) as f:
        refresh = json.load(f)

    prior_count = refresh.get("record_count")
    if prior_count is None:
        return {"name": "coverage", "passed": True, "points": 10,
                "max_points": 10, "detail": f"{current_count} records (no prior count)"}

    drift = abs(current_count - prior_count) / max(prior_count, 1)
    passed = drift <= tolerance
    points = 10 if passed else 0
    detail = f"{current_count} records (prior: {prior_count}, drift: {drift:.1%})"
    return {"name": "coverage", "passed": passed, "points": points,
            "max_points": 10, "detail": detail}


# ──────────────────────────────────────────────────────
# Check 6: Calibration (10 points)
# Verifies calibration multipliers/parameters are within
# reasonable bounds — catches runaway calibration.
# Adapt: change the file format and bounds for your domain.
# ──────────────────────────────────────────────────────
def check_calibration(results_dir, min_mult=0.02, max_mult=2.0):
    cal_file = results_dir / "calibration.json"
    if not cal_file.exists():
        # Calibration is optional — pass if not configured
        return {"name": "calibration", "passed": True, "points": 10,
                "max_points": 10, "detail": "No calibration file (skipped)"}

    with open(cal_file) as f:
        cal = json.load(f)

    out_of_bounds = []
    for section_key, section_val in cal.items():
        if isinstance(section_val, dict) and "multipliers" in section_val:
            for label, mult in section_val["multipliers"].items():
                if isinstance(mult, (int, float)) and (mult < min_mult or mult > max_mult):
                    out_of_bounds.append(f"{section_key}.{label}={mult}")

    passed = len(out_of_bounds) == 0
    points = 10 if passed else 0
    detail = "All multipliers in bounds" if passed else f"Out of bounds: {', '.join(out_of_bounds)}"
    return {"name": "calibration", "passed": passed, "points": points,
            "max_points": 10, "detail": detail}


# ──────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────
def run_all_evals(results_dir, baselines_dir):
    checks = [
        check_leakage_pass(results_dir),
        check_metric_floor(results_dir),
        check_feature_stability(results_dir, baselines_dir),
        check_score_distribution(results_dir),
        check_coverage(results_dir),
        check_calibration(results_dir),
    ]

    score = sum(c["points"] for c in checks)
    passed = score >= 70

    return {
        "score": score,
        "max_score": 100,
        "passed": passed,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="ML Pipeline Eval")
    parser.add_argument("--results", default=None, help="Path to results/ directory")
    parser.add_argument("--baselines", default=None, help="Path to baselines/ directory")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_dir = script_dir.parent
    results_dir = Path(args.results) if args.results else repo_dir / "results"
    baselines_dir = Path(args.baselines) if args.baselines else script_dir / "baselines"

    result = run_all_evals(results_dir, baselines_dir)

    # Write structured output
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / "eval_score.json"
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    status = "PASSED" if result["passed"] else "FAILED"
    print(f"ML Pipeline Eval: {status} ({result['score']}/{result['max_score']})")
    for c in result["checks"]:
        mark = "+" if c["passed"] else "X"
        print(f"  [{mark}] {c['name']}: {c['points']}/{c['max_points']} — {c['detail']}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
