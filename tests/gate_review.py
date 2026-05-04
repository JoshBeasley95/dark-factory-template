#!/usr/bin/env python3
"""
Unified Review Gate — Single Pass/Fail Decision
=================================================
Consolidates all quality checks into one structured verdict.
Runs the right checks based on what files changed.

This is the pre-delivery gate: nothing reaches stakeholders
unless this script exits 0.

Usage:
    python tests/gate_review.py [--all] [--ml] [--code] [--tests]

Without flags, auto-detects what changed via git diff.
With flags, runs the specified checks regardless of git state.

Output:
    results/gate_verdict.json — structured pass/fail with breakdown.
    Exit code 0 = PASS, exit code 1 = FAIL.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_DIR / "results"


def detect_changes():
    """Detect what categories of files changed (staged + unstaged)."""
    categories = {"python": False, "tests": False, "docs": False}

    for diff_cmd in [["git", "diff", "--name-only"], ["git", "diff", "--cached", "--name-only"]]:
        try:
            result = subprocess.run(diff_cmd, capture_output=True, text=True, cwd=REPO_DIR)
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                if line.startswith("src/") and line.endswith(".py"):
                    categories["python"] = True
                elif line.startswith("tests/"):
                    categories["tests"] = True
                elif line.startswith("docs/"):
                    categories["docs"] = True
        except FileNotFoundError:
            pass

    return categories


def run_code_quality():
    """Run code quality checks."""
    script = REPO_DIR / "tests" / "eval_code_quality.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=REPO_DIR
    )
    passed = result.returncode == 0
    issues = 0
    for line in result.stdout.split("\n"):
        if "issues" in line and ":" in line:
            parts = line.split(":")
            for part in parts:
                part = part.strip()
                if part.endswith(" issues"):
                    try:
                        issues += int(part.split()[0])
                    except ValueError:
                        pass
    return {
        "check": "code_quality",
        "passed": passed,
        "issues": issues,
        "output": result.stdout.strip(),
    }


def run_ml_assessment():
    """Run ML pipeline assessment."""
    script = REPO_DIR / "tests" / "eval_pipeline.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=REPO_DIR
    )
    score_file = RESULTS_DIR / "eval_score.json"
    score = 0
    passed = False
    if score_file.exists():
        with open(score_file) as f:
            data = json.load(f)
        score = data.get("score", 0)
        passed = data.get("passed", False)
    return {
        "check": "ml_assessment",
        "passed": passed,
        "score": score,
        "max_score": 100,
        "output": result.stdout.strip(),
    }


def run_pytest():
    """Run pytest if test files exist."""
    test_files = list((REPO_DIR / "tests").glob("test_*.py"))
    if not test_files:
        return {
            "check": "unit_tests",
            "passed": True,
            "passed_count": 0,
            "failed_count": 0,
            "output": "No test_*.py files found — skipped",
            "skipped": True,
        }

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=REPO_DIR
    )
    passed_count = 0
    failed_count = 0
    output_text = result.stdout + result.stderr
    for line in output_text.split("\n"):
        parts = line.split()
        for i, part in enumerate(parts):
            if part == "passed" and i > 0:
                try:
                    passed_count = int(parts[i - 1])
                except ValueError:
                    pass
            if part == "failed" and i > 0:
                try:
                    failed_count = int(parts[i - 1])
                except ValueError:
                    pass

    return {
        "check": "unit_tests",
        "passed": result.returncode == 0,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "output": result.stdout.strip()[-500:],
    }


def main():
    parser = argparse.ArgumentParser(description="Unified Review Gate")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--ml", action="store_true", help="Run ML assessment")
    parser.add_argument("--code", action="store_true", help="Run code quality")
    parser.add_argument("--tests", action="store_true", help="Run pytest")
    args = parser.parse_args()

    if args.all:
        run_checks = {"code": True, "ml": True, "tests": True}
    elif any([args.ml, args.code, args.tests]):
        run_checks = {"code": args.code, "ml": args.ml, "tests": args.tests}
    else:
        changes = detect_changes()
        run_checks = {
            "code": True,  # Always run code quality
            "ml": changes["python"],
            "tests": changes["python"] or changes["tests"],
        }

    results = {}
    if run_checks.get("code"):
        results["code_quality"] = run_code_quality()
    if run_checks.get("ml"):
        results["ml_assessment"] = run_ml_assessment()
    if run_checks.get("tests"):
        results["unit_tests"] = run_pytest()

    all_passed = all(r["passed"] for r in results.values())

    verdict = {
        "gate": "pre-delivery",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": "PASS" if all_passed else "FAIL",
        "checks": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    verdict_file = RESULTS_DIR / "gate_verdict.json"
    with open(verdict_file, "w") as f:
        json.dump(verdict, f, indent=2)

    print(f"Review Gate: {'PASS' if all_passed else 'FAIL'}")
    for name, check in results.items():
        mark = "+" if check["passed"] else "X"
        if name == "ml_assessment":
            detail = f"score: {check.get('score', '?')}/{check.get('max_score', '?')}"
        elif name == "unit_tests":
            if check.get("skipped"):
                detail = "skipped (no test files)"
            else:
                detail = f"{check.get('passed_count', 0)} passed, {check.get('failed_count', 0)} failed"
        elif name == "code_quality":
            detail = f"{check.get('issues', 0)} issues"
        else:
            detail = ""
        print(f"  [{mark}] {name}: {detail}")

    if not all_passed:
        print("\nBlocking issues:")
        for name, check in results.items():
            if not check["passed"]:
                print(f"  {name}: {check.get('output', '')[:200]}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
