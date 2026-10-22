# Task packs

A task pack is what the attacker builds against. It fixes the service contract,
the scaffold, the conformance suite, and the bug classes that are legal for the
pack, so two rounds stay comparable across agents.

## Layout

```
tasks/<task_id>/
├── task.json          # manifest, validated by schemas/task.schema.json
├── BRIEF.md           # what the service does; shared with the defender
├── openapi.yaml       # the contract the service must satisfy
├── conformance/       # immutable tests, harness-owned
├── scaffold/          # starter code, harness-owned
├── seeds/             # deterministic fixtures
└── reference/         # known-good implementation, used to validate the pack
```

`task.json`, `openapi.yaml`, `conformance/`, `seeds/`, and `reference/` are
harness-owned. The attacker must not modify them.

## v1 families

| Family | Service shape | Typical bugs |
|---|---|---|
| `crud-auth` | notes, todos, bookmarks | authz, IDOR, session, mass assignment |
| `files` | uploads, exports, attachments | path traversal, zip slip, content type |
| `query` | search, reports, filters | SQL injection, query injection, ReDoS |
| `render` | invoices, emails, markdown | SSTI, unsafe HTML |
| `jobs` | webhooks, retries, queues | signature bypass, race, idempotency |
| `ledger` | balances, transfers | logic, race, rounding |
| `tenancy` | orgs, memberships, invites | tenant isolation, role confusion |
| `admin` | flags, config, roles | privilege escalation, header trust |

Denied everywhere: memory corruption, kernel bugs, supply chain, deserialization
RCE, `eval`/`exec`, network egress, real-world targets, persistence, host access.

## Ranked vs exhibition

- Ranked rounds must use a pack from the catalog.
- Free-form tasks are allowed only in `exhibition` matches, which are unscored.
- The attacker chooses a band from the pack's `difficulty_bands`.
- If `θ=1`, the bug must belong to `bug_classes` and the sealed PoC must read
  the canary through the service.

## Proposals

New packs go through `tasks/proposals/<task_id>/` and `task review`. A proposal
cannot be used in the season it was proposed; after that it needs either one
season of age or two independent approvals. This prevents tailoring a task to a
specific opponent.

## Reference pack

`notes-api/` is the reference pack. Only the manifest exists so far; the
scaffold, conformance suite, and reference implementation arrive in Phase 1.
