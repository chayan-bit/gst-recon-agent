## Hybrid mode

In hybrid mode the model reads one document at a time (`DOC_SYSTEM_PROMPT` plus the case header and that one document section) and returns its extraction and two judgments per line (ITC category and purpose).
Deterministic code (`gst_recon/hybrid/`) then does all the matching to register, GSTR-2B and bank, the rupee arithmetic and the ITC rules, and emits the same ReconOutput, scored by the same scorer as the end-to-end rows above.
The oracle check (true per-document records through the same code) reproduces target.json exactly on all 132 cases (composite 1.0), so every point lost below is a reading or judgment error, not a code error.
Runs: `python -m gst_recon.eval run --mode hybrid --constrained` (per-document json_schema decoding, Qwen3-4B-Instruct-2507 on one RTX 5070 Ti 16 GB, SGLang 0.5.22, 16k context, 4,096-token reply cap per document); the code-alone floor is `--extractor heuristic` (regex extraction, every line normal and business, no model); Sonnet is `scripts/eval_frontier.py --mode hybrid` on realworld only.
The end-to-end row "SFT constrained (full grammar)" is repeated in the tables for side-by-side comparison (see the caveat under the paired table).
student-sft hybrid is the end-to-end SFT adapter (trained on whole-case prompts) applied to per-document prompts, so it is off its training distribution.
student-perdoc-sft hybrid is the matched model: a LoRA (r 32, alpha 64, all 7 projections, served in bf16) trained on rs-lab for 124 steps (0.42 epoch, 1,984 curated per-document rows built with `build_doc_messages` and `DOC_SYSTEM_PROMPT`, full DocRecord targets, completion-only loss).
All hybrid rows are scored with commit ac03f32, which stops the repair step from computing tax as taxable x a misread rate (an amount read into the rate cell had produced Rs 67M of phantom ITC on test_ood-medium-9002-00001); before it, student-base hybrid had ITC overclaim Rs 620,883 and ITC invoice exact 43.8%.

### Overall (120 simulator cases)

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 120 | 10.9 [7.4, 14.6] | 30.7 [25.3, 36.1] | 465,489 [352,982, 584,747] | 59,776 [20,725, 116,515] | 402,137 [316,132, 496,334] | 64.0 [61.9, 65.9] | 91.0 [89.2, 92.2] | 99.2 [97.5, 100.0] | 58.2 [56.6, 59.6] |
| student-base hybrid | 120 | 44.3 [41.4, 47.3] | 67.6 [63.4, 71.5] | 72,728 [38,279, 113,854] | 542,029 [399,673, 700,714] | 578,549 [437,977, 741,066] | 63.0 [61.0, 65.0] | 87.1 [86.4, 87.9] | 100.0 [100.0, 100.0] | 65.1 [64.0, 66.1] |
| student-sft hybrid | 120 | 38.2 [35.6, 40.9] | 57.5 [53.6, 61.3] | 19,424 [7,041, 34,455] | 686,534 [519,385, 869,921] | 688,739 [525,496, 871,524] | 61.4 [59.6, 63.4] | 86.2 [85.2, 87.3] | 100.0 [100.0, 100.0] | 63.3 [62.3, 64.3] |
| student-perdoc-sft hybrid | 120 | 62.9 [60.2, 65.3] | 82.7 [79.3, 85.8] | 19,053 [6,187, 36,486] | 436,024 [315,294, 571,946] | 440,860 [322,330, 574,220] | 72.2 [70.2, 74.1] | 92.0 [91.3, 92.8] | 100.0 [100.0, 100.0] | 73.2 [72.1, 74.4] |
| heuristic hybrid (code alone) | 120 | 10.4 [8.8, 12.1] | 40.9 [34.7, 46.3] | 29,728 [14,899, 51,425] | 743,155 [574,896, 930,170] | 726,778 [561,474, 909,353] | 35.2 [33.3, 37.2] | 58.4 [57.6, 59.1] | 100.0 [100.0, 100.0] | 47.0 [46.2, 47.8] |

### test_iid

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 60 | 8.1 | 28.6 | 610,319 | 90,586 | 542,383 | 64.5 | 90.6 | 98.3 | 57.5 |
| student-base hybrid | 60 | 40.0 | 66.4 | 105,764 | 752,515 | 810,318 | 60.7 | 87.7 | 100.0 | 63.7 |
| student-sft hybrid | 60 | 40.1 | 59.9 | 4,563 | 928,502 | 924,517 | 60.9 | 87.4 | 100.0 | 63.9 |
| student-perdoc-sft hybrid | 60 | 67.0 | 84.7 | 34,932 | 527,084 | 538,136 | 76.7 | 92.9 | 100.0 | 75.5 |
| heuristic hybrid (code alone) | 60 | 10.3 | 39.6 | 39,569 | 981,934 | 968,462 | 35.2 | 57.7 | 100.0 | 46.8 |

### test_ood

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 60 | 13.7 | 33.2 | 320,659 | 28,966 | 261,891 | 63.5 | 91.4 | 100.0 | 58.9 |
| student-base hybrid | 60 | 48.6 | 68.9 | 39,691 | 331,543 | 346,780 | 65.3 | 86.6 | 100.0 | 66.5 |
| student-sft hybrid | 60 | 36.3 | 54.8 | 34,284 | 444,567 | 452,960 | 62.0 | 85.1 | 100.0 | 62.6 |
| student-perdoc-sft hybrid | 60 | 58.7 | 80.5 | 3,173 | 344,964 | 343,584 | 67.6 | 91.2 | 100.0 | 71.0 |
| heuristic hybrid (code alone) | 60 | 10.6 | 42.4 | 19,888 | 504,377 | 485,094 | 35.2 | 59.0 | 100.0 | 47.2 |

### realworld (12 cases, bootstrap 95% CI)

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 12 | 27.1 [13.9, 40.3] | 72.2 [46.7, 90.5] | 35,924 [16,629, 60,077] | 0 [0, 0] | 34,257 [15,349, 58,864] | 77.6 [72.7, 82.5] | 92.1 [89.2, 94.4] | 100.0 [100.0, 100.0] | 65.8 [62.1, 69.7] |
| student-base hybrid | 12 | 38.9 [26.4, 51.4] | 44.4 [14.3, 73.3] | 165 [0, 495] | 34,691 [14,008, 60,717] | 34,526 [14,008, 60,594] | 79.2 [73.6, 84.4] | 87.0 [83.2, 90.6] | 100.0 [100.0, 100.0] | 67.6 [64.0, 70.8] |
| student-sft hybrid | 12 | 28.5 [13.9, 45.1] | 22.2 [5.5, 46.7] | 0 [0, 0] | 45,227 [21,649, 72,068] | 45,227 [21,649, 72,068] | 85.2 [79.0, 90.5] | 88.2 [83.9, 92.5] | 100.0 [100.0, 100.0] | 66.3 [61.4, 71.6] |
| student-perdoc-sft hybrid | 12 | 76.4 [63.9, 88.9] | 100.0 [100.0, 100.0] | 0 [0, 0] | 3,770 [0, 9,113] | 3,770 [0, 9,113] | 87.0 [81.9, 91.7] | 92.9 [89.5, 96.0] | 100.0 [100.0, 100.0] | 84.4 [78.5, 90.3] |
| heuristic hybrid (code alone) | 12 | 4.9 [0.0, 11.1] | 55.6 [21.4, 78.3] | 784 [0, 2,288] | 54,093 [32,921, 78,573] | 53,309 [32,040, 78,142] | 19.1 [13.2, 24.7] | 52.5 [49.0, 55.8] | 100.0 [100.0, 100.0] | 40.0 [37.2, 42.9] |
| Claude Sonnet (via Claude Code CLI) hybrid | 12 | 97.2 [91.7, 100.0] | 100.0 [100.0, 100.0] | 0 [0, 0] | 152 [0, 454] | 152 [0, 454] | 97.0 [94.3, 99.3] | 98.0 [96.0, 99.2] | 100.0 [100.0, 100.0] | 97.2 [93.5, 99.4] |

### By case prompt length (Qwen3 tokens of the whole case)

| run | group | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | <=16k | 63 | 7.6 | 36.5 | 179,234 | 21,687 | 189,333 | 64.6 | 93.1 | 100.0 | 58.3 |
| SFT constrained (full grammar) | 16-32k | 44 | 16.7 | 29.1 | 671,189 | 66,890 | 559,355 | 66.8 | 91.1 | 100.0 | 60.5 |
| SFT constrained (full grammar) | >32k | 13 | 7.3 | 27.0 | 1,156,505 | 220,281 | 901,298 | 51.7 | 80.5 | 92.3 | 50.1 |
| student-base hybrid | <=16k | 63 | 47.6 | 70.9 | 66,249 | 165,087 | 210,439 | 64.9 | 88.6 | 100.0 | 66.6 |
| student-base hybrid | 16-32k | 44 | 42.0 | 67.6 | 99,527 | 846,445 | 885,073 | 61.9 | 85.8 | 100.0 | 64.1 |
| student-base hybrid | >32k | 13 | 36.1 | 63.2 | 13,422 | 1,338,416 | 1,324,995 | 57.4 | 84.7 | 100.0 | 61.3 |
| student-sft hybrid | <=16k | 63 | 40.1 | 64.3 | 14,198 | 278,779 | 281,355 | 64.3 | 88.8 | 100.0 | 64.9 |
| student-sft hybrid | 16-32k | 44 | 37.1 | 56.4 | 24,264 | 1,045,275 | 1,050,420 | 59.4 | 84.0 | 100.0 | 62.1 |
| student-sft hybrid | >32k | 13 | 32.6 | 51.1 | 28,369 | 1,448,378 | 1,438,832 | 54.3 | 81.5 | 100.0 | 59.2 |
| student-perdoc-sft hybrid | <=16k | 63 | 65.2 | 88.7 | 18,151 | 145,241 | 159,199 | 74.7 | 93.9 | 100.0 | 74.9 |
| student-perdoc-sft hybrid | 16-32k | 44 | 61.6 | 82.1 | 12,494 | 655,548 | 651,799 | 70.4 | 90.2 | 100.0 | 72.0 |
| student-perdoc-sft hybrid | >32k | 13 | 55.4 | 76.4 | 45,622 | 1,102,203 | 1,091,888 | 65.9 | 89.1 | 100.0 | 69.1 |
| heuristic hybrid (code alone) | <=16k | 63 | 12.0 | 41.7 | 12,616 | 314,325 | 310,491 | 38.8 | 59.8 | 100.0 | 48.7 |
| heuristic hybrid (code alone) | 16-32k | 44 | 9.4 | 41.0 | 52,868 | 1,128,930 | 1,099,501 | 32.6 | 57.2 | 100.0 | 45.7 |
| heuristic hybrid (code alone) | >32k | 13 | 6.6 | 39.7 | 34,338 | 1,515,636 | 1,482,645 | 26.6 | 55.5 | 100.0 | 43.2 |

Each model call sees one document (about 1.5-3k tokens), so no hybrid case overflows the 16k context; accuracy still falls with case length because long cases carry more documents and more matching.

### Cases with a document reply cut at the 4,096-token cap

| run | length bucket | cases | context overflow | cut at the token cap |
|---|---|---|---|---|
| student-sft hybrid | <=16k | 63 | 0 | 6 |
| student-sft hybrid | 16-32k | 44 | 0 | 9 |
| student-sft hybrid | >32k | 13 | 0 | 2 |

The column counts cases with at least one cut document reply (student-sft hybrid: 17 cases, one cut document each); a cut reply is unparseable and that document is reconciled as missing, while the other documents of the case still count.

### Paired difference vs student-base hybrid

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-perdoc-sft hybrid | itc_invoice | 132 | +20.3 [+16.9, +23.8] | 0.0005 |
| student-perdoc-sft hybrid | context_acc | 130 | +19.7 [+15.0, +24.7] | 0.0005 |
| student-perdoc-sft hybrid | composite | 132 | +8.9 [+7.7, +10.2] | 0.0005 |

Paired by case_id over all 132 cases (realworld included); same prompts, same code, same server; the only change is the per-document LoRA adapter.

### Paired difference vs SFT constrained (full grammar), end-to-end

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-base hybrid | itc_invoice | 132 | +31.4 [+26.8, +35.9] | 0.0005 |
| student-base hybrid | context_acc | 130 | +28.6 [+20.9, +35.9] | 0.0005 |
| student-base hybrid | composite | 132 | +6.4 [+4.8, +8.0] | 0.0005 |
| student-sft hybrid | itc_invoice | 132 | +24.9 [+19.8, +29.7] | 0.0005 |
| student-sft hybrid | context_acc | 130 | +18.5 [+10.9, +26.4] | 0.0005 |
| student-sft hybrid | composite | 132 | +4.7 [+2.9, +6.4] | 0.0005 |
| student-perdoc-sft hybrid | itc_invoice | 132 | +51.7 [+47.1, +56.4] | 0.0005 |
| student-perdoc-sft hybrid | context_acc | 130 | +48.2 [+42.2, +54.4] | 0.0005 |
| student-perdoc-sft hybrid | composite | 132 | +15.4 [+13.6, +17.1] | 0.0005 |
| heuristic hybrid (code alone) | itc_invoice | 132 | -2.4 [-6.8, +1.4] | 0.2499 |
| heuristic hybrid (code alone) | context_acc | 130 | -2.8 [-11.9, +6.0] | 0.5217 |
| heuristic hybrid (code alone) | composite | 132 | -12.5 [-14.3, -10.8] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) hybrid | itc_invoice | 12 | +70.1 [+52.8, +84.7] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) hybrid | context_acc | 11 | +36.4 [+13.6, +63.6] | 0.0035 |
| Claude Sonnet (via Claude Code CLI) hybrid | composite | 12 | +31.5 [+24.6, +36.7] | 0.0005 |

Paired by case_id over all 132 cases (realworld included); p-value from a centred paired bootstrap (null: zero mean difference).
Caveat: that end-to-end SFT run used the full constrained grammar, which does not match the compact-form SFT targets (blocked and deferred fill with junk; see Notes above), so it understates the SFT model.
A compact-grammar end-to-end SFT rerun is pending, and paired numbers against it will replace these.
student-sft hybrid vs this row is the like-for-like pairing (same adapter, same cases); student-base hybrid is a different model (no fine-tune).

### Throughput

| run | req/s | out tok/s | p50 latency (s) | GPU $/1k cases | API list $/1k cases |
|---|---|---|---|---|---|
| student-base hybrid | 0.09 | 473 | 82.0 | - | - |
| student-sft hybrid | - | - | - | - | - |
| student-perdoc-sft hybrid | 0.10 | 441 | 61.2 | - | - |
| heuristic hybrid (code alone) | 15.55 | 0 | 1.0 | - | - |
| Claude Sonnet (via Claude Code CLI) hybrid | 0.11 | 185 | 16.9 | - | - |

Throughput is from each run's first pass: student-base made 2,288 document calls in 1,553 s wall (2.79M prompt and 0.73M completion tokens), and Sonnet made 36 document calls through `claude -p` at concurrency 2 on the Mac.
student-perdoc-sft hybrid throughput is its first pass; a demo recording shared the server for its first 4 minutes (16:47:30 to 16:51:43 IST, one request at a time against this run's 8), so it is slightly understated.
student-sft hybrid throughput is not reported: demo recordings shared the server during the run and the run was restarted midway (concurrency 8 to 14), so its timings are contaminated; its accuracy is unaffected.
The scores of every hybrid row come from re-reconciling the cached replies after ac03f32 where needed, with no new model calls.
