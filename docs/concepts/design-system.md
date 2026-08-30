# Design System

**Last Updated**: 2026-08-30

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
- **Colour** - `bg` and elevated surfaces; `text` primary / secondary / tertiary; `accent`; the **confidence ramp**, one token per band, which is the only semantic colour set the digest needs; the **fill ramp**, `--fill-high` / `--fill-medium` / `--fill-low`, which is the same three meanings weighted to be filled rather than read; and the **chart ramp**, `--chart-1` to `--chart-8`, which is categorical and carries no verdict.
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

### A fill is not a text colour

The confidence ramp is a text colour. `--band-high`, `--band-medium` and
`--band-low` are read as type - on a status chip, in a table cell, on a card -
so they are weighted for reading, and a 16px solid painted in one of them reads
as ink rather than as a state. Measured 2026-08-30 against `--color-surface` in
the light theme they run 5.02:1, 5.43:1 and 6.12:1, and the console's run strip
drawn in them read as olive and brick. `--fill-high`, `--fill-medium` and
`--fill-low` are the parallel set: the same three meanings, weighted to be
filled. In light they are `#2e9e63`, `#c08200` and `#e0523a`, reading 3.39:1,
3.26:1 and 3.86:1 - clear of the surface, and clear of text weight. In the dark
theme the two ramps agree today, because a fill there is lighter than its ground
and the band values were already at fill weight.

The band a fill value has to land in, measured against `--color-surface`:

| Theme | Bound | Where it comes from |
| --- | --- | --- |
| Both | at least 3:1 | WCAG 2.2 SC 1.4.11. A graphical object that carries meaning has to be distinguishable from what it sits on, or the shape itself is not there. |
| Light | under 4.5:1 | WCAG 2.2 SC 1.4.3 makes 4.5:1 the *minimum* for normal text, so a colour at or above it is a text-weight colour. That is the defect the ramp removes. |
| Dark | under 9:1 | On a dark ground a fill is lighter than its ground and can never become ink, so the light ceiling does not apply. This bound is a measured tripwire instead: the loudest dark fill reads 7.94:1, and 9 fails `--color-text` at 14.93:1 and pure white at 17.62:1. |

[../../frontend/tests/console-run-health.spec.ts](../../frontend/tests/console-run-health.spec.ts)
computes those ratios itself, from the WCAG relative-luminance formula written
out in that file. It is one surface's oracle over the tokens that surface uses,
not an audit sweep, and it adds no dependency - accessibility audit tooling
stays a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a).

Every ratio in this section is **arithmetic over the committed hex values**, not
a sample: the same two colours give the same number on every machine, so the
spread is zero by construction and the date is the date the values were chosen.
That is why the oracle can assert an exact bound rather than a tolerance.

Rejected: lightening the band tokens themselves, which would fail text contrast
on every surface that reads them as type; and drawing a fill as the band token
at reduced opacity, because opacity over a tinted surface gives a different
colour on every surface and so cannot be checked once. Authority: Jony,
2026-08-30.

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

### A label's shape says whether it can be tapped

> **An outline means you can act on it. A tinted fill means it is telling you something.**

The reading page carries both, one line apart, and without this rule the second one to ship would have had to invent a look:

| | Outlined | Tinted fill |
| --- | --- | --- |
| Example | the topic pill row above a day | a lens chip on an item's eyebrow |
| Type | link or button | `<span>`, never focusable |
| Size | `--text-sm`, tap-height | `--text-xs`, no minimum height |
| Carries | a name and a count | a name only |

**One tint for every member of a label family, not one per member.** A lens chip uses `--tint-accent` whatever the topic is: the word carries the category and the colour carries only "this is a topic". Six hues to say what six words already say would collide with the confidence ramp and the chart ramp, and a `war` chip in a warn hue would read as a severity we never assigned. The seventh lens then arrives with its slot already filled and needs no colour decision - which is the point.

A tinted label is decorative under the rule above, because it repeats a word that is already there. It stays decorative only while it carries the word; a tinted chip carrying an icon alone would be semantic colour with no second signal, and is refused.

### Content on demand is a `<details>`, not a button

A section that leads with a shape and keeps its rows behind a control uses a native `<details>` and `<summary>`. Every page here is prerendered and complete before a script runs, so a button plus a conditional block does not hide the rows - it deletes them for a reader with no script, and the section then makes a claim the reader cannot check. The element is also keyboard-reachable for free and says which state it is in without a second label.

The other shape is different and stays: `Show N more` on the failed-item list and the day list is a button that extends a list already on the page. Nothing behind it is hidden, so nothing is lost when the button is dead.

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

Icons are **vector glyphs referenced by id** from a generated manifest, never inline SVG, never a hardcoded path, never a raster image. The manifest is a persisted surface with its own schema ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). An icon that needs a caption is a label wearing a costume.

**Colour arrives by semantic tint, not by multi-colour artwork.** A glyph is monochrome and inherits `currentColor`, so the thing it sits in decides the hue: a confidence mark takes the band's colour, a topic pill takes the pill's. One set serves both themes, and a new status arrives with a slot already waiting instead of a second artwork file. Multi-colour artwork cannot be re-tinted, so a dark theme would need a second set drawn by hand.

**Where a mark goes, and where it does not.** Chrome, controls, the console and the topic pills. Not beside a headline: a topic is a classification the pipeline actually made and may carry a mark, but "what kind of story is this" is an assertion no stage ever produced, and an icon that asserts it is inventing a fact on the page.

**The set is closed and it is checked in both directions.** `frontend/tests/icons.spec.ts` fails on an icon nothing draws and on a reference to an id that does not exist, so a set cannot rot silently either way. The first of those is not theoretical: the set was cut from 29 glyphs to 15 on the day it landed, because the lens and event taxonomies exist in `config/taxonomy.json` and no surface renders them. Those thirteen marks wait for a surface rather than shipping against one that might arrive.

Source is [Lucide](https://lucide.dev) under the ISC licence; only the icons in use are committed, as unmodified source SVG, and the sprite module is generated from them. Provenance and the add procedure are in `frontend/src/lib/icons/PROVENANCE.md`.

### Design rationale

**Icons ship, and the earlier refusal was wrong (owner, 2026-08-29).** The rule used to say "keep the set tiny: an external-link mark, a confidence mark", which in practice produced two inline SVGs and no system at all - the exact state the icon rule was written to prevent. What was right in the old line was the refusal to put a decorative mark beside a headline, and that survives above as a narrower rule.

**Measured cost, 2026-08-29 on this tree.** Fifteen glyphs, 2,128 B of marks, and the generated module reaches every route because a component names an icon by id and a lookup on a dynamic key cannot be tree-shaken: `/` +1,897 B, `/404` +1,771 B, `/<date>/` +1,900 B, `/archive/` +1,833 B, `/console/` +1,404 B, `/evals/` +1,775 B gzipped. `/evals/` also crossed its prerendered-HTML ceiling by 185 B and the ceiling moved from 2,730 to 2,979.

**The rejected alternative was an inline sprite.** It costs no JavaScript at all, which is better, and puts roughly 700 B of gzipped markup into every prerendered document, which is worse where it lands: `/404` had 37 B of headroom under a ceiling whose whole purpose is keeping the error page tiny. The bytes go where there is room for them. If the JS cost ever matters more than the 404's ceiling, this is the trade to revisit, and the numbers to revisit it with are here.

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

Measured 2026-08-30 on this tree with this bundler - these are the built
artefacts, not a bundler probe. Registering only the chart types in use, the
engine is a lazy chunk of **197,561 B gzipped** (585,481 B raw). Importing the
same package whole instead pulled **345,959 B gzipped** (1,044,275 B raw) when
that arm was last built on 2026-08-29, so the registration file is worth about
half the download and is the reason it is a file somebody has to edit.
`d3-scale` and `d3-array`, which the surface already carries, are 20.5 KB
together.

**That record went 25 percent stale in one day, and the way it happened is the
warning.** It read 153,204 B (451,227 B raw) from 2026-08-29, when the
registration list held the funnel, the tooltip and the SVG renderer. The
six-shape vocabulary added bar, line, pie, grid, legend and mark-line hours
later and nobody re-measured, so the number sat 38,685 B under the truth until
the Sankey row rebuilt it on 2026-08-30. Adding a chart type means editing
`frontend/src/lib/charts/core.ts`, and the whole point of it being a file
somebody has to edit is that they measure it in the same commit.

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
first, and the compression chart's two axes followed it on 2026-08-29. That
column became a range plot on 2026-08-30 and its axis carries the same form.
Three labels naming a quantity and its unit the same way is a form, so it is
written down here rather than copied a fourth time by eye.

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

## Ranked by magnitude, in one shape

The operator asks the same question of most of this page: which one is worst.
Five of the console's six tables answered a different one. They sorted by date,
so the source that cost the digest the most articles sat wherever it happened to
fall, and the feed one run away from being rested sorted below a feed that has
failed harmlessly for a month.

`RankedList`, `TargetBar` and `Sparkline` in
[../../frontend/src/lib/components/](../../frontend/src/lib/components/) are the
shape that answers it. Their arithmetic is in
[../../frontend/src/lib/charts/rank.ts](../../frontend/src/lib/charts/rank.ts),
`targetbar.ts` and `sparkline.ts`, not in the markup, so the number a list
prints and the bar it draws come from one place.

Six rules hold them:

- **Ranked by magnitude, never by date.** A date sort is a log. It is the right
  shape for exactly one thing on this page - the item list behind a selected
  cause - and the wrong shape for every ranking above it.
- **The list prints its own divisor**, as a sentence: `A full bar is 38 cuts.` A
  bar scaled to a hidden maximum can be read for order and cannot be read for
  size, and nothing on the screen tells the reader which of the two they are
  looking at.
- **Capped, with the tail in a sentence.** `2 more sources had 11 cuts between
  them.` The sum is printed only where adding the hidden magnitudes means
  something: counts add, distances do not, and a list of distances says how many
  rows are missing and nothing else.
- **The two empty states say different things.** `Nothing has recorded an
  article length yet.` means the ledger cannot answer. `No article was cut short
  in the last 7 days.` means it answered no. Reading the first as the second is
  the same mistake as reading a null as a zero.
- **No row is tinted.** The order is the ranking. A word beside the name carries
  a status where a row has one, because colour is one signal and never the only
  one.
- **A threshold is a marker on the track, never a subtraction the reader
  performs.** `12 failures` means nothing until the count that rests a feed is
  on the same track. `TargetBar` draws the track at the threshold's own scale,
  the fill at the value, and a rule at the threshold. It takes the confidence
  ramp only where the threshold is a health fact - quarantine is, and a policy
  limit somebody chose is not, so tinting one would invent a verdict nobody
  agreed to.

The bars and the trend lines are markup, not charts. Seventy target bars in a
feed table would be seventy chart instances, and four static bars in a list row
do not need an engine, a canvas or a lazy chunk. Markup is also what still draws
with JavaScript off. The engine keeps the chart types markup cannot draw, and
`sparkline.ts` and `targetbar.ts` now export the shape both drawings read, so
the two can never disagree about where a marker sits or what counts as near.

A trend line takes one colour and never the trend ramp. A rising failure count
and a rising published count are the same shape, and green on the first would be
a verdict the page never measured.

## What the cap cost, by source

`Sources cut short most often` is one row per source, ten of them, and it is the
only place on the site that names a source next to a number about that source.
It exists for one decision: **whether raising the truncation cap would actually
reach a source's articles.**

It is a horizontal range plot on a log word-length axis. One row per source, the
shortest, middle and longest article that source published drawn as a track, and
a dashed rule at each cut point across every row. Everything right of the widest
rule is where the cap bites.

| Part | What it says |
| --- | --- |
| the row label | the source id, as the ledger spells it |
| the line under it | `17 of 38 cut` - articles it lost text on, over articles it published |
| the track | shortest to longest article, with a dot at the middle one |
| the emphasised span | the part of that range past the widest cut point |
| a dashed rule | where a cut fell, read off the rows that were cut, and dated where the window holds more than one |

Eight rulings hold it, Jony's of 2026-08-29 unless a later date is given:

- **The cap is on the chart.** This is the whole defect the plot fixes. Five
  columns of numbers were unreadable because the single number they all had to
  be compared against appeared nowhere in the section. Susan, 2026-08-30.
- **The rule comes off the rows, never off `extract.truncation_cap_tokens`.** A
  window can hold rows a run wrote under an older cap, and the setting is one
  number: over the committed ledger a thirty-day window holds cuts at 1,923
  words and at 3,846, and the file says only 3,846. A rule from the file also
  draws in a window where nothing was cut. Fowler, 2026-08-30.
- **It sorts by count, never by rate.** Measured over the committed ledger the
  shares run 3 to 67 percent on denominators of 6 to 38 articles, so a rate sort
  puts a source with 4 cuts of 6 above one with 17 of 38 - and it is the
  seventeen that cost the digest its articles. `Share cut` was dropped as a
  column on 2026-08-30 for the same reason it was never the sort key. What a
  reader loses is the share as a number; both counts are still on the row.
- **No row is tinted.** The order is the ranking. The confidence ramp means
  good, watch and bad about a summary, and a source at 55 percent is not broken,
  it publishes long articles. The rule itself is drawn in tertiary text colour
  rather than the low band: a red vertical would say the cap is a fault, and the
  cap is a setting somebody chose.
- **Ten rows and no `Show more`.** The worst seven hold 69 of 153 cuts, 45
  percent; past ten the tail is sources with a single cut in a week, and a
  control that reveals rows nobody acts on does nothing.
- **The track is the whole article, cut or not.** A track drawn over the cut
  articles alone would answer a question about the cap with a set the cap
  produced, and it would hide how short the rest of the source's articles are -
  which is the part that says whether the cap is the problem.
- **No ledger or config name reaches it.** Not `truncation_flagged`, not
  `source_words_before_cap`, not `truncation_cap_tokens`, not `Truncated`.
- **The two empty states say different things.** `Nothing has recorded an
  article length yet.` means the ledger cannot answer; `No article was cut short
  in the last 7 days.` means it answered no. Reading the first as the second is
  the same mistake as reading a null as a zero.

Rejected here: the cut share on the run-health strip (a 16px square has no room
for a number, and it answers "did it work" rather than "what did it read"); a
histogram of article lengths (the engineer's chart - it answers what the corpus
looks like, and this section exists to answer whether raising the cap would
reach a source); a linear length axis (the lengths span more than two decades,
and linear crushes every short source onto the left edge - Carmack, 2026-08-30);
keeping the table and printing the cap in the intro sentence (recorded as the
fallback if the plot overran; it answers "how far past the cap" by subtraction
rather than by looking - Susan, 2026-08-30); tinting rows by share cut (a source
at 55 percent is not broken, so the tint would invent a fault); a gauge, dial,
donut or progress bar (six percent on a dial is one pixel of arc); a
before-and-after of a cap change on this page (two caps over two different
article sets is two measurements, not a trend, and that claim belongs in
[../reference/measurements.md](../reference/measurements.md)); and a table
component shared with `Feeds that failed` (an abstraction for two call sites -
reversed on 2026-08-29, when the count reached four; the shape is the ranked
list above).

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

**The refusal of a shared table component was reversed on 2026-08-29, and the
reason it was right at the time is the reason it is wrong now.** It was refused
as "an abstraction for two call sites", which is a good rule: a component built
for two callers usually fits neither and has to be argued with by both. The
count is four - the compression outliers, the failed feeds, the failure ledger
ranked by cause, and the chart-arm's two thresholds - and one of those did not
exist when the refusal was written. What the refusal protected against was a
generic `Table`, and that is still refused: the console's problem was never
table markup, it was that a table is the wrong shape for "which one is worst",
and a generic table would make the wrong shape cheaper to produce. What landed
instead is a shape with an opinion - one order, one divisor, one tail sentence,
two empty states - which is the opposite kind of abstraction. Authority: Fowler
([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md))
on the reversal, Susan on the shape, 2026-08-29.

**The geometry was pulled out of the two chart helpers rather than copied.**
`sparkline.ts` and `targetbar.ts` already owned the rules - the track is the
larger end plus 15 percent, the marker sits at `target / track`, inside 10
percent of the target is a warning, a domain is the drawn extent and not zero -
and each also built a chart option. A second copy of those rules for the markup
bars would drift, and the drift shows as a marker in one panel and a verdict in
another disagreeing about the same number with nothing on screen looking wrong.
So each module now exports the shape, and both drawings read it. The rejected
alternative was having the markup call the chart builder and throw the option
away; it wastes nothing worth measuring, and it makes a component that draws no
chart import a chart builder, which the next reader has to work out.

**Measured on this tree at `f51d669`, 2026-08-29, Windows 11, node 24.** The
three components add **0 bytes** to every route, because nothing renders them
yet - the four call sites land in later rows. The number that will matter is the
one the first call site pays, and it is recorded there. Width-based `@media`
rules in `frontend/src`: **1 before this row and 2 after**, the existing one
being a digest item at 1024px. There are no responsive utility prefixes anywhere
in `frontend/src` - measured as 0 matches - so a rule written in a component's
own stylesheet is the only responsive behaviour the surface has.

Against the sufficiency checks: a ranked row is a four-column grid across the
whole console frame rather than a table that stops where its longest cell
stops; the bar sits on a sunken rail so a short bar is still visibly a bar
against a ground; the longest bar is at the top at full width, which is the one
thing the eye lands on; and a selectable row has a hover state, a visible focus
ring and a pressed state. The one check it does not answer on its own is
whether the page uses its screen - that is decided by the sections that render
it, in later rows.

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
2026-08-29 on this tree with this bundler, and the current ones are in the chart
section above: 153,204 B gzipped for the engine as a lazy chunk carrying only
the chart types in use, against 345,959 B for the same package imported whole,
and 1,854 B for what opening the console actually costs. A reader's route
imports none of it. The chunk figure has since been re-measured twice - see the
chart section for what it reads today and why it moved.

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
