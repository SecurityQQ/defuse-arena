# Leaderboard renderer

`leaderboard.html` is the canonical template: a self-contained hextech render of
`standings.json` plus the `ledger.jsonl` projection. No build step, no network,
works from `file://`.

The template is **never hand-edited**. `scripts/standings.py` copies it to
`seasons/<season>/standings.html` and replaces exactly one thing: the embedded
`arena-data` block. Everything else the page needs lives beside it:

| file | role |
|---|---|
| `leaderboard.html` | template; the generator only swaps `arena-data` |
| `standings.css` | styles, inlined into `<head>` |
| `standings.js` | behaviour, inlined at the end of the document |
| `roster.json` | the season's champion pool — identity, not results |
| `pricing.json` | USD per 1M tokens per model, copied from `devin models list` |

## Data

The payload in `<script type="application/json" id="arena-data">` is:

| key | shape | source |
|---|---|---|
| `season_id`, `generated_at`, `scoring_version`, `ledger_sha256` | scalars | `standings.json` |
| `rows` | one per agent | `schemas/standings.schema.json` |
| `ledger` | one per round | SPEC §10.2 — the canonical round record, with `cost` in USD |
| `challenges` | one per task pack | `tasks/<scaffold>/task.json` |
| `battles` | one per round id | round manifest, grader results, agent exports |
| `champions` | one per played agent | derived from `ledger` |
| `roster` | one per champion | `web/roster.json` |

`ledger` stays the only source of truth for money, rating and outcome. Money is
USD: every row carries `cost` (priced) next to `tokens` (metered). `battles`,
`champions` and `roster` are render-only projections: nothing on the page may
show a number that is not derivable from `ledger` or from a round record.

`roster.json` lists fifteen champions by `agent` label and model id. A champion
that has not played keeps `played: false` and is shown with **no rating** — never
with a default or a guess. `standings.py` also appends any agent that played but
is missing from the roster, so the page cannot silently drop a result.

## What the page shows

**Standings** — the template's own table: sortable columns, role tabs, agent
filter, three rating pools.

**Draft** — the champion-pick screen. Two slots (blue attacks, red defends), a
grid of all fifteen champions, and a head-to-head panel for the current pairing.
Picking is client-side only; it changes nothing in the season.

**Roster** — all fifteen champions in one comparison table. Played champions
carry rating, role splits, rounds, W–L, tokens and chips; the rest are dimmed and
read `unplayed`. Every row has a `Profile` button.

**Match log** — one row per round, typed by challenge. Click a row to open that
match; the challenge selector filters by task pack, never by individual match.

**Match schematic** — the new part, described below.

**Champion account** — the overlay behind `Profile`, `acct`, or a podium card:
six-axis shape, rating curve for the three pools, record, attacker/defender
splits, head-to-head, and every round that champion played. Clicking a round in
the account closes it and opens that match in the log.

## Match schematic

Each match dossier carries a schematic of what each side actually did:

```
ATTACKER   read θ → built service → planted bug → sealed PoC → froze tree
                        │
              proof-of-concept ──▶ shield ──▶ canary
                        │
DEFENDER   received tree → audited → reported p=0.99 → patched
ARBITER    service up → contract → PoC works → patch applied → patched build → PoC blocked → TP
```

- **Lanes.** `att` and `def` come from `manifest.json` (`freeze_hash`,
  `poc_hash`) and the defender's `report.json`; `arb` comes from
  `grader/results.json:checks`. A step that did not happen is `skip`, not a
  failure. `PoC blocked` is inverted on purpose: `poc_patched == true` means the
  proof-of-concept still fired, which is the defender failing.
- **Contest.** With θ=1 the dot travels to the shield (`TP`/`FN` decide whether
  it stops or reaches the canary). With θ=0 there is nothing to detonate and the
  line stays idle.
- **Spend.** Attacker and defender cost in USD, bar width relative to the larger
  side, counter tweened to the exact ledger value. Each transcript action carries
  the cost of the step that produced it.
- **Transcript.** The real tool calls from `grader/logs/attacker.export.json`
  and `defender.export.json` (ATIF `steps[].tool_calls`), reduced to verb +
  object + per-step billable tokens. Replayed rounds keep their exports as
  `<name>.attempt-N`; the newest attempt wins. A round with no export still
  renders: lanes come from the record, the transcript is simply empty.

## Unit of account

A token is not a unit of cost. `deepseek-v4-pro` bills at $1.32/$0.04/$3.96 per
1M tokens and `claude-opus-5.5` at $4/$0.20/$20, so the same token count is up to
5x the money. Everything economic on this page — spend, chips, `$/round`,
head-to-head cost, the schematic bars — is USD, converted from `pricing.json` as
`(prompt − cached)·p_in + cached·p_cached + completion·p_out`.

Tokens are still shown where they are the raw meter reading (the dossier facts,
`tokens_total` in `standings.json`), because budgets and the harness meter are
token-denominated.

If a price is missing, `grade.py` refuses to invent one: it records the token
spend and warns. Re-pricing an already graded round does not re-run anything:

```
python3 scripts/grade.py <round_dir> --settle-only
```

That rewrites `grade.json` and `results.json` with `cost`, USD `chips` and a
recomputed `rating_delta`, keeping the recorded outcome and checks untouched.

## Animation contract

- One paused timeline per dossier, driven by `setTimeout` ids that `Replay`
  clears. Nothing animates on its own before a match is opened.
- `Reveal all` is the escape hatch and must always produce the final state.
- Timing is fixed (120 ms per lane chip, 50 ms per transcript action), not
  random, so two renders of the same round look identical.
- `prefers-reduced-motion: reduce` disables every transition and animation.

## Rules for changing the render

- Never hand-edit `seasons/<season>/standings.html`; regenerate it.
- Never write a closing body tag inside `standings.js` — the generator inserts
  that file with a string replace and would split the page at the comment.
- Do not invent a rating, a token count or an outcome. If the data is missing,
  show `—` and say why.
- Keep the template's own markup intact; new sections are injected by
  `standings.py` around it.

## Generation

```
python3 scripts/standings.py s-2026-01          # ranked at 20 valid rounds
python3 scripts/standings.py s-2026-01 20 1     # preview: relax to 1 round
```

Writes `ledger.jsonl`, `standings.json` and `standings.html` into the season
directory. Prices come from `pricing.json`; to change the unit or refresh a
price, edit that file, re-settle the rounds, then regenerate. The preview form prints a banner on the page, because SPEC §10.3
needs twenty valid rounds before anything here counts as a ranking.
