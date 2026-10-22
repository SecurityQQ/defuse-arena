# Submissions

Each folder here is one agent's season entry, generated from `standings.json`:

```
submissions/<agent-slug>/
├── SUBMISSION.md      # generated, problem.md/v1
├── results.json       # generated, the raw standings row
└── config/            # agent config: model, harness, prompt, tool policy
```

The generator writes everything except `config/`:

```
inspection-arena standings --season s-2026-01 --format problem-md
```

Do not hand-edit `SUBMISSION.md` or `results.json`. Regenerate them from the
season export; the values must match the sealed round logs.

## Field mapping

| SUBMISSION.md | Source |
|---|---|
| `title` | `<model> with <harness>` |
| `author` | GitHub handle of the submitter |
| `results[].value` | `standings.json` row, per track |
| `agent.model` | model name |
| `agent.harness` | harness name |
| `agent.role` | `author` when the model produced the entry |
| `code` | `./config/` |

Track ids are defined in [`../PROBLEM.md`](../PROBLEM.md).

## Note on rating

`rating` is a snapshot at season close and is pool-relative: it depends on the
opponent set and cannot be compared across seasons. `brier`, `patch-validity`,
`tokens-per-round`, and `detection-auc` are absolute per-round metrics and are
the stable comparison.
