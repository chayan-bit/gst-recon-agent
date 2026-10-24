"""Disjoint train / test_iid / test_ood: nothing textual leaks into train."""

import pytest

from gst_recon.schema import BusinessProfile as P
from gst_recon.sim import catalog as cat
from gst_recon.sim import lexicon as lex
from gst_recon.sim.__main__ import main
from gst_recon.sim.concepts import CONCEPTS, FAMILIES
from gst_recon.sim.splits import (
    OOD_PROFILES, SPLITS, View, all_forms, concept_forms, ood_concepts, surface_forms, text_pool,
)
from gst_recon.sim.world import generate_case


def test_every_concept_has_at_least_25_surface_forms():
    for c in CONCEPTS:
        assert len({f.casefold() for f in all_forms(c)}) >= 25, c.id


def test_no_description_states_its_use():
    banned = ("staff use", "director", "residence", "gift", "personal", "canteen", "party")
    for c in CONCEPTS:
        for core in c.forms:
            assert not any(b in core.lower() for b in banned), (c.id, core)


def test_pool_level_disjointness():
    train = {f.casefold() for c in CONCEPTS for f in concept_forms(c, "train")}
    for split in ("test_iid", "test_ood"):
        held = {f.casefold() for c in CONCEPTS for f in concept_forms(c, split)}
        assert held and not (train & held), split
    for c in CONCEPTS:
        if c.id in ood_concepts():
            assert not concept_forms(c, "train") and not concept_forms(c, "test_iid")
        else:
            assert concept_forms(c, "train") and concept_forms(c, "test_iid")
    for key, pool in [*((f"remark:{u.value}", p) for u, p in lex.REMARKS.items()),
                      *((f"header:{k.value}", p) for k, p in lex.PROFILE_HEADERS.items())]:
        assert not set(text_pool(pool, key, "train")) & set(text_pool(pool, key, "test_iid")), key


def test_every_family_keeps_a_training_concept_and_some_are_held_out():
    for fam in FAMILIES:
        assert View("train").concepts(fam), fam
    assert len(ood_concepts()) >= 15


def test_ood_vocab_states_profiles_are_disjoint_from_train():
    tr, ood = View("train"), View("test_ood")
    assert not set(tr.states) & set(ood.states)
    assert not set(tr.name_prefix) & set(ood.name_prefix)
    assert not set(tr.name_core) & set(ood.name_core)
    assert not set(tr.number_formats) & set(ood.number_formats)
    assert not set(tr.profiles(False)) & set(OOD_PROFILES)


@pytest.fixture(scope="module")
def generated():
    out = {}
    for split in SPLITS:
        out[split] = [generate_case(5, d, i, split=split) for d in ("easy", "medium", "hard") for i in range(40)]
    return out


def _descriptions(cases):
    return {li.description.casefold() for c in cases for inv in c.inputs.invoices for li in inv.line_items}


def test_no_surface_form_or_ood_item_leaks_into_train(generated):
    train = generated["train"]
    train_desc = _descriptions(train)
    for split in ("test_iid", "test_ood"):
        assert not train_desc & _descriptions(generated[split]), split
    train_concepts = {li.concept for c in train for inv in c.inputs.invoices for li in inv.line_items}
    assert not train_concepts & ood_concepts()
    assert not {c.inputs.buyer_profile.profile for c in train} & set(OOD_PROFILES)
    ood_states = set(View("test_ood").states)
    assert not {inv.supplier_gstin[:2] for c in train for inv in c.inputs.invoices} & ood_states
    assert not {c.inputs.buyer.state_code for c in train} & ood_states
    ood_tokens = set(View("test_ood").name_prefix) | set(View("test_ood").name_core)
    for c in train:
        for inv in c.inputs.invoices:
            assert not any(t in inv.supplier_name for t in ood_tokens if len(t) > 3), inv.supplier_name
    train_remarks = {inv.remarks for c in train for inv in c.inputs.invoices} - {""}
    test_remarks = {inv.remarks for c in generated["test_iid"] + generated["test_ood"] for inv in c.inputs.invoices}
    assert not train_remarks & test_remarks
    train_headers = {c.inputs.buyer_profile.description.split(". Employees")[0] for c in train}
    test_headers = {c.inputs.buyer_profile.description.split(". Employees")[0]
                    for c in generated["test_iid"] + generated["test_ood"]}
    assert not train_headers & test_headers


def test_test_ood_actually_exercises_held_out_items(generated):
    ood = generated["test_ood"]
    concepts = {li.concept for c in ood for inv in c.inputs.invoices for li in inv.line_items}
    assert len(concepts & ood_concepts()) >= 10
    assert {c.inputs.buyer_profile.profile for c in ood} & set(OOD_PROFILES)


def test_iid_uses_training_concepts_and_profiles(generated):
    iid = generated["test_iid"]
    concepts = {li.concept for c in iid for inv in c.inputs.invoices for li in inv.line_items}
    assert not concepts & ood_concepts()
    assert not {c.inputs.buyer_profile.profile for c in iid} & set(OOD_PROFILES)


def test_cli_split_flag(tmp_path):
    from gst_recon.schema import Case
    main(["generate", "--n-cases", "2", "--seed", "3", "--split", "test_ood", "--out", str(tmp_path)])
    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 2 and all(Case.model_validate_json(f.read_text()).split == "test_ood" for f in files)
