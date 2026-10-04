"""Two compacted ledgers and one day of writer files, laid out as the committed tree is, for the query door.

`state/` is a state root: `compact/host-fingerprint/index/daily.json` and
`index/monthly.json`, the compact files they name, and an `index/yearly.json`
that names nothing. `year-state/` is a second state root holding the same August
and September after their year was packed: `index/yearly.json` and
`index/daily.json`, the files they name, and an `index/monthly.json` that names
nothing. The compaction writes a ledger's three indexes together, so each root
carries all three. The
frontend's `ledger-door.spec.ts` reads both through both of the door's entry
points, and `backend/tests/contracts/test_ledger_door_fixture.py` checks that
every entry's `rows` and `bytes` match the file the backend reader opens.

Every row was first filed raw by the backend door, `persist()`, under the identity
of the job that measured it. Each compact file was then built the way the
gardener's compaction builds one: the raw files read back with `load_stored()`,
settled with `settle_rows()` by the key the ledger's day tree declares, and
written by `persist_period()`. So every row keeps the identity its raw file gave
it - its `covers` cell is the day it was filed under, even inside the month file
- and each envelope names `gardener.tasks.compaction` as its producer. The month
was absorbed from daily files of its own two days. The zero-row day went through
`persist_period()` with no rows. The indexes were built from what landed on disk
and serialized by `CompactIndex` itself.

Nothing in the pipeline writes this ledger's compact tier yet: `host-fingerprint`
is still a day tree, and the compaction's door table does not name it. This is
the tier as the compaction writes one for a ledger that does.

What the days exercise:

- `2026-08` is one monthly file: two jobs on 2026-08-30, one on 2026-08-31.
- `2026-08-31` is also a daily file, holding a different job. A day named by both
  indexes is read from the month, so a reader that opens both files, or the
  wrong one, returns a row it should not. A span that starts on 2026-08-31
  reads the month for that day alone, so a reader that keeps the whole month
  returns 2026-08-30's two rows as well.
- `2026-09-01`, `2026-09-02` and `2026-09-05` are daily files. 2026-09-01 holds a
  `plan` job beside two `work` jobs, so a filter has something to narrow.
- `2026-09-03` is a zero-row day: compacted, empty, and quiet rather than a hole.
- `2026-09-04` is the hole: at or before the newest daily entry, named by neither
  index.

What the packed year holds:

- `yearly/2026/2026.parquet` was built by the compaction's own year writer,
  `render_grouped_period()`, from `state/`'s August month file and its September
  day files, one row group each, so a month read from it is the month `state/`
  serves. Its first rows are in August, and its entry still covers all of 2026.
- `daily/2027/01/01.parquet` is a zero-row day, so the daily index names a day
  and the span before it reaches back into the year.
- Its `monthly.json` names nothing: every month the ledger held went into its year.

Regenerating the files changes their bytes, because each envelope records when
it was written; the indexes have to be rebuilt from the new files with them.

The second ledger, `item-health`, exists so a written question can join two
ledgers. In both roots it is a byte copy of `host-fingerprint`'s compact files,
filed under `item-health`'s paths, with indexes that name `item-health`. Its
envelopes still name `host-fingerprint`. The door reads indexes and rows and
never an envelope, so the copy answers a join exactly as a second compacted
ledger would; no backend reader opens it as `item-health`.

`raw/item-health/index/2026-09-06.json` lists one day not packed yet, the way
the site build stages one: two writer files under `raw/item-health/2026/09/06/`,
with each file's size in `bytes`. Their `hostile` cells hold a script tag and an
address, which must reach an answer as text and as nothing else.

`answers/<case>.json` holds the rows each written-question case in
`ledger-door.spec.ts` must return, as the engine's text. `test_ledger_door_fixture.py`
recomputes every one with DuckDB in Python, so a regenerated fixture that moves an
answer fails until the answer is regenerated with it. Each case has exactly one
right answer: its statement orders its rows completely, or ties only rows that
read the same, because rows that tie may come back in any order.
"""
