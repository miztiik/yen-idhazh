# The eval ledger's ID folder, one closed month and one open month

`summary-quality-evals-index/` is a copy of the folder the eval writer files its
measurement IDs into: one 64-character digest a row, one file per writer under
each day's folder. It was written by the real segment writer, and the 3rd was
settled by the real day fold, so every name and byte is one a run leaves.

The tests ask it at a wake on 2026-10-01, when August closed a month ago and
September is not closed yet: it ended at that wake's first instant, and a month
closes one whole day after it ends.

- `2026/08/03/` holds `settled.csv`, the day fold's answer for IDs `a1` and
  `a2`, and beside it a re-run's later file with `a3`: a closed day and a
  straggler.
- `2026/08/17/` holds two writers of one run, `work` with `b1` and `b2` and
  `assemble` with `b2` and `b3`, so one ID is filed twice and settles once.
- `2026/08/31/` holds one writer with `c1`, on the month's last day.
- `2026/09/29/` holds one writer with `d1`: a closed day of the open month.
- `2026/09/30/` holds one writer with `e1`: a day not closed yet at that wake.

So August holds five files and seven distinct IDs, and a fold that settles
months leaves it one `settled.csv` holding those seven, once each. Each ID is
the SHA-256 of `id-months-` and its label.
