"""One compacted ledger, laid out as the committed tree is, for the query door.

`state/` is a state root: `compact/host-fingerprint/index/daily.json` and
`index/monthly.json`, and the compact files they name. The frontend's
`ledger-door.spec.ts` reads it through both of the door's entry points, and
`backend/tests/contracts/test_ledger_door_fixture.py` checks that every entry's
`rows` and `bytes` match the file the backend reader opens.

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
  wrong one, returns a row it should not.
- `2026-09-01`, `2026-09-02` and `2026-09-05` are daily files. 2026-09-01 holds a
  `plan` job beside two `work` jobs, so a filter has something to narrow.
- `2026-09-03` is a zero-row day: compacted, empty, and quiet rather than a hole.
- `2026-09-04` is the hole: at or before the newest daily entry, named by neither
  index.

Regenerating the files changes their bytes, because each envelope records when
it was written; the indexes have to be rebuilt from the new files with them.
"""
