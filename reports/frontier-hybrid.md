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
- Haiku 5.5, minimum thinking: `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 MAX_THINKING_TOKENS=0` and `claude --effort low`. Haiku 5.5 cannot disable thinking via the Claude Code CLI; run at minimum thinking (mean N tokens/doc, see the test rows); the other models use none.
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
The semireal documents are real client documents; the Haiku runs sent them to the Claude CLI only, and only aggregates are reported here.
