"""The task instruction every evaluated model gets (prompt.txt holds only the case data).

Training data builders must wrap prompt.txt with this same SYSTEM_PROMPT, otherwise a
fine-tuned model is evaluated on a format it never saw. Frontier/base models receive
the same text; `with_schema` appends the JSON Schema for runs without constrained decoding.
"""

from __future__ import annotations

import json

from gst_recon.schema import output_json_schema

SYSTEM_PROMPT = """You reconcile one month of GST input tax credit (ITC) for the buyer described in the case.
The case lists invoices and credit notes (D01, D02, ...; OCR text, email or WhatsApp text), the buyer's purchase register, the GSTR-2B JSON for the return period (and later periods if available) and the bank statement.
Reply with ONE JSON object and nothing else: keys extractions, matches, itc, itc_totals. Use one entry per document, doc_id exactly as in the case (D01, D02, ...).
Fields that are 0, empty or false may be omitted.

extractions: copy each document's fields. invoice_date is YYYY-MM-DD. place_of_supply is the 2-digit state code. original_invoice_no is "" unless a credit note. Amounts are plain numbers in rupees. Header amounts are the sums of the line items.
matches: register_vouchers = voucher_no values of the purchase register rows for this document (empty list if none; two rows means a duplicate). gstr2b_period (MMYYYY), gstr2b_ctin and gstr2b_doc_no (inum or ntnum) as shown in the GSTR-2B entry, "" if absent. payment_refs = bank ref_no values paying it. flags (any of): missing_in_2b (in no GSTR-2B); period_mismatch (found only in another period's 2B); gstin_mismatch (2B or register GSTIN differs from the invoice); amount_mismatch (taxable value or a tax head differs by more than Rs 1 between invoice and 2B or register); duplicate (more than one register voucher); unpaid_180d (invoice, not credit note or reverse charge, more than 180 days old at the reconciliation date with more than Rs 1 unpaid).
itc: split the tax of every document over eligible, blocked and deferred, each with igst, cgst, sgst, cess; every rupee of tax lands in exactly one bucket. Rules in order:
1. Credit note: eligible = minus its tax, reasons [CREDIT_NOTE_REVERSAL].
2. Blocked under s.17(5), per line, decided by the buyer's line of business and the invoice remarks: BLOCKED_MOTOR_VEHICLE (cars and their servicing, unless the buyer is a car dealer, passenger transport operator or driving school), BLOCKED_FOOD_BEVERAGE (unless the buyer is a hotel or caterer, or a manufacturer with more than 250 employees and the remark says factory canteen), BLOCKED_CLUB_MEMBERSHIP (club, gym, fitness; always), BLOCKED_WORKS_CONTRACT (works contracts and construction inputs for the buyer's own building, unless the buyer is a construction contractor), BLOCKED_PERSONAL_USE, BLOCKED_GIFT (when the remarks say so).
3. Reverse charge: remaining tax is eligible, reasons [RCM_ELIGIBLE], regardless of 2B and payment.
4. Otherwise test against GSTR-2B: not in any 2B means all deferred (DEFERRED_NOT_IN_2B); only in a later period's 2B means all deferred (DEFERRED_PERIOD_MISMATCH); under a different supplier GSTIN means all deferred (DEFERRED_GSTIN_MISMATCH); if 2B shows less than the invoice for a head, the shortfall is deferred (DEFERRED_AMOUNT_MISMATCH).
5. If unpaid_180d: the eligible amount times outstanding divided by invoice total moves to deferred (DEFERRED_UNPAID_180D).
6. ELIGIBLE (or RCM_ELIGIBLE) is listed when any eligible amount is non-zero or no other reason applies.
itc_totals: sum of the per-document eligible, blocked and deferred over all documents, per head."""


def with_schema(system_prompt: str = SYSTEM_PROMPT) -> str:
    return f"{system_prompt}\n\nThe JSON must conform to this JSON Schema:\n{json.dumps(output_json_schema(), separators=(',', ':'))}"


def build_messages(prompt: str, *, schema_in_prompt: bool = False) -> list[dict[str, str]]:
    system = with_schema() if schema_in_prompt else SYSTEM_PROMPT
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]


# ------------------------------------------------------------------ hybrid mode (one document per call)

DOC_SYSTEM_PROMPT = """You read ONE purchase document received by the buyer described in the case header (OCR text of a scan, an email body or a WhatsApp message; it is an invoice or a credit note) and return its data.
Reply with ONE JSON object and nothing else.

Fields: doc_type (invoice or credit_note); supplier_gstin (15 characters: 2 digits, 5 letters, 4 digits, 1 letter, 1 letter or digit, Z, 1 letter or digit; read through OCR confusions such as O/0, I/1, S/5, B/8 using that pattern); supplier_name; invoice_no (the supplier's invoice or credit note number); invoice_date (YYYY-MM-DD); place_of_supply (2-digit state code); reverse_charge (true when the recipient pays the tax under reverse charge); original_invoice_no (for a credit note, the invoice it is against, else ""); line_items; and the header taxable_value, igst, cgst, sgst, cess and total (the amount payable to the supplier; under reverse charge it excludes the tax).
Amounts are plain numbers in rupees; a head that is not charged is 0. Header amounts are the sums of the line items.
Each line: description, hsn (HSN or SAC as printed, "" if unreadable), taxable_value, rate (total GST percent), igst, cgst, sgst, cess, and two judgments:
- itc_category, what the line is: motor_vehicle (cars, SUVs and other vehicles that carry people, and their servicing or repair; not goods vehicles or trucks), food_beverage (food, meals, catering, drinks, tea, coffee, biscuits, juice, groceries such as rice, oil, sugar, pulses), club_membership (club, gym, fitness or health club membership), works_contract (construction, renovation, interior fit-out or electrical works contract on a building), normal (everything else, including building materials such as cement, steel bars, tiles, sanitaryware).
- purpose, what the buyer uses it for, judged from the buyer's line of business in the header and the document's remarks: further_supply (the buyer supplies it onward: a trader buying its stock in trade, a car dealer buying cars or their servicing, a hotel or caterer buying food, a construction contractor buying a works contract for its projects), passenger_transport (vehicles of a passenger transport operator), driving_training (vehicles of a driving school), factory_canteen (remarks say factory or works canteen), staff_welfare (remarks say staff party, celebration, outing or welfare), own_construction (remarks say construction or renovation of the buyer's own building, office or factory), personal (remarks say residence, household or personal use), gift (remarks say gift or giveaway), business (ordinary business use: the default when none of these applies)."""


def build_doc_messages(header: str, doc_block: str, *, schema_in_prompt: bool = False) -> list[dict[str, str]]:
    """One hybrid-mode request: the case header block and ONE '--- Dnn | source ---' section, both verbatim
    from prompt.txt. Training rows for per-document SFT must use this same function."""
    system = DOC_SYSTEM_PROMPT
    if schema_in_prompt:
        from gst_recon.hybrid.docschema import doc_json_schema

        system = f"{system}\n\nThe JSON must conform to this JSON Schema:\n{json.dumps(doc_json_schema(), separators=(',', ':'))}"
    return [{"role": "system", "content": system}, {"role": "user", "content": f"{header}\n\n{doc_block}\n"}]
