# What the data explorer borrowed

**Last Updated**: 2026-10-08

The Data explorer page borrowed only the parts of the reference workbench that fit this console's data, trust boundary and visual system.

## What it kept

| Feature | Result | Reason |
| --- | --- | --- |
| Slim top bar | Kept as the compact one-row tab strip | The page's work starts on the first screen instead of under full console chrome. |
| Toolbar with Run at the right | Kept | The span and the button that reads it stand in one line. |
| Time range control | Kept as the existing tiles plus `From (UTC)` and `To (UTC)` | Shortcuts stay, and exact dates show as values. |
| One row of question chips | Kept, with overflow folded | Starting from a known question is the fastest first run. |
| Datastores with a filter | Kept as the ledger rail | The operator picks what to ask of and sees how recent each ledger is. |
| Tabbed editor with line numbers | Kept as one fixed SQL editor | Engine errors name a line; one question at a time needs no tabs. |
| One-line status bar under the editor | Kept as the fixed run status | Price, progress and readout land in one place that never changes size. |
| Schema panel with column types | Kept as the column rail | The operator writes against the names and types in view. |
| Dense results table | Kept with row numbers and a sticky typed header | Reading rows is the job, and the box scrolls instead of moving the page. |
| View switch | Kept as `Draw it as`, with a pill for each role's column | Every chart is offered on every answer and the reader picks the columns; a chart the answer's columns cannot support draws nothing and says what it needs. |
| Chart under the table | Kept at measured width | A full-width drawing keeps dates and labels readable. |
| Docs and history controls | Kept | Help and recent questions stand with the question row. |
| Expand next rows | Kept as `Show 50 more rows` | More rows arrive inside the answer box, so nothing below moves. |

## What it refused

| Feature | Result | Reason |
| --- | --- | --- |
| Red guardrail banner | Refused | A question that cannot run is a normal outcome, so it is a neutral sentence where the answer would be. |
| Highlighting anomalies | Refused | A verdict needs a rule, and this page has no rule about a question the operator wrote. |
| Material Symbols font | Refused | The repository already has a committed Lucide-derived icon system. |
| CSV download | Refused | Copy as JSON and Copy as table cover the useful handoff without opening spreadsheet formula risk. |
| Free chart choice | Refused | A line through rows that are not days draws a trend the answer does not contain. |
| Guessed engine facts | Refused | A number on this page is a reading or it is not printed. |
| Left icon rail and breadcrumb | Refused | The route strip already does that job. |
| Several editor tabs | Refused | They would suggest files that do not exist. |
| Load-all control and folded-chunk banner | Refused | The answer stops at the configured row limit and says so in the lede and note. |

## Rules for the next borrowed feature

1. A number on this page is a reading or it is not printed.
2. The console owns a job once.
3. A verdict needs a rule.

## See also

- [Design system](../design-system.md)
- [Query a ledger from the Data explorer console](../../how-to/query-a-ledger-from-the-console.md)
