# Published Layout

**Last Updated**: 2026-09-06

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
state/scores/<YYYY-MM>.csv                              the ledger - one row per measurement, never published twice
state/score-archive/<YYYY-MM>.json                      a score month past its full-grain window, as totals plus a dedupe index
```

```
/                          the newest published day, rendered inline    moving
/<YYYY-MM-DD>/             that day, every vertical                     canonical
/<YYYY-MM-DD>/<vertical>/  that day, one vertical - a projection        canonical
/<YYYY-MM-DD>/#<item id>   an item anchor
/archive/                  every surviving day                          moving
/evals/                    a signpost to /console/, where the scores went
/console/                  the run-health dashboard                     moving
```

**One day directory is the deletion atom.** Nothing outside it points into its interior except the append-only ledger, which is what makes pruning a single operation with no second edit.

**No hash appears in any path, filename or URL.** A day carries two reader-facing addresses and both are the item's own id, `<vertical>-<ten digits>`: the anchor `#<item id>` and the rendered visual `ai-4821903756.svg`. The id is derived from the article's address, so a later run of the same day reaches the same item ([../sources/freshness.md](../sources/freshness.md)), and it is not a digest of anything - the ten digits are decimal and short enough to read back. The sha256 `url_key` that identity for dedupe actually rests on stays a field on the payload and never becomes a path segment. Paths are for humans and for globs; a hash is for the contract.

**The asset name was `<vertical>-<NN>` until 2026-08-27, and both shapes are live in committed data.** The ordinal came from a counter, a counter has to be seeded from something a process can observe, and two runs of one day observed different things - which cost a finished day ([visuals.md](visuals.md)). Naming the file after the item makes the path a function of the item, so no two runs and no two shards can pick one path for two stories. **No old address broke and none had to be migrated**: `assemble` copies `VisualDecision.asset_path` into the day payload verbatim, the page renders that stored string, and the build stages by file suffix - so a name is data the day carries, never a rule the reader re-derives. That is the same property that makes the two contracts at the top of this page separable, applied one level down.

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
- **No run identifier appears in any data path or any reader URL.** It lives in the run manifest and in the day notice, on the pages that render a day.

The returning reader is protected by the read mark and by the run-scoped "new" grouping - both of which work identically for everyone - rather than by freezing an order, which cannot be done in a shared artifact without rendering a different page per person.

## One file per day

A day is one JSON payload carrying every item. A vertical route is a filter over that same payload, never a second file.

The consequence worth protecting: **rendering any page costs at most two requests, no matter how old the archive is.** Any scheme whose request count or index size grows with total history is rejected on sight, at any granularity. A per-item file multiplies requests and defeats compression - a small body never warms the gzip dictionary, where a whole day reaches the measured prose ratio. A global index of everything ever published grows without bound on the hot path.
**One page already breaks that rule, and there is now a number on it.** `/archive/` inlines every committed day so on-device search can see the whole corpus, which is the last rejected alternative below in everything but name. Measured 2026-08-26 over the six committed days, 2,121 items, at the gzip level the Pages edge actually serves: a browse entry - item id, date, vertical, title - costs **45.5 bytes**, and one committed int8 vector costs **249.8 bytes** ([../../reference/measurements.md](../../archive/measurements-2026-08.md#sizing-the-archive-index)). A 30-day month is therefore 482 KB of browse entries and 2.6 MB of vectors at the rate those six days ran, and 1.07 MB and 6.0 MB at the ceiling that five runs of 160 items a day allows.

**Sharding by month does not by itself bound the browse index.** At 45.5 bytes an entry, 300 KB buys about 6,700 entries - a fortnight at the observed rate and eight days at the structural ceiling. A month shard is over 300 KB at every rate measured, so a shard granularity and an index budget have to be chosen together rather than one after the other. That is now done: the granularity is a month and the budget is 1.5 MB, both in [The month search index](#the-month-search-index) below.

**The gzip window settles long before a shard does.** Over the same corpus, per-item gzipped bytes barely move between a quarter of the blob and all of it: 249.6 to 249.8 for the vectors, and 47.3 down to 45.5 for the browse entries. So the compression argument above is about a per-item body of hundreds of bytes, not about a shard of hundreds of kilobytes - any shard past about 70 KB already gets the full ratio.

## An item says why it is here, and whose clock its time is

The planning step scores every story before a single model loads ([../sources/discovery.md](../sources/discovery.md#ranking-is-arithmetic-not-judgement)), and until 2026-08-31 the whole of that arithmetic was thrown away at the end of the plan job. The published item now carries five fields. **Nothing new is computed for them**: four are the score's own terms, and the fifth is a choice `rank.appeared_at` was already making and discarding one line later.

| Field | What it says | What it is not |
| --- | --- | --- |
| `carried_by` | How many feeds carried **this one address** today. | Not "also covered by N sources". Two outlets writing their own piece produce two addresses and both read 1. The honest cross-outlet version is a different measurement. |
| `watchlist_hit` | The story names an entity on the watchlist. | Not an importance grade. It is one bonus term of several. |
| `on_front_page` | An aggregator voted for it. | A vote, never a discovery - a salience feed never puts a new address in the pool. |
| `rank_score` | What the planning step scored the story at. Comparable across the whole day, because every desk uses one scale. | Not a quality score and not a confidence band. `band` is the quality signal and it is measured somewhere else entirely ([../../concepts/evaluation.md](../../concepts/evaluation.md)). |
| `time_source` | Which clock `published_at` came from: `feed`, `first_seen`, or `unknown`. | Not a second timestamp. There is one time on the item and this says whose it is. |

**All five are optional, and an absent one reads as unknown.** Every day published before the fields existed omits all five - 11 days and 3,596 items when they landed, counted 2026-08-31 - and not one of them was rewritten (`CLAUDE.md` section 11). A reader of the payload - our own page included - must not fill an absent field with a default, because every plausible default is a false claim: `0` for `carried_by` says no feed carried the story, `false` for `on_front_page` denies a vote that was never counted, and `0.0` for `rank_score` puts the story at the bottom of its desk. `null` is the only honest answer and the contract test over every committed day asserts it.

`time_source` earns its place because the fallback it names is silent. `published_at` is the feed's own date where the feed gave a usable one, and our first sight of the address where it did not ([../sources/freshness.md](../sources/freshness.md)). Both are the same kind of string, so a page printing the time cannot say whose it is without this field. Measured 2026-08-31 on the committed 2026-08-30 payload - the newest day that had finished publishing - 431 items: 305 distinct `HH:mm` values, and 5 stamps, 1.2 percent, within two minutes of a run stamp. **That last figure is an upper bound on the fallback and not a count of it**, because until this field shipped nothing committed recorded the choice, and a feed's own stamp can land near a run by chance. The fallback is rare either way, which is exactly why it needs naming: a reader has no way to spot the 1 percent.

### The rail is what reads it, and what it can and cannot say (2026-09-02)

The day's stream orders by `published_at`, newest first, and prints it on a rail. So `time_source` stopped being a field with no reader and became the thing that decides which of five strings a story gets ([../../concepts/ui-shell.md](../../concepts/ui-shell.md)). Counted 2026-09-02 on Intel Core i7-1265U / Windows 11 / Python 3.14.2 over every committed day - 12 days, 4,713 stories:

| `time_source` | Stories | Share | What the rail prints |
| --- | --- | --- | --- |
| `feed` | 970 | 20.6 percent | the clock, unmarked |
| `first_seen` | 10 | 0.2 percent | `First seen 06:20`, with a mark |
| `unknown` | 0 | 0 | `No time given` |
| absent | 3,733 | 79.2 percent | the clock, unattributed and unmarked |

Three things follow from that table and each one moved the design.

**The absent case is the archive, not an edge case.** Four fifths of everything published predates the field. A story there carries a stamp `rank.appeared_at` chose the same way it chooses one today - only the label was thrown away - so the honest render is the stamp with no claim attached. Printing it as a feed time would be a claim the run never recorded; refusing to print it would delete a fact from 3,733 stories and leave the rail blank on ten of twelve committed days.

**`unknown` has never happened**, so the branch is carried by the canary day, which plants one story of every state on purpose. A branch no fixture reaches ships with no test at all, and this one decides whether a story with no time still renders.

**"The feed gave a date and no clock" is not expressible, and no heuristic was invented for it.** `discover._published_at` reads `feedparser`'s parsed struct, which fills 00:00:00 for a date-only feed date - and a story genuinely published at midnight parses to the same thing. 47 of the 4,713 committed stories are stamped exactly `T00:00:00Z`, 1.0 percent, and the payload cannot say which of the two each one is. Reading midnight as "no clock given" would mislabel a real midnight story, which is the invented-label failure the rail exists to avoid. The string stays in the vocabulary for the day a feed's own granularity is recorded; until then it prints only where the payload says there is no time at all.

## The same story from several sources says so

A day runs the same story from more than one of our feeds, and until 2026-09-01 nothing on the page said so. The published item now carries two more fields, and both are computed at build time from the vector block the payload already holds - the browser never computes this and no encoder is loaded to do it.

| Field | What it says | What it is not |
| --- | --- | --- |
| `also_covered_by` | How many **other sources** carried the same story today. | Not `carried_by`, which counts syndication of one address and reads 1 when two outlets write their own piece. |
| `same_story_as` | The item a reading surface would draw for this story. | Not a deletion, and not something any page acts on today. |

**`also_covered_by` is what a reader sees.** The item's footer, under the summary, reads `Also covered by N other sources today.`, or `Only one of our sources carried this.` where nothing grouped with it. Both are facts about our feed set and never claims about the world - we know who we read, not who else covered a story. Null prints nothing at all, which is what every day published before 2026-09-01 does.

**`same_story_as` is recorded and not yet drawn**, and that is deliberate. Collapsing a group in `DigestList` was built and then taken out again on the evidence of its own smoke: the reading routes reach an item by paging a topic, so an item filtered out of the list is not merely undrawn on the first screen - it becomes unreachable through every reading route while its address still exists. **Half of that has since been answered and half has not.** A story's own address now pages the stream down to it and focuses it (below), so a reader who follows a link to a collapsed story arrives at it. What is still missing is the way in for a reader who has no link: nothing on the page names the stories a group swallowed, so drawing the collapse today would take five stories off the 2026-08-30 page with no route a reader could find them by. The field is on the committed day so the decision is recorded and auditable; it is **not** on the served projection, because a field with no renderer does not earn the wire.

**Nothing is unpublished.** A grouped item keeps its place in the published order, its address, and its entry in the month search index. Measured on the committed 2026-08-30 day, 2026-09-01: **431 items in, 431 items out**, 5 of them marked as the same story as another.

**A group is always across sources**, and that is a rule rather than an observation. The sentence a reader gets is about sources, so a group of one source has nothing to say - the survivor's line is the one it already had, and forming it would still cost a story. It is also where the encoder is least trustworthy: two press releases off one desk share their boilerplate and differ only in a date, so the Federal Reserve's June minutes and its July minutes score **0.9867** against each other on the committed 2026-08-25 day and are two different documents. One outlet publishing twice is bounded by `collect.max_source_share_per_day` instead.

**Every pair inside a group clears the threshold**, not only each item against the one it joined. Single-link grouping chains: A is the same story as B and B as C while A and C are two different stories, and the chain quietly loses one of them.

**The keeper is the strongest by `rank_score`**, and where two items tie the earlier run wins - a returning reader keeps the item they already saw rather than watching the day swap it for a copy. An item published before `rank_score` existed has none, so it ranks below any scored item.

### What chose 0.94

`assemble.duplicate_similarity_min` is set by hand labels, not by taste. Every group the pass forms over the eleven committed days was read from the published titles and summaries and marked same-story or not. Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 / Python 3.14.2, 3,978 items:

| Threshold | Groups | Items grouped | Largest group | False merges |
| ---: | ---: | ---: | ---: | ---: |
| 0.93 | 30 | 37, 0.93 percent | 4 | **1** |
| 0.94 | 22 | 24, 0.60 percent | 3 | **0** |
| 0.95 | 14 | 14, 0.35 percent | 2 | 0 |
| 0.96 | 11 | 11, 0.28 percent | 2 | 0 |

The one false merge at 0.93 is on 2026-08-30: Ontario's pushback against the lake renaming, folded into Google carrying the renaming out, at a cosine of **0.9317**. Those are two stories, and merging them means the pushback never ran.

**The rule is the first round hundredth above the highest-scoring pair a person marked as two stories.** That leaves a margin of 0.0083, which is thin and is stated rather than dressed up. The way to widen it is more labels, not a higher number: 0.95 buys 0.017 of margin and loses ten groups a person read as one story each.

**The two errors are not equal, which is why the number leans high.** A missed group costs a reader the same story twice, on a page they can see. A false merge costs them a story that never ran, and they cannot see what is not there ([../../../.github/agents/editor.agent.md](../../../.github/agents/editor.agent.md)).

**`assemble.duplicate_similarity_min` is not comparable to `assist.similarity_floor`.** That one scores a reader's query against an item and this one scores two items against each other; the two distributions are different shapes, and reading one number against the other is how a threshold gets set from the wrong evidence.

### What it costs the runner

The pass is one pass over the day's vectors and it is quadratic in the day's item count. Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 / Python 3.14.2, over each committed day at 0.94: **10.5 s on the largest day ever published** (2026-08-24, 731 items), 3.6 s on 2026-08-30 (431 items) and 0.5 s on 2026-08-23 (147). The assemble job's timeout is 20 minutes and the month index rebuild beside it takes 88 to 122 milliseconds, so this is now the stage's largest single cost and still under one percent of its budget.

It compares int8 vectors directly rather than decoding them. `embed.dequantise` divides by the quantisation scale and then normalises, so the scale cancels and the angle between two stored vectors is the angle between the unit vectors they decode to - a test asserts that rather than leaving it as a claim.

### The grouping runs before the lead block, and that order is fixed

Two passes read the finished day inside `assemble.build_day`, and both were written in the same week by different rows. The grouping runs first; the leading stories ([../sources/discovery.md](../sources/discovery.md#a-second-order-over-the-same-day-the-leading-stories)) are chosen over what it produced. The reason is that the grouping decides which item of a group a reading surface would draw, so the block is picked over the day as the reader will see it rather than over one that is annotated a line later.

**The order changes nothing today, and that is measured rather than assumed.** The two passes touch different fields: the grouping writes `also_covered_by` and `same_story_as` and nothing else, and lead selection reads neither. Rebuilding both passes in each order over the eleven committed days - 4,086 items, 2026-09-01, Intel Core i7-1265U / Windows 11 / Python 3.14.2 - gives the identical block on every day. Ten of the eleven produce no block at all, because a lead may only run on the feed's own clock and `time_source` landed on 2026-08-31; the one day that does produce a block holds five leads over eight groups, and **none of the five is a collapsed item and no group holds two of them**.

**What is not yet a rule.** Nothing forbids a lead being an item the grouping collapsed, or two members of one group both leading - the source cap does not catch that, because a group is always across sources. Neither costs a reader anything while `same_story_as` is recorded and not drawn. Both become rules to write on the day the collapse is drawn, which is row 24's reachability question above.

## A desk says why it ran what it ran

Each entry of `verticals` on the committed day carries three more fields since
2026-09-02. The planning step already computed all three, wrote them into the
run plan and published none of them, so the reading page could not say why a
desk was thin.

| Field | What it says | What it is not |
| --- | --- | --- |
| `considered` | Distinct addresses our feeds offered that desk, less what the day had already published or already failed on. | **Not an upper bound on `count`.** Each run counts its own pool and the day's stories accumulate across runs, so a five-run day can publish more than any one run considered. |
| `too_old` | How many of those were past `collect.max_age_hours`. | Not a failure. The age gate working is what this counts. |
| `below_feed_floor` | Some run today found fewer feeds it was allowed to ask than the desk's floor, so that run planned nothing for it. | Not a reader-facing fact. It is published for the operator surfaces and no reading page draws a sentence from it. |

**The three arrive together or not at all**, and the contract refuses a desk
holding two of them. A day published before 2026-09-02 carries none, and absent
reads as unknown rather than zero - a `0` for `considered` would say the feeds
offered a desk nothing on a day that published 216 stories from it.

**Each field is the strongest any run of the day recorded, never the sum.**
`assemble.desk_ref` owns that rule. A later run drops what the day has already
published before it counts anything, so it sees a smaller pool of the same
back-catalogue stories - and adding the runs would print a number the feeds
never offered. A desk this run did not plan keeps what an earlier run said about
it, which is how a desk retired from `config/taxonomy.json` mid-day keeps the
explanation under stories it already published.

**`count` is the payload's own number.** It counts every story the desk
published, including one the duplicate pass grouped behind another - that pass
unpublishes nothing, so the count is not what the default view happens to draw.

**The sentence lives under the topic panel and outside it.** `FilterBar.svelte`
draws it, for the active desk only, as a sibling of the panel rather than a
third child. At 1024px and up that panel is one nowrap band so it is cheap
enough to stick; a third child would be squeezed in beside the pills. It belongs
under the panel anyway - a fact about the desk rather than a control, read once
and then scrolled away. The rule that decides whether it draws at all is
`deskShortfall` in `frontend/src/lib/day-shape.ts`, which is pure and is tested
in Node, because the canary day has one desk and a rule about a healthy desk
needs a second one.

The copy, its three clauses and where the threshold lives are in
[../../concepts/digest.md](../../concepts/digest.md#a-thin-desk-says-what-did-not-run).

## The month search index

`frontend/public/assist/index/<YYYY-MM>.json` is one month of published items in published order, and `<YYYY-MM>.bin` is that month's vectors laid end to end as raw int8. The contract is `backend/idhazh/contracts/search_index.py`; the writer is `assemble.rebuild_search_index`. The archive's story list reads the JSON, and on-device search reads both.

The shard that exists costs **109.3 KB gzipped for 2,237 items, and 545 KB for their 2,235 vectors** ([../../reference/measurements.md](../../reference/measurements.md#the-month-search-index-as-written)). An entry is **50.03 gzipped bytes**, which is 10 percent more than the 45.5 the shape study above priced, because a real entry carries real key names and a vector offset the study's did not.

**A month shard does not break the bounded-request rule above, and here is why.** That rule rejects a scheme whose request count or index size grows with *total history*. A month shard's size is a function of one month, and the month ends; the hundredth month costs a reader exactly what the first one did. Request count is bounded the same way: a page reads the months it shows, which is one for a day page and a fixed pan for an archive view, not one per published day and never one per item. What the rule forbids is the file that has to get bigger every day forever, which is the global index in the rejected-alternatives table - measured at 12.7 MB of browse entries for a single year at the structural ceiling.

**An entry carries the item id, the date, the title and the vertical. Nothing else.** In particular no summary, no source and no band. Measured over the same 2,237 items: adding the summary takes an entry from 50.03 gzipped bytes to **317.52, which is 6.35 times**, and a 30-day month at the rate those six days ran from 518 KB to **3.21 MB**. That charges every browsing visitor the full text of every item in the month. A search result renders by fetching the day payload it names instead: ten results spanning ten days cost at most ten fetches, a day already open is reused, and the result renders through the same item component the digest page uses. That is what the day payloads are staged into `static/` for - see [How it reaches a browser](#how-it-reaches-a-browser).

**`vector` is an explicit byte offset into the `.bin`, or null.** Never a position in the entry list, never a padded zero vector, and the item is never left out. Two of the 2,237 committed items carry no vector today (0.09 percent), and the token-budget work will add more on purpose. Leaving them out would take them out of the browse list as well as out of search, which is the larger loss; a zero vector would be worse still, because it scores against every query. The offsets are dense and in entry order, which is what makes a rebuild byte-identical rather than merely correct.

**The vectors are a sibling file rather than base64 inside the JSON, and the margin is 22.5 percent.** 249.82 gzipped bytes an item against 322.55, measured over 2,119 committed vectors ([../../reference/measurements.md](../../archive/measurements-2026-08.md#sizing-the-archive-index)) - not the 40 percent this was planned against. The real argument for the split is who pays: every visitor browsing a month pays the JSON, only a reader who searches pays the vectors, and a searcher has already accepted the encoder download. That makes the browse index the only ceiling that matters. **No `DecompressionStream` fallback is needed**: GitHub Pages compresses `application/octet-stream` at gzip level 5, measured directly against the live origin, so a raw `.bin` already transfers compressed. It never serves brotli.

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

That is a second copy of the day in the published bundle, and it is worth stating plainly rather than discovering later. **From 2026-09-01 a reading route opens one too.** A topic page carries the head of its own desk and a dated day page carries the head of the day, and both fetch the served day for the rest - so this file now has three readers: a search result, every topic page whose desk is longer than `ui.shell_seed_items`, and every dated day page whose day is. The home page still makes no request at all, and neither does a reading page whose whole list already fits inside the seed.

**It is not a second copy of the day, though, because it is a projection.** The staged file carries thirteen fields an item - the ones a search result actually renders - and nothing else. That is settled below, with what it cost and what it bought.

**The staging source is derived from the digest root, in the script and in the page loader alike**, because an index is a projection of exactly those days. One switch rather than two is what stops a canary build serving the real archive's stories.

**The archive fetches the index rather than inlining it, and that is the whole point.** Every other committed payload this site renders is read at build time and baked into the HTML, which is right for a day page: the day is bounded and the reader came to read it. The archive is the corpus. Inlining it would grow one document by about 50 gzipped bytes an item forever, which is the defect this index exists to end. The console already settled this shape - a bounded seed in the HTML, older months fetched from `static/` on demand - and the archive uses the same mechanism rather than inventing a second one. What the archive page still carries from its own data is a day list, three counts and about twenty topic names: none of it grows per story. The day list is the one part that still grows per day, at 8.0 gzipped bytes, because a link for every published day is what a reader with no script uses to reach one - what a reader SEES there grows by a row a month ([frontend.md](frontend.md#the-day-list-grows-with-months-on-the-page-and-with-days-in-the-document)).

**A missing index is a designed state.** The page falls back to the day list and one plain sentence. It never white-screens ([../../../CLAUDE.md](../../../CLAUDE.md) section 12).

### Two projections, and what one day costs

Two copies of every day used to carry the vector block, and no browser has ever opened it. Its one production reader is the backend's index rebuild, which reads `frontend/public/` off the filesystem. So both copies are narrowed on the way out, in the two places the narrowing can happen:

- **`payload.ts` `loadDay` drops `embeddings` after the parse.** Whatever that function returns is inlined into every prerendered document that renders the day, and there are twelve of those per day - six documents and their six `__data.json` twins.
- **`copy-visuals.mjs` stages a projection rather than a copy.** A named allow-list of thirteen item fields, a one-line projector, and a guard that fails the build if a forbidden name ever reaches the list. That is the shape [../../../backend/idhazh/publish_telemetry.py](../../../backend/idhazh/publish_telemetry.py) already uses to keep URL keys and free text out of the console, and it is copied on purpose: a projection that has quietly widened looks exactly like one that has not.

**Both narrowings are written once, in [../../../frontend/src/lib/payload/project.ts](../../../frontend/src/lib/payload/project.ts).** They used to be two rules in two files: the allow-list sat in the build script, where TypeScript could not read it and the page loader could not import it, and the vector drop was a separate two-line statement of the same idea. Since 2026-08-31 the list, the projector, the forbidden-name guard and the vector drop are one module that both callers import. The module imports nothing itself, because the staging step is run by plain `node` before Vite starts and reaches it through node's own type stripping. Nothing about the bytes moved: all ten published days stage byte-identical, and so does the built site.

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

### The served day is a contract, and its address stops being movable (2026-08-31)

The staged file is now [../../../schemas/digest-view.schema.json](../../../schemas/digest-view.schema.json), generated from [../../../backend/idhazh/contracts/digest_view.py](../../../backend/idhazh/contracts/digest_view.py), and every staged day carries its `version`. Until this commit the shape was a thirteen-name array in a build script. That was honest while the only reader was our own archive page rendering a search result: both halves shipped in one build, so a widening could not surprise anybody.

**What changed is the consumer, not the file.** A reading route is about to fetch this day rather than inline it, so a browser we do not control parses it and a reader's cached shell can be older than the payload it reads. Two things follow, and neither is undone by rebuilding. `<base>/digest/<YYYY>/<MM>/<DD>/digest.json` becomes a public address. And the shape needs a stamp a shell can branch on, which is why `version` is here from the first byte rather than added when it is first needed - a version added later cannot help the shells that are already out.

**The read-side rule is one sentence: absent and null both mean unknown, and a reader may never fill either.** Every plausible default is a false claim - `0` for `carried_by` says no feed carried the story, `false` for `on_front_page` denies a vote nobody counted, `0.0` for `rank_score` puts the story at the bottom of its desk. The projector writes an explicit null for a key the committed day does not hold, so an older shell sees a key it knows with a value it can read, and a newer shell reading an older file sees the key missing. Both are the same fact.

**From here on, a breaking change to this shape needs the read-side migration in the shell, not only in the build.** Section 11 already required a migration; what is new is that the two halves are not upgraded together, so the migration has to live where the reader is. Additive is unchanged and stays cheap: declare the field optional, stamp the version, append the changelog entry, and an older shell ignores a key it does not know. **Changing the address is not a schema change at all - it is a broken bookmark**, and there is no version to branch on for that.

**Nine names joined the thirteen in the same commit, and each has a named renderer.** Measured 2026-08-31 on Intel Core i7-1265U / Windows 11 / node 24.12.0, 11 committed days and 3,733 items, `gzip -9` over the compact projection, each name added to the thirteen-field arm on its own:

| Added | What draws it | Cost |
| --- | --- | ---: |
| `carried_by`, `watchlist_hit`, `on_front_page`, `rank_score` | the lead block, which needs a comparable score across the whole day | +0.94, +1.12, +1.11, +1.16 B an item |
| `published_at`, `time_source` | the time rail, and the item's eyebrow today | +8.29, +0.99 B an item |
| `introduced_by_run` | nothing, since the run divider was deleted on 2026-09-01. It stays because taking a field off this list is a contract change | +1.16 B an item |
| `lenses` | the topic chips | +1.11 B an item |
| `key_points` | the in-page filter, which reads them today | +93.54 B an item |

All nine together are +107.42 bytes an item rather than the +109.42 those nine sum to, because gzip shares what they have in common.

**`key_points` is nine tenths of that and it is the one worth defending.** `DigestList` filters on it now, so once a reading route fetches this file an absent `key_points` is a thrown `TypeError` rather than a narrower filter. The twelve prerendered documents it replaces carry the same words twelve times over, so on the wire it is cheaper here than it was there. Three names were refused: `events` and `entities` have no renderer and are out of scope as reader-facing chips (+1.63 and +1.80 B an item), and `source_form` has no reader at all (+1.21).

**What it cost, end to end.** Two builds of this branch, one an arm, back to back on the same machine, over the 11 days and 3,596 items on disk at the time: the staged payloads went 361.98 to 468.51 gzipped bytes an item, 29.4 percent more, and the 178 rendered images were untouched. A day landed while this row was in flight and took the tree to 3,733 items; the same arithmetic over that tree reads 361.10 to 468.58, which is the check that this is a rate and not a level - the two trees agree to 0.2 percent. The projection is still 40.9 percent under the committed day, which compacts to 792.65 gzipped bytes an item. No prerendered page moved: the six routes the bundle gate names read -1 to +6 bytes across the two builds, because a prerendered document reads the committed day and not this file.

**The runway, re-derived rather than restated (Rule #10).** Two arms of `idhazh site-weight` on the machine that publishes - `ubuntu-latest`, 2026-08-31, `main` at `bb7fd4a` against this branch at `82ebd5c`, both over the same 3,733 items in the same 409 files - read **44,009 against 44,700 bytes a published item**, a built site of 156.7 against 159.1 MB, and **129 against 127 published days to the 1024 MB Pages cap** (96 against 94 to the 800 MB alarm). A local pair on Intel Core i7-1265U / Windows 11 the same day read 44,578 to 45,267 and 128 to 126, which agrees to 1.3 percent and is the check that the platform is not the story. Those day figures divide the headroom by `run.safety_ceiling_per_run` - a per-run ceiling of 160 spent as a per-day rate. **Over the committed days a published day holds a median of 334 items and ranges from 4 to 731**, so the same headroom is 60.8 published days against 61.8: **this change costs about one published day of runway, and the cap arrives about 2026-10-31.** Both figures charge `assist/` and `_app/` - 65.6 MB, 41.2 percent of the site, neither of which grows with a day - to the items, so both are floors.

That is what this row spends. What it buys is the migration, and one day priced on a build of this branch says how much: **2026-08-30 is twelve prerendered documents totalling 8,822,134 bytes raw and 2,528,812 gzipped, against one served payload of 717,709 raw and 194,016 gzipped.** Twelve times the bytes, after this row grew the payload by 62 percent. The documents are the six HTML pages and their six `__data.json` twins, and every one of them carries the whole item list.

### The topic routes spend it (2026-09-01)

A topic route is the day filtered to one desk, and until 2026-09-01 the filter ran at build time in five documents a day. Each of those documents carried the **whole** day so a client-side filter could throw most of it away. Now the document carries the head of its own desk - `ui.shell_seed_items` stories - and a browser fetches the served day for the rest.

**The seed is the head of the desk's list, never of the day's.** The published order is desk-blocked rather than globally ranked ([../sources/discovery.md](../sources/discovery.md)), so the head of the whole day is one desk and every other topic route would have opened on a screen holding none of its own stories.

**The seed is also the head UNION anything the document has to be able to anchor.** A prefix cannot hold a leading story: the reading-page plan's lead block picks across the whole day, and its five leads on the 601-story arm sat at positions 249, 285, 337, 344 and 493. A lead link into a document that carries only a prefix lands on nothing until the fetch arrives, and on nothing at all when it fails. `dayShell` therefore takes a set of ids to keep whatever their position, and the union is what it seeds.

Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 / node 24.12.0, over the 11 committed days, 4,086 items and 51 topic routes. Both arms built with `kit.version.name` pinned to one constant, because it defaults to `Date.now()` and rides into every chunk filename ([../../reference/agent-notes.md](../../reference/agent-notes.md)). A route is its two documents, `index.html` and its `__data.json` twin, at `gzip -9`:

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

### The day routes spend the rest of it (2026-09-01)

`/<date>/` was the last reading route inlining its whole day, and it is the one a shared link actually names. One document per published day, growing with the day it published: the twelve committed days carried 4,203 item payloads across twelve documents, and a reader who opens one day paid for the day they opened. It now carries the head of the day plus every story its leading block points at, and the browser fetches the served day for the rest.

**`/` keeps the whole day inline for ever, and that is a decision rather than an omission.** It is one document per build rather than one per published day, so it contributes nothing to the cap problem - the site could publish for a decade and `/` would still be one document. It is also the address a stranger meets first, and leaving it whole leaves one complete, crawlable, script-free digest on the site. `/404`, `/archive/`, `/evals/` and the console are untouched.

**This is the row that spends `keep`.** A dated page draws the leading block, and every entry in it is an anchor into the stream below. The leads are chosen across the whole day rather than off the top of the published order - on the twelve committed days the newest leads with stories at positions 0, 43, 46, 77 and 86 of 117 - so a document carrying a plain prefix would ship four links out of five that land on nothing until the fetch arrives, and on nothing at all when it fails. The seed is therefore the head UNION the day's leads, which costs the seeded item count and buys a deep link that resolves with no request at all.

**Two days of 117 stories priced the leads.** 2026-08-28 has none and saved 79.8 percent; 2026-09-01 has five, four of them past the head, and saved 73.9 percent. Four extra item payloads in the document is what a working leading block costs.

Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 / node 24.12.0, over the 12 committed days and 4,203 items. Two builds of one worktree back to back; the control arm is this branch's own changed files replaced by `main`'s in place, never a fresh extract, which carries its own byte offset from whatever gitignored state differs between two trees. A route is its two documents, `index.html` and its `__data.json` twin, at `gzip -9`:

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

**`/` and the topic routes are the control.** `/` read 67,534 gzipped bytes for its HTML on the arm that changed the dated routes, and `/<date>/<topic>/` read 19,371 - both what the previous row left them at.

### The revisit trigger, with a date on it

**This does not solve the 1 GB cap (Rule #2). It buys about six weeks.**

At the rate above, the published site reaches 1,073,741,824 bytes on **2026-10-22**, which is fifty-six more published days counted from 2026-08-27. Before this change the date was **2026-10-07**, forty-one days. Across the measured spread on the rate, it runs from 2026-10-19 to 2026-10-28.

Almost all of that is the rate rather than the level: the 18.6 MB taken off the site today is worth 0.8 of a published day, and the 5.6 MB taken off every future day is worth 14.2.

**Nothing fires when that date arrives.** No gate measures the whole-site total against the cap - the bundle gate holds single pages, and the marker count holds what a page inlines. So the trigger is a date and not an alarm: **re-measure the site total and the per-day rate by 2026-09-22, one month before the date, and act on the answer.**

**The lever named here has now been pulled, and it moved the date a long way.** The prerendered dated route trees were 50,598,258 bytes and 39.5 percent of the site, and every one was a document a reader who opens some other day never reads. Five of the six a day were topic routes carrying the whole day, and those are now a seed. Measured 2026-09-01 on the same instrument that printed the numbers above, `idhazh site-weight` over 11 days and 4,086 items: **the site went 168.6 MB to 101.9 MB and the runway went 130 published days to 231** (96 to 175 to the 800 MB alarm). Both figures charge `assist/` and `_app/` - 65.6 MB, neither of which grows with a day - to the items, so both are floors, and both are worst-case days at `run.safety_ceiling_per_run`. The date to re-measure by is unchanged: an instrument that says a year is exactly the one nobody checks.

**The sixth document a day followed the same day, and the dated trees are done.** `/<date>/` was the last reading route inlining its whole day. Over the 12 committed days and 4,203 items on the same instrument, **the site went 101.7 MB to 88.1 MB and the runway went 238 published days to 279** (180 to 212 to the alarm). Reading the two rows together, the reading routes cost the site 168.6 MB and now cost 88.1, and the runway went 130 published days to 279 - it more than doubled. **Nothing about that removes the cap**, because the two directories that do not shrink are the ones that dominate: `assist/` at 43.2 MB and `_app/` at 22.4 MB are 74.5 percent of what is left, and neither grows with a day, so both are charged to the items and both make the runway a floor. **The next lever is retention (below), and there is no third document trick left to play.**

## What the composed page got wrong, and what shipped (2026-09-02)

Twenty-one rows rebuilt this page, each green on its own. `frontend/tests/reading-page.spec.ts` reads the whole thing against a real published day, and it found two things nobody had looked at whole. Both were on a reader's screen. Both are fixed, and the two arms that named them are ordinary assertions now rather than arms written to fail.

Measured 2026-09-02 on Intel Core i7-1265U / Windows 11 / node 24.12.0 and Chromium at 1536x900. The count is read on the 2026-09-01 day, 627 stories over five desks with five leads; the pager is priced on the busiest day the site serves, 2026-08-24 at 731 stories, which is the worst case the committed corpus holds.

### The dated document states the day's count, not the list in its hand

`/2026-09-01/` printed **"20 stories."** as the first line under the date on a day that published **627**, and `/2026-09-01/ai/` printed **"15 stories."**. Twenty is the seed of fifteen plus the day's five leads, so the sentence counted the list `DayNotice` was handed rather than the day the page is about. With script on the number ticked from 20 to 627 while the reader was looking at it. With script off - which this page is built to survive - it stayed at 20 for ever, four lines above a topic row reading `All 627` on the same screen. `/` was always right, because it is the one reading route that still reassembles the whole day into its document.

**`DayNotice` now prints a count it is handed and never one it takes off `day.items`.** `DigestList` had already solved exactly this for the topic row, and its own comment names the hazard: a count taken off the list in hand "would print a number that ticks up while the reader watches". That figure - the day's total across `day.verticals`, or one desk's `count` on a topic route - is a bounded fact that does not grow with the seed, and it is now the number both halves of the same screen state.

**A topic page states its own desk.** The same component draws on `/`, on a dated route, on a topic route and on a day that published nothing, so which number a topic route owes the reader was a content decision rather than a repair. A page about one desk owes that desk's number: the reader chose the desk, the stories under the sentence are that desk's, and the whole day is one pill away on the same row.

Measured after the fix on the same day: `/2026-09-01/` states 627 before hydration and 627 after, and `/2026-09-01/ai/` states 55 against that desk's own published 55. The prerendered figure is the one that mattered - it is what a reader with no script gets and never sees change.

### A story's own address lands wherever it sits in the day

`layout.md` publishes `/<YYYY-MM-DD>/#<item id>` as a canonical reader address, and `restoreAnchor` scrolls and focuses it. On the 2026-09-01 day it resolved for **17 of 627** stories. The stream pages at twelve and the leading block adds its five, whose stories sit at positions 59, 111, 117, 166 and 206 of the reading order, so those seventeen resolved from a cold load. Every other story - 610 of 627 - was not an element on the page when the fragment was read, so the browser did nothing, `restoreAnchor` returned false, and the reader landed at the top of the day with no story focused and no message.

**This was never the seed-and-fetch migration.** The pager predates it and the whole day was never in the document either, so this address had never reached past the pager. What the migration changed is who notices: rows 15 and 26 both made a fragment work for the stories they own, which made the other 610 look like they worked too.

**The pager now reaches the story the address named.** `DigestList` reads the fragment on mount and on `hashchange`, finds that story's position in the order it is drawing, and pages far enough to draw it - then restores the anchor once, after the element exists. Everything else is untouched: with no fragment the reach is zero, so the prerendered document draws the same twelve it always drew and so does every reader who followed an ordinary link. A lead is zero too, because the seed already carries it and paging the stream down to its position is work a click never needed.

**Nothing about the published documents moved.** A control build of `main`'s source beside this one, both on the same tree back to back with `BUILD_VERSION` pinned so the two are comparable: the busiest committed day, `/2026-08-24/` at 731 stories, drew **twelve stories in the document on both arms**, and its `__data.json` twin was byte-identical at 29,278. The document itself read 74,187 raw bytes against 74,189 - **two bytes**, and the two decompose exactly. The live region the fix adds is 73 characters; 71 come back because the reading page now carries 25 preload links rather than 26, since `DigestList` imports the day loader its own route was already loading and a chunk merged. Gzipped at level 9 the document read 15,408 against 15,434. The seed-and-fetch saving above is intact, because none of this runs at build time.

**What it costs is one visit, and only the visit that asked for it.** Following a link to the last story of that 731-story day draws the whole day rather than twelve. Three alternated visits each in a fresh browser context: a plain visit settles in **235 ms** (399, 235, 230) drawing 12 stories on a 5,550 px page, and the deep-linked visit scrolls and focuses in **818 ms** (850, 818, 811) drawing 731 on a 310,781 px page. About six tenths of a second more, on the longest day the corpus holds, for the one reader who followed the link - and nothing at all for anybody else.

**A fragment naming a story the day never held now says so.** `PayloadState` was the state to check first and it does not cover this: it is about the day's arrival, and it lives on the two dated routes, so `/` would still have had no way to say anything. The sentence is one line in `DigestList`'s own live region, and it waits until the list in hand is the whole list - a story still on its way is not a story that was never here.

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

The prerendered dated routes are **50,598,258 bytes, 39.5 percent of the published site** - measured 2026-08-27 on an Intel Core i7-1265U, Windows 11, node 24.12.0, over the six committed days and 2,237 items ([../../reference/measurements.md](../../archive/measurements-2026-08.md#what-is-left-and-where-it-is)). They were 65,197,022 bytes and 44.4 percent before PR #171 narrowed the staged payload.

That is **twelve prerendered documents per published day**: six HTML pages - the all-topics page and one per vertical - and their six `__data.json` twins. Every published day adds twelve more, forever, and nothing else on the site grows per day at anything like that rate. So this is the number the 1 GB cap date is a function of: at 16,641,956 bytes a published day the site reaches the cap on about 2026-10-22, and about 39.5 percent of each of those days is this.

The three levers this page already names - encode efficiently, honour the visual rule, then prune - were all argued about images. **None of them touches an HTML document.** Whatever answers this is a fourth thing, and it has not been designed. What is written down here is the measurement, so the next person starts from a number rather than a feeling.

### What bounds the committed state tree

`state/` is the other tree that grows every run, and it is bounded separately, because what it costs is a checkout rather than a deploy. Re-measured on this checkout 2026-08-31, over the nine days the ledgers then held:

| File | Bytes | Share of `state/` | Bounded by |
| --- | --- | --- | --- |
| `state/seen/<YYYY-MM>.csv` | 2,904,221 | 37.2 percent | `collect.seen_window_days` |
| `state/scores/<YYYY-MM>.csv` | 2,700,019 | 34.6 percent | `observability.scores_full_grain_months` - **archived and deleted from 2026-09-03, and the deletion is in dry run** |
| `state/item-health/<YYYY-MM>.csv` | 1,409,945 | 18.0 percent | `observability.item_health_full_grain_months` - folded, and the fold is in dry run |
| `state/published.csv` | 384,448 | 4.9 percent | nothing, and deliberately - published is forever |
| everything else | 416,995 | 5.3 percent | small enough not to ask |

Total 7,815,628 bytes over 8 files. **All three of the ledgers this table exists to watch moved inside a day**, and the shares moved further than the bytes did, so the shares are the ones to re-take rather than to quote. Against 2026-08-30: `state/` as a whole fell 17.6 percent, because `state/seen/` shed its address column and fell 43.8 percent from 5,166,315. `state/scores.csv` grew 14.4 percent from 2,359,230 in the same day - so its share went from 24.9 to 34.6 percent while it was the only file nobody had touched, and it is now 204,202 bytes short of being the largest file in the tree.

**The fold covers `state/item-health/`, its browser copy, and `state/feed-health/`.** A month older than `observability.item_health_full_grain_months` is read whole, folded to one row per `(date, stage)` in `state/telemetry-aggregate/<YYYY-MM>.csv`, the full-grain shard is deleted, and `frontend/public/telemetry/<YYYY-MM>.csv` goes with it - in that order, with the aggregate read back before the shard is unlinked, so a fold that cannot be written leaves both files where they were. Fourteen months, and the fourteenth is not spare: `console.max_window_days` is 366, `ledger.shards_in_window` walks 367 inclusive days, and a window ending on the first of a month starts on the last day of another - so a read can open 14 month files. The knob carried 13 until 2026-09-02, because the check behind it compared `13 * 30` against 366 rather than against the shards that window selects. Measured over all 146,097 end dates of one 400-year Gregorian cycle, 13 deletes a shard the console still opens on 3,636 of them, 2.5 percent ([../../concepts/config.md](../../concepts/config.md#why-14-and-not-13)).

**Feed health is deleted rather than folded, and that is a decision.** `state/feed-health/<YYYY-MM>.csv` is one row per feed per run. The quarantine reads 31 days and the console reaches at most 366, so no summary of a month past `observability.feed_health_keep_months` has a reader - and a shape nothing consumes, persisted for ever, is the cost of inventing one. `state/feed-retirements.csv` sits beside that directory and is never a candidate: it carries no time window, and a run that forgot a retired address would start asking a dead one again.

**The step ships in dry run, and that is what makes it safe to have written at all.** `idhazh prune-state` logs every file a live run would remove and removes none of them. The reason is `.github/workflows/prune.yml`: it squashes and force-pushes `main` on a schedule, so a state file deleted here stops being recoverable from history once that prune passes over it (`CLAUDE.md` section 8) - `git revert` is not a recovery path for a file older than `finetune.prune_keep_days`. Turning the deletion on is a one-line commit somebody takes after a scheduled run has printed the list.

**Measured on this checkout on 2026-09-03, that list is empty and stays empty for a year.** Every committed shard is inside its own window, so a live run today would remove nothing at all. The first file any store loses is `state/seen/2026-08.csv` on **2026-11-30**, through the 90-day sight window; the first files the fourteen-month rules take are on **2027-10-01**, when `2026-08` falls below fourteen months and four files go together - `state/item-health/2026-08.csv`, `frontend/public/telemetry/2026-08.csv`, `state/feed-health/2026-08.csv` and `state/scores/2026-08.csv`. Reading committed files against a fixed calendar is deterministic, so the spread is zero.

**A score month is summarised before it is deleted, and that is the one deletion here with a summary in front of it.** `state/scores/` is the evidence behind every published quality claim, and `evals.writer` refuses a repeat measurement by reading the rows themselves - so deleting a month outright would erase the evidence AND make every measurement in that month scoreable again as if it were new. A month past `observability.scores_full_grain_months` therefore becomes `state/score-archive/<YYYY-MM>.json` first: the shard's SHA-256 and row count, one digest per distinct measurement it held, and one cohort per (date, run, row version, model, pipeline, scorer) carrying counts, ten faithfulness deciles, three bands, the boolean signal counts, the cut counts, the premise-digest counts and `{n, sum, sum_squares, min, max}` for every numeric column. The file is written temp-then-rename, read back through its contract, and reconciled field by field against a second reading of the shard; only then is the shard unlinked.

**Measured 2026-09-03** on an Intel Core i7-1265U, 12 logical CPUs, 31.8 GiB RAM, Windows 11 (build 26200), CPython 3.14.2, over both committed shards, three reads each:

| Shard | Rows | Cohorts | Source bytes | Archive bytes | Archive as a share |
| --- | --- | --- | --- | --- | --- |
| `2026-08` | 4,110 | 35 | 3,215,734 | 430,009 | 13.4 percent |
| `2026-09` | 1,225 | 10 | 1,050,921 | 127,281 | 12.1 percent |
| both | 5,335 | 45 | 4,266,655 | 557,290 | **13.1 percent** |

Three reads of each shard gave byte-identical archives, so the spread is zero - reading a committed file is deterministic. **What the 13.1 percent means: 87 percent of the bytes go, and a row shrinks from 782 to 858 bytes of CSV to 104 bytes of archive.** Two thirds of what is left is the digest index - 68.8 and 69.3 percent of the two archives - which is the price of keeping the dedupe exact and is what Decision 2 of the plan bought deliberately.

**In years.** The ledger grew 4,266,655 bytes over the 12 published days from 2026-08-22 to 2026-09-02, which is 355,555 bytes a published day and 130 MB a year, with nothing bounding it (444.6 rows a day on average, 10 on the thinnest day and 731 on the fullest, so read the rate as the mean of a wide spread rather than as a constant). With this rule the item-level part stops growing at fourteen months - about 151 MB - and only the archive keeps going, at 46,441 bytes a published day and **17.0 MB a year**. The archive needs 8.9 years to reach the size those fourteen months of shards already are; the raw ledger reached it in fourteen months. That is **7.7 years of headroom for every one the store used to spend**, and the fourteen-month part stops growing at all.

**A thin month summarises LARGER than it held, and that is not a defect.** The digest index scales with rows and the block of moments is a fixed cost per cohort, so a twelve-row month pays the second and barely earns the first. Fourteen-month-old months are the full ones, which is why the direction that matters is the one measured above. `backend/tests/test_retention.py` pins it at a run's worth of rows rather than at a figure, because a figure taken here would go stale the next time a column is added.


**Measured on this checkout, 2026-08-30.** Folding the committed `state/item-health/2026-08.csv` - 4,167 rows over six published days, 1,270,452 bytes - gives 24 aggregate rows and 1,531 bytes: **829.8 times smaller**, 63.8 bytes an aggregate row, 255.2 bytes a published day, 93,136 bytes a year against the shard's 77,285,830. Four rows a day and not five, because `plan` wrote no row that month.

Three things make it the one ledger the fold reaches, and each of them is why the other two need a decision of their own rather than a copy of this one:

- Its rows carry a `stage`, which is what the aggregate is keyed on. A `seen` row is an address and a timestamp; a `scores.csv` row is a faithfulness measurement. Neither folds to `(date, stage)`.
- It shards by month, so a fold is a whole file appearing and a whole file going. `state/scores.csv` is one file, and bounding it means either sharding it - a change across four readers, `payload.ts`, `model-work.ts`, `drift.py` and `label_queue.py` - or rewriting it in place.
- It is a measurement whose totals are worth keeping. `state/seen/` is a lookup, read only through `collect.seen_window_days`, so a shard past that window answers nothing and its honest retention is deletion rather than a fold. **That is what it now gets**, in the same step as the fold: `retention.prune_seen` deletes every seen shard *older* than the oldest month `ledger.shards_in_window(today, seen_window_days)` names - the reader's own helper, so the keep-set cannot drift from what the planner opens. `state/feed-health/` is the same argument reaching the same answer for a different reason: its rows are per-feed-per-run evidence rather than a lookup, and no reader asks a month older than the window for anything. The same day the sight ledger also shed `canonical_url`, which no reader had ever opened: 2,800,881 bytes of 5,705,102 over 25,036 rows, **49.1 percent of the file**, leaving about 356 KB a published day and roughly 32 MB across a full 90-day window.

**Older than the oldest month kept, never merely outside the window.** The two rules read the same on the scheduled path and come apart the moment the prune is handed a date in the past - `--date` takes whatever it is given, and a window drawn around last January puts every shard since outside it, the live one included. Deleting below the window's floor instead makes the retained set a superset of the read set for every date rather than for today's. Measured over the 366 anchor dates from 2026-01-01 at the committed 90-day window: what survives reaches back **90 to 120 days, so the margin over what the planner reads is 0 to 30 days** - zero where the window's oldest day is already the first of a month, thirty where it is the last, because a whole shard is kept either way.

**What this does not do, stated plainly: it does not bound the `/console/` document.** That page was linear in items at a measured 50.45 gzipped bytes an item and crossed its 301,580-byte ceiling on published day 16, because the compression scatter inlined every row `state/scores.csv` had ever held. Both halves of that are closed - the plot moved to a windowed seed over the telemetry projection on 2026-08-29, and the scatter itself became a per-day count of three bins on 2026-08-30 - so the page no longer grows a mark an item. The fold was never an answer to it either way: the two problems share a file and share nothing else.

The aggregate is kept forever by default. `observability.item_health_aggregate_keep_months` is null, and the contract refuses a value at or below `item_health_full_grain_months` - so a month is never deleted before it has been folded. `observability.score_archive_keep_months` stands in the same relation to `scores_full_grain_months`, and is null for the same reason.

**What is deliberately lost when a score month is archived**, and what survives, because a policy that only lists what it keeps is not a policy:

| Lost | Survives |
| --- | --- |
| Looking one item up by its address or its id | Every total and rate the cohorts carry |
| Drawing that month into the human label queue | The distribution, as ten faithfulness deciles and three bands |
| Re-banding those rows under new thresholds | Ranges and spread, from `{n, sum, sum_squares, min, max}` per column |
| An exact percentile | Boolean signal counts, cut counts and premise-digest counts |
| Correlating two columns against each other | Exact dedupe, through the sorted observation digests |
| Any slice the cohort key does not name | The shard's own SHA-256 and row count |

Authority: Andre, under Rule #10 - a claim about an archived month has to be one the archive can still support.

### `state/scores/` shards by month, and that bounds nothing on its own (2026-08-31)

**The eval ledger moved from `state/scores.csv` to `state/scores/<YYYY-MM>.csv` on
2026-08-31.** The migration is a split and nothing else: 3,509 rows, one month,
2,700,019 bytes before and after, every cell compared by name across both
revisions. Say what it did not do first, because the section this replaces was
right about it: **sharding is not a bound.** Nothing is deleted, nothing is
folded, and the tree grows at the same rate it grew yesterday.

What it buys is that the two things which could bound it are now possible. A
retention rule can take a whole month the way `state/item-health/` already does,
instead of rewriting a file that `merge=union` will not let anyone rewrite. And a
reader that wants a window can skip whole files - `payload.ts` has a shared
`readShards` helper now, which `state/item-health/` was already using and this
ledger could not.

It also shrinks what one commit touches. Every run appended to a single file, so
git stored a new blob of the whole ledger several times a day; it now stores a
new blob of the current month.

**The cost was named in advance and it was accurate.** The change touched
`evals/writer.py`, `cli.py`, the `drift.yml` inline program, four utilities, the
canary builder, `payload.ts`, `commit-and-push.sh`'s staged list,
`REFRESH_PATHS`, the closed-world path map and the merge-driver test in
`test_workflows.py`, nine test modules, a fixture tree, and a migration of the
committed file. It is a Level 4 change taken on an owner instruction, against a
file that is not yet costing anything measurable.

One promise had to be defended explicitly. `writer.append` dedupes against
`OBSERVATION_KEY` across **every** shard, not the one being written, because an
observation is the same measurement whichever month it is re-taken in - a dedupe
scoped to the current month would let January's row come back in February and
turn a count over the ledger into a count of times the pipeline looked. The
header check moved ahead of the dedupe for the same reason: a corrupt shard is
corrupt whatever the call had to say, and checking after the dedupe let a stale
header survive an append that returned zero.

#### What the ledger is made of, and the three narrowings not taken

Measured 2026-08-31 on the committed file: 3,544 rows over nine days and 30 runs,
35 columns, 2,728,991 bytes; 770 bytes a row, 303,221 bytes a published day,
about 111 MB a year. There is no cap on `state/` the way there is a 1 GB cap on
the published site, so the runway is not a date - the cost is a checkout, paid by
every `plan`, `work`, `assemble` and CI job, several times a day.

What each reader needs, and how far back:

| Reader | What it needs | How far back |
| --- | --- | --- |
| `payload.ts` -> `model-work.ts` | per-**day** figures only | `console.max_window_days`, 366 |
| `backend/idhazh/drift.py` | per-item, per-domain | `recent_days` plus `baseline_days`, 35 days on the scheduled path |
| `backend/utilities/label_queue.py` | per-item, at the live `scorer_version` and `pipeline_fingerprint` | `evaluation.label_min_run_days`, 10 run-days |
| `backend/idhazh/evals/writer.py` | one row per `OBSERVATION_KEY`, to refuse a repeat | for ever |

**Twenty-four percent of every cell byte is derivable from `run_id`.** Four
columns are constant within a run - measured over all 30 committed runs, **none
varies**:

| Column | Distinct values | Runs that vary | Bytes | Share |
| --- | --- | --- | --- | --- |
| `scorer_version` | 5 | 0 of 30 | 288,448 | 10.6 percent |
| `pipeline_fingerprint` | 7 | 0 of 30 | 230,360 | 8.5 percent |
| `model_id` | 2 | 0 of 30 | 59,328 | 2.2 percent |
| `version` | 6 | 0 of 30 | 46,286 | 1.7 percent |

`scorer_version` alone is a 99-character string repeated 3,544 times to say one
of five things, and `RunRecord` **already carries** `scorer_version` and
`pipeline_fingerprints`, so two of the four are duplicated onto a committed
manifest today. `date` is a strict prefix of `run_id` on 3,544 of 3,544 rows, for
another 38,984 bytes. Together: **663,406 bytes, 24.3 percent, 111 MB a year to
84 MB.**

**This corrects the previous version of this section**, which said the one column
that looks like waste - `scorer_version` - could not move because `label_queue`
selects the live instrument by it. It can move: a per-run side table answers that
selection exactly, because the value never varies inside a run. What it costs is
real and is why it was not taken here: **a row stops being self-describing.**
Reading one today tells you which scorer produced it without opening anything
else, and that is a property somebody chose. 26 MB a year is not obviously worth
trading it for.

Two smaller narrowings, also measured and also not taken:

- **Ten columns no committed-file reader opens** - `attempt`, `hhem_full`,
  `hhem_delta`, `compression`, `extraction_suspect`, `determinism_violation`,
  `scored_at`, `evidential_density`, `speculative_density`, `self_repetition` -
  are 379,095 bytes, 13.9 percent. **"No reader" is not "delete" here.** This
  ledger is evidence, unlike `state/seen/`, which is a lookup: Rule #10 turns on
  being able to re-read a measurement to defend a design, and four of these got
  written descriptions on 2026-08-30. Deleting evidence a day after documenting
  it is churn.
- **`source_url` and `title`** are 643,696 bytes, 23.6 percent - the largest pair
  in the file - and both are read. `drift` names a domain from the first;
  `evals/evidence.py` and `label_queue` both open the second. This is where the
  `PublishedRow` and `SeenRow` narrowings do not repeat: those two dropped a
  column nobody opened, and this ledger has none.

**What would change the answer.** The console learning to read a daily aggregate,
which makes a short full-grain window enough; `state/` acquiring a measured
ceiling the way the published site has one; or the file passing a size where a
checkout is measurably slower. Sharding is what makes the first two cheap when
somebody wants them.

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

**What (a) costs instead is a list that can drift.** Twenty-two field names in [../../../frontend/src/lib/payload/project.ts](../../../frontend/src/lib/payload/project.ts) decide what a fetched day is able to render, and dropping one fails nothing: the page comes out slightly shorter and the reader never learns what they lost. Four things hold it. The module refuses to load, and so fails the build, if a forbidden name reaches the list - the shape `publish_telemetry.py` uses for the same class of mistake. `frontend/tests/staged-day.spec.ts` keeps its own copy of the names and holds the module's list against that copy, so widening the allow-list without widening the promise fails and names the field that arrived. `frontend/tests/search.spec.ts` drives the field where the loss would hurt most - the link out to the source - from the staged bytes through to the rendered link. And since 2026-08-31 the list is a generated schema as well: `test_the_projector_writes_exactly_the_shape_the_contract_names` reads the array out of the TypeScript and holds it against `DigestViewItem`, so a name added on one side of the language boundary and not the other fails rather than shipping a payload that does not match its own schema.

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

**Two lines, and only one of them fails a build.** Over `retention.site_budget_mb` (800 MB) the step prints an Actions warning and passes; past `retention.pages_hard_cap_mb` (1024 MB) it fails. Failing at 800 MB would stop publishing about two weeks before it had to, and a reader would lose a working site to a budget that still had room. Past the cap the bytes cannot be published at all, and failing in the job that measured them names the cause - a deploy that refuses them names nothing.

**The cap is a knob in one direction only.** It was a `Final` in `backend/idhazh/retention.py` until 2026-09-06, which made Rule #2's "the budget is the platform, not a preference" true only for as long as nobody edited the constant. It is now a config field bounded `le=1024`: an operator can name a smaller cap and the schema refuses a larger one, with a message naming the bound. Lowering it is the reason it is here - it buys an earlier and louder failure while there is still headroom to act in - and there is no value that buys more room, because the 1 GB is GitHub's and not ours. The console's site band still draws against the platform's own 1 GB rather than the configured cap: it reports the ceiling that exists, not the one this run chose to stop at.

**`site_bytes` on the run manifest stays what it always was.** It is the committed payload tree, six days of published manifests carry it, and changing what it means would be a contract break for a number that is genuinely useful about repository growth. What changed is that it now says which tree it holds, so nobody reads it as the site again ([../contracts/schemas.md](../contracts/schemas.md)).

**The deploy is not gated.** `pages.yml` prints `du -sb build` and always did. Adding the check there would need a Python install on the deploy path for no new coverage: every byte that reaches `main` passes through the `assemble` job or through `ci.yml`, and both now measure it before the push rather than after.

### A bad day is stopped before the commit; the weight ratchet is not (2026-08-29)

`digest.yml`'s `assemble` job ran `npm run build` and `npm run bundle-gate` in one step, before the commit that publishes. Two failures with nothing in common were welded together, and only one of them is worth a day.

**An invalid payload is caught before the commit, and since 2026-09-01 the build is no longer what catches it.** Prerendering used to serialise every story a day published into a document, so a payload that failed its contract failed the build. A reading document carries a seed now and the browser fetches the rest, so no build ever opens the stories past the seed. `idhazh validate-days` opens all of them, against the committed shape the build reads and the served shape a browser fetches, and it runs immediately before `npm run build` in both publishing jobs. That day is broken, it must not publish, and both checks still run before the commit. **What did change is the guarantee's name: a broken day can no longer be built became a broken day can no longer be merged**, and the publishing step is what keeps the pipeline's own pushes inside it - `ci.yml` never starts from a push the pipeline made ([frontend.md](frontend.md)).

**A weight failure is a number we wrote down ourselves.** `page_weight.ceilings_bytes` in `config/idhazh.json` says how heavy each named page's prerendered HTML may get. Past it the page still reads correctly - what grew is the document, not the meaning. The run that hit it lost the whole day and the two to three hours of runner time that produced it, and the reader lost a digest that was fine. So the gate moved after the commit, in `digest.yml` and in `backfill.yml` alike.

**Leaving it before the commit was the alternative, and it was rejected on the trade rather than on the principle.** It does buy something real: `main` stays green, and the ceiling is discussed before any reader sees the heavy page. It buys that by spending a published day and a runner budget (Rule #2) on a page nobody would have complained about. A digest that never arrives is the larger failure.
**It stays fatal, and that costs something.** The day publishes, then the `assemble` job goes red, and `main` goes red with it at the next CI run. Stated plainly: a ceiling crossed on a Tuesday leaves `main` red until somebody looks at it. That is the price of the trade and it is not hidden. The fix is one line in `config/idhazh.json`, raised in the commit that earned the bytes and saying what they buy ([../../how-to/run-the-gates.md](../../how-to/run-the-gates.md)). For `/console/` it is not to raise the number at all ([frontend.md](frontend.md#the-console-ceiling-is-a-tripwire-and-what-to-do-when-it-fires)). A warning was rejected for the same reason a green light on a broken alarm was: nobody reads it.

**"At the next CI run" is not "at the next push", and the difference is a delay.** `ci.yml` triggers on every push to `main`, but the pipeline's own pushes never start it: GitHub does not begin a workflow from a push made with the job's `GITHUB_TOKEN`. Measured 2026-08-29 - six `work:` and `digest:` commits on `main` carry **zero** check runs between them, while the two pull-request merges either side of them carry two each. So the red job the pipeline itself produces is the `assemble` job inside the digest run, and `main`'s own CI stays green until the next merge somebody pushes. Anyone diagnosing a red `site` job should read it as a page that has been over its ceiling since some earlier publish, not as something the merge in front of them did.

**The old position was never the guarantee its comment claimed, and moving the step did not close it either.** `Commit the day` retries a lost push by rebuilding the day against origin's new tip, and until 2026-08-30 nothing rebuilt the site afterwards. So the gate read the build made before the commit wherever the step sat, and a pass recorded before the push could describe a tree the retry had already replaced.

**That gap fired, and it cost a green job rather than a day.** Run `33270983446` published `2026-08-29` and deployed it, then went red at the gate: `/console/` measured 78,484 B against a recorded 79,230, which is 746 B under a tolerance of 64. Neither number was wrong and no page had changed. Ten commits landed on `main` while the run worked, three of them frontend source and one of them `frontend/bundle-baseline.json`, so the retry rebased onto a tip whose record was 79,230 while `frontend/build` still held the build made from the tip whose record was 78,479 - which that build cleared by 5 B. The gate weighed one tree's pages against another tree's records. The printed remedy is what makes it worth fixing rather than tolerating: the gate offers a copy-pasteable `78,484`, and recording it would file a number measured from the old source as the record for the new one, leaving the next real regression room to land inside the error.

**So a build runs after the last commit step, and the gate reads that one.** It is `npm run build` alone, measured at 17 s in that job's own steps against a run of 164 to 184 min. `npm ci` is deliberately not repeated with it: `frontend/package-lock.json` moved 8 times in 60 days while `frontend/src` and the baseline moved about 8 times a day, so a reinstall would delete `node_modules` on every run to cover the rarer of the two, and `npm ci` has its own partial-extract failure mode. The residual case is a race that carries a lockfile change, where the rebuild uses the dependency set already installed; that is no worse than what the gate read before, and CI on the next merge is the instrument for it. `backend/tests/test_workflows.py::test_the_weight_ratchet_reads_a_build_of_the_tree_that_was_pushed` holds the order for both publishing jobs.

**Re-running the failed job is not the repair, and it looks like one.** A re-run checks out the original commit, so it rebuilds the old source, compares it with the old record and passes - green for a tree that is no longer `main`. Re-run granularity and what it does and does not repeat are in [../../reference/github-actions.md](../../reference/github-actions.md#platform-limits-that-shape-the-workflows).

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
| Serving `DigestDay` whole and deleting the projection | It is the same objection one level on, with a bigger number behind it. Measured 2026-08-31 over 11 committed days and 3,733 items, `gzip -9`: the committed day is 792.65 bytes an item against the projection's 468.58, so serving it whole is 69.2 percent more on the wire - and 40.0 percent of that is a vector block no browser opens. Bytes are what this migration is for. |
| Leaving the served field list a JavaScript array | It was the right answer while the only reader shipped in the same build. It stops being one when a browser we cannot upgrade parses the file: a persisted shape a reader's browser reads is a contract before logic reads it (Rule #3), and without a `version` an older shell has nothing to branch on when the shape next moves. |
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
| Leaving the page-weight gate before the commit | It keeps `main` green by spending a finished day and the two to three hours that built it, on a page that reads correctly and that no reader would have complained about. See [A bad day is stopped before the commit; the weight ratchet is not](#a-bad-day-is-stopped-before-the-commit-the-weight-ratchet-is-not-2026-08-29). |
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
- [../../reference/measurements.md](../../archive/measurements-2026-08.md#sizing-the-archive-index) - what a browse entry, a vector and a month shard actually cost.
- [../../reference/measurements.md](../../reference/measurements.md#days-to-the-1-gb-pages-ceiling) - the cap date, the per-published-day growth rate, and the units error that made both wrong until 2026-08-27.
- [../../reference/measurements.md](../../archive/measurements-2026-08.md#the-site-page-by-page-after-the-payload-narrowing-2026-08-27) - what each page and the whole site weigh today.
- [../../reference/measurements.md](../../reference/measurements.md#the-month-search-index-as-written) - the shard that exists: its bytes, its rebuild cost, and the bijection it holds.
- [../../concepts/config.md](../../concepts/config.md) - where the retention knobs live and the build-time versus shipped-config rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11) and git hygiene (section 8).
