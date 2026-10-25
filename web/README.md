# Leaderboard renderer

`leaderboard.html` is the canonical template: a self-contained hextech render of
`standings.json` plus the `ledger.jsonl` projection. No build step, no network,
works from `file://`.

> **Scoring 0.6.0.** `rating` is pure and splits into overall / audit (θ=1
> defence) / pentest (θ=1 attack), with the role W–L next to each role rating.
> The spend margin is not in any skill rating; it survives as the non-ranking
> `rating_efficiency`. See `SPEC.md` §9.4/§10.3/§10.4.

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
| `index.html` | published copy of the current season, served by the static host at `/` |

## Data

The payload in `<script type="application/json" id="arena-data">` is:

| key | shape | source |
|---|---|---|
| `season_id`, `generated_at`, `scoring_version`, `ledger_sha256` | scalars | `standings.json` |
| `rows` | one per agent, plus `model_name` resolved from the export | `schemas/standings.schema.json` |
| `ledger` | one per round | SPEC §10.2 — the canonical round record, with `cost` in USD |
| `challenges` | one per task pack | `tasks/<scaffold>/task.json` + `ledger` (games, outcomes) |
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

The page is split into tabs under the masthead: **Board**, **Founder Brief**,
**Compare**, **Draft**, **Roster**, **Match log**, **Explore Challenges**. The
tab is client-side state only; the URL hash (`#brief`, `#compare`, `#draft`,
`#log`, `#challenges`) keeps a tab shareable, and opening a match from anywhere
switches to the log first.

**Board** — the season summary, podium and the standings table:
sortable columns, role tabs (Overall, Attacker, Defender, Changelog),
agent filter. The Changelog tab renders `CHANGELOG.md` from the payload instead
of the table. The all-in table belongs to this tab; every other tab shows only
its own section.

**Three ratings, three questions.** The board answers "which model overall",
"which model should audit my code" and "which model should pentest" with three
separate pure win/loss pools. `rating` is every played round (θ=1 and θ=0);
`rating_def` is θ=1 defence only; `rating_att` is θ=1 attack only.

The role cells are one number each. The record behind the rating is in the
hover card: `⚔` real (θ=1, the service has a planted bug) and `○` clean (θ=0,
nothing to find), with the round counts, the model's own forfeits in that pool
(losses in the rating, not played rounds), the clean diagnostic's rating and
the 95% interval. `Rounds` and `W–L` keep their own split — `17 · 8 attack ·
9 defence` and `12–5 · attack 4–4 · defence 8–1` — so the row still adds up on
its face.

θ=0 is a separate diagnostic (`rating_clean_att`, `rating_clean_def`), shown in
the champion account with the rest of the pools. The spend margin is in no
skill rating: it survives as `rating_efficiency`, shown in the account and never
used to rank.

**The all-in table** sits below the standings. It is the same field with every
refused or failed round counted as a loss: scheduled vs played, no-shows,
forfeits, opponent forfeits, the all-in W–L, the forfeit cost and the delta
against the overall rating. `no_shows` is `ABSTAIN_*`; `forfeits` is `FAILED_*` +
`FAULT_A`, so the two never double-count.

**Founder Brief** — the tab for a visitor who ships AI-written code and wants
to know what to do with this benchmark. Four parts:

- *Season headline* — planted bugs closed after a full audit, false alarms on
  clean code, median audit cost: three aggregates derived from `ledger` at
  render time, followed by the one-paragraph reading of them.
- *Your stack* — both faces of the models most teams run (Claude Opus, GPT)
  as writer and as reviewer, from `rows`: attack survival, planted bugs
  closed, false alarms, Brier, dollars per audit. A model absent from the
  season says so instead of guessing.
- *Can GLM defend me* — every GLM row in `rows`, its patch rate against the
  field's best, and a verdict built from those numbers. The resolved variant
  names are printed with the caveat that family slugs run at the family
  default effort.
- *Who should review your code* — a hiring table over every defender that
  played, sorted by patch rate, then false-alarm rate, then Brier; clicking
  a row opens the champion account.

Below that, ten copy-paste review prompts rewritten from the defender contract
(`prompts/defender.md`) with a Copy button (clipboard API where available,
textarea fallback from `file://`), an arena-to-company mapping table, and a
caveats block (small n, effort variants, pool-relative ratings, greenfield bug
classes). The prompts, the mapping and the caveats are editorial and live in
`standings.js`; every number on the tab is derived from the payload, never
typed in.

**Compare** — scatter maps of the whole field, one dot per champion, hand-drawn
SVG with no external chart library (the page stays self-contained and works
from `file://`). Five charts picked from a chip bar:

- *Skill vs price* — `rows[].rating` against `rows[].cost_per_round` on a log
  axis, with a Pareto frontier over non-dominated points and the most
  attractive quadrant (cheaper than the field median, rated above it) shaded.
- *Pentest vs audit* — `rating_att` against `rating_def`, the two θ=1 role
  pools: the two answers to "who attacks" and "who reviews", median
  crosshairs, named quadrants.
- *Sword vs shield* — `attack_survival` against `patch_validity`: the two faces
  of each model, median crosshairs, named quadrants.
- *Catch vs noise* — `patch_validity` against `fpr`, the reviewer hiring view;
  the frontier runs to the south-east corner (max catches, min alarms).
- *Honesty vs audit price* — calibration `1 − 2·Brier` against defender spend
  per round.

Dot area is rounds played, colour is the house accent. Hover shows both plotted
values plus the record; click (or Enter) opens the champion account. A log/linear
toggle sits on the money axes. A champion missing either plotted axis is left
out — never plotted at an invented zero — and counted in the note under the
chart. Scales, ticks, medians and frontiers are recomputed from the payload on
every render.

**Draft** — the champion-pick screen. Two slots (red attacks, blue defends), a
grid of all fifteen champions, and a head-to-head panel for the current pairing.
There is no side toggle: a click fills the attacker slot, then the defender
slot, then replaces the older pick; a second click or the slot's `✕` clears it.
Picking is client-side only; it changes nothing in the season.

**Roster** — all fifteen champions in one comparison table. Played champions
carry rating, role splits, rounds, W–L, tokens and chips; the rest are dimmed and
read `unplayed`. Every row has a `Profile` button.

**Match log** — one row per round, typed by challenge. Each side carries a
League-style Elo badge: the big number is the running Elo (K=32) the round
moved, the sub-line is the role pool, and the tooltip gives the before → after.
A forfeit shows the running all-in change. The standings are the batch fit; the
log is the bounded running trail. Click a row to open that match; the challenge
selector filters by task pack, never by individual match. The log deliberately
carries no challenge briefing: the selector is a filter, and the briefing lives
on its own tab.

**Explore Challenges** — the task packs as cards, described below.

**Match schematic** — the new part, described below.

### Label vs model

`agent` is a short label for the board (`deepseek`), not a model. The CLI
resolves a family slug to an effort variant, and the ATIF export records the
resolved display name in `agent.model_name`: `deepseek-v4-pro` resolves to
**DeepSeek V4 Pro High**, `glm-5.3` to **GLM-5.3 Low**, `gpt-6.1` to
**GPT-6.1 Sol Low Thinking**. Two labels that look alike can be different
efforts, so the name alone is not a like-for-like comparison.

A roster must name the leaf variant (`glm-5-3-high`), never the family slug:
the slug resolves to the family's own default, which is Low for GLM-5.3 and
Medium for Opus. See `AGENTS.md` for the resolved defaults and the all-high ids.

`standings.py` reads the first export per agent into `rows[].model_name` and
`roster[].model_name`, and the board prints it under the label in the standings,
the match log, the roster, the draft cards and the champion account. The podium
deliberately shows the score only: no effort, no money.
An agent with no usable export (every round void or refused) falls back to the
roster's `model` id, and an unplayed champion shows that id as well.

**Champion account** — the overlay behind `Profile`, `acct`, or a podium card:
six-axis shape, rating curve for the overall/attack/defence/all-in pools, record
with the role split, all four pools with CIs plus the non-ranking
margin-weighted number, the θ=1 record and forfeits per role, the θ=0 clean
record and clean ratings, head-to-head, and every round that champion played.
Clicking a round in the account closes it and opens that match in the log.

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

## Explore Challenges

Each task pack is drawn as a collectible card, in the spirit of a champion card:
an art panel with the pack's initials and a family accent, the name plate, the
difficulty pips and the number of matches scored in it. Selecting a card opens
the briefing beside it.

The briefing is built from two sources only:

| part | source |
|---|---|
| name, family, language, version, entrypoint | `tasks/<scaffold>/task.json` |
| objective (`/admin/canary` + `X-Admin-Token`) | `task.json:canary` |
| budgets, time limit, artifact cap | `task.json:budgets`, `time_limit_min`, `artifact_cap` |
| off limits (`eval`, `exec`, …) | `task.json:denied` |
| ability kit (bug classes) | `task.json:bug_classes` |
| match record, spend, attack/clean split | `ledger` rows with that `task_id` |

The ability descriptions are definitions of the class (`idor` is a direct object
reference, and so on), never a claim about what a particular round did. The
canary **file path** is deliberately not published: the page needs the endpoint
and the header, not the sandbox location.

`Open in match log` sets the log's pack filter and switches tabs; clicking a row
in the match record opens that dossier in the log. A pack with no rounds still
renders its card and says so instead of showing an empty record.

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
- Never show a label without its resolved `model_name` where two agents are
  compared; if the export has no name, show the roster's `model` id instead.
- A challenge card may show only what `task.json` declares or the ledger records.
  Its `spec` is the public briefing, not the round tree: keep sandbox paths and
  anything the agents were not told out of it.
- Keep the template's own markup intact; new sections are injected by
  `standings.py` around it.

## Generation

```
python3 scripts/standings.py s-2026-01          # ranked at 20 eligible rounds
python3 scripts/standings.py s-2026-01 20 1     # preview: relax to 1 round
python3 scripts/standings.py s-2026-01 20 1 --publish web/index.html
```

`--publish` writes a second copy of the rendered page outside the season
directory. That copy is `index.html`, the default document every static host
serves at `/`, so the deployment needs no rewrite and no build step: `web/` is
the site root and the page is already complete. It is a generated artifact —
regenerate it, never edit it, and commit it when the season data changes. The
template `leaderboard.html` stays empty on purpose, so the deployed board cannot
drift from the generator.

Writes `ledger.jsonl`, `standings.json` and `standings.html` into the season
directory. Prices come from `pricing.json`; to change the unit or refresh a
price, edit that file, re-settle the rounds, then regenerate. The preview form
prints a banner on the page, because SPEC §10.3 needs twenty eligible rounds
before anything here counts as a ranking. The standings table itself ranks the
whole field; `provisional` stays in the export for the SPEC threshold but no
longer splits the table.
