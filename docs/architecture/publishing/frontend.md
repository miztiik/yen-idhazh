# Published Frontend

**Last Updated**: 2026-09-10

The reader's surface: what is built, what deliberately is not, and the rulings behind both. This page is the living record for the digest page, the archive and the console.

Concept-level *why* lives in [../../concepts/digest.md](../../concepts/digest.md), [../../concepts/design-system.md](../../concepts/design-system.md) and [../../concepts/ui-shell.md](../../concepts/ui-shell.md). This page is the *shape*, and it records where the owner, Jony and Reader disagreed and how it was settled.

## Six documents, and a seventh that answers every dated address

Six routes are generated at build time - `/`, `/archive/`, `/evals/` and the three console routes - and `adapter-static`'s fallback, `404.html`, answers everything else. SvelteKit with `adapter-static`, `prerender = true` declared on each of those six, and no `entries` reading the digest tree anywhere. `/`, `/archive/`, `/404`, `/evals/` and the console inline everything they draw; a dated URL is the fallback document, and the page fetches the served day for the whole of it.

**Until 2026-09-09 every route was prerendered, and that cost six documents a published day.** 20 dated pages and 96 topic pages, each with a `__data.json` twin, all rebuilt on every run because a document holding a seed of a day changes when the day does. Measured on a real build, a developer machine, 2026-09-09, `BUILD_VERSION` pinned across both arms: 796 files and 116,050,183 bytes before, **572 files and 101,880,352 after** - 224 files and 14,169,831 bytes, 12.2 percent of the built site. 123 documents become 7 and 121 `__data.json` files become 5. **The document count no longer moves when a day is added**, which is the whole of it.

Three consequences, and the third one changed shape again when the dated routes moved into the browser:

- **The reading path makes at most one request, and a dated page now needs it.** `/` is one document with the newest day in it and it is done. A dated URL is a cold load of the fallback, the bundle and then the day payload - and only a typed link, a bookmark or a shared link pays that, because in-app navigation never asks the host for a dated address (owner decision, 2026-09-09). What a dated page does not do is wait: the fetch is started by the page component rather than awaited in its `load`, so the chrome and the date are on screen while a payload that runs to 1.9 MB comes down. Awaiting it in the `load` was the simpler code and a blank page.
- **There is one loading state and it is a sentence**, not a spinner and not a skeleton. Past `ui.payload_slow_ms` a dated page says the day is still loading, and a fetch that fails says so and offers a retry ([../../../frontend/src/lib/components/PayloadState.svelte](../../../frontend/src/lib/components/PayloadState.svelte)). The build-time payload loader is still exactly one module under `frontend/src/lib/server/`; the browser's is a second one under `$lib/assist/`, and it reads the served projection rather than the committed day.
- **A day that fails its contract cannot be merged, and since 2026-09-01 it could not be caught by building either.** `python -m idhazh validate-days` opens every story of every committed day instead - in `ci.yml`, and immediately before the commit in both publishing jobs, because `ci.yml` never starts from a push the pipeline made. **The guarantee is weaker than the one prerendering gave and that is stated rather than hidden.**

**What a cold dated load costs the reader, priced here because the ruling that allowed it did not.** Owner decision D11 accepted the cold-load path on 2026-09-08 and settled the two losses it named - the link preview card, and search-engine indexing of dated URLs. It said nothing about the frame. Until 2026-09-09 a dated URL was a prerendered document, so the chrome, the date, the topic row, the leading block and a seed of stories were in the first bytes and painted with no script at all. Now **a cold dated load paints nothing until the bundle has booted**, because the fallback's body is a boot script; then the chrome and the date; then the stories when the payload lands. Two waits where there was none, and only the second one has a sentence. In-app navigation is unaffected. **The first wait is what the 116 documents were paying for**, and it lands on exactly the reader who arrived on a typed address, a bookmark or a shared link.

**A dated URL with no script is blank, and that is answered rather than accepted.** The fallback's body is a boot script and nothing else, so [../../../frontend/src/app.html](../../../frontend/src/app.html) carries one `<noscript>` line at the foot of the body: a page for one day opens with JavaScript, the newest digest is on the front page, and every published day is listed in the archive. Both of those render complete with no script at all. It is last in the body and it claims nothing, so on the pages that do render it sits under what the reader came for and is true there too. **What a script-free reader loses is real**: a topic pill used to be one click to a prerendered desk, and it is now one click to that line. Reader's own rule decided it - a blank page is a site that looks broken to the one reader who will never report it.

**Four files are fetched, and one of them is the whole of a dated page.** The
console reads older telemetry shards when an operator pans back. The archive
reads the month index behind its story list, that month's sibling vector file
when a reader asks to search, and the day payload behind a result it is showing.
Both reading routes read that same day payload - since 2026-09-01 for the
stories past a seed, and since 2026-09-09 for all of them. `/` still makes no
request at all. The rule was that a reader waits for nothing to read the news,
and it is now that they wait for nothing on `/` and for one file on a date.

The build-time loader lives under `frontend/src/lib/server/`, which is the framework's own guarantee that it can never be bundled into anything a browser receives. A `+page.ts` may not import from it at all, which is what makes the dated routes' move checkable rather than promised.

**A tree with no day in it still builds, and nothing has to be excused for it to.** The six prerendered routes read no committed day to decide whether they exist, so every one of them produces a page on every build. [../../../frontend/prerender-guard.js](../../../frontend/prerender-guard.js) is what is left of the guard that used to tell a fresh clone's empty digest tree from a dated page that went missing: an unseen prerender route is now a defect with no innocent reading, and the handler exists for the sentence a failing build prints. `handleUnseenRoutes: 'ignore'` would allow the same builds and every other unseen route with them, silently.

**Whatever the root layout's load returns is inlined into every page beneath it**, so from 2026-09-09 it returns **the config and nothing else** - no day, no date, no field read off one. The home page loads the day it renders. The layout used to return the whole latest day, which put a day of article summaries on the console, on `/evals/`, which draws none, and on every older dated page that already carried its own. Measured 2026-08-26, `gzip -9` over each prerendered page, one tree carrying five published days built twice with only that field differing: `/console/` 406.3 -> 93.0 KB, `/evals/` 315.6 -> 2.4 KB, `/2026-08-23/` 439.6 -> 126.0 KB, and 15749.2 -> 6343.3 KB over all 31 pages. Two builds of the same tree agree to within 0.1 KB. The last two fields it kept - `retention_window_months` for the footer's promise, and `latest` for the empty state's shortcut - went on 2026-09-09, because both are read off the newest day and both therefore rewrote every older page each time one published ([the footer, below](#the-footer-is-its-links-and-nothing-else)).

[frontend/tests/payload-weight.spec.ts](../../../frontend/tests/payload-weight.spec.ts) holds that line. It counts a marker only a day payload carries and fails on any page below the layout that has one. It had one exclusion, `/archive/`, which inlined every committed day on purpose to feed the on-device search; the exclusion is gone from 2026-08-27, and the archive now carries an assertion of its own that it holds **zero** day markers.

**The second line was the guard prerendering used to give free, and it retired with the pages it guarded.** A dated route was exempt from the sweep above while it genuinely rendered its whole day; after the 2026-09-01 split it was held to its own seed, `ui.shell_seed_items` markers on a topic route and that plus `ui.leading_stories` on a day route, so that an exemption could not quietly become a guard that cannot fail - which [layout.md](layout.md) records as a shape this repository has had twice. From 2026-09-09 there is no dated document at all, so there is nothing to hold to a seed: the sweep runs over the six documents a build writes, every one of which must carry zero day markers. `/` is deliberately not held to anything: it keeps the whole day inline for ever, it is one document per build rather than one per published day, and a ceiling there would cap the news.

**`/` is also the one place the golden principle has an open exception, and it is recorded rather than closed.** Owner ruling D2 of [the shell-and-fetch plan](../../../TODO/20260908-shell-and-fetch-plan.md) says shell plus fetch "admits no special case, on the home page and the console alike" (2026-09-08). The console took it - it fetches its months and its verdict. `/` did not: it still prerenders a whole day inline, and the bundle gate reports it at **180,085 bytes `gzip -5`, counted and never capped** - 3.5 times the migrated `/console/`. Each half of that has a reason. The home page is what a stranger meets first, it is the one route that reads complete with no script at all, and one document a build is not one a published day, so it costs the site nothing that grows. **But it is a special case, D2 says there are none, and no row of that plan resolved the two.** Closing it has a reader cost either way, and the decision is nobody's yet.

**The same rule bites a chart, and it is the reason a `load` never returns an
echarts option.** A chart is drawn to SVG on the server and the sentinel
colours in it are swapped for custom-property references on the way out
([../../concepts/design-system.md](../../concepts/design-system.md)), so the
finished SVG is safe. The `option` the live chart hydrates from is not: it still
holds the magenta sentinels, and anything a load returns is serialised into the
document. Hand one across and the page ships a colour no reader may ever see.
[frontend/tests/charts.spec.ts](../../../frontend/tests/charts.spec.ts) scans
every built page for the sentinel pattern and fails the build, which is how the
Machine route's first draft was caught on 2026-08-31 - 981 gzipped bytes of
option JSON in the document, and a colour leak underneath them. Every console
route rebuilds its options in the component from the arrays the load returned;
the server sends the drawing and the numbers, never a drawing instruction.

| State | When | What ships |
| --- | --- | --- |
| Ready | Normal | Prerendered HTML on `/`, with the whole day in it. A dated URL is one shell and the day it fetched |
| Empty | Payload exists, no items | "Nothing was published for *date*", with plain copy that does not point at a notice that may not be on the page |
| Missing | The host has no payload for that date | A named screen that offers the archive and the front page. **Never a redirect to today** - a reader who cannot tell a dead link from a live one has lost the ability to trust any link. It was decided at build time until 2026-09-09 and is decided in the browser now, off a 404 or a 410 from the host |
| Waiting | A dated page has asked for its day and it has not arrived | Nothing at all until `ui.payload_slow_ms`, then one sentence. Never a spinner, a skeleton or a bar |
| Unreachable | A dated page's fetch failed for any reason that is not the host saying it has no such day | One sentence naming the day, a retry, and the days this device still holds |
| Unpublished | No day published at all - a fresh clone | The build succeeds. `/` says "No digest has been published yet" and `/archive/` says "Nothing has been published yet". There is no dated page to link to, so neither offers one |
| Invalid | Payload breaks its contract | `idhazh validate-days` fails, in CI and before the publish |
| Degraded | Low band, source-limit sentence, no visual | The common case, rendered inline. Not an error |

**Missing and Unreachable are two sentences and they never merge.** Telling a reader a day was never published when their train went into a tunnel is a lie they can check. What separates them is now the host's own answer: a 404 or a 410 for `digest/<Y>/<M>/<D>/digest.json` is the host saying it has no such day, and every other failure is the connection. [NotHere.svelte](../../../frontend/src/lib/components/NotHere.svelte) is the one copy of the Missing screen - the framework's error page renders it for a status it was handed, and a dated page renders it when the host says it has no such day, because a reader cannot tell those two apart and must not be told different things by them.

**The table has a machine-readable half, and it is `data-payload-state`.** The live region that [PayloadState.svelte](../../../frontend/src/lib/components/PayloadState.svelte) renders on every state carries the current `DayStatus` - `loading`, `slow`, `ready`, `unreachable` - as that attribute, and Missing is absent from it because that screen is `NotHere` and this region is not on the page at all. The route sets the status and the day in one callback, so **`ready` lands in the same flush as the stories**: it is the only honest "the whole day is in this document". This is what a check measures a dated page by, and there is nothing else it can use - one shell answers every dated address, so the HTML a load or a reload returns carries no stories, offline included, where the worker answers the fetch instead of the host. A count taken at the load event is a count of the shell, and whether it happens to find the day is a property of the machine: measured 2026-09-09 on a developer machine, three runs of the offline arm, the day was already on the page every time - the same read on `ubuntu-latest` found nothing and took `main` red. The wait is one helper, [../../../frontend/tests/support/day-ready.ts](../../../frontend/tests/support/day-ready.ts), rather than the nine longhand copies that let one spec be written without it.

The home page uses the newest committed payload as the day it can prove. It never
uses the build clock as "today". If the site is rebuilt after a quiet or failed
run, the page still names the payload date it actually renders, and the empty
state offers the archive plus the latest published day when one exists.

## A story carries its drawing, so the drawing can read the page

Until 2026-09-05 every published chart shipped inside an `img`. An SVG in an `img` is a separate document: it reads none of the page's custom properties, so the only colours it could ever have are the ones the renderer baked in. Those are black axis type, `#888` ticks, `#ddd` grid lines and a `#4c6ef5` bar - fine on white, and on the dark theme black type on a near-black card. **It was the loudest reader-facing defect on the site and no gate could see it**, because every check the drawing had was about whether the file was served. The grid lines are in that palette and were never in a published drawing: the census below counted 0 of 351.

The fix is the carrier, and it changes no backend byte. `dayShell` reads the file off disk for the stories the prerendered document carries and hands the markup over with the story; [ItemVisual.svelte](../../../frontend/src/lib/components/ItemVisual.svelte) puts it in the document and repaints it from the page's own tokens. **A presentation attribute has the lowest priority in the cascade**, so a stylesheet rule wins over `fill="#000"` with no `!important` and with nothing added to the file - the drawing keeps saying what it said and only the paint moves. Four groups, four tokens:

| What is drawn | Token | Why that one |
| --- | --- | --- |
| The bars (`.mark-rect > path`) | `--chart-1` | The categorical chart ramp, first stop. It holds no green, amber or red, so a bar cannot read as a status |
| Axis labels and the axis title (`.mark-text text`) | `--color-text-secondary` | Type on the card, read the way the reader note above it is read. The chart ramp is for marks that carry no word |
| Ticks and the axis line (`.mark-rule line`) | `--chart-axis` | The token every console chart already draws an axis with, so there is one answer here rather than two |
| Grid lines (`.role-axis-grid line`) | `--chart-grid` | Quieter than the axis that bounds it. No published drawing carries one, so this rule is insurance - the census below says why it is kept |

The drawing that is not a chart needed none of them. The diagram renderer already paints itself in `currentColor`, which inside an `img` could only ever resolve to black; inlined it inherits the page's ink, and the component sets `color: var(--color-text)` on the root so that is a decision rather than an accident. What it still bakes is a `#8a8f98` connector stroke: measured 2026-09-05, that is 5.42:1 on the dark surface and 3.25:1 on the light one, which clears the 3:1 a non-text graphic needs and does not clear 4.5:1. It carries no words, so nothing a reader must read is at that ratio - and the renderer, not the carrier, is where the number gets fixed.

**What the reader gained, as contrast on the dark card.** Measured 2026-09-05 against `--color-surface`: the axis type was black on `#141922`, which is **1.19:1** where readable text needs 4.5:1, and it is now 7.86:1. The bars went from a fixed `#4c6ef5` to 5.93:1 on dark and 6.35:1 on light. The light theme was always fine, which is why this survived every review: the defect was invisible to anyone reading in the theme the drawing was drawn for. The grid lines were `#ddd` at **12.97:1**, which is the loudest thing in a figure - but that figure is the canary chart, and no reader has ever been served one. The census below is where that number comes from.

**Inlining markup means the markup is checked, and since 2026-09-09 the build checks almost none of it.** `refusedDrawing` in [../../../frontend/src/lib/payload/drawing.ts](../../../frontend/src/lib/payload/drawing.ts) is the guard: it refuses a file that is not a published visual path and a file whose markup carries anything a document should not, and a refused drawing is simply not drawn. The module and the rule did not change when the dated routes moved - **where it runs did.** `withDrawing` is called from `dayShell`, and `dayShell` is now called by `/` alone, so the build reads and refuses over the seed of the newest day and nothing else. Every other drawing on the site is checked in the reader's browser instead, by the same function, on the day they ask for it. So the guarantee is the same and the place it is enforced is not: a bad SVG committed for an older day fails no build and no gate, and is caught on the device of the reader who opens that day (row #14 decision 4 of [the shell-and-fetch plan](../../../TODO/20260908-shell-and-fetch-plan.md), Fowler, 2026-09-08). It is the same trade `validate-days` records above - the build stopped being the place a bad day is found, and it is written down rather than assumed.

**Every published drawing is a bar chart, and not one of them carries a grid line.** Counted 2026-09-05 over all 351 drawings the 15 committed days hold: 351 carry a bar, an axis label and an axis line, 0 carry a grid line, and 0 carry a mark of any other type - no line, no area, no arc, no point, and no diagram. It is not an accident of the corpus. `chart_spec` in [visual_planner.py](../../../backend/idhazh/visual_planner.py) writes `"mark": {"type": "bar"}` and `"axis": {"grid": False}` on every spec it builds, so nothing else can reach a reader while that function is the renderer.

Two consequences, and they point opposite ways. The `--chart-grid` rule is exercised only by the canary chart, whose spec is hand-written in `build_canary_day.py` and leaves the grid at the Vega-Lite default - so `item-visual.spec.ts` asserts a rule that no published page has ever used. **It is kept anyway**: it is four lines, it costs a reader nothing, and the day a renderer starts drawing a grid is the day the dark theme would break again without it. The other consequence is the one nothing here can fix. Forty-three drawings on 2026-08-31 - the heaviest committed day, 43 across 601 stories - are 43 distinct files that are all the same picture, and a reader scrolling that day meets one bar chart after another. That is the renderer's shape, so it is the renderer's plan to change; this page records the number so the plan that replaces it does not have to re-measure.

**Only the seed inlines.** A day has published 621 stories; the committed drawings average 12.7 KB, so a document holding every one would be roughly a megabyte of markup on the surface a phone loads first. The seed is small and the drawings on it are rarer than the stories: measured 2026-09-05 over the 15 committed days, a seed holds 0.87 drawings on average and 3 at most, which is 11.8 KB of markup a day. What that cost the reader, measured on the same box on the same day, `gzip -9` over the heaviest prerendered page of each route family:

| Page | Before | After | Change |
| --- | --- | --- | --- |
| `/` | 283,844 B | 287,581 B | +3,737 B, 1.3 percent |
| `/<date>/` | 23,670 B | 30,610 B | +6,940 B, 29.3 percent |
| `/<date>/<topic>/` | 18,222 B | 26,145 B | +7,923 B, 43.5 percent |
| Whole site, per published item | 16,224 B | 16,653 B | +429 B, 2.6 percent |

A day page went up by about a fifth of what a single round trip costs on a slow link, and each inlined drawing removes a request - so for a story on the first screen the page is very likely quicker, not slower. **The drawing lands in the document twice**, once as markup and once inside the serialised `load` data every prerendered page carries, which is why the page grew by more than the file weighs. Rounding the renderer's 17-digit coordinates would take 4.0 percent of the raw bytes and 51 gzipped ones off a drawing, measured, so it is not worth the code.

**A story past the seed fetches the same file and inlines the same markup.** The `img` is deleted rather than kept as a fallback: an SVG inside one can never read the page, so keeping it would leave the defect reachable and put two treatments on one scroll. The story's `path` is on the served day already, so this costs no new field and no new route - it is the request the `img` was making, answered into the document instead of into a separate one.

**The fetch waits until the story is nearly on screen**, because the `img` carried `loading="lazy"` and a plain fetch on mount throws that away. The case where that hurts is not the ordinary one. A reading page draws twelve stories and the seed is fifteen, so a reader who lands on `/<date>/` fetches **no** drawing at all until they press for more, and each press brings twelve stories carrying **0.66 drawings on average** - measured 2026-09-05 over the 15 committed days, 351 drawings across 6,425 stories, which is 5.5 percent. The case that hurts is a deep link: `/<date>/#<story>` pages the stream down to that story, so the whole prefix mounts at once, and on 2026-08-31 - the day carrying the most drawings, 43 across 601 stories - that is up to 43 requests and 534 KB opened together, against the day payload the same page is still waiting on. An `IntersectionObserver` with a `100%` root margin holds it to the drawings within one screen of the reader. The margin is a percentage rather than a pixel count, so a phone asks one phone-screen early and a desktop one desktop-screen, and there is no number to maintain.

**One watcher serves every story that is waiting.** A watcher per story is a cost that rises with the day rather than with the code, which is the shape Rule #12 refuses: nobody writes a line and the page gets more expensive, because the run published more stories. [reveal.ts](../../../frontend/src/lib/reveal.ts) holds one `IntersectionObserver` and a map from element to the work that element waits for, so a story registers on mount and is dropped from both when it goes. Measured 2026-09-06 on a developer machine against the built site, `/2026-08-31/` with all 601 stories revealed and all 43 drawings fetched: **44 observers before, 2 after**. One of each pair is SvelteKit's own link-preload watcher, so ours went from 43 to 1 - one per drawing, to one for the page - and every drawing still arrived. The count is deterministic rather than sampled; the new arm returned 2 on each of three runs. The module imports nothing, for the same reason [drawing.ts](../../../frontend/src/lib/payload/drawing.ts) does: a spec can then drive it in a plain `node` process, which is the only way this rule can be checked at all. The canary day is eight stories against a seed of fifteen, so no canary page ever holds a waiting story and no browser check can reach this path.

**A story that leaves the page takes its request with it.** Unmount drops the watch and aborts the fetch, so a reader who pages away is not still paying for markup nothing will show, and a response that lands after the story is gone is discarded rather than written into a component that no longer exists. An aborted fetch is silent: it is the reader's own move, not a fault, and logging it would fill the console on every page change.

**A drawing that does not arrive leaves the story shorter, and nothing else.** No broken-image glyph, no grey box, no skeleton - which is the shape two stories in three already have, and the reason the placeholder was refused in the first place: a grey rectangle makes "this story needed no picture" look identical to "the picture failed". The element that waits for the fetch is a zero-height `div` with no border and no background, so a story that never gets its drawing is exactly as tall as a story that never had one.

**And the drawing has to survive the rest of the day arriving.** A reading route sets `arrived = whole.items` when the fetch lands, which swapped the seed out for the served copy - and the served copy carries no markup, by design. Measured 2026-09-05 on `/2026-09-04/` before the fix: the document held an inline drawing and the page held an `img` a second later, which is the defect this row exists to remove, arriving one second late. `keepDrawings` in [day-shape.ts](../../../frontend/src/lib/day-shape.ts) re-attaches the seed's drawings by story id, and both reading routes call it at the one line where the list is replaced. It lives beside `orderByTime` rather than in the fetch module because that module imports `$app/paths`, and a spec that imports `$app` fails the whole browser suite at load - so a rule with no test would have been the alternative.

**Inlining moves the trust boundary, and the check is at the move - on both sides of it.** Inside an `img` an SVG is inert whatever it holds. In the document it is markup in our own origin, and a chart's labels are written by a model that read a stranger's page (Rule #11). So a drawing is refused if it does not open on an `<svg>` element or if it carries a script, an inline handler, embedded HTML, a link out, or a fetched image - and its path is matched against the shape `visual_planner.py` writes before that path is joined onto a directory or onto `base`, because it is about to become an address. [drawing.ts](../../../frontend/src/lib/payload/drawing.ts) holds both checks and imports nothing, which is what lets the build and the browser run the same code: `node:fs` in that graph would put the build's file reader in a browser bundle, and a `$lib` alias would put a Vite alias in a plain `node` process. **The browser's copy is the one that matters**, because that is the path a stranger's bytes travel with nobody watching; two copies of one refusal is how the two drift. A refused drawing is logged by name and not drawn, which is a degrade rather than a failure: the story is shorter. [frontend/tests/item-visual.spec.ts](../../../frontend/tests/item-visual.spec.ts) plants each of those six shapes in a copy of the canary tree, asserts the markup never reaches the story and that the same markup would be refused on the fetch path too, with a control that the ordinary drawing does inline - without it every refusal case would pass on a build that inlined nothing.

**No browser check can reach the fetch, and that is a property of the fixture.** The canary day is eight stories against a seed of fifteen, so every story on it is seeded and nothing on that build asks for a drawing. What the canary suite does hold is the page-wide count: zero `<img>` under `main`, which fails the moment a story is left on the old carrier. The fetch itself is checked against the real build, on a committed day longer than the seed.

**The oracle is an equality against a token, never against a hex.** The same spec plants a probe element, sets its `background-color` to the property the stylesheet routes a mark to, and compares what the document computed with what the mark was painted. The two themes give that property two different values, so one baked colour fails one arm whichever colour it is - and a test written against a literal would need editing every time the palette moves, which is how a colour test stops being one.

## Components are swapped by props, and ordered by config

Every component takes a validated slice of the day payload as props and returns markup. No component fetches, no component reads global state, no component knows a route. Swapping one means writing a file with the same props and changing one line.

Page order is `config.ui.sections`, a registry id list. **Reordering the page is a config edit, not a code change.** That is the honest version of "modular".

What is deliberately *not* built is a slot system for moving components left and right. On the surface that matters - a phone - there is no left and no right; there is one column. A layout engine for one column is unbounded QA against a reader who does not exist, and a per-reader layout would break the promise that a shared link shows the recipient what the sender saw. Two named flips are granted where left and right are real: `digest.visual_side` and `digest.source_mark`, both in `config/appearance.json`, which owns everything the published surface is drawn from ([../../concepts/config.md](../../concepts/config.md)). `visual_side` sat in `config/idhazh.json` as well, with a different value, until 2026-09-05; the pipeline file dropped its copy rather than the two files continuing to name one knob twice.

## Theming

Class strategy, not media query. **Dark is the base and light is the override.** `:root` in `frontend/src/styles/tokens.css` carries the dark values, so a document with no `data-theme` attribute - no script yet, or no script at all - paints dark on its first frame. `[data-theme="light"]` comes after it in the file and wins on source order, because both selectors match at the same specificity.

Two themes, and one control with two states: a moon button that flips between them. The glyph never changes - the page is the state indicator, and an icon that changed with the theme would be a second and weaker copy of it - so the `aria-label` names the action (`Switch to the light theme`) and there is no `aria-pressed`. A choice is always stored as `light` or `dark`; the default is never encoded as the absence of a key, or the day the default moves every reader who chose it moves with it without being asked.

A seven-line inline script applies a stored `light` before first paint. It is the one inline script this site carries, and it now exists only for that reader: everyone else is already dark from the stylesheet, so the script has nothing to correct. Its failure branch sets `dark`.

**A theme is exactly one `[data-theme="x"]` block supplying the token names in `frontend/src/styles/tokens.css` and nothing else.** The mechanism ships; two themes ship. A third means re-picking three band colours, eight source swatches and a focus colour and carrying them forever for a reader nobody has met.

`system` was a third toggle state until 2026-08-31. It was removed with `ThemeChoice.SYSTEM`, `watchSystem` and the sun glyph, on the owner's decision that the site starts dark. What a reader loses is a theme that follows their device at sunset; what they get is a control with one obvious action instead of three. `config/appearance.json` still names the default in `digest.theme_default`, and a config that still says `system` reads as `dark` (`CLAUDE.md` section 11).

The browser's own chrome follows the page. `app.html` ships one unconditional `theme-color` tag holding the base theme's background, because an installed window reads it at launch before any script has run and the page is dark whatever the system prefers - a media-scoped pair would be wrong for every reader whose system says light and who has chosen nothing. `apply` in `$lib/theme` rewrites that same tag from the resolved `--color-bg`, so a reader who picked light does not sit under dark chrome.

The oracle is [../../../frontend/tests/theme.spec.ts](../../../frontend/tests/theme.spec.ts). It loads every route three ways - no stored choice, `light` stored, `dark` stored - and asserts that every change to `data-theme` happened while `document.body` was still null, which is what makes it a statement about the first painted frame rather than about the settled one. A fourth arm runs with JavaScript switched off, where there is exactly one frame and it has to be dark.

## Installability

`frontend/static/manifest.webmanifest`, four PNG icons and the `theme-color` tag above. That is the whole feature, and the doctrine around it - including the ban on `Notification` and `PushManager`, and why there is no service worker - is in [../../concepts/ui-shell.md](../../concepts/ui-shell.md).

The icons are generated once from two committed SVG sources, `app-icon.svg` and `app-icon-maskable.svg`, using `sharp` installed with `--no-save` and removed afterwards: the PNGs are the committed artefact, not the toolchain. The maskable variant is a second drawing rather than a crop, with the mark inside the central 80 percent, because a platform that crops the square icon takes the ends off the bars. Measured 2026-08-29: 48,788 B for the six files, of which 46,869 B is raster.

Every path in the manifest is relative, which is what makes the project path a non-issue: `start_url` and `scope` are `.`, and each icon `src` starts `./`, so all of them resolve against the manifest's own URL. SvelteKit rewrites `%sveltekit.assets%` per page depth, so the root emits `./manifest.webmanifest` and a dated page emits `../manifest.webmanifest`, and both land on the same file.

## The confidence signal, and the argument about it

This is where Reader and the owner disagreed, and it is worth recording properly.

**Reader's objection, in their words:** a per-item confidence badge is "the project talking to itself in public". A label that changes nothing a reader does is decoration with a serious face; a page where most items are marked low "stops reading as honesty and starts reading as a confession"; and the day a `high` item is wrong, the label has actively talked the reader out of the suspicion that would have caught it.

**The owner asked for a colourful confidence indicator, and owner approval supersedes an agent** ([../../../CLAUDE.md](../../../CLAUDE.md) section 0). What ships is Jony's proportionate version, which answers most of Reader's objection without discarding the ask:

| Band | On the item |
| --- | --- |
| `high` | **Nothing.** Ink spent on the absence of a problem, and colour-only |
| `medium` | A 6px dot and the sentence named by `band_reason`. An older payload with no reason falls back to "Mostly matches the source" |
| `low` | A 6px dot and the sentence named by `band_reason`, in the low token. An older payload with no reason falls back to "May not match the source" |

It sits **in the item's footer, after the summary and beside the source link** - never above the title. A caveat above the title pre-judges an item before the reader has read a word. The reading order is: what it is, what it says, then where it came from and how sure we are.

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

**The mark is a ring on the item's leading edge, and it carries the read state.** It was a `1.25rem` square in the meta line until 2026-08-31, and that line moves into a 14rem right rail at the side-rail breakpoint - so on a wide screen the read indicator sat 14rem from the title it qualified, paired with nothing. It is now `1.75rem`, a circle, in a leading grid column at every width, with the letters at `--text-xs` and weight 600. The size is in `rem` so the ring grows with a reader who raised their browser's text.

Unread is filled with the source's own swatch and read is hollow, with a hairline in both states - `--color-rule-strong` unread, `--color-rule` read. **The border is never the swatch**: at 1px against the card a swatch reads about 1.1:1, so a coloured ring would be a ring nobody can see. The swatch bound and why it is 1.5:1 rather than 3:1 are in [../../concepts/design-system.md](../../concepts/design-system.md).

When `ui.source_mark` is off the mark is not drawn, and the read state falls back to the title's weight and colour alone. That is what turning a scanning aid off costs, and the knob's owner is the one turning it.

Reader named one thing an item did not carry that they wanted before they would share it: **what kind of source it is.** "A company said its product is faster" and "a reporter measured it" are not the same claim, and they were arriving in the same typeface. `source_kind` is now on the payload, and the item prints it beside the publication name on the eyebrow, only where the speaker has a stake worth naming.

**Four kinds get named, since 2026-09-01.** `announcement` and `community` were the first two; `government` and `research` joined them because a ministry announcing its own policy and a paper nobody has reviewed are also a speaker with something to gain. Over the 12 committed days and 4,598 items on 2026-09-01, that is **340 more items labelled** - 241 `research` and 99 `government` - so 696 in all, 15.1 percent, up from 356 and 7.7 percent. The 340 is the part that holds still; the shares move with every publish.

**`reporting` and `analysis` stay out, and the share is the argument.** The label is a warning, so it only works while most items do not carry one, and `reporting` alone is 79.2 percent of the committed tree. `analysis` is a publication's own reading of a story it does not stand to gain from, which is the line the other four are on the wrong side of. `frontend/tests/item-meta.spec.ts` holds the set and holds the labelled share under a third, so a later widening that turns the mark into wallpaper fails rather than merely looking odd. Authority: Editor, plan row #16.

## The item's facts sit in two places, and the place says what they are about

Until 2026-09-01 every fact about an item was on one line under the summary: the source, the kind, the coverage sentence, the date, the confidence sentence, `Listen` and the link out. Seven things, and the four a reader uses to decide whether to read at all were printed where that decision had already been made.

They now split by what they are a claim about.

| Above the title | Below the summary |
| --- | --- |
| the source monogram, in the item's own leading column | the coverage sentence |
| the desk, as a tinted chip | the confidence sentence |
| the lens chips the item's words earned, in one wrapper | `Listen` |
| who is speaking, and its kind where the kind is worth saying | `Read the original`, at the trailing edge |
| when - a date today, a time on the rail when row #17 lands | |

**The cap is four child elements above the title, at every width.** A line that holds four on a desktop and five on a phone because a chip wrapped in from somewhere else is the failure worth catching, so `frontend/tests/item-meta.spec.ts` drives 360, 801 and 1536 rather than the default viewport. The count is of elements, not of facts: an item that earned three lens chips still spends one slot, because they arrive inside one wrapper, and the kind sits inside the source element it qualifies.

**The monogram is the fourth thing above the title and it is not a child of that line.** Row #12 had already moved it into the item's own leading grid column, where it is level with the eyebrow and beside the title whose read state it carries. Putting it back into the line would undo that and cost a slot, so the ruling's four are read as four things the reader sees above the title, and the mechanical cap is on the line's own children.

**The confidence sentence stays below, and that is the reason for the whole split.** It is a claim about our summary. Printing "our summary leaves out names or figures from the opening" above a headline the reader has not read is a disclaimer on nothing.

**Below the summary is document order, not paint order.** At the side-rail breakpoint the footer moves into a 14rem column beside the prose, as the meta line always did. What the split promises is the order a reader meets the facts in, including with no stylesheet and in a screen reader; where the browser paints them at 1024px and up is [layout.md](layout.md)'s business and row #18 of the reading-page plan revisits it.

**What it weighs: nothing worth a sentence, which is the answer that had to be measured.** Two builds on a developer machine / / node 24.12.0, 2026-09-01, over the same 12 committed days and 4,468 items - one of this branch, one of the same worktree with the five changed source files checked out at `8d658de3`. `gzip -9` on each prerendered document, treated minus control:

| Route | Control | This change | Move |
| --- | ---: | ---: | ---: |
| `/` | 195,644 B | 195,630 B | -14 |
| `/<date>/` | 22,683 B | 22,678 B | -5 |
| `/<date>/<topic>/` | 19,478 B | 19,437 B | -41 |
| `/archive/` | 4,604 B | 4,599 B | -5 |
| `/404`, `/console/`, `/console/machine/`, `/console/model/`, `/evals/` | - | - | -1 to +1 |

**The last row is the spread rather than a result.** Those five routes render no item and the change cannot reach them, so what they moved is what one build differs from another by: at most one byte either way. Every reading route moved further than that and all four moved down, so the split is a small saving and not a cost - the divider's markup and the eyebrow's bullet together weigh a little more than the desk chip that replaced them.

**The cap was measured on the real digest, not only on the fixture.** 2026-09-01, the 382-item day of that date, every item on screen at 360, 801, 1280 and 1536 CSS px: at most four elements above the title on every item at every width, at least three, and zero horizontal overflow. The three-child case is an item that earned no lens.

Authority: Susan, plan row #16.

## Topics: pills, and never an empty one

Pills rather than tabs. Tabs assert a fixed exhaustive set of panels; the vertical set is data-driven and varies daily. Pills read as filters over one list, which is what a topic is here.

Since 2026-09-01 they share a panel with the field that narrows the list - one control, described under [The filter bar](#the-filter-bar-topics-and-a-field-in-one-panel).

**Only verticals present in the payload get a pill, with counts.** That is 1-6 controls on a real day, not 18 - and it makes Reader's objection structurally impossible: an empty tab, which reads as broken software, cannot occur because it is never rendered.

Each pill is a link to a prerendered route, so middle-click, share and back all work. Lenses and events are not on the pill row: thirteen mostly-zero controls above seventeen items is a control bar longer than some days.

The committed days still carry no lens, event or entity on any of their 2,237
items because they were not backfilled. The pipeline now assigns all three on
newly extracted articles through the deterministic rule in
[../sources/discovery.md](../sources/discovery.md). The UI ruling holds either
way: sparse, payload-dependent dimensions do not get a permanent control row.

### A lens is a chip on the item, not a control anywhere

Ruled by Jony and Susan on 2026-08-30 after Editor cut the vocabulary to six.
The pill row is unchanged; the item's eyebrow gains a chip.

A lens renders after the desk name as an inert tinted chip carrying the display
name and nothing else. Two chips at most, in the vocabulary's own order, with no
overflow marker - three of "Trade and tariffs" length wrap the eyebrow on a
390px screen, and the reader keeps a one-line eyebrow on every item in exchange
for the third word on a rare three-lens story. An item with no lens renders
nothing at all: the majority have none, the absence is a gap in our keyword list
rather than a fact about the story, and printing it on nine items in ten would
be printing our own homework.

**The desk name beside them became a chip of the same family on 2026-09-01.** It
was a hairline bullet and a word; it is now a tinted fill on `--tint-accent`,
the same tint the lens chips take, set in upper case so the desk we filed the
story under still reads differently from the words the story itself earned. One
tint for every member of a label family is the rule in
[../../concepts/design-system.md](../../concepts/design-system.md), and it is
what let the second of the two ship without inventing a look.

**It is not a link, and the tinted fill is what says so.** An outline would mean
a reader can act on it, and the only thing a tap could do is what the filter
panel two inches above already does. Forcing a 44px tap target into a 12px line
to duplicate a control on the same screen is a loss, not a gain. Authority:
Susan, plan row #16.

**Inert, and the reason is the count.** On a page grouped by desk, "War" beside
a World item and beside an Energy item says those two are the same story seen
twice, which a desk heading cannot say. Filtering to it would be a different
thing: `war` is expected at 10 to 14 percent, so on a seventeen-item day the
filter's usual result is two items - it removes fifteen things the reader came
for and shows nothing scrolling would not have. Raising it to a control would
also need client JavaScript against a 64-byte-per-route ratchet, to do that.

**Events and entities stay off the page**, and the rule behind all three is one
sentence: a classification may go on the page when it says something the title
cannot, **and** being wrong about it costs the reader nothing they can check.
"Acquisition" above a title that says X buys Y is the same fact in a worse
typeface. "Nvidia" on an item whose title does not say Nvidia is a factual
claim resting on one keyword, and a wrong one is a defect. A lens is a broad
frame - disagree with it and nothing is lost. Lenses pass, entities fail, events
duplicate.

**The cross-day question is deferred, with a number rather than a mood.** "What
has been happening on trade" is real and is not answerable by scrolling, and it
belongs on `/archive/` as an in-place filter over the month index that page
already fetches - no new route and no new request. The trigger:

> **When the lowest-share active lens reaches 10 items in the archive's default
> window, the archive story rows gain a lens filter.**

Until then that filter would return a list shorter than the control bar above
it. Susan accepted the deferral on the condition the trigger was written down,
because a trigger nobody wrote down is a feature nobody ships.

## The read mark is held per day, and it expires

A reader can mark an item read. The mark lives in `localStorage` and nowhere else - never a cookie, because a cookie is sent on every request and would put a reading history into the host's access logs.

**The store is keyed by digest date, one storage key a date**: `idhazh:read:2026-08-23` holds `["ai-0417291083",...]`. It used to be one flat list of ids with no date, and that shape had two faults that are really one fault:

- **It greyed out the wrong article.** An id that came round again on a later day matched a mark the reader had never made, so an unopened item arrived already read.
- **It grew forever.** Nothing in a bare list says which day a mark belongs to, so nothing could ever decide which marks to drop.

A date makes a mark answerable, and answerable is what lets an old one be dropped. `ui.read_mark_days` (14) is the window, and since 2026-09-06 it means **14 calendar days back from today** rather than the newest 14 dates the store happens to hold. That swap costs something and the knob says so: expiry by calendar needs the device clock, and the rule it replaced deliberately needed none. It is worth it because the old rule bounded the store by how often a reader came back rather than by how long ago they read - a reader who opened one day a month kept marks from seven different months, and each greyed out an article last seen most of a year ago. One more thing follows from the calendar, and it is a real loss rather than a rounding error: **a mark made on an archive day the window no longer reaches does not survive the next load.** The window is the promise, and it is the same span `ui.archive_recent_days` lists as rows of its own, so the days the archive offers as shortcuts are exactly the days a mark still lives on. Only a date OLDER than the floor goes, so a device clock running slow loses a reader nothing.

**A click writes one day.** Every mark used to sit under a single key holding every date, so marking one story re-read, re-parsed and re-serialised everything the reader had ever read - a cost that grew with the reading history and never with the day in hand. One key a date makes that write the day's own marks and nothing else, and it makes the pruning a walk over key names rather than a parse of every mark. Proved as bytes rather than argued: `readstate.spec.ts` marks the same story twice, once against an empty store and once with twelve other days of forty marks each, and holds the two writes to the same key and the same length.

**The dated map is carried over; the undated list is not.** A store written under the old single key is folded into one key a date on the next load and then forgotten, because it holds marks a reader really made. The bare list that came before it is still dropped rather than guessed at: there is no honest way to decide which day an undated mark belonged to, and a wrong mark costs a reader an article where a lost one costs them a click.

`forgetAll` clears one day, because the button sits on a day page and has to do what it says. Everything here is a convenience: a quota error or private mode degrades to no marks and never to a broken page.

The rule this must never break is in [layout.md](layout.md): read state may change how an item **looks**, and may never change where it sits, whether it appears, or how it ranks.

### What a read item looks like, and what it sounds like

Three cues, and only one of them is brightness:

- **The ring on the leading edge loses its fill.** An area difference, so it survives a cheap panel, sunlight and arm's length.
- **The title steps one down the ramp and loses a weight**, to `--color-text-secondary` and no further. A dimmed item reads as "you cannot have this" rather than "you already had this".
- **A visually-hidden `Read.` opens the heading**, so the accessible name of a read item is `Read. <title>`. A fill and a font weight are announced to nobody.

**Two older cues are gone.** The eyebrow dot encoded the state as filled-or-hollow with no legend anywhere on the page - a dot with no sentence - and the plain bullet it left behind before the desk name went with the desk name's own move to a tinted chip on 2026-09-01. The visible `Read` chip is removed by the owner, 2026-08-31; the word it printed is the one now in the heading, where a screen reader gets it and the page does not carry a second label.

The reason the fill was needed at all: dim text plus a lighter weight is one signal twice. Both are less ink, so both fail in the same conditions, and on that page the reader had no third cue. Authority: Susan, 2026-08-31.

## Search: overruled, and built the narrow way

Jony refused a top-level search bar and Reader called it "clutter, and a lie about what is behind it" - a box implying an archive the reader cannot reach, which manufactures a failure out of a quiet morning.

The owner asked for it. What ships is the narrow defensible version, which is a filter, not a search:

- It lives **inside the filter bar**, beside the topic pills, not as a top-level bar above the first headline.
- It filters **in place** over what is already on the page. It never navigates and never touches the URL.
- It states its own scope - "6 of 17" - so it cannot imply an archive.
- **It waits for `digest.filter_min_chars` characters before it narrows anything.** One letter narrows nothing: measured 2026-09-01 over the 12 committed days and 4,203 story titles, the median single letter is in 80.2 percent of them and `e` is in 99.8 percent, against a median 0.8 percent for a two-letter pair. A list that redraws on the first keystroke and removes almost nothing is work the reader watches for no answer.
- No results says so plainly, naming the day rather than the corpus.
- The query is untrusted reader input matched against untrusted payload text: compared with a lowercased substring test, and never interpolated into a selector, a class, a URL or markup.

**It reads the list the page is holding, never one it captured.** A reading route prerenders the head of its day and fetches the rest, so a filter that took a copy of the items at mount would narrow a fifteen-story seed for ever, with nothing on screen saying so. The day's searchable text is lowercased once into a `DayIndex` (`indexDay` in `frontend/src/lib/day-shape.ts`) rather than once per keystroke, and that index is derived from the list the page is holding for exactly the same reason - an index built at mount is a captured list wearing a different name. `frontend/tests/filter-bar.spec.ts` drives the rule with a seed and then with the whole day, and asserts the index follows.

**A story's fields are lowercased separately and never joined.** One string per story would be smaller and faster, and it would also make the end of a title and the start of its summary into a substring - so a needle would match text no story holds. `frontend/tests/day-list.spec.ts` asserts it cannot.

Real cross-day search belongs on the archive, later, where the question "where was that thing about the reactor?" is genuinely unanswerable by scrolling.

## The filter bar: topics and a field in one panel

One panel carries the topic pills and the field, on the day page and on the archive. It replaced `TopicPills.svelte` on 2026-09-01, and the reason is vertical space: a field and a pill row each claiming their own band is why the top of a reading page was tall, and on the archive the search box was the last thing on the page - under every story it might have replaced.

Six decisions, all Susan's:

- **The pills are visible at rest.** Never behind the field, never collapsed as a set. The only thing a disclosure holds is the topics past `digest.topic_pills_max`, and its summary says how many.
- **Typing never fetches.** On the day page it narrows the day already on the page - no navigation, no URL change, no request. On the archive it narrows the stories already fetched, by title, and only the `Search` button starts the on-device encoder download, so the 43 MB is named before it is paid for. `frontend/tests/filter-bar.spec.ts` counts the requests under the model directory and prints both counts: zero while typing, and exactly one encoder file after the click, which is what proves the counter was watching.
- **Pressing `Search` turns the box from a filter into a question, and a question is not a substring.** So the list under it stops being narrowed by the words in it until the next keystroke. Without that rule a search which found nothing would leave an empty page instead of the browse list it is supposed to fall back to: a sentence like "medieval basket weaving techniques" is in no title, so the substring filter would empty the one list the page has. `Show all stories` empties the box as well as dropping the answer, for the same reason - it means all of them.
- **Sticky at 1024px and up, and nowhere below it.** That is `frame.breakpoints_px[1]`, where the pills and the field share one band. Below it the panel can run to several wrapped lines, and a control holding a third of a phone screen for the whole scroll is screen the reader paid for.
- **With no script the field is not rendered as a dead box.** A `<noscript>` rule hides it and one sentence takes its place, because an input that swallows typing is worse than no input. The day page's pills are prerendered links and keep working; the archive's pills are buttons over a list a script fetched, so they go with the field.
- **The archive's pills carry whole-archive totals**, one integer a vertical, computed in `+page.server.ts` which already loads every day. That number is also the honest denominator of a topic-filtered list while months are still unread. The pill count and the list count are different numbers and never share a sentence.
- **The archive's model-state and scope sentences moved up**, under the panel. They used to sit below the story list, which put the control behind the answer.

Two shapes were refused. **A search field that expands to reveal filters** hides the filter set behind a control, which is the failure this replaced. **Keeping two separate blocks** was the owner's rejection: the two bands of vertical space are the cost the row exists to remove.

**The thin-desk sentence is drawn by this component and rendered outside the panel.** A topic page whose desk published at most `digest.desk_thin_max` stories carries one line saying what our sources offered it and how much of that was too old. It is a sibling of the panel rather than a third child, because at 1024px and up the panel is one nowrap band and a third child would be squeezed in beside the pills - and because it is a fact about the desk rather than a control, so it should scroll away with the stories it is about. It draws for the active desk only; on the all-topics view there is no desk being read, and on the archive the counts are sums over every published day, so the panel is handed no threshold there at all. What the sentence says and the three clauses behind it are in [../../concepts/digest.md](../../concepts/digest.md#a-thin-desk-says-what-did-not-run).

**The panel is a surface, not a rule.** It takes `--color-surface`, a hairline and `--radius-lg`, the same low-chrome card language the item took in row #8 - the sticky band needs a ground of its own to sit in front of, and a bordered panel is what says the pills and the field are one control rather than two things that happen to be adjacent.

**What it costs in vertical space, measured rather than asserted.** Chromium on the built site, the real 2026-09-01 digest of 117 stories over five desks, an 800px-tall CSS viewport, a developer machine / / node 24.12.0, 2026-09-01. Geometry is deterministic for a given pill count, so the spread is zero across repeats and the numbers move with the number of desks that published, not with the day's story count.

| CSS viewport width | Panel height | Share of the screen | Position |
| --- | --- | --- | --- |
| 360 | 281 px | 35.1 percent | static |
| 801 | 177 px | 22.1 percent | static |
| 1024 | 121 px | 15.1 percent | sticky |
| 1280 | 69 px | 8.6 percent | sticky, one row |
| 1536 | 69 px | 8.6 percent | sticky, one row |

That table is the argument for decision 3 rather than an illustration of it. At 360 the panel is a third of the screen, which is exactly why it scrolls away there; the pills and the field only share a single 69px row from 1280 up, and between 1024 and 1280 the pills take two lines inside the same band. A day with more desks pushes the two middle rows up and does not touch the last two.

## The archive lists stories, and fetches them a month at a time

`/archive/` used to list five dates and no articles, and it inlined every committed day whole so on-device search could read the vectors without a request. Measured 2026-08-27 on one checkout, six committed days and 2,237 items: **1,766,682 gzipped bytes**, growing **489,843 bytes** for the one extra day that carried 621 stories. The page a reader opened to find one story carried all of them. It is **2,912 bytes** now, and one more day of 621 stories costs it **24 bytes** ([../../reference/measurements.md](../../reference/measurements-site.md#the-archive-stops-carrying-the-corpus)).

What it renders now, top to bottom:

- The counts and the retention promise: "6 days, 2237 stories. Nothing here is deleted."
- **The filter bar** - every topic the archive holds with its whole-archive count, and the search field beside them. Under it, the two sentences about the on-device model: what it would cost, and how far back a search would reach.
- **The day list** - the newest `ui.archive_recent_days` days as rows carrying the long date, the story count and a mark when some stories did not finish, then one disclosure a month and one a year for every year before the newest published one. A month row reads `20 of 31 days, 4086 stories` and holds its own days as a wrapped grid of numbers. It was a single wrapped row of every date until 2026-09-01, which is 700 links after two years.
- **The stories**, newest day first, each a link to its own anchor on the day that published it, with the date and the topic beneath.
- **`Show 25 more`** - the same explicit control the day list and the console's failure list already use, sized by `ui.archive_page_size`.

**The stories are fetched, not inlined**, from `index/<YYYY-MM>.json` staged into `static/`. [layout.md](layout.md) owns why, and the short version is that inlining them would leave the page growing per story, which is the defect the index exists to end. Paging back into an older month fetches that month; a month already in hand is not fetched twice.

**A window bounds which months the browse list fetches.** A segmented control - the same pattern as the console's, over the same 1, 7, 14, 30, 90-day presets - sits above the stories under `data-archive-window` and opens on a 30-day window. `monthsInWindow` in [../../../frontend/src/lib/assist/month.ts](../../../frontend/src/lib/assist/month.ts) turns the window into a newest-first prefix of the months, and the loop reads only those, so a story older than the window is out of the browse list until the window widens or a search reaches past it (Rule #12). A narrower window only hides months already in hand; a wider one fetches the months it now reaches. A topic with no story inside the window says so and offers a `Look back` button to the widest preset, rather than walking back through the whole archive to fill a page - that sparse-topic walk was audit finding 89, and the window is what ends it. The window governs the browse list only: search reads its own day floor, not this window.

**Nothing the list needs sits under `assist/`.** That path is the on-device encoder, which the bundle must render complete without ([../../../CLAUDE.md](../../../CLAUDE.md) section 0a). Browsing is not a model feature, so the index is served from its own `index/` path and the list works with the whole model directory deleted. `frontend/tests/archive.spec.ts` holds it by failing every request under `/assist/` and asking for the stories anyway.

Four rulings behind the shape, the first three Jony's and the last one Susan's:

- **No sort control.** Per-reader ordering is forbidden by [layout.md](layout.md) - two people at one URL see one order.
- **No infinite scroll.** It takes the footer away from the reader and has no resting state.
- **The header states the retention window**, which the page did not do and which [layout.md](layout.md) requires before anything is deleted.
- **The per-day story count and the partial flag came back on 2026-09-01, on the newest `ui.archive_recent_days` rows only.** They left the day row in the first place because a count beside every one of 700 dates is what turns a compact row into a wall. That argument holds against 700 rows and not against fourteen: `ui.archive_recent_days` rows are a list somebody reads, and "how big was Tuesday, and did it finish" is what decides whether to open it. Every older day is a number inside its month and carries neither. Run health in the aggregate still belongs to the console.

The degraded states, and each one is designed rather than discovered:

| State | What ships |
| --- | --- |
| No index, or a month that will not load | The day list, and one line: "The story list could not be loaded. Open a day above to read it." |
| A filter or a topic that matches nothing read so far | The day list, and one line: "No story on this page matches that. Press Search to look through the whole archive." The field narrows what the browser has fetched, so the sentence names that scope and points at the control that reaches past it |
| JavaScript off | The day list, and two `<noscript>` lines - one saying the story list needs it, one saying the search and the topic filters do. The day rows and the month disclosures are prerendered and native, so navigation and opening a month both still work |
| Nothing published at all | "Nothing has been published yet.", as before |

### The day list grows with months on the page and with days in the document

The list a reader meets stopped growing one link a published day. At **700 days
it is 18 rows** - seven days, nine months of the newest published year, and one
row each for 2025 and 2024 - against **700 links** before. Opening every year
still tops out at a row a month.

**The prerendered document is a different number and it did not go flat.** The
folded day links are what a reader with no script uses to reach a day older than
a week, so there is still a link per published day in the HTML, and the document
still grows with days:

| Measured | Before | After |
| --- | ---: | ---: |
| `/archive/`, 700 days, gzip -9 | 12,045 B | 10,484 B |
| `/archive/`, 182 days, gzip -9 | 6,319 B | 6,348 B |
| Growth per published day | 11.05 B | 8.0 B |

Both fixture archives cover the same 24 months, so the difference between the
two rows of each column is days and nothing else. Measured 2026-09-01 on Intel
Core a developer machine / / node 24.12.0; method and the full numbers in
[../../reference/measurements.md](../../reference/measurements-site.md#the-archive-day-list-stops-growing-a-row-a-day).

#### Design rationale

**The oracle for this row asked for a document that grows with months and not
with days, and the measurement says 8.0 bytes a day.** The design was kept and
the claim was corrected, because the only way to reach zero is to stop emitting
a link for each day - and then a reader with no script reaches seven days and no
more. That reader is the whole reason the day list survived at all: the page's
own `<noscript>` line says the story list needs a script, and these links are
what is left when it is off. Two clicks to any date is also what let the row
refuse a jump-to-date field.

**What the 27.7 percent came from is worth naming, because it is not the
markup.** The day-list markup is about the same size either way - 106.5 raw
bytes a day before, 90.6 after. The saving is in the serialised `load` return
the document carries: a flat list of `{date, items, partial}` objects became a
list of day-of-month numbers under a month key, which the serialiser dedupes to
31 values however many months there are.

## Search reads the same month index, and says how far back it read

Search used to rank over the whole day payloads the page carried, which is why
the page carried them. It now reads `index/<YYYY-MM>.json` and its
sibling `<YYYY-MM>.bin`, and the eager payloads are gone. That is the last 1.7
MB of the archive's weight, and it is the reason this row exists.

**The scope is a floor of days, filled by whole month shards.**
`assist.search_months` (1) is how many shards a search always reads, newest
first. `assist.search_min_days` (7) is the fewest days it tries to reach: when
the shards `search_months` names cover fewer days than that, a search reads one
more shard - one more and no more, so the cost is bounded at a single extra
fetch.

The reader waits on the download and never on the arithmetic: measured
2026-08-26, one month is a 2.53 MB vector file beside a 518 KB browse index -
about 2.1 seconds on a 10 Mbit line at the rate the committed days ran, or 4.8
seconds at the structural ceiling - against 74 to 159 milliseconds of ranking.
The fetch is 9 to 30 times the ranking at every scope, so a wider scope buys
nothing but waiting: three months is a 14.4 second download, and one month is
the only scope whose first search starts inside about five seconds.

**The extra shard levels the bytes across the month instead of doubling them.**
It fires only when the newest shard is thin, and a thin shard is a small
download. At the observed rate of 353.5 items a day it fires on the first 6 days
of a month - 20 percent of them - and on 1 September the two shards together
move about what the single shard on 30 September already moves. The rejected
version of this rule reached a full month back from the newest published day on
every date, which fetches two whole shards on 29 days out of 30 and charges a
second browse index to every visitor who only browses.

**The page says how far back it searched**, in one line under the box:
`Searching 1 to 20 August 2026 - 8 stories.`, and `Older stories are not
searched.` when the archive holds more than the scope read. It names days rather
than months because the month name is what hid the defect: on 1 September
`September 2026` reads like a month and holds one day. A reader who gets nothing
back has to be able to tell "never published" from "outside what this read", and
the knobs are invisible to them otherwise. The line is there **before** the first
search, and costs nothing to put there: the story list above has already fetched
that month, and the count of searchable stories is in the file it fetched.

**A result renders from the day it names.** The index carries no title-plus-
summary pair on purpose - [layout.md](layout.md) prices that at 6.35 times the
entry, charged to every browsing visitor - so a result fetches the day payload
behind it and renders through `DigestItem`, the same component the digest page
uses. That is what keeps the result list from being a second place where fetched
web text reaches a page unsanitised (Rule #11). Ten results spanning ten days
cost at most ten fetches; ten from one day cost one; a day already in hand is
never fetched twice, and neither is a month. Until a day arrives, and if it
never does, the result is the title, the date and the topic the index carried -
so a failed fetch costs a summary and never a result.

The day a result was found on sits **in the item's eyebrow**, in the time slot, as the link back to it and in place of the day the publisher put on the article. The two are the same day or one apart, and printing both would put two dates on a line capped at four things.

**Two files a month fail independently, and both are designed states.** No index
leaves the story list saying so, and search says `these stories cannot be
searched on this device` without a click, because the identity check reads the
index the list already has. No `.bin` leaves the list working and search saying
the same thing on the first search, because the vectors - 2.53 MB a month at the
observed rate - are fetched then and not before. Either way the check runs
**before** the 43 MB encoder download: a reader who cannot be helped by those
bytes is not asked to spend them.

## The search box is a field, and one click is the whole gesture

The box used to be a link that turned a search box on, and then a search box.
Nobody wants to enable anything; they want an answer. So the field is there
before a byte moves, a reader types the question first, and one click fetches
the vectors, downloads the encoder and runs what is already in the box.

**The model's state is a sentence, never a dot.** Five of them, and the copy is
in [../../concepts/design-system.md](../../concepts/design-system.md): not
downloaded, downloading, ready, the encoder changed since last time, and this
browser cannot run it. Whether the download has already been paid for is read
out of the browser's own cache storage - this device's disk, so nothing is
reported anywhere - and when that cannot be read the whole 43 MB is printed,
because overstating a cost is honest and understating one is not.

**Progress is bytes, and it stops when the measurement stops.** The count is the
library's own, so it covers the encoder's own files and not the ONNX runtime
behind them, which reports nothing to anybody. When the weights land the line
gives up on numbers and prints `Getting ready to search.` A percentage bar over
the part nobody can see would be an invention.

**A stop is offered throughout, and it leaves the page as it was.** Nothing greys
out, the story list above stays live, and the offer comes back unchanged. The
bytes already asked for keep arriving - a browser fetch cannot be called back -
and the loader holds that one request, so a second search joins it rather than
starting another. What stops is the waiting. **A failed download offers a
retry**, because one flaky connection may not turn the feature off for the rest
of a page's life.

**A failure ends the attempt, the same way a stop does.** The library asks for
the tokenizer and the weights at the same time, and it keeps reporting on the one
still arriving after the other has already failed. Until 2026-08-27 that late
report was accepted. It put the block back to `Getting ready to search.` with a
`Stop` beside it, seconds after the reader had been told the download did not
finish, and it took the retry away for the rest of the page's life. That is the
permanent dead end this control exists to remove, arriving by another door. The
counter that already drops a report landing after a stop now counts a failure as
an end too. Measured by holding the tokenizer back four seconds against a failing
weights file: the failure showed at 1.7 s, was overwritten at 4.9 s, and the
retry never came back. It is a race, so it did not fail every time - it turned
the browser gate red in three of the four CI runs seen that day, one of them
`main`'s own commit.

**There is one list, and a search replaces what is in it.** The heading changes
from `Stories` to `Search results`, the count line changes with it, and
`Show all stories` gives the browse list back. Two lists side by side would
leave a reader working out which one answered them - and it is what makes the
browse list the search's empty state: a query that matches nothing leaves the
page exactly where it was, under one line naming the days it read.

**The count is over the stories searched, and the cap is stated when it bites.**
`10 results from the 2235 stories searched. Only the closest 10 are shown.` A
total over the whole archive would be a count across months this did not read,
and `10 of 10` printed as a total is a ceiling wearing a number.

**A weak result stays dropped, and no score reaches the page.**
`assist.similarity_floor` is a selector, not a grade. A weak hit shown is the
archive claiming an answer it does not hold, and a percentage beside it is a
number a reader can do nothing with. The zero case is the whole disclosure.

Rejected here, all Jony's, all with a reason that outlives the row:
search-as-you-type (every keystroke is a forward pass, and submit is the honest
gesture); a search box in the site header (the day page already has an in-place
filter, and two boxes meaning different things is the worst outcome); a separate
search route or a query in the URL (a shared link would land a stranger on a
page with no encoder and no results, and it cannot be prerendered); a percentage
bar or a spinner (no measured source of truth, and both are refused by
[../../concepts/design-system.md](../../concepts/design-system.md)); highlighting
the query inside a result (semantic search has no matched substring, so a
highlight fakes a lexical match that never happened); a weak-matches section, a
percentage or a did-you-mean; the model name, its width or the score; and two
lists side by side.

The whole block is still secondary by construction. Delete
`frontend/static/assist/` and the archive renders complete, the list pages, and
the first search reports the download did not finish and offers to try again.
No digest assertion moves.

## The archive names its encoder, and refuses vectors from any other

On-device search on `/archive/` embeds a query in the tab and dot-products it against vectors the runner committed. That only means anything if both sides used the same encoder, so the payload has always carried `embeddings.model_id`. Until 2026-08-26 nothing read it: the browser checked the width and the dtype and nothing else, so a day written by a different 384-wide int8 encoder passed and was ranked. The scores looked like scores.

Three rules hold it together now.

- **One identifier, and it is the runner's.** `embeddings.model_id` is a `Slug` in the payload contract - `^[a-z0-9]+(?:-[a-z0-9]+)*$` - so `all-minilm-l6-v2-quantized` is the only one of the two strings that can be written into a day at all. The browser used to hold the upstream repository's mixed-case `all-MiniLM-L6-v2` instead. That name could never have reached a payload, so reconciling to it would have meant widening a persisted contract to accommodate a spelling.
- **The identifier and the path are different constants.** One constant used to be both, which is why the path could not be versioned without changing what the guard compares. `frontend/src/lib/assist/encoder.ts` now holds the identifier, the version and the width; `backend/tests/test_embed.py` reads that file and fails when it disagrees with `backend/idhazh/embed.py`. There is no config knob, on the grounds `embed.py` already gives for its own copy: a knob here is a way to turn the guard off by accident.
- **The path carries the version, so different weights are a different URL.** `assist/models/<identifier>/<the date the weights were fetched>/`. A browser caches 43 MB on first search; without the date, a returning reader would answer new vectors with an old encoder and the only symptom would be worse ranking.

The cost is paid on the day the date moves: every returning searcher downloads the encoder again, in full. That is why it moves when the weights move and at no other time.

A reader whose days were written by another encoder gets one line where the offer was, and gets it **before** the download rather than after - there is nothing they can do about it, so there is nothing to prompt them about, and no reason to spend 43 MB of their connection first.

**From 2026-09-10 that guard compares two things that can really differ**, and until then it could not. The browser's encoder was the one this site published, so `model_id` could only ever match; it was a check written against a failure that had no way to happen. The second origin below is what gives it a job.

## The encoder has a second origin, and a manifest is what makes that safe

Our own origin is primary and the committed weights stay. A reader whose fetch of them fails - a dead cache, a partial deploy, a network that answers this site but not that file - used to get an archive with no search in it and one sentence saying the download did not finish. Since 2026-09-10 the browser tries again at Hugging Face.

**The ordering is the library's own resolution, not code of ours.** `transformers.env.allowRemoteModels` stays `false` and `allowLocalModels` stays `true`, so the first `pipeline` call can only read our copy. Nobody pays the second origin's extra 6.75 MB unless this site has already failed them, and there is no ordering code to get wrong. Only when that call throws does [frontend/src/lib/assist/weights.ts](../../../frontend/src/lib/assist/weights.ts) run.

**The URL is the convenience; the manifest is the point.** `assist.model_digests` in `config/idhazh.json` holds the SHA-256 of all five encoder files. The browser hashes every arriving file and compares before a single byte reaches transformers.js. On any miss - a non-200, a truncation, a timeout or a wrong digest - the **whole set is discarded**, and the reader is told the download did not finish. Provenance is never mixed across files: five verified files or none, never four of ours and one of theirs. Without that, naming a second origin would be a permission for another party to put bytes into a reader's tab.

Four things make it check rather than look like it checks.

- **The manifest is baked into the bundle, not fetched.** `vite.config.ts` reads it from `config/` at build time into `__ENCODER_SOURCE__`. A manifest a page fetched could be answered by whoever answered the fetch, which is the thing it exists to guard against. It rides in the `/archive/` route's JavaScript rather than the prerendered document, so roughly 600 bytes of hex stay out of a page measured against a 6,400-byte ceiling.
- **The fetch is pinned to a 40-hex commit.** `assist.model_revision` is refused by the contract unless it is one, because a branch hands back whatever was uploaded last and would make every digest a coin flip. `ENCODER_VERSION` in `encoder.ts` is the browser's copy of it and `backend/tests/test_embed.py` fails when the two differ.
- **The manifest is checked against the committed weights on every build**, not on a reader's device. A manifest that drifted from the bytes would discard every set a browser fetched and leave no trace except readers with no search. The same test hashes the five files.
- **An incomplete block turns the leg off rather than half on.** `encoderSource` in [frontend/asset-base.js](../../../frontend/asset-base.js) answers the empty block unless a URL, a revision, a non-empty manifest and a deadline are all present, so a config edit cannot widen `connect-src` without also committing what the bytes must hash to.

**`connect-src` ships as `'self' https://huggingface.co https://us.aws.cdn.hf.co`.** Three sources, every one derived from `config/idhazh.json` by the same module the fetch reads, so the CSP half and the fetch half cannot disagree. The CDN is listed because a browser checks a redirect target: measured 2026-09-09 from the live Pages origin, 15 reads of 15, the four small files answer on the base host and the 23 MB of weights answers 302 to that CDN. Listing the base host alone would pass the small files and block the model, which is the worst of both.

**A GitHub Release asset cannot serve this**, which is why the second origin is the hub rather than a copy we publish. Measured the same day: no `Access-Control-Allow-Origin` on any hop, 15 refusals in 15 attempts.

**The release that was built for that leg still exists, and it is an open owner decision.** Tag `encoder-2026-08-22`, at commit `5f1eaf60`, carries the five weight files as flat release assets. It was made on 2026-09-09 for the failover the measurement above killed, and nothing references it now: not `config/`, not `asset-base.js`, not a test. **What it costs is not disk.** A tag pins that commit's whole tree - `corpus/` and its article text included - reachable for ever, and `.github/workflows/prune.yml` pushes no tags. So for that one commit it quietly undoes the thing CLAUDE.md section 8 grants the prune its force-push exception to achieve. The decision is stated both ways and taken by nobody yet: **deleting it** loses the only published copy of assets a browser trace verified, and any later argument about that leg starts from scratch; **keeping it** keeps one commit's corpus bytes permanently reachable in a public repository, which is the cost the prune exists to bound. No agent may take this one.

**What it costs a reader, said before they press the button.** The search panel's sentence names this site as the source, and adds one conditional clause: if this site cannot serve the files, the browser asks Hugging Face instead - about 50 MB rather than 43, because the hub does not compress the weights - and they would see the request. The unconditional half stays first and stays true either way: nothing a reader types leaves their browser. Almost nobody pays the conditional half, so it does not open the sentence; a reader deciding whether to start is still told before they start.

The service worker never touches any of it. It refuses an off-origin request before it looks at anything else, so the only copy of a fetched-elsewhere encoder is the one the loader put in the library's own store **after** hashing it. A worker that cached it would be a second copy nobody verified, keyed by a URL nobody checked.

## A vector is a function of its own text, and of nothing it travelled with

Naming the encoder is only half the promise. The other half is that the runner and the tab compute the same thing from the same words, and until 2026-08-26 they did not.

The committed encoder is **dynamically quantised** - 24 `DynamicQuantizeLinear` nodes feeding 36 `MatMulInteger`. A dynamic quantiser reads its activation scale off whatever tensor it is handed, so every sentence in a batch helps set the range the other fifteen are measured against, and so does every pad token. The runner used to embed sixteen items at a time padded to the longest of them; the browser embeds one query with no padding. Measured 2026-08-25 over 48 committed items, the two paths agreed byte for byte on **0 of 48**, and the cosine between them bottomed out at 0.9926. Two batches of sixteen that shared one sentence disagreed about that sentence by up to 1.46e-2 per component - far above anything int8 quantisation hides.

So the rule the encoder path holds to now:

- **One sequence per forward pass, no padding, truncated at `assist.max_tokens`.** That is exactly what a tab does with a lone query, which is the only way the two sides can be compared at all.
- **One intra-op thread, one inter-op thread, sequential execution, the CPU provider named.** The session used to be built with no options, so the thread count came from the host's core count and float addition is not associative.
- **`onnxruntime` is pinned exactly, not floored.** A kernel rewrite in a patch release moves the bytes without moving any API a test watches.

The cost is about 14 percent of the encode stage - 121 ms an item before, 138 ms after, over 48 real items on a loaded developer machine - which is under a minute for every item ever published.

A vector that predates this rule cannot be told apart from one that follows it, because `DigestEmbeddings` records the model, the width and the dtype and not the arithmetic. That is why the repair below re-encodes a short day whole.

## The committed days were part empty, and part written by a retired arithmetic

`build_day` used to replace a day's embeddings block instead of merging it, so a day that ran five times kept the last run's vectors alone. It merges now. Nothing revisits a closed day, though - a scheduled run only ever appends to the current one - so the days already committed stayed wrong until something went back for them. On 2026-08-26 the five closed days held 439 vectors for the 1,614 items that had earned one. `python -m idhazh backfill-vectors` is that something, and [`../../reference/github-actions.md`](../../reference/github-actions.md#vector-backfill) owns how it is run.

**The repair re-encodes a wrong day whole rather than topping it up**, and the reason came out of the measurement rather than the design. Re-encoding the 439 vectors those days already carried reproduced them at a median cosine of 0.9936 - not 1.0 - and moved the top-10 neighbour list of 413 of them. The same test against the day CI had written hours earlier returned a median cosine of exactly 1.000000 with 54 of 80 vectors byte-identical. So the gap was the code, not the machine: every closed day predates the commit that stopped `encode` padding its input and batching it, and its vectors carry an arithmetic the browser's query encoder no longer uses. Filling only the gaps would have left one block holding two arithmetics, and a reader's query cannot rank two populations it cannot compare fairly. One block, one encoder - the same rule `assemble.merge_embeddings` already applies across model ids.

After the repair, a re-encode of a repaired day reproduces it byte for byte: cosine 1.000000 over 180 sampled vectors, zero rank movement, maximum byte delta 0.

**An item that earns no vector gets none, and loses the one it had.** The count to hold a day against is the items above `assist.min_readable_letter_share`, not `len(items)`: a headline in a script the encoder's vocabulary does not carry gets a well-formed vector about its characters rather than its story, which no query a reader types will ever retrieve. Two items on the closed days are in that state, and neither had a vector to lose.

**The current UTC day is excluded and always will be.** A day payload is one JSON file with no union merge, and the scheduled pipeline appends to the live day several times an hour. Two producers writing it do not interleave - one wins whole and the other one's run is gone.

**Two days are still short of that promise, and nothing can see it.** 2026-08-21 and 2026-08-22 already carried a vector for every item they earned, so the repair skipped them - which is what makes the command safe to dispatch twice. Their 14 vectors are still the retired arithmetic. `DigestEmbeddings` records the model, the width and the dtype, and nothing records which encoder path wrote a vector, so no detector can tell a stale block from a current one when the counts agree. Fixing that means a field on a persisted contract, which is a `CLAUDE.md` section 6 Level 5 change and belongs to whoever signs it.

## The all-topics page opens on the day's leading stories, and nothing is dropped to do it

A day of 586 items rendered as one queue had no usable first screen. Items are
appended in plan order, which is per-vertical, so the payload reads
`[run 1: ai..., business..., energy...][run 2: ai...]` and the first twelve on
the page were the top twelve of whichever vertical id sorted first. That is an
accident, not an edit.

**From 2026-09-01 the page opens on `DigestDay.leads`** - at most
`ui.leading_stories` stories, chosen across the whole day by the pipeline, each
carrying one sentence saying why it leads. Below `ui.leading_min` the block does
not render and the day goes straight to the stream. What the block is for a
reader is [../../concepts/digest.md](../../concepts/digest.md#the-days-leading-stories);
how a lead is chosen is
[../sources/discovery.md](../sources/discovery.md#a-second-order-over-the-same-day-the-leading-stories).

Three rules make this hierarchy rather than truncation:

- **No item is removed, hidden or re-ranked.** A lead names a story the stream
 already holds, in the place it already holds it, and the block draws what the
 payload hands it rather than re-ranking anything in the browser.
- **Every lead's story is rendered, so every anchor resolves.** The stream draws
 the head of the published order plus every lead, in published order and never
 twice. That is not a nicety: measured 2026-09-01 on the 601-story day of
 2026-08-31, the five leads sat at positions 249, 285, 337, 344 and 493, so a
 page holding only the head is a block whose links land on nothing - and
 SvelteKit's own `handleMissingId` check fails the build rather than shipping
 it.
- **A topic route and an active filter draw no block.** Both already have a
 subject, and a lead outside what the page is showing is a link that scrolls
 to nothing.

**What this replaced, and what it cost.** Until 2026-09-01 the view rendered one
section per vertical showing each topic's first `ui.items_per_topic` stories and
a link into the topic route. It was hierarchy bought by hiding: on the
431-story day of 2026-08-30 it drew 15 stories and put 416 behind five links.
The pill row is the way to a desk now, where every topic is already its own
prerendered route, and the flat stream below the block carries the whole day.
`ui.items_per_topic` is retired and read by nothing.

The arithmetic lives in
[frontend/src/lib/day-shape.ts](../../../frontend/src/lib/day-shape.ts), the way
the run strip's axis does, so the rules can be tested without a browser.

## The day is a stream with an aside, and the aside is a zone rather than a width

From `frame.breakpoints_px[2]` (1400px) the day page is two columns: the story
stream at `minmax(0, 1fr)` and an `18rem` sticky column carrying the leading
stories. Below that width nothing changes - the block draws above the stream
exactly where `digest.sections` puts it.

**Why it happens there and not sooner.** Measured 2026-09-02 at a 1536px
viewport on the committed digest, the frame's content box is 1,216px, the item
took all 1,216 of it, and the summary took 659.81 - so 230.19px of every card
stood empty beside the prose, at every width from 1,280px up. The frame is not
the problem and was not widened: at 801px the item already takes 91.9 percent of
the frame. What is spendable is one column of at most 27.1rem, once a
68-character measure and a 1.75rem source mark are paid for
([../../reference/measurements.md](../../reference/measurements-site.md#what-the-reading-page-does-with-a-wide-screen-2026-09-02)).

**One trailing column at a time.** The item's own footer rail wants the same
slot, and keeping both leaves the summary 570px against a measure of 659.81. So
the item retires its rail at the same breakpoint and its footer returns under
the summary - which is where the item's own split puts it anyway, because the
confidence sentence is a claim about the summary and the rail painted it level
with the title.

**The aside stands beside the stream, never beside the day's controls.** The day
is rendered in four parts - the sections before the leads, the leads, the
sections between the leads and the stream, and the stream - and the two control
parts span both columns. That is not a preference: the filter panel sticks only
where it is one band, and at the 896px a two-column split leaves, its pills wrap
under its field. Each part renders its own sections in `digest.sections` order
and the parts are in that order too, so the document order a narrow screen and a
reader with no script see is exactly what config asked for, and reordering the
page is still a config edit.

The aside needs the leads to come before the items in `digest.sections`. Any
other order and the day is one column at every width, because an aside beside
the day's controls is the arrangement the rule above refuses.

### The zones are config, and a browser check proves they are relative

`frame.zone_mark_rem`, `frame.zone_rail_rem` and `frame.zone_aside_rem` are read
by [scripts/build-frame-css.mjs](../../../frontend/scripts/build-frame-css.mjs)
and written into `--zone-mark`, `--zone-rail` and `--zone-aside`, the same way
the frame width and the measure already are - a column width has to be right on
the first painted frame, so it cannot be injected from a layout.

They are `rem` because a reader who set their browser text larger needs the
furniture beside the text to grow with it. That is the one property of this
layout no screenshot can check: `14rem` and `224px` are the same number at the
default font size. [frontend/tests/item-zones.spec.ts](../../../frontend/tests/item-zones.spec.ts)
reads each zone's used width with the root font size at 16px and again at 22px
and fails unless every one of them scaled by 22/16, printing both numbers so a
pass cannot be vacuous.

## The day notice is one line, and one divider marks the later runs

The notice states the day as facts and never as a judgement: the count, the
failures when the run was partial and why they failed, how many arrived after
the first run, and last, which run made this page and at what time. It used to
print one near-identical paragraph per later run, which said one fact three
times.

**The last two of those sentences arrived from the footer on 2026-08-31**, and
the reason is where they belong rather than what they say. A stamp about today's
run printed eight screens under today is filed in the wrong place, and the same
footer printed it under `/archive/`, `/console/` and `/evals/`, which render no
day at all. The skipped-story count came with it because the notice was already
stating it - the same fact twice on one page reads as two facts - and the
footer's reason clause, that we could not read enough of the page to summarize
those stories fairly, merged into the notice's sentence so nothing was lost.

The run stamp goes **last** in the paragraph and the count goes first. A reader
came for the stories, not for us.

`introduced_by_run` is on every item and is drawn nowhere. It briefly was: from
2026-08-31 a flat list carried one hairline divider - `Added later today` -
before the first item a later run added. **The divider was deleted on
2026-09-01.** It named a run boundary, and a run is our schedule rather than the
reader's - somebody reading past it does not know what run 3 is and cannot do
anything differently for knowing. The fact a reader wanted from it is when the
story happened, and row #17 of the reading-page plan puts that on a time rail in
words they already use. Authority: Editor, plan row #16.

**The field stays on the served-day projection even though nothing renders it.**
Taking it off is a change to `DigestView` - a contract, its schema, its version
stamp and the read side of any shell already in a browser - and that is a bigger
decision than deleting a divider. It costs 1.16 gzipped bytes an item. The
comment in `frontend/src/lib/payload/project.ts` says the same thing, so the
next person to read that allow-list does not have to trace a renderer that is
not there.

## No summary of the summaries

Asked for, and Reader ruled **no**, decisively:

> Every other piece of text on that page has a link under it, so when a sentence smells wrong I can go check. A paragraph at the top summarising the day would be the only text on the page with nowhere to click.

It would also be three removes from the source - a summary of summaries of articles - and every layer of compression is a layer of invention. What sits at the top instead is a line of facts with no voice: the date, the counts, and, when a run was partial, plainly how many did not finish. If four of five items failed and the page does not say so, a reader who works it out later has spent the trust the digest was saving.

## The footer is its links, and nothing else

```
Archive Console Source code
```

Links only, because they are the only thing in a footer anyone came to use.

**It printed six blocks until 2026-08-31 and three until 2026-09-09.** Two of the
six stated today's run - which run produced the day and at what time, and how
many stories did not finish. The footer is on every page that has one, so both
were printed under `/archive/`, `/console/` and `/evals/`, which render no day at
all, and printed a second time under `/`, where
[the day notice](#the-day-notice-is-one-line-and-one-divider-marks-the-later-runs)
was already saying them. Both live beside the day now.

**Three more went on 2026-09-09, and those did not move anywhere.** They are the
build line - the commit and the deploy date - and the promise about what is
deleted. Every one is a fact a later build or a later day can change, and the
footer is on every page, so each rewrote the bytes of every document on the site
whenever anything published. **That is the finding, and only a hash could catch
it**: measured 2026-09-09 over the 19 committed days, publishing one more day
left the 21 August document at 32,014 raw bytes exactly and changed its SHA-256,
so the page said the same thing and arrived as different bytes. No size gate
could ever have seen it. The row also takes 521 raw and 187 gzipped bytes off
every page that has a footer, but that is the small half of it: the point is that
a page for 21 August now depends on 21 August and on nothing else.

**It is `frontend/src/routes/+layout.ts` rather than `+layout.server.ts`, since
2026-09-09.** A server load is not only a read - it is a promise that a file
called `<route>/__data.json` exists, and SvelteKit's client asks a static host
for one whenever any node in the branch has a server load. Only a prerendered
route has such a file. The root layout is above every route on the site, so
keeping its `load` on the server decided that for all of them, and a route that
ever stopped being prerendered would meet the framework's error screen instead of
its own page. The knobs travel as `__UI_CONFIG__` instead, which
`vite.config.ts` resolves once per build out of the same `uiConfig` the server
reader owns - a knob a surface needs is imported into the bundle at build time
and never fetched
([../../concepts/config.md](../../concepts/config.md)). Page options went with the
file, so `/`, `/archive/` and `/evals/` each declare `prerender = true`
themselves. It takes about 230 gzipped bytes off every prerendered document,
because the config no longer rides in each one as a server-load payload.

What the reader loses is written down rather than implied, under "Design
rationale" in
[../../concepts/design-system.md](../../concepts/design-system.md).
The short version: the commit was the site's own provenance and there is now no
way to tell which build a page came from, the verification sentence was the only
place that told a stranger why an item is allowed to say it is unsure, and the
retention promise is stated on `/archive/` alone. The quiet-day panel keeps its
two ways on and loses the one that named a date: "Latest day - 8 September 2026"
is now "Today's digest", the same destination under an address no later run can
change, and
[frontend/tests/day-states.spec.ts](../../../frontend/tests/day-states.spec.ts)
is what forced a second link rather than one - a screen with nothing to do on it
reads as a dead site. **No replacement surface was built.** A manifest a page
fetches to print a commit was considered and refused - the commit is not worth a
file, a schema, a request and a cleanup story (owner, 2026-09-08).

**`/404` never carried any of this, and that is worth writing down because the
plan that made the first change assumed it did.** The document is the adapter's
fallback shell: no footer, no layout payload, no rendered day, 4,351 raw bytes on
both sides of the change. The one gzipped byte it moved is in the content hashes
in its `modulepreload` list, which are the same length and different characters
once any component changes.

[frontend/tests/footer-facts.spec.ts](../../../frontend/tests/footer-facts.spec.ts)
is what keeps the facts from leaking back or leaking away. It counts the three
links exactly once in the footer of every route that has one, counts the three
deleted sentences at zero there, counts the day's run facts at zero in the
documents that render no day, pins `/404` as a footerless shell, and fails if the
root layout imports the day loader again.

## The bundle gate checks two promises, and used to check three

`npm run bundle-gate` asserts that no encoder reaches the first-load path, and
that every capped page is under the ceiling `config/idhazh.json` sets for it.

**A third check was deleted on 2026-08-30: a per-route first-load JavaScript
ratchet against a hand-maintained record in `frontend/bundle-baseline.json`,
failing when a route moved more than 64 bytes in either direction.** The file is
gone with it. Deleting a gate deserves the same argument as adding one, so here
is the whole of it.

**The gate never had a requirement behind it.** Its own docstring said so: every
route is prerendered, so first-load JavaScript is hydration cost rather than
time-to-read, nobody had measured what that cost a reader, and Rule #1 forbids
the telemetry that would settle it. Having no number to defend, it defined bad
as *different*. That is a change-detector, and Rule #10 says an unmeasured
number may not justify a design.

**What it cost is measured.** A local Windows build does not reproduce a Linux
CI build inside 64 bytes on a route of about 80,000 - 0.08 percent - so a
failure could not be read without a control build of `origin/main` on the same
tree: two extra builds, roughly six minutes, before a branch could tell its own
change from the toolchain. `origin/main`'s own source failed its own record more
than once. Worse, the record was one file every branch had to rewrite, so the
fifteen rows of the console-signal plan serialised behind it - each one rebuilt,
re-measured and re-recorded a number its own change had not moved, because a
sibling had merged first.

**And it caught nothing.** Across every firing in that plan the resolution was
to re-record the number. Not one was a regression somebody then fixed.

What survives answers the question that was actually worth asking. The page
ceilings are absolute limits somebody priced, in `config/idhazh.json`, so
nothing has to re-record them to merge and a page that got lighter needs no
permission. The encoder grep names a cause a byte count never could. And
`tests/payload-weight.spec.ts` covers the pages a ceiling cannot bound - a page
that renders a day weighs whatever the day published - by counting a marker
instead of bytes, which is the same number whatever the published history holds.

| Option | Why rejected |
| --- | --- |
| Keep the ratchet and widen the tolerance | The tolerance was never the problem. A wider one still needs a per-route record in one shared file, which is what serialised the branches. |
| Keep the ratchet and generate the record | A file the build rewrites is a log, and a gate whose own tooling updates its baseline cannot fail. |
| Replace it with a transfer-time budget | Two invented constants instead of one, and Rule #1 forbids the telemetry that would settle either. It also models a cost a reader of a prerendered page does not pay. |
| Delete the page ceilings too | `/archive/` shipped at 873.1 KB of gzipped HTML and nobody noticed until somebody measured. A ceiling is a priced limit, not a change-detector, and it costs nothing to hold. |

Authority: owner, 2026-08-30. The ratchet was Carmack's, 2026-08-25, on the
argument that a new dependency must be measured before it ships; measuring a
dependency is still right, and `docs/reference/measurements.md` is where that
measurement goes. What is gone is failing every unrelated branch until somebody
retypes it.

## The console ceiling is a tripwire, and what to do when it fires

**Every capped route carries its own ceiling, and since 2026-09-10 they share
one convention: the heaviest of five builds of the tree that ships, plus a
tenth, measured at `gzip -5`.** That replaced four different conventions the old
set had accumulated. The current numbers, the spread they were taken over and
the arms behind them are in
[../../reference/measurements.md](../../reference/measurements-site.md#the-page-ceilings-re-aimed-at-the-migrated-tree-2026-09-10);
`config/idhazh.json` is where they live and
[../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) is what to do when
one fires.

**The console takes three of them rather than one**, because one key over three
surfaces fails when any of them grows and then cannot say which one did - the
operator raises the shared number and the regression lands under it. Sizing them
separately is what makes the split worth having.

**`/console/` fell by a factor of 6.4 in the 2026-09-10 re-derivation, and the
fall is the finding rather than a tidy-up.** It was sized on 2026-09-06 against a
document that inlined the telemetry and weighed 3.88 MB. The telemetry moved to a
browser fetch on 2026-09-09, the document became 46,775 gzipped bytes, and the
ceiling stayed - so for four days it stood at 7.2 times the page it bounded and
could not have caught any regression short of a sevenfold one. **A ceiling is
only a tripwire while it is near the page**, and nothing fails when one drifts
away from it, which is what makes this the failure mode to look for rather than
the one to assume cannot happen. **They are meant to expire**: every set before
this one did, on the day a route gained the panels it had been standing empty
for.

**When one fires, the panel does not move.** The owner ruled on 2026-08-31 that
no approved feature is removed, deferred or shrunk to stay under a page-weight
number: a ceiling is a ratchet, not a budget, so a crossed ceiling means
re-measure it, raise it, and record in the same commit what the bytes bought.
**This reversed what this page said until then**, which was to turn
`console.default_window_days` down and never to raise the number. That instinct
is still right when the page is inlining something the first paint does not need
- windowing the seed on 2026-08-29 and folding the compression scatter on
2026-08-30 were both savings - but a saving is not a cut, and neither is a
reason to leave a panel unbuilt. What the ruling does not waive: Rule #2's 1 GB
Pages cap, which is a platform limit, and the 200,000-byte lazy chart chunk,
which stands because a new echarts registration is a decision about the chart
vocabulary rather than about size.

Two answers stay wrong whatever the number is. **Raising the ceiling without
re-measuring** spends headroom somebody priced, which is what got an earlier
`/archive/` ceiling deleted after it was raised twice in one day. And **thinning
a plot** - sampling points, or dropping the oldest days - is not a byte decision
at all: it changes what the chart is a measurement of, and a scatter that quietly
stopped drawing some of its rows is worse than one that got heavy.

Two rules came out of the savings and outlived the numbers that motivated them.
**One mark per article per day, never one per row**: the telemetry holds a row
per item per run, so a re-run writes a second row for an article the first run
published, and the run that read the most of it is the one kept. And **the seed's
cutoff anchors on the newest committed day, never on the build clock** - anchored
on today, a corpus that stopped last month would seed an empty console, which is
precisely when an operator needs it.

**Why a ceiling here does not cap the news, when one on a day page would.** A day
page and the home page render published items, so the only way under a ceiling on
them is to publish fewer - and [layout.md](layout.md) forbids removing an item a
run published, so the ceiling would be deciding how much news ships. No console
route renders a published item. It is the operator's surface, and every figure on
it is derived at build time from ledgers that stay committed and complete
whatever the page shows.

Authority: Jony and Fowler, 2026-08-29; the measurement and the worst-case
sizing, Carmack; the ratchet ruling, owner, 2026-08-31.

## Design rationale

Prerendering everything is the decision the rest hangs off. It was chosen over a runtime fetch of `digest.json` because it collapsed four problems into zero: the loading state stopped existing, the request budget stopped being a budget, a contract-invalid payload became a build failure instead of a reader-facing error, and the page kept working with JavaScript off. The cost is one framework dependency and a build step that enumerates committed directories. Authority: Jony ([../../../.github/agents/jony.agent.md](../../../.github/agents/jony.agent.md)).

**Two of those four came back on 2026-09-01, and they were sold rather than lost.** A reading document carries a seed and the browser fetches the rest, so a reading page has a loading state - one sentence past `ui.payload_slow_ms` - and an invalid story past the seed reaches the browser rather than the build, which is why `idhazh validate-days` exists. What was bought is the cap date: the dated route trees were 39.5 percent of the published site, and the site went 168.6 MB to 88.1 MB with the runway from 130 published days to 279 ([layout.md](layout.md)). The other two hold unchanged - the request budget is still one file, and every page still renders with JavaScript off, a reading page down to its seed. Authority: Fowler, 2026-09-01.

**A third cost was paid at the same time and no reader can see it.** A crawler that does not run scripts now reads a dated page down to its seed and no further, so whatever those pages were worth to a search engine falls to what the seed carries. `/` keeps its whole day and stays complete and crawlable, which is the one page a stranger is most likely to arrive on. This is the least reversible part of the migration: prerendering the dated pages again would be a build change, and an index that has dropped those stories does not come back on the same schedule.

Spending the colour per item rather than at the day level is the resolution of a genuine conflict between an owner instruction and a persona's ruling, and it took two passes to land. The owner asked for a colourful confidence signal; Reader argued that per-item confidence badges are the project talking to itself. The first answer put the aggregate at the top and the proportionate signal on the item. The aggregate then had four months of data behind it and never moved, so it was deleted: colour belongs where it varies, and where a reader can click through and check. Authority: owner (section 0), designed by Jony, constrained by Reader.

Grouping the all-topics page by topic is hierarchy, not truncation, and the distinction is the whole argument. [layout.md](layout.md) forbids removing or demoting a published item, and [../../concepts/digest.md](../../concepts/digest.md) says the reader's budget is protected by ordering and hierarchy - so the fix for a 586-item day had to come from typography rather than from a cap. Every item stays published, in its published order, one prerendered click away. The rejected alternative, truncating the day, would have made the page look like a digest by making it stop being one. Authority: Jony, with Reader as the check.

Removing `uplot` restores the refusal one row below rather than overturning it. Rule #8 requires a dependency to name a beneficiary feature; its recorded beneficiary was pan and zoom, and `Viewport.svelte` implements those itself with a keydown handler and four buttons. What it actually drew was a second, smaller copy of the compression scatter with less information than the SVG above it. It would come back for pan and zoom *inside* a single chart, which is a different requirement, and the gzipped route chunk would be re-measured on that day rather than reusing the 2026-08-23 figure. Authority: Jony, Rule #8.

Taking `d3-scale` and `d3-array` a day later is not that decision reversed. A
chart library owns the element, the redraw and the theme, which is how the last
one ended up drawing a chart that already existed; a scale library returns a
number. The beneficiary feature Rule #8 asks for is the whole console: four
charts that agree on what a pixel is. The cost is measured rather than argued -
the gzipped route weight was measured and written into
`docs/reference/measurements.md`, and Carmack made measuring it a condition of
accepting the dependency at all. That condition still holds; what was dropped on
2026-08-30 is the per-route gate that failed every later branch until somebody
retyped the number. Authority: Jony and Carmack, 2026-08-25, owner accepted.

The same script gates the prerendered HTML and the first-load JavaScript, which
was once rejected on the grounds that one gate over both would make two
workstreams fail each other's builds. That risk was real and it materialised:
the `/archive/` and `/console/` HTML ceilings, added to the script in #126,
fired on ordinary publishes because those pages grow with the published corpus.
The fix was not to split the script but to scope the HTML ceiling to the routes
whose weight does not grow with data - `/404` and `/evals/` - and to report a
data-driven route without failing it. Both of the deleted ceilings have since
come back on a different footing: a route may grow with data and still be capped,
as long as the growth is measured and the headroom is stated in published days.
`/archive/` returned on 2026-08-27 with a year of headroom and `/console/` on
2026-08-29 with three days. What has not come back is a ceiling on a page that
renders a day, and that is the line the original fix was really drawing. So the
two checks that remain share a script and answer for different things: the
encoder grep reads the built modules, the HTML ceilings read
`config/idhazh.json`, and neither fails the other's build. The JavaScript
ratchet that was the third was deleted on 2026-08-30, for the reasons above.
Authority: Carmack (the original rejection), resolved by the page-weight change.

Folding `/evals/` into `/console/` keeps one route answering "how is the
pipeline doing". Both old routes read `state/scores.csv` and counted per-day
bands. Two surfaces reading one ledger would disagree as soon as one count
changed. `/evals/` stays as a static entry point because `CLAUDE.md` section 3
says the published dashboard keeps the route. Authority: Jony and owner defect
3.

The search scope is a floor of days rather than a count of calendar shards,
because a calendar shard is not a window. `assist.search_months` on its own made
the reach whatever the current month happened to hold: 31 days on the evening of
31 August and one day the next morning. A reader who searched that morning got
nothing back and had no way to tell it from a story we never published, and
nothing they did caused the change. The alternative that was explored and
rejected is the obvious one - reach a full month back from the newest published
day, on every date. It gives a constant window and it costs two whole shards on
29 days out of 30, plus a second browse index charged to every visitor who only
browses: 518 KB gzipped a month at the observed rate, measured 2026-08-26,
against an archive page that is 2,912 bytes. A seven-day floor buys the same
reach on the days that were broken, fires on 6 days of 30, and fires only when
the shard already being read is small - so the bytes a search moves are levelled
across the month instead of doubled. Seven is the search's own floor and no
longer a week the rest of the site keeps: since 2026-09-06 `ui.read_mark_days`
keeps a read mark for **14 calendar days back from today** and
`console.min_window_days` lets the console draw a single day, so the reach here
rests on the fetch cost above and nothing else. Authority: Carmack on the fetch
cost, Jony on the sentence, 2026-08-27.

## Rejected alternatives

The reader's surface. The console's own table is on
[console.md](console.md) - a reader row and a console row share nothing but a
heading, so one table over both would be two tables with a line between them.

| Option | Why rejected | Authority |
| --- | --- | --- |
| Runtime fetch of the day payload | Invents a loading state, a request budget and a runtime error class, all of which prerendering deletes. Two of the three came back on 2026-09-01 and were sold for the cap date rather than lost. | Jony |
| A top-level search bar | On a page whose whole content is on screen it is a control with nothing to do, and it promises an archive it cannot reach. Narrowed to an in-place filter. | Jony, Reader |
| Drag-and-drop or slot-based layout | No left and no right on a phone, unbounded QA, and per-reader layout breaks the shared-link promise. | Jony |
| A third theme on day one | Three band colours, eight swatches and a focus colour to carry forever for a reader nobody has named. | Jony |
| Publisher favicons | A runtime third-party request that announces every reader to every publisher, failing to a broken-image glyph mid-page. | Jony |
| A coloured stripe or tinted card per band | At a realistic band distribution it paints most of the page as broken, and the reader believes it. | Jony |
| A `high` badge on every item | Ink spent on the absence of a problem, and colour as the only signal. | Jony |
| A day-level bar of the confidence bands | It charted a constant, shared its tokens with the item mark so it trained the reader to ignore the mark that varies, and printed a sentence the item level had already retracted. | Jony, Reader |
| A day-level sentence counting how many summaries may not match | The bar in prose. A number spread over hundreds of items a reader can neither locate nor act on. | Jony, Reader |
| A summary of the day's summaries | The only text on the page with nowhere to click, and three removes from the source. | Reader |
| Topic tabs including empty ones | An empty tab reads as broken software or an absent desk. Only present verticals are rendered. | Reader |
| A colour per topic | A category-to-colour map that must be re-picked every time the taxonomy changes, carrying nothing the count does not. | Jony |
| A cross-topic "top stories" strip on the day page | The payload carries no cross-vertical rank, so the page would have to invent one at read time. The page renders; it does not think. | Jony |
| Truncating a long day to protect the two-minute budget | Ordering and hierarchy protect the budget. Dropping items a run published is not a typography fix. | Jony |
| Grouping a day that ran to a single topic | One heading over the whole page states what the page already says, and it puts items behind a link that leads back to the same list. | Jony |
| A "newest first" or "best first" sort control | The published order is global and identical for every reader. A sort control makes a shared link show the recipient a different page. | Jony |
| An estimated reading time per topic | An unmeasured number printed as a fact, and it changes nothing a reader does. | Jony, Rule #10 |
| One paragraph per later run in the day notice | Three runs printed three near-identical sentences saying one fact. One total says it once. | Jony |
| `key_points` shown alongside the summary | The same content twice, at the cost of the hierarchy and half the items per screen. | Jony |
| A visual placeholder when there is no visual | Makes "we correctly decided this needed no picture" look identical to a failed image. | Jony |
| A service worker or offline shell | It can serve a reader a stale day, which attacks the rule the whole layout rests on. | Jony |
| Computing "today" in the browser or at build time | The browser would vary by reader timezone, and the build clock would let a stale deploy claim a date the payload does not carry. | owner |
| A flat list of read ids with no date | An id that came round again greyed out an article the reader had never opened, and nothing in the list could decide which marks to drop. | owner |
| Migrating undated read marks rather than discarding them | There is no honest way to say which day they belonged to, and a wrong mark costs a reader an article. | owner |
| A read mark that hides or demotes an item by default | Two people at the same URL would see different pages, and a shared link would stop showing the recipient what the sender saw. | Reader |
| Reconciling the encoder identifier to the upstream `all-MiniLM-L6-v2` | `embeddings.model_id` is a slug, so that spelling can never be written into a payload. Adopting it means widening a persisted contract to fit a capital letter, and re-stamping five committed days to buy nothing. | Fowler, Andre |
| A config knob for the encoder identifier or its version | The guard compares a payload against this string. A knob is a way to turn the guard off by accident, which is the same reason `embed.py` refuses one for its own copy. | Andre |
| Telling the reader their vectors are stale and offering to update | There is no update for them to take - the encoder is whatever this build committed. A prompt with no action behind it is a notification asking for thanks. | Jony, Reader |
| Reaching a full month back from the newest published day on every date | A constant window, bought with two whole shards on 29 days out of 30 and a second 518 KB browse index charged to every visitor who only browses. | Carmack |
| Naming the months a search read, rather than the days | On 1 September "September 2026" reads like thirty days and holds one. The month name is what hid the collapse it was meant to disclose. | Jony |
| Padding every sequence to the token cap so batch composition stops mattering | It was the first proposal and the measurement refused it. Fixed padding removes the *shape* a batch imposes, not the *scale* it sets: pad-to-cap against no padding still moved a component by 1.56e-2, and padding also moves the runner further from a browser that pads nothing. | Carmack, Rule #10 |
| Accepting host variation and gating a re-encode on cosine alone | A cosine tolerance is the right check for a backfill, but leaving the arithmetic unpinned makes every future re-encode a fresh argument about which machine was right. | Carmack |

## See also

- [console.md](console.md) - the operator's surface: which panel is on which route, and the ruling behind its shape.
- [layout.md](layout.md) - the routes, the dated addresses and retention.
- [../sources/health.md](../sources/health.md) - the feed ledger, and the quarantine rule the console mirrors.
- [../../reference/github-actions.md](../../reference/github-actions.md) - the four-run cadence.
- [../../concepts/digest.md](../../concepts/digest.md) - what an item carries and the visual rule.
- [../../concepts/design-system.md](../../concepts/design-system.md) - typography, tokens and the colour rule.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shell's obligations and the five states.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload this renders.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings and the bundle gate.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1, section 0 and section 12.
