# 🚀 Bot Launcher

Boyd's personal **bot app store** (TokenMax SHORTLIST #4): one card for every Grok Bot on this box, Fleet Doctor grades, routines, one-tap **Open chat** deeplinks, a mini **fleet map**, and a **Build Night shelf** of every TokenMax project.

**Live (box only):** http://127.0.0.1:4262/ — start with `./run.sh`  
**Offline:** `dist/bot-launcher-snapshot.html` (single file, works from `file://`)

## Saturday remaster
- Catalog is **refreshed from live** `/home/box/agent-data/agents/*/profile.json` + automations (not a frozen list). Unfinished hatchery stubs like “New Bot” are skipped.
- Deeplinks are exactly `grokbot://app/v1/agent?id=<uuid>` — no other format.
- Fleet Doctor grades/last-active come from `../fleet-doctor/data/report.json` when present; otherwise grades are omitted (graceful degrade).
- Stats strip: bot count, active routines, **healthy (A/B)** vs **needs attention (C/D/F)**, fleet GPA, project count.
- **Fleet map** mini-view: bots plotted by area lane, colored by health; click a node to open chat.
- Search + area filters (Family / Work / Finance / Research / Kids / Fleet ops / Needs attention). Keyboard: `/` search, ←/→ focus cards, Enter opens chat.
- Build Night shelf lists **all** `/workspace/tokenmax/*` projects with a README or `dist/*.html`, with relative links, README blurbs, and an **offline dist** badge when a snapshot exists.
- Avatars: initials on each bot’s profile shape/color (pebble, hex, flower, cloud, …). No invented avatar images.

## Files
| File | Purpose |
|---|---|
| `build.py` | Read-only collector → `data/catalog.json` + `dist/bot-launcher-snapshot.html` |
| `web/index.html` | Page template (inline CSS/JS, no external assets) |
| `server.py` | Stdlib server; rebuilds on start; `/`, `/api/catalog.json`, `/healthz`, `/tm/<shelf>` |
| `run.sh` | Restarts server on port **4262** |
| `make_screens.sh` | Headless Chrome → `screenshots/00-best-home.png` (+ more) |
| `tests/smoke_test.py` | Deeplink format, no prompt leakage, shelf links, filters, offline snapshot |

## Smoke test
```bash
./run.sh
python3 tests/smoke_test.py
```

## Sources (read-only) and rules
- Reads agent profiles/automations, Fleet Doctor report, TokenMax READMEs.
- Writes only inside `/workspace/tokenmax/bot-launcher`. Sends nothing. Invents no data.


---
## Repo notes
- **Built:** Oct 2026 (TokenMax build week; see SHORTLIST/ledger), by TokenMax (Boyd's Grok Bot) on the Grok Bot box.
- **Run:** `./run.sh` (then open the localhost URL it prints).
- Imported from `/workspace/tokenmax/bot-launcher` on Oct 23, 2026. node_modules, virtualenvs, logs and files over 20 MB were left out.
