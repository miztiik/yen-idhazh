# The ledgers under state/

**Last Updated**: 2026-09-27

`state/` is the only memory this pipeline has. Every run starts on a fresh machine with a fresh checkout, so anything one run needs to tell the next is committed (CLAUDE.md Guardrail #1). This page says what each committed ledger answers and why it files at the grain it does.

Three neighbours own the rest of the question. [schemas.md](schemas.md) owns the shape of a row and the rule that decides a grain. [../../concepts/partitions.md](../../concepts/partitions.md) owns what counts as a day file and a month name. [ledger-registry.md](ledger-registry.md) owns which ledgers exist, where each one sits, and the check that stops the build when the code and `config/ledgers.json` disagree. This page is the per-ledger answer: this ledger, this grain, this reason.

Every ledger here is append-only except three that rewrite a whole file: `state/item-health-summary/` and `state/score-archive/` rewrite a month's summary, and `state/day-metrics/` rewrites one day's record when that day is corrected. The section on the first says why.

## A ledger partitions only when its read carries a time window

A window lets the reader name the files it wants and skip the rest. Without one every file is opened anyway, and splitting the ledger buys no read time at all. The rule is [schemas.md](schemas.md); `state/visual-prunes/` is the one declared exception, and it is named below with what it bought instead.

**The day grain buys the same two things everywhere it appears.** A run writes one day, so two runs collide on a file only when they are the same day. And taking a day back off the record is one `rm` rather than an edit inside a shared file, which an append-only ledger cannot express.

## What each ledger answers

| Ledger | Answers | Grain | Read window |
| --- | --- | --- | --- |
| `state/seen/<YYYY>/<MM>/<DD>.csv` | How old is this? - for an article whose feed carried no date | day file | `collect.seen_window_days` |
| `state/published/<YYYY>/<MM>/<DD>.csv` | Have we already run this? | day file | `collect.published_window_days` |
| `state/feed-health/<YYYY>/<MM>/<DD>.csv` | Is this source still working? One row per feed per run | day file | `HEALTH_WINDOW_DAYS` |
| `state/item-health/<YYYY>/<MM>/<DD>.csv` | What did every planned item do? One row per planned item per run | day file | the published projection, a month at a time |
| `state/item-health-summary/<YYYY-MM>.csv` | What is left of an item-health month | month file | the whole file |
| `state/feed-retirements.csv` | Is this address gone for good? | one file | the whole file |
| `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` | Is the picture backlog shrinking? | day file | the whole tree |

`state/seen/` has no published mirror at all, so unlike the two health ledgers there is no second grain anywhere near it.

`state/feed-health/` is read by the console directly at build time. There is no published mirror; the one that existed until 2026-09-16 was never fetched.

`state/item-health/` is the fastest-growing of the four day-filed ledgers. The console reads it a month at a time through the published projection, which stays monthly: `public_telemetry.publish` folds a month from that month's day files.

`state/feed-retirements.csv` is read whole because a retirement has no time bound, so it is one file. It is also the smallest: a row is written only when a server has reported one address permanently gone on five distinct runs.

## The published ledger sizes from the ceiling, not from today

`state/published/` is the grain the published tree itself uses, and a run appends to the day its own rows name and to nothing else.

Its read carries `collect.published_window_days`, and the committed config sets that to `-1`. So today every day file is opened and the answer is every address ever published. **The day grain is what makes a finite cover possible at all**: it names the days in range and opens those files and no others. Until a window is set, the grain buys a small merge surface and a removal that is one `rm`, and not a faster read.

Size it from the ceiling. A run plans at most `run.safety_ceiling_per_run` items, which the committed config sets to 80, and the schedule fires five times a day - so a day writes at most 400 rows and a year at most about 146,000.

Measured 2026-09-08 on an Intel Core i7-1265U over the 7,600 committed rows, header included:

| Quantity | Reading |
| --- | --- |
| A row on disk | 106.9 B |
| A year at the ceiling | 15.6 MB |
| Reading the whole file | median 32.7 ms over fifteen consecutive runs, best 30.1, worst 37.5 |
| The same read with other jobs on the box | as slow as 68.6 ms |

That last row is the number to remember before reading any wall clock here as a property of the file. The 16 committed days average 475 rows a day, which is above the ceiling arithmetic because they were written under three different ceilings - 200 until 2026-08-26, 160 until 2026-09-07, 80 since - and the newest full day wrote 357. See [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md).

## The item-health summary files by month because it summarises a month

`state/item-health-summary/<YYYY-MM>.csv` is what is left of an item-health month once `observability.item_health_full_grain_months` has passed: one row per date and stage, folded by `retention.compact_month`.

A day file of a month's totals is a shape nothing consumes, so it files by month. It is also the one ledger here that is rewritten rather than appended, because every row in it is derived from the days it summarises.

## Why visual-prunes files by day anyway

`state/visual-prunes/` is the declared exception to the partition rule. Its read will never carry a window, so the layout buys it no read time at all.

What it buys is the two things the day grain buys `state/published/`: two runs collide on a file only when they are the same day, and taking a day back off the record is one `rm`. Five rows a day for ever is a collection that grows, and a collection that grows here takes the layout every other growing one has.

A row is written on every run, including the runs where the policy is switched off and there is nothing to clean. A report of "nothing to do" is what makes the day the policy starts working visible.

## A missing file is an answer, not a failure

No reader fails on a missing file. A fresh clone has no history, and a run with no history is a run where nothing was seen, nothing was published and no feed has a record yet - which is exactly what an empty result says.

Callers pass the state directory and never the file name. The layout is one fact, and it lives in `config/ledgers.json`, which [ledger-registry.md](ledger-registry.md) explains.

## See also

- [ledger-registry.md](ledger-registry.md) - which ledgers exist, where each one sits, and the check that stops the build when the code and `config/ledgers.json` disagree.
- [persistence.md](persistence.md) - the ledger door: parquet and JSON lines under `state/raw/` and `state/compact/`, and how the engine is swapped.
- [schemas.md](schemas.md) - the shape of a row, and the rule that decides whether a ledger partitions.
- [../../concepts/partitions.md](../../concepts/partitions.md) - what counts as a day file and a month name, and how a collection changes grain.
- [../../concepts/adaptive-pruning.md](../../concepts/adaptive-pruning.md) - what happens to these rows as they age.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over one of these ledgers costs as it grows.
- [../publishing/retention.md](../publishing/retention.md) - the windows that empty them again.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - where a measured number carries its hardware and date.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #1, Guardrail #12, section 2.
