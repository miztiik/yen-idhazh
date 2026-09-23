# The served day, and the documents that stopped being written

**Last Updated**: 2026-09-23

A dated address used to be answered by a document a build wrote for that date.
It is answered by one shell and one fetched file now. This page holds that
migration: what the served day carries, what it costs an item, what the 116
deleted documents were worth, and the date the runway it bought runs out. The
day payload it is a projection of is [layout.md](layout.md); the routes that
fetch it are [frontend.md](frontend.md).

## Two projections, and what one day costs

Two copies of every day used to carry the vector block, and no browser has ever opened it. Its one production reader is the backend's index rebuild, which reads `frontend/public/` off the filesystem. So both copies are narrowed on the way out, in the two places the narrowing can happen:

- **`payload.ts` `loadDay` drops `embeddings` after the parse.** Whatever that function returns is inlined into every prerendered document that renders the day, and there are twelve of those per day - six documents and their six `__data.json` twins.
- **`copy-visuals.mjs` stages a projection rather than a copy.** A named allow-list of thirteen item fields, a one-line projector, and a guard that fails the build if a forbidden name ever reaches the list. That is the shape [../../../backend/idhazh/telemetry/publish/public_telemetry.py](../../../backend/idhazh/telemetry/publish/public_telemetry.py) already uses to keep URL keys and free text out of the console, and it is copied on purpose: a projection that has quietly widened looks exactly like one that has not.

**Both narrowings are written once, in [../../../frontend/src/lib/payload/project.ts](../../../frontend/src/lib/payload/project.ts).** They used to be two rules in two files: the allow-list sat in the build script, where TypeScript could not read it and the page loader could not import it, and the vector drop was a separate two-line statement of the same idea. Since 2026-08-31 the list, the projector, the forbidden-name guard and the vector drop are one module that both callers import. The module imports nothing itself, because the staging step is run by plain `node` before Vite starts and reaches it through node's own type stripping. Nothing about the bytes moved: all ten published days stage byte-identical, and so does the built site.

`frontend/public/` keeps the whole day, block and all. It is committed, it is in git, and it is the only store the vectors have.

Measured 2026-08-27 on a developer machine / / node 24.12.0, over the six committed days, 2,237 items and 2,235 vectors. Page weights are `gzip -9` of the prerendered HTML, taken by the bundle gate itself, heaviest page per route. Site totals are the sum of file sizes under `frontend/build/`, which agreed with CI's own `du -sb build` on the same tree to 0.0006 percent.

| Measured | Before | After | Saved |
| --- | ---: | ---: | ---: |
| `/<date>/`, gzipped | 581,557 B | 349,259 B | 232,298 B, 39.9 percent |
| `/<date>/<topic>/`, gzipped | 581,034 B | 348,566 B | 232,468 B, 40.0 percent |
| `/`, gzipped | 499,670 B | 302,122 B | 197,548 B, 39.5 percent |
| `static/digest/`, on disk | 6,976,807 B | 3,620,375 B | 3,356,432 B, 48.1 percent |
| The whole published site | 146,696,452 B | 128,064,853 B | 18,631,599 B, 12.7 percent |
| One published day | 22,200,123 +/- 1,785,970 B | 16,641,956 +/- 1,294,368 B | 25.0 percent |

Two of those rows are worth reading rather than scanning. **Two fifths of a day page was a block nobody could open**, which on the 10 Mbit reference line is about 0.19 seconds a reader waited for nothing, on every dated page they ever opened. And **the per-day row is the one that moves the cap**, because it is what the site charges for tomorrow rather than what it charges for the past.

The per-day figures are the three mature days only - 2026-08-24, -25 and -26, at 731, 724 and 621 items. The first three days ran 4, 10 and 147 items, and mixing them halves the answer. The spread is the sample standard deviation over those three days. The before figure lands 3,419 bytes from the 22,196,704 the same rate was measured at independently the same day, which is 0.015 percent, so the two measurements are the same measurement.

**The staged tree does not fall to nothing, and the floor is pictures.** 1,055,600 bytes of it is 87 rendered SVGs that the day pages fetch at runtime, and a projection must not touch those. The `digest.json` half went 5,921,207 -> 2,564,775 bytes, which is 56.7 percent off.

## The served day is a contract, and its address stops being movable

The staged file is now [../../../schemas/digest-view.schema.json](../../../schemas/digest-view.schema.json), generated from [../../../backend/idhazh/contracts/digest_view.py](../../../backend/idhazh/contracts/digest_view.py), and every staged day carries its `version`. Until this commit the shape was a thirteen-name array in a build script. That was honest while the only reader was our own archive page rendering a search result: both halves shipped in one build, so a widening could not surprise anybody.

**What changed is the consumer, not the file.** A reading route is about to fetch this day rather than inline it, so a browser we do not control parses it and a reader's cached shell can be older than the payload it reads. Two things follow, and neither is undone by rebuilding. `<base>/digest/<YYYY>/<MM>/<DD>/digest.json` becomes a public address. And the shape needs a stamp a shell can branch on, which is why `version` is here from the first byte rather than added when it is first needed - a version added later cannot help the shells that are already out.

**The read-side rule is one sentence: absent and null both mean unknown, and a reader may never fill either.** Every plausible default is a false claim - `0` for `carried_by` says no feed carried the story, `false` for `on_front_page` denies a vote nobody counted, `0.0` for `rank_score` puts the story at the bottom of its desk. The projector writes an explicit null for a key the committed day does not hold, so an older shell sees a key it knows with a value it can read, and a newer shell reading an older file sees the key missing. Both are the same fact.

**From here on, a breaking change to this shape needs the read-side migration in the shell, not only in the build.** Section 11 already required a migration; what is new is that the two halves are not upgraded together, so the migration has to live where the reader is. Additive is unchanged and stays cheap: declare the field optional, stamp the version, append the changelog entry, and an older shell ignores a key it does not know. **Changing the address is not a schema change at all - it is a broken bookmark**, and there is no version to branch on for that.

**Nine names joined the thirteen in the same commit, and each has a named renderer.** Measured 2026-08-31 on a developer machine / / node 24.12.0, 11 committed days and 3,733 items, `gzip -9` over the compact projection, each name added to the thirteen-field case on its own:

| Added | What draws it | Cost |
| --- | --- | ---: |
| `carried_by`, `watchlist_hit`, `on_front_page`, `rank_score` | the lead block, which needs a comparable score across the whole day | +0.94, +1.12, +1.11, +1.16 B an item |
| `published_at`, `time_source` | the time beside every story's heading | +8.29, +0.99 B an item |
| `introduced_by_run` | nothing, since the run divider was deleted on 2026-09-01. It stays because taking a field off this list is a contract change | +1.16 B an item |
| `lenses` | the topic chips | +1.11 B an item |
| `key_points` | the in-page filter, which reads them today | +93.54 B an item |

All nine together are +107.42 bytes an item rather than the +109.42 those nine sum to, because gzip shares what they have in common.

**`key_points` is nine tenths of that and it is the one worth defending.** `DigestList` filters on it now, so once a reading route fetches this file an absent `key_points` is a thrown `TypeError` rather than a narrower filter. The twelve prerendered documents it replaces carry the same words twelve times over, so on the wire it is cheaper here than it was there. Three names were refused: `events` and `entities` have no renderer and are out of scope as reader-facing chips (+1.63 and +1.80 B an item), and `source_form` has no reader at all (+1.21).

**On 2026-09-09 the file gained the day's own facts as well as its stories**, because the document that used to carry them stopped being written. That is recorded with its price under [the served day carries the day's own facts](#the-served-day-carries-the-days-own-facts).

**What it cost, end to end.** Two builds of this branch, one a case, back to back on the same machine, over the 11 days and 3,596 items on disk at the time: the staged payloads went 361.98 to 468.51 gzipped bytes an item, 29.4 percent more, and the 178 rendered images were untouched. A day landed while this row was in flight and took the tree to 3,733 items; the same arithmetic over that tree reads 361.10 to 468.58, which is the check that this is a rate and not a level - the two trees agree to 0.2 percent. The projection is still 40.9 percent under the committed day, which compacts to 792.65 gzipped bytes an item. No prerendered page moved: the six routes the bundle gate names read -1 to +6 bytes across the two builds, because a prerendered document reads the committed day and not this file.

**The runway, re-derived rather than restated (Guardrail #10).** Two cases of `idhazh site-weight` on the machine that publishes - `ubuntu-latest`, 2026-08-31, `main` at `bb7fd4a` against this branch at `82ebd5c`, both over the same 3,733 items in the same 409 files - read **44,009 against 44,700 bytes a published item**, a built site of 156.7 against 159.1 MB, and **129 against 127 published days to the 1024 MB Pages cap** (96 against 94 to the 800 MB alarm). A local pair on a developer machine / the same day read 44,578 to 45,267 and 128 to 126, which agrees to 1.3 percent and is the check that the platform is not the story. Those day figures divide the headroom by `run.safety_ceiling_per_run` - a per-run ceiling of 160 spent as a per-day rate. **Over the committed days a published day holds a median of 334 items and ranges from 4 to 731**, so the same headroom is 60.8 published days against 61.8: **this change costs about one published day of runway, and the cap arrives about 2026-10-31.** Both figures charge `assist/` and `_app/` - 65.6 MB, 41.2 percent of the site, neither of which grows with a day - to the items, so both are floors.

That is what this row spends. What it buys is the migration, and one day priced on a build of this branch says how much: **2026-08-30 is twelve prerendered documents totalling 8,822,134 bytes raw and 2,528,812 gzipped, against one served payload of 717,709 raw and 194,016 gzipped.** Twelve times the bytes, after this row grew the payload by 62 percent. The documents are the six HTML pages and their six `__data.json` twins, and every one of them carries the whole item list.

## The served day carries the day's own facts

A dated URL used to be answered by a document a build wrote for that date, and the day's own facts rode in it: the date, the desks and their counts, the leading block, the run list, and the counts the day notice reads. The served day carried the stories and nothing else, and that was enough while a page already holding the facts was the only thing fetching it.

**One shell now answers every dated URL, and no build writes a day into it.** So the browser has no other source for any of that: no topic pills, no leading block, no day notice, no story count and no date in the heading. The nine names below are the file's answer, and each of them has a named renderer.

| Added | What draws it |
| --- | --- |
| `date` | the day heading, and the link every story's own address is built from |
| `verticals` | the topic pills, with the count each one prints |
| `leads` | the leading block, and the anchors it points into the stream with |
| `runs` | the footer's run list, and the sentence naming how many runs published the day |
| `partial`, `items_failed`, `items_planned` | the day notice: a run that lost stories says so, and says how many of how many |
| `retention_window_months` | the footer's promise, stated before anything is deleted |
| `generated_at` | the revision key [../../../frontend/src/lib/assist/day.ts](../../../frontend/src/lib/assist/day.ts) has always read and never found, so a re-fetch that changed nothing now keeps the day the page is holding |

**Every one of them is optional, and that is the read-side rule rather than a softness.** The service worker keeps day payloads, so a shell built after this change can be handed a file written before it, carrying none of the nine. Absent is unknown: a page may not read an absent `partial` as false, an absent `items_failed` as 0, or an absent `verticals` as a day with no desk. `retention_window_months` carries the sharpest version of that - `-1` is the day saying nothing is deleted, and null is the payload not saying, so the footer prints neither sentence for a null.

**What it cost.** Measured 2026-09-09 on a developer machine / over the 20 committed days and 7,967 items, `gzip -9` over the compact projection, both cases built in one process so the nine names are the only difference between them: the served tree went **3,657,996 to 3,664,435 bytes**, which is **6,439 bytes over twenty days - 322 a day on average, 478 on the worst day, and 0.18 percent of what the tree already weighed.** The spread is worth reading: +140 on a four-story day and +478 on a 582-story one, because `verticals` grows with the number of desks and `leads` with how many the day named, and neither grows with the stories. **A day pays this once where an item field pays it per story**, which is why nine names here cost a fifth of what `also_covered_by` cost on its own.

What it buys is the 116 dated and topic documents the row below deletes, and the `__data.json` twin each of them had. 6,439 bytes spread across the days a reader opens, against a tree the build rewrites in full on every run.

**The contract keeps every check `DigestDay` holds over the facts it now carries.** `partial` is exactly whether anything failed, published plus failed cannot exceed planned, a desk's count agrees with the stories under it, and a lead names a story the payload holds. Each clause is skipped when the payload does not carry what it needs, so an older file is not failed for being older. A narrowing that keeps a fact and drops the rule on it is a weaker contract than the one it narrows, and this is the copy a browser reads.

## The dated documents stop being written

The two rows above moved the item list out of a dated document and left the document. This row deletes the document. **116 of them**: 20 for the published days and 96 for their topics, each with a `__data.json` twin, all rebuilt on every run because a document holding a seed of a day changes when the day does. `adapter-static`'s fallback, `404.html`, answers every dated address; the client router resolves the route out of the URL; the page fetches the served day.

Measured on a real build, a developer machine, 2026-09-09, `BUILD_VERSION` pinned across both cases:

| Measured | Before | After | Saved |
| --- | ---: | ---: | ---: |
| Files in `build/` | 796 | 572 | 224 |
| Bytes in `build/` | 116,050,183 | 101,880,352 | 14,169,831 B, 12.2 percent |
| Documents | 123 | 7 | 116 |
| `__data.json` | 121 | 5 | 116 |

**The oracle is the last row rather than the byte count.** A saving of 12.2 percent is a number about today's archive; what this row changes is the slope. Six documents a published day is what the tree used to charge, so the count moved every time the pipeline ran and nobody wrote a line - the shape Guardrail #12 is about. The count is 7 on a tree of 20 days and it is 7 on a tree of 400.

**The reader pays for it on a cold dated load, and only there.** A dated URL is now the fallback, the bundle, and then the day payload - which runs to 1.9 MB on the heaviest committed day - where it used to be one document of about 30 gzipped KB. In-app navigation never asks the host for a dated address, so only a typed link, a bookmark or a shared link takes that path (owner decision, 2026-09-09). What the page does not do is wait for the day: the fetch is started by the page component rather than awaited in its `load`, so the chrome and the date are on screen while the payload comes down, and past `ui.payload_slow_ms` one sentence says so. Awaiting it in the `load` was the simpler code and a blank page.

**Two entries left [../../concepts/growing-reads.md](../../concepts/growing-reads.md) and nothing replaced them.** Both dated routes' `entries` carried a `-1` because a cover on the list of pages a build writes stops writing them past it. There is no list of pages now, so the uncovered read did not move somewhere cheaper - it stopped existing, which is the only way one of those entries is meant to leave that page.

## The topic routes spend it

A topic route is the day filtered to one desk, and until 2026-09-01 the filter ran at build time in five documents a day. Each of those documents carried the **whole** day so a client-side filter could throw most of it away. Now the document carries the head of its own desk - `ui.shell_seed_items` stories - and a browser fetches the served day for the rest.

**The seed is the head of the desk's list, never of the day's.** The day publishes one order per run over the stories that run added ([../../concepts/placement.md](../../concepts/placement.md)), so the head of the whole day is the morning run's best stories rather than one desk's - and a topic route seeded from it would open on a screen holding almost none of its own.

**The seed is also the head UNION anything the document has to be able to anchor.** A prefix cannot hold a leading story: the reading-page plan's lead block picks across the whole day, and its five leads on the 601-story case sat at positions 249, 285, 337, 344 and 493. A lead link into a document that carries only a prefix lands on nothing until the fetch arrives, and on nothing at all when it fails. `dayShell` therefore takes a set of ids to keep whatever their position, and the union is what it seeds.

Measured 2026-09-01 on a developer machine / / node 24.12.0, over the 11 committed days, 4,086 items and 51 topic routes. Both cases built with `kit.version.name` pinned to one constant, because it defaults to `Date.now` and rides into every chunk filename ([../../reference/agent-notes/gates-and-builds.md](../../reference/agent-notes/gates-and-builds.md#running-the-gates)). A route is its two documents, `index.html` and its `__data.json` twin, at `gzip -9`:

| Measured | Before | After | Saved |
| --- | ---: | ---: | ---: |
| All 51 topic routes | 20,467,136 B | 1,153,865 B | 19,313,271 B, 94.4 percent |
| The heaviest, `2026-08-25/india` at 163 stories | 726,134 B | 25,665 B | 96.5 percent |
| The lightest, `2026-08-21/ai` at 4 stories | 10,190 B | 10,242 B | **52 B more** |
| Item ids the 51 documents carry | 20,414 | 686 | - |
| The whole published site | 168.6 MB | 101.9 MB | 66.7 MB, 39.6 percent |
| Bytes a published item | 43,264 | 26,143 | 39.6 percent |
| Published days to the 1024 MB cap | 130 | 231 | +101 |

**The spread is the interesting column, and one route went the wrong way.** Across the 51 routes the saving runs from **-0.5 percent to 97.0 percent**, median 93.4, mean 86.9, sample standard deviation 17.5. The negative one is a four-story desk: it fetches nothing, because its document already holds every story it has, and it pays 52 bytes for the loader and the waiting region it will never use. That is the honest shape of this change - it is a saving proportional to how much a desk publishes, and a desk that publishes almost nothing pays a flat toll instead.

**No story moved off the first screen.** The prerendered HTML draws the same 554 story elements across the 51 routes before and after, on every route individually. A flat list pages at twelve and the seed is fifteen, so the document still renders exactly what it rendered - what left is the payload behind the pager.

**The day route and the home page did not move**, which is the control: `/<date>/` read 350,435 against 350,427 gzipped bytes and `/` read 285,598 against 285,595, both inside the build noise. `/<date>/<topic>/` read 348,607 against 19,362 for the HTML alone.

## The day routes spend the rest of it

`/<date>/` was the last reading route inlining its whole day, and it is the one a shared link actually names. One document per published day, growing with the day it published: the twelve committed days carried 4,203 item payloads across twelve documents, and a reader who opens one day paid for the day they opened. It now carries the head of the day plus every story its leading block points at, and the browser fetches the served day for the rest.

**`/` keeps the whole day inline for ever, and that is a decision rather than an omission.** It is one document per build rather than one per published day, so it contributes nothing to the cap problem - the site could publish for a decade and `/` would still be one document. It is also the address a stranger meets first, and leaving it whole leaves one complete, crawlable, script-free digest on the site. `/404`, `/archive/`, `/evals/` and the console are untouched. That exception closed on 2026-09-10 and `/` carries a seed now; what replaced the argument, and the measurement that closed it, are in [frontend.md](frontend.md).

**This is the row that spends `keep`.** A dated page draws the leading block, and every entry in it is an anchor into the stream below. The leads are chosen across the whole day rather than off the top of the published order - on the twelve committed days the newest leads with stories at positions 0, 43, 46, 77 and 86 of 117 - so a document carrying a plain prefix would ship four links out of five that land on nothing until the fetch arrives, and on nothing at all when it fails. The seed is therefore the head UNION the day's leads, which costs the seeded item count and buys a deep link that resolves with no request at all.

**Two days of 117 stories priced the leads.** 2026-08-28 has none and saved 79.8 percent; 2026-09-01 has five, four of them past the head, and saved 73.9 percent. Four extra item payloads in the document is what a working leading block costs.

Measured 2026-09-01 on a developer machine / / node 24.12.0, over the 12 committed days and 4,203 items. Two builds of one worktree back to back; the control case is this branch's own changed files replaced by `main`'s in place, never a fresh extract, which carries its own byte offset from whatever gitignored state differs between two trees. A route is its two documents, `index.html` and its `__data.json` twin, at `gzip -9`:

| Measured | Before | After | Saved |
| --- | ---: | ---: | ---: |
| All 12 dated day routes | 4,217,706 B | 299,117 B | 3,918,589 B, 92.9 percent |
| The heaviest, `2026-08-25` at 724 stories | 723,497 B | 26,113 B | 96.4 percent |
| The lightest, `2026-08-21` at 4 stories | 10,164 B | 10,238 B | **74 B more** |
| Item payloads the 12 documents carry | 4,203 | 168 | - |
| The whole published site | 101.7 MB | 88.1 MB | 13.6 MB, 13.4 percent |
| Bytes a published item | 25,371 | 21,972 | 13.4 percent |
| Published days to the 1024 MB cap | 238 | 279 | +41 |

**The spread is the same shape the topic routes had, and one day again went the wrong way.** Across the twelve the saving runs from **-0.7 percent to 96.8 percent**, median 92.7, mean 74.9, sample standard deviation 36.0. The negative one published four stories: it fetches nothing, because its document already holds every story it has, and it pays 74 bytes for the loader and the waiting region it will never use. The saving is proportional to what the day published, and a day that published almost nothing pays a flat toll instead.

**No story left the first screen.** The stream pages at twelve and the seed is fifteen, so a document still renders exactly what it rendered - what left is the payload behind the pager. The unrendered half is what the numbers above are: 168 item payloads where 4,203 rode along.

**`/` and the topic routes are the control.** `/` read 67,534 gzipped bytes for its HTML on the case that changed the dated routes, and `/<date>/<topic>/` read 19,371 - both what the previous row left them at.

## The revisit trigger, with a date on it

**This does not solve the 1 GB cap (Guardrail #2). It buys about six weeks.**

At the rate above, the published site reaches 1,073,741,824 bytes on **2026-10-22**, which is fifty-six more published days counted from 2026-08-27. Before this change the date was **2026-10-07**, forty-one days. Across the measured spread on the rate, it runs from 2026-10-19 to 2026-10-28.

Almost all of that is the rate rather than the level: the 18.6 MB taken off the site today is worth 0.8 of a published day, and the 5.6 MB taken off every future day is worth 14.2.

**Nothing fires when that date arrives.** No gate measures the whole-site total against the cap - the bundle gate holds single pages, and the marker count holds what a page inlines. So the trigger is a date and not an alarm: **re-measure the site total and the per-day rate by 2026-09-22, one month before the date, and act on the answer.**

**The lever named here has now been pulled, and it moved the date a long way.** The prerendered dated route trees were 50,598,258 bytes and 39.5 percent of the site, and every one was a document a reader who opens some other day never reads. Five of the six a day were topic routes carrying the whole day, and those are now a seed. Measured 2026-09-01 on the same instrument that printed the numbers above, `idhazh site-weight` over 11 days and 4,086 items: **the site went 168.6 MB to 101.9 MB and the runway went 130 published days to 231** (96 to 175 to the 800 MB alarm). Both figures charge `assist/` and `_app/` - 65.6 MB, neither of which grows with a day - to the items, so both are floors, and both are worst-case days at `run.safety_ceiling_per_run`. The date to re-measure by is unchanged: an instrument that says a year is exactly the one nobody checks.

**The sixth document a day followed the same day, and the dated trees are done.** `/<date>/` was the last reading route inlining its whole day. Over the 12 committed days and 4,203 items on the same instrument, **the site went 101.7 MB to 88.1 MB and the runway went 238 published days to 279** (180 to 212 to the alarm). Reading the two rows together, the reading routes cost the site 168.6 MB and now cost 88.1, and the runway went 130 published days to 279 - it more than doubled. **Nothing about that removes the cap**, because the two directories that do not shrink are the ones that dominate: `assist/` at 43.2 MB and `_app/` at 22.4 MB are 74.5 percent of what is left, and neither grows with a day, so both are charged to the items and both make the runway a floor. **The next lever is retention ([retention.md](retention.md)), and there is no third document trick left to play.**

## The vectors are projected out, not moved out

Two copies of every day carried a block no browser opens, and there were two ways to end that.

**(a) Project at each boundary, which is what shipped.** `frontend/public/` keeps the whole day; each copy that leaves it drops what its own reader does not use. Two edits, no persisted shape moves, and it reverses by putting two lines back.

**(b) Move the vectors out of the day payload into a committed sibling file**, so there is nothing left to project. That is the tidier drawing, and it costs far more than it looks. `DigestDay` is `extra="forbid"` like every persisted model here, so a model without `embeddings` rejects every payload that carries one - all six committed days, 2,237 items. The bill is a read-side migration that strips the key forever, or a rewrite of every committed payload, plus a breaking schema stamp and its migration in the same commit ([../../../CLAUDE.md](../../../CLAUDE.md) section 11). Retention deletes nothing today, so waiting for the old shape to age out is not on offer either. And the reader ends up exactly where (a) already puts them: the block reaches no browser under either.

So (b) is a persisted-contract change that buys a cleaner diagram and zero bytes. (a) was taken on that arithmetic rather than on taste. If a real reason to split the file turns up - a second encoder, or a day payload too large to fetch whole - (b) is still there, and this paragraph is its price list.

**What (a) costs instead is a list that can drift.** Twenty-two field names in [../../../frontend/src/lib/payload/project.ts](../../../frontend/src/lib/payload/project.ts) decide what a fetched day is able to render, and dropping one fails nothing: the page comes out slightly shorter and the reader never learns what they lost. Four things hold it. The module refuses to load, and so fails the build, if a forbidden name reaches the list - the shape `public_telemetry.py` uses for the same class of mistake. `frontend/tests/staged-day.spec.ts` keeps its own copy of the names and holds the module's list against that copy, so widening the allow-list without widening the promise fails and names the field that arrived. `frontend/tests/search.spec.ts` drives the field where the loss would hurt most - the link out to the source - from the staged bytes through to the rendered link. And since 2026-08-31 the list is a generated schema as well: `test_the_projector_writes_exactly_the_shape_the_contract_names` reads the array out of the TypeScript and holds it against `DigestViewItem`, so a name added on one side of the language boundary and not the other fails rather than shipping a payload that does not match its own schema.

**The field that nearly came off the list is `source_url`.** A narrower set of title, summary, source name and band renders a result that looks complete and has no way out to the original. That is the reader's only means of checking what we wrote, so a projection that drops it trades their trust for about ten bytes an item.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Staging the day payload whole and narrowing only the prerendered pages | Measured 2026-08-27: the staged tree is 6,976,807 bytes of the 146,696,452-byte site, and leaving it whole gives back 3,356,432 of the 18,631,599 this change saved. Same two files open, one of the two edits skipped. |
| Serving `DigestDay` whole and deleting the projection | It is the same objection one level on, with a bigger number behind it. Measured 2026-08-31 over 11 committed days and 3,733 items, `gzip -9`: the committed day is 792.65 bytes an item against the projection's 468.58, so serving it whole is 69.2 percent more on the wire - and 40.0 percent of that is a vector block no browser opens. Bytes are what this migration is for. |
| Leaving the served field list a JavaScript array | It was the right answer while the only reader shipped in the same build. It stops being one when a browser we cannot upgrade parses the file: a persisted shape a reader's browser reads is a contract before logic reads it (Guardrail #3), and without a `version` an older shell has nothing to branch on when the shape next moves. |
| Moving the vectors out of the day payload into a sibling committed file | A persisted-contract change that buys no bytes. `extra="forbid"` means a `DigestDay` without `embeddings` rejects all 2,237 committed items, so the price is a read-side migration forever or a rewrite of every day - and the block already reaches no browser. See [The vectors are projected out, not moved out](#the-vectors-are-projected-out-not-moved-out). |
| Seeding a topic route from the head of the whole day | The day publishes one order per run over the stories that run added, so the head of the whole day is the morning run's best stories rather than one desk's - and the route would open on a screen holding almost none of its own. |
| A plain prefix as the seed, with no `keep` set | The leads are chosen across the whole day, and on the 601-story case they sat at positions 249, 285, 337, 344 and 493 - so four links in five land on nothing until the fetch arrives, and on nothing at all when it fails. |
| Awaiting the day payload in a dated route's `load` | The simpler code and a blank page. Starting the fetch in the page component puts the chrome and the date on screen while the payload comes down. |

## See also

- [layout.md](layout.md) - the committed day this file is a projection of, and the two contracts behind its address.
- [what-a-published-item-says-about-itself.md](what-a-published-item-says-about-itself.md) - the item fields the nine names above carry.
- [what-a-month-shard-holds-and-how-it-reaches-a-browser.md](what-a-month-shard-holds-and-how-it-reaches-a-browser.md) - the staging step, and the index a search result comes back through.
- [what-the-site-weighs-and-when-it-stops-fitting.md](what-the-site-weighs-and-when-it-stops-fitting.md) - the instrument every runway figure here came off.
- [frontend.md](frontend.md) - the shell that answers a dated address, and the eight routes still prerendered.
- [retention.md](retention.md) - the next lever, now that the document tricks are spent.
- [../contracts/schemas.md](../contracts/schemas.md) - `DigestView`, its version stamp and the read-side migration rule.
- [../../reference/site-weight.md](../../reference/site-weight.md#days-to-the-1-gb-pages-ceiling) - the cap date and the per-published-day growth rate.
- [../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md#the-site-page-by-page-after-the-payload-narrowing-2026-08-27) - what each page and the whole site weighed after the first narrowing.
