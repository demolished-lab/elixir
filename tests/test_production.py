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


def test_local_ollama_call_is_bounded_and_stays_warm(monkeypatch):
    """The local path sent neither `num_predict` nor `keep_alive`.

    So it ignored ELIXIR_MAX_TOKENS entirely (generating until EOS on a CPU
    that manages ~4 tok/s), and let Ollama evict the model after its default 5
    minutes -- the next call then paid a reload that measures in minutes here.
    """
    import json as _json

    import elixir.config as cfg
    from elixir import buddy

    seen: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"response": "ready"}'

    def fake(req, timeout=0):
        seen.update(_json.loads(req.data))
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    assert buddy._ollama_generate("some-model", "hi", ["aW1n"]) == "ready"
    assert seen["options"]["num_predict"] == cfg.MAX_TOKENS
    assert seen["keep_alive"] == cfg.OLLAMA_KEEP_ALIVE
    assert seen["images"] == ["aW1n"]


def test_warm_preloads_every_local_model(monkeypatch):
    from elixir import buddy
    import elixir.config as cfg

    loaded: list = []
    monkeypatch.setattr(
        buddy, "_ollama_generate",
        lambda model, prompt, images=None: loaded.append(model) or "ready")

    r = buddy.warm()
    assert r["ok"] is True
    assert set(r["models"]) == {cfg.TEXT_MODEL, cfg.VISION_MODEL}
    assert set(loaded) == {cfg.TEXT_MODEL, cfg.VISION_MODEL}


def test_warm_reports_an_absent_model_instead_of_raising(monkeypatch):
    """Warm-up runs on a background thread at Studio startup; a missing or
    unreachable model must show up as a status line, never as a crash."""
    from elixir import buddy

    def down(model, prompt, images=None):
        raise OSError("connection refused")

    monkeypatch.setattr(buddy, "_ollama_generate", down)
    r = buddy.warm()
    assert r["ok"] is False
    assert all(v.startswith("unavailable") for v in r["models"].values())


def test_doctor_all_probes_concurrently_and_keeps_order(monkeypatch):
    """All seven probes block on a subprocess or a live network call.

    In series `elixir doctor` cost the sum of the seven (~53s); the barrier
    below only opens when all seven are in flight at once, so a serial
    doctor_all fails this test rather than merely running slower.
    """
    import threading

    from elixir import probes

    names = ["wigolo", "obscura", "cloak", "cua", "agent-reach", "apps", "judge"]
    gate = threading.Barrier(len(names), timeout=30)

    def make(name):
        def probe():
            gate.wait()
            return probes.Probe(name, "ok", f"{name} ok", None)

        return probe

    for n in names:
        monkeypatch.setattr(probes, "probe_" + n.replace("-", "_"), make(n))

    out = probes.doctor_all()
    assert [p.name for p in out] == names       # stable, serial-looking order
    assert all(p.status == "ok" for p in out)
