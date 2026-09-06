# Telemetry Series

**Last Updated**: 2026-09-05

The console's interactive charts read a published projection of item health. They
never read `state/item-health/` directly.

## Published shards

`backend/idhazh/publish_telemetry.py` reads
`state/item-health/<YYYY-MM>.csv` and writes
`frontend/public/telemetry/<YYYY-MM>.csv`. The browser fetches these monthly
shards on demand as the operator pans the viewport.

The published columns are exactly:

`date, run_id, item_id, vertical, source_id, stage, outcome, code, source_words, summary_words, source_words_before_cap, fetch_ms, extract_ms, summarize_ms, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens`

These source-ledger columns never cross to the browser:

- `canonical_url`
- `url_key`
- `detail`

This is a trust-boundary rule, not a size trick. `detail` is diagnostic free
text, and the URL fields are not needed to draw failure rates or compression.

**The shape is a contract, since 2026-09-02.** `PublicTelemetryRow` in
`backend/idhazh/contracts/public_telemetry.py` owns which cells may cross and
what each one may hold; the module above owns only when a shard is written and
from what. Before that the whole boundary was a tuple of eleven strings and a set
of three more, both readable code and neither a contract - so the one payload a
reader's browser downloads had no schema, no version stamp and no changelog while
every other persisted surface had all three (Rule #3). `FORBIDDEN_COLUMNS` is
checked at **import**, so a forbidden field on the model stops the process rather
than reaching the published tree.

Two consequences worth stating plainly:

- **`version` is a field of the shape and never a cell.** The header check below
  is a prefix, so one more name at position zero would shift every position the
  console reads. `schemas/public-telemetry.schema.json` is where the stamp lives.
- **A published shard has to load, not merely parse.** `publish_telemetry
  --migrate` reads every committed shard back through the contract and rewrites
  it, and a test runs the same round trip on a copy of the committed files. Run
  2026-09-05 on this checkout, after the eight timing and token columns landed:
  `2026-08.csv` 5,227 rows and `2026-09.csv` 2,982 rows, 614,613 and 400,160
  bytes, unchanged to the byte either side. Unchanged is the result the migration
  wanted - it says the committed bytes already are the contract's own output.

`source_words_before_cap` joined the projection on 2026-08-28. It is a word
count of our own extraction, the same class of cell as `source_words`, which
the browser has always had - so it crosses on the same terms. What it buys is
the one thing the browser could not work out for itself: a body was cut when
`source_words_before_cap > source_words`, and by that difference. The cell is
empty on every row written before that date, and empty is unknown rather than
uncut. The column list, and why the count travels instead of the text, is
[../sources/item-health.md](../sources/item-health.md).

### The eight stage timings and token counts, since 2026-09-05

`fetch_ms`, `extract_ms`, `summarize_ms`, `prefill_ms`, `decode_ms`,
`input_tokens`, `output_tokens` and `cached_tokens` joined the projection on
2026-09-05. Every run since 2026-08-23 has measured them and written them to
`state/item-health/`, and the projection dropped all eight on the way out - so
the console could show that a stage failed and never how long the stage took.

They cross on the same terms the two word counts do: they are durations and
counts of **our own work**, never the fetched page. Nothing about them names a
URL, quotes a body, or identifies anything beyond the item id already carried.

**Empty stays empty.** An instrument that did not run writes no cell, never a
zero. A skipped stage and a stage that took no measurable time are different
facts, and collapsing them turns every fetch failure into a fetch that was
infinitely fast. `cached_tokens` is where this bites hardest, because zero is a
real answer there - a server that cached nothing measured zero, and a server
that reported no cache figure at all measured nothing.

**What they cost over the wire, measured 2026-09-05 on this checkout:** the two
committed shards went from 461,564 and 292,116 bytes to 614,613 and 400,160,
and gzipped from 74,791 and 51,312 to 143,098 and 100,918. That is 117,913 more
gzipped bytes across both months, roughly double. It is not a first-load cost:
the console fetches a month shard on demand as the viewport reaches it, and the
prerendered seed carries only the rows the default window needs. The 1 GB Pages
cap (Rule #2) is three orders of magnitude away.

**The prerendered seed does not carry them, and that is a measurement rather
than a preference.** `publicTelemetry` in
`frontend/src/routes/console/+page.server.ts` inlines the default window's rows
into the console document so the page is complete before any script runs. Seeded
with their real values, the eight cost 176,753 more gzipped bytes on `/console/`
- 198,624 to 375,377, an 89 percent page, and 98,182 over the recorded ceiling.
Seeded as nulls the page is 214,985, which is 16,361 more and 62,210 under.
Measured 2026-09-05 on Intel Core i7-1265U / Windows 11 / node 24, one build per
arm; the eight untouched routes moved -2 to +5 bytes between them, so the figure
is the columns and not the build.

So the seed carries nulls. A ceiling is re-recorded by the change that grows it,
and bytes the first paint does not use are not bytes to record a ceiling around.

**A panel draws them since 2026-09-05, and it took neither of the two options
this paragraph used to offer.** The choice was stated as: seed the columns that
panel draws, or drop the seeded months from `loadedMonths` and let the month
fetch fill them, because `+page.svelte` marks the seeded months loaded and
nothing re-fetches them. `What one item cost the model` takes a third path. It
reads this projection on the **server**, at build time, and reduces it to two
doubling-binned distributions and about twenty counts **per entry in
`console.window_presets`**; the browser picks the open one. The seeded rows are
untouched and still carry the eight as nulls, so the page grows by the reduction
rather than by the rows.

What that costs is one thing and it is stated on the page: the section follows
the window's **length** and not a pan, exactly as `Sources cut short most often`
does. A pan asks about days the reduction was not taken over, and re-taking it in
the browser needs the rows the seed deliberately does not carry. The two offered
options were refused for measured reasons - seeding buys back the 176,753 bytes
above, and dropping the seeded months puts a 244 KB fetch behind the first click
of the window control and leaves the section blank until it lands
([frontend.md](frontend.md#it-follows-the-windows-length-not-a-pan)).

The two options remain open for a panel that genuinely needs a panned answer.
Nothing on the page needs one today.

### A new column is appended at the end, and the reader checks a prefix

**The browser's header check is a prefix match, not an equality.**
`parseTelemetryCsv` in `frontend/src/lib/charts/series.ts` holds
`TELEMETRY_COLUMNS`, and compares it position by position against the header it
read - so it asserts that the first `n` published columns are the `n` names it
knows, and says nothing about anything after them.

Both lists carry the same 19 names since 2026-09-05, so the check covers the
whole header today. It is written for the day it does not, and that day is
normal rather than exceptional: **append at the end is a rule rather than
tidiness**.

- **Appending** a column keeps every earlier position where the reader expects
  it, so an old browser build reads a new shard and ignores the new cell.
- **Inserting or reordering** shifts a position the prefix covers, and the check
  throws `telemetry projection header did not match the contract` - loudly,
  which is correct.
- **Removing** one does the same, one position earlier.

**The prefix protects one direction, and widening the reader is the other one.**
An old bundle reading a new shard is safe, which is what the check is for. A new
bundle reading an **old** shard is not: it knows more names than the file has, so
the check throws. That is a stale cached shard against a fresh bundle, and it
degrades rather than breaking - `loadVisibleMonths` in
`frontend/src/routes/console/+page.svelte` wraps the fetch and the parse in one
`try`, logs `telemetry <month> could not be read; showing a gap`, and the charts
draw the gap they already know how to draw.

**On today's data that direction cannot be reached at all**, and the reason is
worth knowing before someone tries to test it. The prerendered seed covers
`console.default_window_days`, which at 30 days reaches back across both
published months, so `monthsToFetch` returns nothing at every preset and the
console makes no runtime shard request. Measured 2026-09-05 by serving an
11-column shard from a route interceptor at the 7, 14, 30 and 90-day presets: the
interceptor fired **zero** times, which proves the path is unreachable and proves
nothing about the degrade. It becomes reachable when a third month is published
and the operator widens past the seeded span.

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

**How long a shard is kept is a knob of its own, and it is now spent.**
`observability.public_telemetry_keep_months` is 14, and the contract refuses any
value that is not equal to `observability.item_health_full_grain_months`: this
file is the browser's copy of that ledger, so a published month whose source has
been folded away is a rate nobody can check, and a source month with no published
copy is a window the console cannot draw. Since 2026-09-03 the two files go
together: `retention.prune_telemetry` folds the ledger month, unlinks the shard,
and unlinks this copy of it in the same step
([../../concepts/config.md](../../concepts/config.md#every-store-names-its-own-cleanup-age)).

Three things about that deletion are worth stating on this page rather than only
on the pruner's:

- **It ships in dry run.** The step logs the files a live run would remove and
  removes none of them, because `.github/workflows/prune.yml` force-pushes `main`
  on a schedule and a deleted file stops being recoverable once that prune passes
  over it (`CLAUDE.md` section 8). Measured 2026-09-02 on this checkout, a live
  run would take nothing today; the first shard it takes is `2026-08.csv` on
  **2027-10-01**.
- **A copy is never deleted before its source.** The aggregate is written and
  read back, then the ledger shard is unlinked, then this copy. A run that dies
  between the last two leaves a published month with nothing behind it, and the
  next run takes it - that pass walks this directory rather than the shards being
  folded, which is the only way it can see a copy whose source is already gone.
- **The reader never asks for one that went.** `telemetryMonths()` lists this
  directory at build time and `monthsToFetch` filters on that list, so a deleted
  month is absent from `data.telemetryMonths` and no widening ever names it.
  `frontend/tests/console-window.spec.ts` holds that over every anchor a year
  offers, at `console.max_window_days`.

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

- `state/scores/<YYYY-MM>.csv` - one row per scored item.
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
| What checking one summary cost | the same binning over the checker's own clock, with its own median and 95th | `score_ms` |
| Which sources the checker doubts | summaries carrying a low band, a figure the article did not give, or a flattened hedge, grouped by the source the article came from | `band`, `unsupported_numbers`, `hedge_dropped`, joined to `source_id` on `url_key` |
| How long the summaries came out | the lowest, middle and highest summary length of each run, against the band its own articles were asked for | `summary_word_count`, `source_word_count`, `summarize.bands` |
| What the model change moved | ten measures either side of the newest day the model id changed, each as a ratio against its own value before | `model_id` plus the columns above, and the two token rates |

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

The two distribution panels on the Model route - `What one summary cost` and
`What checking one summary cost` - cannot answer for a different span by
re-reading what the page already holds. A percentile is taken over the values,
and a percentile read out of a drawn bar is a guess at where inside a doubling it
fell.

So `frontend/src/routes/console/model/+page.server.ts` measures each panel once
per entry in `console.window_presets`, over the millisecond values themselves,
and the browser picks the answer for the open window. Four presets is four small
objects. The alternative was inlining every timing the ledger holds so the page
could re-bin them, which grows with the ledger and buys nothing exact.

The ranked list of doubted sources is measured the same way and for a different
reason: the ranking is a fold over every scored row in the span, and inlining the
rows so the browser could fold them again would put the whole ledger on the page.
It is capped on the server at `console.doubt_rows`, so what is inlined is ten
rows a preset and a pair of tail counts.

The run-length panel is different and is filtered rather than re-measured: a run
is already three numbers, so narrowing the window drops columns and recomputes
nothing.

Every span is anchored on the same day list the cards are anchored on, so the
panels on that page name one window. `DayWindow` in
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts)
is that one answer, passed down rather than re-derived.

### One binning, two clocks

The writing clock and the checking clock are drawn by one component and binned
by one function. They ask the same question - how long did one take, and how bad
does it get - so a second implementation of a log binning and a second pair of
rules could only drift from the first.

`distribution()` in `model-work.ts` owns the bars: the first bar holds everything
under a second, every edge after it doubles, leading and trailing empty bars are
dropped as axis while a gap between two occupied bars stays as data, and the
median and the 95th are taken over the values rather than off a bar.
`TimeHistogram.svelte` draws it, and what differs between the two panels is four
strings and a name.

Neither draws a model-change rule, and both say why in `data-model-rule-none`. A
change to the model, the prompt or the cap moves every bar on the writing chart;
but the horizontal axis is seconds, so a day has no position on it and a rule
would have to be drawn where no date exists.

Measured 2026-09-01 over a thirty-day window on the committed ledger: the writing
clock holds 4,064 timings with a median of 121.2 s and a 95th of 301.9 s, and the
checking clock holds 4,100 with a median of 2.2 s and a 95th of 14.1 s. The
checker's slowest is 51.6 s. Both distributions run over several doublings, which
is what the shape exists to show and what two numbers cannot.

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
| Busy and load | `cpu_busy_pct`, `model_load_ms` | lowest, slowest |
| Peak memory | `peak_rss_bytes` against the runner's 16 GB | the LARGEST shard, never their sum - shards are separate jobs on separate hosts |
| The shape of a run | the item ledger's `summarize_ms` | one ladder a run at the five configured percentiles, interpolated between the two nearest ranks, never pooled between runs |
| The two clocks, compared | the item ledger's `prefill_ms` and `input_tokens - cached_tokens` against the server's own totals | the same pooling and the same 5 percent bound `backend/utilities/reconcile_prefill.py` gates on |

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
runs that computed the same `run_id` both appended, and the file ended up holding
one shard index twice. Summed as rows rather than as a set, run `2026-08-29-3`
reported **-394 seconds** against the item ledger, which is not a number any
machine produced.

Both halves of that are now closed on the writer's side, and this reader is kept
anyway. A run id carries the identity of the execution that made it, so two
workflow runs can no longer compute one; and `ledger.drop_repeated_rows` settles
the file after the merge, where the frozen dedup cannot see. See
[../sources/item-health.md](../sources/item-health.md#the-shape-of-a-row). What
remains is that a reader of a committed file cannot assume the run that wrote it
was made by today's pipeline, so refusing an inconsistent run stays correct and
costs nothing.

The reader groups by shard index. Two rows for one shard whose every counter cell
matches are one scrape written twice, and collapse to one. Two rows that differ
anywhere are two llama-server processes, and the counters are cumulative per
process - so they can neither be added nor chosen between, and the whole run is
refused. A refused run is returned with its id and the reason, never dropped
silently: a page that prints half a run prints a figure that reads as the run.

Measured 2026-08-31 over the committed ledger before the repair: **54 rows, 12
runs, 11 read and 1 refused** - `2026-08-29-3`, whose shard 1 and shard 3 each
held two different scrapes (21:06 against 23:15, and 21:10 against 23:39).
Summing its rows rather than its shards overstated the run's reading clock by
7,495.5 seconds - 19,305.8 against 11,810.3, **63 percent high**. The file was
settled in the same commit that fixed the writer: 54 rows to 52, 7,871 bytes to
7,577. All 12 runs now read. The refusal is still printed on `/console/machine/`
with the run id and the reason, so the run count on that page can be checked
against the ledger.

### The latency ladder is one derivation, drawn twice

`percentileHistory` in
[frontend/src/lib/charts/machine.ts](../../../frontend/src/lib/charts/machine.ts)
reads `summarize_ms` off the item ledger and returns one ladder per run: one
value per configured percentile, in whole milliseconds, over every run the ledger
holds. Two panels read that one array, which is what stops "how long is the tail
today" and "is the tail growing" from being two different numbers about one run.

**Five plots, one a percentile, on ONE shared scale.** Five lines on one chart at
five percentiles of one measure is a bundle a reader untangles by colour;
separated, each is a trend read in one look. Independent scales would make five
different shapes look alike, so the domain is computed once across every value
and every plot is the same box moved down. That shared domain is what the oracle
checks, because it is the property the arrangement exists for: a p99 twenty times
its own p50 has to look twenty times taller. Authority: Susan and Jony,
2026-08-31.

**The plots are stacked, not side by side.** They share the day axis at the foot,
so comparing p50 with p99 on one run is reading straight down one column, and one
pointer position prints all five in the strip below rather than costing five
hovers. Five plots side by side would also map one pointer x to five different
column sets.

**One rule a boundary, down all five at once.** A model or prompt change moves
the whole distribution, so a rule per plot would be one event drawn five times.

**The aggregate stays, for the newest run only.** "How long is the tail today" is
a different question from "is the tail growing", and the aggregate is the only
place one run's whole distribution is visible at once. It is the last entry of
the same array the plots draw. Authority: Andre.

**A run under `console.min_attempts_for_rate` is printed, never drawn.** A p99
over four items is the fourth item. Runs below the floor are named with their
counts under the plots.

**No new chart type.** The small multiples are hand-written SVG, which needs no
registration at all, and the aggregate is the line chart already registered in
`frontend/src/lib/charts/core.ts`.

## Degrade rules

A missing or unparsable month draws a gap. The page stays alive and logs a
browser-console warning. It does not invent zeroes, because zero failed items and
no data are different facts.

The default page is also prerendered as SVG from the same projection. If
JavaScript never runs, the console still shows the current window and honest
empty states.

## A chart never draws a span nothing measured

The window a chart draws is the window the control set, never the days its own
data covers. That is right and it is not going to change: narrowing the span
would make a seven-day record look like a thirty-day one, and the preset a
reader picked would stop meaning anything. What was wrong until 2026-09-01 was
that a chart did not say what it had done with the difference.

Measured 2026-09-01 at 1440 on the built console, on the committed ledger:
`Time per item, by stage` drew a 1,292px plot with every mark between x=1,030
and x=1,342 - **312px, 24 percent of the plot, all against the right edge** -
because the window was 30 days and 8 carried a timing. `Failure rate against
volume` and `Summary length against the length asked for` drew columns on the
same 8 of 30. Nothing on any of the three said so.

Three charts on `/console/` now state it, out of one rule in
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts):
`coverage` counts the columns that carry a measurement, `coverageRegions` places
the empty span, and `coverageSentence` writes the one line under the title.

- **`SPARSE_COVERAGE` is the line, and it is half.** Half is where the empty
  part becomes the larger part of the picture and the marks start reading as a
  chart squashed into one corner. Above it a chart says nothing: a window
  missing a day or two draws that day as a break in a line, and a caveat under
  every chart is one nobody reads. It is a drawing constant beside
  `LABEL_ADVANCE_EM` and `CELL_MAX` rather than a knob in `config/`, because
  nothing an operator would tune sits behind it.
- **The sentence names both numbers.** `We timed 8 of these 30 days` - days
  drawn and days measured, so a reader can count the columns and check it
  (`CLAUDE.md` Rule #10). A share would not be checkable against anything on
  the screen.
- **Each chart brings its own subject and verb**, because the three measure
  three different things: one timed a day, one wrote summaries on it, one
  planned items for it. No one verb is true of all three.
- **The empty span is tinted at the surface level, never hatched.** It is a
  `<rect>` filled with `--color-surface-sunken`, drawn before the grid so a tint
  never sits over a mark. A hatch is a pattern a reader stops to decode, and
  this one has nothing to say beyond "no measurement reached here".
- **A pointer on an unmeasured column is told so.** The hover mechanism always
  worked on those columns and still read as broken, because four columns in five
  carried a date and a set of blanks - or worse, on the band chart, a set of
  zeros, which says every summary of that day landed nowhere. The strip prints
  one row instead: `Nothing was timed on this day`, `Nothing was summarised on
  this day`, `No item was planned on this day`.

Rejected: fitting the domain to the measured days (Editor - it hides the record
and breaks the preset); saying nothing and letting the reader see the gap
(measured, the reader reads it as a right-aligned chart with a broken hover and
asks why, which happened twice - owner, 2026-08-31); and refusing the hover
outside the measured span (Susan - it makes the dead region feel dead rather
than explaining it).

The oracle is over the drawing, not over the rule. It counts the columns
carrying a mark itself, holds each chart's own sentence to that count, and
asserts that no mark falls inside a tinted span -
[../../../frontend/tests/console-coverage.spec.ts](../../../frontend/tests/console-coverage.spec.ts).

## See also

- [frontend.md](frontend.md) - the console view that consumes these shards.
- [../contracts/schemas.md](../contracts/schemas.md) - why a migrated row keeps the `version` cell it was written with.
- [../sources/item-health.md](../sources/item-health.md) - the private item-grain ledger.
- [../../concepts/design-system.md](../../concepts/design-system.md) - how a console figure is worded and printed.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - ledgers as records, logs as evidence.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1 and Rule #11.
