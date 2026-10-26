#!/usr/bin/env bash
# Round-robin orchestrator for Inspection Arena.
#
#   scripts/round-robin.sh                    # all pairs, 1 round per match
#   ROUNDS=4 scripts/round-robin.sh           # 4 rounds per match
#   ONLY=glm-5.3 scripts/round-robin.sh       # only matches involving glm-5.3
#   JOBS=4 scripts/round-robin.sh             # four matches in parallel
#   DRY_RUN=1 scripts/round-robin.sh          # print commands, no model calls
#   ROSTER_FILE=rosters/season-2026-02.tsv scripts/round-robin.sh
#
# Each unordered pair plays four matches: both directions (A attacks B, B
# attacks A) on both coins (theta=1 attack task, theta=0 clean control), so
# every pairing is tested and so, with no randomness in the schedule.
# 5 models -> 10 pairs -> 40 matches; N models -> 2N(N-1) matches.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEASON="${SEASON:-s-2026-01}"
ROUNDS="${ROUNDS:-1}"
BUDGET="${BUDGET:-60000}"
BAND="${BAND:-D3}"
ONLY="${ONLY:-}"
SKIP_DONE="${SKIP_DONE:-0}"
JOBS="${JOBS:-2}"
DRY_RUN="${DRY_RUN:-0}"
DEVIN="${DEVIN:-devin}"
PY="${PY:-python3}"
AGENT_TIMEOUT="${AGENT_TIMEOUT:-1800}"
ROSTER_FILE="${ROSTER_FILE:-}"

export BUDGET BAND DRY_RUN DEVIN AGENT_TIMEOUT

# label|model-id. The CLI resolves these to high-effort variants automatically
# (the export reports names like deepseek-v4-pro-high).
# deepseek-v4.1-flash is newer but flash-tier; v4-pro is the strong one.
MODELS=(
  "deepseek|deepseek-v4-pro"
  "glm-5.2|glm-5.2"
  "glm-5.3|glm-5.3"
  "opus-5.5|claude-opus-5.5"
  "gpt-6.1|gpt-6.1-sol"
)

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# An explicit roster replaces the built-in five. One `label|model-id` per
# line; blank lines and # comments are ignored. The runner records the roster
# it used in season.run.json, so a season stays reproducible.
if [[ -n "$ROSTER_FILE" ]]; then
  [[ -f "$ROSTER_FILE" ]] || die "missing roster file: $ROSTER_FILE"
  MODELS=()
  while IFS='|' read -r label model_id; do
    label="${label%$'\r'}"
    model_id="${model_id%$'\r'}"
    [[ -z "$label" || "$label" == \#* ]] && continue
    [[ -n "$model_id" ]] || die "bad roster line: $label"
    MODELS+=("$label|$model_id")
  done < "$ROSTER_FILE"
  [[ ${#MODELS[@]} -ge 2 ]] || die "roster file needs at least two models"
fi

command -v "$DEVIN" >/dev/null 2>&1 || die "$DEVIN not found on PATH"
[[ -f "$ROOT/prompts/attacker.md" ]] || die "missing prompts/attacker.md"
[[ -f "$ROOT/prompts/defender.md" ]] || die "missing prompts/defender.md"

SEASON_DIR="$ROOT/seasons/$SEASON"
mkdir -p "$SEASON_DIR/matches"

SPECS=()
THETA_LINES=()
match_no=0
n=${#MODELS[@]}

for ((i = 0; i < n; i++)); do
  for ((j = i + 1; j < n; j++)); do
    for side in 0 1; do
      if [[ $side -eq 0 ]]; then a=$i; d=$j; else a=$j; d=$i; fi

      a_label="${MODELS[$a]%%|*}"
      a_model="${MODELS[$a]##*|}"
      d_label="${MODELS[$d]%%|*}"
      d_model="${MODELS[$d]##*|}"

      if [[ -n "$ONLY" && "$a_label" != "$ONLY" && "$d_label" != "$ONLY" ]]; then
        continue
      fi

      # Both coins on every ordered pair: theta=1 (attack task) and theta=0
      # (clean control). No draw, no seed — the schedule itself fixes the coin
      # before any service is built. The coin is recorded for every match in
      # the schedule, including ones SKIP_DONE would skip, so theta.tsv is
      # complete whatever subset is actually (re)run.
      for coin in 1 0; do
        match_no=$((match_no + 1))
        match_id=$(printf 'm-%04d' "$match_no")
        THETA_LINES+=("$match_id"$'\t'"$coin")

        if [[ "$SKIP_DONE" == "1" && -s "$SEASON_DIR/matches/$match_id/result.tsv" ]]; then
          log "skip $match_id (already has result.tsv)"
          continue
        fi

        start_round=$(((match_no - 1) * ROUNDS + 1))

        SPECS+=("$SEASON|$match_id|$start_round|$ROUNDS|$BAND|$a_label|$a_model|$d_label|$d_model")
      done
    done
  done
done

[[ ${#SPECS[@]} -gt 0 ]] || die "no matches selected"

log "season=$SEASON matches=${#SPECS[@]} rounds/match=$ROUNDS jobs=$JOBS dry_run=$DRY_RUN"

"$ROOT/scripts/write-season-run.py" "$SEASON_DIR" "$SEASON" "$ROUNDS" "$BAND" "${MODELS[@]}"

# The coin schedule is the match list itself: every ordered pair gets one
# theta=1 match and one theta=0 match, so the season is exactly half attack
# and half clean by construction and every pairing is tested on both coins.
# Write it before any match runs; an existing theta.tsv is left alone so a
# resumed or replayed season keeps the coins it started with.
if [[ ! -f "$SEASON_DIR/theta.tsv" ]]; then
  printf '%s\n' "${THETA_LINES[@]}" > "$SEASON_DIR/theta.tsv"
  log "theta: $(awk -F'\t' '{c[$2]++} END {printf "%d attack / %d clean", c[1], c[0]}' "$SEASON_DIR/theta.tsv") (both coins per pair, deterministic)"
fi

set +e
printf '%s\n' "${SPECS[@]}" | xargs -P "$JOBS" -I{} "$ROOT/scripts/run-match.sh" "{}"
xargs_status=$?
set -e
[[ $xargs_status -eq 0 ]] || log "warning: xargs exited $xargs_status; aggregating what finished"

SUMMARY="$SEASON_DIR/round-robin.tsv"
printf 'match\tround\tattacker\tdefender\ttheta\toutcome\tcost_a\tcost_b\tbrier\tscore\tdR_a\tdR_b\n' > "$SUMMARY"
find "$SEASON_DIR/matches" -name result.tsv -print | sort | xargs cat >> "$SUMMARY"

log "done. summary: $SUMMARY"
