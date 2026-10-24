import csv
import io
import json
import random

from gst_recon.render.tables import render_bank, render_gstr2b, render_register
from gst_recon.schema import Gstr2b


def test_register_csv_is_well_formed_and_complete(case):
    rows = case.inputs.purchase_register
    for seed in range(12):  # all style variants: csv, text, header sets
        text, meta = render_register(rows, case.inputs.period, case.inputs.buyer.name, random.Random(seed))
        for r in rows:
            assert r.voucher_no in text and r.party_gstin in text
        if meta["style"] == "csv":
            parsed = list(csv.reader(io.StringIO(text)))
            assert len(parsed) == len(rows) + 1
            assert len({len(p) for p in parsed}) == 1


def test_register_keeps_simulated_data_entry_errors(case):
    text, _ = render_register(case.inputs.purchase_register, case.inputs.period, "B", random.Random(1))
    for r in case.inputs.purchase_register:
        assert r.supplier_invoice_no in text  # typo'd numbers are shown as booked


def test_gstr2b_json_round_trips_through_schema(case):
    out = render_gstr2b(case.inputs.gstr2b)
    assert len(out) == len(case.inputs.gstr2b)
    for (period, js), g in zip(out, case.inputs.gstr2b):
        assert period == g.data.rtnprd
        assert Gstr2b.model_validate(json.loads(js)) == g


def test_bank_csv_is_well_formed_and_keeps_refs(case):
    txns = case.inputs.bank_statement
    for seed in range(8):
        text, meta = render_bank(txns, random.Random(seed))
        parsed = list(csv.reader(io.StringIO(text)))
        assert len(parsed) == len(txns) + 1
        assert len({len(p) for p in parsed}) == 1
        for t in txns:
            assert t.ref_no in text
        total_debit = sum(t.debit for t in txns)
        idx = next(i for i, h in enumerate(parsed[0]) if h.startswith(("Withdrawal Amt", "Withdrawal Amount", "Debit")))
        assert abs(sum(float(r[idx]) for r in parsed[1:] if r[idx]) - total_debit) < 0.01
