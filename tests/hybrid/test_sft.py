"""Per-document SFT rows: one row per document, the same prompt the eval sends, record + judgments as target."""

from __future__ import annotations

import json

from gst_recon.eval.prompts import DOC_SYSTEM_PROMPT
from gst_recon.hybrid.docschema import DocRecord, doc_json_schema
from gst_recon.hybrid.inputs import parse_prompt
from gst_recon.hybrid.sft import doc_sft_rows


def test_one_row_per_document_with_truth_judgments(ex):
    prompt, target, case = ex
    rows = doc_sft_rows(prompt, target, case)
    parts = parse_prompt(prompt)
    assert [r["doc_id"] for r in rows] == [d.doc_id for d in parts.docs]
    truth = {i.doc_id: i for i in case.inputs.invoices}
    for r, d in zip(rows, parts.docs):
        sys_msg, user, asst = r["messages"]
        assert sys_msg == {"role": "system", "content": DOC_SYSTEM_PROMPT}
        assert user["content"].startswith(parts.header.text) and d.block in user["content"]
        assert prompt.count(d.block) == 1  # the document text is verbatim from prompt.txt
        rec = DocRecord.model_validate_json(asst["content"])
        assert [(li.itc_category, li.purpose) for li in rec.line_items] == [
            (li.category, li.purpose) for li in truth[d.doc_id].line_items]
        assert rec.invoice_no == truth[d.doc_id].invoice_no


def test_doc_schema_is_flat_and_fully_required():
    s = doc_json_schema()
    text = json.dumps(s)
    assert "$ref" not in text and "$defs" not in text
    assert set(s["required"]) == set(s["properties"])
    line = s["properties"]["line_items"]["items"]
    assert set(line["required"]) == set(line["properties"])
    assert "gift" not in line["properties"]["itc_category"]["enum"]
