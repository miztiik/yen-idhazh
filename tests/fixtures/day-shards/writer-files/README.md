"""One day directory of writer-owned files, for the walker that settles them.

`2026/09/18/` is a day: three writer files, each named
`<run_id>-<attempt>-<job>-<shard>.csv`, and no two writers can name one file.
There is no head above it, so the settlement is something the reader does.

The rows are candidate-model verdicts with a date, run and model key.
What they exercise:

- `candidate-0` is written at attempt 1 and again at attempt 2 with different
  figures. Both rows fill `articles` and `measured_hhem`, so they are contested and the
  higher attempt wins each cell - the supersede case.
- `candidate-extra` is written identically at both attempts. Contested, the
  higher attempt wins, and the answer is the same row - the repeat case.
- `candidate-1` is written once, by a different writer of the same run at the
  same attempt - a second key rather than a second copy of the first.

So one day directory of three files settles to three records. Every row carries
`2026-09-18` as its `version`, which the
contract accepts and nothing here reads. The fold ignores that cell by
construction, so it is a stamp rather than a schema date this fixture has to
keep in step with.
