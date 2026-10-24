## Frontier per-document models (same harness, only the per-document call differs)

Each model replaces the per-document call of the shipped pipeline and nothing else: the same per-document messages, doc schema v2, reconciler v3, fill, linker and scorer, the same case lists (semireal 54 cases: clean 9, sim-s0 9, sim-s1to4 36, 234 documents; simulated test 120 cases, 2,252 documents) and the same statistics.
Pooled numbers are case means; deltas are run minus reference with a paired bootstrap of 10,000 case resamples (seed 0), computed by `scripts/eval_hybrid_compare.py` against gst-hybrid's stored v1 and pd3g287 runs on the same cases (v1 58.5 / 64.1 / 68.6 and pd3g287 61.1 / 71.5 / 72.9 on semireal, ITC / match / composite).
Invented identity is the share of identity slots (3 per document) that the INVENTED rule of `gst_recon/rewards/doc.py` flags (semireal: pd3g287 68 of 702 = 9.7%, v1 141 of 702 = 20.1%).
The target is no test-time compute, like the 4B model, so thinking is off wherever the CLI allows it.

### Claude Haiku (via the Claude Code CLI)

Invocation: `claude -p --model <model> --output-format json --system-prompt <per-document system prompt> --tools "" --no-session-persistence --setting-sources "" --disable-slash-commands --strict-mcp-config --json-schema <doc schema v2>`, run through `python scripts/eval_frontier.py --mode hybrid --schema-mode flag` from a neutral working directory.
The schema goes through the CLI's `--json-schema` structured output (a forced tool call), which is not grammar-constrained decoding like the XGrammar runs of our models, and the Haiku models are not fine-tuned.
Cost is the CLI's own `total_cost_usd`.

- Haiku 4.5, thinking off: `MAX_THINKING_TOKENS=0`. Verified on raw CLI JSON: 0 thinking tokens and 441 to 443 output tokens on a document where the default setting spent 16,449 (15,657 of them thinking, 153 s).
- Haiku 5.5, minimum thinking: `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 MAX_THINKING_TOKENS=0` and `claude --effort low`. Haiku 5.5 cannot disable thinking via the Claude Code CLI; run at minimum thinking (mean 1,012 thinking tokens/doc, p95 2,163, measured on the test run); the other models use none.
  The setting was picked as the lowest mean thinking tokens on 5 fixed simulated test_ood documents (default adaptive thinking about 2,000 to 3,800 tokens on one document): adaptive off + max 0: 1,354; plus `--effort low`: 881; plus `CLAUDE_CODE_DISABLE_THINKING=1`: 1,153; all three plus `--effort low`: 948; `--settings alwaysThinkingEnabled=false` plus adaptive off: 1,275.

**semireal, 54 cases, 234 documents** (delta vs v1 [95% CI]; delta vs pd3g287 [95% CI])

| run | ITC invoice exact % | Match acc % | Composite | docs parsed | invented identity | s per doc | completion tokens per doc (p95) | CLI cost per doc |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5, thinking off | 68.2 (+9.7 [+0.3, +19.1]; +7.1 [-2.5, +16.7]) | 82.2 (+18.1 [+10.5, +26.3]; +10.7 [+6.1, +15.3]) | 77.4 (+8.8 [+3.3, +14.3]; +4.5 [-0.4, +9.5]) | 97.9% (5 of 234 unparseable) | 16.6% (114 of 702) | 8.2 | 728 (1,292) | $0.0094 |
| Haiku 5.5, minimum thinking | 84.9 (+26.4 [+18.4, +35.1]; +23.8 [+16.0, +32.2]) | 88.4 (+24.3 [+16.8, +32.6]; +16.9 [+12.6, +21.2]) | 86.5 (+17.9 [+12.9, +23.4]; +13.6 [+9.4, +18.2]) | 100.0% | 8.4% (59 of 702) | 9.1 | 1,758 incl. thinking (3,301) | $0.0010 |
| Haiku 5.5, default thinking (secondary) | 84.8 (+26.3 [+18.3, +35.0]; +23.7 [+15.9, +32.2]) | 88.6 (+24.5 [+17.0, +32.8]; +17.1 [+12.8, +21.4]) | 86.7 (+18.1 [+13.1, +23.6]; +13.8 [+9.6, +18.4]) | 100.0% | 7.4% (52 of 702) | 11.0 | 2,163 incl. thinking | $0.0015 |

All deltas against v1 and pd3g287 on match accuracy and for Haiku 5.5 on every metric have p < 0.0005; Haiku 4.5 against v1 on ITC has p = 0.043 and against pd3g287 on ITC p = 0.14 and composite p = 0.068.
A Haiku 4.5 run with default thinking was stopped after 64 documents (about 60 s and $0.043 per document, 16k thinking tokens on the check document) and is not scored.
The 30-case subset list `reports/hybrid-haiku45-subset.txt` (fixed in 001a4eb) was fixed for that abandoned thinking-on arm; the thinking-off Haiku 4.5 arm runs the full 120 test cases.
**simulated test, 120 cases (test_iid 60 + test_ood 60), 2,252 documents, schema v2, reconciler v3** (delta vs v1 [95% CI]; delta vs pd3g287 [95% CI]; v1 80.1 / 88.7 / 82.8, pd3g287 80.0 / 85.0 / 81.6)

| run | ITC invoice exact % | Match acc % | Composite | docs parsed | invented identity | s per doc | thinking tokens per doc, mean (p95) | completion tokens per doc, mean (p95) | CLI cost per doc |
|---|---|---|---|---|---|---|---|---|---|
| Haiku 4.5, thinking off | 75.7 (-4.3 [-6.5, -2.3]; -4.2 [-6.6, -2.0]) | 86.4 (-2.3 [-3.5, -1.2]; +1.4 [-0.1, +3.0]) | 80.3 (-2.5 [-3.6, -1.4]; -1.4 [-2.6, -0.1]) | 99.9% (3 of 2,252 unparseable) | 25.9% (1,749 of 6,756) | 7.3 | 0 (0) | 636 (1,145) | $0.0071 |
| Haiku 5.5, minimum thinking | 88.8 (+8.7 [+7.3, +10.2]; +8.8 [+7.3, +10.5]) | 92.4 (+3.7 [+2.7, +4.6]; +7.4 [+6.1, +8.8]) | 87.7 (+5.0 [+3.9, +6.0]; +6.1 [+5.1, +7.1]) | 100.0% | 9.8% (663 of 6,756) | 8.3 | 1,012 (2,163) | 1,580 (2,765) | $0.0011 |

Reference invented-identity rates on the same 120 cases: pd3g287 854 of 6,750 = 12.7%, v1 1,785 of 6,756 = 26.4%.
Every delta except Haiku 4.5 against pd3g287 on match accuracy (p = 0.065) and composite (p = 0.036) has p < 0.0005 or p = 0.0004; the pd3g287 ITC delta for Haiku 4.5 has p = 0.0004.
Haiku 4.5 without thinking trails both of our per-document adapters on ITC invoice exact by about 4 points and is level with pd3g287 on match accuracy; it invents an identity as often as v1 (about 26%), which is what costs it ITC.
Haiku 5.5 at minimum thinking beats both adapters on all three metrics on both sets, with thinking tokens that the 4B model does not use, so it is a reference for what a larger per-document reader reaches, not a like-for-like arm.
The 12 realworld cases are not part of these runs.

The semireal documents are real client documents; the Haiku runs sent them to the Claude CLI only, and only aggregates are reported here.

### GPT-6 luna (codex exec)

Invocation: `codex exec -m gpt-6-luna --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules --json -s read-only` with tools, skills, plugins, hooks and sub-agents disabled through `-c` (the full list is `CODEX_CLEAN` in `scripts/eval_frontier.py`), `-c model_reasoning_effort="none" -c model_reasoning_summary="none"`, the per-document system prompt as `model_instructions_file`, the document as the prompt and doc schema v2 as `--output-schema`, run through `python scripts/eval_frontier.py --mode hybrid --backend codex` from a scratch working directory with a `CODEX_HOME` that holds only `auth.json`.
codex-cli 0.164.0; about 6.0k tokens of harness-injected developer messages remain per call (a trivial prompt costs 16.3k under the default config), so a document call is about 8k input tokens.
The schema is the API's structured output, not grammar-constrained decoding like the XGrammar runs of our models, and the model is not fine-tuned.
Codex reports no per-call cost; tokens come from its `turn.completed` usage events.
The user approved sending the semireal real documents to OpenAI for this baseline; only aggregates are reported here.

Reasoning: gpt-6-luna accepts effort none, low, medium, high, xhigh and max (minimal is rejected).
The headline arm is `none`: 0 reasoning tokens on all 234 semireal and all 2,252 test documents (from the usage events), so there is no test-time compute, like the 4B model.
The secondary arm is `medium` (three smoke documents spent 407 to 804 reasoning tokens each); its semireal run predates the reasoning-token field, so its completion tokens include the reasoning tokens and are not split.
A medium-effort test run was stopped at 554 of 2,252 documents when the no-reasoning requirement arrived and is not scored.

**semireal, 54 cases, 234 documents** (delta vs v1 [95% CI]; delta vs pd3g287 [95% CI])

| run | ITC invoice exact % | Match acc % | Composite | docs parsed | invented identity | s per doc | completion tokens per doc (p95) |
|---|---|---|---|---|---|---|---|
| GPT-6 luna, reasoning none | 70.6 (+12.2 [+8.1, +16.5]; +9.6 [+5.2, +13.9]) | 82.5 (+18.3 [+12.5, +24.8]; +10.9 [+7.5, +14.2]) | 77.9 (+9.3 [+7.4, +11.3]; +5.0 [+2.7, +7.2]) | 100.0% | 15.4% (108 of 702) | 4.2 | 197 (337) |
| GPT-6 luna, medium effort (secondary) | 82.4 (+23.9 [+16.7, +32.1]; +21.3 [+13.9, +29.4]) | 86.4 (+22.3 [+15.1, +30.3]; +14.8 [+10.9, +19.0]) | 84.1 (+15.5 [+11.1, +20.7]; +11.3 [+7.5, +15.6]) | 100.0% | 12.4% (87 of 702) | 6.4 | 458 incl. reasoning (960) |

All semireal deltas have p < 0.0001.

**simulated test, 120 cases (test_iid 60, test_ood 60), 2,252 documents** (delta vs v1 [95% CI]; delta vs pd3g287 [95% CI]; v1 80.1 / 88.7 / 82.8 and pd3g287 80.0 / 85.0 / 81.6 under doc schema v2 and reconciler v3)

| run | ITC invoice exact % | Match acc % | Composite | docs parsed | invented identity | s per doc | completion tokens per doc (p95) |
|---|---|---|---|---|---|---|---|
| GPT-6 luna, reasoning none | 81.9 (+1.8 [-0.1, +3.6]; +1.9 [-0.2, +4.0]) | 90.5 (+1.8 [+0.9, +2.8]; +5.6 [+4.3, +7.0]) | 84.0 (+1.2 [+0.2, +2.3]; +2.4 [+1.2, +3.5]) | 100.0% | 15.4% (1,041 of 6,756) | 4.8 | 193 (288) |

Test p-values: against v1, ITC p = 0.062, match p < 0.0001, composite p = 0.018; against pd3g287, ITC p = 0.083, match and composite p < 0.0001.
Total tokens on the test run: 17.81M input and 0.43M output; wall time 2,156 s at concurrency 5, with no failed calls.
