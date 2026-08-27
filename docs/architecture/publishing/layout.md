# Published Layout

**Last Updated**: 2026-08-27

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
frontend/public/digest/<YYYY>/<MM>/<DD>/<vertical>-<NN>.svg    optional visual
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

**No hash appears in any path, filename or URL.** A rendered visual is filed by its vertical and its ordinal within the day - `ai-03.svg` - which is predictable, derivable without a lookup, free of fetched text, and speakable. The anchor a reader lands on is the item's own id, `<vertical>-<ten digits>`, which is derived from the address so that a later run of the same day reaches the same item ([../sources/freshness.md](../sources/freshness.md)). Identity for dedupe is a field on the payload, not a segment of a path: paths are for humans and for globs, identity is for the contract.

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

`frontend/public/` is where `backend/` writes and the site reads **through the filesystem at build time**. Only `frontend/static/` is copied into the served bundle, which is why [../../../frontend/scripts/copy-visuals.mjs](../../../frontend/scripts/copy-visuals.mjs) stages rendered images and the telemetry projection across. Three more kinds of file ride that same step from 2026-08-27: `<YYYY-MM>.json`, its sibling `<YYYY-MM>.bin`, and every day's `digest.json`.

**The `.bin` is staged because something finally opens it.** It was left out while the index shipped unconsumed - megabytes in the bundle for a file no page fetched - and search reading the index is the commit that earns it.

**The day payloads are staged because a search result renders from the day it names.** The index carries no summary on purpose, so the result has to come from somewhere, and the alternative is a 6.35-times-larger index that every browsing visitor pays for. `run.json` is not staged; nothing fetches it.

That is a second copy of the day text in the published bundle, and it is worth stating plainly rather than discovering later. **Only a reader who searches ever downloads one**, and only for a day a result of theirs sits on - the reading path is still one prerendered document and zero requests. What it costs the 1 GB site cap (Rule #2) is the same order as the day pages themselves, so it moves retention forward rather than introducing a new kind of growth.

**The staging source is derived from the digest root, in the script and in the page loader alike**, because an index is a projection of exactly those days. One switch rather than two is what stops a canary build serving the real archive's stories.

**The archive fetches the index rather than inlining it, and that is the whole point.** Every other committed payload this site renders is read at build time and baked into the HTML, which is right for a day page: the day is bounded and the reader came to read it. The archive is the corpus. Inlining it would grow one document by about 50 gzipped bytes an item forever, which is the defect this index exists to end. The console already settled this shape - a bounded seed in the HTML, older months fetched from `static/` on demand - and the archive uses the same mechanism rather than inventing a second one. What the archive page still carries from its own data is a compact day row, three counts and about twenty topic names: all of it grows per day or per month, none of it per story.

**A missing index is a designed state.** The page falls back to the day row and one plain sentence. It never white-screens ([../../../CLAUDE.md](../../../CLAUDE.md) section 12).

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

**The named trigger that would revive revision is a summarizer model swap** ([../../../TODO/20260825-qwen35-9b-adoption-plan.md](../../../TODO/20260825-qwen35-9b-adoption-plan.md)). A better summarizer is the one event that makes words already published worth rewriting; a bug fix in the pipeline is not, and neither is a new field. That swap is also the point at which the run-manifest join the fields exist for starts to matter, because a day would then hold summaries from two different models.

**The promise is pinned by a test, not by this paragraph.** `backend/tests/test_pipeline.py` asserts that a second run over an item the day already holds leaves its words, its `updated_at` and its `updated_by_run` untouched. A sentence on a page drifted once; the test fails the day the gates stop holding, which forces this page to be corrected in the same commit.

Retention was demoted to third lever after the byte arithmetic showed that encoding and the existing visual rule together move the ceiling from months to years. A policy that deletes a reader's archive to reclaim a fraction of a percent of the bytes would have been solving the wrong problem.

### Two append paths, and only one of them deduplicates (2026-08-27)

`idhazh.ledger._append` writes every row it is handed. `idhazh.evals.writer.append` refuses a row whose address, inputs, words and scorer version it already holds. That looked like one of them being wrong, and it is not: **the two write different kinds of row.** An eval row is a measurement, so re-measuring an item nothing changed about has nothing new to say. A state row is a fact about a run - this feed answered at this hour, this item finished - and a run that runs twice did happen twice. Collapsing those would turn a count of runs into a count of days.

So the blind path stays blind, and each caller that owns a repeat is now named next to it. Two of the four ledgers absorb a repeat at read time: `load_seen` and `load_published` keep the earliest of two rows, so a duplicate costs bytes and never moves a date. The health pair does not, and that is stated rather than guarded: `discover.resting` counts failures to decide a quarantine, so a duplicated failure counts twice. Measured on this checkout 2026-08-27, `state/published.csv` holds 2,097 rows and 2,097 distinct addresses.

**Where the code was already safe, the fix was a sentence and not a guard.** A guard that can never fire is untested branch weight, and it hides which file the guarantee actually lives in. `cli._published_rows` reads as "everything the day holds" and behaves as "what this run added", and it does that because the plan a later run built has already dropped every published address. Its comment used to claim the filter itself; it now names the upstream facts it depends on, so the next person to widen the plan sees what they would break.

**One path was not safe, and that one was fixed.** The day's run reference counted what the current attempt added rather than what the number introduced, so a replay after a lost manifest write built a payload its own contract rejects - `run 1 items_added disagrees with the items it introduced` - and the day was lost rather than doubled. The count now comes from the assembled day, which is the definition the contract validates against.

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
| A hash in a filename or URL | Unreadable, unspeakable, and unguessable-by-accident rather than unguessable-by-design. On a public repo with a public index it hides nothing, and it costs the reader a path they cannot reason about. |
| A title-derived slug in a URL | Titles originate in fetched text, and fetched text never becomes a URL (Rule #11). |
| Deleting text alongside images under one retention knob | Text is a fraction of a percent of the bytes. |
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
- [../../reference/measurements.md](../../reference/measurements.md#the-month-search-index-as-written) - the shard that exists: its bytes, its rebuild cost, and the bijection it holds.
- [../../concepts/config.md](../../concepts/config.md) - where the retention knobs live and the build-time versus shipped-config rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11) and git hygiene (section 8).
