# The ledgers, the evaluations, and the generated layer

**Last Updated**: 2026-09-21

**Level**: 5. Row 5 deletes the generated contract layer whole and row 6 amends the engineering contract that requires it. Every other row here is Level 2 or 3 and runs AUTO once the user authorizes. Row 5 and row 6 PAUSE for the owner before their pull request opens (docs/how-to/execute-a-plan.md, section Escalation).

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 39 split into lanes. Plans 41 and 42 took the model file and the workflows. What is left is the evaluation ledgers, the site's console specs, and the 34,349 generated lines nobody imports. Three of those rows were wrong when they were written: one cuts the work a budget gate measures without moving the gate, one deletes 990 lines of search evaluation to fix two lines in a test, and two overturn rulings a person already made and wrote down. This plan carries what survives, corrected, with the file lists the original rows were missing. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| The second rule | **An instrument is not scaffolding.** A thing that measures something nothing else measures stays, even when it is large and even when no gate reads it. The test is what goes blind when it leaves, and the answer is written in the row. |
| The measure | **Edits per future change, and reviewer attention per commit.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Take the replay count off the dispatch surface and leave the loop that three gates draw from. Delete the ten command-line utilities the census finds unreferenced, and bound the search evaluation's one growing read instead of deleting the evaluation. Give the pipeline test a committed day ledger carrying every case, its summary and the bytes the model actually read. Make nine console specs visit all five routes the site serves. Delete the generated contract layer whole - every JSON schema, every generated TypeScript file, both generators, the drift tests and the continuous-integration job - inlining by hand the five names the site actually uses and giving each closed vocabulary one binding test. Amend the three engineering-contract clauses plan 41 does not already own. Correct one dependency's beneficiary line, which names a feature the dependency does not deliver. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 39 rows 1, 7, 8, 12, 17 and 19, which become `COLLAPSED` in that plan's Reckoner. **Plan 39 row 15 is refused outright** - see the scope-out table. |
| Assumes | **Plan 41 merges before row 6 starts.** Plan 41 row 6 rewrites Guardrail #3 and section 11; row 6 here must quote the text plan 41 leaves, not the text on main today. Rows 1 to 4 assume nothing and may start the moment the user authorizes. |
| ESCALATE triggers | (1) Row 1 must not change what the BUDGET gate measures. If the work a qualification shard does per dispatch changes at all, stop - that gate compares wall clock against a fixed bound and nothing re-tunes it. (2) Row 3 writes a new committed collection. If the nightly prune cannot discover it by the marker in C3, stop; a collection nothing prunes is the growth Guardrail #12 names. (3) Row 5 deletes the artefacts a drift gate protects. If the five inlined names cannot be proved identical to the generated ones before the deletion, stop. (4) Row 5 changes two closed vocabularies from generated to hand-written. Each ships its binding test in the same commit or the row stops. (5) Row 6 amends the engineering contract; it lands in the same pull request as row 5, never after. (6) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Three pull requests. Two run at once because their file sets are disjoint. The third runs last and alone, because it touches a generated twin of every contract the first two edit. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Cutting qualification to one pass per article** (plan 39 row 7's stated scope) | About 180 lines stay, and a qualification dispatch keeps costing what it costs today | **Refused as written, and the reason is a gate nobody checked.** `elapsed_seconds` is stamped before the repeat loop (`backend/idhazh/stages/qualify.py:554`), so it spans all three passes, and the BUDGET gate divides it by 60 and compares it against a fixed `job_budget_minutes` dispatch input (`backend/idhazh/evals/qualify.py:467-483`). Cut three passes to one and the measured side falls by about two thirds while the bound does not move: a candidate roughly 2.9x slower per item than today's passes the only gate that reads Guardrail #2, and every historical BUDGET verdict stops being comparable with every future one. Three more gates - `REASONING_LEAKAGE`, `SCHEMA_VALIDITY`, `PUBLISHABLE_LENGTH` - read properties of the sampled output at `temperature: 0.2`, not of the request, so 90 draws become 30 and detection power on a one-in-fifty schema failure falls from about 84 percent to about 45. **What would bring it in:** a commit that moves `job_budget_minutes` to the one-pass equivalent in the same diff, says in `docs/concepts/evaluation.md` that the margin is not comparable across the change, and accepts losing `wording_spread` and a `determinism_violation` column that can move. That is a measurement decision, not a cleanup, and it is the owner's. Andre and Carmack, independently |
| **Deleting `backend/idhazh/evals/retrieval.py`** (plan 39 row 17 decisions 3 and 6) | 990 lines stay, and one session-scoped fixture keeps reading a growing collection until row 2 bounds it | **The premise is wrong twice.** The growing walk is two lines in the test, not in the module: `backend/tests/test_retrieval_eval.py:250` builds a session fixture from the whole published archive, and every other test in that file builds a bounded in-memory corpus. And the replacement plan 39 promised - "a fixture of query and answer pairs, written the day search changes" - is already committed at `tests/fixtures/search/retrieval-queries.json`, 42,052 bytes, at least 50 queries with at least two gold answers each. Deleting the module leaves `frontend/tests/search.spec.ts:122`, a five-query wiring check whose own file computes its standard error at 0.18 against 0.057 at fifty: a ten-point recall drop is invisible to it. Row 2 bounds the fixture instead. Andre |
| **Deleting the hosted span sink** (plan 39 row 15) | About 120 lines across four files stay, plus one config knob, one optional extra no workflow installs, and a contradiction a reader resolves between CLAUDE.md section 1b and a sink in the tree | **Refused outright. It re-runs an argument a person already settled.** `docs/concepts/telemetry.md:553`: "The span tree was adopted on the owner's reasoning and not on the engineering case. Three personas judged Langfuse against this project alone and refused it... The owner's argument is different and was not one they were briefed on - the skill and the code transfer to a future repository, and that is worth paying for. Authority: owner, 2026-08-30." Plan 39 row 15 lists Fowler as authority for all three of its decisions. CLAUDE.md section 0: user approval supersedes every agent. Carmack, one of the three overruled, tested every candidate new fact since that date - CI cost is still zero, no workflow installs the extra and CI holds no key; the security surface is unchanged; the one maintenance event carried the sink rather than fought it; the version pin has not drifted. **What would bring it in: the owner saying so.** What the row found that is real is one line, and row 7 takes it |
| **Reading the console route list from the site's own source** (plan 39 row 19 decision 2) | Adding a console route stays nine test edits | **Refused as written; the defect it found is kept.** `frontend/src/lib/console/band.ts:131-133` records the ruling in the code: "`console-nav.spec.ts` types them out a third time on purpose - that copy is what the owner chose and reading it from here would only prove the page agrees with itself." Row 4 keeps the navigation spec's independent copy, which is the oracle for the strip, and fixes the coverage hole in all nine. **What would bring it in:** the owner relaxing that ruling for the eight specs that do not test the strip, which is a separate and smaller question than the one plan 39 asked |
| **Splitting the two largest console specs** | `console-machine-data.spec.ts` at 58,345 bytes and `console-machine.spec.ts` at 43,215 bytes keep answering several questions each | A different question - one file answering many - and its own structural pull request. One addition buys one cut. Fowler |
| **Fixing `day_partition.day_files` to accept a `.jsonl` day** | A trial tree may not commit traces, so row 3 commits the CSV ledgers only | `backend/idhazh/day_partition.py:96` refuses anything that is not a two-digit `.csv` day file, and `prune_trial_state` walks through it. Committing `state/<trial>/traces/YYYY/MM/DD-N-S.jsonl` would raise `ValueError` and take the nightly prune step down with it. That is a real latent defect, it predates this plan, and it is one row in its own right. Row 3 routes around it rather than arming it. Carmack |
| **A human-label queue rewritten from scratch** | Nothing today - there are zero committed label rows | Row 2 deletes the code and moves the sampling design into `docs/concepts/evaluation.md` in the same commit, because this repository force-pushes its own history away on a schedule (CLAUDE.md section 8) and a design that lives only in a deleted file's git history is a design that is gone. The rewrite is cheap; re-deriving the sampling design is not. Andre |
| **Deleting the five demoted qualification diagnostics** (plan 39 row 17 decision 4) | Seven diagnostic lines stay on the qualification report | **Refused.** Plan 39 never named the five, so the clause cannot be reviewed against anything. On merit, four of the candidates each witness a failure no gate catches: `unsupported_numbers` is the only witness to a fabricated figure, which is the one summary error a reader acts on; `hedge_dropped` is the only witness to "reportedly" becoming assertion; `extractiveness_mean_non_brief` is the only counterweight to the faithfulness floor on the long path, because `BRIEF_COPYING_CEILING` gates brief items only; `below_lead_coverage_min_share` is the only witness to a model summarising paragraph fourteen. The `diagnostics()` docstring states their purpose: "a number with no bar is still the thing a human reads when a gate passes and the output still looks wrong." Andre |

### What a change costs today

Measured on the tree at `origin/main`, 2026-09-21, except where a line says estimate.

| Reading | Value | Where |
| --- | --- | --- |
| Generated JSON schema | **66 files, 24,697 lines** | `schemas/` |
| Generated TypeScript | **66 files, 9,652 lines** | `frontend/src/contracts/` |
| Import statements in the whole site that reach any of it | **3, in 2 files**, pulling **5 names** | `frontend/src/lib/server/config.ts:24`, `host-fingerprint.ts:37-38` |
| Of those five, how many are runtime values rather than types | **2** - `SERVER_JOB` and `WATCHED_FLAG` are arrays a filter reads, not type declarations | `host-fingerprint.ts:75`, `:162` |
| Generated TypeScript files with no importer | **62 of 66** | derived from the line above |
| Commits on `HEAD` that rewrote a generated file | **370 of 2,280 - about one in six** | 344 touching `schemas/`, 26 touching `frontend/src/contracts/` |
| **What the drift gate costs on the runner** | **1 s, four runs, zero spread** - under 1.5 percent of the job step it sits in, which ran 110 / 64 / 106 / 72 s | runs 35660527882, 35658298924, 35657840521, 35657514579, 2026-09-22 |
| **What the generated layer costs the published site** | **zero bytes.** Vite tree-shakes all 66 modules out; the built site is 70,005,963 bytes against a 1 GB ceiling | committed `frontend/build/` |
| Bytes the layer adds to the repository | 1,592,293 - **1.1 percent** of a 137.46 MiB pack | `schemas/` 1,018,328 B; `frontend/src/contracts/` 573,965 B |
| Files reading the generated directories by **path** rather than by import | **8 frontend specs, 4 lines of frontend tooling, 6 backend contract modules** - and plan 39 row 1 named none of them | section 6 |
| Of those eight specs, how many read at **module scope**, so one missing file takes the whole file down | **3** | `console-machine-panels.spec.ts:28`, `console-model-instruments.spec.ts:45`, `console-model-reasons.spec.ts:39` |
| Command-line utilities with **no textual reference anywhere** outside `backend/utilities/` | **3 of 66**, 638 lines | `backfill_day_metrics` 73, `measure_definition_placement` 264, `scan_reference_articles` 301 |
| Utilities referenced **only by a `docs/` page** | **7**, 1,761 lines | section 3 |
| Utilities plan 39 row 17 claimed had no code reference | **11** - the census says 3 | census, 2026-09-21 |
| `backend/utilities/plan_status.py`, which plan 39 row 17 named for deletion | **1,204 lines, invoked at `.github/workflows/ci.yml:292`** with `--write`, and named in `AGENTS.md:65` as the generator of `TODO/STATUS.md` | it has a caller |
| Console routes the site serves | **5** | `frontend/src/routes/console/`, five `+page.server.ts` |
| Console specs that hand-write a route list | **9 of 62**, listing 3, 3, 3, 4, 4 and 5 routes | section 5 |
| Console routes visited by **none** of those nine | **1** - `/console/judgement/` appears in 12 lines across the whole test tree, in five single-route specs, and in no multi-route list except the navigation spec's | `git grep -oh "'/console/[a-z-]*/'"` |
| Articles one pipeline-test dispatch summarises | **2**, across **3 cases**, against one plan, one date and the same two item ids | `config/pipeline-tests.json:2`; `.github/workflows/idhazh-pipeline-tests.yaml:300`, `:311`, `:370` |
| What a commit step costs that workflow | **about 3 s against a 140-minute bound - 0.04 percent** | measured neighbours in run 35625832336: a small payload commit 2 s, a whole digest day 16 s; estimate |
| Articles that moved under their own address inside one multi-hour job | **2 of 5, on both of two dispatches, 2026-09-15** | `docs/how-to/evaluate-new-summarizer-model.md:551` |

## Section 0b - What this plan does, in one list

Seven rows, three pull requests. Read this before the tables.

1. Take the replay count off the dispatch surface. It becomes a config value with the loop untouched.
2. Delete the ten utilities the census finds unreferenced, delete the human-label queue and keep its sampling design, and bound the one growing read in the search evaluation instead of deleting the evaluation.
3. Give the pipeline test a committed day ledger: one row per case per article, carrying the summary and the bytes the model actually read, discoverable by the nightly prune.
4. Make all nine multi-route console specs visit all five routes the site serves.
5. Delete the generated contract layer whole, inlining five names by hand and giving each closed vocabulary one binding test.
6. Amend the three engineering-contract clauses plan 41 does not own, and the three phrases in the agent pointer that say contracts are generated.
7. Correct one dependency's beneficiary line, which names a feature its own code says it does not deliver.

## Section 1 - Status Reckoner

**A pull request is one worktree, one branch, one review. A row is ready when every `Depends-on` is DONE and its owned files are disjoint from every pull request in flight.**

| # | Row title | PR | Depends-on | Status | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The replay count leaves the dispatch surface | P1 | - | PENDING | - | - | - |
| 2 | The utilities with no caller go, and the search evaluation is bounded | P1 | 1 | PENDING | - | - | - |
| 3 | The pipeline test commits what it produced | P1 | 2 | PENDING | - | - | - |
| 4 | Nine console specs visit every route the site serves | P2 | - | PENDING | - | - | - |
| 5 | The generated contract layer goes | P3 | 1, 2, 3, 4, plan 41, plan 42 | PENDING | - | - | - |
| 6 | The engineering contract and the pages catch up | P3 | 5, plan 41 | PENDING | - | - | - |
| 7 | The dependency's beneficiary line says what it buys | P3 | 5 | PENDING | - | - | - |

### The three pull requests and the files each owns

**Two pull requests never own one file. That is what lets P1 and P2 run at once.**

| Wave | PR | Rows | Files it owns, exclusively | Commits, in order |
| --- | --- | --- | --- | --- |
| 1 | **P1 - the evaluation ledgers** | 1, 2, 3 | `backend/idhazh/stages/qualify.py`, `stages/qualify_decide.py`, `stages/record.py`, `evals/qualify.py`, `evals/labels.py`, `evals/retrieval.py`, `contracts/qualification.py`, `contracts/label_row.py`, `contracts/knobs/retention.py`, `contracts/knobs/run.py`, `idhazh/ledger.py`, `idhazh/cli.py`, `idhazh/retention.py`, `stages/prune_state.py`, `backend/utilities/` (the ten named in section 3, plus `label_queue.py`), `.github/workflows/validate.yml`, `.github/workflows/idhazh-pipeline-tests.yaml`, `config/idhazh.json`, `tests/fixtures/contracts/qualification-*/`, `tests/fixtures/search/`, the named backend tests, `docs/concepts/evaluation.md`, `docs/how-to/evaluate-new-summarizer-model.md`, `docs/reference/repository-layout.md` | (a) the dispatch input - behavioural; (b) the deletions and the fixture bound - structural; (c) the new ledger - behavioural |
| 1 | **P2 - the console coverage hole** | 4 | `frontend/tests/console-axis.spec.ts`, `console-chrome.spec.ts`, `console-model-rule.spec.ts`, `console-nav.spec.ts`, `console-polarity.spec.ts`, `console-readout.spec.ts`, `console-title.spec.ts`, `console-voices.spec.ts`, `console-window-claims.spec.ts` | one commit, behavioural |
| 2 | **P3 - the generated layer and the contract** | 5, 6, 7 | `schemas/`, `frontend/src/contracts/`, `backend/idhazh/contracts/export.py`, `contracts/typescript.py`, `contracts/base.py`, `contracts/__init__.py`, the nine backend contract tests in section 6, the eight frontend specs in section 6, `frontend/scripts/run-checks.ts`, `test-scope.ts`, `tests/test-scope.test.mjs`, `frontend/src/lib/server/config.ts`, `host-fingerprint.ts`, `backend/tests/conftest.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `CLAUDE.md`, `AGENTS.md`, `docs/architecture/contracts/schemas.md` and the pages in section 7 | (a) the inlines and their binding tests, adding nothing and deleting nothing - behavioural; (b) the deletion - structural; (c) the contract amendment and the beneficiary line - documentation |

**Why P3 runs last and alone.** Row 5 deletes a generated twin of every contract P1 edits. Running it beside P1 is a conflict on every file that moved. It also depends on plan 41 and plan 42 for the same reason.

**Why P1 and P2 run together.** No file appears in both. P2 owns nine console specs; P3 owns eight different ones, and the two sets are disjoint - checked name by name.

**Peak workers: 2.**

## Section 1a - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent one of these; it reads this section.**

### C1 - The replay count (row 1)

| Property | Value |
| --- | --- |
| Where it lives after the row | `run.qualification_repeats` in `backend/idhazh/contracts/knobs/run.py`, default `3`, `ge=1`, set in `config/idhazh.json` |
| Where it stops living | `.github/workflows/validate.yml:48-49` - the `repeats` dispatch input is deleted, not defaulted. The `REPEATS` environment variable at `:186` and the shell range check at `:190-193` go with it |
| What does not change | The loop at `backend/idhazh/stages/qualify.py:493`, the outside-in order and its comment, the `if repeat == 1` score filter at `:528`, `wording_spread`, `determinism_violation`, the ten gates, and what `elapsed_seconds` measures |
| `--repeats` on the command line | Stays, because a developer running one shard locally needs it. Its default comes from config rather than from the literal `3` at `backend/idhazh/cli.py:369` |
| Persisted shapes | **Unchanged.** `ItemObservation.repeat`, `QualificationShard.repeats` and `QualificationReport.repeats` all stay, so the committed fixtures still load and there is no read-side migration |

### C2 - The pipeline-test summaries ledger (row 3)

**New committed collection.** `state/<destination>/summaries/<YYYY>/<MM>/<DD>.csv` - a day **file**, not a day directory.

| Property | Value |
| --- | --- |
| Why a CSV day file | Every other day-sharded store is one (`backend/idhazh/telemetry/inventory.py:33`). A day directory is matched by the operator inventory's glob and then sized with `path.stat().st_size` on a directory, which prints an inode size and reports it as the file's bytes - it lies rather than fails. The same shape is refused outright by `day_partition.day_files`, which would raise inside the nightly prune |
| Key | `(case, item_id)`. `ledger.keyed_paths` (`backend/idhazh/ledger.py:2030`) already gives per-key replacement, so a re-run replaces exactly what it re-summarised without one file per article |
| Why the case is a column | The workflow sets one destination and runs three cases - `baseline`, `no-visual-decision`, `parallel-2` - against one plan, one date and the same two item ids. Without the case in the key, the third case overwrites the first two and the comparison the workflow exists for is thrown away. The case rides in the **record** as well as the key, because a file copied out of the tree loses its filename |
| Columns | `case`, `item_id`, `model_id`, `summary`, `seen_text_sha256`, `seen_text`, `source_url`, `sampling_spelling`, `runtime_flags_spelling`, `finish_reason` |
| Why `seen_text` and not just its digest | Two of five articles moved under their own address inside one job on both of two dispatches (`docs/how-to/evaluate-new-summarizer-model.md:551`). A digest detects that the bytes changed; it does not let a person read what the model read. Comparing two models six months later needs the article, and the address will not serve it |
| Guardrail #11 | `seen_text` is post-extraction, post-sanitizer text - the same bytes `backend/idhazh/corpus.py` already commits. It is data in a quoted cell, never an instruction, and nothing reads it back into a prompt |
| Written by | `backend/idhazh/stages/record.py`, and **only when a trial destination is set**. The nightly run leaves it unset and writes nothing |
| Production | Never touched |

### C3 - How the nightly prune finds a trial tree (row 3)

**This is the row's hardest part and the reason plan 39's retention line was not executable.** `_prune_trial_shards` (`backend/idhazh/stages/prune_state.py:377`) reads `run.trial_state_dirname` from the **nightly run's** config, and `config/idhazh.json:305` sets it to `null`. The function returns on its first line, every night, forever. The nightly run has no way to know what a dispatch named its tree.

| Property | Value |
| --- | --- |
| The marker | Each trial tree carries `state/<destination>/.trial-state.json` at its root, written once by the redirect at `backend/idhazh/cli.py:510-523` when it creates the tree |
| Payload | `{ "created": "<YYYY-MM-DD>", "keep_days": <int> }`. `keep_days` comes from `retention.trial_state_days`, which already exists at `backend/idhazh/contracts/knobs/retention.py:66` with a default of 90 |
| Who reads it | `retention.prune_trial_state` discovers trees by scanning `state/*/.trial-state.json` instead of by being told one name in config |
| What that changes for the existing tree | `state/pipeline-tests/` gains a marker on the first dispatch after this row and is pruned from then on. Two host-fingerprint rows already committed there under the old name keep their dates and age out normally |
| What is committed under a trial tree | The CSV ledgers only - item-health, host-fingerprint, scores, span-rollup, and this row's summaries. **Traces are excluded**, and the scope-out table says why |

### C4 - The five names the site inlines (row 5)

Three import lines, five names. **Two of the five are runtime values, not types, and they are the reason this row is not a straight delete.**

| Name | Kind | Read at | Goes to |
| --- | --- | --- | --- |
| `ConsolePanelGroup` | type | `frontend/src/lib/server/config.ts:24`, re-exported at `:307` | `config.ts`, where it is already re-exported |
| `HostFingerprintRow` | type, 28 fields, used as `Required<...>` | `host-fingerprint.ts:53` | `host-fingerprint.ts`. A field dropped in the inline is a field the reader silently stops populating, so it is copied whole and diffed field by field |
| `ServerJob` | type | `host-fingerprint.ts` | `host-fingerprint.ts` |
| `SERVER_JOB` | **runtime array** | `SERVER_JOB.find()` at `host-fingerprint.ts:75` - a membership filter over CSV cells | `host-fingerprint.ts`. A value outside the copy becomes `null` and the row is dropped |
| `WATCHED_FLAG` + `WatchedFlag` | **runtime array** | `watchedFlags()` at `host-fingerprint.ts:162` - drives the chips a machine card draws | `host-fingerprint.ts` |

**Each of the two runtime arrays gets one binding test**, a backend contract test that reads the TypeScript literal and compares it to the Pydantic enum. That pattern is already in this repository at `backend/tests/contracts/_config.py:29`. It is not generation: it is two declarations with one gate, and it is what stops the drift `host-fingerprint.ts:19-23` says once carried a missing flag for a month.

### C5 - What stays in the contract base (row 5)

**Deleting the wrong half of `backend/idhazh/contracts/base.py` breaks every persisted payload in the repository.**

| Part | Verdict | Why |
| --- | --- | --- |
| `json_schema()` L740-758, `schema_text()` L761, `schema_filename()` L736 | **Goes** | Writes and names a schema document |
| `__changelog__`, `ChangelogEntry` L643, `schema_version()` L732 | **Stays** | `schema_version()` returns `__changelog__[0].version` and more than thirty production call sites stamp with it - `Article` at `extract.py:96`, `EvalRow` at `evals/score.py:175`, `RunPlan` at `stages/plan.py:396`. Only `ChangelogEntry.why` is deletable |
| `version` field L710, `_stamp_current_version` L724 | **Stays** | Every persisted payload carries it |
| `read()` L769-807, `StalePayloadError` L651 | **Stays** | It is what lets a reader say "written under an older build" instead of "malformed" |
| `__pydantic_init_subclass__` L713-722 | **Stays, both halves** | The newest-first check is what makes `[0]` mean newest |
| `__schema_stem__` | **Stays as a runtime identifier** | `contracts/console_payloads.py:173` keys a dict on it, and it is the fixture directory name via `backend/tests/contracts/_fixtures.py:24` |
| `Model` L608, `without_retired_keys` L614 | **Stays** | `extra="forbid"` is the validation |
| **`CONTRACTS`, the list at `contracts/export.py:24-166`** | **Moves to `contracts/__init__.py`** | `_fixtures.py:17` builds `BY_STEM` from it. Delete `export.py` whole and the fixture round-trip test - the one thing proving every contract still loads - loses its map. Only `export()`, `export_typescript()`, `expected_filenames()` and `main()` are deleted |
| `backend/idhazh/contracts/derived.py` | **Untouched** | It holds three plain models and two validators and writes no schema. Plan 39 row 1 named it in error |

### C6 - The engineering contract after row 6 (row 6)

**Plan 41 row 6 already owns Guardrail #3 and section 11. Row 6 does not restate either.** Plan 39's clause table quotes the text on main today, and applying it verbatim after plan 41 merges silently reverts plan 41's amendment - with nothing red anywhere, because no gate reads CLAUDE.md.

| Clause | After |
| --- | --- |
| Section 1a, second bullet | Deleted. Nothing generates and nothing drifts |
| Section 9, the drift-gate line | Deleted from the Definition of Done |
| Section 10, hand-editing a generated artifact | Deleted - there are none |
| `AGENTS.md` | The three phrases saying contracts are generated from the models, named in section 7 and removed |
| Guardrail #3, section 11 | **Not row 6's.** Plan 41 row 6 owns both. Row 6's oracle checks the tree, not this table |

**Guardrail #11 and Guardrail #12 are untouched.**

## Section 2 - Row 1 - The replay count leaves the dispatch surface

- **Scope:** Delete the `repeats` dispatch input from the qualification workflow and read the count from config instead. The loop, the gates, the diagnostics and every persisted shape are untouched.
- **Files touched:**
  - `.github/workflows/validate.yml` (the input at L48-49, the `REPEATS` environment variable at L186, the range check at L190-193)
  - `backend/idhazh/contracts/knobs/run.py` (the new `qualification_repeats` knob)
  - `config/idhazh.json`
  - `backend/idhazh/cli.py` (`--repeats` default comes from config)
  - `backend/tests/workflows/test_bench_input_drift.py`
  - `docs/how-to/evaluate-new-summarizer-model.md` - **the runbook carries `-f repeats='3'` at L612 inside the documented qualify dispatch. Plan 39 row 7 did not list this file, and it is the page a person opens to qualify the next model.**
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'qualif or workflows' -q`; CI - full suite.
- **Oracle:** the documented dispatch command in `docs/how-to/evaluate-new-summarizer-model.md` runs against the changed workflow without an unknown-input error, and a qualification run started from the committed config does the same number of passes it does today. Both can fail. ESCALATE trigger 1 applies.
- **What this row does not do, and why it matters:** it does not reduce the work a shard does. `backend/idhazh/stages/qualify.py:554` stamps `elapsed_seconds` before the loop, `qualify_decide.py:58` takes the maximum across shards, and `evals/qualify.py:467` compares that against a fixed `job_budget_minutes`. Any change to the pass count is a change to what that gate means.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The input is deleted, not defaulted. A knob nobody should raise is a knob somebody will | Fowler |
 | 2 | The loop stays. Three of the ten gates read properties of the sampled output, so passes are draws, not repetition | Andre |
 | 3 | `wording_spread` stays. It is the only witness to llama.cpp returning a different numeric path for the same prompt and seed after a build bump or a change to `n_parallel`, `flash_attention` or `cache_type_k`. `backend/idhazh/fingerprint.py:163` already names that mechanism. Nothing else in the repository sees it | Andre |
 | 4 | `determinism_violation` stays a column something can set. A production run structurally cannot set it, so qualification is the only place it can move, and it reaches day metrics, the run record, the console and the fine-tuning corpus filter | Andre |
 | 5 | The runbook is in the file list. A documented command that fails on an unknown flag is the defect this row would otherwise ship | Andre |

## Section 3 - Row 2 - The utilities with no caller go, and the search evaluation is bounded

- **Scope:** Delete the command-line utilities the census finds unreferenced, delete the human-label path while keeping its sampling design, and bound the one session fixture that reads a growing collection.
- **The census is the row's first commit, not its last.** Run it before each deletion, over `backend/`, `.github/`, `docs/`, `frontend/` and `notebooks/`. A utility named only in a runbook still has a user.
- **The ten, measured 2026-09-21:**

 | Utility | Lines | Reference today | What the deletion owes |
 | --- | --- | --- | --- |
 | `backfill_day_metrics` | 73 | none | nothing |
 | `measure_definition_placement` | 264 | none | nothing |
 | `scan_reference_articles` | 301 | none | nothing |
 | `index_sizing` | 518 | `docs/archive/measurements-2026-08.md` | the doc line that names the script loses the name, keeps the finding |
 | `measure_day_window` | 283 | `docs/reference/benchmarks/day-window-read.md` | same |
 | `measure_declared_wholes` | 659 | `docs/reference/benchmarks/articles-that-state-a-whole.md` | same |
 | `measure_probability_mode` | 245 | `docs/reference/benchmarks/which-probabilities-the-server-returns.md` | same |
 | `prune_artifacts` | 194 | `docs/architecture/publishing/retention.md` | same |
 | `token_budget` | 215 | `docs/concepts/config.md` | same |
 | `migrate_item_health` | 78 | `docs/architecture/contracts/schemas.md` | that page is deleted by row 5, so this reference clears itself |

- **Files touched:**
  - the ten above, and their tests where one exists
  - `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/utilities/label_queue.py` and their tests
  - `backend/tests/test_retrieval_eval.py` (the session fixture at L250 and the archive-walk test at L279)
  - `tests/fixtures/search/` (the new bounded corpus)
  - `docs/concepts/evaluation.md`, and each doc page named above
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite.
- **Oracle:** every deleted module has no importer and no invocation, established by census **before** each deletion; and the retrieval evaluation runs to a verdict with no file outside `tests/fixtures/` opened. The second half can fail and is the point of the row.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A one-shot measurement utility retires once its answer is written down. The doc keeps the finding and loses the script's name in the same commit | Fowler |
 | 2 | **`backend/utilities/plan_status.py` is not deleted.** Plan 39 row 17 named it. It is invoked at `.github/workflows/ci.yml:292` with `--write` and `AGENTS.md:65` names it as the generator of `TODO/STATUS.md`, which exists because "a list somebody retypes is a list that rots". It has no importer, so an import-only census would delete it and the pull request would still be green - `pytest` never runs a workflow | Fowler |
 | 3 | **`backend/idhazh/evals/retrieval.py` is not deleted.** The growing read is `backend/tests/test_retrieval_eval.py:250`, a session fixture; every other test in that file already builds a bounded corpus. The module is the only instrument that would see a similarity floor moved by 0.05 turning six search results into two | Andre |
 | 4 | The bound is a committed fixture corpus of the gold days the fifty queries answer, under `tests/fixtures/search/`, beside the query set already committed there at 42,052 bytes. `test_every_labelled_answer_is_still_in_the_archive` at L279 is deleted outright - it goes red because somebody published a day, which CLAUDE.md section 13 forbids by name | Andre |
 | 5 | The human-label path goes: zero committed rows, and CLAUDE.md section 1a now makes LLM-as-judge primary evaluation. **Its sampling design moves into a `## Design rationale` section in `docs/concepts/evaluation.md` in the same commit** - the shuffle that needs no seed and stays reproducible, and the procedure. This repository force-pushes its history away on a schedule, so a design that lives only in a deleted file's history is gone | Andre |
 | 6 | The five demoted qualification diagnostics stay. The scope-out table says why | Andre |

## Section 4 - Row 3 - The pipeline test commits what it produced

- **Scope:** Give the pipeline-test workflow write permission and a committed day ledger carrying every case's summary and the bytes the model read, and make the nightly prune able to find it.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml` (`contents: write`, a `destination` dispatch input, a commit step)
  - `backend/idhazh/ledger.py` (the collection and its columns)
  - `backend/idhazh/stages/record.py` (the write, behind a set destination)
  - `backend/idhazh/cli.py` (the marker, written by the redirect at L510-523)
  - `backend/idhazh/retention.py`, `backend/idhazh/stages/prune_state.py` (discovery by marker)
  - `backend/idhazh/contracts/knobs/retention.py`
  - `config/idhazh.json`
  - `backend/tests/workflows/test_staged_paths.py`, `test_validation_state_root.py`, `backend/tests/test_ledger.py`, `backend/tests/retention/`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'state or ledger or record or retention' -q`; CI - full suite, and one real dispatch watched to completion before the row closes.
- **Oracle:** a three-case dispatch writes **six rows** - one per case per article - all inside the run's own destination and none outside it; and a nightly prune run against a tree whose marker is older than the window removes it. Both can fail, and the first is what plan 39's design got wrong. ESCALATE trigger 2 applies.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A producer commits what it produces. No census of who reads it | Owner ruling 2026-09-21 |
 | 2 | **A day file, not a day directory.** A day directory is sized by `inventory.files()` with `stat().st_size` on a directory and reported as the file's bytes, and is refused by `day_partition.day_files` inside the nightly prune. It is the first store in the repository that would break the shape, and the instrument lies rather than errors | Carmack |
 | 3 | **The case is in the key and in the record.** Three cases share one plan, one date and the same two item ids, so without it the third case silently overwrites the first two - and the third case is the two-slot restart, the one whose batch split most plausibly decodes differently | Carmack |
 | 4 | **The bytes the model read are committed, not just their digest.** Two of five articles moved under their own address inside one job, on both of two dispatches. A digest detects divergence; it does not let a person read | Andre |
 | 5 | Per-key replacement comes from `ledger.keyed_paths`, which already exists. Plan 39's "one file an article" reinvented it and broke three readers doing so | Carmack |
 | 6 | **The retention window is a mechanism, not a comment.** The nightly run's config sets `trial_state_dirname` to `null`, so the trial pruner returns on its first line every night. Discovery moves to a marker file the tree carries - C3 | Carmack |
 | 7 | Traces are not committed under a trial tree. The scope-out table says why | Carmack |
 | 8 | Production is never touched. The nightly run leaves the destination unset | Fowler |
 | 9 | `contents: write` on a workflow that reads the open web in the same job is named, not assumed. It is the same posture the qualification workflow already holds, and nothing fetched reaches a path, an argument or a URL (Guardrail #11) | Carmack |

## Section 5 - Row 4 - Nine console specs visit every route the site serves

- **Scope:** Correct the nine hand-written console route lists so each visits all five routes the site serves.
- **Files touched:** `frontend/tests/console-axis.spec.ts:29`, `console-chrome.spec.ts:30`, `console-model-rule.spec.ts:133`, `console-nav.spec.ts:37`, `console-polarity.spec.ts:33`, `console-readout.spec.ts:23`, `console-title.spec.ts:48`, `console-voices.spec.ts:27`, `console-window-claims.spec.ts:57`
- **Acceptance gates:** local - `npm --prefix frontend run test:browser -- --project console`; CI - full suite.
- **Oracle:** every console route the site serves is visited by every spec that claims to cover all of them. **This fails on the base tree today**, which is the defect: the site serves five console routes and these specs list three, three, three, four, four and five, so `/console/judgement/` is visited by none of the multi-route specs.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The lists stay nine and stay hand-written. `frontend/src/lib/console/band.ts:131-133` records the ruling: the navigation spec types them out "on purpose - that copy is what the owner chose and reading it from here would only prove the page agrees with itself" | Owner, quoted in the code |
 | 2 | The row fixes the hole it finds rather than preserving it. A spec that claimed to cover every route and missed one was not covering anything | Susan |
 | 3 | The cost is named and accepted: adding a console route stays nine test edits. Changing that is a separate question and a smaller one than plan 39 asked | Fowler |

## Section 6 - Row 5 - The generated contract layer goes

- **Scope:** Delete every generated JSON schema and every generated TypeScript contract, the two generators, the drift tests and the continuous-integration job that ran them, after inlining by hand the five names the site uses and giving each closed vocabulary one binding test.
- **The case for this row is reviewer attention, not runtime.** The drift gate costs 1 second on the runner across four measured runs, the layer publishes zero bytes, and it is 1.1 percent of the pack. What it costs is that about one commit in six in this repository has carried a regenerated diff a reviewer scrolled past, and that the generator runs in full to serve four types out of sixty-six.
- **Files touched:**
  - `schemas/` (all 66), `frontend/src/contracts/` (all 66)
  - `backend/idhazh/contracts/export.py` (only `export()`, `export_typescript()`, `expected_filenames()`, `main()` - `CONTRACTS` moves to `contracts/__init__.py`), `contracts/typescript.py`, `contracts/base.py` (C5)
  - `backend/tests/contracts/test_schema_drift.py`, `test_typescript_contracts.py`, `test_cell_shapes.py`
  - **the six backend modules that read the deleted directory, which plan 39 row 1 did not name:** `test_article_and_eval.py:149`, `test_closed_vocabularies.py:53`, `test_run_timeline.py:187`, `test_stamped_boundary.py:186`, `_config.py:29`, and `test_sources_and_marks.py:174` - **that last one spells `REPO_ROOT / "schemas"` directly, so a census on `SCHEMAS_DIR` misses it**
  - `backend/tests/conftest.py:41` (the `SCHEMAS_DIR` constant)
  - **the eight frontend specs that read by path, which plan 39 row 1 did not name:** `console-machine-cards.spec.ts:132` and `:260`, `console-machine-panels.spec.ts:28`, `console-model-instruments.spec.ts:45`, `console-model-reasons.spec.ts:39`, `prompt-reuse.spec.ts:198`, `settings-moved.spec.ts:189`, `processor-lost.spec.ts:163`. **Three of those read at module scope, so one missing file takes the whole file down rather than failing one test**
  - `frontend/scripts/run-checks.ts:310`, `frontend/scripts/test-scope.ts:169`, `frontend/scripts/tests/test-scope.test.mjs` (four lines), `frontend/scripts/copy-visuals.mjs:52` (a comment)
  - `frontend/src/lib/server/config.ts`, `frontend/src/lib/server/host-fingerprint.ts` (the inlines, C4)
  - `.github/workflows/ci.yml` (the drift job), `pyproject.toml:170` (`idhazh-export-schemas`)
  - `docs/architecture/contracts/schemas.md` (deleted)
- **Acceptance gates:** local - `npm --prefix frontend run check`, `npm --prefix frontend run test:changed -- --list` then the selected checks, `python -m pytest backend/tests/contracts -q`; CI - full suite and the browser smoke. ESCALATE triggers 3 and 4 apply.
- **Oracle:** the five inlined names are compared to the generated ones field by field and value by value **before** the deletion; the site compiles and every route renders with no generated file present; and each closed vocabulary's binding test fails when one value is removed from either side. The last clause is the one that can fail for a reason worth catching.
- **The green-suite traps, named so a worker looks for them:**

 | Trap | What happens |
 | --- | --- |
 | Three surviving tests are parametrized over a glob of the deleted directory | They pass with **zero cases** rather than fail. The check is a comparison of collected test counts before and after, not pass or fail |
 | `backend/tests/contracts/_config.py:29` asserts every mention of a name is on a list of survivors | Deleting `frontend/src/contracts/eval-row.ts` **removes a mention**, so the subset assertion still holds and the test stays green pointing at a file that no longer exists |
 | `frontend/tests/processor-lost.spec.ts:163` parses `frontend/src/contracts/item-health-row.ts` as a file | It imports `SERVER_JOB` from `host-fingerprint.ts` instead |
 | `SERVER_JOB` and `WATCHED_FLAG` are copied into the site | Without a binding test each, two hand copies exist with nothing comparing them - the exact drift `host-fingerprint.ts:19-23` says once carried a missing flag for a month |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The layer is deleted whole rather than pruned to the used files. 62 of 66 have no importer, and a generator kept for four types is a generator | Owner ruling 2026-09-21 |
 | 2 | The Pydantic models stay. They are the validation; the schemas were a copy of them in another notation | Fowler |
 | 3 | The drift gate goes with the artefacts. It checked that a generated file still matched the thing that generated it, which is a loop | Fowler |
 | 4 | **`docs/architecture/contracts/schemas.md` is deleted, not refreshed.** The agent bootstrap routes to it, so the next agent reading a page titled for schemas builds what it describes. This is the single most likely way the whole layer returns | Fowler |
 | 5 | **`CONTRACTS` is re-homed, not deleted.** `backend/tests/contracts/_fixtures.py:17` builds `BY_STEM` from it, so deleting `export.py` whole costs the fixture round-trip test its map - and that test is the one thing proving every contract still loads | Fowler |
 | 6 | **`derived.py` is untouched.** It writes no schema. Plan 39 named it in error | Fowler |
 | 7 | The prose requirement on every contract dies with its consumer: it is copied into the generated schema and nowhere else. The version stamp and the changelog stay - `schema_version()` reads `__changelog__[0]` and more than thirty production call sites stamp with it | Fowler |
 | 8 | Each closed vocabulary keeps one binding test. Two declarations with one gate is not generation, and it is cheaper than the drift the row otherwise buys | Fowler |

## Section 7 - Row 6 - The engineering contract and the pages catch up

- **Scope:** Amend the clauses of the engineering contract this plan contradicts that plan 41 does not already own, and refresh every page whose description of the contract layer or the qualification surface is now wrong.
- **Files touched:** `CLAUDE.md` (section 1a second bullet, section 9's drift-gate line, section 10's hand-editing line), `AGENTS.md`, `docs/reference/ci-model-runtime.md`, `docs/architecture/contracts/determinism.md`, `docs/concepts/evaluation.md`, `docs/reference/repository-layout.md`, `docs/how-to/run-the-gates.md`, `TODO/STATUS.md`
- **Acceptance gates:** `python backend/utilities/doc_load.py` before and after, and the split test on any page gaining a section. No application suite is required for a documentation-only closure. ESCALATE trigger 5 applies.
- **Oracle:** no clause of the engineering contract requires a generated artefact, a schema file, or a drift gate - **checked clause by clause against the tree after plan 41 has merged, not against this plan's table.** That is what stops this row reverting plan 41.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The amendment ships with row 5, not after it. CLAUDE.md section 0 requires a conflicting rule to be amended in the same change | Owner, CLAUDE.md section 0 |
 | 2 | **Row 6 does not restate Guardrail #3 or section 11.** Plan 41 row 6 owns both. Plan 39's clause table quotes the text on main today, and applying it verbatim after plan 41 merges reverts plan 41 - cleanly, with nothing red, because no gate reads CLAUDE.md | Fowler |
 | 3 | Each guardrail that moves records who moved it and when, on the line that moved (CLAUDE.md section 1) | Fowler |
 | 4 | Guardrail #11 and Guardrail #12 are untouched | Fowler |
 | 5 | The three phrases in `AGENTS.md` that say the contracts are generated from the models are named and removed. An unnamed amendment is one nobody checks, and agent tools read that file instead of the engineering contract | Fowler |

## Section 8 - Row 7 - The dependency's beneficiary line says what it buys

- **Scope:** Correct the one dependency whose declared beneficiary its own code says it does not deliver.
- **The finding:** `pyproject.toml:162` declares the `langfuse` extra's beneficiary as "the nested span view". `backend/idhazh/telemetry/sinks.py:152` says in its own docstring: "It does not reproduce the nesting on the host." Guardrail #8 requires a dependency to name its beneficiary feature, and this one names a feature it does not provide.
- **Files touched:** `pyproject.toml` (the comment above the extra), `docs/concepts/telemetry.md` if it repeats the claim.
- **Acceptance gates:** none beyond the documentation load check. This is a comment.
- **Oracle:** the beneficiary line and the sink's docstring describe the same capability. Read both.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The line is corrected to what the sink delivers - one flat trace an item on a named host - rather than deleted. A dependency with no beneficiary named is one nobody can later argue to remove | Carmack |
 | 2 | **The dependency itself stays.** The scope-out table says why, and the reason is a person's ruling with a date on it | Owner, `docs/concepts/telemetry.md:553` |

## See also

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - the parent, whose rows 1, 7, 8, 12, 17 and 19 this plan carries and whose row 15 it refuses.
- [`20260921-41-lane-a-model-file-plan.md`](20260921-41-lane-a-model-file-plan.md) - owns Guardrail #3 and section 11; merges before row 6.
- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the workflows.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.
