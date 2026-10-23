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
# Each unordered pair plays twice: A attacks B, then B attacks A.
# 5 models -> 10 pairs -> 20 matches; N models -> N(N-1) matches.

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

      match_no=$((match_no + 1))
      match_id=$(printf 'm-%04d' "$match_no")

      if [[ "$SKIP_DONE" == "1" && -s "$SEASON_DIR/matches/$match_id/result.tsv" ]]; then
        log "skip $match_id (already has result.tsv)"
        continue
      fi

      start_round=$(((match_no - 1) * ROUNDS + 1))

      SPECS+=("$SEASON|$match_id|$start_round|$ROUNDS|$BAND|$a_label|$a_model|$d_label|$d_model")
    done
  done
done

[[ ${#SPECS[@]} -gt 0 ]] || die "no matches selected"

log "season=$SEASON matches=${#SPECS[@]} rounds/match=$ROUNDS jobs=$JOBS dry_run=$DRY_RUN"

"$ROOT/scripts/write-season-run.py" "$SEASON_DIR" "$SEASON" "$ROUNDS" "$BAND" "${MODELS[@]}"

# Stratify the coin. An independent per-round flip leaves a 20-match season with
# lopsided splits (this one drew 6 attack rounds out of 20), which starves the
# attack and patch metrics. Assign exactly half the rounds to each side in a
# random order instead; every theta is still fixed before its build.
if [[ -z "${THETA:-}" && ! -f "$SEASON_DIR/theta.tsv" ]]; then
  "$PY" - "$SEASON_DIR/theta.tsv" <<PY
import random, sys
from pathlib import Path

specs = """$(printf '%s\n' "${SPECS[@]}")""".strip().splitlines()
ids = sorted(s.split("|")[1] for s in specs)
vals = [1] * (len(ids) // 2) + [0] * (len(ids) - len(ids) // 2)
random.shuffle(vals)
Path(sys.argv[1]).write_text("".join(f"{m}\t{v}\n" for m, v in zip(ids, vals)))
PY
  log "theta: $(awk -F'\t' '{c[$2]++} END {printf "%d attack / %d clean", c[1], c[0]}' "$SEASON_DIR/theta.tsv")"
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
