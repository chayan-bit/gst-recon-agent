# gst-recon

A 4B-parameter language model that runs on one 16 GB GPU and reconciles Indian GST input tax credit (ITC) from messy invoices.
It is built for accountants and finance teams who cannot send purchase invoices, bank statements and supplier lists to a cloud API.
Made solo for Syntax Error 2026 (Local LLM track).

Every month a company has to decide how much GST it can claim back.
That means matching each purchase invoice to its own books, to the government's GSTR-2B statement and to a bank payment, then deciding per invoice whether the credit is eligible, blocked or deferred, with the legal reason.
gst-recon does this with a small open model served on SGLang, a LoRA adapter trained with SFT and then GRPO, and ordinary code for everything that must be exact.

Repository: https://github.com/chayan-bit/gst-recon-agent

## Results

The test is the whole job on real documents: 54 cases built from real supplier documents, with simulated books (purchase register, GSTR-2B and bank statement).
Every reader below gets the same document text (no images) and feeds the same code reconciler.

| Real-document set (54 cases) | ITC exact | Match | Composite | Invented IDs |
|---|---|---|---|---|
| Claude Haiku 5.5 (minimum thinking, can't be turned off) | 84.9 | 88.4 | 86.5 | 8.4% |
| GPT-6 luna (reasoning off) | 70.6 | 82.5 | 77.9 | 15.4% |
| Claude Haiku 4.5 (thinking off) | 68.2 | 82.2 | 77.4 | 16.6% |
| pd3g287 (shipped, our local Qwen3-4B + LoRA) | 61.1 | 71.5 | 72.9 | 9.7% |

- **ITC exact**: the share of invoices whose eligible, blocked and deferred amounts (IGST, CGST, SGST and cess) are all within Rs 1 of the truth.
- **Match**: per invoice, whether it found the right purchase-register entry, GSTR-2B row and bank payment and raised the right flags.
- **Composite**: one overall score (ITC per invoice 20%, matching 20%, field extraction 25%, total ITC 10%, arithmetic 10%, valid output 10%, ITC reasons 5%).
- **Invented IDs**: the share of GSTIN, invoice-number and date fields (3 per document) where the model wrote a value that differs from the truth and the page does not show the true value (lower is better).

What to take from it:

- The frontier readers lead on this set: Haiku 5.5 by 13.6 composite points, GPT-6 luna by 5.0 (significant) and Haiku 4.5 by 4.5 (not significant).
- Our case is a 4B model that runs locally on one 16 GB GPU with no document leaving the machine, and it invents fewer identity fields than Haiku 4.5 and luna.
- Our model runs with no test-time compute (Qwen3-4B-Instruct-2507 has no thinking mode, and its output is XGrammar-constrained to start with `{`), and the other readers run at their lowest reasoning setting.
  Haiku 5.5 cannot disable thinking through the Claude Code CLI.
- The 54 labels were drafted by a model and not verified by a human.
- Swapping true values into our model's output shows where it loses: about 86% of its lost ITC exact comes from copying identity fields and amounts off the page, and only about 9% from judgment (blocked-credit category, purpose), so the gap is reading, not reasoning.
  About half of its wrong fields are not in the document text at all, and Haiku 5.5 misses those too.
- Most of the loss is misreading amounts on the page (true amounts alone lift ITC exact from 61.1 to 88.6), which we expect more training, better algorithms and a better harness to improve; the model was trained in a few hours on a hackathon clock.

How the shipped model was built and chosen:

- pd3g287 is a Qwen3-4B-Instruct-2507 LoRA trained on simulator rows with realistic identity formats, then 287 steps of GRPO, run in hybrid mode (it reads one document at a time and deterministic code does the matching, rupee arithmetic and ITC rules).
- We pick models on full reconciliation of real documents, since that is the actual task; simulated dev and test sets were early filters during development, and their numbers are in `reports/`.
- The shipped model sometimes leaves an identity field blank that the page shows (counts in [reports/hybrid.md](reports/hybrid.md)).
- GRPO: the first run (step 75) was neutral and was not shipped; the second run, from the realistic-formats adapter, is the shipped pd3g287.
  The AlignTune SGLang rollout backend we built for GRPO is upstream (PR #32) as infrastructure, not as a headline gain.

Simulated-data results (test and dev), per-field accuracy, the Sonnet comparison and every paired test are in [reports/hybrid.md](reports/hybrid.md), [reports/results.md](reports/results.md), [reports/frontier-hybrid.md](reports/frontier-hybrid.md) and [reports/pipeline.md](reports/pipeline.md).

## Quick start

You need a GPU with about 16 GB and an SGLang install (we ran SGLang 0.5.22 and 0.5.10.post1).
The commands below use the flags from `configs/serve_sft_eval.sh` and `gst_recon/eval/README.md`.

1. Install the repo and fetch the shipped adapter (`grpo-pd3-final` in the Hugging Face repo):

   ```bash
   uv sync --extra eval
   hf download broman23/gst-recon-qwen3-4b-adapters --include "grpo-pd3-final/*" --local-dir .
   ```

2. Serve the base model with the adapter on SGLang.
   The adapter is then addressed as the model `base:perdoc` (and `base` alone is the plain base model).

   ```bash
   python -m sglang.launch_server \
     --model-path Qwen/Qwen3-4B-Instruct-2507 --served-model-name base \
     --enable-lora --lora-paths perdoc=./grpo-pd3-final \
     --max-lora-rank 32 --lora-target-modules all --max-loras-per-batch 2 \
     --host 127.0.0.1 --port 30400 --context-length 16384 --grammar-backend xgrammar
   ```

3. Run the full reconciliation (hybrid mode) on the three bundled example cases and read the scores:

   ```bash
   python -m gst_recon.eval run --mode hybrid --constrained \
     --endpoint http://127.0.0.1:30400/v1 --model base:perdoc \
     --cases examples --out runs/eval/quickstart
   ```

   Without `--truth-dir` the context-accuracy metric falls back to a proxy; the rest is scored against each case's `target.json`.
   Details of every flag and metric are in [gst_recon/eval/README.md](gst_recon/eval/README.md).

4. Or open the demo UI, which streams a case through the server and shows the reconciliation table next to it.
   It also replays saved runs with no GPU at all.

   ```bash
   cd demo && uv sync
   SGLANG_BASE_URL=http://127.0.0.1:30400/v1 uv run uvicorn gst_demo.app:app --port 8765
   # open http://localhost:8765/
   ```

   See [demo/README.md](demo/README.md) for the panels and settings.

Unit tests run in seconds without a GPU: `uv run pytest -q`.

## How it works

1. **Ground truth first.** A deterministic Python world simulator (`gst_recon/sim`) builds a company's month: suppliers, invoices, purchase register, GSTR-2B, bank statement.
   A rules engine computes the correct ITC from that state, with the legal rules written down in [gst_recon/sim/RULES.md](gst_recon/sim/RULES.md).
   Documents are rendered and degraded from the truth afterwards (`gst_recon/render`), so the truth is never something a model wrote.
2. **Messy documents in.** Scans go through Tesseract OCR; WhatsApp and email text goes in as it is.
3. **Hybrid read.** The model reads one document at a time and returns its fields plus two judgments per line (ITC category and purpose).
   SGLang with XGrammar forces the output to match a JSON schema, so it always parses.
4. **Code does the rest.** The reconciler (`gst_recon/hybrid`) matches each document to the register, GSTR-2B and bank, does the rupee arithmetic and applies sections 16(2) and 17(5) and rules 36 and 37.
   The same input always gives the same answer, and every decision has a trace an accountant can check.
5. **Rewards are code.** SFT teaches the format; GRPO then rewards schema validity, flags, reason codes and exact ITC, all checked by `gst_recon/rewards`.
   The same functions score the evals, so a number in a report is the number training optimised.

### Names you will meet in the reports

- **pd3g287**: the shipped adapter (Hugging Face folder `grpo-pd3-final`).
- **v1** (`perdoc-v1`): the earlier per-document adapter, trained on the simulator's original identity formats.
- **semireal**: the 54-case real-document set above (real supplier documents, simulated books).
- **realinv, realinv2**: two eval sets of real invoices, read one document at a time.
- **realworld**: 12 hand-built cases printed through open-source invoice formats.
- **hybrid**: the per-document model plus the code reconciler; **end to end** means one model call for the whole case.

## Repo map

| Path | What is in it |
|---|---|
| `gst_recon/` | The Python package: `sim` (world simulator and rules engine), `render` (documents, degradation, OCR), `rewards` (checkable rewards), `hybrid` (per-document pipeline and reconciler), `eval` (evaluation harness), `train` (data build, SFT and GRPO helpers), `semireal` (real documents with simulated books), `schema.py` (the output schema) |
| `schemas/` | The JSON Schema the model is decoded against |
| `configs/` | SFT and GRPO configs and launch scripts |
| `scripts/` | Eval and analysis scripts (frontier readers, paired comparisons, error attribution) |
| `realworld/` | The 12-case set built from open-source invoice print formats, with provenance and licences |
| `examples/` | Three small rendered cases (prompt, images, ground truth) used by the quick start and the demo |
| `demo/` | The live demo UI and its recorded runs |
| `reports/` | Evaluation reports and serving measurements |
| `pitch/` | Deck outline, judge Q&A and demo script from the submission |
| `infra/` | SGLang launch script, smoke tests and frozen environment lists |
| `notes/` | Write-up of the AlignTune bugs we found |
| `tests/` | Unit tests |

`SPEC.md` is the original one-page spec.

## Upstream contributions

We sent fixes and features back to the toolkits we used.
All 11 pull requests are open and none is merged.

- SGLang [#46287](https://github.com/sgl-project/sglang/pull/46287): skip LoRA release for requests rejected before adapter acquire.
- AlignTune [#32](https://github.com/Lexsi-Labs/aligntune/pull/32): SGLang rollout backend for TRL GRPO.
- AlignTune [#33](https://github.com/Lexsi-Labs/aligntune/pull/33): the unsloth SFT dataset fingerprint pickles the model into host RAM.
- AlignTune [#34](https://github.com/Lexsi-Labs/aligntune/pull/34): config values replaced by factory defaults.
- AlignTune [#35](https://github.com/Lexsi-Labs/aligntune/pull/35): train keys dropped by the YAML parser.
- CuratorKIT [#34](https://github.com/Lexsi-Labs/CuratorKIT/pull/34): carry the gold answer through GRPO rollouts into grpo.jsonl.
- CuratorKIT [#35](https://github.com/Lexsi-Labs/CuratorKIT/pull/35): reject GRPO rollouts whose scoring fails instead of defaulting to 0.5.
- CuratorKIT [#36](https://github.com/Lexsi-Labs/CuratorKIT/pull/36): keep the gold answer out of the GRPO rollout prompt.
- AuditKIT [#9](https://github.com/Lexsi-Labs/AuditKIT/pull/9): centre paired-bootstrap differences on the null so p-values are meaningful.
- AuditKIT [#10](https://github.com/Lexsi-Labs/AuditKIT/pull/10): `RunConfig.failed_as_zero` and failed samples in `summary()`.
- AuditKIT [#11](https://github.com/Lexsi-Labs/AuditKIT/pull/11): `JsonSchemaValid` and `FieldF1` structured-extraction metrics.

## Weights and data

- LoRA adapters for Qwen3-4B-Instruct-2507 (Apache-2.0): https://huggingface.co/broman23/gst-recon-qwen3-4b-adapters
- Simulator-generated training and eval data (Apache-2.0, synthetic only): https://huggingface.co/datasets/broman23/gst-recon-synthetic

The real documents behind the semireal results are client data and are not published; only aggregate numbers are.
Everything in `examples/` and `realworld/` is synthetic.

## License

GPL-3.0-only; see `LICENSE`.
The upstream invoice print formats vendored unchanged in `realworld/formats/vendor/` keep their own licences (GPL-3.0, LGPL-3.0 and MIT, listed in `realworld/PROVENANCE.md`), and the templates ported from them in `realworld/formats/` are derivative works distributed under GPL-3.0.
