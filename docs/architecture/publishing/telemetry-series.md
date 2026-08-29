# Telemetry Series

**Last Updated**: 2026-08-29

The console's interactive charts read a published projection of item health. They
never read `state/item-health/` directly.

## Published shards

`backend/idhazh/publish_telemetry.py` reads
`state/item-health/<YYYY-MM>.csv` and writes
`frontend/public/telemetry/<YYYY-MM>.csv`. The browser fetches these monthly
shards on demand as the operator pans the viewport.

The published columns are exactly:

`date, run_id, item_id, vertical, source_id, stage, outcome, code, source_words, summary_words, source_words_before_cap`

These source-ledger columns never cross to the browser:

- `canonical_url`
- `url_key`
- `detail`

This is a trust-boundary rule, not a size trick. `detail` is diagnostic free
text, and the URL fields are not needed to draw failure rates or compression.

`source_words_before_cap` joined the projection on 2026-08-28. It is a word
count of our own extraction, the same class of cell as `source_words`, which
the browser has always had - so it crosses on the same terms. What it buys is
the one thing the browser could not work out for itself: a body was cut when
`source_words_before_cap > source_words`, and by that difference. The cell is
empty on every row written before that date, and empty is unknown rather than
uncut. The column list, and why the count travels instead of the text, is
[../sources/item-health.md](../sources/item-health.md).

### A new column is appended at the end, and the reader checks a prefix

**The browser's header check is a prefix match, not an equality.**
`parseTelemetryCsv` in `frontend/src/lib/charts/series.ts` holds
`TELEMETRY_COLUMNS`, and compares it position by position against the header it
read - so it asserts that the first `n` published columns are the `n` names it
knows, and says nothing about anything after them.

Both lists carry the same 11 names since 2026-08-29, so the check covers the
whole header today. It is written for the day it does not, and that day is
normal rather than exceptional: **append at the end is a rule rather than
tidiness**.

- **Appending** a column keeps every earlier position where the reader expects
  it, so an old browser build reads a new shard and ignores the new cell.
- **Inserting or reordering** shifts a position the prefix covers, and the check
  throws `telemetry projection header did not match the contract` - loudly,
  which is correct.
- **Removing** one does the same, one position earlier.

**Nothing in the frontend can see the writer, so a contract test holds the two
lists together.**
`backend/tests/test_contracts.py::test_the_console_reads_a_prefix_of_the_published_telemetry_columns`
pulls `TELEMETRY_COLUMNS` out of `series.ts` with a regex and asserts it is a
prefix of `PUBLIC_COLUMNS`. It passes an append on the writer's side, fails an
insert, a rename or a reorder at any position the browser reads, and fails a
frontend name the writer never writes. It fails first when the regex stops
matching, because a guard that quietly finds nothing is worse than no guard.
The two lists had already drifted once with nothing to notice: from 2026-08-28
to 2026-08-29 the shard carried `source_words_before_cap` and the reader did
not. **Do not tighten the check to an equality.** Equality is what the test
deliberately does not assert - it would break every cached bundle on the next
append, which is the one case the prefix exists for.

**The sharp edge is the round trip, not the parse.** `telemetryCsv()`
re-serializes from `TELEMETRY_COLUMNS` as well, so a column the parser ignored
is dropped rather than carried through. Any code that reads a shard and writes
one back narrows it to the names the reader knows. The test permits a
writer-only append, so it cannot catch that; whoever adds column twelve adds it
to `TELEMETRY_COLUMNS` and to `TelemetryRow` in the same commit, or the client
keeps reading a projection it cannot see the end of.

## What the model did - read at build time, never published

The console's `What the model did` section is not drawn from the published
shards. It is computed while the site is built, out of two private ledgers:

- `state/scores.csv` - one row per scored item.
- `state/item-health/<YYYY-MM>.csv` - one row per planned item per run.

Neither file is served and neither crosses to a browser. What reaches the page
is a count of that day's items, never a row and never a score. The derivation is
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts),
which sits under `$lib/server/` so SvelteKit refuses to bundle it for a browser.
The wording of the labels is settled in
[../../concepts/design-system.md](../../concepts/design-system.md); this table
says only where each figure comes from.

| On screen | Counts | Read from |
| --- | --- | --- |
| Summaries today | rows the score ledger holds for the day | `scores.csv` |
| Marked "not sure" | rows in the lowest confidence band | `band` |
| Numbers not in the article | rows asserting a figure the article never gave | `unsupported_numbers` |
| "Maybe" told as fact | rows that turned the article's hedge into an assertion | `hedge_dropped` |
| Article read only in part | rows flagged as cut short, over the day's rows that carry the flag's current meaning | `truncation_flagged`, read through `version` |
| Copied, not rewritten | median of the larger of the two copying measures | `extractiveness`, `verbatim_run` |
| Time to write one | median milliseconds the model spent on one article | `summarize_ms` |
| Model minutes | every millisecond the model spent that day | `summarize_ms` |
| Failed | rows whose run ended in a failure | `outcome` |

`hhem` still decides the band and it never prints. A faithfulness score is a
value between zero and one, and no lever moves it - so it earns no column, and
its consequence, the band, gets one instead.

Two copying measures are read and one figure is printed: the larger of the two
per item, then the median over the day. They miss opposite things. A summary can
score low on scattered four-word overlap and still lift a whole paragraph, so
taking the larger cannot under-report copying, which is the only direction that
matters.

### The cut flag is read through its version stamp

`truncation_flagged` changed meaning. A row stamped before `2026-08-28` holds
the gap between two faithfulness scores. A row stamped `2026-08-28` or later
says extract cut the article body. Those are two facts about two different
things, so one count over both would be one number answering two questions.

The console reads the flag through the row's own `version` cell, the date-stamp
`CLAUDE.md` section 11 puts on every persisted shape. A day's `Article read only
in part` figure counts only that day's rows stamped at or after the boundary,
and is unknown where the day holds none of them. The boundary is
`CUT_FLAG_MEANS_A_CUT_FROM` in
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts).

It is a constant beside the reader, not a knob in `config/`. It is not tunable:
it records the day a shipped column changed meaning, and a run that moved it
would make the page misreport rows already committed.

The comparison is a plain string compare, and the stamp format is what makes
that enough. `YYYY-MM-DD` and `YYYY-MM-DDTHH:MM` sort in the same order as the
instants they name, so `2026-08-27T20:30` comes before `2026-08-28` and
`2026-08-28T09:00` comes after it. A row carrying no stamp reads as older, which
is the safe direction.

Reading the column any other way is a Rule #10 breach on a published page, and
the ledger says how big. Measured 2026-08-28 over all 2,683 committed rows of
`state/scores.csv`: 22 rows are genuinely cut - their post-cap word count is
below their pre-cap one - and `truncation_flagged` is true on **0 of those 22**.
It is true on exactly one row in the whole ledger, and that row read 748 words
of a 748-word article, so it was never cut at all. Those rows were written by a
writer that set the column from a faithfulness delta against a configured
ceiling of `0.1`, and the delta over the 22 cut rows runs from `-0.1235` to
`+0.0381` - it could not reach the threshold. The page was printing "The article
was too long, so the machine read the start and stopped" from a cell that never
said that. The writer was fixed on 2026-08-29 and the ceiling deleted with it;
the column now carries `Article.truncated`.

Restamping the older rows to today would delete the branch instead of writing
it, and is refused: the stamp is the only marker of which rows predate the
change, and [../contracts/schemas.md](../contracts/schemas.md) keeps a migrated
row's `version` cell for exactly this - so a later read-side migration has
something to branch on. This is that migration.

## Degrade rules for the model section

A day earns a row by having summaries - score rows, or a runtime that timed the
summarize stage. Everything else prints as absence rather than as zero:

- **No summaries that day**: no row at all, and a gap in the throughput candle.
  A row of zeroes reads as a day that went badly rather than one with nothing
  in it.
- **The scorer did not run**: the quality cells print `-` while the speed cells
  still print. The runtime measured the time; nothing measured the quality.
- **No health row for a scored day**: the speed cells and the failure count
  print `-`. Nothing wrote a millisecond down, so no millisecond is claimed.
- **A measurement that rounds away**: `<1`, never `0`. Zero would say the model
  ran for nothing.
- **The model changed**: one divider row carrying the date and the new id, and
  the candle drops its percent-shift sentence across that boundary. Two models
  over two article sets is two measurements, not a trend.
- **A column changed meaning**: the cell it feeds prints `-` on every day whose
  rows all predate the change. Unknown, not zero. Those rows measured something
  else, and a zero would say the thing never happened. Every committed row is
  currently stamped before `2026-08-28`, so every day reads `-` under `Article
  read only in part`. The count returns on its own once a run stamps a row on
  the new side of the boundary; nothing has to be edited for that to happen.
  `EvalRow` is stamped `2026-08-29T09:00` from the commit that made the column
  mean a cut, so the next run writes rows on the new side.

## The compression plot leaves items out and does not say so

The plot on the same page draws one mark per scored item, source words against
summary words, and it reads `state/scores.csv` at build time exactly as the
table above does.
[frontend/src/routes/console/+page.server.ts](../../../frontend/src/routes/console/+page.server.ts)
drops any row whose `source_word_count` is not a positive number.

The drop is correct. `extract` discards the pre-cap body, so a truncated row
written before the ledger recorded a pre-cap length has no full length anywhere,
and the ledger now says null rather than guessing one. Measured 2026-08-28 over
the 2,683 committed rows: 142 carry a null, which is 5.3 percent of the ledger,
and the plot draws the other 2,541.

What is wrong is the silence. The plot shrinks by 142 marks and says nothing, so
a reader counting marks gets a smaller corpus than the page's own "items on
record" line, with no way to tell why. It needs one caption naming how many
items it could not place and the reason. That sentence belongs in the component
rather than in this doc, so it is recorded here as owed, not written here.

The same component still marks a point as cut straight from `truncation_flagged`
with no version stamp read, which is the per-item form of the error the table
above no longer makes.

## Degrade rules

A missing or unparsable month draws a gap. The page stays alive and logs a
browser-console warning. It does not invent zeroes, because zero failed items and
no data are different facts.

The default page is also prerendered as SVG from the same projection. If
JavaScript never runs, the console still shows the current window and honest
empty states.

## See also

- [frontend.md](frontend.md) - the console view that consumes these shards.
- [../contracts/schemas.md](../contracts/schemas.md) - why a migrated row keeps the `version` cell it was written with.
- [../sources/item-health.md](../sources/item-health.md) - the private item-grain ledger.
- [../../concepts/design-system.md](../../concepts/design-system.md) - how a console figure is worded and printed.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - ledgers as records, logs as evidence.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1 and Rule #11.
