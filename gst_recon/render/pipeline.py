"""Render one truth case into prompt.txt, target.json and meta.json."""

from __future__ import annotations

import json
import random
import shutil
import time
from pathlib import Path

from gst_recon.render import ocr as ocrmod
from gst_recon.render.context import build_context
from gst_recon.render.degrade import degrade
from gst_recon.render.holdout import check_split
from gst_recon.render.layouts import LAYOUTS, choose_layout
from gst_recon.render.paraphrase import paraphrase
from gst_recon.render.pdf import render_pages
from gst_recon.render.prompt import assemble, source_label
from gst_recon.render.tables import render_bank, render_gstr2b, render_register
from gst_recon.render.textdocs import render_text
from gst_recon.render.tokens import count_tokens
from gst_recon.render.verify import Index, case_recall, check_doc, doc_facts
from gst_recon.schema import Case, DocType

VERSION = "1"
P_EMAIL, P_WHATSAPP = 0.12, 0.08  # share of documents delivered as plain text
CONTEXT_TOKENS = 32768
ANSWER_MARGIN = 256  # tokens kept free beyond the target JSON


def case_split(case: Case, override: str | None) -> str:
    return check_split(override or getattr(case, "split", None) or "train")


def _delivery(doc_rng: random.Random) -> str:
    x = doc_rng.random()
    return "email_text" if x < P_EMAIL else "whatsapp_text" if x < P_EMAIL + P_WHATSAPP else "scan"


def _render_doc(case: Case, inv, split: str, ocr: bool, images: Path | None) -> dict:
    cid = case.case_id
    kind = "cn" if inv.doc_type == DocType.CREDIT_NOTE else "inv"
    layout_id = choose_layout(random.Random(f"{cid}:{inv.supplier_gstin}:layout:{kind}"), inv, split)
    doc_rng = random.Random(f"{cid}:{inv.doc_id}:doc")
    delivery = _delivery(doc_rng)
    ctx = build_context(case, inv, layout_id, random.Random(f"{cid}:{inv.supplier_gstin}:style"), doc_rng, split)
    rec = {"doc_id": inv.doc_id, "supplier_layout": layout_id, "date_fmt": ctx["fmt"].date_fmt, "num_fmt": ctx["fmt"].num_fmt}
    if delivery != "scan":
        text = render_text(ctx, delivery, doc_rng)
        keep = [ctx["inv_no"], ctx["supplier"]["gstin"], ctx["date"], ctx["total"]]
        rec |= {"layout": delivery, "delivery": delivery}
        return rec | {"text": paraphrase(text, keep), "ctx": ctx}
    layout = LAYOUTS[layout_id]
    t0 = time.perf_counter()
    pages = render_pages(layout, ctx)
    t1 = time.perf_counter()
    level = case.difficulty
    out, plans = [], []
    for i, p in enumerate(pages):
        d, plan = degrade(p, level, random.Random(f"{cid}:{inv.doc_id}:deg:{i}"))
        out.append(d)
        plans.append(plan)
    t2 = time.perf_counter()
    text = ocrmod.ocr_pages(out) if ocr else ""
    t3 = time.perf_counter()
    if images is not None:
        for i, d in enumerate(out):
            d.save(images / f"{inv.doc_id}{'' if i == 0 else f'_p{i + 1}'}.png", optimize=True)
    return rec | {"layout": layout_id, "delivery": "scan", "text": text, "ctx": ctx, "pages": len(pages),
                  "degrade": plans, "t": {"render": t1 - t0, "degrade": t2 - t1, "ocr": t3 - t2}}


def render_case(case: Case, out_root: Path, *, split: str | None = None, keep_images: bool = False,
                ocr: bool = True) -> dict:
    """Write out_root/<case_id>/{prompt.txt,target.json,meta.json}; returns meta. Atomic and resumable."""
    split = case_split(case, split)
    final = out_root / case.case_id
    tmp = out_root / f".{case.case_id}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    images = tmp / "images" if keep_images else None
    if images:
        images.mkdir()
    cid, inp = case.case_id, case.inputs

    docs = [_render_doc(case, inv, split, ocr, images) for inv in sorted(inp.invoices, key=lambda i: i.doc_id)]
    reg_text, reg_meta = render_register(inp.purchase_register, inp.period, inp.buyer.name, random.Random(f"{cid}:register"))
    bank_text, bank_meta = render_bank(inp.bank_statement, random.Random(f"{cid}:bank"))
    twob = render_gstr2b(inp.gstr2b)
    prompt, rest = assemble(
        case, [(d["doc_id"], source_label(d["layout"]), d["text"]) for d in docs],
        (f"Tally {reg_meta['style']} export", reg_text), twob, (f"{bank_meta['bank_style'].upper()} CSV", bank_text))

    rest_ix = Index.of(rest)
    by_id = {i.doc_id: i for i in inp.invoices}
    recalls = [check_doc(d["doc_id"], doc_facts(by_id[d["doc_id"]], d["ctx"]["date"]), d["text"], rest_ix) for d in docs]
    stats = case_recall(recalls, {d["doc_id"] for d in docs if d["delivery"] == "scan"})

    target = case.expected.model_dump_json(indent=None)
    p_tok, method = count_tokens(prompt)
    t_tok, _ = count_tokens(target)
    meta = {
        "case_id": cid, "seed": case.seed, "difficulty": case.difficulty, "split": split, "render_version": VERSION,
        "ocr_engine": ocrmod.tesseract_version() if ocr else "none",
        "documents": [{k: d[k] for k in ("doc_id", "layout", "supplier_layout", "delivery", "date_fmt", "num_fmt", "pages", "degrade") if k in d}
                      for d in docs],
        "register": reg_meta, "bank": bank_meta,
        "prompt_chars": len(prompt), "prompt_tokens": p_tok, "target_tokens": t_tok, "token_method": method,
        "fits_context": p_tok + t_tok + ANSWER_MARGIN <= CONTEXT_TOKENS,
        **stats,
        "timing_s": {k: round(sum(d.get("t", {}).get(k, 0) for d in docs), 3) for k in ("render", "degrade", "ocr")},
    }
    (tmp / "prompt.txt").write_text(prompt)
    (tmp / "target.json").write_text(target)
    (tmp / "meta.json").write_text(json.dumps(meta, indent=1))
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    return meta
