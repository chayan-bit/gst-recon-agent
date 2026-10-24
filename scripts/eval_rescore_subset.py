"""Rescore a stopped run on the cases it finished, keeping its recorded config (prompt fingerprints, prices).

    python scripts/eval_rescore_subset.py RUN_DIR --cases data/eval/rendered/test_iid data/eval/rendered/test_ood --truth-dir data/eval/truth
"""
import argparse
import json
from pathlib import Path

from gst_recon.eval.cases import load_cases
from gst_recon.eval.report import run_table_md
from gst_recon.eval.runner import _atomic_write, _case_path, _usable, aggregate, score_all

ap = argparse.ArgumentParser()
ap.add_argument("run", type=Path)
ap.add_argument("--cases", nargs="+", required=True)
ap.add_argument("--truth-dir", type=Path, required=True)
a = ap.parse_args()
cases = [c for c in load_cases(a.cases, truth_dir=a.truth_dir) if _case_path(a.run, c.case_id).exists() and _usable(_case_path(a.run, c.case_id))]
config = json.loads((a.run / "config.json").read_text())
records = score_all(cases, a.run)
agg = aggregate(records, config, json.loads((a.run / "run_stats.json").read_text()), {r["metrics"]["context_source"] for r in records})
agg["subset"] = {"n_finished": len(cases), "note": "run stopped early; scored only on the cases it finished"}
_atomic_write(a.run / "aggregate.json", json.dumps(agg, indent=1))
_atomic_write(a.run / "scores.jsonl", "\n".join(json.dumps({k: r[k] for k in ("case_id", "split", "difficulty", "ocr_bucket", "length_bucket", "metrics", "error", "latency_s", "prompt_tokens", "completion_tokens") if k in r}) for r in records) + "\n")
_atomic_write(a.run / "table.md", run_table_md(agg))
print(f"{a.run.name}: rescored {len(cases)} finished cases")
