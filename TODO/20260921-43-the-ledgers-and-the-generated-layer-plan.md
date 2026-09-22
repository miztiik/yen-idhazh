# The ledgers, the evaluations, and the generated layer

**Last Updated**: 2026-09-22

**Level**: 5. Row 5 deletes the generated contract layer whole and row 6 amends the engineering contract that requires it. Row 3 mints a persisted contract. Those three PAUSE for the owner before their pull request opens. Rows 1, 2, 4 and 7 are Level 2 or 3 and run AUTO once the user authorizes.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight - four, because section 1c's readiness table shows four disjoint file sets at the widest point; refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 39 split into lanes; plans 41 and 42 took the model file and the workflows, and this is the rest. Three of its remaining rows were wrong as written - one cuts the work a budget gate measures without moving the gate, one deletes 990 lines of search evaluation to fix two lines in a test, and one writes a day directory into a tree whose three readers all expect a day file. Two more overturn rulings a person already made and wrote down. What survives is corrected here, with the file lists and the field-level shapes the original rows were missing. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| The second rule | **An instrument is not scaffolding.** A thing that measures what nothing else measures stays, however large and however few gates read it. The test is what goes blind when it leaves, and each row answers it. |
| The measure | **Edits per future change, and reviewer attention per commit.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Take the replay count off the dispatch surface and leave the loop three gates draw from. Delete the ten utilities the census finds unreferenced and the human-label path, and bound the search evaluation's one growing read instead of deleting the evaluation. Give the pipeline test a committed day ledger carrying every case, its summary and the bytes the model read, discoverable by the nightly prune. Make nine console specs visit all five routes the site serves. Delete the generated contract layer whole, inlining five names by hand and binding each closed vocabulary with one test. Amend the three engineering-contract clauses plan 41 does not own. Correct one dependency's beneficiary line. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 39 rows 1, 7, 8, 12, 17 and 19. **Plan 39 row 15 is refused outright** - see the scope-out table. |
| Assumes | **Plan 41 merges before row 6 starts** - plan 41 row 6 rewrites Guardrail #3 and section 11, and row 6 must amend the text plan 41 leaves, not the text on main today. Rows 1, 2 and 4 assume nothing. |
| ESCALATE triggers | (1) Row 1 must not change what the BUDGET gate measures. If the work a qualification shard does per dispatch changes at all, stop. (2) Row 3 mints a persisted contract and a committed collection. If the nightly prune cannot discover the tree by the marker in C4, stop. (3) Row 5 deletes the artefacts a drift gate protects. If the five inlined names cannot be proved identical to the generated ones before the deletion, stop. (4) Row 5 turns two closed vocabularies from generated into hand-written. Each ships its binding test in the same commit or the row stops. (5) Row 6 amends the engineering contract; it lands in the same pull request as row 5, never after. (6) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Four pull requests, three of which run at once because their file sets are disjoint. Fowler rules the contracts, the test tiers and the module structure; Andre the evaluation integrity; Carmack the ledger shape and the prune path. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Cutting qualification to one pass per article** (plan 39 row 7's scope) | About 180 lines stay, and a dispatch keeps costing what it costs | **Refused as written; a gate nobody checked is the reason.** `elapsed_seconds` is stamped before the repeat loop (`backend/idhazh/stages/qualify.py:554`), so it spans all three passes, and `BUDGET` divides it by 60 against a fixed `job_budget_minutes` (`backend/idhazh/evals/qualify.py:467-483`). Three passes to one drops the measured side about two thirds while the bound does not move: a candidate roughly 2.9x slower per item passes the only gate reading Guardrail #2, and every past BUDGET verdict stops comparing with every future one. Three more gates - `REASONING_LEAKAGE`, `SCHEMA_VALIDITY`, `PUBLISHABLE_LENGTH` - read properties of the sampled output at `temperature: 0.2`, so 90 draws become 30 and detection of a one-in-fifty schema failure falls from about 84 percent to about 45. **What brings it in:** one commit that moves `job_budget_minutes` to the one-pass equivalent, records in `docs/concepts/evaluation.md` that the margin no longer compares across the change, and accepts losing `wording_spread` and a movable `determinism_violation`. That is a measurement decision and it is the owner's. Andre and Carmack, independently |
| **Deleting `backend/idhazh/evals/retrieval.py`** (plan 39 row 17 decisions 3 and 6) | 990 lines stay | **The premise is wrong twice.** The growing walk is `backend/tests/test_retrieval_eval.py:250`, a session fixture; every other test in that file already builds a bounded corpus. And the replacement plan 39 promised is already committed at `tests/fixtures/search/retrieval-queries.json`, 42,052 bytes, at least 50 queries with two gold answers each. Deleting the module leaves `frontend/tests/search.spec.ts:122`, a five-query wiring check whose own file computes its standard error at 0.18 against 0.057 at fifty - a ten-point recall drop is invisible to it. Row 2 bounds the fixture instead. Andre |
| **Reading the console route list from the site's own source** (plan 39 row 19 decision 2) | Adding a console route stays nine test edits | **Refused as written; the defect it found is kept.** `frontend/src/lib/console/band.ts:131-133` records the ruling in the code: "`console-nav.spec.ts` types them out a third time on purpose - that copy is what the owner chose and reading it from here would only prove the page agrees with itself." **What brings it in:** the owner relaxing that ruling for the eight specs that do not test the strip - a smaller question than plan 39 asked |
| **Deleting the five demoted qualification diagnostics** (plan 39 row 17 decision 4) | Seven diagnostic lines stay on the report | **Refused.** Plan 39 never named the five, so the clause cannot be reviewed against anything. Four candidates each witness a failure no gate catches: `unsupported_numbers` is the only witness to a fabricated figure, the one summary error a reader acts on; `hedge_dropped` the only witness to "reportedly" becoming assertion; `extractiveness_mean_non_brief` the only counterweight to the faithfulness floor on the long path, because `BRIEF_COPYING_CEILING` gates brief items only; `below_lead_coverage_min_share` the only witness to a model summarising paragraph fourteen. `evals/qualify.py:666` states the purpose: "a number with no bar is still the thing a human reads when a gate passes and the output still looks wrong." Andre |
| **Teaching `day_partition.day_files` to accept a `.jsonl` day** | A trial tree may not commit traces, so row 3 commits the CSV ledgers only | `backend/idhazh/day_partition.py:96` refuses anything that is not a two-digit `.csv` day file, and `retention.prune_trial_state:1478` walks through it. Committing `state/<trial>/traces/YYYY/MM/DD-N-S.jsonl` would raise `ValueError` inside the nightly prune step. A real latent defect that predates this plan, and one row in its own right. Row 3 routes around it rather than arming it. Carmack |
| **Splitting the two largest console specs** | `console-machine-data.spec.ts` at 58,345 bytes and `console-machine.spec.ts` at 43,215 bytes keep answering several questions each | A different question - one file answering many - and its own structural pull request. One addition buys one cut. Fowler |

### What a change costs today

Measured on `origin/main`, 2026-09-22, except where a line says estimate.

| Reading | Value | Where |
| --- | --- | --- |
| Generated JSON schema | **66 files, 24,697 lines** | `schemas/` |
| Generated TypeScript | **66 files, 9,652 lines** | `frontend/src/contracts/` |
| Import statements in the whole site reaching any of it | **3, in 2 files, pulling 5 names** | `frontend/src/lib/server/config.ts:24`, `host-fingerprint.ts:33-38` |
| Of those five, how many are runtime values rather than types | **2** - `SERVER_JOB` (6 values) and `WATCHED_FLAG` (12 values) are arrays a filter reads | `host-fingerprint.ts:75`, `:162` |
| Generated TypeScript files with no importer | **62 of 66** | derived |
| Commits on `HEAD` that rewrote a generated file | **370 of 2,280 - about one in six** | 344 on `schemas/`, 26 on `frontend/src/contracts/` |
| What the drift gate costs on the runner | **1 s, four runs, zero spread** - under 1.5 percent of the job step it sits in | runs 35660527882, 35658298924, 35657840521, 35657514579 |
| What the generated layer costs the published site | **zero bytes** - Vite tree-shakes all 66 out; the built site is 70,005,963 B against a 1 GB ceiling | committed `frontend/build/` |
| Bytes the layer adds to the repository | 1,592,293 - **1.1 percent** of a 137.46 MiB pack | measured |
| Files reading the generated directories by **path** rather than by import | **8 frontend specs, 4 tooling lines, 6 backend modules** - plan 39 row 1 named none | section 6 |
| Of those eight specs, how many read at **module scope**, so one missing file takes the file down | **3** | `console-machine-panels.spec.ts:28`, `console-model-instruments.spec.ts:45`, `console-model-reasons.spec.ts:39` |
| Utilities with **no textual reference anywhere** outside `backend/utilities/` | **3 of 66**, 638 lines | section 3 |
| Utilities referenced **only by a `docs/` page** | **7**, 1,761 lines | section 3 |
| Utilities plan 39 row 17 claimed had no code reference | **11** - the census says 3 | census 2026-09-21 |
| `backend/utilities/plan_status.py` | **1,204 lines, and nothing calls it.** The CI job that ran it was deleted on 2026-09-22 (owner ruling) because a page generated from every plan at once conflicted on every open branch | it stays on disk as an operator surface |
| Console routes the site serves | **5** | five `+page.server.ts` under `frontend/src/routes/console/` |
| Console specs hand-writing a route list | **9 of 62**, listing 3, 3, 3, 4, 4 and 5 | section 5 |
| Console routes visited by **none** of those nine | **1** - `/console/judgement/` | `git grep -oh "'/console/[a-z-]*/'"` |
| Articles one pipeline-test dispatch summarises | **2, across 3 cases**, one plan, one date, the same two item ids | `config/pipeline-tests.json:2`; `.github/workflows/idhazh-pipeline-tests.yaml:300`, `:311`, `:370` |
| What a commit step costs that workflow | **about 3 s against a 140-minute bound - 0.04 percent** | neighbours in run 35625832336: small payload 2 s, whole digest day 16 s; estimate |
| Articles that moved under their own address inside one job | **2 of 5, on both of two dispatches** | `docs/how-to/evaluate-new-summarizer-model.md:551` |
| What `_prune_trial_shards` prunes today | **nothing, ever** - it returns at `backend/idhazh/stages/prune_state.py:394` because the nightly config sets `trial_state_dirname` to `null` | `config/idhazh.json:305` |

## Section 0b - What this plan does, in one list

1. Take the replay count off the dispatch surface. It becomes a config value; the loop is untouched.
2. Delete the ten unreferenced utilities and the human-label path, keeping its sampling design, and bound the search evaluation's one growing read.
3. Give the pipeline test a committed day ledger: one row per case per article, carrying the summary and the bytes the model read, discoverable by the nightly prune.
4. Make all nine multi-route console specs visit all five routes the site serves.
5. Delete the generated contract layer whole, inlining five names and binding two vocabularies.
6. Amend the three engineering-contract clauses plan 41 does not own, and the three phrases in the agent pointer.
7. Delete the hosted span sink, its optional dependency and its two callers, keeping the committed local trace file.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The replay count leaves the dispatch surface | - | A | PENDING | - | - | - |
| 2 | The unreferenced utilities go, and the search evaluation is bounded | - | B | PENDING | - | - | - |
| 3 | The pipeline test commits what it produced | 1 | A | PENDING | - | - | - |
| 4 | Nine console specs visit every route the site serves | - | C | DONE | p43r4 | - | R4 |
| 5 | The generated contract layer goes | 1, 2, 3, 4 | D | PENDING | - | - | - |
| 6 | The engineering contract and the pages catch up | 5 | D | PENDING | - | - | - |
| 7 | The hosted span sink goes | - | E | PENDING | - | - | - |

**Row 4 delivered five of the nine lists, and the other four were already whole.** Its oracle - every route visited by every spec that claims all of them - is not reached, and the reason is a defect the widening found. `/console/judgement/` and `/console/voices/` each draw charts, and neither draws one that prints a readout strip, so `console-chrome.spec.ts` and `console-readout.spec.ts` count zero on those routes and fail on the route rather than on a chart. Both files name the two routes they leave out and say what the reader loses: on those pages a value is reachable by hover and by nothing else, which a thumb cannot do. **Giving `MergedStoriesPanel` and the voices panels a readout strip is unclaimed work** - it belongs to whoever takes the next design row, and until it lands the rule those two files exist to enforce does not cover two of the five pages a reader can open.

### Section 1a - The five pull requests and the files each owns

**Two pull requests never own one file.** That is what lets three run at once.

| PR | Rows | Kind | Files it owns, exclusively |
| --- | --- | --- | --- |
| **P1 - the qualification surface and the new ledger** | 1, 3 | behavioural | `backend/idhazh/contracts/knobs/run.py`, `knobs/retention.py`, `contracts/pipeline_test_summary.py` (new), `contracts/export.py` (one entry), `backend/idhazh/cli.py`, `ledger.py`, `retention.py`, `stages/record.py`, `stages/prune_state.py`, `config/idhazh.json`, `.github/workflows/validate.yml`, `.github/workflows/idhazh-pipeline-tests.yaml`, `schemas/pipeline-test-summary.schema.json` (new), `frontend/src/contracts/pipeline-test-summary.ts` (new), `tests/fixtures/contracts/pipeline-test-summary/`, `backend/tests/test_ledger.py`, `backend/tests/retention/`, `backend/tests/workflows/test_bench_input_drift.py`, `test_staged_paths.py`, `test_validation_state_root.py`, `docs/how-to/evaluate-new-summarizer-model.md`, `docs/reference/repository-layout.md` |
| **P2 - the deletions and the fixture bound** | 2 | structural | the ten utilities in section 3, `backend/utilities/label_queue.py`, `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/tests/test_retrieval_eval.py`, `backend/tests/test_evidence.py`, `tests/fixtures/search/`, `docs/concepts/evaluation.md`, and the six doc pages in section 3 |
| **P3 - the console coverage hole** | 4 | behavioural | `frontend/tests/console-axis.spec.ts`, `console-chrome.spec.ts`, `console-model-rule.spec.ts`, `console-nav.spec.ts`, `console-polarity.spec.ts`, `console-readout.spec.ts`, `console-title.spec.ts`, `console-voices.spec.ts`, `console-window-claims.spec.ts` |
| **P4 - the hosted span sink** | 7 | behavioural | `backend/idhazh/telemetry/sinks.py`, `telemetry/__init__.py`, `contracts/knobs/observability.py`, `backend/idhazh/stages/work.py`, `backend/utilities/probe_feeds.py`, `backend/tests/test_spans.py`, `backend/tests/contracts/test_telemetry_surface.py`, `pyproject.toml`, `docs/concepts/telemetry.md`, `docs/how-to/run-the-gates.md` |
| **P5 - the generated layer and the contract** | 5, 6 | two commits: inline-and-bind, then delete-and-amend | `schemas/` (all), `frontend/src/contracts/` (all), `backend/idhazh/contracts/export.py`, `typescript.py`, `base.py`, `__init__.py`, the nine backend contract tests in section 6, `backend/tests/conftest.py`, the eight frontend specs in section 6, `frontend/scripts/run-checks.ts`, `test-scope.ts`, `tests/test-scope.test.mjs`, `copy-visuals.mjs`, `frontend/src/lib/server/config.ts`, `host-fingerprint.ts`, `pyproject.toml`, `.github/workflows/ci.yml`, `CLAUDE.md`, `AGENTS.md`, `docs/architecture/contracts/schemas.md`, `docs/reference/ci-model-runtime.md`, `docs/architecture/contracts/determinism.md`, `docs/how-to/run-the-gates.md` |

**`pyproject.toml` and `docs/how-to/run-the-gates.md` appear in P4 and P5.** P4 removes the `langfuse` extra at `:164-166` and its mypy override; P5 removes the `idhazh-export-schemas` script at `:170`. Those hunks are four lines apart, inside git's default context, so **P4 merges first and P5 rebases.** P5 runs last regardless, so this costs nothing.

**`backend/idhazh/contracts/export.py` appears in P1 and P4.** P1 adds one entry to `CONTRACTS`; P4 moves the whole list to `contracts/__init__.py` and deletes the rest of the module. P4 depends on P1 for exactly this reason, so they are never in flight together.

### Section 1b - Why the pull requests fall where they do

| Question | Answer |
| --- | --- |
| Why rows 1 and 3 share a pull request | Both edit `backend/idhazh/cli.py` and `config/idhazh.json`. Splitting them puts two branches on one file for no gain |
| Why row 2 is its own pull request | It shares no file with rows 1 or 3 once `docs/concepts/evaluation.md` is assigned to it alone, and it is **pure deletion** where P1 is behavioural. Mixing structural and behavioural change in one review is what hides a behaviour change inside a diff of removals |
| Why row 4 is its own pull request | Nine frontend specs, disjoint from everything. It can land the day the user authorizes |
| Why row 7 is its own pull request | The telemetry package is disjoint from every other row, so it runs in wave one. It shares only `pyproject.toml` with P5, which runs last anyway |
| Why P5 runs last and alone | Row 5 deletes a generated twin of every contract P1 edits, and waits on plans 41 and 42 for the same reason |
| Why rows 5 and 6 share a pull request | CLAUDE.md section 0 requires a conflicting rule to be amended in the change that conflicts |

### Section 1c - Readiness, computed rather than read off a letter

**A row is ready when every `Depends-on` is DONE and its `Files touched` list shares no entry with a row in flight.** The owner diffs those lists before each dispatch.

| At this point | Ready together | Held, and why |
| --- | --- | --- |
| Start | **1, 2, 4, 7** - four disjoint file sets | 3 waits on 1 (`cli.py`, `config/idhazh.json`). 5 waits on all of them |
| Row 1 returns | **3** refills the slot | 5 still waits |
| Rows 2, 3, 4, 7 returned and merged, plans 41 and 42 merged | **5**, alone | 6 is a commit inside P5, not a separate dispatch |

**Peak workers: 4.**

**No row here measures anything**, so the run-alone rule that applies to a benchmarking row applies to none of them.

## Section 1d - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.** Every existing idiom named here is cited in the tree so the new code copies it rather than inventing a second spelling.

### C1 - The replay knob (row 1)

| Property | Value |
| --- | --- |
| New field | `qualification_repeats: int` on `RunConfig`, `backend/idhazh/contracts/knobs/run.py` |
| Declaration | `Field(default=3, ge=1, description=...)`. The description says what a pass is for - three gates read properties of the sampled output, so passes are draws - and that `wording_spread` reads them |
| Placement | Beside `trial_state_dirname` (`run.py:120`), the nearest knob of the same kind |
| Config | `config/idhazh.json` `run` block (`:296-306`) gains `"qualification_repeats": 3`. Keys in that block are alphabetical; it sorts first |
| Deleted | `.github/workflows/validate.yml:48-49` (the `repeats` dispatch input), `:186` (`REPEATS:` env), `:190-193` (the `^[1-9][0-9]{0,3}$` range check) |
| `backend/idhazh/cli.py:369` | `--repeats` stays. Its `default=3` literal becomes the config value, read the way every other config-backed default in that file is read |
| Unchanged | The loop at `stages/qualify.py:493`, its outside-in order and comment, the `if repeat == 1` filter at `:528`, `wording_spread`, `determinism_violation`, the ten gates, and what `elapsed_seconds` measures |
| Persisted shapes | **None change.** `ItemObservation.repeat`, `QualificationShard.repeats` and `QualificationReport.repeats` all stay, so `tests/fixtures/contracts/qualification-shard/one-shard.json` and `qualification-report/qualified.json` still load and there is no read-side migration |

### C2 - The pipeline-test summary row (row 3)

**A new `CsvContract`.** File: `backend/idhazh/contracts/pipeline_test_summary.py`. Copy the idiom from `backend/idhazh/contracts/item_health.py`.

| Property | Value |
| --- | --- |
| Class | `PipelineTestSummaryRow(CsvContract)` |
| `__schema_stem__` | `"pipeline-test-summary"` |
| `__changelog__` | one entry, `version="2026-09-22"`, stating the initial shape. The base class refuses a subclass without one (`backend/tests/contracts/test_judge_call.py:49`) |
| Registered | **Yes** - added to `CONTRACTS` in `backend/idhazh/contracts/export.py`, so `schemas/pipeline-test-summary.schema.json` and `frontend/src/contracts/pipeline-test-summary.ts` are generated and committed. Row 5 deletes both with the rest |
| Fixture | `tests/fixtures/contracts/pipeline-test-summary/one-row.json`, so the fixture round-trip test reaches it through `_fixtures.py` `BY_STEM` |

**Columns, in order.** Alias types are from `backend/idhazh/contracts/base.py:160-258`.

| Column | Type | Meaning |
| --- | --- | --- |
| `case` | `Slug` | which pipeline-test case wrote the row - `baseline`, `no-visual-decision`, `parallel-2` |
| `item_id` | `ItemId` | the article |
| `url_key` | `UrlKey` | its address key |
| `date` | `DateStamp` | the run's date |
| `run_id` | `RunId` | the run |
| `model_id` | `str` | the summarizing model's own identifier |
| `title` | `UntrustedLine \| None` | the summary's title, or null |
| `summary` | `Prose \| None` | the summary text, or null when the item failed |
| `output_digest` | `Sha256` | the digest `Summary.output_digest` already carries |
| `seen_text` | `str` | the post-extraction, post-sanitizer bytes the model was shown |
| `seen_text_sha256` | `Sha256` | their digest - the field `contracts/qualification.py:169` already declares |
| `source_url` | `Url` | where the article came from |
| `finish_reason` | `str` | why decoding stopped |
| `sampling_spelling` | `str` | the decode identity `backend/idhazh/fingerprint.py:141` already builds |
| `runtime_flags_spelling` | `str` | the server flags, same source |

| Property | Value |
| --- | --- |
| Path | `state/<destination>/summaries/<YYYY>/<MM>/<DD>.csv` - a day **file** |
| Dirname constant | `SUMMARIES_DIRNAME: Final = "summaries"` in `backend/idhazh/ledger.py`, in the block at `:126-135` |
| Path function | `summaries_path(state_dir, date)`, copying `item_health_path` at `ledger.py:469`: `state_dir / SUMMARIES_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"` |
| Writer | `append_summaries(state_dir, date, rows)`, copying `append_published` at `ledger.py:1189` - one line: `extend_ledger_file(summaries_path(state_dir, date), PipelineTestSummaryRow.csv_columns(), list(rows))`. **There is no `append_item_health`** - item health goes through `write_segment`, which is the wrong idiom here because a dispatch writes one file per day, not one per job |
| Key | `SUMMARIES_KEY: Final = ("case", "item_id")`, declared beside `ITEM_HEALTH_KEY` at `ledger.py:213`, and added to `keyed_paths` as `KeyedLedger(path, SUMMARIES_KEY, PipelineTestSummaryRow)` - copy the line at `ledger.py:2169` |
| Written by | `backend/idhazh/stages/record.py`, in `stage_record`, beside the existing `write_segment` call - **only when `settings.app.run.trial_state_dirname` is set.** The nightly run leaves it unset and writes nothing |
| Guardrail #11 | `seen_text` is post-sanitizer text, the same bytes `backend/idhazh/corpus.py` already commits. Data in a quoted cell; nothing reads it back into a prompt |

### C3 - Why a day file and not a day directory (row 3)

Plan 39 proposed `.../<DD>/<item id>.json`. Three readers break on it, and this is why the shape above is not negotiable.

| Reader | What a day directory does |
| --- | --- |
| `backend/idhazh/telemetry/inventory.py:42` | its glob matches the directory, then `:69` calls `path.stat().st_size` on it and prints an inode size as the file's bytes. **It lies rather than fails** |
| `backend/idhazh/day_partition.py:96` | `day_files` refuses anything that is not a two-digit `.csv`, via `_refuse_stray` |
| `backend/idhazh/retention.py:1478` | `prune_trial_state` walks each child with `day_files`, so that refusal raises `ValueError` inside the nightly prune step and takes it down |

Per-item replacement, plan 39's stated reason for one file per article, comes from the key in C2 instead.

### C4 - How the nightly prune finds a trial tree (row 3)

**`_prune_trial_shards` prunes nothing today and never has.** `backend/idhazh/stages/prune_state.py:394` returns when `run.trial_state_dirname` is falsy, and the nightly `config/idhazh.json:305` sets it to `null`. The nightly run cannot know what a dispatch named its tree.

| Property | Value |
| --- | --- |
| The marker | `state/<destination>/.trial-state.json`, written once by the redirect at `backend/idhazh/cli.py:524-525` when it creates the tree |
| Payload | `{"created": "<YYYY-MM-DD>", "keep_days": <int>}` - `keep_days` from `retention.trial_state_days`, which exists at `backend/idhazh/contracts/knobs/retention.py:66` with default 90 |
| Discovery | `_prune_trial_shards` enumerates `state/*/.trial-state.json` instead of reading one name from config, and calls `retention.prune_trial_state` once per tree found |
| `prune_trial_state` | **Signature unchanged** (`backend/idhazh/retention.py:1439`). It already takes `dirname`, already walks one ledger directory per child, already refuses a stray. Only its caller changes |
| The existing tree | `state/pipeline-tests/` gains a marker on the first dispatch after this row and is pruned from then on. Its committed host-fingerprint rows keep their dates and age out normally |
| Dispatch input | `.github/workflows/idhazh-pipeline-tests.yaml` gains a `destination` input defaulting to the model's own identifier, replacing the hard-coded `trial_state: pipeline-tests` at `:140` |

### C5 - The five names the site inlines (row 5)

Three import lines, five names. **Two are runtime values, not types**, and that is why this is not a straight delete.

| Name | Kind | Declared at | Read at | Inlined into |
| --- | --- | --- | --- | --- |
| `ConsolePanelGroup` | interface, 3 fields (`id`, `title`, `panels`) | `frontend/src/contracts/appearance-config.ts:198-208` | `config.ts:24`, re-exported at `:307` | `frontend/src/lib/server/config.ts` |
| `HostFingerprintRow` | interface, **30 fields**, used as `Required<...>` | `host-fingerprint-row.ts:39` | `host-fingerprint.ts:53` | `host-fingerprint.ts`. A field dropped in the copy is a field the reader silently stops populating, so it is copied whole and diffed field by field |
| `ServerJob` | type derived from the array below | `host-fingerprint-row.ts:36` | `host-fingerprint.ts` | `host-fingerprint.ts` |
| `SERVER_JOB` | **runtime array, 6 values**: `plan`, `work`, `assemble`, `visuals`, `runtime`, `decide` | `host-fingerprint-row.ts:34` | `SERVER_JOB.find()` at `host-fingerprint.ts:75`, a membership filter over CSV cells | `host-fingerprint.ts`. A value outside the copy becomes `null` and the row is dropped |
| `WATCHED_FLAG` + `WatchedFlag` | **runtime array, 12 values**: `amx_bf16`, `amx_int8`, `amx_tile`, `avx2`, `avx512_bf16`, `avx512_fp16`, `avx512_vnni`, `avx512f`, `avx_vnni`, `f16c`, `fma`, `sse4_2` | `machine-panels.ts:156` | `watchedFlags()` at `host-fingerprint.ts:162`, which drives the chips a machine card draws | `host-fingerprint.ts` |

`frontend/tests/processor-lost.spec.ts:163` parses `frontend/src/contracts/item-health-row.ts` as a file to get `SERVER_JOB`. It imports it from `host-fingerprint.ts` instead.

### C6 - The two binding tests (row 5)

**One per runtime vocabulary, in `backend/tests/contracts/`, reading the TypeScript literal and comparing it to the Python source of truth.** The pattern already exists at `backend/tests/contracts/_config.py:29`.

| Vocabulary | Python source of truth | TypeScript home after row 5 | Note |
| --- | --- | --- | --- |
| `SERVER_JOB` | `ServerJob(StrEnum)` at `backend/idhazh/contracts/base.py:105` | `frontend/src/lib/server/host-fingerprint.ts` | new test |
| `WATCHED_FLAG` | `WATCHED_FLAGS` at `backend/idhazh/contracts/host_fingerprint.py:46` | `frontend/src/lib/server/host-fingerprint.ts` | new test. **Python already binds itself** - `backend/idhazh/contracts/machine_panels.py:84` raises when `WatchedFlag` and `WATCHED_FLAGS` disagree, so only the cross-language half is missing |

Each test fails when one value is removed from either side. **That is not generation: it is two declarations with one gate**, and it is what stops the drift `host-fingerprint.ts:19-23` says once carried a missing flag for a month.

### C7 - What stays in the contract base (row 5)

**Deleting the wrong half of `backend/idhazh/contracts/base.py` breaks every persisted payload in the repository.**

| Part | Verdict | Why |
| --- | --- | --- |
| `json_schema()` L740-758, `schema_text()` L761, `schema_filename()` L736 | **Goes** | Writes and names a schema document |
| `__changelog__`, `ChangelogEntry` L643, `schema_version()` L732 | **Stays** | `schema_version()` returns `__changelog__[0].version`, and more than thirty production call sites stamp with it - `Article` at `extract.py:96`, `EvalRow` at `evals/score.py:175`, `RunPlan` at `stages/plan.py:396`. Only `ChangelogEntry.why` is deletable |
| `version` field L710, `_stamp_current_version` L724 | **Stays** | Every persisted payload carries it |
| `read()` L769-807, `StalePayloadError` L651 | **Stays** | It is what lets a reader say "written under an older build" rather than "malformed" |
| `__pydantic_init_subclass__` L713-722 | **Stays, both halves** | The newest-first check is what makes `[0]` mean newest |
| `__schema_stem__` | **Stays as a runtime identifier** | `contracts/console_payloads.py:173` keys a dict on it; it is the fixture directory name via `backend/tests/contracts/_fixtures.py:24` |
| `Model` L608, `without_retired_keys` L614 | **Stays** | `extra="forbid"` is the validation |
| `ServerJob` L105 | **Stays** | C6 binds the site's copy to it |
| **`CONTRACTS`, `contracts/export.py:24-166`** | **Moves to `contracts/__init__.py`** | `_fixtures.py:17` builds `BY_STEM` from it. Deleting `export.py` whole costs the fixture round-trip test its map, and that test is the one thing proving every contract still loads. Only `export()`, `export_typescript()`, `expected_filenames()` and `main()` are deleted |
| `backend/idhazh/contracts/derived.py` | **Untouched** | Three plain models, two validators, no schema writing. Plan 39 named it in error |

### C8 - The engineering contract after row 6

**Plan 41 row 6 already owns Guardrail #3 and section 11. Row 6 does not restate either.**

| Clause | After |
| --- | --- |
| Section 1a, second bullet | Deleted. Nothing generates and nothing drifts |
| Section 9, the drift-gate line | Deleted from the Definition of Done |
| Section 10, hand-editing a generated artifact | Deleted - there are none |
| `AGENTS.md` | The three phrases saying contracts are generated from the models, named in section 7 and removed |
| Guardrail #3, section 11 | **Not row 6's.** Plan 41 row 6 owns both. Row 6's oracle checks the tree, not this table |

**Guardrail #11 and Guardrail #12 are untouched.**

## Section 2 - Row 1 - The replay count leaves the dispatch surface

- **Scope:** Delete the `repeats` dispatch input from the qualification workflow and read the count from config; the loop, the gates, the diagnostics and every persisted shape are untouched.
- **Files touched:**
  - `.github/workflows/validate.yml` (L48-49, L186, L190-193)
  - `backend/idhazh/contracts/knobs/run.py`
  - `config/idhazh.json`
  - `backend/idhazh/cli.py` (L369)
  - `backend/tests/workflows/test_bench_input_drift.py`
  - `docs/how-to/evaluate-new-summarizer-model.md` (L612 carries `-f repeats='3'` inside the documented dispatch; L622 and L685 describe the machinery)
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'qualif or workflows' -q`; CI - full suite.
- **Oracle:** the dispatch command documented at `docs/how-to/evaluate-new-summarizer-model.md:612` runs against the changed workflow with no unknown-input error, and a qualification run started from the committed config does the same number of passes it does today. **What it cannot settle:** whether three is the right number of passes. Nothing here measures that, and the scope-out table says what would.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The input is deleted, not defaulted. A knob nobody should raise is a knob somebody will | Fowler |
 | 2 | The loop stays. `elapsed_seconds` spans all passes and `BUDGET` compares it to a fixed bound, so changing the pass count silently triples the gate's margin | Carmack |
 | 3 | `wording_spread` stays. It is the only witness to llama.cpp taking a different numeric path for the same prompt and seed after a build bump or a change to `n_parallel`, `flash_attention` or `cache_type_k`; `backend/idhazh/fingerprint.py:163` names that mechanism | Andre |
 | 4 | `determinism_violation` stays a column something can set. A production run structurally cannot set it, so qualification is the only place it moves, and it reaches day metrics, the run record, the console and the corpus filter | Andre |
 | 5 | `--repeats` stays on the command line. A developer running one shard locally needs it; the default comes from config | Fowler |
 | 6 | The runbook is in the file list. A documented command that fails on an unknown flag is the defect this row would otherwise ship | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Cut the loop to one pass, as plan 39 row 7 proposed | Silently loosens the only gate reading Guardrail #2 and drops 90 gate draws to 30 | A commit that re-tunes `job_budget_minutes`, records that the margin no longer compares, and accepts losing two instruments. The owner's decision, not a worker's | Andre and Carmack |
 | 2 | Default the input to 1 and keep it | The same loosening by a different road, and harder to see in a diff | Nothing saved | Fowler |
 | 3 | Keep the input and change nothing | Leaves a dispatch knob whose safe range is exactly one value | Nothing to take, and the plan's rule says a knob nobody should raise does not belong on a dispatch form | Fowler |

## Section 3 - Row 2 - The unreferenced utilities go, and the search evaluation is bounded

- **Scope:** Delete the command-line utilities the census finds unreferenced and the human-label path, and bound the one session fixture that reads a growing collection.
- **The census is the row's first commit, not its last.** Run it over `backend/`, `.github/`, `docs/`, `frontend/` and `notebooks/` before each deletion. A utility named only in a runbook still has a user.
- **The ten, measured 2026-09-21:**

 | Utility | Lines | Reference today | What the deletion owes |
 | --- | --- | --- | --- |
 | `backfill_day_metrics` | 73 | none | nothing |
 | `measure_definition_placement` | 264 | none | nothing |
 | `scan_reference_articles` | 301 | none | nothing |
 | `index_sizing` | 518 | `docs/archive/measurements-2026-08.md` | the doc keeps the finding and loses the script's name |
 | `measure_day_window` | 283 | `docs/reference/benchmarks/day-window-read.md` | same |
 | `measure_declared_wholes` | 659 | `docs/reference/benchmarks/articles-that-state-a-whole.md` | same |
 | `measure_probability_mode` | 245 | `docs/reference/benchmarks/which-probabilities-the-server-returns.md` | same |
 | `prune_artifacts` | 194 | `docs/architecture/publishing/retention.md` | same |
 | `token_budget` | 215 | `docs/concepts/config.md` | same |
 | `migrate_item_health` | 78 | `docs/architecture/contracts/schemas.md` | that page is deleted by row 5, so the reference clears itself |

- **Files touched:**
  - the ten above and their tests
  - `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/utilities/label_queue.py`, `backend/tests/test_evidence.py`
  - `backend/tests/test_retrieval_eval.py` (the session fixture at L250, the archive-walk test at L279)
  - `tests/fixtures/search/` (the new bounded corpus)
  - `docs/concepts/evaluation.md`, and each doc page above
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite.
- **Oracle:** the retrieval evaluation runs to a verdict with no file outside `tests/fixtures/` opened, and every deleted module has no importer and no invocation, established by census **before** its deletion. **What it cannot settle:** whether the fifty committed queries still represent what a reader searches for. Nothing measured that before this row either.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A one-shot measurement utility retires once its answer is written down. The doc keeps the finding and loses the script's name in the same commit | Fowler |
 | 2 | **`backend/utilities/plan_status.py` is not deleted, and nothing calls it.** The CI job that ran it was removed on 2026-09-22 (owner ruling): a page derived from every plan at once had a writer per open branch and conflicted on every line that moved. The module stays on disk as an operator surface a person runs by hand. **The census must not read "no caller" as "delete"** - this row deletes by owner-approved name, not by census verdict alone | Owner, 2026-09-22 |
 | 3 | **`backend/idhazh/evals/retrieval.py` is not deleted.** It is the only instrument that would see a similarity floor moved by 0.05 turning six search results into two | Andre |
 | 4 | The bound is a committed fixture corpus of the gold days the fifty queries answer, beside the query set already at `tests/fixtures/search/retrieval-queries.json`. `test_every_labelled_answer_is_still_in_the_archive` at L279 is deleted outright - it goes red because somebody published a day, which CLAUDE.md section 13 forbids by name | Andre |
 | 5 | The human-label path goes: zero committed rows, and CLAUDE.md section 1a makes LLM-as-judge primary evaluation. **Its sampling design moves into a `## Design rationale` section in `docs/concepts/evaluation.md` in the same commit** - the shuffle that needs no seed and stays reproducible, from `evals/labels.py:139`, and the procedure. This repository force-pushes its history away on a schedule, so a design living only in a deleted file's history is gone | Andre |
 | 6 | The five demoted qualification diagnostics stay. The scope-out table says why | Andre |
 | 7 | The whole row is deletion and test-scope change, so it is one pull request with no behaviour in it. Keeping it out of P1 is what makes that reviewable | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete all eleven utilities plan 39 named | One is `plan_status.py`, which the owner has ruled stays on disk even with no caller. The census says three others are free and seven more need a doc edit | A module the owner asked to keep, deleted on a census verdict | Owner, 2026-09-22 |
 | 2 | Delete `retrieval.py` and write the replacement fixture later | The replacement is already committed. The row would delete 990 lines and promise to rebuild something that exists | The only search-quality measure, against a five-query wiring check that cannot see a ten-point recall drop | Andre |
 | 3 | Keep the label queue because Bonsai may need human judgement | Defensible - the shape is proven for the other judge at `docs/how-to/label-the-similarity-holdout.md`. It loses because zero rows have ever been committed and the code is cheap to rewrite; what is not cheap is the sampling design, which decision 5 preserves | 1,073 lines and a schema, kept against a need nobody has expressed since it was written | Andre |
 | 4 | Fold this row into P1 | Fewer pull requests | A review that mixes about 3,400 deleted lines with a new persisted contract, where the contract is what needs the attention | Fowler |

## Section 4 - Row 3 - The pipeline test commits what it produced

- **Scope:** Give the pipeline-test workflow write permission and a committed day ledger carrying every case's summary and the bytes the model read, and make the nightly prune able to find the tree.
- **Files touched:**
  - `backend/idhazh/contracts/pipeline_test_summary.py` (new, C2)
  - `backend/idhazh/contracts/export.py` (one `CONTRACTS` entry)
  - `schemas/pipeline-test-summary.schema.json`, `frontend/src/contracts/pipeline-test-summary.ts` (generated, committed)
  - `tests/fixtures/contracts/pipeline-test-summary/one-row.json`
  - `backend/idhazh/ledger.py` (dirname, path function, writer, `keyed_paths` entry)
  - `backend/idhazh/stages/record.py` (the write)
  - `backend/idhazh/cli.py` (the marker, at the redirect L524-525)
  - `backend/idhazh/stages/prune_state.py` (L379-415, discovery by marker)
  - `backend/idhazh/retention.py` (caller only; `prune_trial_state` at L1439 is unchanged)
  - `backend/idhazh/contracts/knobs/retention.py`, `config/idhazh.json`
  - `.github/workflows/idhazh-pipeline-tests.yaml` (`contents: write`, the `destination` input, the commit step)
  - `backend/tests/test_ledger.py`, `backend/tests/retention/`, `backend/tests/workflows/test_staged_paths.py`, `test_validation_state_root.py`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'state or ledger or record or retention' -q`; CI - full suite, and one real dispatch watched to completion before the row closes.
- **Oracle:** a three-case dispatch writes **six rows** - one per case per article - all inside the run's own destination and none outside it, and a nightly prune against a tree whose marker is older than the window removes it. **What it cannot settle:** whether two models' summaries are actually comparable six months on. The row commits the evidence a person needs to judge that; it does not judge it.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A producer commits what it produces. No census of who reads it | Owner ruling 2026-09-21 |
 | 2 | **A day file, not a day directory.** C3 names the three readers that break | Carmack |
 | 3 | **The case is in the key and in the record.** Three cases share one plan, one date and the same two item ids, so without it the third silently overwrites the first two - and the third is the two-slot restart, the case whose batch split most plausibly decodes differently | Carmack |
 | 4 | **The bytes the model read are committed, not just their digest.** Two of five articles moved under their own address inside one job, on both of two dispatches. A digest detects divergence; it does not let a person read | Andre |
 | 5 | Per-key replacement comes from `ledger.keyed_paths`, which exists. Plan 39's one-file-per-article reinvented it and broke three readers doing so | Carmack |
 | 6 | **The retention window is a mechanism, not a comment.** `_prune_trial_shards` returns at `prune_state.py:394` every night because the nightly config names no tree. Discovery moves to a marker the tree carries | Carmack |
 | 7 | Traces are not committed under a trial tree. The scope-out table says why | Carmack |
 | 8 | Production is never touched. The nightly run leaves the destination unset | Fowler |
 | 9 | `contents: write` on a workflow that reads the open web in the same job is named, not assumed. It is the posture the qualification workflow already holds, and nothing fetched reaches a path, an argument or a URL (Guardrail #11) | Carmack |
 | 10 | The contract is registered in `CONTRACTS` and its generated files committed, even though row 5 deletes them. Two files of churn buys a green drift gate at every commit in between | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | `state/<model>/summaries/<YYYY>/<MM>/<DD>/<item>.json`, as plan 39 wrote it | Breaks three readers: the inventory sizes a directory, `day_files` refuses it, the nightly prune raises | A `day_partition` change and an `inventory` change, each belonging to its own row | Carmack |
 | 2 | `<YYYY>/<MM>/<DD>-<case>-<item id>.json`, the shape traces already use | Clears the inventory but not the prune, because `day_files` still refuses a non-CSV day | Fixing `day_files` for the trace shape too - a good row, and not this one | Carmack |
 | 3 | A per-case sub-path rather than a case column | Pushes the tree a fourth level below the state root, where the inventory's two-depth glob stops matching, and two cases cannot be diffed without walking two trees | One path segment and a worse comparison | Carmack |
 | 4 | Commit the digest and not the text | The address is not a substitute - 40 percent of articles moved inside one job | Nothing that matters: two article bodies a dispatch | Andre |
 | 5 | Commit the whole run directory | The cost and health rows already land in their own ledgers | Several times the bytes for readings recorded elsewhere | Fowler |
 | 6 | Leave the retention window as a description on the knob | It is what plan 39 did, and it prunes nothing | Nothing to take. A collection with a window nothing enforces is the growth Guardrail #12 names | Carmack |

## Section 5 - Row 4 - Nine console specs visit every route the site serves

- **Scope:** Correct the nine hand-written console route lists so each visits all five routes the site serves.
- **Files touched:** `frontend/tests/console-axis.spec.ts:29`, `console-chrome.spec.ts:30`, `console-model-rule.spec.ts:133`, `console-nav.spec.ts:37`, `console-polarity.spec.ts:33`, `console-readout.spec.ts:23`, `console-title.spec.ts:48`, `console-voices.spec.ts:27`, `console-window-claims.spec.ts:57`
- **Acceptance gates:** local - `npm --prefix frontend run test:browser -- --project console`; CI - full suite.
- **Oracle:** every console route the site serves is visited by every spec that claims to cover all of them. **This fails on the base tree today** - the site serves five and these specs list three, three, three, four, four and five, so `/console/judgement/` is visited by none of them. **What it cannot settle:** whether the tenth route added next quarter reaches all nine lists. Nothing enforces that after this row, and decision 1 says why.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The lists stay nine and stay hand-written. `frontend/src/lib/console/band.ts:131-133` records the ruling: the navigation spec types them out "on purpose - that copy is what the owner chose and reading it from here would only prove the page agrees with itself" | Owner, quoted in the code |
 | 2 | The row fixes the hole it finds rather than preserving it. A spec that claimed to cover every route and missed one was not covering anything | Susan |
 | 3 | The cost is named and accepted: adding a console route stays nine test edits | Fowler |
 | 4 | `console-window-claims.spec.ts:57` lists routes without the leading and trailing slash the others use. It keeps its own spelling; this row changes membership, not form | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Export `ROUTE_IDS` from `band.ts` and have all nine read it | Overturns a ruling recorded in the code at `band.ts:131` | The owner relaxing that ruling. Defensible for the eight specs that do not test the strip, and a separate question | Owner |
 | 2 | A new exported constant in `frontend/tests/` that all nine import | The same circularity objection one file along, and a tenth place the list lives | About 20 lines, and a list still updated by hand | Fowler |
 | 3 | Leave the hole and note it | It is the only defect in this plan a reader could meet | Nothing to take | Susan |

## Section 6 - Row 5 - The generated contract layer goes

- **Scope:** Delete every generated JSON schema and every generated TypeScript contract, the two generators, the drift tests and the continuous-integration job, after inlining the five names the site uses and binding the two vocabularies.
- **The case is reviewer attention, not runtime.** The drift gate costs 1 second across four measured runs, the layer publishes zero bytes, and it is 1.1 percent of the pack. What it costs is that about one commit in six has carried a regenerated diff a reviewer scrolled past, and that the generator runs in full to serve four types out of sixty-six.
- **Files touched:**
  - `schemas/` (all), `frontend/src/contracts/` (all)
  - `backend/idhazh/contracts/export.py` (delete `export()`, `export_typescript()`, `expected_filenames()`, `main()`; move `CONTRACTS` to `contracts/__init__.py`), `contracts/typescript.py`, `contracts/base.py` (C7)
  - `backend/tests/contracts/test_schema_drift.py`, `test_typescript_contracts.py`, `test_cell_shapes.py`
  - **the six backend modules reading the deleted directory, which plan 39 row 1 did not name:** `test_article_and_eval.py:149`, `test_closed_vocabularies.py:53`, `test_run_timeline.py:187`, `test_stamped_boundary.py:186`, `_config.py:29`, and `test_sources_and_marks.py:174` - **that last one spells `REPO_ROOT / "schemas"` directly, so a census on `SCHEMAS_DIR` misses it**
  - `backend/tests/conftest.py:41` (the `SCHEMAS_DIR` constant)
  - **the eight frontend specs reading by path, which plan 39 row 1 did not name:** `console-machine-cards.spec.ts:132` and `:260`, `console-machine-panels.spec.ts:28`, `console-model-instruments.spec.ts:45`, `console-model-reasons.spec.ts:39`, `prompt-reuse.spec.ts:198`, `settings-moved.spec.ts:189`, `processor-lost.spec.ts:163`
  - `frontend/scripts/run-checks.ts:310`, `test-scope.ts:169`, `tests/test-scope.test.mjs` (four lines), `copy-visuals.mjs:52`
  - `frontend/src/lib/server/config.ts`, `host-fingerprint.ts` (C5), and the two new binding tests (C6)
  - `.github/workflows/ci.yml` (the drift job, ~L208-214), `pyproject.toml:170` (`idhazh-export-schemas`)
  - `docs/architecture/contracts/schemas.md` (deleted)
- **Acceptance gates:** local - `npm --prefix frontend run check`, `npm --prefix frontend run test:changed -- --list` then the selected checks, `python -m pytest backend/tests/contracts -q`; CI - full suite and the browser smoke.
- **Oracle:** each binding test in C6 fails when one value is removed from either side, proved by removing one and watching it go red before it is restored. **What it cannot settle:** whether the 28 non-vocabulary fields of `HostFingerprintRow` were copied faithfully. Nothing can check that once the source is gone, so it is checked before - field by field, against the generated file, in the same session.
- **The green-suite traps, named so a worker looks for them:**

 | Trap | What happens |
 | --- | --- |
 | Three surviving tests are parametrized over a glob of the deleted directory | They pass with **zero cases** rather than fail. The check is a comparison of collected test counts before and after, not pass or fail |
 | `backend/tests/contracts/_config.py:29` asserts every mention of a name is on a list of survivors | Deleting `frontend/src/contracts/eval-row.ts` **removes a mention**, so the subset assertion still holds and the test stays green pointing at a file that is gone |
 | `frontend/tests/processor-lost.spec.ts:163` parses a generated file as text | It imports `SERVER_JOB` from `host-fingerprint.ts` instead |
 | Three of the eight frontend specs read at **module scope** | One missing file raises while the module loads and takes every test in that file with it, including the ones that never touched a schema |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The layer is deleted whole rather than pruned to the used files. 62 of 66 have no importer, and a generator kept for four types is a generator | Owner ruling 2026-09-21 |
 | 2 | The Pydantic models stay. They are the validation; the schemas were a copy of them in another notation | Fowler |
 | 3 | The drift gate goes with the artefacts. It checked that a generated file still matched the thing that generated it, which is a loop | Fowler |
 | 4 | **`docs/architecture/contracts/schemas.md` is deleted, not refreshed.** The agent bootstrap routes to it, so the next agent reading a page titled for schemas builds what it describes. This is the single most likely way the whole layer returns | Fowler |
 | 5 | **`CONTRACTS` is re-homed, not deleted.** `_fixtures.py:17` builds `BY_STEM` from it, so deleting `export.py` whole costs the fixture round-trip test its map - and that test is the one thing proving every contract still loads | Fowler |
 | 6 | **`derived.py` is untouched.** It writes no schema. Plan 39 named it in error | Fowler |
 | 7 | The prose requirement dies with its consumer: it is copied into the generated schema and nowhere else. The version stamp and the changelog stay - `schema_version()` reads `__changelog__[0]` and thirty-plus production call sites stamp with it | Fowler |
 | 8 | Each closed vocabulary keeps one binding test. Two declarations with one gate is not generation, and it is cheaper than the drift the row otherwise buys | Fowler |
 | 9 | The cost framing plan 39 used - forty thousand lines between a person and a change - is dropped. The drift gate is one second and the layer publishes nothing. A row whose stated benefit is one second is a row that gets reverted the first time an inlined type drifts | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete only the 62 unimported TypeScript files | Leaves the generator, both drift tests, the CI job and 24,697 lines of schema to serve four types | About 8,700 lines removed instead of about 34,300, and the same ritual on every field | Fowler |
 | 2 | Keep the schemas, delete the TypeScript | The schemas' only readers afterwards are the generator that writes them and the test that checks the generator | About 9,600 lines removed, and a gate policing itself | Fowler |
 | 3 | Point the site at the generated types instead of its hand-written copies | The opposite change, and defensible - one declaration per shape. It loses because nobody has wanted it for 66 shapes over the project's life, and the hand-written copies are the ones under test | A rewrite of the payload, search and console layers against a need nobody has expressed | Fowler |
 | 4 | Inline the two vocabularies with no binding test | It is the drift `host-fingerprint.ts:19-23` says once carried a missing flag for a month | Two copies with nothing comparing them, and a machine card that quietly stops drawing a chip | Fowler |

## Section 7 - Row 6 - The engineering contract and the pages catch up

- **Scope:** Amend the engineering-contract clauses this plan contradicts that plan 41 does not own, and refresh every page whose description of the contract layer or the qualification surface is now wrong.
- **Files touched:** `CLAUDE.md` (section 1a second bullet, section 9's drift-gate line, section 10's hand-editing line), `AGENTS.md`, `docs/reference/ci-model-runtime.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/repository-layout.md`, `docs/how-to/run-the-gates.md`
- **Acceptance gates:** `python backend/utilities/doc_load.py` before and after, and the split test on any page gaining a section. No application suite is required for a documentation-only closure.
- **Oracle:** no clause of the engineering contract requires a generated artefact, a schema file, or a drift gate - **checked clause by clause against the tree after plan 41 has merged, not against this plan's table.** That is what stops this row reverting plan 41. **What it cannot settle:** whether a later agent reads the amended clause the way it was meant. Decision 5 is the mitigation.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The amendment ships with row 5, not after it. CLAUDE.md section 0 requires a conflicting rule to be amended in the same change | Owner, CLAUDE.md section 0 |
 | 2 | **Row 6 does not restate Guardrail #3 or section 11.** Plan 41 row 6 owns both. Plan 39's clause table quotes the text on main today, and applying it verbatim after plan 41 merges reverts plan 41 - cleanly, with nothing red, because no gate reads CLAUDE.md | Fowler |
 | 3 | Each guardrail that moves records who moved it and when, on the line that moved (CLAUDE.md section 1) | Fowler |
 | 4 | Guardrail #11 and Guardrail #12 are untouched | Fowler |
 | 5 | The three phrases in `AGENTS.md` saying the contracts are generated from the models are named and removed. An unnamed amendment is one nobody checks, and agent tools read that file instead of the engineering contract | Fowler |
 | 6 | `TODO/STATUS.md` is not regenerated by anything after 2026-09-22. If the file still sits in the tree when this row runs, the row deletes it: a summary nobody regenerates is worse than no summary, because it looks current | Owner, 2026-09-22 |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take a named exception for each row instead of amending the contract | Several exceptions to one rule is the rule being wrong | A handful of dated notes and a guardrail nobody believes | Fowler |
 | 2 | Amend the contract after row 5 lands | Leaves the repository in a state where its own contract forbids its own code | Nothing saved; it is a sequencing error | Owner |
 | 3 | Apply plan 39's clause table verbatim | It reverts plan 41's amendment to Guardrail #3, cleanly and silently | A second amendment nobody knew was needed, found by whoever next reads the guardrail | Fowler |

## Section 8 - Row 7 - The hosted span sink goes

- **Scope:** Delete the optional hosted trace sink, its selection code, its optional dependency and the pages describing it, keeping the local trace file the pipeline already writes with the standard library.
- **Owner approval 2026-09-22.** This reverses the ruling recorded at `docs/concepts/telemetry.md:553`, where the span tree was adopted on the owner's reasoning against three personas. CLAUDE.md section 0: user approval supersedes every agent and every rule.
- **Files touched:**
  - `backend/idhazh/telemetry/sinks.py` (`langfuse_sink` at `:110-137`, `_LangfuseSink` at `:140-190`, `_trace_context` at `:193-203`, `_usage` at `:213-221`)
  - `backend/idhazh/telemetry/__init__.py` (the `langfuse_sink` re-export)
  - `backend/idhazh/stages/work.py` (`trace_sink` at `:87-101` collapses to the file sink)
  - **`backend/utilities/probe_feeds.py:392`** - a second caller plan 39 row 15 did not list. `:46` describes it in the module docstring
  - `backend/tests/test_spans.py` (`:407-424`, `:425-453`), `backend/tests/contracts/test_telemetry_surface.py:77` (the export list)
  - `pyproject.toml` (the `langfuse` extra at `:164-166`, its comment block, the `langfuse.*` mypy override at `:216-218`)
  - `docs/concepts/telemetry.md` (`:199-203`, `:553-561`, the decision table), `docs/how-to/run-the-gates.md:231-234`
  - `backend/idhazh/contracts/knobs/observability.py` - **the `tracing_enabled` description only.** No field is removed; the knob still switches the local file sink
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'telemetry or trace or span or canaries' -q`; CI - full suite.
- **Oracle:** a run still writes one trace line per span to the committed local trace file, byte-identical to today, **and no module in the repository can send a span anywhere else** - asserted by a census that finds zero references to the package outside the lockfile. The first half is the behaviour that must not change; the second is what the row removes. **What it cannot settle:** whether the skill the sink was kept for transfers to a future repository. That was the owner's reason for keeping it, and it is not a thing a test can weigh.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The local trace file is the whole feature. The hosted viewer is a second path no pipeline runs - continuous integration installs neither the extra nor a key | Owner, 2026-09-22 |
 | 2 | It reads against the engineering contract's own words: logging is local by construction, with no log sink and no log service (CLAUDE.md section 1b). Deleting the sink removes a contradiction a reader had to resolve | Fowler |
 | 3 | **`backend/utilities/probe_feeds.py:392` is in the file list.** It is a second caller, nothing imports that module, and the suite stays green while a utility a person runs by hand raises `AttributeError`. Plan 39 row 15 missed it | Carmack |
 | 4 | `tracing_enabled` stays. It switches the committed file sink, which is the surviving feature | Fowler |
 | 5 | The beneficiary comment at `pyproject.toml:162` was corrected on 2026-09-22 and dies with the extra. Correcting it first is what kept the tree honest in between | Carmack |
 | 6 | A developer who wants a span tree drawn reads the committed local file. That is the cost, and it is named | Owner, 2026-09-22 |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep it, since the extra is opt-in and costs continuous integration nothing | It was the standing position and the owner has reversed it. An unused second implementation is the thing that rots, and it is a sink pointed at a third party sitting in a repository whose contract says there is no sink | About 120 lines across five files, a comment block, an extra and a mypy override | Owner, 2026-09-22 |
 | 2 | Keep the sink interface and delete only the hosted implementation | An interface with one implementation is the implementation | About 40 lines kept for a shape with nothing behind it | Fowler |
 | 3 | Correct the beneficiary comment and stop there | That was this row before the approval. It leaves the dependency, the second code path and the contradiction | Two lines changed and nothing removed | Carmack |

## See also

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - the parent, whose rows 1, 7, 8, 12, 15, 17 and 19 this plan carries.
- [`20260921-41-lane-a-model-file-plan.md`](20260921-41-lane-a-model-file-plan.md) - owns Guardrail #3 and section 11; merges before row 6.
- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the workflows.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.
