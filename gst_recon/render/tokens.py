"""Token counts with the Qwen3 tokenizer (cached download), else chars/4."""

from __future__ import annotations

import os
import urllib.request
from functools import lru_cache
from pathlib import Path

URL = "https://huggingface.co/Qwen/Qwen3-8B/resolve/main/tokenizer.json"  # Apache-2.0, ungated
CACHE = Path(os.environ.get("GST_TOKENIZER", Path.home() / ".cache" / "gst_recon" / "qwen3-tokenizer.json"))


def ensure_tokenizer_cache() -> bool:
    """Download the tokenizer file once (atomic); False if offline."""
    if CACHE.exists():
        return True
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_name(f"{CACHE.name}.{os.getpid()}.part")
        urllib.request.urlretrieve(URL, tmp)
        os.replace(tmp, CACHE)  # atomic on POSIX and Windows, safe if another process won the race
        return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def _tokenizer():
    try:
        from tokenizers import Tokenizer

        if not ensure_tokenizer_cache():
            return None
        return Tokenizer.from_file(str(CACHE))
    except Exception:  # offline or tokenizers missing: fall back, flagged in count_tokens
        return None


def count_tokens(text: str) -> tuple[int, str]:
    """(count, method) where method is 'qwen3' or 'chars/4'."""
    tok = _tokenizer()
    if tok is None:
        return (len(text) + 3) // 4, "chars/4"
    return len(tok.encode(text).ids), "qwen3"
