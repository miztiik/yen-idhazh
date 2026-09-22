# No file has two writers

**Status**: DRAFT - not dispatched. The contract in section 0d is not agreed yet. Nothing below it is dispatchable until it is.

**Last Updated**: 2026-09-22

## Section 0 - What this is for

A run that finishes its work and cannot commit it publishes nothing. **7 of the last 49 completed digest runs died at a push step.** Run `35660521768` read the feeds, planned the day, and lost all of it at the rebase on 2026-09-21.

The intent is the owner's, stated 2026-09-22: **content refresh runs in parallel, with no lock anywhere.** Design for unbounded concurrency and do not price how much of it there will be. `concurrency: group: digest` is not the disease; it is where the disease surfaces. This plan removes the reason the lock exists, then removes the lock.

## Section 0a - The one sentence

> **A file two runs can both write must be a pure function of files only one run each writes.**

## Section 0b - The findings that decided it

Four mechanics, all proved in a scratch repository on 2026-09-22. Each one is reproducible in under a minute and none is taken on trust.

| # | Proof | Result |
| --- | --- | --- |
| P1 | Two branches rewrite one file to the **same bytes** and both delete the same path | Merged, exit 0. **Two writers that agree byte for byte need no coordination.** |
| P2 | Two branches write **different bytes** to one file | `CONFLICT (add/add)` |
| P3 | Two branches each rewrite two directories; resolve one directory to your own commit and the other to upstream | Each side won its own directory. **Per-directory ownership is implementable with no lock.** |
| P4 | Replay of run `35660521768` under this design | See section 0e. It lands clean, and it found one more thing that has to ship. |

So coordination is only needed where two writers disagree. `stage_compact` makes them disagree by construction: it reads the **existing head**, merges the waiting segments into it, and writes the result. Two folders starting from different heads always produce different bytes. Sorting does not fix it - the stale folder holds fewer keys, so its head would delete rows the tip has. The conflict is git protecting the data.

**A head file written by more than one process is broken. No merge driver, no sort order and no refresh timing fixes it.** Only two things do: exactly one process ever writes it, or there is no head file.

A serialized single-writer workflow was considered and rejected. GitHub keeps only **one** pending run per concurrency group and a newer pending run silently cancels the older - the incident is recorded in [`.github/workflows/validate.yml`](../.github/workflows/validate.yml) lines 55-65. Under contention it would drop folds with no error anywhere.

## Section 0c - Ownership is an identity, not a side

**Nothing in this repository says `ours` or `theirs`.** Those are git's positional names, they invert between a merge and a rebase, and they describe which side of a graph a version came from rather than who is entitled to it. A design that reasons in them is a design nobody can check.

The writer's identity is already in the filename. `ledger.segment_path` spells it `<run_id>-<attempt>-<job>-<shard>`, and its own docstring says *"Nobody else writes this path."* So the resolution rule reads:

> **A conflicted path whose name carries this job's own identity resolves to what this job wrote. Every other conflicted path stops the push and names itself.**

Two consequences worth stating.

- **The rule should never fire.** If every path carries its writer's identity, no second writer can name that file, so a conflict on it is impossible. Firing is a defect report, not a repair - it means two jobs claimed one identity, and the run log says which.
- **Git's spelling is hidden in one place.** Two shell functions, `keep_what_this_job_wrote` and `keep_what_origin_has`, carry the `--theirs`/`--ours` inversion and a one-line comment saying a rebase reverses them. No workflow, no doc and no contract sentence uses either word again.

**Two limits on the rule, both verified rather than assumed:**

- **`--theirs` silently does nothing on a modify/delete conflict.** Exit 0, no output, path left `DU` unmerged. Under `set -euo pipefail` a script walks straight past it. This shape is live: the fold deletes drained segments and `prune-state` deletes whole shards. The resolver must assert the index is clean after it runs.
- **On a derived file the rule is silent deletion.** Proved: three single-writer inputs all landed intact while the derived file conflicted, and resolving it to one side would have deleted the other writer's rows. **A derived path may never be declared owned.** This is rule 5 of the contract and it is the one that keeps the rest honest.

## Section 0d - The contract

Eight rules. Each one testable. Each holds for unbounded concurrent runs of digest, telemetry, backfill, validate, measure and council. **This section is what has to be agreed before any row is dispatched.**

1. **One writer, one path.** Every committed path has exactly one job that may write it, and the path's own name carries enough writer identity that two runs, two attempts, two shards or two jobs can never name one file.
   *Test: two declarations naming one path fail the build. No data needed.*
2. **A job declares its paths before it writes one.** The declaration lives in `config/`. Three readers: the workflow's staging argv, the conflict resolution, and the test. It cannot be today's staging argv - `plan`, `assemble` and `fold` each stage `state` whole, so three jobs already claim one directory.
   *Test: the argv of every `commit-and-push.sh` call equals that job's declaration.*
3. **Declared means self-derived.** A path may be declared only if its content is a function of this job's own inputs.
   *Test: run the job in the real-bash harness, `git ls-files` what it wrote, fail on anything outside the declaration.*
4. **A conflict inside a declared path resolves to the declaring job. A conflict anywhere else stops the push.** There is no third case, and the resolver asserts the index is clean afterwards (section 0c, modify/delete).
   *Test: the P3 shape, committed - two branches, two directories, assert each side won its own.*
5. **A derived file is a fold of declared files and nothing else.** Rebuilt from the tip plus this run's own inputs. Never text-merged, and never resolved by rule 4.
   *Test: every path in `REFRESH_PATHS` is absent from every declaration, and the reverse.*
6. **A path with no declared owner stops the push and names itself.** Not resolved either way, not dropped.
   *Test: a harness run that writes an undeclared path exits non-zero with that path in the message.*
7. **An ordinal is assigned by the fold, never by the writer.** A writer stamps its identity and its arrival time. Any number a reader sees is derived from arrival order at fold time. No writer reads or waits for another writer's ordinal.
   *Test: a day built from blocks that arrived in any order validates and renders.*
8. **History rewriting is outside rules 1 to 7.** The one job that force-pushes `main` re-fetches immediately before the push and refuses if the tip moved. It keeps its schedule and is due again next wake.
   *Test: the harness pushes a commit between the prune's checkout and its push; the prune must refuse rather than force.*

**What the contract costs, stated:** it buys a run that never dies at the push, and pays by making every path's ownership a written claim that one wrong entry turns into silent deletion. Rule 6 is the only thing standing between those two, and it is the rule most likely to be argued away as noisy.

## Section 0e - Does this stop run 35660521768? Replayed, not asserted

The failure: a 46-minute-stale checkout folded segments the run ahead had already folded and pushed. Both sides rewrote the same five derived day heads, those heads have no union merge driver, the rebase conflicted and the push died.

The replay builds that exact shape - two segments, a run ahead that folds and pushes, a stale job that folds the same two from its old base and adds one segment of its own - and rebases.

| Attempt | Result |
| --- | --- |
| Fold as it works today (read the head, merge into it) | `CONFLICT (content)` on every head. The failure reproduces. |
| Fold as split-and-rename, one segment in and one day file out | **`CONFLICT (file location)`.** Not the old failure - a new one. |
| Split-and-rename, with `merge.directoryRenames=false` | **`Successfully rebased`, exit 0.** Both of the run-ahead's folded files present, the stale job's own new segment present and unfolded. Nothing lost. |

**Yes, it stops it - and the replay found something that has to ship with it.** Emptying `state/segments/` makes git read the whole directory as *renamed* to the day directory, so the stale job's brand-new segment added into `state/segments/` trips `CONFLICT (file location)`. The data was correct in the tree and the rebase stopped anyway. `merge.directoryRenames=false` on the rebase is not a tuning knob here; without it this design still loses the day, on a different error.

Note what did **not** happen: the ownership rule never fired. There was no conflict for it to resolve. That is the rule working as section 0c says it should - partitioning makes the conflict impossible, and the resolver is the net under it.

## Section 0f - What this plan does NOT do

**It does not deliver two simultaneous passes over the same feeds.** The item ceiling binds, not supply: about 10,000 addresses are considered a day and about 300 publish, so two runs reading one feed snapshot with the same deterministic ranking take the same top 80. And two parallel `plan` jobs cannot see each other's claims, because the published ledger is written by `assemble` - picking the winner by whichever machine finished first is choosing editorial text with a stopwatch.

**Parallel runs earn their place as catch-up for a lost slot**, four hours of news behind and covering different ground. 2026-09-13 published 75 stories on 2 runs where 2026-09-16 published 364 on 5.

**The work shard's timeout is out of scope.** It sits at 190.6 of 200 minutes and rising, and it is a model-workload problem. The commit contract is correct or wrong at a shard length of 5 minutes and at 500. It gets its own plan.

## Section 1 - Status Reckoner

**A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch.

| # | Row title | PR | Depends-on | Status | Level | Worktree | PR link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The one state writer with no lock gets one, and the failure stops lying | A | - | PENDING | 1 | - | - |
| 2 | The rebase stops guessing that a drained directory was renamed | A | - | PENDING | 1 | - | - |
| 3 | The fold becomes a function a reader can call | B | - | PENDING | 3 | - | - |
| 4 | The day directory is the ledger | C | 3 | PENDING | 5 | - | - |
| 5 | The head goes | D | 4 | PENDING | 3 | - | - |
| 6 | A job declares what it owns, and an undeclared path stops the push | E | 5 | PENDING | 4 | - | - |
| 7 | The push window is measured | F | 6 | PENDING | 2 | - | - |
| 8 | The one rule that needs a sequence is deleted | G | 7 | PENDING | 5 | - | - |
| 9 | The published day is folded from per-run fragments | G | 8 | PENDING | 5 | - | - |
| 10 | The corpus moves to its own ref | H | - | PENDING | 4 | - | - |
| 11 | The concurrency group goes | I | 9, 10 | PENDING | 4 | - | - |

**Rows 1 and 2 are one-line fixes and need no contract agreement.** Rows 3 to 5 are the partitioning and need section 0d agreed. Rows 8 onward need row 7's measurement.

PR [#1041](https://github.com/miztiik/yen-idhazh/pull/1041) is already open and merges as-is: a band-aid that lowers the failure rate until row 4 lands, and reverting it is a second change for no gain.

## Section 2 - The rows

### Row 1 - The one state writer with no lock gets one, and the failure stops lying

`measure.yml` gets a `concurrency:` block. Its own comment already admits it is the only `state/` writer without one, and it is dispatched by hand many times a day. `validate.yml`'s group is per candidate, so two candidates already fold `state/pipeline-tests/` at once.

In the same PR, [`commit-and-push.sh`](../.github/scripts/commit-and-push.sh) reports `$attempt` instead of the constant "three". A conflicting rebase hits `break`, so every recorded failure spent one attempt while printing three. That sentence sends the next reader to the retry count, which cannot help.

**What was wrong**: a lock that depends on every future author remembering to join it is not a lock, and an error message that lies about its own budget costs the next person a wrong diagnosis.

### Row 2 - The rebase stops guessing that a drained directory was renamed

Every `git rebase` in [`commit-and-push.sh`](../.github/scripts/commit-and-push.sh) runs with `-c merge.directoryRenames=false`.

**Found by the replay in section 0e, and it is not a tuning knob.** The fold drains `state/segments/` and writes into the day directory. Git reads an emptied directory as *renamed*, so a brand-new segment added into `state/segments/` by another job trips `CONFLICT (file location)` - *"added in ... inside a directory that was renamed in HEAD, suggesting it should perhaps be moved to ..."*. The tree was correct and the rebase stopped anyway.

With the guess off, the same replay rebases clean. Without it, row 4 still loses the day - on a different error, which is the worst kind to inherit.

**What was wrong**: git guesses intent from a directory that emptied, and a pipeline that drains directories on purpose gets the guess wrong every time.

**Out of this plan: the work shard's timeout.** It is at 190.6 of 200 minutes and rising three days running, which is real and urgent, and it is a model-workload problem. The commit contract is correct or wrong at any shard length. It gets its own plan and does not gate a row here.

### Row 3 - The fold becomes a function a reader can call

Extract `_settle` out of `stage_compact` into a function that returns rows instead of writing a file. No behaviour change.

Add a sharded-day walker beside `day_files` and `dayShardFiles`, one per language, and point the six head ledgers at it. **`day_files` itself is not touched**: it has about 40 callers and most walk trees that are not changing.

**What was wrong**: the merge logic only exists inside something that writes a file, so nothing can fold without also committing the result. And of the two existing walkers, `day_files` refuses a directory loudly while the frontend's `/^\d{2}\.csv$/` **skips one silently** - the silent half would ship a wrong number with no test going red.

This PR is inert. Nothing writes a directory yet, so it cannot change a single run. It is the read-side migration, landing before the break rather than beside it.

### Row 4 - The day directory is the ledger

Producers write `state/<ledger>/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.csv`. `stage_compact` becomes split-and-rename: read one segment, split its rows by their own date cell, write, delete. Output bytes depend on exactly one input file, so two folders emit identical adds and identical deletes.

The 98 committed head files move in the same PR - 29 item-health, 31 scores, 31 score-index, 6 host-fingerprint, 1 span-rollup, about 16.9 MB. Extend [`backend/utilities/migrate_to_day_shards.py`](../backend/utilities/migrate_to_day_shards.py), which already did this repository's last grain change and already refuses to write a tree it cannot read back: *"a migration that writes an empty tree and unlinks its source is a delete with exit 0."*

**What was wrong**: the fold reads the existing head and merges into it, so two folders from different heads always differ. That is the defect, in three workflows.

**This is the risky PR and it needs a quiet window.** A digest run in flight when it merges pushes an old-shape head the move missed. That is a timing call for a person, not a code problem.

Cost, measured: `state/` goes from 359 files to roughly 4,100 - an estimate scaled from 105 and 83 segments on two measured days, bounded by the 30-day retention and not growing with the archive. **History bytes for those ledgers fall from 78.7 MB to about 40 MB**, because nothing is rewritten. A rewritten head costs 2.29x its own size in history and 20x on a busy day; a file written once costs 1x. `state/` ships zero files to the site, so the 1 GB Pages cap is untouched.

### Row 5 - The head goes

Delete the reduce in `stage_compact` and the single-file branch in both walkers. Stamp `version`, append one changelog line.

**What was wrong**: dead code that can still be called is a second answer waiting to be given. Separate from row 4 so row 4 stays revertible on its own.

### Row 6 - A job declares what it owns, and an undeclared path stops the push

Contract rules 2, 4 and 6 ship here. A declaration file in `config/` names the paths each job may write. `commit-and-push.sh` gains two functions, `keep_what_this_job_wrote` and `keep_what_origin_has`, which between them hold git's inverted `--theirs`/`--ours` spelling and one line saying a rebase reverses it. Nothing outside those two functions uses either word.

On a conflicted rebase the resolver walks `git diff --name-only --diff-filter=U`. A path whose name carries this job's `<run>-<attempt>-<job>-<shard>` resolves to what this job wrote. **Every other conflicted path stops the push and names itself** - not resolved either way, not dropped. Then the resolver asserts the index holds no unmerged entry, because `--theirs` exits 0 and does nothing on a modify/delete (section 0c).

The declaration cannot be today's staging argv: `plan`, `assemble` and `fold` each stage `state` whole, so three jobs already claim one directory and a resolution keyed on that argv hands `state` to whoever resolves first.

**What was wrong**: today any conflict anywhere kills the whole run, and no job has ever said what it owns - so a new `state/` writer has arrived without the right handling three times, by the commit script's own admission.

In the same PR, `state/seen` gets `merge=union` in `.gitattributes`. It has no merge driver today and falls through to `*.csv text eol=lf`, so two parallel runs conflict at the push. `load_seen` keeps the earliest timestamp per key, so a repeated row changes no answer - the same argument already written above `state/published/**`.

### Row 7 - The push window is measured

Two monotonic stamps and one `echo` inside the retry loop that already exists, reporting `W` - the time from `git fetch` completing to the server accepting the push - per job, per attempt. No new job, no new file, no new artifact.

**This is the one measurement the design turns on, and it settles the one open disagreement.** An optimistic rebase-and-push converges in expectation at any commit rate; a fixed three-attempt loop does not. Holding success at 95 percent, the loop survives a commit rate of roughly `0.459 / W`:

| Job | `W` | Commit rate it survives | Headroom over today's 5.5/hour |
| --- | --- | --- | --- |
| plan, work shard | ~2 s (estimate) | 826/hour | 150x |
| **assemble** | ~75 s - the 1.2-minute rebuild sits inside the window | **22/hour** | **4x** |

If `W_assemble` comes back near 75 s, `REGENERATE_COMMAND` has to leave the push window and row 9 is required. If it comes back near 5 s because the rebuild usually finds nothing to do, the ceiling is about 330/hour, the rebuild is not the problem, and row 9 is argued on contract grounds alone.

In the same PR the retry loop stops being a count. A fixed three cannot converge under unbounded N; it becomes a wall-clock deadline with jittered backoff, because without jitter every loser refetches and collides in lockstep.

**What was wrong**: nothing counts a rebase today. The `rebased` output is read by one `if:` and thrown away with the runner, so no trend exists and every argument about contention is an argument from anecdote.

### Row 8 - The one rule that needs a sequence is deleted

`_order_is_global_and_append_only` holds eight rules. **Exactly one needs a writer to know what another writer did**, and it is deleted:

| Rule | Needs a sequence? |
| --- | --- |
| item ids distinct within a day | No |
| `introduced_by_run` non-decreasing - *"a later run appends; it never reorders what a reader already read"* | **No - and it becomes the whole ordering rule** |
| **runs numbered from 1 without gaps** | **Yes. Deleted.** |
| bounds check, `items_added` arithmetic, vertical counts, `partial`, `updated_by_run >= introduced_by_run` | No - arithmetic inside one file |

The same sentence sits in `RunManifest`. Both go together.

**`n` is already an arrival ordinal, not a schedule ordinal.** `assemble.run_n_for` computes `previous.runs[-1].n + 1` and its own docstring splits `n` (the day's ordinal) from `run_id` (the execution's identity), on purpose. Nothing in this repository believes `n` means "the 02:20 run". It means "the Nth block this day received" - which is first come, first to digest.

After this the fold assigns `n` by `enumerate()` over arrival order. Contiguity holds by construction; the validator checks the fold's arithmetic instead of a writer's claim.

A reader loses nothing. `DayNotice` prints "(update 3)" and stays true - a reader cannot tell arrival order from schedule order. `introduced_by_run` has **no renderer at all**: the divider that used it was deleted on 2026-09-01, and it stays on the wire only because removing a name from `DigestView` is a contract change. It costs 1.16 gzipped bytes an item.

**What an operator loses**: the rule caught a producer that skipped a block, and nothing else catches that.

**What was wrong**: every variant of "read the day, count the runs, claim N+1" has already failed here with a date on it - on 2026-08-29 runs `33270983446` and `33274853468` both derived `2026-08-29-3`, and the ledgers keyed on it held six counter rows for four shards. The ordinal is a rendering of position, not an identity.

### Row 9 - The published day is folded from per-run fragments

Each run commits `frontend/public/digest/<Y>/<M>/<D>/runs/<run_id>.json` - one writer, written once, never rewritten. `digest.json` stops being written by a run and becomes derived from the fragments by one idempotent append-only fold.

Two folds that see the same fragment set emit identical bytes, which P1 makes free. A fold that sees fewer fragments emits a valid **prefix**, and the next fold appends the rest. The append-only promise is kept exactly, because the fold inherits position rather than computing a key.

Ordering was ruled on separately and both advisors landed on the same answer: order by **landing**, whole block at a time, never interleaved. First sight, run start, run completion and score each break the promise by moving a story a reader was part-way through.

`DigestRunRef` gains `run_id` and `completed_at`, both optional. The 31 committed days carry neither and null reads as "this day predates fragments". `DayNotice` already guards on absent runs.

**What was wrong**: `digest.json` is one path two runs both rewrite - the same defect as the head, on the published side. It is also the only path in the repository where a **directory** is not a partition: two runs of one day both own `frontend/public/digest/<D>/`, so the key has to include the run, exactly as `state/segments/` already does.

**Out of scope, deliberately**: deleting `introduced_by_run` from `DigestView`. It has no renderer and costs 1.16 gzipped bytes an item, but removing it changes the contract, the schema and every cached shell in a browser. Separate decision, separate commit.

**Rejected**: `merge=union` on `frontend/public/**/*.json`. It works for `state/published` because a CSV row is independent of every other row. JSON has no line independence, so a union of two objects is a file that is not JSON, and the failure surfaces in a reader's browser instead of at the push.

### Row 10 - The corpus moves to its own ref

`corpus/` leaves `main` for a ref of its own, so `prune.yml`'s force push cannot reach the branch every other job commits to.

**A partition cannot fix this one and it is worth saying why.** The prune's unit is a commit range, not a path - *"a squash boundary is per-commit, not per-path"* - so it rewrites `backend/`, `docs/` and `state/` alongside `corpus/`. A force push is a whole-ref operation that never reads a path, so there is nothing for path ownership to own. Anything pushed between the prune's checkout and its push is deleted by that push, and every concurrent job's base stops being an ancestor of `main`.

Today this is held by two things that do not survive unbounded concurrency: a `corpus-prune` group that reaches no other workflow, and a 23:37 cron hand-placed in the one 266-minute idle gap the serial schedule leaves. Parallel runs erase that gap.

Contract rule 8 ships here too: the prune re-fetches immediately before the push and refuses if the tip moved. An unstamped prune is due again next wake.

**Considered and rejected**: one concurrency group shared between `prune.yml` and every pushing workflow. It serialises the entire pipeline behind a maintenance job, which is the end of the feature rather than a fix for it.

**What was wrong**: the only job that rewrites history shares a ref with every job that appends to it.

### Row 11 - The concurrency group goes

`concurrency: group: digest` is deleted from `digest.yml`.

**What was wrong**: the group is a lock doing load-bearing work it was never designed for, and it manufactures the staleness it appears to prevent. Run `35660521768` waited 46 minutes in that queue and then folded a 46-minute-old store. It also gives no protection worth having - GitHub keeps one pending run and silently cancels the older, so a second dispatch during a long run disappears with no error anywhere.

## Section 3 - What nobody asked, and it outranks this plan

Two findings came out of this work that this plan does not fix. Both were measured, both are reader-facing, and both are worth their own row somewhere.

**GitHub drops a quarter of the slots.** 48 of 65 scheduled slots produced a run over 2026-09-09 to 2026-09-21 - 26 percent lost. 2026-09-19 published nothing at all. No concurrency design touches this, because the run never exists. More cron slots is the only lever, and it is free.

**The site never says it is behind.** Of 155 slots in the published archive, 124 landed. A day the pipeline broke and a quiet Sunday both read "0 stories", and a missing day's page says *"the day it names was never published"* - the same sentence a mistyped address gets. `run.json` knows which it was. In the reader's own words: *"I cannot tell a broken digest from a quiet one, and the first time I find out you were broken and did not say, I stop trusting the days you did publish."*

## Section 4 - Where the evidence lives

The design rationale belongs in [`docs/architecture/publishing/committing.md`](../docs/architecture/publishing/committing.md), which already owns the question of how a run's rows reach the repository, not in this file. This plan tracks rows; that page holds the reason.

Every count in this file is dated 2026-09-22 and describes a growing collection. Re-measure before quoting one.
