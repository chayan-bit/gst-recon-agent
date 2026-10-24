"""Jinja2 HTML -> PDF (WeasyPrint) -> PIL pages (pypdfium2).

Fonts are bundled (`fonts/`) and fontconfig is pointed at them only, so output
does not depend on the host's installed fonts and startup stays fast.
Needs pango/harfbuzz shared libraries (on macOS under nix: set
DYLD_FALLBACK_LIBRARY_PATH to their lib dirs; Linux hosts normally have them).
"""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops

from gst_recon.render.layouts import Layout

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"


def _setup_fontconfig() -> None:
    cache = Path(tempfile.gettempdir()) / "gst-recon-fontcache"
    cache.mkdir(exist_ok=True)
    conf = cache / "fonts.conf"
    xml = f'<?xml version="1.0"?><fontconfig><dir>{FONTS}</dir><cachedir>{cache}</cachedir></fontconfig>'
    try:
        if not conf.exists() or conf.read_text(encoding="utf-8") != xml:
            tmp = cache / f"fonts.{os.getpid()}.tmp"
            tmp.write_text(xml, encoding="utf-8")
            os.replace(tmp, conf)  # workers start together; never leave a half-written config
    except OSError:
        pass  # another worker is replacing it right now (Windows keeps open files locked); content is identical
    os.environ["FONTCONFIG_FILE"] = str(conf)


@lru_cache(maxsize=1)
def _env():
    import jinja2

    return jinja2.Environment(loader=jinja2.FileSystemLoader(HERE / "templates"), autoescape=True,
                              undefined=jinja2.StrictUndefined)


@lru_cache(maxsize=1)
def _weasy():
    _setup_fontconfig()  # must precede the first pango use
    import weasyprint

    return weasyprint


def render_html(layout: Layout, ctx: dict) -> str:
    return _env().get_template(layout.template).render(**ctx, fonts=FONTS.as_uri(), page=layout.page)


def html_to_pdf(html: str) -> bytes:
    return _weasy().HTML(string=html, base_url=str(HERE)).write_pdf()


def pdf_to_pages(pdf: bytes, dpi: int) -> list[Image.Image]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        return [doc[i].render(scale=dpi / 72).to_pil().convert("RGB") for i in range(len(doc))]
    finally:
        doc.close()


def crop_blank(img: Image.Image, pad: int = 24) -> Image.Image:
    """Trim blank space below/around content (receipt-style documents)."""
    bg = Image.new("RGB", img.size, (255, 255, 255))
    box = ImageChops.difference(img, bg).getbbox()
    if not box:
        return img
    l, t, r, b = box
    return img.crop((max(0, l - pad), max(0, t - pad), min(img.width, r + pad), min(img.height, b + pad)))


def crop_bottom(img: Image.Image, pad: int = 60, min_h: int = 500) -> Image.Image:
    """Drop the blank lower part of a page: same width, shorter scan (saves OCR time)."""
    box = ImageChops.difference(img, Image.new("RGB", img.size, (255, 255, 255))).getbbox()
    return img.crop((0, 0, img.width, min(img.height, max(min_h, box[3] + pad)))) if box else img


def render_pages(layout: Layout, ctx: dict) -> list[Image.Image]:
    pages = pdf_to_pages(html_to_pdf(render_html(layout, ctx)), layout.dpi)
    return [crop_blank(p) if layout.crop else crop_bottom(p) for p in pages]
