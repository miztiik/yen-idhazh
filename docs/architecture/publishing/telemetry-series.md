# Telemetry Series

**Last Updated**: 2026-08-30

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
| What one summary cost | every timed article in the window, binned by doublings of the clock, with the median and the 95th taken over the values | `summarize_ms` |
| Checking a summary | median and 95th of the scorer's own clock, over the rows it timed | `score_ms` |
| How long the summaries came out | the lowest, middle and highest summary length of each run, against the band its own articles were asked for | `summary_word_count`, `source_word_count`, `summarize.bands` |
| Did the model change move anything | seven measures either side of the newest day the model id changed, each as a ratio against its own value before | `model_id` plus the six columns above |

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

**Re-measured 2026-08-30, and the fix is now proven on committed rows rather
than argued.** The ledger has grown to 3,113 rows and 430 of them are stamped
`2026-08-29T09:00`, on the new side of the boundary. Over those 430: 4 articles
were genuinely cut, all 4 are flagged, and the flag agrees with the word-count
pair on **430 of 430**. Over the 2,683 older rows nothing moved - still 0 of 22,
still the one 748-of-748 row - because those rows were never rewritten. The
whole-ledger count of flagged rows is now 5, and reading it as one number is
exactly the mistake the version branch exists to stop: 4 of the 5 are right and
1 is the old defect.

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
  else, and a zero would say the thing never happened. **The count has now
  returned on its own**, which is what this rule was written to allow: 430
  committed rows are stamped `2026-08-29T09:00`, so the days those rows cover
  print a number under `Article read only in part` and every earlier day still
  reads `-`. Nothing was edited to make that happen.

## Every span the control offers is measured at build time

The two distribution panels on the Model route - `What one summary cost` and the
scoring cost beside it - cannot answer for a different span by re-reading what
the page already holds. A percentile is taken over the values, and a percentile
read out of a drawn bar is a guess at where inside a doubling it fell.

So `frontend/src/routes/console/model/+page.server.ts` measures each panel once
per entry in `console.window_presets`, over the millisecond values themselves,
and the browser picks the answer for the open window. Four presets is four small
objects. The alternative was inlining every timing the ledger holds so the page
could re-bin them, which grows with the ledger and buys nothing exact.

The run-length panel is different and is filtered rather than re-measured: a run
is already three numbers, so narrowing the window drops columns and recomputes
nothing.

Every span is anchored on the same day list the cards are anchored on, so the
panels on that page name one window. `DayWindow` in
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts)
is that one answer, passed down rather than re-derived.

## The compression plot was retired, and what replaced it

Until 2026-08-30 the Pipelines route drew one mark per scored item, source words
against summary words. It had a measured hole it did not admit to: `extract`
discards the pre-cap body, so a truncated row written before the ledger recorded
a pre-cap length has no full length anywhere. Measured 2026-08-30 over all 3,113
committed rows, **142** carried a null and the plot drew the other **2,971**,
saying nothing about the difference. Every one of the 142 predates the
2026-08-27T21:00 writer fix, so the hole is a fixed set of old rows that a
longer ledger keeps diluting.

Two drawings replaced it and neither has that defect:

- **`Summaries a day, split by whether each landed inside its target band`** on
  the Pipelines route, which counts the rows it could not place and prints that
  count in a sentence under itself.
- **`How long the summaries came out`** on the Model route, three marks a run
  rather than one a summary. The owner ruled on 2026-08-30 that compression is
  drawn per run as lowest, middle and highest and never per item: thousands of
  marks in one colour render their dense middle as a solid area, and the marks
  that area hides are the only ones anybody acts on.

Both read the cut from the two length cells of one row rather than from
`truncation_flagged`, which is the per-item form of the version-stamp rule
above.

## What the machine did - read at build time, never published

The same arrangement as the model section above, over a third private ledger:
`state/runtime-counters.csv`, one row per work shard per run, holding what
llama-server itself counted. The reader is
[frontend/src/lib/server/runtime-counters.ts](../../../frontend/src/lib/server/runtime-counters.ts),
under `$lib/server/` for the same reason `model-work.ts` is. Nothing is served
and no column is published: `state/` is not part of the site, and the figures
below reach a page as numbers, never as rows.

Since 2026-08-31 `/console/machine/` draws them
([frontend.md](frontend.md#what-the-machine-route-draws)). Before that the
ledger had been committed for four days with no page reading a cell of it.

| Figure | Made from | Composed as |
| --- | --- | --- |
| Seconds reading, seconds writing | `prompt_seconds_total`, `tokens_predicted_seconds_total` | summed over shards, and never added together into one "model seconds" |
| Read and write speed | those seconds against `prompt_tokens_total` and `tokens_predicted_total` | sum over sum, never a mean of per-shard rates |
| Read spread | the fastest shard's read rate over the slowest | one run only; a run of one shard reports nothing |
| Prompt cache | `prompt_tokens_total` against `prompt_tokens_cached_total` | share of every token the prompt needed, read or reused |
| Context headroom | `n_tokens_max` against `models.inference.n_ctx` | the longest sequence any shard saw. A maximum, not a sum |
| Job clock | `job_seconds` against `run.shard_timeout_minutes` | the slowest shard. A run's wall clock is its slowest shard |
| The processor | `cpu_model` | text, per shard, and never averaged |
| Busy, memory, load | `cpu_busy_pct`, `peak_rss_bytes`, `model_load_ms` | lowest, highest, slowest |
| Do the two clocks agree | the item ledger's `prefill_ms` and `input_tokens - cached_tokens` against the server's own totals | the same pooling and the same 5 percent bound `backend/utilities/reconcile_prefill.py` gates on |

Both ceilings come from `config/idhazh.json` through
[frontend/src/lib/server/config.ts](../../../frontend/src/lib/server/config.ts)
(Rule #6). A counter without its ceiling is not a measurement: 4,925 says
nothing until 8,192 sits beside it.

**What counts as a read prompt token is defined once**, in `itemRead` in
[frontend/src/lib/charts/machine.ts](../../../frontend/src/lib/charts/machine.ts):
`input_tokens - cached_tokens`, because the runtime reused the cached ones
instead of reading them and leaving them in reports a rate the machine never ran
at. The reader imports it rather than restating it, which is why a server module
imports a chart module for that one function - the run figure and the per-shard
figure the page draws can then never disagree about what a token is.

### Every figure carries the shards it was made from

Three columns landed on 2026-08-29 and three more on 2026-08-30, so most
committed rows are blank in most of them. Each derived figure therefore leaves
the module as a `Reading` - a value, the shards that reported the cells it needs,
and the shards the run split into. A page can then tell **never measured** (`from`
is zero) from **measured on some** from **measured on all**, without guessing.

`value: 0` with `from` above zero is a measurement of zero and stays one. A blank
cell is `value: null` with `from` of zero. `RuntimeCountersRow.csv_row` states
the rule on the writer's side: "A server that never answered and a server that
read no tokens are different facts, and one of them is a broken scrape."

### A shard is a set, and a run that cannot be reconciled is refused

`state/runtime-counters.csv` is merged line by line with the union driver, while
the deduplication that writes it reads a tree frozen at checkout. So two workflow
runs that compute the same `run_id` both append, and the file ends up holding one
shard index twice. Summed as rows rather than as a set, run `2026-08-29-3`
reported **-394 seconds** against the item ledger, which is not a number any
machine produced.

The reader groups by shard index. Two rows for one shard whose every counter cell
matches are one scrape written twice, and collapse to one. Two rows that differ
anywhere are two llama-server processes, and the counters are cumulative per
process - so they can neither be added nor chosen between, and the whole run is
refused. A refused run is returned with its id and the reason, never dropped
silently: a page that prints half a run prints a figure that reads as the run.

Measured 2026-08-31 over the committed ledger: **54 rows, 12 runs, 11 read and 1
refused** - still `2026-08-29-3`, and now both its shard 1 and its shard 3 hold
two different scrapes. Summing its rows rather than its shards overstates the
run's reading clock by 7,495.5 seconds, 63 percent high. The refusal is printed
on `/console/machine/` with the run id and the reason, so the run count on that
page can be checked against the ledger.

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
