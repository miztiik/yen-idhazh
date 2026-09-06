# UI Shell

**Last Updated**: 2026-09-06
The chrome around the content: what the published site is made of, what each surface owns, and the states every page must handle. The visual vocabulary lives in [design-system.md](design-system.md); the item itself lives in [digest.md](digest.md). This page is the *structure*.

## The shell is deliberately thin

The whole site is a small number of static pages rendering committed payloads. There is no router-driven application, no session, no client state worth persisting, and nothing to fetch beyond same-origin files that shipped in the same commit (Rule #1).

That means the shell's job is small and worth stating plainly: **load a payload, render it, and be honest when it is missing.** Since 2026-09-01 a reading page loads its day in two halves - the head of it at build time, the rest from a same-origin file the browser asks for - so "be honest when it is missing" gained a second half too: be honest when the rest of it has not arrived yet, and when it never will.

## The surfaces

| Surface | Owns | Reads |
| --- | --- | --- |
| **Digest** | The day's items, grouped by topic when the day has more than one, and the run-level notice when a run was partial. | The published digest payload. |
| **Archive** | Reaching a previous day. A reader who missed a day wants to catch up, not start over ([../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md)). | The index of published days. |
| **Dashboard** | The eval ledger rendered as a trend - band counts over time. It never recomputes a score ([evaluation.md](evaluation.md)). | The committed CSV. |
| **Console** | Whether the pipeline itself is working: a chronological strip of runs and the feeds that failed. An operator surface, not a reading one ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)). Since 2026-08-30 it is one surface on three prerendered routes - `/console/` (Pipelines), `/console/model/` (Summaries) and `/console/machine/` (Hardware) - sharing a navigation strip of real anchors, a standing band under it and one window control under that. | The committed run manifests, the feed-health ledger, and since 2026-09-03 the source-health view the run publishes - the four facts about every address a curator has left active. |

Four surfaces is the whole site, and only two of them are for a reader. A fifth needs an argument.

The two operator surfaces are held to a different standard on purpose. They sit off the reading path, so they spend no reader attention and take no ornament: no display face, no gradient, no illustration. What they owe instead is **legibility** - a figure the operator can read at a glance, a table that fits the screen it is on, and a page that can be scanned in one pass. Correctness is the floor, not the ceiling. An instrument that is right and unreadable has not done its job ([vision.md](vision.md)).

**An operator is a reader, so an operator surface names things in plain words too** (`CLAUDE.md` section 0b). A stage name is a term the pipeline uses on itself; it is not a term for the person reading the page, and no operator surface earns an exemption for being technical. The console renamed its chart-arm section on 2026-08-31 for exactly this: `router` was what the code called the stage, so the page named the actor in plain words and dropped the word entirely where it was only modifying a number. Two route labels moved the same day for the same reason - `Machine` became **Hardware**, which is the plainest word for a processor and a clock, and `Model` became **Summaries**, because every panel on that route is about a published summary. Every panel title on the three routes is a noun phrase rather than a question, because a question asks the reader to hold it while he reads the panel. The identifiers - route ids, `data-` attributes, config keys, ledger columns - kept the old names that day, because those are addresses and a label may change where an address may not; the ones that were not published moved on 2026-09-05 ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)).

**The actor is "the visual planner", singular, on every surface.** The page said "the visuals planner" from 2026-08-31 to 2026-09-05, which was a third spelling beside the module `visual_planner.py` and the knob `models.visual_planner` - so an operator reading the page had to translate before editing the config. Singular is also the accurate word: the stage decides one visual for one story, and the plural came from the `visuals` job, which is plural because one job renders a whole day. Which strings moved, and what the rename costs while every visual is still a chart, is in [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md).

## What the shell provides, once

- **The page frame** - header, footer, and the space scale that separates items. Shared, not re-implemented per page.
- **The payload loader** - one place that reads a same-origin committed file, validates it against the generated contract, and hands a typed value to the page. Validation at the boundary is what turns a malformed payload into a designed empty state instead of a stack trace. There are two of them since 2026-09-01 and that is a seam rather than a second implementation: `frontend/src/lib/server/payload.ts` reads the committed day at build time, and `frontend/src/lib/assist/day.ts` fetches the served day in the browser. **The build no longer proves every committed day renders**, because it never opens the stories past a document's seed - `idhazh validate-days` opens them instead, in CI and before every publish, and the guarantee is now that a broken day cannot be merged rather than that it cannot be built.
- **The empty and degraded states** - see below.
- **The console log** - the browser console is the entire logging surface ([telemetry.md](telemetry.md)). What a page logs is what a reader would need to hand back when something looks wrong: which payload it tried to load, and what was wrong with it.
- **Reader state, in `localStorage` and nowhere else** - the read mark and the theme choice. Never a cookie: a cookie is sent on every request and would put a reading history into the host's access logs. It is a convenience, so it degrades to nothing under a quota error or private mode, and it is bounded by a window rather than kept forever ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)). The service worker's caches are not an exception to this: they hold copies of files this site served, and nothing about the reader.

An item component never fetches. It receives a validated slice and renders it.

## Every page handles five states

These are designed, not discovered:

1. **Loaded** - the normal case.
2. **Empty** - the payload exists and has nothing in it. A run can legitimately produce zero items. The page says so.
3. **Missing** - the payload is not there at all, because the day has not run or the deploy raced. The page says so and offers the archive.
4. **Waiting** - the page has the head of its day and the rest is still coming. It is a reading-route state only, and it stays silent until `ui.payload_slow_ms`, because the first frame is already readable and there is nothing to fill. Past that it is **one sentence**, never a spinner, a skeleton or a bar.
5. **Unreachable** - the payload exists and the fetch for it failed. The stories already on screen stay exactly as they are, the page names the day that did not arrive, it offers a retry, and it lists the days this device can still read with no network.
6. **Degraded** - the payload loaded but individual items are marked low-confidence, truncated, or without a visual. This is the *common* case, not an exception, and it is rendered inline rather than as an error ([digest.md](digest.md)).

Six entries and five states, because Loaded is the one that is not a failure of any kind.

**Missing is decided at build time and Unreachable in the browser**, so neither has to guess which it is. Telling a reader a day was never published when their train went into a tunnel is a lie they can check.

**A page that white-screens on missing data is a failure**, and it is an explicit gate in `CLAUDE.md` section 12. States 2, 3 and 5 are the most often skipped and the most likely to be seen by a real reader.

**Waiting and Unreachable are new since 2026-09-01**, and they are what a reading route bought by stopping carrying its whole day. Before that a document held every story it published, so there was nothing to wait for and nothing that could fail after the page arrived.

## The day runs newest first, on a time rail

The stream orders by the time on the story, newest first, down a rail on its leading edge. What it replaced was the published order, which is desk-blocked rather than ranked - the whole of one desk, then the whole of the next - so a reader met the same desk ninety times before the next one began. **Nothing editorial is lost by re-ordering it**: what the day thinks is important is the leading block, chosen across the whole day, and it is unchanged. Measured 2026-09-02 over the 12 committed days and 4,713 stories, the re-ordered set is the published set on every day.

**No relative time, anywhere, ever.** A page is rendered once and read for the next 24 hours, and its times are in the document before any script runs and stay there if none ever does - so `3 hours ago` baked in at 06:20 is wrong by 18:20 and wrong for ever on an archived day. A device may add a relative form beside a correct absolute string; it may never replace one. `Yesterday` is not a relative form - it is relative to the day the page IS, which is printed at the top of that page and never moves.

Five strings, and the fourth is the one that matters:

| The reader sees | When |
| --- | --- |
| `14:05` | the story's stamp is on the day being read |
| `Yesterday 23:40` | it is on the day before. Common rather than an edge case: feed-to-arrival reaches 25.7 hours against a 24-hour age limit |
| `11 Jun 08:15`, or `11 Jun 2019 08:15` across a year boundary | older than that |
| `First seen 06:20`, with a mark | the feed's own time was absent or rejected as impossible, so the clock printed is **ours** |
| `No time given` | neither clock answered, so the story carries no time at all |

The fourth exists because the fallback behind it is silent. `published_at` is the feed's own date where the feed gave a usable one and our first sight of the address where it did not, and both are the same kind of string - so a page printing the time cannot say whose it is without `time_source` ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)). **The page never prints a time it rejected as a feed time.** That is the same class of failure as an invented axis label.

A story published before `time_source` existed prints the stamp with **no attribution at all** and no mark. The run recorded no answer, so "the feed said this" and "we said this" are both claims we cannot back, and 3,733 of the 4,713 committed stories are in that state.

**One marker per group, never one per story.** The rail draws a label where the time group changes and nothing on the stories under it; a group is `digest.rail_group_minutes` wide, an hour by default. Measured 2026-09-02 over the same 12 days: 907 markers rather than 4,713, so the rail leaves out 80.8 percent of the labels a marker-per-story rail would print. The busiest day draws 33 markers over 627 stories. **The marker is the first story's own time to the minute rather than a rounded one**, and since the stream runs newest first it is an upper bound on everything below it until the next marker - which is how a reader already reads a rail.

The zone is named once, in one line above the stream: `Times shown in UTC.` Not a suffix on 359 labels, and not a fifth band at the top of the page - it belongs to the column it explains, so it sits directly above it.

**A phone gets the same rail without a column.** Below the small breakpoint the marker is a rule across the top of its group with the time under it, because a 360px screen has 328 CSS px of content box and a column plus the read mark plus the card's own padding left the summary 186px - about 25 characters, with a title broken mid-word ([design-system.md](design-system.md)).

**The time is printed once.** It used to sit in the item's eyebrow, above the title, and the rail took it on 2026-09-02. A search result keeps a date in that slot, because that list has no rail and the date is how a reader tells which day a found story was published on.

## What the shell must never do

- Run anything off the reader's device, report a reader's behaviour anywhere, or load a third-party script that phones home (Rule #1). A static asset is judged on bytes, licence and privacy behaviour, never on hostname - and this project self-hosts its font because the request is the larger cost, not because the origin is forbidden.
- Show a spinner. One reading page in the site waits on anything at all, it waits on a file this site publishes, and the frame the reader already has is readable - so there is nothing for a spinner to fill. Past `ui.payload_slow_ms` the page says one sentence. If a wait is long enough to need more than that, the payload is too big and that is a build-time problem.
- Ask the reader for anything - no cookie banner, no signup, no notification permission, no rating widget. Every interruption is a reason to close the tab.
- Recompute a score, re-rank items, or derive anything the pipeline already decided. The page renders; it does not think.
- Hide a low-confidence item to make the page look better.
- **Call `Notification` or `PushManager`. Ever.** The reader decides when to read (CLAUDE.md section 0a). This is written down rather than implied because installability makes the temptation concrete: an installed app is exactly the context in which "just a gentle daily reminder" starts to sound reasonable. It is not. Since 2026-09-02 background sync is on the same list, and for the same reason - work on the reader's device that they did not ask for, on a schedule we chose. `frontend/tests/manifest.spec.ts` greps the source, the worker included, and fails on any of those names.

## Installable, and readable with no network

The site ships a web app manifest, an icon set, a `theme-color` and a service worker. A manifest is a static JSON file: no request, no account, no code outliving the tab. It sits inside Rule #1 for the same reason the font does, and so does the worker: it runs on the reader's own device, over files this site already serves, and reports nothing anywhere.

**The worker exists so a day a reader has already opened can be read again with no network.** That is the whole feature. An installed window is then a reader rather than a bookmark.

**Until 2026-09-02 there was no worker, and that was the right answer at the time.** A day used to sit inside its own document, so a worker would have cached HTML and given a reader nothing an ordinary browser cache does not already give. The 2026-09-01 migration made the day a separate addressable file, and offline reading became a real thing to have rather than a word for what the browser did anyway.

**The way out was designed before the way in, and it is checked before a single byte is spent.** A worker is the only code this project ships that survives the tab closing, so a broken one cannot be fixed by the reader closing it, and a stale worker serving a stale bundle is the hardest bug class available to a static site. So:

- `config/appearance.json` names two numbers: `ui.offline_version`, the version this build's worker carries, and `ui.offline_retired_through`, the version through which workers must retire. The build writes the second into `service-worker-kill.json` at the site root and bakes the first into the worker.
- A worker whose version is at or below the number that file names **deletes every cache it owns and unregisters itself**. Zero retires none, because the lowest version a worker can carry is one.
- **Both the worker and the page read it**, and that is not one check written twice. The worker reads it at install, so a retired worker keeps nothing, and at activate, which is where a retirement normally lands. The page reads it before it registers anything, and that half does not depend on the worker being well - a worker whose own activate handler is broken is precisely the reader-pinned-to-a-bad-bundle failure the switch exists for. It is also what makes a retirement converge: the shell registers on every page load, and a registration pending removal is resurrected by the next `register()`, so a worker that could only retire itself would come straight back on the next page.
- A switch that cannot be read is not a switch that says yes. A worker that retired itself whenever the network was down would be a worker that never works offline.
- The bill for leaving it on is one 27-byte file per page load and nothing else: a retired worker precaches nothing, and the page stops registering it.

**It caches what a reader has already opened, and nothing else.** On install, the shell's own assets and its stylesheets - the font, the icons, the manifest, the CSS. **Not the app's JavaScript**, and that was measured rather than assumed: the built client is 23.56 MB, of which 21.60 MB is the search encoder's runtime and 1.47 MB is two libraries only the console and the search panel ever load (measured 2026-09-02 on Intel Core i7-1265U / Windows 11 / node 24.12.0). Downloading those for a reader who opened one day is the same spend that argued against precaching days. The code a page needs is kept when that page asks for it, which is what makes a day already opened read again.

A day payload is kept only after that day has been fetched once, and never a day nobody asked for. The kept days are bounded twice: by `ui.offline_days_kept` (14), and by `ui.offline_bytes_kept` (20,000,000 bytes) since 2026-09-06. Two bounds because a day count cannot bound bytes - measured 2026-09-02 over the 12 served days, one day payload runs 8,231 to 1,373,593 bytes, a factor of 167, so fourteen days is anything between 115 KB and 19 MB. The byte ceiling is a backstop rather than the binding rule today: 20 MB is just over the 19 MB fourteen days already reach at the largest day measured. Nothing reads it yet - the eviction rule is row 8 of [../../TODO/20260906-constant-cost-reads-plan.md](../../TODO/20260906-constant-cost-reads-plan.md). Never the encoder's model and runtime, which are 43.2 MB together and keep their own store, and never the switch itself.

**The shell is network-first, and a day is served from the device first.** The shell changes on every deploy, so a stale one is the bug the switch exists for. A day is different: an archived day never changes again, so reading it off the device is correct. **Today's day is the exception, and it is why this is not a plain cache-first.** The pipeline republishes the current day several times an hour, so a reader who opened it at nine would otherwise be held at nine for the rest of the day. What ships returns the copy on the device at once and refreshes it behind the reader, which costs exactly the request they would have made with no worker at all.

**A cached day goes through the same boundary check a fetched one does.** The worker hands the response to the page, and `frontend/src/lib/assist/day.ts` drops a story missing any of the four names it dereferences - so a day off the device is validated exactly as a day off the network is.

**A reader offline on a day they never opened is not left with a button that cannot work.** The Unreachable state names the day, offers the retry, and lists the days this device still holds - read straight off the cache by the page, which already owns that question.

The manifest's own paths are relative - `start_url` and `scope` are `.`, and every icon `src` starts `./` - so they resolve against the manifest's URL and survive the project path without being templated. A manifest that validates at a domain root and 404s every icon under a project path is the standard failure, and the oracle resolves each path the way a browser would, from a deep route rather than only from the root.

## Base-path discipline

The site is served from a project path on GitHub Pages, not from a domain root. Every internal link, asset reference and payload path must resolve under that prefix, and a link that works in development and 404s in production is the standard way this breaks. The deployment runbook is [../how-to/ship-to-github-pages.md](../how-to/ship-to-github-pages.md).

## Design rationale

**"They earn no design budget" was struck on 2026-08-29, and it is the sentence that produced the console.** It conflated a design budget with an ornament budget. The console does not need a gradient; it needs a table that fits the screen, charts that are not 164px wide, and a page that is not 6562px tall - and those are not decoration, they are whether the instrument can be read at all. Measured 2026-08-28 at a 1209px viewport: a 10-column table rendered at 627px and seven elements with horizontal scrollbars, while 582px of screen sat empty beside them. The sentence also contradicted [design-system.md](design-system.md)'s own console-copy section, which spends a large budget on nine labels and five numbering rules - so the page both granted and refused the budget, and the refusal won in practice because it was shorter and sounded like a principle. The rejected alternative was softening it; a softened absolute is still read as an absolute. Authority: owner, 2026-08-29.

**The cross-origin bullet was corrected in the same commit and is an independent fix.** It read "Fetch anything cross-origin: no CDN font, no analytics snippet, no third-party widget", which contradicts `CLAUDE.md` Rule #1 as amended 2026-08-23 - the rule draws its line at a *service*, not at an origin, and explicitly permits a third-party static asset judged on bytes, licence and privacy behaviour. Rule #4 makes the contract win, so this doc was simply stale and was a trap for the next agent reading it. What did not change: this project still self-hosts its font, because the HTTP cache is partitioned per site so the shared-cache argument is dead, and `script-src` and `default-src` are `self` only.

Putting payload loading and validation in exactly one place per side of the build, rather than in each page, is what makes the states above a shared implementation rather than five inconsistent ones - and it is the reason a malformed payload degrades instead of white-screening. The rejected alternative, per-page fetching, produces a site where the empty state is correct on the page someone remembered to test. Authority: Fowler (contract shape), Jony (what the states look like).

Keeping the site to three surfaces is a delete-first decision. Per-source views and tag pages are both reachable and neither has a named reader yet; a static page that nobody asked for is rent paid forever. Filtering and search were on that list until the owner overruled it, and what shipped is not a page: they are two controls in one panel above a list that already exists, described in [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md). Authority: Jony, with Reader as the check.

The console is the one surface added since, and it was added for a named person doing a named job: the owner, asking whether the pipeline is still working. That is a question the digest cannot answer - a quiet news day and a broken collector produce the same short page. It sits off the reading path, so it costs a reader nothing and costs the shell one route.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A client-side router with per-item pages | Multiplies the surface for a reader who skims one page in two minutes, and every generated page is bytes committed forever. | Jony |
| Fetching the payload per component | Three inconsistent empty states and no single place to validate at the boundary. | Fowler |
| A loading spinner while the payload parses | The frame a reader already has is readable, so a spinner would fill nothing. What survives of this ruling after a reading page began fetching is one sentence past `ui.payload_slow_ms`, which is a fact rather than an animation. | Carmack |
| Client-side filtering or search over the ledger | Moves computation to read time for a surface whose whole premise is that nothing computes at read time. | Carmack |
| Run health shown on the digest page | The reader is not the operator. A grid of squares above the news answers a question they did not ask. | owner |
| A cookie for the read mark | Sent on every request, so it would put a reading history into the host's access logs. | Reader |
| A day-level chart of the confidence bands | Its proportions were the same every day, and it shared its colours with the item mark that does vary. Colour is spent per item. | Jony, Reader |
| Truncating a long day so the page looks like a digest | It would stop being one. The day's leading stories give the page a first screen without dropping a published item, and the stream below carries the whole day. | Jony |
| Our own pipeline arrival time on the rail | Puts our run schedule into the news timeline. A reader wants to know when the news happened, not when we found it. The one exception is the story that has no other time, and there the label says `First seen` and carries a mark. | owner |
| Keeping the published order and using time only as a label | A rail whose numbers jump up and down as the reader scrolls, which trains them to stop reading it. | Editor |
| A relative time rewritten by script | Two clocks on one page, and a wrong one for every reader with script off. | Editor |
| A midnight stamp read as "the feed gave a date and no clock" | 47 of the 4,713 committed stories are stamped exactly `T00:00:00Z`, which is what a date-only feed date parses to - and it is also what a story genuinely published at midnight parses to. The payload cannot tell them apart, so printing `no time given` on that guess would mislabel a real midnight story, which is the invented-label failure the rail exists to avoid. | agent, 2026-09-02 |
| A service worker with no kill-switch | The one failure a static site cannot recover from: a reader pinned to a broken bundle with no way to reach the fix. This page named the condition before the worker existed, and the worker shipped with the switch written first. | Fowler |
| Precaching every published day on install | It spends a stranger's data on days they may never open, and it grows without bound as the archive grows. | Carmack |
| Background sync, so a day is ready before the reader arrives | Work on the reader's device that they did not ask for, on a schedule we chose. It is the same instinct push notifications come from. | owner |

## See also

- [digest.md](digest.md) - the item this shell frames.
- [design-system.md](design-system.md) - the tokens and states the chrome uses.
- [telemetry.md](telemetry.md) - the browser-console logging rule.
- [evaluation.md](evaluation.md) - what the dashboard renders.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the shape of each surface, the read mark, and the console.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the routes these surfaces sit on.
- [../how-to/ship-to-github-pages.md](../how-to/ship-to-github-pages.md) - the deployment runbook and base-path handling.
- [../../CLAUDE.md](../../CLAUDE.md) - section 12, the published-site verification gate.
