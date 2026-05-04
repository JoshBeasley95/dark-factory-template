# Dark Factory Template — Project Instructions

## Overview

The Dark Factory is a pattern for building automated ML pipelines with built-in quality gates, eval-driven development, and AI-assisted workflows. It transforms raw data into scored predictions and stakeholder-ready dashboards with minimal human intervention.

Adapt this template to any domain: churn prediction, lead scoring, fraud detection, demand forecasting, recommendation systems, etc.

## File Map

### Pipeline Scripts (`src/`)
| Script | Purpose |
|--------|---------|
| `train_model.py` | Model training + feature importance + Gate 1 leakage checks |
| `score_pipeline.py` | Prediction scoring + aggregation into output summaries |
| `leakage_checks.py` | Automated leakage detection (reusable module) |
| `extract_data.py` | Data extraction + feature engineering |
| `refresh_scores.py` | End-to-end orchestration: 3 modes (full / score-only / skip-extract) |
| `generate_synthetic_data.py` | Demo data generation for testing |

### Tests & Evals (`tests/`)
| Script | Purpose |
|--------|---------|
| `eval_pipeline.py` | ML pipeline eval — 100-point scoring rubric across 6 checks |
| `eval_code_quality.py` | Syntax, secrets, import validation |
| `gate_review.py` | Unified review gate — consolidates all checks into PASS/FAIL |
| `test_*.py` | Unit tests (pytest) |

### Data & Results
- `data/` — Training and scoring datasets (gitignored)
- `results/` — Model artifacts, scores, eval outputs (gitignored)
- `tests/baselines/` — SHAP/feature baselines for stability checks

## Quality Gates

### Gate 1: Automated Checks (blocks delivery)
Four automated leakage checks in `leakage_checks.py`:
| Check | Trigger | Catches |
|---|---|---|
| Dominance | Top feature importance >3x runner-up | "Too good to be true" features |
| Scoring Variance | Feature variance <0.05 in scoring set | Point-in-time snapshot fields |
| Target Correlation | Single-feature AUC >0.90 | Outcome-encoding features |
| Distribution Shift | >80% gap in binary feature rates | Retroactive state changes |

### Gate 2: Human Feature Review (first delivery only)
Top 10 features reviewed once, approval persists. Subsequent runs auto-compare; new entries flagged.

### Pre-Delivery Gate
`tests/gate_review.py` consolidates:
- Code quality eval (syntax, secrets, imports)
- ML pipeline eval (100-point rubric)
- Unit tests (pytest)

All must pass before results reach stakeholders.

## Running the Pipeline

```bash
# Full retrain
python src/refresh_scores.py --mode full

# Score only (skip training)
python src/refresh_scores.py --mode score-only

# Development (from cached data)
python src/refresh_scores.py --mode skip-extract

# Generate synthetic data for testing
python src/generate_synthetic_data.py --deals 10000 --output data/
```

## Eval-Driven Development

The harness uses machine-readable evals instead of manual review:

1. **Code quality eval** — runs on every commit (pre-commit hook)
2. **ML pipeline eval** — 100-point rubric, runs after training
3. **Unit tests** — pytest suite for pipeline logic
4. **Unified gate** — combines all checks into single verdict

This enables autonomous AI coding loops: the agent runs code, checks evals, fixes issues, and iterates until all gates pass.

## Parallel vs Sequential Task Decomposition

**Safe to parallelize (independent):**
- Multiple model training (if models are independent after segmentation)
- ML pipeline evals + dashboard/UI tests
- Multi-panel dashboard development
- Documentation updates

**Must be sequential (dependencies):**
- Data extraction → feature engineering → training → scoring
- Training → feature importance → leakage checks
- Leakage checks → human feature review
- Score deployment → integration tests
- Any git operations — always sequential

## Skills (Slash Commands)

Three project-specific skills for repeatable workflows:

| Command | Purpose |
|---------|---------|
| `/project:refresh [mode]` | Run ML pipeline end-to-end with eval-gated deployment. Modes: `full`, `score-only`, `skip-extract` |
| `/project:smoke` | Run integration/smoke tests against deployed output |
| `/project:review` | Pre-commit review gate — runs applicable checks based on what changed |

Skills live in `.claude/skills/<name>/SKILL.md` and are auto-discovered by Claude Code.

### Loop Status

`.claude/loop-status.md` persists state across Claude Code sessions for iterative development. Read it at the start of each session, update it at the end. Three loop patterns: Feature Development, Pipeline Refresh, Harness Improvement.

## Coding Standards

- Pipeline scripts are standalone Python — no package manager beyond pip
- All results go to `results/` (gitignored)
- Data files go to `data/` (gitignored)
- Evals output structured JSON for machine consumption
- Gate verdicts include timestamps and check breakdowns
