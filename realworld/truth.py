"""Truth Cases for the real-world sanity set, from the hand-written specs in cases.json.

Documents, register, GSTR-2B and bank rows are built from each case spec; the expected
output comes from the repo's rules engine (`sim.rules.reconcile`) and is then compared with
the hand-computed `expect` block of every document. A disagreement is reported, never patched.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from gst_recon.schema import (BankTxn, BuyerProfile, Case, CaseInputs, DocType, Gstr2b, ItcCategory, LinePurpose,
                              Party, PurchaseRegisterRow, TruthInvoice, TruthLineItem)
from gst_recon.sim import catalog
from gst_recon.sim.concepts import CONCEPTS
from gst_recon.sim.gstin import is_valid_gstin
from gst_recon.sim.money import r2, split_tax
from gst_recon.sim.rules import HEADS, Link, reconcile

HERE = Path(__file__).resolve().parent
SPLIT = "realworld"
E_INVOICE_FORMATS = {"ic_e_invoice"}  # documents carrying an IRN, so their 2B row shows srctyp e-Invoice
_CONCEPT = {c.id: c for c in CONCEPTS}


def load_specs(path: Path = HERE / "cases.json") -> list[dict]:
    return json.loads(path.read_text())["cases"]


def load_parties(path: Path = HERE / "parties.json") -> dict:
    return json.loads(path.read_text())


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _ddmmyyyy(d: date) -> str:
    return f"{d.day:02d}-{d.month:02d}-{d.year}"


def _next_month(period: str, day: int) -> date:
    mm, yyyy = int(period[:2]), int(period[2:])
    return date(yyyy + mm // 12, mm % 12 + 1, day)


def digits(key: str, n: int) -> str:
    """Deterministic n-digit string from a key (UTRs, ack numbers)."""
    return str(int(hashlib.sha256(key.encode()).hexdigest(), 16))[:n]


def _party(p: dict) -> Party:
    return Party(name=p["name"], gstin=p["gstin"], state_code=p["state_code"], address=p["address"])


# ---------------------------------------------------------------- documents


def _line(spec: dict, intra: bool) -> TruthLineItem:
    taxable = r2(Decimal(str(spec["q"])) * Decimal(str(spec["p"])))
    igst, cgst, sgst = split_tax(taxable, spec["r"], intra)
    return TruthLineItem(description=spec["d"], hsn=spec["h"], quantity=spec["q"], unit=spec["u"], unit_price=spec["p"],
                         taxable_value=taxable, rate=spec["r"], igst=igst, cgst=cgst, sgst=sgst, cess=0.0,
                         category=ItcCategory(spec.get("cat", "normal")), concept=spec["c"],
                         purpose=LinePurpose(spec.get("pur", "business")))


def build_invoice(doc: dict, supplier: Party, buyer: Party) -> TruthInvoice:
    intra = supplier.state_code == buyer.state_code  # place of supply is always the buyer's state here
    lines = [_line(l, intra) for l in doc["lines"]]
    heads = {h: r2(sum(getattr(l, h) for l in lines)) for h in HEADS}
    taxable = r2(sum(l.taxable_value for l in lines))
    rcm = doc.get("rcm", False)
    total = taxable if rcm else r2(taxable + sum(heads.values()))
    if doc.get("round_off"):
        total = float(Decimal(str(total)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return TruthInvoice(
        doc_id=doc["id"], doc_type=DocType(doc.get("doc_type", "invoice")), supplier_gstin=supplier.gstin,
        supplier_name=supplier.name, supplier_address=supplier.address, buyer_gstin=buyer.gstin, buyer_name=buyer.name,
        invoice_no=doc["no"], invoice_date=_d(doc["date"]), place_of_supply=buyer.state_code, reverse_charge=rcm,
        original_invoice_no=doc.get("orig"), line_items=lines, taxable_value=taxable, total=total,
        remarks=doc.get("remarks", ""), **heads)


# ---------------------------------------------------------------- register


def _register(spec: dict, invs: list[TruthInvoice]) -> tuple[list[PurchaseRegisterRow], dict[str, list[str]]]:
    rows, links, n = [], {}, spec["voucher_start"]
    dupes = []
    for doc, inv in zip(spec["docs"], invs):
        over = doc.get("register", {})
        row = PurchaseRegisterRow(
            voucher_no=str(n), voucher_date=min(inv.invoice_date + timedelta(days=2), _d(spec["as_of"])),
            voucher_type="Debit Note" if inv.doc_type == DocType.CREDIT_NOTE else "Purchase",
            party_name=inv.supplier_name, party_gstin=over.get("party_gstin", inv.supplier_gstin),
            supplier_invoice_no=inv.invoice_no, supplier_invoice_date=inv.invoice_date, taxable_value=inv.taxable_value,
            igst=inv.igst, cgst=inv.cgst, sgst=inv.sgst, cess=inv.cess, total=over.get("total", inv.total),
            reverse_charge=inv.reverse_charge)
        rows.append(row)
        links[inv.doc_id] = [row.voucher_no]
        n += 1
        if over.get("duplicate"):
            dupes.append((inv.doc_id, row))
    for doc_id, row in dupes:  # the same bill keyed in again later in the month
        again = row.model_copy(update={"voucher_no": str(n), "voucher_date": row.voucher_date + timedelta(days=9)})
        rows.append(again)
        links[doc_id].append(again.voucher_no)
        n += 1
    return rows, links


# ------------------------------------------------------------------ GSTR-2B


def _twob_row(doc: dict, inv: TruthInvoice, over: dict) -> dict:
    heads = {h: getattr(inv, h) for h in HEADS} | over.get("heads", {})
    taxable = over.get("taxable", inv.taxable_value)
    if over and len({l.rate for l in inv.line_items}) != 1:
        raise ValueError(f"{inv.doc_id}: 2B amount overrides need a single-rate document")
    item = {"num": 1, "rt": inv.line_items[0].rate, "txval": taxable, **heads}
    val = inv.total if not ({"taxable", "heads"} & over.keys()) else r2(taxable + (0 if inv.reverse_charge else sum(heads.values())))
    row = {"dt": _ddmmyyyy(inv.invoice_date), "val": val, "pos": inv.place_of_supply,
           "rev": "Y" if inv.reverse_charge else "N", "items": [item]}
    if doc["format"] in E_INVOICE_FORMATS:
        row |= {"srctyp": "e-Invoice", "irn": irn(inv), "irngendate": _ddmmyyyy(inv.invoice_date)}
    return row


def _gstr2b(spec: dict, invs: list[TruthInvoice], buyer: Party, names: dict[str, str]) -> tuple[list[Gstr2b], dict]:
    periods: dict[str, dict] = {spec["period"]: {"b2b": {}, "cdnr": {}}}
    links = {}
    for doc, inv in zip(spec["docs"], invs):
        over = doc.get("twob", {})
        if over is None:
            continue  # not reported by the supplier
        period, ctin = over.get("period", spec["period"]), over.get("ctin", inv.supplier_gstin)
        row = _twob_row(doc, inv, over)
        sec = periods.setdefault(period, {"b2b": {}, "cdnr": {}})
        if inv.doc_type == DocType.CREDIT_NOTE:
            sec["cdnr"].setdefault(ctin, []).append({"ntnum": inv.invoice_no, "typ": "C", "suptyp": "R", **row})
        else:
            sec["b2b"].setdefault(ctin, []).append({"inum": inv.invoice_no, "typ": "R", **row})
        links[inv.doc_id] = (period, ctin, inv.invoice_no)
    out = []
    for period in sorted(periods, key=lambda p: (p[2:], p[:2])):
        sec = periods[period]
        sup = lambda ctin: {"ctin": ctin, "trdnm": names.get(ctin, names.get("_alt", "")),  # noqa: E731
                            "supfildt": _ddmmyyyy(_next_month(period, 11)), "supprd": period}
        out.append(Gstr2b.model_validate({"data": {
            "gstin": buyer.gstin, "rtnprd": period, "version": "1.0", "gendt": _ddmmyyyy(_next_month(period, 14)),
            "docdata": {"b2b": [sup(c) | {"inv": v} for c, v in sec["b2b"].items()],
                        "cdnr": [sup(c) | {"nt": v} for c, v in sec["cdnr"].items()]}}}))
    return out, links


def irn(inv: TruthInvoice) -> str:
    """64-hex Invoice Reference Number (synthetic: sha256 of GSTIN, FY, doc type, number, like the real IRN)."""
    return hashlib.sha256(f"{inv.supplier_gstin}{inv.invoice_date.year}INV{inv.invoice_no}".encode()).hexdigest()


# -------------------------------------------------------------------- bank


def _bank(spec: dict, invs: list[TruthInvoice]) -> tuple[list[BankTxn], dict[str, list[str]]]:
    as_of = _d(spec["as_of"])
    credited = {}
    for inv in invs:
        if inv.doc_type == DocType.CREDIT_NOTE:
            credited[inv.original_invoice_no] = credited.get(inv.original_invoice_no, 0) + inv.total
    txns, links = [], {}
    for doc, inv in zip(spec["docs"], invs):
        if inv.doc_type == DocType.CREDIT_NOTE:
            continue
        default = [[(inv.invoice_date + timedelta(days=20 if inv.total > 10000 else 0)).isoformat(),
                    r2(inv.total - credited.get(inv.invoice_no, 0))]]
        for i, (when, amount) in enumerate(doc.get("pay", default)):
            if _d(when) > as_of:
                continue  # paid after the reconciliation date: not on the statement
            ref = f"N{digits(spec['id'] + inv.doc_id + str(i), 15)}"
            txns.append((_d(when), f"NEFT DR/{ref}/{inv.supplier_name.upper()}/INV {inv.invoice_no}", ref, amount, 0.0))
            links.setdefault(inv.doc_id, []).append(ref)
    start = min(i.invoice_date for i in invs).replace(day=1)
    k = spec["id"]
    noise = [(start + timedelta(days=2), "NEFT CR/CUSTOMER RECEIPT/AGAINST BILLS", f"C{digits(k + 'c1', 11)}", 0.0, 1850000.0),
             (start + timedelta(days=6), "SALARY TRANSFER BATCH", f"SAL{digits(k + 's', 9)}", 640000.0, 0.0),
             (start + timedelta(days=19), "GST PMT CIN " + digits(k + 'g', 14), f"G{digits(k + 'g2', 11)}", 112500.0, 0.0),
             (start + timedelta(days=24), "RTGS CR/CUSTOMER RECEIPT", f"C{digits(k + 'c2', 11)}", 0.0, 2240000.0)]
    rows, bal = [], 6_000_000.0
    for d, narr, ref, dr, cr in sorted(txns + [t for t in noise if t[0] <= as_of], key=lambda t: (t[0], t[2])):
        bal = r2(bal - dr + cr)
        rows.append(BankTxn(txn_date=d, narration=narr, ref_no=ref, debit=dr, credit=cr, balance=bal))
    return rows, links


# -------------------------------------------------------------------- case


def build_case(spec: dict, parties: dict) -> Case:
    b = parties["buyers"][spec["buyer"]]
    buyer = _party(b)
    profile = BuyerProfile(profile=b["profile"], description=b["description"], employees=b["employees"])
    sups = {k: _party(v) for k, v in parties["suppliers"].items()}
    invs = [build_invoice(d, sups[d["supplier"]], buyer) for d in spec["docs"]]
    names = {s.gstin: s.name for s in sups.values()}
    for d, inv in zip(spec["docs"], invs):  # a GSTIN-mismatch 2B row still shows the supplier's trade name
        ctin = (d.get("twob") or {}).get("ctin")
        if ctin:
            names[ctin] = inv.supplier_name
    register, reg_links = _register(spec, invs)
    twob, twob_links = _gstr2b(spec, invs, buyer, names)
    bank, pay_links = _bank(spec, invs)
    inputs = CaseInputs(buyer=buyer, buyer_profile=profile, period=spec["period"], as_of_date=_d(spec["as_of"]),
                        invoices=invs, purchase_register=register, gstr2b=twob, bank_statement=bank)
    links = {i.doc_id: Link(tuple(reg_links.get(i.doc_id, ())), twob_links.get(i.doc_id), tuple(pay_links.get(i.doc_id, ())))
             for i in invs}
    expected = reconcile(inputs, links)
    tags = sorted({f for m in expected.matches for f in m.flags} | {r for x in expected.itc for r in x.reasons})
    return Case(case_id=spec["id"], seed=0, difficulty=SPLIT, inputs=inputs, expected=expected, split=SPLIT,
                anomalies=[getattr(t, "value", t) for t in tags])


# ------------------------------------------------------------------ checks


def _bucket_total(d, bucket: str) -> float:
    return r2(sum(getattr(getattr(d, bucket), h) for h in HEADS))


def disagreements(spec: dict, case: Case) -> list[str]:
    """Rules engine vs the hand-computed `expect` of every document."""
    out = []
    matches = {m.doc_id: m for m in case.expected.matches}
    itc = {x.doc_id: x for x in case.expected.itc}
    for doc in spec["docs"]:
        e, m, x = doc["expect"], matches[doc["id"]], itc[doc["id"]]
        got = {"flags": [f.value for f in m.flags], "reasons": [r.value for r in x.reasons],
               **{b: _bucket_total(x, b) for b in ("eligible", "blocked", "deferred")}}
        for k, v in e.items():
            same = abs(got[k] - v) <= 0.005 if isinstance(v, (int, float)) else got[k] == v
            if not same:
                out.append(f"{spec['id']}/{doc['id']} {k}: engine {got[k]!r} vs hand {v!r}")
    return out


def spec_errors(spec: dict, parties: dict) -> list[str]:
    """Inputs the law check depends on: valid GSTINs and the date-effective rate of every line."""
    out = []
    for doc in spec["docs"]:
        sup = parties["suppliers"][doc["supplier"]]
        if not is_valid_gstin(sup["gstin"]):
            out.append(f"{doc['supplier']}: bad GSTIN")
        for l in doc["lines"]:
            want = catalog.rate_on(_CONCEPT[l["c"]], _d(doc["date"]))
            if want is None or want[0] != l["r"] or want[1] != 0:
                out.append(f"{spec['id']}/{doc['id']} {l['d']!r}: rate {l['r']} but catalog says {want} on {doc['date']}")
    return out


def build_all(out_dir: Path | None = None) -> tuple[list[Case], list[str]]:
    parties = load_parties()
    if not is_valid_gstin(parties["buyers"]["B1"]["gstin"]):
        raise ValueError("buyer GSTIN invalid")
    cases, problems = [], []
    for spec in load_specs():
        problems += spec_errors(spec, parties)
        case = build_case(spec, parties)
        problems += disagreements(spec, case)
        cases.append(case)
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{case.case_id}.json").write_text(case.model_dump_json(indent=1))
    return cases, problems


if __name__ == "__main__":
    import sys

    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    built, issues = build_all(dest)
    print(f"{len(built)} cases, {sum(len(c.inputs.invoices) for c in built)} documents")
    for p in issues:
        print("DISAGREE" if " vs hand " in p else "SPEC", p)
    sys.exit(1 if issues else 0)
