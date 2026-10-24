"""Code half of the hybrid pipeline: per-document records in, full ReconOutput plus an audit trace out.

ANTI-CHEAT: `reconcile_prompt` receives the prompt text and the per-document records only. It opens no
file, and nothing in this package imports the eval case loader, target.json, meta.json or truth Case JSON
(tests/hybrid/test_anticheat.py enforces both).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from gst_recon.hybrid.fill import fill_identity
from gst_recon.hybrid.docschema import HEADS, DocRecord, invoice_date, to_extraction, to_truth_invoice
from gst_recon.hybrid.inputs import PromptParts, parse_prompt
from gst_recon.hybrid.linker import lev, link_documents
from gst_recon.hybrid.repair import repair
from gst_recon.schema import CaseInputs, DocType, ItcCategory, Party, ReconOutput, TruthInvoice
from gst_recon.sim import rules
from gst_recon.sim.gstin import is_valid_gstin

GOODS_VEHICLE_HSN = "8704"  # s.17(5)(a) blocks motor vehicles for transport of persons; goods vehicles are outside it


def _goods_vehicles(rec: DocRecord) -> tuple[DocRecord, list[str]]:
    """A line read as motor_vehicle but printed with HSN 8704 (goods vehicle) is not a s.17(5)(a) vehicle."""
    notes, lines = [], []
    for i, li in enumerate(rec.line_items, 1):
        if li.itc_category == ItcCategory.MOTOR_VEHICLE and li.hsn.strip().startswith(GOODS_VEHICLE_HSN):
            li = li.model_copy(update={"itc_category": ItcCategory.NORMAL})
            notes.append(f"line {i}: HSN {li.hsn} is a goods vehicle: motor_vehicle -> normal")
        lines.append(li)
    return (rec.model_copy(update={"line_items": lines}) if notes else rec), notes


def _gstin_fix(inv: TruthInvoice, link: rules.Link, inputs: CaseInputs, twob: dict) -> str | None:
    """An invoice GSTIN that fails the mod-36 check digit is a misread: take the valid GSTIN of the linked
    GSTR-2B entry (else of a linked register row) when it is within 2 edits and differs either in the state code
    or in the rest, never both (another state's registration with a misread check digit is not a misread of
    this one). A valid GSTIN is never changed, so a real registration under another GSTIN (same PAN, other
    state) still shows as gstin_mismatch."""
    if is_valid_gstin(inv.supplier_gstin):
        return None
    regs = {r.voucher_no: r for r in inputs.purchase_register}
    entry = twob.get(link.gstr2b) if link.gstr2b else None
    cands = ([entry.ctin] if entry else []) + [regs[v].party_gstin.upper() for v in link.register_vouchers if v in regs]
    read = inv.supplier_gstin.strip().upper()
    return next((g for g in cands if is_valid_gstin(g) and (g[:2] == read[:2] or g[2:] == read[2:]) and lev(g, read) <= 2), None)


def _explain(inv: TruthInvoice, inputs: CaseInputs, link: rules.Link, twob: dict, out_row, itc_row) -> dict:
    """Why each flag and ITC amount came out as it did, from the same rule functions."""
    entry = twob.get(link.gstr2b) if link.gstr2b else None
    why: dict = {"flags": [f.value for f in out_row.flags], "reasons": [r.value for r in itc_row.reasons]}
    if entry is None:
        why["gstr2b"] = "no GSTR-2B entry linked"
    else:
        why["gstr2b"] = {"period": entry.period, "case_period": inputs.period, "ctin": entry.ctin, "invoice_gstin": inv.supplier_gstin,
                         "taxable": [inv.taxable_value, entry.taxable], **{h: [getattr(inv, h), entry.heads[h]] for h in HEADS}}
    regs = {r.voucher_no: r for r in inputs.purchase_register}
    why["register"] = [{"voucher": v, "gstin": regs[v].party_gstin, "taxable": regs[v].taxable_value, "total": regs[v].total}
                       for v in link.register_vouchers if v in regs]
    if inv.doc_type == DocType.INVOICE and not inv.reverse_charge:
        days = (inputs.as_of_date - inv.invoice_date).days
        why["payment"] = {"days_since_invoice": days, "outstanding": rules.outstanding(inv, inputs, link),
                          "total": inv.total, "unpaid_180d": rules.is_unpaid_180d(inv, inputs, link)}
    why["lines"] = [{"description": li.description, "itc_category": li.category.value, "purpose": li.purpose.value,
                     "block": (r.value if (r := rules.line_block_reason(li, inputs.buyer_profile)) else None)}
                    for li in inv.line_items]
    return why


def _inputs(parts: PromptParts, invoices: list[TruthInvoice]) -> CaseInputs:
    h = parts.header
    return CaseInputs(buyer=Party(name=h.buyer_name, gstin=h.buyer_gstin, state_code=h.buyer_state, address=""),
                      buyer_profile=h.profile, period=h.period, as_of_date=h.as_of, invoices=invoices,
                      purchase_register=parts.register, gstr2b=parts.gstr2b, bank_statement=parts.bank)


def reconcile_prompt(prompt: str, records: Mapping[str, DocRecord]) -> tuple[ReconOutput, dict]:
    """Assemble the case output from prompt.txt and the per-document records (doc_id -> record).
    Documents without a record (the model call failed) are left out of the output."""
    parts = parse_prompt(prompt)
    h = parts.header
    period_start = date(int(h.period[2:]), int(h.period[:2]), 1)
    trace: dict = {"missing_records": [d.doc_id for d in parts.docs if d.doc_id not in records], "bad_dates": [], "repairs": {}}
    fixed = {}
    for doc_id, rec in records.items():
        rec, law = _goods_vehicles(rec)
        fixed[doc_id], notes = repair(rec)
        notes = law + notes
        if notes:
            trace["repairs"][doc_id] = notes
    records = fixed
    trace["fills"] = {}
    for d in parts.docs:
        if d.doc_id in records:
            records[d.doc_id], notes = fill_identity(records[d.doc_id], d.text, parts.register, parts.gstr2b)
            if notes:
                trace["fills"][d.doc_id] = notes
    invoices = []
    for d in parts.docs:
        rec = records.get(d.doc_id)
        if rec is None:
            continue
        when, ok = invoice_date(rec, period_start)
        if not ok:
            trace["bad_dates"].append({"doc_id": d.doc_id, "model_date": rec.invoice_date, "used": when.isoformat()})
        invoices.append(to_truth_invoice(d.doc_id, rec, buyer_gstin=h.buyer_gstin, buyer_name=h.buyer_name, when=when))
    inputs = _inputs(parts, invoices)
    links, link_trace = link_documents(inputs)
    twob = rules.index_2b(inputs)
    trace["gstin_fixes"] = {}
    for i, inv in enumerate(invoices):
        if g := _gstin_fix(inv, links[inv.doc_id], inputs, twob):
            trace["gstin_fixes"][inv.doc_id] = f"{inv.supplier_gstin} fails the check digit -> {g} (linked entry)"
            invoices[i] = inv.model_copy(update={"supplier_gstin": g})
            records[inv.doc_id] = records[inv.doc_id].model_copy(update={"supplier_gstin": g})
    inputs = _inputs(parts, invoices)
    out = rules.reconcile(inputs, links)
    out = out.model_copy(update={"extractions": [to_extraction(i.doc_id, records[i.doc_id]) for i in invoices]})
    trace["links"] = link_trace
    trace["decisions"] = {i.doc_id: _explain(i, inputs, links[i.doc_id], twob, m, t)
                          for i, m, t in zip(invoices, out.matches, out.itc)}
    return out, trace
