---
name: changelog
description: Record every substantial modification to this repository as a CHANGELOG.md entry, in the same change that introduces it. Invoke before calling any non-trivial work here done.
---

# Changelog discipline

Every substantial modification to this repository MUST be recorded in
`CHANGELOG.md` in the same change that introduces it — the entry is part of the
work, not a follow-up.

## What counts as substantial

- Scoring, grading, ratings, chips, outcome taxonomy, budgets, fees.
- Round protocol, prompts, artifact contract, isolation or runner behaviour.
- Schemas, ledger/standings field formats, `scoring_version` bumps.
- Board structure: columns, tabs, sections, publish flow.

Not substantial: typo and comment edits, formatting, generated season data
under `seasons/`, dependency bumps with no behaviour change.

## How to write the entry

- Put it under the version heading at the top, newest first. If the change
  alters scoring semantics, bump the `scoring_version` written by
  `scripts/grade.py` / `scripts/standings.py` and use that number in the
  heading (`## <version> — <date> — <one-line theme>`).
- Group bullets under small `###` section headings (Scoring, Board, Harness…).
- One bullet per behaviour change, written for an operator reading the board:
  what changed, why it matters, what the old behaviour was when it replaced
  something.
- Plain markdown only — the board renders this file in its Changelog tab.
  Inline `code` and **bold** are fine; no HTML, no links, no images.

## Board wiring

`scripts/standings.py` reads `CHANGELOG.md` into the page payload and the
Changelog tab renders it. After adding an entry, regenerate the published board
so the tab shows it:

```
python3 scripts/standings.py <season> [ranked_at] [render_ranked_at] \
  --publish web/index.html
```
