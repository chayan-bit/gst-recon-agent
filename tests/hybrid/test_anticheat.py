"""The reconciler sees prompt.txt and the per-document records only: no file access, no truth imports."""

from __future__ import annotations

import ast
import builtins
import io
import pathlib
from pathlib import Path

import pytest

from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.hybrid.sft import truth_records

PKG = Path(__file__).resolve().parents[2] / "gst_recon" / "hybrid"
RECONCILER = ("reconcile.py", "linker.py", "inputs.py", "docschema.py", "repair.py", "fill.py")
FORBIDDEN_IMPORTS = ("gst_recon.hybrid.sft", "gst_recon.eval.cases", "gst_recon.sim.world")
FORBIDDEN_TEXT = ("target.json", "meta.json", "truth")


def test_reconciler_modules_import_no_truth_source():
    for name in RECONCILER:
        tree = ast.parse((PKG / name).read_text())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not mods & set(FORBIDDEN_IMPORTS), name
        code = "\n".join(ast.get_source_segment((PKG / name).read_text(), n) or "" for n in tree.body
                         if not isinstance(n, ast.Expr))  # skip module docstrings
        assert not any(s in code for s in ("target.json", "meta.json", "open(", "read_text")), name


def test_reconcile_opens_no_file(ex, monkeypatch):
    prompt, target, case = ex
    recs = truth_records(target, case)  # truth is read BEFORE the trap is set

    def trap(*a, **k):
        raise AssertionError(f"reconciler tried to open a file: {a[:1]}")

    for mod, attr in ((builtins, "open"), (io, "open"), (pathlib.Path, "open"), (pathlib.Path, "read_text"),
                      (pathlib.Path, "read_bytes")):
        monkeypatch.setattr(mod, attr, trap)
    out, _ = reconcile_prompt(prompt, recs)
    assert out.itc


def test_trap_actually_fires(monkeypatch):
    monkeypatch.setattr(pathlib.Path, "read_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("trap")))
    with pytest.raises(AssertionError):
        Path("examples/x/target.json").read_text()
