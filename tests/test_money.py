from gst_recon.sim.money import r2, split_tax


def test_round_half_up():
    assert r2(0.125) == 0.13
    assert r2(2.675) == 2.68  # float would round this down
    assert r2(-0.125) == -0.13


def test_intra_state_splits_cgst_sgst():
    assert split_tax(1000, 18, intra_state=True) == (0.0, 90.0, 90.0)


def test_inter_state_is_igst():
    assert split_tax(1000, 18, intra_state=False) == (180.0, 0.0, 0.0)


def test_half_rate_rounding_per_head():
    # 333.33 x 5% / 2 = 8.33325 -> 8.33 each head
    assert split_tax(333.33, 5, True) == (0.0, 8.33, 8.33)


def test_nil_rate():
    assert split_tax(500, 0, True) == (0.0, 0.0, 0.0)
