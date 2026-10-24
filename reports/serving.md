# Serving measurements for the teacher

Hand-written; the figures were measured on 2026-10-24 on one shared NVIDIA H100 serving Qwen3-30B-A3B-Instruct-2507-FP8 (the teacher) with SGLang.
No hostnames, accounts or network paths are published here.

## Launch settings

| setting | value |
|---|---|
| context length per request | 65,536 tokens (the model's native maximum is 262,144; `rope_scaling` is null, so no YaRN) |
| `--mem-fraction-static` | 0.62 |
| `--max-running-requests` | 128 |
| grammar backend | xgrammar |
| chunked prefill size | 8,192 |
| KV cache pool | 301,744 tokens (K 13.81 GB plus V 13.81 GB) |

One 64k request fits in the pool; about 4 concurrent 64k requests, or many shorter ones, share the 301,744 tokens.

## Throughput

At most 256 new tokens per request, prompts of about 200 words, temperature 0.8, other tenants' processes present on the host.

| concurrency | completion tokens | wall | throughput |
|---|---|---|---|
| 64 | 16,384 | 2.8 s | 5.8k tok/s |
| 128 | 32,768 | 3.4 s | 9.7k tok/s |

After the relaunch with the 65,536 context, 64 concurrent short requests were re-measured at 5.7k tok/s (unchanged).

## Long context

A needle test places a passphrase in the middle of a long prompt and asks for it back.
A 39,153-token prompt returned the right passphrase in 2.3 s, and a 58,751-token prompt in 3.8 s.
The host was shared with other tenants' processes at the time, so treat the times as indicative.
