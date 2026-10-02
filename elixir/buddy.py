# -*- coding: utf-8 -*-
"""Elixir buddy (Clicky pattern, Windows-native, $0): see screen, answer aloud.

Loop: screenshot (cua-driver) + question -> local Ollama vision (minicpm5)
-> text answer -> Windows SAPI speech. No cloud, no meter.
Voice-in (mic STT) is future work (no mic deps on this box); input is typed.
Pointing: answer may name window titles; physical cursor-pointing stays a
manual `elixir os click` until a pure-move tool exists in cua-driver.
"""
from __future__ import annotations
import base64
import json
import subprocess
import urllib.request

from . import config as _cfg

OLLAMA = _cfg.OLLAMA_URL
VISION_MODELS = [_cfg.VISION_MODEL, "openbmb/minicpm5:latest"]
TEXT_MODEL = _cfg.TEXT_MODEL
BYNARA_URL = "https://router.bynara.id"
BYNARA_KEY_FILE = _cfg.BYNARA_KEY_FILE
BYNARA_VISION_MODEL = _cfg.CLOUD_VISION_MODEL
BYNARA_MAX_TOKENS = _cfg.MAX_TOKENS


def _bynara_key() -> str | None:
    import re

    try:
        with open(BYNARA_KEY_FILE, encoding="utf-8") as f:
            return re.search(r'"([^"]+)"', f.read()).group(1)
    except (OSError, AttributeError):
        return None


def _bynara_text(prompt: str, model: str = "agnes-2.5-flash") -> str:
    """Metered text fallback. Spend-guarded by the caller."""
    key = _bynara_key()
    if not key:
        raise RuntimeError("bynara key file unreadable")
    payload = {"model": model, "max_tokens": 300,
               "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        f"{BYNARA_URL}/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())
    text = "".join(b.get("text", "") for b in body.get("content", [])).strip()
    try:
        from . import spend as _spend

        u = body.get("usage", {})
        _spend.record(model, u.get("input_tokens", 0), u.get("output_tokens", 0), 0.1, 0.2)
    except Exception:  # noqa: BLE001
        pass
    return text


def _bynara_vision(question: str, img_b64: str) -> str:
    """Cloud eyes via bynara router (metered PAYG, pennies per ask)."""
    key = _bynara_key()
    if not key:
        raise RuntimeError("bynara key file unreadable")
    payload = {
        "model": BYNARA_VISION_MODEL,
        "max_tokens": BYNARA_MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": f"{question} Answer in 2-3 sentences."},
                ],
            }
        ],
    }
    req = urllib.request.Request(
        f"{BYNARA_URL}/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())
    text = "".join(b.get("text", "") for b in body.get("content", [])).strip()
    try:
        from . import spend as _spend

        u = body.get("usage", {})
        _spend.record(BYNARA_VISION_MODEL, u.get("input_tokens", 0),
                      u.get("output_tokens", 0), 0.1, 0.2)
    except Exception:  # noqa: BLE001 — accounting must never block answers
        pass
    return text


def _local_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=15) as resp:
            return [m["name"] for m in json.loads(resp.read()).get("models", [])]
    except Exception:  # noqa: BLE001
        return []


def say(text: str, rate: int = 0) -> dict:
    """Speak via built-in Windows SAPI. No deps, no network."""
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.Rate={int(rate)};"
        "$s.Speak([Console]::In.ReadToEnd())"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            input=text[:2000], capture_output=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        return {"ok": r.returncode == 0, "spoken_chars": len(text)}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e)[:200]}


def _ollama_generate(model: str, prompt: str, images: list[str] | None = None) -> str:
    payload: dict = {"model": model, "prompt": prompt, "stream": False}
    if images:
        payload["images"] = images
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read()).get("response", "").strip()


def ask(question: str, shot: str = "buddy.png") -> dict:
    """Screenshot context + local answer. Degrades honestly without vision."""
    import os as _os

    from . import os_hands

    shot = _os.path.abspath(shot)
    snap = os_hands.desktop(shot, max_dim=1024)
    if not snap.get("ok"):
        return {"ok": False, "error": f"screenshot failed: {snap}"}
    with open(shot, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    names = _local_models()
    for vm in VISION_MODELS:
        if not any(vm in n for n in names):
            continue
        try:
            answer = _ollama_generate(
                vm,
                f"You see the user's Windows screen. Answer briefly (2-3 sentences): {question}",
                [img],
            )
            return {"ok": True, "answer": answer, "via": vm, "shot": shot}
        except Exception:  # noqa: BLE001 — try next vision model, then cloud
            continue
    try:
        from . import spend as _spend

        if not _spend.allowed():
            raise RuntimeError(f"spend cap reached ({_spend.spent_this_month():.1f} IDR)")
        answer = _bynara_vision(question, img)
        return {"ok": True, "answer": answer, "via": f"bynara:{BYNARA_VISION_MODEL}",
                "shot": shot, "note": "metered pennies, local vision pending"}
    except Exception as e:  # noqa: BLE001 — fall through to text context
        cloud_err = str(e)[:160]
    wins = None
    try:
        wins = os_hands.windows()
    except Exception:  # noqa: BLE001
        wins = None
    titles = ""
    if wins:
        try:
            data = wins.get("data", {})
            items = data.get("windows") or data.get("_legacy_windows") or []
            titles = ", ".join(w.get("title", "?")[:60] for w in items[:8])
        except Exception:  # noqa: BLE001
            pass
    try:
        answer = _ollama_generate(
            TEXT_MODEL,
            f"Open windows: {titles}. User asks: {question}. Answer briefly.",
        )
        return {"ok": True, "answer": answer, "via": TEXT_MODEL,
                "degraded": f"local text-only; cloud vision failed: {cloud_err}"}
    except Exception as e2:  # noqa: BLE001
        return {"ok": False, "error": f"ollama down: {e2}"[:200]}


def listen_loop() -> None:
    print("buddy listening (typed input; empty line quits). Screen is visible to me.")
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        r = ask(q)
        ans = r.get("answer", r.get("error", "silent failure"))
        print(f"buddy [{r.get('via', '?')}]> {ans}")
        say(ans)
