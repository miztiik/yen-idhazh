# A 90-day window at month grain against day grain, 2026-09-11

**Last Updated**: 2026-09-11

Frozen. This is one run on one day; it is not updated when a later run
disagrees. A later run gets its own record.

Five `state/` ledgers are moving from one file a month to one file a day
([`../../../TODO/20260910-24-day-sharded-ledgers-plan.md`](../../../TODO/20260910-24-day-sharded-ledgers-plan.md)),
and nobody had priced what that does to a windowed read. The trade is **more
file handles for fewer bytes**: `collect.seen_window_days` is 90, so
`ledger.load_seen` opens at most 4 month files and would open at most 91 day
files - and 4 month shards can hold up to 120 days of rows where 91 day files
hold exactly 90.

## Conditions

| | |
| --- | --- |
| Instrument | `backend/utilities/measure_day_window.py`, default arguments |
| Runtime | CPython 3.14.2, Windows 11 (26200) |
| Box | A developer machine, not a runner. Nothing else heavy was running |
| Fixture | 120 consecutive days, 3,152 sight rows a day, 378,240 rows in all |
| Window | 90 days, anchored on 2026-09-07 |
| Passes | 9 an arm, **interleaved** - month, day, month, day, in one process |

The 3,152 rows a day is the median day of the committed sight ledger on
2026-09-11 (67,205 rows over 20 days), so the fixture is the shape this read
meets rather than a number somebody liked.

**Both arms read one row list written twice.** The rows are identical and only
the layout differs, so a difference between the arms is the layout and cannot be
the data. The month arm is `ledger.load_seen` itself. The day arm is the same
reduction over `<YYYY>/<MM>/<DD>.csv`, written inside the instrument because no
ledger files sight rows by day yet - which is the change being priced.

**The arms are interleaved because a stopwatch here measures the page cache.**
The same bounded reads over one fixture came out 16.6 percent apart minutes
apart on this project, and every arm that writes more files makes the tree
warmer for whatever runs next
([`../agent-notes/gates-and-builds.md`](../agent-notes/gates-and-builds.md)).
Running one arm to completion and then the other measures the order they ran in.

## The arms

| Arm | Files opened | Rows read | Median | Spread |
| --- | --- | --- | --- | --- |
| month | 4 | 312,048 | 2,826.9 ms | 638.7 ms |
| day | 91 | 286,832 | 2,727.8 ms | 499.3 ms |

The day arm opens **87 more files** and reads **25,216 fewer rows**, which is
25.2 thousand rows of the 312.0 thousand the month arm reads - 8.1 percent of
them, and every one of them a day outside the window. The two counts check out
by hand: 91 day files at 3,152 rows is 286,832 exactly, and the four month
shards the window touches hold 99 of the fixture's days rather than 91.

The day arm's median is **99.1 ms faster, 3.5 percent**, and both spreads are
larger than that gap - 22.6 percent of the median on the month arm and 18.3
percent on the day arm.

## What it settles

**The clock does not separate the two layouts**, and the two counts that have no
spread both favour the day grain. 87 more file handles cost less than 25,216
rows of reading on this box.

## What it does not settle

- **Nothing about a runner.** A duration taken on a developer machine is an
  order-of-magnitude check ([`../measurements.md`](../measurements.md)). The
  file and row counts are arithmetic and do travel; the milliseconds do not.
- **Nothing about the other four ledgers.** Sight rows are 118.5 bytes; the
  score row is wider and the seen row is the narrowest of the five, so the
  bytes-saved side of the trade is smallest here and the handle side is the
  same. This is the arm least favourable to the day grain, which is why it was
  the one measured.
- **Nothing about a window that is not 90 days.** A 31-day window opens 32 day
  files against at most 2 month shards, so the handle ratio is different.

## See also

- [`../measurements.md`](../measurements.md) - the instrument log, which carries the figure now in force and links here.
- [`../../concepts/partitions.md`](../../concepts/partitions.md) - what a partition is at either grain.
- [`../../concepts/growing-reads.md`](../../concepts/growing-reads.md) - what a read over a growing collection declares.
