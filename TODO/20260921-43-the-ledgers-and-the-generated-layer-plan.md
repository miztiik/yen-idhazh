# The ledgers, the evaluations, and the generated layer

**Last Updated**: 2026-09-22

**Level**: 5. Rows 5, 6 and 7 each delete or mint a persisted contract, and row 7 amends the engineering contract that requires one. Those three PAUSE for the owner before their pull request opens. Rows 1 to 4 are Level 2 or 3 and run AUTO once the user authorizes.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 39 split into lanes. Plans 41 and 42 took the model file and the workflows and have closed; this is the rest. Every shape a worker needs is declared in section 2 before any row is read, so no row asks a worker to invent a field, a write site or an encoder. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| The second rule | **An instrument is not scaffolding.** A thing that measures what nothing else measures stays, however large and however few gates read it. The test is what goes blind when it leaves, and each row answers it. |
| The measure | **Edits per future change, and reviewer attention per commit.** |
| Hard scope - in | Take the replay count off the qualification dispatch surface and make a lowered count visible on the report. Delete the three spent utilities and record the rule that keeps an instrument a page cites. Delete the hosted span sink. Push the evaluation pin into the retrieval loaders so three growing reads become bounded without losing the live measurement. Delete the human-label path. Give the pipeline test a committed day ledger carrying its summaries and digests, written from the one stage that holds them. Delete the generated contract layer whole, inlining five names, binding two vocabularies and one field set, and amending the nine engineering-contract clauses that still require it. |
| Hard scope - out | **The article bytes stay out of git.** `.github/workflows/idhazh-pipeline-tests.yaml:415-419` already uploads `backend/var/cases/` - which carries each case's `*.article.json`, and therefore `article.text` - at `retention-days: 90`, and `retention.trial_state_days` is also 90. Committing the same bytes buys **zero extra days**, and `backend/idhazh/contracts/article.py` declares that field "Sanitized text. Never republished." Row 6 commits the digest and names the artifact; it does not commit the text. |
| What the owner decides | Three rulings, in section 1b. None of them is the article-text question, which the retention arithmetic above settles. |
| ESCALATE triggers | (1) Row 1 must not change what the BUDGET gate measures. If the work a qualification shard does per dispatch changes at all, stop. (2) Row 4 must not move a gated number. `report` and every assertion over it are byte-identical before and after, or stop. (3) Row 6 mints a persisted contract. If any committed cell can carry a character outside `\x20-\x7e`, stop. (4) Row 7 deletes the artefacts a drift gate protects. If the five inlined names cannot be proved identical to the generated ones before the deletion, stop. (5) Row 7's contract amendment lands in the same pull request as its deletion, never after. (6) Any row that would raise a runner budget figure (Guardrail #2). |
| Runner budget | Measured 2026-09-22: **no row moves a Guardrail #2 figure.** The 6 h job is untouched - the pipeline test runs under its own 140-minute budget and gains about 3 s of commit. The 1 GB site is untouched: `state/` ships zero bytes into `frontend/build`, which stands at 70,005,963 B, and row 7 removes 1.59 MB from the pack. The 10 GB cache and the 20-job concurrency are untouched. Trigger 6 exists for a change this plan does not contain. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

### Section 0a - The first step of every row

**Before the first edit, a worker re-derives its own file list by census and stops if the result differs from what is written here.** One `git grep` per named symbol, per row. The file lists below were measured on 2026-09-22 and are the plan's only defence against a missed consequence; three of them were wrong when this plan was first drafted, and a census is what found all three. Report the difference, correct the row, then implement.

`grep_search` and `file_search` time out on this repository. Use `git grep -n <pattern> origin/main -- <paths>` and `git show origin/main:<path>` from the terminal.

**Cite symbols, not line numbers.** Every line number in this plan was true on 2026-09-22 and several had already drifted from an earlier draft. Where a citation and the tree disagree, the symbol wins.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The replay count leaves the dispatch surface | - | A | PENDING | - | - | - |
| 2 | The spent utilities go, and the keep-rule is written down | - | A | PENDING | - | - | - |
| 3 | The hosted span sink goes | - | A | PENDING | - | - | - |
| 4 | The retrieval loaders take the pin | - | A | PENDING | - | - | - |
| 5 | The human-label path goes | - | A | PENDING | - | - | - |
| 6 | The pipeline test commits what it produced | 1, 3, **plan 46 rows 8 and 11** | B | PENDING | - | - | - |
| 7 | The generated contract layer goes, and the contract catches up | 5, 6, **all of plan 46** | C | PENDING | - | - | - |
| 8 | Nine console specs visit every route the site serves | - | - | DONE | p43r4 | #1040 | R4 |

**Row 8 shipped in #1040** and its residue - two specs whose route lists still omitted `/console/judgement/` and `/console/voices/` - was closed by plan 45 in #1045, #1046 and #1049. The rule and the two scans that hold it are in [`docs/architecture/publishing/console-charts.md`](../docs/architecture/publishing/console-charts.md). Nothing is left to do; the line stays so the next reader is not sent looking.

### Section 1a - Six pull requests, three waves

| PR | Rows | Wave | Level | Files it owns |
| --- | --- | --- | --- | --- |
| **P1** | 1 | A | 2 | `.github/workflows/validate.yml`, `backend/idhazh/contracts/knobs/run.py`, `backend/idhazh/cli.py`, `backend/idhazh/evals/qualify.py`, `config/idhazh.json`, `backend/tests/test_qualify.py`, `backend/tests/workflows/test_shard_fan_out.py`, `docs/how-to/evaluate-new-summarizer-model.md` |
| **P2** | 2, 3 | A | 2 | `backend/utilities/backfill_day_metrics.py`, `migrate_item_health.py`, `measure_definition_placement.py` and their tests; `backend/idhazh/telemetry/sinks.py`, `telemetry/__init__.py`, `backend/idhazh/contracts/knobs/observability.py`, `backend/idhazh/stages/work.py`, `backend/utilities/probe_feeds.py`, `backend/tests/test_spans.py`, `backend/tests/contracts/test_telemetry_surface.py`, `pyproject.toml`, `docs/concepts/telemetry.md`, `docs/how-to/run-the-gates.md`, `docs/reference/documentation-structure.md` |
| **P3** | 4 | A | 3 | `backend/idhazh/evals/retrieval.py`, `backend/tests/test_retrieval_eval.py`, `backend/utilities/measure_retrieval.py` (new), `docs/concepts/growing-reads.md`, `docs/concepts/evaluation.md` |
| **P4** | 5 | A | 5 | the seventeen paths in C8 |
| **P5** | 6 | B | 5 | `backend/idhazh/contracts/pipeline_test_summary.py` (new), `contracts/base.py`, `contracts/export.py`, `contracts/knobs/run.py`, `backend/idhazh/ledger.py`, `backend/idhazh/stages/work.py`, `stages/prune_state.py`, `backend/utilities/pipeline_case_config.py`, `config/idhazh.json`, `.github/workflows/idhazh-pipeline-tests.yaml`, `schemas/pipeline-test-summary.schema.json` and `frontend/src/contracts/pipeline-test-summary.ts` (generated), `tests/fixtures/contracts/pipeline-test-summary/one-row.json`, `backend/tests/test_ledger.py`, `backend/tests/contracts/test_cell_shapes.py`, `backend/tests/contracts/test_repo_structure.py`, `backend/tests/retention/`, `backend/tests/workflows/test_staged_paths.py`, `docs/reference/repository-layout.md` |
| **P6** | 7 | C | 5 | `schemas/` (all 65), `frontend/src/contracts/` (all 65), the readers in C13, `backend/idhazh/contracts/export.py`, `typescript.py`, `base.py`, `__init__.py`, `frontend/src/lib/server/config.ts`, `host-fingerprint.ts`, `frontend/scripts/run-checks.ts`, `test-scope.ts`, `tests/test-scope.test.mjs`, `copy-visuals.mjs`, `pyproject.toml`, `.github/workflows/ci.yml`, `CLAUDE.md`, `AGENTS.md`, `docs/architecture/contracts/schemas.md`, `docs/reference/ci-model-runtime.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/repository-layout.md`, `docs/how-to/run-the-gates.md`, `docs/reference/agent-notes/gates-and-builds.md`, `docs/reference/agent-notes/shell-and-tools.md` |

**Wave A is five pull requests, and their file lists share not one path**: P1 owns the qualification surface, P2 the two deletions, P3 the retrieval evaluation, P4 the label path. `Parallel N = 4` bounds the writers, so the fifth starts as the first slot frees.

**Wave B is P5 alone.** Row 6 shares `cli.py` and `config/idhazh.json` with row 1 and `stages/work.py` with row 3, so it waits for P1 and P2 rather than resolving them. It also waits on **plan 46**, which owns the rule its new committed path must follow, and shares `ledger.py`, `stages/work.py`, `cli.py`, `config/idhazh.json` and the push script with it.

### Section 1c - What waits for plan 46, and what does not

Plan 46 is in flight. Six of its sixteen rows are DONE and nine are PENDING, including three at Level 5. **Five of the seven rows here do not wait**, and blocking them on a sixteen-row plan would be serialisation nobody asked for.

| Row | Waits? | Measured reason |
| --- | --- | --- |
| 1 | No | Shares `validate.yml`, `cli.py` and `config/idhazh.json`, in different hunks: plan 46 edits commit steps and state paths, this edits an input block and an argument parser. Three trivial rebases. |
| 2 | No | Zero intersection. Plan 46 names six utilities and none is one of these three. |
| 3 | No, and land it early | Collides on `stages/work.py` and on the regenerated `app-config` pair. A regenerated conflict is resolved by regenerating. Landing early shrinks plan 46's rebase rather than growing it. |
| 4 | No | Zero intersection. |
| 5 | No | Zero intersection. Deleting one file from `schemas/` does not conflict with a plan that adds a different one. |
| **6** | **Yes - plan 46 rows 8 and 11** | Row 11 is *the day directory is the ledger*, PENDING and Level 5. Minting a ledger first mints it in the shape row 11 must then migrate. Row 8 makes an unowned committed path stop the push, so a path minted before the ownership register exists is a path nobody classified. |
| **7** | **Yes - all of plan 46** | It deletes `schemas/` and `frontend/src/contracts/` whole while nine PENDING rows still write into both, including a new `schemas/digest-run-fragment.schema.json`. Both plans also edit `frontend/src/lib/server/host-fingerprint.ts`. And row 7 amends Guardrail #3 to say contracts are no longer generated, while plan 46's unlanded rows mint contracts under the rule that says they are. |

**Nothing else here depends on another plan.** Plan 44 and plan 47 collide with this one on `schemas/`, `validate.yml`, `pyproject.toml`, `cli.py`, `CLAUDE.md` and `determinism.md`, and a collision is a rebase, not a dependency. Whichever of P6, plan 44 and plan 46 lands second re-reads C9's census rather than assuming the name list is still six.

**Wave C is P6 alone, and it is the long pole**: about 32,800 deleted lines, the only browser smoke in the plan, nine `CLAUDE.md` clauses, four new tests, a 31-field hand copy, and a rebase over every predecessor. It deletes the generated twin of every contract P4 and P5 move, so it runs last whatever else is ready.

**Four files appear in more than one pull request, and P6 rebases over all four.** `pyproject.toml`: P2 removes the `langfuse` extra and its mypy override, P6 removes the `idhazh-export-schemas` script. `docs/how-to/run-the-gates.md`: P2 edits the extras table, P6 the gate list. `docs/reference/repository-layout.md`: P5 adds the new collection, P6 drops `schemas/`. `contracts/export.py`: P4 removes one entry, P5 adds one, P6 deletes the module's body and re-homes `CONTRACTS`. Each costs P6 one rebase over deletion hunks and nothing else.

### Section 1b - What the owner decides

Three rulings. Each is needed before that row's pull request opens; none blocks P1, P2 or P3.

| id | The decision | What it costs either way |
| --- | --- | --- |
| **D1** (row 5) | Delete `LabelRow`, a persisted contract with a committed schema, a committed TypeScript twin and two committed fixtures? Zero rows have ever been written, and CLAUDE.md section 1a makes LLM-as-judge primary evaluation. | Deleting costs 1,073 lines and a schema against a need nobody has expressed since it was written; the sampling design is preserved in `docs/concepts/evaluation.md` in the same commit, so what is lost is the code, not the method. Keeping costs a second judge path nothing exercises and a contract the next census re-proposes. |
| **D2** (row 6) | Mint `PipelineTestSummaryRow`, a new persisted collection under `state/`? | Minting costs about 12 KB a dispatch, bounded at 90 days by `retention.trial_state_days`, plus one schema. Leaving it costs the comparison the row exists for: two models' summaries of the same two articles, months apart, with nothing committed to read. |
| **D3** (row 7) | Delete the generated contract layer and amend nine clauses of `CLAUDE.md`? | Deleting costs a 31-field hand copy plus four binding tests, and stops about one commit in six carrying a regenerated diff a reviewer scrolls past. Keeping costs nothing measurable today - the drift gate is 1 s over four runs and the layer publishes zero bytes - and keeps a generator running in full to serve four types of sixty-five. |

## Section 2 - Contracts declared before any code

**Every shape, name, encoder and write site a worker needs is here.** A row below cites a contract by id and adds no shape of its own. Where this section and a row disagree, this section wins (CLAUDE.md Guardrail #3).

### C1 - The qualification replay count

**What moves.** `qualification_repeats` becomes a knob on `RunConfig` in `backend/idhazh/contracts/knobs/run.py`, `Field(default=3, ge=1, le=10)`, description: "How many times a qualification shard replays each item. Three is the smallest count that separates a model that is deterministic from one that happens to agree twice." `config/idhazh.json` carries `"qualification_repeats": 3` in the same object as the other `run` knobs.

**Four deletion sites in `.github/workflows/validate.yml`**, all four in one commit:

| Site | What is there now | After |
| --- | --- | --- |
| `:45-46` | the `repeats` entry in `workflow_dispatch.inputs` | gone |
| `:172-173` | the `repeats` entry in `workflow_call.inputs` | gone |
| `:182` | the `repeats` pass-through in the caller's `with:` | gone |
| **`:397`** | `--repeats "${{ fromJSON(inputs.repeats) }}"` on the qualify command | **gone** |

**`:397` is the one that fails silently if it is missed.** An undeclared `inputs.repeats` makes `fromJSON` fail at expression evaluation, and every qualification dispatch dies before a step runs. No existing test catches it: eight modules under `backend/tests/workflows/` parse `validate.yml` and not one asserts that every `inputs.<name>` it reads is declared. Row 1 adds that test (C10).

**The CLI cannot read a config default at parser-build time**, because `backend/idhazh/cli.py` builds the parser before it loads settings. Follow the `--cap` idiom already in the file: declare `--repeats` with `default=None`, then after `settings = config.load(args.config)` resolve

```python
repeats = settings.app.run.qualification_repeats if args.repeats is None else args.repeats
```

The flag stays so an operator can override one run without editing config.

**The BUDGET verdict names the count.** `backend/idhazh/evals/qualify.py` already carries `Budget.repeats`, set from `{shard.repeats for shard in shards}` with a disagreement check, so **no contract changes**. Only the `threshold=` string in `budget()` moves, from

```python
threshold=f"{budget_.job_budget_minutes:.0f} min per job"
```

to

```python
threshold=f"{budget_.job_budget_minutes:.0f} min per job, at {budget_.repeats} passes per item"
```

Without this, lowering `"qualification_repeats"` to 1 is a legal one-line config edit that cuts the work to a third and reports a BUDGET pass with a margin nobody can read as false. `QualificationShard.repeats` and `QualificationReport.repeats` stay exactly as they are - they are the record of what ran.

### C2 - `PipelineTestSummaryRow`

A new `Contract` in `backend/idhazh/contracts/pipeline_test_summary.py`. `__schema_stem__ = "pipeline-test-summary"`. `version` is the date the row lands. **Fourteen columns, in this order.** Every one carries the exact expression that produces it, so no worker has to find a value.

| # | Column | Type | Written from |
| --- | --- | --- | --- |
| 1 | `case` | `str`, `min_length=1` | `settings.app.run.case_id` (C4) |
| 2 | `item_id` | `str` | `item.item_id` |
| 3 | `url_key` | `str` | `item.url_key` |
| 4 | `date` | `str`, `YYYY-MM-DD` | the stage's `date` argument |
| 5 | `run_id` | `str` | `recorder.run_id` |
| 6 | `model_id` | `str` | `settings.models.summarize.id` |
| 7 | `title` | folded `str` (C3) | `summary.title` |
| 8 | `summary` | folded `str` (C3) | `summary.summary` |
| 9 | `output_digest` | `str`, 64 hex | `summary.output_digest` |
| 10 | `seen_text_sha256` | `str`, 64 hex | `text_digest(article.text or "")` |
| 11 | `source_url` | `str` | `article.canonical_url` |
| 12 | `finish_reason` | `str` | `reply.finish_reason or ""` |
| 13 | `sampling_spelling` | `str` | `canonical_json(fingerprint.sampling_spelling(settings.models.summarize.request))` |
| 14 | `runtime_flags_spelling` | `str` | `canonical_json(fingerprint.runtime_flags_spelling(settings.models.summarize.server))` |

**There is no `seen_text` column.** The text the model read is already retained for 90 days by `.github/workflows/idhazh-pipeline-tests.yaml:415-419`, which uploads `backend/var/cases/` and therefore every `*.article.json`; `retention.trial_state_days` is 90 too, so a committed copy would expire on the same day. The digest at column 10 is what ties a committed row to that artifact, and `text_digest` is the helper `backend/idhazh/stages/qualify.py` already uses. The column description says so in one line, naming the workflow path.

**The write site is `stage_work`**, in `backend/idhazh/stages/work.py`, inside the per-item loop that already writes `items_dir / f"{item.item_id}.article.json"`. It is the only place in the pipeline that holds the article, the summary and the reply object at once. `stage_assemble` cannot be the site: it has no reply, so `finish_reason` is unreachable from it. `stage_record` cannot be the site either - five of the fourteen columns are not in scope there.

**`stage_work` is sharded, so the file is partitioned by writer.** It takes a `shard: int` and already writes its spans to a per-shard path. One day file appended by up to nine shards is the defect plan 46 exists to delete - a head written by more than one process, which no merge driver, sort order or refresh timing repairs.

**Plan 46 already owns this rule, so do not invent a second spelling of it.** That plan declares three classes for every committed path - `written-once`, `derived` and `union-safe` - and the filename grammar `<run_id>-<attempt>-<job>-<shard>` for the first. This collection is **written-once**: each shard names its own file, nothing rewrites it, and retention is the only other process that touches it. Take the grammar, the class and the ownership entry from plan 46 as they land; this row adds a member to a register it does not design.

**This is why row 6 waits on plan 46 rows 8 and 11.** Row 11 makes the day directory the ledger, so minting one before it lands mints the shape row 11 then has to migrate - a Level 5 data migration made larger by this row. Row 8 makes an unowned committed path stop the push, so a path minted before the ownership register exists is a path nobody classified, and the failure surfaces as a blocked push in an unrelated job.

**Guard.** The row is appended only when `settings.app.run.case_id` is set. A production run leaves it unset and writes nothing, so the pipeline's own output is unchanged.

### C3 - The fold codec

Two columns carry model prose into a CSV cell. **The encoder is `json.dumps(value, ensure_ascii=True)` and the decoder is `json.loads`.** Nothing else.

The obvious alternative - spell a newline as a backslash and an `n` - is **not injective**: a summary that itself contains a backslash followed by `n` decodes to a newline, and `seen_text_sha256` then disagrees with the text it names. `json.dumps` escapes the backslash too, `ensure_ascii=True` forces every non-ASCII character into a `\uXXXX` escape, and the result is guaranteed to hold no byte outside `\x20-\x7e` - which is what `backend/tests/contracts/test_cell_shapes.py` requires of a committed cell. Declare one `FoldedText` annotated alias in the contract module and use it for both columns, so the rule is written once.

### C4 - The case identity

`case_id: str | None = Field(default=None, ...)` joins `RunConfig` in `backend/idhazh/contracts/knobs/run.py`. It is **not** in `config/idhazh.json`; the default of `None` is what a production run uses.

`backend/utilities/pipeline_case_config.py` writes it. That module already loops over the cases and calls `write_case(case, source=..., root=args.cases_root / case.id / "config")`, so it holds `case.id` at the moment it writes each case's `idhazh.json`. It sets `run.case_id = case.id` in the copy it writes.

**Without this there is no case column at all.** All three cases pass the same `trial_state: pipeline-tests` string to the workflow, so nothing in-process can tell baseline from parallel-2, and fourteen columns of two models' work would land in one file with no way to separate them.

### C5 - How a trial root is found, with no marker

**`TrialStateMarker` is not minted.** The earlier draft proposed a sentinel file so the prune could find trial roots; four measurements say it would never be read. `prune_trial_state` in `backend/idhazh/stages/prune_state.py` deletes day files by the date in their own name and never looks for a marker; `_prune_trial_shards` returns before it would reach one; a `keep_days` field on it would duplicate `retention.trial_state_days`; `cli.py` redirects the state root on every stage, so `created` would be restamped on every run; and the file would have to be committed to be visible to the nightly job that reads it.

**The mechanism instead: enumerate.** A child directory of `state/` whose name is not one of the store directory constants declared in `backend/idhazh/ledger.py` is a trial root. That list is already declared, already tested, and gains a new name whenever a real store is added, so the discovery cannot fall out of step.

Row 6 also adds the half that is missing: when a prune empties a trial root, the root itself is removed. Without it the child count under `state/` only ever rises, which is the shape Guardrail #12 exists to stop.

### C6 - How the dispatch commits what it produced

**Two jobs, not one.** The case job keeps `permissions: contents: read`. A second job takes the write.

| Field | Value |
| --- | --- |
| Name | `commit` |
| `needs` | the case job |
| `if` | `always()` |
| `permissions` | `contents: write` |
| Steps | checkout; `actions/download-artifact` with `merge-multiple: true`; `bash .github/scripts/commit-and-push.sh state/pipeline-tests` |

This is the shape `.github/workflows/validate.yml` already uses, where a `decide` job downloads the shard artifacts and runs the same script against `state/pipeline-tests`. Reuse it rather than writing a third push path. Estimated cost 40 to 70 s, against the workflow's 140-minute budget - about 0.7 percent, and it is an estimate because no run has measured this job yet (Guardrail #10).

Raising `contents: write` on the case job instead would hand a token that can push to `main` to the job that runs a model over fetched web text. That is the trust boundary in Guardrail #11 and it is not adapted.

### C7 - The retrieval pin moves into the loaders

The pin already exists and is already configured: `Corpus.through(date)` in `backend/idhazh/evals/retrieval.py` and `assist.eval_corpus_through` in `backend/idhazh/contracts/knobs/assist.py`. What is missing is that the filter runs **after** the whole archive has been read off disk.

**Add `through: str | None = None` to `load_corpus` and to `load_index_corpus`**, and filter on the day directory name before opening a file. Measured 2026-09-22: 32 published days exist, 6 of them at or before the configured pin of `2026-08-26`, so the read drops by about 5x and every gated number is byte-identical because the same rows survive.

**Three growing reads close** in `backend/tests/test_retrieval_eval.py`: the `corpus` fixture, the `index_corpus` fixture, and the second `load_index_corpus(REPO_ROOT)` call inside the index-scope test.

**Two things move to `backend/utilities/measure_retrieval.py` instead of being deleted.** The `live_report` fixture walks the unpinned archive on purpose and prints what a reader actually gets from today's index - it is the only measurement of live search quality anywhere in the project, and a bounded fixture would make it identical to `report` and silently stop measuring anything. The membership check that asserts the index names every published item has the same property. Both become operator surfaces, which pytest does not collect, so the suite stops depending on the archive while the measurement survives. Print the same lines the test printed.

**One test must be read before the loaders change**: the assertion that the pinned gate cannot drift with the archive compares a scored count against the corpus count and expects the corpus to be the larger. Once the loader is pinned, both sides are pinned and it can no longer fail. Move it to the same operator surface or delete it, and say in the commit which and why. Do not leave it asserting something that is now trivially true.

### C8 - What deleting the human-label path touches

Seventeen paths, measured 2026-09-22. **Four of them were missing from the earlier draft**, and the census in section 0a is what found them.

| Kind | Paths |
| --- | --- |
| Code | `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/utilities/label_queue.py` |
| Registration | the `LabelRow` import and its `CONTRACTS` entry in `backend/idhazh/contracts/export.py` |
| Generated | `schemas/label-row.schema.json`, `frontend/src/contracts/label-row.ts` |
| Fixtures | both files under `tests/fixtures/contracts/label-row/` |
| Tests | `backend/tests/test_labels.py`, `backend/tests/test_evidence.py`, the `label` entry in `backend/tests/contracts/_config.py` |
| Docs | `docs/how-to/label-the-faithfulness-queue.md` (whole page), `docs/concepts/evaluation.md`, `docs/concepts/glossary.md`, `docs/concepts/growing-reads.md`, `docs/reference/repository-layout.md`, `docs/architecture/publishing/retention.md`, `docs/architecture/publishing/autotune-content-similarity.md` |

`docs/how-to/label-the-similarity-holdout.md` is a **different** path and it stays - it labels the similarity holdout, which this row does not touch. `docs/archive/measurements-2026-08.md` is an archived measurement and is not edited.

**The sampling design moves, it does not die.** Before the code is deleted, the rule the queue encoded - how a faithfulness sample is drawn and why - is written into `docs/concepts/evaluation.md` as a `## Design rationale` section, in the same commit. Deleting the code without it loses the method, and the method is the part worth keeping.

### C9 - The six names the frontend inlines

Exactly two frontend modules import from `frontend/src/contracts/`, and between them they take six names from three generated files. Every other mention of "contracts" in the frontend is a comment pointing at a Python module.

| Where | Name | Kind | From |
| --- | --- | --- | --- |
| `frontend/src/lib/server/config.ts` | `ConsolePanelGroup` | type | `appearance-config` |
| `frontend/src/lib/server/host-fingerprint.ts` | `SERVER_JOB` | value | `host-fingerprint-row` |
| `frontend/src/lib/server/host-fingerprint.ts` | `HostFingerprintRow` | type | `host-fingerprint-row` |
| `frontend/src/lib/server/host-fingerprint.ts` | `ServerJob` | type | `host-fingerprint-row` |
| `frontend/src/lib/server/host-fingerprint.ts` | `WATCHED_FLAG` | value | `machine-panels` |
| `frontend/src/lib/server/host-fingerprint.ts` | `WatchedFlag` | type | `machine-panels` |

`HostFingerprintRow` is the 31-field hand copy. Copy it from the generated file before deleting it, keep the field order, and let C10 hold it in step.

### C10 - The four tests that replace the generator

A generated layer is a control. Deleting it without a replacement control is how a hand copy drifts. Four tests, each named for what it proves.

| Test | Where | What it proves |
| --- | --- | --- |
| The field set | `backend/tests/contracts/` | the hand-written `HostFingerprintRow` in TypeScript names exactly the fields the Pydantic `HostFingerprintRow` declares - no more, no fewer |
| The two vocabularies | `backend/tests/contracts/` | the TypeScript `SERVER_JOB` and `WATCHED_FLAG` literals hold exactly the members their Python enums hold |
| Every workflow input is declared | `backend/tests/workflows/` | every `inputs.<name>` any workflow expression reads is declared in that workflow's `inputs:` block. Belongs to row 1; this is the test that would have caught `validate.yml:397` |
| Nothing regenerates | `backend/tests/contracts/` | no `schemas/` or `frontend/src/contracts/` path is reachable, and `idhazh.contracts.export` no longer exists as a module |

These are contract-tier tests and they read source text, not the committed archive (CLAUDE.md section 13).

### C11 - The reappearance sweep

Deleting a generator leaves references to it in prose, and prose does not fail a build. Row 7 sweeps for `idhazh-export-schemas`, `contracts.export`, `schemas/`, `expected_filenames`, `export_typescript` and `module_text` across `pyproject.toml`, `.github/workflows/`, `CLAUDE.md`, `AGENTS.md`, `docs/` and `frontend/scripts/`, and edits every hit.

**Five of those hits are docstrings, not imports**, so they will not break a build and will not be found by running the suite: `backend/idhazh/contracts/derived.py`, `contracts/judge_call.py`, `contracts/typescript.py`, `backend/tests/council/test_metrics_sink.py` and `backend/tests/workflows/test_telemetry_cli.py` each describe the export module in prose. `contracts/derived.py` in particular explains that its models are deliberately not exported - a sentence that means nothing once nothing is exported.

**Six files import from it for real** and each one breaks loudly: `backend/tests/contracts/_fixtures.py`, `test_judge_call.py`, `test_retired_fingerprint.py`, `test_schema_drift.py`, `test_stamped_boundary.py` and `test_typescript_contracts.py`. The last two of those take `expected_filenames`, `export`, `expected_type_filenames` and `export_typescript`, which all go away with the generator.

### C12 - What survives in `contracts/base.py`, and where `CONTRACTS` lives

**`json_schema()` stays.** It is `model_json_schema()` plus the project's own canonicalisation, and `canonical_json(cls.json_schema())` is what the stamped-boundary and drift checks compute over. Deleting the generator does not delete the ability to ask a contract for its schema.

**`__schema_stem__` keeps its name.** The earlier draft said in one place that it stays and in two others that it is renamed, with no new name given. It stays: it is the stable published key for a payload and is read by the fixture map, so renaming it is a second change wearing this one's clothes. Only its docstring changes, to stop describing a file that no longer exists.

**`CONTRACTS` moves to `backend/idhazh/contracts/__init__.py`.** It is the registry of every declared contract and six test modules import it; it is not part of the generator. Every one of those six imports is rewritten in the same commit, and `backend/tests/contracts/_fixtures.py` - which builds the stem-to-class map the whole contract tier drives from - is the one that fails first and loudest if a single import is missed.

### C13 - The engineering-contract clauses

Row 7's amendments to `CLAUDE.md`, by heading rather than by line number. Each is one edit and all of them land in the deletion's own pull request.

| Clause | What it says now | What it must say |
| --- | --- | --- |
| Guardrail #3 | every downstream artifact is generated from the schema, never hand-written | the Pydantic model is the source of truth; a hand copy that crosses into the frontend is held by a named test |
| Section 1a | `schemas/*.schema.json` is generated from those models, and the frontend's types from those schemas | the model is the truth; the frontend copy is small, hand-written and test-bound |
| Section 1a | a CI drift gate regenerates both and fails on any diff | the four controls in C10 |
| Section 9 | the contract drift gate must regenerate byte-identical | replaced by the C10 controls |
| Section 10 | do not hand-edit a generated artifact | there is no generated artifact |
| Section 11 | `schemas/<name>.schema.json` is generated from it | the schema is computed on demand from the model |
| Section 13 | contract tier means generated schemas against readers and writers | contract tier means the model against its readers and writers |
| Section 14 | Fowler's altitude mentions the generated layer | unchanged in substance, corrected in wording |
| `AGENTS.md` | repeats the generation rule in its own words | restates the amended clause, adds nothing (CLAUDE.md section 5) |

The same pass corrects the four documentation pages that describe the generator as a running thing: `docs/architecture/contracts/schemas.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/ci-model-runtime.md` and `docs/reference/repository-layout.md`.

## Section 3 - Row 1: the replay count leaves the dispatch surface

**Scope.** Implement C1 whole: the knob, the config default, the four workflow deletions, the CLI resolution after `config.load`, and the BUDGET threshold string. Nothing else in `validate.yml` moves.

**Why.** The replay count is a property of how this project qualifies a model, not a thing an operator picks per dispatch. It is declared in three places and passed through four, and the count that actually ran is already recorded on every shard, so the dispatch surface is carrying a decision it does not own.

**Files.** P1's row in section 1a.

**Acceptance gates.**

- `ruff check backend`, `ruff format --check backend`, `mypy backend` clean.
- `pytest backend/tests/test_qualify.py backend/tests/workflows/` green, including the new every-input-is-declared test from C10.
- `git grep -n 'repeats' -- .github/workflows/validate.yml` returns **nothing**. This is the check for `:397`.
- `python -m idhazh.cli qualify --help` still lists `--repeats`.
- Contract drift gate green: `config/idhazh.json` validates against the regenerated `app-config.schema.json`.

**Oracle - prove the gate can fail.** Delete the `qualification_repeats` line from `config/idhazh.json` and confirm the config load fails by name rather than defaulting silently. Then set it to `1` and confirm the BUDGET verdict's threshold string reads `at 1 passes per item`. Restore both from the commit, not from the working tree.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | The flag stays. An operator overriding one run without editing config is the case the flag exists for; what leaves is the dispatch input, not the ability to override. |
| 2 | `QualificationShard.repeats` and `QualificationReport.repeats` stay. They record what ran, which is a different question from what to run. |
| 3 | The dispatch's own range check goes with the input, and `Field(ge=1, le=10)` on the knob replaces it. The threshold string is what stops a lowered count being invisible. |

**Refused.** *Cut the loop to one pass and delete the count.* Three passes is what separates a model that is deterministic from one that agreed twice by luck. One pass makes the determinism gate unable to fail, which is a quieter failure than a missing input.

## Section 4 - Row 2: the spent utilities go, and the keep-rule is written down

**Scope.** Delete `backend/utilities/backfill_day_metrics.py`, `backend/utilities/migrate_item_health.py` and `backend/utilities/measure_definition_placement.py`, with their tests. Write the keep-rule into `docs/reference/documentation-structure.md`.

**Why each one is spent.** The first two are migrations whose last unmigrated row has aged out - they run over data no store holds any more. The third measured a question that has since been answered and written down.

**The keep-rule, written as a `## Design rationale` section**: an instrument a documentation page cites stays, because deleting it makes the page's number unreproducible. A migration whose last row has aged out goes. State the rule, name the three utilities it just removed, and name at least one utility it protects.

**Files.** P2's row in section 1a, the first group.

**Acceptance gates.**

- `ruff check backend`, `mypy backend` clean.
- `pytest backend/tests/` green.
- `git grep -n 'backfill_day_metrics\|migrate_item_health\|measure_definition_placement'` returns nothing outside `docs/archive/`.
- No page under `docs/` cites a number produced by any of the three.

**Oracle.** For each of the three, name in the commit message the store its last row would have lived in and show that store is empty of unmigrated rows. A deletion with no such sentence is not ready.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | The rule is written before the deletions, in the same commit. A rule written after is a rule that describes what somebody already did. |
| 2 | Archived measurement pages are not edited. They are dated records of what was true then. |

## Section 5 - Row 3: the hosted span sink goes

**Scope.** Delete the hosted span sink in `backend/idhazh/telemetry/sinks.py` and its export, the `langfuse` extra and its mypy override in `pyproject.toml`, the knobs in `backend/idhazh/contracts/knobs/observability.py` that configure it, and its call sites in `backend/idhazh/stages/work.py` and `backend/utilities/probe_feeds.py`. Keep the local span record.

**Why.** It is a runtime call to a third party from a build-time producer, which Guardrail #1 and CLAUDE.md section 1b both refuse - logging here is local by construction. It has no configured endpoint, so it has never sent anything.

**Files.** P2's row in section 1a, the second group.

**Acceptance gates.**

- `ruff check backend`, `mypy backend` clean.
- `pytest backend/tests/test_spans.py backend/tests/contracts/test_telemetry_surface.py` green.
- `git grep -rn 'langfuse'` returns nothing outside `docs/archive/`.
- `uv sync` resolves with the extra gone and the lockfile in step with the manifest.
- `python -m idhazh.contracts.export` regenerates `schemas/app-config.schema.json` and `frontend/src/contracts/app-config.ts` byte-identical to what the commit carries. **Removing a knob description moves both files; if they are not in the commit the drift gate fails in CI.**

**Oracle.** Run one pipeline stage end to end on the canary day and confirm the local span record still holds the same span names it held before. The sink going away must not take a span with it.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | The local span record stays. It is the only trace this project keeps and nothing about it crosses the network. |
| 2 | The two generated files ship in the same commit. They are generated, not hand-edited (CLAUDE.md section 10). |

## Section 6 - Row 4: the retrieval loaders take the pin

**Scope.** Implement C7: `through=` on both loaders, three growing reads closed, two measurements moved to `backend/utilities/measure_retrieval.py`, and the drift test that can no longer fail either moved or deleted. Update `docs/concepts/growing-reads.md` to match.

**Why.** Three tests read every published day to answer a question that is pinned to six of them. Guardrail #12 is about exactly this: a cost that rises because the repository accumulated more data, with no change to the question.

**Files.** P3's row in section 1a.

**Acceptance gates.**

- `pytest backend/tests/test_retrieval_eval.py` green, and **every gated number byte-identical to the pre-change run.** Capture the report summary line before and after and diff them. This is ESCALATE trigger 2.
- No `REPO_ROOT`-rooted corpus or index load remains in the test module.
- `python backend/utilities/measure_retrieval.py` runs and prints the same live lines the fixture printed.
- `docs/concepts/growing-reads.md` no longer lists the three reads, and lists the operator surface instead.

**Oracle.** Point the loader at a day that is after the pin and confirm it is not read - the count of opened files must not change. Then remove the pin from config and confirm the count rises, which proves the filter is doing the work rather than the data happening to be small.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | The pin goes into the loader, not into a gold-day fixture. A fixture would make the live measurement identical to the pinned one and stop measuring live search quality without anything going red. |
| 2 | The live measurement moves to an operator surface rather than dying. It is the only reading of what today's index actually returns. |
| 3 | The queries file and the embedder still load from the repository root. They are fixed-size inputs, not a growing collection. |

## Section 7 - Row 5: the human-label path goes

**PAUSE for decision D1 before the pull request opens.**

**Scope.** Implement C8: seventeen paths, and the sampling design written into `docs/concepts/evaluation.md` first.

**Why.** It is a second evaluation path with a persisted contract, a committed schema, a committed TypeScript twin, two fixtures and a whole how-to page, and zero rows have ever been written through it. CLAUDE.md section 1a makes LLM-as-judge the primary evaluation, including in production.

**Files.** C8.

**Acceptance gates.**

- `ruff check backend`, `mypy backend` clean; `pytest backend/tests/` green.
- `npm --prefix frontend run check` clean.
- `python -m idhazh.contracts.export` leaves no `label-row` artefact behind - **confirm the two generated files are deleted, not merely unwritten.** The exporter writes; it does not prune.
- `git grep -rni 'labelrow\|label_queue\|label-the-faithfulness'` returns nothing outside `docs/archive/`.
- Every link to `docs/how-to/label-the-faithfulness-queue.md` is gone from every page that carried one.

**Oracle.** Before deleting, confirm the store is empty: no committed row anywhere matches the label row's schema stem. A row found is a stop, not a smaller deletion.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | The sampling design is written into `docs/concepts/evaluation.md` in the same commit. The method is what is worth keeping; the code is not. |
| 2 | `docs/how-to/label-the-similarity-holdout.md` stays. Different queue, different row, untouched. |
| 3 | This is its own pull request. It removes a persisted contract, which is a Level 5 diff and should not be read inside a pile of ordinary deletions. |

## Section 8 - Row 6: the pipeline test commits what it produced

**PAUSE for decision D2 before the pull request opens.** Depends on rows 1 and 3, and on plan 46 rows 8 and 11 (section 1c).

**Scope.** Implement C2, C3, C4, C5 and C6 together: the fourteen-column contract, the fold codec, the case identity, the marker-free prune, and the two-job commit.

**Why.** The dispatch runs two models over the same two articles and throws the output away. Nothing committed says what either model wrote, so the comparison the workflow exists to support cannot be made a month later.

**Files.** P5's row in section 1a.

**Acceptance gates.**

- The new contract is declared in `backend/idhazh/contracts/` **before any code reads or writes it** (Guardrail #3), registered in `CONTRACTS`, and `schemas/pipeline-test-summary.schema.json` plus its TypeScript twin are generated and committed.
- `version` is stamped with the landing date and the first `changelog` entry is one line.
- `backend/tests/contracts/test_cell_shapes.py` passes over the new contract: **no committed cell carries a byte outside `\x20-\x7e`.** This is ESCALATE trigger 3, and this test is the reason the row keeps that module rather than deleting it.
- A fixture at `tests/fixtures/contracts/pipeline-test-summary/one-row.json` round-trips through the contract.
- `pytest backend/tests/test_ledger.py backend/tests/retention/ backend/tests/workflows/test_staged_paths.py` green.
- A prune over a trial root that empties it removes the root. Assert the child count under the state root falls.
- `.github/workflows/idhazh-pipeline-tests.yaml` keeps `permissions: contents: read` on the case job.
- **Two shards writing the same date produce two files, and reading the date returns both rows.** Assert it, or the row has rebuilt the defect plan 46 removes.

**Oracle.** Fold a title containing a newline, a literal backslash-n, a double quote and a non-ASCII character, commit it through the real write path, read it back with `json.loads`, and assert the round-trip is exact and the cell is pure ASCII. A codec that cannot survive that input is the wrong codec, and the naive escape does not.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | No `seen_text` column. The artifact already holds the bytes for 90 days and `trial_state_days` is 90, so a committed copy buys zero extra days and contradicts `article.py`'s own "Never republished". |
| 2 | The write site is `stage_work`. It is the only stage holding article, summary and reply at once, and it partitions by shard because it is sharded. |
| 3 | `json.dumps` with `ensure_ascii=True`, never a hand-rolled escape. The hand-rolled one is not injective and silently breaks the digest. |
| 4 | No `TrialStateMarker`. Enumerate trial roots against the declared store names instead. |
| 5 | Two jobs for the commit. The job that runs a model over fetched text does not get a token that can push to `main` (Guardrail #11). |
| 6 | The row is written only when `case_id` is set, so a production run is unchanged. |

**Refused.** *One day directory per case instead of a case column.* Three cases would write three day files for the same date, and every reader that walks a date would have to know to merge them. One column is cheaper for every reader.

## Section 9 - Row 7: the generated contract layer goes, and the contract catches up

**PAUSE for decision D3 before the pull request opens.** Depends on rows 5 and 6, and on **all of plan 46** (section 1c). Runs last.

**Scope.** Implement C9, C10, C11, C12 and C13 in one pull request: inline the six names, add the four tests, delete `schemas/` (65 files) and `frontend/src/contracts/` (65 files), delete the generator, re-home `CONTRACTS`, sweep the prose, and amend the nine engineering-contract clauses.

**Why.** A full generator runs on every contract change to serve six names in two frontend files. Sixty-five schemas are generated and sixty-one are read by nothing but the gate that checks they were generated.

**Order, and it is not negotiable.**

1. **Confirm plan 46 has landed.** It mints contracts under the rule this row deletes, and nine of its rows were still writing into `schemas/` and `frontend/src/contracts/` when this was written. Starting before it finishes means deleting a directory another plan is still filling.
2. Copy the six names out of the generated files into hand-written TypeScript.
3. Add the four tests from C10 and watch them pass against the generated layer still in place.
4. Only then delete. A test that has never passed against the old layer proves nothing about the new one - this is ESCALATE trigger 4.
5. Amend `CLAUDE.md` and `AGENTS.md` in the same commit - ESCALATE trigger 5.

**Files.** P6's row in section 1a.

**Acceptance gates.**

- `ruff check backend`, `mypy backend` clean; `pytest backend/tests/` green.
- `npm --prefix frontend run check` clean. There is no `npm run lint` in this repository.
- The four C10 tests pass **before** the deletion and after it.
- `git grep -rn 'idhazh-export-schemas\|contracts\.export\|expected_filenames\|export_typescript'` returns nothing outside `docs/archive/`.
- `.github/workflows/ci.yml` no longer runs a drift gate that has nothing to check.
- **Browser smoke** (CLAUDE.md section 12): load the console route that reads the host fingerprint, confirm zero new `[error]` and zero new `404`, and confirm the page still renders with its data file absent. This is the only row in the plan that publishes a change a reader can see.

**Oracle.** Add a field to the Pydantic `HostFingerprintRow` and confirm the field-set test goes red. Remove a member from one of the two enums and confirm the vocabulary test goes red. Restore both from the commit. If either stays green, the hand copy is unheld and the deletion is not safe.

**Decisions.**

| # | Decision |
| --- | --- |
| 1 | `json_schema()` stays on the base model. The generator goes; the ability to ask a contract for its schema does not. |
| 2 | `__schema_stem__` keeps its name. It is the published key and the fixture map reads it; only its docstring changes. |
| 3 | `CONTRACTS` moves to `contracts/__init__.py`. It is the registry, not part of the generator, and six test modules import it. |
| 4 | The contract amendment is in this pull request, not a follow-up. A contract that requires a layer that no longer exists is a contract the next agent will follow. |

**Refused.**

| Alternative | Why not |
| --- | --- |
| Delete only the 61 schemas nothing imports | The count is a fact about today. Tomorrow's contract adds a sixty-sixth and the generator is still running in full. |
| Keep the schemas, delete the TypeScript | The schemas are the larger half and the less read half. This keeps the cost and drops the part that has a reader. |
| Amend the contract in a follow-up | Between the two, `CLAUDE.md` requires a generated layer that does not exist, and an agent reading it will regenerate one. |

## See also

- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the workpool, readiness and the merge rule.
- [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the environment and every gate command.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - Guardrail #12's escape hatch, which row 4 edits.
- [`docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md) - the layer row 7 deletes.
- [`docs/reference/agent-notes.md`](../docs/reference/agent-notes.md) - the tool quirks that make a command lie, including the search timeouts in section 0a.
