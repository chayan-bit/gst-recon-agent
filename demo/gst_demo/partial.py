"""Best-effort parse of a JSON document that is still being generated."""

from __future__ import annotations

import json


def parse_partial(text: str) -> dict | None:
    """Dict for the longest valid prefix of `text` (open brackets closed, a dangling key or value cut), else None."""
    stack: list[str] = []
    snaps: list[tuple[int, str]] = []  # (cut position, closers) after each opener and comma: a valid cut
    in_str = esc = False
    for i, ch in enumerate(text):
        if in_str:
            esc = (not esc) and ch == "\\"
            in_str = esc or ch != '"'
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
            snaps.append((i + 1, "".join(reversed(stack))))
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == "," and stack:
            snaps.append((i, "".join(reversed(stack))))
    tail = text.rstrip().removesuffix("\\") + ('"' if in_str else "")
    candidates = [tail + "".join(reversed(stack)), *(text[:cut] + closers for cut, closers in reversed(snaps))]
    for cand in candidates[:1] + candidates[1:8]:
        try:
            obj = json.loads(cand)
        except ValueError:
            continue
        return obj if isinstance(obj, dict) else None
    return None
