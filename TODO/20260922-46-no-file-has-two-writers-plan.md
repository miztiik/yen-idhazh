# No file has two writers

**Status**: DRAFT - not dispatched. Section 6 rules this Level 5 from row 5 onward; a person signs off before row 5 starts.

**Last Updated**: 2026-09-22

## Section 0 - What this is for

A run that finishes its work and cannot commit it publishes nothing. **7 of the last 49 completed digest runs died at a push step.** Run `35660521768` read the feeds, planned the day, and lost all of it at the rebase on 2026-09-21.

The intent behind this plan is the owner's, stated 2026-09-22: **content refresh runs in parallel, with no lock anywhere.** Today `concurrency: group: digest` stops that. The lock is not the disease; it is where the disease surfaces. This plan removes the reason the lock exists, then removes the lock.

## Section 0a - The one sentence

> **A file two runs can both write must be a pure function of files only one run each writes.**

Everything below is that sentence applied. A test can enforce it: every `state/` path a production stage writes either matches the four-element grammar `<run>-<attempt>-<job>-<shard>` in `ledger.segment_path`, or is derived from paths that do.

## Section 0b - The finding that decided it

Git does not conflict when two sides write **identical bytes**, or when both delete the same path. Proved 2026-09-22 in a scratch repository: two branches that rewrote one file to the same content and deleted the same file merged with exit 0; two branches writing different bytes gave `CONFLICT (add/add)`.

So coordination is only needed where two writers disagree. `stage_compact` makes them disagree by construction: it reads the **existing head**, merges the waiting segments into it, and writes the result. Two folders starting from different heads always produce different bytes. Sorting does not fix it - the stale folder holds fewer keys, so its head would delete rows the tip has. The conflict is git protecting the data.

**A head file written by more than one process is broken. No merge driver, no sort order and no refresh timing fixes it.** Only two things do: exactly one process ever writes it, or there is no head file.

A serialized single-writer workflow was considered and rejected. GitHub keeps only **one** pending run per concurrency group and a newer pending run silently cancels the older - the incident is recorded in [`.github/workflows/validate.yml`](../.github/workflows/validate.yml) lines 55-65. Under contention it would drop folds with no error anywhere.

## Section 0c - What this plan does NOT do

**It does not deliver two simultaneous passes over the same feeds.** All three advisors rejected that as the goal, on separate grounds:

- The item ceiling binds, not supply. About 10,000 addresses are considered a day and about 300 publish. Two runs reading one feed snapshot with the same deterministic ranking take the same top 80. Same stories, twice. (Editor)
- Two parallel `plan` jobs cannot see each other's claims: the published ledger is written by `assemble`, so neither run knows the other is already summarising a story. Picking the winner by whichever machine finished first is choosing editorial text with a stopwatch. (Editor)
- The freshness it buys is 18 percent of reader latency. One config line buys 31 percent at the same runner cost. (Carmack, section 3)

**Parallel runs earn their place as catch-up for a lost slot**, four hours of news behind and covering different ground - not as a twin. 2026-09-13 published 75 stories on 2 runs where 2026-09-16 published 364 on 5. That is the coverage loss worth capacity.

## Section 1 - Status Reckoner

**A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch.

| # | Row title | PR | Depends-on | Status | Level | Worktree | PR link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The one state writer with no lock gets one, and the failure stops lying | A | - | PENDING | 1 | - | - |
| 2 | The work shard gets its headroom back | B | - | PENDING | 2 | - | - |
| 3 | The fold becomes a function a reader can call | C | - | PENDING | 3 | - | - |
| 4 | The day directory is the ledger | D | 3 | PENDING | 5 | - | - |
| 5 | The head goes | E | 4 | PENDING | 3 | - | - |
| 6 | One paired dispatch says what is really still broken | F | 5 | PENDING | 2 | - | - |
| 7 | The run ordinal is derived at landing, never claimed | G | 6 | PENDING | 5 | - | - |
| 8 | The published day is folded from per-run fragments | G | 7 | PENDING | 5 | - | - |
| 9 | A story is claimed before a model is spent on it | H | 8 | PENDING | 5 | - | - |
| 10 | The concurrency group goes | H | 9 | PENDING | 4 | - | - |

**Rows 1 to 5 are the prerequisite and can start now. Rows 7 to 10 need row 6's measurement and a person's sign-off.** PR [#1041](https://github.com/miztiik/yen-idhazh/pull/1041) is already open and merges as-is: it is a band-aid that lowers the failure rate until row 4 lands, and reverting it is a second change for no gain.

## Section 2 - The rows

### Row 1 - The one state writer with no lock gets one, and the failure stops lying

`measure.yml` gets a `concurrency:` block. Its own comment already admits it is the only `state/` writer without one, and it is dispatched by hand many times a day. `validate.yml`'s group is per candidate, so two candidates already fold `state/pipeline-tests/` at once.

In the same PR, [`commit-and-push.sh`](../.github/scripts/commit-and-push.sh) reports `$attempt` instead of the constant "three". A conflicting rebase hits `break`, so every recorded failure spent one attempt while printing three. That sentence sends the next reader to the retry count, which cannot help.

**What was wrong**: a lock that depends on every future author remembering to join it is not a lock, and an error message that lies about its own budget costs the next person a wrong diagnosis.

### Row 2 - The work shard gets its headroom back

`run.max_parallel: 4 -> 8` in [`config/idhazh.json`](../config/idhazh.json), with the three conditions in `docs/reference/pipeline-cost.md` answered on the line that changes it.

The fan-out is `min(ceil(safety_ceiling_per_run / shard_size), max_parallel)` = `min(16, 4)`. **`max_parallel` is the only binding term.** At 8 a worker draws 10 items instead of 20 and the shard roughly halves.

Measured from the committed record, 2026-09-22 - the slowest work shard, against the 200-minute `shard_timeout_minutes` kill:

| Day | Slowest work shard | Share of the bound |
| --- | --- | --- |
| 2026-09-19 | 167.6 min | 83.8% |
| 2026-09-20 | 181.5 min | 90.8% |
| 2026-09-21 | **190.6 min** | **95.3%** |

Three consecutive days, rising. The bound was derived on 2026-09-14 against a worst 20-item shard of 96.1 minutes; production runs at 1.98x that derivation, so **the derivation is falsified**. A worker killed at the bound uploads nothing and the run loses every item it held.

**What was wrong**: the shard is nine minutes from a silent total loss, and no row below is safe to add contention on top of it.

**This row blocks row 10 outright.** It is also the cheapest freshness lever there is: reader latency is an estimated 285 minutes mean, of which the run is 183. Halving the run takes it to roughly 198 - about 31 percent - against the 18 percent two parallel runs would buy at the same 8-job cost.

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

### Row 6 - One paired dispatch says what is really still broken

On a branch with the `digest` group removed, dispatch two runs of one day at once and record what happens. Three things are designed for this race and none has been run:

| Surface | Why it should hold |
| --- | --- |
| `assemble` commit the day | `REGENERATE_COMMAND` rebuilds against the winning tip rather than text-merging |
| `DigestRunRef.n` | `assemble` strips its own `n` and re-appends against `previous`, so a rebuild may already re-derive it |
| `state/published` | Day-partitioned, append-only, re-derived by the rebuild |

**What was wrong**: rows 7 and 8 are weeks of contract work designed for a race the rebuild path may already handle. Three hours of runner time settles it with data.

In the same PR, `state/seen` gets `merge=union` in `.gitattributes`. It has no merge driver today and falls through to `*.csv text eol=lf`, so two parallel runs conflict at the push. `load_seen` keeps the earliest timestamp per key, so a repeated row changes no answer - the same argument already written above `state/published/**`.

### Row 7 - The run ordinal is derived at landing, never claimed

`DigestDay` requires runs numbered 1..N with no gaps. A run claims its own `n` by counting the day payload it checked out. **This has already failed with a date on it**: on 2026-08-29 runs `33270983446` and `33274853468` both derived `2026-08-29-3`, and the ledgers keyed on it held six counter rows for four shards.

`n` becomes `enumerate()` over the day's run records in landing order. Contiguity then holds by construction and the validator checks the assembler's arithmetic instead of a claim.

The ordinal stays on the page and stops being an identity anywhere else. It is rendered once, in `DayNotice.svelte`, as "(update 4)". `introduced_by_run` has no renderer at all.

**What was wrong**: every variant of "read the day, count the runs, claim N+1" is the same bug with a longer fuse. The ordinal is a rendering of position, not an identity.

### Row 8 - The published day is folded from per-run fragments

Each run commits `frontend/public/digest/<Y>/<M>/<D>/runs/<run_id>.json` - one writer, written once, never rewritten. `digest.json` stops being written by a run and becomes derived from the fragments by one idempotent append-only fold.

Two folds that see the same fragment set emit identical bytes. A fold that sees fewer fragments emits a valid **prefix**, and the next fold appends the rest. The append-only promise - *"a later run appends; it never reorders what a reader already read"* - is kept exactly, because the fold inherits position rather than computing a key.

Ordering was ruled on separately and both advisors landed on the same answer: order by **landing**, whole block at a time, never interleaved. First sight, run start, run completion and score each break the promise by moving a story a reader was part-way through.

`DigestRunRef` gains `run_id` and `completed_at`, both optional. The 31 committed days carry neither and null reads as "this day predates fragments". `DayNotice` already guards on absent runs.

**What was wrong**: `digest.json` is one path two runs both rewrite - the same defect as the head, on the published side.

**Out of scope, deliberately**: deleting `introduced_by_run` from `DigestView`. It has no renderer and costs 1.16 gzipped bytes an item, but removing it changes the contract, the schema and every cached shell in a browser. Separate decision, separate commit.

**Rejected**: `merge=union` on `frontend/public/**/*.json`. It works for `state/published` because a CSV row is independent of every other row. JSON has no line independence, so a union of two objects is a file that is not JSON, and the failure surfaces in a reader's browser instead of at the push.

### Row 9 - A story is claimed before a model is spent on it

A run reserves an address at planning time, before summarising, and a second run sees the reservation. Today the claim is only recorded after publication, by `assemble`.

Without this, two parallel runs both summarise the same story and one call is binned - bounded by `safety_ceiling_per_run` = 80 items. The reader never sees a duplicate: the item id is content-addressed from the address, `assemble` keeps the item the day already holds, and `drop_raced_assets` keeps the tip's chart. So this row buys the model call back, not correctness.

**What was wrong**: whose wording a reader gets is decided by which machine finished first. That is a stopwatch making an editorial call.

### Row 10 - The concurrency group goes

`concurrency: group: digest` is deleted from `digest.yml`.

Two things must be true first and neither is today:

- **Row 2.** The work shard is at 95.3 percent of its kill and rising. Contention pushes it over, and a killed worker uploads nothing.
- **`prune.yml`.** It force-pushes at 23:37 into the single 266-minute gap the serial schedule leaves. Parallel runs erase that gap, and a force-push over an in-flight digest discards it. Move it, or gate it on an in-flight digest.

**What was wrong**: the group is a lock doing load-bearing work it was never designed for, and it manufactures the staleness it appears to prevent. Run `35660521768` waited 46 minutes in that queue and then folded a 46-minute-old store.

## Section 3 - What nobody asked, and it outranks this plan

Two findings came out of this work that this plan does not fix. Both were measured, both are reader-facing, and both are worth their own row somewhere.

**GitHub drops a quarter of the slots.** 48 of 65 scheduled slots produced a run over 2026-09-09 to 2026-09-21 - 26 percent lost. 2026-09-19 published nothing at all. No concurrency design touches this, because the run never exists. More cron slots is the only lever, and it is free.

**The site never says it is behind.** Of 155 slots in the published archive, 124 landed. A day the pipeline broke and a quiet Sunday both read "0 stories", and a missing day's page says *"the day it names was never published"* - the same sentence a mistyped address gets. `run.json` knows which it was. In the reader's own words: *"I cannot tell a broken digest from a quiet one, and the first time I find out you were broken and did not say, I stop trusting the days you did publish."*

## Section 4 - Where the evidence lives

The design rationale belongs in [`docs/architecture/publishing/committing.md`](../docs/architecture/publishing/committing.md), which already owns the question of how a run's rows reach the repository, not in this file. This plan tracks rows; that page holds the reason.

Every count in this file is dated 2026-09-22 and describes a growing collection. Re-measure before quoting one.
