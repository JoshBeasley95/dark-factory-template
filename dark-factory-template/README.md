# Dark Factory Template

An automated ML pipeline template with built-in quality gates, eval-driven development, and AI-assisted workflows.

## What Is This?

The Dark Factory pattern transforms raw data into scored predictions and stakeholder-ready output with minimal human intervention. It combines:

- **Automated quality gates** that catch data leakage and model degradation
- **Machine-readable evals** that enable AI coding agents to self-check
- **A recommendation engine** that maps model features to prescriptive actions
- **Three-layer testing** (invariants, browser harness, AI testing agent)

## Quick Start

```bash
# 1. Generate synthetic data
python src/generate_synthetic_data.py --records 10000 --output data/

# 2. Install the pre-commit hook
cp hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

# 3. Run the full pipeline (after implementing your model in train_model.py)
python src/refresh_scores.py --mode full

# 4. Run the quality gate standalone
python tests/gate_review.py --all
```

## Structure

```
dark-factory-template/
  CLAUDE.md                      # Project instructions for AI assistants
  src/
    extract_data.py              # Data extraction + feature engineering
    train_model.py               # Model training + Gate 1 leakage checks
    score_pipeline.py            # Prediction scoring + aggregation
    leakage_checks.py            # 4 automated leakage detection checks
    refresh_scores.py            # End-to-end orchestration (3 modes)
    generate_synthetic_data.py   # Demo data for testing
  tests/
    eval_pipeline.py             # ML pipeline eval (100-point rubric)
    eval_code_quality.py         # Syntax, secrets, import checks
    gate_review.py               # Unified PASS/FAIL review gate
    baselines/                   # Feature stability baselines (auto-created)
  docs/
    architecture-playbook.md     # Complete architecture reference
  hooks/
    pre-commit                   # Code quality check on every commit
  data/                          # Training + scoring data (gitignored)
  results/                       # Model artifacts + eval outputs (gitignored)
```

## How to Adapt

1. Replace `extract_data.py` with your data source logic
2. Replace `train_model.py` with your model training code
3. Wire up leakage checks to your feature importance output
4. Adjust eval thresholds in `eval_pipeline.py` for your domain
5. Build your recommendation map (feature → action text)

See `docs/architecture-playbook.md` for the full architecture reference.

## Quality Gates

| Gate | What | When |
|------|------|------|
| Pre-commit hook | Syntax, secrets, imports | Every commit |
| ML pipeline eval | 6-check 100-point rubric | After training |
| Unit tests | pytest suite | Before delivery |
| Unified review gate | All of the above | Before any stakeholder delivery |
