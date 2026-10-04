# What a parquet file costs

**Last Updated**: 2026-10-04

How much of a parquet file is a charge every file pays whatever its row count,
and so how many rows must share one file before it is smaller than the same
rows as CSV.

**What decides the cost is how many rows share a file.** One parquet file of
220 `item-health` rows is 2.6 times smaller than the same rows as CSV.
`host-fingerprint` rows filed as 79 files of one or two rows each are 15.1 times
larger than the same rows as CSV. That is the reason a compaction packs a
ledger's raw files into one file a day and a month, and a gardener shard files
one record for all its tasks rather than one a task.

## Conditions

| Condition | Value |
| --- | --- |
| Dates | 2026-09-24 for the row table; 2026-09-25 for the two ledger readings |
| Machine | A Windows development machine for the row table; not recorded for the ledger readings. A byte count does not change with the machine |
| Engine | Not recorded with the figures |
| Compression | snappy and zstd for the row table, one column each; not recorded for the ledger readings |
| Method | The same rows written as CSV and as parquet, and the sizes of the files compared |

## One row shape at four row counts

A row of 13 columns. Every figure is bytes.

| Rows in the file | CSV | parquet, snappy | parquet, zstd |
| --- | --- | --- | --- |
| 1 | 224 | 3,796 | 4,017 |
| 13 | 1,070 | 4,184 | 4,459 |
| 91 | 6,920 | 6,731 | 5,195 |
| 1,000 | 80,495 | 35,592 | 15,949 |

At snappy each row adds about 32 bytes, so about 3,764 bytes of every file of
this row shape are paid whatever the row count, and by 91 rows the parquet file
is the smaller one. At a thousand rows zstd is 2.2 times smaller than snappy; at
1 and 13 rows it is larger.

## Two ledgers, packed and not packed

The eight newest `item-health` CSV files committed on 2026-09-25, 220 rows of
122 columns:

| What | Bytes | Against the CSV |
| --- | --- | --- |
| The eight CSV files as committed | 225,711 | - |
| One parquet file, every column | 87,714 | 2.6 times smaller |
| One parquet file, the 83 columns a page read then | 62,304 | 3.6 times smaller |
| One parquet file, every column, per-column statistics off | 81,739 | 2.8 times smaller, and 6.8 percent below the same file with statistics |

Three days of `host-fingerprint`, one file per writer: 79 files of one or two
rows of 31 columns. Their 57,888 bytes of CSV became 873,872 bytes of parquet,
15.1 times larger. A one-row file of 31 columns is about 9,300 bytes of page,
dictionary and statistics overhead around 370 bytes of data.

## What it settles

- Packing decides the cost. A ledger packed into one file was 2.6 times smaller
  than its CSV, and a ledger filed as one file per writer was 15.1 times larger.
- The charge every file pays grows with its columns: about 3,764 bytes at 13
  columns and about 9,300 at 31. So the row count at which parquet becomes the
  smaller file differs from one ledger to the next.

## What it does not settle

- Where one particular ledger breaks even. Take the reading again at its own
  column count: write a day of its rows through `ledger.persist` as one file and
  as one file per writer, and compare both with the CSV of the same rows.
- Which compression the two ledger readings used, and what another engine or
  engine version writes: a parquet footer names the engine that wrote it, so the
  bytes change with it.
- Anything about time: how long a file takes to write, read or download.

## See also

- [../../architecture/contracts/persistence.md](../../architecture/contracts/persistence.md) - the door that writes these files, and its compression knobs.
- [../../architecture/publishing/ledger-compaction.md](../../architecture/publishing/ledger-compaction.md) - the compaction that packs a ledger's raw files into one file a day and a month.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
