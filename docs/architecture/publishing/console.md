# Published Console

**Last Updated**: 2026-09-10

The operator's surface: which panel is on which route, the question each one
answers, and the ruling behind its shape. `/console/` tells the owner what
happened to the pipeline, where the digest tells a reader what happened in the
world.

**A rule about how any figure may read is not here.** This page says what a
named panel is; [../../concepts/console-design.md](../../concepts/console-design.md)
says how a figure on it may be worded, ranked, tinted and drawn. That is the
same axis run in both directions, and it is what keeps four console pages from
becoming four opinions.

| Page | Owns |
| --- | --- |
| this page | the inventory: which panel, on which route, answering what |
| [../../concepts/console-design.md](../../concepts/console-design.md) | the presentation rule: wording, colour, ranking, empty states |
| [console-payloads.md](console-payloads.md) | the wire: what a browser may fetch, and the trust boundary |
| [telemetry-series.md](telemetry-series.md) | the grain: what a figure was measured over |

It is instrumentation: it takes no ornament and spends no reader attention, and
what it owes instead is legibility - a figure readable at a glance, a table that
fits the screen it is on, and a page that can be scanned in one pass
([../../concepts/vision.md](../../concepts/vision.md)).

## The console answers "is it working", in one screen

`/console/` is the operator's surface. The digest tells a reader what happened in the world; the console tells the owner what happened to the pipeline. It is instrumentation: it takes no ornament and spends no reader attention, and what it owes instead is legibility - a figure readable at a glance, a table that fits the screen it is on, and a page that can be scanned in one pass ([../../concepts/vision.md](../../concepts/vision.md)).

`/evals/` remains a published entry point for old bookmarks. It carries a
prerendered meta refresh, a canonical link and a plain link to `/console/`.
GitHub Pages cannot serve a SvelteKit server redirect, so the redirect must be
static HTML. A reader with JavaScript disabled still receives a page and can use
the link.

## The console is three routes, and the strip is real anchors

Since 2026-08-30 the operator surface is three prerendered routes, drawn as a
tab strip:

| Path | Label | What it answers |
| --- | --- | --- |
| `/console/` | **Pipelines** | Did the runs work, which feeds broke, and what each stage cost. |
| `/console/model/` | **Summaries** | What the model wrote, how long it took, and what it got wrong. |
| `/console/machine/` | **Hardware** | The hardware the model ran on, and how much it varied between runs. |

`/console/` keeps its path. It is the one an operator types and the one every
existing bookmark points at, so moving it to `/console/pipelines/` would have
cost a redirect and bought a symmetry nobody asked for.

**Two of the three labels changed on 2026-08-31 and no address moved with
them.** `Model` became **Summaries**, because every panel on that route is about
a published summary - its length, its cost, how long it took, what the checker
doubted - and none is about the model as an artefact. `Machine` became
**Hardware**, which is the plainest word for a processor, a memory, a clock and
a context window; `Runner` was refused because it is a term the build system
uses on itself rather than a term for a reader (`CLAUDE.md` section 0b), and
`Model` was refused for the middle route because it would put that word on the
page about the box rather than the page about the output. The route ids stay
`pipelines` / `model` / `machine`, every `href` is unchanged, and the three
`page_weight.ceilings_bytes` keys are unchanged - a label is not an address.
[../../../frontend/tests/console-title.spec.ts](../../../frontend/tests/console-title.spec.ts)
asserts both halves in one file. Authority: owner, 2026-08-31.

**Every panel title on the three routes is a noun phrase**, and that rule is
mechanical so it can be checked: no trailing question mark, and no opening
auxiliary verb. `Did the runs finish?` became `Runs that finished`, `Do the two
clocks agree` became `The two clocks, compared`, `Is the tail growing` became
`How the tail moved`, and `Did the model change move anything` became `What the
model change moved`. `What one more article costs` was already the form and is
the model for it. A question title asks the reader to hold it while he reads the
panel; a noun phrase names what is in front of him. `What`, `Which` and `How`
stay legal openings, because they head a free relative rather than a question.
Authority: Editor, 2026-08-31.

`Model` and `Machine` shared a first letter, which was the recorded cost of the
old name set; `Summaries` and `Hardware` do not, so that cost is paid off.
`What the model did` survives verbatim as the h2 on the Summaries route - it is
protected copy, and [../../../frontend/tests/console-model.spec.ts](../../../frontend/tests/console-model.spec.ts)
holds all eleven of its labels byte for byte.

**Routes, not tabs, and the JavaScript-disabled gate is why.** A tab strip that
switches with script shows one panel set and no way to reach the others when the
script does not run, and every panel it hides still ships inside the one
document. Three routes with real anchors pass both, and each one can be weighed
on its own. Tabs keyed on a query string cannot prerender at all; tabs keyed on
a hash stop find-in-page at the hidden panels.

**Every label carries its own worst state**, computed at build time from the
committed ledger - `Machine - shards read 4.31x apart`, not `Machine`.
Without it a route is where a metric goes to die: nobody opens a page to find
out whether it was worth opening. Machine's candidates are a run the counters
reader refused, a shard that committed no row, and the newest run's read spread.
The spread is reported at the lowest rank on purpose: nobody has agreed how far
apart two shards of one run may read before it is a problem, so ranking it any
higher would publish a threshold this project has not taken.

**The strip never takes the health ramp.** The one thing that differs between
routes is a 3px rule under the active label, from the categorical ramp. Green,
amber and red on a label would say a route is failing, and a route is a noun.
[../../../frontend/tests/console-nav.spec.ts](../../../frontend/tests/console-nav.spec.ts)
reads the computed style of every tab and fails on any of the six verdict
tokens.

**Identity is otherwise identical across the three** - type scale, space scale,
radius, elevation, frame width, both ramps. The shapes they share live in
[../../../frontend/src/styles/app.css](../../../frontend/src/styles/app.css)
rather than in three scoped `<style>` blocks, because three copies are three
identities that happen to agree today.

## The standing band carries three things, and the strip is above it

The order down the page is title, strip, band, window control, content. Chrome
above content is the one ordering a reader never has to learn, and the band's
worst fact links into the strip - which on a phone used to sit 337px BELOW it,
where a reader had already scrolled past. The control comes last of the three
because a control read before any fact asks the operator to configure a page he
has been told nothing about, and because it governs everything under it and
nothing over it. Authority: Susan, 2026-08-31.

The band's three facts: yesterday's verdict as a sentence with one square per
run of that day, the one worst thing and what it costs, and site size against
the 1 GB limit with the articles the headroom buys. The pipeline derives it once
and publishes it as `console/band.json`; the console fetches it once in
[../../../frontend/src/routes/console/+layout.ts](../../../frontend/src/routes/console/+layout.ts)
and draws it once in
[../../../frontend/src/routes/console/+layout.svelte](../../../frontend/src/routes/console/+layout.svelte),
above all three route panels, so they cannot disagree about which route is
worst. It was derived in the browser build until 2026-09-09; see
[console-payloads.md](console-payloads.md).

**The band was 340px on a desktop and 586px on a phone - 69 percent of an 844px
viewport - measured 2026-09-01 at bf37eeef.** Three changes pay for that: the
control moved out, the site-size fact dropped from about sixty words to one
line, and the page subtitle went from all three routes. The subtitle repeated
what the active tab's own description says 150px lower and cost 25px on every
route.

**The site-size fact is one line: the level, the limit and the articles the
headroom buys.** The rate it divides by, the days it was measured over and the
clause about which tree the cap measures live on `What one more article costs`,
which already owns the rate, its n and its spread - a band that repeated them
spent sixty of its hundred words on a caveat, and `idhazh site-weight` and
`committed payload tree` are not reader strings anywhere now.

**The worst-thing fact says what the state costs, and the strip keeps the short
form.** `15 feeds resting` on a label becomes `15 feeds are resting, so nothing
they carry reaches the digest. Each is asked again after 5 runs.` in the band.
The retry count comes from `availability_strikes_before_rest` and never from a
literal.
The two said the same words until 2026-08-31, 337px apart on a phone. Nothing in
the sentence invents a task: quarantine is self-terminating, so what it asks is
that the operator knows the digest is short of sources until the retry
([../sources/health.md](../sources/health.md)).

**A resting feed no longer outranks a failed run on a tie.** Both rank BROKEN
and the sort is stable, so listing the feeds first handed every tie to the state
that clears itself after five skips. The run candidates are pushed first.

**The verdict fact draws one small square per run of the newest day**, on the
same `--fill-*` ramp and the same shape as `Run health` 800px below, capped at
twelve then `+N`. It says what the sentence cannot: whether one run ate all 34
failures or all five limped. It is hand-written markup, so it is on the page
before any script runs, and every square names its verdict in words.

None of the three is **windowed**, and that is the difference between the band
and the per-article cost panel on Pipelines. The band stands on every route, so
a figure that moved when a control on one route moved would read as three
different sites. The runway is taken over every published day on record.

The window control sits **below** the band, in a container of its own. Inside it
it was a control in a panel it does not govern - the band is deliberately not
windowed - and it cost 125px of the first viewport on a desktop and 195px on a
phone for four tiles and a sentence. Its
tiles and its status line share one row now where the column is wide enough for
both. Each route hands its own control the same props: Pipelines prices the
month files a wider window would fetch, and Summaries and Hardware fetch nothing
and price nothing. All three read the same `idhazh:console-window` key, so a
span picked on Pipelines is the span Hardware opens on and the other way round -
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts)
drives it both ways in one browser session, because a route that writes the key
and never reads it passes a one-way check.

**Machine joined the window on 2026-08-31, and until then it was the one route
without a control.** It printed a sentence naming the fixed span instead, on the
argument that a control which answers a click by changing nothing is worse than
an absent one. What that cost is the question the console exists for: an
operator who narrowed Pipelines to 7 days to look at a bad afternoon lost the
span the moment he asked what the machine had been doing, and two charts on two
spans cannot be compared. The route is also the one whose numbers move most
between runs, so it is the one where "over how long" matters most.
Authority: owner, 2026-08-31; Fowler concurs.

**Every span the control offers is answered on the server, one small object per
preset.** The browser holds no ledger - a token total, a cache share and a
recording note all read rows this page never receives - so it cannot
re-aggregate a window the way the Pipelines viewport can. Four small objects is
the price, and it is bounded: the widest preset is the widest anything on the
route can reach, so a run older than 90 days is carried at no span at all and
the page does not grow with the ledger. That is the same rule Model's per-preset
distributions follow, and the alternative was inlining every counter row so the
browser could re-bin it. Authority: Carmack, 2026-08-31.

**A panel about one run does not follow the window.** The shard board, the
reading-against-writing split, the clock check and the latency curves read the
newest run or the newest day the ledger holds, at every preset. A window is a
span and a snapshot is not something a span can narrow - a board that emptied at
7 days would say the run had stopped existing. The page states this once, above
the snapshots, and names the run they are about. Authority: Jony, 2026-08-31.

**One snapshot reads its own ledger, and often a different run.** The span
breakdown reads `state/span-rollup/` rather than the counters, and the span
record started later than the counters did, so the newest run it can draw is
often not the newest run the counters hold. It names the run it found instead of
borrowing the counters' newest, so the two are never silently conflated.

Seven surfaces on Hardware declare `data-windowed`, and each one prints the day
count in its own words: the run count at the top, the prompt cache, context
headroom, the host panel's three spans, the latency plots, tokens per run and
the cost panel. The refused-run list follows the window without declaring it,
because a clean span renders nothing at all and a surface that comes and goes
cannot report a day count.

## What the Hardware route draws

Twelve panels. Eleven read `state/runtime-counters.csv` and `state/item-health/`;
one - where a shard's clock went - reads `state/span-rollup/`. All three are read
at build time under `$lib/server/` and none is published: the route added no
telemetry column and no reader sees a cell of any of them.

| Panel | Grain | The sentence it is for |
| --- | --- | --- |
| Shards of the newest run | one row a shard | Was the day slow because of the work or because of the machine. |
| Where a shard's clock went | one bar a shard | How much of a shard's time went to items, and how much to overhead nobody named. |
| Peak memory, and how near the runner's ceiling it got | one bar a shard | How much of the runner's 16 GB one run needed. |
| Reading against writing | the newest run | What a written token costs against a read one. |
| Prompt cache | one column a day | Whether a bigger cache would save wall clock. |
| Context headroom | one mark a run | Whether raising the truncation cap is even possible. |
| The two clocks, compared | one bar a shard | Whether the day's rates can be trusted at all. || The host under the newest run | the newest run | Which processors it drew, how busy they were, and how long the weights took to open. |
| How the tail moved | one plot a percentile, one mark a run | Whether the slow end of a run is moving. |
| How long the newest run's tail was | the newest run | What the whole distribution of one run looks like at once. |
| Tokens per run | one bar a run, twice | How much the model read and how much it wrote. |
| What this would have cost somewhere else | the whole span | Whether the runner time was a good trade. |

**The shard is the unit, and that is the whole point of the route.** Measured on
the committed ledger on 2026-08-31, the fastest shard of run `2026-08-30-5` read
its prompts at 41.98 prompt tokens a second and the slowest at 9.73 - the same
run, the same day, **4.31x apart** - and the two slow shards took 62 and 78
percent longer to finish. A per-run average reports neither end of that, and it
is the average every throughput figure this project had quoted until this page.

**Reading and writing are never one bar, anywhere.** Read speed varies more than
4x inside a run on this ledger and write speed barely moves, so a single "model
seconds" figure averages two different machines together.

**The span breakdown draws where a shard's clock went, and the residual is the
point.** Each shard's wall clock is `item.total_ms` - the time inside its items -
plus `unattributed_ms`, the overhead outside every item that no span covers, and
the fold commits the second on the item row so the two reconcile exactly. The
panel draws that split per shard: the four sub-steps no ledger column times, the
rest of the item work, and the overhead drawn hollow on the right - beside the
stages rather than buried in them. It carries no threshold and no tint, because
nobody has agreed how much overhead is too much and a colour would publish an
alarm that does not exist. The record starts 2026-09-06, the day tracing went on
across the pipeline; before it a run timed its stages but did not commit them, so
the committed rollup is empty and the real page shows a named empty state that
says so.
[../../../frontend/tests/console-machine-spans.spec.ts](../../../frontend/tests/console-machine-spans.spec.ts)
re-derives the drawn residual straight from the committed rollup cell and holds
it against the number the page drew, and reaches the empty state through a rollup
truncated to its header. The reader is
[../../../frontend/src/lib/server/span-rollup.ts](../../../frontend/src/lib/server/span-rollup.ts),
and the fixture rollup the canary draws is written in
[../../../frontend/scripts/build-canary.mjs](../../../frontend/scripts/build-canary.mjs).

**The board is five columns on a desktop and one card a shard at 1024px and
under.** The column head is the only thing naming a value, so when the columns
go the names have to go into the cells - a heading that exists only on a desktop
is a value with no name on a phone. What the cards replaced was a two-column
fallback holding five children, which pushed the read rate and the job clock
into the 3rem shard column: measured 2026-09-01 at 360px on the build before the
change, `1 h 28 m` was drawn over four lines in a 20px box, one character to a
line, and `of the 150-minute timeout - 59 percent` took six lines in 41px. Every
value the desktop shows the phone shows;
[../../../frontend/tests/console-machine-data.spec.ts](../../../frontend/tests/console-machine-data.spec.ts)
compares the two sets rather than trusting the layout, and holds every string to
at least twelve characters a line. Dropping a column on a phone was refused: the
board is five facts about one shard, and an instrument that answers four
questions on a phone and five on a desktop is two instruments. So was a
horizontal scroll, which hides the job clock - the column an operator opens the
page for. Authority: Jony and Susan, 2026-08-31.

**The card is an edge, not a fill.** Every quiet line in a row is
`--color-text-tertiary`, which reads 4.72:1 on `--color-surface` and 4.26:1 on
`--color-surface-raised`, so lifting the card would put four strings under 4.5:1
in the dark theme to buy a tint. Both bars in a row are drawn on
`--color-surface-sunken`, so a sunken card would erase them instead.

**A run whose rows cannot be made into one run is named on the page.** The
reader refuses a run where one shard index committed two different scrapes -
two workflow runs computed the same run id and `merge=union` concatenated both -
and the route prints the run id and the reason rather than quietly excluding it
from a count nobody can then check. Both halves of that cause are closed on the
writer's side since 2026-08-31 and the committed file was settled with them, so
today no run is refused; the guard stays because a reader of a committed ledger
cannot assume the run that wrote it was made by today's pipeline.

**The cost panel is a counterfactual and never a bill**, and it is the one place
on this site a figure in currency appears. CLAUDE.md Rule #10 carries the
owner's carve-out for it; the condition is that the page prints the rate it used
and says whether that rate came from `config/idhazh.json` or from the operator.
The operator's pair is kept in `localStorage` and read on mount only, so the
first paint always matches the prerendered document, and every cost figure on
the page is derived from one shared value rather than from four copies that
could drift.

### Context headroom is one chart with a limit rule

**Thirteen near-identical bars, each with two lines of prose, is a table
pretending to be a chart.** The panel used to draw one target bar a run, so a
question about a trend - is headroom moving toward the ceiling - had to be
answered by reading thirteen numbers in a row. Since 2026-09-01 it is one chart:
runs across the x-axis oldest first, the longest sequence on the y, the context
window as a rule, and spare capacity as a second series. Authority: Susan,
2026-08-31.

**The window is a rule, not a bar.** A limit is a line a series approaches. A bar
beside a bar invites a reader to compare two lengths and forget which of them is
the ceiling, and the browser oracle checks the geometry rather than the
attribute: every mark must sit at or below the rule, because no run can exceed
the window it was given. Authority: Jony.

**Spare capacity is dotted, because it is derived.** It is the window minus the
measurement and not a second reading of anything, so the stroke says so.
Measured on the committed ledger 2026-09-01 over 18 readable runs, the longest
sequence ran 4,120 to 7,186 tokens of the configured 8,192 - so the worst run in
the window used 88 percent of the window, and the panel's answer to "can the
truncation cap go up" was no. It was yes on 2026-09-09, when the window went to
16,384 and the same 7,186-token worst run became 44 percent of it. The cap
doubled to 10,000 that day and the panel's answer is no again, at a worst case
of about 86 percent. That is the panel working: it is the one surface that says
when the lever is free and when it is spent.

**The panel is about the worst run in the span, not the newest**, which is why
it stays windowed and why every run in the span keeps a mark. Drawing only the
newest run was refused for that reason. Authority: Carmack.

**One mark a run means the x-axis columns are runs, not days**, and a day can
carry several runs. Two consequences follow. `dayTicks` still owns the thinning
and the anchoring, but a repeated day is labelled once and the tick mark stays -
two identical dates side by side read as a chart that lost its order. And the
model-change rule falls on the FIRST run of a changed day, so one change draws
one rule; without that, a day with three runs would say the pipeline changed
three times.

**Every run's own three numbers stay on the page**, in a screen-reader list
under the chart. The chart is the shape of the question; the list is the table it
was made from, and nothing on this route is only in a picture.

### Peak memory is a maximum, and never a sum

**Shards are separate jobs on separate hosts.** Adding four of them reports a
machine that never existed, and on this ledger the sum would read about 53 GB on
a runner that has 16. So the run's figure is the LARGEST of its shards, the
per-shard bars sit beside it, and the oracle in
[../../../frontend/tests/console-machine-data.spec.ts](../../../frontend/tests/console-machine-data.spec.ts)
asserts the aggregate is the maximum and is not the total. Authority: Carmack,
2026-08-31.

**The 16 GB runner is the rule the marks are read against**, and every bar runs
to the same track so their lengths compare. Measured 2026-09-01 over the 11
committed runs that carry the cell, the high-water mark is **14,155,517,952 B -
13.18 GiB, 82 percent of the runner** - on shard 1 of run
`2026-08-31-33448379177`. **That is llama-server's resident-set high-water mark,
and it is neither the job's total nor the memory the machine had free.** The
python beside the server is not in it, and a resident-set mark counts mapped
weight pages the kernel can evict. So the panel says which shard ran nearest the
track, and nothing more. What decides whether a bigger model fits is free
memory, and the run of 2026-09-09 is the first to measure it: `MemAvailable`
bottomed out at 6.84 GiB
([MemAvailable went up by 1.21 GiB](../../reference/measurements.md#memavailable-went-up-by-121-gib-and-the-runner-is-why)).

**No tint and no band.** Nobody has agreed how near 16 GB is too near, and a
colour would publish a threshold that does not exist. Authority: Susan.

**An unmeasured shard is left out and counted, never drawn as zero.**
`peak_rss_bytes` landed on 2026-08-30, so a shard older than that reports
nothing: measured 2026-09-01, 44 of the 76 committed rows carry it. The panel
draws the shards that reported and names how many of the run's shards those
were.

**The polarity is declared at the measure, not at the paint site.**
`MEMORY_POLARITY` sits beside `RUNNER_MEMORY_BYTES` in
`frontend/src/lib/charts/machine.ts`, so a bar and a delta drawn from the same
figure on two panels cannot disagree about which direction is good.

### Three cross-boundary carries, one sentence each

Each route ends its introduction with one sentence pointing at a panel another
route owns: Pipelines says what the model spent of the day it just described,
Model says how far apart the day's runs read, Machine says how many articles the
day published. No chart, no card - a signpost that looks like a figure gets read
as one. They exist because the failure mode of splitting a page is a route that
hides the panel explaining another route's numbers.

### The run strip is a time axis, and a day nothing ran is drawn

The pipeline has written `state/runtime-counters.csv` since 2026-08-26 and no
page has ever read a cell of it. The route exists before its panels do, and says
what is missing once at the top and once per named panel. A route that hid
itself until it had data would be a route nobody knew to check - which is
exactly how a ledger goes four days unread.

**The run strip is a time axis: one column per day of the window, oldest on the
left.** Days advance left to right the way every other time series does, so "it
broke on Tuesday and has been amber since" is a shape rather than a sentence.
Each day is a track that grows with the room the strip has, floored at 16px with
a 4px gap, and a label may never widen a track - two days apart must measure
twice one day apart, whatever the date under it says.

**A column with no square is a day nothing ran, and it is drawn.** Until
2026-09-01 the strip drew one column per day a manifest exists for, so at the
default thirty-day window over the committed ledger it drew eleven columns:
measured 2026-09-01 at 1440 on Intel Core i7-1265U, Windows 11, node 24.12.0,
**464px of a 1,326px frame - 35.0 percent**, with the other 862px empty on the
right. That reads as a chart that failed to load. The window's own calendar
draws thirty columns at 1,290px, **97.3 percent**, and the gaps in it are the
fact this panel is the only place to see: a day the schedule dropped.

**`CELL_MAX` was not what left the margin, and the plan row that ordered this
said it was.** The ceiling is 34px and the frame offers 35.4px a column at thirty
days, so the cap costs 30px of 1,326 - two percent, not sixty-five. The column
count was the whole of it. The ceiling stays at 34, which is the size a fortnight
wants; a narrower preset still cannot fill a page-wide frame at any cell size a
run square should have, and that is what the centring rule below is for.

**Within a day, runs rise from a shared baseline.** Run 1 sits on the ground and
later runs stack upward, so every column starts from the same line and a busy
day is visibly taller than a quiet one. The DOM still reads run 1 first: the
order is reversed by layout, not by markup, so a screen reader gets the day in
the order it happened.

**Only a run that wrote a manifest gets a square.** A scheduled run that never
started left no evidence, and an empty slot would claim knowledge of a schedule
the payload does not carry. Drawing missed runs needs a persisted schedule or
attempt contract first; until one exists, the strip says what happened and
nothing about what should have.

**Dates are a separate, sparse row.** One day gets one full date. Two to six
days get one compact span (`18-20 Aug 2026`). Seven or more get a full date at
each end and as many between them as `dayTicks` measures room for. The year is
printed on the first label that changes it and not again. The arithmetic lives in
[frontend/src/lib/charts/run-history.ts](../../../frontend/src/lib/charts/run-history.ts)
so it can be tested without a browser. Eleven narrow columns had room for four
labels; thirty have room for the cadence the axis was written for.

**A day is read through the shared readout strip, not through a `title`.** The
only way to read a square was a native tooltip until 2026-09-01, and a native
tooltip needs a hover - so on a phone the run's verdict did not exist - takes no
styling, and prints one square where a reader wants the day. The strip below the
plot prints every run of the hovered day, each with the swatch it is drawn in
and the word for what it did, and the arrow keys step through the days. The
`title` and the `aria-label` stay on each square, because nothing the readout
reports may be needed to read the chart
([../../concepts/design-system.md](../../concepts/design-system.md)).

**The standing key went with it.** The readout prints the swatch and the verdict
for the run it is on, so a key beside it drew the same pair a second time - and
one fact drawn twice is how two of them drift. The rule the key's red entry
carried, `failed, or under N% published`, is a rule and not a legend, so it is
in the panel's note where the rest of the reading instructions are.

**A strip that cannot fill its frame is centred in it.** Until 2026-09-01 it
started at the left edge and the spare room piled up on the right - and the
right of a time axis whose last column is today is where a reader looks for the
days that just happened, so the room read as a run that had stopped. That was
the right answer while the strip drew only the days that carried a run, because
then the right-hand room really was "days not yet published"; with the window's
calendar drawn, the last column is today and there is nothing to the right of it.
`centreOffset` returns zero once the strip overflows, because a scrolling strip
has no spare room to divide and an offset would push its first column out of
reach. At the default window the strip fills, so the rule is only visible at the
7- and 14-day presets.

**Centring it exposed a gap `cellFor` had been counting and the strip never
draws.** `StripMetrics.width` was `days * (cell + gap)`, which includes a gap
after the last column that is never painted. Nothing read the number until the
spare room had to be halved, and then it put one whole gap more on the right
than on the left - 8 px of 1,326 at a 34 px cell, measured 2026-09-01, which is
a quarter of a column. `denseCellFor` beside it already counted the honest way
and said why in a comment. The same width scales the readout's marks, so the
correction also moved a pointer halfway along the strip onto the column it is
actually over.

**Where an overflowing strip OPENS is a different question, and it is the one
`console.today_anchor` answers.** The two were one line of layout for a while
and they are not the same fact: the anchor is a scroll position, and the
alignment above is where the columns sit inside a frame that is wider than they
are. The strip is a native horizontal scroll region - focusable, labelled, and
pannable with the arrow keys, with no buttons and no chart dependency.
JavaScript sets the initial scroll to the newest edge once, on the first
animation frame after mount, and never again: after that the position belongs to
the operator.

**The strip is a panel, and it follows the page's window.** It draws the days
inside the span the window control holds, states that span in its own note and
in its accessible label, and carries `data-windowed="run-health"` like every
other windowed section. A window that reaches no run says so in its own sentence
rather than showing an empty grid, and that sentence is not the one an empty
ledger gets - "no run recorded a manifest in the last N days" and "no run has
recorded a manifest yet" are different facts.

Three colours, and the boundaries are read from config rather than chosen by the page:

| Colour | When |
| --- | --- |
| Green | The run completed, nothing failed, and the source list was current |
| Amber | Something is worth a look: an item failed, the run did not complete, the source list was stale, or nothing was attempted |
| Red | The run failed, or its success rate fell below `run.success_floor_pct` |

**The red threshold is the same knob CI uses to decide whether a run opens an issue.** A red square and an open issue can never disagree, because there is one number and both read it.

**The squares are painted from the fill ramp, not the confidence ramp.** A 16px
solid is not type, and until 2026-08-30 it was painted in colours that are:
measured against the panel's surface, `--band-medium` is 5.43:1 and `--band-low`
6.12:1, which is text weight, and on screen they read as olive and brick. The
band tokens stay text colours because four other surfaces read them as type;
`--fill-high`, `--fill-medium` and `--fill-low` are the parallel set, and
[../../concepts/design-system.md](../../concepts/design-system.md) owns the band
a fill value has to land in.

**A skipped item is not a failure.** An article already published, or one a feed repeated, is skipped by design, so the rate is over what was *attempted*. Counting skips would paint a healthy day amber for doing its job.

Beneath the strip, the section leads with its own denominator: **how many feeds did not fail, out of how many the pipeline read, over how many runs** - 152 of 179 across 44 runs, measured 2026-09-03. Four broken feeds out of eight is a collapse and four out of two hundred is a Tuesday, and until this landed the page drew both identically. The clean feeds are NAMED behind a `<details>`, alphabetically, with no bars and no order, and the summary says why there is no order: a feed is read once a run, so every clean feed has the same record. Under `console.min_attempts_for_rate` runs the sentence prints the same counts and says the record is too shallow to read as reliability - two runs deep, "did not fail" means "did not fail twice". The rule is `reliability()` in `frontend/src/lib/feed-health.ts`, reading the same `failing()` the quarantine reads ([../sources/health.md](../sources/health.md)).

**The sentence names its span, since 2026-09-09, because it never had one.** It said feeds "have never failed", and the read behind it is `feedResults(shardMonths(widest))` - the newest five month shards, which is what the widest window preset can reach and no further. "Never" claimed every run there has been over a read that opens a bounded set of files, so the page was making a claim only a growing read could support (`CLAUDE.md` Rule #12, owner decision 2026-09-08). It now says the feeds "did not fail a read in these 44 runs", with the count from the record rather than a literal. The windowed sentence is also the more useful one: a feed that broke once in August and has answered every run since is permanently disqualified by "never failed", and the question on the desk is whether anything is broken now. `tests/console-window-claims.spec.ts` holds it - it reads the three built console documents, strips scripts and every attribute but `aria-label`, and refuses a claim in the present perfect.

**What that guard does not catch, said out loud.** It bans a grammar, not a word: "has never failed" and "has ever reached" place a claim in an unbounded past, while "runs are never pooled" and "a counterfactual, never a bill" state rules and read over no span at all. Measured on the canary build 2026-09-09, the three console documents carry **42 remaining uses of `never` or `ever`, and every one is a rule, a domain term or a statement about named items** - 24 of them are the cell `Never checked:`, which is one of the checker's five reason names. A word list would have fired on all 42. A bare past tense - "the feeds that never failed" - makes the same claim as the perfect and is not matched, because the only pattern that would catch it is a list of verbs, and that list fires on "the part the machine never read" two sections up the same page. Those strings are held by review and by the assertions in `console.spec.ts`.

**A refusal is not an ask, and until 2026-09-03 it was.** A row that preserves the strike streak - a rest, or a robots answer - never asked the feed whether it still works, so it can make the feed neither clean nor broken. The old rule dropped only the rests, so a source the pipeline has been refused by on every single run sat in the clean count and the page reported it as reliable delivery. Measured over the committed ledger that day, **5 feeds of 184** were in that state and every one had given the digest nothing: `anthropic-engineering`, `anthropic-research`, `axios-business`, `cbc-world`, `cnbc-top`. They are now a third count with their own disclosure, and the predicate that decides it is `preserves` - the same one the strike rule runs on, so an ask means one thing in both places. The section's own explanatory paragraph already said "a feed nobody has asked is in neither count"; the code was what disagreed with it.

## Four facts about every source we may ask

Above the failure list sits the census the list needs: **one row per state, per fact, over the addresses a curator has left active**. Permission, reading, retirement and the publishing record, and no cell combines two of them. It is drawn from `frontend/public/source-health.json`, which the run writes once a day, and the page renders that decision rather than making a second one ([../sources/health.md](../sources/health.md)).

- **A table of states, not a chart.** Four categorical facts over 144 addresses, most of them in one state, is a tally - and a tally is a table. Every state is drawn whether or not it is empty, because a census that hides its empty states is a sample. The oracle asserts the drawn counts sum to the census, so a state that stopped being drawn cannot pass as a state nothing is in.
- **Every state says what it withholds while it holds.** `denied` withholds that source until a later run reads its rules, `unreachable` means the address is not asked at all, a rest withholds it until the probe, and a retirement withholds that address until its configured URL changes. A count with no cost beside it is a number nobody can weigh.
- **Then the sources held back, loudest state first.** Retirement and a refusal come before a rest, because a rest lifts itself and neither of those does. Capped at `console.source_rows`, with the tail in one sentence, exactly as the failure list is.
- **The curated title is not unique, so the row carries the id too.** Two feeds in this repository are both titled `Anthropic`, and the thing an operator edits is one configured address. The title alone drew two identical rows.
- **The publishing record is counts and never a rate while the record is short.** `collect.source_yield_min_complete_days` is 30 and the ledger is nine complete days deep, so the sentence prints what was offered, what was published and what a source lost, and says in the same breath that this is too short to read as a rate.
- **It does not follow the window control.** Permission, reading and retirement are read over the whole record, and the publishing record has a fixed span of its own. It declares no `data-windowed` surface for that reason, and its own spec asserts the span instead.
- **Its population is smaller than the failure list's, and it says so.** The census counts the addresses a run may ask; the list below reads the whole ledger, tombstoned feeds included. Measured 2026-09-03, the 24 tombstoned sources in the item ledger were offered 560 addresses over the window and published none, so the smaller population loses no publication and stops the denominator counting sources nobody may ask.

**Nothing fetches it, so nothing stages it.** `frontend/public/source-health.json` is read at build time by `sourceHealthView()` in `frontend/src/lib/server/payload.ts` and never by a browser, so it is not copied into `frontend/static/` and `frontend/scripts/copy-visuals.mjs` is untouched. Its path is derived from `DIGEST_ROOT` the way `INDEX_ROOT` is, so a canary build reads the canary's own census.

**A missing or malformed view is a named absence, not a blank page.** The reader is the same guard `loadDay` uses - `null`, a list, and an object with no source list all parse cleanly and all three would reach the page as a section rendering nothing - and a view that cannot be read costs one section and logs one line.

Then comes **every feed that failed at least once, nearest to a rest first**, capped at `console.feed_rows` with the remainder in one sentence. A feed with a clean record is not in that list: the operator came here to find what is broken, and a list naming all 182 sources hides the 26 that are. The cap is applied on the server, because this list is inlined into the prerendered document and the rows it drops cost the page nothing; the list publishes `data-feeds-drawn` and `data-feeds-hidden` so an oracle can check that the cap counted what it dropped. The failing rule matches `FeedHealthRow.failing` in the contract exactly - a `200` that parsed to no entries counts as a failure, a `robots.txt` refusal does not ([../sources/health.md](../sources/health.md)).

**The count beside a feed is its run of failures, not its lifetime total.** The
pipeline rests a feed on failures in a row ending at the newest read, so that is
the number the page prints. A source that failed twelve times in July and
answered this morning is healthy, and a lifetime total printed beside a rest
marker is a number the pipeline never used to rest anything. The rule is
restated on the read side in `frontend/src/lib/feed-health.ts`, which runs the
same loop `discover.streak` runs, so a test can drive it with rows it made up.
Both read the same evidence as well: `feedResults()` settles the ledger to one
row per feed per run before any panel counts it, by the same rule
`discover.settled` uses, so a run a second attempt wrote down twice is one run
on the page and one run in the pipeline ([../sources/health.md](../sources/health.md)).
Ranking follows the same fact: nearest to a rest first, then by how much has
gone wrong in total, because a feed four failures into a five-failure rule is
one run from being dropped and a feed with more failures spread over a month is
not.

**Each feed carries a target bar and a strip of days.** The bar's track is
`collect.availability_strikes_before_rest`, its fill is the run of failures, and
its marker sits on the threshold - the same `TargetBar` the truncation cap and
the minutes-per-visual rule draw with. The strip is one square a day over the page's
window, oldest to newest, on a single date axis every row shares, so "broken
since Tuesday" and "flaky all month" cannot draw the same picture. It shrinks to
fit its row rather than scrolling, because twenty scroll regions in one column
is not a list. Every square carries its whole day's tally as a sentence: colour
is one signal and never the only one, and the two outcomes that are not a
verdict - a polite refusal and a day nobody asked - take no verdict colour at
all. The squares that do are painted from the **fill ramp**, the same three
tokens the run strip above uses, so the console holds one health ramp rather
than two: a square this small is a solid, and the band ramp is weighted to be
read as type.
`Last result` stays free text, because it is the only human-readable cause on
the page and is never traded for a glyph.

**The console reads committed records in two ways.** The run strip, feed list and
timing medians still read the ledgers at build time. The item-health viewport
fetches the browser-safe monthly projection under `telemetry/<YYYY-MM>.csv`.
Nothing under `state/` is ever served - the browser reads only the narrow
projection that drops `canonical_url`, `url_key` and `detail`
([telemetry-series.md](telemetry-series.md)).

Stage timing medians read from `state/item-health/<YYYY-MM>.csv`, not from
`state/scores.csv`. The item-health ledger has one row per planned item, so it
can answer "is it getting slower" even when the scorer did not run. The score
ledger still owns faithfulness and scorer time for the scored subset.

**The timing chart draws three stages, and `score_ms` is not one of them.** It
was a fourth line until 2026-08-31. The chart is titled `Time per item, by
stage`, so every line on it is something an item waits on - and the scorer reads
a summary the model has already finished, so nothing waits on it. A fourth line
there read as a fourth constraint on the run. It is on the Summaries route now,
under `What one summary cost`, beside the cost of writing the summary it checks,
and it prints its middle and its slowest one in twenty over the summaries it
timed. An empty cell is one fewer item timed, never a zero; a zero is the value
the column defaulted to before it was written, and it is counted as untimed for
the same reason. Authority: owner, 2026-08-31.

The viewport is a 30-day default window, not a retention policy. The window size
and where today sits are `console.default_window_days` and
`console.today_anchor`. Arrow keys pan, and `+` / `-` step the window to the
next preset, from a labelled focusable control with a visible focus ring; the
buttons beside it pan with a pointer. **Every console chart is drawn on the
server before any script runs** - most as hand-written SVG, the rest prerendered
by the engine and swapped for a live chart on mount - so the page is complete
with no script and stays complete if none arrives. If a telemetry month is
absent or cannot be parsed, that month is a gap in the charts. It is not
interpolated, and it never white-screens the console.

## One window governs the page

The window belongs to the page, not to the viewport, and one control at the top
of the console sets it. It is a set of radio buttons carrying
`console.window_presets` - five spans, all five on the page at once, so the cost
of the wide one is readable without opening a menu. A slider was rejected for
the same reason: every span is a different number of month files to fetch, and
the spans between these five cannot be told apart once drawn. The narrowest is
one day, added 2026-09-06 as the cheapest read the console can do.

Three rules keep the control honest and all three are in the contract, so a bad
config fails the build rather than the page:

- `default_window_days` is a member of `window_presets`, or the page opens on a
  window with every button unchecked.
- The presets are ascending and distinct.
- Every preset sits between `min_window_days` and `max_window_days`.

A window of N days is exactly N days, even when the ledger holds fewer. It used
to shrink to fit the rows it found, which was invisible while nothing on the
page named the span and a lie the moment a control does - a page reading 90 days
while the charts draw 2 cannot be trusted about anything else. Empty calendar
space is the honest answer to "there is nothing there".

**Widening fetches, and the control prices it first.** A preset that reaches
into months not already in hand carries a `+2 months` label, and picking it
re-uses the same month-fetch path a pan uses rather than reloading the page, so
rows already paid for stay. The control shows a busy state while the files are
in the air. Narrowing costs nothing.

**The choice is kept in `localStorage` and read on mount, never during
prerender.** First paint is therefore always the window the server drew, so the
prerendered document and the control cannot disagree while the page hydrates.

Three surfaces do not simply follow the span, and each says so on the page:

| Surface | What it does | Why |
| --- | --- | --- |
| `Feeds that failed` | The count and its marker read every run on record; the strip of days beside them follows the span | A windowed recount would disagree with the resting the pipeline actually performed. Two numbers for one decision is the defect the run strip already avoids. The strip answers a different question - when it broke - and that one is only readable over a span. |
| `Sources we may ask, and what they yield` | Permission, reading and retirement read every run on record; the publishing record reads `collect.source_yield_min_complete_days` complete days | It renders the run's own decisions, and the run rests on the whole count. The publishing record has a fixed span because that span is also its readability bar - one question, one number. |
| `Site size` | Absolute number always; the delta and the runway are windowed | The size is a level and the operator wants today's whatever span he is reading. The delta and the runway are rates, and a rate has to say what it is over. |
| `Minutes per visual` | Prints `The rule reads 14 days. Widen the window to see it.` under 14 days | The retirement rule is stated over 14 days. A median of the wrong span is the same figure with a different meaning and nothing on the page to say which one is being read. |

**Known defect: two of those readers walk the whole score ledger and will lose
history when a shard is deleted.** `pipelineChanges`, which draws the model-change
markers on `/console/` and `/console/machine/`, and `scoredDays` with
`modelByDate` on `/console/model/`, all read every committed score row rather
than the window. That is deliberate - a change marker has to sit on the day it
happened, whatever span is being read - but `idhazh prune-state` archives and
deletes a score shard past `observability.scores_full_grain_months`, and the
archive carries cohort totals rather than dated rows. So from the first live
deletion those three lose the dates in the deleted month. **No number a reader
sees moves; a date list silently shortens.** Reported 2026-09-02 and left as it
is, because deletion is still in dry run. Before that switch is thrown, either
teach the readers to union the archive's cohort dates or say on the page how far
back the marker list reaches.

`Sources cut short most often` used to hard-code seven days. It follows the
control now, and the section prints its own denominator, which at seven days
runs as low as six articles. Its rows are aggregated once per preset at build
time - four sets of ten costs less than one fetch, and it keeps the section
working with no script at all. It follows the window's *length* rather than
where a pan leaves it, and the section says so: the days it reads always end on
the newest day the ledger holds.

`Visuals published` used to draw a smoothed line over a fixed fourteen days,
under a control reading thirty. It is one bar a day over the control's own
window now, and the count above the bars is that same window summed, so a
reader adding up the columns gets the number the card printed. Bars rather than
a line, because a count per day is a discrete quantity and a line between two
days claims a value for the hours in between that nobody counted. The strip is
markup rather than an engine drawing: it is complete before any script runs,
and it follows the control with one drawing instead of a server-drawn seed and
a client redraw that can disagree about the span. A window that published
nothing prints the count and no strip at all, because thirty bars of zero is an
empty plot area and a card is still a card without one.

**`Articles published` sits beside it, and it is the denominator.** Until
2026-09-01 the strip printed how many visuals were drawn and nothing said what
they were drawn for, so a reader could not tell a busy day from a
well-illustrated one - 185 visuals is most of a quiet fortnight and a rounding
error on one heavy day. The two cards read left to right as the fraction they
are, articles first, and each carries its own total for the window on screen.

**One function draws both strips, and each is drawn against its own busiest
day.** `publishedSkyline` takes the measure as an argument, so the two cannot
drift in the one property that makes the pair readable: both are one bar a day,
over the same window, at the same pitch, with the same left edges.
[frontend/tests/console-published.spec.ts](../../../frontend/tests/console-published.spec.ts)
asserts the two strips report the same `data-published-days`, which is the whole
of "they are on one window". Each strip normalises to its own peak rather than
to the larger series: articles run two orders of magnitude above visuals on the
committed ledger, so a shared scale would draw every visual bar as a hairline
and the smaller card would stop saying which of its own days were heavy.

**One chart with both series was refused.** Two axes invite a comparison of
slopes that means nothing, and one axis flattens the smaller series to nothing.
Authority: Jony, plan row #10.

The card was labelled `Charts published` until 2026-09-01. It counts visuals in
state `rendered`, the section above it is `Visuals drawn for articles` and the
table column is `Visuals published`, so the card was the last reader-facing
string on the page still calling a drawn thing a chart. Its label is also a test
selector, and the selector moved in the same commit.

The page intro carried two counts of rows on record until 2026-08-30 - scored
items, and item-health rows. Both only ever grow, so neither could indicate a
state, and nothing on the page or off it acted on either. They are gone, and
their server-side computation went with them in the same commit.

**The prerendered seed carries that same window, and no more.** The server used
to concatenate every committed month and inline all of it, so the console
document grew for as long as the pipeline ran - a reader downloaded four months
to look at thirty days, and would have downloaded a year by next summer. It now
reads `console.default_window_days` back from the newest day on record, which is
the window the viewport opens on, so the two cannot disagree.

Measured 2026-08-26 on one Windows dev machine, against four months of real row
volume - the committed August shard (2,000 rows, 171 KB) plus three copies of it
shifted back a month each, 8,000 rows in all:

| | Raw HTML | Gzipped | Rows from the three older months |
| --- | --- | --- | --- |
| Before | 3,461,576 | 600,925 | 6,000 |
| After | 2,252,783 | 490,912 | 0 |

That is 18% off the gzipped document and 35% off the raw one, and the saving
grows with every month committed. One build per arm; a prerender is
deterministic, and a control pair that the window could not affect differed by
7 gzipped bytes, which is the noise floor here.

**On the corpus committed today it changes nothing**, because that corpus is
two days long and a corpus shorter than the window is already inside it. The
defect was one of growth, and it was measured before it arrived rather than
after.

Two consequences worth stating, because both are the reason this is safe:

- **Nothing became unreachable.** The monthly shards are untouched. Panning back
  fetches `telemetry/<YYYY-MM>.csv` exactly as it always did, so the dropped
  days are one arrow key away rather than gone. That fetch path already existed
  and was dead code: with every month in the seed, there was never a month left
  to fetch.
- **The cutoff is anchored on the newest committed day, never on the build
  clock.** Anchored on today, a corpus that stopped last month would seed an
  empty console - the page would go blank precisely when the pipeline broke,
  which is when an operator needs it.

The read is bounded too. A window is a count of days, so it straddles a month
boundary and reads two shards at worst; every older shard is skipped unopened,
however many the repository has accumulated.

**Every chart draws through one coordinate frame, in CSS pixels.**
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
owns the width, the margin box and the two domain rules - linear, rounded
outward to numbers a reader can place, and anchored at zero only where the
mark's *length* carries the value; and log, snapped to whole decades. A mark
that encodes by position takes the padded domain instead, because a zero no run
was ever measured at is plot spent on nothing. The rounding is a default rather
than a law: a chart whose domain is already decided by something else turns it
off, because rounding a fixed domain outward moves every mark on the chart to
buy a tick label that reads the same either way. The log rule has one user since
2026-08-30 - the stage-timing y axis, drawing whole decades and the eight steps
between them. It had two until the compression scatter was replaced by a per-day
count, and a count of articles is linear. Which rule a chart takes is decided by
the extent it draws, and the
threshold is stated under stage timings below. The tick values come from `d3`
either way, which
is the part hand-rolling gets wrong. Before the frame, each chart chose its own
`viewBox` and let the browser fit it to the column, and a `viewBox` is a scale
factor rather than a unit. Measured
2026-08-25 at a 1057px window: the same `font-size="10"` came out 4.5px in the
three-up failure panel and 16.6px in the chart under it, and a `stroke-width` of
1 came out at 0.45px and 1.66px. One module means a chart cannot invent a fifth
convention.

A prerendered chart has no element to measure, so the server draws at
`console.chart_width` and the client redraws once it has measured the real
width. The knob is what keeps the prerendered chart honest: without a width
given to it, a server-rendered SVG has to pick an arbitrary one, and picking an
arbitrary one is the defect.

The arithmetic comes from `d3-scale` and `d3-array`, which compute and draw
nothing. This is not a chart library returning ([../../concepts/design-system.md](../../concepts/design-system.md)):
they own no element, no canvas and no theme, and no reader route imports either
one. `npm run bundle-gate` holds that true: its encoder check refuses any of the
three assist symbols on the first-load path, whatever pulled them there. The
same script also holds each prerendered page's HTML under a ceiling, and a
route earns one when somebody has priced its growth: `/404` and `/evals/` move
only when the source does, `/archive/` grows by one day link a published day,
and `/console/` grows with the item-telemetry rows inside the page's window. A
day page and the home page weigh whatever the day published, so they are
measured and reported and never failed - a ceiling on either would cap the news
rather than catch a regression
([../../concepts/config.md](../../concepts/config.md)).

The item-health viewport has three parts, in this order:

- **Failure rate against volume**: one chart. Per-day columns of the day's items, split by where each one stopped - finished, then fetch, extract and summarize failures in the categorical ramp - so the height of a column IS the volume. Each stage's failure share is a line on a right-hand axis **fixed at 0 to 100%**: scaled to the window's own maximum, a single day in view normalised its bar to itself, so a 12% rate and a 90% one both filled the panel. **Every rate is printed in type with its denominator in the same sentence** - `16% failed, 672 of the 4,273 that reached it.` - because an SVG `<title>` does not fire on touch and does not survive the screenshot an operator pastes into an issue. **A stage under `console.min_attempts_for_rate` prints its counts and no rate at all**, and its line breaks over any day that thin, because a share of four items is not a measurement. An empty window says so rather than drawing a column of zeroes, because a column of zeroes reads as a run that went badly.
- **Summary length against the length asked for**: one column a day, stacked three ways - inside the target band, short of it, past it - with the `summarize.bands` ladder printed as numbers beside the chart and the worst misses named underneath in a ranked list. Hand-written SVG in the categorical chart ramp, a word beside every swatch, and the counts carried on the column as `data-band-inside`, `data-band-short` and `data-band-long` so an oracle can add them up. It follows the shared window and declares itself `data-windowed="band-distance"`. It replaced a scatter of article length against summary length: the scatter placed every article in the browser, which is what made the console document 40 percent of its weight, and it answered "what does the corpus look like" where the operator's question is "how many missed, and by how much".
- **Why items failed**: a ledger of causes, then the sources those failures cost the most articles, then the rows behind a selected one. **A cause is a stage and a code**, ranked by count through `RankedList` - a bar in the cell, a markup sparkline of that cause's daily count, and breadth as `sources hit: 3 of 47`. **Breadth is the column that earns its width**: one source changing its markup and the extractor being broken carry the same count and a very different number of sources, and until this landed the two read identically. **Which source is the second ranking, and it is the one column of the item table nothing above it answered.** A cause says what broke and a source says where, and an operator acts on both. It is a second `RankedList` and no new chart type: 122 sources against an eight-stop ramp is not a stacked bar, and the question - which is biggest - is a ranking, which this console already draws as a list with an opinion. **The magnitude is ARTICLES, one per source per day**, the rule `compressionView` reads the same ledger by, so the two surfaces cannot disagree about how many articles a day held; the rows under it are one per stage per run, so counting rows would leave every bar in proportion and every number too big. **The denominator rides in the value** - `42 of 42 articles` is a source that stopped working and `42 of 500` is a bad afternoon, and the count alone cannot tell them apart. **No tint and no verdict on a source row**: per-source yield is not measurable until the ledger is thirty days deep ([../sources/health.md](../sources/health.md)), so a colour would publish a threshold nobody agreed. Capped at `console.source_rows` with the tail in one sentence - measured 2026-09-01 over the committed projection, a thirty-day window holds 60 sources with a loss and 778 lost articles, so the tail names 50 sources and 398 articles. The rows below are the detail, and they sit behind a shut `<details>`: still newest-first, which is the one shape on this page a date sort is right for, still **capped at `console.failure_list_max` with a `Show 25 more` button**, and still stating their own scope - `Showing 25 of 214 failed items in this window.` A code chip, a selected cause and a selected source all filter them, and they narrow together rather than replacing one another; picking a cause or a source opens the disclosure, because a filter whose result is behind a shut disclosure is a control with no visible effect; a new window, a new chip, a new cause or a new source resets the cap, because each is a new question. **The `Item` column is gone and `item_id` rides on the row's `title`**: it is a content address, it was the widest cell in the table, and no operator acts on one - the page-level grep it cost is a terminal job. Uncapped the list measured 7824px against 800 rows and put the compression chart at document y=9105. The section sits last for the same reason, and the disclosure is why the two rankings stay readable: the rows are the only child that can outgrow the screen. They survive verbatim rather than being deleted - the address in one is where troubleshooting a single URL starts, and a documented workflow begins there. **There is no cause text and none is invented** - the published projection withholds `detail` ([telemetry-series.md](telemetry-series.md)), which can carry fetched article text, so the code is everything the browser is given. **The stage is a word and not a mark.** The design asked for a monochrome stage glyph beside it and it is refused here: the icon set is one generated module that reaches every route, because a lookup on a dynamic key cannot be tree-shaken. Fifteen glyphs cost the routes 1,404 to 1,900 gzipped bytes (measured 2026-08-29, [../../concepts/design-system.md](../../concepts/design-system.md)), which is 94 to 127 bytes a glyph a route against a 64-byte ratchet tolerance, so three stage marks would move `/`, `/404`, `/<date>/`, `/<date>/<topic>/`, `/archive/` and `/evals/` - six reader routes that cannot show this section at all. The same page calls an icon that needs a caption a label wearing a costume, and the stage name is already in the cell.

Measured 2026-08-24 on the committed ledger: the console document went from
11552px to 4878px.

**A stage's denominator is what the stage before it let through, never the
day.** An item that died at fetch never reached extract, so counting it in
extract's denominator understates every stage after the first. The projection
carries the funnel already: one row per planned item per run, holding the stage
that item ended at, so `series.ts` walks the pipeline order once per day and
each stage's `reached` is the one before it minus that one's failures. A row
that never left `plan` is in the day and in no stage's denominator. Measured
2026-08-30 over the 4,273 rows of the committed projection: 672 items died at
fetch, 437 at extract and 19 at summarize, so extract reads 10.2 percent against
the day's 4,273 and 12.1 percent against the 3,601 that actually reached it, and
summarize reads 0.4 against 0.6. The three panels divided by the day and were
wrong about two stages of three.

**Three panels became one chart because a rate on its own cannot be acted on.**
A stage that failed both of the two items it was given drew the same full bar as
an outage, and the number that tells them apart - the denominator - was the one
number the panel did not print. Volume and rate are one question, so they are
one picture: the column says how much work there was and the line says how much
of it failed. The split also cost every panel its width: three charts side by
side measured 164px each in a 624px column, and `font-size="10"` reached the
screen at 4.5px in one of them (measured 2026-08-25). That 164px is the number
`console-frame.spec.ts` forbids, and the three-up row was the surface it was
written against - so the chart that replaces it is a `<figure>`, which is what
that check scans. Ruled by Susan (Craft and Delight) and Jony (UI/UX) on the
console signal review, 2026-08-30.

Two alternatives were rejected there. **Keeping three panels and adding
sparklines** leaves the split, which is the defect rather than the content
(Jony). **A single headline failure rate for the whole pipeline** hides which
stage failed, and which stage failed is the actionable half (Susan).

**The scatter was replaced on 2026-08-30, and what it cost is why.** It drew
article length against summary length on a log x axis: 2,740 marks in one colour
on a 1026px plot, measured that day. The dense middle rendered as a solid block,
which hid the outliers - the only marks on it anybody could act on - and reading
it meant taking two axes per mark to answer one question. The question is how far
a summary landed from the length the prompt asked for, so the distance is what
is drawn: at the widest preset that is 90 columns instead of one mark an article,
and the outliers are named rather than hunted for. Ruled by Susan (Craft and
Delight) with the owner on the measurement, 2026-08-30. The runner-up was a
density-binned scatter with only the outliers drawn individually; it was refused
because it keeps the two-axis reading the bar removes. Reducing the mark opacity
was refused for making a paler blob (Jony).

**Colour here is categorical, never the confidence ramp.** A summary outside its
band missed a length somebody chose in `config/`, and a policy limit is not a
verdict on the run - `TargetBar` draws the same line, lending the ramp only to a
threshold that is a health fact. Every swatch carries its word, so the three bins
are readable in a screenshot and in either theme.

**The bounds are printed as numbers beside the chart.** A shaded target zone with
no printed bound cannot be checked against what is drawn over it, which is what
the scatter asked a reader to do. The table prints one row a rung -
`under 60` / `30 to 45` - read off the ladder rather than off a rung, because a
rung records only the length it starts at and the last one has no ceiling at all.

**Three things went with the scatter, and none of them has a reader now.** The
dashed cap lines and their handover labels, which read `extract`'s cut off the
points in view; the diamond for an article the run cut short; and the pointer
readout, because a bar of counts has no mark to land on and its column already
carries a `<title>`. `capsInView`, `capLabel` and `seenWords` were deleted with
them. `CompressionPoint` keeps `source_seen_words` and `truncation_flagged`,
because `placeRow` still decides all three of its outcomes off the two lengths
and nothing else.

**A row the section cannot place is counted out loud.** The article length before
the cut is nullable - the pre-cap body is never persisted, so an older cut row
has no length to recover - and a row without one has no band. Measured over the
committed ledger 2026-08-29: 142 of 2,683 rows, 5.3 percent. The sentence under
the intro says how many, for whatever window is open, and the count comes from
the rows the server dropped rather than from a constant, so the sentence and the
columns answer out of one decision. A window that dropped nothing prints no
sentence at all. A section that drops articles without saying so under-reports
its own gaps.

**The oracle is that the split adds up.** `inside + short + long` equals the
day's own count of articles a band can be read for, recomputed in
[frontend/tests/console-compression.spec.ts](../../../frontend/tests/console-compression.spec.ts)
from the committed ladder and the canary's own projection rather than through the
page's reader. A split that does not add up is mis-binning articles, and the
picture would still look right. The canary was given one summary that runs past
its band on the same day - 260 words where the rung asks for 50 to 90 - because
every other row it writes lands inside or short, and a third state the fixture
cannot reach is a state an implementation can pass by never entering.

**Every chart with a shared column carries a pointer readout, and it is not an
SVG `<title>`.** It was two charts when the strip was written and seven of
twenty-four by 2026-08-30; it is the default on all three console routes from
2026-08-31, and a chart with no shared column now says so in
`data-readout-none` rather than by saying nothing.
Both are **never pinned to the pointer** - a readout under a thumb is a
readout nobody reads. One
Svelte action beside `observeWidth` drives it
([frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)):
`pointermove` and `pointerdown` on the `<svg>`, which is one stream covering
mouse, pen and touch, plus `focusin`, `keydown`, `pointerleave` and `focusout`.
The hit rule is nearest mark **by x**, from positions the chart already
computed. Only a mouse leaving clears the readout, because a touch raises
`pointerleave` the moment the thumb lifts and clearing there would blank the
numbers before they could be read.

The `<svg>` takes `tabindex="0"` and the marks take none: Left and Right step,
Home and End jump, Escape closes. A tab stop per data point is a trap rather
than access - the committed ledger draws 2,541 of them. The `<title>` elements
stay as each mark's accessible name and are never the publication: nothing a
readout alone can tell you is needed to read either chart, which is also the
whole no-JavaScript answer.

**The stage-timing chart takes one of the two, and it is a strip below the plot
rather than a box over it.** A floating box was measured on 2026-08-29 at 88 to
121px over a 220px plot - 40 to 55 percent of the chart it was explaining - so
this one is laid out under the plot where it cannot cover a mark at any width,
and `chart.readout_max_share` bounds it at a third of the plot so it cannot
become a paragraph beside a chart being glanced at. The run-health strip still
gets none - it has no per-day point to land on, and it says so where it is
drawn. `FailurePanels` gained one: it does print every stage's rate and its
denominator in type under the plot, but not per day, and the day is the column
the strip prints.

**That strip is the legend as well.** The legend already printed the newest day's
four numbers and a sentence under it said which day they were, which is the
readout's resting state written out longhand. One strip prints a date and four
values, opens on the newest day, and follows a pointer or an arrow key; the row
order is still fixed by the newest day, because a legend that re-sorts under the
eye as the pointer moves is a legend nobody can read. Nothing is hidden until a
pointer arrives, so the no-JavaScript answer is the page as it prerenders.

**The throughput candle's readout moved below its plot on 2026-08-30, and it is
no longer `caption()` verbatim.** It was a box over the plot carrying the
`<title>` sentence unchanged, on the rule that one day gets one sentence rather
than two. That box is the one measured above, and this strip is bounded by the
same `chart.readout_max_share`. `caption()` closes with a run list that grows
with the day's run count, so it is the one clause with no bound, and at a third
of the plot it wrapped to four lines per series. The strip is a `<dl>` printing
the day, then one row per series carrying the median and the extent - every
series at once, so comparing read against write costs no second hover. It rests
on the newest day rather than opening blank, so pointing at the chart never
changes the room it takes and never moves the marks under the pointer. The
`<title>` keeps every word, including the middle half the box already draws, and
the run count stays in the verdict line under the legend.

The strip's shape is not this chart's own. `dayTicks`, `dayColumnX`,
`readoutCapStyle` and `readoutMarks` in
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
hold the axis-thinning, the column arithmetic, the cap and the hover targets, so
the stage-timing trend directly above this one on the page and this chart cannot
drift apart. Two charts stacked on one page that hover differently cost the
operator a second guess.

**A window with nothing in it says so, rather than removing the chart.** Until
2026-08-30 the throughput trend rendered nothing at all when no day in the
window carried a measurement, while the stage-timing trend six inches above it
printed `We timed nothing in these 30 days`. Found 2026-08-30 by rebuilding the
console against an emptied item-health ledger: the page was intact and threw
nothing, and the chart had simply gone. A chart that vanishes beside one that
explains itself reads as a chart that broke. The heading now stays and one line
of type under it says the window is empty.

**The throughput axis names a day per column.** It shared the run strip's
sparse-label arithmetic until 2026-08-30, which printed the whole window as one
span string and no per-day label at all, so a spike could not be attributed to a
date. It now prints one date per plotted day through `dayTicks`,
thinned to what the plot has room for with both endpoints always kept, and the
span it used to print moved into the `<svg>`'s accessible name. Measured
2026-08-30 by building the canary console from either side of the change on one
machine in one session: 6 text nodes carrying 0 date labels before, 7 carrying 2
after, over a canary of two days. Five of those nodes are the y axis's own ticks
either way, so what moved is one span string becoming one date per column. A
dashed
vertical rule marks each boundary where the day's model differs from the day
before it, so a step in the trend is attributable to a swap rather than guessed
at; the model reaches the page through the prerendered HTML, from the same score
rows the model table reads, and no telemetry column was added to publish it. The
committed ledger holds one real swap - `qwen3-8b-q4-k-m` to 2026-08-26 and
`qwen3-5-9b-q4-k-m` from 2026-08-27 - and the published console draws exactly
one rule, on 2026-08-27, measured 2026-08-30 on a production build. The canary's
throughput days are older than the ledger's first row, so no day there names a
model and the rule cannot draw in the browser gate; the test says where it stops
rather than passing quietly on an absence.

**Stage timings are one trend chart, not a list per day.** Four polylines over a
calendar x axis, oldest on the left, with a mark at every point and a date under
every column the density allows. The old block was one group of four bars per
day - about 150 rows at a 30-day window, and no trend - and "is it getting
slower" is the only question the section is asked.

**The x axis prints a date per column, thinned to what fits.** It used
to print one string for the whole span - `24-29 Aug 2026`, measured on the built
page 2026-08-30 - which is the run strip's sparse-label arithmetic, and that
arithmetic is right for a strip of 16px squares and wrong for a 760px plot. Six
labels over thirty days puts every mark within three columns of a date; one
label over six days put a spike nowhere at all. The first and last day are always
among them, evenly spaced indices fill the rest, and the year is printed once and
then only where it changes. `chart.tick_density` is the ceiling on how many the
axis may carry and the measured fit takes more away where the plot is narrow, so
nothing overlaps at 390px; a column whose date was dropped keeps its tick mark.
`dayTicks` in
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
owns it, so the throughput candle beside it labels its axis the same way, and so
do the band columns, the failure panel, the run lengths and both run strips.
The rule and what it costs are in
[../../concepts/design-system.md](../../concepts/design-system.md).

**Every point on it carries a mark.** A filled dot is a measured time and an open
dot on the baseline is a measured zero; a day a stage was never timed on has
neither, and the note under the chart counts it. Before 2026-08-30 the chart drew
0 marks across 4 polylines, so there was nothing to aim a pointer at and nothing
for an arrow key to land on.

**Its columns are the window the operator set, not the days that carry a row.**
The chart used to build its own calendar from the first and last dated row it
held, so a control reading 30 days sat above a plot drawing 6. Two spans on one
page cannot be compared, which is the question the operator came for, and it is
the same defect the window control was built to remove - `windowOfDays` returns
exactly N days whatever the ledger holds, for the same reason. So the chart takes
the shared `TimeWindow` and draws `daysInWindow` of it; a day inside the window
with no row is a gap the notes already name, and a row outside the window is not
drawn. A window with no timings in it at all says so and offers the widening,
rather than drawing an empty frame.

**Its y axis is decades, and that is where the domain rule has its threshold.**
The padded, `.nice()`, non-zero-anchored linear domain above stands for series
of comparable size. **It yields to a decade-rounded log domain when the drawn
extent spans more than two decades.** Measured 2026-08-25 on the committed
ledger, one linear axis over these four gave `summarize` 78.1% of the plot
height, `score` 2.15%, `fetch` 0.38% and `extract` 0.03%: one stage set the
domain and the other three drew flat on the baseline. The same four values on
the decade axis are 81.4%, 50.2%, 35.2% and 12.9%, so a tenth added to `extract`
and a tenth added to `summarize` are the same vertical move and the axis
measures change at every size. The composition survives the change - `summarize`
still sits on top, `extract` still at the bottom, and the gap still reads as
about three decades - so one instrument answers both questions. Decade gridlines
run full width and are labelled, crossing from milliseconds to seconds at
1000 ms; the eight steps inside each decade are unlabelled stubs on the y axis
only, because 32 full-width rules is a hatch rather than an axis, and without
them a log axis reads as a linear one with odd numbers on it.

**A series is deleted when it carries no information, never when the axis is
failing to show the information it carries.** `extract` at 42 ms was worth
deleting from the linear chart, where it was a flat line at the bottom. That was
a fact about the axis, not about the stage: on the decade axis it gets the same
vertical resolution as `summarize`, so a 3x extractor regression - what a source
changing its markup looks like - is as visible as a 3x model regression, and
nothing else on the console carries that signal.

**Three facts about a missing number, three marks, and none of them a bare
zero.** All three used to arrive at this chart as the number `0`: a day nothing
timed, a day whose median really was zero, and a day timed for only some of its
items. Each day now arrives as a `StageTiming` - the median, how many items the
stage timed, and how many items there were - and each fact draws as itself:

- **Nothing timed** breaks the line, because "no number" and "no time spent" are
  different facts.
- **A measured zero** breaks the line too, and draws an open dot in the stage
  colour, centred on the baseline rule. It is never clamped into the bottom
  decade: a clamped point draws a plunge to the floor of the plot, which states
  that the stage got a thousand times faster. Zero has no position on a decade
  axis, and the baseline rule is the one place on that axis which is not a claim
  about size. A median of zero does not mean the stage took no time - it means
  it finished faster than a 1 ms clock can measure, which is an ordinary state
  for a cheap stage. `state/scores.csv` recorded exactly that for `score_ms` on
  all ten rows of 2026-08-22 - the reading that made the rule necessary, taken
  on a column that has since moved to the Summaries route.
- **A day timed in part** draws the items it timed, and the line under the chart
  says how many that was.

One line of type per stage names whichever of the three happened, because a hole
in a line is a mystery and three holes that look alike are worse than one: `We
timed no fetch work on 3 of the 30 days. The line breaks there.`, `extract took
under 1 ms per item on 1 day, which is faster than we can time. The open dot on
the baseline marks it.`, and `We timed 1,240 of the 1,480 items for extract on 2
days. The line is the items we timed.` A stage timed in full on every day of the
window has nothing to explain and gets no line at all.

**A stage the window never timed is stated once, in the legend**: the row greys
and prints `not timed` where a value would be. It used to be stated twice - the
legend printed `no data` and a paragraph under it printed the same absence in
longer words. The open dot gets no legend entry either; the line of type names
it, and a key would be a second thing to read for a mark that appears on a
handful of days a year. A run of one day draws a dot, so a stage that runs on
alternate days is drawn rather than absent. With no days at all the section is
one line.

**The legend prints the newest day's value per stage, sorted by that value,
descending.** The number an operator acts on is today's; a window median moves
when the operator pans, which is the same defect that rules out indexing each
stage to its own median. Sorting by the newest day makes vertical position a
second signal beside colour, for free, and it reorders only when two stages have
changed places - which is when the operator wants to notice. **Colour stays
bound to the stage and never to the rank**, so a reorder never repaints a line.
The chart gains no linear/log toggle: a toggle is an admission that we could not
decide which axis is correct.

**The counts ride on the payload rather than being reconstructed from the
value.** The chart used to rebuild "this is absent" from the number it was
handed, which is how the three facts collapsed in the first place: `median()`
returned `0` for an empty sample, and `score_ms` went through `Number(cell ?? 0)
|| 0`, which invented a zero sample point out of an empty cell rather than only
losing one. `sample()` is now the only way to build a `StageTiming`, and
`median()` takes one rather than a `number[]`, so a bare array of numbers - and
the fabricated zero that used to fill an empty cell - no longer type-checks.
`svelte-check` is the gate for that: `StageTimingDay` is a hand-written
prerender input, not a Pydantic contract and not a committed payload, so the
schema versioning in `CLAUDE.md` section 11 does not apply to it. Telling the
three apart cost the console route 509 B of gzipped first-load JavaScript, which
is 0.8 percent of it, measured 2026-08-27 against `origin/main`'s own source
built on the same tree and the same machine.

Authority: Jony, 2026-08-25; the three marks and the counts behind them, Jony
and Fowler, 2026-08-27.

## Why a summary was doubted, and the one ledger that can answer it

The Summaries route draws the five reasons a summary failed to reach the top
band, one column a day, over the window the page shares. The measure cards above
it say how often the checker stopped; this says what was wrong.

**It reads the committed day payloads, not `state/scores/`.** `band_reason` is
decided by `verdict()` and written onto the published item by
`assemble.build_day`. The score ledger's 35 columns carry the inputs a reason is
decided from - `hhem`, `coverage`, `unsupported_numbers`, `hedge_dropped` - and
the band, and no reason column at all. So the route walks `DIGEST_ROOT` the way
`publishedItems` already does for the Pipelines route, and what ships is one
count per reason per day rather than the payloads. Re-deriving the reason from
the ledger's inputs was refused: it puts a second copy of `verdict()` in a second
language, and the day the two disagree the console is wrong about the item a
reader was shown ([../../concepts/evaluation.md](../../concepts/evaluation.md)).

**The five are drawn apart and never added into one doubt count.** A single
number says how often the checker stopped and never says which fault to go and
fix. Each item carries at most one reason, so the five add up with nothing
counted twice - which is what makes the stack legal and what the oracle checks.

**Stacked, with a switch to lines.** The same array draws both with only `type`
and `stack` moving, which is the condition
[../../concepts/design-system.md](../../concepts/design-system.md) sets for that
control. Picking `Lines` reaches the live chart, not only the prerendered one. A
chart carries an explicit lifetime now - it hydrates, draws when a reader comes
within a screen of it, takes a changed option through `update()`, and is
destroyed once - and a small `$effect` in
[../../../frontend/src/lib/charts/Chart.svelte](../../../frontend/src/lib/charts/Chart.svelte)
hands the live chart each new option, so a control that moves the shape or the
window is followed without a rebuild.

**A reason with no items draws nothing, so the panel names it in a sentence.**
`not_scored` has never fired: it needs a missing faithfulness score, and the
scorer has run on every production item. A series that is zero everywhere is
dropped by `stacked()`, so without the sentence a reader cannot tell a fault that
never happened from one nobody looked for.

**The column total is the day's reason count, never its doubtful count**, and
the difference is printed. 369 doubtful summaries carry no reason, all of them on
the three days published before the field existed. A panel that folded them into
a band would draw a fault the checker never named; one that dropped them silently
would make three days look clean.

**It does not declare `data-windowed`.** The exact list of surfaces that do is an
oracle in
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts),
and that oracle is stronger for being exact. The panel honours the same control
and proves it in its own spec, by driving the control to each preset and reading
the control's own attribute back against the panel's.

**What it cost, measured 2026-09-05 on an Intel Core i7-1265U.** The panel adds
**5,557 gzipped bytes** to `/console/model/`: the median of five builds is 38,867
B against 33,310 B for `origin/main`'s own source built in place on the same tree
and the same machine. Five builds of the shipping tree spanned 15 B, so the 64 B
noise floor holds.

**The ceiling moved to 47,974 B, by the method that owns it.** Heaviest of five
builds (38,873 B), plus seven published days, plus the 64 B floor. A published
day now costs this route **1,291 gzipped bytes**, re-measured by removing
2026-08-31 - 601 articles, the heaviest committed day - from every ledger the
route reads and rebuilding: 38,866 B fell to 37,575 B. It was 1,179 B when the
ceiling was last re-derived on 2026-08-31, and the panel is what added the other
112 B a day. The page therefore ships with 9,101 B of slack, which is seven
published days and expires by design.

That is one of the three ceilings the plan that grew them re-records, done for
the one route this panel grew. `/console/` and `/console/machine/` are untouched
and their own re-derivation is still owed.

## Every instrument the checker writes, and the panel that owes it a number

The Summaries route draws three more panels: the faithfulness score, the lead
coverage, and a table of the six instruments nothing acts on. What matters more
than any of the three is the map they ship with.

**The artefact is `DRAWN_BY`, not the charts.**
[../../../frontend/src/lib/console/eval-instruments.ts](../../../frontend/src/lib/console/eval-instruments.ts)
assigns every measured column of `state/scores/` to exactly one panel, and
`NOT_A_MEASUREMENT` says of every remaining column why it is not one - fifteen
identity and provenance columns, each with a sentence. Between them the two must
name every property of
[../../../schemas/eval-row.schema.json](../../../schemas/eval-row.schema.json),
once, and name nothing else.
[../../../frontend/tests/console-model-instruments.spec.ts](../../../frontend/tests/console-model-instruments.spec.ts)
compares the two sets in the ninety-second gate. So a column added to `EvalRow`
next month fails a test rather than going undrawn, which is what happened here:
`hhem` and `coverage` were scored on every summary from the first published day
and read by nothing on the site for two weeks.

**The scope said two panels and the survey said six columns more.** Row 4 of
[../../../TODO/20260905-03-console-backfill-plan.md](../../../TODO/20260905-03-console-backfill-plan.md)
named faithfulness and lead coverage and stated the goal as *every* existing
instrument reaching the console. Counted 2026-09-06, ten of the ledger's twenty
measured columns had no reader anywhere in `frontend/src`. The two named ones got
their own panels; the other eight went to the third. Drawing two and calling the
goal met would have left the map failing its own test on the day it was written.

**`hhem_full` and `hhem_delta` are a sentence, not a second chart.** The checker
scores each summary twice, once against the text the machine was given and once
against the whole article, so a summary that only looks faithful because the
article was cut cannot pass. Measured 2026-09-06 over 6,966 rows the two readings
differ on **7 of them**, because production hands the same string to both - the
finding recorded in [../../concepts/evaluation.md](../../concepts/evaluation.md).
A chart of a number that is flat on 99.9 percent of rows teaches an operator to
stop looking; a sentence saying how often it parts, and by how much, is the same
fact at the size it is worth.

**Nothing sets a bar, and that is decision 2 of the row.** No threshold line, no
red, no band tint, no polarity - and the spec fails the build if a tinted element
appears inside either score panel. The committed window is fifteen days and the
summarizer is about to change twice, so a threshold taken off it would be a guess
wearing a measurement's clothes. The one number that *is* a bar - the configured
lead-coverage share - is printed as a count of summaries under it and never drawn
as a line to fail against, because it caps a summary at "fairly sure" and has
never on its own marked one "not sure".

**Two lines on faithfulness, one on lead coverage.** Measured 2026-09-06 over the
fifteen committed days, the middle summary's faithfulness sat between 88 and 95
percent while the lower quarter swung from 73 to 94 - so the level and the tail
are two different facts and both are drawn. Lead coverage does the opposite: the
middle summary sat between 57 and 64 percent every single day, so a line of it
beside a moving one would read as the important one. What moves there is the
share of a day that fell under the floor, and that is what is drawn; the level is
in the readout strip and the headline.

**Lines, and no shape switch on either.** One percentile added to another is not
a quantity, and neither is one day's share added to the next day's. The condition
[../../concepts/design-system.md](../../concepts/design-system.md) sets for
carrying that control is that both shapes read the same array honestly. Bars
here would not.

**A day is that day's middle summary, and the recorded table says so.** A median
over the whole window needs every summary's reading, and carrying 6,966 of them
into the page to print four figures is not a trade worth making. The table prints
the quietest day, the middle day and the loudest day, each by its own middle
summary, and names that in the panel rather than leaving a reader to assume a
window median.

**The two densities are drawn per thousand words, not per word.** Per word they
are 0.011 and 0.004 - two numbers a reader cannot tell apart, neither of which
reads as a quantity of anything. Per thousand words they are 11.0 and 4.0
markers, which is a count of phrases in about four pages.

**Neither new panel declares `data-windowed`**, for the reason the doubt-reason
panel does not, and each proves it honours the control in its own spec.

**The faithfulness plot fails a sufficiency check on purpose.** Its axis runs
from zero to a hundred, so the fifteen committed days sit in the top fifth of
the plot and four fifths of it is empty - which is
[../../concepts/design-system.md](../../concepts/design-system.md)'s first check,
does it use the space it is on, answered no. Cropping the axis to the data would
fill the plot and would also turn a four-point drift into a cliff. This panel
exists because a band could not show a four-point move; a plot that shows a
four-point move as a collapse is the same failure with the sign flipped. The
empty four fifths is what tells an operator the movement is small, and that is
worth more than the space. Recorded here rather than waved through, per
`CLAUDE.md` section 9.

**What it cost, measured 2026-09-06 on an Intel Core i7-1265U.** The three panels
add **5,930 gzipped bytes** to `/console/model/`: the median of five builds is
44,948 B against 39,018 B for `origin/main`'s own source built in place on the
same tree and the same machine. Five builds of the shipping tree spanned 11 B and
three of the control spanned 8 B, so the 64 B noise floor holds. `/console/` and
`/console/machine/` moved by 2 B and 4 B between the arms, which is the same
floor - the change reaches one route.

That control arm reads 39,018 B where 2026-09-05 recorded 38,867 B for the same
commit. The 151 B is a different machine, not a change: nothing between the two
dates touched this route's source or the ledgers it reads.

**The ceiling moved to 56,385 B, by the method that owns it.** Heaviest of five
builds (44,953 B), plus seven published days, plus the 64 B floor. A published
day now costs this route **1,624 gzipped bytes**, re-measured by the same method
as before - removing 2026-08-31, the heaviest committed day, from every ledger
the route reads and rebuilding: 44,948 B fell to 43,324 B. It was 1,291 B on
2026-09-05, and these three panels are what added the other 333 B a day: one
reduced day in the seed, two screen-reader rows, and two chart points. The page
ships with 11,437 B of slack, which is seven published days and expires by
design.

**Every ceiling in this section is superseded.** All three were re-derived on
2026-09-10 against the tree that moved the console's telemetry to a browser
fetch, on one convention - the heaviest of five builds plus a tenth, at `gzip
-5` - and `/console/` fell by a factor of 6.4. The per-published-day rates above
are the record of how this route grew while it inlined its telemetry, and they
are kept for that. The live numbers and the current method are in
[../../reference/measurements.md](../../reference/measurements.md#the-page-ceilings-re-aimed-at-the-migrated-tree-2026-09-10)
and what to do when one fires is in
[../../how-to/run-the-gates.md](../../how-to/run-the-gates.md).

## The model-change rule, and the charts it means something on

A dashed rule down a chart says one sentence: *everything left of this line was
written by a different setup*. That sentence is true of a chart of writing time
and false of a chart of feed outcomes, so the mark is a judgement about what the
chart measures and never a decoration applied everywhere. A marker that means
nothing on half the page teaches an operator to stop reading it, and that costs
the half where it did mean something.

**The boundary is a `pipeline_fingerprint` transition, never a `model_id` one.**
The stamp is a digest over every declared input that can move an output - the
weights, the quantisation, the llama.cpp build, the chat template, the prompt,
the output schema, the truncation cap, the decoding settings, and the extractor
and sanitizer versions
([../../../backend/idhazh/contracts/fingerprint.py](../../../backend/idhazh/contracts/fingerprint.py)).
Measured 2026-08-27 over 2,232 rows the stamp moved four times while every row
named one model, so a slug attributes a changed number to an unchanged pipeline;
[../../concepts/evaluation.md](../../concepts/evaluation.md) segments on the
stamp for the same reason.

**A day is a boundary when it ran a stamp the previous scored day did not run.**
A day that only stopped using one of yesterday's stamps started nothing, so it
is not one. A day carrying several stamps is one boundary, because a day is one
column and a change inside it cannot be placed any finer. Measured 2026-08-31
over the committed ledger - 3,884 rows, 10 scored days - that rule finds five
boundaries: 23, 24, 26, 27 and 29 August. Comparing only the previous day's last
stamp against this day's first would have found two, and would have called
2026-08-26 a single unchanged day while it ran three pipelines.

**Derived once on the server, over the whole ledger, and passed down.**
`pipelineChanges()` in `$lib/server/model-work` is the one derivation and
`/console/`'s load calls it; a component that derived its own would be deriving
it off its own day list, and two of them would eventually disagree about when it
happened. Over the whole ledger rather than the window, so a chart opening on
the day after a change still knows the change happened.

**The rule is dashed, in the neutral rule ink, and never on the health ramp.** A
pipeline change is an event, not a verdict. It sits on the leading edge of the
changed day rather than through its own marks, so a step in the trend either
lines up with it or does not. A change on the oldest drawn day draws nothing: it
would separate nothing from nothing, because every day on the chart ran the
setup that came out of it.

**Every chart says which bucket it is in, in markup.** A chart that draws
carries `data-model-rule="yes"`, its own drawn span as
`data-model-rule-from`/`-to`, and one `data-model-rule-line` per boundary inside
that span. A chart that does not carries `data-model-rule="no"` and the reason
in words in `data-model-rule-none`. The pair is the point: an absent rule and a
rule nobody remembered to draw look identical on a page, and only one of them is
an answer. Where a drawing chart's span holds no boundary it says so in type
(`data-model-rule-empty`) rather than leaving the reader to guess.

| Chart | Route | Draws | Why |
| --- | --- | --- | --- |
| Time per item, by stage | Pipelines | **yes** | `summarize` is the model writing, and `extract` moves with the extractor version the same stamp digests. |
| Summary length against the length asked for | Pipelines | **yes** | The length a summary comes out at is decided by the prompt and the model, and the stamp covers both. |
| What one more article costs | Pipelines | no | Bytes an article are what got published, not how it was written. |
| Feeds that failed | Pipelines | no | A feed answered or it did not, before any summary existed. |
| Sources we may ask | Pipelines | no | Permission, a rest and a retirement are all decided before a summary is written. |
| Charts drawn for articles | Pipelines | no | The chart arm is a different model call, judged on its own retirement rule. |
| Time to write one summary | Summaries | no | A change moves every bar on it. The axis is seconds, so the window is pooled into one distribution and a day has no position to draw at. |
| Prompt cache | Hardware | no | A change moves it - the prompt is in the stamp - and its engine-drawn axis carries no rule yet. |
| Context headroom | Hardware | no | One bar a run, so there is no day edge to draw between. |
| Tokens per run | Hardware | no | One bar a run, so there is no day edge to draw between. |

The last three are the honest edge of this rule and are recorded rather than
hidden: two of them are charts a change **does** move, and neither draws,
because the mechanism is a `<line>` in an SVG the component owns and neither
chart owns one. Rows #19, #20 and #21 of the console chart-craft plan rebuild
all three, and the rule lands with the chart it belongs to. `ThroughputTrend` on
Summaries has drawn its own version since 2026-08-30, off `model_id` rather than
the stamp; that is the precedent this rule was generalised from and it is not
yet a caller of it.

**The rule reaches the readout as well as the plot.** A boundary day prints one
extra line in the strip under the chart, so a reader stepping the days with an
arrow key meets the change without a pointer. Two charts, one string, from
`$lib/charts/frame` - two charts describing one event differently is how the two
descriptions drift.

The wording never says "the model changed", because the stamp moves for a
reworded prompt or a rebuilt runtime as readily as for new weights, and four of
the five stamps in the ledger cannot be expanded into their cause at all
(measured 2026-08-27). It says *a new model, prompt or setting started here*,
which is the set the stamp actually covers.

Authority: Andre (AI/LLM) on which measures a change moves, Fowler
(Architecture) on one server-side derivation, Jony (UI/UX) on the mark being
neutral ink; console chart-craft plan Row #3, 2026-08-31.

## What one item cost the model is two clocks, drawn apart

`What one item cost the model` is a section of the Pipelines route with two
distributions and one split bar. It answers what a run total cannot: how long
the model spent on **one** article, split into the part it spent reading and the
part it spent writing.

The Hardware route already pools both quantities per run and per shard, out of
the model server's own counters. That is a different measurement of a different
thing, and it cannot say that one item in nine got nothing from the prompt
cache. This section reads the published projection, per item, and follows the
window control.

### Reading and writing are two charts, and pooling them is refused

Measured 2026-09-05 over the 6,104 items of the committed projection that carry
both clocks: a prompt token costs about **101 milliseconds** to read and a
written token about **183** to write, so a written token costs **1.8 times** a
read one. The two also move for different reasons - the article's length moves
the first and the summary's length moves the second - so an operator acts on
them separately. One `model seconds` chart would hide which of the two moved.
Carmack, plan 03 Row #2 rejected alternative 1.

The panel prints both rates and the ratio, and then says the thing the ratio is
for: cutting a hundred tokens from the summary saves more time than cutting a
hundred from the article. The sentence is derived from the measured ratio rather
than written down, so it flips if the ratio ever does.

Both are drawn as **doubling bins**, by the same `distribution()` the Summaries
route's two clocks use. It moved to
[frontend/src/lib/charts/series.ts](../../../frontend/src/lib/charts/series.ts)
on 2026-09-05 so a route outside `$lib/server/` could reach it - four panels now
share one binning and one pair of rules, rather than four that can drift apart.

The axis is a doubling and not a linear one, and the ledger says why. Measured
2026-09-05, reading one prompt runs from **1.4 seconds to 692**, which is nine
doublings; on a linear axis every bar but one is a hairline against the left
edge. Writing is the opposite shape and is drawn the same way on purpose:
**4,456 of 6,104** items land in one bin, 32 to 64 seconds, and drawing it
linearly would suggest a spread the measurement does not have. `fetch_ms`, whose
worst is 43,627 ms against a middle of 567, is not in this section at all - it is
a stage clock and `Time per item, by stage` above already draws it per day.

### The prompt cache is a share, and the share is deliberately not a trend

The split bar's geometry is **absolute prompt tokens** - the ones the model read
against the ones it did not - and the share is printed beside it as whole
percent. Four figures sit under it: the middle prompt, the middle summary, the
middle item's own share, and how many items were read whole with nothing held
over.

**A falling share here does not mean the cache got worse, and the panel says
so.** Measured 2026-09-05 over the same 6,104 items, `cached_tokens` is nearly a
constant: the middle item kept **922** tokens and the widest kept **941**, while
`input_tokens` runs from a middle of 1,688 to a worst of 7,093. So the share
moves almost entirely because the denominator moves. Drawn as a line over time
it would fall on a week of long articles and read as a cache regression, which is
the one wrong thing an operator could act on. The share is a number and the token
counts are the picture.

**The plan's own illustrative range did not survive the measurement.** Plan 03
Row #2 decision 1 quotes `0.72 to 0.90`. Measured over the committed projection
the per-item share has a middle of **0.518**, a 5th percentile of **0.000** and a
95th of **0.820** - and **667 of 6,104** items reused nothing at all. The
decision itself stands: the share is drawn, and it is named in words beside it.

### Every denominator is its own, because three of them differ

An item that failed before the model saw it has no clock and no token count; one
that failed before the fetch has no stage clock either. Measured 2026-09-05 over
the committed projection: **8,300** rows in all, **6,873** with a stage clock and
**6,104** with the model's own two. One "items" figure would be wrong for at
least one column of this section whichever row set it counted, so each figure
carries the count it answers for and the lead states the widest one.

An empty cell stays empty. A mean that treats an absent instrument as a zero
turns every fetch failure into a fetch that was infinitely fast, and zero reuse
is a real answer that has to stay counted - which is why `readWhole` is a count
and not an exclusion.

### It follows the window's length, not a pan

The reduction is taken on the server, once per entry in
`console.window_presets`, and the browser picks the open one - the same
arrangement `Sources cut short most often` and the Summaries route's
distributions use.

**That is a measured choice, not a preference.** The prerendered seed carries the
eight columns as nulls, because seeded with their real values they cost
`/console/` **176,753 gzipped bytes** - 198,624 to 375,377, and 98,182 over the
recorded ceiling (measured 2026-09-05, recorded in
[telemetry-series.md](telemetry-series.md)). The two alternatives the seed note
offered were to seed the columns this section draws, or to drop the seeded months
from `loadedMonths` and let a runtime fetch fill them. Both were refused: the
first buys the ceiling problem the seed note was written to avoid, and the second
puts a 244 KB fetch behind the first click of a control and leaves the section
blank until it lands. Reducing on the server costs the page about a hundred
numbers a preset and draws complete before any script runs.

What it costs is stated on the page: panning does not move these days, and they
always end on the newest day the ledger holds. The section says so in the same
words `Sources cut short most often` does, because one rule stated two ways reads
as two rules.

Authority: Carmack (Engine & Runtime) on the two clocks and the axis, Fowler
(Architecture) on one binning shared by four panels, Reader on the sentence
beside the share; plan 03 Row #2, 2026-09-05.

## The chart arm is a flow, and every drop leaves it as a named branch

`Visuals drawn for articles` opens with one diagram of where items go between the
visual planner reaching one and a visual reaching a page. It is drawn left to
right, the direction the page reads and the order the pipeline runs its stages
in, and it totals the whole open window rather than one day - a single day's four
numbers are already legible in the table under it, and "where do items go" is a
question about the window.

**It was a funnel until 2026-08-30, and a funnel could not answer the question
it was on the page for.** A funnel draws a monotonic sequence as a taper, so it
says how much is left at each step and nothing about where the rest went. The
three drops here have three different causes and three different fixes: an item
can be answered without the model being asked at all, the model can be asked and
draw nothing, and a drafted chart can fail the checks that run after it. A taper
shows all three as one slope. Every loss now leaves the flow as its own branch,
labelled `Answered without a visual`, `The model drew nothing` and `Did not
survive the checks`, and the branch is as wide as the number of items in it.

**The widths conserve, and that is asserted rather than assumed.** What leaves a
stage is what arrived at it: the branch that carries on plus the branch that was
lost. `frontend/tests/charts.spec.ts` recomputes the four stage totals from the
fixture and checks every node against them, so a layout that drew a plausible
shape from the wrong numbers fails. A flow whose widths do not conserve is
drawing a picture, not the data.

**A branch of zero is not drawn.** A stage that lost nothing has no loss to
show, and a zero-width branch with a label beside it reads as a loss too small
to see rather than as no loss at all.

**A window that gains items prints a sentence instead of a diagram.** The four
counts are not guaranteed to fall: a chart published inside the window can have
been drafted before the window opened, and the committed ledger holds exactly
that - 2026-08-25 recorded 23 drafted and 27 published. Over a whole window the
totals came back monotonic (2,121 reached, 1,425 asked, 144 drafted, 124
published on 2026-08-30), but a narrower window need not, and the drop would be
negative. The diagram steps aside and says which stage gained, because a
negative branch cannot be drawn and a clamped one would be a lie about the
count. The table below it still holds the numbers. Zero reached is the other
empty state and keeps its own sentence, so the two nothings are never one blank
panel.

**Colour is the categorical ramp, and a loss keeps the hue of the stage it
left.** Every fill comes from `PALETTE` through the sentinel bridge, so both
themes resolve with no JavaScript at all; a loss branch is the same hue at 0.28
opacity against the flow's 0.55. A second hue would say a loss is a different
kind of thing, and it is the same items going a different way. Both opacities
are low because a label to the right of a node sits over the links leaving it,
which is unavoidable in a flow this shape - the label has to stay readable
across them.

**Every label sits outside its node, on two lines, carrying the count and the
share of everything reached.** The narrowest node on the committed ledger is
under three pixels tall, so a label inside it would be unreadable - the defect
the funnel already had to fix once. Three measurements set the geometry, all
taken in the browser on 2026-08-30:

- **Two lines, not one.** `Answered without a chart  696  (33%)` ran 280px into
  a 246px column pitch and printed over the next stage's label. Split, the
  widest line is the name alone.
- **The right margin is 170 pixels, not a share of the width.** A label does not
  shrink with the frame, so a percentage leaves too little on a narrow screen -
  the first arm reserved 30 percent and still clipped `Did not survive the
  checks`, which measures 151px at 12px type.
- **The node gap is 34 pixels, against the engine's default of 14.** `Published`
  and `Did not survive the checks` are 13.8px and 2.2px tall over the committed
  ledger, so at 14px their two-line labels shared nine pixels of one line. A
  two-line label is 31px and the gap has to carry it.

`depth` is set on every node rather than inferred, because an inferred layout
justifies dead ends to the far edge - it would draw the first stage's loss
beside the last stage's.

**What it cost, measured 2026-08-30 on one Windows dev machine, node 24, after
merging `origin/main`, with main's own source built on this same tree first and
this branch second.** The lazy chart chunk went from 191,889 to 197,561 gzipped
bytes, **5,672 bytes for the Sankey layout**, and registering `SankeyChart` in
place of `FunnelChart` is the whole of it. Both arms read byte-identical on
every build, so the spread is zero and the difference is the change. That leaves
**2,439 bytes under the 200,000-byte line** the console plan draws, which is 1.2
percent - the next chart type registered will cross it, and the answer then is
to measure what the current set costs before adding to it. First-load JavaScript
on `/console/` went from 76,727 to 77,343, **616 bytes**, which is the option
builder growing; the engine is still a lazy chunk nothing preloads. The
console's prerendered HTML went from 162,225 to 163,089 gzipped bytes, **864
bytes** for three more nodes and seven two-line labels, and against the 301,580
ceiling that leaves 138,491 spare - 0.29 percent of the ceiling spent.

**The recorded chunk size was already wrong before this landed, and by more than
this change costs.** `docs/concepts/design-system.md` carried 153,204 B from
2026-08-29, when only the funnel, the tooltip and the SVG renderer were
registered. The six figures added since brought bar, line, pie, grid, legend and
mark-line with them and nobody re-measured, so the record sat 38,685 B - 25
percent - under the truth. The number is corrected there in this commit, and the
lesson is the one `core.ts` already states: the registration list is a file
somebody has to edit, and re-measuring it is the reason it is. (The legend came
back out on 2026-08-31, when the readout strip became every chart's key: 5,532 B
gzipped, re-measured in the same commit.)

Authority: the shape, Jony, 2026-08-30; the chunk, Carmack, 2026-08-30.

## The chart arm is judged against its own rule, and the daily rows come second

`Visuals drawn for articles` is the only console section carrying a written
decision rule in its own prose: over a stated span the arm is retired if the
median day spends more than a set number of minutes per published visual, or
puts a visual on fewer than a set share of the items it published. Until
2026-08-30 the section printed that rule in a paragraph and then showed none of
the three numbers in it. Seven columns of daily counts sat where the answer
should have been, and the operator was asked to take a fourteen-day median of a
ratio, twice, against two limits that were nowhere on the screen.

The section leads with the two figures the rule names. Each is a `TargetBar` -
the track at the threshold's own scale, the fill at the window median, a rule
drawn at the threshold - with a `Sparkline` under it, because `4.2 and falling`
and `4.2 and rising` are different pictures and a single number is neither. One
sentence above them states both figures and which side of its threshold each
fell on.

**The sentence and the two bars are one computation.** `chartArm` in
[frontend/src/lib/charts/glance.ts](../../../frontend/src/lib/charts/glance.ts)
returns the medians, both bars' geometry, both trends and the sentence together,
and the browser suite asserts the printed sentence is byte-identical to the one
the module builds. A verdict written in the template could say `inside` while
the bar beside it drew a fill past its marker, and nothing on the page would
look wrong.

**All three numbers are config.** `console.chart_arm_rule_days`,
`console.chart_arm_minutes_target` and `console.chart_arm_coverage_pct` live in
`config/appearance.json`, bounded by `ConsoleConfig`. They were constants in a
TypeScript module until 2026-08-30, which made the one section that states a
threshold the one section an operator could not move a threshold on (Rule #6).
The contract also refuses a preset list whose widest span cannot reach
`chart_arm_rule_days`: a rule no preset can show would print the
widen-the-window notice at every setting of the control, which reads as a broken
surface rather than as a narrow window.

**Coverage divides by what the day published, and a day that published nothing
has no share at all.** The denominator is the item count on the day's own
`digest.json`, read in the same pass that counts its charts, so no new telemetry
column was published to answer this. A quiet day returns null rather than zero
percent: zero would say the arm ran and reached nobody, and nineteen quiet days
would drag the median of a healthy fortnight onto the floor. This is the
null-is-not-zero rule the timing medians already follow
([../../concepts/design-system.md](../../concepts/design-system.md)).

**Neither bar takes the health ramp.** These are limits somebody chose, not a
verdict on the machine, so `TargetBar` draws them in its `policy` tone. The
marker carries the fact. Tinting a policy threshold green would invent a health
judgement nobody agreed to, which is the same mistake as a chart borrowing the
band tokens.

**Below the rule's own span the section prints the notice and no number.** The
window control governs the medians, and under `chart_arm_rule_days` the section
says `The rule reads 14 days. Widen the window to see it.` and draws no bar. It
is the same sentence and the same reason as the glance card next to it: a median
of the wrong span is the same figure with a different meaning, and nothing on
the page would say which one is being read. The section carries
`data-windowed="chart-arm"` and states its span in words at every setting, so
the window oracle in `frontend/tests/console-window.spec.ts` holds it to the
control like every other windowed surface.

**The seven daily columns are behind a native `<details>`, not a button.** The
console is complete before any script runs and stays complete if none does, so a
button plus a conditional block would leave the rows permanently unreachable
with JavaScript off - the rows would be gone rather than on demand. A disclosure
is keyboard-reachable for free and says which state it is in without a second
label. `Reached`, `Asked the model`, `Visuals drafted` and raw `Minutes spent`
moved down with the table: the flow diagram above already draws the first three
as branches, and the minutes on their own are the numerator of the ratio rather
than a decision. Nothing was deleted, and the table gained the `Items published`
column that coverage divides by, so the share and its denominator sit on one
row.

**What it cost, measured 2026-08-30 on one Windows dev machine, node 24, with
six sibling agents on the box, with main's own source built first on this same
tree and this branch built four times after it.** First-load JavaScript on
`/console/` went from 80,843 to 82,761, 82,758, 82,761 and 82,755 gzipped bytes:
**1,915 B for the section**, which is 2.4 percent of the route, and 6 B of
spread over the four treatment builds. The control arm is the six routes this
row does not touch - `/`, `/404`, `/<date>/`, `/<date>/<topic>/`, `/archive/`
and `/evals/` moved -4 to -12 B between the arms, every one of them inside the
64-byte tolerance against its committed record, so the delta on the console is
the change and not the toolchain. **No chart type was registered**, so the lazy
engine chunk did not move at all: 197,961 gzipped bytes in both arms, against
the 200,000 the console plan draws. The prerendered console document went from
179,776 to 180,653 gzipped bytes, **877 bytes** for two bars, two trends, one
extra table column over twenty rows and a summary element, and against the
301,580 ceiling that leaves 120,927 spare - 0.29 percent of the ceiling spent.

Authority: the two bars and the verdict, Susan, 2026-08-30; the disclosure
element, Jony, 2026-08-30.

### Both daily tables follow the window, and shut they are not cards

The Pipelines table and the Summaries table are the two `<details>` on the
console that hold a row per day. Until 2026-08-31 neither followed the control
above it: the cards on Summaries said 7 days while the rows under them held
every day either ledger ever wrote, and on Pipelines the rule's own medians were
taken over the window while the table below them was not. Two answers to one
question on one page is exactly what a shared control was built to remove.

Both are windowed now, and both take one name, byte-identical at the same
preset: **Show these figures day by day, over these N days.** `Show the daily
figures` was refused because "figures" names nothing on a page that is nothing
but figures. The day count is on the line that opens the table, so an operator
knows what he is opening before he opens it.

**Neither table is deleted, and the Pipelines one was the closer call.** Most of
what it holds is already drawn above it - the flow covers reached, asked,
drafted and published, and two target bars with their sparklines cover the
minutes and the coverage. Only `Items published` is uncharted. It stays as the
per-DAY reading of a window-level picture: it is the only place a printed rate
can be checked against the two counts it was divided from, and the only way to
attribute a window aggregate to a day. Authority: Susan, 2026-08-31.

**On Pipelines it ends `[data-windowed="chart-arm"]` rather than hanging below
it.** It answers the section above it, and a table that has to be found is a
table nobody reads. On Summaries the placement was already right, so only the
chrome, the name and the span changed.

**Shut, a disclosure drops its border, its background, its shadow and its
padding.** Closed it is one line of link text, and a bordered, shadowed, rounded
card around it gave a footnote the visual weight of a section - which is what
made it read as something hanging off the bottom of the page rather than as the
last line of the section above. Open it takes the frame back, because then it
holds a table. The rule is `.console-disclosure:not([open])` in
[../../../frontend/src/styles/app.css](../../../frontend/src/styles/app.css), and
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts)
reads the computed values either side - an eye cannot check a box-shadow.
Authority: Susan, 2026-08-31.

The Summaries table declares `data-windowed="daily-figures"`, so the window
oracle holds it to the control like every other windowed surface. The Pipelines
one declares nothing of its own: it sits inside `chart-arm`, which already
declares the span and prints it in words.

## What the cap costs, and the four places the console says it

The truncation cap is the one setting on this project that silently removes
words a reader might have got. Five figures answer five different questions
about it, and each one is on the surface that already owns its grain.

| Figure | Where | Grain | Read from |
| --- | --- | --- | --- |
| `Article read only in part` | the model table | one day | `state/scores.csv` |
| `Read only in part, as a percent` | the model table | one day | `state/scores.csv` |
| `Time to write one`, second figure | the model table | one day | `state/item-health/` |
| `Too long to send` | the model table | one day | `state/item-health/` |
| `n read only in part` | the run square's own label | one run | `state/item-health/` |
| `Sources cut short most often` | its own range plot | one source, the open window | `state/item-health/` |

**The run grain is a clause on a label and never a published figure.** Measured
2026-08-29 over the 19 committed runs, the count is 1 to 12 articles of 160 to
200 - 0.6 to 7.5 percent - and that swing is which articles the feeds carried
that hour. Drawn as a number beside the others it would read as the cap moving
when nothing about the cap moved. A run square is where run-level facts already
live, so it goes there and stops.

**The day grain divides by the rows its own flag answers for.**
`truncation_flagged` changed meaning at `CUT_FLAG_MEANS_A_CUT_FROM`, so a day
holding rows from both sides of that stamp has two populations in one column.
The count already excluded the older rows; the share divides by the same subset,
because a share whose numerator and denominator answer different questions is
not a share. Both are null - a dash, never a zero - on a day made only of older
rows.

**The source section is a range plot, and the cap is a rule across it.** It was
five columns of numbers, and the one number every column had to be read against
- where the cut falls - appeared nowhere in the section. One row per source now,
on a log word-length axis, with the shortest, middle and longest article that
source published drawn as a track, and a dashed rule at the cut point across
every row. The part of a track right of the rule is where the cap bites, and the
distance is the text the machine never read. The axis is a log one because the
lengths span more than two decades: a 400-word note and a 9,000-word feature sit
on the same plot, and a linear axis puts every short source on the left edge.

**One rule per cut point, not one rule.** `caps` is one entry per distinct
post-cap length among the window's cut articles, oldest first - the same rule
the compression plot reads its own lines by, so two drawings of one fact
cannot disagree. A thirty-day window over the committed ledger holds two of
them, 1,923 words and 3,846, because the cap moved on 29 August. Past the widest
of them an article lost text whichever cut was in force, so the emphasised span
starts there and says the strong thing; the narrower rule is drawn with its own
dates, so the move is visible rather than averaged away.

**Every margin on this plot is measured, and the label column moves rather than
the plot.** Three constants sized it until 2026-09-01: a 168px gutter for the
source names, a 34px row pitch, and a 130px threshold past which a cap label
flips to read right to left. Measured 2026-09-01 on the built console, the
gutter was 12 percent of a 1,342px frame at 1440 and **52 percent of a 324px one
at 390** - so on a phone the names took more of the chart than the plot did, and
the six tracks drew inside 91px of it.

- **`labelGutter` sizes the name column from the widest name's own advance**,
  and returns null where that would take more than `MAX_GUTTER_SHARE` of the
  frame. Null is the cue to put the names above their tracks instead. A source
  id is the ledger's own spelling of a name and there is no shorter true form of
  it, so the gutter moves and the word does not - nothing is abbreviated at any
  width.
- **`rowPitch` grows a row with the plot, between a floor and a ceiling**, the
  way `cellFor` grows a run-strip cell. The floor is `ROW_PITCH_MIN`: two lines
  of type and a 10px bar leave a 34px row with no air at all between one source
  and the next. The ceiling is where six rows stop reading as one set.
- **The cap label's flip is decided by the label's own advance.** `cut at 3,846
  words (from 25 Aug)` needs 186px at `font-size="10"`; the constant it replaced
  was 130. Nothing was clipped by it on the committed tree, and a constant that
  is 56px under the string it guards is the same defect waiting for one more
  word.
- **The right-most decade label is Row #1's rule, not a second one.**
  `tickAnchor` anchors the end labels inwards, so `10,000` needs no room outside
  the plot and the 12px right margin is the track's own round cap. The
  `10,00` clip measured on 2026-08-31 was fixed there;
  [../../../frontend/tests/console-source-cuts.spec.ts](../../../frontend/tests/console-source-cuts.spec.ts)
  asserts it stays fixed rather than fixing it again.
- **`thinLabels` drops the axis labels that will not fit, and keeps both ends.**
  A label survives only where its left edge clears the last kept label's right
  edge by `AXIS_LABEL_GAP_PX`; a dropped label leaves its mark, so nothing about
  the data goes with it. Measured 2026-09-01 at 390 on the built console: a
  doubling axis running to 1,024 seconds carries twelve edge labels across the
  274px of plot the phone leaves, which is 24.9px an edge against the 28.3px
  `512` and `1,024` need side by side. Drawn every edge, the two ends of the
  axis are crowded; thinned, seven of the twelve survive and none is.
  It lives in `frame.ts` rather than inside the chart because a ledger is not
  obliged to span twelve doublings and the committed canary does not - its
  slowest check is under a second, so the drawn page cannot put the rule under
  load, and an axis the data never stresses is a null result rather than a pass.
  [../../../frontend/tests/console-model-panels.spec.ts](../../../frontend/tests/console-model-panels.spec.ts)
  drives it directly at the plot width the page reports.

**The log domain still snaps to decades, and the dead space is the price.** The
plot fills its frame; the tracks do not fill the plot, and that is a different
thing. Over the committed ledger the shortest article on the board is 361 words
and the longest 6,670, inside a domain of 100 to 10,000 - so 27.9 percent of the
plot sits left of the shortest track and 8.8 percent right of the longest,
measured 2026-09-01 at 1440. Starting the domain at the shortest article would
recover it and lose the landmark: the two cut rules are the reason the chart
exists, and a floating domain gives a reader nothing to place a mark against.

**The rule is read off the rows and never off the setting.** Every cut point
comes off the `source_words` cell a run wrote after its own cap fired. Two
things break if the page reads `extract.truncation_cap_tokens` instead. The
setting is one number, so a window spanning a change draws one rule where the
rows say two - measured on this tree the file says 10,000 tokens, which is 7,692
words, and the window's cut rows sit at 1,923 and 3,846 from the two caps
before it. And a rule from the file draws even in a window where nothing was cut
at all, which a derived one cannot.
[frontend/tests/console-sources.spec.ts](../../../frontend/tests/console-sources.spec.ts)
holds it with a pair of calls over rows cut at two different lengths: no
constant satisfies both.

**Two columns went, and what a reader loses is named.** `Share cut` is gone: it
was dashed below `console.min_attempts_for_rate`, it was explicitly not the sort
key, and a rate ranking was already ruled wrong here. What is lost is the share
as a number - a source at 55 percent and one at 12 percent now read the same
until their two counts are compared, and both counts are on the row.
`Cut short` and `Articles` are gone as columns and are the row's own label,
`17 of 38 cut`, which keeps the count sort and puts the denominator beside the
track it describes. Authority: Susan, 2026-08-30.

**Aggregated on the server, ten rows per preset.** A window of the committed
ledger is a few thousand rows, and this page inlines whatever it is handed, so
the browser never sees the rows the plot was made from. The window ends on the
newest day the ledger holds rather than on the build clock, so rebuilding an old
tree draws what that tree said rather than an empty plot. The 10 rows are a
constant in
[frontend/src/lib/server/model-work.ts](../../../frontend/src/lib/server/model-work.ts)
and not a config knob, because a knob there is a way to make the copy lie.

**A cut is two cells of one row compared, and never a count against the cap.**
`source_words_before_cap > source_words` is the whole test
([../sources/item-health.md](../sources/item-health.md)). The alternative,
`source_words == int(truncation_cap_tokens / 1.3)`, moves the day the cap moves,
so a seven-day window spanning a cap change would mix two cut points - and it
calls an article cut when its body happens to end on the boundary. The column
is empty on every row a run wrote before 2026-08-28, and empty is not zero:
reading it as zero would call every one of those articles cut.

**Articles, not rows.** A run writes a row for every item it plans, so the same
article carries several rows - 1.12 rows per address, measured 2026-08-25. The
table counts addresses, and where two runs read the same article it keeps the
run that read the most of it, so the two lengths compared always come off one
row. The copy says "how many articles", and the count has to mean it.

**What the cut cost is recorded here, not charted.** `hhem_full - hhem` over the
articles the cap cut is what a lost tail costs in faithfulness. Measured
2026-08-29 over all 2,683 committed score rows: **22 rows are cut**, and over
those 22 the delta runs **-0.0381 to +0.1235, mean +0.0039, median 0.0000**. It
is not on the page and will not be: it is a value between zero and one, which
the console refuses ([../../concepts/design-system.md](../../concepts/design-system.md)),
and at n=22 with a median of exactly zero it is not yet a result. The words are
the part that is publishable, and the table prints them with the same n beside
them: over those 22 articles the cut removed a median of 1,009 words and at
most 6,519.

Authority: Jony, 2026-08-29, over Fowler's ordering constraint that this ships
before the cap moves - the first day at a new cap has to be measured by a
console that can already see it, or Rule #10 defeats the change.

**Three headings were renamed on the same day, and all three for one reason: a
heading has to say what is under it.** `Compression` was a subsystem word that
names neither axis of the chart it sat over, and that chart now also carries the
cap line - it is `Article length against summary length`, which is the string
the chart's own accessible name already used. `Charts` on a page of six charts
reads as "the charts" rather than as the planner's output, so it is `Charts drawn
for articles`. `Runs` sat four headings below `Run health` and neither name said
which was which; it became `Runs and site size`, which is what its columns were.
No doc anchor and no test selector read any of the three. `Runs and site size`
is itself gone since 2026-08-30 - two nouns joined by "and" is two sections, and
the section below says where each half went.

**`Charts drawn for articles` became `Visuals drawn for articles` on 2026-08-31,
and the whole section stopped saying `router`.** `router` names a pipeline
stage, and `CLAUDE.md` section 0b bars a subsystem word from a string a person
reads - ten reader strings carried it, from the section's own rule down to the
flow diagram's empty note. Where the word modified a quantity it is gone,
because a section headed for the arm does not need to name the arm again:
`Router minutes per chart` is `Minutes per visual`, the column `Router minutes`
is `Minutes spent`, and `No router time is on record` is `has no minutes on
record`. Where it names the actor it is `the visual planner` - `Reached is
every item the visual planner looked at`. `chart` as the name of a drawn thing
became `visual` in the same pass, including the flow branch `Answered without a
visual`, because more visual kinds are coming and a name about to stop being
true is worth changing once.

**What that costs, stated rather than implied.** `Visuals published` counts only
items whose `visual` is a `chart` in state `rendered`, which is what
[visuals.md](visuals.md) requires so a diagram never lands on the chart arm's
bill. Measured 2026-08-31 over the eleven committed published days: 185 visuals,
185 of them charts, no other kind and no other state - so the heading and the
count agree today and the rename is early rather than wrong. The day a non-chart
visual publishes for real, either the count widens or the heading narrows;
`frontend/tests/console.spec.ts` holds the count to charts and says so.

**No identifier moved on that day, and every one of them has moved since.**
`RouteId`, `data-` attributes, `chart_arm_rule_days`,
`chart_arm_minutes_target`, `chart_arm_coverage_pct`, `route_ms`,
`items_routed`, `charts_drafted` and `routerMinutes` were left alone on
2026-08-31, because renaming those reaches `backend/`, `config/` and the
committed ledgers and is its own change with its own gates. That change ran on
2026-09-05 as a plan of six rows. `routerMinutes` is `plannerMinutes`, and the
two manifest keys `route_ms` and `items_routed` are the one thing that did not
move: they are published in fifteen days of `run.json`, so the Python behind
them is `decision_ms` and `items_decided` and the wire keeps the old spelling
([../contracts/schemas.md](../contracts/schemas.md)). The section also still says `the chart-only
gate`, which is the gate's real name in [visuals.md](visuals.md) and is the
sentence that explains why every visual here is a chart. Authority: owner,
2026-08-31, over Fowler's split of copy from identifiers.

## The site's size is a rate, and the level beside it says which tree

The console asks one size question - is the site going to outgrow the 1 GB Pages
cap - and until 2026-08-30 it answered with two levels and no date. A waterfall
drew megabytes added per day, and a table drew the running total. Neither says
when.

**The waterfall drew the item ceiling and called it site growth.** Measured
2026-08-30 over the ten committed manifests, a day's gain ran 0.04 MB to 2.82 MB
while the day published 4 articles or 731. Divided by the articles, the same ten
days sit between 2,478 and 4,541 bytes. The first series moves when the feeds
have a busy morning; the second moves when somebody changes what a payload
carries, which is the only thing anybody can act on. So the chart is
`What one more article costs`, in bytes of payload tree per published article,
and it follows the page's window.

**A day outside one standard deviation of the window's median is marked, and the
rule is the whole of the marking.** The band is taken about the median rather
than about the mean: the line drawn on the chart is the median, and a band whose
centre and whose width came from two different statistics is asymmetric about
its own centre for no reason a reader can see. One published day in the window
reports no spread at all rather than a spread of zero, which would call that day
perfectly typical of itself. The values are published as text beside the chart -
that is what a chart owes anybody who cannot see it, and it is also the only way
the flags can be checked: `frontend/tests/console-site-size.spec.ts` recomputes
the band from exactly those numbers and fails if the marks disagree.

**The panel says what it is for, and until 2026-09-01 it never had.** Its note
described its own axes - bytes gained, over articles published - and a reader
met a chart of four-digit numbers with nothing to hold them against. It is not
a chart of data growth across days; it is the marginal cost of one more article,
and it is on the page to answer how long the project can keep publishing under
the 1 GB Pages cap. The note now opens with that question and the panel closes
with the answer.

**The horizon is two measured rates over one set of days.** `publishingHorizon`
divides the headroom by the window's median cost, which gives articles, and then
by the median articles a published day taken over the same days that cost came
from - so the sentence and the chart above it cannot be read off two different
windows. Neither rate is a config knob. The band next door prints the same
headroom in articles and stops there, for the reason two sections down: articles
need no daily rate at all, and the one number that used to stand in for a rate
bounded a run rather than a day. The years figure lives here because this is
where the spread and the flagged days are drawn, and the spread is the only
thing that says whether a rate is stable enough to extrapolate from. Null
wherever either rate is missing: a tree that never grew over an article it
published has no horizon, and a window whose days published nothing has no daily
rate.

**The sentence carries the caveat it cannot derive.** The cap is measured on the
built site and this rate is measured on the committed payload tree behind it, so
the room is the most we have and never the least - the two trees were 14.63
times apart on 2026-08-30 and the multiple is not stable. A figure that printed
a date without that clause would be optimistic by a multiple nobody can see.

**The chart measures its container.** It was handed a literal `760` until
2026-09-01 while every other chart on the page read `console.chart_width`; the
drawn width already tracked, because `Chart.svelte` owns it from mount onward
through a `ResizeObserver`, so what changed is that the seed is no longer a
number somebody typed. Measured 2026-09-01 at 1440, 768 and 390, the SVG is its
host's width to within a pixel at all three.

**The window bounds what is drawn and never what is differenced.** A day's cost
is its own bytes minus the previous manifest's, so the oldest day on screen
still reads against the day before it. Differenced against zero it would report
the whole tree as one day's work, and the window would invent an outlier every
time it moved.

**The `Site size` fact carries the level, a track against the cap, the window's
delta and a runway.** The runway is headroom over the per-article cost, and what
it counts is **articles**: `(cap - bytes) / bytesPerItem`. It was published days
until 2026-08-31, divided by `run.safety_ceiling_per_run` articles a day - and
that knob bounds one **run**, not one day. Up to five runs a day is normal, so
the band priced a day at 160 articles while the days it measured ran a median of
334, and the printed runway was 2.09 times too long
([../../reference/measurements.md](../../reference/measurements.md#days-to-the-1-gb-pages-ceiling)).
Articles need no daily rate at all, which is why the fix removed the assumption
instead of correcting it. Where no published day grew the tree over an article
it published there is no rate, so the fact says there is no runway instead of
printing a figure.

**The delta is megabytes and not a percentage, and that was a measurement.** The
oldest committed manifest recorded 13,595 bytes, so a share taken from there read
`+73,933%` on 2026-08-30 - true, unreadable, and painted green by the card's
own up-is-good rule, which is the wrong verdict on a site size as well as one
nobody asked for. `Up 9.6 MB over 30 days` is the same fact in the unit the
number above it is already in.

**The card names the tree it measured, and this is the one thing it cannot fix
itself.** `site_bytes` in a run manifest is `frontend/public/digest/`, and the
Pages cap is measured on the built bundle, which also carries every prerendered
page and the on-device model. Measured 2026-08-30 on Intel Core i7-1265U,
Windows 11 10.0.26200, node v24.12.0, one build:

| | Bytes | Files | Per published article | Runway to the 1 GB cap |
| --- | --- | --- | --- | --- |
| Committed payload tree | 10,414,335 | 170 | 2,478 to 4,541, median 3,261 | about 2,038 published days |
| Built bundle | 152,373,806 | 343 | 46,971 cumulative, 25,786 marginal | 123 published days |

The bundle is **14.63 times larger**, and it was eighteen times larger on
2026-08-27 ([the run-manifest changelog](../../../backend/idhazh/contracts/run_manifest.py)),
so the multiple itself is not stable. **The committed-tree runway above is how
that cell was derived on the day it was measured**; it counts articles since
2026-08-31, for the reason two paragraphs up.

**The caveat left the band on 2026-08-31 and lives on the panel it belongs to.**
The band's fact was written caveat-first: three sentences naming the committed
payload tree, the larger built site, and the build command that prints the
runway that binds, before the one number the fact is for. It was about sixty of
the band's hundred words, and it stood on all three routes. It is one line now -
the level, the limit and the articles the headroom buys - and every clause it
dropped is on `What one more article costs` directly below it, which already
owns the rate, the days it was measured over, its spread and the sentence
saying the cap is measured on a larger tree so the room is the most we have and
never the least. `idhazh site-weight` and `committed payload tree` are not
reader strings on any surface now: a build command is not something a reader can
run, and neither phrase says anything the panel's own wording does not. The band
still never says "the site" has room for N, because it does not know that.
Measured 2026-08-31 the band read about 312,000 articles of room in the
committed payload tree, while `site-weight` on 2026-08-30 read 119 published
days in a bundle 14.63 times larger - two trees, two units, and that gap is what
the panel's wording exists to keep visible
([../../how-to/run-the-gates.md](../../how-to/run-the-gates.md)).

**What the deleted table was for, and where each column went.** `Runs`,
`Planned` and `Failed` were per-day run counts, and all three are already on the
run strip four headings above - `Planned` rides the run square's own label as
`N of M succeeded`, which is where run-level facts live. `Site` is the card.
`Files` is gone with no replacement: it was the count of files under the payload
tree, and the question it answered - did the tree grow because we published more
or because pages got heavier - is the question the per-article chart now answers
directly.

### Design rationale

**The plan that ordered this row asked for a runway and assumed the console
could measure the tree the cap measures. It cannot, and that was found by
measuring rather than by reading.** The row's stated basis was 24,378 bytes an
article, spread 23,066 to 26,538, which is the built bundle's cumulative average
from `idhazh site-weight`. The console reads run manifests, and the same
arithmetic over those gives 2,478 to 4,541 bytes an article - a different tree,
roughly seven times smaller per article and thirteen times smaller in total.

Three options were weighed:

| # | Option | Outcome |
| --- | --- | --- |
| 1 | Print the runway from the payload tree against the cap and call it the site's | Rejected on the measurement. It reads about 2,000 published days where `site-weight` reads 123 - out by a factor of sixteen, and a fabricated date is worse than the level it replaced. |
| 2 | Add `built_site_bytes` to the run manifest | Rejected here, not on merit. It is a persisted-contract change, which is `CLAUDE.md` section 6 Level 5 and pauses work. It is the change that would make the console's runway exact, and it is recorded here so the next person does not have to rediscover it. |
| 3 | Print the runway of the tree the console has, and name that tree inside the sentence | Taken. Every clause on the card is true and checkable, the direction of the error is stated, and the instrument that measures the other tree is named. |

A fourth was considered and dropped without a table row: a measured
payload-to-site multiple held in `config/`. The two trees do not scale together
- `frontend/static/assist/` is 45,328,441 bytes and does not grow with articles
at all - so one multiplier is not just stale-prone, it is structurally wrong.
The measured multiple was 14.63 on 2026-08-30 and eighteen three days earlier,
which is the evidence.

**The track reads about one percent full, and that is the honest picture.** It
fails the "does it use the screen it is on" sufficiency check
([../../concepts/design-system.md](../../concepts/design-system.md)) in the sense
that a nearly-empty bar carries little information, and it ships anyway: the
caption prints the room left as a number beside it - `1,014 MB left of the 1 GB
Pages cap` - and the fill has a 2px minimum so a level far under its limit still
reads as a measurement rather than as an empty control. The alternative -
rescaling the track to make the bar look busy - is a chart that lies about how
much room is left.

## Rejected alternatives

The operator's surface. The reader's own table is on
[frontend.md](frontend.md) - a reader row and a console row share nothing but a
heading.

| Option | Why rejected | Authority |
| --- | --- | --- |
| A console LISTING every feed, healthy ones included | Naming all 182 sources hides the 26 that are broken. The clean ones are named behind a disclosure since 2026-09-01, with no bars and no order - a name is a fact, a row in the broken list is a call to act. | owner, Susan |
| A ranked "ten most reliable feeds" | Every key it could rank on ties: a feed is read once a run, so one that never failed has answered on every run it was asked. A top ten of a hundred-and-fifty-way tie is charting a constant. | Susan |
| A newest-first run strip | Every other time series on the page reads left to right in time. One that read right to left made the newest day's position depend on how much history existed. | Jony |
| An empty square for a scheduled run that wrote no manifest | It claims evidence the payload does not carry. Missed runs need a persisted schedule or attempt contract before they can be drawn. | Fowler |
| A date under every column of the run strip | At 16px a track and 10px a label the dates overlap from about the fourth day, and an axis that cannot be read is decoration. | Jony |
| Scroll buttons, a zoom control or a chart library for the strip | A native scroll region already pans with the arrow keys, costs no bytes and needs no focus management of its own. | Jony |
| Re-centring the strip on the newest run after data or layout changes | The operator scrolled there on purpose. A view that snaps back cannot be read. | Jony |
| A second threshold for the red square | CI already reads a success floor to decide whether to open an issue. Two numbers answering one question drift, and then a red square and an open issue disagree. | owner |
| Counting skipped items against a run's health | An already-published article is skipped by design. Counting it would paint a healthy day amber for doing its job. | owner |
| Dropping a column from the shard board on a phone | The board is five facts about one shard, and an instrument that answers four questions on a phone and five on a desktop is two instruments. A horizontal scroll was refused with it: it hides the job clock, the column an operator opens the page for. | Jony, Susan |
| Summing peak memory across shards | Shards are separate jobs on separate hosts. The sum reads about 53 GB on a runner that has 16. | Carmack |
| Reading stage timings from `state/scores.csv` | The score ledger did not carry those columns, and it only covers scored items. Timings belong on the item-health census. | Fowler |
| Serving `state/item-health/` directly | It carries `canonical_url`, `url_key` and untrusted `detail`. The browser gets only the published telemetry projection. | Fowler, Rule #11 |
| A failure bar scaled to the window's own maximum | With one day in view the bar normalises to itself, so a 12% failure rate and a 90% one both fill the panel. | Jony |
| A failure rate carried only by an SVG `<title>` | A tooltip does not fire on touch and does not survive the screenshot an operator pastes into an issue. | Jony |
| Suppressing the failure chart for a window holding one day | It was right when the panel drew one bar per stage: a chart of a single value is a rectangle. The column carries the volume now, so one day is one column and still says how much work there was. Only a window holding nothing at all draws no chart. | Jony |
| Keeping three failure panels and adding sparklines | It leaves the split, which is the defect rather than the content. | Jony |
| A single headline failure rate for the whole pipeline | It hides which stage failed, and which stage failed is the actionable half. | Susan |
| Rendering every failed row in the window | 800 rows measured 7824px and pushed the compression chart to document y=9105. The rows are on demand. | Jony |
| A virtual-scrolling failure table | A dependency and a scroll-position bug for something a cap and a button already solve. | Jony |
| A stage glyph beside the stage name | The icon set is one generated module that reaches every route, so three stage marks would move six reader routes that cannot show this section at all. An icon that needs a caption is a label wearing a costume, and the stage name is already in the cell. | Jony |
| A per-day stacked bar list for stage timings | Thirty days is about 150 rows and no trend, and the trend is the only question the section is asked. | Jony |
| Clamping a zero stage timing into the bottom decade | It draws a plunge to the floor of the plot, which says the stage got a thousand times faster on a day it was merely quick. | Jony |
| A caret beside the line for a zero stage timing | A second shape for a fact the open dot already carries, and one more thing to learn before the chart can be read. | Jony |
| A dashed bridge across a stage-timing gap | A slope between two days that share no measurement is a number nobody took. | Jony |
| A fifth sub-millisecond decade on the stage-timing axis | It moves every mark on a 30-day chart to hold ten rows from one day. The axis is not the thing that was wrong. | Jony |
| A linear/log toggle on the stage-timing axis | A toggle is an admission that we could not decide which axis is correct. | Jony |
| A density-binned scatter, or reducing the mark opacity | Both keep the two-axis reading the band split removes, and the second makes a paler blob. | Jony |
| `uplot` on the compression scatter | It drew a second, smaller chart beneath a complete SVG, and the pan and zoom it was bought for live in the viewport control, not in the plot. | Jony, Rule #8 |
| Fading the per-point band lines instead of collapsing them | The wash is a node count, not an alpha value. One fact drawn 1166 times is still drawn 1166 times at any opacity, and the fact has one value per configured band. | Jony, Carmack |
| A drawing library for the console charts - `echarts`, `@observablehq/plot`, `chart.js`, a component library | 336 KB gz on canvas, 128 KB gz and a DOM shim to prerender, 67 KB gz on canvas, and a component set is worst of all where every chart is bespoke. All of them own the element and the theme; the console needed the arithmetic. This was reversed for the console on 2026-08-29 on three named conditions, and it still binds a reader route. | Jony, Carmack |
| `d3-scale` from a CDN | The HTTP cache is partitioned per site, so the shared-cache argument is dead, and the repo's `script-src` allows `self` only. | Carmack |
| Fixing the units by hand instead of taking the dependency | `.nice()` and `ticks()` are exactly the part hand-rolling gets wrong, and an axis labelled 0, 37, 74 is an axis nobody reads a value off. | Jony |
| A `console.chart_width` default per chart shape | One knob names the width the reading column leaves; a chart sharing a row divides it. Four knobs would be four ways to disagree about one column. | Jony |
| Putting the page ceilings anywhere but `config/` | A ceiling is a limit a person chose and raises on purpose, which is the definition of a knob (Rule #6). | Carmack, Rule #2 |
| A `run.success_floor_pct` reference line on a stage failure panel | That floor is a published rate over attempted items; a stage panel is a different denominator. A wrong reference line is worse than none. | Jony |
| A separate chart for where the cut falls | It is a line. A chart that says what a line says has not earned its place. | Jony |
| A cap line read from `extract.truncation_cap_tokens` | A thirty-day window can hold two settings, so the knob is a claim about a config file rather than about the plot. It also draws a line when nothing in view was cut, and the data-derived line cannot. | Jony |
| `--band-low` for the cap line | A red vertical says the cap is a failure. The cap is a setting. | Jony |
| A second shaded region for the cut | The band zone already means "target summary length". Two shadings meaning two things on one plot is one too many. | Jony |
| An SVG `<title>` as the chart tooltip | It does not fire on touch, carries a delay nobody chose, cannot be styled, is not keyboard-reachable, and does not survive a screenshot pasted into an issue. It stays as the accessible name. | Jony |
| A readout pinned to the pointer | A readout under a thumb is a readout nobody reads. | Jony |
| A tab stop on every data point | The committed ledger draws 2,541 of them. A 2,541-stop tab order is a trap, not access. | Jony |
| A readout on the run-health strip | It has no per-day point to land on. | Jony |
| A readout on `FailurePanels` - reversed 2026-08-31 | It was refused because the chart prints every stage's rate and its denominator in type under the plot. It prints them for the window, not for a day, and the day is the column the strip prints. | Susan |
| A readout on `StageTimings` - reversed 2026-08-30 | It was refused because the chart "already prints its headline in type", and the headline it printed was the newest day. The chart had no per-day label and no mark, so the other twenty-nine days could not be read at all. | Susan, over Jony's 2026-08-25 ruling |
| A floating readout box over a plot | Measured 2026-08-29 at 88 to 121px over a 220px plot: 40 to 55 percent of the chart it explains. A strip below the plot cannot occlude at any width. | Jony |
| Re-sorting the readout rows to the hovered day | The rows are the legend. A legend that re-orders under the eye as the pointer moves cannot be read, and the colour swatch already matches the line. | Jony |
| Labelling only the first and last day of a date axis | That is what it did. It is what makes a spike unattributable to a date. | owner, 2026-08-30 |
| A charting library for the readout | There is none on this surface and this adds none. One action beside `observeWidth`. | Jony, Rule #8 |
| One chart carrying both the visuals strip and the articles strip | Two axes invite a comparison of slopes that means nothing, and one axis flattens the smaller series to nothing. | Jony |
| Seeding the per-item cost columns with real values | It cost `/console/` 176,753 gzipped bytes and put it 98,182 over its ceiling. Dropping the seeded months instead puts a 244 KB fetch behind the first click and leaves the section blank until it lands. | Carmack |

## See also

- [frontend.md](frontend.md) - the reader's published surface, and the routes this one sits beside.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
- [console-payloads.md](console-payloads.md) - what the console fetches, and what it may never be served.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
- [../sources/health.md](../sources/health.md) - the feed ledger these panels render, and the quarantine rule they mirror.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings and what to do when one fires.
- [../../reference/measurements.md](../../reference/measurements.md) - the instrument log behind every number here.
