"""Platform branches of the batch CLI: start method and per-worker memory cap (Linux vs Windows vs macOS)."""

import pytest

from gst_recon.render import memlimit
from gst_recon.render.__main__ import _init_worker, mp_context


@pytest.mark.parametrize("platform,method", [("linux", "fork"), ("win32", "spawn"), ("darwin", "spawn")])
def test_start_method_follows_platform(platform, method):
    assert mp_context(platform) == method


def test_memory_cap_dispatches_by_platform(monkeypatch):
    monkeypatch.setattr(memlimit, "_job_object_cap", lambda gb: "job_object")
    monkeypatch.setattr(memlimit, "_rlimit_cap", lambda gb: "rlimit_data")
    assert memlimit.apply_memory_cap(6, "win32") == "job_object"
    assert memlimit.apply_memory_cap(6, "linux") == "rlimit_data"
    assert memlimit.apply_memory_cap(6, "darwin") == "unsupported"
    assert memlimit.apply_memory_cap(0, "win32") == "off"


def test_linux_cap_sets_rlimit_data_only(monkeypatch):
    import resource

    calls = []
    monkeypatch.setattr(resource, "setrlimit", lambda which, lim: calls.append((which, lim)))
    assert memlimit._rlimit_cap(2) == "rlimit_data"
    assert calls == [(resource.RLIMIT_DATA, (2 * 2**30, 2 * 2**30))]


def test_linux_cap_reports_unsupported_when_the_kernel_refuses(monkeypatch):
    import resource

    def refuse(*_):
        raise OSError("not permitted")

    monkeypatch.setattr(resource, "setrlimit", refuse)
    assert memlimit._rlimit_cap(2) == "unsupported"


def test_worker_init_warns_when_cap_is_not_enforceable(monkeypatch, capsys):
    monkeypatch.setattr("gst_recon.render.__main__.apply_memory_cap", lambda gb: "unsupported")
    _init_worker(6)
    assert "not enforceable" in capsys.readouterr().err
    monkeypatch.setattr("gst_recon.render.__main__.apply_memory_cap", lambda gb: "job_object")
    _init_worker(6)
    assert capsys.readouterr().err == ""


@pytest.mark.skipif(not __import__("sys").platform.startswith("win"), reason="Windows only")
def test_job_object_cap_applies_on_windows():
    assert memlimit._job_object_cap(64) == "job_object"


def test_tokenizer_cache_download_is_skipped_when_present(tmp_path, monkeypatch):
    from gst_recon.render import tokens

    f = tmp_path / "tok.json"
    f.write_text("{}")
    monkeypatch.setattr(tokens, "CACHE", f)
    monkeypatch.setattr(tokens.urllib.request, "urlretrieve", lambda *a: pytest.fail("must not download"))
    assert tokens.ensure_tokenizer_cache() is True
