# Published Frontend

**Last Updated**: 2026-08-25

The reader's surface: what is built, what deliberately is not, and the rulings behind both. This page is the living record for the digest page, the archive and the console.

Concept-level *why* lives in [../../concepts/digest.md](../../concepts/digest.md), [../../concepts/design-system.md](../../concepts/design-system.md) and [../../concepts/ui-shell.md](../../concepts/ui-shell.md). This page is the *shape*, and it records where the owner, Jony and Reader disagreed and how it was settled.

## Everything is prerendered

Every route is generated at build time with its items inlined in the HTML. SvelteKit with `adapter-static`, `prerender = true`, and `entries()` enumerating the committed date directories.

Three consequences, and each one removes a whole class of problem:

- **The reading path makes zero runtime requests.** One document and it is done - well inside the two-request budget, and the page works with JavaScript off.
- **There is no loading state to design**, and therefore no spinner to be tempted by. The payload loader still exists as exactly one module; it runs in Node instead of in a browser.
- **A payload that fails its contract fails the build.** What would have been a runtime error a reader discovers becomes a build error nobody ships.

The loader lives under `frontend/src/lib/server/`, which is the framework's own guarantee that it can never be bundled into anything a browser receives.

| State | When | What ships |
| --- | --- | --- |
| Ready | Normal | Prerendered HTML with the items in it |
| Empty | Payload exists, no items | "Nothing was published for *date*", with plain copy that does not point at a notice that may not be on the page |
| Missing | No payload for that date | A 404 that names the date and offers the archive. **Never a redirect to today** - a reader who cannot tell a dead link from a live one has lost the ability to trust any link |
| Invalid | Payload breaks its contract | The build fails |
| Degraded | Low band, source-limit sentence, no visual | The common case, rendered inline. Not an error |

The home page uses the newest committed payload as the day it can prove. It never
uses the build clock as "today". If the site is rebuilt after a quiet or failed
run, the page still names the payload date it actually renders, and the empty
state offers the archive plus the latest published day when one exists.

## Components are swapped by props, and ordered by config

Every component takes a validated slice of the day payload as props and returns markup. No component fetches, no component reads global state, no component knows a route. Swapping one means writing a file with the same props and changing one line.

Page order is `config.ui.sections`, a registry id list. **Reordering the page is a config edit, not a code change.** That is the honest version of "modular".

What is deliberately *not* built is a slot system for moving components left and right. On the surface that matters - a phone - there is no left and no right; there is one column. A layout engine for one column is unbounded QA against a reader who does not exist, and a per-reader layout would break the promise that a shared link shows the recipient what the sender saw. Two named flips are granted where left and right are real: `ui.visual_side` and `ui.source_mark`.

## Theming

Class strategy, not media query: a reader on a dark-defaulted phone who wants to read in bed needs a way to say so. Three toggle states (`system`, `light`, `dark`), two themes. A six-line inline script applies the stored choice before first paint, which is the one inline script this site carries and exists solely to prevent a white flash.

**A theme is exactly one `[data-theme="x"]` block supplying the token names in `frontend/src/styles/tokens.css` and nothing else.** The mechanism ships; two themes ship. A third means re-picking three band colours, eight source swatches and a focus colour and carrying them forever for a reader nobody has met.

## The confidence signal, and the argument about it

This is where Reader and the owner disagreed, and it is worth recording properly.

**Reader's objection, in their words:** a per-item confidence badge is "the project talking to itself in public". A label that changes nothing a reader does is decoration with a serious face; a page where most items are marked low "stops reading as honesty and starts reading as a confession"; and the day a `high` item is wrong, the label has actively talked the reader out of the suspicion that would have caught it.

**The owner asked for a colourful confidence indicator, and owner approval supersedes an agent** ([../../../CLAUDE.md](../../../CLAUDE.md) section 0). What ships is Jony's proportionate version, which answers most of Reader's objection without discarding the ask:

| Band | On the item |
| --- | --- |
| `high` | **Nothing.** Ink spent on the absence of a problem, and colour-only |
| `medium` | A 6px dot and "Mostly matches the source" |
| `low` | A 6px dot and "May not match the source", the label in the low token |

It sits **on the meta line, after the summary and beside the source link** - never above the title. A caveat above the title pre-judges an item before the reader has read a word. The reading order is: what it is, what it says, then where it came from and how sure we are.

**No stripe, no tint, no coloured card.** If two-thirds of items are medium or low, a large treatment paints two-thirds of the page as broken and the reader concludes the whole digest is. One dot and eight words stays proportionate at any distribution.

**The day level carries no confidence chart, and this reverses an earlier
ruling.** The owner asked for a colourful confidence signal, and what shipped
first was a three-segment bar of the day's bands with the counts beside it. It
was deleted on 2026-08-24 for four reasons that compound:

- It charted a constant. Measured 2026-08-24 at n=447, re-banded: 57.7 / 24.2 / 18.1. The same three-part shape every day is not a signal.
- It shared `--band-medium` and `--band-low` with the item dot, so a reader trained to ignore the day-level red was trained to ignore the item-level red - the one that does have something to say.
- Its legend still printed "mostly matches the source", the exact string the item level abandoned when it moved to naming what is missing. The reader met the retracted sentence first.
- Its `aria-label` was the legend verbatim, so a screen-reader user heard the counts twice.

The owner's ask is still honoured: the colour is on the item dot, where it
varies between two items on one screen, carries a sentence naming what is
missing, and sits beside the link that lets the reader check. **The prose
version is refused too** - "104 of today's 586 summaries may not match their
article" is the same defect in a different typeface, a number over a corpus the
reader can neither locate nor act on. A day-level confidence instrument that
would be honest is a trend against previous days, and that is the console's job.
Authority: Jony and Reader, 2026-08-24.

**Source limits are sentences**, not chips. An abstract item says "This is a
summary of the paper's abstract. The full paper is a PDF." A truncated item says
"We could only read the first part of this page." Reader wanted specific
warnings they could act on rather than a grade, and Jony rejected another badge.

**Where Reader still wins:** if most items land low, the page will look like something is wrong, and it will be right. The fix belongs in the pipeline, not in the palette.

## Source identity, and the field Reader asked for

A build-time monogram plus the publication name in type. No fetched favicon - that is a runtime third-party request that announces every reader to every publisher, and its failure mode is a broken-image glyph mid-page. No per-publisher artwork either: 37 marks and growing, each one somebody's trademark at 16px.

Reader named one thing an item did not carry that they wanted before they would share it: **what kind of source it is.** "A company said its product is faster" and "a reporter measured it" are not the same claim, and they were arriving in the same typeface. `source_kind` is now on the payload, and the item prints it only where the speaker has a stake worth naming - `announcement` and `community`. Labelling every item "Reporting" would be noise; labelling a vendor's own copy is the warning.

## Topics: pills, and never an empty one

Pills rather than tabs. Tabs assert a fixed exhaustive set of panels; the vertical set is data-driven and varies daily. Pills read as filters over one list, which is what a topic is here.

**Only verticals present in the payload get a pill, with counts.** That is 1-6 controls on a real day, not 18 - and it makes Reader's objection structurally impossible: an empty tab, which reads as broken software, cannot occur because it is never rendered.

Each pill is a link to a prerendered route, so middle-click, share and back all work. Lenses and events are not on the pill row: thirteen mostly-zero controls above seventeen items is a control bar longer than some days.

## The read mark is held per day, and it expires

A reader can mark an item read. The mark lives in `localStorage` and nowhere else - never a cookie, because a cookie is sent on every request and would put a reading history into the host's access logs.

**The store is keyed by digest date**: `{ "2026-08-23": ["ai-0417291083", ...] }`. It used to be one flat list of ids with no date, and that shape had two faults that are really one fault:

- **It greyed out the wrong article.** An id that came round again on a later day matched a mark the reader had never made, so an unopened item arrived already read.
- **It grew forever.** Nothing in a bare list says which day a mark belongs to, so nothing could ever decide which marks to drop.

A date makes a mark answerable, and answerable is what lets an old one be dropped. `loadRead` prunes to the newest `ui.read_mark_days` (7) days on every page load, so the store is bounded by the window rather than by how long the reader has been coming.

**The old shape is discarded, not migrated.** There is no honest way to decide which day an undated mark belonged to. A wrong mark costs a reader an article; a lost mark costs them a click.

`forgetAll` clears one day, because the button sits on a day page and has to do what it says. Everything here is a convenience: a quota error or private mode degrades to no marks and never to a broken page.

The rule this must never break is in [layout.md](layout.md): read state may change how an item **looks**, and may never change where it sits, whether it appears, or how it ranks.

## Search: overruled, and built the narrow way

Jony refused a top-level search bar and Reader called it "clutter, and a lie about what is behind it" - a box implying an archive the reader cannot reach, which manufactures a failure out of a quiet morning.

The owner asked for it. What ships is the narrow defensible version, which is a filter, not a search:

- It lives **inside the topic row**, not as a top-level bar above the first headline.
- It filters **in place** over what is already on the page. It never navigates and never touches the URL.
- It states its own scope - "6 of 17" - so it cannot imply an archive.
- No results says so plainly, naming the day rather than the corpus.
- The query is untrusted reader input matched against untrusted payload text: compared with a lowercased substring test, and never interpolated into a selector, a class, a URL or markup.

Real cross-day search belongs on the archive, later, where the question "where was that thing about the reactor?" is genuinely unanswerable by scrolling.

## The all-topics page is grouped, and nothing is dropped to do it

A day of 586 items rendered as one queue had no usable first screen. Items are
appended in plan order, which is per-vertical, so the payload reads
`[run 1: ai..., business..., energy...][run 2: ai...]` and the first twelve on
the page were the top twelve of whichever vertical id sorted first. That is an
accident, not an edit.

The all-topics view now renders one section per vertical, in the payload's own
topic order - the same order the pills use - showing each topic's first
`ui.items_per_topic` items and then a link into the prerendered topic route:
`All 173 AI stories`. A topic that fits inside the limit carries no link,
because the link would lead to what is already on screen.

Three rules make this hierarchy rather than truncation:

- **No item is removed, hidden or re-ranked.** A slice is the head of the published order, and the whole topic is one click away on a route that is prerendered, shareable and works with JavaScript off. [layout.md](layout.md) forbids demoting a published item, and this does not.
- **A topic route and an active filter stay flat.** Both already have a subject, and filter results cross topics.
- **A day that ran to a single topic stays flat too.** One heading over the whole page states what the page already says, and it would put items behind a link that leads back to the same list. This is also what keeps every planted item on one page for the injection canaries.

An emptied section is not rendered. A heading over nothing reads as broken
software, and it happens for real when a reader hides what they have read - so
the link is measured against the day's own count, not against the view.

The arithmetic lives in
[frontend/src/lib/day-shape.ts](../../../frontend/src/lib/day-shape.ts), the way
the run strip's axis does, so the rules can be tested without a browser.

## The day notice is one line, and one divider marks the later runs

The notice states the day as facts and never as a judgement: the count, the
failures when the run was partial, and how many arrived after the first run. It
used to print one near-identical paragraph per later run, which said one fact
three times.

`introduced_by_run` is on every item and used to be rendered nowhere, so the
notice named a fact with no place on the page. A flat list now carries one
hairline divider - `Added later today` - before the first item a later run
added. Once per page, never once per run and never once per item, and never a
run number or a UTC time, because a reader does not know what run 3 is.

## No summary of the summaries

Asked for, and Reader ruled **no**, decisively:

> Every other piece of text on that page has a link under it, so when a sentence smells wrong I can go check. A paragraph at the top summarising the day would be the only text on the page with nowhere to click.

It would also be three removes from the source - a summary of summaries of articles - and every layer of compression is a layer of invention. What sits at the top instead is a line of facts with no voice: the date, the counts, and, when a run was partial, plainly how many did not finish. If four of five items failed and the page does not say so, a reader who works it out later has spent the trust the digest was saving.

## The footer states two commits, and never merges them

```
Run 1 of 21 August 2026, 21:12 UTC.
Built from git - 473ba32 - deployed 2026-08-21
```

The run is the data's provenance; the commit is the site's. They move independently, so a single line claiming both would be wrong half the time. The SHA comes from the build environment, injected at build time - never fetched, never read from a committed pointer that could go stale.

## The console answers "is it working", in one screen

`/console/` is the operator's surface. The digest tells a reader what happened in the world; the console tells the owner what happened to the pipeline. It is instrumentation, it earns no design budget, and its only obligation is to be correct ([../../concepts/vision.md](../../concepts/vision.md)).

`/evals/` remains a published entry point for old bookmarks. It carries a
prerendered meta refresh, a canonical link and a plain link to `/console/`.
GitHub Pages cannot serve a SvelteKit server redirect, so the redirect must be
static HTML. A reader with JavaScript disabled still receives a page and can use
the link.

**The run strip is a time axis: one column per day, oldest on the left.** Days
advance left to right the way every other time series does, so "it broke on
Tuesday and has been amber since" is a shape rather than a sentence. Each day is
a fixed 16px track with a 4px gap, and a label may never widen a track - two
days apart must measure twice one day apart, whatever the date under it says.

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
each end and a label every seventh column between them, dropping any
intermediate that lands within six columns of the newest end, where the two
texts would share pixels. The year is printed on the first label that changes
it and not again. The arithmetic lives in
[frontend/src/lib/charts/run-history.ts](../../../frontend/src/lib/charts/run-history.ts)
so it can be tested without a browser.

**Overflow opens on the newest edge.** The strip is a native horizontal scroll
region - focusable, labelled, and pannable with the arrow keys, with no buttons
and no chart dependency. A history shorter than the viewport aligns right, so
the newest run is in the same place whether there are three days or three
hundred. JavaScript sets the initial scroll to the newest edge once, on the
first animation frame after mount, and never again: after that the position
belongs to the operator.

Three colours, and the boundaries are read from config rather than chosen by the page:

| Colour | When |
| --- | --- |
| Green | The run completed, nothing failed, and the source list was current |
| Amber | Something is worth a look: an item failed, the run did not complete, the source list was stale, or nothing was attempted |
| Red | The run failed, or its success rate fell below `run.success_floor_pct` |

**The red threshold is the same knob CI uses to decide whether a run opens an issue.** A red square and an open issue can never disagree, because there is one number and both read it.

**A skipped item is not a failure.** An article already published, or one a feed repeated, is skipped by design, so the rate is over what was *attempted*. Counting skips would paint a healthy day amber for doing its job.

Beneath the strip is **every feed that failed at least once**, worst first, with its attempt count, its last outcome and how close it is to quarantine. A feed with a clean record is not listed: the operator came here to find what is broken, and a list naming all seventy sources hides the four that are. The failing rule matches `FeedHealthRow.failing` in the contract exactly - a `200` that parsed to no entries counts as a failure, a `robots.txt` refusal does not ([../sources/health.md](../sources/health.md)).

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

The viewport is a 30-day default window, not a retention policy. The window size
and where today sits are `console.default_window_days` and
`console.today_anchor`. When less history exists, the first view fits the rows
that exist instead of drawing empty calendar space. Arrow keys pan, and `+` /
`-` zoom, from a labelled focusable control with a visible focus ring; the
buttons beside it do the same thing with a pointer. **Every console chart is
hand-written SVG rendered on the server**, so the page is complete before any
script runs and stays complete if none does. If a telemetry month is absent or
cannot be parsed, that month is a gap in the charts. It is not interpolated, and
it never white-screens the console.

**Every chart draws through one coordinate frame, in CSS pixels.**
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
owns the width, the margin box and the two domain rules - linear, rounded
outward to numbers a reader can place, and anchored at zero only where the
mark's *length* carries the value; and log, snapped to whole decades. A mark
that encodes by position takes the padded domain instead, because a zero no run
was ever measured at is plot spent on nothing. Before the frame, each chart
chose its own `viewBox` and let the browser fit it to the column, and a
`viewBox` is a scale factor rather than a unit. Measured
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
one. `npm run bundle-gate` holds that true. Beside its encoder check it now
prices every route class against a gzipped first-load ceiling, so the next
dependency has to be measured before it can ship. HTML weight is deliberately
outside that gate: the document belongs to the payload work, and one gate
spanning both would make two workstreams fail each other's builds.

The item-health viewport has three parts, in this order:

- **Failure panels**: fetch, extract and summarize failure rates as separate bars. **The rate is printed in type under each stage name** - `16% failed, 126 of 800.` - because an SVG `<title>` does not fire on touch and does not survive the screenshot an operator pastes into an issue. **The y domain is fixed at 0 to 100%.** Scaled to the window's own maximum, a single day in view normalised its bar to itself, so a 12% rate and a 90% one both filled the panel. **A window holding one day draws no chart at all**: a chart of one value is a rectangle, and the sentence is the panel. Thin denominators use outlined bars below `console.min_attempts_for_rate`, explained once under the row rather than once per bar. Colour is spent only on a failure.
- **Compression scatter**: source words against summary words on a log x axis with decade ticks, the `summarize.bands` step function as the reference band, and a distinct mark for truncation-flagged scored items. One chart, hand-written SVG. It used to carry a second `uplot` canvas underneath drawing the same dataset with neither the band reference nor the truncation mark, which is two drawings of one dataset that disagree.
- **Failed item list**: the rows behind the shape, **capped at `console.failure_list_max` with a `Show 25 more` button**, and stating its own scope - `Showing 25 of 214 failed items in this window.` A panel chip filters it, because after a spike the operator needs rows, and a new window or a new chip resets the cap because it is a new question. Uncapped it measured 7824px against 800 rows and put the compression chart at document y=9105. It sits last for the same reason: it is the only child that can outgrow the screen, so it cannot sit between two charts.

Measured 2026-08-24 on the committed ledger: the console document went from
11552px to 4878px.

**Stage timings are one trend chart, not a list per day.** Four polylines over a
calendar x axis, oldest on the left, sharing the run strip's own sparse-label
arithmetic. A day with no census breaks the line rather than closing the gap,
because "no data" and "no time spent" are different facts, and a single day
draws dots rather than lines. The legend prints the newest day's value per
stage. The old block was one group of four bars per day - about 150 rows at a
30-day window, and no trend - and "is it getting slower" is the only question
the section is asked.

## Design rationale

Prerendering everything is the decision the rest hangs off. It was chosen over a runtime fetch of `digest.json` because it collapses four problems into zero: the loading state stops existing, the request budget stops being a budget, a contract-invalid payload becomes a build failure instead of a reader-facing error, and the page keeps working with JavaScript off. The cost is one framework dependency and a build step that enumerates committed directories. Authority: Jony ([../../../.github/agents/jony.agent.md](../../../.github/agents/jony.agent.md)).

Spending the colour per item rather than at the day level is the resolution of a genuine conflict between an owner instruction and a persona's ruling, and it took two passes to land. The owner asked for a colourful confidence signal; Reader argued that per-item confidence badges are the project talking to itself. The first answer put the aggregate at the top and the proportionate signal on the item. The aggregate then had four months of data behind it and never moved, so it was deleted: colour belongs where it varies, and where a reader can click through and check. Authority: owner (section 0), designed by Jony, constrained by Reader.

Grouping the all-topics page by topic is hierarchy, not truncation, and the distinction is the whole argument. [layout.md](layout.md) forbids removing or demoting a published item, and [../../concepts/digest.md](../../concepts/digest.md) says the reader's budget is protected by ordering and hierarchy - so the fix for a 586-item day had to come from typography rather than from a cap. Every item stays published, in its published order, one prerendered click away. The rejected alternative, truncating the day, would have made the page look like a digest by making it stop being one. Authority: Jony, with Reader as the check.

Removing `uplot` restores the refusal one row below rather than overturning it. Rule #8 requires a dependency to name a beneficiary feature; its recorded beneficiary was pan and zoom, and `Viewport.svelte` implements those itself with a keydown handler and four buttons. What it actually drew was a second, smaller copy of the compression scatter with less information than the SVG above it. It would come back for pan and zoom *inside* a single chart, which is a different requirement, and the gzipped route chunk would be re-measured on that day rather than reusing the 2026-08-23 figure. Authority: Jony, Rule #8.

Taking `d3-scale` and `d3-array` a day later is not that decision reversed. A
chart library owns the element, the redraw and the theme, which is how the last
one ended up drawing a chart that already existed; a scale library returns a
number. The beneficiary feature Rule #8 asks for is the whole console: four
charts that agree on what a pixel is. The cost is measured rather than argued -
the ceiling in `bundle-gate.mjs` is what a later row has to fit inside, and
Carmack made that gate a condition of accepting the dependency at all. Authority:
Jony and Carmack, 2026-08-25, owner accepted.

Putting the first-load ceilings in `bundle-gate.mjs` rather than in `config/`
is deliberate, and it is the one place the config rule does not apply. Rule #6
sends a tunable to `config/` because an operator may reasonably want it
different; nobody reasonably wants a reader to download more. A budget an
operator can edit to fit the build is not a budget (Rule #2), so raising one is a
reviewed diff with a measurement beside it. Authority: Carmack.

Folding `/evals/` into `/console/` keeps one route answering "how is the
pipeline doing". Both old routes read `state/scores.csv` and counted per-day
bands. Two surfaces reading one ledger would disagree as soon as one count
changed. `/evals/` stays as a static entry point because `CLAUDE.md` section 3
says the published dashboard keeps the route. Authority: Jony and owner defect
3.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Runtime fetch of the day payload | Invents a loading state, a request budget and a runtime error class, all of which prerendering deletes. | Jony |
| A top-level search bar | On a page whose whole content is on screen it is a control with nothing to do, and it promises an archive it cannot reach. Narrowed to an in-place filter. | Jony, Reader |
| Drag-and-drop or slot-based layout | No left and no right on a phone, unbounded QA, and per-reader layout breaks the shared-link promise. | Jony |
| A third theme on day one | Three band colours, eight swatches and a focus colour to carry forever for a reader nobody has named. | Jony |
| Publisher favicons | A runtime third-party request that announces every reader to every publisher, failing to a broken-image glyph mid-page. | Jony |
| A coloured stripe or tinted card per band | At a realistic band distribution it paints most of the page as broken, and the reader believes it. | Jony |
| A `high` badge on every item | Ink spent on the absence of a problem, and colour as the only signal. | Jony |
| A summary of the day's summaries | The only text on the page with nowhere to click, and three removes from the source. | Reader |
| Topic tabs including empty ones | An empty tab reads as broken software or an absent desk. Only present verticals are rendered. | Reader |
| `key_points` shown alongside the summary | The same content twice, at the cost of the hierarchy and half the items per screen. | Jony |
| A visual placeholder when there is no visual | Makes "we correctly decided this needed no picture" look identical to a failed image. | Jony |
| A chart library on the dashboard | Kilobytes of dependency to draw a stacked bar over a few hundred rows. | Jony |
| A service worker or offline shell | It can serve a reader a stale day, which attacks the rule the whole layout rests on. | Jony |
| Computing "today" in the browser or at build time | The browser would vary by reader timezone, and the build clock would let a stale deploy claim a date the payload does not carry. | owner |
| A flat list of read ids with no date | An id that came round again greyed out an article the reader had never opened, and nothing in the list could decide which marks to drop. | owner |
| Migrating undated read marks rather than discarding them | There is no honest way to say which day they belonged to, and a wrong mark costs a reader an article. | owner |
| A read mark that hides or demotes an item by default | Two people at the same URL would see different pages, and a shared link would stop showing the recipient what the sender saw. | Reader |
| A console listing every feed, healthy ones included | Naming all seventy sources hides the four that are broken. | owner |
| A newest-first run strip | Every other time series on the page reads left to right in time. One that read right to left made the newest day's position depend on how much history existed. | Jony |
| An empty square for a scheduled run that wrote no manifest | It claims evidence the payload does not carry. Missed runs need a persisted schedule or attempt contract before they can be drawn. | Fowler |
| A date under every column | At 16px a track and 10px a label the dates overlap from about the fourth day, and an axis that cannot be read is decoration. | Jony |
| Scroll buttons, a zoom control or a chart library for the strip | A native scroll region already pans with the arrow keys, costs no bytes and needs no focus management of its own. | Jony |
| Re-centring the strip on the newest run after data or layout changes | The operator scrolled there on purpose. A view that snaps back cannot be read. | Jony |
| A second threshold for the red square | CI already reads a success floor to decide whether to open an issue. Two numbers answering one question drift, and then a red square and an open issue disagree. | owner |
| Counting skipped items against a run's health | An already-published article is skipped by design. Counting it would paint a healthy day amber for doing its job. | owner |
| Reading stage timings from `state/scores.csv` | The score ledger did not carry those columns, and it only covers scored items. Timings belong on the item-health census. | Fowler |
| Serving `state/item-health/` directly | It carries `canonical_url`, `url_key` and untrusted `detail`. The browser gets only the published telemetry projection. | Fowler, Rule #11 |
| A day-level bar of the confidence bands | It charted a constant, shared its tokens with the item mark so it trained the reader to ignore the mark that varies, and printed a sentence the item level had already retracted. | Jony, Reader |
| A day-level sentence counting how many summaries may not match | The bar in prose. A number spread over hundreds of items a reader can neither locate nor act on. | Jony, Reader |
| A cross-topic "top stories" strip on the day page | The payload carries no cross-vertical rank, so the page would have to invent one at read time. The page renders; it does not think. | Jony |
| Truncating a long day to protect the two-minute budget | Ordering and hierarchy protect the budget. Dropping items a run published is not a typography fix. | Jony |
| A colour per topic | A category-to-colour map that must be re-picked every time the taxonomy changes, carrying nothing the count does not. | Jony |
| A "newest first" or "best first" sort control | The published order is global and identical for every reader. A sort control makes a shared link show the recipient a different page. | Jony |
| An estimated reading time per topic | An unmeasured number printed as a fact, and it changes nothing a reader does. | Jony, Rule #10 |
| One paragraph per later run in the day notice | Three runs printed three near-identical sentences saying one fact. One total says it once. | Jony |
| Grouping a day that ran to a single topic | One heading over the whole page states what the page already says, and it puts items behind a link that leads back to the same list. | Jony |
| A failure bar scaled to the window's own maximum | With one day in view the bar normalises to itself, so a 12% failure rate and a 90% one both fill the panel. | Jony |
| A failure rate carried only by an SVG `<title>` | A tooltip does not fire on touch and does not survive the screenshot an operator pastes into an issue. | Jony |
| A bar chart for a window holding one day | A chart of a single value is a rectangle. The number is the panel. | Jony |
| Rendering every failed row in the window | 800 rows measured 7824px and pushed the compression chart to document y=9105. The rows are on demand. | Jony |
| A virtual-scrolling failure table | A dependency and a scroll-position bug for something a cap and a button already solve. | Jony |
| A per-day stacked bar list for stage timings | Thirty days is about 150 rows and no trend, and the trend is the only question the section is asked. | Jony |
| `uplot` on the compression scatter | It drew a second, smaller chart beneath a complete SVG, and the pan and zoom it was bought for live in the viewport control, not in the plot. | Jony, Rule #8 |
| A drawing library for the console charts - `echarts`, `@observablehq/plot`, `chart.js`, a component library | 336 KB gz on canvas, 128 KB gz and a DOM shim to prerender, 67 KB gz on canvas, and a component set is worst of all where every chart is bespoke. All of them own the element and the theme; the console needed the arithmetic. | Jony, Carmack |
| `d3-scale` from a CDN | The HTTP cache is partitioned per site, so the shared-cache argument is dead, and the repo's `script-src` allows `self` only. | Carmack |
| Fixing the units by hand instead of taking the dependency | `.nice()` and `ticks()` are exactly the part hand-rolling gets wrong, and an axis labelled 0, 37, 74 is an axis nobody reads a value off. | Jony |
| A `console.chart_width` default per chart shape | One knob names the width the reading column leaves; a chart sharing a row divides it. Four knobs would be four ways to disagree about one column. | Jony |
| Gating HTML weight in the same script as first-load JS | The document is owned by the payload work. One gate over both would make two independent workstreams fail each other's builds. | Carmack |
| Putting the first-load ceilings in `config/` | An operator has no reason to raise the weight a reader pays, and a budget that can be edited to fit the build is not a budget. | Carmack, Rule #2 |
| A `run.success_floor_pct` reference line on a stage failure panel | That floor is a published rate over attempted items; a stage panel is a different denominator. A wrong reference line is worse than none. | Jony |

## See also

- [layout.md](layout.md) - the routes, the dated addresses and retention.
- [../sources/health.md](../sources/health.md) - the feed ledger the console renders, and the quarantine rule it mirrors.
- [../../reference/github-actions.md](../../reference/github-actions.md) - the four-run cadence that gives the strip four squares a day.
- [../../concepts/digest.md](../../concepts/digest.md) - what an item carries and the visual rule.
- [../../concepts/design-system.md](../../concepts/design-system.md) - typography, tokens and the colour rule.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shell's obligations and the four states.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload this renders.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1, section 0 and section 12.
