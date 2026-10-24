import json

import pytest

from gst_recon.schema import Case, DocType
from gst_recon.sim.__main__ import main
from gst_recon.sim.gstin import is_valid_gstin
from gst_recon.sim.world import generate_case

HEADS = ("igst", "cgst", "sgst", "cess")


def test_same_seed_same_case():
    assert generate_case(3, "hard", 5).model_dump_json() == generate_case(3, "hard", 5).model_dump_json()


def test_different_index_or_seed_differs():
    base = generate_case(3, "medium", 0).model_dump_json()
    assert base != generate_case(3, "medium", 1).model_dump_json()
    assert base != generate_case(4, "medium", 0).model_dump_json()


@pytest.mark.parametrize("difficulty,lo,hi", [("easy", 5, 12), ("medium", 10, 25), ("hard", 20, 40)])
def test_invoice_count_in_range(difficulty, lo, hi):
    for i in range(10):
        c = generate_case(0, difficulty, i)
        n = sum(1 for inv in c.inputs.invoices if inv.doc_type == DocType.INVOICE)
        assert lo <= n <= hi


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_cases_are_internally_consistent(difficulty):
    for i in range(15):
        c = Case.model_validate_json(generate_case(11, difficulty, i).model_dump_json())
        assert is_valid_gstin(c.inputs.buyer.gstin)
        invs = {inv.doc_id: inv for inv in c.inputs.invoices}
        assert [m.doc_id for m in c.expected.matches] == list(invs)
        for inv in invs.values():
            assert is_valid_gstin(inv.supplier_gstin)
            intra = inv.supplier_gstin[:2] == inv.place_of_supply
            for li in inv.line_items:
                assert (li.igst == 0) == intra or li.rate == 0
        for d in c.expected.itc:  # every rupee of tax lands in exactly one bucket
            inv = invs[d.doc_id]
            sign = -1 if inv.doc_type == DocType.CREDIT_NOTE else 1
            for h in HEADS:
                total = getattr(d.eligible, h) + getattr(d.blocked, h) + getattr(d.deferred, h)
                assert abs(total - sign * getattr(inv, h)) < 0.011
        vouchers = {r.voucher_no for r in c.inputs.purchase_register}
        refs = {t.ref_no for t in c.inputs.bank_statement}
        for m in c.expected.matches:
            assert set(m.register_vouchers) <= vouchers and set(m.payment_refs) <= refs
        assert all(t.txn_date <= c.inputs.as_of_date for t in c.inputs.bank_statement)


def test_hard_cases_exercise_every_flag_and_reason():
    flags, reasons = set(), set()
    for i in range(40):
        c = generate_case(1, "hard", i)
        flags |= {f for m in c.expected.matches for f in m.flags}
        reasons |= {r for d in c.expected.itc for r in d.reasons}
    from gst_recon.schema import MatchFlag, ReasonCode
    assert flags == set(MatchFlag)
    assert reasons == set(ReasonCode)


def test_easy_cases_have_no_180_day_cases():
    for i in range(20):
        c = generate_case(2, "easy", i)
        assert all("unpaid_180d" not in m.flags for m in c.expected.matches)


def test_cli_writes_one_file_per_case(tmp_path):
    main(["generate", "--n-cases", "3", "--seed", "9", "--difficulty", "medium", "--out", str(tmp_path)])
    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 3
    Case.model_validate(json.loads(files[0].read_text()))


def test_train_size_profiles_shrink_cases_and_keep_eval_sizes():
    from gst_recon.sim.world import DIFFICULTY, TRAIN_SIZES

    for size, ranges in TRAIN_SIZES.items():
        for d, (lo, hi) in ranges.items():
            c = generate_case(3, d, 0, size=size)
            invoices = [i for i in c.inputs.invoices if i.doc_type.value == "invoice"]
            assert lo <= len(invoices) <= hi and c.case_id.startswith(f"{size}-{d}-") and c.split == "train"
            assert hi < DIFFICULTY[d].n_invoices[1]
    assert generate_case(3, "hard", 0, size="sft").case_id != generate_case(3, "hard", 0).case_id
    with pytest.raises(ValueError):
        generate_case(3, "hard", 0, split="test_ood", size="grpo")


def _cn_collisions(case) -> list[tuple[str, str]]:
    from collections import Counter

    from gst_recon.schema import DocType

    keys = Counter((i.supplier_gstin, i.invoice_no) for i in case.inputs.invoices if i.doc_type == DocType.CREDIT_NOTE)
    return [k for k, n in keys.items() if n > 1]


def test_credit_note_numbers_are_unique_per_supplier():
    """GSTR-2B keys documents by (period, ctin, number): a reused CN number would overwrite the first note."""
    from gst_recon.sim.world import generate_case

    assert not _cn_collisions(generate_case(9001, "medium", 14, split="test_iid"))  # the reported case
    for i in range(150):
        assert not _cn_collisions(generate_case(77, "hard", i)), i
