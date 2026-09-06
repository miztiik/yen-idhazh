# 06 - Fewer, better articles

**Last Updated**: 2026-09-05
**Level**: 3 (scoring, plan-stage selection, and the two run knobs the two-call design is sized against)

**Chain**: previous [`20260905-05-span-tree-plan.md`](20260905-05-span-tree-plan.md) | next [`20260905-07-better-summaries-plan.md`](20260905-07-better-summaries-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O6, O10, O25, O27, O32, rows 51, 52, 53, sections 8.2, 13.2, 14.2, 16.1, M11.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Two things at once. A better digest from the same budget - a feed that has been publishing badly still scores as though it had not, and the same story at two addresses is fetched, summarised, scored and published twice. **And the budget the rest of the programme needs**: at today's 40 items a shard, adding a second model call per item takes the worst shard past even a raised timeout |
| Hard scope - in | Feed reliability as a multiplier inside `authority()`; semantic duplicate collapse at the plan stage, record-only first; `run.safety_ceiling_per_run` 160 to 80; `run.shard_timeout_minutes` 150 to 200 |
| Hard scope - out | Any change to what a summary says (plan 07). Any cross-shard dedup worker - by the time every shard has finished, every model call has already been spent. Retiring any model |
| ESCALATE triggers | 1. The measured duplicate rate says a plan-time cut would remove more than 5 percent of a day - that is an editorial decision, not a throughput one. 2. Any vertical would fall under its `min_feeds` floor. 3. The reliability multiplier would move a feed's score by more than a factor of two on the committed window |
| Chosen strategy | Measure, then record-only, then cut. A cut at plan time is irreversible where the assemble grouping is reversible and visible |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The load-bearing row is #4, and it is not the item count.** `shard_timeout_minutes` 150 to 200 is what plan 11 needs. The worst measured shard used 90.3 percent of a 150-minute timeout over 80 rows; a second call at 20 items needs about 87 minutes on top of about 68. If row 4 slips, plan 11 overruns.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | How much of a day is the same story twice | - | A | DONE | - | #458 | w1 |
| 2 | A feed that publishes badly stops scoring as though it did not | - | A | DONE | - | #462 | w2 |
| 3 | The same story at two addresses is planned once | 1 | B | DONE | - | #467 | w3 |
| 4 | Half the day, and the clock the next plans need | 3 | C | DONE | - | #469 | w4 |

---

## 2. Row #1 - How much of a day is the same story twice

- **Scope:** Count, over every committed day payload, how many items carry `also_covered_by` - the upper bound on what a plan-time cut could save.
- **Files touched:** `docs/reference/measurements.md`
- **Acceptance gates:** none beyond the docs check; no code moves.
- **Oracle:** The recorded figure names the day count, the item count and the distribution, not a single mean - and states that it is an **upper bound**, because `also_covered_by` is computed after summarisation and a plan-time pass sees less.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The rate is measurable now with no run: the committed day payloads already carry the field | M11 |
| 2 | `carried_by` and `also_covered_by` are different counts and must not be pooled. `carried_by` is syndication of **one address**; `also_covered_by` is other sources telling the same story | Section 16.1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Size the dedup from the design and skip the measurement | Rule #10. And the number decides whether row 3 is worth its risk at all | Carmack |

---

## 3. Row #2 - A feed that publishes badly stops scoring as though it did not

- **Scope:** A reliability factor derived from a trailing window of committed outcomes, applied **multiplicatively** inside `authority()`.
- **Files touched:** `backend/idhazh/rank.py`, `backend/idhazh/ledger.py`, `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_rank.py`, `docs/concepts/freshness.md` or the ranking doc
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Replayed over the committed window, no vertical falls under its `min_feeds` floor and no feed's factor leaves the declared clamp. Both bounds asserted - a multiplier tested only in the middle of its range is untested.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Multiplicative, never additive. An added bonus lets a feed buy its way across a tier | Row 53 |
| 2 | It may **only ever reduce** - clamped to a floor above zero and a ceiling of 1.0 | Row 53 |
| 3 | The window is no shorter than 30 days, because a feed resting for five runs is the quarantine working, not evidence of quality | Row 53 |
| 4 | All 191 `weight` values in `config/sources.json` are 1.0, so the manual lever has never been pulled. That is why this is derived rather than hand-set | Row 53 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Retire the worst feeds instead | A vertical under `min_feeds` plans nothing at all, and two desks would go dark. Measured once already | Recorded finding |
| 2 | Hand-tune `weight` per feed | 191 values nobody has ever moved is evidence about the lever, not about the feeds | Editor |

---

## 4. Row #3 - The same story at two addresses is planned once

- **Scope:** Semantic duplicate collapse at the plan stage, using the encoder already in the dependency set, over a window read from `state/published.csv`. Record-only on its first run.
- **Files touched:** `backend/idhazh/rank.py`, `backend/idhazh/discover.py`, `backend/idhazh/embed.py`, `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_rank.py`, `docs/concepts/freshness.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch reading the record-only log.
- **Oracle:** On the record-only run, what the pass **would** have cut is written to the run record with what it was cut against, and the count matches row 1's upper bound to within the difference the design predicts. A dedup whose first live count is a surprise has not been measured.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Semantic, not string.** Only syndicated wire copy shares a title; on a significant event nearly every outlet writes its own headline, so a string match finds the one case `url_key` already catches | O27 |
| 2 | The encoder is already a hard dependency and embeds three summaries in 16 ms, so 80 titles is under a second and reaches no network | O27 |
| 3 | **Never cut a desk's only story.** Score is authority times carriers, so a single-carrier story scores lowest by construction and a straight top-N cut is a systematic cut of the exclusive story | Row 52 |
| 4 | A story that **developed** is not a duplicate - a re-run of a published story takes a recency decay, not a cut | Section 14.2 |
| 5 | Refused at the plan stage, not at assemble. `collapse_same_story` groups and removes nothing, and by assemble every model call is already spent | C11, section 14.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A separate cross-shard dedup job | Costs a runner slot and a cache restore, cannot start until the slowest shard finishes, and saves **zero** model calls | Carmack, section 14.2 |
| 2 | Cut on the first run | A plan-stage cut is irreversible where the assemble grouping is reversible and visible | Fowler |

---

## 5. Row #4 - Half the day, and the clock the next plans need

- **Scope:** `run.safety_ceiling_per_run` 160 to 80, and `run.shard_timeout_minutes` 150 to 200.
- **Files touched:** `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `frontend/src/lib/server/config.ts`, `backend/tests/test_contracts.py`, `docs/concepts/config.md`, `docs/concepts/freshness.md`, `docs/concepts/vision.md`, `docs/concepts/digest.md`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch of `digest.yml`; `bundle-gate`.
- **Oracle:** The dispatched run plans 80 items across 4 workers at 20 each, and every one of the seven places that assert "a normal day never reaches the ceiling" has been re-read and corrected. `git grep -n 'safety_ceiling_per_run'` returns no sentence that is now false.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One knob, not two. `shard_size` does not bind above 20 items a day - the shard count is `min(ceil(items/shard_size), max_parallel)` and `max_parallel` always wins. Changing `shard_size` is noise | Section 8.2 |
| 2 | `max_parallel` stays 4. Raising it to 8 keeps 160 items and **doubles** the 5.29 GiB cache restores | Section 8.2 |
| 3 | The timeout rise is free: minutes are unmetered on a public repository, a timeout is a ceiling and not an allocation, and 200 minutes is 56 percent of the 6 hour platform ceiling | O32, section 13.2 |
| 4 | **This is an editorial decision and must be presented as one.** The day publishes half as many stories. Row 3 governs which half is lost | Row 51, Editor |
| 5 | Do **not** lower the timeout to reclaim the halved item count. Size from the worst case, which is 135.4 minutes, not the median 78.5 | Section 13.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep 160 and raise `max_parallel` | Doubles the cache restores for the same work | Carmack |
| 2 | Change `shard_size` | It does not bind. Editing it changes nothing and invalidates every prior work identity | Carmack |
| 3 | Ship the item cut without the timeout rise | Then plan 11 overruns the worst shard by about five minutes and the failure surfaces as a dead run | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-05-span-tree-plan.md`](20260905-05-span-tree-plan.md) - the previous plan.
- [`20260905-07-better-summaries-plan.md`](20260905-07-better-summaries-plan.md) - the next plan.
