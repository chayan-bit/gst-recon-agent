"""Oracle check: the TRUE per-document records (truth Case + target extraction, `hybrid.sft.truth_records`) fed
through the real hybrid path (`eval.runner.run_eval` + `hybrid.run.make_generator`, so the reply JSON parsing,
repair, identity fill, linker and rules engine all run) must reproduce the target. Misses are listed per
document with the reconciler's own explanation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gst_recon.eval.cases import load_cases
from gst_recon.eval.runner import run_eval
from gst_recon.hybrid.inputs import parse_prompt
from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.hybrid.run import make_generator
from gst_recon.hybrid.sft import truth_records
from gst_recon.rewards import expand


def _answers(cases) -> dict[str, dict]:
    """case_id -> {doc block: true record JSON}."""
    out = {}
    for c in cases:
        recs = truth_records(c.target, c.truth)
        out[c.case_id] = {d.block: recs[d.doc_id].model_dump_json() for d in parse_prompt(c.prompt).docs}
    return out


def _misses(c) -> list[dict]:
    want = expand(c.target)
    got, trace = reconcile_prompt(c.prompt, truth_records(c.target, c.truth))
    got = got.model_dump(mode="json")
    rows = []
    for key in ("extractions", "matches", "itc"):
        w, g = {r["doc_id"]: r for r in want[key]}, {r["doc_id"]: r for r in got[key]}
        for doc_id in sorted(w.keys() | g.keys()):
            if w.get(doc_id) != g.get(doc_id):
                rows.append({"doc_id": doc_id, "part": key, "want": w.get(doc_id), "got": g.get(doc_id),
                             "why": trace.get("decisions", {}).get(doc_id), "repairs": trace.get("repairs", {}).get(doc_id),
                             "fills": trace.get("fills", {}).get(doc_id), "links": trace.get("links", {}).get(doc_id) if isinstance(trace.get("links"), dict) else None})
    return rows


def run_oracle(cases_dir: Path, truth_dir: Path, out: Path) -> dict:
    cases = load_cases([cases_dir], truth_dir=truth_dir)
    if any(c.truth is None for c in cases):
        raise FileNotFoundError(f"truth Case JSON missing under {truth_dir} for some case in {cases_dir}")
    answers = _answers(cases)

    def call(messages):
        user = messages[-1]["content"]
        text = next((t for blocks in answers.values() for b, t in blocks.items() if user.rstrip("\n").endswith(b)), "")
        return {"text": text, "prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0, "error": None if text else "no oracle answer"}

    shutil.rmtree(out, ignore_errors=True)  # no cached per-document replies from an earlier build
    agg = run_eval(cases, make_generator(call, out, concurrency=4), out, {"label": f"oracle {cases_dir.name}", "mode": "hybrid"},
                   concurrency=2, resume=False)
    scores = {r["case_id"]: r for r in map(json.loads, (out / "scores.jsonl").read_text().splitlines())}
    per_case = {c.case_id: {"metrics": {k: scores[c.case_id]["metrics"].get(k) for k in ("composite", "itc_invoice", "match_accuracy")},
                            "error": scores[c.case_id].get("error"), "misses": _misses(c)} for c in cases}
    groups: dict[str, list] = {}
    for c in cases:
        groups.setdefault(c.difficulty, []).append(per_case[c.case_id])
    by_difficulty = {g: {"n_cases": len(v), "itc_invoice": sum(x["metrics"]["itc_invoice"] for x in v) / len(v),
                         "cases_with_misses": sum(bool(x["misses"]) for x in v)} for g, v in sorted(groups.items())}
    return {"cases_dir": str(cases_dir), "n_cases": len(cases), "by_difficulty": by_difficulty, "overall": {k: agg["overall"][k]["mean"] for k in
            ("composite", "itc_invoice", "match_accuracy") if k in agg["overall"]}, "n_errors": agg["n_errors"], "cases": per_case}
