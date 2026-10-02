# -*- coding: utf-8 -*-
"""Security regressions: injection, CSRF/auth, path traversal, spend cap.

Every test here locks in a bug that actually existed in v0.1.0:
  * router.search passed user query to cmd.exe via shell=True
  * ui accepted text/plain POST from any origin (CSRF, no token)
  * /file served anything under DATA_DIR via a startswith() prefix check
  * _bynara_text trusted callers to enforce the spend cap
"""
from __future__ import annotations

import json
import shutil
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from elixir import router, ui

requires_npx = pytest.mark.skipif(shutil.which("npx") is None,
                                  reason="npx (Node.js) not on PATH")


# --------------------------------------------------------------------------
# 1. command injection in router.search
# --------------------------------------------------------------------------
@requires_npx
def test_search_argv_keeps_metacharacters_literal():
    q = "evil&whoami|calc >x"
    argv = router.search_argv(q)
    assert argv is not None
    assert argv[2].startswith("wigolo@")      # version pinned, not floating
    assert argv[4] == q                       # one element, never re-parsed
    assert sum(1 for a in argv if a == q) == 1


@requires_npx
def test_search_argv_never_enables_shell(monkeypatch):
    seen: dict = {}

    class _R:
        returncode = 1
        stdout = ""
        stderr = "boom"

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return _R()

    monkeypatch.setattr(router.subprocess, "run", fake_run)
    router.search("x&y")
    assert seen["cmd"][4] == "x&y"
    assert seen["kw"].get("shell", False) is False
    # absolute npx path -> CreateProcess finds npx.CMD without a shell
    assert seen["cmd"][0] == shutil.which("npx")


@requires_npx
def test_npx_argv_is_absolute():
    argv = router.npx_argv("pkg", "--version")
    assert argv is not None
    assert argv[0] == shutil.which("npx")


# --------------------------------------------------------------------------
# 2. URL scheme / SSRF guards
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    "file:///C:/Windows/System32/drivers/etc/hosts",
    "ftp://example.com/x",
    "javascript:alert(1)",
    "data:text/html,<b>x",
    "gopher://x",
    "",
])
def test_validate_url_blocks_dangerous_schemes(bad):
    assert router.validate_url(bad), f"{bad!r} must be refused"


def test_validate_url_blocks_cloud_metadata():
    assert router.validate_url("http://169.254.169.254/latest/meta-data/")
    assert router.validate_url("https://metadata.google.internal/computeMetadata/v1/")


def test_validate_url_allows_normal_traffic():
    assert router.validate_url("https://example.com/docs") is None
    assert router.validate_url("http://127.0.0.1:5000/health") is None


# --------------------------------------------------------------------------
# 3. artifact path containment
# --------------------------------------------------------------------------
def test_artifact_traversal_blocked(tmp_path, monkeypatch):
    art = tmp_path / "artifacts"
    art.mkdir()
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / ".elixir_state.json").write_text("{}")
    monkeypatch.setattr(ui, "ARTIFACTS_DIR", art)
    for rel in ("../.env", "..\\.env", "../.elixir_state.json",
                "sub/../../.env", "../../etc/passwd"):
        assert ui._resolve_artifact(rel) is None, rel


def test_artifact_sibling_prefix_blocked(tmp_path, monkeypatch):
    """startswith() containment let artifacts_evil/ pass. commonpath() does not."""
    (tmp_path / "artifacts").mkdir()
    evil = tmp_path / "artifacts_evil"
    evil.mkdir()
    (evil / "x.md").write_text("leak")
    monkeypatch.setattr(ui, "ARTIFACTS_DIR", tmp_path / "artifacts")
    assert ui._resolve_artifact("../artifacts_evil/x.md") is None


def test_artifact_denied_suffixes_blocked(tmp_path, monkeypatch):
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "app.env").write_text("K=1")
    (art / "log.jsonl").write_text("x")
    (art / ".elixir_state.json").write_text("{}")
    monkeypatch.setattr(ui, "ARTIFACTS_DIR", art)
    assert ui._resolve_artifact("app.env") is None
    assert ui._resolve_artifact("log.jsonl") is None
    assert ui._resolve_artifact(".elixir_state.json") is None


def test_artifact_inside_allowed(tmp_path, monkeypatch):
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "example.com.md").write_text("# hi")
    monkeypatch.setattr(ui, "ARTIFACTS_DIR", art)
    assert ui._resolve_artifact("example.com.md") == str(art / "example.com.md")


# --------------------------------------------------------------------------
# 4. HTTP surface: token, Origin, Host, content-type, body size
# --------------------------------------------------------------------------
def _raw(port, method, path, headers=None, body=b"", host=None,
         content_length=None):
    """Send a hand-built request so we can forge Host/Origin/Content-Type."""
    headers = dict(headers or {})
    lines = [f"{method} {path} HTTP/1.1",
             f"Host: {host or '127.0.0.1:%d' % port}",
             "Connection: close"]
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    cl = len(body) if content_length is None else content_length
    if cl:
        lines.append(f"Content-Length: {cl}")
    payload = ("\r\n".join(lines) + "\r\n\r\n").encode() + body
    with socket.create_connection(("127.0.0.1", port), timeout=20) as s:
        s.sendall(payload)
        data = b""
        while True:
            chunk = s.recv(8192)
            if not chunk:
                break
            data += chunk
    head, _, bdy = data.partition(b"\r\n\r\n")
    status = int(head.split(b" ", 2)[1])
    return status, bdy, head


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


@pytest.fixture()
def studio(monkeypatch):
    """Run the real handler on a free port, without kicking off real work."""
    monkeypatch.setattr(ui, "_work", lambda rid, task: None)
    monkeypatch.setattr(ui, "_runs", {})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], ui
    httpd.shutdown()
    httpd.server_close()


def test_page_hands_out_token_without_cors(studio):
    port, u = studio
    code, body, headers = _get(f"http://127.0.0.1:{port}/")
    assert code == 200
    assert u._TOKEN.encode() in body
    # if we ever leaked ACAO, a foreign page could read the token back
    assert "access-control-allow-origin" not in {k.lower() for k in headers}


def test_bootstrap_page_refuses_rebound_host(studio):
    """evil.com -> 127.0.0.1 would make our page same-origin with the attacker."""
    port, u = studio
    code, _, _ = _raw(port, "GET", "/", host="evil.example:8765")
    assert code == 403
    code, _, _ = _raw(port, "GET", "/", host="127.0.0.1:%d" % port)
    assert code == 200


def test_api_get_requires_token(studio):
    port, u = studio
    code, body, _ = _get(f"http://127.0.0.1:{port}/api/runs/r1")
    assert code == 403 and b"token" in body
    code, body, _ = _get(f"http://127.0.0.1:{port}/api/runs/r1?t={u._TOKEN}")
    assert code == 200


def test_post_without_token_is_rejected(studio):
    """v0.1.0 answered 200 here: any page, text/plain, no secret needed."""
    port, u = studio
    code, _, _ = _raw(port, "POST", "/api/run",
                      {"Content-Type": "text/plain"},
                      json.dumps({"task": "hi"}).encode())
    assert code == 403


def test_post_cross_origin_is_rejected(studio):
    port, u = studio
    code, _, _ = _raw(port, "POST", "/api/run",
                      {"Content-Type": "application/json",
                       "Origin": "https://evil.example",
                       "X-Elixir-Token": u._TOKEN},
                      json.dumps({"task": "hi"}).encode())
    assert code == 403


def test_post_rebound_host_is_rejected(studio):
    port, u = studio
    code, _, _ = _raw(port, "POST", "/api/run",
                      {"Content-Type": "application/json",
                       "X-Elixir-Token": u._TOKEN},
                      json.dumps({"task": "hi"}).encode(),
                      host="evil.example:8765")
    assert code == 403


def test_post_requires_json_content_type(studio):
    port, u = studio
    code, _, _ = _raw(port, "POST", "/api/run",
                      {"Content-Type": "text/plain",
                       "X-Elixir-Token": u._TOKEN},
                      json.dumps({"task": "hi"}).encode())
    assert code == 415


def test_post_valid_request_accepted(studio):
    port, u = studio
    code, body, _ = _raw(port, "POST", "/api/run",
                         {"Content-Type": "application/json",
                          "X-Elixir-Token": u._TOKEN},
                         json.dumps({"task": "hello"}).encode())
    assert code == 200
    assert json.loads(body)["id"].startswith("r")


def test_post_garbage_body_is_400(studio):
    port, u = studio
    code, _, _ = _raw(port, "POST", "/api/run",
                      {"Content-Type": "application/json",
                       "X-Elixir-Token": u._TOKEN},
                      b"not json at all")
    assert code == 400


def test_post_oversized_body_is_413(studio):
    port, u = studio
    code, _, _ = _raw(port, "POST", "/api/run",
                      {"Content-Type": "application/json",
                       "X-Elixir-Token": u._TOKEN},
                      b"{}", content_length=ui.MAX_BODY + 1)
    assert code == 413


def test_file_route_traversal_and_denied(studio, tmp_path, monkeypatch):
    port, u = studio
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "hello.md").write_text("# hi")
    (tmp_path / ".env").write_text("KEY=1")
    monkeypatch.setattr(u, "ARTIFACTS_DIR", art)
    tok = u._TOKEN

    for rel in ("../.env", "sub/../../.env", "..\\..\\.env"):
        q = urllib.parse.quote(rel, safe="")
        code, _, _ = _raw(port, "GET", f"/file?f={q}&t={tok}")
        assert code == 404, rel

    code, body, _ = _raw(port, "GET", f"/file?f=hello.md&t={tok}")
    assert code == 200 and b"# hi" in body

    code, _, _ = _raw(port, "GET", "/file?f=hello.md")
    assert code == 403


# --------------------------------------------------------------------------
# 5. run store stays bounded
# --------------------------------------------------------------------------
def test_run_ttl_prunes_finished_runs(monkeypatch):
    monkeypatch.setattr(ui, "_runs", {})
    monkeypatch.setattr(ui, "RUN_TTL", 10)
    now = time.time()
    with ui._lock:
        ui._runs["old"] = {"log": "x", "done": True, "ts": now - 100}
        ui._runs["live"] = {"log": "x", "done": False, "ts": now - 100}
        ui._runs["new"] = {"log": "x", "done": True, "ts": now}
    assert ui._prune_runs(now) == 1
    assert set(ui._runs) == {"live", "new"}


def test_run_store_is_capped(monkeypatch):
    monkeypatch.setattr(ui, "_runs", {})
    now = time.time()
    with ui._lock:
        for i in range(ui.MAX_RUNS + 5):
            ui._runs[f"a{i}"] = {"log": "x", "done": True, "ts": now}
    dropped = ui._prune_runs(now)
    assert dropped == 5
    assert len(ui._runs) == ui.MAX_RUNS


# --------------------------------------------------------------------------
# 6. spend cap is enforced at the boundary, not by callers
# --------------------------------------------------------------------------
def test_spend_cap_blocks_bynara_text(monkeypatch):
    from elixir import buddy, spend

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("network call attempted past the cap")

    monkeypatch.setattr(buddy, "_bynara_key", lambda: "test-key")
    monkeypatch.setattr(spend, "allowed", lambda *a, **k: False)
    monkeypatch.setattr("urllib.request.urlopen", boom)

    with pytest.raises(RuntimeError, match="spend cap"):
        buddy._bynara_text("hello")
    assert calls["n"] == 0


def test_spend_cap_blocks_bynara_vision(monkeypatch):
    from elixir import buddy, spend

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("network call attempted past the cap")

    monkeypatch.setattr(buddy, "_bynara_key", lambda: "test-key")
    monkeypatch.setattr(spend, "allowed", lambda *a, **k: False)
    monkeypatch.setattr("urllib.request.urlopen", boom)

    with pytest.raises(RuntimeError, match="spend cap"):
        buddy._bynara_vision("what is this", "aGVsbG8=")
    assert calls["n"] == 0


# --------------------------------------------------------------------------
# 7. autopilot: installs ask, approvals actually act, no machine-specific code
# --------------------------------------------------------------------------
def test_cloak_update_requires_approval():
    from elixir import autopilot

    p = autopilot.plan_for("cloak", "warn", "stale")
    assert p["mode"] == "ask"
    assert p["kind"] == "install"


def _fake_verify(monkeypatch):
    from elixir import probes
    monkeypatch.setattr(probes, "doctor_all", lambda: [])


def test_approved_ask_plan_actually_runs(monkeypatch):
    from elixir import autopilot

    _fake_verify(monkeypatch)
    ran: list = []
    monkeypatch.setattr(autopilot, "diagnose", lambda: [
        {"tier": "judge", "fix": "pip install cactus-needle", "mode": "ask",
         "kind": "install", "run": "install_judge"}])
    monkeypatch.setattr(autopilot, "run_auto",
                        lambda k: (ran.append(k), {"ok": True})[1])
    log = autopilot.autopilot(ask_fn=lambda q: True)["actions"]
    assert ran == ["install_judge"]
    assert log[0]["approved"] is True and log[0]["ok"] is True


def test_declined_ask_plan_runs_nothing(monkeypatch):
    from elixir import autopilot

    _fake_verify(monkeypatch)
    ran: list = []
    monkeypatch.setattr(autopilot, "diagnose", lambda: [
        {"tier": "judge", "fix": "pip install cactus-needle", "mode": "ask",
         "kind": "install", "run": "install_judge"}])
    monkeypatch.setattr(autopilot, "run_auto",
                        lambda k: (ran.append(k), {"ok": True})[1])
    log = autopilot.autopilot(ask_fn=lambda q: False)["actions"]
    assert ran == []
    assert log[0]["approved"] is False


def test_machine_specific_fix_removed():
    from elixir import autopilot

    # `schtasks /Run /TN VyuhaMountVHD` belonged to one laptop, not the project
    assert autopilot.run_auto("mount_e")["ok"] is False
