# semireal: real documents, simulated books (EVAL ONLY)

`semireal` turns labelled real purchase documents into full reconciliation cases.
The documents are real: their text goes into `prompt.txt` verbatim and their label is the truth extraction.
The books around them are simulated: the purchase register, GSTR-2B and bank statement come from the simulator's own functions (`sim.world._register`, `sim.twob.build_gstr2b`, `sim.bank.plan_payments`, `sim.bank.build_bank_statement`) with the simulator's own anomaly draws (`sim.world._anomalies`).
The target is `sim.rules.reconcile` on the truth Case, the same code path as every simulated case, so the scorer and `python -m gst_recon.eval run --mode hybrid` work unchanged.
It is evaluation data only and must never be used for training (`mark_eval_dir` writes `DO_NOT_TRAIN` into the output root).
The real documents, labels and built cases are client data and stay out of git; this file and the code are generic.

## How to build

    python -m gst_recon.semireal build --labels <labels dir> --out <out dir> [--seed 0] [--sim-seeds 0,1,2,3,4] [--max-docs 25]

Input layout and output layout are in the docstring of `gst_recon/semireal/__main__.py`.
Output: `<out>/{clean,sim}/<case_id>/{prompt.txt,target.json,meta.json}`, truth Case JSON under `<out>/truth/<level>/<case_id>.json` (pass `--truth-dir <out>/truth` to the eval), `<out>/manifest.json` and `<out>/oracle.json`.

## Design

- One buyer-month is one case: documents are grouped by the month of their labelled invoice date, and a month above `--max-docs` documents is split into near-equal chunks.
- Document order within a case is shuffled with a seeded rng, as the simulator does.
- The reconciliation date follows the simulator's medium knobs (half of the cases are reviewed more than 180 days after the period, which enables the 180-day rule).
- The document order and the reconciliation date do not depend on the noise level, so a `clean` case and its `sim` twin differ only in the planted book discrepancies.
- Two noise levels:
  - `clean`: no planted book discrepancies (anomaly rate 0); every invoice is booked once, filed in the period's 2B under its GSTIN with its amounts, and paid in full 5 to 60 days after its date (a payment after the reconciliation date is not in the statement, as in the simulator).
  - `sim`: the simulator's default per-document rate (`DIFFICULTY["medium"].p_side` = 0.12 per side): not filed, filed against another buyer, filed under the supplier's other-state GSTIN, filed with a wrong amount, filed in the next period; register duplicate, amount typo, GSTIN typo, invoice-number typo; unpaid, partly paid, paid late (payment anomalies only in late reviews, as in the simulator).
- Replicas: `clean` is built once (`--seed`); `sim` is built once per `--sim-seeds` seed, each a fresh draw of document order, review date and book discrepancies over the same documents.
  Case ids carry the seed (`semireal-sim-s<seed>-YYYYMM`, `semireal-clean-YYYYMM`) so the truth lookup stays unique, and `meta.json` `difficulty` is `sim-s<seed>`, so the eval's difficulty breakdown is the per-replica breakdown.
  The `sim` replica whose seed equals `--seed` is the `clean` set's twin (same order and review date).
- Register rendering: the hybrid parser reads the fixed-width Tally text style by splitting on runs of spaces, so an empty GSTIN cell (unregistered supplier) would shift the row; such a register is redrawn until the CSV style comes up (`meta.register.redrawn_for_empty_gstin`).
- Not planted: the simulator's synthetic credit notes (they would need a simulator-rendered document, which is not real) and its buyer-profile purposes (the labels decide category and purpose).
- Every planted discrepancy is listed per case in `meta.json` `anomalies` and in `manifest.json` (`planted`), in the simulator's `D03:not_filed` form.
- Structural facts that are not planted discrepancies are listed too: `unregistered_supplier_not_in_2b` and `credit_note_of:Dnn`.

## Documents that are left out, and why

A document gets books only when its true identity (supplier GSTIN, invoice number, invoice date) is known, because the register and GSTR-2B must carry the true values.

- An identity field the label marks unreadable ("" in the truth) excludes the document.
- A printed GSTIN that fails the mod-36 check digit excludes the document: no GSTR-2B can carry it and the true registration is unknown.
- A GSTIN the page does not print at all (an unregistered supplier; the label's `unreadable` note says "not printed") is known to be "": the document is kept, booked without a GSTIN, and never appears in any GSTR-2B (structural, also at the `clean` level).
- An unparseable invoice date excludes the document.
- Low or medium labelling confidence does not exclude a document: the label is the best reading, and `meta.json` carries each document's confidence so results can be split by it.

## Oracle check

`gst_recon.semireal.oracle.run_oracle` feeds the true per-document records (`hybrid.sft.truth_records`, the hybrid worker's oracle) through the real hybrid path (`eval.runner.run_eval` + `hybrid.run.make_generator`: reply parsing, repair, identity fill, linker, rules engine) and lists every document whose extraction, match row or ITC differs from the target, with the reconciler's trace.
A miss means the reconciler and the truth disagree on correct input, so it must be explained before the set is used.
Known cause on real documents: `hybrid.repair` sets `total` to taxable value plus tax, so a real invoice whose payable total also carries a non-taxable pass-through (for example a travel agent's invoice that includes the airline fare) loses its extracted total and therefore its payment link, and the register total then reads as an amount mismatch.
In a late review the lost payment link cascades into ITC: the reconciler sees the invoice unpaid after 180 days and defers its credit (`DEFERRED_UNPAID_180D`).

## What this set measures

- Real document reading: OCR of real scans and PDF text layers, real layouts, real supplier variety and the real category mix, feeding the full reconciliation.

## What it does not measure

- Real book messiness: clerk register conventions, real 2B filing errors and amendments, real UPI narrations, lump and netted payments.
  The books follow the simulator's distributions, which the reconciler was developed on.
- Label noise: the labels may be model-drafted rather than human-verified.
  A wrong label propagates into books that agree with it, so a model that reads the page correctly can be scored wrong, and one that repeats the label's mistake is scored right.
- Excluded documents (unreadable or invalid identity) are the hardest pages; leaving them out flatters document reading.
- The documents' category and purpose mix is whatever the real buyer bought; if no line is s.17(5)-blocked, the planted book discrepancies are the only source of non-eligible ITC, and the `clean` level has none at all.

Report each noise level separately, and never merge either into a real-world claim about books.
