"""Error attribution of a hybrid run by field-group oracle swaps, and how many wrong fields the input text even holds.

    python scripts/hybrid_error_attribution.py --cases CASE_ROOT... --truth TRUTH_ROOT --run NAME=RUN_DIR ...

Evaluation only (reads truth); no model calls; prints aggregates only, never document text.
1. Oracle ablation: every parsed record of the run gets one field group replaced by the labelled truth, the case is
   re-reconciled by reconciler v3 (`reconcile_prompt`) and re-scored (`eval_metrics`); case means of ITC invoice
   exact, match accuracy and composite per variant, and the share of the gap to all-truth records each closes.
   Groups: identity (GSTIN, invoice number, date), amounts (header and line taxable, rate, tax heads, total),
   judgment (line itc_category and purpose, reverse_charge, place_of_supply, doc_type).
2. Input-limited share: every wrong copy field (identity and header amounts) of a parsed record is recoverable from
   the document text or not (GSTIN and number look-alike folded, dates in any parseable style, amounts within Rs 1;
   a true amount of 0 counts as recoverable; an identity value whose truth is "" is its own kind, "truth empty"),
   and how many of those the other runs got right.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gst_recon.hybrid.docschema import HEADS, DocRecord  # noqa: E402
from gst_recon.hybrid.inputs import parse_date, split_docs, split_sections  # noqa: E402
from gst_recon.hybrid.reconcile import reconcile_prompt  # noqa: E402
from gst_recon.hybrid.run import parse_doc  # noqa: E402
from gst_recon.hybrid.sft import truth_records  # noqa: E402
from gst_recon.rewards.doc import _same, visible  # noqa: E402
from gst_recon.rewards.metrics import eval_metrics  # noqa: E402
from gst_recon.schema import Case  # noqa: E402

METRICS = ("itc_invoice", "match_accuracy", "composite")
IDENTITY = ("supplier_gstin", "invoice_no", "invoice_date")
AMOUNTS = ("taxable_value", *HEADS, "total")
LINE_AMOUNTS = ("taxable_value", "rate", *HEADS)
JUDGMENT = ("reverse_charge", "place_of_supply", "doc_type")
VARIANTS = ("model", "identity", "amounts", "judgment", "identity+amounts", "all three", "all truth")
TOL = 1.0  # rupees
_DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[-/. ](?:[A-Za-z]{3}|\d{1,2})[-/. ](?:\d{4}|\d{2})")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def patch(m: DocRecord, t: DocRecord, groups: tuple[str, ...]) -> DocRecord:
    """m with the true values of the named groups; lines align by index, and a line-count misread is fixed only by
    the amounts group (true lines, keeping the model's judgments where it has that line)."""
    upd = {f: getattr(t, f) for g, fs in (("identity", IDENTITY), ("amounts", AMOUNTS), ("judgment", JUDGMENT)) if g in groups for f in fs}
    judge = lambda ml, tl: {"itc_category": tl.itc_category, "purpose": tl.purpose} if "judgment" in groups else {}  # noqa: E731
    lines = list(m.line_items)
    if "amounts" in groups and len(lines) != len(t.line_items):
        lines = [tl if i >= len(lines) else tl.model_copy(update={"itc_category": lines[i].itc_category, "purpose": lines[i].purpose, **judge(lines[i], tl)})
                 for i, tl in enumerate(t.line_items)]
    else:
        amounts = lambda tl: {f: getattr(tl, f) for f in LINE_AMOUNTS} if "amounts" in groups else {}  # noqa: E731
        lines = [ml.model_copy(update={**judge(ml, tl), **amounts(tl)}) for ml, tl in zip(lines, t.line_items)] + lines[len(t.line_items):]
    return m.model_copy(update={**upd, "line_items": lines})


def right(field: str, pred, truth) -> bool:
    if field in IDENTITY:
        return _same(field, str(pred), str(truth)) or (not str(truth).strip() and not str(pred).strip())
    return abs(float(pred) - float(truth)) <= TOL


def recoverable(field: str, truth, text: str) -> bool:
    """Whether the document text holds the true value (normalised; see the module docstring)."""
    if field in AMOUNTS:
        return float(truth) == 0 or any(abs(float(n.replace(",", "")) - float(truth)) <= TOL for n in _NUM.findall(text))
    if field == "invoice_date":
        for d in _DATE.findall(text):
            try:
                if parse_date(d) == parse_date(str(truth)):
                    return True
            except (ValueError, KeyError):
                continue
    return bool(str(truth).strip()) and visible(field, str(truth), text)


def load_records(run: Path, case_id: str) -> dict[str, DocRecord]:
    out = {}
    for f in sorted((run / "docs" / case_id).glob("*.json")):
        r = json.loads(f.read_text())
        rec, _ = parse_doc(r.get("text") or "") if not r.get("error") else (None, "")
        if rec is not None:
            out[f.stem] = rec
    return out


def score(prompt: str, case: Case, records: dict[str, DocRecord]) -> dict[str, float]:
    out, _ = reconcile_prompt(prompt, records)
    m = eval_metrics(out.model_dump_json(), case)
    return {k: m[k] for k in METRICS}


def variants(model: dict[str, DocRecord], truth: dict[str, DocRecord]) -> dict[str, dict[str, DocRecord]]:
    swap = lambda gs: {d: patch(r, truth[d], gs) if d in truth else r for d, r in model.items()}  # noqa: E731
    return {"model": model, "identity": swap(("identity",)), "amounts": swap(("amounts",)), "judgment": swap(("judgment",)),
            "identity+amounts": swap(("identity", "amounts")), "all three": swap(("identity", "amounts", "judgment")), "all truth": truth}


def field_errors(model: dict[str, DocRecord], truth: dict[str, DocRecord], blocks: dict[str, str], others: dict[str, dict[str, DocRecord]]) -> Counter:
    c = Counter()
    for d, t in truth.items():
        m = model.get(d)
        if m is None:
            c["unparsed docs"] += 1
            continue
        for f in (*IDENTITY, *AMOUNTS):
            if right(f, getattr(m, f), getattr(t, f)):
                continue
            tv = getattr(t, f)
            kind = ("truth empty" if f in IDENTITY and not str(tv).strip()
                    else "model-limited" if recoverable(f, tv, blocks.get(d, "")) else "input-limited")
            grp = "identity" if f in IDENTITY else "amounts"
            c[f"wrong {grp}"] += 1
            c[f"wrong {grp} {kind}"] += 1
            c[f"field {f} {kind}"] += 1
            for name, o in others.items():
                c[f"wrong {grp} {kind}, {name} right"] += d in o and right(f, getattr(o[d], f), getattr(t, f))
        n = min(len(m.line_items), len(t.line_items))
        c["lines"] += len(t.line_items)
        c["line count wrong"] += len(m.line_items) != len(t.line_items)
        c["line judgment wrong"] += sum((ml.itc_category, ml.purpose) != (tl.itc_category, tl.purpose) for ml, tl in zip(m.line_items[:n], t.line_items[:n]))
        c["doc judgment wrong"] += sum(getattr(m, f) != getattr(t, f) for f in JUDGMENT)
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, nargs="+", required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--run", action="append", required=True, help="NAME=RUN_DIR (holding docs/<case>/<doc>.json)")
    a = ap.parse_args()
    runs = {n: Path(p) for n, p in (r.split("=", 1) for r in a.run)}
    dirs = {p.parent.name: p.parent for r in a.cases for p in r.glob("*/target.json")}
    sums = {n: {v: Counter() for v in VARIANTS} for n in runs}
    errs = {n: Counter() for n in runs}
    stored = {n: {r["case_id"]: r["metrics"] for r in map(json.loads, (p / "scores.jsonl").read_text().splitlines())} for n, p in runs.items() if (p / "scores.jsonl").exists()}
    mismatch, cases = Counter(), 0
    for case_id, d in sorted(dirs.items()):
        tj = next(a.truth.glob(f"*/{case_id}.json"), None) or a.truth / f"{case_id}.json"
        case = Case.model_validate_json(tj.read_text())
        prompt, target = (d / "prompt.txt").read_text(), json.loads((d / "target.json").read_text())
        truth = truth_records(target, case)
        blocks = {s.doc_id: s.text for s in split_docs(split_sections(prompt)["INVOICES"])}
        models = {n: load_records(p, case_id) for n, p in runs.items()}
        cases += 1
        for n, model in models.items():
            for v, recs in variants(model, truth).items():
                s = score(prompt, case, recs)
                sums[n][v].update(s)
                if v == "model" and n in stored and case_id in stored[n]:
                    mismatch[n] += any(abs(s[k] - stored[n][case_id][k]) > 1e-9 for k in METRICS)
            errs[n] += field_errors(model, truth, blocks, {o: models[o] for o in models if o != n})
    for n in runs:
        mean = {v: {k: 100 * sums[n][v][k] / cases for k in METRICS} for v in VARIANTS}
        gap = {k: mean["all truth"][k] - mean["model"][k] for k in METRICS}
        rows = {v: {k: f"{mean[v][k]:.1f}" + (f" ({100 * (mean[v][k] - mean['model'][k]) / gap[k]:.0f}% of gap)" if gap[k] and v != "model" else "") for k in METRICS} for v in VARIANTS}
        print(json.dumps({"run": n, "cases": cases, "stored score mismatches": mismatch[n], "ablation": rows, "field errors": dict(sorted(errs[n].items()))}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
