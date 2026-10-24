# gst-recon

Local LLM that reconciles Indian GST input tax credit from messy documents. Syntax Error 2026, Local LLM track.

Repository: https://github.com/chayan-bit/gst-recon-agent

## Results

Full-reconciliation numbers only: every row is the whole pipeline scored end to end by the same scorer.

| System | Test ITC exact | Test match | Test composite | Semireal ITC exact | Semireal match | Semireal composite |
|---|---|---|---|---|---|---|
| pd3g287 (shipped): per-document model + our reconciler | 80.0 | 85.0 | 81.6 | 61.1 | 71.5 | 72.9 |
| student-perdoc-sft (v1): first per-document model + our reconciler | 80.1 | 88.7 | 82.8 | 58.5 | 64.1 | 68.6 |
| Claude Haiku 5.5, same hybrid harness (one call per document + our reconciler); minimum thinking (mean {{HAIKU_THINK_TOKENS}} tokens per document), cannot be disabled via the CLI | {{HAIKU_TEST_ITC}} | {{HAIKU_TEST_MATCH}} | {{HAIKU_TEST_COMP}} | 84.9 | 88.4 | 86.5 |
| Claude Haiku 4.5, same hybrid harness (one call per document + our reconciler); thinking off (0 thinking tokens) | {{HAIKU45_TEST_ITC}} | {{HAIKU45_TEST_MATCH}} | {{HAIKU45_TEST_COMP}} | 68.2 | 82.2 | 77.4 |
| GPT-6 luna, same hybrid harness (one call per document + our reconciler); lowest reasoning effort | 81.9 | 90.5 | 84.0 | 70.6 | 82.5 | 77.9 |
| Claude Sonnet, whole case in one prompt (a different harness; thinking at CLI default) | 96.3 | 99.0 | 94.4 | not run | not run | not run |

Test is the 120 simulator test cases; semireal is 54 cases built around real documents with simulated purchase register, GSTR-2B and bank books, pooled, so it measures document reading and not real book messiness, and its labels were drafted by a model and not verified by a human.
ITC exact is the share of invoices whose eligible, blocked and deferred amounts are all within Rs 1 of the truth; match is match accuracy; composite is the weighted composite, which has a high floor.
pd3g287 and student-perdoc-sft run under reconciler v3 and doc schema v2, and their test rows were scored once.
On the test set pd3g287 ties student-perdoc-sft on ITC exact (80.0 against 80.1) and matches 3.8 points worse (85.0 against 88.7, composite 81.6 against 82.8); on the semireal real documents it is ahead on all three, significantly on match and composite.
On the semireal real documents the readers with no test-time compute lead our shipped model: Haiku 5.5 at minimum thinking by 13.6 composite points, GPT-6 luna by 5.0 (significant) and Haiku 4.5 by 4.5 (p = 0.068, not significant); our model's case rests on running locally on one 16 GB GPU, with no document leaving the machine. On the 120 simulator test cases luna also leads pd3g287 (ITC exact +1.9, not significant; match +5.6 and composite +2.4, both significant). On the same documents it also invents fewer identity fields than the two small readers (9.7% of identity slots against 16.6% for Haiku 4.5 and 15.4% for luna), a diagnostic and not a headline.
Sonnet ran through the Claude Code CLI with the whole case in one prompt, so its row is a different harness and not a like-for-like comparison with the hybrid rows.
No model gets test-time compute beyond what its harness cannot remove: our 4B (Qwen3-4B-Instruct-2507) has no thinking mode and its output is XGrammar-constrained to start with `{`, Haiku 4.5 runs with thinking off, GPT-6 luna at the lowest reasoning effort, and Haiku 5.5 cannot disable thinking through the Claude Code CLI, so its row is at minimum thinking.
Sonnet's whole-case run used the Claude Code CLI defaults, and its report does not record the thinking setting, so we say thinking at CLI default.
For scale, a context-blind rules engine handed the true extraction and links scores 82.7 ITC exact, 100.0 match and 87.3 composite on the same test cases: on ITC exact alone it is ahead of our system, and what the model adds is reading the documents and judging context.
The shipped system is pd3g287: Qwen3-4B-Instruct-2507 with a per-document LoRA trained on simulator rows with realistic identity formats, then 287 steps of GRPO with the per-document reward, run in hybrid mode (the model reads one document at a time and deterministic code does the matching, rupee arithmetic and ITC rules) with reconciler v3 and doc schema v2.
We chose it by a post-hoc override, and we say so plainly. Our pre-registered ship rule said no, because it regressed on simulated dev (small-dev ITC exact delta -1.7, 95% CI [-4.5, +0.9], against a required lower bound of -3.0). We overrode the rule after the fact because real documents are what matter: on the 54 pooled semireal cases it is the best model end to end (composite +4.3 [+1.7, +7.0], match +7.4 [+1.4, +13.7], ITC exact +2.6 [-1.4, +6.7], not significant), and the simulated dev sets use the old simulator formats, which this model was not trained on. The override was committed before the test set was run. It over-abstains: it left 22 visible identity fields empty on the 42 real documents and 16 visible invoice numbers empty on the 30 held-out ones (counts in `reports/hybrid.md`).
GRPO: the first run (step 75, from the second per-document adapter) was neutral on the dev sets and was not shipped; the second run, from the realistic-formats adapter, is the shipped pd3g287, by the override above; the AlignTune SGLang rollout backend we built for GRPO is upstream (PR #32) as infrastructure, not as a headline gain.
Per-field accuracy, dev sets, per-document scores on real invoices, schema-valid rates, decoding ablations and every paired test are in `reports/hybrid.md`, `reports/results.md` and `reports/pipeline.md`.

## Weights and data

- LoRA adapters for Qwen3-4B-Instruct-2507 (Apache-2.0): https://huggingface.co/broman23/gst-recon-qwen3-4b-adapters
- Simulator-generated training and eval data (Apache-2.0, synthetic only): https://huggingface.co/datasets/broman23/gst-recon-synthetic

## License

GPL-3.0-only; see `LICENSE`.
The upstream invoice print formats vendored unchanged in `realworld/formats/vendor/` keep their own licences (GPL-3.0, LGPL-3.0 and MIT, listed in `realworld/PROVENANCE.md`), and the templates ported from them in `realworld/formats/` are derivative works distributed under GPL-3.0.
