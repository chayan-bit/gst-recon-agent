"""Case directories: <case_id>/{prompt.txt, meta.json, target.json?, images/D05.png?}."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DOC_RE = re.compile(r"^--- (D\d+) \| (.*?) ---\s*$", re.M)
SECTION_RE = re.compile(r"^=== (.*?) ===\s*$", re.M)
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    path: Path

    @property
    def prompt(self) -> str:
        return (self.path / "prompt.txt").read_text()

    @property
    def meta(self) -> dict:
        p = self.path / "meta.json"
        return json.loads(p.read_text()) if p.exists() else {}

    @property
    def target(self) -> dict | None:
        p = self.path / "target.json"
        return json.loads(p.read_text()) if p.exists() else None

    @property
    def images(self) -> dict[str, Path]:
        d = self.path / "images"
        return {p.stem.upper(): p for p in sorted(d.iterdir()) if p.suffix.lower() in IMG_EXT} if d.is_dir() else {}


def split_prompt(prompt: str) -> dict:
    """prompt.txt -> {header: {Buyer: ...}, docs: [{id, kind, text}], sections: {title: text}}."""
    marks = list(SECTION_RE.finditer(prompt))
    body = {m.group(1): prompt[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(prompt)].strip("\n")
            for i, m in enumerate(marks)}
    header = {k.strip(): v.strip() for k, _, v in (ln.partition(":") for ln in body.get("CASE", "").splitlines()) if v}
    inv = body.get("INVOICES", "")
    hits = list(DOC_RE.finditer(inv))
    docs = [{"id": m.group(1), "kind": m.group(2),
             "text": inv[m.end(): hits[i + 1].start() if i + 1 < len(hits) else len(inv)].strip("\n")}
            for i, m in enumerate(hits)]
    sections = {k: v for k, v in body.items() if k not in ("CASE", "INVOICES", "END")}
    return {"header": header, "docs": docs, "sections": sections}


def find_cases(root: Path) -> list[DemoCase]:
    """`root` is a case directory itself, or a directory of case directories."""
    root = root.expanduser().resolve()
    if (root / "prompt.txt").is_file():
        return [DemoCase(root.name, root)]
    return [DemoCase(p.parent.name, p.parent) for p in sorted(root.glob("*/prompt.txt"))]


class Registry:
    """Cases from the configured directories; more directories can be added while running."""

    def __init__(self, dirs: list[Path]):
        self._cases: dict[str, DemoCase] = {}
        for d in dirs:
            self.add(d)

    def add(self, root: Path) -> int:
        found = find_cases(root)
        for c in found:
            self._cases.setdefault(c.case_id, c)
        return len(found)

    def get(self, case_id: str) -> DemoCase | None:
        return self._cases.get(case_id)

    def all(self) -> list[DemoCase]:
        return sorted(self._cases.values(), key=lambda c: (c.meta.get("difficulty", ""), c.case_id))


def summary(c: DemoCase) -> dict:
    m = c.meta
    parts = split_prompt(c.prompt)
    return {"id": c.case_id, "split": m.get("split"), "difficulty": m.get("difficulty"),
            "docs": len(parts["docs"]), "buyer": parts["header"].get("Buyer"), "period": parts["header"].get("Return period"),
            "has_truth": c.target is not None, "images": sorted(c.images),
            "prompt_tokens": m.get("prompt_tokens"), "target_tokens": m.get("target_tokens")}


def detail(c: DemoCase) -> dict:
    parts = split_prompt(c.prompt)
    imgs = c.images
    for d in parts["docs"]:
        d["image"] = f"/api/cases/{c.case_id}/images/{d['id']}" if d["id"] in imgs else None
    return {**summary(c), **parts}
