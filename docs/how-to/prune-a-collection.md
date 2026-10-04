# Prune a collection

**Last Updated**: 2026-10-04

How do I delete the old members of a collection, safely, without taking the
whole backlog in one go?

Two routes, one core. `idhazh telemetry prune` takes a range of days out of a
ledger under `state/`: the day files of a CSV ledger, or the rows of a ledger
the door files. The gardener's two collection tasks take members out of a
collection GitHub holds for us. A CSV ledger and a GitHub collection lose one
member at a time; a ledger the door files changes one file at a time, each
written whole. Every route stops at a ceiling and says where the next pass
resumes. What "atomic" means here and why a range is not one is in
[../concepts/atomic-deletes.md](../concepts/atomic-deletes.md).

## Before you start

| You need | Why |
| --- | --- |
| A clean working tree | a live pass deletes committed files, and you want the diff to be only that |
| `GITHUB_TOKEN` in the environment, with `actions:write`, and `GITHUB_REPOSITORY` as `owner/name` | only to run a GitHub collection task by hand; a scheduled wake has both. The token is never read from a file and never printed |
| A run id and the full sha of the checkout | only for a live pass on a ledger the door files: each file it rebuilds names them as its writer |
| The output of a dry run | it is the default, and it is the list you are agreeing to |

## Prune a collection GitHub holds

`workflow-artifacts` and `workflow-runs` are gardener tasks. Each is one
declaration under `config/gardener/`, named for its collection, and
`.github/workflows/idhazh-gardener.yml` runs both at every wake and lands their
rows in its shards' records
([../architecture/publishing/idhazh-gardener.md](../architecture/publishing/idhazh-gardener.md)).
Both ship `dry_run: true`.

### 1. See what the window selects

Read the task's row in the gardener's record from the last wake, under
`state/raw/gardener/<YYYY>/<MM>/<DD>/`: `selected` is how many members the window
holds, `deleted` is how many a live pass would take, up to the ceiling, and
`stopped_because` says whether there is more. That wake's log lists every member
by id. `workflow-runs` reads only the days after `handled_through` on its last
row, so its `selected` counts the runs of those days, and `handled_through` says
how far its walk has got.

To see it now, run the task in a checkout with the two variables exported. It
lists the collection, deletes nothing while the declaration says `dry_run: true`,
writes the record into the checkout and pushes nothing:

```
python -m idhazh gardener run-task workflow-artifacts --run-id <YYYY-MM-DD-N> --attempt 1 --git-sha <sha>
```

The age is `window.value` in `config/gardener/workflow-artifacts.json` and the
ceiling is `max_deletes_per_run` beside it.

### 2. Read the last line before you read the list

| Last line says | What it means | What to do |
| --- | --- | --- |
| `nothing was deleted - a live run would delete the members above` | the pass was a dry run; the line above it says why it stopped | to delete them, follow step 3 |
| `the collection is exhausted` | nothing else is inside the window | one live pass finishes the job |
| `the ceiling of N stopped this pass at <id>` | there is more | each later wake takes the next batch, until the line changes |
| `the ceiling of N would stop a live pass at <id>; the rest of that day was counted, not listed` | a dry run of `workflow-runs` listed the ceiling's worth of one day's runs and counted the rest | nothing; the next dry run starts on the day after the one it names |
| `the pass failed at <id>` | the members above it are gone | fix the cause; the next wake retries that member |
| `the pass failed after N members, before it could name the next one` | the listing itself failed, or a member could not be read | fix the cause; the next wake starts from the oldest member the window holds |

### 3. Delete

Set the declaration's `dry_run` to `false`, in one reviewed commit taken after a
scheduled wake has printed its list, and name the task in `LIVE_BY_DECISION` in
`backend/tests/contracts/test_gardener_config.py` with the decision beside it.
The next wake takes up to the ceiling, and each wake after it takes the next
batch until the last line says the collection is exhausted. Each wake is the
same shape and the same cost whatever the backlog is - that is what the ceiling
is for.

What a wake's exit code means is on the gardener's page: a task that fails part
way is exit 1, and its row says where the next pass starts.

## Prune a range of days out of a ledger

```
idhazh telemetry prune --target feed-health --since 2026-08-24 --until 2026-08-26
```

Both ends are named and both are inclusive, so `--since X --until X` is one day.
`--dry-run` is on by default here too, and `--no-dry-run` is the second word.

`--max-deletes` bounds a pass. Its default is every day the range names, so a
range you typed is taken whole unless you ask for a smaller bite:

```
idhazh telemetry prune --target content-similarity-judge-scored-pairs \
  --since 2025-01-01 --until 2025-12-31 --no-dry-run --max-deletes 30
```

Which ledgers this may be pointed at, and which are refused and why, are in
[../architecture/publishing/retention.md](../architecture/publishing/retention.md#a-named-prune-one-ledger-one-range-of-days).

### A ledger the door files

A ledger whose `config/ledgers.json` entry says `raw-and-compact` keeps a day's
rows in its raw files until a compaction packs them into a daily file, then a
month file, then a year file. One file can hold many days, so a pass takes rows,
not files. For the days it takes, it deletes their raw files, rebuilds each daily, monthly or yearly file
that holds one of them without their rows, and rewrites the index beside it. A
file whose every row goes stays as an empty file, so no index has a hole.

```
idhazh telemetry prune --target item-health --since 2026-08-24 --until 2026-08-26
idhazh telemetry prune --target item-health --since 2026-08-24 --until 2026-08-26 \
  --no-dry-run --run-id 2026-10-01-1 --commit <full sha of the checkout>
```

- A live pass needs `--run-id` and `--commit`. Each file it rebuilds names that
  run and that commit as its writer, so a later reader can trace the file. A
  dry run needs neither; given both, it builds exactly the files the live pass
  writes, so its byte counts are the live pass's.
- Each line of the list says `remove` or `rewrite`. A month or a year file is
  rewritten, never removed, because it holds other days.
- A member is a day, and `--max-deletes` caps the days, oldest first. An index
  counts a file's rows and not a day's, so every day of the range in a month or
  a year file that holds a row counts, whether or not that day filed one.
- Whether the command may take a ledger's days is that ledger's compaction
  declaration's `prune_refusal`, in `config/gardener/compact-<ledger>.json`.
  `null` lets it; a sentence refuses the ledger and is the reason printed.
  `summary-quality-evals` carries one, because every eval row is kept for ever.
- A pass that stopped, on its ceiling or on a failure, is finished by running
  the same command again. It takes only what is left.

## Failure modes

| What you see | What happened | What to do |
| --- | --- | --- |
| `GITHUB_TOKEN is not set` | the token is not exported | export one with `actions:write` for this repository. Never put it in a file |
| `GITHUB_REPOSITORY is not set`, or `a repository is named owner/name` | the repository is not exported, or the slug is wrong | export `GITHUB_REPOSITORY=miztiik/yen-idhazh` |
| `a prune takes the name of a ledger, not ...` | a path was passed where a name belongs | pass a name. There is no argument on either route a path can travel through |
| `published is refused: ...` | you named a ledger that must not forget | read the reason in the message. It is a decision, not an oversight |
| `summary-quality-evals is refused: ...` | the ledger's compaction declaration refuses it | read the reason. Changing it is a reviewed edit to that declaration's `prune_refusal` |
| `--no-dry-run on a ledger on the door rewrites ...` | a live pass on a ledger the door files had no `--run-id` or no `--commit` | pass both: the run id as `YYYY-MM-DD-N` and the full forty-character sha |
| `... cannot be read, so which files hold the days is not known` or `... names <period> and no file holds it` | an index of the ledger is damaged, or names a file that is gone. Nothing was changed | restore the index or the file from git, then run the command again |
| `since is after until` | the two ends are swapped | the oldest day comes first |
| the list, then exit 1 | a delete or a write failed part way; the files listed have already changed | fix the cause, then run the same command again |
| the same members print on every run | the pass is a dry run | for a ledger, add `--no-dry-run`; for a GitHub collection, set its declaration's `dry_run` to `false` |

## See also

- [../concepts/atomic-deletes.md](../concepts/atomic-deletes.md) - what atomic means here, and why a range is not one.
- [../architecture/publishing/retention.md](../architecture/publishing/retention.md) - what bounds each tree, and which ledger carries which window.
- [../concepts/config/idhazh-gardener.md](../concepts/config/idhazh-gardener.md) - the two collection declarations and the ages they keep.
- [run-the-gates.md](run-the-gates.md) - the checks to run after a change to either route.
