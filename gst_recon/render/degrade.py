"""Scan/photo degradation of rendered pages, severity by difficulty.

The effect list and every parameter are drawn from a per-document rng, so a
(seed, doc) pair always produces the same pixels. Augraphy reads the global
`random` / `numpy.random` state, which is therefore re-seeded per call (single
threaded per process). The chosen parameters are returned for meta.json.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).resolve().parent / "fonts" / "LiberationSans-Bold.ttf"
STAMPS = ("PAID", "RECEIVED", "COPY", "CHECKED", "ORIGINAL", "VERIFIED", "ACCOUNTS")
LEVELS = {"easy": 0, "medium": 1, "hard": 2}


def _stamp(img: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    """Semi-transparent rubber stamp dropped anywhere on the page (may cover figures)."""
    text, size = rng.choice(STAMPS), rng.randint(55, 110)
    colour = rng.choice(((190, 30, 30), (30, 60, 170), (20, 20, 20)))
    font = ImageFont.truetype(str(FONT), size)
    box = font.getbbox(text)
    w, h = box[2] + 40, box[3] + 30
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle((4, 4, w - 5, h - 5), outline=colour + (150,), width=5)
    d.text((20, 10), text, font=font, fill=colour + (150,))
    angle = rng.uniform(-30, 30)
    layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    x, y = rng.randint(0, max(0, img.width - layer.width)), rng.randint(0, max(0, img.height - layer.height))
    out = img.convert("RGBA")
    out.alpha_composite(layer, (x, y))
    return out.convert("RGB"), {"stamp": text, "stamp_xy": [x, y]}


def _fold(a: np.ndarray, rng: random.Random) -> np.ndarray:
    """A paper crease: a soft shaded band plus a thin dark line (augraphy's Folding is not seed-stable)."""
    h = a.shape[0]
    y, width = rng.randint(h // 5, 4 * h // 5), rng.randint(14, 40)
    rows = np.arange(h)
    shade = 1 - rng.uniform(0.1, 0.35) * np.exp(-(((rows - y) / width) ** 2))
    shade[max(0, y - 1):y + 1] *= rng.uniform(0.55, 0.8)
    return np.clip(a * shade[:, None, None], 0, 255).astype(np.uint8)


def _fax(a: np.ndarray, rng: random.Random) -> np.ndarray:
    """Low-resolution 1-bit fax: halve the resolution, hard threshold, a few dead scan lines.

    (Augraphy's Faxify allocated >12 GB on some inputs, so it is not used.)
    """
    import cv2

    h, w = a.shape[:2]
    g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA)
    g = np.where(g > rng.randint(110, 170), 255, 0).astype(np.uint8)
    for _ in range(rng.randint(0, 3)):
        g[rng.randrange(g.shape[0]), :] = rng.choice((0, 255))
    g = cv2.resize(g, (w, h), interpolation=cv2.INTER_NEAREST)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def _plan(level: str, rng: random.Random) -> dict:
    """Draw the effect parameters for one document."""
    lv = LEVELS[level]
    u = rng.uniform
    return {
        "level": level,
        "rotate": round(u(-1, 1) * (0.6, 1.5, 3.0)[lv], 2),
        "blur_sigma": round(u(0, (0.3, 0.6, 1.1)[lv]), 2),
        "rescale": round(u((1, 0.85, 0.6)[lv], 1.0), 2) if lv else 1.0,  # down-up resample: lost resolution
        "jpeg": rng.randint(*((80, 95), (60, 85), (30, 60))[lv]),
        "brightness": round(u(*((0.95, 1.05), (0.85, 1.1), (0.7, 1.15))[lv]), 2),
        "ink_bleed": rng.random() < (0.2, 0.4, 0.6)[lv],
        "noise_texture": lv >= 1 and rng.random() < (0, 0.3, 0.5)[lv],
        "subtle_noise": rng.randint(3, 8) * (1 + lv // 2),
        "shadow": lv >= 1 and rng.random() < (0, 0.15, 0.3)[lv],
        "folds": rng.choice((0, 0, 0, 1)) if lv == 1 else rng.choice((0, 1, 1, 2)) if lv == 2 else 0,
        "photocopy": lv >= 1 and rng.random() < (0, 0.25, 0.5)[lv],
        "fax": lv == 2 and rng.random() < 0.2,
        "dirty_drum": lv == 2 and rng.random() < 0.3,
        "low_ink_lines": lv >= 1 and rng.random() < (0, 0.1, 0.3)[lv],
        "stamp": lv >= 1 and rng.random() < (0, 0.1, 0.35)[lv],
        "seed": rng.randrange(2**31),
    }


def degrade(img: Image.Image, level: str, rng: random.Random) -> tuple[Image.Image, dict]:
    """Return (degraded RGB image, parameter record)."""
    import cv2
    from augraphy import (BadPhotoCopy, Brightness, DirtyDrum, InkBleed, Jpeg, LowInkRandomLines,
                          NoiseTexturize, ShadowCast, SubtleNoise)

    cv2.setNumThreads(1)
    # opencv's CPU-dispatched kernels (AVX512 vs AVX2, per build) round HSV2BGR/warpAffine differently; the baseline path
    # is bit-identical across hosts, which keeps renders byte-identical between machines
    cv2.setUseOptimized(False)
    plan = _plan(level, rng)
    random.seed(plan["seed"])
    np.random.seed(plan["seed"] % (2**32))
    rng2 = random.Random(plan["seed"])

    if plan["stamp"]:
        img, extra = _stamp(img, rng2)
        plan.update(extra)
    a = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    steps = []
    if plan["ink_bleed"]:
        steps.append(InkBleed(intensity_range=(0.3, 0.5), kernel_size=(3, 3), severity=(0.2, 0.4), p=1))
    if plan["noise_texture"]:
        steps.append(NoiseTexturize(sigma_range=(2, 6), turbulence_range=(2, 4), p=1))
    if plan["photocopy"]:
        steps.append(BadPhotoCopy(noise_type=-1, noise_iteration=(1, 1), noise_size=(1, 2), noise_value=(60, 140),
                                  noise_sparsity=(0.2, 0.6), noise_concentration=(0.1, 0.4), p=1))
    if plan["dirty_drum"]:
        steps.append(DirtyDrum(line_width_range=(1, 2), line_concentration=0.02, noise_intensity=0.25, p=1))
    if plan["low_ink_lines"]:
        steps.append(LowInkRandomLines(count_range=(3, 8), use_consistent_lines=False, noise_probability=0.1, p=1))
    if plan["shadow"]:
        steps.append(ShadowCast(shadow_opacity_range=(0.2, 0.5), shadow_blur_kernel_range=(101, 201), p=1))
    steps.append(SubtleNoise(subtle_range=plan["subtle_noise"], p=1))
    steps.append(Brightness(brightness_range=(plan["brightness"], plan["brightness"]), p=1))
    for s in steps:
        out = s(a)
        a = out if isinstance(out, np.ndarray) else out["output"] if isinstance(out, dict) else out
    if plan["fax"]:
        a = _fax(a, rng2)
    for _ in range(plan["folds"]):
        a = _fold(a, rng2)
    if plan["rescale"] < 1.0:
        h, w = a.shape[:2]
        small = cv2.resize(a, (int(w * plan["rescale"]), int(h * plan["rescale"])), interpolation=cv2.INTER_AREA)
        a = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    if plan["blur_sigma"] > 0.05:
        a = cv2.GaussianBlur(a, (0, 0), plan["blur_sigma"])
    h, w = a.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), plan["rotate"], 1.0)
    a = cv2.warpAffine(a, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    out = Jpeg(quality_range=(plan["jpeg"], plan["jpeg"]), p=1)(a)
    a = out if isinstance(out, np.ndarray) else out["output"] if isinstance(out, dict) else out
    return Image.fromarray(cv2.cvtColor(a, cv2.COLOR_BGR2RGB)), plan
