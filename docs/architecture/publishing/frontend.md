# Published Frontend

**Last Updated**: 2026-09-23

What a build writes, what a reader's browser fetches, and where each part of the
reader's surface is written up. This page holds the shell: the documents a build
emits, the eight states a reading page can be in, the config that rides in every
document, the theme that paints the first frame, and the manifest that installs
it. Everything drawn inside that shell has a page of its own, and the table
below routes.

Concept-level *why* lives in [../../concepts/digest.md](../../concepts/digest.md), [../../concepts/design-system.md](../../concepts/design-system.md) and [../../concepts/ui-shell.md](../../concepts/ui-shell.md). This page is the *shape*, and it records where the owner, Jony and Reader disagreed and how it was settled.

## Where the reader's surface is written up

Six pages, one question each. Arrive at the one holding your question and stop.

| Page | The question it answers |
| --- | --- |
| this one | What does a build write, what does a browser fetch, and what state can a page be in |
| [what-a-story-shows-and-where-each-fact-sits.md](what-a-story-shows-and-where-each-fact-sits.md) | What does one story print, which facts sit above the title, and what changes once it is read |
| [how-a-story-chart-is-drawn-and-what-refuses-one.md](how-a-story-chart-is-drawn-and-what-refuses-one.md) | How does a story's chart reach the page, which token does each mark take, and what is refused on arrival |
| [how-a-day-page-is-arranged.md](how-a-day-page-is-arranged.md) | How is a day laid out from header to footer, and where does the leading block go on a wide screen |
| [how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md) | How does a reader filter a day, browse the archive, and search across months |
| [the-on-device-encoder-and-its-vectors.md](the-on-device-encoder-and-its-vectors.md) | Which encoder wrote these vectors, where does a browser get it, and what makes two vectors comparable |

The operator's surface is a different reader with a different budget, and it is
[console.md](console.md).

## Eight documents, and a ninth that answers every dated address

Eight routes are generated at build time - `/`, `/archive/`, `/evals/`, `/console/` and its four tabs - and `adapter-static`'s fallback, `404.html`, answers everything else. SvelteKit with `adapter-static` and no `entries` reading the digest tree anywhere. **Nine files declare `prerender = true` and eight routes get a document.** The counts differ because `console/+layout.ts` declares it for every route under `/console/` and each console tab that has a server load declares it again - so how many documents a build writes is counted in the build and never in the grep: the build writes eight `index.html` files plus `404.html` ([the 2026-09-12 record](../../reference/benchmarks/prerender-on-and-off.md)). `/archive/`, `/404`, `/evals/` and the console inline everything they draw; `/` inlines a seed of the newest day and fetches the rest; a dated URL is the fallback document, and the page fetches the served day for the whole of it.

**Until 2026-09-09 every route was prerendered, and that cost six documents a published day.** 20 dated pages and 96 topic pages, each with a `__data.json` twin, all rebuilt on every run because a document holding a seed of a day changes when the day does. Measured on a real build, a developer machine, 2026-09-09, `BUILD_VERSION` pinned across both cases: 796 files and 116,050,183 bytes before, **572 files and 101,880,352 after** - 224 files and 14,169,831 bytes, 12.2 percent of the built site. On that build 123 documents became 7 and 121 `__data.json` files became 5; the documents are 9 today and the twins are 7, because each of the two console tabs added on 2026-09-12 has since grown a server load of its own - `/console/voices/` on 2026-09-14 and `/console/judgement/` on 2026-09-17. **The document count no longer moves when a day is added**, which is the whole of it - it moves when somebody adds a route, which is a line in a commit rather than a run of the pipeline.

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

**A tree with no day in it still builds, and nothing has to be excused for it to.** The eight prerendered routes read no committed day to decide whether they exist, so every one of them produces a page on every build.

**Whatever the root layout's load returns is inlined into every page beneath it**, so from 2026-09-09 it returns **the config and nothing else** - no day, no date, no field read off one. The home page loads the day it renders. The layout used to return the whole latest day, which put a day of article summaries on the console, on `/evals/`, which draws none, and on every older dated page that already carried its own. Measured 2026-08-26, `gzip -9` over each prerendered page, one tree carrying five published days built twice with only that field differing: `/console/` 406.3 -> 93.0 KB, `/evals/` 315.6 -> 2.4 KB, `/2026-08-23/` 439.6 -> 126.0 KB, and 15749.2 -> 6343.3 KB over all 31 pages. Two builds of the same tree agree to within 0.1 KB. The last two fields it kept - `retention_window_months` for the footer's promise, and `latest` for the empty state's shortcut - went on 2026-09-09, because both are read off the newest day and both therefore rewrote every older page each time one published ([the footer](how-a-day-page-is-arranged.md#the-footer-is-its-links-and-nothing-else)).

[frontend/tests/payload-weight.spec.ts](../../../frontend/tests/payload-weight.spec.ts) holds that line. It counts a marker only a day payload carries and fails on any page below the layout that has one. It had one exclusion, `/archive/`, which inlined every committed day on purpose to feed the on-device search; the exclusion is gone from 2026-08-27, and the archive now carries an assertion of its own that it holds **zero** day markers.

**The second line was the guard prerendering used to give free, and it retired with the pages it guarded.** A dated route was exempt from the sweep above while it genuinely rendered its whole day; after the 2026-09-01 split it was held to its own seed, `ui.shell_seed_items` markers on a topic route and that plus `ui.leading_stories` on a day route, so that an exemption could not quietly become a guard that cannot fail - which [layout.md](layout.md) records as a shape this repository has had twice. From 2026-09-09 there is no dated document at all, so there is nothing to hold to a seed: the sweep runs over every document a build writes - the eight `index.html` files and `404.html` - every one of which must carry zero day markers. `/` is deliberately exempt, because it is the one document that renders a day at all, and the sweep's second assertion holds it to carrying at least one marker so a build that lost the day cannot pass by carrying none. **The exemption was written when `/` carried the whole day, and the reason given was that a ceiling there would cap the news. `/` has carried a seed since 2026-09-10, so that reason has gone and the exemption has not**: the rule asks whether a page renders the day it inlines, never how much of it. [payload-weight.spec.ts](../../../frontend/tests/payload-weight.spec.ts) still says `/` keeps the whole day inline for ever in its own docstring, which is this same stale claim left in the code.

**`/` was the one place the golden principle had an open exception, and it is closed since 2026-09-10.** Owner ruling D2 of the shell-and-fetch migration says shell plus fetch "admits no special case, on the home page and the console alike" (2026-09-08). The console took it. `/` did not, on the argument that it is the one route that reads complete with no script at all. **That argument was false, and measuring it is what closed the exception rather than a ruling overturning it.** Measured 2026-09-10 on a clean production build with every `<script>` stripped, on a 72-story day: the document was 176,622 bytes raw, **63.9 percent of them script**, and what a script-free reader could actually read was **17 stories under a header saying 72, above a pager offering 55 more that did nothing**. On a mature day the header says 360 or 627 and the seed is still about 17. So the exception was charging a reader with no script for most of a day they could never reach, and leaving them a control that lies.

`/` carries a seed and fetches the rest now, like every other reading route. Measured the same day, same build, same method: the document fell from **43,606 to 22,838 bytes `gzip -5`** - 48 percent - while the markup a script-free reader can read moved from 63,763 to 63,850 bytes raw, which is the `PayloadState` region and nothing else. **The reader with no script loses nothing and stops paying for 55 stories they cannot open.**

**`/` stays prerendered, and that is a decision rather than a leftover.** The four reasons behind it, what reversing it would cost and the measurement it was confirmed on are one entry under [Design rationale](#design-rationale). It is written once, there, because two statements of one decision leave the next reader working out which governs.

**The seed keeps the day's leads.** A lead is chosen across the whole day rather than off its head - measured 2026-09-01 on the 601-story day of 2026-08-31, the five sat at positions 249, 285, 337, 344 and 493 - so a seed built as a plain prefix ships a leading block whose links land on nothing. The aside only exists once a lead resolves, so it would also mean a first paint in one column that re-lays itself into two when the fetch arrives, re-wrapping every card on screen. `dayShell` has taken a `keep` option for exactly this since the seam was built, and had no caller in `frontend/src` until now.

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
| Ready | Normal | Prerendered HTML on `/`, carrying a seed of the newest day, with the rest of it fetched. A dated URL is one shell and the day it fetched |
| Empty | Payload exists, no items | "Nothing was published for *date*", with plain copy that does not point at a notice that may not be on the page |
| Missing | The host has no payload for that date | A named screen that offers the archive and the front page. **Never a redirect to today** - a reader who cannot tell a dead link from a live one has lost the ability to trust any link. It was decided at build time until 2026-09-09 and is decided in the browser now, off a 404 or a 410 from the host |
| Waiting | A dated page has asked for its day and it has not arrived | Nothing at all until `ui.payload_slow_ms`, then one sentence. Never a spinner, a skeleton or a bar |
| Unreachable | A dated page's fetch failed for any reason that is not the host saying it has no such day | One sentence naming the day, a retry, and the days this device still holds |
| Unpublished | No day published at all - a fresh clone | The build succeeds. `/` says "No digest has been published yet" and `/archive/` says "Nothing has been published yet". There is no dated page to link to, so neither offers one |
| Invalid | Payload breaks its contract | `idhazh validate-days` fails, in CI and before the publish |
| Degraded | Low band, source-limit sentence, no visual | The common case, rendered inline. Not an error |

**Empty is a real state and two different days land in it.** A day that planned
nothing found no new article, so `partial` is false and the console paints it
amber. A day where every story failed publishes empty and says `partial`,
because a run that publishes nothing on a bad day is a run whose bad days are
invisible - 2026-09-14 is that day, 80 planned and 80 failed, and refusing it
would delete the only record that the day went wrong. So Empty is not a fault
and `validate-days` does not refuse it.

**The third empty day is refused, and it is the one that cannot be told apart
from the first.** `idhazh.stages.validate_days._census_faults` stops a day that
planned stories, failed none and published none. `ItemOutcome` has two members,
so every story the pipeline touched is `ok` or `failed`; a day holding neither
has lost its whole plan with nothing recording where it went, and the reader is
shown "Nothing was published" for a day where a great deal was attempted. The
producer refuses it at the moment it is written, which is the only moment a day
is still wrong - a published day is frozen, and re-reading all of them costs
more every day the pipeline runs (Guardrail #12).

**Missing and Unreachable are two sentences and they never merge.** Telling a reader a day was never published when their train went into a tunnel is a lie they can check. What separates them is now the host's own answer: a 404 or a 410 for `digest/<Y>/<M>/<D>/digest.json` is the host saying it has no such day, and every other failure is the connection. [NotHere.svelte](../../../frontend/src/lib/components/NotHere.svelte) is the one copy of the Missing screen - the framework's error page renders it for a status it was handed, and a dated page renders it when the host says it has no such day, because a reader cannot tell those two apart and must not be told different things by them.

**The table has a machine-readable half, and it is `data-payload-state`.** The live region that [PayloadState.svelte](../../../frontend/src/lib/components/PayloadState.svelte) renders on every state carries the current `DayStatus` - `loading`, `slow`, `ready`, `unreachable` - as that attribute, and Missing is absent from it because that screen is `NotHere` and this region is not on the page at all. The route sets the status and the day in one callback, so **`ready` lands in the same flush as the stories**: it is the only honest "the whole day is in this document". This is what a check measures a dated page by, and there is nothing else it can use - one shell answers every dated address, so the HTML a load or a reload returns carries no stories, offline included, where the worker answers the fetch instead of the host. A count taken at the load event is a count of the shell, and whether it happens to find the day is a property of the machine: measured 2026-09-09 on a developer machine, three runs of the offline case, the day was already on the page every time - the same read on `ubuntu-latest` found nothing and took `main` red. The wait is one helper, [../../../frontend/tests/support/day-ready.ts](../../../frontend/tests/support/day-ready.ts), rather than the nine longhand copies that let one spec be written without it.

The home page uses the newest committed payload as the day it can prove. It never
uses the build clock as "today". If the site is rebuilt after a quiet or failed
run, the page still names the payload date it actually renders, and the empty
state offers the archive plus the latest published day when one exists.

## Components are swapped by props, and ordered by config

Every component takes a validated slice of the day payload as props and returns markup. No component fetches, no component reads global state, no component knows a route. Swapping one means writing a file with the same props and changing one line.

Page order is `config.ui.sections`, a registry id list. **Reordering the page is a config edit, not a code change.** That is the honest version of "modular".

What is deliberately *not* built is a slot system for moving components left and right. On the surface that matters - a phone - there is no left and no right; there is one column. A layout engine for one column is unbounded QA against a reader who does not exist, and a per-reader layout would break the promise that a shared link shows the recipient what the sender saw. Two named flips are granted where left and right are real: `digest.visual_side` and `digest.source_mark`, both in `config/appearance.json`, which owns everything the published surface is drawn from ([../../concepts/config/appearance.md](../../concepts/config/appearance.md)). `visual_side` sat in `config/idhazh.json` as well, with a different value, until 2026-09-05; the pipeline file dropped its copy rather than the two files continuing to name one knob twice.

## Theming

Class strategy, not media query. **Dark is the base and light is the override.** `:root` in `frontend/src/styles/tokens.css` carries the dark values, so a document with no `data-theme` attribute - no script yet, or no script at all - paints dark on its first frame. `[data-theme="light"]` comes after it in the file and wins on source order, because both selectors match at the same specificity.

Two themes, and one control with two states: a moon button that flips between them. The glyph never changes - the page is the state indicator, and an icon that changed with the theme would be a second and weaker copy of it - so the `aria-label` names the action (`Switch to the light theme`) and there is no `aria-pressed`. A choice is always stored as `light` or `dark`; the default is never encoded as the absence of a key, or the day the default moves every reader who chose it moves with it without being asked.

A seven-line inline script applies a stored `light` before first paint. It is the one inline script this site carries, and it now exists only for that reader: everyone else is already dark from the stylesheet, so the script has nothing to correct. Its failure branch sets `dark`.

**A theme is exactly one `[data-theme="x"]` block supplying the token names in `frontend/src/styles/tokens.css` and nothing else.** The mechanism ships; two themes ship. A third means re-picking three band colours, eight source swatches and a focus colour and carrying them forever for a reader nobody has met.

`system` was a third toggle state until 2026-08-31. It was removed with `ThemeChoice.SYSTEM`, `watchSystem` and the sun glyph, on the owner's decision that the site starts dark. What a reader loses is a theme that follows their device at sunset; what they get is a control with one obvious action instead of three. `config/appearance.json` still names the default in `digest.theme_default`, and a config that still says `system` reads as `dark` (`CLAUDE.md` section 11).

The browser's own chrome follows the page. `app.html` ships one unconditional `theme-color` tag holding the base theme's background, because an installed window reads it at launch before any script has run and the page is dark whatever the system prefers - a media-scoped pair would be wrong for every reader whose system says light and who has chosen nothing. `apply` in `$lib/theme` rewrites that same tag from the resolved `--color-bg`, so a reader who picked light does not sit under dark chrome.

The oracle is [../../../frontend/tests/theme.spec.ts](../../../frontend/tests/theme.spec.ts). It loads every route three ways - no stored choice, `light` stored, `dark` stored - and asserts that every change to `data-theme` happened while `document.body` was still null, which is what makes it a statement about the first painted frame rather than about the settled one. A fourth case runs with JavaScript switched off, where there is exactly one frame and it has to be dark.

## Installability

`frontend/static/manifest.webmanifest`, four PNG icons and the `theme-color` tag above. That is the whole feature, and the doctrine around it - including the ban on `Notification` and `PushManager`, and why there is no service worker - is in [../../concepts/ui-shell.md](../../concepts/ui-shell.md).

The icons are generated once from two committed SVG sources, `app-icon.svg` and `app-icon-maskable.svg`, using `sharp` installed with `--no-save` and removed afterwards: the PNGs are the committed artefact, not the toolchain. The maskable variant is a second drawing rather than a crop, with the mark inside the central 80 percent, because a platform that crops the square icon takes the ends off the bars. Measured 2026-08-29: 48,788 B for the six files, of which 46,869 B is raster.

Every path in the manifest is relative, which is what makes the project path a non-issue: `start_url` and `scope` are `.`, and each icon `src` starts `./`, so all of them resolve against the manifest's own URL. SvelteKit rewrites `%sveltekit.assets%` per page depth, so the root emits `./manifest.webmanifest` and a dated page emits `../manifest.webmanifest`, and both land on the same file.

## Design rationale

Prerendering everything was the decision the rest hangs off. It was chosen over a runtime fetch of `digest.json` because it collapsed four problems into zero: the loading state stopped existing, the request budget stopped being a budget, a contract-invalid payload became a build failure instead of a reader-facing error, and the page kept working with JavaScript off. The cost is one framework dependency and a build step that enumerates committed directories. Authority: Jony ([../../../.github/agents/jony.agent.md](../../../.github/agents/jony.agent.md)).

**Two of those four came back on 2026-09-01, and they were sold rather than lost.** A reading document carries a seed and the browser fetches the rest, so a reading page has a loading state - one sentence past `ui.payload_slow_ms` - and an invalid story past the seed reaches the browser rather than the build, which is why `idhazh validate-days` exists. What was bought is the cap date: the dated route trees were 39.5 percent of the published site, and the site went 168.6 MB to 88.1 MB with the runway from 130 published days to 279 ([layout.md](layout.md)). The other two hold unchanged - the request budget is still one file, and every page still renders with JavaScript off, a reading page down to its seed. Authority: Fowler, 2026-09-01.

**A third cost was paid at the same time and no reader can see it.** A crawler that does not run scripts now reads a dated page down to its seed and no further, so whatever those pages were worth to a search engine falls to what the seed carries. `/` stays complete and crawlable down to its seed, which is the one page a stranger is most likely to arrive on. This is the least reversible part of the migration: prerendering the dated pages again would be a build change, and an index that has dropped those stories does not come back on the same schedule.

**The eight routes that are still prerendered are a decision, and they are not the leftover half of the one above.** Four reasons hold it. One document a build is not one a published day, so what remains costs the site nothing that grows. The seed and the leading block on `/` ship in the first bytes rather than a request away, because it is the address a stranger meets first. A failed fetch on `/` leaves the reader the seed with `MoreDays` under it, which a dated URL cannot offer - so its failure sentence names the shortfall in the day's own units rather than claiming the stories on screen are all of them. And the fourth is not a property of `/` at all, which is why it settles the question: **without the declaration the site root emits no `index.html`, and GitHub Pages answers every address including `/` at HTTP 404.** Authority: plan 26 section 0.2, 2026-09-12, over an instruction that called prerendering legacy and was reading the tree as it stood before 2026-09-09, when the dated routes were prerendered at twelve documents a published day and 39.5 percent of the published site. Reversing it is one row of the table below and needs the owner.

**What it costs was measured rather than assumed, and the bytes turned out not to be the question.** One tree built both ways - as it stands, and with the seven declarations deleted and nothing else changed - three interleaved passes a case at one pinned `BUILD_VERSION`, and zero spread on every quantity. With prerendering the built site is 106,316,899 B and without it 104,681,197 B, so prerendering costs **1,635,702 B: 1.54 percent of the published site, which is 1.6 MB of a 1,024 MB cap, or 18 published days of the 1,047 the runway has left.** The case without the declarations writes no `frontend/build/index.html` at all and leaves `404.html` as the only HTML file in the tree, and `npm run build` exits 1 on it, because `frontend/scripts/build-state.ts` refuses to certify a build whose root document is missing - so every browser spec would stop collecting as well. The hardware, the method, the pin and every figure are in [../../reference/benchmarks/prerender-on-and-off.md](../../reference/benchmarks/prerender-on-and-off.md), which is the page to cite and the page a better number replaces.

Removing `uplot` restores the refusal one row below rather than overturning it. Guardrail #8 requires a dependency to name a beneficiary feature; its recorded beneficiary was pan and zoom, and `Viewport.svelte` implements those itself with a keydown handler and four buttons. What it actually drew was a second, smaller copy of the compression scatter with less information than the SVG above it. It would come back for pan and zoom *inside* a single chart, which is a different requirement, and the gzipped route chunk would be re-measured on that day rather than reusing the 2026-08-23 figure. Authority: Jony, Guardrail #8.

Taking `d3-scale` and `d3-array` a day later is not that decision reversed. A
chart library owns the element, the redraw and the theme, which is how the last
one ended up drawing a chart that already existed; a scale library returns a
number. The beneficiary feature Guardrail #8 asks for is the whole console: four
charts that agree on what a pixel is. The cost is measured rather than argued -
the gzipped route weight was measured and written into
`docs/reference/pipeline-cost.md`, and Carmack made measuring it a condition of
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

**This page became a shell page and an index on 2026-09-23, and five pages came off it.** It answered at least six questions at about 32,250 tokens, which made it the heaviest page the routing table could send an agent to once the config page was cut. The stem keeps the question a reader of a route arrives with - what a build writes and what a browser fetches - and each child keeps one of the others. The cost is real and is the usual one: a ruling whose page nobody can guess now costs a table lookup, where before it cost a long scroll ([../../reference/documentation-structure.md](../../reference/documentation-structure.md)). Authority: Fowler.

## Rejected alternatives

The reader's shell and the routes. A ruling about one story, one day page, the
archive or the encoder is on that part's own page; the console's own table is on
[console.md](console.md) - a reader row and a console row share nothing but a
heading, so one table over both would be two tables with a line between them.

| Option | Why rejected | Authority |
| --- | --- | --- |
| Runtime fetch of the day payload | Invents a loading state, a request budget and a runtime error class, all of which prerendering deletes. Two of the three came back on 2026-09-01 and were sold for the cap date rather than lost. | Jony |
| Deleting the seven `prerender = true` declarations, so every route renders in the browser | `adapter-static` has one fallback, so GitHub Pages would answer every address including `/` at HTTP 404 and `npm run build` would exit 1 with no root document to certify; the home page would have no first-screen content and its grid would re-wrap under the reader when the leads arrived; the console's first paint would be blank; and nothing on the site would render without a script, `/archive/`'s month disclosures included. Measured 2026-09-12, it saves 1,635,702 B - 1.54 percent of the published site, 18 published days of runway out of 1,047. | Plan 26 section 0.2, 2026-09-12. Only the owner may reverse it |
| Drag-and-drop or slot-based layout | No left and no right on a phone, unbounded QA, and per-reader layout breaks the shared-link promise. | Jony |
| A third theme on day one | Three band colours, eight swatches and a focus colour to carry forever for a reader nobody has named. | Jony |
| A service worker or offline shell | It can serve a reader a stale day, which attacks the rule the whole layout rests on. | Jony |
| A per-route first-load JavaScript ratchet | It failed every later branch until somebody retyped the number, and it answered for nothing the two remaining checks do not. | Carmack, 2026-08-30 |

## See also

- [what-a-story-shows-and-where-each-fact-sits.md](what-a-story-shows-and-where-each-fact-sits.md) - one story, and where each of its facts sits.
- [how-a-story-chart-is-drawn-and-what-refuses-one.md](how-a-story-chart-is-drawn-and-what-refuses-one.md) - the picture inside a story that earned one.
- [how-a-day-page-is-arranged.md](how-a-day-page-is-arranged.md) - the day from header to footer.
- [how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md) - filtering, browsing the archive and searching it.
- [the-on-device-encoder-and-its-vectors.md](the-on-device-encoder-and-its-vectors.md) - the encoder a search downloads, and what makes its vectors comparable.
- [console.md](console.md) - the operator's surface: which panel is on which route, and the ruling behind its shape.
- [layout.md](layout.md) - the routes, the dated addresses and retention.
- [../sources/health.md](../sources/health.md) - the feed ledger, and the quarantine rule the console mirrors.
- [../../reference/github-actions.md](../../reference/github-actions.md) - the four-run cadence.
- [../../concepts/digest.md](../../concepts/digest.md) - what an item carries and the visual rule.
- [../../concepts/design-system.md](../../concepts/design-system.md) - typography, tokens and the colour rule.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shell's obligations and the five states.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload this renders.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings and the bundle gate.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #1, section 0 and section 12.
