"""Buyer business profile, what it buys, and why (the line purpose).

The purpose decides the s.17(5) outcome together with the concept's category
(rules.line_block_reason). The generator only produces purposes the model can
see: either implied by the profile header (a car dealer buying cars) or stated
in the invoice remarks (a factory canteen, a staff party, a gift, a director's
residence, own building construction). Every other line is ordinary business use.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from gst_recon.schema import BusinessProfile as P
from gst_recon.schema import BuyerProfile
from gst_recon.schema import LinePurpose as U
from gst_recon.sim import lexicon as lex
from gst_recon.sim.concepts import Concept
from gst_recon.sim.splits import P_OOD_PROFILE, View

OPTIONAL_REMARK = {U.FURTHER_SUPPLY, U.PASSENGER_TRANSPORT, U.DRIVING_TRAINING}
P_OPTIONAL_REMARK = 0.3
P_NEUTRAL_REMARK = 0.3
_MV_PURPOSE = {P.CAR_DEALER: U.FURTHER_SUPPLY, P.PASSENGER_TRANSPORT: U.PASSENGER_TRANSPORT,
               P.DRIVING_SCHOOL: U.DRIVING_TRAINING}


@dataclass(frozen=True)
class BuyerContext:
    profile: BuyerProfile
    trade_line: str | None  # trading companies only
    family_weights: dict[str, float]

    @property
    def kind(self) -> P:
        return self.profile.profile

    @property
    def resale_families(self) -> tuple[str, ...]:
        return lex.TRADE_LINES[self.trade_line][0] if self.trade_line else ()


def make_buyer_context(rng: random.Random, view: View) -> BuyerContext:
    held_out = rng.random() < P_OOD_PROFILE
    kind = rng.choice(view.profiles(held_out))
    trade_line = None
    weights = dict(lex.PROFILE_FAMILIES[kind])
    if kind == P.TRADING_COMPANY:
        trade_line = rng.choice(sorted(lex.TRADE_LINES))
        header = rng.choice(view.trade_headers(trade_line))
        for fam in lex.TRADE_LINES[trade_line][0]:
            weights[fam] = weights.get(fam, 0) + lex.TRADE_LINE_BOOST
    else:
        header = rng.choice(view.headers(kind))
        if "{x}" in header:
            header = header.format(x=rng.choice(view.slots(kind)))
    employees = rng.randint(40, 900) if kind == P.MANUFACTURER else rng.randint(6, 300)
    profile = BuyerProfile(profile=kind, description=f"{header}. Employees: {employees}.", employees=employees)
    return BuyerContext(profile, trade_line, weights)


def choose_purpose(rng: random.Random, family: str, concept: Concept, ctx: BuyerContext) -> U:
    """Why this buyer buys from this family (one purpose per invoice)."""
    kind, r = ctx.kind, rng.random()
    if family in ctx.resale_families and not concept.is_service:
        return U.FURTHER_SUPPLY
    if family == "motor_vehicle":
        return _MV_PURPOSE.get(kind, U.BUSINESS)
    if family == "food":
        if kind in (P.HOTEL, P.CATERER):
            return U.FURTHER_SUPPLY  # same-category outward supply / element of composite supply
        if kind == P.MANUFACTURER and r < 0.4:
            return U.FACTORY_CANTEEN
        return U.STAFF_WELFARE if r < (0.6 if kind == P.MANUFACTURER else 0.3) else U.BUSINESS
    if family == "club":
        return U.STAFF_WELFARE if r < 0.3 else U.BUSINESS
    if family == "works_contract":
        return U.FURTHER_SUPPLY if kind == P.CONSTRUCTION_CONTRACTOR else U.BUSINESS
    if family == "construction":
        return U.BUSINESS if kind == P.CONSTRUCTION_CONTRACTOR else U.OWN_CONSTRUCTION
    if family == "household":
        return U.BUSINESS if kind == P.HOTEL or r >= 0.5 else U.PERSONAL
    if family == "giftable":
        return U.GIFT
    if family == "office":
        return U.PERSONAL if r < 0.08 else U.GIFT if r < 0.12 else U.BUSINESS
    return U.BUSINESS


def remark_for(rng: random.Random, purpose: U, view: View) -> str:
    """Remarks text. Purpose-revealing when needed; otherwise often a neutral
    remark, so the mere presence of a remark predicts nothing."""
    r = rng.random()
    if purpose in lex.REMARK_REQUIRED:
        return rng.choice(view.remarks(purpose))
    if purpose in OPTIONAL_REMARK and r < P_OPTIONAL_REMARK:
        return rng.choice(view.remarks(purpose))
    return rng.choice(view.neutral_remarks) if rng.random() < P_NEUTRAL_REMARK else ""
