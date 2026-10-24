"""Evaluation outputs are never training data.

Every eval run directory carries a DO_NOT_TRAIN marker. Training-data builders call
`refuse_eval_path(path)` on every input path; it raises for anything under `runs/eval/`
or under a directory holding the marker.
"""

from __future__ import annotations

from pathlib import Path

MARKER = "DO_NOT_TRAIN"
EVAL_ROOT = ("runs", "eval")


class EvalDataError(RuntimeError):
    """Raised when a training-data builder is pointed at evaluation output."""


def mark_eval_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / MARKER).write_text("Evaluation outputs. Never read these into training data.\n")


def is_eval_path(path: str | Path) -> bool:
    p = Path(path).expanduser().resolve()
    parts = p.parts
    if any(parts[i:i + 2] == EVAL_ROOT for i in range(len(parts) - 1)):
        return True
    return any((d / MARKER).exists() for d in (p, *p.parents))


def refuse_eval_path(path: str | Path) -> Path:
    """Return the path unchanged, or raise EvalDataError if it is evaluation output."""
    if is_eval_path(path):
        raise EvalDataError(f"{path} is evaluation output (runs/eval/ or marked {MARKER}); refusing to use it as training data")
    return Path(path)
