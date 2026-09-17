# Stage 2 — Calibration & Confidence-Stratified Results

*Covers the Stage 2 evaluation contract and results for `distilbert-base-uncased-finetuned-sst-2-english`.*

## Frozen Evaluation Contract (Pre-registered before inspecting Stage 2 results)

1. **Calibration metrics**: ECE (10-bin, equal-width) and Brier score on all 28 tested deletion inputs. Ground truth proxy: model's own predicted label (limitation: this measures calibration relative to self, not human labels. ECE will be artificially low. Flagged, not hidden.)
2. **Confidence-stratified faithfulness**: Bucket all 28 deletion-tested inputs into 3 confidence bins: <0.90, 0.90–0.99, ≥0.99. Report per-bucket: direction-correct rate, label flip rate, mean |delta|, input IDs.
3. **Subgroup slice**: Report faithfulness separately for strong_baselines category (the "should be easy" group that shows paradoxical failure).
4. **Distribution-shift slice**: Report faithfulness separately for distribution_style_shift category (OOD inputs).
5. **Per-example preservation**: All 30 inputs documented with individual status (tested/skipped/excluded) and per-input metrics. No input hidden behind aggregates.
6. **Pass/fail criteria**:
   - ECE < 0.10 to consider calibration acceptable (with proxy-label caveat)
   - Confidence-stratified: if mean |delta| for ≥0.99 bucket is < 0.01, flag single-token deletion as underpowered for high-confidence regime
   - If strong_baselines flip rate remains 0%, flag LIME as unfaithful on high-confidence inputs regardless of direction-correct rate

## Calibration Results

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

## Confidence-Stratified Faithfulness

*Populated 2026-09-10. Results are from `summary.json`.*

| Confidence Bucket | n | Dir. Correct | Flip Rate | Mean \|Delta\| | Inputs |
|-------------------|---|-------------|-----------|--------------|--------|
| 0.00 – 0.90 | 1 | 1.0 (100%) | 0.0% | 0.126 | [20] |
| 0.90 – 0.99 | 4 | 1.0 (100%) | 50.0% | 0.506 | [1, 4, 12, 17] |
| 0.99 – 1.00 | 23 | 87.0% | 39.1% | 0.375 | [2,3,5,6,7,8,10,11,13,14,15,16,18,19,21,22,23,24,25,26,27,28,29] |

**Pre-registered prediction assessment**: Prediction was that the ≥0.99 bucket would show mean|delta| < 0.01 and flip rate ≈ 0%. **Prediction was WRONG** — actual mean|delta| = 0.375 and flip rate = 39.1%.

**Why the prediction failed**: The ≥0.99 bucket contains both lexical_shortcuts (high confidence, huge deletion impact, 100% flip rate) and strong_baselines (high confidence, near-zero deletion impact, 0% flip rate). These average to a misleadingly healthy bucket aggregate. The strong-baseline paradox is real but is diluted by the lexical-shortcuts effect in this bucketing. Per-category analysis (see `failure_memo.md` Faithfulness Findings) is more revealing than confidence stratification alone at this sample size.

## Per-Example Status Table (All 30 Inputs)

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

## Exploratory Follow-Up (NOT frozen — hypotheses for future work)

The following analyses are exploratory and were NOT pre-registered. Results should be interpreted with appropriate skepticism.

1. **Temperature scaling experiment (E5)**: Fit temperature parameter on SST-2 dev split, re-run LIME on calibrated model. Tests whether flat decision surface is artifact of overconfidence or inherent property.
2. **LIME vs random baseline (E4)**: Compare LIME's top-k deletion delta against random-k token removal on high-confidence inputs. Tests whether LIME adds value over random in the high-confidence regime.
3. **Multi-token deletion curve (E2)**: Run top-1/3/5/10 deletion on all inputs. Tests whether increasing k recovers faithfulness signal lost by single-token deletion.
4. **Stability-confidence correlation (E6)**: Spearman correlation between model confidence and Jaccard stability. Tests whether the strong-baseline instability is confidence-driven.
5. **Adversarial typo slice (E7)**: 10 new inputs with systematic character perturbations. Tests LIME under distribution shift within-text.
