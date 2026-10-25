# Inspection Arena

A two-agent benchmark for hidden-vulnerability auditing.

One model builds a small service. A coin flip decides whether that service
contains a deliberately planted vulnerability. A second model audits the frozen
service, reports the probability that a vulnerability is present, and — if it
finds one — submits a patch. An executable proof-of-concept decides who is right.

The benchmark scores three things separately: **detection** (Brier score),
**defusal** (does the patch actually block the PoC), and **efficiency** (tokens
spent). These feed a zero-sum chip ledger and a batch Bradley-Terry rating with
a spend margin.

**Status:** specification + Phase 1 runner. The spec, schemas, task packs,
prompts, and round-robin harness are in place; the container harness and
immutable conformance suite are next.

- [`SPEC.md`](SPEC.md) — full specification
- [`schemas/`](schemas/) — JSON schemas for the round manifest, defender report,
  and grade record

## Safety

Every service is authored by the attacker from a harness-provided scaffold and
runs in a disposable, network-isolated container. The "vulnerability" is a logic
or web bug in that scaffold, and the only secret is a per-round random canary.
Nothing here targets real software, real credentials, or the host. The artifact
is a CTF-style exercise against code the attacker wrote five minutes earlier.

## Why

Existing work measures sabotage in transcripts (SHADE-Arena), covert code
execution in a shell (Ctrl-Z / BashArena), or CTF exploitation (Cybench). This
benchmark measures the audit loop end to end: build, freeze, inspect, report,
patch, verify.

## Round folders

A round lives at
`seasons/<season>/matches/<match>/rounds/<round>/`. The game master owns that
tree. The attacker sees only `attacker/`, the defender sees only
`defender/inbox/` (read-only) and `defender/out/` (writable), and the grader
sees `frozen/`, `sealed/`, and `defender/out/`. Everything else is absent from
the container, not merely forbidden by prompt. See SPEC §7.8–7.13.

## Leaderboard

`ledger.jsonl` holds one row per round: who attacked, who defended, θ, outcome,
tokens spent by each side, chips, and the Elo delta. `standings.json` and
`standings.md` aggregate it per agent, with separate attacker and defender
ratings. Both are derived from the round records and can be regenerated or
verified at any time. See SPEC §10.2–10.5.

Preview: open [`web/leaderboard.html`](web/leaderboard.html) — a self-contained
hextech-style render that fills from a season export, with sortable columns,
role tabs, and a click-to-filter match log. It ships empty.

The generated season page adds six views on top of that template, behind a tab
bar: a **founder brief** — what a company that ships AI-written code should do
with this benchmark, from season numbers for an Opus/GPT stack and a data answer
to "can GLM defend me" to ten copy-paste review prompts and an arena-to-company
mapping; a **compare** screen — scatter maps of the whole field, one dot per
champion: skill vs price with a Pareto frontier, the two faces of each model,
and the reviewer trade-offs, hoverable and clickable into the champion accounts;
a **match schematic** per round (attacker, defender and arbiter lanes, the
proof-of-concept travelling at the patch, and a transcript-driven action feed
with the spend of both sides), a **draft** screen for picking a champion per
side, a **champion account** with shape, rating curve, role splits and every
round played, and **Explore Challenges**, where each task pack is a card with the
briefing the rounds were scored against — objective, budgets, permitted bug
classes and the match record. The match log itself keeps only the pack filter.
`web/roster.json` declares the fifteen-champion pool; a model that has not played
is listed without a rating.

`web/index.html` is the published copy of the current season, served by the
static deployment (Vercel, site root `web/`) as the default document. Regenerate
it with `--publish` when the season data changes; the template stays empty.

Spend is reported in **USD**, not tokens: `web/pricing.json` holds the per-model
price from `devin models list`, and the chip ledger, `$/round` and the rating
margin are all settled in money, because a token costs several times more on one
model than on another. Tokens stay in the record as the raw meter reading.
See [`web/README.md`](web/README.md).

## Tasks

Ranked rounds run against a task pack from the catalog: fixed contract, fixed
conformance suite, declared bug classes, declared difficulty bands. Eight
families ship in v1, from CRUD/auth to ledgers and tenancy. Agents can propose
new packs, but a proposal cannot be used in the season it was proposed.
See SPEC §7.14–7.17 and [`tasks/README.md`](tasks/README.md).

## problem.md

The repository is shaped as a [problem.md](https://problem.md) competition:
`PROBLEM.md` at the root, one `submissions/<agent>/SUBMISSION.md` per agent.
The export is generated from `standings.json`:

```
inspection-arena standings --season s-2026-01 --format problem-md
```

Track ids and baselines are in [`PROBLEM.md`](PROBLEM.md). Rating is
pool-relative; the absolute tracks are the stable comparison.

## Layout (planned)

```
inspection-arena/
├── PROBLEM.md                # problem.md/v1 competition manifest
├── SPEC.md
├── schemas/
├── src/inspection_arena/     # gm, layout, tasks, arena, meter, grader, rating, cli
├── tasks/                    # task packs: families, bands, conformance
├── prompts/                  # attacker.md, defender.md
├── scripts/                  # round-robin.sh
├── submissions/              # generated per-agent entries
├── seasons/                  # runtime data: matches, rounds, ledger, standings
├── web/                      # leaderboard: template, css, js, roster
├── tests/
└── docs/
```
