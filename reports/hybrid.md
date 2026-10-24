## Hybrid mode

In hybrid mode the model reads one document at a time (`DOC_SYSTEM_PROMPT` plus the case header and that one document section) and returns its extraction and two judgments per line (ITC category and purpose).
Deterministic code (`gst_recon/hybrid/`) then does all the matching to register, GSTR-2B and bank, the rupee arithmetic and the ITC rules, and emits the same ReconOutput, scored by the same scorer as the end-to-end rows above.
The oracle check (true per-document records through the same code) reproduces target.json exactly on all 132 cases (composite 1.0), so every point lost below is a reading or judgment error, not a code error.
Runs: `python -m gst_recon.eval run --mode hybrid --constrained` (per-document json_schema decoding, Qwen3-4B-Instruct-2507 on one RTX 5070 Ti 16 GB, SGLang 0.5.22, 16k context, concurrency 8); the code-alone floor is `--extractor heuristic` (regex extraction, every line normal and business, no model); Sonnet is `scripts/eval_frontier.py --mode hybrid` on realworld only.
All hybrid rows are scored with commit ac03f32, which stops the repair step from computing tax as taxable x a misread rate (an amount read into the rate cell had produced Rs 67M of phantom ITC on test_ood-medium-9002-00001); before it, student-base hybrid had ITC overclaim Rs 620,883 and ITC invoice exact 43.8%.

### Overall (120 simulator cases)

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| student-base hybrid | 120 | 44.3 [41.4, 47.3] | 67.6 [63.4, 71.5] | 72,728 [38,279, 113,854] | 542,029 [399,673, 700,714] | 578,549 [437,977, 741,066] | 63.0 [61.0, 65.0] | 87.1 [86.4, 87.9] | 100.0 [100.0, 100.0] | 65.1 [64.0, 66.1] |
| heuristic hybrid (code alone) | 120 | 10.4 [8.8, 12.1] | 40.9 [34.7, 46.3] | 29,728 [14,899, 51,425] | 743,155 [574,896, 930,170] | 726,778 [561,474, 909,353] | 35.2 [33.3, 37.2] | 58.4 [57.6, 59.1] | 100.0 [100.0, 100.0] | 47.0 [46.2, 47.8] |

### test_iid

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| student-base hybrid | 60 | 40.0 | 66.4 | 105,764 | 752,515 | 810,318 | 60.7 | 87.7 | 100.0 | 63.7 |
| heuristic hybrid (code alone) | 60 | 10.3 | 39.6 | 39,569 | 981,934 | 968,462 | 35.2 | 57.7 | 100.0 | 46.8 |

### test_ood

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| student-base hybrid | 60 | 48.6 | 68.9 | 39,691 | 331,543 | 346,780 | 65.3 | 86.6 | 100.0 | 66.5 |
| heuristic hybrid (code alone) | 60 | 10.6 | 42.4 | 19,888 | 504,377 | 485,094 | 35.2 | 59.0 | 100.0 | 47.2 |

### realworld (12 cases, bootstrap 95% CI)

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| student-base hybrid | 12 | 38.9 [26.4, 51.4] | 44.4 [14.3, 73.3] | 165 [0, 495] | 34,691 [14,008, 60,717] | 34,526 [14,008, 60,594] | 79.2 [73.6, 84.4] | 87.0 [83.2, 90.6] | 100.0 [100.0, 100.0] | 67.6 [64.0, 70.8] |
| heuristic hybrid (code alone) | 12 | 4.9 [0.0, 11.1] | 55.6 [21.4, 78.3] | 784 [0, 2,288] | 54,093 [32,921, 78,573] | 53,309 [32,040, 78,142] | 19.1 [13.2, 24.7] | 52.5 [49.0, 55.8] | 100.0 [100.0, 100.0] | 40.0 [37.2, 42.9] |
| Claude Sonnet (via Claude Code CLI) hybrid | 12 | 97.2 [91.7, 100.0] | 100.0 [100.0, 100.0] | 0 [0, 0] | 152 [0, 454] | 152 [0, 454] | 97.0 [94.3, 99.3] | 98.0 [96.0, 99.2] | 100.0 [100.0, 100.0] | 97.2 [93.5, 99.4] |

### By case prompt length (Qwen3 tokens of the whole case)

| run | group | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| student-base hybrid | <=16k | 63 | 47.6 | 70.9 | 66,249 | 165,087 | 210,439 | 64.9 | 88.6 | 100.0 | 66.6 |
| student-base hybrid | 16-32k | 44 | 42.0 | 67.6 | 99,527 | 846,445 | 885,073 | 61.9 | 85.8 | 100.0 | 64.1 |
| student-base hybrid | >32k | 13 | 36.1 | 63.2 | 13,422 | 1,338,416 | 1,324,995 | 57.4 | 84.7 | 100.0 | 61.3 |
| heuristic hybrid (code alone) | <=16k | 63 | 12.0 | 41.7 | 12,616 | 314,325 | 310,491 | 38.8 | 59.8 | 100.0 | 48.7 |
| heuristic hybrid (code alone) | 16-32k | 44 | 9.4 | 41.0 | 52,868 | 1,128,930 | 1,099,501 | 32.6 | 57.2 | 100.0 | 45.7 |
| heuristic hybrid (code alone) | >32k | 13 | 6.6 | 39.7 | 34,338 | 1,515,636 | 1,482,645 | 26.6 | 55.5 | 100.0 | 43.2 |

Each model call sees one document (about 1.5-3k tokens), so no hybrid case overflows the 16k context or hits the token cap; accuracy still falls with case length because long cases carry more documents and more matching.

### Paired difference vs SFT constrained (full grammar), end-to-end

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-base hybrid | itc_invoice | 132 | +31.4 [+26.8, +35.9] | 0.0005 |
| student-base hybrid | context_acc | 130 | +28.6 [+20.9, +35.9] | 0.0005 |
| student-base hybrid | composite | 132 | +6.4 [+4.8, +8.0] | 0.0005 |
| heuristic hybrid (code alone) | itc_invoice | 132 | -2.4 [-6.8, +1.4] | 0.2499 |
| heuristic hybrid (code alone) | context_acc | 130 | -2.8 [-11.9, +6.0] | 0.5217 |
| heuristic hybrid (code alone) | composite | 132 | -12.5 [-14.3, -10.8] | 0.0005 |

Paired by case_id over all 132 cases (realworld included); p-value from a centred paired bootstrap (null: zero mean difference).
Caveat: that end-to-end SFT run used the full constrained grammar, which does not match the compact-form SFT targets (blocked and deferred fill with junk; see Notes above), so it understates the SFT model.
A compact-grammar end-to-end SFT rerun is pending, and paired numbers against it will replace these.
The student-base hybrid row is also a different model (no fine-tune) from the end-to-end SFT row; the like-for-like pairing is SFT hybrid vs SFT end-to-end, which follows when the SFT hybrid run finishes.

### Throughput

| run | req/s | out tok/s | p50 latency (s) | GPU $/1k cases | API list $/1k cases |
|---|---|---|---|---|---|
| student-base hybrid | 0.09 | 473 | 82.0 | - | - |
| heuristic hybrid (code alone) | 25.91 | 0 | 0.0 | - | - |
| Claude Sonnet (via Claude Code CLI) hybrid | 0.11 | 185 | 16.9 | - | - |

Throughput is from each run's first pass: student-base made 2,288 document calls in 1,553 s wall (2.79M prompt and 0.73M completion tokens), and Sonnet made 36 document calls through `claude -p` at concurrency 2 on the Mac.
The scores of every hybrid row come from re-reconciling the cached replies after ac03f32, with no new model calls; only student-base changed.
