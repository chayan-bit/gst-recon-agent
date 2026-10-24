"""OCR-recall check: which ground-truth key values can still be read from the text?

Per document we list key facts (invoice no, supplier GSTIN, date, header amounts,
line HSN codes and taxable values, original invoice no for credit notes). A fact is

- `found`: present in that document's OCR text (light normalisation), or
- `recoverable`: not in the OCR text but present in the other prompt sections
  (register / GSTR-2B / bank), so a reader could still get it, or
- `lost`: in neither. Lost facts are the ones the model cannot be blamed for.

Normalisation: ids compare alphanumerics only with O/0 and I/1 folded; amounts
compare digit tokens with `,` `.` separators ignored (OCR swaps them); dates ignore
spacing and `/ . -` differences; HSN codes need digit boundaries.
Caveat: "recoverable elsewhere" is a substring/token test over whole sections, so a
short number can match by coincidence; ids and 2-dp amounts make that rare.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gst_recon.render.fmt import DATE_FORMATS, fmt_date
from gst_recon.schema import TruthInvoice

_FOLD = str.maketrans({"O": "0", "I": "1"})
_NUM = re.compile(r"\d[\d,.]*\d|\d")


@dataclass(frozen=True)
class Fact:
    name: str
    kind: str  # id | amount | date | hsn | text
    value: str  # canonical text of the fact
    alts: tuple[str, ...] = ()  # other spellings to look for in other sections


def _amount_fact(name: str, x: float) -> Fact:
    return Fact(name, "amount", f"{x:.2f}")


def doc_facts(inv: TruthInvoice, shown_date: str) -> list[Fact]:
    facts = [Fact("invoice_no", "id", inv.invoice_no), Fact("supplier_gstin", "id", inv.supplier_gstin),
             Fact("invoice_date", "date", shown_date, tuple(fmt_date(inv.invoice_date, f) for f in (*DATE_FORMATS, "YYYY-MM-DD"))),
             _amount_fact("taxable_value", inv.taxable_value), _amount_fact("total", inv.total)]
    facts += [_amount_fact(h, getattr(inv, h)) for h in ("igst", "cgst", "sgst", "cess") if getattr(inv, h) > 0]
    if inv.original_invoice_no:
        facts.append(Fact("original_invoice_no", "id", inv.original_invoice_no))
    if getattr(inv, "remarks", ""):
        facts.append(Fact("remarks", "text", inv.remarks))
    for i, l in enumerate(inv.line_items):
        facts += [Fact(f"line{i}_hsn", "hsn", l.hsn), _amount_fact(f"line{i}_taxable", l.taxable_value)]
    return facts


def _alnum(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper()).translate(_FOLD)


def _digit_tokens(text: str) -> set[str]:
    return {re.sub(r"[,.]", "", t) for t in _NUM.findall(text)}


def _date_key(text: str) -> str:
    return re.sub(r"[\s/.\-]", "", text.lower())


@dataclass
class Index:
    """Pre-normalised view of a text for repeated fact lookups."""

    alnum: str
    tokens: set[str]
    datekey: str
    raw: str

    @classmethod
    def of(cls, text: str) -> "Index":
        return cls(_alnum(text), _digit_tokens(text), _date_key(text), text)


def present(f: Fact, ix: Index) -> bool:
    if f.kind == "id":
        return _alnum(f.value) in ix.alnum
    if f.kind == "amount":
        cents = str(round(float(f.value) * 100))
        return cents in ix.tokens or (cents.endswith("00") and cents[:-2] in ix.tokens)
    if f.kind == "date":
        return any(_date_key(v) in ix.datekey for v in (f.value, *f.alts))
    if f.kind == "text":  # free text: most of its words must be readable
        words = {w for w in re.findall(r"[a-z]{4,}", f.value.lower())}
        have = set(re.findall(r"[a-z]{4,}", ix.raw.lower()))
        return not words or len(words & have) / len(words) >= 0.7
    return re.search(rf"(?<!\d){re.escape(f.value)}(?!\d)", ix.raw) is not None


@dataclass
class DocRecall:
    doc_id: str
    found: int
    total: int
    lost: list[str] = field(default_factory=list)  # fact names in neither OCR text nor other sections
    missing_in_ocr: list[str] = field(default_factory=list)


def check_doc(doc_id: str, facts: list[Fact], ocr_text: str, rest: Index) -> DocRecall:
    ix = Index.of(ocr_text)
    missing = [f for f in facts if not present(f, ix)]
    # a fact is only "recoverable elsewhere" through its other-section spellings
    lost = [f.name for f in missing if not _elsewhere(f, rest)]
    taxable_lost = [n for n in lost if n.startswith("line") and n.endswith("_taxable")]
    if len(taxable_lost) == 1 and "taxable_value" not in {f.name for f in missing}:
        lost.remove(taxable_lost[0])  # derivable: header taxable value minus the other readable lines
    return DocRecall(doc_id, len(facts) - len(missing), len(facts), lost, [f.name for f in missing])


def _elsewhere(f: Fact, rest: Index) -> bool:
    if f.kind in ("hsn", "text") or f.name.startswith("line"):
        return False  # only invoices carry HSN codes and per-line values
    return present(f, rest)


def case_recall(docs: list[DocRecall], scanned: set[str]) -> dict:
    tot = sum(d.total for d in docs) or 1
    sc = [d for d in docs if d.doc_id in scanned]
    sc_tot = sum(d.total for d in sc)
    return {
        "ocr_recall": round(sum(d.found for d in docs) / tot, 4),
        "ocr_recall_scanned": round(sum(d.found for d in sc) / sc_tot, 4) if sc_tot else None,
        "doc_recall": {d.doc_id: round(d.found / d.total, 3) for d in docs},
        "unrecoverable": [{"doc_id": d.doc_id, "facts": d.lost} for d in docs if d.lost],
        "has_unrecoverable": any(d.lost for d in docs),
    }
