# Where a drawing becomes pixels

**Last Updated**: 2026-09-23

The reader's browser draws the chart and the pipeline never draws one. This page
holds that ruling, what it cost and what it bought, where the marks are
published, the contract they travel in, the one place a renderer version is
stated, and the compiler that turns one validated plan into one set of marks.
Who decides a picture at all is [visuals.md](visuals.md); what the browser then
does with the file is
[how-a-story-chart-is-drawn-and-what-refuses-one.md](how-a-story-chart-is-drawn-and-what-refuses-one.md).

## Where a drawing becomes pixels, ruled

**The reader's browser draws the chart. The pipeline never draws one.** Owner ruling,
2026-09-13, under `CLAUDE.md` section 0.

**The chain, end to end.** Code reads the article and finds every quantity it can, with the
offsets that prove where each one came from. The model labels those quantities, names the
chart type and selects which elements it is drawn from. Code compiles that into a spec -
the data and its shape, and nothing else. **The day payload carries that spec**, and the
reader's browser draws the SVG from it with d3. Nothing renders at build time and no
drawing is committed.

**This closes a question three documents answered three different ways**, which is why a
worker scoping plan 12 row #1 stopped rather than guess. In
[`../../../TODO/20260902-visual-planner-pseudo-plan.md`](../../../TODO/20260902-visual-planner-pseudo-plan.md),
row 22 ruled build-time SVG with hydration on point-or-focus, and row 37 ruled that the
compiled spec travels in the day payload and the browser draws it. The proposal behind both
still records the question as open. The code follows row 22. **Row 37 was right, and it is
now the whole rule rather than the tail of it**: there is one drawing path and it is the
browser's.

**What the ruling costs, named rather than implied.** A reader with JavaScript off gets no
chart, where today they get one, because today the drawing is markup inside the document
itself. That is the reason row 22 chose build-time SVG and it is a real loss. **They get no
sentence either.** Measured on the canary
build that day: the prerendered document carries zero `<figure>` elements, because the
figure exists only once the marks have arrived - so `alt` reaches a payload blob and never
a reader who runs no script. What a reader who does run one hears is written in the browser
off the same marks the bars are drawn from, and it states every one of them
([../../concepts/design-system.md](../../concepts/design-system.md#every-fact-a-drawing-shows-is-reachable-without-a-pointer)).

**And every day published before 2026-09-13 loses its chart, for every reader rather than
only for one with JavaScript off.** The 495 committed drawings are deleted and no marks file
was ever written for one, so those stories publish shorter from here on. Back-filling would
mean re-fetching 495 source pages that have since moved, and a chart compiled from today's
page under an old day's date is a record of nothing.

And the drawing stops being an archival artefact: a committed SVG is a fixed record of what a
reader saw on a given day, where a spec plus drawing code can be redrawn differently by a
later change with nothing in the payload to show it moved. `renderer_version` travelling on
the payload is what makes that visible, and it is why it is minted before anything draws.

**What it buys.** The 495 committed drawings - 6,297,398 bytes, mean 12.7 KB each,
re-measured on this branch 2026-09-13 - stop being published bytes, and their growing tail
stops counting against the 1 GB site cap (Guardrail #2). A visual's marks weigh about a tenth
of what its drawing did: the two on the canary day are 1,711 and 1,332 bytes against a mean
drawing of 12,722. The chart takes the width the reader's screen actually has, which a fixed
build-time canvas cannot do and which is the whole of plan 12's complaint. And the build-time
renderer's own non-determinism goes with it - the clip-path counter recorded in
[what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md) - so an
item compiled twice from unchanged inputs now writes identical bytes, and git does not
conflict on two adds of identical content.

**The two-runs-one-path race itself does not go, and the row that deleted the renderer did
not delete the control** (Fowler, 2026-09-13). The marks file is filed under the item's id
exactly as the drawing was, and it is compiled from a plan and an element table derived from
text re-fetched off the open web - so a source page that moved between two runs' fetches still
puts two different blobs on one path. That is rarer than the clip-path counter was and exactly
as expensive: run `32869125768` cost eight workers, a day of summaries and the day's digest.
A rare catastrophic failure with the control deleted is worse than a frequent one, because
nobody will have it in mind when it fires. `drop_raced_assets.py` keeps the job and changed
only what it lists
([one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md)).

**What the reading page now carries, measured rather than estimated** (Guardrail #8). Two d3
modules reach a reader and no others: `d3-scale` gives the bar its band scale - the
per-category slot, step, padding and rounding arithmetic that decides where each mark sits -
and `d3-array` supplies the `range` and `InternMap` that band scale is built on. Both were
already installed for the operator console's chart frame, so this added no install time, and
both are now exact-pinned: a caret range lets a patch bump move pixels with no diff to review.
`d3-selection`, `d3-axis` and `d3-shape` are **not installed**, which is the control rather
than a preference - a package that is not in the lockfile cannot be imported onto a reading
page. Nothing here joins, enters or exits, so `d3-selection` would buy a join engine and use
only its append path; `d3-axis` writes a 10px axis font, which is below `--text-xs` at every
root size this site uses, so it would be imported in order to be undone; and `d3-shape` has no
rect generator, so it waits for the row that draws a path (Carmack, 2026-09-13).

Measured on the development box (Windows 11, 8 vCPU, node 24.12.0), 2026-09-13, control build
at `origin/main` against this branch, same machine and same toolchain: the reading route's
first load goes from **60,544 to 62,577 bytes at gzip -5**, over 24 modules either way. That
is **2,033 bytes, 3.4 percent**, and it covers the scale arithmetic, the geometry module and
the component rewrite together, net of the inlining code they replaced. Raw, it is 144,500 to
149,955. **There is no `page_weight` entry to re-baseline**: the owner ruled on 2026-09-10
that a route may be named in `page_weight.ceilings_bytes` only if its weight does not move
when a run publishes, and a reading route's document carries the day. The gate measures and
prints it rather than guarding it.

**What the reader can read, measured rather than promised, and it is not the floor yet.** The
drawing is placed at the width the card actually gave it, in CSS pixels, so one drawn unit is
one pixel on screen and there is no scale factor between what a token says and what a reader
sees. Measured on the canary day, both cases on one developer machine back to back with
`BUILD_VERSION` pinned, 2026-09-14, at 360, 390 and 1440 CSS px in both themes. **After, the
scale is 1.000 at all three widths and every drawn string resolves at 12.0 CSS px**, which is
`--text-xs` at its own size. Before, the same drawing laid itself out 720 units wide whatever
the card gave it, so the browser squeezed or stretched it: **0.350 at 360 px, 0.392 at 390 px
and 1.233 at 1440 px**. A string set at 12 therefore reached the reader at **4.2, 4.7 and
14.8 CSS px** - 65 percent under the token on a small phone, and 23 percent over it on a
desktop. The drawn height moved with the width the same way: the taller of the canary's two
charts stood 59.5 px at 360 and 209.7 px at 1440, and now stands **202 px at all three**, so
the figure is its final height before a mark lands in it. Plan 12 row #2 removed that scale;
row #4 is the row that holds the result to a floor a person can read, and it could not start
until something measurable was drawing. The width comes from
`frontend/src/lib/visual/width.ts`, which measures the figure's content box and is one watcher
for every chart on the page rather than one each (Guardrail #12).

**The name sits above its bar rather than beside it, and that is what makes one layout work at
every width** (row #2, 2026-09-14). A name column has to hold the longest name the compiler
allows - `MARK_NAME_MAX` is 40 of the article's own characters, about 250 CSS pixels at
`--text-xs` - and a 360 px phone has roughly 300 pixels of card to spend. Side by side, a
column that fits the names leaves nothing for the bars and a column that fits the bars cuts
the names in half; the old drawing hid that by scaling the type down until the names fitted,
which is the defect above. Above the bar, the name has the whole width at every size, and the
bar has all of it but the sixteenth reserved for the figure that sits beside it - so the
comparison the chart exists to make gets every pixel left once the number it compares has
somewhere to stand. What a reader gives up is the tidy left-hand column of names a desktop had
room for, and one text line of height per bar.

**What this ruling does NOT change, because each has been read as following from it.** The
pages stay prerendered; prerendering a route and prerendering a chart are different acts and
only the second one ends. The model still never writes a number - it labels, names and
selects, and code cuts every character a reader sees. The validator, the downgrade ladder
and the sufficiency bar all stay; what moves is only where the spec becomes pixels. The
console keeps its own chart engine and is not migrated.

## Where the data lives, and why it is not in the day payload

**Published location, ruled 2026-09-13.** One visual is one file, in the day's own directory, beside
the payload that points at it:

```
frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.json
```

That is the path the drawing occupied with a `.svg` extension until 2026-09-13, so the shape did not
move -
only what is inside it. **The shard is the day directory**, which is what every other published
store uses, and the day is also what a reader fetches.

**The chart data is kept out of `digest.json`, and the prune is the reason rather than the size.**
The day payload is never deleted - it is the record that a day happened. Chart data inside it would
therefore be undeletable, and `retention.image_months` would have nothing to act on. A separate file
per visual keeps the two clocks apart: the text is permanent, the drawing ages out, and the prune
granularity stays exactly what it is today rather than coarsening to a whole day.

**The size argument is real but it is the second reason.** Measured 2026-09-13 over all 24 committed
days: `digest.json` totals 23.30 MB, mean 994.3 KB a day, largest 1.88 MB. Only 495 of 9,353 items
carry a drawing - **5.3 percent** - so folding chart data into the payload would make every reader
download data for charts that 94.7 percent of stories do not have, and would push the largest day
further up against the 1 GB site cap.

## The contract, and the one field the day payload gains

`VisualData` in `backend/idhazh/contracts/visual_data.py` is the shape of that file.
Three parts.

| Part | What it is |
| --- | --- |
| `item_id`, `type` | Which story, and which of the declarable forms. A new type costs an enum member, never a new document format. |
| `marks` | **A flat pool, not a list of rows.** Each mark carries what it says (`text`), what it measures (`value` with its `unit`), and where that came from - `element_id` for a slice of the article, or `derived` for a chain through the four-function allow-list. Exactly one of the two, checked. |
| `encoding` | Which marks fill which channel, by id, mirroring `PlanEncodings` role for role. Every role is a key and an unused one is empty. |

**The pool is flat because a row is a geometry decision.** A bar is a name and a length, a scatter
point is two measured axes, a histogram bar is a bin - shape them into rows here and this contract
grows a case per type and stops being data. A flat pool with an encoding over it can also express
the thing a row list cannot: four names against three figures, which is exactly the mis-shaped
payload the reader's page has to refuse rather than draw short.

The day payload gains **one** field, `DigestVisual.data_path`, and gains nothing else. It stays what
the flow diagram's node table says it is - a pointer - and the chart data never enters it.

## `renderer_version` has one home, and this is why it has one

`VisualData.renderer_version` is the one place a drawing contract's version is stated. Not on a
mark, not on the decision, not in the day payload.

**Two homes is a failure this subsystem has already had.** `spec_format` carried the same idea in a
second place, the two disagreed on 2026-09-05T18:00, and what disagreeing looks like from a reader's
seat is a page drawing yesterday's numbers under today's rules. A version in one place can be wrong.
A version in two places can be *inconsistent*, and nothing downstream can tell which one to believe.

The reader's page holds the set of renderers it knows and refuses anything else. That is what lets
the shape move at all: a later build publishes a later stamp, an older cached page does not draw it,
and nobody gets a chart whose data means something other than what the picture says.

## The degrade rule, stated once

**A visual that cannot be drawn leaves the story shorter, and costs nothing else.** Four things
degrade, and every one of them degrades to the same place.

| What went wrong | What the reader gets |
| --- | --- |
| The day predates this file, so `data_path` is absent | The story, with no chart. Absent reads as no data carried. |
| The drawing was published and the data write failed | The story, with no chart. `data_path` stays null; nothing half-written is pointed at. |
| The file does not fetch, or is not a `visual-data` document | The story, with no chart. |
| The document names a renderer or a type this page does not know, or its channels do not pair | The story, with no chart, and a console line naming the file. |

**It refuses rather than guesses, and refusing is free.** A degrade path that draws something
approximate is how a wrong chart reaches a reader, and the product is trust. 94.7 percent of stories
already have no visual, so a story without one is the ordinary shape of the page rather than a hole
in it - there is no placeholder to design and no layout to hold open.

`refusedVisualData` in `frontend/src/lib/payload/drawing.ts` is where that check lives, and
`frontend/src/lib/visual/bar.ts` is what draws once it has passed. The split is not decoration:
geometry with no DOM in it can be checked by calling it twice and comparing, which is the row's
own oracle, and a function that also wrote to a document could only be checked by rendering one.

## Two things that moved with the drawing, and where they went

**`retention.py` reads identity rather than extension.** `_visuals_in` selected a day's
prunable files by image suffix, and a visual is a `.json` document now - the same extension
`digest.json` and `run.json` carry. Adding `.json` to a suffix set would have made the record
that a day happened a deletion candidate, which is a much worse failure than an orphan. So a
visual is **a file named for an item**, which is the rule `render.write.assets_in_day` already
used and the rule the writer already obeys. It needs no list of names to skip, and a list is
what rots: the one that named `digest.json` was written before `run.json` existed, and
`run.json` walked straight through it. `retention.image_months` is 13, so nothing prunes
before 2027 either way.

**`frontend/scripts/copy-visuals.mjs` stages by the same rule.** It selected by image suffix
and now selects a per-item `.json`, because the file the browser fetches has to be in the
bundle. `visuals.asset_base_url` still switches both halves together - where a visual is asked
for and whether it also ships cannot disagree.

## One plan becomes one set of marks, and `compile_bar` is the only thing that makes them

`backend/idhazh/render/chart.py` holds the compiler the plan contract was written for. It takes one
validated `VisualPlan` and one article's `ElementTable`, resolves every mark through
`resolve_displayed_values`, and returns the alt text and the published `VisualData` together.

**The file kept its name and the package kept its name.** `chart.py` says what it produces rather
than how, and it still produces a chart - as data now rather than as pixels. Stripping it in place
is also the diff a reviewer can read: the resolution path, which is the whole safety argument,
shows as untouched lines rather than as a file that arrived from nowhere. Renaming `render/` would
move 23 importers and a dozen doc references for no behaviour, and the moment that is worth an hour
is the one where plans 15 to 18 add the second visual vocabulary and somebody has to name a new
module anyway (Fowler, 2026-09-13).

**One resolution, two outputs.** The sentence a screen reader hears and the data a browser draws
are built from the same resolved marks in one pass, so the picture a reader sees and the sentence
beside it cannot disagree about what the article said. Resolving twice is how they would.

**Every number in those marks came out of the article, by construction.** The plan carries element
references and no figure at all - the shape refuses one - so a bar can only be as long as an element
the extractor cut out of the article's own characters, or as long as a derived value with a chain
back to several of them. Nothing in the compiler can reach a number from anywhere else.

**Category `i` names quantity `i`.** The resolver returns each channel in the plan's own order, so
the pairing is the plan's rather than a rule invented in the compiler, and the bars are drawn in
that order. Re-ranking them here would be the compiler deciding what the comparison says.

**One type, and a second is refused by name.** `bar` is what this build compiles. Compiling a `line`
plan into bars because bars are what we have would publish a picture nobody planned, so every other
member of the vocabulary raises `CompileError` naming itself. The rest of the types are plan 12's.

**The alt text is assembled from the same figures the marks carry**, so the sentence and the
picture cannot disagree. That is the reason `alt_text` is not a field the model may write - and
since 2026-09-13 it is also the whole of what a reader with JavaScript off receives.

**No `title` and no `caption` reach the wire.** The plan carries both and the published marks carry
neither, because publishing the compiled result must not become the hole an authored string gets
through. The drawn title the old renderer put above the bars is therefore gone, and plan 12 row #5
is the row that gives a caption a home.

**A plan this build cannot compile leaves the item decided to nothing, and that is the contract's
ruling rather than a shortcut.** `render_failed` means marks were compiled and their file did not
land, and `VisualDecision` refuses a `render_failed` that carries no spec - so a plan that never
compiled has nothing to record there. `render_planned_visual` in `render/write.py` is the whole path
in one call for exactly that reason: the decision arrives as the `none` it is, a successful compile
promotes it to a `chart` through the contract's own validation, and a caller never has to remember a
`try`.

**The oracle is the published figure against the element table.** `backend/tests/test_render.py`
compiles the committed `bar` plan and asserts every published figure equals the one its element
states, in the plan's own channel order; a second case doubles one element's figure and requires that
one mark to double with the other three untouched, which is what an equality on a single table
cannot say. The browser's half is `frontend/tests/item-visual.spec.ts`, which reads the same numbers
back off a real page and checks each bar's length is its figure in proportion to the longest.

**The canary day carries one compiled visual and one written by hand**, built by
`backend/utilities/build_canary_day.py` from the same committed plan and table, so the browser suite
reads back the marks the backend oracle compiled. Driven from the canary and never from
`frontend/public/digest/`, because a test may not cost more as the archive grows (Guardrail #12).
The hand-written one carries the case a compiled plan cannot - bars with no unit on their axis - and
a third story is planned with no file, which is what keeps a visual that is not a published chart on
the day.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Fold the chart data into `digest.json` | The day payload is never deleted, so chart data inside it would be undeletable and `retention.image_months` would have nothing to act on. It would also make every reader download data for charts 94.7 percent of stories do not have. |
| A list of rows in `VisualData` instead of a flat mark pool | A row is a geometry decision, so the contract grows a case per type and stops being data - and a row list cannot express four names against three figures, which is the mis-shaped payload the reader's page has to refuse. |
| State `renderer_version` in a second place | `spec_format` carried the same idea twice, the two disagreed on 2026-09-05T18:00, and nothing downstream can tell which of two versions to believe. |
| A visual placeholder when a drawing refuses | It makes "we correctly decided this needed no picture" look identical to a failed image, and 94.7 percent of stories already have no visual. |
| Install `d3-selection`, `d3-axis` or `d3-shape` for the reading page | Nothing here joins, enters or exits; `d3-axis` writes a 10px font that would be imported in order to be undone; `d3-shape` has no rect generator. A package absent from the lockfile cannot be imported onto a reading page. |
| Keep the name in a column beside its bar | A name column has to hold 40 of the article's characters, about 250 CSS px, against roughly 300 px of card on a phone - so either the bars or the names lose, and the old drawing hid that by scaling the type until the names fitted. |
| Back-fill the 495 deleted drawings as marks | It means re-fetching 495 source pages that have since moved, and a chart compiled from today's page under an old day's date is a record of nothing. |

## See also

- [visuals.md](visuals.md) - who decides a picture at all, and where the pass runs.
- [what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md](what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) - the plan this compiler is the only reader of.
- [where-every-drawn-figure-came-from.md](where-every-drawn-figure-came-from.md) - the resolution the compiler runs before it writes a mark.
- [one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md) - what the file is called, and what happens when two runs write it.
- [what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md) - the three renderers this ruling replaced, and what each cost.
- [how-a-story-chart-is-drawn-and-what-refuses-one.md](how-a-story-chart-is-drawn-and-what-refuses-one.md) - what the browser does with the file.
- [../contracts/schemas.md](../contracts/schemas.md) - `VisualData`, and where a persisted shape lives.
- [layout.md](layout.md) - the published tree this file lands in.
