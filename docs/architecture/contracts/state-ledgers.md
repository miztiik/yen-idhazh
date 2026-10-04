# The ledgers under state/

**Last Updated**: 2026-10-02

`state/` is the only memory this pipeline has. Every run starts on a fresh machine with a fresh checkout, so anything one run needs to tell the next is committed (CLAUDE.md Guardrail #1). This page says what each committed ledger answers and why it files at the grain it does.

Three neighbours own the rest of the question. [schemas.md](schemas.md) owns the shape of a row and the rule that decides a grain. [../../concepts/partitions.md](../../concepts/partitions.md) owns what counts as a day file and a month name. [ledger-registry.md](ledger-registry.md) owns which ledgers exist, where each one sits, and the check that stops the build when the code and `config/ledgers.json` disagree. This page is the per-ledger answer: this ledger, this grain, this reason.

Every ledger here is append-only except two that rewrite a whole file: `state/item-health-summary/` rewrites a month's summary, and `state/day-metrics/` rewrites one day's record when that day is corrected. The section on the first says why.

## A ledger partitions only when its read carries a time window

A window lets the reader name the files it wants and skip the rest. Without one every file is opened anyway, and splitting the ledger buys no read time at all. The rule is [schemas.md](schemas.md); `state/raw/feed-retirements/` and `state/raw/visual-prunes/` are the declared exceptions, and they are named below with what they bought instead.

**The day grain buys the same two things everywhere it appears.** A run writes one day, so two runs collide on a file only when they are the same day. And taking a day back off the record is one `rm` rather than an edit inside a shared file, which an append-only ledger cannot express.

## What each ledger answers

| Ledger | Answers | Grain | Read window |
| --- | --- | --- | --- |
| `state/raw/seen/<YYYY>/<MM>/<DD>/<file_id>.parquet` | How old is this? - for an article whose feed carried no date. One file per plan job | raw and compact | `collect.seen_window_days` |
| `state/raw/published/<YYYY>/<MM>/<DD>/<file_id>.parquet` | Have we already run this? One file per assemble job | raw and compact | `collect.published_window_days` |
| `state/raw/feed-health/<YYYY>/<MM>/<DD>/<file_id>.parquet` | Is this source still working? One row per feed per run, one file per plan job | raw and compact | `HEALTH_WINDOW_DAYS` |
| `state/raw/item-health/<YYYY>/<MM>/<DD>/<file_id>.parquet` | What did every planned item do? One row per planned item per run, one file per writer | raw and compact | the published projection, a month at a time |
| `state/item-health-summary/<YYYY-MM>.csv` | What is left of an item-health month | month file | the whole file |
| `state/raw/feed-retirements/<YYYY>/<MM>/<DD>/<file_id>.parquet` | Is this address gone for good? One file per writer, under the day the address was retired | raw and compact | the whole tree |
| `state/raw/visual-prunes/<YYYY>/<MM>/<DD>/<file_id>.parquet` | Is the picture backlog shrinking? One file per run | raw and compact | the whole tree |
| `state/raw/gardener/<YYYY>/<MM>/<DD>/<file_id>.parquet` | What did each gardener task see, take and leave at one wake? One file per shard | raw and compact | none yet |
| `state/raw/run-plan/<YYYY>/<MM>/<DD>/<file_id>.parquet` | What plan did the day hand to its later stages? One row per plan execution | raw and compact | the named UTC day |

The seen ledger has no published mirror at all, so unlike the two health ledgers there is no second grain anywhere near it.

The run-plan ledger is the handoff between planning and later stages. The plan
stage writes it through the ledger door, and readers ask for one named UTC day
through `ledger.load_days`. If a day has more than one execution, the reader
uses the newest `generated_at` value, then `run_id` as a stable tie-breaker.

The console reads the feed record at build time from its packed files under `state/compact/feed-health/`, so the Voices page stops at the newest packed day. There is no published mirror; the one that existed until 2026-09-16 was never fetched.

`state/raw/item-health/` is the fastest-growing ledger in the table above. The console reads it a month at a time through the published projection, which stays monthly: `public_telemetry.publish` folds a month from that month's days, read through `ledger.load_days` ([persistence.md](persistence.md#reading-a-whole-ledger)).

`state/raw/feed-retirements/` is read whole because a retirement has no time bound. It files by day anyway, for the reason the section on the two whole-read ledgers gives below. It is also the smallest: a row is written only when a server has reported one address permanently gone on five distinct runs, and none had been written when it moved under `state/raw/` on 2026-09-28.

## The gardener

`state/raw/gardener/` is the first ledger born under the two roots the ledger door files into. Each gardener shard writes one file a wake through `ledger.persist`, holding one `CollectionPruneRow` per task it ran - a dry run included - and lands it itself ([../publishing/idhazh-gardener.md](../publishing/idhazh-gardener.md)). A row names the task, the run, the attempt, the job and the shard that wrote it, what the pass saw and took, why it stopped, the task's own wall clock, the instant the shard finished working, and `cone_bytes`, what the folders the shard owns weighed at the commit it checked out, beside `downloaded_bytes`, what the shard downloaded for its tasks to read - both empty on a row a hand run wrote, because a hand run weighs nothing.

Nothing reads it yet, so it has no read window. It files at the `raw-and-compact` grain; what `prefix` means for that grain, and which builders refuse it, is [ledger-registry.md](ledger-registry.md#a-ledger-under-the-two-roots).

## The published ledger sizes from the ceiling, not from today

The published ledger files by the day the published tree itself uses. The assemble job files one raw file under `state/raw/published/` for the day its own rows name, and writes no other day.

Its read carries `collect.published_window_days`, and the committed config sets that to `-1`. So today every day is read, one held month at a time, and the answer is every address ever published. **The day grain is what makes a finite cover possible at all**: it names the days in range and reads those days and no others. Until a window is set, the grain buys a file of its own for every writer, and not a faster read.

Size it from the ceiling. A run plans at most `run.safety_ceiling_per_run` items, which the committed config sets to 80, and the schedule fires five times a day - so a day writes at most 400 rows and a year at most about 146,000.

The whole read holds one month's rows and the answer at a time, whatever the history holds. `backend/tests/test_ledger.py::test_load_published_costs_the_answer_and_not_the_file` doubles the months held and checks that the peak stays flat. The read times measured on 2026-09-08 were of the CSV day files this ledger no longer keeps, so they are not repeated here; git history holds them. See [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md).

## The item-health summary files by month because it summarises a month

`state/item-health-summary/<YYYY-MM>.csv` is what is left of an item-health month once the `full-grain` series of `config/gardener/telemetry-aggregate.json` has passed: one row per date and stage, folded by `retention.compact_month`.

A day file of a month's totals is a shape nothing consumes, so it files by month. It is also the one ledger here that is rewritten rather than appended, because every row in it is derived from the days it summarises.

## Why the two whole-read ledgers file by day anyway

`state/raw/feed-retirements/` and `state/raw/visual-prunes/` are the declared exceptions to the partition rule. Neither read will ever carry a window, so the layout buys them no read time at all.

What it buys is what the ledger door buys every ledger that goes through it ([persistence.md](persistence.md)): each writer files a file of its own, so two runs never write one file and neither tree needs a merge driver, and taking a day back off the record is one `rm` of that day's folder. Five cleanup rows a day for ever is a collection that grows, and a collection that grows here takes the layout every other growing one has.

A cleanup row is written on every run, including the runs where the policy is switched off and there is nothing to clean. A report of "nothing to do" is what makes the day the policy starts working visible.

## A missing file is an answer, not a failure

No reader fails on a missing file. A fresh clone has no history, and a run with no history is a run where nothing was seen, nothing was published and no feed has a record yet - which is exactly what an empty result says.

Callers pass the state directory and never the file name. The layout is one fact, and it lives in `config/ledgers.json`, which [ledger-registry.md](ledger-registry.md) explains.

## See also

- [ledger-registry.md](ledger-registry.md) - which ledgers exist, where each one sits, and the check that stops the build when the code and `config/ledgers.json` disagree.
- [persistence.md](persistence.md) - the ledger door: parquet and JSON lines under `state/raw/` and `state/compact/`, and how the engine is swapped.
- [schemas.md](schemas.md) - the shape of a row, and the rule that decides whether a ledger partitions.
- [../../concepts/partitions.md](../../concepts/partitions.md) - what counts as a day file and a month name, and how a collection changes grain.
- [../../concepts/adaptive-pruning.md](../../concepts/adaptive-pruning.md) - what happens to these rows as they age.
- [../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12 - every read must have a fixed-size input.
- [../publishing/retention.md](../publishing/retention.md) - the windows that empty them again.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - where a measured number carries its hardware and date.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #1, Guardrail #12, section 2.
