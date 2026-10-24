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
