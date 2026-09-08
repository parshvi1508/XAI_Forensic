import os

MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"

LIME_NUM_SAMPLES = 300
LIME_NUM_FEATURES = 10
LIME_CLASS_NAMES = ["negative", "positive"]

RANDOM_SEEDS = [42, 123, 456, 789, 1024]
CANONICAL_SEED = 42

TOP_K_FOR_JACCARD = 5

STABILITY_THRESHOLD_JACCARD = 0.6
STABILITY_THRESHOLD_KENDALL = 0.5
FAITHFULNESS_THRESHOLD_DIRECTION = 0.7

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_SET_PATH = os.path.join(BASE_DIR, "test_set.json")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
RAW_CSV_PATH = os.path.join(RESULTS_DIR, "raw_attributions.csv")
DELETION_CSV_PATH = os.path.join(RESULTS_DIR, "deletion_faithfulness.csv")
STABILITY_CSV_PATH = os.path.join(RESULTS_DIR, "stability_metrics.csv")
SUMMARY_PATH = os.path.join(RESULTS_DIR, "summary.json")
