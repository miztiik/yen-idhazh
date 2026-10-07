# Which console surfaces follow the window, and which say why not

**Last Updated**: 2026-10-07

One control at the top of the console sets the span for the whole page. This page
is the control, and the list of every surface that does not simply follow it -
which is the question asked far more often than how the control is drawn.

Which panel sits on which route is [console.md](console.md). The control stands on
the strip beside the route tabs, and sticks with it from the wide breakpoint up;
the shell it stands in is
[what-sits-above-every-console-route.md](what-sits-above-every-console-route.md).

## One window governs the page

The window belongs to the page, not to the viewport. The control is a set of
radio buttons carrying `console.window_presets` - five spans, all five on the
page at once, so the cost of the wide one is readable without opening a menu. A
slider was rejected for the same reason: every span is a different number of
month files to fetch, and the spans between these five cannot be told apart once
drawn. The narrowest is one day, the cheapest read the console can do.

The viewport default is `console.default_window_days`, and `console.today_anchor`
says where the day every window ends on sits in it. Arrow keys pan, and `+` / `-` step the window to the next
preset, from a labelled focusable control with a visible focus ring; the buttons
beside it pan with a pointer.

**Every window ends on the site's newest published day**, the newest day the
site published a digest, which is the day the console treats as today. Every
route places every span the control offers on that one day, read at build time
by `windowDay()` in `frontend/src/lib/server/window-day.ts`. Neither the build
clock nor any record's own newest day places a window, so two builds of the same
data draw the same windows, and a record whose rows stop leaves its panels empty
for the window rather than moving the window back to its last rows. A route
reads exactly the widest window and no day before it
([how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md#how-far-a-ledger-reaches)).
When the site has published no day, the window is placed on the build's own UTC
day: there is nothing to draw either way, and the page still renders.

**The route says when a window is empty because of its record.** A day is
packed only after it ends, so in normal running the packed records reach the day
before the newest published day, and every panel built on one draws that day
with nothing in it. The last line of the route's record notes says so, a step
quieter than the others, every day. A record whose packed rows stop before the
window says from when, and names the narrowest window that reaches back to them
([console-payloads.md](console-payloads.md)). Each route writes its notes once
for each preset, so the page picks the open window's and fetches nothing.

Three rules keep the control honest and all three are in the contract, so a bad
config fails the build rather than the page:

- `default_window_days` is a member of `window_presets`, or the page opens on a
 window with every button unchecked.
- The presets are ascending and distinct.
- Every preset sits between `min_window_days` and `max_window_days`.

**A window of N days is exactly N days, even when the ledger holds fewer.** A
window that shrinks to fit the rows it finds is invisible while nothing on the
page names the span and a lie the moment a control does - a page reading 90 days
while the charts draw 2 cannot be trusted about anything else. Empty calendar
space is the honest answer to "there is nothing there".

**Widening fetches, and the page prices it first.** The sentence under the band
names each wider preset that reaches into months not already in hand -
`30D would fetch 1 more month, 90D 3 more.` - and picking one re-uses the same
month-fetch path a pan uses rather than reloading the page, so rows already paid
for stay. The price is in that sentence rather than on the tiles because the
sentence is always drawn and keeps room for its longest form, so a price that
lands or clears moves nothing below it. The control shows a busy state while the
files are in the air. Narrowing costs nothing.

**The choice is kept in `localStorage` and read on mount, never during
prerender.** First paint is therefore always the window the server drew, so the
prerendered document and the control cannot disagree while the page hydrates.

**Every route hands the layout the same props.** Pipelines prices the month
files a wider window would fetch; the other routes fetch nothing and price
nothing. All of them read the same `idhazh:console-window` key, so a span picked on
Pipelines is the span Hardware opens on and the other way round -
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts)
drives it both ways in one browser session, because a route that writes the key
and never reads it passes a one-way check.

**If a telemetry month is absent or cannot be parsed, that month is a gap in the
charts.** It is not interpolated, and it never white-screens the console.

## Every route has the control, including Hardware

A route without a control prints a sentence naming its fixed span instead, on the
argument that a control which answers a click by changing nothing is worse than
an absent one. **What that costs is the question the console exists for:** an
operator who narrows Pipelines to 7 days to look at a bad afternoon loses the
span the moment he asks what the machine had been doing, and two charts on two
spans cannot be compared. Hardware is also the route whose numbers move most
between runs, so it is the one where "over how long" matters most.

**Every span the control offers is answered on the server, one small object per
preset.** The browser holds no ledger - a token total, a cache share and a
recording note all read rows the page never receives - so it cannot re-aggregate
a window the way the Pipelines viewport can. Four small objects is the price, and
it is bounded: the widest preset is the widest anything on the route can reach,
so a run older than 90 days is carried at no span at all and the page does not
grow with the ledger. That is the same rule the Summaries route's per-preset
distributions follow, and the alternative was inlining every counter row so the
browser could re-bin it.

**A panel about one run does not follow the window.** The shard board, the
reading-against-writing split, the clock check and the latency curves read the
newest run or the newest day the ledger holds, at every preset. A window is a
span and a snapshot is not something a span can narrow - a board that emptied at
7 days would say the run had stopped existing. The page states this once, above
the snapshots, and names the run they are about.

**Eight surfaces on Hardware declare `data-windowed`**, and each one prints the
day count in its own words: the run count at the top, the prompt cache, context
headroom, what the platform has been giving us, the server panel's three spans,
the latency plots, what a run reads against what it writes and the cost panel.
The refused-run list follows the window without declaring it, because a clean
span renders nothing at all and a surface that comes and goes cannot report a day
count.

## The surfaces that do not simply follow the span

Each one says so on the page. Three are on Voices, one on Pipelines, and one
stands on every route.

| Surface | Route | What it does | Why |
| --- | --- | --- | --- |
| `Feeds that failed` | Voices | The count and its marker read every run on record; the strip of days beside them follows the span | A windowed recount would disagree with the resting the pipeline actually performed. Two numbers for one decision is the defect the run strip already avoids. The strip answers a different question - when it broke - and that one is only readable over a span. |
| `Sources we may ask, and what they yield` | Voices | Permission, reading and retirement read every run on record; the publishing record reads `collect.source_yield_min_complete_days` complete days | It renders the run's own decisions, and the run rests on the whole count. The publishing record has a fixed span because that span is also its readability bar - one question, one number. |
| `What the ranking makes of each feed` | Voices | Reads the factor the run applied, over the span the run reduced it on | The run reduced it over `collect.reliability_window_days` when it happened. Redrawing it over seven days would print a number no run ever applied. |
| `Site size` | every route | Absolute number always; the delta and the runway are windowed | The size is a level and the operator wants today's, whatever span he is reading. The delta and the runway are rates, and a rate has to say what it is over. |
| `Minutes per visual` | Pipelines | Prints `The rule reads 14 days. Widen the window to see it.` under 14 days | The retirement rule is stated over 14 days. A median of the wrong span is the same figure with a different meaning and nothing on the page to say which one is being read. |

Two more follow the window's **length** rather than where a pan leaves it, and
each says so in the same words, because one rule stated two ways reads as two
rules: `Sources cut short most often`
([console-truncation.md](console-truncation.md)) and `What one item cost the
model`
([what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md#it-follows-the-windows-length-not-a-pan)).
The days they read always end on the newest published day. Their rows are
aggregated once per preset at build time - four sets of numbers cost less than
one fetch, and it keeps the section working with no script at all.

**A panel that honours the control need not declare `data-windowed`.** The exact
list of surfaces that do is an oracle in
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts),
and that oracle is stronger for being exact. A panel outside the list proves it
honours the control in its own spec, by driving the control to each preset and
reading the control's own attribute back against the panel's.

## The model-change markers read the window as well

`pipelineChanges`, which draws the model-change markers on `/console/` and
`/console/machine/`, and `scoredDays` with `modelByDate` on `/console/model/`,
read the score record's packed days in the widest window preset, which ends on
the newest published day - the cover every other panel on those routes reads -
and never the whole ledger. The
`compact-summary-quality-evals` compaction never drops a month: its `monthly_window`
is `forever`, and a year it packs keeps every row, so turning it live moves
none of their dates.

## The prerendered seed carries the window, and no more

The server used to concatenate every committed month and inline all of it, so the
console document grew for as long as the pipeline ran - a reader downloaded four
months to look at thirty days, and would have downloaded a year by next summer.
It reads only the window it is handed now: the widest preset, which ends on the
newest published day as every other console window does, so the read and the
windows cannot disagree.

Measured 2026-08-26 on one Windows dev machine, against four months of real row
volume - the committed August shard (2,000 rows, 171 KB) plus three copies of it
shifted back a month each, 8,000 rows in all:

| | Raw HTML | Gzipped | Rows from the three older months |
| --- | --- | --- | --- |
| Before | 3,461,576 | 600,925 | 6,000 |
| After | 2,252,783 | 490,912 | 0 |

That is 18% off the gzipped document and 35% off the raw one, and the saving
grows with every month committed. One build per case; a prerender is
deterministic, and a control pair that the window could not affect differed by 7
gzipped bytes, which is the noise floor here.

**On a corpus shorter than the window it changes nothing.** The defect is one of
growth, and it was measured before it arrived rather than after.

Two consequences worth stating, because both are the reason this is safe:

- **Nothing became unreachable.** The monthly shards are untouched. Panning back
 fetches `telemetry/<YYYY-MM>.csv` exactly as it always did, so the dropped days
 are one arrow key away rather than gone. That fetch path already existed and
 was dead code: with every month in the seed, there was never a month left to
 fetch.
- **The read ends on the newest published day, never on the build clock.**
 Anchored on the build clock, a pipeline that stopped last month would draw an
 empty console - the page would go blank precisely when the pipeline broke,
 which is when an operator needs it. Run back from the projection's own newest
 row instead, a projection holding a day after the newest published day cuts
 the oldest day off the widest window.

The read is bounded too. A window is a count of days, so it straddles month
boundaries and opens one shard for each month it touches - four at most for a
90-day window. Every other shard is skipped unopened, however many the
repository has accumulated (`CLAUDE.md` Guardrail #12).

## Design rationale

**Every window ends on the newest published day, not on a record's own rows.**
The owner ruled this on 2026-10-05. Each route used to end its windows on the
newest day in whatever rows it held, so a record that stopped writing kept its
last rows on screen and moved its window into the past, and two records on one
route could end on different days. Three other days were weighed and refused:
the build's UTC day (a build that runs before the day's digest ends every window
on a day with nothing published), each record's newest rows (the past-moving
window above), and the newest day packing can have reached (it is not the
current day, and the packing delay differs by ledger).

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

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) - the strip and the band this control sits under.
- [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) - the panels that follow the window's length rather than a pan.
- [who-supplied-the-day-and-which-feeds-failed.md](who-supplied-the-day-and-which-feeds-failed.md) - the three Voices surfaces in the table above.
- [telemetry-series.md](telemetry-series.md) - the monthly shards a widened window fetches.
- [retention.md](retention.md) - the prune that shortens the marker list.
