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

Primary (components): `schema_valid` (pydantic `ReconOutput`), `extraction_f1`, `match_accuracy`, `itc_invoice` (all 12 ITC amounts within Rs 1), `context_acc`, `itc_abs_err_rs`, and `composite` (the weighted reward).
Secondary: `grpo`, `parse_ok`, `arithmetic`, `itc_reasons`, `itc_total_exact`, `itc_all_abs_err_rs`.

- `context_acc`: accuracy on invoices with a line whose s.17(5) outcome depends on the buyer profile or remarks (truth category not normal, or purpose not business). Correct when the 4 blocked amounts are within Rs 1 and the BLOCKED_* reasons match. Pooled over documents.
- `itc_abs_err_rs`: absolute error in rupees of the eligible ITC the model claims, summed over IGST, CGST, SGST and cess, using its `itc_totals` (or the sum of its per-document rows if `itc_totals` is missing). Unparseable output claims zero.
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
