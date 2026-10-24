"""Markdown tables and bar chart across runs. Reads runs/eval/<name>/aggregate.json (+ scores.jsonl)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from gst_recon.eval.stats import paired_delta

COLS = (("itc_invoice", "ITC invoice exact %", 100), ("context_acc", "Context acc %", 100),
        ("itc_overclaim_rs", "ITC overclaim (Rs)", 1), ("itc_underclaim_rs", "ITC underclaim (Rs)", 1),
        ("itc_abs_err_rs", "ITC net abs err (Rs)", 1), ("match_accuracy", "Match acc %", 100),
        ("extraction_f1", "Field F1 %", 100), ("schema_valid", "Schema valid %", 100), ("composite", "Composite (0-100)", 100))
BASELINE_KEYS = {"field_f1": "extraction_f1", "context_doc_acc": "context_acc"}
CHART_METRICS = (("itc_invoice", "ITC invoice exact"), ("context_acc", "Context accuracy"), ("match_accuracy", "Match accuracy"),
                 ("composite", "Composite (secondary)"))


def _fmt(v: float | None, scale: float, nd: int = 1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    return f"{v * scale:,.0f}" if scale == 1 else f"{v * scale:.{nd}f}"


def _cell(m: dict | None, scale: float, ci: bool) -> str:
    if not m:
        return "-"
    s = _fmt(m.get("mean"), scale)
    if ci and "ci_lo" in m:
        s += f" [{_fmt(m['ci_lo'], scale)}, {_fmt(m['ci_hi'], scale)}]"
    return s


def _table(header: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header), *("| " + " | ".join(r) + " |" for r in rows)])


def _metric_cells(summary: dict, ci: bool) -> list[str]:
    return [_cell(summary.get(k), s, ci) for k, _, s in COLS]


def _money(x: float | None) -> str:
    return "-" if x is None else f"${x:,.2f}"


def _perf_cells(agg: dict) -> list[str]:
    t, c = agg["throughput"], agg["cost_per_1000_cases"]
    f = lambda v, nd=2: "-" if v is None else f"{v:.{nd}f}"  # noqa: E731
    return [f(t["req_per_s"]), f(t["out_tok_per_s"], 0), f(t["latency_p50_s"], 1), _money(c["gpu_usd"]), _money(c["api_usd"])]


PERF_HEAD = ["req/s", "out tok/s", "p50 latency (s)", "GPU $/1k cases", "API list $/1k cases"]


DIMS = (("split", "By split"), ("difficulty", "By difficulty"), ("split_difficulty", "By split and difficulty"),
        ("ocr_bucket", "By OCR recall (full = every field present in the prompt)"),
        ("length_bucket", "By case prompt length (Qwen3 tokens: <=16k, 16-32k, >32k)"))


def run_table_md(agg: dict) -> str:
    """table.md of one run: primary metrics with 95% CIs, breakdowns, throughput and cost."""
    head = ["group", "n"] + [c[1] for c in COLS]
    parts = [f"# {agg['label']}", "",
             f"cases: {agg['n_cases']}, transport errors: {agg['n_errors']} (context overflow: {agg.get('n_context_overflow', 0)}), truncated (finish_reason=length): {agg['n_truncated']}",
             f"context accuracy source: {agg['context_source']}", "", "## Overall (bootstrap 95% CI over cases)", "",
             _table(head, [["all", str(agg["n_cases"])] + _metric_cells(agg["overall"], True)])]
    for dim, title in DIMS:
        if dim not in agg["breakdowns"]:
            continue
        rows = [[g, str(s["n"])] + _metric_cells(s, False) for g, s in agg["breakdowns"][dim].items()]
        parts += ["", f"## {title}", "", _table(head, rows)]
    parts += ["", "## Throughput and cost", "", _table(PERF_HEAD, [_perf_cells(agg)]), ""]
    sec = agg["overall"]
    parts.append("Secondary: " + ", ".join(f"{k}={_cell(sec[k], 100 if 'err' not in k else 1, False)}"
                                           for k in ("grpo", "parse_ok", "arithmetic", "itc_reasons", "itc_total_exact", "itc_all_abs_err_rs")))
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------- multi-run


def find_run_dirs(paths: list[Path]) -> list[Path]:
    """Each path is a run dir (has aggregate.json) or a parent of run dirs."""
    out: list[Path] = []
    for p in paths:
        if (p / "aggregate.json").exists():
            out.append(p)
        elif p.is_dir():
            out += sorted(c for c in p.iterdir() if (c / "aggregate.json").exists())
    return out


def load_runs(paths: list[Path]) -> list[dict]:
    runs = []
    for d in find_run_dirs(paths):
        agg = json.loads((d / "aggregate.json").read_text())
        agg["dir"] = str(d)
        runs.append(agg)
    return runs


def load_baselines(path: Path | None) -> dict[str, dict[str, dict]]:
    """sim audit --json output -> {split: {baseline name: {metric: value}}}."""
    if path is None:
        return {}
    out: dict[str, dict[str, dict]] = {}
    for key, row in json.loads(Path(path).read_text())["baselines"].items():
        split, name = key.split("/", 1)
        if name == "rules_engine":
            continue  # the oracle, not a baseline
        out.setdefault(split, {})[name] = {BASELINE_KEYS.get(k, k): v for k, v in row.items()}
    return out


def _records(run: dict) -> list[dict]:
    p = Path(run["dir"]) / "scores.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def _baseline_cells(row: dict) -> list[str]:
    return [_fmt(row.get(k), s) if k in row and row[k] is not None else "-" for k, _, s in COLS]


def report_md(runs: list[dict], baselines: dict[str, dict[str, dict]] | None = None, ref: str | None = None,
              appendices: list[str] | None = None, placeholders: list[str] | None = None) -> str:
    baselines = baselines or {}
    pending = lambda ncols, extra=0: [[f"{n} (not run yet)", *["-"] * (ncols - 1 + extra)] for n in placeholders or []]  # noqa: E731
    head = ["run", "n"] + [c[1] for c in COLS]
    parts = ["# gst-recon evaluation results", "",
             "Headline metrics are ITC invoice exact and context accuracy; the composite (the weighted reward) is secondary because "
             "its floor is high (trivial baselines score about 80). ITC overclaim is the rupees of credit the model would have wrongly "
             "claimed (per invoice, sum of max(0, predicted eligible - true eligible)); underclaim is the mirror; net abs err is the "
             "absolute error of the claimed eligible total, where invoices can cancel. Cells are percentages unless stated; "
             "[lo, hi] is a bootstrap 95% CI over cases. Trivial baselines are handed the true extraction and links "
             "(they isolate the decisions): their field F1 and match accuracy are oracle values and their composite already "
             "includes full credit for extraction, schema and arithmetic, so compare them on ITC invoice exact, context accuracy and ITC error only.", "",
             "## Overall", "", _table(head, [[r["label"], str(r["n_cases"])] + _metric_cells(r["overall"], True) for r in runs] + pending(len(head))),
             "", "## Throughput and cost per 1,000 cases", "",
             _table(["run", *PERF_HEAD], [[r["label"], *_perf_cells(r)] for r in runs] + pending(len(PERF_HEAD) + 1)),
             "", "GPU cost = measured wall time x the GPU-hour price passed to `run`. API cost = this run's mean token counts x the list "
             "price passed to `run`. Prices are inputs, not facts; `-` means no price was given.", ""]
    splits = sorted({s for r in runs for s in r["breakdowns"]["split"]})
    for split in splits:
        rows = [[r["label"], str(r["breakdowns"]["split"][split]["n"])] + _metric_cells(r["breakdowns"]["split"][split], False)
                for r in runs if split in r["breakdowns"]["split"]]
        rows += [[f"baseline: {name}", "-"] + _baseline_cells(row) for name, row in baselines.get(split, {}).items()
                 if any(row.get(k) is not None for k, _, _ in COLS)]
        rows += pending(len(head))
        parts += [f"## {split}", "", _table(head, rows), ""]
    for dim, title in DIMS[1:]:
        rows = [[r["label"], g, str(s["n"])] + _metric_cells(s, False) for r in runs for g, s in r["breakdowns"].get(dim, {}).items()]
        if not rows:
            continue
        parts += [f"## {title}", "", _table(["run", "group", "n", *[c[1] for c in COLS]], rows), ""]
    if ref:
        refs = [r for r in runs if ref in (r["label"], Path(r["dir"]).name)]
        if refs:
            parts += [_vs_ref(refs[0], [r for r in runs if r is not refs[0]]), ""]
    parts += (appendices or [])
    return "\n".join(parts).rstrip() + "\n"


def _vs_ref(ref: dict, others: list[dict]) -> str:
    rows = []
    ra = _records(ref)
    for r in others:
        for name in ("itc_invoice", "context_acc", "composite"):
            d = paired_delta(ra, _records(r), name)
            if "delta" in d:
                rows.append([r["label"], name, f"{int(d['n'])}", f"{d['delta'] * 100:+.1f} [{d['ci_lo'] * 100:+.1f}, {d['ci_hi'] * 100:+.1f}]", f"{d['p_value']:.4f}"])
    return "\n".join([f"## Paired difference vs {ref['label']}", "",
                      _table(["run", "metric", "paired n", "delta pts [95% CI]", "bootstrap p"], rows),
                      "", "Paired by case_id; p-value from a centred paired bootstrap (null: zero mean difference)."])


def chart(runs: list[dict], baselines: dict[str, dict[str, dict]], out_png: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    splits = [s for s in ("test_iid", "test_ood") if any(s in r["breakdowns"]["split"] for r in runs)] or ["all"]
    colors = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")  # Okabe-Ito, colour-blind safe
    fig, axes = plt.subplots(1, len(splits), figsize=(max(6, 1.1 * len(runs) + 4) * len(splits) / 1.6, 5), sharey=True, squeeze=False)
    for ax, split in zip(axes[0], splits):
        entries: list[tuple[str, dict]] = []
        for r in runs:
            s = r["breakdowns"]["split"].get(split) if split != "all" else r["overall"]
            if s:
                entries.append((r["label"], {k: (s[k]["mean"] if isinstance(s.get(k), dict) else None) for k, _ in CHART_METRICS}))
        entries += [(f"{n} (baseline)", row) for n, row in baselines.get(split, {}).items()]
        w = 0.8 / len(CHART_METRICS)
        for j, (key, name) in enumerate(CHART_METRICS):
            vals = [e[1].get(key) for e in entries]
            bars = ax.bar([i + j * w for i in range(len(entries))], [v if v is not None else 0 for v in vals], w, label=name, color=colors[j])
            for bar, (label, _) in zip(bars, entries):
                if label.endswith("(baseline)"):
                    bar.set_hatch("//")
                    bar.set_alpha(0.55)
        ax.set_xticks([i + 0.4 - w / 2 for i in range(len(entries))])
        ax.set_xticklabels([e[0] for e in entries], rotation=35, ha="right", fontsize=8)
        ax.set_title(split)
        ax.set_ylim(0, 1.05)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.25)
    axes[0][0].set_ylabel("score (0-1)")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, frameon=False, loc="upper center", ncol=len(labels))
    fig.text(0.5, 0.005, "hatched = trivial baseline given the true extraction and links (oracle field F1 and match accuracy)",
             ha="center", fontsize=7, color="#555555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png
