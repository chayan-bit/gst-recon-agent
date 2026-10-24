"""Cost per 1,000 cases. Every price is a caller-supplied input; none is built in."""

from __future__ import annotations


def cost_per_1000(*, n_requests: int, wall_s: float, prompt_tokens: int, completion_tokens: int,
                  gpu_hour_usd: float | None = None, api_in_per_mtok: float | None = None,
                  api_out_per_mtok: float | None = None) -> dict[str, float | None]:
    """gpu: measured wall time of this run times the GPU-hour price (assumes the GPU is saturated at the
    run's concurrency). api: this run's mean token counts times the closed API's list price; token counts come
    from this model's tokenizer, so treat the API figure as an approximation."""
    out: dict[str, float | None] = {"gpu_usd": None, "api_usd": None}
    if n_requests <= 0:
        return out
    if gpu_hour_usd is not None and wall_s > 0:
        out["gpu_usd"] = gpu_hour_usd * (wall_s / 3600.0) * 1000.0 / n_requests
    if api_in_per_mtok is not None and api_out_per_mtok is not None:
        out["api_usd"] = (prompt_tokens * api_in_per_mtok + completion_tokens * api_out_per_mtok) / 1e6 * 1000.0 / n_requests
    return out
