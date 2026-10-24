# Ground-truth rules and simplifications

The rules engine (`rules.py`) derives the expected output from the simulated world.
Section refs are to the CGST Act 2017 and CGST Rules 2017 unless noted.
Every rule here is a deliberate model of the law, not a full restatement of it.

## Tax computation

| Rule | Implementation | Ref |
| --- | --- | --- |
| Intra vs inter-state | Supplier state code (GSTIN chars 1-2) equal to place of supply: CGST + SGST at half the rate each; otherwise IGST at the full rate. | CGST s.9, IGST Act s.5, s.7, s.8 |
| Place of supply | Always the buyer's state (goods delivered to the buyer; B2B services to a registered recipient). | IGST Act s.10(1), s.12(2) |
| Rounding | Each head per line is rounded half-up to 2 dp; headers are sums of lines. No invoice-level round-off to the rupee. | - |
| Cess | Ad valorem compensation cess on a few goods (cars 22%, aerated drinks 12%). | GST (Compensation to States) Act s.8 |
| Reverse charge | Invoice shows the tax but the amount payable to the supplier (`total`) is the taxable value only. | s.9(3) |

## Match flags (per invoice / credit note)

| Flag | Raised when |
| --- | --- |
| `missing_in_2b` | No entry for the document in any provided GSTR-2B. |
| `period_mismatch` | Found, but in a GSTR-2B whose `rtnprd` is not the case period. |
| `gstin_mismatch` | GSTR-2B `ctin` differs from the GSTIN on the invoice, or a linked register row has a different party GSTIN. |
| `amount_mismatch` | Taxable value or any tax head in GSTR-2B, or taxable/any head/total in a linked register row, differs from the invoice by more than Rs 1. |
| `duplicate` | More than one register voucher is linked to the document. |
| `unpaid_180d` | Invoice (not credit note, not RCM), more than 180 days between invoice date and `as_of_date`, and more than Rs 1 still outstanding. |

Flags are emitted in enum order. Links (which voucher, 2B row and bank txn belong to which document) come from the simulator; flags and ITC are then computed from the documents' contents.

## ITC decision (per document, per head: IGST, CGST, SGST, cess)

Every rupee of tax on the document lands in exactly one of eligible / blocked / deferred (tested invariant).
Applied in this order:

1. Credit note: `eligible = -tax` on every head, reason `CREDIT_NOTE_REVERSAL` (s.34, s.16; the recipient must reduce ITC by the tax on a supplier credit note).
2. Blocked lines: tax on lines whose use falls in s.17(5) goes to `blocked`, regardless of 2B or payment:
   - motor vehicles for transport of persons (seating up to 13) and their repair/servicing: s.17(5)(a), (ab) -> `BLOCKED_MOTOR_VEHICLE`
   - food and beverages, outdoor catering: s.17(5)(b)(i) -> `BLOCKED_FOOD_BEVERAGE`
   - membership of a club, health and fitness centre: s.17(5)(b)(ii) -> `BLOCKED_CLUB_MEMBERSHIP`
   - works contract for construction of immovable property (not plant and machinery): s.17(5)(c), (d) -> `BLOCKED_WORKS_CONTRACT`
   - goods or services for personal consumption: s.17(5)(g) -> `BLOCKED_PERSONAL_USE`
   - goods given as gifts: s.17(5)(h) -> `BLOCKED_GIFT`
3. Reverse charge: the remaining tax is `eligible` with `RCM_ELIGIBLE`. It does not depend on GSTR-2B (the recipient itself pays the tax and reports it in GSTR-3B table 4(A)(3)) or on paying the supplier (r.37(1) excludes RCM supplies).
4. Otherwise the remaining tax is tested against GSTR-2B (s.16(2)(aa), r.36(4)):
   - not in any 2B -> all `deferred`, `DEFERRED_NOT_IN_2B`;
   - only in a later period's 2B -> all `deferred`, `DEFERRED_PERIOD_MISMATCH` (claimable in that period);
   - under a different supplier GSTIN -> all `deferred`, `DEFERRED_GSTIN_MISMATCH` (not reflected against this supplier until amended);
   - per head, if 2B shows less than the invoice by more than Rs 1, the shortfall is `deferred` (`DEFERRED_AMOUNT_MISMATCH`); if 2B shows more, credit is still capped at the invoice (s.16(2)(a)).
5. 180-day rule (s.16(2) second and third provisos, r.37): if `unpaid_180d`, the eligible amount times `outstanding / invoice total` moves from `eligible` to `deferred` with `DEFERRED_UNPAID_180D`.
6. `ELIGIBLE` (or `RCM_ELIGIBLE`) is added when any eligible amount is non-zero, or when no other reason applies (e.g. nil-rated supplies). Reasons are emitted in enum order.

`itc_totals` is the per-bucket, per-head sum over all documents.

## Simplifications (deliberate, documented)

1. **Two rate regimes, chosen by supply date.** See "Rate regimes" below. Supply date = invoice date, payment later, no advances, so s.14 always resolves to the rate on the invoice date.
2. **"Deferred" covers both "not yet claimable" and "reverse now, re-avail later".** The 180-day rule strictly requires reversing credit already availed (with interest). We do not model prior-period claims, so the unpaid share is reported as `deferred`. No interest is computed.
3. **Recon timing.** `as_of_date` is either 12-25 days after the period end (normal GSTR-3B timing) or 190-230 days after (a late/annual review, which is when the 180-day rule can bite). The next period's GSTR-2B is provided only if it was generated (14th of the month after next) by `as_of_date`; a late-filed invoice whose 2B is not yet available is therefore just `missing_in_2b`.
4. **Later 2B is partial.** The next period's 2B contains only the late-filed documents of this case, not the supplier's genuine next-month invoices.
5. **Credit notes** are only issued against invoices that are fully reflected in 2B with the correct GSTIN and amount, so the original credit was eligible. A credit note always reduces `eligible` (negative amounts), whether or not it appears in 2B (conservative). Payments to a supplier are net of credit notes, and credit notes count as settlement for the 180-day test.
6. **One payment per invoice** (full, partial, or none). Lump-sum payments across invoices are not simulated. Payments made after `as_of_date` do not appear in the bank statement.
7. **IMS (Invoice Management System, from Oct 2024)** is not modelled: every supplier-filed document is treated as deemed-accepted into 2B. `itcavl` is always `"Y"` and `rsn` empty (no POS-based ineligibility; place of supply is always the buyer's state).
8. **s.16(4) time limit** (30 Nov following the financial year) is not applied; `as_of_date` is at most 230 days after the period end, i.e. no later than 16 Nov after the financial year, so no simulated claim reaches it.
9. **Blocked-credit facts are given, not inferred.** s.17(5) depends on use (e.g. a car used for passenger transport business would be eligible). The simulated buyer is a generic manufacturer/trader, every catalog item tagged as blocked is blocked, and its description states the use ("staff use", "director residence", "Diwali gifts to dealers").
10. **Amount tolerance** for flags and capping is Rs 1 (rounding noise). Rewards use the same Rs 1 tolerance for ITC.
11. **RCM suppliers are registered** (GTA, advocate firm, security agency), so RCM documents can appear in 2B with `rev = "Y"`. RCM from unregistered persons (s.9(4)) is not simulated.
12. **Register data-entry errors** (amount transposition, GSTIN typo, invoice-number typo, duplicate voucher) never change ITC: credit follows the supplier's invoice and 2B, not the buyer's books.

## Rate regimes (date-effective rate table)

Simulated return periods default to April 2024 through September 2026 (`--period-from` / `--period-to` on the CLI).
Every line's rate and cess come from `catalog.rate_on(product, invoice_date)`:

- **Before 22 Sep 2025:** the 2017 schedule as amended (0/5/12/18/28 plus compensation cess).
- **From 22 Sep 2025 (GST 2.0):** 5% / 18% / 40% slabs (plus nil and exempt items), with compensation cess Nil on everything except tobacco, which the catalog does not carry.
- **Supply date rule (s.14 CGST Act):** supply, invoice and payment dates fall on the same side of the change, except that payment can come later. A supply invoiced before 22 Sep 2025 therefore keeps the old rate, even when GSTR-2B, payment or the reconciliation fall after the cutover (s.14(a)(ii)).
- **Credit notes:** a credit note reduces the original supply (s.34), so it carries the original invoice's rate and cess even when it is issued after the cutover.
- **Periods that straddle the cutover:** a supplier only offers products with a known rate on both sides, and lines dated 1-21 Sep 2025 and 22-30 Sep 2025 in the same case use different rates.
- **Unverified post-cutover rates:** a product with no verified post-cutover rate (`post_rate=None`) is not generated on or after the cutover. Every product currently in the catalog was verified, so none is excluded.

Primary sources (gazette texts read for this table):

| Ref | Notification | Used for |
| --- | --- | --- |
| N9 | 9/2025-Central Tax (Rate), 17 Sep 2025, G.S.R. 641(E), in force 22 Sep 2025 (Schedule I 2.5%+2.5%, II 9%+9%, III 20%+20%) | goods rates |
| N9c | Corrigendum to 9/2025-CT(R), G.S.R. 676(E), 18 Sep 2025 | relabels sub-items on one page only; touches no catalog heading |
| N10 | 10/2025-Central Tax (Rate), 17 Sep 2025 (exemptions; supersedes 2/2017-CT(R)) | nil-rated goods |
| N15 | 15/2025-Central Tax (Rate), 17 Sep 2025 (amends 11/2017-CT(R), services) | services rates |
| CC2 | 2/2025-Compensation Cess (Rate), 17 Sep 2025, G.S.R. 659(E), in force 22 Sep 2025 (amends 1/2017-CC(R)) | cess Nil |

Post-cutover catalog rates and where each one comes from:

| HSN/SAC | Item | Pre | Post | Source |
| --- | --- | --- | --- | --- |
| 8471 | laptop | 18 | 18 | N9 Sch II S.No.456 |
| 8443 | printer | 18 | 18 | N9 Sch II S.No.430 |
| 9403 | office furniture | 18 | 18 | N9 Sch II S.No.612 |
| 7208 | flat-rolled steel | 18 | 18 | N9 Sch II S.No.267 |
| 2523 | cement | 28 | 18 | N9 Sch II S.No.9 |
| 8415 | air conditioner | 28 | 18 | N9 Sch II S.No.404 |
| 4011 | truck tyre | 28 | 18 | N9 Sch II S.No.137 |
| 3208 | paint | 18 | 18 | N9 Sch II S.No.50 |
| 8481 | valve | 18 | 18 | N9 Sch II S.No.466 |
| 8544 | insulated cable | 18 | 18 | N9 Sch II S.No.516 |
| 3402 | detergent | 18 | 18 | N9 Sch II S.No.67 |
| 2710 | lubricating oil | 18 | 18 | N9 Sch II S.No.29 |
| 1507 | soyabean oil | 5 | 5 | N9 Sch I S.No.84 |
| 1701 | sugar | 5 | 5 | N9 Sch I S.No.105 |
| 6109 | T-shirt up to Rs 2500/piece | 5 | 5 | N9 Sch I S.No.388 |
| 3004 | medicaments | 12 | 5 | N9 Sch I S.No.234 |
| 4901 | printed books | 0 | 0 | N10 S.No.132 |
| 0713 | pulses, not pre-packaged | 0 | 0 | N10 S.No.39 |
| 8703 | SUV over 4000 mm / 1500 cc | 28 + 22 cess | 40 + Nil | N9 Sch III S.No.5; CC2 (S.No.52, 52A, 52B to Nil) |
| 2202 | aerated water with added sugar | 28 + 12 cess | 40 + Nil | N9 Sch III S.No.1; CC2 (S.No.2 to Nil) |
| 8528 | television | 28 | 18 | N9 Sch II S.No.500 |
| 9102 | wrist watch | 18 | 18 | N9 Sch II S.No.584 |
| 996311 | hotel up to Rs 7500/day | 12 | 5 | N15 S.No.7(i) (supplier forgoes ITC; the recipient's credit is not restricted by that condition) |
| 999723 | fitness centre (group 99972) | 18 | 5 | N15 S.No.35(i) |
| 996791 | GTA, reverse charge | 5 | 5 | N15 S.No.9(iii): only the forward-charge option (b) moved 12 to 18 |
| 996812 | courier | 18 | 18 | N15 S.No.9(ii) |
| 995414 | works contract (building) | 18 | 18 | N15 S.No.3: only items (vii), (viii), (x) amended |
| 998313, 997212, 998412, 996425, 998719, 998211, 998525, 998714, 996331 | IT, rent, telecom, economy air, AMC, legal (RCM), security (RCM), car repair, restaurant | unchanged | unchanged | not amended by N15 (verified by absence) |

**Not verified:**
- The pre-cutover rates (domain knowledge, not re-read from the 2017 notifications as amended).
- Whether any rate notification after 19/2025-CT(R) (31 Dec 2025, tobacco only, in force 1 Feb 2026) changes a catalog item before Sep 2026. No such notification was found.
- The cess S.No.52A/52B content. All 8703 cess entries from S.No.47 onward are set to Nil by CC2, so the outcome does not depend on it.

## GSTR-2B field names

`gstr2b` follows the `data` object of the GSTN GSTR-2B download (`gstin`, `rtnprd`, `version`, `gendt`, `docdata.b2b[].{ctin, trdnm, supfildt, supprd, inv[].{inum, typ, dt, val, pos, rev, itcavl, rsn, diffprcnt, srctyp, irn, irngendate, items[].{num, rt, txval, igst, cgst, sgst, cess}}}`, and `docdata.cdnr[].nt[]` with `ntnum`, `typ`, `suptyp`).
Key names and formats (DD-MM-YYYY dates, MMYYYY periods, Y/N flags) were checked against a published sample response for the GSTR-2B API.
Not modelled: `itcsumm`, `cpsumm`, `chksum`, and the other sections (`b2ba`, `cdnra`, `isd`, `impg`, `impgsez`).

## Catalog caveats

Post-cutover rates are checked against the notifications above; pre-cutover rates are from domain knowledge.
Goods use 4-digit HSN (real B2B invoices of taxpayers above Rs 5 crore turnover must show 6 digits).
The 6-digit SACs for security services (998525), building works contract (995414), fitness membership (999723) and telecom (998412) are plausible but unverified; they only need to be internally consistent for training.
