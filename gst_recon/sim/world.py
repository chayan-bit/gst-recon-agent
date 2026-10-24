"""Seeded world generator: one buyer, one month, its suppliers and documents.

The generator decides the true state (invoices, what each supplier filed,
what the buyer booked, what was paid) and the true links between documents;
`rules.reconcile` then derives the expected output from that state.
"""

from __future__ import annotations

import calendar
import random
import string
from dataclasses import dataclass, field
from datetime import date, timedelta

from gst_recon.schema import (
    Case,
    CaseInputs,
    DocType,
    Party,
    PurchaseRegisterRow,
    TruthInvoice,
    TruthLineItem,
)
from gst_recon.sim import catalog as cat
from gst_recon.sim.bank import build_bank_statement, plan_payments
from gst_recon.sim.gstin import make_gstin, random_pan
from gst_recon.sim.money import r2, split_tax
from gst_recon.sim.rules import Link, reconcile
from gst_recon.sim.twob import build_gstr2b


@dataclass(frozen=True)
class Knobs:
    n_invoices: tuple[int, int]
    p_side: float  # per-invoice probability of an anomaly on each side (2B, register, payment)
    p_late_recon: float  # recon done > 180 days after the period (enables 180-day cases)
    p_rcm: float
    p_blocked: float
    p_credit_note: float


DIFFICULTY = {
    "easy": Knobs((5, 12), 0.05, 0.0, 0.06, 0.06, 0.04),
    "medium": Knobs((10, 25), 0.12, 0.5, 0.10, 0.10, 0.06),
    "hard": Knobs((20, 40), 0.22, 0.7, 0.12, 0.14, 0.08),
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


def fy_label(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


@dataclass
class Supplier:
    party: Party
    alt_gstin: str  # same PAN, registration in another state
    products: tuple[cat.Product, ...]
    kind: str
    number_fmt: str
    counter: int


@dataclass
class Draft:
    """An invoice plus the generator's decisions about it."""

    inv: TruthInvoice
    supplier: Supplier
    twob: str | None = None
    reg: str | None = None
    pay: str | None = None
    credit_note_of: "Draft | None" = None
    vouchers: list[str] = field(default_factory=list)
    twob_key: tuple[str, str, str] | None = None
    payment_refs: list[str] = field(default_factory=list)


def _name(rng: random.Random) -> str:
    return " ".join(x for x in (rng.choice(cat.NAME_PREFIX), rng.choice(cat.NAME_CORE), rng.choice(cat.NAME_SUFFIX)) if x)


def _address(rng: random.Random, state: str) -> str:
    sname, cities = cat.STATES[state]
    return f"{rng.randint(1, 250)}, {rng.choice(cat.STREETS)}, {rng.choice(cities)}, {sname}"


def make_party(rng: random.Random, state: str) -> Party:
    name = _name(rng)
    if "Ltd" in name or "Limited" in name:
        holder = "C"  # PAN 4th char: company
    elif "LLP" in name or "& Co" in name or "Associates" in name:
        holder = "F"  # firm / LLP
    else:
        holder = rng.choice("FP")
    return Party(name=name, gstin=make_gstin(state, random_pan(rng, holder, name)), state_code=state,
                 address=_address(rng, state))


def _offered(pool: tuple[cat.Product, ...], start: date, end: date) -> list[cat.Product]:
    """Products with a known rate on every day of the period (both regimes if it straddles the cutover)."""
    return [p for p in pool if cat.rate_on(p, start) and cat.rate_on(p, end)]


def _new_supplier(rng: random.Random, buyer_state: str, kind: str, start: date, end: date) -> Supplier:
    state = buyer_state if rng.random() < 0.6 else rng.choice(sorted(cat.STATES))
    party = make_party(rng, state)
    other = rng.choice([s for s in sorted(cat.STATES) if s != state])
    pool = _offered({"goods": cat.GOODS, "services": cat.SERVICES, "rcm": cat.RCM, "blocked": cat.BLOCKED}[kind], start, end)
    k = 1 if kind in ("rcm", "blocked") else min(len(pool), rng.randint(2, 5))
    fmt = rng.choice(("INV/{fy}/{:04d}", "{:05d}", "GST-{:04d}", "SI{:06d}", "{fy}/{:d}", "TI/{:03d}"))
    return Supplier(party, make_gstin(other, party.gstin[2:12]), tuple(rng.sample(pool, k)), kind, fmt,
                    rng.randint(1, 900))


def _line(rng: random.Random, p: cat.Product, intra: bool, supply_date: date) -> TruthLineItem:
    rate, cess_rate = cat.rate_on(p, supply_date)
    qty = rng.randint(*p.qty_range)
    price = r2(rng.uniform(*p.price_range))
    taxable = r2(qty * price)
    igst, cgst, sgst = split_tax(taxable, rate, intra)
    return TruthLineItem(description=p.description, hsn=p.hsn, quantity=qty, unit=p.unit, unit_price=price,
                         taxable_value=taxable, rate=rate, igst=igst, cgst=cgst, sgst=sgst,
                         cess=r2(taxable * cess_rate / 100), category=p.category)


def _assemble(s: Supplier, buyer: Party, lines: list[TruthLineItem], no: str, dt: date, doc_type: DocType,
              rcm: bool, original: str | None = None) -> TruthInvoice:
    heads = {h: r2(sum(getattr(l, h) for l in lines)) for h in ("taxable_value", "igst", "cgst", "sgst", "cess")}
    tax = heads["igst"] + heads["cgst"] + heads["sgst"] + heads["cess"]
    return TruthInvoice(
        doc_id="", doc_type=doc_type, supplier_gstin=s.party.gstin, supplier_name=s.party.name,
        supplier_address=s.party.address, buyer_gstin=buyer.gstin, buyer_name=buyer.name, invoice_no=no,
        invoice_date=dt, place_of_supply=buyer.state_code, reverse_charge=rcm, original_invoice_no=original,
        line_items=lines, total=r2(heads["taxable_value"] + (0 if rcm else tax)), **heads,
    )


def _invoice(rng: random.Random, s: Supplier, buyer: Party, dt: date, goods: list[cat.Product]) -> TruthInvoice:
    intra = s.party.state_code == buyer.state_code  # place of supply = buyer's state (IGST Act s.10/12(2))
    lines = [_line(rng, p, intra, dt) for p in rng.sample(s.products, rng.randint(1, len(s.products)))]
    if s.kind == "blocked" and rng.random() < 0.25:
        lines.append(_line(rng, rng.choice(goods), intra, dt))  # mixed invoice: blocked + normal line
    s.counter += 1
    no = s.number_fmt.format(s.counter, fy=fy_label(dt))
    return _assemble(s, buyer, lines, no, dt, DocType.INVOICE, s.kind == "rcm")


def _credit_note(rng: random.Random, d: Draft, buyer: Party, period_end: date) -> TruthInvoice:
    src = d.inv.line_items[0]  # rate/cess follow the original supply, even across the cutover (s.34)
    intra = d.supplier.party.state_code == buyer.state_code
    taxable = r2(src.taxable_value * rng.choice((0.05, 0.1, 0.2, 0.25)))
    igst, cgst, sgst = split_tax(taxable, src.rate, intra)
    line = src.model_copy(update=dict(description=f"{src.description} - rate difference / return",
                                      quantity=1, unit_price=taxable, taxable_value=taxable, igst=igst,
                                      cgst=cgst, sgst=sgst, cess=r2(taxable * src.cess / max(src.taxable_value, 1))))
    dt = min(period_end, d.inv.invoice_date + timedelta(days=rng.randint(1, 10)))
    no = f"CN/{rng.randint(1, 400):03d}"
    return _assemble(d.supplier, buyer, [line], no, dt, DocType.CREDIT_NOTE, False, d.inv.invoice_no)


def _pick_kind(rng: random.Random, k: Knobs) -> str:
    x = rng.random()
    if x < k.p_rcm:
        return "rcm"
    if x < k.p_rcm + k.p_blocked:
        return "blocked"
    return "goods" if rng.random() < 0.6 else "services"


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
    for d in sorted(drafts, key=lambda d: d.inv.invoice_date):
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
            base["party_gstin"] = _typo(rng, inv.supplier_gstin[:14], string.ascii_uppercase + string.digits) + inv.supplier_gstin[14]
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


def generate_case(seed: int, difficulty: str = "medium", index: int = 0,
                  periods: list[tuple[int, int]] | None = None) -> Case:
    knobs = DIFFICULTY[difficulty]
    rng = random.Random(f"gst-recon:{seed}:{difficulty}:{index}")
    y, m = rng.choice(periods or DEFAULT_PERIODS)
    start, end = date(y, m, 1), _month_end(y, m)
    late = rng.random() < knobs.p_late_recon
    as_of = end + timedelta(days=rng.randint(190, 230) if late else rng.randint(12, 25))
    buyer = make_party(rng, rng.choice(sorted(cat.STATES)))

    goods = _offered(cat.GOODS, start, end)
    suppliers: dict[str, list[Supplier]] = {}
    drafts: list[Draft] = []
    for _ in range(rng.randint(*knobs.n_invoices)):
        kind = _pick_kind(rng, knobs)
        pool = suppliers.setdefault(kind, [])
        if not pool or rng.random() < 0.4:
            pool.append(_new_supplier(rng, buyer.state_code, kind, start, end))
        s = rng.choice(pool)
        inv = _invoice(rng, s, buyer, start + timedelta(days=rng.randrange(end.day)), goods)
        d = Draft(inv, s, twob=_maybe(rng, knobs.p_side, TWOB_ANOMALIES), reg=_maybe(rng, knobs.p_side, REG_ANOMALIES),
                  pay=_maybe(rng, knobs.p_side, PAY_ANOMALIES) if late else None)
        if s.kind == "rcm" and d.twob == "filed_other_gstin":
            d.twob = None  # keep RCM anomalies to missing/late filing
        drafts.append(d)

    for d in list(drafts):
        if d.supplier.kind in ("goods", "services") and d.twob is None and rng.random() < knobs.p_credit_note:
            drafts.append(Draft(_credit_note(rng, d, buyer, end), d.supplier, credit_note_of=d))

    drafts.sort(key=lambda d: (d.inv.invoice_date, d.inv.supplier_gstin, d.inv.invoice_no))
    for i, d in enumerate(drafts, 1):
        d.inv = d.inv.model_copy(update={"doc_id": f"D{i:02d}"})

    register = _register(rng, drafts, end)
    gstr2b = build_gstr2b(rng, drafts, buyer, start, as_of)
    payments = plan_payments(rng, drafts, as_of)
    bank = build_bank_statement(rng, payments, start, as_of)

    inputs = CaseInputs(buyer=buyer, period=f"{m:02d}{y}", as_of_date=as_of, invoices=[d.inv for d in drafts],
                        purchase_register=register, gstr2b=gstr2b, bank_statement=bank)
    links = {d.inv.doc_id: Link(tuple(d.vouchers), d.twob_key, tuple(d.payment_refs)) for d in drafts}
    anomalies = [f"{d.inv.doc_id}:{a}" for d in drafts for a in (d.twob, d.reg, d.pay) if a]
    anomalies += [f"{d.inv.doc_id}:credit_note_of:{d.credit_note_of.inv.doc_id}" for d in drafts if d.credit_note_of]
    anomalies += [f"{d.inv.doc_id}:{d.supplier.kind}" for d in drafts if d.supplier.kind in ("rcm", "blocked")]
    return Case(case_id=f"{difficulty}-{seed}-{index:05d}", seed=seed, difficulty=difficulty, inputs=inputs,
                expected=reconcile(inputs, links), anomalies=anomalies)
