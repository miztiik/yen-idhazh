# What a story shows, and where each fact sits

**Last Updated**: 2026-09-23

One story on the page: what it prints above the title, what it prints under the
summary, which of those facts is a claim about the article and which is a claim
about our summary, and what changes once a reader has read it. Every ruling here
is about the item, so it holds on the day page, on a topic route and in a search
result alike. The page the item sits on is
[how-a-day-page-is-arranged.md](how-a-day-page-is-arranged.md); the chart inside
it is
[how-a-story-chart-is-drawn-and-what-refuses-one.md](how-a-story-chart-is-drawn-and-what-refuses-one.md).

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
| when - the story's own published time on a dated page, and the day it was found on in a search result | |

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

Since 2026-09-01 they share a panel with the field that narrows the list - one control, described under [The filter bar](how-a-reader-finds-a-story.md#the-filter-bar-topics-and-a-field-in-one-panel).

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

**The desk name beside them is a chip of the same family.** It uses
`--tint-accent` and keeps the configured display name, without forced capitals
or added letter spacing. Its first position identifies the desk. One
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

## Design rationale

Spending the colour per item rather than at the day level is the resolution of a genuine conflict between an owner instruction and a persona's ruling, and it took two passes to land. The owner asked for a colourful confidence signal; Reader argued that per-item confidence badges are the project talking to itself. The first answer put the aggregate at the top and the proportionate signal on the item. The aggregate then had four months of data behind it and never moved, so it was deleted: colour belongs where it varies, and where a reader can click through and check. Authority: owner (section 0), designed by Jony, constrained by Reader.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A coloured stripe or tinted card per band | At a realistic band distribution it paints most of the page as broken, and the reader believes it. | Jony |
| A `high` badge on every item | Ink spent on the absence of a problem, and colour as the only signal. | Jony |
| A day-level bar of the confidence bands | It charted a constant, shared its tokens with the item mark so it trained the reader to ignore the mark that varies, and printed a sentence the item level had already retracted. | Jony, Reader |
| A day-level sentence counting how many summaries may not match | The bar in prose. A number spread over hundreds of items a reader can neither locate nor act on. | Jony, Reader |
| Publisher favicons | A runtime third-party request that announces every reader to every publisher, failing to a broken-image glyph mid-page. | Jony |
| Topic tabs including empty ones | An empty tab reads as broken software or an absent desk. Only present verticals are rendered. | Reader |
| A colour per topic | A category-to-colour map that must be re-picked every time the taxonomy changes, carrying nothing the count does not. | Jony |
| An estimated reading time per topic | An unmeasured number printed as a fact, and it changes nothing a reader does. | Jony, Guardrail #10 |
| `key_points` shown alongside the summary | The same content twice, at the cost of the hierarchy and half the items per screen. Settled for good on 2026-09-24: the field left the payload, so there is nothing to show. | Jony |
| A flat list of read ids with no date | An id that came round again greyed out an article the reader had never opened, and nothing in the list could decide which marks to drop. | owner |
| Migrating undated read marks rather than discarding them | There is no honest way to say which day they belonged to, and a wrong mark costs a reader an article. | owner |
| A read mark that hides or demotes an item by default | Two people at the same URL would see different pages, and a shared link would stop showing the recipient what the sender saw. | Reader |

## See also

- [frontend.md](frontend.md) - what a build writes and what a browser fetches, and where the rest of the reader's surface is written up.
- [how-a-day-page-is-arranged.md](how-a-day-page-is-arranged.md) - the page these items are laid out on.
- [how-a-story-chart-is-drawn-and-what-refuses-one.md](how-a-story-chart-is-drawn-and-what-refuses-one.md) - the picture inside an item that earned one.
- [how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md) - the filter panel the pill row shares.
- [../../concepts/digest.md](../../concepts/digest.md) - what an item carries and why.
- [../../concepts/design-system.md](../../concepts/design-system.md) - the tokens, the tints and the swatch bound.
- [../../concepts/classification.md](../../concepts/classification.md) - the lens, event and entity vocabulary this draws from.
- [layout.md](layout.md) - the rule that read state may change how an item looks and never where it sits.
