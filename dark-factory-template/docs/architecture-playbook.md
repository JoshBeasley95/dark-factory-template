# Dark Factory Architecture Playbook

A complete reference for building automated ML pipelines with built-in quality gates, eval-driven development, and AI-assisted workflows. This playbook captures the patterns — apply them to any domain.

---

## Table of Contents

1. [The Core Idea](#1-the-core-idea)
2. [The Automated Flow](#2-the-automated-flow)
3. [Two-Gate Quality System](#3-two-gate-quality-system)
4. [Recommendation Engine](#4-recommendation-engine)
5. [Three-Layer Testing Model](#5-three-layer-testing-model)
6. [Eval-Driven Development Harness](#6-eval-driven-development-harness)
7. [Build Order (7 Phases)](#7-build-order-7-phases)
8. [Productization Lessons](#8-productization-lessons)
9. [Applying to New Domains](#9-applying-to-new-domains)

---

## 1. The Core Idea

Most ML projects stop at "model predicts things." The Dark Factory extends the pipeline all the way to stakeholder-ready output:

```
Raw Data → Feature Engineering → Model Training → Predictions → Recommendations → Dashboard
```

The key insight: **predictions without recommendations leave a prescriptive gap.** Stakeholders don't want probabilities — they want to know what to do. The recommendation engine closes that gap by mapping model features to actionable next steps.

The second key insight: **quality gates make autonomous operation possible.** When you can machine-verify that outputs are correct, you can let AI coding agents iterate without human review at every step. The human reviews the finished product, not the process.

---

## 2. The Automated Flow

```
Business Question
    → Query Data (extract from source systems)
    → Analysis (feature engineering + model training)
    → Dashboard (visualization + interactive exploration)
    → Predictions (scored records with confidence + explainability)
    → Recommendations (prescriptive actions per record)
```

Each step produces machine-readable artifacts that the next step consumes. This is what makes the pipeline automatable — there are no "look at this and decide" steps until the final human review.

### Pipeline Orchestration

Three modes for different cadences:

| Mode | When | What Runs |
|------|------|-----------|
| `full` | Monthly or on schema changes | Extract + Train + Score |
| `score-only` | Weekly | Score with existing model |
| `skip-extract` | Development | Train + Score from cached data |

The orchestrator (`refresh_scores.py`) runs the appropriate steps and finishes with the quality gate. If the gate fails, results are not marked as ready for delivery.

---

## 3. Two-Gate Quality System

Quality gates are the backbone. They catch problems early and make autonomous operation safe.

### Gate 1: Automated Leakage Checks (blocks delivery)

Four checks run after feature importance computation. If any fails, the pipeline halts.

| Check | What It Catches | How |
|-------|----------------|-----|
| **Dominance** | Features that are "too good to be true" | Top feature importance > 3x the runner-up |
| **Scoring Variance** | Point-in-time snapshot fields that are constant for open records | Feature IQR ratio (scoring / training) < 0.05 |
| **Target Correlation** | Features that directly encode the outcome | Single-feature AUC > 0.90 |
| **Distribution Shift** | Retroactive state changes (field value changes after outcome) | Binary feature rate gap > 80% between positive/negative classes |

**Why these four?** They cover the most common leakage patterns in production ML:

1. **Outcome-encoded features** — A field like "status=Won" achieves AUC=1.0. Target Correlation catches it.
2. **Post-hoc fields** — Set after the outcome is determined, only useful in hindsight. Scoring Variance catches them (zero variance in open records).
3. **Retroactive snapshots** — Current state, not state-at-prediction-time. Distribution Shift catches the asymmetry (e.g., "is_active" is 98% for positive outcomes because activity is a consequence, not a cause).
4. **One-feature models** — If one feature does all the work, the model is fragile and likely leaky. Dominance flags it.

### Gate 2: Human Feature Review (first delivery only)

After Gate 1 passes, the top 10 features are presented for human review. Some leakage requires domain knowledge — a machine can't know that "days_since_last_purchase" is backfilled retroactively in your system.

**One-time cost:** Review the top 10 once and approve. Save approvals to a config file. On subsequent runs, the system auto-compares the current top 10 against the approved list. If a new feature enters, it's flagged for review. Stable top 10 = hands-free operation.

**Why top 10 only?** Leakage concentrates at the top of the feature importance ranking. Features ranked #30+ have negligible impact even if technically leaky.

### Unified Review Gate

The pre-delivery gate consolidates all checks:

```
Code Quality (syntax, secrets, imports)
  + ML Pipeline Eval (100-point rubric)
  + Unit Tests (pytest)
  = Single PASS/FAIL verdict (gate_verdict.json)
```

The verdict is a structured JSON file with timestamps, scores, and per-check breakdowns. This makes it machine-readable — AI agents can parse the verdict and decide what to fix.

---

## 4. Recommendation Engine

Three tiers, from simple to sophisticated. Build them in order — each tier is independently useful.

### Tier 1: Rule-Based Recommendations

Deterministic rules that map aggregated signals to actions.

| Component | Description |
|-----------|-------------|
| **Signal** | What data point triggers the rule (e.g., "stale committed deals") |
| **Condition** | Threshold or filter (e.g., committed deals older than 90 days) |
| **Template** | Action text with variable placeholders (e.g., "Initiate review — {N} deals open {X}+ days") |
| **Scope** | Who the recommendation targets (org, team, individual) |
| **Priority** | Ordering for display |

Adding a new recommendation = adding a row to the rule table. No code changes to the rendering logic.

Cap at 5 recommendations per view to avoid overwhelming stakeholders.

### Tier 2: Feature-Importance-Driven Recommendations

Map individual feature contributions (e.g., SHAP values) to prescriptive actions per record. This is where predictions become truly actionable.

**Architecture:**

```
Per-record SHAP values (top 5 features driving each prediction)
    → Feature-to-action mapping (domain-specific lookup table)
    → Model-aware text (different actions for different model types)
    → Value-aware templates (include actual feature values)
    → Rendered as bullet list per record
```

**Feature-to-action mapping structure:**

```javascript
{
  "feature_name": {
    "neg": {  // Feature is hurting this prediction
      "model_a": "Observation → recommended action for model A context",
      "model_b": "Observation → recommended action for model B context"
    },
    "pos": {  // Feature is helping this prediction
      "model_a": "Observation → recommended action for model A context",
      "model_b": "Observation → recommended action for model B context"
    }
  }
}
```

**Key design decisions:**

- **Model-aware text:** Different model types need different actions. A churn model and an upsell model might share features but the recommended actions are opposite.
- **Value placeholders:** `{v}` gets replaced with the actual feature value, formatted appropriately (percentages, currencies, counts). "Engagement score at {v}" → "Engagement score at 73%".
- **Context placeholders:** `{account}`, `{region}`, `{owner}` get replaced with record-level metadata.
- **Observation → Action format:** Each recommendation starts with what the model sees, then what to do about it. This builds trust — stakeholders understand WHY the recommendation exists.
- **Skip dominant features:** If the top feature is >3x the next, skip it — it's probably a segment indicator, not actionable.
- **Cap at 3 actions per record:** More than 3 overwhelms. Pick the top 3 non-marketing, model-relevant features.

**Value formatting:**
Create a formatter lookup per feature to control how values display:
- Rates/percentages: `"87%"` not `"0.87"`
- Currency amounts: `"$125K"` not `"125000"`
- Counts: `"1,200"` not `"1200.0"`
- Missing/zero: `"0% (missing)"` not `"0"`

### Tier 3: Gap-to-Plan Recommendations

Combine predictions with targets to generate gap-aware prescriptive actions.

```
Plan Target (by segment)
  - Expected Revenue (high-confidence predictions)
  = Revenue Gap

Gap Closers = records in the "swing zone" (25-75% probability),
              sorted by Expected Value (probability x amount),
              stacked until cumulative EV >= gap
```

Each gap closer record shows:
- Amount and probability
- Top SHAP features (why this record is worth pursuing)
- Mapped action (what to do about it)

**Swing deal framework:**
- **Likely wins (>75%)** — Close regardless, low intervention value
- **Swing zone (25-75%)** — Intervention changes outcomes, highest ROI
- **Long shots (<25%)** — Effort rarely changes result

Focus recommendations on swing zone records. This is where the recommendation engine has the highest impact.

### Tier 4: Full External Integration

Auto-pull plan targets, customer health scores, competitive intelligence from external systems. Combine with model predictions for fully automated "here's your gap, here's how to close it" reports.

---

## 5. Three-Layer Testing Model

Inspired by autonomous software factories: coding agents build software, testing agents validate it, they loop until quality is met, then humans review the finished product.

### Layer 1: DOM/State Invariant Checks (self-check)

Internal validation that runs after every render or state change. Catches mechanical bugs instantly.

Example invariants for a dashboard:
- No stale messages coexisting with visible content
- Disabled controls have no effect on rendered data
- Every visible table has data rows OR a no-data message, never neither
- State reset produces identical output to initial load

These run inside the application itself — zero external dependencies.

### Layer 2: Automated Browser/Integration Harness

Scripted tests that exercise the application through its UI or API. Iterates through inputs, states, and edge cases. Asserts:
- No runtime errors
- No orphaned UI elements
- No state leaks across interactions
- Outputs match expected values

For dashboards: Playwright or Selenium scripts. For APIs: pytest with HTTP client. For CLI tools: subprocess-based integration tests.

### Layer 3: AI Testing Agent

An LLM agent that uses the application as a stakeholder would and **interprets** what it sees — not just mechanical assertions but semantic checks:

- "Does this chart make sense given the filter I applied?"
- "Do the numbers in the summary match the detail table?"
- "Would a VP reviewing this find anything confusing or contradictory?"

The AI testing agent reports issues in natural language back to the coding agent, which fixes them and re-runs. This loop continues until the testing agent reports clean.

**The testing agent catches what scripts can't:**
- Contextual inconsistencies (numbers that are technically correct but misleading)
- UX problems (confusing layout, unclear labels)
- Cross-panel coherence (summary doesn't match detail)

### Feedback Loop

```
Coding Agent builds/modifies the application
    → Layer 1: Internal invariants (instant, catches crashes)
    → Layer 2: Automated harness (minutes, catches regressions)
    → Layer 3: AI testing agent (minutes, catches semantic issues)
    → If issues found: Coding Agent fixes, re-runs from Layer 1
    → If clean: Human reviews finished product
```

---

## 6. Eval-Driven Development Harness

The harness is what turns "AI helps me code faster" into "small autonomous software factory."

### Core Principle

Replace manual review with machine-readable evals. When an AI coding agent can:
1. Run code
2. Check evals
3. Parse structured verdicts
4. Fix issues
5. Repeat until all gates pass

...then it can operate autonomously within the quality boundaries you've defined.

### The 100-Point Rubric

The ML pipeline eval scores outputs on a 100-point scale:

| Check | Points | What It Validates |
|-------|--------|-------------------|
| Leakage Detection | 30 | No data leakage in model |
| Metric Floor | 20 | Model performance meets minimum threshold |
| Feature Stability | 15 | Top features haven't drifted from baseline |
| Score Distribution | 15 | Predictions are numeric, bounded, non-degenerate |
| Coverage | 10 | Record count within tolerance of prior run |
| Calibration | 10 | Calibration parameters within bounds |

**Pass threshold: 70/100.** This means the model can lose some points on stability or calibration but still ship — only critical issues (leakage, metric failure) are truly blocking.

**Why a rubric, not pass/fail?** A score provides gradient. An agent that improves from 45 to 65 knows it's making progress. Pure pass/fail gives no signal about direction.

### Structured Output

Every eval produces structured JSON:

```json
{
  "score": 85,
  "max_score": 100,
  "passed": true,
  "checks": [
    {
      "name": "leakage_pass",
      "passed": true,
      "points": 30,
      "max_points": 30,
      "detail": "2 models passed leakage checks"
    }
  ]
}
```

AI agents parse this directly. No log scraping, no regex on human-readable output.

### Pre-Commit Hook

The fastest check (code quality) runs on every commit:
- Syntax errors → blocked
- Hardcoded secrets → blocked
- Broken imports → blocked

This is 1-2 seconds. ML evals and tests are too slow for pre-commit — they run in the review gate.

---

## 7. Build Order (7 Phases)

Build in this order. Each phase is independently valuable. Phases 0-2 are the Minimum Viable Harness (~4-5 hours).

### Phase 0: Foundation
- Create CLAUDE.md (or equivalent project instructions)
- Initial repo structure and git init
- Document file map, coding standards, quality gate design

**Value:** Session memory. Every AI conversation starts with context.

### Phase 1: Eval Scripts
- `eval_pipeline.py` — 100-point ML rubric
- `eval_code_quality.py` — syntax, secrets, imports

**Value:** Quality is machine-readable. AI agents can self-check.

### Phase 2: AI Skills/Commands
- Repeatable workflows as named commands (e.g., `/refresh`, `/smoke-test`, `/review`)
- Each skill encapsulates a multi-step workflow into a single invocation

**Value:** Workflows are repeatable. New sessions inherit process knowledge.

### Phase 3: Cross-Session Persistence
- Status file tracking what's been done, what's next, what's blocked
- Updated at the end of each AI session

**Value:** Multi-session continuity. Work doesn't reset between conversations.

### Phase 4: Unit Tests
- pytest suite for pipeline logic (leakage checks, scoring, data transforms)

**Value:** Regression safety. Changes don't silently break existing behavior.

### Phase 5: Parallel Agent Patterns
- Document which tasks can run in parallel vs. must be sequential
- Define independent deliverables for multi-agent decomposition

**Value:** Speed. Independent tasks run concurrently.

### Phase 6: Unified Review Gate
- `gate_review.py` — consolidates code quality + ML eval + tests into single verdict
- Auto-detects what changed to run the right checks

**Value:** Single command to verify everything. Blocks delivery on failure.

### Phase 7: Pre-Commit Hook
- Code quality eval on every commit (fast check only)

**Value:** Catches trivial issues before they enter the codebase.

---

## 8. Productization Lessons

Patterns discovered while building production ML pipelines. Generic versions — apply to any domain.

### Data Leakage Patterns

| Pattern | Example | Detection |
|---------|---------|-----------|
| **Outcome-encoded features** | Status field that literally contains the target value | Target Correlation check (single-feature AUC > 0.90) |
| **Post-hoc fields** | Set after outcome is determined, not available at prediction time | Scoring Variance check (zero variance in open records) |
| **Outcome-dependent calculations** | Metrics computed from the outcome (e.g., "days to resolution" is null for open cases) | Scoring Variance check |
| **Point-in-time snapshots** | Current state, not state at prediction time. Positive outcomes retroactively change the field | Distribution Shift check (asymmetric rates) |
| **Retroactive timestamps** | "Last modified" is always recent for positive outcomes because the outcome event modifies the record | Distribution Shift check |
| **Useless-for-scoring features** | Powerful historical discriminator but constant for all open records | Scoring Variance check |

### Data Quality Patterns

| Pattern | Solution |
|---------|----------|
| **Extreme outliers** in numeric fields | Tree-based models handle outliers well, but outliers cause false positives in variance-based leakage checks. Use IQR-based comparisons. |
| **Column naming inconsistencies** between sources | Flexible lookup: `col = "Name A" if "Name A" in df.columns else "Name_A"`. Better: standardize at extraction time. |
| **Timezone-aware vs naive datetimes** | Convert all dates at extraction: `pd.to_datetime(col, utc=True).dt.tz_localize(None)` |
| **Mixed types from Excel imports** | `pd.to_numeric(col, errors="coerce")` before any aggregation |
| **Lambda aggregation failures** in groupby | Pre-compute flag columns before groupby. Avoid lambdas. |

### Architecture Patterns

| Pattern | Solution |
|---------|----------|
| **Mixed populations in one model** | Segment into separate models (e.g., new vs. returning customers). Different populations have different feature dynamics. |
| **Using snapshot fields for segmentation** | Use historical logic instead (e.g., "first purchase" not "current customer status"). Snapshot fields encode outcomes. |
| **Feature coverage varies by segment** | Drop feature groups with <20% non-zero coverage for a segment. Low-coverage features add noise. |
| **Source system changes granularity** | Validate feature cardinality matches between training and scoring sets when source systems change. |

### Signal Quality

| Pattern | Solution |
|---------|----------|
| **High-touch/spray channels are noise** | Weight attendance-based signals (events, meetings) over passive signals (page views, downloads). |
| **Upstream vs. downstream signal** | Some features drive top-of-funnel (lead generation) but don't differentiate outcomes once in-pipeline. Accept this — build separate models for generation vs. conversion. |
| **Low external data coverage** | Include external features but note coverage limitations. The model will learn to weight them appropriately for covered records. |

---

## 9. Applying to New Domains

### Step 1: Define Your Pipeline

Map your domain to the flow:

| Step | Example: Churn | Example: Fraud | Example: Demand |
|------|---------------|----------------|-----------------|
| Data Source | CRM + usage logs | Transaction DB | Sales history + external |
| Features | Engagement, support tickets, contract age | Amount, velocity, location, device | Seasonality, price, promotions |
| Target | Churned (Y/N) | Fraudulent (Y/N) | Units sold (continuous) |
| Recommendation | Retention action | Investigation priority | Reorder suggestion |

### Step 2: Adapt the Evals

1. **Leakage checks** — Same four checks work for any binary classification. For regression, replace Target Correlation (AUC) with Target Correlation (R-squared of single feature).
2. **Metric floor** — Set threshold for your metric (AUC, RMSE, F1, MAP@K).
3. **Feature stability** — Works as-is for any model with feature importance.
4. **Score distribution** — Adjust bounds for your prediction range (not always [0,1]).
5. **Coverage** — Set tolerance based on your data volatility.

### Step 3: Build the Recommendation Map

For each important feature in your model:
1. What does a negative contribution mean in plain language?
2. What should the stakeholder DO about it?
3. Does the action differ by segment/model type?

Write these as observation-action pairs:
```
"Feature X at {value} → Recommended action based on this signal"
```

### Step 4: Set Up the Harness

Follow the 7-phase build order. Start with Phase 0-2 (Minimum Viable Harness):
1. Write your CLAUDE.md with project context
2. Create eval scripts adapted to your domain
3. Define repeatable workflows as skills/commands

### Step 5: Iterate

The Dark Factory is never "done." It's a flywheel:
- Model retrains catch concept drift
- Evals catch quality regressions
- Feature review catches new leakage patterns
- Recommendation refinement improves stakeholder actions
- Each iteration is safer than the last because the gates accumulate knowledge

---

## Appendix: Key Design Principles

1. **Machine-readable over human-readable.** Structured JSON verdicts, not log files. AI agents parse JSON; they struggle with natural language logs.

2. **Gates, not guidelines.** A gate blocks delivery. A guideline is ignored under pressure. Make quality non-negotiable by making it automated.

3. **Observation → Action format.** Every recommendation starts with what the model sees (builds trust) and ends with what to do (delivers value).

4. **Progressive fallback.** When the best data isn't available, fall back gracefully: ML score → historical rate → rule-based default. Never show "no recommendation."

5. **Point-in-time discipline.** Every feature must represent the state at prediction time, not current state. Retroactive fields are the #1 source of leakage.

6. **Segment before modeling.** Different populations need different models. One model averaging across segments produces mediocre results for everyone.

7. **Build for the loop, not the run.** The pipeline will run hundreds of times. Invest in automation, evals, and gates — they compound. Manual steps don't.
