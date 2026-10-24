"""Seeded world generator: one buyer, one month, its suppliers and documents.

The generator decides the true state (who the buyer is, what it bought and why,
what each supplier filed, what the buyer booked, what was paid) and the true
links between documents; `rules.reconcile` then derives the expected output.

Anomalies are drawn per document independently of the supplier, concept,
wording and position, and document order is shuffled (see `audit.py`).
"""

from __future__ import annotations

import calendar
import random
import string
from dataclasses import dataclass, field
from datetime import date, timedelta

from gst_recon.schema import Case, CaseInputs, DocType, Party, PurchaseRegisterRow, TruthInvoice
from gst_recon.sim.bank import build_bank_statement, plan_payments
from gst_recon.sim.buyer import BuyerContext, make_buyer_context
from gst_recon.sim.money import r2
from gst_recon.sim.rules import Link, line_block_reason, reconcile
from gst_recon.sim.splits import View, check_split
from gst_recon.sim.suppliers import Supplier, credit_note, fy_label, make_party, offered, purchase_invoice
from gst_recon.sim.twob import build_gstr2b


@dataclass(frozen=True)
class Knobs:
    n_invoices: tuple[int, int]
    p_side: float  # per-document probability of an anomaly on each side (2B, register, payment)
    p_late_recon: float  # recon done > 180 days after the period (enables 180-day cases)
    p_credit_note: float


DIFFICULTY = {
    "easy": Knobs((5, 12), 0.05, 0.0, 0.04),
    "medium": Knobs((10, 25), 0.12, 0.5, 0.06),
    "hard": Knobs((20, 40), 0.22, 0.7, 0.08),
}

TWOB_ANOMALIES = ("not_filed", "filed_wrong_buyer", "filed_other_gstin", "filed_wrong_amount", "filed_late")
REG_ANOMALIES = ("reg_duplicate", "reg_amount_typo", "reg_gstin_typo", "reg_invoice_no_typo")
PAY_ANOMALIES = ("unpaid", "partial", "paid_late")


def period_range(first: tuple[int, int], last: tuple[int, int]) -> list[tuple[int, int]]:
    """Inclusive list of (year, month) return periods."""
    out, (y, m) = [], first
    while (y, m) <= last:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if not out:
        raise ValueError(f"empty period range {first}..{last}")
    return out


# April 2024 to September 2026: spans the 22 Sep 2025 GST 2.0 rate cutover (RULES.md)
DEFAULT_PERIODS = period_range((2024, 4), (2026, 9))


@dataclass
class Draft:
    """A document plus the generator's decisions about it."""

    inv: TruthInvoice
    supplier: Supplier
    family: str
    twob: str | None = None
    reg: str | None = None
    pay: str | None = None
    credit_note_of: "Draft | None" = None
    vouchers: list[str] = field(default_factory=list)
    twob_key: tuple[str, str, str] | None = None
    payment_refs: list[str] = field(default_factory=list)


def _maybe(rng: random.Random, p: float, options: tuple[str, ...]) -> str | None:
    return rng.choice(options) if rng.random() < p else None


def _typo(rng: random.Random, text: str, alphabet: str) -> str:
    i = rng.randrange(len(text))
    return text[:i] + rng.choice([c for c in alphabet if c != text[i]]) + text[i + 1:]


def _transpose_amount(rng: random.Random, x: float) -> float:
    digits = f"{x:.2f}".replace(".", "")
    i = rng.randrange(len(digits) - 3) if len(digits) > 3 else 0
    swapped = digits[:i] + digits[i + 1] + digits[i] + digits[i + 2:]
    y = int(swapped) / 100
    return y if abs(y - x) > 1 else r2(x * 1.1)


def _register(rng: random.Random, drafts: list[Draft], period_end: date) -> list[PurchaseRegisterRow]:
    rows: list[PurchaseRegisterRow] = []
    seq = {"Purchase": 0, "Debit Note": 0}
    for d in sorted(drafts, key=lambda d: (d.inv.invoice_date, d.inv.doc_id)):
        inv = d.inv
        vtype = "Debit Note" if inv.doc_type == DocType.CREDIT_NOTE else "Purchase"
        base = dict(voucher_date=min(period_end, inv.invoice_date + timedelta(days=rng.randint(0, 4))),
                    voucher_type=vtype, party_name=inv.supplier_name, party_gstin=inv.supplier_gstin,
                    supplier_invoice_no=inv.invoice_no, supplier_invoice_date=inv.invoice_date,
                    taxable_value=inv.taxable_value, igst=inv.igst, cgst=inv.cgst, sgst=inv.sgst,
                    cess=inv.cess, total=inv.total, reverse_charge=inv.reverse_charge)
        if d.reg == "reg_amount_typo":
            base["taxable_value"] = _transpose_amount(rng, inv.taxable_value)
            base["total"] = r2(inv.total - inv.taxable_value + base["taxable_value"])
        elif d.reg == "reg_gstin_typo":
            alphabet = string.ascii_uppercase + string.digits
            base["party_gstin"] = _typo(rng, inv.supplier_gstin[:14], alphabet) + inv.supplier_gstin[14]
        elif d.reg == "reg_invoice_no_typo":
            base["supplier_invoice_no"] = _typo(rng, inv.invoice_no, string.digits)
        for _ in range(2 if d.reg == "reg_duplicate" else 1):
            seq[vtype] += 1
            prefix = "PUR" if vtype == "Purchase" else "DN"
            vno = f"{prefix}/{fy_label(period_end)}/{seq[vtype]:04d}"
            rows.append(PurchaseRegisterRow(voucher_no=vno, **base))
            d.vouchers.append(vno)
    return rows


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _families(ctx: BuyerContext, view: View, start: date, end: date) -> tuple[list[str], list[float]]:
    fams = [f for f, w in ctx.family_weights.items() if w > 0 and offered(view.concepts(f), start, end)]
    return fams, [ctx.family_weights[f] for f in fams]


def _anomalies(rng: random.Random, knobs: Knobs, late: bool, payable: bool) -> dict[str, str | None]:
    """Independent of everything about the document (supplier, concept, wording, position)."""
    return dict(twob=_maybe(rng, knobs.p_side, TWOB_ANOMALIES), reg=_maybe(rng, knobs.p_side, REG_ANOMALIES),
                pay=_maybe(rng, knobs.p_side, PAY_ANOMALIES) if late and payable else None)


def _draft_invoices(rng: random.Random, knobs: Knobs, view: View, ctx: BuyerContext, buyer: Party,
                    start: date, end: date, late: bool) -> list[Draft]:
    fams, weights = _families(ctx, view, start, end)
    suppliers: dict[tuple[str, bool], list[Supplier]] = {}
    drafts: list[Draft] = []
    for _ in range(rng.randint(*knobs.n_invoices)):
        family = rng.choices(fams, weights)[0]
        dt = start + timedelta(days=rng.randrange(end.day))
        inv, s = purchase_invoice(rng, view, ctx, buyer, family, suppliers, dt, start, end)
        drafts.append(Draft(inv, s, family, **_anomalies(rng, knobs, late, True)))
    for d in list(drafts):
        clean = d.twob is None and not d.inv.reverse_charge and all(
            line_block_reason(li, ctx.profile) is None for li in d.inv.line_items)
        if clean and rng.random() < knobs.p_credit_note:
            cn = credit_note(rng, d.inv, d.supplier, buyer, end)
            drafts.append(Draft(cn, d.supplier, d.family, credit_note_of=d, **_anomalies(rng, knobs, late, False)))
    return drafts


def generate_case(seed: int, difficulty: str = "medium", index: int = 0,
                  periods: list[tuple[int, int]] | None = None, split: str = "train") -> Case:
    knobs, view = DIFFICULTY[difficulty], View(check_split(split))
    tag = "" if split == "train" else f"{split}:"
    rng = random.Random(f"gst-recon:{tag}{seed}:{difficulty}:{index}")
    y, m = rng.choice(periods or DEFAULT_PERIODS)
    start, end = date(y, m, 1), _month_end(y, m)
    late = rng.random() < knobs.p_late_recon
    as_of = end + timedelta(days=rng.randint(190, 230) if late else rng.randint(12, 25))
    ctx = make_buyer_context(rng, view)
    buyer = make_party(rng, view, rng.choice(view.states))

    drafts = _draft_invoices(rng, knobs, view, ctx, buyer, start, end, late)
    rng.shuffle(drafts)  # document position carries no information
    for i, d in enumerate(drafts, 1):
        d.inv = d.inv.model_copy(update={"doc_id": f"D{i:02d}"})

    register = _register(rng, drafts, end)
    gstr2b = build_gstr2b(rng, drafts, buyer, start, as_of)
    payments = plan_payments(rng, drafts, as_of)
    bank = build_bank_statement(rng, payments, start, as_of)

    inputs = CaseInputs(buyer=buyer, buyer_profile=ctx.profile, period=f"{m:02d}{y}", as_of_date=as_of,
                        invoices=[d.inv for d in drafts], purchase_register=register, gstr2b=gstr2b,
                        bank_statement=bank)
    links = {d.inv.doc_id: Link(tuple(d.vouchers), d.twob_key, tuple(d.payment_refs)) for d in drafts}
    anomalies = [f"{d.inv.doc_id}:{a}" for d in drafts for a in (d.twob, d.reg, d.pay) if a]
    anomalies += [f"{d.inv.doc_id}:credit_note_of:{d.credit_note_of.inv.doc_id}" for d in drafts if d.credit_note_of]
    anomalies += [f"{d.inv.doc_id}:{d.family}:{d.inv.line_items[0].purpose.value}" for d in drafts
                  if d.family in ("rcm", "motor_vehicle", "food", "club", "works_contract", "construction",
                                  "household", "giftable") or d.inv.line_items[0].purpose.value != "business"]
    prefix = "" if split == "train" else f"{split}-"
    return Case(case_id=f"{prefix}{difficulty}-{seed}-{index:05d}", seed=seed, difficulty=difficulty, split=split,
                inputs=inputs, expected=reconcile(inputs, links), anomalies=anomalies)
