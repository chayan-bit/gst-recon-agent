"""CLI: python -m gst_recon.sim generate --n-cases N --seed S --difficulty medium --out data/truth/"""

from __future__ import annotations

import argparse
from pathlib import Path

from gst_recon.sim.world import DIFFICULTY, generate_case


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.sim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write one ground-truth JSON per case")
    g.add_argument("--n-cases", type=int, required=True)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--difficulty", choices=sorted(DIFFICULTY), default="medium")
    g.add_argument("--out", type=Path, default=Path("data/truth"))
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    for i in range(args.n_cases):
        case = generate_case(args.seed, args.difficulty, i)
        (args.out / f"{case.case_id}.json").write_text(case.model_dump_json(indent=1))
    print(f"wrote {args.n_cases} {args.difficulty} cases to {args.out}")


if __name__ == "__main__":
    main()
