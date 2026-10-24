"""Per-document curation: the case-level OCR rule applied to each document on its own."""

import json

from gst_recon.hybrid.sft import doc_sft_rows
from gst_recon.train.perdoc import curate_doc_rows
from tests.hybrid.conftest import example


def test_lost_hsn_is_blanked_and_other_losses_drop_only_that_document():
    rows = doc_sft_rows(*example("easy-21-00001"))
    first, second = rows[0]["doc_id"], rows[1]["doc_id"]
    kept, dropped, masked = curate_doc_rows(rows, (f"{first}:line0_hsn", f"{second}:invoice_no"))
    assert (dropped, masked) == (1, 1) and [r["doc_id"] for r in kept] == [first, *(r["doc_id"] for r in rows[2:])]
    rec = json.loads(kept[0]["messages"][-1]["content"])
    assert rec["line_items"][0]["hsn"] == "" and json.loads(rows[0]["messages"][-1]["content"])["line_items"][0]["hsn"]
    assert kept[0]["messages"][:2] == rows[0]["messages"][:2]  # prompt untouched; input rows not mutated
    assert curate_doc_rows(rows, ()) == (rows, 0, 0)


def test_hard_grpo_rows_are_medium_or_hard_with_a_hidden_identity_or_several_lines():
    from gst_recon.train.perdoc import is_hard_grpo_row

    def row(difficulty, gstin_on_page, lines):
        truth = {"supplier_gstin": "07ABCDE1234F1Z5", "invoice_no": "INV-9", "invoice_date": "",
                 "line_items": [{}] * lines}
        page = f"INV-9 {'07ABCDE1234F1Z5' if gstin_on_page else 'GSTIN: ##########'}"
        return {"difficulty": difficulty, "reference": json.dumps({"truth": truth, "doc_text": page})}

    assert is_hard_grpo_row(row("hard", False, 1)) and is_hard_grpo_row(row("medium", True, 2))
    assert not is_hard_grpo_row(row("hard", True, 1))  # everything visible, one line
    assert not is_hard_grpo_row(row("easy", False, 3))  # easy cases stay out
