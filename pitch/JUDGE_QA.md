# Judge Q&A: the hardest questions, with honest answers

Rule for every answer: say what was measured, say what was not, and never reach past the evidence.
Placeholders `{{...}}` are filled from `NUMBERS.md`; if one is still empty when you present, say "not measured yet" and move on.

## 1. Isn't this sim-to-sim? You train and test on your own simulator.

Yes, the training data and the main evaluation come from the same simulator, and the headline numbers are not evidence that it works on real company data.
What the simulator buys is a checkable truth: every answer is verified by code, which is what makes a verifiable reward possible at all, and a real invoice archive has no ground truth for ITC.
Three things keep it from being a closed loop.
First, the documents are rendered, degraded (rotation, blur, JPEG, folds, photocopy and fax effects, stamps) and read by real Tesseract, so the text the model sees carries real OCR noise, not generated noise.
Second, the out-of-distribution split holds out 20 of the 84 item concepts, two invoice layouts, three buyer profiles, a quarter of the states, and number and date formats, so the test measures generalisation within the simulator's world.
Third, a small real-world sanity set built from public sample invoice formats (36 documents) is reported separately: schema-valid {{REAL_SCHEMA_VALID}}, field F1 {{REAL_FIELD_F1}}.
What we do not claim: that the ITC decisions are right on real books, only that the pipeline, the metrics and the generalisation tests are sound.

## 2. Why not just call GPT or Claude?

For this data, privacy decides: purchase invoices, bank statements and supplier GSTINs are the data a business cannot send to a third-party API, and an on-premises model removes that question.
Cost and latency at month-end volume are the second reason: {{Z_COST_PCT}}% of Sonnet's cost per 1,000 cases and a p50 of {{STUDENT_P50_LATENCY_S}} s (see question 6 for how fair that comparison is).
We are not claiming the small model is better: Claude Sonnet scores 97.8% ITC-exact on the same held-out cases against our {{GRPO_ITCEXACT_OOD}}, so the student reaches {{Y_PCT_OF_SONNET_ACCURACY}}% of it.
A private deployment of a hosted model is another way to meet a privacy requirement; we did not test that, and a team that can use one should compare it.

## 3. How do you know your GST law is right?

We do not know it is complete, and we do not claim legal review we have not had (review status: rules encoded by the author from CGST Act sections 16(2), 17(5) and 34 and rules 36(4) and 37, with Circular 172/04/2022; not yet reviewed by a practising CA).
What exists is a written, cited model of the law in `gst_recon/sim/RULES.md`: sections 16(2), 17(5), 34, rule 36(4), rule 37, the reverse-charge treatment and the 17(5) exceptions, with the circular that supports each exception.
The rules engine is a deliberate model, and every simplification is listed there (for example, no Section 17(2) apportionment, canteen credit assumes the employer bears the full cost).
Rates are date-effective across the 22 September 2025 GST 2.0 change, and any rate we could not verify is never generated after the cutover.
Tests assert invariants such as every rupee of tax landing in exactly one of eligible, blocked and deferred.
If the model of the law is wrong, the student faithfully learns the error, but the rule table is data in one place: fix it, regenerate, retrain.

## 4. What does GRPO add over SFT?

(Before the GRPO numbers: the best measured student today is the per-document hybrid described in question 12.)


SFT teaches the model to imitate a reference answer token by token, which is how it learns the format and the common patterns.
GRPO samples several answers to the same case and rewards the outcome we care about, which code can check exactly: schema validity, flag and reason-code sets, and exact ITC on the invoices that are not fully eligible, with a dense term so partial progress still counts.
The hypothesis is that this helps most where imitation is weak: context-dependent blocked credits and exact amounts.
The measured effect on ITC-exact out-of-distribution is {{GRPO_DELTA_VS_SFT_ITCEXACT_OOD}} points (95% CI {{GRPO_VS_SFT_CI}}, p = {{GRPO_VS_SFT_P}} from a paired bootstrap), and on context accuracy it is 33.2% (the full-grammar SFT run, a format mismatch) -> {{GRPO_CTX_OOD}}.
If that interval includes zero we say GRPO did not help on that metric, and we show where it did.
One limit we know about: our GRPO cases are short (2 to 4 invoices, prompts up to 6,144 tokens).
One thing we checked rather than assumed: both SFT runs used completion-only loss, with every prompt token labelled -100 so the model is trained on its reply only.
The end-to-end run used unsloth's responses-only masking, verified on the first curated row with the real Qwen3 tokenizer before launch.
The per-document run uses TRL's prompt/completion masking, and its runner aborts before step 1 unless the prompt is a fully masked prefix (first row: 1,235 prompt tokens masked, 224 reply tokens trained).
That check caught an earlier attempt in which AlignTune's data normaliser had turned the rows into full-sequence messages, so no full-sequence step was trained.

## 5. What breaks on real scans?

A text-only model cannot recover what the OCR lost, and we measure that instead of hiding it: each case records `ocr_recall`, and the facts that are unrecoverable from the OCR text (in the committed hard example, line HSN codes on five of 13 documents).
In training, a target HSN that OCR lost is blanked rather than demanded as a guess.
On real scans we expect these failure modes, in roughly this order: handwriting, photographs taken at an angle or with shadows, multi-page tables, mixed-language text, and digits confused by OCR (in one committed case OCR turned the I in a supplier GSTIN into a 1, and the model has to repair it against the register and the 2B).
Results by OCR-recall bucket are in the report: composite on full-recall versus partial-recall cases is {{COMPOSITE_FULL_OCR}} versus {{COMPOSITE_PARTIAL_OCR}}, and on the real-format sanity set field F1 is {{REAL_FIELD_F1}}.
The fix we would build next is a vision-language student that reads the page directly.

## 6. You say 'Y% of Sonnet at Z% of the cost and latency'. Is that comparison fair?

Partly, and the caveats are on the slide.
The Sonnet baseline runs through the Claude Code CLI because there is no API key: each case is one non-interactive call with the schema in the system prompt and no constrained decoding, at concurrency 2.
Its cost is list-price arithmetic from token counts, and its latency includes CLI overhead, so the latency ratio overstates the gap and should be read as an upper bound.
The student's GPU cost is measured wall time times an hourly price we choose ({{GPU_HOUR_USD}} dollars per hour here), assuming a saturated GPU; at low utilisation the per-case cost is higher.
Accuracy is scored by the same code on the same cases for every model, and failed or truncated outputs count as wrong for everyone.
The claim we stand behind is the ratio of accuracy on the same held-out cases, plus the fact that nothing left the machine.

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
On the student, between unconstrained and constrained decoding: schema-valid {{GRPO_SCHEMA_VALID_UNCON}}% -> {{GRPO_SCHEMA_VALID_CON}}% and ITC-exact {{GRPO_ITCEXACT_UNCON}} -> {{GRPO_ITCEXACT_CON}}.
Constrained output can also be cut off by the token budget, which leaves it unfinished; the harness counts truncations and context overflows as failures instead of discarding them, and the overhead of constraining on throughput is {{XGRAMMAR_OVERHEAD_PCT}}%.
The point of the grammar is operational: downstream code can parse every answer and the reward function always has something to score.

## 9. Is SGLang really in your training loop, and are the sponsor contributions merged?

Be precise here, because the answer has three parts.
SGLang is the engine for teacher generation, serving and evaluation, and that is measured and logged.
The SGLang rollout backend for GRPO exists as AlignTune pull request #32 (open) with CPU tests and a GPU integration test, but it is wired into AlignTune's TRL GRPO trainer, while the unsloth backend ignores `rollout_backend`.
Our only GRPO config (`configs/grpo_sglang.yaml`) uses the TRL backend with `rollout_backend: sglang`, and the GRPO runner refuses to start without it, so a GRPO run cannot silently fall back to Hugging Face generation.
That the final run did generate its rollouts on SGLang is confirmed by `{{GRPO_ROLLOUT_BACKEND_ACTUALLY_USED}}` in its training log; until that run exists we present the backend as a contribution with its measured benchmark, not as how this model was trained.
The backend was developed against SGLang 0.5.22, and the training host runs SGLang 0.5.10.post1 because of its CUDA driver, so compatibility on that version is a separate check (result: {{SGLANG_0510_COMPAT}}).
On merging: they are open pull requests (AuditKIT #9, #10, #11, CuratorKIT #34, #35, #36, AlignTune #32, #33, #34, #35, SGLang #46287), eleven in all and none merged at the time of writing.

## 10. Your test cases are much longer than your training cases. Why should it work?

It may not, and that is a measured axis, not a hidden assumption.
Training cases are deliberately short so they fit the hardware: SFT cases have 3 to 6 invoices and fit 12k tokens in total, GRPO cases have 2 to 4 invoices with prompts up to 6,144 tokens and 4,096 completion tokens, while evaluation cases have 5 to 12 documents (easy), 10 to 25 (medium) and 20 to 40 (hard), up to tens of thousands of prompt tokens plus thousands of output tokens.
So even the easy evaluation cases are larger than most training cases.
The evaluation keeps the full difficulty sizes on purpose, and the report breaks results down by prompt length (up to 16k, 16 to 32k, over 32k tokens) and by difficulty.
Results by length: ITC-exact {{ITCEXACT_LEN_LE16K}} up to 16k tokens, {{ITCEXACT_LEN_16_32K}} for 16 to 32k, {{ITCEXACT_LEN_GT32K}} above 32k.
The student is served at a context of {{STUDENT_CONTEXT_LEN}} tokens, and {{N_CONTEXT_OVERFLOW_STUDENT}} cases overflowed it; those count as failures.
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
What we do not claim: the compact-grammar rerun is pending, so we say "not measured yet" for it and do not quote the full-grammar row as the SFT model's capability; and the student is far behind Sonnet, which is why the eligible-bucket parity with the teacher is not the headline.

## 12. What is hybrid mode, and what is your best number?

In hybrid mode the model reads one document at a time and returns its extraction plus two judgments per line (ITC category and purpose).
Deterministic code then does the matching to the register, GSTR-2B and bank, the rupee arithmetic and the ITC rules, and emits the same output scored by the same scorer.
The oracle check, true per-document records through the same code, reproduces the truth exactly on all 132 cases, so every point lost is a reading or judgment error, not a code error.
Our best measured student is Qwen3-4B with a per-document LoRA (r 32, 124 steps, 1,984 curated rows, completion-only loss) in this mode.
With reconciler v3 it scores ITC-exact 79.9% [77.5, 82.4] on the 120 simulator cases (82.5 in-distribution, 77.3 out-of-distribution), context accuracy 82.7%, composite 82.7, ITC overclaim Rs 27,183; the same replies scored 73.1%, 82.7%, 77.8 and Rs 23,757 under reconciler v2, and 62.9%, 82.7%, 73.2 and Rs 19,053 under v1.
The same model without the adapter, same prompts, code and server, gets 55.2% / 67.9% / 71.3 with Rs 85,156 overclaim under v3 (53.3% under v2, 44.3% under v1), so the adapter adds +25.9 ITC-exact points under v3 (95% CI +22.5 to +29.2, p = 0.0005, n = 132).
v2's rules came from error analysis of one demo case (examples/test_iid-hard-23-00001, seed 23, not one of the 132 evaluation cases, which use seeds 9001/9002); they were tuned and checked only on 120 train-split dev cases (71.4% to 80.1%) and frozen before the test set was re-scored once.
v3 was developed only on train-split dev cases (120 small cases and 60 larger ones, seeds 7301 and 7302), where the per-document adapter went from 80.1% to 87.8% and from 76.7% to 81.1% ITC-exact, and was frozen before the test set was re-scored once from the cached replies, with no new model calls.
That the reconciler was revised twice is why we show v1, v2 and v3 side by side and name the dev sets: the test set was touched once per version, and the rules were developed on train-split cases only (v2 was inspired by one demo case outside the evaluation set).
Overclaim rises across versions: documents that used to stay deferred for lack of a link now link, so a wrong model judgment on them (a works contract or motor vehicle line read as normal) is counted instead of being masked.
Against the 30B model run end to end (paired by case on the 120 simulator cases), the 4B per-document hybrid system under reconciler v3 is ahead on ITC-exact (+20.2 points [+16.4, +24.2]), context accuracy (+47.2 [+41.1, +53.7]) and the composite (+13.6 [+10.3, +17.6]), all p = 0.0005; it was level on ITC-exact under reconciler v1 (+3.1 [-1.6, +7.5], p = 0.175) and ahead on all three under v2 (ITC-exact +13.4).
That is a comparison of systems, not of models: the 4B system has deterministic code doing the matching and the 30B model does not.
On the 12 real-world sanity cases it scores 81.9% under v2 and v3 (76.4% under v1) against 97.2% for Claude Sonnet in the same mode, so we are still far behind the frontier.
What we do not claim: these hybrid rows are not like-for-like with the end-to-end rows of the 30B teacher and Sonnet, because code does part of the work; the reconciler was revised twice (v1 to v2 to v3) and all three are reported; and throughput is slightly understated because a demo recording shared the server for the first four minutes (reconciler v2 reuses the same model replies, so its throughput is the v1 figure).

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
We say plainly that on ITC-exact alone the context-blind engine given perfect extraction is ahead of our system (82.7% against 79.9%), because most invoices do not depend on the buyer.
Where the answer depends on who is buying, the same item can be blocked for one buyer and eligible for another (the caterer example in the demo), the rule baselines reach 48 to 50% and our system reaches 82.7%.
That context accuracy gap is the case for a model, and the code-alone floor shows what happens when reading the documents is left to regex.
Last, the reconciler fixes in versions 2 and 3 are ordinary matching logic (check-digit validation of GSTINs, unique-match filling of fields the OCR did not show, no invoice-number veto on GSTR-2B links), each checked against an oracle that reproduces the truth on all 132 test cases and all 120 small dev cases (58 of 60 on the larger dev set, the same two misses under every reconciler version: a payment-tie ambiguity).
What we do not claim: that the 4B system is more accurate than a rules engine that is given perfect inputs on every metric; the claim is that it must read the documents itself and judge context, and that it does both better than the alternatives we measured.
