# What sits above every console route

**Last Updated**: 2026-11-11

How the console keeps navigation, the selected window and dated evidence in reach
without putting a screen of repeated status ahead of the first useful reading.
[Console delivery](console.md) owns the panels and their data sources.

## One labelled navigation, not top tabs

From `frame.breakpoints_px[1]`, a persistent left rail lists every route and the
active route's named group anchors. Links pair existing glyphs with readable
route labels, not metadata prose or health colors. The selected route has an
outline and tinted surface; the same glyph appears larger beside its page
title. Descriptions remain each link's `title`. All destinations are real
anchors with their existing URLs. Each route's issue stays beside its dated
page evidence; the standing band retains the worst issue across routes.

Below that breakpoint, the same links sit in a native `Console menu` disclosure.
It closes after navigation. Without JavaScript it starts open, so every route
and group remains reachable. There is one navigation tree, not duplicate hidden
menus. Group headings retain their `Top` links to a normal-flow `#console-top`
anchor before the sticky title, so a link still returns to the route's start
after the title sticks.

The shared site header uses the homepage's actual wordmark, linking to the
digest, without a second Console label. It scrolls away in normal page flow:
there is no animated shrink or compensating spacer. Reading routes keep their
existing header. No font or icon asset is added.

The existing theme control sits at the right of the shared footer beside
Archive, Console and Source code. It wraps to a right-aligned second line when
needed. Workbench routes keep this compact footer too. Theme storage and the
before-paint theme resolution are unchanged.

## Route identity and the window lead the evidence

The content column starts with the active route's visible heading and the days
control. The title, window control and window/evidence sentence form one sticky
band; the latest-run sentence and standing band continue in normal flow. Below
the first breakpoint, a labelled native days select replaces the radio tiles,
keeping the frozen band compact. Its measured height supplies the document's
scroll padding so anchors and focused controls are not covered. The explorer's
title stays in flow because its window and Run controls belong to the editor.

A back-to-top button appears once the brand has scrolled away. On wide screens
it floats at the foot of the navigation rail, outside chart readings, and lifts
above the measured footer when that enters view. On narrower screens it uses a
reserved corner of the sticky title band instead of covering charts. It focuses
the page heading and scrolls the document itself, with no smooth movement when
motion is disabled or reduced motion is requested.

Hardware places its recording disclosure immediately below the run count. The
closed summary flags gaps or measurement being off, names excluded runs and
states that their articles still count. Its body retains all recording dates,
missing counts, run IDs and reasons. Detailed provenance must remain reachable
without pushing the first comparison off a phone.

The layout owns the mounted window choice; each route still owns its queries,
fetch state and returned record reach. The
[window contract](which-console-surfaces-follow-the-window-and-which-say-why-not.md)
defines optional storage, presets and the exceptions to the shared span.

From `frame.breakpoints_px[2]`, panel groups may use the configured number of
columns without changing source order. Wide and route-verdict panels span the
group. Narrow layouts use one column. The first viewport must contain the route,
selected window, evidence date and a useful comparison or readout.

Each route keeps its browser title: route label, Console, then the configured
site title. Client navigation updates it just as a direct load does.

## Run completion and record reach are different dates

The completeness sentence dates the band's `generated_at`, in UTC. It never
claims that every ledger reaches that instant. Packed panels date their actual
returned record beside the window or their own readings; a pending or missing
reach supplies no data date.

Prerendered markup states the run's completion instant without claiming its age.
The browser compares UTC days using `console.completeness_grace_days`, then
rechecks at UTC midnight and when the page becomes visible. A late record names
the missing days. An absent band says its completion time is unavailable.
`covers_through` and the retained zero-valued compaction-lag reading cannot
establish freshness.

## The standing band carries three facts

The producer writes `console/band.json`; the universal console layout reads it
once and keeps the band shared between routes. It contains:

- Latest day's verdict, labelled `Latest day`, not a relative day name.
- The worst issue and its consequence, linking to its route.
- Site size against the platform's 1 GB limit and the articles the headroom buys.

These are not selected-window aggregates. The site-size runway uses the
published record; the per-article cost panel owns its rate and denominator.

Run verdicts remain available in a native disclosure. Each square names its run
and verdict; grouped words give the same facts without a pointer. The producer's
cap and `+N` count remain intact. Squares use the existing status-fill meanings,
not the categorical chart palette.

The band does not repeat a compaction-lag line whose value cannot move. A
resting-feed issue names its retry behavior from configuration; it does not
invent an operator task for a state that clears itself.

## Worst-state selection keeps its existing meanings

Failed-run candidates precede resting feeds, so a failed run wins a stable tie.
Editorial faults cap at `WORTH_A_LOOK`, except a gating instrument whose recorded
decline rate reaches either configured extreme: both accepting everything and
rejecting everything make the instrument untrustworthy. No absent rate triggers
that rule.

Hardware candidates include a refused run, a planned shard with no record and
the newest run's read spread. Missing-shard counts use the independently recorded
plan denominator, never the number of host rows as both numerator and
denominator. Spread uses the server's own prompt-token/time counters and stays
lowest-ranked because it has no agreed alarm threshold. Swap use is reported
only when total swap is known and positive; a box with no swap is not a full
swap device.

Voices ranks a feed at the reliability floor as `WORTH_A_LOOK`; too little source
evidence is `WORTH_KNOWING` and retains its denominator. Feeds that answered
nothing are a subset of the at-floor set, not a duplicate candidate.

## Data explorer keeps its workbench

`console.explorer_chrome` selects workbench chrome. The explorer uses the same
rail, route heading and visual tokens, but keeps its days and Run controls
inside the editor. It has no duplicate band, completeness line or window
sentence. Editor and result regions retain their existing behavior.

Every console route fills the available window with configured gutters by
default. `frame.console_max_px: null` removes the centered cap; an existing
numeric value still selects a bounded frame. Drawings measure their actual
containers rather than stretching an old SVG coordinate frame. Neither path
adds a server load; direct explorer loading still uses the static fallback
document.

## Design rationale

The rail keeps labelled destinations reachable without a wide top strip.
Putting window reach beside its control distinguishes available evidence from
run completion. Keeping this small band in reach avoids repeated trips to the
top; letting the brand scroll away avoids a second fixed header and layout
jumps. The native phone select trades simultaneous preset visibility for more
space for the page title and evidence.

Neutral surfaces separate grouping from status; typography, shared hover
tooltips and non-hover readings carry the comparison. The operator-only generated style
scope includes the outer canvas and header before paint without recoloring the
reader. [Appearance configuration](../../concepts/config/appearance.md) owns its
validated values.

## See also

- [console.md](console.md) - panels and data boundaries.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - shared window and dated exceptions.
- [console-site-size.md](console-site-size.md) - size and headroom.
- [console-payloads.md](console-payloads.md) - the band's producer.
- [../sources/health.md](../sources/health.md) - source retry behavior.
- [../../concepts/console-design.md](../../concepts/console-design.md) - wording and chart meaning.
