"""CLI: python -m gst_recon.semireal build --labels <dir> --out <dir> [--seed 0] [--sim-seeds 0,1,2,3,4] [--max-docs 25] [--no-oracle]

<labels> layout (the per-document labelling output):
  manifest.json                        buyer_profile_header (a "=== CASE ===" block), documents[] {doc_id, confidence, section_label}
  cases/<doc_id>/truth.json            the labelled DocRecord
  cases/<doc_id>/input.txt             the document text the model reads, verbatim
  cases/<doc_id>/label.json            optional: "unreadable" list; "<field>: not printed ..." marks a field the page lacks
Writes <out>/{clean,sim}/<case_id>/{prompt.txt,target.json,meta.json}, <out>/truth/<level>/<case_id>.json,
<out>/manifest.json and <out>/oracle.json. EVAL ONLY: never point a training builder at <out>.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from gst_recon.eval.guard import mark_eval_dir
from gst_recon.hybrid.docschema import DocRecord
from gst_recon.hybrid.inputs import parse_header, split_sections
from gst_recon.schema import Party
from gst_recon.semireal.build import IDENTITY, LEVELS, MAX_DOCS, RealDoc, build_set
from gst_recon.semireal.oracle import run_oracle


def _absent(label: dict) -> frozenset[str]:
    """Identity fields the label says the page does not print (as opposed to printed but unreadable)."""
    out = set()
    for note in label.get("unreadable", []):
        f, _, why = str(note).partition(":")
        if f.strip() in IDENTITY and re.search(r"\bnot printed\b", why):
            out.add(f.strip())
    return frozenset(out)


def load_labels(root: Path) -> tuple[list[RealDoc], Party, object]:
    m = json.loads((root / "manifest.json").read_text())
    h = parse_header(split_sections(m["buyer_profile_header"])["CASE"])
    buyer = Party(name=h.buyer_name, gstin=h.buyer_gstin, state_code=h.buyer_state, address="")
    info = {d["doc_id"]: d for d in m.get("documents", [])}
    docs = []
    for d in sorted(p for p in (root / "cases").iterdir() if (p / "truth.json").exists()):
        label = json.loads((d / "label.json").read_text()) if (d / "label.json").exists() else {}
        meta = info.get(d.name, {})
        docs.append(RealDoc(key=d.name, record=DocRecord.model_validate_json((d / "truth.json").read_text()),
                            text=(d / "input.txt").read_text(encoding="utf-8"),
                            source=meta.get("section_label") or "scanned document, OCR text",
                            confidence=meta.get("confidence") or label.get("confidence", ""), absent=_absent(label)))
    return docs, buyer, h.profile


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.semireal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="labelled real documents + simulated books -> eval cases (clean and sim levels)")
    b.add_argument("--labels", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--sim-seeds", default="0", help="comma-separated seeds of the sim-level replicas, e.g. 0,1,2,3,4")
    b.add_argument("--max-docs", type=int, default=MAX_DOCS)
    b.add_argument("--no-oracle", action="store_true")
    a = ap.parse_args(argv)
    docs, buyer, profile = load_labels(a.labels)
    a.out.mkdir(parents=True, exist_ok=True)
    mark_eval_dir(a.out)
    manifest = build_set(docs, buyer, profile, a.out, seed=a.seed, max_docs=a.max_docs,
                         sim_seeds=tuple(int(x) for x in a.sim_seeds.split(",")))
    manifest["confidence"] = {d.key: d.confidence for d in docs}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    for level, v in manifest["levels"].items():
        print(f"{level}: {v['n_cases']} cases, {v['n_docs']} docs; per seed: {v['per_seed']}")
    print(f"excluded {len(manifest['excluded'])}: " + "; ".join(f"{e['source_key']} ({e['reason']})" for e in manifest["excluded"]))
    if a.no_oracle:
        return 0
    oracle = {lv: run_oracle(a.out / lv, a.out / "truth", a.out / "oracle_runs" / lv) for lv in LEVELS}
    (a.out / "oracle.json").write_text(json.dumps(oracle, indent=1))
    bad = 0
    for lv, o in oracle.items():
        misses = {cid: c["misses"] for cid, c in o["cases"].items() if c["misses"]}
        bad += len(misses)
        print(f"oracle {lv}: {o['overall']}, errors {o['n_errors']}, by difficulty {o['by_difficulty']}, cases with misses {len(misses)}: "
              + ", ".join(f"{cid} {sorted({(m['doc_id'], m['part']) for m in ms})}" for cid, ms in misses.items()))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
