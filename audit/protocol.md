# LIME Attribution Audit - Pre-Registration Protocol

## Test Set
- 30 inputs defined in `test_set.json`
- 6 categories x 5 inputs: negation/minimal pairs, lexical shortcuts, ambiguity, distribution/style shift, strong baselines, edge cases
- Inputs are not changed after this protocol is finalized.

## Model
- `distilbert-base-uncased-finetuned-sst-2-english`
- Loaded via `transformers.pipeline("text-classification", model=..., top_k=None)`
- Model revision hash recorded in results summary

## LIME Parameters
- `num_samples=300` (perturbation count per explanation)
- `num_features=10` (top tokens returned)
- `class_names=["negative", "positive"]`
- 5 random seeds: `[42, 123, 456, 789, 1024]`

## Stability Metrics
- **Jaccard top-5 overlap**: For each input, across all C(5,2)=10 seed pairs, compute Jaccard index of top-5 token sets. 
  - Acceptable threshold: overall mean >= 0.6
- **Kendall's tau rank correlation**: For each input, across all seed pairs, compute Kendall's tau on rank orderings of tokens present in both rankings.
  - Acceptable threshold: overall mean >= 0.5
- **Label stability**: Whether the predicted label is identical across all 5 seeds
- **Top-1 unanimity**: Whether the highest-attribution token is identical across all 5 seeds

## Faithfulness Metrics
- **Confidence delta**: Signed change in positive-class score after removing the highest-attribution token (from canonical seed=42)
- **Label flip**: Boolean - did the predicted label change after token removal?
- **Direction correctness**: If LIME says token has positive weight, removing it should decrease positive score (and vice versa). Rate of directionally correct deletions.
  - Acceptable threshold: >= 0.7

## Rules
1. Test set, metric definitions, and thresholds must not change after seeing results
2. Negative results are valid findings, not reasons to re-tune
3. Failed/crashed inputs are logged, not excluded
4. All raw data is preserved in CSV format
