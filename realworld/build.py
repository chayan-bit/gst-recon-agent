"""CLI: python -m realworld.build --out data/realworld [--images-dir DIR] [--truth-out data/truth/realworld]

Builds the real-world sanity split: truth from cases.json (rules engine, checked against the hand
expectations), each document rendered through its real-world print format to PDF, rasterised at
200 dpi and OCR'd with Tesseract (clean-scan realism, no synthetic degradation). With --images-dir,
phone photos replace the rasterised PDF for the documents they cover (see PHOTO_PROTOCOL.md).
Writes <out>/<case_id>/{prompt.txt,target.json,meta.json} like data/rendered, plus <out>/print/*.pdf.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

from realworld.truth import SPLIT, build_all, load_parties, load_specs

VERSION = "rw1"
DPI = 200
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")  # HEIC needs pillow-heif: shoot JPEG ("Most Compatible")

# format id -> provenance (PROVENANCE.md mirrors this table)
SOURCES = {
    "ic_e_invoice": ("resilient-tech/india-compliance", "GPL-3.0", "india_compliance/gst_india/print_format/e_invoice/e_invoice.html",
                     "f0c6bec3af89448a785e4abcabfbe6f47833ecce", "original"),
    "ic_pos_invoice": ("resilient-tech/india-compliance", "GPL-3.0", "india_compliance/gst_india/print_format/gst_pos_invoice/gst_pos_invoice.json",
                       "f0c6bec3af89448a785e4abcabfbe6f47833ecce", "original"),
    "ic_gst_tax_invoice": ("resilient-tech/india-compliance", "GPL-3.0", "india_compliance/gst_india/print_format/gst_tax_invoice/gst_tax_invoice.json",
                           "f0c6bec3af89448a785e4abcabfbe6f47833ecce", "port"),
    "billgst_invoice": ("ghoshbishakh/billgst", "GPL-3.0", "gstbillingapp/templates/gstbillingapp/invoice_printer.html",
                        "9a45e0173b30fa04b3276baa27aaa9ad8bca60d5", "port"),
    "odoo_l10n_in_invoice": ("odoo/odoo", "LGPL-3.0", "addons/l10n_in/views/report_invoice.xml",
                             "60fdb530c0eaf38b46600e772156b39a83578d81", "port"),
    "technodweep_tax_invoice": ("technodweep/gst-invoice", "MIT", "views/invoice-order/print.php",
                                "dcce9b6075e1e4d1fce373af0198ecbdecaeb3e6", "port"),
    "fgb_classic": ("IamRamgarhia/Free-GST-Billing-Software", "MIT", "src/components/InvoicePreview.jsx",
                    "f96be4603dc90a5f814e93c07fc31a81aa60d4d9", "port"),
}
SHOWN_DATE = {"ic_e_invoice": "DD/MM/YYYY", "ic_pos_invoice": "DD-MM-YYYY", "ic_gst_tax_invoice": "DD-MM-YYYY",
              "billgst_invoice": "YYYY-MM-DD", "odoo_l10n_in_invoice": "DD/MM/YYYY", "technodweep_tax_invoice": "DD-MM-YYYY",
              "fgb_classic": "DD/MM/YYYY"}
# Documents printed and photographed under PHOTO_PROTOCOL.md: every format at least once, all discrepancy kinds.
PHOTO_SUBSET = ("rw01_D01", "rw01_D02", "rw01_D03", "rw02_D01", "rw02_D02", "rw03_D01", "rw04_D03", "rw05_D02",
                "rw06_D02", "rw09_D02")


def photo_map(images_dir: Path | None) -> dict[str, list[Path]]:
    """<case>_<doc>[_pN].<ext> files map by name; otherwise N files (sorted by name, i.e. capture order)
    map one-to-one onto PHOTO_SUBSET."""
    if images_dir is None:
        return {}
    files = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXT)
    named = {}
    for p in files:
        key = "_".join(p.stem.split("_")[:2])
        if key.startswith("rw"):
            named.setdefault(key, []).append(p)
    if named:
        return named
    if len(files) != len(PHOTO_SUBSET):
        raise SystemExit(f"{images_dir}: {len(files)} images but PHOTO_SUBSET has {len(PHOTO_SUBSET)}; name files <case>_<doc>.jpg instead")
    return {k: [p] for k, p in zip(PHOTO_SUBSET, files)}


def load_photo(path: Path):
    from PIL import Image, ImageOps

    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")  # phones store rotation in EXIF


def render_doc(case, doc_spec: dict, parties: dict, print_dir: Path, photos: list[Path], ocr: bool) -> dict:
    from gst_recon.render import ocr as ocrmod
    from gst_recon.render.pdf import crop_blank, crop_bottom, pdf_to_pages
    from realworld.docs import html_to_pdf, render_html

    inv = next(i for i in case.inputs.invoices if i.doc_id == doc_spec["id"])
    sup = next(s for k, s in parties["suppliers"].items() if k == doc_spec["supplier"])
    from gst_recon.schema import Party

    supplier = Party(name=sup["name"], gstin=sup["gstin"], state_code=sup["state_code"], address=sup["address"])
    fmt = doc_spec["format"]
    pdf = html_to_pdf(render_html(fmt, inv, supplier, case.inputs.buyer, doc_spec))
    key = f"{case.case_id}_{inv.doc_id}"
    (print_dir / f"{key}.pdf").write_bytes(pdf)
    if photos:
        pages, delivery = [load_photo(p) for p in photos], "photo"
    else:
        pages = [crop_blank(p) if fmt == "ic_pos_invoice" else crop_bottom(p) for p in pdf_to_pages(pdf, DPI)]
        delivery = "scan"
    text = ocrmod.ocr_pages(pages) if ocr else ""
    repo, lic, path, commit, method = SOURCES[fmt]
    return {"doc_id": inv.doc_id, "format": fmt, "delivery": delivery, "pages": len(pages), "text": text,
            "images": [p.name for p in photos], "source": {"repo": f"https://github.com/{repo}", "license": lic,
                                                           "path": path, "commit": commit, "method": method}}


def render_case(case, spec: dict, parties: dict, out: Path, photos: dict, ocr: bool) -> dict:
    from gst_recon.render.fmt import fmt_date
    from gst_recon.render.prompt import assemble
    from gst_recon.render.tables import render_bank, render_gstr2b, render_register
    from gst_recon.render.tokens import count_tokens
    from gst_recon.render.verify import Index, case_recall, check_doc, doc_facts

    print_dir = out / "print"
    print_dir.mkdir(parents=True, exist_ok=True)
    cid, inp = case.case_id, case.inputs
    docs = [render_doc(case, d, parties, print_dir, photos.get(f"{cid}_{d['id']}", []), ocr) for d in spec["docs"]]
    reg_text, reg_meta = render_register(inp.purchase_register, inp.period, inp.buyer.name, random.Random(f"{cid}:register"))
    bank_text, bank_meta = render_bank(inp.bank_statement, random.Random(f"{cid}:bank"))
    label = {"scan": "scanned document, OCR text", "photo": "phone photo, OCR text"}
    prompt, rest = assemble(case, [(d["doc_id"], label[d["delivery"]], d["text"]) for d in docs],
                            (f"Tally {reg_meta['style']} export", reg_text), render_gstr2b(inp.gstr2b),
                            (f"{bank_meta['bank_style'].upper()} CSV", bank_text))
    by_id = {i.doc_id: i for i in inp.invoices}
    rest_ix = Index.of(rest)
    recalls = [check_doc(d["doc_id"], doc_facts(by_id[d["doc_id"]], fmt_date(by_id[d["doc_id"]].invoice_date, SHOWN_DATE[d["format"]])),
                         d["text"], rest_ix) for d in docs]
    stats = case_recall(recalls, {d["doc_id"] for d in docs})
    target = case.expected.model_dump_json(indent=None)
    p_tok, method = count_tokens(prompt)
    t_tok, _ = count_tokens(target)
    from gst_recon.render import ocr as ocrmod

    split = SPLIT + ("_photo" if any(d["delivery"] == "photo" for d in docs) else "")
    meta = {"case_id": cid, "seed": 0, "difficulty": SPLIT, "split": split, "render_version": VERSION,
            "ocr_engine": ocrmod.tesseract_version() if ocr else "none", "degradation": "none (clean 200 dpi raster) unless delivery=photo",
            "documents": [{k: v for k, v in d.items() if k != "text"} for d in docs], "register": reg_meta, "bank": bank_meta,
            "anomalies": case.anomalies, "prompt_chars": len(prompt), "prompt_tokens": p_tok, "target_tokens": t_tok,
            "token_method": method, "parties": "synthetic (realworld/parties.json)", **stats}
    final, tmp = out / cid, out / f".{cid}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for name, text in (("prompt.txt", prompt), ("target.json", target), ("meta.json", json.dumps(meta, indent=1))):
        (tmp / name).write_text(text, encoding="utf-8")
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m realworld.build", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=Path("data/realworld"))
    ap.add_argument("--truth-out", type=Path, default=Path("data/truth/realworld"))
    ap.add_argument("--images-dir", type=Path, help="phone photos replacing the rasterised PDF (PHOTO_PROTOCOL.md)")
    ap.add_argument("--no-ocr", action="store_true", help="write PDFs and truth only")
    a = ap.parse_args(argv)
    cases, problems = build_all(a.truth_out)
    if problems:  # never render a set whose truth disagrees with the hand-checked law
        print("\n".join(problems), file=sys.stderr)
        return 1
    parties, specs = load_parties(), {s["id"]: s for s in load_specs()}
    photos = photo_map(a.images_dir)
    (a.out / "print").mkdir(parents=True, exist_ok=True)
    (a.out / "print" / "PHOTO_ORDER.txt").write_text("".join(f"{k}.pdf\n" for k in PHOTO_SUBSET))
    for c in cases:
        m = render_case(c, specs[c.case_id], parties, a.out, photos, not a.no_ocr)
        print(f"{c.case_id}: {len(m['documents'])} docs, ocr_recall {m['ocr_recall']:.3f}, prompt {m['prompt_tokens']} tok, "
              f"target {m['target_tokens']} tok, lost {m['unrecoverable']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
