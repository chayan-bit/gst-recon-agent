"""Invoices delivered as plain text: an email body or a WhatsApp-style message.

Every fact (ids, date, place of supply, HSN, amounts) is present exactly as on
the paper layouts; only the voice differs (abbreviations, typos in prose).
"""

from __future__ import annotations

import random

_INTRO = ("Dear Sir/Madam,\n\nPlease find below the invoice details for the material supplied.",
          "Dear Sir,\n\nPls find the tax invoice details below, original copy follows by courier.",
          "Hello,\n\nPlease find attatched invoice summary as discussed. Details below.",
          "Dear Team,\n\nInvoice detials are given below for your records and processing.",
          "Respected Sir/Madam,\n\nKindly find enclosed our bill. Summary of the same is given below.")
_OUTRO = ("Kindly arrange payment at the earliest and acknowledge recipt.",
          "Pls release the payment as per agreed terms. Revert in case of any query.",
          "Request you to process the payment within due date. Thanks.",
          "Kindly confirm recipt of this mail.")
_WA_OPEN = ("hi sir, invoice details below", "good morning sir. bill attached, details", "sir pls find bill details",
            "hello, inv details for ur order", "namaste sir, bill ka detail below")
_WA_CLOSE = ("pls confirm n pay asap", "payment pls", "kindly check n confirm sir", "thnx, pls clear dues soon",
             "ok pls do the needful")


def _lines(c: dict, wa: bool) -> list[str]:
    out = []
    for i, it in enumerate(c["items"], 1):
        if wa:
            out.append(f"{i}. {it['desc']} hsn {it['hsn']} {it['qty_unit']} @{it['price']} = {it['taxable']} + gst {it['rate']}% ({it['tax']})")
        else:
            out.append(f"{i}) {it['desc']} | HSN/SAC {it['hsn']} | {it['qty_unit']} x {it['price']} = {it['taxable']} | GST {it['rate']}% ({it['tax']})")
    return out


def render_text(c: dict, kind: str, rng: random.Random) -> str:
    """`kind` is 'email_text' or 'whatsapp_text'; `c` is a build_context() dict."""
    L, s, b = c["L"], c["supplier"], c["buyer"]
    cn = c["is_credit_note"]
    head = [f"{L['inv_no']}: {c['inv_no']}   {L['date']}: {c['date']}"]
    if c["orig_no"]:
        head.append(f"Against invoice no: {c['orig_no']}")
    tot = [f"{label}: {value}" for label, value in c["totals"]]
    note = [f"Remarks / Purpose: {c['remarks']}"] if c["remarks"] else []
    if kind == "email_text":
        return "\n".join([
            f"From: {c['ex']['email']}", f"Subject: {'Credit Note' if cn else rng.choice(('Invoice', 'Tax Invoice'))} {c['inv_no']} dt {c['date']} - {s['name']}",
            "", rng.choice(_INTRO), "", f"Supplier: {s['name']}, {s['address']}", f"{L['gstin']}: {s['gstin']}", *head,
            f"Bill to: {b['name']} ({L['gstin']}: {b['gstin']})", f"{L['pos']}: {c['pos']}",
            f"Reverse charge: {c['rcm_text']}", "", "Items:", *_lines(c, False), "", *tot, f"({c['words']})", *note, "",
            rng.choice(_OUTRO), "", "Regards,", c["ex"]["signatory"], s["name"], c["ex"]["phone"]])
    return "\n".join([
        rng.choice(_WA_OPEN), "", f"{'credit note' if cn else 'inv'} no {c['inv_no']} dt {c['date']}"
        + (f" (against {c['orig_no']})" if c["orig_no"] else ""),
        f"{s['name']}", f"{L['gstin']} {s['gstin']}", f"to: {b['name']} {b['gstin']}", f"pos {c['pos']} rcm {c['rcm_text']}",
        *_lines(c, True), *[t.lower() if i < len(tot) - 1 else t for i, t in enumerate(tot)], *[n.lower() for n in note], "", rng.choice(_WA_CLOSE)])
