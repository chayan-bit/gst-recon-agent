"""Rupee rounding and tax split. All amounts are rounded half-up to 2 dp."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def r2(x: float | Decimal) -> float:
    return float(Decimal(str(x)).quantize(_CENT, rounding=ROUND_HALF_UP))


def split_tax(taxable: float, rate: float, intra_state: bool) -> tuple[float, float, float]:
    """(igst, cgst, sgst) for one line.

    s.9 CGST Act / s.5 IGST Act: intra-state supply (supplier state == place of
    supply, IGST Act s.8) attracts CGST + SGST at half the rate each; inter-state
    supply (IGST Act s.7) attracts IGST at the full rate.
    """
    tv = Decimal(str(taxable))
    if intra_state:
        half = r2(tv * Decimal(str(rate)) / 200)
        return 0.0, half, half
    return r2(tv * Decimal(str(rate)) / 100), 0.0, 0.0
