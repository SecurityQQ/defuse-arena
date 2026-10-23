#!/usr/bin/env bash
# Replay one round that never produced a result, keeping its original coin
# (THETA from manifest.json) and its match/round ids stable.
#
#   scripts/replay-voids.sh '<season|match|start_round|rounds|band|a|am|d|dm>'
#
# Feed it a spec per line, e.g.:
#   xargs -P 2 -I{} scripts/replay-voids.sh {} < specs.txt
set -uo pipefail

SPEC="${1:?missing match spec}"
IFS='|' read -r SEASON MATCH_ID START_ROUND _ROUNDS _BAND _AL _AM _DL _DM <<< "$SPEC"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ROUND_DIR="seasons/$SEASON/matches/$MATCH_ID/rounds/r-$(printf '%04d' "$START_ROUND")"
if [[ ! -f "$ROUND_DIR/manifest.json" ]]; then
  echo "[$(date +%H:%M:%S)] $MATCH_ID: no manifest, nothing to replay"
  exit 1
fi

THETA=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['theta'])" "$ROUND_DIR/manifest.json")
echo "[$(date +%H:%M:%S)] replay $MATCH_ID theta=$THETA"

THETA="$THETA" AGENT_RETRIES="${AGENT_RETRIES:-3}" RETRY_BACKOFF="${RETRY_BACKOFF:-20}" \
  scripts/run-match.sh "$SPEC"
rc=$?
echo "[$(date +%H:%M:%S)] $MATCH_ID finished rc=$rc"
exit $rc
