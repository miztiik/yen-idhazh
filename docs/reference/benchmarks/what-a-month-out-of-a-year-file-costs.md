# What a month out of a year file costs

**Last Updated**: 2026-10-04

What a browser pays to read one month out of a packed year file by byte range,
against the same month's own file read whole and read by byte range, what a
second read of that month on the same page pays, and what a deploy that changes
the year file's ETag between two reads costs.

**One month read out of a 29.8 MB year file by byte range cost 243,046 bytes and
drew in 10.9 seconds on a slow 4G link: a tenth of the bytes of the month's own
file, and 4.2 seconds sooner than fetching that file whole.** The month's own file
read by byte range was sooner still, 9.4 seconds for 213,076 bytes. **Read again
on the same page, the month cost the same 243,046 bytes and drew in 9.0
seconds**, because each read asks at an address of its own and the page keeps
nothing of the file. In return, a deploy between two reads costs no whole file:
every request after it was a range answered 206, where a read at the address an
earlier read used was sent all 29,816,165 bytes.

## Conditions

| Condition | Value |
| --- | --- |
| Date | 2026-10-01 |
| Browser | Chromium 151, the build Playwright 1.62 installs. No other browser was run |
| Engine | `@duckdb/duckdb-wasm` 1.33.1-dev57 (DuckDB 1.5.4), the single-threaded build the site ships |
| Host | `frontend/tests/support/range-host.ts` on 127.0.0.1: a ranged GET answered 206, a `HEAD` 200 with the full length, an ETag of modification time and size, `max-age=600`, nothing compressed, `If-Range` honoured as the HTTP standard says |
| Link | Lighthouse's slow 4G, applied by the host to the data files alone: 562.5 ms before each response, then 188,743 bytes a second |
| Machine | A Windows development machine shared with other work. The link sets the times, and three rounds of each read agreed to within 3 percent |
| Year file | 2025: 29,816,165 bytes, 123,084 rows of the eval ledger's 42 columns, 12 row groups of 10,257 rows, one a month; its footer is 70,553 bytes |
| Month file | June 2025: 2,490,452 bytes, the same 10,257 rows in one row group |
| Columns | The 10 eval-ledger columns the console's model-change panel draws: `date`, `model_id`, `summary_words`, `source_words_before_cap`, `source_words`, `extractiveness`, `verbatim_run`, `band`, `unsupported_numbers`, `hedge_dropped` |

**How the files were built.** The 28 committed day files of the eval ledger for
September 2026 were read back with `ledger.load_stored`, and their 10,257 rows were
re-dated into each month of 2025. The year file was written by the compaction's
own year writer, `ledger.render_grouped_period`, one row group a month, and June by
its month writer, `ledger.render_period`.

**How a run went.** A fresh browser context; the query door's page, its engine
and the engine's parquet add-on loaded first over an unslowed root; then one slice
of June 2025 through the door, timed in the page from the call to its rows. Each
run read its indexes as a page does: `daily.json` and `monthly.json` for the month
file, and `yearly.json` as well for the year file. The fourth read is the second
slice of June on a page that has just read it once, timed the same way. Three
rounds, the four reads in a different order each round; the figures are medians.

## The four reads

| # | Read | Median | The three rounds | Bytes of the file read | Requests for the file | Index requests |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | The month file, whole | 15.1 s | 15.1, 15.1, 15.2 | 2,490,452 | 1 GET, answered 200 | 2 |
| 2 | The year file, by byte range | 10.9 s | 10.9, 10.8, 11.1 | 243,046 | 12 GETs, each a range answered 206, and 1 `HEAD` | 3 |
| 3 | The month file, by byte range | 9.4 s | 9.4, 9.4, 9.6 | 213,076 | 11 GETs, each a range answered 206, and 1 `HEAD` | 2 |
| 4 | The year file, by byte range, read again on the same page | 9.0 s | 9.0, 9.0, 9.1 | 243,046 | 12 GETs, each a range answered 206, and 1 `HEAD` | 0 |

Every run drew the same 10,257 rows. The year file's reads were its first byte,
79,205 bytes around its footer, and 163,840 bytes of June's row group for the 10
columns. It drew 1.5 seconds later than the month file by range because it asks
for one more index, reads nearly five times the bytes around its footer (79,205
against 16,468), and makes one more request.

**A second read pays its bytes again.** It asked for the same twelve ranges as the
first, byte for byte: the engine keeps nothing of a file it has dropped, and the
browser holds nothing at an address no earlier read used. It drew 1.8 seconds
sooner than the first read on its page, whose median was 10.8 seconds, because the
page already held the three indexes the first read asked for.

## After a deploy

Chromium keeps the ranges a page fetched under their address, and asks for a
range it does not hold at that address with `If-Range` naming the ETag it kept.
Pages gives every file a new ETag at every deploy, over the same bytes. Here one
page read June out of the year file, the year file's ETag then changed with its
bytes unchanged, and the same page read July, unslowed. Rows 1 and 2 come from
the run before each read had an address of its own, when every read of a version
asked at one address; they were not taken again, because the door no longer asks
that way. Row 3 is this run.

| # | How July's read was addressed | What the host was asked for July | Answer | Bytes |
| --- | --- | --- | --- | --- |
| 1 | At the address June's read used | The first range, with `If-Range` naming the old ETag | 200 and the whole file | 29,816,165 |
| 2 | At the address June's read used | Seven more ranges, after the browser dropped what it kept | 206 each | 180,224 |
| 3 | At an address of its own | Twelve ranges; each `If-Range` named the ETag the host gave that read | 206 each | 275,814 |

At the shared address the engine took July's rows out of the whole file
correctly, and the 29,996,389 bytes were 12 times what the month's own file costs.
On the slow 4G link above, the whole file alone takes about 158 seconds. At an
address of its own the browser held nothing, so no request named the old ETag.

`frontend/tests/ledger-ranges.spec.ts` reproduces both ways a deploy can fall
between two reads on the small fixture - the same page reading again, and a new
page opened while what an earlier page fetched is still fresh within Pages' 600
seconds - and requires every GET for the year file to be answered 206 and every
`If-Range` to name the ETag the host gave that read.

## What it settles

- Reading by byte range keeps one month out of a year file to a tenth of the
  month file's bytes, and draws it sooner than the month file whole on a slow
  link. Every GET for the year file was a range answered 206.
- A second read of the same month on one page costs its bytes again, 243,046,
  and still drew sooner than the month file whole: 9.0 seconds against 15.1.
- With an address of its own for each read, a deploy between two reads costs no
  whole file.
- Pages honours `If-Range`, measured on the live site: a ranged GET whose
  `If-Range` names an ETag it no longer serves, or a date before the file's, gets
  200 and the whole file, and one naming the current ETag gets 206. Every file in
  a deploy carries that deploy's time, so an unchanged file gets a new ETag every
  deploy.

## What it does not settle

- How often a page reads the same year file twice.
- A deploy that lands inside one read, between its first request and its last,
  which still sends that read the whole file. About 1 read in 500 on a slow
  mobile link (ESTIMATE, from an 11-second read and a deploy about every 85
  minutes).
- A month file by range on a fast link, where each of its 12 requests is a round
  trip the whole file does not make. Take the three reads again unslowed before
  moving month files to ranges.

## How to take it again

1. Build a year file and one month file of the same year as above, named
   `year-<YYYY>.parquet` and `month-<YYYY>-<MM>.parquet`, in one folder outside
   the repository.
2. From `frontend/`, after `npm run build:canary`, which the browser suite's
   preview server needs:

```powershell
$env:IDHAZH_RANGE_BENCH_DIR = '<that folder>'
npx playwright test tests/ledger-ranges.spec.ts -g measure
```

The case writes every run to `frontend/test-results/ledger-ranges/measure.json`.
It fails when the year file by range, read once or read again, costs more than
twice the month file's bytes, when any GET for it is not a range answered 206,
when either draws later than the month file whole, or when the read after a
deploy is answered with the whole year file.

## See also

- [../../architecture/publishing/how-the-query-door-answers-a-panel.md](../../architecture/publishing/how-the-query-door-answers-a-panel.md#how-a-year-file-is-read-by-byte-range) - how the door reads a year file by byte range, at an address of its own for each read.
- [../../architecture/publishing/ledger-compaction.md](../../architecture/publishing/ledger-compaction.md#a-year) - how a year file is packed, one row group a month.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
