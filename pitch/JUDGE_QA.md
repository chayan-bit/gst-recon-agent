# Judge Q&A: the hardest questions, with honest answers

Rule for every answer: say what was measured, say what was not, and never reach past the evidence.
Every number is copied from `reports/results.md`, `reports/hybrid.md`, `reports/pipeline.md`, `reports/curation.md` or `reports/serving.md`.

## 1. Isn't this sim-to-sim? You train and test on your own simulator.

Yes, the training data and the main evaluation come from the same simulator, and the headline numbers are not evidence that it works on real company data.
What the simulator buys is a checkable truth: every answer is verified by code, which is what makes a verifiable reward possible at all, and a real invoice archive has no ground truth for ITC.
Three things keep it from being a closed loop.
First, the documents are rendered, degraded (rotation, blur, JPEG, folds, photocopy and fax effects, stamps) and read by real Tesseract, so the text the model sees carries real OCR noise, not generated noise.
Second, the out-of-distribution split holds out 20 of the 84 item concepts, two invoice layouts, three buyer profiles, a quarter of the states, and number and date formats, so the test measures generalisation within the simulator's world.
Third, a small real-world sanity set built from public sample invoice formats (36 documents) is reported separately: schema-valid 100.0%, field F1 96.4% [92.8, 98.9] (the SFT student with the compact grammar, 12 cases).
What we do not claim: that the ITC decisions are right on real books, only that the pipeline, the metrics and the generalisation tests are sound.

## 2. Why not just call GPT or Claude?

For this data, privacy decides: purchase invoices, bank statements and supplier GSTINs are the data a business cannot send to a third-party API, and an on-premises model removes that question.
Latency at month-end volume is the second reason: p50 38.0 s per case end to end (SFT with the compact grammar, 30 simulator cases) and 61.2 s per case in hybrid mode (one document per call, first pass, slightly understated because a demo recording shared the server), against 67.9 s for Sonnet through the Claude Code CLI (not a clean API latency) (see question 6 for how fair that comparison is).
We are not claiming the small model is better: on the same 120 simulator test cases Claude Sonnet scores 96.3% ITC-exact end to end against 80.0% for our shipped hybrid system (pd3g287 plus the deterministic reconciler), so the system reaches 83.1% of Sonnet's ITC-exact accuracy; student-perdoc-sft reached 83.2% (80.1 / 96.3) under the same doc schema v2, and 83.0% (79.9 / 96.3) under schema v1.
A private deployment of a hosted model is another way to meet a privacy requirement; we did not test that, and a team that can use one should compare it.

## 3. How do you know your GST law is right?

We do not know it is complete, and we do not claim legal review we have not had (review status: rules encoded by the author from CGST Act sections 16(2), 17(5) and 34 and rules 36(4) and 37, with Circular 172/04/2022; not yet reviewed by a practising CA).
What exists is a written, cited model of the law in `gst_recon/sim/RULES.md`: sections 16(2), 17(5), 34, rule 36(4), rule 37, the reverse-charge treatment and the 17(5) exceptions, with the circular that supports each exception.
The rules engine is a deliberate model, and every simplification is listed there (for example, no Section 17(2) apportionment, canteen credit assumes the employer bears the full cost).
Rates are date-effective across the 22 September 2025 GST 2.0 change, and any rate we could not verify is never generated after the cutover.
Tests assert invariants such as every rupee of tax landing in exactly one of eligible, blocked and deferred.
If the model of the law is wrong, the student faithfully learns the error, but the rule table is data in one place: fix it, regenerate, retrain.

## 4. What does GRPO add over SFT?

(Before the GRPO numbers: the shipped student is the per-document hybrid described in question 12.)

It is part of the shipped adapter, chosen by an override we explain below, and its measured gain is on real documents, not on simulated dev.
SFT teaches the model to imitate a reference answer token by token, which is how it learns the format and the common patterns.
GRPO samples several answers to the same case and rewards the outcome we care about, which code can check exactly: schema validity, flag and reason-code sets, and exact ITC on the invoices that are not fully eligible, with a dense term so partial progress still counts.
We built the SGLang rollout backend for it and upstreamed it to AlignTune (PR #32), and we ran GRPO twice.
The first run (step 75, from the second per-document adapter) was neutral against its starting point on the two dev sets (ITC-exact +0.9 points [-0.5, +2.5], p = 0.23 on 120 cases and -0.4 [-1.0, +0.2], p = 0.19 on 60, scored under reconciler v3, nothing significant); on the semireal set it added 1 to 2 points of ITC-exact but lost 4 to 7 points of match accuracy, and on 42 real purchase documents it read invoice numbers worse (21.4% against 30.9%) and invented more identity fields (12.3% against 8.8%), so we did not ship it.
The second run, from the realistic-formats adapter (287 steps, one pass over 1,147 hard documents), is pd3g287, the shipped adapter.
We chose it by a post-hoc override, and we say so plainly.
Our pre-registered ship rule said no, because it regressed on simulated dev (small-dev ITC-exact delta -1.7, 95% CI [-4.5, +0.9], against a required lower bound of -3.0).
We overrode the rule after the fact because real documents are what matter: on the 54 pooled real-document cases (semireal, books simulated) it is the best model end to end, with composite +4.3 [+1.7, +7.0], match accuracy +7.4 [+1.4, +13.7] and ITC-exact +2.6 [-1.4, +6.7], not significant.
The simulated dev sets use the old simulator formats, which this model was not trained on.
The override was committed before the test set was run.
It over-abstains: it left 22 visible identity fields empty on the 42 real documents and 16 visible invoice numbers empty on the 30 held-out ones, with invoice-number accuracy 21.4% and 30.0% against 30.9% and 40.0% for student-perdoc-sft.
The tension is the main open finding: the simulated dev sets reward familiarity with the simulator's formats, the real documents reward the format and abstention fixes, and the next round re-validates with a dev set in the new formats.
What SFT adds end to end is still the cleanest number to quote: over the base model, paired on 30 simulator cases, +25.7 ITC-exact points [18.8, 32.6] and +45.9 on context accuracy [35.0, 56.5], all p = 0.0005.
One limit we know about: our GRPO cases are short (2 to 4 invoices, prompts up to 6,144 tokens).
One thing we checked rather than assumed: both SFT runs used completion-only loss, with every prompt token labelled -100 so the model is trained on its reply only.
The end-to-end run used unsloth's responses-only masking, verified on the first curated row with the real Qwen3 tokenizer before launch.
The per-document run uses TRL's prompt/completion masking, and its runner aborts before step 1 unless the prompt is a fully masked prefix (first row: 1,235 prompt tokens masked, 224 reply tokens trained).
That check caught an earlier attempt in which AlignTune's data normaliser had turned the rows into full-sequence messages, so no full-sequence step was trained.

## 5. What breaks on real scans?

A text-only model cannot recover what the OCR lost, and we measure that instead of hiding it: each case records `ocr_recall`, and the facts that are unrecoverable from the OCR text (in the committed hard example, line HSN codes on five of 13 documents).
In training, a target HSN that OCR lost is blanked rather than demanded as a guess.
On real scans we expect these failure modes, in roughly this order: handwriting, photographs taken at an angle or with shadows, multi-page tables, mixed-language text, and digits confused by OCR (in one committed case OCR turned the I in a supplier GSTIN into a 1, and the model has to repair it against the register and the 2B).
On the real-format sanity set field F1 is 96.4% [92.8, 98.9] for the SFT student with the compact grammar; every simulator case in the report falls in the partial-recall bucket, so we have no full-recall comparison to show.
The fix we would build next is a vision-language student that reads the page directly.

## 6. How fair is the comparison with Sonnet on accuracy and latency?

Partly, and the caveats are on the slide.
The Sonnet baseline runs through the Claude Code CLI because there is no API key: each case is one non-interactive call with the schema in the system prompt and no constrained decoding, at concurrency 2.
Its cost is list-price arithmetic from token counts, and its latency includes CLI overhead, so the latency ratio overstates the gap and should be read as an upper bound.
We have not measured the student's GPU cost per 1,000 cases, so we publish no cost ratio; the report has Sonnet's list-price cost ($226.88 per 1,000 cases) and the 30B teacher's illustrative GPU cost ($20.04), both stated there.
Accuracy is scored by the same code on the same cases for every model, and failed or truncated outputs count as wrong for everyone.
The claim we stand behind is the ratio of accuracy on the same held-out cases, plus the fact that nothing left the machine.

We also ran Claude and GPT readers in our hybrid harness (one call per document plus our reconciler, no test-time compute: Haiku 4.5 thinking off, GPT-6 luna at the lowest reasoning effort, Haiku 5.5 at minimum thinking because the Claude Code CLI cannot disable it), and on the 54 semireal real documents they lead our shipped model: composite 86.5 for Haiku 5.5 (+13.6 over pd3g287), 77.9 for luna (+5.0, significant) and 77.4 for Haiku 4.5 (+4.5, p = 0.068), with ITC exact leads of +9.6 for luna (significant) and +7.1 for Haiku 4.5 (not significant).
On the 120 simulator test cases luna (reasoning none) scores 81.9 / 90.5 / 84.0 against 80.0 / 85.0 / 81.6 for pd3g287: ITC exact +1.9 (not significant), match +5.6 and composite +2.4 (both significant).
Our model invents fewer identity fields on those documents (9.7% of identity slots against 16.6% for Haiku 4.5 and 15.4% for luna), which is a diagnostic and not a headline; its case is that it runs locally on one 16 GB GPU and no document leaves the machine.

## 7. With only 84 concepts, isn't the model just memorising them?

For the in-distribution split, partly, and that is fine: a bookkeeping model should know that a steel coil is a normal input.
The question is whether it memorises the answer instead of reading the context, and the data is built against that.
The same item gets a different answer depending on the buyer's profile and the purpose remark, and the item alone never states the use, so a model that keys on the item name is wrong on the context-dependent invoices by construction.
Our `context_blind` baseline (the real rules engine, given perfect document comparison, but no buyer profile and no remarks) shows how much a shortcut gets: ITC-exact 82.7% (82.3% out of distribution) and context accuracy 50.1% (46.8% out of distribution).
Its ITC-exact is high because most invoices do not depend on the buyer profile; context accuracy is the number that exposes the shortcut, 50.1% against 92.7% for Claude Sonnet on the same cases.
Twenty concepts and a quarter of the phrasings of the rest are held out entirely.
`tests/test_splits.py` asserts that no description, concept, remark, header, profile, state or name token of a test split appears in train, the eval sets are frozen by hash manifest, and training builders refuse any path under the evaluation output.
Not yet shown: that it generalises to concepts far outside the 84; the held-out 20 are in the same families.

## 8. Doesn't constrained decoding just hide errors behind valid JSON?

It guarantees the syntax and the schema, not the content, and a grammar can force a well-formed but wrong value.
That is why validity is reported separately from correctness, and why the table shows both.
Measured on the 30B teacher, on the same 19 cases: schema-valid 15.8% unconstrained against 94.7% constrained, and ITC-exact 14.9% against 68.0%; 15 of the 19 unconstrained replies hit the 24,000-token cap in repetition loops.
On the SFT student (30 simulator cases), between unconstrained and constrained decoding: schema-valid 70.0% -> 100.0% and ITC-exact 72.3 -> 75.7; paired on 42 cases, dropping the grammar costs -2.4 ITC-exact points [-7.3, +2.5], p = 0.32, so the grammar buys valid output at no measurable accuracy cost.
Constrained output can also be cut off by the token budget, which leaves it unfinished; the harness counts truncations and context overflows as failures instead of discarding them, and we have not isolated the throughput overhead of constraining.
The point of the grammar is operational: downstream code can parse every answer and the reward function always has something to score.

## 9. Is SGLang really in your training loop, and are the sponsor contributions merged?

Be precise here, because the answer has three parts.
SGLang is the engine for teacher generation, serving and evaluation, and that is measured and logged.
The SGLang rollout backend for GRPO exists as AlignTune pull request #32 (open) with CPU tests and a GPU integration test, but it is wired into AlignTune's TRL GRPO trainer, while the unsloth backend ignores `rollout_backend`.
Our only GRPO config (`configs/grpo_sglang.yaml`) uses the TRL backend with `rollout_backend: sglang`, and the GRPO runner refuses to start without it, so a GRPO run cannot silently fall back to Hugging Face generation.
The GRPO runner refuses to start without that backend, and the shipped adapter's GRPO stage (pd3g287) used it: AlignTune with the TRL backend and SGLang rollouts (`configs/grpo_perdoc_v3_hard.yaml`; unsloth with SGLang is refused by design), every rollout request constrained to the document JSON schema, 287 steps (one pass over 1,147 hard documents, 4 per step) from the realistic-formats SFT LoRA, beta 0, temperature 1.0, on one H100; we do not present the backend as the reason for the accuracy, because we have no ablation against a Hugging Face rollout, and it stands as a contribution with its measured benchmark.
The backend was developed against SGLang 0.5.22, and the training host runs SGLang 0.5.10.post1 because of its CUDA driver, and the backend was tested end to end on both versions (full-sync fidelity on 0.5.10.post1: 0.049 nats per token against a noise floor of 0.052; rollout speedup 9.9x), as reported in PR #32.
On merging: they are open pull requests (AuditKIT #9, #10, #11, CuratorKIT #34, #35, #36, AlignTune #32, #33, #34, #35, SGLang #46287), eleven in all and none merged at the time of writing.

## 10. Your test cases are much longer than your training cases. Why should it work?

It may not, and that is a measured axis, not a hidden assumption.
Training cases are deliberately short so they fit the hardware: SFT cases have 3 to 6 invoices and fit 12k tokens in total, GRPO cases have 2 to 4 invoices with prompts up to 6,144 tokens and 4,096 completion tokens, while evaluation cases have 5 to 12 documents (easy), 10 to 25 (medium) and 20 to 40 (hard), up to tens of thousands of prompt tokens plus thousands of output tokens.
So even the easy evaluation cases are larger than most training cases.
The evaluation keeps the full difficulty sizes on purpose, and the report breaks results down by prompt length (up to 16k, 16 to 32k, over 32k tokens) and by difficulty.
Results by length for the SFT student with the compact grammar (30 simulator cases): ITC-exact 85.8% up to 16k tokens (16 cases), 69.1% for 16 to 32k (8 cases) and 57.7% above 32k (6 cases), so accuracy does fall with length.
No SFT-compact case overflowed the server context (the report's overflow table lists none); an overflow would count as a failure, and in hybrid mode no case overflows 16k because each call sees one document.
If the numbers drop sharply with length, the honest summary is that the system works on small and medium month-ends today and that long ones need longer-case training.

## 11. Why was your first SFT score 10.9%?

Because of a mismatch between the grammar we decoded with and the format we trained on, not because the model could not do the task.
The SFT targets use a compact form that drops fields that are zero, empty or false.
The constrained-decoding grammar we first served it with was the full one, which requires the blocked and deferred buckets and all four tax heads in every ITC record.
Those are slots the student never saw filled in training, and the grammar leaves it no way to omit them, so it filled them with junk.
On the 120 simulator cases (2,252 truth ITC records), the SFT model predicts blocked as nonzero in 79.0% of records where the truth is 21.9%, and deferred as nonzero in 72.2% where the truth is 12.2%.
The eligible bucket, the part the model did learn, is exactly right in 59.0% of aligned records (57.9% of all truth records).
For comparison, the 30B teacher gets 61.6% (53.1% of all truth records) and Claude Sonnet 96.9% (96.4%), so on the eligible bucket alone the student is within about 3 points of the teacher on aligned records.
The teacher aligns only 1,939 of the 2,252 records because some of its replies are invalid or cut, which is why the share of all truth records is the fairer comparison.
All three buckets are right together in only 12.1% of SFT records, against 61.0% for the teacher and 96.5% for Sonnet, and that gap is what drags the headline 10.9% ITC-exact down.
A record counts as right when all four tax heads are within Rs 0.02 of the truth.
The fix is a compact grammar that matches the training format: it makes the zero-droppable inner fields optional and keeps the top-level keys, types and reason enums.
We label that row "compact grammar" in the report, and the full-grammar row stays in as evidence of the failure.
The lesson is about structured output with small models: constrained decoding is only as good as the agreement between the grammar and what the model was trained to emit, and a grammar stricter than the training format does not catch errors, it manufactures them.
We then reran the same SFT model with that grammar on a seeded stratified sample of 42 cases (15 in-distribution, 15 out-of-distribution, 12 realworld).
On the 30 simulator cases it scores ITC-exact 75.7% [70.0, 81.5] and context accuracy 63.9% [52.5, 73.8], against 10.9% and 30.7% for the full grammar on all 120 cases; on the same 42 cases the matching grammar is 59.5 points better on ITC-exact (p = 0.0005), so the mismatch, not the model, caused the 10.9%.
On realworld (12 cases) it scores 68.8% ITC-exact and 83.3% context accuracy.
Paired on the same cases, the 30B teacher served end to end is 20.7 points lower on ITC-exact [-27.6, -14.2] and 38.3 lower on context accuracy, both p = 0.0005, so on this sample the 4B SFT student scores above the 30B teacher.
Claude Sonnet is still 24.7 points ahead on ITC-exact (+28.7 on context accuracy, n = 42), and the context-blind rules engine, which is handed the true extraction and links, is 6.7 points ahead on ITC-exact, a difference that is not significant (CI -0.6 to +14.0, p = 0.07).
What we do not claim: this is a sample of 42 and the intervals are wide, so we say "on a sample of 30 simulator cases", not "beats the teacher" in general; the teacher runs used the task prompt from before the compact-form sentence was added; the full-grammar row is format-mismatch evidence and not the SFT model's capability; and the per-record numbers above are the full-grammar run on 120 cases.
On the 30 sampled simulator cases with the matching compact grammar, the eligible bucket is exactly right in 71.6% of aligned records and all three buckets in 69.7% (full grammar on the same cases: 55.5% and 9.0%; the 30B teacher 60.9% and 59.2%, aligning only 466 of 587 records; Sonnet 98.5% and 98.1%).
Under the compact grammar blocked is nonzero in 13.7% of records and deferred in 2.2%, so the remaining error is the eligible decision and a missing deferred bucket, not junk.

## 12. What is hybrid mode, and what is your best number?

In hybrid mode the model reads one document at a time and returns its extraction plus two judgments per line (ITC category and purpose).
Deterministic code then does the matching to the register, GSTR-2B and bank, the rupee arithmetic and the ITC rules, and emits the same output scored by the same scorer.
The oracle check, true per-document records through the same code, reproduces the truth exactly on all 132 cases, so every point lost is a reading or judgment error, not a code error.
The shipped student is pd3g287: Qwen3-4B with a per-document LoRA trained on simulator rows with realistic identity formats, then 287 steps of GRPO, in this mode with reconciler v3 and doc schema v2; on the 120 simulator test cases (scored once) it reaches ITC-exact 80.0, match 85.0, context accuracy 81.5 and composite 81.6, against 80.1 ITC-exact for student-perdoc-sft under the same protocol.
Paired with student-perdoc-sft on those cases it ties on ITC exact (-0.1 [-1.5, +1.3], p = 0.92), matches 3.8 points worse (-3.8 [-4.8, -2.7], p < 0.005) and has a slightly lower composite (-1.1 [-2.1, -0.2], p = 0.02); its ITC overclaim is Rs 52,370 against Rs 26,205 (the report's overclaim column), so on simulated test cases it is not better, and our case for shipping it rests on the real documents.
The choice was a post-hoc override of our pre-registered ship rule, described in question 4 and question 14.
The rest of this answer is the ladder measured on the first per-document adapter, student-perdoc-sft (Qwen3-4B with a per-document LoRA, r 32, 124 steps, 1,984 curated rows, completion-only loss), under doc schema v1.
With reconciler v3 student-perdoc-sft scored ITC-exact 79.9% [77.5, 82.4] on the 120 simulator cases (82.5 in-distribution, 77.3 out-of-distribution), context accuracy 82.7%, composite 82.7, ITC overclaim Rs 27,183; the same replies scored 73.1%, 82.7%, 77.8 and Rs 23,757 under reconciler v2, and 62.9%, 82.7%, 73.2 and Rs 19,053 under v1.
The same model without the adapter, same prompts, code and server, gets 55.2% / 67.9% / 71.3 with Rs 85,156 overclaim under v3 (53.3% under v2, 44.3% under v1), so the adapter adds +25.9 ITC-exact points under v3 (95% CI +22.5 to +29.2, p = 0.0005, n = 132).
v2's rules came from error analysis of one demo case (examples/test_iid-hard-23-00001, seed 23, not one of the 132 evaluation cases, which use seeds 9001/9002); they were tuned and checked only on 120 train-split dev cases (71.4% to 80.1%) and frozen before the test set was re-scored once.
v3 was developed only on train-split dev cases (120 small cases and 60 larger ones, seeds 7301 and 7302), where the per-document adapter went from 80.1% to 87.8% and from 76.7% to 81.1% ITC-exact, and was frozen before the test set was re-scored once from the cached replies, with no new model calls.
That the reconciler was revised twice is why we show v1, v2 and v3 side by side and name the dev sets: the test set was touched once per version, and the rules were developed on train-split cases only (v2 was inspired by one demo case outside the evaluation set).
Overclaim rises across versions: documents that used to stay deferred for lack of a link now link, so a wrong model judgment on them (a works contract or motor vehicle line read as normal) is counted instead of being masked.
Against the 30B model run end to end (paired by case on the 120 simulator cases), the 4B per-document hybrid system under reconciler v3 is ahead on ITC-exact (+20.2 points [+16.4, +24.2]), context accuracy (+47.2 [+41.1, +53.7]) and the composite (+13.6 [+10.3, +17.6]), all p = 0.0005; it was level on ITC-exact under reconciler v1 (+3.1 [-1.6, +7.5], p = 0.18) and ahead on all three under v2 (ITC-exact +13.4).
That is a comparison of systems, not of models: the 4B system has deterministic code doing the matching and the 30B model does not.
On the 12 real-world sanity cases it scores 81.9% under v2 and v3 (76.4% under v1) against 97.2% for Claude Sonnet in the same mode, so we are still far behind the frontier.
Against the same model fine-tuned and run end to end with the matching compact grammar, paired by case on the 42 shared cases (30 simulator, 12 realworld), the per-document hybrid under v3 ties on ITC-exact (+5.9 points [-1.8, +13.2], p = 0.11, not significant), is clearly ahead on context accuracy (+20.7 [+11.6, +30.5], p = 0.0005) and level on the composite (+2.5 [-1.1, +6.2]).
It overclaims about 9 times less ITC (Rs 33,706 per case against Rs 317,078, p = 0.002) but is more conservative: it underclaims Rs 102,274 per case against Rs 13,922 (p = 0.014), so it leaves more eligible ITC unclaimed.
What we do not claim: that hybrid mode beats end-to-end SFT on ITC-exact, because that difference is not significant on a 42-case sample; the hybrid's clear gain is context accuracy, and code, not the model, does the rupee arithmetic; these hybrid rows are not like-for-like with the end-to-end rows of the 30B teacher and Sonnet, because code does part of the work; the reconciler was revised twice (v1 to v2 to v3) and all three are reported; and throughput is slightly understated because a demo recording shared the server for the first four minutes (reconciler v2 reuses the same model replies, so its throughput is the v1 figure).

## 13. Isn't this mostly deterministic rules? Why not OCR plus rules?

The law is deterministic on purpose, and the model does only what rules cannot do.
The 4B model reads each messy document (scan OCR, WhatsApp or email text) into a typed record and judges, per line, the item category and the business purpose in the buyer's context.
Code parses the already structured books (purchase register, GSTR-2B, bank statement), links them to the documents, and applies the statute (sections 16(2) and 17(5), rules 36 and 37) and the rupee arithmetic.
That keeps the part that must be auditable fixed and testable, and gives perception and judgment to the model.
Here is what we measured on the 120 simulator cases, each row in `reports/hybrid.md` or `reports/results.md`.
First, OCR plus regex extraction plus the same reconciler, with no model, is the "heuristic hybrid (code alone)" row: ITC invoice exact 10.4% [8.8, 12.1] under reconciler v1 and 11.1% [9.5, 12.7] under v3 (re-scored once from the same cached extractions), with context accuracy 40.9% [34.7, 46.3] under both.
Second, the base 4B model in the same hybrid mode ("student-base hybrid") scores 44.3% under reconciler v1 and 55.2% [51.9, 58.6] under v3, and the fine-tuned per-document 4B ("student-perdoc-sft hybrid") scores 62.9% [60.2, 65.3] under v1 and 79.9% [77.5, 82.4] under v3, with context accuracy 82.7% [79.3, 85.8] under both.
So like for like the ladder is 10.4, 44.3, 62.9 ITC-exact under reconciler v1 and 11.1, 55.2, 79.9 under v3 (code alone, base 4B, per-document 4B), and the model, not the rules, is what moves it.
Third, the rule baselines in `reports/results.md` are handed the true extraction and the true document links, which a real deployment never has, so only their decisions are comparable: "keyword (oracle extraction and links)" (naive Bayes on line descriptions, no buyer context) scores ITC-exact 71.6% [68.9, 74.2] with context accuracy 48.1% [43.7, 52.4], and "context-blind rules (oracle extraction and links)" (the real rules engine without the buyer profile or remarks) scores 82.7% [80.4, 85.0] with context accuracy 50.1% [44.9, 55.6].
We say plainly that on ITC-exact alone the context-blind engine given perfect extraction is ahead of our system (82.7% against 80.0% for the shipped pd3g287, 79.9% for student-perdoc-sft), because most invoices do not depend on the buyer.
Where the answer depends on who is buying, the same item can be blocked for one buyer and eligible for another (the caterer example in the demo), the rule baselines reach 48 to 50% and our system reaches 81.5% (82.7% for student-perdoc-sft).
That context accuracy gap is the case for a model, and the code-alone floor shows what happens when reading the documents is left to regex.
Last, the reconciler fixes in versions 2 and 3 are ordinary matching logic (check-digit validation of GSTINs, unique-match filling of fields the OCR did not show, no invoice-number veto on GSTR-2B links), each checked against an oracle that reproduces the truth on all 132 test cases and all 120 small dev cases (58 of 60 on the larger dev set, the same two misses under every reconciler version: a payment-tie ambiguity).
What we do not claim: that the 4B system is more accurate than a rules engine that is given perfect inputs on every metric; the claim is that it must read the documents itself and judge context, and that it does both better than the alternatives we measured.

## 14. Did you test on real invoices?

Yes, on a small eval-only set, and the result is mixed, which is why we report it.
We took 42 real purchase documents of one buyer, labelled them with a strong model from the page images with automatic arithmetic and GSTIN checks (not human verified), and never trained on them; the documents and labels are client data and stay private, so only aggregates are published.
The model sees OCR output, and only 26 of 39 printed supplier GSTINs, 33 of 42 invoice numbers and 28 of 42 dates survive into that text, so part of every error is OCR loss.
Reading the documents one at a time, the first fine-tuned per-document model (student-perdoc-sft) reads amounts, categories and purposes better than the base model (ITC document exact 57.1% against 42.9%), but it reads invoice numbers and dates much worse (invoice number 30.9% against 52.4%).
The cause is that it invents rather than abstains: of its 29 wrong invoice numbers, 23 are not in the document text and 18 use the simulator's own number formats, so the simulator taught it identity formats that our simulated test set cannot reveal.
GRPO from that adapter (step 75) made the invention worse, not better.
We diversified the simulator's invoice-number and date formats, designed from CGST Rule 46 (at most 16 characters; letters, digits, hyphen and slash; unique per financial year) and general Indian invoicing practice, and not from the real invoices, which nobody opened for this.
We retrained two per-document adapters on it (per-doc SFT with realistic identity formats, and per-doc SFT with realistic formats that abstains when an identity field is not visible), and set a ship rule before their final numbers (`reports/hybrid.md`).
The real-invoice eval exposed an overfit to simulator identity formats; we fixed it in the simulator from CGST Rule 46 without using those invoices and retrained, and the retrained adapters no longer write the simulator-format wrong invoice numbers that student-perdoc-sft wrote.
The numbers: student-perdoc-sft writes 18 of its 29 wrong invoice numbers in the simulator's formats, the retrained adapters write none (0 of 21 and 0 of 10), and invoice-number accuracy rises from 30.9% to 47.6% for the realistic-formats adapter.
The result is mixed: ITC document exact on the real set does not improve (50.0% for the realistic-formats adapter, a tie at 57.1% for the abstaining one), and on the simulated dev sets the retrained adapters trail student-perdoc-sft by 1 to 5 ITC-exact points, past the pre-registered non-inferiority bound (a lower bound of -3.0 points; -4.5 on the small set for pd3g287).
The abstaining adapter invents 3.5% of identity fields against 8.8%, but leaves 16 visible ones empty, and the GRPO variant over-abstains (invoice number 21.4%).
A field-wise vote of three adapters (ensemble B, with the GRPO adapter as tie-breaker) invents no identity and ties on real-document ITC document exact, which is structural because it takes every ITC judgment from the shipped adapter.
After seeing that, the user amended the ship rule for that ensemble, and we say so: it would ship if it was at least as good as student-perdoc-sft on ITC exact and on match accuracy pooled over 54 real-document cases with simulated books, a criterion fixed before any of its numbers existed (`reports/hybrid.md`).
It was not: ITC-exact 58.3% against 58.5% (-0.2 [-1.0, +0.8], p = 0.62), although it matches 5.6 points better, so the ensemble does not ship.
On those 54 cases every retrained adapter links documents to the books 6 to 7 points better than student-perdoc-sft end to end (match accuracy +7.2 [+1.9, +12.9] for realistic formats, +7.4 [+1.4, +13.7] for its GRPO variant, +6.1 [+0.2, +12.4] for the abstaining one), with every identity fill correct and no false link, so the fix pays off end to end even though it did not clear the simulated-dev bound.
The GRPO variant, pd3g287, was the strongest model there (composite +4.3 [+1.7, +7.0]; ITC-exact +2.6 [-1.4, +6.7], not significant) and invents no identity field on the real documents, but it failed the pre-registered dev bound on the small simulated set, whose identity formats student-perdoc-sft was trained on.
We chose it by a post-hoc override, and we say so plainly.
Our pre-registered ship rule said no, because it regressed on simulated dev (small-dev ITC-exact delta -1.7, 95% CI [-4.5, +0.9], against a required lower bound of -3.0).
We overrode the rule after the fact because real documents are what matter: on the 54 pooled real-document cases (semireal, books simulated) it is the best model end to end, with composite +4.3 [+1.7, +7.0], match accuracy +7.4 [+1.4, +13.7] and ITC-exact +2.6 [-1.4, +6.7], not significant.
The simulated dev sets use the old simulator formats, which this model was not trained on.
The override was committed before the test set was run.
It over-abstains: it left 22 visible identity fields empty on the 42 real documents and 16 visible invoice numbers empty on the 30 held-out ones, with invoice-number accuracy 21.4% and 30.0% against 30.9% and 40.0% for student-perdoc-sft.
The next round is to re-validate with a dev set in the new formats.
The books in that set are simulated and the labels were drafted by a model, so this is a real-document reading result, not a real-world book result.
We then labelled 30 fresh real invoices from 30 other suppliers, never used for selection, and scored both models once: pd3g287 gets GSTIN 73.3%, invoice number 30.0%, date 60.0%, ITC document exact 60.0% and invents no identity field; student-perdoc-sft gets 73.3%, 40.0%, 46.7%, 70.0% and 2.6%, with 10 of its 18 wrong invoice numbers in simulator formats.
The realistic-formats adapter without GRPO reads invoice numbers best there (76.7%, none of its wrong numbers in simulator formats), and the GRPO stage trades that away for abstention.
That check is small and labelled by a model, not by a human, so read it as a failure analysis and not as a real-world accuracy figure.
We also capped invoice numbers at 16 characters in the decoding grammar (the Rule 46 limit), because the first retrained adapter looped inside the invoice-number string on 81 of 384 replies without it; on student-perdoc-sft the cap changes nothing (ITC invoice exact 87.9% against 87.8% on small dev).
Feeding the same documents through the full reconciliation (nine buyer-month cases with books generated by the simulator), the reconciler's identity fill worked: every fill was correct (43 of 43 for the fine-tuned model) and no run made a false link, and ITC-exact was 59.6% (clean) and 58.6% (with planted discrepancies) for the fine-tuned model against 42.5% and 46.0% for the base.
What we do not claim: a real-world accuracy figure for the whole system, because the books in that set are simulated, no line in it is blocked under s.17(5) so it does not test blocking judgment, the labels are not human verified, and the set is 42 documents.
