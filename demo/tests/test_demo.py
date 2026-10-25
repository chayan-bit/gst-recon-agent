import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gst_demo import app as app_mod
from gst_demo.cases import split_prompt
from gst_demo.partial import parse_partial
from gst_demo.view import build_view

EX = Path(__file__).resolve().parents[2] / "examples"
CASE = EX / "easy-21-00001"
TARGET = json.loads((CASE / "target.json").read_text())


def test_partial_closes_open_brackets_and_cuts_dangling_key():
    assert parse_partial('{"a":[{"x":1},{"x":2') == {"a": [{"x": 1}, {"x": 2}]}
    assert parse_partial('{"a":[1,2],"bb') == {"a": [1, 2]}
    assert parse_partial('{"a":"hel') == {"a": "hel"}
    assert parse_partial("") is None


def test_every_prefix_of_a_real_output_parses_to_a_prefix_of_the_rows():
    text = json.dumps(TARGET)
    seen = 0
    for n in range(0, len(text), 97):
        out = parse_partial(text[:n])
        rows = (out or {}).get("extractions", [])
        assert len(rows) >= seen
        seen = len(rows)


def test_truth_as_output_has_no_wrong_cells_and_matching_headline():
    v = build_view(json.dumps(TARGET), TARGET, final=True)
    assert v["diff"]["wrong_cells"] == 0 and v["diff"]["exact"] == v["diff"]["judged"] == len(TARGET["itc"])
    assert v["headline"] == v["truth_headline"] and v["validity"]["schema"] is True


def test_changed_blocked_amount_marks_only_that_cell():
    bad = json.loads(json.dumps(TARGET))
    row = bad["itc"][0]
    row["eligible"] = {"igst": 1.0}
    v = build_view(json.dumps(bad), TARGET, final=True)
    wrong = {r["doc_id"]: r["wrong"] for r in v["rows"] if r["wrong"]}
    assert set(wrong[row["doc_id"]]) >= {"eligible"} and v["diff"]["exact"] == len(TARGET["itc"]) - 1


def test_streaming_view_hides_unfinished_record():
    text = json.dumps(TARGET)
    cut = text.index('"itc"') + 40  # inside the first itc record
    v = build_view(text[:cut], TARGET, final=False)
    assert v["rows"] and not v["rows"][0]["ready"]["itc"] and v["rows"][0]["ready"]["match"]


def test_prompt_split_finds_every_document():
    parts = split_prompt((CASE / "prompt.txt").read_text())
    assert [d["id"] for d in parts["docs"]] == [f"D0{i}" for i in range(1, 7)]
    assert "Buyer" in parts["header"] and "PURCHASE REGISTER (Tally csv export)" in parts["sections"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "RECORDINGS", tmp_path)
    monkeypatch.setattr(app_mod, "BASE_URL", "http://127.0.0.1:9/v1")  # nothing listens: replay path only
    return TestClient(app_mod.app)


def test_replay_streams_recording_and_view_matches(client, tmp_path):
    text = json.dumps(TARGET)
    chunks = [[i, text[i:i + 50]] for i in range(0, len(text), 50)]
    (tmp_path / "r.json").write_text(json.dumps({"case_id": CASE.name, "model": "base:sft", "constrained": True, "recorded_at": "x",
                                                 "stats": {"completion_tokens": len(chunks)}, "chunks": chunks}))
    r = client.post("/api/run", json={"case_id": CASE.name, "model": "base", "constrained": False, "mode": "replay", "speed": 1000})
    ev = [json.loads(ln) for ln in r.text.splitlines()]
    assert ev[0]["mode"] == "replay" and ev[0]["model"] == "base:sft" and ev[-1]["type"] == "done"
    assert "".join(e["t"] for e in ev if e["type"] == "tok") == text
    assert client.get("/api/health").json()["live"] is False
    assert client.post("/api/run", json={"case_id": CASE.name, "mode": "replay"}).status_code == 200


def test_adapter_models_get_the_compact_grammar_and_base_the_strict_one():
    from gst_demo.stream import request_body
    from gst_recon.rewards import compact

    def n_required(model):
        return json.dumps(request_body("p", model, True, 10)["response_format"]).count('"required"')

    assert n_required("base:sft") < n_required("base")
    # a compact output (zero fields omitted) still renders and validates after expansion
    v = build_view(json.dumps(compact(TARGET)), TARGET, final=True)
    assert v["validity"]["schema"] is True and v["diff"]["wrong_cells"] == 0


def test_per_document_request_carries_the_invoice_number_cap():
    from gst_demo.hybrid import doc_request
    from gst_recon.hybrid.docschema import INVOICE_NO_MAX

    props = doc_request("h", "b", "base:perdoc", True)["response_format"]["json_schema"]["schema"]["properties"]
    assert INVOICE_NO_MAX == 16
    assert props["invoice_no"]["maxLength"] == props["original_invoice_no"]["maxLength"] == INVOICE_NO_MAX


def test_results_page_and_its_numbers_are_served():
    c = TestClient(app_mod.app)
    assert c.get("/results").status_code == 200
    assert c.get("/built").status_code == 200
    d = c.get("/static/results.json").json()
    ours = [r for r in d["readers"] if r.get("ours")]
    assert len(d["readers"]) == 4 and len(ours) == 1 and ours[0]["itc"] == 61.1  # the README Results table, real documents only
    assert all(0 <= r[k] <= 100 for r in d["readers"] for k in ("itc", "match", "composite", "invented"))


def test_shipped_and_earlier_per_document_adapters_have_their_labels():
    assert app_mod._model_entry("base:perdoc-grpo")["label"] == "Per-document SFT + GRPO (shipped)"
    assert app_mod._model_entry("base:perdoc")["label"] == "Per-document SFT"
