# Qwen3.5-9B Adoption, Model-Ref Centralization and Chart Economics - Plan

**Last Updated**: 2026-08-25

**Level**: 5 (model pick plus persisted contracts). The model pick is pre-cleared
by owner approval on 2026-08-25 (`CLAUDE.md` section 0); the remaining Level-5
surface is the persisted-contract work in rows 3, 5 and 7.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Adopt Qwen3.5-9B-Q4_K_M, retire Qwen3-8B-Q4_K_M, make every measurement attributable to the model that produced it, and settle whether the chart arm earns its runner minutes. |
| Supersedes | [`20260825-qwen35-9b-swap-plan.md`](20260825-qwen35-9b-swap-plan.md). That plan is research material until row 12 deletes it. |
| Hard scope - in | Model-byte verification; single-source model ref; truthful fingerprint identity and ledger rows; reasoning-guard defect; `shard_size` and `--cap` enforcement; route budget cut to 40 minutes; chart-draft counting; console Charts table; machine-gate qualification of the candidate; the value-only adoption commit; cache wipe and rollout verification; living-doc distillation. |
| Hard scope - out | Prompt rewrite; vendor sampling; thinking mode; a lower quantisation; mmproj or vision; replacing the 4B router; raising any runner limit; rewriting historical payloads; a fingerprint-based inference skip; an LLM judge; a pre-registered human selector; per-model quality split on the console. |
| ESCALATE triggers | (1) Any HARD gate in row 10 fails - stop, leave the 8B configured, report the failing metric and its measured value. (2) The measured 9B worst-case shard exceeds 330 minutes after row 7 - stop (Rule #2); the lever is `run.safety_ceiling_per_run`, never `timeout-minutes`. (3) Row 12 rollout finds the served alias and the served bytes disagree. (4) Any row would rewrite a published payload. |
| Chosen strategy | Land identity and capacity first, qualify on machine gates second, swap in one reversible value-only commit third. Ruled by Fowler (commit ordering) and Carmack (capacity), with Andre owning the gate set. |
| Human quality comparison | Owner ruling 2026-08-25: Andre option (c). Ship on machine gates; `evaluation.spot_checks_per_week` is the standing alarm. No blind pairwise session is scheduled, no human selector is built, and row 13 records that no human comparison was made. |
| Shared-file rows | Rows 1, 4, 5, 6 and 7 all touch `backend/idhazh/cli.py`, `config/idhazh.json` or `.github/workflows/digest.yml` in different regions. The orchestrator rebases each branch on the advanced `main` before its merge rather than assuming a clean base. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3. |

## Section 0a - Overlapping plans, resolve before dispatch

Two other plan-docs were authored on 2026-08-25 and were untracked in the working
tree when this plan was written. They contend for the same surfaces. Resolve each
collision before dispatching the affected row; do not dispatch two plans onto one
file.

| This plan | Contends with | Surface | Resolution owed |
| --- | --- | --- | --- |
| Row 5 - centralize the model ref | `20260825-runtime-and-publish-defects-plan.md` row 3, "Pin the llama.cpp build and name it in the cache key" | the `work` cache key in `.github/workflows/digest.yml` | One row owns the cache key. The build pin and the model ref both belong in it. |
| Row 6 - truthful fingerprint inputs | Same plan, deferred item 2, "Stamping the observed llama.cpp build into `runtime_build`" | `runtime_build` at the `build_inputs` call site | Identical change. Collapse into whichever row dispatches first. |
| Row 6 - truthful fingerprint inputs | Same plan, deferred item 1, widening `PipelineInputs` and adding the `require_matching_header` guard | `backend/idhazh/contracts/fingerprint.py` | Both reset every fingerprint. Land them in one commit or the stamp moves twice. |
| Row 7 - enforce `shard_size` | Same plan, row 10, "Raise the shard ceiling from 4 to 8 and measure it" | the shard count in `.github/workflows/digest.yml` | Directly contradictory framings of the same knob. One ruling, from Carmack, before either dispatches. |
| Row 1 - verify the model bytes | Same plan, row 5, "The `work` job names its host, its binary and its weights" | the `work` job identity steps | Overlapping intent. Merge the step lists. |
| Rows 8 and 9 - console sections | `20260825-console-charts-plan.md`, rows 1 and 2 | `frontend/src/routes/console/` and the throughput candle | The coordinate-frame rewrite lands first. New sections build on the new frame, never on the old one. |

Both contending plans cite `20260825-qwen35-9b-swap-plan.md`, which this plan
supersedes. Re-point those citations here when the collisions are resolved.

## Target identity (verified 2026-08-25 against the Hugging Face API)

| Field | Value |
| --- | --- |
| Repository | `unsloth/Qwen3.5-9B-GGUF` |
| Revision | `3885219b6810b007914f3a7950a8d1b469d598a5` |
| File | `Qwen3.5-9B-Q4_K_M.gguf` |
| Model id | `qwen3-5-9b-q4-k-m` |
| Bytes | 5,680,522,464 (`x-linked-size`) |
| SHA-256 | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` (`x-linked-etag`) |
| Licence | Apache-2.0 |
| Vision projector | Not downloaded, not configured |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Fill and verify the model bytes | - | A | PENDING | - | - | - |
| 2 | Reject any non-empty reasoning block | - | A | PENDING | - | - | - |
| 3 | Name the run that wrote a revised item | - | A | PENDING | - | - | - |
| 4 | Cut the route budget and count chart drafts | - | A | PENDING | - | - | - |
| 5 | Centralize the model ref through plan outputs | 1 | B | PENDING | - | - | - |
| 6 | Truthful fingerprint inputs, and a ledger that has rows | 1 | B | PENDING | - | - | - |
| 7 | Enforce `shard_size` and wire `--cap` | 1 | B | PENDING | - | - | - |
| 8 | Console: the Charts table | 4 | C | PENDING | - | - | - |
| 9 | Console: what the model did, in plain words | 8 | D | PENDING | - | - | - |
| 10 | Qualify the candidate on machine gates | 2, 5, 6, 7 | C | PENDING | - | - | - |
| 11 | Adopt the 9B and retire the 8B | 10 | E | PENDING | - | - | - |
| 12 | Wipe the cache and verify the first 9B day | 11 | F | PENDING | - | - | - |
| 13 | Distil into living docs and delete both plans | 9, 12 | G | PENDING | - | - | - |

## Row #1 - Fill and verify the model bytes

- **Scope:** Record the SHA-256 of both configured GGUFs, refuse a null digest at the fingerprint boundary, and make a mismatched download fail before the server starts.
- **Files touched:**
  - `config/idhazh.json` - `models.summarize.sha256`, `models.route.sha256`
  - `backend/idhazh/cli.py` - the `model_sha256=model.sha256 or "0" * 64` coercion
  - `.github/workflows/digest.yml` - a `sha256sum` step between the weight fetch and the server start; an alias assert inside the health check
  - `backend/tests/test_fingerprint.py`, `backend/tests/test_workflows.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; contract drift gate; a unit test proving a null `sha256` raises rather than coerces; a workflow test proving the verify step sits before the server start.
- **Oracle:** With a deliberately wrong `sha256` in config, the `work` job fails at the verify step and never starts `llama-server`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Raise on a null `model_sha256` rather than substitute 64 zeros. A stamp built on a placeholder validates and lies (Rule #10). | Fowler |
  | 2 | The run manifest records the OBSERVED digest of the file on disk, not the declared config value. | Carmack |
  | 3 | The health check asserts `GET /v1/models` returns the config alias and the loaded path ends in the config filename. | Carmack |
  | 4 | `ModelRef.sha256` stays optional in the contract. Five published run manifests carry `null`; requiring it would break reading them (`CLAUDE.md` section 11). | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Make `ModelRef.sha256` required and non-null | Breaking against published payloads; the only migration is rewriting history | Fowler |
  | 2 | Add a `revision` field now | Nothing reads it - `backend/utilities/measure_llm.py` hardcodes `resolve/main`. Speculative generality | Carmack |

## Row #2 - Reject any non-empty reasoning block

- **Scope:** Close the guard bypass where an empty first `<think>` block hides a non-empty second one.
- **Files touched:**
  - `backend/idhazh/summarize.py` - `split_thinking`, which uses `_THINK.search` and inspects only the first match
  - `backend/tests/test_summarize.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; a unit test where the first block is empty, the second carries content, and the reply is rejected.
- **Oracle:** `<think></think><think>reasoning</think>answer` is rejected; `<think></think>answer` still passes.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Scan every block, not the first. The guard asserts the absence of reasoning, so one unchecked block defeats it. | Andre |
  | 2 | This lands before row 9. A candidate must not pass a safety gate that a defect made passable. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Rely on `chat_template_kwargs.enable_thinking: false` alone | A flag is a request; the guard is the control (Rule #11 posture) | Andre |

## Row #3 - Name the run that wrote a revised item

- **Scope:** Add an optional `updated_by_run` to a published item so the model join stays correct after a later run rewrites the text.
- **Files touched:**
  - `backend/idhazh/contracts/digest_day.py` - `DigestItem`, plus a validator pairing the field to `updated_at`
  - `schemas/digest-day.schema.json` - regenerated
  - `frontend/src/contracts/` - regenerated
  - `backend/idhazh/assemble.py`
  - `backend/tests/test_contracts.py`, `backend/tests/test_pipeline.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; contract drift gate byte-identical; a contract test loading a pre-change day payload with the field absent.
- **Oracle:** For every published day, `introduced_by_run` or `updated_by_run` resolves to a `DigestDay.runs[n]` entry whose manifest names the model that wrote the item's current words.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Add the field. The base join already resolves; the revised case returns a confidently wrong run. | Fowler (narrow dissent from Andre, ratified by the owner 2026-08-25) |
  | 2 | Optional with a null default, so every payload written before the change still validates. Additive; `version` bump plus `changelog` entry; no read-side migration. | Fowler |
  | 3 | The summarizer `model_id` does NOT go on `DigestItem`. The run join already carries it and a duplicate can disagree (Rule #4). | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Forbid a mid-day model change by contract | Unenforceable, and fixes the wrong thing - any fingerprint input can move mid-day | Fowler |
  | 2 | Accept the imprecision | Worse than silence: the join returns a wrong answer confidently | Fowler |

## Row #4 - Cut the route budget and count chart drafts

- **Scope:** Reduce the route stage budget by 20% and persist the one count that explains why drafted charts do not become published charts.
- **Files touched:**
  - `config/idhazh.json` - `run.route_budget_minutes` 50 -> 40
  - `.github/workflows/digest.yml` - `route` job `timeout-minutes` 60 -> 50, preserving the measured 10-minute headroom
  - `backend/idhazh/contracts/run_manifest.py` - `charts_drafted`
  - `schemas/run-manifest.schema.json` - regenerated
  - `backend/idhazh/cli.py` - `stage_route`
  - `backend/tests/test_route.py`, `backend/tests/test_contracts.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; contract drift gate; a contract test loading a pre-change manifest with `charts_drafted` absent.
- **Oracle:** For a fixture day, `charts_drafted` minus the count of published charts equals the number of items the post-model checks rejected.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Persist `charts_drafted` on the run manifest. 8 of 17 drafts died after the model on 2026-08-25 and no committed row says so. | Jony |
  | 2 | Do NOT persist `draft_kind`. With `enabled_kinds` at `["chart"]` the model is never offered a diagram, so zero diagram drafts is a config guarantee, not a measurement. Restore the field the day a second kind is enabled. | Jony |
  | 3 | Do NOT split `route_ms` into decide and render. The render is our own deterministic code on roughly 10% of items; the model call is 40.3 s on roughly 53%. Measure the render once, offline, into `docs/reference/measurements.md`. | Jony |
  | 4 | Do NOT add a `route` row to `state/item-health/`. It doubles the ledger for a number that only means anything as a day sum, which the manifest already carries. | Jony |
  | 5 | Pre-registered kill line for the chart arm, recorded before the data is read: over 14 consecutive days with the chart-only gate on, retire the arm if the median day publishes a chart on fewer than 5% of published items, or spends more than 6 router minutes per published chart. Either limb trips it. A day stopped at the budget still counts. Measured 2026-08-25: 6.2% and 4.4 minutes. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep `timeout-minutes` at 60 while the budget drops to 40 | Leaves a 20-minute dead band where a stuck stage burns runner wall-clock past its own bound | Carmack |
  | 2 | Replace the 4B router with the 9B | The 50-minute budget affords 124 items on a fast host and 64 on a slow one (derived from the measured 2.17x ratio) against a 145-item day. At 40 minutes it is worse | Carmack |
  | 3 | Retire the chart arm now | The measured rate sits inside the kill line. Deciding before the 14-day window is arguing the number after seeing one day of it | Jony |

## Row #5 - Centralize the model ref through plan outputs

- **Scope:** Make `config/idhazh.json` the only place a production model ref is written, and delete the workflow copies.
- **Files touched:**
  - `.github/workflows/digest.yml` - a `models` step in the `plan` job writing to `$GITHUB_OUTPUT`; `jobs.plan.outputs`; the `work` and `route` cache keys; deletion of `MODEL_REPO`, `MODEL_FILE`, `ROUTE_REPO`, `ROUTE_FILE`
  - `backend/tests/test_workflows.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; a workflow test asserting no production job reads a model repo or filename from `env`; one dispatched `digest.yml` run reaching a healthy server.
- **Oracle:** Grepping `.github/workflows/digest.yml` for a GGUF filename or a Hugging Face repo returns zero matches; the run still restores the same cache key.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The `plan` job publishes the refs as job outputs. `work` and `route` already `needs: plan`, and the `needs` context resolves before a job's first step - unlike `steps`, which is why the cache key could not read config until now. | Carmack |
  | 2 | The cache key becomes `llm-${{ needs.plan.outputs.summarize_file }}-v2`. | Carmack |
  | 3 | Leave `measure.yml` and `validate.yml` alone. Neither keys a cache on the model ref, and measuring a candidate means naming a model deliberately not in config yet. Read config inline where needed. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep the workflow `env` copies and rely on review | The alias already comes from config while the weights come from `env`. Change one and `llama-server` serves 8B bytes under the 9B alias, and every eval row names a model that never ran | Carmack |
  | 2 | A repository-level variable or secret | Adds a surface outside the repo that a clone cannot read, breaking the sane-default rule (Rule #6) | Carmack |

## Row #6 - Truthful fingerprint inputs, and a ledger that has rows

- **Scope:** Stop the fingerprint digesting placeholders, and write the ledger row that lets a stamp be expanded.
- **Files touched:**
  - `backend/idhazh/cli.py` - `chat_template`, `runtime_build`, `runner_class` at the `build_inputs` call site; an `append_new` call from `stage_work`
  - `backend/idhazh/fingerprint.py`
  - `state/fingerprints.csv` - gains its first rows from a run, not from an edit
  - `backend/tests/test_fingerprint.py`, `backend/tests/test_pipeline.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; contract drift gate; an integration test on a fixture run proving a stamp reaches the ledger exactly once; a test proving a second run with identical inputs appends nothing.
- **Oracle:** Every distinct `pipeline_fingerprint` in `state/scores.csv` written after this row resolves to exactly one row in `state/fingerprints.csv`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `pipeline_fingerprint` is the load-bearing attribution key, not `model_id`. A slug does not move when the prompt, the truncation cap or the runtime build moves, and all three move the score. | Andre |
  | 2 | `chat_template` digests the rendered template, not the model id string. | Andre |
  | 3 | `runtime_build` and `runner_class` come from the environment, not from a literal. | Carmack |
  | 4 | No new lineage contract. `state/fingerprints.csv` already is the lineage record; a second store would restate it and disagree (Rule #4). | Fowler |
  | 5 | No `reason` or `superseded_by` column. Nothing parses a sentence in a CSV, and the machine-readable "why" already lives in `state/validation-<date>.csv`. The prose goes in the living doc. | Fowler |
  | 6 | The three existing stamps in `state/scores.csv` stay unexpandable and are recorded as unknown. Reconstruct what is reconstructible; never guess (Rule #10). | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A new `state/model-eras.csv` | Duplicates `FingerprintRow`, which already carries `first_seen_run`, `first_seen_at` and the model digest (Rule #4) | Fowler |
  | 2 | Backfill the 1032 existing rows with a reconstructed stamp | Manufactures a measurement nobody took (Rule #10) | Andre |
  | 3 | A prose-only record in `docs/reference/measurements.md` | Cannot be joined to a row, cannot be gated, drifts silently | Andre |

## Row #7 - Enforce `shard_size` and wire `--cap`

- **Scope:** Derive the shard count from the planned item count so a full day fits the `work` timeout on the slower candidate, and pass the parsed cap into planning.
- **Files touched:**
  - `backend/idhazh/cli.py` - `stage_plan` receives `--cap`; shard-count derivation
  - `.github/workflows/digest.yml` - the `plan` job's shard computation reads the derived count
  - `config/idhazh.json` - `run.safety_ceiling_per_run` if the arithmetic requires it
  - `backend/tests/test_plan.py`, `backend/tests/test_workflows.py`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; a unit test proving the shard count honours `run.shard_size` and never exceeds `run.max_parallel`; a unit test proving `--cap` reaches `stage_plan`.
- **Oracle:** For a planned day at `run.safety_ceiling_per_run`, the worst-case shard time derived from the measured 9B per-article figures stays under the 330-minute `work` timeout.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Fix the enforcement, not the timeout. A 50-item shard of long articles costs 345 derived minutes on the 9B against a 330-minute bound; the 8B is already at 285. The lever is the ceiling or the shard count (Rule #2). | Carmack |
  | 2 | `--cap` is parsed today and dropped. A validation run can exceed the job budget because of it. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Raise `timeout-minutes` past 330 | The budget is the platform, not a preference (Rule #2) | Carmack |
  | 2 | Leave the 1-through-4 fixed shard input | It is why `run.shard_size: 5` reads as configuration and behaves as decoration | Fowler |

## Row #8 - Console: the Charts table

- **Scope:** One table on the console that answers whether the chart arm earns its runner minutes.
- **Files touched:**
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/tests/` - a browser assertion
  - `docs/architecture/publishing/visuals.md`
- **Acceptance gates:** `svelte-check` 0/0; build; bundle gate; browser suite; the page renders with the route data absent (`CLAUDE.md` section 12 step 5); zero new console `[error]` and zero new `404`.
- **Oracle:** For the canary day, every printed cell equals the value computed directly from that day's committed run manifest.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A table, not a funnel. The stages fall by an order of magnitude (88, 47, 17, 9) and a bar funnel makes the last stage - the one the decision rests on - the hardest to read. | Jony |
  | 2 | Columns: Day, Reached, Asked the model, Charts drafted, Charts published, Router minutes, Minutes per chart. Two gaps carry the story: Reached-to-Asked is the pre-model gate, Drafted-to-Published is the post-model checks. | Jony |
  | 3 | Its own heading, "Charts". Not bolted onto "Runs", where site size and chart economics dilute each other. | Jony |
  | 4 | Degraded rendering: a day whose route job never ran prints 0 reached and `-` for minutes, never 0 minutes. Zero charts prints `-` for minutes per chart, never infinity and never 0. | Jony |
  | 5 | The percentage is not stored. Two committed counts divided is the percentage. | Jony |
  | 6 | Nothing about chart economics reaches the reader-facing digest page. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Five separate numbers as the owner first framed them | Four counts plus one derived ratio answer the same question with less screen. Render time moves to an offline measurement (row 4, decision 3) | Jony |
  | 2 | A model swap mark on the console charts now | The ledger must tell the truth before a chart draws it. Deferred to row 13's re-read | Andre |
  | 3 | A model filter or legend on the console | A filter over two values hides data and saves nobody any work | Jony |

## Row #9 - Console: what the model did, in plain words

- **Scope:** Report what the summarizer actually did on the day's own articles, under one heading, with every metric named so a non-technical person understands it.
- **Files touched:**
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/tests/` - a browser assertion
  - `docs/architecture/publishing/telemetry-series.md`
  - `docs/concepts/design-system.md` - the label set, so the wording is settled once
- **The columns.** Labels ruled by Reader, placement ruled by Jony. Every figure is the day's own articles.

  | Label on screen | Line under it | Printed as | Source |
  | --- | --- | --- | --- |
  | Summaries today | - | count | `state/scores.csv` rows for the day |
  | Marked "not sure" | How many of today's summaries we told you not to trust. | count out of the day | `band` |
  | Numbers not in the article | The summary had a figure. The article did not. | count out of the day | `unsupported_numbers` |
  | "Maybe" told as fact | The article said it might have happened. The summary said it did. | count out of the day | `hedge_dropped` |
  | Article read only in part | The article was too long, so the machine read the start and stopped. | count out of the day | `truncation_flagged` |
  | Copied, not rewritten | How much of a normal summary is lifted word for word. | whole percent, median item | `extractiveness`, `verbatim_run` |
  | Time to write one | How long the machine takes on one article. | whole seconds, median item | `summarize_ms` |
  | Model minutes | - | whole minutes | `summarize_ms` summed |
  | Failed | - | count | `state/item-health/` outcome |

- **Acceptance gates:** `svelte-check` 0/0; build; bundle gate; browser suite; the page renders with the score data absent (`CLAUDE.md` section 12 step 5); zero new console `[error]` and zero new `404`; a browser assertion that no 0-to-1 value and no internal column name appears under the heading.
- **Oracle:** For the canary day, every printed cell equals the value computed directly from that day's committed `state/scores.csv` and `state/item-health/` rows, and no cell prints a decimal.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One heading, `What the model did`, placed above the existing throughput candle. The score table moves under it. No fourth console section is added. | Jony |
  | 2 | Every number is a count of today's items, not a score. No 0-to-1 value reaches the screen. No decimals. | Reader |
  | 3 | `hhem` never prints. It cannot be said plainly, and a number a person cannot act on does not earn a column. It keeps deciding the "not sure" flag. | Reader |
  | 4 | Quality is a table, never a line. A line invites a trend that is not there. | Jony |
  | 5 | The `Summaries today` column is mandatory beside every quality column. A mean over four articles is not a measurement. | Jony |
  | 6 | One line under the heading, in the reader's words: the articles change every day, so a dip can be the news, and every figure was measured the day it ran. | Reader, Jony |
  | 7 | Static benchmark figures never appear on the console. They stay in `docs/reference/measurements.md`, reached by a link. | Jony |
  | 8 | The throughput candle stays, unmoved, first inside the section. It is the only thing on the page that draws a spread, and the swap mark lands there and nowhere else. | Jony |
  | 9 | A swap is one divider row in the table carrying the date and the new model id. No arrow, no delta, no claim of cause. Percent-shift text is suppressed across the boundary. | Jony |
  | 10 | Degraded states: no summaries prints no row and a gap in the candle, never a zero; the scorer off prints `-` in quality cells while speed cells still print, never `0.000`; a one-item day prints one tick and no box. | Jony |
  | 11 | `Copied, not rewritten` is kept over Jony's drop list. Reader ruled it answers a question a person can act on rather than exposing the scorer's working. | Reader, over Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | One overall score, such as "92 percent accurate" | Unfalsifiable to a reader, invites trust they cannot check, and worth nothing the day they catch one wrong summary. Six honest counts survive that; one grade does not | Reader |
  | 2 | A static-versus-production comparison, a dashed bench line on the candle, or an expected-against-actual column | Two machines and two workloads; any gap reads as a regression nobody measured | Jony |
  | 3 | Separate reading-time and writing-time columns (`prefill_ms`, `decode_ms`) | For the person tuning the machine, not the person judging it. The candle already carries it | Reader |
  | 4 | Length metrics on screen (`coverage`, `compression`, word counts) | The reader can see the length; it is on the page | Reader |
  | 5 | `hhem_full`, `hhem_delta`, `evidential_density`, `speculative_density`, `scorer_version`, `score_ms` | Scores about the scorer, not about the digest | Reader, Jony |
  | 6 | A `determinism_violation` column | A build alarm. When it fires it moves the "not sure" count, which is where a reader would look | Reader |

## Row #10 - Qualify the candidate on machine gates

- **Scope:** Run the registered machine gate set against Qwen3.5-9B-Q4_K_M on a deterministic paired corpus, and commit the evidence.
- **Files touched:**
  - `.github/workflows/validate.yml` - capture once and replay both models against identical input hashes; preserve failures in the denominator; pin the scorer
  - `backend/idhazh/contracts/validation_row.py` - `not_reported` leaderboard provenance
  - `state/validation-<date>.csv` - the committed result
  - `tests/fixtures/` - the paired corpus and the live canaries
  - `docs/reference/measurements.md`
- **Acceptance gates:** every HARD gate below passes; `ruff`; `mypy --strict`; full backend suite; contract drift gate.
- **HARD gates (block the merge):**

  | Gate | Threshold | Source |
  | --- | --- | --- |
  | Reasoning leakage | zero non-empty `reasoning_content`; zero non-empty `<think>` block, with row 2 landed | Andre |
  | Schema validity | `finish_reason = stop`, schema-valid JSON, no repair path, 100% of attempts | Andre |
  | Injection canaries | every `must_not_survive` marker absent and every `must_survive` fact present, on live candidate calls | Andre, Rule #11 |
  | Determinism | `determinism_violation = 0` over three repeats; identical `output_digest` | Andre |
  | Publishable length | every `summary_word_count` inside [`summary_words_min`, `summary_words_max`] | Andre |
  | Paired denominator | at least 20 common successful pairs on identical input hashes; full attempted denominator recorded | Andre |
  | Unsupported numbers | paired total must not exceed the incumbent. Tolerance zero | Andre |
  | Hedges and lead coverage | `hedge_dropped` and the share below `lead_coverage_min` do not rise above the incumbent's paired value | Andre |
  | Copying | `extractiveness` and `verbatim_run` must not rise while `hhem` holds flat or up | Andre |
  | Faithfulness floor | mean `hhem` not below the incumbent by more than `validation_drop_max` | Andre |
  | Context fit | complete chat-templated request plus `max_output_tokens` fits `n_ctx`; `fits_context` over-reserves | Carmack |
  | Identity | GGUF SHA-256 equals the target digest at the pinned revision | Carmack |
  | Budget | every qualification and production job inside 330 minutes with measured worst-case margin | Carmack, Rule #2 |

- **DIAGNOSTIC (recorded, does not block):** `compression`, `hhem_delta`, `evidential_density`, `speculative_density`, generated-title fallback rate, band adherence, decode throughput.
- **Oracle:** Both models score the identical list of input hashes, and one candidate failure remains in the denominator rather than vanishing from it.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `validation_switch_margin` decides nothing. HHEM is the alarm, not the selector. | Andre |
  | 2 | No LLM judge, at any point (`CLAUDE.md` section 0a). | Andre |
  | 3 | Controls held fixed across the comparison: prompt, output schema, `temperature: 0.0`, `top_p: 1.0`, `seed: 0`, thinking off, truncation cap 2500, `n_ctx` 8192, `n_batch`/`n_ubatch` 512, `n_threads` 4, Q4_K_M, no vision projector. | Andre |
  | 4 | The candidate is never made to pass by moving a threshold, enabling thinking, adopting vendor sampling, taking a lower quant, or raising a timeout. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A pre-registered blind human selector with a pass threshold and tie handling | Owner approval already selected the model. A human session records a comparison; it does not choose | Andre |
  | 2 | Refetch each URL per model | Two models would score different bytes and the comparison would measure the web | Andre |
  | 3 | `leaderboard_hhem` as a required float | The candidate has no reported value. Missing provenance stays `not_reported`, never zero | Fowler |

## Row #11 - Adopt the 9B and retire the 8B

- **Scope:** One value-only commit switching `models.summarize` to the candidate.
- **Files touched:**
  - `config/idhazh.json` - `models.summarize` `{repo, file, id, quantisation, sha256}`
- **Acceptance gates:** `ruff`; `mypy --strict`; full backend suite; contract drift gate; config schema validation; no schema version bump (no shape changed).
- **Oracle:** `git show --stat` on the commit lists exactly one file, and the diff contains no key additions or removals - only values.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One file, values only. Rollback is reverting this commit. Row 5 is what makes that true. | Fowler |
  | 2 | The 8B is removed from configuration, not from history. Days it produced stay attributed to it and are never rewritten. | Andre |
  | 3 | The swap lands between days, never mid-day. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Bundle the swap with the docs update | A rollback would then revert prose as well as the value | Fowler |
  | 2 | Keep the 8B configured as a fallback | Two configured summarizers means two cache fills and an ambiguous manifest | Carmack |

## Row #12 - Wipe the cache and verify the first 9B day

- **Scope:** Remove the incumbent cache, fill the candidate once, and prove the first published day is attributable end to end.
- **Files touched:**
  - `docs/reference/measurements.md` - the observed cold-fill time and the first-day figures
  - `docs/reference/github-actions.md` - the cache transition procedure
- **Acceptance gates:** one scheduled or dispatched `digest.yml` run completes; `work` and `route` inside their timeouts; the published day renders; browser smoke per `CLAUDE.md` section 12.
- **Oracle:** For the first 9B day, the served alias, the served bytes, the manifest `model_ref`, the `state/scores.csv` `model_id` and the `state/fingerprints.csv` row all name Qwen3.5-9B-Q4_K_M, and the ledger row expands the stamp those score rows carry.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Wipe rather than hold both. Owner ruling 2026-08-25. The transition would otherwise need 13,205,586,208 bytes against a 10 GB cache cap (Rule #2). | Owner, Carmack |
  | 2 | Rollback cost after the wipe is one config revert plus one cold fill, measured at 180 s for 4.7 GB, on a 164-184 minute critical path. | Carmack |
  | 3 | Record the observed cold-fill seconds with hardware and date (Rule #10). | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Hold both weights through the transition | Exceeds the 10 GB cache cap | Carmack |
  | 2 | A bounded re-summarize of recent days on the new model | Rewrites payloads an earlier run wrote, and destroys the incumbent's own record | Andre |

## Row #13 - Distil into living docs and delete both plans

- **Scope:** Move every landed fact into the doc that owns it, record what the adoption did and did not prove, and remove the plan-docs.
- **Files touched:**
  - `docs/concepts/evaluation.md` - the adoption claim below
  - `docs/reference/measurements.md` - candidate promoted from "measured, not adopted" to the configured model; the 8B rows retained as the incumbent record
  - `docs/architecture/overview.md`, `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/throughput.md`
  - `docs/how-to/run-the-pipeline.md`, `docs/how-to/test-models-locally.md`, `docs/how-to/troubleshoot-one-url.md`, `docs/how-to/evaluate-new-summarizer-model.md`
  - `docs/reference/github-actions.md`
  - `docs/architecture/contracts/determinism.md` - the fingerprint now carries observed identity
  - `docs/architecture/publishing/visuals.md` - the kill line and the 14-day window
  - `TODO/20260825-qwen35-9b-swap-plan.md` - deleted
  - `TODO/20260825-qwen35-9b-adoption-plan.md` - deleted
- **Acceptance gates:** every doc carries `Last Updated` and "See also"; ASCII only; no doc names the 8B as the configured model; every measurement carries hardware, date and spread (Rule #10).
- **Oracle:** Grepping `docs/` for `Qwen3-8B` returns only rows explicitly labelled as the retired incumbent's historical record.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `docs/concepts/evaluation.md` carries this claim verbatim: Qwen3.5-9B-Q4_K_M was adopted on 2026-08-25 by owner approval (`CLAUDE.md` section 0) and machine gates only. No blind pairwise human comparison was made. Nothing here shows its summaries are better or worse than Qwen3-8B-Q4_K_M's. The evidence is that it did not fail the registered safety, schema, canary and counterweight gates on 20 paired items. | Andre |
  | 2 | The post-swap alarm: the share of `state/scores.csv` rows with `unsupported_numbers > 0`, segmented by `model_id` at one fixed `scorer_version`, over a rolling 14 run-days against the last 14 8B days. Trips when the rate doubles or rises 5 points absolute. Second limb: mean `extractiveness` up 0.10 or more while mean `hhem` is flat or up. Both are arithmetic on committed rows; no model runs. | Andre |
  | 3 | Re-read `docs/architecture/summarize/throughput.md` on the swap mark. Its own condition - build it with the first swap - now has a second model id to fire on. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep the superseded swap plan as an archive | Two plans that disagree is the failure Rule #4 forbids; git history is the record | Fowler |
  | 2 | Record the adoption in an ADR | There is no ADR file and no `decisions/` directory (`CLAUDE.md` section 5) | Fowler |

## See also

- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [`../docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - the generic adoption procedure.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - every candidate and runner figure cited above.
- [`../docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the selector and alarm boundaries.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - fingerprint identity.
- [`../docs/architecture/publishing/visuals.md`](../docs/architecture/publishing/visuals.md) - the chart arm and its kill line.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the gate commands every row runs.
