# Design System

**Last Updated**: 2026-08-29

The visual vocabulary of the published surface: the state-driven styling pattern, design tokens, the restrained motion set, and the icon rule. This is the shared language the [chrome](ui-shell.md) and every [item](digest.md) speak; the concrete token file lands with the design-system code row, and this page fixes the vocabulary that row builds to. The bounds are owned by Jony ([../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md)).

The surface is small on purpose: a digest page, an item, and an eval dashboard. There is no application here - no session, no navigation tree, no state to lose ([vision.md](vision.md)).

**The architecture fixes how much surface there is. It does not fix how good that surface is.** Scope-restraint is inherited and not up for debate. Craft-restraint is a choice, and every instance of it needs an argument on the day it is made.

## Typography is the interface

This is a reading surface before it is anything else. Measure, leading, hierarchy and the space between items do more work here than any component will, and a digest that is hard to skim has failed before a single control is considered.

- **A reading measure on the text, and a fluid frame around it.** Long lines are where a skim turns into work, so the summary, the title and the key points are held to a measure. **The measure is a property of a text element and never of the shell.** Put it on the shell and the whole application inherits a paragraph's width: measured 2026-08-28, one `max-w-2xl` on the root layout capped every page at 624px and left 912px of a 1536px screen empty, including a console with five tables and six charts in it.
- **A hierarchy of exactly three levels** on an item - what it is, what it says, where it came from. A fourth level means something on the item has not earned its place.
- **Two faces at most**: one for reading, one for data (tabular numerals on the dashboard, so columns line up).

## The state-driven styling pattern

The DOM state is the single source of truth for the view. Nothing is styled imperatively: **state is reflected by toggling a class or a `data-` attribute, and CSS reacts declaratively.**

- **State classes** carry the look: `loading`, `empty`, `degraded`, `truncated`, `low-confidence`.
- **Data-attribute styling** carries variants: an item keys its treatment off `data-route` (chart / diagram / illustration / none) and `data-band` (the confidence band from [evaluation.md](evaluation.md)).
- **No inline styles** except genuinely dynamic values. Everything else is a token or a class.

Because the payload already carries the route kind, the band and the truncation flag, rendering is **one component parameterised by data** rather than a layout per item type. A per-item special case is a smell.

## Design tokens

Every colour, space, radius, shadow, font, easing and duration is a CSS custom property in [../../frontend/src/styles/tokens.css](../../frontend/src/styles/tokens.css), named **by purpose**, not by value:

- **Fonts** - a display face for headings, a reading face for body, and a tabular data face. The display face is self-hosted woff2, Latin subset, one variable file at 48,256 bytes; the body keeps the system stack, because that renders on the first frame at zero bytes and the body is what the reader came for.
- **Space** - `--space-0` to `--space-9` on a 4px base. On a page that is mostly text this does more work than any component will.
- **Type** - `--text-xs` to `--text-3xl`, each paired with its own `--leading-*`. A size without a leading is half a decision.
- **Radius** - five steps. Panel language needs a bigger corner than a chip does.
- **Elevation** - `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-panel`, plus `--color-surface-raised` and `--color-surface-sunken`. A page with one surface colour is a page where nothing is in front of anything.
- **Colour** - `bg` and elevated surfaces; `text` primary / secondary / tertiary; `accent`; the **confidence ramp**, one token per band, which is the only semantic colour set the digest needs; and the **chart ramp**, `--chart-1` to `--chart-8`, which is categorical and carries no verdict.
- **Tints** - `--tint-accent`, `--tint-info`, `--tint-good`, `--tint-warn`, `--tint-bad`, `--tint-neutral`. A panel takes the hue of what it means, at 7 to 9 percent in light and roughly double that in dark.
- **Gradients** - `--gradient-brand`, `--gradient-wash`, `--gradient-panel`. Chrome and identity only.
- **Frame** - `--frame-reading`, `--frame-console`, `--measure`, `--gutter`. Defaults live in the token file and `config/appearance.json` overrides them at build time ([config.md](config.md)).
- **Motion** - one ease and a short duration scale.

**The two colour ramps may not be swapped for each other.** The confidence ramp
is green, amber and red because those colours mean good, watch and bad. The
chart ramp exists so a chart can tell up to eight series apart, and it
deliberately holds none of those three hues - a chart that borrowed the band
tokens told a reader that the slowest stage was the failing one.
`--source-swatch-*` is not the answer either: those are pale background tints
for a monogram, not stroke colours, and at 1px on a white card they are not
visible. `--series-1` to `--series-4` survive as aliases of the first four chart
stops so no existing chart changed colour when the ramp widened.

**The dark theme is designed, not derived.** A shadow on a dark ground reads as
nothing, so elevation there is a raised surface colour plus a hairline; every
tint is re-tuned rather than reused at the same alpha, because the same alpha
over a dark ground is invisible.

**A scale is not a colour, and does not live in a theme block.** Space, type,
radius and motion are declared once in their own `:root` block outside both
themes. A scale left inside a theme block reads as something a theme could
change, and the next theme has to restate it or lose it.

Theming is override, not a second set of names: dark mode overrides the same token values. Where a utility framework is used, its theme **mirrors** these tokens so a utility resolves to the same custom property - one source of truth, not two - and [../../frontend/tests/tokens.spec.ts](../../frontend/tests/tokens.spec.ts) asserts three things at once: every theme colour has a dark override, every non-exempt token has an `@theme inline` mirror, and nothing uses a token that is never declared.

## Colour is one signal, never the only one

A confidence band carries a **word** as well as a tint. A route kind carries a shape or a position as well as a colour. This is a clarity rule for all readers, and it is also what keeps the page legible in a screenshot, in dark mode, and on a bad screen.

Accessibility *audit tooling* is a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a); labelled controls, semantic landmarks and visible focus are simply good building and are in scope.

### Decorative colour and semantic colour are not the same rule

The rule above binds **colour that encodes meaning**. Read as a general ban on colour it says something it never meant, and for eleven months that is how it was read: no gradient was proposed on this surface, ever, and the reason was a rule that does not apply to one.

- **Semantic colour is doubly constrained.** A tint that tells a reader something carries a word or a shape as well, and it may never borrow the confidence ramp's three hues. This is the whole of the rule above.
- **Decorative colour is unconstrained.** Chrome, identity, a panel tint, an empty state, the wordmark, a page background. It encodes nothing, so there is nothing for a second signal to duplicate.

The line is drawn by the question "would a reader be wrong about a fact if this were grey?" A gradient on the site header fails that question, so it is decoration. A gradient running red at the bad end of a chart passes it, so it is semantic and is refused - a reader would read the hue as the verdict.

## Sufficiency is a gate, not a taste

A surface fails review for being **insufficient**, exactly as it fails for being over-built. This is stated because the opposite was: every review persona this project had was a veto, so the surface converged on the minimum that passed all of them, and nobody's job was to say it was not enough.

The checks, applied to any reader-facing surface:

- **Does it use the screen it is on?** Measured 2026-08-28: the digest used 40.6 percent of a 1536px viewport and had two responsive breakpoints in the entire site, one of which changed padding.
- **Does it separate figure from ground?** A page with one surface colour and no elevation is a page where nothing is in front of anything.
- **Is there one thing the eye lands on first?** If everything is the same weight, the page has no order to read it in.
- **Does it look like it was made this year?** Not a matter of fashion. A surface that looks abandoned is read as abandoned, and the judgement transfers to the summaries.

A surface that fails one of these ships only with a `## Design rationale` entry saying why. `CLAUDE.md` section 9 carries the Definition-of-Done line; Susan ([../../.github/agents/susan.agent.md](../../.github/agents/susan.agent.md)) rules them.

**And a veto costs something.** A ruling that removes must name what the reader loses. "Remove before adding" is a good instinct and a bad rule when it is free: a removal that states only what was removed is not a ruling and does not bind ([../agents/guardrails.md](../agents/guardrails.md)).

## Motion vocabulary

There is almost no motion here, and that is the correct amount. This is a page a reader skims, not a thing they operate.

- **`transform` + `opacity` only.** Never animate a layout-triggering property.
- **`prefers-reduced-motion` is a hard kill-switch** - a media query that zeroes durations.
- The whole named set: `fadeIn` (content arriving), `shimmer` (skeleton while a payload parses), `toastIn` (the rare notice). Anything beyond these needs an argument.

There is no network in the loop, so **there is no excuse for a spinner.**

**One control on the whole site does wait on a network, and it still gets no
spinner.** The archive's search downloads a 43 MB encoder the first time a
reader uses it. What it shows meanwhile is bytes as type, taken from the
library's own count of what has arrived - a measurement, not an animation. When
the weights land that count goes blind, because the runtime behind them reports
nothing to anybody, so the line stops printing numbers and prints a word. A bar
that keeps moving on no measurement is a bar that is making it up.

## A machine's state is a sentence, never a dot

Colour is one signal and never the only one, and that rule has a second edge: a
dot says nothing until it carries a word, and once it carries a word it is a
sentence. So a state a reader has to act on is written out in full.

The archive's on-device search is the whole example, and it has five states:

| State | The sentence |
| --- | --- |
| Not downloaded | `Search runs on your device. The first search downloads 43 MB, once. Nothing you type leaves your browser.` |
| Downloading | `Downloading - 12.4 MB of 43 MB.` and, once the count goes blind, `Getting ready to search.` |
| Ready | `Search runs on your device. Nothing you type leaves your browser. The download is done.` |
| The encoder changed | `The search files changed since your last visit. The next search downloads 43 MB again, once. Nothing you type leaves your browser.` |
| This browser cannot run it | `Search is unavailable here - this browser cannot run it. Everything above still works.` |

Three rules hold under them:

- **The cost is named before the click, never after it.** Whether the download
  has already been paid for is read out of the browser's own cache storage. That
  is this device's disk, so nothing is reported anywhere and Rule #1 is intact.
  When it cannot be read the whole size is printed, because overstating a cost
  is honest and understating one is not.
- **Every wait offers a stop, and stopping leaves the page as it was.** Nothing
  greys out while a download runs, and the list a reader was reading stays live.
- **A failure offers a retry.** One flaky connection may not turn a feature off
  for the rest of a page's life.

The shape generalises past this one control: any state worth a colour is worth a
sentence, and a state a reader cannot act on is worth neither.

## Icons

Icons are **vector glyphs referenced by id** from a generated manifest, never inline SVG, never a hardcoded path, never a raster image. The manifest is a persisted surface with its own schema ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). Keep the set tiny: an external-link mark, a confidence mark, and whatever the dashboard genuinely needs. An icon that needs a caption is a label wearing a costume.

## Charts are static first, enhanced only when interaction earns it

A chart on an item is rendered at build time from a specification and shipped as an asset ([digest.md](digest.md)). Every chart on the dashboard is hand-written markup over a committed CSV or the published telemetry projection.

**No chart library on a reader's route. The operator surface is a separate
question, and it is open.** A scale library is not a chart library and never was.

The reading-route half of that is settled and is not about bytes on a graph: a
chart on an item is rendered at build time and shipped as an asset, so a reader
has nothing to run. A charting engine on a reading page is a runtime dependency
for nothing.

The console half was decided wrongly, twice, and both times on an argument that
turned out not to be the real one. A chart library was carried for the console
between 2026-08-23 and 2026-08-24 for pan and zoom, then removed because the
viewport control already did that with a keydown handler and four buttons - a
correct removal. On 2026-08-29 the same blanket ban was re-argued from a
`/console/` weight of 66,550 B that was **four and a half times out of date**;
the route was 301,580 B by then. The owner overruled it. What replaces it is not
another blanket, in either direction: it is three conditions and a measurement,
below.

Any library adopted for the console must (1) render SVG, not canvas, so
`tokens.css` stays the only place a colour is decided, (2) render server-side at
build time, so the page is complete before any script runs, and (3) carry a
measured gzipped cost recorded next to the decision.

Measured 2026-08-29 on this tree with this bundler, after the engine shipped -
these are the built artefacts, not a bundler probe. Registering only the chart
types in use, the engine is a lazy chunk of **153,204 B gzipped** (451,227 B
raw). Importing the same package whole instead pulls **345,959 B gzipped**
(1,044,275 B raw) for the same one chart, so the registration file is worth 56
percent of the download and is the reason it is a file somebody has to edit.
`d3-scale` and `d3-array`, which the surface already carries, are 20.5 KB
together.

The number that decides whether this is affordable is not the chunk. It is what
opening the console costs, and that moved **1,854 B**, from 69,622 to 71,476 -
the component, the option builder and the token bridge. About 40 B of that is
the toolchain rather than the change: every unrelated route on the same machine
and the same node read 36 to 63 B above its record in the same build. The engine
is fetched only when a chart hydrates, and no other route references it at all;
`frontend/tests/charts.spec.ts` fails the build if a page ever preloads it.

Those numbers belong to the console route alone - the reading routes never
import any of it.

What a chart may take from a library is the arithmetic. `d3-scale` and
`d3-array` map a domain to pixels and choose the tick values; they own no
element, no canvas and no theme, and the marks, the SVG and the prerendering
stay ours. `.nice()` and `ticks()` are the part a hand-rolled axis gets wrong,
and getting them wrong shows as an axis labelled 0, 37, 74 that nobody can read
a value off. Nothing on a reader's route imports either one.

**A chart draws in CSS pixels at the width it occupies.** A `viewBox` is a scale
factor, not a unit: four charts that each pick their own and then stretch to the
column render the same `font-size` at four sizes. Measured 2026-08-25 at a
1057px window, one console page put `font-size="10"` on screen at 4.5px in one
panel and at 16.6px in the next. The width comes from one place -
[frontend/src/lib/charts/frame.ts](../../frontend/src/lib/charts/frame.ts) - and
the server draws at `console.chart_width` so the page is complete before any
script runs.

Hand-written SVG has a second property worth stating: it renders on the server,
so a page is complete before any script runs. A canvas cannot inherit a CSS
custom property inside the drawn pixels, so a canvas chart has to resolve the
token values in JavaScript at mount and again after every theme change - which
means the token file stops being the only place a colour is decided.

## A console figure says what it counts, in words

The console is read by the developer and the operator, not by a digest reader.
That sets who it is for; it does not relax how it is written. `CLAUDE.md`
section 0b binds every string in this repo, so a figure on this page is labelled
in words a person can act on and never in the name of the column behind it.

Five rules hold for every number the console prints:

- **A count of that day's items, not a score.** No value between zero and one
  reaches the screen, and no cell prints a decimal. A share prints as whole
  percent.
- **No ledger column name on screen.** `hhem`, `hedge_dropped` and
  `truncation_flagged` are how the file spells it. The page spells what it
  means.
- **A dash where the ledger holds no answer.** Null and zero are different
  facts, and a zero that was really an absence is the one number nobody checks.
- **`<1` where a real measurement rounds away.** A `0` there would say the work
  was free.
- **The item count sits beside every quality figure.** A share over four
  articles is not a measurement, and a column that hides its denominator
  invites a trend that is not there.

The label set for `What the model did`, with the sentence each one carries:

| Label | The line under it |
| --- | --- |
| Summaries today | - |
| Marked "not sure" | How many of today's summaries we told you not to trust. |
| Numbers not in the article | The summary had a figure. The article did not. |
| "Maybe" told as fact | The article said it might have happened. The summary said it did. |
| Article read only in part | The article was too long, so the machine read the start and stopped. |
| Read only in part, as a percent | The same articles, against the day's own count, so a busy day and a quiet one compare. |
| Copied, not rewritten | How much of a normal summary is lifted word for word. |
| Time to write one | How long the machine takes on one article. The second figure is the articles it read only the start of. |
| Model minutes | - |
| Too long to send | The article and the instructions together did not fit, so the machine was never asked. |
| Failed | - |

Two of those carry a rule the others do not. **The share divides by the rows
its own flag answers for**, never by the day: `truncation_flagged` changed
meaning on 2026-08-28, so a day holding rows from both sides of that stamp would
otherwise report a fact about the migration wearing a percent sign. And **`Time
to write one` carries a second figure only where the day cut something** - a
dash under every other day would be a column of absences pretending to be a
split.

**`Too long to send` is expected to read zero, and that is the point of it.** At
a truncation cap of 2,500 tokens no prompt can reach the window the machine
reads with, so the count is zero by arithmetic rather than by luck. It is on the
page so that the day the cap moves, the number that says the move went too far
is already being printed.

### An axis title and a column header take one form

`Article length, words`. **Sentence case, a comma, the unit in lower case, and
no full stop.** `Sources cut short most often` shipped `Longest article, words`
first, and the compression chart's two axes followed it on 2026-08-29. Three
labels naming a quantity and its unit the same way is a form, so it is written
down here rather than copied a fourth time by eye.

- **The quantity, then the unit.** `Summary length, words` - never `Summary
  length (words)` and never `words`. A bracket reads as a footnote, and a label
  a reader meets before any of the numbers is not a footnote.
- **An axis title may not be a ledger column name.** `source words` is how the
  file spells `source_word_count` and `source_words`. A term from a subsystem is
  not a term for a user (`CLAUDE.md` section 0b), and this is the rule two
  bullets above - no ledger column name on screen - applied to the label rather
  than to the cell.
- **It says what the heading says.** Until 2026-08-29 the compression chart
  called one quantity `Article length` in its heading and `source words` on its
  axis, on one screen. Two names for one thing makes a reader work out that they
  are the same thing before they can read the chart.
- **A label that needs no unit is just the noun.** `Runs`, `Failed`, `Cut
  short`. The comma form is for a quantity whose number means nothing without
  the unit, and adding one where none is needed is noise.

Where each figure is read from is in
[../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md).

## What the cap cost, by source

`Sources cut short most often` is one table of ten rows, and it is the only
place on the site that names a source next to a number about that source. It
exists for one decision: **whether raising the truncation cap would actually
reach a source's articles.**

| Header | What it prints |
| --- | --- |
| `Source` | the source id, as the ledger spells it |
| `Cut short` | articles this source lost text on |
| `Articles` | articles it published in the window - the denominator |
| `Share cut` | whole percent, or a dash under `console.min_attempts_for_rate` |
| `Longest article, words` | the longest article it published, before the cut |

Five rulings hold it, all Jony's, 2026-08-29:

- **It sorts by count, never by rate.** Measured over the committed ledger the
  shares run 3 to 67 percent on denominators of 6 to 38 articles, so a rate sort
  puts a source with 4 cuts of 6 above one with 17 of 38 - and it is the
  seventeen that cost the digest its articles. The sort order is the ranking,
  which is also why **no row is tinted**: the confidence ramp means good, watch
  and bad about a summary, and a source at 55 percent is not broken, it publishes
  long articles.
- **Ten rows and no `Show more`.** The worst seven hold 69 of 153 cuts, 45
  percent; past ten the tail is sources with a single cut in a week, and a
  control that reveals rows nobody acts on does nothing.
- **The longest article is the whole article, cut or not.** A column that read
  the longest *cut* article would answer a question about the cap with a number
  the cap produced.
- **No ledger or config name reaches it.** Not `truncation_flagged`, not
  `source_words_before_cap`, not `truncation_cap_tokens`, not `Truncated`.
- **The two empty states say different things.** `Nothing has recorded an
  article length yet.` means the ledger cannot answer; `No article was cut short
  in the last 7 days.` means it answered no. Reading the first as the second is
  the same mistake as reading a null as a zero.

Rejected here: the cut share on the run-health strip (a 16px square has no room
for a number, and it answers "did it work" rather than "what did it read"); a
histogram of article lengths (the engineer's chart - the scatter already shows
that distribution along its x axis); a gauge, dial, donut or progress bar (six
percent on a dial is one pixel of arc); a before-and-after of a cap change on
this page (two caps over two different article sets is two measurements, not a
trend, and that claim belongs in
[../reference/measurements.md](../reference/measurements.md)); and a table
component shared with `Feeds that failed` (an abstraction for two call sites).

**Quality is a table, never a line.** A line invites a trend across days whose
articles have nothing in common. The one thing on the page that draws a spread
is the throughput candle, because a spread is a property of a day's article mix
and a single number cannot carry it.

**A fixed benchmark figure never appears on the console.** It was taken on
another machine against another workload, so a gap between it and a run reads as
a regression nobody measured. Those numbers stay in
[../reference/measurements.md](../reference/measurements.md) and the page links
to them.

## Design rationale

**Three sentences were struck on 2026-08-29, and the reason is one mechanism rather than three mistakes.** This page opened with "Restraint is not a style choice on this project; it falls out of the architecture", [ui-shell.md](ui-shell.md) and [vision.md](vision.md) said the operator surfaces "earn no design budget", and the reading measure was written as a property of the shell. All three are defensible sentences and all three are the same error: an architectural constraint restated as a design value. Rule #1 constrains what may *execute* at read time and says nothing about what may be *drawn* - a gradient, an elevation scale and a self-hosted face are bytes in a committed stylesheet that cost a reader nothing at read time and the runner nothing at build time. But a constraint stated as a value stops needing a justification, so every additive proposal had to argue against the project's own doctrine while every subtractive one was pre-approved.

The measurements that settled it, taken in the integrated browser on 2026-08-28: 40.6 percent of a 1536px viewport used; the content column fixed at 624px from 1024px upward; **two** responsive breakpoints in the whole of `frontend/src`, one of which changes padding and the other of which divides an already-capped column into three 164px charts; seven horizontal scrollbars on the console while 582px of screen sat empty beside them. The rejected alternative was softening the three sentences rather than striking them, and it was rejected because a softened absolute is still read as an absolute. Authority: owner, 2026-08-29, over Jony's prior ruling.

**The token list on this page specified a shadow scale and a space scale that were never built.** That is not a doctrine change and it is worth naming separately: the doctrine was right and the implementation stopped short, which is the quieter half of the same failure.

**Sufficiency became a gate because the review roster was six vetoes and no demand.** Jony removes, Fowler deletes, Carmack refuses on budget, Reader and Editor report. Nothing asked whether the result was good enough to be worth a stranger's attention, and a system of pure vetoes converges on the minimum that passes every veto. The rejected alternative was giving Jony the demand mandate as well; one head holding both "remove before adding" and "this is not enough" resolves to the veto every time, which is the observed outcome. Susan was added at a distinct altitude instead, and a veto now has to name what the reader loses. Authority: owner and Fowler, 2026-08-29.

Driving the look from fields the payload already carries - route kind, band, truncation - rather than from per-item styling decisions is what keeps the surface one component instead of many, and it means a new route kind or band arrives with a slot already waiting for it. The rejected alternative, bespoke treatment per item type, produces a page that must be edited every time the pipeline learns something new. Authority: Jony.

Keeping the motion set to three named animations is a deliberate under-build. A reading surface that animates is a reading surface that interrupts. Authority: Jony, with Reader ([../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md)) as the check.

Taking `d3-scale` and `d3-array` while still refusing a chart library is one
distinction, not two rules. A chart library owns the element, the redraw and the
theme, which is why the last one drew a second copy of a chart that already
existed. A scale library returns a number. The rejected alternatives were all
libraries that draw: `echarts` (336 KB gz, canvas), `@observablehq/plot`
(128 KB gz, and it needs a DOM shim to prerender), `chart.js` (67 KB gz,
canvas), `uplot` (removed one row below, and re-adding it would re-litigate a
settled decision), and a component library, which is worst of all when every
chart on the surface is bespoke. A CDN was rejected on top of all of them: the
HTTP cache is partitioned per site, so the shared-cache argument is dead, and
the repo's `script-src` allows `self` only. "Fix the units without the
dependency" was rejected last, because `.nice()` and `ticks()` are exactly the
part hand-rolling gets wrong. Authority: Jony and Carmack, 2026-08-25, owner
accepted.

**The blanket ban on a chart library was reversed for the operator surface on
2026-08-29, and the reason it was wrong is worth more than the reversal.** It
rested on three claims. The first was a byte count - "the `/console/` route is
66,550 B" - which was **four and a half times out of date**; the route was
301,580 B on the day the argument was made. The second was "a canvas cannot
inherit a CSS custom property", which is true of canvas and false of the SVG
renderers those libraries also ship, so it generalised from the worst case. The
third, that the page would stop being complete before script runs, holds only
for a library that cannot render server-side, and the leading one has an
explicit build-time SVG mode.

The paragraph above this one is still correct about a reading route and is not
touched. What changed is that the two surfaces stopped sharing one answer.

The measurements that now stand in place of the stale one were taken on
2026-08-29 on this tree with this bundler, and are in the chart section above:
153,204 B gzipped for the engine as a lazy chunk carrying only the chart types
in use, against 345,959 B for the same package imported whole, and 1,854 B for
what opening the console actually costs. A reader's route imports none of it.

Three lessons are recorded because they are more transferable than the ruling.
**A byte count is a measurement and goes stale like any other** - Rule #10 asks
for the hardware and the date, and a design argument that leans on a number
someone took months ago has not met it. **An argument that generalises from
the worst implementation of a thing is not an argument about the thing.** And
the one this row taught at its own expense: **a bundler probe is not the
artefact.** The 188.4 KB that justified this decision was measured with a
standalone bundler script; the thing that shipped read 345,959 B until the
imports were narrowed, and 153,204 B after. Measure the file the build wrote.

A fourth, about the argument rather than the bytes: the case made for the
engine here was that it buys a pointer readout. It does not - `frontend/src/lib/charts/frame.ts`
already had one, covering mouse, pen, touch and keyboard, and two of the four
charts were simply never wired to it. The engine earns its place on chart types
the surface cannot draw today, which is a smaller claim than the one first
made. **Check whether the thing a dependency is supposed to buy is already
built** before pricing it.

Authority: owner, 2026-08-29, overruling the 2026-08-25 ruling on the operator
surface only.

## See also

- [ui-shell.md](ui-shell.md) - the chrome that consumes these tokens.
- [../../.github/agents/susan.agent.md](../../.github/agents/susan.agent.md) - who rules the sufficiency checks, and why the roster needed a demand side.
- [../agents/guardrails.md](../agents/guardrails.md) - the authority table, and the rule that a veto must name what the reader loses.
- [digest.md](digest.md) - the item shape this vocabulary dresses.
- [evaluation.md](evaluation.md) - where the confidence bands come from.
- [principles.md](principles.md) - the beliefs behind the restraint.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the console projection.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the payload fields the styling keys off.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a (accessibility scope) and section 12 (published-site verification).
