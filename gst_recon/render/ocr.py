"""OCR with the Tesseract CLI (no Python binding needed).

Binary from $GST_TESSERACT (default `tesseract` on PATH); language data from
$TESSDATA_PREFIX if set. One OCR thread per process (parallelism is per worker).
"""

from __future__ import annotations

import io
import os
import re
import subprocess

from PIL import Image

ENGINE = "tesseract"


def tesseract_version() -> str:
    cmd = os.environ.get("GST_TESSERACT", "tesseract")
    out = subprocess.run([cmd, "--version"], capture_output=True, text=True, check=True)
    return (out.stdout or out.stderr).splitlines()[0].strip()


SCALE = float(os.environ.get("GST_OCR_SCALE", "1.5"))  # 200 dpi pages: x1.0 vs x1.5 vs x2.0 gave medium recall .87/.90/.90, easy .94/.94/.92; psm 6 beat psm 3/4/11 on noisy scans


def ocr_page(img: Image.Image, psm: int = 6, scale: float = SCALE) -> str:
    import cv2
    import numpy as np

    cmd = os.environ.get("GST_TESSERACT", "tesseract")
    buf = io.BytesIO()
    gray = np.asarray(img.convert("L"))
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    Image.fromarray(gray).save(buf, format="PNG")
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    res = subprocess.run([cmd, "stdin", "stdout", "-l", "eng", "--psm", str(psm), "-c", "preserve_interword_spaces=1"],
                         input=buf.getvalue(), capture_output=True, env=env, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"tesseract failed: {res.stderr.decode(errors='replace')[:300]}")
    return clean(res.stdout.decode("utf-8", errors="replace"))


def clean(text: str) -> str:
    """Trim line ends, squeeze long space runs (keeps column gaps), drop blank-line runs."""
    lines = [re.sub(r" {3,}", "  ", l.rstrip()) for l in text.replace("\x0c", "").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def ocr_pages(pages: list[Image.Image]) -> str:
    return "\n\n".join(ocr_page(p) for p in pages)
