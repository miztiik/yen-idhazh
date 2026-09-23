# How a day page is arranged

**Last Updated**: 2026-09-23

A day page from top to bottom: the header that states each publication fact
once, the leading block the day opens on, the two-column arrangement that gives
the leads a column of their own on a wide screen, and the footer that is its
links and nothing else. Every ruling here is about the page rather than the
story on it - what one item shows is
[what-a-story-shows-and-where-each-fact-sits.md](what-a-story-shows-and-where-each-fact-sits.md).

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
([../../reference/site-weight.md](../../reference/site-weight.md#what-the-reading-page-does-with-a-wide-screen-2026-09-02)).

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

## The day header states each publication fact once

`DayNotice` starts with the edition date and the published count supplied by
the caller. It never counts the seed or the currently visible items. The header
is unboxed and wraps the count beside or below the date as space permits.

An incomplete day carries the recorded failure count, with no invented cause.
The old sentence attributed every failure to inadequate source text, although
the payload carries no such shared reason. Unknown counts remain absent.

The last line uses `runs.at(-1)` for `Updated HH:MM UTC (update N).` Its time is
the digest's recorded generation time, not the site's deployment time. The
sum of `items_added` where `n > 1` states how many were added since the first
update. Missing run history prints neither a time nor an assumed first run.
These facts belong to the day header, never the shared site footer.

`introduced_by_run` is on every item and is drawn nowhere. It briefly was: from
2026-08-31 a flat list carried one hairline divider - `Added later today` -
before the first item a later run added. **The divider was deleted on
2026-09-01.** It named a run boundary, and a run is our schedule rather than the
reader's - somebody reading past it does not know what run 3 is and cannot do
anything differently for knowing. The fact a reader wanted from it is when the
story happened, and plan 25 row #5 puts that beside every story's own heading,
in digits they already read. Authority: Editor, plan row #16.

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
[the day notice](#the-day-header-states-each-publication-fact-once)
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
([../../concepts/config.md](../../concepts/config.md#build-time-config-versus-shipped-config)). Page options went with the
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

## Design rationale

Grouping the all-topics page by topic is hierarchy, not truncation, and the distinction is the whole argument. [layout.md](layout.md) forbids removing or demoting a published item, and [../../concepts/digest.md](../../concepts/digest.md) says the reader's budget is protected by ordering and hierarchy - so the fix for a 586-item day had to come from typography rather than from a cap. Every item stays published, in its published order, one prerendered click away. The rejected alternative, truncating the day, would have made the page look like a digest by making it stop being one. Authority: Jony, with Reader as the check.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A summary of the day's summaries | The only text on the page with nowhere to click, and three removes from the source. | Reader |
| A cross-topic "top stories" strip on the day page | The payload carries no cross-vertical rank, so the page would have to invent one at read time. The page renders; it does not think. | Jony |
| Truncating a long day to protect the two-minute budget | Ordering and hierarchy protect the budget. Dropping items a run published is not a typography fix. | Jony |
| Grouping a day that ran to a single topic | One heading over the whole page states what the page already says, and it puts items behind a link that leads back to the same list. | Jony |
| One paragraph per later run in the day notice | Three runs printed three near-identical sentences saying one fact. One total says it once. | Jony |
| A divider naming the run that added an item | A run is our schedule rather than the reader's, and nobody reading past it can do anything differently for knowing. | Editor |
| Computing "today" in the browser or at build time | The browser would vary by reader timezone, and the build clock would let a stale deploy claim a date the payload does not carry. | owner |
| A manifest a page fetches so the footer can print the commit | The commit is not worth a file, a schema, a request and a cleanup story. | owner, 2026-09-08 |

## See also

- [frontend.md](frontend.md) - what a build writes and what a browser fetches, and where the rest of the reader's surface is written up.
- [what-a-story-shows-and-where-each-fact-sits.md](what-a-story-shows-and-where-each-fact-sits.md) - the item this page lays out.
- [how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md) - the filter panel that spans both columns.
- [layout.md](layout.md) - the frame, the routes and the rule against re-ordering a published day.
- [../../concepts/digest.md](../../concepts/digest.md) - what the leading block is for a reader.
- [../sources/discovery.md](../sources/discovery.md#a-second-order-over-the-same-day-the-leading-stories) - how a lead is chosen.
- [../../concepts/config/appearance.md](../../concepts/config/appearance.md) - the `ui.*` and `frame.*` knobs this page reads.
