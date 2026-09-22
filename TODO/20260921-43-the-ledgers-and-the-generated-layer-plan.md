# The ledgers, the evaluations, and the generated layer

**Last Updated**: 2026-09-22

**Level**: 5. Row 5 deletes the generated contract layer whole and row 6 amends the engineering contract that requires it. Row 3 mints two persisted contracts. Those three PAUSE for the owner before their pull request opens. Rows 1, 2 and 7 are Level 2 or 3 and run AUTO once the user authorizes. Row 4 is DONE.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight - one, because no two remaining rows are ready at the same time and a second branch buys a 479 s gating wait it cannot use; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 39 split into lanes; plans 41 and 42 took the model file and the workflows and have both closed, and this is the rest. Three of its remaining rows were wrong as written - one cuts the work a budget gate measures without moving the gate, one deletes 539 lines of search evaluation to fix two lines in a test, and one writes a day directory into a tree whose three readers all expect a day file. Two more overturn rulings a person already made and wrote down. What survives is corrected here, with the file lists and the field-level shapes the original rows were missing. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| The second rule | **An instrument is not scaffolding.** A thing that measures what nothing else measures stays, however large and however few gates read it. The test is what goes blind when it leaves, and each row answers it. |
| The measure | **Edits per future change, and reviewer attention per commit.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Take the replay count off the dispatch surface and leave the loop three gates draw from. Delete the three spent utilities and the human-label path, and bound the search evaluation's one growing read instead of deleting the evaluation. Give the pipeline test a committed day ledger carrying every case, its summary and the bytes the model read, folded to one line, discoverable by the nightly prune. Delete the generated contract layer whole, inlining five names by hand and binding each closed vocabulary with one test. Amend the nine engineering-contract clauses that still require a generated artefact. Delete the hosted span sink. **Row 4 - nine console specs visiting all five routes - landed in #1040.** |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 39 rows 1, 7, 8, 12, 17 and 19. **Plan 39 row 15 is no longer refused** - owner approval 2026-09-22 reversed the ruling at `docs/concepts/telemetry.md:553`, and row 7 carries it. |
| Assumes | **Plan 41 merges before row 6 starts** - plan 41 row 6 rewrites Guardrail #3 and section 11, and row 6 must amend the text plan 41 leaves, not the text on main today. **Plan 41 merged on 2026-09-22 in #1036 and #1044, so this is satisfied; row 6 is written against `CLAUDE.md` as it stands.** **Row 3 assumes nothing from [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) and owes it nothing.** Plan 46 row 4 converts the six segment-fed head ledgers named by `SegmentLedger` at `backend/idhazh/ledger.py:1658`, and its own row 3 says `day_files` is untouched; row 3's ledger is appended through `extend_ledger_file`, never folded, so it is one of the nine day-file ledgers plan 46 leaves as they are. Measured 2026-09-22: 14 day-file ledger roots under `state/`, five of them heads. The two plans may run in either order. Rows 1, 2 and 7 assume nothing. |
| ESCALATE triggers | (1) Row 1 must not change what the BUDGET gate measures. If the work a qualification shard does per dispatch changes at all, stop. (2) Row 3 mints two persisted contracts and a committed collection. If the nightly prune cannot discover the tree by the marker in C4, stop - **and the oracle drives the missing-marker case as well as the present-marker case, because a tree with no marker is never enumerated and nothing goes red.** **If `seen_text` or `summary` reaches a committed cell carrying a newline, stop**: `ledger.drop_repeated_rows:2217` states that no cell in these contracts can carry one, and `settle_header:1083` and `migrate_header:1024` read by line on the same assumption. (3) Row 5 deletes the artefacts a drift gate protects. If the five inlined names cannot be proved identical to the generated ones before the deletion, stop. (4) Row 5 turns two closed vocabularies from generated into hand-written. Each ships its binding test in the same commit or the row stops. (5) Row 6 amends the engineering contract; it lands in the same pull request as row 5, never after. (6) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Three pull requests, run one at a time. P2 carries rows 2 and 7 - both pure deletion, no shared file, no dependency, two commits in one branch so the span-sink removal is readable on its own. Fowler rules the contracts, the test tiers and the module structure; Andre the evaluation integrity; Carmack the ledger shape and the prune path. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 - no two remaining rows are ready together, so a second worker would idle.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Cutting qualification to one pass per article** (plan 39 row 7's scope) | About 180 lines stay, and a dispatch keeps costing what it costs | **Refused as written; a gate nobody checked is the reason.** `elapsed_seconds` is stamped before the repeat loop (`backend/idhazh/stages/qualify.py:554`), so it spans all three passes, and `BUDGET` divides it by 60 (`stages/qualify.py:580`) against a fixed `job_budget_minutes` (`backend/idhazh/evals/qualify.py:454-463`). Three passes to one drops the measured side about two thirds while the bound does not move: a candidate roughly 2.9x slower per item passes the only gate reading Guardrail #2, and every past BUDGET verdict stops comparing with every future one. Three more gates - `REASONING_LEAKAGE`, `SCHEMA_VALIDITY`, `PUBLISHABLE_LENGTH` - read properties of the sampled output at `temperature: 0.2`, so 90 draws become 30 and detection of a one-in-fifty schema failure falls from about 84 percent to about 45. **What brings it in:** one commit that moves `job_budget_minutes` to the one-pass equivalent, records in `docs/concepts/evaluation.md` that the margin no longer compares across the change, and accepts losing `wording_spread` and a movable `determinism_violation`. That is a measurement decision and it is the owner's. Andre and Carmack, independently |
| **Deleting `backend/idhazh/evals/retrieval.py`** (plan 39 row 17 decisions 3 and 6) | 539 lines stay | **The premise is wrong twice.** The growing walk is `backend/tests/test_retrieval_eval.py:250`, a session fixture; every other test in that file already builds a bounded corpus. And the replacement plan 39 promised is already committed at `tests/fixtures/search/retrieval-queries.json`, 42,052 bytes, at least 50 queries with two gold answers each. Deleting the module leaves `frontend/tests/search.spec.ts:122`, a five-query wiring check whose own file computes its standard error at 0.18 against 0.057 at fifty - a ten-point recall drop is invisible to it. Row 2 bounds the fixture instead. Andre |
| **Reading the console route list from the site's own source** (plan 39 row 19 decision 2) | Adding a console route stays nine test edits | **Refused as written; the defect it found is kept.** `frontend/src/lib/console/band.ts:131-133` records the ruling in the code: "`console-nav.spec.ts` types them out a third time on purpose - that copy is what the owner chose and reading it from here would only prove the page agrees with itself." **What brings it in:** the owner relaxing that ruling for the eight specs that do not test the strip - a smaller question than plan 39 asked |
| **Deleting the five demoted qualification diagnostics** (plan 39 row 17 decision 4) | Seven diagnostic lines stay on the report | **Refused.** Plan 39 never named the five, so the clause cannot be reviewed against anything. Four candidates each witness a failure no gate catches: `unsupported_numbers` is the only witness to a fabricated figure, the one summary error a reader acts on; `hedge_dropped` the only witness to "reportedly" becoming assertion; `extractiveness_mean_non_brief` the only counterweight to the faithfulness floor on the long path, because `BRIEF_COPYING_CEILING` gates brief items only; `below_lead_coverage_min_share` the only witness to a model summarising paragraph fourteen. A number with no bar is still what a person reads when a gate passes and the output still looks wrong. Andre |
| **Teaching `day_partition.day_files` to accept a `.jsonl` day** | A trial tree may not commit traces, so row 3 commits the CSV ledgers only | `backend/idhazh/day_partition.py:96` refuses anything that is not a two-digit `.csv` day file, and `retention.prune_trial_state:1478` walks through it. Committing `state/<trial>/traces/YYYY/MM/DD-N-S.jsonl` would raise `ValueError` inside the nightly prune step. A real latent defect that predates this plan, and one row in its own right. Row 3 routes around it rather than arming it. Carmack |
| **Splitting the two largest console specs** | `console-machine-data.spec.ts` at 58,345 bytes and `console-machine.spec.ts` at 43,215 bytes keep answering several questions each | A different question - one file answering many - and its own structural pull request. One addition buys one cut. Fowler |

### What a change costs today

Measured on `origin/main`, 2026-09-22, except where a line says estimate.

| Reading | Value | Where |
| --- | --- | --- |
| Generated JSON schema | **65 files, 23,582 lines** | `schemas/` |
| Generated TypeScript | **65 files, 9,218 lines** | `frontend/src/contracts/` |
| Import statements in the whole site reaching any of it | **3, in 2 files, pulling 5 names** | `frontend/src/lib/server/config.ts:24`, `host-fingerprint.ts:33-38` |
| Of those five, how many are runtime values rather than types | **2** - `SERVER_JOB` (6 values) and `WATCHED_FLAG` (12 values) are arrays a filter reads | `host-fingerprint.ts:75`, `:162` |
| Generated TypeScript files with no importer | **62 of 65** | derived |
| Commits on `HEAD` that rewrote a generated file | **370 of 2,280 - about one in six** | 344 on `schemas/`, 26 on `frontend/src/contracts/` |
| What the drift gate costs on the runner | **1 s, four runs, zero spread** - under 1.5 percent of the job step it sits in | runs 35660527882, 35658298924, 35657840521, 35657514579 |
| What the generated layer costs the published site | **zero bytes** - Vite tree-shakes all 66 out; the built site is 70,005,963 B against a 1 GB ceiling | committed `frontend/build/` |
| Bytes the layer adds to the repository | 1,592,293 - **1.1 percent** of a 137.46 MiB pack | measured |
| Files reading the generated directories by **path** rather than by import | **8 frontend specs, 4 tooling lines, 6 backend modules** - plan 39 row 1 named none | section 6 |
| Of those eight specs, how many read at **module scope**, so one missing file takes the file down | **1** - `console-machine-panels.spec.ts:28`. The other two an earlier draft named, `console-model-instruments.spec.ts:45` and `console-model-reasons.spec.ts:39`, are `resolve()` calls that never throw; their reads are at `:56` and `:253`, inside tests | section 6 |
| Utilities with **no textual reference anywhere** outside `backend/utilities/` | **3 of 68**, 637 lines | section 3 |
| Utilities referenced **only by a `docs/` page** | **7**, 1,761 lines | section 3 |
| Utilities plan 39 row 17 claimed had no code reference | **11** - the census says 3 | census 2026-09-21 |
| `backend/utilities/plan_status.py` | **1,204 lines, and nothing calls it.** The CI job that ran it was deleted on 2026-09-22 (owner ruling) because a page generated from every plan at once conflicted on every open branch | it stays on disk as an operator surface |
| Console routes the site serves | **5** | five `+page.server.ts` under `frontend/src/routes/console/` |
| Console specs hand-writing a route list | **9 of 62** | section 5 |
| Console routes visited by **none** of those nine | **0, since #1040 merged.** It was 1 - `/console/judgement/` - when row 4 was written, which is why row 4 exists | row 4, DONE |
| Articles one pipeline-test dispatch summarises | **2, across 3 cases**, one plan, one date, the same two item ids | `config/pipeline-tests.json:2`; `.github/workflows/idhazh-pipeline-tests.yaml:300`, `:311`, `:370` |
| What a commit step costs that workflow | **about 3 s against a 140-minute bound - 0.04 percent** | neighbours in run 35625832336: small payload 2 s, whole digest day 16 s; estimate |
| What a dispatch commits | **39 KB typical, 63 KB when both drawn articles sit at the 90th percentile, 188 KB worst case** - six rows, three cases over two articles, each body written three times. Measured across 1,490 corpus bodies: body median 3,712, mean 4,559, p90 8,542, max 29,294 characters; summary mean 1,287; the other 13 columns about 650 a row | `corpus/corpus.jsonl`, 2026-09-22 |
| What that costs the repository | **Bounded at about 90 days of dispatches, not a year.** `retention.trial_state_days` = 90 bounds the working tree; `finetune.prune_keep_days` = 60 with `prune_every_days` = 30 is what bounds the pack, because deleting a file does not delete its history. At one dispatch a day that is 3.5 MB of working tree and roughly 1.2 MB of pack in steady state, against a 142.38 MiB pack - under 1 percent. **The dispatch rate is an estimate**: five dispatches exist, all on 2026-09-15 | `config/idhazh.json`; `git count-objects -vH` |
| What it costs the published site | **Zero.** `state/` ships no bytes to `frontend/build`, which stands at 70,005,963 B against the 1 GB Pages cap | `idhazh site-weight` |
| Post-sanitizer bodies that contain a newline | **1,490 of 1,490 - 100 percent.** 454 of 1,490 also contain a double quote. `drop_repeated_rows`, `settle_header` and `migrate_header` all read these files with `readlines()`, which is why C2 folds two columns to one line | measured 2026-09-22 |
| What one more pull request costs, at `Parallel N = 1` | **one 479 s gating wait** - a code-carrying CI run, spread 456-518 s over 6 runs - **plus one merge turn and one local gate pass at 452-1,098 s** on a developer box | `gh run list --workflow=ci.yml` |
| Articles that moved under their own address inside one job | **2 of 5, on both of two dispatches** | `docs/how-to/evaluate-new-summarizer-model.md:549` |
| What `_prune_trial_shards` prunes today | **nothing, ever** - it returns at `backend/idhazh/stages/prune_state.py:394` because the nightly config sets `trial_state_dirname` to `null` | `config/idhazh.json:306` |

## Section 0b - What this plan does, in one list

1. Take the replay count off the dispatch surface. It becomes a config value; the loop is untouched.
2. Delete the three utilities whose work is finished and the human-label path, bound the search evaluation's one growing read, and record the rule that keeps an instrument a page cites.
3. Give the pipeline test a committed day ledger: one row per case per article, carrying the summary and the bytes the model read, folded to one line, discoverable by the nightly prune.
4. Make all nine multi-route console specs visit all five routes the site serves. **DONE, #1040.**
5. Delete the generated contract layer whole, inlining five names and binding two vocabularies.
6. Amend the nine engineering-contract clauses that still require it, and the fourteen instructions in code and docs that still say generate.
7. Delete the hosted span sink, its optional dependency and its two callers, keeping the committed local trace file.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Pull request | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The replay count leaves the dispatch surface | - | P1 | PENDING | - | - | - |
| 2 | The spent utilities go, and the search evaluation is bounded | - | P2 | PENDING | - | - | - |
| 3 | The pipeline test commits what it produced | 1 | P1 | PENDING | - | - | - |
| 4 | Nine console specs visit every route the site serves | - | - | DONE | p43r4 | #1040 | R4 |
| 5 | The generated contract layer goes | 1, 2, 3, 7 | P3 | PENDING | - | - | - |
| 6 | The engineering contract and the pages catch up | 5 | P3 | PENDING | - | - | - |
| 7 | The hosted span sink goes | - | P2 | PENDING | - | - | - |

**Row 4 delivered five of the nine lists, and the other four were already whole.** Its oracle - every route visited by every spec that claims all of them - is not reached, and the reason is a defect the widening found: `console-chrome.spec.ts` and `console-readout.spec.ts` leave `/console/judgement/` and `/console/voices/` out, so the rule those two files enforce covers three of the five pages a reader can open. **That defect is now `TODO/20260922-45-the-readout-covers-every-console-route-plan.md` and is no longer unclaimed.** Plan 45 also corrects what the note here and both spec headers said about the two routes. Judgement draws five charts and two of them already print a strip, so the gap there is the other three declaring nothing. Voices draws one chart, `SourceCutRange`, and it already declares a reason - so the fix on that route was never a missing strip, and it stays out of both chart specs because its chart has no column two marks share.

### Section 1a - The three pull requests and the files each owns

**One worker, one branch at a time.** The file lists below are what a reviewer sees in one diff, not a parallelism plan.

| PR | Rows | Kind | Files it owns |
| --- | --- | --- | --- |
| **P1 - the qualification surface and the new ledger** | 1, 3 | behavioural | `backend/idhazh/contracts/knobs/run.py`, `knobs/retention.py`, `contracts/pipeline_test_summary.py` (new), `contracts/trial_state_marker.py` (new), `contracts/export.py` (two entries), `backend/idhazh/cli.py`, `ledger.py`, `retention.py`, `stages/record.py`, `stages/prune_state.py`, `config/idhazh.json`, `.github/workflows/validate.yml`, `.github/workflows/idhazh-pipeline-tests.yaml`, `schemas/pipeline-test-summary.schema.json` and `schemas/trial-state-marker.schema.json` (new), the two matching files under `frontend/src/contracts/` (new), `tests/fixtures/contracts/pipeline-test-summary/` and `tests/fixtures/contracts/trial-state-marker/`, `backend/tests/test_ledger.py`, `backend/tests/retention/`, `test_staged_paths.py`, `test_validation_state_root.py`, `docs/how-to/evaluate-new-summarizer-model.md`, `docs/reference/repository-layout.md` |
| **P2 - the deletions** | 2, 7 | structural, **two commits**: the utilities and the fixture bound, then the span sink | the three utilities in section 3, `backend/utilities/label_queue.py`, `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/tests/test_retrieval_eval.py`, `backend/tests/test_evidence.py`, `tests/fixtures/search/`, `docs/reference/documentation-structure.md`, `docs/concepts/evaluation.md`, `docs/architecture/contracts/schemas.md`, the six doc pages in section 3; and `backend/idhazh/telemetry/sinks.py`, `telemetry/__init__.py`, `contracts/knobs/observability.py`, `backend/idhazh/stages/work.py`, `backend/utilities/probe_feeds.py`, `backend/tests/test_spans.py`, `backend/tests/contracts/test_telemetry_surface.py`, `pyproject.toml`, `docs/concepts/telemetry.md`, `docs/how-to/run-the-gates.md` |
| **P3 - the generated layer and the contract** | 5, 6 | two commits: inline-and-bind, then delete-and-amend | `schemas/` (all), `frontend/src/contracts/` (all), `backend/idhazh/contracts/export.py`, `typescript.py`, `base.py`, `__init__.py`, the nine backend contract tests in section 6, `backend/tests/contracts/test_repo_structure.py`, `backend/tests/conftest.py`, the eight frontend specs in section 6, `frontend/scripts/run-checks.ts`, `test-scope.ts`, `tests/test-scope.test.mjs`, `copy-visuals.mjs`, `frontend/src/lib/server/config.ts`, `host-fingerprint.ts`, `pyproject.toml`, `.github/workflows/ci.yml`, `CLAUDE.md`, `AGENTS.md`, `docs/architecture/contracts/schemas.md`, `docs/reference/ci-model-runtime.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/repository-layout.md`, `docs/how-to/run-the-gates.md` |

**Four files appear in more than one pull request, and P3 rebases over every one of them.** `pyproject.toml`: P2 removes the `langfuse` extra at `:166-168` and its mypy override at `:214-221`; P3 removes the `idhazh-export-schemas` script at `:172`. `docs/how-to/run-the-gates.md`: P2 at `:229-234`, P3 elsewhere. `docs/architecture/contracts/schemas.md`: P2 corrects one example, P3 strips the generation sections. `docs/reference/repository-layout.md`: P1 adds the new collection, P3 drops `schemas/`. **P3 runs last regardless, so each of these costs one rebase over deletion hunks and nothing else.**

**`backend/idhazh/contracts/export.py` appears in P1 and P3.** P1 adds two entries to `CONTRACTS`; P3 moves the whole list to `contracts/__init__.py` and deletes the rest of the module. P3 depends on P1 for exactly this reason, and P3 runs last regardless, so they are never in flight together.

### Section 1b - Why the pull requests fall where they do

| Question | Answer |
| --- | --- |
| Why rows 1 and 3 share a pull request | Both edit `backend/idhazh/cli.py` and `config/idhazh.json`. Splitting them puts two branches on one file for no gain |
| Why rows 2 and 7 share a pull request | Both are pure deletion of code with no caller, they share no file, and neither waits on anything. Row 7 is not behavioural despite its size: continuous integration installs neither the `langfuse` extra nor a key, so `trace_sink` already collapses to the file sink under the committed config. At `Parallel N = 1` a second pull request cannot land either row sooner - it costs one more 479 s gating wait, one more merge turn and one more rebase of P3 over an advanced `main`, and buys only an independent revert of 120 lines nothing calls. Measured 2026-09-22 |
| Why they are two commits and not one | Row 7 removes a dependency and a mypy override - 3.4 percent of a 3,520-line diff, and the kind of line a reviewer scrolls past. Two commits keep `git log -p` honest, which is the split P3 already uses |
| Why P3 runs last and alone | Row 5 deletes a generated twin of every contract P1 edits, and it is the only pull request that touches `CLAUDE.md` |
| Why rows 5 and 6 share a pull request | CLAUDE.md section 0 requires a conflicting rule to be amended in the change that conflicts |

### Section 1c - The order, computed rather than read off a letter

**A row is ready when every `Depends-on` is DONE.** At `Parallel N = 1` there is no file-disjointness question to answer: one branch is open at a time.

| Order | Row | Held until |
| --- | --- | --- |
| 1 | **2 and 7**, as P2 | nothing. It can open the day the user authorizes |
| 2 | **1**, as the first commit of P1 | nothing; it is sequenced after P2 only because one worker runs one branch |
| 3 | **3**, as the second commit of P1 | row 1 - both edit `cli.py` and `config/idhazh.json` |
| 4 | **5 then 6**, as P3 | rows 1, 2, 3 and 7. Row 5 deletes a generated twin of every contract they touch |

**Peak workers: 1.**

**No row here measures anything**, so the run-alone rule that applies to a benchmarking row applies to none of them.

## Section 1d - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.** Every existing idiom named here is cited in the tree so the new code copies it rather than inventing a second spelling.

### C1 - The replay knob (row 1)

| Property | Value |
| --- | --- |
| New field | `qualification_repeats: int` on `RunConfig`, `backend/idhazh/contracts/knobs/run.py` |
| Declaration | `Field(default=3, ge=1, description=...)`. The description says what a pass is for - three gates read properties of the sampled output, so passes are draws - and that `wording_spread` reads them |
| Placement | Beside `trial_state_dirname` (`run.py:120`), the nearest knob of the same kind |
| Config | `config/idhazh.json` `run` block (`:297-307`) gains `"qualification_repeats": 3`. Keys in that block are alphabetical; it sorts first |
| Deleted | `.github/workflows/validate.yml:45-47` (the `repeats` dispatch input and its description and default), `:172` (`REPEATS: ${{ inputs.repeats }}` in the fanout step's `env`). **`job_budget_minutes` at `:48-50` is not touched** - it is the bound ESCALATE trigger 1 exists to protect |
| Changed, not deleted | `.github/workflows/validate.yml:180-184` is a `for count in "$CORPUS_PER_SHARD" "$REPEATS" "$JOB_BUDGET_MINUTES"` loop whose `^[1-9][0-9]{0,3}$` check at `:181` guards all three. `:180` drops `"$REPEATS"` from the list and `:182`'s message becomes `corpus_per_shard and job_budget_minutes are 1 through 9999`. **The loop is not deleted** |
| `backend/idhazh/cli.py:345` | `--repeats` stays. Its `default=3` literal becomes the config value, read the way every other config-backed default in that file is read |
| Unchanged | The loop at `stages/qualify.py:495`, its outside-in order and comment, the `if repeat == 1` filter at `:529`, `wording_spread`, `determinism_violation`, the ten gates, and what `elapsed_seconds` measures |
| Not this row's | `runtime_repeats` (`docs/how-to/evaluate-new-summarizer-model.md:397`, `:421`, `:456`) and `bench.repeats` (`:403`) are a different knob on the benchmark workflow. Untouched |
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

**Columns, in order.** Alias types are from `backend/idhazh/contracts/base.py:160-258`, with one exception: `UntrustedLine` is at `backend/idhazh/contracts/article.py:41`, imported as `from idhazh.contracts.article import UntrustedLine`.

| Column | Type | Meaning |
| --- | --- | --- |
| `case` | `Slug` | which pipeline-test case wrote the row - `baseline`, `no-visual-decision`, `parallel-2` |
| `item_id` | `ItemId` | the article |
| `url_key` | `UrlKey` | its address key |
| `date` | `DateStamp` | the run's date |
| `run_id` | `RunId` | the run |
| `model_id` | `str` | the summarizing model's own identifier |
| `title` | `UntrustedLine \| None` | the summary's title, or null |
| `summary` | `str \| None` | the summary text **folded to one line**, `\n` spelled as two characters, or null when the item failed. **Not `Prose`**: `Prose` is multi-line by declaration (`contracts/base.py:191`, `:256`) and is used by three JSON contracts and no CSV ledger |
| `output_digest` | `Sha256` | the digest `Summary.output_digest` already carries |
| `seen_text` | `str` | the post-extraction, post-sanitizer bytes the model was shown, **folded to one line the same way** |
| `seen_text_sha256` | `Sha256` | their digest - the field `contracts/qualification.py:169` already declares. **Taken over the unfolded bytes**, so it still matches what the model read |
| `source_url` | `Url` | where the article came from |
| `finish_reason` | `str` | why decoding stopped |
| `sampling_spelling` | `str` | `canonical_json(fingerprint.sampling_spelling(request))`. **The function at `backend/idhazh/fingerprint.py:139` returns `dict[str, str]`**, so the column names its encoder rather than leaving a worker to invent one |
| `runtime_flags_spelling` | `str` | `canonical_json(fingerprint.runtime_flags_spelling(server))`, `backend/idhazh/fingerprint.py:208`, same shape and same encoding |

**Why two columns are folded.** `ledger.drop_repeated_rows:2217` states the invariant in its own docstring - every free-text cell in these contracts is pinned to printable ASCII on one line, so no cell can carry a newline - and `settle_header:1083` and `migrate_header:1024` both call `readlines()` on it. **Every post-sanitizer body carries a newline: 1,490 of 1,490 measured, and 454 of them carry a double quote too.** `csv.DictWriter` would quote the cell correctly and the file would be valid CSV, but the three line readers would see one article body as dozens of rows and settle on fragments, with nothing red. One encode at write and one decode at read, about 15 lines, plus a unit test that round-trips a body carrying both a newline and a quote.

| Property | Value |
| --- | --- |
| Path | `state/<destination>/summaries/<YYYY>/<MM>/<DD>.csv` - a day **file** |
| Dirname constant | `SUMMARIES_DIRNAME: Final = "summaries"` in `backend/idhazh/ledger.py`, in the block at `:131-140` |
| Path function | `summaries_path(state_dir, date)`, copying `item_health_path` at `ledger.py:474`: `state_dir / SUMMARIES_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"` |
| Writer | `append_summaries(state_dir, date, rows)`, copying `append_published` at `ledger.py:1194` - one line: `extend_ledger_file(summaries_path(state_dir, date), PipelineTestSummaryRow.csv_columns(), list(rows))`. **There is no `append_item_health`** - item health goes through `write_segment`, which is the wrong idiom here because a dispatch writes one file per day, not one per job |
| Key | `SUMMARIES_KEY: Final = ("case", "item_id")`, declared beside `ITEM_HEALTH_KEY` at `ledger.py:218`, and added to `keyed_paths` as `KeyedLedger(path, SUMMARIES_KEY, PipelineTestSummaryRow)` - copy the line at `ledger.py:2168` |
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

**This is a shape ruling, not a claim about concurrency.** [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) converts the six heads a segment folds into; this ledger is appended and never folded, and `.github/workflows/idhazh-pipeline-tests.yaml:64` queues one dispatch at a time into one sequential job, so it has one writer by construction.

### C4 - How the nightly prune finds a trial tree (row 3)

**`_prune_trial_shards` prunes nothing today and never has.** `backend/idhazh/stages/prune_state.py:394` returns when `run.trial_state_dirname` is falsy, and the nightly `config/idhazh.json:306` sets it to `null`. The nightly run cannot know what a dispatch named its tree.

| Property | Value |
| --- | --- |
| The marker | `state/<destination>/.trial-state.json`, written once by the redirect at `backend/idhazh/cli.py:524-525` when it creates the tree |
| **Its contract** | **`TrialStateMarker(Contract)` in `backend/idhazh/contracts/trial_state_marker.py`.** One run writes it and a later run reads it, so CLAUDE.md section 11 applies and plan 41's configuration carve-out does not - nobody edits this file by hand. `__schema_stem__ = "trial-state-marker"`, one `__changelog__` entry at `version="2026-09-22"`, fields `created: DateStamp` and `keep_days: int = Field(ge=1)`. Registered in `CONTRACTS` beside `PipelineTestSummaryRow`, fixture at `tests/fixtures/contracts/trial-state-marker/one-marker.json` |
| Payload | `{"created": "<YYYY-MM-DD>", "keep_days": <int>}` - `keep_days` from `retention.trial_state_days`, which exists at `backend/idhazh/contracts/knobs/retention.py:66` with default 90 |
| Discovery | `_prune_trial_shards` enumerates `state/*/.trial-state.json` instead of reading one name from config, and calls `retention.prune_trial_state` once per tree found |
| **The silent case** | A tree with **no** marker is never enumerated and never pruned, and nothing goes red - the same shape as `_prune_trial_shards` returning at `prune_state.py:394` every night since it was written. The row's oracle drives it |
| `prune_trial_state` | **Signature unchanged** (`backend/idhazh/retention.py:1439`). It already takes `dirname`, already walks one ledger directory per child, already refuses a stray. Only its caller changes |
| The existing tree | `state/pipeline-tests/` gains a marker on the first dispatch after this row and is pruned from then on. Its committed host-fingerprint rows keep their dates and age out normally |
| Dispatch input | `.github/workflows/idhazh-pipeline-tests.yaml` gains a `destination` input defaulting to the model's own identifier, replacing the hard-coded `trial_state: pipeline-tests` at `:140` |

### C5 - The five names the site inlines (row 5)

Three import lines, five names. **Two are runtime values, not types**, and that is why this is not a straight delete.

| Name | Kind | Declared at | Read at | Inlined into |
| --- | --- | --- | --- | --- |
| `ConsolePanelGroup` | interface, 3 fields (`id`, `title`, `panels`) | `frontend/src/contracts/appearance-config.ts:199-208` | `config.ts:24`, re-exported at `:307` | `frontend/src/lib/server/config.ts` |
| `HostFingerprintRow` | interface, **31 fields**, used as `Required<...>` | `host-fingerprint-row.ts:39` | `host-fingerprint.ts:53` | `host-fingerprint.ts`. A field dropped in the copy is a field the reader silently stops populating, so it is copied whole and diffed field by field |
| `ServerJob` | type derived from the array below | `host-fingerprint-row.ts:36` | `host-fingerprint.ts` | `host-fingerprint.ts` |
| `SERVER_JOB` | **runtime array, 6 values**: `plan`, `work`, `assemble`, `visuals`, `runtime`, `decide` | `host-fingerprint-row.ts:34` | `SERVER_JOB.find()` at `host-fingerprint.ts:75`, a membership filter over CSV cells | `host-fingerprint.ts`. A value outside the copy becomes `null` and the row is dropped |
| `WATCHED_FLAG` + `WatchedFlag` | **runtime array, 12 values**: `amx_bf16`, `amx_int8`, `amx_tile`, `avx2`, `avx512_bf16`, `avx512_fp16`, `avx512_vnni`, `avx512f`, `avx_vnni`, `f16c`, `fma`, `sse4_2` | `machine-panels.ts:156` | `watchedFlags()` at `host-fingerprint.ts:162`, which drives the chips a machine card draws | `host-fingerprint.ts` |

`frontend/tests/processor-lost.spec.ts:163` parses `frontend/src/contracts/item-health-row.ts` as a file to get `SERVER_JOB`. It imports it from `host-fingerprint.ts` instead.

### C6 - The two binding tests (row 5)

**One per runtime vocabulary, in `backend/tests/contracts/`, reading the TypeScript literal and comparing it to the Python source of truth.** The pattern already exists at `backend/tests/contracts/test_taxonomy_and_prompts.py:173-183` - it regex-extracts `TELEMETRY_COLUMNS` out of `series.ts`, asserts the match is non-empty, and holds it against `PUBLIC_COLUMNS`.

| Vocabulary | Python source of truth | TypeScript home after row 5 | Note |
| --- | --- | --- | --- |
| `SERVER_JOB` | `ServerJob(StrEnum)` at `backend/idhazh/contracts/base.py:105` | `frontend/src/lib/server/host-fingerprint.ts` | new test |
| `WATCHED_FLAG` | `WATCHED_FLAGS` at `backend/idhazh/contracts/host_fingerprint.py:46` | `frontend/src/lib/server/host-fingerprint.ts` | new test. **Python already binds itself** - `backend/idhazh/contracts/machine_panels.py:84` raises when `WatchedFlag` and `WATCHED_FLAGS` disagree, so only the cross-language half is missing |

Each test fails when one value is removed from either side. **That is not generation: it is two declarations with one gate**, and it is what stops the drift `host-fingerprint.ts:19-23` was written to prevent. Read that comment carefully: it says the page *would have* carried a missing flag for a month, crediting the gate. It is the failure the gate stops, not a failure that happened.

### C7 - What stays in the contract base (row 5)

**Deleting the wrong half of `backend/idhazh/contracts/base.py` breaks every persisted payload in the repository.**

| Part | Verdict | Why |
| --- | --- | --- |
| `json_schema()` L740-758 | **STAYS - correcting an earlier draft of this plan, which said it goes.** It has **four production callers outside the exporter**: `contracts/visual.py:543`, `:559`, `:647`, and `stages/validate_days.py:198-199`. It is the shape in the only notation those callers can walk, not an exporter helper. Deleting it breaks the visual planner and day validation |
| `schema_filename()` L736, `schema_text()` L761 | **Go.** Their only callers are `export.py:172-173`, `:184` and the drift test |
| `__changelog__`, `ChangelogEntry` L643, `schema_version()` L732 | **Stays** | `schema_version()` returns `__changelog__[0].version`, and more than thirty production call sites stamp with it - `Article` at `extract.py:96`, `EvalRow` at `evals/score.py:175`, `RunPlan` at `stages/plan.py:396`. Only `ChangelogEntry.why` is deletable |
| `version` field L710, `_stamp_current_version` L726 | **Stays** | Every persisted payload carries it |
| `read()` L769-807, `StalePayloadError` L651 | **Stays** | It is what lets a reader say "written under an older build" rather than "malformed" |
| `__pydantic_init_subclass__` L713-722 | **Stays, both halves** | The newest-first check is what makes `[0]` mean newest |
| `__schema_stem__` | **Stays as a runtime identifier** | `contracts/console_payloads.py:173` keys a dict on it; it is the fixture directory name via `backend/tests/contracts/_fixtures.py:24` |
| `Model` L608, `without_retired_keys` L614 | **Stays** | `extra="forbid"` is the validation |
| `ServerJob` L105 | **Stays** | C6 binds the site's copy to it |
| **`CONTRACTS`, `contracts/export.py:94-160`** | **Moves to `contracts/__init__.py`** | `_fixtures.py:17` builds `BY_STEM` from it. Deleting `export.py` whole costs the fixture round-trip test its map, and that test is the one thing proving every contract still loads. Only `export()`, `export_typescript()`, `expected_filenames()` and `main()` are deleted |
| `backend/idhazh/contracts/derived.py` | **Untouched** | Three plain models, two validators, no schema writing. Plan 39 named it in error |

### C8 - The reappearance sweep (row 5)

**Prose gates nothing. This is the one control that fails on the commit that brings the layer back.**

| Property | Value |
| --- | --- |
| Where | a contract-tier test in `backend/tests/contracts/`, copying the bounded `git ls-files` shape at `backend/tests/contracts/test_repo_structure.py:517-558` |
| What it refuses | any tracked path under `schemas/` or `frontend/src/contracts/`, and any new module under `backend/idhazh/contracts/` that writes a `.schema.json` or a `.ts` file |
| Self-check | it asserts the listing it read is non-empty - the same trap plan 39 row 1 named, where a check over an empty glob passes with zero cases |
| Cost | about 25 lines |

### C9 - The field-set binding test (row 5)

**The row's asymmetry, corrected.** Two runtime vocabularies get binding tests in C6 and the three inlined types get nothing - but a vocabulary drift announces itself (Python already raises at `contracts/machine_panels.py:84`, and a bad job name visibly drops a row from the panel) while a **type** drift is silent in every gate this project runs.

| Property | Value |
| --- | --- |
| The failure it catches | `HostFingerprintRow` gains a 32nd field. The CSV column is written, `readDayShards` parses it, the hand-written interface never gained it, so the reader never names it and the machine card never draws it. No compile error, no runtime error, no missing row |
| Why `Required<HostFingerprintRow>` does not catch it | `frontend/src/lib/server/host-fingerprint.ts:53` demands every field **the interface has**. `Required<T>` of a stale `T` is stale. It catches the reader forgetting a field; it cannot catch the interface forgetting one |
| The test | a contract-tier test comparing `HostFingerprintRow.model_fields` to the field names parsed from the TypeScript interface. Same idiom as C6; `test_the_frontend_names_every_committed_lens_including_a_tombstone` at `test_taxonomy_and_prompts.py:131` is a second instance |
| Cost | about 25 lines |

### C10 - The instructions that still say "generate" (row 6)

**Row 6 amends the engineering contract; these are the fourteen places in code and docs that still tell a developer to generate.** A guardrail amended while the base class still instructs is an amendment nobody reads.

| Where | What it says |
| --- | --- |
| `backend/idhazh/contracts/base.py:700-703` | the base-class docstring every new contract is written against, naming `schemas/<stem>.schema.json`. **The most direct instruction in the tree** |
| `frontend/src/lib/server/host-fingerprint.ts:14-22` | "The row shape and the flag vocabulary are generated, never typed here" - **the most direct one on the site's side, and it sits in the file row 5 inlines into** |
| `frontend/src/lib/server/host-fingerprint.ts:30-32` | the same instruction, restated over the import |
| `__schema_stem__`, on all 66 models | an attribute named for a file that will not exist. Renamed by row 5 decision 12 |
| `backend/idhazh/contracts/judge_call.py:23`, `backend/tests/contracts/test_judge_call.py:168` | "the exporter calls `schema_filename()` on every..." |
| `docs/architecture/overview.md:96` and `:104` | a diagram node and the export command |
| `docs/concepts/principles.md:21` | "generated from those models rather than written twice" |
| `docs/concepts/config.md:9` and `:49` | "and to the schema generated from it" |
| `docs/how-to/ship-a-pr.md:88` | the drift gate as a merge step |
| `docs/architecture/publishing/layout.md:537` and `:597` | justifies the `ajv` dependency **because** the drift gate generates the schema it validates against - a live dependency whose stated beneficiary moves |
| `backend/tests/contracts/test_app_config.py:591` | "is generated and the drift gate..." |
| `frontend/src/lib/console/machine/processor-lost.ts:32` | points at prose living inside a generated contract |

**Not amended, and named so nobody deletes them:** `backend/idhazh/summarize.py:248` and `backend/idhazh/classify/calls.py:1194` both carry "Generated from the model, never hand-written (Guardrail #3)". Those generate the decode-time output schema the model is constrained by - which `backend/idhazh/llm/server.py:508` calls "the control that survives an injection". **That generation is correct and stays.**

### C11 - The engineering contract after row 6

**Measured against `CLAUDE.md` on 2026-09-22, after plan 41 merged.** Plan 41 added the configuration carve-out to Guardrail #3 and scoped section 11, and **left the generation sentence standing**. That sentence is row 6's.

| Clause | Reads today | After |
| --- | --- | --- |
| Guardrail #3, `CLAUDE.md:90`, **one sentence** | "Every downstream artifact (DB migration, API spec, frontend type, cross-service binding) is generated from that schema, never hand-written." | **Replaced, not deleted.** Deleting it orphans the decode-time output schema, which two docstrings cite by number and which is a Guardrail #11 control. The replacement: **"A copy of a declared shape is generated from it or gated against it - never neither. Generate the copy a machine consumes; gate the copy a person maintains, with a test that reads both sides and fails on a difference. What is forbidden is the same shape written twice with nothing comparing them."** |
| Section 0d, `:60` | "**The contract** is this file, `docs/`, the models in `backend/idhazh/contracts/` and the generated `schemas/`" | The trailing clause goes. The contract is this file, `docs/` and the models |
| Section 1a, second bullet, `:105` | "`schemas/*.schema.json` is generated from those models... A CI drift gate regenerates both and fails on any diff." | Rewritten to the surviving arrangement: the Pydantic models are the source, a copy a person maintains is gated by a test. **It must not say "nothing is generated"** - nine scripts under `frontend/scripts/` still generate committed files, and so does the decode-time schema |
| Section 1a, Schema-first bullet, `:110` | "Every config file and every persisted payload conforms to a generated schema in `schemas/`; a config or payload that fails its schema fails the build" | The payload is validated by its own Pydantic model at the moment it is written. Plan 41 already took config out of this bullet's scope; row 6 takes the generated file out |
| Section 9, `:221` | "Contract drift gate green: schemas and frontend types regenerate byte-identical to what is committed." | Replaced by the binding tests: every gated copy agrees with its source |
| Section 9, `:225` | "Schemas version-stamped + changelogged..." | **Kept.** The stamp survives the schemas - `schema_version()` reads `__changelog__[0]` and thirty-plus production call sites use it (C7) |
| Section 10, `:240` | "Hand-edit a generated artifact (`schemas/*.schema.json`, `frontend/src/contracts/*`)..." | Retargeted to the artefacts that still exist - the icon manifest and the offline worker constants - rather than deleted |
| Section 11, `:262` | "`schemas/<name>.schema.json` is generated from it" | **This IS row 6's, correcting an earlier draft that said section 11 was untouched.** Plan 41 scoped *which payloads* section 11 covers; it left this sentence standing. The clause keeps its four rules and drops the generated file |
| Section 13, Contract tier, `:299` | "the generated schemas vs the readers and the writers, plus the drift gate" | The contract tier becomes the Pydantic models against their readers and writers, plus the binding tests in C6 and C9 |
| `AGENTS.md:51`, and the fourteen places in C10 | say the contracts are generated from the models | Named and corrected |

**Guardrail #11 and Guardrail #12 are untouched.**

## Section 2 - Row 1 - The replay count leaves the dispatch surface

- **Scope:** Delete the `repeats` dispatch input from the qualification workflow and read the count from config; the loop, the gates, the diagnostics and every persisted shape are untouched.
- **Files touched:**
  - `.github/workflows/validate.yml` (the input at `:45-47`, the `REPEATS:` env at `:172`, and `:180-184` where the shared range loop drops one name - **`job_budget_minutes` at `:48-50` is not touched**)
  - `backend/idhazh/contracts/knobs/run.py`
  - `config/idhazh.json`
  - `backend/idhazh/cli.py` (`:345`)
  - `docs/how-to/evaluate-new-summarizer-model.md` (`:608` carries `-f repeats='3'` inside the documented dispatch; `:618` describes the machinery). **`runtime_repeats` at `:397`, `:421`, `:456` and `bench.repeats` at `:403` are a different knob on the benchmark workflow and are untouched**
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'qualif or workflows' -q`; CI - full suite.
- **Oracle:** the dispatch command documented at `docs/how-to/evaluate-new-summarizer-model.md:608` runs against the changed workflow with no unknown-input error, and a qualification run started from the committed config does the same number of passes it does today. **What it cannot settle:** whether three is the right number of passes. Nothing here measures that, and the scope-out table says what would.
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

## Section 3 - Row 2 - The spent utilities go, and the search evaluation is bounded

- **Scope:** Delete the three utilities whose work is finished, delete the human-label path, bound the one session fixture that reads a growing collection, and write down the rule that keeps a census from proposing the rest again.
- **The rule, written into `docs/reference/documentation-structure.md` in this row's first commit:** **a utility a `docs/` page names as the instrument behind a recorded reading is kept, whatever a caller census says.** The page records what was measured; the utility is how the measurement is reproduced. Deleting it turns a reading into a number nobody can check. A census that finds no caller has found no caller - it has not found a dead tool.
- **The three that go, measured 2026-09-22:**

 | Utility | Lines | What it did | Why it is spent |
 | --- | --- | --- | --- |
 | `backfill_day_metrics` | 73 | Wrote day-metrics records for days already published | A one-shot migration. Every day it would fill is filled |
 | `migrate_item_health` | 78 | Rewrote committed item-health files to the current column set | A one-shot migration, and `docs/architecture/contracts/schemas.md` already names it as an example of a pattern the engine replaced |
 | `measure_definition_placement` | 264 | Measured whether putting thirty taxonomy definitions in the prompt costs more tokens than the accuracy it buys | Repeatable, but **no page records its answer**, so there is no reading to reproduce. It is the only one of the ten with neither a caller nor a finding |

- **The seven that stay, and why:**

 | Utility | Lines | Kept because |
 | --- | --- | --- |
 | `index_sizing` | 518 | `docs/archive/measurements-2026-08.md` names it as the method behind its index-size reading |
 | `measure_day_window` | 283 | `docs/reference/benchmarks/day-window-read.md` names it under **Instrument** |
 | `measure_declared_wholes` | 659 | `docs/reference/benchmarks/articles-that-state-a-whole.md` names it under **Instrument**, with its arguments |
 | `measure_probability_mode` | 245 | `docs/reference/benchmarks/which-probabilities-the-server-returns.md` names it under **Instrument**, with its settings |
 | `token_budget` | 215 | `docs/concepts/config.md` says it reproduces the token sweep |
 | `prune_artifacts` | 194 | **Not a measurement at all.** It deletes artifacts GitHub holds, resuming where the last pass stopped, and `docs/how-to/prune-a-collection.md` documents it as a procedure a person follows |
 | `scan_reference_articles` | 302 | Flags extracted text that is not really an article - stub, link dump, duplicate, promotional. Repeatable against any corpus, and the next corpus is Bonsai's |

- **Files touched:**
  - the three above and their tests
  - `docs/reference/documentation-structure.md` (the keep-rule)
  - `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/utilities/label_queue.py`, `backend/tests/test_evidence.py`
  - `backend/tests/test_retrieval_eval.py` (the session fixture at L250, the archive-walk test at L279)
  - `tests/fixtures/search/` (the new bounded corpus)
  - `docs/concepts/evaluation.md`, `docs/architecture/contracts/schemas.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite.
- **Oracle:** the retrieval evaluation runs to a verdict with no file outside `tests/fixtures/` opened, and each deleted module has no importer, no workflow invocation and **no `docs/` page naming it as an instrument** - established by census before its deletion. **What it cannot settle:** whether the fifty committed queries still represent what a reader searches for. Nothing measured that before this row either.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **A utility named by a page as the instrument behind a reading is kept.** Seven of the ten plan 39 proposed are ad-hoc instruments a person runs by hand, five of them cited under **Instrument** on a benchmark page. Deleting the tool leaves a number nobody can reproduce, which is a worse outcome than the lines it saves | Owner, 2026-09-22 |
 | 2 | The rule is written into `docs/reference/documentation-structure.md`, not just applied here. A rule applied once and not recorded is a rule the next census re-litigates | Fowler |
 | 3 | Only a one-shot migration retires outright, and only two qualify: both have already run over every day they would touch | Fowler |
 | 4 | `measure_definition_placement` goes even though it is repeatable, because **no page records what it found.** There is no reading to protect. If its answer mattered it would have been written down | Andre |
 | 5 | **`prune_artifacts` is not a measurement and was never a deletion candidate.** It writes - it removes artifacts GitHub holds - and a how-to page documents it as a procedure | Carmack |
 | 6 | **`backend/utilities/plan_status.py` is not deleted, and nothing calls it.** Its CI job was removed on 2026-09-22 (owner ruling): a page derived from every plan at once had a writer per open branch and conflicted on every line that moved. It stays as an operator surface | Owner, 2026-09-22 |
 | 7 | **`backend/idhazh/evals/retrieval.py` is not deleted.** It is the only instrument that would see a similarity floor moved by 0.05 turning six search results into two | Andre | | 8 | The bound is a committed fixture corpus of the gold days the fifty queries answer, beside the query set already at `tests/fixtures/search/retrieval-queries.json`. `test_every_labelled_answer_is_still_in_the_archive` at L279 is deleted outright - it goes red because somebody published a day, which CLAUDE.md section 13 forbids by name | Andre |
 | 9 | The human-label path goes: zero committed rows, and CLAUDE.md section 1a makes LLM-as-judge primary evaluation. **Its sampling design moves into a `## Design rationale` section in `docs/concepts/evaluation.md` in the same commit** - the shuffle that needs no seed and stays reproducible, from `evals/labels.py:139`, and the procedure. This repository force-pushes its history away on a schedule, so a design living only in a deleted file's history is gone | Andre |
 | 10 | The five demoted qualification diagnostics stay. The scope-out table says why | Andre |
 | 11 | The whole row is deletion, a documented rule and a test-scope change, so it is one pull request with no behaviour in it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete all ten, as an earlier draft of this row said | Seven are ad-hoc instruments, five cited under **Instrument** on a benchmark page and one documented as an operator procedure. A caller census cannot tell a dead tool from a tool nobody has needed this month | About 2,400 lines, five unreproducible readings and one documented procedure | Owner, 2026-09-22 |
 | 2 | Keep all ten and write only the rule | Two are finished migrations over days that are all filled, and one has no recorded answer to protect | 416 lines of code that can never run usefully again | Fowler |
 | 3 | Delete `retrieval.py` and write the replacement fixture later | The replacement is already committed. The row would delete 539 lines and promise to rebuild something that exists | The only search-quality measure, against a five-query wiring check that cannot see a ten-point recall drop | Andre |
 | 4 | Keep the label queue because Bonsai may need human judgement | Defensible - the shape is proven for the other judge at `docs/how-to/label-the-similarity-holdout.md`. It loses because zero rows have ever been committed and the code is cheap to rewrite; what is not cheap is the sampling design, which decision 9 preserves | 1,073 lines and a schema, kept against a need nobody has expressed since it was written | Andre |
 | 5 | Fold this row into P1 | Fewer pull requests | A review that mixes about 3,400 deleted lines with a new persisted contract, where the contract is what needs the attention | Fowler |

## Section 4 - Row 3 - The pipeline test commits what it produced

- **Scope:** Give the pipeline-test workflow write permission and a committed day ledger carrying every case's summary and the bytes the model read, and make the nightly prune able to find the tree.
- **Files touched:**
  - `backend/idhazh/contracts/pipeline_test_summary.py` (new, C2)
  - `backend/idhazh/contracts/trial_state_marker.py` (new, C4)
  - `backend/idhazh/contracts/export.py` (two `CONTRACTS` entries)
  - `schemas/pipeline-test-summary.schema.json`, `schemas/trial-state-marker.schema.json`, and the two matching files under `frontend/src/contracts/` (generated, committed)
  - `tests/fixtures/contracts/pipeline-test-summary/one-row.json`, `tests/fixtures/contracts/trial-state-marker/one-marker.json`
  - `backend/idhazh/ledger.py` (dirname, path function, writer, `keyed_paths` entry, and the one-line fold and unfold C2 names)
  - `backend/idhazh/stages/record.py` (the write)
  - `backend/idhazh/cli.py` (the marker, at the redirect `:524-525`)
  - `backend/idhazh/stages/prune_state.py` (`:379-415`, discovery by marker)
  - `backend/idhazh/retention.py` (caller only; `prune_trial_state` at `:1439` is unchanged)
  - `backend/idhazh/contracts/knobs/retention.py`, `config/idhazh.json`
  - `.github/workflows/idhazh-pipeline-tests.yaml` (`contents: write`, the `destination` input, the commit step)
  - `backend/tests/test_ledger.py`, `backend/tests/retention/`, `backend/tests/workflows/test_staged_paths.py`, `test_validation_state_root.py`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'state or ledger or record or retention' -q`; CI - full suite, and one real dispatch watched to completion before the row closes.
- **Oracle:** a three-case dispatch writes **six rows** - one per case per article - all inside the run's own destination and none outside it; **a row whose `seen_text` carries a newline and a double quote round-trips through `drop_repeated_rows` as one row, not several**; a nightly prune against a tree whose marker is older than the window removes it; **and a tree with no marker is reported rather than silently skipped.** **What it cannot settle:** whether two models' summaries are actually comparable six months on. The row commits the evidence a person needs to judge that; it does not judge it.
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
 | 10 | **Both contracts are registered in `CONTRACTS` and their generated files committed, even though row 5 deletes them.** The reason is `_fixtures.py:24`, which builds `BY_STEM` from `CONTRACTS`: an unregistered contract's fixture is never loaded by anything, so nothing proves the model round-trips. It is **not** the drift gate - `test_schema_drift.py:63` compares `SCHEMAS_DIR.glob("*.json")` to `expected_filenames()`, both derived from `CONTRACTS`, so an unregistered contract is absent from both sets and the gate is green either way. `CONTRACTS` survives row 5; only the four generated files churn | Fowler |
 | 11 | **The two multi-line columns are folded to one line at write.** C2 says why: `drop_repeated_rows`, `settle_header` and `migrate_header` all read these files with `readlines()` on a stated invariant that no cell carries a newline, and every measured article body carries one | Carmack |

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

**DONE, merged in #1040.** Kept for its decisions, which bind the next person who touches a console route list. The residue it found is [`20260922-45-the-readout-covers-every-console-route-plan.md`](20260922-45-the-readout-covers-every-console-route-plan.md).

- **Scope:** Correct the nine hand-written console route lists so each visits all five routes the site serves.
- **Files touched:** `frontend/tests/console-axis.spec.ts:29`, `console-chrome.spec.ts:30`, `console-model-rule.spec.ts:133`, `console-nav.spec.ts:37`, `console-polarity.spec.ts:33`, `console-readout.spec.ts:23`, `console-title.spec.ts:48`, `console-voices.spec.ts:27`, `console-window-claims.spec.ts:57`
- **Acceptance gates:** local - `npm --prefix frontend run test:browser -- --project console`; CI - full suite.
- **Oracle:** every console route the site serves is visited by every spec that claims to cover all of them. It failed on the base tree before #1040: the site serves five and these specs listed three, three, three, four, four and five, so `/console/judgement/` was visited by none of them. **What it could not settle:** whether the tenth route added next quarter reaches all nine lists. Nothing enforces that, and decision 1 says why.
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
- **The case is reviewer attention, not runtime.** The drift gate costs 1 second across four measured runs, the layer publishes zero bytes, and it is 1.1 percent of the pack. What it costs is that about one commit in six has carried a regenerated diff a reviewer scrolled past, and that the generator runs in full to serve four types out of sixty-five.
- **Files touched:**
  - `schemas/` (all 65), `frontend/src/contracts/` (all 65)
  - `backend/idhazh/contracts/export.py` (delete `export()`, `export_typescript()`, `expected_filenames()`, `main()`; move `CONTRACTS` to `contracts/__init__.py`), `contracts/typescript.py`, `contracts/base.py` (C7)
  - `backend/tests/contracts/test_schema_drift.py`, `test_typescript_contracts.py`, `test_cell_shapes.py`
  - **the seven backend modules reading the deleted directory, which plan 39 row 1 did not name:** `test_article_and_eval.py:149`, `test_closed_vocabularies.py:53`, `test_run_timeline.py:187`, `test_stamped_boundary.py:186`, `_config.py:29`, `test_sources_and_marks.py:174` - **that one spells `REPO_ROOT / "schemas"` directly, so a census on `SCHEMAS_DIR` misses it** - and `test_repo_structure.py`, which reads it **twice**: `:114` is a parametrize source over `SCHEMAS_DIR.glob("*.json")` at module scope, and `:514` lists `"schemas"` in `RETIRED_STORE_SWEEP` as one of six trees a person edits, which becomes five
  - `backend/tests/conftest.py:41` (the `SCHEMAS_DIR` constant)
  - **the eight frontend specs reading by path, which plan 39 row 1 did not name:** `console-machine-cards.spec.ts:132` and `:260`, `console-machine-panels.spec.ts:28`, `console-model-instruments.spec.ts:56`, `console-model-reasons.spec.ts:253`, `prompt-reuse.spec.ts:198`, `settings-moved.spec.ts:208-218`, `processor-lost.spec.ts:163`
  - `frontend/scripts/run-checks.ts:310`, `test-scope.ts:169`, `tests/test-scope.test.mjs` (four lines), `copy-visuals.mjs:52`
  - `frontend/src/lib/server/config.ts`, `host-fingerprint.ts` (C5), and the two new binding tests (C6)
  - `.github/workflows/ci.yml:199-208` - **the comment at `:199-203` and the whole `Contract drift gate` step at `:204-208`**; `pyproject.toml:172` (`idhazh-export-schemas`; `:170` is the `[project.scripts]` header and stays)
  - **the reappearance sweep (C8) and the field-set binding test (C9)**, both new contract-tier tests
  - `backend/idhazh/contracts/base.py:700-703` and every `__schema_stem__` (C10's rename)
  - `docs/architecture/contracts/schemas.md` - **stripped to what survives, not deleted**, and it hosts this row's `## Design rationale`
- **Acceptance gates:** local - `npm --prefix frontend run check`, `npm --prefix frontend run test:changed -- --list` then the selected checks, `python -m pytest backend/tests/contracts -q`; CI - full suite and the browser smoke.
- **Oracle:** each binding test in C6 and C9 fails when one value or one field is removed from either side, proved by removing one and watching it go red before it is restored; and the reappearance sweep in C8 fails when a file is added back under either deleted directory. **All three can fail, and C8 is the only one that fails on the commit that undoes this row.** **What it cannot settle:** whether the 30 non-vocabulary fields of `HostFingerprintRow` were copied faithfully at the moment of the inline. Nothing can check that once the source is gone, so it is checked before - field by field, against the generated file, in the same session. C9 protects the field set from that point forward.
- **The green-suite traps, named so a worker looks for them:**

 | Trap | What happens |
 | --- | --- |
 | `backend/tests/contracts/test_repo_structure.py:114` parametrizes over a glob of the deleted directory | It passes with **zero cases** rather than fail. The check is a comparison of collected test counts before and after, not pass or fail |
 | `backend/tests/contracts/test_repo_structure.py:514` lists `"schemas"` among six trees `RETIRED_STORE_SWEEP` covers | It silently covers five. Nothing goes red, and one tree stops being swept |
 | `backend/tests/contracts/_config.py:29` asserts every mention of a name is on a list of survivors | Deleting `frontend/src/contracts/eval-row.ts` **removes a mention**, so the subset assertion still holds and the test stays green pointing at a file that is gone |
 | `frontend/tests/processor-lost.spec.ts:163` parses a generated file as text | It imports `SERVER_JOB` from `host-fingerprint.ts` instead |
 | **One** of the eight frontend specs reads at **module scope** - `console-machine-panels.spec.ts:28` | One missing file raises while the module loads and takes every test in that file with it, including the ones that never touched a schema. The other two an earlier draft named read inside tests, at `console-model-instruments.spec.ts:56` and `console-model-reasons.spec.ts:253` |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The layer is deleted whole rather than pruned to the used files. 62 of 66 have no importer, and a generator kept for four types is a generator | Owner ruling 2026-09-21 |
 | 2 | The Pydantic models stay. They are the validation; the schemas were a copy of them in another notation | Fowler |
 | 3 | The drift gate goes with the artefacts. It checked that a generated file still matched the thing that generated it, which is a loop | Fowler |
 | 4 | **`docs/architecture/contracts/schemas.md` is stripped, not deleted - correcting an earlier draft of this plan.** That draft said the agent bootstrap routes to it; **it does not** - `docs/agents/bootstrap.md` routes a persisted shape to CLAUDE.md section 11 and the model itself. **47 files link to the page**, and three of its rules have nothing to do with generation: the shard rule six pages cite, the changelog-trim ruling, and the version-stamp rules section 11 defers to. The generation sections go; the page keeps the rest and hosts this plan's `## Design rationale` | Fowler |
 | 5 | **`CONTRACTS` is re-homed, not deleted.** `_fixtures.py:17` builds `BY_STEM` from it, so deleting `export.py` whole costs the fixture round-trip test its map - and that test is the one thing proving every contract still loads | Fowler |
 | 6 | **`derived.py` is untouched.** It writes no schema. Plan 39 named it in error | Fowler |
 | 7 | The prose requirement dies with its consumer: it is copied into the generated schema and nowhere else. The version stamp and the changelog stay - `schema_version()` reads `__changelog__[0]` and thirty-plus production call sites stamp with it | Fowler |
 | 8 | Each closed vocabulary keeps one binding test. Two declarations with one gate is not generation, and it is cheaper than the drift the row otherwise buys | Fowler |
 | 9 | The cost framing plan 39 used - forty thousand lines between a person and a change - is dropped. The drift gate is one second and the layer publishes nothing. A row whose stated benefit is one second is a row that gets reverted the first time an inlined type drifts | Carmack |
 | 10 | **The row ships a reappearance sweep** (C8). Prose gates nothing; this is the only control that fails on the commit that brings the layer back | Fowler |
 | 11 | **The row ships a field-set binding test for `HostFingerprintRow`** (C9). Without it a 32nd Python column is read, dropped and never drawn, with every gate green - which is the failure `host-fingerprint.ts:19-23` was written to stop | Fowler |
 | 12 | **`__schema_stem__` is renamed and `base.py:700-703` rewritten.** That docstring tells every new contract its stem names `schemas/<stem>.schema.json`. It is the most direct instruction in the tree to rebuild what this row deletes | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete only the 62 unimported TypeScript files | Leaves the generator, both drift tests, the CI job and 23,582 lines of schema to serve four types | About 8,700 lines removed instead of about 32,800, and the same ritual on every field | Fowler |
 | 2 | Keep the schemas, delete the TypeScript | The schemas' only readers afterwards are the generator that writes them and the test that checks the generator | About 9,200 lines removed, and a gate policing itself | Fowler |
 | 3 | Point the site at the generated types instead of its hand-written copies | The opposite change, and defensible - one declaration per shape. It loses because nobody has wanted it for 65 shapes over the project's life, and the hand-written copies are the ones under test | A rewrite of the payload, search and console layers against a need nobody has expressed | Fowler |
 | 4 | Inline the two vocabularies with no binding test | It is the drift `host-fingerprint.ts:19-23` was written to stop | Two copies with nothing comparing them, and a machine card that quietly stops drawing a chip | Fowler |
 | 5 | Delete the layer and rely on the amended guardrail to keep it out | Prose gates nothing. Twelve instructions in code and docs still say generate, including the base-class docstring every new contract is written against | The layer returns the first time a console panel wants a ledger nobody typed by hand. C8 is 25 lines | Fowler |
 | 6 | Give the three inlined types no protection, as an earlier draft of this row did | Backwards. A vocabulary drift announces itself - Python raises, or a row visibly drops from the panel. A **type** drift is silent in every gate this project runs | A column written, parsed and never drawn, found when somebody asks why the card has no new reading | Fowler |

## Section 7 - Row 6 - The engineering contract and the pages catch up

- **Scope:** Amend the engineering-contract clauses this plan contradicts that plan 41 does not own, and refresh every page whose description of the contract layer or the qualification surface is now wrong.
- **Files touched:** `CLAUDE.md` (**nine clauses, listed in C11**: section 0d at `:60`, Guardrail #3's generation sentence at `:90`, section 1a's second bullet at `:105` and its Schema-first bullet at `:110`, section 9's drift-gate line at `:221`, section 10's hand-editing line at `:240`, section 11's generation sentence at `:262`, and section 13's Contract tier at `:299`), `AGENTS.md:51`, **the fourteen code and doc instructions in C10**, `docs/reference/ci-model-runtime.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/repository-layout.md`, `docs/how-to/run-the-gates.md`
- **Acceptance gates:** `python backend/utilities/doc_load.py` before and after, and the split test on any page gaining a section. No application suite is required for a documentation-only closure.
- **Oracle:** no clause of the engineering contract requires a generated artefact, a schema file, or a drift gate - **checked clause by clause against the tree, not against this plan's table.** That is what stops this row reverting plan 41, which merged on 2026-09-22. **What it cannot settle:** whether a later agent reads the amended clause the way it was meant. Decision 5 is the mitigation.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The amendment ships with row 5, not after it. CLAUDE.md section 0 requires a conflicting rule to be amended in the same change | Owner, CLAUDE.md section 0 |
 | 2 | **Row 6 amends one sentence of Guardrail #3 and leaves the rest of that clause alone.** Plan 41 added the configuration carve-out and scoped section 11, but the sentence requiring every downstream artifact to be generated from the schema is still standing at `CLAUDE.md:90`. Rewriting the whole guardrail from plan 39's table would revert plan 41 - cleanly, with nothing red, because no gate reads CLAUDE.md | Fowler |
 | 3 | Each guardrail that moves records who moved it and when, on the line that moved (CLAUDE.md section 1) | Fowler |
 | 4 | Guardrail #11 and Guardrail #12 are untouched | Fowler |
 | 5 | The phrase in `AGENTS.md:51` saying the contracts are generated from the models is named and removed. An unnamed amendment is one nobody checks, and agent tools read that file instead of the engineering contract | Fowler |
 | 6 | **`TODO/STATUS.md` is not this row's.** Nothing in `.github/` refers to it and nothing regenerates it - its CI job went on 2026-09-22 (owner ruling) - so deleting it waits on no gate and belongs in its own commit ahead of every row here, not inside a contract amendment a reviewer is weighing nine clauses in. **Whoever deletes the page settles `backend/utilities/plan_status.py:966` in the same commit**, where `STATUS_PATH = PurePosixPath("TODO/STATUS.md")` still stands: row 2 decision 6 keeps that utility as an operator surface, so the first person who runs it by hand re-creates the page | Owner, 2026-09-22 |

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
  - `backend/idhazh/telemetry/sinks.py` (`langfuse_sink` at `:113`, `_LangfuseSink` at `:141`, `_trace_context` at `:187`, `_usage` at `:205`). **`_string_attribute` at `:200` is a shared helper** - check it for a surviving caller before it goes
  - `backend/idhazh/telemetry/__init__.py` (the `langfuse_sink` re-export)
  - `backend/idhazh/stages/work.py` - `trace_sink` is at `:79`; what goes is the `langfuse_sink(...)` call at `:103-105` and the host and key reads that feed it. **The function is not gutted**; it collapses to the file sink
  - **`backend/utilities/probe_feeds.py:392`** - a second caller plan 39 row 15 did not list. `:46` describes it in the module docstring
  - `backend/tests/test_spans.py` - `test_a_named_host_with_no_package_falls_back_to_the_file` at `:420-437` and `test_a_host_is_never_reached_unless_all_three_variables_are_set` at `:438-466`. **`:411-419` is `test_a_span_records_nothing_for_a_value_nobody_measured` and stays**
  - `backend/tests/contracts/test_telemetry_surface.py:77` (the export list)
  - `pyproject.toml` - the `langfuse` extra at `:166-168`, its comment block, and the mypy override at `:214-221` (the comment at `:214-217`, the `[[tool.mypy.overrides]]` header at `:218`, `module` at `:219`, `ignore_missing_imports` at `:220`). **Deleting a narrower range orphans the header and attaches `langfuse.*` to the previous override**
  - `docs/concepts/telemetry.md` (`:199-203`, `:553-561`, the decision table), `docs/how-to/run-the-gates.md:229-234` - **`:229` is the extras table row; a narrower cut leaves the table advertising a removed extra**
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

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - the parent, whose rows 1, 7, 8, 12, 15, 17 and 19 this plan carries. Its section 1 is the verified ledger of where all twenty-one of its rows went.
- [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) - the workflows, and what plan 42 did not finish.
- [`20260922-45-the-readout-covers-every-console-route-plan.md`](20260922-45-the-readout-covers-every-console-route-plan.md) - the residue row 4 found and could not fix.
- [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) - the head ledgers. It does not meet row 3; section 0's `Assumes` says why.
- Plan 41 owned Guardrail #3 and section 11; delivered in #1036 and #1039 and deleted on close.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.
