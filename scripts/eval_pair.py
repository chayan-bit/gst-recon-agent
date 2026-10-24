"""Paired comparison of two eval runs on their shared cases: all, simulator and realworld.

usage: python scripts/eval_pair.py REF_RUN_DIR OTHER_RUN_DIR
Prints a Markdown table of OTHER minus REF with a paired bootstrap 95% CI and a centred-bootstrap p-value.
The ratio metrics (ITC invoice exact, context accuracy, composite) use gst_recon.eval.stats.paired_delta and show pooled means;
the rupee metrics are per-case means over the shared cases.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from gst_recon.eval.stats import arrays, paired_delta

N_BOOT = 10000
SETS = {"all shared": lambda r: True, "simulator": lambda r: r["split"] != "realworld", "realworld": lambda r: r["split"] == "realworld"}


def load(run_dir: str) -> list[dict]:
    with open(f"{run_dir}/scores.jsonl") as f:
        return [json.loads(line) for line in f if line.strip()]


def rs_delta(a: list[dict], b: list[dict], key: str) -> tuple[int, float, float, float, float] | None:
    diff = np.array([y["metrics"][key] - x["metrics"][key] for x, y in zip(a, b)])
    if len(diff) < 2:
        return None
    boots = diff[np.random.default_rng(0).integers(0, len(diff), size=(N_BOOT, len(diff)))].mean(1)
    p = (np.sum(np.abs(boots - boots.mean()) >= abs(diff.mean())) + 1) / (N_BOOT + 1)
    return len(diff), diff.mean(), *np.percentile(boots, [2.5, 97.5]), p


def pooled(rs: list[dict], name: str) -> float:
    n, d = arrays(rs, name)
    return 100 * n.sum() / d.sum()


def main(ref_dir: str, other_dir: str) -> None:
    ref, other = load(ref_dir), load(other_dir)
    names = (ref_dir.rstrip("/").split("/")[-1], other_dir.rstrip("/").split("/")[-1])
    print(f"| set | metric | n | {names[0]} | {names[1]} | delta (other minus ref) [95% CI] | bootstrap p |")
    print("|---|---|---|---|---|---|---|")
    for set_name, keep in SETS.items():
        ids = {r["case_id"] for r in ref if keep(r)} & {r["case_id"] for r in other if keep(r)}
        a = sorted((r for r in ref if r["case_id"] in ids), key=lambda r: r["case_id"])
        b = sorted((r for r in other if r["case_id"] in ids), key=lambda r: r["case_id"])
        for name in ("itc_invoice", "context_acc", "composite"):
            d = paired_delta(a, b, name)
            if "delta" in d:
                print(f"| {set_name} | {name} | {int(d['n'])} | {pooled(a, name):.1f} | {pooled(b, name):.1f} | "
                      f"{d['delta'] * 100:+.1f} [{d['ci_lo'] * 100:+.1f}, {d['ci_hi'] * 100:+.1f}] pts | {d['p_value']:.4f} |")
        for key in ("itc_overclaim_rs", "itc_underclaim_rs"):
            r = rs_delta(a, b, key)
            if r:
                mean = lambda rs: np.mean([x["metrics"][key] for x in rs])  # noqa: E731
                print(f"| {set_name} | {key} (Rs per case) | {r[0]} | {mean(a):,.0f} | {mean(b):,.0f} | {r[1]:+,.0f} [{r[2]:+,.0f}, {r[3]:+,.0f}] | {r[4]:.4f} |")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
