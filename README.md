# gst-recon

Local LLM that reconciles Indian GST input tax credit from messy documents. Syntax Error 2026, Local LLM track.

Repository: https://github.com/chayan-bit/gst-recon-agent

## Results

| Real-document set (54 cases) | ITC exact | Match | Composite | Invented IDs |
|---|---|---|---|---|
| Claude Haiku 5.5 (minimum thinking, can't be turned off) | 84.9 | 88.4 | 86.5 | 8.4% |
| GPT-6 luna (reasoning off) | 70.6 | 82.5 | 77.9 | 15.4% |
| Claude Haiku 4.5 (thinking off) | 68.2 | 82.2 | 77.4 | 16.6% |
| pd3g287 (shipped, our local Qwen3-4B + LoRA) | 61.1 | 71.5 | 72.9 | 9.7% |

Every reader feeds the same code reconciler; the 54 cases are real supplier documents with simulated books (purchase register, GSTR-2B and bank), and their labels were drafted by a model and not verified by a human.
Every reader got the same document text (no images), and swapping true values into our model's output shows where it loses: about 86% of its lost ITC exact comes from copying identity fields and amounts off the page, and only about 9% from judgment (blocked-credit category, purpose), so the gap is reading, not reasoning; about half of its wrong fields are not in the document text at all, and Haiku 5.5 misses those too.

ITC exact is the share of invoices whose eligible, blocked and deferred amounts (IGST, CGST, SGST and cess) are all within Rs 1 of the truth; match is, per invoice, whether it found the right purchase-register entry, GSTR-2B row and bank payment and raised the right flags; composite is one overall score (ITC per invoice 20%, matching 20%, field extraction 25%, total ITC 10%, arithmetic 10%, valid output 10%, ITC reasons 5%); invented IDs is the share of GSTIN, invoice-number and date fields (3 per document) where the model wrote a value that differs from the truth and the page does not show the true value (lower is better).
The frontier readers lead on this set: Haiku 5.5 by 13.6 composite points, GPT-6 luna by 5.0 (significant) and Haiku 4.5 by 4.5 (not significant); our case is a 4B model that runs locally on one 16 GB GPU with no document leaving the machine, and it invents fewer identity fields than Haiku 4.5 and luna.
Our model runs with no test-time compute (Qwen3-4B-Instruct-2507 has no thinking mode, and its output is XGrammar-constrained to start with `{`), and the other readers run at their lowest reasoning setting; Haiku 5.5 cannot disable thinking through the Claude Code CLI.
The shipped model is pd3g287: a Qwen3-4B-Instruct-2507 LoRA trained on simulator rows with realistic identity formats, then 287 steps of GRPO, run in hybrid mode (it reads one document at a time and deterministic code does the matching, rupee arithmetic and ITC rules).
We pick models on full reconciliation of real documents, since that is the actual task; simulated dev and test sets were early filters during development, and their numbers are in `reports/`. The shipped model sometimes leaves an identity field blank that the page shows (counts in `reports/hybrid.md`).
GRPO: the first run (step 75) was neutral and was not shipped; the second run, from the realistic-formats adapter, is the shipped pd3g287; the AlignTune SGLang rollout backend we built for GRPO is upstream (PR #32) as infrastructure, not as a headline gain.
The shipped model was trained in a few hours on a hackathon clock, and most of its lost ITC exact comes from misreading amounts on the page (true amounts alone lift it from 61.1 to 88.6), which we expect more training, better algorithms and a better harness to improve.
Simulated-data results (test and dev), per-field accuracy, the Sonnet comparison and every paired test are in `reports/hybrid.md`, `reports/results.md`, `reports/frontier-hybrid.md` and `reports/pipeline.md`.

## Weights and data

- LoRA adapters for Qwen3-4B-Instruct-2507 (Apache-2.0): https://huggingface.co/broman23/gst-recon-qwen3-4b-adapters
- Simulator-generated training and eval data (Apache-2.0, synthetic only): https://huggingface.co/datasets/broman23/gst-recon-synthetic

## License

GPL-3.0-only; see `LICENSE`.
The upstream invoice print formats vendored unchanged in `realworld/formats/vendor/` keep their own licences (GPL-3.0, LGPL-3.0 and MIT, listed in `realworld/PROVENANCE.md`), and the templates ported from them in `realworld/formats/` are derivative works distributed under GPL-3.0.
