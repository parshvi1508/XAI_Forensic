"""
Reproducibility verification: runs audit twice, diffs CSVs.

Usage:
    python -m audit.verify
"""

import filecmp
import os
import shutil
import subprocess
import sys

from audit.config import RESULTS_DIR


def verify_reproducibility():
    python = sys.executable
    backup_dir = os.path.join(RESULTS_DIR, "_verify_backup")

    print("=== Run 1 ===")
    subprocess.run([python, "-m", "audit.runner"], check=True)
    subprocess.run([python, "-m", "audit.analyse_results"], check=True)

    os.makedirs(backup_dir, exist_ok=True)
    files_to_check = [
        "raw_attributions.csv",
        "deletion_faithfulness.csv",
        "stability_metrics.csv",
    ]
    for f in files_to_check:
        src = os.path.join(RESULTS_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_dir, f))

    print("\n=== Run 2 ===")
    subprocess.run([python, "-m", "audit.runner"], check=True)
    subprocess.run([python, "-m", "audit.analyse_results"], check=True)

    print("\n=== Comparing ===")
    all_match = True
    for f in files_to_check:
        run1 = os.path.join(backup_dir, f)
        run2 = os.path.join(RESULTS_DIR, f)
        if not os.path.exists(run1):
            print(f"  {f}: MISSING from run 1")
            all_match = False
            continue
        if not os.path.exists(run2):
            print(f"  {f}: MISSING from run 2")
            all_match = False
            continue
        if filecmp.cmp(run1, run2, shallow=False):
            print(f"  {f}: IDENTICAL")
        else:
            print(f"  {f}: DIFFERS (non-determinism detected)")
            all_match = False

    shutil.rmtree(backup_dir)

    if all_match:
        print("\nVERIFIED: all outputs are deterministic across runs.")
    else:
        print("\nWARNING: some outputs differ between runs.")
        print("Check that all random seeds are pinned and LIME version is fixed.")

    return all_match


if __name__ == "__main__":
    verify_reproducibility()
