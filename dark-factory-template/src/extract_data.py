#!/usr/bin/env python3
"""
Data Extraction + Feature Engineering
=======================================
Pulls raw data from your source system and engineers features
for model training and scoring.

Adapt this script to your data source:
  - Database queries (SQL, KQL, etc.)
  - API calls
  - File imports (CSV, Excel, Parquet)

Output:
  - data/training_data.csv — Historical labeled data
  - data/scoring_data.csv — Current unlabeled data for predictions
"""

import argparse
import sys
from pathlib import Path


def extract_training_data(output_dir):
    """Pull historical labeled data for model training.

    Replace this with your actual data extraction logic:
      - SQL query against your data warehouse
      - API call to your CRM/ERP
      - Read from cloud storage (S3, GCS, Azure Blob)
    """
    print("Extracting training data...")
    # TODO: Replace with your extraction logic
    # Example:
    #   df = pd.read_sql("SELECT * FROM deals WHERE closed_date IS NOT NULL", conn)
    #   df = engineer_features(df)
    #   df.to_csv(output_dir / "training_data.csv", index=False)
    print(f"  Output: {output_dir / 'training_data.csv'}")


def extract_scoring_data(output_dir):
    """Pull current unlabeled data for prediction scoring.

    Same source as training, but filtered to open/active records.
    """
    print("Extracting scoring data...")
    # TODO: Replace with your extraction logic
    # Example:
    #   df = pd.read_sql("SELECT * FROM deals WHERE status = 'Open'", conn)
    #   df = engineer_features(df)
    #   df.to_csv(output_dir / "scoring_data.csv", index=False)
    print(f"  Output: {output_dir / 'scoring_data.csv'}")


def engineer_features(df):
    """Transform raw data into model features.

    Common patterns:
      - Encode categoricals (label encoding, one-hot)
      - Compute time-based features (days since X, recency)
      - Aggregate related records (count of interactions, sum of amounts)
      - Normalize numeric ranges
      - Create composite scores from feature groups

    WARNING: Only use point-in-time data. Never include features that
    are set or modified after the prediction target is determined.
    See leakage_checks.py for automated detection.
    """
    # TODO: Replace with your feature engineering
    return df


def main():
    parser = argparse.ArgumentParser(description="Data Extraction")
    parser.add_argument("--output", default="data/", help="Output directory")
    parser.add_argument("--training-only", action="store_true")
    parser.add_argument("--scoring-only", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.scoring_only:
        extract_training_data(output_dir)
    if not args.training_only:
        extract_scoring_data(output_dir)

    print("Extraction complete.")


if __name__ == "__main__":
    main()
