# Design System

**Last Updated**: 2026-10-12

Shared rules for typography, layout, colour, motion and controls. [Console design](console-design.md) owns panel-specific presentation; [appearance configuration](config/appearance.md) owns tunable values.

New designs, charts and visuals render in the browser. Do not add prerendered data surfaces. The console uses d3, with no ECharts engine or server-side chart renderer. Its remaining private build-time inputs are not precedents for new panels; [console delivery](../architecture/publishing/console.md#rendering-direction) names that boundary.

## Typography is the interface

- Constrain prose, not the application shell. A dashboard may use the frame's width while paragraphs retain a comfortable measure.
- Keep an item's hierarchy to title, summary and provenance. Use the configured display face for titles and the reading face for prose; data uses tabular numerals.
- Keep article type readable on phones. Reduce columns before reducing prose size. Pair each size token with its leading token.
- Edition headers and the leading-story index are unboxed. Story cards retain their surfaces and edges.
- Use the configured display-face toggle and type scale. Do not add a font for a single decorative treatment.

## The state-driven styling pattern

Reflect state through classes and `data-` attributes; let CSS render it. Loading, empty, degraded, truncated and low-confidence states must be explicit. Use payload metadata rather than a bespoke layout for each item.

Inline styles are for genuinely dynamic values such as coordinates or computed widths. Fixed appearance belongs in tokens and classes.

## Design tokens

[tokens.css](../../frontend/src/styles/tokens.css) and `config/appearance.json` own colours, type, leading, spacing, radius, elevation, frame widths and motion. Name tokens by purpose. Keep non-colour scales outside theme blocks; tune both themes explicitly.

| Token family | Meaning |
| --- | --- |
| `--band-*` | Confidence expressed as readable text |
| `--fill-*` | The same status meanings expressed as filled marks |
| `--chart-*` | Distinguishable categories, not good/bad verdicts |
| `--movement-*` | Whether a change improved or worsened a measure |
| `--source-swatch-*` | Source identity and the read-state ring |
| `--tint-*` | Restrained surface treatments |
| `--type-*` | The family of a column's data type, as readable text |

Do not substitute one family for another. A categorical series colour must not imply confidence. A source tint must not become an unreadable chart stroke.

### The reading item is a surface, and it does not float

Use the item surface, configured corner radius and a hairline. There is no shadow at rest. Hover and keyboard focus may add the configured shadow and accent edge, but the card does not rise: its title is not itself a link. Preserve a visible edge in both themes.

### A fill is not a text colour

Use status fill tokens for solid marks and band tokens for text. The fill's contrast against its surface is at least 3:1, below 4.5:1 in light and below 9:1 in dark. Existing surface tests check these bounds; do not replace the text ramp to adjust a fill.

### Movement colour reads the measure, not the sign

Declare polarity with the measure: lower-is-better, higher-is-better or no-agreed-direction. Zero and directionless changes are neutral. Print the sign and explain a neutral direction where needed. Movement colours are distinct from confidence colours: slower does not mean invalid.

### The source swatch is a fill, and its floor is 1.5:1

Filled means unread; hollow means read. Keep every source swatch visible against the item surface at 1.5:1 or above. The source is also named in words, so hue alone carries no identity requirement.

### A value the scale cannot hold does not go on the reading surface

Do not use arbitrary bracketed utility values or authored pixel sizes on reading routes. Use tokens, relative units, fractions and measured dynamic values. A one-pixel hairline and media-query breakpoints checked against configuration are the defined exceptions. Shared components follow the reading rules when a reading route uses them.

## Colour is one signal, never the only one

Pair semantic colour with words, shape or position. Keep labelled controls, semantic landmarks, visible focus and keyboard access. Follow `CLAUDE.md` section 0a for audit-tool scope.

Decoration may use colour without encoding a fact. A decorative wordmark still has to be readable: every gradient stop clears 4.5:1 against the page background in both themes. The wordmark does not animate.

### A label's shape says whether it can be tapped

Outlined labels are links or buttons; tinted labels are non-focusable information. Give a label family one tint rather than inventing a verdict for each member. The item's desk and lens labels use the same family.

Primary controls use tap-height targets. Secondary publisher links in a compact item footer currently use the footer's line height; this is a smaller phone target, not the standard for a new control bar.

### Content on demand is a `<details>`, not a button

Use native disclosure for content already present but hidden. Use a button when an action extends an existing list. Preserve keyboard operation and expose state without relying on a second handwritten control protocol.

### No reader-facing surface scrolls sideways

Wrap variable-width labels and use a configured disclosure count for overflow. Do not hide a horizontal scrollbar and leave the hidden contents behind it. Grids must allow their minimum track width to fit the available container.

### A control only sticks where it is one band

A sticky control occupies one band at the width where it sticks. Below that breakpoint, wrapped controls flow with the page. The console's route strip may scroll internally to stay one row; this does not permit sideways scrolling on reading pages.

### The reading page spends its width in four named zones

Use the source mark, measured prose, optional item footer rail and optional day aside. Zone widths are configured relative units, not pixel substitutes. At a width where the day aside appears, return the item footer beneath the prose rather than squeezing both trailing columns beside it.

### The measure is one block, not one class per line

Apply `--measure` once to the block holding title and summary, at the prose size. A `ch` width applied separately to different fonts or sizes produces different edges. Keep figures outside that prose cap. Verify zone widths also scale when the root font size changes.

### A chart's column is set by what the chart was drawn at

Draw against the actual content width in CSS pixels. Do not shrink a wide drawing until its labels are unreadable. Reserve the figure's dimensions to avoid layout shifts; choose a simpler layout when the available width cannot hold its labels.

Every SVG text string on a reader chart must resolve to at least `--text-xs`,
with one drawn unit equal to one CSS pixel. The reader browser gate checks
this on the canary day at 390 CSS pixels, including the figure's content width,
mark readings and stable geometry after navigation and reload. Narrow and wide
geometry checks stay in the logic tier. This floor does not govern console
charts or repeat the visual validator's mark-count limits.

### Every fact a drawing shows is reachable without a pointer

The accessible description and visible marks come from the same drawing data. An item chart is one tab stop whose name includes every bar, its value and the unit. Do not require a keyboard user to tab through every mark in a long story stream. Compare the complete pointer-visible and keyboard-accessible fact sets in tests.

### A control that needs a script is not left on the page without one

Hide or disable script-dependent controls until they can act. Provide a truthful no-script state, and retain working navigation and native disclosure where available. Do not promise that fetched charts exist without JavaScript or leave an input that accepts typing but does nothing.

### A diagram a narrow column cannot hold becomes a list, never a smaller diagram

Derive the wide diagram and narrow list from one dataset. Show only one representation at a time, preserve every count, and test their equivalence. Do not trade legibility for smaller type or a scrollbar that hides the comparison.

## Sufficiency is a gate, not a taste

Design review asks whether the changed surface communicates its purpose,
shows a clear first point of attention, and remains usable. Judge the surface
in a representative view with realistic content. Include one narrow view only
when the change can affect its layout. Review another theme or data state only
when the change affects it. This review does not create a test case per page,
panel, width, theme, chart or state.

Keep the meaning and readings of a drawing consistent with its data. Make the
readout usable with keyboard and touch, and make unavailable evidence clear
without treating it as zero. The owning design or data contract defines any
specific behavior that matters. Do not turn these principles into a fixed
matrix of selectors, wording, boxes or per-panel gate drivers.

The browser suite checks one representative shared layout and interaction.
Lower-tier tests cover deterministic readers, column contracts and query
bounds. Visual review is for the changed design; it is not a recurring
inventory of every panel.

Judge useful first-screen content and access to facts, not total page height. A reduction must state what the reader loses.

## Motion vocabulary

Use `fadeIn` for arriving content, `shimmer` for the console's reserved loading box, and `toastIn` for a notice. Animate transform, opacity or paint-only properties, not layout.

Reduced motion removes movement and shimmer gradients; setting a duration to zero is insufficient if it leaves an interaction transform or a frozen bright band. Do not remove transforms that position an element rather than animate it.

Do not use spinners. Keep existing reading content available while more arrives; show a slow or failed fetch as a concise state with retry. Console panels reserve their own room and may use a loading skeleton. Show progress numbers only when a real measurement supplies them.

## A machine's state is a sentence, never a dot

State cost before a download, progress while it is measurable, readiness when complete, and a useful failure with retry. Every cancellable wait offers a stop without disabling unrelated content. Use the configured download size rather than a copied number. Do not imply that initialization progress is measured when the runtime reports none.

## Icons

Use the existing Lucide-derived icon system by id. Keep glyphs monochrome and inherit `currentColor`; do not add a handwritten inline path or a second theme-specific artwork set. [Icon provenance](../../frontend/src/lib/icons/PROVENANCE.md) owns source and update details.

Icons belong in controls, chrome and declared classifications. Do not invent a story type with a decorative headline icon. `clock-alert` identifies a printed fallback time that came from this pipeline, not the publisher; absence of time provenance must not manufacture that claim. Tests check both missing ids and unused glyphs. `icons.stroke_px` sets the line width in screen pixels, and `Icon.svelte` converts it to Lucide's 24-unit grid for each icon size. Susan picked 1.5 px from the comparison sheet: at 1.25 px, six 13 px lines in the dark theme were no brighter than secondary text and eight more sat just above it; at 1.5 px, no line is that dim. At density 3, a 1.5 px icon line is 1.50 px beside a weight-600 label stroke of 1.68 px, so the icon does not outweigh its label.

## Charts render in the browser

Use d3 for chart arithmetic and browser rendering. Theme values come from shared tokens. The browser measures the occupied width; floor fractional pixel widths when needed to prevent a resize loop. Reserve stable height where the chart's row count allows it.

Do not introduce an engine that prerenders charts or requires a runtime server. Removing a chart engine does not remove route-shell prerendering or authorize publishing private inputs. Data preparation may happen in the producer; native console drawing and interaction happen on the reader's device.

## A figure on a chart is the article's or it is ours, and it never has to be guessed

- Preserve source spans for stated values and a traceable derivation for computed values.
- Draw a converted quantity once, in its converted unit. Include the source's original text in the accessible description when it differs.
- Label computed shares, counts and aggregates as computations, not quotations from the article.
- Do not draw an unsupported value. Publish the item without a picture when no valid drawing remains.
- Shortening a number's notation does not permit smaller or illegible type.

## Design rationale

One token system and payload-driven states keep meaning consistent across pages and themes. A measured prose block preserves reading comfort without wasting dashboard width. Browser-drawn charts adapt to the actual device. Shared drawing data keeps marks, descriptions and narrow layouts consistent.

The digest drawing and console use one TypeScript number formatter. Its locale, SI prefix threshold and significant digits come only from `visuals.number_format` in `config/idhazh.json`, never from a reader's browser. Where a shortened figure differs from the article's text, the accessible description keeps the original characters. Owner ruling: kumarsnaveen, 2026-10-24.

Measured values, axes and dated readouts share the configured precision and SI prefixes. Exact event counts retain every digit with the same locale's grouping. Standalone component tests provide the real page's number settings through the shared server-render helper or browser component mount; a missing page context still fails rather than choosing another locale.

The shared footer must not depend on the latest day's data or build identity: either would change unrelated pages on every publication. The current link-only footer has limited visual hierarchy. Improve it with stable content rather than restoring those dependencies.

## See also

- [console-design.md](console-design.md) - operator presentation rules.
- [ui-shell.md](ui-shell.md) - shared page chrome.
- [digest.md](digest.md) - reading-item structure.
- [config/appearance.md](config/appearance.md) - appearance controls.
- [telemetry-intent.md](telemetry-intent.md) - browser rendering and data requirements.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - visual verification.
