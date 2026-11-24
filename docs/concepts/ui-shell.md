# UI Shell

**Last Updated**: 2026-11-24

**Known noncompliance:** Existing prerendering does not meet [Telemetry Intent](telemetry-intent.md) and will be removed as existing pages migrate. All new designs, charts and visuals must render in the browser; none may be prerendered.

What the shared page frame provides, what each surface owns, and how it handles
loading and failure. Visual styling belongs to [design-system.md](design-system.md);
story content belongs to [digest.md](digest.md). This page states the intended
design, not a claim that the existing implementation already meets it.

## Rendering policy

Static hosting does not require prerendered content. Publish code, assets and data
files; the browser fetches what the current view needs and draws it there.

- Do not add prerendered pages, charts or visuals, or bake their data into HTML.
- Move existing prerendered surfaces to browser rendering. Their current behavior is a migration task, not a pattern for new work.
- Use shared browser data readers for loading, validation and queries. Presentation components receive validated data rather than each inventing a fetch path.
- Browser filtering, sorting and chart queries are allowed. Do not recompute editorial scores or silently change the pipeline's publication decisions.

The console's data and chart rules are owned by
[Telemetry Intent](telemetry-intent.md) and
[how a console chart gets its data](console-design/how-a-console-chart-gets-its-data.md).
The current console still prerenders its route shells. Published-ledger panels
fetch and draw native answers in the browser; approved private build-time inputs
remain on Pipelines, Summaries, Voices and Judgement. Hardware carries only
configuration and words before its native reads. Data explorer uses the fallback
document. [The console boundary](../architecture/publishing/console.md#rendering-direction)
names those exceptions. Retiring a chart engine does not change that architecture
or publish private inputs.
Current implementation details belong to the
[frontend architecture](../architecture/publishing/frontend.md).

## The surfaces

| Surface | Owns | Reads |
| --- | --- | --- |
| **Digest** | Published stories and notices about a partial run. | The digest payload. |
| **Archive** | Finding and opening a previous day. | The published-day index. |
| **Dashboard** | Evaluation trends without recomputing scores. | The evaluation records. |
| **Console** | Pipeline operation, model results and source health. | The telemetry ledgers, queried for the current view. |

Keep operator health off the main reading path. A new surface needs a named user
need. All surfaces owe readable figures, tables that fit the screen, and plain
labels. Technical content does not excuse technical shorthand. Use noun phrases
for panel titles and "the visual planner" for that actor.

## What the shell provides, once

- **Page frame:** shared header, navigation, footer and spacing. The same footer
  band groups edition and project links on reading pages, in the same order
  when stacked on phones. Only the home page links to the previous published
  edition when known. The console footer offers Back to digest, Source code
  and the theme control, not reader search or a link to itself. The archive
  omits the band so its single search surface ends with its stories.
- **Story continuation:** Show more stories and the displayed count belong to
  the list before the footer. Only a fully shown, unfiltered edition gets an
  end marker; narrowed views name their own endpoint and unfinished loads keep
  their wait or retry. Unread only and this edition's read-mark reset sit
  under Reading options at the end of the list. The reader's icon-only Back
  to top is available mid-scroll and docks with the list controls.
- **Data loading:** validate fetched and cached payloads at the same boundary. A malformed payload must not leave a blank page. Publication checks still run before publishing; a successful static build is not proof that every day is valid.
- **Page states:** shared loading, empty, missing and degraded behavior.
- **Local logging:** the browser console records which payload failed and why. No remote log collector or reader tracking.
- **Reader preferences:** read marks and theme choice use `localStorage`, never cookies. Bound reading history and tolerate unavailable or full storage.

The operator layout keeps the window choice in memory across console routes.
Only that mounted boundary reads or writes its optional stored preset; a
storage failure warns locally but cannot delay queries or leave controls and
charts on different windows. The
[console shell](../architecture/publishing/what-sits-above-every-console-route.md)
owns its labelled glyph rail, homepage wordmark, sticky title/window evidence,
footer theme control and back-to-top behavior.

A storage permission or quota refusal must not stop page hydration or the
theme control. Keep the current theme usable for this page, and report the
unsaved preference in the local browser console. Other unexpected errors are
not storage refusals and must remain visible.

Browser chrome follows the resolved page background after client navigation as
well as a theme change. The console palette must not remain on a reading route.

## Every page handles five states

Loaded content is the normal case. Design these five additional states:

1. **Empty:** the payload exists but has no items. Say so.
2. **Missing:** the host returns 404 or 410 for the requested day. Offer the archive.
3. **Waiting:** the request is pending. A reading page names the wait after `ui.payload_slow_ms`, without a spinner, skeleton or progress bar. Console panels reserve their dimensions immediately and shimmer only after `console.shimmer_after_ms`.
4. **Unreachable:** another fetch failure occurred. Keep existing content, name the failed request, offer retry and list days available offline.
5. **Degraded:** keep truncated or missing-visual items readable inline. Reader
   pages show no summary-quality warning or quality glyph; quality evaluation
   remains in the backend and operator console.

Never report a failed connection as an unpublished day. Never clear usable content
or leave a blank page because another request failed.

## The day runs newest first, and every story carries its own time

The stream runs newest first without dropping published stories or changing the
editorial leading block ([placement.md](placement.md)). Put each story's own
absolute UTC timestamp beside its heading, not on a shared rail or behind hover.

Use `HH:mm UTC` only when both the viewed edition and the story's publication
day are actual UTC today. Otherwise print `DD MMM YYYY HH:mm UTC`, for example
`15 Nov 2026 23:30 UTC`, including a two-digit day and the year. Every dated
article on an archived edition gets its full publication date, even when it
matches that edition. A previous-day article in today's edition also gets its
full date. Never substitute the edition date for the story's own date.

Resolve today from the mounted reader's UTC clock, not the build time or payload
generation time. Refresh at UTC midnight and when the page becomes visible,
regains focus or returns from the browser's page cache. Before the browser clock
is available, including without JavaScript, keep the full date rather than
guessing that the edition is today.

Mark first-sighting time as such; never present it as the feed's publication
time. If `time_source` is unknown, show no time. If an older record has no
attribution, do not invent one. A relative time may supplement, never replace,
the absolute one.

Use the same type and wrapping as the other item metadata and label each clock
`UTC`. The semantic time element retains the original timestamp in `datetime`;
only its visible label changes. On a dated page the stamp replaces the day link;
search results keep the day link instead. These rules apply to browser-rendered
content too.

## What the shell must never do

- Depend on a runtime backend, send reader behavior elsewhere, or load tracking code. A third-party static asset is judged on bytes, licence and privacy, not hostname.
- Interrupt reading with signup, cookie banners, rating requests or notifications.
- Hide a low-confidence item or truncate the day to make the page look better.
- Use `Notification`, `PushManager` or background sync. Installation does not grant permission to schedule work or contact the reader.

## Installable, and readable with no network

The manifest and service worker support rereading days already opened. They do not
create an account, report reader activity or prefetch the archive.

- Keep a retirement mechanism. `ui.offline_version` and `ui.offline_retired_through` control it. Both the worker and the page check retirement; a retired worker deletes its own caches and unregisters, and the page must not register it again. Failure to fetch the retirement declaration is not an instruction to retire.
- Precache basic shell assets, not all application JavaScript or unopened days. Cache requested code as needed. Keep day data separate from the build's shell cache so a new deployment does not discard offline reading.
- Bound saved days by both `ui.offline_days_kept` and `ui.offline_bytes_kept`. Measure cached body bytes, not compressed transfer headers. Retain at least one day even when it exceeds the byte limit. Do not put the search model, runtime or retirement declaration in that day cache.
- Fetch the shell and day payloads from the network first. Revalidate day payloads against the host; use the saved day only when the network request fails. An HTTP error still reaches the page's missing or unreachable state rather than being hidden by an old copy.
- Validate cached data as fetched data. Missing optional visuals may degrade the page, but must not prevent the saved text from being read.
- Restrict the shell cache to its declared assets and opened routes. It must not collect every same-origin request or duplicate telemetry and search caches.

## Base-path discipline

Resolve internal links, assets, payloads and manifest paths under the GitHub Pages
project prefix, including on deep routes. Keep manifest paths relative to its URL.
See [deployment](../how-to/ship-to-github-pages.md).

## Design rationale

- Browser rendering follows the maintainer's no-prerender direction (2026-09-29) and [Telemetry Intent](telemetry-intent.md). A shipped implementation cannot override it.
- Shared loading and validation keep error handling consistent across surfaces.
- The list ends with reading actions, the footer with destinations. Native
  links work even if the digest fails to arrive or JavaScript is unavailable.
  Keep the shared footer independent of the current day's data and build
  identity so unrelated pages do not change with every edition.
- Readability is a requirement for operator pages too, not decoration.
- A spinner reports neither progress nor failure. A named wait and stable panel dimensions communicate what is missing without moving content.
- Cookies transmit reader state with requests. Local preferences need not leave the device. Offline caches retain requested content without fetching the archive.
- A service worker can outlive a broken page, so retirement must work from both the worker and the page before registration.
- Background cache refresh does not update a day already rendered. Network-first day reads prevent an older offline copy from replacing newly published content; a failed cache write must not discard a successful network response.

## See also

- [telemetry-intent.md](telemetry-intent.md) - browser-owned data loading and the no-prerender goal.
- [digest.md](digest.md) - the item this shell frames.
- [design-system.md](design-system.md) - the tokens and states the chrome uses.
- [telemetry.md](telemetry.md) - the browser-console logging rule.
- [evaluation.md](evaluation.md) - what the dashboard renders.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the shape of each surface, the read mark, and the console.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the routes these surfaces sit on.
- [../how-to/ship-to-github-pages.md](../how-to/ship-to-github-pages.md) - the deployment runbook and base-path handling.
- [../../CLAUDE.md](../../CLAUDE.md) - section 12, the published-site verification gate.
