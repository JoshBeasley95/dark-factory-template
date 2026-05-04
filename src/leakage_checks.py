#!/usr/bin/env python3
"""
Automated Leakage Detection
=============================
Four checks that catch common data leakage patterns in ML pipelines.
Called from train_model.py after feature importance computation.

These checks are the backbone of Gate 1 — if any check fails,
the pipeline halts and results never reach stakeholders.

Checks:
  1. Dominance — Top feature importance >3x runner-up
  2. Scoring Variance — Feature has near-zero variance in scoring set
  3. Target Correlation — Single feature achieves AUC >0.90
  4. Distribution Shift — Binary feature rates differ >80% between classes

Each check returns: {"passed": bool, "details": str, "flagged_features": list}
"""


def check_dominance(importances, threshold=3.0):
    """A feature with >3x the importance of the runner-up is suspicious.

    This catches outcome-encoding features (e.g., a status field that
    directly encodes the target). These features dominate SHAP because
    they're essentially the answer key.

    Args:
        importances: list of (feature_name, importance_score), sorted descending
        threshold: ratio of #1 to #2 that triggers a flag
    """
    if len(importances) < 2:
        return {"passed": True, "details": "Not enough features to check", "flagged_features": []}

    top = importances[0]
    runner_up = importances[1]

    if runner_up[1] == 0:
        return {"passed": False, "details": f"Runner-up has zero importance",
                "flagged_features": [top[0]]}

    ratio = top[1] / runner_up[1]
    if ratio > threshold:
        return {"passed": False,
                "details": f"{top[0]} has {ratio:.1f}x the importance of {runner_up[0]}",
                "flagged_features": [top[0]]}

    return {"passed": True, "details": f"Top ratio: {ratio:.1f}x (threshold: {threshold}x)",
            "flagged_features": []}


def check_scoring_variance(feature_stats_training, feature_stats_scoring, min_iqr_ratio=0.05):
    """Features with near-zero variance in scoring but high variance in training
    are likely point-in-time snapshot fields or post-hoc calculations.

    Example: close_date_slip_days has IQR=5 in historical data (deals that
    closed had various slip amounts) but IQR=0 in open pipeline (no deal
    has slipped yet because they haven't closed).

    Args:
        feature_stats_training: dict of {feature: {"iqr": float}}
        feature_stats_scoring: dict of {feature: {"iqr": float}}
        min_iqr_ratio: scoring IQR / training IQR below this threshold flags
    """
    flagged = []
    for feature in feature_stats_scoring:
        if feature not in feature_stats_training:
            continue
        train_iqr = feature_stats_training[feature].get("iqr", 0)
        score_iqr = feature_stats_scoring[feature].get("iqr", 0)

        if train_iqr > 0 and (score_iqr / train_iqr) < min_iqr_ratio:
            flagged.append(feature)

    passed = len(flagged) == 0
    details = f"{len(flagged)} features with near-zero scoring variance" if flagged else "All features have adequate scoring variance"
    return {"passed": passed, "details": details, "flagged_features": flagged}


def check_target_correlation(feature_aucs, max_auc=0.90):
    """A single feature achieving AUC >0.90 is suspicious — it likely
    encodes the outcome directly or is derived from it.

    Example: Forecast_Category_enc achieves AUC=1.0 because Won deals
    literally have FC="Won".

    Args:
        feature_aucs: dict of {feature_name: auc_score}
        max_auc: AUC above this threshold triggers a flag
    """
    flagged = []
    for feature, auc in feature_aucs.items():
        if auc > max_auc:
            flagged.append(feature)

    passed = len(flagged) == 0
    if flagged:
        details = f"{len(flagged)} features exceed AUC {max_auc}: {', '.join(flagged)}"
    else:
        details = f"No features exceed AUC {max_auc}"
    return {"passed": passed, "details": details, "flagged_features": flagged}


def check_distribution_shift(feature_class_rates, max_gap=0.80):
    """Binary features with >80% relative gap in rates between positive
    and negative classes suggest retroactive state changes.

    Example: is_prospect shows 2.1% for Won (accounts flip to customer
    after winning) vs 41.6% for Lost (accounts stay as prospects). The
    95% relative gap means this field encodes outcome information.

    Args:
        feature_class_rates: dict of {feature: {"positive_rate": float, "negative_rate": float}}
        max_gap: relative gap threshold (|rate_pos - rate_neg| / max(rate_pos, rate_neg))
    """
    flagged = []
    for feature, rates in feature_class_rates.items():
        pos_rate = rates.get("positive_rate", 0)
        neg_rate = rates.get("negative_rate", 0)
        max_rate = max(pos_rate, neg_rate)

        if max_rate == 0:
            continue

        gap = abs(pos_rate - neg_rate) / max_rate
        if gap > max_gap:
            flagged.append(feature)

    passed = len(flagged) == 0
    details = f"{len(flagged)} features with >{ int(max_gap * 100)}% distribution shift" if flagged else "No significant distribution shifts"
    return {"passed": passed, "details": details, "flagged_features": flagged}


def run_all_checks(importances, feature_stats_training, feature_stats_scoring,
                   feature_aucs, feature_class_rates):
    """Run all 4 leakage checks and return consolidated result.

    Returns:
        {"passed": bool, "checks": [check_result, ...], "all_flagged": [feature_names]}
    """
    checks = [
        check_dominance(importances),
        check_scoring_variance(feature_stats_training, feature_stats_scoring),
        check_target_correlation(feature_aucs),
        check_distribution_shift(feature_class_rates),
    ]

    all_passed = all(c["passed"] for c in checks)
    all_flagged = []
    for c in checks:
        all_flagged.extend(c["flagged_features"])

    return {
        "passed": all_passed,
        "checks": checks,
        "all_flagged": list(set(all_flagged)),
    }
