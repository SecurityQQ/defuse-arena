#!/usr/bin/env python3
"""Derive ledger + standings for a season and render the hextech leaderboard.

Implements SPEC §10.2 (ledger), §10.3 (standings), §10.4 (render).

Rating model
------------
The ratings are a **batch Bradley-Terry fit** — the maximum-likelihood Elo —
not a sequential update. The fit is a pure function of the season's games, so
the same ledger yields the same table whatever order the rounds were graded or
scheduled in. Every pool answers one question (SPEC §9.4):

* ``rating`` — which model overall for cyber security. Every played round,
  θ=1 and θ=0, pure win/loss.
* ``rating_def`` — which model should audit my code. θ=1 defence only: ``TP``
  is a win, ``FN`` a loss; a defender forfeit is a loss at weight 1.5.
* ``rating_att`` — which model should pentest. θ=1 attack only: ``FN`` is a
  win, ``TP`` a loss; an attacker forfeit is a loss at weight 1.5.
* ``rating_clean_att`` / ``rating_clean_def`` — θ=0 diagnostics: who writes
  clean services, who avoids false alarms. Not the audit or pentest answer.
* ``rating_contest`` — every non-void round, a forfeit is a loss: reliability
  when showing up is part of the score.
* ``rating_efficiency`` — the 0.5.0 margin-weighted played-only fit, kept as a
  separate non-ranking axis. The spend margin is in no skill rating.

The role and clean pools are one two-sided fit, ``P(attacker wins) = σ(θ·(A_i
− D_j) + c)``, so an attack is priced against the defender's defence rating and
a defence against the attacker's attack rating. ``c`` is published as
``defense_advantage``. A forfeit is a one-sided game: it moves the offending
role only, because the opponent's forfeit is not a test of that role.

A Gaussian prior toward 1500 (sd 250) keeps a small sample finite; the 95%
confidence interval comes from the Hessian. VOID (infrastructure) moves
nothing and is replayed. No-shows and forfeits are published on their own axis
and in the all-in table instead of corrupting the played-only pools.
"""
import hashlib, json, math, re, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing  # noqa: E402  (sibling module, resolved from this file)

ROOT = Path(__file__).resolve().parent.parent
# Usage: standings.py <season> [ranked_at] [render_ranked_at] [--publish <path>]
#   ranked_at        rounds needed to leave "provisional" (SPEC 10.3: 20)
#   render_ranked_at lower it only to preview a season that is still short
#   --publish        also write the rendered page to <path>, for a static host
_args = list(sys.argv[1:])
PUBLISH = None
if "--publish" in _args:
    _i = _args.index("--publish")
    if _i + 1 >= len(_args):
        sys.exit("--publish needs a path")
    PUBLISH = Path(_args[_i + 1]).resolve()
    del _args[_i:_i + 2]

SEASON = _args[0] if len(_args) > 0 else "s-2026-01"
RANKED_AT = int(_args[1]) if len(_args) > 1 else 20
RENDER_RANKED_AT = int(_args[2]) if len(_args) > 2 else RANKED_AT
SDIR = ROOT / "seasons" / SEASON

# Outcome sets (scoring 0.4.0). Played rounds move every pool. Forfeits move
# only the all-in contest pool: the played-only pools measure skill conditional
# on actually playing, and a refusal is published as its own axis instead.
# VOID is infrastructure only and is replayed, never priced.
PLAYED = {"TP", "TN", "FP", "FN", "DISCOVERY"}
FORFEIT_A = {"ABSTAIN_A", "FAILED_A", "FAULT_A"}
FORFEIT_D = {"ABSTAIN_D", "FAILED_D"}


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def task_meta(scaffold):
    """Task pack behind a round: the problem the attacker is asked to build."""
    path = ROOT / "tasks" / scaffold / "task.json"
    if path.exists():
        try:
            t = json.load(open(path))
            return (t.get("task_id", scaffold), t.get("title", scaffold), t.get("family", ""))
        except Exception:
            pass
    return scaffold, scaffold, ""


# ------------------------------------------------ battle record (§10.4 render)
# The schematic on the page is a replay of what each side actually did, so it
# reads the ATIF export the harness keeps next to the round, not a summary.

def _base(path):
    return str(path).rstrip("/").rsplit("/", 1)[-1][:40] or "\u2014"


def cmd_action(cmd):
    """Turn a shell command into a short verb + object, for the action feed."""
    c = cmd.strip()
    if c.startswith("cd "):
        parts = c.split("&&", 1)
        if len(parts) == 2:
            c = parts[1].strip()
    # drop leading VAR=value assignments so `B=/abs/path python3 x` reads as python3
    while True:
        head, _, rest = c.partition(" ")
        name = head.split("=", 1)[0]
        if rest and "=" in head and name and name.replace("_", "").isalnum():
            c = rest.strip()
            continue
        break
    low = c.lower()
    if "curl" in low:
        m = re.search(r"https?://[^\s/'\"]+(/[^\s'\"]*)?", c)
        return "probed", (m.group(1) if m and m.group(1) else "/")[:34]
    if "pytest" in low or "unittest" in low:
        return "tested", "suite"
    if "py_compile" in low:
        return "compiled", "python"
    if "pkill" in low or "lsof" in low or low.startswith("kill"):
        return "stopped", "server"
    if low.startswith("chmod"):
        return "chmod", "+x"
    if low.startswith("git"):
        parts = c.split()
        return "git", parts[1] if len(parts) > 1 else ""
    if low.startswith(("ls", "find", "tree")):
        return "listed", "tree"
    if low.startswith(("cat", "head", "tail", "sed -n", "nl ")):
        return "read", "file"
    if low.startswith(("rm ", "mv ", "cp ", "mkdir ")):
        return "arranged", "files"
    if low.startswith("sleep"):
        return "waited", "shell"
    if "python" in low:
        return "ran", "python"
    # never publish a host path: the page is deployed, and an absolute path
    # carries the operator's home directory with it
    first = (c.split()[0][:24] if c else "shell")
    if "/" in first:
        first = first.rstrip("/").rsplit("/", 1)[-1] or "shell"
    return "ran", first


def classify(fn, args, share):
    if fn in ("write", "edit"):
        return ["wrote" if fn == "write" else "edited", _base(args.get("file_path", "")), share]
    if fn in ("apply_patch", "patch"):
        return ["patched", _base(str(args.get("path") or args.get("file_path") or "files")), share]
    if fn == "read":
        return ["read", _base(args.get("file_path", "")), share]
    if fn == "exec":
        verb, obj = cmd_action(args.get("command") or "")
        return [verb, obj, share]
    if fn in ("grep", "glob", "find_file_by_name"):
        return ["searched", str(args.get("pattern") or args.get("query") or "")[:26], share]
    if fn == "get_output":
        return ["waited", "shell", share]
    if fn == "kill_shell":
        return ["stopped", "server", share]
    if fn == "run_subagent":
        return ["delegated", "", share]
    if fn == "todo_write":
        return ["planned", "", share]
    return [fn[:12], "", share]


def battle_side(path, model_id, limit=44):
    """One side of a round: model, wall clock, spend and the ordered tool calls."""
    empty = {"model": "", "secs": 0, "steps": 0, "cost": 0.0,
             "prompt": 0, "cached": 0, "completion": 0, "acts": [], "more": 0}
    if not path.exists():
        # A replayed round keeps its exports as <name>.attempt-N.
        tries = sorted(path.parent.glob(path.name + ".*"))
        if not tries:
            return empty
        path = tries[-1]
    try:
        d = json.load(open(path))
    except Exception:
        return empty

    steps = [s for s in d.get("steps", []) if s.get("source") == "agent"]
    stamps = [s.get("timestamp") for s in steps if s.get("timestamp")]
    secs = 0
    if len(stamps) >= 2:
        try:
            t0 = datetime.fromisoformat(stamps[0].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(stamps[-1].replace("Z", "+00:00"))
            secs = max(0, int((t1 - t0).total_seconds()))
        except Exception:
            secs = 0

    acts = []
    total_cost = 0.0
    for st in steps:
        m = st.get("metrics") or {}
        step_cost = pricing.cost_usd(
            {"prompt": m.get("prompt_tokens", 0),
             "cached": m.get("cached_tokens", 0),
             "completion": m.get("completion_tokens", 0)}, model_id) or 0.0
        total_cost += step_cost
        calls = st.get("tool_calls") or []
        if not calls:
            continue
        share = step_cost / len(calls)
        for tc in calls:
            a = tc.get("arguments")
            # a few tools pass a bare string instead of an object
            acts.append(classify(tc.get("function_name") or "", a if isinstance(a, dict) else {}, share))

    fm = d.get("final_metrics") or {}
    prompt = fm.get("total_prompt_tokens", 0)
    cached = fm.get("total_cached_tokens", 0)
    completion = fm.get("total_completion_tokens", 0)
    return {
        "model": (d.get("agent") or {}).get("model_name") or "",
        "secs": secs,
        "steps": fm.get("total_steps") or len(steps),
        "cost": round(total_cost, 6),
        "prompt": prompt,
        "cached": cached,
        "completion": completion,
        "acts": acts[:limit],
        "more": max(0, len(acts) - limit),
    }


def battle_stages(theta, outcome, checks, report_present, confidence, freeze_hash, poc_hash, def_steps):
    """Three lanes: what the attacker built, what the defender did, what the grader saw."""
    g = checks.get
    built = "done" if freeze_hash else "bad"

    att = [["read \u03b8", str(theta), "done"],
           ["built service", "", built],
           ["planted bug", "", built if theta == 1 else "skip"],
           ["sealed PoC", "", ("done" if poc_hash else "bad") if theta == 1 else "skip"],
           ["froze tree", "", built]]

    dfn = [["received tree", "", built],
           ["audited", f"{def_steps} steps" if def_steps else "", "done" if def_steps else "skip"]]
    if report_present:
        dfn.append(["reported", f"p={confidence:.2f}" if confidence is not None else "", "done"])
        dfn.append(["patched", "", "done" if g("patch_applied") else "skip"])
    else:
        dfn.append(["no report", "", "bad"])
        dfn.append(["no patch", "", "skip"])

    arb = []

    def seen(key, label, soft=False):
        v = g(key)
        arb.append([label, "", "good" if v else "skip" if (soft or v is None) else "bad"])

    seen("started", "service up")
    seen("smoke_unpatched", "contract")
    if theta == 1:
        seen("poc_unpatched", "PoC works")
    else:
        arb.append(["PoC vs clean", "", "skip"])
    seen("patch_applied", "patch applied", soft=True)
    seen("smoke_patched", "patched build", soft=True)
    if theta == 1:
        # poc_patched true means the proof-of-concept still fires after the
        # patch, which is the defender failing, so the chip is inverted.
        if g("patch_applied") and g("poc_patched") is not None:
            arb.append(["PoC blocked", "", "bad" if g("poc_patched") else "good"])
        else:
            arb.append(["PoC blocked", "", "skip"])
    else:
        arb.append(["PoC vs patched", "", "skip"])
    arb.append([outcome, "",
                "good" if outcome in ("TP", "TN", "DISCOVERY")
                else "bad" if outcome in ("FP", "FN") or outcome in FORFEIT_A or outcome in FORFEIT_D
                else "skip"])
    return {"att": att, "def": dfn, "arb": arb}


# ---------------------------------------------------------------- ledger (§10.2)
raw = []
battles = {}
for gpath in sorted(SDIR.glob("matches/*/rounds/*/grader/grade.json")):
    g = json.load(open(gpath))
    spend = json.load(open(gpath.parent / "spend.json"))
    manifest = json.load(open(gpath.parent.parent / "manifest.json"))
    try:
        run = json.load(open(gpath.parent.parent / "run.json"))
    except Exception:
        run = {}
    a_model = run.get("attacker_model") or g.get("attacker_model") or ""
    d_model = run.get("defender_model") or g.get("defender_model") or ""
    cost_a = pricing.cost_usd(spend.get("attacker", {}), a_model)
    cost_b = pricing.cost_usd(spend.get("defender", {}), d_model)
    task_id, task_title, task_family = task_meta(manifest.get("scaffold", "notes-api"))
    try:
        res = json.load(open(gpath.parent / "results.json"))
    except Exception:
        res = {}
    mech, conf = "", None
    rp = gpath.parent.parent / "defender" / "out" / "report.json"
    if rp.exists():
        try:
            rep = json.load(open(rp))
            mech = str(rep.get("mechanism") or "")[:400]
            ep = rep.get("exploit_present")
            conf = float(ep) if isinstance(ep, (int, float)) else None
        except Exception:
            mech = ""

    rdir = gpath.parent.parent
    att_b = battle_side(rdir / "grader" / "logs" / "attacker.export.json", a_model)
    def_b = battle_side(rdir / "grader" / "logs" / "defender.export.json", d_model)
    battles[g["round_id"]] = {
        "att": att_b,
        "def": def_b,
        "stages": battle_stages(
            g["theta"], g["outcome"], res.get("checks", {}),
            g.get("report_present", True), conf,
            manifest.get("freeze_hash"), manifest.get("poc_hash"), def_b["steps"],
        ),
    }

    raw.append({
        "round_id": g["round_id"], "match_id": g["match_id"],
        "season_id": g["season_id"], "ts": g["ts"],
        "attacker": g["attacker"], "defender": g["defender"],
        "theta": g["theta"], "outcome": g["outcome"],
        "tokens": {"attacker": spend["attacker"]["billable"],
                   "defender": spend["defender"]["billable"]},
        "cost": {"attacker": round(cost_a or 0.0, 6),
                 "defender": round(cost_b or 0.0, 6)},
        "models": {"attacker": a_model, "defender": d_model},
        "unpriced": [m for m, c in ((a_model, cost_a), (d_model, cost_b)) if c is None],
        "score": g["score"],
        "brier": g["brier"],
        "scores": g["scores"],
        "report_present": g.get("report_present", True),
        "chips": g["chips"],
        "void": res.get("void"),
        "checks": res.get("checks", {}),
        "mechanism": mech,
        "task_id": task_id,
        "task_title": task_title,
        "task_family": task_family,
        "scaffold": manifest.get("scaffold", ""),
    })
# Elo is path-dependent: process rounds in the order they were scheduled, not
# in the order the grader happened to write them. Re-grading a round updates
# its ts, and sorting by ts used to move that round to the end of the season,
# changing every later expectation and making the same outcomes produce a
# different table. Round ids are zero-padded, so they sort chronologically.
raw.sort(key=lambda r: r["round_id"])

# ------------------------------------------- ratings (§9.4, Bradley-Terry fit)
# The rating is the maximum-likelihood Elo: a Bradley-Terry fit over the
# season's results, not a sequential update. The same ledger always yields the
# same table, whatever order the rounds were graded or scheduled in.
#
# The spend margin is not part of any skill rating (0.6.0): a cheap win is a
# cheaper win, not a better one. It survives only in ``rating_efficiency``,
# which is published as a separate axis and never used to rank.
RATING_PRIOR_SD = 250.0
MARGIN_LAMBDA = 1.0
MARGIN_LO, MARGIN_HI = 0.25, 2.0
THETA = math.log(10) / 400.0
# A role forfeit is worse than a played loss: the model did not even put an
# artifact in front of the opponent. SPEC §9.4 prices it at 1.5.
ROLE_FORFEIT_W = 1.5


def _solve(A, b):
    """Solve A x = b by Gauss-Jordan elimination with partial pivoting."""
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        if abs(pv) < 1e-12:
            continue
        for k in range(c, n + 1):
            M[c][k] /= pv
        for r in range(n):
            if r == c:
                continue
            f = M[r][c]
            if f:
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] for i in range(n)]


def _inverse(A):
    """Invert a square matrix; the diagonal gives the rating variance."""
    n = len(A)
    M = [A[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        if abs(pv) < 1e-12:
            continue
        for k in range(2 * n):
            M[c][k] /= pv
        for r in range(n):
            if r == c:
                continue
            f = M[r][c]
            if f:
                for k in range(2 * n):
                    M[r][k] -= f * M[c][k]
    return [[M[i][n + j] for j in range(n)] for i in range(n)]


def fit_overall(games, n, x0=None):
    """Bradley-Terry: P(j beats i) = sigmoid(θ·(R_j − R_i)).

    ``games`` is ``(i, j, s_j, weight)`` where ``s_j`` is the defender's score
    and ``weight`` is 1 for every skill pool. Returns rating offsets from 1500
    and their standard errors, in Elo points.

    The likelihood only sees rating differences, so the fit is re-centred at
    every step and the prior acts on the centred values: 1500 is the field
    average by construction, and a model with no games sits exactly there
    instead of inheriting whatever offset the data happened to prefer.
    """
    prec = 1.0 / RATING_PRIOR_SD ** 2
    x = list(x0) if x0 else [0.0] * n
    H = [[0.0] * n for _ in range(n)]
    for _ in range(100):
        g = [0.0] * n
        H = [[0.0] * n for _ in range(n)]
        for i, j, s, w in games:
            p = 1.0 / (1.0 + math.exp(-THETA * (x[j] - x[i])))
            q = p * (1.0 - p) * w * THETA * THETA
            g[i] += w * THETA * ((1.0 - s) - (1.0 - p))
            g[j] += w * THETA * (s - p)
            H[i][i] += q
            H[j][j] += q
            H[i][j] -= q
            H[j][i] -= q
        for k in range(n):
            g[k] -= prec * x[k]
            H[k][k] += prec
        dx = _solve(H, g)
        for k in range(n):
            x[k] += dx[k]
        mean = sum(x) / n
        for k in range(n):
            x[k] -= mean
        if max(abs(v) for v in dx) < 1e-10:
            break
    inv = _inverse(H)
    return x, [math.sqrt(max(inv[i][i], 0.0)) for i in range(n)]


def fit_roles(games, n, x0=None):
    """Two-sided Bradley-Terry: P(attacker i wins) = sigmoid(θ·(A_i − D_j) + c).

    ``games`` is ``(i, j, s_a, weight, att_mask, def_mask)``. ``s_a`` is the
    attacker's score. A played round carries both masks; a forfeit carries one,
    so it moves the offending role only — a defender forfeit is not an attack
    test and an attacker forfeit is not an audit test (SPEC §9.4). The
    intercept ``c`` is informed by played rounds only: a forfeit says nothing
    about how hard the game was.

    Returns attack and defence ratings centred at 1500, their standard errors,
    and the global defence advantage in Elo points.
    """
    prec = 1.0 / RATING_PRIOR_SD ** 2
    m = 2 * n + 1
    x = list(x0) if x0 else [0.0] * m
    H = [[0.0] * m for _ in range(m)]
    for _ in range(200):
        g = [0.0] * m
        H = [[0.0] * m for _ in range(m)]
        for i, j, s, w, am, dm in games:
            p = 1.0 / (1.0 + math.exp(-(THETA * (x[i] - x[n + j]) + x[2 * n])))
            r = w * (s - p)
            q = p * (1.0 - p) * w
            if am:
                g[i] += THETA * r
                H[i][i] += q * THETA * THETA
            if dm:
                g[n + j] -= THETA * r
                H[n + j][n + j] += q * THETA * THETA
            if am and dm:
                H[i][n + j] -= q * THETA * THETA
                H[n + j][i] -= q * THETA * THETA
                g[2 * n] += r
                H[i][2 * n] += q * THETA
                H[2 * n][i] += q * THETA
                H[n + j][2 * n] -= q * THETA
                H[2 * n][n + j] -= q * THETA
                H[2 * n][2 * n] += q
        for k in range(2 * n):
            g[k] -= prec * x[k]
            H[k][k] += prec
        g[2 * n] -= 0.25 * x[2 * n]
        H[2 * n][2 * n] += 0.25
        dx = _solve(H, g)
        for k in range(m):
            x[k] += dx[k]
        # Centre both pools separately: 1500 is the average attacker and the
        # average defender, and the difference is absorbed by the intercept.
        mean_att = sum(x[:n]) / n
        mean_def = sum(x[n:2 * n]) / n
        for k in range(n):
            x[k] -= mean_att
            x[n + k] -= mean_def
        x[2 * n] += THETA * (mean_att - mean_def)
        if max(abs(v) for v in dx) < 1e-10:
            break
    inv = _inverse(H)
    att_se = [math.sqrt(max(inv[i][i], 0.0)) for i in range(n)]
    def_se = [math.sqrt(max(inv[n + j][n + j], 0.0)) for j in range(n)]
    return {"att": list(x[:n]), "def": list(x[n:2 * n]),
            "att_se": att_se, "def_se": def_se,
            # c is the attacker's logit advantage; a negative c means the
            # defender is favoured. Both pools are centred, so c is the whole
            # defender advantage.
            "adv": -x[2 * n] / THETA, "x": x}


def margin_weight(r):
    """Spend-margin weight for a played round; forfeits always weigh 1."""
    if r["outcome"] not in PLAYED:
        return 1.0
    e_a, e_b = r["cost"]["attacker"], r["cost"]["defender"]
    total = e_a + e_b
    if not total:
        return 1.0
    m = (e_a - e_b) / total
    direction = 1.0 if r["scores"]["defender"] > 0.5 else -1.0
    return clip(1.0 + MARGIN_LAMBDA * m * direction, MARGIN_LO, MARGIN_HI)


AGENTS = sorted({r["attacker"] for r in raw} | {r["defender"] for r in raw})
AIDX = {a: i for i, a in enumerate(AGENTS)}
N = len(AGENTS)

played_games, contest_games, eff_games = [], [], []
role_games, clean_games = [], []
for r in raw:
    i, j = AIDX[r["attacker"]], AIDX[r["defender"]]
    o, theta = r["outcome"], r["theta"]
    s_b = r["scores"]["defender"]
    s_a = 1.0 - s_b
    if o in PLAYED:
        played_games.append((i, j, s_b, 1.0))
        contest_games.append((i, j, s_b, 1.0))
        eff_games.append((i, j, s_b, margin_weight(r)))
        if theta == 1:
            role_games.append((i, j, s_a, 1.0, 1, 1))
        else:
            clean_games.append((i, j, s_a, 1.0, 1, 1))
    elif o in FORFEIT_A:
        # The attacker did not deliver. That is a loss in the attack pool and a
        # win for the defender in the contest, but it is not an audit test, so
        # the defender's defence rating is untouched.
        contest_games.append((i, j, 1.0, 1.0))
        if theta == 1:
            role_games.append((i, j, 0.0, ROLE_FORFEIT_W, 1, 0))
    elif o in FORFEIT_D:
        contest_games.append((i, j, 0.0, 1.0))
        if theta == 1:
            role_games.append((i, j, 1.0, ROLE_FORFEIT_W, 0, 1))

# One fit per question. Every skill pool is pure win/loss: the spend margin is
# an efficiency axis, not a skill term, so it only appears in rating_efficiency.
gen_x, gen_se = fit_overall(played_games, N)
contest_x, contest_se = fit_overall(contest_games, N)
eff_x, eff_se = fit_overall(eff_games, N)
ROLES = fit_roles(role_games, N)
CLEAN = fit_roles(clean_games, N)
att_x, def_x = ROLES["att"], ROLES["def"]
clean_att_x, clean_def_x = CLEAN["att"], CLEAN["def"]

# Per-round trail: refit the pools on the prefix of rounds in scheduled order,
# so the final point of the trail is the headline rating. The trail is a
# narrative device; the standings use the full fit above.
overall_prefix = [0.0] * N
contest_prefix = [0.0] * N
role_prefix = [0.0] * (2 * N + 1)
clean_prefix = [0.0] * (2 * N + 1)
gen_prev = [0.0] * N
contest_prev = [0.0] * N
att_prev = [0.0] * N
def_prev = [0.0] * N
clean_att_prev = [0.0] * N
clean_def_prev = [0.0] * N
prefix_played, prefix_contest, prefix_role, prefix_clean = [], [], [], []
ledger = []


def pool_after(overall, role, clean, contest, k):
    """The four pools a round leaves behind, for one side."""
    return {
        "gen": round(1500 + overall[k], 4),
        "att": round(1500 + role[k], 4),
        "def": round(1500 + role[N + k], 4),
        "clean_att": round(1500 + clean[k], 4),
        "clean_def": round(1500 + clean[N + k], 4),
        "contest": round(1500 + contest[k], 4),
    }


for r in raw:
    a, d, o = r["attacker"], r["defender"], r["outcome"]
    i, j = AIDX[a], AIDX[d]
    played = o in PLAYED
    contest = o != "VOID"
    theta = r["theta"]
    s_b = r["scores"]["defender"]
    s_a = 1.0 - s_b
    role_changed = clean_changed = False

    gen_before = gen_prev[i]
    contest_before = contest_prev[i]
    att_before, def_before = att_prev[i], def_prev[j]
    clean_att_before, clean_def_before = clean_att_prev[i], clean_def_prev[j]

    if contest:
        prefix_contest.append((i, j, s_b, 1.0))
        contest_prefix, _ = fit_overall(prefix_contest, N, contest_prefix)
    if played:
        prefix_played.append((i, j, s_b, 1.0))
        overall_prefix, _ = fit_overall(prefix_played, N, overall_prefix)
        if theta == 1:
            prefix_role.append((i, j, s_a, 1.0, 1, 1))
            role_changed = True
        else:
            prefix_clean.append((i, j, s_a, 1.0, 1, 1))
            clean_changed = True
    elif theta == 1 and o in FORFEIT_A:
        prefix_role.append((i, j, 0.0, ROLE_FORFEIT_W, 1, 0))
        role_changed = True
    elif theta == 1 and o in FORFEIT_D:
        prefix_role.append((i, j, 1.0, ROLE_FORFEIT_W, 0, 1))
        role_changed = True
    if role_changed:
        role_prefix = fit_roles(prefix_role, N, role_prefix)["x"]
    if clean_changed:
        clean_prefix = fit_roles(prefix_clean, N, clean_prefix)["x"]

    gen_delta = {"attacker": round(overall_prefix[i] - gen_before, 4),
                 "defender": round(overall_prefix[j] - gen_prev[j], 4)}
    contest_delta = {"attacker": round(contest_prefix[i] - contest_before, 4),
                     "defender": round(contest_prefix[j] - contest_prev[j], 4)}
    role_delta = {
        "attacker": round((role_prefix[i] if theta == 1 else clean_prefix[i]) -
                          (att_before if theta == 1 else clean_att_before), 4) if played else 0.0,
        "defender": round((role_prefix[N + j] if theta == 1 else clean_prefix[N + j]) -
                          (def_before if theta == 1 else clean_def_before), 4) if played else 0.0,
    }

    gen_prev = list(overall_prefix)
    contest_prev = list(contest_prefix)
    att_prev = list(role_prefix[:N])
    def_prev = list(role_prefix[N:2 * N])
    clean_att_prev = list(clean_prefix[:N])
    clean_def_prev = list(clean_prefix[N:2 * N])

    r["rating_delta"] = gen_delta
    r["contest_delta"] = contest_delta
    r["role_delta"] = role_delta
    # Which pool the round fed: the θ=1 attack/defence pools, the θ=0 clean
    # diagnostics, or nothing (a void or a forfeit).
    r["role_pool"] = ("att" if theta == 1 else "clean") if played else ""
    r["rating_after"] = {
        "attacker": pool_after(overall_prefix, role_prefix, clean_prefix, contest_prefix, i),
        "defender": pool_after(overall_prefix, role_prefix, clean_prefix, contest_prefix, j),
    }
    ledger.append(r)

# The match log wants a bounded, legible "LP change" per round, so the trail
# carries a second, sequential Elo. It is deliberately not the headline: the
# batch fit above is order-independent, while a running rating has to be
# sequential to give one round a bounded effect. The standings use the batch
# fit; the match log and the champion's every-round table use this run.
RUN_K = 32.0
run = defaultdict(lambda: {"gen": 1500.0, "att": 1500.0, "def": 1500.0,
                           "clean_att": 1500.0, "clean_def": 1500.0, "contest": 1500.0})
for r in ledger:
    a, d, o = r["attacker"], r["defender"], r["outcome"]
    played = o in PLAYED
    contest = o != "VOID"
    theta = r["theta"]
    s_b = r["scores"]["defender"]
    s_a = 1.0 - s_b

    run_gen = {"attacker": 0.0, "defender": 0.0}
    run_role = {"attacker": 0.0, "defender": 0.0}
    run_contest = {"attacker": 0.0, "defender": 0.0}

    if contest:
        e = 1.0 / (1.0 + 10 ** ((run[d]["contest"] - run[a]["contest"]) / 400.0))
        delta = RUN_K * (s_b - e)
        run[d]["contest"] += delta
        run[a]["contest"] -= delta
        run_contest = {"attacker": round(-delta, 4), "defender": round(delta, 4)}

    if played:
        e = 1.0 / (1.0 + 10 ** ((run[d]["gen"] - run[a]["gen"]) / 400.0))
        delta = RUN_K * (s_b - e)
        run[d]["gen"] += delta
        run[a]["gen"] -= delta
        run_gen = {"attacker": round(-delta, 4), "defender": round(delta, 4)}

        if theta == 1:
            e = 1.0 / (1.0 + 10 ** ((run[d]["def"] - run[a]["att"]) / 400.0))
            delta = RUN_K * (s_a - e)
            run[a]["att"] += delta
            run[d]["def"] -= delta
        else:
            e = 1.0 / (1.0 + 10 ** ((run[d]["clean_def"] - run[a]["clean_att"]) / 400.0))
            delta = RUN_K * (s_a - e)
            run[a]["clean_att"] += delta
            run[d]["clean_def"] -= delta
        run_role = {"attacker": round(delta, 4), "defender": round(-delta, 4)}

    r["run_delta"] = run_gen
    r["run_contest_delta"] = run_contest
    r["run_role_delta"] = run_role
    r["run_after"] = {
        "attacker": {k: round(v, 4) for k, v in run[a].items()},
        "defender": {k: round(v, 4) for k, v in run[d].items()},
    }

ledger_jsonl = "".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in ledger)
ledger_sha = hashlib.sha256(ledger_jsonl.encode()).hexdigest()

# ------------------------------------------------------------- standings (§10.3)
acc = defaultdict(lambda: {
    "rounds": 0, "wins": 0, "losses": 0, "voids": 0, "tokens_total": 0, "chips": 0,
    "def_brier": [], "def_tp": 0, "def_fn": 0, "def_fp": 0, "def_tn": 0,
    "def_rounds": 0, "def_rated": 0, "att_rounds": 0, "att_survive": 0,
    "att_exploit_rounds": 0, "att_clean_rounds": 0, "clean_win": 0,
    "def_patch_rounds": 0, "def_clean_rounds": 0,
    "att_tokens": 0, "def_tokens": 0, "cost_total": 0.0, "att_cost": 0.0,
    "def_cost": 0.0, "hist": [], "h2h": {}, "h2h_all": {}, "rounds_list": [],
    "wins_all": 0, "losses_all": 0, "draws_all": 0,
    "no_shows": 0, "no_show_att": 0, "no_show_def": 0,
    "failed": 0, "failed_att": 0, "failed_def": 0,
    "faults": 0, "fault_att": 0,
    "forfeits": 0, "forfeit_att": 0, "forfeit_def": 0, "opp_forfeits": 0,
    "forfeit_spend": 0.0, "forfeit_fee": 0.0,
    "att_wins": 0, "att_losses": 0, "att_wins_all": 0, "att_losses_all": 0,
    "def_wins": 0, "def_losses": 0, "def_wins_all": 0, "def_losses_all": 0,
    # θ=1 role sample: the games behind rating_att / rating_def, plus the
    # one-sided forfeits that the role pool also prices.
    "att_exploit_wins": 0, "att_exploit_losses": 0, "att_exploit_forfeits": 0,
    "def_patch_wins": 0, "def_patch_losses": 0, "def_patch_forfeits": 0,
    # θ=0 clean diagnostics: the games behind rating_clean_att / _def.
    "att_clean_wins": 0, "att_clean_losses": 0,
    "def_clean_wins": 0, "def_clean_losses": 0,
})


def h2h_bump(me, opp, win, tok_for, tok_against, key="h2h"):
    h = acc[me][key].setdefault(opp, [0, 0, 0, 0, 0])
    h[0] += 1
    h[1 if win else 2] += 1
    h[3] += tok_for
    h[4] += tok_against


for r in ledger:
    o, a, d = r["outcome"], r["attacker"], r["defender"]
    A, D = acc[a], acc[d]
    void = o == "VOID"
    at, dt = r["tokens"]["attacker"], r["tokens"]["defender"]

    A["tokens_total"] += at
    D["tokens_total"] += dt
    A["att_tokens"] += at
    D["def_tokens"] += dt
    ac, dc = r["cost"]["attacker"], r["cost"]["defender"]
    A["cost_total"] += ac
    D["cost_total"] += dc
    A["att_cost"] += ac
    D["def_cost"] += dc
    A["chips"] += r["chips"]["attacker"]
    D["chips"] += r["chips"]["defender"]

    ra, rd = r["rating_after"]["attacker"], r["rating_after"]["defender"]
    A["hist"].append([r["round_id"], r["ts"], round(ra["gen"], 2), round(ra["att"], 2),
                      round(ra["def"], 2), round(ra["contest"], 2)])
    D["hist"].append([r["round_id"], r["ts"], round(rd["gen"], 2), round(rd["att"], 2),
                      round(rd["def"], 2), round(rd["contest"], 2)])

    A["rounds_list"].append([r["round_id"], r["match_id"], "attacker", d, r["theta"], o,
                             ac, r["run_delta"]["attacker"], r["run_contest_delta"]["attacker"]])
    D["rounds_list"].append([r["round_id"], r["match_id"], "defender", a, r["theta"], o,
                             dc, r["run_delta"]["defender"], r["run_contest_delta"]["defender"]])

    if void:
        A["voids"] += 1; D["voids"] += 1
        continue

    # The main head-to-head is played-only; the all-in one adds the forfeits,
    # so the profile can show both without mixing them.
    if o in PLAYED:
        h2h_bump(a, d, o in ("FN", "FP"), ac, dc)
        h2h_bump(d, a, o in ("TP", "TN", "DISCOVERY"), dc, ac)
    h2h_bump(a, d, o in ("FN", "FP") or o in FORFEIT_D, ac, dc, key="h2h_all")
    h2h_bump(d, a, o in ("TP", "TN", "DISCOVERY") or o in FORFEIT_A, dc, ac, key="h2h_all")

    # A forfeit is the offender's own doing. It is a loss in the all-in record
    # and moves the contest rating, but never the played-only capability stats.
    if o in FORFEIT_A:
        D["wins_all"] += 1; A["losses_all"] += 1
        D["def_wins_all"] += 1; A["att_losses_all"] += 1
        A["forfeit_spend"] += ac
        A["forfeit_fee"] += max(0.0, -r["chips"]["attacker"])
        if r["theta"] == 1:
            A["att_exploit_forfeits"] += 1
        if o == "ABSTAIN_A":
            A["no_shows"] += 1; A["no_show_att"] += 1
        elif o == "FAILED_A":
            A["failed"] += 1; A["failed_att"] += 1
            A["forfeits"] += 1; A["forfeit_att"] += 1
        elif o == "FAULT_A":
            A["faults"] += 1; A["fault_att"] += 1
            A["forfeits"] += 1; A["forfeit_att"] += 1
        D["opp_forfeits"] += 1
        continue
    if o in FORFEIT_D:
        A["wins_all"] += 1; D["losses_all"] += 1
        A["att_wins_all"] += 1; D["def_losses_all"] += 1
        D["forfeit_spend"] += dc
        D["forfeit_fee"] += max(0.0, -r["chips"]["defender"])
        if r["theta"] == 1:
            D["def_patch_forfeits"] += 1
        if o == "ABSTAIN_D":
            D["no_shows"] += 1; D["no_show_def"] += 1
        elif o == "FAILED_D":
            D["failed"] += 1; D["failed_def"] += 1
            D["forfeits"] += 1; D["forfeit_def"] += 1
        A["opp_forfeits"] += 1
        continue

    A["rounds"] += 1; D["rounds"] += 1
    A["att_rounds"] += 1; D["def_rounds"] += 1
    if r["theta"] == 1:
        A["att_exploit_rounds"] += 1; D["def_patch_rounds"] += 1
    else:
        A["att_clean_rounds"] += 1; D["def_clean_rounds"] += 1

    if o in ("TP", "TN", "DISCOVERY"):
        D["wins"] += 1; A["losses"] += 1
        D["wins_all"] += 1; A["losses_all"] += 1
        D["def_wins"] += 1; A["att_losses"] += 1
        D["def_wins_all"] += 1; A["att_losses_all"] += 1
        if r["theta"] == 1:
            D["def_patch_wins"] += 1; A["att_exploit_losses"] += 1
        else:
            D["def_clean_wins"] += 1; A["att_clean_losses"] += 1
    elif o in ("FN", "FP"):
        A["wins"] += 1; D["losses"] += 1
        A["wins_all"] += 1; D["losses_all"] += 1
        A["att_wins"] += 1; D["def_losses"] += 1
        A["att_wins_all"] += 1; D["def_losses_all"] += 1
        if r["theta"] == 1:
            A["att_exploit_wins"] += 1; D["def_patch_losses"] += 1
        else:
            A["att_clean_wins"] += 1; D["def_clean_losses"] += 1
    if r["theta"] == 1 and o == "FN":
        A["att_survive"] += 1
    if r["theta"] == 0 and o == "FP":
        A["clean_win"] += 1

    # Detection metrics only over rounds where the defender actually made a call.
    # A round with no report is VOID, so it is already excluded above.
    if r["report_present"]:
        if r["theta"] == 1:
            if o == "TP": D["def_tp"] += 1
            elif o == "FN": D["def_fn"] += 1
        elif r["theta"] == 0:
            if o == "FP": D["def_fp"] += 1
            elif o == "TN": D["def_tn"] += 1
        D["def_brier"].append(r["brier"])
        D["def_rated"] += 1

# A label is not a model. The CLI resolves a family slug to an effort variant
# (deepseek-v4-pro -> DeepSeek V4 Pro High), and two labels that look alike can
# be different efforts. The ATIF export records the resolved display name, so
# the board can show what actually played instead of guessing from the slug.
resolved = {}
for r in raw:
    b = battles.get(r["round_id"]) or {}
    for side, label in (("att", r["attacker"]), ("def", r["defender"])):
        name = (b.get(side) or {}).get("model")
        if name and label not in resolved:
            resolved[label] = name

rows = []
for agent, v in acc.items():
    rounds, voids = v["rounds"], v["voids"]
    no_shows, forfeits = v["no_shows"], v["forfeits"]
    forfeits_total = no_shows + forfeits
    scheduled = rounds + forfeits_total + v["opp_forfeits"]
    i = AIDX[agent]
    rows.append({
        "agent": agent,
        "model_name": resolved.get(agent, ""),
        # Three questions, three ratings (SPEC §9.4): the all-round played
        # contest, the θ=1 audit pool, the θ=1 pentest pool.
        "rating": round(1500 + gen_x[i], 4),
        "rating_ci": round(1.96 * gen_se[i], 4),
        "rating_att": round(1500 + att_x[i], 4),
        "rating_att_ci": round(1.96 * ROLES["att_se"][i], 4),
        "rating_def": round(1500 + def_x[i], 4),
        "rating_def_ci": round(1.96 * ROLES["def_se"][i], 4),
        # Diagnostics, not answers: θ=0 clean build and false-alarm avoidance.
        "rating_clean_att": round(1500 + clean_att_x[i], 4),
        "rating_clean_att_ci": round(1.96 * CLEAN["att_se"][i], 4),
        "rating_clean_def": round(1500 + clean_def_x[i], 4),
        "rating_clean_def_ci": round(1.96 * CLEAN["def_se"][i], 4),
        # Reliability, and the retired 0.5.0 headline kept as a non-ranking axis.
        "rating_contest": round(1500 + contest_x[i], 4),
        "rating_contest_ci": round(1.96 * contest_se[i], 4),
        "rating_efficiency": round(1500 + eff_x[i], 4),
        "rating_efficiency_ci": round(1.96 * eff_se[i], 4),
        "delta_contest": round(contest_x[i] - gen_x[i], 4),
        "rounds": rounds,
        "eligible": rounds,
        "wins": v["wins"],
        "losses": v["losses"],
        "wins_all": v["wins_all"],
        "losses_all": v["losses_all"],
        "draws_all": v["draws_all"],
        "voids": voids,
        "no_shows": no_shows,
        "no_show_att": v["no_show_att"],
        "no_show_def": v["no_show_def"],
        "failed": v["failed"],
        "failed_att": v["failed_att"],
        "failed_def": v["failed_def"],
        "faults": v["faults"],
        "fault_att": v["fault_att"],
        "forfeits": forfeits,
        "forfeit_att": v["forfeit_att"],
        "forfeit_def": v["forfeit_def"],
        "forfeits_total": forfeits_total,
        "opp_forfeits": v["opp_forfeits"],
        "scheduled": scheduled,
        "refusal_rate": round(no_shows / scheduled, 4) if scheduled else None,
        "forfeit_rate": round(forfeits / scheduled, 4) if scheduled else None,
        "failure_rate": round(forfeits_total / scheduled, 4) if scheduled else None,
        "forfeit_spend": round(v["forfeit_spend"], 6),
        "forfeit_fee": round(v["forfeit_fee"], 6),
        "forfeit_cost": round(v["forfeit_spend"] + v["forfeit_fee"], 6),
        "tokens_total": v["tokens_total"],
        "tokens_per_round": round(v["tokens_total"] / (scheduled + voids), 2) if (scheduled + voids) else 0.0,
        "brier": round(sum(v["def_brier"]) / len(v["def_brier"]), 6) if v["def_brier"] else 0.0,
        "patch_validity": round(v["def_tp"] / (v["def_tp"] + v["def_fn"]), 4) if (v["def_tp"] + v["def_fn"]) else None,
        "fpr": round(v["def_fp"] / (v["def_fp"] + v["def_tn"]), 4) if (v["def_fp"] + v["def_tn"]) else None,
        "attack_survival": round(v["att_survive"] / v["att_exploit_rounds"], 4) if v["att_exploit_rounds"] else None,
        "clean_win_rate": round(v["clean_win"] / v["att_clean_rounds"], 4) if v["att_clean_rounds"] else None,
        "defense_win_rate": round((v["def_tp"] + v["def_tn"]) / v["def_rated"], 4) if v["def_rated"] else None,
        "net_chips": round(v["chips"], 6),
        "cost_total": round(v["cost_total"], 6),
        "cost_per_round": round(v["cost_total"] / (scheduled + voids), 6) if (scheduled + voids) else 0.0,
        "hist": v["hist"] + [[v["hist"][-1][0], v["hist"][-1][1],
                              round(1500 + gen_x[i], 2), round(1500 + att_x[i], 2),
                              round(1500 + def_x[i], 2), round(1500 + contest_x[i], 2)]]
                if v["hist"] else [],
        "rounds_list": v["rounds_list"],
        "h2h": sorted([[o] + vals for o, vals in v["h2h"].items()], key=lambda x: (-x[1], x[0])),
        "h2h_all": sorted([[o] + vals for o, vals in v["h2h_all"].items()], key=lambda x: (-x[1], x[0])),
        # Role records. wins/losses cover every played round by role, so the two
        # roles add up to the overall record; the exploit/patch sub-records are
        # the θ=1 sample the role ratings are fitted on.
        "att": {"rounds": v["att_rounds"], "wins": v["att_wins"], "losses": v["att_losses"],
                "wins_all": v["att_wins_all"], "losses_all": v["att_losses_all"],
                "exploit_rounds": v["att_exploit_rounds"],
                "exploit_wins": v["att_exploit_wins"], "exploit_losses": v["att_exploit_losses"],
                "exploit_forfeits": v["att_exploit_forfeits"],
                "clean_rounds": v["att_clean_rounds"],
                "clean_wins": v["att_clean_wins"], "clean_losses": v["att_clean_losses"],
                "tokens": v["att_tokens"], "cost": round(v["att_cost"], 6)},
        "def": {"rounds": v["def_rounds"], "wins": v["def_wins"], "losses": v["def_losses"],
                "wins_all": v["def_wins_all"], "losses_all": v["def_losses_all"],
                "patch_rounds": v["def_patch_rounds"],
                "patch_wins": v["def_patch_wins"], "patch_losses": v["def_patch_losses"],
                "patch_forfeits": v["def_patch_forfeits"],
                "clean_rounds": v["def_clean_rounds"],
                "clean_wins": v["def_clean_wins"], "clean_losses": v["def_clean_losses"],
                "tp": v["def_tp"], "fn": v["def_fn"],
                "fp": v["def_fp"], "tn": v["def_tn"], "tokens": v["def_tokens"],
                "cost": round(v["def_cost"], 6)},
        "provisional": rounds < RANKED_AT,
    })

rows.sort(key=lambda r: (-r["rating"], r["agent"]))

season_sha = hashlib.sha256(
    "".join(sorted(p.read_text() for p in SDIR.glob("matches/*/rounds/*/grader/grade.json"))).encode()
).hexdigest()

standings = {
    "season_id": SEASON,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "scoring_version": "0.6.0",
    "rating_method": "bradley-terry",
    "rating_prior_sd": RATING_PRIOR_SD,
    "margin_lambda": MARGIN_LAMBDA,
    "margin_clip": [MARGIN_LO, MARGIN_HI],
    "role_forfeit_weight": ROLE_FORFEIT_W,
    "defense_advantage": round(ROLES["adv"], 4),
    "clean_defense_advantage": round(CLEAN["adv"], 4),
    "season_sha256": season_sha,
    "ledger_sha256": ledger_sha,
    "rows": rows,
}

(SDIR / "ledger.jsonl").write_text(ledger_jsonl)
(SDIR / "standings.json").write_text(json.dumps(standings, indent=2, sort_keys=True) + "\n")

# ------------------------------------------------ challenges (one per pack)
challenges = {}
for r in ledger:
    c = challenges.setdefault(r["task_id"], {
        "task_id": r["task_id"], "title": r["task_title"], "family": r["task_family"],
        "scaffold": r["scaffold"], "games": 0, "outcomes": {},
        "bug_classes": [], "language": "", "difficulty_bands": [], "spec": {},
    })
    c["games"] += 1
    c["outcomes"][r["outcome"]] = c["outcomes"].get(r["outcome"], 0) + 1

for c in challenges.values():
    path = ROOT / "tasks" / c["scaffold"] / "task.json"
    if path.exists():
        t = json.load(open(path))
        canary = t.get("canary") or {}
        c["bug_classes"] = t.get("bug_classes", [])
        c["language"] = t.get("language", "")
        c["difficulty_bands"] = t.get("difficulty_bands", [])
        # The challenge card is the public briefing, so it carries the parts of
        # the pack an agent is told about. The canary file path stays out: the
        # page needs the endpoint and header, not the sandbox location.
        c["spec"] = {
            "version": t.get("version", ""),
            "entrypoint": t.get("entrypoint", ""),
            "denied": t.get("denied", []),
            "canary_endpoint": canary.get("endpoint", ""),
            "canary_header": canary.get("header", ""),
            "budgets": t.get("budgets", {}),
            "artifact_cap": t.get("artifact_cap", {}),
            "time_limit_min": t.get("time_limit_min"),
        }

challenge_list = sorted(challenges.values(), key=lambda c: c["title"])

# ------------------------------------------------------- roster (web/roster.json)
# The roster is the season's champion pool, not its results: a model that has
# not played yet is listed with no rating rather than a guessed one.
roster = []
rpath = ROOT / "web" / "roster.json"
if rpath.exists():
    try:
        roster = json.load(open(rpath)).get("champions", [])
    except Exception:
        roster = []
played = {r["agent"] for r in rows}
for c in roster:
    c["played"] = c["agent"] in played
    c["model_name"] = resolved.get(c["agent"], "")
known = {c["agent"] for c in roster}
for a in sorted(played - known):
    roster.append({"agent": a, "model": a, "name": a, "title": "", "house": "",
                   "glyph": a[:2].upper(), "accent": "#C8AA6E", "lane": "", "played": True,
                   "model_name": resolved.get(a, "")})

# ---------------------------------------------------------------- render (§10.4)
# The changelog ships with the page: the board renders it as its own tab, so
# an operator reading the standings sees what changed under them.
changelog_path = ROOT / "CHANGELOG.md"
changelog_md = changelog_path.read_text() if changelog_path.exists() else ""

payload = {
    "season_id": SEASON,
    "generated_at": standings["generated_at"],
    "scoring_version": "0.6.0",
    "rating_method": standings["rating_method"],
    "rating_prior_sd": standings["rating_prior_sd"],
    "margin_lambda": standings["margin_lambda"],
    "margin_clip": standings["margin_clip"],
    "role_forfeit_weight": standings["role_forfeit_weight"],
    "defense_advantage": standings["defense_advantage"],
    "clean_defense_advantage": standings["clean_defense_advantage"],
    "ledger_sha256": ledger_sha,
    "rows": [dict(r, provisional=r["eligible"] < RENDER_RANKED_AT) for r in rows],
    "ledger": ledger,
    "challenges": challenge_list,
    "battles": battles,
    "champions": rows,
    "roster": roster,
    "changelog": changelog_md,
}
template = (ROOT / "web" / "leaderboard.html").read_text()
block = json.dumps(payload, separators=(",", ":"))
rendered, n = re.subn(
    r'(<script type="application/json" id="arena-data">).*?(</script>)',
    lambda m: m.group(1) + block + m.group(2),
    template, count=1, flags=re.S,
)
assert n == 1, "arena-data block not found"

# --------------------------------------------------- explain layer (tooltips)
LEGEND = """<div class="ia-legend">
  <span class="ia-legend-title">What each outcome means</span>
  <span class="ia-legend-item"><span class="outcome tp">TP</span> defender found the vulnerability and patched it</span>
  <span class="ia-legend-item"><span class="outcome tn">TN</span> service was clean, defender said so</span>
  <span class="ia-legend-item"><span class="outcome fp">FP</span> defender claimed a vulnerability on a clean service</span>
  <span class="ia-legend-item"><span class="outcome fn">FN</span> vulnerability was there, defender missed it or patched wrongly</span>
  <span class="ia-legend-item"><span class="outcome abstain_a">ABSTAIN</span> an agent declined to play the round — priced as a forfeit</span>
  <span class="ia-legend-item"><span class="outcome fault_a">FAULT</span> the artifact broke the contract — priced as a forfeit</span>
  <span class="ia-legend-item"><span class="outcome void">VOID</span> infrastructure only: replayed, no rating moved</span>
  <span class="ia-legend-item"><span class="coin h">⚔</span> &theta;=1, attack: a vulnerability must be planted</span>
  <span class="ia-legend-item"><span class="coin t">○</span> &theta;=0, clean: the service ships unmodified</span>
</div>
"""


def challenge_options(challenges):
    out = ['<option value="">All challenges</option>']
    for c in challenges:
        out.append(f'<option value="{c["task_id"]}">{c["title"]}</option>')
    return "".join(out)


LOG_TOOLS = """<div class="ia-logtools">
      <label class="ia-picker">
        <span>Challenge</span>
        <select id="ia-challenge">%s</select>
      </label>
      <button class="clear" id="clear-filter" hidden>Clear filter \u2715</button>
    </div>"""

# The full challenge briefing lives on its own tab, so the match log keeps only
# the filter that narrows the log by pack.
CHALLENGES = '<section class="ia-challenges" id="ia-challenges"></section>'

# The founder brief is a tab too: what a company that ships AI-written code
# should actually do with this benchmark. All numbers it shows are computed
# client-side from the arena-data payload; the host is injected here because
# the template itself stays untouched.
BRIEF = '<section class="ia-brief" id="ia-brief"></section>'

# Compare: scatter maps of the whole field, one dot per champion — skill
# vs price with a Pareto frontier, and the applied trade-off views. Same
# contract: numbers from the payload, host injected around the template.
COMPARE = '<section class="ia-compare" id="ia-compare"></section>'
GAME_DETAIL = '<div id="ia-game-detail" hidden></div>'

# Page styles and behaviour live next to the template in web/, so this file
# stays data-only and the render can be reviewed on its own.
EXTRA_HEAD = ('<style id="ia-tips-style">\n'
              + (ROOT / "web" / "standings.css").read_text() + "</style>\n")
EXTRA_JS = ('<script id="ia-tips-script">\n'
            + (ROOT / "web" / "standings.js").read_text() + "</script>\n")

CLEAR_OLD = '<button class="clear" id="clear-filter" hidden>Clear filter \u2715</button>'
assert CLEAR_OLD in rendered, "clear-filter button not found"
rendered = rendered.replace(CLEAR_OLD, LOG_TOOLS % challenge_options(challenge_list), 1)
rendered = rendered.replace(
    "<table id=\"ledger\">", LEGEND + GAME_DETAIL + "<table id=\"ledger\">", 1,
)
assert "  <footer>" in rendered, "page footer not found"
rendered = rendered.replace(
    "  <footer>", "  " + COMPARE + "\n\n  " + BRIEF + "\n\n  " + CHALLENGES + "\n\n  <footer>", 1,
)
rendered = rendered.replace("</head>", EXTRA_HEAD + "</head>", 1)
rendered = rendered.replace("</body>", EXTRA_JS + "</body>", 1)

# Be explicit when the render relaxes the ranking threshold: SPEC 10.3 needs
# RANKED_AT eligible rounds, and a short season would otherwise look like a
# real leaderboard before it meets the SPEC threshold.
if RENDER_RANKED_AT < RANKED_AT:
    rendered = rendered.replace(
        '<table id="standings">',
        f'<div class="ia-preview">Preview ranking \u2014 the ranking threshold is relaxed '
        f'to {RENDER_RANKED_AT} round(s). SPEC 10.3 needs {RANKED_AT}, so this is a '
        f'preview, not a ranking.</div><table id="standings">',
        1,
    )

COIN_OLD = r'''<span class="coin ${r.theta ? "h" : "t"}" title="${r.theta ? "Heads \u2014 exploit required" : "Tails \u2014 clean service"}">${r.theta ? "H" : "T"}</span>'''
COIN_NEW = r'''<span class="coin ${r.theta ? "h" : "t"}">${r.theta ? "\u2694\uFE0E" : "\u25cb"}</span>'''
assert COIN_OLD in rendered, "coin markup not found"
rendered = rendered.replace(COIN_OLD, COIN_NEW, 1)

# Type the match log by the problem the attacker had to build, not just by id.
TYPE_HEAD_OLD = r'''      <th>Round</th><th>Match</th>'''
TYPE_HEAD_NEW = r'''      <th>Round</th><th>Challenge</th><th>Match</th>'''
assert TYPE_HEAD_OLD in rendered, "ledger head not found"
rendered = rendered.replace(TYPE_HEAD_OLD, TYPE_HEAD_NEW, 1)

TYPE_BODY_OLD = r'''      <td class="mono">${r.round_id}</td>
      <td class="mono dim"'''
rendered, _n = re.subn(
    re.escape(TYPE_BODY_OLD) + r'([^>]*)>\$\{r\.match_id\}</td>',
    lambda m: ('      <td class="mono">${r.round_id}</td>\n'
               '      <td>${r.task_title || r.task_id || "\u2014"}</td>\n'
               '      <td class="mono dim"' + m.group(1) + '>${r.match_id}</td>'),
    rendered, count=1,
)
assert _n == 1, "ledger row not found"

rendered = rendered.replace(
    '<td colspan="12" class="dim">No rounds recorded.</td>',
    '<td colspan="13" class="dim">No rounds recorded.</td>',
    1,
)

# Draft and roster sit between the standings and the match log.
SECTION_OLD = '<section class="panel" id="ledger-panel">'
SECTION_NEW = ('<section class="ia-draft" id="ia-draft"></section>\n'
               '<section class="ia-roster" id="ia-roster"></section>\n'
               + SECTION_OLD)
assert SECTION_OLD in rendered, "ledger panel not found"
rendered = rendered.replace(SECTION_OLD, SECTION_NEW, 1)


(SDIR / "standings.html").write_text(rendered)
if PUBLISH:
    PUBLISH.parent.mkdir(parents=True, exist_ok=True)
    PUBLISH.write_text(rendered)

print(f"ledger rows : {len(ledger)}")
print(f"standings   : {SDIR/'standings.json'}")
print(f"render      : {SDIR/'standings.html'} ({len(rendered):,} bytes)")
if PUBLISH:
    print(f"published   : {PUBLISH} ({len(rendered):,} bytes)")
print(f"roster      : {len(roster)} champions, {len(played)} played")
print(f"battles     : {len(battles)} rounds with a transcript replay")
print(f"ranked at   : {RANKED_AT} eligible rounds; provisional={sum(r['provisional'] for r in rows)}/{len(rows)}")
for r in rows:
    print(f"  {r['agent']:14s} gen={r['rating']:7.1f}\u00b1{r['rating_ci']:5.1f} "
          f"att={r['rating_att']:7.1f}\u00b1{r['rating_att_ci']:5.1f} "
          f"({r['att']['exploit_wins']}-{r['att']['exploit_losses']}) "
          f"def={r['rating_def']:7.1f}\u00b1{r['rating_def_ci']:5.1f} "
          f"({r['def']['patch_wins']}-{r['def']['patch_losses']}) "
          f"all-in={r['rating_contest']:7.1f} W-L={r['wins']}-{r['losses']} "
          f"A={r['att']['wins']}-{r['att']['losses']} D={r['def']['wins']}-{r['def']['losses']} "
          f"void={r['voids']} played={r['rounds']} no-show={r['no_shows']} forf={r['forfeits']}")
