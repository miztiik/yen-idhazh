# How the query door answers a written question

**Last Updated**: 2026-10-02

The query door can run one operator-written, read-only DuckDB statement over chosen ledgers and UTC days. The page chooses the ledgers and the dates; the statement sees only views named from the closed ledger list. It never chooses a file.

## What `ask()` does

`ask()` lives beside `slice()` in `frontend/src/lib/data/ledger.ts`. It reads compact files through the same page keeper as panels, then creates one DuckDB view per selected ledger. Each view is named from `LEDGER_NAMES`; every file name in it was minted by the engine. Before each run the door drops every unselected ledger view, so a later question cannot read a ledger the operator did not select and price.

The operator statement passes `statement.ts` first. That module refuses more than one statement, a statement that does not start with `SELECT`, `WITH`, `DESCRIBE`, `SUMMARIZE` or `EXPLAIN`, and a statement beyond the caller's character limit. This is a courtesy refusal, not the boundary. The browser content policy is the boundary on what the engine can fetch.

## How the answer is bounded

`askCost()` reads indexes and staged raw-day listings only. It counts files and bytes before data files are fetched. `ask()` refuses a span above the caller's byte ceiling before any data file is fetched. Rows are capped in the engine by wrapping the statement on its own lines, so a trailing line comment cannot eat the wrapper. Cells cross back as text, and column names and types come from `DESCRIBE`.

## The writers' tier

A date is read through one tier only. Packed files win first. For dates after the newest packed day, `ask()` may read writer files only through a staged `RawDayIndex` listing. That listing carries one byte size per file, so the browser can price and check it. Until the site build stages listings, `__RAW_LISTED_THROUGH__` names no day and `ask()` reads packed files only.

## Boundary

The engine module is unchanged. The only module importing `@duckdb/duckdb-wasm` remains `frontend/src/lib/data/engine.ts`. The browser's `connect-src` policy applies to the engine worker, so a statement that tries to read an unlisted origin is refused by the browser before the request reaches the network.

## See also

- [how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md) - the panel entry point this one extends.
- [../contracts/schemas.md](../contracts/schemas.md) - the `RawDayIndex` contract and the frontend hand copy.
