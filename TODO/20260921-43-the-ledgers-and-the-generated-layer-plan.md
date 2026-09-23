# The ledgers, the evaluations, and the generated layer

**Last Updated**: 2026-09-23

**Level**: 5. Rows 5 and 7 each delete or amend a persisted contract and stop before their pull request opens. Rows 1, 2, 3, 4 and 6 are Level 2 or 3 and run AUTO once the user authorizes.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; AUTO-merge on green gates; honor the ESCALATE triggers each row carries. AUTHOR-AND-STOP until the user authorizes.

**One row is one place.** Everything a worker needs for a row - the shapes, the exact expressions, the file list, the gates, the oracle - is in that row's own section. No row sends a worker to another row to find its own contract.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Hard scope - in | Take the replay count off the qualification dispatch surface and give it a floor that refuses a report which cannot fail. Delete the three spent utilities and the hosted span sink. Bound the two retrieval loaders, each on the bound that fits the question it answers. Make the human-label queue runnable instead of deleting it. Commit what a pipeline-test dispatch already wrote, and repair the prune that has never run over it. Delete the generated contract layer and amend the nine engineering-contract clauses that require it. |
| Hard scope - out | **The article bytes stay out of git.** `.github/workflows/idhazh-pipeline-tests.yaml` uploads `backend/var/cases/` - which carries each case's `*.article.json`, and therefore `article.text` - at `retention-days: 90`. `backend/idhazh/contracts/article.py` declares that field "Sanitized text. Never republished." Row 6 commits what the run wrote about the article; it does not commit the article. |
| Runner budget | Measured 2026-09-22: **no row moves a Guardrail #2 figure.** The 6 h job is untouched - the pipeline test runs under its own 140-minute budget and row 6 adds one `commit` job estimated at 40 to 70 s, between 0.5 and 0.9 percent of it, and it is an estimate because no run has executed that job (Guardrail #10). The 1 GB site is untouched for a reason rather than by a count: **no console page reads `state/pipeline-tests/`**, so row 6's committed rows prerender into nothing and add zero bytes to the built site, and neither `schemas/` nor `frontend/src/contracts/` is served, so row 7's deletion moves the site by zero bytes too. That deletion removes 1,517,319 B from every future checkout and **does not shrink the repository** - git history is append-only, so it adds a commit to the pack. The committed published payload under `frontend/public` is 39,377,134 B, about 4 percent of the cap. The local `frontend/build` tree is a stale canary build - newest file 2026-09-18, and `build/digest/` holds 22 stub days that predate the first published day - so it is not a measurement of the site. The 10 GB cache and the 20-job concurrency are untouched. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` |

### Section 0a - The first step of every row

**Before the first edit, a worker re-derives its own file list by census and stops if the result differs from what the row says.** One `git grep` per named symbol. Report the difference, correct the row, then implement.

**Cite symbols, not line numbers.** Every line number here was true on 2026-09-22. Where a citation and the tree disagree, the symbol wins.

`grep_search` and `file_search` time out on this repository. Use `git grep -n <pattern> origin/main -- <paths>` and `git show origin/main:<path>` from the terminal.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The replay count leaves the dispatch surface | - | A | DONE | p43r1 | - | worker |
| 2 | The spent utilities go, and the keep-rule is written down | - | A | DONE | p43r23 | - | worker |
| 3 | The hosted span sink goes | - | A | DONE | p43r23 | - | worker |
| 4 | The retrieval loaders take their bounds | - | A | DONE | p43r4 | - | worker |
| 5 | The label queue becomes runnable | - | A | DONE | p43r5 | - | worker |
| 6 | The pipeline test commits what it already wrote | 2, 3 | B | DONE | p43r6 | - | worker |
| 7 | The generated contract layer goes, and the contract catches up | plan 46, landed 2026-09-23 | C | PENDING | - | - | - |

### Section 1a - Six pull requests, three waves

| PR | Rows | Wave | Level | Waits for |
| --- | --- | --- | --- | --- |
| P1 | 1 | A | 2 | nothing |
| P2 | 2, 3 | A | 2 | nothing |
| P3 | 4 | A | 3 | nothing |
| P4 | 5 | A | 2 | nothing; rebases over P1 on `config/idhazh.json` |
| P5 | 6 | B | 3 | P2 |
| P6 | 7 | C | 5 (PAUSE) | all of plan 46 |

**Wave A is four pull requests.** P1 owns the qualification surface, P2 the two deletions, P3 the retrieval evaluation, P4 one config line and one docs page. P1 and P4 both add a line to `config/idhazh.json`; that is a two-line rebase, named rather than claimed away. `Parallel N = 3`, so the fourth starts as the first slot frees.

**Wave B is P5 alone.** Row 6 adds two guarded writes to `backend/idhazh/stages/work.py`, which P2 edits in large hunks. Landing P2 first turns a conflict into a trivial rebase.

**Wave C is P6 alone.** It deletes 130 generated files and amends nine `CLAUDE.md` clauses, and it waits on plan 46 for the reason in its own section.

**An earlier draft of this plan claimed wave A's file lists shared not one path. Three of them did.** That is why section 0a exists and why every file list below carries the date it was measured.

### Section 1b - The one pause

**Row 7 deletes a persisted contract layer and amends the engineering contract, so it stops before its pull request opens** (CLAUDE.md section 6, Level 5). It is cheap to write and expensive to reverse, which is what Level 5 names.

**A worker reaching it stops and reports**: what the deletion removes, what a future change loses by not having it, and the smallest thing that would put it back. It does not open the pull request. The owner rules, and the ruling lands as a dated `## Design rationale` line in the living doc the row edits.

**No other row pauses.** Rows 1 to 6 are Level 2 or 3 and run AUTO.

## Section 2 - Row 1: the replay count leaves the dispatch surface

**Level 2.** Waits on nothing.

**Why.** The replay count is a property of how this project qualifies a model, not a thing an operator picks per dispatch. It is declared once and passed through four more places, and the count that actually ran is already recorded on every shard.

### Section 2a - The shapes this row needs

**The knob.** `qualification_repeats` joins `RunConfig` in `backend/idhazh/contracts/knobs/run.py`, **`Field(default=3, ge=3, le=10)`**, description: "How many times a qualification shard replays each item. Three is the smallest count that separates a model that is deterministic from one that happened to agree twice, and it is the floor rather than the default because a report built on fewer passes is a report that cannot fail." `config/idhazh.json` carries `"qualification_repeats": 3` beside the other `run` knobs.

**The floor is the control. The threshold string is not.** `ge=1` would re-admit the exact failure this row refuses: one pass makes the determinism verdict unable to fail, and a line of text on a passing report is read by somebody who has already decided. `ge=3` refuses at config load, before a step runs, and `--repeats 1` is refused on the same rule because the flag resolves into the same knob. `le=10` is narrower than the dispatch's `1 through 9999`; ten passes is past any determinism question, and a run that wants more edits the field.

**`config/idhazh.json` already carries `"repeats": 3` under `bench`.** Different owner, same word, one file. The new knob is `run.qualification_repeats` and the bench one is untouched.

**Five sites in `.github/workflows/validate.yml`, all five in one commit. Three are edits, not deletions.** There is no `workflow_call:` block in that file - it has `workflow_dispatch` only.

| id | Site, by symbol | What goes | What survives, and why |
| --- | --- | --- | --- |
| A1 | the `repeats:` entry under `on.workflow_dispatch.inputs` | the key, its `description` and its `default: '3'` | the four sibling inputs. `job_budget_minutes` is the next entry and is untouched. |
| A2 | `REPEATS: ${{ inputs.repeats }}` in the `fanout` step's `env:` | that one line | `SHARDS`, `CORPUS_PER_SHARD` and `JOB_BUDGET_MINUTES` in the same block. **`JOB_BUDGET_MINUTES` is a different input.** Deleting it takes the BUDGET gate's bound with it. |
| A3 | the `"$REPEATS"` word in the range loop in `fanout`'s `run:` | that one word | the loop, the `^[1-9][0-9]{0,3}$` pattern, `set -euo pipefail`, the `exit 1`, and the shards check above it. |
| A4 | the error message inside that loop | the word `repeats` and its comma | the line, its `>&2` and its `exit 1`. The message still names two inputs. |
| A5 | `--repeats "${{ fromJSON(inputs.repeats) }}"` on the `qualify` command in `Freeze the corpus and replay it` | the whole line, including its trailing `\` | every other flag on that command, `--shards` included. |

**A3, exact.** Before: `for count in "$CORPUS_PER_SHARD" "$REPEATS" "$JOB_BUDGET_MINUTES"; do`. After: `for count in "$CORPUS_PER_SHARD" "$JOB_BUDGET_MINUTES"; do`.

**A4, exact.** Before: `echo "corpus_per_shard, repeats and job_budget_minutes are 1 through 9999" >&2`. After: `echo "corpus_per_shard and job_budget_minutes are 1 through 9999" >&2`.

**A3 is the site that fails loudest.** `fanout` runs under `set -euo pipefail`; remove `REPEATS` from `env:` and leave `"$REPEATS"` in the loop, and the step dies on an unbound variable on every dispatch. **A5 is the site that fails most obscurely:** an undeclared `inputs.repeats` makes `fromJSON` fail at expression evaluation and every qualification dispatch dies before a step runs.

**The CLI cannot read a config default at parser-build time.** `backend/idhazh/cli.py` builds the parser before it loads settings. Follow the `--cap` idiom already in the file: declare `--repeats` with `default=None`, then after `settings = config.load(args.config)` resolve

```python
repeats = settings.app.run.qualification_repeats if args.repeats is None else args.repeats
```

**The BUDGET verdict names the count, and no contract changes.** `backend/idhazh/evals/qualify.py` already carries `Budget.repeats`, set from `{shard.repeats for shard in shards}` with a disagreement check. Only the `threshold=` string in `budget()` moves, to `f"{budget_.job_budget_minutes:.0f} min per job, at {budget_.repeats} passes per item"`. `QualificationShard.repeats` and `QualificationReport.repeats` stay - they record what ran.

**A new test, and it belongs here.** `backend/tests/workflows/test_workflow_inputs.py`: every `${{ inputs.<name> }}` any workflow expression reads is declared in that workflow's `inputs:` block. Eight modules under `backend/tests/workflows/` parse `validate.yml` and not one asserts this. It does not cover A3 - that site reads a shell variable, not an input - so the `git grep` gate below is A3's control.

### Section 2b - Files, measured 2026-09-22

`.github/workflows/validate.yml`, `backend/idhazh/contracts/knobs/run.py`, `backend/idhazh/cli.py`, `backend/idhazh/evals/qualify.py`, `config/idhazh.json`, `schemas/app-config.schema.json` and `frontend/src/contracts/app-config.ts` (both generated), `backend/tests/test_qualify.py`, `backend/tests/workflows/test_workflow_inputs.py` (new), `docs/how-to/evaluate-new-summarizer-model.md`.

Shares `config/idhazh.json` with P4.

### Section 2c - Acceptance gates

- `ruff check backend`, `ruff format --check backend`, `mypy backend` clean.
- `pytest backend/tests/test_qualify.py backend/tests/workflows/` green, including the new test.
- **`git grep -n 'repeats' -- .github/workflows/validate.yml` returns nothing.** This is A3's and A5's control.
- `python -m idhazh qualify --help` still lists `--repeats`.
- `python -m idhazh.contracts.export` regenerates both `app-config` artefacts byte-identical to what the commit carries. Adding a knob moves them; if they are not in the commit the drift gate fails in CI.

### Section 2d - Oracle: prove a gate can fail

Set `"qualification_repeats": 2` in `config/idhazh.json` and confirm the config load refuses it by name. Then delete the `REPEATS` env line but leave the loop word, and confirm a workflow-parsing test or a shell lint catches it. Restore both from the commit, not from the working tree.

**What this oracle cannot settle:** that `--repeats 4` on a real dispatch still produces four passes. Only a live qualification run shows that, and none is in scope here.

### Section 2e - Decisions

| # | Decision |
| --- | --- |
| 1 | The flag stays. An operator overriding one run without editing config is what it is for; what leaves is the dispatch input. |
| 2 | `ge=3`, not `ge=1`. A knob whose legal range includes a value this row calls a silent failure is a trap, not a knob. |
| 3 | The threshold string is a label, not the mechanism. It names the count on the artefact for free. |
| 4 | The range loop and its message survive. They guard `corpus_per_shard` and `job_budget_minutes`, which this row does not touch. |

## Section 3 - Row 2: the spent utilities go, and the keep-rule is written down

**Level 2.** Waits on nothing. Ships with row 3 as P2.

**Why.** Two are migrations whose last unmigrated row has aged out. The third measured a question that has since been answered and written down.

### Section 3a - The shapes this row needs

None. Three file deletions and one `## Design rationale` section.

**The keep-rule, written into `docs/reference/documentation-structure.md` before the deletions, in the same commit:** an instrument a documentation page cites stays, because deleting it makes the page's number unreproducible. A migration whose last row has aged out goes. Name the three utilities this rule just removed and at least one it protects.

### Section 3b - Files, measured 2026-09-22

`backend/utilities/backfill_day_metrics.py`, `backend/utilities/migrate_item_health.py`, `backend/utilities/measure_definition_placement.py` and their tests; `docs/reference/documentation-structure.md`.

### Section 3c - Acceptance gates

- `ruff check backend`, `mypy backend` clean; `pytest backend/tests/` green.
- `git grep -n 'backfill_day_metrics\|migrate_item_health\|measure_definition_placement'` returns nothing outside `docs/archive/`.
- **No page under `docs/`, including `docs/reference/benchmarks/`, cites a number produced by any of the three.** `docs/archive/` is exempt; `docs/reference/benchmarks/` is not.

### Section 3d - Oracle

For each of the three, name in the commit message the store its last row would have lived in and show that store holds no unmigrated row: `python -m idhazh.cli <the store's read verb>` over the committed tree, or the utility's own dry-run flag. A deletion with no such sentence is not ready.

**What this oracle cannot settle:** whether a store that is empty today stays empty. It cannot - the migration is what emptied it.

### Section 3e - Decisions

| # | Decision |
| --- | --- |
| 1 | The rule is written before the deletions, in the same commit. A rule written after describes what somebody already did. |
| 2 | Archived measurement pages are not edited. They are dated records of what was true then. |

## Section 4 - Row 3: the hosted span sink goes

**Level 2.** Waits on nothing. Ships with row 2 as P2.

**Why.** It is a runtime call to a third party from a build-time producer, which Guardrail #1 and CLAUDE.md section 1b both refuse. It has no configured endpoint, so no run has been observed to send anything.

### Section 4a - The shapes this row needs

The hosted sink class in `backend/idhazh/telemetry/sinks.py` and its export from `backend/idhazh/telemetry/__init__.py` go. The knobs in `backend/idhazh/contracts/knobs/observability.py` that configure it go, which regenerates `schemas/app-config.schema.json` and `frontend/src/contracts/app-config.ts`. The call sites in `backend/idhazh/stages/work.py` and `backend/utilities/probe_feeds.py` lose the hosted branch and keep the local one. The `langfuse` extra and its mypy override leave `pyproject.toml`.

**The local span record stays.** It is the only trace this project keeps and nothing about it crosses the network.

### Section 4b - Files, measured 2026-09-22

`backend/idhazh/telemetry/sinks.py`, `backend/idhazh/telemetry/__init__.py`, `backend/idhazh/contracts/knobs/observability.py`, `backend/idhazh/stages/work.py`, `backend/utilities/probe_feeds.py`, `backend/tests/test_spans.py`, `backend/tests/contracts/test_telemetry_surface.py`, `pyproject.toml`, `schemas/app-config.schema.json` and `frontend/src/contracts/app-config.ts` (both generated), `docs/concepts/telemetry.md`, `docs/how-to/run-the-gates.md`, `docs/reference/documentation-structure.md`.

Shares `stages/work.py` with P5 and `schemas/app-config.schema.json` with P1 and P4. **P2 lands first and the others rebase**, because P2's hunks are the large ones.

### Section 4c - Acceptance gates

- `ruff check backend`, `mypy backend` clean; `pytest backend/tests/test_spans.py backend/tests/contracts/test_telemetry_surface.py` green.
- `git grep -rn 'langfuse'` returns nothing outside `docs/archive/`.
- `uv sync` resolves with the extra gone and the lockfile in step with the manifest.
- Both `app-config` artefacts regenerate byte-identical to what the commit carries.

### Section 4d - Oracle

Run one pipeline stage end to end on the canary day and confirm the local span record still holds the same span names it held before. The sink going away must not take a span with it.

**What this oracle cannot settle:** whether the hosted sink ever sent anything in a past run. The claim rests on a snapshot of config, not on history.

### Section 4e - Decisions

| # | Decision |
| --- | --- |
| 1 | The local span record stays. |
| 2 | The two generated files ship in the same commit. They are generated, not hand-edited (CLAUDE.md section 10). |

## Section 5 - Row 4: the retrieval loaders take their bounds

**Level 3.** Waits on nothing.

**Why.** Three tests read every published day and every committed month shard to answer questions that are bounded. Guardrail #12 is about exactly this: a cost that rises because the repository accumulated more data, with no change to the question. None of the three was ever declared under the escape hatch.

### Section 5a - The shapes this row needs

**The two loaders take different bounds, because they answer different questions.**

`load_corpus` takes `through: str | None = None` and filters on the day directory in the path **before opening a file**. That is the pin, it is what `Corpus.through(date)` and `assist.eval_corpus_through` already configure, and it keeps every gated number byte-identical: 32 published days exist and 6 are at or before the configured pin of `2026-08-26`, so the same rows survive and the read drops about 5x.

**`load_index_corpus` takes no `through`.** It globs `index/[0-9][0-9][0-9][0-9]-[0-9][0-9].json` - **month shards, not day directories** - so a day pin cannot filter it at the file level, and filtering rows after opening every shard would bound nothing. It already carries the right bound: `months`, newest first, with `min_days` as the one-more-shard rule, both read from `assist.search_months` and `assist.search_min_days`. Pass them. `None` - every committed month - is what makes the read grow.

**That bound is a trailing window, so the live measurement stays gated.** `months` newest-first is at most `months` shards whatever the archive accumulates, which is Guardrail #12's "another explicit input". It is also still live - it reads the newest shards, which is what a reader's tab reads - so the reading does not go stale and nobody has to remember to run it.

**One thing moves to `backend/utilities/measure_retrieval.py`, and one only**: the membership check that asserts the index names every published item. That genuinely needs both whole collections at once and no bound can answer it. Print the same lines the test printed.

**The drift test is deleted, not moved.** It compares a scored count against the corpus count and expects the corpus to be larger; with the corpus pinned, both sides are pinned and it cannot fail. What it protected - a gated number drifting as the archive grows - is now structurally impossible because the loader takes the pin. Say that in the commit message.

**Precedence, so a worker does not have to choose.** `load_index_corpus(root, months=..., min_days=...)` keeps its current meaning exactly; `through` is not added to it. `load_corpus(root, through=...)` gains one parameter and has no others.

### Section 5b - Files, measured 2026-09-22

`backend/idhazh/evals/retrieval.py`, `backend/tests/test_retrieval_eval.py`, `backend/utilities/measure_retrieval.py` (new), `docs/concepts/growing-reads.md`, `docs/concepts/evaluation.md`.

### Section 5c - Acceptance gates

- `pytest backend/tests/test_retrieval_eval.py` green, and **every gated number byte-identical to the pre-change run.** Capture the report summary line before and after and diff them.
- No `REPO_ROOT`-rooted unbounded corpus or index load remains in the test module. `git grep -n 'load_index_corpus' -- backend/tests/` shows every call passing `months`.
- `python backend/utilities/measure_retrieval.py` runs and prints the membership check.
- **`docs/concepts/growing-reads.md` gains the three reads as closed, and gains the operator surface.** The page never listed them - it has no occurrence of `retrieval`, `load_corpus`, `load_index_corpus` or `live_report` - so this is an addition, not a deletion. A gate asking a worker to remove rows that were never there is a gate that passes for free.

### Section 5d - Oracle

Add a published day after the pin to a fixture tree and assert `load_corpus(root, through=<pin>)` returns the same row count as before. Then call it with `through=None` and assert the count rises. That proves the filter does the work rather than the data happening to be small.

**What this oracle cannot settle:** whether the pinned six days are still the right six. That is an editorial question about `eval_corpus_through`, not a question about the loader.

### Section 5e - Decisions

| # | Decision |
| --- | --- |
| 1 | The pin goes into the loader, not into a gold-day fixture. A fixture would make the live measurement identical to the pinned one and stop measuring live search quality without anything going red. |
| 2 | The live index measurement stays in the gated suite, on the trailing window the loader already has. Only the membership check moves, because no bound can answer it. |
| 3 | `load_index_corpus` gets `months`, not `through`. It globs month shards; a day pin cannot filter them. |
| 4 | The drift test is deleted. Both sides are pinned after this row, so it cannot fail. |

### Section 5f - Refused

| Alternative | Why not, and what it would cost to take |
| --- | --- |
| Move `live_report` to an operator surface too | It is the only measurement of live search quality in the project, and a utility with no scheduled caller is an instrument deleted on a delay. Taking it would cost that reading, and buy nothing the trailing window does not already give. |

## Section 6 - Row 5: the label queue becomes runnable

**Level 2.** Waits on nothing.

**An earlier draft of this plan deleted the human-label path. That is withdrawn, and this row replaces it.** The deletion failed this plan's own test - what goes blind when the instrument leaves - and three things went blind.

**Why the deletion was wrong.** `docs/concepts/adaptive-pruning.md` lists `state/labels.csv` as "Keep, always", "the only ground truth here, and the one file in `state/` a person wrote rather than a machine", and states separately that it "is never deleted at any age". That is a retention contract, and the earlier seventeen-path census missed it. `docs/concepts/evaluation.md` names four structural controls in its "Discouragement is not a control" paragraph - the required `labeller` checked against `evaluation.labellers`, the human-paced CLI with no `--from-file`, no `--model` and no stdin, the `seconds_spent` floor, and the test in `backend/tests/test_labels.py` forbidding the draw module from importing `idhazh.llm`. Those four are the only mechanical block on the quality loop closing on itself, and CLAUDE.md section 1a now lets a model verdict decide publication. Removing the independent check in the same quarter the judge was given that authority is the wrong order.

**"Zero rows" was a finding about the roster, not the need.** `config/idhazh.json` carries `"labellers": []`. An empty roster makes the required `labeller` check refuse every write, so the instrument has never been runnable. Zero of 60 is what an unrunnable instrument reads.

**Why this row instead.** Three documented open questions are all blocked on the same missing measurement, and the thing blocking it is an empty list: the faithfulness band thresholds' error rate, the direction of `evaluation.chunk_words`, and which geometry is truer after the measured 0.40 slicing penalty.

### Section 6a - The shapes this row needs

None minted. `LabelRow`, its schema, its TypeScript twin and its two fixtures all stay exactly as they are.

`config/idhazh.json` gains at least one name at `evaluation.labellers`. `docs/concepts/evaluation.md` gains the sampling-design `## Design rationale` section - how a faithfulness sample is drawn and why - and its "0 of 60" sentence is corrected to say the roster was empty until this date, so the next reader does not read the zero as demand.

### Section 6b - Files, measured 2026-09-22

`config/idhazh.json`, `docs/concepts/evaluation.md`, and whatever `backend/utilities/label_queue.py` writes to `state/labels.csv`.

Shares `config/idhazh.json` with P1.

### Section 6c - Acceptance gates

- `backend/utilities/label_queue.py` runs end to end against a **temporary** state root, and the row it writes validates against `LabelRow`. **No row is committed to `state/labels.csv`.** Amended 2026-09-22: this gate used to ask for one row in the committed ledger, which contradicted decision 3 below and would have had an agent write human ground truth - a fabricated label is indistinguishable from a real one in the only file this project treats as that.
- The four structural controls still hold: `labeller` required and checked, the CLI still has no `--from-file`, no `--model` and no stdin, the `seconds_spent` floor unchanged, and the import ban in `backend/tests/test_labels.py` still green.
- `pytest backend/tests/test_labels.py backend/tests/test_evidence.py` green.

### Section 6d - Oracle

Set `evaluation.labellers` back to `[]` and confirm the write is refused by name. Restore from the commit.

**What this oracle cannot settle:** whether one sitting of labels is enough to move any of the three open questions. It is not - it is the first reading, and the page that consumes it says how many it needs.

### Section 6e - Decisions

| # | Decision |
| --- | --- |
| 1 | The deletion is withdrawn. The row failed the plan's own second rule, so there is nothing to weigh. |
| 2 | The sampling-design rationale is written into `docs/concepts/evaluation.md` either way. It was the best part of the withdrawn row and it costs nothing. |
| 3 | Taking the first labels is a person's sitting, not an agent's. Estimated at 60 rows at roughly 90 s each, about 90 minutes in one pass - an estimate, because the `seconds_spent` floor is the only pace this project has recorded (Guardrail #10). |

### Section 6f - Refused

| Alternative | Why not, and what it would cost to take |
| --- | --- |
| Seed the queue with model pre-labels for a person to confirm | Confirmation is anchoring; it turns an independent measurement into an agreement rate with the model. Taking it would cost the independence that is the whole reason the file exists, and buy perhaps an hour. |
| Delete the path anyway | Then nothing in this project measures the faithfulness judge's error rate. The only human-labelled set left is the similarity holdout, which scores the merge judge and never sees a summary. The band thresholds become permanently unfalsifiable, `evaluation.chunk_words` keeps a value this project's own page calls no longer neutral, and the judge that CLAUDE.md section 1a lets decide publication has no independent check of any kind. That sentence goes in front of the owner if the deletion is ever revived. |

## Section 7 - Row 6: the pipeline test commits what it already wrote

**Level 3.** Waits on P2, which edits `backend/idhazh/stages/work.py` in large hunks.

**Why.** The dispatch runs two models over the same articles and already writes every answer to disk - the per-item summary payload, the run's input manifest, and an item-health day file under the trial root. The job has `permissions: contents: read` and no commit step, so all of it is deleted when the runner is torn down.

**Why it mints nothing.** An earlier draft proposed a fourteen-column ledger. Every value in it is already produced, in shapes already declared, and then thrown away: `work.py` writes `items_dir / f"{item.item_id}.summary.json"` under the `Summary` contract, calls `_write_inputs(items_dir, inputs=inputs)` under `PipelineInputs`, and `recorder.note(date=plan.date, run_id=plan.run_id, ...)` records the identity columns on `ItemHealthRow`. A minted row would re-derive what exists into a CSV cell - and the fold codec, the column list and the case-id knob the earlier draft needed all existed only to serve that re-derivation. **The cheapest contract is the one you did not have to define.**

**Why it is not an extension of `ItemHealthRow` either.** That would put five new columns on every production item row for the rest of the archive, and model prose inside a census row. The production store's meaning is a census of what happened, not a copy of what was written.

### Section 7a - The shapes this row needs

**None minted, and none extended.** Three things move.

**1. The case becomes the trial root name.** `backend/utilities/pipeline_case_config.py` already loops the cases and writes each one's config, so it holds `case.id` at that moment. It sets `run.trial_state_dirname = f"pipeline-tests/{case.id}"` in the copy it writes. Three cases then write three roots and nothing shares a path. This replaces the earlier draft's `case_id` knob and its filename-grammar problem: the three cases share one `plan.json`, so one `run_id`, run `work` with no `--shard`, so `shard=0`, in one job and one attempt - four identical fields, one filename, three writers.

**2. A second job commits.** The case job keeps `permissions: contents: read`. A new job takes the write.

| Field | Value |
| --- | --- |
| Name | `commit` |
| `needs` | the case job |
| `if` | `always()` |
| `permissions` | `contents: write` |
| Steps | checkout; `actions/download-artifact` with `merge-multiple: true`; **validate every downloaded payload against its contract and refuse the push on any failure**; `bash .github/scripts/commit-and-push.sh state/pipeline-tests` |

The validation step is the control, not the job split - the job split only bounds the blast radius. The bytes derive from fetched web pages through a model, `if: always()` means a failed case job's output still arrives, and `merge-multiple: true` lets one artifact land on another's path. `.github/scripts/commit-and-push.sh` is the path `validate.yml` and `measure.yml` already push this tree with; **plan 44 carries a blocked row that deletes it, so re-census that path at execution time** (section 0a).

**3. The prune learns to find the trial roots.** Measured 2026-09-22: `config/idhazh.json` sets `"trial_state_dirname": null`, `_prune_trial_shards` in `backend/idhazh/stages/prune_state.py` returns before it does anything when that value is unset, and the nightly prune runs the production config. **Nothing has ever pruned `state/pipeline-tests/`**, and the two host-fingerprint day files committed there on 17 and 19 September are still there.

**Setting the knob in production config is not the repair, and is refused by name:** `backend/idhazh/cli.py` redirects `common.STATE_ROOT` to `state/<trial_state_dirname>` on every stage but `prune-state`, so a production value would move the daily pipeline's own ledgers into the trial root.

**`_prune_trial_shards` takes its roots from the tree instead.** A child directory of `state/` whose name is not in `STORE_DIRNAMES` - a new `frozenset` in `backend/idhazh/ledger.py` holding the store directory constants already declared there - is a trial root, and every trial root is pruned against `retention.trial_state_days`. The list gains a name in the same commit that adds a store, because a store is created through its constant, so discovery cannot fall out of step. Inside a root nothing else changes: `day_shards.shard_files` still refuses a stray, so a root misidentified by a missing constant loses aged-out day files and nothing newer. **When a prune empties a trial root, the root itself is removed** - without that the child count under `state/` only ever rises (Guardrail #12).

**What the workflow says now is false after this row, in three places, and P5 owns all three.**

| id | Path | What row 6 must change |
| --- | --- | --- |
| B1 | `.github/workflows/idhazh-pipeline-tests.yaml` header comment | "It publishes nothing. No step writes `frontend/public/`, no step commits, and nothing here is on any reader's path." becomes: it publishes nothing a reader sees, no step writes `frontend/public/`, and it does commit one thing - a `commit` job appends the case output under `state/pipeline-tests/`, the trial root `validate.yml` and the bench already commit into and no console page reads. The case job keeps `contents: read`. |
| B2 | `backend/tests/workflows/test_pipeline_tests_workflow.py` | It asserts `"git commit" not in text` and `"git push" not in text`, which would stay green by accident because `commit-and-push.sh` contains neither word. **Amend it explicitly** to assert the `commit` job holds `contents: write` alone, the case job holds `contents: read`, and the pushed path is `state/pipeline-tests` and nothing wider. |
| B3 | `docs/reference/github-actions.md` | Carries the same "It publishes nothing: no step writes `frontend/public/`, no step commits" claim. Same correction, in that page's voice. |

**Defect 20 is untouched.** `frontend/scripts/build-state.ts` `isInput` names it: a producer filing receipts about a scratch tree into a production ledger path - `idhazh validate-days` writing `state/day-validations.csv`. This writes into the trial root, which is where a trial producer is supposed to write. `state/` stays a prerender input and every committed row changes the tree fingerprint, which is the same cost `digest.yml` pays daily - a rebuild, not a failed check, and `run-checks.ts` only refuses when an input moves *during* a run, which a commit on a runner in its own checkout cannot do.

### Section 7b - Files, measured 2026-09-22

`backend/utilities/pipeline_case_config.py`, `backend/idhazh/stages/work.py`, `backend/idhazh/stages/prune_state.py`, `backend/idhazh/retention.py`, `backend/idhazh/ledger.py`, `.github/workflows/idhazh-pipeline-tests.yaml`, `backend/tests/workflows/test_pipeline_tests_workflow.py`, `backend/tests/workflows/test_staged_paths.py`, `backend/tests/retention/`, `docs/reference/github-actions.md`, `docs/reference/repository-layout.md`.

Shares `stages/work.py` with P2 and `ledger.py` with plan 46; whichever lands second rebases.

### Section 7c - Acceptance gates

- `ruff check backend`, `mypy backend` clean; `pytest backend/tests/workflows/ backend/tests/retention/` green.
- **`prune-state` run against the production config - `trial_state_dirname` unset, exactly as `config/idhazh.json` carries it - deletes an aged-out day file under a trial root in a fixture state tree, and removes the root once it is empty.** A gate that sets the knob to make the prune run tests a configuration production does not have. Assert the file is gone and the child count under the fixture root falls by one.
- **A declared store's aged-out day file under the same fixture root is untouched by the same call.** That is what holds `STORE_DIRNAMES` honest.
- The three declared cases write three trial roots. `config/pipeline-tests.json` declares `baseline`, `no-visual-decision` and `parallel-2`; assert three distinct `trial_state_dirname` values come out of `pipeline_case_config.py`.
- The case job keeps `permissions: contents: read`; the `commit` job holds `contents: write` alone.

### Section 7d - Oracle

Restore the `if run is None or not run.trial_state_dirname: return []` early return in `_prune_trial_shards` and confirm the first prune gate goes red. A gate that stays green against the old code is measuring the fixture, not the prune. Restore from the commit.

**What this oracle cannot settle:** that the `commit` job actually pushes on a real dispatch. Only a live dispatch shows that, and its duration on the run page is what replaces the 40-to-70-second estimate with a number.

### Section 7e - Decisions

| # | Decision |
| --- | --- |
| 1 | Nothing is minted. Every value an earlier draft would have copied into a CSV cell already exists in a declared shape that this run already writes. |
| 2 | The case is the trial root's name, not a column and not a filename field. Three cases, three roots, no shared path. |
| 3 | The commit job validates before it pushes. The job split bounds the blast radius; the validation is the control (Guardrail #11). |
| 4 | The prune finds trial roots by enumeration, not by the knob. The knob is `null` in production and cannot be set there without moving the daily pipeline's own ledgers. |
| 5 | The workflow's "no step commits" claim is overruled by name in all three places that carry it, not left to go quietly false. |

### Section 7f - Refused

| Alternative | Why not, and what it would cost to take |
| --- | --- |
| Mint a `PipelineTestSummaryRow` with a column per value | It re-derives what already exists, and costs a contract, a schema, a TypeScript twin, a fixture, an encoder, a write site, a prune path, an ownership entry and a Level 5 pause. It buys nothing the committed payloads do not already carry. |
| Extend `ItemHealthRow` with the missing columns | Five new columns on every production item row for the rest of the archive, and model prose inside a census row. It costs the production store's meaning. |
| One day directory per case | `retention.prune_trial_state` walks a trial root one level and hands each child to `day_shards.shard_files` expecting a day tree directly beneath it, so a case level above the ledger makes every child a directory of directories the walk refuses as a stray. It costs a prune rewrite. |

## Section 8 - Row 7: the generated contract layer goes, and the contract catches up

**PAUSE before the pull request opens** (section 1b). **Level 5.** Waited on all of plan 46, which landed on 2026-09-23.

**What it waited for, and what arrived.** Plan 46 minted contracts under the rule this row deletes and had rows still writing into both directories this row removes whole. All of that is settled on `main`: `schemas/digest-run-fragment.schema.json` and its generated frontend twin are committed and nothing further is being minted, and `frontend/src/lib/server/host-fingerprint.ts` is on its final shape. Plan 46's plan-doc is deleted and git holds it. **The checkable gate is spent** - it named a file that no longer exists, and nothing replaces it. Its one surviving row is the corpus ref move, now [`20260923-48-the-corpus-ref-move-plan.md`](20260923-48-the-corpus-ref-move-plan.md), which mints no contract, touches no schema, and is not scheduled. **Re-read the generated layer against the tree before starting**: the schema count below was taken before plan 46 added to it.

**Why.** A full generator runs on every contract change to serve six names in two frontend files. Sixty-five schemas are generated and sixty-one are read by nothing but the gate that checks they were generated.

### Section 8a - The shapes this row needs

**The six names the frontend inlines.** Exactly two frontend modules import from `frontend/src/contracts/`. Every other mention of "contracts" in the frontend is a comment pointing at a Python module.

| Where | Name | Kind | From |
| --- | --- | --- | --- |
| `frontend/src/lib/server/config.ts` | `ConsolePanelGroup` | type | `appearance-config` |
| `frontend/src/lib/server/host-fingerprint.ts` | `SERVER_JOB` | value | `host-fingerprint-row` |
| `frontend/src/lib/server/host-fingerprint.ts` | `HostFingerprintRow` | type | `host-fingerprint-row` |
| `frontend/src/lib/server/host-fingerprint.ts` | `ServerJob` | type | `host-fingerprint-row` |
| `frontend/src/lib/server/host-fingerprint.ts` | `WATCHED_FLAG` | value | `machine-panels` |
| `frontend/src/lib/server/host-fingerprint.ts` | `WatchedFlag` | type | `machine-panels` |

`HostFingerprintRow` is the 31-field hand copy. Copy it from the generated file before deleting it, keep the field order.

**Four tests replace the generator**, each named for what it proves and each given its filename so four workers write one file.

| File | What it proves |
| --- | --- |
| `backend/tests/contracts/test_frontend_field_set.py` | the hand-written `HostFingerprintRow` in TypeScript names exactly the fields the Pydantic `HostFingerprintRow` declares - no more, no fewer, and the same types |
| `backend/tests/contracts/test_frontend_vocabularies.py` | the TypeScript `SERVER_JOB` and `WATCHED_FLAG` literals hold exactly the members their Python enums hold |
| `backend/tests/contracts/test_no_generated_layer.py` | no `schemas/` or `frontend/src/contracts/` path is reachable, and `idhazh.contracts.export` no longer exists as a module |
| `backend/tests/workflows/test_workflow_inputs.py` | already added by row 1; this row does not touch it |

**What survives in `backend/idhazh/contracts/base.py`.** `json_schema()` stays - it is `model_json_schema()` plus this project's canonicalisation, and `canonical_json(cls.json_schema())` is what the stamped-boundary and drift checks compute over. `__schema_stem__` keeps its name: it is the stable published key and the fixture map reads it. Only its docstring changes.

**`CONTRACTS` moves to `backend/idhazh/contracts/__init__.py`.** It is the registry, not part of the generator. **Six modules import it for real and each breaks loudly**: `backend/tests/contracts/_fixtures.py` (which builds the stem-to-class map the whole contract tier drives from, and fails first), `test_judge_call.py`, `test_retired_fingerprint.py`, `test_schema_drift.py`, `test_stamped_boundary.py`, `test_typescript_contracts.py`. The last two also take `expected_filenames`, `export`, `expected_type_filenames` and `export_typescript`, which go away with the generator.

**Five more files describe the export module in prose.** They break nothing and running the suite will not find them: `backend/idhazh/contracts/derived.py` (which explains that its models are deliberately not exported - a sentence that means nothing once nothing is exported), `contracts/judge_call.py`, `contracts/typescript.py`, `backend/tests/council/test_metrics_sink.py`, `backend/tests/workflows/test_telemetry_cli.py`.

**The sweep.** `idhazh-export-schemas`, `contracts.export`, `schemas/`, `expected_filenames`, `export_typescript`, `module_text` across `pyproject.toml`, `.github/workflows/`, `CLAUDE.md`, `AGENTS.md`, `docs/` and `frontend/scripts/`.

**The engineering-contract amendments. Eight clauses in `CLAUDE.md` plus `AGENTS.md`, exact text.**

| # | Clause | Now | After |
| --- | --- | --- | --- |
| 1 | Guardrail #3 | "Every downstream artifact (DB migration, API spec, frontend type, cross-service binding) is generated from that schema, never hand-written." | "A downstream artifact is derived from that model at the moment it is needed. Where a copy must cross into another language, it is small, hand-written, and held in step by a named test." |
| 2 | Section 1a, Pydantic bullet | "`schemas/*.schema.json` is generated from those models, and the frontend's TypeScript types and validators are generated from those schemas." | "A contract can produce its own JSON Schema on demand through `json_schema()`. The frontend carries a small hand-written copy of the few shapes it needs." |
| 3 | Section 1a, same bullet | "A CI drift gate regenerates both and fails on any diff. Nobody hand-edits a generated artifact." | "Two tests hold the hand copy in step: one over the field set, one over the vocabularies." |
| 4 | Section 1a, Schema-first bullet | "conforms to a generated schema in `schemas/`; a config or payload that fails its schema fails the build" | "conforms to the contract that declares it; a config or payload that fails validation fails the build" |
| 5 | Section 9 | "- [ ] Contract drift gate green: schemas and frontend types regenerate byte-identical to what is committed." | "- [ ] The frontend field-set and vocabulary tests are green for any contract the frontend copies." |
| 6 | Section 10 | "- Hand-edit a generated artifact (`schemas/*.schema.json`, `frontend/src/contracts/*`). Edit the Pydantic model and regenerate." | "- Change a frontend contract copy without changing the Pydantic model, or the reverse. The two tests that bind them are not optional." |
| 7 | Section 11 | "and `schemas/<name>.schema.json` is generated from it" | "and its JSON Schema is computed from it on demand" |
| 8 | Section 13 | "- **Contract** - the generated schemas vs the readers and the writers, plus the drift gate." | "- **Contract** - the model against its readers and its writers, plus the two tests binding the frontend copy." |
| 9 | `AGENTS.md` | "the contracts generated from `backend/idhazh/contracts/`" - two occurrences | "the contracts declared in `backend/idhazh/contracts/`" - restates the amended clause and adds nothing (CLAUDE.md section 5) |

The same pass corrects the four pages that describe the generator as a running thing: `docs/architecture/contracts/schemas.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/ci-model-runtime.md` and `docs/reference/repository-layout.md`.

### Section 8b - Order, and it is not negotiable

1. Confirm the plan 46 gate above returns 0.
2. Copy the six names into hand-written TypeScript.
3. Add the three new tests and watch them pass **against the generated layer still in place**. A test that has never passed against the old layer proves nothing about the new one.
4. Only then delete `schemas/` (65 files) and `frontend/src/contracts/` (65 files), the generator, and re-home `CONTRACTS`.
5. Amend `CLAUDE.md` and `AGENTS.md` in the same commit. A contract requiring a layer that no longer exists is a contract the next agent will follow.

### Section 8c - Files, measured 2026-09-22

`schemas/` (all 65), `frontend/src/contracts/` (all 65), the six real importers and five prose mentions above, `backend/idhazh/contracts/export.py`, `typescript.py`, `base.py`, `__init__.py`, `frontend/src/lib/server/config.ts`, `host-fingerprint.ts`, `frontend/scripts/run-checks.ts`, `test-scope.ts`, `tests/test-scope.test.mjs`, `copy-visuals.mjs`, `pyproject.toml`, `.github/workflows/ci.yml`, `CLAUDE.md`, `AGENTS.md`, `docs/architecture/contracts/schemas.md`, `docs/architecture/contracts/determinism.md`, `docs/reference/ci-model-runtime.md`, `docs/reference/repository-layout.md`, `docs/how-to/run-the-gates.md`, `docs/reference/agent-notes/gates-and-builds.md`, `docs/reference/agent-notes/shell-and-tools.md`.

### Section 8d - Acceptance gates

- `ruff check backend`, `mypy backend` clean; `pytest backend/tests/` green.
- `npm --prefix frontend run check` clean. There is no `npm run lint` in this repository.
- The three new tests pass **before** the deletion and after it.
- `git grep -rn 'idhazh-export-schemas\|contracts\.export\|expected_filenames\|export_typescript'` returns nothing outside `docs/archive/`.
- `.github/workflows/ci.yml` no longer runs a drift gate with nothing to check.
- **Browser smoke** (CLAUDE.md section 12): load the console route that reads the host fingerprint, confirm zero new `[error]` and zero new `404`, and confirm the page still renders with its data file absent. The six names live in `frontend/src/lib/server/`, which runs at prerender time, so the published bytes should not move - but a `lib/server` module that fails to import breaks prerender for a whole route, and that is what the smoke catches.

### Section 8e - Oracle

Add a field to the Pydantic `HostFingerprintRow` and confirm the field-set test goes red. Remove a member from one of the two enums and confirm the vocabulary test goes red. Restore both from the commit.

**What this oracle cannot settle:** whether the 31 fields were copied with the right **types**. Proving the test catches an added field says nothing about a field copied as `string` that should be `number`. The field-set test asserts types for that reason; read its failure message before trusting it.

### Section 8f - Decisions

| # | Decision |
| --- | --- |
| 1 | `json_schema()` stays. The generator goes; the ability to ask a contract for its schema does not. |
| 2 | `__schema_stem__` keeps its name. It is the published key and the fixture map reads it; only its docstring changes. |
| 3 | `CONTRACTS` moves to `contracts/__init__.py`. It is the registry, not part of the generator. |
| 4 | The contract amendment is in this pull request, not a follow-up. |

### Section 8g - Refused

| Alternative | Why not, and what it would cost to take |
| --- | --- |
| Delete only the 61 schemas nothing imports | The count is a fact about today. Tomorrow's contract adds a sixty-sixth and the generator still runs in full. It would cost a second pass later and buy a smaller diff now. |
| Keep the schemas, delete the TypeScript | The schemas are the larger half at 970,649 B against 546,670 B, and the less read half. It keeps the cost and drops the part that has a reader. |

## What this plan measured, and what it only estimated

| Claim | Status |
| --- | --- |
| 20 of the last 200 commits touch `schemas/` or `frontend/src/contracts/` - one in ten, so about one review in ten opens on a regenerated diff | Measured 2026-09-22 |
| The drift gate costs 0 s, 0 s and 2 s on `ubuntu-latest` over the three most recent runs that ran it - about 1 s of a job, which is not a reason to delete the layer. The case for row 7 is reviewer attention, not runner seconds. The local export takes 13 to 48 s on a contended developer machine, which is a developer number and never a runner number | Measured 2026-09-22 |
| `schemas/` 970,649 B + `frontend/src/contracts/` 546,670 B = 1,517,319 B, and 23,589 + 9,221 = 32,810 lines | Measured 2026-09-22 |
| 32 published days, 6 at or before the pin `2026-08-26` | Measured 2026-09-22 |
| Row 6's `commit` job at 40 to 70 s, 0.5 to 0.9 percent of the 140-minute dispatch budget | **Estimate.** No run has executed this job. The first dispatch's `commit` duration replaces it. |
| One sitting of labels at about 90 minutes | **Estimate.** The `seconds_spent` floor is the only pace recorded. |

## See also

- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the workpool, readiness and the merge rule.
- [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the environment and every gate command.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - Guardrail #12's escape hatch, which row 4 edits.
- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the three open questions row 5 unblocks.
- [`docs/reference/agent-notes.md`](../docs/reference/agent-notes.md) - the tool quirks that make a command lie, including the search timeouts in section 0a.

