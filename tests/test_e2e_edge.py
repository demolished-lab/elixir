# -*- coding: utf-8 -*-
"""End-to-end edge cases: every failure mode must degrade honestly."""

from elixir import autopilot, brain
from elixir import memory as mem


def test_empty_task_falls_back_to_buddy():
    steps = brain.decompose("hello there")
    assert steps and steps[0]["verb"] == "buddy_ask"


def test_login_wall_routes_to_fallback():
    from elixir import social

    r = social.route("xiaohongshu")
    assert r["ok"] is False
    assert "cloak" in r["elixir_fallback"]
    assert "unlock" in r


def test_unknown_platform():
    from elixir import social

    r = social.route("myspace2")
    assert r["ok"] is False and "unknown" in r["error"]


def test_unknown_backend_fix():
    r = autopilot.run_auto("does_not_exist")
    assert r["ok"] is False


def test_spend_gate_before_cloud():
    from elixir import spend

    assert isinstance(spend.spent_this_month(), float)
    assert isinstance(spend.allowed(), bool)


def test_retry_rung_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(mem, "DB", tmp_path / "mem.db")
    r = brain.run("fetch https://example.com")
    assert r["ok"] is True
    con_steps = [t["step"].get("verb") for t in r["steps"]]
    assert "web_fetch" in con_steps


def test_learning_changes_arbitration(tmp_path, monkeypatch):
    monkeypatch.setattr(mem, "DB", tmp_path / "mem.db")
    assert mem.best_backend("edge-site", ["obscura", "cloak"]) == "obscura"
    for _ in range(3):
        mem.log_site("edge-site", "cloak", True)
    assert mem.best_backend("edge-site", ["obscura", "cloak"]) == "cloak"


def test_single_sample_does_not_overrule(tmp_path, monkeypatch):
    monkeypatch.setattr(mem, "DB", tmp_path / "mem.db")
    mem.log_site("thin-site", "cloak", True)  # only 1 sample
    assert mem.best_backend("thin-site", ["obscura", "cloak"]) == "obscura"


def test_doctor_shape():
    from elixir.probes import doctor_all

    names = {p.name for p in doctor_all()}
    assert {"wigolo", "obscura", "cloak", "cua", "agent-reach", "apps", "judge"} <= names
    for p in doctor_all():
        assert p.status in ("ok", "warn", "off", "error")
