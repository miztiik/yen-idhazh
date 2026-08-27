# Published Frontend

**Last Updated**: 2026-08-27

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
ledger still owns faithfulness and scorer time for the scored subset, and
`score_ms` is read through the same rule as the other three stages: an empty
cell is one fewer item timed, never a zero.

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
than a law. A chart whose domain is already decided by something else turns it
off, because rounding a fixed domain outward moves every mark on the chart to
buy a tick label that reads the same either way - which is how the compression
scatter gains a labelled y axis and still puts every point where it already
was. The log rule has two users: the compression scatter's x axis and the
stage-timing y axis, both drawing whole decades and the eight steps between
them. Which rule a chart takes is decided by the extent it draws, and the
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
one. `npm run bundle-gate` holds that true. Beside its encoder check it records
every route class's first-load JavaScript and fails when the number moves, so
the next dependency has to be measured and written down before it can ship. The
same script also holds each prerendered page's HTML under a ceiling, but only
for the routes whose weight does not grow with the published data - `/404` and
`/evals/`: a route that grows with the corpus is measured and reported, never
failed, so the payload workstream cannot fail a build over an ordinary publish
([../../concepts/config.md](../../concepts/config.md)).

The item-health viewport has three parts, in this order:

- **Failure panels**: fetch, extract and summarize failure rates as separate bars. **The rate is printed in type under each stage name** - `16% failed, 126 of 800.` - because an SVG `<title>` does not fire on touch and does not survive the screenshot an operator pastes into an issue. **The y domain is fixed at 0 to 100%.** Scaled to the window's own maximum, a single day in view normalised its bar to itself, so a 12% rate and a 90% one both filled the panel. **A window holding one day draws no chart at all**: a chart of one value is a rectangle, and the sentence is the panel. Thin denominators use outlined bars below `console.min_attempts_for_rate`, explained once under the row rather than once per bar. Colour is spent only on a failure.
- **Compression scatter**: source words against summary words on a log x axis with decade ticks and the eight steps between them, summary words labelled on a y axis of their own, the `summarize.bands` step function drawn once as a shaded target zone, and a distinct mark for truncation-flagged scored items. One chart, hand-written SVG. Two things it used to do: carry a second `uplot` canvas underneath drawing the same dataset with neither the band reference nor the truncation mark, which is two drawings of one dataset that disagree; and draw the band reference as one vertical line per point, which measured 1166 nodes on 2026-08-25 for a fact that has one value per configured band. The zone is one `<path>` at any point count, and `summary words` moved off the bottom row, where it was printed beside the x axis title of the variable it is not.
- **Failed item list**: the rows behind the shape, **capped at `console.failure_list_max` with a `Show 25 more` button**, and stating its own scope - `Showing 25 of 214 failed items in this window.` A panel chip filters it, because after a spike the operator needs rows, and a new window or a new chip resets the cap because it is a new question. Uncapped it measured 7824px against 800 rows and put the compression chart at document y=9105. It sits last for the same reason: it is the only child that can outgrow the screen, so it cannot sit between two charts.

Measured 2026-08-24 on the committed ledger: the console document went from
11552px to 4878px.

**Stage timings are one trend chart, not a list per day.** Four polylines over a
calendar x axis, oldest on the left, sharing the run strip's own sparse-label
arithmetic. The old block was one group of four bars per day - about 150 rows at
a 30-day window, and no trend - and "is it getting slower" is the only question
the section is asked.

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
  all ten rows of 2026-08-22.
- **A day timed in part** draws the items it timed, and the line under the chart
  says how many that was.

One line of type per stage names whichever of the three happened, because a hole
in a line is a mystery and three holes that look alike are worse than one: `We
timed no fetch work on 3 of the 30 days. The line breaks there.`, `score took
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

## The bundle gate is a regression detector, not a performance budget

`npm run bundle-gate` reads one number per route class - the gzipped first-load
JavaScript - and compares it against `frontend/bundle-baseline.json`. **The
threshold is the last known-good measurement and nothing else.**

It used to be a measured baseline plus an invented constant: 1 KB of "headroom"
on a reader route and 10 KB on the console. Nothing measured either one. Rule #10
forbids an unmeasured number justifying a design, and the console's 10 KB
allowance was down to 464 B spare within a day of being granted - which is what
an unused allowance always does. Both constants are gone, and the word with
them.

**A budget would need a cost this page does not have.** Every route is
prerendered, so the document is complete HTML before a script runs and the
reading path works with JavaScript off. First-load JavaScript is hydration cost,
not time-to-read. There is no measured number for what that cost may be, and
Rule #1 forbids the telemetry that would produce one, so the gate does not
pretend to own a budget it cannot defend.

**The ratchet is two-sided.** A route heavier than its record fails, and a route
lighter than its record fails too. One-sided decays back into a flat constant:
slack accumulates, the next regression lands inside it, and the gate goes quiet.
Tolerance is 64 bytes either way, the same for every route, and it is derived
rather than measured - see
[../../reference/measurements.md](../../reference/measurements.md).

Three things the file's shape is doing:

- **It is hand-edited.** No writer, no `--update` flag, no environment escape
  hatch. A file the build rewrites is a log, and a gate whose own tooling
  updates its baseline cannot fail. The printed lines are copy-pasteable, so the
  friction is ten seconds and the deliberate act is the friction working.
- **`why` is required, and an empty one fails.** That turns "edit the number"
  into a written justification sitting in the PR diff forever, and it gives a
  reviewer a one-sentence job instead of a byte-diffing job. The gate cannot
  tell whether a `why` went stale when `bytes` moved; a reviewer sees both in
  the same diff, and machinery for that is not worth building.
- **The measurement is per file.** Each module is gzipped on its own, because
  that is how it arrives - one response, one gzip stream. Gzipping the
  concatenation is order-sensitive, so a bundler reordering the preloads would
  move the number for a reason nobody caused.

The encoder symbol grep stays beside it. It costs no bytes and it names a cause
the byte number cannot: the byte gate catches the hazard that is not on the
list, and the grep catches the three that are.

| Option | Why rejected |
| --- | --- |
| Delete the gate | `/archive/` shipped at 873.1 KB of gzipped HTML and nobody noticed until somebody measured - the same failure class, on the axis that had no gate. Deleting the gate that exists *because* it is quiet reads half the data. |
| A transfer-time budget on a stated connection speed | Replaces one invented constant with two, and Rule #1 forbids the telemetry that would settle either. It also models a cost the reader does not pay, because the page is prerendered. |
| A relative cap - the console may exceed the heaviest reader route by N% | Couples two routes that have nothing to do with each other, lets a legitimate reader-route increase silently grant the console more room, and N is the same invented constant wearing a percent sign. |
| A flat constant with the justification written down | This is what was there, minus the prose. A written justification does not stop an allowance being spent: the 10 KB went to 464 B spare exactly as an unused allowance always does. Headroom is a budget people spend, not a margin they respect. |
| A one-sided ratchet | Decays into the flat constant. |
| The weights in `config/` | `config/` holds knobs; this is a recorded measurement, and it would make every byte change a schema change. |
| A generated baseline file | A file the build rewrites is a log. |
| The numbers inline in `bundle-gate.mjs` | Mixes a logic diff and a measurement diff in one review, and pollutes `git log -p` on the numbers. |
| Gzip over the concatenated module set | Order-sensitive, so a bundler reorder moves the number for a reason nobody caused, and it under-reports the wire cost. |

Authority: Carmack, 2026-08-25.

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
the recorded weight in `frontend/bundle-baseline.json` is what a later row is
compared against, and Carmack made that gate a condition of accepting the
dependency at all. Authority: Jony and Carmack, 2026-08-25, owner accepted.

The first-load weights sit in `frontend/bundle-baseline.json` rather than in
`config/`, and that is not the config rule being waived. `config/` holds knobs a
person tunes to change behaviour; this is a recorded measurement, and filing a
measurement under preferences invites editing it as one. Routing it through
`config/idhazh.json` would also drag in the `AppConfig` model, a schema
regeneration, a `changelog` stamp and the `frontend/src/lib/server/config.ts`
mirror - which would make every byte change a schema change. Authority: Carmack,
2026-08-25.

The same script gates the prerendered HTML and the first-load JavaScript, which
was once rejected on the grounds that one gate over both would make two
workstreams fail each other's builds. That risk was real and it materialised:
the `/archive/` and `/console/` HTML ceilings, added to the script in #126,
fired on ordinary publishes because those pages grow with the published corpus.
The fix was not to split the script but to scope the HTML ceiling to the routes
whose weight does not grow with data - `/404` and `/evals/` - and to report a
data-driven route without failing it. So the two checks share a script and stay
independent: the JavaScript ratchet reads `frontend/bundle-baseline.json`, the
HTML ceilings read `config/idhazh.json`, and neither fails the other's build.
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
| A bar chart for a window holding one day | A chart of a single value is a rectangle. The number is the panel. | Jony |
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
