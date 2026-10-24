"""Suppliers and the documents they issue (invoices, credit notes)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
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


def fy_tags(d: date) -> dict[str, str]:
    """Financial-year spellings a number format may use: {fy} 24-25 (v1), {fyl} 2024-25, {fyc} 2425, {fys} 24/25,
    {fyn} FY25, {yr} 2024 (calendar year of the document)."""
    start = d.year if d.month >= 4 else d.year - 1
    return {"fy": fy_label(d), "fyl": f"{start}-{(start + 1) % 100:02d}", "fyc": f"{start % 100:02d}{(start + 1) % 100:02d}",
            "fys": f"{start % 100:02d}/{(start + 1) % 100:02d}", "fyn": f"FY{(start + 1) % 100:02d}", "yr": str(d.year)}


# fmt_version 2: per-supplier invoice-number formats built from parts, within CGST Rule 46(b): at most 16 characters,
# letters, digits, hyphen and slash only, a consecutive serial unique per financial year. Train data only (no split
# holdout); v1 cases keep catalog.NUMBER_FORMATS.
MAX_NO_LEN = 16
LEGAL_NO = re.compile(r"[A-Za-z0-9/-]{1,16}")
_PREFIXES = ("INV", "TI", "GST", "SI", "TAX", "B", "S", "BL", "INV", "T", "GT", "SB", "RI", "TIN", "SL", "IN", "BILL")
_BRANCHES = ("MH", "DL", "KA", "TN", "GJ", "UP", "WB", "TS", "RJ", "HR", "BLR", "PNQ", "DEL", "HYD", "CHN", "MUM",
             "AHM", "JPR", "NDA", "GGN", "01", "02", "A", "B", "HO", "BR1")
_CN_PREFIXES = ("CN", "CRN", "CR", "CN", "SCN", "C")


def _initials(name: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", name) if w[0].isupper())[:4] or "S"


def _serial(rng: random.Random) -> str:
    return rng.choice(("{:d}", "{:d}", "{:03d}", "{:04d}", "{:04d}", "{:05d}", "{:06d}"))


def v2_number_format(rng: random.Random, name: str, cn: bool = False) -> str:
    """One supplier's numbering scheme, as a str.format template over (counter, **fy_tags)."""
    pre = rng.choice(_CN_PREFIXES) if cn else rng.choice((*_PREFIXES, _initials(name), _initials(name)))
    fy = rng.choice(("{fy}", "{fyl}", "{fyc}", "{fys}", "{fyn}", "{yr}"))
    br, sep, ser = rng.choice(_BRANCHES), rng.choice(("/", "/", "-", "-", "")), _serial(rng)
    shapes = (f"{pre}{sep}{fy}{sep}{ser}", f"{pre}{sep}{ser}", f"{pre}{sep}{ser}{sep or '/'}{fy}", f"{fy}{sep}{ser}",
              f"{pre}{sep}{br}{sep}{fy}{sep}{ser}", f"{br}{sep}{pre}{sep}{ser}", f"{fy}{sep or '/'}{pre}{sep}{ser}",
              f"{pre}{ser}")
    shapes += () if cn else ("{:d}", "{:05d}", f"{br}{sep}{ser}", "{fyc}{:08d}", "9{:09d}", f"{pre}{sep}{br}{sep}{{:06d}}")
    fmt = rng.choice(shapes)
    case = rng.random()
    if case < 0.12:
        fmt = re.sub(r"[A-Z]+(?![^{]*})", lambda m: m.group().lower(), fmt)  # inv/24-25/12 (placeholders untouched)
    elif case < 0.2:
        fmt = re.sub(r"[A-Z]+(?![^{]*})", lambda m: m.group().capitalize(), fmt)
    return fmt


def v2_counter(rng: random.Random) -> int:
    """Serial already reached at the case start: log-uniform 1..~30000, so unpadded serials vary in width."""
    return int(10 ** rng.uniform(0, 4.5))


def fits(fmt: str, counter: int, d: date) -> bool:
    """The template renders a legal Rule 46(b) number for this counter (and the next 100) on date d."""
    return all(LEGAL_NO.fullmatch(fmt.format(n, **fy_tags(d))) for n in (counter, counter + 100))


@dataclass
class Supplier:
    party: Party
    alt_gstin: str  # same PAN, registration in another state
    concepts: tuple[Concept, ...]
    family: str
    number_fmt: str
    counter: int
    credit_notes: set[str] = field(default_factory=set)  # CN numbers issued in this case (GSTR-2B key part)
    cn_fmt: str | None = None  # fmt_version 2: this supplier's credit-note numbering (v1: CN/NNN)


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
    if view.fmt_version >= 2:
        return _v2_supplier(rng, party, make_gstin(other, party.gstin[2:12]), concepts, family)
    return Supplier(party, make_gstin(other, party.gstin[2:12]), concepts, family, rng.choice(view.number_formats),
                    rng.randint(1, 900))


def _v2_supplier(rng: random.Random, party: Party, alt: str, concepts: tuple, family: str) -> Supplier:
    probe = date(2026, 3, 31)  # widest fy tags; checked again at issue time
    counter = v2_counter(rng)
    fmt = v2_number_format(rng, party.name)
    while not fits(fmt, counter, probe):
        fmt = v2_number_format(rng, party.name)
    cn = v2_number_format(rng, party.name, cn=True)
    while not fits(cn, 400, probe):
        cn = v2_number_format(rng, party.name, cn=True)
    return Supplier(party, alt, concepts, family, fmt, counter, cn_fmt=cn)


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
    no = s.number_fmt.format(s.counter, **fy_tags(dt))  # v1 templates use only {fy}
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
    draw = (lambda: s.cn_fmt.format(rng.randint(1, 400), **fy_tags(dt))) if s.cn_fmt else \
        (lambda: f"CN/{rng.randint(1, 400):03d}")
    no = draw()
    while no in s.credit_notes:  # redraw only on a repeat, so every case without one stays byte-identical
        no = draw()
    s.credit_notes.add(no)
    return assemble(s, buyer, [line], no, dt, DocType.CREDIT_NOTE, False, inv.invoice_no)
