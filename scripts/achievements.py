"""Achievements — data-driven model badges for the board.

Each badge is awarded by a rule over the aggregated standings rows, so the
holders recompute from the season data and are never hand-written. The art is
an SVG in ``web/badges/<key>.svg`` (generated once with Ideogram Vector). The
page references it as ``<img src="badges/<key>.svg">`` rather than inlining it:
the browser rasterises each badge once, which keeps the DOM light and avoids
the ``g0``/``g1`` gradient-id collisions that inlining ten of them would cause.

Public entry point: ``compute(rows, badges_dir)`` returns the render-ready
``achievements`` list and annotates each row in place with a ``badges`` list
(the keys that model holds).
"""


def _num(row, key):
    v = row.get(key)
    return None if v is None else v


def _provisional(row):
    return bool(row.get("provisional"))


# -- award rules ------------------------------------------------------------
# Each rule returns the list of winning agent names for a badge, given the
# rows. ``stat`` formats the number the board prints next to the holder.

def _argbest(rows, field, lo=False, flt=None):
    cand = [r for r in rows if (flt is None or flt(r)) and _num(r, field) is not None]
    if not cand:
        return []
    cand.sort(key=lambda r: _num(r, field), reverse=not lo)
    return [cand[0]["agent"]]


def _plays(min_rounds):
    return lambda r: r.get("rounds", 0) >= min_rounds


# key -> metadata + rule. Order is the display order on the Answers screen.
# tone: good (gold/teal), warn (threat, read as risk), caution (desaturated).
ACHIEVEMENTS = [
    {
        "key": "champion", "emoji": "\U0001F451", "name": "Champion", "tone": "good",
        "question": "Which model overall, day to day?",
        "tagline": "#1 overall skill rating.",
        "stat_field": "rating", "stat_fmt": "rating",
        "rule": lambda rows: _argbest(rows, "rating"),
    },
    {
        "key": "gatekeeper", "emoji": "\U0001F6E1️", "name": "Gatekeeper", "tone": "good",
        "question": "Who should review my code?",
        "tagline": "Best auditor — top audit rating.",
        "stat_field": "rating_def", "stat_fmt": "rating",
        "rule": lambda rows: _argbest(rows, "rating_def"),
    },
    {
        "key": "sniper", "emoji": "\U0001F3AF", "name": "The Sniper", "tone": "good",
        "question": "Whose verdict is best calibrated?",
        "tagline": "Sharpest detection — lowest Brier score.",
        "stat_field": "brier", "stat_fmt": "brier",
        "rule": lambda rows: _argbest(rows, "brier", lo=True, flt=_plays(10)),
    },
    {
        "key": "best-value", "emoji": "\U0001F48E", "name": "Best Value", "tone": "good",
        "question": "Best skill per dollar?",
        "tagline": "Top efficiency rating at proven skill.",
        "stat_field": "rating_efficiency", "stat_fmt": "rating",
        "rule": lambda rows: _argbest(rows, "rating_efficiency", flt=lambda r: not _provisional(r)),
    },
    {
        "key": "featherweight", "emoji": "\U0001FAB6", "name": "Featherweight", "tone": "good",
        "question": "Cheapest model that still plays?",
        "tagline": "Lowest spend per round.",
        "stat_field": "cost_per_round", "stat_fmt": "usd",
        "rule": lambda rows: _argbest(rows, "cost_per_round", lo=True,
                                      flt=lambda r: r.get("rounds", 0) >= 10 and (_num(r, "refusal_rate") or 0) < 0.5),
    },
    {
        "key": "never-folds", "emoji": "\U0001F91D", "name": "Never Folds", "tone": "good",
        "question": "Which model always shows up?",
        "tagline": "Near-zero refusals, and strong with it.",
        "stat_field": "refusal_rate", "stat_fmt": "pct",
        "rule": lambda rows: _argbest(rows, "rating",
                                      flt=lambda r: _num(r, "refusal_rate") is not None
                                      and _num(r, "refusal_rate") <= 0.03 and r.get("rounds", 0) >= 20),
    },
    {
        "key": "infiltrator", "emoji": "\U0001F977", "name": "The Infiltrator", "tone": "warn",
        "question": "Who can hide a working bug from review?",
        "tagline": "Strongest red team — read this as a risk.",
        "stat_field": "rating_att", "stat_fmt": "rating",
        # two holders: best attacker rating, and best at slipping a bug past audit
        "rule": lambda rows: list(dict.fromkeys(
            _argbest(rows, "rating_att") + _argbest(rows, "attack_survival", flt=_plays(10)))),
    },
    {
        "key": "panicker", "emoji": "\U0001F6A8", "name": "The Panicker", "tone": "caution",
        "question": "Who cries wolf on clean code?",
        "tagline": "Highest false-alarm rate on clean services.",
        "stat_field": "fpr", "stat_fmt": "pct",
        "rule": lambda rows: _argbest(rows, "fpr", flt=_plays(10)),
    },
    {
        "key": "flake", "emoji": "\U0001F3F3️", "name": "The Flake", "tone": "caution",
        "question": "Who refuses to play (a missed bug in prod)?",
        "tagline": "Highest refusal / no-show rate.",
        "stat_field": "refusal_rate", "stat_fmt": "pct",
        "rule": lambda rows: _argbest(rows, "refusal_rate", flt=_plays(8)),
    },
    {
        "key": "locksmith", "emoji": "\U0001F512", "name": "The Locksmith", "tone": "good",
        "question": "Whose patch always blocks the exploit?",
        "tagline": "Every patch defused the proof-of-concept.",
        "stat_field": "patch_validity", "stat_fmt": "pct",
        "rule": lambda rows: [r["agent"] for r in rows
                              if (_num(r, "patch_validity") or 0) >= 1.0 and r.get("rounds", 0) >= 20],
    },
]


# -- stat formatting --------------------------------------------------------

def _fmt(kind, v):
    if v is None:
        return "—"
    if kind == "rating":
        return f"{v:.0f}"
    if kind == "brier":
        return f"{v:.3f}"
    if kind == "usd":
        return f"${v:.3f}"
    if kind == "pct":
        return f"{round(v * 100)}%"
    return str(v)


# -- entry point ------------------------------------------------------------

def compute(rows, badges_dir):
    """Return the render-ready ``achievements`` list; annotate each row.

    Each achievement carries its holders (with a formatted stat) and the
    relative path to its badge art, which the page loads with ``<img>``. Each
    row gains a ``badges`` list of the keys that model holds.
    """
    by_agent = {r["agent"]: r for r in rows}
    for r in rows:
        r.setdefault("badges", [])

    achievements = []
    for spec in ACHIEVEMENTS:
        holders = [a for a in spec["rule"](rows) if a in by_agent]
        for a in holders:
            if spec["key"] not in by_agent[a]["badges"]:
                by_agent[a]["badges"].append(spec["key"])

        has_art = (badges_dir / f"{spec['key']}.svg").exists()
        achievements.append({
            "key": spec["key"], "emoji": spec["emoji"], "name": spec["name"],
            "tone": spec["tone"], "question": spec["question"], "tagline": spec["tagline"],
            "stat_field": spec["stat_field"],
            "badge": f"badges/{spec['key']}.svg" if has_art else None,
            "holders": [{
                "agent": a,
                "model_name": by_agent[a].get("model_name", ""),
                "stat": _fmt(spec["stat_fmt"], _num(by_agent[a], spec["stat_field"])),
                "provisional": _provisional(by_agent[a]),
            } for a in holders],
        })
    return achievements
