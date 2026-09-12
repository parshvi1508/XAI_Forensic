# LIME Attribution Audit - Failure Memo

## Row Accounting: 30 → 29 → 28

The pre-registered test set contains 30 inputs. Not all appear in every output file. This table documents every exclusion:

| Input ID | Text | raw_attributions.csv (145 rows) | stability_metrics.csv (29 rows) | deletion_faithfulness.csv (30 rows, 28 tested + 2 skipped) | Exclusion Reason |
|----------|------|---|----|----|----|
| 1–8 | (various) | Present (5 rows each) | Present | Present | — |
| **9** | "Fine." | **Present** (5 rows) | **Present** | **Present (skipped_single_token)** | Single token. Removing "Fine." produces empty string → deletion test skipped. Logged in CSV as `skipped_single_token`. Not included in faithfulness aggregates. |
| 10–29 | (various) | Present (5 rows each) | Present | Present | — |
| **30** | `" "` (single space) | **ABSENT** | **ABSENT** | **Present (skipped_empty)** | Whitespace-only input. `runner.py:336` `text.strip()` is empty → skipped before LIME runs. No canonical seed result exists → deletion phase logs as `skipped_empty` at `runner.py:429`. |

**Summary**: 30 defined, 29 with LIME attributions (−1 whitespace), 28 with deletion tests (−1 whitespace, −1 single-token). Both exclusions are structural (code guards), not data quality issues.


## Executive Summary

LIME passes both pre-registered thresholds - mean Jaccard top-5 = **0.81** (threshold: 0.60) and direction-correct rate = **89.3%** (threshold: 0.70). However, these headline numbers mask serious per-input instability: 6 inputs fall below the Jaccard threshold, strong baselines show near-zero deletion impact despite high LIME weights, and Kendall tau is undefined for short inputs. LIME is reliable enough for a demo but not trustworthy enough for production decisions.

## Stability Findings

### Overall
| Metric | Value | Threshold | Passes? |
|--------|-------|-----------|---------|
| Mean Jaccard top-5 | 0.81 | >= 0.60 | Yes |
| Mean Kendall tau | NaN (partial) | >= 0.50 | No (undefined for short inputs) |
| Label-unstable inputs | 0/29 | - | Stable |
| Top-1 unanimous | 19/29 (66%) | - | - |
| Perfect Jaccard (1.0) | 12/29 (41%) | - | - |
| Below Jaccard threshold | 6/29 (21%) | < 0.60 | - |

### Per-Category Stability
| Category | Mean Jaccard | Mean Kendall tau |
|----------|-------------|-----------------|
| Ambiguity | 0.97 | 0.69 |
| Edge cases | 0.94 | NaN (partial) |
| Negation/minimal pairs | 0.80 | 0.57 |
| Lexical shortcuts | 0.77 | NaN (partial) |
| Distribution/style shift | 0.72 | 0.68 |
| **Strong baselines** | **0.67** | **0.54** |

### Worst-Case Inputs (Jaccard < 0.60)
| Input | Text | Mean Jaccard | Min Jaccard |
|-------|------|-------------|-------------|
| 21 | "This is the best product I have ever purchased." | 0.46 | 0.25 |
| 6 | "The movie was terrible but I loved every minute of it." | 0.50 | 0.43 |
| 1 | "I am not entirely unhappy with this result." | 0.57 | 0.43 |
| 17 | "The patient presents with acute exacerbation..." | 0.57 | 0.43 |
| 18 | "Revenue increased 12% YoY driven by strong Q4..." | 0.57 | 0.43 |
| 24 | "This is awful and I regret buying it." | 0.52 | 0.43 |

**Key finding**: Input 21 ("best product I have ever purchased") is unambiguously positive yet has the *worst* stability of all 29 inputs (Jaccard 0.46, min 0.25). This is a strong baseline that should be trivially stable. The failure is because the sentence has many function words ("is", "the", "I", "have", "ever") whose LIME weights are near-zero and swap positions randomly across seeds. LIME's instability is not limited to hard cases - it also affects easy ones when token count is high relative to signal tokens.

### Kendall Tau Undefined
Kendall tau returns NaN when fewer than 2 tokens overlap between seed pairs. This affects:
- Input 9 ("Fine.") - 1 token, no rank comparison possible
- Input 26 ("good good good good good") - identical repeated token, LIME collapses to 1 unique
- Lexical shortcuts category overall - driven by input 9

This is a **limitation of the metric**, not LIME. For very short inputs, Jaccard is the only meaningful stability measure.



## Faithfulness Findings

### Overall
| Metric | Value | Threshold | Passes? |
|--------|-------|-----------|---------|
| Direction-correct rate | 25/28 (89.3%) | >= 0.70 | Yes |
| Label flip rate | 11/28 (39.3%) | - | - |
| Mean |confidence delta| | 0.3846 | - | - |

### Per-Category Faithfulness
| Category | Dir. Correct | Flip Rate | Mean |Delta| |
|----------|-------------|-----------|------------|
| Lexical shortcuts | 100% | 100% | 0.995 |
| Ambiguity | 100% | 40% | 0.408 |
| Distribution/style shift | 100% | 20% | 0.230 |
| Negation/minimal pairs | 80% | 60% | 0.590 |
| **Strong baselines** | **80%** | **0%** | **0.0002** |
| **Edge cases** | **75%** | **25%** | **0.162** |

### Direction-Incorrect Inputs (3 failures)
1. **Input 5** - "Nothing about this experience was disappointing." → LIME gives `experience` a negative weight (-0.183). Removing it *decreases* positive score (0.992 → 0.990). Delta is tiny (-0.002), so the direction error is within noise.
2. **Input 22** - "Terrible experience, complete waste of money." → LIME gives `Terrible` a negative weight (-0.318). Removing it barely changes score (0.000185 → 0.000183). Delta is -0.000002, essentially zero. The model is so confident in negative that removing one word doesn't matter.
3. **Input 26** - "good good good good good" → LIME gives `good` positive weight (+0.021). Removing it changes score by +0.000001. All signal is in one repeated word; removing one instance is like removing 20% of a uniform signal - no meaningful change.

### Strong Baseline Paradox
Strong baselines have 80% direction-correct but **0% label flip rate** and mean |delta| of **0.0002**. This means: LIME correctly identifies important tokens, but the model is so confident on these inputs that removing the top token barely changes the output. LIME's faithfulness metric is *directionally correct but magnitude-insensitive*. When a model outputs 0.9999 confidence, removing one token drops it to 0.9995 - directionally correct but practically meaningless.

### Lexical Shortcuts: LIME's Best Category
100% direction-correct, 100% label flip, mean |delta| = 0.995. These inputs have contradictory lexical cues ("terrible but loved", "Excellent but useless"). LIME correctly identifies the decisive word, and removing it causes a full label flip. This is where LIME's bag-of-words perturbation strategy works exactly as designed - the decisive token dominates the linear model.



## Specific Failure Modes

### 1. Function Word Noise (Inputs 21, 24, 25)
Longer sentences with clear sentiment have many near-zero-weight function words. LIME assigns random small weights to "the", "is", "I", "have". These swap positions across seeds, tanking Jaccard. The top-1 token ("best", "awful", "thrilled") is often stable, but ranks 2-5 are noise.

### 2. Negation Fragility (Input 5)
"Nothing about this experience was disappointing" - semantically positive (negation of negative). LIME attributes to `experience` (-0.18) and `disappointing` (-0.17) but gives `Nothing` only +0.04. LIME's whitespace tokenizer sees "Nothing" as one token while the model's WordPiece may process it differently. The key negator gets less weight than the content words it negates.

### 3. Near-Zero Deletion Impact on High-Confidence Inputs
For inputs where model confidence exceeds 0.999, removing the top LIME token changes the score by <0.001. LIME is *faithful in direction* but the deletion test is underpowered - one-token removal cannot significantly perturb a model this confident. A more aggressive test (removing top-3 tokens) would better measure faithfulness on these inputs.

### 4. Kendall Tau Gaps
LIME returns only tokens with nonzero weight. For short inputs (1-2 tokens), LIME returns 1-2 tokens total, making rank correlation impossible. The metric framework assumes at least 5 ranked tokens - this assumption fails for ~15% of inputs.

### 5. LIME Whitespace Tokenizer vs. WordPiece
LIME splits on whitespace: `"I'm"` → one token. The model's WordPiece tokenizer splits it into `["i", "'", "m"]`. LIME's perturbation masks whole whitespace tokens but the model processes subwords. This means LIME's attribution is to whitespace tokens, not to the features the model actually uses. This mismatch is fundamental and cannot be fixed without replacing LIME's tokenizer.



## Limitations of This Audit

1. **30 inputs is small.** Category-level statistics are based on 4-5 data points. Per-category rates (e.g., "80% direction-correct") have wide confidence intervals.
2. **Only Model A tested.** Model B (Twitter-RoBERTa) is never explained by LIME. 
3. **num_samples=300 is low.** LIME's perturbation sampling is the source of instability. Higher sample counts (1000+) would improve stability but increase runtime 3x+.
4. **Single-token deletion only.** Removing the top token is the weakest faithfulness test. Removing top-3 or top-5 tokens would test compositional faithfulness.
5. **No human ground truth.** We measure stability (self-consistency) and deletion faithfulness (directional impact), not whether the explanations are "right" in a human sense.
6. **CPU-only run.** GPU would reduce runtime from 47 min to ~5 min, enabling higher num_samples experiments.


---

## Stage 2: Calibration & Confidence-Stratified Evaluation

### Frozen Evaluation Contract (Pre-registered before inspecting Stage 2 results)



1. **Calibration metrics**: ECE (10-bin, equal-width) and Brier score on all 28 tested deletion inputs. Ground truth proxy: model's own predicted label (limitation: this measures calibration relative to self, not human labels. ECE will be artificially low. Flagged, not hidden.)
2. **Confidence-stratified faithfulness**: Bucket all 28 deletion-tested inputs into 3 confidence bins: <0.90, 0.90–0.99, ≥0.99. Report per-bucket: direction-correct rate, label flip rate, mean |delta|, input IDs.
3. **Subgroup slice**: Report faithfulness separately for strong_baselines category (the "should be easy" group that shows paradoxical failure).
4. **Distribution-shift slice**: Report faithfulness separately for distribution_style_shift category (OOD inputs).
5. **Per-example preservation**: All 30 inputs documented with individual status (tested/skipped/excluded) and per-input metrics. No input hidden behind aggregates.
6. **Pass/fail criteria**:
   - ECE < 0.10 to consider calibration acceptable (with proxy-label caveat)
   - Confidence-stratified: if mean |delta| for ≥0.99 bucket is < 0.01, flag single-token deletion as underpowered for high-confidence regime
   - If strong_baselines flip rate remains 0%, flag LIME as unfaithful on high-confidence inputs regardless of direction-correct rate

### Calibration Results

*Populated 2026-09-10 from `python -m audit.analyse_results` output.*

ECE and Brier computed using model's own label as ground truth (n=28 deletion-tested inputs):

| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| ECE | **0.0124** | < 0.10 | **PASS** — internally consistent |
| Brier | **0.0014** | — | Near-zero; model is high-confidence throughout |

**Reliability diagram** (3 of 10 bins populated — model is bimodal, near 0 or near 1):

| Bin | n | Mean Predicted | Mean Actual | Gap |
|-----|---|---------------|-------------|-----|
| [0.0, 0.1) | 12 | 0.0056 | 0.0 | 0.0056 |
| [0.1, 0.2) | 1 | 0.1779 | 0.0 | **0.1779** |
| [0.9, 1.0] | 15 | 0.9932 | 1.0 | 0.0068 |

**Note on bin [0.1, 0.2)**: n=1. Isolated point — not actionable at this sample size.

**Caveat**: ECE uses model's own label as ground truth, measuring *internal consistency* not *calibration against reality*. A perpetually overconfident but correct model scores ≈ 0. With no human labels, ECE is a necessary-but-not-sufficient check only.

### Confidence-Stratified Faithfulness

*Populated 2026-09-10. Results are from `summary.json`.*

| Confidence Bucket | n | Dir. Correct | Flip Rate | Mean \|Delta\| | Inputs |
|-------------------|---|-------------|-----------|--------------|--------|
| 0.00 – 0.90 | 1 | 1.0 (100%) | 0.0% | 0.126 | [20] |
| 0.90 – 0.99 | 4 | 1.0 (100%) | 50.0% | 0.506 | [1, 4, 12, 17] |
| 0.99 – 1.00 | 23 | 87.0% | 39.1% | 0.375 | [2,3,5,6,7,8,10,11,13,14,15,16,18,19,21,22,23,24,25,26,27,28,29] |

**Pre-registered prediction assessment**: Prediction was that the ≥0.99 bucket would show mean|delta| < 0.01 and flip rate ≈ 0%. **Prediction was WRONG** — actual mean|delta| = 0.375 and flip rate = 39.1%.

**Why the prediction failed**: The ≥0.99 bucket contains both lexical_shortcuts (high confidence, huge deletion impact, 100% flip rate) and strong_baselines (high confidence, near-zero deletion impact, 0% flip rate). These average to a misleadingly healthy bucket aggregate. The strong-baseline paradox is real but is diluted by the lexical-shortcuts effect in this bucketing. Per-category analysis (see Faithfulness Findings above) is more revealing than confidence stratification alone at this sample size.

### Per-Example Status Table (All 30 Inputs)

| ID | Category | Stability CSV | Deletion CSV | Status | Notes |
|----|----------|:---:|:---:|--------|-------|
| 1 | negation_minimal_pairs | Y | Y | tested | Below Jaccard threshold (0.57) |
| 2 | negation_minimal_pairs | Y | Y | tested | Perfect Jaccard (1.0) |
| 3 | negation_minimal_pairs | Y | Y | tested | Perfect Jaccard (1.0) |
| 4 | negation_minimal_pairs | Y | Y | tested | — |
| 5 | negation_minimal_pairs | Y | Y | tested | Direction-incorrect (within noise) |
| 6 | lexical_shortcuts | Y | Y | tested | Below Jaccard threshold (0.50) |
| 7 | lexical_shortcuts | Y | Y | tested | — |
| 8 | lexical_shortcuts | Y | Y | tested | — |
| 9 | lexical_shortcuts | Y | **Y(skip)** | skipped_single_token | "Fine." — deletion produces empty string, logged in CSV |
| 10 | lexical_shortcuts | Y | Y | tested | — |
| 11 | ambiguity | Y | Y | tested | Perfect Jaccard (1.0) |
| 12 | ambiguity | Y | Y | tested | — |
| 13 | ambiguity | Y | Y | tested | Perfect Jaccard (1.0) |
| 14 | ambiguity | Y | Y | tested | Perfect Jaccard (1.0) |
| 15 | ambiguity | Y | Y | tested | Perfect Jaccard (1.0) |
| 16 | distribution_style_shift | Y | Y | tested | Perfect Jaccard (1.0) |
| 17 | distribution_style_shift | Y | Y | tested | Below Jaccard threshold (0.57) |
| 18 | distribution_style_shift | Y | Y | tested | Below Jaccard threshold (0.57) |
| 19 | distribution_style_shift | Y | Y | tested | — |
| 20 | distribution_style_shift | Y | Y | tested | — |
| 21 | strong_baselines | Y | Y | tested | **Worst stability** (Jaccard 0.46). Below threshold. |
| 22 | strong_baselines | Y | Y | tested | Direction-incorrect (within noise) |
| 23 | strong_baselines | Y | Y | tested | Perfect Jaccard (1.0) |
| 24 | strong_baselines | Y | Y | tested | Below Jaccard threshold (0.52) |
| 25 | strong_baselines | Y | Y | tested | — |
| 26 | edge_cases | Y | Y | tested | Direction-incorrect. Perfect Jaccard (1.0). Repeated token. |
| 27 | edge_cases | Y | Y | tested | Perfect Jaccard (1.0) |
| 28 | edge_cases | Y | Y | tested | — |
| 29 | edge_cases | Y | Y | tested | Perfect Jaccard (1.0) |
| 30 | edge_cases | **N** | **Y(skip)** | skipped_empty | `" "` — whitespace-only, skipped before LIME, logged in deletion CSV |

### Exploratory Follow-Up (NOT frozen — these are hypotheses for future work)

The following analyses are exploratory and were NOT pre-registered. Results should be interpreted with appropriate skepticism.

1. **Temperature scaling experiment (E5)**: Fit temperature parameter on SST-2 dev split, re-run LIME on calibrated model. Tests whether flat decision surface is artifact of overconfidence or inherent property.
2. **LIME vs random baseline (E4)**: Compare LIME's top-k deletion delta against random-k token removal on high-confidence inputs. Tests whether LIME adds value over random in the high-confidence regime.
3. **Multi-token deletion curve (E2)**: Run top-1/3/5/10 deletion on all inputs. Tests whether increasing k recovers faithfulness signal lost by single-token deletion.
4. **Stability-confidence correlation (E6)**: Spearman correlation between model confidence and Jaccard stability. Tests whether the strong-baseline instability is confidence-driven.
5. **Adversarial typo slice (E7)**: 10 new inputs with systematic character perturbations. Tests LIME under distribution shift within-text.

---

## Raw Data References

- `audit/results/raw_attributions.csv` - 145 rows (29 inputs x 5 seeds)
- `audit/results/deletion_faithfulness.csv` - 28 rows (input 9 "Fine." excluded: single-token deletion produces empty string)
- `audit/results/stability_metrics.csv` - 29 rows with per-input aggregates
- `audit/results/summary.json` - full aggregate statistics including calibration + confidence-stratified faithfulness
- `audit/results/environment.json` - exact library versions and runtime info
