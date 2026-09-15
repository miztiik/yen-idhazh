# Per-item observability, and the spine that holds it

**Last Updated**: 2026-09-15

**Level**: 5 (persisted contracts, section 6). Rows 2, 3 and 4 change shapes an earlier run already wrote.

**Every row has landed.** Section 13 records what execution surfaced that the plan did not predict, and the two decisions it handed back.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A 5x model-time regression ran for six days and no surface named it. Median model time per item moved 97,879 ms -> 475,890 ms between run `34745383977` (2026-09-13) and run `34852763827` (2026-09-14), median output tokens 229 -> 1,158, and the two agree within 4 percent, so the whole move is decoded-token volume at an unchanged decode rate. Nothing recorded that the configuration had changed, nothing printed during a 200-minute shard, and the published telemetry mirror carries no second-call columns at all. This plan builds the instrument that makes the next one visible on day one |
| Hard scope - in | `state/item-health/<YYYY>/<MM>/<DD>.csv` widened to the per-item spine (selection terms, per-stage delays, per-call tokens and cache, per-item hardware, configuration provenance, full failure detail). Structured per-item, per-stage and heartbeat log lines from `work.py`. Prebaked selection sub-scores on `PlannedItem`. The `item_label_call` / `summarize_and_visual_decision_call` rename across code, persisted columns and prose. Prompt and reply capture to a 90-day artifact behind a config flag. `recovered_completion` wired to a caller. The cancelled-shard artifact loss. A dispatch-only three-arm test workflow |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. A read-side migration cannot be written for a widened persisted shape, and the row proposes a dual read side instead. 2. A row proposes to change the grain of any directory under `frontend/public/`. 3. A row proposes to delete `frontend/public/telemetry/` while the console still fetches it. 4. A row proposes `n_parallel` above 1 as a production default before row 11 has measured it. 5. A row proposes to change an output budget, a truncation cap or the call sequence - this plan builds the instrument and changes no pipeline behaviour that selects or shortens what publishes. 6. The widened day file exceeds 150 KB at 80 rows |
| Chosen strategy | Contracts land before the producers that write them and the readers that parse them (Fowler, CLAUDE.md section 14); the three test arms run sequentially on one runner because the between-runner spread is 4.2x and would swallow the effect (Carmack, Guardrail #10) |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. **Rows group into five pull requests, not eleven** - the `Ships on` column is authoritative. Stack commits inside a group; one PR per group. Documentation-only edits land on `main` directly with no PR (owner decision, 2026-09-14) |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Fixing the slowdown itself - output budgets, the truncation cap, `run.max_parallel`, the call sequence | The pipeline stays at roughly 200 minutes a run and keeps cancelling shards | This plan's instrument producing the per-call rate and per-stage split that a fix would be argued against. The fix is the next plan, and it is deliberately not this one |
| Streaming call 2 to timestamp the `visual` field boundary (the exact split) | The summary-vs-plan split is a token ratio, labelled an estimate in the data | Row 7's estimate disagreeing with row 11 arm S2's measured delta by more than 10 percent |
| Changing `frontend/public/` from month to day grain | `state/` and the published mirror stay at different grains | An owner ruling. `console.window_presets` includes 90 days, which is 5 fetches at month grain and up to 90 at day grain, and `WindowControl.svelte` prices the month figure |
| Deleting `frontend/public/telemetry/` and serving telemetry from `state/` | Telemetry keeps a second home shaped for a browser rather than for analysis | A console data path that reads from somewhere else. Owner intends this; it is not a row here because the console breaks the day the directory goes |
| Retiring `keyphrases` and `lede_sentence_ids` from the label call | The label call keeps decoding two arrays with zero consumers anywhere in the pipeline | A reading of what those two arrays cost in decoded tokens, which row 5 produces for free once `label_tokens_written` is split by field |
| `n_parallel: 2` as a production default | Possible decode throughput left on the table | Row 11 arm S3's number, taken on one runner against arm S1 |
| Retiring `state/runtime-counters.csv` now that item-health carries the same signals | Two ledgers carry overlapping machine data | A row in a later plan, after item-health has written the hardware columns for long enough to prove they are equivalent |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Ships on | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The two calls get names that say what they do | - | A | PR-1 | PENDING | - | - | - |
| 2 | `state/item-health/` becomes the per-item spine | 1 | B | PR-2 | PENDING | - | - | - |
| 3 | The selection score carries its own terms | - | B | PR-2 | PENDING | - | - | - |
| 4 | Logging is a set of flags, not a level | - | B | PR-2 | PENDING | - | - | - |
| 5 | `work.py` says what it is doing, per item and per stage | 2, 3, 4 | C | PR-3 | PENDING | - | - | - |
| 6 | Every item records the machine that ran it | 2, 4 | C | PR-3 | PENDING | - | - | - |
| 7 | The summary and the picture are timed apart | 2 | C | PR-3 | PENDING | - | - | - |
| 8 | What the model saw, kept for 90 days | 4 | C | PR-3 | PENDING | - | - | - |
| 9 | A cut reply keeps its summary | 1 | D | PR-4 | PENDING | - | - | - |
| 10 | A killed shard keeps the work it finished | - | D | PR-4 | PENDING | - | - | - |
| 11 | Two articles, three arms, one runner | 4 | E | PR-5 | OPEN | p27-tests | #740 | - |

### Pull request groups

| Group | Rows | One sentence |
| --- | --- | --- |
| PR-1 | 1 | The rename, atomic across code, persisted columns and prose |
| PR-2 | 2, 3, 4 | Every contract and config change, so rows 5-8 rebase once instead of three times |
| PR-3 | 5, 6, 7, 8 | The instrument itself, all of it inside `work.py` and its immediate neighbours |
| PR-4 | 9, 10 | Two defects that waste work already paid for |
| PR-5 | 11 | The workflow and its URL list |

## 2. Row #1 - The two calls get names that say what they do

- **Scope:** `call_one` / `call_two` and their prose become `item_label_call` / `summarize_and_visual_decision_call`, including the persisted `call_1_*` and `call_2_*` ledger columns, which become `label_*` and `summary_*`.
- **Files touched:**
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/dag.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/contracts/public_telemetry.py`
  - `backend/idhazh/publish_telemetry.py`
  - `schemas/item-health-row.schema.json`, `schemas/public-telemetry.schema.json`
  - the remaining 32 files carrying the old spelling (13 under `backend/idhazh`, 10 under `backend/tests`, 5 `docs/architecture`, 5 `docs/reference`, 3 `docs/concepts`, 1 `.github/workflows`, 1 `backend/utilities`, 1 `docs/how-to`)
- **Acceptance gates:** local - `ruff`, `mypy`, the contract export, and the test modules the selector names for the touched files. CI - full suite and the drift gate.
- **Oracle:** a fixture item-health row written in the committed 42-column shape reads back through the read-side migration with `label_*` and `summary_*` populated from `call_1_*` and `call_2_*`, and a row written in the new shape round-trips byte-identical through the contract. It cannot settle whether any prose sentence still reads naturally after substitution; a human reads the docs diff.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The rename lands first so every row after it is written in the new names | Fowler |
| 2 | `CallName.LABEL` and `CallName.SUMMARIZE_AND_PLAN` already say what they do and do not change; only the `call_one_*` / `CALL_ONE_*` helpers, the persisted columns and the prose move | Fowler |
| 3 | The persisted column rename carries a `version` stamp, a `changelog` entry and the read-side migration in the same commit | CLAUDE.md section 11 |
| 4 | `frontend/public/telemetry/<YYYY-MM>.csv` gains the six second-call columns it has never carried, renamed, in this row | owner, 2026-09-14 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Rename the prose, leave the persisted columns | The columns are the surface an operator reads; renaming everything except the thing they look at is the drift this row exists to end | Nothing to take - it is cheaper. It costs a permanent mismatch between what the code calls the call and what the ledger calls it | Fowler |
| 2 | Do the rename last, after the instrument lands | Rows 2 and 5 write new columns; landing them under the old naming means renaming them again a week later | One extra rename pass over the new columns, and every row between written twice | Fowler |

## 3. Row #2 - `state/item-health/` becomes the per-item spine

- **Scope:** the item-health row gains the selection terms, the per-stage delays, the per-call token and cache figures, the per-item hardware readings, the configuration provenance and the full failure detail, with a read-side migration for every committed row.
- **Files touched:**
  - `backend/idhazh/contracts/item_health.py`
  - `schemas/item-health-row.schema.json`
  - `backend/idhazh/ledger.py`
  - `backend/tests/fixtures/` - one fixture row in the committed shape, one in the new shape
- **Acceptance gates:** local - the contract export, `ruff`, `mypy`, the ledger and telemetry test modules. CI - full suite and the drift gate.
- **Oracle:** a fixture row in the committed 42-column shape reads back with every new column at its declared absent value and no exception, and a fully-populated new row round-trips byte-identical. It cannot settle whether these are the right columns to have chosen; only row 11 running against a real regression can.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The day grain stays. `ledger.item_health_path` already writes `state/item-health/<YYYY>/<MM>/<DD>.csv` and plan 24 row #5 ruled it | plan 24, PR #656 |
| 2 | Configuration provenance is denormalised onto every row - `model_id`, `n_ctx_configured`, `n_parallel`, `n_threads`, `n_batch`, `max_output_tokens`, `label_budget_tokens`, `summary_budget_tokens`, `run_visual_decision`, `model_calls`, `temperature`, `truncation_cap_tokens`. A row that cannot say what it was configured as is a row that gets read wrong, and that is precisely how a 5x move read as weather | owner, 2026-09-14 |
| 3 | `stage_gap_ms` is carried: `item_total_ms` minus every named stage. Unattributed time is the only column that can catch a regression in a stage nobody has thought to name yet | Fowler |
| 4 | `detail` carries the full exception message. `work.py` lines 674 and 834 log `type(error).__name__` and discard the Pydantic message, which is the only text that names the failing field | owner, 2026-09-14 |
| 5 | The two existing writers stay. The second records items a shard never reached, which a writer inside the work loop cannot do because a killed shard writes nothing. Repeats stay settled by `ITEM_HEALTH_KEY` | `ledger.py` line 424 |
| 6 | Four decode-rate columns are stored rather than derived at read time - `label_prefill_tokens_per_s`, `label_decode_tokens_per_s`, `summary_prefill_tokens_per_s`, `summary_decode_tokens_per_s` | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Join `state/scores/` into item-health for one table | `state/scores/` carries an `attempt` column, so its grain is (item, attempt). A 1:1 join duplicates every mechanics row on a re-score | A composite key and a read side that de-duplicates on every read. Priced by counting rows where `attempt > 1` across the committed archive | Fowler |
| 2 | Keep configuration provenance in `state/runtime-counters.csv` and join on `run_id` plus `shard` | The strings repeat across 80 rows of a shard, so the join saves most of the widening cost - but a reader who forgets the join reads a row wrong, silently | About 70 MB less in `state/` across the 14-month retention window. Measured from the committed 2026-09-14 day file: 80 rows, 42 columns, 334 bytes a row, 26.6 KB | owner, 2026-09-14 |
| 3 | A new ledger beside item-health rather than widening it | Two files with the same key and the same grain is the shape this plan is consolidating away from | A second writer, a second retention rule and a join on every read | Fowler |

## 4. Row #3 - The selection score carries its own terms

- **Scope:** `PlannedItem` gains the terms that compose `rank_score`, so an operator can see which part of the score admitted a story.
- **Files touched:**
  - `backend/idhazh/contracts/run_plan.py`
  - `schemas/run-plan.schema.json`
  - `backend/idhazh/rank.py`
  - `backend/idhazh/stages/plan.py`
- **Acceptance gates:** local - the contract export, `ruff`, `mypy`, the rank and plan test modules. CI - full suite and the drift gate.
- **Oracle:** for every item in a built fixture plan, `authority_score + carriage_step + watchlist_bonus + lens_bonus + recency_bonus` equals `selection_score` to six decimal places, which is the rounding `rank.score` applies. It cannot settle whether any individual term is correct - only that the parts sum to the whole the ranker already publishes.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The terms are prebaked in the plan stage, never recomputed in `work.py`. A second copy of the ranker's arithmetic is a second thing to keep in step | Guardrail #5 |
| 2 | Terms carried: `authority_score`, `tier_score`, `feed_weight`, `feed_reliability`, `lens_bonus`, `recency_bonus`, `carriage_step`, `watchlist_bonus` | owner, 2026-09-14 |
| 3 | A desk carries no score and none is invented. A desk has a per-desk ceiling and a feed floor, which are quotas | `rank.day_source_ceiling`, `rank.desks_below_floor` |
| 4 | Slots are declared now for scores that in-flight plans will produce - `label_confidence` (plan 23), `relationship_score` and `fit_weight` (visual planning architecture), `dual_score` and `null_score` (known defects). They are nullable and read empty until a producer exists | owner, 2026-09-14 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Log only `rank_score` and skip the contract change | An operator can see that an article scored 1.84 and never why, which is the same blindness one level down | Nothing to take. It costs the reason behind every admission decision | owner, 2026-09-14 |
| 2 | Recompute the terms in `work.py` from config | `feed_reliability` is built once per run from the feed ledger and is not in `work.py`'s hands; the rest would be a duplicate ranker | Passing the reliability map into every shard, and a second implementation to keep in step | Fowler |

## 5. Row #4 - Logging is a set of flags, not a level

- **Scope:** `config/idhazh.json` gains a `logging` block that turns each new line type on and off, defaulting on, each flag carrying its removal condition on the line that declares it.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `config/idhazh.json`
- **Acceptance gates:** local - the contract export, `ruff`, `mypy`, the app-config test module. CI - full suite and the drift gate.
- **Oracle:** with every flag false the run emits exactly the log lines `main` emits today, byte-identical on a fixture run; with every flag true each declared line type appears exactly once per item. It cannot settle whether the defaults are right for a quiet production run; that is a later reading.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Flags default true, to be flipped once the slowdown is closed | owner, 2026-09-14 |
| 2 | Flags: `item_lines`, `stage_lines`, `waiting_heartbeat_seconds`, `capture_prompts`, `capture_replies` | owner, 2026-09-14 |
| 3 | `item_lines` carries no removal condition because it is the permanent instrument; every other flag names the reading that retires it | Guardrail #6 |
| 4 | `logging.level` stays and is unrelated. These flags choose which records exist, not how loud the logger is | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Reuse `logging.level` DEBUG instead of flags | One switch cannot turn on per-item lines while leaving prompt capture off, and prompt capture is the expensive one | Nothing to build. It costs the ability to keep the cheap instrument and drop the expensive one | Fowler |

## 6. Row #5 - `work.py` says what it is doing, per item and per stage

- **Scope:** `work.py` emits a start line, a per-stage line, a per-item completion line, a heartbeat while a model call is in flight, an abandoned line when a timeout kills an item mid-flight, and a shard summary, each a flattened single-line JSON record.
- **Files touched:**
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/telemetry.py`
  - `backend/tests/` - the work-stage test module
- **Acceptance gates:** local - `ruff`, `mypy`, the work-stage and telemetry test modules driven from the canary day under `backend/var/canary/`. CI - full suite.
- **Oracle:** for a built fixture item every field declared in row 2's contract is present on the completion line, and `stage_gap_ms` equals `item_total_ms` minus the sum of the named stages to within 1 ms. It cannot settle whether a human reads the line easily; a person reads one.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Records are flat single-line JSON. A nested envelope makes the common operation - grep one field across a shard - harder than it needs to be | owner, 2026-09-14 |
| 2 | The start line exists so a killed shard names the item it died on. Today a timeout leaves no trace of the in-flight item at all | owner, 2026-09-14 |
| 3 | The completion line is emitted for failures as well as successes. `item scored` at line 294 fires only for items that passed, so the expensive failures are the least visible thing in the log | owner, 2026-09-14 |
| 4 | The article title is not logged. It is raw feed text and `telemetry.event` does not sanitise; `canonical_url` and `source_id` are recomputed identity and are safe | Guardrail #11 |
| 5 | The heartbeat carries elapsed seconds and which call is in flight. A 22-minute call prints nothing at all today until it returns or dies | owner, 2026-09-14 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Write the ledger row and let an operator read the CSV after the run | The ledger is already written and already carries most of this. The defect is that it reaches a human only after a 200-minute shard has ended | Nothing to build. It costs the entire run as a blind window, which is the state this plan exists to end | owner, 2026-09-14 |
| 2 | Emit per-token progress by streaming the model response | Answers a question nobody asked - the heartbeat's elapsed seconds is what tells you a call is stuck | An SSE parser and a new request path. Priced by row 7's estimate failing | Carmack |

## 7. Row #6 - Every item records the machine that ran it

- **Scope:** each item records the CPU model, CPU utilisation at start, end, maximum and minimum, one-minute load, llama resident and peak memory, the Python process memory and the cgroup peak.
- **Files touched:**
  - `backend/idhazh/measured.py`
  - `backend/idhazh/stages/work.py`
  - `backend/tests/` - the measured test module
- **Acceptance gates:** local - `ruff`, `mypy`, the measured test module driven from a built `/proc`-shaped fixture. CI - full suite.
- **Oracle:** over a built workload the sampler returns `cpu_busy_max >= cpu_busy_pct >= cpu_busy_min` and a peak resident figure that never decreases within one item. It cannot settle absolute accuracy of a reading taken on a runner, because the fixture is not a runner; row 11 produces the first real readings.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every source is a local file read or one localhost request - `/proc/stat`, `/proc/self/status`, `/proc/<server pid>/status`, `/proc/loadavg`, the cgroup peak, and the server's own metrics endpoint. Cost is a few milliseconds against a median 475,890 ms of model time | Carmack |
| 2 | Row 5's heartbeat thread is the sampler for maximum and minimum. A second timer for the same readings is a second thing to start, stop and leak | Carmack |
| 3 | A reading that cannot be taken - a path absent on a developer machine - records empty and never raises. A missing instrument degrades the row, not the run | section 1a, degrade do not fail |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Add `psutil` | Every reading needed here is one `open()` on a documented kernel file | A dependency, its install time and its shipped bytes, for arithmetic that is four lines | Guardrail #8 |
| 2 | Keep the machine readings at shard grain in `state/runtime-counters.csv` | A shard figure cannot attribute a slow item to a noisy neighbour, which is the question the runner lottery raises | Nothing to build. It costs per-item attribution against a 4.2x between-runner spread | Carmack |

## 8. Row #7 - The summary and the picture are timed apart

- **Scope:** the summarize-and-visual-decision call's decode time is split between the summary half and the plan half by the token ratio, and the row says in the data that the split is an estimate.
- **Files touched:**
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/stages/work.py`
  - `backend/tests/` - the calls test module
- **Acceptance gates:** local - `ruff`, `mypy`, the calls test module. CI - full suite.
- **Oracle:** `summary_ms + visual_plan_ms` equals the call's decode time exactly, and their ratio equals `summary_tokens_written : visual_plan_tokens_written`. It cannot settle whether decode rate is genuinely flat across the two halves of one reply; row 11 arm S2 is the check, and a disagreement wider than 10 percent promotes the streaming approach out of hard-scope-out.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A token ratio is the method. `summary` is declared before `visual` and field order is decode order, so the summary is written and closed before the plan is started - the halves do not interleave | `calls.py` `call_two_model` |
| 2 | `visual_plan_ms_is_estimate` is a column, not a doc sentence. A number whose method is recorded somewhere else is a number that gets quoted without it | Guardrail #10 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Stream the reply and timestamp the `visual` key | Exact, and not yet needed - the ratio is free and the decision it feeds is coarse | An SSE parser, a new request path and a second timeout policy. Priced by this row's oracle failing | Carmack |
| 2 | Report only the call total and leave the halves unattributed | The decision this feeds is whether the picture earns its decode, and a total cannot answer it. Run-wide `charts_drafted` was 0 on run `34852763827` | Nothing to build. It costs the ability to price the chart at all | Editor |

## 9. Row #8 - What the model saw, kept for 90 days

- **Scope:** behind `capture_prompts` and `capture_replies`, both prompts and both replies for every item are written to a run artifact with 90-day retention, and every row carries the prompt's SHA-256 and token count unconditionally.
- **Files touched:**
  - `backend/idhazh/stages/work.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/` - the work-stage test module
- **Acceptance gates:** local - `ruff`, `mypy`, the work-stage test module. CI - full suite, plus one dispatch of row 11's workflow confirming the artifact appears.
- **Oracle:** with capture on there is exactly one artifact entry per call per item, and its SHA-256 matches the `prompt_sha256` column on that item's ledger row. It cannot settle whether 90 days is the right window; the artifact budget is the constraint and row 11 measures the bytes.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Prompts go to an artifact, never to the log stream. The repository is public, Actions logs are public, and a prompt carries the full article body | CLAUDE.md section 0a; owner, 2026-09-14 |
| 2 | Retention is 90 days | owner, 2026-09-14 |
| 3 | The SHA-256 and token count are on the ledger row unconditionally, so two prompts can be proved to share a prefix long after the artifact expires | Fowler |
| 4 | The artifact is never committed and is named in no `commit-and-push.sh` call, matching the existing article-text artifact at `digest.yml` line 910 | CLAUDE.md section 0a |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Print prompts to the workflow log | Publishes article text to a public log on every run | Nothing to build. It costs a section 0a breach on every scheduled run | Andre |
| 2 | Log the prompt with the article body replaced by a hash | Defeats the purpose - the question is what the model actually saw, and the article is the part in doubt | Nothing to build. It costs the only view of the input that matters | Andre |

## 10. Row #9 - A cut reply keeps its summary

- **Scope:** `recovered_completion` gains its production caller, so a reply the output budget cuts in the plan half still publishes its summary.
- **Files touched:**
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/dag.py` - the three docstrings that already describe this as live
  - `backend/tests/` - the calls test module
- **Acceptance gates:** local - `ruff`, `mypy`, the calls and work-stage test modules. CI - full suite.
- **Oracle:** a fixture completion with `finish_reason == "length"` and a closed, parseable summary half yields a published item carrying that summary with `visual_state` absent, and a fixture whose summary half is itself unclosed still fails. It cannot settle how often this fires in production; the ledger's `recovered` column answers that from the next run onward.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The function exists, is tested, and has no caller, while three docstrings describe it as live. The defect is the missing call site, not the function | Fowler |
| 2 | The row also corrects `work.py` line 380, where `_summary_half_of` leaves `finish_reason == "length"` on a completion it has repaired | Fowler |
| 3 | `recovered` becomes a ledger column in row 2, so the recovery rate is readable | owner, 2026-09-14 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Delete `recovered_completion` as dead code | Three items on run `34852763827` decoded exactly `CALL_TWO_BUDGET_TOKENS` and lost their summaries; the function is the fix for precisely that | Nothing to delete. It costs every truncated item its summary, which is the half a reader came for | Editor |

## 11. Row #10 - A killed shard keeps the work it finished

- **Scope:** a shard that exceeds its timeout uploads the item payloads it completed, so `assemble` sees them.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/` - the workflow-shape test module
- **Acceptance gates:** local - the workflow-shape test module. CI - full suite, plus one real digest run confirming the committed day count matches the ledger's published count.
- **Oracle:** every step that must survive a cancelled job carries a guard that runs on cancellation, asserted by name against the workflow file, and the count of `outcome=ok,stage=publish` ledger rows for a run equals `items_added` summed across that day's `digest.json` run entries. It cannot settle whether `assemble` composes a partially-uploaded shard correctly in every case; a real run is the check.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is a defect, not a symptom of the slowdown. On run `34852763827` the ledger recorded 46 published items across four shards while the committed day carries 13 - shard 3's count, the only shard that finished. Three shards recorded 33 items as published whose payloads no reader can see | owner, 2026-09-14 |
| 2 | The ledger steps already survive cancellation and the upload steps do not, which is why the census over-reports by 3.5x rather than under-reporting | Fowler |
| 3 | The oracle is a workflow-shape assertion rather than a killed-run rehearsal, because a rehearsal that kills a job cannot run in the test suite | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Have the shard commit payloads directly instead of uploading artifacts | Four shards committing to one branch is the contention the artifact hand-off exists to avoid | A merge strategy for payload files and a retry loop on push. Priced by measuring push contention across four concurrent shards | Carmack |
| 2 | Make the census count only items that reached `assemble` | Records the loss instead of fixing it, and the work is still thrown away | Nothing to build. It costs 33 articles of model time per affected run | Editor |

## 12. Row #11 - Two articles, three arms, one runner

- **Scope:** `.github/workflows/idhazh-pipeline-tests.yaml`, dispatch-only, picks two articles at random from a configured list of at least twenty and runs three arms in sequence on one runner.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `config/pipeline-tests.json`
  - `backend/idhazh/contracts/app_config.py` or a new contract module for the URL list
  - `schemas/pipeline-tests-config.schema.json`
- **Acceptance gates:** local - the contract export, `ruff`, `mypy`, the config test module. CI - full suite, plus one real dispatch.
- **Oracle:** the three arms record the same two `item_id` values, proving the pick happened once. It cannot settle whether two articles are representative of eighty; they are a fast signal, not a sample.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three arms run sequentially on one runner, not as a matrix. The between-runner spread is 4.2x, wider than anything being measured, so a matrix would compare CPUs rather than settings | Carmack, Guardrail #10 |
| 2 | The article pick happens once, before the arms, seeded from the run id and printed. A per-arm pick would compare different articles and answer nothing | Carmack |
| 3 | Arms: `baseline` (both calls, both tasks, `n_parallel 1`), `no_visual_decision` (`plan=False`), `parallel_2` (both tasks, `n_parallel 2`). The third restarts the server because `n_parallel` is a start-time flag | owner, 2026-09-14 |
| 4 | `plan=False` needs no new code. `call_two_model` already builds a summary-only grammar and `dag.py` line 93 hardcodes `plan=True`; the row makes that value come from config | Guardrail #6 |
| 5 | Dispatch-only, no schedule, so the workflow costs nothing when nobody is looking at it | Carmack |
| 6 | The URL list lives in `config/`, schema-validated, and the job reports which addresses failed to fetch so the list can be pruned as links rot | Guardrail #6 |
| 7 | The three dead workflow registrations - `probe-protego.yml`, `probe-host.yml`, `probe-whole-day.yml` - were cleared on 2026-09-14 by deleting the single run each held. The files were already absent from every branch | owner, 2026-09-14 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A matrix of three jobs | Three runners, three CPU draws, and only 17 percent of draws land on the fast part - the arms would differ by hardware more than by setting | Nothing to build, and it is faster. It costs the validity of every comparison it produces | Carmack |
| 2 | Extend `measure.yml` rather than add a workflow | `measure.yml` is 1,427 lines and answers a different question; adding a third arm set to it makes both harder to read | Nothing to build. It costs a clear separation between benchmarking a model and probing the pipeline | Fowler |
| 3 | Run all twenty articles | 20 articles at roughly 8 minutes each across three arms is most of a working day, which is the slow loop this row exists to escape | Runner minutes. The list exists so that repeated dispatches cover it by rotation instead | Carmack |

## 13. What execution surfaced

The plan predicted eleven rows of work and one census error. It did not predict that building the instrument would find five more defects, three of them live in production. That is the finding worth keeping: **an instrument cannot be built without walking the path it measures, and the walk is what finds the holes.**

| # | What surfaced | How it surfaced | Landed |
| --- | --- | --- | --- |
| 1 | An empty headline killed a whole work shard rather than degrading one item. `discover.clean_title` returns `None` for a feed entry with no title, nothing gated it between there and the extractor, and the per-item loop caught nothing. A single headline-less entry from any live feed would have taken down a shard | the test rig's first successful dispatch | #748 |
| 2 | `state/item-health/2026/09/14.csv` carried two headers and two row widths. A scheduled run on a checkout taken before row 2 merged wrote the retired 43-column shape, and `merge=union` stacked both tables silently. It took `main` red and every open pull request with it | the full suite, after the merge | #747 |
| 3 | A mechanical substitution over prose broke 14 sentences where the retired phrase was a verb rather than a name, and missed 7 more where a line wrap had split it | a reviewer reading one diff | #744 |
| 4 | The arm script was committed mode 644 and invoked as a bare command, so the first dispatch died on exit 126. No YAML test, no lint and no shellcheck can see a file mode | the first dispatch | #746 |
| 5 | One broken arm skipped the two after it, so a rig built to report what happened reported nothing | the first dispatch | #746 |

Two measurements the plan asserted were confirmed rather than assumed. Prompt caching was never broken - the summarize-and-plan call reuses 98.2 percent of its prompt, which is 0.8 percent of a run's model time, so the cost is decode and not prefill. And the census over-reported by 3.5x: 46 items recorded as published on 2026-09-14 against 13 in the committed day.

### Two decisions handed back

Both are the owner's under CLAUDE.md section 0. Neither is an agent's to take.

| # | Decision | Why it is not an agent's |
| --- | --- | --- |
| 1 | Three arms over two articles need about 115 minutes; `budget_minutes` and the job bound both say 45. Raising the bound, drawing one article, or dropping an arm each change what a dispatch measures | ESCALATE trigger 5 in section 0 |
| 2 | Whether a story with no headline should publish untitled or be dropped. Every downstream surface already has an untitled fallback, so publishing is reachable in one line. The row shipped the drop because that is what was asked for | Editor rules what runs, CLAUDE.md section 14 |

### One number, for the plan that follows

The first successful arm measured **2,172,743 ms of model time over two articles - about 18 minutes an article**, on a stock `ubuntu-latest`, 2026-09-15, one run, no spread. The production median on 2026-09-14 was 475,890 ms an item. Two articles is a signal and not a sample, and the runner model was not recorded for this arm. The fix plan starts here.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.
