# -*- coding: utf-8 -*-
"""Elixir production gates: policy, secrets, accounting, survival."""

from elixir import autopilot, spend
from elixir.log import scrub


def test_credentials_never_auto():
    plans = [autopilot.plan_for("agent-reach", "warn", "login needed")]
    assert plans[0]["mode"] == "ask"
    assert plans[0]["kind"] == "login"


def test_unknown_auto_fix():
    r = autopilot.run_auto("nope_nothing")
    assert r["ok"] is False


def test_scrub_removes_key():
    assert scrub({"x-api-key": "sk-nry-SECRET"}) == {"x-api-key": "***"}
    assert scrub("prefix sk-nry-abc suffix") == "***key***"
    assert scrub({"a": {"token": "x"}}) == {"a": {"token": "***"}}


def test_spend_cap_blocks(tmp_path, monkeypatch):
    import elixir.config as cfg

    monkeypatch.setattr(cfg, "SPEND_LOG", tmp_path / "sp.jsonl")
    monkeypatch.setattr(spend, "SPEND_LOG", tmp_path / "sp.jsonl")
    monkeypatch.setattr(spend, "SPEND_CAP_IDR", 100.0)
    assert spend.allowed() is True
    spend.record("m", 100000, 100000, 10.0, 10.0)
    assert spend.allowed() is False


def test_seed_sticky_and_rotates():
    from elixir.harness import rotate_seed, seed_for

    a = seed_for("unit-site-xyz")
    b = seed_for("unit-site-xyz")
    assert a == b
    c = rotate_seed("unit-site-xyz")
    assert isinstance(c, str) and len(c) > 0


def test_seat_acquire_release(tmp_path, monkeypatch):
    import elixir.harness as h

    monkeypatch.setattr(h, "SEAT_LOCK", tmp_path / "seat.lock")
    h.acquire_seat(timeout=5)
    assert (tmp_path / "seat.lock").exists()
    h.release_seat()
    assert not (tmp_path / "seat.lock").exists()


def test_stale_seat_reclaimed(tmp_path, monkeypatch):
    import os
    import time

    import elixir.harness as h

    lock = tmp_path / "seat.lock"
    lock.write_text("99999")
    old = time.time() - 400
    os.utime(lock, (old, old))
    monkeypatch.setattr(h, "SEAT_LOCK", lock)
    h.acquire_seat(timeout=5)  # must not block on stale lock
    h.release_seat()


def test_judge_shape():
    from elixir import judge

    r = judge.decide("fetch https://example.com")
    assert r["ok"] is True
    assert "calls" in r and "confidence" in r


def test_config_defaults():
    import elixir.config as cfg

    assert cfg.MAX_TOKENS > 0
    assert "agent-reach" in cfg.PINS
    assert cfg.SEAT_TIMEOUT > 0


def test_probe_check_handles_reexported_callables():
    """cloakbrowser.launch is a *function* re-exported by the package, not a
    submodule. Checking it as a module raised ImportError and made a fully
    installed cloak report `off  pip install cloakbrowser` in `elixir doctor`.
    """
    from elixir import probes

    assert probes._exports("re", "match") is True        # re-exported callable
    assert probes._importable("re.match") is False       # ...not a module
    assert probes._exports("re", "no_such_attr") is False
    assert probes._importable("elixir_no_such_module") is False


def test_off_probe_separates_uninstalled_from_not_on_path():
    """`cua` and `apps` both read `off  pip install ...` on a box where both
    were installed: pip had put the launchers in the user Scripts directory,
    which is not on PATH. Telling people to reinstall fixes nothing."""
    from elixir import probes

    p = probes._missing("tier", "elixir-no-such-dist", "nope",
                        "pip install nope")
    assert p.status == "off"
    assert p.message == "pip install nope"          # genuinely absent

    p = probes._missing("tier", "pytest", "pytest", "pip install pytest")
    assert p.status == "off"
    assert "not on PATH" in p.message               # installed, misplaced
    assert "pip install pytest" not in p.message    # never: it is present
    # the directory must be where pip really lands, not site.USER_BASE with
    # "Scripts" bolted on -- that is a version-less path on Windows and
    # does not exist (it reads .../Roaming/Python/Scripts, the real one is
    # .../Roaming/Python/Python313/Scripts).
    import os
    import sysconfig

    scheme = "nt_user" if os.name == "nt" else "posix_user"
    assert sysconfig.get_path("scripts", scheme) in p.message
