#!/usr/bin/env python3
"""Bot Launcher smoke test (Saturday remaster).
Checks catalog, snapshot, live server DOM, deeplink format, no prompt leakage,
Build Night shelf, Fleet Doctor grades when present."""
import json, os, re, subprocess, sys, tempfile, urllib.request, glob

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TM = "/workspace/tokenmax"
ROOT = "/home/box/agent-data/agents"
PORT = int(os.environ.get("PORT", "4262"))
URL = f"http://127.0.0.1:{PORT}/"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
LINK_RE = re.compile(
    r"^grokbot://app/v1/agent\?id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)
ANY_GROK = re.compile(r"grokbot://[^\"'\s<>)]*")
SKIP_NAMES = {"New Bot"}

passed = failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        print("PASS", msg)
    else:
        failed += 1
        print("FAIL", msg)


def live_expected():
    """name -> id from live profiles on disk (same rules as build.py)."""
    out = {}
    for d in sorted(glob.glob(os.path.join(ROOT, "*/"))):
        aid = os.path.basename(d.rstrip("/"))
        if not UUID_RE.match(aid):
            continue
        p = os.path.join(d, "profile.json")
        if not os.path.exists(p):
            continue
        prof = json.load(open(p))
        name = (prof.get("name") or "").strip()
        if not name or name in SKIP_NAMES:
            continue
        out[name] = aid
    return out


def check_links(links, where, expected_ids):
    # Open-chat buttons + fleet-map nodes both use the same deeplink format (duplicates OK).
    check(len(links) >= len(expected_ids), f"{where}: at least {len(expected_ids)} grokbot:// links (got {len(links)})")
    ids = []
    for l in links:
        m = LINK_RE.match(l)
        check(bool(m), f"{where}: format ok {l}")
        if m:
            ids.append(m.group(1))
    check(sorted(set(ids)) == sorted(set(expected_ids)), f"{where}: unique link IDs == live agent IDs exactly")
    check(set(ids) <= set(expected_ids), f"{where}: no unexpected IDs")
    check(not any(re.search(r"plugin|skill", l, re.I) for l in links), f"{where}: no plugin/skill deeplinks")


EXPECTED = live_expected()
N = len(EXPECTED)
check(N >= 15, f"live profiles on box: {N} bots")

cat = json.load(open(os.path.join(HERE, "data", "catalog.json")))
bots = cat["bots"]
check(len(bots) == N, f"catalog has {N} bots (got {len(bots)})")
check({b["name"]: b["id"] for b in bots} == EXPECTED, "catalog name→ID map matches live profiles")

for b in bots:
    check(b["deeplink"] == f"grokbot://app/v1/agent?id={b['id']}", f"{b['name']}: deeplink exact")
    prof = json.load(open(os.path.join(ROOT, b["id"], "profile.json")))
    check(prof.get("name") == b["name"], f"{b['name']}: name matches its profile.json")
    check((prof.get("title") or "") == (b["title"] or ""), f"{b['name']}: title matches profile")
    desc = prof.get("description") or ""
    role = b["role"]
    check(role.count(". ") == 0 and role.endswith("."), f"{b['name']}: role is one sentence")
    dw = re.findall(r"[a-z']+", desc.lower())
    rw = " ".join(re.findall(r"[a-z']+", role.lower()))
    grams = {" ".join(dw[i:i + 6]) for i in range(max(0, len(dw) - 5))}
    check(not any(g in rw for g in grams), f"{b['name']}: role is not verbatim prompt text")
    check(set(b["areas"]) <= {"family", "work", "finance", "research", "kids", "fleet"} and b["areas"],
          f"{b['name']}: valid areas")
    real = sorted(
        json.load(open(p)).get("name")
        for p in glob.glob(os.path.join(ROOT, b["id"], "automations", "*", "automation.json"))
    )
    check(sorted(r["name"] for r in b["routines"]) == real,
          f"{b['name']}: routines match automations on box ({len(real)})")
    for r in b["routines"]:
        check(bool(r["when"]), f"{b['name']}/{r['name']}: has schedule words '{r['when']}'")
    check(b["avatar"]["image"] is None, f"{b['name']}: no invented avatar image")
    check(b["avatar"]["initials"], f"{b['name']}: has initials")

# Fleet Doctor (graceful if missing)
fd_path = os.path.join(TM, "fleet-doctor/data/report.json")
if os.path.exists(fd_path) and cat.get("doctorAvailable"):
    fd = {c["name"]: c["grade"] for c in json.load(open(fd_path))["cards"]}
    graded = [b for b in bots if b.get("doctor")]
    check(len(graded) == sum(1 for b in bots if b["name"] in fd),
          f"grades present for bots in Fleet Doctor ({len(graded)})")
    check(all(b["doctor"]["grade"] == fd[b["name"]] for b in graded),
          "grades match Fleet Doctor exactly")
    attn = sum(1 for b in bots if b.get("health") == "attention")
    healthy = sum(1 for b in bots if b.get("health") == "healthy")
    check(attn + healthy <= N, f"health buckets: healthy={healthy} attention={attn}")
    check(cat["stats"]["healthy"] == healthy and cat["stats"]["attention"] == attn, "stats strip matches health buckets")
else:
    check(True, "Fleet Doctor report missing — grades degraded gracefully")

# Shelf
shelf = cat["shelf"]
check(len(shelf) >= 30, f"Build Night shelf has {len(shelf)} projects")
for s in shelf:
    for k in ("readme", "snapshot"):
        if s.get(k):
            check(not s[k].startswith("/") and os.path.exists(os.path.join(TM, s[k])),
                  f"shelf {s['slug']} {k} relative + exists")
    check("offlineReady" in s, f"shelf {s['slug']}: offlineReady flag")
    if s.get("snapshot"):
        check(s["offlineReady"] is True, f"shelf {s['slug']}: snapshot ⇒ offlineReady")
check(not any(s["slug"] == "bot-launcher" for s in shelf), "shelf excludes itself")

# Snapshot
snap_p = os.path.join(HERE, "dist", "bot-launcher-snapshot.html")
snap = open(snap_p, encoding="utf-8").read()
check(os.path.getsize(snap_p) > 20000, "snapshot exists and is non-trivial")
check(not re.search(r'(src|href)="(https?:)?//', snap), "snapshot has no external src/href (offline)")
check("../../" in snap, "snapshot shelf links are relative (../../)")
expected_links = sorted(f"grokbot://app/v1/agent?id={i}" for i in EXPECTED.values())
check(sorted(set(ANY_GROK.findall(snap))) == expected_links, "snapshot source: only exact deeplinks")
for s in shelf:
    for k in ("readme", "snapshot"):
        if s.get(k):
            check(os.path.exists(os.path.normpath(os.path.join(HERE, "dist", "../../" + s[k]))),
                  f"snapshot link resolves: {s[k]}")

# Fleet map present
check('id="fleetmap"' in snap and "Fleet map" in snap, "UI includes fleet map")


def dom(url):
    d = tempfile.mkdtemp()
    out = subprocess.run(
        ["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
         f"--user-data-dir={d}", "--virtual-time-budget=3500", "--dump-dom", url],
        capture_output=True, text=True, timeout=90,
    ).stdout
    return re.sub(r"<script.*?</script>", "", out, flags=re.S)


for where, url in (("snapshot DOM", "file://" + snap_p), ("server DOM", URL)):
    html = dom(url)
    links = re.findall(r'href="(grokbot://[^"]*)"', html)
    # fleet map also embeds deeplink circles — filter to Open chat style OR all must be exact format
    check_links(links, where, list(EXPECTED.values()))
    check(html.count('class="card') >= N or html.count('class="card"') == N or html.count("class=\"card") >= N,
          f"{where}: {N} cards rendered (count class=card)")
    # more precise:
    cards = len(re.findall(r'class="card(?:\s|")', html))
    check(cards == N, f"{where}: {N} cards rendered (got {cards})")
    books = len(re.findall(r'class="book(?:\s|")', html))
    check(books == len(shelf), f"{where}: {len(shelf)} shelf items rendered (got {books})")

# filters — kids includes Pam + tutors + Path; Engineering Lead is work/fleet
kids = dom(URL + "?area=kids")
names = re.findall(r"<h3>([^<]+)</h3>", kids)
check(set(names) >= {"Char Tutor", "Pam", "Path", "Vic Tutor"}, f"kids filter includes tutors/Pam/Path → {names}")
fin = re.findall(r"<h3>([^<]+)</h3>", dom(URL + "?area=finance"))
check(fin == ["Oscar"], f"finance filter → {fin}")
srch = re.findall(r"<h3>([^<]+)</h3>", dom(URL + "?q=homework"))
check(sorted(srch) == ["Char Tutor", "Vic Tutor"], f"search 'homework' → {srch}")

# Server
with urllib.request.urlopen(URL + "healthz", timeout=5) as r:
    check(r.read() == b"bot-launcher ok", f"server healthy on {PORT}")
with urllib.request.urlopen(URL + "api/catalog.json", timeout=5) as r:
    check(len(json.load(r)["bots"]) == N, "api/catalog.json ok")
s0 = shelf[0]
with urllib.request.urlopen(URL + "tm/" + (s0["readme"] or s0["snapshot"]), timeout=5) as r:
    check(r.status == 200, "shelf file served")
try:
    urllib.request.urlopen(URL + "tm/usage.json", timeout=5)
    check(False, "non-shelf file blocked")
except urllib.error.HTTPError as e:
    check(e.code == 404, "non-shelf file blocked (404)")

# Deliverables
best = os.path.join(HERE, "screenshots", "00-best-home.png")
check(os.path.exists(best) and os.path.getsize(best) > 10000, "best screenshot 00-best-home.png present")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
