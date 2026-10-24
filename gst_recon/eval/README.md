# gst_recon.eval

Evaluation harness for gst-recon: run a model on rendered cases, score with the shared reward functions, report component metrics with bootstrap CIs, throughput and cost.
Everything here is a client; the model is served elsewhere (SGLang).
Outputs live under `runs/eval/` and are never training data (see Guard).

Where to run: runs and reports are light (HTTP client plus scoring), but bulk scoring and AuditKIT sweeps belong on kratos or rs-epyc, not the Mac.
The frontier baseline is the one thing that runs on the Mac (it needs the local `claude` login).

## Install

    uv sync --extra eval          # numpy + matplotlib; the run command needs only numpy

## Task prompt

`prompt.txt` holds only the case data.
`gst_recon/eval/prompts.py` holds `SYSTEM_PROMPT`, the task instruction every model gets (output keys, flag and reason-code semantics, ITC rules in order).
Unconstrained runs also get the JSON Schema appended to the system prompt (`--no-schema-in-prompt` to drop it); constrained runs pass it as `response_format` instead.
Training data builders must wrap `prompt.txt` with the same `SYSTEM_PROMPT`, otherwise a fine-tuned model is scored on a format it never saw.

## run

    python -m gst_recon.eval run \
      --endpoint http://localhost:30000/v1 --model teacher \
      --cases data/rendered/test_iid data/rendered/test_ood \
      --out runs/eval/base-constrained --label "base constrained" \
      --constrained --concurrency 32 \
      --gpu-hour-usd 2.5 --api-in-per-mtok 3 --api-out-per-mtok 15

- `--constrained` sends `response_format={"type":"json_schema","json_schema":{"name":"recon","schema":<schemas/output.schema.json>}}`; `--unconstrained` (default) sends none.
- `--cases` takes one or more directories whose children are `<case_id>/{prompt.txt,target.json,meta.json}`; split, difficulty and `ocr_recall` come from `meta.json`.
  `--n-per-dir N` takes a seeded random sample per directory.
- `--truth-dir data/truth` (default, if present) loads the truth `Case` JSON to find context-dependent documents; without it a proxy (documents with BLOCKED_* reasons) is used and the report says so.
- `--max-tokens` (default 32768) is clipped automatically to what the server allows (context and completion caps); the harness never fails a case for asking too much.
- `--no-thinking` sends `chat_template_kwargs {"enable_thinking": false}` for Qwen3 thinking models; `--extra-body '{...}'` merges arbitrary JSON into the request.
- Prices are inputs and nothing is built in: GPU cost per 1,000 cases = measured wall time x `--gpu-hour-usd`; API cost per 1,000 cases = this run's mean token counts x the closed API list price.
- Resumable: cases already under `--out/cases/` without a transport error are skipped; `--no-resume` regenerates.

Per run directory:

| file | content |
|---|---|
| `cases/<case_id>.json` | raw output, parsed JSON, latency, prompt and completion tokens, finish reason, error |
| `scores.jsonl` | per-case metrics (rescored from the stored raw output at every run) |
| `aggregate.json` | overall, per split, per difficulty, per OCR bucket, throughput, cost |
| `table.md`, `config.json`, `run_stats.json`, `DO_NOT_TRAIN` | markdown table, settings and prompt fingerprints, fresh-request wall time and tokens, guard marker |

### Metrics

Headline: `itc_invoice` (all 12 ITC amounts within Rs 1) and `context_acc`; the composite has a high floor (trivial baselines score about 80), so it is secondary.
Primary (components, in table order): `itc_invoice`, `context_acc`, `itc_overclaim_rs`, `itc_underclaim_rs`, `itc_abs_err_rs`, `match_accuracy`, `extraction_f1`, `schema_valid` (pydantic `ReconOutput`).
Secondary: `composite` (the weighted reward), `grpo`, `parse_ok`, `arithmetic`, `itc_reasons`, `itc_total_exact`, `itc_all_abs_err_rs`.

- `context_acc`: accuracy on invoices with a line whose s.17(5) outcome depends on the buyer profile or remarks (truth category not normal, or purpose not business). Correct when the 4 blocked amounts are within Rs 1 and the BLOCKED_* reasons match. Pooled over documents.
- `itc_abs_err_rs`: absolute error in rupees of the eligible ITC the model claims, summed over IGST, CGST, SGST and cess, using its `itc_totals` (or the sum of its per-document rows if `itc_totals` is missing). Unparseable output claims zero.
- `itc_overclaim_rs`: the rupees of credit the model would have wrongly claimed, summed over invoices of max(0, predicted eligible ITC - true eligible ITC), eligible ITC summed over the four heads per invoice. An invoice the model invented counts fully. `itc_underclaim_rs` is the mirror, max(0, true - predicted). Unlike `itc_abs_err_rs` they are per invoice, so errors on different invoices never cancel. Unparseable output claims nothing, so it is all underclaim.
- A transport error or unparseable output scores 0 on everything and is counted (`n_errors`, `n_context_overflow`, `n_truncated`).
- CIs: 2,000-resample bootstrap over cases (percentile). Breakdown tables show means only.
- OCR buckets: `full` means `meta.ocr_recall >= 0.9999` (every field is present in the prompt), `partial` otherwise.

## report

    python -m gst_recon.eval report --runs runs/eval/* --out reports/results.md \
      --baselines runs/audit.json --ref base-unconstrained \
      --order base-unconstrained base-constrained sft sft-grpo frontier \
      --append runs/eval/auditkit-compare/auditkit_compare.md

- Writes `reports/results.md` and `reports/results.png` (grouped bars of composite, ITC invoice exact, match accuracy and field F1 per split).
- `--runs` takes run directories or parents of them.
- `--baselines` is the JSON from `python -m gst_recon.sim.audit --json FILE`: trivial baselines (majority, no_anomaly, keyword, context_blind), which are handed the true extraction and links, so only their decision metrics are comparable.
- `--ref` adds paired differences (mean per-case difference, bootstrap 95% CI, centred bootstrap p) of every run against one run.
- `--append` adds markdown files verbatim (the AuditKIT section).

## Frontier baseline: Claude Sonnet (via Claude Code CLI)

    python scripts/eval_frontier.py --cases data/rendered/test_iid data/rendered/test_ood --n-per-dir 50 --concurrency 2

There is no API key; each case is one non-interactive CLI call:

    claude -p --model sonnet --output-format json \
      --system-prompt "<SYSTEM_PROMPT + JSON Schema>" --tools "" \
      --no-session-persistence --setting-sources "" --disable-slash-commands --strict-mcp-config
    # prompt.txt on stdin; reply in the "result" field, usage and total_cost_usd alongside

Prompt-only (the schema is in the system prompt, no constrained decoding), same scorer as every other run.
Run from a neutral working directory (`runs/eval/frontier/cwd`) so no project files or CLAUDE.md are picked up.
Output goes only to `runs/eval/frontier/` (resumable per case; errored cases are retried on the next call); the script refuses any other `--out`.
Concurrency is capped at 2.
Cost per 1,000 cases for this row is the CLI's own `total_cost_usd` (list basis); wall time and tokens are CLI-bound, not comparable to the SGLang rows.

## AuditKIT (1.1.3)

Separate venv, handoff by files.
Python 3.11 or 3.12; `requests` is needed for the `api:` backend; pydantic and numpy because the script reuses the gst-recon scorer.

    uv venv --python 3.11 .venv-auditkit
    uv pip install --python .venv-auditkit/bin/python "auditkit[requests]==1.1.3" pydantic numpy

    PYTHONPATH=. .venv-auditkit/bin/python scripts/eval_auditkit.py \
      --cases data/rendered/test_iid data/rendered/test_ood --n-per-dir 100 \
      --run base=runs/eval/base-unconstrained \
      --run sft=runs/eval/sft \
      --api live-sft=sft-model@http://127.0.0.1:30000/v1 --constrained \
      --out runs/eval/auditkit-compare

- `--run NAME=RUN_DIR` scores the predictions already stored in a `gst_recon.eval run` directory (`model="precomputed"`, so the same predictions as the main table).
- `--api NAME=MODEL@ENDPOINT` has AuditKIT query the SGLang endpoint itself through `ak.evaluate(..., model="api:MODEL", api_base=ENDPOINT, api_key="EMPTY", server="sglang", adapter=ChatAdapter(system_prompt=SYSTEM_PROMPT))` with temperature 0; `--constrained` adds the `json_schema` response_format.
- The first source is the baseline; each other source is compared to it with `ak.compare()` and `.significance(metric)`.
- Output: `auditkit_compare.json` and `auditkit_compare.md` (run fingerprints, per-metric deltas, AuditKIT p-values, corrected p-values, failed-sample counts).
- Scorers are the gst-recon components wrapped with `ak.scorer`. If the installed AuditKIT has the contributed metrics (branch below), `json_schema_valid` and `field_f1` are added automatically.

Two things to know about AuditKIT 1.1.3:

1. `compare().significance()` p-values are not usable: `_bootstrap.paired_bootstrap` resamples the raw paired differences without centring them on the null, so `p_value` is about 0.5 for any effect and `significant` is never true (50 pairs with means 0.11 vs 0.80 give p=0.52).
   The script therefore prints a corrected column (differences centred before resampling) next to AuditKIT's, and the fix is on the fork as `fix/paired-bootstrap-null`.
2. AuditKIT excludes failed samples (HTTP errors, context overflow) from its means instead of counting them as wrong, unlike the main table. Compare only runs with zero failed samples.

The contributed metrics (`JsonSchemaValid`, `FieldF1`) live on `https://github.com/chayan-bit/AuditKIT/tree/feat/structured-extraction-metrics`; to use them in the AuditKIT venv:

    uv pip install --python .venv-auditkit/bin/python "auditkit[requests,jsonschema] @ git+https://github.com/chayan-bit/AuditKIT@feat/structured-extraction-metrics"

## Eval sets (frozen)

Two splits of 60 cases each, 20 easy, 20 medium and 20 hard, at full size (no truncation).
The data lives outside git under `data/eval/` and is pinned by `gst_recon/eval/eval_sets_manifest.json`.

| split | seed | truth | rendered |
|-------|------|-------|----------|
| test_iid | 9001 | `data/eval/truth/test_iid` | `data/eval/rendered/test_iid` |
| test_ood | 9002 | `data/eval/truth/test_ood` | `data/eval/rendered/test_ood` |

Seeds 9001 and 9002 are disjoint from every training seed.
Both splits were rendered once, on kratos, with one OCR engine: Tesseract 5.5.0 (`GST_TESSERACT=$HOME/gst-tess/tesseract`).
Both sets predate commit 73cd471, which disables OpenCV CPU dispatch (`cv2.setUseOptimized(False)`) so degraded pixels are identical across hosts; they are not re-rendered and stay kratos-only.
Training corpora may also be rendered on rs-lab (conda win-64 Tesseract 5.5.0, leptonica 1.83.1), whose OCR text differs slightly from kratos for the same input; `meta.json` `ocr_build` records engine, leptonica, SIMD flags, dotproduct and platform.
The manifest records the engine, the render version, per-case hashes and the per-split difficulty and length-bucket counts.

Command per split (kratos, `~/gst-recon-eval/render_split.sh <split> <seed>`, run under tmux, one worker per split):

```
python -m gst_recon.sim generate --n-cases 20 --seed <seed> --difficulty {easy,medium,hard} --split <split> --out data/eval/truth/<split>
python -m gst_recon.render --truth data/eval/truth/<split> --out data/eval/rendered/<split> --workers 1 --max-mem-gb 3
```

The kratos user cgroup is capped at 2 CPUs, so the two splits render in parallel with one worker each.
More workers only add contention.

Check a copy of the data against the manifest (exit 1 on missing, extra or changed content):

```
python -m gst_recon.eval.manifest verify --rendered data/eval/rendered --manifest gst_recon/eval/eval_sets_manifest.json
```

Regenerate the manifest with `python -m gst_recon.eval.manifest write --rendered data/eval/rendered --out gst_recon/eval/eval_sets_manifest.json --seed test_iid=9001 --seed test_ood=9002 --command "<render command>"`.

### How the baselines were run

- Keyword and context-blind baselines: `python scripts/eval_baselines.py --cases data/eval/rendered/test_iid data/eval/rendered/test_ood --truth-dir data/eval/truth --out-root runs/eval`, on kratos.
  They are handed the true extraction, so only the decision components are comparable.
- Teacher (Qwen3-30B-A3B, SGLang at rs-epyc:30000, served as `teacher`): `python -m gst_recon.eval run --endpoint http://127.0.0.1:30000/v1 --model teacher --cases <both splits> --truth-dir data/eval/truth --out runs/eval/teacher-constrained --constrained --concurrency 4-6 --max-tokens 24000`.
  The runs are resumable and were done in passes as cases finished rendering.
  The first passes used a 24000-token cap, later passes added `--max-tokens-factor 2` (cap = 2 x reference length + 1000, never above 24000) because unconstrained and some constrained generations degenerate into repetition.
  A reply that hits the cap is scored as it stands, so a capped runaway counts as a failure; `n_truncated` is in each `aggregate.json`.
- The teacher passes used the task prompt from before the compact-form sentence was added (`Fields that are 0, empty or false may be omitted.`).
  The prompt hash of each run is in its `config.json`.
- Teacher unconstrained was stopped early at the coordinator's request (the teacher GPU was needed for training), so it is reported as a subset with `n` stated, next to the same subset of the constrained run.
- Sonnet: `scripts/eval_frontier.py` over both splits, concurrency 2 on the Mac, output only under `runs/eval/frontier`.
  The first 62 completed cases ran under the earlier task prompt and the last 58 under the current one (the process was relaunched after the prompt commit); the run is resumable and `config.json` holds only the last launch's prompt hash.
- Stopped or partial runs are rescored on the cases they finished with `scripts/eval_rescore_subset.py RUN_DIR --cases ... --truth-dir ...`, which keeps the recorded config; the same script rescored all runs when the ITC overclaim and underclaim metrics were added.
- The `--gpu-hour-usd` and `--api-*-per-mtok` flags are illustrative inputs for the cost column, not measured prices.
  The Sonnet cost is the `total_cost_usd` reported by the CLI.

## SGLang tunnel

See `infra/launch_teacher.sh`: `ssh -N -L 30000:127.0.0.1:30000 rs-epyc`, then `--endpoint http://localhost:30000/v1`.
The teacher is served with `--context-length 16384`, which is too small for most medium and hard cases (prompts of 5k to 36k tokens plus 2.5k to 18k tokens of output); the harness reports such cases as `context overflow` errors.

## Guard

`gst_recon.eval.guard.refuse_eval_path(path)` raises `EvalDataError` for anything under `runs/eval/` or under a directory holding a `DO_NOT_TRAIN` marker (every run directory has one).
Training-data builders must call it on every input path.

## Tests

    uv run pytest tests/eval -q        # stub OpenAI-compatible server, no GPU, about 10 s
    PYTHONPATH=. .venv-auditkit/bin/python -m pytest tests/eval/test_auditkit_script.py   # needs the AuditKIT venv

## Sample report

`reports/smoke/results.md` and `.png` come from a 6-case smoke (the only rendered cases available at the time): the teacher on SGLang, unconstrained and constrained, with the teacher's 16k context overflowing on half the cases, plus the Claude CLI row, the sim audit baselines and the AuditKIT section.
Treat the numbers as a harness check, not results.
