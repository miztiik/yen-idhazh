# How to run the pipeline

**Last Updated**: 2026-10-04

Running a digest end to end on your own machine, and what each stage is allowed
to do. Project-specific by nature: this describes *this* pipeline, not a process
that transfers between repositories.

## The three stages

Each takes a file and writes a file, which is what lets the middle one be
sharded across disposable machines and re-run cheaply. A stage that only works
as part of the whole is a stage nobody can debug.

| Stage | Does | Needs the network | Needs a model |
| --- | --- | --- | --- |
| `plan` | Reads every live feed, records what each one did, deduplicates, ranks, drops what was already published | yes | no |
| `work` | Fetches, extracts, summarizes and scores one item at a time | yes | yes |
| `assemble` | Collects whatever finished, publishes it, appends the ledger | no | no |

```
python -m idhazh plan
python -m idhazh work
python -m idhazh assemble
```

`python -m idhazh run` is the three in order.

## Before the first run

Install the package, and the faithfulness extra if you want scores:

```
python -m pip install -e ".[dev]"
python -m pip install -e ".[faithfulness]" # current Transformers 5 + torch, hundreds of MB
```

Get the runtime and the weights per
[set-up-local-inference.md](set-up-local-inference.md), then print the server
command with the program in
[test-models-locally.md](test-models-locally.md#serve-a-model) and run it. Do
not type the flags: `server_argv` is the only place they are written, and a
hand-typed copy here has already drifted once.

The summarize stage talks to the address in `config/idhazh.json` under
`model_server.base_url`, which is `http://127.0.0.1:8080` as committed. To use a
server on another machine, change that value to its scheme, host and port.
Article text goes only to a model process the operator of this run controls
([../../CLAUDE.md](../../CLAUDE.md) Guardrail #11). Every job in `.github/`
starts its own server and probes it on loopback.

## Useful flags

| Flag | For |
| --- | --- |
| `--date YYYY-MM-DD` | Re-run a specific day. Defaults to today, UTC. |
| `--execution N` | Name the run. The plan stage files its plan under this run, and a later stage reads this run's plan. Left out, a later stage reads the newest plan of the day. |
| `--shard N --shards M` | Take one worker's share. Round-robin, so lengths spread evenly. |
| `--no-faithfulness` | Skip the scorer. The digest still publishes; **the eval ledger stays empty.** |
| `--config PATH` | Point at a different `config/` directory. |

## Where things land

| Path | What | Committed |
| --- | --- | --- |
| `state/raw/run-plan/<YYYY>/<MM>/<DD>/` | The day's work list, one row per run that planned it, packed later under `state/compact/run-plan/` | **yes** |
| `backend/var/run/<date>/items/*.json` | Per-item article, summary and eval | no - gitignored |
| `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `digest.json` and `run.json` | **yes** |
| `state/raw/summary-quality-evals/<YYYY>/<MM>/<DD>/` | One row per scored item, packed later under `state/compact/summary-quality-evals/` | **yes** |
| `state/raw/seen/<YYYY>/<MM>/<DD>/` | First sight of every address, so an undated article still has an age, packed later under `state/compact/seen/` | **yes** |
| `state/raw/published/<YYYY>/<MM>/<DD>/` | Every address that reached a digest, so nothing runs twice, packed later under `state/compact/published/` | **yes** |
| `state/raw/feed-health/<YYYY>/<MM>/<DD>/` | What every feed did on every run, packed later under `state/compact/feed-health/` | **yes** |
| `state/raw/feed-retirements/<YYYY>/<MM>/<DD>/` | Every endpoint the run stopped asking, and the evidence | **yes** |
| `state/raw/item-health/<YYYY>/<MM>/<DD>/` | What every planned item did on every run, packed later under `state/compact/item-health/` | **yes** |

**The ledgers under `state/` are the pipeline's whole memory.** Plan reads them
at the start of a run and appends to them before it ranks anything, and Assemble
appends item health after it has seen every worker payload. A local run that is
never committed forgets everything the moment it ends - the second run will
re-publish what the first one did. `state/` is read at build time and never
served to a reader
([../architecture/sources/freshness.md](../architecture/sources/freshness.md),
[../architecture/sources/health.md](../architecture/sources/health.md),
[../architecture/sources/item-health.md](../architecture/sources/item-health.md)).

**No article body is ever committed.** The extracted text lives under
`backend/var/`, which is gitignored, and is what the model reads. What ships is
the link, the title and our own summary.

## Turning state cleanup on

Each retention pass is a gardener task, and each task's declaration under
`config/gardener/` ships with `dry_run: true`. **A pass prints every file a live
pass would take and takes none of them.** That is on purpose:
The `history` job of `.github/workflows/idhazh-gardener.yml` force-pushes `main` on a schedule
([../../CLAUDE.md](../../CLAUDE.md) section 8), so a file a task deletes wrongly
stops being recoverable once that prune passes over the range. `git revert` is
not a recovery path here. Until the gardener's own workflow runs the tasks on a
schedule, `python -m idhazh gardener run-task NAME --run-id RUN_ID --attempt N
--git-sha SHA` runs one in a checkout and prints what it would take.

Turning one task's deletion on is a change of its own to that task's
declaration, and this is the order:

1. Wait for a scheduled pass whose output would name at least one file. **For the
 fourteen-month tasks the first such day is 2027-10-01**, when `2026-08` falls
 below their windows. Before then the list is empty every day and the switch
 proves nothing.
2. Read that run's log: `gh run view <runId> --repo <owner/repo> --job <jobId>
 --log`, and grep it for `would delete`. Each task prints one line a pass and
 then one line a file it would take.
3. Check the list against what you expect. On 2027-10-01 the retention tasks
 name one tree - `frontend/public/telemetry/2026-08.csv`. A second name, or a
 month that is not the oldest, means a boundary is wrong and the switch waits.
 The item-health and feed-health rows are not on that list: their compactions
 delete them, and a compaction's own list is read as
 [the compaction page](../architecture/publishing/ledger-compaction.md#what-a-dry-run-does-and-what-the-record-says)
 says. The eval rows are on no list at all, because nothing deletes one.
4. `compact-summary-quality-evals` keeps every month: its `monthly_window` is `forever`, so a
 live pass packs the eval rows into fewer files and drops none of them
 ([../concepts/evaluation.md](../concepts/evaluation.md#design-rationale)).
5. Only then set that task's `dry_run` to `false` in its own declaration. In the
 same change, name the task in `LIVE_BY_DECISION` in
 `backend/tests/contracts/test_gardener_config.py`, with the reason in plain
 words, and correct every doc sentence the switch makes false: that test fails
 on a live switch the list does not name.

**The console ledgers' packing tasks are the ones to turn on first.**
`compact-item-health` and `compact-host-fingerprint` pack live.
`compact-summary-quality-evals` ships report-only, and the console reads its packed files, so
until it runs live the console shows its days up to the day the migration ran.

**Each task is switched on by itself, and the picture cleanup is a task of its
own.** `visual-prune` files a row under `state/raw/visual-prunes/` saying what it
found on every pass, and setting another task live leaves it reporting.
`retention.image_months` is `13` from 2026-09-13, so the pass does name a cutoff -
and nothing published is old enough to sit behind it. Switching it on is a
separate change with its own conditions
([../architecture/publishing/retention.md](../architecture/publishing/retention.md#the-cleanup-says-what-it-did-not-clear)).

One consequence to know before step 5. The published copy goes with its private
source, so `/console/`'s per-item detail stops reaching back past the window.

What each ledger keeps, and why, is on the doc that owns it:
[../architecture/sources/health.md](../architecture/sources/health.md) for feed
health, [../architecture/sources/item-health.md](../architecture/sources/item-health.md)
for the item census, [../concepts/evaluation.md](../concepts/evaluation.md) for
the eval ledger, and
[../architecture/publishing/layout.md](../architecture/publishing/layout.md) for
the whole committed tree.

## Reading a run that went wrong

`idhazh telemetry` is the read side of a finished run. Every subcommand is
bounded by the days it is handed - four of them read one date, and `prune` works
over the range it is given - so none of them gets slower as the archive grows:

```
python -m idhazh telemetry show   --date 2026-09-15  # which instrument files that day has
python -m idhazh telemetry census --date 2026-09-15  # how that day's items ended
python -m idhazh telemetry item ai-01 --date 2026-09-15
```

`show` lists a CSV day tree's files for the date, a door ledger's raw files for
that day, and the packed day or month file once a compaction has taken it.

`census` is the fastest way in: it counts the day's items by stage, outcome and
failure code, which is the same answer as filtering the census shard by hand.

`item` requires the exact item id and a UTC date. It prints settled health and
each retained trace tree, grouped by run, attempt, job and shard. Missing or
expired traces leave health visible with a reason. It reads only the requested
day and never adds the two passes of an item together. The
[telemetry page](../concepts/telemetry.md#the-committed-traces-briefly) owns
retention and legacy-identity behavior.

Every planned item has a census row in the item-health ledger. Read it directly
when you need a column `census` does not fold, because that ledger is committed
and keeps the denominator next to the failure count:

1. Read the day through `ledger.load_days`, which settles a re-run's rows for you.
2. Filter by `run_id`.
3. Read `stage`, `outcome`, `code`, `http_status`, `source_words`,
 `summary_words`, `fetch_ms`, `extract_ms` and `summarize_ms`.
4. Treat `detail` as a bug report for the classifier. It appears only when
 `code = unknown`, and it means the enum needs a better member.

Use the gitignored payloads under `backend/var/run/<date>/items/` only for the
next layer of evidence while the local run still exists:

- `.article.json` explains fetch and extract failures.
- `.summary.json` explains summarizer failures.
- The digest says whether the run was partial, but not why. The census says why.

Logs go to stderr and nowhere else. There is no log service and no runtime call
home ([../../CLAUDE.md](../../CLAUDE.md) section 1b). A log is evidence; the
census row is the record.

When the day itself is fine but its console projections are not - a projection
added after that day published, or a shard lost to a race - write them again
from the day already on disk:

```
python -m idhazh telemetry publish --date 2026-09-15
```

That walks the same route `assemble` walks, in the same order, reading the day's
own `digest.json` and `run.json` rather than the run payloads under
`backend/var/`, which a local run does not keep. It refuses a date that tree has
never published, because there would be nothing to publish the instrument for.

When a run wrote instrument rows nobody wants kept, delete them by naming the
ledger and the two days. Both ends are named, so this is three days:

```
python -m idhazh telemetry prune --target feed-health --since 2026-09-13 --until 2026-09-15
```

It prints every file a live run would remove and removes nothing until you add
`--no-dry-run`. A ledger on the ledger door, as feed health is, also needs
`--run-id` and `--commit` for that live pass, because each file it rewrites
names the run and the commit that wrote it. `--target` takes the name of a ledger and never a path, and
`published` and `seen` are refused by name - forgetting is the one thing those
two may not do. Which ledgers it accepts, why those two are refused, and what
makes it safe to stop half way is
[../architecture/publishing/retention.md](../architecture/publishing/retention.md#a-named-prune-one-ledger-one-range-of-days).

A ledger the door files, such as `item-health`, is a target too. The command
takes those days' rows out of every raw, daily, monthly and yearly file that
holds them, and a live pass also needs `--run-id` and `--commit`, which each
rebuilt file names as its writer. `summary-quality-evals` is refused by its own
declaration, because every eval row is kept for ever. The steps are in
[prune-a-collection.md](prune-a-collection.md#a-ledger-the-door-files).

## Three things that will bite

**A quiet news day is decided by the tie-break.** When no story is carried by
more than one feed every score is identical, so the ordering rule - score, then
when it appeared, then the address - is what picks the day, and
`collect.max_per_source` is what stops one prolific blog becoming the whole
vertical. A quiet day is also where `collect.max_source_share_per_day` earns its
keep: the same two-per-desk rule that is a rounding error on a 400-item day is a
quarter of a four-item one, and the share is what says so.

**A vertical below its feed floor plans nothing.** The floor is `min_feeds` on
the vertical in `config/taxonomy.json`, and it counts only the endpoints the run
may lawfully ask - a curated tombstone, a retired endpoint, a robots denial and
unknown permission are all excluded, while a resting or failing endpoint still
counts. That is the floor working, not a bug: a thin list produces a thin day,
and a reader cannot tell a quiet day from a broken one. Fix it by adding sources,
not by lowering the floor.

**A feed that is resting is not read at all.** Five failed attempts in a row put
a feed to sleep, and the log says `feed resting id=...` rather than an error.
The rest ends on its own after five skips. Nothing here ever edits
`config/sources.json`, which stays curated by a person - but retirement is no
longer a person's job: five HTTP 410 results across five distinct runs write one
row under `state/raw/feed-retirements/` and the run stops asking that address, for
good. Changing that feed's configured URL makes a new endpoint, with no inherited
strikes and no inherited retirement
([../architecture/sources/health.md](../architecture/sources/health.md)).

## In CI

`.github/workflows/digest.yml`, displayed as `Content refresh`, starts at 02:20,
06:20, 10:20, 14:20, and 18:20 UTC. A plan job loads no weights. It files the
day's plan in the run-plan ledger and hands that day's folder of plans to the
later jobs, and every step after it names its run with `--execution`
([../architecture/contracts/state-ledgers.md](../architecture/contracts/state-ledgers.md)).
A matrix of worker jobs each restores the weights once and works a shard. A scheduled run
derives its own worker count from the day it just planned - at most four, and
fewer on a small day. Manual runs accept one to eight and default to four; the
plan rejects any other dispatched value before it creates the matrix. The `visuals` job uses
their output, and assemble runs **even when a worker failed** - a run that publishes nothing
on a bad day is a run whose bad days are invisible. Each run appends to the
day's payload rather than replacing it, so the day grows through the day. The
workflow names and triggers are pinned in
[../reference/github-actions.md](../reference/github-actions.md)
([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).

## See also

- [troubleshoot-one-url.md](troubleshoot-one-url.md) - isolate one planned URL or use the explicit manual diagnostic workaround.
- [set-up-local-inference.md](set-up-local-inference.md) - getting the runtime and the weights.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - what each stage owns.
- [../concepts/config.md](../concepts/config.md) - the knobs these stages read.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - the cadence, the seen ledger, item ids, and why a day has no cap.
- [../architecture/sources/health.md](../architecture/sources/health.md) - the feed ledger and the quarantine rule.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the item census used to read failed runs.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - what fetch and extract refuse to do.
- [../concepts/evaluation.md](../concepts/evaluation.md) - what the scores mean.
- [../reference/github-actions.md](../reference/github-actions.md) - workflow names and exact triggers.
