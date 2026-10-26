# How the query door answers a written question

**Last Updated**: 2026-10-23

The Data explorer runs one operator-written, read-only DuckDB statement over the tables that SQL names. Repository tables use selected UTC days; local Parquet tables do not. The statement sees views, not repository addresses.

## SQL dependencies and local files

DuckDB-Wasm's native `getTableNames()` discovers dependencies before any repository
index or Parquet read. It handles joins, aliases, nested queries, common table
expressions and quoted identifiers. Existing owned views are dropped first:
the native parser expands existing views instead of returning their names.
All references must name a consented registry ledger or an imported local
table before metadata is read. Unknown and disabled names fail explicitly.
Native `json_serialize_sql()` also checks table schema and database prefixes:
`getTableNames()` alone discards those prefixes. Only the default `main`
schema and no explicit database prefix are accepted. EXPLAIN's wrapper is
removed for this syntax inspection, not for execution.
Saved ledger lists are compatibility hints, not query inputs. Expressions
without tables still run.

The file picker reads actual Parquet with the same engine. `local-tables.ts`
retains page-local File handles and inspected columns, never saved bytes.
It checks file sizes and aggregate retained size against
`console.explorer_max_fetch_bytes`, and count against
`console.explorer_max_files`, before reading the file. It reads only the
format markers before allocating the whole buffer. DuckDB inspects the schema;
missing markers, corrupt data, unreadable files and exceeded limits are errors.
Aliases are minted as `local_<counter>`, separate from registry names, which
cannot contain underscores. The original filename is display text only.

Local bytes enter the engine only for inspection or when SQL names that alias.
Each registration gets an engine-minted path. Temporary local views and files
are dropped even after a failed statement. Unreferenced imports are not
registered, so another user of the shared engine cannot discover retained
local files through views. One queue serializes parsing, inspection, execution
and cleanup. Local files need no registry, consent, indexes, packing metadata,
`covers` or date field. Local-only questions work when the registry is absent
or invalid. No upload, URL import, model call or file-byte persistence exists.

The Run preflight counts referenced local bytes and files together with the
repository candidates. The column rail independently preflights its one
browsed ledger; typing SQL does not trigger column-file reads. Its quoted table
name can be copied without changing SQL or running a question.

## Source and session

The explorer reads `config/ledgers.json` and compact output under `state/compact/` from the committed `ledger.archive_base_url` in `config/idhazh.json`. A nonempty value is its sole source, including recent packed days. An explicitly empty value chooses the site or local fixture source. A repository failure never falls back to a site copy. Ordinary [panel reads](how-the-query-door-answers-a-panel.md) keep their staged source.

The registry parser produces one immutable catalog per session. [Explorer consent](../contracts/ledger-registry.md#explorer-consent-and-its-runtime-catalog) controls both the offered names and every request. A registered name without consent is refused before its indexes are read. Consent does not promise packed data. Build-time publication membership does not decide explorer membership.

Refresh fences old page results, ends the old reader session, drops its owned views and releases its files, imports and indexes. It then fetches a fresh registry and starts a new reader. Registry, indexes and Parquet use `cache: 'no-store'`; a changed file with unchanged row count and byte length is fetched again. Refresh may describe columns, but never runs the operator's SQL. Press Run explicitly.

Repository files are fetched as buffers. The engine receives only names it minted for those buffers, never repository URLs. The source address comes only from committed configuration, not fetched text or an environment destination.

## Compact selection and failure

Each selected ledger reads its daily, monthly and yearly index from its validated registry prefix. All three absent means no packed record is available. A partial set, invalid JSON, unsupported shape, wrong ledger or wrong period is a named failure. A missing named Parquet file or a byte-length mismatch is also a failure, never a quiet answer. The browser console names the index or file. Retry with Refresh, then Run.

`filesFor()` chooses the coarsest packed file covering each UTC day, once: year, month, then day. It does not probe directories, list an API or discover raw writer files. The newest data waits for packing.

A wider month or year file is filtered on `covers`, the UTC day a row was filed under. Reads join with `UNION ALL BY NAME`. This preserves date bounds even for ledgers without a `date` cell. A hole after the first named period is `day-missing`; an explicit empty or lost period is not a hole.

Days before a ledger's first compact period are cut from that ledger's answer, not refused. A month starts on its first UTC day and a year on 1 January. The selected dates do not move. `cut` names each affected ledger and its first available day.

`through` is the newest day any compact index names: a daily entry's day, a month's last UTC day or 31 December for a year. The answer's `readFrom` and `readTo` cover only ledgers that read at least one selected day. A ledger that stopped before the window supplies neither bound. These bounds belong to the answer, not later editor changes.

## Views and columns

`createLedgerReader()` binds the catalog and compact source. `question-reader.ts` discovers the SQL dependencies and `ask-reader.ts` prepares each repository view. Each engine tracks its owned views independently of the catalog. The question reader removes them before discovery and after execution, including failed execution. Calls, column descriptions and Refresh cleanup are serialized because the engine has one connection.

A selected ledger with no file in the span uses an empty view (`LIMIT 0`) over its newest indexed file when another ledger supplies rows. A zero-row packed file can supply columns; an explicit empty or lost entry supplies no file. A ledger with no file to supply that empty view is `missing`. When no referenced ledger has a file in the span and no local table is referenced, the answer is `quiet` without executing SQL after dependency discovery.

The column rail describes the one table being browsed, not the query's dependencies. For a repository ledger it describes its newest file, even outside the dates. Columns belong to the ledger; dates bound repository answer rows. A ledger with no file lists no columns. Fetch or engine failures are named in the browser console. Local columns come from the already inspected file.

## Limits and pricing

`console.explorer_max_files` is a positive integer, default 128 unique Parquet candidates per question. It becomes `ExplorerConfig.max_files` and `AskOptions.maxFiles`. Selection and pricing are shared by Run and the automatic column rail. Candidates include the query files and newest files needed for columns or empty views; duplicate paths count once. Preflight applies the file and byte limits before either path fetches Parquet.

Above the file limit the reader returns `too-many-files` with `files` and `max`. Above `console.explorer_max_fetch_bytes` it returns `over-ceiling`. The action line shows the refusal. Existing row, SQL-length and date limits remain. The default date reach is the current UTC day and the 364 days before it, controlled by `console.explorer_reach_days`.

`SpanCost` prices that candidate set and estimates the answer's UTC bounds. `FetchCost` counts files fetched for the call, their actual bytes, files already held, and elapsed milliseconds. A keeper holds registered repository files until Refresh or release. Local registrations last only for one inspection or question. Pricing is not proof that every selected day contains rows.

## Statement wraps

`statement.ts` rejects multiple statements, an unsupported first word and SQL beyond the character limit. It permits `SELECT`, `WITH`, `DESCRIBE`, `SUMMARIZE` and `EXPLAIN`. This is a courtesy refusal, not the trust boundary.

The engine describes the statement before running it. Most statements run inside:

```sql
SELECT COLUMNS(*)::VARCHAR FROM (
<operator statement>
) LIMIT <max rows + 1>
```

Separate lines protect the closing bracket from a trailing SQL comment. `EXPLAIN` runs without the wrap. Cells return as text with the engine's spelling, including dates, decimals, lists and structs. The answer reports when its row limit clipped rows.

The browser content policy applies to the engine worker. The boundary test uses the shipped directives and proves that a query cannot fetch an unlisted origin. Only `engine.ts` imports DuckDB-Wasm.

## Missing records and answers

`unreachable.ledger` names the ledger, or is null for engine startup failure. `at` names the selected day associated with the failed file or index. `fault` distinguishes an index, named file, day gap or engine failure; it is null for other failures such as a byte mismatch.

An answer with no matching rows is `quiet`, with described columns when SQL ran. `ok` and `quiet` carry `gaps`: lost UTC days and files set aside unread, per ledger. A lost day is not a zero-row day. A span of lost days is quiet but still reports the loss. Set-aside notes name the registered raw folder for a person to inspect; the browser does not fetch it.

The date chart breaks its line at lost days within the answer's bounds. It does not extend those bounds or add every unobserved day. For multiple ledgers it uses their combined lost-day evidence because an arbitrary SQL row does not identify its source ledger.

## Date range and address

Native `From (UTC)` and `To (UTC)` inputs use the configured reach. Presets end on the current UTC day. A link carries either `days`, or custom `from` and `end`, and never runs SQL.

Invalid, reversed or out-of-reach dates produce a notice and reset to a supported window. Saved questions and History use the same date checks; an invalid entry is dropped with a console message. [Explorer state](data-explorer-state.md) owns browser storage and sharing.

## Design rationale

**One direct compact source makes existing pages see new records.** Maintainer-directed decision: 2026-10-22 UTC. A site's compiled publication list and staged files cannot reveal a newly consented ledger or newly packed data without rebuilding. The existing committed repository origin and three indexes already identify the required files. Using them directly removes that build dependency without a new manifest, directory API, raw discovery or runtime server. This is the approved section 4 exception in `CLAUDE.md`; static publication, sanitization and operator-controlled destinations remain boundaries. The trade-off is packing delay and explicit repository failures, not silent stale answers. HTTP no-store avoids local cache reuse but does not promise immediate propagation through every origin cache.

**File limits cover automatic reads too.** The same preflight bounds Run and a browsed ledger's columns independently, including empty views. The newest column source may add a candidate outside the query dates. Counting it is conservative. Local files share the existing limits rather than adding another configuration or persisted shape.

**Use the engine's parser and temporary registrations.** The shipped engine
already discovers SQL references; a second parser would add download weight
and another SQL vocabulary to maintain. Keeping local File handles instead of
registered engine files prevents shared-engine views from exposing a retained
import. The cost is reading a referenced local file again on each Run. These
are completed capabilities, not two flag-selected implementations; no
development flag or new persisted contract is needed.

**Keep real fixtures and the existing browser journey.** The feed fixtures use Python contracts and the real Parquet writer; native DuckDB supplies an independent column reading. The existing journey changes only its generated repository after the site build, then proves that Refresh offers a new runtime name and an explicit Run returns its rows. Same-size replacement and removed-view cases stay in lower-tier tests. No new browser inventory is needed.

**Calendar bounds belong to the answer.** A selected window can begin before a ledger or end after it stopped. One combined calendar span avoids counting overlapping dates once per ledger. Carrying actual bounds with the answer prevents later date edits from changing what the prior run claims to have read.

## See also

- [How the query door answers a panel](how-the-query-door-answers-a-panel.md) - unchanged staged-panel delivery.
- [Contract schemas](../contracts/schemas.md) - persisted payload ownership and binding tests.
- [Query a ledger](../../how-to/query-a-ledger-from-the-console.md) - operator steps.
