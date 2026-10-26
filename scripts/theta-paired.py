#!/usr/bin/env python3
"""Write a paired, role-balanced coin for a round-robin season.

    scripts/theta-paired.py rosters/season-2026-04.tsv seasons/s-2026-04/theta.tsv [seed]

`round-robin.sh` draws one θ per match from a season-level shuffle. That keeps
the season at half attack / half clean, but a pair can draw the same coin in
both directions and a model can end up with 7 attack rounds of one coin and 3
of the other. With one round per match that is noise; with a verification
season it is the difference between testing a role and testing a coin.

This writes the file the runner would otherwise generate, with two properties:

* every unordered pair gets one attack direction and one clean direction, so
  both coins are tested on every pair;
* every model gets as close to half of its attack rounds and half of its
  defence rounds on each coin as the field allows — exact for an odd number of
  models, 2+3 / 3+2 for six — because the attack directions form a regular
  tournament (a cyclic tournament with the roster order permuted).

The assignment is still random — the permutation is seeded — and it is fixed
before any service is built, which is the property the protocol needs.
"""
import random
import sys
from pathlib import Path


def main() -> int:
    roster = Path(sys.argv[1])
    out = Path(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 20261026

    labels = []
    for line in roster.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            labels.append(line.split("|", 1)[0])
    n = len(labels)
    if n < 3:
        print("need at least three models", file=sys.stderr)
        return 1

    order = list(range(n))
    random.Random(seed).shuffle(order)
    rank = {model: k for k, model in enumerate(order)}
    half = (n - 1) // 2

    # Cyclic tournament on the permuted order: a beats b when b-a (mod n) is
    # in 1..half. Each vertex has out-degree and in-degree half, so every
    # model attacks half its opponents on a bug round and defends half of
    # them on a bug round.
    def bug_direction(i: int, j: int) -> int:
        a, b = rank[i], rank[j]
        return 1 if 0 < (b - a) % n <= half else 0

    lines = []
    balance = {label: {"att1": 0, "att0": 0, "def1": 0, "def0": 0} for label in labels}
    match = 0
    for i in range(n):
        for j in range(i + 1, n):
            match += 1
            theta = bug_direction(i, j)  # i attacks j
            lines.append(f"m-{match:04d}\t{theta}")
            balance[labels[i]]["att1" if theta else "att0"] += 1
            balance[labels[j]]["def1" if theta else "def0"] += 1
            match += 1
            theta = 1 - theta  # j attacks i
            lines.append(f"m-{match:04d}\t{theta}")
            balance[labels[j]]["att1" if theta else "att0"] += 1
            balance[labels[i]]["def1" if theta else "def0"] += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    attack = sum(1 for line in lines if line.endswith("\t1"))
    print(f"{out}: {len(lines)} matches, {attack} attack / {len(lines) - attack} clean")
    for label in labels:
        b = balance[label]
        print(f"  {label:18s} attack {b['att1']}+{b['att0']}-  defence {b['def1']}+{b['def0']}-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
