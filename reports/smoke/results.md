# gst-recon evaluation results

Component metrics are primary; composite is the weighted reward. Cells are percentages unless stated; [lo, hi] is a bootstrap 95% CI over cases. Trivial baselines are handed the true extraction and links (they isolate the decisions): their field F1 and match accuracy are oracle values and their composite already includes full credit for extraction, schema and arithmetic, so compare them on ITC invoice exact, context accuracy and ITC error only.

## Overall

| run | n | Schema valid % | Field F1 % | Match acc % | ITC invoice exact % | Context acc % | ITC abs err (Rs) | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|
| teacher unconstrained | 6 | 16.7 [0.0, 50.0] | 16.5 [0.0, 49.6] | 16.7 [0.0, 50.0] | 16.7 [0.0, 50.0] | 11.1 [0.0, 50.0] | 775,998 [287,154, 1,470,327] | 16.6 [0.0, 49.9] |
| teacher constrained | 6 | 33.3 [0.0, 66.7] | 32.6 [0.0, 65.4] | 32.5 [0.0, 65.8] | 28.3 [0.0, 61.7] | 11.1 [0.0, 50.0] | 749,655 [272,455, 1,451,557] | 30.0 [0.0, 63.2] |
| Claude Sonnet (via Claude Code CLI) | 6 | 100.0 [100.0, 100.0] | 98.9 [98.5, 99.2] | 99.8 [99.5, 100.0] | 98.8 [97.4, 100.0] | 97.2 [94.5, 100.0] | 26,724 [0, 76,811] | 96.1 [92.1, 99.8] |

## Throughput and cost per 1,000 cases

| run | req/s | out tok/s | p50 latency (s) | GPU $/1k cases | API list $/1k cases |
|---|---|---|---|---|---|
| teacher unconstrained | 0.18 | 288 | 21.9 | $3.87 | $40.79 |
| teacher constrained | 0.16 | 300 | 24.5 | $4.37 | $43.39 |
| Claude Sonnet (via Claude Code CLI) | 0.02 | 348 | 76.0 | - | $251.67 |

GPU cost = measured wall time x the GPU-hour price passed to `run`. API cost = this run's mean token counts x the list price passed to `run`. Prices are inputs, not facts; `-` means no price was given.

## test_iid

| run | n | Schema valid % | Field F1 % | Match acc % | ITC invoice exact % | Context acc % | ITC abs err (Rs) | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|
| teacher unconstrained | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1,377,421 | 0.0 |
| teacher constrained | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1,377,421 | 0.0 |
| Claude Sonnet (via Claude Code CLI) | 2 | 100.0 | 98.7 | 99.5 | 96.5 | 95.7 | 80,172 | 88.7 |
| baseline: majority | - | - | 100.0 | 94.0 | 64.2 | 37.9 | 635,963 | 79.7 |
| baseline: no_anomaly | - | - | 100.0 | 94.0 | 67.3 | 37.9 | 614,038 | 81.0 |
| baseline: keyword | - | - | 100.0 | 94.0 | 68.2 | 41.3 | 492,834 | 81.2 |
| baseline: context_blind | - | - | 100.0 | 100.0 | 79.0 | 42.4 | 519,892 | 85.9 |

## test_ood

| run | n | Schema valid % | Field F1 % | Match acc % | ITC invoice exact % | Context acc % | ITC abs err (Rs) | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|
| teacher unconstrained | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 486,937 | 0.0 |
| teacher constrained | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 486,937 | 0.0 |
| Claude Sonnet (via Claude Code CLI) | 2 | 100.0 | 98.5 | 100.0 | 100.0 | 100.0 | 0 | 99.6 |
| baseline: majority | - | - | 100.0 | 94.2 | 66.7 | 35.8 | 378,107 | 80.2 |
| baseline: no_anomaly | - | - | 100.0 | 94.2 | 69.8 | 35.8 | 360,641 | 81.5 |
| baseline: keyword | - | - | 100.0 | 94.2 | 71.4 | 43.1 | 285,332 | 81.8 |
| baseline: context_blind | - | - | 100.0 | 100.0 | 78.4 | 39.4 | 241,636 | 85.3 |

## train

| run | n | Schema valid % | Field F1 % | Match acc % | ITC invoice exact % | Context acc % | ITC abs err (Rs) | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|
| teacher unconstrained | 2 | 50.0 | 49.6 | 50.0 | 50.0 | 57.1 | 463,637 | 49.9 |
| teacher constrained | 2 | 100.0 | 97.7 | 97.5 | 85.0 | 57.1 | 384,607 | 89.9 |
| Claude Sonnet (via Claude Code CLI) | 2 | 100.0 | 99.4 | 100.0 | 100.0 | 100.0 | 0 | 99.8 |

## By difficulty

| run | group | n | Schema valid % | Field F1 % | Match acc % | ITC invoice exact % | Context acc % | ITC abs err (Rs) | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|
| teacher unconstrained | easy | 2 | 50.0 | 49.6 | 50.0 | 50.0 | 57.1 | 463,637 | 49.9 |
| teacher unconstrained | hard | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1,377,421 | 0.0 |
| teacher unconstrained | medium | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 486,937 | 0.0 |
| teacher constrained | easy | 2 | 100.0 | 97.7 | 97.5 | 85.0 | 57.1 | 384,607 | 89.9 |
| teacher constrained | hard | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1,377,421 | 0.0 |
| teacher constrained | medium | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 486,937 | 0.0 |
| Claude Sonnet (via Claude Code CLI) | easy | 2 | 100.0 | 99.4 | 100.0 | 100.0 | 100.0 | 0 | 99.8 |
| Claude Sonnet (via Claude Code CLI) | hard | 2 | 100.0 | 98.7 | 99.5 | 96.5 | 95.7 | 80,172 | 88.7 |
| Claude Sonnet (via Claude Code CLI) | medium | 2 | 100.0 | 98.5 | 100.0 | 100.0 | 100.0 | 0 | 99.6 |

## By OCR recall (full vs partial)

| run | group | n | Schema valid % | Field F1 % | Match acc % | ITC invoice exact % | Context acc % | ITC abs err (Rs) | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|
| teacher unconstrained | partial | 6 | 16.7 | 16.5 | 16.7 | 16.7 | 11.1 | 775,998 | 16.6 |
| teacher constrained | partial | 6 | 33.3 | 32.6 | 32.5 | 28.3 | 11.1 | 749,655 | 30.0 |
| Claude Sonnet (via Claude Code CLI) | partial | 6 | 100.0 | 98.9 | 99.8 | 98.8 | 97.2 | 26,724 | 96.1 |

## Paired difference vs teacher unconstrained

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| teacher constrained | composite | 6 | +13.3 [-0.1, +40.1] | 0.3763 |
| teacher constrained | itc_invoice | 6 | +11.7 [+0.0, +35.0] | 0.3763 |
| Claude Sonnet (via Claude Code CLI) | composite | 6 | +79.4 [+46.4, +98.0] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) | itc_invoice | 6 | +82.2 [+49.1, +99.6] | 0.0005 |

Paired by case_id; p-value from a centred paired bootstrap (null: zero mean difference).

## AuditKIT 1.1.3 comparison

6 cases. Baseline: `unconstrained`. Run fingerprints (sha256 of model, dataset, adapter, metrics and config):

| run | fingerprint |
|---|---|
| unconstrained | `8d5ce048e7d6ae6f` |
| constrained | `57a703057db7787b` |
| live-constrained | `34021fcb8080412f` |

### `constrained` vs `unconstrained` (grade: DeltaGrade.PASS)

| metric | baseline | candidate | delta | AuditKIT p | AuditKIT significant | corrected p (centred bootstrap) | 95% CI of delta |
|---|---|---|---|---|---|---|---|
| schema_valid | 0.1667 | 0.3333 | +0.1667 | 0.657 | False | 0.3763 | [+0.0000, +0.5000] |
| extraction_f1 | 0.1653 | 0.3258 | +0.1604 | 0.552 | False | 0.3763 | [-0.0040, +0.4853] |
| match_accuracy | 0.1667 | 0.3250 | +0.1583 | 0.657 | False | 0.3763 | [+0.0000, +0.4750] |
| itc_invoice | 0.1667 | 0.2833 | +0.1167 | 0.657 | False | 0.3763 | [+0.0000, +0.3500] |
| composite | 0.1663 | 0.2996 | +0.1332 | 0.552 | False | 0.3763 | [-0.0010, +0.4006] |
| itc_abs_err_rs | 775998.2600 | 749655.0633 | -26343.1967 | 0.515 | False | 0.3763 | [-79029.5233, +0.0000] |

### `live-constrained` vs `unconstrained` (grade: DeltaGrade.PASS)

| metric | baseline | candidate | delta | AuditKIT p | AuditKIT significant | corrected p (centred bootstrap) | 95% CI of delta |
|---|---|---|---|---|---|---|---|
| schema_valid | - | - | - | - | - | - | - |
| extraction_f1 | - | - | - | - | - | - | - |
| match_accuracy | - | - | - | - | - | - | - |
| itc_invoice | - | - | - | - | - | - | - |
| composite | - | - | - | - | - | - | - |
| itc_abs_err_rs | - | - | - | - | - | - | - |

AuditKIT 1.1.3's `p_value` comes from resampling the raw paired differences without centring them on the null, so it stays near 0.5 for any effect size; the corrected column centres them. Prefer the corrected p until upstream fixes it.
