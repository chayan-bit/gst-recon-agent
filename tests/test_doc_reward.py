"""Per-document GRPO reward: weighted field match, abstention credit, schema gate."""

import json

from gst_recon.hybrid.sft import doc_sft_rows
from gst_recon.rewards.doc import INVENTED, VALID_FLOOR, doc_components, doc_reward, identity_score, parse_doc, visible
from gst_recon.train.perdoc import grpo_doc_row
from gst_recon.train.reward import doc_grpo_reward
from tests.hybrid.conftest import example


def _doc():
    row = grpo_doc_row(doc_sft_rows(*example("easy-21-00001"))[0])
    ref = json.loads(row["reference"])
    return ref["truth"], ref["doc_text"], row


def _out(rec: dict, **changes) -> str:
    return json.dumps({**rec, **changes})


def test_truth_scores_one_and_garbage_or_schema_invalid_scores_zero():
    truth, text, _ = _doc()
    assert doc_reward(_out(truth), truth, text) == 1.0
    assert doc_reward("```json\n" + _out(truth) + "\n```", truth, text) == 1.0
    assert doc_reward("not json", truth, text) == 0.0
    assert doc_reward(_out(truth, line_items="none"), truth, text) == 0.0
    assert doc_reward(_out(truth, extra_field=1), truth, text) == 0.0  # DocRecord forbids extra keys
    assert doc_reward(json.dumps({k: v for k, v in truth.items() if k != "total"}), truth, text) == 0.0


def test_reference_holds_the_document_block_only():
    truth, text, row = _doc()
    assert text.startswith(f"--- {row['doc_id']} |") and "=== CASE ===" not in text
    assert row["prompt"][1]["content"].endswith(text)
    assert visible("supplier_gstin", truth["supplier_gstin"], text)
    assert visible("invoice_no", truth["invoice_no"], text)
    assert visible("invoice_date", truth["invoice_date"], text)  # rendered as DD-MM-YYYY etc., truth is ISO


def test_visible_identity_must_be_read_correctly():
    truth, text, _ = _doc()
    for f in ("supplier_gstin", "invoice_no", "invoice_date"):
        assert identity_score(f, truth[f], truth[f], text) == 1.0
        assert identity_score(f, "", truth[f], text) == 0.0
    assert identity_score("supplier_gstin", "27AAAAA0000A1Z5", truth["supplier_gstin"], text) == 0.0


def test_unreadable_identity_rewards_abstaining_and_penalises_inventing():
    truth, text, _ = _doc()
    garbled = text.replace(truth["supplier_gstin"], "2?AB#C??0") .replace(truth["invoice_no"], "IN?/--")
    assert not visible("supplier_gstin", truth["supplier_gstin"], garbled)
    assert identity_score("supplier_gstin", "", truth["supplier_gstin"], garbled) == 1.0
    assert identity_score("supplier_gstin", truth["supplier_gstin"], truth["supplier_gstin"], garbled) == 1.0
    assert identity_score("supplier_gstin", "27AAAAA0000A1Z5", truth["supplier_gstin"], garbled) == INVENTED
    abstain = doc_reward(_out(truth, supplier_gstin="", invoice_no=""), truth, garbled)
    invent = doc_reward(_out(truth, supplier_gstin="27AAAAA0000A1Z5", invoice_no="INV-1"), truth, garbled)
    assert abstain == 1.0 and VALID_FLOOR <= invent < 0.75
    # on a clean page the same blanks cost credit but never fall below a wrong-format answer
    assert VALID_FLOOR < doc_reward(_out(truth, supplier_gstin="", invoice_no=""), truth, text) < 1.0


def test_lookalike_ocr_errors_still_count_as_shown():
    truth, text, _ = _doc()
    g = truth["supplier_gstin"]
    misread = text.replace(g, g.replace("0", "O").replace("1", "I"))
    assert misread != text and visible("supplier_gstin", g, misread)
    assert identity_score("supplier_gstin", "", g, misread) == 0.0  # readable: abstaining earns nothing
    assert visible("invoice_no", "SI000690", "Inv. No.: $1000690") and not visible("invoice_no", "TI/227", "No.: T#227")


def test_weights_order_identity_and_judgments_above_amounts():
    truth, text, _ = _doc()
    lines = truth["line_items"]
    other_cat = next(c for c in ("normal", "motor_vehicle", "food_beverage") if c != lines[0]["itc_category"])
    wrong_cat = [{**li, "itc_category": other_cat} for li in lines]
    wrong_amt = [{**li, "taxable_value": li["taxable_value"] + 100} for li in lines]
    r_cat = doc_reward(_out(truth, line_items=wrong_cat), truth, text)
    r_amt = doc_reward(_out(truth, line_items=wrong_amt), truth, text)
    r_name = doc_reward(_out(truth, supplier_name="Someone Else"), truth, text)
    assert r_cat < r_amt < r_name < 1.0
    comp = doc_components(parse_doc(_out(truth, line_items=lines[:-1] if len(lines) > 1 else [])), parse_doc(_out(truth)), text)
    assert comp["line_amounts"] < 1.0  # a missing line counts as a miss


def test_plugin_reads_the_reference_and_is_total():
    truth, text, row = _doc()
    assert doc_grpo_reward(_out(truth), row["reference"]) == 1.0
    assert doc_grpo_reward(_out(truth), None) == 0.0
    assert doc_grpo_reward(_out(truth), '{"truth": {}}') == 0.0
    assert doc_grpo_reward(_out(truth), "not json") == 0.0
