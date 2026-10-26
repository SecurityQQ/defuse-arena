#!/usr/bin/env python3
"""Re-embed a season's standings into the onboarding page.

    python3 scripts/onboarding.py <season> [web/onboarding.html]

The onboarding is hand-written except one block, fenced by
``/* @onboarding-data begin */`` and ``/* @onboarding-data end */``, which this
script rewrites from ``seasons/<season>/standings.json``, ``ledger.jsonl`` and
``web/roster.json``:

* the agent select: the top six by pentest rating (``rating_att``) and the top
  six by audit rating (``rating_def``), each with its played record in that
  role and USD per round;
* the leaderboard drawer: every played champion by overall ``rating``, W–L and
  net chips;
* the demo pair, kept as deepseek vs opus-5.5 while both are in their corner,
  else the top seed of each corner;
* the played-rounds badge on the task family.

Names are the resolved variant the CLI recorded (``model_name``, e.g. "Claude
Opus 5.5 Medium"), so the page shows what actually played, as the board does.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = 6
DEMO = {"chall": "deepseek", "guard": "opus-5.5"}
BEGIN, END = "/* @onboarding-data begin", "/* @onboarding-data end */"

if not 2 <= len(sys.argv) <= 3:
    sys.exit(__doc__.strip().splitlines()[2].strip())
season = sys.argv[1]
target = Path(sys.argv[2]) if len(sys.argv) == 3 else ROOT / "web" / "onboarding.html"
sdir = ROOT / "seasons" / season

standings = json.loads((sdir / "standings.json").read_text())
ledger = [json.loads(l) for l in (sdir / "ledger.jsonl").read_text().splitlines() if l.strip()]
roster = {c["agent"]: c for c in json.loads((ROOT / "web" / "roster.json").read_text())["champions"]}
rows = standings["rows"]


def champ(r):
    c = roster.get(r["agent"], {})
    return {
        "agent": r["agent"],
        "name": r.get("model_name") or c.get("name") or r["agent"],
        "title": c.get("title", ""),
        "glyph": c.get("glyph", r["agent"][:2].upper()),
        "price": f"${r['cost_per_round']:.2f}",
    }


def corner(key, side):
    played = [r for r in rows if r[side]["rounds"]]
    played.sort(key=lambda r: -r[key])
    return [dict(champ(r), rt=round(r[key]), rec=f"{r[side]['wins']}–{r[side]['losses']}")
            for r in played[:TOP]]


def chips(x):
    return f"{'+' if x >= 0 else chr(0x2212)}${abs(x):.2f}"


def tour_round():
    """The round the tour replays: the demo pair's first graded heads round the
    defender won, else their first graded round."""
    pair = [l for l in ledger if not l.get("void") and l["attacker"] == DEMO["chall"]
            and l["defender"] == DEMO["guard"]]
    if not pair:
        sys.exit(f"{season}: no graded round between {DEMO['chall']} and {DEMO['guard']}")
    return next((l for l in pair if l["theta"] == 1 and l["outcome"] == "TP"), pair[0])


def clip(line, n=46):
    line = line.rstrip()
    return line if len(line) <= n else line[:n - 1] + "\u2026"


def is_code(line):
    t = line.strip()
    return t and not t.startswith("#")


def routes(main):
    out, method = [], None
    for line in main.splitlines():
        m = re.match(r"\s*def do_([A-Z]+)\(", line)
        if m:
            method = m.group(1)
        m = re.search(r'path == "([^"]+)"', line) or re.search(r're\.match\(r"\^([^"$]+)\$"', line)
        if m and method:
            path = re.sub(r"\(\\d\+\)", "{id}", m.group(1))
            if [method, path] not in out:
                out.append([method, path])
    return out


def tour(l):
    rdir = sdir / "matches" / l["match_id"] / "rounds" / l["round_id"]
    tree = rdir / "frozen" / "tree"
    report = json.loads((rdir / "defender" / "out" / "report.json").read_text())
    patch = (report.get("patch") or "").splitlines()
    loc = (report.get("locations") or [{}])[0]
    src = (tree / loc["path"]).read_text().splitlines() if loc.get("path") else []
    lo, hi = (loc.get("lines") or [1, len(src)])[:2]
    removed = {x[1:].rstrip() for x in patch if x.startswith("-") and not x.startswith("---")}
    added = [x[1:] for x in patch if x.startswith("+") and not x.startswith("+++") and is_code(x[1:])]
    hot = [n for n in range(lo, hi + 1) if src[n - 1].rstrip() in removed and is_code(src[n - 1])]
    # the planted branch is the longest run of removed code (comments may sit inside it)
    runs = []
    for n in hot:
        if runs and all(src[k - 1].strip().startswith("#") for k in range(runs[-1][-1] + 1, n)):
            runs[-1].append(n)
        else:
            runs.append([n])
    run = max(reversed(runs), key=len) if runs else []
    # the same function after the patch: its first line, then the patch's new code
    fixed, n_new = [], None
    for x in patch:
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", x)
        if m:
            n_new = int(m.group(1))
            continue
        if n_new is None or x.startswith(("---", "+++", "-", "\\")):
            continue
        if x.startswith("+") or (not fixed and x[1:].strip().startswith("def ")) or (fixed and len(fixed) == 1 and is_code(x[1:])):
            fixed.append([n_new, clip(x[1:]), x.startswith("+")])
        n_new += 1
    head = [lo] if lo not in run else []
    focus = (head + run)[:4]
    poc = rdir / "sealed" / "poc" / "run.sh"
    checks = l.get("checks", {})
    return {
        "round_id": l["round_id"], "no": int(l["round_id"].split("-")[-1]), "ts": l["ts"],
        "task": l.get("task_title") or l["task_id"], "task_id": l["task_id"], "family": l.get("task_family"),
        "theta": l["theta"], "outcome": l["outcome"], "p": report.get("exploit_present"),
        "brier": l["brier"], "mechanism": report.get("mechanism") or l.get("mechanism", ""),
        "location": f"{loc.get('path', '')}:{lo}\u2013{hi}" if loc else "",
        "files": [[str(f.relative_to(tree)), len(f.read_text().splitlines())]
                  for f in sorted(tree.rglob("*.py")) if f.stat().st_size],
        "routes": routes((tree / "app" / "main.py").read_text()) if (tree / "app" / "main.py").exists() else [],
        "code": [[n, clip(src[n - 1])] for n in focus],
        "hot": run[len(run) // 2] if run else None,
        "fixed": fixed[:2] + [f for f in fixed[2:] if f[2]][:1] + [f for f in fixed[2:] if f[2]][1:][-1:],
        "patch": [x for x in patch if not x.startswith(("diff ", "--- ", "+++ ", "\\"))],
        "poc": [x for x in poc.read_text().splitlines() if "headers=" in x or "Request(" in x][:2] if poc.exists() else [],
        "canary": (checks.get("poc_unpatched_note") or "").strip(),
        "checks": {k: checks.get(k) for k in ("patch_applied", "patched_started", "smoke_patched",
                                              "poc_unpatched", "poc_patched")},
        "tokens": l["tokens"], "cost": l["cost"], "chips": l["chips"],
        "delta": l.get("rating_delta", {}), "role_delta": l.get("role_delta", {}),
        "first": l.get("first_game", {}),
        "brief": brief(l["task_id"]),
    }


def brief(task_id):
    t = json.loads((ROOT / "tasks" / task_id / "task.json").read_text())
    return {"language": t.get("language"), "bug_classes": t.get("bug_classes", []),
            "canary": t.get("canary", {}), "minutes": t.get("time_limit_min"),
            "budget": (t.get("budgets") or {}).get("defender")}


TOUR = tour_round()


def seat(cards, agent, key, side):
    """Keep the tour pair in its corner even if it fell out of the top six."""
    if any(c["agent"] == agent for c in cards):
        return cards
    r = next(r for r in rows if r["agent"] == agent)
    return cards[:TOP - 1] + [dict(champ(r), rt=round(r[key]), rec=f"{r[side]['wins']}\u2013{r[side]['losses']}")]


att, dfn = corner("rating_att", "att"), corner("rating_def", "def")
att = seat(att, TOUR["attacker"], "rating_att", "att")
dfn = seat(dfn, TOUR["defender"], "rating_def", "def")
demo = {"chall": TOUR["attacker"], "guard": TOUR["defender"]}
board = [{"rank": i + 1, "agent": r["agent"], "name": champ(r)["name"], "rt": round(r["rating"]),
          "wl": f"{r['wins']}\u2013{r['losses']}", "chips": chips(r["net_chips"]),
          "att": round(r["rating_att"]), "def": round(r["rating_def"])}
         for i, r in enumerate(sorted(rows, key=lambda r: -r["rating"]))]
family = next((l.get("task_family") for l in ledger if l.get("task_family")), "crud-auth")

data = {
    "season": standings["season_id"],
    "scoring": standings["scoring_version"],
    "generated_at": standings["generated_at"],
    "rounds": len(ledger),
    "family": family,
    "demo": demo,
    "att": att,
    "def": dfn,
    "board": board,
    "tour": dict(tour(TOUR), attacker=TOUR["attacker"], defender=TOUR["defender"]),
}


def js(v):
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def field(k, v, pad="    "):
    if isinstance(v, list) and v and isinstance(v[0], (dict, list)):
        return f"{pad}{js(k)}: [\n" + ",\n".join(f"{pad}  {js(x)}" for x in v) + f"\n{pad}]"
    if isinstance(v, dict) and any(isinstance(x, (dict, list)) for x in v.values()):
        return f"{pad}{js(k)}: {{\n" + ",\n".join(field(a, b, pad + "  ") for a, b in v.items()) + f"\n{pad}}}"
    return f"{pad}{js(k)}: {js(v)}"


blob = "{\n" + ",\n".join(field(k, v) for k, v in data.items()) + "\n  }"
block = (f"{BEGIN} — generated by scripts/onboarding.py {season}; do not edit */\n"
         f"  const SEASON = {blob};\n  {END}")

page = target.read_text()
pat = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
if not pat.search(page):
    sys.exit(f"{target}: no {BEGIN} … {END} block")
target.write_text(pat.sub(lambda _: block, page, count=1))
print(f"{target}: {data['season']} · {len(board)} champions · {data['rounds']} rounds · "
      f"demo {demo['chall']} vs {demo['guard']}")
