#!/usr/bin/env python3
"""Bot Launcher collector + snapshot builder (Saturday remaster).
Reads /home/box/agent-data/agents/*/ (profile.json, automations) READ-ONLY,
plus /workspace/tokenmax/fleet-doctor/data/report.json and each TokenMax README.
Writes only inside /workspace/tokenmax/bot-launcher."""
import json, os, glob, re, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/home/box/agent-data/agents"
TM = "/workspace/tokenmax"
ET = ZoneInfo("America/New_York")
DEEPLINK = "grokbot://app/v1/agent?id={}"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# One-sentence role paraphrases (never quote prompt text). Keyed by profile name.
ROLES = {
    "Kelly": "Watches the web and X for AI news, papers and product drops and reports the trends that matter to Boyd.",
    "Michael": "Boyd's chief of staff and front door, reading mail, Slack and calendar and handing specialist work to the other bots.",
    "Oscar": "Watches over Boyd's money, from upcoming bills and cash flow to investing, retirement savings and tax time.",
    "Ryan": "Hunts for concrete, ranked business and side-hustle ideas that fit Boyd's interests.",
    "Dr. EggBot": "Designs and sets up new Grok Bots for the fleet after asking a few preference questions.",
    "Boyd Family Times": "Puts together the family's daily household newspaper as a printable PDF.",
    "Vic Tutor": "Homework helper for Victor in 6th grade, explaining and quizzing across subjects.",
    "Brief": "Writes Boyd's weekday morning brief of the mail, Slack threads and meetings that need him.",
    "Jim": "Follows what Boyd reads and saves and turns it into interest notes and research.",
    "Dwight": "Boyd's software engineer, shipping code changes, fixes and investigations.",
    "Pam": "Keeps the family schedule running, covering sports, school, doctor visits, trips and weekend plans.",
    "Pods": "Checks Boyd's favorite podcast and YouTube channels for new episodes and briefs him on what's worth a listen.",
    "Path": "Guides Charlotte's high-school placement journey toward a fall 2027 start.",
    "Char Tutor": "Homework helper for Charlotte in 8th grade, explaining and quizzing across subjects.",
    "TokenMax": "Turns leftover subscription usage into fun builds before the weekly and monthly resets.",
    "Engineering Lead": "Runs Boyd's engineering cadence: breaks work into Cloud Agents, tracks CI and reviews, and only surfaces items that are stuck, merge-ready, or finished.",
}
AREAS = {
    "Kelly": ["research"],
    "Michael": ["work", "family"],
    "Oscar": ["finance"],
    "Ryan": ["research", "work"],
    "Dr. EggBot": ["fleet"],
    "Boyd Family Times": ["family"],
    "Vic Tutor": ["kids"],
    "Brief": ["work"],
    "Jim": ["research"],
    "Dwight": ["work"],
    "Pam": ["family", "kids"],
    "Pods": ["research"],
    "Path": ["kids"],
    "Char Tutor": ["kids"],
    "TokenMax": ["fleet"],
    "Engineering Lead": ["work", "fleet"],
}
# Skip unfinished hatchery stubs that shouldn't appear in Boyd's app store.
SKIP_NAMES = {"New Bot"}

COLORS = {
    "red": "#ef5350", "yellow": "#f2b705", "green": "#43a047", "blue": "#3d7be0",
    "orange": "#fb8c00", "cyan": "#00acc1", "violet": "#8e6be8", "magenta": "#d63aa8",
    "gray": "#90a4ae", "grey": "#90a4ae", "": "#7b8794",
}
DAYS = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]
GRADE_HEALTHY = {"A", "B"}
GRADE_ATTENTION = {"C", "D", "F"}


def fmt_time(h, m):
    h, m = int(h), int(m)
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def cron_words(c):
    try:
        mi, hr, dom, mon, dow = c.split()
        if dom != "*" or mon != "*" or not mi.isdigit():
            return f"Custom schedule ({c})"
        times = " and ".join(fmt_time(h, mi) for h in hr.split(","))
        if dow == "*":
            when = "Every day"
        elif dow == "1-5":
            when = "Weekdays"
        elif dow in ("0,6", "6,0"):
            when = "Weekends"
        elif dow.isdigit():
            when = DAYS[int(dow) % 7]
        else:
            return f"Custom schedule ({c})"
        return f"{when} at {times} ET"
    except Exception:
        return f"Custom schedule ({c})"


def iso_et(ms_or_iso):
    if ms_or_iso is None:
        return None
    if isinstance(ms_or_iso, (int, float)):
        d = datetime.datetime.fromtimestamp(ms_or_iso / 1000, tz=datetime.timezone.utc)
    else:
        d = datetime.datetime.fromisoformat(str(ms_or_iso).replace("Z", "+00:00"))
    return d.astimezone(ET).isoformat(timespec="minutes")


def initials(name):
    w = re.sub(r"[^A-Za-z ]", " ", name).split()
    if not w:
        return "?"
    if len(w) == 1:
        return w[0][:2].title()
    return (w[0][0] + w[-1][0]).upper()


def load_json(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def paraphrase_role(name, title, desc):
    if name in ROLES:
        return ROLES[name]
    # Safe fallback: one short sentence from title + first clause, never a 6-word prompt run.
    base = (title or name or "Grok Bot").strip()
    return f"Specialist bot focused on {base.lower()} for Boyd."


def infer_areas(name, title, desc):
    if name in AREAS:
        return AREAS[name]
    blob = f"{name} {title} {desc}".lower()
    areas = []
    if any(k in blob for k in ("tutor", "homework", "kid", "school", "charlotte", "victor")):
        areas.append("kids")
    if any(k in blob for k in ("family", "calendar", "household", "sports")):
        areas.append("family")
    if any(k in blob for k in ("finance", "bill", "money", "tax", "invest")):
        areas.append("finance")
    if any(k in blob for k in ("code", "engineer", "cloud agent", "ci", "software", "slack", "brief", "chief")):
        areas.append("work")
    if any(k in blob for k in ("research", "interest", "bookmark", "trend", "podcast", "idea")):
        areas.append("research")
    if any(k in blob for k in ("bot", "fleet", "token", "hatch")):
        areas.append("fleet")
    return areas or ["fleet"]


def readme_blurb(p):
    """Title = first markdown heading; blurb = first prose paragraph after it."""
    title, blurb = None, None
    try:
        text = open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return None, None
    paras = [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]
    for para in paras:
        first = para.splitlines()[0].strip()
        if title is None:
            if first.startswith("#"):
                title = first.lstrip("#").strip()
                rest = "\n".join(para.splitlines()[1:]).strip()
                if not rest:
                    continue
                para, first = rest, rest.splitlines()[0].strip()
            else:
                continue
        if first.startswith(("#", "!", "|", "```", "- ", "* ", ">", "<", "1.", "Live", "Port", "Run", "Offline")):
            continue
        t = " ".join(l.strip() for l in para.splitlines())
        t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
        t = re.sub(r"[*_`]", "", t).strip()
        if len(t) < 25:
            continue
        blurb = t
        break
    if blurb and len(blurb) > 170:
        blurb = blurb[:167].rsplit(" ", 1)[0] + "…"
    return title, blurb


def discover_agents():
    """All UUID agent dirs with a profile.json, minus unfinished hatchery stubs."""
    found = []
    for d in sorted(glob.glob(os.path.join(ROOT, "*/"))):
        aid = os.path.basename(d.rstrip("/"))
        if not UUID_RE.match(aid):
            continue
        prof_path = os.path.join(d, "profile.json")
        if not os.path.exists(prof_path):
            continue
        prof = load_json(prof_path, {}) or {}
        name = (prof.get("name") or "").strip()
        if not name or name in SKIP_NAMES:
            continue
        found.append((name, aid, prof, d))
    return found


def grade_bucket(grade):
    if grade in GRADE_HEALTHY:
        return "healthy"
    if grade in GRADE_ATTENTION:
        return "attention"
    return "unknown"


def main():
    report = load_json(os.path.join(TM, "fleet-doctor/data/report.json"), {}) or {}
    cards_by_name = {c["name"]: c for c in report.get("cards", [])}
    agents = discover_agents()
    bots = []
    for name, aid, prof, adir in agents:
        routines = []
        for ap in sorted(glob.glob(os.path.join(adir, "automations", "*", "automation.json"))):
            a = load_json(ap, {}) or {}
            runs = load_json(os.path.join(os.path.dirname(ap), "runs.json"), []) or []
            ok = sum(1 for r in runs if r.get("status") == "ok")
            last = max((r.get("startedAt") or 0 for r in runs), default=0) or a.get("lastRunAt")
            routines.append({
                "name": a.get("name") or os.path.basename(os.path.dirname(ap)),
                "cron": a.get("schedule"),
                "when": cron_words(a.get("schedule") or ""),
                "enabled": bool(a.get("enabled")),
                "runs": len(runs),
                "ok": ok,
                "lastRun": iso_et(last) if last else None,
            })
        fd = cards_by_name.get(name)
        grade = None
        if fd:
            grade = {
                "grade": fd.get("grade"),
                "score": fd.get("score"),
                "reasons": (fd.get("reasons") or [])[:2],
                "fixes": (fd.get("fixes") or [])[:1],
            }
        last_active = iso_et(fd.get("lastActive")) if fd and fd.get("lastActive") else None
        if not last_active:
            lr = [r["lastRun"] for r in routines if r["lastRun"]]
            last_active = max(lr) if lr else None
        desc = prof.get("description") or ""
        title = prof.get("title") or ""
        color_name = prof.get("avatarColor") or ""
        bots.append({
            "id": aid,
            "name": name,
            "title": title,
            "role": paraphrase_role(name, title, desc),
            "areas": infer_areas(name, title, desc),
            "avatar": {
                "shape": prof.get("avatarShape") or "circle",
                "color": COLORS.get(color_name, "#7b8794"),
                "colorName": color_name,
                "initials": initials(name),
                "image": None,
            },
            "routines": routines,
            "lastActive": last_active,
            "doctor": grade,
            "health": grade_bucket(grade["grade"]) if grade and grade.get("grade") else "unknown",
            "deeplink": DEEPLINK.format(aid),
        })

    # Stable sort: attention first (so Boyd sees them), then name.
    health_rank = {"attention": 0, "unknown": 1, "healthy": 2}
    bots.sort(key=lambda b: (health_rank.get(b["health"], 9), b["name"].lower()))

    # Build Night / Project shelf — every TokenMax project with README or dist HTML.
    shelf = []
    for d in sorted(glob.glob(os.path.join(TM, "*/"))):
        slug = os.path.basename(d.rstrip("/"))
        if slug in ("bot-launcher",) or slug.startswith(("_", ".")):
            continue
        readme = os.path.join(d, "README.md")
        snaps = sorted(glob.glob(os.path.join(d, "dist", "*.html")))
        pref = [s for s in snaps if "snapshot" in os.path.basename(s)] or snaps
        snap = pref[0] if pref else None
        if not os.path.exists(readme) and not snap:
            continue
        title, blurb = readme_blurb(readme) if os.path.exists(readme) else (None, None)
        mtime = max(os.path.getmtime(p) for p in [readme, snap] if p and os.path.exists(p))
        shelf.append({
            "slug": slug,
            "title": title or slug.replace("-", " ").title(),
            "blurb": blurb,
            "readme": f"{slug}/README.md" if os.path.exists(readme) else None,
            "snapshot": os.path.relpath(snap, TM) if snap else None,
            "offlineReady": bool(snap),
            "updated": datetime.datetime.fromtimestamp(mtime, tz=ET).isoformat(timespec="minutes"),
        })

    healthy = sum(1 for b in bots if b["health"] == "healthy")
    attention = sum(1 for b in bots if b["health"] == "attention")
    routine_n = sum(len(b["routines"]) for b in bots)
    active_routines = sum(1 for b in bots for r in b["routines"] if r["enabled"])
    offline_n = sum(1 for s in shelf if s["offlineReady"])

    catalog = {
        "generatedAt": datetime.datetime.now(tz=ET).isoformat(timespec="minutes"),
        "doctorGeneratedAt": iso_et(report.get("generatedAt")) if report.get("generatedAt") else None,
        "doctorAvailable": bool(report.get("cards")),
        "fleetScore": report.get("fleetScore"),
        "fleetGpa": report.get("gpa"),
        "stats": {
            "bots": len(bots),
            "routines": routine_n,
            "activeRoutines": active_routines,
            "healthy": healthy,
            "attention": attention,
            "projects": len(shelf),
            "offlineReady": offline_n,
        },
        "bots": bots,
        "shelf": shelf,
        "notes": [
            "Catalog refreshed from live agent profiles and automations on this box.",
            "No avatar image files exist in bot profiles, so cards use each bot's profile color and shape with initials.",
            "Routines come from automations on this box; bots without a folder there show 'No routines on this box'.",
            "Last activity and grades come from Fleet Doctor when report.json is present; otherwise grades are omitted.",
        ],
    }
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    with open(os.path.join(HERE, "data", "catalog.json"), "w") as f:
        json.dump(catalog, f, indent=1)

    tpl = open(os.path.join(HERE, "web", "index.html"), encoding="utf-8").read()
    snap = (
        tpl.replace("/*__CATALOG__*/null", json.dumps(catalog).replace("</", "<\\/"))
        .replace("__BASE__", "../../")
    )
    with open(os.path.join(HERE, "dist", "bot-launcher-snapshot.html"), "w", encoding="utf-8") as f:
        f.write(snap)
    print(
        f"bots={len(bots)} shelf={len(shelf)} routines={routine_n} "
        f"active={active_routines} healthy={healthy} attention={attention} offline={offline_n}"
    )


if __name__ == "__main__":
    main()
