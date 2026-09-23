# What the page is drawn from

**Last Updated**: 2026-09-23

Every knob a reader's page or an operator's console is drawn from: the file that
owns them, the rule that decides which file owns a key when two name it, the
bounds that make a layout number safe to edit, and the numbers the day page, the
archive and the console read. What a knob is, and what is not one, is
[../config.md](../config.md).

## `config/appearance.json` - the published surface's own file

Split off `config/idhazh.json` on 2026-08-29 on the same argument the source model was split on, one surface later: curating a reading surface and pinning a decode temperature have different review cadences, and one file meant every appearance edit touched the file that holds the sampler seed.

Its blocks:

| Block | What it tunes |
| --- | --- |
| `digest` | The day page. Formerly `idhazh.json`'s `ui` block, unchanged in shape. |
| `console` | The operator viewport. Formerly `idhazh.json`'s `console` block. |
| `assist` | On-device archive search. Formerly `idhazh.json`'s `assist` block. |
| `frame` | The frame maximums, the reading measure, the gutter range, and the three breakpoints. |
| `theme` | Whether gradients, elevation and the display face are drawn, and how strongly a panel takes a tint. |
| `chart` | Drawn height and server-side width, whether a chart answers a pointer and how wide that readout may be, the palette, tick density, and the sparkline and donut geometry. |
| `icons` | Icon size, whether an icon takes the hue of what it means, and whether a topic carries a mark. |
| `motion` | The two durations, and one switch. `prefers-reduced-motion` sits above the switch and is deliberately not configurable. |

The contract is `backend/idhazh/contracts/appearance_config.py`, and it imports `UiConfig`, `ConsoleConfig` and `AssistConfig` from `idhazh.contracts.knobs` rather than copying them: the file moved, the contract did not fork. `AppConfig` keeps the three moved blocks, and the frontend loader merges three layers - defaults, then the legacy block, then the new file - so a checkout that has not been migrated resolves to exactly what it resolved to before (`CLAUDE.md` section 11). The legacy block is a middle layer rather than a discarded one so a partly migrated file cannot snap a knob back to a default nobody chose.

**One definition, two exposure points, so one new knob is a six-file commit.** `UiConfig`, `ConsoleConfig` and `AssistConfig` are each reachable through `AppConfig` and through `AppearanceConfig`, and both of those generate a schema. Adding one field to any of the three therefore moves two models, both `schemas/app-config.schema.json` and `schemas/appearance-config.schema.json`, a `version` stamp and a `changelog` entry on each of those two, and the committed fixtures for both files under `tests/fixtures/contracts/`. Change the model and stop there and the contract drift gate fails on a file the commit never mentioned, which reads as an unrelated breakage. Plan the second half before writing the first.

### Every key has one owner, and the owner is whoever draws it

The merge runs one way: `config/appearance.json` is the last layer, so it wins. A knob the legacy `ui`, `console` or `assist` block still carries therefore has to agree with the appearance file. Let the two differ and the loser is silent - a knob edited in the file somebody happened to open does nothing, and nothing says why.

Six keys were settled that way, and the rule is the same each time: **the file that owns a key is the file whose readers read it.** `digest.visual_side` on 2026-09-05, then the last five later the same day:

| Key | Was | Owner now | Why |
| --- | --- | --- | --- |
| `console.chart_height` | 180 here, 220 there | `config/appearance.json` | Every reader is a console page. Nothing under `backend/idhazh/` reads it |
| `console.chart_width` | 600 here, 760 there | `config/appearance.json` | Same |
| `assist.recall_min` | 0.68 here, 0.61 there | `config/idhazh.json` | The one reader is the retrieval gate. The frontend's `AssistConfig` does not declare the field |
| `assist.max_tokens` | 256 in both | `config/idhazh.json` | The one reader is the encoder. The keep-list stopped the page receiving it, which left the appearance copy with no reader at all |
| `assist.min_readable_letter_share` | 0.5 in both | `config/idhazh.json` | Same |

Two contract defaults moved with them: `console.chart_height` 180 -> 220 and `console.chart_width` 600 -> 760. Those are the numbers `chart.height_px` and `chart.width_px` already carried - the pair was raised when the frame widened - so a fresh clone with no `config/` had been drawing a console chart at a size no console page uses. Every value legal before is legal now, so no read-side migration is owed, and a `config/idhazh.json` written before today still declares the two sizes and still wins over the new defaults through the middle merge layer.

`assist` went the other way because the block holds two kinds of knob. Four of them - `similarity_floor`, `result_limit`, `search_months`, `search_min_days` - are read in the browser, and the appearance file declares those. Two - `recall_min` and `eval_corpus_through` - are the retrieval gate's inputs, read by `backend/tests/test_retrieval_eval.py` and drawn by nothing, so the pipeline file declares those and the appearance file declares neither. The 0.61 that sat here had no reader at all: it was the bar's value before it was re-derived against the pinned corpus on 2026-09-04 ([../evaluation.md](../evaluation.md)), 0.07 below the live 0.68, which is 10.3 percent of the bar - worth nothing while nothing read it, and a wrong gate the day something did.

**Two more of the block are the pipeline's, and only the pipeline file declares them now.** `max_tokens` and `min_readable_letter_share` are the encoder's, read by `backend/idhazh/embed.py`. They sat in the appearance file as well as the pipeline one, with the same values, which the gate below tolerates - and the tolerance was correct while the page received them, because the appearance file was the last merge layer. It stopped being correct the moment the keep-list landed: from then on the browser was handed neither, so the appearance copies were read by nothing, which is where `assist.recall_min` had been an hour earlier. Both were deleted on 2026-09-05 for that reason. Until that keep-list all four of the pipeline's knobs were merged straight into the prerendered `/archive/` document, because `assistConfig` returned the raw merge. It now keeps exactly what `AssistConfig` declares. A keep-list rather than a strip-list: a strip-list has to be extended every time a knob lands in the block and ships it to readers in silence when somebody forgets, while a keep-list's own failure - a browser knob added to the file and not to the interface - is refused by the compiler at the component that reads it. Measured on a real build, 2026-09-05: `frontend/build/archive/index.html` went from 18,659 to 18,567 bytes, so the four knobs were 92 bytes on every load of that page.

**Five more are the build's, and neither file's readers are in a tab.** `model_base_url`, `model_cdn_origins`, `model_revision`, `model_digests` and `model_fetch_deadline_ms` are the encoder's failover leg, read by `vite.config.ts` and `svelte.config.js` through `frontend/asset-base.js`. The pipeline file declares them and the appearance file declares none of them, for the same reason as the two above: nothing the published surface is drawn from reads any of them. One of them is roughly 600 bytes of hex, so the keep-list matters more than it did - declared in `AssistConfig` on the frontend they would ride in the prerendered `/archive/` document and its `__data.json` twin, against a ceiling of 7,553 gzipped bytes, for a value no component reads.

**A mirror pinned to the default is only right where a fallback is what it pins.** The browser needs a token cap of its own and holds a hardcoded 256 in `frontend/src/lib/assist/loader.ts`. That copy stays, because `loader.ts` runs in a tab and cannot open `config/idhazh.json`; putting the cap back on the page would undo the 92 bytes the keep-list just took off it. What changed on 2026-09-05 is what the gate compares it against. `test_the_browser_reads_a_query_exactly_as_far_as_the_runner_read_the_items` in `backend/tests/test_embed.py` compared the literal against `AssistConfig.max_tokens` - the contract default - while `Embedder` truncates at `self._assist.max_tokens`, the committed knob. Set `assist.max_tokens` to 384 in `config/idhazh.json` and leave `loader.ts` alone and the old assertion was still `256 == 256`: green, with the runner reading 384 tokens of every item and a tab reading 256 of the query. Nothing else would have caught it - no error, no 404, just worse search results.

The rule the two shapes of mirror follow:

| The frontend copy is | Pin it to | Because |
| --- | --- | --- |
| a fallback, with `config/` merged over it | the contract default | The default is the number that fallback resolves to on a clone with no `config/`, which is the only time it is read |
| the only value that runtime has | the committed knob | Nothing merges over it, so it has to equal what the runner actually ran with |

`ARCHIVE_RECENT_DAYS`, `payload_slow_ms` and `visual_side` are the first shape and pin to the default, correctly. `MAX_TOKENS` is the second shape and was pinned to the default by copying its neighbours. `test_the_oracle_the_cap_sits_at_or_above_the_p95_of_what_it_reads` had the same subject and now reads the committed knob too: the question it asks is whether the cap covers the ordinary item, and only the cap that ships can answer it.

**The gate is `test_a_moved_block_is_declared_in_one_file_and_the_other_does_not_argue`**, in `backend/tests/test_appearance_config.py`, and it runs over all three moved blocks. It refuses two files naming one knob twice with two answers; it tolerates two files naming it twice with one answer, because that is the migration's middle layer doing its job. `backend/idhazh/config.py` already followed the same rule before any of this: it reads `console.max_window_days` out of the appearance file, and says in a comment that `AppConfig.console` is the layer underneath and can disagree.

**A mirror test has to hold the pair that decides the picture.** `test_the_console_chart_size_is_a_knob_the_frontend_agrees_with` used to compare the contract default against `config/idhazh.json` and then against the frontend's own fallback constant. All three were 600 and the console drew at 760, so the gate was green over three copies of a number nothing drew with - which is worse than no gate, because it reads as coverage. It now starts from what `config/appearance.json` declares, because that is the last merge layer and therefore what the server draws at, and requires the contract default and the frontend fallback to be that same number.

### Why a frame width is a knob, when a 2026-08-28 ruling said it should not be

The objection was that a config able to set the frame to 300px would need a code change to still look right. That is true of an unvalidated number and false of a validated one. **`frame.reading_max_px` cannot be set below 960 or above 1600; `measure_ch` cannot leave 52 to 80; `breakpoints_px` must be exactly three ascending, distinct widths; and `console_max_px` may not be narrower than `reading_max_px`.** A validator refuses a document that breaks any of them, so no reachable value breaks the design. The contract is the answer to the objection rather than a refusal of the knob, and `backend/tests/test_appearance_config.py` asserts every bound in both directions.

One cross-block rule is worth naming because it is the one that bites in production rather than in review: `chart.width_px` may not exceed `frame.console_max_px`. The server prerenders every chart at `width_px` because a prerendered chart has no element to measure, and the client re-measures once a script runs. Draw wider than the container can ever be and every first paint is wrong and then visibly snaps - on the one kind of site whose whole premise is that the page is finished before any script runs.

Two knobs in that block decide what a chart's axis and its readout look like, and both exist because a number written into a component is a number nobody can move. **`chart.tick_density` is the most date labels an x axis may carry** - a ceiling and never a target, because the axis then measures those labels against the room the plot actually has and drops more of them until none touch. So a month of columns gets six dates on a desktop rather than one span string, three on a phone rather than six overlapping ones, and a column whose date was dropped keeps its tick mark. **`chart.readout_max_share` is the widest the readout strip under a plot may be, as a share of that plot** - 0.33, bounded above 0 and at or below 1. The strip sits below the plot, so no value here can cover a mark; the cap is what stops it becoming a paragraph. The floating box it replaced was measured on 2026-08-29 at 88 to 121px over a 220px plot, which is 40 to 55 percent of the chart it was explaining.

## Console surface

The console knobs are:

- `console.default_window_days`
- `console.window_presets`
- `console.today_anchor`
- `console.pan_days`
- `console.zoom_factor`
- `console.min_window_days`
- `console.max_window_days`
- `console.min_attempts_for_rate`
- `console.chart_height`
- `console.failure_list_max`
- `console.source_rows`
- `console.feed_rows`

The 30-day setting is a viewport. It never deletes rows. `failure_list_max` is
the same idea one level down: the failed-item list shows a page at a time and
offers the rest, so the charts above it stay reachable. `source_rows` and
`feed_rows` are caps on two ranked lists beside it - the sources a window's
failures cost the most articles, and the feeds that failed at least once. Both
state their tail in one sentence rather than offering more rows, because a
ranking is read from the top and a tail is a number, not a page.

`window_presets` is the list of spans the console's window control offers, and
one control sets the span for every section that follows it. Five presets rather
than a free number, because a wider window fetches a month file per month it
reaches back into - so every value is a distinct transfer cost, and the values
between these five cannot be told apart on the page. The narrowest is one day,
added 2026-09-06: it is the cheapest read the console can do, one month file and
the run that has just finished, and it is what an operator wants when a run has
gone wrong and the surrounding month is noise around it. `default_window_days`
must be one of them, or the page would open on a window its own control cannot
name, and every preset must sit between `min_window_days` and `max_window_days`.
All three rules are in the contract, so a config that breaks one fails the build
rather than the page.

`max_window_days` (366) is not a viewport clamp and lowering it makes no page
cheaper. **It is a retention floor**: `AppConfig` refuses a cleanup age shorter
than the months a window this wide can touch, so the number decides how far back
the month shards may not be deleted. Lower it and the pipeline is authorised to
delete shards the console can still ask for, and a deleted shard draws as a gap
that reads like a day the pipeline did nothing
([retention-ages.md](retention-ages.md#why-14-and-not-13)).

`zoom_factor` has had no reader since the presets landed: the `+` and `-` keys
step to the next preset instead of scaling the span, because a free span is the
thing the presets exist to prevent. The knob is still in the contract, and
retiring it is a removal with a read-side migration behind it
([../config.md](../config.md#removing-a-config-field-is-breaking-and-its-migration-is-the-file)).

## Reader surface

Six knobs decide the day's leading block, and every one of them is a number the
pipeline reads at assemble rather than a literal in a stage.
`ui.leading_stories` (5) is the most stories it may hold, `ui.leading_per_desk`
(2) the most from one desk, and `ui.leading_min` (3) the fewest worth drawing a
block for - under it nothing renders and the day goes straight to the stream.
`ui.lead_cluster_floor` (3) is how many distinct sources must name one registry
entity in their published titles before that shared subject counts,
`ui.lead_shared_subject_weight` (0.2) is what it then adds, and
`ui.lead_max_yesterday` (1) bounds how many of the leads the feed dated to the
previous day. None of them is handed to a browser: the block is decided before
the page sees it, and the page draws what it is handed.

Where the weight came from, and why it must stay under `collect.carriage_step`, is
[../../architecture/sources/discovery.md](../../architecture/sources/discovery.md#why-a-shared-subject-is-worth-less-than-a-second-carrier).

`ui.items_per_topic` is retired. It was how many of a topic's stories the
all-topics page showed before linking to the rest, and the leading block
replaced that page structure on 2026-09-01. The field survives on `UiConfig` so
a config written before then still validates - an unknown key is refused - and
nothing reads it.

`ui.archive_page_size` (25) is how many stories the archive's list adds each
time a reader asks for more. The day page pages at twelve because a day is short
and the reader came to read it; the archive holds thousands and the reader came
to find one, so it opens on the same twenty-five the console's failure list
does. It hides nothing - every story is one more click away, and the order is
the published one.

`ui.archive_recent_days` (14) is how many of the newest published days the
archive lists as rows of their own, each carrying the long date, the story count
and whether every story finished. Every other day sits inside a disclosure for
its month, and every month older than the newest published year sits inside a
disclosure for that year - so the list a reader meets grows by twelve rows a
year rather than by 365. Fourteen because a row here invites a reader back to a
day, so it has to be a day whose read marks are still there: `ui.read_mark_days`
keeps a mark for the same fourteen days, and the two move together or the block
starts offering days that come back looking unread. It was seven on both counts
until 2026-09-06. The ceiling is 31, and the bound is the point:
above a month the block is the wall of dates it replaced, and a month row
already reaches any date in two clicks. It is one of three knobs in this block a
browser is never told - the archive's `load` decides the list at build time and
the page draws what it is handed.

`ui.archive_window_days` (30) is the span the archive's window control opens on,
and it is the third. **It names one of `console.window_presets` rather than
declaring a second list of day counts**, and both config documents refuse a file
where it does not - the same rule `console.default_window_days` has had since
2026-08-29. So the contract holds exactly one list of spans, and the archive and
the console cannot end up offering different day counts for the same idea. The
cost of that is real and is the price of one list: a config that narrows the
presets has to name the archive's span inside the narrowed list. Thirty is what
the console opens on and about the reach `assist.search_months` already gives a
search, so the control ships opening on what the archive costs today. Nothing
reads it yet; the control is row 25 of
[../../../TODO/20260906-constant-cost-reads-plan.md](../../../TODO/20260906-constant-cost-reads-plan.md).

`ui.filter_min_chars` (2) is how many characters a reader types before an
in-place filter narrows a list. It binds both surfaces, because the day page and
the archive share one panel since 2026-09-01, and it is a knob rather than a
literal for that reason - the same rule cannot be spelled in two components
(Guardrail #6). Two rather than one because one letter narrows nothing: measured
2026-09-01 over the 12 committed days and 4,203 story titles - arithmetic over
committed text, so the spread is zero by construction - the median single letter
matches 80.2 percent of them and `e` matches 99.8 percent, against a median 0.8
percent for a two-letter pair. A first keystroke that redraws the page and
removes almost nothing is work the reader watches for no answer. The ceiling of
8 is where a field stops narrowing anything a reader would think to type.

`ui.desk_thin_max` (12) is the most stories a desk may publish and still be
called thin. A thin desk prints one sentence saying how many stories our sources
offered it and how many were too old to run; every other desk prints nothing,
because a shortfall sentence under all five is a column of absences pretending
to be information. Twelve is one page of the stream - what a reader sees before
the first `Show more` - so a desk under it is a desk they see the whole of at
once, which is where "is this broken?" starts. Measured 2026-09-02 over the 12
committed days and 56 desk-days: 7 sit at or below it, 12.5 percent, and the
record has a gap with nothing between 4 and 12, so any value from 5 to 12 selects
the same six startup desk-days and 12 adds the seventh. Arithmetic over committed
payloads, so the spread is zero by construction. It is a knob rather than a
literal because it decides whether a page speaks, which is not a number a
component may hold (Guardrail #6).

`ui.shell_seed_items` (15) is how many of a day's stories a prerendered document
carries. It is the one knob in this block a browser is never told: the root
layout inlines the rest of them into every document, and a build-only number put
there would ride to every reader on every page for ever. **It has decided what a
reading document holds since 2026-09-01**, when the topic routes and then the day
route stopped inlining their lists and began fetching the remainder: measured
2026-09-01
on the 431-story day of 2026-08-30, `gzip -9`, the first fifteen stories cost a
dated route 20,302 bytes across the two documents it emits, against 420,074 for
all 431.

**It is a floor and not the whole answer, and the day route spends the rest.**
Fifteen covers the twelve a flat list pages at and
the five the leading block draws. But a lead is chosen across the WHOLE day, so
it is not inside any prefix: measured 2026-09-01 on the 601-story day of
2026-08-31, the five sat at positions 249, 285, 337, 344 and 493. The document
carries those five as well as the seed, or their anchors land on nothing - so a
day document is bounded at `shell_seed_items` plus `leading_stories` and a topic
document at `shell_seed_items` alone, which is what
`frontend/tests/payload-weight.spec.ts` holds them to.

`ui.payload_slow_ms` (1200) is the exact opposite knob, and the pair is worth
reading together. It is how long a reader may wait for the rest of a day before
the page says one sentence about it, and it is the one knob in this block **only
a browser reads** - the wait happens in the reader's browser, and a prerendered
document is the only channel a static site has to tell a browser anything. So
this one rides in every document on purpose, where `shell_seed_items` is kept
out of them on purpose.

What appears past it is a sentence and never a dot: no spinner, no skeleton and
no progress bar. The frame a reader already has is readable, so there is nothing
to fill, and a byte readout would be worse than nothing - a compressed response
reports its compressed length, so a bar drawn on it prints precision the number
does not carry, which
[../design-system.md](../design-system.md) already calls a bar making it up.

The bounds are 250 ms and 30 s. Under 250 the sentence fires on a fetch that was
never slow, which teaches a reader to ignore it; over 30 s they have already
decided the page is broken. Measured 2026-09-01 on a developer machine /
 / node 24.12.0, Chromium against a local preview server: a
9,731-byte served day answered in 10.2 to 22.3 ms over 12 probes, median 13 - so
the default sits about 90 times above that median and cannot fire on a healthy
fetch here. That is a server on the same machine, not a reader's connection, and
what a reader's connection costs is not something anyone here can measure. That
is exactly why the number is a knob and not a constant.

The `assist` block is on-device search. The runner embeds the day and commits
the vectors; a reader's tab embeds only the query. The first two knobs say how
much of an item the encoder is allowed to read, the last two say how much of
the archive a search reads at all, and the five `model_` knobs say where the
browser may fetch the encoder from and what it must prove about the bytes. All
of them are set from what was measured rather than from taste.

- `assist.max_tokens` (256) is how far into an item's text the encoder reads
 before it truncates. 512 is a hard ceiling because that is the encoder's
 position table, and 256 is the default because that is what the model was
 trained at. This is the one knob here that was moved out of code, and the
 move came with the measurement that says where to leave it: over the 1886
 embedded items of the six committed days, p95 is 217 tokens, p99 is 243 and
 the longest is 280, so 256 reads 99.95 percent of every token published. The
 0.58 percent of items that do run over lose a mean of 13 tokens off the end.
 Raising it would buy that 0.05 percent and re-date every committed vector, so
 it stays. `backend/utilities/token_budget.py` reproduces the sweep, and a test
 fails if a future day's p95 ever climbs above the cap.
- `assist.min_readable_letter_share` (0.5) is how much of an item's alphabet the
 encoder has to know before the item gets a vector at all. The committed
 weights carry an English uncased vocabulary. An item in another script still
 gets a vector out of that encoder - a confident, well-formed one, about which
 characters appeared rather than about the story, which no query a reader types
 will retrieve. Below this share the item gets no vector and the run logs why;
 the item still publishes and still reads normally. Half is a plain reading of
 "mostly not in our alphabet", and the corpus says the exact number does not
 matter: 3 of 1889 items score 0.0 and the next lowest scores 0.9975, so every
 threshold between 0.01 and 0.99 picks the same three items.
- `assist.search_months` (1) is how many month shards a search always reads,
 newest first. The reader waits on the download and never on the arithmetic: one
 month is a 2.53 MB vector file beside a 518 KB browse index, about 2.1 seconds
 on a 10 Mbit line at the rate the committed days ran, against 74 to 159
 milliseconds of ranking. The fetch is 9 to 30 times the ranking at every scope,
 so this knob buys download seconds and never compute seconds, and three months
 is a 14.4 second wait before the first result. One month is the only scope
 whose first search starts inside about five seconds.
- `assist.search_min_days` (7) is the fewest days of published stories a search
 tries to reach, and it is what stops a calendar shard being mistaken for a
 window. On 31 August the newest shard held 31 days; on 1 September it held one,
 so the same search reached 31 times less for a reason no reader could see, and
 finding nothing looked exactly like a story we never published. Below this
 floor a search reads one more shard, and one more only, so the cost is bounded
 at a single extra fetch. Seven days, and it is now this knob's own number
 rather than a borrowed one: it used to be justified as the week
 `ui.read_mark_days` and `console.min_window_days` also kept, and on 2026-09-06
 those moved to fourteen calendar days and to one day. The measurement is what
 still holds. The
 extra fetch fires on the first 6 days of a month, 20 percent of them, and only
 when the shard already being read is small, so the bytes a search moves are
 levelled across the month rather than doubled. Widening either knob is visible
 to a reader rather than silent: the page prints the days it searched under the
 box.

The browser keeps its own copy of the token cap in
`frontend/src/lib/assist/loader.ts`, because the config reader is server-only and
a query read further than the items it is matched against is a different
question asked silently. A backend test compares the two and fails when they
separate.

**The five `model_` knobs are the encoder's failover leg, and they are read at
build time rather than by a reader's tab.** Our own origin is primary and the
committed weights stay; these are reached only when this site has already
failed to hand a reader the encoder. `vite.config.ts` and `svelte.config.js`
read them through `frontend/asset-base.js`, so the address the browser fetches
from and the `connect-src` that permits it come from one value and cannot
disagree. None of them reaches the prerendered `/archive/` document.

- `assist.model_base_url` (`https://huggingface.co/Xenova/all-MiniLM-L6-v2`) is
 the second origin. A repository prefix rather than a bare host, so the fetch is
 built from one value; the path in it is a directory on that host and only the
 ORIGIN reaches the CSP.
- `assist.model_cdn_origins` (`https://us.aws.cdn.hf.co`) are the origins that
 base redirects a large file to. Listed because a browser checks a redirect
 target: measured 2026-09-09 from the live Pages origin, 15 reads of 15, the
 four small files answer on the base host and the 23 MB of weights answers 302
 to this CDN. Listing the base host alone would pass the small files and block
 the model, which is the worst of both - the reader waits, then gets nothing.
- `assist.model_revision` (`751bff37...`) is the upstream commit the committed
 weights are the bytes of. The contract refuses anything that is not a full
 40-hex SHA-1, because a branch hands back whatever was uploaded last and makes
 every digest below a coin flip.
- `assist.model_digests` is the SHA-256 of all five encoder files. **This is what
 makes a second origin safe at all**: the browser hashes what arrives and
 discards the WHOLE set on any miss - a non-200, a truncation, a timeout or a
 wrong digest - so provenance is never mixed across files. Without it the URL
 above would be a permission rather than a fallback. A backend test hashes the
 committed weights against this map, so a manifest that drifts fails the build
 rather than failing closed on every reader.
- `assist.model_fetch_deadline_ms` (120000) bounds the whole set rather than
 each file, because a reader is waiting on the set and a per-file deadline lets
 four slow files add up to a wait nobody bounded. Two minutes is the download it
 exists to complete: the hub serves the weights uncompressed at 22,972,370 bytes
 where our origin gzips them to 16.22 MB (measured 2026-09-08 on a laptop
 against CloudFront AMS58-P3, n=3, spread 0), about 18 seconds on a 10 Mbit line
 and about 100 on a 2 Mbit one.

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [../design-system.md](../design-system.md) - the sufficiency checks a surface drawn from these knobs has to pass.
- [../console-design.md](../console-design.md) - what the operator viewport is for.
- [../search-quality.md](../search-quality.md) - what the `assist` knobs are measured against.
- [../../architecture/publishing/frontend.md](../../architecture/publishing/frontend.md) - how the published site reads them.
- [../../architecture/publishing/layout.md](../../architecture/publishing/layout.md) - the frame and the page these numbers draw.
- [../../architecture/publishing/console-charts.md](../../architecture/publishing/console-charts.md) - what `chart.*` draws.
- [../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md) - what `console.*` tunes.
- [retention-ages.md](retention-ages.md) - why `console.max_window_days` is a retention floor.
