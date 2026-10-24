"""Root-cause attribution of wrong ITC invoices in a hybrid run (evaluation only: reads truth).

    python scripts/hybrid_attribution.py RUN_DIR TRUTH_ROOT CASE_ROOT...

For every document whose 12 ITC amounts miss the target (the scorer's own itc_invoice test), the model's
record for that document alone is patched with the true values of one field group at a time and the case
is re-reconciled; the first group that fixes it is the cause (then pairs; else "several"). Groups:
identity (GSTIN, invoice no, date, type, original no, place of supply, reverse charge), judgment (line
category and purpose), amounts (lines and header figures). A wrong document whose record already equals the
truth is a reconciler or cross-document cause. Identity causes are split by whether the true value is
printed in the document's OCR text at all ("ocr_lost"). Rs impact = |predicted - true| eligible ITC.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from gst_recon.hybrid.docschema import HEADS, DocRecord
from gst_recon.hybrid.inputs import split_docs, split_sections
from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.hybrid.run import parse_doc
from gst_recon.hybrid.sft import truth_records
from gst_recon.rewards.scoring import _itc_close
from gst_recon.schema import Case

IDENTITY = ("supplier_gstin", "invoice_no", "invoice_date", "doc_type", "original_invoice_no", "place_of_supply", "reverse_charge")
AMOUNTS = ("taxable_value", *HEADS, "total")
GROUPS = ("identity", "judgment", "amounts")


def _patch(m: DocRecord, t: DocRecord, groups: tuple[str, ...]) -> DocRecord:
    upd: dict = {}
    if "identity" in groups:
        upd |= {f: getattr(t, f) for f in IDENTITY}
    if "amounts" in groups:
        upd |= {f: getattr(t, f) for f in AMOUNTS}
    lines = list(m.line_items)
    if len(lines) != len(t.line_items):  # line count misread: only a full-line swap can fix it
        if "amounts" in groups:
            lines = [tl if "judgment" in groups or i >= len(lines) else tl.model_copy(update={"itc_category": lines[i].itc_category, "purpose": lines[i].purpose})
                     for i, tl in enumerate(t.line_items)]
    else:
        lines = [ml.model_copy(update={**({"itc_category": tl.itc_category, "purpose": tl.purpose} if "judgment" in groups else {}),
                                       **({f: getattr(tl, f) for f in ("taxable_value", "rate", *HEADS)} if "amounts" in groups else {})})
                 for ml, tl in zip(lines, t.line_items)]
    return m.model_copy(update={**upd, "line_items": lines})


def _differs(m: DocRecord, t: DocRecord, group: str) -> bool:
    return _patch(m, t, (group,)) != m


def _eligible(row: dict) -> float:
    return sum((row.get("eligible") or {}).get(h, 0.0) for h in HEADS)


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def attribute_case(prompt: str, target: dict, case: Case, model: dict[str, DocRecord]) -> list[dict]:
    truth = truth_records(target, case)
    blocks = {d.doc_id: d.block for d in split_docs(split_sections(prompt)["INVOICES"])}
    t_itc = {r["doc_id"]: r for r in target["itc"]}

    def itc_of(records):
        out, _ = reconcile_prompt(prompt, records)
        return {r.doc_id: r.model_dump(mode="json") for r in out.itc}

    base = itc_of(model)
    rows = []
    for doc, t in t_itc.items():
        p = base.get(doc)
        if p is not None and _itc_close(p, t):
            continue
        rs = abs(_eligible(p or {}) - _eligible(t))
        if doc not in model:
            rows.append({"doc": doc, "cause": "no_reply", "rs": rs})
            continue
        m, tr = model[doc], truth[doc]
        cands = [g for g in GROUPS if _differs(m, tr, g)]
        cause = "reconciler_or_cross_doc" if not cands else "several"
        for k in (1, 2):
            hit = next((c for c in combinations(cands, k) if _itc_close(itc_of({**model, doc: _patch(m, tr, c)}).get(doc) or {}, t)), None)
            if hit:
                cause = "+".join(hit)
                break
        if cause.startswith("identity"):
            txt = _norm(blocks.get(doc, ""))
            lost = [f for f in ("supplier_gstin", "invoice_no") if getattr(m, f) != getattr(tr, f) and _norm(str(getattr(tr, f))) not in txt]
            cause += " (ocr_lost)" if lost else " (misread)"
        rows.append({"doc": doc, "cause": cause, "rs": rs,
                     "fields": [f for f in IDENTITY if getattr(m, f) != getattr(tr, f)]})
    return rows


def main(run: Path, truth_root: Path, roots: list[Path]) -> dict:
    dirs = {p.parent.name: p.parent for r in roots for p in r.glob("*/target.json")}
    count, rs, fields = Counter(), defaultdict(float), Counter()
    n_docs = 0
    for case_id, d in sorted(dirs.items()):
        tj = next(truth_root.glob(f"*/{case_id}.json"), None)
        if tj is None or not (run / "docs" / case_id).exists():
            continue
        case = Case.model_validate_json(tj.read_text())
        target = json.loads((d / "target.json").read_text())
        model = {}
        for f in (run / "docs" / case_id).glob("*.json"):
            rec, _ = parse_doc(json.loads(f.read_text()).get("text") or "")
            if rec is not None:
                model[f.stem] = rec
        n_docs += len(target["itc"])
        for r in attribute_case((d / "prompt.txt").read_text(), target, case, model):
            count[r["cause"]] += 1
            rs[r["cause"]] += r["rs"]
            fields.update(r.get("fields", []))
    return {"docs": n_docs, "wrong": sum(count.values()), "by_cause": dict(count.most_common()),
            "rs_by_cause": {k: round(v) for k, v in sorted(rs.items(), key=lambda x: -x[1])}, "identity_fields_wrong": dict(fields.most_common())}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]]), indent=1))
