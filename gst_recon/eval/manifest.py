"""Manifest of the frozen eval sets: ids, seeds, hashes and render settings, never the data itself.

    python -m gst_recon.eval.manifest write  --rendered data/eval/rendered --out gst_recon/eval/eval_sets_manifest.json \
        --seed test_iid=9001 --seed test_ood=9002 --command "<generation command>"
    python -m gst_recon.eval.manifest verify --rendered data/eval/rendered --manifest gst_recon/eval/eval_sets_manifest.json

`verify` exits non-zero if any case is missing, extra or has a different prompt/target hash, so a regenerated or
re-rendered set cannot silently replace the frozen one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from gst_recon.eval.cases import EvalCase

LENGTH_ORDER = ("<=16k", "16-32k", ">32k")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_entry(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text())
    ec = EvalCase(d.name, "", {}, meta)
    return {"case_id": d.name, "difficulty": meta.get("difficulty"), "seed": meta.get("seed"), "ocr_recall": meta.get("ocr_recall"),
            "prompt_tokens": meta.get("prompt_tokens"), "target_tokens": meta.get("target_tokens"), "length_bucket": ec.length_bucket,
            "fits_context_32k": meta.get("fits_context"), "prompt_sha256": _sha(d / "prompt.txt"), "target_sha256": _sha(d / "target.json")}


def build(rendered: Path, seeds: dict[str, int], command: str = "") -> dict:
    splits, engines, versions = {}, set(), set()
    for sdir in sorted(p for p in Path(rendered).iterdir() if p.is_dir()):
        cases = [_case_entry(c) for c in sorted(sdir.iterdir()) if (c / "meta.json").exists()]
        for c in cases:
            m = json.loads((sdir / c["case_id"] / "meta.json").read_text())
            engines.add(m.get("ocr_engine"))
            versions.add(m.get("render_version"))
        splits[sdir.name] = {
            "seed": seeds.get(sdir.name), "n_cases": len(cases),
            "by_difficulty": dict(Counter(c["difficulty"] for c in cases)),
            "by_length_bucket": {b: sum(c["length_bucket"] == b for c in cases) for b in LENGTH_ORDER},
            "mean_ocr_recall": round(sum(c["ocr_recall"] or 0 for c in cases) / max(1, len(cases)), 4),
            "cases": cases}
    return {"description": "frozen eval sets; data lives outside git (data/eval/), this file pins it", "command": command,
            "ocr_engines": sorted(map(str, engines)), "render_versions": sorted(map(str, versions)), "splits": splits}


def verify(rendered: Path, manifest: dict) -> list[str]:
    now = build(rendered, {})
    problems = []
    for split, spec in manifest["splits"].items():
        have = {c["case_id"]: c for c in now["splits"].get(split, {"cases": []})["cases"]}
        want = {c["case_id"]: c for c in spec["cases"]}
        problems += [f"{split}: missing {i}" for i in sorted(want.keys() - have.keys())]
        problems += [f"{split}: extra {i}" for i in sorted(have.keys() - want.keys())]
        problems += [f"{split}: {i} content changed" for i in sorted(want.keys() & have.keys())
                     if (want[i]["prompt_sha256"], want[i]["target_sha256"]) != (have[i]["prompt_sha256"], have[i]["target_sha256"])]
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.eval.manifest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--rendered", type=Path, required=True)
    w.add_argument("--out", type=Path, required=True)
    w.add_argument("--seed", action="append", default=[], metavar="SPLIT=SEED")
    w.add_argument("--command", default="")
    v = sub.add_parser("verify")
    v.add_argument("--rendered", type=Path, required=True)
    v.add_argument("--manifest", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "write":
        seeds = {k: int(v) for k, v in (s.split("=") for s in a.seed)}
        m = build(a.rendered, seeds, a.command)
        a.out.write_text(json.dumps(m, indent=1) + "\n")
        print(f"wrote {a.out}: " + ", ".join(f"{k} {v['n_cases']} cases" for k, v in m["splits"].items()) + f"; engines {m['ocr_engines']}")
        return 0
    problems = verify(a.rendered, json.loads(a.manifest.read_text()))
    print("\n".join(problems) or "manifest verified")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
