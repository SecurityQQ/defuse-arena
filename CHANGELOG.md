# Changelog

Every substantial modification to this repository is recorded here. The
leaderboard renders this file under its **Changelog** tab, so entries must stay
plain markdown — no HTML, no links to local files.

## 0.4.8 — 2026-10-25 — ratings follow the schedule, not the grader clock

### Scoring

- Elo updates are processed in scheduled round order (`round_id`), not by
  `grade.json:ts`. Re-grading a round updates its timestamp; sorting by `ts`
  moved that round to the end of the season, changed every later expectation,
  and made the same outcomes produce a different table. The 43 re-graded
  rounds now sit in their original slots, so the table is reproducible from
  the ledger alone.
- After the correction and the order fix, s-2026-02 reads GPT-6.1 1590.6,
  Opus 5.5 1573.2, Gemini 4 Argon 1564.6, GLM-5.3 Flash 1553.2, Grok 4.7
  1551.6. GLM-5.3 Low is 7th at 1518.8: its earlier #1 was inflated by
  opponent patches the grader never applied. Once those patches count, its
  attack wins become losses and its attack rating falls from ~1580 to ~1437,
  while its defence rating rises from ~1492 to ~1541.

## 0.4.7 — 2026-10-25 — every patch is applied before it is judged

### Scoring

- `git apply` was run inside this repository, so a patch with a `diff --git`
  header was resolved against the repo root, silently ignored, and returned 0.
  `apply_patch` reported `patch_applied: True` and the grader ran the PoC on
  the unpatched tree, recording a real patch as `FN`. `GIT_CEILING_DIRECTORIES`
  now stops the repo walk at the round, and a no-op patch is rejected instead
  of accepted.
- Re-graded the 43 affected rounds in s-2026-02: 26 `FN` became `TP`, one
  became `FAULT_A`, and the season now reads `TP 39 / FN 4` instead of
  `TP 12 / FN 32`. Every rating, chip and patch-validity number was
  regenerated. The correction moves Opus 5.5 to #1, GPT-6.1 to #2 and
  GLM-5.3 Flash to #3; GLM-5.3 Max rises to #9 with 100% patch validity,
  not 25%.
- `standings.py` stamps the payload `scoring_version` 0.4.7. Per-round grades
  keep their 0.4.0 taxonomy.

## 0.4.6 — 2026-10-23 — the GLM twins join the field

### Scoring

- A failed agent run that burned completion tokens is now a failed delivery
  (`FAILED_A` / `FAILED_D`), not a `VOID`. The runner only voids a round when
  the failed side spent no completion tokens; a max-output truncation or a
  crash after real work is priced as a forfeit. Previously any non-zero exit
  was written as infrastructure, so a model that worked and delivered nothing
  escaped the ledger.

### Board

- The eleven-model field gains two GLM-5.3 variants: **GLM-5.3 Flash Max** and
  **GLM-5.3 Max**. Each plays every existing model in both directions, plus
  each other, for 46 new matches in s-2026-02 — 156 rounds and 13 agents.
- `web/roster.json` carries both champions, and `web/pricing.json` prices their
  leaf ids (`glm-5-3-flash-max`, `glm-5-3-max`).

## 0.4.5 — 2026-10-23 — compare the field on applied axes

### Board

- New **Compare** tab, after the Founder Brief, shareable as `#compare`: scatter
  maps of the whole field, one dot per champion. Four charts: **Skill vs price**
  — general rating against real dollars per round with a Pareto frontier and
  the most attractive quadrant shaded (the reading popularised by model-index
  sites) — **Sword vs shield** (attack survival vs patch validity, the two faces
  of each model), **Catch vs noise** (patch validity vs false-alarm rate, the
  hiring view), and **Honesty vs audit price** (calibration, one minus twice the
  Brier score, against defender spend per round).
- Each chart carries field-median crosshairs with named quadrants, a log/linear
  toggle on the money axes, dot size by rounds played and house colour. Hover a
  dot for its two plotted values plus record; click it to open the champion
  account. Champions missing a plotted axis are left out and counted in the
  note — never plotted with an invented zero.
- All scales, ticks, medians and frontiers are computed client-side from the
  arena-data payload, so a new season redraws every chart with no edits.
  `standings.py` injects the empty `#ia-compare` host around the untouched
  template.

## 0.4.4 — 2026-10-23 — the board answers a founder

### Board

- New **Founder Brief** tab, second after Board, shareable as `#brief`. It is
  written for the visitor who ships AI-written code and has to decide what to
  do with this benchmark: what the season's numbers mean for a stack built on
  Claude Opus and GPT, a data answer to **can GLM defend me**, a hiring table
  over every defender that played, ten copy-paste review prompts rewritten
  from the defender contract, and a mapping from each arena concept to its
  equivalent in a company.
- Every number on the tab is computed from the arena-data payload at render
  time — season aggregates, per-model cards, the GLM verdict and the hiring
  table all re-derive themselves, so a new season refreshes the brief with no
  edits. Nothing numeric is typed into the render.
- The editorial layer (the ten prompts, the company mapping, the caveats)
  lives in `web/standings.js`; `standings.py` injects the empty `#ia-brief`
  host around the untouched template, the same way as the draft and challenges
  sections. Prompt copying falls back to a textarea when the page is opened
  from `file://`, where the clipboard API is unavailable.

## 0.4.3 — 2026-10-23 — the board ranks the whole field

### Board

- The standings table no longer splits the field at a **Provisional — fewer
  than 20 valid rounds** divider. Every agent is ordered by general rating and
  gets a rank; the podium and the champion accounts use the same order.
  `provisional` stays in the export for SPEC §10.3 and the preview banner, but
  the page neither marks a row as provisional nor hides it below a divider.

## 0.4.2 — 2026-10-23 — the board names the model variant

### Board

- **Resolved model names.** A label is not a model: the CLI resolves a family
  slug to an effort variant, so two similar labels can be different efforts.
  `standings.py` now reads `agent.model_name` from the ATIF export and carries
  it as `rows[].model_name` and `roster[].model_name`. In s-2026-02 that makes
  `deepseek` = DeepSeek V4 Pro High, `glm-5.2` = GLM-5.2 High, `glm-5.3` =
  GLM-5.3 Low and `gpt-6.1` = GPT-6.1 Sol Low Thinking — the labels alone were
  not a like-for-like comparison.
- The resolved name is printed under the label in the standings, the match log,
  the roster, the draft cards and the champion account. An agent with no usable
  export falls back to the roster's `model` id; an unplayed champion shows that
  id.
- The podium shows the score only: no effort, no money.
- `AGENTS.md` records the family-slug defaults and the explicit all-high ids, so
  a roster cannot silently run `glm-5.3` as Low while reading as "high".

## 0.4.1 — 2026-10-23 — rosters are files, refusals are no-shows

### Scoring

- The ranking threshold now counts **eligible rounds**: played rounds plus
  rounds an opponent forfeited. An agent's own forfeits still do not count, so
  a refusal keeps the offender provisional — but the opponent who showed up is
  no longer stripped of the round. Previously both sides lost the round, which
  left an entire 110-match season at 9–18 valid rounds and made every agent
  provisional.
- `standings.py` exports `eligible` on every row and stamps the payload
  `scoring_version` 0.4.1. Per-round grades stay 0.4.0: the taxonomy and the
  per-round chips are unchanged, only the eligibility aggregate is.

### Harness

- A provider refusal is recorded as a no-show, not infrastructure. The runner
  detects `content_filter` / "Provider refusal" in the agent log, skips the
  retry, and lets the grader price `ABSTAIN_*` / `FAILED_*` from the completion
  count. Previously the non-zero exit aborted the whole match before a result
  was written, so a refusal vanished from the ledger instead of being priced.
- `run_agent_settled` no longer re-enables `set -e` before returning: a
  non-zero agent exit used to kill `run-match.sh` at the function boundary,
  leaving an empty `result.tsv` and no grade. The caller already restores
  `set -e` after capturing the exit code.
- Freeze faults are priced in USD and stamped scoring 0.4.0. `FAULT_A` now
  charges 12.5% of the offender's token budget converted at its own input
  price, instead of writing a token-denominated fee under the stale 0.2.0
  version.
- `scripts/round-robin.sh` accepts `ROSTER_FILE` (`label|model-id` per line,
  blank lines and `#` comments ignored), so a season can run a larger field
  without editing the script. `N` models still produce `N(N-1)` matches —
  every pair plays both directions — and the roster used is recorded in
  `season.run.json`. The built-in five remain the default.
- `rosters/season-2026-02.tsv` declares the eleven-champion field for the next
  season: the original five plus Astra, Gemini Argon, Kimi K3, Sonnet 5.5,
  Grok 4.7 and Muse Wonder. At 110 matches every agent is scheduled for 20
  rounds; with forfeits, `eligible` keeps the side that showed up at 20 while
  the offender drops below it.

## 0.4.0 — 2026-10-23 — forfeits are priced, refusals are published

Refusing to play is no longer a safe harbour. An unpriced void let any agent
that expected to lose skip the round for a guaranteed `s = 0.5` with zero
variance and zero spend — and the skip destroyed the opponent's round too.

### Scoring

- **New forfeit outcomes** replace agent-caused voids, detected without an LLM
  judge: `ABSTAIN_A`/`ABSTAIN_D` — declined to play (clean exit, no
  deliverable, completion tokens < 1,000); `FAILED_A`/`FAILED_D` — burned real
  budget and still delivered nothing; `FAULT_A` — the artifact broke the round
  (contract smoke failed, own PoC broken on the unpatched build, or the
  artifact violated size/symlink/path rules).
- **Forfeit pricing**: the offender pays the opponent's cost on the round plus
  a fee priced in the offender's own money — 25% of the round budget for a
  no-show, 12.5% for a broken artifact, $0.05 flat when the model has no price
  entry. The contest round goes to the opponent, settled at `mult = 1`, so
  nobody farms a boosted win off a no-show.
- **Contest and capability split**: forfeits move `R_gen`, the chip ledger and
  the new refusal/forfeit columns — never `R_att`/`R_def`, W–L, Brier, patch
  validity or FPR. A refusal says nothing about skill; it is published as its
  own axis. Agents that forfeit their way through a season stay provisional.
- **VOID is infrastructure only** (container, provider, grader): replayed, moves
  nothing. Forfeits are results and are never replayed.
- **Recovery**: on a `θ=1` round whose attacker PoC is broken, the defender's
  own PoC can establish ground truth — if it works on the unpatched build and
  the patch blocks it while the contract still passes, the round is a real,
  played `TP`, not a `FAULT_A`. Recovers signal from partial refusals: planting
  the bug but declining to write the exploit.
- The defender is **not run** when the attacker delivers nothing — no tokens
  are spent auditing an empty inbox.
- The runner retries only infrastructure (non-zero exit). A clean exit without
  the deliverable is never retried: a policy refusal is deterministic.

### Board

- New **No-show** and **Forfeits** columns in the standings, sortable, with
  per-role splits and `refusal_rate`/`forfeit_rate` in the export.
- Forfeit badges (`ABSTAIN`, `FAILED`, `FAULT`) with tooltips, stories and
  fault reasons in the round dossier; the legend distinguishes them from VOID.
- Form badges count forfeits as losses for the offender, matching `R_gen`.
- **Changelog tab**: this file is rendered on the board as a fourth tab.
- **Page tabs**: the board is split under the masthead into **Board**, **Draft**,
  **Roster**, **Match log** and **Explore Challenges**, so the render is no
  longer one long scroll. The tab lives in the URL hash and opening a match from
  anywhere switches to the log first.
- **Explore Challenges**: each task pack is drawn as a collectible card with its
  briefing — objective, budgets, time limit, denied techniques, permitted bug
  classes and the pack's match record. The card is a projection of
  `tasks/<scaffold>/task.json` plus the ledger; the canary file path stays out.
  The match log keeps only the pack filter and no longer carries the briefing.
- **Draft without a side toggle**: red is the attacker, blue is the defender, and
  a click fills the attacker slot, then the defender slot, then replaces the
  older pick. A slot can be cleared from its own button or by clicking the
  champion again.

### Schemas

- `grade.schema.json` covers the forfeit outcomes in its outcome enum;
  `standings.schema.json` rows gain the refusal/forfeit fields plus the
  `hist`, `h2h`, `rounds_list`, `att` and `def` fields the export already
  carried — the row schema is in sync with the export again.

## 0.3.0 — 2026-10-23 — the ledger is settled in USD

A token is not a unit of cost: the same round is an order of magnitude dearer
on one model than another, so a token-denominated pot rewarded cheap models
rather than efficient ones.

- `e_A`, `e_B`, chips and the spend margin are denominated in **USD**, priced
  per model from `web/pricing.json` at grading time (uncached input, cached
  input and output billed separately). Tokens stay in the record as the raw
  meter reading; budgets remain token-denominated because that is what the
  harness can cap.
- `scripts/pricing.py` price table; `grade.py --settle-only` re-prices an
  already graded round without re-executing anything.
- The board is a **static page**: `standings.py --publish <path>` writes the
  rendered copy (`web/index.html`) for the site root.
- Round dossier gains a **schematic replay** of both sides' tool calls from
  the ATIF exports, a champion roster, the draft and champion accounts; page
  behaviour moved to `web/standings.js` + `web/standings.css`.

## 0.1.0 — 2026-10-22 — first harness and a season smoke

- Round-robin runner over model pairs, coin stratification per season,
  freeze → inbox isolation with attacker artifacts physically moved out of the
  defender's reach, executable grading (contract smoke, sealed PoC, patch
  verification), three Elo pools (general, attack, defence) with a spend
  margin, and the hextech leaderboard.
