# Agent instructions — Inspection Arena

## Model ids in a roster must be explicit

A season is defined by `rosters/<season>.tsv` (`label|model-id`). The model id
MUST be a leaf variant from `devin models list`, never a family slug. A family
slug resolves to that family's own default effort, and the defaults differ:

| slug | resolves to |
|---|---|
| `glm-5.3` | GLM-5.3 **Low** |
| `claude-opus-5.5` | Claude Opus 5.5 **Medium** |
| `gpt-6.1-sol` | GPT-6.1 Sol **Low Thinking** |
| `grok-4.7` | Grok 4.7 **XHigh** |
| `kimi-k3`, `muse-wonder` | **Max** |
| `gemini-4-argon` | **High** |
| `gpt-6-astra`, `claude-sonnet-5.5` | **Max** |
| `deepseek-v4-pro` | DeepSeek V4 Pro **High** |
| `glm-5.2` | GLM-5.2 High — this slug *is* the High variant |

A field written with slugs is therefore not "high everywhere" and not a
like-for-like comparison. For an all-high field:

```
deepseek|deepseek-v4-pro-high
glm-5.2|glm-5-2
glm-5.3|glm-5-3-high
opus-5.5|claude-opus-5-5-high
gpt-6.1|gpt-6-1-sol-high
gpt-6-astra|gpt-6-astra-high
gemini-4-argon|gemini-4-argon-high
kimi-k3|kimi-k3-high
sonnet-5.5|claude-sonnet-5-5-high
grok-4.7|grok-4-7-high
muse-wonder|muse-wonder-1-0-high
```

Before a season starts, check every id against `devin models list`. The CLI
records the resolved name in the ATIF export as `agent.model_name`, and the
board prints it under the label, so a wrong variant is visible rather than
silent.

## Long runs go to a background agent

A full round-robin is hours of wall clock and hundreds of agent calls. Launch
it in a **background** agent or background shell, not in the main conversation
thread: the main thread prepares the roster, starts the run, and reports
progress; it does not sit on the run. The 110-match s-2026-02 season took about
three hours and blocked the main thread for the whole run.

- Background subagent: `run_subagent` with `is_background=true`.
- Background shell: `exec` with `timeout: 0`, then poll with `get_output`.
- The runner is unattended: each match writes its own `result.tsv`, and
  `SKIP_DONE=1` resumes a run that stopped on rate limits.

## Repository rules

- `seasons/` is runtime data: never commit it, and never hand-edit a generated
  `standings.html`.
- `web/index.html` is a generated artifact: regenerate it with
  `python3 scripts/standings.py <season> [ranked_at] [render_ranked_at] --publish web/index.html`,
  never edit it.
- Record substantial changes in `CHANGELOG.md` in the same commit — see
  `.devin/skills/changelog/SKILL.md`.
