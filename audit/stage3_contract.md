# Stage 3 Frozen Contract — DistilBERT-SST2 Calibration & Evaluation

> **Amendment note (supersedes commit cf419d9):** Two construct-validity issues in the prior version were corrected before any Stage 3 outcomes were inspected: (1) the contract title and scope incorrectly named "VertexED" — the model under evaluation is `distilbert-base-uncased-finetuned-sst-2-english` (revision `714eb0fa89d2f80546fda750413ed43d93601a13`), continuing the same model used in Stages 1-2; (2) P1 has been renamed from a calibration criterion to a confidence self-consistency diagnostic, removing all PASS/FAIL calibration language, since no external ground-truth labels are available. The prior contract commit is preserved in git history.
>
> **Second amendment (pre-run, no Stage 3 outcomes inspected):**
> (a) P4 boundary and non-finite handling made explicit (see Primary Analysis P4). Classifier extracted to `audit/p4_decision.py` with boundary tests in `audit/test_p4_decision.py`.
> (b) P3 fail-condition language softened so a zero flip rate is reported as a limitation of the single-token deletion diagnostic, not as a general falsification of LIME. Measured quantities (flip rate, direction-correct rate, mean \|delta\|) are preserved.
> (c) Tokenizer is bound to the same frozen revision as the model via `audit/config.py:MODEL_REVISION` (full 40-char immutable HF commit SHA `714eb0fa89d2f80546fda750413ed43d93601a13`) and is recorded alongside the model revision in the run receipt (`audit/runner.py:get_environment_info`).
> (d) Scope of the slice analysis (P2, P3, P4) is labelled as a post-Stage-2, pre-Stage-3 analysis plan, not fresh independent confirmatory evidence, since Stage 1-2 inputs and their aggregate results were seen before slice definitions were frozen. All Stage 1-2 artifacts and the 30 / 29 / 28 accounting are preserved unchanged.


## Scope

Calibration and explanation-quality evaluation of the DistilBERT-SST2 model (`distilbert-base-uncased-finetuned-sst-2-english`, revision `714eb0fa89d2f80546fda750413ed43d93601a13`) on the pre-registered 30-input sentiment test set (same inputs as Stages 1–2, `audit/test_set.json`). Evaluation is bounded to the frozen criteria below. Exploratory follow-ups are listed separately and carry no pass/fail weight.



## Primary Analysis (frozen)

### P1 — Confidence Self-Consistency Diagnostic

*Note: this is not a calibration criterion. No independent ground-truth labels exist. ECE and Brier here measure whether the model's confidence scores are internally consistent — they do not measure calibration against reality and carry no calibration PASS claim.*

| Metric | Computation | Flag threshold |
|--------|------------|----------------|
| ECE | 10-bin equal-width, model's own predicted label as ground-truth proxy | Report value; flag if ECE ≥ 0.10 as high internal inconsistency |
| Brier score | Mean squared error vs model's own label | Report value; flag if Brier ≥ 0.05 as high internal inconsistency |
| Reliability diagram | Bin-level mean predicted vs mean actual | Report populated bins; flag if < 5 bins populated as bimodal/degenerate confidence distribution |

These flags are diagnostic only. A flag does not constitute a PASS or FAIL verdict.

### P2 — Confidence-stratified faithfulness

Bucket all deletion-tested inputs into three confidence bins. Report per bucket: direction-correct rate, label-flip rate, mean |confidence delta|, input IDs.

| Bucket | Range |
|--------|-------|
| Low | [0.00, 0.90) |
| Mid | [0.90, 0.99) |
| High | [0.99, 1.00] |

**Pre-registered prediction:** High bucket expected to show mean |delta| < 0.01 and flip rate ≈ 0% for strong-baseline inputs, confirming the Stage 2 paradox holds on this model.  
Pass/fail: if high-bucket mean |delta| < 0.01 *and* flip rate = 0%, flag single-token deletion as underpowered for the high-confidence regime.

### P3 — Subgroup slice: `strong_baselines`

Report faithfulness separately for the `strong_baselines` category (5 inputs: IDs 21–25).  
**Pre-registered prediction:** flip rate will remain 0% despite directional correctness. If flip rate > 0%, record as disconfirmation.

### P4 — Stress slice: `distribution_style_shift`

This is a small preregistered stress slice of 5 inputs (IDs 16–20) covering style and domain shift. It is not broad OOD evidence — it tests whether LIME degrades under a controlled, narrow distribution shift. Results should not be generalised beyond this slice.

**Pre-registered quantitative rule (amended for boundary and non-finite cases):**  
Let `J_shift` = mean Jaccard top-5 for `distribution_style_shift`. Let `J_anchor` = mean Jaccard top-5 for `ambiguity`. Let `delta = J_anchor - J_shift` computed on unrounded values.

- **Confirmed** (stress effect present): `delta > 0.05` (strict)
- **Inconclusive** (directional but small): `0 < delta <= 0.05` (equality included per amendment)
- **Disconfirmed** (no degradation): `delta <= 0`
- **Undetermined**: `J_anchor` or `J_shift` missing, non-finite (NaN, inf), or computed over an empty slice

Decision is computed from unrounded values; rounding or formatting is applied only after classification. The classification is implemented in `audit/p4_decision.py` with boundary and non-finite unit tests in `audit/test_p4_decision.py`. Report which outcome applies. The `ambiguity` slice is chosen as anchor because it contains the same input count (5) with no distribution shift.

### P5 — Per-example preservation

Every input in the 30-input test set must appear in the per-example output table with one of:
- `tested` — evaluation ran, results recorded
- `skipped_single_token` — single-token input, deletion produces empty string, logged with original model score
- `skipped_empty` — whitespace-only input, pipeline skipped before model runs

No input may be silently absent. Aggregate metrics are only computed over `tested` inputs.


## Pass/Fail Summary Criteria

All five primary criteria must be assessed before Stage 3 is considered complete. P1 is diagnostic only and carries no pass/fail weight.

| Criterion | Pass condition | Fail condition |
|-----------|---------------|----------------|
| P1 (self-consistency) | — diagnostic, report flags only — | — |
| P2 (confidence-stratified) | High-bucket mean\|delta\| ≥ 0.01 OR flip rate > 0% | High-bucket mean\|delta\| < 0.01 AND flip rate = 0% → flag deletion as underpowered |
| P3 (strong_baselines slice) | Flip rate > 0% (paradox broken) | Flip rate = 0%: record as a limitation of the single-token deletion diagnostic on the `strong_baselines` slice; preserve the measured flip rate, directional-correctness rate, and mean \|delta\|; do NOT report as a general falsification of LIME |
| P4 (stress slice) | Outcome documented per quantitative rule | Outcome not computed or threshold rule not applied |
| P5 (per-example) | All 30 inputs present with status | Any input silently absent |



## Exploratory Follow-Up (NOT frozen — no pass/fail weight)

These are hypotheses for future work. Results, if computed, must be clearly separated from P1–P5 above.

| ID | Hypothesis |
|----|-----------|
| E8 | Multi-token deletion curve (top-1 / 3 / 5 / 10): tests whether increasing k recovers faithfulness signal |
| E9 | Stability–confidence Spearman correlation: tests whether strong-baseline instability is confidence-driven |
| E10 | Adversarial typo slice (10 new inputs with character perturbations): tests LIME under within-text distribution shift |

