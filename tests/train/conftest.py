"""Tiny rendered-case fixtures (no render extra needed): real truth cases, hand-built prompts."""

import json

import pytest

from gst_recon.sim.world import generate_case

EMAIL = """From: accounts@example.in
Subject: Invoice INV-77 dt 18/07/2024 - ACME TRADERS

Supplier: ACME TRADERS
GSTIN No.: 27AAAAA0000A1Z5
Bill No: INV-77   Date: 18/07/2024
Items:
1) steel coil | HSN/SAC 7208 | 2 Nos x 100.00 = 200.00 | GST 18% (IGST 36.00)
Grand Total: 236.00
Remarks / Purpose: for workers' canteen
"""


def prompt_for(case) -> str:
    docs = [f"--- {inv.doc_id} | {'email body' if i == 0 else 'scanned document, OCR text'} ---\n"
            + (EMAIL if i == 0 else f"TAX INVOICE {inv.invoice_no} TOTAL {inv.total}\n")
            for i, inv in enumerate(case.inputs.invoices)]
    return "=== CASE ===\nBuyer: X\n\n=== INVOICES ===\n" + "\n\n".join(docs) + "\n\n=== PURCHASE REGISTER (x) ===\nrows\n\n=== END ===\n"


def write_case(root, case, unrecoverable=(), prompt_tokens=None):
    d = root / case.case_id
    d.mkdir(parents=True)
    prompt = prompt_for(case)
    (d / "prompt.txt").write_text(prompt)
    target = case.expected.model_dump_json()
    (d / "target.json").write_text(target)
    meta = {"case_id": case.case_id, "split": case.split, "difficulty": case.difficulty,
            "documents": [{"doc_id": i.doc_id} for i in case.inputs.invoices],
            "prompt_tokens": prompt_tokens or len(prompt) // 4, "target_tokens": len(target) // 4,
            "unrecoverable": [{"doc_id": "D01", "facts": list(unrecoverable)}] if unrecoverable else []}
    (d / "meta.json").write_text(json.dumps(meta))
    return d


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("rendered")
    for i in range(12):
        write_case(root, generate_case(1, "easy", i), unrecoverable=("invoice_no",) if i == 0 else ())
    write_case(root, generate_case(1, "easy", 0, split="test_iid"))
    write_case(root, generate_case(1, "easy", 99), prompt_tokens=50_000)  # too long for every stage
    return root
