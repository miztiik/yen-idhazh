# How a story chart is drawn, and what refuses one

**Last Updated**: 2026-10-25

A story that carries a chart carries a pointer at its marks, and the reader's
browser is what turns those marks into a picture. This page holds that path: who
draws it, which token every mark takes, what is refused on arrival, when the
fetch happens, and where the trust boundary sits now that a stranger's numbers
become markup in our own origin. The routes this drawing arrives on are
[frontend.md](frontend.md); what a visual is allowed to say at all is
[what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md).

## The browser draws the chart, so the chart reads the page it is printed on

**The reader's browser draws the chart and the pipeline never draws one** (owner ruling, 2026-09-13, [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md)). A story arrives carrying a pointer at its marks; [ItemVisual.svelte](../../../frontend/src/lib/components/ItemVisual.svelte) fetches that file when the story comes near, [drawing.ts](../../../frontend/src/lib/payload/drawing.ts) refuses anything that does not fit the type it names, and [visual/bar.ts](../../../frontend/src/lib/visual/bar.ts) places bar, dot, slope and line marks. Line marks use the shared D3 date-series builder. Svelte writes them, so the marks are ordinary elements in the component's own subtree and take the page's tokens through plain scoped CSS.

**Two carriers preceded it and both are worth keeping on the page, because the second one is why the tokens below exist.** Until 2026-09-05 every published chart shipped inside an `img`. An SVG in an `img` is a separate document: it reads none of the page's custom properties, so the only colours it could ever have are the ones the renderer baked in - black axis type, `#888` ticks, `#ddd` grid lines and a `#4c6ef5` bar, fine on white and on the dark theme black type on a near-black card. **It was the loudest reader-facing defect on the site and no gate could see it**, because every check the drawing had was about whether the file was served. From 2026-09-05 the build read the committed SVG off disk for the stories a prerendered document carried and inlined it, so the page could repaint it; that carrier went on 2026-09-13 with the renderer that filled it.

**What the reader gained, as contrast on the dark card.** Measured 2026-09-05 against `--color-surface`: the axis type was black on `#141922`, which is **1.19:1** where readable text needs 4.5:1, and it is now 7.86:1. The bars went from a fixed `#4c6ef5` to 5.93:1 on dark and 6.35:1 on light. The light theme was always fine, which is why this survived every review: the defect was invisible to anyone reading in the theme the drawing was drawn for. Nothing bakes a colour any more - the marks carry no colour at all - so these are now the numbers that say why each token was chosen rather than a repair.

| What is drawn | Token | Why that one |
| --- | --- | --- |
| Bars, dots, slope points/lines and line-series paths/points | `--chart-1` through `--chart-8` | The categorical chart ramp. It holds no green, amber or red, so a mark cannot read as a status |
| Names, time labels and units | `--color-text-secondary` | Type on the card, read the way the reader note above it is read. The chart ramp is for marks that carry no word |
| Figures and column labels | `--color-text` | A reader reads these as values or time labels, so they take the page's own ink |
| Bar and dot baselines (`line.axis`) | `--chart-axis` | The token every console chart already draws an axis with, so there is one answer here rather than two |

## What arrives is checked, and it is checked in the reader's browser

`refusedVisualData` in [../../../frontend/src/lib/payload/drawing.ts](../../../frontend/src/lib/payload/drawing.ts) is the guard: it refuses a path that is not a published visual, a document whose `renderer_version` this page does not hold, a type it cannot draw, and a shape that does not fit that type - four names against three figures, a channel naming a mark that is not carried, a bar with no figure. A refusal costs the story its picture and nothing else. **The build checks none of it**, because the build draws nothing: every chart on the site is checked on the device of the reader who opens that day. That is the same trade `check-publication` records on [frontend.md](frontend.md) - the build stopped being the place a bad day is found, and it is written down rather than assumed.

**Before the position-and-length charts landed, every published visual was a bar.** The
compiler now draws `bar`, `dot`, `slope` and `line` from source-backed channels. The historical
forty-three drawings on 2026-08-31 - the heaviest committed day, 43 across 601 stories - were
all bars, which is why this chart family was needed.

## Nothing inlines, and that is the byte trade this made

A day has published 621 stories, the committed drawings averaged 12.7 KB, and a seed held 0.87 of them on average - 11.8 KB of markup a day. All of it is gone from the document, and what replaced it is a fetch per story that carries a chart: 1,711 and 1,332 bytes for the two on the canary day, against a mean drawing of 12,722. The reading route's first-load JavaScript grew instead, by **2,033 bytes at gzip -5** - 60,544 to 62,577, measured on this box against a control build of `origin/main`, 2026-09-13 - which is what the band scale, the geometry module and the component rewrite cost together.

**The fetch waits until the story is nearly on screen**, because the `img` that preceded all of this carried `loading="lazy"` and a plain fetch on mount throws that away. The case where that hurts is not the ordinary one. A reading page draws twelve stories, so each press for more brings **0.66 charts on average** - measured 2026-09-05 over the 15 committed days, 351 visuals across 6,425 stories, which is 5.5 percent. The case that hurts is a deep link: `/<date>/#<story>` pages the stream down to that story, so the whole prefix mounts at once, and on 2026-08-31 - the day carrying the most visuals, 43 across 601 stories - that is up to 43 requests opened together, against the day payload the same page is still waiting on. An `IntersectionObserver` with a `100%` root margin holds it to the stories within one screen of the reader. The margin is a percentage rather than a pixel count, so a phone asks one phone-screen early and a desktop one desktop-screen, and there is no number to maintain.

**One watcher serves every story that is waiting.** A watcher per story is a cost that rises with the day rather than with the code, which is the shape Guardrail #12 refuses: nobody writes a line and the page gets more expensive, because the run published more stories. [reveal.ts](../../../frontend/src/lib/reveal.ts) holds one `IntersectionObserver` and a map from element to the work that element waits for, so a story registers on mount and is dropped from both when it goes. Measured 2026-09-06 on a developer machine against the built site, `/2026-08-31/` with all 601 stories revealed and all 43 drawings fetched: **44 observers before, 2 after**. One of each pair is SvelteKit's own link-preload watcher, so ours went from 43 to 1 - one per story, to one for the page - and every drawing still arrived. The count is deterministic rather than sampled; the new case returned 2 on each of three runs. The module imports nothing, for the same reason [drawing.ts](../../../frontend/src/lib/payload/drawing.ts) does: a spec can then drive it in a plain `node` process, which is the only way this rule can be checked at all.

**A story that leaves the page takes its request with it.** Unmount drops the watch and aborts the fetch, so a reader who pages away is not still paying for a chart nothing will show, and a response that lands after the story is gone is discarded rather than written into a component that no longer exists. An aborted fetch is silent: it is the reader's own move, not a fault, and logging it would fill the console on every page change.

Route navigation pauses new chart requests and aborts pending ones before the
old story unmounts. The old page cannot start a late chart fetch ahead of the
destination's first payload. A story that remains after navigation can resume
an interrupted request; a completed request is not repeated.

**Marks that do not arrive leave the story shorter, and nothing else.** No broken-image glyph, no grey box, no skeleton - which is the shape two stories in three already have, and the reason the placeholder was refused in the first place: a grey rectangle makes "this story needed no picture" look identical to "the picture failed". The element that waits for the fetch is a zero-height `div` with no border and no background, so a story that never gets its chart is exactly as tall as a story that never had one.

## Untrusted marks become text and geometry, never supplied markup

The page accepts structured chart data, not SVG from disk or fetched markup.
[drawing.ts](../../../frontend/src/lib/payload/drawing.ts) checks the published
path and current payload before the component draws it. Svelte writes titles,
captions, labels and source figures as text nodes. Bar lengths, dot positions and
slope lines come from validated values. None of that text becomes HTML, a path
or a fetch URL.
The retired SVG reader and its markup checks have no compatibility path.

The fixed canary has eight stories and seeds three through its fixture config.
Its second chart sorts last and loads after the initial shell. Browser tests
reveal the named fixture's drawings before checking their marks, labels and
reload stability. They never open a longer committed day for this check.

`frontend/tests/visual-legibility.spec.ts` owns that browser check. It compares
the marks with the fixture's drawing data, verifies the complete accessible
description, and checks the text and width rules in the
[design system](../../concepts/design-system.md#a-charts-column-is-set-by-what-the-chart-was-drawn-at).
It visits the archive and returns, then reloads the day, to check that the same
data keeps the same geometry. No reader styling change was needed to meet the
floor; this gate protects the existing measured-width drawing.

`refusedVisualData` checks the current renderer, supported type, mark references,
paired channels for each type, canonical dates on line time marks, framing fields
and exactly one emphasized measured mark.
The [compiler contract](where-a-drawing-becomes-pixels.md#design-rationale)
owns how plan references select that mark. Invalid or older incompatible data
costs the story its chart, not its text. There is no placeholder and no guessed
priority. The pipeline owns mark-count limits; the browser does not invent a
second editorial threshold.

The page accepts one current `renderer_version`, stated on the chart document.
A cached page refuses an unknown stamp rather than drawing values under rules
it does not know. The dated owner exception for older charts lives in the
[contract rationale](where-a-drawing-becomes-pixels.md#design-rationale).

**The mis-shaped cases are built in the spec rather than committed, and that is a constraint.** Every file under `tests/fixtures/contracts/` is round-tripped through its model by the backend suite, and a mis-shaped document will not load - so a committed one fails that gate before it reaches this one. [item-visual.spec.ts](../../../frontend/tests/item-visual.spec.ts) accepts the fitting bar control, then changes one named condition per refusal case. Dot, slope and line fixtures come from bounded element-table sources and are checked against native compilation; the geometry tests use those same files at narrow and wide widths.

## Design rationale

Bars stay horizontal at narrow widths so category names remain readable. Dots
use one shared value scale when position compares items better than length.
Slopes join paired values across two labelled time columns and omit an axis;
their units are still visible. Lines order source-backed measurements by
canonical date, keep source wording for labels, and group only when each
reading carries its own series label. They share date ticks, value axes and
measured width with the Data explorer's date-series builder. One shared drawing
component handles all four forms. A line's unit appears once at the value axis;
numeric tick labels do not repeat it. Their bounded settings live under `chart.story_geometry`, separate from the
console chart's fixed coordinate dimensions, and reach the browser only through
the existing typed build-time UI configuration. The dot baseline ends at the
same measured position as its value scale, and mark outlines take their width
from that bounded geometry.

**The oracle is an equality against a token, never against a hex.** The same spec plants a probe element, sets its `background-color` to the property the stylesheet routes a mark to, and compares what the document computed with what the mark was painted. The two themes give that property two different values, so one baked colour fails one case whichever colour it is - and a test written against a literal would need editing every time the palette moves, which is how a colour test stops being one.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A visual placeholder when there is no visual | Makes "we correctly decided this needed no picture" look identical to a failed image. | Jony |
| Drawing the chart in the pipeline and shipping it inside an `img` | An SVG in an `img` is a separate document and reads none of the page's tokens, so the only colours it can have are baked ones - black axis type at 1.19:1 on the dark card, which no gate could see. | owner, 2026-09-13 |
| A degrade path that draws something approximate from mis-shaped data | It is how a wrong chart reaches a reader. A story with no visual is simply shorter, which is already the shape 94.7 percent of stories have. | Jony |

## See also

- [frontend.md](frontend.md) - what a build writes and what a browser fetches, and where the rest of the reader's surface is written up.
- [visuals.md](visuals.md) - whether a story earns a picture at all, and what the pipeline publishes for it.
- [../../concepts/design-system.md](../../concepts/design-system.md) - the tokens every mark above takes, and the colour rule behind them.
- [what-a-story-shows-and-where-each-fact-sits.md](what-a-story-shows-and-where-each-fact-sits.md) - the rest of the item the chart sits inside.
- [console-charts.md](console-charts.md) - the operator's charts, which are a different surface with a different lifetime.
