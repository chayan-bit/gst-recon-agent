"""CLI: python -m gst_recon.sim generate --n-cases N --seed S --difficulty medium --out data/truth/
        [--period-from 2024-04 --period-to 2026-09]"""

from __future__ import annotations

import argparse
from pathlib import Path

from gst_recon.sim.world import DEFAULT_PERIODS, DIFFICULTY, generate_case, period_range


def _ym(text: str) -> tuple[int, int]:
    try:
        y, m = (int(x) for x in text.split("-"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM, got {text!r}") from None
    if not 1 <= m <= 12:
        raise argparse.ArgumentTypeError(f"bad month in {text!r}")
    return y, m


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.sim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write one ground-truth JSON per case")
    g.add_argument("--n-cases", type=int, required=True)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--difficulty", choices=sorted(DIFFICULTY), default="medium")
    g.add_argument("--out", type=Path, default=Path("data/truth"))
    g.add_argument("--period-from", type=_ym, default=DEFAULT_PERIODS[0], help="first return period, YYYY-MM")
    g.add_argument("--period-to", type=_ym, default=DEFAULT_PERIODS[-1], help="last return period, YYYY-MM")
    args = ap.parse_args(argv)
    try:
        periods = period_range(args.period_from, args.period_to)
    except ValueError as e:
        ap.error(str(e))

    args.out.mkdir(parents=True, exist_ok=True)
    for i in range(args.n_cases):
        case = generate_case(args.seed, args.difficulty, i, periods)
        (args.out / f"{case.case_id}.json").write_text(case.model_dump_json(indent=1))
    print(f"wrote {args.n_cases} {args.difficulty} cases to {args.out}")


if __name__ == "__main__":
    main()
