"""Deterministic parsers for the non-invoice parts of prompt.txt.

Input is the prompt text and nothing else (see `reconcile.reconcile_prompt`): the case header, the
per-document sections, the purchase register (Tally CSV or fixed-width text), each GSTR-2B JSON and the
bank statement CSV. The layouts are the ones `gst_recon.render.prompt.assemble` and
`gst_recon.render.tables` write, which are also the formats real exports use.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime

from gst_recon.schema import BankTxn, BuyerProfile, BusinessProfile, Gstr2b, PurchaseRegisterRow

_DOC = re.compile(r"^--- (D\d+) \| (.+?) ---$", re.M)
_SECTION = re.compile(r"^=== (.+?) ===$", re.M)


@dataclass(frozen=True)
class DocSection:
    doc_id: str
    source: str  # "scanned document, OCR text", "email body", "WhatsApp message"
    text: str  # the document body exactly as in prompt.txt

    @property
    def block(self) -> str:
        return f"--- {self.doc_id} | {self.source} ---\n{self.text}"


@dataclass(frozen=True)
class CaseHeader:
    text: str  # the "=== CASE ===" block verbatim, title line included
    buyer_name: str
    buyer_gstin: str
    buyer_state: str
    profile: BuyerProfile | None
    period: str  # MMYYYY
    as_of: date


@dataclass(frozen=True)
class PromptParts:
    header: CaseHeader
    docs: list[DocSection]
    register: list[PurchaseRegisterRow]
    gstr2b: list[Gstr2b]
    bank: list[BankTxn]


# ------------------------------------------------------------------ sections


def split_sections(prompt: str) -> dict[str, str]:
    """Title -> body for every '=== TITLE ===' section (the GSTR-2B ones keep their period in the title)."""
    marks = list(_SECTION.finditer(prompt))
    return {m.group(1): prompt[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(prompt)].strip("\n")
            for i, m in enumerate(marks)}


def split_docs(invoices: str) -> list[DocSection]:
    marks = list(_DOC.finditer(invoices))
    return [DocSection(m.group(1), m.group(2), invoices[m.end() + 1:marks[i + 1].start() if i + 1 < len(marks) else len(invoices)].rstrip("\n"))
            for i, m in enumerate(marks)]


def _field(text: str, label: str) -> str:
    m = re.search(rf"^{re.escape(label)}: (.*)$", text, re.M)
    if not m:
        raise ValueError(f"case header has no {label!r} line")
    return m.group(1).strip()


def parse_header(text: str) -> CaseHeader:
    profile = None
    if re.search(r"^Buyer line of business: ", text, re.M):
        kind, _, desc = _field(text, "Buyer line of business").partition(" - ")
        profile = BuyerProfile(profile=BusinessProfile(kind.strip().replace(" ", "_")), description=desc.strip(),
                               employees=int(_field(text, "Buyer employees")))
    state = re.search(r"\((\d{2})\)\s*$", _field(text, "Buyer state"))
    return CaseHeader(text="=== CASE ===\n" + text.strip("\n"), buyer_name=_field(text, "Buyer"), buyer_gstin=_field(text, "Buyer GSTIN"),
                      buyer_state=state.group(1) if state else "", profile=profile,
                      period=_field(text, "Return period").split()[0],
                      as_of=date.fromisoformat(_field(text, "Reconciliation date")))


# ------------------------------------------------------------------ values

_MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def parse_date(s: str) -> date:
    """Every date style the register, bank and documents use: DD-MM-YYYY, DD/MM/YY, D Mon YYYY, DD-Mon-YY, ..."""
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})[-/. ]([A-Za-z]{3}|\d{1,2})[-/. ](\d{2}|\d{4})", s)
    if not m:
        raise ValueError(f"unrecognised date {s!r}")
    mon = _MONTHS[m[2].lower()] if m[2].isalpha() else int(m[2])
    year = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
    return date(year, mon, int(m[1]))


def parse_amount(s: str) -> float:
    s = s.strip().replace(",", "")
    return float(s) if s else 0.0


# ------------------------------------------------------------------ register

_REG_FIELDS = {  # header synonyms (render.tables._REG_HEADERS) -> PurchaseRegisterRow field
    "voucher_date": ("Date", "Voucher Date"), "party_name": ("Particulars", "Party Name"),
    "voucher_type": ("Voucher Type", "Vch Type"), "voucher_no": ("Voucher No.", "Vch No"),
    "supplier_invoice_no": ("Supplier Inv. No.", "Ref No", "Bill No."),
    "supplier_invoice_date": ("Supplier Inv. Date", "Ref Date", "Bill Date"),
    "party_gstin": ("GSTIN/UIN", "Party GSTIN", "GST Registration No."),
    "total": ("Gross Total", "Invoice Value", "Total Amount"), "taxable_value": ("Taxable Value", "Assessable Value", "Value"),
    "cgst": ("CGST", "Input CGST", "Central Tax"), "sgst": ("SGST", "Input SGST", "State Tax"),
    "igst": ("IGST", "Input IGST", "Integrated Tax"), "cess": ("Cess", "Input Cess"),
    "reverse_charge": ("Reverse Charge", "RCM", "Reverse Charge Applicable"),
}
_REG_LOOKUP = {syn: f for f, syns in _REG_FIELDS.items() for syn in syns}


def _register_rows(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if "," in lines[0] and _REG_LOOKUP.keys() & set(next(csv.reader([lines[0]]))):
        rows = list(csv.reader(io.StringIO("\n".join(lines))))
        return rows[0], rows[1:]
    # fixed-width Tally text: title lines, header, a dashed rule, rows; cells are separated by 2+ spaces
    rule = next(i for i, ln in enumerate(lines) if set(ln.strip()) == {"-"})
    split = lambda ln: re.split(r"\s{2,}", ln.strip())  # noqa: E731
    return split(lines[rule - 1]), [split(ln) for ln in lines[rule + 1:]]


def parse_register(text: str) -> list[PurchaseRegisterRow]:
    head, body = _register_rows(text)
    keys = [_REG_LOOKUP.get(h.strip()) for h in head]
    if None in keys:
        raise ValueError(f"unknown register column(s): {[h for h, k in zip(head, keys) if k is None]}")
    out = []
    for cells in body:
        if len(cells) != len(keys):
            raise ValueError(f"register row has {len(cells)} cells, header has {len(keys)}: {cells}")
        v = dict(zip(keys, (c.strip() for c in cells)))
        out.append(PurchaseRegisterRow(
            voucher_no=v["voucher_no"], voucher_date=parse_date(v["voucher_date"]), voucher_type=v["voucher_type"],
            party_name=v["party_name"], party_gstin=v["party_gstin"], supplier_invoice_no=v["supplier_invoice_no"],
            supplier_invoice_date=parse_date(v["supplier_invoice_date"]),
            **{h: parse_amount(v.get(h, "")) for h in ("taxable_value", "igst", "cgst", "sgst", "cess", "total")},
            reverse_charge=v["reverse_charge"].lower() in ("yes", "y")))
    return out


# ------------------------------------------------------------------ bank

_BANK_COLS = {  # render.tables._BANK_STYLES column names -> BankTxn field
    "date": ("Date", "Transaction Date", "Txn Date"), "narration": ("Narration", "Transaction Remarks", "Description"),
    "ref_no": ("Chq./Ref.No.", "Cheque Number", "Ref No./Cheque No."),
    "debit": ("Withdrawal Amt.", "Withdrawal Amount (INR )", "Debit"),
    "credit": ("Deposit Amt.", "Deposit Amount (INR )", "Credit"), "balance": ("Closing Balance", "Balance (INR )", "Balance"),
}


def parse_bank(text: str) -> list[BankTxn]:
    rows = list(csv.reader(io.StringIO(text.strip())))
    head = rows[0]
    idx = {f: next(i for i, h in enumerate(head) if h in syns) for f, syns in _BANK_COLS.items()}
    return [BankTxn(txn_date=parse_date(r[idx["date"]]), narration=r[idx["narration"]], ref_no=r[idx["ref_no"]],
                    debit=parse_amount(r[idx["debit"]]), credit=parse_amount(r[idx["credit"]]),
                    balance=parse_amount(r[idx["balance"]])) for r in rows[1:] if r]


# ------------------------------------------------------------------ whole prompt


def parse_prompt(prompt: str) -> PromptParts:
    sec = split_sections(prompt)
    title = lambda prefix: next(t for t in sec if t.startswith(prefix))  # noqa: E731
    return PromptParts(
        header=parse_header(sec["CASE"]),
        docs=split_docs(sec["INVOICES"]),
        register=parse_register(sec[title("PURCHASE REGISTER")]),
        gstr2b=[Gstr2b.model_validate_json(body) for t, body in sec.items() if t.startswith("GSTR-2B period")],
        bank=parse_bank(sec[title("BANK STATEMENT")]),
    )
