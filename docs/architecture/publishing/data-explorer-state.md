# What the Data explorer keeps and shares

**Last Updated**: 2026-10-23

Which data the Data explorer reads, keeps in this browser and carries in a shared address.

## Source data and Refresh

The route reads the ledger registry from `config/ledgers.json` at the committed
`ledger.archive_base_url`; an explicitly empty value uses site fixtures. Its panel ids are
`data-explorer-ask`, `data-explorer-rows` and `data-explorer-shape`.
[The workbench layout](../../concepts/console-design/how-the-data-explorer-shares-the-window.md)
owns their visible arrangement.

The route renders only in the browser. It uses the common `404.html` fallback,
with `prerender = false` and `ssr = false`; it has no separate generated HTML
file. Build-time configuration supplies knobs and the destination, not current
membership or ledger rows. The browser fetches and validates the registry, indexes and
chosen files. The registry's [explicit consent](../contracts/ledger-registry.md#explorer-consent-and-its-runtime-catalog)
controls which ledgers the explorer offers and selects; it does not establish
whether data is available.

The page queries only the selected ledgers and UTC days. Each ledger's
packed-through day comes from its compact indexes, not the current date; newer
raw rows wait for compaction. The written-question reader owns the configured
date reach, file and byte limits, and explicit repository errors. Refresh
releases the page's immutable catalog, cached indexes, registered files and owned views through
`startAfresh()`, then fetches the registry again. Old results cannot update the
new session. All explorer HTTP reads use no-store, including same-size changed
Parquet after Refresh. It does not run the question. The
[written-question reader](how-the-query-door-answers-a-written-question.md)
owns compact selection, limits and explicit source failures. No repository error
switches to a staged site copy. Newest data waits for packing.

Refresh removes selections whose consent has been disabled or whose entry has
gone, and names them in a notice. It does not silently substitute an example
when the whole selection is removed. A registry that fails validation reports
its error and prevents Run rather than retaining an actionable stale catalog.

## Browser questions

Saved questions and recent runs stay in this browser. They are not committed
queries or shared server state. The configured saved-question and history caps
bound each list. If storage fails, the page says so and does not present Save or
History as working.

Examples come from `console.explorer_examples`. An example is offered only when
every ledger it names has consent in the validated registry. Choosing an example or saved question replaces the
SQL, ledger selection and span without running it. You can clear the loaded SQL
in the editor, but that does not restore the previous question or its settings.

The [date and reopening rules](../../how-to/query-a-ledger-from-the-console.md#share-or-keep-a-question)
apply equally to saved questions and History. Chart and column choices stay in
runtime memory; they are not part of a saved question or link.

## Shared addresses

An address is editor state, never an instruction to execute a query. The
`ledgers` parameter names a checked selection, `days` names a preset, and `from`
with `end` names custom UTC dates. `q` holds compressed SQL. These are query
parameters, not a fragment.

Unknown ledger names, unsupported presets, invalid dates and unreadable
compressed questions produce notices. Opening the address fills the editor and
waits for Run. A question too long for the measured link limit can still be
saved or run: its link carries only ledgers and dates, and the page provides
Copy question separately.

## Answer copies

Cells render as text, never as links, images or HTML. Copy as JSON preserves the
text cells; Copy as table puts each cell in a Markdown code span. There is no
spreadsheet download that could execute a cell as a formula. The answer table's
types, formatting and sorting belong to
[the console design](../../concepts/console-design.md#data-explorer-prints-the-engine-answer-as-written).

## Design rationale

**Search-engine behavior is not a delivery requirement.** The page exists to
answer an operator's questions over recorded data, not to serve a crawler.
Its raw fallback response need not carry a `noindex` tag. Do not generate a
separate route document or change the common fallback to satisfy that check.
Dated reader addresses use the same fallback, so changing it would affect
pages outside the console. Existing search hints do not guarantee exclusion
from search results and are not access controls. Owner ruling:
kumarsnaveen, 2026-10-09.

## See also

- [Query a ledger](../../how-to/query-a-ledger-from-the-console.md) - operator steps.
- [Address-length measurement](../../reference/benchmarks/address-length-on-pages.md) - the current host limit.
- [Console payloads](console-payloads.md) - published pipeline output.
