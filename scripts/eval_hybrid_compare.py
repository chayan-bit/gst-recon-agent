"""Full-reconciliation comparison of a hybrid run against stored reference runs on the same cases, plus per-document diagnostics.

    python scripts/eval_hybrid_compare.py --run RUN_DIR --cases CASE_DIR... --truth TRUTH_ROOT \
        --ref NAME=SCORES_DIR[,SCORES_DIR...] ... [--split test_iid,test_ood]

Case-mean of itc_invoice, match_accuracy and composite over the cases of RUN_DIR (all must be in every reference), the
paired bootstrap of run minus reference (10,000 case resamples, seed 0, two-sided centred p) as in reports/hybrid.md,
and from RUN_DIR/docs: parse rate, invented-identity rate (reward/doc.py INVENTED slots over all identity slots), mean
per-document latency, tokens and CLI cost. Prints aggregates only, never document text.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gst_recon.hybrid.run import parse_doc  # noqa: E402
from gst_recon.hybrid.sft import truth_records  # noqa: E402
from gst_recon.hybrid.inputs import split_docs, split_sections  # noqa: E402
from gst_recon.rewards.doc import IDENTITY, INVENTED, identity_score  # noqa: E402
from gst_recon.schema import Case  # noqa: E402

METRICS = ("itc_invoice", "match_accuracy", "composite")


def load_scores(dirs: list[Path], splits: set[str] | None = None) -> dict[str, dict]:
    out = {}
    for d in dirs:
        for line in (d / "scores.jsonl").read_text().splitlines():
            r = json.loads(line)
            if splits is None or r.get("split") in splits:
                out[r["case_id"]] = r["metrics"]
    return out


def paired(run: dict, ref: dict, ids: list[str], metric: str, reps: int = 10000) -> tuple[float, float, float, float]:
    d = [run[i][metric] - ref[i][metric] for i in ids]
    rng = random.Random(0)
    boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(reps))
    p = 2 * min(sum(b <= 0 for b in boots), sum(b >= 0 for b in boots)) / reps
    return sum(d) / len(d), boots[int(0.025 * reps)], boots[int(0.975 * reps) - 1], min(p, 1.0)


def doc_diagnostics(run: Path, cases: list[Path], truth_root: Path, ids: set[str]) -> dict:
    dirs = {p.parent.name: p.parent for r in cases for p in r.glob("*/target.json")}
    n = ok = invented = slots = 0
    lat, ptok, ctok, cost = [], 0, 0, 0.0
    for case_id in sorted(ids & dirs.keys()):
        tj = next(truth_root.glob(f"*/{case_id}.json"), None) or truth_root / f"{case_id}.json"
        case = Case.model_validate_json(tj.read_text())
        truth = truth_records(json.loads((dirs[case_id] / "target.json").read_text()), case)
        blocks = {d.doc_id: d.block for d in split_docs(split_sections((dirs[case_id] / "prompt.txt").read_text())["INVOICES"])}
        for f in sorted((run / "docs" / case_id).glob("*.json")):
            r = json.loads(f.read_text())
            n += 1
            lat.append(r.get("latency_s") or 0)
            ptok += r.get("prompt_tokens") or 0
            ctok += r.get("completion_tokens") or 0
            cost += r.get("cost_usd") or 0
            rec, _ = parse_doc(r.get("text") or "") if not r.get("error") else (None, "")
            if rec is None or f.stem not in truth:
                continue
            ok += 1
            for field in IDENTITY:
                slots += 1
                invented += identity_score(field, getattr(rec, field), getattr(truth[f.stem], field), blocks[f.stem]) == INVENTED
    return {"docs": n, "parse_ok_%": round(100 * ok / n, 1), "invented_identity_%": round(100 * invented / max(slots, 1), 2),
            "invented_identity_n": invented, "mean_doc_latency_s": round(sum(lat) / n, 1), "prompt_tokens_per_doc": ptok // n,
            "completion_tokens_per_doc": ctok // n, "cli_cost_usd_total": round(cost, 3), "cli_cost_usd_per_doc": round(cost / n, 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--cases", type=Path, nargs="+", required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--ref", action="append", default=[], help="NAME=DIR[,DIR...] (dirs holding scores.jsonl)")
    ap.add_argument("--split", default=None, help="comma-separated split values to keep in every scores.jsonl")
    a = ap.parse_args()
    splits = set(a.split.split(",")) if a.split else None
    run = load_scores([a.run], splits)
    ids = sorted(run)
    refs = {n: load_scores([Path(p) for p in v.split(",")]) for n, v in (r.split("=", 1) for r in a.ref)}
    for name, ref in refs.items():
        missing = [i for i in ids if i not in ref]
        if missing:
            print(f"warning: {name} lacks {len(missing)} of {len(ids)} run cases; pairing on the shared {len(ids) - len(missing)}", file=sys.stderr)
    print(f"cases: {len(ids)}")
    print("run:", {m: round(100 * sum(run[i][m] for i in ids) / len(ids), 1) for m in METRICS})
    for name, ref in refs.items():
        shared = [i for i in ids if i in ref]
        row = {"n": len(shared), name: {m: round(100 * sum(ref[i][m] for i in shared) / len(shared), 1) for m in METRICS}}
        for m in METRICS:
            d, lo, hi, p = paired(run, ref, shared, m)
            row[f"run minus {name} {m}"] = f"{100 * d:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] p={p:.4f}"
        print(json.dumps(row, indent=1))
    print(json.dumps(doc_diagnostics(a.run, a.cases, a.truth, set(ids)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
