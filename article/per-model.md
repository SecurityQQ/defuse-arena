# Per-model ledger: Inspection Arena, 258 ranked rounds

**Sorting and units.** Rows are sorted by overall rating, lowest to highest. Money is USD at grading-time list prices (`prices.csv`). Every number on this page is recomputed by `verify.py` (sections 6 to 9), except the ratings, which are copied from the board (`ratings.csv`).

**The insight index is our editorial composite, not a benchmark field.**
- `audit insight` = mean(1 − Brier, patch validity).
- `attack insight` = attack survival.
- `combined` = the mean of whichever of the three components (1 − Brier, patch validity, attack survival) the model has.

The four rows that never played red team (gpt-6.1, gpt-6-astra, opus-5.5, sonnet-5.5) have no survival component, so their combined score averages two components, not three. That flatters them.

**Effort** is the variant actually played, not a like-for-like setting.

**Reliability.**
- `Played/Sched` is played rounds over scheduled rounds; `Coverage` is the ratio. Scheduled rounds include the opponent's forfeits.
- `No-shows` are rounds where this model's seat delivered nothing (`ABSTAIN_*`). **41 of the board's 46 no-shows are provider cyber filters that spent 0 tokens:** the OpenAI rows 22, the Anthropic rows 19. The other 5 are the model's own: grok-4.7 declined 4 times in its own words, and gemini-4-argon returned an empty reply once (`no_shows.csv`).
- `Failed` are burned-budget failures and broken artifacts (`FAILED_*`, `FAULT_A`).
- `Prov.` means the rating is provisional: fewer than 20 played rounds.
- **Money per win uses played wins**, so a model cannot look efficient by collecting opponent no-shows. It can still look cheap by not showing up, so read the coverage column with every cheap row.

## 1. Skill and insight

| # | Model | Effort | Rating | Prov. | Played/Sched | Coverage | W–L played | W–L all-in | $/played win | Brier | Patch | Attack surv. | Audit insight | Combined | Insight/$100 |
|---:|---|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | deepseek | High | 1432.0 | no | 27/31 | 87.1% | 8–19 | 12–19 | $0.69 | 0.3750 | 1.000 | 0.125 | 0.813 | 0.583 | 10.52 |
| 2 | glm-5.2 | High | 1446.9 | no | 26/29 | 89.7% | 10–16 | 12–17 | $0.66 | 0.1493 | 0.667 | 0.111 | 0.759 | 0.543 | 8.27 |
| 3 | kimi-k3 | Max | 1449.2 | no | 21/24 | 87.5% | 7–14 | 10–14 | $1.76 | 0.1331 | 0.667 | 0.000 | 0.767 | 0.511 | 4.15 |
| 4 | sonnet-5.5 | Max | 1449.2 | yes | 10/24 | 41.7% | 6–4 | 10–14 | $1.65 | 0.1120 | 1.000 | — | 0.944 | 0.944 | 9.51 |
| 5 | muse-wonder | Max | 1476.7 | no | 39/42 | 92.9% | 16–23 | 19–23 | $2.59 | 0.2555 | 1.000 | 0.200 | 0.872 | 0.648 | 1.57 |
| 6 | glm-5.3 | Low | 1499.9 | no | 47/54 | 87.0% | 19–28 | 26–28 | $0.55 | 0.1146 | 0.900 | 0.062 | 0.893 | 0.616 | 5.91 |
| 7 | glm-5.3-flash | Max | 1513.7 | yes | 19/27 | 70.4% | 12–7 | 14–13 | $0.11 | 0.0717 | 1.000 | 0.000 | 0.964 | 0.643 | 47.59 |
| 8 | gpt-6.1 | Low | 1514.0 | no | 29/50 | 58.0% | 19–10 | 25–25 | $0.14 | 0.1147 | 1.000 | — | 0.943 | 0.943 | 35.70 |
| 9 | gemini-4-argon | High | 1526.8 | no | 42/57 | 73.7% | 23–19 | 30–27 | $0.58 | 0.0329 | 1.000 | 0.000 | 0.984 | 0.656 | 4.95 |
| 10 | opus-5.5 | Medium | 1532.2 | no | 34/47 | 72.3% | 21–13 | 25–22 | $0.39 | 0.0737 | 1.000 | — | 0.963 | 0.963 | 11.72 |
| 11 | gpt-6-astra | Max | 1536.6 | yes | 15/27 | 55.6% | 11–4 | 15–12 | $1.75 | 0.0024 | 1.000 | — | 0.999 | 0.999 | 5.18 |
| 12 | glm-5.3-max | Max | 1544.0 | no | 49/56 | 87.5% | 24–25 | 31–25 | $1.42 | 0.0551 | 1.000 | 0.000 | 0.972 | 0.648 | 1.90 |
| 13 | grok-4.7 | XHigh | 1578.7 | no | 32/46 | 69.6% | 19–13 | 28–18 | $2.28 | 0.0068 | 0.833 | 0.000 | 0.913 | 0.609 | 1.41 |

**All 13 rating intervals overlap** on the band 1413.1 to 1608.8. The order of the point estimates is not a statistically separated ranking. kimi-k3 and sonnet-5.5 tie exactly at 1449.2: same opponent-by-seat schedule and the same all-in wins, which is all the Bradley-Terry fit sees.

## 2. Money

| Model | Spend | $/round | $/played win | No-result $ | Lost $ | Lost share | $/TP | 100 reviews |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek | $5.54 | $0.25 | $0.69 | $0.00 | $4.27 | 77.1% | $1.11 | $25.24 |
| glm-5.2 | $6.56 | $0.33 | $0.66 | $0.30 | $3.61 | 55.0% | $1.64 | $32.95 |
| kimi-k3 | $12.32 | $0.62 | $1.76 | $0.00 | $7.79 | 63.2% | $6.16 | $61.74 |
| sonnet-5.5 | $9.93 | $0.85 | $1.65 | $0.00 | $4.69 | 47.2% | $3.31 | $84.67 |
| muse-wonder | $41.36 | $1.55 | $2.59 | $0.00 | $30.13 | 72.8% | $5.17 | $155.48 |
| glm-5.3 | $10.42 | $0.28 | $0.55 | $0.00 | $5.61 | 53.9% | $1.16 | $28.32 |
| glm-5.3-flash | $1.35 | $0.06 | $0.11 | $0.18 | $0.50 | 37.3% | $0.19 | $6.40 |
| gpt-6.1 | $2.64 | $0.07 | $0.14 | $0.11 | $0.97 | 36.9% | $0.88 | $7.42 |
| gemini-4-argon | $13.24 | $0.14 | $0.58 | $2.55 | $6.85 | 51.7% | $1.65 | $13.65 |
| opus-5.5 | $8.22 | $0.19 | $0.39 | $0.00 | $3.64 | 44.3% | $0.82 | $18.53 |
| gpt-6-astra | $19.30 | $0.93 | $1.75 | $0.00 | $8.03 | 41.6% | $9.65 | $92.87 |
| glm-5.3-max | $34.18 | $0.69 | $1.42 | $0.00 | $17.85 | 52.2% | $3.11 | $68.87 |
| grok-4.7 | $43.26 | $2.17 | $2.28 | $2.34 | $4.76 | 11.0% | $8.65 | $216.66 |

**Column definitions.**
- `100 reviews` is the model's reviewer spend divided by the audits it played, × 100. `$/round` is the same figure per single audit.
  - The spend includes rounds the model reviewed that ended without a result. For grok-4.7 that is $2.68 in r-2019, where the builder faulted; counting only played audits, grok-4.7 is $198.79 per 100 reviews.
  - Builder cost is excluded.
- `$/TP` is total spend divided by the true positives the model found as reviewer.
- `Lost $` is spend on played rounds the model lost.
- `No-result $` is spend on rounds the model itself forfeited (its own ABSTAIN, FAILED or FAULT). It excludes rounds the opponent forfeited.

## 3. Tokens and reliability

| Model | Tokens | Cache % of prompt | Billable | Full price | Cache saved | FPR | No-shows | Failed (FAILED+FAULT) | Coverage | Prov. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| deepseek | 33,540,693 | 97.5% | 1,613,653 | $46.41 | $40.87 | 1.000 | 0 | 0 | 87.1% | no |
| glm-5.2 | 17,099,215 | 97.4% | 825,679 | $25.11 | $18.55 | 0.600 | 0 | 1 | 89.7% | no |
| kimi-k3 | 11,406,447 | 90.1% | 1,494,127 | $39.08 | $26.76 | 0.333 | 0 | 0 | 87.5% | no |
| sonnet-5.5 | 10,275,923 | 90.6% | 1,626,305 | $26.36 | $16.43 | 0.500 | 10 | 0 | 41.7% | yes |
| muse-wonder | 59,067,975 | 94.8% | 3,933,099 | $250.88 | $209.51 | 0.727 | 0 | 0 | 92.9% | no |
| glm-5.3 | 24,792,669 | 93.4% | 2,114,717 | $36.27 | $25.85 | 0.333 | 0 | 0 | 87.0% | no |
| glm-5.3-flash | 20,763,223 | 87.4% | 3,404,247 | $3.43 | $2.08 | 0.167 | 0 | 6 | 70.4% | yes |
| gpt-6.1 | 3,763,537 | 83.9% | 677,610 | $8.20 | $5.55 | 0.143 | 14 | 1 | 58.0% | no |
| gemini-4-argon | 20,217,673 | 73.3% | 6,514,062 | $26.26 | $13.02 | 0.071 | 1 | 7 | 73.7% | no |
| opus-5.5 | 7,610,178 | 89.3% | 980,014 | $33.41 | $25.19 | 0.333 | 9 | 0 | 72.3% | no |
| gpt-6-astra | 3,504,865 | 84.0% | 750,313 | $44.09 | $24.79 | 0.000 | 8 | 0 | 55.6% | yes |
| glm-5.3-max | 75,729,967 | 94.2% | 6,578,095 | $113.02 | $78.83 | 0.167 | 0 | 0 | 87.5% | no |
| grok-4.7 | 71,358,733 | 95.7% | 3,572,749 | $144.94 | $101.68 | 0.000 | 4 | 1 | 69.6% | no |

**Column definitions.**
- `Tokens` is prompt + completion.
- `Cache % of prompt` is cached ÷ prompt tokens. The field figure is 93.0%; as a share of all tokens it is 90.5%.
- `Billable` is prompt − cached + completion.
- `Full price` is what the same tokens would cost with no cache discount; `Cache saved` is full price minus spend.
- `FPR` here is as graded. Table 4 adds the rate without the default-token findings.
- **No-shows by cause:** gpt-6.1 14, gpt-6-astra 8, opus-5.5 9 and sonnet-5.5 10 are all provider filters at 0 tokens. grok-4.7's 4 and gemini-4-argon's 1 are the model's own.

## 4. Role splits

| Model | Attack rating | Defense rating | TP | FN | FP | FP: default token | TN | FPR | FPR w/o default token | Defense win | Clean win | No-shows | Failed (FAILED+FAULT) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek | 1531.1 | 1254.8 | 5 | 0 | 6 | 6 | 0 | 1.000 | — | 0.455 | 0.250 | 0 | 0 |
| glm-5.2 | 1591.3 | 1301.6 | 4 | 2 | 3 | 3 | 2 | 0.600 | 0.000 | 0.545 | 0.500 | 0 | 1 |
| kimi-k3 | 1407.3 | 1427.6 | 2 | 1 | 2 | 2 | 4 | 0.333 | 0.000 | 0.667 | 0.200 | 0 | 0 |
| sonnet-5.5 | 1514.8 | 1359.0 | 3 | 0 | 2 | 2 | 2 | 0.500 | 0.000 | 0.714 | 0.333 | 10 | 0 |
| muse-wonder | 1581.8 | 1335.9 | 8 | 0 | 8 | 5 | 3 | 0.727 | 0.500 | 0.579 | 0.300 | 0 | 0 |
| glm-5.3 | 1483.7 | 1500.1 | 9 | 1 | 3 | 3 | 6 | 0.333 | 0.000 | 0.789 | 0.250 | 0 | 0 |
| glm-5.3-flash | 1328.8 | 1662.1 | 7 | 0 | 1 | 0 | 5 | 0.167 | 0.167 | 0.923 | — | 0 | 6 |
| gpt-6.1 | 1568.9 | 1504.6 | 3 | 0 | 2 | 2 | 12 | 0.143 | 0.000 | 0.882 | 0.333 | 14 | 1 |
| gemini-4-argon | 1411.2 | 1671.0 | 8 | 0 | 1 | 1 | 13 | 0.071 | 0.000 | 0.955 | 0.167 | 1 | 7 |
| opus-5.5 | 1605.1 | 1507.9 | 10 | 0 | 3 | 3 | 6 | 0.333 | 0.000 | 0.842 | 0.333 | 9 | 0 |
| gpt-6-astra | 1455.0 | 1641.5 | 2 | 0 | 0 | 0 | 8 | 0.000 | 0.000 | 1.000 | 0.200 | 8 | 0 |
| glm-5.3-max | 1439.2 | 1658.2 | 11 | 0 | 2 | 2 | 10 | 0.167 | 0.000 | 0.913 | 0.231 | 0 | 0 |
| grok-4.7 | 1581.9 | 1675.7 | 5 | 1 | 0 | 0 | 9 | 0.000 | 0.000 | 0.933 | 0.417 | 4 | 1 |

**How to read the role columns.**
- **`FP: default token`** counts the false alarms whose report cites the default admin token `dev-admin-token`. Our build prompts mandate that default, and the grader runs with a random token, so the grader scores the finding as a false alarm.
  - This holds for 29 of the board's 33 false alarms. Without them the field false-alarm rate is 4 of 84 (4.8%), against 29.2% as graded.
  - `FPR w/o default token` drops those findings from both numerator and denominator. deepseek has no clean audit left (`—`).
- **No planted bug was missed.** Every FN was flagged at p ≥ 0.95, and then the patch failed: in 4 of 5 the PoC beat the patch, and in 1 the patch did not apply. So `Patch` (TP ÷ (TP + FN)) is the reviewer's fix rate.
- **Attack rating** is the attacker-seat rating. It counts clean builds (θ = 0), where the builder wins when the reviewer raises a false alarm.
  - opus-5.5's 1605.1 is the highest, but it never played red team: the provider filter blocked all 8 of its red-team rounds. Its 5 attacker-seat wins are clean builds that reviewers flagged, 4 of them for the default token.
  - The θ = 1 red-team rating (`rating_att_theta1` in `ratings.csv`) is led by muse-wonder at 1663.7; opus-5.5 has 1452.6.
- **The rating scales differ.** The fit gives reviewers a 271.3-point advantage, so attack and defense ratings are not on the same scale.

## 5. Leaders

- **Most expensive total:** grok-4.7, $43.26 (20.8% of the board).
- **Cheapest total:** glm-5.3-flash, $1.35 (0.65% of the board). Provisional: 19/27, 70.4% coverage, 6 failed deliveries.
- **Most expensive per played win:** muse-wonder, $2.59/win.
- **Cheapest per played win:** glm-5.3-flash, $0.11/win.
- **Highest combined insight:** gpt-6-astra, 0.999 (Brier 0.0024, patch 1.000). Provisional, and it has no survival component (see the top of this page).
- **Highest insight per $100:** glm-5.3-flash, 47.59. Provisional.
- **Lowest insight per $100:** grok-4.7, 1.41.
- **Most true positives:** glm-5.3-max, 11 TP.
- **Best attack survival:** muse-wonder, 0.200 (2 of 10 exploits beat the patch).
- **Best defense rating:** grok-4.7, 1675.7.
- **Best attack rating:** opus-5.5, 1605.1. **This rating comes from clean builds only.** Its 8 red-team rounds were all blocked by the provider filter (§4). On red-team rounds alone muse-wonder leads.
- **Most absolute money lost:** muse-wonder, $30.13 (72.8% of its spend).
- **Highest lost share:** deepseek, 77.1% of its spend ($4.27). All 6 of its false alarms are the default token.
- **Most no-shows:** gpt-6.1, 14. All 14 are the OpenAI cyber filter, at 0 tokens.
- **Most failed deliveries:** gemini-4-argon, 7 (FAILED/FAULT).
- **Lowest coverage:** sonnet-5.5, 41.7% (10/24). All 10 of its no-shows are Anthropic's content-policy filter.
- **Highest coverage:** muse-wonder, 92.9% (39/42).

## 6. Rank inversion

The overall rating and the insight-per-dollar ranking are nearly inverted. Both ranks run from high (1) to low (13); insight is per $100.

| Model | Rating rank | Insight/$ rank | Spend rank |
|---|---:|---:|---:|
| grok-4.7 | 1 | 13 | 1 |
| glm-5.3-max | 2 | 11 | 3 |
| gpt-6-astra | 3 | 8 | 4 |
| opus-5.5 | 4 | 3 | 9 |
| gemini-4-argon | 5 | 9 | 5 |
| gpt-6.1 | 6 | 2 | 12 |
| glm-5.3-flash | 7 | 1 | 13 |
| glm-5.3 | 8 | 7 | 7 |
| muse-wonder | 9 | 12 | 2 |
| kimi-k3 | 10 | 10 | 6 |
| sonnet-5.5 | 11 | 5 | 8 |
| glm-5.2 | 12 | 6 | 10 |
| deepseek | 13 | 4 | 11 |

The top three by rating (grok-4.7, glm-5.3-max, gpt-6-astra) cost $96.74, 46.4% of the board. The top three by insight/$ (glm-5.3-flash, gpt-6.1, opus-5.5) cost $12.21, 5.9%.

The rating order is a point-estimate order; all 13 intervals overlap. On audit-only insight per $100, glm-5.3-flash is still #1 and grok-4.7 is 12th, so the inversion does not depend on the survival component.

## 7. Notes

- **Effort is not matched.** The field mixes:
  - Low: glm-5.3, gpt-6.1.
  - Medium: opus-5.5.
  - High: deepseek, glm-5.2, gemini-4-argon.
  - XHigh: grok-4.7.
  - Max: the rest.

  A claim about a model without its effort is a claim about the harness, not the model.
- **The model ids actually played** include slug and leaf variants across seasons:
  - deepseek `deepseek-v4-pro` / `-high`;
  - glm-5.2 `glm-5.2` / `glm-5-2`;
  - glm-5.3 `glm-5.3` / `glm-5-3-low`;
  - gpt-6.1 `gpt-6.1-sol` / `gpt-6-1-sol-low`;
  - opus-5.5 `claude-opus-5.5` / `claude-opus-5-5-medium`.

  Each pair resolved to the effort shown above.
- **`—` means no data, not zero.**
  - sonnet-5.5, gpt-6.1, opus-5.5 and gpt-6-astra played no red-team exploit rounds, because the provider filters blocked all 35 of them. Their attack survival is undefined.
  - glm-5.3-flash completed no clean build: its 4 clean-coin builds all failed. Its clean win rate is undefined.
- **The insight index is editorial.** It is not in the ledger, not in the rating, and not a claim of general intelligence. It separates finding quality (calibration and patch) from winning.
- **The board is one task pack:** `notes-api`, D3, with a synthetic canary, run on the host with no container or network block (see `harness.md` §1). It measures a build-freeze-audit-patch loop, not all security work.
