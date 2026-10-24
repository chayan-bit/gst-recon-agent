"""Shortcut audit: base rates, trivial baselines, spurious correlations.

    python -m gst_recon.sim.audit [--n 2000] [--n-test 300] [--seed 0] [--json out.json]

(a) per-flag and per-reason base rates by difficulty (train);
(b) trivial baselines on test_iid / test_ood, scored with the reward functions.
    Every baseline is handed the true extraction and true document links, so
    the scores isolate the decisions (flags, ITC buckets, reasons):
      majority       global majority flag set / reason set, all tax eligible
      no_anomaly     every document clean (reason from the visible doc type / RCM flag)
      keyword        no_anomaly + per-line s.17(5) label looked up from description
                     tokens learned on train
      context_blind  the real rules engine with perfect document comparison but
                     no buyer profile and no remarks (category decides s.17(5))
(c) spurious correlations: for each document feature x flag, the largest
    deviation of the flag rate within one feature value from the base rate.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from statistics import mean
from typing import Callable

from gst_recon.rewards import score
from gst_recon.schema import Case, DocType, ItcDecision, LinePurpose, MatchFlag, ReasonCode, TaxHeads, TruthLineItem
from gst_recon.sim.rules import HEADS, Link, line_block_reason, reconcile, totals_of
from gst_recon.sim.world import DIFFICULTY, generate_case

# r.37 reversal applies only to forward-charge invoices: unpaid_180d is tested on those alone
LEGAL_SCOPE = {"unpaid_180d": lambda f: f["doc_type"] == "invoice" and f["reverse_charge"] == "False"}
MIN_SUPPORT, MAX_DEV, MIN_Z = 100, 0.03, 5.0


def gen(split: str, n: int, seed: int) -> list[Case]:
    diffs = sorted(DIFFICULTY)
    return [generate_case(seed, diffs[i % 3], i // 3, split=split) for i in range(n)]


# --------------------------------------------------------------- (a) base rates


def base_rates(cases: list[Case]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for d in sorted(DIFFICULTY):
        cs = [c for c in cases if c.difficulty == d]
        docs = [m for c in cs for m in c.expected.matches]
        itc = [x for c in cs for x in c.expected.itc]
        row = {f"flag:{f.value}": mean(f in m.flags for m in docs) for f in MatchFlag}
        row |= {f"reason:{r.value}": mean(r in x.reasons for x in itc) for r in ReasonCode}
        row["docs"] = len(docs)
        out[d] = row
    return out


# --------------------------------------------------------------- (b) baselines

BlockFn = Callable[[TruthLineItem], ReasonCode | None]
TOKEN = re.compile(r"[a-z0-9]+")


def _decision(inv, block: BlockFn) -> ItcDecision:
    zero = {h: 0.0 for h in HEADS}
    if inv.doc_type == DocType.CREDIT_NOTE:
        neg = {h: -getattr(inv, h) for h in HEADS}
        return ItcDecision(doc_id=inv.doc_id, eligible=TaxHeads(**neg), blocked=TaxHeads(**zero),
                           deferred=TaxHeads(**zero), reasons=[ReasonCode.CREDIT_NOTE_REVERSAL])
    blocked, eligible, reasons = dict(zero), dict(zero), set()
    for li in inv.line_items:
        r = block(li)
        target = blocked if r else eligible
        for h in HEADS:
            target[h] = round(target[h] + getattr(li, h), 2)
        if r and any(getattr(li, h) for h in HEADS):
            reasons.add(r)
    if any(eligible.values()) or not reasons:
        reasons.add(ReasonCode.RCM_ELIGIBLE if inv.reverse_charge else ReasonCode.ELIGIBLE)
    return ItcDecision(doc_id=inv.doc_id, eligible=TaxHeads(**eligible), blocked=TaxHeads(**blocked),
                       deferred=TaxHeads(**zero), reasons=[r for r in ReasonCode if r in reasons])


def _clean_output(c: Case, block: BlockFn) -> dict:
    out = c.expected.model_dump(mode="json")
    for m in out["matches"]:
        m["flags"] = []
    itc = [_decision(inv, block) for inv in c.inputs.invoices]
    out["itc"] = [x.model_dump(mode="json") for x in itc]
    out["itc_totals"] = totals_of(itc).model_dump(mode="json")
    return out


def majority_baseline(train: list[Case]) -> Callable[[Case], dict]:
    flags = Counter(tuple(m.flags) for c in train for m in c.expected.matches).most_common(1)[0][0]
    reasons = Counter(tuple(x.reasons) for c in train for x in c.expected.itc).most_common(1)[0][0]

    def predict(c: Case) -> dict:
        out = c.expected.model_dump(mode="json")
        zero = {h: 0.0 for h in HEADS}
        itc = [ItcDecision(doc_id=inv.doc_id, eligible=TaxHeads(**{h: getattr(inv, h) for h in HEADS}),
                           blocked=TaxHeads(**zero), deferred=TaxHeads(**zero), reasons=list(reasons))
               for inv in c.inputs.invoices]
        for m in out["matches"]:
            m["flags"] = [f.value for f in flags]
        out["itc"] = [x.model_dump(mode="json") for x in itc]
        out["itc_totals"] = totals_of(itc).model_dump(mode="json")
        return out
    return predict


def keyword_model(train: list[Case]) -> BlockFn:
    """Multinomial naive Bayes, description tokens -> s.17(5) label (OK or a block reason)."""
    counts: dict[str, Counter] = defaultdict(Counter)
    prior: Counter = Counter()
    for c in train:
        for inv in c.inputs.invoices:
            for li in inv.line_items:
                r = line_block_reason(li, c.inputs.buyer_profile)
                label = r.value if r else "OK"
                prior[label] += 1
                counts[label].update(TOKEN.findall(li.description.lower()))
    vocab = {t for cnt in counts.values() for t in cnt}
    size = {k: sum(v.values()) + len(vocab) for k, v in counts.items()}
    n = sum(prior.values())

    def block(li: TruthLineItem) -> ReasonCode | None:
        toks = [t for t in TOKEN.findall(li.description.lower()) if t in vocab]
        label = max(prior, key=lambda k: math.log(prior[k] / n)
                    + sum(math.log((counts[k][t] + 1) / size[k]) for t in toks))
        return None if label == "OK" else ReasonCode(label)
    return block


def context_blind(c: Case) -> dict:
    links = {m.doc_id: Link(tuple(m.register_vouchers),
                            (m.gstr2b_period, m.gstr2b_ctin, m.gstr2b_doc_no) if m.gstr2b_period else None,
                            tuple(m.payment_refs)) for m in c.expected.matches}
    invs = [inv.model_copy(update={"line_items": [li.model_copy(update={"purpose": LinePurpose.BUSINESS})
                                                  for li in inv.line_items]}) for inv in c.inputs.invoices]
    blind = c.inputs.model_copy(update={"buyer_profile": None, "invoices": invs})
    return reconcile(blind, links).model_dump(mode="json")


def _sensitive(li: TruthLineItem) -> bool:
    """Lines whose s.17(5) outcome depends on the buyer context, not the item alone."""
    return li.category.value != "normal" or li.purpose != LinePurpose.BUSINESS


def line_accuracy(cases: list[Case], block: BlockFn, only_sensitive: bool = False) -> float:
    pairs = [(block(li), line_block_reason(li, c.inputs.buyer_profile))
             for c in cases for inv in c.inputs.invoices if inv.doc_type == DocType.INVOICE
             for li in inv.line_items if _sensitive(li) or not only_sensitive]
    return mean(a == b for a, b in pairs)


METRICS = ("match_accuracy", "itc_invoice", "itc_reasons", "itc_total", "composite")


def evaluate(train: list[Case], tests: dict[str, list[Case]]) -> dict:
    kw = keyword_model(train)
    preds = {"majority": majority_baseline(train), "no_anomaly": lambda c: _clean_output(c, lambda li: None),
             "keyword": lambda c: _clean_output(c, kw), "context_blind": context_blind,
             "rules_engine": lambda c: c.expected.model_dump(mode="json")}
    table: dict = {}
    for split, cases in tests.items():
        for name, fn in preds.items():
            scores = [score(fn(c), c.expected) for c in cases]
            table[(split, name)] = {k: mean(s[k] for s in scores) for k in METRICS}
        for name, fn in (("keyword", kw), ("no_anomaly", lambda li: None)):
            table[(split, name)] |= {"line_acc": line_accuracy(cases, fn), "ctx_line_acc": line_accuracy(cases, fn, True)}
    table[("train", "keyword")] = {"line_acc": line_accuracy(train, kw), "ctx_line_acc": line_accuracy(train, kw, True)}
    return table


# ------------------------------------------------------- (c) spurious correlations


def _fmt_class(no: str) -> str:
    return re.sub(r"[A-Z]+", "A", re.sub(r"\d+", "9", no.upper()))


def doc_features(c: Case) -> list[tuple[dict[str, str], dict[str, bool]]]:
    flags = {m.doc_id: set(m.flags) for m in c.expected.matches}
    rows = []
    for pos, inv in enumerate(c.inputs.invoices):
        name = inv.supplier_name.split()
        feats = {
            "supplier_state": inv.supplier_gstin[:2], "intra_state": str(inv.supplier_gstin[:2] == inv.place_of_supply),
            "invoice_no_format": _fmt_class(inv.invoice_no), "name_first_token": name[0],
            "name_second_token": name[1] if len(name) > 1 else "", "position": str(min(pos // 5, 6)),
            "doc_type": inv.doc_type.value, "reverse_charge": str(inv.reverse_charge),
            "n_lines": str(len(inv.line_items)), "concept": inv.line_items[0].concept,
            "category": inv.line_items[0].category.value, "has_remark": str(bool(inv.remarks)),
            "profile": c.inputs.buyer_profile.profile.value,
        }
        rows.append((feats | {"difficulty": c.difficulty}, {f.value: f in flags[inv.doc_id] for f in MatchFlag}))
    return rows


def spurious(cases: list[Case]) -> list[dict]:
    """Per feature x flag, the feature value whose flag rate deviates most from the rate
    expected given its documents' difficulty mix (difficulty drives both the number
    of documents and the anomaly rates, so it is controlled for, not tested)."""
    all_rows = [r for c in cases for r in doc_features(c)]
    feats = [f for f in all_rows[0][0] if f != "difficulty"]
    out = []
    for flag in (f.value for f in MatchFlag):
        rows = [r for r in all_rows if LEGAL_SCOPE.get(flag, lambda f: True)(r[0])]
        by_diff: dict[str, list[bool]] = defaultdict(list)
        for f, t in rows:
            by_diff[f["difficulty"]].append(t[flag])
        rate = {d: mean(ys) for d, ys in by_diff.items()}
        base = mean(t[flag] for _, t in rows)
        for feat in feats:
            groups: dict[str, list[tuple[bool, float]]] = defaultdict(list)
            for f, t in rows:
                groups[f[feat]].append((t[flag], rate[f["difficulty"]]))
            worst = (0.0, 0.0, "")
            for v, ys in groups.items():
                var = sum(p * (1 - p) for _, p in ys)
                if len(ys) < MIN_SUPPORT or var == 0:
                    continue
                dev = (sum(y for y, _ in ys) - sum(p for _, p in ys)) / len(ys)
                worst = max(worst, (abs(dev), abs(dev) * len(ys) / math.sqrt(var), v))
            out.append({"feature": feat, "flag": flag, "base": base, "max_dev": worst[0], "z": worst[1],
                        "value": worst[2], "spurious": worst[0] > MAX_DEV and worst[1] > MIN_Z})
    return out


# --------------------------------------------------------------------- report


def report(n: int, n_test: int, seed: int) -> dict:
    train = gen("train", n, seed)
    tests = {s: gen(s, n_test, seed + 1) for s in ("test_iid", "test_ood")}
    return {"base_rates": base_rates(train), "baselines": evaluate(train, tests), "spurious": spurious(train)}


def _print(rep: dict) -> None:
    br = rep["base_rates"]
    print("## (a) base rates on train (share of documents)\n")
    print("| key | " + " | ".join(br) + " |\n|---|" + "---|" * len(br))
    for k in next(iter(br.values())):
        print(f"| {k} | " + " | ".join(f"{br[d][k]:.3f}" if k != "docs" else str(br[d][k]) for d in br) + " |")
    print("\n## (b) baselines (true extraction and links given; decisions scored)\n")
    cols = (*METRICS, "line_acc", "ctx_line_acc")
    print("| split | baseline | " + " | ".join(cols) + " |\n|---|---|" + "---|" * len(cols))
    for (split, name), row in rep["baselines"].items():
        print(f"| {split} | {name} | " + " | ".join(f"{row[c]:.3f}" if c in row else "" for c in cols) + " |")
    bl = rep["baselines"]
    for split in ("test_iid", "test_ood"):
        lift = bl[(split, "keyword")]["ctx_line_acc"] - bl[(split, "no_anomaly")]["ctx_line_acc"]
        print(f"keyword lift over always-eligible on context-dependent lines, {split}: {lift:+.3f}")
    sp = sorted(rep["spurious"], key=lambda r: -r["max_dev"])
    print("\n## (c) largest feature -> flag deviations (train)\n")
    print("| feature | flag | base | max_dev | z | value | verdict |\n|---|---|---|---|---|---|---|")
    for r in sp[:15]:
        verdict = "SPURIOUS" if r["spurious"] else "ok"
        print(f"| {r['feature']} | {r['flag']} | {r['base']:.3f} | {r['max_dev']:.3f} | {r['z']:.1f} | "
              f"{r['value']} | {verdict} |")
    print(f"\nspurious pairs: {sum(r['spurious'] for r in sp)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.sim.audit")
    ap.add_argument("--n", type=int, default=2000, help="train cases")
    ap.add_argument("--n-test", type=int, default=300, help="cases per test split")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", help="also write the full report as JSON")
    args = ap.parse_args(argv)
    rep = report(args.n, args.n_test, args.seed)
    _print(rep)
    if args.json:
        rep["baselines"] = {f"{s}/{b}": v for (s, b), v in rep["baselines"].items()}
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=1)


if __name__ == "__main__":
    main()
