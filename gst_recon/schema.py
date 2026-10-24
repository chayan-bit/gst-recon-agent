"""Single source of truth for gst-recon data shapes.

Three groups of models:
1. Input truth: the four documents per case (invoice, purchase register row,
   GSTR-2B, bank statement txn) as the simulator knows them before rendering.
2. Model output (`ReconOutput`): extraction + match table + ITC decision.
   Its JSON Schema is exported to `schemas/output.schema.json` for
   SGLang/XGrammar constrained decoding, so it deliberately avoids nulls,
   numeric/string constraints, patterns and formats (see `output_json_schema`).
3. `Case`: one simulated month for one buyer (inputs + expected output).

Run `python -m gst_recon.schema` to regenerate the exported schema.
"""

from __future__ import annotations

import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "output.schema.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- enums


class DocType(str, Enum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"


class MatchFlag(str, Enum):
    MISSING_IN_2B = "missing_in_2b"
    GSTIN_MISMATCH = "gstin_mismatch"
    AMOUNT_MISMATCH = "amount_mismatch"
    DUPLICATE = "duplicate"
    PERIOD_MISMATCH = "period_mismatch"
    UNPAID_180D = "unpaid_180d"


class ReasonCode(str, Enum):
    """ITC reason codes. Section refs are to the CGST Act 2017 unless noted."""

    ELIGIBLE = "ELIGIBLE"  # s.16(1), all s.16(2) conditions met
    RCM_ELIGIBLE = "RCM_ELIGIBLE"  # s.9(3)/9(4) tax paid by recipient, credit via s.16
    BLOCKED_MOTOR_VEHICLE = "BLOCKED_MOTOR_VEHICLE"  # s.17(5)(a), (ab)
    BLOCKED_FOOD_BEVERAGE = "BLOCKED_FOOD_BEVERAGE"  # s.17(5)(b)(i)
    BLOCKED_CLUB_MEMBERSHIP = "BLOCKED_CLUB_MEMBERSHIP"  # s.17(5)(b)(ii)
    BLOCKED_WORKS_CONTRACT = "BLOCKED_WORKS_CONTRACT"  # s.17(5)(c), (d)
    BLOCKED_PERSONAL_USE = "BLOCKED_PERSONAL_USE"  # s.17(5)(g)
    BLOCKED_GIFT = "BLOCKED_GIFT"  # s.17(5)(h)
    DEFERRED_NOT_IN_2B = "DEFERRED_NOT_IN_2B"  # s.16(2)(aa), s.38
    DEFERRED_PERIOD_MISMATCH = "DEFERRED_PERIOD_MISMATCH"  # s.16(2)(aa): claim in the 2B period
    DEFERRED_GSTIN_MISMATCH = "DEFERRED_GSTIN_MISMATCH"  # s.16(2)(aa): not reflected against this supplier
    DEFERRED_AMOUNT_MISMATCH = "DEFERRED_AMOUNT_MISMATCH"  # s.16(2)(aa) + r.36(4): excess over 2B
    DEFERRED_UNPAID_180D = "DEFERRED_UNPAID_180D"  # s.16(2) 2nd/3rd proviso, r.37
    CREDIT_NOTE_REVERSAL = "CREDIT_NOTE_REVERSAL"  # s.34 + s.16: credit note reduces ITC


class ItcCategory(str, Enum):
    """Truth-only: what an inward supply is used for (drives s.17(5))."""

    NORMAL = "normal"
    MOTOR_VEHICLE = "motor_vehicle"
    FOOD_BEVERAGE = "food_beverage"
    CLUB_MEMBERSHIP = "club_membership"
    WORKS_CONTRACT = "works_contract"
    PERSONAL_USE = "personal_use"
    GIFT = "gift"


class BusinessProfile(str, Enum):
    """What the buyer does; decides several s.17(5) exceptions."""

    MANUFACTURER = "manufacturer"
    IT_SERVICES = "it_services"
    TRADING_COMPANY = "trading_company"
    CAR_DEALER = "car_dealer"
    PASSENGER_TRANSPORT = "passenger_transport"
    DRIVING_SCHOOL = "driving_school"
    HOTEL = "hotel"
    CATERER = "caterer"
    GYM_OPERATOR = "gym_operator"
    CONSTRUCTION_CONTRACTOR = "construction_contractor"
    AUTO_WORKSHOP = "auto_workshop"


class LinePurpose(str, Enum):
    """Truth-only: what the buyer uses a line for. Visible to the model only via
    the buyer profile header or the invoice remarks (see sim/RULES.md)."""

    BUSINESS = "business"  # ordinary business use
    FURTHER_SUPPLY = "further_supply"  # resale / same-category outward supply / composite element
    PASSENGER_TRANSPORT = "passenger_transport"
    DRIVING_TRAINING = "driving_training"
    FACTORY_CANTEEN = "factory_canteen"
    STAFF_WELFARE = "staff_welfare"
    OWN_CONSTRUCTION = "own_construction"
    PERSONAL = "personal"
    GIFT = "gift"


# ------------------------------------------------------------------- input truth


class Party(_Strict):
    name: str
    gstin: str
    state_code: str  # 2-digit GST state code, e.g. "27"
    address: str


class BuyerProfile(_Strict):
    """Company header shown to the model with every case."""

    profile: BusinessProfile
    description: str  # e.g. "Business hotel with restaurant and banquets. Employees: 140."
    employees: int


class TruthLineItem(_Strict):
    description: str
    hsn: str  # HSN (goods) or SAC (services) code
    quantity: float
    unit: str
    unit_price: float
    taxable_value: float
    rate: float  # total GST rate in percent: 0, 5, 12, 18, 28
    igst: float
    cgst: float
    sgst: float
    cess: float
    category: ItcCategory = ItcCategory.NORMAL
    concept: str = ""  # catalog concept id (truth-only)
    purpose: LinePurpose = LinePurpose.BUSINESS  # truth-only


class TruthInvoice(_Strict):
    """An invoice or credit note as issued by the supplier (rendering source)."""

    doc_id: str  # stable id of the rendered document within the case, e.g. "D03"
    doc_type: DocType
    supplier_gstin: str
    supplier_name: str
    supplier_address: str
    buyer_gstin: str
    buyer_name: str
    invoice_no: str
    invoice_date: date
    place_of_supply: str  # 2-digit state code
    reverse_charge: bool
    original_invoice_no: str | None = None  # credit notes only
    line_items: list[TruthLineItem]
    taxable_value: float
    igst: float
    cgst: float
    sgst: float
    cess: float
    total: float  # amount payable to supplier; excludes tax when reverse_charge
    remarks: str = ""  # free-text "Remarks / Purpose" line printed on the document, "" if none


class PurchaseRegisterRow(_Strict):
    """One voucher in a Tally-style purchase register export."""

    voucher_no: str
    voucher_date: date
    voucher_type: str  # "Purchase" or "Debit Note" (buyer's side of a supplier credit note)
    party_name: str
    party_gstin: str
    supplier_invoice_no: str
    supplier_invoice_date: date
    taxable_value: float
    igst: float
    cgst: float
    sgst: float
    cess: float
    total: float
    reverse_charge: bool


class Gstr2bItem(_Strict):
    num: int
    rt: float
    txval: float
    igst: float
    cgst: float
    sgst: float
    cess: float


class Gstr2bInvoice(_Strict):
    inum: str
    typ: str = "R"  # R = regular
    dt: str  # DD-MM-YYYY
    val: float
    pos: str
    rev: str  # "Y" / "N"
    itcavl: str = "Y"
    rsn: str = ""
    diffprcnt: float = 1
    srctyp: str = ""
    irn: str = ""
    irngendate: str = ""
    items: list[Gstr2bItem]


class Gstr2bB2bSupplier(_Strict):
    ctin: str
    trdnm: str
    supfildt: str  # DD-MM-YYYY
    supprd: str  # MMYYYY
    inv: list[Gstr2bInvoice]


class Gstr2bNote(_Strict):
    ntnum: str
    typ: str = "C"  # C = credit note, D = debit note
    suptyp: str = "R"
    dt: str
    val: float
    pos: str
    rev: str
    itcavl: str = "Y"
    rsn: str = ""
    diffprcnt: float = 1
    srctyp: str = ""
    irn: str = ""
    irngendate: str = ""
    items: list[Gstr2bItem]


class Gstr2bCdnrSupplier(_Strict):
    ctin: str
    trdnm: str
    supfildt: str
    supprd: str
    nt: list[Gstr2bNote]


class Gstr2bDocData(_Strict):
    b2b: list[Gstr2bB2bSupplier] = Field(default_factory=list)
    cdnr: list[Gstr2bCdnrSupplier] = Field(default_factory=list)


class Gstr2bData(_Strict):
    gstin: str
    rtnprd: str  # MMYYYY
    version: str = "1.0"
    gendt: str  # DD-MM-YYYY
    docdata: Gstr2bDocData


class Gstr2b(_Strict):
    """GSTR-2B download, `data` object only (subset: b2b + cdnr sections)."""

    data: Gstr2bData


class BankTxn(_Strict):
    txn_date: date
    narration: str
    ref_no: str  # UTR / cheque no; payment_refs in the output point here
    debit: float
    credit: float
    balance: float


class CaseInputs(_Strict):
    buyer: Party
    buyer_profile: BuyerProfile | None = None
    period: str  # MMYYYY, the return period being reconciled
    as_of_date: date  # date the reconciliation is performed (180-day rule clock)
    invoices: list[TruthInvoice]
    purchase_register: list[PurchaseRegisterRow]
    gstr2b: list[Gstr2b]  # the period's 2B, plus later periods available by as_of_date
    bank_statement: list[BankTxn]


# ------------------------------------------------------------------ model output


class LineItemOut(_Strict):
    description: str
    hsn: str
    taxable_value: float
    rate: float
    igst: float
    cgst: float
    sgst: float
    cess: float


class ExtractionRecord(_Strict):
    doc_id: str
    doc_type: DocType
    supplier_gstin: str
    supplier_name: str
    invoice_no: str
    invoice_date: str = Field(description="YYYY-MM-DD")
    place_of_supply: str = Field(description="2-digit GST state code")
    reverse_charge: bool
    original_invoice_no: str = Field(description="credit notes only, else empty string")
    line_items: list[LineItemOut]
    taxable_value: float
    igst: float
    cgst: float
    sgst: float
    cess: float
    total: float


class MatchRow(_Strict):
    doc_id: str
    register_vouchers: list[str] = Field(description="matching purchase register voucher_no values")
    gstr2b_period: str = Field(description="MMYYYY of the GSTR-2B where found, else empty string")
    gstr2b_ctin: str = Field(description="supplier GSTIN as shown in GSTR-2B, else empty string")
    gstr2b_doc_no: str = Field(description="inum/ntnum as shown in GSTR-2B, else empty string")
    payment_refs: list[str] = Field(description="bank statement ref_no values paying this document")
    flags: list[MatchFlag]


class TaxHeads(_Strict):
    igst: float
    cgst: float
    sgst: float
    cess: float


class ItcDecision(_Strict):
    doc_id: str
    eligible: TaxHeads
    blocked: TaxHeads
    deferred: TaxHeads
    reasons: list[ReasonCode]


class ItcTotals(_Strict):
    eligible: TaxHeads
    blocked: TaxHeads
    deferred: TaxHeads


class ReconOutput(_Strict):
    extractions: list[ExtractionRecord]
    matches: list[MatchRow]
    itc: list[ItcDecision]
    itc_totals: ItcTotals


class Case(_Strict):
    case_id: str
    seed: int
    difficulty: str
    inputs: CaseInputs
    expected: ReconOutput
    split: str = "train"  # train | test_iid | test_ood
    anomalies: list[str] = Field(default_factory=list)  # generator log, for debugging/stratified eval
    # 2 = diverse per-supplier invoice-number and date formats (train data); omitted at 1 so v1 files stay byte-identical
    fmt_version: int = Field(default=1, exclude_if=lambda v: v == 1)


# ------------------------------------------------------------- schema export

_DROP_KEYS = {"title", "default", "examples"}


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline(defs[node["$ref"].rsplit("/", 1)[-1]], defs)
        return {k: _inline(v, defs) for k, v in node.items() if k not in _DROP_KEYS and k != "$defs"}
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


def output_json_schema() -> dict[str, Any]:
    """JSON Schema for ReconOutput, flattened for grammar-constrained decoding.

    Dropped vs pydantic's default output: `$defs`/`$ref` (inlined; the model is
    non-recursive), `title`, `default`. No nulls, formats, patterns or numeric
    bounds are used by the output models in the first place: dates are plain
    strings documented as YYYY-MM-DD and validated by the reward code instead.
    """
    raw = ReconOutput.model_json_schema()
    return _inline(raw, raw.get("$defs", {}))


def export_output_schema(path: Path = SCHEMA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output_json_schema(), indent=2) + "\n")
    return path


if __name__ == "__main__":
    print(export_output_schema())
