# Who supplied the day, and which feeds failed

**Last updated:** 2026-10-10

`/console/voices/` answers two questions in eight panels. The order, stable ids,
judged inventory and route thresholds live in `config/console/voices.json`.
The owning page reads the immutable console configuration; its server load
does not serialize another console configuration or an article ledger.

## What the sources supplied

1. **`source-health` — Sources we may ask, and what they yield.** The published
   source census keeps permission, answering, retirement and yield separate.
   Every permission and availability state appears, including states containing
   no sources. Held sources are named loudest-state first, with curated title,
   stable id, desk, what is withheld, offers and publications. A shared-scale
   ranked yield list compares each source against the best source. The census's
   complete-day floor decides whether it prints counts or rates; source-owned
   failures are never subtracted from both denominator and numerator.
2. **`feeds-failed` — Feeds and articles that failed.** The real build-time feed
   record and native `feedsFailedQuery` meet in two tile rows per source: feed
   above article. Filled means failure, outlined means recorded without a
   failure, and dashed means no evidence-bearing ask was recorded. A feed that
   answered with no entries failed; robots refusal and resting are not failed
   asks. Article failures are client errors, rate limits, server errors and
   network errors. The readout retains outcome, code words, HTTP status, source
   form, tier and the number of failures out of recorded fetches. The common
   axis stops at the older **observed row end**, not the build clock
   or a synthetic job day. A newer article tail awaiting feed evidence is named.
   Sources failing in either row rank by failed days, with failed and observed
   clean sources counted in the tail. An unavailable or empty article answer
   retains useful feed evidence, explicitly as feed-only evidence. An unobserved
   day never proves that every fetch answered. A scriptless document has a
   separately named feed-only reading outside the native panel's reserved body.
3. **`fetch-time` — Where a fetch spent its time.** Native `fetchTimeQuery`
   ranks sources by mean whole `fetch_ms`. Rows without a whole or robots clock
   cannot support this comparison. Robots, previous attempts/retries, connecting,
   waiting for headers and the remaining fetch time split the whole only when
   **every row in that source's mean** has the required clocks. A partial
   population cannot supply parts of a different population's mean. The
   producer's first-attempt retry count and retry time are recorded zeroes.
   Null is an untaken reading, never zero. Headers exclude handshake time and
   body download; retry time precedes the winning attempt. The residual is
   derived only from a complete, non-overlapping reading. If its parts exceed
   the whole, the breakdown is refused, not clamped. The whole can remain useful
   with an explicitly unknown split. The retry-count statement requires recorded
   retry evidence, not an empty list.
4. **`retiring` — Sources close to retiring themselves.** The census's target
   bars, recorded daily squares, evidence floors, unjudged rows and dwell area
   remain. The producer counted `days_under_the_mark` and named `retires_on`;
   the browser does not make a second retirement decision. An automatic-retire
   flag of false says “watching only.” Rows below either evidence floor retain
   their squares and counts but acquire no countdown. Empty and missing census
   readings have different sentences.
5. **`source-cuts` — Sources cut short most often.** Native `sourceCutsQuery`
   now supplies the existing `SourceCutRange` geometry at view time. Its log
   axis and original-length range remain. Stable source/address keys collapse
   reruns; the strongest recorded pre-cap reading wins. Unknown before/after
   lengths are neither zeroes nor evidence for a cut-share denominator. The
   typical removed words compare against the source's original-length range.

## What the ranking did

6. **`ranking-discount` — How far the ranking discounts each feed.** This is
   the build-time source census's reliability, not an item ledger substitute:
   a failed feed may have supplied no item row. The ranked value is
   `1 - reliability`, heaviest discount first, with most reads breaking ties.
   The rule is `1 - reliability_floor`, “the most the ranking takes.” Only
   discounted, read feeds get bars. Measured full-weight feeds and unread
   default-full-weight feeds are separately counted in the tail. The applied
   run and its fixed reliability span are named.
7. **`why-chosen` — Why the newest day's articles were chosen.** Native
   `whyChosenQuery` supplies each item's own newest **numeric-suffix run** on
   the newest recorded day. Authority, recency, lens, watchlist and carriage,
   in that order, must sum to `selection_score` within `0.000001`. Authority
   already includes tier, feed weight and reliability: these remain readout
   factors, not extra stacked parts. A short or unrecorded candidate population
   cannot establish the configured twentieth authority-only threshold.
8. **`watchlist` — What the watchlist caught.** Native `watchlistQuery` counts
   distinct address keys, not repeated run rows. Day tiles distinguish a
   recorded false from an unrecorded hit cell. True front-page flags are counted
   separately from unknown front-page evidence. A partial count is a lower
   bound, not a fabricated zero. Catch and naming thresholds are respectively
   one and three; no-catch words require recorded quiet evidence.

## The route's read and its four nothings

The five declared queries are imported from `queries/voices.ts`, with no second
column declaration. `routeReach` anchors their windows on the oldest available
ledger end. `rangeFor(query, preset, reach, windowPresets)` establishes each
range; the owning page calls `sliceOnce`, never the raw door. Newest-day choice
does not pretend to follow the selected window.

The route owns one pending standing and one delayed shimmer. Native bodies are
value- and date-free in the built document. Loading reserves an axis frame
without fictitious bars; settled record frames use the shared words:
“Nothing recorded,” “Not published yet” and “Did not arrive.” A successful empty
record is not a publication absence or a failed request.

Changing the preset asks that range. Explorer Refresh changes the explicit
`readSession`, invalidating held answers. Retry forgets failed asks only,
re-asks reach and retains useful successful siblings. The shared control
receives `{asked, first, through}`; the layout does not run engine queries.
Short windows, lost days and set-aside files retain their evidence notes.

The census, retirement and ranking-factor surfaces remain fully build-time,
because their source view is not published as a browser ledger. All three
explicitly name their fixed run/span rather than implying the window control
recomputes a private decision. Every panel declines a model-change rule with
its own name and reason: permissions, outcomes, ranking, rule distance, one
day's choice or hit counts are not a model trend.

Pure modules under `src/lib/console/voices/` own the reductions. The Svelte
components draw their geometry and readouts. Native tests publish independent
Parquet roots through the existing bounded private builder; they do not replace
engine answers or rewrite the shared canary's exact failure counts.

## Design rationale

Shared Voices browser assertions still require an owner decision before this
route can ship. The shared `frontend/tests/console.spec.ts` cases require feed-only
partitions, row metadata and a feed-only count equation from the combined
feed-and-article list. A clean feed with a failed article belongs in that list;
its feed evidence remains clean. The list's common end can also precede the
feed record's end. These are different populations, not missing feed metadata.

The required scope amendment is a structural Move Function prerequisite owned
by the shared test owners: move the eight Voices cases, their constants and
`feedHeadline` into a route-only spec without changing a case, fixture or
assertion. Then retain feed-only assertions against truthful feed-only evidence
and check the combined population separately. Row8 cannot edit the shared body;
the earlier approval to move window cases did not approve this move.
The shared disjointness, drawn-plus-hidden count and feed-row metadata assertions
remain unresolved. Combined rows identify a failed source, not a failed feed.

## Related contracts

- [console.md](console.md): console route questions.
- [console-truncation.md](console-truncation.md): original-length/cap geometry.
- [../sources/health.md](../sources/health.md): feed evidence and permissions.
- [../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md): source/readout doctrine.
