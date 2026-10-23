# Query a ledger from the Data explorer console

**Last Updated**: 2026-10-22

Use the Data explorer page when the console has the data you need but no purpose-built panel answers your question.

## What the page reads

Data explorer offers the ledgers with [explicit consent](../architecture/contracts/ledger-registry.md#explorer-consent-and-its-runtime-catalog). It reads the current registry and compact files from the committed repository address in `ledger.archive_base_url`. An explicitly empty address uses the site. It never switches to a site copy after a repository error.

The newest data waits for packing. Consent does not promise data exists. A ledger without packed records says so; missing or invalid named files produce an error, not a zero-row answer. Refresh reads the registry and files afresh without a site rebuild. It clears the old answer but runs no question: press Run afterward.

Days before a ledger's first compact period are cut from that ledger's answer and named below it. The selected dates do not move.

## Ask a question

1. Open `/console/data-explorer/`.
2. Choose one or more ledgers.
3. Choose `From (UTC)` and `To (UTC)`. The inputs accept the reader's UTC day and the 364 UTC days before it by default.
4. Write one read-only DuckDB statement. Use the selected ledger names as quoted table names, for example `"host-fingerprint"`.
5. Press Run, at the right end of the editor's heading line beside Save and Copy link, or press Ctrl+Enter in the editor.

The page never runs a question from a link by itself. A shared link fills the editor and waits for Run.

## What a result means

The answer table prints every cell as text. It never turns a cell into a link, image, fetch address or style. The `Chart` tab opens on the chart the answer's columns choose, and draws only shapes the answer can support. If no chart fits, the table is still the answer. `Copy as JSON` and `Copy as table`, at the right end of the answer's heading line, put the answer on the clipboard.

To draw the answer another way, press a tile under `Draw it as`, then press a pill above the drawing to pick the column for that role - for example which column runs along the bottom, or which numbers draw as lines. A pill lists only the columns that fit its role, and its `Find a column` filter finds a name by any part of it. A chart these columns cannot draw says what it needs in its box. Your choices hold while you run other questions on the page, and they are not saved with a question or carried in a link.

The line under the answer says which UTC days it read, for example `Read from 11 UTC days, 5 Jun 2030 to 15 Jun 2030.` It counts the days read, not the days selected. That can be fewer when every chosen ledger starts later or stops earlier than the window. It belongs to the answer: changing dates or ledgers changes it only after Run.

Under the line that says which days were read, the answer names what each selected ledger is missing in those days. A day whose record was lost has no rows in the answer; it was not a quiet day. The date chart breaks its line at such a day rather than joining the days either side. A file the packing set aside unread may hold rows the answer lacks; the line says how many files and which folder holds them, `state/raw/<ledger>/set-aside/`, for a person to read.

The action line prices the next run before it fetches data. Its UTC day count and dates estimate the same span the line under the answer reports: from the earliest day a selected ledger will read to the latest day one will read. It does not add each ledger's days together. For a 14-day window ending on 15 Jun 2030, a ledger that starts on 11 Jun reads 5 UTC days; beside a ledger that covers the whole window, the count is 14 UTC days. A ledger that stops before the window ends cannot add days after it stops. The line says `Run will read {files}, {size} from {ledgers} over 5 UTC days, from 11 Jun 2030 through 15 Jun 2030.`, or `over 1 UTC day: 15 Jun 2030.` for one day, and `over 0 UTC days.` when no selected ledger reads a day. A wide span can be refused before any file is fetched when it would pass `console.explorer_max_fetch_bytes`.

The file-count limit is `console.explorer_max_files`, default 128 unique
Parquet candidates per question. It includes files needed for empty views and
the automatic column list. Both the file and byte limits are checked before
those data fetches. Reduce the dates or selection when the action line refuses
the next question.

## Share or keep a question

Copy link stores the chosen ledgers, the custom dates and the compressed question when the link fits `console.explorer_link_max_bytes`, the measured request-target limit. A longer link carries the ledgers and the days only, and `Copy question` appears beside Copy link. A preset span that ends today keeps `days`; a custom span uses `from` and `end`.

Save keeps the question in this browser. A question saved before custom dates existed opens ending on the reader's UTC day.

Saved questions and History keep exact dates only for a custom span. A preset
span reopens ending on the current UTC day. A custom span marks no day tile;
press any tile to replace its dates with that span ending today. Older entries
that already carry dates keep them, even when their length matches a preset.

## See also

- [How the query door answers a written question](../architecture/publishing/how-the-query-door-answers-a-written-question.md)
- [What the data explorer borrowed](../concepts/console-design/what-the-data-explorer-borrowed.md)
