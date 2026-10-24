"""Hook for a later LLM paraphrase stage of text-delivered documents (email, WhatsApp)."""

from __future__ import annotations


def paraphrase(text: str, facts: list[str]) -> str:
    """Rewrite `text` in a different voice (no LLM is called yet: identity).

    HOOK: a future stage may plug an LLM in here. Contract: every string in
    `facts` (invoice no, GSTIN, date, amounts exactly as displayed) must appear
    verbatim in the result; the OCR-recall check after rendering enforces it.
    """
    return text
