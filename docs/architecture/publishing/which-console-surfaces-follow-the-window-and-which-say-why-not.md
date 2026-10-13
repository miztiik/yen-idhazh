# Which console surfaces follow the window, and which say why not

**Last Updated**: 2026-10-12

One control at the top of the console sets the span for the whole page. This page
is the control, and the list of every surface that does not simply follow it -
which is the question asked far more often than how the control is drawn.

Which panel sits on which route is [console.md](console.md). The control stands on
the strip beside the route tabs, and sticks with it from the wide breakpoint up;
the shell it stands in is
[what-sits-above-every-console-route.md](what-sits-above-every-console-route.md).

## One window governs the page

The window belongs to the page, not to a chart engine. The control is a set of
radio buttons carrying `console.window_presets` - five spans, all five on the
page at once, so the cost of the wide one is readable without opening a menu. A
slider was rejected for the same reason: every span is a different number of
month files to fetch, and the spans between these five cannot be told apart once
drawn. The narrowest is one day, the cheapest read the console can do.

The initial span is `console.default_window_days`. The labelled radio group
supports pointer and keyboard selection with visible focus. There is no shared
pan or multiplicative zoom control. Its former knobs have no live reader and
are removed; [appearance configuration](../../concepts/config/appearance.md#console-surface)
owns the retained span bounds.

**Build-time evidence uses the site's newest published day**, the newest day the
site published a digest, which is the day the console treats as today. Every
build-time span is placed on that day using `console.today_anchor`, read at build time
by `windowDay()` in `frontend/src/lib/server/window-day.ts`. Neither the build
clock nor any record's own newest day places a window, so two builds of the same
data draw the same windows, and a record whose rows stop leaves its panels empty
for the window rather than moving the window back to its last rows. A route
reads the widest configured window and no day before it
([how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md#how-far-a-ledger-reaches)).
When the site has published no day, the window is placed on the build's own UTC
day: there is nothing to draw either way, and the page still renders.

**The route distinguishes a quiet answer from an absent record.** Published
ledger panels share the pending, quiet, missing and failed states. A reach that
did not arrive supplies no data date. Private build-time panels retain their
record notes and do not acquire a public reader just because the engine leaves.

Three rules keep the control honest and all three are in the contract, so a bad
config fails the build rather than the page:

- `default_window_days` is a member of `window_presets`, or the page opens on a
 window with every button unchecked.
- The presets are ascending and distinct.
- Every preset sits between `min_window_days` and `max_window_days`.

### Published-ledger panels anchor the window on the returned record

Pipelines, Summaries, Voices and Hardware use declared native queries. Their common endpoint is the
oldest available `through` among its ledgers. Each query clamps its first day
to its own ledger's first day. Neither the browser clock nor the build clock
supplies a data day. A reach that did not arrive supplies no day at all.

The typed record reach passes through the existing route-to-layout window
slot. `WindowStatus` says `Showing N days, to DATE.` If the record is shorter
than the requested preset, it also names its first day and the UTC day on
which that preset fills. A first frame with no record yet prints no data date.
Build-time evidence keeps the published-day behavior above. This does not
reinterpret the recorded judging and holdout evidence on Judgement.

### Build-time window space and control behavior

**A build-time window of N days is exactly N days, even when the ledger holds fewer.** A
window that shrinks to fit the rows it finds is invisible while nothing on the
page names the span and a lie the moment a control does - a page reading 90 days
while the charts draw 2 cannot be trusted about anything else. Empty calendar
space is the honest answer to "there is nothing there".

**Changing the preset asks only for its declared native window.** The shared
query reader owns indexes, files and reuse; no panel rebuilds a public-month URL
or downloads the retired telemetry mirror. The control shows a busy state while
its answer is pending. Private build-time values already in the page are selected
without a fetch.

**The choice is kept in `localStorage` and read on mount, never during
prerender.** The first frame uses the configured choice. Native panels do not
claim a data date before their record arrives.

**Every route hands the layout the same window choice.** Published-ledger
routes also hand over typed record reach. All read the same
`idhazh:console-window` key, so a span picked on Pipelines is the span Hardware
opens on and the other way round. The representative console journey checks
shared navigation; deterministic window and query rules use lower-tier tests.

**A tab click carries the span too, with no page load.** The router mounts the
next route under the same layout and tears the last one down in the same
update, and the control then holds the span the next route draws.
[window-slot.ts](../../../frontend/src/lib/console/window-slot.ts) now keeps which
route holds the control in a plain variable, which a teardown reads as it is.

**If a native read fails, it is not an empty measurement.** Retrying re-asks only
unsuccessful questions and preserves successful sibling answers. No failure
white-screens the console or becomes an interpolated measurement.

## Every route has the control, including Hardware

A route without a control prints a sentence naming its fixed span instead, on the
argument that a control which answers a click by changing nothing is worse than
an absent one. **What that costs is the question the console exists for:** an
operator who narrows Pipelines to 7 days to look at a bad afternoon loses the
span the moment he asks what the machine had been doing, and two charts on two
spans cannot be compared. Hardware is also the route whose numbers move most
between runs, so it is the one where "over how long" matters most.

**Hardware asks its ledgers in the browser, not a server counter facade.**
Its declarations distinguish selected-window, newest-day and widest-span
questions. The page carries configuration and words only. Native item, host and
recorded shard-count answers supply the arithmetic; unknown counts remain
unknown instead of being derived from the hosts that happened to answer.

**A newest-day question is a snapshot, not a selected-window aggregate.**
The clock check, machine cards, slowest-article list and memory-held panel name
the newest day or its newest recorded run. They do not fall back to an older
successful run when the newest one was refused. The widest host population
supplies the machine colour ramp, so changing the selected span cannot recolour
a machine.

Panel-specific rules live in [console-machine.md](console-machine.md), beside
the questions and missing-data meanings they protect. They do not require
another browser case per panel or preset.

## The surfaces that do not simply follow the span

Each one says so on the page. Three are on Voices, one on Pipelines, one on
Judgement, and one stands on every route.

| Surface | Route | What it does | Why |
| --- | --- | --- | --- |
| `Feeds that failed` | Voices | The count and its marker read every run on record; the strip of days beside them follows the span | A windowed recount would disagree with the resting the pipeline actually performed. Two numbers for one decision is the defect the run strip already avoids. The strip answers a different question - when it broke - and that one is only readable over a span. |
| `Sources we may ask, and what they yield` | Voices | Permission, reading and retirement read every run on record; the publishing record reads `collect.source_yield_min_complete_days` complete days | It renders the run's own decisions, and the run rests on the whole count. The publishing record has a fixed span because that span is also its readability bar - one question, one number. |
| `What the ranking makes of each feed` | Voices | Reads the factor the run applied, over the span the run reduced it on | The run reduced it over `collect.reliability_window_days` when it happened. Redrawing it over seven days would print a number no run ever applied. |
| `What the record still needs` | Judgement | The three bars read the record's newest row on or before the window's last day, so they show the same counts at every preset; the strip of squares and the count of fitted days follow the span | The record is a running total that changes only when a run writes a row, so its newest row is what it holds whatever span is open. Read from the window's rows alone, a window with no row drew the bars at zero, which is the picture of a record that holds nothing. When the bars stand on a row before the window, the note names its day: `The bars show what the record held on 14 Jun 2030, before this one day.` |
| `Site size` | every route | Absolute number always; the delta and the runway are windowed | The size is a level and the operator wants today's, whatever span he is reading. The delta and the runway are rates, and a rate has to say what it is over. |
| `Minutes per visual` | Pipelines | Prints `The rule reads 14 days. Widen the window to see it.` under 14 days | The retirement rule is stated over 14 days. A median of the wrong span is the same figure with a different meaning and nothing on the page to say which one is being read. |

Source truncation and item-cost panels now derive their answers from declared
native queries over the selected window. Their old per-preset telemetry copies
are not a reason to retain an unused file reader or pan control.

**A panel that honours the control need not declare `data-windowed`.**
Lower-tier query and render tests prove dates, denominators, gaps and snapshots
from real fixtures. Do not turn the route's surface inventory into a browser
matrix.

`What is failing, by stage` and `Where an item's time went` on Pipelines draw
exactly the window's days from their native queries. Each names its span in its
own accessible label. A day with nothing to draw keeps its
column, empty, and a window with nothing to draw prints one sentence in the
chart's room ([what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md#what-is-failing-by-stage)).

## The model-change markers read the window as well

Published-ledger panels receive settings-change markers from the shared band
and use their declared date window. The old build-time counter-note reader and
TypeScript settings comparison are absent. Keep the producer's settings
comparison and the recorded input meanings; deleting a dead frontend helper is
not permission to infer setup changes from a run id or discard historical rows.

## Native answers are not a prerendered telemetry seed

Pipelines, Summaries, Voices and Hardware ask the native query door for their
declared cells and dates. Their route documents contain no copy of those query
answers. Unused server readers and retired public-month mirrors do not survive
as fallback paths. Their removal deletes no native records.

The shared band, private build-time panels and route-shell prerendering remain.
[console.md](console.md#rendering-direction) names the private boundary. Removing
ECharts does not authorize a no-prerender architecture or public copies of those
inputs. Each query and build-time read still names a fixed-size input under
`CLAUDE.md` Guardrail #12.

## Design rationale

**One selected span has one declared endpoint.** Native routes use their shared
record reach; build-time evidence uses the site's published day. Neither the
browser clock nor the build clock invents a data date. A missing native reach
stays missing rather than silently moving the panel to another record.

**The day packing has not reached gets one quiet line on the route, not a mark
on every panel.** Ruled on 2026-10-06 by Susan and Jony, with Reader on the
words, after one debate round in which each accepted the other's wording. A
mark on every date-axis panel is about 20 components in three drawing systems.
What the line leaves, said rather than implied: on bar and day-strip panels the
newest day looks like a day with nothing in it, and at the one-day window some
panels print a sentence that reads as quiet, for example
`Nothing was timed in this one day.` on Summaries, while the line above them
says that day is not packed yet. So waiting and quiet still look alike for one
day on those panels. The follow-up row that marks the unpacked days on bar and
strip panels, and gives every panel whose whole window is unpacked its own
sentence, closes it; until it lands, this entry is the record of the gap.

**The record's three bars stand on its newest row, not on the window's.** Ruled
on 2026-10-07 by Jony, with Reader on the words, after one debate round in which
Reader added the window to the note, because every windowed panel names its own
days. A window with no row used to draw the bars at zero while the record still
held what its newest earlier row counted. Three other pictures were refused: a
dash in place of each bar (the operator loses how far the record is from each
gate, an exact count the page already holds), the same bars in a muted fill (an
exact value made to look doubtful, and a second kind of target bar to say what a
date already says), and no bars at all (the empty state is the panel, and the
panel would change height with the window). So bars at zero mean one thing: the
record holds nothing, because it never held a row or because it emptied. The
note says the record `was started again` only where that row's own hold reason
says so; a row of zeros alone does not prove it.

**The failure mix and the item time split use the same declared calendar as their
readouts.** Neither trims the window to days that happen to hold readings.
Failure mix uses failed rows over recorded rows; a recorded clean day is zero,
while a day with no rows is unknown. Time split uses only complete, consistent
clock cohorts and names the missing or refused readings. Keeping those gaps
prevents a line from inventing a measurement on an unread day. These charts
do not infer planned or reached-stage populations from the rows that answered.

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) - the strip and the band this control sits under.
- [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) - Pipelines questions and their native windows.
- [who-supplied-the-day-and-which-feeds-failed.md](who-supplied-the-day-and-which-feeds-failed.md) - the three Voices surfaces in the table above.
- [telemetry-series.md](telemetry-series.md) - the monthly shards a widened window fetches.
- [retention.md](retention.md) - the prune that shortens the marker list.
