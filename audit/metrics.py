"""Re-exports from lime_audit.metrics — single source of truth is src/lime_audit/metrics.py."""
from lime_audit.metrics import (  # noqa: F401
    jaccard_top_k,
    kendall_tau_top_k,
    confidence_delta,
    faithfulness_direction_correct,
    bootstrap_ci,
    expected_calibration_error,
    confidence_bucket_analysis,
    count_tokenizer_mismatch,
    compute_pairwise_stability,
)
