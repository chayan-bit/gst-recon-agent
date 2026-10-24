"""Assemble the model input text from rendered parts."""

from __future__ import annotations

from gst_recon.schema import Case
from gst_recon.sim import catalog as cat

MONTH_NAMES = ("January February March April May June July August September October November December").split()


def _header(case: Case) -> str:
    b = case.inputs.buyer
    mm, yyyy = int(case.inputs.period[:2]), int(case.inputs.period[2:])
    lines = [
        "=== CASE ===",
        f"Buyer: {b.name}",
        f"Buyer GSTIN: {b.gstin}",
        f"Buyer state: {cat.STATES[b.state_code][0] if b.state_code in cat.STATES else b.state_code} ({b.state_code})",
    ]
    profile = getattr(case.inputs, "buyer_profile", None)  # added by the simulator
    if profile is not None:
        kind = getattr(profile.profile, "value", profile.profile).replace("_", " ")
        lines += [f"Buyer line of business: {kind} - {profile.description}", f"Buyer employees: {profile.employees}"]
    lines += [f"Return period: {case.inputs.period} ({MONTH_NAMES[mm - 1]} {yyyy})",
              f"Reconciliation date: {case.inputs.as_of_date.isoformat()}",
              f"Documents: {len(case.inputs.invoices)} invoices/credit notes (D01..D{len(case.inputs.invoices):02d})"]
    return "\n".join(lines)


def assemble(case: Case, docs: list[tuple[str, str, str]], register: tuple[str, str], gstr2b: list[tuple[str, str]],
             bank: tuple[str, str]) -> tuple[str, str]:
    """docs: (doc_id, source label, text). Returns (full prompt, text of the non-invoice sections)."""
    invoices = ["=== INVOICES ==="] + [f"--- {doc_id} | {source} ---\n{text}" for doc_id, source, text in docs]
    rest = [f"=== PURCHASE REGISTER ({register[0]}) ===\n{register[1]}"]
    rest += [f"=== GSTR-2B period {period} ===\n{js}" for period, js in gstr2b]
    rest.append(f"=== BANK STATEMENT ({bank[0]}) ===\n{bank[1]}")
    tail = "\n\n".join(rest)
    return "\n\n".join([_header(case), "\n\n".join(invoices), tail, "=== END ==="]) + "\n", tail


def source_label(layout_id: str) -> str:
    return {"email_text": "email body", "whatsapp_text": "WhatsApp message"}.get(layout_id, "scanned document, OCR text")

