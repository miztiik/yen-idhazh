# What a month out of a year file costs

**Last Updated**: 2026-10-01

What a browser pays to read one month out of a packed year file by byte range,
against the same month's own file read whole and read by byte range, and what it
pays when a deploy changes the year file's ETag while a page holds part of it.

**One month read out of a 29.8 MB year file by byte range cost 243,046 bytes and
drew in 11.0 seconds on a slow 4G link: a tenth of the bytes of the month's own
file, and 4.2 seconds sooner than fetching that file whole.** The month's own file
read by byte range was sooner still, 9.5 seconds for 213,076 bytes. **But a page
that holds part of a year file asks for any other part naming the ETag it kept,
and a deploy changes that ETag.** A host that honours that check, as the HTTP
standard says, then sends the whole year file: 29,816,165 bytes for one month.

## Conditions

| Condition | Value |
| --- | --- |
| Date | 2026-10-01 |
| Browser | Chromium, the build Playwright 1.62 installs. No other browser was run |
| Engine | `@duckdb/duckdb-wasm` 1.33.1-dev57 (DuckDB 1.5.4), the single-threaded build the site ships |
| Host | `frontend/tests/support/range-host.ts` on 127.0.0.1: a ranged GET answered 206, a `HEAD` 200 with the full length, an ETag of modification time and size, `max-age=600`, nothing compressed, `If-Range` honoured as the HTTP standard says |
| Link | Lighthouse's slow 4G, applied by the host to the data files alone: 562.5 ms before each response, then 188,743 bytes a second |
| Machine | A Windows development machine shared with other work. The link sets the times, and three rounds of each read agreed to within 2 percent |
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
file, and `yearly.json` as well for the year file. Three rounds, the three reads in
a different order each round; the figures are medians.

## The three reads

| # | Read | Median | The three rounds | Bytes of the file read | Requests for the file | Index requests |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | The month file, whole | 15.2 s | 15.2, 15.3, 15.2 | 2,490,452 | 1 GET, answered 200 | 2 |
| 2 | The year file, by byte range | 11.0 s | 10.9, 11.1, 11.0 | 243,046 | 12 GETs, each a range answered 206, and 1 `HEAD` | 3 |
| 3 | The month file, by byte range | 9.5 s | 9.5, 9.5, 9.5 | 213,076 | 11 GETs, each a range answered 206, and 1 `HEAD` | 2 |

Every run drew the same 10,257 rows. The year file's reads were its first byte,
79,205 bytes around its footer, and 163,840 bytes of June's row group for the 10
columns. It drew 1.5 seconds later than the month file by range because it asks
for one more index, reads nearly five times the bytes around its footer (79,205
against 16,468), and makes one more request.

## After a deploy

Chromium keeps the ranges a page fetched, and asks for a range it does not hold
with `If-Range` naming the ETag it kept. Pages gives every file a new ETag at
every deploy, over the same bytes. Here one page read June out of the year file,
the year file's ETag then changed with its bytes unchanged, and the same page read
July, unslowed:

| # | What the host was asked for July | Answer | Bytes |
| --- | --- | --- | --- |
| 1 | The first range, with `If-Range` naming the old ETag | 200 and the whole file | 29,816,165 |
| 2 | Seven more ranges, after the browser dropped what it kept | 206 each | 180,224 |

The engine took July's rows out of the whole file correctly, and the 29,996,389
bytes were 12 times what the month's own file costs. On the slow 4G link above,
the whole file alone takes about 158 seconds.

A new page escapes it: it opens the file again, the browser checks the first byte
it kept with `If-None-Match`, learns the file changed, and drops the rest, so every
later range is answered 206. What is caught is a page that holds part of a year
file across a deploy and then reads a part it does not hold, or a new page that
finds the browser's copy of the first byte still within Pages' 600 seconds.
`frontend/tests/ledger-ranges.spec.ts` reproduces both on the small fixture: the
new page that escapes as a passing test, and the copy still fresh as a test
expected to fail until the door reads past it.

## What it settles

- Reading by byte range keeps one month out of a year file to a tenth of the
  month file's bytes, and draws it sooner than the month file whole on a slow
  link. Every GET for the year file was a range answered 206.
- A host that honours `If-Range` sends a page the whole year file once after a
  deploy, when the page already holds part of it.
- Pages is such a host, measured on the live site: a ranged GET whose `If-Range`
  names an ETag it no longer serves, or a date before the file's, gets 200 and the
  whole file, and one naming the current ETag gets 206. Every file in a deploy
  carries that deploy's time, so an unchanged file gets a new ETag every deploy.

## What it does not settle

- How often a page holds part of a year file across a deploy.
- A month file by range on a fast link, where each of its 13 requests is a round
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
It fails when the year file by range costs more than twice the month file's bytes,
when any GET for it is not a range answered 206, or when it draws later than the
month file whole.

## See also

- [../../architecture/publishing/how-the-query-door-answers-a-panel.md](../../architecture/publishing/how-the-query-door-answers-a-panel.md#how-a-year-file-is-read-by-byte-range) - how the door reads a year file by byte range.
- [../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md#a-year) - how a year file is packed, one row group a month.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
