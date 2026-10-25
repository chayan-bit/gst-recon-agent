# gst-recon live demo

A single-page web app for trying the reconciler without reading JSON.
Pick a case, press Run, and it streams the case through the SGLang-served model and shows the reconciliation table next to the model output.
It is a small FastAPI backend with a static front end.
If you have no GPU, "Replay" re-plays runs that were recorded earlier.

Panels, left to right:

1. The degraded invoice scans and the OCR text, plus the purchase register, GSTR-2B and bank statement of the case.
2. The model output streaming token by token, constrained (`json_schema`) or unconstrained, with time to first token, tokens per second and total latency.
3. The reconciliation table: one row per invoice, match chips, ITC eligible, blocked and deferred with the legal reason in plain words, a headline total, and a "compare with ground truth" diff.

Pipelines:

- **End-to-end**: one call returns the whole reconciliation JSON (`gst_recon.eval.prompts.SYSTEM_PROMPT`, `gst_recon.output_json_schema`).
- **Hybrid**: one call per document (`build_doc_messages`, `doc_json_schema`), then the real code reconciler (`gst_recon.hybrid.reconcile.reconcile_prompt`) runs.
  Click an invoice row to open its decision trace ("why this was blocked or deferred").

Source: **Live** calls SGLang. **Replay** re-streams a saved real run at its recorded pacing (1x to 8x), labelled "REPLAY".
Every live run is saved to `recordings/` (set `DEMO_RECORD=0` to stop), so anything you ran once can be replayed with the GPU off.

## Run

```bash
cd demo                       # this directory, inside the gst-recon repo
uv sync                       # project-local venv (.venv)
uv run uvicorn gst_demo.app:app --port 8765
# open http://localhost:8765/
```

For live mode, serve the model with SGLang first (see "Quick start" in the top-level README) and, if the server runs on a remote GPU box, forward its port with `ssh -N -L 30400:127.0.0.1:30400 <gpu-host>`.
Point the demo at it with `SGLANG_BASE_URL=http://127.0.0.1:30400/v1` (the default is port 30000).
Replay only (no GPU, no tunnel): the UI shows "Offline" and Replay works.

Config via environment:

| Variable | Default | Meaning |
|---|---|---|
| `SGLANG_BASE_URL` | `http://127.0.0.1:30000/v1` | OpenAI-compatible endpoint of your SGLang server (for a server on another port, for example `SGLANG_BASE_URL=http://127.0.0.1:30400/v1`) |
| `SGLANG_API_KEY` | `EMPTY` | bearer token |
| `DEMO_CASE_DIRS` | `<repo>/examples` | `:`-separated case directories; the `+` button in the UI adds one at runtime |
| `DEMO_RECORDINGS` | `demo/recordings` | where recordings are read and written |
| `DEMO_RECORD` | `1` | `0` stops saving live runs |

A case directory holds `prompt.txt`, optional `target.json` (ground truth), `meta.json` and `images/D<nn>.png`.
Model names come from `/v1/models`: `base`, and `base:<adapter>` for every LoRA the server reports (so an end-to-end SFT adapter and the per-document adapters appear on their own).
Only one run is allowed at a time, so the demo never piles load onto a shared GPU.

## Recording the demo video

Replay at 4x or 8x gives a deterministic, GPU-free take; label it as sped up (the UI shows the speed in the replay badge).
`e2e/shot.mjs` takes 1920x1080 screenshots through headless Chrome (`cd e2e && npm install`, then `node shot.mjs out.png --kind hybrid --mode replay --speed 8 --run`).

## Tests

```bash
uv run pytest -q
```
