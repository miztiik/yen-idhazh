# What a month shard holds, and how it reaches a browser

**Last Updated**: 2026-09-23

One month of published items in one file, its vectors in a sibling file, the
ceilings that say when a month stops being the right period, and the staging
step that puts both in front of a browser. The control that fetches them is
[how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md); where the day
payloads themselves sit is [layout.md](layout.md).

## The month search index

`frontend/public/assist/index/<YYYY-MM>.json` is one month of published items in published order, and `<YYYY-MM>.bin` is that month's vectors laid end to end as raw int8. The contract is `backend/idhazh/contracts/search_index.py`; the writer is `assemble.rebuild_search_index`. The archive's story list reads the JSON, and on-device search reads both.

The shard that exists costs **109.3 KB gzipped for 2,237 items, and 545 KB for their 2,235 vectors** ([../../reference/site-weight.md](../../reference/site-weight.md#the-month-search-index-as-written)). An entry is **50.03 gzipped bytes**, which is 10 percent more than the 45.5 the shape study priced, because a real entry carries real key names and a vector offset the study's did not.

**A month shard does not break the bounded-request rule, and here is why.** That rule rejects a scheme whose request count or index size grows with *total history* ([layout.md](layout.md#one-file-per-day)). A month shard's size is a function of one month, and the month ends; the hundredth month costs a reader exactly what the first one did. Request count is bounded the same way: a page reads the months it shows, which is one for a day page and a fixed pan for an archive view, not one per published day and never one per item. What the rule forbids is the file that has to get bigger every day forever, which is the global index in the rejected-alternatives table below - measured at 12.7 MB of browse entries for a single year at the structural ceiling.

**An entry carries the item id, the date, the title and the vertical. Nothing else.** In particular no summary, no source and no band. Measured over the same 2,237 items: adding the summary takes an entry from 50.03 gzipped bytes to **317.52, which is 6.35 times**, and a 30-day month at the rate those six days ran from 518 KB to **3.21 MB**. That charges every browsing visitor the full text of every item in the month. A search result renders by fetching the day payload it names instead: ten results spanning ten days cost at most ten fetches, a day already open is reused, and the result renders through the same item component the digest page uses. That is what the day payloads are staged into `static/` for - see [How it reaches a browser](#how-it-reaches-a-browser).

**`vector` is an explicit byte offset into the `.bin`, or null.** Never a position in the entry list, never a padded zero vector, and the item is never left out. Two of the 2,237 committed items carry no vector today (0.09 percent), and the token-budget work will add more on purpose. Leaving them out would take them out of the browse list as well as out of search, which is the larger loss; a zero vector would be worse still, because it scores against every query. The offsets are dense and in entry order, which is what makes a rebuild byte-identical rather than merely correct.

**The vectors are a sibling file rather than base64 inside the JSON, and the margin is 22.5 percent.** 249.82 gzipped bytes an item against 322.55, measured over 2,119 committed vectors ([../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md#sizing-the-archive-index)) - not the 40 percent this was planned against. The real argument for the split is who pays: every visitor browsing a month pays the JSON, only a reader who searches pays the vectors, and a searcher has already accepted the encoder download. That makes the browse index the only ceiling that matters. **No `DecompressionStream` fallback is needed**: GitHub Pages compresses `application/octet-stream` at gzip level 5, measured directly against the live origin, so a raw `.bin` already transfers compressed. It never serves brotli.

**The JSON is compact - no indent, no separator spaces.** Every other committed payload is pretty-printed because reviewing its diff by eye is worth the bytes. This one is thousands of entries a reader downloads whole, and the indent would roughly double it.

**The header states its own quantisation `scale` from the first commit.** It is `1/127` today, which is the step the committed vectors were made with, and the index cannot tighten it: it projects bytes that are already int8, and re-scaling an integer adds rounding rather than recovering precision. A tighter corpus-wide scale is worth about four times less score noise at zero extra bytes an item, and it has to be applied where the floats still exist - in the encoder, in the commit that re-dates every vector. The field is here now so that change is additive instead of breaking.

## When to reconsider the month

A ceiling with no revisit point is how the last one was set wrong. Two numbers fire, and the third is the second one counted a way you can see coming:

| Quantity | Observed rate | Structural ceiling | Revisit at | What changes |
| --- | ---: | ---: | ---: | --- |
| Browse index, one month, `gzip -5` | 518 KB | 1.15 MB | **1.5 MB** | Shorten the period to `<YYYY-Www>`, exactly as an over-large ledger shard does ([../sources/item-health.md](../sources/item-health.md)). The readers glob the directory, so the period is a layout change and not a contract change. |
| Vector file, one month, `gzip -5` | 2.53 MB | 5.72 MB | **8 MB** | Revisit the dtype before the period. One bit a component is 48 bytes a vector against 384; what that costs recall is unmeasured, and measuring it is the work. |
| Items in one month | 10,605 | 24,000 | **34,000** | The same line as the row above, in the unit a plan is written in: 8 MB divided by 249.79 gzipped bytes a vector. |

**Why 1.5 MB and not the size it is today.** 1.5 MB is 30 percent above what the structural ceiling projects, and the structural ceiling is five cron slots times a safety ceiling of 160 items. So the trigger fires exactly when somebody widens one of those two - a sixth slot alone puts a month at 1.38 MB - and not on an ordinary busy month. On the 10 Mbit reference line it is 1.2 seconds, against 0.9 seconds at the ceiling today.

**Why 8 MB for the vectors.** Only a reader who searches downloads them, and that reader has already accepted the encoder: 22.97 MB on disk, 16.22 MB on the wire. 8 MB is half of what they already said yes to, and 40 percent above the ceiling projection.

**No month shard gets under 300 KB, so that figure is not a candidate ceiling.** The leanest entry that still browses - date lifted to a key, vertical dropped because it is already the item id's prefix - is 41.51 bytes, and a month is over 300 KB at every rate measured. 300 KB buys about 6,000 real entries, which is 17 days at the observed rate and 7 at the ceiling.

**Sharding by month does not by itself bound the browse index**, which is why the granularity and the budget were chosen together rather than one after the other. At 45.5 bytes an entry, 300 KB buys about 6,700 entries - a fortnight at the observed rate and eight days at the structural ceiling.

**The gzip window settles long before a shard does.** Over the same corpus, per-item gzipped bytes barely move between a quarter of the blob and all of it: 249.6 to 249.8 for the vectors, and 47.3 down to 45.5 for the browse entries. So the compression argument for one file per day is about a per-item body of hundreds of bytes, not about a shard of hundreds of kilobytes - any shard past about 70 KB already gets the full ratio.

## The shard is derived, so retention needs nothing

A month shard is rebuilt whole from the day payloads that are on disk at the time. There is no incremental path, so there is no read-modify-write for two runs of a day to race on and no repair command for when they do. **Deleting a day and re-running assemble regenerates a correct shard**, because the rebuild simply does not find the day it used to name. That is the entire retention obligation, and it is discharged by construction rather than by a rule somebody has to remember.

The rebuild costs one pass over the month's committed payloads: **88 to 122 milliseconds for 2,237 items**, and about one second projected at the structural ceiling of 24,000, against the assemble job's 20-minute timeout. That is one tenth of one percent of the budget (Guardrail #2).

The obligation that does need stating: **every writer of a committed day payload owes its month a rebuild.** There are three - the assemble stage, the one-shot `backfill-vectors` command, and `backend/utilities/build_canary_day.py`, which writes twenty fixture days for the browser suite to browse. A fourth would have to.

## An output path is derived at the call site, never held as a constant

The index root comes off the digest root where it is used, the shape
`public_telemetry` already had, so a caller that moves the days moves the index
with them. **A constant that names an output path is safe only until a caller
redirects a sibling path**, and the failure is silent by construction: the code
runs, the file is written, and the only symptom is in a file nobody re-reads.
Two tests hold it - one that the derived root follows a redirected `PUBLIC_ROOT`
out of the repository, and one that the shard on disk names exactly the days on
disk. The second is the reader-facing half: the archive lists what that file
holds, so a shard that disagrees with the tree is a page listing the wrong
stories.

## How it reaches a browser

`frontend/public/` is where `backend/` writes and the site reads **through the filesystem at build time**. Only `frontend/static/` is copied into the served bundle, which is why [../../../frontend/scripts/copy-visuals.mjs](../../../frontend/scripts/copy-visuals.mjs) stages rendered images and the telemetry projection across. Three more kinds of file ride that same step from 2026-08-27: `<YYYY-MM>.json` and its sibling `<YYYY-MM>.bin` into `static/index/`, and every day's `digest.json` into `static/digest/`.

**The index is staged beside the encoder, never inside it.** `static/assist/` is the on-device encoder and its wasm - authored files, committed, and secondary by contract: the bundle must render complete with that directory deleted ([../../../CLAUDE.md](../../../CLAUDE.md) section 0a), and CI proves it by parking `static/assist`, building, and asserting the bundle carries no `assist/` at all. Browsing the archive is not a model feature. It is how the page lists anything, so the data it needs cannot live in a directory whose whole contract is that it can be removed. The index therefore gets its own top-level tree, the same shape `static/digest/` and `static/telemetry/` already have: one directory per staged projection, ignored by git, rebuilt every build.

**The `.bin` goes there too, even though only a searching reader fetches it.** It is one shard in two files, so splitting them across two paths would buy nothing, and the reason the directory is wrong has nothing to do with who reads the file: staging runs inside `npm run build`, so anything written under `static/assist/` reappears after the gate has parked it.

**The first placement was inside `static/assist/index/`, and CI caught it the same day.** `build/assist` existed on a build that had otherwise succeeded, and the gate failed. Read as a gate problem it invites an exclusion. It was a path problem: two different things, one directory.

**The `.bin` is staged because something finally opens it.** It was left out while the index shipped unconsumed - megabytes in the bundle for a file no page fetched - and search reading the index is the commit that earns it.

**The day payloads are staged because a search result renders from the day it names.** The index carries no summary on purpose, so the result has to come from somewhere, and the alternative is a 6.35-times-larger index that every browsing visitor pays for. `run.json` is not staged; nothing fetches it.

That is a second copy of the day in the published bundle, and it is worth stating plainly rather than discovering later. **From 2026-09-01 a reading route opens one too.** A topic page carries the head of its own desk and a dated day page carries the head of the day, and both fetch the served day for the rest - so this file now has three readers: a search result, every topic page whose desk is longer than `ui.shell_seed_items`, and every dated day page whose day is. The home page still makes no request at all, and neither does a reading page whose whole list already fits inside the seed.

**It is not a second copy of the day, though, because it is a projection.** The staged file carries thirteen fields an item - the ones a search result actually renders - and nothing else. What that cost and what it bought is in [the-served-day-and-the-documents-that-stopped-being-written.md](the-served-day-and-the-documents-that-stopped-being-written.md).

**The staging source is derived from the digest root, in the script and in the page loader alike**, because an index is a projection of exactly those days. One switch rather than two is what stops a canary build serving the real archive's stories.

**The archive fetches the index rather than inlining it, and that is the whole point.** Every other committed payload this site renders is read at build time and baked into the HTML, which is right for a day page: the day is bounded and the reader came to read it. The archive is the corpus. Inlining it would grow one document by about 50 gzipped bytes an item forever, which is the defect this index exists to end. The console already settled this shape - a bounded seed in the HTML, older months fetched from `static/` on demand - and the archive uses the same mechanism rather than inventing a second one. What the archive page still carries from its own data is a day list, three counts and about twenty topic names: none of it grows per story. The day list is the one part that still grows per day, at 8.0 gzipped bytes, because a link for every published day is what a reader with no script uses to reach one - what a reader SEES there grows by a row a month ([how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md#the-day-list-grows-with-months-on-the-page-and-with-days-in-the-document)).

**A missing index is a designed state.** The page falls back to the day list and one plain sentence. It never white-screens ([../../../CLAUDE.md](../../../CLAUDE.md) section 12).

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
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
| Merging a day's vectors across a model, width or dtype change | One map holding two widths, which is what the self-describing block exists to prevent. The reader-side decoder cannot tell the entries apart, so it would score half the day as plausible nonsense instead of failing. |

## See also

- [layout.md](layout.md) - where the day payloads this shard is derived from sit.
- [the-served-day-and-the-documents-that-stopped-being-written.md](the-served-day-and-the-documents-that-stopped-being-written.md) - the projection the staged day payloads are, and what one day costs.
- [how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md) - the archive list and the search that read both files.
- [the-on-device-encoder-and-its-vectors.md](the-on-device-encoder-and-its-vectors.md) - what made the vectors, and what makes two of them comparable.
- [../../reference/site-weight.md](../../reference/site-weight.md#the-month-search-index-as-written) - the shard that exists: its bytes, its rebuild cost, and the bijection it holds.
- [../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md#sizing-the-archive-index) - what a browse entry, a vector and a month shard actually cost.
- [../sources/item-health.md](../sources/item-health.md) - the ledger whose shard period this one would follow.
