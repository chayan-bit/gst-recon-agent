"""Self-consistency for hybrid mode: per-field majority vote over k sampled runs of the same documents.

    python scripts/hybrid_vote.py OUT_RUN_DIR SAMPLE_RUN_DIR... [--identity-quorum Q]

Writes <OUT>/docs/<case>/<doc>.json with the voted record as the reply text, so that
`python -m gst_recon.eval run --mode hybrid --out OUT --no-resume ...` reconciles and scores it with no model
calls. Vote: the line count is the modal count among parseable samples; every scalar field and every line
field (among samples with that line count) takes its most frequent value. Identity fields (GSTIN, invoice
no, date, original no) take "" when no value reaches the quorum (default: a strict plurality, ties -> "").
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from gst_recon.hybrid.docschema import DocRecord
from gst_recon.hybrid.run import parse_doc

IDENTITY = ("supplier_gstin", "invoice_no", "invoice_date", "original_invoice_no")


def _mode(values: list, quorum: int | None = None, empty=None):
    (top, n), *rest = Counter(json.dumps(v, sort_keys=True) for v in values).most_common() + [(None, 0)]
    tied = rest and rest[0][1] == n
    if empty is not None and (tied or (quorum and n < quorum)):
        return empty
    return json.loads(top)


def vote(records: list[DocRecord], quorum: int | None) -> DocRecord:
    dicts = [r.model_dump(mode="json") for r in records]
    n_lines = _mode([len(d["line_items"]) for d in dicts])
    same = [d for d in dicts if len(d["line_items"]) == n_lines]
    out = {k: _mode([d[k] for d in dicts], quorum, "" if k in IDENTITY else None) for k in dicts[0] if k != "line_items"}
    out["line_items"] = [{k: _mode([d["line_items"][i][k] for d in same]) for k in same[0]["line_items"][i]} for i in range(n_lines)]
    return DocRecord.model_validate(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("samples", type=Path, nargs="+")
    ap.add_argument("--identity-quorum", type=int, default=None)
    a = ap.parse_args()
    n = 0
    for case_dir in sorted((a.samples[0] / "docs").iterdir()):
        for f in sorted(case_dir.glob("*.json")):
            replies = [json.loads(p.read_text()) for s in a.samples if (p := s / "docs" / case_dir.name / f.name).exists()]
            recs = [r for r in (parse_doc(x.get("text") or "")[0] for x in replies) if r is not None]
            text = vote(recs, a.identity_quorum).model_dump_json() if recs else ""
            dst = a.out / "docs" / case_dir.name / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps({"text": text, "error": None, "finish_reason": "stop", "n_samples": len(recs),
                                       "prompt_tokens": sum(x.get("prompt_tokens") or 0 for x in replies),
                                       "completion_tokens": sum(x.get("completion_tokens") or 0 for x in replies)}))
            n += 1
    print(f"voted {n} documents from {len(a.samples)} sample runs into {a.out}")


if __name__ == "__main__":
    main()
