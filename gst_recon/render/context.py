"""Turn a TruthInvoice into display data: labels, formatted rows and totals.

Everything here is a pure function of (case, invoice, layout, seeds). Facts come
from the truth object; only the presentation (labels, formats, column order,
incidental supplier details) is randomised.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

from gst_recon.render.fmt import DATE_FORMATS, DATE_FORMATS_V2, NUM_FORMATS, fmt_amount, fmt_date
from gst_recon.render.holdout import OOD_DATE_FORMATS, pick
from gst_recon.render.layouts import LAYOUTS, is_service
from gst_recon.render.words import amount_in_words
from gst_recon.schema import Case, DocType, TruthInvoice
from gst_recon.sim import catalog as cat

LABELS = {
    "inv_no": ("Invoice No.", "Inv No", "Bill No", "Invoice #", "Tax Invoice No.", "Inv. No.", "Bill No."),
    "cn_no": ("Credit Note No.", "CN No", "Credit Note #", "C.N. No."),
    "date": ("Date", "Invoice Date", "Dated", "Inv Date", "Bill Date"),
    "cn_date": ("Date", "Credit Note Date", "CN Date", "Dated"),
    "gstin": ("GSTIN", "GSTIN/UIN", "GST No.", "GSTIN No.", "GST IN"),
    "hsn_goods": ("HSN/SAC", "HSN Code", "HSN", "HSN/SAC Code"),
    "hsn_service": ("SAC", "SAC Code", "HSN/SAC", "Service Accounting Code"),
    "desc_goods": ("Description of Goods", "Particulars", "Item Description", "Description", "Item"),
    "desc_service": ("Description of Services", "Particulars", "Service Description", "Description"),
    "qty": ("Qty", "Quantity", "Qty."),
    "rate": ("Rate", "Unit Price", "Price", "Rate (Rs.)"),
    "taxable": ("Taxable Value", "Taxable Amt", "Amount", "Taxable Amount"),
    "pos": ("Place of Supply", "POS", "Place of supply"),
    "buyer": ("Bill To", "Buyer (Bill to)", "Billed To", "Customer", "Consignee (Ship to)"),
    "total": ("Grand Total", "Total Amount", "Invoice Total", "Net Amount", "Total"),
    "line_total": ("Total", "Amount", "Line Total"),
}
BANKS = (("HDFC", "HDFC Bank"), ("ICIC", "ICICI Bank"), ("SBIN", "State Bank of India"), ("UTIB", "Axis Bank"),
         ("KKBK", "Kotak Mahindra Bank"), ("PUNB", "Punjab National Bank"), ("BARB", "Bank of Baroda"))
ACCENTS = ("#1f3a8a", "#0f766e", "#7c2d12", "#374151", "#9d174d", "#14532d", "#1e40af")


@lru_cache(maxsize=1)
def _faker():
    from faker import Faker

    return Faker("en_IN")


def _person(seed: str) -> str:
    fk = _faker()
    fk.seed_instance(seed)
    return fk.name()


@dataclass(frozen=True)
class DocFormat:
    """Presentation choices of one document, recorded in meta.json."""

    layout: str
    date_fmt: str
    num_fmt: str
    labels: dict[str, str]


def _qty(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


# held out of train/test_iid: the last synonym of every label group
OOD_LABELS = tuple(v[-1] for v in LABELS.values())


def _pick_labels(rng: random.Random, inv: TruthInvoice, split: str) -> dict[str, str]:
    cn = inv.doc_type == DocType.CREDIT_NOTE
    svc = is_service(inv)
    chosen = {k: pick(rng, v, OOD_LABELS, split) for k, v in LABELS.items()}
    return {
        "inv_no": chosen["cn_no"] if cn else chosen["inv_no"],
        "date": chosen["cn_date"] if cn else chosen["date"],
        "gstin": chosen["gstin"],
        "hsn": chosen["hsn_service" if svc else "hsn_goods"],
        "desc": chosen["desc_service" if svc else "desc_goods"],
        **{k: chosen[k] for k in ("qty", "rate", "taxable", "pos", "buyer", "total", "line_total")},
    }


def supplier_extras(case: Case, inv: TruthInvoice, rng: random.Random) -> dict:
    code, bank = rng.choice(BANKS)
    slug = "".join(c for c in inv.supplier_name.lower() if c.isalnum())[:14] or "sales"
    return {
        "phone": f"+91 {rng.choice('6789')}{rng.randint(10**8, 10**9 - 1)}",
        "email": f"{rng.choice(('accounts', 'sales', 'info', 'billing'))}@{slug}.{rng.choice(('in', 'com', 'co.in'))}",
        "pan": inv.supplier_gstin[2:12],
        "bank_name": bank,
        "ifsc": f"{code}0{rng.randint(0, 999999):06d}",
        "acct": str(rng.randint(10**10, 10**15)),
        "branch": rng.choice(("Main Branch", "MIDC Branch", "Station Road", "Industrial Area", "Sector 18")),
        "signatory": _person(f"{case.case_id}:{inv.supplier_gstin}"),
        "upper_name": rng.random() < 0.4,
        "accent": rng.choice(ACCENTS),
        "irn": "".join(rng.choice("0123456789abcdef") for _ in range(64)) if rng.random() < 0.3 else "",
    }


def _state(code: str) -> str:
    return cat.STATES[code][0] if code in cat.STATES else code


def _group_rates(inv: TruthInvoice, f) -> list[dict]:
    groups: dict[float, dict] = {}
    for l in inv.line_items:
        g = groups.setdefault(l.rate, dict(rate=l.rate, taxable=0.0, igst=0.0, cgst=0.0, sgst=0.0, cess=0.0))
        for h in ("taxable", "igst", "cgst", "sgst", "cess"):
            g[h] += l.taxable_value if h == "taxable" else getattr(l, h)
    return [{k: (f(v) if k != "rate" else f"{v:g}") for k, v in g.items()} for g in sorted(groups.values(), key=lambda g: g["rate"])]


def _table(inv: TruthInvoice, mode: str, rng: random.Random, f, L: dict[str, str]) -> tuple[list[dict], list[list[str]]]:
    intra = inv.igst == 0 and (inv.cgst > 0 or inv.sgst > 0 or all(l.rate == 0 for l in inv.line_items))
    has_cess = inv.cess > 0
    sr, merged_qty, hsn_first = rng.random() < 0.7, rng.random() < 0.5, rng.random() < 0.3
    tax_mode = rng.choice(("pair", "amt"))
    with_total = mode == "full" and not inv.reverse_charge and rng.random() < 0.5

    cols: list[dict] = []
    def add(key, label, align="r"):
        cols.append({"key": key, "label": label, "align": align})

    if sr:
        add("sr", rng.choice(("Sr", "S.No", "#", "Sl")), "c")
    if hsn_first and mode == "full":
        add("hsn", L["hsn"], "c")
    add("desc", L["desc"], "l")
    if not (hsn_first and mode == "full"):
        add("hsn", L["hsn"], "c")
    if merged_qty:
        add("qty_unit", L["qty"], "r")
    else:
        add("qty", L["qty"], "r")
        add("unit", "Unit", "c")
    add("price", L["rate"])
    add("taxable", L["taxable"] if mode == "full" else rng.choice(("Amount", "Amt", "Value")))
    if mode == "full":
        heads = ("cgst", "sgst") if intra else ("igst",)
        if tax_mode == "pair":
            for h in heads:
                add(f"{h}_rate", f"{h.upper()} %")
                add(h, f"{h.upper()} Amt")
        else:
            add("rate", "GST %")
            for h in heads:
                add(h, h.upper())
        if has_cess:
            add("cess", "Cess")
        if with_total:
            add("line_total", L["line_total"])
    else:
        add("rate", "GST%")

    rows = []
    for i, l in enumerate(inv.line_items, 1):
        half = f"{l.rate / 2:g}"
        vals = {
            "sr": str(i), "desc": l.description, "hsn": l.hsn, "qty": _qty(l.quantity), "unit": l.unit,
            "qty_unit": f"{_qty(l.quantity)} {l.unit}", "price": f(l.unit_price), "taxable": f(l.taxable_value),
            "rate": f"{l.rate:g}", "cgst": f(l.cgst), "sgst": f(l.sgst), "igst": f(l.igst), "cess": f(l.cess),
            "cgst_rate": half, "sgst_rate": half, "igst_rate": f"{l.rate:g}",
            "line_total": f(l.taxable_value + l.igst + l.cgst + l.sgst + l.cess),
        }
        rows.append([vals[c["key"]] for c in cols])
    return cols, rows


def _totals(inv: TruthInvoice, f, L: dict[str, str], single_rate: str | None) -> list[tuple[str, str]]:
    out = [(L["taxable"] if L["taxable"] != "Amount" else "Taxable Value", f(inv.taxable_value))]
    suffix = {"cgst": f" @ {float(single_rate) / 2:g}%", "sgst": f" @ {float(single_rate) / 2:g}%",
              "igst": f" @ {float(single_rate):g}%"} if single_rate else {}
    for h, label in (("cgst", "CGST"), ("sgst", "SGST"), ("igst", "IGST"), ("cess", "Cess")):
        v = getattr(inv, h)
        if v:
            out.append((label + suffix.get(h, ""), f(v)))
    if inv.reverse_charge:
        tax = inv.igst + inv.cgst + inv.sgst + inv.cess
        out.append(("Tax payable on Reverse Charge by recipient (not included)", f(tax)))
        out.append(("Amount Payable to Supplier", f(inv.total)))
    else:
        out.append((L["total"], f(inv.total)))
    return out


TIME_STYLES = ("24h", "12h", "24h_sec")
P_TIME = 0.25  # v2: share of suppliers (POS / e-invoice systems) that print a time next to the date


def _v2_date(case: Case, inv: TruthInvoice, style_rng: random.Random) -> tuple[str, str]:
    """(date style, shown date text) for a fmt_version 2 case: the style, and whether and how a time is printed,
    are per supplier (`style_rng`); the time itself is per document, from its own stream."""
    style = style_rng.choice(DATE_FORMATS_V2)
    tstyle = style_rng.choice(TIME_STYLES) if style_rng.random() < P_TIME else None
    shown = fmt_date(inv.invoice_date, style)
    if not tstyle:
        return style, shown
    t = random.Random(f"{case.case_id}:{inv.doc_id}:time")
    h, m, sec = t.randint(8, 21), t.randint(0, 59), t.randint(0, 59)
    clock = {"24h": f"{h:02d}:{m:02d}", "24h_sec": f"{h:02d}:{m:02d}:{sec:02d}",
             "12h": f"{(h - 1) % 12 + 1:02d}:{m:02d} {'AM' if h < 12 else 'PM'}"}[tstyle]
    return style, f"{shown} {clock}"


def build_context(case: Case, inv: TruthInvoice, layout_id: str, style_rng: random.Random,
                  doc_rng: random.Random, split: str = "train") -> dict:
    """Display data for one document. `style_rng` is per supplier, `doc_rng` per document."""
    layout = LAYOUTS.get(layout_id)
    mode = layout.table if layout else "full"
    v2 = case.fmt_version >= 2
    date_fmt, shown_date = _v2_date(case, inv, style_rng) if v2 else (pick(style_rng, DATE_FORMATS, OOD_DATE_FORMATS, split), None)
    num_fmt = style_rng.choices(NUM_FORMATS, weights=(70, 20, 10))[0]
    L = _pick_labels(style_rng, inv, split)
    ex = supplier_extras(case, inv, style_rng)

    def f(x: float) -> str:
        return fmt_amount(x, num_fmt)

    cols, rows = _table(inv, mode, style_rng, f, L)
    rates = {l.rate for l in inv.line_items}
    cn = inv.doc_type == DocType.CREDIT_NOTE
    buyer = case.inputs.buyer
    sup_state = inv.supplier_gstin[:2]
    title = "CREDIT NOTE" if cn else doc_rng.choice(("TAX INVOICE", "TAX INVOICE", "INVOICE", "Tax Invoice"))
    if layout_id == "handwritten_bill":
        title = "CREDIT NOTE" if cn else doc_rng.choice(("CASH / CREDIT MEMO", "BILL", "TAX INVOICE"))
    pos = inv.place_of_supply
    return {
        "layout": layout_id,
        "fmt": DocFormat(layout_id, date_fmt, num_fmt, L),
        "title": title,
        "L": L,
        "ex": ex,
        "is_credit_note": cn,
        "service": is_service(inv),
        "supplier": {"name": inv.supplier_name.upper() if ex["upper_name"] else inv.supplier_name,
                     "address": inv.supplier_address, "gstin": inv.supplier_gstin,
                     "state": _state(sup_state), "state_code": sup_state},
        "buyer": {"name": inv.buyer_name, "gstin": inv.buyer_gstin, "address": buyer.address,
                  "state": _state(buyer.state_code), "state_code": buyer.state_code},
        "remarks": getattr(inv, "remarks", "") or "",
        "inv_no": inv.invoice_no,
        "date": shown_date or fmt_date(inv.invoice_date, date_fmt),
        **({"date_only": fmt_date(inv.invoice_date, date_fmt)} if v2 else {}),
        "orig_no": inv.original_invoice_no or "",
        "pos": doc_rng.choice((f"{pos}-{_state(pos)}", f"{_state(pos)} ({pos})", f"{_state(pos)} - {pos}")),
        "rcm": inv.reverse_charge,
        "rcm_text": doc_rng.choice(("Yes", "Y")) if inv.reverse_charge else doc_rng.choice(("No", "N")),
        "cols": cols,
        "rows": rows,
        "items": [{"desc": l.description, "hsn": l.hsn, "qty_unit": f"{_qty(l.quantity)} {l.unit}",
                   "price": f(l.unit_price), "taxable": f(l.taxable_value), "rate": f"{l.rate:g}",
                   "tax": " + ".join(f"{h.upper()} {f(getattr(l, h))}" for h in ("cgst", "sgst", "igst", "cess")
                                     if getattr(l, h))}
                  for l in inv.line_items],
        "tax_summary": _group_rates(inv, f),
        "totals": _totals(inv, f, L, f"{next(iter(rates)):g}" if len(rates) == 1 else None),
        "total": f(inv.total),
        "words": amount_in_words(inv.total, style_rng.choice(("rupees", "inr", "rs"))),
        "intra": inv.igst == 0,
        "has_cess": inv.cess > 0,
        "n_items": len(inv.line_items),
    }
