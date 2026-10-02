# Elixir — human-equal web entity
Standalone router: `wigolo -> obscura -> cloak -> cua-driver`, read + act.

Demo video kept local-only by choice (`take_full.mp4`, not shipped).

## Install
```powershell
git clone https://github.com/demolished-lab/elixir.git
cd elixir
pip install -e ".[dev]"              # elixir cli + pytest/pyflakes

# tier 1 — search/memory (npm, free)
npx -y wigolo@0.2.1 --version

# tier 2 — obscura fast render. NOT on PyPI: the package called `obscura`
# there is an unrelated Argon2 file-encryptor. Get the Rust binary:
#   https://github.com/h4ckf0r0day/obscura/releases -> obscura-x86_64-windows.zip
# extract obscura.exe + obscura-worker.exe into ~/.obscura/  (0.2.2 = pinned)
~/.obscura/obscura.exe --version

# tier 3 — stealth browser (free, 1 session)
pip install cloakbrowser==0.5.11
python -m cloakbrowser install       # downloads the 535 MB Chromium once

# tier 4 — OS hands + desktop apps
pip install cua-driver==0.32.0
cua-driver serve --socket "\\.\pipe\cua-driver"   # one daemon per boot

# tiers 5-7 — social, app harnesses, intent router
pip install https://github.com/Panniantong/agent-reach/archive/main.zip
pip install cli-anything-hub==0.4.1
pip install cactus-needle==3.0.6

# local brains for the voice buddy (no cloud, no spend)
ollama pull qwen3:4b-instruct-2507-q4_K_M   # text
ollama pull qwen2.5vl:3b                    # vision

python -m elixir doctor              # every tier must read `ok`
python -m elixir health              # {"healthy": true}
```

If `doctor` reports `cua`/`apps` off with the tools installed, your user
Scripts dir isn't on PATH — pip put the launchers in
`%APPDATA%\Python\Python313\Scripts`, add it to PATH and open a new shell.

`elixir versions` checks all seven against their pins; if it reports drift
you upgraded something on purpose, so bump `PINS` in `elixir/config.py`.

## Use
```powershell
python -m elixir doctor              # probe every tier for real
python -m elixir search "LLM framework compare" --json
python -m elixir fetch https://example.com --dump markdown
python -m elixir act https://browserscan.net/bot-detection --screenshot scan.png
python -m elixir studio              # local web UI at http://127.0.0.1:8765/
```

Routing: wigolo search -> obscura fetch -> cloak `launch_persistent_context(humanize=True)` on `blocked_by_challenge/403/Turnstile`.
Profiles: `./profiles/<site>/` fixed `--fingerprint=seed` + storage_state, one human per site.
Artifacts (`.md` / `.pdf` / screenshots) land in `<ELIXIR_DATA_DIR>/artifacts/`
— that is the only directory Studio will ever serve.

## Speed

```powershell
python -m elixir warm        # load both local models once (~18s)
```

Local calls are quick while the models stay resident; bringing one *back* is
not. Ollama evicts a model 5 minutes after its last call, and a reload costs
minutes on a CPU-only box, so `warm` pays it once up front (the Studio warms
on startup too), and every call asks for a longer lease via `keep_alive`
(`ELIXIR_OLLAMA_KEEP_ALIVE`, default `15m`).

Measured on a Ryzen 5 7520U (4C/8T, no GPU offload):

| call | time |
|---|---|
| `spend`, warm text generation | 0.3–1 s |
| `fetch`, `apps`, `decide` (warm) | 0.5–3 s |
| `act` (launch + screenshot) | ~10 s |
| `search` | 12–20 s |
| `warm` (first load of both models) | ~18 s |
| `doctor` / `health` | ~25 s |
| `run` (plan → search → local LLM) | ~48 s |
| **`buddy ask` (screen vision)** | **~150–175 s** |

`doctor` probes all seven tiers concurrently, so it costs the slowest single
probe (`agent-reach`, ~25 s) instead of the sum of all seven (~50 s).

**Screen vision is the one slow path, and it is hardware.** Ollama runs the
image encoder on CPU (`clip_ctx: CLIP using CPU backend`) and Qwen-VL needs
1024 image tokens — llama-server is started with `--image-min-tokens 1024`,
so shrinking the screenshot does not help (384 px still costs 1065 tokens).
That is 1105 tokens prefilled at ~8 tok/s ≈ 140 s, measured with the model
already resident and 5 GB RAM free, so it is not cold start and not paging.
Every other call stays on the fast path. To make `buddy ask` fast, give the
box a GPU, or set `ELIXIR_VISION_MODEL` to a vision model with a smaller
image budget.

## Security model (Studio)

| Control | Behaviour |
| --- | --- |
| Bind | `127.0.0.1` only, never `0.0.0.0` |
| Auth | random token per process, required on **every** route except `/` |
| CORS | no `Access-Control-Allow-Origin`, ever — a foreign page cannot read the token |
| CSRF | `Origin` must be loopback, `Host` must be loopback, `Content-Type` must be `application/json` |
| Body | capped at 64 KB, `task` capped at 2000 chars, malformed JSON → 400 |
| File reads | `os.path.commonpath()` containment inside `artifacts/`, `.env`/`.lock`/`.jsonl` refused |
| Memory | finished runs pruned after 15 min, hard cap of 50 |
| Subprocess | `shell=False` everywhere; `npx` resolved to its absolute path so `&`/`|` reach wigolo as literal argv |
| URLs | `http`/`https` only; cloud metadata endpoints refused |
| Spend | `spend.allowed()` checked *inside* `_bynara_text`/`_bynara_vision`, not left to callers |
| Output | feed HTML is escaped; untrusted tool evidence is wrapped as tagged data for the synthesiser |

## Ops (production)
```powershell
elixir doctor        # human report, 7 tiers — all must read `ok`
elixir health        # machine JSON: {"healthy": bool, "tiers": {...}} — point monitoring here
elixir versions      # pinned vs installed upstream drift
elixir spend         # metered cloud-eyes vs monthly cap (default 50000 IDR)
elixir autopilot     # self-heal safe tiers, ask approval for login/spend/install
elixir studio        # local web UI, token printed at startup
python -m pytest -q  # 56 gates: injection, CSRF, traversal, spend cap, seat lock, scrub
```
CI (`.github/workflows/ci.yml`) runs `pyflakes` + the suite on
ubuntu/windows × Python 3.10/3.13, and builds the wheel.
Policy: `elixir/autopilot.py` — auto = retries/escalation/rotation/daemons;
ask = logins, spend, installs, updates, irreversible. An approval with a
`run` key executes immediately (a declined or inert approval is theatre).
Secrets via env/`.env` (`ELIXIR_BYNARA_KEY_FILE`), never code;
logs scrub keys (`elixir/log.py`).
