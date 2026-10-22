#!/usr/bin/env python3
"""Write season.run.json for a round-robin run."""
import json
import sys

season_dir, season_id, rounds, band = sys.argv[1:5]
models = sys.argv[5:]

roster = []
for entry in models:
    label, model_id = entry.split("|", 1)
    roster.append({"label": label, "model": model_id})

data = {
    "season_id": season_id,
    "rounds_per_match": int(rounds),
    "band": band,
    "roster": roster,
}

with open(season_dir + "/season.run.json", "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
