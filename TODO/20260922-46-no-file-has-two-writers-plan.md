# No file has two writers

**Last Updated**: 2026-09-22
**Level**: 5 (row 11 moves a persisted contract and migrates committed data; every other row is named at its own level in section 1)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

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

**A closed day is where a fold is still safe.** A head conflicts because its input set is not frozen - a stale folder sees fewer writer files and emits different bytes. **Two folds that read the same input set emit byte-identical adds and deletes, which B1 proves merges at exit 0.** A fold that read a different input set is not smoothed over; it is refused (rule 1a). That is the whole of why row 12 needs no owner.

**What the push actually costs, measured on run `35701213155`.** `Assemble and publish` - the rebuild - is **5 seconds**. `Commit the day` is **11 seconds**. The `assemble` job ran **1.8 minutes of its 20-minute timeout**, so 18.2 minutes were spare. Every argument in this plan about moving work out of the push window is settled by those three numbers: there is 5 seconds to win inside a job using 9 percent of its budget, and the rows are argued on correctness instead.

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

### Rule 1 - Every committed path is one of three classes, and no path is in two

| Class | What it means | How a race ends |
| --- | --- | --- |
| **written-once** | The filename carries `<run_id>-<attempt>-<job>-<shard>`. No process rewrites it or deletes it except retention and the closed-day fold (rule 1a). | Two writers cannot name one file, so there is no race. |
| **derived** | Content is a function of other jobs' output. Named in `idhazh.paths.DERIVED`. Handed back to the tip before the rebase and rebuilt. | The rebuild wins. Never text-merged, never resolved by identity. |
| **union-safe** | Append-only rows, `merge=union`, and a **named read-side property that makes a repeat change no answer**. | Both sides land, the reader settles. |

*Test (contract tier): for every path a production stage writes, exactly one of `idhazh.paths.is_written_once(path)`, `path in idhazh.paths.DERIVED` and `path in idhazh.paths.UNION_SAFE` is true. The test enumerates the writers from `idhazh.paths` itself, never from the tree and never from a hand-written fixture - nothing in this plan walks `state/`.*

**A third class is not a loophole; it is what the tree already is.** Six committed stores are append-only with an earliest-wins or key-settled read, and forcing them into written-once would migrate data for no gain. What the class costs is the discipline of naming the property: `union-safe` with no sentence saying why a repeat is harmless is `derived` written badly. Table C2 names all six.

**The three classes are closed, and that is what makes this design survive the repository growing.** A tree that appears after this plan was written gets a class, not a redesign: it either names itself, or it is rebuilt from the tip, or its repeat changes no answer. There is no fourth thing a committed file can be. So a new store is one line in `idhazh.paths` and, at most, one migration - never a reopened contract. **Counts are re-measured to size a migration, never to decide one** (section 4).

**The declaration lives in `backend/idhazh/paths.py`, not in a workflow string.** An earlier draft said "there is no separate declaration file" and then tested against `REFRESH_PATHS`, a hand-written space-split YAML string whose own header warns that no path may carry a space. That sentence is deleted, and the harness copy of the same list goes with it - three lists that can drift is the defect, not two.

### Rule 1a - A closed day folds once, and a conflicted fold is refused whole

A day older than `run.settled_fold_after_days` folds to one `settled.csv` beside its writer files, and the writer files it read are deleted. **A day that already carries `settled.csv` is never folded again.**

**A conflicted fold is refused, never resolved.** `settled.csv` carries no identity, so rule 3's predicate answers no and the push stops. That refusal is the mechanism, not a gap in it: **per-path resolution is what loses data here.** Taking the tip's `settled.csv` leaves this job's *deletion* of a straggler file standing - a deletion is not a conflict, so git keeps it - and the straggler's rows then exist in no file, at exit 0. Refusing means the whole fold commit dies with the runner, the tip keeps both its `settled.csv` and the straggler, and the next run folds again.

*Test (integration tier): two branches fold one closed-day fixture and merge at exit 0 with identical bytes; a third folds it while a straggler is added on the tip, and the push must exit non-zero with `settled.csv` named - after which the tip still holds every row.*

### Rule 2 - A derived file is never owned

Its content is a function of other jobs' output, so it is handed back to the tip before the rebase and rebuilt from the tip plus this run's own inputs. It is never text-merged and never resolved by rule 3.

*Test (contract tier): the three sets in rule 1 are pairwise disjoint, and their union covers every path-building helper `ledger.py` and the telemetry publishers export.*

### Rule 3 - Identity resolves, everything else refuses

A conflicted path whose name carries this job's identity resolves to what this job wrote. **Every other conflicted path stops the push and names the path and this job's identity.** No third outcome. The resolver then asserts the index holds no unmerged entry, because of B4.

**A derived path cannot reach the resolver** - it was handed back before the rebase - so one appearing there is a defect in `idhazh.paths.DERIVED`, and the push stops naming it. That is the second half of "everything else refuses", not an exception to it.

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

### Table C - the eleven written-once trees, after row 11

One template. Eleven trees. No exceptions. `Writers a day` is measured on the two 5-run days 2026-09-17 and 2026-09-20, counting distinct `(run_id, job, shard)`.

| id | Tree | Path template | Where the date comes from | Writers a day |
| --- | --- | --- | --- | --- |
| C1 | item-health | `state/item-health/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv` | the row's own `date` cell | 20 |
| C2 | host-fingerprint | `state/host-fingerprint/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 25 |
| C3 | scores | `state/scores/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 5 |
| C4 | score-index | `state/score-index/<YYYY>/<MM>/<DD>/<identity>.csv` | `run_id[:10]`, stamped by the writer | 5 |
| C5 | span-rollup | `state/span-rollup/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 20 |
| C6 | day-validations | `state/day-validations/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 4 |
| C7 | traces | `state/traces/<YYYY>/<MM>/<DD>/<identity>.jsonl` | the run's date | 20 |
| C8 | feed-health | `state/feed-health/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 5 |
| C9 | counterfactual-scores | `state/counterfactual-scores/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 5 |
| C10 | digest-fragments | `state/digest-fragments/<YYYY>/<MM>/<DD>/<run_id>.json` | the run's date | 5 |
| C11 | pipeline-tests | `state/pipeline-tests/<ledger>/<YYYY>/<MM>/<DD>/<identity>.csv` | the row's own `date` cell | 0 on a digest run |

`<identity>` is `<run_id>-<attempt>-<job>-<shard>`, spelled once in `ledger._segment_name` and never a second time.

**Four things in this table were wrong in an earlier draft and are corrected here.**

- **There is no `state/validation/` tree.** `VALIDATION_DIRNAME` is declared in `ledger.py` and nothing has ever filled it. The rows live under `state/pipeline-tests/<ledger>/`, written by the pipeline-tests workflow and not by a digest run. C11 gains a `<ledger>` level and contributes zero files to a digest day.
- **Traces already carry run identity.** They are `state/traces/<Y>/<M>/<DD>-<run_id>-<shard>.jsonl` today, so the 2026-08-29 ordinal defect is not their problem. What they lack is `attempt`, so a re-run overwrites its own first attempt. That one element is the whole of what row 11 changes here, and there is no `<ledger>` level.
- **span-rollup moves from month grain to day grain**, so `month_partition.month_files` stops being a state-ledger walker and keeps only its `frontend/public/` callers.
- **score-index gains no date column.** `segment_dates_from_run` and `dates_from_run` are deleted; the writer already knows `run_id[:10]`.

Three names are reserved, each with its removal condition on the line that declares it:

- `settled.csv` - rule 1a's closed-day fold. **Derived.** Sorts below every writer file, because a writer's attempt starts at 1 and 0 is a place no writer can take.
- `before-partition.csv` - what the migration writes for bytes that predate identity. A committed head is many runs already merged, so it has no identity to stamp. **Removal condition: it goes when the oldest committed day is newer than the migration date.**
- `repair-<YYYYMMDDTHHMMSSZ>.csv` - what `rebuild_index` writes as an operator utility. One add, never a rewrite. **Removal condition: it goes when `rebuild_index` is deleted.**

### Table C2 - every other committed tree, classified

Rule 1's test is red on day one unless every writer is classified. These are the ones that are not written-once.

| id | Path | Class | Merge attribute | Writer | Row |
| --- | --- | --- | --- | --- | --- |
| P1 | `state/<tree>/<Y>/<M>/<DD>/settled.csv` | derived | none | the closed-day fold | 12 |
| P2 | `state/seen/<Y>/<M>/<DD>.csv` | union-safe | **gains `merge=union`** | `plan` | 8 |
| P3 | `state/published/<Y>/<M>/<DD>.csv` | union-safe | `merge=union` | `assemble` | 11 - leaves `REFRESH_PATHS` |
| P4 | `state/visual-prunes/<Y>/<M>/<DD>.csv` | union-safe | `merge=union` | `assemble` | none |
| P5 | `state/feed-retirements.csv` | union-safe | **gains `merge=union`** | `plan` | 15 |
| P6 | `state/llm-council/shard-outcomes/<Y>/<M>/<DD>.csv` | union-safe | **gains `merge=union`** | the council workflow | 15 |
| P7 | `state/content-similarity-judge/{metrics,merge-line-holdout-scores,scored-pairs,fitted-thresholds}/<Y>/<M>/<DD>.csv` | union-safe | **gains `merge=union`** | the judge workflow | 15 |
| P8 | `state/content-similarity-judge/holdout-pairs.csv` | person-written | `merge=text` - **stays** | a person | none |
| P9 | `state/day-metrics/<Y>/<M>/<DD>.json` | derived | none | `assemble` | 16 |
| P10 | `state/telemetry-aggregate/<YYYY-MM>.csv` | derived | none | `prune-state` | none |
| P11 | `state/score-archive/<Y>/<M>.csv` | derived | none | `prune-state` | none |
| P12 | `state/llm-council/score-distribution.json` | derived | none | the council workflow | none |
| P13 | `state/llm-council/archive/<stamp>.json` | written-once | none | the council workflow | none - the UTC stamp is its identity |
| P14 | `frontend/public/digest/<Y>/<M>/<DD>/digest.json` | derived | none | the fold | 9 |
| P15 | `frontend/public/digest/<Y>/<M>/<DD>/run.json` | derived | none | `assemble` | 9 |
| P16 | `frontend/public/digest/<Y>/<M>/<DD>/<item_id>.{svg,json}` | written-once by item id | none | the visuals job | none - `drop_raced_assets.py` is the collision rule and it stays |
| P17 | `frontend/public/{telemetry,assist/index,source-health.json,console,run-days,day-metrics,machine,span-rollup,run-timeline}` | derived | none | `assemble` | none - **these are what keeps `REGENERATE_COMMAND` for ever** |
| P18 | `corpus/*.{jsonl,json,txt}` | replayed | `text eol=lf`, deliberately not union | the harvest step | 7 - moves to its own ref |

**Every union-safe row names the property that makes a repeat harmless.** A class without it is `derived` written badly.

| id | Tree | Why a repeat changes no answer |
| --- | --- | --- |
| Q1 | `state/seen` | `load_seen` keeps the earliest first-seen stamp per key, so a second copy of a row moves no date |
| Q2 | `state/published` | `load_published` keeps the earliest publication date per address |
| Q3 | `state/visual-prunes` | `append_visual_prunes` settles the day file on `(date, run_id)` |
| Q4 | `state/feed-retirements.csv` | the key is `(source_id, retired_on)`, and a retirement is a statement about a day |
| Q5 | `state/llm-council/shard-outcomes` | one row is one shard of one run, and no shard says anything about another |
| Q6 | the four judge trees | one row is one measurement of one pair on one day; the reader keys on the pair and takes the newest |

### Table D - the two new modules

| id | Module | The one question it answers | Public surface |
| --- | --- | --- | --- |
| D1 | `backend/idhazh/day_shards.py` | What does a day directory of writer-owned files read back as? | `SETTLED_NAME: Final = "settled.csv"`; `shard_files(root, *, days) -> Iterator[Path]`; `settled_rows(root, key, model, *, days) -> list[dict[str, str]]` |
| D2 | `backend/idhazh/paths.py` | Which committed paths are written once, which are derived, and which are union-safe? | `DERIVED`, `UNION_SAFE`, `is_written_once(relpath)`, `refresh_paths(*, day_dir) -> str` |

`settled_rows` runs the identical three-case fold `_settle` runs today - join, supersede, repeat. **`parse_segment_name` is not touched and keeps raising on an unknown name**; `day_shards` owns the one branch that lets `settled.csv` through:

```python
def _order(path: Path) -> tuple[int, str]:
    """Reading order inside one day directory.

    `settled.csv` sorts below every writer file. A writer's attempt is the run's
    own GITHUB_RUN_ATTEMPT, which starts at 1, so attempt 0 is a place no writer
    can take - and it is the right place, because every row in `settled.csv` has
    already won its settlement and any straggler is later.
    """
    if path.name == SETTLED_NAME:
        return (0, path.name)
    return (ledger.parse_segment_name(path).attempt, path.name)
```

**The sort key is the relative path, never the bare filename.** `settled.csv` has the same basename in every day directory, so a reader spanning two days has no total order without it, and a non-total order here is a silently wrong answer rather than a flake: only two keys carry a preference rule, and every other key settles by position.

### Table E - the contract models that move

| id | Row | `__schema_stem__` | `version` | The one-line changelog entry |
| --- | --- | --- | --- | --- |
| E1 | 6 | `run-manifest` | `2026-09-22` | `runs may be numbered with gaps, and two runs may not share an ordinal` |
| E2 | 6 | `digest-day` | `2026-09-22` | `runs may be numbered with gaps, and two runs may not share an ordinal` |
| E3 | 9 | `digest-run-fragment` (new) | `2026-09-22` | `first version` |
| E4 | 9 | `digest-day` | same-day revision of E2 | `items_failed may be null; generated_at is the newest run's completion, not a fold clock` |
| E5 | 9 | `digest-view` | same-day revision | `generated_at is the newest run's completion, not a fold clock` |

**Rows 5, 11, 12, 13, 15 and 16 move no stem and stamp no version.** A path is not a schema field and no row shape changes. Say so in each PR body so a reviewer does not go looking.

**The new fragment model**, declared before any logic reads or writes it:

- Class `DigestRunFragment`, module `backend/idhazh/contracts/digest_run_fragment.py`, `__schema_stem__ = "digest-run-fragment"`.
- Path `state/digest-fragments/<YYYY>/<MM>/<DD>/<run_id>.json`. **Not under `frontend/public/`** - see row 9.
- Required: `run_id`, `completed_at`, `failed_item_ids: list[str]`, `partial: bool`, and the item block.
- **Sort key, required: `__sort_key__: ClassVar = ("completed_at", "run_id")`.** `completed_at` is landing order; `run_id` breaks a same-second tie and is unique by construction. Without the tie-break two folds emit different bytes, which is the whole defect.

**The read-side migration for a payload yesterday's run wrote.** `DigestRunRef.run_id` and `.completed_at` are optional. The committed days carry neither. The fold, meeting a `digest.json` with `runs` and no sibling fragment directory, **leaves it alone and emits it unchanged** - null reads as "this day predates fragments", and `DayNotice` already guards on absent runs. That is the migration, in one branch.

## Section 0h - What this plan costs to run

Measured 2026-09-22 from GitHub job step timestamps.

| id | Reading | What it means |
| --- | --- | --- |
| R1 | `ci.yml` is the only workflow firing on a pull request; it runs 7 jobs; a code pull request measures 3.8 to 8.6 min (n=8, median 7.7) and a docs-only one 0.6 min | Ten pull requests at one run plus one merge run is a **139-minute floor**, about 280 minutes at two pushes each |
| R2 | `cancel-in-progress` is on for pull requests | Only the last push of a branch counts, so a rework is free |
| R3 | Three pull requests in flight is 21 concurrent jobs against the 20 allowance | A queue, not a failure (Guardrail #2) |
| R4 | The browser and whole-day jobs already run on every pull request | Only PR G and PR C name an **extra** hand-driven smoke |
| R5 | Two rows need the live schedule: PR C needs the overnight quiet window, measured at **4 h 48 min** between the 18:20 run finishing and 02:20; PR I needs two overlapping runs, about 3.5 h | Neither is CI time. Both are a person's calendar |
| R6 | The `assemble` job uses **1.8 of its 20 minutes**; a work shard uses up to 190.6 of 200 | Nothing in this plan moves either close to a cap |

**Parallel N = 3, not 4.** `digest.yml` is what serialises this plan - six of the ten pull requests write it - and after the file lists are made disjoint wave 1 holds three. Waves 2 onward hold one or two by construction. A fourth slot would idle.

## Section 1 - Status Reckoner

**A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch. `Parallel-group` is the wave; readiness is still computed from `Depends-on` plus disjoint `Files touched` ([execute-a-plan.md](../docs/how-to/execute-a-plan.md#parallel-fan-out)).

| # | Row title | PR | Depends-on | Parallel-group | Status | Level | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | Every job that commits keeps its record when the push fails | Z | - | 0 | DONE | 1 | p46r3 | - | - |
| 1 | The last state writer with no group gets one, and the failure stops lying | A | 3 | 1 | DONE | 1 | p46a | - | GitHub Copilot |
| 2 | The rebase stops guessing that a drained directory was renamed | A | 3 | 1 | DONE | 1 | p46a | - | GitHub Copilot |
| 4 | The push loop becomes a deadline and says what each attempt cost | A | 3 | 1 | DONE | 2 | p46a | - | GitHub Copilot |
| 16 | The day's metrics file is declared derived | A | 4 | 1 | PENDING | 2 | - | - | - |
| 5 | A day directory reads back as settled rows | B | - | 1 | PENDING | 3 | - | - | - |
| 6 | The one rule that needs a sequence is deleted | F | - | 1 | PENDING | 5 | - | - | - |
| 7 | The corpus moves to its own ref | H | 1, 2, 4 | 2 | PENDING | 4 | - | - | - |
| 8 | An unowned path stops the push and names itself | E | 1, 2, 4 | 2 | PENDING | 4 | - | - | - |
| 9 | The published day is folded from per-run fragments | G | 5, 6, 7 | 3 | PENDING | 5 | - | - | - |
| 10 | One clock, and a label on every block that landed | G | 9 | 3 | PENDING | 3 | - | - | - |
| 11 | The day directory is the ledger | C | 5, 8 | 4 | PENDING | 5 | - | - | - |
| 12 | A closed day folds to one file | C | 11 | 4 | PENDING | 3 | - | - | - |
| 15 | The plan job's own ledgers stop being shared files | C | 11 | 4 | PENDING | 3 | - | - | - |
| 13 | The head goes | D | 11, 12 | 5 | PENDING | 3 | - | - | - |
| 14 | The concurrency group goes | I | 7, 9, 13, 15 | 6 | PENDING | 4 | - | - | - |

Rows are listed in wave order. **Row 3 keeps its number and runs first**: it is the incident fix, it is four lines, and holding it behind a rewrite of the commit script is holding the only thing that stops today's failure.

### Table F - the wave map, and what makes each wave disjoint

**Ten pull requests in seven waves.** `digest.yml` is what serialises this plan - six of the ten write it - so the pool is three wide and only wave 1 fills it.

| id | Wave | In flight | Why their files are disjoint |
| --- | --- | --- | --- |
| F1 | 0 | **Z alone** | Four `if: always()` lines in `digest.yml` and one workflow test. Merge it the hour it is written; everything after it assumes it landed. |
| F2 | 1 | **A, B, F** | A owns `commit-and-push.sh`, `digest.yml`, `measure.yml`, `config/idhazh.json`, `contracts/app_config.py`, `schemas/app-config.schema.json`, `frontend/src/contracts/app-config.ts`, `backend/idhazh/paths.py` and `backend/tests/workflows/`. B owns the backend read side and the server-side TypeScript walkers and **declares no config file** - row 5's retention knob moved into A for exactly this reason. F owns two contract modules, their schemas, the generated frontend contracts and `placement.py`. |
| F3 | 2 | **H, E** | H must edit `digest.yml` (the harvest step and the `corpus` argument on the commit call), `prune.yml`, and `test_staged_paths.py`, `test_triggers.py` and `_harness.py` - all of which are A's, so it waits for A. E is `commit-and-push.sh`, `.gitattributes` and `test_daily_commit_steps.py`, also behind A. H and E share nothing with each other. |
| F4 | 3 | **G alone** | The published payload, three contract modules, three page components and `digest.yml` - behind B, F and H. |
| F5 | 4 | **C alone** | **The one PR that must land alone.** It moves every committed ledger and rewrites every producer's write path. A digest run in flight when it merges pushes an old-shape head the migration missed - a timing call for a person, not a code problem. The measured quiet window is 4 h 48 min. |
| F6 | 5 | **D** | `compact.py`, `day_shards.py` and both walkers, behind C. |
| F7 | 6 | **I** | `digest.yml`, behind everything. Deleting the group is the last thing, not the first. |

PR [#1041](https://github.com/miztiik/yen-idhazh/pull/1041) is already open and merges as-is: it lowers the failure rate until PR C lands, and reverting it is a second change for no gain.

### Table G - watch these two

Risk of a bad day per unit of value, worst first. The rest of the list is in wave order above.

| id | PR | Why it is here |
| --- | --- | --- |
| G1 | **C** | It migrates every committed ledger, and a revert leaves the tree migrated. A bad day here is unreadable committed data. |
| G2 | **A** | It rewrites the one script whose failure costs a day. |
| G3 | **B** | Lowest risk and the largest share of the plan's value - nothing writes a directory yet, so it cannot change a run. Merge it early. |

## Section 2 - The rows

Rows appear in numeric order. Wave order is Table F.

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

### Row 3 - Every job that commits keeps its record when the push fails

- **Scope:** four `if: always()` lines and one `continue-on-error`, so that no job throws away what it already produced because a push lost a race. Merges alone and first.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_daily_commit_steps.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_daily_commit_steps.py`. CI - the full suite.
- **Oracle:** for every job in `digest.yml` that commits, every step that carries its output to a downstream job or to an artifact is reachable when the commit step fails. Asserted from the workflow file. **It cannot settle** whether the artifact content is correct, only that it is produced.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 3.1 | **`plan`**: the `actions/upload-artifact` step gets `if: always()` and the commit step gets `continue-on-error: true`. **This is run `35660521768`, exactly.** It did not die because rows were lost. It died because a failed push skipped the artifact upload, so the plan never reached the shards. | Carmack |
| 3.2 | **`assemble` keeps nothing today, and an earlier draft said it kept the record.** `Commit the day` has no `continue-on-error`, so every step after it is skipped - including `Build the day's review tree`, whose output the only `if: always()` upload needs. Three steps get `if: always()`: `Retire the ledger shards and the visuals nothing still reads`, `Commit the folded telemetry`, and `Build the day's review tree`. | Carmack |
| 3.3 | **`Commit the day` does NOT get `continue-on-error`.** That marks the step succeeded, so a run that published nothing reads green. `if: always()` on the record-keeping steps keeps the job red **and** keeps the record, which is strictly better. | Fowler |
| 3.4 | `Rebuild the site against the tree that was pushed` and the bundle gate get nothing. They measure a publish that did not happen. | Carmack |
| 3.5 | Measured per job, 2026-09-22: the work shard's commit is already `if: always()` with `continue-on-error: true` and all four of its uploads are `if: always()`, so a failed push costs it nothing. It needs no change. | Carmack |
| 3.6 | This is why no row in this plan parks work on a side branch. The expensive work is protected by artifacts, and the two jobs where it was not are fixed here in five lines. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 3.R1 | Park the output on a side branch when the push fails | A parked branch nothing drains is a graveyard that looks like the work was saved | The drain job, its schedule, and a second place a reader has to look | Fowler |
| 3.R2 | Fold this row into PR A | PR A rewrites the one script whose failure costs a day. This is four lines of pure gain and must not wait for that review. | One merge saved, against holding the incident fix behind a Level 2 rewrite | Carmack |

### Row 4 - The push loop becomes a deadline and says what each attempt cost

- **Scope:** the three-attempt counter becomes a wall-clock deadline with jittered backoff, three failure paths become `continue`, every attempt prints what it spent, and the derived-path list moves out of the workflow into Python.
- **Files touched:**
  - `.github/scripts/commit-and-push.sh`
  - `backend/idhazh/paths.py` (new)
  - `backend/idhazh/cli.py`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `frontend/src/contracts/app-config.ts` (generated)
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_daily_commit_steps.py`
  - `tests/fixtures/paths/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows`, the contract drift gate, and the repository's yaml lint. CI - the full suite.
- **Oracle:** a scripted origin that rejects the first N pushes and accepts the N+1th; the script lands the commit within the deadline and prints one line per attempt whose `window_ms` sums to less than the deadline. **It cannot settle** the real `W` on a runner - that is what the printed line exists to collect.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 4.1 | Deadline `run.push_deadline_seconds`, default 300. Measured on run `35701213155`, `assemble` used 1.8 of its 20 minutes, so 300 s is 25 percent of the timeout and 18.2 minutes were spare. | Carmack |
| 4.2 | Backoff `min(2^(k-1), 8) x U(0.5, 1.5)` seconds, `k` = failures so far. Sleeps run 1, 2, 4, 8, 8, 8. At the measured 11-second window that is about **16 attempts** in 300 s. Multiplicative jitter centred on 1 stops every loser refetching in lockstep, and its spread grows with the backoff, so collisions fall as contention rises. | Carmack |
| 4.3 | Which failure paths change: **`git fetch` fails becomes `continue`** - a transient the deadline is built to ride out, where a broken token costs 300 s of a 6 h budget. **A conflicting rebase whose every conflicted path carries this job's identity becomes resolve, `--continue`, `continue`** - that is row 8's resolver doing its job. Everything else **stays `break`**: an unowned conflicted path (retrying cannot make another writer's file yours), a failed `REGENERATE_COMMAND` (a producer fault against the tip, not a race), and any failure of `hand_back`, `git add`, `git commit --amend`, `git reset --soft`, `discard_noise` or `clear_what_the_tip_will_write_over` (index or filesystem damage, which retrying compounds). | Carmack |
| 4.4 | Six stamps, printed once per attempt to stdout and to `$GITHUB_STEP_SUMMARY`: `push attempt=<n> job=<job> shard=<s> outcome=<landed\|rejected> window_ms= fetch_ms= handback_ms= rebase_ms= rebuild_ms= push_ms=`. The split matters: a single `W` cannot tell a slow rebuild from a slow push. | Carmack |
| 4.5 | **Attempt 1 has no window in the retry model's sense.** There is no `git fetch` before the first `git push`, so its exposure is the whole job - checkout to push, two to three hours - which is not a retry parameter. `W` is defined for attempts 2 and up; attempt 1 is recorded as `outcome=landed\|rejected`, and the first-push success rate is the measurement of its exposure. | Carmack |
| 4.6 | **The number is not committed to a ledger.** Both candidate rows are written by Python before the commit step runs, so neither can carry a number that does not exist until after the push. If a trend is later wanted it is `state/span-rollup`, span name `push`, whose columns already fit with zero schema change - and `assemble` has a second commit step after the first push, so it can carry one for free. | Carmack |
| 4.7 | **4.9 One deadline value does not fit two jobs.** A work shard's wrap-up is `run.shard_wrap_up_minutes` = 12 minutes and the worst shard has already overshot its 188-minute self-bound by 2.6 minutes, so 300 s would be 5 of those 12. The knob keeps its 300 default for `assemble`; the work shard's commit step passes `PUSH_DEADLINE_SECONDS: "120"` in its own `env:` block - 16.7 percent of the wrap-up, four attempts at the capped backoff. **What would change it:** the `push attempt=` line over twenty runs. A first-push success rate above 95 percent means 120 s is almost never spent and the value can rise; below 80 percent means the partition has not landed and no deadline is the right answer. | Carmack |
| 4.8 | **`REFRESH_PATHS` moves into `backend/idhazh/paths.py` and is emitted through `$GITHUB_OUTPUT`, never `$GITHUB_ENV`.** An env var reaches every later step of the job, and `Commit the folded telemetry` is a later step in `assemble` with no `REGENERATE_COMMAND` - the script would refuse on every run with exit 2, silently, because that step is `continue-on-error: true`. The producing step is `id: derived`, runs `python -m idhazh derived-paths --day-dir "$DAY_DIR" >> "$GITHUB_OUTPUT"`, and `Commit the day` consumes it as `REFRESH_PATHS: ${{ steps.derived.outputs.refresh_paths }}` inside its own `env:` block. | Fowler |
| 4.9 | `DERIVED` holds POSIX templates with **one placeholder, `{day_dir}`**, and a contract test asserts no entry holds a second placeholder or a space. Two entries need it - `{day_dir}/digest.json` and `{day_dir}/run.json` - and a static tuple cannot emit them otherwise. | Fowler |
| 4.10 | `COMMIT_REFRESH_PATHS` in `backend/tests/workflows/_harness.py` is **deleted**. With the list generated from `idhazh.paths`, the harness asserts against `DERIVED` itself; its own copy is a third list that can only drift. `EXPRESSION_VALUES` in the same file is a closed-world map and needs an entry for `${{ steps.derived.outputs.refresh_paths }}` in the same commit, or four tests across three workflow modules go red. | Fowler |
| 4.11 | **This row is early, not last.** Rows 9, 11, 12 and 14 all argue from its output. | Carmack and Fowler, converged |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 4.R1 | Keep the fixed three attempts and raise the count | A fixed count is spent instantly under unbounded N, whatever the count. An optimistic rebase-and-push converges in expectation at any commit rate; a counter does not. | Nothing to build, and the loop keeps failing at exactly the rate the owner is raising | Carmack |
| 4.R2 | Add two nullable duration columns to `host-fingerprint` now | The row is written before the push happens, so the columns would always be null | A schema stamp, a changelog line and a migration, for a column nothing can fill | Fowler |
| 4.R3 | Emit `REFRESH_PATHS` into `$GITHUB_ENV` | It poisons every later step in the job and stops the telemetry fold committing, silently, on every run | One fewer expression in the workflow, against a fold that quietly never happens | Fowler |
| 4.R4 | One deadline for every caller | The work shard's reserve and the assemble job's timeout are two budgets with an eightfold difference | One knob instead of one knob and one override, against 5 of the shard's 12 spare minutes | Carmack |

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
  - `tests/fixtures/day-shards/both-shapes/` (new)
  - `frontend/tests/fixtures/day-shards/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, `npm --prefix frontend run test:changed -- --list` then the selected checks, `npm --prefix frontend run check`. CI - the full suite and the drift gate.
- **Oracle:** `day_shards.settled_rows` over a fixture directory holding three writer files that settle on one key at two attempts returns **exactly** what today's `_compact_ledger` returns for the same rows folded into a head. Parity, row for row. **It cannot settle** whether every production caller was moved - that is the enumerated list in decision 5.2, checked by a separate assertion.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 5.1 | `_settle`, `_contested`, `_Held` and `_Waiting` move into `backend/idhazh/day_shards.py`, whose one question is *what does a day directory of writer-owned files read back as*. Identical three-case fold. | Fowler |
| 5.2 | Eleven Python call sites move from `day_files` to `day_shards.shard_files`: `evals/writer.py` `ledger_days`, `records`, `index_days`, `indexed_observations`; `ledger.py` census for item-health and host-fingerprint; `retention.py` `_operator_pass`; `telemetry/prune.py` `_prune_ledger`; and four utilities - `measure_ledgers`, `item_health_provenance`, `server_memory_mark`, `empty_column_census`. | Fowler |
| 5.3 | **`day_partition.day_files` is not touched.** It keeps its callers over `state/published/` and `state/visual-prunes/`, which are not moving, and it keeps refusing a directory loudly. That refusal is now the tripwire that catches a twelfth tree arriving without a plan. | Fowler |
| 5.4 | **The walker reads both shapes** - a `<DD>.csv` file and a `<DD>/` directory. That is what makes this PR inert. Row 13 removes the file branch. | Fowler |
| 5.5 | **The sort key is the path relative to the ledger root, never the bare filename.** `settled.csv` has the same basename in every day directory, so a reader spanning two days has no total order without it - and only two keys carry a preference rule, so a non-total order is a silently wrong answer rather than a flake. | Fowler |
| 5.6 | `day_shards` owns the `settled.csv` branch in its own `_order` helper. **`ledger.parse_segment_name` is not touched and keeps raising** on a name that is neither a writer's nor `settled.csv`. | Fowler |
| 5.7 | `dayShardFiles` gains the directory branch, and its silent skip is **reversed for directories**: a `/^\d{2}$/` directory holding zero readable `.csv` files throws. The silent skip is the one defect in this plan that would ship green - four prerendered console routes drawing zero rows on a passing build. A prerender failure is where that belongs. | Fowler |
| 5.8 | `span-rollup.ts` `readShards` becomes a day-directory reader in the same change, because row 11 moves that ledger from month grain to day grain. | Fowler |
| 5.9 | **score-index gets a prune and no new knob.** It is derived from `state/scores/` and is pruned to exactly the span `retention.scores_full_grain_months` keeps, in the same pass. A derived index that outlives its source is a lookup that misses for ever, and `refresh_index` only ever fills a month with no index - it never repairs a stale one, so nothing would notice. | Carmack |
| 5.10 | **This PR declares no config file.** The day-validations prune needs a new knob and therefore rides PR C, where that tree moves anyway. Without this split, PR B and PR A collide on `config/idhazh.json`, `schemas/app-config.schema.json` and the generated `app-config.ts`, and wave 1 stops being parallel. | Carmack |
| 5.11 | The Guardrail #12 declaration is rewritten in the same commit as the walker it describes: the console reads a fixed 91-day window, the folded days cost one file each, and only the live days cost one file per writer - so the read is bounded by `run.settled_fold_after_days` times writers-per-day, and by nothing in the archive. | Fowler |

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
  - `tests/fixtures/contracts/run-manifest/runs-with-a-gap.json` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests/contracts`, the contract drift gate, `npm --prefix frontend run check`. CI - the full suite.
- **Oracle:** a manifest whose runs are numbered 1, 2, 4 **and which carries an item introduced by run 4** validates where it previously raised; a manifest with two runs both numbered 3 raises; and every other clause still raises on its own fixture. **It cannot settle** that no reader assumed contiguity - decision 6.5 is the enumeration that answers that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 6.1 | `_order_is_global_and_append_only` holds eight rules and **exactly one** needs a writer to know what another writer did: `runs are numbered from 1 without gaps`. It goes. | Fowler |
| 6.2 | **Deleting that one line is not enough, and an earlier draft said it was.** `max(introduced) > len(self.runs)` and `max(revised) > len(self.runs)` are contiguity checks wearing a bounds-check name - they are only equivalent while the ordinals are 1..N. Both become membership against the recorded set: `recorded = {run.n for run in self.runs}`, then `if not recorded.issuperset(introduced): raise`, and the same for `revised`. | Fowler |
| 6.3 | **A distinctness clause is added and it is load-bearing.** With contiguity gone, nothing else stops two `DigestRunRef`s numbered 3, and the `items_added` clause below would count one block's items against both. `if len(recorded) != len(self.runs): raise ValueError("two runs cannot share an ordinal")`. | Fowler |
| 6.4 | The same three edits apply to `RunManifest._runs_are_append_only_and_addressed_by_date`. Its `run_id` uniqueness and date-prefix checks stay. | Fowler |
| 6.5 | **`n` is read in four places, not one.** The page footer, the console's operator line, the server payload reader, and `day-metrics.revision`. Row 6 states the new meaning once in `placement.py`'s docstring and corrects the console string from `run` to `block`; nothing else moves. | Jony |
| 6.6 | Two docstring sentences in `placement.py` become false and are corrected in the same commit: *"the score's own first pick among the stories the first run published"* becomes *the first block to land*, and *"the blocks keep the order the runs published them in"* becomes *the blocks keep the order they landed in*. One line is added saying `introduced_by_run` is arrival order at fold time. | Jony |
| 6.7 | **What an operator loses**: the rule caught a producer that skipped a block. After row 9 the fold assigns `n` by `enumerate()` over arrival order, so contiguity holds by construction and the validator checks the fold's arithmetic instead of a writer's claim. The skipped-block case is then caught by the fragment count. | Fowler |

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
  - `tests/fixtures/resolver/` (new)
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
  - `tests/fixtures/digest-fragments/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, the contract drift gate, `npm --prefix frontend run check`. CI - the full suite. Browser smoke per CLAUDE.md section 12, shared with row 10.
- **Oracle:** three fragments, two sharing a `completed_at` second, folded in every arrival permutation, emit **byte-identical** `digest.json`. **It cannot settle** that a day predating fragments still reads - that is the separate parity case in decision 9.6.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 9.1 | **The fragment does not go under `frontend/public/`.** Everything there is copied verbatim into the build output, so as drafted the fragments would be served, crawlable, and a second full copy of every story on a site Pages refuses over 1 GB. Path: `state/digest-fragments/<Y>/<M>/<D>/<run_id>.json`. **What enforces it is absence** - there is no URL, so there is nothing to index and nothing for a reader to land on. A `robots.txt` disallow would be a request to a crawler, not a control, and would leave the bytes in the deploy. | Jony |
| 9.2 | `digest.json` remains the only thing the site build reads, and the fold writes it temp-file-plus-rename. A half-written day file is then never readable, so a build sees either the previous fold's file or the new one and the archive count can never disagree with the day page. | Jony |
| 9.3 | **Order by landing, whole block at a time, never interleaved.** First sight, run start, run completion and score each break the append-only promise by moving a story a reader was part-way through. The sort is `__sort_key__ = ("completed_at", "run_id")`, both required. | Editor and Jony, converged |
| 9.4 | A fold that sees fewer fragments emits a valid **prefix**; the next fold appends the rest. The append-only promise is kept exactly, because the fold inherits position rather than computing a key. Two folds over the same fragment set emit identical bytes, which B1 makes free. | Fowler |
| 9.5 | **`generated_at` is the maximum `completed_at` across the fragments folded, not the fold's own wall clock.** A wall clock means two folds of one fragment set emit different bytes, which turns every re-fold into an add/add conflict on the one file a reader actually opens - the defect this plan exists to remove, re-introduced on the published side. A max over the set is monotonic and deterministic. **Both descriptions are rewritten and a changelog entry is appended in the same commit** (Table E). **The one case this gets wrong**: a rewrite that adds no run - a retention pass deleting an old drawing - changes the payload and leaves `generated_at` where it was, so a session already holding that day can draw a path that was just deleted. That costs one broken drawing in one open tab until a reload, against a conflict on every re-fold, which costs the day for every reader. | Jony and Fowler, converged |
| 9.6 | The fold, meeting a `digest.json` with `runs` and no sibling fragment directory, **leaves it alone and emits it unchanged.** Null `run_id` and `completed_at` read as "this day predates fragments". That is the whole read-side migration, in one branch. | Fowler |
| 9.7 | **`items_failed` and `partial` are two readings of one set, and the fold derives both from that set.** `failed = union(failed_item_ids) - {published item ids}`; `items_failed = len(failed)`; `partial = bool(failed)`. An earlier draft had `partial = any(fragment.partial)`, which is monotonic - so an article that failed at 02:20 and landed at 06:20 gives `partial=True` beside `items_failed=0`, a payload the contract refuses. `DigestDay.items_failed` becomes `int \| None`, matching `DigestView`, and the validator skips both its `items_failed` clauses when the value is null. | Jony and Fowler, converged |
| 9.8 | `_order_is_global_and_append_only` guards `partial == (items_failed > 0)` and `len(items) + items_failed > items_planned` on `items_failed is not None`. Null constrains nothing; it is the reader's "not known". | Fowler |
| 9.9 | `assemble.run_n_for` is **deleted here**, not in row 6. Row 6 removes the rule that made the claim load-bearing; this row removes the claim. The fold assigns `n` by `enumerate()` over the sorted fragments. | Fowler |
| 9.10 | `retention.py` prunes `state/digest-fragments/<day>/` on the same rule as the day itself. Without it the fragments are an unbounded second archive. | Jony |
| 9.11 | **The rebuild does not leave the push window and no row should try to move it.** Nine `frontend/public/` projections stay derived - the telemetry shard, the search index, source-health, the four console payloads, the run-days tree and the run timeline - and `idhazh assemble` is the only producer of any of them. Measured on run `35701213155`, the whole rebuild is **5 s inside an 11 s commit step, in a job that used 1.8 of its 20 minutes**. Row 9 removes two paths from that list, which is a correctness change - a day file is no longer text-merged - and buys no measurable time. An earlier draft claimed it took the rebuild out for good; 17 paths remained. | Carmack |
| 9.12 | **There is no skip-the-rebuild guard.** One was drafted and it carries a silent lost day: it would run after `hand_back` has already `git rm`ed every path this attempt introduced, so on the first publish of a day - where the tip has no `digest.json` - skipping the rebuild leaves a commit with no day in it and the script **exits 0**. That is the exact failure the script refuses at startup, *"a refresh with no rebuild discards work"*, reached at attempt 2 instead. It is one `git diff --quiet` to save 5 seconds against a silently unpublished day. Deleted. | Carmack |

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
  - `.github/workflows/measure.yml`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `docs/architecture/publishing/committing.md`
  - `docs/concepts/partitions.md`
  - `tests/fixtures/day-shard-migration/`
  - `tests/fixtures/paths/`
  - `tests/fixtures/traces/` (new)
  - `tests/fixtures/pipeline-tests/two-candidates/` (new)
  - every committed file of the eleven trees in Table C, plus `state/day-validations.csv`
- **Acceptance gates:** local - `python -m pytest backend/tests`, the contract drift gate, `npm --prefix frontend run check`, and the full browser smoke in decision 11.9. CI - the full suite.
- **Oracle:** the migration reads its own output back through the pipeline's own reader and compares **row for row** against what came out of the old heads; it refuses to install a tree it cannot read back. **It cannot settle** whether a run in flight during the merge pushes an old-shape head - that is the quiet window in decision 11.8, and it is a person's call.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 11.1 | **Producers write the day path directly. There is no split-and-rename.** The segment directory existed because the head had one shape and many writers; once the day directory takes the writer-identity name, the segment directory *is* the day directory and only the parent changes. `ledger.segment_path` is renamed `ledger.day_shard_path` and gains the three date arguments. `_segment_name` is unchanged. | Fowler |
| 11.2 | **Nothing settles on disk.** Settlement happens at read time in `day_shards.settled_rows`, which row 5 already shipped. Cross-run collapse survives - `OBSERVATION_KEY` has no `run_id`, so two runs scoring one article do settle, just in the reader rather than in the fold. | Fowler |
| 11.3 | **A key containing `run_id` does not make a ledger safe to leave unsettled.** `ITEM_HEALTH_KEY` contains it and the work shard and `assemble` both write that key for one run from two jobs; `attempt` is in no key at all, by design, because a re-run is meant to correct. So every ledger can have two files holding one key, and a rule that splits on `run_id` splits nothing. | Fowler |
| 11.4 | Table C is the authority on every path. **Three corrections an earlier draft got wrong**: there is no `state/validation/` tree; traces already carry `run_id` and only lack `attempt`, with no `<ledger>` level; and span-rollup moves from month to day grain, so `month_partition.month_files` keeps only its `frontend/public/` callers. | Carmack |
| 11.5 | `refresh_index` and `_fill_index` are **deleted** - they exist to back-fill a day whose rows predate the index, and after the migration no such day exists. `recorded_observations` drops its `refresh_index` call. `rebuild_index` survives as an operator utility writing `repair-<YYYYMMDDTHHMMSSZ>.csv`, one add, never a rewrite. Also deleted: `ledger.segment_dates_from_run`, `_HeadShape.dates_from_run`, and `CompactionReport.lag_days` and `.rows_waiting_before`, both of which derive their date from a segment filename. | Fowler |
| 11.6 | `state/day-validations.csv` becomes tree C6 on the same template, and gains `retention.day_validation_keep_months`, default 14, matching every other retention knob. A receipt for a day the archive no longer holds cannot be read. Its only reader, `stages/validate_days.py`, gains `day_shards.settled_rows` on `("date",)`. | Carmack |
| 11.7 | The migration writes one fixed name per day, `before-partition.csv`, with its removal condition on the declaring line. A committed head is many runs already merged, so it has no identity to stamp, and a synthetic identity would fail rule 1's own test. Extend `migrate_to_day_shards.py`, which already did this repository's last grain change and already refuses to write a tree it cannot read back: *"a migration that writes an empty tree and unlinks its source is a delete with exit 0."* | Fowler |
| 11.8 | **This is the one PR that lands alone, and it needs a quiet window.** A digest run in flight when it merges pushes an old-shape head the migration missed. Measured: the longest gap in the schedule is **4 h 48 min**, between the 18:20 run finishing and 02:20. That is a timing call for a person - ESCALATE trigger 1. | Carmack |
| 11.9 | Browser smoke, per CLAUDE.md section 12, against a checkout whose `state/` is in the new shape, after asserting the preview serves *this* build: `/console/`, `/console/machine/`, `/console/model/` and `/console/voices/` each draw non-zero rows; one digest day page as the cross-page smoke; zero new `[error]` and zero new `404` on each; and the same six with `state/item-health/` renamed away, where every page must render rather than white-screen. On `/console/machine/` scroll the whole page first and take a viewport screenshot - an element screenshot never settles there. | Jony |
| 11.10 | **Cost, measured 2026-09-22.** Retention is **14 months, about 426 days**. Writers a day is **99**, not the 50 an earlier draft used - span-rollup's 20 was read as a per-run figure, host-fingerprint is 25 not 16, and traces and day-validations were missing. Without row 12 that is **about 33,800 files at today's rate and about 169,000 at five parallel runs a slot.** With row 12 it is **about 3,200 and about 6,000.** `state/` ships zero files to the site - verified, `frontend/build` holds no `state` path - so the 1 GB Pages cap is untouched. | Carmack |
| 11.11 | **An earlier claim is deleted as falsified, not softened.** History bytes do **not** fall from 78.7 MB to about 40 MB. Measured in a scratch repository with real rows, pack size goes **up** 1.24x at 20 files a day and 1.76x at 98. A falsified number in a plan is worse than no number. | Carmack |
| 11.12 | **Keep the CSV header on every writer file.** The 97.1 percent overhead on host-fingerprint is a ratio on a ledger measured in kilobytes - about 2.2 MB over the whole retention window. **What was traded**: roughly 97 percent of that one ledger's bytes, against every file under `state/` staying readable by `csv.DictReader`, by a spreadsheet, and by a person opening it. A headerless file would also break `ledger.settle_header` and every reader in row 5. | Carmack |
| 11.13 | `git add` and clone-plus-checkout rise roughly linearly with the file count - measured 11.9x and 4.3x at 2,940 files, one repetition on a dev machine with no spread, so treat them as a floor on a 4 vCPU runner. Re-derived at row 12's corrected 6,000-file steady state, `git add state` lands near 5 s. **Accepted**: seconds inside a job that used 1.8 of its 20 minutes, and neither is one of the two numbers that fail a run. | Carmack |
| 11.14 | **Eight paths leave `REFRESH_PATHS` in this row.** Seven because they are written once - item-health, host-fingerprint, scores, score-index, span-rollup, traces and segments - and `state/published` beside them because it is union-safe and the hand-back was **discarding this run's appended rows before the union driver could ever fire**, leaving the publication record dependent on a rebuild succeeding. `hand_back` then touches no `state/` path at all. **What that buys is correctness, not time**: against a 5-second rebuild in an 11-second step there is no time to win. | Fowler |
| 11.15 | Two callers of the old fold are deleted in this row, because left standing they fold closed days before the day is committed: the `plan` job's step *Fold any segments an earlier run left behind*, and the `stage_compact` call inside `stages/assemble.py`. The two bench call sites in `measure.yml` and `validate.yml` gain the new `--date` argument, and the harness's `BENCH_COMPACT_COMMAND` literal moves with them. | Fowler |
| 11.16 | **Before this row is dispatched, run rule 1's classification check against the tree as it stands and read Table C against it.** Twice now a claim in this plan about the repository has gone stale between writing and reading, and three other plans merged while this one was being written. **A tree that has appeared since is a class to assign, not a design to revisit** - the three classes are closed, so the answer is one line in `idhazh.paths` plus at most one migration. Re-measure the counts in 11.10 to size the migration; do not let them decide it. Scope by the property - every committed file of the trees in Table C - never by the cardinal. | Carmack and Fowler, converged |

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
  - `backend/idhazh/stages/compact.py`
  - `backend/idhazh/day_shards.py`
  - `backend/idhazh/paths.py`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `.github/workflows/digest.yml`
  - `docs/concepts/growing-reads.md`
  - `tests/fixtures/day-shards/closed-day/` (new)
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules, the contract drift gate. CI - the full suite.
- **Oracle:** two branches fold the same closed-day fixture and merge at exit 0 with identical bytes; a third folds it while a straggler lands on the tip, and the push must **exit non-zero with `settled.csv` named** - after which the tip still holds every row. **It cannot settle** the real straggler rate; 12.3 makes a straggler cost one file rather than a repair.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 12.1 | `run.settled_fold_after_days`, default 7. Two folds that read the same input set emit byte-identical adds and deletes (B1), so the fold needs no owner. | Carmack |
| 12.2 | **This is what stops the repository's cost rising with the run rate.** With it, `state/` settles at about **3,200 files today and about 6,000 at five parallel runs**, against 33,800 and 169,000 without. The floor is about **2,550 settled files and it does not move with the run rate at all** - only the live window scales with concurrency. | Carmack |
| 12.3 | **The fold keeps `stage_compact`'s name, module and CLI verb.** "Compact" in ordinary English is *press together into less space*, which is what it now does, so three workflow call sites do not move and there is never a commit where the entry point is a no-op. Its signature gains one keyword: `stage_compact(state_dir, *, date)`. | Fowler |
| 12.4 | **Where it runs: the `assemble` job, between `Retire the ledger shards and the visuals nothing still reads` and `Commit the folded telemetry`, with `if: always()` and `continue-on-error: true`.** It rides that existing commit step, which stages `state frontend/public/telemetry` and carries neither `REFRESH_PATHS` nor `REGENERATE_COMMAND`. | Fowler |
| 12.5 | **It runs after the day is committed, never before**, and the reason is mechanical: `Commit the day` carries `REFRESH_PATHS` and `hand_back` checks the tip's copy back over every refresh path, while `idhazh assemble` re-emits no `settled.csv`. A fold before the day commit is a fold the rebuild silently half-reverts. The telemetry fold below it already carries the same ordering for its own reason. | Fowler |
| 12.6 | **A conflicted fold is refused, never resolved.** `settled.csv` carries no identity, so rule 3 answers no and the push stops; the step is `continue-on-error: true`, so the job carries on and the tip keeps both its own `settled.csv` and the straggler. **Per-path resolution is what loses data**: taking the tip's copy leaves this job's *deletion* of the straggler standing - a deletion is not a conflict - and the straggler's rows then exist in no file at exit 0. An earlier draft said the tip's copy wins whole; that draft loses rows. | Fowler |
| 12.7 | **"Fold once, never again" survives**, because the only way a second fold can be attempted is if the first never landed. | Fowler |
| 12.8 | **What a refused fold costs**: it shares a commit step with `prune-state`, so that run's telemetry month fold is lost too. The step's own comment already prices exactly that - *"A month it does not fold today it folds on the next run."* | Carmack |
| 12.9 | The knob's shape, so the owner can see it rather than take 7 on trust. Files = `fold_days` x writers-per-day + (426 - `fold_days`) x 6 folding trees. | Carmack |

| `settled_fold_after_days` | Files at today's 5 runs a day | Files at 25 runs a day |
| --- | --- | --- |
| 1 | 2,649 | 3,045 |
| **7 (the default)** | **3,207** | **5,979** |
| 14 | 3,858 | 9,402 |
| 30 | 5,346 | 17,226 |
| no fold | 33,794 | 168,970 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 12.R1 | Never fold; accept one file per writer for ever | 169,000 files at five parallel runs, rising with the run rate for ever, in a design whose premise is that the file count is bounded | One verb and one knob saved, against an unbounded repository | Carmack |
| 12.R2 | A compacted read-side artifact instead | It would be derived, so it is rebuilt from the tip by every run - a second two-writer file introduced to fix a two-writer file | A new artifact, its prune and its schema, for a worse shape | Carmack |
| 12.R3 | Give the fold its own job with its own concurrency group | A group is a lock, and the owner's intent is no lock. The fold does not need one. | One workflow, and the thing the plan exists to remove | Carmack |
| 12.R4 | A new module for the fold | `compact.py`'s one question is already *what does a closed day press into*, and row 11 empties its body in the same PR. A new module leaves the old name a no-op between two merges. | One file, and three workflow call sites that would have to move | Fowler |

### Row 13 - The head goes

- **Scope:** delete the head-reading path everywhere - the reduce that wrote one, and the single-file branch in both walkers.
- **Files touched:**
  - `backend/idhazh/stages/compact.py`
  - `backend/idhazh/day_shards.py`
  - `backend/idhazh/ledger.py`
  - `frontend/src/lib/server/payload.ts`
  - `tests/fixtures/day-shards/both-shapes/`
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

### Row 15 - The plan job's own ledgers stop being shared files

- **Scope:** the four committed stores the `plan` and council jobs write that no earlier row reaches - `feed-health`, `counterfactual-scores`, `feed-retirements` and the council and judge trees - get a class each, and the two that need one get a merge driver.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/stages/plan.py`
  - `backend/idhazh/paths.py`
  - `backend/utilities/migrate_to_day_shards.py`
  - `.gitattributes`
  - `tests/fixtures/day-shard-migration/`
  - every committed file under `state/feed-health` and `state/counterfactual-scores`
- **Acceptance gates:** local - `python -m pytest backend/tests` for the touched modules. CI - the full suite.
- **Oracle:** rule 1's contract test passes with no path unclassified. **It cannot settle** whether a union-safe read really is repeat-proof - each one names its property in Table C2 and each property has its own unit test against a doubled row.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 15.1 | **`state/feed-health` becomes written-once, and it is the sharpest gap in the old plan.** It has no merge driver - one was removed on 2026-09-19 when retries were still serial - it is appended by the `plan` job, and until row 3 lands that job's commit step has no tolerance. Two parallel `plan` jobs conflict, the job dies, and `assemble` never runs. `ledger.append_health` is deleted; the path becomes tree C8; every reader goes through `day_shards.settled_rows` on `FEED_HEALTH_KEY`. | Fowler |
| 15.2 | **Not `merge=union`, even though the key carries `run_id` and a union would be safe.** A union here would make the conflict quiet rather than remove it, and the conflict is the symptom of a shared file. The written-once name removes it. | Fowler |
| 15.3 | `state/counterfactual-scores` becomes tree C9 on the same template and for the same reason. | Fowler |
| 15.4 | `state/feed-retirements.csv`, `state/llm-council/shard-outcomes/` and the four judge trees become **union-safe** and gain `merge=union`. Each carries its repeat-proof property in Table C2, and each is a row per key that says nothing about another row. Migrating them would move data for no gain. | Fowler |
| 15.5 | `state/content-similarity-judge/holdout-pairs.csv` keeps `merge=text` and is classified **person-written**. Two edits there are two people disagreeing, which is a conversation rather than a race. | Fowler |
| 15.6 | This row rides PR C because it migrates committed data and PR C lands alone anyway. It must land before row 14, or the first pair of parallel runs kills the `plan` job. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 15.R1 | Give `feed-health` `merge=union` and leave it shared | It hides the shared file instead of removing it, and the reader would then carry a settle nobody asked for | One `.gitattributes` line, against a tree that still has two writers | Fowler |
| 15.R2 | Migrate the six union-safe trees too | Data movement for no gain - each one is already repeat-proof by its own read | Six more migrations inside the riskiest PR in the plan | Carmack |

### Row 16 - The day's metrics file is declared derived

- **Scope:** `state/day-metrics/<Y>/<M>/<DD>.json` and its published twin join `idhazh.paths.DERIVED`, so they are handed back and rebuilt like every other projection.
- **Files touched:**
  - `backend/idhazh/paths.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_staged_paths.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_staged_paths.py`, the contract drift gate. CI - the full suite.
- **Oracle:** rule 1's contract test sees `state/day-metrics` as derived and in no other class. **It cannot settle** that the rebuild reproduces it byte-for-byte from a different tip - that is the producer's own existing test.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 16.1 | **It is one whole-file-per-day JSON written by `assemble` - the same two-writer defect as `digest.json`, one directory over** - and no earlier row named it. | Fowler |
| 16.2 | **It does not become a fragment fold.** It is already a pure function of the day's item-health rows and the published day; it is not a record of what one run saw. Once row 11 makes item-health written-once, two runs compute the same file from the same rows, and the only question left is who wins a race - which the existing rebuild already answers in milliseconds. | Fowler |
| 16.3 | It ships in PR A, beside row 4, because that is the row that creates `idhazh.paths` and rewrites the refresh list. Two tuple entries. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 16.R1 | Give it fragments and a fold, like `digest.json` | A second fragment shape, a second fold, a second schema and a second prune, to answer a question the rebuild already answers | Row 9's whole surface again, for a file no reader opens | Fowler |
| 16.R2 | Leave it out of `DERIVED` and let the rebase merge it | It is JSON; a text merge of two objects is a file that is not JSON | Nothing to build, and a console payload that fails to parse | Fowler |

## Section 3 - What nobody asked, and it outranks this plan

Two findings came out of this work that this plan does not fix. Both are measured, both are reader-facing, and both need a plan of their own. Section 0f lists the four things this plan must not do, or that plan gets harder.

**GitHub drops a quarter of the slots.** 48 of 65 scheduled slots produced a run over 2026-09-09 to 2026-09-21 - 26 percent lost. 2026-09-19 published nothing at all. No concurrency design touches this, because the run never exists. More cron slots is the only lever, and it is free.

**The site never says it is behind.** A day the pipeline broke and a quiet Sunday both read "0 stories", and a missing day's page says *"the day it names was never published"* - the same sentence a mistyped address gets. `run.json` knows which it was. The three sentences the page owes a reader are: *"We tried to publish 19 September and the run did not finish. Nothing from that day is here."*; *"No run was scheduled for 19 September."*; and *"We ran on 19 September and found nothing worth publishing."* Plus one more on a live day: *"Last updated 06:47 UTC. The 10:20 update has not arrived."*

## Section 4 - Where the evidence lives

The design rationale belongs in [`docs/architecture/publishing/committing.md`](../docs/architecture/publishing/committing.md), which already owns the question of how a run's rows reach the repository, not in this file. This plan tracks rows; that page holds the reason.

Every count in this file is dated 2026-09-22 and describes a growing collection. Re-measure before quoting one, and scope a migration by the property - every committed head of these trees - never by the cardinal.
