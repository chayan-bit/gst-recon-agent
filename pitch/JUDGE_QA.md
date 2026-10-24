# Judge Q&A: the ten hardest questions, with honest answers

Rule for every answer: say what was measured, say what was not, and never reach past the evidence.
Placeholders `{{...}}` are filled from `NUMBERS.md`; if one is still empty when you present, say "not measured yet" and move on.

## 1. Isn't this sim-to-sim? You train and test on your own simulator.

Yes, the training data and the main evaluation come from the same simulator, and the headline numbers are not evidence that it works on real company data.
What the simulator buys is a checkable truth: every answer is verified by code, which is what makes a verifiable reward possible at all, and a real invoice archive has no ground truth for ITC.
Three things keep it from being a closed loop.
First, the documents are rendered, degraded (rotation, blur, JPEG, folds, photocopy and fax effects, stamps) and read by real Tesseract, so the text the model sees carries real OCR noise, not generated noise.
Second, the out-of-distribution split holds out 20 of the 84 item concepts, two invoice layouts, three buyer profiles, a quarter of the states, and number and date formats, so the test measures generalisation within the simulator's world.
Third, a small real-world sanity set built from public sample invoice formats ({{REAL_N_DOCS}} documents) is reported separately: schema-valid {{REAL_SCHEMA_VALID}}, field F1 {{REAL_FIELD_F1}}.
What we do not claim: that the ITC decisions are right on real books, only that the pipeline, the metrics and the generalisation tests are sound.

## 2. Why not just call GPT or Claude?

For this data, privacy decides: purchase invoices, bank statements and supplier GSTINs are the data a business cannot send to a third-party API, and an on-premises model removes that question.
Cost and latency at month-end volume are the second reason: {{Z_COST_PCT}}% of Sonnet's cost per 1,000 cases and a p50 of {{STUDENT_P50_LATENCY_S}} s (see question 6 for how fair that comparison is).
We are not claiming the small model is better: Claude Sonnet scores {{SONNET_ITCEXACT_OOD}} ITC-exact on the same held-out cases against our {{GRPO_ITCEXACT_OOD}}, so the student reaches {{Y_PCT_OF_SONNET_ACCURACY}}% of it.
A private deployment of a hosted model is another way to meet a privacy requirement; we did not test that, and a team that can use one should compare it.

## 3. How do you know your GST law is right?

We do not know it is complete, and we do not claim legal review we have not had (review status: {{CA_REVIEW_STATUS}}).
What exists is a written, cited model of the law in `gst_recon/sim/RULES.md`: sections 16(2), 17(5), 34, rule 36(4), rule 37, the reverse-charge treatment and the 17(5) exceptions, with the circular that supports each exception.
The rules engine is a deliberate model, and every simplification is listed there (for example, no Section 17(2) apportionment, canteen credit assumes the employer bears the full cost).
Rates are date-effective across the 22 September 2025 GST 2.0 change, and any rate we could not verify is never generated after the cutover.
Tests assert invariants such as every rupee of tax landing in exactly one of eligible, blocked and deferred.
If the model of the law is wrong, the student faithfully learns the error, but the rule table is data in one place: fix it, regenerate, retrain.

## 4. What does GRPO add over SFT?

SFT teaches the model to imitate a reference answer token by token, which is how it learns the format and the common patterns.
GRPO samples several answers to the same case and rewards the outcome we care about, which code can check exactly: schema validity, flag and reason-code sets, and exact ITC on the invoices that are not fully eligible, with a dense term so partial progress still counts.
The hypothesis is that this helps most where imitation is weak: context-dependent blocked credits and exact amounts.
The measured effect on ITC-exact out-of-distribution is {{GRPO_DELTA_VS_SFT_ITCEXACT_OOD}} points (95% CI {{GRPO_VS_SFT_CI}}, p = {{GRPO_VS_SFT_P}} from a paired bootstrap), and on context accuracy it is {{SFT_CTX_OOD}} -> {{GRPO_CTX_OOD}}.
If that interval includes zero we say GRPO did not help on that metric, and we show where it did.
Two limits we know about: our GRPO cases are short (2 to 4 invoices, prompts up to 6,144 tokens), and AlignTune's unsloth SFT path computes the loss over the prompt as well as the answer.

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
Our `context_blind` baseline (the real rules engine, given perfect document comparison, but no buyer profile and no remarks) shows how much a shortcut gets: ITC-exact {{CONTEXT_BLIND_ITC_EXACT}} and context accuracy {{CONTEXT_BLIND_CTX}}.
Twenty concepts and a quarter of the phrasings of the rest are held out entirely.
`tests/test_splits.py` asserts that no description, concept, remark, header, profile, state or name token of a test split appears in train, the eval sets are frozen by hash manifest, and training builders refuse any path under the evaluation output.
Not yet shown: that it generalises to concepts far outside the 84; the held-out 20 are in the same families.

## 8. Doesn't constrained decoding just hide errors behind valid JSON?

It guarantees the syntax and the schema, not the content, and a grammar can force a well-formed but wrong value.
That is why validity is reported separately from correctness, and why the table shows both: schema-valid {{GRPO_SCHEMA_VALID_UNCON}}% -> {{GRPO_SCHEMA_VALID_CON}}% and ITC-exact {{GRPO_ITCEXACT_UNCON}} -> {{GRPO_ITCEXACT_CON}} between unconstrained and constrained decoding on the student.
Constrained output can also be cut off by the token budget, which leaves it unfinished; the harness counts truncations and context overflows as failures instead of discarding them, and the overhead of constraining on throughput is {{XGRAMMAR_OVERHEAD_PCT}}%.
The point of the grammar is operational: downstream code can parse every answer and the reward function always has something to score.

## 9. Is SGLang really in your training loop, and are the sponsor contributions merged?

Be precise here, because the answer has three parts.
SGLang is the engine for teacher generation, serving and evaluation, and that is measured and logged.
The SGLang rollout backend for GRPO exists on our AlignTune fork branch with CPU tests and a GPU integration test, but it is wired into AlignTune's TRL GRPO trainer, while the unsloth backend ignores `rollout_backend`.
Our GRPO config starts on the unsloth backend with Hugging Face rollouts, so the statement "our GRPO run generated rollouts on SGLang" is true only if `{{GRPO_ROLLOUT_BACKEND_ACTUALLY_USED}}` says so; if it says hf, we present the backend as a contribution and its measured benchmark, not as how this model was trained.
The backend was developed against SGLang 0.5.22, and the training host runs SGLang 0.5.10.post1 because of its CUDA driver, so compatibility on that version is a separate check (result: {{SGLANG_0510_COMPAT}}).
On merging: these are fork branches and issue drafts, not merged upstream, and the status line says exactly that ({{UPSTREAM_STATUS}}).

## 10. Your test cases are much longer than your training cases. Why should it work?

It may not, and that is a measured axis, not a hidden assumption.
Training cases are deliberately short so they fit the hardware: SFT cases have 3 to 6 invoices and fit 12k tokens in total, GRPO cases have 2 to 4 invoices with prompts up to 6,144 tokens and 4,096 completion tokens, while evaluation cases have 5 to 12 documents (easy), 10 to 25 (medium) and 20 to 40 (hard), up to tens of thousands of prompt tokens plus thousands of output tokens.
So even the easy evaluation cases are larger than most training cases.
The evaluation keeps the full difficulty sizes on purpose, and the report breaks results down by prompt length (up to 16k, 16 to 32k, over 32k tokens) and by difficulty.
Results by length: ITC-exact {{ITCEXACT_LEN_LE16K}} up to 16k tokens, {{ITCEXACT_LEN_16_32K}} for 16 to 32k, {{ITCEXACT_LEN_GT32K}} above 32k.
The student is served at a context of {{STUDENT_CONTEXT_LEN}} tokens, and {{N_CONTEXT_OVERFLOW_STUDENT}} cases overflowed it; those count as failures.
If the numbers drop sharply with length, the honest summary is that the system works on small and medium month-ends today and that long ones need longer-case training.
