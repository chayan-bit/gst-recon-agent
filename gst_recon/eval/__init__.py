"""Evaluation harness: run models on rendered cases, score with the shared rewards, report.

    python -m gst_recon.eval run    --endpoint URL --model NAME --cases data/rendered/test_iid --out runs/eval/<name>
    python -m gst_recon.eval report --runs runs/eval/* --out reports/results.md

Outputs live under runs/eval/ and are never training data (see `gst_recon.eval.guard`).
"""
