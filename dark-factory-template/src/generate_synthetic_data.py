#!/usr/bin/env python3
"""
Synthetic Data Generator
=========================
Creates realistic-looking demo data for testing the pipeline
end-to-end without needing access to real data sources.

Adapt the feature distributions and target logic to match
your domain's characteristics.

Usage:
    python src/generate_synthetic_data.py --records 10000 --output data/
"""

import argparse
import csv
import random
from pathlib import Path


def generate_record(record_id):
    """Generate a single synthetic record.

    Replace with features relevant to your domain. The key requirement
    is that the target variable should have a realistic relationship
    with the features — pure random won't exercise leakage checks properly.
    """
    # Example features (replace with your domain)
    amount = random.lognormvariate(10, 1.5)  # Log-normal deal sizes
    age_days = random.randint(1, 365)
    engagement_score = random.uniform(0, 100)
    tier = random.choice(["enterprise", "mid_market", "smb"])
    region = random.choice(["north", "south", "east", "west"])
    category = random.choice(["new", "renewal", "expansion"])

    # Synthetic target with realistic feature relationships
    base_prob = 0.3
    if tier == "enterprise":
        base_prob += 0.15
    if engagement_score > 70:
        base_prob += 0.2
    if age_days > 180:
        base_prob -= 0.1
    if category == "renewal":
        base_prob += 0.25

    base_prob = max(0.05, min(0.95, base_prob))
    target = 1 if random.random() < base_prob else 0

    return {
        "record_id": f"REC-{record_id:06d}",
        "amount": round(amount, 2),
        "age_days": age_days,
        "engagement_score": round(engagement_score, 2),
        "tier": tier,
        "region": region,
        "category": category,
        "target": target,
    }


def main():
    parser = argparse.ArgumentParser(description="Synthetic Data Generator")
    parser.add_argument("--records", type=int, default=10000, help="Number of records")
    parser.add_argument("--output", default="data/", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate training data (labeled — historical records with known outcomes)
    training_records = [generate_record(i) for i in range(args.records)]
    training_path = output_dir / "training_data.csv"
    with open(training_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=training_records[0].keys())
        writer.writeheader()
        writer.writerows(training_records)

    won_count = sum(1 for r in training_records if r["target"] == 1)
    win_rate = won_count / len(training_records) * 100
    print(f"Training data: {len(training_records)} records, {win_rate:.1f}% win rate")
    print(f"  Saved to: {training_path}")

    # Generate scoring data (unlabeled — current open records)
    scoring_count = args.records // 4
    scoring_records = [generate_record(i + args.records) for i in range(scoring_count)]
    for r in scoring_records:
        del r["target"]  # Remove label — these are "open" records

    scoring_path = output_dir / "scoring_data.csv"
    with open(scoring_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=scoring_records[0].keys())
        writer.writeheader()
        writer.writerows(scoring_records)

    print(f"Scoring data: {len(scoring_records)} records (unlabeled)")
    print(f"  Saved to: {scoring_path}")


if __name__ == "__main__":
    main()
