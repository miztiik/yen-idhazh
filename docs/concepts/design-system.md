# Design System

**Last Updated**: 2026-08-27

The visual vocabulary of the published surface: the state-driven styling pattern, design tokens, the restrained motion set, and the icon rule. This is the shared language the [chrome](ui-shell.md) and every [item](digest.md) speak; the concrete token file lands with the design-system code row, and this page fixes the vocabulary that row builds to. The bounds are owned by Jony ([../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md)).

The surface is small on purpose: a digest page, an item, and an eval dashboard. There is no application here - no session, no navigation tree, no state to lose. Restraint is not a style choice on this project; it falls out of the architecture ([vision.md](vision.md)).

## Typography is the interface

This is a reading surface before it is anything else. Measure, leading, hierarchy and the space between items do more work here than any component will, and a digest that is hard to skim has failed before a single control is considered.

- **A reading measure**, not a full-width line. Long lines are where a skim turns into work.
- **A hierarchy of exactly three levels** on an item - what it is, what it says, where it came from. A fourth level means something on the item has not earned its place.
- **Two faces at most**: one for reading, one for data (tabular numerals on the dashboard, so columns line up).

## The state-driven styling pattern

The DOM state is the single source of truth for the view. Nothing is styled imperatively: **state is reflected by toggling a class or a `data-` attribute, and CSS reacts declaratively.**

- **State classes** carry the look: `loading`, `empty`, `degraded`, `truncated`, `low-confidence`.
- **Data-attribute styling** carries variants: an item keys its treatment off `data-route` (chart / diagram / illustration / none) and `data-band` (the confidence band from [evaluation.md](evaluation.md)).
- **No inline styles** except genuinely dynamic values. Everything else is a token or a class.

Because the payload already carries the route kind, the band and the truncation flag, rendering is **one component parameterised by data** rather than a layout per item type. A per-item special case is a smell.

## Design tokens

Every colour, space, radius, shadow, font, easing and duration is a CSS custom property in `:root`, named **by purpose**, not by value:

- **Fonts** - a reading face and a tabular data face.
- **Space / radius / shadow** - a small named scale. The space scale does most of the work on a page that is mostly text.
- **Colour** - `bg` and elevated surfaces; `text` primary / secondary / tertiary; `accent`; the **confidence ramp**, one token per band, which is the only semantic colour set the digest needs; and the **series ramp**, `--series-1` to `--series-4`, which is categorical and carries no verdict.
- **Motion** - one ease and a short duration scale.

**The two colour ramps may not be swapped for each other.** The confidence ramp
is green, amber and red because those colours mean good, watch and bad. The
series ramp exists so a chart can tell four stages apart, and it deliberately
holds none of those three hues - a chart that borrowed the band tokens told a
reader that the slowest stage was the failing one. `--source-swatch-*` is not
the answer either: those are pale background tints for a monogram, not stroke
colours, and at 1px on a white card they are not visible.

Theming is override, not a second set of names: dark mode overrides the same token values. Where a utility framework is used, its theme **mirrors** these tokens so a utility resolves to the same custom property - one source of truth, not two - and a contract test asserts every non-exempt token has a mirror.

## Colour is one signal, never the only one

A confidence band carries a **word** as well as a tint. A route kind carries a shape or a position as well as a colour. This is a clarity rule for all readers, and it is also what keeps the page legible in a screenshot, in dark mode, and on a bad screen.

Accessibility *audit tooling* is a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a); labelled controls, semantic landmarks and visible focus are simply good building and are in scope.

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

**There is no chart library, on any surface - and a scale library is not a
chart library.** One chart library was carried for the console
between 2026-08-23 and 2026-08-24 on the argument that the owner required pan
and zoom. It was removed once that argument was checked: the pan and zoom are
implemented by the viewport control, with a keydown handler and four buttons,
and what the library actually drew was a second, smaller copy of a chart the
hand-written SVG already drew better. A charting library that outweighs the data
it draws has not earned its bytes, and a runtime dependency on a reading page is
a runtime dependency for nothing.

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
| Copied, not rewritten | How much of a normal summary is lifted word for word. |
| Time to write one | How long the machine takes on one article. |
| Model minutes | - |
| Failed | - |

Where each figure is read from is in
[../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md).

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

## See also

- [ui-shell.md](ui-shell.md) - the chrome that consumes these tokens.
- [digest.md](digest.md) - the item shape this vocabulary dresses.
- [evaluation.md](evaluation.md) - where the confidence bands come from.
- [principles.md](principles.md) - the beliefs behind the restraint.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the console projection.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the payload fields the styling keys off.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a (accessibility scope) and section 12 (published-site verification).
