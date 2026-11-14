# What sits above every console route

**Last Updated**: 2026-11-14

How the console keeps navigation, the selected window and dated evidence in reach
without putting a screen of repeated status ahead of the first useful reading.
[Console delivery](console.md) owns the panels and their data sources.

## One labelled navigation, not top tabs

From `frame.breakpoints_px[1]`, a persistent left rail lists every route and the
active route's named group anchors. Links pair existing glyphs with readable
route labels, not metadata prose or health colors. The selected route has an
outline and tinted surface; the same glyph appears larger beside its page
title. Descriptions remain each link's `title`. All destinations are real
anchors with their existing URLs. Recorded run failures belong to the run-health
comparison, not repeated route and global banners.

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
control. The title, window control, compact source-labelled UTC ranges and
closed `Data sources` disclosure form one sticky band. Below
the first breakpoint, a labelled native days select replaces the radio tiles,
keeping the frozen band compact. Its measured height supplies the document's
scroll padding so anchors and focused controls are not covered. The explorer
keeps its window and Run controls in the editor. Its title and back-to-top
corner stick on narrow page-scrolling layouts; its full-height wide workbench
keeps the title in flow.

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
group. Narrow layouts use one column. The first viewport contains the route,
selected window, access to evidence dates and a useful comparison or readout.

Each route keeps its browser title: route label, Console, then the configured
site title. Client navigation updates it just as a direct load does.

## Run completion and record reach are different dates

The visible date line distinguishes `Published charts` from the `Main packed
window`; neither is a page-wide endpoint. The latter names both UTC bounds
instead of an unqualified `Showing ... to ...` claim. A short record names how
many requested days are available. Pending or missing reach supplies no data
date. Per-panel bounds name independently clamped, private packed or snapshot
evidence. The closed `Data sources` disclosure explains build-time counts and private chart inputs,
compact ledgers rather than raw files, and `Site built` from the band's
`generated_at`. Opening it never reanchors a source.

The last-update timestamp is metadata, not a claim that every ledger reaches
that instant. A fresh completion produces no standing paragraph. The browser
still compares UTC days using `console.completeness_grace_days`, rechecks at UTC
midnight and on visibility, and leaves a late or unread completion warning
visible outside the disclosure. `covers_through` and zero compaction lag cannot
establish freshness.

## Useful panels lead, not repeated summaries

The shell displays no `Latest day`, `Needs attention`, `Site size`, grouped
run-verdict band, route-worst sentence or cross-route metric carry. Navigation,
settings-change metadata and the producer's shared payload remain unchanged.
Run health keeps the actual day and run counts; Pipelines keeps its measured
per-article cost and headroom comparison.

The trade-off is no at-a-glance cross-route worst-issue ranking, coarse verdict
grouping or absolute site-size headline. Their producer records remain intact;
the route navigation and diagnostic panels provide the actionable detail.
Missing, unreachable and loading records keep their own visible states and
working retry access, never a success-shaped fallback.

## Data explorer keeps its workbench

`console.explorer_chrome` selects workbench chrome. The explorer uses the same
rail, route heading, hover surface, back-to-top control and visual tokens, but keeps its days and Run controls
inside the editor. It has no shared date disclosure or completeness line.
Editor and result regions retain their query behavior. The wide
layout reserves the configured query room and gives remaining room to results.
Their actual minimums propagate through the frame, so a short window scrolls
the document rather than letting a result cover the shared footer.

Every console route fills the available window with configured gutters by
default. `frame.console_max_px: null` removes the centered cap; an existing
numeric value still selects a bounded frame. Drawings measure their actual
containers rather than stretching an old SVG coordinate frame. Neither path
adds a server load; direct explorer loading still uses the static fallback
document.

## Design rationale

The rail keeps labelled destinations reachable without a wide top strip.
Keeping compact source dates visible beside the control distinguishes evidence
reach from run completion without delaying the first useful chart. Removing
repeated summaries trades immediate global alerts for space to compare the
actual readings. Letting the brand scroll away avoids a second fixed header
and layout jumps. The native phone select trades simultaneous preset visibility
for more space for the page title and evidence.

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
