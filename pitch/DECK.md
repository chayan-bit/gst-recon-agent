# Deck outline: gst-recon (Syntax Error 2026, Local LLM track)

Ten slides, about 4 minutes if presented live, and each slide also reads on its own as a static PDF.
Every number is a placeholder written in double braces; the source of each is in `NUMBERS.md`.
Nothing here is a measured result unless `NUMBERS.md` marks it as measured.
Visuals marked "committed" already exist in the repo (`examples/`, `reports/smoke/`); all others have to be made.
All invoices, GSTINs and buyers are synthetic (simulator output), and the deck says so on the slides that show them.

## Slide 1 - Private, local financial reasoning on one GPU

Must work for a non-accountant judge in 10 seconds, so the slide is one picture and one sentence.

- Headline: "Private, local financial reasoning on one GPU."
- One-sentence explainer: "Messy invoices in, a checked reconciliation out, and the rupees of tax credit you would have wrongly claimed, flagged with the legal reason."
- Footer line: "A 4B open model on SGLang with grammar-constrained JSON. Your invoices and bank statements never leave the building."

Visual: a three-panel strip, left to right.
Left panel: a skewed, stamped, scanned invoice (committed: `examples/test_iid-hard-23-00001/images/D05.png`) next to a WhatsApp-style text bill, to show "messy".
Middle panel: a box labelled "your GPU, your network" with a padlock and a small SGLang logo, and the line "no cloud API".
Right panel: a four-row reconciliation table where three rows are green and one row is red.
The red row reads "Tea and sugar for 'annual day celebration' - credit blocked - Rs 5,713.44 - Sec 17(5)(b)(i), food and beverages" (this is the real ground truth of the committed hard example, D01, a synthetic invoice).
Use the amount only with the label "synthetic example".

## Slide 2 - The data that cannot go to a cloud API

- A company's purchase invoices, bank statements and supplier GSTINs are its supplier list, its prices and its cash position in one file.
- Month-end GST input-tax-credit (ITC) reconciliation is the job: match every invoice to the books, to the government's GSTR-2B statement and to a payment, then decide how much tax credit can be claimed.
- A wrong claim is not a typo, it is tax that must be repaid with interest, and the legal reason must be stated.
- Why GST: it is a hard, rule-heavy, checkable case study of private financial reasoning, not the only use. The same shape fits any on-prem document-to-decision workflow.

Visual: a simple "data leaves the building" diagram with the cloud route crossed out and the on-prem GPU route highlighted.
Add a small inset: "13 documents in one month, scans and pasted text mixed" (committed example: `examples/test_ood-medium-22-00000`, a case with 13 documents).

## Slide 3 - What the system does, end to end

- Input per case: OCR text of the invoices (scans and WhatsApp/email text), the purchase register export, the GSTR-2B JSON and the bank statement.
- Output per case: one strict JSON object with three parts: extraction per invoice, matching with flags, and ITC eligible / blocked / deferred per invoice with a reason code.
- The model is text-only: scans go through Tesseract OCR first, and the pipeline is honest about what OCR loses (`ocr_recall` is recorded per case).
- SGLang serves the model with XGrammar JSON-schema constrained decoding, so the output is always valid against the schema.

Visual: a left-to-right pipeline diagram: invoice image -> Tesseract OCR -> prompt (invoices + register + 2B + bank) -> 4B model on SGLang with XGrammar -> JSON -> reconciliation table.
Under the diagram, show one real excerpt of the prompt and the first lines of the matching JSON (committed: `examples/test_iid-hard-23-00001/prompt.txt` and `target.json`).

## Slide 4 - Ground truth first, so every answer is checkable by code

- A deterministic Python simulator builds the true state of a company's month first (suppliers, invoices, register, 2B, bank, buyer profile); documents are rendered and degraded from it afterwards.
- The rules engine computes the correct ITC from the world, so the truth is never "what a model wrote down".
- Every reward is code: schema validity, per-field match, accounting identities, match-table correctness, exact ITC in rupees.
- That is what makes verifiable rewards (GRPO) possible: the reward is a function, not a judge model.

Visual: a flow diagram "world state -> rules engine -> truth JSON" branching into "-> renderer + OCR -> prompt" and "-> reward function".
A small table of the reward components and weights (composite and GRPO reward in `gst_recon/sim/RULES.md`).

## Slide 5 - Built so the model cannot memorise its way to a score

- The buyer's profile changes the right answer: the same tea and sugar is blocked for a construction contractor's "annual day celebration" and can be eligible for a caterer, so the model has to read the context, not the item name.
- 84 item concepts, each with 8 hand-written core phrases expanded into at least 32 distinct forms (so at least 2,688 phrasings; exact count {{N_PHRASINGS}}): typos, abbreviations, Hinglish, vendor jargon. No phrase states the use.
- Held-out out-of-distribution test set: 20 of the 84 concepts never seen in training, two unseen invoice layouts (SaaS two-column, handwritten bill), unseen buyer profiles (driving school, caterer, auto workshop), unseen states and number formats, held-out date formats.
- A shortcut audit scores trivial baselines (majority, no-anomaly, keyword lookup, context-blind rules engine) so you can see how much of the task a shortcut solves: best baseline ITC-exact 82.3% on out-of-distribution cases (the context-blind rules engine, handed the true extraction and links; 82.7% overall), but only 46.8% context accuracy. <!-- reports/results.md, "context-blind rules (oracle extraction and links)", test_ood and Overall rows -->
- A small real-world sanity set from public sample invoice formats (36 documents, 12 cases) is a separate, clearly labelled check.

Visual: a split bar showing train / test_iid / test_ood, with the held-out items listed under test_ood, and a two-row "same item, two buyers, two answers" card.

## Slide 6 - The climb: base, then SFT, then SFT plus GRPO

- Student: Qwen3-4B-Instruct-2507 with LoRA, trained with AlignTune: SFT on curated cases, then GRPO against the verifiable reward.
- Headline metric: ITC-exact, the share of invoices whose eligible, blocked and deferred amounts are all within Rs 1 of the truth, in-distribution then out-of-distribution: base {{BASE_ITCEXACT_IID}} / {{BASE_ITCEXACT_OOD}}, SFT 8.1 / 13.7 (the full-grammar run, a format mismatch; the compact-grammar rerun is pending), SFT+GRPO {{GRPO_ITCEXACT_IID}} / {{GRPO_ITCEXACT_OOD}}.
- The number that matters most for the pitch: context accuracy, the invoices where the buyer profile decides the answer ({{BASE_CTX_OOD}} -> 33.2 (full-grammar SFT) -> {{GRPO_CTX_OOD}}).
- The weighted composite is shown in small print ({{BASE_COMPOSITE_OOD}} / 58.9 (full-grammar SFT) / {{GRPO_COMPOSITE_OOD}}), because its floor is high: a model that copies the documents perfectly and calls everything clean already scores about 0.81.
<!-- Slide 6 SFT figures: reports/results.md, "SFT constrained (full grammar)" rows, test_iid 8.1, test_ood 13.7, context accuracy test_ood 33.2, composite test_ood 58.9. -->
- What GRPO adds over SFT on ITC-exact, with a paired bootstrap interval and a corrected p-value: {{GRPO_DELTA_VS_SFT_ITCEXACT_OOD}} points, p = {{GRPO_VS_SFT_P}}.

Visual: a three-step staircase bar chart (base, SFT, SFT+GRPO), two bars per step (iid and ood), with 95% bootstrap CIs.
The chart is built from the ITC-exact and context-accuracy columns, in the style produced by `python -m gst_recon.eval report` (sample in `reports/smoke/results.png`, a harness check, not results).
If GRPO shows no significant gain on some metric, the slide says so and shows the metric where it does help.

## Slide 7 - Not claiming to beat frontier models: how close, at what cost

- Claim: the 4B student reaches {{Y_PCT_OF_SONNET_ACCURACY}}% of Claude Sonnet's ITC-exact accuracy at {{Z_COST_PCT}}% of the cost per 1,000 cases, fully local.
- Latency: p50 {{STUDENT_P50_LATENCY_S}} s on SGLang versus {{SONNET_P50_LATENCY_S}} s for Sonnet, with the caveat on the slide that the Sonnet number is measured through a CLI and is not a clean API latency.
- Open-model reference: Qwen3-30B-A3B (the teacher, served on SGLang with a 64k context) scores 55.7 / 63.8 ITC-exact (in-distribution / out-of-distribution; Claude Sonnet 94.9 / 97.8). <!-- reports/results.md, teacher-30B constrained and Claude Sonnet rows, test_iid and test_ood -->
- Constrained versus unconstrained decoding on the student (XGrammar): schema-valid {{GRPO_SCHEMA_VALID_UNCON}}% -> {{GRPO_SCHEMA_VALID_CON}}%, ITC-exact {{GRPO_ITCEXACT_UNCON}} -> {{GRPO_ITCEXACT_CON}}.

Visual: a scatter of accuracy (y, ITC-exact) against cost per 1,000 cases (x, log scale) with five points: base 4B, SFT, SFT+GRPO, 30B teacher, Claude Sonnet.
Next to it, a two-bar chart of the constrained versus unconstrained student.

## Slide 8 - What we gave back to the sponsor stack

- AlignTune: an SGLang rollout backend for GRPO. Rollouts come from a live SGLang server, prompts are sent once with `n` samples so RadixAttention shares the prefill, and weights are synced after each step. Measured speedup {{ROLLOUT_SPEEDUP_X}}x on rollout generation.
- AuditKIT: structured-extraction metrics (`JsonSchemaValid`, `FieldF1`, 66 tests) and a fix for `compare().significance()`, whose p-value was about 0.5 for any effect (50 pairs, means 0.11 vs 0.80, p = 0.52).
- AlignTune bugs found the hard way: the datasets fingerprint pickles the whole trainer (a 42.7 GB host-RAM blowup), YAML values silently overridden by defaults (512-token truncation, wrong output directory), and dropped train keys (gradient checkpointing silently off).
- CuratorKIT gates earn their keep: only 55% of teacher paraphrases were kept; 121 failed the code fact check and 28 failed the HallucinationGate.

Upstream PRs, all open at the time of writing:
- AuditKIT PRs: #9 https://github.com/Lexsi-Labs/AuditKIT/pull/9, #10 https://github.com/Lexsi-Labs/AuditKIT/pull/10, #11 https://github.com/Lexsi-Labs/AuditKIT/pull/11.
- CuratorKIT PRs: #34 https://github.com/Lexsi-Labs/CuratorKIT/pull/34, #35 https://github.com/Lexsi-Labs/CuratorKIT/pull/35, #36 https://github.com/Lexsi-Labs/CuratorKIT/pull/36.
- AlignTune PR: #32 https://github.com/Lexsi-Labs/AlignTune/pull/32.

Visual: a four-tile grid, one tile per toolkit, each with a one-line before/after and a link to the branch or issue draft.
The status of each (fork branch, draft, upstream PR) is shown honestly in a corner badge: "7 pull requests open upstream, none merged; AlignTune bug write-ups are drafts, not filed".

## Slide 9 - How SGLang is used, feature by feature

- XGrammar JSON-schema constrained decoding: the schema (`schemas/output.schema.json`) is passed as `response_format`, so every answer parses and validates, which also makes it a legal input to the verifiable reward.
- RadixAttention prefix sharing: GRPO samples n completions of one long prompt (up to 6,144 prompt tokens of invoices in our GRPO config), and the shared prefix is prefilled once; measured 1216 of 1216 prompt tokens served from cache on the repeated samples, against 0 without `n`.
- Weight updates from disk during RL: the policy is exported and the server reloads it with `update_weights_from_disk`, which also flushes the prefix cache, so rollouts always come from the current policy.
- Long context: the 30B teacher is served with a 65,536-token context (a 58,751-token prompt answered in 3.8 s), because real month-end cases are tens of thousands of tokens.
- Multi-LoRA serving: include this bullet only if the demo serves base, SFT and GRPO adapters side by side (`{{MULTI_LORA_USED}}`); otherwise delete it.

Visual: a table with columns "SGLang feature", "what it does for us", "evidence" (a log line, a metric or a chart), one row per bullet.
Only rows with evidence stay on the slide.

## Slide 10 - What is solid, what is not yet, and what is next

- Solid: ground-truth-first data, checkable rewards, a held-out OOD set, an honest baseline ladder, and four contributions to the sponsor toolkits.
- Not yet: real scans at scale (the real-world sanity set is small: 36 documents, field F1 {{REAL_FIELD_F1}}), tax law beyond the modelled sections, and a vision front end that replaces OCR.
- Next: a vision-language student that reads the page directly, more of the GST rules (and a lawyer-reviewed rule table), and upstreaming the AlignTune and AuditKIT work.

Visual: a three-column "solid / not yet / next" board; under it, a QR code to the repo and the demo video.
