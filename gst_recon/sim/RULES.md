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
2. Blocked lines: tax on lines whose use falls in s.17(5) goes to `blocked`, regardless of 2B or payment.
   The outcome is a function of the line's category, its purpose and the buyer profile (`rules.line_block_reason`), all visible to the model (see "Buyer profile and s.17(5) exceptions"):
   - personal consumption: s.17(5)(g) -> `BLOCKED_PERSONAL_USE`
   - gifts: s.17(5)(h) -> `BLOCKED_GIFT`
   - goods or services for construction of the buyer's own immovable property: s.17(5)(d) (and (c) for works contracts) -> `BLOCKED_WORKS_CONTRACT`
   - motor vehicles for transport of persons (seating up to 13) and their servicing/repair: s.17(5)(a), (ab), unless an exception applies -> `BLOCKED_MOTOR_VEHICLE`
   - food and beverages: s.17(5)(b)(i), unless an exception applies -> `BLOCKED_FOOD_BEVERAGE`
   - membership of a club, health and fitness centre: s.17(5)(b)(ii) -> `BLOCKED_CLUB_MEMBERSHIP`
   - works contract for construction of immovable property (not plant and machinery): s.17(5)(c), unless an exception applies -> `BLOCKED_WORKS_CONTRACT`
3. Reverse charge: the remaining tax is `eligible` with `RCM_ELIGIBLE`. It does not depend on GSTR-2B (the recipient itself pays the tax and reports it in GSTR-3B table 4(A)(3)) or on paying the supplier (r.37(1) excludes RCM supplies).
4. Otherwise the remaining tax is tested against GSTR-2B (s.16(2)(aa), r.36(4)):
   - not in any 2B -> all `deferred`, `DEFERRED_NOT_IN_2B`;
   - only in a later period's 2B -> all `deferred`, `DEFERRED_PERIOD_MISMATCH` (claimable in that period);
   - under a different supplier GSTIN -> all `deferred`, `DEFERRED_GSTIN_MISMATCH` (not reflected against this supplier until amended);
   - per head, if 2B shows less than the invoice by more than Rs 1, the shortfall is `deferred` (`DEFERRED_AMOUNT_MISMATCH`); if 2B shows more, credit is still capped at the invoice (s.16(2)(a)).
5. 180-day rule (s.16(2) second and third provisos, r.37): if `unpaid_180d`, the eligible amount times `outstanding / invoice total` moves from `eligible` to `deferred` with `DEFERRED_UNPAID_180D`.
6. `ELIGIBLE` (or `RCM_ELIGIBLE`) is added when any eligible amount is non-zero, or when no other reason applies (e.g. nil-rated supplies). Reasons are emitted in enum order.

`itc_totals` is the per-bucket, per-head sum over all documents.

## Buyer profile and s.17(5) exceptions

Each case has a buyer profile (`inputs.buyer_profile`: kind, a free-text company header, employee count), rendered as the company header.
The same item is eligible or blocked depending on that context:

| Item | Blocked by | Eligible when (simulated) | Authority |
| --- | --- | --- | --- |
| car / SUV (8703, seating up to 13) | s.17(5)(a) | buyer is a car dealer (further supply), a passenger transport operator (transport of passengers) or a driving school (training) | s.17(5)(a)(A), (B), (C) |
| car servicing / repair (998714) | s.17(5)(ab) | the vehicle is used for an (a)(A)-(C) purpose (same buyers as above) | s.17(5)(ab), first proviso (i) |
| food and beverages (restaurant meals, tea, coffee, biscuits, juice, drinks, rice, oil, sugar, pulses) | s.17(5)(b)(i) | buyer is a hotel or caterer (outward supply of the same category, or an element of its composite supply) | s.17(5)(b)(i), proviso |
| food for a factory canteen | s.17(5)(b)(i) | buyer is a manufacturer with more than 250 employees and the remark says canteen; the Factories Act 1948 s.46 makes a canteen obligatory above 250 workers | s.17(5)(b), second proviso ("obligatory for an employer ... under any law"); Circular 172/04/2022-GST: that proviso covers the whole of clause (b) |
| club / gym membership | s.17(5)(b)(ii) | never: (b)(ii) has no same-category proviso, and no law obliges an employer to provide club or gym membership, so the employer-obligation proviso is never met | s.17(5)(b)(ii); second proviso to (b) |
| works contract on a building (995414, 995468, 995461) | s.17(5)(c) | buyer is a construction contractor (input service for further supply of works contract service) | s.17(5)(c), "except where it is an input service for further supply of works contract service" |
| cement, TMT, tiles, sanitaryware, putty, aluminium | s.17(5)(d) | buyer is a construction contractor (inputs for its outward works contract); for anyone else they are for its own building | s.17(5)(d) |
| goods vehicle (8704) | not blocked | always eligible (clause (a) covers vehicles for transport of persons only) | s.17(5)(a) |

Hard negatives: a canteen remark from a manufacturer with 250 or fewer employees stays blocked; a staff-party remark on food stays blocked for every buyer; gym membership stays blocked even as staff welfare; household goods are blocked only when the remark says residence or personal use.
Hard positives: an SUV for a cab operator, car servicing for a driving school, rice for a caterer, a building works contract for a contractor.

Conservative simplifications:
- Every buyer's outward supplies are taxable under rate options that allow ITC (e.g. a hotel's restaurant is assumed to be in a specified premises; a caterer's outward supply is assumed taxable with ITC). Otherwise s.17(2) apportionment would apply, which is not modelled.
- Canteen credit assumes the employer bears the full cost (no recovery from employees), so no proportional credit (Circular 172/04/2022 para 6) is needed.
- Car servicing for a car dealer is treated as servicing of vehicles held for further supply ((ab) proviso (i)).
- Who buys what is restricted so the remaining cases are unambiguous: car parts are bought only by dealers, transport operators, driving schools and auto workshops; gym equipment only by gym operators; auto workshops never buy car servicing; hotels and auto workshops never buy passenger vehicles.
- Works contract concepts are works on buildings (immovable property), never on plant and machinery.

## Splits (train / test_iid / test_ood)

`generate_case(..., split=)` and `--split` on the CLI. Assignment is deterministic (sha256 of a fixed key), so it never changes between runs (`sim/splits.py`):
- **Concepts:** about a quarter of each family with 3 or more concepts (20 of 84) appear only in test_ood.
- **Surface forms:** each concept has 8 core phrases; each core expands into variants (UPPER, abbreviation or qualifier, one typo, truncation or trade tag), giving at least 32 distinct case-folded forms per concept. A quarter of each in-distribution concept's cores (with all their variants) are held out for the test splits, so near-duplicates never leak.
- **Profiles:** driving school, caterer and auto workshop appear only in test_ood (60% of its cases).
- **Vocabulary:** a held-out quarter of states, about 30% of supplier-name prefixes and cores, and a quarter of invoice-number formats appear only in test_ood. Profile headers, slot fillers and remarks are split by core like descriptions.
- test_iid = train concepts, profiles, states and vocabulary, held-out phrasing. test_ood = held-out concepts preferred (70% when the family has one), held-out profiles, states, vocabulary and phrasing.

`tests/test_splits.py` asserts that no description, concept, remark, header, profile, state or name token of a test split occurs in train.

## Anomalies and the shortcut audit

Each document draws its 2B, register and payment anomaly independently, with a probability that depends only on the difficulty knob, never on the supplier, concept, wording or state.
Documents are shuffled before doc ids are assigned, so position carries no information.
`python -m gst_recon.sim.audit` reports base rates per flag and reason by difficulty, trivial baselines scored with the reward functions, and the largest feature-to-flag deviation (controlling for difficulty) for supplier state, intra-state, invoice-number format, supplier-name tokens, position, document type, RCM, line count, concept, category, remark presence and buyer profile.
`unpaid_180d` is tested on forward-charge invoices only, because r.37 itself excludes credit notes and RCM supplies.
`tests/test_audit.py` asserts there are no spurious pairs (deviation above 3 points with z above 5).

## Simplifications (deliberate, documented)

1. **Two rate regimes, chosen by supply date.** See "Rate regimes" below. Supply date = invoice date, payment later, no advances, so s.14 always resolves to the rate on the invoice date.
2. **"Deferred" covers both "not yet claimable" and "reverse now, re-avail later".** The 180-day rule strictly requires reversing credit already availed (with interest). We do not model prior-period claims, so the unpaid share is reported as `deferred`. No interest is computed.
3. **Recon timing.** `as_of_date` is either 12-25 days after the period end (normal GSTR-3B timing) or 190-230 days after (a late/annual review, which is when the 180-day rule can bite). The next period's GSTR-2B is provided only if it was generated (14th of the month after next) by `as_of_date`; a late-filed invoice whose 2B is not yet available is therefore just `missing_in_2b`.
4. **Later 2B is partial.** The next period's 2B contains only the late-filed documents of this case, not the supplier's genuine next-month invoices.
5. **Credit notes** are only issued against invoices that are fully reflected in 2B with the correct GSTIN and amount, so the original credit was eligible. A credit note always reduces `eligible` (negative amounts), whether or not it appears in 2B (conservative). Payments to a supplier are net of credit notes, and credit notes count as settlement for the 180-day test.
6. **One payment per invoice** (full, partial, or none). Lump-sum payments across invoices are not simulated. Payments made after `as_of_date` do not appear in the bank statement.
7. **IMS (Invoice Management System, from Oct 2024)** is not modelled: every supplier-filed document is treated as deemed-accepted into 2B. `itcavl` is always `"Y"` and `rsn` empty (no POS-based ineligibility; place of supply is always the buyer's state).
8. **s.16(4) time limit** (30 Nov following the financial year) is not applied; `as_of_date` is at most 230 days after the period end, i.e. no later than 16 Nov after the financial year, so no simulated claim reaches it.
9. **Blocked-credit facts are visible, never hidden.** s.17(5) depends on use. The use of every line is either implied by the buyer profile header shown to the model (a car dealer buying cars, a hotel buying food) or stated in the invoice remarks (canteen, staff welfare, gift, residence, own building). Descriptions never carry use-revealing words; a line with no such signal is ordinary business use. One purpose per invoice.
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

Catalog concepts (`sim/concepts.py`) and the source of each post-cutover rate.
"N9 II-267" means N9 Schedule II S.No.267; "N15 n/a" means the SAC entry was not amended by N15 (verified by absence), so the rate is unchanged; "CC S.No.x Nil" means CC2 set that cess entry to Nil.

| HSN/SAC | Concept | Family | Pre | Post | Source |
| --- | --- | --- | --- | --- | --- |
| 7208 | hr_steel_coil | industrial | 18 | 18 | N9 II-267 |
| 7318 | fasteners | industrial | 18 | 18 | N9 II-296 |
| 8482 | bearings | industrial | 18 | 18 | N9 II-467 |
| 8481 | valves (test_ood only) | industrial | 18 | 18 | N9 II-466 |
| 8544 | cables | industrial | 18 | 18 | N9 II-516 |
| 3917 | plastic_pipes | industrial | 18 | 18 | N9 II-118 |
| 3923 | plastic_packing | industrial | 18 | 18 | N9 II-124 |
| 4819 | cartons | industrial | 18 | 5 | N9 I-322 |
| 3208 | paint (test_ood only) | industrial | 18 | 18 | N9 II-50 |
| 2710 | lubricants | industrial | 18 | 18 | N9 II-29 |
| 3402 | detergent (test_ood only) | industrial | 18 | 18 | N9 II-67 |
| 8501 | electric_motors (test_ood only) | industrial | 18 | 18 | N9 II-474 |
| 8536 | switchgear | industrial | 18 | 18 | N9 II-508 |
| 8504 | ups_transformers | industrial | 18 | 18 | N9 II-477 |
| 8414 | compressors_fans | industrial | 18 | 18 | N9 II-401 |
| 4011 | truck_tyres | industrial | 28 | 18 | N9 II-137 |
| 8704 | goods_vehicle | goods_vehicle | 28 | 18 | N9 II-540 |
| 2523 | cement | construction | 28 | 18 | N9 II-9 |
| 7214 | tmt_bars | construction | 18 | 18 | N9 II-268 |
| 6907 | tiles | construction | 18 | 18 | N9 II-238 |
| 6910 | sanitaryware | construction | 18 | 18 | N9 II-240 |
| 3214 | putty_sealants (test_ood only) | construction | 18 | 18 | N9 II-56 |
| 7610 | aluminium_structures (test_ood only) | construction | 18 | 18 | N9 II-339 |
| 8471 | laptop | office | 18 | 18 | N9 II-456 |
| 8473 | computer_parts (test_ood only) | office | 18 | 18 | N9 II-458 |
| 8443 | printer | office | 18 | 18 | N9 II-430 |
| 9403 | office_furniture | office | 18 | 18 | N9 II-612 |
| 8517 | phones_network (test_ood only) | office | 18 | 18 | N9 II-490 |
| 8415 | air_conditioner | office | 28 | 18 | N9 II-404 |
| 9608 | pens_markers | office | 18 | 18 | N9 II-626 |
| 4818 | tissue_paper | office | 18 | 18 | N9 II-184 |
| 8528 | led_tv | household | 28 | 18 | N9 II-500 |
| 8418 | refrigerator | household | 18 | 18 | N9 II-407 |
| 8450 | washing_machine (test_ood only) | household | 18 | 18 | N9 II-437 |
| 8516 | water_heater | household | 18 | 18 | N9 II-489 |
| 8509 | mixer_grinder | household | 18 | 18 | N9 II-482 |
| 9102 | watches | giftable | 18 | 18 | N9 II-584 |
| 7113 | jewellery | giftable | 3 | 3 | N9 IV-10 |
| 3303 | perfume | giftable | 18 | 18 | N9 II-60 |
| 4202 | luggage (test_ood only) | giftable | 18 | 18 | N9 II-145 |
| 3401 | toilet_soap (test_ood only) | toiletries | 18 | 5 | N9 I-251 |
| 3305 | shampoo_hairoil | toiletries | 18 | 5 | N9 I-245 |
| 3306 | toothpaste | toiletries | 18 | 5 | N9 I-246 |
| 3004 | medicaments (test_ood only) | misc | 12 | 5 | N9 I-234 |
| 4901 | books | misc | 0 | 0 | N10-132 |
| 6109 | uniform_tshirts | misc | 5 | 5 | N9 I-388 |
| 9506 | gym_equipment | gym_equipment | 18 | 18 | N9 II-619 |
| 8708 | car_parts | car_parts | 28 | 18 | N9 II-544 |
| 998313 | it_consulting | services | 18 | 18 | N15 n/a (S.No.21(ii)) |
| 998315 | cloud_hosting (test_ood only) | services | 18 | 18 | N15 n/a |
| 997331 | software_licence | services | 18 | 18 | N15 n/a |
| 998361 | advertising (test_ood only) | services | 18 | 18 | N15 n/a |
| 998221 | audit_accounting | services | 18 | 18 | N15 n/a |
| 998513 | manpower_supply | services | 18 | 18 | N15 n/a |
| 998533 | housekeeping | services | 18 | 18 | N15 n/a |
| 999293 | training | services | 18 | 18 | N15 n/a |
| 998596 | event_management | services | 18 | 18 | N15 n/a |
| 998719 | amc_repairs (test_ood only) | services | 18 | 18 | N15 n/a |
| 997212 | office_rent | services | 18 | 18 | N15 n/a |
| 998412 | telecom | services | 18 | 18 | N15 n/a |
| 996812 | courier | services | 18 | 18 | N15 S.No.9(ii) |
| 996311 | hotel_stay | travel | 12 | 5 | N15 S.No.7(i) |
| 996425 | air_travel | travel | 5 | 5 | N15 n/a |
| 996791 | gta_freight (test_ood only) | rcm | 5 | 5 | N15 S.No.9(iii): RCM option unchanged |
| 998211 | legal_fees | rcm | 18 | 18 | N15 n/a |
| 998525 | security_services | rcm | 18 | 18 | N15 n/a |
| 8703 | small_car (test_ood only) | motor_vehicle | 28 + 1 cess | 18 | N9 II-534; CC S.No.50 Nil |
| 8703 | suv | motor_vehicle | 28 + 22 cess | 40 | N9 III-5; CC S.No.52B Nil |
| 998714 | car_servicing | motor_vehicle | 18 | 18 | N15 n/a |
| 996331 | restaurant_meals | food | 5 | 5 | N15 n/a (S.No.7(ii)) |
| 0902 | tea | food | 5 | 5 | N9 I-34 |
| 0901 | coffee | food | 5 | 5 | N9 I-33 |
| 1905 | biscuits | food | 18 | 5 | N9 I-123 |
| 2009 | fruit_juice | food | 12 | 5 | N9 I-133 |
| 2202 | aerated_drinks | food | 28 + 12 cess | 40 | N9 III-1; CC S.No.2 Nil |
| 1006 | packaged_rice (test_ood only) | food | 5 | 5 | N9 I-48 |
| 1507 | edible_oil | food | 5 | 5 | N9 I-84 |
| 1701 | sugar | food | 5 | 5 | N9 I-105 |
| 0713 | pulses_loose (test_ood only) | food | 0 | 0 | N10-39 |
| 999723 | gym_membership | club | 18 | 5 | N15 S.No.35(i) |
| 999599 | club_membership | club | 18 | 18 | N15 n/a |
| 995414 | wc_building | works_contract | 18 | 18 | N15 S.No.3(xii) n/a |
| 995468 | wc_interior | works_contract | 18 | 18 | N15 S.No.3(xii) n/a |
| 995461 | wc_electrical (test_ood only) | works_contract | 18 | 18 | N15 S.No.3(xii) n/a |

Excluded for want of a verified post-cutover rate or a clean HSN mapping: buses (8702, cess), paper and stationery (4802, 4820), LED lamps (9405, 8539), pumps (8413), rent-a-cab, outdoor catering, motor insurance, packaged water, milk products (0402), nuts (0802), sugar confectionery (1704).

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
The 6-digit SACs of the services concepts (e.g. 998525 security, 995414/995468/995461 works contracts, 999723 fitness, 999599 club, 998412 telecom) are plausible but unverified at 6 digits; the rate depends only on the verified heading or group, and they only need to be internally consistent for training.
