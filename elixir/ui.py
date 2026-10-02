# -*- coding: utf-8 -*-
"""Elixir Studio: Manus-style local web UI. Stdlib only.

  python -m elixir.ui  ->  http://127.0.0.1:8765
"""
from __future__ import annotations
import base64
import html
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
_runs: dict = {}
_lock = threading.Lock()


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Elixir Studio</title><style>
*{box-sizing:border-box;font-family:'Segoe UI',system-ui,sans-serif}
body{margin:0;background:#f6f6f4;color:#1c1c1c;display:flex;height:100vh}
#rail{width:64px;background:#fff;border-right:1px solid #e5e5e0;display:flex;flex-direction:column;align-items:center;padding:12px 0;gap:14px}
#rail .dot{width:38px;height:38px;border-radius:10px;background:#f0efe9;display:flex;align-items:center;justify-content:center;font-size:18px}
#rail .dot.on{background:#1c1c1c;color:#fff}
#main{flex:1;overflow-y:auto;padding:28px 40px;max-width:1060px;margin:0 auto;width:100%}
h1.logo{font-size:44px;margin:6px 0 2px;letter-spacing:-1px}
.sub{color:#777;margin-bottom:20px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
.card{background:#fff;border:1px solid #e7e7e1;border-radius:14px;padding:18px;cursor:pointer}
.card:hover{border-color:#1c1c1c}
.card b{font-size:16px}.card p{color:#777;font-size:13px;margin:6px 0 0}
#box{background:#fff;border:1px solid #e0e0da;border-radius:16px;padding:14px 16px;margin-bottom:14px}
#task{width:100%;border:0;outline:0;font-size:16px;resize:none;background:transparent}
#row{display:flex;justify-content:flex-end;margin-top:8px}
#go{background:#1c1c1c;color:#fff;border:0;border-radius:50%;width:42px;height:42px;font-size:20px;cursor:pointer}
#tiers{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;font-size:12px}
.pill{background:#fff;border:1px solid #e2e2dc;border-radius:20px;padding:4px 12px}
.pill.ok{border-color:#3a9e5f}.pill.bad{border-color:#c04545}
#feed{background:#1c1c1c;color:#e8e8e8;border-radius:14px;padding:16px;font-family:Consolas,monospace;font-size:13px;white-space:pre-wrap;min-height:120px;max-height:300px;overflow-y:auto}
.sug{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
.sug div{background:#fff;border:1px solid #e7e7e1;border-radius:12px;padding:12px;font-size:13px;cursor:pointer}
#shots img{max-width:220px;border-radius:10px;margin:6px;border:1px solid #ddd}
</style></head><body>
<div id=rail><div class=dot on>&#10022;</div><div class=dot>&#9998;</div><div class=dot>&#9783;</div><div class=dot>&#9776;</div></div>
<div id=main>
<h1 class=logo>elixir</h1><div class=sub>Human-equal web entity &mdash; tell it anything.</div>
<div id=tiers>loading tiers&hellip;</div>
<div class=cards>
<div class=card onclick="fill('Build a summary of the top Hacker News story right now')"><b>&#128296; Browse &gt;</b><p>Search, read, and act on the live web</p></div>
<div class=card onclick="fill('What is on my screen right now?')"><b>&#9679; Buddy &gt;</b><p>See the screen, answer aloud</p></div>
</div>
<div id=box><textarea id=task rows=2 placeholder="Assign a task or type / for more"></textarea>
<div id=row><button id=go onclick="run()">&#8593;</button></div></div>
<div id=feed>idle — assign a task above.</div>
<div id=shots></div>
<div class=sug>
<div onclick="fill('Fetch https://example.com and summarize it')">Fetch a page and summarize it</div>
<div onclick="fill('Search Bilibili for AI tutorials')">Search Bilibili for AI tutorials</div>
<div onclick="fill('Check spend, memory, and tier health')">Report spend, memory, health</div>
</div></div>
<script>
function fill(t){document.getElementById('task').value=t;}
async function tiers(){const r=await fetch('/api/doctor');const j=await r.json();
document.getElementById('tiers').innerHTML=j.map(t=>`<span class="pill ${t.status=='ok'?'ok':'bad'}">${t.name}: ${t.status}</span>`).join('');}
async function run(){const task=document.getElementById('task').value.trim();if(!task)return;
const f=document.getElementById('feed');f.textContent='planning…\\n';
const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task})});
const {id}=await r.json();
const t=setInterval(async()=>{const s=await(await fetch('/api/runs/'+id)).json();
f.textContent=s.log;if(s.done){clearInterval(t);shots(s.shots||[]);tiers();}},900);}
function shots(s){document.getElementById('shots').innerHTML=s.map(p=>`<img src="/shot?f=${encodeURIComponent(p)}">`).join('');}
tiers();
</script></body></html>"""


def _shot_bytes(path):
    import os

    from .config import DATA_DIR

    full = os.path.abspath(path)
    if not full.startswith(str(DATA_DIR)):
        return None
    try:
        with open(full, "rb") as f:
            return f.read()
    except OSError:
        return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/":
            return self._send(PAGE, "text/html; charset=utf-8")
        if self.path == "/api/doctor":
            from .probes import doctor_all

            return self._send(json.dumps(
                [{"name": p.name, "status": p.status} for p in doctor_all()]))
        if self.path.startswith("/api/runs/"):
            rid = self.path.rsplit("/", 1)[-1]
            with _lock:
                r = _runs.get(rid, {"log": "unknown run", "done": True, "shots": []})
            return self._send(json.dumps(r))
        if self.path.startswith("/shot?"):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            img = _shot_bytes(q.get("f", [""])[0])
            if img:
                return self._send(img, "image/png")
            return self._send("nope", "text/plain", 404)
        if self.path.startswith("/file?"):
            import os

            from .config import DATA_DIR

            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            rel = q.get("f", [""])[0]
            full = os.path.abspath(os.path.join(str(DATA_DIR), rel))
            if not full.startswith(str(DATA_DIR)):
                return self._send("nope", "text/plain", 404)
            try:
                with open(full, "rb") as f:
                    raw = f.read()
            except OSError:
                return self._send("nope", "text/plain", 404)
            ctype = "application/pdf" if full.endswith(".pdf") else "text/markdown"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Disposition",
                             f"attachment; filename={os.path.basename(full)}")
            self.end_headers()
            self.wfile.write(raw)
            return
        return self._send("{}", "application/json", 404)

    def do_POST(self):
        if self.path == "/api/run":
            n = int(self.headers.get("Content-Length", 0))
            task = json.loads(self.rfile.read(n) or b"{}").get("task", "")
            rid = f"r{int(time.time() * 1000)}"
            with _lock:
                _runs[rid] = {"log": "planning…\n", "done": False, "shots": []}
            threading.Thread(target=_work, args=(rid, task), daemon=True).start()
            return self._send(json.dumps({"id": rid}))
        return self._send("{}", "application/json", 404)


def _say(run, text):
    with _lock:
        run["log"] += text + "\n"


def _work(rid, task):
    from . import brain, buddy, router
    from . import memory as mem

    def get():
        with _lock:
            return _runs[rid]

    try:
        run = get()
        _say(run, f"task: {task}")
        for i, step in enumerate(brain.decompose(task)):
            _say(run, f"[{i}] {step['verb']} {str(step.get('args'))[:100]}")
            if step["verb"] == "web_search":
                r = router.search(step["args"].get("query", task), 3)
                titles = [x.get("title", "?") for x in (r.get("results") or [])[:3]]
                _say(run, f"  -> {len(titles)} results: " + " | ".join(titles)[:200])
                mem.log_run(task, f"{i}:web_search", "wigolo", bool(titles), 0, 0.8)
            elif step["verb"] == "web_fetch":
                url = step["args"].get("url", "")
                saved = router.fetch_and_save(url, out_dir=".")
                _say(run, f"  -> {saved['chars']} chars "
                          f"<a href='/file?f={saved['path'].split(chr(92))[-1]}' "
                          f"style='color:#8ab4ff'>download .md</a>")
                mem.log_run(task, f"{i}:web_fetch", "fetch",
                            saved["chars"] > 200, 0, 0.7)
            elif step["verb"] == "stealth_act":
                url = step["args"].get("url", "")
                r = router.act(url, screenshot=f"ui_{rid}_3.png")
                pdf = router.act_pdf(url, f"ui_{rid}.pdf")
                _say(run, f"  -> {r.get('title')} (3-frame flipbook + "
                          f"<a href='/file?f=ui_{rid}.pdf' style='color:#8ab4ff'>PDF</a>)")
                mem.log_run(task, f"{i}:stealth_act", "cloak", bool(r.get("title")), 0, 0.8)
                with _lock:
                    for fp in r.get("frames", []) or [f"ui_{rid}_3.png"]:
                        import os as _os
                        run["shots"].append(_os.path.basename(fp))
            elif step["verb"] == "buddy_ask":
                r = buddy.ask(step["args"].get("question", task), shot=f"buddy_{rid}.png")
                _say(run, f"  -> [{r.get('via')}] " + str(r.get("answer"))[:300])
                mem.log_run(task, f"{i}:buddy", str(r.get("via")), bool(r.get("ok")), 0, 0.7)
                with _lock:
                    run["shots"].append(f"buddy_{rid}.png")
            else:
                _say(run, f"  -> manual: elixir {step['verb']} (see CLI)")
        with _lock:
            run["done"] = True
            run["log"] += "done.\n"
    except Exception as e:  # noqa: BLE001 — feed shows errors, never hangs
        with _lock:
            rr = _runs.get(rid)
            if rr:
                rr["log"] += f"error: {e}\n"
                rr["done"] = True


def serve(port: int = PORT) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()