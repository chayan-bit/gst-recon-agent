"""Code half of the hybrid pipeline: per-document records in, full ReconOutput plus an audit trace out.

ANTI-CHEAT: `reconcile_prompt` receives the prompt text and the per-document records only. It opens no
file, and nothing in this package imports the eval case loader, target.json, meta.json or truth Case JSON
(tests/hybrid/test_anticheat.py enforces both).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from gst_recon.hybrid.docschema import HEADS, DocRecord, invoice_date, to_extraction, to_truth_invoice
from gst_recon.hybrid.inputs import PromptParts, parse_prompt
from gst_recon.hybrid.linker import link_documents
from gst_recon.hybrid.repair import repair
from gst_recon.schema import CaseInputs, DocType, Party, ReconOutput, TruthInvoice
from gst_recon.sim import rules


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
        fixed[doc_id], notes = repair(rec)
        if notes:
            trace["repairs"][doc_id] = notes
    records = fixed
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
    out = rules.reconcile(inputs, links)
    out = out.model_copy(update={"extractions": [to_extraction(i.doc_id, records[i.doc_id]) for i in invoices]})
    twob = rules.index_2b(inputs)
    trace["links"] = link_trace
    trace["decisions"] = {i.doc_id: _explain(i, inputs, links[i.doc_id], twob, m, t)
                          for i, m, t in zip(invoices, out.matches, out.itc)}
    return out, trace
