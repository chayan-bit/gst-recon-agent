"""Aggregation with bootstrap CIs. Every metric is a ratio sum(num)/sum(den) over cases, so plain
means (den 1) and pooled ratios (context accuracy over documents) share one code path."""

from __future__ import annotations

from typing import Any

import numpy as np

# Headline first: ITC invoice-exact and context accuracy separate systems; the composite has a high floor (trivial
# baselines score ~80), so it is secondary.
PRIMARY = ("itc_invoice", "context_acc", "itc_overclaim_rs", "itc_underclaim_rs", "itc_abs_err_rs", "match_accuracy",
           "extraction_f1", "schema_valid")
SECONDARY = ("composite", "grpo", "parse_ok", "arithmetic", "itc_reasons", "itc_total_exact", "itc_all_abs_err_rs")
ALL_METRICS = PRIMARY + SECONDARY
N_BOOT = 2000
LENGTH_ORDER = ["<=16k", "16-32k", ">32k"]


def _num_den(rec: dict, name: str) -> tuple[float, float]:
    m = rec["metrics"]
    if name == "context_acc":
        return float(m["context_ok"]), float(m["context_n"])
    return float(m[name]), 1.0


def arrays(records: list[dict], name: str) -> tuple[np.ndarray, np.ndarray]:
    nd = [_num_den(r, name) for r in records]
    return np.array([x[0] for x in nd], float), np.array([x[1] for x in nd], float)


def _ratio(num: np.ndarray, den: np.ndarray) -> float:
    d = den.sum()
    return float("nan") if d == 0 else float(num.sum() / d)


def metric_summary(records: list[dict], name: str, *, ci: bool = True, seed: int = 0) -> dict[str, float]:
    num, den = arrays(records, name)
    out = {"mean": _ratio(num, den), "n": float(den.sum())}
    if ci and len(records) > 1 and den.sum() > 0:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, len(records), size=(N_BOOT, len(records)))
        d = den[idx].sum(1)
        vals = num[idx].sum(1)[d > 0] / d[d > 0]
        out["ci_lo"], out["ci_hi"] = (float(x) for x in np.percentile(vals, [2.5, 97.5]))
    return out


def summarize(records: list[dict], *, ci: bool = True) -> dict[str, Any]:
    return {"n": len(records), **{m: metric_summary(records, m, ci=ci) for m in ALL_METRICS}}


def breakdowns(records: list[dict]) -> dict[str, dict[str, Any]]:
    """Metric means (no CI) per split, difficulty and OCR-recall bucket."""
    out: dict[str, dict[str, Any]] = {}
    recs = [{**r, "split_difficulty": f"{r['split']}/{r['difficulty']}"} for r in records]
    for dim in ("split", "difficulty", "split_difficulty", "ocr_bucket", "length_bucket"):
        groups = sorted({r[dim] for r in recs}, key=lambda g: (LENGTH_ORDER.index(g) if g in LENGTH_ORDER else 9, g))
        out[dim] = {g: summarize([r for r in recs if r[dim] == g], ci=False) for g in groups}
    return out


def paired_delta(a: list[dict], b: list[dict], name: str = "composite", seed: int = 0) -> dict[str, float]:
    """Mean per-case difference b - a over shared case_ids, with a paired bootstrap 95% CI and a
    two-sided bootstrap p-value (null: mean difference 0, via centred resampling)."""
    ia, ib = {r["case_id"]: r for r in a}, {r["case_id"]: r for r in b}
    ids = sorted(ia.keys() & ib.keys())
    if len(ids) < 2:
        return {"n": float(len(ids))}
    na, da = arrays([ia[i] for i in ids], name)
    nb, db = arrays([ib[i] for i in ids], name)
    ok = (da > 0) & (db > 0)
    diff = nb[ok] / db[ok] - na[ok] / da[ok]
    if len(diff) < 2:
        return {"n": float(len(diff))}
    rng = np.random.default_rng(seed)
    boots = diff[rng.integers(0, len(diff), size=(N_BOOT, len(diff)))].mean(1)
    centred = boots - boots.mean()
    p = (np.sum(np.abs(centred) >= abs(diff.mean())) + 1) / (N_BOOT + 1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n": float(len(diff)), "delta": float(diff.mean()), "ci_lo": float(lo), "ci_hi": float(hi), "p_value": float(p)}
