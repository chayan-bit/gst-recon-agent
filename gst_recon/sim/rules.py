"""Ground-truth rules engine: match flags and ITC decision per document.

Pure function of the case inputs plus the true document links (which register
vouchers, GSTR-2B entry and bank payments belong to each invoice; the
simulator knows them because it created them). Section refs are CGST Act 2017
and CGST Rules 2017. Simplifications are listed in RULES.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from gst_recon.schema import (
    BuyerProfile,
    BusinessProfile,
    CaseInputs,
    DocType,
    ExtractionRecord,
    ItcCategory,
    ItcDecision,
    ItcTotals,
    LineItemOut,
    LinePurpose,
    MatchFlag,
    MatchRow,
    ReasonCode,
    ReconOutput,
    TaxHeads,
    TruthInvoice,
    TruthLineItem,
)
from gst_recon.sim.money import r2

HEADS = ("igst", "cgst", "sgst", "cess")
AMOUNT_TOLERANCE = 1.0  # rupees; differences at or below this are rounding noise
UNPAID_DAYS = 180

BLOCK_REASON = {
    ItcCategory.MOTOR_VEHICLE: ReasonCode.BLOCKED_MOTOR_VEHICLE,
    ItcCategory.FOOD_BEVERAGE: ReasonCode.BLOCKED_FOOD_BEVERAGE,
    ItcCategory.CLUB_MEMBERSHIP: ReasonCode.BLOCKED_CLUB_MEMBERSHIP,
    ItcCategory.WORKS_CONTRACT: ReasonCode.BLOCKED_WORKS_CONTRACT,
    ItcCategory.PERSONAL_USE: ReasonCode.BLOCKED_PERSONAL_USE,
    ItcCategory.GIFT: ReasonCode.BLOCKED_GIFT,
}

Heads = dict[str, float]


@dataclass(frozen=True)
class Link:
    register_vouchers: tuple[str, ...] = ()
    gstr2b: tuple[str, str, str] | None = None  # (rtnprd, ctin, inum/ntnum)
    payment_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class TwoBEntry:
    period: str
    ctin: str
    doc_no: str
    taxable: float
    heads: Heads = field(default_factory=dict)


def _zero() -> Heads:
    return {h: 0.0 for h in HEADS}


def _heads_of(obj) -> Heads:
    return {h: float(getattr(obj, h)) for h in HEADS}


def index_2b(inputs: CaseInputs) -> dict[tuple[str, str, str], TwoBEntry]:
    out: dict[tuple[str, str, str], TwoBEntry] = {}
    for doc in inputs.gstr2b:
        period = doc.data.rtnprd
        rows = [(s.ctin, i.inum, i.items) for s in doc.data.docdata.b2b for i in s.inv]
        rows += [(s.ctin, n.ntnum, n.items) for s in doc.data.docdata.cdnr for n in s.nt]
        for ctin, num, items in rows:
            heads = {h: r2(sum(getattr(it, h) for it in items)) for h in HEADS}
            out[(period, ctin, num)] = TwoBEntry(period, ctin, num, r2(sum(it.txval for it in items)), heads)
    return out


# ------------------------------------------------------------------ match flags


def _differs(a: float, b: float) -> bool:
    return abs(a - b) > AMOUNT_TOLERANCE


def _amounts_differ(inv: TruthInvoice, taxable: float, heads: Heads) -> bool:
    return _differs(inv.taxable_value, taxable) or any(_differs(getattr(inv, h), heads[h]) for h in HEADS)


def outstanding(inv: TruthInvoice, inputs: CaseInputs, link: Link) -> float:
    """Amount still payable to the supplier on as_of_date (net of credit notes)."""
    paid = sum(t.debit for t in inputs.bank_statement if t.ref_no in link.payment_refs and t.txn_date <= inputs.as_of_date)
    credited = sum(
        cn.total
        for cn in inputs.invoices
        if cn.doc_type == DocType.CREDIT_NOTE
        and cn.supplier_gstin == inv.supplier_gstin
        and cn.original_invoice_no == inv.invoice_no
    )
    return max(0.0, r2(inv.total - paid - credited))


def is_unpaid_180d(inv: TruthInvoice, inputs: CaseInputs, link: Link) -> bool:
    """s.16(2) second proviso + r.37(1): supplier not paid within 180 days of
    invoice date. Not applicable to reverse charge supplies (r.37(1)) or credit notes."""
    if inv.doc_type != DocType.INVOICE or inv.reverse_charge:
        return False
    if (inputs.as_of_date - inv.invoice_date).days <= UNPAID_DAYS:
        return False
    return outstanding(inv, inputs, link) > AMOUNT_TOLERANCE


def match_flags(inv: TruthInvoice, inputs: CaseInputs, link: Link, twob: dict) -> list[MatchFlag]:
    regs = {r.voucher_no: r for r in inputs.purchase_register}
    rows = [regs[v] for v in link.register_vouchers if v in regs]
    entry = twob.get(link.gstr2b) if link.gstr2b else None
    flags: set[MatchFlag] = set()
    if entry is None:
        flags.add(MatchFlag.MISSING_IN_2B)
    else:
        if entry.period != inputs.period:
            flags.add(MatchFlag.PERIOD_MISMATCH)
        if entry.ctin != inv.supplier_gstin:
            flags.add(MatchFlag.GSTIN_MISMATCH)
        if _amounts_differ(inv, entry.taxable, entry.heads):
            flags.add(MatchFlag.AMOUNT_MISMATCH)
    for row in rows:
        if row.party_gstin.upper() != inv.supplier_gstin:
            flags.add(MatchFlag.GSTIN_MISMATCH)
        if _amounts_differ(inv, row.taxable_value, _heads_of(row)) or _differs(inv.total, row.total):
            flags.add(MatchFlag.AMOUNT_MISMATCH)
    if len(rows) > 1:
        flags.add(MatchFlag.DUPLICATE)
    if is_unpaid_180d(inv, inputs, link):
        flags.add(MatchFlag.UNPAID_180D)
    return [f for f in MatchFlag if f in flags]


# ---------------------------------------------------------------------- ITC


CANTEEN_HEADCOUNT = 250  # Factories Act 1948 s.46: canteen mandatory above 250 workers
_MV_EXCEPT = {LinePurpose.FURTHER_SUPPLY, LinePurpose.PASSENGER_TRANSPORT, LinePurpose.DRIVING_TRAINING}


def _employer_obliged(purpose: LinePurpose, profile: BuyerProfile | None) -> bool:
    """s.17(5)(b) second proviso (scope per Circular 172/04/2022: all of clause (b)):
    credit available where the employer is obliged by law to provide it. Only
    modelled case: a factory canteen of a manufacturer with > 250 workers."""
    return (purpose == LinePurpose.FACTORY_CANTEEN and profile is not None
            and profile.profile == BusinessProfile.MANUFACTURER and profile.employees > CANTEEN_HEADCOUNT)


def line_block_reason(line: TruthLineItem, profile: BuyerProfile | None) -> ReasonCode | None:
    """s.17(5) for one line, from its category, its purpose and the buyer profile.
    None = not blocked."""
    p = line.purpose
    if p == LinePurpose.PERSONAL:
        return ReasonCode.BLOCKED_PERSONAL_USE  # s.17(5)(g)
    if p == LinePurpose.GIFT:
        return ReasonCode.BLOCKED_GIFT  # s.17(5)(h)
    if p == LinePurpose.OWN_CONSTRUCTION:
        return ReasonCode.BLOCKED_WORKS_CONTRACT  # s.17(5)(c), (d): own immovable property
    cat = line.category
    if cat == ItcCategory.MOTOR_VEHICLE:
        # s.17(5)(a)(A)-(C) for vehicles; (ab) proviso (i) for their servicing
        return None if p in _MV_EXCEPT else ReasonCode.BLOCKED_MOTOR_VEHICLE
    if cat == ItcCategory.FOOD_BEVERAGE:
        # s.17(5)(b)(i) first proviso: same-category outward supply / composite element
        ok = p == LinePurpose.FURTHER_SUPPLY or _employer_obliged(p, profile)
        return None if ok else ReasonCode.BLOCKED_FOOD_BEVERAGE
    if cat == ItcCategory.CLUB_MEMBERSHIP:
        # s.17(5)(b)(ii): no same-category proviso; employer-obligation proviso never met here
        return None if _employer_obliged(p, profile) else ReasonCode.BLOCKED_CLUB_MEMBERSHIP
    if cat == ItcCategory.WORKS_CONTRACT:
        # s.17(5)(c): except an input service for further supply of works contract service
        return None if p == LinePurpose.FURTHER_SUPPLY else ReasonCode.BLOCKED_WORKS_CONTRACT
    return BLOCK_REASON.get(cat)  # legacy categories PERSONAL_USE / GIFT


def _split_blocked(inv: TruthInvoice, profile: BuyerProfile | None) -> tuple[Heads, Heads, list[ReasonCode]]:
    """s.17(5): tax on blocked line items is never available. Returns
    (blocked heads, remaining heads, reasons)."""
    blocked, remaining, reasons = _zero(), _zero(), []
    for line in inv.line_items:
        reason = line_block_reason(line, profile)
        target = blocked if reason else remaining
        for h in HEADS:
            target[h] += getattr(line, h)
        if reason and any(getattr(line, h) for h in HEADS):
            reasons.append(reason)
    return {h: r2(v) for h, v in blocked.items()}, {h: r2(v) for h, v in remaining.items()}, reasons


def _defer_all(eligible: Heads) -> tuple[Heads, Heads]:
    return _zero(), dict(eligible)


def _cap_to_2b(inv: TruthInvoice, eligible: Heads, entry: TwoBEntry) -> tuple[Heads, Heads]:
    """s.16(2)(aa) + r.36(4): credit only to the extent the supplier reported it
    in GSTR-2B; s.16(2)(a): never more than the invoice shows. The per-head
    shortfall (invoice minus 2B) is taken out of the non-blocked portion."""
    new_elig, deferred = {}, {}
    for h in HEADS:
        shortfall = max(0.0, getattr(inv, h) - entry.heads[h])
        deferred[h] = r2(min(eligible[h], shortfall)) if shortfall > AMOUNT_TOLERANCE else 0.0
        new_elig[h] = r2(eligible[h] - deferred[h])
    return new_elig, deferred


def _apply_180d(inv: TruthInvoice, inputs: CaseInputs, link: Link, eligible: Heads) -> tuple[Heads, Heads]:
    """s.16(2) 2nd proviso: credit proportionate to the unpaid value is reversed
    (3rd proviso: re-availed on payment), so we treat it as deferred."""
    if not is_unpaid_180d(inv, inputs, link):
        return eligible, _zero()
    frac = outstanding(inv, inputs, link) / inv.total
    moved = {h: r2(eligible[h] * frac) for h in HEADS}
    return {h: r2(eligible[h] - moved[h]) for h in HEADS}, moved


def itc_decision(inv: TruthInvoice, inputs: CaseInputs, link: Link, twob: dict) -> ItcDecision:
    if inv.doc_type == DocType.CREDIT_NOTE:
        # s.34 + s.16: a supplier credit note reduces the recipient's ITC.
        neg = {h: -float(getattr(inv, h)) if getattr(inv, h) else 0.0 for h in HEADS}
        return ItcDecision(doc_id=inv.doc_id, eligible=TaxHeads(**neg), blocked=TaxHeads(**_zero()),
                           deferred=TaxHeads(**_zero()), reasons=[ReasonCode.CREDIT_NOTE_REVERSAL])

    blocked, eligible, reasons = _split_blocked(inv, inputs.buyer_profile)
    deferred = _zero()
    if inv.reverse_charge:
        # s.9(3): recipient pays the tax itself; credit does not depend on 2B
        # or on paying the supplier (r.37(1) excludes RCM).
        lead = ReasonCode.RCM_ELIGIBLE
    else:
        lead = ReasonCode.ELIGIBLE
        entry = twob.get(link.gstr2b) if link.gstr2b else None
        if entry is None:
            eligible, deferred = _defer_all(eligible)
            reason = ReasonCode.DEFERRED_NOT_IN_2B
        elif entry.period != inputs.period:
            eligible, deferred = _defer_all(eligible)
            reason = ReasonCode.DEFERRED_PERIOD_MISMATCH
        elif entry.ctin != inv.supplier_gstin:
            eligible, deferred = _defer_all(eligible)
            reason = ReasonCode.DEFERRED_GSTIN_MISMATCH
        else:
            eligible, deferred = _cap_to_2b(inv, eligible, entry)
            reason = ReasonCode.DEFERRED_AMOUNT_MISMATCH
        if any(deferred.values()):
            reasons.append(reason)
        eligible, moved = _apply_180d(inv, inputs, link, eligible)
        if any(moved.values()):
            reasons.append(ReasonCode.DEFERRED_UNPAID_180D)
            deferred = {h: r2(deferred[h] + moved[h]) for h in HEADS}
    if any(eligible.values()) or not reasons:
        reasons.append(lead)
    ordered = [r for r in ReasonCode if r in set(reasons)]
    return ItcDecision(doc_id=inv.doc_id, eligible=TaxHeads(**eligible), blocked=TaxHeads(**blocked),
                       deferred=TaxHeads(**deferred), reasons=ordered)


# ------------------------------------------------------------------ assembly


def extraction_of(inv: TruthInvoice) -> ExtractionRecord:
    return ExtractionRecord(
        doc_id=inv.doc_id, doc_type=inv.doc_type, supplier_gstin=inv.supplier_gstin,
        supplier_name=inv.supplier_name, invoice_no=inv.invoice_no,
        invoice_date=inv.invoice_date.isoformat(), place_of_supply=inv.place_of_supply,
        reverse_charge=inv.reverse_charge, original_invoice_no=inv.original_invoice_no or "",
        line_items=[LineItemOut(**l.model_dump(include={"description", "hsn", "taxable_value", "rate", *HEADS}))
                    for l in inv.line_items],
        taxable_value=inv.taxable_value, igst=inv.igst, cgst=inv.cgst, sgst=inv.sgst, cess=inv.cess,
        total=inv.total,
    )


def totals_of(decisions: list[ItcDecision]) -> ItcTotals:
    def tot(bucket: str) -> TaxHeads:
        return TaxHeads(**{h: r2(sum(getattr(getattr(d, bucket), h) for d in decisions)) for h in HEADS})
    return ItcTotals(eligible=tot("eligible"), blocked=tot("blocked"), deferred=tot("deferred"))


def reconcile(inputs: CaseInputs, links: dict[str, Link]) -> ReconOutput:
    twob = index_2b(inputs)
    matches, itc = [], []
    for inv in inputs.invoices:
        link = links.get(inv.doc_id, Link())
        entry = twob.get(link.gstr2b) if link.gstr2b else None
        matches.append(MatchRow(
            doc_id=inv.doc_id,
            register_vouchers=list(link.register_vouchers),
            gstr2b_period=entry.period if entry else "",
            gstr2b_ctin=entry.ctin if entry else "",
            gstr2b_doc_no=entry.doc_no if entry else "",
            payment_refs=list(link.payment_refs),
            flags=match_flags(inv, inputs, link, twob),
        ))
        itc.append(itc_decision(inv, inputs, link, twob))
    return ReconOutput(extractions=[extraction_of(i) for i in inputs.invoices], matches=matches,
                       itc=itc, itc_totals=totals_of(itc))
