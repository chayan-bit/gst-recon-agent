"""Trivial baselines from the sim audit, scored on the frozen eval sets with the same scorer as every model.

    python scripts/eval_baselines.py --cases data/eval/rendered/test_iid data/eval/rendered/test_ood \
        --truth-dir data/eval/truth --out-root runs/eval

Writes runs/eval/baseline-keyword and runs/eval/baseline-context-blind. Both are handed the TRUE extraction and
document links (they isolate the decisions), so their field F1, match accuracy, schema and arithmetic are oracle
values; compare them on ITC invoice exact, context accuracy and ITC error.
  keyword        naive Bayes on line descriptions -> s.17(5) label, trained on simulated train cases, no flags
  context-blind  the real rules engine without the buyer profile or remarks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gst_recon.eval.cases import load_cases  # noqa: E402
from gst_recon.eval.runner import run_eval  # noqa: E402
from gst_recon.sim import audit  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, nargs="+", required=True)
    ap.add_argument("--truth-dir", type=Path, required=True, help="truth Case JSONs (needed: the baselines read the true documents)")
    ap.add_argument("--out-root", type=Path, default=Path("runs/eval"))
    ap.add_argument("--n-train", type=int, default=900, help="simulated train cases the keyword model learns from")
    ap.add_argument("--train-seed", type=int, default=0)
    a = ap.parse_args(argv)
    cases = load_cases(a.cases, truth_dir=a.truth_dir)
    if any(c.truth is None for c in cases):
        ap.error(f"missing truth Case JSON under {a.truth_dir} for some cases")
    kw = audit.keyword_model(audit.gen("train", a.n_train, a.train_seed))
    preds = {"baseline-keyword": ("keyword (oracle extraction and links)", lambda c: audit._clean_output(c, kw)),
             "baseline-context-blind": ("context-blind rules (oracle extraction and links)", audit.context_blind)}
    for name, (label, fn) in preds.items():
        cfg = {"label": label, "model": name, "endpoint": "none (rule-based)", "constrained": False, "prices": {},
               "n_train": a.n_train, "cases": [str(p) for p in a.cases]}
        run_eval(cases, lambda c, fn=fn: {"text": json.dumps(fn(c.truth)), "latency_s": 0.0, "error": None}, a.out_root / name, cfg,
                 concurrency=1, resume=False)
        print(f"{name}: wrote {a.out_root / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
