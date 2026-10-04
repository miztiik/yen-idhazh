# How the query door answers a written question

**Last Updated**: 2026-10-04

The query door can run one operator-written, read-only DuckDB statement over the ledgers and UTC days the page chose. The statement sees views, not files.

## Views

`ask()` lives beside `slice()` in `frontend/src/lib/data/ledger.ts`. It uses the same page keeper as the panel path. For each selected ledger, `ask-reader.ts` creates one DuckDB view whose name is a member of `LEDGER_NAMES`. The files inside that view are engine-minted names such as `door/1.parquet`; no index, cell, caller text or fetched text becomes a file name.

Each call first drops every unselected ledger view. This matters because the page keeper can still hold files from an earlier run. Without the drop, a later statement could read a ledger the operator did not select and did not see priced.

Calls run one at a time. The engine has one connection, and each call rewrites the same set of ledger views.

A selected ledger with no file in the span still gets a view, so a statement that names it binds: an empty view (`LIMIT 0`) over the files of its newest day. That day's files come from its listing when the build listed a day after the newest packed one, and otherwise from the packed tier. A packed file with zero rows is used here, though a span's own read skips it: the empty view needs only the file's columns, and a ledger whose packed days all hold zero rows, as `candidate-models` does today, would otherwise reach the engine as `read_parquet([])`, which DuckDB refuses. A selected ledger with no file at all to read its columns from answers `missing`.

## Statement wraps

`statement.ts` is a courtesy refusal. It rejects more than one statement, a statement that does not start with `SELECT`, `WITH`, `DESCRIBE`, `SUMMARIZE` or `EXPLAIN`, and a statement beyond the caller's character limit. It is not the boundary; the browser content policy is.

Before the answer runs, `ask()` asks DuckDB to describe the statement. That gives the answer columns even when no row matches. The run itself wraps most statements as:

```sql
SELECT COLUMNS(*)::VARCHAR FROM (
<operator statement>
) LIMIT <max rows + 1>
```

The statement sits on its own lines so a final `--` comment cannot comment out the closing bracket. `EXPLAIN` runs without that wrap because DuckDB does not parse it there. `SUMMARIZE` and `DESCRIBE` do parse there. Every cell crosses back as text, so decimals, dates, lists and structs keep the engine's own spelling.

## Writers' tier

A date is read through exactly one tier. Packed files win first: year, month, then day, through `filesFor()`. For dates after the newest packed day, `ask()` may read the writers' own parquet files, but only through a staged `RawDayIndex` listing.

The listing must carry `bytes`, one size per file. `askCost()` uses those sizes before a data file is fetched. `ask()` refuses a span above the byte ceiling before a data file is fetched. The page keeper checks the same size when the file arrives.

The site build stages those listings for raw days after each ledger's newest
packed day, up to the widest console preset. A day whose raw directory holds a
non-parquet writer file is left unlisted and the build log names that file. A
listing that is absent inside the listed range is a file gap, not an empty day.

## Reach and cost

`through` is the newest UTC day any selected tier can answer. A daily entry counts as that day. A month counts through its last UTC day. A year counts through 31 December. A staged writer listing can move `through` later than the packed indexes.

`FetchCost` is the keeper's reading for this call. A whole file counts at the bytes that arrived. A file read by byte range counts at the whole indexed length, because the page cannot see which ranges the engine read and that length is the most the read can cost. `alreadyHeld` counts files the keeper already had registered before this call.

## Unreachable fields

`unreachable` carries the fields its sentence prints.

- `ledger` names the ledger when the failure belongs to one ledger; it is `null` for an engine that did not start.
- `at` names the UTC day to retry or explain. For a day file it is that day. For a month or year file it is the first span day that file was chosen for. For a refused daily index it is the span's first day.
- `fault` names a file gap when the indexes prove one: `index-missing`, `file-missing` or `day-missing`. It is `null` for a file that did not arrive whole. It is `engine` when the engine did not start.

When no selected ledger holds a file in the span, `ask()` answers `quiet` and starts no engine. When files are in the span and the statement matches no rows, it also answers `quiet`, with the columns from `DESCRIBE`.

## Boundary

The engine module is unchanged. The only module importing `@duckdb/duckdb-wasm` remains `frontend/src/lib/data/engine.ts`. The browser's shipped `connect-src` policy applies to the engine worker, so a statement that tries to read an unlisted origin is refused by the browser. The boundary test builds its support page with the same policy directives as `svelte.config.js` and asserts the refused request never reaches the network.

## See also

- [how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md) - the panel entry point this one extends.
- [../contracts/schemas.md](../contracts/schemas.md) - the `RawDayIndex` contract and the frontend hand copy.
