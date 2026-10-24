"""Suppliers and the documents they issue (invoices, credit notes)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from gst_recon.schema import DocType, LinePurpose, Party, TruthInvoice, TruthLineItem
from gst_recon.sim import catalog as cat
from gst_recon.sim.buyer import BuyerContext, choose_purpose, remark_for
from gst_recon.sim.concepts import Concept
from gst_recon.sim.gstin import make_gstin, random_pan
from gst_recon.sim.money import r2, split_tax
from gst_recon.sim.splits import P_OOD_CONCEPT, View, ood_concepts

P_NEW_SUPPLIER = 0.4
P_MIXED_BILL = 0.25
SINGLE_CONCEPT_FAMILIES = {"rcm", "club", "works_contract", "goods_vehicle"}  # a grocery bill that also carries non-food items


def fy_label(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


@dataclass
class Supplier:
    party: Party
    alt_gstin: str  # same PAN, registration in another state
    concepts: tuple[Concept, ...]
    family: str
    number_fmt: str
    counter: int


def _name(rng: random.Random, view: View) -> str:
    parts = (rng.choice(view.name_prefix), rng.choice(view.name_core), rng.choice(cat.NAME_SUFFIX))
    return " ".join(x for x in parts if x)


def make_party(rng: random.Random, view: View, state: str) -> Party:
    name = _name(rng, view)
    if "Ltd" in name or "Limited" in name:
        holder = "C"  # PAN 4th char: company
    elif "LLP" in name or "& Co" in name or "Associates" in name:
        holder = "F"  # firm / LLP
    else:
        holder = rng.choice("FP")
    sname, cities = cat.STATES[state]
    address = f"{rng.randint(1, 250)}, {rng.choice(cat.STREETS)}, {rng.choice(cities)}, {sname}"
    return Party(name=name, gstin=make_gstin(state, random_pan(rng, holder, name)), state_code=state, address=address)


def offered(pool: list[Concept], start: date, end: date) -> list[Concept]:
    """Concepts with a known rate on every day of the period (both regimes if it straddles the cutover)."""
    return [c for c in pool if cat.rate_on(c, start) and cat.rate_on(c, end)]


def _new_supplier(rng: random.Random, view: View, buyer: Party, family: str, pool: list[Concept]) -> Supplier:
    state = buyer.state_code if rng.random() < 0.6 else rng.choice(view.states)
    party = make_party(rng, view, state)
    other = rng.choice([s for s in view.states if s != state] or [s for s in sorted(cat.STATES) if s != state])
    held = [c for c in pool if c.id in ood_concepts()]
    if view.split == "test_ood" and held and rng.random() < P_OOD_CONCEPT:
        pool = held
    k = 1 if family in SINGLE_CONCEPT_FAMILIES else rng.randint(1, 4)
    concepts = tuple(rng.sample(pool, min(len(pool), k)))
    return Supplier(party, make_gstin(other, party.gstin[2:12]), concepts, family, rng.choice(view.number_formats),
                    rng.randint(1, 900))


def _line(rng: random.Random, view: View, c: Concept, intra: bool, supply_date: date,
          purpose: LinePurpose) -> TruthLineItem:
    rate, cess_rate = cat.rate_on(c, supply_date)
    qty = rng.randint(*c.qty_range)
    price = r2(rng.uniform(*c.price_range))
    taxable = r2(qty * price)
    igst, cgst, sgst = split_tax(taxable, rate, intra)
    return TruthLineItem(description=rng.choice(view.forms(c)), hsn=c.hsn, quantity=qty, unit=c.unit,
                         unit_price=price, taxable_value=taxable, rate=rate, igst=igst, cgst=cgst, sgst=sgst,
                         cess=r2(taxable * cess_rate / 100), category=c.category, concept=c.id, purpose=purpose)


def assemble(s: Supplier, buyer: Party, lines: list[TruthLineItem], no: str, dt: date, doc_type: DocType,
             rcm: bool, original: str | None = None, remarks: str = "") -> TruthInvoice:
    heads = {h: r2(sum(getattr(l, h) for l in lines)) for h in ("taxable_value", "igst", "cgst", "sgst", "cess")}
    tax = heads["igst"] + heads["cgst"] + heads["sgst"] + heads["cess"]
    return TruthInvoice(
        doc_id="", doc_type=doc_type, supplier_gstin=s.party.gstin, supplier_name=s.party.name,
        supplier_address=s.party.address, buyer_gstin=buyer.gstin, buyer_name=buyer.name, invoice_no=no,
        invoice_date=dt, place_of_supply=buyer.state_code, reverse_charge=rcm, original_invoice_no=original,
        line_items=lines, total=r2(heads["taxable_value"] + (0 if rcm else tax)), remarks=remarks, **heads,
    )


def purchase_invoice(rng: random.Random, view: View, ctx: BuyerContext, buyer: Party, family: str,
                     suppliers: dict, dt: date, start: date, end: date) -> tuple[TruthInvoice, Supplier]:
    pool = offered(view.concepts(family), start, end)
    is_service = rng.choice(sorted({c.is_service for c in pool}))
    existing = suppliers.setdefault((family, is_service), [])
    if not existing or rng.random() < P_NEW_SUPPLIER:
        existing.append(_new_supplier(rng, view, buyer, family, [c for c in pool if c.is_service == is_service]))
    s = rng.choice(existing)
    concepts = rng.sample(s.concepts, rng.randint(1, min(3, len(s.concepts))))
    purpose = choose_purpose(rng, family, concepts[0], ctx)
    intra = s.party.state_code == buyer.state_code  # place of supply = buyer's state (IGST Act s.10/12(2))
    lines = [_line(rng, view, c, intra, dt, purpose) for c in concepts]
    extra = offered(view.concepts("toiletries"), start, end)
    if family == "food" and not is_service and purpose == LinePurpose.BUSINESS and extra and rng.random() < P_MIXED_BILL:
        lines.append(_line(rng, view, rng.choice(extra), intra, dt, LinePurpose.BUSINESS))  # mixed: blocked + eligible
    s.counter += 1
    no = s.number_fmt.format(s.counter, fy=fy_label(dt))
    rcm = any(c.reverse_charge for c in concepts)
    return assemble(s, buyer, lines, no, dt, DocType.INVOICE, rcm, remarks=remark_for(rng, purpose, view)), s


def credit_note(rng: random.Random, inv: TruthInvoice, s: Supplier, buyer: Party, period_end: date) -> TruthInvoice:
    src = inv.line_items[0]  # rate/cess follow the original supply, even across the cutover (s.34)
    intra = s.party.state_code == buyer.state_code
    taxable = r2(src.taxable_value * rng.choice((0.05, 0.1, 0.2, 0.25)))
    igst, cgst, sgst = split_tax(taxable, src.rate, intra)
    line = src.model_copy(update=dict(description=f"{src.description} - rate difference / return",
                                      quantity=1, unit_price=taxable, taxable_value=taxable, igst=igst,
                                      cgst=cgst, sgst=sgst, cess=r2(taxable * src.cess / max(src.taxable_value, 1))))
    dt = min(period_end, inv.invoice_date + timedelta(days=rng.randint(1, 10)))
    no = f"CN/{rng.randint(1, 400):03d}"
    return assemble(s, buyer, [line], no, dt, DocType.CREDIT_NOTE, False, inv.invoice_no)
