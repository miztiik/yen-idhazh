# Query a ledger from the Data explorer console

**Last Updated**: 2026-10-08

Use the Data explorer page when the console has the data you need but no purpose-built panel answers your question.

## What the page reads

Data explorer reads the ledgers that `config/ledgers.json` declares and `config/idhazh.json` publishes. It reads the site copy first. It asks the committed repository, through `ledger.archive_base_url`, only for older days the site copy trimmed. When the selected window begins before a ledger's first day, it moves the window's start to that day for that ledger and says so, naming the ledger: `Days of the {ledger} record before {day} are not on this site.` The window's end never moves. If `ledger.archive_base_url` is empty, Data explorer reads the site only.

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

The line under the answer says which UTC days it read, for example `Read from 11 UTC days, 5 Jun 2030 to 15 Jun 2030.` It counts the days read. That is fewer than the days you chose when every chosen ledger starts later than the window: it began inside the window, or the repository could not give its older days. It is fewer too when every chosen ledger stops before the window's last day: the line then ends on the newest day one of them reaches. It belongs to the answer: changing the dates or the ledgers changes it only after you press Run again.

Under the line that says which days were read, the answer names what each selected ledger is missing in those days. A day whose record was lost has no rows in the answer; it was not a quiet day. The date chart breaks its line at such a day rather than joining the days either side. A file the packing set aside unread may hold rows the answer lacks; the line says how many files and which folder holds them, `state/raw/<ledger>/set-aside/`, for a person to read.

The action line prices the next run before it fetches data. A wide span can be refused before any file is fetched when it would pass `console.explorer_max_fetch_bytes`.

## Share or keep a question

Copy link stores the chosen ledgers, the custom dates and the compressed question when the link fits `console.explorer_link_max_bytes`, the measured request-target limit. A longer link carries the ledgers and the days only, and `Copy question` appears beside Copy link. A preset span that ends today keeps `days`; a custom span uses `from` and `end`.

Save keeps the question in this browser. A question saved before custom dates existed opens ending on the reader's UTC day.

## See also

- [How the query door answers a written question](../architecture/publishing/how-the-query-door-answers-a-written-question.md)
- [What the data explorer borrowed](../concepts/console-design/what-the-data-explorer-borrowed.md)
