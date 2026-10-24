"""Hand-built case fixtures for rules and reward tests."""

from __future__ import annotations

from datetime import date

from gst_recon.schema import (
    BankTxn, CaseInputs, DocType, Gstr2b, Gstr2bB2bSupplier, Gstr2bCdnrSupplier, Gstr2bData,
    Gstr2bDocData, Gstr2bInvoice, Gstr2bItem, Gstr2bNote, ItcCategory, Party, PurchaseRegisterRow,
    TruthInvoice, TruthLineItem,
)
from gst_recon.sim.gstin import make_gstin
from gst_recon.sim.money import r2, split_tax

BUYER = Party(name="Buyer Pvt Ltd", gstin=make_gstin("27", "AABCB1234C"), state_code="27", address="Pune")
SUP_LOCAL = make_gstin("27", "AAFCS5678D")  # same state -> CGST+SGST
SUP_OTHER = make_gstin("29", "AAFCT9012E")  # other state -> IGST
SUP_LOCAL_ALT = make_gstin("24", "AAFCS5678D")  # same PAN, Gujarat registration
PERIOD = "062024"


def line(taxable: float, rate: float, intra: bool = True, cess_rate: float = 0.0,
         category: ItcCategory = ItcCategory.NORMAL, hsn: str = "8471") -> TruthLineItem:
    igst, cgst, sgst = split_tax(taxable, rate, intra)
    return TruthLineItem(description="item", hsn=hsn, quantity=1, unit="Nos", unit_price=taxable,
                         taxable_value=taxable, rate=rate, igst=igst, cgst=cgst, sgst=sgst,
                         cess=r2(taxable * cess_rate / 100), category=category)


def invoice(doc_id: str, lines: list[TruthLineItem], gstin: str = SUP_LOCAL, no: str = "INV-1",
            dt: date = date(2024, 6, 10), rcm: bool = False, doc_type: DocType = DocType.INVOICE,
            original: str | None = None) -> TruthInvoice:
    heads = {h: r2(sum(getattr(l, h) for l in lines)) for h in ("taxable_value", "igst", "cgst", "sgst", "cess")}
    tax = heads["igst"] + heads["cgst"] + heads["sgst"] + heads["cess"]
    return TruthInvoice(doc_id=doc_id, doc_type=doc_type, supplier_gstin=gstin, supplier_name="Supplier",
                        supplier_address="x", buyer_gstin=BUYER.gstin, buyer_name=BUYER.name, invoice_no=no,
                        invoice_date=dt, place_of_supply="27", reverse_charge=rcm, original_invoice_no=original,
                        line_items=lines, total=r2(heads["taxable_value"] + (0 if rcm else tax)), **heads)


def items_of(inv: TruthInvoice, scale: float = 1.0) -> list[Gstr2bItem]:
    return [Gstr2bItem(num=i, rt=l.rate, txval=r2(l.taxable_value * scale), igst=r2(l.igst * scale),
                       cgst=r2(l.cgst * scale), sgst=r2(l.sgst * scale), cess=r2(l.cess * scale))
            for i, l in enumerate(inv.line_items, 1)]


def twob(period: str, invs: list[tuple[TruthInvoice, str, float]]) -> Gstr2b:
    """invs: (invoice, ctin as filed, amount scale)."""
    b2b, cdnr = {}, {}
    for inv, ctin, scale in invs:
        common = dict(dt=inv.invoice_date.strftime("%d-%m-%Y"), val=inv.total, pos="27",
                      rev="Y" if inv.reverse_charge else "N", items=items_of(inv, scale))
        if inv.doc_type == DocType.CREDIT_NOTE:
            cdnr.setdefault(ctin, Gstr2bCdnrSupplier(ctin=ctin, trdnm="S", supfildt="11-07-2024", supprd=period, nt=[]))
            cdnr[ctin].nt.append(Gstr2bNote(ntnum=inv.invoice_no, **common))
        else:
            b2b.setdefault(ctin, Gstr2bB2bSupplier(ctin=ctin, trdnm="S", supfildt="11-07-2024", supprd=period, inv=[]))
            b2b[ctin].inv.append(Gstr2bInvoice(inum=inv.invoice_no, **common))
    return Gstr2b(data=Gstr2bData(gstin=BUYER.gstin, rtnprd=period, gendt="14-07-2024",
                                  docdata=Gstr2bDocData(b2b=list(b2b.values()), cdnr=list(cdnr.values()))))


def reg_row(inv: TruthInvoice, vno: str, **override) -> PurchaseRegisterRow:
    base = dict(voucher_no=vno, voucher_date=inv.invoice_date, voucher_type="Purchase", party_name="Supplier",
                party_gstin=inv.supplier_gstin, supplier_invoice_no=inv.invoice_no,
                supplier_invoice_date=inv.invoice_date, taxable_value=inv.taxable_value, igst=inv.igst,
                cgst=inv.cgst, sgst=inv.sgst, cess=inv.cess, total=inv.total, reverse_charge=inv.reverse_charge)
    return PurchaseRegisterRow(**(base | override))


def pay(ref: str, amount: float, when: date = date(2024, 7, 1)) -> BankTxn:
    return BankTxn(txn_date=when, narration=f"NEFT DR/{ref}", ref_no=ref, debit=amount, credit=0, balance=0)


def inputs(invs, register=(), gstr2b=(), bank=(), as_of=date(2024, 7, 15)) -> CaseInputs:
    return CaseInputs(buyer=BUYER, period=PERIOD, as_of_date=as_of, invoices=list(invs),
                      purchase_register=list(register), gstr2b=list(gstr2b), bank_statement=list(bank))
