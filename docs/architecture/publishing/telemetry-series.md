# Telemetry Series

**Last Updated**: 2026-09-19

The console's interactive charts read a published projection of item health. They
never read `state/item-health/` directly.

## Published shards

`backend/idhazh/telemetry/publish/public_telemetry.py` reads
`state/item-health/<YYYY>/<MM>/<DD>.csv` and writes
`frontend/public/telemetry/<YYYY-MM>.csv`. The browser fetches these monthly
shards on demand as the operator pans the viewport.

**The source files by day and the projection files by month, since 2026-09-13.**
They take their grain from different things - the ledger from what a run writes
and what a removal takes away, the mirror from what a browser fetches - and
[../../concepts/partitions.md](../../concepts/partitions.md#a-store-and-its-mirror-may-file-at-different-grains)
owns both rules. This module is the bridge: `day_partition.days_by_month` groups
the day files, and a month is projected whole from at most 31 of them. What it
cost, stated rather than implied: the unbounded case opens about thirty times as
many file handles for the same rows, and the count is asserted in
`backend/tests/test_publish_telemetry.py` rather than described here.

**This is a month partition, and it now honours the freeze rule.** The pattern -
what closes a partition, and what a correction, a deletion or a late arrival does
to a closed one - is
[../../concepts/partitions.md](../../concepts/partitions.md). Two
freezes compose. `publish` writes only the months a caller names as changed - a
month outside that set is skipped without being read, unless its shard is missing
on a fresh checkout - and `_write_if_changed` then writes a named month only when
its projected bytes differ from the committed shard. So a re-run with no new data
writes no shard, and a run that adds one day rewrites that day's month and no
other. That closed finding 11 of
[../../reference/data-growth-audit.md](../../reference/data-growth-audit.md) (row
19 of the constant-cost-reads plan, #484); before it, `publish` globbed
`state/item-health/` and rewrote every month it found on every run, so an
ordinary run paid for every month the project had ever published. The shard is
still a full rewrite of the source month, never `merge=union` - a union of two
rewrites is a file with every row twice.

The published columns are exactly:

`date, run_id, item_id, vertical, source_id, stage, outcome, code, source_words, summary_words, source_words_before_cap, fetch_ms, extract_ms, summarize_ms, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens, model_calls, label_kind, label_prefill_ms, label_decode_ms, label_input_tokens, label_output_tokens, label_cached_tokens, summary_kind, summary_prefill_ms, summary_decode_ms, summary_input_tokens, summary_output_tokens, summary_cached_tokens, queue_wait_ms, label_ms, summary_ms, visual_plan_ms, visual_plan_ms_is_estimate, faithfulness_ms, model_wait_ms, item_total_ms, stage_gap_ms, visual_plan_tokens_written, label_prefill_tokens_per_s, label_decode_tokens_per_s, summary_prefill_tokens_per_s, summary_decode_tokens_per_s, cpu_model, cpu_busy_pct, load_1m`

Forty-nine of the census's 119. The last seventeen landed 2026-09-15 and are
[the three questions](#the-seventeen-columns-an-operator-asks-for-since-2026-09-15)
below. Positions 20 to 31 are the two model calls' own shares of the five cost
cells before them, and the kind of call each one was. The flat cells are their
sum, and the contract refuses a row where they are not.

**They used to be six, and the browser was told to subtract.** The shard ended at
`label_cached_tokens`, on the reasoning that the second call is the total minus
the first. That was wrong in three ways, each of which reads as a plausible
number rather than as an error. A remainder has no kind, so nothing on the page
could name what the second call was. The remainder is one call only where
`model_calls` is 2, and that cell is empty on every row published before
2026-09-12. And a reader who wanted the second call's cache share had to subtract
two cells and divide, which is three chances to get wrong a ratio the producer
already held exactly. Six more cells cost 72.9 and 80.1 percent more gzipped on
the two committed shards against 35.3 and 40.8 for the first six, measured
2026-09-12 with every timed row populated - and that is what the split is worth,
because the panel it feeds cannot be drawn from a subtraction
([the split](../summarize/throughput.md#each-call-is-charged-on-its-own-and-the-item-is-their-sum)).

**A shard published before 2026-09-15 still loads.** The first call's cells were
headed `call_1_*` then; `PublicTelemetryRow.from_csv_row` reads a retired heading
into the column that replaced it, one direction only. The six new cells are
appended at the end, so a cached bundle keeps working - an append moves no cell
`parseTelemetryCsv` reads, under the positional prefix it used then or the column
names it uses now ([below](#the-reader-finds-a-cell-by-its-name-so-a-column-can-move)).

**`read_shard` checks the header as a prefix too, since 2026-09-15.** It used to
demand equality, which made every widening a release blocker for exactly the file
it exists to prove still loads: the moment the contract grew a column, the
committed shard was the current header cut short and the reader refused it
(`CLAUDE.md` section 11). Cells behind the cut come back null, which is what an
empty cell already reads as. A header that disagrees *inside* the prefix is still
refused - shorter is an older shape, different is a different shape.

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
every other persisted surface had all three (Guardrail #3). `FORBIDDEN_COLUMNS` is
checked at **import**, so a forbidden field on the model stops the process rather
than reaching the published tree.

Two consequences worth stating plainly:

- **`version` is a field of the shape and never a cell.** The header check below
 is a prefix, so one more name at position zero would shift every position the
 console reads. `schemas/public-telemetry.schema.json` is where the stamp lives.
- **A published shard has to load, not merely parse.** `public_telemetry
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
cap (Guardrail #2) is three orders of magnitude away.

**The prerendered seed does not carry them, and that is a measurement rather
than a preference.** `publicTelemetry` in
`frontend/src/routes/console/+page.server.ts` inlines the default window's rows
into the console document so the page is complete before any script runs. Seeded
with their real values, the eight cost 176,753 more gzipped bytes on `/console/`
- 198,624 to 375,377, an 89 percent page, and 98,182 over the recorded ceiling.
Seeded as nulls the page is 214,985, which is 16,361 more and 62,210 under.
Measured 2026-09-05 on a developer machine / / node 24, one build per
case; the eight untouched routes moved -2 to +5 bytes between them, so the figure
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
([console.md](console.md#it-follows-the-windows-length-not-a-pan)).

The two options remain open for a panel that genuinely needs a panned answer.
Nothing on the page needs one today.

### The seventeen columns an operator asks for, since 2026-09-15

The census measures 119 columns an item at a time. This projection published 32
of them, so three questions an operator asks had no answer anywhere a person
could read.

**Where did an item's time go?** `queue_wait_ms`, `label_ms`, `summary_ms`,
`visual_plan_ms`, `visual_plan_ms_is_estimate`, `faithfulness_ms`,
`model_wait_ms`, `item_total_ms` and `stage_gap_ms`. The published row carried
fetch, extract and summarize and stopped, so the queue wait, the faithfulness
scorers, the wait on the model server and the split of the summarize stage
between its two calls were all invisible - and so was the remainder.
`stage_gap_ms` is the one that matters most, and it is the reason the other eight
come with it: it is `item_total_ms` minus every named stage, so it is the only
cell that can catch a regression in a step nobody has thought to time, and it is
worth nothing without the named stages beside it to subtract from. It is signed
on purpose, so the schema carries no lower bound on it: below zero means two
named stages overlapped or two clocks disagreed, and clamping would hide exactly
that.

**Is the model getting slower, or is there just more to write?** The four rates -
`label_prefill_tokens_per_s`, `label_decode_tokens_per_s`,
`summary_prefill_tokens_per_s`, `summary_decode_tokens_per_s` - and
`visual_plan_tokens_written`. A total cannot tell those two apart and a rate can:
a decode rate that fell while the wall clock held still is a regression, and a
wall clock that rose while the rate held still is a longer summary. The row
already carried the tokens written per call, so the rates are what completes the
pair.

**Was it the machine?** `cpu_busy_pct` and `load_1m` are per item and vary item
to item, so a slow row can be read as a busy box rather than a slow pipeline.
`cpu_model` is constant inside a shard and is carried anyway: a throughput number
with no machine beside it is not a measurement (Guardrail #10), and the
shard-grain counters that hold the processor are read at build time and never
published for a browser to join against.

**What it costs, measured 2026-09-15 on this checkout.** Every one of the 12,037
committed rows is empty in all seventeen, so the file on disk is the floor and
not the answer. Both cases:

| Case | Raw bytes a row | Gzipped bytes a row |
| --- | ---: | ---: |
| Today, 32 columns | 142.7 | 32.12 |
| Committed shards rewritten, all seventeen empty | 159.8 | 32.52 |
| Every cell filled the way its producer writes it | 219.5 | 54.50 |

The filled case is the one to plan against. Durations were taken from each row's
own recorded milliseconds, rates written at `round(x, 2)` as `stages/work.py`
writes them, and one 31-character processor string repeated. Fourteen months of
retention at the busiest committed day - 1,000 rows - goes from 59.9 MB to
92.2 MB, which is 5.58 to 8.59 percent of the 1 GB published cap (Guardrail #2).
At the median day of 480 rows it is 28.8 MB to 44.3 MB, 2.68 to 4.12 percent.

**`cpu_model` is 32.00 of the 76.8 raw bytes and 1.54 of the 22.4 gzipped**, so
it is 42 percent of what the widening costs the cap and 7 percent of what it
costs a fetch. It is the first cell to drop if the cap ever binds, and dropping
it takes the busiest-day projection from 8.59 to 7.33 percent.

**What was left behind, and why.** Seventy census columns still do not cross,
in seven groups.

| Group | Columns | Why not |
| --- | --- | --- |
| Refused at the trust boundary | `canonical_url`, `url_key`, `detail` | Guardrail #11. Adding one fails at import, not in the published tree. |
| Ranking provenance | `selection_score`, `authority_score`, `tier_score`, `feed_weight`, `feed_reliability`, `lens_bonus`, `recency_bonus`, `carriage_step`, `watchlist_bonus`, `carried_by`, `watchlist_hit`, `on_front_page`, `tier`, `source_form`, `published_at`, `time_source` | Sixteen cells about why a story was chosen. No timing or rate question reads one, and the ranker has its own surfaces. |
| Fetch sub-splits | `fetch_connect_ms`, `fetch_ttfb_ms`, `robots_ms`, `retry_count`, `retry_total_ms`, `http_status` | One level below the question asked. `fetch_ms` names the band; these say which half of it, which is the next question and not this one. |
| Cache and slot internals | `label_cache_pct`, `summary_cache_pct`, `slot_id`, `kv_tokens_at_start`, `prefix_shared_with_previous` | The two percentages are `cached / input` off cells already published, and the other three are llama-server bookkeeping a page never draws. |
| Shard and run bookkeeping | `shard`, `job`, `item_index`, `shard_item_count`, `item_started_at`, `item_ended_at`, `cpu_busy_max`, `cpu_busy_min`, `llama_rss_bytes`, `llama_rss_peak_bytes`, `python_rss_bytes`, `cgroup_peak_bytes` | Answered at shard grain on `/console/machine/`, which already publishes them once a shard instead of once an item. |
| What the machine had | `os_mem_available_bytes`, `os_mem_total_bytes`, `os_mem_cached_bytes`, `os_swap_free_bytes`, `os_swap_total_bytes`, `os_mem_available_min_bytes` | Six memory cells a reader never asks about. The operator console reads them out of `state/` at build time, so publishing them would cost every browser fetch and answer nobody's question. |
| Configuration provenance | `model_id`, `model_quantisation`, `n_ctx_configured`, `n_parallel`, `n_threads`, `n_batch`, `max_output_tokens`, `label_budget_tokens`, `summary_budget_tokens`, `run_visual_decision`, `temperature`, `truncation_cap_tokens` | Constant within a run. Carrying twelve constants on every row is the largest byte waste on the list, and the run surface already holds them. |
| Extraction, finish reasons, recovery | `source_chars`, `span_integrity`, `elements_found`, `element_class`, `failed_field`, `failed_rule`, `label_finish_reason`, `summary_finish_reason`, `recovered` | The extraction pass has its own panel, and a finish reason is neither a timing nor a rate. |

A column nobody reads is weight on every browser fetch, so each group above is a
decision to revisit when a question needs it rather than a permanent refusal.

### The reader finds a cell by its name, so a column can move

**`parseTelemetryCsv` in `frontend/src/lib/charts/series.ts` resolves every cell
against the header of the file it just read.** `TELEMETRY_COLUMNS` names the
cells it wants; the header says where each one sits. Nothing is read by a
position, so the writer can append, insert or reorder without moving a cell the
console draws.

Until 2026-09-16 it took each cell by index - `cpu_model` from `cells[46]` - and
guarded that with a prefix match on the header. The guard is what made the
indices survivable, and it only ever protected one direction. Reading by name
removes the question rather than guarding it, and the three cases collapse to
one answer.

| Change on the writer's side | What the console does |
| --- | --- |
| **Appending** a column | Reads every cell it knows. Ignores the new one until `TELEMETRY_COLUMNS` and `TelemetryRow` name it. |
| **Inserting or reordering** | The same. Position is not what it looks a cell up by. |
| **Removing** one, or renaming it | That cell reads as absent - null for a figure, empty for a word - and the names go to the browser console once per shard. Every other cell is unaffected. |

**An absent column degrades and does not fail** (`CLAUDE.md` section 1a). The
absent value is the one every panel already draws for a cell nothing measured,
so a shard that lost `cpu_model` draws the processor as unknown and keeps every
other figure. `telemetryColumnIndex` is the detectable half: it hands back which
contract columns the header did not carry, so nothing has to infer a gap from an
empty string.

What that gives up, stated rather than implied: a renamed column now draws as
absence where the old prefix check stopped the parse. The rename fails earlier
instead, in the contract test below, before either side ships.

**A header with no `date`, `run_id` or `item_id` is refused**, and those three
are the only refusal left. Every panel filters by `date` and counts by one of
the other two, so a file carrying none of them is not this projection - a 200
that served an error page, or a shard of some other series. Parsing it would
hand the console a month of blank rows instead of a gap. A refusal is not a
broken page: `loadVisibleMonths` in `frontend/src/routes/console/+page.svelte`
wraps the fetch and the parse in one `try`, logs `telemetry <month> could not be
read; showing a gap`, and the charts draw the gap they already know how to draw.

**A new bundle against an old cached shard is the case this was measured on, and
today it cannot be reached at all.** The prerendered seed covers
`console.default_window_days`, which at 30 days reaches back across both
published months, so `monthsToFetch` returns nothing at every preset and the
console makes no runtime shard request. Measured 2026-09-05 by serving an
11-column shard from a route interceptor at the 7, 14, 30 and 90-day presets: the
interceptor fired **zero** times, which proves the path is unreachable and proves
nothing about what happens on it. It becomes reachable when a third month is
published and the operator widens past the seeded span. What it will do then is
draw whatever cells that shard does carry and report the rest absent - for the
11-column shard above, eleven cells drawn and the other thirty-eight reported
absent against the 49 the reader knows - which is the row above rather than a
special case.

`frontend/tests/telemetry-header.spec.ts` holds all of it on built shards: a
reversed header, a header with a column inserted at the front, a header with
`cpu_model` gone, and a header that is not this projection. Every one is written
in the test. Reading `frontend/public/telemetry/` instead would cost more every
published month (Guardrail #12) and could not produce any of the four.

**Nothing in the frontend can see the writer, so a contract test holds the two
lists together.**
`backend/tests/contracts/test_taxonomy_and_prompts.py::test_the_console_reads_only_telemetry_columns_the_writer_writes`
pulls `TELEMETRY_COLUMNS` out of `series.ts` with a regex and asserts every name
in it is a name `PUBLIC_COLUMNS` writes. It fails a typo and a rename, which is
the drift the reader degrades on and therefore cannot report. It says nothing
about order, because the reader reads none. It fails first when the regex stops
matching, because a guard that quietly finds nothing is worse than no guard.
The two lists had already drifted once with nothing to notice: from 2026-08-28
to 2026-08-29 the shard carried `source_words_before_cap` and the reader did
not. **Do not tighten it to an equality.** A writer-only column is the normal
state between the commit that publishes a cell and the commit that draws it.

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
- **The reader never asks for one that went.** `telemetryMonths` lists this
 directory at build time and `monthsToFetch` filters on that list, so a deleted
 month is absent from `data.telemetryMonths` and no widening ever names it.
 `frontend/tests/console-window.spec.ts` holds that over every anchor a year
 offers, at `console.max_window_days`.

**The sharp edge is the round trip, not the parse.** `telemetryCsv`
re-serializes from `TELEMETRY_COLUMNS` as well, so a column the parser ignored
is dropped rather than carried through. Any code that reads a shard and writes
one back narrows it to the names the reader knows. The contract test permits a
writer-only column, so it cannot catch that; whoever adds column fifty adds it
to `TELEMETRY_COLUMNS` and to `TelemetryRow` in the same commit, or the client
keeps reading a projection it cannot see all of.

## What the model did - read at build time, never published

The console's `What the model did` section is not drawn from the published
shards. It is computed while the site is built, out of two private ledgers:

- `state/scores/<YYYY>/<MM>/<DD>.csv` - one row per scored item.
- `state/item-health/<YYYY>/<MM>/<DD>.csv` - one row per planned item per run.

Neither file is served and neither crosses to a browser. What reaches the page
is a count of that day's items, never a row and never a score. The derivation is
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts),
which sits under `$lib/server/` so SvelteKit refuses to bundle it for a browser.
The wording of the labels is settled in
[../../concepts/console-design.md](../../concepts/console-design.md); this table
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

Reading the column any other way is a Guardrail #10 breach on a published page, and
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

`distribution` in `model-work.ts` owns the bars: the first bar holds everything
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
`state/runtime-counters.csv`, one row per model-server job per shard per run,
holding what llama-server itself counted. The reader is
[frontend/src/lib/server/runtime-counters.ts](../../../frontend/src/lib/server/runtime-counters.ts),
under `$lib/server/` for the same reason `model-work.ts` is. Nothing is served
and no column is published: `state/` is not part of the site, and the figures
below reach a page as numbers, never as rows.

**This page is the `work` series, and the ledger held two between 2026-09-12 and
2026-09-13.** The `visuals` job filed a row of its own for the small model it
served, and `machine.PUBLISHED_JOB` keeps it out of the published
mirror: the figures below pool a run's tokens over a run's seconds, and the two
jobs served different weights, so one pooled rate over both would describe no
model. Plan 11 row #6 retired that job, so `work` is the only series a run
appends to now and the older rows are read from `state/` by hand.

Since 2026-08-31 `/console/machine/` draws them
([console.md](console.md#what-the-hardware-route-draws)). Before that the
ledger had been committed for four days with no page reading a cell of it.

| Figure | Made from | Composed as |
| --- | --- | --- |
| Seconds reading, seconds writing | `prompt_seconds_total`, `tokens_predicted_seconds_total` | summed over shards, and never added together into one "model seconds" |
| Read and write speed | those seconds against `prompt_tokens_total` and `tokens_predicted_total` | sum over sum, never a mean of per-shard rates |
| Read spread | the fastest shard's read rate over the slowest | one run only; a run of one shard reports nothing |
| Prompt cache | `prompt_tokens_total` against `prompt_tokens_cached_total` | share of every token the prompt needed, read or reused |
| Context headroom | `n_tokens_max` against `models.summarize.inference.n_ctx` | the longest sequence any shard saw. A maximum, not a sum |
| Job clock | `job_seconds` against `run.shard_timeout_minutes` | the slowest shard. A run's wall clock is its slowest shard |
| The processor | `cpu_model` | text, per shard, and never averaged |
| Busy and load | `cpu_busy_pct`, `model_load_ms` | lowest, slowest |
| Peak memory | `peak_rss_bytes` against the runner's 16 GB | the LARGEST shard, never their sum - shards are separate jobs on separate hosts |
| The shape of a run | the item ledger's `summarize_ms` | one ladder a run at the five configured percentiles, interpolated between the two nearest ranks, never pooled between runs |
| The two clocks, compared | the item ledger's `prefill_ms` and `input_tokens - cached_tokens` against the server's own totals | the same pooling and the same 5 percent bound `backend/utilities/reconcile_prefill.py` gates on |

Both ceilings come from `config/idhazh.json` through
[frontend/src/lib/server/config.ts](../../../frontend/src/lib/server/config.ts)
(Guardrail #6). A counter without its ceiling is not a measurement: 4,925 says
nothing until the configured 65,536 sits beside it.

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
workflow runs can no longer compute one; and from 2026-09-18 each model-server
job writes its counters into its own segment under `state/segments/`, so no two
writers open this file at all and the frozen scan-before-append that could not
see a sibling's push is gone. The union driver that made the repeat possible came
off every head under `state/` on 2026-09-19. See
[../sources/item-health.md](../sources/item-health.md#the-structure). What
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
 (`CLAUDE.md` Guardrail #10). A share would not be checkable against anything on
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

- [console-payloads.md](console-payloads.md) - every dataset the console fetches, and the forbidden-cell list for each.
- [frontend.md](frontend.md) - the console view that consumes these shards.
- [../contracts/schemas.md](../contracts/schemas.md) - why a migrated row keeps the `version` cell it was written with.
- [../../concepts/partitions.md](../../concepts/partitions.md) - the month partition as a pattern, and the freeze rule this writer does not yet hold.
- [../sources/item-health.md](../sources/item-health.md) - the private item-grain ledger.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is worded and printed.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - ledgers as records, logs as evidence.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #1 and Guardrail #11.
