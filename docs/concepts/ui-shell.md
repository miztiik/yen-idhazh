# UI Shell

**Last Updated**: 2026-08-24

The chrome around the content: what the published site is made of, what each surface owns, and the states every page must handle. The visual vocabulary lives in [design-system.md](design-system.md); the item itself lives in [digest.md](digest.md). This page is the *structure*.

## The shell is deliberately thin

The whole site is a small number of static pages rendering committed payloads. There is no router-driven application, no session, no client state worth persisting, and nothing to fetch beyond same-origin files that shipped in the same commit (Rule #1).

That means the shell's job is small and worth stating plainly: **load a payload, render it, and be honest when it is missing.**

## The surfaces

| Surface | Owns | Reads |
| --- | --- | --- |
| **Digest** | The day's items, in order, and the run-level notice when a run was partial. | The published digest payload. |
| **Archive** | Reaching a previous day. A reader who missed a day wants to catch up, not start over ([../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md)). | The index of published days. |
| **Dashboard** | The eval ledger rendered as a trend - band counts over time. It never recomputes a score ([evaluation.md](evaluation.md)). | The committed CSV. |
| **Console** | Whether the pipeline itself is working: a chronological strip of runs and the feeds that failed. An operator surface, not a reading one ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)). | The committed run manifests and the feed-health ledger. |

Four surfaces is the whole site, and only two of them are for a reader. A fifth needs an argument.

The two operator surfaces are held to a different standard on purpose: they are instrumentation, they sit off the reading path, they earn no design budget, and their only obligation is to be correct ([vision.md](vision.md)).

## What the shell provides, once

- **The page frame** - header, footer, and the space scale that separates items. Shared, not re-implemented per page.
- **The payload loader** - one place that fetches a same-origin committed file, validates it against the generated contract, and hands a typed value to the page. Validation at the boundary is what turns a malformed payload into a designed empty state instead of a stack trace.
- **The empty and degraded states** - see below.
- **The console log** - the browser console is the entire logging surface ([telemetry.md](telemetry.md)). What a page logs is what a reader would need to hand back when something looks wrong: which payload it tried to load, and what was wrong with it.
- **Reader state, in `localStorage` and nowhere else** - the read mark and the theme choice. Never a cookie: a cookie is sent on every request and would put a reading history into the host's access logs. It is a convenience, so it degrades to nothing under a quota error or private mode, and it is bounded by a window rather than kept forever ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)).

An item component never fetches. It receives a validated slice and renders it.

## Every page handles four states

These are designed, not discovered:

1. **Loaded** - the normal case.
2. **Empty** - the payload exists and has nothing in it. A run can legitimately produce zero items. The page says so.
3. **Missing** - the payload is not there at all, because the day has not run or the deploy raced. The page says so and offers the archive.
4. **Degraded** - the payload loaded but individual items are marked low-confidence, truncated, or without a visual. This is the *common* case, not an exception, and it is rendered inline rather than as an error ([digest.md](digest.md)).

**A page that white-screens on missing data is a failure**, and it is an explicit gate in `CLAUDE.md` section 12. States 2 and 3 are the two most often skipped and the two most likely to be seen by a real reader.

## What the shell must never do

- Fetch anything cross-origin: no CDN font, no analytics snippet, no third-party widget (Rule #1).
- Show a spinner. There is no network in the loop; if something is slow, the payload is too big and that is a build-time problem.
- Ask the reader for anything - no cookie banner, no signup, no notification permission, no rating widget. Every interruption is a reason to close the tab.
- Recompute a score, re-rank items, or derive anything the pipeline already decided. The page renders; it does not think.
- Hide a low-confidence item to make the page look better.

## Base-path discipline

The site is served from a project path on GitHub Pages, not from a domain root. Every internal link, asset reference and payload path must resolve under that prefix, and a link that works in development and 404s in production is the standard way this breaks. The deployment runbook is [../how-to/ship-to-github-pages.md](../how-to/ship-to-github-pages.md).

## Design rationale

Putting payload loading and validation in exactly one place, rather than in each page, is what makes the four states above a shared implementation rather than three inconsistent ones - and it is the reason a malformed payload degrades instead of white-screening. The rejected alternative, per-page fetching, produces a site where the empty state is correct on the page someone remembered to test. Authority: Fowler (contract shape), Jony (what the states look like).

Keeping the site to three surfaces is a delete-first decision. Filtering, search, per-source views and tag pages are all reachable and none of them have a named reader yet; a static page that nobody asked for is rent paid forever. Authority: Jony, with Reader as the check.

The console is the one surface added since, and it was added for a named person doing a named job: the owner, asking whether the pipeline is still working. That is a question the digest cannot answer - a quiet news day and a broken collector produce the same short page. It sits off the reading path, so it costs a reader nothing and costs the shell one route.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A client-side router with per-item pages | Multiplies the surface for a reader who skims one page in two minutes, and every generated page is bytes committed forever. | Jony |
| Fetching the payload per component | Three inconsistent empty states and no single place to validate at the boundary. | Fowler |
| A loading spinner while the payload parses | There is no network in the loop. A spinner would be an animation apologising for a build-time mistake. | Carmack |
| Client-side filtering or search over the ledger | Moves computation to read time for a surface whose whole premise is that nothing computes at read time. | Carmack |
| Run health shown on the digest page | The reader is not the operator. A grid of squares above the news answers a question they did not ask. | owner |
| A cookie for the read mark | Sent on every request, so it would put a reading history into the host's access logs. | Reader |

## See also

- [digest.md](digest.md) - the item this shell frames.
- [design-system.md](design-system.md) - the tokens and states the chrome uses.
- [telemetry.md](telemetry.md) - the browser-console logging rule.
- [evaluation.md](evaluation.md) - what the dashboard renders.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the shape of each surface, the read mark, and the console.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the routes these surfaces sit on.
- [../how-to/ship-to-github-pages.md](../how-to/ship-to-github-pages.md) - the deployment runbook and base-path handling.
- [../../CLAUDE.md](../../CLAUDE.md) - section 12, the published-site verification gate.
