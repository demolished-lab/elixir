# -*- coding: utf-8 -*-
"""Elixir CLI: doctor/search/fetch/act."""
import argparse
import json

from .probes import doctor_all
from . import router


def main() -> None:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="elixir")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="probe wigolo/obscura/cloak/cua for real")

    p = sub.add_parser("search", help="wigolo search")
    p.add_argument("query")
    p.add_argument("--max-results", type=int, default=5)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("fetch", help="obscura -> cloak escalation")
    p.add_argument("url")
    p.add_argument("--dump", default="markdown")

    p = sub.add_parser("act", help="cloak humanize goto/fill/screenshot")
    p.add_argument("url")
    p.add_argument("--screenshot", default=None)
    p.add_argument("--fill", default=None, help='JSON {"selector":"value"}')

    sub.add_parser("harness-check", help="seat + fingerprint pool + decay signals")
    sub.add_parser("fresh", help="decay check + auto cloakbrowser update")

    p = sub.add_parser("os", help="cua-driver OS hands")
    p.add_argument("action", choices=["screen", "desktop", "windows", "click", "type", "hotkey"])
    p.add_argument("--x", type=int, default=None)
    p.add_argument("--y", type=int, default=None)
    p.add_argument("--text", default=None)
    p.add_argument("--keys", default=None, help="comma-separated, e.g. ctrl,c")
    p.add_argument("--out", default="desktop.png")

    p = sub.add_parser("social", help="agent-reach social tier status/route")
    p.add_argument("platform", nargs="?", default=None)

    p = sub.add_parser("apps", help="CLI-Anything app harnesses")
    p.add_argument("action", choices=["search", "info", "install", "launch"])
    p.add_argument("name", nargs="?", default=None)
    p.add_argument("extra", nargs=argparse.REMAINDER)

    p = sub.add_parser("buddy", help="voice buddy: see screen, answer aloud")
    p.add_argument("action", choices=["say", "ask", "listen"], nargs="?", default="listen")
    p.add_argument("text", nargs="?", default=None)

    p = sub.add_parser("decide", help="Needle instant intent router")
    p.add_argument("request")

    p = sub.add_parser("run", help="brain: plan -> act -> verify with memory")
    p.add_argument("task")
    p.add_argument("--record", action="store_true", help="trajectory evidence under runs/")
    p.add_argument("--video", action="store_true", help="also capture session mp4 (needs ffmpeg)")
    p = sub.add_parser("memory", help="learned site stats")
    p.add_argument("site", nargs="?", default=None)

    sub.add_parser("health", help="machine-readable health for monitoring")
    sub.add_parser("versions", help="pinned vs installed upstream versions")
    sub.add_parser("spend", help="metered spend this month vs cap")

    p = sub.add_parser("autopilot", help="self-heal all tiers, ask approval for risky fixes")
    p.add_argument("--yes", action="store_true", help="auto-approve ask-tier (still never credentials)")

    a = ap.parse_args()
    if a.cmd == "doctor":
        for pr in doctor_all():
            print(f"{pr.status:5} {pr.name:8} {pr.message[:160]}")
    elif a.cmd == "search":
        res = router.search(a.query, a.max_results)
        print(json.dumps(res, ensure_ascii=False, indent=2)[:6000] if a.json else str(res)[:4000])
    elif a.cmd == "fetch":
        import sys

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(router.fetch(a.url, a.dump)[:6000])
    elif a.cmd == "act":
        fill = json.loads(a.fill) if a.fill else None
        print(json.dumps(router.act(a.url, a.screenshot, fill), ensure_ascii=False, indent=2))
    elif a.cmd == "harness-check":
        from .harness import SEAT_LOCK, seed_for, cloak_version

        print(json.dumps({
            "seat_locked": SEAT_LOCK.exists(),
            "cloak": cloak_version(),
            "sample_seed_example_com": seed_for("example.com"),
        }, indent=2))
    elif a.cmd == "fresh":
        from .harness import ensure_fresh

        print(json.dumps(ensure_fresh(), ensure_ascii=False, indent=2))
    elif a.cmd == "os":
        from . import os_hands

        if a.action == "screen":
            print(json.dumps(os_hands.screen(), indent=2))
        elif a.action == "desktop":
            print(json.dumps(os_hands.desktop(a.out), indent=2)[:800])
        elif a.action == "windows":
            r = os_hands.windows()
            s = json.dumps(r, ensure_ascii=False)[:3000]
            print(s)
        elif a.action == "click":
            print(json.dumps(os_hands.click_desktop(a.x, a.y), indent=2))
        elif a.action == "type":
            print(json.dumps(os_hands.type_text(a.text or ""), indent=2))
        elif a.action == "hotkey":
            print(json.dumps(os_hands.hotkey(*a.keys.split(",")), indent=2))
    elif a.cmd == "social":
        from . import social

        if a.platform:
            print(json.dumps(social.route(a.platform), ensure_ascii=False, indent=2))
        else:
            s = social.status()
            chs = s.get("channels", {})
            ok = [k for k, v in chs.items() if v["status"] == "ok"]
            need = [k for k, v in chs.items() if v["status"] != "ok"]
            print(json.dumps({"score": s.get("score"), "ok": ok,
                              "need_login_or_setup": need}, ensure_ascii=False, indent=2))
    elif a.cmd == "apps":
        from . import apps

        if a.action == "search":
            print(apps.search(a.name or ""))
        elif a.action == "info":
            print(apps.info(a.name or ""))
        elif a.action == "install":
            print(apps.install(a.name or ""))
        elif a.action == "launch":
            print(apps.launch(a.name or "", [x for x in (a.extra or []) if x != "--"]))
    elif a.cmd == "buddy":
        from . import buddy

        if a.action == "say":
            print(json.dumps(buddy.say(a.text or "Elixir online"), indent=2))
        elif a.action == "ask":
            r = buddy.ask(a.text or "What do you see on my screen?")
            print(json.dumps(r, ensure_ascii=False, indent=2)[:3000])
            if r.get("answer"):
                buddy.say(r["answer"])
        elif a.action == "listen":
            buddy.listen_loop()
    elif a.cmd == "decide":
        from . import judge

        print(json.dumps(judge.decide(a.request), ensure_ascii=False, indent=2))
    elif a.cmd == "run":
        from . import brain

        rec = None
        if a.record or a.video:
            from . import record as _rec

            if a.video:
                _rec.ensure_ffmpeg()
            rec = _rec.start("task", video=a.video)
        r = brain.run(a.task)
        if rec:
            from . import record as _rec

            _rec.stop()
            r["evidence"] = rec["dir"]
        print(json.dumps({k: v for k, v in r.items() if k != "steps"},
                         ensure_ascii=False, indent=2)[:2000])
        for t in r["steps"]:
            o = t["outcome"]
            print(f"- {t['step'].get('verb')}: ok={o['ok']} tier={o['tier']} conf={o['conf']}")
    elif a.cmd == "memory":
        from . import memory as _mem

        print(json.dumps(_mem.stats(a.site), ensure_ascii=False, indent=2))
    elif a.cmd == "health":
        import time

        probes = doctor_all()
        print(json.dumps({
            "ts": time.time(),
            "healthy": all(p.status == "ok" for p in probes),
            "tiers": {p.name: {"status": p.status, "backend": p.backend} for p in probes},
        }, indent=2))
    elif a.cmd == "versions":
        import os

        from .config import PINS
        from .probes import _run

        obscura_exe = os.path.expanduser("~/.obscura/obscura.exe")
        out = {}
        checks = {"wigolo": ["npx", "-y", "wigolo", "--version"],
                  "obscura": [obscura_exe, "--version"]}
        for name, pin in PINS.items():
            if name in checks:
                ok, ver = _run(checks[name])
                out[name] = {"pinned": pin, "found": ver[:60], "match": pin in ver}
            else:
                try:
                    m = __import__("importlib.metadata", fromlist=["x"]).version(name)
                    out[name] = {"pinned": pin, "found": m, "match": pin in m}
                except Exception:  # noqa: BLE001
                    out[name] = {"pinned": pin, "found": "missing", "match": False}
        print(json.dumps(out, indent=2))
    elif a.cmd == "spend":
        from . import spend as _spend
        from .config import SPEND_CAP_IDR

        print(json.dumps({"spent_idr": round(_spend.spent_this_month(), 2),
                          "cap_idr": SPEND_CAP_IDR}, indent=2))
    elif a.cmd == "autopilot":
        from . import autopilot as ap

        if a.yes:
            def approve(text: str, plan: dict | None = None) -> bool:
                return True
            # --yes approves installs only; credentials/logins always ask
            orig = ap.autopilot
            def ask_fn(t: str) -> bool:
                low = t.lower()
                if "login" in low or "cookie" in low or "credential" in low:
                    try:
                        return input(f"APPROVE: {t} ").strip().lower().startswith("y")
                    except (EOFError, KeyboardInterrupt):
                        return False
                return True
            res = orig(ask_fn=ask_fn)
        else:
            res = ap.autopilot()
        print(json.dumps(res, ensure_ascii=False, indent=2))
