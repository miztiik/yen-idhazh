# Plan 50 - Idhazh Gardener: one utility tends every ledger

**Last Updated**: 2026-09-29

**Level**: 5 (CLAUDE.md section 6). It changes a persisted contract, the project's persistence format, and the one workflow that force-pushes `main`. The owner's rulings recorded in section 0 and in each row ARE the design consultation; the ESCALATE triggers name what still stops a worker.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star this plan serves; section 0's intent map says which of its eleven statements this plan delivers and which it only clears the way for. Locally: one utility tends every ledger; its config decides what happens and when; it runs the decision tree every day; nothing depends on anything else. **Contract**: section 5 below declares every persisted shape, path, key and exit code in full. **Code**: the twelve rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; **keep a running pool of parallel N = 2, refilling a slot the moment a worker returns its report and never waiting on a merge** - section 1 names the pairs that run two-wide; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Execution handover (zero-context cold start)

A paste-ready brief for an agent that picks this plan up with no prior context. [execute-a-plan.md](../docs/how-to/execute-a-plan.md) is the canonical contract; this brief adds only what this plan's run has learned. Written 2026-09-27, about 20:10 UTC, and brought up to date 2026-09-28, about 12:15 UTC, when the first owner handed over after row 5 merged, about 14:00 UTC, when the second owner's dispatch checks on row 7 added deviations 96 to 101 and row 12, about 17:30 UTC, after row 7 merged, and 2026-09-29, about 06:15 UTC, when the third owner's session ran out of context with row 8 ready to merge and row 12's worker ended mid-row, about 06:40 UTC, when the person ruled on row 9's two open questions, and about 07:30 UTC, when the fourth owner had merged row 8 and dispatched rows 12 and 9 side by side (deviation 137), and about 08:40 UTC, when row 12 had merged and row 9 was dispatched again from main (deviation 146).

```text
You are the OWNER of TODO/20260924-50-idhazh-gardener-plan.md. You have no prior context.
Execution is AUTHORIZED (owner, 2026-09-27): deliver it end to end with a running pool,
settle any ambiguity by debate (two or more personas from .github/agents/, asked in
parallel, converging on one ruling), record every deviation in the table below, and stop
only on an ESCALATE trigger (section 0).

STEP 0 - COLD START. Read CLAUDE.md, docs/how-to/execute-a-plan.md, docs/how-to/ship-a-pr.md
and docs/how-to/run-the-gates.md. Then read this plan's section 0, section 1 (the Status
Reckoner, the only tracker) and each row just before you dispatch it.

STEP 1 - ADOPT OR CLOSE. Run git worktree list, gh pr list and git branch -r. At the last
update (2026-09-29, 08:40 UTC) rows 1 to 8, 11 and 12 had merged (#1127, #1131, #1142,
#1139, #1145, #1141, #1151, #1156, #1136, #1161) and row 10 is collapsed. Row 9 is the
last row and is in flight (STEP 2). If its worker ended without a report, read worktree
p50r9, its pushed branch and %TEMP%\p50r9\report.md before dispatching it again. The
owner's worktree, p50own, holds no unpushed work.
Section 0's three plan-54 reads ran before row 5 and all three came back empty.

STEP 2 - DISPATCH. Row 8's findings are deviations 118 to 131 and three open questions
for a person (section "Open questions for a person, from row 8"); ESCALATE trigger 1 was
answered with A3 (deviation 130). Refill a slot on a report, never on a merge. Two
workers started together return together (deviation 94).
  row 8              merged as #1156 at 07:05 UTC 2026-09-29, after its branch took main
                     in and CI went green, with no digest.yml or prune.yml run queued or
                     running. Worktree p50r8 and its branch are removed
  row 12             merged as #1161 at 08:26 UTC 2026-09-29 by its worker (deviation
                     138), with no digest.yml or idhazh-gardener.yml run queued or
                     running. Its departures from the row are deviations 139 to 144.
                     Worktree p50r12 and its branch are removed
  row 9              IN-FLIGHT, finishing in two waves from about 12:40 UTC 2026-09-29
                     (deviation 153). Worker p50-r9-worker-3 in worktree p50r9, branch
                     p50r9-the-console-ledgers-become-parquet, fixes the backend.
                     Worker p50-r9-worker-fe in worktree p50r9fe, branch
                     p50r9fe-the-console-readers-read-parquet, moves the frontend
                     readers. Their reports are %TEMP%\p50r9\report.md and
                     %TEMP%\p50r9fe\report.md. Then one worker merges p50r9fe into
                     p50r9, runs the migration and opens the pull request. Its first
                     worker ended with nothing committed (deviation 146), and its
                     second pushed five commits (deviations 147 to 152).
                     The person's rulings are deviations 135 and 136, read with 112,
                     132 and 133. It deletes CSV trees a digest run writes, so it
                     merges as row 3 was merged (deviation 52): no digest.yml
                     or idhazh-gardener.yml run queued or running, and the migration run
                     again just before the merge. sliceFromDisk() is on main in
                     frontend/src/lib/server/ledger-disk.ts; do not build it here.
                     A plain git push here is refused (403); push with
                     git -c credential.helper= -c 'credential.helper=!gh auth
                     git-credential' push origin <branch>

STEP 3 - GATES. A worker runs `npm --prefix frontend run test:changed -- --list`, then only
its row's named acceptance gates, then pushes and reports. CI is the one full-suite run
(CLAUDE.md section 9). No local full-suite run, and no run through
backend/utilities/gate_lock.py: that lock is shared by every worktree on this machine, and
one run waited 27 minutes behind another plan's.

STEP 4 - MERGE. GitHub refuses auto-merge on this repository, so merge by hand when CI is
green: gh pr merge <N> --repo miztiik/yen-idhazh --squash --delete-branch, run from outside
the repository, then confirm with gh pr view and remove the worktree and its local branch.
Run from a worktree, gh pr merge exits 1 even when the merge worked. A row that changes a
workflow a scheduled run is using, or a file a scheduled job also writes, reads deviations
52 and 54 for when it may merge. Each row stamps its own Reckoner line and the lines sit
next to each other, so the second of two open pull requests conflicts on this file. Merge
origin/main into its branch, keep both lines and push. Never rebase and force-push.

STEP 5 - CLOSE. When every row is DONE or COLLAPSED, follow the closing section of
execute-a-plan.md.

WATCH, whoever owns the plan on the day:
  2026-09-30 02:40   the first idhazh-gardener.yml run (cron 00:40 UTC, created about two
                     hours late): every task is report-only except the squash, and each
                     task's record lands under state/raw/gardener. Once row 12 has
                     merged, its fold is live as well
  about 2026-10-29   the first squash that rewrites history replays six September merge
                     commits. If one carried a change of its own, the program stops with
                     exit 2 before any push, for a person (deviation 82)
```

### Deviations and owner rulings to date

Every place where the tree, or a ruling, departs from the text further down. A worker reads the lines for its row before it starts.

| # | Row | The plan said | What is true, and why | Authority |
| --- | --- | --- | --- | --- |
| 1 | 1 | `retention.py` is 1,880 lines | It is 1,819 | Found at dispatch |
| 2 | 1 | The list of names that move | It missed `BYTES_PER_MB` in `stages/site_weight.py`, and `_STAGED_DIGEST_DIRNAME` | Found at dispatch |
| 3 | 1 | `site_weight.py` defines `PAGES_HARD_CAP_MB` | It is defined in `contracts/knobs/retention.py`, so it is imported and never defined twice | Found at dispatch |
| 4 | 1 | A new `backend/idhazh/site_weight.py` | `stages/site_weight.py` already existed. The plan's name stood, as `assemble.py` beside `stages/assemble.py` already does | Plan owner |
| 5 | 4 | Row 4 edits `host-fingerprint.ts` | Row 2 made that edit, so row 4 touches no frontend file (row 4 decision 7) | Found at dispatch |
| 6 | 2 | Row 2 depends on row 1 | Both ran from main at once. They shared one docstring line in `assemble.py`, and row 2 merged first | Plan owner |
| 7 | 2 | Row 2's file list | `docs/architecture/contracts/schemas.md` also quotes `SERVER_JOB`, so it changed with it | Found at dispatch |
| 8 | 7 | `backend/idhazh/ledger/settle.py` is new | It is already on main. Read it at dispatch and write only what is missing | Found at dispatch |
| 9 | 2, 8, 9 | pyarrow's install is re-measured on `ubuntu-latest` before row 2 merges, and rows 8 and 9 read that figure | Dropped: pyarrow is adopted whatever it costs. Section 4, section 5.9, row 2, row 8 decision 8 and row 9 say so | Owner ruling, 2026-09-27 |
| 10 | 3, 4 | Rows 3 and 4 run two-wide | Row 3 depends on row 4: it sets `grain: "raw-and-compact"`, the value row 4 adds to `Grain`, and the two rows share three files | Found at dispatch; Fowler and Carmack |
| 11 | 7, 11 | Row 7 declares the four index shapes | Row 11 declares them now, so plan 51's query door does not wait for the compaction | Plan 51's owner asked, 2026-09-27; Fowler and Carmack ruled |
| 12 | all | AUTO-merge on green (the line above section 0) | GitHub refuses auto-merge on this repository. Merge by hand on green | Found at merge |
| 13 | all | A worker runs the test selector locally before merge | Only the row's named gates run locally. CI is the full run, and the local test lock is shared | Plan owner, CLAUDE.md section 9 |
| 14 | 4, 8 | Row 4 moves `github_collections.py` to `gardener/tasks/`, and row 8 creates `gardener/tasks/github_collections.py` | Row 4 moves it to `backend/idhazh/gardener/github_collections.py`, beside `one_at_a_time.py`. Row 4 creates an empty task package (section 5.9.5), and discovery refuses a module there that has no `KIND` and `run` (section 5.5). Row 8 leaves the GitHub code where row 4 puts it and adds `tasks/collection.py`, holding only `KIND` and `run`: `bind()` looks for a module named for the task, then for its kind, so a task module named `github_collections` would never be found | Fowler and Carmack, 2026-09-27 |
| 15 | 4, 8 | `config/idhazh_gardener.json` ships `attempts: 5` with `shards: 5` | It ships `attempts: 6`. Section 5.2 refuses `attempts` at or below `shards`, so the committed value failed its own check. The refusal stays, with its reason corrected: five shards alone need exactly five attempts, so `attempts` minus `shards` is how many outside or failed pushes one wave can absorb - one, at 6 and 5. The loop does not sleep after its last attempt, so its worst case is about 23 s of sleep and about 40 s in total, an estimate until row 8's observation times it. Every "near 30 seconds" in sections 5.6 and 5.9.11 and in row 8 decision 11 reads "near 40 seconds at `attempts: 6`". The 20-minute `run-tasks` timeout does not move | Fowler and Carmack, 2026-09-27 |
| 16 | 4, 6 | Row 4's scope lists the `corpus-squash` verb | Row 6 adds that verb with its body (row 6's file list). Row 4 ships `list-tasks`, `plan-shards` and `run-task`, and no placeholder for the fourth | Plan owner; Fowler agreed, 2026-09-27 |
| 17 | 4, 8 | Section 5.2's `GardenerConfig` holds `max_cone_mb` | Row 8 adds `max_cone_mb` with its only reader, the cone-size check, and `cone_mb` on the record (section 5.1). Row 4's `GardenerConfig` holds `version`, `attempts` and `shards`. Row 4 declares all four `TaskPolicy` members, and the `collection` member takes a class name other than `CollectionPolicy`: `knobs/prune.py` already holds a class of that name, and `AppConfig.prune` still reads it until row 8 | Fowler, 2026-09-27 |
| 18 | 4 | Section 5.2's load-time refusals all run in `backend/idhazh/config.py` | The two that need discovery - a declaration no module serves, and a module no declaration uses - run in the shard pre-flight in `runner.py`, and the `deleted_paths` check runs in `publish.py`. Config loads before discovery (section 5.5) | Fowler, 2026-09-27 |
| 19 | 4 | Section 5.6's `publish()` compares the staged set with one equality | Section 5.9.12's three checks apply instead. A write whose bytes already match `origin/main` stages nothing, and it counts as landed when `local_blob(p)` equals `remote_blob(p)`; without that, a harmless rewrite exits 2 | Fowler, 2026-09-27 |
| 20 | 4 | Section 5.5 says row 2's AST walk checks that no task module imports pyarrow or an HTTP client at module scope | No check on main covers a task module. Row 4 adds one that runs `discover()` and then reads `sys.modules`, modelled on `test_the_facade_does_not_load_pyarrow`, so an import that arrives through a support module is caught too | Carmack, 2026-09-27 |
| 21 | 4 | Row 4's file list | It also touches `backend/idhazh/contracts/app_config.py` (it imports `PruneConfig`), `docs/how-to/prune-a-collection.md` and `docs/concepts/atomic-deletes.md` (they link the moved module), the docstring of `backend/tests/retention/test_prune_range.py`, and the two samples in `tests/fixtures/contracts/collection-prune-row/`, written again through the widened model. Section 5.3's `is_eligible` oracle belongs to row 4 as well | Found at dispatch |
| 22 | 4 | Row 4's file list names no contract for the plan payload | Row 4 declares `backend/idhazh/contracts/gardener_plan.py` (`GardenerPlan` and `ShardPlan`, section 5.9.7), because its `plan-shards` verb and `backend/utilities/gardener_shards.py` are that payload's first writers (Guardrail #3). A test holds the two writers to the same bytes | Plan owner, 2026-09-27 |
| 23 | 4 | Section 5.3's `is_eligible` oracle: the eligible set is "identical at every one [of the five wakes] except the last minute" | At `after_hours` 24 the set is identical at all five wakes of a day, 23:59 included (the day before has been over 23 h 59 min, not 24 h), and first changes at 00:00 next day. With whole hours the set can never change between 23:00 and 23:59. And "no wake time changes the answer" is false for a knob that is not a whole day: at 30 hours a day turns eligible at 06:00, between the 00:40 and 12:00 wakes. Tests pin all three plus the exact instant. Whether `compact_after_hours` should be whole days is a question for row 7 | Fowler and Carmack, 2026-09-27 |
| 24 | 4 | Section 5.2: the plan job reads four keys, `lifecycle_status`, `owns` or `owns_everything_else_under`, and `after`. The split rule is unstated | `after` is stale (nothing uses it; row 7 rules out placement keys). The plan job reads `lifecycle_status`, `kind` (to leave out `history`) and `owns`. The split is round-robin over sorted active non-history names into `min(shards, tasks)` shards, so none is empty. `any_active_task` means "a task the matrix runs is active": a registry with only a history task gives the empty shape, so row 8 must gate the history job on something else | Fowler and Carmack, 2026-09-27 |
| 25 | 4 | `prune_artifacts.py` imports follow; nothing else changes | Its `--record` flag is removed with its docs. The widened row needs a run id, attempt, job, shard and timing a hand-run pass does not have, and nothing read the file | Fowler and Carmack, 2026-09-27 |
| 26 | 4 | Section 5.1 keeps the validator `(stopped_because is exhausted) == (resume_from is None)` | A `failed` row may carry `resume_from: null` when the pass failed before it could name a member; `exhausted` must be null and `ceiling` must name one. `take()` now carries a listing or describe failure as `PruneInterruptedError` with the partial `Pass`, so a failure after deletes still records them, and `Pass.more_to_do` reads `stopped_because`. Carmack preferred naming the first owned prefix; Fowler's null won because a prefix is a fake position no reader can tell from a real one and a collection task owns no prefix | Fowler, 2026-09-27; Carmack dissent recorded |
| 27 | 4 | `run-task NAME \| --shard N` runs and lands a shard | `idhazh gardener run-task` runs the tasks and writes the record, and never pushes; it takes the commit as a required `--git-sha`. The shard a wake runs is `python backend/utilities/gardener_publish.py NAME \| --shard N --run-id R --attempt A`, the same line without `--git-sha`, built from the same parser. (An earlier head of #1139 gated landing on a `--publish` flag; deviation 40 is why the flag went) | Fowler and Carmack, 2026-09-27; the move is the worker's, 2026-09-27 |
| 28 | 4 | File list: `schedule.py` | The typed planner is `gardener/shards.py`, and `gardener/context.py` (`TaskContext`) and `gardener/listing.py` (operator listings) are new, one question each. `schedule.py` holds `ended_at` and `is_eligible` only | Fowler and Carmack, 2026-09-27 |
| 29 | 4 | `discover()` walks `backend/idhazh/gardener/tasks/` | `discover(package=tasks)` takes the package as a Python-only parameter, memoised per package, so tests run real fixture task modules from `tests/fixtures/gardener/task_packages/`. No config or CLI value reaches it | Fowler and Carmack, 2026-09-27 |
| 30 | 4 | (not in the plan) | `backend/tests/workflows/test_ledger_staging.py` learns the raw-and-compact grain, and `state/raw/gardener` joins `LEDGERS_AN_OWNER_WRITES`: the runner writes it through `ledger.persist` and `publish()` stages it file by file, which the derivation cannot follow. Teach the derivation `persist` when a second ledger moves onto it | Fowler and Carmack, 2026-09-27 |
| 31 | 4 | `Pass` gains `written`; `max_deletes_per_run` widens to `int \| None` | `Pass.ceiling` and `take(ceiling=...)` also take `None` = no ceiling, so a null in a declaration reaches the record as null rather than as a large number | Carmack, 2026-09-27 (Fowler: only if row 4 can pass None, which it can) |
| 32 | 4 | Refusals 11-15 in `config.py`, with no day/month rule | All five are implemented. A days-against-months comparison is made where it is hardest to pass: the fewest days the kept months can hold against the most the needed ones can (1 month 28 to 31 days, 12 months 365 to 366, 14 months 424 to 428); the same unit compares numbers. A pair reaches back `daily_keep_days` plus `monthly_window`. Refusal 12 reads as `fewest(monthly_window) >= daily_keep_days + 31`. The owner may move these to row 7 | Fowler (owner call to move), Carmack (keep in row 4), 2026-09-27. Kept in row 4 by the plan owner |
| 33 | 4 | (not in the plan) | `bind()` refuses a module whose `KIND` differs from the declaration's `kind`, exit 2 in the pre-flight. The run identity: `--run-id` and `--attempt` are required, `job` is `history` for a history task and `run-tasks` otherwise, `git_sha` is read before any task runs, and the producer is `gardener.runner` (the plan's worked example says `gardener.tasks`) | Fowler and Carmack, 2026-09-27 |
| 34 | 4 | (not in the plan) | `backend/utilities/ledger_families.py` counts a raw-and-compact ledger under each root on its own line; it would have printed 0 for the gardener. The registry refuses a raw-and-compact prefix other than the ledger's own name, because the five root builders file it under that name | Fowler and Carmack, 2026-09-27 |
| 35 | 4 | Section 5.5: every path in `Pass.taken` and `Pass.written` sits under `owns` | A `collection` task is checked on `written` alone, and its `taken` never reaches `Shard.deleted_paths`: what it takes are GitHub ids, not repository paths | Worker, 2026-09-27 |
| 36 | 4 | Section 5.9.12: three staged-set checks, in the order writes, strays, deletions | The stray check runs first, so a folder handed over as a write is reported as the files it staged; each check has a failure case of its own in `test_publish.py` | Worker, 2026-09-27 |
| 37 | 4 | Section 5.9.7: one line from `json.dumps(payload, separators=(",", ":"))` | Both writers add `sort_keys=True`, so the parity test compares bytes that cannot differ by key order | Worker, 2026-09-27 |
| 38 | 4 | File list: `path()`, `relpath()` and `tree_root()` refuse a `raw-and-compact` ledger | `tree_relpath()` refuses it too, with the same message. It is the fourth builder that reads the registry, and leaving it out would hand a caller the old CSV folder of a moved ledger | Worker, 2026-09-27 |
| 39 | 4 | File list: `backend/tests/gardener/` (the registry tests would be `test_registry.py`) | The registry tests are `backend/tests/gardener/test_task_registry.py`. `backend/tests/test_marks.py` keys every test module by its file stem, and `backend/tests/council/test_registry.py` already holds that stem | Worker, 2026-09-27 |
| 40 | 4, 6, 8 | Hard scope and the file list: `backend/idhazh/gardener/` holds the commit loop (`publish.py`), and the runner reads `git_sha` before any task | The commit loop is `backend/utilities/gardener_publish.py`, which also reads the commit and is the entry point a shard runs. The package keeps `runner.py` (runs, records, hands back a `Shard`) and a new `outcome.py` (exit codes, `Shard`, `Outcome`). Why: `backend/tests/test_canaries.py::test_no_pipeline_module_can_turn_a_string_into_an_action` refuses `subprocess`, `os.system`, `pty` and `shlex` anywhere under `backend/idhazh/` - the injection defence's rule that the package reading the open web holds no machinery to act - and CI run 36357672718 failed on it. Every other git call in the repository already lives under `backend/utilities/`. **Rows 6 and 8 inherit this**: the corpus squash cannot run git from a task module under `gardener/tasks/`, and the workflow's shard step runs the utility, not `idhazh gardener run-task` | Worker, 2026-09-27; the canary is a trust-boundary control, so it was kept and not adapted |
| 41 | 11 | Oracle: "every refuse case raises, with the ledger and the period or date in its message" | Only the three validator refusals name the ledger and the day or period. Four cases are refused by the field types alone - a `.csv` name, a fractional-second `listed_at`, a leftover `file_count`, a bare run number in `run_id` - and those errors name the field and the bad value. Section 5.9.13 specifies exactly this, so the oracle line was what was wrong | Fowler and Carmack, 2026-09-27 |
| 42 | 11 | Scope: "one sample for each of the three shapes that is a file" | Seven samples, one for each accepted payload section 5.9.13 prints, so each accept case exists once as a file the byte-for-byte round trip also checks. No test treats the illustrative monthly sizes as measured | Fowler, 2026-09-27; Carmack preferred three |
| 43 | 7 | Row 7 reads these files; the plan does not say whether a refusal names the file | A field-type error names neither the ledger nor the day, and `Contract.read()` names the path only for a file written under an older version. Row 7's reader names the path on any refusal | Carmack; Fowler agreed, 2026-09-27 |
| 44 | all | STEP 3: a worker pushes and reports, and the owner merges on green | A worker waits for its own CI run and fixes a red one before it reports, because the owner does not implement a delegated row. Row 4's worker ran out of context after its CI went green and before it reported; the owner adopted #1139 from the worker's notes and the green run. Every worker now keeps a running report file so that stays possible | Plan owner, 2026-09-27 |
| 45 | 6 | Row 6 puts `corpus_history.py` in `backend/idhazh/gardener/` and keeps `push_rewritten_history.py` | `backend/utilities/corpus_history.py` holds the five functions and is the one program the history job runs after its full clone: boundary, squash, replay, record the run, push. Its module scope is standard library only; `idhazh` is imported inside the function that needs it. It absorbs `push_rewritten_history.py`, whose refusal and exit 1 move across word for word, and the tests that pin them follow (`backend/tests/workflows/_harness.py`, `test_prune_push.py`). Deviation 40's canary refuses git under `backend/idhazh/`, and one process means the force-push decision never crosses workflow steps as an environment string | Fowler and Carmack, 2026-09-27 |
| 46 | 6 | The verb `idhazh gardener corpus-squash`, and a task module whose `run` calls the squash | There is no such verb. `config/gardener/corpus-squash.json` and `backend/idhazh/gardener/tasks/corpus_squash.py` exist, and the task's `run` does only the step that needs no git: `corpus.record_run`. The utility binds that task through the registry's two lookups and calls it between the replay and the push. It never lands through `gardener_publish.publish`, whose `reset --mixed origin/main` would throw the rewrite away | Fowler and Carmack, 2026-09-27 |
| 47 | 6 | `squash_history`: "if the boundary is None, return 0 having written nothing" | The run is recorded whether or not anything was worth squashing, as `prune.yml` does today, and pushed without force when nothing was rewritten. Otherwise the history job takes a full clone and an install every day from 2026-09-29 until a commit is 60 days old, about 20 wakes. Only a refused push leaves the run unrecorded | Fowler and Carmack, 2026-09-27 |
| 48 | 6 | The boundary is the newest commit at or before the cut, found by `git rev-list --before` | The cut reads author dates. `--before` reads committer dates, and a rebase gives every replayed commit the squash day as its committer date, so after a real squash the next two due wakes found nothing: squashes landed every 90 days and history reached back 150, where CLAUDE.md section 8 says 60 to 90. A test squashes one repository twice, 30 days apart, and the second squash finds commits to collapse | Fowler and Carmack, 2026-09-27 |
| 49 | 6 | Row 6's file list | It also edits `.github/workflows/prune.yml`: the due step runs `corpus_squash_due.py`, and the squash, stamp and push steps become one run of `corpus_history.py`. Without that edit the next daily wake fails on a file this row renames and a CLI verb it retires. The file's name, cron and job shape stay for row 8 | Fowler and Carmack, 2026-09-27 |
| 50 | 6 | Section 5.2: a declaration added with its module ships `dry_run: true` | `corpus-squash` ships `dry_run: false`, and the history job honours the flag, so `true` really stops the squash. The squash has run live since 2026-08-28 by owner decision (CLAUDE.md section 8), so `false` transcribes today's behaviour and ESCALATE trigger 6 does not fire. The review-gate test names `corpus-squash` alone as its exception and cites that decision | Fowler and Carmack, 2026-09-27; the live squash is the owner's decision of 2026-08-28 |
| 51 | 3 | Row 3's file list names no workflow | After row 3, `stages/plan.py`, `stages/assemble.py`, `stages/prune_state.py` and `telemetry/publish/source_health.py` read or write parquet, and `digest.yml` runs `pip install -e .` without the `parquet` extra (row 9 was to add it). Row 3 gives every workflow job that reaches either ledger pyarrow, with `cache-suffix: parquet` (section 5.9.11). Without it every visual-prune write fails behind `continue-on-error`, and the plan and assemble stages fail on their first retirements read | Carmack; Fowler, 2026-09-27 |
| 52 | 3 | Row 3 merges like any other row | It merges only inside the 22:34 to 03:00 UTC gap, with no `digest.yml` run queued or in progress. A run checks out the commit it was created at, so a stale run's CSV append conflicts with the deleted file, and `commit_and_push.py` stops that push - a lost digest day if that run retired a feed. Just before the merge, main is merged in, `migrate_csv.py` runs again (it is idempotent), `--check` passes and CI is green. A day file that appears after the merge is migrated by running it again | Fowler and Carmack, 2026-09-27 |
| 53 | 3 | Deviation 30: teach `test_ledger_staging.py`'s derivation `ledger.persist` when a second ledger moves onto it | Row 3 moves two ledgers onto it, so row 3 teaches it | Found at dispatch |
| 54 | 6 | Row 6 merges like any other row | Row 6 rewrites `corpus/corpus.meta.json`, which `digest.yml`'s weekly harvest also writes (next on 2026-10-01) and which has no merge driver. So it merges on a day no harvest runs and not while `prune.yml` runs. `prune.yml`'s next due wake, 2026-09-29 23:37 UTC, finds no commit older than its cut, so the first live run of the new program only records the run and pushes without force | Plan owner, 2026-09-27 |
| 55 | 3 | Install the parquet extra with a `cache-suffix` on `actions/setup-python` | The action has no `cache-suffix` input, so the four jobs install `.[parquet]` and keep the shared pip cache key. Rows 4 and 8 of the plan still prescribe it, and row 8 drops it | Carmack, 2026-09-28; checked against the action's inputs |
| 56 | 3 | Each writer's file names the commit that wrote it | CLI `--commit` (default 40 zeros) feeds a required `commit_sha` to `stage_plan` and `stage_prune_state`; digest plan and prune-state, validate plan and measure runtime pass it; a workflow test requires it | Fowler and Carmack, 2026-09-28 |
| 57 | 3 | The staging test knows which ledgers a job writes | The derivation also follows `ledger.persist` calls and the `cli.main` hand-over verbs, failing by name on one it cannot map; `state/raw/gardener` left `LEDGERS_AN_OWNER_WRITES` | Fowler, 2026-09-28 |
| 58 | 3 | Readers load the raw files | A file this build cannot read (`ValueError`) is skipped with one warning naming its path; `ImportError` still stops the run; each file loads alone | Fowler and Carmack, 2026-09-28 |
| 59 | 3 | Readers read the raw tree | New `ledger/raw_files.py` and `paths.raw_root`: explicit oldest-first sort, highest attempt per unit, first row per key; `settle.py` loses both ledgers; the unbounded walk is listed in `growing-reads.md` until row 7's compaction bounds it | Fowler and Carmack, 2026-09-28 |
| 60 | 3 | Row 3 is one commit and its Reckoner line the second | The derivation moved unchanged in its own first commit; a merge of origin/main and the row commit follow, so the Reckoner line is the third of row 3's own commits, and one agent-note commit comes after it | Fowler, 2026-09-28 |
| 61 | 3 | The migration refuses a day that disagrees with what is filed | It persists into a scratch directory with the same identity to learn the expected envelope; a re-run must reuse the first `--run-id` | Carmack, 2026-09-28 |
| 62 | 3 | (not named) | `split_visual_prunes.py` and its tests are deleted: it built the 2026-09-08 day tree, which is gone | Worker, 2026-09-28 |
| 63 | 3 | (not named) | `visual-prunes` left `idhazh telemetry prune --target`, which deletes CSV day files; an operator has no range delete of the cleanup record until compaction bounds the raw tree | Worker, 2026-09-28 |
| 64 | 3 | (not named) | `check_seeded_ledgers.py` drops the feed-retirements header check; the plan job stages `state` whole, so a missing folder cannot abort its commit | Worker, 2026-09-28 |
| 65 | 3 | (not named) | The registry refuses an empty `prefix` for every grain, a flat file included | Worker, 2026-09-28 |
| 66 | 3 | (not named) | prune-state files as `job=ASSEMBLE, shard=0`; producer names come from each module's `__name__` | Worker, 2026-09-28 |
| 67 | 3 | (not named) | A retirement files under its `retired_on` day, in the writer and in the migration | Worker, 2026-09-28 |
| 68 | 3 | (not named) | Both retirement causes log one line format; assemble keeps its `::warning` annotation | Worker, 2026-09-28 |
| 69 | 3, 7 | (not priced) | One cleanup row is one 8,008-byte parquet file where it was a 105-byte CSV line: 76 times the bytes, about 14.6 MB a year at five runs a day, measured 2026-09-28 on Windows with pyarrow 25.0.1. Accepted: it is repository history rather than published site, and row 7's compaction folds closed days into one file a day | Worker measurement; priced by the plan owner, 2026-09-28 |
| 70 | 6 | Row 6's four-case table puts "a value that is not a date" under exit non-zero | A null `last_run` counts as due, the same as a missing file. So does a null `pruned_date` when `last_run` is absent. Null is how the contract itself writes "never run". A missing key, a value that is not a `YYYY-MM-DD` day, and a file that is not a JSON object still exit non-zero and print no `due` | Fowler and Carmack, 2026-09-28 |
| 71 | 6 | `every_days` is copied from `finetune.prune_every_days`. Decision 1 makes `finetune.prune_keep_days` the source of the boundary | Both numbers moved into `config/gardener/corpus-squash.json`: `window: {days: 60}` and `every_days: 30`, and both readers take them from there. `FinetuneConfig` refuses the two old names by name and points at the declaration. `HistoryPolicy.window` accepts whole days only. CLAUDE.md section 8 names the new keys; its rule is unchanged. Nothing else read either key | Fowler and Carmack, 2026-09-28; accepted by the plan owner, because two copies of one number would leave one that nothing reads |
| 72 | 6 | The boundary is "the newest commit at or before the cut", and the cut is `now` minus `keep_days` | The cut is 00:00 UTC on `today` minus the window. The boundary is the last commit of the unbroken first-parent run, counted from the root, whose author dates are all at or before the cut. The new root carries the boundary's author date, so a commit authored long before it landed can only keep extra history, never collapse newer work. On `main` at `c8edeedc8`, 11 of 2,696 first-parent commits are out of author-date order, the worst by 3.9 hours | Fowler and Carmack, 2026-09-28 |
| 73 | 6 | `squash_history(repo, *, keep_days, now, message)`, and no run identity | The program takes `--today` (the due step's own reading, so the job reads the clock once), `--run-id <today>-<github.run_id>` and `--attempt`. `squash_history` takes `today`, `dry_run` and a `record` callable. The history job writes no gardener parquet record in this row, because its install has no parquet extra | Fowler and Carmack, 2026-09-28 |
| 74 | 6 | `dry_run: true` stops the squash | A dry run still refuses a dirty tree or a detached head (exit 2). Otherwise it prints the boundary, its author date and the commit count, and writes, records and pushes nothing, so it is due again at the next wake - a clone and an install a day for as long as the flag is on | Fowler and Carmack, 2026-09-28 |
| 75 | 6 | (not in the plan) | A `paused` or `retired` squash is never due, even when forced. The due check prints `due=false`, and the program refuses a declaration that is not active with exit 2 | Carmack, 2026-09-28 |
| 76 | 6 | Exit 2 means a detached head, a dirty tree or a missing boundary sha | Exit 2 also means: HEAD is not on `main`; a replay stopped on a conflict (the rebase is aborted); the replayed tip's tree differs from the tip the job started from; the declaration does not load or is not active; or the task cannot record the run. Each refuses before any push | Fowler, 2026-09-28 |
| 77 | 6 | The tip-moved refusal moves across word for word | Its words and its exit 1 are unchanged. Its inputs are gone: the `BASE_COMMIT` and `SQUASHED` environment values, and the refusal for a missing `BASE_COMMIT`. The program reads the tip itself, before it rewrites anything. ESCALATE trigger 2 did not fire | Found at build |
| 78 | 6 | Section 5.2: a contract test asserts that a declaration added in the same change as its module ships `dry_run: true` | A test cannot see which change added a file, so the gate checks the committed tree: every declaration ships `dry_run: true` unless `LIVE_BY_DECISION` in `test_gardener_config.py` names it with a reason. `corpus-squash` is the only entry, citing the owner decision of 2026-08-28. Turning a task live later means adding a line to that list | Found at build, following deviation 50 |
| 79 | 6 | Row 6's file list | Also changed: `stages/prune_stamp.py` is deleted with its verb; `data_wrangler.py` prints `last_run`; `test_commit_script.py` reads the identity off the commits the program made; `test_stdlib_only_programs.py` holds the due check to the standard library; `test_task_registry.py` and `test_gardener_config.py` no longer assert an empty garden; `test_retention_knobs.py` checks the two moved knobs are refused by name | Found at build |
| 80 | 6 | The shell made the root with `checkout --orphan` and `commit` | The program makes the root with `git commit-tree`: the same tree, no parent and the same message, with no temporary branch and no change to the working tree. `record_run` keeps the signature `stamp_prune` had | Found at build |
| 81 | 6, 8 | (not in the plan) | A person can still record a squash run without squashing, by running `gardener_publish.py corpus-squash` or `idhazh gardener run-task corpus-squash`, which would push `last_run` and delay the next squash by 30 days. Row 8 decides whether the runner refuses a history task outside its own job | Row 6 worker, 2026-09-28; for row 8 |
| 82 | 6 | (not in the plan) | The first real squash, about 2026-10-29, replays six September merge commits, and a plain rebase flattens merges. If one carried a change of its own, the replayed tree differs and the program stops with exit 2 before any push, for a person to decide | Fowler, 2026-09-28; named observation for that wake |
| 83 | 3, 6 | Rows 3 and 6 share no file | After their deviations they shared seven, `backend/idhazh/cli.py` among them. Row 3 merged first, inside the 22:34 to 03:00 UTC gap before any digest run was created, with the migration already current. The owner merged main into row 6 with no conflict, ran ruff and mypy, and let CI run again | Plan owner, 2026-09-28 |
| 84 | 5 | Section 5.5 lists what `TaskContext` carries, and a complement task asserts nothing about the working tree | `TaskContext` also carries `owned_folders` and `git_sha`. `backend/utilities/gardener_publish.py` runs one `git ls-tree -d --name-only -z HEAD -- state/ <each owned folder>`, and `runner.run` takes the answer as a required `committed_folders`, so a complement task's folders come from the commit and are held to the checkout. `idhazh gardener run-task` passes none, and a complement task is then refused by name. A declared folder the commit lacks is logged and skipped | Fowler and Carmack, 2026-09-28 |
| 85 | 5 | `owns` is exclusive, and every path a task writes sits under it | A declaration may name `appends_to`, a list of ledgers that defaults to empty, and `Pass.appended` lists what the task filed there. The runner checks that each appended file is the path `ledger.raw_path()` gives for a listed ledger, the wake's day and the task's own file id and format, exempts it from `owns`, and lands it on a dry run too. `owns` stays exclusive. `visual-prune` files its `visual-prunes` report this way | Fowler and Carmack, 2026-09-28 |
| 86 | 5, 8 | (not in the plan) | From row 5's merge until row 8's, nothing runs the cleanup tasks: `digest.yml` lost its cleanup step, and no workflow runs the gardener yet. Nothing that was being deleted stops being deleted, because the old step ran with `retention.dry_run: true`. The daily `visual-prunes` report pauses until row 8. Before the old passes were deleted, each old pass and its task ran live over their own copy of the real tree on 2026-09-28, and all ten pairs removed and wrote the same files: `traces` removed 92 on both sides, and the other nine nothing yet | Fowler and Carmack, 2026-09-28; the paired run is Carmack's |
| 87 | 5 | Each task selects its own members | Every task selects through `one_at_a_time.take`, and its listing keeps the old walk's pruning by name. `scores` and `telemetry-aggregate` work in whole months: load refuses a series task whose window differs from its full-grain series, or that carries a ceiling, so `Pass.taken` stays a list of file paths. `visual-prune` counts past its fuse itself | Fowler and Carmack, 2026-09-28 |
| 88 | 5 | Which keys leave `config/idhazh.json` | Eleven keys leave with their values unchanged, and each old spelling is refused by name, pointing at its declaration. No declaration records which key it came from: `docs/concepts/config/retention-ages.md` holds that table. `retention.image_months` and the other five `observability.public_*` windows stay. The pair rules, the host floor and the console check on the moved windows run in `config.load_gardener`. `scores` gains a full-grain series of 14 months and an archive kept forever | Fowler, 2026-09-28 |
| 89 | 5 | (not settled in the plan) | `visual-prune` and `digest-fragments` declare `days: 390`, 13 months of 30 days, which is what the old passes computed from `retention.image_months`. Load refuses any value other than 30 times `retention.image_months` | Fowler and Carmack, 2026-09-28 |
| 90 | 5, 8 | Row 5 retires the `prune-state` verb | `idhazh prune-state` stays as an alias. It accepts the old flags, prints the two gardener commands that replace it, says `dry_run` is set per declaration, and exits 2 before it loads config. Its removal condition, on the line that declares it, is row 8 | Fowler and Carmack, 2026-09-28 |
| 91 | 5 | (not in the plan) | The ledger-staging derivation in `backend/tests/workflows/_ledger_derivation.py` followed one call from each verb and never reached a task module, because the runner imports tasks by walking their package. A verb that enters the runner now also enters every module `registry.discover()` returns. CI run 36383719163 failed until it did | Found at build |
| 92 | 5 | (not in the plan) | `backend/idhazh/retention.py` keeps only the helpers the tasks call, and `cutoff` went with its last caller. `test_retention_oracle.py` and `test_trace_tree.py` went with the stage. The list of day-shard readers in `backend/tests/pipeline/test_day_shards.py` names the cleanup tasks where `retention.py` stood; CI run 36406294547 failed until it did | Found at build |
| 93 | 5 | (not in the plan) | The commits ran the tasks first, then the console follow, then the module deletion, and the window move last. Moving the keys first would have needed a bridge that is then thrown away | Fowler, 2026-09-28 |
| 94 | all | STEP 2: refill a slot the moment a worker reports | The tool that starts workers in parallel returns only when every worker it started has finished. So the pool ran in waves of two, and a finished worker's slot waited for its sibling | Plan owner, 2026-09-28 |
| 95 | 5 | Deviation 44: a worker waits for its CI run and then reports | Row 5's worker stopped after its CI run went green, while it wrote its pull request description, and never reported. The owner finished the description from the worker's running report and merged on that green run | Plan owner, 2026-09-28 |
| 96 | 7, 12 | Decision 9: row 7 moves `digest.yml`'s fold step into the gardener, `stages/compact.py` becomes the compaction task's body, and `run.settled_fold_after_days` leaves | Row 7 leaves the CSV fold as it is: the step, the knob, the `compact` verb and `stages/compact.py`. That step folds the eight CSV day trees in `DAY_TREES`, not the parquet ledgers row 7 compacts. Each of those trees already belongs to a retention task that ships `dry_run: true`, and `_refuse_overlapping_claims` refuses a second owner, so no row 7 task may write there. Stopping the fold leaves about 128 extra files a day: each open day holds 5 to 30 writer files a tree, and a folded day holds one, measured on main 2026-09-28. New row 12, after row 8, carries decision 9 for these trees. Until it lands, a CSV day closes after 7 days and a parquet day after 1. Row 7 no longer edits `digest.yml`, so it needs no merge window | Fowler and Carmack, 2026-09-28 |
| 97 | 7 | Row 7 names `ledger/settle.py` as "the read-side settlement over a raw day tree", and names no reader | `settle.py` is the CSV post-merge settlement, and row 7 does not touch it. The raw-tree settlement is `ledger/raw_files.py` (deviation 59). `ledger.load_retirements` reads only raw files, and it has four production callers: `stages/plan.py`, `stages/assemble.py`, `telemetry/publish/source_health.py`, and `file_retirements` in `telemetry/source_health.py`, which skips an address it already retired. So a compaction that deleted raw files would make the pipeline fetch a dead feed again and file it again. A new module reads the monthly files, then the daily files, then calls `raw_files.py` for the raw days no compact index names. `load_retirements` and `load_visual_prunes` switch to it and keep their signatures. Its tests replace `backend/tests/ledger/test_settle.py`, and both loaders' entries in `docs/concepts/growing-reads.md` change | Fowler; Carmack agreed, 2026-09-28 |
| 98 | 7, 8 | (not settled in the plan) | The three compaction declarations ship `dry_run: true`. `backend/tests/contracts/test_gardener_config.py` refuses a live declaration that `LIVE_BY_DECISION` does not name, and a new compaction copies nothing that already runs live. Turning one on is ESCALATE trigger 6, and because deviation 97's reader lands first, that is a config change only. The cost: until a person turns them on, nothing lands under `state/compact/`, and `state/raw/gardener/` grows by one record file a shard a wake. Row 8's first-run check expects each compaction's record, not compact files | Fowler and Carmack, 2026-09-28 |
| 99 | 4, 7 | Section 5.9.5: `compact_after_hours`, "30 gives thirty hours"; rejected alternative 10 keeps six hours open | The knob becomes `compact_after_days`: `int`, `ge=1`, default `1`. `schedule.is_eligible` takes days. Only whole days keep the wake time out of which days qualify (CLAUDE.md section 2, deviation 23); six hours would make the wake time an input just as thirty does. No alias: nothing reads the knob yet, and config files are outside CLAUDE.md section 11 (owner, 2026-09-21). Do not copy section 5.3's 23:59 table row: 23 h 59 min have passed at that wake, not 24 h | Fowler and Carmack, 2026-09-28 |
| 100 | 7 | Decision 4: a day below the watermark that has raw files again is compacted again from the union | The ledger door stamps every row with its writer's `unit_id` and `attempt`. A compact file written through it unchanged would carry the compaction's identity and lose the rows' own, so a re-run's attempt 2 would sit beside attempt 1 instead of replacing it. A compact file keeps each row's original identity columns, so `ledger/persist.py` joins row 7's file list. A re-compaction keeps the highest attempt per `unit_id` first, then the first row per key. Test: compact attempt 1, add an attempt 2 that files fewer rows, compact again, and compare with settling both raw files | Fowler and Carmack, 2026-09-28 |
| 101 | 7 | Row 7's file list | Row 2 already put the four `.gitattributes` lines and the four `paths.py` builders on main, so row 7 writes none of them. `backend/tests/workflows/test_digest_workflow.py` does not exist, and after deviation 96 row 7 edits no workflow | Found at dispatch |
| 102 | 7 | Section 5.3: list every eligible raw day, then run the daily period, then the monthly one | Each pass drops what the windows no longer keep, then folds finished months, then takes due days, and a day's listing is written only when that day is taken. A shard refuses a file it both wrote and deleted, and the planned order does exactly that on a catch-up pass | Carmack; Fowler agreed, 2026-09-28 |
| 103 | 7 | Two modules: `_index_day.py` lists a raw day and writes its index, `compaction.py` does the rest | `compaction.py` holds `KIND` and `run`. Beside it, `_daily_period.py`, `_monthly_period.py` and `_compact_tree.py`, which holds every change a pass decides before anything touches disk; `_index_day.py` only builds the listing. The registry test also accepts a module named after its task kind | Fowler, 2026-09-28 |
| 104 | 7, 9 | Deviation 100: `ledger/persist.py` changes, shape Fowler's call | `persist` writes raw files only, and lost its `tier`, `period` and `built_from` arguments. New `persist_period` writes a compact file and keeps each row's original writer identity, and refuses a row whose own `attempt` or `unit_id` differs from its writer's. The door also gained `render_period`, `load_stored` and a declared row-identity type. `docs/architecture/contracts/persistence.md` says so | Fowler, 2026-09-28 |
| 105 | 7 | Deviation 100: the highest attempt per `unit_id`, then the first row per key | Per unit, only the latest file of its highest attempt counts. Without the "latest file" part, a job that wrote one unit twice in one attempt kept both copies, and an existing test caught it. `raw_files.py` holds the one merge rule, and `pick_current_files` is deleted | Fowler, 2026-09-28 |
| 106 | 7 | (not in the plan) | `ledger/keys.py` holds a table that pairs each ledger with its row type and its key. The `gardener` ledger's key is date, `run_id` and task | Fowler, 2026-09-28 |
| 107 | 7 | Section 5.9.5: a compaction carries the base `window` and `max_deletes_per_run`, and `daily_keep_days` is `ge=1` | A compaction's `window` is fixed to forever and its delete limit to none, in the type itself. `daily_keep_days` is at least 31, one more than the 30 days GitHub allows a re-run. A raw file that lands in a month already folded is refused and left for a person | Fowler; Carmack, 2026-09-28 |
| 108 | 7 | Section 5.2 and deviation 32: load refuses a `daily_keep_days` that leaves less than a whole month before `monthly_window` begins | That refusal is deleted. `monthly_window` counts from the day a month is folded, so the gap it guarded cannot occur. The monthly period holds exactly its window of months on every UTC day, tested across 2027 and 2028 | Fowler and Carmack, 2026-09-28 |
| 109 | 7 | Decision 10: a first run starts at the watermark plus one, bounded by `max_periods_per_run` | A first pass starts on the 1st of a month, from the same function that decides which months are kept. Days and months each get `max_periods_per_run`, and days a re-run wrote into again count first. Raw days in a month already past the window are deleted rather than folded; no such month exists today | Carmack and Fowler, 2026-09-28 |
| 110 | 7 | Section 3's diagrams move unchanged | Redrawn to show the tree after row 7: nothing schedules the gardener yet, `prune.yml` runs the corpus squash alone, the CSV fold still runs in `digest.yml`, every task is report-only, and the reader is `ledger/ledger_files.py`, not the browser. Row 8 redraws them when it schedules the garden | Deviation 96, 2026-09-28 |
| 111 | 7 | Row 7's file list | Also touched: `backend/idhazh/config.py`, `ledger/keys.py`, `ledger/rows.py`, `ledger/__init__.py`, `test_task_registry.py`, `test_gardener_config.py`, `_ledger_derivation.py`, `test_ledger_door_jobs.py`, `persistence.md` and `docs/reference/agent-notes/browser.md`. `docs/reference/github-actions.md` was not: nothing it states changed | Found at build |
| 112 | 9 | (not in the plan) | `scores` rows carry an `attempt` field of their own, and since deviation 104 the door refuses a row whose own `attempt` differs from its writer's. One of the two needs a new name before row 9 moves `scores` onto the door; `persistence.md` says so | Row 7's worker, 2026-09-28 |
| 113 | 7 | (another plan) | Plan 51's freshness paragraph said `compact_after_hours: 24`, and read as if compact files would appear on their own. It now says `compact_after_days: 1` (deviation 99), and one added sentence says every compaction ships report-only until a person turns it on (deviation 98). Corrected on main by this plan's owner | Plan owner, 2026-09-28 |
| 114 | 8 | Oracle: `fetch-depth: 0` appears in exactly one job of one workflow, the history job's second checkout | `ci.yml` already takes two full clones, at its lines 64 and 111, in jobs that never push. The rule's own reason is a job that commits paying for a clone it does not use, so it binds jobs that commit or push: among those, only the history job's second checkout takes `fetch-depth: 0` | Found at dispatch |
| 115 | 8 | Three places name `prune.yml` and move with it: `pages.yml`'s upstream-workflow list, `docs/reference/github-actions.md` and the workflow harness tests | `pages.yml` does not name it: its `workflow_run` list is `[CI, Content refresh]`. Those that do are `docs/reference/github-actions.md`, `backend/tests/workflows/_harness.py`, `test_prune_push.py`, `test_staged_paths.py`, `test_triggers.py`, and a comment in `backend/tests/retention/test_score_ledger.py` | Found at dispatch |
| 116 | 8 | File list: `backend/idhazh/gardener/tasks/github_collections.py` (new) and `backend/tests/gardener/tasks/test_github_collections.py`; trigger 2 names `push_rewritten_history.py` | The task module is `tasks/collection.py`, holding only `KIND` and `run`, and the GitHub code stays in `gardener/github_collections.py`, already tested by `backend/tests/gardener/test_github_collections.py` (deviation 14). The tip-moved refusal that trigger 2 guards now lives in `backend/utilities/corpus_history.py` (deviation 45) | Found at dispatch |
| 117 | 8 | Section 5.9.11 and `prune.yml`'s header: a scheduled run starts 40 to 70 minutes after its cron minute (n=3, 2026-08-23 and 24) | Measured 2026-09-28: the last ten scheduled `prune.yml` runs (cron 23:37) were each created 112 to 139 minutes late, at 01:29 to 01:56 UTC. Over the same five days the last digest run of each day ended between 00:00 and 00:52 UTC, and the first began no earlier than 07:38. So a 00:40 wake starts about 02:30 to 03:00 and its force push lands by about 03:50, inside the gap on either model. Not trigger 4: section 4 holds no drift figure, and the chain fits. Row 8 restates the window derivation (decision 8) with these readings | Plan owner's measurement, 2026-09-28 |
| 118 | 8 | Section 5.1: `cone_mb` on every record row | `cone_bytes`: exact, and empty when a hand run weighed nothing | Fowler, 2026-09-28 |
| 119 | 8 | Section 5.2: `max_cone_mb` of 64 | 768, an estimate. The heaviest shard owns 46.3 MB today and grows about 1.4 MB a day, so 64 would turn red within two weeks and stay red | Carmack, 2026-09-28 |
| 120 | 8 | A shard over the ceiling stops before any task runs | Its tasks still run and its record lands, then it exits 1: stopping first would block the deletions that shrink it | Fowler and Carmack, 2026-09-28 |
| 121 | 8 | Section 5.9.11: `permissions` at workflow level | Set per job, and a test pins them | Fowler and Carmack, 2026-09-28 |
| 122 | 8 | (not in the plan) | Both history checkouts pin `ref: main`; without it the tip check refuses on every due wake | Carmack, 2026-09-28 |
| 123 | 8 | Section 5.9.7: the plan payload | The plan job also outputs one `run_id` for the whole wake | Row 8's worker, 2026-09-28 |
| 124 | 8 | Section 5.6: a complement task asserts nothing about the working tree | The `trials` task's folders are in no shard's checkout, so it would fail at every wake. The shard adds them to its own checkout before any task runs: 952 bytes today | Fowler and Carmack, 2026-09-28 |
| 125 | 8 | The retired `prune` block is refused through `knobs/removed.py` | Through `SUPERSEDED_APP_NAMES` in `contracts/app_config.py`, which is where a retired top-level key is already refused | Row 8's worker, 2026-09-28 |
| 126 | 8 | Deviation 81: whether the runner refuses a history task outside its own job | It does, with exit 2, naming `backend/utilities/corpus_history.py` as the only program that runs it | Fowler and Carmack, 2026-09-28 |
| 127 | 8 | (not in the plan) | A collection declaration names its collection in a `collection` key and is filed under that name; its window is whole days, and it owns no folder. `gardener_shards.py` joins the list of standard-library-only programs | Fowler and Carmack; the list is the worker's, 2026-09-28 |
| 128 | 8 | (not in the plan) | CLAUDE.md section 8 and `AGENTS.md` name `idhazh-gardener.yml`'s history job as the standing force-push exception, no wider than before | Fowler and Carmack, 2026-09-28 |
| 129 | 8 | Deviation 117 and decision 8: the force-push window | The timing test checks the push against the measured busy times of the other scheduled runs. At a start delay of 112 to 334 minutes, an estimate from `prune.yml`'s own lateness, plus 55 minutes of job limits, the push lands between 02:32 and 07:09 UTC. The quiet time runs from 01:23, when the council's latest run ends, to 07:23, when the first digest run is created: 69 minutes of margin before and 14 after. The scheduled wakes before the first due squash, about 2026-10-29, replace the estimate, and the test turns red if the real delay leaves the window | Carmack, 2026-09-28 |
| 130 | 8 | ESCALATE trigger 1 | The owner chose A3 on 2026-09-28: the old name goes in row 8, which merges only after the squash's first live run has rewritten `corpus/corpus.meta.json` and pushed. The worker held the change as a patch outside the repository; the plan owner applied it to #1156 and stamped the changelog entry `2026-09-28T21:00`. Until about 2026-10-28 GitHub allows a re-run of a digest run from before the rename, which would write the old name back; that now stops the harvest and the squash loudly, and cannot cause a wrong force push | Owner, 2026-09-28 |
| 131 | all | (not in the plan) | Plan 52's doc reached main with two lines using the word the ledger sweep refuses, so every pull request's test job failed. The plan owner changed both to "Keep" on main, the words #1154 also carries | Plan owner, 2026-09-28 |
| 132 | 9 | The settled escalation: the build-time readers are `host-fingerprint.ts`, `machine-counters.ts` and `model-work.ts`, and `payload.ts` touches none of these ledgers | Measured on main at e5a0f8718: `model-work.ts` opens no `state/` path, because it computes from rows it is handed. `payload.ts` reads two of the three: `evalRows()` reads `state/scores` and `itemHealthRows()` reads `state/item-health`, and the loaders of `/console`, `/console/machine`, `/console/model` and `/console/voices` call them. `dayShardFiles()` returns no rows for a missing folder, so a row 9 that deletes the CSV and leaves these two in place ships four routes that draw nothing on a green build. Row 9 moves `evalRows()` and `itemHealthRows()` onto `sliceFromDisk()` with `host-fingerprint.ts` and `machine-counters.ts` | Plan 51's owner, 2026-09-28 |
| 133 | 9 | (not in the plan) | `sliceFromDisk()` reads packed files only, and row 9's three packing declarations ship `dry_run: true` (deviation 98), so every reader row 9 moves returns "missing" until packed files exist. A live task also packs at most 8 days a pass from the first of the oldest month, so reaching the present from 1 August takes about eight wakes (estimate). How packed files first reach main is a person's call, asked by plan 51's owner on 2026-09-28: row 9's one-time migration packs every finished day with the packing code and the tasks stay report-only; or the three tasks go live in row 9's pull request with `max_periods_per_run` raised; or they onboard report-only and the four routes show "missing" until they go live. Plan 51's rows 3 and 8 wait on the answer | Plan 51's owner, 2026-09-28 |
| 134 | 12 | Row 12 depends on row 8, and a row is ready when its dependencies are DONE | Row 12 was dispatched on 2026-09-28 stacked on #1156's green branch, because row 8 waited only for its merge condition (deviation 130) and every file row 12 shares with it is row 8's. Row 12's pull request shows row 8's changes until #1156 merges; then its branch takes main in, and it merges after #1156, inside a digest gap | Plan owner, 2026-09-28 |
| 135 | 9 | Deviation 133: how packed files first reach main, three options | The person chose the first. Row 9's one-time migration packs every day the packing rule already admits, with the packing task's own code, and writes each day's file, `index/daily.json` and the daily watermark exactly as a live pass would, so a task turned on later resumes from the right day. Days the rule does not yet admit become raw files, as the row already says. The three packing tasks stay report-only (deviation 98), and turning them on is a later call for a person. The cost: the four routes deviation 132 names show data up to the day the migration ran, and stop there until the tasks go live. Rejected: the tasks going live in row 9's pull request, which switches on deletion in the same merge as the migration; and report-only with no packing, which ships four routes that draw nothing on a green build | Owner, 2026-09-29 |
| 136 | 9 | Row 9's naming correction 4: `EvalRow.attempt` keeps its name and gains a description (owner decision, 2026-09-26) | Deviation 112: the person chose to rename it. `EvalRow.attempt` becomes `summary_attempt`, beside the other three renames, with a `version` stamp and a read-side alias in the same commit and the description correction 4 asked for. The writer's `attempt` on every row keeps its name. Rejected: renaming the writer's `attempt`, which changes a shape every ledger already on parquet has written | Owner, 2026-09-29 |
| 137 | 9, 12 | Row 12's scope: row 9 may move `item-health`, `scores` and `host-fingerprint` first, so row 12 folds whichever trees are still CSV when it is dispatched. Section 1 pairs row 9 with row 8, and row 12 runs after row 8 | Row 12 was dispatched first and folds all eight trees, those three included. Compared at row 9's dispatch on 2026-09-29, the two rows share at least ten files - `.github/workflows/digest.yml`, `backend/idhazh/telemetry/silicon.py`, `backend/idhazh/day_shards.py`, `config/gardener/host-fingerprint.json`, `config/gardener/scores.json`, `config/gardener/telemetry-aggregate.json`, `frontend/src/lib/server/payload.ts`, `backend/tests/test_ledger.py`, `backend/tests/test_silicon.py` and `backend/tests/test_telemetry.py` - and row 9 must take away the live fold row 12 gives the three trees it moves. So row 9 runs beside row 12 stacked on row 12's pushed branch, as row 12 did on row 8 (deviation 134): it writes the files it does not share first, takes row 12's branch in before it edits a shared one, and merges after row 12. Its `Depends-on` gains 12. Holding row 9 until row 12 merged would leave one of the two slots empty for as long as row 12 waits for a quiet merge time | Plan owner, 2026-09-29 |
| 138 | 12 | STEP 4, and the worker rule in `docs/how-to/execute-a-plan.md`: the owner merges and a worker does not | Row 12's worker merges its own pull request by hand once CI is green and no `digest.yml` or `idhazh-gardener.yml` run is queued or running, confirms the merge, and removes `p50r12`. The tool that starts workers hands both back only when both finish (deviation 94), so an owner-only merge would hold a green row 12 for as long as row 9 takes, and row 9 would take a branch in rather than main. The owner still merges row 9, because its migration runs again just before its merge | Plan owner, 2026-09-29 |
| 139 | 12 | Files touched: `backend/idhazh/contracts/knobs/removed.py` refuses `run.settled_fold_after_days` | It is refused through `SUPERSEDED_RUN_NAMES` in `backend/idhazh/contracts/knobs/run.py`, and `removed.py` is untouched | Row 12's worker, 2026-09-29 |
| 140 | 12 | Decision 3 and the dispatch debate: the five task modules that own a tree fold it | One new module, `backend/idhazh/gardener/closed_day_fold.py`, does every fold: the runner calls it after each task's window, with that task's own `fold` block. No task module changed; six declarations carry the block | Row 12's worker, 2026-09-29 |
| 141 | 12 | Decision 3: `LIVE_BY_DECISION` names the fold | `LIVE_BY_DECISION` is keyed by task and key, so a fold's switch is listed apart from its window's. A new `UNFOLDED_BY_DECISION` excuses `candidate-models`, which has no committed tree | Row 12's worker, 2026-09-29 |
| 142 | 12 | Row 5's test: every retention task answers to a recorded pass of the old cleanup | `span-rollup` replaced no pass, so it is named as an exception with its reason, and its own test holds that its forever window takes nothing, dry or live, over twenty months of files. Nothing was invented in `removals.json`, which records what a deleted module did | Fowler, 2026-09-29 |
| 143 | 12 | Files touched | Also `backend/utilities/gardener_publish.py`: it turns rename detection off, so a writer file replaced by its `settled.csv` is staged as a deletion rather than a move. Also three new test files, one record fixture, the knob page, `retention-ages.md` and nine more docs pages. `docs/reference/github-actions.md` never named the fold step and needed no edit | Row 12's worker, 2026-09-29 |
| 144 | 12 | Decision 4: the record contract takes a version stamp | Stamped `2026-09-28T22:07`, when the shape was written; the row merged on 2026-09-29 | Row 12's worker, 2026-09-29 |
| 145 | all | (not in the plan) | The local test selector reads two backend test helpers, `backend/tests/workflows/_harness.py` and `backend/tests/workflows/_ledger_derivation.py`, as inputs every frontend group shares, so an edit to either selects every frontend group and a site build. Found by row 12's worker. It is not this plan's to fix; closure hands it to a row that will | Row 12's worker, 2026-09-29 |
| 146 | 9 | (not in the plan) | Row 9's first worker ended at about 07:46 UTC with no report, no commit and no push; its reading notes are `%TEMP%\p50r9\s001.txt` to `s026.txt`. Row 12 merged at 08:26 UTC, so the second worker builds on main and the stacking of deviation 137 is not needed | Plan owner, 2026-09-29 |
| 147 | 9 | Naming corrections 1 and 3: `source_word_count` becomes `source_words` and `source_seen_word_count` becomes `source_words_before_cap` | By meaning the table is the wrong way round. `source_word_count` is the article's length before the cap, so it becomes `source_words_before_cap`; `source_seen_word_count` is what the model saw after the cap, so it becomes `source_words`. Each name now matches the `ItemHealthRow` field that holds the same fact | Row 9's second worker, 2026-09-29 |
| 148 | 9 | (not in the plan) | `ItemHealthRow.job` and `ItemHealthRow.shard` become `machine_job` and `machine_shard`, with one version stamp, one changelog line and a read-side alias. The ledger door refused every item-health row, because the row's own `job` and `shard` collide with the writer identity the door stamps on every file. Deviation 136 settled the same collision for `attempt` by renaming the row's field and keeping the writer's. `persist` now checks the identity cells before it writes | Fowler and Carmack, 2026-09-29 |
| 149 | 9 | Files touched: a cell-merge rule for `HOST_FINGERPRINT_KEY` in `backend/idhazh/ledger/keys.py` | No new rule. The door keeps its whole-row settle. The clock step reads back its own probe row and files the whole row as a later write of the same work unit, so the newest row carries both halves | Fowler and Carmack in debate, 2026-09-29; Fowler withdrew the cell merge |
| 150 | 9 | Oracle: every row in each committed CSV tree reads back from the parquet | Every row today's CSV reader returns reads back. The migration files each day's rows as `day_shards.settled_day` returns them, one raw file a day, and the compaction's own daily step packs them. The parity check is a one-off operator run, not a test over `state/` (Guardrail #12) | Row 9's second worker, 2026-09-29 |
| 151 | 9 | `UNREAD_CELLS` names 39 of item-health's 122 columns | It names 6 | Found at execution |
| 152 | 9 | (not in the plan) | `DayMetrics`: an instrument's `column` reads a renamed eval column under its new name, with a version stamp and a changelog entry, so a window that spans the rename does not split one instrument into two | Row 9's second worker, 2026-09-29 |
| 153 | 9 | One worker carries a row, and the owner merges it (STEP 4) | Row 9's second worker ended at about 11:55 UTC partway through its tests: five commits pushed, and a rerun of 56 test files read 228 failed, 46 errors and 793 passed. Row 9 finishes in two waves. First, a backend worker in `p50r9` and a frontend worker in `p50r9fe`, on a branch cut from row 9's, whose files do not overlap. Then one worker merges the two, runs the migration, opens the pull request and merges it itself in a quiet time, as deviation 138 allowed row 12 | Plan owner, 2026-09-29 |
| 154 | 9 | Files touched: one `changelog` entry each in `item_health.py`, `eval_row.py` and `host_fingerprint.py` for the move | None for the move: a changelog records a change of shape, and moving where rows are filed changes no field. The renames carry their own entries | Fowler and Carmack, 2026-09-29 |
| 155 | 2, 9 | Row 2 made pyarrow an optional extra, and row 9 decision 4 installs it on three digest jobs | pyarrow becomes a base dependency. Every `.[parquet]` install goes, with the install check and the code only it used; the two tests that keep pyarrow out of every module but one stay. Row 9 found three more jobs that read the door without it, and a check that follows imports would miss the next way in (a Node script starting Python, a verb held in a variable). Cost: a few seconds on about 12 installs that never use it. The 2-second estimate is inside run-to-run noise; the widest gap those timings allow is about 12 s | Fowler and Carmack, second round, 2026-09-29 |
| 156 | 9 | (not in the plan) | `measure.yml`'s bench stages its raw host-fingerprint folder only when the probe wrote one, and says "no machine recorded" otherwise; its test checks that step, not the committed files. The two trial CSV files under `state/pipeline-tests/host-fingerprint/` (952 bytes) stay: section 5.8 gives that tree to a later plan, and migrating them would fire ESCALATE trigger 3 and write about 56 files to carry one row | Fowler and Carmack, second round, 2026-09-29 |
| 157 | 9 | (not in the plan) | The scores task no longer builds a month archive, because it hashed the CSV day files. So no score-index day is dropped, one read grows by a file a day (listed in `docs/concepts/growing-reads.md`), and `compact-scores` stays report-only. Whether a follow-up row builds the archive from the door's rows is put to the person | Row 9's third worker, 2026-09-29 |
| 158 | 9 | (not in the plan) | `idhazh telemetry prune` no longer takes a day of the three ledgers; their days go when their compaction goes live, as row 3 left `visual-prunes`. The migration refuses a day where a late scores row conflicts with one already filed, for a person to fix. The drift review skips a raw file whose rows the contract refuses, with a warning, which is the door's rule for every reader | Row 9's third worker; plan owner, 2026-09-29 |
| 159 | 9 | (not in the plan) | The four console routes read the packed files and say, in one plain line under the route's introduction, when a ledger is not packed yet, did not load, or stops two or more days early. The item-health column list is written once, in `frontend/src/lib/server/ledger-rows.ts`, and a backend test binds it to `ItemHealthRow`. About 25 panels still say "no rows" where the reason is "not packed yet"; plan 52's route rows reword them | Fowler, Jony and Susan, 2026-09-29 |
| 160 | 9 | Deviation 153: one worker finishes the row | Wave 1 ended with both branches pushed, and both merged into row 9's branch with main without a conflict. Wave 2 is a docs worker and a code worker on separate branches; then the owner runs the migration, opens the pull request and merges it | Plan owner, 2026-09-29 |

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Blocked by** | **Nothing. Row 5's only blocker was plan 54's row D1, which landed; plan 54 closed on 2026-09-27 and its plan-doc is deleted.** **Plan 54 decommissioned `state/day-validations/` end to end** - the contract, the `LedgerName` member, the `config/ledgers.json` entry, the retention pass, the knob and the committed tree - so three statements in this plan about that ledger are written against a tree that no longer exists; each is marked below. **The work that made `backend/idhazh/ledger/` a package has landed** (pull requests #1107 to #1115, merged 2026-09-26 and 2026-09-27), so row 2 of this plan already has the package to live in, `LedgerName` in `backend/idhazh/contracts/ledger_name.py` to type its first argument, `backend/idhazh/ledger/paths.py` to add its builders to, and `backend/idhazh/ledger/filenames.py` to add `unit_id`, `file_id` and `_pack_v8` to. What that work left behind is [`../docs/architecture/contracts/ledger-registry.md`](../docs/architecture/contracts/ledger-registry.md): the registry, the seven modules behind the door, and the rule that `ledger/__init__.py` holds imports and nothing else.<br><br>That same work renamed `ledger.py` to `ledger/__init__.py` and `paths.py` to `path_classes.py`, and this file was swept against what it shipped on 2026-09-27. A worker who finds a stale module name in this plan and cannot find the file should stop and say so, never substitute the name it guesses - that guess is how a row silently builds against the wrong module. |
| **Verify before row 5** | **Plan 54 deletes the `day-validations` ledger. This plan checks that it landed and stops if it did not.** Three reads, before row 5 starts, all of which must come back empty: `git ls-files state/day-validations` (the committed tree); `git grep -n -e day-validations -e day_validation -- config` (the registry entry and the knob); `git grep -n -e DAY_VALIDATION -e prune_day_validation -- backend/idhazh` (the `LedgerName` member, its key and rule, and the pass). **Any one of the three finding something is a stop.** Say what was found and wait for a person. **Rows 1 to 4 do not wait**: none of them touches anything plan 54 deletes, checked 2026-09-27. The failure this prevents is row 5's: it turns every pass in `backend/idhazh/stages/prune_state.py` into a task, and while `_prune_day_validation_shards` is still in that module a worker following the rule writes a task, a declaration and a module for a ledger plan 54 is about to delete - three files plan 54 then has to find, and a declaration ESCALATE trigger 6 guards from the day it lands. **The ledger is no longer claimed twice**: `config/ledgers.json` gave it an entry, so the trial sweep has not treated it as a stray since 2026-09-27. |
| Why this plan exists | Four programs delete things on four unrelated schedules, one `--dry-run` flag covers eleven independent decisions, every ledger writes its own format by hand, and two schedulers disagree about when a day is closed. This makes one utility with one verb per task, one config, one persistence door, one record and one safe way to commit. |
| Hard scope - in | - `backend/idhazh/ledger/` is the one door a payload takes to disk, parquet or JSON, with exactly one module importing the parquet engine.<br>- `state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet` is where a new writer files; `state/compact/<ledger>/<period>/...` is what compaction leaves, named for the period it covers - `daily/2026/09/23.parquet`, `monthly/2026/08.parquet`.<br>- `backend/idhazh/gardener/` holds the registry, the schedule, the record and the commit loop.<br>- **Ten of the eleven passes** in `backend/idhazh/stages/prune_state.py` become tasks, each with its own window and its own `dry_run`; plan 54 deletes the eleventh before row 5 runs.<br>- The corpus squash leaves inline shell for a tested Python module.<br>- `backend/utilities/prune_artifacts.py` is deleted and its work becomes two tasks; a utility that is also a task is two places to look.<br>- `.github/workflows/prune.yml` names no task: a standard-library `plan` job splits the tasks into shards, a sharded `run-tasks` job runs them, a `history` job reads its own dueness and rewrites the corpus last.<br>- `digest.yml`'s compaction step moves to the gardener, so one scheduler decides when a day is closed.<br>- **Three of the ten ledgers a console route reads move to parquet here**: `item-health`, `scores` and `host-fingerprint`, plus the two small ledgers that prove the door. **The fourth, `span-rollup`, is deleted rather than migrated**, so row 10 is collapsed and the deletion goes to plan 52's row for the last console route to move, beside the `span-rollup` projection that row already removes. That is three producers in two modules, and it is what lets a later plan delete the six projections under `frontend/public/` that exist only because the build had to do the work in advance. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. Removing the `pruned_date` read-side alias - stop before the commit that removes it, not before the commit that adds it. **The alias has two homes**: `CorpusMeta`'s validator and the standard-library reader the `history` job runs, which cannot import the contract. Row 8 removes both or neither.<br>2. Any behaviour change to the tip-moved refusal in `backend/utilities/push_rewritten_history.py`, including its exit code.<br>3. Migrating any CSV tree to `state/raw/` or to parquet beyond the six named in section 5.8 as moved by rows 3, 9 and 10.<br>4. A measured figure that contradicts section 4, **or** a measured chain in front of the force push that does not fit the gap it must sit in - the remedy for the second is a cron change, which moves when the site publishes.<br>5. **Moving a ledger that any build-time reader under `frontend/src/lib/server/` opens, before that reader's answer is settled.** Row 9 fires it. Three answers, each with its price: a build-time parquet reader (a second engine importer in `frontend/`, which row 7 decision 11 forbids, plus a Node parquet dependency); a dual write for one release (two writers of one fact, and somebody must remember to stop); or holding each reader until its route moves to the browser (blocks row 9 on route rows that do not exist yet).<br><br>**Four earlier triggers became controls instead**, because a control that fires is a red test and a test is a better stop than a note: a window including today is refused by name at config load (section 5.2); a second parquet importer is caught by row 2's oracle; a writer outside the two roots raises in `paths` (section 5.4); and a declaration no module serves fails the two-way refusal (section 5.2).<br><br>6. **Changing any task's `window`, or any compaction's `monthly_window`, from `{unit: forever}` to a bounded window, or any task's `dry_run` from `true` to `false`.** Both are the first deletion that tree has ever seen. Neither is reversible past the corpus squash, and no test can see that the number is wrong. Stop before the commit that makes the change, not before the commit that adds the member. |
| Chosen strategy | Register the two new roots, lay the persistence door, then move tasks in one PR per outcome, reader before writer, behaviour unchanged until the row that changes it. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2; section 1 names the pairs that run two-wide. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Migrating the rest of `state/` to `state/raw/` | Two layouts coexist: the gardener's own ledgers and the two row 3 takes sit under `state/raw/`, the rest stay where they are. Row 2 registers both roots so nothing reads them as strays. Section 5.8 lists what is left, with its producer and its consumer, so the later plan starts from a map rather than a survey | Its own plan. The owner's direction on 2026-09-24 is that `state/raw/` is where every writer lands **in future**; that is a rule for new writers, and moving committed data is a separate change with its own fixtures |
| Migrating the remaining CSV day trees to parquet | They stay CSV, and `backend/idhazh/day_shards.py` stays CSV-only and says so in one docstring line. Section 5.8 shows the write side is two functions and the read side is two more, so the later plan is bounded work rather than a ledger-by-ledger slog | Its own plan, now that the ledger door has two producers rather than none |
| The other six console ledgers, and the other fifteen ECharts importers | One panel on `/console/machine` reads parquet and draws in d3; every other panel keeps its CSV reader and its ECharts option builder, and `echarts` stays installed. Two grammars coexist on one route until plan 52 closes it | [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md), which starts from the chart vocabulary, the readout strip and the ten gates written by `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md`'s rows titled **The chart vocabulary and the house style, with no panel moved**, **One readout strip, every chart, and hover a keyboard can reach** and **The ten sufficiency gates and the panel capture group** |
| Everything the console does: one panel reading parquet in the browser, the d3 house style, the console shell, and the Hardware route's double count | Telemetry-intent N2, N3 and N5 get no stone in this plan, and `/console/machine` keeps a count that is wrong by about a fifth until that plan lands | Nothing. It is `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md`, whose row titled **One panel end to end: the browser fetches the ledger and draws it in d3** waits on this plan's rows titled **One compaction task a ledger, two compact periods, and the diagrams move into the page**, **The three ledgers the console's routes read become parquet** and **`span-rollup` becomes parquet**. They were split because they share no consumer, no risk class and no escalation surface: these ten rows change what is deleted from `main` and what force-pushes it, and nothing in that plan can lose data |
| Switching the visuals deletion on | The published tree keeps SVGs no day page links to | Plan `20260905-13-switch-on-deletion-plan.md`, row titled "The fuse comes out, and one run is watched". Row 5 moves that row's subject from a CLI flag to `config/gardener/visual-prune.json`'s `dry_run` |
| Evicting `corpus/corpus.jsonl` rows as a task | The row cap stays with the harvest | It is a count bound, not an age bound, and `corpus.roll()` at harvest time is its only reader |
| An `enabled` flag per task | Nothing. **`lifecycle_status: paused` is the off-switch**, and it does more than an `enabled: false` would: a paused task keeps its declaration and its `owns` claim, so its paths stay reserved and no sibling can quietly take them | Nothing. It would be a second spelling of `lifecycle_status: paused`, and two spellings mean two places to look when a task did not run. **`dry_run` is not the off-switch** - a dry run still runs, still costs a task slot and still writes a record (section 5.2) |
| A rollback for a deletion | **A wrong deletion is recovered from git history for between 60 and 90 days**, and after that the corpus squash has rewritten the range and the bytes are gone (CLAUDE.md section 8, `finetune.prune_keep_days: 60` and `prune_every_days: 30`). Past that there is no path back | Nothing. `one_at_a_time.py` already refuses to carry one, on purpose |
| Applying this naming to what `digest.yml` commits | The one path pair that can still lose a race stays as it is: `corpus/corpus.jsonl` and `corpus/corpus.meta.json` have no merge driver, are in neither `paths.DERIVED` nor `paths.UNION_SAFE`, and carry no writer identity in their names - so where the rebase replay conflicts, `commit_and_push.py` cannot choose a side and the push fails | Its own plan. Everything else `digest.yml` commits survives a rebase today - `state/` shards carry a per-writer name, nine collections take a `merge=union` driver, and every path under `frontend/public/` is in `paths.DERIVED` and rebuilt against the tip before the rebase. **A union driver is a workaround rather than the answer, and it is precisely what telemetry-intent N6 retires**: it survives a race by keeping both sides instead of by having one writer, so it cannot tell a concurrent append from a duplicate. **Row 3 retires two of the nine** with the ledgers it migrates, `state/feed-retirements.csv` and `state/visual-prunes/`; section 5.8 maps the other seven to their own plan. **The heaviest of the seven is `state/published/`**, which `stages/assemble.py` appends to on every run and which holds 34 committed files, counted 2026-09-26. **The published payloads can never take this naming**: a static site cannot list a directory, so something must answer at a known address. That address is the ledger's own committed index (section 5.9.13), fetched by the query door at view time. **It is not `console/band.json`** - that route was taken for a day and reversed on 2026-09-25, because `+layout.ts` prerenders and would inline the list into every console document |

### The intent this plan serves

[docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star: eleven statements about what must be true of telemetry when the workstream is done. It sits above this plan (CLAUDE.md section 0d), so where the two disagree **this plan is what changes**. Not everything below ships here; this plan is a stepping stone and the map says which stones it lays.

| # | The intent, in short | What plan 50 does about it |
| --- | --- | --- |
| N1 | Parquet at rest, PyArrow writes it, CSV retired | **Stone laid.** Row 2 builds the parquet half of `backend/idhazh/ledger/` as the one door and row 3 takes two ledgers through it. Section 5.8 names every ledger still on CSV, its producer and its consumer |
| N2 | The browser queries the parquet itself | **Not here.** `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md`. **What this plan owes it is the compact tier**: that is what the browser addresses, so no row here may change a period's grain, how often it is produced, or its index shape without plan 51's row titled "One panel end to end: the browser fetches the ledger and draws it in d3" |
| N3 | The browser fetches its own data at view time | **Not here.** Plan 51, and no row here may make it harder |
| N4 | Prerendering is an anti-pattern; the prerendered routes come off it | **Not here, and its owner is [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md).** Nine files under `frontend/src` carry `export const prerender` today, verified 2026-09-24. Plan 51 leaves all nine and stops a row from retiring one with an ESCALATE trigger, which is the right move for that plan but leaves N4 claimed by nobody. **Prerendering can only come off once nothing needs inlining at build time**, and that is true exactly when plan 52 has deleted the six projections - so plan 52 is the closing act and owes N4 a row. Until it has one, the intent page's own rule bites: a thing that contradicts one of the eleven is a defect, not a trade-off |
| N5 | d3.js is the only charting library; ECharts is retired | **Not here.** Plan 51 writes the house style and moves one importer of **sixteen**. Two of the sixteen, `waterfall.ts` and `donut.ts`, have no importer at all |
| N6 | One writer per path; bytes never change after the writer closes | **Stone laid.** Section 5.7 mints the name from the writer's identity, and row 3 retires a `merge=union` driver on each ledger it migrates |
| N7 | `state/` is the console's only source; no projection survives in `frontend/` | **Not here.** Nine payloads live under `frontend/public/` |
| N8 | `frontend/` holds UI code, not production artefacts | **Not here**, the same nine |
| N9 | A file is named `<uuid8>.parquet` | **Delivered for raw** by section 5.7, which is where the rule earns its keep - raw has many uncoordinated writers. **Narrowed for compact**: a compact file is named for the period it covers, because that tier has one writer and a minted name there costs the browser a computable address. Owner ruling, 2026-09-25, overturning 2026-09-24 |
| N10 | `state/` splits into `state/raw/` and `state/compact/` | **Delivered** by section 2 and section 5.4, as a refusal rather than a convention |
| N11 | One shard pattern for every tree, keyed on `covers` | **Delivered for what this plan writes**, mapped for the rest in section 5.8 |

**Five of the eleven are about the console and none of them is here.** They are `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md`, whose row titled **The three ledgers the console reads are published** waits on this plan's rows titled **One compaction task a ledger, two compact periods, and the diagrams move into the page** and **The three ledgers the console's routes read become parquet**. What this plan owes that one is a door, two roots and three migrated ledgers that already work.

## 1. Status Reckoner

**Eleven pull requests in eight slots. One row is one pull request; three pairs run two-wide - rows 4 and 11, rows 3 and 6, rows 8 and 9 - row 12 runs after row 8, and row 10 is collapsed.** The dispatcher is a running pool, not a wave ([execute-a-plan.md](../docs/how-to/execute-a-plan.md)): a slot frees when a worker returns its report, never when a pull request merges. `Depends-on` and the `Files touched` lists are the readiness test; `Parallel-group` is a hint.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The site-size instruments leave the prune module | - | A | DONE | p50r1 | #1127 | p50-r1-worker |
| 2 | The payload ledger, the two roots, and the arrow mapping | 1 | B | DONE | p50r2 | #1131 | p50-r2-worker |
| 3 | Two ledgers become parquet and their union drivers retire | 2, 4 | D | DONE | p50r3 | #1142 | p50-r3-worker |
| 4 | The gardener: registry, config, schedule, record, commit loop | 2 | C | DONE | p50r4 | #1139 | p50-r4-worker |
| 5 | Every prune pass becomes a gardener task | 3, 4 | E | DONE | p50r5 | #1145 | p50-r5-worker |
| 6 | The corpus squash becomes Python | 4 | D | DONE | p50r6 | #1141 | p50-r6-worker |
| 7 | One compaction task a ledger, two compact periods, and the diagrams move into the page | 5, 11 | F | DONE | p50r7 | #1151 | p50-r7-worker |
| 8 | `prune.yml` becomes `idhazh-gardener.yml`, and the whole garden is scheduled | 6, 7 | G | DONE | p50r8 | #1156 | p50-r8-worker |
| 9 | The three ledgers the console's routes read become parquet | 7, 12, and plan 51's row titled **The query door module and its two entry points** | H | DONE | p50r9, p50r9fe | - | p50-r9-worker-3, p50-r9-worker-fe, p50-r9-worker-5, p50-r9-worker-docs2 |
| 10 | `span-rollup` becomes parquet | - | - | **COLLAPSED** | - | - | - |
| 11 | The index and watermark shapes are declared | 2 | C | DONE | p50r11 | #1136 | p50-r11-worker |
| 12 | The closed-day fold of the CSV day trees moves into the gardener | 7, 8 | I | DONE | p50r12 | #1161 | p50-r12-worker-2 |

**Row 5 now depends on row 3 as well as row 4.** Its `visual-prune` task calls the parquet writer row 3 creates; dispatched after row 4 alone it would write CSV through a door that does not exist.

**Row 3 now depends on row 4.** Row 3 switches `visual-prunes` and `feed-retirements` to `grain: "raw-and-compact"`, and that value is the one row 4 adds to `Grain`. The two rows also share `config/ledgers.json`, `backend/idhazh/contracts/ledgers.py` and `backend/idhazh/ledger/paths.py`. Found by diffing their file lists at dispatch, 2026-09-27. Rows 3 and 6 share no file, so they are the pair that runs after row 4.

**Row 11 declares the four index shapes that row 7 used to own**, so plan 51's query door can bind to them without waiting for the compaction. Plan 51's owner asked for the move on 2026-09-27. Fowler and Carmack ruled for a new row rather than reopening row 2, and row 11's decisions say why.

**Dispatch row 6 ahead of row 5 when both are ready.** Row 6's acceptance is a named observation at the next scheduled wake rather than a gate, so its clock starts as early as its dependency allows and the largest row in the plan does not wait behind it. The dispatcher takes any ready row, so this is an ordering preference and not a dependency.

**Row 10 is collapsed, not pending.** Its subject is a ledger that is being deleted rather than migrated, so the migration has no beneficiary. The deletion is one outcome with its own risk class - a one-way removal of a ledger with five live readers and one published projection - and it goes to [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md)'s row for the last console route to move, beside the `span-rollup` projection that row already deletes (that plan's section titled **The shape this plan is expected to take**). **Nothing in this plan or in plan 51 depends on the removal**; leaving it costs one duplicated ledger being written, which is what happens today.

**Why the order is 5 before 6.** Row 5's acceptance is a gate; row 6's is an observation at the next scheduled wake. Numbering is an id, not a sequence - the dispatcher takes any ready row - so the preference is written above rather than encoded in the numbers, and a pointer from another plan cites a row by TITLE for the same reason.

**Why the width is two, and what row 4 does to it.** Rows 5 to 9 would all have appended to `config/idhazh_gardener.json` and `backend/idhazh/gardener/tasks/__init__.py`, and a plan whose second half shares one surface is serial whatever its letters say. **Row 4 removes both joins, because the task list is open** (owner ruling, 2026-09-26): a task is a declaration in `config/gardener/` and a module in `backend/idhazh/gardener/tasks/`, and no file anywhere lists them. Adding a task edits nothing anybody else owns. **Rows 5 and 7 stay serial**, because both remove a step from `.github/workflows/digest.yml`, and a workflow file is not relaxed for a slot: a bad merge in a doc page costs a paragraph, a bad merge in the daily workflow costs the run.

**Three properties the grouping preserves, each of which a merge would have cost.**

| Property | What it means | What breaks without it |
| --- | --- | --- |
| Row 1 ships without a blocker | Row 1 waits on nothing, and neither do rows 2 to 4 now that the ledger package has landed; only row 5 waits, on plan 54 row D1 | Merged, row 1 waits for a plan it does not need |
| A one-way change is alone | Rows 3 and 9 each move committed bytes and cannot be reverted by reverting code | Merged, a revert of a neighbour's defect takes a migration out with it |
| The force push is alone | Row 6 is the only code here that force-pushes `main` | Merged, reverting it carries the task registry out with it |

**Every new test module a row adds carries a module-level `pytestmark`, so `backend/tests/test_marks.py` is not in its `Files touched`.** That file holds `UNMARKED_MODULES`, the set of test modules carrying no mark, and it appears only in a row that moves or renames one of those.

**Row 2 already gave `SERVER_JOB` in `frontend/src/lib/server/host-fingerprint.ts` its three new jobs** - `migrate`, `run-tasks` and `history` - and `backend/tests/contracts/test_frontend_vocabularies.py` binds them. So row 4 does not edit that file, and plan 51's edits to it no longer hold either plan for the other.

**Every `Files touched` entry below names a file, never a directory**, because readiness is computed by diffing those lists. Two directories qualify for the one exception - a directory the row creates that no other row in either plan touches - and each is marked on its own line: `backend/idhazh/ledger/` and `backend/idhazh/gardener/tasks/`. `backend/tests/` and `docs/` never qualify.

**The plan-doc itself is excluded from the disjointness diff.** Every row stamps its own Reckoner line in its own change, so the file is in every row's real set.

**Compaction lands before the workflow.** The old order scheduled a gardener whose own record ledger had nothing pruning it, which would have made `state/raw/gardener/` the only unbounded tree in the repository between two rows. The switch goes last.

## 2. The layout this plan establishes

**This is telemetry-intent N10 and N11 made concrete, and it binds every writer added after this plan.** Everything under `state/` goes to one of two roots and nothing else: `state/raw/` for data as a writer left it, `state/compact/` for what a compaction left behind. A third root is not a thing. The ledgers that sit directly under `state/` today predate the rule; row 2 moves two of them and section 5.8 maps the rest to their own plan (ESCALATE trigger 5). What this plan owes is that **nothing new is ever born outside the two roots**, and section 5.4 makes that a refusal rather than a convention.

**This tree is the reference. Every path literal in this plan and in `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md` is one of these shapes and no other.**

```
state/
|-- raw/
|   `-- <ledger>/
|       |-- 2026/
|       |   `-- 09/
|       |       |-- 23/
|       |       |   |-- a81f3c92....parquet      many writers, write-once
|       |       |   `-- b27d9e11....parquet
|       |       `-- 24/
|       |           `-- c93ab812....parquet
|       `-- index/
|           |-- 2026-09-23.json                  the compaction task wrote this, whole
|           `-- 2026-09-24.json
`-- compact/
    `-- <ledger>/
        |-- daily/
        |   |-- 2026/
        |   |   `-- 09/
        |   |       |-- 23.parquet
        |   |       `-- 24.parquet
        |   `-- watermark.json
        |-- monthly/
        |   |-- 2026/
        |   |   |-- 07.parquet
        |   |   `-- 08.parquet
        |   `-- watermark.json
        `-- index/
            |-- daily.json
            `-- monthly.json
```

**Two periods, not three.** A yearly period is not built here: at the default `monthly_window` of 13 months the monthly period is already bounded, and the first yearly file could not be written before January 2028. A period with no writer and no reader for twenty-seven months is minted by the plan that needs it.

**"Tier" and "period" are two words for two things and are never swapped.** A **tier** is `raw` or `compact` - the two roots, and the `Tier` enum. A **period** is `daily` or `monthly` - how much time one compact file covers, and the `Period` enum. `state/compact/<ledger>/daily/` is the daily period of the compact tier.

**A raw file carries a minted name; a compact file carries a date.** Raw has many uncoordinated writers, so `<file_id>` (section 5.7) is what stops two of them taking one path. A compact period has exactly one writer and its path comes from the period it covers, so a minted name there buys nothing and costs the reader a computable address - **owner ruling, 2026-09-25, overturning the 2026-09-24 ruling that bound the `<unit_id>` name to every tier.** N9 still binds raw, which is where it was earning its keep.

**There is one `state/` tree and there always was.** `raw` and `compact` are two directories inside it, not two trees and not a second checkout. "The two roots" in this plan always means those two directories; "the two ledgers" always means the two things row 3 migrates, `feed-retirements.csv` and `visual-prunes`.

Worked example - run 2026-09-24-17482910337, first attempt, `run-tasks` shard 03, on 2026-09-24:

```
state/raw/gardener/2026/09/24/01a0d03c-2e00-8461-98e0-a67898e9a802.parquet
state/raw/gardener/index/2026-09-24.json
state/compact/gardener/daily/2026/09/24.parquet
state/compact/gardener/daily/watermark.json
state/compact/gardener/index/daily.json
```

`<ledger>` is `gardener`, `visual-prunes`, `feed-retirements`, `item-health`, `scores` or `host-fingerprint` - always the `LedgerName` value, never a task name, so the ledger is `visual-prunes` even though the task that prunes images is `visual-prune`. Rows 3, 4 and 9 add them. `LedgerName` is the closed set that refuses a typo, and `config/ledgers.json` must name exactly its members or the build stops at import, so **a ledger this plan creates is two edits before it is one write**: its member and its registry entry ([`../docs/architecture/contracts/ledger-registry.md`](../docs/architecture/contracts/ledger-registry.md)). Five of the six already have both. **`gardener` has neither, and row 4 adds both.** **Every ledger under `state/raw/` and `state/compact/` carries `grain: "raw-and-compact"` in its entry** - a sixth `Grain` member, added by row 4, that the CSV path builders in `backend/idhazh/ledger/paths.py` refuse by name, so nothing reads or writes a moved ledger at its old path by accident. A row switches a ledger's entry in the same commit that moves it. `Grain` itself goes when the last CSV ledger moves, as its own docstring already requires (owner decision, 2026-09-27).

**A data file is written once and never rewritten. Five small JSON files are rewritten in place, and each one has exactly one writer.** The raw day index of an open day, and the index and watermark of each compact period - `index/daily.json`, `index/monthly.json`, `daily/watermark.json`, `monthly/watermark.json`. **A raw day index stops being rewritten the moment its day is compacted** (section 5.9.13), which is what lets `raw_index_keep_days` hold a real listing rather than ninety days of empty ones. A path with one writer cannot lose a push race, needs no merge driver, and makes "same path, different identity" a detectable defect - so single writership is the property that matters here, not immutability, and section 5.4's `paths.py` is what makes it structural rather than hoped for.

**Why a watermark file exists when the newest file already names a date.** A listing cannot tell you about a gap. If 23 September produced nothing, no daily file is written, the newest file still says the 22nd, and the task retries the 23rd every day forever. The watermark records "I looked at the 23rd and there was nothing", which is the one fact no walk of the tree recovers. There is one per period because there are two roll-ups - raw to daily, daily to monthly - and each resumes from its own mark, which that period's step writes last (section 5.3).

**Compaction is per ledger and per period, at each period's own eligibility rule.** Section 4 says what each grain costs.

## 3. The shape this plan builds

**Both diagrams moved into the architecture page in row 7, drawn as the gardener stands rather than as planned**: [../docs/architecture/publishing/idhazh-gardener.md](../docs/architecture/publishing/idhazh-gardener.md) carries the job graph in its section on a wake, and how a row travels from a writer to a reader in its section on the compaction. The plan keeps a link, not a copy, because two pictures of one job graph disagree the first time the workflow changes (row 7 decision 12, Guardrail #4).

## 4. What was measured, 2026-09-24

Three readings drove a decision. Everything else was noise and is not kept. A figure that contradicts one of these is ESCALATE trigger 4.

**Parquet's cost is a fixed charge per file plus a charge per column in that file, so the only number that matters is how many rows share one file.** The footer is about 3,764 bytes. **A column costs about 250 bytes flat when its value never varies, and its own data when it does.** So the format is expensive at one row and cheap at several hundred, and consolidation is the whole design.

**Measured 2026-09-25 against the eight newest committed `item-health` files - 220 rows, 122 columns.**

| What | Bytes | Against the CSV |
| --- | --- | --- |
| The eight committed CSV files as they are | 225,711 | - |
| One parquet file, every column | **87,714** | **2.6 times smaller** |
| One parquet file, the 83 columns a page reads | 62,304 | 3.6 times smaller, and 29 percent below the line above |
| One parquet file, every column, per-column statistics off | 81,739 | saves 6.8 percent |

**And measured at the other extreme, against three days of `host-fingerprint` - 79 per-writer shards of one or two rows each: 57,888 bytes of CSV become 873,872 bytes of parquet, 15.1 times larger.** That is the same format and the same data, split 79 ways instead of one. A one-row file of 31 columns is about 9,300 bytes of page, dictionary and statistics overhead around 370 bytes of data.

**Those two readings are the whole argument for this plan.** A ledger written per writer and never consolidated is the worst thing parquet does; the same ledger consolidated into one file a day is better than the CSV it replaces. **Nothing is published from the raw tier**, and every compact period is one file.

**A constant column costs about 250 bytes flat** - a page header, a dictionary page and statistics. That is what decides section 5.7's column-or-footer split: a column earns its 250 bytes only when a query filters on it, because row-group statistics then let a reader skip the whole file.

**Git delta-compresses a rewritten period file rather than storing a whole new blob.** Measured over nine real `host-fingerprint` days: 119,207 bytes written becomes **37,315 bytes packed**, which is the reading; the other figures are derived from it. That is 4,146 bytes a day per ledger, and 373 KB over the 90 days `finetune.prune_keep_days: 60` and `prune_every_days: 30` allow history to hold. An earlier draft asserted "roughly 360 MB" for daily compaction across every ledger; that was arithmetic on a false premise. **Per ledger the real figure is about a thousand times smaller, and summed over all twenty-nine leaf ledgers it is 10.8 MB, about thirty-three times smaller.** The churn was never the constraint, so how often a period is rewritten is a preference about what a reader gains.

**Every size in this section names its compression.** 32 bytes a row is snappy; a period file is zstd, which row 2 decision 5 measured at 2.2 times smaller at a thousand rows. **A worker pricing a new ledger off this section reads the compression before the number, and re-takes the reading for that ledger's own column count** - the break-even is a function of width, and `host-fingerprint`'s 31 columns and `item-health`'s 122 do not behave alike.

**pyarrow is the largest thing the gardener installs.** It is an optional extra, not a runtime dependency: `pip install -e .` appears at **17 call sites across 9 workflow files** and `digest.yml` alone runs it 30 times a day. **Row 9 puts it into three of those job kinds.** **Owner ruling 2026-09-27: pyarrow is adopted whatever it costs, so its install is not re-measured on `ubuntu-latest` and no row waits on a figure.** The one reading is from Windows, 96.9 MiB installed, and a sentence that quotes it says so, because the two platforms bundle different shared objects.

**Zero published bytes, in this plan only.** Nothing this plan writes reaches a reader's browser; it lays the ledger and the periods, and `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md` is where a download is first paid for and priced.

## 5. The contracts

**A worker implements these and invents nothing.** Everything here is declared before any logic reads or writes it (Guardrail #3).

### 5.1 `CollectionPruneRow`, widened - there is no new record contract

`backend/idhazh/contracts/collection_prune.py`, stem `collection-prune-row`. Eight of the fields already exist with these meanings; nothing persists the shape today, so the widening owes a `version` stamp and one `changelog` line and no migration. Minting a second near-twin contract would be two shapes for one question (Guardrail #4).

| Field | Type | Meaning |
| --- | --- | --- |
| `version` | `DateStamp`, inherited from `Contract` | The shape's own date stamp |
| `date` | `DateStamp` | The day the pass ran |
| `task` | `Slug` | **Renamed from `collection`.** The task's name - the declaration's filename stem and the `--task` value. It named a GitHub collection when only two tasks wrote this row; every task writes it now, so the column is `task` and the rename ships with a `version` stamp and one `changelog` line |
| `run_id` | `str`, `RUN_ID_PATTERN` | **new.** The execution that produced the row, so a reader finds the job log after the path is gone |
| `attempt` | `int`, `ge=1` | **new.** The GitHub run attempt; says whether a retry happened |
| `job` | `ServerJob` | **new.** `run-tasks` or `history` |
| `shard` | `int`, `ge=0` | **new.** The matrix index, so a row maps to one job log when three tasks share a job |
| `since` | `DateStamp \| None` | Oldest day a member may carry and still qualify. Empty means no lower end |
| `until` | `DateStamp \| None` | Newest day a member may carry and still qualify, inclusive. Empty means no upper end |
| `max_deletes_per_run` | `int \| None`, `ge=0` | **widened to optional.** `null` is no ceiling; `0` keeps its meaning of a survey that reports the first qualifying member and takes nothing |
| `dry_run` | `bool` | True when the pass only reported. `selected` and `deleted` still say what it would have taken |
| `candidates_seen` | `int`, `ge=0` | Members the listing yielded before the pass stopped. Never the size of the collection |
| `selected` | `int`, `ge=0` | Of those, how many the window held |
| `deleted` | `int`, `ge=0` | How many it removed, or would have. A compaction's written bytes are not netted against this |
| `bytes_freed` | `int`, `ge=0` | What those deletes freed, or would. `0` is honest where a member has no readable size |
| `stopped_because` | `StopReason` - `exhausted`, `ceiling` or `failed` | Why the pass ended. `failed` is how one task's failure reaches the record without taking its shard siblings down |
| `resume_from` | `MemberId \| None` | Where the next pass begins. Empty exactly when `stopped_because` is `exhausted` |
| `duration_ms` | `int`, `ge=0` | **new.** Wall clock for this task alone, never the job |
| `work_ended_at` | `Timestamp` | **new.** The UTC instant this shard finished its work and entered the commit loop. **The push's own cost is the landed commit's timestamp minus this**, which is why the field is an instant rather than a `push_wait_ms` |
| `cone_mb` | `float`, `ge=0` | **new, in row 8.** This shard's working tree after checkout, in megabytes, measured once a shard and written on every row it writes (section 5.2's `max_cone_mb`) |

Cross-field validators, existing ones kept and one amended: `selected <= candidates_seen`; `deleted <= selected`; `deleted <= max_deletes_per_run` when it is neither null nor 0; `(stopped_because is exhausted) == (resume_from is None)`; `since <= until` when both are set.

**There is no `push_attempts` column and no `push_wait_ms` column, and `work_ended_at` is what stands in for them.** The record is one of the files the push lands, so it is written before the first push attempt and cannot describe what that attempt did. Rewriting it between turns of the loop is not available either: section 5.6 makes "same path, different bytes" exit 2, and that check is what catches two writers minting one identifier - relaxing it so a retry may edit its own record would cost the check its meaning. A second commit after the push succeeds would double the pushes, ten a wake at five shards, and could itself lose a race.

**So the record carries the instant the work stopped, and git carries the instant it landed.** The push's cost for one shard is `git log -1 --format=%cI -- <record_path>` minus that row's `work_ended_at`: one bounded read per commit, no second push, and durable for as long as the history holds - 60 to 90 days, which the corpus squash bounds (CLAUDE.md section 8). **That is what turns `attempts` and `push_deadline_seconds` from estimates into knobs a reading can move** (Guardrail #10); row 8 decision 11 is where the estimate is stated today.

### 5.2 `config/idhazh_gardener.json`, and one declaration a task under `config/gardener/`

`GardenerConfig` in `backend/idhazh/contracts/knobs/gardener.py` holds `version`, `attempts`, `shards` and `max_cone_mb` and nothing else. **Every task declares itself in its own file, `config/gardener/<task-name>.json`**, validated by `TaskPolicy` in the same module. The filename stem is the task name; there is no `name` field inside, because a name written twice can disagree with itself - and because `json.loads` keeps the last value of a duplicate key silently, so two rows adding a block of one name to one file after a botched merge produce one block, no error, and a task that quietly stopped running. A directory refuses that at the filesystem.

**The task list is open and there is no index.** The directory is the list (owner ruling, 2026-09-26). An index would be a file every row appends to - the join this shape exists to remove - and a second statement of a fact that can then disagree with the directory. **Nothing but a task declaration is ever placed in `config/gardener/`.**

**The loader gathers the directory and validates the set; a declaration is never validated alone**, because half the refusals below read two tasks at once.

**Retiring is a status change, never a file deletion.** `lifecycle_status: retired` keeps the declaration and keeps its `owns` prefixes in the disjointness check, so a later task claiming a retired task's paths is refused by name. Deleting the file instead is one line of `git rm` and it takes the tombstone with it - the one thing a single file made harder than a directory does, and the one rule that has to be written down because of it.

**There is no `to-be-drafted` and no `to-be-onboarded`, for the same reason there is no `enabled`.** A declaration with `lifecycle_status: paused` is a draft; a declaration with `lifecycle_status: active` and `dry_run: true` is a task being onboarded. Two more statuses would be two more spellings of those, and at run time nothing could tell the new pair from the old. **Dropping the file in is the onboarding**, and `dry_run` being required with no default is what makes that safe: a new task computes its full delete set, writes its record and deletes nothing, no matter who dropped the file in. What forces a NEW declaration to ship `dry_run: true` is a review gate and is named as one - a contract test over the committed tree asserting that a declaration added in the same change as its module ships `dry_run: true`. ESCALATE trigger 6 covers the later flip.

**Hard constraint: the shard plan must be computable from these files with `json`, `datetime` and `pathlib` alone**, because the `plan` job runs before any `pip install` - the discipline `backend/utilities/prune_due.py` already keeps and states. **The plan job opens no file outside `config/`**, which is what holds its checkout to two directories however many tasks the garden gains (section 5.3). **It never opens a task module, never imports anything from `idhazh`, and never reads `state/`, `corpus/` or `frontend/`.** The read is a sorted glob, and it takes four keys a declaration - `lifecycle_status`, `owns` or `owns_everything_else_under`, and `after` - ignoring every other key it finds; the Pydantic loader inside `run-tasks` takes all of them and keeps `extra="forbid"`. Validating everything in both would let a key added for one task break the matrix on every runner, before any install, with nothing able to catch it.

`config/idhazh_gardener.json`:

```json
{
  "version": "2026-09-24",
  "attempts": 5,
  "shards": 5,
  "max_cone_mb": 64
}
```

`config/gardener/seen.json`, whose filename stem is the task name:

```json
{
  "lifecycle_status": "active",
  "kind": "retention",
  "window":  { "unit": "days", "value": 90 },
  "dry_run": true,
  "max_deletes_per_run": null,
  "owns": ["state/seen"]
}
```

`config/gardener/trials.json` has the same shape, with `"owns_everything_else_under": ["state"]` in place of `owns`. Both ship `dry_run: true`, as all ten retention declarations do (section 5.2.1).

The first four keys below belong to `config/idhazh_gardener.json`; every key after them belongs to a task declaration.

| Key | Type | Meaning |
| --- | --- | --- |
| `version` | `DateStamp` | The config shape's date stamp |
| `attempts` | `int`, `ge=1` | How many times the commit loop re-fetches, recomputes and pushes before exit 3 |
| `shards` | `int`, `ge=1` | How many `run-tasks` jobs the `plan` job splits the active tasks into. A workflow test asserts `idhazh-gardener.yml`'s `max-parallel` is not below it |
| `max_cone_mb` | `int`, `ge=1`, default `64` | **The ceiling on one `run-tasks` shard's working tree after checkout.** The shard sums its own bytes right after the checkout and before any task lists anything, and **exits 1 naming the shard, the size it measured, the ceiling and its three heaviest prefixes** when it is over. It writes the size on every record row as `cone_mb`, so where tasks land is answered by data at the next wake. The default sits above the heaviest shard measured on 2026-09-26, 53.6 MB, and below twice it, so it fires on growth rather than on how the tasks happen to be placed |
| `lifecycle_status` | `TaskLifecycleStatus`: `active`, `paused` or `retired`, the three values a ledger family carries. **Required, no default** | The task's place in the garden, and the whole of its lifecycle. **It is not called `state`**, because `state` is already the folder every ledger sits in and one word cannot carry two meanings. The enum is named for its subject, because `LedgerLifecycleStatus` is the families' and `LifecycleStatus` the taxonomy's (owner ruling, handover from plan 53, 2026-09-27). **`active`** runs at every wake. **`paused`** does not run at all: it keeps its declaration and its `owns` claim, so its paths stay reserved and no other task can take them. **`retired`** means the task never runs again but its declaration stays, so a reader of a committed record can still see the policy that produced it; deleting the declaration instead would orphan every record naming the task. **There is no fourth status and `dry_run` is not one of these three**: a dry run still runs, still costs a task slot and still writes a record, which is what onboarding needs and exactly what a broken task must not do |
| `kind` | the `TaskPolicy` member, **required** | Which member validates the rest of the file (section 5.9.5) |
| `window` | `{unit: days\|months, value: int ge=1}` or `{unit: forever}`, discriminated on `unit` | What the task keeps. Two bounded units so a ledger counted in months keeps a month window, and **`forever` for a tree this project has chosen not to age-bound**. `forever` carries no `value`, and `extra="forbid"` refuses one for free. **Three committed windows are null today** - `observability.item_health_aggregate_keep_months`, `observability.score_archive_keep_months` and `observability.visual_aggregate_keep_months`, read from `config/idhazh.json` on 2026-09-26 - and null there means never delete. **They transcribe to `{unit: forever}` and to nothing else.** A third union member rather than a nullable `value`, because `null` is also what an absent key looks like, and this contract makes `lifecycle_status` and `dry_run` required with no default precisely so that an omission cannot be read as an intent |
| `dry_run` | `bool`, **required, no default** | Run and report, change nothing |
| `max_deletes_per_run` | `int \| null`, `ge=0` | `null` no ceiling, `0` survey. Same meaning as the record column |
| `owns` | list of POSIX path prefixes, repository-relative | Every path this task may delete under. One declaration yields three things: the disjointness proof, the sparse-checkout cone, and **the permitted set for both verbs - what this task may delete and what it may write**. It is never the staging list; `Shard.written_paths` and `Shard.deleted_paths` are (section 5.6) |
| `owns_everything_else_under` | list of POSIX path prefixes | The complement form, for the `trials` task only. The set is `under` minus every other task's `owns` minus the registered ledger names |

**Load-time refusals, each naming the offender:** an `active` or `paused` declaration no module serves, or a module no `active` or `paused` declaration uses; a window that would include today; two tasks whose owned sets intersect or where one is a prefix of the other; more than one task using the complement form; `config/gardener/seen.json`'s `window.value` shorter than `collect.seen_window_days`; `config/gardener/counterfactual-scores.json`'s `window.value` shorter than `lens_weights.window_days`; `config/gardener/telemetry-aggregate.json` carrying a series window shorter than the `observability` key that series covers; a `deleted_paths` entry naming a directory rather than a file; an `owns` entry that is not a directory prefix, because the checkout's cone mode matches directories and a file-valued entry would silently match nothing; **`attempts` at or below `shards`**, naming both knobs and their values, because the last-placed shard needs an attempt left after every other shard has landed and at `attempts == shards` it has none; **a ledger in `LedgerConfig.published` whose compaction declares `monthly_window: {unit: forever}`**, naming the ledger and the knob; and **a `daily_keep_days` that does not leave at least one whole month before `monthly_window` begins**, which would open a gap no tier covers.

**The published-ledger refusal is the one that keeps a reader's first request from growing with the archive.** A published ledger's compact periods are what the browser addresses, so what it can reach is bounded by `daily_keep_days` and `monthly_window` and by nothing that is a term of elapsed time. `config/idhazh.json` carries three null windows today (`item_health_aggregate_keep_months`, `score_archive_keep_months`, `visual_aggregate_keep_months`), where null means never delete. **A published ledger may not keep its month files forever.** Publishing a ledger is what makes its windows load-bearing for a reader, and that is the moment to insist on them (Guardrail #12, and `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md`'s section titled "How the browser reaches the bytes").

Three more refusals ride with it, each naming both knobs it read:

- **a published ledger whose `daily_keep_days` and `monthly_window` together reach back less far than the largest value in `console.window_presets`**, which would leave the widest span the console offers with days no file holds. `daily_keep_days` alone may be shorter than that span, on purpose: the monthly period serves the older days.
- **a `monthly_window` that, with `daily_keep_days`, reaches less far back than the window that limited that ledger before it moved.** Once a ledger goes through the door the two periods *are* its retention, and a shorter pair silently cuts it. **That window is the `window` of the retention task whose `owns` names the ledger's old tree, `state/<ledger>`, or, for a task with series, the series that covers that tree** - for `item-health`, the `full-grain` series of the `telemetry-aggregate` task. That task's `aggregate` series is kept forever, but it covers `state/item-health-summary`, not `state/item-health`; compared against it, `item-health` could never be published. The compaction owns the new tree, so the old task's declaration is the only record of how far back the ledger reached; a retired task keeps its declaration and its `owns` (above), so the window stays readable after the move empties the old tree. **A ledger that no task ever limited has no floor**, and its compaction's windows bound it like every other ledger: `gardener`, `visual-prunes` and `feed-retirements` stop being kept forever when they move, and `feed-retirements` keeps its month files longer than the default (row 7) (owner decisions, 2026-09-27). Five cases, and the refusal names which one it hit: a bounded floor against a bounded pair compares and refuses when the pair is shorter; a bounded floor against a `forever` pair passes; **a `forever` floor against a bounded pair refuses**, naming the ledger, because a person chose never to delete it; `forever` against `forever` passes; no floor passes.
- **a `raw_index_keep_days` shorter than `daily_keep_days`**, which would delete an index the daily period may still need to rebuild its own file.

**A task has a life, and the three states are what it is made of.** The gardener is built to carry a list that grows and occasionally shrinks, so the whole lifecycle is in the contract from the first commit rather than bolted on when the first task needs holding.

| Stage | How it is spelled | What happens | What it costs |
| --- | --- | --- | --- |
| **Onboard** | a module that serves it, a declaration in `config/gardener/`, `lifecycle_status: active`, `dry_run: true` | The task runs at every wake, computes what it would delete and writes a record saying so. **It deletes nothing.** A person reads a few days of records, then flips `dry_run` to `false` | One run's work per wake, and no risk. **This is the only way a new task earns trust**, because a deletion is not reversible and a first live run against the wrong `owns` prefix is how a ledger disappears |
| **Hold** | `lifecycle_status: paused` | The task does not run. It keeps its declaration and its `owns` claim, so **its paths stay reserved** and no sibling can quietly take them | Whatever the task was keeping bounded stops being bounded. A paused prune means a ledger grows, so a hold is a decision with a cost and not a shrug |
| **Retire** | `lifecycle_status: retired`, declaration kept | The task never runs again. The declaration survives as a tombstone so the disjointness proof still sees the paths this task used to own, until the data under them is gone too | One declaration. Deleting it before the data is what lets a later task claim those paths and delete something nobody meant |

**`dry_run` is a modifier, not a state, and this is the correction.** An earlier draft had two states and said a task that should act on nothing is `dry_run: true`. That conflates two different things: a dry run **still runs**, costs a job slot and writes a record, which is exactly what you want while onboarding and exactly what you do not want when a task is broken. A broken task is paused. A new task is dry-run. The two are orthogonal and both are needed.

**Load-time refusals that carry the lifecycle:** a `paused` declaration still needs a module - pausing does not mean deleting it - and a module that only `retired` declarations would use must go; both are the first refusal above. A `paused` task whose `owns` prefixes overlap an `active` task's is a fault, because the reservation is the point.

**Two knobs do not move into this file**: `collect.seen_window_days` and `lens_weights.window_days`. Both are read by the pipeline to produce a day, not only by a prune, and moving them would make the planner load the retention config. The cross-file refusal above is what keeps the two in step.

### 5.2.1 The ten retention declarations, transcribed, and the pass that gets none

**This table is the contract for row 5 and a worker copies it rather than deriving it.** Every window was read from `config/idhazh.json` on 2026-09-26 and every prefix from the pass's own body in `backend/idhazh/stages/prune_state.py`. Where this table and the committed config disagree, **the config is right and this table is the defect** - row 5's oracle compares the two key by key.

**`lifecycle_status` is `active` and `kind` is `retention` on all ten.** **`dry_run` is `true` on all ten, and that is a finding rather than a choice** - see below. **The table carries eleven rows because `day-validations` is listed in order to be refused**: plan 54 deletes that ledger, so it gets no declaration, and a worker who writes one has not run the check in section 0.

| Task | `window` | Transcribed from | `owns` | `max_deletes_per_run` |
| --- | --- | --- | --- | --- |
| `seen` | `days: 90` | `collect.seen_window_days`, which stays in `config/idhazh.json` | `state/seen` | `null` |
| `counterfactual-scores` | `days: 30` | `lens_weights.window_days`, which stays in `config/idhazh.json` | `state/counterfactual-scores` | `null` |
| `traces` | `days: 7` | `observability.trace_window_days` | `state/traces` | `null` |
| `feed-health` | `months: 14` | `observability.feed_health_keep_months` | `state/feed-health` | `null` |
| `host-fingerprint` | `months: 14` | `observability.host_fingerprint_keep_months` | `state/host-fingerprint` | `null` |
| `scores` | `months: 14` | `observability.scores_full_grain_months` | `state/scores`, `state/score-index`, `state/score-archive` | `null` |
| `day-validations` | **No task. Plan 54 deletes this ledger** - the contract, the retention pass and the committed tree - and plan 54 lands before row 5 runs, which the check in section 0 confirms. A worker that finds `state/day-validations/` still present should stop and say so rather than write the task | - | - | - |
| `digest-fragments` | `months: 13` | `retention.image_months` | `state/digest-fragments` | `null` |
| `visual-prune` | `months: 13` | `retention.image_months` | `frontend/public/digest` | `200`, from `retention.max_deletes_per_run` |
| `trials` | `days: 90` | `retention.trial_state_days` | `owns_everything_else_under: ["state"]` | `null` |
| `telemetry-aggregate` | three series, below | three `observability` keys | `state/item-health`, `state/item-health-summary`, `frontend/public/telemetry` | `null` |

**The task keeps the name `telemetry-aggregate`, while the ledger it writes is now `item-health-summary`**: it folds three telemetry series and only one of them writes that ledger, and section 2 already lets a task and a ledger differ (handover from plan 53, 2026-09-27). Its three windows live under `telemetry-aggregate.series`, and the third is the reason `forever` exists:

| Series | `window` | Transcribed from |
| --- | --- | --- |
| `full-grain` | `months: 14` | `observability.item_health_full_grain_months` |
| `public-copy` | `months: 14` | `observability.public_telemetry_keep_months`, which the contract already forces to equal the key above |
| `aggregate` | **`forever`** | `observability.item_health_aggregate_keep_months`, **committed as `null`, which means never delete** |

**Every pass in the module is report-only today, and the plan believed otherwise until 2026-09-26.** `.github/workflows/digest.yml` passes `--dry-run` to the whole `prune-state` invocation and `config/idhazh.json` carries `retention.dry_run: true`; one flag fans out to every pass in `prune_state.py`. **So nothing under `state/` is being deleted by this program at all**, and ten declarations at `dry_run: true` is what "each task ships whatever that pass does today" actually means. **The gardener therefore deletes nothing on the day it ships**, and switching any task on is a separate decision with its own record to read first (section 5.2's onboarding stage).

**Two tasks own paths outside `state/`**, which is legal and is why `owns` is a repository-relative prefix rather than a `state/`-relative one: `visual-prune` owns `frontend/public/digest` and `telemetry-aggregate` owns `frontend/public/telemetry`. The two-roots refusal in section 5.4 binds where a **writer** files, not where a task may delete.

**Two of the ten read a key this file does not hold**, so each needs the same cross-file refusal `seen` already has: `config/gardener/seen.json`'s `window.value` shorter than `collect.seen_window_days`, and `config/gardener/counterfactual-scores.json`'s `window.value` shorter than `lens_weights.window_days`. Both are stated in section 5.2's refusal list.

**`retention.image_months` is transcribed twice**, by `digest-fragments` and by `visual-prune`. That is one key bounding two trees today; the declarations carry the same source name and diverge the moment somebody gives either its own number.

### 5.3 How dueness is known, and why a watermark is not a stamp

**There is no stamp ledger.** An earlier draft gave each task a small JSON file it overwrote on every run, recording when the task last ran. That file was not sharded, it sat flat at the root of a ledger, and five jobs rewrote it - exactly the lost-push-race the whole design exists to remove.

**A watermark is not that, and the difference is what it records.** A stamp says *when a job ran*; a watermark says *what the data covers*. Re-running a task against an unchanged stamp does nothing, so a lost stamp write silently skips work. Re-running a compaction against an unchanged watermark redoes exactly the periods that are genuinely not done, so a lost watermark write costs one repeat and loses nothing. That is why one is refused and the other is the mechanism.

**The `plan` job asks no task whether it is due.** Every task in the matrix runs at every wake, so the plan job reads `config/idhazh_gardener.json` and the declarations in `config/gardener/` (section 5.2), splits the active tasks into shards - every kind but `history`, which the `history` job runs itself (row 6) - and stops. The question splits three ways and all three answers are the same one.

| Task kind | Which tasks | What the `plan` job has to know |
| --- | --- | --- |
| **Windowed** | The ten retention tasks, and both GitHub collection tasks | Nothing. They run **at every wake**, as every task in the matrix does, and the window decides what qualifies. A wake with nothing old enough is a listing that finds nothing and a record that says `deleted: 0`. No last-run state exists because none is needed |
| **Compaction** | `compact-<ledger>`, one per ledger | Nothing. The task runs at every wake and **its own watermarks decide the work**, read inside `run-tasks` where that ledger is already in the cone. A wake with no eligible period writes a record saying so, which is the answer the windowed tasks give too. **One task runs both grains in order in one process and lands them in one commit**, and it also writes that ledger's raw day indexes before it reads them. Two earlier designs split this three ways - an index task, a daily compaction and a monthly - and each split bought back a failure the merge removes: an index task owning `state/raw/<ledger>/index` beside a compaction owning `state/raw/<ledger>` is one prefix inside the other, which section 5.2 refuses by name; and a daily and a monthly in different shards both rewrite `index/daily.json`, so the loser of the push race resets to the new tip and re-adds the copy it built before, dropping its sibling's entries at exit 0 and invisible in both logs. **What the merge costs, named: a ledger cannot hold one grain dry while the other runs live** |

**Owner ruling, 2026-09-26, overturning the 2026-09-24 design in which the `plan` job opened `state/compact/<ledger>/<period>/watermark.json`.** That file is outside the plan job's checkout, so the read would have found nothing, answered "never compacted" at every wake forever, and burned a shard slot on finished work - with nothing going red, because `run-tasks` does hold the ledger, reads the real watermark and correctly records `deleted: 0`. Widening the cone was not the remedy: cone mode matches whole directories, so `state/compact` writes every compacted parquet file into a job that opens a few hundred bytes. **The read is deleted rather than relocated**, because at `compact_after_hours: 24` every compaction has a day to take at every wake in steady state, so the read can never answer "no".

**`corpus-squash` is not in this table, because it is not in the matrix and the `plan` job does not gate it.** The `history` job gates itself, in the two-stage shape `prune.yml` runs today: `fetch-depth: 1`, open `corpus/corpus.meta.json`, and only on a due day a second `actions/checkout@v6` at `fetch-depth: 0`. That file's own comment carries over because it is the same job doing the same thing - "29 wakes out of 30 only read one committed file". **Owner ruling, 2026-09-26, overturning the 2026-09-24 design in which the plan job emitted a `history_due` flag**: `corpus/` is outside the plan job's checkout, a missing file reads as "never run", and the job on the other end of that flag is the only one in this repository that force-pushes `main` - so the defect would have rewritten history daily instead of about twelve times a year. The file is in the history job's own checkout, so an absent file there is genuinely absent and `prune_due.py`'s fail-open comment carries over verbatim.

**Why running the windowed tasks at every wake is the cheaper answer, not the lazier one.** A cadence for a windowed task is a second control over the same thing the window already controls, and two controls over one behaviour is how a ledger quietly stops being pruned when somebody widens one and forgets the other. It is also what makes a missed wake cost one wake: a task that failed or lost its push simply runs again at the next wake with no state to reconcile. **This is why there is no `cadence` key at all**, rather than why every task's copy of it says one.

**A wake is not guaranteed daily, and no argument here depends on the rate.** This repository has measured scheduled-workflow placement at 5 runs from 13 slots - about one wake every 2.6 days - and `digest.yml` carries that reading in its own header. A missed wake costs the next wake one more qualifying period, bounded by `max_periods_per_run: 8`, which covers a backlog several times longer than the measured gap.

**An absent watermark means the ledger has never been compacted, and the first run is bounded by config rather than by the archive.** A compaction consumes at most `max_periods_per_run` eligible periods in one wake. With no watermark it starts at the oldest period that ledger's own keep-window still admits, **never at the oldest file in the tree**. A ledger published carrying fourteen months of history drains its backlog over several wakes instead of in one long job or one period a day for two months. This is the one number that makes "starts at the watermark plus one" and "one period at a time" the same program (Guardrail #12).

#### The daily compaction, in order

**A day is eligible once `compact_after_hours` have passed since that day ended.** That is the whole rule, and it is two instants and a subtraction:

```python
def ended_at(day: date) -> datetime:
    """The instant a UTC day closed: 00:00 on the day after it."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone.utc)

def is_eligible(day: date, *, now: datetime, after_hours: int) -> bool:
    return now - ended_at(day) >= timedelta(hours=after_hours)
```

**`now` is a parameter, not a call inside the function.** The caller passes `datetime.now(timezone.utc)` once per wake and the test passes a fixed instant, so the rule is decidable without a clock (CLAUDE.md section 2).

**The wake time is not part of the rule, and an earlier draft had it the other way round.** That draft put the cron at `24 23 * * *` and then read the rule off where the wake landed: at 23:24 yesterday was 36 minutes short of a whole day, so `compact_after_hours: 24` produced today minus two and `23` would have produced today minus one. A cron minute was deciding which days compact. **A schedule is a wake, never a measurement** (CLAUDE.md section 2), so the threshold moved into the code above and the wake moved past the boundary it was sitting on.

**The cron is `40 0 * * *` - 00:40 UTC.** What that buys, at the default `compact_after_hours: 24`:

| Wake, on the 25th | The 24th ended 00:00 on the 25th | The 23rd ended 00:00 on the 24th | Newest eligible |
| --- | --- | --- | --- |
| 00:40 (the cron) | 0.7 h elapsed - **no** | 24.7 h elapsed - **yes** | the 23rd |
| 06:00, if GitHub is late | 6.0 h elapsed - **no** | 30.0 h elapsed - **yes** | the 23rd |
| 23:59, at the far edge | 24.0 h elapsed - **yes** | 48.0 h - **yes** | the 24th |

**Every wake from 00:00 to 23:59 gives the same answer but the last minute of the day**, so the margin against GitHub's scheduling drift is 23 hours 20 minutes. At the old 23:24 wake it was 36 minutes: a run that started late enough to cross midnight would have compacted a different day than the same run started on time, with nothing in the record to say so.

**The knob is a duration and the code reads it as one, so nothing about it is tied to 24.** `compact_after_hours: 30` waits thirty hours; a future task that wants fifteen days states fifteen days in its own declaration and reads the same function. The number a worker must not invent is the default, which is 24 because a whole day is the rule this design wanted.

**The oracle, in row 4:** `is_eligible` is driven at a fixed set of simulated wake instants spanning one UTC day - 00:00, 00:40, 12:00, 23:00, 23:59 - and the eligible set is identical at every one except the last minute, which is named in the test rather than tolerated. A second case drives it at `after_hours` of 1, 24, 30 and 360 and asserts the boundary moves with the knob. Neither case reads a clock.

1. Take the days from the watermark plus one up to the newest eligible day, at most `max_periods_per_run` of them, **and do each one separately**.
2. For each day: read that day's index, read exactly the files it names, settle their rows, write `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`, rewrite `index/daily.json`, delete the raw files, then advance the watermark. **Settling applies that ledger's rule from the settle table in `backend/idhazh/ledger/keys.py`, so a compacted file holds one row per record key** and nothing that reads it has to settle it (owner decision, 2026-09-27). Settling is per day: the monthly compaction joins settled days as they are and never settles across them, because a key with no date cell can legitimately repeat on two days. **A day whose index names no file still gets a zero-row file and an entry with `rows: 0`**, so the newest day `daily.json` names is always the day the watermark names - which is what lets a browser find the edge without opening a watermark.

**Two days that were missed produce two files, never one.** If the wake on the 24th fails and the next is on the 25th, the watermark still says the 21st, so the task compacts the 22nd into `22.parquet` and the 23rd into `23.parquet`. **Merging two days into one file is a defect, not an optimisation**: the file is named for the day it covers, and a file named `22.parquet` holding the 23rd's rows makes every date query wrong.

**A day already below the watermark that still has raw files is compacted again.** Its compact file is rewritten from the union and the watermark stays where it is. This is how a re-run of a failed job - GitHub allows one for thirty days, and it writes into its original day - is absorbed without a second mechanism.

#### The monthly compaction, in order, and no step may be reordered

1. A month `M` is **eligible** when the clock is more than `daily_keep_days` past `M`'s own end instant, which is 00:00 UTC on the first of the month after it. Same shape as the daily rule and the same reason: the month's end is a fact, the wake is not. Nothing else makes a month eligible.
2. Take the oldest eligible month after the monthly watermark. Read `index/daily.json` and confirm it names a daily file for **every** day of `M` that the daily watermark has passed. A missing day is a hole: refuse the month by name, leave the watermark where it is, and exit 1.
3. Write `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet` from exactly those files.
4. Rewrite `state/compact/<ledger>/index/monthly.json`.
5. Delete exactly the daily files absorbed, and rewrite `daily.json`.
6. Advance `state/compact/<ledger>/monthly/watermark.json` **last**.

Steps 3 to 5 are one commit, so there is no instant at which a date sits in two periods or in neither.

**A month is absorbed whole or not at all.** Absorbing it in pieces would make a date reachable through two periods, and the browser's coarsest-period rule would then read a month file that does not yet hold the day it asked for - a silent undercount with no 404 and no error, which is the defect class this design exists to remove. The price is that the daily period holds between `daily_keep_days` and `daily_keep_days + 31` days rather than exactly 45.

**What a watermark means, per period.** `daily/watermark.json.through` is the newest **day** whose raw files have been absorbed. `monthly/watermark.json.through` is the newest **month** fully absorbed, stamped `YYYY-MM`. Each answers exactly one question for its own compaction: where does the next run resume.

**A watermark is a producer file, and nothing in a browser opens one.** An earlier draft gave the reader a three-branch rule whose first branch read raw files for any date after the daily watermark - and section 5.9.4 says no raw file is ever published, so that branch was unreachable from a browser. The two indexes already state exactly what exists, so the rule is two lines: **is the date named in `monthly.json`? read that month file. Else is it named in `daily.json`? read that day file. Else it is not available.** That is **two fetches a panel instead of four, on every page load**. Owner ruling, 2026-09-26.

**A date that is not available is one of two things, and `daily.json` alone tells them apart.** Its newest day is the newest day compacted, because step 2 of the daily compaction gives every day it takes in a file and an entry, a day with no rows included. **A date after that day has not been compacted yet**: the console does not draw it, and says how far its data reaches. **A date at or before that day that neither index names is a hole**, which the console renders as `unreachable` rather than as a low number. Without the edge the two look alike, and today - never compacted yet - would turn every panel that reaches it `unreachable`. The zero-row entry is what keeps a quiet day from reading as a hole. Owner decision, 2026-09-27.

**Every task in the matrix runs at every wake, both monthly compactions included.** A compaction runs at the gardener's own wake, published or not - **no workflow step outside `idhazh-gardener.yml` triggers one** - and its own watermark decides whether a period is there to take. A monthly compaction therefore wakes daily and writes a record saying nothing was eligible about 29 days in 30. That costs one task slot inside a shard that runs anyway, and it buys the `plan` job a checkout of `config/` and `backend/utilities/` that no later ledger widens. It is also what a published ledger needs: the reader's open period is every day past the daily watermark and no raw file is published, so a day that has not been compacted is a day the console cannot draw.

**There is no `cadence` key, because a wake rate is a cron line and not a per-task value.** `on.schedule.cron` is `40 0 * * *`, which section 5.9.11 declares a workflow value row 8 transcribes. There is one wake and every matrix task is in it, so a per-task cadence would copy one line this config does not own into every declaration, each copy hand-written by a different row and none of them able to change anything. **The one task with a schedule of its own is `corpus-squash`**, which is not in the matrix: it carries `every_days` on its own policy member (section 5.9.5), transcribed from `finetune.prune_every_days: 30`, and the `history` job is what reads it. Owner ruling 2026-09-26, on Fowler's reading, following the 2026-09-26 ruling that left the key with no reader.

### 5.4 The paths, and the refusal that keeps the two roots true

`backend/idhazh/ledger/paths.py` is the only module that builds any of these, and the set is closed:

| Builder | Answers |
| --- | --- |
| `raw_path(ledger, date, file_id)` | `state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet` |
| `raw_index_path(ledger, date)` | `state/raw/<ledger>/index/<YYYY-MM-DD>.json` |
| `compact_path(ledger, period, covers)` | `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`, or the monthly shape |
| `compact_index_path(ledger, period)` | `state/compact/<ledger>/index/<period>.json` |
| `watermark_path(ledger, period)` | `state/compact/<ledger>/<period>/watermark.json` |

`ledger` is a `LedgerName` and `period` is a `Period` on every one of them, so a typo is a `ValueError` at the call site rather than a directory nobody meant. `compact_path` takes no `tier`: a compact path is compact by construction.

Grammar and the full tree in section 2. `.gitattributes` gains exactly these lines, path-anchored so a generic name cannot match elsewhere in the repository:

```
state/**/*.parquet                -merge
state/raw/*/index/*.json          -merge
state/compact/*/index/*.json      -merge
state/compact/*/*/watermark.json  -merge
*.parquet                         binary
```

**The door refuses a path whose second segment is neither `raw` nor `compact`, by name, at build time.** Not a lint, not a review habit - a `ValueError` naming the offending path and the rule. A test proves the refusal fires.

This needs no allow-list and no register of exceptions. The ledgers section 5.8 leaves on CSV do not call this door; they build paths through `ledger.day_shard_path`, which is untouched. A ledger migrates by moving to the door, and inherits the rule the moment it does. When the last one has moved, `ledger.day_shard_path` is deleted and the rule is the only way to build a state path.

`state/raw` and `state/compact` are subtracted from the trial-roots computation in the same commit that creates them. Without that, the `_trial_roots` computation in `backend/idhazh/stages/prune_state.py` reads them as unknown directories and the gardener deletes its own records.

### 5.5 The task registry

**The registry is discovered, not listed. The task list is open and it keeps changing** (owner ruling, 2026-09-26). The registry holds a name and a callable and nothing else, because config decides what happens and when.

`backend/idhazh/gardener/registry.py` holds `discover()` and `bind()`, and they are the whole of it. **A task module carries no name**, which is what makes it import-safe: it holds exactly two top-level names, `KIND` and `run`. `discover()` lists `backend/idhazh/gardener/tasks/` with `pkgutil.iter_modules` - **depth one, `.py` only, sorted by stem, skipping any stem beginning with `_`** - imports each module, and keys the result by filename stem. **It takes no config and reads none**, so nothing has to be loaded before it and import order decides nothing. The result is memoised for the process.

**Every task module takes its folders from the registry**: `ledger.tree_root(state_dir, which)` for a folder, `ledger.path(state_dir, which, covers)` for a file and `ledger.tree_relpath(which)` for a log line, and section 5.4's builders for a `raw-and-compact` ledger, which the first three refuse by name. The door test in `backend/tests/contracts/test_ledger_package.py` refuses a `LedgerName` joined onto a path by hand outside the ledger package, and a typed `state/<family>` string in any non-test module. A module that cannot import the ledger package and must spell a folder is added to that test's `TYPES_ITS_OWN_FOLDERS`, with its reason (handover from plan 53, 2026-09-27).

`bind(name, kind, modules)` returns the one callable that runs a declaration, in two lookups and no third: the module whose stem is `name` with hyphens turned to underscores, else the single module whose stem is the declaration's `kind` value. Anything else raises, naming the declaration and both stems it looked for. **A declaration names its module; no module names itself** - which is section 5.2's rule about a name written twice, applied inside Python as well as inside JSON.

**There is no `TASKS` constant and no `Task` type.** An earlier draft had a module build a tuple of tasks from the loaded policies of its kind, which the same section forbade in the next paragraph: `discover()` imports the module, so building that tuple means reading config at import. A module that carries no name has nothing to build.

**No task module imports pyarrow, duckdb or an HTTP client at module scope.** Discovery imports every module in every shard, so a heavy import at module scope is paid by every shard whether or not it runs that task; it goes inside `run`. Row 2's AST walk carries the check.

**`backend/idhazh/gardener/tasks/__init__.py` holds a docstring and imports no sibling.** An `__init__.py` that imported every module would make every import site pay for every task, including a test that wants one.

**The order at shard start is config first, then discovery, then the two-way check.** After the shape above the order is no longer load-bearing for correctness, which is the property that removed the contradiction; it is fixed anyway so the cheaper and likelier failure - a hand-edited declaration - fires before twenty imports.

**Four discovery failures. All are exit 2, all fire before anything is run, staged or deleted, and none is ever caught and skipped.**

| Failure | What it means | What the shard does |
| --- | --- | --- |
| A declaration with no module | The matrix handed this shard a name `discover()` does not produce | Exit 2, naming the task |
| A module that raises on import | `discover()` could not finish | Exit 2, naming the module, re-raising the original traceback. **Never caught and skipped**: a skipped module is a deletion that silently stopped running, and there is no frozen tuple left to notice its absence |
| A module declaring no task | A non-`_` module in the package with no `KIND`, no `run`, or a `KIND` of the wrong type | Exit 2, naming the module. A module beginning with `_` is support and is never imported by discovery, which is what makes this decidable rather than a judgement |
| Two modules declaring one name | The defect the open list creates that a frozen tuple did not have - a tuple with a duplicate is a visible diff, a directory with a duplicate is two files nobody diffed together | Exit 2, naming the name and both modules. **Never last-one-wins** |

**Exit 2 rather than exit 1 for all four: the tree is wrong and a retry cannot fix it.**

```python
@dataclass(frozen=True, slots=True)
class Task:
    """One verb. Everything else about it is config."""

    name: Slug                          # equals the config key and the --task value
    run: Callable[[TaskContext], Pass]


@dataclass(frozen=True, slots=True)
class TaskContext:
    state_dir: Path
    repo_root: Path
    today: date
    policy: TaskPolicy                  # this task's validated declaration
    run_id: str
    attempt: int
    job: ServerJob
    shard: int
```

`run` returns the `Pass` that `backend/idhazh/gardener/one_at_a_time.py` defines - moved there from `backend/idhazh/prune/` in row 4, because a module answering "how do I delete a collection's members one at a time" is the gardener's core and not a neighbour's - and `backend/idhazh/gardener/report.py` turns a `Pass` into the record row, filling the four new identity columns from the `TaskContext`. **`Pass` gains one field in that move: `written: tuple[str, ...]` beside `taken`**, filled on both sides of `dry_run`. `taken` holds what the task deleted or would delete and `written` what it wrote or would write; for a gardener task both are repository-relative POSIX paths.

**The invariant the runner asserts after every task and before anything is staged: every path in `Pass.taken` and every path in `Pass.written` sits under one of that task's `owns` prefixes**, matched as a POSIX directory prefix. A task using `owns_everything_else_under` is checked against the complement the config computed at load. A violation is exit 2, naming the path and the task. This is what stops the telemetry aggregation deleting a derived path its own producer rebuilds.

**It reads the selection, not the staging lists, so it fires the same way at `dry_run: true`.** `Pass.taken` is already the same list on both sides of `dry_run`, by its own docstring, and `Pass.written` is its twin. Every retention task ships report-only, so a check that ran only live would be a check nobody exercises until the first irreversible day.

**`owns` governs both verbs.** The write side is not exempt: a permission that covers deleting and not writing has a hole in exactly the direction a compaction can do damage. The one write no task owns is the shard's own record under `state/raw/gardener/`, which the shard writes rather than a task, and which carries its own one-line check (section 5.9.6).

### 5.6 The checkout, the commit loop and the exit codes

**The checkout is partial and sparse, and that is what keeps the job's cost flat as the repository grows** (Guardrail #12). **The workflow has three checkouts, one a job, and each is labelled here so none is copied into the wrong job.**

**The `plan` job's checkout** has no cone expression, because this job runs before any install and opens nothing outside `config/` and `backend/utilities/`:

```yaml
      - uses: actions/checkout@v6
        with:
          fetch-depth: 1
          filter: blob:none
          sparse-checkout: |
            config
            backend/utilities
```

**The `run-tasks` checkout.** A `run-tasks` runner never downloads historical parquet:

```yaml
      # The cone is this shard's tasks' `owns` prefixes, emitted by the `plan`
      # job from the same config that declares them, plus the three directories
      # the code lives in. A task whose ledger sits outside the cone lists an
      # empty directory and reports success - the one failure no gate catches.
      - uses: actions/checkout@v6
        with:
          fetch-depth: 1
          filter: blob:none
          sparse-checkout: |
            config
            backend
            .github
            ${{ matrix.cone }}
```

`filter: blob:none` omits file contents until git needs one; `sparse-checkout` keeps the rest out of the working tree.

**The `history` job's checkout is not sparse, and that is deliberate.** It takes `fetch-depth: 1` over the whole tree so its standard-library reader can open `corpus/corpus.meta.json` and `config/gardener/corpus-squash.json`, then on a due day a second `actions/checkout@v6` at `fetch-depth: 0`, which takes everything anyway. A cone here would buy nothing and would be one more cone to keep in step.

**`matrix.cone` is a field of the section 5.9 plan payload, never an expression invented in YAML.** `gardener_shards.py` computes it from the same config that declares `owns`.

**The cone stops growing only once its tasks run live, and until then `max_cone_mb` is what stops it growing unseen.** Every prefix in it is a ledger some task prunes to a window, so a live task holds its prefix to that window. But every retention task ships `dry_run: true` (section 5.2.1), so on the first wake no prefix is held by anything, and each stays unbounded until a person turns its task's `dry_run` off, which is ESCALATE trigger 6. That makes the cone a declared growing read under Guardrail #12, recorded in `docs/concepts/growing-reads.md` by row 8, rather than a bounded one. The shard planner does not weigh bytes, so the two heaviest prefixes can land in one shard; the ceiling in section 5.2 turns that into a red job instead of a slow one. The one prefix that is not a ledger is the `trials` task's `state`, and that task reads **directory names at depth one** - `git ls-tree HEAD state/`, no `-r` - because it is looking for a directory nobody claims and the contents of a claimed one are not its business. One tree read at constant cost, and it replaces a sweep over every file under `state/`.

**Before a task lists anything, it asserts its `owns` prefixes exist in the working tree and exits 1 naming the prefix if one does not.** A silent zero is what a wrong cone produces, and an assertion is the only thing that turns it into a red job. **A task using `owns_everything_else_under` asserts nothing about the working tree**: it emits an empty cone by design and reads `git ls-tree HEAD state/` out of the object database, so `state/` is legitimately absent from its checkout and the assertion would fail on every wake. One harness test: every `owns` prefix in the committed config appears in exactly one shard's cone, computed by the function the `plan` job calls, and a complement task contributes none.

**Clone and fetch are not two ways to do this, and neither is written by hand.** `git clone` creates the repository; `git fetch` updates one that already exists, so a job that has checked nothing out has nothing to fetch into. The job needs both, at different moments - the clone once at the top, a fetch on each turn of the commit loop below. The clone is not spelled out because `actions/checkout@v6` already does it and is the only step that writes the credential header the later `git push` needs; all thirty checkout steps in this repository use it, and a hand-rolled `git clone` beside it buys a second clone or a push with no token.

```python
def publish(shard: Shard, message: str, *, attempts: int) -> int:
    """Land the files this job already produced. The work is not done again."""
    for attempt in range(1, attempts + 1):
        git("fetch", "origin", "main", "--depth=1")

        landed = remote_blob(shard.record_path)
        if landed is not None:
            if landed == local_blob(shard.record_path):
                return EXIT_OK                      # an earlier attempt won
            return EXIT_INTEGRITY                   # two writers, one path

        git("reset", "--mixed", "origin/main")      # the index moves, the tree does not

        # Explicit files, never a prefix. `git add -- <prefix>` after a reset
        # stages every difference under it against the new tip, and digest.yml
        # writes into these prefixes five times a day - so a prefix would stage
        # the deletion of a shard that landed while this job worked.
        for path in shard.written_paths:
            git("add", "--sparse", "--", str(path))
        for path in shard.deleted_paths:
            git("rm", "--cached", "--sparse", "--ignore-unmatch", "--", str(path))

        # Read the index back. This is the one class of error that commits
        # cleanly, pushes cleanly and passes every gate.
        if staged_names() != {str(p) for p in shard.written_paths | shard.deleted_paths}:
            return EXIT_INTEGRITY

        git("commit", "-m", message)
        if git_ok("push", "origin", "HEAD:refs/heads/main"):
            return EXIT_OK
        sleep_with_jitter(attempt)
    return EXIT_PUSH_KEPT_LOSING
```

**Three shapes this forces, and the first is load-bearing.**

- **`Shard` carries `written_paths` and `deleted_paths`, two explicit file lists the tasks produced.** `owns` stays in config as the **permission** each path is checked against, never as the staging list. One field answering both questions is how a gardener deletes a file a digest run wrote twenty minutes earlier and exits 0.
- **`attempts` is the only bound on the loop, and the backoff is declared rather than left to a worker.** `sleep_with_jitter(k)` sleeps a uniform random time between zero and `min(2 ** (k - 1), 8)` seconds - full jitter, so five shards that collide do not retry in lockstep. At `attempts: 5` the sleeps are capped at 1 + 2 + 4 + 8 = 15 seconds and the whole loop is bounded near 30 seconds including five round trips. **There is no `push_deadline_seconds` in this config.** `backend/utilities/commit_and_push.py` uses a monotonic deadline and `config/idhazh.json` declares `run.push_deadline_seconds: 300` for its own pusher, but at this attempt count and this backoff a 300-second deadline can never fire, and a knob that cannot change behaviour fails Guardrail #6's substitution test - which is the same test that deleted `cadence` in row 4. **`attempts` must exceed `shards`**, refused at config load, because the last-placed shard needs an attempt left after every other shard has landed.
- **The loop needs a git identity before its first commit**, set from the same constants `commit_and_push.py` uses: `miztiik <miztiik@users.noreply.github.com>` (CLAUDE.md section 8). Without it a bare runner exits 128 on `git commit`, and `backend/tests/workflows/_harness.py`'s identity-source tuple names `prune.yml` today, so it moves to the new filename in row 8 or loses its only member.
- **`git config index.sparse true` immediately after checkout.** `git reset --mixed` expands the index to the whole repository unless the index is sparse, and `actions/checkout` does not set it - so without this the worktree cost is flat and the index cost is not.
- **The index read-back is exit 2, beside the ownership assertion.** It is what stops this class of error returning later as a different prefix.

**The work happens once, before the loop. The loop only stages and pushes.** That is what keeps a job's cost flat however many times it loses a race, and it is why nothing here has to be recomputed against the new tip: every path this job touches is one the registry proves no other task owns, so a moved tip cannot have changed them. **`work_ended_at` is stamped at that boundary** - the last instant before `publish()` is called, once per shard, onto every record row the shard writes (section 5.1).

**Same path and same bytes is a successful retry. Same path and different bytes is a data-integrity error.** The invariant holds as written, with no second tier, because **the file is written once and its name is minted once**. A retry re-stages the same bytes; it does not re-produce them. Two different contents at one path would mean two writers minted one identifier, which the identifier's construction (section 5.7) makes impossible - so exit 2 is an assertion that should never fire, which is exactly what it is for.

**Every task is one kind: add its record, always; then delete its selected paths, possibly none, in one commit.** Three writer kinds were three ways to get this wrong - the worst being that a dry run selects nothing, so a "nothing left to delete" verdict would report success and publish no record at all.

**What a `dry_run: true` task contributes, stated once because it is the normal case and not the edge case.** Every retention task and both collection tasks ship report-only (section 5.2.1), so on the first wake this is nearly the whole garden. A dry-run task **runs**, computes its full selection, and fills `Pass.taken` and `Pass.written` exactly as a live task would - that list is what a dry run delivers, and the reason a count would not do. It adds **nothing** to `Shard.written_paths` and **nothing** to `Shard.deleted_paths`, and its record row carries `selected`, `taken` and `bytes_freed` saying what it would have taken. **The ownership check still runs, over the selection** (section 5.5), so a report-only task whose selection reaches outside its `owns` is exit 2 on the wake it is added, not on the day somebody flips the flag. **A shard of nothing but dry-run tasks still stages exactly one file - its record - and still pushes**, which is what makes the onboarding record readable the next morning, and why the commit loop has no "nothing to do" branch.

| Code | Meaning | Retryable |
| --- | --- | --- |
| 0 | Every task in this job landed, or was already landed | - |
| 1 | A task failed. Its row carries `stopped_because: failed` and `resume_from`; its shard siblings still ran and still have rows | Yes, next wake |
| 2 | A task's selection - a path it wrote or deleted, or would have at `dry_run: true` - sits outside its `owns`; or the shard's record sits outside `state/raw/gardener/`; or one record path holds two identities. The ownership claim is wrong | **No** |
| 3 | The push kept losing after `attempts`. Nothing landed, so a windowed task simply runs again at the next wake and a periodic one is still due | Yes, next wake |

**Why reset-and-reapply rather than rebase, stated once.** The writer has exactly one local change - the files it just produced - so there is nothing to merge. Reset to the new tip, re-add the same artefacts, commit, push. **The amount of local work does not grow with the size of the repository**: no historical parquet is downloaded, nothing accumulated is rebased, no other directory is reconciled by hand. A rebase would also carry a real hazard: a deletion rebased onto an append to the same union-merged file keeps both sides and the deleted rows come back at exit zero.

`git reset --hard` stays banned (CLAUDE.md section 8); `--mixed` is not on that list and is what keeps the working tree while the index moves. `--force-with-lease` is not used - a lease names the commit a rejection has just made stale.

### 5.7 The unit identifier, and the envelope inside the file

**North star, and it binds every ledger added after this plan. A filename carries identity, never meaning. Everything a reader needs to know about a file is inside the file.** A filename that is parsed is an undeclared, unversioned, unvalidated schema, and renaming a file becomes a breaking change. With the envelope inside, a file can be renamed, moved or re-partitioned and every reader still knows what it holds - which is the thing a filename cannot survive when one query opens a hundred files at once.

This plan applies the rule to the ledgers it creates and to the two row 3 migrates. The trees section 5.8 leaves behind keep their parsed names until they migrate, because `ledger.SEGMENT_NAME` is a compiled pattern that `idhazh.path_classes` uses to answer whether a committed path has exactly one writer, and retiring that is the migration plan's work, not this one's.

#### The identifier, and why there are two

**One file carries two identifiers, because a file answers two questions and one value cannot answer both.** `unit_id` answers *what work does this record?* and must be identical for every attempt at that work. The filename answers *which file is this?* and must differ for every file ever written.

**An earlier draft made one value do both and it did neither.** It put a write clock and `attempt` into `unit_id`, so every write minted a fresh id - and then the same section called deduplication `GROUP BY unit_id`. That GROUP BY collapsed nothing: a re-run's rows sat beside the originals forever, and the one mechanism this design has for absorbing a failed job was a sentence with no machine behind it. Splitting the two restores it.

| | `unit_id` | `file_id`, which is the filename |
| --- | --- | --- |
| Answers | which work unit | which file |
| Kind | `uuid5`, pure, no clock | `uuid8`, clock first |
| Seeded from | `ledger`, `covers`, `run_id`, `job`, `shard`, `producer` | the 48-bit write clock, then 74 bits of `sha256(unit_id, attempt, written_at_ms)` |
| Same across two attempts | **yes - that is the whole job** | no - every write is a new file |
| Lives in | a column | the filename, and a footer key |
| Used for | `GROUP BY unit_id`, highest `attempt` wins | naming, and a listing that sorts by time |

`backend/idhazh/ledger/filenames.py`, beside the CSV segment grammar that answers the same question ([`../docs/architecture/contracts/ledger-registry.md`](../docs/architecture/contracts/ledger-registry.md) - nothing outside the package names a file under `state/`):

```python
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")

def unit_id(*, ledger: str, covers: str, run_id: str, job: str, shard: int, producer: str) -> uuid.UUID:
    """Which work unit this file records. Identical for every attempt at that unit."""
    return uuid.uuid5(NAMESPACE, f"{ledger}|{covers}|{run_id}|{job}|{shard}|{producer}")

def file_id(*, unit: uuid.UUID, attempt: int, written_at_ms: int) -> uuid.UUID:
    """The name of one file. Minted once, when the file is written, and then kept."""
    digest = hashlib.sha256(f"{unit}|{attempt}|{written_at_ms}".encode()).digest()
    return _pack_v8(
        written_at_ms & 0xFFFFFFFFFFFF,                        # the clock, sortable
        int.from_bytes(digest[0:2], "big") & 0xFFF,
        int.from_bytes(digest[2:10], "big") & ((1 << 62) - 1),
    )

def _pack_v8(unix_ms: int, rand_a: int, rand_b: int) -> uuid.UUID:
    """Pack RFC 9562 version 8: 48 bits of clock, 12 free bits, 62 free bits."""
    return uuid.UUID(
        int=(unix_ms & 0xFFFFFFFFFFFF) << 80
        | 0x8 << 76
        | (rand_a & 0xFFF) << 64
        | 0b10 << 62
        | rand_b & ((1 << 62) - 1)
    )
```

| Bits | Holds |
| --- | --- |
| 80-127 | `unix_ms`, 48 bits, most significant - what makes the name sort by time |
| 76-79 | `0x8`, the version, fixed by the RFC |
| 64-75 | `rand_a`, 12 bits |
| 62-63 | `0b10`, the variant, fixed by the RFC |
| 0-61 | `rand_b`, 62 bits |

**The test vector is the worked example's own name:** `_pack_v8(0x01A0D03C2E00, 0x461, 0x18E0A67898E9A802)` returns `01a0d03c-2e00-8461-98e0-a67898e9a802`, with `version == 8` and the RFC 4122 variant. The test asserts all three.

Measured 2026-09-24 against `uuid.uuid8`: version 8, variant RFC 4122, files written in the same millisecond share the 13-character clock prefix, and sort order equals time order across milliseconds.

| # | Decision | Why |
| --- | --- | --- |
| 1 | **`attempt` is in `file_id` and must never be in `unit_id`** | GitHub holds `run_id` steady across a re-run, so `attempt` is the only field that tells two attempts apart. In `unit_id` it gives them different ids and **both survive the GROUP BY** - which is precisely the duplicate the GROUP BY exists to remove. In `file_id` only, they collapse to one and the newest attempt wins |
| 2 | **`producer` replaces the per-process call sequence an earlier draft had** | Two producers write `item-health` in the `assemble` job, so something has to tell them apart. A sequence counts calls inside one process, so it changes between attempts - poison in a key whose entire job is to be stable. `producer` is the declared name of the module that writes (`stages.assemble`, `telemetry.work`), it is what genuinely differs, and it survives a re-run unchanged |
| 3 | `written_at_ms` is the clock inside `file_id`, and it is **passed in** rather than read inside the function | The name then sorts by time, which is what a directory listing and any later object ledger both want. Passing the instant keeps the function pure, so its test needs no clock (CLAUDE.md section 2) |
| 4 | **The name is minted once, when the file is written, and held in a variable.** A push retry re-stages that same path | The caller keeps the file and the name across push attempts, exactly as section 5.6's checkout recipe does. `file_id` is recomputable from the envelope, which is what makes the oracle possible, but no code path needs to recompute it |
| 5 | `_pack_v8` is hand-written, about ten lines | `uuid.uuid8` arrived in Python 3.14 and `requires-python` is `>=3.12`. The RFC 9562 layout is fixed, so packing it ourselves costs less than raising the floor |
| 6 | Within one millisecond the order of two `file_id`s is arbitrary | The bits after the clock are a hash. Ordering is a property across time, not within an instant. Said plainly because a group of files from one run looks ordered and is not |
| 7 | What it costs: a person reading a git diff no longer sees the run, attempt, job and shard in the filename | The path still carries `<ledger>/<YYYY>/<MM>/<DD>`, the commit message names the run, and the envelope carries all of it. A reader who needs more opens the file |

**Deduplication, stated once so nobody has to derive it.** A union over any set of files is `GROUP BY unit_id`, keeping the group's **highest `attempt`**. Two files share a `unit_id` and an `attempt` only when a push retry re-staged the same name, so that pair is byte-identical and either one wins.

**This is what makes row 7's "a re-run of a failed job is absorbed" true rather than hopeful.** GitHub re-runs only the jobs that failed, into the original `run_id`, so the re-run writes `attempt: 2` files whose `unit_id`s equal the originals'. The recompaction unions both sets and the first attempt drops out. **A re-run replaces its attempt rather than adding to it** - if attempt 2 produced fewer rows than attempt 1, the day holds attempt 2's rows, because a re-run is the correction and not a supplement.

#### The envelope

Parquet file-level key-value metadata, written by `backend/idhazh/ledger/parquet.py`, declared as `FileEnvelope` in `backend/idhazh/contracts/file_envelope.py`. Parquet metadata is bytes to bytes, so every value is a UTF-8 string and any structure is JSON inside one.

**What goes in a column and what goes in the footer, with the measurement that decides it.** A constant column costs about **250 bytes flat, whatever the row count** - a page header, a dictionary page and statistics. **Eight identity columns are about 2,000 bytes**: 26 percent of a 3-row raw file, 6 percent of a 420-row month file. The envelope costs about **1,920 bytes for 612 bytes of JSON**, because pyarrow ledgers schema metadata twice, once as parquet key-value and once base64-encoded inside `ARROW:schema`. `store_schema=False` saves 3,244 bytes and **deletes the envelope entirely**, so it cannot be used.

So the rule: **a field is a column when a query filters or groups on it**, because row-group statistics then let a reader skip a whole file without decompressing anything - measured, a constant column carries `min == max` and that is what a skip reads. **Everything else is footer only**, where it is provenance a person reads after the fact and costs nothing per row.

| # | Key | Value | Also a column? |
| --- | --- | --- | --- |
| 1 | `envelope_version` | `YYYY-MM-DD`. The envelope's own stamp, distinct from the row schema's, so the envelope can evolve | no |
| 2 | `schema_version` | `YYYY-MM-DD` of the row contract (CLAUDE.md section 11) | yes, as `version` - a reader selects rows of one shape |
| 3 | `tier` | `raw` or `compact`. A compacted file says it is one | no - the path already says it, and this is the copy that survives a move |
| 4 | `ledger` | Which ledger: `gardener`, `visual-prune`, `item-health`. **This key was `dataset` until 2026-09-26**, which was a fourth word for a thing that already had three | yes - the commonest filter |
| 5 | `covers` | What this file covers: a day (`2026-09-23`) on a raw or daily file, a month (`2026-08`) on a monthly one. **Not** the day it was written | yes, as `covers` - every time filter uses it |
| 6 | `period` | `daily` or `monthly`, on a `compact` file only. Absent on a raw file | no - the path says it, and this is the copy that survives a move |
| 7 | `written_at_ms` | Arrival time, epoch milliseconds, UTC. **This is the clock inside `file_id`** | no - never filtered, and as a column it is 250 bytes for one value |
| 8 | `run_id`, `attempt`, `job`, `shard` | Which writer produced it | yes, all four - tracing a bad run is a filter on `run_id`, and **`attempt` is what the deduplication ranks on** |
| 9 | `producer` | The declared name of the module that wrote it - `stages.assemble`, `telemetry.work`. It is in `unit_id` because two producers write one ledger in one job | no - **and not because a query can filter on `unit_id` instead**, which an earlier draft claimed. `unit_id` is a `uuid5`: one-way, so nothing recovers a producer from it short of enumerating every `(ledger, covers, run_id, attempt, job, shard, producer)` and recomputing. It is out for the reason stated two paragraphs above - **no query filters on it** - and the day one does, it becomes a column at 250 bytes. Until then it is provenance a person reads in a footer, and keeping it out holds the identity columns at eight |
| 10 | `unit_id` | Which work unit this file records. `uuid5`, **stable across attempts**, computed from keys 4, 5, 8 and 9. Deduplication is `GROUP BY unit_id` keeping the highest `attempt`, never a filename convention | yes - you cannot group by a footer key |
| 11 | `file_id` | The identifier in the filename. `uuid8`, clock first, different for every file ever written | no - `content_sha256` already tells two files apart, and the filename is right there |
| 12 | `content_sha256` | Over the row bytes. Tells two files apart after a rename and proves a copy is a copy | no |
| 13 | `git_sha` | The commit the producing run checked out. The one field tying a data file to the code that made it | no |
| 14 | `writer` | `idhazh.ledger.parquet`. The parquet footer's own `created_by` names pyarrow, not us | no |
| 15 | `writer_version` | The engine version, because a footer is not byte-stable across engine versions | no |
| 16 | `compression` | `snappy` or `zstd` | no |
| 17 | - | *(`name_strategy` was here and is cut. It had a beneficiary only under a design where a reader computes a name and must know which algorithm minted it; that design died on N6 on 2026-09-25, so the key has no reader and `envelope_version` already answers the question it was invented for)* | - |
| 18 | `built_from` | On a `compact` file only: how many files it read to make this one. Absent on a raw file | no |

**`row_count` is deliberately not a key.** The parquet footer already carries `num_rows`, free and authoritative, and the footer is written last so its presence already proves the file is complete. A second spelling is two answers to one question (Guardrail #4).

A worked envelope, and what it costs:

```python
{
  "envelope_version": "2026-09-26", "schema_version": "2026-09-24", "tier": "raw",
  "ledger": "gardener", "covers": "2026-09-24",
  "written_at_ms": "1790200000431",
  "run_id": "2026-09-24-17482910337", "attempt": "1", "job": "run-tasks", "shard": "03",
  "producer": "gardener.tasks",
  "unit_id": "7b2f1c84-0e5a-53d1-9c40-1f8b6a2e4d07",
  "file_id": "01a0d03c-2e00-8461-98e0-a67898e9a802",
  "content_sha256": "9f2c...", "git_sha": "0735031c2...",
  "writer": "idhazh.ledger.parquet", "writer_version": "25.0.1",
  "compression": "snappy",
}
```

Read back without touching a row: `pq.read_metadata(path).metadata[b"unit_id"]`, and `pq.read_metadata(path).num_rows`. Verified to round-trip intact, 2026-09-24.

**The oracle for this, in row 2:** every file the door writes carries a complete envelope; the envelope round-trips byte-identically; `file_id` in the envelope equals the filename stem; `file_id` recomputed from `unit_id`, `attempt` and `written_at_ms` equals both; and `unit_id` recomputed from the envelope's own six identity fields equals the `unit_id` column. **One more case, and it is the one that would have caught the collapsed design:** write the same work unit twice with `attempt` 1 and 2, confirm the two files have different names and the **same** `unit_id`, then union them and confirm the reader returns attempt 2's rows only.

### 5.8 Every ledger, its producer, its consumer, and what moves it

**The CSV-to-parquet migration of all of `state/` is bounded by five chokepoints, not by twenty-nine ledgers.** That is why this section exists: it is the finding that makes telemetry-intent N1 and N11 affordable, and it is what a later plan starts from instead of re-deriving.

| Side | The chokepoint | What goes through it |
| --- | --- | --- |
| Write | `ledger.write_segment` and `extend_segment`, keyed by `LedgerName` and refused outside `DAY_TREES` | Eight day-sharded ledgers, since plan 54 took `day-validations` out of `DAY_TREES`: `item-health`, `host-fingerprint`, `span-rollup`, `scores`, `score-index`, `candidate-models`, `feed-health`, `counterfactual-scores` |
| Write | `ledger.extend_ledger_file` | Seven append-and-union ledgers: `feed-retirements.csv`, `visual-prunes`, `scored-pairs`, `fitted-thresholds`, `llm-council/shard-outcomes`, judge `metrics`, `merge-line-holdout-scores` |
| Write | `ledger.write_item_health_summary` | One month-partitioned ledger, `item-health-summary`, **written whole rather than appended to** - see row 5 decision 11 |
| Read, backend | `backend/idhazh/day_shards.py` | Every day-sharded ledger the backend compacts or settles |
| Read, console | `readCsv`, `readDayShards`, `dayShardFiles`, `settledDayShards` - all four exported from `frontend/src/lib/server/payload.ts` | Every ledger the console draws |

`backend/idhazh/ledger/` is the sixth door, and it is the one the other five eventually forward to. **That is what makes row 2 the load-bearing row of this plan**: it is not a utility the gardener happens to need, it is the door the other seventeen writers walk through later.

**The ledgers, producer and consumer verified by call site on 2026-09-24.** **Row 9 of this plan moves the three ledgers the console reads**, and plan 51's row titled **The three ledgers the console reads are published** is what publishes them. **A ledger the console draws is named in `LedgerConfig.published` (section 5.9.4), which is what a browser may address and the input to the published-ledger refusals in section 5.2.**

| Ledger under `state/` | Producer | Consumer | Console route | Moved by |
| --- | --- | --- | --- | --- |
| `feed-retirements.csv` | `stages/plan.py`, `stages/assemble.py` | those two, plus `telemetry/publish/source_health.py` | - | **Row 3** |
| `visual-prunes` | `stages/prune_state.py` | backend only | - | **Row 3** |
| `raw/gardener` | `gardener/report.py` | the gardener's own dueness check | - | **Row 4**, born parquet |
| `seen` | `stages/plan.py` | `stages/plan.py`, `discover.py` | - | a later plan |
| `published` | `stages/assemble.py` | `day_shards.py`, `month_partition.py` | - | **Unowned, and it is the one to own first.** The heaviest surviving `merge=union` tree: appended to on every run, 34 committed files counted 2026-09-26, two backend readers and no console route. Three plans name it and none takes it. **It does not belong to plan 52**, which is a console plan, and it does not belong here - this plan's own scope line puts the rest of `state/` in a successor. It needs that successor named, with `published` as its first row |
| `item-health-summary` | `retention.compact_month`, through `ledger.write_item_health_summary`. **The gardener owns it from row 5** | `month_partition.py`, and `retention.py`'s own read-back check | - | a later plan. **A whole-file month rewrite, which N6 forbids** - row 5 decision 11 |
| `digest-fragments` | `stages/assemble.py` | `assemble.py` | - | a later plan. **The filename is the run id and a re-run writes it again** - row 5 decision 12 |
| `traces` | `telemetry/traces.py` | `telemetry/rollup.py` | - | a later plan |
| `counterfactual-scores` | `stages/plan.py` | backend only | - | a later plan |
| `score-index` | `evals/writer.py` | `evals/writer.py`, `stages/rebuild_score_index.py` | - | a later plan |
| `day-validations` | **gone before row 5 runs** - plan 54 decommissions the receipt end to end and renames `stages/validate_days.py` to the `publication_checks/` package | - | - | **Plan 54**, not a later plan |
| `candidate-models` | `stages/decide.py`, `stages/qualify_decide.py` | backend only | - | a later plan |
| `llm-council/shard-outcomes` | `council/session.py` | backend only | - | a later plan |
| `content-similarity-judge/scored-pairs` | `stages/count_verdicts.py` | `similarity/counting.py` | - | a later plan |
| `content-similarity-judge/metrics` | `stages/count_verdicts.py` | backend only | - | a later plan |
| `pipeline-tests/**` | the pipeline-test workflow | backend only | - | a later plan |
| `content-similarity-judge/fitted-thresholds` | `stages/set_merge_line.py` | `lib/server/similarity-ledger.ts` | `/console/judgement` | a console plan |
| `content-similarity-judge/merge-line-holdout-scores` | `stages/score_merge_line_holdout.py` | `lib/server/similarity-holdout.ts` | `/console/judgement` | a console plan |
| `content-similarity-judge/score-distribution.json` | `stages/count_verdicts.py` | `lib/server/similarity-ledger.ts` | `/console/judgement` | a console plan |
| `content-similarity-judge/holdout-pairs.csv` | hand-labelled, read by `similarity/holdout.py` | `lib/server/similarity-holdout.ts` | `/console/judgement` | a console plan |
| `span-rollup` | `stages/work.py` | `lib/server/span-rollup.ts`, `run-timeline.ts` | `/console` | **Deleted, not migrated** - plan 52's row for the last console route |
| `host-fingerprint` | `telemetry/silicon.py` | `lib/server/host-fingerprint.ts`, `machine-counters.ts` | `/console/machine` | **Row 9** |
| `day-metrics` | `stages/assemble.py` | `lib/server/payload.ts`, `model-work.ts` | `/console/model` | a console plan |
| `feed-health` | `stages/plan.py` | `lib/server/payload.ts`, `lib/feed-health.ts` | `/console/voices` | a console plan |
| `item-health` | `stages/assemble.py`, `stages/record.py` | `lib/server/payload.ts`, `machine-counters.ts` | four routes | **Row 9** |
| `scores` | `evals/writer.py` | `lib/server/payload.ts` | `/console/model` | **Row 9** |

**What `state/` weighs today, so no later plan re-measures it.** Seventeen leaf ledgers and one flat file, **909 files, 56.6 MiB**, measured 2026-09-26 - it gained 931 files in the seven days before that reading, which is itself the Guardrail #12 signal. Three ledgers hold two thirds: `traces`, `seen` and `scores`. The two row 3 takes are 11 KB and 0.1 KB together - deliberately, because rows 2 and 3 prove a door rather than move a corpus.

---

### 5.9 The shapes a worker must not invent

**Every shape below is declared here or the row that needs it cannot start.** A field named without its type, its default, its nullability and one sentence of description is not declared (Guardrail #3). Ranked by where a worker stops first.

#### 5.9.1 `Tier`, `Period`, `Format`, `WriterIdentity`, `FileEnvelope` - `backend/idhazh/contracts/file_envelope.py`

**`LedgerName` is not declared here. It already exists** in `backend/idhazh/contracts/ledger_name.py`, holding every ledger under `state/` and having replaced `SegmentLedger` and the per-ledger directory constants at once. This plan imports it. An earlier draft declared a two-member `StoreName` here, and rows 9 and 10 then added four names that the older enum already held - two closed sets over one vocabulary, drifting apart the moment one of them gained a member.

**What this plan still owes `LedgerName` is the membership rule, not the type.** A ledger joins the gardener by having a compaction declaration in `config/gardener/`; the two-way refusal in section 5.2 asserts that against `LedgerName` rather than against a list of its own.

```python
class Tier(StrEnum):
    """Which of the two roots under `state/` a file sits in."""
    RAW = "raw"          # data as a writer left it
    COMPACT = "compact"  # what a compaction left behind

class Period(StrEnum):
    """How much time one compact file covers. Also the directory name."""
    DAILY = "daily"
    MONTHLY = "monthly"

class Format(StrEnum):
    PARQUET = "parquet"
    JSON = "json"

class WriterIdentity(Model):
    """Which run, attempt, job, shard and module wrote a file, and from which tree."""
    run_id: RunId            # no default; the `RUN_ID_PATTERN` alias, not a bare str
    attempt: int             # ge=1, no default
    job: ServerJob           # no default
    shard: int               # ge=0, no default
    producer: str            # no default; the writing module's dotted name, plus ":<part>" when one module writes one record as two files (row 9); min_length=1
    git_sha: CommitSha       # no default

class FileEnvelope(Contract):
    __schema_stem__: ClassVar[str] = "file-envelope"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-25",
            change="Initial shape: the footer keys section 5.7 declares, raw and compact alike.",
            why="A parquet file must say what it holds without its filename being parsed.",
        ),
    )
```

**`WriterIdentity` is a `Model`, not a `Contract`.** It is nested inside an envelope and has no file of its own; a `Contract` would demand a stem, a changelog and a version string for a value that is never written alone. The same rule puts `CompactEntry` (5.9.13) and `Shard` (5.9.6) on `Model`.

**`ChangelogEntry` takes three fields - `version`, `change` and `why` - not two.** `backend/idhazh/contracts/base.py` requires all three, so every "one `changelog` line" instruction in this plan means a three-field entry. The two-field form in CLAUDE.md section 11 is the prose summary, and the code is what validates.

**`GardenerConfig` and `GardenerPlan` are `Model`s, not `Contract`s.** One is a configuration file this project authors, which CLAUDE.md section 11 scopes versioning away from; the other is a process-local payload no later run reads. **The four stems are `file-envelope`, `raw-day-index`, `compact-index` and `watermark`**, and those four are the only new entries in `CONTRACTS`.

**Nothing is generated.** `schemas/` and `idhazh.contracts.export` were deleted on 2026-09-23 and `backend/tests/contracts/test_no_generated_layer.py` is a ratchet that fails if either returns. A new contract joins `CONTRACTS` and `__all__` in `backend/idhazh/contracts/__init__.py`, and that file is in the `Files touched` list of every row that mints one.

**No `WriterIdentity` field is nullable and none has a default**: an identity with a hole cannot mint a name. Defaults elsewhere are named where they are declared. `fmt: Format | None = None` on `persist()` means **take it from `config/idhazh.json`'s `ledger.format`**, and that is the only meaning it has.

#### 5.9.2 The arrow type mapping - `backend/idhazh/ledger/arrow_schema.py`

Row 2's rejected alternative 4 forbids inferring a schema from the first row, so **the mapping is the module** and it is a literal table, not a fallback chain. Every annotation the two migrated contracts use appears here; an annotation that is not in the table raises by name.

| Python annotation | Arrow type | Nullable |
| --- | --- | --- |
| `str`, and every constrained-string alias in `contracts/base.py` | `pa.string()` | no |
| `str \| None` | `pa.string()` | yes |
| `int` | `pa.int64()` | no |
| `int \| None` | `pa.int64()` | yes |
| `float`, `float \| None` | `pa.float64()` | as annotated |
| `bool`, `bool \| None` | `pa.bool_()` | as annotated |
| `DateStamp` | `pa.string()`, **not `date32`** | no |
| any `StrEnum` | `pa.string()`, **not `dictionary`** | as annotated |
| anything else | raise `TypeError` naming the field and its annotation | - |

`DateStamp` stays a string because it is a `YYYY-MM-DD` stamp a person reads in a diff and a partition path, and a date type would make two spellings of one value. A `StrEnum` stays a string because a dictionary column's encoding is an engine's choice and this file is read by two engines.

#### 5.9.3 `FileEnvelope` - the field list is section 5.7's table and nothing restates the count

Section 5.7's table is the field list. **No sentence anywhere gives a number**, because three sentences gave three different numbers and a worker could not tell which was the shape. One key is kept as a tombstone rather than deleted, because a reader of a committed envelope needs to know a key is gone rather than missing: `name_strategy` has no reader, no second strategy, and `envelope_version` already answers the question it was invented for.

`built_from: int | None` is the one key a raw file omits.

**The model declares the typed field only.** One method, `as_metadata() -> dict[bytes, bytes]`, is the single place a value becomes a UTF-8 string, and one classmethod, `from_metadata(mapping)`, is the single place it comes back. Every value is `str(value)`, except `built_from`, which is omitted from the mapping when `None`, and `attempt` and `shard`, which are zero-padded to two digits. The round-trip test asserts `from_metadata(e.as_metadata()) == e` for a raw envelope and a compact one. **There is no parallel string field on the model**: a second spelling of every key is a second thing to keep in step.

**One envelope shape, raw and compact alike.** Two shapes would be two contracts and a reader that has to know which one it is holding. The cost of carrying the envelope on a small raw file is bounded rather than growing: a published ledger's raw days are compacted at the end of every content run and every other ledger's within the week.

#### 5.9.4 `LedgerConfig`, and the literal that goes in `config/idhazh.json`

```json
"ledger": {
  "format": "parquet",
  "compression_raw": "snappy",
  "compression_compact": "zstd",
  "published": []
}
```

**Four fields**, and `published: list[LedgerName]`. Decision 5 requires two compressions and one field cannot hold them; `published` names the ledgers a browser may address. **`published` ships empty.** No console panel reads a compact file until plan 51 moves one, so an entry here would publish files no page opens. Plan 51's row titled **The three ledgers the console reads are published** adds all three: `item-health`, `scores` and `host-fingerprint`.

The browser never reads this list; one backend test asserts that every ledger a console panel names is in it.

**A published ledger's daily compaction runs at every wake like every other task in the matrix, at the gardener's own wake. No workflow step outside `idhazh-gardener.yml` triggers a compaction** (row 7 decision 9). **The newest daily file covers today minus two**, which is what the eligibility rule allows and what a reader's open period is measured against - an earlier draft claimed per-run compaction could make it one run old, which the eligibility rule forbids at any trigger rate.

**No raw file is ever published, and that is what the daily compaction buys.** Section 4 measures a published ledger's raw period at 15.1 times the CSV it replaces, so a reader fetching an open day verbatim would pay about 342 KB and thirty requests to draw one day. What the daily compaction costs is git churn, measured in section 4 - not the 360 MB an earlier draft asserted.

`format` defaults to `parquet`, `compression_raw` to `snappy`, `compression_compact` to `zstd`, `published` to an empty list. The matching non-default entry goes in `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json` in the same commit, and `backend/idhazh/contracts/app_config.py` gains the `ledger` block - without that line nothing can reach the knob.

#### 5.9.5 `GardenerConfig`, `TaskPolicy`, and every declaration

**`config/gardener/` first appears in row 5, with the first declarations, and every later row adds its own declarations and its own task modules in the same commit.** Git does not track an empty directory, and nothing but a declaration may sit in this one (section 5.2), so row 4 ships no directory; until row 5, the loader and the `plan` job read a missing `config/gardener/` as no tasks. The shard pre-flight in section 5.5 is what makes that structural rather than hoped for: a declaration with no discovered task is exit 2 naming the task, so row 4 **cannot** ship declarations against the empty tasks package it creates, and `paused` is no escape - a paused declaration with no module is a fault too. **No value in any declaration is invented: every window is transcribed from a named `config/idhazh.json` key and the file carries that key's name**, so row 5's move is a transcription a reviewer can check against the source line. Two of those windows delete data, which is why a guessed value is not an acceptable outcome and why the refusal exists.

**`TaskPolicy` is a discriminated union on a required `kind`.** Four members: `retention`, `collection`, `compaction`, `history`. The compaction task writes its ledger's raw day indexes, so there is no `index` member (section 5.3). A key on the wrong member is refused by name at load.

| Where | Keys |
| --- | --- |
| **On the base, every member** | `lifecycle_status` (`TaskLifecycleStatus`, required, no default), `kind`, `window`, `dry_run`, `max_deletes_per_run`, and **exactly one** of `owns` / `owns_everything_else_under` - both or neither is refused |
| `HistoryPolicy` only | `every_days: int, ge=1`, transcribed from `finetune.prune_every_days: 30`. **The one schedule in this file**, because `corpus-squash` is the one task outside the matrix; every matrix task runs at every wake (section 5.3). A key on the wrong member is refused by name at load, which is what a cadence on the base could never be |
| `CompactionPolicy` only | `ledger: LedgerName` (required, typed rather than parsed from the stem - a refusal composes `compact-<ledger>` from the field and compares it to the filename), `raw_index_keep_days`, `daily_keep_days`, `monthly_window`, `max_periods_per_run`, `max_raw_files_per_period`, `compact_after_hours`. **There is no `period`**: one task runs both grains |
| `RetentionPolicy` only | `series: dict[Slug, SeriesWindow]`, non-empty for `telemetry-aggregate` and absent everywhere else. `SeriesWindow` is `{unit, value}`, the same union as `window` |

| Knob | Type | Whose | What it acts on |
| --- | --- | --- | --- |
| `compact_after_hours` | `int`, `ge=1`, default `24` | compaction: index step and daily period | How long after a day ends before that day may be read, measured against the day's own end instant in UTC. **The default is the rule: a whole day must have ended**, which at the `40 0 * * *` wake makes the newest eligible day two days back. The knob is a plain duration - 30 gives thirty hours - and section 5.3 proves no wake time in the day changes the answer |
| `raw_index_keep_days` | `int`, `ge=1`, default `90` | compaction: index step | How long `state/raw/<ledger>/index/<YYYY-MM-DD>.json` survives. **Without it the raw index tree grows by 365 files a ledger a year forever**: it is written by the compaction's index step, read by the daily compaction once, and after that day is in the daily period nothing reads it again. It outlives the daily period deliberately, so a compaction that was reverted still has its input - and **the index step stops rewriting a day once that day is compacted** (section 5.9.13), so what the window holds is that day's real listing rather than an emptied directory's `files: []` |
| `daily_keep_days` | `int`, `ge=1`, default `45` | compaction: monthly period | **How old every day of a month must be before that month is absorbed.** It is not a per-file age test. A daily file is never deleted before its month's file exists, so the daily period holds between `daily_keep_days` and `daily_keep_days + 31` days |
| `monthly_window` | `{unit: months, value: int ge=1}` or `{unit: forever}`, discriminated on `unit`. Default `{unit: months, value: 13}` | compaction: monthly period | How long a month file survives. With `daily_keep_days` this is the ledger's real retention floor once it goes through the door: about 14 months at the defaults. **The same union as a task's `window`, and for the same reason** - two knobs answering "how long do I keep this" answer it in one spelling. **The name carries no unit because the value may be `forever`**, and a field named `_months` holding `forever` says the wrong thing (CLAUDE.md section 0b). A ledger that no task ever limited has no floor, so its own declaration's windows bound it; one whose old tree a task limited must reach back at least as far as that task's `window` (section 5.2) |
| `max_periods_per_run` | `int`, `ge=1`, default `8` | compaction | How many eligible periods one wake may consume. **This is what keeps a first run's cost off the size of the archive** (Guardrail #12) and what makes "starts at the watermark plus one" and "one period at a time" the same program |
| `max_raw_files_per_period` | `int`, `ge=1`, default `2000` | compaction | **How many raw files one period may absorb in one wake.** `max_periods_per_run` bounds how many periods a wake takes; nothing bounded how much is inside one. `RawDayIndex.files` is an unbounded list and the compaction reads exactly the files it names, so a single day that a re-run or a wide fan-out filled is unbounded work inside a bounded period count - the Guardrail #12 hole that a period ceiling looks like it closed and does not. **A day whose index names more than this is refused by name at run time, not at config load**, because the count is data rather than configuration: the task logs the day, the count and the ceiling, writes its record, exits 1, and leaves the watermark where it is so the next wake retries the same day rather than skipping past it. A refusal that skipped would lose the day silently, which is the failure this ceiling exists to make loud |

**`yearly_keep_years` is not declared**, because no yearly period ships (section 2).

**The telemetry aggregation reads three `observability` keys, not one window and not eleven.** Verified 2026-09-24: `item_health_full_grain_months`, `item_health_aggregate_keep_months` and `public_telemetry_keep_months`. The three become three named series entries under one task, `telemetry-aggregate.series.<name>.window`, so the task keeps one policy and the three keep their own numbers. The cross-file refusal in 5.2 is stated per series, not once.

#### 5.9.6 `Shard` - `backend/idhazh/gardener/publish.py`

```python
class Shard(Model):
    """One matrix leg as the runner finished it: what it ran and what it changed."""
    index: int                      # ge=0
    task_names: tuple[str, ...]     # what this leg ran, in order
    record_path: RelPath            # the one file this leg writes
    written_paths: frozenset[RelPath]
    deleted_paths: frozenset[RelPath]
```

**`cone` is not a field of `Shard`.** It belongs to the plan payload's `ShardPlan` (section 5.9.7): the `plan` job computes it and `actions/checkout` consumes it, and the runner never reads it or works it out again. One model across a boundary where one side cannot import it is two producers of one value, and they disagree the first time the cone rule changes.

**`owned_paths` is not a field of either.** Ownership is a permission checked against config; it is not the staging list, and one field answering both questions is how committed data gets deleted.

**`record_path` is exactly one file, and the commit loop's whole integrity check rests on that.** `persist()` returns `list[Path]`, because it routes every row under the day that row's own `covers` names, so one call can write several files (row 2). A shard's record cannot: every row in it is this job's own work on this wake, so every row carries the same `date` and the call returns one path. **The runner asserts that and exits 2 if it is ever handed more**, because the `remote_blob` lookup, its comparison against `local_blob` and the already-landed branch each name one path - a second record file would land unchecked and the already-landed test would pass on the first of two.

**`record_path` is always a member of `written_paths`.** It is named on its own because the commit loop's already-landed branch tests that one path, not because it is staged separately: the staged set is `written_paths` and `deleted_paths` together, and the record is in it. **The runner asserts the record sits under `state/raw/gardener/` and exits 2 if it does not** - it is the one write no task owns, and this one-line check is what keeps it out of the per-task ownership rule (section 5.5).

#### 5.9.7 The plan payload - `backend/idhazh/contracts/gardener_plan.py`

A standard-library script writes it and a YAML matrix expression reads it, so it is a **cross-process contract** and it is declared like one. `gardener_shards.py` cannot import the model (it runs before `pip install`), so this is the hand-copy case, and `backend/tests/contracts/test_gardener_plan_matrix.py` asserts the committed workflow's matrix expression reads only keys the model declares.

```json
{
  "any_active_task": true,
  "shard_count": 5,
  "shards": [
    { "index": 0, "task_names": ["seen", "traces"], "cone": "state/seen\nstate/traces" }
  ],
  "matrix": { "include": [ { "shard": 0, "cone": "state/seen\nstate/traces" } ] }
}
```

Each entry of `shards` is a `ShardPlan`, declared in the same module:

```python
class ShardPlan(Model):
    """One matrix leg as the `plan` job describes it, before anything runs."""
    index: int                      # ge=0
    task_names: tuple[str, ...]     # what this leg must run, in order
    cone: tuple[RelPath, ...]       # the sparse-checkout prefixes, from section 5.6
```

**Three fields the workflow reads and each is read differently.** `any_active_task` gates the `run-tasks` job and is named for what it checks: the config holds at least one task in `lifecycle_status: active`. **It is not called `due`.** Every task in the matrix runs at every wake (section 5.3), so there is no per-task dueness left for this payload to carry, and a field named for a question nothing asks sends the next reader looking for the answer - the same move that took `find-due` to `plan-shards` (CLAUDE.md section 0b). `shard_count` is a **number**, because `max-parallel` given a JSON array is invalid and GitHub fails the workflow at parse. `matrix` carries `include`, because `cone` must be a matrix member rather than a sibling field - an expression naming a missing context property evaluates to the empty string with no error, so a missed `cone` checks out nothing and every deletion silently finds nothing.

**`history_due` is not a field.** The `history` job reads `corpus/corpus.meta.json` out of its own checkout (section 5.3). Owner ruling, 2026-09-26, overturning the 2026-09-24 design: a flag the `plan` job could not compute is a flag that force-pushes `main` every day.

**`cone` crosses the boundary as one newline-joined string and is a tuple on both sides of it.** `ShardPlan.cone` is `tuple[RelPath, ...]`; the payload's `cone` is `"\n".join(shard_plan.cone)`, because `sparse-checkout` takes a block scalar. The join and the split each live in one named function and the field-set test asserts a round trip.

**A task using `owns_everything_else_under` emits an empty `cone`.** Cone-mode sparse checkout matches directories and has no depth-one form, so a cone of `state` would materialise every file under `state/` - 909 files and 59,319,788 bytes, every day, to read the eighteen entries at depth one. The `trials` task asks `git ls-tree HEAD state/` with no `-r`, which reads tree objects a `blob:none` clone already holds and needs no working tree at all; **the listing yields blobs as well as trees and the task ignores a blob by name.** An empty cone emits the three code prefixes alone - `config`, `backend`, `.github`. **A cone of a bare ledger root is Guardrail #12 broken rather than answered**, and one harness test asserts no shard's cone contains one.

`"any_active_task": false` ships `"shards": []`, `"shard_count": 0` and `"matrix": {"include": []}` - the empty case is a shape, not an absence, because a matrix expression reading a missing key fails differently on every runner.

#### 5.9.8 The exit codes, ordered

A shard runs several tasks and exits with the **worst** code, and worst is not numeric maximum: **2 > 3 > 1 > 0**. Unretryable outranks retryable, because a job that reports 3 gets re-run and a job that reports 2 must not be.

#### 5.9.9 `run_id` is a dated address, and every example in this plan uses one

`contracts/base.py` declares `RUN_ID_PATTERN` as `^\d{4}-\d{2}-\d{2}-[0-9]+$`. A bare workflow number fails it. Every worked example in sections 2 and 5.7 reads `2026-09-24-17482910337`, and `unit_id` takes `run_id: RunId` rather than `str`, so a bad shape is refused before a name is minted from it.

#### 5.9.10 Nothing states a task count

**The count is `ls config/gardener/` and nothing else writes it down.** `idhazh gardener list-tasks` prints every task, its lifecycle status, its window and what it owns; `idhazh gardener plan-shards --json` prints the shards and the fullest one. A count in prose has nothing reading it, so nothing goes red when it drifts - and this one was wrong three different ways before it was deleted.

**One derived number survives, and it is derived where it is used**: row 8's `timeout-minutes` is stated against the fullest shard that `plan-shards --json` reports, read from the named observation at the first scheduled run.

#### 5.9.11 The workflow's own values, so row 8 transcribes rather than chooses

| Key | Value | Reason |
| --- | --- | --- |
| `name` | `Idhazh Gardener` | The rename is the row's point; a display name left behind still reads `Corpus prune` in the Actions list |
| `on.schedule.cron` | `40 0 * * *` | **After the UTC day boundary, not before it**, so eligibility is decided by section 5.3's arithmetic and never by where the wake falls. 40 minutes past the hour misses GitHub's top-of-hour scheduling surge. The worst case - a 1-minute `plan` job, a `run-tasks` wave inside its 20-minute timeout, the history job's own 0.5-minute dueness read and a 30-minute history job - finishes inside the 22:34 to 03:00 gap between the 22:00 council and the 02:20 digest |
| `on.workflow_dispatch` | keep the `force` boolean, redefined as "run every task, due or not" | The only way to take rows 6 and 8's named observations without waiting a day |
| `timeout-minutes` | `plan: 5`, `run-tasks: 20`, `history: 30` | 30 is what `prune.yml` uses for the same history work, and it now also covers the dueness read that exits early. 5 for a job that reads one committed file. **20 is derived and here is the derivation**: sparse checkout 30 s, `setup-python` 20 s, a cold `pip install -e .[parquet]` on `ubuntu-latest`, which is not measured beforehand (owner ruling 2026-09-27, section 4), **the fullest shard's tasks at 45 s each**, as `idhazh gardener plan-shards --json` reports them (section 5.9.10), which is the one term that is an estimate, and a push loop bounded near 30 s by `attempts: 5` and the declared backoff. **At every candidate install figure, and up to seven tasks in a shard, the sum lands between about 6 and 13 minutes against a 20-minute timeout, so `timeout-minutes: 20` does not move.** Row 8's named observation replaces the task term with the first scheduled run's readings |
| `concurrency` | `group: idhazh-gardener`, `cancel-in-progress: false`, at workflow level | The history job force-pushes, and two copies push two histories. **Not keyed on `github.ref`**, or a dispatch and a schedule run together |
| `permissions` | `contents: write` **and `actions: write`** | The second is missing from every workflow here today, and `github_collections.py` refuses by name without it - so the two collection tasks 403 on their first live run |
| `env` on the run-tasks step | `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` | `github_collections.py` reads it from the environment and raises when unset. **`dry_run: true` still lists**, so row 8's observation is unreachable without it |
| `persist-credentials` | left at the default `true` | It is the only thing that writes the credential header the later push uses |
| `runs-on` | `ubuntu-latest`, all three jobs | Guardrail #2 |
| python | `actions/setup-python@v7`, `3.12`, on `run-tasks` and `history` only | The `plan` job installs nothing and uses the runner's `python3`, as `prune.yml`'s due step does. **The history job's own dueness step runs on the runner's `python3` too**, before its `setup-python` and before its full clone |
| `history` checkout | **not sparse, on purpose** | Section 5.6 says why: its second checkout takes the whole tree anyway |
| the install step | `pip install -e .[parquet]` on every `run-tasks` shard | **Every shard writes its own record through the ledger door** (section 5.6: "add its record, always"), so every shard needs the engine. An earlier draft made the extra a matrix field for the four tasks that read parquet, which was wrong - the record is parquet too |
| pip cache | `cache: pip`, `cache-dependency-path: pyproject.toml`, **`cache-suffix: parquet`** | `setup-python` keys on the OS, the interpreter and the dependency file - **never on the extras** - so without a suffix this workflow and `digest.yml` share one entry whose contents depend on which ran first. A cache key that does not name the resolved set it holds reports a hit and delivers a miss |
| `max-parallel` | `${{ fromJSON(needs.plan.outputs.shard_count) }}` | A **number**, not the shard array: `max-parallel` given a JSON array is invalid and GitHub fails the workflow at parse. **The workflow test asserting `max-parallel` is not below the shard count is deleted**: it cannot fail |
| the matrix | `include: ${{ fromJSON(needs.plan.outputs.matrix).include }}` | `cone` must be a matrix member, not a sibling field. An expression naming a missing context property evaluates to the **empty string with no error**, so a missed `cone` checks out nothing and every deletion silently finds nothing |
| no active task | `run-tasks`: `if: needs.plan.outputs.any_active_task == 'true'`. `history`: `needs: [plan, run-tasks]`, `if: always() && (needs.run-tasks.result == 'success' \|\| needs.run-tasks.result == 'skipped')` | **A skipped `needs` skips the dependant**, so the force-push job would never run on a day when every task is paused. **The `history_due` clause is gone**: the squash fires about twelve times a year and the windowed tasks fire daily, and the job that can see `corpus/corpus.meta.json` is the one that decides. It starts every day and exits in an estimated 20-30 s on the 29 wakes out of 30 that do nothing. Owner ruling, 2026-09-26, overturning the 2026-09-24 decision that put the flag in the plan payload |
| commit message | run-tasks: `gardener: <task names> on <date>`. history: `corpus: squash history older than <keep_days> days`, **byte-identical to today's** | The history line is the one string a person greps the rewritten history for |

**The plan payload is emitted on one line** - `json.dumps(payload, separators=(",", ":"))` - because a value carrying a literal newline needs the heredoc form in `$GITHUB_OUTPUT` and the obvious pretty-printed version breaks it silently.

#### 5.9.12 The helpers `publish()` calls

`git`, `git_ok`, `remote_blob`, `local_blob`, `staged_names`, `sleep_with_jitter` and the **four** `EXIT_*` constants - `EXIT_OK`, `EXIT_TASK_FAILED`, `EXIT_INTEGRITY`, `EXIT_PUSH_KEPT_LOSING` - all live in `backend/idhazh/gardener/publish.py`. All four in one place, because the worst-code rule in 5.9.8 needs all four to compare them. Four helpers carry git semantics a worker would get wrong:

| Helper | Body | Why it is not the obvious one |
| --- | --- | --- |
| `staged_names()` | `set(git("diff", "--cached", "--name-only", "-z").split("\0")) - {""}` | **`-z` is load-bearing.** Without it git C-quotes a path holding a non-ASCII byte and the set comparison fails on a path the repository may legally hold |
| `exists_on_remote(p)` | **deleted** | It asked a question `remote_blob` already answers, with a command that defeats `filter: blob:none`. Two helpers, two rows in this table, and both reasons cells left empty - which is how it survived three reviews |
| `remote_blob(p)` | `git_out("rev-parse", "--verify", "--quiet", f"origin/main:{p}")`, returning the object id or `None` | **One call answers both questions the loop asks**, and it is the one that does not undo the checkout. **There is no `exists_on_remote`.** An earlier draft answered "is it there" with `cat-file -e`, which **materialises the blob** - and under `filter: blob:none` that is a lazy fetch from the promisor remote, on every attempt, for the one file the loop is about to overwrite anyway. `rev-parse` resolves the path through tree objects a `blob:none` clone already holds and never touches content. The partial checkout in section 5.6 exists to avoid exactly that fetch |
| `local_blob(p)` | `git("hash-object", "--", str(p))` | It hashes the **working file**, not an index entry: the file is on disk and not yet staged when the check runs |
| `sleep_with_jitter(k)` | sleep `random.uniform(0, min(2 ** (k - 1), 8))` seconds | **Full jitter, not exponential-plus-noise.** Five shards that lose one race retry in lockstep under a fixed backoff and lose the next one together; drawing from zero spreads them. The cap of 8 seconds bounds the loop near 30 seconds at `attempts: 5` |

**The staged-set assertion is three checks, not one equality.** Every write must be staged; nothing outside the union may be staged; and a deletion that staged nothing is an error **only if it still exists on the remote**. A flat equality turns a benign race - `digest.yml` rebuilding a path the `visual-prune` task was about to delete - into exit 2, the one code that must never be retried. It is named for git's staging area and has nothing to do with the file indexes in section 5.9.13.

#### 5.9.13 The three small files, and what is in each

All three are read by a later run, so all three are contracts with a `__schema_stem__` and a `__changelog__` (section 5.9.1). All three are written whole, never appended to, through the same temp-file-plus-rename as a data file.

**`version` is inherited from `Contract` and is never re-declared.** It is `SchemaVersion`, not `DateStamp`: the base permits a same-day revision stamp and a narrower alias would silently take that away.

One alias joins `backend/idhazh/contracts/base.py`, because a filename reaches a fetch URL and Guardrail #11 names the schema as the control:

```python
#: `<file_id>.parquet` or `<file_id>.json`. A name this project minted, never a name it was given.
FILE_ID_NAME_PATTERN: Final = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(parquet|json)$"
)
FileIdName = Annotated[str, StringConstraints(pattern=FILE_ID_NAME_PATTERN)]

#: What one compact file covers: `2026-09-23` or `2026-08`.
PeriodStamp = DateStamp | MonthStamp
```

**The suffix group holds both formats, because the door writes both.** `Format` carries `JSON`, `persist()` takes `fmt`, and row 2 decision 7 keeps JSON first-class - "a payload a person reads in a pull request should not be binary". A pattern ending `\.parquet$` would leave a JSON-format ledger with raw days that cannot be indexed at all, failing at validation rather than at the door. Widening it costs the control nothing: the alias still refuses a `.csv` name, still refuses a name this project did not mint, and still refuses anything a fetched page could have supplied.

**`PeriodStamp` is a union of two aliases that already exist**, not a third pattern: `base.py` declares `MONTH_PATTERN` and `MonthStamp` today. `DateStamp` alone cannot hold `2026-08`, so it is not the type for anything a monthly period writes.

```python
class RawDayIndex(Contract):
    """Which raw files exist for one day of one ledger.

    Rewritten at every wake until that day is compacted, and never again after.
    """
    ledger: LedgerName
    date: DateStamp             # the UTC day these files hold, not the day this was written
    files: list[FileIdName]     # ascending, unique; empty is legal and means the day made nothing
    content_sha256: Sha256      # over "\n".join(files)
    listed_at: Timestamp        # when the compaction task last listed this day

class CompactEntry(Model):      # one row inside CompactIndex, never a file
    covers: PeriodStamp         # the day or the month this one file holds
    rows: int                   # ge=0, after settling: one row per record key
    bytes: int                  # ge=0, so a reader checks Content-Length before it parses anything

class CompactIndex(Contract):
    """Which compact files exist in one period of one ledger.

    Sufficient on its own: a date is in monthly, or in daily, or it is not
    available. The newest daily entry is the newest day compacted, which is
    how a browser tells a day not yet compacted from a hole.
    """
    ledger: LedgerName
    period: Period
    entries: list[CompactEntry]

class Watermark(Contract):
    """How far one period of one ledger has been compacted.

    A producer file. It says where the next run resumes and nothing else.
    """
    ledger: LedgerName
    period: Period
    through: PeriodStamp        # the newest period fully absorbed
    advanced_at: Timestamp
    run_id: RunId               # which run left it here, after the record naming it is pruned
```

**Three validators, one per shape, each raising with the ledger and the period or date in the message.** `RawDayIndex`: `files` ascends and holds no duplicate. `CompactIndex`: `entries` ascends by `covers`, no `covers` appears twice, and every one matches the granularity `period` declares. `Watermark`: `through` matches the granularity `period` declares - `PeriodStamp` is a union of two aliases, so without that line a daily watermark legally holds `2026-08`, and this is the file that decides where a compaction resumes.

**`file_count` is not a field, and `extra="forbid"` is what makes the removal stick.** `len(files)` is free to anything that has already parsed the JSON, so a count beside the list is two answers to one question - the same reason `row_count` is not in the envelope (Guardrail #4). `Model` sets `extra="forbid"`, so a writer that still emits `file_count` fails at validation rather than being quietly tolerated: the deletion is enforced, not merely documented, and it cannot half-land.

**`content_sha256` is `Sha256`, not `str`.** `base.py` already declares that alias at `^[0-9a-f]{64}$`. A bare `str` accepts an empty string or a URL, and this value travels into a record row.

**`CompactEntry` carries no hash, and `bytes` is why.** `bytes` lets a reader check `Content-Length` before it parses anything, which is the cheap integrity check the index is for; the file's own envelope carries the hash for the case that needs certainty. A second hash in the index would be a second thing to keep in step with the file it describes.

**`Watermark.run_id` answers the question `advanced_at` cannot.** When an operator asks why a watermark stopped on the 12th, `advanced_at` says when and the job log says why - but the record row holding `run_id` is itself pruned on a window, and the watermark is not.

##### The payloads themselves, so a worker matches bytes rather than a description

**Every hash below is real and a worker may assert against it.** Each is `sha256` over `"\n".join(files)` of the list in that same payload, UTF-8, no trailing newline. `version` is the shape's own stamp and sits next to `date`, which is the data's day; they are different questions and the pairing invites a misread, which is why each carries its own description in the model.

`state/raw/item-health/index/2026-09-24.json` - a populated day:

```json
{
  "version": "2026-09-26",
  "ledger": "item-health",
  "date": "2026-09-24",
  "files": [
    "01a0d140-9ba7-8ea9-bdd5-7b9344b4ce8c.parquet",
    "01a0d140-9ca8-8733-ad3a-ed18a16e34e6.parquet",
    "01a0d140-9de4-83e8-8c70-7a05105620c9.parquet",
    "01a0d14c-afba-80a3-8ee1-e2b9b8c6d823.parquet",
    "01a0d14c-b02e-81ab-953d-a30e9d7b505e.parquet",
    "01a0d2ab-d8c0-829b-ac38-cea80ffde2ed.parquet"
  ],
  "content_sha256": "9b5c285871509ca89bca27690aabddc4ea455d549ecbb387e48ba1dc9b33cede",
  "listed_at": "2026-09-25T00:40:12Z"
}
```

An eligible day that produced nothing. The hash is `sha256("")`, because joining an empty list gives the empty string:

```json
{
  "version": "2026-09-26",
  "ledger": "item-health",
  "date": "2026-09-21",
  "files": [],
  "content_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "listed_at": "2026-09-25T00:40:12Z"
}
```

The same shape for a ledger whose `ledger.format` is `json` - this is what the widened suffix group unblocks:

```json
{
  "version": "2026-09-26",
  "ledger": "<a json-format ledger>",
  "date": "2026-09-24",
  "files": [
    "01a0d14c-afba-80a3-8ee1-e2b9b8c6d823.json",
    "01a0d14c-b02e-81ab-953d-a30e9d7b505e.json"
  ],
  "content_sha256": "4646d2b78b213d57e160cb585fd45c3f794fd17bda7edf36163a48c6fc2c7fd5",
  "listed_at": "2026-09-25T00:40:12Z"
}
```

`state/compact/item-health/index/daily.json`:

```json
{
  "version": "2026-09-26",
  "ledger": "item-health",
  "period": "daily",
  "entries": [
    { "covers": "2026-09-22", "rows": 214, "bytes": 86104 },
    { "covers": "2026-09-23", "rows": 220, "bytes": 87714 }
  ]
}
```

`state/compact/item-health/index/monthly.json`:

```json
{
  "version": "2026-09-26",
  "ledger": "item-health",
  "period": "monthly",
  "entries": [
    { "covers": "2026-07", "rows": 6412, "bytes": 1174208 },
    { "covers": "2026-08", "rows": 6789, "bytes": 1231872 }
  ]
}
```

**87,714 is section 4's measured figure for 220 item-health rows at 122 columns. The monthly sizes are illustrative and a worker must not assert on them.**

`state/compact/item-health/daily/watermark.json` and `state/compact/item-health/monthly/watermark.json`:

```json
{
  "version": "2026-09-26",
  "ledger": "item-health",
  "period": "daily",
  "through": "2026-09-23",
  "advanced_at": "2026-09-25T00:41:03Z",
  "run_id": "2026-09-25-17491882043"
}
```

```json
{
  "version": "2026-09-26",
  "ledger": "item-health",
  "period": "monthly",
  "through": "2026-08",
  "advanced_at": "2026-09-25T00:41:07Z",
  "run_id": "2026-09-25-17491882043"
}
```

##### What each shape must accept and what it must refuse

Row 11's `backend/tests/contracts/test_ledger_index.py` drives every cell, each case built in the test rather than read at module scope (CLAUDE.md section 13).

| Shape | Accepts | Refuses |
| --- | --- | --- |
| `RawDayIndex` | a populated day, an empty day, a `.json`-format day | out-of-order `files`, a duplicate file, a `.csv` name, a fractional-second `listed_at`, and a leftover `file_count` |
| `CompactIndex` | an ordered daily index, an ordered monthly index | a daily index holding `2026-08`, unordered `entries`, a repeated `covers` |
| `Watermark` | daily with a date, monthly with a month | a daily watermark holding `2026-08`, a bare run number in `run_id` |

**Two of those refusals come free and neither is obvious.** `listed_at` is `Timestamp`, whose pattern is whole seconds ending `Z`, so a fractional-second stamp is refused without a line being written for it. And `file_count` is refused by `extra="forbid"` on the `Model` base, which is what turns deleting a field into something a writer cannot quietly undo.

**The compaction task's index step** runs at every wake, before the daily period, and writes an index for every raw day directory of its ledger that is eligible under `compact_after_hours`, **skipping any day at or below `daily/watermark.json.through` whose raw directory is empty or absent**. It lists the directory, computes `content_sha256` over the sorted filename list, and writes the index whole.

**Without that skip, `raw_index_keep_days` buys nothing.** The daily compaction deletes a day's raw files. An index step that re-lists the emptied directory rewrites the index to `files: []`, so the ninety days the window holds are ninety days of empty lists and the revert case it was bought for is gone one day after compaction.

**The skip is conditioned on the directory being empty, and that clause is load-bearing.** A bare "at or below the watermark" test would also skip the one day that must not be skipped: a re-run of a failed job writes into its original day, which is below the watermark, and row 7 decision 4 absorbs that rather than guarding against it. Conditioning on emptiness keeps both - a compacted day is never re-listed, and a day that has raw files again is indexed again so the compaction can take it. The emptiness is free: the task lists the directory anyway. It is also why the field is `listed_at` rather than `sealed_at` - "sealed" claims a finality a re-run can legitimately break, where `listed_at` says what it means, the moment the task last agreed with the tree.

**The daily compaction** reads the index for the day it is about to take. It re-lists that one directory first and, on a mismatch, rewrites the index before compacting - one listing, for one day, at the moment it matters. It never skips.

**A day already below the watermark that has raw files again** was written into by a re-run of a failed job, which GitHub permits for thirty days. The compaction rewrites that day's compact file from the union, deletes the raw files and leaves the watermark alone. A period-file rewrite costs 1,649 bytes packed, which is what makes absorbing a late arrival cheaper than guarding against one.

**An empty eligible day writes an index with `files: []`.** The day was looked at and produced nothing. Writing nothing instead would have the browser ask for a file that is not there.

**What a reader does with a stamp it does not know.** On the Python side `Contract.read()` already refuses a stale payload by name. In the browser the rule is: the query door compares an index's `version` against the one the bundle was built with, and on any mismatch it renders the `unreachable` state with both stamps in the console and fetches nothing. A build and the tree it reads ship from one checkout in one artefact, so a mismatch is a deployment fault rather than a data fault, and reading past it would draw a chart from a shape nobody checked.

**The read-side migration when an index changes shape.** These files are derived and rebuildable: the compaction that owns a period rewrites its whole index on its next wake. So a breaking change to `CompactIndex` or `Watermark` ships a one-line reset of that period's watermark to its first period, which makes the next run rewrite every file and every index in it. `RawDayIndex` cannot take that route, because a compacted day's raw files are not rewritten, so it ships a read-side branch on `version` in `ledger/settle.py`, kept for one release.

---

### Row #1 - The site-size instruments leave the prune module

- **Scope:** `backend/idhazh/retention.py` is 1,880 lines answering two questions; the half that measures the published site and deletes nothing moves to its own module, unchanged.
- **Files touched:**
  - `backend/idhazh/retention.py` (the site-size half leaves)
  - `backend/idhazh/site_weight.py` (new: `SiteSize`, `measure`, `count_published_items`, `heaviest_directories`, `over_budget`, `over_cap`, `headroom_mb`, `daily_growth_bytes`, `days_to_alarm`, `days_to_cap`, `budget_alarm`, `cap_breach`, `PAGES_HARD_CAP_MB`)
  - `backend/idhazh/cli.py` (the `site-weight` verb)
  - every caller the move breaks, found by `git grep -n 'retention\.\(SiteSize\|measure\|count_published_items\|heaviest_directories\|over_budget\|over_cap\|headroom_mb\|daily_growth_bytes\|days_to_alarm\|days_to_cap\|budget_alarm\|cap_breach\|PAGES_HARD_CAP_MB\)'`
  - `backend/tests/` (the covering module moves with them), `backend/tests/test_marks.py`
  - `docs/architecture/publishing/console-site-size.md`, `docs/architecture/publishing/retention.md`
- **Acceptance gates:** local `ruff check .` from the repository root, `mypy backend`, `pytest backend/tests -k "site_weight or site_size or retention"`. CI runs the full suite.
- **Oracle:** the moved function bodies are byte-identical - every line of the site half appears in the new file unchanged and `retention.py` loses exactly those lines. It cannot settle whether the seam is right; only that nothing changed while it moved.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Ships first and alone, because row 5 deletes from `retention.py` and a pure move underneath a semantic change is a merge nobody can review | Fowler |
  | 2 | Named for what it produces, matching the `idhazh site-weight` verb that prints it | CLAUDE.md section 1a |
  | 3 | No behaviour changes. Not a rename, not a signature, not a default | execute-a-plan.md |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave `retention.py` whole | It keeps answering two questions, and every gardener row then edits the same 1,880-line file as every site-size row | Zero now; the cost lands as a conflict on every later row | CLAUDE.md section 1a |
  | 2 | Move the site half under `backend/idhazh/gardener/` | The gardener deletes; this half measures. It would make the package's first sentence false | Zero; costs the package a second question | Fowler |

---

### Row #2 - The payload ledger, the two roots, and the arrow mapping

- **Scope:** one call persists any contract payload as parquet or JSON; exactly one module imports the parquet engine; `state/raw/` and `state/compact/` exist and are registered; **writes honour a family's `lifecycle_status`** (below). **No committed byte moves in this row**, which is what makes it revert to nothing.

**`state/raw/` and `state/compact/` are bounded by the compaction, not by a retention task.** Row 7 gives three ledgers one compaction task each (section 5.3): `gardener`, which row 4 creates, and `visual-prunes` and `feed-retirements`, which row 3 moves. The daily compaction deletes a day's raw files, `raw_index_keep_days` bounds the raw index tree, and `daily_keep_days` with `monthly_window` bounds the two compact periods. **A second task windowing a tree a compaction already owns is forbidden** - row 7 decision 7 - because it would have to own a root that task already owns. What this row registers the two roots against is narrower: the `trials` task sweeps any directory under `state/` that no task claims, and without the registration it would read them as strays and delete the gardener's own records. "Registered" means "not a stray", never "not pruned".
- **Files touched:**
  - `backend/idhazh/ledger/` - **the four modules this row adds to the existing package**, and which no other row in either plan touches: `persist.py`, `parquet.py` (**the only module that imports pyarrow**), `json_lines.py`, `arrow_schema.py`. **Two more modules already exist and this row adds to them**: `paths.py` gains the five builders in section 5.4, and `filenames.py` gains `unit_id`, `file_id` and `_pack_v8` (section 5.7).<br>**`__init__.py` gains re-exports and nothing else, and none of them may pull in `parquet.py`.** Two tests in `backend/tests/contracts/test_ledger_package.py` hold both halves: the door defines nothing of its own, and a fresh interpreter that imports the door must not find `pyarrow` or `idhazh.ledger.parquet` in `sys.modules`. **So `persist.py` imports `parquet.py` inside the function that writes parquet, never at the top of the file.** This is not only a test to satisfy: pyarrow is an optional extra that only the jobs touching parquet install (decision 4), and eight of the 24 modules under `backend/idhazh/stages/` import the door (checked 2026-09-27), so a module-scope import would stop each of them loading in every job that did not install `.[parquet]`

**The one door every producer reuses, now and later:**

```python
def persist(
    rows: Sequence[Contract], *, ledger: LedgerName, covers: PeriodStamp,
    identity: WriterIdentity, tier: Tier = Tier.RAW, period: Period | None = None,
    built_from: int | None = None, fmt: Format | None = None,
) -> list[Path]:
    """Write these rows and return where they went, one path per period they cover."""


C = TypeVar("C", bound=Contract)


def load(paths: Sequence[Path], *, model: type[C]) -> list[C]:
    """Read these files back as rows of one contract, in the order the paths give."""
```

**`load()` is the inverse of `persist()` and nothing else.** It does not remove duplicates - a union over several attempts at one work unit is settled by `ledger/settle.py` (row 7). It reads the format from each file's own envelope, never from its suffix, and a file whose envelope's `schema_version` the model does not accept raises, naming the path, the stamp it found and the stamp it wanted.

**`persist()` returns its paths ascending by `covers`**, the day or month each file is filed under - never by path string, because a path string sorts a ledger name before a date and a caller wants the periods in order. **The write is `atomic_write.write_atomic_bytes(path, payload)` and nothing else**: a temp file in the destination's own directory, written whole, then moved onto the target. The door carries no second spelling of the one rule that decides whether a half-written parquet file can be seen.

**`period` is required when `tier` is `COMPACT` and refused when it is `RAW`**, because `compact_path` needs it and `raw_path` has no use for it. `covers` is a `PeriodStamp`, not a `DateStamp`: a monthly file covers `2026-08`.

**`persist` returns a list, and this is the correction that nearly did not get made.** `write_segment` does not write one file per call: `_dated_rows` routes every row under the day **its own `date` cell** names, so a call carrying three days of rows writes three files. Its docstring spells the reason once - "rows a run left behind three days ago land under that day rather than under today" - and that is CLAUDE.md section 2 applied, a day being the UTC day the row records and never the day the job woke. **A `persist` returning a single `Path` cannot replace `write_segment` without deleting that rule**, and the alternative is twenty producers each learning to group their own rows by date, which is one rule written twenty times. So `persist` keeps the routing, `covers` is the period a row is routed **to** rather than a promise about the batch, and the return type is `list[Path]`, ascending. Found by Fowler, 2026-09-26, against plan 53.

It mints `unit_id` and then `file_id` through `filenames` (section 5.7), builds the path through `paths.raw_path` or `paths.compact_path`, assembles the envelope, writes through a temp file and renames. **A producer never builds a path, never invents a filename and never assembles an envelope** - which is what makes the next producer's migration a change of call site rather than a change of design. **`identity.producer` is the one field a call site must get right**, because it is the field that keeps two producers of one dataset apart inside `unit_id`.

**Writes honour a family's `lifecycle_status`, and a write into a paused or retired family is skipped, never failed** (handover from plan 53, 2026-09-27). Plan 53 left what the status means at write time to this plan, and the owner ruled three things. This row builds it, at the door every producer moves to. A write into a paused or retired family is skipped with one warning, and the run carries on; it never fails the run. And the gardener keeps compacting and ageing a paused or retired family's old rows: a status says whether new rows are written, never how long old rows are kept, so freezing old rows means pausing the task that deletes them.

**One function decides, and every route that writes new rows asks it.** `backend/idhazh/ledger/lifecycle.py` (new) holds `accepts_new_rows(which: LedgerName, rows: int) -> bool`. It reads the status of the family holding `which` on every call, from the registry `paths.py` already loads. An active family returns `True`. A paused or retired one logs one warning naming the ledger, its family, the status and the rows not written, and returns `False`; the caller then writes nothing and returns what an empty write returns. It is its own module because the package's `__init__.py` defines nothing, and a test holds that. **The check sits at the write, never in the path builders**: `path`, `tree_root` and `relpath` also serve readers, and a paused family is still read.

**`persist()` skips a write only when all three hold**: the family is not active, `tier` is `RAW`, and `identity.job` is not in `MAINTENANCE_JOBS`, the frozenset `{MIGRATE, RUN_TASKS, HISTORY}` declared beside `ServerJob`. **A job name alone cannot say what a write is for.** `idhazh compact` runs in `digest.yml`'s `assemble` job, `measure.yml`'s `runtime` job and `validate.yml`'s `decide` job, and each of those jobs also writes new rows. A compact-tier write only files rows again that were already recorded, and skipping one after its raw days were deleted would lose those rows while the run reports success. So the compact tier is exempt by tier, and the gardener's own writes by job.

**Every route, from a grep of `main` on 2026-09-27.** Section 5.8's write chokepoints start this list; they are not all of it.

| Route | Asks the check | Why |
| --- | --- | --- |
| `persist()` | yes, under the rule above | the door every producer moves to |
| `ledger.write_segment`, `ledger.extend_segment` | yes | new rows from a pipeline job |
| each `ledger.append_*` helper except `append_visual_prunes` | yes | new rows |
| `stages/count_verdicts.py` (the score distribution and the judge archive), `stages/score_merge_line_holdout.py`, `council/metrics_sink.py`, `telemetry/publish/day_metrics.py`, `assemble.py` (digest fragments) | yes, before the write | each builds a registry path and writes it itself |
| `stages/work.py`'s `trace_sink` | yes, once when it builds the sink, never once per span | the trace exporter writes `state/traces` itself |
| `stages/compact.py`'s CSV fold, `ledger.write_item_health_summary`, `evals/archive.write`, and `append_visual_prunes` from `stages/prune_state.py` | no | maintenance: compaction, ageing, and the prune's own log. None of them asks. Once one reaches `persist()`, the compact tier or the gardener's job exempts it - except the prune's log between rows 3 and 5, the first cost below |
| `evals/writer._append_index` | no | an operator's repair of the score index. New index rows already go through `write_segment` |
| the one-off splits and migrations under `backend/utilities/` | no | a person runs each once, to move rows already recorded |

**`write_item_health_summary` must never be skipped, for a second reason.** The ageing step reads the summary back and raises on a mismatch before it deletes the raw days, so a silent skip there would fail the run - the one outcome the second ruling forbids.

**Three costs, named.** Between rows 3 and 5 the visual-prunes log goes through `persist()` under `ASSEMBLE`, so pausing `visual-prunes` in that window skips the log rows while the prune still runs; no stage reads those rows, and the prune deletes nothing today. CI builds its canary day through the same writers (`backend/utilities/build_canary_day.py`), so pausing a family also thins that fixture. And a paused `content-similarity-judge` re-judges the same nights at every council run until they leave the window, because `nights_outstanding` in `backend/idhazh/similarity/tenant.py` reads the record the skip stops writing.
  - `backend/idhazh/contracts/file_envelope.py` (new: `Tier`, `Period`, `Format`, `WriterIdentity`, `FileEnvelope`, per section 5.9.1. **`LedgerName` already exists** in `backend/idhazh/contracts/ledger_name.py`)
  - `backend/idhazh/contracts/__init__.py` (`FileEnvelope` joins `CONTRACTS` and `__all__`. **Nothing is generated** - `schemas/` and `idhazh.contracts.export` were deleted on 2026-09-23 and `backend/tests/contracts/test_no_generated_layer.py` refuses their return)
  - `backend/idhazh/contracts/base.py` (`FileIdName` and `PeriodStamp`, per section 5.9.13, and **`ServerJob` gains `MIGRATE`, `RUN_TASKS` and `HISTORY` here rather than in row 4**, because row 3's migration needs a job name and rows 3 and 4 must not share a file. `MAINTENANCE_JOBS`, the frozenset of those three that the status check exempts, sits beside it, because it is a fact about the vocabulary and not a knob), `frontend/src/lib/server/host-fingerprint.ts` (its copy `SERVER_JOB` takes the same three in the same commit; `test_frontend_vocabularies.py` asserts the two hold the same members in order)
  - `backend/idhazh/contracts/knobs/ledger.py` (`LedgerConfig`: `format`, `compression_raw`, `compression_compact`, `published` - **four fields**, per section 5.9.4), `backend/idhazh/contracts/app_config.py` (`AppConfig` gains the `ledger` block - without this line nothing can reach the knob), `config/idhazh.json` (the `ledger` block literal), `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `backend/idhazh/ledger/paths.py` (the two roots `state/raw` and `state/compact` are claimed **inside** `ledger.claimed_roots()`, not in a second list beside it. `_trial_roots` in `backend/idhazh/stages/prune_state.py` reads only that function, so that file does not change. Once they are claimed, the door test in `backend/tests/contracts/test_ledger_package.py` also refuses a typed `state/raw` or `state/compact` string outside the ledger package, which is what this plan wants; handover from plan 53, 2026-09-27. **`day-validations` needs no work**: it already has a `config/ledgers.json` entry, and plan 54 deletes the tree and that entry before row 5 runs), `backend/tests/retention/test_trial_state.py`
  - `backend/idhazh/day_shards.py` (one docstring line: this reader is CSV-only and parquet goes through `ledger/`)
  - `backend/idhazh/atomic_write.py` (new: `write_atomic` and `write_atomic_bytes` **move here unchanged from `backend/idhazh/assemble.py`**, every caller repointed, in their own structural commit. `assemble` imports the embedding, placement, ranking and tagging stages at module top, so `ledger/` importing it would charge all of that to every `run-tasks` shard on every wake)
  - `pyproject.toml` (`[project.optional-dependencies] parquet = ["pyarrow>=21"]`, and `dev` depends on it)
  - `.gitattributes` (the five lines in section 5.4)
  - `backend/tests/ledger/test_persist.py`, `test_arrow_schema.py`, `test_single_engine_import.py`, `test_trial_roots.py`; `tests/fixtures/parquet/`
  - `backend/idhazh/ledger/lifecycle.py` (new: `accepts_new_rows`), `backend/idhazh/ledger/rows.py` (`write_segment`, `extend_segment` and the `append_*` helpers ask it), and the direct writers in the route table above: `backend/idhazh/stages/count_verdicts.py`, `backend/idhazh/stages/score_merge_line_holdout.py`, `backend/idhazh/council/metrics_sink.py`, `backend/idhazh/telemetry/publish/day_metrics.py`, `backend/idhazh/assemble.py` and `backend/idhazh/stages/work.py`
  - `backend/idhazh/contracts/ledgers.py` (the `LedgerLifecycleStatus` docstring stops saying nothing reads the status), `docs/architecture/contracts/state-ledgers.md` (the paragraph that begins "The write path does not read the status yet" is rewritten to say it does, and how)
  - `backend/tests/ledger/test_lifecycle.py` (new), and `backend/tests/contracts/test_ledger_registry.py`, where `test_every_family_is_active_until_the_write_path_reads_the_status` is **deleted in the same commit that makes the status honoured**
  - `docs/architecture/contracts/persistence.md` (new: the door, the two formats, the swap procedure)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/ledger backend/tests/retention backend/tests/contracts backend/tests/test_plan.py -q`, and the tests `npm --prefix frontend run test:changed -- --list` names for the stage modules this row touches. CI runs the full suite.
  - **Named measurement before merge: dropped.** Owner ruling 2026-09-27: pyarrow is adopted whatever its install size or time, so the `ubuntu-latest` re-measurement is not taken and no row waits on it. The one reading stays the Windows figure, 96.9 MiB installed, and a sentence that quotes it says it is the Windows figure.
- **Oracle:** six checks. Round-trip parity - for every model this plan persists, `load(persist(rows))` returns rows equal to the input in both formats. The single-engine rule - **an AST walk** over every module under `backend/idhazh/` and `frontend/src/` finds exactly one `import pyarrow`, in `backend/idhazh/ledger/parquet.py`. An AST walk and not a grep: the test names the package and a grep would count its own file. The two-root refusal - `raw_path` and `compact_path` raise by name on any path whose second segment is neither `raw` nor `compact`. The trial-roots check - over a tree holding only `raw/` and `compact/`, the trial-roots computation returns empty. **The two-identifier check** - persist the same work unit twice with `attempt` 1 and 2, confirm two different filenames and one shared `unit_id`, then union the two files and confirm the reader returns attempt 2's rows only. **The lifecycle check**, the three tests the handover from plan 53 asks for: every checked route writes into an active family, and into a paused one writes nothing and logs exactly one warning naming the ledger, family, status and row count; the plan stage run on its fixture with `seen` paused still lands `feed-health` and `counterfactual-scores`; and `persist()` into a paused family lands its file under `RUN_TASKS`, under `MIGRATE`, and at the compact tier under `ASSEMBLE`. A test pauses a family by handing the check a real registry with that family paused, through the same `monkeypatch.setattr` the suite uses to redirect its roots - no mock. Row 7 repeats the compact case through the real compaction. It cannot settle whether the arrow type mapping is the best one, only that it round-trips.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Parquet is the persistence format the project moves to, `state/` first and published payloads after. This plan writes what it creates in parquet and lays the door the rest use | Owner, 2026-09-24. Not open to a later row |
  | 2 | The engine is pyarrow: the reference implementation, so everything else reads what it writes; its column API maps onto a contract model's fields; and it is the cheaper of the two that write native Python objects | Fowler and Carmack, on section 4 |
  | 3 | duckdb is the named swap candidate at 47.3 MiB and 11.6 s. Not the pick today because writing goes through SQL and it brings a query engine where a writer is wanted. The single-import rule makes taking it a one-file change | Carmack |
  | 4 | pyarrow is an **optional extra**, not a runtime dependency. `pip install -e .` appears at 17 call sites across 9 workflow files and `digest.yml` alone runs it 30 times a day; only the jobs that touch parquet install `.[parquet]` | Carmack. Precedent: `digest.yml` already installs `.[faithfulness]` |
  | 5 | `compression` is a knob, `snappy` for `raw`, `zstd` for `compact`. Snappy is what every reader supports without a plugin and barely moves a raw shard's size; zstd is 2.2x smaller at a thousand rows, and a compacted file is read by this project alone | Guardrail #6, on section 4 |
  | 6 | A parquet footer records the writer version, so two runs on different pyarrow versions do not produce identical bytes. That breaks nothing: the commit loop compares path existence, not bytes | Fowler |
  | 7 | JSON stays first-class behind the same door. A payload a person reads in a pull request should not be binary | Owner, 2026-09-24 |
  | 8 | `state/raw` and `state/compact` are claimed in the same commit that creates them. Without it the `_trial_roots` computation in `backend/idhazh/stages/prune_state.py` reads them as unknown directories and the gardener deletes its own records | Fowler. **`day-validations` is not this row's business**: every ledger already has a `config/ledgers.json` entry, that one included, and plan 54 deletes the tree and its entry before row 5 runs |
  | 9 | `day_shards.py` stays CSV-only. Teaching one reader two formats is how a tree ends up with two grammars; `ledger/` exists to avoid that | Fowler |
  | 10 | **The door ships before any byte moves.** Row 3 is the only one-way change in this plan; keeping it out of this pull request is what lets either be reverted alone | Fowler |
  | 11 | **A file carries two identifiers, `unit_id` and `file_id`, and neither can do the other's job** (section 5.7). `unit_id` is a clock-free `uuid5` that is identical across attempts, so `GROUP BY unit_id` collapses a re-run onto its original; `file_id` is a clock-first `uuid8` that differs on every write, so no two writers take one path. **`attempt` goes only in `file_id`, and `producer` goes only in `unit_id`** | Owner, 2026-09-26, overturning the single-identifier design of 2026-09-24, which put a clock and `attempt` inside the value it then deduplicated on |
  | 12 | **Every instant this door reads, writes or compares is UTC** - `written_at_ms` is UTC epoch milliseconds, `covers` is a UTC day or month, and `listed_at` is ISO-8601 with `Z` | CLAUDE.md section 2 |
  | 13 | **Writes honour `lifecycle_status`.** A raw-tier write from a pipeline job into a paused or retired family is skipped with one warning. The compact tier and `MAINTENANCE_JOBS` are exempt, and so is every maintenance route that never asks | The three rulings are the owner's, 2026-09-27, handed over by plan 53. The exemption by tier and by job is Fowler's, 2026-09-27 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | polars | 186.7 MiB and 32.1 s for a dataframe surface this plan does not use | 90 MiB per job over pyarrow, measured | Carmack |
  | 2 | fastparquet | 123.2 s to install, seven times pyarrow, because it compiles against numpy and cramjam | About 106 s per job, measured | Carmack |
  | 3 | Let each writer import pyarrow | The engine stops being swappable the moment a second module imports it | Zero; costs the swap, which is why the door exists | Owner, 2026-09-24 |
  | 4 | Infer the arrow schema from the first row | A nullable column whose first row is null infers as null type and then refuses the second row | Zero; costs a class of failures that appear only on sparse data | Fowler |
  | 5 | Move every remaining ledger under `state/raw/` in this row | It changes where committed data lives across twenty-odd trees at once, which is a migration with its own fixtures, readers and merge drivers | Its own plan, from the map in section 5.8. The owner's rule is where a writer lands in future | ESCALATE trigger 3 |
  | 6 | Ship the door and the migration in one pull request | Reverting the migration would revert the door, and reverting the door would leave committed parquet nothing can read | One extra merge cycle | Fowler |
  | 7 | One identifier doing both jobs, as drafted on 2026-09-24 | It held a write clock and `attempt`, so every write minted a fresh value - and the same section called deduplication `GROUP BY` that value. The GROUP BY collapsed nothing and a re-run's rows would have sat beside the originals forever. **The plan claimed a dedup mechanism it did not have** | About fifteen lines in `filenames.py`, one extra envelope key and one extra column | Owner, 2026-09-26 |
  | 8 | Keep a per-process call sequence to separate two producers of one dataset | A sequence counts calls inside one process, so it differs between attempt 1 and attempt 2 of the same work - it breaks the stability that `unit_id` exists to provide. `producer` is what actually differs and it survives a re-run | Zero; `producer` is a field a call site already knows | Fowler |
  | 9 | Make `built_from` the raw index's `content_sha256` instead of a count, so a compact file proves which listing built it | **It detects a failure this design already forecloses.** Section 5.9.13 has the compaction re-list the one directory it is about to take and rewrite the index on a mismatch **before** compacting, so a stale listing is corrected at read time rather than recorded for somebody to notice afterwards. The hash would also prove provenance rather than correctness - it says which index was read, not that the index was right - and it retypes a declared field from a count to a digest, which is two meanings for one name. **If provenance ever earns its place it is a new key with a named reader, not a retype of this one** | Zero to take; costs a footer key its single meaning, and adds a detector for a case the read-time re-listing already removes | Fowler, 2026-09-26 |
  | 10 | Tell maintenance from new rows by the writer's job alone | `idhazh compact` runs inside three pipeline jobs that also write new rows, so a skipped compact write after its raw days were deleted loses rows while the run reports success | Zero to take; costs rows | Fowler, 2026-09-27 |
  | 11 | Check the status in the path builders | They also serve readers, and a paused family is still read | Zero to take; costs every reader of a paused family | Handover from plan 53, 2026-09-27 |

---

### Row #3 - Two ledgers become parquet and their union drivers retire

- **Scope:** **two** existing ledgers move end to end to parquet, producer and consumer, to prove the chain; the two writers of retirements collapse into one; both union merge drivers retire.

**The chain proof: two ledgers, both ends.** Together they are 11 KB, which is the point - this row proves a door, it does not move a corpus (section 5.8).

`state/feed-retirements.csv` **proves the reader and the union retirement.** Two writers reach it - `stages/plan.py` retires an address that answered `410 Gone` on five separate runs, `stages/assemble.py` retires one that kept answering and stopped being worth reading - and each reaches `ledger.append_retirements` with its own rows and its own warning line. Three readers, those two plus `telemetry/publish/source_health.py`, all through `ledger.load_retirements`. Eight columns, three test files, no fixtures, one committed file of about 500 bytes, no console reader.

**The two writers collapse into one, and both stages call it.** Owner direction, 2026-09-24. `telemetry/source_health.py` grows `file_retirements(state, rows, identity)`: it drops what is already retired, persists through the row 2 door, and writes the one warning line. `ledger.append_retirements` goes. **The two stages keep their two causes** - `410 Gone` and low yield are different evidence about different failures, and merging them would lose why an address went - but neither owns the write any more.

`state/visual-prunes/` **proves the layout, and it is in scope by owner direction, 2026-09-24.** Row 5 turns its pass into a gardener task; leaving the format for a later plan would mean the gardener's record and the gardener's own pass disagreed about how a ledger is written, in the same release. One writer (`stages/prune_state.py`), fifteen columns, eighteen committed files of 11 KB, no reader outside the backend. It moves onto `state/raw/visual-prunes/<YYYY>/<MM>/<DD>/<file_id>.parquet`, one file per writer - `file_id` and not `unit_id`, because `unit_id` is identical across attempts and a retry named by it would overwrite the attempt before it (section 5.7).

**The migration is one-shot and it ships in this row's own commit.** `backend/utilities/migrate_csv.py` reads the committed CSV tree, writes the parquet, deletes the CSV, and **is deleted by row 8**; its removal condition is written on the line that declares it (Guardrail #6). Without it, every committed `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` and `state/feed-retirements.csv` becomes unreadable at its old path, which CLAUDE.md section 11 calls a release blocker.

**Its command line, so no worker invents one:**

```
python backend/utilities/migrate_csv.py --state-dir state --run-id <YYYY-MM-DD-NNNN>
       --git-sha <sha> [--ledger feed-retirements|visual-prunes] [--check]
```

| Argument | Rule |
| --- | --- |
| `--state-dir` | Required. The tree to migrate |
| `--run-id` | Required, `RUN_ID_PATTERN`. A person runs this once, so there is no run to read it from |
| `--git-sha` | Required, `COMMIT_SHA_PATTERN`. The envelope's `git_sha` |
| `--ledger` | Optional. Both ledgers when absent |
| `--check` | Writes nothing. Exit 1 if any source CSV remains |

Every file it writes carries `WriterIdentity(run_id=..., attempt=1, job=ServerJob.MIGRATE, shard=0, producer="utilities.migrate_csv", git_sha=...)`, with `run_id` and `git_sha` taken from the two arguments of those names. Neither has a default, so neither is invented here.

| Exit | Meaning |
| --- | --- |
| 0 | Every source CSV migrated, or there was none. **A second run exits 0 and writes nothing** |
| 1 | A row did not round-trip, or `--check` found a remaining CSV. Nothing was deleted |
| 2 | A file for the same work unit exists and its envelope's `content_sha256` differs from what this run would write. **Two migrations disagree, and neither is discarded**: a person resolves it, because overwriting committed bytes is a one-way write |

**Running it twice is safe by construction.** `unit_id` comes from `(ledger, covers, run_id, job, shard, producer)`, and every term is fixed by the arguments, so a second run mints the same `unit_id` and the same `content_sha256`. A file for that unit that already exists and matches is left alone, and its source CSV is deleted if it is still there. That makes a partial failure re-runnable, which matters most here, because this program rewrites committed data.
- **Files touched:**
  - `backend/utilities/migrate_csv.py` (new, one-shot, deleted by row 8)
  - `backend/idhazh/telemetry/source_health.py` (grows `file_retirements`), `backend/idhazh/stages/plan.py`, `backend/idhazh/stages/assemble.py` (the two `ledger.append_retirements` call sites), `backend/tests/test_source_health.py`
  - `backend/idhazh/contracts/feed_retirement.py`, `backend/idhazh/contracts/visual_prune.py` (**no `version` stamp**: no field moves, and a stamp would say a shape moved when only its address did)
  - `backend/idhazh/ledger/__init__.py` (**`append_retirements` and `append_visual_prunes` are deleted, not left forwarding** - per decision 5 - and their `extend_ledger_file` paths go with them)
  - `backend/idhazh/stages/prune_state.py` (writes through the door)
  - `backend/idhazh/path_classes.py` (the `state/feed-retirements.csv` and `state/visual-prunes` union entries go), `.gitattributes` (the same two union lines go)
  - `config/ledgers.json` (the `visual-prunes` and `feed-retirements` **ledgers** switch to `grain: "raw-and-compact"`, section 2. **Their family entries keep `name`, `description` and `onboarded`**; only the ledger's layout changes), `backend/idhazh/contracts/ledgers.py` and `backend/idhazh/ledger/paths.py` (`feed-retirements` is the one family named by a file's stem today. Once it has a folder, the stem exception in the family check, and the sentence about it in `claimed_roots()`'s docstring, are deleted in this commit rather than left as a rule nothing uses; handover from plan 53, 2026-09-27)
  - `backend/tests/ledger/test_migrate_csv.py`, `backend/tests/test_ledger.py`
  - `docs/architecture/contracts/persistence.md` (the migration section)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/ledger backend/tests/test_ledger.py backend/tests/test_source_health.py -q`. CI runs the full suite.
- **Oracle:** **migration parity** - every row in the committed `state/feed-retirements.csv` and `state/visual-prunes/` tree reads back from the parquet the migration wrote, field for field, with no row lost and none invented. It cannot settle whether a later ledger migrates as cleanly; each brings its own arrow mapping.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Two ledgers, not one. The second costs one more arrow mapping and one more migration test, and it buys the only two shapes that matter: a flat file with two writers, and a day-sharded tree with one. A door proved against one shape is a door proved against one shape | Fowler |
  | 2 | `state/visual-prunes/` migrates here, not in a later plan. Row 5 makes its pass a gardener task, and a release where the gardener's record is parquet and the gardener's own pass still appends CSV to a shared day file is a release that ships the defect it was written to remove | Owner, 2026-09-24 |
  | 3 | Both retire a `merge=union` driver and a `paths.UNION_SAFE` entry, which is part of the proof rather than a surprise: a per-writer parquet file has nothing for a union to settle | Fowler |
  | 4 | **No `version` stamp on either contract.** A ledger move changes no field. Stamping it would say a shape moved when only its address did, and the next reader of the changelog would go looking for the field | Fowler, CLAUDE.md section 11 |
  | 5 | `telemetry/source_health.file_retirements` is the only writer of retirements after this row, and `ledger.append_retirements` is deleted rather than left forwarding. A second way in is how the first way stops being true | Owner, 2026-09-24 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the CSV in place and dual-write for one release | Two writers of one fact, and the second one is the format this plan exists to retire. The ledgers are 11 KB; there is nothing to stage | Zero; costs a second writer | Fowler |
  | 2 | Keep `ledger.append_retirements` forwarding to the new writer | A second way in is how the first way stops being true | Zero; costs the single-writer property | Owner, 2026-09-24 |
  | 3 | Migrate every remaining ledger here | Twenty-odd trees with their own fixtures, readers and merge drivers | Its own plan, from the map in section 5.8. **That plan has one question to answer before it moves a nested ledger**: section 2 files a raw path under the `LedgerName` value, and a nested value (`metrics`, `archive`) names nothing without its family. Raised here for that plan; this plan does not settle it (handover from plan 53, 2026-09-27) | ESCALATE trigger 3 |

---

### Row #4 - The gardener: registry, config, schedule, record, commit loop

- **Scope:** `idhazh gardener list-tasks | plan-shards | run-task | corpus-squash` answer from `config/idhazh_gardener.json` and the declarations in `config/gardener/`; a run writes one record per shard and lands it on `main`. `backend/idhazh/prune/` is absorbed. No retention pass has moved and nothing is deleted.

**`backend/idhazh/prune/` becomes `backend/idhazh/gardener/`.** That package is not a telemetry thing and never was: `one_at_a_time.py` answers "how do I delete a collection's members one at a time, safely, resumably, under a ceiling", which is the gardener's whole job; `report.py` turns a pass into the record row; `github_collections.py` is a task. All three move, `contracts/knobs/prune.py` merges into `contracts/knobs/gardener.py`, and the package is deleted rather than left as a second home. `telemetry/prune.py` keeps its verb and imports the core from its new place, which is the right direction of dependency - a task depending on the gardener, not the gardener on a task.

**The verbs are two words where one was doing too much work:**

| Verb | What it does |
| --- | --- |
| `idhazh gardener list-tasks` | Prints every registered task, its lifecycle status, its window and what it owns |
| `idhazh gardener plan-shards` | Splits the active tasks into shards and emits the matrix. The standard-library twin under `backend/utilities/` is what the `plan` job runs |
| `idhazh gardener run-task NAME` or `--shard N` | Runs one task, or one shard's worth |
| `idhazh gardener corpus-squash` | Squashes the git history the committed corpus grows (row 6). Not a matrix task |

**The verb is `plan-shards` and not `find-due` because nothing asks a task whether it is due.** Every task in the matrix runs at every wake (section 5.3), so the program reads config, splits the active list and stops - it reads no last-run state of any kind. A verb named for a question the program does not ask is a verb that sends the next reader looking for the answer (CLAUDE.md section 0b). Owner ruling, 2026-09-26; same move that took `squash-history` to `corpus-squash`.

**The verb says nothing about the work, and that is deliberate.** The twenty tasks do four different kinds of work - delete behind a window, list a raw day, compact one period into the next, rewrite history - so any verb naming the work would be wrong for some of them; the task's own name already says which kind it is. An earlier draft used `tend`, which was gardening vocabulary rather than a description, and made a reader hold the metaphor to know what the command did (CLAUDE.md section 0b). The workflow job is `run-tasks` for the same reason, and `ServerJob` takes that spelling.
- **Files touched:**
  - `backend/idhazh/gardener/__init__.py`, `cli.py` (the router - a copy of `backend/idhazh/telemetry/cli.py`'s shape), `tasks/__init__.py` (**a package, never a module called `tasks.py`**; a docstring and no sibling imports - **the directory this row creates**, and rows 5, 7, 8 and 9 each add their own modules to it), `registry.py` (new: `discover()`, section 5.5 - the one walk, sorted, memoised), `schedule.py`, `runner.py` (the shard loop, the discovery pre-flight and the ownership assertion), `publish.py` (section 5.6)
  - `backend/utilities/gardener_shards.py` (new: the standard-library-only shard reader the `plan` job runs before any install. **It opens `config/idhazh_gardener.json` and a sorted glob of `config/gardener/*.json`, and nothing else** - sections 5.2 and 5.3)
  - `backend/idhazh/contracts/knobs/gardener.py` (section 5.2), `config/idhazh_gardener.json`, `backend/idhazh/config.py` (load, and every refusal in section 5.2)
  - `backend/idhazh/contracts/collection_prune.py` (widened per section 5.1, with its `version` stamp and one `changelog` line), `backend/idhazh/contracts/knobs/prune.py` (merges into `knobs/gardener.py`)
  - `backend/idhazh/prune/` (deleted: `one_at_a_time.py` and `report.py` move to `gardener/`, `github_collections.py` to `gardener/tasks/`), `backend/idhazh/telemetry/prune.py` and `backend/utilities/prune_artifacts.py` (their imports follow), `backend/tests/prune/` (moves with them)
  - `backend/idhazh/contracts/ledger_name.py` (`LedgerName` gains `GARDENER = "gardener"`) and `config/ledgers.json` (one `gardener` **family**: `lifecycle_status: active`, a one-line `description`, `onboarded` set to the UTC day this row lands, and one ledger, `{name: "gardener", grain: "raw-and-compact", prefix: ["gardener"]}`. `GARDENER = "gardener"` already passes the naming rule; handover from plan 53, 2026-09-27). **Both or neither**: `backend/tests/contracts/test_ledger_registry.py` refuses a member with no entry and an entry with no member, and the build stops at import either way.
  - `backend/idhazh/contracts/ledgers.py` (`Grain` gains `RAW_AND_COMPACT = "raw-and-compact"`, section 2) and `backend/idhazh/ledger/paths.py` (`path()`, `relpath()` and `tree_root()` refuse a `raw-and-compact` ledger by name and point at the builders section 5.4 declares), with a refusal case for each in `backend/tests/contracts/test_ledger_registry.py`, and `docs/architecture/contracts/ledger-registry.md` (the sixth grain and **what `prefix` means for that grain**: everywhere else it is the path from `state/`, but for a `raw-and-compact` ledger it is the path inside each of the two roots, so `["gardener"]` means `state/raw/gardener/` and `state/compact/gardener/`. The family check still passes, because `prefix[0]` is still the family's name; handover from plan 53, 2026-09-27), and `docs/architecture/contracts/state-ledgers.md` (the `gardener` row)
  - `backend/idhazh/cli.py` (the `gardener` verb joins the `choices` tuple)
  - `backend/tests/gardener/`, `backend/tests/contracts/test_gardener_config.py`, `tests/fixtures/gardener/`
  - *(`frontend/src/lib/server/host-fingerprint.ts` was listed here. Row 2 made that edit, so this row touches no frontend file - decision 7)*
  - `docs/architecture/publishing/idhazh-gardener.md` (new - created here so rows 5 to 8 extend a page rather than each inventing one), `docs/concepts/config.md`, `docs/concepts/config/idhazh-gardener.md`, `docs/architecture/publishing/committing.md`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/contracts -q`, and `python backend/utilities/gardener_shards.py` runs under a bare interpreter with no package installed **and in a copy of the tree holding only `config/` and `backend/utilities/`**, which is the checkout row 8 gives it. CI runs the full suite.
- **Oracle:** two checks. The two-way check - every active or paused declaration is served by exactly one module, and every module serves at least one of them (section 5.5), asserted both ways; and for every pair, neither's owned set intersects the other's and neither is a prefix of the other, with the complement task's discovered set empty against the named set. And idempotence - `publish()` against a local bare repository standing in for `origin` leaves the same tree run twice as run once, and against a moved tip leaves both the mover's change and this job's. It cannot settle what a real GitHub rejection does; row 6's named observation is the first reading of that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The config file is `config/idhazh_gardener.json`, not a block in the app config | Owner, 2026-09-24 |
  | 2 | The router copies `telemetry/cli.py` verbatim in shape, so consolidation introduces no new convention | Fowler |
  | 3 | The record contract is `CollectionPruneRow` widened, not a new twin. Eight fields already exist with these meanings and nothing persists the shape today | Fowler, section 5.1 |
  | 4 | **No last-run state is persisted anywhere, and the `plan` job reads no state at all.** A windowed task runs daily and its window decides. A compaction runs daily and its own watermark decides, inside `run-tasks`, where that ledger is already in the cone. The history squash reads the key the corpus already owns, inside the `history` job, which has `corpus/` in its checkout. A mutable per-task file would have been the one unsharded, overwritten path under `state/`, which is the race the whole design removes | Section 5.3. **Owner, 2026-09-26**, overturning the 2026-09-24 clause that had the plan job read "the newest month under its own output, with two directory listings" - a read outside its checkout, and one that also contradicted row 7's rejected alternative 8 |
  | 5 | The `plan` job's shard reader is standard library only, so it runs before `pip install` exactly as `prune_due.py` does today, **and it opens no file outside `config/`**. Both halves are hard constraints on the config shape | Carmack; the second half Owner, 2026-09-26 |
  | 6 | A task whose window would include today is refused at config load. That is what makes the gardener safe to run while `digest.yml` is live, and it turns an arrangement into a check | Fowler |
  | 7 | `ServerJob` gained `MIGRATE`, `RUN_TASKS` and `HISTORY` in row 2, with its frontend copy `SERVER_JOB`. This row spends them and touches no frontend file. `MIGRATE` is a permanent member for a program a person runs once, and it is kept so a record can say a row came from the migration rather than from a scheduled wake | Fowler, 2026-09-26 |
  | 8 | **No `enabled` flag, because `lifecycle_status: paused` is the off-switch.** An `enabled: false` would be a second spelling of it. **`dry_run` is not the off-switch either**: a dry run still runs, still costs a task slot and still writes a record, which is what onboarding needs and exactly what a broken task must not do | Fowler, corrected against section 5.2's lifecycle, 2026-09-26 |
  | 9 | **No `cadence` key on the base.** A wake rate is a cron line, not a per-task value: `on.schedule.cron` is one line in the workflow and every matrix task is in that wake. The one schedule that is a real choice belongs to `corpus-squash`, which is not in the matrix, and it lands as `every_days` on `HistoryPolicy`. **This does not break Guardrail #6**, whose test is "change the config and behaviour changes": a per-task `cadence` fails that test the moment the `plan` job stops reading it, so deleting it removes a claim rather than a control. Every knob that does decide something survives - the cron, `window`, `compact_after_hours`, `max_periods_per_run`, `every_days` | Owner, 2026-09-26, on Fowler's reading |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Resolve the registry from config with `importlib` on a path the declaration names | **Still rejected, and the open list does not revive it.** An import path in data lets a config file name any module in the tree, which is the Guardrail #11 surface. Discovery walks one fixed package and binds by declared name; the declaration never names a module | Zero; costs the property that only `backend/idhazh/gardener/tasks/` can ever be imported as a task | Fowler; re-stated against the open list, Owner, 2026-09-26 |
  | 6 | Keep a frozen tuple in `tasks/__init__.py`, built from explicit imports | Adding a task then edits a file every other task lives in, which is the join the open list removes, and the owner ruled the list must not be closed | Zero to take; costs the property that one pass is one module and one declaration and nothing shared | Owner, 2026-09-26 |
  | 7 | Generate an index file from the directory and have the `plan` job read one file | It re-creates the single append point the split removes, and a generated index can disagree with the directory - so there is then a refusal to write, a test to keep, and a question about which one is right | Zero to take; costs the property that the directory is the list | Fowler, 2026-09-26 |
  | 8 | Discover lazily - import only the modules this shard's names need | A duplicate name is then invisible, because only one of the two modules is ever imported, and the pre-flight cannot answer before the first task runs | Zero to take; costs the duplicate-name refusal and the nothing-changed guarantee at exit 2 | Carmack, 2026-09-26 |
  | 2 | One flat `idhazh gardener-<task>` verb per task | Sixteen top-level verbs; the `choices` tuple stops being readable | Zero; costs the CLI its shape | Fowler |
  | 3 | Three writer kinds for `already_landed` | A dry run selects nothing, so a delete-only verdict reads as "already landed" and publishes no record - exactly the reading the dry run exists to produce | Zero; costs every dry run its output | Fowler |
  | 4 | Compare blobs to decide whether a record landed | `duration_ms` and the parquet footer are not byte-stable across a retry, so it fires the un-retryable code on the happy path | Zero; costs the loop its first iteration | Fowler |
  | 5 | Keep `cadence` on every task declaration | Every declaration would restate one value nothing reads, each hand-written by a different row and none able to change behaviour. The load refusal written to police it - "a published ledger whose daily compaction does not have `cadence: days: 1`" - cannot fire once nothing can set it wrong, and a refusal that cannot fire reads as a control in review and costs a test that passes forever | Zero to take; costs the config its claim that a key changes behaviour. **Putting the knob back later is one key, one refusal and one reader; taking it out later is a `refuse_a_removed_knob` entry, one key in every committed declaration and two parquet columns already written** | Fowler, 2026-09-26 |

---

### Row #5 - Every prune pass becomes a gardener task

**The rule is one pass, one task; the count is whatever the registry holds.** `backend/idhazh/stages/prune_state.py` held eleven passes when it was read on 2026-09-26, and **plan 54 deletes one of them before this row starts**, so ten become tasks. **No code and no test may hard-code either number.** The directory `config/gardener/` is the answer to "how many", the two-way refusal in section 5.2 is what keeps it honest, and a further pass arriving next month is a module and a declaration rather than an edit to this plan.

- **Scope:** every pass in `backend/idhazh/stages/prune_state.py` becomes a task with its own window in the gardener config and its own `dry_run`; the module is deleted; `digest.yml` stops calling it.
- **The ten, named so none is missed:** `_prune_seen_shards`, `_prune_counterfactual_shards`, `_prune_trace_shards`, `_prune_feed_health_shards`, `_prune_host_fingerprint_shards`, `_prune_score_shards`, `_prune_trial_shards`, `_prune_digest_fragments`, `retention.prune_telemetry`, `_clean_the_visuals`.
- **`_prune_day_validation_shards` is the eleventh, and it is deliberately not in that list.** Plan 54 deletes that pass, its knob, its ledger and its committed tree. **Finding it still in the module is the stop condition in section 0**, not a licence to write the task: that tree is claimed twice today, by this pass and by the strays sweep, so a task written for it freezes a live defect into a declaration that ESCALATE trigger 6 then guards forever.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/` - one module per task: `seen.py`, `counterfactual_scores.py`, `traces.py`, `feed_health.py`, `host_fingerprint.py`, `scores.py`, `trials.py`, `digest_fragments.py`, `telemetry_aggregate.py`, `visual_prune.py`
  - `docs/concepts/growing-reads.md` (one entry: the `trials` task's `git ls-tree HEAD state/` at depth one, with what it reads, how cost scales, and why a bounded input cannot answer it)
  - `config/gardener/seen.json`, `config/gardener/counterfactual-scores.json`, `config/gardener/traces.json`, `config/gardener/feed-health.json`, `config/gardener/host-fingerprint.json`, `config/gardener/scores.json`, `config/gardener/digest-fragments.json`, `config/gardener/visual-prune.json`, `config/gardener/trials.json` and `config/gardener/telemetry-aggregate.json` (the ten tasks of section 5.2.1, one file a task, each carrying the window moved from `config/idhazh.json` and naming the key it came from). **No registry file is edited**: each module holds `KIND` and `run`, and `bind()` finds it (section 5.5)
  - `config/idhazh.json` (the moved windows leave `observability` and `retention`; `collect.seen_window_days` and `lens_weights.window_days` stay)
  - `backend/idhazh/contracts/knobs/observability.py`, `retention.py` (the emptied keys; `refuse_windows_shorter_than` becomes the cross-file check at `config.load()`)
  - `backend/idhazh/retention.py` (the ten prune functions leave), `backend/idhazh/stages/prune_state.py` (deleted), `backend/idhazh/telemetry/prune.py` (the body leaves; the verb forwards)
  - `backend/idhazh/cli.py` (`prune-state` forwards and warns, with its removal condition on the declaring line)
  - `.github/workflows/digest.yml` (the prune step is removed; the commit step is untouched)
  - `frontend/src/lib/server/config.ts` and every console surface printing a retention window; the frontend field-set and vocabulary tests
  - `backend/tests/gardener/tasks/`, `backend/tests/workflows/`
  - `docs/architecture/publishing/idhazh-gardener.md`, `retention.md`, `telemetry-series.md`, `one-visual-one-file-and-the-race-between-two-runs.md`, `docs/concepts/adaptive-pruning.md`, `docs/concepts/config/retention-ages.md`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/workflows backend/tests/contracts -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks, and the browser smoke on any console page that prints a retention window (CLAUDE.md section 12). `git grep -n 'prune-state\|prune_state'` returns only the alias and its removal condition. CI runs the full suite.
- **Commits inside this pull request:** one per task, then the window move, then the console follow, then the module deletion last. A reviewer reads ten small diffs rather than one large one.
- **Oracle:** for each of the ten, the old pass and the new task over the same fixture tree produce the identical removal set, asserted per task; and every window value is byte-identical before and after the move, compared key by key against a frozen fixture. It cannot settle whether a console page reads the right key; the browser smoke does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`dry_run` is required with no default, and all ten declarations ship `true`, because every pass in the module is report-only today.** `.github/workflows/digest.yml` passes `--dry-run` to the whole `prune-state` invocation, `config/idhazh.json` carries `retention.dry_run: true`, and one flag fans out to every pass - read 2026-09-26, correcting a draft that believed some were live. Flipping a report-only pass into a live deletion inside a move row is a behaviour change dressed as a refactor | Fowler; the reading, Owner, 2026-09-26 |
  | 2 | `_prune_digest_fragments` is a task. It was missing from the earlier draft entirely, and with the module deleted its ledger would have grown unbounded with no test going red | Verified against `stages/prune_state.py`, 2026-09-24 |
  | 3 | Each task's window moves in this row, with its task. A separate row would be a second pass over every file this row already touches, and the oracle works per task exactly as well as in bulk | Fowler |
  | 4 | `collect.seen_window_days` and `lens_weights.window_days` do not move. Both are read by the pipeline to produce a day; moving them would make the planner load the retention config. The cross-file refusal keeps the two in step | Fowler |
  | 5 | The `trials` task declares the **complement** - everything under `state` that no other task owns and no **family** claims, read from `ledger.claimed_roots()` - not a prefix. **A family, not a ledger name**: a nested ledger's name (`metrics`, `archive`, `shard-outcomes`) is not a top-level folder, so checking `LedgerName` values would leave `content-similarity-judge/` and `llm-council/` unclaimed and the sweep would delete them. **And the sweep is not a retention tool**: every family is claimed, so a family no task owns - `day-metrics`, which `/console/model` reads, is one - is never swept, and bounding one takes its own task (handover from plan 53, 2026-09-27). A prefix would be a prefix of every other task's path and the disjointness oracle could never pass | Fowler |
  | 6 | Each task routes through `backend/idhazh/gardener/one_at_a_time.py`, which two of the four existing surfaces already use and the eleven biggest do not. That is the consolidation, not the router | Fowler |
  | 7 | `idhazh telemetry prune` survives as a verb and forwards. An operator's muscle memory is not a reason to move a body | Owner, 2026-09-24 |
  | 8 | The visuals task keeps `dry_run: true` and owns paths under `frontend/public/digest/`, which no other task owns. That ownership is what lets it stage its own deletions - the thing `digest.yml`'s commit step never staged, and the reason the deletion could not be switched on there | Plan `20260905-13`, row titled "The fuse comes out, and one run is watched" |
  | 9 | The visual-prune record's partition, format and merge policy all move in row 3, not here. Row 5 changes one thing about it: which program calls the writer. Three changes and a move in one row is how a refactor hides a data migration | Fowler. Owner direction on visual-prunes, 2026-09-24 |
  | 10 | The telemetry aggregation's delete set is bounded by the ownership invariant in section 5.5. A derived path its producer rebuilds is not an input to that task and is not that task's to delete | Fowler |
  | 11 | **The telemetry aggregation keeps writing `state/item-health-summary/<YYYY-MM>.csv` whole, and this row does not close that.** One writer rewriting a shared month file in place is the shape telemetry-intent N6 retires, and from this row the gardener owns it. It is left alone for decision 9's reason - changing a path's format and its partition inside a move row is how a refactor hides a data migration - and the cost of leaving it is bounded by a fact worth stating: **the tree holds nothing today.** `state/item-health-summary/` does not exist, checked 2026-09-27, because no month has yet aged past `observability.item_health_full_grain_months: 14`. There is nothing to migrate and nothing at risk, and the first month to age out is when that stops being true | Fowler, 2026-09-26 |
  | 12 | **`digest-fragments` keeps a filename a re-run overwrites, and this row prunes it without fixing it.** `assemble.fragment_path` writes `state/digest-fragments/<YYYY>/<MM>/<DD>/<run_id>.json`, and GitHub's run id is stable across attempts - only `run_attempt` moves - so attempt 2 writes over attempt 1. That is the shared-path write N6 removes, and section 5.8 routes the ledger's move to a later plan. **What this row must not do is make it worse, and one refusal already stops it**: section 5.2 refuses a window that would include today at config load, so this task never selects a day a concurrent `assemble` is still writing into | Fowler, 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Split the ten across three or four pull requests | `main` carries a half-migrated `prune_state.py` for several merge cycles, and somebody writes a bridge letting a task read a window out of the app config and then deletes it again | Zero; costs three extra merge cycles and a throwaway bridge | Fowler |
  | 2 | Ship one or more tasks at `dry_run: false`, so something starts being deleted | **There are no live deletions to preserve.** Every pass in the module is report-only today (section 5.2.1), so a `false` here is the first deletion that tree has ever seen, chosen inside a move row by whoever wrote the declaration, with no record for anybody to have read first | Zero to take; costs an irreversible first deletion that no test can see is wrong | Owner, 2026-09-26, correcting a draft that believed nine deletions were live |
  | 3 | Keep one shared `--dry-run` | It is the defect this plan exists to remove | Zero; costs the ability to enable one deletion without enabling all | Owner, 2026-09-24 |
  | 4 | Keep `prune-state` in the assemble job and move only some passes | Every task then commits from two workflows, and the visuals deletion stays impossible | Zero; costs the deletion plan 13 waits on | Owner, 2026-09-24 |
  | 5 | Delete the `prune-state` verb immediately | A dispatch or script naming it breaks with no warning | Zero; costs an operator a silent failure | Guardrail #6 |

---

### Row #6 - The corpus squash becomes Python

- **Scope:** the forty lines of inline shell in `prune.yml` that do the squash become a tested module; `prune_due.py` is renamed for the one job that reads it and keeps its place in front of the full clone; `pruned_date` becomes `last_run`.

**The `history` job gates itself, and this is where that becomes true.** It keeps the two-stage checkout `prune.yml` runs today - `fetch-depth: 1`, read the file, and only on a due day a second `actions/checkout@v6` at `fetch-depth: 0` - because the file it must read lives in `corpus/`, which no other shape of this workflow puts on disk (section 5.3). The reader stays standard-library-only for the same reason it is today: it runs before any install. **Owner ruling, 2026-09-26.**

**What `backend/utilities/gardener_shards.py` must never grow: a read of this file.** Verified by grep on 2026-09-26, the readers of `corpus/corpus.meta.json` after this row are `backend/idhazh/corpus.py` - `read_meta`, `write` and the renamed `record_run`, all three in this row's Files touched - and `backend/utilities/corpus_squash_due.py`, this row's own rename. The `plan` job's reader names neither the path nor the key, which is what makes the rename below safe: a standard-library reader left naming `pruned_date` would read `None`, fail open, and force-push `main` every day.

**The reader must tell four things apart, and today's fallback tells two.** `prune_due.py` does `.get("pruned_date")` and falls back to `None`, with its own comment saying an absent stamp is "a force-push a day". **That fallback is written for an absent file and cannot see an absent key.** Rename the key without changing the fallback and a healthy `corpus.meta.json` reads as never-pruned - the same daily force push, arriving through the rename instead of through the checkout. The `history` job gating itself does not protect against this one, because the job is reading the file correctly and the file is telling it the wrong thing.

| What the reader finds | What it means | What it does |
| --- | --- | --- |
| No file at `corpus/corpus.meta.json` | Never pruned - a fresh clone, or a corpus no squash has reached | `due=true`. Today's comment carries over verbatim |
| `last_run` present and a valid date | The normal case | Compare it against `every_days` |
| `last_run` absent, `pruned_date` present and valid | A payload written before this row's rename | Read it. **This reader is the second home of that alias** |
| Anything else - both keys absent, a value that is not a date, a file that is not JSON | The reader does not know | **Exit non-zero and print no `due`.** A job that cannot read the stamp does not force-push |

**An unsure read exits rather than answering "due", because the two errors are different sizes.** A false "due" rewrites `main` every day: every clone has to be re-fetched and `git blame` loses its range. A false "not due" delays a squash by one wake, which section 5.3 already prices at one day. So the reader leans not-due when it is unsure - and "unsure" has to be a state distinct from "absent" before that sentence can be said at all.

**The `pruned_date` alias now has two homes, and ESCALATE trigger 1 covers both.** One is `CorpusMeta`'s `model_validator(mode="before")`. The other is this reader, which is standard-library-only and cannot import the contract - Guardrail #3's hand-copy case, so a named test holds the two in step. Row 8 removes both in one commit or it removes neither: an alias surviving in only one of them is a payload that one reader understands and the other does not.

**`corpus_history.py` holds five functions, and `squash_history` is the only one anything outside it calls:**

```python
def boundary_commit(repo: Path, *, keep_days: int, now: datetime) -> str | None:
    """The newest commit at or before the cut, or None when fewer than two are behind it.

    The cut is `now` minus `keep_days`, in UTC. None means the squash is not worth
    doing this wake, which is a success and not a failure.
    """

def squash_below(repo: Path, *, boundary: str, message: str) -> str:
    """Collapse everything at or before `boundary` into one orphan root. Returns its sha."""

def replay_above(repo: Path, *, boundary: str, onto: str) -> None:
    """Rebase every commit after `boundary` onto `onto`, trees unchanged."""

def push_rewritten(repo: Path, *, tip_before: str) -> int:
    """Force-push the rewritten history, refusing if origin's tip moved.

    The refusal and its exit code carry over unchanged from
    `backend/utilities/push_rewritten_history.py`, which returns 1. Changing either
    is ESCALATE trigger 2.
    """

def squash_history(repo: Path, *, keep_days: int, now: datetime, message: str) -> int:
    """The whole squash, in order, and the `history` job's only entry point.

    Resolve the boundary; if None, return 0 having written nothing. Otherwise squash,
    replay, `corpus.record_run(meta_path, when=now.date())`, then push. A refused push
    returns without recording the run, so the squash is due again at the next wake.
    """
```

| Exit from `squash_history` | Meaning |
| --- | --- |
| 0 | Squashed and pushed, or nothing was worth doing |
| 1 | The push was refused because the tip moved. No stamp written |
| 2 | The repository is not in a state this can rewrite - a detached head, a dirty tree, a missing boundary sha |
- **Files touched:**
  - `backend/idhazh/gardener/corpus_history.py` (new; the five functions and the exit codes above)
  - `backend/idhazh/gardener/cli.py` (the verb `idhazh gardener corpus-squash`), `config/gardener/corpus-squash.json` (`kind: history`, `owns: ["corpus"]`, and the squash's own `every_days`), `backend/idhazh/gardener/tasks/corpus_squash.py` (new: `KIND` set to the `history` kind, and a `run` that calls `corpus_history.squash_history`). **The verb binds that module through the same two lookups a shard uses (section 5.5) and calls its `run`**, so the two-way check holds with no exception and the verb is not a second way in
  - `backend/utilities/prune_due.py` **renamed to `backend/utilities/corpus_squash_due.py`**, standard library only, reading `corpus/corpus.meta.json:last_run` and the squash's own `every_days`, and telling the four cases above apart. `backend/utilities/push_rewritten_history.py` (the tip-moved refusal moves in, behaviour and exit code unchanged)
  - `backend/tests/workflows/test_staged_paths.py` (**the `prune_due.py` path only** - that test invokes the reader against the real committed config and the real `corpus/corpus.meta.json`, so a prune run changes its answer and it can only assert shape. Nothing else in it moves)
  - `backend/tests/workflows/test_corpus_squash_due.py` (new: **the assertion that protects the force push**, driven from a fixture repository as `backend/tests/workflows/test_prune_push.py` already builds one. One case per row of the four-case table, and the last of them asserts a non-zero exit with no `due` printed. There is no such assertion today)
  - `backend/idhazh/corpus.py` (`stamp_prune()` becomes `record_run()`), `backend/idhazh/contracts/corpus.py` (`pruned_date` becomes `last_run` with a `model_validator(mode="before")` alias for one release, then `refuse_a_removed_knob`; precedent `models.route` to `models.visual_planner`, PR #1045). Section 11 applies: `version` stamped, one `changelog` line, read-side migration in the same commit
  - `backend/idhazh/cli.py` (`prune-stamp` retires), `corpus/corpus.meta.json`
  - `backend/tests/gardener/test_corpus_history.py`, `backend/tests/contracts/test_corpus_meta.py` (**including the test that holds the two aliases in step**: the contract and the standard-library reader accept the same two keys and prefer the same one)
  - `docs/how-to/fine-tune-a-model.md`, `docs/concepts/adaptive-pruning.md`, and the pages `git grep -n 'prune-stamp\|stamp_prune\|pruned_date'` names
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/contracts -q` - the squash runs against a temporary repository the test builds, never against this one. CI runs the full suite.
  - **Not a gate:** dispatching `idhazh-gardener.yml`. What it would prove is a force push onto `main`, which cannot be repeated, cannot run unattended and ends with somebody reverting history. **Named observation instead**, at the first scheduled run after row 6 merges: read the job log for the boundary commit it resolved and the count it collapsed, and confirm `corpus/corpus.meta.json:last_run` advanced. A refused push says the tip moved and writes no stamp, so it is due again at the next daily wake.
- **Oracle:** against a temporary repository with a known commit graph, the task collapses exactly the commits at or before the boundary date and leaves every later commit reachable with its tree intact, compared by `git rev-parse HEAD^{tree}` before and after. It cannot settle what a real force push does under a concurrent push; the tip-moved refusal handles that and is carried over unchanged.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The boundary is a **date**, from `finetune.prune_keep_days`. The commit count `prune.yml` computes is a "worth doing" check that skips when one commit or fewer is behind the cut, not a policy | Owner, 2026-09-24, correcting an earlier draft |
  | 2 | `corpus/corpus.jsonl`'s row cap does not move here. It is a count bound applied by `corpus.roll()` at harvest time | Owner, 2026-09-24 |
  | 3 | **The squash is not a matrix task.** It rewrites every commit, force-pushes, and needs a full clone with history - none of which works in a depth-1 sparse-checkout matrix runner. It gets its own verb, its own declaration and its own job | Fowler |
  | 4 | The force push keeps `--force`, not `--force-with-lease`: the rebase rewrote every commit a lease would name | `backend/utilities/push_rewritten_history.py`, carried over |
  | 5 | The tip-moved refusal is carried over verbatim including its exit code. Changing it is ESCALATE trigger 4 | CLAUDE.md section 8 |
  | 6 | `corpus/corpus.jsonl` stays JSON lines. It is the file a trainer loads, and TRL, Unsloth, Axolotl and LLaMA-Factory all read that shape | `backend/tests/test_corpus_contract.py` |
  | 7 | **The squash's dueness read stays in the `history` job and stays a separate program from the shard reader.** Two jobs, two checkouts, two questions: the `plan` job splits tasks into shards from `config/` alone, and the history job asks whether a squash is due from the file it can see. One reader serving both would have to see both trees | Owner, 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the squash in inline shell | The largest piece of untested logic in the repository, and it force-pushes `main` | Zero; costs the only force push any coverage at all | Fowler |
  | 2 | Keep `pruned_date` and add `last_run` beside it | Two keys naming one fact | A one-release alias is what a rename costs; keeping both costs a permanent second spelling | Guardrail #4 |
  | 3 | Put the squash in the `run-tasks` matrix | Every sibling job's push would be invalidated mid-flight, and the checkout it needs is not the one a matrix runner takes | Zero to take; costs every other task its commit | Fowler |
  | 4 | A `history_due` flag in the plan payload, computed by the `plan` job | The file it must read is in neither of that job's two checkout directories, so it reads as "never run" and force-pushes `main` daily instead of about twelve times a year | Zero to take; costs the only force push in this repository its gate | Owner, 2026-09-26, overturning the 2026-09-24 design |
  | 5 | Keep the flag and have the `plan` job read the file with `git cat-file blob HEAD:corpus/corpus.meta.json` | It works - a sparse checkout narrows the working tree, not the object database, so the blob is already there and costs no extra bytes. It is still a new process boundary and a new refusal in front of the only force push, where the history job simply opens a file it already has | Zero extra bytes, measured 2026-09-26; costs a `rev-parse --verify` gate, a refusal that must not answer "not due" quietly, and two integration tests | Fowler, 2026-09-26 |

---

### Row #7 - One compaction task a ledger, two compact periods, and the diagrams move into the page

- **Scope:** one compaction task a ledger, which lists each eligible raw day and then runs the daily and monthly periods, each with its own window and watermark (section 5.3); `digest.yml`'s own compaction step moves in, so one config decides when a day is closed; the architecture page takes both diagrams.

**Compaction is not one blanket pass over `state/raw/`.** One task a ledger, `config/gardener/compact-<ledger>.json`, lists that ledger's eligible raw days, then runs the daily and monthly periods in order, in one process and one commit (section 5.3). It runs at every wake, as every task does. Adding a ledger is one declaration and no Python.

**The order inside a period is the part a worker must not rearrange**, and section 5.3 gives both sequences step by step. Read the index. Read exactly the files it names. Write the period's compact file. Rewrite that period's index. **Advance that period's watermark last.** A run that dies in the middle leaves the watermark behind the truth, so the next wake redoes that one period and nothing else. The opposite order leaves a period in no tier, in no index and past the watermark - gone, with no error, and no test able to see it.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_index_day.py` (new; lists a raw day and writes `RawDayIndex`; the leading underscore keeps discovery from importing it as a task, section 5.5), `backend/idhazh/gardener/tasks/compaction.py` (new; absorbs `backend/idhazh/stages/compact.py`, one callable serving both periods), `backend/idhazh/ledger/settle.py` (the read-side settlement over a raw day tree)
  - *(`backend/idhazh/contracts/ledger_index.py` and its contract test moved to row 11 on 2026-09-27. This row imports the four shapes from there and writes them)*
  - `backend/idhazh/contracts/file_envelope.py` (`FileEnvelope` takes a `changelog` entry for `built_from` being filled for the first time. **Additive and back-compatible**: `built_from` is `int | None = None` from row 2, so a row-3-era envelope reads unchanged and needs no migration)
  - `backend/idhazh/ledger/paths.py` (`raw_index_path`, `compact_path` takes a `Period`, `compact_index_path`, `watermark_path`)
  - `config/gardener/compact-gardener.json`, `config/gardener/compact-visual-prunes.json` and `config/gardener/compact-feed-retirements.json` (**one compaction a ledger**, keys per section 5.9.5. No task ever limited these three ledgers, so section 5.2 gives them no floor. `gardener` and `visual-prunes` keep the default windows. **`feed-retirements` sets `monthly_window: {unit: months, value: 60}`**, because a retirement the window deletes is a feed the pipeline starts fetching again. These windows are the owner's, 2026-09-27, so writing them does not fire ESCALATE trigger 6). **No registry file is edited**: `compaction.py` holds `KIND` and `run`, and `bind()` finds it by kind, so a fourth ledger is one declaration and no Python
  - `docs/concepts/growing-reads.md` (three entries: the compaction's per-day listing, the compaction's per-period read, and `settle()` over a raw day tree - each with what it reads, how cost scales, and why a bounded input cannot answer it)
  - `backend/idhazh/gardener/schedule.py` (**no pairing rule and no placement key**: one compaction a ledger means there is no pair to place, which is what decision 13 bought by merging rather than by scheduling)
  - `config/idhazh.json` (`run.settled_fold_after_days` leaves), `backend/idhazh/contracts/knobs/run.py`, `backend/idhazh/contracts/knobs/removed.py` (the removed-knob entry, without which a local config fails silently)
  - `backend/idhazh/cli.py` (the `compact` verb forwards with its removal condition), `.github/workflows/digest.yml` (the step named `Fold the days that can gain no more rows` is removed). **Two more workflows call the verb**: `measure.yml`'s `runtime` job and `validate.yml`'s `decide` job each run `idhazh compact --config backend/var/candidate-config`. They keep calling it, so the verb's removal condition is that neither does, and their writes at the compact tier land under their own jobs - which is why row 2's status check exempts the compact tier rather than trusting a job name (Fowler, 2026-09-27)
  - `.gitattributes` (the three JSON `-merge` lines in section 5.4)
  - `TODO/20260924-50-idhazh-gardener-plan.md` (section 3 becomes a link)
  - `docs/architecture/publishing/idhazh-gardener.md` (takes both diagrams and the compaction), `docs/reference/github-actions.md`, `docs/concepts/adaptive-pruning.md`, `docs/architecture/publishing/retention.md`, `docs/concepts/glossary.md`
  - `backend/tests/gardener/tasks/test_compaction.py` (it also compacts a paused family and asserts the compact file lands: row 2's lifecycle check, through the real task), `backend/tests/ledger/test_settle.py`, `backend/tests/workflows/test_digest_workflow.py`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/ledger backend/tests/contracts backend/tests/workflows -q`, and `python backend/utilities/doc_load.py` before and after. The six diagram checks in [docs/reference/documentation-structure.md](../docs/reference/documentation-structure.md) are run by eye on a light page and a dark one, for both diagrams. CI runs the full suite. **No browser smoke**: nothing published changes in this row, because `LedgerConfig.published` is still empty.
- **Oracle:** **compaction changes no answer, and no date is ever readable twice.** **The rows in a compact file equal `settle()` over the raw rows it was built from**, in equal order, so nobody who reads a compact file has to settle it - that is what makes compaction safe to skip, safe to repeat and safe to run on only some periods. The second half is the one that catches the defect that matters: over a fixture ledger carrying both periods plus open raw days, **every date in the window is reachable through exactly one file, and a date the daily watermark has passed that is named in neither index is reported as a hole rather than skipped.** **After every run, the newest day `daily.json` names is the daily watermark's `through`**, a run whose newest day had no rows included, because the browser takes its edge from that entry. A date in two periods doubles every number a panel draws, which is the defect class filed as 33. Paired with both diagrams passing all six merge checks, and with every cell of section 5.9.13's accept-and-refuse table driven by `test_ledger_index.py` against the reference payloads printed there. It cannot settle whether the size win holds at real volumes; the `bytes_freed` column the task writes is the reading, and section 4's figures are the prediction it tests.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Two periods, not three and not one.** A single month grain makes a reader fetch 56 days for a 39-day span. A single day grain makes a 90-day span 92 requests and holds about 426 files for a 14-month ledger. Daily plus monthly serves every span the console offers and **bounds the tree at between 62 and 93 files a ledger at the defaults** - 45 to 76 daily files, 13 monthly, two indexes and two watermarks. **No yearly period ships**: at the default `monthly_window` of 13 months the monthly period is already bounded, and the first yearly file could not be written before January 2028 - twenty-seven months with no writer and no reader. It is minted by the plan that needs it | Owner, 2026-09-25, on section 4 |
  | 2 | **A compact file is named for the period it covers**, `daily/2026/09/23.parquet`, not for a minted `file_id`. A compact period has exactly one writer, so a minted name buys no collision safety and costs the browser a computable address. Raw keeps `<file_id>`, which is where the rule earns its keep | Owner, 2026-09-25, overturning the 2026-09-24 ruling that bound the name to every tier |
  | 3 | **A day is eligible when `compact_after_hours` have passed since that day ended**, computed in code against the day's own end instant in UTC. The cron moves to `40 0 * * *` - after the boundary - so the wake time is not an input: every wake in the day returns the same eligible set, and the margin against scheduling drift goes from 36 minutes to 23 hours. At the default 24 the newest eligible day is two days back. **The watermark is what makes a missed run cost nothing**: two missed days produce two files, never one merged file | Owner, 2026-09-26 |
  | 4 | **A re-run of a failed job is absorbed, not guarded against.** GitHub permits one for thirty days and it writes into its original day. The compaction re-lists the one day it is about to take, and a day below the watermark that has raw files again is compacted again from the union. Nothing else re-reads anything | Carmack, 2026-09-25 |
  | 5 | **Data first, watermark last**, in every period. The failure modes are not symmetric: watermark-behind costs one repeated period, watermark-ahead loses data with no error | Fowler |
  | 6 | **A month is absorbed whole or not at all**, and its daily files are deleted in the same commit. A partial month file would put a date in two periods, and the browser's coarsest-period rule would read a month file that does not hold the day it asked for. The price is that the daily period holds `daily_keep_days` to `daily_keep_days + 31` days | Carmack, 2026-09-25 |
  | 7 | **The compaction carries the bound on its own ledgers.** Each period absorbs the one below and drops its own files past its own window, in one pass. A second task windowing `state/compact/` would have to own a root this task already owns, which the disjointness rule forbids | Carmack |
  | 8 | It is the same writer kind as every other task: write the compact file, the index, the watermark and the record, delete what it absorbed, one commit | Fowler, section 5.6 |
  | 9 | **`digest.yml`'s compaction step moves here.** Two schedulers - one in config and one in a workflow step - is what the owner ruled against. `stages/compact.py` becomes this task's body and the assemble step is removed | Owner, 2026-09-24, overturning the earlier scope-out line. A scope boundary is a dated decision, not a law (CLAUDE.md section 0d) |
  | 10 | **`max_periods_per_run` bounds a first run.** Without it, "starts at the watermark plus one" and "one period at a time" are two different programs, and the first ledger published with history either takes one long job or drains one period a day for two months | Carmack, 2026-09-25 |
  | 11 | **`frontend/src/lib/server/payload.ts` is not touched.** A build-time reader walking the compact periods would be a second parquet importer in `frontend/`, which plan 51 forbids. The first reader of a compact period is that plan's query door, at view time | Fowler |
  | 12 | The plan keeps a link, not a copy of the diagrams. Two pictures of one job graph disagree the first time the workflow changes | Guardrail #4 |
  | 13 | **One compaction task a ledger, running both grains in order in one process and landing them in one commit.** An earlier design split daily from monthly and placed them in one shard, daily first, to survive a push race: the two rewrite one file - `state/compact/<ledger>/index/daily.json`, which the daily rewrites at every wake and the monthly rewrites on the roughly twelve days a year it absorbs a month - and split across shards the loser resets to the new tip and re-adds the copy it built before, **dropping every entry its sibling had just written, at exit 0 and invisible in both logs**. A placement key, a rule in the shard planner and an oracle in row 8 were three mechanisms buying back one property the merge gives free. **The merge also deletes `period` as a discriminator and the per-period conditional validator on `CompactionPolicy`** | Carmack, 2026-09-26, overturning his own decision of 2026-09-25 |
  | 14 | **The index is a step of the compaction, not a task.** An index task owning `state/raw/<ledger>/index` beside a compaction owning `state/raw/<ledger>` is one path inside the other, which section 5.2 refuses by name (section 5.3) | Section 5.2's overlap refusal, 2026-09-26 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Compact at day grain only | A 90-day span becomes 92 requests and a 14-month ledger holds about 426 files | Measured, section 4 | Carmack |
  | 2 | Compact at month grain only | A reader fetches 56 days for a 39-day span and the edge month is always over-fetched | Measured, section 4; costs the reader 44 percent | Owner, 2026-09-25 |
  | 3 | Ship a yearly period now | Twenty-seven months with no writer and no reader, plus a keep-window and a monthly-to-yearly gap rule for a period nothing fills | One enum member, one keep-window on `CompactionPolicy` and one gap refusal, later; no new task | Owner, 2026-09-25 |
  | 4 | Skip compaction and accept the footer | At one row per file parquet is seventeen times the CSV | Measured; costs the whole size argument for the format | Carmack |
  | 5 | Leave `idhazh compact` in `digest.yml` | Two schedulers, one of which the gardener config cannot see | Zero; costs the single-decision-tree property this plan exists for | Owner, 2026-09-24 |
  | 6 | Compact into `state/raw/` beside the files it read, as the CSV compaction does today | A reader could not tell a compacted tree from an untouched one by path, and a prune over `raw` would have to know which files are outputs | Zero; costs the property that `raw` holds only writer files | Owner, 2026-09-24 |
  | 7 | Let each producer append its own filename to the day's index | Many writers on one path: the push race and the merge driver both return, and an append is read-modify-write on a shared file | Zero; costs the single-writer property | Owner, 2026-09-25 |
  | 8 | Derive dueness from the newest directory instead of a watermark file | A listing cannot distinguish a period that produced nothing from one never attempted, so a gap is retried every day forever | Zero; costs a task that never settles | Fowler |
  | 9 | One watermark file per ledger carrying both dates | Since decision 13 one task writes both, so there is no race; two files stay because each period's step writes its own mark last (decision 5) | Zero; costs each period's step its own mark | Fowler |
  | 10 | Keep a six-hour late-arrival allowance rather than a whole day | Six hours is a number nobody derived. A whole day states the rule - the day has ended and a further day has passed - and a late arrival is already handled without it, by re-compacting a day below the watermark. The knob still takes six if a measurement ever argues for it | Zero; costs the sentence its meaning | Owner, 2026-09-25 |
  | 11 | Write partial month files and rewrite them as days age in | The monthly period would be current within a day, at 1,649 bytes a rewrite - and a date would sit in two periods for up to 30 days a month | Zero; costs the one-file-per-date invariant | Carmack, 2026-09-25 |
  | 12 | Add the gardener page as a section of `retention.md` | That page answers what is deleted and for how long; the job graph, the commit loop and the record layout are a second question | Zero; costs the page its single question | `docs/reference/documentation-structure.md` |
  | 13 | Have the `plan` job read each period's `watermark.json` and put only the compactions it finds eligible in the matrix | The file is outside that job's checkout, so the read finds nothing and answers "never compacted" at every wake forever. It also answers nothing worth having: at `compact_after_hours: 24` every compaction has a day to take at every wake in steady state | Zero; costs the plan job a cone that grows with every ledger | Owner, 2026-09-26, overturning the 2026-09-24 design. Consistent with rejected alternative 8 above, which this clause had been contradicting |
  | 14 | Fold `through` into `CompactIndex`, since one writer writes both | It would be legal - same writer, same commit - but decision 5 makes "data first, watermark last" an invariant, and one file cannot hold two states. The reason anybody wanted the fold was to save a browser a fetch, and no browser reads a watermark at all now (section 5.3) | Zero; costs the resumable ordering that makes a half-finished period cost one repeat | Fowler, 2026-09-26 |
  | 15 | Give `CompactEntry` a `content_sha256` | `bytes` already lets a reader check `Content-Length` before it parses anything, and the file's own envelope carries the hash for the case that needs certainty. A second hash is a second thing to keep in step with the file it describes | Zero; costs `bytes` the reason it is in the index | Fowler, 2026-09-26 |

---

### Row #8 - `prune.yml` becomes `idhazh-gardener.yml`, and the whole garden is scheduled

- **Scope:** the workflow is renamed for what it now does, splits the registry into shards and runs them with no ordering between tasks; and the GitHub artifacts and runs pruners are scheduled for the first time.

**The rename is the point, not decoration.** `prune.yml` named one job; the file now runs every task the gardener tends, so it becomes `idhazh-gardener.yml`. Three places name it and move with it: `pages.yml`'s upstream-workflow list, `docs/reference/github-actions.md`, and the workflow harness tests. GitHub treats it as a new workflow, so the schedule restarts from the next cron and the old file's run history stays under its old name - stated because somebody will look for it.

**`workflow-artifacts` and `workflow-runs` are tasks, not a separate kind of thing.** The word "collection" survived from when only those two wrote the record; they are ordinary tasks with ordinary declarations, and the record column that used to be called `collection` is now `task` (section 5.1).

**No ESCALATE trigger fires in this row, and trigger 2 is the one somebody will stop on.** That trigger guards the tip-moved refusal in `backend/utilities/push_rewritten_history.py` - its behaviour and its exit code - and this row changes neither. What changes is **which job decides whether the squash runs at all**, which is a dueness gate and not a refusal. Trigger 4 is the one to watch instead: the chain in front of the force push grows by the history job's own dueness read, an estimated 20-30 s, and section 5.9.11 restates the whole chain with that term in it.
- **The shape:**
  - `plan` - depth-1 sparse checkout of `config/` and `backend/utilities/`, runs `python backend/utilities/gardener_shards.py --json` **before any install**, emits `any_active_task`, `shard_count`, `shards` and `matrix` (section 5.9.7). **That cone is the whole of what the reader opens**, and the oracle below is what keeps it true as ledgers are added.
  - `run-tasks` - `needs: plan`, `strategy: {matrix: {include: ...}, fail-fast: false, max-parallel: ${{ fromJSON(needs.plan.outputs.shard_count) }}}`, which is `config/idhazh_gardener.json`'s `shards`, today 5. Each runner sparse-checks out the union of its shard's tasks' cones, installs `.[parquet]`, loops its tasks, and publishes once with row 4's commit loop.
  - `history` - `needs: [plan, run-tasks]`, and **it gates itself**: `fetch-depth: 1`, `python3 backend/utilities/corpus_squash_due.py`, then only on a due day a second `actions/checkout@v6` at `fetch-depth: 0`, `idhazh gardener corpus-squash`, and the force push with the tip-moved refusal. The two-stage shape and its comment carry over from `prune.yml` unchanged, because it is the same job doing the same thing (section 5.3).
- **Files touched:**
  - `.github/workflows/prune.yml` renamed to `.github/workflows/idhazh-gardener.yml` and rewritten
  - `backend/idhazh/gardener/tasks/github_collections.py` (new), `backend/utilities/prune_artifacts.py` (**deleted**; this module is its only home), `config/gardener/workflow-artifacts.json` and `config/gardener/workflow-runs.json` (both `dry_run: true`), `config/idhazh.json` (the `prune.collections` block leaves)
  - `backend/utilities/migrate_csv.py` (**deleted**; row 3 declared its removal condition on the line that created it), `backend/idhazh/contracts/corpus.py` **and `backend/utilities/corpus_squash_due.py`** (the `pruned_date` read-side alias is removed from **both homes in this one commit** - **ESCALATE trigger 1 fires here**)
  - `backend/tests/workflows/test_gardener_workflow.py` (**including the gate this plan was missing: the `plan` job's sparse-checkout cone contains every directory its reader opens, computed from the committed workflow and the committed reader rather than from a hand-written list**), `backend/tests/contracts/test_gardener_plan_matrix.py` (new: the committed matrix expression reads only keys `GardenerPlan` declares, and `gardener_shards.py` writes exactly the keys `ShardPlan` declares), `backend/tests/gardener/tasks/test_github_collections.py` (driven from a recorded response, never the network - Guardrail #7)
  - `docs/reference/github-actions.md`, `docs/architecture/publishing/idhazh-gardener.md`, `docs/architecture/publishing/retention.md`
  - `backend/idhazh/contracts/knobs/gardener.py` and `config/idhazh_gardener.json` (`max_cone_mb`, section 5.2), `backend/idhazh/gardener/runner.py` (the size check right after checkout, and `cone_mb` on every record row, section 5.1), `backend/tests/gardener/test_cone_ceiling.py` (a fixture tree at, just under and just over the ceiling), `docs/concepts/growing-reads.md` (one entry: the `run-tasks` cone, what it reads, how it grows while its tasks are report-only, and the ceiling that stops it growing unseen)
- **Acceptance gates:** local `pytest backend/tests/workflows backend/tests/gardener backend/tests/contracts -q`, `ruff check .`, `mypy backend`, and the workflow file parses as YAML. CI runs the full suite.
  - **Not a gate:** dispatching the workflow. Split per author-a-plan.md - what is decidable from committed files is the harness test; what needs a live runner is the observation below.
  - **Named observation, first scheduled run after merge:** read each `run-tasks` job's log for the tasks it ran and the record path it wrote; confirm one file per shard under `state/raw/gardener/<YYYY>/<MM>/<DD>/` and nothing written outside `state/raw/` or `state/compact/`; confirm no job reports exit 2 or exit 3; confirm the two GitHub tasks report `dry_run` true, `candidates_seen` above zero and `deleted` zero. **Read the five timings section 5.9.11 estimates and restate that row against them**, and compute each shard's push cost from its record's `work_ended_at` against the timestamp of the commit that carries it (section 5.1) - that is the reading decision 11's 4.7-minute estimate is waiting for. Exit 2 means two tasks claimed one path and the registry is wrong - stop and read the path it named. Exit 3 means the push rate is too high for `attempts`; raise `attempts` before lowering `max-parallel`.
- **Oracle:** the set of shards the matrix can produce is exactly a partition of the registry - every task appears in exactly one shard and no shard is empty - and every job id the workflow spells is a `ServerJob` member, asserted over the committed workflow and the committed declarations. **There is no pairing clause here any more**: one compaction a ledger means there is no pair to place, which is what row 7 decision 13 bought by merging rather than by scheduling. **And the `plan` job's sparse-checkout cone contains every directory its reader opens**, both sides computed rather than listed by hand: the cone from the committed workflow, the directories from the committed reader. That last one is the gate this plan did not have, and its absence is what let a reader drift outside its own checkout with nothing going red. **And `fetch-depth: 0` appears in exactly one job of one workflow in this repository - the `history` job's second checkout - and nowhere else**, asserted over every committed workflow file. That job takes a full clone deliberately, because it rewrites every commit; any other job that commits and takes a full history is paying for a clone it does not use, and the rule only survives if something can see it broken. It cannot settle whether five runners pushing at once land; the named observation does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `max-parallel: 5`. Jobs beyond that queue, and a queue is fine | Owner, 2026-09-24. Settled |
  | 2 | **The matrix is five shards of 3-4 tasks, not one job per task.** One job per task means one record row per file, so the per-file charge never amortises: **measured 2026-09-26 with pyarrow 25.0.1, nineteen one-row record files weigh 132.5 KiB where five four-row files carrying the same rows weigh 36.5 KiB** - 3.6 times, and an empty 19-column table with its envelope is already 4,690 bytes before a single row. Each task keeps its own verb, its own declaration and its own `dry_run`; a shard is a container, not a task | Carmack, on section 4, re-measured 2026-09-26. `digest.yml`'s own header already makes this argument: a worker takes a shard of several items rather than one item per machine |
  | 3 | The runner catches per task, writes that task's row with `stopped_because: failed`, continues, and exits with the worst code. `fail-fast: false` protected twelve tasks from one failure when each had a job; sharding buys that back inside the job | Fowler |
  | 4 | `needs: [plan, run-tasks]` on the history job is the only ordering, and it is not one task depending on another: it is everything else being pushed before history is rewritten. **`if: always() && ... (success or skipped)`**, because a skipped `needs` skips the dependant and the force-push job would never run on an idle day. **The `history_due` clause is gone from that expression**: the job reads `corpus/corpus.meta.json` out of its own checkout and decides for itself | Owner, 2026-09-24; the second half Owner, 2026-09-26, overturning the flag |
  | 5 | The workflow names no task. The matrix comes from the declarations the `plan` job reads (section 5.2), so adding a task is a declaration, plus a module only when nothing serves its kind, and never a workflow edit | Owner, 2026-09-24 |
  | 6 | **The header records that a `GITHUB_TOKEN` push triggers no workflow**, and a test asserts the `run-tasks` job uses the default token and sets no personal access token. Five pushes a day that triggered `ci.yml` would be five full CI runs a day; that recursion guard is the only thing between the two outcomes and it is invisible in the file that depends on it | Carmack |
  | 7 | **`pip install -e .[parquet]` on every `run-tasks` shard, and `cache-suffix: parquet`.** Every shard writes its own record through the ledger door (section 5.6), so every shard needs the engine - an earlier draft made the extra a matrix field for the four tasks that read parquet, which missed the record. `setup-python` keys its cache on the OS, the interpreter and the dependency file and **never on the extras**, so without a suffix this workflow and `digest.yml` share one entry whose contents depend on which ran first | Carmack, 2026-09-25 |
  | 8 | The force-push window derivation in `docs/reference/github-actions.md` is restated in this row, with the install time labelled an estimate until the first scheduled run reports it: no measurement is taken beforehand (owner ruling 2026-09-27). The chain in front of the push grows by three things: the plan job, the `run-tasks` wave, and the history job's own dueness read | Carmack. Guardrail #4: the change that makes a sentence false is the change that fixes it |
  | 9 | The two collection tasks ship `dry_run: true`. This is the only new behaviour in the plan, and a first scheduled run of a program nothing has ever scheduled should not delete from a collection outside this repository | Guardrail #10 |
  | 10 | Two collection tasks, not one: `workflow-artifacts` and `workflow-runs` have different retention values today and no reason to run together | Owner, 2026-09-24 |
  | 11 | **There is no `gardener.push_deadline_seconds`, and `attempts` is what bounds the push loop.** `digest.yml` has one pusher; this workflow has five racing one ref, and at `attempts: 5` with the declared full-jitter backoff capped at 8 seconds the loop is bounded near 30 seconds - so a 300-second deadline could never fire, and a knob that cannot change behaviour fails Guardrail #6's substitution test. A load-time refusal binds `attempts` above `shards` instead, which is the condition that actually decides whether the last-placed shard can land | Carmack, 2026-09-26, replacing the 2026-09-25 decision that gave the gardener its own deadline |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | One job per due task | The footer never amortises, and it costs more job start-ups and two more waves in front of the force push | Measured, section 4 | Carmack |
  | 2 | One job running every due task in sequence | One failure takes the rest, and one long-held checkout races every push for its whole duration | Zero; costs the parallelism and the isolation | Owner, 2026-09-24 |
  | 3 | A repository-wide concurrency group over `run-tasks` | Serialises the matrix, which is what the matrix is for | Zero; costs the parallelism | Owner, 2026-09-24 |
  | 4 | Have the `plan` job run `idhazh gardener plan-shards` | It would need `pip install` to print a JSON array, where today the same answer comes from standard-library code before any install | Zero; costs the plan job an install it has never needed | Carmack |
  | 5 | Ship the collection tasks at `dry_run: false` | A first scheduled run deleting from a collection outside this repository, unrecoverably, if the selection is wrong | Zero; costs an unrecoverable deletion | Guardrail #10 |
  | 6 | Merge this row into row 7 | They share four files and cannot parallelise, so it would save one merge cycle - and a compaction defect would then revert the workflow rename and `pages.yml`'s upstream list with it | One merge cycle | Fowler |
  | 7 | Widen the `plan` job's cone to `state/compact` and `corpus` so its reader can open what it needs | Cone mode matches whole directories and has no file form, so this writes every compacted parquet file and `corpus/corpus.jsonl` - the largest committed file here - into a job that reads a few hundred bytes, in a job bounded at `timeout-minutes: 5`. It is also the wrong direction: the reads were deleted, not relocated (section 5.3) | Zero to take; costs the plan job a working tree that grows with the archive, which is Guardrail #12 broken rather than answered | Owner, 2026-09-26 |

---

### Row #9 - The three ledgers the console's routes read become parquet

- **Scope:** `state/item-health/`, `state/scores/` and `state/host-fingerprint/` move through the door, producer and consumer.

**These three are what the console draws, so this is the row that makes a browser query possible at all.** 122 columns, 36 and 31; 220 rows over the eight newest item-health files; 30 host-fingerprint shards a day from `plan`, `work` and `assemble` across five runs.

**Every column is kept.** `UNREAD_CELLS` in `backend/idhazh/contracts/item_health.py` names 39 of item-health's 122 as having no reader on any page today. **They stay recorded**: item quality, feed quality and search quality work is pending and those columns are its input. What they cost is a reader's download, and that is answered by consolidation rather than by deletion - section 4 measures the same 122 columns at 2.6 times smaller than the CSV once a day is one file.

**pyarrow enters `digest.yml`'s hot path here, and this row pays for it.** These three ledgers are written by `plan` (1 job), `work` (4 shards) and `assemble` (1 job) on each of five runs a day - **30 jobs a day**. Row 2 made pyarrow an optional extra to keep it out of those installs; this row gives that back on three job kinds. **No install measurement gates this row: owner ruling 2026-09-27 adopts pyarrow whatever it costs.**
- **Files touched:**
  - `backend/idhazh/stages/assemble.py` and `backend/idhazh/stages/record.py` (the two `item-health` call sites), `backend/idhazh/evals/writer.py` (the `scores` call site), `backend/idhazh/telemetry/silicon.py` (the two `host-fingerprint` call sites. The probe row written when a job starts and the clock row written when it ends become two files, told apart by `producer`: the module's dotted name with `:probe` and `:clock` after it (section 5.9.1). **One `producer` for both would make section 5.7 read the second file as a retry of the first** and drop one half before compaction sees it)
  - `backend/idhazh/ledger/keys.py` (**a cell-merge rule for `HOST_FINGERPRINT_KEY`**. The settle table holds only preferences today, and a preference keeps one whole row; `host-fingerprint` has no entry, so the first row is kept and the other half is dropped. The new rule takes every cell from both rows and reports a cell that both rows set to different values as a defect. `item-health` and `scores` keep the rule the table gives them today)
  - `backend/utilities/migrate_to_parquet.py` (new, one-shot; **its declaring line reads "delete when every `state/item-health`, `state/scores` and `state/host-fingerprint` CSV is gone from `main`"**, and plan 52 carries its deletion in its section titled **What this plan inherits and must close**)
  - `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/eval_row.py`, `backend/idhazh/contracts/host_fingerprint.py` (**no `version` stamp** - no field moves, only the address - **and one `changelog` entry each**, `"Rows move to state/raw/<ledger>/ as parquet; the CSV path is gone"`, because CLAUDE.md section 11 requires an entry for every change and the read-side migration is the module above, shipping in the same commit)

**Four naming corrections ride in this row, and they ride here because the row is already rewriting every one of these rows.** Renaming a column while a migration rewrites the file is free; doing it afterwards is a second migration with its own read-side alias. Owner decision, 2026-09-26.

| # | Today | Becomes | Why |
| --- | --- | --- | --- |
| 1 | `EvalRow.source_word_count` | `source_words` | `ItemHealthRow.source_words` is the same fact under a second spelling |
| 2 | `EvalRow.summary_word_count` | `summary_words` | Same, against `ItemHealthRow.summary_words` |
| 3 | `EvalRow.source_seen_word_count` | `source_words_before_cap` | Same, against `ItemHealthRow.source_words_before_cap`. **The two names also disagree about which end of the cap they mean**, which is worse than a duplicate: a reader cannot tell from either name whether the number is before or after truncation |
| 4 | `EvalRow.attempt` | keeps its name, **gains a description** | It is declared `attempt: int = Field(ge=1)` with no description, so it is undeclared under Guardrail #3. It is set from `summary.attempt` - **which attempt at writing the summary produced the text being scored** - and it is **not** the `attempt` in the ledger's own filename, which is `<run_id>-<attempt>-<job>-<shard>` and carries the GitHub Actions re-run counter. One word, two meanings, one ledger |

**These three renames DO stamp `version` and DO need a read-side alias**, unlike the address change above: a field that changed name is a breaking change (CLAUDE.md section 11), and the alias is a `model_validator(mode="before")` in the same commit, on the pattern `corpus.py` already uses for `pruned_date`.
  - `backend/idhazh/contracts/ledger_name.py` (`LedgerName` gains nothing - `ITEM_HEALTH`, `SCORES` and `HOST_FINGERPRINT` are already members, each with its `config/ledgers.json` entry. **This row's contract change is the arrow mapping and the envelope, not the vocabulary**)
  - `config/ledgers.json` (the `item-health`, `scores` and `host-fingerprint` entries switch to `grain: "raw-and-compact"`, section 2)
  - `config/gardener/compact-item-health.json`, `config/gardener/compact-scores.json` and `config/gardener/compact-host-fingerprint.json` (one compaction a ledger, section 5.9.5), and `config/gardener/host-fingerprint.json` set to `lifecycle_status: retired`: this row moves the only tree that task owns, and its declaration stays so section 5.2 can read its `window` as the ledger's floor. `scores.json` and `telemetry-aggregate.json` stay `active`, because each still owns a tree this row does not move
  - `backend/idhazh/ledger/__init__.py`, `backend/idhazh/day_shards.py` (the read side for these three moves to `ledger/settle.py`)
  - `frontend/src/lib/server/host-fingerprint.ts`, `frontend/src/lib/server/machine-counters.ts`, `frontend/src/lib/server/model-work.ts` (the three readers move onto `sliceFromDisk()`, which plan 51 builds - see the settled escalation below)
  - `frontend/src/lib/server/payload.ts` (`mergedDayShards` is deleted once `host-fingerprint.ts` and `machine-counters.ts` leave CSV, if nothing else calls it; plan 51's row titled **The Hardware route stops counting every job twice** adds it for the CSV reader only)
  - `.github/workflows/digest.yml` (`plan`, `work` and `assemble` install `.[parquet]`)
  - `backend/tests/ledger/test_migrate_to_parquet.py`, `backend/tests/test_ledger.py`, `backend/tests/telemetry/`, `frontend/tests/`
- **The escalation, settled 2026-09-26. It is no longer a blocker, and it needs no new module.** Three build-time readers under `frontend/src/lib/server/` open these ledgers as CSV: `host-fingerprint.ts` reads `host-fingerprint`, `machine-counters.ts` reads both `host-fingerprint` and `item-health`, and `model-work.ts` reads `scores`. **Measured 2026-09-26 by the `state/` paths each module actually opens** - an earlier count said four and then seven, and both were grep artefacts: `payload.ts` reads `day-metrics` and `feed-health` and touches none of these, `run-timeline.ts` opens no `state/` path at all, and `similarity-ledger.ts` matched only because it names `host-fingerprint.ts` in a comment.

  **The engine already in the plan is the answer.** Plan 51 installs `@duckdb/duckdb-wasm` behind one module, `frontend/src/lib/data/engine.ts`, and `frontend/src/lib/data/ledger.ts` is the public door in front of it. **duckdb-wasm runs in node**, so a build-time read needs no second engine and no second reader. A draft of this section proposed `frontend/src/lib/server/parquet.ts` and that was wrong twice over: it would have been a second parquet reader where one already exists, and **it would have broken plan 51's rule that `engine.ts` is the only module in `frontend/` that imports the engine**.

  **What is needed is a second entry point, and plan 51 builds it.** The browser's entry point joins `visuals.asset_base_url` and fetches an address; a build-time read wants a local path under `state/`. Same engine, same query, different source. Plan 51's row titled **The query door module and its two entry points** builds both - `slice()` for the browser and `sliceFromDisk(stateDir, ledger, opts)` for a build-time reader - and the engine's Node set-up in `engine.ts`. This row only moves the three readers onto `sliceFromDisk()`, and the single-engine rule stays true with one importer. **`sliceFromDisk()` reads compacted files only**, so the pages these three readers feed show data up to the newest compacted day, not today (section 5.9.4).

  **The cost is an ordering constraint and it is the only thing this settles.** `sliceFromDisk()` is built by plan 51's row titled **The query door module and its two entry points**, so **this row cannot merge before that module exists** - and that ordering is in this row's `Depends-on` cell rather than in prose, because the dispatcher reads the cell. That row depends on plan 51's row titled **The chart vocabulary and the house style, with no panel moved** and on this plan's row titled **One compaction task a ledger, two compact periods, and the diagrams move into the page**. **An earlier draft pointed at plan 51's row titled One panel end to end: the browser fetches the ledger and draws it in d3, which produced a cycle**: that row waits on plan 51's publishing row, which waited on this one. That is recorded in plan 51's dependent-plans section as well, because a constraint written on one side only is a constraint somebody discovers.

  | # | Rejected | Why | What it would cost |
  | --- | --- | --- | --- |
  | 1 | A separate build-time parquet reader | Two modules importing one engine, which breaks plan 51's rule that `engine.ts` is the only importer on the day it lands | A module, and a gate |
  | 2 | Dual-write CSV for one release | Two writers of one fact, and **"one release" is a promise nothing enforces**. The same defect Fowler rejected in row 2's alternative 3, bounded only by an intention | Double the bytes for the three largest ledgers, for as long as somebody forgets |
  | 3 | Hold each reader until its route moves to the browser | **It breaks plan 51's row titled The three ledgers the console reads are published**, which needs these ledgers migrated to parquet. It inverts the dependency and parks rows 9 and 10 behind seventeen pull requests | Zero code; costs the whole console workstream its ordering |
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/ledger backend/tests/telemetry backend/tests/workflows -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks, and the browser smoke on every console route. CI runs the full suite.
- **Oracle:** **migration parity, per ledger.** Every row in each committed CSV tree reads back from the parquet the migration wrote, field for field, no row lost and none invented, and **the column set is identical** - 122, 36 and 31, with `UNREAD_CELLS` still naming 39 of the first. **A compacted `host-fingerprint` day holds one row per record key**, carrying the probe row's cells and the clock row's cells, and a cell both set to different values is reported as a defect. It cannot settle whether the browser can query them; plan 51 does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Three ledgers in one row, because they share one reader surface and one escalation.** All three are opened by build-time readers under `frontend/src/lib/server/`, and the answer to that escalation is one answer for all three - splitting them would take the same Level 5 decision three times | Fowler |
  | 2 | **Every column is kept.** 39 of item-health's 122 have no reader on a page today; they are the input to work that has not started. A reader's download is answered by consolidation, not by deletion | Owner, 2026-09-26 |
  | 3 | This row waits on the compaction task, not on the door. Per-writer parquet with nothing to consolidate it is 15.1 times the CSV it replaces | Carmack, section 4 |
  | 4 | `digest.yml` gains `[parquet]` on three job kinds and no others. The remaining jobs never touch the format | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Drop the 39 unread columns while migrating | It saves 29 percent of the published file and throws away the input to the item, feed and search quality work | Zero to take, and it costs a workstream | Owner, 2026-09-26 |
  | 2 | Migrate `host-fingerprint` in plan 51 instead | Three call sites in one file across two plans, so the two collide on `work.py` and neither can run beside the other | Zero; costs the parallelism | Fowler |
  | 3 | Keep a CSV copy for the build-time readers indefinitely | Two writers of one fact, and the CSV is the format this workstream exists to retire | Zero; costs the single-writer rule | Fowler |

---

### Row #10 - COLLAPSED - `span-rollup` becomes parquet

**This row is collapsed and there is nothing here to execute.** `state/span-rollup/` is being deleted rather than migrated, so the migration has no beneficiary. The deletion is a different outcome with a different risk class - a one-way removal of a ledger with five live readers and one published projection - and it goes to [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md)'s row for the last console route to move, beside the `span-rollup` projection that row already deletes (that plan's section titled **The shape this plan is expected to take**). Nothing in this plan or in plan 51 waits on it; leaving the ledger in place costs one duplicated write, which is what happens today.

**Everything below this line is the evidence for that ruling, not an instruction.** The `Scope`, `Files touched`, `Acceptance gates` and `Oracle` blocks describe the migration that is not happening, and they are kept only until the plan 52 row that deletes the ledger carries the measurements across.

> **HELD, 2026-09-26. Do not start this row.** Susan was asked twice. The first brief was wrong - it offered her only the shard-grain fold and asked about a panel. The second gave her `state/traces/` and asked about a query surface. **Both rulings say delete, and the second says it for a better reason.**
>
> **The granular data already exists and nobody built it.** `state/traces/` is 177 files and 14,933,006 bytes - **24.3 percent of everything under `state/`** - holding ten span names at per-item grain with parent chains, durations and attributes. `span-rollup` is a fold of five of them to shard grain. Nothing in this repository reads a trace: only `retention.py` (to delete them), `paths.py`, one migration utility and three test files name the path.
>
> **Seven of the ten spans already have a per-item column on the item-health row**, filled on 2026-09-25: `item`/`item_total_ms` 800 of 800, `fetch`/`fetch_ms` 800 of 800, `robots`/`robots_ms` 800 of 800, `extract`/`extract_ms` 800 of 800, `summarize`/`summarize_ms`+`model_wait_ms` 742 of 800, `model_call`/`prefill_ms`+`decode_ms` 734 of 800, `visual_planner`/`visual_plan_ms` 426 of 800. `score` is on the eval row. **Only `tag`, `render_prompt` and `parse_reply` have no column, and across a whole day of 800 items they total 5,887 ms - 0.0034 percent of a day's item time.**
>
> **An operator can already answer "why was this item slow", and the trace adds nothing.** Worked on the slowest item of 2026-09-25, `energy-ej2ghj5hgv1nwkhp` at 1,326,769 ms - 22.1 minutes. Its item-health row: `fetch_ms` 450, `robots_ms` 169, `extract_ms` 78, `stage_gap_ms` 5, `summarize_ms` 1,326,236, `model_wait_ms` 1,326,236, `queue_wait_ms` 7,447,233. **Six columns in one row explain it to within rounding.** The trace splits `summarize` one level finer and attributes 1,326,214 ms to a single `model_call`, which `model_wait_ms` had already said.
>
> **The `robots` finding is the one that settles it.** `robots_ms` is filled on 800 of 800 item rows for 2026-09-25 while **the `robots` span produced zero rows in all twenty trace files of that same day**, and the rollup has written zero `robots` rows in 700. The column outlived the span. `SpanRollupRow`'s own docstring says "the row exists to hold what no ledger already holds" - **two of its five names are now a second account of a number a ledger keeps at finer grain**, which is exactly what it says it refuses to be.
>
> **The disjointness test is structurally blind and that is why none of this was caught.** `backend/tests/contracts/test_span_rollup.py` compares the strings `count`, `total_ms` and `unattributed_ms` against every ledger's column names. Because the rollup names its measurement generically it can never collide with anything, so the test is green while two spans are duplicated. **A test that compares column names cannot see a semantic duplicate.**
>
> **Susan's ruling, 2026-09-26, second pass.** DELETE `state/span-rollup/` and `SpanRollupRow`. REFUSE `tag_ms`, `render_prompt_ms`, `parse_reply_ms` as item-health columns - 5,887 ms a day does not earn three headings on every row forever. REFUSE a per-item span ledger - 8,000 rows a day to carry that same 5,887 ms. KEEP `state/traces/` at its 7-day window, unpublished; it is the right home with the right window and no reader. `unattributed_ms` is a cell on the row being deleted, so it goes with the row and needs no separate investigation.
>
> **What is missing is a tool, not a dataset.** Susan's NEW: `idhazh telemetry item <item_id> --date <d>`, a sixth subcommand beside `rollup`, `census` and `show`. It prints one item's row from item-health and, where the day is inside the 7-day window, its span tree from the one trace file. Bounded to one item and one file (Guardrail #12). No new ledger, no new column, no new contract, no published byte. **The join key already exists**: `trace_id` is `<run_id>-<item_id>`, which is `ITEM_HEALTH_KEY` minus the date the path already carries.
>
> **One wrinkle a tool author must know:** an item produces **two** `item` spans per shard, one for the fetch-and-extract pass and one for the summarize pass, sharing a `trace_id`. A tool that sums `item` spans double-counts.
>
> **`/console/query` does not exist and nobody has proposed it.** Plan 51's "query door" is a module a panel calls, not a box an operator types into. A query page is a new reader-facing surface with its own injection surface and its own byte cost: **its own plan, not 50, 51 or 52.** And it would not change gate 7 - an unsaved query notices nothing, so it is not a reader; **a saved, named, committed query is**, because it breaks visibly when a column goes.
>
> **What the reader loses, named (CLAUDE.md section 14):** the only record of `tag`, `render_prompt` and `parse_reply` that survives past 7 days. After the delete an operator who suspects `render_prompt` has regressed has a 7-day horizon of raw traces and no longer baseline.
>
> **Two retention defects found on the way, and they belong in `20260823-known-defects-plan.md` rather than here.** Twelve day directories sit on disk against a `observability.trace_window_days: 7` window - 09-15 to 09-18 are 52 files and 4,386,597 bytes past it. And **eight files the pruner can never see**: they sit at `state/traces/2026/09/` in the pre-2026-09-18 flat shape, and `trace_date` needs four path parts below the traces root where these give three, so it returns `None` and the file is left alone. 687,103 bytes, unprunable by the current code.

- **Scope:** `state/span-rollup/` moves through the door, producer and consumer. Eight columns, one writer, two build-time console readers and three backend readers.

**It is the fourth and last ledger the console reads.** Narrow and written by one call site, so it is the cheapest of the four.
- **Files touched:**
  - `backend/idhazh/stages/work.py` (the one `write_segment` call for `SPAN_ROLLUP` moves to `persist()`), `backend/idhazh/telemetry/publish/span_rollup.py` (the read side), `backend/idhazh/contracts/span_rollup.py` (**no `version` stamp**, one `changelog` entry)
  - `backend/idhazh/stages/validate_days.py`, `backend/idhazh/telemetry/inventory.py` (two more backend readers)
  - `frontend/src/lib/server/span-rollup.ts`, `frontend/src/lib/server/run-timeline.ts`
  - `backend/utilities/migrate_span_rollup.py` (new, one-shot; **its declaring line reads "delete when every `state/span-rollup` CSV is gone from `main`"**)
  - `backend/idhazh/contracts/ledger_name.py` (`LedgerName` gains nothing - `SPAN_ROLLUP` is already a member), `backend/idhazh/contracts/__init__.py`, `backend/idhazh/ledger/__init__.py` and `backend/idhazh/day_shards.py` (the write and read sides it leaves)
  - `config/gardener/compact-span-rollup.json`
  - `frontend/src/lib/server/span-rollup.ts`
  - `backend/tests/ledger/test_migrate_span_rollup.py`, `backend/tests/telemetry/test_span_rollup.py`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/ledger backend/tests/telemetry -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks. CI runs the full suite.
- **Oracle:** migration parity - every committed span-rollup row reads back from the parquet, field for field. It cannot settle whether the timeline panel still draws; plan 51's successor does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Its own row, not folded into row 9. A different call site writes it, so the revert surface is separate - but the two share `contracts/file_envelope.py`, `contracts/__init__.py`, `ledger/__init__.py` and `day_shards.py`, so they run in sequence | Fowler |
  | 2 | Eight columns means the fixed cost dominates at any row count, so this ledger gains most from the monthly period and least from the daily one. Its declaration says so | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave it CSV because it is small | It is one of the four ledgers the console reads, and one CSV reader left standing keeps a second grammar alive in the query door | Zero; costs the door its single format | Fowler |
  | 2 | Merge it into `item-health` | Different grain - a span is per run and per stage, an item-health row is per item. Merging would repeat every span row once per item. **And measured 2026-09-25, two ledgers in one file save 24 bytes against two files**, so there is no size argument either | Carmack |

### Row #11 - The index and watermark shapes are declared

- **Scope:** the four shapes section 5.9.13 specifies - `RawDayIndex`, `CompactEntry`, `CompactIndex` and `Watermark` - declared in `backend/idhazh/contracts/ledger_index.py` with their three validators, every case in section 5.9.13's accept-and-refuse table, and one sample for each of the three shapes that is a file. **Nothing writes or reads them yet**: row 7 writes them, and plan 51's query door reads `CompactEntry` and `CompactIndex` through a hand-written copy.

**Why the shapes land before the compaction that writes them.** Plan 51's row titled **The query door module and its two entry points** binds its copy of two of these shapes to the models here, and it needs nothing else from this plan. Left in row 7, the door would wait for rows 4, 3, 5 and 7 to merge, and this plan's row 9 waits on the door. Declared here, the door can start as soon as plan 51's own row 4 lands. Guardrail #3 asks for a contract before the logic that writes it in any case. Plan 51's owner asked for the move on 2026-09-27.

- **Files touched:**
  - `backend/idhazh/contracts/ledger_index.py` (new: the four shapes and their three validators, per section 5.9.13. Every type they use is on main: `PeriodStamp` and `FileIdName` in `base.py`, `Period` in `file_envelope.py`, `LedgerName` in `ledger_name.py`)
  - `backend/idhazh/contracts/__init__.py` (`RawDayIndex`, `CompactIndex` and `Watermark` join `CONTRACTS` and `__all__` under the stems `raw-day-index`, `compact-index` and `watermark`. `CompactEntry` is a `Model` and joins `__all__` only)
  - `backend/tests/contracts/test_ledger_index.py` (new: every cell of section 5.9.13's accept-and-refuse table, each case built inside its test)
  - `tests/fixtures/contracts/raw-day-index/`, `tests/fixtures/contracts/compact-index/` and `tests/fixtures/contracts/watermark/` (new directories that no other row in either plan touches: the samples. **`backend/tests/contracts/test_schema_drift.py` saves every sample back and compares bytes**, and the payloads printed in section 5.9.13 do not list their keys in the order the model writes them, so each sample is written through the model rather than pasted)
  - `TODO/20260924-50-idhazh-gardener-plan.md` (this row's Reckoner line)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** every accept case loads; every refuse case raises, with the ledger and the period or date in its message; every sample round-trips byte for byte through `test_schema_drift.py`. **One bite, shown red and then restored:** swap two names in the populated raw-day sample's `files`, and the validator refuses it by ledger and date. It cannot settle whether these shapes serve the compaction well; row 7 settles that by writing them.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A new row, not a second pull request for row 2.** Row 2 merged as #1131, and one row is one pull request. Reopening it would put a finished row back in flight ahead of rows 3 and 4, and plan 51 would read row 2 as DONE while the shapes were still missing | Fowler and Carmack, 2026-09-27 |
  | 2 | **Not folded into row 4.** Row 4 is the largest row in the plan. A defect in these shapes there would hold rows 3, 5 and 6 and plan 51's door, and reverting row 4 would take away shapes plan 51's test reads | Fowler and Carmack, 2026-09-27 |
  | 3 | **No docs page in this row.** Each field's description says what the field means. Row 7's page, `docs/architecture/publishing/idhazh-gardener.md`, explains the index and the watermark once something writes them | Plan owner, 2026-09-27 |
  | 4 | **`backend/tests/workflows/test_ledger_staging.py` stays green.** It asks every ledger for a writer, and this row adds shapes, not a ledger | Fowler, 2026-09-27 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the shapes in row 7 | Plan 51's door, and this plan's row 9 after it, would wait for four more merges | Zero; costs the door four merges of waiting | Fowler and Carmack |

---

### Row #12 - The closed-day fold of the CSV day trees moves into the gardener

- **Scope:** row 7 decision 9, for the trees row 7 cannot reach (deviation 96). `backend/idhazh/stages/compact.py` folds every closed day of each CSV day tree in `DAY_TREES` into one `settled.csv` and deletes the writer files it read. Its only production caller is `digest.yml`'s step `Fold the days that can gain no more rows`. This row makes a gardener task do that fold, and removes the step, `run.settled_fold_after_days` and the stage in the same change. **When it lands, one rule in `config/gardener/` decides when a day is closed**, for CSV and parquet alike.

**Why it is its own row.** Row 7 compacts parquet ledgers under `state/raw/`, and none of these trees is there. They stay CSV (Hard scope - out), and ESCALATE trigger 3 stops any migration beyond the six named. Row 9 may move `item-health`, `scores` and `host-fingerprint` first, and plan 52 deletes `span-rollup`, so the trees this row folds are the ones still in `DAY_TREES` when it is dispatched.

**The design question, settled at dispatch by Fowler and Carmack: which task folds each tree.** Two facts bound the answer. Each tree already belongs to one retention task - `feed-health`, `host-fingerprint`, `counterfactual-scores`, `scores` (with `score-index`) and `telemetry-aggregate` (`item-health`) - while `span-rollup` and `candidate-models` fall under the `trials` complement, and `_refuse_overlapping_claims` refuses a second owner. And each of those tasks ships `dry_run: true`, which writes nothing, while the fold runs live today: a fold placed inside them would stop until a person turns on a deletion window. `corpus-squash` is the one precedent for a live task: `LIVE_BY_DECISION` in `backend/tests/contracts/test_gardener_config.py` names it because it copied a job that already ran live.

- **Files touched (expected; the dispatch check confirms them):**
  - `.github/workflows/digest.yml` (the step and its commit step), `backend/idhazh/stages/compact.py`, `backend/idhazh/cli.py` (the `compact` verb; `measure.yml`'s `runtime` job and `validate.yml`'s `decide` job still call it with `--config backend/var/candidate-config`, so its removal condition is that neither does)
  - `config/idhazh.json`, `backend/idhazh/contracts/knobs/run.py`, `backend/idhazh/contracts/knobs/removed.py`
  - the task module and the declaration that fold, under `backend/idhazh/gardener/tasks/` and `config/gardener/`
  - `backend/tests/pipeline/test_compact.py`, `backend/tests/workflows/test_closed_day_fold_push.py`, `backend/tests/conftest.py`, `backend/tests/contracts/test_gardener_config.py`
  - `docs/concepts/growing-reads.md`, `docs/architecture/publishing/idhazh-gardener.md`, `docs/reference/github-actions.md`
  - `TODO/20260924-50-idhazh-gardener-plan.md` (this row's Reckoner line)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/pipeline backend/tests/contracts backend/tests/workflows`. CI runs the full suite.
- **Oracle:** **the fold changes no answer**: over a fixture tree, `day_shards.settled_rows` reads the same rows for every day before and after the task runs, and a day that is still open is never touched. After the merge, no workflow step runs `idhazh compact` against the committed `state/`.
- **Merge window:** it edits `digest.yml`, so it merges only while no digest run is queued or running (deviations 52 and 54).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The fold never pauses.** The step leaves `digest.yml` in the same change that makes a gardener task fold, and that task folds on its first wake. Stopping it leaves about 128 extra files a day (deviation 96) | Fowler and Carmack, 2026-09-28 |
  | 2 | **Not in row 7 and not in row 8.** Row 7 would roughly double and the fold would stop from its merge to row 8's; row 8 already carries the workflow rename and ESCALATE trigger 1 | Fowler and Carmack, 2026-09-28 |
  | 3 | **The task that owns each tree folds it, and the fold has its own switch.** `RetentionPolicy` gains a `fold` block with its own whole-day `after_days` and its own `dry_run`. The window keeps `dry_run: true`; the fold ships `dry_run: false`, and `LIVE_BY_DECISION` names it because it copies a fold that already runs live. `span-rollup` gets a retention declaration whose window is forever and whose only live action is the fold. One job writes each tree per wake, no tree is checked out twice, and no flag records a deletion as a dry run | Fowler and Carmack, 2026-09-28, second round. Fowler had ruled a fifth task kind, which puts five of six folds in a different shard from their tree; Carmack had ruled the owner's task with one switch, which records a deletion as a dry run |
  | 4 | **The fold's answer rides on the task's existing record row**, as new optional fields - the fold's own `dry_run` and its own counts - left empty when the task does not fold. `dry_run`, `deleted` and `bytes_freed` keep describing the window. Not a second row: the record keeps one row per day, run and task. The record contract takes a version stamp and a changelog entry | Fowler, 2026-09-28 |
  | 5 | **The runner lands the fold's changes on the fold's own switch.** Today it stages a task's files only when that task's one `dry_run` is off, and `retention_files` reads the same switch, so a live fold inside a dry task would change the disk and stage nothing, at exit 0. The window runs first, and the fold skips any day the window deletes, because a shard refuses a path it both wrote and deleted. Test: one shard through `run_and_land` against a real git remote, window dry and fold live; main then holds the day's `settled.csv`, none of that day's writer files, and every file the window only reported | Carmack and Fowler, 2026-09-28 |
  | 6 | **A day is closed one whole day after it ends**, read through `schedule.is_eligible`, the same rule and default as `compact_after_days`. Of 755 writer files filed from 2026-09-22 to 28, the latest landed 0.9 hours after its day ended and none after 24 hours; a later re-run costs one more fold of that day, never a row. The first wake folds about six days - about 770 files and 11 MB - at 1 to 2 seconds a day | Fowler and Carmack, 2026-09-28; the readings are Carmack's |
  | 7 | **The `compact` verb and both trial-root fold steps go in this row**: `measure.yml`'s "Fold the machine record into its day" and `validate.yml`'s "Fold the verdict into its day". A fold changes no answer, and the trial root holds two files under 1 KB. Both workflows run only when a person starts them. `digest.yml`'s "Commit the folded telemetry" leaves with the fold step, and the rebuild step's `if:` drops `steps.commit_fold.outputs.rebased` | Fowler and Carmack, 2026-09-28 |

**What the dispatch debate added to the file list.** `backend/idhazh/contracts/knobs/gardener.py`, `backend/idhazh/gardener/runner.py`, `backend/idhazh/gardener/retention_files.py`, the record contract (section 5.1), the five task modules and six declarations that fold, `.github/workflows/measure.yml`, `.github/workflows/validate.yml`, and the comments in `frontend/src/lib/server/payload.ts` that quote the old knob. Grep for `stages.compact`, `stage_compact`, `idhazh compact`, `CLOSED_DAY_FOLD`, `folded telemetry` and `settled_fold_after_days`: about nine test modules, four code comments and seven docs pages name one of them. **Keep the bench test that a fold of one state root never reaches the other**, because the trial root sits inside `state/`. No `candidate-models` tree is committed today.

---

## Open questions for a person, from row 8

Row 8 shipped each of these as the plan wrote it. None blocks a row; each needs a person, because it changes an owner's ruling, a trigger's subject or a growing read.

1. **The history job's start condition.** It runs only when every `run-tasks` shard succeeded or none ran (row 8 decision 4). So one red shard skips that day's squash, which is then due again at the next wake, while a failed `plan` job does not skip it. Row 8's worker proposes `if: ${{ !cancelled() }}`: the squash would then run on a day a shard is red, and the red shard's work is retried at the next wake either way. Changing it overturns an owner ruling of 2026-09-24 and 2026-09-26.
2. **The gap between the tip check and the force push** (ESCALATE trigger 2). `corpus_history.py` reads origin's tip, then pushes with `--force`; a commit landing between the two is lost. `--force-with-lease=refs/heads/main:<tip>` would make GitHub refuse the push instead. Any change here is trigger 2.
3. **The `run-tasks` checkout is a growing read** (Guardrail #12). Each shard checks out the folders its tasks own, and those grow with what the repository keeps while every task is report-only: the heaviest shard holds 46.3 MB today and grows about 1.4 MB a day. Section 5.6 said it stops growing once its tasks run live; for this shard that is false for about a year. `max_cone_mb: 768` turns a shard red before it grows unseen, and `docs/concepts/growing-reads.md` records the read. A person approves it or names the bound.

## Dependent plans

- `TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md`. Its row titled **The three ledgers the console reads are published** waits on this plan's rows titled **One compaction task a ledger, two compact periods, and the diagrams move into the page** and **The three ledgers the console's routes read become parquet**. Its row titled **The query door module and its two entry points** waits on this plan's row titled **The index and watermark shapes are declared**, and this plan's row 9 waits on that door. Row 11 depends only on row 2, so the chain has no cycle. Nothing else in this plan is a predecessor there.
- **[`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md), a placeholder and not yet a plan.** One row per console route. Each row moves that route's panels to the query door, and **each row's scope line ends with the projection under `frontend/public/` it deletes**: `/console/machine` deletes `machine`, the model route deletes `telemetry`, and the last route out deletes `day-metrics`, `run-days`, `run-timeline` and `span-rollup`. About 4.1 MB leaves the published site and six directories go. `console/band.json` stays - it is the freshness header every route fetches first, not a projection. **A route is not done while the projection it fed survives.**
- **Susan rules every chart on that plan again, from scratch** (CLAUDE.md section 14). The charts on those routes were drawn against what a build-time projection could carry - twenty columns in the machine projection's case, aggregated per shard before any page saw them. A browser that can query the ledger can ask questions the projection could not answer, so **the existing chart is evidence of an old limit rather than a decision to preserve**. Her mandate on each route is what the data now allows, not what it used to show.
- `TODO/20260905-13-switch-on-deletion-plan.md`, row titled "The fuse comes out, and one run is watched": its subject moves from the `--dry-run` flag on `digest.yml`'s assemble step to `config/gardener/visual-prune.json`'s `dry_run`. That plan is updated after this one delivers, per the owner, 2026-09-24.

## Open questions, handed to plan 52

**Three of these are now measured rather than open, and one is new.** What is left is a ruling, not a survey.

### `scores` is named for nothing, and it duplicates nine facts item-health already holds

**Measured 2026-09-26.** `EvalRow` is 35 data columns; `ItemHealthRow` is 122. Nine facts appear on both:

| On `scores` | On `item-health` | Note |
| --- | --- | --- |
| `date`, `run_id`, `item_id`, `url_key`, `vertical`, `model_id` | same six | Identity. A join needs some of these, so not all six are waste |
| `source_word_count` | `source_words` | **Two spellings of one fact** |
| `summary_word_count` | `summary_words` | **Two spellings of one fact** |
| `source_seen_word_count` | `source_words_before_cap` | **Two spellings of one fact**, and the names disagree about which end of the cap they name |

**The name says nothing about what is scored.** Every column is about one summary of one item - `hhem`, `compression`, `extractiveness`, `verbatim_run`, `coherence`, `semantic_coverage`, `band`. There is no `feed_id` and no `endpoint_key`, so the earlier worry that it might be scoring the feed is answered: it is not. The name is not wrong, it is empty. **`summary-quality` says what it holds**, and it is also what a content-quality judge would ask for by name.

**Merging the row into item-health is the part that does not follow, and the reason is the key rather than the writer.** The two ledgers are keyed differently and it is not a detail:

| Ledger | Key | One row per |
| --- | --- | --- |
| `item-health` | `(date, run_id, item_id)` | **one planned item on one run** |
| `scores` | `(url_key, output_digest, scorer_version)` | **one summary text, scored once** |

`output_digest` is the SHA-256 of the summary the model wrote. So a scores row is addressed by **the text itself**, not by the item-run that produced it. Summarise the same URL again and get the same text and there is still one row; change the scorer and there is a new one. **Folding it onto an item-run key would write a score row per item per run whether or not the text changed - which is exactly the duplicate `OBSERVATION_KEY` exists to remove.**

**And `attempt` on a scores row is not the `attempt` in its own filename.** The segment file is `<run_id>-<attempt>-<job>-<shard>.csv`, where that `attempt` is the GitHub Actions re-run counter. The `attempt` **column** is set from `summary.attempt` - which attempt at *writing the summary* produced the text being scored. **The field carries no description at all**, which makes it undeclared under Guardrail #3, and one word meaning two things in one ledger is the defect to fix first, before any rename.

**Fixing the three double-spellings costs nothing and gets most of the benefit.** The merge does not.

**What is needed to decide the widening.** A content-quality judge does not exist yet, so nobody can say which columns it wants. The cheap move is to name the judge's inputs first and widen once, rather than widen twice.

### `frontend/src/lib/server/similarity-ledger.ts` is a second name for a ledger that already has one

**Measured 2026-09-26: it opens `state/content-similarity-judge/fitted-thresholds/` and `state/content-similarity-judge/score-distribution.json`, and nothing else.** So it is the content-similarity-judge reader, named for neither the judge nor the ledger. `similarity-ledger` is the kind of second name CLAUDE.md section 0b deletes rather than replaces, and a reader looking for the judge's build-time reader will not find it under this name.

**Its location is correct and is not the defect.** `$lib/server/` is what stops SvelteKit bundling a build-time read into a browser payload, which is the same reason `host-fingerprint.ts` sits there. It moves to the browser when plan 52 moves `/console/judgement`, and not before. **The rename is a one-file change with no owner yet**: it was handed to plan 53, and that plan closed on 2026-09-27 without taking it. Its sibling `similarity-holdout.ts` reads `holdout-pairs` and `merge-line-holdout-scores` from the same tree and has the same problem.

### The two that stay open

- **Does `span-rollup` survive at all?** Settled: it does not. Row 10 is collapsed and carries the measurements and Susan's two rulings; the deletion is plan 52's to do, not a migration's.
- **Does `scores` become `summary-quality`?** A directory rename is a data migration, so it is the owner's call rather than a tidy.
