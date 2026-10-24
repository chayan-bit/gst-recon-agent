# gst-recon evaluation results

Headline metrics are ITC invoice exact and context accuracy; the composite (the weighted reward) is secondary because its floor is high (trivial baselines score about 80). ITC overclaim is the rupees of credit the model would have wrongly claimed (per invoice, sum of max(0, predicted eligible - true eligible)); underclaim is the mirror; net abs err is the absolute error of the claimed eligible total, where invoices can cancel; all three are rupees per case (mean). Cells are percentages unless stated; [lo, hi] is a bootstrap 95% CI over cases. Trivial baselines are handed the true extraction and links (they isolate the decisions): their field F1 and match accuracy are oracle values and their composite already includes full credit for extraction, schema and arithmetic, so compare them on ITC invoice exact, context accuracy and ITC error only.

## Overall

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | 120 | 71.6 [68.9, 74.2] | 48.1 [43.7, 52.4] | 325,563 [251,310, 402,111] | 64,115 [27,593, 106,948] | 313,083 [247,349, 381,826] | 93.9 [93.2, 94.6] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 82.1 [81.2, 83.1] |
| context-blind rules (oracle extraction and links) | 120 | 82.7 [80.4, 85.0] | 50.1 [44.9, 55.6] | 54,046 [40,276, 68,838] | 337,934 [185,293, 515,106] | 367,198 [219,483, 541,305] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 87.3 [86.2, 88.4] |
| teacher-30B constrained | 120 | 59.8 [55.6, 63.9] | 38.8 [32.4, 45.0] | 383,144 [295,619, 487,652] | 140,111 [63,289, 230,110] | 509,015 [399,915, 624,934] | 71.1 [66.7, 75.1] | 87.5 [82.8, 91.6] | 92.5 [87.5, 96.7] | 69.1 [65.3, 72.5] |
| teacher-30B unconstrained | 19 | 14.9 [2.1, 29.8] | 9.1 [0.0, 21.2] | 8,658 [855, 20,755] | 217,067 [78,804, 419,825] | 228,875 [93,895, 431,532] | 16.1 [3.7, 31.8] | 20.4 [5.0, 40.6] | 15.8 [0.0, 31.6] | 15.5 [3.4, 30.5] |
| teacher-30B constrained (same 19 cases as unconstrained) | 19 | 68.0 [56.7, 78.1] | 47.3 [27.1, 67.3] | 89,025 [25,550, 170,079] | 91,462 [155, 270,666] | 198,476 [65,356, 399,887] | 82.8 [71.0, 90.8] | 92.4 [81.6, 98.2] | 94.7 [84.2, 100.0] | 75.1 [65.4, 81.0] |
| SFT constrained (full grammar) | 120 | 10.9 [7.4, 14.6] | 30.7 [25.3, 36.1] | 465,489 [352,982, 584,747] | 59,776 [20,725, 116,515] | 402,137 [316,132, 496,334] | 64.0 [61.9, 65.9] | 91.0 [89.2, 92.2] | 99.2 [97.5, 100.0] | 58.2 [56.6, 59.6] |
| Claude Sonnet (via Claude Code CLI) | 120 | 96.3 [94.3, 97.7] | 92.7 [90.5, 94.6] | 15,306 [7,532, 24,334] | 28,403 [4,860, 61,386] | 43,079 [17,201, 78,166] | 99.0 [97.2, 99.9] | 98.4 [96.7, 99.4] | 99.2 [97.5, 100.0] | 94.4 [92.3, 95.9] |
| SFT+GRPO (not run yet) | - | - | - | - | - | - | - | - | - | - |

## Throughput and cost per 1,000 cases

| run | req/s | out tok/s | p50 latency (s) | GPU $/1k cases | API list $/1k cases |
|---|---|---|---|---|---|
| keyword (oracle extraction and links) | 260.73 | 0 | 0.0 | - | - |
| context-blind rules (oracle extraction and links) | 196.46 | 0 | 0.0 | - | - |
| teacher-30B constrained | 0.03 | 391 | 134.6 | $20.04 | $224.41 |
| teacher-30B unconstrained | 0.18 | 288 | 450.6 | $3.87 | $40.79 |
| teacher-30B constrained (same 19 cases as unconstrained) | 0.03 | 391 | 45.5 | - | - |
| SFT constrained (full grammar) | 0.04 | 387 | 185.0 | - | - |
| Claude Sonnet (via Claude Code CLI) | 0.03 | 358 | 67.9 | - | $226.88 |
| SFT+GRPO (not run yet) | - | - | - | - | - |

GPU cost = measured wall time x the GPU-hour price passed to `run`. API cost = this run's mean token counts x the list price passed to `run`. Prices are inputs, not facts; `-` means no price was given.

## test_iid

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | 60 | 72.7 | 50.5 | 404,271 | 87,961 | 380,117 | 94.0 | 100.0 | 100.0 | 82.5 |
| context-blind rules (oracle extraction and links) | 60 | 83.1 | 52.9 | 49,500 | 580,138 | 603,904 | 100.0 | 100.0 | 100.0 | 87.4 |
| teacher-30B constrained | 60 | 55.7 | 36.7 | 492,270 | 205,132 | 664,436 | 69.6 | 83.7 | 88.3 | 66.1 |
| teacher-30B unconstrained | 19 | 14.9 | 9.1 | 8,658 | 217,067 | 228,875 | 16.1 | 20.4 | 15.8 | 15.5 |
| teacher-30B constrained (same 19 cases as unconstrained) | 19 | 68.0 | 47.3 | 89,025 | 91,462 | 198,476 | 82.8 | 92.4 | 94.7 | 75.1 |
| SFT constrained (full grammar) | 60 | 8.1 | 28.6 | 610,319 | 90,586 | 542,383 | 64.5 | 90.6 | 98.3 | 57.5 |
| Claude Sonnet (via Claude Code CLI) | 60 | 94.9 | 92.3 | 23,982 | 39,299 | 62,212 | 98.0 | 97.5 | 98.3 | 93.0 |
| SFT+GRPO (not run yet) | - | - | - | - | - | - | - | - | - | - |

## test_ood

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | 60 | 70.4 | 45.5 | 246,854 | 40,269 | 246,049 | 93.9 | 100.0 | 100.0 | 81.7 |
| context-blind rules (oracle extraction and links) | 60 | 82.3 | 46.8 | 58,592 | 95,731 | 130,492 | 100.0 | 100.0 | 100.0 | 87.1 |
| teacher-30B constrained | 60 | 63.8 | 41.1 | 274,018 | 75,089 | 353,595 | 72.5 | 91.3 | 96.7 | 72.0 |
| SFT constrained (full grammar) | 60 | 13.7 | 33.2 | 320,659 | 28,966 | 261,891 | 63.5 | 91.4 | 100.0 | 58.9 |
| Claude Sonnet (via Claude Code CLI) | 60 | 97.8 | 93.1 | 6,629 | 17,506 | 23,946 | 99.9 | 99.4 | 100.0 | 95.8 |
| SFT+GRPO (not run yet) | - | - | - | - | - | - | - | - | - | - |

## realworld

realworld is a sanity split of 12 hand-built cases (not part of the Overall row or the difficulty, OCR and length tables); cells show a bootstrap 95% CI over those cases, which is wide at this n. Baseline rows are not CI-bearing.

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 12 | 27.1 [13.9, 40.3] | 72.2 [46.7, 90.5] | 35,924 [16,629, 60,077] | 0 [0, 0] | 34,257 [15,349, 58,864] | 77.6 [72.7, 82.5] | 92.1 [89.2, 94.4] | 100.0 [100.0, 100.0] | 65.8 [62.1, 69.7] |
| Claude Sonnet (via Claude Code CLI) | 12 | 97.2 [91.7, 100.0] | 100.0 [100.0, 100.0] | 0 [0, 0] | 64 [0, 192] | 64 [0, 192] | 99.3 [97.9, 100.0] | 98.8 [97.2, 99.9] | 100.0 [100.0, 100.0] | 97.9 [94.7, 99.8] |
| baseline: majority | - | 43.8 | 36.4 | - | - | 35,770 | 87.5 | 100.0 | - | 73.1 |
| baseline: no_anomaly | - | 48.6 | 36.4 | - | - | 34,202 | 87.5 | 100.0 | - | 74.7 |
| baseline: keyword | - | 42.4 | 31.8 | - | - | 21,201 | 87.5 | 100.0 | - | 73.9 |
| baseline: context_blind | - | 73.6 | 60.6 | - | - | 25,672 | 100.0 | 100.0 | - | 88.4 |
| SFT+GRPO (not run yet) | - | - | - | - | - | - | - | - | - | - |

## By difficulty

| run | group | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | easy | 40 | 78.9 | 52.7 | 98,140 | 10,733 | 107,672 | 97.0 | 100.0 | 100.0 | 85.4 |
| keyword (oracle extraction and links) | hard | 40 | 64.5 | 45.8 | 625,695 | 140,837 | 554,117 | 90.4 | 100.0 | 100.0 | 79.2 |
| keyword (oracle extraction and links) | medium | 40 | 71.3 | 50.4 | 252,853 | 40,776 | 277,460 | 94.3 | 100.0 | 100.0 | 81.7 |
| context-blind rules (oracle extraction and links) | easy | 40 | 84.8 | 57.1 | 29,260 | 45,986 | 70,670 | 100.0 | 100.0 | 100.0 | 89.7 |
| context-blind rules (oracle extraction and links) | hard | 40 | 80.8 | 47.5 | 77,415 | 690,224 | 717,526 | 100.0 | 100.0 | 100.0 | 85.2 |
| context-blind rules (oracle extraction and links) | medium | 40 | 82.6 | 51.5 | 55,462 | 277,593 | 313,398 | 100.0 | 100.0 | 100.0 | 86.9 |
| teacher-30B constrained | easy | 40 | 71.6 | 44.6 | 119,928 | 44,141 | 194,549 | 83.7 | 94.4 | 97.5 | 77.3 |
| teacher-30B constrained | hard | 40 | 43.6 | 34.0 | 716,946 | 326,871 | 946,317 | 53.7 | 75.0 | 82.5 | 56.5 |
| teacher-30B constrained | medium | 40 | 64.0 | 44.7 | 312,557 | 49,320 | 386,181 | 75.9 | 93.1 | 97.5 | 73.4 |
| teacher-30B unconstrained | easy | 19 | 14.9 | 9.1 | 8,658 | 217,067 | 228,875 | 16.1 | 20.4 | 15.8 | 15.5 |
| teacher-30B constrained (same 19 cases as unconstrained) | easy | 19 | 68.0 | 47.3 | 89,025 | 91,462 | 198,476 | 82.8 | 92.4 | 94.7 | 75.1 |
| SFT constrained (full grammar) | easy | 40 | 7.8 | 38.4 | 114,584 | 14,415 | 113,935 | 64.5 | 93.4 | 100.0 | 58.2 |
| SFT constrained (full grammar) | hard | 40 | 16.2 | 29.2 | 936,156 | 139,009 | 716,920 | 59.9 | 87.2 | 97.5 | 57.1 |
| SFT constrained (full grammar) | medium | 40 | 8.7 | 30.2 | 345,726 | 25,903 | 375,556 | 67.5 | 92.5 | 100.0 | 59.4 |
| Claude Sonnet (via Claude Code CLI) | easy | 40 | 98.0 | 96.4 | 170 | 148 | 317 | 100.0 | 99.4 | 100.0 | 98.1 |
| Claude Sonnet (via Claude Code CLI) | hard | 40 | 95.5 | 90.8 | 38,449 | 22,949 | 59,684 | 99.6 | 99.0 | 100.0 | 91.6 |
| Claude Sonnet (via Claude Code CLI) | medium | 40 | 95.4 | 94.3 | 7,298 | 62,111 | 69,237 | 97.2 | 96.9 | 97.5 | 93.5 |

## By split and difficulty

| run | group | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | test_iid/easy | 20 | 79.1 | 55.9 | 74,419 | 1,431 | 74,288 | 97.1 | 100.0 | 100.0 | 85.7 |
| keyword (oracle extraction and links) | test_iid/hard | 20 | 63.8 | 48.3 | 865,078 | 199,407 | 734,697 | 89.9 | 100.0 | 100.0 | 78.9 |
| keyword (oracle extraction and links) | test_iid/medium | 20 | 75.3 | 52.5 | 273,315 | 63,043 | 331,366 | 94.9 | 100.0 | 100.0 | 82.8 |
| keyword (oracle extraction and links) | test_ood/easy | 20 | 78.7 | 49.1 | 121,861 | 20,034 | 141,056 | 97.0 | 100.0 | 100.0 | 85.1 |
| keyword (oracle extraction and links) | test_ood/hard | 20 | 65.2 | 42.3 | 386,311 | 82,266 | 373,537 | 90.9 | 100.0 | 100.0 | 79.5 |
| keyword (oracle extraction and links) | test_ood/medium | 20 | 67.4 | 48.6 | 232,391 | 18,508 | 223,553 | 93.8 | 100.0 | 100.0 | 80.6 |
| context-blind rules (oracle extraction and links) | test_iid/easy | 20 | 82.8 | 57.6 | 24,786 | 59,475 | 83,785 | 100.0 | 100.0 | 100.0 | 89.2 |
| context-blind rules (oracle extraction and links) | test_iid/hard | 20 | 79.8 | 49.1 | 88,216 | 1,181,573 | 1,207,637 | 100.0 | 100.0 | 100.0 | 84.9 |
| context-blind rules (oracle extraction and links) | test_iid/medium | 20 | 86.6 | 59.2 | 35,498 | 499,364 | 520,289 | 100.0 | 100.0 | 100.0 | 88.2 |
| context-blind rules (oracle extraction and links) | test_ood/easy | 20 | 86.7 | 56.6 | 33,734 | 32,497 | 57,554 | 100.0 | 100.0 | 100.0 | 90.2 |
| context-blind rules (oracle extraction and links) | test_ood/hard | 20 | 81.7 | 45.4 | 66,615 | 198,874 | 227,415 | 100.0 | 100.0 | 100.0 | 85.4 |
| context-blind rules (oracle extraction and links) | test_ood/medium | 20 | 78.5 | 45.1 | 75,427 | 55,822 | 106,507 | 100.0 | 100.0 | 100.0 | 85.6 |
| teacher-30B constrained | test_iid/easy | 20 | 68.7 | 49.2 | 89,739 | 86,889 | 194,637 | 83.4 | 92.6 | 95.0 | 75.5 |
| teacher-30B constrained | test_iid/hard | 20 | 36.2 | 34.3 | 990,806 | 463,161 | 1,303,903 | 49.5 | 67.2 | 75.0 | 50.6 |
| teacher-30B constrained | test_iid/medium | 20 | 62.3 | 35.8 | 396,264 | 65,346 | 494,769 | 75.9 | 91.2 | 95.0 | 72.2 |
| teacher-30B constrained | test_ood/easy | 20 | 74.6 | 39.6 | 150,117 | 1,392 | 194,461 | 83.9 | 96.2 | 100.0 | 79.1 |
| teacher-30B constrained | test_ood/hard | 20 | 51.0 | 33.5 | 443,086 | 190,581 | 588,730 | 57.8 | 82.8 | 90.0 | 62.5 |
| teacher-30B constrained | test_ood/medium | 20 | 65.8 | 52.1 | 228,850 | 33,295 | 277,593 | 75.8 | 95.0 | 100.0 | 74.5 |
| teacher-30B unconstrained | test_iid/easy | 19 | 14.9 | 9.1 | 8,658 | 217,067 | 228,875 | 16.1 | 20.4 | 15.8 | 15.5 |
| teacher-30B constrained (same 19 cases as unconstrained) | test_iid/easy | 19 | 68.0 | 47.3 | 89,025 | 91,462 | 198,476 | 82.8 | 92.4 | 94.7 | 75.1 |
| SFT constrained (full grammar) | test_iid/easy | 20 | 4.7 | 42.4 | 77,210 | 780 | 72,217 | 65.4 | 93.8 | 100.0 | 57.9 |
| SFT constrained (full grammar) | test_iid/hard | 20 | 13.0 | 23.4 | 1,331,443 | 254,386 | 1,046,977 | 60.3 | 84.9 | 95.0 | 55.5 |
| SFT constrained (full grammar) | test_iid/medium | 20 | 6.7 | 33.3 | 422,303 | 16,592 | 507,954 | 67.8 | 93.2 | 100.0 | 59.2 |
| SFT constrained (full grammar) | test_ood/easy | 20 | 10.8 | 34.0 | 151,958 | 28,050 | 155,654 | 63.6 | 92.9 | 100.0 | 58.4 |
| SFT constrained (full grammar) | test_ood/hard | 20 | 19.3 | 37.1 | 540,869 | 23,632 | 386,862 | 59.6 | 89.5 | 100.0 | 58.7 |
| SFT constrained (full grammar) | test_ood/medium | 20 | 10.8 | 27.5 | 269,149 | 35,214 | 243,158 | 67.2 | 91.8 | 100.0 | 59.5 |
| Claude Sonnet (via Claude Code CLI) | test_iid/easy | 20 | 97.5 | 96.6 | 126 | 295 | 421 | 100.0 | 99.1 | 100.0 | 97.6 |
| Claude Sonnet (via Claude Code CLI) | test_iid/hard | 20 | 94.7 | 91.3 | 62,176 | 41,251 | 100,564 | 99.5 | 99.0 | 100.0 | 90.8 |
| Claude Sonnet (via Claude Code CLI) | test_iid/medium | 20 | 92.4 | 92.5 | 9,644 | 76,350 | 85,650 | 94.6 | 94.4 | 95.0 | 90.6 |
| Claude Sonnet (via Claude Code CLI) | test_ood/easy | 20 | 98.6 | 96.2 | 213 | 0 | 213 | 100.0 | 99.7 | 100.0 | 98.6 |
| Claude Sonnet (via Claude Code CLI) | test_ood/hard | 20 | 96.3 | 90.2 | 14,722 | 4,648 | 18,803 | 99.7 | 99.1 | 100.0 | 92.3 |
| Claude Sonnet (via Claude Code CLI) | test_ood/medium | 20 | 98.3 | 95.8 | 4,952 | 47,871 | 52,823 | 99.9 | 99.4 | 100.0 | 96.4 |

## By OCR recall (full = every field present in the prompt)

| run | group | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | partial | 120 | 71.6 | 48.1 | 325,563 | 64,115 | 313,083 | 93.9 | 100.0 | 100.0 | 82.1 |
| context-blind rules (oracle extraction and links) | partial | 120 | 82.7 | 50.1 | 54,046 | 337,934 | 367,198 | 100.0 | 100.0 | 100.0 | 87.3 |
| teacher-30B constrained | partial | 120 | 59.8 | 38.8 | 383,144 | 140,111 | 509,015 | 71.1 | 87.5 | 92.5 | 69.1 |
| teacher-30B unconstrained | partial | 19 | 14.9 | 9.1 | 8,658 | 217,067 | 228,875 | 16.1 | 20.4 | 15.8 | 15.5 |
| teacher-30B constrained (same 19 cases as unconstrained) | partial | 19 | 68.0 | 47.3 | 89,025 | 91,462 | 198,476 | 82.8 | 92.4 | 94.7 | 75.1 |
| SFT constrained (full grammar) | partial | 120 | 10.9 | 30.7 | 465,489 | 59,776 | 402,137 | 64.0 | 91.0 | 99.2 | 58.2 |
| Claude Sonnet (via Claude Code CLI) | partial | 120 | 96.3 | 92.7 | 15,306 | 28,403 | 43,079 | 99.0 | 98.4 | 99.2 | 94.4 |

## By case prompt length (Qwen3 tokens: <=16k, 16-32k, >32k)

| run | group | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | <=16k | 63 | 76.7 | 51.3 | 154,183 | 10,001 | 158,978 | 96.3 | 100.0 | 100.0 | 84.2 |
| keyword (oracle extraction and links) | 16-32k | 44 | 67.9 | 49.7 | 458,106 | 73,764 | 456,927 | 91.8 | 100.0 | 100.0 | 80.3 |
| keyword (oracle extraction and links) | >32k | 13 | 59.1 | 40.2 | 707,488 | 293,703 | 573,044 | 89.5 | 100.0 | 100.0 | 77.7 |
| context-blind rules (oracle extraction and links) | <=16k | 63 | 84.6 | 56.5 | 37,168 | 59,194 | 91,421 | 100.0 | 100.0 | 100.0 | 89.0 |
| context-blind rules (oracle extraction and links) | 16-32k | 44 | 80.8 | 49.9 | 62,933 | 637,769 | 657,863 | 100.0 | 100.0 | 100.0 | 85.4 |
| context-blind rules (oracle extraction and links) | >32k | 13 | 79.6 | 42.0 | 105,758 | 673,928 | 719,866 | 100.0 | 100.0 | 100.0 | 84.9 |
| teacher-30B constrained | <=16k | 63 | 69.5 | 44.3 | 197,353 | 29,252 | 247,862 | 82.3 | 94.8 | 98.4 | 76.7 |
| teacher-30B constrained | 16-32k | 44 | 54.0 | 38.7 | 560,245 | 196,744 | 743,334 | 64.8 | 86.4 | 93.2 | 66.3 |
| teacher-30B constrained | >32k | 13 | 31.7 | 31.6 | 684,097 | 485,666 | 981,528 | 38.0 | 55.8 | 61.5 | 41.4 |
| teacher-30B unconstrained | <=16k | 19 | 14.9 | 9.1 | 8,658 | 217,067 | 228,875 | 16.1 | 20.4 | 15.8 | 15.5 |
| teacher-30B constrained (same 19 cases as unconstrained) | <=16k | 19 | 68.0 | 47.3 | 89,025 | 91,462 | 198,476 | 82.8 | 92.4 | 94.7 | 75.1 |
| SFT constrained (full grammar) | <=16k | 63 | 7.6 | 36.5 | 179,234 | 21,687 | 189,333 | 64.6 | 93.1 | 100.0 | 58.3 |
| SFT constrained (full grammar) | 16-32k | 44 | 16.7 | 29.1 | 671,189 | 66,890 | 559,355 | 66.8 | 91.1 | 100.0 | 60.5 |
| SFT constrained (full grammar) | >32k | 13 | 7.3 | 27.0 | 1,156,505 | 220,281 | 901,298 | 51.7 | 80.5 | 92.3 | 50.1 |
| Claude Sonnet (via Claude Code CLI) | <=16k | 63 | 96.6 | 94.3 | 303 | 31,633 | 31,827 | 98.4 | 97.8 | 98.4 | 96.0 |
| Claude Sonnet (via Claude Code CLI) | 16-32k | 44 | 96.1 | 92.3 | 29,599 | 14,044 | 42,133 | 99.7 | 99.3 | 100.0 | 93.6 |
| Claude Sonnet (via Claude Code CLI) | >32k | 13 | 95.5 | 91.4 | 39,635 | 61,345 | 100,812 | 99.3 | 98.9 | 100.0 | 89.2 |

## Context overflow and truncation by prompt length

| run | length bucket | cases | context overflow | cut at the token cap |
|---|---|---|---|---|
| SFT constrained (full grammar) | >32k | 13 | 0 | 1 |

Context overflow = the prompt alone does not fit the server context, so the case scores 0 (what a real deployment at that context would do). Cut at the cap = the reply was truncated and is scored as it stands. Only buckets with at least one are listed.

## Paired difference vs SFT constrained (full grammar)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| keyword (oracle extraction and links) | itc_invoice | 120 | +60.7 [+56.3, +64.9] | 0.0005 |
| keyword (oracle extraction and links) | context_acc | 119 | +11.0 [+2.9, +18.5] | 0.0015 |
| keyword (oracle extraction and links) | composite | 120 | +23.9 [+22.3, +25.5] | 0.0005 |
| context-blind rules (oracle extraction and links) | itc_invoice | 120 | +71.8 [+67.2, +76.2] | 0.0005 |
| context-blind rules (oracle extraction and links) | context_acc | 119 | +17.0 [+9.2, +25.4] | 0.0005 |
| context-blind rules (oracle extraction and links) | composite | 120 | +29.1 [+27.3, +30.9] | 0.0005 |
| teacher-30B constrained | itc_invoice | 120 | +48.9 [+43.3, +54.5] | 0.0005 |
| teacher-30B constrained | context_acc | 119 | +2.2 [-7.5, +11.1] | 0.6367 |
| teacher-30B constrained | composite | 120 | +10.9 [+7.1, +14.4] | 0.0005 |
| teacher-30B unconstrained | itc_invoice | 19 | +11.9 [-1.2, +27.2] | 0.1004 |
| teacher-30B unconstrained | context_acc | 19 | -32.2 [-51.9, -13.5] | 0.0010 |
| teacher-30B unconstrained | composite | 19 | -41.9 [-54.0, -27.2] | 0.0005 |
| teacher-30B constrained (same 19 cases as unconstrained) | itc_invoice | 19 | +65.0 [+54.2, +74.7] | 0.0005 |
| teacher-30B constrained (same 19 cases as unconstrained) | context_acc | 19 | -0.3 [-26.1, +26.7] | 0.9870 |
| teacher-30B constrained (same 19 cases as unconstrained) | composite | 19 | +17.7 [+7.8, +23.6] | 0.0015 |
| Claude Sonnet (via Claude Code CLI) | itc_invoice | 132 | +84.0 [+79.8, +87.8] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) | context_acc | 130 | +56.5 [+50.7, +62.0] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) | composite | 132 | +35.8 [+33.5, +37.8] | 0.0005 |

Paired by case_id; p-value from a centred paired bootstrap (null: zero mean difference).

## Notes

- The two baseline rows are handed the true extraction and document links, so their match accuracy, field F1 and schema validity are oracle values; compare them on ITC invoice exact, context accuracy and the rupee metrics only.
- teacher-30B unconstrained was stopped early, at the coordinator's request, because the teacher GPU was needed for student training.
- It finished 19 cases, all test_iid easy, and 15 of the 19 hit the 24,000-token completion cap in repetition loops.
- The row "teacher-30B constrained (same 19 cases as unconstrained)" is the constrained run restricted to those 19 cases, for a paired comparison; it is not a separate run.
- teacher-30B constrained covers all 120 cases; 9 of 120 hit the completion cap and are scored as they stand.
- Teacher runs used the task prompt from before the compact-form sentence ("Fields that are 0, empty or false may be omitted.") was added; the first teacher passes had a 24,000-token cap and later passes added a cap of 2 x reference length + 1,000.
- Sonnet: the first 62 completed cases ran under the earlier prompt and the last 58 under the current one (prompt hashes are in config.json).
- GPU and API price flags in the cost table are illustrative inputs; the Sonnet API cost is the total_cost_usd reported by the claude CLI.
- All 120 cases were rendered with one OCR engine (Tesseract 5.5.0); gst_recon/eval/eval_sets_manifest.json pins the data.
- realworld (12 hand-built cases, 36 documents printed through 7 open-source print formats, OCR'd with Tesseract 5.5.0, no synthetic degradation; see realworld/README.md) is reported as its own split and is excluded from the Overall row and from the difficulty, OCR and length tables, so those stay comparable with the simulator test sets.
- With n = 12 the realworld bootstrap CIs are wide; read them as coverage evidence, not a precise score.
- The realworld baseline rows come from `python -m realworld.baselines --n-train 2000` and are handed the true extraction and links; the two oracle-extraction baseline runs above were not run on realworld.
- No teacher row exists for realworld because the teacher was stopped.
- The "SFT constrained (full grammar)" row is format-mismatch evidence, not the SFT model's capability.
- The SFT targets use the compact form (zero fields dropped), but the full constrained grammar requires blocked, deferred and all four tax heads in every ITC record.
- Forced to emit slots it never saw in training, the model fills blocked and deferred with junk: predicted blocked is nonzero in 78.5% of 2,246 ITC records (truth 21.9%) and deferred in 71.4% (truth 12.2%).
- Per ITC record, the eligible bucket is exactly right in 59.0% of records, but all three buckets are right in only 12.3%, which matches the headline 10.9% ITC invoice exact.
- Rows labelled "compact grammar" use `--compact-schema`, which makes the zero-droppable inner fields optional while keeping top-level keys, types and reason enums.
