import json

from gst_recon.schema import SCHEMA_PATH, ReconOutput, output_json_schema

ALLOWED_KEYS = {
    "type", "properties", "required", "items", "enum", "description", "additionalProperties",
}


def _walk(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if path.endswith(".properties"):
                yield from _walk(v, f"{path}.{k}")  # k is a field name, not a keyword
                continue
            assert k in ALLOWED_KEYS, f"unsupported keyword {k!r} at {path}"
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    yield node


def test_output_schema_uses_only_grammar_friendly_keywords():
    list(_walk(output_json_schema()))


def test_exported_schema_file_is_current():
    assert json.loads(SCHEMA_PATH.read_text()) == output_json_schema()


def test_every_object_is_closed_and_fully_required():
    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                check(v)
        elif isinstance(node, list):
            for v in node:
                check(v)
    check(output_json_schema())


def test_minimal_output_round_trips():
    zero = {"igst": 0, "cgst": 0, "sgst": 0, "cess": 0}
    out = ReconOutput.model_validate(
        {"extractions": [], "matches": [], "itc": [],
         "itc_totals": {"eligible": zero, "blocked": zero, "deferred": zero}}
    )
    assert ReconOutput.model_validate_json(out.model_dump_json()) == out
