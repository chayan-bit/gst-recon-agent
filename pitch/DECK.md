# Deck outline: gst-recon (Syntax Error 2026, Local LLM track)

Ten slides, about 4 minutes if presented live, and each slide also reads on its own as a static PDF.
Every number is copied from a public report: `reports/results.md`, `reports/hybrid.md`, `reports/pipeline.md`, `reports/curation.md` or `reports/serving.md`.
A token in double braces is a number that has not been measured yet; nothing else on this page is an unmeasured claim.
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
- 84 item concepts, each with 8 hand-written core phrases expanded into at least 32 distinct forms (exactly 2,688 distinct case-folded phrasings: 84 concepts x 8 core phrases x 4 distinct forms each, counted by `scripts/count_phrasings.py`): typos, abbreviations, Hinglish, vendor jargon. No phrase states the use.
- Held-out out-of-distribution test set: 20 of the 84 concepts never seen in training, two unseen invoice layouts (SaaS two-column, handwritten bill), unseen buyer profiles (driving school, caterer, auto workshop), unseen states and number formats, held-out date formats.
- A shortcut audit scores trivial baselines (majority, no-anomaly, keyword lookup, context-blind rules engine) so you can see how much of the task a shortcut solves: best baseline ITC-exact 82.3% on out-of-distribution cases (the context-blind rules engine, handed the true extraction and links; 82.7% overall), but only 46.8% context accuracy. <!-- reports/results.md, "context-blind rules (oracle extraction and links)", test_ood and Overall rows -->
- A small real-world sanity set from public sample invoice formats (36 documents, 12 cases) is a separate, clearly labelled check.

Visual: a split bar showing train / test_iid / test_ood, with the held-out items listed under test_ood, and a two-row "same item, two buyers, two answers" card.

## Slide 6 - Results: the full reconciliation, on simulated cases and on real documents

- Headline table: the whole pipeline end to end, scored by the same scorer.

| System | Test ITC exact | Test match | Test composite | Semireal ITC exact | Semireal match | Semireal composite |
|---|---|---|---|---|---|---|
| pd3g287 (shipped): per-document model + our reconciler | {{SHIP_ITC_PT}} | {{SHIP_MATCH_PT}} | {{SHIP_COMP_PT}} | 61.1 | 71.5 | 72.9 |
| student-perdoc-sft (v1): first per-document model + our reconciler | {{V1_ITC_PT}} | {{V1_MATCH_PT}} | {{V1_COMP_PT}} | 58.5 | 64.1 | 68.6 |
| Claude Haiku 5.5, same hybrid harness (one call per document + our reconciler); minimum thinking (mean {{HAIKU_THINK_TOKENS}} tokens per document), cannot be disabled via the CLI | {{HAIKU_TEST_ITC}} | {{HAIKU_TEST_MATCH}} | {{HAIKU_TEST_COMP}} | {{HAIKU_SEMI_ITC}} | {{HAIKU_SEMI_MATCH}} | {{HAIKU_SEMI_COMP}} |
| Claude Haiku 4.5, same hybrid harness (one call per document + our reconciler); thinking off (0 thinking tokens) | {{HAIKU45_TEST_ITC}} | {{HAIKU45_TEST_MATCH}} | {{HAIKU45_TEST_COMP}} | {{HAIKU45_SEMI_ITC}} | {{HAIKU45_SEMI_MATCH}} | {{HAIKU45_SEMI_COMP}} |
| GPT-6 luna, same hybrid harness (one call per document + our reconciler); lowest reasoning effort | {{LUNA_TEST_ITC}} | {{LUNA_TEST_MATCH}} | {{LUNA_TEST_COMP}} | {{LUNA_SEMI_ITC}} | {{LUNA_SEMI_MATCH}} | {{LUNA_SEMI_COMP}} |
| Claude Sonnet, whole case in one prompt (a different harness; thinking at CLI default) | 96.3 | 99.0 | 94.4 | not run | not run | not run |

- Test is the 120 simulator test cases; semireal is 54 cases built around real documents with simulated purchase register, GSTR-2B and bank books, pooled, so it measures document reading and not real book messiness, and its labels were drafted by a model and not verified by a human.
- ITC exact is the share of invoices whose eligible, blocked and deferred amounts are all within Rs 1 of the truth; match is match accuracy; composite is the weighted composite, which has a high floor.
- pd3g287 and student-perdoc-sft run under reconciler v3 and doc schema v2, and their test rows were scored once.
- Sonnet ran through the Claude Code CLI with the whole case in one prompt, so its row is a different harness and not a like-for-like comparison with the hybrid rows.
- No model gets test-time compute beyond what its harness cannot remove: our 4B (Qwen3-4B-Instruct-2507) has no thinking mode and its output is XGrammar-constrained to start with `{`, Haiku 4.5 runs with thinking off, GPT-6 luna at the lowest reasoning effort, and Haiku 5.5 cannot disable thinking through the Claude Code CLI, so its row is at minimum thinking.
- Sonnet's whole-case run used the Claude Code CLI defaults, and its report does not record the thinking setting, so we say thinking at CLI default.
- For scale, a context-blind rules engine handed the true extraction and links scores 82.7 ITC exact, 100.0 match and 87.3 composite on the same test cases: on ITC exact alone it is ahead of our system, and what the model adds is reading the documents and judging context.
- The shipped system is pd3g287: Qwen3-4B-Instruct-2507 with a per-document LoRA trained on simulator rows with realistic identity formats, then 287 steps of GRPO with the per-document reward, run in hybrid mode (the model reads one document at a time and deterministic code does the matching, rupee arithmetic and ITC rules) with reconciler v3 and doc schema v2.
- We chose it by a post-hoc override, and we say so plainly. Our pre-registered ship rule said no, because it regressed on simulated dev (small-dev ITC exact delta -1.7, 95% CI [-4.5, +0.9], against a required lower bound of -3.0). We overrode the rule after the fact because real documents are what matter: on the 54 pooled semireal cases it is the best model end to end (composite +4.3 [+1.7, +7.0], match +7.4 [+1.4, +13.7], ITC exact +2.6 [-1.4, +6.7], not significant), and the simulated dev sets use the old simulator formats, which this model was not trained on. The override was committed before the test set was run. It over-abstains: it left 22 visible identity fields empty on the 42 real documents and 16 visible invoice numbers empty on the 30 held-out ones (counts in `reports/hybrid.md`).
- GRPO: the first run (step 75, from the second per-document adapter) was neutral on the dev sets and was not shipped; the second run, from the realistic-formats adapter, is the shipped pd3g287, by the override above; the AlignTune SGLang rollout backend we built for GRPO is upstream (PR #32) as infrastructure, not as a headline gain.
- Per-field accuracy, dev sets, per-document scores on real invoices, schema-valid rates, decoding ablations and every paired test are in `reports/hybrid.md`, `reports/results.md` and `reports/pipeline.md`.
<!-- Figures: reports/results.md (Sonnet and context-blind rows, overall, n = 120), reports/hybrid.md (semireal under doc schema v2, commit 0358900; test rows for pd3g287 and student-perdoc-sft, pending; Haiku row from the gst-eval run, pending). -->

Visual: the headline table as a slide, with the shipped row highlighted and the harness note in small print under it; no staircase chart, because every bar would be a different harness.

## Slide 7 - Not claiming to beat frontier models: how close, at what cost

- Claim: on the same 120 test cases pd3g287 reaches {{SHIP_PCT_SONNET}}% of Claude Sonnet's ITC exact ({{SHIP_ITC_PT}} against 96.3; Sonnet is a different harness, the whole case in one prompt, so this is a comparison of systems), fully local; Sonnet costs $226.88 per 1,000 cases at list price (token counts through the CLI), and we do not publish a student cost ratio because we have not measured the student's GPU cost.
- Latency: p50 38.0 s per case end to end (SFT with the compact grammar, 30 simulator cases) and 61.2 s per case in hybrid mode (one document per call, first pass, slightly understated because a demo recording shared the server), against 67.9 s for Sonnet through the Claude Code CLI (not a clean API latency). <!-- reports/results.md throughput table ("SFT constrained, compact grammar (same 36 cases)", "Claude Sonnet (via Claude Code CLI)") and reports/hybrid.md hybrid throughput -->
- Open-model reference: Qwen3-30B-A3B (the teacher, served on SGLang with a 64k context), run end to end on the same 120 test cases, scores ITC exact 59.8, match 71.1 and composite 69.1. <!-- reports/results.md, teacher-30B constrained, overall -->
- Constrained versus unconstrained decoding on the SFT student (XGrammar, 30 simulator cases): schema-valid 70.0% -> 100.0%, ITC-exact 72.3 -> 75.7 (paired on 42 cases the difference is -2.4 points [-7.3, +2.5], p = 0.32 without the grammar, so the grammar buys valid output at no measurable accuracy cost). <!-- reports/results.md, "SFT unconstrained" and "SFT constrained, compact grammar" rows and their note -->

Visual: a scatter of accuracy (y, ITC-exact) against cost per 1,000 cases (x, log scale) with five points: base 4B, SFT, per-document hybrid, 30B teacher, Claude Sonnet.
Next to it, a two-bar chart of the constrained versus unconstrained student.

## Slide 8 - What we gave back to the sponsor stack

- AlignTune: an SGLang rollout backend for GRPO. Rollouts come from a live SGLang server, prompts are sent once with `n` samples so RadixAttention shares the prefill, and weights are synced after each step. Measured: about 9x faster rollout generation (9.6x on SGLang 0.5.22 and 9.9x on 0.5.10.post1 with full weight sync, 7.6x with adapter sync; 1,623 tokens/s with Hugging Face generate against 14,949 tokens/s with SGLang on 0.5.22; a 0.5B GSM8K benchmark, AlignTune PR #32).
- AuditKIT: structured-extraction metrics (`JsonSchemaValid`, `FieldF1`, 66 tests) and a fix for `compare().significance()`, whose p-value was about 0.5 for any effect (50 pairs, means 0.11 vs 0.80, p = 0.52).
- AlignTune bugs found the hard way: the datasets fingerprint pickles the whole trainer (a 42.7 GB host-RAM blowup), YAML values silently overridden by defaults (512-token truncation, wrong output directory), and dropped train keys (gradient checkpointing silently off).
- CuratorKIT gates earn their keep: only 651 of 1,242 teacher paraphrases were kept; 471 failed the code fact check and 120 failed the HallucinationGate.

Upstream PRs, all open at the time of writing:
- AuditKIT PRs: #9 https://github.com/Lexsi-Labs/AuditKIT/pull/9, #10 https://github.com/Lexsi-Labs/AuditKIT/pull/10, #11 https://github.com/Lexsi-Labs/AuditKIT/pull/11.
- CuratorKIT PRs: #34 https://github.com/Lexsi-Labs/CuratorKIT/pull/34, #35 https://github.com/Lexsi-Labs/CuratorKIT/pull/35, #36 https://github.com/Lexsi-Labs/CuratorKIT/pull/36.
- AlignTune PRs: #32 https://github.com/Lexsi-Labs/AlignTune/pull/32 (SGLang rollout backend for GRPO), #33 https://github.com/Lexsi-Labs/aligntune/pull/33 (unsloth SFT fingerprint pickles the model into host RAM), #34 https://github.com/Lexsi-Labs/aligntune/pull/34 (config values replaced by factory defaults), #35 https://github.com/Lexsi-Labs/aligntune/pull/35 (train keys dropped by the parser).
- SGLang PR: #46287 https://github.com/sgl-project/sglang/pull/46287 (LoRA requests rejected before adapter reservation no longer try to release a null adapter id and log TypeError tracebacks).
- Two SGLang 0.5.10 issues we hit (a LoRA `n>1` refcount hang on unload, and a SIGTERM drain hang from leaked rejected requests) are fixed on SGLang main (#31808 in v0.5.22 and #28694 in v0.5.14), so we filed no PRs for them; our rollout backend works around both on 0.5.10.

Visual: a four-tile grid, one tile per toolkit, each with a one-line before/after and a link to the upstream pull request.
The status of each (upstream PR, open or merged) is shown honestly in a corner badge: "11 pull requests open upstream, none merged".

## Slide 9 - How SGLang is used, feature by feature

- XGrammar JSON-schema constrained decoding: the schema (`schemas/output.schema.json`) is passed as `response_format`, so every answer parses and validates, which also makes it a legal input to the verifiable reward.
- RadixAttention prefix sharing: GRPO samples n completions of one long prompt (up to 6,144 prompt tokens of invoices in our GRPO config), and the shared prefix is prefilled once; measured 1216 of 1216 prompt tokens served from cache on the repeated samples, against 0 without `n`.
- Weight updates from disk during RL: the policy is exported and the server reloads it with `update_weights_from_disk`, which also flushes the prefix cache, so rollouts always come from the current policy.
- Long context: the 30B teacher is served with a 65,536-token context (a 58,751-token prompt answered in 3.8 s), because real month-end cases are tens of thousands of tokens.
- Multi-LoRA serving: one SGLang server serves base, base:sft and base:perdoc as LoRA adapters on a single base model, switched per request (the server is launched with enable_lora and max_loras_per_batch 3). No throughput claim is made for it.

Visual: a table with columns "SGLang feature", "what it does for us", "evidence" (a log line, a metric or a chart), one row per bullet.
Only rows with evidence stay on the slide.

## Slide 10 - What is solid, what is not yet, and what is next

- Solid: ground-truth-first data, checkable rewards, a held-out OOD set, an honest baseline ladder, and four contributions to the sponsor toolkits.
- Not yet: real scans at scale (the semireal set is 54 real documents with simulated books, and a separate eval-only set of 42 real purchase documents stays private), tax law beyond the modelled sections, and a vision front end that replaces OCR.
- What we learned: the real-invoice eval exposed an overfit to simulator identity formats; we fixed it in the simulator from CGST Rule 46 without using those invoices and retrained, and the retrained models no longer write the simulator-format invoice numbers the first one invented (counts in `reports/hybrid.md`).
- The result is mixed and we say so: on the 54 semireal cases the retrained models match better end to end, but they cost ITC exact on the simulated dev sets, whose formats are the old ones.
- Our pre-registered ship rule therefore said no for pd3g287, we overrode it after the fact, before the test set was run, and shipped it; the rule had also been amended once for an ensemble, which still failed. Over-abstention is the price.
- Next round: re-validate with a dev set in the new formats.
- Next: a vision-language student that reads the page directly, more of the GST rules (and a lawyer-reviewed rule table), and upstreaming the AlignTune and AuditKIT work.

Visual: a three-column "solid / not yet / next" board; under it, a QR code to the repo (https://github.com/chayan-bit/gst-recon-agent) and the demo video.
