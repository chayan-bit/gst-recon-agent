# gst-recon spec

The one-page spec the project started from.
The README has the current results; this file says what we set out to build and the rules we held ourselves to.

Syntax Error 2026 (SDSLabs, IIT Roorkee), Local LLM track, problem statement 6: reasoning with verifiable answers (financial calculations).
Deadline: Sunday 2026-10-25 09:00 IST. Solo entry.

## Product
A small open model (about 4B, LoRA) served on SGLang that does monthly GST input tax credit (ITC) reconciliation for one buyer company.
Inputs per case: OCR text of messy purchase invoices, the buyer's purchase register (Tally-style export), the GSTR-2B JSON for the period, and a bank statement.
Outputs per case (strict JSON, enforced by SGLang grammar-constrained decoding):
1. Extraction: one record per invoice (supplier GSTIN, invoice no, date, place of supply, line items with HSN, taxable value, rate, CGST/SGST/IGST, total).
2. Matching: each invoice matched to register row, 2B row and payment, or flagged (missing_in_2b, gstin_mismatch, amount_mismatch, duplicate, period_mismatch, unpaid_180d).
3. ITC: eligible / blocked / deferred amount per invoice with a rule reason code (Sec 16(2) conditions, Sec 17(5) blocked credits, RCM, 180-day rule, credit notes).

## Hard rules
- Ground truth first, render second: a deterministic Python world simulator produces the true state; documents are rendered and degraded from it. Never derive ground truth from generated text.
- Every reward is checked by code: schema validity, per-field match, accounting identities, match-table correctness, exact ITC.
- SGLang is the only inference engine (teacher generation, GRPO rollouts, serving, evals).
- Lexsi Labs toolkits: CuratorKIT (data curation), AlignTune (SFT and GRPO), AuditKIT (evals). Each runs in its own virtualenv; they hand off through files.
- Bulk training text comes from a local open teacher on SGLang, not from a closed API.
- No real client data anywhere in this repo.

## Compute
- Training, teacher generation, rendering and evals ran on rented or shared Linux GPU hosts: one H100 NVL (94 GB, shared, used within a memory budget), an RTX A6000 48 GB and an RTX 5070 Ti 16 GB.
- The shipped 4B model serves on a single 16 GB GPU.
- The development laptop was used for editing and light checks only.

## Layout
- `gst_recon/schema.py` - pydantic models + JSON Schema export (single source of truth).
- `gst_recon/sim/` - world simulator and GST rules engine (ground truth).
- `gst_recon/render/` - document rendering, degradation, OCR.
- `gst_recon/rewards/` - verifiable reward functions (shared by GRPO and evals).
- `infra/` - host setup and SGLang launch scripts; serving measurements are in `reports/serving.md`.
- `data/`, `runs/` - gitignored.
- `gst_recon/hybrid/`, `gst_recon/eval/`, `gst_recon/train/`, `realworld/`, `demo/` - added later; see the README repo map.
