# UI Shell

**Last Updated**: 2026-09-29

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

- **Page frame:** shared header, navigation, footer and spacing.
- **Data loading:** validate fetched and cached payloads at the same boundary. A malformed payload must not leave a blank page. Publication checks still run before publishing; a successful static build is not proof that every day is valid.
- **Page states:** shared loading, empty, missing and degraded behavior.
- **Local logging:** the browser console records which payload failed and why. No remote log collector or reader tracking.
- **Reader preferences:** read marks and theme choice use `localStorage`, never cookies. Bound reading history and tolerate unavailable or full storage.

## Every page handles five states

Loaded content is the normal case. Design these five additional states:

1. **Empty:** the payload exists but has no items. Say so.
2. **Missing:** the host returns 404 or 410 for the requested day. Offer the archive.
3. **Waiting:** the request is pending. A reading page names the wait after `ui.payload_slow_ms`, without a spinner, skeleton or progress bar. Console panels reserve their dimensions immediately and shimmer only after `console.shimmer_after_ms`.
4. **Unreachable:** another fetch failure occurred. Keep existing content, name the failed request, offer retry and list days available offline.
5. **Degraded:** show low-confidence, truncated or missing-visual items inline.

Never report a failed connection as an unpublished day. Never clear usable content
or leave a blank page because another request failed.

## The day runs newest first, and every story carries its own time

The stream runs newest first without dropping published stories or changing the
editorial leading block ([placement.md](placement.md)). Put each story's own
absolute UTC timestamp beside its heading, not on a shared rail or behind hover.

Use a numeric clock. Add a date when it differs from the viewed day, and the year
when needed. Mark first-sighting time as such; never present it as the feed's time.
If `time_source` is unknown, show no time. If an older record has no attribution,
do not invent one. A relative time may supplement, never replace, the absolute one.

Use the same type as the other item metadata. On a dated page the stamp replaces
the day link; search results keep the day link instead. State `Times shown in UTC.`
once above the stream. These rules apply to browser-rendered content too.

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
- Fetch the shell from the network first. Serve a saved day immediately; refresh the current UTC day in the background so the saved copy does not freeze the news.
- Validate cached data as fetched data. Missing optional visuals may degrade the page, but must not prevent the saved text from being read.
- Restrict the shell cache to its declared assets and opened routes. It must not collect every same-origin request or duplicate telemetry and search caches.

## Base-path discipline

Resolve internal links, assets, payloads and manifest paths under the GitHub Pages
project prefix, including on deep routes. Keep manifest paths relative to its URL.
See [deployment](../how-to/ship-to-github-pages.md).

## Design rationale

- Browser rendering follows the owner's no-prerender direction (2026-09-29) and [Telemetry Intent](telemetry-intent.md). A shipped implementation cannot override it.
- Shared loading and validation keep error handling consistent across surfaces.
- Readability is a requirement for operator pages too, not decoration.
- A spinner reports neither progress nor failure. A named wait and stable panel dimensions communicate what is missing without moving content.
- Cookies transmit reader state with requests. Local preferences need not leave the device. Offline caches retain requested content without fetching the archive.
- A service worker can outlive a broken page, so retirement must work from both the worker and the page before registration.

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
