"""semireal builder on synthetic documents (no client data): grouping, exclusion, case-format round trip, oracle."""

from __future__ import annotations

import pytest

from gst_recon.eval.cases import load_cases
from gst_recon.hybrid.docschema import DocLine, DocRecord
from gst_recon.hybrid.inputs import parse_header, parse_prompt, split_sections
from gst_recon.schema import Party
from gst_recon.semireal.build import RealDoc, build_set, exclusion_reason, group_docs
from gst_recon.semireal.oracle import run_oracle
from gst_recon.sim.rules import extraction_of
from gst_recon.sim.world import generate_case


def _docs(seed: int, period: tuple[int, int], prefix: str) -> tuple[list[RealDoc], Party, object]:
    case = generate_case(seed, "medium", 0, periods=[period])
    docs = []
    for inv in case.inputs.invoices:
        ex = extraction_of(inv).model_dump(exclude={"doc_id", "line_items"})
        lines = [DocLine(description=li.description, hsn=li.hsn, taxable_value=li.taxable_value, rate=li.rate, igst=li.igst,
                         cgst=li.cgst, sgst=li.sgst, cess=li.cess, itc_category=li.category, purpose=li.purpose) for li in inv.line_items]
        text = (f"TAX INVOICE\n{inv.supplier_name}\nGSTIN: {inv.supplier_gstin}\nInvoice No: {inv.invoice_no}\n"
                f"Date: {inv.invoice_date:%d/%m/%Y}\nTotal: {inv.total:.2f}\n")
        docs.append(RealDoc(f"{prefix}{inv.doc_id}", DocRecord(**ex, line_items=lines), text, "scanned document, OCR text", "high"))
    return docs, case.inputs.buyer, case.inputs.buyer_profile


def _rec(docs: list[RealDoc], **upd) -> RealDoc:
    d = docs[0]
    return RealDoc(d.key, d.record.model_copy(update=upd), d.text, d.source, d.confidence)


def test_groups_by_invoice_month_and_splits_big_months():
    a, _, _ = _docs(1, (2025, 6), "a")
    many = [RealDoc(f"x{i:02d}", a[0].record, a[0].text, a[0].source) for i in range(30)]
    other = [RealDoc(f"y{i}", a[0].record.model_copy(update={"invoice_date": "2025-08-03"}), "t", "s") for i in range(3)]
    groups = group_docs(many + other, max_docs=25)
    assert [(k, len(g)) for k, g in groups] == [("202506-1", 15), ("202506-2", 15), ("202508", 3)]


def test_exclusion_keeps_unprinted_gstin_and_drops_unknown_identity():
    docs, _, _ = _docs(1, (2025, 6), "a")
    assert exclusion_reason(docs[0]) is None
    unreadable = _rec(docs, supplier_gstin="")
    assert "supplier_gstin" in exclusion_reason(unreadable)
    unregistered = RealDoc(unreadable.key, unreadable.record, unreadable.text, unreadable.source, absent=frozenset({"supplier_gstin"}))
    assert exclusion_reason(unregistered) is None
    g = docs[0].record.supplier_gstin
    assert "check digit" in exclusion_reason(_rec(docs, supplier_gstin=g[:14] + ("0" if g[14] != "0" else "1")))
    assert "invoice_no" in exclusion_reason(_rec(docs, invoice_no=" "))
    assert "unparseable" in exclusion_reason(_rec(docs, invoice_date="31-31-2025"))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    a, buyer, profile = _docs(5, (2025, 6), "a")
    b, _, _ = _docs(6, (2025, 7), "b")
    unreg = RealDoc("u1", b[0].record.model_copy(update={"supplier_gstin": "", "invoice_no": "U-77"}), "CASH BILL\nNo U-77\n",
                    "scanned document, OCR text", "medium", frozenset({"supplier_gstin"}))
    bad = RealDoc("z1", a[0].record.model_copy(update={"supplier_gstin": ""}), "illegible", "scanned document, OCR text")
    out = tmp_path_factory.mktemp("semireal")
    manifest = build_set(a + b + [unreg, bad], buyer, profile, out, seed=3, sim_seeds=(3, 4))
    return out, manifest, {d.key: d for d in a + b + [unreg]}


def test_manifest_counts_levels_and_exclusions(built):
    _, m, docs = built
    assert m["excluded"] == [{"source_key": "z1", "reason": m["excluded"][0]["reason"]}]
    assert m["levels"]["clean"]["n_cases"] == 2 and m["levels"]["clean"]["n_docs"] == len(docs)
    assert m["levels"]["sim"]["n_cases"] == 4 and m["levels"]["sim"]["n_docs"] == 2 * len(docs)
    assert set(m["levels"]["sim"]["per_seed"]) == {"3", "4"}
    ids = [c["case_id"] for c in m["levels"]["sim"]["cases"]]
    assert len(set(ids)) == 4 and all(i.startswith(("semireal-sim-s3-", "semireal-sim-s4-")) for i in ids)
    assert all(not c["planted"] for c in m["levels"]["clean"]["cases"])
    assert sum(len(c["planted"]) for c in m["levels"]["sim"]["cases"]) > 0
    assert any("unregistered_supplier_not_in_2b" in a for c in m["levels"]["clean"]["cases"] for a in c["anomalies"])


def test_cases_round_trip_through_load_cases_and_the_hybrid_parsers(built):
    out, _, docs = built
    for level in ("clean", "sim"):
        cases = load_cases([out / level], truth_dir=out / "truth")
        assert len(cases) == (2 if level == "clean" else 4)
        assert all(c.truth is not None and c.truth.case_id == c.case_id and c.split == f"semireal_{level}" for c in cases)
        for c in cases:
            h = parse_header(split_sections(c.prompt)["CASE"])
            assert (h.period, h.as_of) == (c.truth.inputs.period, c.truth.inputs.as_of_date)
            keys = {d["doc_id"]: d["source_key"] for d in c.meta["documents"]}
            assert [d.text for d in parse_prompt(c.prompt).docs] == [docs[keys[d.doc_id]].text.rstrip("\n") for d in parse_prompt(c.prompt).docs]
    clean = {c.case_id[len("semireal-clean-"):]: c for c in load_cases([out / "clean"], truth_dir=out / "truth")}
    sim = {c.case_id[len("semireal-sim-s3-"):]: c for c in load_cases([out / "sim"], truth_dir=out / "truth") if "-s3-" in c.case_id}
    for k, c in clean.items():  # the sim replica with the clean seed shares document order and reconciliation date
        assert c.meta["documents"] == sim[k].meta["documents"]
        assert c.truth.inputs.as_of_date == sim[k].truth.inputs.as_of_date


@pytest.mark.parametrize("level", ["clean", "sim"])
def test_oracle_true_records_reproduce_the_target(built, tmp_path, level):
    out, _, _ = built
    o = run_oracle(out / level, out / "truth", tmp_path / "oracle")
    assert o["n_errors"] == 0 and o["overall"]["itc_invoice"] == pytest.approx(1.0)
    assert {cid: c["misses"] for cid, c in o["cases"].items() if c["misses"]} == {}
    assert set(o["by_difficulty"]) == ({"clean"} if level == "clean" else {"sim-s3", "sim-s4"})
