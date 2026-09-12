# Stage 3 Frozen Contract — VertexED Calibration & Evaluation

**Status: FROZEN — pre-run. Do not add result values before reviewer approves this SHA.**  
**Author: Parshvi Jain**  
**Date frozen: 2026-09-12**  
**Preceding stage caveat:** Stage 2 results (failure_memo.md) were computed before that contract was written. Stage 3 corrects this — this file is committed before any Stage 3 evaluation runs.

---

## Scope

Calibration and explanation-quality evaluation of the VertexED model on the pre-registered 30-input sentiment test set (same inputs as Stages 1–2, `audit/test_set.json`). Evaluation is bounded to the frozen criteria below. Exploratory follow-ups are listed separately and carry no pass/fail weight.

---

## Primary Analysis (frozen)

### P1 — Calibration

| Metric | Computation | Pass threshold | Fail threshold |
|--------|------------|----------------|----------------|
| ECE | 10-bin equal-width, model's predicted label as ground-truth proxy | ECE < 0.10 | ECE ≥ 0.10 |
| Brier score | Mean squared error vs model's own label | Brier < 0.05 | Brier ≥ 0.05 |
| Reliability diagram | Bin-level mean predicted vs mean actual | ≥ 5 bins populated | < 5 bins populated (flag as bimodal/degenerate) |

**Proxy-label caveat (pre-stated):** No human labels exist. ECE and Brier use the model's own predicted label as ground truth. This measures *internal consistency*, not calibration against reality. A perpetually overconfident-but-correct model can score ≈ 0. Results must be reported with this caveat; they do not constitute a claim about real-world calibration.

### P2 — Confidence-stratified faithfulness

Bucket all deletion-tested inputs into three confidence bins. Report per bucket: direction-correct rate, label-flip rate, mean |confidence delta|, input IDs.

| Bucket | Range |
|--------|-------|
| Low | [0.00, 0.90) |
| Mid | [0.90, 0.99) |
| High | [0.99, 1.00] |

**Pre-registered prediction:** High bucket expected to show mean |delta| < 0.01 and flip rate ≈ 0% for strong-baseline inputs, confirming the Stage 2 paradox holds on VertexED.  
Pass/fail: if high-bucket mean |delta| < 0.01 *and* flip rate = 0%, flag single-token deletion as underpowered for the high-confidence regime.

### P3 — Subgroup slice: `strong_baselines`

Report faithfulness separately for the `strong_baselines` category (5 inputs: IDs 21–25).  
**Pre-registered prediction:** flip rate will remain 0% despite directional correctness. If flip rate > 0%, record as disconfirmation.

### P4 — Distribution-shift slice: `distribution_style_shift`

Report faithfulness separately for the `distribution_style_shift` category (5 inputs: IDs 16–20). These are the deliberately OOD inputs.  
**Pre-registered prediction:** stability (Jaccard) will be lower for this slice than the `ambiguity` slice.

### P5 — Per-example preservation

Every input in the 30-input test set must appear in the per-example output table with one of:
- `tested` — evaluation ran, results recorded
- `skipped_single_token` — single-token input, deletion produces empty string, logged with original model score
- `skipped_empty` — whitespace-only input, pipeline skipped before model runs

No input may be silently absent. Aggregate metrics are only computed over `tested` inputs.

---

## Pass/Fail Summary Criteria

All five primary criteria must be assessed before Stage 3 is considered complete. The overall verdict is:

- **PASS** if P1 ECE + Brier both pass *and* P3 flip-rate prediction confirmed *and* per-example table complete.
- **CONDITIONAL PASS** if calibration passes but confidence-stratification prediction is wrong — record the disconfirmation and explain.
- **FAIL** if ECE ≥ 0.10 *or* per-example table is incomplete.

---

## Exploratory Follow-Up (NOT frozen — no pass/fail weight)

These are hypotheses for future work. Results, if computed, must be clearly separated from P1–P5 above.

| ID | Hypothesis |
|----|-----------|
| E8 | Multi-token deletion curve (top-1 / 3 / 5 / 10): tests whether increasing k recovers faithfulness signal |
| E9 | Stability–confidence Spearman correlation: tests whether strong-baseline instability is confidence-driven |
| E10 | VertexED vs Model A head-to-head on identical inputs: tests whether calibration gap is model-specific |
| E11 | Adversarial typo slice (10 new inputs with character perturbations): tests LIME under within-text distribution shift |

---

## Accounting Rules (pre-stated)

- Test set: 30 inputs (`audit/test_set.json`), IDs 1–30. No inputs may be added or removed post-commit.
- Stability CSV: computed over inputs with LIME attributions (expected 29; Input 30 whitespace-only excluded).
- Deletion CSV: computed over inputs with canonical tokens and non-empty post-deletion text (expected 28; Input 9 single-token excluded; both logged as skipped).
- Any deviation from expected counts must be documented with exact runner line reference before results are interpreted.

---

## Commit Sequence

1. Commit this file alone (no result files).
2. Run `git log --format="%H" -1` — send SHA to reviewer.
3. Await reviewer confirmation before running evaluation.
4. After reviewer OKs: run evaluation, populate results in a separate `stage3_results.md`.
5. Commit results file separately — contract file must not be modified after step 1.
