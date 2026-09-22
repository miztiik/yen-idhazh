# No file has two writers

**Last Updated**: 2026-09-22
**Level**: 5 (row 11 moves a persisted contract and migrates committed data; every other row is named at its own level in section 1)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A run that finishes its work and cannot commit it publishes nothing. 7 of the last 49 completed digest runs died at a push step, and the owner wants content refresh to run in parallel with no lock anywhere. |
| Hard scope - in | Every committed path a production stage writes gets exactly one writer. The fold that rewrites a shared head is deleted. The push loop converges at any commit rate. The published day becomes a fold of per-run fragments. The reader is never shown a clock that goes backwards. The concurrency group is removed last. |
| Hard scope - out | Table A below. |
| ESCALATE triggers | (1) Row 11 before a person has named the quiet window to merge it in. (2) Any row that would add a lock, a claims file, a parked branch or a serialized single-writer workflow. (3) Any row that would raise the 6 h job kill or the 1 GB Pages cap rather than fit inside them. (4) Row 4's measurement showing `rebuild_ms` is a small fraction of `window_ms` - that overturns row 9's cost argument and the owner re-rules it. (5) A new `## Design rationale` that changes a persisted contract beyond the four stems named in section 0e. |
| Chosen strategy | Partition by writer identity in the filename, settle at read time, fold a closed day once. Ruled by Fowler (architecture and persisted contracts) and Carmack (file count, push window, runner budget) in debate, 2026-09-22; the published surface ruled by Jony. |
| Execution | autonomous orchestrator per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md). Parallel N = 4. |

### Table A - Hard scope, out

| id | What is out | What it costs to leave it out | What would bring it in |
| --- | --- | --- | --- |
| A1 | Two simultaneous passes over the same feeds | Nothing today. The item ceiling binds rather than supply - about 10,000 addresses considered, about 300 published - so two runs on one feed snapshot with the same deterministic ranking take the same top 80. | A non-deterministic ranking, or a claim ledger the `plan` job can read. Both are new contracts and neither is cheap. |
| A2 | The work shard's 190.6-of-200-minute timeout | A shard that crosses 200 minutes loses its own rows. The commit contract does not change that either way. | Nothing here. It is a model-workload problem with its own plan. The commit contract is correct or wrong at a shard length of 5 minutes and at 500. |
| A3 | Telling the reader a day is broken, never ran, or was quiet | The reader cannot tell a broken digest from a quiet one, and a missing day reads like their own typo. Measured: 48 of 65 scheduled slots became runs over 2026-09-09 to 2026-09-21, and 2026-09-19 published nothing. | Its own plan. It needs the cron schedule published as a fact a page can compare against, `run.json` read at build time, and a new empty state. Section 0f lists the four things this plan must not do, or that plan gets harder. |
| A4 | Deleting `introduced_by_run` from `DigestView` | Nothing. Row 10 gives it a renderer, so it stops being dead weight and the question closes. | It is closed. Do not reopen it. |
| A5 | A story that vanishes between loads because the duplicate pass folded it behind another | The reader wonders whether they imagined it. `DigestVerticalRef` already counts a folded story, so no number moves. | A duplicate-pass plan. It is not a fold question. |
| A6 | Moving the console's prerendered reads onto the committed projection | 896 file opens per build today and 3,136 at five parallel runs, against 364 today. Bounded by the live window, not by the archive. | If `run.settled_fold_after_days` is ever raised past about 14, or a build-time measurement shows the opens cost more than a second. Row 5 writes the declaration that makes the cost visible. |

## Section 0a - The intent

**The owner's intent, 2026-09-22: content refresh runs in parallel, with no lock anywhere.** Design for unbounded concurrency and do not price how much of it there will be.

`concurrency: group: digest` is not the disease. It is where the disease surfaces, and it manufactures the staleness it appears to prevent - run `35660521768` waited 46 minutes in that queue and then folded a 46-minute-old store. This plan removes the reason the lock exists, then removes the lock.

## Section 0b - The one sentence

> **A file two runs can both write must be a pure function of files only one run each writes.**

## Section 0c - What the mechanics actually do

Seven behaviours, proved in a scratch repository on 2026-09-22. Each is reproducible in under a minute and none is taken on trust.

### Table B - what git actually does

| id | Proof | Result |
| --- | --- | --- |
| B1 | Two branches rewrite one file to the **same bytes** and both delete the same path | Merged, exit 0. **Two writers that agree byte for byte need no coordination.** |
| B2 | Two branches write **different bytes** to one file | `CONFLICT (add/add)` |
| B3 | Two branches each rewrite two directories; resolve one directory to this job's commit and the other to upstream | Each side won its own directory. **Per-directory ownership is implementable with no lock.** |
| B4 | The git spelling that keeps one side of a conflict, applied to a **modify/delete** | **Exit 0, no output, path left `DU` unmerged.** Under `set -euo pipefail` a script walks straight past it. |
| B5 | Replay of run `35660521768` with the fold as it works today | `CONFLICT (content)` on every head. The failure reproduces. |
| B6 | Same replay, producers writing the final day path, `merge.directoryRenames` left at its default | **`CONFLICT (file location)`.** Git reads an emptied `state/segments/` as *renamed* into the day directory, so a brand-new segment added there trips a location conflict. The tree was correct and the rebase stopped anyway. |
| B7 | Same replay, with `merge.directoryRenames=false` | **`Successfully rebased`, exit 0.** Nothing lost. |

**Why the head file is the defect.** `stage_compact` reads the **existing head**, merges the waiting segments into it, and writes the result. Two folders starting from different heads always produce different bytes, so B2 fires every time. Sorting does not fix it: the stale folder holds fewer keys, so its head would delete rows the tip has. The conflict is git protecting the data.

**A head file written by more than one process is broken.** No merge driver, no sort order and no refresh timing fixes it. Only two things do: exactly one process ever writes it, or there is no head file. Under unbounded parallel runs there is no job that can be named the one process - two runs both finish, so "the last job" does not exist. So there is no head file.

**A serialized single-writer workflow is refused, not deferred.** GitHub keeps only **one** pending run per concurrency group and a newer pending run silently cancels the older; the incident is recorded in [`.github/workflows/validate.yml`](../.github/workflows/validate.yml) lines 55-79. Under contention it drops folds with no error anywhere.

**A closed day is the one place a fold is still safe.** A head conflicts because its input set is not frozen - a stale folder sees fewer writer files and emits different bytes. A day past the live window has a frozen input set, so two folders emit byte-identical adds and byte-identical deletes, which B1 proves merges at exit 0. That is why row 12 exists and why it needs no owner.

## Section 0d - Ownership is an identity, not a side

**Nothing in this repository says `ours` or `theirs` outside two named shell functions.** Those are git's positional names, they invert between a merge and a rebase, and they describe which side of a graph a version came from rather than who is entitled to it. A design that reasons in them is a design nobody can check.

The writer's identity is already in the filename. `ledger.segment_path` spells it `<run_id>-<attempt>-<job>-<shard>`, and its own docstring says *"Nobody else writes this path."*

> **A conflicted path whose name carries this job's own identity resolves to what this job wrote. Every other conflicted path stops the push and names itself.**

Three consequences, each load-bearing.

- **The rule should never fire.** If every path carries its writer's identity, no second writer can name that file, so a conflict on it is impossible. Firing is a defect report, not a repair - it means two jobs claimed one identity, and the run log says which.
- **Git's spelling is hidden in one place.** Two shell functions, `keep_what_this_job_wrote` and `keep_what_origin_has`, carry the inversion and one line saying a rebase reverses it. Nothing outside them uses either word. `hand_back`'s existing `local tip="$1" ours path` is renamed `introduced_here` in row 8 - the banned word is in the file this plan is about.
- **There is a third case and it refuses.** B4: the git spelling exits 0 and does nothing on a modify/delete. A path still unmerged after the resolver ran is a delete race on a file this job owns, and nothing else can have deleted it - so the deletion is a defect and the push stops. It prints **one** identity, because one is all there is.

**A derived path may never be declared owned.** Resolving it to one side silently deletes the other writer's rows, and that failure is invisible: three single-writer inputs all land intact while the derived file quietly loses half its content. This is rule 2 below, and it is the one that keeps the rest honest.

## Section 0e - The contract

**Five rules. Each testable. Each holds for unbounded concurrent runs of digest, validate, measure, council and backfill.** A worker implements against this section; it is not a summary of the rows.

### Rule 1 - Written-once or derived, and the two sets are disjoint

Every committed path a stage writes is either **written-once** or **derived**.

A **written-once** path carries its writer's identity in its own filename - `<run_id>-<attempt>-<job>-<shard>` - and no process rewrites it or deletes it except retention and the closed-day fold (rule 1a).

A **derived** path is rebuilt from the tip plus this run's own inputs, is named in `idhazh.paths.DERIVED`, and is never resolved by identity.

*Test (contract tier): for every path a production stage writes, exactly one of `idhazh.paths.is_written_once(path)` and `path in idhazh.paths.DERIVED` is true. The test enumerates the writers from the code, never from the tree - nothing in this plan walks `state/`.*

**The declaration lives in `backend/idhazh/paths.py`, not in a workflow string.** `REFRESH_PATHS` stays as the transport and stops being the source: `digest.yml` runs a step that emits the list into `GITHUB_ENV`. An earlier draft said "there is no separate declaration file" and then tested against `REFRESH_PATHS`, a hand-written space-split YAML string whose own header warns that no path may carry a space. That sentence is deleted. One writer of the list, and the drift gate already covers a generated artifact.

### Rule 1a - A closed day folds once, and the fold is derived

A day older than `run.settled_fold_after_days` has a frozen input set, so any two folds of it emit byte-identical adds and byte-identical deletes (B1). Such a day folds to one `settled.csv` beside its writer files, and **a day that already carries `settled.csv` is never folded again** - a straggler arriving afterwards stays a writer file for ever and costs one file.

`settled.csv` is **derived** under rule 2. On a conflict, the tip's copy wins whole and this job's fold of that day is abandoned, which restores both the tip's file and any writer file this job's fold deleted. Nothing is lost either way: the tip's fold read the same input set or a subset, and abandoning restores the difference.

`settled.csv` reads at attempt 0 - the lowest - exactly as the head does today, because every row in it has already won its settlement and any straggler is by definition later.

*Test (integration tier): two branches fold one closed day from the same fixture and merge at exit 0; a third folds it with one extra straggler file, conflicts, and the resolver leaves the tip's `settled.csv` with the straggler intact beside it.*

### Rule 2 - A derived file is never owned

Its content is a function of other jobs' output, so it is rebuilt from the tip plus this run's own inputs. It is never text-merged and never resolved by rule 3.

*Test (contract tier): every path in `idhazh.paths.DERIVED` fails `is_written_once`, and the reverse.*

### Rule 3 - Identity resolves, everything else refuses

A conflicted path whose name carries this job's identity resolves to what this job wrote. **Every other conflicted path stops the push and names the path and this job's identity.** No third outcome. The resolver then asserts the index holds no unmerged entry, because of B4.

The predicate is one string comparison and reads no state:

```bash
# TRUE for every file this job is entitled to keep.
mine() {
  case "${1##*/}" in
    "${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-${JOB}-${SHARD}"*) return 0 ;;
    *) return 1 ;;
  esac
}
```

All three values are already on every commit step. Two jobs can never both answer yes, because GitHub allocates `run_id` and nothing else can reproduce it.

*Test (integration tier): the B3 shape committed - two branches, two identities, assert each side won its own; plus a branch that writes an unowned path, which must exit non-zero with that path in the message; plus a modify/delete, which must refuse rather than exit 0.*

### Rule 4 - An ordinal is assigned by the fold, never claimed by the writer

A writer stamps its identity and its completion time. Any number a reader sees is derived from arrival order at fold time. No writer reads or waits for another writer's ordinal.

**Every variant of "read the day, count the runs, claim N+1" has already failed here with a date on it.** On 2026-08-29 runs `33270983446` and `33274853468` both derived `2026-08-29-3`, and the ledgers keyed on it held six counter rows for four shards.

*Test (unit tier): a day built from fragments supplied in any order validates, renders, and emits byte-identical output for every permutation of arrival.*

### Rule 5 - History rewriting is outside rules 1 to 4

A force push is a whole-ref operation that never reads a path, so path ownership has nothing to own. The one job that force-pushes `main` re-fetches immediately before the push and refuses if the tip moved. It keeps its schedule and is due again next wake.

*Test (integration tier): the harness pushes a commit between the prune's checkout and its push; the prune must refuse rather than force.*

### Three questions settled, and why

**No ownership-claims file, and no lock file of any kind.** A lock file in a git repository is not a lock: two jobs both read "free" from their own stale checkouts and both take it, which is the read-modify-write race that broke the heads. **The only compare-and-swap this platform offers is the ref update itself** - a push succeeds only if the remote ref is where the pusher thought it was. That primitive is already in use, and a claims file would add a second weaker one beside it plus a growing collection nobody prunes.

**No parked branch for an unowned conflict.** Under rule 1 it should never happen, and infrastructure for a case that should never occur is scaffolding for a design broken somewhere else. A parked branch nothing drains is a graveyard that looks like the work was saved. And the work it would save is already saved - row 3 is the one job where it was not.

**The sequential run rule goes.** Exactly one of eight validator rules needs it; see row 6.

## Section 0f - The four things this plan must not do

Row 9 changes the published day payload, and a later plan (Table A row A3) has to tell a reader whether a day was broken, never ran, or was quiet. Ruled by Jony, 2026-09-22.

1. **Do not collapse `runs[]` to one entry, and do not drop `run_id` or `completed_at` from `DigestRunRef` as redundant.** "The 10:20 update has not arrived" is a set difference between the schedule and the runs that landed. Delete the list and there is nothing to subtract from.
2. **Do not let the fold write a `digest.json` for a date with no fragments.** A zero-item day file and a quiet day become the same bytes, and the later plan loses the ability to tell "never ran" from "ran and found nothing". Absent must stay absent.
3. **Do not make `items_failed` non-nullable again.** Row 9 makes it nullable and the broken-day sentence reads it.
4. **Do not put a freshness string anywhere but `DayNotice`.** Row 10 keeps it in one component; the later plan extends that component instead of reconciling three copies.

## Section 0g - The shapes, declared before any code

Every persisted shape this plan moves, named here so no worker invents one (Guardrail #3).

### Table C - the nine committed trees, after row 11

One template. Nine trees. No exceptions.

| id | Tree | Path template | Where the date comes from |
| --- | --- | --- | --- |
| C1 | item-health | `state/item-health/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell |
| C2 | host-fingerprint | `state/host-fingerprint/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell |
| C3 | scores | `state/scores/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell |
| C4 | score-index | `state/score-index/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | `run_id[:10]`, stamped by the writer |
| C5 | validation | `state/validation/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell |
| C6 | span-rollup | `state/span-rollup/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell |
| C7 | day-validations | `state/day-validations/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell |
| C8 | traces | `state/traces/<ledger>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.jsonl` | the run's date |
| C9 | pipeline-tests | `state/pipeline-tests/<ledger>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the run's date |

Three of these looked like exceptions and each is closed.

- **span-rollup moves from month grain to day grain.** Its key already carries `date`; the month grain existed only because the head was a month file. With no head there is no month file to justify it. `month_partition.month_files` stops being a state-ledger walker and keeps only its `frontend/public/` callers.
- **score-index gains no date column.** `ledger.segment_dates_from_run` and the `dates_from_run` field of `_HeadShape` are deleted; the writer already knows `run_id[:10]`, so that line moves out of the fold and into `evals.writer.append`. A persisted shape does not change to answer a question the writer already has.
- **traces already break rule 1 today.** `state/traces/<Y>/<M>/<DD>-<ordinal>-<shard>.jsonl` names the file for `<ordinal>`, which is the same `n` two runs both derived as 3 on 2026-08-29. It moves in this plan, not a later one.

Two further names are reserved, each with its removal condition on the line that declares it:

- `before-partition.csv` - what the migration writes for bytes that predate identity. A committed head is many runs already merged, so it has no identity to stamp. Written once, for the whole history, by a person running the utility. **Removal condition: it goes when the oldest committed day is newer than the migration date.**
- `repair-<YYYYMMDDTHHMMSSZ>.csv` - what `rebuild_index` writes as an operator utility. One add, never a rewrite. **Removal condition: it goes when `rebuild_index` is deleted.**
- `settled.csv` - rule 1a's closed-day fold. Derived, not owned.

### Table D - the two new modules

| id | Module | The one question it answers | Public surface |
| --- | --- | --- | --- |
| D1 | `backend/idhazh/day_shards.py` | What does a day directory of writer-owned files read back as? | `shard_files(root, *, days) -> Iterator[Path]`; `settled_rows(root, key, model, *, days) -> list[dict[str, str]]` |
| D2 | `backend/idhazh/paths.py` | Which committed paths are derived, and which are written once? | `DERIVED: Final[tuple[str, ...]]`; `is_written_once(relpath: str) -> bool` |

`settled_rows` runs the identical three-case fold `_settle` runs today - join, supersede, repeat - over one day's files, sorted by `(attempt, filename, lineno)` exactly as `_waiting_rows` sorts. Same code, same answer. `settled.csv` enters at attempt 0.

### Table E - the contract models that move

| id | Row | `__schema_stem__` | `version` | The one-line changelog entry |
| --- | --- | --- | --- | --- |
| E1 | 6 | `run-manifest` | `2026-09-22` | `runs no longer have to be numbered without gaps` |
| E2 | 6 | `digest-day` | `2026-09-22` | `runs no longer have to be numbered without gaps` |
| E3 | 9 | `digest-run-fragment` (new) | `2026-09-22` | `first version` |
| E4 | 9 | `digest-day` | same-day revision of E2 | `DigestRunRef carries run_id and completed_at; items_failed may be null` |

**Rows 5, 11, 12 and 13 move no stem and stamp no version.** A path is not a schema field and no row shape changes. Say so in each PR body so a reviewer does not go looking.

**The new fragment model**, declared before any logic reads or writes it:

- Class `DigestRunFragment`, module `backend/idhazh/contracts/digest_run_fragment.py`, `__schema_stem__ = "digest-run-fragment"`.
- Path `state/digest-fragments/<YYYY>/<MM>/<DD>/<run_id>.json`. **Not under `frontend/public/`** - see row 9.
- Required: `run_id`, `completed_at`, `failed_item_ids: list[str]`, `partial: bool`, and the item block.
- **Sort key, required: `__sort_key__: ClassVar = ("completed_at", "run_id")`.** `completed_at` is landing order; `run_id` breaks a same-second tie and is unique by construction. Without the tie-break two folds emit different bytes, which is the whole defect.

**The read-side migration for a payload yesterday's run wrote.** `DigestRunRef.run_id` and `.completed_at` are optional. The committed days carry neither. The fold, meeting a `digest.json` that has `runs` and no sibling fragment directory, **leaves it alone and emits it unchanged** - null reads as "this day predates fragments", and `DayNotice` already guards on absent runs. That is the migration, in one branch.

## Section 1 - Status Reckoner

**A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch. `Parallel-group` is the wave; readiness is still computed from `Depends-on` plus disjoint `Files touched` ([execute-a-plan.md](../docs/how-to/execute-a-plan.md#parallel-fan-out)).

| # | Row title | PR | Depends-on | Parallel-group | Status | Level | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The last state writer with no group gets one, and the failure stops lying | A | - | 1 | PENDING | 1 | - | - | - |
| 2 | The rebase stops guessing that a drained directory was renamed | A | - | 1 | PENDING | 1 | - | - | - |
| 3 | The plan job's artifact survives a failed push | A | - | 1 | PENDING | 1 | - | - | - |
| 4 | The push loop becomes a deadline and says what each attempt cost | A | - | 1 | PENDING | 2 | - | - | - |
| 5 | A day directory reads back as settled rows | B | - | 1 | PENDING | 3 | - | - | - |
| 6 | The one rule that needs a sequence is deleted | F | - | 1 | PENDING | 5 | - | - | - |
| 7 | The corpus moves to its own ref | H | - | 1 | PENDING | 4 | - | - | - |
| 8 | An unowned path stops the push and names itself | E | 1, 2, 4 | 2 | PENDING | 4 | - | - | - |
| 9 | The published day is folded from per-run fragments | G | 5, 6 | 2 | PENDING | 5 | - | - | - |
| 10 | One clock, and a label on every block that landed | G | 9 | 2 | PENDING | 3 | - | - | - |
| 11 | The day directory is the ledger | C | 5, 8 | 3 | PENDING | 5 | - | - | - |
| 12 | A closed day folds to one file | C | 11 | 3 | PENDING | 3 | - | - | - |
| 13 | The head goes | D | 11, 12 | 4 | PENDING | 3 | - | - | - |
| 14 | The concurrency group goes | I | 7, 9, 13 | 5 | PENDING | 4 | - | - | - |

### Table F - the wave map, and what makes each wave disjoint

**Nine pull requests in five waves.** The pool is four wide and it is only full in wave 1; waves 3, 4 and 5 are single-PR by construction, which is correct - two of them move committed data and the third removes the safety rail.

| id | Wave | In flight together | Why their files are disjoint |
| --- | --- | --- | --- |
| F1 | 1 | **A, B, F, H** | A owns the commit script, `digest.yml`, `measure.yml`, `config/idhazh.json` and the workflow tests. B owns the backend read side plus the server-side TypeScript walkers. F owns two contract modules, their schemas and the generated frontend contracts. H owns `prune.yml` and the finetune workflow. **H must carry no config knob** or it collides with A on `config/idhazh.json`. |
| F2 | 2 | **E, G** | E is the commit script and `.gitattributes`, serial behind A on that file. G is the published payload and the three page components, serial behind B and F. They share nothing. |
| F3 | 3 | **C alone** | **The one PR that must land alone.** It moves every committed head and rewrites every producer's write path. A digest run in flight when it merges pushes an old-shape head the migration missed - a timing call for a person, not a code problem. |
| F4 | 4 | **D** | The fold module and both walkers, behind C. |
| F5 | 5 | **I** | `digest.yml`, behind everything. Deleting the group is the last thing, not the first. |

PR [#1041](https://github.com/miztiik/yen-idhazh/pull/1041) is already open and merges as-is: it lowers the failure rate until PR C lands, and reverting it is a second change for no gain.

## Section 2 - The rows

### Row 1 - The last state writer with no group gets one, and the failure stops lying

- **Scope:** `measure.yml` gets a `concurrency:` block, and the commit script's failure message reports the attempt it actually spent.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `.github/scripts/commit-and-push.sh`
  - `backend/tests/workflows/test_triggers.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_triggers.py`, plus the repository's yaml lint. CI - the full suite.
- **Oracle:** every workflow that stages a path under `state/` declares a `concurrency:` group, asserted from the workflow files themselves. **It cannot settle** whether the groups are the right ones - only that none is missing.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1.1 | `measure.yml` is the only `state/` writer with no group and is dispatched by hand many times a day. It gets one. | Carmack |
| 1.2 | The message prints `$attempt`, not the constant "three". A conflicting rebase hits `break`, so every recorded failure spent one attempt while the log said three, and that sentence sends the next reader to the retry count, which cannot help. | Fowler |
| 1.3 | `validate.yml`'s group stays per candidate. Two candidates are two questions, and a shared group silently cancels the older pending run. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1.R1 | Leave `measure.yml` ungrouped because row 11 makes every writer safe anyway | Row 11 is waves away and `measure.yml` is dispatched today | One line saved now, against every hand dispatch between now and wave 3 racing the scheduled runs | Carmack |

### Row 2 - The rebase stops guessing that a drained directory was renamed

- **Scope:** every `git rebase` in the commit script runs with `-c merge.directoryRenames=false`.
- **Files touched:**
  - `.github/scripts/commit-and-push.sh`
  - `backend/tests/workflows/test_daily_commit_steps.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_daily_commit_steps.py`. CI - the full suite.
- **Oracle:** the B6 shape driven against a real temporary repository - one job drains a directory while another adds a file into it - rebases at exit 0 with the added file intact. **It cannot settle** whether any other directory-rename guess exists elsewhere in the pipeline.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 2.1 | This is a prerequisite, not a tuning knob. Git reads an emptied directory as *renamed*, so a brand-new file added into it trips `CONFLICT (file location)` with a correct tree. Without the flag, row 11 still loses the day on a different error - the worst kind to inherit. | Carmack, proved at B6 and B7 |
| 2.2 | It ships in wave 1, ahead of row 11, not beside it. The conflict class exists today because the fold already drains `state/segments/`. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 2.R1 | Set it repository-wide in `.gitconfig` | The runner's config is not the repository's, and a per-invocation flag is readable at the call site | One less flag on three lines, against a behaviour a reader cannot see from the script | Fowler |

### Row 3 - The plan job's artifact survives a failed push

- **Scope:** the plan job's `actions/upload-artifact` step gets `if: always()`, and its commit step gets `continue-on-error: true`.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_daily_commit_steps.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_daily_commit_steps.py`. CI - the full suite.
- **Oracle:** for every job in `digest.yml` that commits, the artifact upload that carries its output to a downstream job is not conditioned on that commit succeeding. Asserted from the workflow file. **It cannot settle** whether the artifact content is correct, only that it is uploaded.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 3.1 | **This is run `35660521768`, exactly.** It did not die because rows were lost. It died because a failed push skipped the artifact upload, so the plan never reached the shards. Measured per job, 2026-09-22: the work shard's commit is already `if: always()` with `continue-on-error: true` and all four of its uploads are `if: always()`, so a failed push costs it nothing; `assemble` loses the publish but keeps the record; **`plan` loses the whole run**. | Carmack |
| 3.2 | This is why no row in this plan parks work on a side branch. The expensive work is already protected by artifacts, and the one job where it was not is fixed here in two lines. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 3.R1 | Park the plan's output on a side branch when the push fails | A parked branch nothing drains is a graveyard that looks like the work was saved | The drain job, its schedule, and a second place a reader has to look | Fowler |

### Row 4 - The push loop becomes a deadline and says what each attempt cost

- **Scope:** the three-attempt counter becomes a wall-clock deadline with jittered backoff, three failure paths become `continue`, and every attempt prints what it spent.
- **Files touched:**
  - `.github/scripts/commit-and-push.sh`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_daily_commit_steps.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_daily_commit_steps.py`, the contract drift gate, and the repository's yaml lint. CI - the full suite.
- **Oracle:** a scripted origin that rejects the first N pushes and accepts the N+1th; the script lands the commit within the deadline and prints one line per attempt whose `window_ms` sums to less than the deadline. **It cannot settle** the real `W` on a runner - that is what the printed line exists to collect, over about twenty runs.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 4.1 | Deadline `run.push_deadline_seconds`, default 300. Against `assemble`'s 20-minute timeout that is 25 percent of the job; against a work shard it is 53 percent of the 9.4 minutes it has left, and that is affordable because a work shard's failed push already costs nothing (row 3). | Carmack |
| 4.2 | Backoff `min(2^(k-1), 8) x U(0.5, 1.5)` seconds, `k` = failures so far. Sleeps run 1, 2, 4, 8, 8, 8. The cap at 8 s turns the deadline into about 32 attempts at a 2-second window instead of 8. Multiplicative jitter centred on 1 stops every loser refetching in lockstep, and its spread grows with the backoff, so collisions fall as contention rises. | Carmack |
| 4.3 | Which failure paths change: **`git fetch` fails becomes `continue`** - a transient the deadline is built to ride out, where a broken token costs 300 s of a 6 h budget. **A conflicting rebase whose every conflicted path carries this job's identity becomes resolve, `--continue`, `continue`** - that is row 8's resolver doing its job. Everything else **stays `break`**: an unowned conflicted path (retrying cannot make another writer's file yours), a failed `REGENERATE_COMMAND` (a producer fault against the tip, not a race), and any failure of `hand_back`, `git add`, `git commit --amend`, `git reset --soft`, `discard_noise` or `clear_what_the_tip_will_write_over` (index or filesystem damage, which retrying compounds). | Carmack |
| 4.4 | Six stamps, printed once per attempt to stdout and to `$GITHUB_STEP_SUMMARY`: `push attempt=<n> job=<job> shard=<s> outcome=<landed\|rejected> window_ms= fetch_ms= handback_ms= rebase_ms= rebuild_ms= push_ms=`. **The split is the point** - `rebuild_ms` against `window_ms` is the only number in this plan that decides a design, and a single `W` cannot answer it. | Carmack |
| 4.5 | **Attempt 1 has no window in the retry model's sense.** There is no `git fetch` before the first `git push`, so its exposure is the whole job - checkout to push, two to three hours - which is not a retry parameter. `W` is defined for attempts 2 and up; attempt 1 is recorded as `outcome=landed\|rejected` and the first-push success rate over twenty runs is the measurement of its exposure. | Carmack |
| 4.6 | **The number is not committed to a ledger, yet.** Both candidate rows - host-fingerprint's and span-rollup's - are written by Python *before* the commit step runs, so neither can carry a number that does not exist until after the push. Any committed push window needs a later step, job or run. That machinery buys a trend; the decision it is meant to settle is taken once (Guardrail #10). | Carmack |
| 4.7 | If a trend is later wanted it is `state/span-rollup`, span name `push`. Its columns `run_id,shard,span_name,count,total_ms,unattributed_ms` already fit with zero schema change, and `count` carries the attempt number for free. Host-fingerprint would need two new columns on a persisted contract to record a duration on a row about a machine's identity - wrong shelf. | Carmack |
| 4.8 | **This row is first, not last.** Rows 9, 11, 12 and 14 all argue from its output. An earlier draft scheduled it after the change that invalidates its baseline. | Carmack and Fowler, converged |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 4.R1 | Keep the fixed three attempts and raise the count | A fixed count is spent instantly under unbounded N, whatever the count. An optimistic rebase-and-push converges in expectation at any commit rate; a counter does not. | Nothing to build, and the loop keeps failing at exactly the rate the owner is raising | Carmack |
| 4.R2 | Add two nullable duration columns to `host-fingerprint` now | The row is written before the push happens, so the columns would always be null | A schema stamp, a changelog line and a migration, for a column nothing can fill | Fowler |
| 4.R3 | A new telemetry artifact for the push window | A new committed collection to answer a question asked once | One artifact, one prune, one schema - against an `echo` | Carmack |

### Row 5 - A day directory reads back as settled rows

- **Scope:** the settlement moves out of the thing that writes a file and into a reader both languages can call, every walker learns to read a day directory as well as a day file, and the two ledgers with no prune get one. Nothing writes a directory yet, so this PR cannot change a single run.
- **Files touched:**
  - `backend/idhazh/day_shards.py` (new)
  - `backend/idhazh/stages/compact.py`
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/retention.py`
  - `backend/idhazh/evals/writer.py`
  - `backend/idhazh/telemetry/prune.py`
  - `backend/utilities/measure_ledgers.py`
  - `backend/utilities/item_health_provenance.py`
  - `backend/utilities/server_memory_mark.py`
  - `backend/utilities/empty_column_census.py`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/lib/server/span-rollup.ts`
  - `frontend/src/lib/server/host-fingerprint.ts`
  - `docs/concepts/growing-reads.md`
  - `docs/concepts/partitions.md`
  - `backend/tests/fixtures/day-shards/both-shapes/` (new)
  - `frontend/tests/fixtures/day-shards/` (new)
  - `backend/tests/fixtures/retention/score-index-and-day-validations/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, `npm --prefix frontend run test:changed -- --list` then the selected checks, `npm --prefix frontend run check`. CI - the full suite and the drift gate.
- **Oracle:** `day_shards.settled_rows` over a fixture directory holding three writer files that settle on one key at two attempts returns **exactly** what today's `_compact_ledger` returns for the same rows folded into a head. Parity, row for row. **It cannot settle** whether every production caller was moved - that is the enumerated list in decision 5.2, checked by a separate assertion.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 5.1 | `_settle`, `_contested`, `_Held` and `_Waiting` move into `backend/idhazh/day_shards.py`, whose one question is *what does a day directory of writer-owned files read back as*. Identical three-case fold, same sort - `(attempt, filename, lineno)`. | Fowler |
| 5.2 | Eleven Python call sites move from `day_files` to `day_shards.shard_files`: `evals/writer.py` `ledger_days`, `records`, `index_days`, `indexed_observations`; `ledger.py` census for item-health and host-fingerprint; `retention.py` `_operator_pass`; `telemetry/prune.py` `_prune_ledger`; and four utilities - `measure_ledgers`, `item_health_provenance`, `server_memory_mark`, `empty_column_census`. | Fowler |
| 5.3 | **`day_partition.day_files` is not touched.** It keeps its callers over `state/published/` and `state/visual-prunes/`, which are not moving, and it keeps refusing a directory loudly. That refusal is now the tripwire that catches a tenth tree arriving without a plan. | Fowler |
| 5.4 | **The walker reads both shapes** - a `<DD>.csv` file and a `<DD>/` directory. That is what makes this PR inert. Row 13 removes the file branch. | Fowler |
| 5.5 | `dayShardFiles` gains the directory branch, and its silent skip is **reversed for directories**: a `/^\d{2}$/` directory holding zero readable `.csv` files throws. The silent skip is the one defect in this plan that would ship green - four prerendered console routes drawing zero rows on a passing build. A prerender failure is where that belongs. | Fowler |
| 5.6 | `span-rollup.ts` `readShards` becomes a day-directory reader in the same change, because row 11 moves that ledger from month grain to day grain. | Fowler |
| 5.7 | **score-index gets no new knob.** It is derived from `state/scores/` and is pruned to exactly the span `retention.scores_full_grain_months` keeps, in the same pass. A derived index that outlives its source is a lookup that misses for ever, and `refresh_index` only ever fills a month with no index - it never repairs a stale one, so nothing would notice. | Carmack |
| 5.8 | **day-validations gets `retention.day_validation_keep_months`, default 14**, matching every other retention knob in the file. A receipt for a day the archive no longer holds cannot be read. | Carmack |
| 5.9 | The Guardrail #12 declaration is rewritten in the same commit as the walker it describes: the console reads a fixed 91-day window, the folded days cost one file each, and only the live days cost one file per writer - so the read is bounded by `run.settled_fold_after_days` times writers-per-day, and by nothing in the archive. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 5.R1 | Fold rows 5, 11 and 13 into one pull request | Row 11 is the riskiest change in the plan and must stay revertible on its own. Reverting a combined PR also reverts the only reader that can read the migrated tree, with the tree already migrated. | Two merges saved, against a revert that leaves committed data unreadable | Fowler |
| 5.R2 | Move the four prerendered console routes onto the committed projection first | Under row 12's fold the build reads 896 files today and 3,136 at five parallel runs, against 364 now - bounded by a knob, not by the archive | One more PR gating row 11, to remove a cost that a declaration already makes visible. Revisit if the fold window is ever raised past about 14 days. | Carmack |
| 5.R3 | Keep `_settle` where it is and give each ledger its own read-side fold | Six answers to one question, drifting independently | Six implementations instead of one, and a reader that forgets to call it reads double-counted rows | Fowler |

### Row 6 - The one rule that needs a sequence is deleted

- **Scope:** the clause requiring runs to be numbered from 1 without gaps is deleted from both models that carry it, and two docstrings that now describe the wrong guarantee are corrected.
- **Files touched:**
  - `backend/idhazh/contracts/digest_day.py`
  - `backend/idhazh/contracts/run_manifest.py`
  - `backend/idhazh/placement.py`
  - `schemas/digest-day.schema.json`
  - `schemas/run-manifest.schema.json`
  - `frontend/src/contracts/digest-day.ts`
  - `backend/tests/fixtures/contracts/run-manifest/runs-with-a-gap.json` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests/contracts`, the contract drift gate, `npm --prefix frontend run check`. CI - the full suite.
- **Oracle:** a manifest whose runs are numbered 1, 2, 4 validates where it previously raised, and every other clause of `_order_is_global_and_append_only` still raises on its own fixture. **It cannot settle** that no reader assumed contiguity - decision 6.4 is the enumeration that answers that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 6.1 | `_order_is_global_and_append_only` holds eight rules and **exactly one** needs a writer to know what another writer did: `runs are numbered from 1 without gaps`. It goes. The others - distinct item ids, non-decreasing `introduced_by_run`, the bounds checks, the `items_added` arithmetic, the vertical counts, `partial`, `updated_by_run >= introduced_by_run` - are arithmetic inside one file and stay. | Fowler |
| 6.2 | The same sentence sits in `RunManifest._runs_are_append_only_and_addressed_by_date`. Both go in one commit - they are one sentence in two files. The `run_id` uniqueness and date-prefix checks stay. | Fowler |
| 6.3 | **`n` is already an arrival ordinal, not a schedule ordinal.** `assemble.run_n_for`'s own docstring splits `n` (the day's ordinal) from `run_id` (the execution's identity), on purpose. Nothing here believes `n` means "the 02:20 run"; it means "the Nth block this day received". | Fowler |
| 6.4 | Two docstring sentences in `placement.py` become false and are corrected in the same commit: *"the score's own first pick among the stories the first run published"* becomes *the first block to land*, and *"the blocks keep the order the runs published them in"* becomes *the blocks keep the order they landed in*. One line is added saying `introduced_by_run` is arrival order at fold time. Without it the next reader re-derives the wrong guarantee. | Jony |
| 6.5 | **What an operator loses**: the rule caught a producer that skipped a block. After row 9 the fold assigns `n` by `enumerate()` over arrival order, so contiguity holds by construction and the validator checks the fold's arithmetic instead of a writer's claim. The skipped-block case is then caught by the fragment count, not by the ordinal. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 6.R1 | Keep contiguity and have writers coordinate the ordinal | Every variant of "read the day, count the runs, claim N+1" has already failed here with a date on it - 2026-08-29, two runs, one ordinal, six counter rows for four shards | A coordination primitive this platform does not have | Fowler |
| 6.R2 | Ship rows 6 and 9 as one pull request | They share `digest_day.py`, so they cannot run beside each other - but row 6 is a two-line deletion that unblocks row 9 and finishes in wave 1 | One merge saved, against row 9 waiting a wave longer to start | Carmack |

### Row 7 - The corpus moves to its own ref

- **Scope:** `corpus/` leaves `main` for a ref of its own, and the force-pushing job re-checks the tip immediately before it pushes.
- **Files touched:**
  - `.github/workflows/prune.yml`
  - `.github/workflows/finetune.yml`
  - `.github/scripts/` (the prune's own script, if one is extracted)
  - `docs/how-to/fine-tune-a-model.md`
  - `backend/tests/workflows/` (the prune's test)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows` for the prune's test. CI - the full suite.
- **Oracle:** the harness pushes a commit between the prune's checkout and its push; the prune refuses rather than forcing, exits non-zero, and the pushed commit survives. **It cannot settle** whether the corpus ref itself stays healthy across a prune - that is the prune's own existing test.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 7.1 | **A partition cannot fix this one.** The prune's unit is a commit range, not a path, so it rewrites `backend/`, `docs/` and `state/` alongside `corpus/`. A force push is a whole-ref operation that never reads a path, so there is nothing for path ownership to own. | Fowler |
| 7.2 | Today this is held by two things that do not survive unbounded concurrency: a `corpus-prune` group that reaches no other workflow, and a 23:37 cron hand-placed in the one 266-minute idle gap the serial schedule leaves. Parallel runs erase that gap. | Carmack |
| 7.3 | Contract rule 5 ships here: the prune re-fetches immediately before the push and refuses if the tip moved. An unstamped prune is due again next wake, so refusing costs one cycle. | Fowler |
| 7.4 | **This PR carries no config knob**, or it collides with row 4 on `config/idhazh.json` and the two cannot run in the same wave. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 7.R1 | One concurrency group shared between `prune.yml` and every pushing workflow | It serialises the entire pipeline behind a maintenance job, which is the end of the feature rather than a fix for it | One line, and the owner's stated intent | Carmack |
| 7.R2 | Stop pruning and let history grow | The corpus commits article text and git history is append-only, so deleting a row does not delete its bytes | An unbounded repository, which is the reason the prune exists | Fowler |

### Row 8 - An unowned path stops the push and names itself

- **Scope:** contract rules 1 and 3 ship as code. The commit script resolves a conflicted path it owns, refuses one it does not, and asserts the index is clean afterwards.
- **Files touched:**
  - `.github/scripts/commit-and-push.sh`
  - `.gitattributes`
  - `backend/tests/fixtures/resolver/` (new)
  - `backend/tests/workflows/test_daily_commit_steps.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_daily_commit_steps.py`. CI - the full suite.
- **Oracle:** the B3 shape committed - two branches, two identities, each side keeps its own file - **plus** a branch writing an unowned path, which must exit non-zero with that path and this job's identity in the message, **plus** a modify/delete on an owned path, which must refuse rather than exit 0. **It cannot settle** that the predicate is right for a writer that does not exist yet; row 5's disjoint-sets test is what covers that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 8.1 | The resolver walks `git diff --name-only --diff-filter=U`, applies the `mine()` predicate from contract rule 3, and refuses on the first path that answers no. | Fowler |
| 8.2 | **The refusal prints one identity, not two.** A file named for this job that the tip has deleted means retention or a person deleted it, not another run. A second identity field would always be empty. | Fowler |
| 8.3 | After resolving, `git diff --name-only --diff-filter=U` must be empty. The git spelling exits 0 and does nothing on a modify/delete (B4), so without this assertion `set -euo pipefail` walks straight past a `DU` entry. | Fowler |
| 8.4 | Two shell functions, `keep_what_this_job_wrote` and `keep_what_origin_has`, hold the whole of git's positional spelling plus one line saying a rebase reverses it. `hand_back`'s existing `local tip="$1" ours path` is renamed `introduced_here` - it does not even mean a git side. | Fowler |
| 8.5 | In the same PR, `state/seen` gets `merge=union` in `.gitattributes`. It has no driver today and falls through to `*.csv text eol=lf`, so two parallel runs conflict at the push. `load_seen` keeps the earliest timestamp per key, so a repeated row changes no answer - the same argument already written above `state/published/**`. | Fowler |
| 8.6 | **No merge driver on any tree in Table C.** A written-once file is only ever added, and two adds of one path would mean two writers - which is the defect, not a case to smooth over. | Fowler |
| 8.7 | **It should never fire**, and it is bought anyway: it is the only thing that turns the next two-writer defect into a message rather than a silent loss, and the only thing that catches the modify/delete case. About 60 lines of bash and one test. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 8.R1 | A declaration file listing what each job owns | The identity is already in the filename, and `segment_path`'s own docstring says so. A config list restates it and drifts. | One file, one reader, and a second place to forget | Fowler |
| 8.R2 | A lock file taken before the push | Two jobs both read "free" from their own stale checkouts and both take it - the same read-modify-write race that broke the heads. The only compare-and-swap here is the push itself. | A second, weaker primitive beside the one that works | Carmack |
| 8.R3 | Resolve an unowned path to the tip and carry on | On a derived file that is silent deletion of another writer's rows, invisible in every gate | Nothing to build, and a data-loss mode nobody can see | Fowler |

### Row 9 - The published day is folded from per-run fragments

- **Scope:** each run commits one fragment named for itself; `digest.json` stops being written by a run and becomes derived from the fragments by one idempotent fold.
- **Files touched:**
  - `backend/idhazh/contracts/digest_run_fragment.py` (new)
  - `backend/idhazh/contracts/digest_day.py`
  - `backend/idhazh/contracts/digest_view.py`
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/retention.py`
  - `backend/idhazh/paths.py`
  - `schemas/digest-run-fragment.schema.json` (generated)
  - `schemas/digest-day.schema.json`
  - `schemas/digest-view.schema.json`
  - `frontend/src/contracts/` (generated)
  - `.github/workflows/digest.yml`
  - `backend/tests/fixtures/digest-fragments/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, the contract drift gate, `npm --prefix frontend run check`. CI - the full suite. Browser smoke per CLAUDE.md section 12, shared with row 10.
- **Oracle:** three fragments, two sharing a `completed_at` second, folded in every arrival permutation, emit **byte-identical** `digest.json`. **It cannot settle** that a day predating fragments still reads - that is the separate parity case in decision 9.6.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 9.1 | **The fragment does not go under `frontend/public/`.** Everything there is copied verbatim into the build output, so as drafted the fragments would be served, crawlable, and a second full copy of every story on a site Pages refuses over 1 GB. Path: `state/digest-fragments/<Y>/<M>/<D>/<run_id>.json`. **What enforces it is absence** - there is no URL, so there is nothing to index and nothing for a reader to land on. A `robots.txt` disallow would be a request to a crawler, not a control, and would leave the bytes in the deploy. | Jony |
| 9.2 | `digest.json` remains the only thing the site build reads, and the fold writes it temp-file-plus-rename. A half-written day file is then never readable, so a build sees either the previous fold's file or the new one and the archive count can never disagree with the day page. | Jony |
| 9.3 | **Order by landing, whole block at a time, never interleaved.** First sight, run start, run completion and score each break the append-only promise by moving a story a reader was part-way through. The sort is `__sort_key__ = ("completed_at", "run_id")`, both required. | Editor and Jony, converged |
| 9.4 | A fold that sees fewer fragments emits a valid **prefix**; the next fold appends the rest. The append-only promise is kept exactly, because the fold inherits position rather than computing a key. Two folds over the same fragment set emit identical bytes, which B1 makes free. | Fowler |
| 9.5 | **`generated_at` is the maximum `completed_at` across the fragments folded, not the fold's own wall clock.** A wall clock breaks the identical-bytes promise on the first re-fold. A max over the set is monotonic - a new fragment can only raise it - and deterministic. It means "the newest run in this page finished at HH:MM UTC". | Jony |
| 9.6 | The fold, meeting a `digest.json` with `runs` and no sibling fragment directory, **leaves it alone and emits it unchanged.** Null `run_id` and `completed_at` read as "this day predates fragments". That is the whole read-side migration, in one branch. | Fowler |
| 9.7 | **`items_failed` is not a sum across fragments.** An article that failed at 02:20 and landed at 06:20 would be counted failed and published on one page. The fragment carries `failed_item_ids: list[str]`; the fold takes the union and subtracts every id that appears in `items`. `DigestDay.items_failed` becomes `int \| None`, matching `DigestView`, which already guards on null. `partial` stays a required `bool` and the fold sets it `any(fragment.partial)` - a boolean OR needs no de-duplication, so it is always computable even when the count is not. | Jony |
| 9.8 | `_order_is_global_and_append_only` skips its two `items_failed` clauses when the value is null. | Fowler |
| 9.9 | `assemble.run_n_for` is **deleted here**, not in row 6. Row 6 removes the rule that made the claim load-bearing; this row removes the claim. The fold assigns `n` by `enumerate()` over the sorted fragments. | Fowler |
| 9.10 | `retention.py` prunes `state/digest-fragments/<day>/` on the same rule as the day itself. Without it the fragments are an unbounded second archive. | Jony |
| 9.11 | This is what takes `REGENERATE_COMMAND` out of the assemble push window for good. Until it lands, the rebuild is bounded by row 4's deadline and by the guard in 9.12. | Carmack |
| 9.12 | Until this row lands, the rebuild is skipped when the tip carries no change to any refresh path since the base being rebased onto - `git diff --quiet "$(git merge-base HEAD FETCH_HEAD)" FETCH_HEAD -- "${REFRESH[@]}"`. Most pushes that lose a race lose to a sibling job's `state/` commit, not to another run's digest, and when no derived path moved the rebuild reproduces this run's own output. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 9.R1 | `merge=union` on `frontend/public/**/*.json` | A union of two objects is a file that is not JSON, and the failure surfaces in a reader's browser instead of at the push | One `.gitattributes` line, against a white screen | Fowler |
| 9.R2 | Order by first sight, run start, or score | Each moves a story the reader was part-way through | A better-looking order, against the one promise the reader asked for by name | Jony |
| 9.R3 | Keep the fragments under `frontend/public/` and exclude them at build | An exclusion is a rule somebody has to remember; absence is not | One build-config line, against a reader landing on raw machine text from a search result | Jony |

### Row 10 - One clock, and a label on every block that landed

- **Scope:** the freshness line prints one clock that cannot go backwards, and every block after the first says when it arrived.
- **Files touched:**
  - `frontend/src/lib/components/DayNotice.svelte`
  - `frontend/src/lib/components/BlockDivider.svelte` (new)
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/tests/` (the component tests)
  - `frontend/playwright.whole-day.config.ts` suite (the archive-count parity test)
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:** local - `npm --prefix frontend run test:changed -- --list` then the selected checks, `npm --prefix frontend run check`, and the browser smoke in CLAUDE.md section 12. CI - the full suite.
- **Oracle:** for the newest published day, the archive row's story count equals the number the day page prints - asserted in a browser, not argued. **It cannot settle** whether the label's wording reads well; that is the section 12 screenshot.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 10.1 | **`(update N)` does not survive.** The sentence carried two orderings three words apart: a wall clock that can go backwards and a count that only goes forwards. **What the reader loses**: they can no longer see how many times the day was added to - only that it was, and where. That is the price, and it is paid because a reader who once sees the time go back while the count goes forward stops believing every date on the site. | Jony |
| 10.2 | The clock is **`day.generated_at`**, not `runs.at(-1).at`. `at` is a per-run stamp, so the last run's `at` is the clock of whichever run landed last, which under parallel folds is any clock at all. The field already exists on both `DigestDay` and `DigestView`; **no new field**. The string is `Updated 06:47 UTC.` - `clockUtc` already appends the zone. | Jony |
| 10.3 | The second half of the line keeps `laterAdded` and changes wording only: `{laterAdded} added after this page first went up.` - true under arrival order, and it does not borrow the word 10.1 deleted. | Jony |
| 10.4 | **A block label, and it is computed from the run's clock, never from the stories' own time.** `DigestItem.published_at` is nullable and comes from the feed, so a block routinely holds a back-catalogue story next to one filed an hour ago; a label derived from those says "last Tuesday" over stories the reader is meeting for the first time. The label answers *when did this arrive on this page*. | Jony |
| 10.5 | The label **never claims a direction relative to the block above it.** "Earlier this morning" is right for a catch-up landing second and a lie for the normal case, and the page cannot tell which it has without comparing clocks that are allowed to be in any order. It states its own clock, absolutely: `Added 02:58 UTC`, from `clockUtc(run.completed_at ?? run.at)`. | Jony |
| 10.6 | Three conditions, all of them: it draws above the first item of a block only when that item's `introduced_by_run` differs from the previous item's; **never above the first block**, which needs no label saying it is the page; and **never when the block's clock is unknown**, because a divider with no time says nothing. | Jony |
| 10.7 | New component `frontend/src/lib/components/BlockDivider.svelte`, one prop `{ label: string }`, drawn by `DigestList.svelte` inside the existing item loop. One component, one string, driven by a field every item already carries - not a per-item special case. | Jony |
| 10.8 | **This gives `introduced_by_run` a renderer**, so deleting it from `DigestView` stops being a deferred option and becomes a refusal (Table A, row A4). | Jony |
| 10.9 | **Page order does not change.** `placement.py` keeps first-block-wins; the head of the page goes to the first block that landed. Row 6's docstring correction already says so. **What the reader loses**: on a day a slow catch-up lands first, the topic-spread top dozen is that block's and fresher stories sit below it. **What they gain**: the never-reshuffle promise held exactly, at zero code risk, with 10.5's label making it honest - they can see the head block finished at 02:58 and judge for themselves. | Jony |
| 10.10 | **Row 10 ships in the same pull request as row 9**, after it. The gap between two merges would put a clock that goes backwards on the live site, and a reader-visible defect may not live on main between two merges. | Jony |
| 10.11 | No frontend change for `items_failed`. `DayNotice` already guards on null, so when the count cannot be computed the sentence simply does not draw. The string is unchanged: `{n} articles did not finish.` | Jony |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 10.R1 | Give the head of the page to the freshest block | Requires moving a block up the page after a reader has seen it, which breaks never-reshuffle directly | A better head, against the reader's stated promise | Jony |
| 10.R2 | Re-pick the head across the whole day on every fold | Every fold can then move any story a reader was part-way through | The best head available, against destroying the promise outright | Jony |
| 10.R3 | Hold the head unassigned until the day's last run lands | Under parallel arrival there is no last run, and holding means the 07:00 reader gets no framed head at all | Nothing to build, and a worse page for every early reader | Jony |
| 10.R4 | Drop the archive story count | It is the only number telling a reader whether a day is worth opening | One number removed, to fix a disagreement that 9.2 already makes impossible | Jony |

### Row 11 - The day directory is the ledger

- **Scope:** producers write the final day path directly; `state/segments/` and the read-the-head fold are deleted; every committed head migrates.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/stages/compact.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/stages/record.py`
  - `backend/idhazh/stages/decide.py`
  - `backend/idhazh/stages/qualify_decide.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/stages/validate_days.py`
  - `backend/idhazh/evals/writer.py`
  - `backend/idhazh/telemetry/traces.py`
  - `backend/idhazh/paths.py`
  - `backend/idhazh/month_partition.py`
  - `backend/utilities/migrate_to_day_shards.py`
  - `backend/utilities/rebuild_index.py`
  - `.github/workflows/digest.yml`
  - `.github/workflows/validate.yml`
  - `config/idhazh.json`
  - `docs/architecture/publishing/committing.md`
  - `docs/concepts/partitions.md`
  - `backend/tests/fixtures/paths/production-writers.json` (new)
  - `backend/tests/fixtures/migrate-to-day-shards/` (new)
  - `backend/tests/fixtures/traces/` (new)
  - `backend/tests/fixtures/pipeline-tests/two-candidates/` (new)
  - `backend/var/canary/`
  - every committed file under `state/item-health`, `state/host-fingerprint`, `state/scores`, `state/score-index`, `state/span-rollup`, `state/validation`, `state/traces`, `state/pipeline-tests`, and `state/day-validations.csv`
- **Acceptance gates:** local - `python -m pytest backend/tests`, the contract drift gate, `npm --prefix frontend run check`, and the full browser smoke in decision 11.9. CI - the full suite.
- **Oracle:** the migration reads its own output back through the pipeline's own reader and compares **row for row** against what came out of the old heads; it refuses to install a tree it cannot read back. **It cannot settle** whether a run in flight during the merge pushes an old-shape head - that is the quiet window in decision 11.8, and it is a person's call.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 11.1 | **Producers write the day path directly. There is no split-and-rename, and `stage_compact` is deleted.** The segment directory existed because the head had one shape and many writers; once the day directory takes the writer-identity name, the segment directory *is* the day directory and only the parent changes. `ledger.segment_path` is renamed `ledger.day_shard_path` and gains the three date arguments. `_segment_name` is unchanged. | Fowler |
| 11.2 | **Nothing settles on disk.** Settlement happens at read time in `day_shards.settled_rows`, which row 5 already shipped. Cross-run collapse survives - `OBSERVATION_KEY` has no `run_id`, so two runs scoring one article do settle, just in the reader rather than in the fold. | Fowler |
| 11.3 | **A key containing `run_id` does not make a ledger safe to leave unsettled.** `ITEM_HEALTH_KEY` contains it and the work shard and `assemble` both write that key for one run from two jobs; `attempt` is in no key at all, by design, because a re-run is meant to correct. So every ledger can have two files holding one key, and a rule that splits on `run_id` splits nothing. | Fowler |
| 11.4 | **span-rollup moves to day grain**; `month_partition.month_files` stops being a state-ledger walker and keeps only its `frontend/public/` callers. **score-index gains no date column**: `segment_dates_from_run` and `dates_from_run` are deleted and the writer stamps `run_id[:10]`. **traces move in this plan**, because their filename already carries the ordinal two runs both derived as 3 on 2026-08-29. | Fowler |
| 11.5 | `refresh_index` and `_fill_index` are **deleted** - they exist to back-fill a day whose rows predate the index, and after the migration no such day exists. `recorded_observations` drops its `refresh_index` call. `rebuild_index` survives as an operator utility writing `repair-<YYYYMMDDTHHMMSSZ>.csv`, one add, never a rewrite. | Fowler |
| 11.6 | `state/day-validations.csv` gets no exception: it becomes tree C7 on the same template. Its only reader, `stages/validate_days.py`, gains `day_shards.settled_rows` on `("date",)`. | Fowler |
| 11.7 | The migration writes one fixed name per day, `before-partition.csv`, with its removal condition on the declaring line. A committed head is many runs already merged, so it has no identity to stamp, and a synthetic identity would fail rule 1's own test. Extend `migrate_to_day_shards.py`, which already did this repository's last grain change and already refuses to write a tree it cannot read back: *"a migration that writes an empty tree and unlinks its source is a delete with exit 0."* | Fowler |
| 11.8 | **This is the one PR that lands alone, and it needs a quiet window.** A digest run in flight when it merges pushes an old-shape head the migration missed. That is a timing call for a person, not a code problem - ESCALATE trigger 1. | Carmack |
| 11.9 | Browser smoke, per CLAUDE.md section 12, against a checkout whose `state/` is in the new shape, after asserting the preview serves *this* build: `/console/`, `/console/machine/`, `/console/model/` and `/console/voices/` each draw non-zero rows; one digest day page as the cross-page smoke; zero new `[error]` and zero new `404` on each; and the same six with `state/item-health/` renamed away, where every page must render rather than white-screen. On `/console/machine/` scroll the whole page first and take a viewport screenshot - an element screenshot never settles there. | Jony |
| 11.10 | **Cost, measured 2026-09-22 and stated rather than implied.** Retention is **14 months, about 426 days** - not the 30 days an earlier draft assumed. Writers per day today: item-health 20, scores 5, score-index about 5, host-fingerprint 16, span-rollup about 4.3, so about 50 files a day. Without row 12 that is **about 21,400 files at today's rate and about 107,000 at five parallel runs a slot.** With row 12 it is **about 2,900 and about 4,300.** `state/` ships zero files to the site - verified, `frontend/build` holds no `state` path - so the 1 GB Pages cap is untouched. | Carmack |
| 11.11 | **An earlier claim is deleted as falsified, not softened.** History bytes do **not** fall from 78.7 MB to about 40 MB. Measured in a scratch repository with real rows, pack size goes **up** 1.24x at 20 files a day and 1.76x at 98. A falsified number in a plan is worse than no number. | Carmack |
| 11.12 | **Keep the CSV header on every writer file.** The 97.1 percent overhead on host-fingerprint is a ratio on a ledger measured in kilobytes - about 2.2 MB over the whole 14-month window. **What was traded**: roughly 97 percent of that one ledger's bytes, against every file under `state/` staying readable by `csv.DictReader`, by a spreadsheet, and by a person opening it. A headerless file would also break `ledger.settle_header` and every reader in row 5. | Carmack |
| 11.13 | `git add` rises 11.9x (203 ms to 2,409 ms at 2,940 files) and clone-plus-checkout 4.3x, on a dev machine, one repetition, no spread taken - treat them as a floor on a 4 vCPU runner. **Accepted**: both are seconds inside a job measured in hours, and neither is one of the two numbers that fail a run. Against the work shard's 200-minute budget the checkout rise is 0.02 percent. | Carmack |
| 11.14 | The five state ledgers leave `idhazh.paths.DERIVED` in this row - nothing derives them any more - so `hand_back` stops touching `state/` altogether and the assemble push window gets **shorter**, not longer. Row 4's `handback_ms` is what shows it. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 11.R1 | One head per day with exactly one named writer | Under unbounded parallel runs two runs both finish, so "the last job" does not exist. There is no job that can be named. | Nothing to build, and a design that cannot be implemented | Carmack |
| 11.R2 | One file per run per day, folded by that run's own assemble | An orphaned file is then never folded by anyone. Today the next run folds it. That is a data-loss mode the current design does not have. | 12,780 files today and 63,900 at five parallel, and a new way to lose rows | Carmack |
| 11.R3 | Keep the head and add a merge driver | A union of two heads stacks rows the fold exists to collapse, and a stale folder's head deletes rows the tip has | One `.gitattributes` line, against silently wrong ledgers | Fowler |
| 11.R4 | Split only the ledgers whose settlement key contains `run_id` | Decision 11.3 - it splits nothing, because two jobs of one run write one key | A partial migration that still has two writers on one file | Fowler |

### Row 12 - A closed day folds to one file

- **Scope:** a day past the live window folds once into `settled.csv`, and the writer files it read are deleted.
- **Files touched:**
  - `backend/idhazh/day_shards.py`
  - `backend/idhazh/stages/compact.py`
  - `backend/idhazh/paths.py`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `.github/workflows/digest.yml`
  - `docs/concepts/growing-reads.md`
  - `backend/tests/fixtures/day-shards/closed-day/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, the contract drift gate. CI - the full suite.
- **Oracle:** two branches fold the same closed-day fixture and merge at exit 0 with identical bytes; a third folds it with one extra straggler, conflicts, and ends with the tip's `settled.csv` and the straggler intact beside it. **It cannot settle** the real straggler rate, which is why 12.3 makes a straggler cost one file rather than a repair.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 12.1 | `run.settled_fold_after_days`, default 7. A day older than this has a frozen input set, so two folds emit byte-identical adds and byte-identical deletes (B1) and the fold needs no owner - it has no disagreement to have. | Carmack |
| 12.2 | **This is what stops the repository's cost rising with the run rate.** With it, `state/` settles at about 2,900 files today and about 4,300 at five parallel runs, against 21,400 and 107,000 without. `git add state` is 2.4 s rather than 17.6 s, and the prerendered console build opens 896 files rather than 7,280. | Carmack |
| 12.3 | **A day that already carries `settled.csv` is never folded again.** A straggler arriving afterwards stays a writer file for ever and costs one file. That is cheaper and safer than any repair. | Carmack |
| 12.4 | `settled.csv` is **derived** under contract rule 2. On a conflict the tip's copy wins whole and this job's fold of that day is abandoned, which restores both the tip's file and any writer file this job's fold deleted. Nothing is lost: the tip's fold read the same input set or a subset, and abandoning restores the difference. | Fowler |
| 12.5 | `settled.csv` reads at attempt 0 - the lowest - exactly as the head does today, because every row in it has already won its settlement and any straggler is by definition later. | Fowler |
| 12.6 | The Guardrail #12 declaration is updated in the same commit: the read is bounded by the fold window times writers-per-day, and by nothing in the archive. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 12.R1 | Never fold; accept one file per writer for ever | `git add state` at 88 s and checkout at 4.3x, both rising with the run rate for ever, in a design whose premise is that the file count is bounded | One verb and one knob saved, against an unbounded repository | Carmack |
| 12.R2 | A compacted read-side artifact instead | It would be derived, so it is rebuilt from the tip by every run - a second two-writer file introduced to fix a two-writer file | A new artifact, its prune and its schema, for a worse shape | Carmack |
| 12.R3 | Give the fold its own job with its own concurrency group | A group is a lock, and the owner's intent is no lock. The fold does not need one - a frozen input set makes two folds agree. | One workflow, and the thing the plan exists to remove | Carmack |

### Row 13 - The head goes

- **Scope:** delete the head-reading path everywhere - the reduce that wrote one, and the single-file branch in both walkers.
- **Files touched:**
  - `backend/idhazh/stages/compact.py`
  - `backend/idhazh/day_shards.py`
  - `backend/idhazh/ledger.py`
  - `frontend/src/lib/server/payload.ts`
  - `backend/tests/fixtures/day-shards/both-shapes/`
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, `npm --prefix frontend run check`. CI - the full suite.
- **Oracle:** the row-5 fixture with its `<DD>.csv` half removed still reads; the test that exercised the file branch goes red first, then is deleted with the branch. **It cannot settle** that no external tool reads a head - nothing outside this repository does.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 13.1 | Dead code that can still be called is a second answer waiting to be given. | Fowler |
| 13.2 | Separate from row 11 so row 11 stays revertible on its own. This is the whole reason it is its own PR and its own wave. | Fowler |
| 13.3 | No schema moves and no version is stamped. Say so in the PR body so a reviewer does not go looking. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 13.R1 | Leave the file branch as a fallback | A fallback nothing exercises is a path nothing tests, and it can still be reached | Four lines kept, against a second reader of a shape that no longer exists | Fowler |

### Row 14 - The concurrency group goes

- **Scope:** delete `concurrency: group: digest` from `digest.yml`.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_triggers.py`
  - `docs/architecture/publishing/committing.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_triggers.py`. CI - the full suite. Then one observed pair of overlapping runs on the live schedule.
- **Oracle:** two digest runs dispatched to overlap both reach a green `assemble` and both publish, with neither losing a block. **It cannot settle** the behaviour at higher parallelism - that is what row 4's printed attempt line collects over time.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 14.1 | The group is a lock doing load-bearing work it was never designed for, and it manufactures the staleness it appears to prevent: run `35660521768` waited 46 minutes in that queue and then folded a 46-minute-old store. | Carmack |
| 14.2 | It gives no protection worth having either - GitHub keeps one pending run and silently cancels the older, so a second dispatch during a long run disappears with no error anywhere. | Fowler |
| 14.3 | **This is last, not first.** Removing the rail before the partition lands multiplies every failure mode the plan exists to remove. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 14.R1 | Keep the group and raise its queue depth | GitHub does not offer a queue depth. One pending run is the whole of the feature. | Nothing to build, because there is nothing to build | Carmack |
| 14.R2 | Replace it with a narrower group, per date | Two runs of one day are exactly the case the owner wants parallel | One line, against the intent | Carmack |

## Section 3 - What nobody asked, and it outranks this plan

Two findings came out of this work that this plan does not fix. Both are measured, both are reader-facing, and both need a plan of their own. Section 0f lists the four things this plan must not do, or that plan gets harder.

**GitHub drops a quarter of the slots.** 48 of 65 scheduled slots produced a run over 2026-09-09 to 2026-09-21 - 26 percent lost. 2026-09-19 published nothing at all. No concurrency design touches this, because the run never exists. More cron slots is the only lever, and it is free.

**The site never says it is behind.** A day the pipeline broke and a quiet Sunday both read "0 stories", and a missing day's page says *"the day it names was never published"* - the same sentence a mistyped address gets. `run.json` knows which it was. The three sentences the page owes a reader are: *"We tried to publish 19 September and the run did not finish. Nothing from that day is here."*; *"No run was scheduled for 19 September."*; and *"We ran on 19 September and found nothing worth publishing."* Plus one more on a live day: *"Last updated 06:47 UTC. The 10:20 update has not arrived."*

## Section 4 - Where the evidence lives

The design rationale belongs in [`docs/architecture/publishing/committing.md`](../docs/architecture/publishing/committing.md), which already owns the question of how a run's rows reach the repository, not in this file. This plan tracks rows; that page holds the reason.

Every count in this file is dated 2026-09-22 and describes a growing collection. Re-measure before quoting one, and scope a migration by the property - every committed head of these trees - never by the cardinal.
