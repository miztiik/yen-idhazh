# How a reader finds a story

**Last Updated**: 2026-09-23

Three controls answer one question, and they are deliberately different sizes.
The filter narrows what is already on the page. The archive's day list and story
list browse what has been published. On-device search reads a month of vectors
and ranks them. This page holds all three, what each one may promise, and the
sentences that say how far each actually reached. The encoder those vectors come
from is
[the-on-device-encoder-and-its-vectors.md](the-on-device-encoder-and-its-vectors.md).

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

Eight decisions. Susan's, except the two the row order added on 2026-09-13: the Editor set the margin and Jony ruled the cap soft.

- **The pills are visible at rest.** Never behind the field, never collapsed as a set. The only thing a disclosure holds is an auto-created topic past `digest.topic_pills_max`, and its summary says how many.
- **The row leads with the desk holding most of the day**, and a desk only passes one it is ahead of by `digest.pill_move_min` stories. The order is arithmetic over the payload, computed where the payload is drawn and never a measurement of the row: one order is published and a row that measured itself on the reader's device could disagree with it. Ordering by raw count was refused for years because a topic would move between two days for a reason a reader cannot see, and the margin is what answers that - the desk in front is ahead by at least the margin, and the counts on the pills say so. Below the margin the payload's own alphabetical order stands, so a smaller count can sit ahead of a bigger one: measured 2026-09-13 over the 23 committed days carrying all five desks, that is one adjacent pair in 92 at the committed margin of 2, reading 1 ahead of 2. **What the margin does not buy is steadiness across days** - the same measurement counted 31 desk-days moving at a margin of 2 against 28 at 1, so a bigger margin moves the row more. It bounds the reason a desk moves, never how often.
- **A curated desk is never folded away; an auto-created one may be.** A desk a person put in `config/taxonomy.json` is a promise the site makes; a desk a model proposed is a suggestion, and hiding a suggestion costs a reader nothing. That makes `digest.topic_pills_max` a **soft** cap: nothing bounds how tall the row gets, and the row's height is the length of the vocabulary. `config/taxonomy.json` declares five verticals and the cap is five, so today nothing folds on any real day - `frontend/src/lib/payload/desks.ts` is the empty mirror an auto-created desk arrives in, and `frontend/tests/topics.spec.ts` fails on any drift between it and the vocabulary.
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

`/archive/` used to list five dates and no articles, and it inlined every committed day whole so on-device search could read the vectors without a request. Measured 2026-08-27 on one checkout, six committed days and 2,237 items: **1,766,682 gzipped bytes**, growing **489,843 bytes** for the one extra day that carried 621 stories. The page a reader opened to find one story carried all of them. It is **2,912 bytes** now, and one more day of 621 stories costs it **24 bytes** ([../../reference/site-weight.md](../../reference/site-weight.md#the-archive-stops-carrying-the-corpus)).

What it renders now, top to bottom:

- The counts and the retention promise: "6 days, 2237 stories. Nothing here is deleted."
- **The filter bar** - every topic the archive holds with its whole-archive count, and the search field beside them. Under it, the two sentences about the on-device model: what it would cost, and how far back a search would reach.
- **The day list** - the newest `ui.archive_recent_days` days as rows carrying the long date, the story count and a mark when some stories did not finish, then one disclosure a month and one a year for every year before the newest published one. A month row reads `20 of 31 days, 4086 stories` and holds its own days as a wrapped grid of numbers. It was a single wrapped row of every date until 2026-09-01, which is 700 links after two years.
- **The stories**, newest day first, each a link to its own anchor on the day that published it, with the date and the topic beneath.
- **`Show 25 more`** - the same explicit control the day list and the console's failure list already use, sized by `ui.archive_page_size`.

**The stories are fetched, not inlined**, from `index/<YYYY-MM>.json` staged into `static/`. [layout.md](layout.md) owns why, and the short version is that inlining them would leave the page growing per story, which is the defect the index exists to end. Paging back into an older month fetches that month; a month already in hand is not fetched twice.

**A window bounds which months the browse list fetches.** A segmented control - the same pattern as the console's, over the same 1, 7, 14, 30, 90-day presets - sits above the stories under `data-archive-window` and opens on a 30-day window. `monthsInWindow` in [../../../frontend/src/lib/assist/month.ts](../../../frontend/src/lib/assist/month.ts) turns the window into a newest-first prefix of the months, and the loop reads only those, so a story older than the window is out of the browse list until the window widens or a search reaches past it (Guardrail #12). A narrower window only hides months already in hand; a wider one fetches the months it now reaches. A topic with no story inside the window says so and offers a `Look back` button to the widest preset, rather than walking back through the whole archive to fill a page - the window is what ends that sparse-topic walk. The window governs the browse list only: search reads its own day floor, not this window.

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
[../../reference/site-weight.md](../../reference/site-weight.md#the-archive-day-list-stops-growing-a-row-a-day).

#### Why the document still grows with days

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
web text reaches a page unsanitised (Guardrail #11). Ten results spanning ten days
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

## Design rationale

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

| Option | Why rejected | Authority |
| --- | --- | --- |
| A top-level search bar | On a page whose whole content is on screen it is a control with nothing to do, and it promises an archive it cannot reach. Narrowed to an in-place filter. | Jony, Reader |
| A "newest first" or "best first" sort control | The published order is global and identical for every reader. A sort control makes a shared link show the recipient a different page. | Jony |
| Reaching a full month back from the newest published day on every date | A constant window, bought with two whole shards on 29 days out of 30 and a second 518 KB browse index charged to every visitor who only browses. | Carmack |
| Naming the months a search read, rather than the days | On 1 September "September 2026" reads like thirty days and holds one. The month name is what hid the collapse it was meant to disclose. | Jony |
| A search field that expands to reveal filters | It hides the filter set behind a control, which is the failure the one panel replaced. | Susan |
| Keeping the pills and the field as two separate blocks | Two bands of vertical space are the cost the one panel exists to remove. | owner |

## See also

- [frontend.md](frontend.md) - what a build writes and what a browser fetches, and where the rest of the reader's surface is written up.
- [the-on-device-encoder-and-its-vectors.md](the-on-device-encoder-and-its-vectors.md) - the encoder a search downloads, and what makes two vectors comparable.
- [what-a-story-shows-and-where-each-fact-sits.md](what-a-story-shows-and-where-each-fact-sits.md) - the pill row's own rulings, and the item a result renders as.
- [layout.md](layout.md) - the month index, the dated addresses and the one-order rule.
- [../../reference/site-weight.md](../../reference/site-weight.md) - what the archive weighs, and what a month shard costs.
- [../../concepts/search-quality.md](../../concepts/search-quality.md) - what the ranking is measured against.
