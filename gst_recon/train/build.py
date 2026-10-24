"""Rendered cases -> SFT and GRPO rows, token-length filtering and statistics.

Input: <rendered>/<case_id>/{prompt.txt, target.json, meta.json} (gst_recon.render).
Train-split cases are partitioned by a hash of case_id into SFT and GRPO pools
(disjoint, so GRPO never optimises on prompts the SFT stage memorised); test
splits are written as GRPO-style eval rows only, never as training data.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from gst_recon.eval.guard import refuse_eval_path
from gst_recon.eval.prompts import build_messages
from gst_recon.rewards import compact

SFT_SHARE = 0.7
TEMPLATE_OVERHEAD = 16  # chat-template role markers around system + user (+ assistant) turns
GRPO_MAX_PROMPT = 6144  # training budgets (coordinator): GRPO prompt <= 6k, completion <= 3k
GRPO_MAX_COMPLETION = 3072
SFT_MAX_SEQ = 12288  # SFT prompt + target <= 12k


@dataclass(frozen=True)
class Candidate:
    case_id: str
    split: str
    difficulty: str
    n_docs: int
    prompt: str
    target: str
    prompt_tokens: int
    target_tokens: int
    unrecoverable: tuple[str, ...]  # "doc_id:fact" the OCR lost (render recall check)
    path: str


def _read(path: Path) -> str:
    return refuse_eval_path(path).read_text()


def load_rendered(root: Path) -> list[Candidate]:
    """Every path read goes through the eval guard: frontier/eval outputs never become training data."""
    root = refuse_eval_path(root)
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        meta = json.loads(_read(d / "meta.json"))
        lost = tuple(f"{u['doc_id']}:{f}" for u in meta.get("unrecoverable", []) for f in u["facts"])
        out.append(Candidate(meta["case_id"], meta["split"], meta["difficulty"], len(meta["documents"]),
                             _read(d / "prompt.txt"), _read(d / "target.json").strip(),
                             meta["prompt_tokens"], meta["target_tokens"], lost, str(refuse_eval_path(d))))
    return out


HSN_LOST = re.compile(r"^(D\d+):line(\d+)_hsn$")


def mask_lost_hsn(c: Candidate) -> Candidate | None:
    """Curated OCR rule: a line HSN code the OCR lost (the most common loss) is blanked in the
    target, so training teaches "unreadable -> empty" rather than invention; any other lost
    fact (amounts, ids, remarks) drops the case (None). target_tokens stays an upper bound."""
    hits = [HSN_LOST.match(f) for f in c.unrecoverable]
    if not all(hits):
        return None
    if not hits:
        return c
    t = json.loads(c.target)
    docs = {e["doc_id"]: e for e in t["extractions"]}
    for m in hits:
        lines = docs.get(m.group(1), {}).get("line_items", [])
        if int(m.group(2)) >= len(lines):
            return None
        lines[int(m.group(2))]["hsn"] = ""
    return replace(c, target=_dump(compact(t)), unrecoverable=())


def _dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def compact_target(c: Candidate, count) -> Candidate:
    """Training targets use the compact output form (zero / false / empty fields left out, about
    a quarter fewer tokens); rewards.parse_output expands it, so it scores like the full form."""
    target = _dump(compact(json.loads(c.target)))
    return replace(c, target=target, target_tokens=count(target)[0])


def role(case_id: str) -> str:
    """'sft' or 'grpo' for a train case: from the size-profile prefix (sim --size), else a stable hash."""
    for r in ("sft", "grpo"):
        if case_id.startswith(f"{r}-"):
            return r
    h = int(hashlib.sha256(f"train-role:{case_id}".encode()).hexdigest(), 16)
    return "sft" if h % 1000 < SFT_SHARE * 1000 else "grpo"


def with_prompt(c: Candidate, prompt: str, tokens: int) -> Candidate:
    return replace(c, prompt=prompt, prompt_tokens=tokens)


def sft_row(c: Candidate) -> dict:
    return {"case_id": c.case_id, "difficulty": c.difficulty, "n_docs": c.n_docs,
            "messages": build_messages(c.prompt) + [{"role": "assistant", "content": c.target}]}


def grpo_row(c: Candidate) -> dict:
    """`reference` is the truth ReconOutput JSON: AlignTune passes it to the reward as `reference`."""
    return {"case_id": c.case_id, "difficulty": c.difficulty, "n_docs": c.n_docs, "prompt": build_messages(c.prompt),
            "reference": c.target}


def length_ok(c: Candidate, kind: str, sys_tokens: int, limits: dict[str, int]) -> bool:
    p = c.prompt_tokens + sys_tokens + TEMPLATE_OVERHEAD
    if kind == "sft":
        return p + c.target_tokens <= limits["sft_max_seq"]
    return p <= limits["grpo_max_prompt"] and c.target_tokens <= limits["grpo_max_completion"]


def _pct(xs: list[int], q: float) -> int:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0


def group(c: Candidate) -> str:
    """Histogram group: train cases by stage pool, eval splits by name."""
    return f"train-{role(c.case_id)}" if c.split == "train" else c.split


def token_report(cands: list[Candidate], sys_tokens: int, limits: dict[str, int]) -> dict:
    """Prompt/target token percentiles by difficulty and by document count, and the largest
    document count whose p95 still fits each stage (the proposed max invoices per case)."""
    full = [(c, c.prompt_tokens + sys_tokens + TEMPLATE_OVERHEAD) for c in cands]

    def summary(rows: list[tuple[Candidate, int]]) -> dict:
        p, t = [x for _, x in rows], [c.target_tokens for c, _ in rows]
        return {"n": len(rows), "prompt_p50": _pct(p, .5), "prompt_p95": _pct(p, .95), "prompt_max": max(p, default=0),
                "target_p50": _pct(t, .5), "target_p95": _pct(t, .95), "target_max": max(t, default=0),
                "sum_p95": _pct([a + b for a, b in zip(p, t)], .95)}

    by_docs = {}
    for lo in range(0, max((c.n_docs for c in cands), default=0) + 1, 5):
        rows = [r for r in full if lo <= r[0].n_docs < lo + 5]
        if rows:
            by_docs[f"{lo}-{lo + 4}"] = summary(rows)
    def hist(xs: list[int], width: int = 2048) -> dict[str, int]:
        out: dict[str, int] = {}
        for x in sorted(xs):
            lo = x // width * width
            out[f"{lo // 1024}-{(lo + width) // 1024}k"] = out.get(f"{lo // 1024}-{(lo + width) // 1024}k", 0) + 1
        return out

    def hists(rows: list[tuple[Candidate, int]]) -> dict:
        return {"prompt": hist([p for _, p in rows]), "target": hist([c.target_tokens for c, _ in rows]),
                "total": hist([p + c.target_tokens for c, p in rows])}

    fits = lambda k: max((int(b.split("-")[1]) for b, s in by_docs.items() if k(s)), default=0)
    return {
        "system_prompt_tokens": sys_tokens,
        "by_difficulty": {d: summary([r for r in full if r[0].difficulty == d]) for d in ("easy", "medium", "hard")},
        "by_n_docs": by_docs,
        "by_group": {g: summary([r for r in full if group(r[0]) == g]) for g in sorted({group(c) for c in cands})},
        "histogram": {g: hists([r for r in full if group(r[0]) == g]) for g in sorted({group(c) for c in cands})},
        "proposed_max_docs": {
            "grpo": fits(lambda s: s["prompt_p95"] <= limits["grpo_max_prompt"]
                         and s["target_p95"] <= limits["grpo_max_completion"]),
            "sft": fits(lambda s: s["sum_p95"] <= limits["sft_max_seq"]),
        },
        "limits": limits,
    }


def write_jsonl(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def export(cands: list[Candidate], out: Path, sys_tokens: int, limits: dict[str, int]) -> dict:
    """Write <out>/sft/train.jsonl and <out>/grpo/train.jsonl from train cases; returns counts."""
    train = [c for c in cands if c.split == "train"]
    counts = {}
    for kind, make in (("sft", sft_row), ("grpo", grpo_row)):
        pool = [c for c in train if role(c.case_id) == kind]
        keep = [c for c in pool if length_ok(c, kind, sys_tokens, limits)]
        counts[kind] = {"pool": len(pool), "too_long": len(pool) - len(keep),
                        "rows": write_jsonl(out / kind / "train.jsonl", [make(c) for c in keep]),
                        "by_difficulty": {d: sum(c.difficulty == d for c in keep) for d in ("easy", "medium", "hard")}}
    return counts


def export_eval(cands: list[Candidate], out: Path) -> dict[str, int]:
    """Test splits as prompt + reference rows (for eval only; never mixed into training files)."""
    return {s: write_jsonl(out / f"{s}.jsonl", [grpo_row(c) for c in cands if c.split == s])
            for s in ("test_iid", "test_ood") if any(c.split == s for c in cands)}

