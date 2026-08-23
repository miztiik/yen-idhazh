# Published Frontend

**Last Updated**: 2026-08-23

The reader's surface: what is built, what deliberately is not, and the rulings behind both. This page is the living record for the digest page, the archive, the eval dashboard and the console.

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

**The colour the owner asked for is spent once, at the top, as an aggregate**: a three-segment bar with the counts beside it in words. "How much of today can you trust" is a day-level question, and that is the honest place for a colourful instrument.

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

**The grid is one column per day and one square per run.** Four runs a day means four squares, oldest at the bottom of the column. A month of pipeline history fits above the fold, and the shape of a problem - one bad afternoon, or every run since Tuesday - is visible before any number is read.

Three colours, and the boundaries are read from config rather than chosen by the page:

| Colour | When |
| --- | --- |
| Green | The run completed, nothing failed, and the source list was current |
| Amber | Something is worth a look: an item failed, the run did not complete, the source list was stale, or nothing was attempted |
| Red | The run failed, or its success rate fell below `run.success_floor_pct` |

**The red threshold is the same knob CI uses to decide whether a run opens an issue.** A red square and an open issue can never disagree, because there is one number and both read it.

**A skipped item is not a failure.** An article already published, or one a feed repeated, is skipped by design, so the rate is over what was *attempted*. Counting skips would paint a healthy day amber for doing its job.

Beneath the grid is **every feed that failed at least once**, worst first, with its attempt count, its last outcome and how close it is to quarantine. A feed with a clean record is not listed: the operator came here to find what is broken, and a list naming all seventy sources hides the four that are. The failing rule matches `FeedHealthRow.failing` in the contract exactly - a `200` that parsed to no entries counts as a failure, a `robots.txt` refusal does not ([../sources/health.md](../sources/health.md)).

**The console reads committed records in two ways.** The run grid, feed list and
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
that exist instead of drawing empty calendar space. JavaScript enhances the
server-rendered SVG with pan and zoom. Arrow keys pan, and `+` / `-` zoom, from a
labelled focusable control with a visible focus ring. If a telemetry month is
absent or cannot be parsed, that month is a gap in the charts. It is not
interpolated, and it never white-screens the console.

The item-health viewport has three parts:

- Failure panels: fetch, extract and summarize failure rates as separate bars.
  The label carries the raw pair. Thin denominators use outlined bars below
  `console.min_attempts_for_rate`. Colour is spent only on a failure.
- Failed item list: a panel chip filters this list, because after a spike the
  operator needs rows.
- Compression scatter: source words against summary words, with the
  `summarize.bands` step function as the reference band and a distinct mark for
  truncation-flagged scored items.

## Design rationale

Prerendering everything is the decision the rest hangs off. It was chosen over a runtime fetch of `digest.json` because it collapses four problems into zero: the loading state stops existing, the request budget stops being a budget, a contract-invalid payload becomes a build failure instead of a reader-facing error, and the page keeps working with JavaScript off. The cost is one framework dependency and a build step that enumerates committed directories. Authority: Jony ([../../../.github/agents/jony.agent.md](../../../.github/agents/jony.agent.md)).

Spending the colour at the day level rather than per item is the resolution of a genuine conflict between an owner instruction and a persona's ruling. The owner asked for a colourful confidence signal; Reader argued that per-item confidence badges are the project talking to itself. Both are satisfied by putting the aggregate where it is a real instrument and the per-item signal where it is proportionate. Authority: owner (section 0), designed by Jony, constrained by Reader.

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
| A second threshold for the red square | CI already reads a success floor to decide whether to open an issue. Two numbers answering one question drift, and then a red square and an open issue disagree. | owner |
| Counting skipped items against a run's health | An already-published article is skipped by design. Counting it would paint a healthy day amber for doing its job. | owner |
| Reading stage timings from `state/scores.csv` | The score ledger did not carry those columns, and it only covers scored items. Timings belong on the item-health census. | Fowler |
| Serving `state/item-health/` directly | It carries `canonical_url`, `url_key` and untrusted `detail`. The browser gets only the published telemetry projection. | Fowler, Rule #11 |

## See also

- [layout.md](layout.md) - the routes, the dated addresses and retention.
- [../sources/health.md](../sources/health.md) - the feed ledger the console renders, and the quarantine rule it mirrors.
- [../sources/freshness.md](../sources/freshness.md) - the six-hour cadence that gives the grid four squares a day.
- [../../concepts/digest.md](../../concepts/digest.md) - what an item carries and the visual rule.
- [../../concepts/design-system.md](../../concepts/design-system.md) - typography, tokens and the colour rule.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shell's obligations and the four states.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload this renders.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1, section 0 and section 12.
