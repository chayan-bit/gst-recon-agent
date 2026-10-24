"""Arithmetic check and repair of a per-document record: code, not the model, owns the rupee arithmetic.

GST tax on a line is taxable x rate, as IGST (inter-state) or half each CGST + SGST (intra-state, supplier
state = place of supply), rounded half-up to 2 dp per head; the header is the sum of the lines; the total is
taxable + tax (taxable only under reverse charge). The model reads the printed values; where its reading
breaks these identities by more than Rs 1, the values are recomputed from the parts it read (taxable value
and rate), or the rate is corrected when the heads it read fit a standard rate exactly. Records that already
satisfy the identities, e.g. true records, are returned unchanged. Every change goes to the trace.
"""

from __future__ import annotations

from gst_recon.hybrid.docschema import HEADS, DocLine, DocRecord
from gst_recon.sim.money import r2, split_tax
from gst_recon.sim.rules import AMOUNT_TOLERANCE

RATES = (0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0, 40.0)
_DIGIT = str.maketrans({"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2", "L": "1"})


def _off(a: float, b: float) -> bool:
    return abs(a - b) > AMOUNT_TOLERANCE


def _intra(rec: DocRecord, line: DocLine) -> bool:
    if line.igst and not (line.cgst or line.sgst):
        return False
    if (line.cgst or line.sgst) and not line.igst:
        return True
    return rec.supplier_gstin.strip().upper()[:2].translate(_DIGIT) == rec.place_of_supply.strip()[:2]


def _header_rate(rec: DocRecord) -> float | None:
    tax = sum(getattr(rec, h) for h in HEADS if h != "cess")
    return next((r for r in RATES if rec.taxable_value and not _off(tax, rec.taxable_value * r / 100)), None)


def _repair_line(rec: DocRecord, li: DocLine) -> tuple[DocLine, str]:
    intra = _intra(rec, li)
    tax = li.igst + li.cgst + li.sgst
    valid_split = not (li.igst and (li.cgst or li.sgst)) and not (intra and _off(li.cgst, li.sgst))
    if valid_split and not _off(tax, li.taxable_value * li.rate / 100):
        return li, ""
    if valid_split and li.taxable_value:
        fit = [r for r in RATES if not _off(tax, li.taxable_value * r / 100)]
        if fit:
            return li.model_copy(update={"rate": fit[0]}), f"rate {li.rate:g} -> {fit[0]:g} (tax read fits it)"
    rate, why = li.rate, ""
    if rate not in RATES:  # a misread rate (e.g. an amount in the rate cell) must not mint tax from taxable x rate
        rate = _header_rate(rec)
        if rate is None:
            return li, f"rate {li.rate:g} not a GST rate and the header fits none: heads kept as read"
        why = f"rate {li.rate:g} -> {rate:g} (header rate), "
    igst, cgst, sgst = split_tax(li.taxable_value, rate, intra)
    return (li.model_copy(update={"rate": rate, "igst": igst, "cgst": cgst, "sgst": sgst}),
            f"{why}heads recomputed from taxable x {rate:g}% ({'intra' if intra else 'inter'}-state)")


def repair(rec: DocRecord) -> tuple[DocRecord, list[str]]:
    notes, lines = [], []
    for i, li in enumerate(rec.line_items, 1):
        new, why = _repair_line(rec, li)
        lines.append(new)
        if why:
            notes.append(f"line {i}: {why}")
    upd: dict = {"line_items": lines}
    sums = {f: r2(sum(getattr(li, f) for li in lines)) for f in ("taxable_value", *HEADS)}
    if lines and not _off(sums["taxable_value"], rec.taxable_value):  # header taxable agrees: lines are complete
        for h in HEADS:
            if _off(getattr(rec, h), sums[h]):
                upd[h] = sums[h]
                notes.append(f"header {h} {getattr(rec, h):.2f} -> sum of lines {sums[h]:.2f}")
        tax = sum(upd.get(h, getattr(rec, h)) for h in HEADS)
        total = r2(rec.taxable_value + (0 if rec.reverse_charge else tax))
        if _off(rec.total, total):
            upd["total"] = total
            notes.append(f"total {rec.total:.2f} -> {total:.2f}")
    return rec.model_copy(update=upd), notes
