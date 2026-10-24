"""Render tests need the `render` extra (and pango for WeasyPrint); skip cleanly without them."""

import shutil

import pytest

pytest.importorskip("jinja2")
pytest.importorskip("pypdfium2")
pytest.importorskip("augraphy")


@pytest.fixture(scope="session")
def weasy():
    try:
        from gst_recon.render import pdf

        return pdf._weasy()
    except OSError as e:  # pango/gobject shared libraries missing
        pytest.skip(f"WeasyPrint system libraries unavailable: {e}")


@pytest.fixture(scope="session")
def has_tesseract():
    return shutil.which("tesseract") is not None


@pytest.fixture(scope="session")
def case():
    from gst_recon.sim.world import generate_case

    return generate_case(3, "easy", 0)


@pytest.fixture(scope="session")
def tiny_case(case):
    """Two documents only: keeps the end-to-end render tests to a few seconds (Mac: light tests only)."""
    inputs = case.inputs.model_copy(update={"invoices": case.inputs.invoices[:2]})
    return case.model_copy(update={"inputs": inputs})
