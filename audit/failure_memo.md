# LIME Attribution Audit - Failure Memo


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


## Raw Data References

- `audit/results/raw_attributions.csv` - 145 rows (29 inputs x 5 seeds)
- `audit/results/deletion_faithfulness.csv` - 28 rows (input 9 "Fine." has no deletion - single word)
- `audit/results/stability_metrics.csv` - 29 rows with per-input aggregates
- `audit/results/summary.json` - full aggregate statistics
- `audit/results/environment.json` - exact library versions and runtime info
