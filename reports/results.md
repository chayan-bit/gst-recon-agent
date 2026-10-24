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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 30 | 50.0 [41.7, 58.2] | 24.7 [13.5, 37.0] | 384,809 [228,829, 566,930] | 278,024 [22,897, 647,167] | 648,016 [341,829, 1,039,593] | 59.7 [49.8, 68.9] | 81.6 [70.6, 90.7] | 90.0 [76.7, 100.0] | 60.1 [51.7, 67.0] |
| SFT constrained (full grammar) | 120 | 10.9 [7.4, 14.6] | 30.7 [25.3, 36.1] | 465,489 [352,982, 584,747] | 59,776 [20,725, 116,515] | 402,137 [316,132, 496,334] | 64.0 [61.9, 65.9] | 91.0 [89.2, 92.2] | 99.2 [97.5, 100.0] | 58.2 [56.6, 59.6] |
| SFT constrained (compact grammar) | 30 | 75.7 [70.0, 81.5] | 63.9 [52.5, 73.8] | 435,416 [215,198, 701,045] | 19,491 [6,265, 36,743] | 322,681 [183,096, 493,411] | 85.7 [80.9, 90.3] | 95.7 [94.2, 97.0] | 100.0 [100.0, 100.0] | 80.5 [77.7, 83.5] |
| SFT constrained, compact grammar (same 36 cases) | 30 | 75.7 [70.0, 81.5] | 63.9 [52.5, 73.8] | 435,416 [215,198, 701,045] | 19,491 [6,265, 36,743] | 322,681 [183,096, 493,411] | 85.7 [80.9, 90.3] | 95.7 [94.2, 97.0] | 100.0 [100.0, 100.0] | 80.5 [77.7, 83.5] |
| SFT unconstrained | 30 | 72.3 [64.8, 79.4] | 59.5 [48.0, 69.7] | 387,852 [183,040, 636,231] | 36,977 [7,310, 78,010] | 355,488 [196,829, 546,233] | 83.6 [76.0, 89.7] | 92.6 [85.6, 96.7] | 70.0 [53.3, 86.7] | 75.5 [68.4, 81.1] |
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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 0.01 | 59 | 121.6 | - | - |
| SFT constrained (full grammar) | 0.04 | 387 | 185.0 | - | - |
| SFT constrained (compact grammar) | 0.05 | 203 | 31.8 | - | - |
| SFT constrained, compact grammar (same 36 cases) | 0.05 | 203 | 38.0 | - | - |
| SFT unconstrained | 0.04 | 200 | 31.0 | - | - |
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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 15 | 46.9 | 17.2 | 412,362 | 527,029 | 984,915 | 54.0 | 73.8 | 80.0 | 54.2 |
| SFT constrained (full grammar) | 60 | 8.1 | 28.6 | 610,319 | 90,586 | 542,383 | 64.5 | 90.6 | 98.3 | 57.5 |
| SFT constrained (compact grammar) | 15 | 72.6 | 57.4 | 605,393 | 11,688 | 432,296 | 84.1 | 95.6 | 100.0 | 78.7 |
| SFT constrained, compact grammar (same 36 cases) | 15 | 72.6 | 57.4 | 605,393 | 11,688 | 432,296 | 84.1 | 95.6 | 100.0 | 78.7 |
| SFT unconstrained | 15 | 72.1 | 56.6 | 532,352 | 6,526 | 481,081 | 85.2 | 95.9 | 73.3 | 76.1 |
| Claude Sonnet (via Claude Code CLI) | 60 | 94.9 | 92.3 | 23,982 | 39,299 | 62,212 | 98.0 | 97.5 | 98.3 | 93.0 |
| SFT+GRPO (not run yet) | - | - | - | - | - | - | - | - | - | - |

## test_ood

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| keyword (oracle extraction and links) | 60 | 70.4 | 45.5 | 246,854 | 40,269 | 246,049 | 93.9 | 100.0 | 100.0 | 81.7 |
| context-blind rules (oracle extraction and links) | 60 | 82.3 | 46.8 | 58,592 | 95,731 | 130,492 | 100.0 | 100.0 | 100.0 | 87.1 |
| teacher-30B constrained | 60 | 63.8 | 41.1 | 274,018 | 75,089 | 353,595 | 72.5 | 91.3 | 96.7 | 72.0 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 15 | 53.1 | 33.3 | 357,256 | 29,019 | 311,118 | 65.3 | 89.4 | 100.0 | 65.9 |
| SFT constrained (full grammar) | 60 | 13.7 | 33.2 | 320,659 | 28,966 | 261,891 | 63.5 | 91.4 | 100.0 | 58.9 |
| SFT constrained (compact grammar) | 15 | 78.9 | 71.4 | 265,438 | 27,294 | 213,067 | 87.3 | 95.7 | 100.0 | 82.3 |
| SFT constrained, compact grammar (same 36 cases) | 15 | 78.9 | 71.4 | 265,438 | 27,294 | 213,067 | 87.3 | 95.7 | 100.0 | 82.3 |
| SFT unconstrained | 15 | 72.6 | 62.9 | 243,352 | 67,429 | 229,895 | 82.0 | 89.3 | 66.7 | 74.8 |
| Claude Sonnet (via Claude Code CLI) | 60 | 97.8 | 93.1 | 6,629 | 17,506 | 23,946 | 99.9 | 99.4 | 100.0 | 95.8 |
| SFT+GRPO (not run yet) | - | - | - | - | - | - | - | - | - | - |

## realworld

realworld is a sanity split of 12 hand-built cases (not part of the Overall row or the difficulty, OCR and length tables); cells show a bootstrap 95% CI over those cases, which is wide at this n. Baseline rows are not CI-bearing.

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 6 | 63.9 [47.2, 80.6] | 75.0 [37.5, 93.8] | 30,311 [3,653, 65,081] | 0 [0, 0] | 34,896 [9,476, 65,484] | 81.9 [76.4, 87.5] | 91.4 [87.9, 93.9] | 100.0 [100.0, 100.0] | 71.5 [68.6, 74.8] |
| SFT constrained (full grammar) | 12 | 27.1 [13.9, 40.3] | 72.2 [46.7, 90.5] | 35,924 [16,629, 60,077] | 0 [0, 0] | 34,257 [15,349, 58,864] | 77.6 [72.7, 82.5] | 92.1 [89.2, 94.4] | 100.0 [100.0, 100.0] | 65.8 [62.1, 69.7] |
| SFT constrained (compact grammar) | 12 | 68.8 [54.8, 83.3] | 83.3 [60.0, 96.2] | 21,235 [619, 49,870] | 0 [0, 0] | 21,235 [619, 49,870] | 96.0 [92.4, 99.3] | 96.4 [92.8, 98.9] | 100.0 [100.0, 100.0] | 84.2 [78.0, 90.5] |
| SFT constrained, compact grammar (same 36 cases) | 6 | 79.2 [58.3, 95.8] | 83.3 [50.0, 100.0] | 18,870 [0, 55,950] | 0 [0, 0] | 18,870 [0, 55,950] | 96.2 [90.6, 100.0] | 98.3 [96.1, 100.0] | 100.0 [100.0, 100.0] | 88.6 [78.9, 96.7] |
| SFT unconstrained | 12 | 68.8 [55.6, 80.6] | 83.3 [61.5, 100.0] | 6,135 [329, 15,537] | 5,310 [0, 15,930] | 11,445 [1,247, 24,644] | 96.0 [93.1, 98.6] | 95.8 [92.1, 98.5] | 100.0 [100.0, 100.0] | 83.4 [78.2, 89.2] |
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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | easy | 10 | 63.3 | 23.5 | 207,280 | 150 | 141,045 | 83.9 | 93.4 | 100.0 | 72.5 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | hard | 10 | 33.4 | 17.6 | 647,801 | 816,921 | 1,465,494 | 33.0 | 62.8 | 70.0 | 42.8 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | medium | 10 | 53.3 | 38.2 | 299,347 | 17,001 | 337,510 | 62.1 | 88.6 | 100.0 | 64.9 |
| SFT constrained (full grammar) | easy | 40 | 7.8 | 38.4 | 114,584 | 14,415 | 113,935 | 64.5 | 93.4 | 100.0 | 58.2 |
| SFT constrained (full grammar) | hard | 40 | 16.2 | 29.2 | 936,156 | 139,009 | 716,920 | 59.9 | 87.2 | 97.5 | 57.1 |
| SFT constrained (full grammar) | medium | 40 | 8.7 | 30.2 | 345,726 | 25,903 | 375,556 | 67.5 | 92.5 | 100.0 | 59.4 |
| SFT constrained (compact grammar) | easy | 10 | 87.1 | 76.5 | 92,074 | 1,346 | 106,430 | 98.4 | 98.8 | 100.0 | 87.0 |
| SFT constrained (compact grammar) | hard | 10 | 61.6 | 57.6 | 1,110,727 | 40,303 | 744,924 | 72.0 | 91.8 | 100.0 | 72.7 |
| SFT constrained (compact grammar) | medium | 10 | 78.5 | 69.1 | 103,445 | 16,824 | 116,689 | 86.7 | 96.3 | 100.0 | 81.8 |
| SFT constrained, compact grammar (same 36 cases) | easy | 10 | 87.1 | 76.5 | 92,074 | 1,346 | 106,430 | 98.4 | 98.8 | 100.0 | 87.0 |
| SFT constrained, compact grammar (same 36 cases) | hard | 10 | 61.6 | 57.6 | 1,110,727 | 40,303 | 744,924 | 72.0 | 91.8 | 100.0 | 72.7 |
| SFT constrained, compact grammar (same 36 cases) | medium | 10 | 78.5 | 69.1 | 103,445 | 16,824 | 116,689 | 86.7 | 96.3 | 100.0 | 81.8 |
| SFT unconstrained | easy | 10 | 84.7 | 76.5 | 64,606 | 2,032 | 74,404 | 97.0 | 98.7 | 100.0 | 87.1 |
| SFT unconstrained | hard | 10 | 64.2 | 57.6 | 997,968 | 76,180 | 834,305 | 73.6 | 92.3 | 40.0 | 67.7 |
| SFT unconstrained | medium | 10 | 68.1 | 54.4 | 100,981 | 32,719 | 157,755 | 80.1 | 86.8 | 70.0 | 71.6 |
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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | test_iid/easy | 5 | 65.8 | 31.6 | 219,711 | 125 | 137,586 | 84.7 | 93.1 | 100.0 | 72.6 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | test_iid/hard | 5 | 19.0 | 12.8 | 694,575 | 1,559,160 | 2,381,690 | 16.6 | 36.0 | 40.0 | 24.1 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | test_iid/medium | 5 | 56.0 | 20.0 | 322,801 | 21,802 | 435,469 | 60.7 | 92.4 | 100.0 | 65.9 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | test_ood/easy | 5 | 60.9 | 13.3 | 194,848 | 175 | 144,505 | 83.1 | 93.8 | 100.0 | 72.4 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | test_ood/hard | 5 | 47.8 | 25.5 | 601,026 | 74,682 | 549,298 | 49.4 | 89.7 | 100.0 | 61.6 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | test_ood/medium | 5 | 50.7 | 48.8 | 275,892 | 12,199 | 239,551 | 63.5 | 84.9 | 100.0 | 63.9 |
| SFT constrained (full grammar) | test_iid/easy | 20 | 4.7 | 42.4 | 77,210 | 780 | 72,217 | 65.4 | 93.8 | 100.0 | 57.9 |
| SFT constrained (full grammar) | test_iid/hard | 20 | 13.0 | 23.4 | 1,331,443 | 254,386 | 1,046,977 | 60.3 | 84.9 | 95.0 | 55.5 |
| SFT constrained (full grammar) | test_iid/medium | 20 | 6.7 | 33.3 | 422,303 | 16,592 | 507,954 | 67.8 | 93.2 | 100.0 | 59.2 |
| SFT constrained (full grammar) | test_ood/easy | 20 | 10.8 | 34.0 | 151,958 | 28,050 | 155,654 | 63.6 | 92.9 | 100.0 | 58.4 |
| SFT constrained (full grammar) | test_ood/hard | 20 | 19.3 | 37.1 | 540,869 | 23,632 | 386,862 | 59.6 | 89.5 | 100.0 | 58.7 |
| SFT constrained (full grammar) | test_ood/medium | 20 | 10.8 | 27.5 | 269,149 | 35,214 | 243,158 | 67.2 | 91.8 | 100.0 | 59.5 |
| SFT constrained (compact grammar) | test_iid/easy | 5 | 83.6 | 73.7 | 126,104 | 0 | 130,144 | 98.4 | 98.1 | 100.0 | 84.9 |
| SFT constrained (compact grammar) | test_iid/hard | 5 | 58.6 | 56.4 | 1,631,803 | 26,062 | 1,065,113 | 66.6 | 91.1 | 100.0 | 70.7 |
| SFT constrained (compact grammar) | test_iid/medium | 5 | 75.6 | 48.0 | 58,273 | 9,003 | 101,630 | 87.3 | 97.7 | 100.0 | 80.6 |
| SFT constrained (compact grammar) | test_ood/easy | 5 | 90.7 | 80.0 | 58,045 | 2,692 | 82,717 | 98.4 | 99.6 | 100.0 | 89.2 |
| SFT constrained (compact grammar) | test_ood/hard | 5 | 64.6 | 59.6 | 589,651 | 54,544 | 424,736 | 77.4 | 92.6 | 100.0 | 74.7 |
| SFT constrained (compact grammar) | test_ood/medium | 5 | 81.3 | 81.4 | 148,618 | 24,645 | 131,748 | 86.2 | 94.8 | 100.0 | 83.0 |
| SFT constrained, compact grammar (same 36 cases) | test_iid/easy | 5 | 83.6 | 73.7 | 126,104 | 0 | 130,144 | 98.4 | 98.1 | 100.0 | 84.9 |
| SFT constrained, compact grammar (same 36 cases) | test_iid/hard | 5 | 58.6 | 56.4 | 1,631,803 | 26,062 | 1,065,113 | 66.6 | 91.1 | 100.0 | 70.7 |
| SFT constrained, compact grammar (same 36 cases) | test_iid/medium | 5 | 75.6 | 48.0 | 58,273 | 9,003 | 101,630 | 87.3 | 97.7 | 100.0 | 80.6 |
| SFT constrained, compact grammar (same 36 cases) | test_ood/easy | 5 | 90.7 | 80.0 | 58,045 | 2,692 | 82,717 | 98.4 | 99.6 | 100.0 | 89.2 |
| SFT constrained, compact grammar (same 36 cases) | test_ood/hard | 5 | 64.6 | 59.6 | 589,651 | 54,544 | 424,736 | 77.4 | 92.6 | 100.0 | 74.7 |
| SFT constrained, compact grammar (same 36 cases) | test_ood/medium | 5 | 81.3 | 81.4 | 148,618 | 24,645 | 131,748 | 86.2 | 94.8 | 100.0 | 83.0 |
| SFT unconstrained | test_iid/easy | 5 | 81.3 | 68.4 | 127,068 | 0 | 131,113 | 98.4 | 98.1 | 100.0 | 84.3 |
| SFT unconstrained | test_iid/hard | 5 | 62.6 | 57.7 | 1,401,626 | 12,995 | 1,181,659 | 68.9 | 92.7 | 40.0 | 66.5 |
| SFT unconstrained | test_iid/medium | 5 | 72.3 | 44.0 | 68,360 | 6,582 | 130,472 | 88.4 | 97.0 | 80.0 | 77.7 |
| SFT unconstrained | test_ood/easy | 5 | 88.1 | 86.7 | 2,143 | 4,065 | 17,696 | 95.6 | 99.3 | 100.0 | 90.0 |
| SFT unconstrained | test_ood/hard | 5 | 65.9 | 57.4 | 594,310 | 139,365 | 486,950 | 78.4 | 91.9 | 40.0 | 68.9 |
| SFT unconstrained | test_ood/medium | 5 | 63.9 | 60.5 | 133,602 | 58,856 | 185,038 | 71.9 | 76.6 | 60.0 | 65.5 |
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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | partial | 30 | 50.0 | 24.7 | 384,809 | 278,024 | 648,016 | 59.7 | 81.6 | 90.0 | 60.1 |
| SFT constrained (full grammar) | partial | 120 | 10.9 | 30.7 | 465,489 | 59,776 | 402,137 | 64.0 | 91.0 | 99.2 | 58.2 |
| SFT constrained (compact grammar) | partial | 30 | 75.7 | 63.9 | 435,416 | 19,491 | 322,681 | 85.7 | 95.7 | 100.0 | 80.5 |
| SFT constrained, compact grammar (same 36 cases) | partial | 30 | 75.7 | 63.9 | 435,416 | 19,491 | 322,681 | 85.7 | 95.7 | 100.0 | 80.5 |
| SFT unconstrained | partial | 30 | 72.3 | 59.5 | 387,852 | 36,977 | 355,488 | 83.6 | 92.6 | 70.0 | 75.5 |
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
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | <=16k | 16 | 60.4 | 27.4 | 229,038 | 8,738 | 198,071 | 77.9 | 91.2 | 100.0 | 70.2 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 16-32k | 8 | 44.3 | 28.9 | 354,784 | 421,662 | 747,808 | 49.0 | 79.6 | 87.5 | 55.7 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | >32k | 6 | 30.1 | 18.3 | 840,233 | 804,602 | 1,714,815 | 25.2 | 58.8 | 66.7 | 38.9 |
| SFT constrained (full grammar) | <=16k | 63 | 7.6 | 36.5 | 179,234 | 21,687 | 189,333 | 64.6 | 93.1 | 100.0 | 58.3 |
| SFT constrained (full grammar) | 16-32k | 44 | 16.7 | 29.1 | 671,189 | 66,890 | 559,355 | 66.8 | 91.1 | 100.0 | 60.5 |
| SFT constrained (full grammar) | >32k | 13 | 7.3 | 27.0 | 1,156,505 | 220,281 | 901,298 | 51.7 | 80.5 | 92.3 | 50.1 |
| SFT constrained (compact grammar) | <=16k | 16 | 85.8 | 79.0 | 69,832 | 9,861 | 82,209 | 94.6 | 97.6 | 100.0 | 85.9 |
| SFT constrained (compact grammar) | 16-32k | 8 | 69.1 | 57.8 | 476,592 | 12,114 | 510,706 | 82.0 | 95.3 | 100.0 | 77.2 |
| SFT constrained (compact grammar) | >32k | 6 | 57.7 | 58.5 | 1,355,403 | 55,009 | 713,240 | 67.1 | 90.9 | 100.0 | 70.6 |
| SFT constrained, compact grammar (same 36 cases) | <=16k | 16 | 85.8 | 79.0 | 69,832 | 9,861 | 82,209 | 94.6 | 97.6 | 100.0 | 85.9 |
| SFT constrained, compact grammar (same 36 cases) | 16-32k | 8 | 69.1 | 57.8 | 476,592 | 12,114 | 510,706 | 82.0 | 95.3 | 100.0 | 77.2 |
| SFT constrained, compact grammar (same 36 cases) | >32k | 6 | 57.7 | 58.5 | 1,355,403 | 55,009 | 713,240 | 67.1 | 90.9 | 100.0 | 70.6 |
| SFT unconstrained | <=16k | 16 | 78.9 | 61.3 | 43,439 | 20,663 | 81,436 | 89.5 | 91.7 | 87.5 | 80.4 |
| SFT unconstrained | 16-32k | 8 | 67.3 | 59.0 | 511,408 | 7,410 | 548,030 | 81.2 | 94.9 | 37.5 | 70.4 |
| SFT unconstrained | >32k | 6 | 61.7 | 58.5 | 1,141,544 | 119,904 | 829,572 | 71.0 | 91.8 | 66.7 | 69.1 |
| Claude Sonnet (via Claude Code CLI) | <=16k | 63 | 96.6 | 94.3 | 303 | 31,633 | 31,827 | 98.4 | 97.8 | 98.4 | 96.0 |
| Claude Sonnet (via Claude Code CLI) | 16-32k | 44 | 96.1 | 92.3 | 29,599 | 14,044 | 42,133 | 99.7 | 99.3 | 100.0 | 93.6 |
| Claude Sonnet (via Claude Code CLI) | >32k | 13 | 95.5 | 91.4 | 39,635 | 61,345 | 100,812 | 99.3 | 98.9 | 100.0 | 89.2 |

## Context overflow and truncation by prompt length

| run | length bucket | cases | context overflow | cut at the token cap |
|---|---|---|---|---|
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | 16-32k | 8 | 0 | 1 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | >32k | 6 | 0 | 2 |
| SFT constrained (full grammar) | >32k | 13 | 0 | 1 |

Context overflow = the prompt alone does not fit the server context, so the case scores 0 (what a real deployment at that context would do). Cut at the cap = the reply was truncated and is scored as it stands. Only buckets with at least one are listed.

## Paired difference vs SFT constrained (compact grammar)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| keyword (oracle extraction and links) | itc_invoice | 30 | -8.2 [-14.2, -2.7] | 0.0070 |
| keyword (oracle extraction and links) | context_acc | 30 | -29.8 [-42.1, -17.9] | 0.0005 |
| keyword (oracle extraction and links) | composite | 30 | +0.6 [-2.0, +2.9] | 0.6382 |
| context-blind rules (oracle extraction and links) | itc_invoice | 30 | +6.7 [-0.6, +14.0] | 0.0715 |
| context-blind rules (oracle extraction and links) | context_acc | 30 | -10.1 [-28.0, +7.6] | 0.2744 |
| context-blind rules (oracle extraction and links) | composite | 30 | +7.1 [+4.0, +10.0] | 0.0005 |
| teacher-30B constrained | itc_invoice | 30 | -20.7 [-27.6, -14.2] | 0.0005 |
| teacher-30B constrained | context_acc | 30 | -38.3 [-49.3, -26.3] | 0.0005 |
| teacher-30B constrained | composite | 30 | -13.8 [-21.5, -7.7] | 0.0020 |
| teacher-30B unconstrained | itc_invoice | 5 | -83.6 [-100.0, -59.6] | 0.0005 |
| teacher-30B unconstrained | context_acc | 5 | -70.0 [-100.0, -30.0] | 0.0005 |
| teacher-30B unconstrained | composite | 5 | -84.9 [-89.4, -78.8] | 0.0005 |
| teacher-30B constrained (same 19 cases as unconstrained) | itc_invoice | 5 | -14.4 [-34.4, +0.0] | 0.0855 |
| teacher-30B constrained (same 19 cases as unconstrained) | context_acc | 5 | -30.0 [-70.0, +0.0] | 0.0875 |
| teacher-30B constrained (same 19 cases as unconstrained) | composite | 5 | -6.3 [-10.5, -2.0] | 0.0030 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | itc_invoice | 36 | -24.0 [-29.9, -17.8] | 0.0005 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | context_acc | 36 | -39.6 [-50.1, -29.6] | 0.0005 |
| student-base constrained (36 completed cases, 6 realworld lost to host failure) | composite | 36 | -19.9 [-26.0, -15.1] | 0.0005 |
| SFT constrained (full grammar) | itc_invoice | 42 | -59.5 [-68.2, -50.3] | 0.0005 |
| SFT constrained (full grammar) | context_acc | 41 | -22.5 [-34.2, -11.2] | 0.0005 |
| SFT constrained (full grammar) | composite | 42 | -21.9 [-25.0, -18.9] | 0.0005 |
| SFT unconstrained | itc_invoice | 42 | -2.4 [-7.3, +2.5] | 0.3203 |
| SFT unconstrained | context_acc | 41 | -1.7 [-9.0, +5.9] | 0.6482 |
| SFT unconstrained | composite | 42 | -3.8 [-8.1, -0.4] | 0.0490 |
| Claude Sonnet (via Claude Code CLI) | itc_invoice | 42 | +24.7 [+18.8, +30.2] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) | context_acc | 41 | +28.7 [+18.3, +39.1] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) | composite | 42 | +15.6 [+13.0, +18.0] | 0.0005 |

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
- Per-record ITC comparison on the 120 simulator cases (2,252 truth records; a record is correct when all four heads are within Rs 0.02, records aligned by doc_id), eligible bucket exactly right / all three buckets right, as a share of aligned records (share of all truth records in brackets):
- SFT full grammar: 59.0% (57.9%) / 12.1% (11.9%); teacher-30B constrained: 61.6% (53.1%) / 61.0% (52.5%); Sonnet: 96.9% (96.4%) / 96.5% (96.0%).
- The teacher aligns only 1,939 of 2,252 records because some of its replies are invalid or cut, which is why its share of truth records is lower than its share of aligned records.
- Predicted blocked is nonzero in 79.0% of SFT records, 2.9% of teacher records and 19.8% of Sonnet records (deferred 72.2%, 1.7%, 12.8%); the truth rates are 21.9% and 12.2%.
- So on the eligible bucket the SFT model matches the teacher, and the whole gap to the teacher on ITC invoice exact comes from blocked and deferred under the full grammar.
- The earlier SFT figures 59.0% and 12.3% above include realworld (2,246 aligned records); the simulator-only figures are in this note.
- The "SFT constrained (compact grammar)" rows are the SFT model scored with the grammar that matches its compact training targets (`--compact-schema`); they replace the full-grammar row as the SFT headline.
- Scope: the compact run is a seeded stratified sample, 15 test_iid, 15 test_ood and all 12 realworld cases, so its Overall row has n = 30 simulator cases while the other rows have n = 120.
- Compare rows only through the paired table, which uses the shared case ids; the CIs at n = 30 are wide.
- Sign convention in the paired table is the other run minus SFT compact, so a negative delta means SFT compact is better.
- Same 42 cases, SFT compact vs SFT full grammar: ITC invoice exact +59.5 points, context accuracy +22.5, composite +21.9 (all p = 0.0005); the grammar mismatch, not the model, caused the earlier 10.9%.
- Per-record ITC buckets on the same 30 sampled simulator cases (587 truth records; correct = all four heads within Rs 0.02, aligned by doc_id), eligible bucket right / all three buckets right, as a share of aligned records (share of truth records in brackets):
- SFT compact grammar: 71.6% (71.2%) / 69.7% (69.3%); SFT full grammar: 55.5% (55.5%) / 9.0% (9.0%); teacher-30B constrained: 60.9% (48.4%) / 59.2% (47.0%); Sonnet: 98.5% (98.5%) / 98.1% (98.1%).
- Predicted blocked is nonzero in 13.7% of SFT compact records and deferred in 2.2%, against truth rates near 22% and 12%, so under the compact grammar the remaining error is mostly the eligible decision and a missing deferred bucket, not junk.
- "SFT unconstrained" is the same 42-case sample with no grammar, the JSON Schema in the system prompt and a per-case token cap of 2 x the reference length + 1000; no case hit the cap (0 truncated, all finish_reason stop) and none looped.
- Without the grammar the model still emits valid compact JSON on most cases, but only 70.0% pass the schema check and 1 reply failed to parse (a missing closing brace), against 100% schema-valid with the compact grammar.
- Paired against SFT compact (same 42 cases): ITC invoice exact -2.4 points [-7.3, +2.5], p = 0.32, context accuracy -1.7 [-9.0, +5.9], p = 0.65, composite -3.8 [-8.1, -0.4], p = 0.049.
- So the compact grammar gives the guarantee of valid output at no measurable accuracy cost, and the SFT model does not depend on the grammar for its ITC decisions.
- "student-base constrained" (Qwen3-4B-Instruct-2507 with the full grammar, no training) ran the same 42-case sample at concurrency 2.
- Six of its 12 realworld cases (rw01, rw02, rw04, rw06, rw09, rw11) failed with ConnectionResetError when the shared rs-epyc host was starved of RAM at the end of the run, and were not retried.
- Those failures are infrastructure, not model results, so the report does not publish the 42-case base aggregate; the base row covers the 36 completed cases only (30 simulator cases and 6 realworld cases), with transport errors 0.
- The row "SFT constrained, compact grammar (same 36 cases)" is SFT compact restricted to the same 36 cases, for a like-for-like comparison; the realworld table shows both at n = 6.
- 3 base replies hit the 24,000-token cap on test_iid-hard cases (prompts of 33k to 40k tokens), which are genuine and kept.
- On the 30 simulator cases the base model scores ITC invoice exact 50.0, context accuracy 24.7 and composite 60.1, against 75.7, 63.9 and 80.5 for SFT compact.
- Paired on those 30 simulator cases, SFT compact beats base by +25.7 points on ITC invoice exact [18.8, 32.6], +45.9 on context accuracy [35.0, 56.5] and +20.5 on composite [14.4, 27.4], all p = 0.0005.

## Hybrid mode

In hybrid mode the model reads one document at a time (`DOC_SYSTEM_PROMPT` plus the case header and that one document section) and returns its extraction and two judgments per line (ITC category and purpose).
Deterministic code (`gst_recon/hybrid/`) then does all the matching to register, GSTR-2B and bank, the rupee arithmetic and the ITC rules, and emits the same ReconOutput, scored by the same scorer as the end-to-end rows above.
The oracle check (true per-document records through the same code) reproduces target.json exactly on all 132 cases (composite 1.0) under all three reconciler versions, so every point lost below is a reading or judgment error or a linking miss, not a rules error.
Runs: `python -m gst_recon.eval run --mode hybrid --constrained` (per-document json_schema decoding, Qwen3-4B-Instruct-2507 on one RTX 5070 Ti 16 GB, SGLang 0.5.22, 16k context, 4,096-token reply cap per document); the code-alone floor is `--extractor heuristic` (regex extraction, every line normal and business, no model); Sonnet is `scripts/eval_frontier.py --mode hybrid` on realworld only.
The end-to-end row "SFT constrained (full grammar)" is repeated in the tables for side-by-side comparison; it understates the SFT model (see the caveat below), and the paired comparison against the compact-grammar end-to-end SFT run, the reference row of this report, is the like-for-like one.
student-sft hybrid is the end-to-end SFT adapter (trained on whole-case prompts) applied to per-document prompts, so it is off its training distribution.
student-perdoc-sft hybrid is the matched model: a LoRA (r 32, alpha 64, all 7 projections, served in bf16) trained on rs-lab for 124 steps (0.42 epoch, 1,984 curated per-document rows built with `build_doc_messages` and `DOC_SYSTEM_PROMPT`, full DocRecord targets, completion-only loss).
student-perdoc-sft-v2 hybrid continues that LoRA for 174 more steps on the 2,775 curated rows v1 never saw (one full epoch of 4,759 rows, same prompt and LoRA shape, adapter sha256 c0c287de...); it was compared with v1 on both dev sets before the test set was run once.
All rows include commit ac03f32, which stops the repair step from computing tax as taxable x a misread rate (it had produced Rs 67M of phantom ITC on one case).

### Reconciler v1, v2 and v3

Rows without a suffix use reconciler v1; rows marked "(reconciler v2)" or "(reconciler v3)" re-score the same cached model replies (no new model calls) with reconciler v2 (commit b5c3c0b) or v3 (commit 8286f1f).
v2's rules were fixed after an error analysis of one demo case (examples/test_iid-hard-23-00001, a test_iid-split example case, seed 23, not among the 132 scored cases, seeds 9001/9002) and checked on the train split before the test set was re-scored once:
- A GSTR-2B link no longer requires the invoice number to match within one edit; the number adds to the score and a link without it needs GSTIN, date and amounts (threshold unchanged).
- A supplier GSTIN that fails the mod-36 check digit is an OCR misread and is replaced by the linked GSTR-2B (else register) GSTIN when that one is valid and within 2 edits; a valid GSTIN is never changed, so a real registration in another state still raises gstin_mismatch.
- A line read as motor_vehicle with HSN 8704 (goods vehicle) is not blocked under s.17(5)(a).
- A single-line document whose header is self-consistent (heads = taxable x a standard rate, total = taxable + tax) takes the header's figures for the line (this rule never fired on the dev set).
Dev set: the 120 train-split cases grpo-{easy,medium,hard}-201-00000 to 00039, which the per-document SFT never saw (its rows come only from the sft-* cases); on dev, v1 to v2 moved ITC invoice exact from 71.4% to 80.1% (student-perdoc-sft) and from 43.6% to 53.1% (student-base), with no false register or GSTR-2B link added.

v3 was developed only on train-split dev cases (an error attribution of the dev misses put 47 of 79 wrong student-perdoc-sft documents on identity fields the OCR text does not show) and then frozen; the test set was re-scored once:
- An invoice number or date that the document text does not show (empty, or not found in the OCR text within one edit) is taken from the one GSTR-2B entry of this GSTIN with the same taxable value, tax heads, total and note type (else from the one such register row, date only, since registers carry number typos); a value the text does show is never replaced, and every fill is recorded in the trace.
- The v2 GSTIN fix may change either the state code or the rest of the GSTIN, never both: on the larger dev set two fixes had changed the state code together with another character, turning the document's GSTIN into another state's registration of the same PAN (one of them an Rs 4.3 lakh overclaim).
Dev, student-perdoc-sft, v2 to v3: ITC invoice exact 80.1% to 87.8% and composite 85.3 to 91.2 on the 120 small cases, 76.7% to 81.1% and 79.6 to 82.6 on the 60 larger cases (below); student-base 53.1% to 54.5% on the small cases; no false register or GSTR-2B link on either dev set.
The code-alone floor (`--extractor heuristic`, OCR text and regex, no model), re-scored once under v3 from the same cached extractions: ITC invoice exact 10.4% to 11.1%, context 40.9% unchanged, composite 47.0 to 47.4 on the 120 simulator cases, and 4.9% to 13.2% ITC on realworld; the model rows gain far more from v3 because the fill and the GSTIN fix need a mostly right reading to start from.
ITC overclaim rises from v1 to v3 (test, student-perdoc-sft: Rs 19,053 to 27,183 per case; larger dev set: Rs 4,913 to 39,752): a document that v1 left deferred for lack of a link now links, so a wrong model judgment on it (a works contract or motor vehicle line read as normal) counts as overclaim instead of being masked.

### Larger dev set (60 train-split cases, about 25 documents each)

A second dev set of 60 simulator cases (seeds 7301 medium and 7302 hard, train split, 10 to 43 documents per case, never used for SFT or test) checks that the reconciler holds on longer cases; it was rendered with the same OCR pipeline.

| student-perdoc-sft hybrid | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | Composite | register false | GSTR-2B false | payment false | GSTR-2B missed | register missed |
|---|---|---|---|---|---|---|---|---|---|---|
| reconciler v1 | 68.2 | 80.4 | 4,913 | 537,641 | 75.6 | 1 | 1 | 9 | 436 | 323 |
| reconciler v2 | 76.7 | 80.4 | 44,044 | 321,295 | 79.6 | 1 | 1 | 9 | 283 | 323 |
| reconciler v3 | 81.1 | 80.4 | 39,752 | 173,209 | 82.6 | 0 | 0 | 9 | 176 | 195 |

The set has 1,570 true register, 1,379 GSTR-2B and 1,138 payment links.
The oracle reproduces 58 of the 60 cases exactly under v1, v2 and v3 alike; both misses are the same irreducible ambiguity: one untagged part payment that either of two open invoices of the same supplier could take (the simulator picks the paid invoice at random).
A first-in first-out tie-break fixed those two but broke one other dev case and one test case, so the linker keeps its original tie-break.
Of the 9 false payment links of student-perdoc-sft under v3 on this set, 3 are such ties and 5 follow from a misread true owner (its amount or number misread, so the payment fits a sibling invoice of the same supplier as a part payment); a veto on payments whose narration names another invoice number turned 3 of them into misses but, through the greedy assignment, raised false payment links to 13 and lowered the oracle to 57 of 60, so it was not adopted.

### Self-consistency (dev only, negative result)

Five replies per document sampled at temperature 0.7 and voted field by field (the modal line count, then the plurality value per field; an identity field with a tied vote is left empty) score close to greedy decoding on the 120 small dev cases (student-perdoc-sft): ITC invoice exact 80.1% greedy vs 80.7% voted under v2, 87.8% vs 88.6% under v3, composite 91.2 vs 91.6 under v3 (paired, greedy minus voted: ITC -0.8 [-2.6, +0.9], p = 0.34; composite -0.4 [-1.5, +0.7], p = 0.45).
A single temperature-0.7 sample scores 79.3% to 80.7% under v2, so greedy is already near the vote; the vote costs 5x the completion tokens and about 3.3x the wall time on one 16 GB card, so the test set was not run with it.
`python scripts/hybrid_vote.py OUT_RUN SAMPLE_RUN...` builds the voted run from cached replies.

### Doc schema v2 (protocol change, 61f4b63)

The per-document SFT v3 adapter (trained on the simulator's diverse identity formats, `fmt_version` 2) fell into a greedy loop inside `invoice_no` on 81 of the 384 small-dev document replies: after a fiscal-year prefix such as `2627` it kept choosing `0` until the 4,096-token cap, so the reply did not parse and the document dropped out of the reconciliation (ITC invoice exact 69.7% against 87.8% for student-perdoc-sft v1, all of the gap from the unparsed documents; on the parsed documents it read every header field better than v1).
Doc schema v2 caps `invoice_no` and `original_invoice_no` at 16 characters (`maxLength` in `doc_json_schema`), the legal maximum of an invoice number under CGST Rule 46(b), so grammar-constrained decoding has to close the string.
It is the default for every arm from 61f4b63 on, including the shipped system; the reconciler (v3) is unchanged.
Sanity check on an adapter that never looped (student-perdoc-sft v1, fresh replies, schema v2 vs v1): small dev ITC invoice exact 87.9% vs 87.8%, composite 91.3 vs 91.2, context 90.7% vs 90.7%; big dev ITC 81.2% vs 81.1%, composite 82.6 vs 82.6, context 80.4% vs 80.4%.
Two cases of the 12-case realworld set carry an 18-character invoice number (beyond the Rule 46 limit, which that hand-built set did not enforce), so no arm can read those two fields under v2; every other set's invoice numbers are at most 16 characters long.
Results labelled "doc schema v2" below were run with fresh replies under this protocol; earlier rows are schema v1.

### Ship rule for the v3 adapters (pre-registered 2026-10-25 02:21 IST, before their final numbers)

The small dev set uses the simulator's original (`fmt_version` 1) identity formats, which student-perdoc-sft v1 was trained on, so "beats v1 on sim dev" is biased against adapters trained on the diverse formats.
Candidates: student-perdoc-sft v3 (pd3), its GRPO final (pd3g287), the abstention SFT (pd3a: identity fields not visible on the page blanked in the SFT targets) and its GRPO final, if it lands in time.
All of them, and student-perdoc-sft v1 as the reference, are run under doc schema v2 and reconciler v3.

A candidate ships instead of student-perdoc-sft v1 if and only if:
- (a) it is non-inferior on simulated dev: the paired ITC invoice exact delta against v1 has a 95% CI lower bound of at least -3.0 points on both the small (120) and the big (60) dev set;
- (b) on the realinv per-document set it beats v1 on ITC doc exact and on the mean of invoice number and invoice date accuracy, with a lower invented-identity rate.

Among the candidates that pass (a), the best on (b) is chosen.
That candidate and v1 are then run once on the simulated test set (paired, schema v2; this is v1's second test run, under a protocol change applied to both arms) and scored once on realinv2, a fresh held-out set of about 30 real invoices labelled the same way.
From this point realinv is a selection set; realinv2 is never used for selection.
Added 2026-10-25 02:45 IST (commit 2d18998), before anything was scored on realinv2: if no candidate passes, student-perdoc-sft v1 stays and the test set is not run again.
realinv2 is scored for v1 as the shipped model's held-out real-document check; the four v3 candidates are scored on it as an exploratory replication after the ship decision was locked, and nothing on realinv2 can change that decision.

### The v3 per-document adapters (doc schema v2, measured, not shipped)

Three adapters were trained tonight against the identity inventions found on the real documents, and evaluated under doc schema v2 and reconciler v3 against student-perdoc-sft v1 run the same way:
- pd3: per-document SFT on simulator rows with diverse per-supplier invoice-number and date formats (`fmt_version` 2);
- pd3g287: GRPO from pd3 with the per-document reward (287 steps, one pass over 1,147 hard documents);
- pd3a: as pd3, but an identity field (supplier GSTIN, invoice number, invoice date) that the page does not show is "" in the SFT target, so the model is taught to leave it empty.

A GRPO run from pd3a was planned but dropped (its host stopped responding), and none of the three passes the pre-registered rule, so student-perdoc-sft v1 stays the shipped adapter and the test set was not run again.

**Simulated dev under doc schema v2 (paired against student-perdoc-sft v1 under schema v2, bootstrap 95% CI over cases).**

| dev set | run | ITC invoice exact % | Context acc % | Match acc % | Composite | unparsed doc replies | ITC delta [95% CI] | Composite delta [95% CI] | rule (a) |
|---|---|---|---|---|---|---|---|---|---|
| small (120) | student-perdoc-sft v1 | 87.9 | 90.7 | 92.4 | 91.3 | 0 | | | |
| small (120) | pd3 | 86.2 | 85.7 | 91.8 | 90.1 | 3 | -1.8 [-4.4, +0.7] | -1.2 [-2.8, +0.4] | fails |
| small (120) | pd3g287 | 86.2 | 86.4 | 90.7 | 89.7 | 2 | -1.7 [-4.5, +0.9] | -1.5 [-3.2, +0.0] | fails |
| small (120) | pd3a | 83.1 | 86.4 | 90.0 | 88.2 | 3 | -4.8 [-8.4, -1.5] | -3.0 [-5.1, -1.1] | fails |
| big (60) | student-perdoc-sft v1 | 81.2 | 80.4 | 89.4 | 82.6 | 1 | | | |
| big (60) | pd3 | 80.0 | 78.5 | 87.4 | 81.5 | 5 | -1.3 [-2.5, -0.1] | -1.1 [-1.9, -0.4] | passes |
| big (60) | pd3g287 | 80.3 | 79.1 | 86.2 | 81.9 | 1 | -1.0 [-2.1, +0.1] | -0.7 [-1.7, +0.4] | passes |
| big (60) | pd3a | 78.0 | 78.3 | 84.8 | 80.4 | 1 | -3.3 [-4.7, -1.9] | -2.3 [-3.2, -1.3] | fails |

Rule (a) needs a lower bound of at least -3.0 on both sets; every candidate misses it on the small set, whose identity formats are the ones v1 was trained on, and pd3a misses it on both.
The unparsed replies left under schema v2 are long hard-case documents that run into the 4,096-token cap inside the line items, not invoice-number loops.
Under schema v1 the same pd3 adapter left 81 small-dev replies unparsed (ITC 69.7%); GRPO cut the loop to 38 replies at step 100 and 4 at step 125 (old schema, small dev), before the schema change made it moot.
False links stayed at 0 register and 0 GSTR-2B for every run, with 1 false payment link on small dev and 8 to 12 on big dev (v1: 2 and 9).

**realinv under doc schema v2 (42 real documents; a selection set from 02:21 on).**

| run | cap hits | GSTIN | Invoice no | Date | mean no + date | ITC doc exact | Invented identity | Doc reward | identity blanks (right / wrong) | wrong invoice no in sim format |
|---|---|---|---|---|---|---|---|---|---|---|
| student-perdoc-sft v1 | 0 | 66.7 | 30.9 | 50.0 | 40.5 | 57.1 | 8.8 | 0.687 | 0 / 0 | 18 of 29 |
| pd3 (v3 SFT) | 1 | 66.7 | 47.6 | 52.4 | 50.0 | 50.0 | 8.9 | 0.702 | 0 / 0 | 0 of 21 |
| pd3g287 (GRPO from pd3) | 1 | 71.4 | 21.4 | 69.0 | 45.2 | 54.8 | 0.0 | 0.762 | 17 / 22 | 0 of 2 |
| pd3a (v3 abstention SFT) | 0 | 59.5 | 42.9 | 66.7 | 54.8 | 57.1 | 3.5 | 0.817 | 24 / 16 | 0 of 10 |
| ensemble A (v1 + pd3 + pd3a) | 0 | 69.0 | 42.9 | 59.5 | 51.2 | 57.1 | 0.0 | 0.823 | 26 / 15 | 0 of 5 |
| ensemble B (A + pd3g287 confirmation) | 0 | 71.4 | 42.9 | 59.5 | 51.2 | 57.1 | 0.0 | 0.779 | 16 / 14 | 0 of 5 |

On realinv no candidate passes rule (b) either: pd3 and pd3a read invoice numbers and dates better than v1 but do not beat its ITC doc exact (50.0% and a tie at 57.1%), and pd3g287 trails it (54.8%).
The format fix worked as intended: v1 writes 18 of its 29 wrong invoice numbers in the simulator's own formats, the three v3 adapters none.
The two ways of teaching abstention behave very differently: pd3a (blank SFT targets) leaves 24 unseen identities empty, invents 3.5% of identities against v1's 8.8% and reads dates best (66.7% against 50.0%), while GRPO from pd3 drives invention to 0 by over-abstaining (22 visible identities left empty, invoice number accuracy 21.4%).
"Identity blanks" counts empty GSTIN, invoice number and date fields in parsed replies, split by whether the truth value is visible in the model's input text; v1 and pd3 never leave one empty.

**realinv2: held-out real documents (30 invoices from 30 suppliers, none in realinv; scored once).**
student-perdoc-sft v1 is the shipped model's held-out check; the other rows are exploratory, scored after the ship decision was locked, and cannot change it.

| run | cap hits | GSTIN | Invoice no | Date | mean no + date | ITC doc exact | Invented identity | Doc reward | identity blanks (right / wrong) | wrong invoice no in sim format |
|---|---|---|---|---|---|---|---|---|---|---|
| student-perdoc-sft v1 | 0 | 73.3 | 40.0 | 46.7 | 43.3 | 70.0 | 2.6 | 0.693 | 0 / 0 | 10 of 18 |
| pd3 (v3 SFT) | 0 | 66.7 | 76.7 | 53.3 | 65.0 | 60.0 | 5.3 | 0.728 | 0 / 0 | 0 of 7 |
| pd3g287 (GRPO from pd3) | 0 | 73.3 | 30.0 | 60.0 | 45.0 | 60.0 | 0.0 | 0.740 | 7 / 16 | 0 of 1 |
| pd3a (v3 abstention SFT) | 0 | 66.7 | 50.0 | 80.0 | 65.0 | 66.7 | 2.6 | 0.784 | 10 / 10 | 0 of 3 |
| ensemble A (v1 + pd3 + pd3a) | 0 | 70.0 | 60.0 | 63.3 | 61.7 | 70.0 | 0.0 | 0.795 | 11 / 7 | 0 of 1 |
| ensemble B (A + pd3g287 confirmation) | 0 | 70.0 | 60.0 | 63.3 | 61.7 | 70.0 | 0.0 | 0.761 | 6 / 7 | 0 of 1 |

On fresh documents the shipped v1 reads 73.3% of GSTINs, 40.0% of invoice numbers and 46.7% of dates, with ITC doc exact 70.0%, and again writes 10 of its 18 wrong invoice numbers in the simulator's formats.
Both findings replicate: no v3 adapter writes a simulator-format number, pd3a abstains and reads dates best (80.0%), and pd3g287 again over-abstains (16 visible invoice numbers left empty) with no invented identity.
The ensemble rows are explained in the next section.

### Ensemble of v1, pd3 and pd3a (combiner rule pre-registered 2026-10-25 03:10 IST, before any ensemble number)

The ensemble combines the saved per-document replies of student-perdoc-sft v1, pd3 and pd3a offline (no new model calls), then runs the same reconciler (v3) and scorer.
Per document and per field, over the three parsed DocRecords (an unparsed reply is absent):
- Identity fields (supplier_gstin, invoice_no, invoice_date, original_invoice_no): the value that at least 2 of the 3 models emit, compared after the scorer's normalisation (`norm`, and `parse_date` for the date), written as the first of v1, pd3a, pd3 that emitted it; otherwise "" (abstain, so the v3 identity fill can act). A "" counts as a vote.
- All other header fields and the lines array: v1's value (the dev-validated model); if v1 is unparsed, the value the other two agree on, else pd3a's (or the only parsed one).
- No tuning after this commit.

It is scored on small and big dev (schema v2 replies), realinv (selection set), realinv2 (exploratory: that set had already been seen for the three members) and semireal, and checked against rules (a) and (b); the test set is not run for it unless decided separately.

Ablation, variant B (pre-registered 2026-10-25 03:13 IST, commit 5c95f97, after variant A's realinv and realinv2 numbers had been computed and before any variant B number): as A, but when no identity value has two votes and pd3g287 emitted a non-blank value equal (after the same normalisation) to one of the three members' values, that value is used instead of "".
Rationale: pd3g287 almost never invents an identity (0% on both real sets), so a non-blank value from it is a confirmation rather than a vote.
Variant A stays the primary ensemble whichever scores higher; there are no other variants.

Amendment (user decision after the ensemble results, committed 2026-10-25 03:20 IST in 8419cf6, before any variant B semireal number existed): the per-invoice ITC tie on realinv is structural (B takes all ITC-relevant fields from v1), so it no longer counts as a fail.
Replacement criterion (b'): on semireal under schema v2, pooled over all 54 cases (clean 9 + sim-s0 9 + sim-s1to4 36), ensemble B must be at least student-perdoc-sft v1 on both ITC invoice exact and match accuracy (point estimates; paired deltas and CIs reported).
Pooled means the mean of the per-case values over the 54 cases (the case mean the eval tables report), with a paired bootstrap of 10,000 case resamples (seed 0) for the CIs; fixed before any B semireal number.
Variant A is not eligible (it fails rule (a)).
If B passes (b'), the frozen test set is run once under schema v2 for v1, pd3, pd3a and pd3g287 and B is built offline from those replies (v1's second test run, the members' first, the protocol change applied to all); B then becomes the shipped configuration. If it fails, v1 ships and the test set stays untouched.

**Ensemble results (0 new model calls; reconciler v3, doc schema v2; paired against student-perdoc-sft v1).**

| dev set | run | ITC invoice exact % | Context acc % | Match acc % | Composite | ITC delta [95% CI] | Composite delta [95% CI] | rule (a) |
|---|---|---|---|---|---|---|---|---|
| small (120) | student-perdoc-sft v1 | 87.9 | 90.7 | 92.4 | 91.3 | | | |
| small (120) | ensemble A | 86.1 | 90.7 | 90.5 | 89.6 | -1.9 [-3.2, -0.8] | -1.6 [-2.6, -0.8] | fails |
| small (120) | ensemble B | 87.4 | 90.7 | 92.0 | 90.8 | -0.6 [-1.7, +0.4] | -0.5 [-1.2, +0.2] | passes |
| big (60) | student-perdoc-sft v1 | 81.2 | 80.4 | 89.4 | 82.6 | | | |
| big (60) | ensemble A | 78.9 | 80.4 | 86.0 | 80.9 | -2.3 [-3.2, -1.5] | -1.8 [-2.6, -1.0] | fails |
| big (60) | ensemble B | 80.7 | 80.4 | 87.5 | 82.2 | -0.5 [-1.0, -0.1] | -0.5 [-0.8, +0.0] | passes |

False links stay at 0 register and 0 GSTR-2B (payment: 2 on small dev, 12 and 10 on big dev; v1 2 and 9).
On realinv (table above) both variants raise the mean of invoice number and date accuracy from 40.5% to 51.2% and invent no identity (v1 8.8%), but tie v1 on ITC doc exact (57.1%): the ensemble takes amounts, categories and purposes from v1, and the identity fields do not enter that metric.
So variant A fails rule (a) (small-dev lower bound -3.2) and variant B, which passes (a), fails rule (b) on the tie ("beats" was pre-registered); neither ships under the rule as first registered; the user then replaced (b) for B by a pooled semireal criterion (amendment above), which B also fails (below).
On sim dev an identity left empty where v1 had read it right is only recovered when the book fill finds exactly one matching entry, which is consistent with A (more abstentions) trailing v1 on match accuracy and B (fewer) staying level; the per-field split was not measured.

**semireal under doc schema v2 (real documents with simulated books, end to end through reconciler v3; exploratory for the adapters, criterion (b') for ensemble B).**

| level | run | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | Match acc % | Composite | fills (right) | register / GSTR-2B / payment missed | false links |
|---|---|---|---|---|---|---|---|---|---|---|
| clean (9 cases) | student-perdoc-sft v1 | 59.6 | 100.0 | 0 | 10,065 | 62.8 | 68.7 | 8 (8) | 14 / 14 / 7 of 39 / 38 / 21 | 0 |
| clean (9 cases) | pd3a | 48.0 | 92.9 | 0 | 25,803 | 67.9 | 66.0 | 8 (8) | 14 / 14 / 8 of 39 / 38 / 21 | 0 |
| clean (9 cases) | pd3 | 56.7 | 100.0 | 0 | 10,001 | 71.2 | 70.5 | 6 (6) | 12 / 12 / 7 of 39 / 38 / 21 | 0 |
| clean (9 cases) | pd3g287 | 61.8 | 100.0 | 0 | 9,948 | 71.3 | 73.0 | 13 (13) | 14 / 14 / 8 of 39 / 38 / 21 | 0 |
| clean (9 cases) | ensemble A | 53.2 | 100.0 | 0 | 21,173 | 65.4 | 66.8 | 8 (8) | 14 / 14 / 7 of 39 / 38 / 21 | 0 |
| clean (9 cases) | ensemble B | 58.7 | 100.0 | 0 | 11,173 | 69.6 | 70.2 | 9 (9) | 13 / 13 / 7 of 39 / 38 / 21 | 0 |
| sim, seed 0 (9) | student-perdoc-sft v1 | 59.6 | 100.0 | 0 | 9,495 | 66.1 | 69.3 | 7 (7) | 13 / 12 / 8 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | pd3a | 52.5 | 92.9 | 0 | 23,614 | 70.5 | 67.7 | 9 (9) | 13 / 13 / 8 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | pd3 | 58.1 | 100.0 | 0 | 8,992 | 72.9 | 71.0 | 6 (6) | 12 / 11 / 7 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | pd3g287 | 61.8 | 100.0 | 0 | 8,939 | 71.4 | 73.1 | 11 (11) | 15 / 14 / 8 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | ensemble A | 59.6 | 100.0 | 0 | 9,524 | 71.1 | 70.6 | 8 (8) | 13 / 12 / 8 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | ensemble B | 59.6 | 100.0 | 0 | 9,524 | 71.3 | 70.7 | 8 (8) | 13 / 12 / 8 of 42 / 34 / 27 | 0 |
| sim, seeds 1-4 (36) | student-perdoc-sft v1 | 57.9 | 100.0 | 0 | 6,118 | 63.9 | 68.4 | 27 (27) | 55 / 52 / 29 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | pd3a | 54.5 | 96.4 | 0 | 18,814 | 70.7 | 69.4 | 37 (37) | 50 / 48 / 30 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | pd3 | 56.7 | 94.6 | 0 | 5,766 | 71.0 | 70.5 | 17 (17) | 52 / 48 / 28 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | pd3g287 | 60.7 | 100.0 | 0 | 9,452 | 71.6 | 72.8 | 53 (53) | 59 / 56 / 32 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | ensemble A | 56.2 | 100.0 | 0 | 9,380 | 67.9 | 68.7 | 30 (30) | 57 / 53 / 29 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | ensemble B | 57.8 | 100.0 | 0 | 6,610 | 69.3 | 69.7 | 32 (32) | 55 / 52 / 29 of 160 / 143 / 103 | 0 |

Pooled over the 54 cases (case mean, paired bootstrap of 10,000 case resamples):

| run | ITC invoice exact % (delta vs v1 [95% CI], p) | Match acc % (delta [95% CI], p) | Composite (delta [95% CI], p) |
|---|---|---|---|
| student-perdoc-sft v1 | 58.5 | 64.1 | 68.6 |
| pd3g287 | 61.1 (+2.6 [-1.4, +6.7], p = 0.20) | 71.5 (+7.4 [+1.4, +13.7], p = 0.02) | 72.9 (+4.3 [+1.7, +7.0], p < 0.005) |
| pd3 | 56.9 (-1.5 [-4.7, +1.6], p = 0.33) | 71.4 (+7.2 [+1.9, +12.9], p = 0.01) | 70.6 (+2.0 [+0.3, +3.6], p = 0.02) |
| pd3a | 53.1 (-5.4 [-11.0, -0.3], p = 0.04) | 70.2 (+6.1 [+0.2, +12.4], p = 0.04) | 68.6 (-0.0 [-3.2, +3.0], p = 0.99) |
| ensemble A | 56.3 (-2.2 [-5.2, +0.0], p = 0.06) | 68.0 (+3.9 [-0.6, +9.0], p = 0.10) | 68.7 (+0.1 [-1.9, +1.8], p = 0.89) |
| ensemble B | 58.3 (-0.2 [-1.0, +0.8], p = 0.62) | 69.7 (+5.6 [+1.7, +10.2], p < 0.005) | 69.9 (+1.3 [+0.5, +2.4], p < 0.005) |

Decision: ensemble B fails criterion (b'): its pooled ITC invoice exact is 58.27% against v1's 58.47% (4 cases worse, 1 better), although it matches 5.6 points better.
student-perdoc-sft v1 stays the shipped adapter under doc schema v2, and the test set was not run again for any of tonight's candidates.

Every v3 adapter matches better than v1 on the real documents (+6 to +7 points pooled): the identity fix pays off end to end in register and GSTR-2B links, with all fills correct and no false link.
pd3g287 is the strongest model on these real documents end to end (pooled ITC +2.6 points, not significant, and composite +4.3, significant), yet it failed rule (a) on the small simulated dev set, whose identity formats v1 was trained on.
That tension is the main open finding for the next round: the simulated dev sets reward v1's familiarity with the simulator's formats, while the real documents reward the format and abstention fixes; rule (a) was kept as pre-registered, so no ship claim is made for pd3g287.
pd3a's abstentions cost ITC on real documents (underclaim Rs 19k to 26k per level against v1's Rs 6k to 10k), because an empty identity is recovered only when exactly one book entry matches.
The semireal books follow the simulator's distributions and the labels were drafted by Claude, so these are real-document reading results, not a real-world book result.

### Decision update (user override, committed 2026-10-25 03:27 IST in a50f90b, before any test-set number for it)

pd3g287 (GRPO from pd3, 287 steps; adapter `adapter_model.safetensors` sha256 8941cff5...3655) ships instead of student-perdoc-sft v1, by the user's decision.
This overrides pre-registered rule (a): pd3g287's paired ITC delta on the small simulated dev set has a 95% CI lower bound of -4.5, below the -3.0 limit.
The user's reason is the real-document evidence: on semireal, pooled over 54 cases under doc schema v2, pd3g287 scores composite +4.3 [+1.7, +7.0], ITC invoice exact +2.6 (not significant) and match accuracy +7.4 against v1.
The simulated dev sets are rendered in the simulator's original (`fmt_version` 1) identity formats, which v1 was trained on and the pd3-family adapters were not.
This is a post-hoc override of a pre-registered rule, made after the dev and real-document results were known, and it is disclosed as such.
The decision is fixed before the test run: pd3g287 and v1 are each run once on the frozen test set under doc schema v2 and reconciler v3 (paired; v1's second test run, pd3g287's first), and the result is reported below whatever it is.

### GRPO from the per-document SFT (dev only, measured, not shipped)

A GRPO snapshot (step 75) trained from student-perdoc-sft v2 with the per-document reward was measured on both dev sets under reconciler v3; it is not the shipped adapter and was never run on test.

| dev set | run | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | Match acc % | Composite |
|---|---|---|---|---|---|---|---|
| small (120) | student-perdoc-sft v1 | 87.8 | 90.7 | 12,044 | 31,103 | 92.4 | 91.2 |
| small (120) | student-perdoc-sft v2 | 88.9 | 90.0 | 14,000 | 21,813 | 93.7 | 92.0 |
| small (120) | GRPO step 75 | 89.8 | 91.4 | 4,884 | 20,985 | 93.9 | 92.6 |
| big (60) | student-perdoc-sft v1 | 81.1 | 80.4 | 39,752 | 173,209 | 89.2 | 82.6 |
| big (60) | student-perdoc-sft v2 | 82.2 | 83.4 | 36,405 | 179,894 | 90.0 | 83.5 |
| big (60) | GRPO step 75 | 81.8 | 83.0 | 36,394 | 179,464 | 89.8 | 83.4 |

Paired (GRPO step 75 minus reference, bootstrap 95% CI over cases):

| dev set | reference | ITC invoice exact | Context acc | Composite |
|---|---|---|---|---|
| small | student-perdoc-sft v1 | +2.0 [-0.6, +4.6], p = 0.13 | -0.7 [-5.8, +4.7], p = 0.81 | +1.3 [-0.2, +2.9], p = 0.09 |
| small | student-perdoc-sft v2 | +0.9 [-0.5, +2.5], p = 0.23 | +0.8 [-2.2, +4.2], p = 0.62 | +0.5 [-0.3, +1.5], p = 0.20 |
| big | student-perdoc-sft v1 | +0.8 [-0.6, +2.1], p = 0.27 | +2.1 [-0.2, +4.8], p = 0.10 | +0.8 [-0.2, +1.8], p = 0.13 |
| big | student-perdoc-sft v2 | -0.4 [-1.0, +0.2], p = 0.19 | +0.3 [-1.3, +2.2], p = 0.68 | -0.1 [-0.3, +0.1], p = 0.20 |

No difference is significant; against its own starting point (v2) the snapshot is neutral on both dev sets, with lower ITC overclaim on small dev only.
False links stayed at 0 register, 0 GSTR-2B and 0 payment on small dev, and 0 / 0 / 8 on big dev (student-perdoc-sft v1: 9 payment).
On the real documents below it reads invoice numbers and dates worse than either SFT adapter, so it was not carried further.

### Real purchase documents (eval only)

Two eval-only sets are built from 42 real purchase documents of one buyer (a caterer), labelled by Claude (Opus) from the page images in two passes with automatic arithmetic and GSTIN checks, not verified by a human.
The documents, their text and the labels are client data: they are never used for training and stay out of this repository; only the aggregate numbers below are published.
The model sees the OCR or text-layer output, not the image: only 26 of 39 printed supplier GSTINs, 33 of 42 invoice numbers and 28 of 42 invoice dates survive into that text, so part of every error below is OCR loss.
No line in the set is blocked under s.17(5), so ITC accuracy on it measures amount reading and the absence of false blocks, not blocking judgment.

**Per-document reading (42 documents, no books).**
Each document is sent alone, exactly as in hybrid mode (`build_doc_messages`, constrained to `doc_json_schema`), and scored field by field against the label (a label's listed alternates also count); "invented identity" is the share of fields whose true value is empty (not printed) where the model returned a value.

| run | GSTIN | Invoice no | Date | Taxable | Total | Line count | Line amounts | Category | Purpose | ITC doc exact | Invented identity | Doc reward |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| student-base | 59.5 | 52.4 | 73.8 | 57.1 | 61.9 | 76.2 | 57.8 | 42.6 | 42.6 | 42.9 | 9.6 | 0.689 |
| student-perdoc-sft | 66.7 | 30.9 | 47.6 | 52.4 | 64.3 | 81.0 | 51.0 | 50.0 | 49.0 | 57.1 | 8.8 | 0.689 |
| student-perdoc-grpo (step 75) | 71.4 | 21.4 | 40.5 | 59.5 | 64.3 | 81.0 | 53.4 | 52.5 | 54.5 | 54.8 | 12.3 | 0.692 |
| student-base, blank-if-not-printed filter | 59.5 | 52.4 | 61.9 | 57.1 | 61.9 | 76.2 | 57.8 | 42.6 | 42.6 | 42.9 | 9.6 | 0.747 |
| student-perdoc-sft, blank-if-not-printed filter | 66.7 | 30.9 | 35.7 | 52.4 | 64.3 | 81.0 | 51.0 | 50.0 | 49.0 | 57.1 | 8.8 | 0.762 |

The per-document adapters read amounts, categories and purposes better than the base model but invoice numbers and dates much worse, and the cause is invention, not abstention: none of the three runs ever left these fields empty.
Of the 29 invoice numbers student-perdoc-sft got wrong, 23 are not in the document text at all and 18 have the simulator's own number formats (for example TAX/0123/26-27 or 26-27-INV-00412); of base's 20 wrong numbers, 15 are other numbers that are in the text and none has a simulator format.
GRPO from the per-document SFT (step 75) amplifies this (29 wrong numbers not in the text, 20 in simulator formats) even though its reward credits abstention.
The per-document SFT learned the simulator's identity formats, which the simulated test set cannot reveal; the simulator's number and date formats are being widened for the next training round.
The two filter rows blank an invoice number or date that the document text does not support, with reconciler v3's own check (`fill.py`); this is not what v3 does on its own (v3 replaces such a value only when exactly one book entry of the same GSTIN matches, and otherwise passes it on).
The number check rejected only wrong numbers (6 for base, 17 for student-perdoc-sft), but the date check also rejected 5 right dates per model (printed forms it does not recognise, or OCR-damaged dates the model reconstructed).

**semireal: the same documents with simulated books.**
The 39 documents with a known identity (3 with an illegible or invalid GSTIN are left out, which flatters reading) become 9 buyer-month cases whose purchase register, GSTR-2B and bank statement come from the simulator's own functions; `clean` plants no book discrepancies, `sim` plants discrepancies at the simulator's medium rate (7 to 16 per seed over 39 documents), with five seeds (s0 is the twin of `clean`).
Everything is reconciler v3; the oracle (true records through v3) is exact except one travel agent's invoice whose printed total includes a pass-through airfare, which `repair` resets to taxable value plus tax so its payment no longer links (Rs 420.71 deferred in two seeds).
The books follow the simulator's distributions, which the reconciler was developed on, so this set measures real document reading feeding the full reconciliation, not real book messiness; report each level on its own, never as a real-world book result.

| level | run | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | Match acc % | Composite | fills (right) | register / GSTR-2B / payment missed | false links |
|---|---|---|---|---|---|---|---|---|---|---|
| clean (9 cases) | student-base | 42.5 | 92.9 | 0 | 26,215 | 70.8 | 64.3 | 3 (3) | 13 / 13 / 7 of 39 / 38 / 21 | 0 |
| clean (9 cases) | student-perdoc-sft | 59.6 | 100.0 | 0 | 10,065 | 64.6 | 69.1 | 8 (8) | 13 / 13 / 7 of 39 / 38 / 21 | 0 |
| clean (9 cases) | student-perdoc-grpo (step 75) | 61.8 | 100.0 | 0 | 12,106 | 60.9 | 70.1 | 8 (8) | 18 / 18 / 8 of 39 / 38 / 21 | 0 |
| sim, seed 0 (9) | student-base | 43.9 | 100.0 | 0 | 24,476 | 70.4 | 65.2 | 3 (3) | 14 / 13 / 10 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | student-perdoc-sft | 59.6 | 100.0 | 0 | 9,495 | 66.1 | 69.3 | 7 (7) | 13 / 12 / 8 of 42 / 34 / 27 | 0 |
| sim, seed 0 (9) | student-perdoc-grpo (step 75) | 61.8 | 100.0 | 0 | 11,536 | 59.6 | 69.8 | 8 (8) | 18 / 18 / 9 of 42 / 34 / 27 | 0 |
| sim, seeds 1-4 (36) | student-base | 46.0 | 100.0 | 0 | 22,093 | 71.1 | 66.6 | 14 (14) | 56 / 52 / 34 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | student-perdoc-sft | 58.6 | 100.0 | 0 | 6,118 | 63.5 | 68.6 | 28 (28) | 57 / 53 / 29 of 160 / 143 / 103 | 0 |
| sim, seeds 1-4 (36) | student-perdoc-grpo (step 75) | 59.6 | 98.2 | 0 | 11,618 | 59.5 | 69.2 | 34 (34) | 75 / 72 / 34 of 160 / 143 / 103 | 0 |

Reconciler v3's identity fill worked on real documents: every fill was correct (student-base 20 of 20, student-perdoc-sft 43 of 43, GRPO step 75 50 of 50 over the three levels), and no run made a false register, GSTR-2B or payment link.
student-perdoc-sft leads student-base by 13 to 17 points of ITC invoice exact but trails it by 5 to 8 points of match accuracy, the matching cost of its invented identities, and it needed about twice as many fills.
GRPO step 75 adds 1 to 2 points of ITC over student-perdoc-sft but loses another 4 to 7 points of match accuracy and misses more register links (18 vs 13 of 39 on `clean`), in line with its worse invoice numbers on the per-document set.
Parser limitation found while building the set (not fixed, the reconciler is frozen): the fixed-width register reader shifts a row whose GSTIN cell is empty, so the builder renders such registers in CSV layout.

### Overall (120 simulator cases)

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 120 | 10.9 [7.4, 14.6] | 30.7 [25.3, 36.1] | 465,489 [352,982, 584,747] | 59,776 [20,725, 116,515] | 402,137 [316,132, 496,334] | 64.0 [61.9, 65.9] | 91.0 [89.2, 92.2] | 99.2 [97.5, 100.0] | 58.2 [56.6, 59.6] |
| student-base hybrid | 120 | 44.3 [41.4, 47.3] | 67.6 [63.4, 71.5] | 72,728 [38,279, 113,854] | 542,029 [399,673, 700,714] | 578,549 [437,977, 741,066] | 63.0 [61.0, 65.0] | 87.1 [86.4, 87.9] | 100.0 [100.0, 100.0] | 65.1 [64.0, 66.1] |
| student-base hybrid (reconciler v2) | 120 | 53.3 [50.0, 56.7] | 67.9 [63.8, 71.9] | 84,460 [48,143, 128,505] | 397,572 [292,494, 509,525] | 440,303 [334,764, 555,140] | 72.7 [70.7, 74.8] | 88.0 [87.3, 88.8] | 100.0 [100.0, 100.0] | 69.8 [68.6, 71.1] |
| student-base hybrid (reconciler v3) | 120 | 55.2 [51.9, 58.6] | 67.9 [63.8, 71.9] | 85,156 [49,028, 129,037] | 357,306 [258,737, 463,217] | 403,643 [301,406, 510,957] | 77.3 [75.4, 79.2] | 88.6 [87.8, 89.4] | 100.0 [100.0, 100.0] | 71.3 [70.1, 72.5] |
| student-sft hybrid | 120 | 38.2 [35.6, 40.9] | 57.5 [53.6, 61.3] | 19,424 [7,041, 34,455] | 686,534 [519,385, 869,921] | 688,739 [525,496, 871,524] | 61.4 [59.6, 63.4] | 86.2 [85.2, 87.3] | 100.0 [100.0, 100.0] | 63.3 [62.3, 64.3] |
| student-sft hybrid (reconciler v2) | 120 | 44.4 [41.6, 47.3] | 57.5 [53.6, 61.3] | 24,891 [11,087, 42,294] | 602,684 [450,645, 769,581] | 603,720 [452,684, 769,781] | 70.3 [68.2, 72.4] | 87.1 [86.0, 88.1] | 100.0 [100.0, 100.0] | 66.9 [65.7, 68.2] |
| student-sft hybrid (reconciler v3) | 120 | 46.8 [43.8, 49.8] | 57.5 [53.6, 61.3] | 27,094 [12,831, 44,754] | 579,879 [435,854, 739,514] | 579,294 [435,683, 736,593] | 76.1 [74.0, 78.2] | 87.8 [86.7, 88.9] | 100.0 [100.0, 100.0] | 68.8 [67.5, 70.2] |
| student-perdoc-sft hybrid | 120 | 62.9 [60.2, 65.3] | 82.7 [79.3, 85.8] | 19,053 [6,187, 36,486] | 436,024 [315,294, 571,946] | 440,860 [322,330, 574,220] | 72.2 [70.2, 74.1] | 92.0 [91.3, 92.8] | 100.0 [100.0, 100.0] | 73.2 [72.1, 74.4] |
| student-perdoc-sft hybrid (reconciler v2) | 120 | 73.1 [70.8, 75.3] | 82.7 [79.3, 85.8] | 23,757 [9,550, 42,321] | 297,661 [207,995, 406,136] | 305,093 [215,153, 411,300] | 80.7 [78.8, 82.6] | 92.3 [91.5, 93.0] | 100.0 [100.0, 100.0] | 77.8 [76.6, 79.0] |
| student-perdoc-sft hybrid (reconciler v3) | 120 | 79.9 [77.5, 82.4] | 82.7 [79.3, 85.8] | 27,183 [12,495, 45,815] | 203,126 [138,671, 278,037] | 215,451 [150,808, 290,143] | 88.7 [86.9, 90.6] | 93.8 [93.0, 94.6] | 100.0 [100.0, 100.0] | 82.7 [81.2, 84.4] |
| student-perdoc-sft-v2 hybrid | 120 | 63.3 [60.6, 66.1] | 83.6 [80.0, 86.8] | 25,888 [11,450, 44,211] | 448,650 [337,891, 568,733] | 450,437 [342,534, 570,806] | 68.1 [65.8, 70.5] | 91.8 [91.0, 92.5] | 100.0 [100.0, 100.0] | 72.4 [71.1, 73.7] |
| student-perdoc-sft-v2 hybrid (reconciler v3) | 120 | 81.8 [79.7, 84.0] | 83.6 [80.0, 86.8] | 34,409 [18,311, 53,983] | 164,628 [117,658, 216,980] | 178,646 [130,931, 229,316] | 86.6 [84.6, 88.7] | 93.7 [92.9, 94.5] | 100.0 [100.0, 100.0] | 82.5 [81.1, 84.0] |
| heuristic hybrid (code alone) | 120 | 10.4 [8.8, 12.1] | 40.9 [34.7, 46.3] | 29,728 [14,899, 51,425] | 743,155 [574,896, 930,170] | 726,778 [561,474, 909,353] | 35.2 [33.3, 37.2] | 58.4 [57.6, 59.1] | 100.0 [100.0, 100.0] | 47.0 [46.2, 47.8] |
| heuristic hybrid (code alone) (reconciler v3) | 120 | 11.1 [9.5, 12.7] | 40.9 [34.7, 46.3] | 30,075 [15,301, 51,702] | 735,840 [568,629, 920,114] | 719,127 [554,115, 900,987] | 36.3 [34.4, 38.2] | 58.6 [57.8, 59.3] | 100.0 [100.0, 100.0] | 47.4 [46.6, 48.2] |

### test_iid

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 60 | 8.1 | 28.6 | 610,319 | 90,586 | 542,383 | 64.5 | 90.6 | 98.3 | 57.5 |
| student-base hybrid | 60 | 40.0 | 66.4 | 105,764 | 752,515 | 810,318 | 60.7 | 87.7 | 100.0 | 63.7 |
| student-base hybrid (reconciler v2) | 60 | 51.3 | 66.9 | 122,572 | 534,456 | 597,672 | 73.0 | 88.6 | 100.0 | 69.6 |
| student-base hybrid (reconciler v3) | 60 | 53.0 | 66.9 | 122,515 | 488,833 | 559,620 | 78.6 | 89.1 | 100.0 | 71.2 |
| student-sft hybrid | 60 | 40.1 | 59.9 | 4,563 | 928,502 | 924,517 | 60.9 | 87.4 | 100.0 | 63.9 |
| student-sft hybrid (reconciler v2) | 60 | 48.4 | 59.9 | 14,768 | 790,355 | 783,677 | 71.8 | 88.3 | 100.0 | 68.4 |
| student-sft hybrid (reconciler v3) | 60 | 51.4 | 59.9 | 19,213 | 752,049 | 742,092 | 79.2 | 89.1 | 100.0 | 70.9 |
| student-perdoc-sft hybrid | 60 | 67.0 | 84.7 | 34,932 | 527,084 | 538,136 | 76.7 | 92.9 | 100.0 | 75.5 |
| student-perdoc-sft hybrid (reconciler v2) | 60 | 75.6 | 84.7 | 40,224 | 363,510 | 380,232 | 83.3 | 93.1 | 100.0 | 79.2 |
| student-perdoc-sft hybrid (reconciler v3) | 60 | 82.5 | 84.7 | 47,076 | 230,788 | 255,389 | 91.8 | 94.7 | 100.0 | 84.4 |
| student-perdoc-sft-v2 hybrid | 60 | 69.4 | 86.3 | 29,837 | 487,086 | 495,389 | 77.9 | 93.6 | 100.0 | 76.5 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | 60 | 84.0 | 86.3 | 44,644 | 199,038 | 228,769 | 92.6 | 95.5 | 100.0 | 85.1 |
| heuristic hybrid (code alone) | 60 | 10.3 | 39.6 | 39,569 | 981,934 | 968,462 | 35.2 | 57.7 | 100.0 | 46.8 |
| heuristic hybrid (code alone) (reconciler v3) | 60 | 11.2 | 39.6 | 39,759 | 967,588 | 953,927 | 36.6 | 58.0 | 100.0 | 47.3 |

### test_ood

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 60 | 13.7 | 33.2 | 320,659 | 28,966 | 261,891 | 63.5 | 91.4 | 100.0 | 58.9 |
| student-base hybrid | 60 | 48.6 | 68.9 | 39,691 | 331,543 | 346,780 | 65.3 | 86.6 | 100.0 | 66.5 |
| student-base hybrid (reconciler v2) | 60 | 55.2 | 69.2 | 46,347 | 260,687 | 282,933 | 72.4 | 87.5 | 100.0 | 70.0 |
| student-base hybrid (reconciler v3) | 60 | 57.4 | 69.2 | 47,797 | 225,780 | 247,665 | 76.0 | 88.0 | 100.0 | 71.4 |
| student-sft hybrid | 60 | 36.3 | 54.8 | 34,284 | 444,567 | 452,960 | 62.0 | 85.1 | 100.0 | 62.6 |
| student-sft hybrid (reconciler v2) | 60 | 40.5 | 54.8 | 35,014 | 415,013 | 423,762 | 68.8 | 85.9 | 100.0 | 65.4 |
| student-sft hybrid (reconciler v3) | 60 | 42.1 | 54.8 | 34,976 | 407,709 | 416,495 | 73.0 | 86.4 | 100.0 | 66.8 |
| student-perdoc-sft hybrid | 60 | 58.7 | 80.5 | 3,173 | 344,964 | 343,584 | 67.6 | 91.2 | 100.0 | 71.0 |
| student-perdoc-sft hybrid (reconciler v2) | 60 | 70.7 | 80.5 | 7,290 | 231,812 | 229,955 | 78.2 | 91.4 | 100.0 | 76.5 |
| student-perdoc-sft hybrid (reconciler v3) | 60 | 77.3 | 80.5 | 7,290 | 175,465 | 175,513 | 85.6 | 92.9 | 100.0 | 81.0 |
| student-perdoc-sft-v2 hybrid | 60 | 57.2 | 80.5 | 21,940 | 410,214 | 405,486 | 58.3 | 89.9 | 100.0 | 68.3 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | 60 | 79.6 | 80.5 | 24,175 | 130,218 | 128,524 | 80.7 | 91.9 | 100.0 | 79.9 |
| heuristic hybrid (code alone) | 60 | 10.6 | 42.4 | 19,888 | 504,377 | 485,094 | 35.2 | 59.0 | 100.0 | 47.2 |
| heuristic hybrid (code alone) (reconciler v3) | 60 | 11.0 | 42.4 | 20,391 | 504,092 | 484,327 | 36.0 | 59.1 | 100.0 | 47.5 |

### realworld (12 cases, bootstrap 95% CI)

| run | n | ITC invoice exact % | Context acc % | ITC overclaim (Rs) | ITC underclaim (Rs) | ITC net abs err (Rs) | Match acc % | Field F1 % | Schema valid % | Composite (0-100) |
|---|---|---|---|---|---|---|---|---|---|---|
| SFT constrained (full grammar) | 12 | 27.1 [13.9, 40.3] | 72.2 [46.7, 90.5] | 35,924 [16,629, 60,077] | 0 [0, 0] | 34,257 [15,349, 58,864] | 77.6 [72.7, 82.5] | 92.1 [89.2, 94.4] | 100.0 [100.0, 100.0] | 65.8 [62.1, 69.7] |
| student-base hybrid | 12 | 38.9 [26.4, 51.4] | 44.4 [14.3, 73.3] | 165 [0, 495] | 34,691 [14,008, 60,717] | 34,526 [14,008, 60,594] | 79.2 [73.6, 84.4] | 87.0 [83.2, 90.6] | 100.0 [100.0, 100.0] | 67.6 [64.0, 70.8] |
| student-base hybrid (reconciler v2) | 12 | 44.4 [30.6, 56.9] | 44.4 [14.3, 73.3] | 165 [0, 495] | 31,471 [10,371, 58,140] | 31,306 [10,362, 57,963] | 82.3 [77.1, 87.9] | 87.9 [84.1, 91.4] | 100.0 [100.0, 100.0] | 69.8 [65.8, 73.5] |
| student-base hybrid (reconciler v3) | 12 | 44.4 [30.6, 56.9] | 44.4 [14.3, 73.3] | 165 [0, 495] | 31,471 [10,371, 58,140] | 31,306 [10,362, 57,963] | 82.3 [77.1, 87.9] | 87.9 [84.1, 91.4] | 100.0 [100.0, 100.0] | 69.8 [65.8, 73.5] |
| student-sft hybrid | 12 | 28.5 [13.9, 45.1] | 22.2 [5.5, 46.7] | 0 [0, 0] | 45,227 [21,649, 72,068] | 45,227 [21,649, 72,068] | 85.2 [79.0, 90.5] | 88.2 [83.9, 92.5] | 100.0 [100.0, 100.0] | 66.3 [61.4, 71.6] |
| student-sft hybrid (reconciler v2) | 12 | 31.2 [14.6, 49.3] | 22.2 [5.5, 46.7] | 2,700 [0, 8,100] | 42,077 [17,404, 69,740] | 39,437 [14,518, 68,145] | 88.4 [81.6, 94.1] | 88.9 [84.4, 93.1] | 100.0 [100.0, 100.0] | 67.8 [62.5, 73.5] |
| student-sft hybrid (reconciler v3) | 12 | 31.2 [14.6, 49.3] | 22.2 [5.5, 46.7] | 2,700 [0, 8,100] | 42,077 [17,404, 69,740] | 39,437 [14,518, 68,145] | 88.4 [81.6, 94.1] | 88.9 [84.4, 93.1] | 100.0 [100.0, 100.0] | 67.8 [62.5, 73.5] |
| student-perdoc-sft hybrid | 12 | 76.4 [63.9, 88.9] | 100.0 [100.0, 100.0] | 0 [0, 0] | 3,770 [0, 9,113] | 3,770 [0, 9,113] | 87.0 [81.9, 91.7] | 92.9 [89.5, 96.0] | 100.0 [100.0, 100.0] | 84.4 [78.5, 90.3] |
| student-perdoc-sft hybrid (reconciler v2) | 12 | 81.9 [68.1, 94.4] | 100.0 [100.0, 100.0] | 0 [0, 0] | 504 [0, 1,510] | 504 [0, 1,510] | 93.9 [89.8, 97.4] | 92.9 [89.5, 96.0] | 100.0 [100.0, 100.0] | 88.8 [82.2, 95.1] |
| student-perdoc-sft hybrid (reconciler v3) | 12 | 81.9 [68.1, 94.4] | 100.0 [100.0, 100.0] | 0 [0, 0] | 504 [0, 1,510] | 504 [0, 1,510] | 93.9 [89.8, 97.4] | 93.3 [89.7, 96.5] | 100.0 [100.0, 100.0] | 88.9 [82.3, 95.3] |
| student-perdoc-sft-v2 hybrid | 12 | 73.6 [62.5, 84.7] | 100.0 [100.0, 100.0] | 0 [0, 0] | 6,366 [795, 13,563] | 6,366 [795, 13,563] | 75.5 [67.9, 83.2] | 91.1 [87.2, 94.8] | 100.0 [100.0, 100.0] | 79.3 [73.0, 85.9] |
| student-perdoc-sft-v2 hybrid (reconciler v3) | 12 | 79.2 [69.4, 88.9] | 100.0 [100.0, 100.0] | 0 [0, 0] | 3,100 [128, 8,568] | 3,100 [128, 8,568] | 86.3 [77.4, 93.8] | 91.7 [87.6, 95.7] | 100.0 [100.0, 100.0] | 84.0 [77.1, 90.9] |
| heuristic hybrid (code alone) | 12 | 4.9 [0.0, 11.1] | 55.6 [21.4, 78.3] | 784 [0, 2,288] | 54,093 [32,921, 78,573] | 53,309 [32,040, 78,142] | 19.1 [13.2, 24.7] | 52.5 [49.0, 55.8] | 100.0 [100.0, 100.0] | 40.0 [37.2, 42.9] |
| heuristic hybrid (code alone) (reconciler v3) | 12 | 13.2 [4.9, 22.2] | 55.6 [21.4, 78.3] | 7,189 [192, 16,219] | 43,360 [25,658, 66,762] | 38,923 [21,410, 63,630] | 29.5 [21.9, 36.5] | 53.1 [49.5, 56.6] | 100.0 [100.0, 100.0] | 44.4 [40.4, 48.1] |
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
| student-base hybrid (reconciler v2) | <=16k | 63 | 57.9 | 71.3 | 74,738 | 103,120 | 156,398 | 75.4 | 89.5 | 100.0 | 72.1 |
| student-base hybrid (reconciler v2) | 16-32k | 44 | 49.3 | 68.1 | 109,736 | 622,879 | 672,792 | 70.6 | 86.6 | 100.0 | 67.8 |
| student-base hybrid (reconciler v2) | >32k | 13 | 44.4 | 63.2 | 46,020 | 1,061,955 | 1,029,260 | 66.8 | 85.5 | 100.0 | 65.6 |
| student-base hybrid (reconciler v3) | <=16k | 63 | 60.1 | 71.3 | 74,976 | 80,612 | 140,135 | 80.1 | 90.0 | 100.0 | 73.6 |
| student-base hybrid (reconciler v3) | 16-32k | 44 | 50.9 | 68.1 | 111,335 | 583,369 | 630,253 | 74.9 | 87.3 | 100.0 | 69.3 |
| student-base hybrid (reconciler v3) | >32k | 13 | 46.4 | 63.2 | 45,881 | 933,076 | 913,656 | 72.0 | 86.3 | 100.0 | 67.3 |
| student-sft hybrid | <=16k | 63 | 40.1 | 64.3 | 14,198 | 278,779 | 281,355 | 64.3 | 88.8 | 100.0 | 64.9 |
| student-sft hybrid | 16-32k | 44 | 37.1 | 56.4 | 24,264 | 1,045,275 | 1,050,420 | 59.4 | 84.0 | 100.0 | 62.1 |
| student-sft hybrid | >32k | 13 | 32.6 | 51.1 | 28,369 | 1,448,378 | 1,438,832 | 54.3 | 81.5 | 100.0 | 59.2 |
| student-sft hybrid (reconciler v2) | <=16k | 63 | 47.6 | 64.3 | 14,597 | 227,459 | 230,501 | 73.9 | 89.8 | 100.0 | 69.1 |
| student-sft hybrid (reconciler v2) | 16-32k | 44 | 41.9 | 56.4 | 25,141 | 939,578 | 943,987 | 67.6 | 84.7 | 100.0 | 65.1 |
| student-sft hybrid (reconciler v2) | >32k | 13 | 37.9 | 51.1 | 73,930 | 1,280,827 | 1,260,718 | 62.4 | 82.2 | 100.0 | 62.4 |
| student-sft hybrid (reconciler v3) | <=16k | 63 | 50.8 | 64.3 | 14,670 | 219,497 | 222,515 | 81.4 | 90.6 | 100.0 | 71.6 |
| student-sft hybrid (reconciler v3) | 16-32k | 44 | 43.4 | 56.4 | 31,046 | 890,637 | 889,141 | 71.5 | 85.2 | 100.0 | 66.4 |
| student-sft hybrid (reconciler v3) | >32k | 13 | 38.4 | 51.1 | 73,930 | 1,274,548 | 1,259,583 | 66.1 | 82.8 | 100.0 | 63.4 |
| student-perdoc-sft hybrid | <=16k | 63 | 65.2 | 88.7 | 18,151 | 145,241 | 159,199 | 74.7 | 93.9 | 100.0 | 74.9 |
| student-perdoc-sft hybrid | 16-32k | 44 | 61.6 | 82.1 | 12,494 | 655,548 | 651,799 | 70.4 | 90.2 | 100.0 | 72.0 |
| student-perdoc-sft hybrid | >32k | 13 | 55.4 | 76.4 | 45,622 | 1,102,203 | 1,091,888 | 65.9 | 89.1 | 100.0 | 69.1 |
| student-perdoc-sft hybrid (reconciler v2) | <=16k | 63 | 77.1 | 88.7 | 18,199 | 68,361 | 82,950 | 84.3 | 94.1 | 100.0 | 80.2 |
| student-perdoc-sft hybrid (reconciler v2) | 16-32k | 44 | 70.0 | 82.1 | 22,614 | 478,802 | 478,980 | 77.7 | 90.5 | 100.0 | 75.9 |
| student-perdoc-sft hybrid (reconciler v2) | >32k | 13 | 64.3 | 76.4 | 54,563 | 795,789 | 793,090 | 73.8 | 89.5 | 100.0 | 73.1 |
| student-perdoc-sft hybrid (reconciler v3) | <=16k | 63 | 86.3 | 88.7 | 18,199 | 25,599 | 41,066 | 93.7 | 95.8 | 100.0 | 86.8 |
| student-perdoc-sft hybrid (reconciler v3) | 16-32k | 44 | 74.4 | 82.1 | 30,660 | 338,820 | 347,506 | 84.0 | 91.8 | 100.0 | 78.8 |
| student-perdoc-sft hybrid (reconciler v3) | >32k | 13 | 67.9 | 76.4 | 58,952 | 604,184 | 613,591 | 80.8 | 90.9 | 100.0 | 75.8 |
| student-perdoc-sft-v2 hybrid | <=16k | 63 | 65.6 | 89.1 | 22,323 | 178,038 | 198,135 | 69.7 | 93.2 | 100.0 | 73.7 |
| student-perdoc-sft-v2 hybrid | 16-32k | 44 | 62.0 | 83.4 | 14,176 | 652,325 | 646,179 | 67.5 | 90.5 | 100.0 | 71.5 |
| student-perdoc-sft-v2 hybrid | >32k | 13 | 56.5 | 76.4 | 82,810 | 1,070,710 | 1,010,621 | 62.5 | 89.2 | 100.0 | 68.7 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | <=16k | 63 | 87.5 | 89.1 | 23,097 | 27,610 | 49,442 | 91.1 | 95.3 | 100.0 | 86.5 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | 16-32k | 44 | 76.5 | 83.4 | 30,023 | 277,387 | 284,181 | 82.2 | 92.1 | 100.0 | 78.5 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | >32k | 13 | 72.2 | 76.4 | 104,076 | 446,993 | 447,600 | 79.8 | 91.2 | 100.0 | 76.7 |
| heuristic hybrid (code alone) | <=16k | 63 | 12.0 | 41.7 | 12,616 | 314,325 | 310,491 | 38.8 | 59.8 | 100.0 | 48.7 |
| heuristic hybrid (code alone) | 16-32k | 44 | 9.4 | 41.0 | 52,868 | 1,128,930 | 1,099,501 | 32.6 | 57.2 | 100.0 | 45.7 |
| heuristic hybrid (code alone) | >32k | 13 | 6.6 | 39.7 | 34,338 | 1,515,636 | 1,482,645 | 26.6 | 55.5 | 100.0 | 43.2 |
| heuristic hybrid (code alone) (reconciler v3) | <=16k | 63 | 12.8 | 41.7 | 12,616 | 302,020 | 298,187 | 40.0 | 60.0 | 100.0 | 49.2 |
| heuristic hybrid (code alone) (reconciler v3) | 16-32k | 44 | 9.8 | 41.0 | 53,813 | 1,126,611 | 1,096,238 | 33.7 | 57.4 | 100.0 | 46.1 |
| heuristic hybrid (code alone) (reconciler v3) | >32k | 13 | 6.8 | 39.7 | 34,338 | 1,515,588 | 1,482,693 | 27.2 | 55.6 | 100.0 | 43.4 |

Each model call sees one document (about 1.5-3k tokens), so no hybrid case overflows the 16k context; accuracy still falls with case length because long cases carry more documents and more matching.

### Cases with a document reply cut at the 4,096-token cap

| run | length bucket | cases | context overflow | cut at the token cap |
|---|---|---|---|---|
| student-sft hybrid | <=16k | 63 | 0 | 6 |
| student-sft hybrid | 16-32k | 44 | 0 | 9 |
| student-sft hybrid | >32k | 13 | 0 | 2 |
| student-sft hybrid (reconciler v2) | <=16k | 63 | 0 | 6 |
| student-sft hybrid (reconciler v2) | 16-32k | 44 | 0 | 9 |
| student-sft hybrid (reconciler v2) | >32k | 13 | 0 | 2 |
| student-sft hybrid (reconciler v3) | <=16k | 63 | 0 | 6 |
| student-sft hybrid (reconciler v3) | 16-32k | 44 | 0 | 9 |
| student-sft hybrid (reconciler v3) | >32k | 13 | 0 | 2 |
| student-perdoc-sft-v2 hybrid | <=16k | 63 | 0 | 1 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | <=16k | 63 | 0 | 1 |

The column counts cases with at least one cut document reply (student-sft hybrid: 17 cases, one cut document each); a cut reply is unparseable and that document is reconciled as missing, while the other documents of the case still count.

### Link audit against target.json (all 132 test cases; dev in brackets)

| run | GSTR-2B links missed | GSTR-2B false links | register missed | register false | payment missed | payment false |
|---|---|---|---|---|---|---|
| student-base hybrid | 931 [177] | 3 [0] | 700 [124] | 0 [0] | 362 [64] | 36 [2] |
| student-base hybrid (reconciler v2) | 623 [114] | 3 [0] | 700 [124] | 0 [0] | 361 [64] | 36 [2] |
| student-sft hybrid | 970 | 2 | 774 | 0 | 344 | 58 |
| student-sft hybrid (reconciler v2) | 679 | 2 | 773 | 0 | 344 | 58 |
| student-perdoc-sft hybrid | 822 [120] | 2 [0] | 573 [80] | 1 [0] | 156 [16] | 22 [1] |
| student-perdoc-sft hybrid (reconciler v2) | 501 [75] | 1 [0] | 573 [80] | 1 [0] | 156 [16] | 22 [1] |
| student-base hybrid (reconciler v3) | 486 [79] | 3 [0] | 541 [86] | 0 [0] | 342 [60] | 35 [2] |
| student-sft hybrid (reconciler v3) | 537 | 2 | 604 | 0 | 326 | 54 |
| student-perdoc-sft hybrid (reconciler v3) | 304 [31] | 1 [0] | 329 [30] | 1 [0] | 149 [14] | 19 [2] |
| student-perdoc-sft-v2 hybrid | 979 [108] | 1 [0] | 617 [66] | 1 [0] | 205 [13] | 33 [0] |
| student-perdoc-sft-v2 hybrid (reconciler v3) | 341 [27] | 1 [0] | 367 [24] | 1 [0] | 199 [10] | 31 [0] |
| heuristic hybrid (code alone) | 1,281 | 1 | 1,393 | 0 | 1,532 | 3 |
| heuristic hybrid (code alone) (reconciler v3) | 1,222 | 1 | 1,391 | 0 | 1,522 | 3 |

Test has 2,109 true GSTR-2B links, 2,398 register links and 1,674 payment links (dev: 355, 401, 270); `python scripts/hybrid_link_audit.py RUN_DIR CASE_ROOT...` reproduces the counts.
v2 recovers 291 to 321 GSTR-2B links per model on test without adding a false one (student-perdoc-sft: 2 false links under v1, 1 under v2).
v3 recovers a further 137 to 197 GSTR-2B and 159 to 244 register links per model on test, with no new false register or GSTR-2B link; payment false links fall from 22 to 19 (student-perdoc-sft).

### Paired difference, reconciler v2 vs v1 (same model, same replies)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-base hybrid (reconciler v2) | itc_invoice | 132 | +8.7 [+7.0, +10.4] | 0.0005 |
| student-base hybrid (reconciler v2) | context_acc | 130 | +0.5 [+0.0, +1.3] | 0.1104 |
| student-base hybrid (reconciler v2) | composite | 132 | +4.5 [+3.8, +5.2] | 0.0005 |
| student-sft hybrid (reconciler v2) | itc_invoice | 132 | +5.9 [+4.6, +7.3] | 0.0005 |
| student-sft hybrid (reconciler v2) | composite | 132 | +3.5 [+3.0, +4.0] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v2) | itc_invoice | 132 | +9.8 [+8.2, +11.5] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v2) | composite | 132 | +4.6 [+3.9, +5.4] | 0.0005 |

Context accuracy is identical case by case under v1 and v2 for student-sft and student-perdoc-sft, so the report prints no row for it.

### Paired difference, reconciler v3 vs v2 (same model, same replies)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-base hybrid (reconciler v3) | itc_invoice | 132 | +1.7 [+1.0, +2.5] | 0.0005 |
| student-base hybrid (reconciler v3) | composite | 132 | +1.3 [+0.9, +1.7] | 0.0005 |
| student-sft hybrid (reconciler v3) | itc_invoice | 132 | +2.1 [+1.4, +2.9] | 0.0005 |
| student-sft hybrid (reconciler v3) | composite | 132 | +1.7 [+1.3, +2.2] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | itc_invoice | 132 | +6.2 [+4.8, +7.6] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | composite | 132 | +4.4 [+3.5, +5.5] | 0.0005 |

Context accuracy is identical case by case under v2 and v3, so the report prints no row for it.

### Paired difference vs student-base hybrid (both reconciler v3)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-perdoc-sft hybrid (reconciler v3) | itc_invoice | 132 | +25.9 [+22.5, +29.2] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | context_acc | 130 | +19.1 [+14.5, +24.2] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | composite | 132 | +12.1 [+10.7, +13.5] | 0.0005 |

Same prompts, code and server; the only change is the per-document LoRA adapter.
Under reconciler v1 the same comparison gave ITC invoice exact +20.3 [+16.9, +23.8], context +19.7 [+15.0, +24.7], composite +8.9 [+7.7, +10.2]; under v2, +21.4 [+18.0, +24.8], +19.1 [+14.5, +24.2] and +9.0 [+7.7, +10.3].

### Per-document adapter v2 vs v1 (both reconciler v3)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-perdoc-sft-v2 hybrid (reconciler v3) | itc_invoice | 132 | +1.5 [-0.2, +3.2] | 0.0865 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | context_acc | 130 | +0.8 [-0.8, +2.3] | 0.3233 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | composite | 132 | -0.6 [-1.7, +0.4] | 0.2349 |

Paired by case_id over all 132 cases; with reconciler v1 the same pairing gives ITC invoice exact +0.2 [-1.8, +2.1] and composite -1.2 [-2.0, -0.5] (p = 0.004).
On dev (reconciler v3) v2 was ahead of v1 by ITC +1.1 [-1.1, +3.4] on the 120 small cases and +1.2 [-0.3, +2.7] on the 60 larger cases, composite +0.8 and +0.9, with fewer false payment links (2 to 0 and 9 to 6); on test it gains ITC invoice exact (CI just includes zero) but loses match accuracy (86.6% vs 88.7%), adds false payment links (31 vs 19) and overclaims more (Rs 34,409 vs 27,183 per case), and scores 79.2% vs 81.9% ITC on realworld.
The longer training is therefore not a clear gain: student-perdoc-sft (v1) stays the headline per-document model.

Against teacher-30B constrained end-to-end, student-perdoc-sft-v2 hybrid (reconciler v3) gives:

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-perdoc-sft-v2 hybrid (reconciler v3) | itc_invoice | 120 | +22.1 [+18.3, +26.0] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | context_acc | 119 | +48.0 [+41.7, +54.5] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | composite | 120 | +13.4 [+10.1, +17.2] | 0.0005 |

### Paired difference vs teacher-30B constrained, end-to-end

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-perdoc-sft hybrid (reconciler v3) | itc_invoice | 120 | +20.2 [+16.4, +24.2] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | context_acc | 119 | +47.2 [+41.1, +53.7] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | composite | 120 | +13.6 [+10.3, +17.6] | 0.0005 |

Paired by case_id over the 120 simulator cases (the teacher did not run realworld); the teacher is the end-to-end teacher-30B constrained row above in this report.
With reconciler v1 the per-document 4B hybrid is level with the 30B teacher on ITC invoice exact (+3.1 [-1.6, +7.5], p = 0.18); with v2 it is ahead on all three (ITC +13.4 [+9.3, +17.5], composite +8.8 [+5.5, +12.5]), and with v3 by the margins above.

### Paired difference vs SFT constrained (compact grammar), end-to-end (reconciler v3)

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-base hybrid (reconciler v3) | itc_invoice | 42 | -22.9 [-29.5, -16.6] | 0.0005 |
| student-base hybrid (reconciler v3) | context_acc | 41 | -11.8 [-23.6, -1.1] | 0.0405 |
| student-base hybrid (reconciler v3) | composite | 42 | -10.9 [-13.8, -8.1] | 0.0005 |
| student-sft hybrid (reconciler v3) | itc_invoice | 42 | -32.8 [-41.8, -23.7] | 0.0005 |
| student-sft hybrid (reconciler v3) | context_acc | 41 | -22.8 [-36.1, -9.2] | 0.0030 |
| student-sft hybrid (reconciler v3) | composite | 42 | -13.2 [-16.8, -9.7] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | itc_invoice | 42 | +8.0 [+2.2, +13.8] | 0.0045 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | context_acc | 41 | +23.1 [+13.6, +32.5] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | composite | 42 | +1.5 [-2.0, +4.7] | 0.3718 |
| heuristic hybrid (code alone) (reconciler v3) | itc_invoice | 42 | -60.5 [-67.5, -53.2] | 0.0005 |
| heuristic hybrid (code alone) (reconciler v3) | context_acc | 41 | -39.2 [-50.7, -29.0] | 0.0005 |
| heuristic hybrid (code alone) (reconciler v3) | composite | 42 | -34.8 [-38.0, -31.6] | 0.0005 |

Paired by case_id over the 42 cases the compact-grammar end-to-end run covers (15 test_iid, 15 test_ood, 12 realworld); p-value from a centred paired bootstrap (null: zero mean difference).
student-perdoc-sft hybrid (reconciler v3) against this row, with overclaim and underclaim in rupees, is in "Pipeline comparison: e2e SFT-compact vs per-doc hybrid v3" below: level on ITC invoice exact (+5.9 [-1.8, +13.2]) and ahead on context accuracy (+20.7 [+11.6, +30.5]).
student-sft hybrid, the same SFT adapter fed one document at a time, is far below its own end-to-end run, since that adapter was trained on whole cases.

### Paired difference vs SFT constrained (full grammar), end-to-end

| run | metric | paired n | delta pts [95% CI] | bootstrap p |
|---|---|---|---|---|
| student-base hybrid | itc_invoice | 132 | +31.4 [+26.8, +35.9] | 0.0005 |
| student-base hybrid | context_acc | 130 | +28.6 [+20.9, +35.9] | 0.0005 |
| student-base hybrid | composite | 132 | +6.4 [+4.8, +8.0] | 0.0005 |
| student-base hybrid (reconciler v2) | itc_invoice | 132 | +40.1 [+35.1, +45.0] | 0.0005 |
| student-base hybrid (reconciler v2) | context_acc | 130 | +29.1 [+21.5, +36.5] | 0.0005 |
| student-base hybrid (reconciler v2) | composite | 132 | +10.9 [+9.0, +12.6] | 0.0005 |
| student-base hybrid (reconciler v3) | itc_invoice | 132 | +41.9 [+37.0, +46.8] | 0.0005 |
| student-base hybrid (reconciler v3) | context_acc | 130 | +29.1 [+21.5, +36.5] | 0.0005 |
| student-base hybrid (reconciler v3) | composite | 132 | +12.3 [+10.5, +14.0] | 0.0005 |
| student-sft hybrid | itc_invoice | 132 | +24.9 [+19.8, +29.7] | 0.0005 |
| student-sft hybrid | context_acc | 130 | +18.5 [+10.9, +26.4] | 0.0005 |
| student-sft hybrid | composite | 132 | +4.7 [+2.9, +6.4] | 0.0005 |
| student-sft hybrid (reconciler v2) | itc_invoice | 132 | +30.9 [+25.4, +35.9] | 0.0005 |
| student-sft hybrid (reconciler v2) | context_acc | 130 | +18.5 [+10.9, +26.4] | 0.0005 |
| student-sft hybrid (reconciler v2) | composite | 132 | +8.1 [+6.2, +10.0] | 0.0005 |
| student-sft hybrid (reconciler v3) | itc_invoice | 132 | +33.0 [+27.6, +38.2] | 0.0005 |
| student-sft hybrid (reconciler v3) | context_acc | 130 | +18.5 [+10.9, +26.4] | 0.0005 |
| student-sft hybrid (reconciler v3) | composite | 132 | +9.8 [+7.9, +11.8] | 0.0005 |
| student-perdoc-sft hybrid | itc_invoice | 132 | +51.7 [+47.1, +56.4] | 0.0005 |
| student-perdoc-sft hybrid | context_acc | 130 | +48.2 [+42.2, +54.4] | 0.0005 |
| student-perdoc-sft hybrid | composite | 132 | +15.4 [+13.6, +17.1] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v2) | itc_invoice | 132 | +61.5 [+56.8, +66.2] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v2) | context_acc | 130 | +48.2 [+42.2, +54.4] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v2) | composite | 132 | +19.9 [+18.1, +21.7] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | itc_invoice | 132 | +67.7 [+63.0, +72.3] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | context_acc | 130 | +48.2 [+42.2, +54.4] | 0.0005 |
| student-perdoc-sft hybrid (reconciler v3) | composite | 132 | +24.4 [+22.4, +26.4] | 0.0005 |
| student-perdoc-sft-v2 hybrid | itc_invoice | 132 | +51.9 [+47.2, +56.6] | 0.0005 |
| student-perdoc-sft-v2 hybrid | context_acc | 130 | +49.0 [+43.0, +54.9] | 0.0005 |
| student-perdoc-sft-v2 hybrid | composite | 132 | +14.1 [+12.4, +15.9] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | itc_invoice | 132 | +69.2 [+64.6, +73.7] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | context_acc | 130 | +49.0 [+43.0, +54.9] | 0.0005 |
| student-perdoc-sft-v2 hybrid (reconciler v3) | composite | 132 | +23.7 [+21.8, +25.7] | 0.0005 |
| heuristic hybrid (code alone) | itc_invoice | 132 | -2.4 [-6.8, +1.4] | 0.2499 |
| heuristic hybrid (code alone) | context_acc | 130 | -2.8 [-11.9, +6.0] | 0.5217 |
| heuristic hybrid (code alone) | composite | 132 | -12.5 [-14.3, -10.8] | 0.0005 |
| heuristic hybrid (code alone) (reconciler v3) | itc_invoice | 132 | -1.1 [-5.4, +2.7] | 0.6052 |
| heuristic hybrid (code alone) (reconciler v3) | context_acc | 130 | -2.8 [-11.9, +6.0] | 0.5217 |
| heuristic hybrid (code alone) (reconciler v3) | composite | 132 | -11.8 [-13.4, -10.1] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) hybrid | itc_invoice | 12 | +70.1 [+52.8, +84.7] | 0.0005 |
| Claude Sonnet (via Claude Code CLI) hybrid | context_acc | 11 | +36.4 [+13.6, +63.6] | 0.0035 |
| Claude Sonnet (via Claude Code CLI) hybrid | composite | 12 | +31.5 [+24.6, +36.7] | 0.0005 |

Paired by case_id over all 132 cases (realworld included).
Caveat: that end-to-end SFT run used the full constrained grammar, which does not match the compact-form SFT targets (blocked and deferred fill with junk; see Notes above), so it understates the SFT model; it is kept as evidence of that grammar mismatch, and the compact-grammar pairing above replaces it for comparisons.

### Throughput

| run | req/s | out tok/s | p50 latency (s) | GPU $/1k cases | API list $/1k cases |
|---|---|---|---|---|---|
| student-base hybrid | 0.09 | 473 | 82.0 | - | - |
| student-base hybrid (reconciler v2) | - | - | - | - | - |
| student-base hybrid (reconciler v3) | - | - | - | - | - |
| student-sft hybrid | - | - | - | - | - |
| student-sft hybrid (reconciler v2) | - | - | - | - | - |
| student-sft hybrid (reconciler v3) | - | - | - | - | - |
| student-perdoc-sft hybrid | 0.10 | 441 | 61.2 | - | - |
| student-perdoc-sft hybrid (reconciler v2) | - | - | - | - | - |
| student-perdoc-sft hybrid (reconciler v3) | - | - | - | - | - |
| student-perdoc-sft-v2 hybrid | 0.11 | 488 | 62.7 | - | - |
| student-perdoc-sft-v2 hybrid (reconciler v3) | - | - | - | - | - |
| heuristic hybrid (code alone) | 15.55 | 0 | 1.0 | - | - |
| heuristic hybrid (code alone) (reconciler v3) | - | - | - | - | - |
| Claude Sonnet (via Claude Code CLI) hybrid | 0.11 | 185 | 16.9 | - | - |

Throughput is from each run's first pass: student-base made 2,288 document calls in 1,553 s wall (2.79M prompt and 0.73M completion tokens), and Sonnet made 36 document calls through `claude -p` at concurrency 2 on the Mac.
student-perdoc-sft hybrid throughput is its first pass; a demo recording shared the server for its first 4 minutes (16:47:30 to 16:51:43 IST, one request at a time against this run's 8), so it is slightly understated.
student-perdoc-sft-v2 hybrid throughput is its first pass with the server otherwise idle.
student-sft hybrid throughput is not reported: demo recordings shared the server during the run and the run was restarted midway (concurrency 8 to 14), so its timings are contaminated; its accuracy is unaffected.
Reconciler v2 and v3 rows reuse the v1 model replies, so their throughput is the v1 row's (the reconciler itself takes well under a second per case).

## Pipeline comparison: e2e SFT-compact vs per-doc hybrid v3

Which pipeline is better: the end-to-end SFT model with the compact grammar (`student-sft-compact`), or the per-document hybrid (`hybrid-perdoc-v3`, the per-document SFT adapter plus the deterministic reconciler, commit 8286f1f)?
Both are scored on the same 42 cases: the 30 simulator cases of the stratified sample (15 test_iid, 15 test_ood) and the 12 realworld cases.
The delta is hybrid minus e2e, with a paired bootstrap 95% CI and a centred paired-bootstrap p-value over shared case ids.
Ratio metrics show pooled values in points; the two rupee metrics are per-case means.
Context accuracy has one case fewer because that case has no context documents.
Regenerate with `python scripts/eval_pair.py runs/eval/student-sft-compact runs/eval/hybrid-perdoc-v3`.

| set | metric | n | student-sft-compact | hybrid-perdoc-v3 | delta (other minus ref) [95% CI] | bootstrap p |
|---|---|---|---|---|---|---|
| all shared | itc_invoice | 42 | 73.7 | 79.7 | +5.9 [-1.8, +13.2] pts | 0.1144 |
| all shared | context_acc | 41 | 65.3 | 84.1 | +20.7 [+11.6, +30.5] pts | 0.0005 |
| all shared | composite | 42 | 81.6 | 84.1 | +2.5 [-1.1, +6.2] pts | 0.1639 |
| all shared | itc_overclaim_rs (Rs per case) | 42 | 317,078 | 33,706 | -283,373 [-472,384, -133,013] | 0.0022 |
| all shared | itc_underclaim_rs (Rs per case) | 42 | 13,922 | 102,274 | +88,352 [+30,437, +164,947] | 0.0138 |
| simulator | itc_invoice | 30 | 75.7 | 78.7 | +3.0 [-3.6, +8.8] pts | 0.3393 |
| simulator | context_acc | 30 | 63.9 | 82.8 | +18.3 [+10.2, +26.9] pts | 0.0005 |
| simulator | composite | 30 | 80.5 | 82.2 | +1.7 [-1.9, +4.6] pts | 0.3148 |
| simulator | itc_overclaim_rs (Rs per case) | 30 | 435,416 | 47,188 | -388,228 [-633,839, -186,378] | 0.0026 |
| simulator | itc_underclaim_rs (Rs per case) | 30 | 19,491 | 142,982 | +123,491 [+42,579, +222,106] | 0.0109 |
| realworld | itc_invoice | 12 | 68.8 | 81.9 | +13.2 [-8.3, +32.6] pts | 0.2274 |
| realworld | context_acc | 11 | 83.3 | 100.0 | +27.3 [+0.0, +54.5] pts | 0.0400 |
| realworld | composite | 12 | 84.2 | 88.9 | +4.7 [-5.1, +13.6] pts | 0.3448 |
| realworld | itc_overclaim_rs (Rs per case) | 12 | 21,235 | 0 | -21,235 [-49,387, -611] | 0.0443 |
| realworld | itc_underclaim_rs (Rs per case) | 12 | 0 | 504 | +504 [+0, +1,510] | 0.2573 |

Reading:

- The hybrid is clearly better on context accuracy, by 18 to 28 points on every set (p = 0.0005 on all 42 cases).
- The hybrid overclaims far less ITC: Rs 33,706 per case against Rs 317,078 (p = 0.002), which is the side that creates tax risk.
- The hybrid underclaims more: Rs 102,274 per case against Rs 13,922 (p = 0.014), so it is more conservative and leaves eligible ITC unclaimed.
- ITC invoice exact and composite are statistically tied (+5.9 and +2.5 points, p = 0.11 and 0.16).
- With n = 42 the intervals are wide, so read this as hybrid being the safer and more auditable pipeline, with e2e SFT recovering more of the eligible ITC.
- For scale, both are well below Sonnet on the same cases (e2e SFT-compact is 24.7 points below Sonnet on ITC invoice exact, p = 0.0005).
