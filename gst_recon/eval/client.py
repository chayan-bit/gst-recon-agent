"""Minimal OpenAI-compatible chat client (stdlib only) with per-request retry and timing."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from gst_recon.schema import output_json_schema


def chat_url(endpoint: str) -> str:
    e = endpoint.rstrip("/")
    if e.endswith("/chat/completions"):
        return e
    return f"{e}/chat/completions" if e.endswith("/v1") else f"{e}/v1/chat/completions"


def json_schema_format(schema: dict | None = None) -> dict:
    """response_format for grammar-constrained decoding (SGLang/XGrammar)."""
    return {"type": "json_schema", "json_schema": {"name": "recon", "schema": schema or output_json_schema()}}


def chat(endpoint: str, model: str, messages: list[dict], *, response_format: dict | None = None,
         max_tokens: int = 8192, temperature: float = 0.0, timeout: float = 900.0, api_key: str = "EMPTY",
         retries: int = 2, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """One completion. Never raises: failures come back as {"error": str, "text": ""} after retries.
    Returns text, prompt_tokens, completion_tokens, finish_reason, latency_s (of the successful try)."""
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if response_format:
        body["response_format"] = response_format
    body.update(extra or {})
    req = urllib.request.Request(chat_url(endpoint), data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    err = ""
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            choice = data["choices"][0]
            usage = data.get("usage") or {}
            return {"text": choice["message"].get("content") or "", "finish_reason": choice.get("finish_reason"),
                    "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                    "latency_s": time.perf_counter() - t0, "error": None}
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
            if e.code < 500 and e.code != 429:
                break  # a 4xx will not get better on retry
        except (urllib.error.URLError, TimeoutError, ConnectionError, KeyError, IndexError, ValueError) as e:
            err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(min(2 ** attempt, 8))
    return {"text": "", "finish_reason": None, "prompt_tokens": None, "completion_tokens": None,
            "latency_s": None, "error": err}
