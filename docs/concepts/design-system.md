# Design System

**Last Updated**: 2026-09-10

The visual vocabulary of the published surface: the state-driven styling pattern, design tokens, the restrained motion set, and the icon rule. This is the shared language the [chrome](ui-shell.md) and every [item](digest.md) speak; the concrete token file lands with the design-system code row, and this page fixes the vocabulary that row builds to. The bounds are owned by Jony ([../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md)).

**A rule is here if it binds a token or a bound the whole site resolves.** A rule about one named console panel - how a figure is worded, ranked, tinted or drawn there - is in [console-design.md](console-design.md), which reads this page's vocabulary and adds no token of its own.

The surface is small on purpose: a digest page, an item, and an eval dashboard. There is no application here - no session, no navigation tree, no state to lose ([vision.md](vision.md)).

**The architecture fixes how much surface there is. It does not fix how good that surface is.** Scope-restraint is inherited and not up for debate. Craft-restraint is a choice, and every instance of it needs an argument on the day it is made.

## Typography is the interface

This is a reading surface before it is anything else. Measure, leading, hierarchy and the space between items do more work here than any component will, and a digest that is hard to skim has failed before a single control is considered.

- **A reading measure on the text, and a fluid frame around it.** Long lines are where a skim turns into work, so the summary, the title and the key points are held to a measure. **The measure is a property of a text element and never of the shell.** Put it on the shell and the whole application inherits a paragraph's width: measured 2026-08-28, one `max-w-2xl` on the root layout capped every page at 624px and left 912px of a 1536px screen empty, including a console with five tables and six charts in it.
- **A hierarchy of exactly three levels** on an item - what it is, what it says, where it came from. A fourth level means something on the item has not earned its place.
- **Two faces at most**: one for reading, one for data (tabular numerals on the dashboard, so columns line up).

## The state-driven styling pattern

The DOM state is the single source of truth for the view. Nothing is styled imperatively: **state is reflected by toggling a class or a `data-` attribute, and CSS reacts declaratively.**

- **State classes** carry the look: `loading`, `empty`, `degraded`, `truncated`, `low-confidence`. `loading` is a global class in [../../frontend/src/styles/app.css](../../frontend/src/styles/app.css) rather than a component's scoped one, because the surface it belongs to switches every block on at once from one ancestor - see [the reserved box](console-design.md#a-console-panel-reserves-its-room-and-names-which-nothing-it-is-holding).
- **Data-attribute styling** carries variants: an item keys its treatment off `data-visual` (the visual's state - `rendered`, `render_failed` or `absent`) and `data-band` (the confidence band from [evaluation.md](evaluation.md)).
- **No inline styles** except genuinely dynamic values. Everything else is a token or a class.

Because the payload already carries the visual's kind and state, the band and the truncation flag, rendering is **one component parameterised by data** rather than a layout per item type. A per-item special case is a smell.

## Design tokens

Every colour, space, radius, shadow, font, easing and duration is a CSS custom property in [../../frontend/src/styles/tokens.css](../../frontend/src/styles/tokens.css), named **by purpose**, not by value:

- **Fonts** - a display face for headings, a reading face for body, and a tabular data face. The display face is self-hosted woff2, Latin subset, one variable file at 48,256 bytes; the body keeps the system stack, because that renders on the first frame at zero bytes and the body is what the reader came for.
- **Space** - `--space-0` to `--space-9` on a 4px base. On a page that is mostly text this does more work than any component will.
- **Type** - `--text-xs` to `--text-3xl`, each paired with its own `--leading-*`. A size without a leading is half a decision.
- **Radius** - five steps. Panel language needs a bigger corner than a chip does.
- **Elevation** - `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-panel`, plus `--color-surface-raised` and `--color-surface-sunken`. A page with one surface colour is a page where nothing is in front of anything.
- **Colour** - `bg` and elevated surfaces; `text` primary / secondary / tertiary; `accent`; the **confidence ramp**, one token per band, which is the only semantic colour set the digest needs; the **fill ramp**, `--fill-high` / `--fill-medium` / `--fill-low`, which is the same three meanings weighted to be filled rather than read; and the **chart ramp**, `--chart-1` to `--chart-8`, which is categorical and carries no verdict.
- **Tints** - `--tint-accent`, `--tint-info`, `--tint-good`, `--tint-warn`, `--tint-bad`, `--tint-neutral`. A panel takes the hue of what it means, at 7 to 9 percent in light and roughly double that in dark.
- **Gradients** - `--gradient-wordmark`, `--gradient-wash`, `--gradient-panel`. Chrome and identity only.
- **Frame** - `--frame-reading`, `--frame-console`, `--measure`, `--gutter`. Defaults live in the token file and `config/appearance.json` overrides them at build time ([config.md](config.md)).
- **Motion** - one ease and a short duration scale.

**The two colour ramps may not be swapped for each other.** The confidence ramp
is green, amber and red because those colours mean good, watch and bad. The
chart ramp exists so a chart can tell up to eight series apart, and it
deliberately holds none of those three hues - a chart that borrowed the band
tokens told a reader that the slowest stage was the failing one.
`--source-swatch-*` is not the answer either: those are background tints for a
monogram, not stroke colours, and at 1px on a card they are not visible.
`--series-1` to `--series-4` survive as aliases of the first four chart
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

### Movement colour reads the measure, not the sign

`--movement-good` and `--movement-bad` say a number went the way we wanted.
They are the third semantic pair, after the confidence ramp and the fill ramp,
and they exist because a sign is not a verdict: **a fall in `Time to write one`
is the machine getting faster, and a fall in `Summaries published` is a quiet
news day.** Until 2026-08-31 the console painted both from the sign, so the
improvement read as the loss.

- **Polarity is a property of the measure, declared where the measure is
 defined** - `lower-is-better`, `higher-is-better`, or `no-agreed-direction`.
 The console declares it in three places and nowhere else: `COLUMNS` on the
 Model route, `sideMeasures` in
 [../../frontend/src/lib/server/model-work.ts](../../frontend/src/lib/server/model-work.ts),
 and the `TargetSense` a bar was already built with. A component that decided
 its own is how two cards come to disagree about whether down is good.
- **A movement with no agreed direction paints neutral and says so**, in words
 on the card. Susan, 2026-08-31: a grey number a reader has to interpret is a
 fact withheld.
- **Zero is neutral on every measure.** Nothing moved, so there is no direction
 to be right about.
- **The pair is not the confidence ramp and may never equal it.** Green there
 means "it worked". A summary that got 3 percent slower is not broken, and
 painting it `--band-low` is how an operator learns to ignore `--band-low`.
 `ThemeConfig` in
 [../../backend/idhazh/contracts/appearance_config.py](../../backend/idhazh/contracts/appearance_config.py)
 refuses a movement value equal to a band value, and
 [../../frontend/tests/console-polarity.spec.ts](../../frontend/tests/console-polarity.spec.ts)
 refuses it again on the rendered page.
- **Same meaning, quieter voice.** Measured 2026-08-31 over the committed hex
 values, the light pair sits at 40.5 and 44.2 percent saturation against the
 confidence ramp's 66 and 70.6, and both still clear the 4.5:1 WCAG 2.2 SC
 1.4.3 sets for normal type.
- **Colour is never the only signal.** The sign is printed beside every
 coloured percentage.

The values live in `config/appearance.json` under `theme` and reach CSS through
`frame.generated.css` at build time - the same route the frame tokens take, and
for the same reason: a colour that has to be right on the first painted frame
cannot be injected from a layout.

Rejected: reusing the confidence ramp, which is the alarm-fatigue trade above;
and letting the sign alone decide, which is the defect the row removed. Owner,
2026-08-31.

### The source swatch is a fill, and its floor is 1.5:1

The eight `--source-swatch-*` values are the fill of the ring on an item's
leading edge. **Whether that ring is filled at all is the read mark**: filled
means unread, hollow means read. So the swatch has to be visible against
`--color-surface`, and until 2026-08-31 it was not - the dark set read 1.16:1 to
1.34:1 and the light set 1.18:1 to 1.28:1, which makes a filled ring and a
hollow one the same ring. All sixteen were re-tuned in place, hue kept and
lightness moved, and every one now reads at least 1.5:1.

**1.5:1, and not the 3:1 the fill ramp takes.** The bound above binds a fill
whose *colour* carries meaning; here the colour carries nothing, because the
publication is named in words on the same line and the monogram repeats it. What
carries meaning is the presence of the fill, which is an area rather than a hue -
and an area difference survives a cheap panel, sunlight and arm's length, which
is exactly what dimmer text and a lighter weight do not. Those two are one signal
twice: both are less ink, so they fail together.

The letters sit on the fill at about 4.9:1 in both themes, so raising the tint
cost the monogram nothing.
[../../frontend/tests/tokens.spec.ts](../../frontend/tests/tokens.spec.ts)
recomputes all sixteen ratios from the committed hex values, and checks the
number of swatches against the modulus `swatchIndex` divides by - an index with
no swatch behind it resolves to no fill, which on this surface reads as "already
read". Authority: Susan, 2026-08-31.

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
 the reader's own setting, or a `clamp` between two of those.

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

A confidence band carries a **word** as well as a tint. A visual kind carries a shape or a position as well as a colour. This is a clarity rule for all readers, and it is also what keeps the page legible in a screenshot, in dark mode, and on a bad screen.

Accessibility *audit tooling* is a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a); labelled controls, semantic landmarks and visible focus are simply good building and are in scope.

### Decorative colour and semantic colour are not the same rule

The rule above binds **colour that encodes meaning**. Read as a general ban on colour it says something it never meant, and for eleven months that is how it was read: no gradient was proposed on this surface, ever, and the reason was a rule that does not apply to one.

- **Semantic colour is doubly constrained.** A tint that tells a reader something carries a word or a shape as well, and it may never borrow the confidence ramp's three hues. This is the whole of the rule above.
- **Decorative colour is unconstrained.** Chrome, identity, a panel tint, an empty state, the wordmark, a page background. It encodes nothing, so there is nothing for a second signal to duplicate.

The line is drawn by the question "would a reader be wrong about a fact if this were grey?" A gradient on the site header fails that question, so it is decoration. A gradient running red at the bad end of a chart passes it, so it is semantic and is refused - a reader would read the hue as the verdict.

### Decoration that spells a word is still read

The wordmark is the one place the two rules meet. Its gradient encodes nothing,
so the paragraph above leaves it unconstrained - but the shape it fills is the
site's name, and a reader reads a name as type. So `--gradient-wordmark` takes
the one bound a decoration normally escapes: **every stop clears 4.5:1 against
`--color-bg` in both themes**, which is what WCAG 2.2 SC 1.4.3 sets for normal
text.

That bound was not being met. Measured 2026-08-31 over the committed hex values,
the three light-theme stops read 3.9803:1, 4.0195:1 and 2.9318:1 - a site name a
third of the way below its own floor, in the theme nobody was looking at.
Nothing had ever asked.
[../../frontend/tests/tokens.spec.ts](../../frontend/tests/tokens.spec.ts) now
asks on every run, from the committed values, so the spread is zero by
construction.

- **Five stops at 135deg, one set per theme.** Seven stops across roughly 200px
 of glyphs puts a stop every 28px and the middle three read as one band. Dark
 gets its own set rather than a tint of light's, because on a light ground a
 stop has to go down to be read and on a dark ground it has to go up.
- **`--wordmark-size` is `clamp(1.75rem, 1.2rem + 2.2vw, 2.75rem)`** - 28px on a
 360px phone, 44px from 1127px up. Not 52px: the header sits on every route,
 and 52px is 8 percent of a 640px phone screen spent before the first story.
- **Weight 300, and no second face.** The committed variable face covers 100 to
 900, so the weight axis is free. A display face bought for ten characters on
 one string is a second woff2 on every route (`CLAUDE.md` Rule #2).
- **No animation.** A cycling `background-position` is a loop rather than a
 response to anything the reader did, and `prefers-reduced-motion` is a hard
 kill-switch, so the effect would have to be designed twice. **What is lost is
 the moving shimmer**; what buys it back is the size, the five stops and the
 wider angle, which survive a screenshot, reduced motion and a battery.
- **The three wordmark scale tokens sit in the `:root` block, outside both
 themes.** A scale is not a colour. The tracking is `0.06em` rather than a
 pixel count so it holds at both ends of the clamp - a fixed 4px is 0.14em at
 28px and breaks the word into separate letters.

Authority: Susan, 2026-08-31. Rejected: a second geometric display face, on
bytes; and animating the gradient, on the reduced-motion cost above.

### A label's shape says whether it can be tapped

> **An outline means you can act on it. A tinted fill means it is telling you something.**

The reading page carries both, one line apart, and without this rule the second one to ship would have had to invent a look:

| | Outlined | Tinted fill |
| --- | --- | --- |
| Example | the topic pill row above a day | the desk chip and a lens chip on an item's eyebrow |
| Type | link or button | `<span>`, never focusable |
| Size | `--text-sm`, tap-height | `--text-xs`, no minimum height |
| Carries | a name and a count | a name only |

**One tint for every member of a label family, not one per member.** A lens chip uses `--tint-accent` whatever the topic is: the word carries the category and the colour carries only "this is a topic". Six hues to say what six words already say would collide with the confidence ramp and the chart ramp, and a `war` chip in a warn hue would read as a severity we never assigned. The seventh lens then arrives with its slot already filled and needs no colour decision - which is the point.

**The item's desk name joined that family on 2026-09-01**, and it is the case the rule was written for. It had been a hairline bullet and a word; it takes `--tint-accent`, the same padding and the same radius as the lens chips beside it, and it stays legible as a different kind of label through upper case and letter-spacing rather than through a second hue. It is not a link, and the tinted fill is what says so: the only thing a tap on it could do is what the filter panel on the same screen already does, and a 44px tap target does not fit a 12px line. What the reader loses is nothing they did not already have two inches above. Authority: Susan, plan row #16.

A tinted label is decorative under the rule above, because it repeats a word that is already there. It stays decorative only while it carries the word; a tinted chip carrying an icon alone would be semantic colour with no second signal, and is refused.

### Content on demand is a `<details>`, not a button

A section that leads with a shape and keeps its rows behind a control uses a native `<details>` and `<summary>`. **The reason is the element itself: it is keyboard-reachable for free and it says which state it is in without a second label.** A button plus a conditional block has to be given both, and a control that has to be given them is a control somebody can forget to give them to.

The script-less argument is the second reason and it is now narrower than it was. It reads: a page is complete before a script runs, so a conditional block does not hide the rows - it deletes them for a reader with no script, and the section then makes a claim the reader cannot check. That holds **unchanged on `/`, `/archive/`, `/404` and `/evals/`**, which are whole in the document and always will be. On a reading route it holds for the seed the document carries and not for the stories a browser fetches after it, because those are not there to be hidden either way ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)). The first reason covers every page equally, which is why it is the first reason.

The other shape is different and stays: `Show N more` on the failed-item list and the day list is a button that extends a list already on the page. Nothing behind it is hidden, so nothing is lost when the button is dead.

### No reader-facing surface scrolls sideways

> **A horizontal scrollbar is a control that hides its own contents.** The owner ruled it out everywhere on the reading surface, 2026-08-31.

It says nothing about how much is behind it, it is invisible until a pointer arrives, and on a phone it competes with the gesture that moves between pages. Hiding the bar with `scrollbar-width: none` is strictly worse: the control still hides the contents and the only hint that more exists is gone.

Two shapes replace it. A row of variable-width labels **wraps**, and the overflow past a configured count folds into a `<details>` reading `+N more` - the pill row is the case, with the count in `digest.topic_pills_max`. Which items fold is decided by a count at build time and never by measuring the row: every page here is prerendered, so a row that measures itself is wrong until a script runs. A grid guards its own minimum with `minmax(min(var(--auto-grid-min), 100%), 1fr)`, because a bare minimum is a demand for room the container may not have.

### A control only sticks where it is one band

> **A panel that follows the reader down the page must be one band tall at the width it sticks at.**

The filter bar is the case. It sticks from `frame.breakpoints_px[1]` (1024px) up, where the pills sit on the left and the field on the right in a single band. Below that it can run to several wrapped lines plus a field, and a control holding a third of a phone screen for the whole scroll is screen the reader paid for. A media query cannot read a custom property, so the number is written twice - in `config/appearance.json` and in the component - which is the one place this duplication is unavoidable and is already true of the item's side rail.

**This rule is why the day's aside stands beside the stream and not beside the day's controls.** The first arrangement of the two-column day put the leads in column two from the top of the page, which narrowed everything below them to 896px - and at 896px the filter bar's six pills wrap under its field, so a two-band panel then followed the reader down the page. The controls keep the whole content box and the aside starts level with the first story.

### The reading page spends its width in five named zones

> **No zone is a pixel count.** Every column the reading page draws beside its prose is a `rem` knob in `config/appearance.json`, so it grows with a reader who set their browser text larger.

| Zone | Token | Default | Drawn from |
| --- | --- | --- | --- |
| the day's time rail | `--zone-time` | `5.5rem` | the small breakpoint |
| the source mark | `--zone-mark` | `1.75rem` | every width - the read state has to stay beside the title it qualifies |
| the card | `minmax(0, 1fr)`, text at `--measure` | `68ch` | every width |
| the item's footer rail | `--zone-rail` | `14rem` | the middle breakpoint, and it retires at the wide one |
| the day's aside | `--zone-aside` | `18rem`, sticky | the wide breakpoint |

**A phone gets no time rail column, and that was measured rather than assumed.** A 360px screen leaves 328 CSS px of content box; the item already spends 40 on the read mark and its gap and 32 on its own padding, so a 3.5rem rail plus its gap left the summary **186px** - about 25 characters, with `Interconnector` broken across two lines in the title. Below the small breakpoint the marker is a rule across the top of its group instead, which costs the reading column nothing and reads as a section heading. What the reader loses is the label sitting level with the story it opens; what they get back is 70px of every line.

**The frame's content box holds a measure plus exactly one trailing column.** Measured 2026-09-02 at 1536px, that box is 1,216px and the item filled all of it, while the summary used 659.81 - so 230.19px stood empty beside the prose on every story. What that buys is one column of at most 27.1rem once the measure and the mark are paid for. Both the item's rail and the day's aside want it, and keeping both leaves the summary 570px, so the day's column wins at the width it appears and the item gives its rail back. The footer then returns to where the item's own split put it, under the summary it is a claim about.

**The measure never moves.** A wide card holding a 68-character paragraph is not wasted space; a wide paragraph is what the measure exists to prevent, and widening it was refused before the layout was chosen. What the aside spends is the space the measure does not want.

**A `rem` zone is only a `rem` zone if something checks.** `14rem` and `224px` look identical at the default font size and diverge the moment a reader changes it, and no screenshot tells them apart. `frontend/tests/item-zones.spec.ts` reads every zone's used width with the root font size at 16px and again at 22px and fails unless each one scaled by 22/16 - measured on its own build, the mark went 28 to 38.5, the item's footer rail 224 to 308, the aside 288 to 396 and the time rail 88 to 121. It prints both numbers in the failure, so the assertion cannot pass on a layout it never measured. Numbers and method: [../reference/measurements.md](../reference/measurements-site.md#what-the-reading-page-does-with-a-wide-screen-2026-09-02).

**The hairline behind the rail is what makes a column of times one axis.** It runs the height of the stream and each marker knocks a hole in it by painting its own ground - so the eye reads a single line with labels on it rather than a stack of separate numbers. That is the only place on the reading surface a rule runs vertically, and it earns it because the thing beside it is ordered. It is a column affordance, so below the small breakpoint it turns: the marker becomes a rule across the top of its group with the time under it.

### A chart's column is set by what the chart was drawn at

An item's visual has no column of its own, and the reason is arithmetic rather than taste. The committed charts are 825 x 437px SVGs carrying 25 labels at 10px. Across the card body at 890px those labels draw at 10.8 CSS px; in a 20rem column they draw at 3.9. That is the same rule as [the Sankey above](#a-diagram-a-narrow-column-cannot-hold-becomes-a-list-never-a-smaller-diagram) - a chart engine scales its marks with the container and its type with nothing at all - so the figure keeps the card's width until the render spec is handed the width it will occupy. `digest.visual_side` stays unread until then, because a knob whose only setting draws an illegible chart is worse than a knob nothing reads.

**Reserved is not the same as unowned.** `config/appearance.json` declares `digest.visual_side` and nothing else does; `config/idhazh.json` carried a second copy saying `above` until 2026-09-05, and the frontend's fallback merge quietly dropped it, so a knob edited in that file did nothing. Both the committed value and the contract default now read `trailing`, which is what the card draws - title, summary, reader note, then the figure. A default naming a position no page renders is the wrong answer waiting for the reader who first switches this on.

What the figure did give back is height. A fixed 16:10 box reserved space the chart never used: an 825 x 437 chart inside an 890 x 556 box left 85px of empty band above and below it. An SVG carries its own width and height, so `width: 100%; height: auto` reserves the right box from the markup and still cannot shift the page as the image loads.

**And since 2026-09-05 the drawing takes its colours from these tokens like everything else on the card.** A story holds the SVG itself rather than a link to it - the build puts it there for the stories a prerendered document carries, and the browser fetches it for the rest - so the page's stylesheet reaches the marks: the bars take `--chart-1`, the axis type takes `--color-text-secondary`, the ticks and the axis line take `--chart-axis` and the grid takes `--chart-grid`. Nothing was added to the file to make that work - a presentation attribute is the lowest priority in the cascade, so `fill="#000"` loses to any rule. What the drawing brought with it, and what it cost, are in [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md#a-story-carries-its-drawing-so-the-drawing-can-read-the-page).

### A control that needs a script is not left on the page without one

> **A dead input that swallows typing is worse than no input.**

Every page here is rendered whole before a script runs - the stories past a reading route's seed are the one exception, and they are content rather than a control - so a control that only works afterwards has to say so. The shape is a `<noscript>` block holding a `<style>` that hides the scripted controls by attribute, and one sentence, hidden by `hidden`, that the same rule un-hides. Nothing is conditionally rendered, so hydration has nothing to reconcile and there is no flash.

Two details make it work rather than look like it works. The rule inside `<noscript>` is unscoped, and a Svelte scoped class rule outranks it - `.field.svelte-<hash>` is specificity (0,2,0) against (0,1,0) - so the element carrying the attribute must not take a `display` of its own; the layout goes on a child. And the fallback sentence uses `hidden`, which the author rule beats without an `!important`. The trap and its symptom are in [../reference/agent-notes/browser.md](../reference/agent-notes/browser.md#svelte).

What survives without a script is the part that was never scripted. On a day page the topic pills are links to prerendered routes, so a reader with no script still reaches every desk; on the archive they are buttons over a list a script fetched, so they go with the field and the page keeps its prerendered day list - the recent days as rows, and every older day inside a native month disclosure that opens with no script at all.

`frontend/tests/layout-overflow.spec.ts` is the memory: `document.documentElement.scrollWidth <= document.documentElement.clientWidth`, on every reader-facing route, at 360, 801 and 1536 CSS px, in both themes. Measured before the rule landed, `/archive/` reported 368px of document in a 360px viewport in both themes, from an `--auto-grid-min` of `22rem` inside the 328px a 360px screen leaves after its gutters.

The console is not covered by that spec. It carries live scroll containers of its own and a sibling plan holds those routes; `frontend/tests/console-frame.spec.ts` asserts the same property there, per element.

### A diagram a narrow column cannot hold becomes a list, never a smaller diagram

A chart engine scales its marks with the container and its **type with nothing at all**. The chart-arm flow is the case: its Sankey labels sit outside the nodes, in a fixed 170-pixel column, at a fixed 12-pixel size. Measured 2026-09-01 in Chromium on the built console, that column is 12 percent of a 1,376px SVG at 1440 and **52 percent of a 328px one at 360**, so the four stages divide 158 pixels between them and their labels print over each other.

| Viewport | Flow SVG | Label pairs overlapping | Worst overlap |
| --- | --- | --- | --- |
| 360 | 328 px | 3 | 59.1 px |
| 390 | 358 px | 3 | 56.2 px |
| 640 | 589 px | 2 | 17.1 px |
| 690 | 635 px | 1 | 1.8 px |
| **700** | 644 px | **0** | - |
| 1440 | 1,376 px | 0 | - |

Two answers were refused before this one. **A horizontal scroll** destroys the diagram's whole value - seeing every branch at once - and hides the small branches off screen. **Smaller type** was already measured and rejected once, when a one-line label ran 280px into a 246px column pitch; the reply then was two lines, and two lines is what the table above measures. Neither is available at 360, because the label column does not shrink with the frame at any font size a reader can use.

So below `48rem` the same numbers are a **stepped list**: one row per stage with its count and its share of everything that reached the arm, and the branch that left it indented under it. The breakpoint is the one the console page already stacks at, and it clears the measured crossing by 68 pixels.

**One call builds both shapes.** `chartFlow` returns the option and the steps together, so the list and the diagram cannot report two different flows - which is the failure a fallback invites and the one nothing on screen would show.
`frontend/tests/console-flow.spec.ts` reads every count off the diagram at 1440 and off the list at 390 and compares the two sets, and it checks on the page that what leaves a stage is what arrived at it.

**Only one is drawn at a time.** Two shapes of one flow on one screen is two answers to one question, and a reader who finds them has to work out whether they agree.

Authority: Jony, plan row #13. The geometry is measured in a browser and never reasoned about, which is the rule that produced both this table and the two-line labels before it.

## Sufficiency is a gate, not a taste

A surface fails review for being **insufficient**, exactly as it fails for being over-built. This is stated because the opposite was: every review persona this project had was a veto, so the surface converged on the minimum that passed all of them, and nobody's job was to say it was not enough.

The checks, applied to any reader-facing surface:

- **Does it use the screen it is on?** Measured 2026-08-28: the digest used 40.6 percent of a 1536px viewport and had two responsive breakpoints in the entire site, one of which changed padding.
- **Does it separate figure from ground?** A page with one surface colour and no elevation is a page where nothing is in front of anything.
- **Is there one thing the eye lands on first?** If everything is the same weight, the page has no order to read it in.
- **Does it look like it was made this year?** Not a matter of fashion. A surface that looks abandoned is read as abandoned, and the judgement transfers to the summaries.

A surface that fails one of these ships only with a `## Design rationale` entry saying why. `CLAUDE.md` section 9 carries the Definition-of-Done line; Susan ([../../.github/agents/susan.agent.md](../../.github/agents/susan.agent.md)) rules them.

**And a veto costs something.** A ruling that removes must name what the reader loses. "Remove before adding" is a good instinct and a bad rule when it is free: a removal that states only what was removed is not a ruling and does not bind ([../agents/guardrails.md](../agents/guardrails.md)).

### Height is not the target; the page somebody lands on is

The console chart-craft plan opened by complaining that `/console/` was too tall on a phone - 16,385 px, with the band taking 63 percent of the first viewport and the first chart a screen and a half down. Twenty-six rows later it is **15,131 px, 7.7 percent shorter**, and the other two console routes are **32 to 37 percent taller** because they gained a doubt list, a cost distribution, a context chart, peak memory and three latency plots. Across all three the console grew 13.2 percent on a phone.

That is the sufficiency gate and the veto working together rather than one beating the other. **A surface is not judged by its total height.** It is judged by what the first viewport says, what a reader has to scroll past to reach a figure, and whether the figure is there at all. Cutting the band and capping the failure list bought the first two; the panels behind the other two routes are the third, and shrinking them to hold a height number would have been the failure the sufficiency checks exist to catch. Numbers and method: [../reference/measurements.md](../reference/measurements.md).

## Motion vocabulary

There is almost no motion here, and that is the correct amount. This is a page a reader skims, not a thing they operate.

- **`transform` and `opacity`, plus the paint-only properties.** A colour, a border colour and a shadow change without moving anything, so they may ease - `RankedList`, the topic pills and the theme control already do. Never animate a layout-triggering property.
- **`prefers-reduced-motion` is a hard kill-switch** - a media query that zeroes durations, and removes a transform an interaction brings on rather than making it instant. A zeroed duration shortens a movement; it does not remove one, so a 2px rise on hover becomes a jump in one frame and a reader who asked for stillness still sees it move. The reset names the elements that take an interaction rather than every element, because a transform that **positions** something - a rotated axis title, a chart readout centred on its own width - is not motion and a blanket reset drops both on the floor.
- **A moving gradient is the case a zeroed duration gets wrong, not slightly but completely.** `animation-duration: 0.01ms !important` on `*` does not stop the sweep across a skeleton block - it FREEZES it, and a frozen sweep is a bright band across the block that nobody chose and that says nothing. So a reserved block loses the gradient outright under reduced motion and stays a flat tint. It wins on specificity, `(0,2,0)` against the blanket's `(0,0,0)`, and the proof is a computed style read in a browser that asked for stillness rather than an argument about the cascade.
- The whole named set: `fadeIn` (content arriving), `shimmer` (skeleton while a payload parses), `toastIn` (the rare notice). Anything beyond these needs an argument. `shimmer` has exactly one caller and it is the console's reserved box; it is not available to a reading page, where a skeleton would draw boxes over prose a reader is already reading.

Nothing on the reading path waits on a network for its first frame, so **there is no excuse for a spinner.** Nothing on the operator path gets one either, and there the reason is different: the console has a dozen waits at once and an operator who can act from the first frame. A spinner suits one wait, a blank page and a person who can do nothing until it stops - and none of those three is true here. Authority: Susan, accepted as owner decision D3, plan row #12.

**Three things wait, and none of them gets a spinner.** A reading page fetches
the stories past its seed. What it shows meanwhile is nothing at all, because
the frame the reader already has is readable; past `ui.payload_slow_ms` it is
one sentence, and a fetch that fails is one sentence and a retry. A skeleton
there would draw boxes where a reader is already reading.

And the archive's search downloads a 43 MB encoder the first time a
reader uses it. What it shows meanwhile is bytes as type, taken from the
library's own count of what has arrived - a measurement, not an animation. When
the weights land that count goes blind, because the runtime behind them reports
nothing to anybody, so the line stops printing numbers and prints a word. A bar
that keeps moving on no measurement is a bar that is making it up.

The console is the third and it is the one that gets the skeleton, because it is
the only surface here whose panels have nothing at all to show until a fetch
lands. What it draws is [a reserved box with the axis frame in it](console-design.md#a-console-panel-reserves-its-room-and-names-which-nothing-it-is-holding).

**A day payload gets no byte readout, and that is the same rule read the other
way.** A compressed response reports its compressed length, so a bar drawn on
one would print precision the number does not carry - which is a bar making it
up, exactly as above. The encoder is different because the library counts real
bytes and because 43 MB is worth naming before a click.

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

**The reading stream draws exactly one glyph, and it is `clock-alert` on the day's time rail.** It marks the story whose printed clock is ours rather than the publisher's - the feed's own time was absent or rejected as impossible. That is the one case where a reader scanning a column of times would otherwise read a number from a different clock as a feed time, and since 2026-09-06 the mark is the only thing that says so: the rail prints digits, so the words that used to carry it are gone. Nothing else on the rail takes a mark: a story with no stamp at all prints nothing, and a merely old story needs none because the date in front of its clock says it. Ten of the 4,713 committed stories are in the marked state, measured 2026-09-02, which is why it needs a mark - a reader has no way to spot two in a thousand.

**The set is closed and it is checked in both directions.** `frontend/tests/icons.spec.ts` fails on an icon nothing draws and on a reference to an id that does not exist, so a set cannot rot silently either way. The first of those is not theoretical: the set was cut from 29 glyphs to 15 on the day it landed, because the lens and event taxonomies exist in `config/taxonomy.json` and no surface renders them. Those thirteen marks wait for a surface rather than shipping against one that might arrive.

Source is [Lucide](https://lucide.dev) under the ISC licence; only the icons in use are committed, as unmodified source SVG, and the sprite module is generated from them. Provenance and the add procedure are in `frontend/src/lib/icons/PROVENANCE.md`.

### Design rationale

**Icons ship, and the earlier refusal was wrong (owner, 2026-08-29).** The rule used to say "keep the set tiny: an external-link mark, a confidence mark", which in practice produced two inline SVGs and no system at all - the exact state the icon rule was written to prevent. What was right in the old line was the refusal to put a decorative mark beside a headline, and that survives above as a narrower rule.

**Measured cost, 2026-08-29 on this tree.** Fifteen glyphs, 2,128 B of marks, and the generated module reaches every route because a component names an icon by id and a lookup on a dynamic key cannot be tree-shaken: `/` +1,897 B, `/404` +1,771 B, `/<date>/` +1,900 B, `/archive/` +1,833 B, `/console/` +1,404 B, `/evals/` +1,775 B gzipped. `/evals/` also crossed its prerendered-HTML ceiling by 185 B and the ceiling moved from 2,730 to 2,979.

**The rejected alternative was an inline sprite.** It costs no JavaScript at all, which is better, and puts roughly 700 B of gzipped markup into every prerendered document, which is worse where it lands: `/404` had 37 B of headroom under a ceiling whose whole purpose is keeping the error page tiny. The bytes go where there is room for them. If the JS cost ever matters more than the 404's ceiling, this is the trade to revisit, and the numbers to revisit it with are here.

## Charts are static first, enhanced only when interaction earns it

A chart on an item is rendered at build time from a specification and shipped as
an asset ([digest.md](digest.md)). Every chart on the dashboard is hand-written
markup over a committed CSV or the published telemetry projection.

**No chart library on a reader's route.** An item's chart is already an asset, so
an engine there is a runtime dependency for nothing. That half is settled.

**The operator surface is a separate question, and it was answered wrongly
twice.** An engine was carried for pan and zoom between 2026-08-23 and
2026-08-24, then removed because the viewport control already did that with a
keydown handler and four buttons. On 2026-08-29 the same blanket ban was
re-argued from a `/console/` weight four and a half times out of date, and the
owner overruled it. What replaces the blanket is not another blanket in either
direction. Any library adopted for the console must (1) render SVG, not canvas,
so `tokens.css` stays the only place a colour is decided, (2) render server-side
at build time, so the page is complete before any script runs, and (3) carry a
measured gzipped cost recorded next to the decision.

Measured 2026-09-01 on five builds of `origin/main` at `8d658de`, and unmoved
across twenty-six rows of chart work: registering only the chart types in use,
the engine is a lazy chunk of **192,029 B gzipped** (567,839 B raw) on every one
of the five. The number that decides affordability is not the chunk but what
opening the console costs, and that moved **1,854 B**, from 69,622 to 71,476.
About 40 B of that is the toolchain rather than the change. What importing the
package whole would have cost, what deleting the legend component bought, and
the stale figure this record replaced are in
[../archive/measurements-2026-08.md](../archive/measurements-2026-08.md).

Three rules came out of taking those numbers, and they cost more than the
numbers did. **Identify the chunk by content, never by size** - the encoder
chunk beside it is bigger, so "the largest chunk" finds the wrong file. **Read
the gzip level-9 byte, not the bundler's log line**, which uses a different
compressor and reads about 2 KB high. And **a bundler probe is not the
artefact**: the figure that justified adopting the engine was taken with a
standalone script, and the thing that shipped read more than twice it. Adding a
chart type means editing
[../../frontend/src/lib/charts/core.ts](../../frontend/src/lib/charts/core.ts),
and the whole point of it being a file somebody has to edit is that they measure
it in the same commit - the record went 25 percent stale in one day when six
shapes were added and nobody re-measured. No reading route imports any of it,
and [../../frontend/tests/charts.spec.ts](../../frontend/tests/charts.spec.ts)
fails the build if a page ever preloads it.

What a chart may take from a library is the arithmetic. `d3-scale` and
`d3-array` map a domain to pixels and choose the tick values; they own no
element, no canvas and no theme, and the marks, the SVG and the prerendering
stay ours. `.nice` and `ticks` are the part a hand-rolled axis gets wrong,
and getting it wrong shows as an axis labelled 0, 37, 74 that nobody can read a
value off. The two are 20.5 KB together, and nothing on a reader's route imports
either one.

**A chart draws in CSS pixels at the width it occupies.** A `viewBox` is a scale
factor, not a unit: four charts that each pick their own and then stretch to the
column render the same `font-size` at four sizes. Measured 2026-08-25 at a
1057px window, one console page put `font-size="10"` on screen at 4.5px in one
panel and at 16.6px in the next. The width comes from one place -
[../../frontend/src/lib/charts/frame.ts](../../frontend/src/lib/charts/frame.ts)
- and the server draws at `console.chart_width`, so the page is complete before
any script runs. A canvas cannot inherit a custom property inside the drawn
pixels, so a canvas chart resolves tokens in JavaScript at mount and after every
theme change - which ends the token file being the only place a colour is
decided.

## A figure on a chart is the article's or it is ours, and it never has to be guessed

Every number a reader reads off an axis is one of two things and no third. It is
the article's own characters, cut at a span anybody can re-slice; or it is
arithmetic we performed over those characters, carrying a chain back to every one
of them. `docs/architecture/publishing/visuals.md` holds the contract that makes
that true. What binds a surface is the consequence of it.

- **A converted figure is drawn in its converted form and never redrawn over the
 original.** `4.2 kt` and `4,200 t` are one quantity, and putting both on one
 page is two answers to one question. The axis carries the form the chart is
 drawn against.
- **The accessible description carries what the article printed, where the two
 differ.** Nothing is lost by a conversion - the element still holds the
 characters - so the description is where a reader who wants the source figure
 is given it, rather than a second visible label competing with the first.
- **A figure we computed is never presented as a figure the article stated.** A
 percentage that is a share of the slices, or a bar that is a count of values in
 a range, is what the caption says it is. This is the same rule as
 [a console figure says what it counts, in words](console-design.md#a-console-figure-says-what-it-counts-in-words),
 read from the reader's side.
- **A chart with nothing to draw draws nothing.** A mark whose figure resolves to
 neither of the two ways is not softened, greyed or labelled "unavailable" - the
 item publishes with no picture, which reads exactly like the nine items in ten
 that never earned one.

Shortening a number is a separate act and is not on this list: `2,000,000` drawn
as `2M` is the same quantity in fewer glyphs. It is bound by the legibility floor
like any other drawn label, and making a number shorter is not a licence to set it
smaller.

## Design rationale

**Three sentences were struck on 2026-08-29, and the reason is one mechanism
rather than three mistakes.** This page opened with "Restraint is not a style
choice on this project; it falls out of the architecture", [ui-shell.md](ui-shell.md)
and [vision.md](vision.md) said the operator surfaces "earn no design budget",
and the reading measure was written as a property of the shell. All three are
defensible sentences and all three are the same error: an architectural
constraint restated as a design value. Rule #1 constrains what may *execute* at
read time and says nothing about what may be *drawn* - a gradient, an elevation
scale and a self-hosted face cost a reader nothing at read time and the runner
nothing at build time. But a constraint stated as a value stops needing a
justification, so every additive proposal had to argue against the project's own
doctrine while every subtractive one was pre-approved. The measurements that
settled it are at the sufficiency gate above; the rejected alternative was
softening the three sentences rather than striking them, refused because a
softened absolute is still read as an absolute. Owner, 2026-08-29, over Jony's
prior ruling.

**The token list on this page specified a shadow scale and a space scale that
were never built.** That is the quieter half of the same failure: the doctrine
was right and the implementation stopped short.

**Sufficiency became a gate because the review roster was six vetoes and no
demand.** Jony removes, Fowler deletes, Carmack refuses on budget, Reader and
Editor report. Nothing asked whether the result was good enough to be worth a
stranger's attention, and a system of pure vetoes converges on the minimum that
passes every veto. Giving Jony the demand mandate as well was rejected: one head
holding both "remove before adding" and "this is not enough" resolves to the veto
every time. Susan was added at a distinct altitude instead, and a veto now has to
name what the reader loses. Owner and Fowler, 2026-08-29.

**Driving the look from fields the payload already carries** - visual kind, band,
truncation - rather than from per-item styling is what keeps the surface one
component instead of many, and it means a new visual kind or band arrives with a
slot already waiting. The rejected alternative, bespoke treatment per item type,
produces a page that must be edited every time the pipeline learns something new.
Jony.

**Keeping the motion set to three named animations is a deliberate under-build.**
A reading surface that animates is a reading surface that interrupts. Jony, with
Reader as the check.

**Taking `d3-scale` and `d3-array` while still refusing a chart library on a
reading route is one distinction, not two rules.** A chart library owns the
element, the redraw and the theme, which is why the last one drew a second copy
of a chart that already existed. A scale library returns a number. The rejected
alternatives were all libraries that draw: `echarts` (canvas), `@observablehq/plot`
(needs a DOM shim to prerender), `chart.js` (canvas), `uplot`, and a component
library, which is worst of all when every chart on the surface is bespoke. A CDN
was rejected on top of all of them: the HTTP cache is partitioned per site, so
the shared-cache argument is dead, and the repo's `script-src` allows `self`
only. "Fix the units without the dependency" was rejected last, because `.nice`
and `ticks` are exactly the part hand-rolling gets wrong. Jony and Carmack,
2026-08-25, owner accepted; overruled for the operator surface only on
2026-08-29, on the three conditions in the chart section above.

Three lessons from that reversal are recorded because they are more transferable
than the ruling. **A byte count is a measurement and goes stale like any other** -
a design argument leaning on a number someone took months ago has not met Rule
#10. **An argument that generalises from the worst implementation of a thing is
not an argument about the thing** - "a canvas cannot inherit a custom property"
is true of canvas and false of the SVG renderers those libraries also ship. And
**check whether the thing a dependency is supposed to buy is already built**: the
case for the engine was that it buys a pointer readout, and `frame.ts` already
had one covering mouse, pen, touch and keyboard - two of the four charts were
simply never wired to it.

### The footer ships as one row of links, and it fails two sufficiency checks

**On 2026-09-09 the footer lost three of its four blocks and gained nothing.**
What is left is the three links: Archive, Console, Source code. This entry
exists because that surface fails the gate above, and `CLAUDE.md` section 9 says
a surface that fails ships only with the reason written down.

Two of the four checks fail. **Nothing lands first** - three links of one weight
in one row have no order to be read in. And **it does not look like it was made
this year**: a bare link strip under a hairline is the plainest footer a page
can have, and it is the exact "thin, cold, unloved" shape Susan exists to catch
([../../.github/agents/susan.agent.md](../../.github/agents/susan.agent.md)).
Measured 2026-09-09 in Chromium at 1280x900 on the canary build, the same on all
five routes that have a footer: the block is **102 px tall and holds three
links**, against 3 blocks and 2 paragraphs before. The other two checks pass -
the footer uses the width of the frame it sits in, and the top rule plus
`--color-text-tertiary` still hold it away from the reading surface.

**What the reader loses, named rather than implied.** The build line said which
commit produced the page, so a reader who thought something looked wrong could
open that commit; there is now no way to tell one build from another from the
page. The verification sentence - "Every summary is checked against the article
it came from" - was the only place that told a stranger why an item is allowed
to say it is unsure, and Reader
([../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md))
argued to keep it beside the day. The retention promise is now stated on
`/archive/` alone, so a reader on a dated page is told nothing about what may
later be deleted.

**Why it ships anyway.** Every one of those sentences is read off the newest day
or off the build, and the footer is on every page - so each rewrote the bytes of
every document on the site whenever anything published, leaving a page a reader
already holds stale for a reason that is nothing to do with what it says. The
measurement, and the alternatives the owner refused, are in
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md).

**What would fix the two failed checks costs nothing this row cares about,** and
it is written here so the next person does not have to rediscover it: the footer
needs one block that does not come from a day or a build. A sentence about what
the site is, set above the links at the heading step, would give the eye
somewhere to land and give the strip a reason to be a footer rather than a
leftover. It is a fixed string, so it moves no bytes on any later run.

## See also

- [console-design.md](console-design.md) - the operator half: how a console figure is worded, ranked, tinted and drawn.
- [ui-shell.md](ui-shell.md) - the chrome that consumes these tokens.
- [../../.github/agents/susan.agent.md](../../.github/agents/susan.agent.md) - who rules the sufficiency checks, and why the roster needed a demand side.
- [../agents/guardrails.md](../agents/guardrails.md) - the authority table, and the rule that a veto must name what the reader loses.
- [digest.md](digest.md) - the item shape this vocabulary dresses.
- [evaluation.md](evaluation.md) - where the confidence bands come from.
- [principles.md](principles.md) - the beliefs behind the restraint.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md) - the console projection.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the payload fields the styling keys off.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a (accessibility scope) and section 12 (published-site verification).
