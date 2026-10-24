"""Render one truth document through its real-world print format (HTML -> PDF).

Two methods (see PROVENANCE.md):
- `original`: the vendored upstream template file is rendered as is, with small shims for the
  framework objects it calls (frappe.db, doc.get_formatted, ...): ic_e_invoice, ic_pos_invoice.
- `port`: the upstream markup, labels and field order re-expressed as a standalone Jinja
  template in formats/ (framework calls replaced by plain values): every other format.
"""

from __future__ import annotations

import base64
import io
import json
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from gst_recon.render.fmt import fmt_amount
from gst_recon.render.words import integer_words
from gst_recon.schema import DocType, Party, TruthInvoice

from realworld.truth import digits, irn

FORMATS = Path(__file__).resolve().parent / "formats"
VENDOR = FORMATS / "vendor"

STATE_NAMES = {"06": "Haryana", "07": "Delhi", "08": "Rajasthan", "24": "Gujarat", "27": "Maharashtra",
               "29": "Karnataka", "33": "Tamil Nadu", "36": "Telangana", "37": "Andhra Pradesh"}
UQC = {"Nos": "NOS", "MT": "MTS", "Kg": "KGS", "kg": "KGS", "Bag": "BAG", "Box": "BOX", "Ctn": "CTN", "Tin": "TIN",
       "Units": "UNT"}


def money(x: float) -> str:
    return fmt_amount(x, "indian")


def rupees(x: float) -> str:
    """frappe fmt_money(value, currency='INR') with the Indian number format."""
    return f"₹ {money(x)}"


def words(x: float) -> str:
    rupee = int(x)
    paise = int(round((x - rupee) * 100))
    w = f"{integer_words(rupee)} Rupees"
    return w + (f" and {integer_words(paise)} Paise" if paise else "") + " Only"


def pin_city(address: str) -> tuple[str, str, str]:
    """'Plot 9, Peenya 2nd Stage, Bengaluru 560058' -> ('Plot 9, Peenya 2nd Stage', 'Bengaluru', '560058')."""
    m = re.match(r"(.*),\s*([^,]+?)\s+(\d{6})$", address)
    return (m.group(1), m.group(2), m.group(3)) if m else (address, "", "")


def heads(inv: TruthInvoice) -> dict:
    return {"igst": inv.igst, "cgst": inv.cgst, "sgst": inv.sgst, "tax": round(inv.igst + inv.cgst + inv.sgst, 2),
            "intra": inv.supplier_gstin[:2] == inv.place_of_supply,
            "round_off": round(inv.total - inv.taxable_value - (0 if inv.reverse_charge else inv.igst + inv.cgst + inv.sgst), 2)}


def common(inv: TruthInvoice, supplier: Party, buyer: Party, doc: dict) -> dict:
    return {"inv": inv, "s": supplier, "b": buyer, "x": doc.get("extra", {}), "h": heads(inv), "money": money,
            "rupees": rupees, "words": words, "state": lambda c: STATE_NAMES.get(c, c), "pin_city": pin_city,
            "is_cn": inv.doc_type == DocType.CREDIT_NOTE, "pan": supplier.gstin[2:12],
            "dmy": lambda d, sep="-": f"{d.day:02d}{sep}{d.month:02d}{sep}{d.year}", "fonts": FONTS_URI}


FONTS_URI = (Path(__file__).resolve().parent.parent / "gst_recon" / "render" / "fonts").as_uri()


# ------------------------------------------------------------ e-invoice (original)


def e_invoice_json(inv: TruthInvoice, supplier: Party, buyer: Party) -> dict:
    ack_dt = datetime.combine(inv.invoice_date, datetime.min.time()) + timedelta(hours=11, minutes=int(digits(inv.invoice_no, 2)) % 60)

    def party(p: Party, pos: str | None = None) -> dict:
        addr, city, pin = pin_city(p.address)
        out = {"Gstin": p.gstin, "LglNm": p.name, "Addr1": addr, "Loc": city, "Pin": int(pin), "Stcd": p.state_code}
        return out | ({"Pos": pos} if pos else {})

    items = [{"SlNo": str(i), "PrdDesc": l.description, "IsServc": "Y" if l.hsn.startswith("99") else "N", "HsnCd": l.hsn,
              "Qty": l.quantity, "Unit": UQC.get(l.unit, "OTH"), "UnitPrice": l.unit_price, "TotAmt": l.taxable_value,
              "Discount": 0, "AssAmt": l.taxable_value, "GstRt": l.rate, "IgstAmt": l.igst, "CgstAmt": l.cgst,
              "SgstAmt": l.sgst, "CesRt": 0, "CesAmt": 0,
              "TotItemVal": round(l.taxable_value + l.igst + l.cgst + l.sgst, 2)} for i, l in enumerate(inv.line_items, 1)]
    h = heads(inv)
    return {"Version": "1.1", "Irn": irn(inv), "AckNo": int("1" + digits(inv.invoice_no + "ack", 14)),
            "AckDt": ack_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "Y" if inv.reverse_charge else "N"},
            "DocDtls": {"Typ": "CRN" if inv.doc_type == DocType.CREDIT_NOTE else "INV", "No": inv.invoice_no,
                        "Dt": inv.invoice_date.strftime("%d/%m/%Y")},
            "SellerDtls": party(supplier), "BuyerDtls": party(buyer, inv.place_of_supply), "ItemList": items,
            "ValDtls": {"AssVal": inv.taxable_value, "CgstVal": inv.cgst, "SgstVal": inv.sgst, "IgstVal": inv.igst,
                        "CesVal": 0, "Discount": 0, "OthChrg": 0, "RndOffAmt": h["round_off"], "TotInvVal": inv.total}}


def signed_qr(data: dict) -> str:
    """JWT-shaped like the IRP's signed QR, but issuer and signature say it is synthetic."""
    b64 = lambda o: base64.urlsafe_b64encode(json.dumps(o, separators=(",", ":")).encode()).decode().rstrip("=")  # noqa: E731
    payload = {"data": json.dumps({"SellerGstin": data["SellerDtls"]["Gstin"], "BuyerGstin": data["BuyerDtls"]["Gstin"],
                                   "DocNo": data["DocDtls"]["No"], "DocTyp": data["DocDtls"]["Typ"],
                                   "DocDt": data["DocDtls"]["Dt"], "TotInvVal": data["ValDtls"]["TotInvVal"],
                                   "ItemCnt": len(data["ItemList"]), "MainHsnCode": data["ItemList"][0]["HsnCd"],
                                   "Irn": data["Irn"], "IrnDt": data["AckDt"]}), "iss": "SYNTHETIC (not NIC)"}
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}.SYNTHETIC-UNSIGNED"


def qr_png_b64(text: str, scale: int = 2) -> str:
    import segno

    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=scale, border=2)
    return base64.b64encode(buf.getvalue()).decode()


def _nonzero(data, field_map: dict, mandatory: set) -> dict:
    rows = data if isinstance(data, list) else [data]
    keep = {f for f in field_map for r in rows if r.get(f)} | mandatory
    return {f: label for f, label in field_map.items() if f in keep}


E_INVOICE_ITEM_FIELDS = {"SlNo": "Sr.", "PrdDesc": "Product Description", "HsnCd": "HSN Code", "Qty": "Qty", "Unit": "UOM",
                         "UnitPrice": "Rate", "Discount": "Discount", "AssAmt": "Taxable Amount", "GstRt": "Tax Rate",
                         "CesRt": "Cess Rate", "TotItemVal": "Total"}  # india_compliance/gst_india/utils/jinja.py
E_INVOICE_AMOUNT_FIELDS = {"AssVal": "Taxable Value", "CgstVal": "CGST", "SgstVal": "SGST", "IgstVal": "IGST", "CesVal": "CESS",
                           "Discount": "Discount", "OthChrg": "Other Charges", "RndOffAmt": "Round Off", "TotInvVal": "Total Value"}


class _Doc(SimpleNamespace):
    """frappe Document stand-in: attribute access plus get_formatted()."""

    def get_formatted(self, field, *_):
        v = getattr(self, field)
        if isinstance(v, date):
            return v.strftime("%d-%m-%Y")
        if isinstance(v, float):
            return rupees(v)
        return str(v)

    def get(self, k, default=None):
        return getattr(self, k, default)


def _frappe(invoice_data: str, qr: str) -> SimpleNamespace:
    def format_datetime(s: str, fmt: str) -> str:
        d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return d.strftime("%d/%m/%Y %I:%M:%S") if fmt == "dd/MM/yyyy hh:mm:ss" else str(d)

    def flt(v, p=None):
        return round(float(v), p) if p is not None else float(v)

    db = SimpleNamespace(get_value=lambda *a, **k: {"invoice_data": invoice_data, "signed_qr_code": qr})
    utils = SimpleNamespace(format_datetime=format_datetime, fmt_money=lambda v, currency=None: rupees(float(v)),
                            cint=lambda v: int(v), flt=flt)
    return SimpleNamespace(db=db, utils=utils)


@lru_cache(maxsize=1)
def _env():
    import jinja2

    shims = jinja2.DictLoader({
        "templates/print_formats/standard_macros.html":
            "{% macro add_header() %}{% endmacro %}{% macro render_field() %}{% endmacro %}{% macro print_value() %}{% endmacro %}",
        "india_compliance/gst_india/print_format/e_invoice/e_invoice.css": (VENDOR / "ic_e_invoice.css").read_text(),
    })
    env = jinja2.Environment(loader=jinja2.ChoiceLoader([jinja2.FileSystemLoader([FORMATS, VENDOR]), shims]),
                             autoescape=False, extensions=["jinja2.ext.do"])
    env.globals.update(json=json, _=lambda s: s, _dict=dict)
    return env


def _shell(body: str, page: str, css: str = "_frappe_print.css", margin: str = "12mm 10mm") -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{css}">'
            f"<style>@page {{ size: {page}; margin: {margin}; }}</style></head>"
            f'<body><div class="print-format">{body}</div></body></html>')


def render_e_invoice(inv: TruthInvoice, supplier: Party, buyer: Party, doc: dict) -> str:
    data = e_invoice_json(inv, supplier, buyer)
    qr = signed_qr(data)
    env = _env()
    body = env.get_template("ic_e_invoice.html").render(
        doc=_Doc(irn=data["Irn"], name=inv.invoice_no, ewaybill=None),
        frappe=_frappe(json.dumps(data), qr), print_settings=SimpleNamespace(repeat_header_footer=False),
        letter_head="", no_letterhead=True, footer="", get_state=lambda c: STATE_NAMES[c],
        get_qr_code=qr_png_b64, get_e_invoice_item_fields=lambda d: _nonzero(d, E_INVOICE_ITEM_FIELDS, {"GstRt"}),
        get_e_invoice_amount_fields=lambda d, _doc: _nonzero(
            d, E_INVOICE_AMOUNT_FIELDS, {"CgstVal", "SgstVal"} if heads(inv)["intra"] else {"IgstVal"}))
    return _shell(body, "A4")


def render_pos(inv: TruthInvoice, supplier: Party, buyer: Party, doc: dict) -> str:
    x = doc.get("extra", {})
    h = heads(inv)
    items = [_Doc(item_code=l.description, item_name=l.description, gst_hsn_code=l.hsn, serial_no=None,
                  qty=float(l.quantity), rate=float(l.unit_price), amount=l.taxable_value) for l in inv.line_items]
    rate = inv.line_items[0].rate
    taxes = [_Doc(description=n, rate=rate / 2, tax_amount=v, included_in_print_rate=0)
             for n, v in (("CGST", inv.cgst), ("SGST", inv.sgst))] if h["intra"] else \
            [_Doc(description="IGST", rate=rate, tax_amount=inv.igst, included_in_print_rate=0)]
    d = _Doc(company=supplier.name, company_address_display=supplier.address.replace(", ", "<br>"), company_gstin=supplier.gstin,
             docstatus=1, status="Paid", select_print_heading=None, name=inv.invoice_no, owner=x.get("cashier", "pos@local"),
             posting_date=inv.invoice_date, posting_time=x.get("time", "12:00:00"), grand_total=inv.total,
             address_display=buyer.address, customer_name=buyer.name, items=items,
             flags=SimpleNamespace(show_inclusive_tax_in_print=False), total=inv.taxable_value, net_total=inv.taxable_value,
             taxes=taxes, discount_amount=0, rounded_total=inv.total, payments=[_Doc(mode_of_payment="UPI", amount=inv.total)],
             paid_amount=inv.total, change_amount=0, terms="")
    body = _env().get_template("ic_gst_pos_invoice.html").render(doc=d, letter_head="")
    return _shell(body, "80mm 300mm", "_frappe_pos.css", "4mm")


def render_port(name: str, inv: TruthInvoice, supplier: Party, buyer: Party, doc: dict) -> str:
    return _env().get_template(f"{name}.html.j2").render(**common(inv, supplier, buyer, doc))


RENDERERS = {"ic_e_invoice": render_e_invoice, "ic_pos_invoice": render_pos}
METHOD = {"ic_e_invoice": "original", "ic_pos_invoice": "original"}


def render_html(fmt: str, inv: TruthInvoice, supplier: Party, buyer: Party, doc: dict) -> str:
    if fmt in RENDERERS:
        return RENDERERS[fmt](inv, supplier, buyer, doc)
    return render_port(fmt, inv, supplier, buyer, doc)


def html_to_pdf(html: str) -> bytes:
    from gst_recon.render import pdf as rpdf

    rpdf._setup_fontconfig()
    import weasyprint

    return weasyprint.HTML(string=html, base_url=str(FORMATS)).write_pdf()
