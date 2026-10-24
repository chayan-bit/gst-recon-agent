"""Supplier payments and the buyer's bank statement."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from gst_recon.schema import BankTxn, DocType
from gst_recon.sim.money import r2

BANKS = ("HDFC", "ICIC", "SBIN", "UTIB", "KKBK")


@dataclass(frozen=True)
class Payment:
    when: date
    amount: float
    payee: str
    invoice_no: str
    ref: str


def _ref(rng: random.Random, used: set[str]) -> str:
    while True:
        ref = f"{rng.choice(BANKS)}N{rng.randint(10**11, 10**12 - 1)}"
        if ref not in used:
            used.add(ref)
            return ref


def plan_payments(rng: random.Random, drafts: list, as_of: date) -> list[Payment]:
    """One payment per invoice (net of its credit notes) unless the payment
    anomaly says otherwise; payments after as_of do not appear. Sets
    `draft.payment_refs`."""
    credited: dict[int, float] = {}
    for d in drafts:
        if d.credit_note_of is not None:
            credited[id(d.credit_note_of)] = credited.get(id(d.credit_note_of), 0.0) + d.inv.total
    used: set[str] = set()
    out: list[Payment] = []
    for d in drafts:
        inv = d.inv
        if inv.doc_type != DocType.INVOICE or d.pay == "unpaid":
            continue
        net = r2(inv.total - credited.get(id(d), 0.0))
        when = inv.invoice_date + timedelta(days=rng.randint(5, 60))
        if d.pay == "partial":
            net = r2(net * rng.uniform(0.3, 0.7))
        elif d.pay == "paid_late" and (as_of - inv.invoice_date).days > 185:
            when = inv.invoice_date + timedelta(days=rng.randint(185, (as_of - inv.invoice_date).days))
        if when > as_of or net <= 0:
            continue
        p = Payment(when, net, inv.supplier_name, inv.invoice_no, _ref(rng, used))
        d.payment_refs.append(p.ref)
        out.append(p)
    return out


def _noise(rng: random.Random, start: date, as_of: date) -> list[tuple[date, str, float, float]]:
    rows = []
    d = start
    while d <= as_of:
        for _ in range(rng.randint(2, 5)):
            day = min(as_of, d + timedelta(days=rng.randint(0, 27)))
            rows.append((day, f"NEFT CR/CUSTOMER RECEIPT/{rng.randint(1000, 9999)}", 0.0, r2(rng.uniform(50000, 900000))))
        for day, text, lo, hi in ((25, "SALARY TRANSFER BATCH", 300000, 1500000), (20, "GST PMT CPIN", 20000, 300000)):
            when = d.replace(day=day)
            if when <= as_of:
                rows.append((when, f"{text}/{rng.randint(10**8, 10**9)}", r2(rng.uniform(lo, hi)), 0.0))
        nxt = d.replace(day=28) + timedelta(days=4)
        d = nxt.replace(day=1)
    return rows


def build_bank_statement(rng: random.Random, payments: list[Payment], start: date, as_of: date) -> list[BankTxn]:
    rows = _noise(rng, start, as_of)
    for p in payments:
        mode = "RTGS" if p.amount >= 200000 else "NEFT"
        tail = f"/INV {p.invoice_no}" if rng.random() < 0.5 else ""
        rows.append((p.when, f"{mode} DR/{p.ref}/{p.payee.upper()[:28]}{tail}", p.amount, 0.0, p.ref))
    rows = [r if len(r) == 5 else (*r, f"TXN{rng.randint(10**9, 10**10 - 1)}") for r in rows]
    rows.sort(key=lambda r: (r[0], r[4]))
    balance = r2(sum(r[2] for r in rows) + rng.uniform(5e5, 3e6))
    out = []
    for when, text, debit, credit, ref in rows:
        balance = r2(balance - debit + credit)
        out.append(BankTxn(txn_date=when, narration=text, ref_no=ref, debit=debit, credit=credit, balance=balance))
    return out
