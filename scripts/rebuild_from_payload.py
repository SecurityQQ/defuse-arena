#!/usr/bin/env python3
"""Rebuild a season's round directories from the arena-data payload it published.

The seasons/ tree is runtime data and is not in git; when the tree is gone but
the published board is not, the board's ledger is the surviving record. This
writes the six files standings.py reads for every round, solving the spend split
so that the recomputed USD cost and billable tokens land exactly on the recorded
ones, plus the round's published replay as battle.json, which standings.py uses
when the round has no agent exports.

usage: rebuild_from_payload.py <payload-html> <out-season-dir>
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing  # noqa: E402


def load_payload(path):
    html = Path(path).read_text()
    m = re.search(r'<script type="application/json" id="arena-data">(.*?)</script>', html, re.S)
    if not m:
        sys.exit(f"no arena-data block in {path}")
    return json.loads(m.group(1))


def solve_spend(billable, cost, price):
    """(prompt, cached, completion) reproducing billable tokens and USD cost.

    billable = (prompt - cached) + completion, so cached prompt is free to carry
    part of the bill at the cached rate. Two unknowns, one equation, so the
    completion count is swept around its cheapest fit and cached closes the gap;
    the sweep is what lands the cost on its 1e-6 grid.
    """
    p0, p1, p2 = price
    target = cost * 1e6
    B = p2 - p0
    if B == 0 or p1 <= 0:
        return None
    A = target - billable * p0
    k0 = int(round(min(max(A / B, 0.0), float(billable))))
    for dk in range(0, 4000):
        for k in (k0 - dk, k0 + dk):
            if k < 0 or k > billable:
                continue
            c = (A - k * B) / p1
            if c < 0:
                continue
            c = int(round(c))
            u = billable - k
            if round((u * p0 + c * p1 + k * p2) / 1e6, 6) == round(cost, 6):
                return {"prompt": u + c, "cached": c, "completion": k,
                        "total": u + c + k, "billable": billable}
    return None


def main(html, outdir):
    payload = load_payload(html)
    out = Path(outdir)
    bad = []
    for r in payload["ledger"]:
        rd = out / "matches" / r["match_id"] / "rounds" / r["round_id"]
        (rd / "grader" / "logs").mkdir(parents=True, exist_ok=True)
        (rd / "defender" / "out").mkdir(parents=True, exist_ok=True)

        spend = {}
        for side in ("attacker", "defender"):
            model = r["models"][side]
            p = pricing.price(model)
            if p is None:
                bad.append((r["round_id"], side, "unpriced"))
                spend[side] = {"prompt": 0, "cached": 0, "completion": 0,
                               "total": r["tokens"][side], "billable": r["tokens"][side]}
                continue
            row = solve_spend(r["tokens"][side], r["cost"][side], p)
            if row is None:
                bad.append((r["round_id"], side, f"no split for {r['tokens'][side]} / {r['cost'][side]}"))
                row = {"prompt": 0, "cached": 0, "completion": 0,
                       "total": r["tokens"][side], "billable": r["tokens"][side]}
            spend[side] = row

        grade = {k: r[k] for k in ("round_id", "match_id", "season_id", "attacker",
                                   "defender", "theta", "outcome", "score", "brier",
                                   "scores", "chips", "cost", "report_present", "ts")}
        grade["scoring_version"] = payload["scoring_version"]
        grade["tests_pass"] = bool(r["checks"].get("smoke_unpatched"))
        grade["poc_unpatched"] = r["checks"].get("poc_unpatched")
        grade["poc_patched"] = r["checks"].get("poc_patched")

        (rd / "grader" / "grade.json").write_text(json.dumps(grade, indent=2, sort_keys=True))
        (rd / "grader" / "results.json").write_text(json.dumps({
            "status": "graded", "void": r["void"], "outcome": r["outcome"],
            "theta": r["theta"], "brier": r["brier"], "score": r["score"],
            "scores": r["scores"], "report_present": r["report_present"],
            "spend": r["tokens"], "chips": r["chips"], "cost": r["cost"],
            "checks": r["checks"],
        }, indent=2, sort_keys=True))
        (rd / "grader" / "spend.json").write_text(json.dumps(spend, indent=2, sort_keys=True))
        (rd / "manifest.json").write_text(json.dumps({
            "round_id": r["round_id"], "theta": r["theta"], "scaffold": r["scaffold"],
            "difficulty": "", "budgets": {}, "spend": r["tokens"],
            "freeze_hash": None, "poc_hash": None, "void": r["void"],
        }, indent=2, sort_keys=True))
        (rd / "run.json").write_text(json.dumps({
            "round_id": r["round_id"], "match_id": r["match_id"],
            "season_id": r["season_id"], "attacker": r["attacker"],
            "defender": r["defender"], "attacker_model": r["models"]["attacker"],
            "defender_model": r["models"]["defender"], "status": "ungraded",
        }, indent=2, sort_keys=True))
        (rd / "defender" / "out" / "report.json").write_text(json.dumps({
            "mechanism": r["mechanism"], "exploit_present": None,
        }, indent=2, sort_keys=True))
        # The replay, wall clocks and resolved model names live only in the
        # payload's battles; keep them next to the round so standings.py sees them.
        b = payload.get("battles", {}).get(r["round_id"])
        if b:
            (rd / "battle.json").write_text(json.dumps(b, sort_keys=True))

    print(f"rounds written: {len(payload['ledger'])}  unsolved: {len(bad)}")
    for b in bad[:10]:
        print("  ", b)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
