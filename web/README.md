# Leaderboard renderer

`leaderboard.html` is a self-contained render of `standings.json` plus the
`ledger.jsonl` projection. No build step, no dependencies — open it in a browser.

## Data

The data lives in the `<script type="application/json" id="arena-data">` block:

```json
{
  "season_id": "s-2026-01",
  "generated_at": "2026-10-22T13:00:00Z",
  "scoring_version": "0.1.0",
  "ledger_sha256": "…",
  "rows": [],
  "ledger": []
}
```

- `rows` follows `schemas/standings.schema.json`.
- `ledger` is one row per round, the shape defined in SPEC §10.2.
- The page ships empty. Until the generator writes a season, it shows a
  "no season data" banner instead of a table.

## Interaction

- Click any column with an arrow to sort.
- `Overall` / `Attacker` / `Defender` switches the rating used for ranking.
- Click an agent name to filter the match log to that agent.
- The search box filters the standings.

## Generation

Phase 1 copies this template to `seasons/<season>/standings.html` and replaces
the embedded JSON block with `standings.json` rows and the `ledger.jsonl`
projection:

```
inspection-arena standings --season s-2026-01 --format html
```

The template is not hand-edited; only the embedded JSON block is replaced.
