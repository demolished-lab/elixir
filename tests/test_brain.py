# -*- coding: utf-8 -*-
"""Brain + memory gates: plan shape, learned arbitration, run logging."""

from elixir import brain
from elixir import memory as mem


def test_decompose_url_task():
    steps = brain.decompose("fetch https://example.com please")
    assert any(s["verb"] == "web_fetch" for s in steps)
    assert any("example.com" in str(s["args"]) for s in steps)


def test_decompose_search_task():
    steps = brain.decompose("search the web for stealth browsers")
    assert any(s["verb"] == "web_search" for s in steps)


def test_best_backend_prefers_learned(tmp_path, monkeypatch):
    import elixir.memory as m

    monkeypatch.setattr(m, "DB", tmp_path / "mem.db")
    assert m.best_backend("s", ["obscura", "cloak"]) == "obscura"
    for _ in range(3):
        m.log_site("s", "cloak", True)
    m.log_site("s", "obscura", False)
    assert m.best_backend("s", ["obscura", "cloak"]) == "cloak"


def test_run_logs_and_verifies(tmp_path, monkeypatch):
    import elixir.memory as m

    monkeypatch.setattr(m, "DB", tmp_path / "mem.db")
    r = brain.run("fetch https://example.com")
    assert r["ok"] is True
    assert m.stats("example.com")
