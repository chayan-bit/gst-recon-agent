"""CLI: python -m realworld.baselines [--n-train 500] [--json runs/realworld/baselines.json]

The sim audit's trivial baselines (majority, no_anomaly, keyword, context_blind, plus the rules-engine
oracle) scored on the real-world split. The keyword model is trained on simulator train cases, exactly
as in `python -m gst_recon.sim.audit`; the JSON uses the audit's format so `gst_recon.eval report
--baselines` can show it next to model runs.
"""

from __future__ import annotations

import argparse
import json
import sys

from gst_recon.sim.audit import METRICS, evaluate, gen
from realworld.truth import SPLIT, build_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m realworld.baselines")
    ap.add_argument("--n-train", type=int, default=500, help="simulator train cases for the keyword model")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", help="write {'baselines': {'realworld/<name>': metrics}}")
    a = ap.parse_args(argv)
    cases, problems = build_all()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    table = evaluate(gen("train", a.n_train, a.seed), {SPLIT: cases})
    rows = {f"{s}/{n}": v for (s, n), v in table.items() if s == SPLIT}
    cols = (*METRICS, "line_acc", "ctx_line_acc")
    print("| baseline | " + " | ".join(cols) + " |\n|---|" + "---|" * len(cols))
    for k, row in rows.items():
        print(f"| {k.split('/', 1)[1]} | " + " | ".join(
            "" if c not in row else f"{row[c]:,.0f}" if c == "itc_abs_err_rs" else f"{row[c]:.3f}" for c in cols) + " |")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"n_cases": len(cases), "n_train": a.n_train, "baselines": rows}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
