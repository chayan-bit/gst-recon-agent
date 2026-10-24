"""Link each document to its purchase-register vouchers, its GSTR-2B entry and its bank payments.

Only what is printed in the case is used: invoice number, GSTIN (and its PAN), date, amounts and the
payee name / invoice tag in bank narrations. No hidden ids. Every candidate pair gets an additive score
from visible evidence; pairs are assigned greedily, best first, one-to-one (a register row may join an
already-linked document only as an exact duplicate voucher). Each decision is written to the trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gst_recon.schema import BankTxn, CaseInputs, DocType, PurchaseRegisterRow, TruthInvoice
from gst_recon.sim.rules import AMOUNT_TOLERANCE, HEADS, Link

MIN_REGISTER = 7  # e.g. exact GSTIN + date + amounts with a mistyped invoice number scores 10
MIN_2B = 7
MIN_NAME = 0.6  # share of the (truncated) payee name found in the narration


def lev(a: str, b: str, cap: int = 3) -> int:
    """Levenshtein distance, saturating at `cap`."""
    if abs(len(a) - len(b)) >= cap:
        return cap
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return min(prev[-1], cap)


def norm_no(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= AMOUNT_TOLERANCE


def _no_score(a: str, b: str) -> tuple[int, str]:
    d = lev(norm_no(a), norm_no(b))
    return {0: (4, "invoice no equal"), 1: (2, "invoice no 1 edit apart")}.get(d, (0, ""))


def _gstin_score(a: str, b: str) -> tuple[int, str]:
    a, b = a.strip().upper(), b.strip().upper()
    if a == b:
        return 3, "GSTIN equal"
    if lev(a, b) <= 2:
        return 2, "GSTIN within 2 edits"
    if len(a) == len(b) == 15 and a[2:12] == b[2:12]:
        return 2, "same PAN, other registration"
    return 0, ""


def _score(parts: list[tuple[int, str]]) -> tuple[int, list[str]]:
    return sum(p for p, _ in parts), [why for p, why in parts if p]


# ------------------------------------------------------------------ register


def _register_score(inv: TruthInvoice, row: PurchaseRegisterRow) -> tuple[int, list[str]]:
    if (row.voucher_type.lower() == "debit note") != (inv.doc_type == DocType.CREDIT_NOTE):
        return 0, []
    heads_ok = all(_close(getattr(inv, h), getattr(row, h)) for h in HEADS)
    return _score([_no_score(inv.invoice_no, row.supplier_invoice_no), _gstin_score(inv.supplier_gstin, row.party_gstin),
                   (2, "invoice date equal") if inv.invoice_date == row.supplier_invoice_date else (0, ""),
                   (1, "taxable equal") if _close(inv.taxable_value, row.taxable_value) else (0, ""),
                   (1, "tax heads equal") if heads_ok else (0, ""),
                   (1, "total equal") if _close(inv.total, row.total) else (0, "")])


def _row_content(row: PurchaseRegisterRow) -> dict:
    return row.model_dump(exclude={"voucher_no", "voucher_date"})


def link_register(invoices: list[TruthInvoice], rows: list[PurchaseRegisterRow], trace: dict) -> dict[str, list[str]]:
    pairs = sorted(((s, why, inv.doc_id, i) for inv in invoices for i, row in enumerate(rows)
                    for s, why in [_register_score(inv, row)] if s >= MIN_REGISTER), key=lambda p: (-p[0], p[2], p[3]))
    out: dict[str, list[str]] = {}
    primary: dict[str, int] = {}
    used: set[int] = set()
    for s, why, doc, i in pairs:  # one-to-one, best first
        if doc in primary or i in used:
            continue
        primary[doc], out[doc] = i, [rows[i].voucher_no]
        used.add(i)
        trace[doc]["register"].append({"voucher": rows[i].voucher_no, "score": s, "evidence": why})
    for s, why, doc, i in pairs:  # a leftover voucher identical to a linked one is a duplicate booking
        if i in used or doc not in primary or _row_content(rows[i]) != _row_content(rows[primary[doc]]):
            continue
        used.add(i)
        out[doc].append(rows[i].voucher_no)
        trace[doc]["register"].append({"voucher": rows[i].voucher_no, "score": s,
                                       "evidence": why + [f"identical to {rows[primary[doc]].voucher_no} (duplicate voucher)"]})
    trace["_unlinked"]["register"] = [rows[i].voucher_no for i in range(len(rows)) if i not in used]
    return out


# ------------------------------------------------------------------ GSTR-2B


@dataclass(frozen=True)
class _TwoBRow:
    key: tuple[str, str, str]  # (rtnprd, ctin, inum/ntnum), the rules engine's GSTR-2B key
    is_note: bool
    dt: str
    val: float
    taxable: float
    heads: dict


def _twob_rows(inputs: CaseInputs) -> list[_TwoBRow]:
    """Every printed GSTR-2B document, one row each (rows are linked one-to-one, even if two share a key)."""
    out = []
    for g in inputs.gstr2b:
        docs = [(s.ctin, i.inum, i, False) for s in g.data.docdata.b2b for i in s.inv]
        docs += [(s.ctin, n.ntnum, n, True) for s in g.data.docdata.cdnr for n in s.nt]
        for ctin, num, d, note in docs:
            out.append(_TwoBRow((g.data.rtnprd, ctin, num), note, d.dt, d.val, sum(it.txval for it in d.items),
                                {h: sum(getattr(it, h) for it in d.items) for h in HEADS}))
    return out


def _twob_score(inv: TruthInvoice, row: _TwoBRow) -> tuple[int, list[str]]:
    if row.is_note != (inv.doc_type == DocType.CREDIT_NOTE):
        return 0, []
    return _score([_no_score(inv.invoice_no, row.key[2]), _gstin_score(inv.supplier_gstin, row.key[1]),
                   (2, "date equal") if row.dt == inv.invoice_date.strftime("%d-%m-%Y") else (0, ""),
                   (1, "taxable equal") if _close(inv.taxable_value, row.taxable) else (0, ""),
                   (1, "tax heads equal") if all(_close(getattr(inv, h), row.heads[h]) for h in HEADS) else (0, ""),
                   (1, "value equal") if _close(inv.total, row.val) else (0, "")])


def link_2b(inputs: CaseInputs, trace: dict) -> dict[str, tuple[str, str, str]]:
    rows = _twob_rows(inputs)
    pairs = sorted(((s, why, inv.doc_id, j) for inv in inputs.invoices for j, row in enumerate(rows)
                    for s, why in [_twob_score(inv, row)] if s >= MIN_2B), key=lambda p: (-p[0], p[2], p[3]))
    out: dict[str, tuple[str, str, str]] = {}
    used: set[int] = set()
    for s, why, doc, j in pairs:
        if doc in out or j in used:
            continue
        out[doc] = rows[j].key
        used.add(j)
        trace[doc]["gstr2b"] = {"period": rows[j].key[0], "ctin": rows[j].key[1], "doc_no": rows[j].key[2], "score": s, "evidence": why}
    trace["_unlinked"]["gstr2b"] = [list(r.key) for j, r in enumerate(rows) if j not in used]
    return out


# ------------------------------------------------------------------ bank


@dataclass(frozen=True)
class _Due:
    inv: TruthInvoice
    net: float  # invoice total less its credit notes: what a full payment would be


def _canon(s: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9&]+", " ", s.upper()).split())


def name_share(name: str, narration: str) -> float:
    """Longest prefix of the supplier name found in the narration, relative to the shorter of the name and
    18 characters (bank narrations truncate payee names to 18 to 28 characters)."""
    n, t = _canon(name), _canon(narration)
    k = len(n)
    while k and n[:k] not in t:
        k -= 1
    return min(1.0, k / max(1, min(len(n), 18)))


def _pay_score(due: _Due, t: BankTxn) -> tuple[float, list[str]] | None:
    inv = due.inv
    if t.debit <= 0 or t.txn_date < inv.invoice_date:
        return None
    if t.debit > due.net + AMOUNT_TOLERANCE:
        return None  # one payment per invoice, never more than is due
    no = norm_no(inv.invoice_no)
    tagged = bool(no) and re.search(rf"INV{re.escape(no)}(?![A-Z0-9])", norm_no(t.narration)) is not None
    share = name_share(inv.supplier_name, t.narration)
    if share < MIN_NAME and not tagged:
        return None
    why = [f"payee name match {share:.2f}"]
    s = 4 * share
    if tagged:
        s += 5
        why.append("narration carries the invoice no")
    if _close(t.debit, due.net):
        s += 4
        why.append(f"amount equals net due {due.net:.2f}")
    elif t.debit >= 0.25 * due.net:
        s += 1
        why.append(f"part payment {t.debit:.2f} of {due.net:.2f}")
    else:
        return None
    s -= 0.0001 * (t.txn_date - inv.invoice_date).days  # tie-break: the earliest open invoice is paid first
    return s, why


def link_payments(inputs: CaseInputs, trace: dict) -> dict[str, list[str]]:
    notes = [i for i in inputs.invoices if i.doc_type == DocType.CREDIT_NOTE]
    dues = [_Due(i, i.total - sum(n.total for n in notes if n.supplier_gstin == i.supplier_gstin
                                  and norm_no(n.original_invoice_no or "") == norm_no(i.invoice_no)))
            for i in inputs.invoices if i.doc_type == DocType.INVOICE]
    pairs = sorted(((s, why, d.inv.doc_id, j) for d in dues for j, t in enumerate(inputs.bank_statement)
                    for r in [_pay_score(d, t)] if r for s, why in [r]), key=lambda p: (-p[0], p[2], p[3]))
    out: dict[str, list[str]] = {}
    used: set[int] = set()
    for s, why, doc, j in pairs:
        if doc in out or j in used:
            continue
        t = inputs.bank_statement[j]
        out[doc] = [t.ref_no]
        used.add(j)
        trace[doc]["payments"].append({"ref": t.ref_no, "date": t.txn_date.isoformat(), "amount": t.debit,
                                       "score": round(s, 3), "evidence": why})
    trace["_unlinked"]["supplier_like_debits"] = [
        t.ref_no for j, t in enumerate(inputs.bank_statement) if t.debit > 0 and j not in used
        and any(name_share(d.inv.supplier_name, t.narration) >= MIN_NAME for d in dues)]
    return out


def link_documents(inputs: CaseInputs) -> tuple[dict[str, Link], dict]:
    trace: dict = {inv.doc_id: {"register": [], "gstr2b": None, "payments": []} for inv in inputs.invoices}
    trace["_unlinked"] = {}
    reg = link_register(inputs.invoices, inputs.purchase_register, trace)
    twob = link_2b(inputs, trace)
    pay = link_payments(inputs, trace)
    links = {i.doc_id: Link(tuple(reg.get(i.doc_id, ())), twob.get(i.doc_id), tuple(pay.get(i.doc_id, ())))
             for i in inputs.invoices}
    return links, trace
