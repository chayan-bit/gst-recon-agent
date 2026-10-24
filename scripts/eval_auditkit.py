"""Score eval runs with AuditKIT 1.1.3 and compare model A vs B with its significance machinery.

Runs in the AuditKIT venv (auditkit[requests]==1.1.3, pydantic, numpy), not the project venv:

    PYTHONPATH=. .venv-auditkit/bin/python scripts/eval_auditkit.py \\
        --cases data/rendered/test_iid data/rendered/test_ood --n-per-dir 100 \\
        --run base=runs/eval/base-unconstrained --run sft=runs/eval/sft \\
        --out runs/eval/auditkit-compare

Sources: `--run NAME=RUN_DIR` scores the predictions already stored in a `gst_recon.eval run` directory
(model="precomputed"); `--api NAME=MODEL@ENDPOINT` makes AuditKIT itself query the SGLang endpoint through its
`api:` backend (same system prompt, temperature 0; `--constrained` adds the json_schema response_format).
The first source is the baseline; every other one is compared against it with `ak.compare()`.
Writes <out>/auditkit_compare.json and <out>/auditkit_compare.md (append it to the report with `report --append`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import auditkit as ak
from auditkit.adapter import ChatAdapter
from auditkit.runspec import RunConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gst_recon.eval.cases import EvalCase, load_cases  # noqa: E402
from gst_recon.eval.client import json_schema_format  # noqa: E402
from gst_recon.eval.guard import mark_eval_dir  # noqa: E402
from gst_recon.eval.metrics import case_metrics  # noqa: E402
from gst_recon.eval.prompts import SYSTEM_PROMPT  # noqa: E402

# (name, higher_is_better); one AuditKIT scorer per gst-recon component metric
SCORERS = (("schema_valid", True), ("extraction_f1", True), ("match_accuracy", True), ("itc_invoice", True),
           ("composite", True), ("itc_abs_err_rs", False))


def make_scorers(cases: dict[str, EvalCase]):
    """Wrap the shared gst-recon scorer as AuditKIT scorers, plus the contributed metrics when the installed
    AuditKIT has them (the feat/structured-extraction-metrics branch)."""
    cache: dict[tuple[str, str], dict] = {}

    def metrics(sample, output):
        key = (sample.id, output)
        if key not in cache:
            cache[key] = case_metrics(output, cases[sample.id])
        return cache[key]

    out = []
    for name, up in SCORERS:
        d = ak.Direction.MAXIMIZE if up else ak.Direction.MINIMIZE
        out.append(ak.scorer(lambda s, o, n=name: float(metrics(s, o)[n]), direction=d, name=name))
    if hasattr(ak, "JsonSchemaValid"):
        out.append(ak.JsonSchemaValid(schema=json.loads((Path(__file__).parent.parent / "schemas" / "output.schema.json").read_text())))
    if hasattr(ak, "FieldF1"):
        out.append(ak.FieldF1(normalize_numbers=True, case_sensitive=False))
    return out


def to_samples(cases: list[EvalCase], outputs: dict[str, str] | None) -> list[ak.Sample]:
    return [ak.Sample(id=c.case_id, input=c.prompt, target=json.dumps(c.target), tags=[c.split, c.difficulty, f"ocr_{c.ocr_bucket}"],
                      metadata={"split": c.split, "difficulty": c.difficulty},
                      actual_output=None if outputs is None else outputs.get(c.case_id, ""))
            for c in cases if outputs is None or c.case_id in outputs]


def stored_outputs(run_dir: Path) -> dict[str, str]:
    return {p.stem: json.loads(p.read_text()).get("raw", "") for p in (run_dir / "cases").glob("*.json")}


def evaluate_source(kind: str, name: str, spec: str, cases: list[EvalCase], scorers, a) -> ak.RunResult:
    cfg = RunConfig(temperature=0.0, max_tokens=a.max_tokens, concurrency=a.concurrency, track_performance=True)
    if kind == "run":
        samples = to_samples(cases, stored_outputs(Path(spec)))
        return ak.evaluate(samples, model="precomputed", scorers=scorers, config=cfg, experiment_name=name)
    model, endpoint = spec.rsplit("@", 1)
    extra = {"response_format": json_schema_format()} if a.constrained else {}
    return ak.evaluate(to_samples(cases, None), model=f"api:{model}", api_base=endpoint, api_key="EMPTY", server="sglang",
                       adapter=ChatAdapter(system_prompt=SYSTEM_PROMPT), scorers=scorers, config=cfg,
                       experiment_name=name, **extra)


def corrected_p(base: ak.RunResult, cand: ak.RunResult, metric: str, n: int = 2000, seed: int = 0) -> dict:
    """Paired bootstrap with a proper null (centred differences). AuditKIT 1.1.3 resamples the raw differences, so
    its p-value sits near 0.5 whatever the effect (see README)."""
    import numpy as np

    from auditkit._bootstrap import score_pairs

    pairs = score_pairs(base, cand, metric)
    if len(pairs) < 2:
        return {"n": len(pairs)}
    diff = np.array([c - b for b, c in pairs])
    boots = diff[np.random.default_rng(seed).integers(0, len(diff), (n, len(diff)))].mean(1)
    p = (np.sum(np.abs(boots - boots.mean()) >= abs(diff.mean())) + 1) / (n + 1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n": len(diff), "delta": float(diff.mean()), "ci_lo": float(lo), "ci_hi": float(hi), "p_value_corrected": float(p)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, nargs="+", required=True)
    ap.add_argument("--n-per-dir", type=int)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--truth-dir", type=Path, default=Path("data/truth"))
    ap.add_argument("--run", action="append", default=[], metavar="NAME=RUN_DIR")
    ap.add_argument("--api", action="append", default=[], metavar="NAME=MODEL@ENDPOINT")
    ap.add_argument("--constrained", action="store_true", help="api sources: send the json_schema response_format")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    sources = [("run", *s.split("=", 1)) for s in a.run] + [("api", *s.split("=", 1)) for s in a.api]
    if len(sources) < 2:
        ap.error("need at least two sources (a baseline and a candidate)")
    cases = load_cases(a.cases, truth_dir=a.truth_dir if a.truth_dir.exists() else None, n_per_dir=a.n_per_dir, seed=a.seed)
    by_id = {c.case_id: c for c in cases}
    scorers = make_scorers(by_id)
    results = {name: evaluate_source(kind, name, spec, cases, scorers, a) for kind, name, spec in sources}

    base_name = sources[0][1]
    metric_names = list(results[base_name].headline)
    doc: dict = {"auditkit_version": ak.__version__, "baseline": base_name, "cases": len(cases), "runs": {}, "comparisons": {}}
    for name, r in results.items():
        doc["runs"][name] = {"fingerprint": r.fingerprint, "run_id": r.run_id, "headline": r.headline, "failed": r.failed_count,
                             "perf": r.perf, "token_usage": r.token_usage, "unscored": r.unscored}
    for name, r in list(results.items())[1:]:
        cmp = ak.compare(results[base_name], r)
        doc["comparisons"][name] = {m: {"auditkit": cmp.significance(m), "corrected": corrected_p(results[base_name], r, m)}
                                    for m in metric_names}
        doc["comparisons"][name]["_grade"] = str(cmp.grade())
    a.out.mkdir(parents=True, exist_ok=True)
    mark_eval_dir(a.out)
    (a.out / "auditkit_compare.json").write_text(json.dumps(doc, indent=1, default=str))
    (a.out / "auditkit_compare.md").write_text(render_md(doc, metric_names))
    print((a.out / "auditkit_compare.md").read_text())
    return 0


def render_md(doc: dict, metric_names: list[str]) -> str:
    L = [f"## AuditKIT {doc['auditkit_version']} comparison", "",
         f"{doc['cases']} cases. Baseline: `{doc['baseline']}`. Run fingerprints (sha256 of model, dataset, adapter, metrics and config):", "",
         "| run | fingerprint |", "|---|---|", *(f"| {n} | `{r['fingerprint']}` |" for n, r in doc["runs"].items()), ""]
    for name, comp in doc["comparisons"].items():
        L += [f"### `{name}` vs `{doc['baseline']}` (grade: {comp['_grade']})", "",
              "| metric | baseline | candidate | delta | AuditKIT p | AuditKIT significant | corrected p (centred bootstrap) | 95% CI of delta |", "|---|---|---|---|---|---|---|---|"]
        for m in metric_names:
            s, c = comp[m]["auditkit"], comp[m]["corrected"]
            if "error" in s or "delta" not in c:
                L.append(f"| {m} | - | - | - | - | - | - | - |")
                continue
            L.append(f"| {m} | {s['mean_baseline']:.4f} | {s['mean_candidate']:.4f} | {s['delta']:+.4f} | {s['p_value']:.3f} | {s['significant']} | "
                     f"{c['p_value_corrected']:.4f} | [{c['ci_lo']:+.4f}, {c['ci_hi']:+.4f}] |")
        L.append("")
    L.append("AuditKIT 1.1.3's `p_value` comes from resampling the raw paired differences without centring them on the null, "
             "so it stays near 0.5 for any effect size; the corrected column centres them. Prefer the corrected p until upstream fixes it.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
