from gst_recon.sim.world import generate_case
from gst_recon.train import paraphrase as para
from tests.train.conftest import EMAIL, prompt_for


def test_blocks_and_apply_only_touch_text_documents():
    prompt = prompt_for(generate_case(1, "easy", 3))
    found = para.blocks(prompt)
    assert [(d, s) for d, s, _ in found] == [("D01", "email body")]
    assert found[0][2].strip() == EMAIL.strip()
    out = para.apply(prompt, {"D01": "  Hello, new voice.  "})
    assert "--- D01 | email body ---\nHello, new voice.\n\n\n--- D02 |" in out  # original spacing kept
    assert out.replace("Hello, new voice.", EMAIL.strip()) == prompt


def test_missing_facts_catches_numbers_remarks_and_names():
    extraction = {"supplier_name": "ACME TRADERS", "line_items": [{"description": "steel coil"}]}
    assert para.missing_facts(EMAIL, EMAIL, extraction) == []
    assert "236.00" in para.facts(EMAIL) and "for workers' canteen" in para.facts(EMAIL)
    bad = EMAIL.replace("236.00", "263.00").replace("for workers' canteen", "for the office").replace("steel coil", "coil")
    assert para.missing_facts(EMAIL, bad, extraction) == ["236.00", "for workers' canteen", "steel coil"]
