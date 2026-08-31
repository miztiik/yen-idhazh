# Published Frontend

**Last Updated**: 2026-08-30

The reader's surface: what is built, what deliberately is not, and the rulings behind both. This page is the living record for the digest page, the archive and the console.

Concept-level *why* lives in [../../concepts/digest.md](../../concepts/digest.md), [../../concepts/design-system.md](../../concepts/design-system.md) and [../../concepts/ui-shell.md](../../concepts/ui-shell.md). This page is the *shape*, and it records where the owner, Jony and Reader disagreed and how it was settled.

## Everything is prerendered

Every route is generated at build time with its items inlined in the HTML. SvelteKit with `adapter-static`, `prerender = true`, and `entries()` enumerating the committed date directories.

Three consequences, and each one removes a whole class of problem:

- **The reading path makes zero runtime requests.** One document and it is done - well inside the two-request budget, and the page works with JavaScript off.
- **There is no loading state to design**, and therefore no spinner to be tempted by. The payload loader still exists as exactly one module; it runs in Node instead of in a browser.
- **A payload that fails its contract fails the build.** What would have been a runtime error a reader discovers becomes a build error nobody ships.

**Three files are fetched, and none of them is on the reading path.** The
console reads older telemetry shards when an operator pans back. The archive
reads the month index behind its story list, that month's sibling vector file
when a reader asks to search, and the day payload behind a result it is showing.
A day page, a topic page and the home page still make no request at all. The
rule is about what a reader waits for to read the news, and it is unchanged.

The loader lives under `frontend/src/lib/server/`, which is the framework's own guarantee that it can never be bundled into anything a browser receives.

**A tree with no day in it still builds.** The dated routes are prerendered and their entries come from the committed digest tree, so on a clone that has never run the pipeline they produce no page and SvelteKit exits 1 on `/[date], /[date]/[vertical] not found while crawling`. That made building the site wait on a pipeline run, against [../../../CLAUDE.md](../../../CLAUDE.md) section 1a - a fresh clone runs on the defaults. One published day with no item did the same to `/[date]/[vertical]` on its own.

`handleUnseenRoutes: 'ignore'` clears both and hides every later prerender defect with them, so the build asks the tree instead. [../../../frontend/prerender-guard.js](../../../frontend/prerender-guard.js) excuses `/[date]` only when no day is published, and `/[date]/[vertical]` only when no published day names a topic. Any other unseen route still fails, and so do those two when the tree says they had a page to build. The guard asks a smaller question than `entries()` does - `entries()` lists the days, the guard only asks whether any day is there at all - so the two can disagree, and a disagreement fails the build. [../../../frontend/tests/prerender-guard.spec.ts](../../../frontend/tests/prerender-guard.spec.ts) drives the real handler off the real config, so the wiring is under test with the rule.

**Whatever the root layout's load returns is inlined into every page beneath it**, so the root layout returns the four facts the footer prints and never the day they were read from. The home page loads the day it renders. The layout used to return the whole latest day, which put a day of article summaries on the console, on `/evals/`, which draws none, and on every older dated page that already carried its own. Measured 2026-08-26, `gzip -9` over each prerendered page, one tree carrying five published days built twice with only that field differing: `/console/` 406.3 -> 93.0 KB, `/evals/` 315.6 -> 2.4 KB, `/2026-08-23/` 439.6 -> 126.0 KB, and 15749.2 -> 6343.3 KB over all 31 pages. Two builds of the same tree agree to within 0.1 KB.

[frontend/tests/payload-weight.spec.ts](../../../frontend/tests/payload-weight.spec.ts) holds that line. It counts a marker only a day payload carries and fails on any page below the layout that has one. It had one exclusion, `/archive/`, which inlined every committed day on purpose to feed the on-device search; the exclusion is gone from 2026-08-27, and the archive now carries an assertion of its own that it holds **zero** day markers.

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
| Ready | Normal | Prerendered HTML with the items in it |
| Empty | Payload exists, no items | "Nothing was published for *date*", with plain copy that does not point at a notice that may not be on the page |
| Missing | No payload for that date | A 404 that names the date and offers the archive. **Never a redirect to today** - a reader who cannot tell a dead link from a live one has lost the ability to trust any link |
| Unpublished | No day published at all - a fresh clone | The build succeeds. `/` says "No digest has been published yet" and `/archive/` says "Nothing has been published yet". There is no dated page to link to, so neither offers one |
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

The browser's own chrome follows the page. `app.html` ships two media-scoped `theme-color` tags, one per system preference, because an installed window reads those at launch before any script has run. A media query only knows what the system wants, so `apply()` in `$lib/theme` also writes one unconditional tag from the resolved `--color-bg`; an unconditional tag wins over both, which is what keeps a manually chosen light page from sitting under dark chrome.

## Installability

`frontend/static/manifest.webmanifest`, four PNG icons and the `theme-color` tags above. That is the whole feature, and the doctrine around it - including the ban on `Notification` and `PushManager`, and why there is no service worker - is in [../../concepts/ui-shell.md](../../concepts/ui-shell.md).

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

## The archive lists stories, and fetches them a month at a time

`/archive/` used to list five dates and no articles, and it inlined every committed day whole so on-device search could read the vectors without a request. Measured 2026-08-27 on one checkout, six committed days and 2,237 items: **1,766,682 gzipped bytes**, growing **489,843 bytes** for the one extra day that carried 621 stories. The page a reader opened to find one story carried all of them. It is **2,912 bytes** now, and one more day of 621 stories costs it **24 bytes** ([../../reference/measurements.md](../../reference/measurements.md#the-archive-stops-carrying-the-corpus)).

What it renders now, top to bottom:

- The counts and the retention promise: "6 days, 2237 stories. Nothing here is deleted."
- **The days as one compact row** of short dates. "The whole of Tuesday" is still a real request, and the row grows about 60 bytes a day, but a full date per line is an index rather than reading.
- **The stories**, newest day first, each a link to its own anchor on the day that published it, with the date and the topic beneath.
- **`Show 25 more`** - the same explicit control the day list and the console's failure list already use, sized by `ui.archive_page_size`.

**The stories are fetched, not inlined**, from `index/<YYYY-MM>.json` staged into `static/`. [layout.md](layout.md) owns why, and the short version is that inlining them would leave the page growing per story, which is the defect the index exists to end. Paging back into an older month fetches that month; a month already in hand is not fetched twice.

**Nothing the list needs sits under `assist/`.** That path is the on-device encoder, which the bundle must render complete without ([../../../CLAUDE.md](../../../CLAUDE.md) section 0a). Browsing is not a model feature, so the index is served from its own `index/` path and the list works with the whole model directory deleted. `frontend/tests/archive.spec.ts` holds it by failing every request under `/assist/` and asking for the stories anyway.

Four rulings behind the shape, all Jony's:

- **No sort control.** Per-reader ordering is forbidden by [layout.md](layout.md) - two people at one URL see one order.
- **No infinite scroll.** It takes the footer away from the reader and has no resting state.
- **The header states the retention window**, which the page did not do and which [layout.md](layout.md) requires before anything is deleted.
- **The per-day story count and the partial flag left the day row.** A count beside every date is what turns a compact row back into a wall, and a day page states its own count. Run health belongs to the console.

The degraded states, and each one is designed rather than discovered:

| State | What ships |
| --- | --- |
| No index, or a month that will not load | The day row, and one line: "The story list could not be loaded. Open a day above to read it." |
| JavaScript off | The day row, and a `<noscript>` line saying the list needs it. The day links are prerendered, so navigation still works |
| Nothing published at all | "Nothing has been published yet.", as before |

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

The day a result was found on sits **on the item's own meta line**, as the link
back to it, in place of the day the publisher put on the article. The two are
the same day or one apart, and printing both put two dates on a line that
already carries four facts.

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
| `/console/model/` | **Model** | What the model wrote, how long it took, and what it got wrong. |
| `/console/machine/` | **Machine** | The hardware the model ran on, and how much it varied between runs. |

`/console/` keeps its path. It is the one an operator types and the one every
existing bookmark points at, so moving it to `/console/pipelines/` would have
cost a redirect and bought a symmetry nobody asked for.

**The labels are the owner's own words, taken verbatim on 2026-08-30.** Each
carries a one-line description under it and the same text as a `title`. `Model`
and `Machine` share a first letter, which is the recorded cost of that name set;
it is paid off by the description line and by the silhouette of the first panel
on each route, which is what an operator recognises before he reads a word.
`What the model did` survives verbatim as the h2 on the Model route - it is
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

### The standing band carries four things and nothing else

Above the strip, on all three routes: yesterday's verdict as a sentence, the one
worst thing and which route it is on, site size against the 1 GB cap with its
runway, and the window control. It is derived once in
[../../../frontend/src/lib/server/console-shell.ts](../../../frontend/src/lib/server/console-shell.ts)
and read by all three, so they cannot disagree about which route is worst.

The first three are **not windowed**, and that is the difference between the
band and the per-article cost panel on Pipelines. The band stands on every
route, so a figure that moved when a control on one route moved would read as
three different sites. The runway is taken over every published day on record
and says so.

The window control sits **inside** the band rather than under it, because a
control below the thing it governs is read second. Each route hands its own
control in: Pipelines prices the month files a wider window would fetch, Model
fetches nothing and prices nothing, and Machine draws no control at all and
prints a sentence saying where the control is. That last one is a deliberate
departure from "the band carries the window control on all three routes": every
figure on Machine reads one fixed span, `console.default_window_days`, and a
control that answers a click by changing nothing is worse than an absent one.
What the sentence in its place prints is the span itself, with both dates - a
figure whose span a reader cannot SEE is worse than one he cannot change, and
the bound is also what stops the cache chart growing a column a day forever.
The choice is still shared - all three routes read the same
`idhazh:console-window` key - so setting it on Pipelines and clicking Model
keeps the span.

### What the Machine route draws

Nine panels, all off `state/runtime-counters.csv` and `state/item-health/`, both
read at build time under `$lib/server/` and neither published. The route added
no telemetry column and no reader sees a cell of either ledger.

| Panel | Grain | The sentence it is for |
| --- | --- | --- |
| Shards of the newest run | one row a shard | Was the day slow because of the work or because of the machine. |
| Reading against writing | the newest run | What a written token costs against a read one. |
| Prompt cache | one column a day | Whether a bigger cache would save wall clock. |
| Context headroom | one bar a day | Whether raising the truncation cap is even possible. |
| Do the two clocks agree | one bar a shard | Whether the day's rates can be trusted at all. |
| The host under the newest run | the newest run | Which processors it drew, how busy they were, how close to 16 GB, and how long the weights took to open. |
| The shape of a run's latency | one curve a run | Whether a tail changed shape, which no single percentile says. |
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

**A run whose rows cannot be made into one run is named on the page.** The
reader refuses a run where one shard index committed two different scrapes -
two workflow runs computed the same run id and `merge=union` concatenated both -
and the route prints the run id and the reason rather than quietly excluding it
from a count nobody can then check.

**The cost panel is a counterfactual and never a bill**, and it is the one place
on this site a figure in currency appears. CLAUDE.md Rule #10 carries the
owner's carve-out for it; the condition is that the page prints the rate it used
and says whether that rate came from `config/idhazh.json` or from the operator.
The operator's pair is kept in `localStorage` and read on mount only, so the
first paint always matches the prerendered document, and every cost figure on
the page is derived from one shared value rather than from four copies that
could drift.

### Three cross-boundary carries, one sentence each

Each route ends its introduction with one sentence pointing at a panel another
route owns: Pipelines says what the model spent of the day it just described,
Model says how far apart the day's runs read, Machine says how many articles the
day published. No chart, no card - a signpost that looks like a figure gets read
as one. They exist because the failure mode of splitting a page is a route that
hides the panel explaining another route's numbers.

### Machine ships almost empty, and says so

The pipeline has written `state/runtime-counters.csv` since 2026-08-26 and no
page has ever read a cell of it. The route exists before its panels do, and says
what is missing once at the top and once per named panel. A route that hid
itself until it had data would be a route nobody knew to check - which is
exactly how a ledger goes four days unread.

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

**The strip starts on the left, and the spare room is on the right.** Until
2026-08-30 a history shorter than its frame was pushed to the right edge, on the
argument that the newest run should sit in one place whatever the day count.
Re-measured on 2026-08-30 after merging `origin/main`, at 1440px over the
committed ledger, on this tree with the one alignment declaration flipped back:
its ten days draw 421px inside a 1326px frame, so right-anchored they leave
905px of empty page on the left - the strip uses 32 percent of its own row,
which reads as one that failed to draw rather than as one with room to spare.
Left-anchored the same ten days start at the frame's own left edge, 0px in, and
the 905px of room falls on the right. The argument for the right edge is the
thing that broke it: the ledger went from nine days to ten while this change was
being merged, so a right-anchored strip slid every column one place left and a
run the operator had looked at yesterday was somewhere else today. Left-anchored,
a day keeps its place and the empty room is on the side the days that have not
happened yet belong to.

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

Beneath the strip is **every feed that failed at least once, nearest to a rest first**. A feed with a clean record is not listed: the operator came here to find what is broken, and a list naming all seventy sources hides the four that are. The failing rule matches `FeedHealthRow.failing` in the contract exactly - a `200` that parsed to no entries counts as a failure, a `robots.txt` refusal does not ([../sources/health.md](../sources/health.md)).

**The count beside a feed is its run of failures, not its lifetime total.** The
pipeline rests a feed on failures in a row ending at the newest read, so that is
the number the page prints. A source that failed twelve times in July and
answered this morning is healthy, and a lifetime total printed beside a rest
marker is a number the pipeline never used to rest anything. The rule is
restated on the read side in `frontend/src/lib/feed-health.ts`, which runs the
same loop `discover._rests` runs, so a test can drive it with rows it made up.
Ranking follows the same fact: nearest to a rest first, then by how much has
gone wrong in total, because a feed four failures into a five-failure rule is
one run from being dropped and a feed with more failures spread over a month is
not.

**Each feed carries a target bar and a strip of days.** The bar's track is
`collect.quarantine_after_failures`, its fill is the run of failures, and its
marker sits on the threshold - the same `TargetBar` the truncation cap and the
router-minute rule draw with. The strip is one square a day over the page's
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
there read as a fourth constraint on the run. It is on the Model route now,
under `What one summary cost`, beside the cost of writing the summary it checks,
and it prints its middle and its slowest one in twenty over the summaries it
timed. An empty cell is one fewer item timed, never a zero; a zero is the value
the column defaulted to before it was written, and it is counted as untimed for
the same reason. Authority: owner, 2026-08-31.

The viewport is a 30-day default window, not a retention policy. The window size
and where today sits are `console.default_window_days` and
`console.today_anchor`. Arrow keys pan, and `+` / `-` step the window to the
next preset, from a labelled focusable control with a visible focus ring; the
buttons beside it pan with a pointer. **Every console chart is hand-written SVG
rendered on the server**, so the page is complete before any script runs and
stays complete if none does. If a telemetry month is absent or cannot be parsed,
that month is a gap in the charts. It is not interpolated, and it never
white-screens the console.

### One window governs the page

The window belongs to the page, not to the viewport, and one control at the top
of the console sets it. It is a set of radio buttons carrying
`console.window_presets` - four spans, all four on the page at once, so the cost
of the wide one is readable without opening a menu. A slider was rejected for
the same reason: every span is a different number of month files to fetch, and
the spans between these four cannot be told apart once drawn.

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
| `Site size` | Absolute number always; the delta and the runway are windowed | The size is a level and the operator wants today's whatever span he is reading. The delta and the runway are rates, and a rate has to say what it is over. |
| `Router minutes per chart` | Prints `The rule reads 14 days. Widen the window to see it.` under 14 days | The retirement rule is stated over 14 days. A median of the wrong span is the same figure with a different meaning and nothing on the page to say which one is being read. |

`Sources cut short most often` used to hard-code seven days. It follows the
control now, and the section prints its own denominator, which at seven days
runs as low as six articles. Its rows are aggregated once per preset at build
time - four sets of ten costs less than one fetch, and it keeps the section
working with no script at all. It follows the window's *length* rather than
where a pan leaves it, and the section says so: the days it reads always end on
the newest day the ledger holds.

`Charts published` used to draw a smoothed line over a fixed fourteen days,
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
- **Why items failed**: a ledger of causes, then the rows behind a selected one. **A cause is a stage and a code**, ranked by count through `RankedList` - a bar in the cell, a markup sparkline of that cause's daily count, and breadth as `sources hit: 3 of 47`. **Breadth is the column that earns its width**: one source changing its markup and the extractor being broken carry the same count and a very different number of sources, and until this landed the two read identically. The rows below are the detail: still newest-first, which is the one shape on this page a date sort is right for, still **capped at `console.failure_list_max` with a `Show 25 more` button**, and still stating their own scope - `Showing 25 of 214 failed items in this window.` A code chip and a selected cause both filter them; a new window, a new chip or a new cause resets the cap, because each is a new question. **The `Item` column is gone and `item_id` rides on the row's `title`**: it is a content address, it was the widest cell in the table, and no operator acts on one - the page-level grep it cost is a terminal job. Uncapped the list measured 7824px against 800 rows and put the compression chart at document y=9105. The section sits last for the same reason: it is the only child that can outgrow the screen, so it cannot sit between two charts. **There is no cause text and none is invented** - the published projection withholds `detail` ([telemetry-series.md](telemetry-series.md)), which can carry fetched article text, so the code is everything the browser is given. **The stage is a word and not a mark.** The design asked for a monochrome stage glyph beside it and it is refused here: the icon set is one generated module that reaches every route, because a lookup on a dynamic key cannot be tree-shaken. Fifteen glyphs cost the routes 1,404 to 1,900 gzipped bytes (measured 2026-08-29, [../../concepts/design-system.md](../../concepts/design-system.md)), which is 94 to 127 bytes a glyph a route against a 64-byte ratchet tolerance, so three stage marks would move `/`, `/404`, `/<date>/`, `/<date>/<topic>/`, `/archive/` and `/evals/` - six reader routes that cannot show this section at all. The same page calls an icon that needs a caption a label wearing a costume, and the stage name is already in the cell.

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

**Two charts carry a pointer readout, and it is not an SVG `<title>`.** The
stage-timing and throughput trends each get a strip below their plot.
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
become a paragraph beside a chart being glanced at. `FailurePanels` and the
run-health strip still get none. The run-health strip has no per-day point to
land on. The failure chart has one per stage per day, but it prints every
stage's rate and its denominator in type under the plot at all times, so a
readout there would only repeat a sentence that is never hidden.

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
hold the axis-thinning, the column arithmetic, the cap and the announcement, so
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
thinned evenly to `chart.tick_density` with both endpoints always kept, and the
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

**The x axis prints a date per column, thinned to `chart.tick_density`.** It used
to print one string for the whole span - `24-29 Aug 2026`, measured on the built
page 2026-08-30 - which is the run strip's sparse-label arithmetic, and that
arithmetic is right for a strip of 16px squares and wrong for a 760px plot. Six
labels over thirty days puts every mark within three columns of a date; one
label over six days put a spike nowhere at all. The first and last day are always
among them, evenly spaced indices fill the rest, and the year is printed once and
then only where it changes. `dayTicks` in
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
owns it, so the throughput candle beside it labels its axis the same way.

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
  on a column that has since moved to the Model route.
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

## The chart arm is a flow, and every drop leaves it as a named branch

`Charts drawn for articles` opens with one diagram of where items go between the
router reaching one and a chart reaching a page. It is drawn left to right, the
direction the page reads and the order the pipeline runs its stages in, and it
totals the whole open window rather than one day - a single day's four numbers
are already legible in the table under it, and "where do items go" is a question
about the window.

**It was a funnel until 2026-08-30, and a funnel could not answer the question
it was on the page for.** A funnel draws a monotonic sequence as a taper, so it
says how much is left at each step and nothing about where the rest went. The
three drops here have three different causes and three different fixes: an item
can be answered without the model being asked at all, the model can be asked and
draw nothing, and a drafted chart can fail the checks that run after it. A taper
shows all three as one slope. Every loss now leaves the flow as its own branch,
labelled `Answered without a chart`, `The model drew nothing` and `Did not
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
somebody has to edit, and re-measuring it is the reason it is.

Authority: the shape, Jony, 2026-08-30; the chunk, Carmack, 2026-08-30.

## The chart arm is judged against its own rule, and the daily rows come second

`Charts drawn for articles` is the only console section carrying a written
decision rule in its own prose: over a stated span the arm is retired if the
median day spends more than a set number of router minutes per published chart,
or puts a chart on fewer than a set share of the items it published. Until
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
label. `Reached`, `Asked the model`, `Charts drafted` and raw `Router minutes`
moved down with the table: the flow diagram above already draws the first three
as branches, and router minutes on its own is the numerator of the ratio rather
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

**The rule is read off the rows and never off the setting.** Every cut point
comes off the `source_words` cell a run wrote after its own cap fired. Two
things break if the page reads `extract.truncation_cap_tokens` instead. The
setting is one number, so a window spanning a change draws one rule where the
rows say two - measured on this tree the file says 5,000 tokens, which is 3,846
words, and half the window's cut rows sit at 1,923. And a rule from the file
draws even in a window where nothing was cut at all, which a derived one cannot.
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
reads as "the charts" rather than as the router's output, so it is `Charts drawn
for articles`. `Runs` sat four headings below `Run health` and neither name said
which was which; it became `Runs and site size`, which is what its columns were.
No doc anchor and no test selector read any of the three. `Runs and site size`
is itself gone since 2026-08-30 - two nouns joined by "and" is two sections, and
the section below says where each half went.

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

**The window bounds what is drawn and never what is differenced.** A day's cost
is its own bytes minus the previous manifest's, so the oldest day on screen
still reads against the day before it. Differenced against zero it would report
the whole tree as one day's work, and the window would invent an outlier every
time it moved.

**The `Site size` card carries the level, a track against the cap, the window's
delta and a runway.** The runway is the arithmetic
[../../../backend/idhazh/retention.py](../../../backend/idhazh/retention.py)
already runs: headroom divided by one published day's growth, where a day's
growth is the per-article cost times `run.safety_ceiling_per_run`. The item
ceiling and not an average of the days on disk - a day that published 97
articles is no evidence the next one will, and a runway has to be the worst case
to be worth printing (Rule #10). Where the window measured no growth there is no
rate, so the card says there is no runway instead of printing a date.

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
so the multiple itself is not stable. The card's sentence is therefore written
caveat-first: it says the number is the committed payload tree and not the
published site, that the site is what the cap measures, and that
`idhazh site-weight` prints the runway that binds - and only then that
`160 articles a day would fill this tree to 1 GB in about N published days`. It
never says "the site" has N days, because it does not know that. Measured
2026-08-30 the card read 2,038 published days and `site-weight` read 123, which
is the size of the gap the wording exists to keep visible
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

**Since 2026-08-31 there are three of them, one per route.** `/console/` is
capped at 250,096 bytes, `/console/model/` at 28,394 and `/console/machine/` at
30,391. One key over three surfaces still fails when any of them grows and then
cannot say which one did, so the operator raises the shared number and the
regression lands under it. Sizing them separately is what makes the split worth
having. **They are meant to expire** - all three of the first numbers did, on
the day they were set, when Model and Machine gained the panels they had been
standing empty for.

Each of the first two has the same three terms `/archive/` has, and only the
middle one differs:

```text
  115,562  heaviest of seven builds of the tree that ships
+ 134,470  seven published days, at 19,210 bytes measured by removing a real one
+      64  the build noise floor, derived in measurements.md
= 250,096  /console/

   20,392  heaviest of seven builds
+   7,938  seven published days, at 1,134 bytes measured the same way
+      64  the build noise floor
=  28,394  /console/model/
```

**All three moved on 2026-08-31, and every one of them was re-derived rather
than nudged.** `/console/` fell 547 bytes because `score_ms` left its timing
chart. `/console/model/` rose 9,712 because it gained the per-item cost
distribution, the per-run summary lengths and the model-swap comparison - and
because a published day now costs it 1,134 bytes instead of 730, since the
length panel draws a column per run and a day holds up to five. The owner's byte
ruling of 2026-08-31 is why the numbers moved and the panels did not.

`/console/machine/` was priced at 6,899 while it rendered no ledger - a published
day moved it minus three bytes against a nine-byte build spread, so its allowance
was a bound on text rather than a growth rate. It draws the runtime counters
since 2026-08-31 and is priced in RUNS, because a day that ran three times and a
day that ran five cost it differently:

```text
   22,242  heaviest of five builds
+   8,085  seven published days at 5 runs a day, 231 bytes a run
+      64  the build noise floor
=  30,391  /console/machine/
```

**A published day was priced by removing a real one, not by cloning one.** Take
every ledger the console reads - `state/scores.csv`, `state/item-health/`,
`state/feed-health/`, the published telemetry shard and the day's own directory -
drop one real mature day from all of them through `STATE_ROOT`, `TELEMETRY_ROOT`
and `DIGEST_ROOT`, and rebuild. Cloning a day instead reads 18 percent cheaper,
because gzip sees a near-copy of a block it already holds and a real day is not a
near-copy of anything ([../../reference/measurements.md](../../reference/measurements.md#three-console-routes-three-ceilings-and-a-day-priced-on-each-2026-08-31)).

**Seven days, and not the year `/archive/` carries, because of what the headroom
has to be smaller than.** The regression a page ceiling exists to catch on this
route is a day payload inlined by a layout, which cost 313,300 gzipped bytes when
it last happened. `/console/`'s slack is 134,814, so that regression is 2.32
times it and the gate sees it land; eight days would put the margin under 2x. The
horizon is the largest whole number of measured ordinary publishes that keeps the
margin above 2x. On the other two routes the margins are 60.6x and 199.6x, so
seven days is nowhere near binding there and the term that decides them is their
own growth rather than the guard.

**When one of them fires, the panel does not move.** The owner ruled on
2026-08-31 that no approved feature is removed, deferred or shrunk to stay under
a page-weight number: a ceiling is a ratchet, not a budget, so a crossed ceiling
means re-measure it, raise it, and record in the same commit what the bytes
bought. **This reverses what this page said until then**, which was to turn
`console.default_window_days` down and never to raise the number. That instinct
is still right when the page is inlining something the first paint does not need
- windowing the seed on 2026-08-29 and folding the compression scatter on
2026-08-30 were savings, and both are described below - but a saving is not a
cut, and neither is a reason to leave a panel unbuilt. What the ruling does not
waive: Rule #2's 1 GB Pages cap, which is a platform limit, and the 200,000-byte
lazy chart chunk, which stands because a new echarts registration is a decision
about the chart vocabulary rather than about size.

**Why a ceiling here does not cap the news, when one on a day page would.** A day
page and the home page render published items, so the only way under a ceiling on
them is to publish fewer - and [layout.md](layout.md) forbids removing an item a
run published, so the ceiling would be deciding how much news ships. No console
route renders a published item. It is the operator's surface, and every figure on
it is derived at build time from ledgers that stay committed and complete
whatever the page shows.

### The response, taken on 2026-08-29 before the gate fired

**The compression scatter reads the published telemetry projection, and the
score ledger no longer reaches the page at all.** Both halves shipped together,
which was always the only way either of them worked.

The page used to build one point per row of `state/scores.csv` on the server and
inline every one of them into the prerendered HTML. That ledger held 2,791 rows
on 2026-08-29, gains about 349 a day, and nothing trims it. The plot now folds
the same telemetry rows the failure panels already use - seeded to
`console.default_window_days` on the server, grown by month fetch in the browser
- so **the scatter costs the page nothing beyond the telemetry it was carrying
anyway**, and an operator who pans back gets the plot for those days at the same
moment they get the panels.

`frontend/src/lib/charts/series.ts` owns the per-row decision now, as one
function with three outcomes: a point, a row with no article length, a row with
no summary. It used to sit in `frontend/src/lib/server/model-work.ts` and could
only run at build time. **One decision, because the plot and the sentence under
it read the same answer** - counting the unplaced rows anywhere else lets the two
disagree about the same row on the same day.

**One mark per article per day, never one per row.** The score ledger held one
row a scored item; the projection holds one row per item per *run*, so a re-run
writes a second row for an article the first run already published. The run that
read the most of it is the one kept, with both of its lengths, because a length
before the cap from one run against a length after it from another measures
nothing. It is the rule `sourceCuts` already reads the same ledger by, so the
plot and the source table cannot disagree about how many articles a day had. The
canary carries an article two runs both wrote a row for, which is the fixture
that catches this: without the fold, Svelte refuses the duplicate key and the
whole console page fails to hydrate.

**What the projection made simpler, and it is not a byte argument.** The score
ledger has a `truncation_flagged` column that changed meaning on 2026-08-28, so
the plot needed a stamp gate to know which question a row was answering. The
projection carries the two lengths instead - `source_words_before_cap` above
`source_words` is the cut, and it has meant that on every row ever written. There
is no stamp to read and no second meaning to gate.

The article's own length is `source_words_before_cap` where a run wrote one down
and `source_words` where it did not, which is exactly `Article.full_source_words()`
on the producing side. A run before 2026-08-28 wrote no pre-cap length, so its
articles are drawn at the length that survived and carry no cut mark. That is the
honest reading: the ledger holds no answer to what those articles were, and a
mark on them would claim a cut nobody measured. It cost the page one sentence,
which is gone with the state it described.

**Measured 2026-08-29**, both arms built back to back on one tree, one machine
and one Node, against the same committed ledger, so the figure is a difference
rather than an absolute:

| | before | after | difference |
| --- | --- | --- | --- |
| `/console/` prerendered HTML, gzip -9 | 175,892 B | 148,800 B | **-27,092 B, 15.4 percent of the page** |
| `/console/` first-load JavaScript | 69,410 B | 69,622 B | +212 B, 0.3 percent of the route |
| room left under the 301,580 B ceiling | 125,688 B | 152,780 B | +27,092 B |

The decision moved into the browser bundle and cost 212 bytes there, which is
128 times less than it took off the document. Two builds of the branch on this
tree read 69,622 and 69,617, so the spread is 5 bytes against a tolerance of 64.

**What the page grows with now, and what that is worth.** Not the ledger, and
that is the whole point: a term with no bound became one with a bound. The seed
is one window of item telemetry, so once the window is full a published day
entering it pushes the oldest day out and the page stops moving with the
calendar. Removing one mature published day from the projection and rebuilding
cost 35,130, 34,922 and 29,765 gzipped bytes over days of 1,000, 1,000 and 872
rows - **about 35 gzipped bytes an item-health row**, steady to within 3 percent
across the three, or about 48 bytes a published article.

Read that as a steady state rather than as a rate, because a rate is what it
stopped being: the page settles at `console.default_window_days` times the rows a
day writes, times 35 bytes. At the 160 rows a day the last two committed days
wrote, thirty days is about 168,000 bytes of seed and the page sits comfortably
under the ceiling. At the 1,000 rows a day of 2026-08-24 it would not, and **the
knob to turn then is `console.default_window_days`, not the ceiling** - it is a
number an operator can reason about, it shortens only what the page opens on, and
panning back still fetches whole months. Since the owner's ruling of 2026-08-31
that is the better first move rather than the only one: windowing a seed the
first paint does not need is a saving, and raising a re-measured ceiling is now
also an answer.

**The `/console/` ceiling was not moved on the day this landed, and that was
right at the time.** The page was 148,800 bytes against a 301,580 ceiling, so the
headroom was 152,780 - more than the three published days it had been sized for.
That is the gate working, not a number to re-derive on the day a saving lands. It
was re-derived at the close of the console-signal plan instead, once the page had
settled and the unit it grows by had changed, and it came down to 259,908; the
section above carries that derivation. The key is asserted in ten files,
including `backend/tests/test_contracts.py` and
`tests/fixtures/contracts/app-config/tuned.json`, so moving it is a change of its
own and never a footnote to another one.

Two things that are still not the answer. **Raising the number** spends the
headroom somebody measured and buys days, which is the move that got the last
`/archive/` ceiling deleted after it was raised twice in one day. **Thinning the
plot** - sampling points, or dropping the oldest days from the ledger - changes
what the chart is a measurement of, and a scatter that quietly stopped drawing
some of its rows is worse than one that got heavy.

**The first of those two was reversed on 2026-08-31 and the second was not.**
The owner ruled that a page-weight ceiling is a ratchet rather than a budget, so
raising it - re-measured, with the reason recorded in the same commit - is now
the correct response to a page that genuinely carries more, and no approved
feature is cut to stay under a number. What that ruling does not touch is
thinning the plot: that is not a byte decision at all, it is a change to what the
chart measures, and it stays wrong for the reason written above. The section at
the head of this page carries the current rule.

Authority: Jony and Fowler, 2026-08-29; the measurement and the worst-case
sizing, Carmack.

### The second response, 2026-08-30: the plot stopped being a mark an article

Windowing the seed bounded how many rows reached the page. Replacing the scatter
bounded how much page a row costs, and it is the larger of the two. Measured
2026-08-30 on Windows 11, node v24.12.0, 12th Gen Intel Core i7-1265U, both arms
built back to back in one session on one tree over one committed ledger:

| | scatter | band split | difference |
| --- | --- | --- | --- |
| `/console/` prerendered HTML, gzip -9 | 179,797 B | 106,927 B | **-72,870 B, 40.5 percent of the document** |
| `/console/` first-load JavaScript | 80,834 B | 82,330 B | +1,496 B, 1.9 percent of the route |
| room left under the 301,580 B ceiling | 121,783 B | 194,653 B | +72,870 B |

The control is what makes those the change rather than the machine: the untouched
arm read 80,834 B against a record of 80,831, and the six routes this row does
not touch each moved 12 to 14 B down between the two builds, which is the shared
shell getting lighter as one component leaves the client manifest.

The first-load number went the other way, and it is the trade rather than a
regression. `RankedList` and the `rank.ts` arithmetic behind it had no call site
until this row, so every build before it tree-shook them away; the scatter's log
axis, cap-line arithmetic and pointer readout left in the same commit. 1,496 B of
JavaScript bought 72,870 B of document, which is 49 times its own size, and the
document is the part every visit pays for whether a script runs or not.

**What the chart now grows with is a column a day, not a mark an article.** A
published day adds up to three rectangles and its share of a date label, whatever
it published. The page is a separate question, and the closure measurement
settled it on 2026-08-30: the prerendered seed still carries one row per planned
item per run, so the document is linear in telemetry rows at **20.09 gzipped
bytes a row** - a third of the 60 bytes an item the scatter charged, and bounded
by the window rather than by the calendar. The ceiling was re-derived against
that shape and came down to 259,908; the section above carries the arms.

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
across the month instead of doubled. Seven, because a week is already this
site's unit for what a reader still has in mind: `ui.read_mark_days` keeps a
read mark for seven days and `console.min_window_days` will not draw a narrower
window. Authority: Carmack on the fetch cost, Jony on the sentence, 2026-08-27.

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
| Reconciling the encoder identifier to the upstream `all-MiniLM-L6-v2` | `embeddings.model_id` is a slug, so that spelling can never be written into a payload. Adopting it means widening a persisted contract to fit a capital letter, and re-stamping five committed days to buy nothing. | Fowler, Andre |
| A config knob for the encoder identifier or its version | The guard compares a payload against this string. A knob is a way to turn the guard off by accident, which is the same reason `embed.py` refuses one for its own copy. | Andre |
| Telling the reader their vectors are stale and offering to update | There is no update for them to take - the encoder is whatever this build committed. A prompt with no action behind it is a notification asking for thanks. | Jony, Reader |
| Reaching a full month back from the newest published day on every date | A constant window, bought with two whole shards on 29 days out of 30 and a second 518 KB browse index charged to every visitor who only browses. | Carmack |
| Naming the months a search read, rather than the days | On 1 September "September 2026" reads like thirty days and holds one. The month name is what hid the collapse it was meant to disclose. | Jony |
| Padding every sequence to the token cap so batch composition stops mattering | It was the first proposal and the measurement refused it. Fixed padding removes the *shape* a batch imposes, not the *scale* it sets: pad-to-cap against no padding still moved a component by 1.56e-2, and padding also moves the runner further from a browser that pads nothing. | Carmack, Rule #10 |
| Accepting host variation and gating a re-encode on cosine alone | A cosine tolerance is the right check for a backfill, but leaving the arithmetic unpinned makes every future re-encode a fresh argument about which machine was right. | Carmack |
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
| Suppressing the failure chart for a window holding one day | It was right when the panel drew one bar per stage: a chart of a single value is a rectangle. The column carries the volume now, so one day is one column and still says how much work there was. Only a window holding nothing at all draws no chart. | Jony |
| Rendering every failed row in the window | 800 rows measured 7824px and pushed the compression chart to document y=9105. The rows are on demand. | Jony |
| A virtual-scrolling failure table | A dependency and a scroll-position bug for something a cap and a button already solve. | Jony |
| A per-day stacked bar list for stage timings | Thirty days is about 150 rows and no trend, and the trend is the only question the section is asked. | Jony |
| Clamping a zero stage timing into the bottom decade | It draws a plunge to the floor of the plot, which says the stage got a thousand times faster on a day it was merely quick. | Jony |
| A caret beside the line for a zero stage timing | A second shape for a fact the open dot already carries, and one more thing to learn before the chart can be read. | Jony |
| A dashed bridge across a stage-timing gap | A slope between two days that share no measurement is a number nobody took. | Jony |
| A fifth sub-millisecond decade on the stage-timing axis | It moves every mark on a 30-day chart to hold ten rows from one day. The axis is not the thing that was wrong. | Jony |
| `uplot` on the compression scatter | It drew a second, smaller chart beneath a complete SVG, and the pan and zoom it was bought for live in the viewport control, not in the plot. | Jony, Rule #8 |
| Fading the per-point band lines instead of collapsing them | The wash is a node count, not an alpha value. One fact drawn 1166 times is still drawn 1166 times at any opacity, and the fact has one value per configured band. | Jony, Carmack |
| A drawing library for the console charts - `echarts`, `@observablehq/plot`, `chart.js`, a component library | 336 KB gz on canvas, 128 KB gz and a DOM shim to prerender, 67 KB gz on canvas, and a component set is worst of all where every chart is bespoke. All of them own the element and the theme; the console needed the arithmetic. | Jony, Carmack |
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
| A readout on `FailurePanels` or the run-health strip | The run-health strip has no per-day point to land on, and the failure chart already prints every stage's rate and its denominator in type under the plot at all times. | Jony |
| A readout on `StageTimings` - reversed 2026-08-30 | It was refused because the chart "already prints its headline in type", and the headline it printed was the newest day. The chart had no per-day label and no mark, so the other twenty-nine days could not be read at all. The strip replaces the legend rather than joining it, so the count of things that move on the card is still one. | Susan, over Jony's 2026-08-25 ruling |
| A floating readout box over the stage-timing plot | Measured 2026-08-29 at 88 to 121px over a 220px plot: 40 to 55 percent of the chart it explains. A strip below the plot cannot occlude at any width, so there is nothing left for a dodge rule to solve. | Jony |
| Re-sorting the readout rows to the hovered day | The rows are the legend. A legend that re-orders under the eye as the pointer moves cannot be read, and the colour swatch already matches the line. | Jony |
| Labelling only the first and last day of the timing axis | That is what it did. It is what makes a spike unattributable to a date. | Owner, 2026-08-30 |
| A charting library for the readout | There is none on this surface and this adds none. One action beside `observeWidth`. | Jony, Rule #8 |

## See also

- [layout.md](layout.md) - the routes, the dated addresses and retention.
- [../sources/health.md](../sources/health.md) - the feed ledger the console renders, and the quarantine rule it mirrors.
- [../../reference/github-actions.md](../../reference/github-actions.md) - the four-run cadence that gives the strip four squares a day.
- [../../concepts/digest.md](../../concepts/digest.md) - what an item carries and the visual rule.
- [../../concepts/design-system.md](../../concepts/design-system.md) - typography, tokens and the colour rule.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shell's obligations and the four states.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload this renders.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #1, section 0 and section 12.
