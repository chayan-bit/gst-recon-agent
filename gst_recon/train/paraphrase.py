"""LLM paraphrase of text-delivered documents (email / WhatsApp) inside a rendered prompt.

The render stage leaves these blocks in a templated voice (its `paraphrase` hook is
identity). Here a teacher LLM rewrites each block; a rewrite is only kept in the
curated set if every fact string survives verbatim (our code check) and the
CuratorKIT HallucinationGate judges it grounded in the original.
"""

from __future__ import annotations

import re

SOURCES = ("email body", "WhatsApp message")
BLOCK = re.compile(r"^--- (D\d+) \| (" + "|".join(SOURCES) + r") ---\n(.*?)(?=\n--- D\d+ \||\n\n=== )", re.MULTILINE | re.DOTALL)
FACT = re.compile(r"[^\s,;:()\"']*\d[^\s,;:()\"']*")

INSTRUCTION = ("Rewrite this business message about a purchase invoice in a different natural voice, as a "
               "different sender would write it. Keep every number, code, GSTIN, invoice number, date and amount "
               "exactly as written (same characters), keep the company name, every item description and any "
               "'Remarks / Purpose' line word for word, add no new facts. Reply with the rewritten message only.")


def blocks(prompt: str) -> list[tuple[str, str, str]]:
    """(doc_id, source, text) for every text-delivered document."""
    return [(m.group(1), m.group(2), m.group(3)) for m in BLOCK.finditer(prompt)]


REMARK = re.compile(r"Remarks / Purpose: (.+)")


def facts(text: str, extraction: dict | None = None) -> set[str]:
    """Strings a rewrite must keep verbatim: digit-bearing tokens (amounts, dates, GSTINs,
    invoice numbers, HSN), the remarks (they decide s.17(5)), and the supplier name and
    line descriptions that the target extraction reproduces."""
    out = {f.rstrip(".") for f in FACT.findall(text)} | {r.strip() for r in REMARK.findall(text)}
    if extraction:
        out |= {extraction.get("supplier_name", "")} | {li.get("description", "") for li in extraction.get("line_items", [])}
    return {f for f in out if f and f in text}  # only what the original actually shows


def missing_facts(original: str, rewrite: str, extraction: dict | None = None) -> list[str]:
    return sorted(f for f in facts(original, extraction) if f not in rewrite)


def apply(prompt: str, rewrites: dict[str, str]) -> str:
    """Replace the text of each rewritten block (keyed by doc_id); other blocks unchanged."""
    def sub(m: re.Match) -> str:
        new = rewrites.get(m.group(1))
        if new is None:
            return m.group(0)
        old = m.group(3)
        return m.group(0)[: m.start(3) - m.start(0)] + new.strip() + old[len(old.rstrip()):]
    return BLOCK.sub(sub, prompt)
