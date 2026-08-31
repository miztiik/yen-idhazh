# Design System

**Last Updated**: 2026-08-31

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

### The reading item is a surface, and it does not float

An item is a card on the page ground: `--color-surface`, `--radius-lg`, a 1px
hairline, and **no shadow at rest**. `--shadow-md` and an accent border arrive
together on `:hover` and on `:focus-within`, so a reader who never touches a
pointer gets the same feedback from the keyboard.

**Nothing lifts.** The title is a heading, not a link, so a rise would promise a
click the card does not answer - and it would promise it on every row of a day
that published 621 items at its largest in the last six (2026-08-26, measured
2026-08-31 on the committed payloads; the six days run 111 to 621). Elevation on
hover says "these lines belong together"; a lift says "click me", and only one of
those is true.

**The hairline is the separation, in both themes, and on dark it takes
`--color-rule-strong`.** The surface lift alone is 1.08:1 in light and 1.10:1 in
dark, which is not an edge in either. Against the page ground, `--color-rule`
reads 1.16:1 in light and 1.36:1 in dark; `--color-rule-strong` reads 1.36:1 and
1.77:1. Dark is the branch `--item-edge` takes when the document names no theme
and light is named explicitly, so the item stays right whichever theme is the
base. Every ratio here is arithmetic over the committed hex values, so the
spread is zero by construction and the date is the date the values were chosen;
[../../frontend/tests/item-card.spec.ts](../../frontend/tests/item-card.spec.ts)
recomputes them from the live document.

**This reverses a rule that never bound.** The item carried "hairline rules
rather than cards: seventeen boxes of chrome on a page whose product is prose is
chrome winning" from the day it was written. It named what was removed and never
what the reader gave up, so under
[../agents/guardrails.md](../agents/guardrails.md) it was not a ruling. It cost
four things: figure and ground on the whole reading surface, the container an
item's chart needed, an anchor a top-of-page list could point at, and any hover
or focus feedback at all. Authority: Susan, 2026-08-31.

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

Theming is override, not a second set of names: **dark is the base and light overrides the same token values.** `:root` carries dark, so a page paints dark before any script runs and keeps it when no script runs at all. Where a utility framework is used, its theme **mirrors** these tokens so a utility resolves to the same custom property - one source of truth, not two - and [../../frontend/tests/tokens.spec.ts](../../frontend/tests/tokens.spec.ts) asserts it: every theme colour has a light override, every non-exempt token has an `@theme inline` mirror, and nothing uses a token that is never declared.

**The type scale is mirrored with its leading attached.** `--text-sm` and
`--leading-sm` are one decision, so the mirror carries both - `--text-sm` and
`--text-sm--line-height` - and the utility emits the pair. Mirror only the size
and the utility silently takes the framework's own default leading, which is the
"a size without a leading is half a decision" rule failing in the one place a
diff does not show it: the source reads `text-sm` and the page renders a leading
nobody chose. Measured 2026-08-31 on the archive search panel, the only place
this had already happened - 14px text on a 20px leading where the token pairs it
with 20.8px.

### A value the scale cannot hold does not go on the reading surface

Every font, colour, size and space on the reading routes resolves through a
utility to a token. Two rules, and an oracle in
[../../frontend/tests/tokens.spec.ts](../../frontend/tests/tokens.spec.ts) for
each, over every file a reading route can reach:

- **No bracketed arbitrary value in a utility class.** `text-[0.8125rem]` is a
  size no theme can reach and no scale can hold. Where one sat between two
  steps it was rounded to the nearer step, and to the larger of the two on an
  exact tie - this surface's proven failure mode is being too little, so a tie
  that shrinks it is the wrong way to break one.
- **No `px` literal in an authored style block.** A hard pixel count ignores a
  reader who set their browser text larger. A size is `%` or `fr` for a share of
  the space, `ch` for a text measure, `rem` for anything that should scale with
  the reader's own setting, or a `clamp()` between two of those.

Two carve-outs, named in the oracle rather than left to a general escape. **A
hairline is `1px`**, because a border that scales stops being a hairline. **A
media-query breakpoint keeps its committed value**, because a media query cannot
read a custom property - and the oracle checks the number against
`frame.breakpoints_px` in `config/appearance.json`, so an invented breakpoint
still fails. An aspect ratio is neither: it has no absolute value, so there is no
step to round it to.

A genuinely dynamic value - a computed width, a chart coordinate - stays in a
`style=` attribute, which the inline-style rule above already allows. The oracle
reads utility classes and `<style>` blocks and does not read `style=`.

**The console is out of scope, and it is excluded structurally.** The oracle
walks the import graph from the reading routes, so a component only the console
renders drops out on its own and no name list has to be maintained against a
sibling plan. A component both surfaces share is covered, which is the stricter
answer and the right one.

### Design rationale

The pile was 60 bracketed values across 19 files and 8 distinct type sizes -
10, 12, 13, 14, 15, 17, 20 and 22px - against a seven-step scale, measured
2026-08-31. Rejected: minting tokens that match the existing values, which
preserves the pile under new names and leaves the scale unusable; and doing this
inside the row that raises contrast, which would put a no-op refactor and a
visual change in one commit so a regression could not be attributed to either.
Authority: Susan and Fowler, with the owner ruling the scope on 2026-08-31 -
every hardcoded value, not only type, because a hex in a component is a colour
the dark theme cannot override.

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

- **`transform` and `opacity`, plus the paint-only properties.** A colour, a border colour and a shadow change without moving anything, so they may ease - `RankedList`, the topic pills and the theme control already do. Never animate a layout-triggering property.
- **`prefers-reduced-motion` is a hard kill-switch** - a media query that zeroes durations, and removes a transform an interaction brings on rather than making it instant. A zeroed duration shortens a movement; it does not remove one, so a 2px rise on hover becomes a jump in one frame and a reader who asked for stillness still sees it move. The reset names the elements that take an interaction rather than every element, because a transform that **positions** something - a rotated axis title, a chart readout centred on its own width - is not motion and a blanket reset drops both on the floor.
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

Measured 2026-08-31 on this tree with this bundler - these are the built
artefacts, not a bundler probe. Registering only the chart types in use, the
engine is a lazy chunk of **192,029 B gzipped** (567,839 B raw). Importing the
same package whole instead pulled **345,959 B gzipped** (1,044,275 B raw) when
that arm was last built on 2026-08-29, so the registration file is worth about
half the download and is the reason it is a file somebody has to edit.
`d3-scale` and `d3-array`, which the surface already carries, are 20.5 KB
together.

**Deleting a component is worth measuring too.** The chunk read 197,561 B
gzipped (585,481 B raw) until the legend component came out of the registration
list on 2026-08-31, because no chart on this site draws a key any more - the
readout strip is the key. That is **5,532 B, 2.8 percent**, and it takes the
room left under the 200,000 B line this plan drew from 2,439 B to 7,971 B. Both
arms were built back to back on one tree, and the arm holding the old list read
197,561 B to the byte.

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

### A chart with a shared column prints every series together, in a fixed strip

One contract, one implementation:
[frontend/src/lib/components/ChartReadout.svelte](../../frontend/src/lib/components/ChartReadout.svelte).
It binds every chart on the console whose marks sit on a shared column - four
series or one - and the rules are not negotiable per chart:

- **A fixed strip below the plot, never a floating box over it.** A floating
  tooltip covers the mark it explains, and one that dodges the cursor moves the
  thing being read. Measured 2026-08-30: a floating box occupied 40 to 55
  percent of the chart it explained.
- **Every series at the hovered column, at once.** Comparing four series must
  not cost four hovers. The strip is the legend as well, so the four numbers a
  reader compares are printed once rather than twice.
- **Capped at `chart.readout_max_share`** - 0.33 today. A share of the plot and
  not a pixel count, so the cap holds at every window width.
- **A vertical guide down the hovered column**, across every series.
- **Reachable by keyboard.** Left and Right step, Home and End jump, Escape
  returns to rest. **A tooltip is never the only place a value appears**: a
  tooltip needs a hover, and a hover is not a thing a thumb can do.
- **It opens on a resting column and is never blank.** The prerendered document
  carries that column's numbers in words, so a reader with no script still gets
  one column read out to him, and the panel never changes size as it fills.

An engine-drawn chart takes the same strip through
[Chart.svelte](../../frontend/src/lib/charts/Chart.svelte). The action goes on
the wrapping element and never on the SVG, because the engine swaps that SVG out
on hydration; the column centres come from `bandShares`, which recomputes them
from the measured width because the engine keeps its grid insets in pixels.

### A chart with no column to hover says so, and no chart draws a key twice

The strip **is** the legend. It prints each series in the colour that series is
drawn in, at the column the reader is on, so a standing key beside it would draw
the same pair a second time - and one fact drawn twice is how two of them drift.
No chart on the console draws a key any more: the engine's `legend` component is
not even registered in
[core.ts](../../frontend/src/lib/charts/core.ts), and the three markup keys that
survived under charts that already had a strip are gone.

A chart with no shared column gets no strip - a ranked list, one target bar, a
flow, two shares of one total. A strip there would print the row the cursor is
already on. **That is a decision, so it is written down where the chart is**:
such a chart carries `data-readout-none` with the reason in words, and a chart
with a column carries `data-readout-columns` with the count.

The pair exists because of what the absence looks like otherwise. A chart
somebody decided needs no hover and a chart where the readout was forgotten are
the same chart on screen.
[console-readout.spec.ts](../../frontend/tests/console-readout.spec.ts)
enumerates every chart on the three console routes, fails on one that declares
neither, fails on a declared column with no strip, and fails on a swatch drawn
inside a chart that has one. It also holds the reason to five words, because
`none` passes an attribute check and tells a reader nothing.

### A stacked chart offers lines only where no data is re-shaped

Stacked says what the mix is and how big the total got. Lines say what one
series did on its own, which a stack hides the moment one band halves while its
neighbour doubles. Both questions are worth answering, so the chart offers both
shapes - **but only where the same array draws both with nothing between them**.

The test is mechanical and is the acceptance rule, not a preference: hand the
engine the identical `data` list in both shapes and change only `type` and
`stack`. The presence of a transform is the definition of "not cheap", and a
chart that needs its data massaged to fit the second shape gets no switch at
all. Owner, 2026-08-30. Two charts qualify today - `What is failing, by stage`
and `Prompt cache`, both callers of `stacked()` - and
`console-chrome.spec.ts` fails the build if their two shapes ever draw different
numbers.

One control per panel, never one per series and never a preference that follows
the reader across the site. A Sankey is not a line and a histogram is not a
stacked bar; forcing the control everywhere would mean massaging data to fit it.

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

### The empty state is the panel, not a replacement for it

A panel that vanishes when it has nothing teaches the operator that the
measurement does not exist. The heading and the explanatory sentence stay; only
the figure changes. Jony, 2026-08-30.

This is the normal case rather than the exception, and the ledger says so.
Measured 2026-08-31 on the committed tree: `job_seconds` and `cpu_model` are
empty on **24 of 54** counter rows, the three host cells on **34 of 54**, and
the counters ledger starts 2026-08-27 against a score ledger that starts
2026-08-22 - so five days inside a thirty-day window have scores and no server
figures at all. A console that only designed the loaded state would be mostly
undesigned.

Five states have fixed wording, written by the owner on 2026-08-30 and held in
[frontend/src/lib/console/recording.ts](../../frontend/src/lib/console/recording.ts).
Only the dates and counts inside them are computed, and every one is derived
from the ledger that is missing - **a date that is not true is worse than no
date**. None is apologetic, none is styled as an error, each states a fact about
the recording at body size in the panel it governs, and none is a banner across
the page: three panels can be in three different states on one day.

| State | What it says |
| --- | --- |
| Measurement off | `Measurement is off. Nothing has been recorded since <day>, so the figures below stop on that day. Turn it back on in config/idhazh.json.` |
| Sampled below 1.0 | `Measured on 1 run in <n>. These figures count the runs we measured and are not scaled up to stand for the rest.` |
| Counters but no scores | `The machine ran and we timed it. Nothing scored the summaries, so this day has no quality figure.` |
| Scores but no counters | `The summaries were scored, but the server's own counters were not written down for this day. The speed figures here come from the summariser, not the server.` |
| Recording started mid-window | `Recording started on <day>. The <n> days before it have no server figures, and the gap in the chart is a gap in the recording, not a quiet day.` |

Two of those are worth reading twice. **A sampled figure is never scaled up** -
multiplying a quarter-sample by four publishes an estimate as a measurement,
which Rule #10 forbids. And **no string names a config key as if it were a
word**: it is `Measurement is off`, never `runtime_counters_scrape is false`,
because a term from a subsystem is not a term for a user (section 0b).

### A figure in currency prints its rate, its source and the word for what it is

There is exactly one money figure on this site: the counterfactual cost on
`/console/machine/`. CLAUDE.md Rule #10 forbids the rest, and carries the
owner's carve-out for that one on conditions this section holds:

- **Never a currency symbol.** `0.48 USD`, never `$0.48`. A symbol in front of a
  number is the shape a bill takes, and this is not a bill - nothing bills us,
  because Actions minutes are free on a public repository.
- **The rate is printed, in full, beside the figure.** Both halves of it: a
  provider prices prompt tokens and written tokens apart, and one blended rate
  would understate a run that wrote a lot.
- **Where the rate came from is printed too** - `Using your rate` or `Using the
  configured rate`. A money figure whose basis is invisible is the exact thing
  Rule #10 exists to prevent.
- **The word for what it is sits in the panel, not in a tooltip**: what the run
  would have cost somewhere else, never an amount owed.
- **Digits are grouped by hand, never by `toLocaleString`.** The server draws
  the page and two builds have to agree; a locale-dependent separator moves the
  prerendered document and the byte gate reads it as a regression.

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

### A section keeps the sentence that decides and loses the sentence that narrates

Twelve rows rewrote this page on 2026-08-30, each writing its own headings,
intros, readouts and empty states. Twelve hands write twelve voices, so one pass
reads the whole page at the end and settles it against `CLAUDE.md` section 0b.

What survives is decided once:

- **A sentence that names a threshold, a denominator, a cost or an
  empty-state reason is kept.** Several of the console's decision rules are
  written nowhere else. Owner, 2026-08-30.
- **A sentence that says what the chart is, or argues for the shape it took, is
  cut.** The heading already names the subject, and the case against a rejected
  chart type belongs in the code comment that rejected it. Owner, 2026-08-30.
- **Prose cut from the page goes into the chart's accessible description**, so a
  screen-reader user is never left with less than a sighted one. Jony.

Three habits are what that pass actually caught, and they are the ones to check
in any new section:

- **One name for one span.** A count inside the window reads `in these 30 days`;
  a section states its own span as `Over 30 days.` The page carried four
  phrasings for one window - `in these N days`, `in the last N days`, `over the
  last N days` and `The last N days` - and wrote the same instruction as `Widen
  the window to look further back` in one section and `reach further back` in
  the next.
- **One name for one control.** `Failure rate against volume` stopped being
  three panels, and the list under it still told the operator that `Panel chips`
  filtered it. A name taken from a component outlives the component.
- **A number says what it is out of, on the same line.** `prompt reused 51%` did
  not, and the figure is a share of prompt tokens, so it reads `prompt tokens
  reused` now. This is the one clause of section 0b a reviewer can check
  mechanically, which is why it catches what the others miss.

**Say it once per screen.** `Sources cut short most often` and the `What the
model did` cards both explained that they follow the window's length rather than
a pan, and `Failure rate against volume` printed the same date span the viewport
heading a few lines above it had already printed. A fact stated twice on one
screen reads as two facts.

### Eleven measures are eleven cards, and the rows are one control away

The eleven above shipped as eleven columns of one table until 2026-08-30, and
that shape could not answer the question an operator brings to it. **Did it get
worse is a vertical scan**, and in a wide table every column beside the one being
scanned is a different quantity - a count, a percent, a second, a minute. At a
thirty-day window it was 330 numbers under eleven header paragraphs.

So the section leads with eleven cards on one `auto-fit minmax(220px, 1fr)`
grid, and each card carries the same five things:

- **The label, verbatim.** The copy above is protected; the shape was the defect
  and the words were not. `frontend/tests/console-model.spec.ts` compares the
  rendered labels byte for byte against the page's own `COLUMNS` and against the
  table on this page, so a paraphrase fails the build rather than a review.
- **The newest day's figure**, at reading size. Which day that is is printed
  once above the grid, not eleven times.
- **A line over the window**, drawn as markup by `Sparkline`. Eleven
  engine-backed sparklines would be eleven chart instances and a lazy chunk on a
  page that renders complete without one.
- **What it is out of**, for the six quality figures. On a table row the day's
  count sat one column away; a card has no row, so it carries its own
  denominator or it invites a trend that is not there.
- **Its sentence**, moved out of the header into the body where there is room
  for it.

**A day the model changed draws a dashed rule across every line**, at the first
drawn point on the new model, from the same rows the daily table draws its
dividers from. Whether a swap moved anything is the question the table could not
answer at all. The rule carries a date and an id and nothing else - an arrow or
a delta across it would claim the swap caused whatever the line then did, and no
committed figure says that.

**No card is tinted.** `Copied, not rewritten` reads about 12 percent and nobody
has agreed what a bad number would be, so a tint there would invent a threshold
and publish it. The health ramp is lent to a threshold somebody agreed to, and
to nothing else.

**The daily table stays, below, behind a `Show the daily figures` control.**
Nothing is deleted: after a card moves, the rows are what say which day. It is a
native disclosure, so the rows are in the prerendered document either way,
opening it costs no fetch, and the whole section works with no script at all.
The dash-not-zero rule, the `<1` rule and the version-stamped share are
unchanged by any of this.

### A distribution answers what a median refuses to

`What one summary cost` is a log-binned histogram of the time to write one
summary, with a cumulative curve on a second axis and a rule at the median and
at the 95th, each printing its own value.

A median answers "how long does one take" and refuses "how bad does it get".
Measured 2026-08-31 over the 3,500 timed summaries in `state/item-health/`, this
box, those are different questions by a factor of 2.5: the median is **122 s**
and the 95th is **300 s**, with a slowest of 702 s. The second figure is the one
that decides whether a shard fits `run.shard_timeout_minutes`, and no single
number on the page was carrying it.

Three rules hold for it:

- **The bars double.** Writing times run from 0.3 s to 702 s, and on a linear
  axis every bar but one is a hairline against the left edge. Each bar is one
  doubling of the clock, so a bar is the same width wherever it sits. The lowest
  bar has no lower edge worth a label and carries the console's own `<1`.
- **The two rules are taken over the values, never off a bar.** A percentile read
  out of a bin is a guess at where inside a doubling it fell, and these are the
  two figures somebody quotes.
- **Leading and trailing empty bars are dropped; a gap in the middle stays.** An
  empty span between two occupied bars is the distribution saying nothing landed
  there, which over the committed ledger is a real and visible fact: one summary
  finished in 0.3 s and the next fastest took 16 s.

**`score_ms` lives under the same heading, as two figures and no chart.** It was
a fourth line on the Pipelines route's `Time per item, by stage` until
2026-08-31, where a fourth line read as a fourth thing the run is held up by. It
is not: the scorer reads a summary the model has already finished. Measured
2026-08-31 over the 3,534 timed rows of `state/scores.csv`, this box, the middle
is **2,463 ms** and the slowest one in twenty is **14,491 ms** - printed as 2 s
and 14 s, because the console prints no decimal. Ten committed rows carry the
zero the column defaulted to before it was written, and they are counted as
untimed rather than as instant. Owner, 2026-08-31.

### Compression is three marks a run, and the band prints its bounds

`How long the summaries came out` draws one column per run: the shortest summary
it wrote, the middle one and the longest.

**It was a mark per summary until 2026-08-31, and the block was the defect.**
Thousands of marks in one colour render their dense middle as a solid area, so
the only marks anybody acts on - a summary of three words, or one at twice the
length that was asked for - are the ones the block hides. Three marks a run keep
both ends and lose the block. Owner, 2026-08-30.

**Per run and never per day.** A day holds up to five runs, and a run is one
model reading one set of articles under one set of settings, so it is the
smallest thing on this page that a change can be attributed to.

**The band's bounds print as numbers beside the chart.** A shaded region nobody
can read a bound off is a decoration, and this one is a setting somebody chose.
The band drawn behind each column is what that run's own articles were asked
for, read through each article's own length rather than off `summarize.bands`
directly - an article's length picks its band, so a run of short pieces is asked
for less than a run of long ones. Susan, 2026-08-30.

### A swap comparison carries direction in the arrow, never in the hue

`Did the model change move anything` is seven paired dot rows. Each measure is
drawn against its own value on the older model, so no change is 100 percent on
every row, and that is the only axis a median in seconds, a length in words and
a count in a hundred summaries can share.

- **The arrowhead carries the direction.** A red-for-worse ramp would need
  somebody to have agreed which way is worse for each of the seven, and nobody
  has: a shorter summary is what a smaller model was picked for, and more
  copying is not obviously worse than more invention. The chart says how far and
  which way, and leaves worse to the reader.
- **The axis is symmetric about no change**, so a fifth off and a fifth on draw
  the same track length. An axis running 78 to 120 would draw one of them as the
  bigger move.
- **Both absolute values print on the row label**, because a ratio with no
  magnitude behind it can be a rounding error wearing a percentage.
- **Both article counts print above the chart, and the panel refuses to draw at
  all where either side holds fewer than `console.min_attempts_for_rate`
  summaries.** Two models over two article sets is two measurements, not a
  trend. Andre, 2026-08-30.

Measured 2026-08-31 off the built page, across the one swap the ledger holds -
`qwen3-8b-q4-k-m` on 2,232 summaries to 26 August, `qwen3-5-9b-q4-k-m` on 1,312
since 27 August - the seven read:

| Measure | Before | After | Against the old model |
| --- | --- | --- | --- |
| Time to write one | 120 s | 124 s | 103% |
| Summary length | 100 words | 79 words | 79% |
| Copied, not rewritten | 9% | 11% | 119% |
| Marked "not sure" | 16 in 100 | 14 in 100 | 86% |
| Numbers not in the article | 5 in 100 | 3 in 100 | 68% |
| "Maybe" told as fact | 12 in 100 | 14 in 100 | 116% |
| Outside the length we asked for | 29 in 100 | 11 in 100 | 38% |

It is a difference and not yet a cause, which is what the two article counts are
there to say.

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

### A date axis is thinned by measurement, and a dropped date keeps its mark

One helper: `dayTicks` in
[../../frontend/src/lib/charts/frame.ts](../../frontend/src/lib/charts/frame.ts).
Every hand-written date axis on the console calls it - the stage timings, the
throughput candles, the band columns, the failure panel, the run lengths and
both run strips through `axisLabels`. There were four rules before 2026-08-31
and three of them thinned by a count.

**A count cannot hold at two widths.** `chart.tick_density` picks the columns
that carry a tick mark, and then the labels are measured against the room the
plot actually has and dropped in whole steps until no two of them touch. So the
knob is a **ceiling and never a target**: it can take a label away and it can no
longer force one on. Measured 2026-08-31 on the built console at 390px, before
this rule: `Summary length against the length asked for` drew `2 Aug 2026` and
`8 Aug` 13.6px on top of each other, `Time per item, by stage` 7.4px,
`Model tokens per second per day` 26.1px and `Summary length per run` 1.9px.

The width comes from the string rather than from the element, because the axis
is decided on the server where there is no text engine to ask. `LABEL_ADVANCE_EM`
is 0.58, which is ten percent over the widest character measured at
`font-size="10"` in Chromium on 2026-08-31 - `20 Aug 2026` is 55.83px over 11
characters and `18 Aug` is 31.53px over 6. It is deliberately over: an estimate
under the truth lets two labels touch, and an estimate over it only drops one
label the axis could have carried.

**A dropped label keeps its tick mark.** A reader counting columns needs the
grid even where the date is gone, so the marks come from the ceiling and only
the dates thin.

**The end labels anchor inwards.** The first and last tick of any axis sit ON
the plot edges, so a centred label there hangs half its own width outside the
frame and an `svg` cuts what hangs. Measured 2026-08-31 at 1440,
`What the cap cost, by source` drew `10,000` 3.2px past its own `svg` and read
`10,00`. `tickAnchor` is the rule and it binds a value axis as well as a date
one.

Two console axes are drawn by the engine rather than by us, and the engine owns
where its labels go - `hideOverlap` is its own measured rule and it is left to
do that job. What they take from here is the date grammar: `2026-08-25` is how
the ledger spells a day and it is not how a page says one.

The oracle is geometric and reads the page rather than the rule. At 1440, 768
and 390 it collects the box of every element carrying `data-day-axis` and
asserts that no two on one axis overlap and that none is drawn outside the `svg`
that would clip it -
[../../frontend/tests/console-axis.spec.ts](../../frontend/tests/console-axis.spec.ts).

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
  in these 7 days.` means it answered no. Reading the first as the second is
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
  in these 7 days.` means it answered no. Reading the first as the second is
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
for two callers usually fits neither and has to be argued with by both. Counted
again on 2026-08-30 once every section had landed, the three components draw
**nine times across five sections**: `RankedList` twice, in the band-distance
outliers and the failure ledger; `TargetBar` three times, on the feed
quarantine countdown and the chart arm's two thresholds; and `Sparkline` four
times, in the failure ledger, `What the model did` and the chart arm. Two of
those sections did not exist when the refusal was written. What the refusal
protected against was a generic `Table`, and that is still refused: the
console's problem was never table markup, it was that a table is the wrong
shape for "which one is worst", and a generic table would make the wrong shape
cheaper to produce. What landed instead is a shape with an opinion - one order,
one divisor, one tail sentence, two empty states - which is the opposite kind
of abstraction. Authority: Fowler
([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md))
on the reversal, Susan on the shape, 2026-08-29.

**The refusal to window `Sources cut short most often` was reversed on
2026-08-30, and it turns on one word: hidden.** The section read a fixed seven
days, and widening it was refused because a span the reader cannot see makes
the section's own sentence lie - `17 of 38 cut` over a span nobody names is a
count with no denominator in time, and a number in a config file is exactly
that kind of unseen span. What changed is that the span stopped being unseen.
One control at the top of the page holds it, all four presets are on the screen
at once, and every windowed section states the span it read in its own sentence
and in its accessible description. A control the operator is looking at cannot
make the sentence lie, so long as the sentence reads the same window the query
reads - and `frontend/tests/console-window.spec.ts` asserts exactly that, for
every surface that declares itself windowed. The section prints its own
denominator too, which at seven days runs as low as six articles, so the
narrowest window says how thin it is instead of hiding it. The rejected
alternative was leaving the seven days fixed while every other section followed
the control: two spans on one page is the defect the shared window exists to
remove, and the section that disagreed would be the one nobody checked.
Authority: Susan on the reversal, Fowler on recording it, 2026-08-30.

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
