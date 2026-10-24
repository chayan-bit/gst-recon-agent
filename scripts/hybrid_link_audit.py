"""Count link errors of a run against target.json: links made that the target does not have (false) and
target links not made (missed), for register vouchers, the GSTR-2B entry and bank payments.

    python scripts/hybrid_link_audit.py RUN_DIR CASE_DIR_ROOT...

Reads <RUN_DIR>/cases/<case_id>.json ("parsed") and <root>/<case_id>/target.json. Evaluation only: it reads
targets, so nothing in gst_recon/hybrid may import it.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _links(m: dict) -> set[tuple]:
    out = {("register", v) for v in m.get("register_vouchers") or []}
    out |= {("payment", p) for p in m.get("payment_refs") or []}
    if m.get("gstr2b_doc_no"):
        out.add(("gstr2b", m.get("gstr2b_period"), m.get("gstr2b_ctin"), m["gstr2b_doc_no"]))
    return out


def audit(run: Path, roots: list[Path]) -> Counter:
    targets = {p.parent.name: p for r in roots for p in r.glob("*/target.json")}
    c: Counter = Counter()
    for f in sorted((run / "cases").glob("*.json")):
        rec = json.loads(f.read_text())
        if rec["case_id"] not in targets or not rec.get("parsed"):
            continue
        truth = {m["doc_id"]: _links(m) for m in json.loads(targets[rec["case_id"]].read_text())["matches"]}
        pred = {m["doc_id"]: _links(m) for m in rec["parsed"]["matches"]}
        c["cases"] += 1
        for doc, t in truth.items():
            p = pred.get(doc, set())
            for kind in ("register", "gstr2b", "payment"):
                tk, pk = {x for x in t if x[0] == kind}, {x for x in p if x[0] == kind}
                c[f"{kind}_true"] += len(tk)
                c[f"{kind}_false"] += len(pk - tk)
                c[f"{kind}_missed"] += len(tk - pk)
    return c


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]), indent=1))
