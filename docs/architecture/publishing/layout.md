# Published Layout

**Last Updated**: 2026-08-30

Where the pipeline writes what a reader reads, what a reader's URL looks like, and what may later be deleted. Assemble is the stage that produces all of it ([../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md)); this page owns the shape it writes into and the promises that shape makes.

## Two contracts, not one

The layout on disk and the address in the reader's browser are **separate contracts that are allowed to disagree**. This is the decision everything else on this page hangs off.

| | Shape | Optimised for |
| --- | --- | --- |
| **Data path** | segmented `<YYYY>/<MM>/<DD>/` | tree churn, and a single glob to prune a month |
| **Reader route** | one segment `<YYYY-MM-DD>` | a human reading it once, in a phone address bar |

Coupling them means a change of mind about URL aesthetics rewrites every committed payload. Separating them costs one pure function.

```
frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json     the whole day, every item
frontend/public/digest/<YYYY>/<MM>/<DD>/run.json        append-only runs[] for that date
frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.svg           optional visual
frontend/public/assist/index/<YYYY-MM>.json             one month of items, for browsing and search
frontend/public/assist/index/<YYYY-MM>.bin              that month's vectors, raw int8
state/scores.csv                                        the ledger - one path, never published twice
```

```
/                          the newest published day, rendered inline    moving
/<YYYY-MM-DD>/             that day, every vertical                     canonical
/<YYYY-MM-DD>/<vertical>/  that day, one vertical - a projection        canonical
/<YYYY-MM-DD>/#<item id>   an item anchor
/archive/                  every surviving day                          moving
/evals/                    the score dashboard                          moving
/console/                  the run-health dashboard                     moving
```

**One day directory is the deletion atom.** Nothing outside it points into its interior except the append-only ledger, which is what makes pruning a single operation with no second edit.

**No hash appears in any path, filename or URL.** A day carries two reader-facing addresses and both are the item's own id, `<vertical>-<ten digits>`: the anchor `#<item id>` and the rendered visual `ai-4821903756.svg`. The id is derived from the article's address, so a later run of the same day reaches the same item ([../sources/freshness.md](../sources/freshness.md)), and it is not a digest of anything - the ten digits are decimal and short enough to read back. The sha256 `url_key` that identity for dedupe actually rests on stays a field on the payload and never becomes a path segment. Paths are for humans and for globs; a hash is for the contract.

**The asset name was `<vertical>-<NN>` until 2026-08-27, and both shapes are live in committed data.** The ordinal came from a counter, a counter has to be seeded from something a process can observe, and two runs of one day observed different things - which cost a finished day ([visuals.md](visuals.md)). Naming the file after the item makes the path a function of the item, so no two runs and no two shards can pick one path for two stories. **No old address broke and none had to be migrated**: `assemble` copies `route.asset_path` into the day payload verbatim, the page renders that stored string, and the build stages by file suffix - so a name is data the day carries, never a rule the reader re-derives. That is the same property that makes the two contracts at the top of this page separable, applied one level down.

**`latest` and `archive` are derived at build time** from the directory listing, never committed. A committed pointer is exactly the file that goes stale after a prune or a raced deploy.

## The day is one artifact, shared by everyone

The pipeline adds to the day five times at the schedule in
[../../reference/github-actions.md](../../reference/github-actions.md). The
rule that governs what that means starts from a fact about the medium: **there
is one published payload, and every reader gets the same bytes.** Reading is
private and per-device; ordering is public and global. Ordering can therefore
never depend on who has read what.

- **The published order is global, deterministic and identical for every reader.** It is a pure function of the ranking inputs, and no reader's behaviour changes it. Two people opening the same dated URL see the same items in the same order, always.
- **An item is never removed, demoted or hidden because someone read it.** One person having read an item says nothing about the thousands who have not. This is the behaviour of every working news front page: the story stays where its importance puts it, read or unread.
- **Read-state is a client-side mark and nothing more.** It may change how an item looks. It may never change where an item sits, whether it appears, or how it ranks. The only exception is a filter the reader switches on themselves, and it is off by default.
- **"New" is a property of the item, not of the reader.** An item is new because a later run introduced it, which is true for everybody and needs no storage to assert. It is never a diff against a remembered last-visit time, which would be a claim that evaporates the moment a browser is cleared.
- **Membership only grows.** The runs of a day append to one day payload rather than replacing it, so the day grows through the day. That is only safe because an item's id comes from its address: run 2 recognises what run 1 already published instead of renumbering it. There is no daily item cap - what a day carries is what supply and the ranking produced ([../sources/freshness.md](../sources/freshness.md)).
- **A run can come back as itself, and that is one run.** Assemble writes `digest.json`, then builds the manifest, then writes `run.json`. A run that dies between those two writes leaves a day holding its items and a manifest that never heard of it, so the next run reads the same number off the manifest. The day therefore replaces the reference for a number it already has rather than adding a second one, and the count on that reference is every item the number introduced. The manifest appends instead, and does not need the same replace: its contract refuses a `runs` list that is not numbered from 1 without gaps, so the next number cannot already be taken. A guard there would be a branch nothing can reach.
- **The day's vectors grow with it.** A run encodes only the items it summarized, so it merges its block into the one the day already carried instead of replacing it. Replacing left a day searchable over its last run alone: the committed 2026-08-24 day held 145 vectors for 731 items, which is 19.8 percent of them. A newer vector wins a collision, because it was encoded from the newer text. A block that names another model, width or dtype replaces the old one whole rather than joining it.
- **An item's words are written once, by the run that introduced it.** No run revises. Three gates hold that, and all three are load-bearing for something else: `rank.plan_vertical` drops a candidate whose address is already in `state/published.csv`, `cli` supplies that set, and `assemble.build_day` drops an item the day already holds. The published item carries `updated_at` and `updated_by_run` for a revision that cannot happen yet, and both are null in every committed payload. **If a revision is ever built, it must be visible.** Silently improving wording under someone who already read it makes them doubt their own memory, and their trust in the summaries is the entire product.
- **No run identifier appears in any data path or any reader URL.** It lives in the run manifest and in the page footer.

The returning reader is protected by the read mark and by the run-scoped "new" grouping - both of which work identically for everyone - rather than by freezing an order, which cannot be done in a shared artifact without rendering a different page per person.

## One file per day

A day is one JSON payload carrying every item. A vertical route is a filter over that same payload, never a second file.

The consequence worth protecting: **rendering any page costs at most two requests, no matter how old the archive is.** Any scheme whose request count or index size grows with total history is rejected on sight, at any granularity. A per-item file multiplies requests and defeats compression - a small body never warms the gzip dictionary, where a whole day reaches the measured prose ratio. A global index of everything ever published grows without bound on the hot path.
**One page already breaks that rule, and there is now a number on it.** `/archive/` inlines every committed day so on-device search can see the whole corpus, which is the last rejected alternative below in everything but name. Measured 2026-08-26 over the six committed days, 2,121 items, at the gzip level the Pages edge actually serves: a browse entry - item id, date, vertical, title - costs **45.5 bytes**, and one committed int8 vector costs **249.8 bytes** ([../../reference/measurements.md](../../reference/measurements.md#sizing-the-archive-index)). A 30-day month is therefore 482 KB of browse entries and 2.6 MB of vectors at the rate those six days ran, and 1.07 MB and 6.0 MB at the ceiling that five runs of 160 items a day allows.

**Sharding by month does not by itself bound the browse index.** At 45.5 bytes an entry, 300 KB buys about 6,700 entries - a fortnight at the observed rate and eight days at the structural ceiling. A month shard is over 300 KB at every rate measured, so a shard granularity and an index budget have to be chosen together rather than one after the other. That is now done: the granularity is a month and the budget is 1.5 MB, both in [The month search index](#the-month-search-index) below.

**The gzip window settles long before a shard does.** Over the same corpus, per-item gzipped bytes barely move between a quarter of the blob and all of it: 249.6 to 249.8 for the vectors, and 47.3 down to 45.5 for the browse entries. So the compression argument above is about a per-item body of hundreds of bytes, not about a shard of hundreds of kilobytes - any shard past about 70 KB already gets the full ratio.

## The month search index

`frontend/public/assist/index/<YYYY-MM>.json` is one month of published items in published order, and `<YYYY-MM>.bin` is that month's vectors laid end to end as raw int8. The contract is `backend/idhazh/contracts/search_index.py`; the writer is `assemble.rebuild_search_index`. The archive's story list reads the JSON, and on-device search reads both.

The shard that exists costs **109.3 KB gzipped for 2,237 items, and 545 KB for their 2,235 vectors** ([../../reference/measurements.md](../../reference/measurements.md#the-month-search-index-as-written)). An entry is **50.03 gzipped bytes**, which is 10 percent more than the 45.5 the shape study above priced, because a real entry carries real key names and a vector offset the study's did not.

**A month shard does not break the bounded-request rule above, and here is why.** That rule rejects a scheme whose request count or index size grows with *total history*. A month shard's size is a function of one month, and the month ends; the hundredth month costs a reader exactly what the first one did. Request count is bounded the same way: a page reads the months it shows, which is one for a day page and a fixed pan for an archive view, not one per published day and never one per item. What the rule forbids is the file that has to get bigger every day forever, which is the global index in the rejected-alternatives table - measured at 12.7 MB of browse entries for a single year at the structural ceiling.

**An entry carries the item id, the date, the title and the vertical. Nothing else.** In particular no summary, no source and no band. Measured over the same 2,237 items: adding the summary takes an entry from 50.03 gzipped bytes to **317.52, which is 6.35 times**, and a 30-day month at the rate those six days ran from 518 KB to **3.21 MB**. That charges every browsing visitor the full text of every item in the month. A search result renders by fetching the day payload it names instead: ten results spanning ten days cost at most ten fetches, a day already open is reused, and the result renders through the same item component the digest page uses. That is what the day payloads are staged into `static/` for - see [How it reaches a browser](#how-it-reaches-a-browser).

**`vector` is an explicit byte offset into the `.bin`, or null.** Never a position in the entry list, never a padded zero vector, and the item is never left out. Two of the 2,237 committed items carry no vector today (0.09 percent), and the token-budget work will add more on purpose. Leaving them out would take them out of the browse list as well as out of search, which is the larger loss; a zero vector would be worse still, because it scores against every query. The offsets are dense and in entry order, which is what makes a rebuild byte-identical rather than merely correct.

**The vectors are a sibling file rather than base64 inside the JSON, and the margin is 22.5 percent.** 249.82 gzipped bytes an item against 322.55, measured over 2,119 committed vectors ([../../reference/measurements.md](../../reference/measurements.md#sizing-the-archive-index)) - not the 40 percent this was planned against. The real argument for the split is who pays: every visitor browsing a month pays the JSON, only a reader who searches pays the vectors, and a searcher has already accepted the encoder download. That makes the browse index the only ceiling that matters. **No `DecompressionStream` fallback is needed**: GitHub Pages compresses `application/octet-stream` at gzip level 5, measured directly against the live origin, so a raw `.bin` already transfers compressed. It never serves brotli.

**The JSON is compact - no indent, no separator spaces.** Every other committed payload is pretty-printed because reviewing its diff by eye is worth the bytes. This one is thousands of entries a reader downloads whole, and the indent would roughly double it.

**The header states its own quantisation `scale` from the first commit.** It is `1/127` today, which is the step the committed vectors were made with, and the index cannot tighten it: it projects bytes that are already int8, and re-scaling an integer adds rounding rather than recovering precision. A tighter corpus-wide scale is worth about four times less score noise at zero extra bytes an item, and it has to be applied where the floats still exist - in the encoder, in the commit that re-dates every vector. The field is here now so that change is additive instead of breaking.

### When to reconsider the month

A ceiling with no revisit point is how the last one was set wrong. Two numbers fire, and the third is the second one counted a way you can see coming:

| Quantity | Observed rate | Structural ceiling | Revisit at | What changes |
| --- | ---: | ---: | ---: | --- |
| Browse index, one month, `gzip -5` | 518 KB | 1.15 MB | **1.5 MB** | Shorten the period to `<YYYY-Www>`, exactly as an over-large ledger shard does ([../sources/item-health.md](../sources/item-health.md)). The readers glob the directory, so the period is a layout change and not a contract change. |
| Vector file, one month, `gzip -5` | 2.53 MB | 5.72 MB | **8 MB** | Revisit the dtype before the period. One bit a component is 48 bytes a vector against 384; what that costs recall is unmeasured, and measuring it is the work. |
| Items in one month | 10,605 | 24,000 | **34,000** | The same line as the row above, in the unit a plan is written in: 8 MB divided by 249.79 gzipped bytes a vector. |

**Why 1.5 MB and not the size it is today.** 1.5 MB is 30 percent above what the structural ceiling projects, and the structural ceiling is five cron slots times a safety ceiling of 160 items. So the trigger fires exactly when somebody widens one of those two - a sixth slot alone puts a month at 1.38 MB - and not on an ordinary busy month. On the 10 Mbit reference line it is 1.2 seconds, against 0.9 seconds at the ceiling today.

**Why 8 MB for the vectors.** Only a reader who searches downloads them, and that reader has already accepted the encoder: 22.97 MB on disk, 16.22 MB on the wire. 8 MB is half of what they already said yes to, and 40 percent above the ceiling projection.

**The 300 KB figure this was planned against is retired.** It was written before anything was measured, and the measurement says no shape gets under it: the leanest entry that still browses - date lifted to a key, vertical dropped because it is already the item id's prefix - is 41.51 bytes, and a month is still over at every rate. 300 KB buys about 6,000 real entries, which is 17 days at the observed rate and 7 at the ceiling. The numbers above replace it.

### The shard is derived, so retention needs nothing

A month shard is rebuilt whole from the day payloads that are on disk at the time. There is no incremental path, so there is no read-modify-write for two runs of a day to race on and no repair command for when they do. **Deleting a day and re-running assemble regenerates a correct shard**, because the rebuild simply does not find the day it used to name. That is the entire retention obligation, and it is discharged by construction rather than by a rule somebody has to remember.

The rebuild costs one pass over the month's committed payloads: **88 to 122 milliseconds for 2,237 items**, and about one second projected at the structural ceiling of 24,000, against the assemble job's 20-minute timeout. That is one tenth of one percent of the budget (Rule #2).

The obligation that does need stating: **every writer of a committed day payload owes its month a rebuild.** There are three - the assemble stage, the one-shot `backfill-vectors` command, and `backend/utilities/build_canary_day.py`, which writes twenty fixture days for the browser suite to browse. A fourth would have to.

### The suite rewrote the shard it was meant to project (2026-08-27)

The writer was right from its first commit and the shard on `main` was not. It held **one** entry - `ai-01`, "Example Lab releases a smaller model" - against six committed days holding 2,237 items, and no published day holds that item at all. A rebuild over the committed tree produces 2,237 entries and 2,235 vectors, so the arithmetic was never in question.

The cause was the path. `cli.stage_assemble` took the index root from a module constant while every pipeline test redirects `PUBLIC_ROOT` at a temporary tree, so **running the backend suite rebuilt the published shard out of fixture days**, on any machine that ran it. Nothing failed; the file was simply wrong afterwards, and it was committed that way.

The fix is the shape `publish_telemetry` already had: the index root is derived from the digest root at the call site rather than kept as a constant of its own, so a caller that moves the days moves the index with them. Two tests hold it - one that the derived root follows a redirected `PUBLIC_ROOT` out of the repository, and one that the shard on disk names exactly the days on disk. The second is the reader-facing half: the archive lists what that file holds, so a shard that disagrees with the tree is a page listing the wrong stories.

**The general shape is worth more than the instance.** A constant that names an output path is safe only until a caller redirects a *sibling* path, and the failure is silent by construction: the code runs, the file is written, and the only symptom is in a file nobody re-reads.

### How it reaches a browser

`frontend/public/` is where `backend/` writes and the site reads **through the filesystem at build time**. Only `frontend/static/` is copied into the served bundle, which is why [../../../frontend/scripts/copy-visuals.mjs](../../../frontend/scripts/copy-visuals.mjs) stages rendered images and the telemetry projection across. Three more kinds of file ride that same step from 2026-08-27: `<YYYY-MM>.json` and its sibling `<YYYY-MM>.bin` into `static/index/`, and every day's `digest.json` into `static/digest/`.

**The index is staged beside the encoder, never inside it.** `static/assist/` is the on-device encoder and its wasm - authored files, committed, and secondary by contract: the bundle must render complete with that directory deleted ([../../../CLAUDE.md](../../../CLAUDE.md) section 0a), and CI proves it by parking `static/assist`, building, and asserting the bundle carries no `assist/` at all. Browsing the archive is not a model feature. It is how the page lists anything, so the data it needs cannot live in a directory whose whole contract is that it can be removed. The index therefore gets its own top-level tree, the same shape `static/digest/` and `static/telemetry/` already have: one directory per staged projection, ignored by git, rebuilt every build.

**The `.bin` goes there too, even though only a searching reader fetches it.** It is one shard in two files, so splitting them across two paths would buy nothing, and the reason the directory is wrong has nothing to do with who reads the file: staging runs inside `npm run build`, so anything written under `static/assist/` reappears after the gate has parked it.

**The first placement was inside `static/assist/index/`, and CI caught it the same day.** `build/assist` existed on a build that had otherwise succeeded, and the gate failed. Read as a gate problem it invites an exclusion. It was a path problem: two different things, one directory.

**The `.bin` is staged because something finally opens it.** It was left out while the index shipped unconsumed - megabytes in the bundle for a file no page fetched - and search reading the index is the commit that earns it.

**The day payloads are staged because a search result renders from the day it names.** The index carries no summary on purpose, so the result has to come from somewhere, and the alternative is a 6.35-times-larger index that every browsing visitor pays for. `run.json` is not staged; nothing fetches it.

That is a second copy of the day in the published bundle, and it is worth stating plainly rather than discovering later. **Only a reader who searches ever downloads one**, and only for a day a result of theirs sits on - the reading path is still one prerendered document and zero requests.

**It is not a second copy of the day, though, because it is a projection.** The staged file carries thirteen fields an item - the ones a search result actually renders - and nothing else. That is settled below, with what it cost and what it bought.

**The staging source is derived from the digest root, in the script and in the page loader alike**, because an index is a projection of exactly those days. One switch rather than two is what stops a canary build serving the real archive's stories.

**The archive fetches the index rather than inlining it, and that is the whole point.** Every other committed payload this site renders is read at build time and baked into the HTML, which is right for a day page: the day is bounded and the reader came to read it. The archive is the corpus. Inlining it would grow one document by about 50 gzipped bytes an item forever, which is the defect this index exists to end. The console already settled this shape - a bounded seed in the HTML, older months fetched from `static/` on demand - and the archive uses the same mechanism rather than inventing a second one. What the archive page still carries from its own data is a compact day row, three counts and about twenty topic names: all of it grows per day or per month, none of it per story.

**A missing index is a designed state.** The page falls back to the day row and one plain sentence. It never white-screens ([../../../CLAUDE.md](../../../CLAUDE.md) section 12).

### Two projections, and what one day costs

Two copies of every day used to carry the vector block, and no browser has ever opened it. Its one production reader is the backend's index rebuild, which reads `frontend/public/` off the filesystem. So both copies are narrowed on the way out, in the two places the narrowing can happen:

- **`payload.ts` `loadDay` drops `embeddings` after the parse.** Whatever that function returns is inlined into every prerendered document that renders the day, and there are twelve of those per day - six documents and their six `__data.json` twins.
- **`copy-visuals.mjs` stages a projection rather than a copy.** A named allow-list of thirteen item fields, a one-line projector, and a guard that fails the build if a forbidden name ever reaches the list. That is the shape [../../../backend/idhazh/publish_telemetry.py](../../../backend/idhazh/publish_telemetry.py) already uses to keep URL keys and free text out of the console, and it is copied on purpose: a projection that has quietly widened looks exactly like one that has not.

`frontend/public/` keeps the whole day, block and all. It is committed, it is in git, and it is the only store the vectors have.

Measured 2026-08-27 on Intel Core i7-1265U / Windows 11 / node 24.12.0, over the six committed days, 2,237 items and 2,235 vectors. Page weights are `gzip -9` of the prerendered HTML, taken by the bundle gate itself, heaviest page per route. Site totals are the sum of file sizes under `frontend/build/`, which agreed with CI's own `du -sb build` on the same tree to 0.0006 percent.

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

### The revisit trigger, with a date on it

**This does not solve the 1 GB cap (Rule #2). It buys about six weeks.**

At the rate above, the published site reaches 1,073,741,824 bytes on **2026-10-22**, which is fifty-six more published days counted from 2026-08-27. Before this change the date was **2026-10-07**, forty-one days. Across the measured spread on the rate, it runs from 2026-10-19 to 2026-10-28.

Almost all of that is the rate rather than the level: the 18.6 MB taken off the site today is worth 0.8 of a published day, and the 5.6 MB taken off every future day is worth 14.2.

**Nothing fires when that date arrives.** No gate measures the whole-site total against the cap - the bundle gate holds single pages, and the marker count holds what a page inlines. So the trigger is a date and not an alarm: **re-measure the site total and the per-day rate by 2026-09-22, one month before the date, and act on the answer.**

What to act on is already named. The prerendered dated route trees are 50,598,258 bytes, 39.5 percent of the whole site, and every one of them is a document that a reader who opens some other day never reads. They were 65,197,022 bytes and 44.4 percent before this change, so narrowing the payload made them smaller without making them a smaller share of the problem. That is the next lever, and retention (below) is the one after it.

## Retention

Retention exists to bound the **published site**, which has a hard ceiling. It does nothing for repository size: deleting a committed file leaves the blob in history forever, and rewriting history is forbidden ([../../../CLAUDE.md](../../../CLAUDE.md) section 8). Anything that must not grow the repository must not be committed at all.

The levers are ordered, and deletion is the last one:

1. **Encode efficiently.** Images are the overwhelming majority of the bytes; the encoding choice alone moves the ceiling by years.
2. **Honour the visual rule.** "Nothing" is the common and correct answer ([../../concepts/digest.md](../../concepts/digest.md)), so most items carry no image at all.
3. **Then, and only if still needed, prune.**

After the first two, the knob may never need to be switched on. That is the intended outcome, not a fallback.

What the job may do: delete rendered visuals older than a configured age, never on a size trigger, dry-run by default, refusing to act above a maximum-deletions fuse, in its own scheduled workflow that can never take the daily digest down with it. A pruned visual is a **distinct state from a failed render** - "we could not make this" and "we made it and threw it away" are different facts, and one field must not mean both.

What it must never touch: a day's JSON payload, a date directory, the eval ledger, the golden fixtures including retired ones, the injection canaries, or any schema changelog. The ledger and the fixtures are three orders of magnitude smaller than the images and are the only reason a year-over-year quality claim can be interpreted at all.

Two promises to the reader, both non-negotiable: **the window is stated before anything is deleted**, on the archive page and on the missing-day page; and a pruned day lands in the designed missing state, **never a silent redirect to today**. A reader who cannot distinguish a dead link from a live one has lost the ability to trust any link.

The archive states it in its own header from 2026-08-27, and **the sentence names what is actually deleted**. The knob is `retention.image_months` and the job it drives may remove a rendered chart and nothing else, so "Charts older than N months are deleted. Every story and every link stays." is the promise, and "Nothing here is deleted." is what ships today at `image_months: -1`. The footer used to say days were removed, which promised the opposite of what the code does; it now says the same thing the archive does, because two sentences disagreeing about deletion on one page is the exact failure this section exists to prevent.

### Follow-up: the dated route trees are what decides the cap date (2026-08-27)

**Recorded, not fixed. No row has addressed it.**

The prerendered dated routes are **50,598,258 bytes, 39.5 percent of the published site** - measured 2026-08-27 on an Intel Core i7-1265U, Windows 11, node 24.12.0, over the six committed days and 2,237 items ([../../reference/measurements.md](../../reference/measurements.md#what-is-left-and-where-it-is)). They were 65,197,022 bytes and 44.4 percent before PR #171 narrowed the staged payload.

That is **twelve prerendered documents per published day**: six HTML pages - the all-topics page and one per vertical - and their six `__data.json` twins. Every published day adds twelve more, forever, and nothing else on the site grows per day at anything like that rate. So this is the number the 1 GB cap date is a function of: at 16,641,956 bytes a published day the site reaches the cap on about 2026-10-22, and about 39.5 percent of each of those days is this.

The three levers this page already names - encode efficiently, honour the visual rule, then prune - were all argued about images. **None of them touches an HTML document.** Whatever answers this is a fourth thing, and it has not been designed. What is written down here is the measurement, so the next person starts from a number rather than a feeling.

### What bounds the committed state tree

`state/` is the other tree that grows every run, and it is bounded separately, because what it costs is a checkout rather than a deploy. Measured on this checkout 2026-08-30, over the eight days the ledgers then held:

| File | Bytes | Share of `state/` | Bounded by |
| --- | --- | --- | --- |
| `state/seen/<YYYY-MM>.csv` | 5,166,315 | 54.5 percent | **nothing** |
| `state/scores.csv` | 2,359,230 | 24.9 percent | **nothing** |
| `state/item-health/<YYYY-MM>.csv` | 1,270,452 | 13.4 percent | `observability.keep_months` |
| `state/published.csv` | 338,979 | 3.6 percent | nothing, and deliberately - published is forever |
| everything else | 352,309 | 3.7 percent | small enough not to ask |

**The fold covers `state/item-health/` and only that.** A month older than `observability.keep_months` is read whole, folded to one row per `(date, stage)` in `state/telemetry-aggregate/<YYYY-MM>.csv`, and the full-grain shard is deleted - in that order, with the aggregate read back before the shard is unlinked, so a fold that cannot be written leaves the shard where it was. Thirteen months, because `console.max_window_days` is 366 and a shard has to answer for a year with the current month still being written.

**Measured on this checkout, 2026-08-30.** Folding the committed `state/item-health/2026-08.csv` - 4,167 rows over six published days, 1,270,452 bytes - gives 24 aggregate rows and 1,531 bytes: **829.8 times smaller**, 63.8 bytes an aggregate row, 255.2 bytes a published day, 93,136 bytes a year against the shard's 77,285,830. Four rows a day and not five, because `plan` wrote no row that month.

Three things make it the one ledger the fold reaches, and each of them is why the other two need a decision of their own rather than a copy of this one:

- Its rows carry a `stage`, which is what the aggregate is keyed on. A `seen` row is an address and a timestamp; a `scores.csv` row is a faithfulness measurement. Neither folds to `(date, stage)`.
- It shards by month, so a fold is a whole file appearing and a whole file going. `state/scores.csv` is one file, and bounding it means either sharding it - a change across four readers, `payload.ts`, `model-work.ts`, `drift.py` and `label_queue.py` - or rewriting it in place.
- It is a measurement whose totals are worth keeping. `state/seen/` is a lookup, read only through `collect.seen_window_days`, so a shard past that window answers nothing and its honest retention is deletion rather than a fold.

**What this does not do, stated plainly: it does not bound the `/console/` document.** That page is linear in items at a measured 50.45 gzipped bytes an item and crosses its 301,580-byte ceiling on published day 16, because the compression scatter inlines every row `state/scores.csv` has ever held. Thirteen months is roughly published day 395. The two problems share a file and share nothing else, and the fold cannot be read as an answer to the page.

The aggregate is kept forever by default. `observability.hard_delete_after_months` is null, and the contract refuses a value at or below `keep_months` - so a month is never deleted before it has been folded.

## The frontend stack

Svelte 5, Vite, TypeScript, Tailwind, vitest, Playwright, `json-schema-to-typescript`, and `ajv`.

The spine matches both sibling projects, so tooling knowledge transfers across a one-maintainer estate. The profile is deliberately the leaner of the two siblings: this site renders a small committed JSON payload and needs no query engine, no charting library and no map projection. `ajv` rather than `zod` because it validates against the committed JSON Schema that the contract drift gate already generates, where `zod` would require a second generator feeding the same gate.

Runtime inference in the browser is not a stack choice to be weighed; Rule #1 forbids it.

## Design rationale

The reader-facing half of this design is driven by one asymmetry: a reader who loses trust does not complain, they simply stop coming back, and nothing in any test suite detects it. So the failure modes that shape the layout are the silent ones - a bookmark that looks healthy but is a year stale, a page that quietly rearranges between two readings, a link that redirects somewhere plausible instead of admitting it is gone.

That is why the plain address is the moving one and dated addresses are the frozen ones, rather than the reverse. The tempting design makes the dated page canonical and the front page a pointer to it; the failure it invites is a front page that lags, which presents as a perfectly healthy site showing last month's news.

The engineering half is driven by arithmetic rather than preference. Segmented date directories were chosen over a flat layout because a flat directory of tens of thousands of entries rewrites a large tree object on every commit. One file per day was chosen over per-item files because compression works far better across a whole day than across many small bodies, and because a per-item file buys nothing an already-fetched day payload does not have.

### The two revision fields stay, unwritten (2026-08-26)

This page used to say "A revision is visible or it does not happen", which reads as a description of shipped code and is not one. No run can revise an item, so nothing has ever had the chance to be visible or silent. The sentence is now what the system does, with the promise kept as the rule a revision would have to meet.

**Deleting the fields is not the cheap option it looks like.** Every persisted model is `extra="forbid"`, so a model without the two fields rejects every payload that carries them. Measured on this checkout, 2026-08-26: six committed days, 2,121 items, 2,121 carrying `updated_at`, 2,107 carrying `updated_by_run`, and **zero** carrying a value in either. Removal costs a read-side migration that strips two keys from every day forever, or a rewrite of all six committed payloads. Retention deletes nothing today (`image_months` is -1 and `dry_run` is on), so waiting for the old payloads to age out is not available either. That is the whole price, and the reader gets nothing for it.

**The named trigger that would revive revision is a summarizer model swap, and it fired on 2026-08-27** ([../../concepts/evaluation.md](../../concepts/evaluation.md)). A better summarizer is the one event that makes words already published worth rewriting; a bug fix in the pipeline is not, and neither is a new field. Nothing was revised, and that is the correct answer here rather than an oversight: no comparison against the retired model was ever run, so nothing measured says the new summaries are better, and rewriting published words on an unmeasured hunch is the move Rule #10 forbids. What the swap does change is the run-manifest join the two fields exist for - from the first day the new model publishes, a day can hold summaries from two different models, so the join now has something to join.

**The promise is pinned by a test, not by this paragraph.** `backend/tests/test_pipeline.py` asserts that a second run over an item the day already holds leaves its words, its `updated_at` and its `updated_by_run` untouched. A sentence on a page drifted once; the test fails the day the gates stop holding, which forces this page to be corrected in the same commit.

Retention was demoted to third lever after the byte arithmetic showed that encoding and the existing visual rule together move the ceiling from months to years. A policy that deletes a reader's archive to reclaim a fraction of a percent of the bytes would have been solving the wrong problem.

### The vectors are projected out, not moved out (2026-08-27)

Two copies of every day carried a block no browser opens, and there were two ways to end that.

**(a) Project at each boundary, which is what shipped.** `frontend/public/` keeps the whole day; each copy that leaves it drops what its own reader does not use. Two edits, no persisted shape moves, and it reverses by putting two lines back.

**(b) Move the vectors out of the day payload into a committed sibling file**, so there is nothing left to project. That is the tidier drawing, and it costs far more than it looks. `DigestDay` is `extra="forbid"` like every persisted model here, so a model without `embeddings` rejects every payload that carries one - all six committed days, 2,237 items. The bill is a read-side migration that strips the key forever, or a rewrite of every committed payload, plus a breaking schema stamp and its migration in the same commit ([../../../CLAUDE.md](../../../CLAUDE.md) section 11). Retention deletes nothing today, so waiting for the old shape to age out is not on offer either. And the reader ends up exactly where (a) already puts them: the block reaches no browser under either.

So (b) is a persisted-contract change that buys a cleaner diagram and zero bytes. (a) was taken on that arithmetic rather than on taste. If a real reason to split the file turns up - a second encoder, or a day payload too large to fetch whole - (b) is still there, and this paragraph is its price list.

**What (a) costs instead is a list that can drift.** Thirteen field names in [../../../frontend/scripts/copy-visuals.mjs](../../../frontend/scripts/copy-visuals.mjs) decide what a search result is able to render, and dropping one fails nothing: the result comes out slightly shorter and the reader never learns what they lost. Three things hold it. The script asserts that no forbidden name is on the list and fails the build if one is, which is the shape `publish_telemetry.py` uses for the same class of mistake. `frontend/tests/staged-day.spec.ts` keeps its own copy of the thirteen names, so widening the script without widening the promise fails. And `frontend/tests/search.spec.ts` drives the field where the loss would hurt most - the link out to the source - from the staged bytes through to the rendered link.

**The field that nearly came off the list is `source_url`.** A narrower set of title, summary, source name and band renders a result that looks complete and has no way out to the original. That is the reader's only means of checking what we wrote, so a projection that drops it trades their trust for about ten bytes an item.

### Two append paths, and only one of them deduplicates (2026-08-27)

`idhazh.ledger._append` writes every row it is handed. `idhazh.evals.writer.append` refuses a row whose address, inputs, words and scorer version it already holds. That looked like one of them being wrong, and it is not: **the two write different kinds of row.** An eval row is a measurement, so re-measuring an item nothing changed about has nothing new to say. A state row is a fact about a run - this feed answered at this hour, this item finished - and a run that runs twice did happen twice. Collapsing those would turn a count of runs into a count of days.

So the blind path stays blind, and each caller that owns a repeat is now named next to it. Two of the four ledgers absorb a repeat at read time: `load_seen` and `load_published` keep the earliest of two rows, so a duplicate costs bytes and never moves a date. The health pair does not, and that is stated rather than guarded: `discover.resting` counts failures to decide a quarantine, so a duplicated failure counts twice. Measured on this checkout 2026-08-27, `state/published.csv` holds 2,097 rows and 2,097 distinct addresses.

**Where the code was already safe, the fix was a sentence and not a guard.** A guard that can never fire is untested branch weight, and it hides which file the guarantee actually lives in. `cli._published_rows` reads as "everything the day holds" and behaves as "what this run added", and it does that because the plan a later run built has already dropped every published address. Its comment used to claim the filter itself; it now names the upstream facts it depends on, so the next person to widen the plan sees what they would break.

**One path was not safe, and that one was fixed.** The day's run reference counted what the current attempt added rather than what the number introduced, so a replay after a lost manifest write built a payload its own contract rejects - `run 1 items_added disagrees with the items it introduced` - and the day was lost rather than doubled. The count now comes from the assembled day, which is the definition the contract validates against.

### The site alarm watched a tree eighteen times smaller than the site (2026-08-27)

The 1 GB cap is on the **built bundle** - `frontend/build/`, the directory the Pages deploy uploads. The alarm measured `frontend/public/digest/`, which is what the pipeline writes. Measured 2026-08-27 on this checkout: **7,027,075 bytes against 128,064,853**, eighteen times apart, and twenty-one times apart the day before. At the rate the payload tree grows, an alarm point of 800 MB on it could not have been reached until the site was already about six times past the cap. **The alarm ran every pipeline run, cost real seconds, and would never have warned anybody.** That is worse than no alarm, because a green light is read as safety.

The recorded arithmetic had the same units error and it is corrected in [../../reference/measurements.md](../../reference/measurements.md#days-to-the-1-gb-pages-ceiling): the site crosses 1 GB on about **2026-10-22, 56 published days from 2026-08-27**, not the 593 or 516 days that page carried.

**Re-derived 2026-08-29 at the close of the design-system reset, and the number moved for a reason worth stating.** The built site is 143,717,288 B and the cap is about 94 published days out, near 2026-11-30. That is not the reset making the site smaller - the reset made every route slightly larger. It is that the two most recent days carried 117 and 212 items where the days behind them carried 731, and a day rate averaged over whatever days are on disk moves when the item mix moves. The stable unit is **24,378 B per published item, spread 23,066 to 26,538** over the seven mature days. Divide that by the item ceiling in force to get a day rate, rather than averaging days. Full working in [../../reference/measurements.md](../../reference/measurements.md).

**The fix is to measure where the site exists.** The bundle does not exist while `assemble` runs - it is built by a later step - so the measurement moved out of the assemble stage and became its own step, `idhazh site-weight --site-tree build`, in every job that builds the site: `ci.yml`'s `site` job, `digest.yml`'s `assemble` job, and `backfill.yml`. It runs before the commit that publishes a day, so a day that would break the site never lands.

**The tree has no default.** A default is how the old call came to name the wrong one. The workflow names it at the call site, and a contract test reads the path back off `pages.yml`'s own upload step - so the thing measured and the thing published are pinned to be one directory, and pointing the gate anywhere else fails the suite rather than being noticed a month later.

**Two lines, and only one of them fails a build.** Over `retention.site_budget_mb` (800 MB) the step prints an Actions warning and passes; past the 1 GiB cap it fails. Failing at 800 MB would stop publishing about two weeks before it had to, and a reader would lose a working site to a budget that still had room. Past the cap the bytes cannot be published at all, and failing in the job that measured them names the cause - a deploy that refuses them names nothing.

**`site_bytes` on the run manifest stays what it always was.** It is the committed payload tree, six days of published manifests carry it, and changing what it means would be a contract break for a number that is genuinely useful about repository growth. What changed is that it now says which tree it holds, so nobody reads it as the site again ([../contracts/schemas.md](../contracts/schemas.md)).

**The deploy is not gated.** `pages.yml` prints `du -sb build` and always did. Adding the check there would need a Python install on the deploy path for no new coverage: every byte that reaches `main` passes through the `assemble` job or through `ci.yml`, and both now measure it before the push rather than after.

### The build stops a bad day; the weight ratchet does not (2026-08-29)

`digest.yml`'s `assemble` job ran `npm run build` and `npm run bundle-gate` in one step, before the commit that publishes. Two failures with nothing in common were welded together, and only one of them is worth a day.

**A build failure is the payload.** Every route is prerendered, so a payload that fails its contract fails the build instead of a reader's browser. That day is broken, it must not publish, and the build still runs before the commit. Nothing about that changed.

**A weight failure is a number we wrote down ourselves.** `page_weight.ceilings_bytes` in `config/idhazh.json` says how heavy each named page's prerendered HTML may get. Past it the page still reads correctly - what grew is the document, not the meaning. The run that hit it lost the whole day and the two to three hours of runner time that produced it, and the reader lost a digest that was fine. So the gate moved after the commit, in `digest.yml` and in `backfill.yml` alike.

**Leaving it before the commit was the alternative, and it was rejected on the trade rather than on the principle.** It does buy something real: `main` stays green, and the ceiling is discussed before any reader sees the heavy page. It buys that by spending a published day and a runner budget (Rule #2) on a page nobody would have complained about. A digest that never arrives is the larger failure.

**It stays fatal, and that costs something.** The day publishes, then the `assemble` job goes red, and `main` goes red with it at the next CI run. Stated plainly: a ceiling crossed on a Tuesday leaves `main` red until somebody looks at it. That is the price of the trade and it is not hidden. The fix is one line in `config/idhazh.json`, raised in the commit that earned the bytes and saying what they buy ([../../how-to/run-the-gates.md](../../how-to/run-the-gates.md)). For `/console/` it is not to raise the number at all ([frontend.md](frontend.md#the-console-ceiling-is-a-tripwire-and-what-to-do-when-it-fires)). A warning was rejected for the same reason a green light on a broken alarm was: nobody reads it.

**"At the next CI run" is not "at the next push", and the difference is a delay.** `ci.yml` triggers on every push to `main`, but the pipeline's own pushes never start it: GitHub does not begin a workflow from a push made with the job's `GITHUB_TOKEN`. Measured 2026-08-29 - six `work:` and `digest:` commits on `main` carry **zero** check runs between them, while the two pull-request merges either side of them carry two each. So the red job the pipeline itself produces is the `assemble` job inside the digest run, and `main`'s own CI stays green until the next merge somebody pushes. Anyone diagnosing a red `site` job should read it as a page that has been over its ceiling since some earlier publish, not as something the merge in front of them did.

**The old position was never the guarantee its comment claimed.** `Commit the day` retries a lost push by rebuilding the day against origin's new tip, and nothing rebuilds the site afterwards. So the gate reads the build made before the commit wherever the step sits, and a pass recorded before the push could describe a tree the retry had already replaced. Moving the step does not fix that. What it fixes is a stale measurement being the thing that costs a reader the day.

**`site-weight` did not move.** The 1 GB Pages cap is the platform's limit, not our record of our own bytes, and past it the deploy fails whatever we do - so refusing to publish is the honest answer there and it still runs before the commit.

### The size instrument printed a level, and a level has no date in it (2026-08-30)

`site-weight` printed a megabyte figure and a headroom figure. Both are levels. **Neither is a rate, so neither could answer the only question anyone asks a size instrument: when does this stop working?** The date existed - it was worked out by hand in [../../reference/measurements.md](../../reference/measurements.md#days-to-the-1-gb-pages-ceiling) three separate times, and got the wrong answer twice - while the step that had all the inputs printed two numbers that could not produce it.

Three things were added and none of them fails a build.

**`by_directory` - the top-level children of `build/`.** One total cannot say whether the visuals grew or the telemetry did, so the day the total moves is the day somebody starts guessing. The split is asserted to sum exactly to the total, because a split that quietly loses bytes names the wrong directory on the one occasion it is used to decide what to cut.

**`bytes_per_published_item` - the unit that holds still.** A rate per day is not stable here: measured 2026-08-29, the day rate moved by a factor of six across seven mature days, because two of them published 117 and 212 items where the ones behind them published 731. The per-item figure over the same days was 24,378 bytes, spread 23,066 to 26,538. So the day rate is derived - per-item times `run.safety_ceiling_per_run`, the ceiling in force - rather than averaged over whichever days happen to be on disk. That is a worst-case day by construction, which is what a runway needs (Rule #10).

**`days_to_alarm` and `days_to_cap` - the runway.** Headroom divided by that rate, in published days rather than calendar days. It is printed on every run, including the runs that are nowhere near either line, because the day the alarm fires is not the day anybody wanted to first learn the date.

**The count comes from the tree that was measured, and that is not a detail.** Items are read from the day payloads staged under `build/digest/`, never from `frontend/public/digest/` and never from a run manifest. Bytes and items have to come from one corpus or the rate divides a numerator by somebody else's denominator - which is exactly the shape of the defect in the section above, one level down.

**It reports and it gates nothing new.** `npm run bundle-gate` already fails a build on a crossed per-route ceiling, and `cap_breach` already fails one past the platform's. A third gate would be a third thing to keep green for coverage that already exists. A gate on one directory's share was rejected outright: the cap is on the whole tree, and one directory's share of it is not a date.

**A runway from nothing raises rather than returning a comfortable number.** Zero published items divides into an infinite runway, and an infinite runway reads exactly like a healthy site - the same failure as the green light on the wrong tree, one function along. So the per-item property raises on an empty tree, the CLI checks before it asks, and a tree carrying no day payloads prints `runway: unknown` instead. The zero-file tree still fails outright, as it already did.

**What it printed the first time, 2026-08-30 at `76cdc72`:** 141.1 MB in 311 files, 883 MB of headroom, 48,457 B a published item, 7.39 MB a published day, and **119 published days to the cap**. The rate is an average over the whole tree, so it charges the on-device encoder and the JavaScript bundle - 46.5 percent of the site, and neither of them grows with a day - to every future item. **That makes the printed runway a floor: at least 119 days, and about 223 once the fixed directories are taken out.** It prints the conservative one on purpose, and `by_directory` is on the same output so a reader can do that subtraction rather than take the floor as the answer. Full working in [../../reference/measurements.md](../../reference/measurements.md#days-to-the-1-gb-pages-ceiling).

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A `latest` route alongside `/` | Two moving pointers. A reader bookmarks one and shares the other, and they disagree about which is canonical. |
| A redirect at `/` | A blank first paint and a wasted round trip on the site's most-visited address. |
| A committed pointer file naming the newest day | Derived data committed as fact, and the first thing to go stale after a prune. Deriving it at build time is what makes retention a one-step operation. |
| One file per item | Multiplies requests, defeats compression, and duplicates bytes the day payload already carries. |
| One file per vertical per day | Several sources for one fact, to avoid a trivial client-side filter. |
| A global index of every item ever published | Unbounded growth on the hot path of every page load. Measured 2026-08-26: 45.5 gzipped bytes an entry, so a year at the structural ceiling is 12.7 MB of browse entries before a single vector joins them. |
| One search index file per day | The per-item-file objection at a different granularity: a search that spans a month is 30 requests, and no shard warms the gzip dictionary. |
| base64 vectors inside the index JSON | 322.55 gzipped bytes an item against 249.82 - 22.5 percent more - and it charges every browsing visitor the vectors as well. |
| HTTP range requests into the vector file | One request per result, against a static host that has to answer each one. The whole file already transfers compressed. |
| A summary, source or band on an index entry | Measured 2026-08-26: 6.35 times the entry, and a month at the observed rate goes from 518 KB to 3.21 MB. A result renders from the day payload it names instead. |
| A gate that fails on one directory's share of the site | The cap is on the whole tree. One directory's share does not yield a date, and a second weight gate is a second thing to keep green beside `bundle-gate`, which already fails on a crossed page ceiling. |
| A day rate averaged over the days on disk | It moved by a factor of six across seven mature days measured 2026-08-29, because the item counts did. Bytes per published item over the same days held inside 23,066 to 26,538. |
| Moving the vectors out of the day payload into a sibling committed file | A persisted-contract change that buys no bytes. `extra="forbid"` means a `DigestDay` without `embeddings` rejects all 2,237 committed items, so the price is a read-side migration forever or a rewrite of every day - and the block already reaches no browser. See [The vectors are projected out, not moved out](#the-vectors-are-projected-out-not-moved-out-2026-08-27). |
| Staging the day payload whole and narrowing only the prerendered pages | Measured 2026-08-27: the staged tree is 6,976,807 bytes of the 146,696,452-byte site, and leaving it whole gives back 3,356,432 of the 18,631,599 this change saved. Same two files open, one of the two edits skipped. |
| A positional vector index instead of a byte offset | Every reader then has to count how many entries above it were skipped, and an off-by-one decodes cleanly and ranks nonsense. |
| Omitting an item that has no vector | It disappears from the browse list as well as from search, which is the larger loss. Two of 2,237 committed items are in this state today. |
| A padded zero vector for an item that has none | It scores against every query. A null says "not searchable"; a zero says "equally close to everything". |
| An incremental read-modify-write of a shard | Two runs of one day race on it, and the repair for that race is a rebuild - so the rebuild is the only path and the race never exists. |
| Inlining the month index at prerender time | It is the same defect one order of magnitude smaller: the archive document would still grow about 50 gzipped bytes an item, forever. It also cannot be smoke-tested - "delete the file and reload" needs a runtime fetch to have anything to fail at. |
| Staging the whole index directory, `.bin` included, before anything read it | Megabytes in the bundle for a file no page opened. It was staged on 2026-08-27, in the commit that made search read it. |
| A second environment switch for the index root | An index is a projection of a specific set of days. Two switches means one of them can be set alone, and a canary build then serves the real archive's stories. |
| A `latest` symlink or a committed month list | Both are the committed-pointer objection again: the build lists the directory instead. |
| A per-vector half-precision scale | Two bytes an item to describe a quantisation that is identical for every vector in the file. One header field says it once. |
| Binary quantisation now | 48 bytes a vector against 384 is real, and what it costs recall is unmeasured. The revisit trigger is written down instead. |
| DuckDB-WASM, `sql.js` or `wa-sqlite` in the browser | Megabytes of engine to answer a dot product over a file that is already fetched, on a site whose whole point is that the bundle is the runtime. |
| Re-ranking a day on a later run | Contradicts the memory of a reader who already read it. |
| Merging a day's vectors across a model, width or dtype change | One map holding two widths, which is what the self-describing block exists to prevent. The reader-side decoder cannot tell the entries apart, so it would score half the day as plausible nonsense instead of failing. |
| A run identifier in the path | One item at two addresses, so the same item is reachable two ways and neither is canonical. |
| A hash in a filename or URL | Unreadable, unspeakable, and unguessable-by-accident rather than unguessable-by-design. On a public repo with a public index it hides nothing, and it costs the reader a path they cannot reason about. A ten-digit item id is not this: it is decimal, it is short, and it is already the anchor a reader lands on. |
| A per-vertical ordinal in a rendered asset's filename | `ai-03.svg` reads better than `ai-4821903756.svg` and cannot be made correct. The ordinal comes from a counter, every seeding rule reads something a process can observe, and two runs of one day observe different things - which lost a finished day on 2026-08-25 ([visuals.md](visuals.md)). Speakability is worth less than a name two stories can never share. |
| Rewriting the committed days into the new asset name | Nothing is broken to fix. A path is stored on the payload, so every old day still resolves, and a rewrite would move addresses a reader may already hold in exchange for tidiness. |
| A title-derived slug in a URL | Titles originate in fetched text, and fetched text never becomes a URL (Rule #11). |
| Deleting text alongside images under one retention knob | Text is a fraction of a percent of the bytes. |
| Measuring the site cap over `frontend/public/digest` | It is not the site. Measured 2026-08-27: 7,027,075 bytes against the built bundle's 128,064,853, eighteen times apart and growing at different rates, so neither can stand in for the other. |
| Deriving the site size from the payload tree with a calibrated multiplier | The ratio moved from 21x to 18x on one pull request. A multiplier nobody can re-measure per run is an unmeasured number justifying a design (Rule #10). |
| Failing the build at the 800 MB alarm point | It stops publishing about two weeks before it has to. A reader loses a working site to a budget that still had room; the cap is where refusing the bytes is the honest answer. |
| Measuring the site in the Pages deploy instead | The day is already committed by then, and undoing it is a revert. Gating before the push is what turns a broken site into a run that publishes nothing. |
| Leaving the page-weight gate before the commit | It keeps `main` green by spending a finished day and the two to three hours that built it, on a page that reads correctly and that no reader would have complained about. See [The build stops a bad day; the weight ratchet does not](#the-build-stops-a-bad-day-the-weight-ratchet-does-not-2026-08-29). |
| Making the page-weight gate a warning instead of moving it | A warning that fires on every heavy publish is a line in a log nobody opens, and the ceiling then drifts with no date on it. Red after the day is published is read; amber before it is not. |
| A default value for `--site-tree` | A default is how the measurement came to name the wrong tree. The workflow names it, and a test reads it back off the deploy's own upload step. |
| Reusing the render-failure state to mark a prune | One field carrying two different facts, which is the band-aid Rule #5 forbids. |
| Deduplicating the state ledgers the way the eval ledger does | A state row is a fact about a run, not a measurement. A feed that answered twice answered twice, and collapsing the two rows turns a count of runs into a count of days - which is the number `discover.resting` reads to decide a quarantine. |
| A duplicate-run guard in `build_manifest` to match the one in `build_day` | Unreachable. `RunManifest` refuses a `runs` list that is not numbered from 1 without gaps, so the next number cannot already be taken. The branch would never run and no test could reach it. |

## See also

- [../../concepts/digest.md](../../concepts/digest.md) - what a reader gets and the visual rule this layout serves.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the Assemble stage that writes all of this.
- [../sources/discovery.md](../sources/discovery.md) - where the day's items come from, and the same retire-never-delete discipline applied to sources.
- [../sources/freshness.md](../sources/freshness.md) - the run cadence, where an item's id comes from, and why a day has no cap.
- [../../reference/github-actions.md](../../reference/github-actions.md) - workflow names and exact triggers.
- [frontend.md](frontend.md) - the two dashboards these routes serve.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload contracts and the versioning rules a deletion has to honour.
- [../../reference/measurements.md](../../reference/measurements.md#sizing-the-archive-index) - what a browse entry, a vector and a month shard actually cost.
- [../../reference/measurements.md](../../reference/measurements.md#days-to-the-1-gb-pages-ceiling) - the cap date, the per-published-day growth rate, and the units error that made both wrong until 2026-08-27.
- [../../reference/measurements.md](../../reference/measurements.md#the-site-page-by-page-after-the-payload-narrowing-2026-08-27) - what each page and the whole site weigh today.
- [../../reference/measurements.md](../../reference/measurements.md#the-month-search-index-as-written) - the shard that exists: its bytes, its rebuild cost, and the bijection it holds.
- [../../concepts/config.md](../../concepts/config.md) - where the retention knobs live and the build-time versus shipped-config rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11) and git hygiene (section 8).
