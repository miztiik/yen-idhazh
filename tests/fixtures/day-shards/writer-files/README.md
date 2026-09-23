"""One day directory of writer-owned files, for the walker that settles them.

`2026/09/18/` is a day: three writer files, each named
`<run_id>-<attempt>-<job>-<shard>.csv`, and no two writers can name one file.
There is no head above it, so the settlement is something the reader does.

The rows are `span-rollup`, which has seven columns and a four-cell key, so the
settlement can be read by eye. What they exercise:

- `shard 0, item` is written at attempt 1 and again at attempt 2 with different
  figures. Both rows fill `count` and `total_ms`, so they are contested and the
  higher attempt wins each cell - the supersede case.
- `shard 0, robots` is written identically at both attempts. Contested, the
  higher attempt wins, and the answer is the same row - the repeat case.
- `shard 1, item` is written once, by a different writer of the same run at the
  same attempt - a second key rather than a second copy of the first.

So one day directory of three files settles to three records. Every row carries
`2026-09-06` as its `version` - the date the span record begins, which the
contract accepts and nothing here reads. The fold ignores that cell by
construction, so it is a stamp rather than a schema date this fixture has to
keep in step with.
