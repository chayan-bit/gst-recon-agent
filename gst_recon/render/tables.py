"""Purchase register (Tally-style export), GSTR-2B JSON and bank statement CSV.

Values come straight from the truth rows (which already contain the simulator's
data-entry errors); only headers, date/number formats and bank narration styles vary.
"""

from __future__ import annotations

import csv
import io
import json
import random
import re

from gst_recon.render.fmt import fmt_amount, fmt_date
from gst_recon.schema import BankTxn, Gstr2b, PurchaseRegisterRow

# ------------------------------------------------------------------ purchase register

_REG_HEADERS = (
    ("Date", "Particulars", "Voucher Type", "Voucher No.", "Supplier Inv. No.", "Supplier Inv. Date", "GSTIN/UIN",
     "Gross Total", "Taxable Value", "CGST", "SGST", "IGST", "Cess", "Reverse Charge"),
    ("Voucher Date", "Party Name", "Vch Type", "Vch No", "Ref No", "Ref Date", "Party GSTIN",
     "Invoice Value", "Assessable Value", "Input CGST", "Input SGST", "Input IGST", "Input Cess", "RCM"),
    ("Date", "Particulars", "Voucher Type", "Voucher No.", "Bill No.", "Bill Date", "GST Registration No.",
     "Total Amount", "Value", "Central Tax", "State Tax", "Integrated Tax", "Cess", "Reverse Charge Applicable"),
)


def render_register(rows: list[PurchaseRegisterRow], period: str, buyer: str, rng: random.Random) -> tuple[str, dict]:
    """Return (text, format record). Either a CSV or a fixed-width Tally text report."""
    hdr = rng.choice(_REG_HEADERS)
    date_fmt = rng.choice(("DD-Mon-YY", "DD-MM-YYYY", "DD/MM/YYYY"))
    num_fmt = rng.choice(("plain", "plain", "indian"))
    style = rng.choice(("csv", "csv", "text"))
    cess = any(r.cess for r in rows)
    keep = [i for i in range(len(hdr)) if cess or hdr[i] not in ("Cess", "Input Cess")]

    def line(r: PurchaseRegisterRow) -> list[str]:
        f = lambda x: fmt_amount(x, num_fmt)  # noqa: E731
        vals = [fmt_date(r.voucher_date, date_fmt), r.party_name, r.voucher_type, r.voucher_no, r.supplier_invoice_no,
                fmt_date(r.supplier_invoice_date, date_fmt), r.party_gstin, f(r.total), f(r.taxable_value), f(r.cgst),
                f(r.sgst), f(r.igst), f(r.cess), "Yes" if r.reverse_charge else "No"]
        return [vals[i] for i in keep]

    head = [hdr[i] for i in keep]
    body = [line(r) for r in rows]
    meta = {"style": style, "date_fmt": date_fmt, "num_fmt": num_fmt, "header_set": _REG_HEADERS.index(hdr)}
    if style == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(head)
        w.writerows(body)
        return buf.getvalue().rstrip("\n"), meta
    widths = [max(len(x[i]) for x in [head, *body]) for i in range(len(head))]
    fixed = lambda cells: "  ".join(c.ljust(w) if i in (1, 2, 3, 4, 6) else c.rjust(w)  # noqa: E731
                                   for i, (c, w) in enumerate(zip(cells, widths)))
    mm, yy = period[:2], period[2:]
    title = [buyer, "Purchase Register", f"Period: {mm}/{yy}", ""]
    return "\n".join([*title, fixed(head), "-" * (sum(widths) + 2 * len(widths)), *map(fixed, body)]), meta


# ------------------------------------------------------------------------------ GSTR-2B


def render_gstr2b(docs: list[Gstr2b]) -> list[tuple[str, str]]:
    """[(period, compact JSON)] in the schema's own field naming, one per 2B."""
    return [(g.data.rtnprd, json.dumps(g.model_dump(), separators=(",", ":"))) for g in docs]


# ---------------------------------------------------------------------------- bank

_BANK_STYLES = {
    "hdfc": dict(date="DD/MM/YY", cols=("Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance")),
    "icici": dict(date="DD-MM-YYYY", cols=("S No.", "Value Date", "Transaction Date", "Cheque Number", "Transaction Remarks",
                                           "Withdrawal Amount (INR )", "Deposit Amount (INR )", "Balance (INR )")),
    "sbi": dict(date="D Mon YYYY", cols=("Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance")),
}
_PAY = re.compile(r"^(NEFT|RTGS) DR/(\S+)/(.+?)(?:/INV (.+))?$")


def _ifsc(ref: str, rng: random.Random) -> str:
    return f"{ref[:4]}0{rng.randint(0, 999999):06d}"


def _narration(style: str, text: str, ref: str, amount: float, rng: random.Random) -> str:
    m = _PAY.match(text)
    if not m:
        return text  # receipts, salary, GST payments keep the simulator's wording
    mode, _, payee, inv = m.groups()
    payee = payee[: rng.choice((18, 22, 28))].rstrip()
    if mode == "NEFT" and amount <= 100000 and rng.random() < 0.3:
        mode = rng.choice(("IMPS", "UPI"))
    tail = f"-INV {inv}" if inv else ""
    if style == "hdfc":
        if mode == "UPI":
            return f"UPI-{payee}-{ref}{tail}"
        return f"{mode} DR-{_ifsc(ref, rng)}-{payee}-{ref}{tail}"
    if style == "icici":
        return {"IMPS": f"MMT/IMPS/{ref}/{payee}{tail}", "UPI": f"UPI/{ref}/{payee}{tail}"}.get(
            mode, f"{mode}-{ref}-{payee}{tail}")
    if mode in ("IMPS", "UPI"):
        return f"TO TRANSFER-{mode} {ref} {payee}{tail}"
    return f"TO TRANSFER-INB {mode} UTR NO: {ref}-{payee}{tail}" if rng.random() < 0.5 else f"BY TRANSFER-{mode}*{_ifsc(ref, rng)}*{ref}*{payee}{tail}"


def render_bank(txns: list[BankTxn], rng: random.Random) -> tuple[str, dict]:
    style = rng.choice(sorted(_BANK_STYLES))
    spec = _BANK_STYLES[style]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(spec["cols"])
    for i, t in enumerate(txns, 1):
        d = fmt_date(t.txn_date, spec["date"])
        narr = _narration(style, t.narration, t.ref_no, t.debit, rng)
        dr = fmt_amount(t.debit, "plain") if t.debit else ""
        cr = fmt_amount(t.credit, "plain") if t.credit else ""
        bal = fmt_amount(t.balance, "plain")
        if style == "hdfc":
            w.writerow([d, narr, t.ref_no, d, dr, cr, bal])
        elif style == "icici":
            w.writerow([i, d, d, t.ref_no, narr, dr, cr, bal])
        else:
            w.writerow([d, d, narr, t.ref_no, dr, cr, bal])
    return buf.getvalue().rstrip("\n"), {"bank_style": style}
