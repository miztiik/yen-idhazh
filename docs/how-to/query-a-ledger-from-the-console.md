# Query a ledger from the Data explorer console

**Last Updated**: 2026-10-05

Use the Data explorer page when the console has the data you need but no purpose-built panel answers your question.

## What the page reads

Data explorer reads the ledgers that `config/ledgers.json` declares and `config/idhazh.json` publishes. It reads the site copy first. It asks the committed repository, through `ledger.archive_base_url`, only for older days the site copy trimmed. When the selected window begins before a ledger's first day, it moves the window's start to that day for that ledger and says so: `Days before {day} are not on this site.` The window's end never moves. If `ledger.archive_base_url` is empty, Data explorer reads the site only.

## Ask a question

1. Open `/console/data-explorer/`.
2. Choose one or more ledgers.
3. Choose `From (UTC)` and `To (UTC)`. The inputs accept the reader's UTC day and the 364 UTC days before it by default.
4. Write one read-only DuckDB statement. Use the selected ledger names as quoted table names, for example `"host-fingerprint"`.
5. Press Run.

The page never runs a question from a link by itself. A shared link fills the editor and waits for Run.

## What a result means

The answer table prints every cell as text. It never turns a cell into a link, image, fetch address or style. The chart panel draws only shapes the answer can support. If no chart fits, the table is still the answer.

Under the line that says which days were read, the answer names what each selected ledger is missing in those days. A day whose record was lost has no rows in the answer; it was not a quiet day. The date chart breaks its line at such a day rather than joining the days either side. A file the packing set aside unread may hold rows the answer lacks; the line says how many files and which folder holds them, `state/raw/<ledger>/set-aside/`, for a person to read.

The action line prices the next run before it fetches data. A wide span can be refused before any file is fetched when it would pass `console.explorer_max_fetch_bytes`.

## Share or keep a question

Copy link stores the chosen ledgers, the custom dates and the compressed question when it fits the measured request-target limit. A preset span that ends today keeps `days`; a custom span uses `from` and `end`.

Save keeps the question in this browser. A question saved before custom dates existed opens ending on the reader's UTC day.

## See also

- [How the query door answers a written question](../architecture/publishing/how-the-query-door-answers-a-written-question.md)
- [What the data explorer borrowed](../concepts/console-design/what-the-data-explorer-borrowed.md)
