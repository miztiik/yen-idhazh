# Design System

**Last Updated**: 2026-08-20

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
- **Colour** - `bg` and elevated surfaces; `text` primary / secondary / tertiary; `accent`; and the **confidence ramp**, one token per band, which is the only semantic colour set the digest needs.
- **Motion** - one ease and a short duration scale.

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

## Icons

Icons are **vector glyphs referenced by id** from a generated manifest, never inline SVG, never a hardcoded path, never a raster image. The manifest is a persisted surface with its own schema ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). Keep the set tiny: an external-link mark, a confidence mark, and whatever the dashboard genuinely needs. An icon that needs a caption is a label wearing a costume.

## Charts are build-time output, not a runtime library

A chart on an item is rendered at build time from a specification and shipped as an asset ([digest.md](digest.md)). The dashboard's own chart is hand-written markup over a committed CSV. A charting library that outweighs the data it draws has not earned its bytes, and a runtime dependency on a reading page is a runtime dependency for nothing.

## Design rationale

Driving the look from fields the payload already carries - route kind, band, truncation - rather than from per-item styling decisions is what keeps the surface one component instead of many, and it means a new route kind or band arrives with a slot already waiting for it. The rejected alternative, bespoke treatment per item type, produces a page that must be edited every time the pipeline learns something new. Authority: Jony.

Keeping the motion set to three named animations is a deliberate under-build. A reading surface that animates is a reading surface that interrupts. Authority: Jony, with Reader ([../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md)) as the check.

## See also

- [ui-shell.md](ui-shell.md) - the chrome that consumes these tokens.
- [digest.md](digest.md) - the item shape this vocabulary dresses.
- [evaluation.md](evaluation.md) - where the confidence bands come from.
- [principles.md](principles.md) - the beliefs behind the restraint.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the payload fields the styling keys off.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a (accessibility scope) and section 12 (published-site verification).
