# Published Layout

**Last Updated**: 2026-09-23

Where the pipeline writes what a reader reads, what a reader's URL looks like, and what a day is once five runs have added to it. Assemble is the stage that produces all of it ([../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md)); this page owns the shape it writes into and the promises that shape makes.

What happens to any of it afterwards is the other half, and it is [retention.md](retention.md): unpublishing a day, what bounds the committed state tree, and the score shards that turn into summaries once they age out.

## Where each part is written up

Six pages, one question each. Arrive at the one holding your question and stop.

| Page | The question it answers |
| --- | --- |
| this one | Where a file goes, what a reader's address is, and what a day is once five runs have added to it |
| [what-a-published-item-says-about-itself.md](what-a-published-item-says-about-itself.md) | Why is this story here, whose clock is that time, and what does an absent field mean |
| [how-a-day-is-ordered-and-what-each-desk-published.md](how-a-day-is-ordered-and-what-each-desk-published.md) | What order the page comes in, what chooses the leading block, and why a desk ran what it ran |
| [what-a-month-shard-holds-and-how-it-reaches-a-browser.md](what-a-month-shard-holds-and-how-it-reaches-a-browser.md) | What one month of the search index holds, what it costs, and how it is staged |
| [the-served-day-and-the-documents-that-stopped-being-written.md](the-served-day-and-the-documents-that-stopped-being-written.md) | What a browser fetches for a dated address, what the 116 deleted documents were worth, and the runway it bought |
| [what-the-site-weighs-and-when-it-stops-fitting.md](what-the-site-weighs-and-when-it-stops-fitting.md) | What the site weighs, which tree is measured, and when it stops fitting under 1 GB |

## Two contracts, not one

The layout on disk and the address in the reader's browser are **separate contracts that are allowed to disagree**. This is the decision everything else hangs off.

| | Shape | Optimised for |
| --- | --- | --- |
| **Data path** | segmented `<YYYY>/<MM>/<DD>/` | tree churn, and a single glob to prune a month |
| **Reader route** | one segment `<YYYY-MM-DD>` | a human reading it once, in a phone address bar |

Coupling them means a change of mind about URL aesthetics rewrites every committed payload. Separating them costs one pure function.

```
frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json the whole day, every item
frontend/public/digest/<YYYY>/<MM>/<DD>/run.json append-only runs[] for that date
frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.json  optional visual, drawn in the browser
frontend/public/assist/index/<YYYY-MM>.json one month of items, for browsing and search
frontend/public/assist/index/<YYYY-MM>.bin that month's vectors, raw int8
state/scores/<YYYY>/<MM>/<DD>/ the ledger - one row per measurement, never published twice
state/score-index/<YYYY>/<MM>/<DD>/ the identity of every measurement that day holds, 76 bytes each
state/score-archive/<YYYY-MM>.json a score month past its full-grain window, as totals plus a dedupe index
```

```
/ the newest published day, rendered inline moving
/<YYYY-MM-DD>/ that day, every vertical canonical
/<YYYY-MM-DD>/<vertical>/ that day, one vertical - a projection canonical
/<YYYY-MM-DD>/#<item id> an item anchor
/archive/ every surviving day moving
/evals/ a signpost to /console/, where the scores went
/console/ the run-health dashboard moving
```

**One day directory is the deletion atom.** Nothing outside it points into its interior except the append-only ledger, which is what makes pruning a single operation with no second edit.

**No hash appears in any path, filename or URL.** A day carries two reader-facing addresses and both are the item's own id: the anchor `#<item id>` and the visual's marks, `ai-wfyypy5sgvnwcxd3.json`. The id is derived from the article's address, so a later run of the same day reaches the same item ([../sources/freshness.md](../sources/freshness.md)), and it is not a digest of anything - a digest here is 32 or 64 hex characters, and an item id is neither of those widths. The sha256 `url_key` that identity for dedupe actually rests on stays a field on the payload and never becomes a path segment. Paths are for humans and for globs; a hash is for the contract.

**Two id shapes are live, and the pattern that accepts them never contracts.** Every day published before 2026-09-12 carries `<vertical>-<ten decimal digits>`; a published day is frozen, so not one of those ids moved. A run writes `<vertical>-<sixteen Crockford base32 symbols>` from 2026-09-12 - the 32-symbol alphabet without `i`, `l`, `o` and `u`, so no id can be misread aloud, and a subset of the slug alphabet, so the id is still a slug. **Nothing sorts ids across days**, because the two shapes do not order against each other.

**The asset name was `<vertical>-<NN>` until 2026-08-27, and both shapes are live in committed data.** The ordinal came from a counter, a counter has to be seeded from something a process can observe, and two runs of one day observed different things - which cost a finished day ([one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md)). Naming the file after the item makes the path a function of the item, so no two runs and no two shards can pick one path for two stories. **No old address broke and none had to be migrated**: `assemble` copies `VisualDecision.data_path` into the day payload verbatim, the page fetches that stored string, and the build stages by the same item-shaped name - so a name is data the day carries, never a rule the reader re-derives. That is the same property that makes the two contracts at the top of this page separable, applied one level down.

**`latest` and `archive` are derived at build time** from the directory listing, never committed. A committed pointer is exactly the file that goes stale after a prune or a raced deploy.

**A visual is one file named for its item, and nothing recomputes the name.** From 2026-09-13 a published visual is `<item_id>.json` - its marks - and the day payload points at it with `DigestVisual.data_path` ([where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md)). It replaced `<item_id>.svg`, which was the drawing the pipeline used to render; `DigestVisual.path` retired with it, and the 24 committed days that still carry the key are read through a named pop rather than by widening the model. `digest.json` and `run.json` sit in the same directory and belong to the day rather than to a story; neither can collide, because an item id ends in a hyphen and a run of digits or sixteen base32 symbols, so no item is called `digest` or `run`. That is also the rule the retention prune and the bundle staging read, rather than a file extension - a `.json` suffix no longer tells a visual apart from the record that a day happened.

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
- **A run can come back as itself, and that is one run.** A run files one block named for itself, so a run that comes back rewrites its own block rather than adding a second one. `n` is a position the fold assigns by counting down the blocks it can see, and anything else needing that number reads it off the day - so the day and the manifest cannot disagree about how many times the day was built. The manifest's contract still refuses a `runs` list in which two runs share an ordinal, and after the fold that clause checks the fold's own arithmetic rather than a writer's claim.
- **The day's vectors grow with it.** A run encodes only the items it summarized, so it merges its block into the one the day already carried instead of replacing it. Replacing left a day searchable over its last run alone: the committed 2026-08-24 day held 145 vectors for 731 items, which is 19.8 percent of them. A newer vector wins a collision, because it was encoded from the newer text. A block that names another model, width or dtype replaces the old one whole rather than joining it.
- **An item's words are written once, by the run that introduced it.** No run revises. Three gates hold that, and all three are load-bearing for something else: `rank.plan_vertical` drops a candidate whose address is already in `state/published/`, `cli` supplies that set, and `assemble.build_day` drops an item the day already holds. The published item carries `updated_at` and `updated_by_run` for a revision that cannot happen yet, and both are null in every committed payload ([what-a-published-item-says-about-itself.md](what-a-published-item-says-about-itself.md#the-two-revision-fields-stay-unwritten)). **If a revision is ever built, it must be visible.** Silently improving wording under someone who already read it makes them doubt their own memory, and their trust in the summaries is the entire product.
- **No run identifier appears in any data path or any reader URL.** It lives in the run manifest and in the day notice, on the pages that render a day.

The returning reader is protected by the read mark and by the run-scoped "new" grouping - both of which work identically for everyone - rather than by freezing an order, which cannot be done in a shared artifact without rendering a different page per person.

## The day is folded from one block per run

**No run writes `digest.json`.** A run writes its own block -
`state/digest-fragments/<YYYY>/<MM>/<DD>/<run_id>.json`, a `DigestRunFragment` -
and the published day is folded from every block that is there. That is the
whole reason the shape exists: a file with one writer cannot carry two runs'
disagreement, and `digest.json` had been exactly that.

**The blocks are not under `frontend/public/`, and absence is what keeps them
out.** Everything in that tree is copied verbatim into the deploy, so blocks
filed there would be served, crawlable, and a second whole copy of every story
on a site Pages refuses over 1 GB. There is no URL, so there is nothing to index
and nothing for a reader to land on. A `robots.txt` line would be a request to a
crawler rather than a control, and it would leave the bytes in the deploy.

**Whole blocks, in landing order, never interleaved.** The sort is
`("completed_at", "run_id")` and both are required: `completed_at` is when the
run finished, and `run_id` breaks a same-second tie and is unique by
construction. A block keeps the position it landed in, which is what lets a
reader come back and find what they were part-way through where they left it
([../../concepts/placement.md](../../concepts/placement.md#one-order-inside-what-a-run-added)).

**A fold that sees fewer blocks is not an error and needs no special case.** It
emits a valid prefix of the day and the next fold appends the rest, because the
fold inherits position rather than recomputing a key. Two folds over the same
set of blocks emit identical bytes, and git merges two identical adds with no
conflict at all - which is what makes re-folding free.

**`generated_at` is the newest block's completion, not the fold's own clock.** A
wall clock would make two folds of one set of blocks emit different bytes, which
puts an add/add conflict back on the one file every reader opens - the defect
this shape exists to remove, re-introduced on the published side. A maximum over
the set is monotonic and deterministic instead. **What the rule costs**: a
rewrite that adds no run - a retention pass deleting an old drawing, say -
changes the payload and leaves the stamp where it was, so a browser already
holding that day can draw a path that has just gone, until it reloads. That is
one broken drawing in one open tab, against a conflict on every re-fold, which
costs the day for every reader.

**A day written before runs filed their own blocks is left exactly as it is.** A
recorded run carrying no `run_id` is a block no fragment can reproduce, so
folding that day would publish only what the blocks hold and delete every story
the reader has already been shown. `assemble.predates_fragments` is that one
branch, and it retires itself: once a date's runs all name themselves it is
false forever after.

**`items_failed` and `partial` are two readings of one set**, so the fold
derives both from it: the union of every block's failed item ids, less the items
that did publish. Reading `partial` off the blocks instead - true if any block
said so - is monotonic, so an article that failed at 02:20 and landed at 06:20
would report `partial` true beside `items_failed` zero, which the contract
refuses.

What the push does with a block, and why a `digest.json` two runs both computed
used to lose the day, is
[in committing.md](committing.md#two-runs-of-one-day-work-at-the-same-time-and-nothing-queues-them).

Authority: Jony and Fowler, converged, 2026-09-22.

## One file per day

A day is one JSON payload carrying every item. A vertical route is a filter over that same payload, never a second file.

The consequence worth protecting: **rendering any page costs at most two requests, no matter how old the archive is.** Any scheme whose request count or index size grows with total history is rejected on sight, at any granularity. A per-item file multiplies requests and defeats compression - a small body never warms the gzip dictionary, where a whole day reaches the measured prose ratio. A global index of everything ever published grows without bound on the hot path.

**One page already breaks that rule, and there is now a number on it.** `/archive/` inlines every committed day so on-device search can see the whole corpus, which is the global-index alternative below in everything but name. Measured 2026-08-26 over the six committed days, 2,121 items, at the gzip level the Pages edge actually serves: a browse entry - item id, date, vertical, title - costs **45.5 bytes**, and one committed int8 vector costs **249.8 bytes** ([../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md#sizing-the-archive-index)). A 30-day month is therefore 482 KB of browse entries and 2.6 MB of vectors at the rate those six days ran, and 1.07 MB and 6.0 MB at the ceiling that five runs of 160 items a day allows. The granularity and the budget that answer it - a month, and 1.5 MB - are in [what-a-month-shard-holds-and-how-it-reaches-a-browser.md](what-a-month-shard-holds-and-how-it-reaches-a-browser.md).

## Two rules a reading page owes an address

**A day notice prints a count it is handed, never one it takes off the list in
hand.** A seeded list grows as the browser fetches, so a count read off it ticks
up while the reader watches, and with script off it freezes at the seed - four
lines above a topic row stating the real total. The figure is the day's total
across `day.verticals`, or one desk's `count` on a topic route: a bounded fact
that does not grow with the seed. A topic page states its own desk, because the
reader chose that desk and the whole day is one pill away on the same row.

**A fragment names a story anywhere in the day, so the pager reaches it.**
`/<YYYY-MM-DD>/#<item id>` is a canonical reader address, and the stream pages,
so most stories are not elements on the page when the fragment is read.
`DigestList` reads the fragment on mount and on `hashchange`, finds that story's
position in the order it is drawing, pages far enough to draw it, then restores
scroll position and keyboard focus once the element exists. An already-drawn
lead needs no extra paging, but still receives focus when its link changes the
fragment, including a return to an earlier lead. With no fragment the reach is
zero, so an ordinary link draws what it always drew. The cost is one visit and
only the visit that asked: the deep link draws the whole day rather than a page of it.
A fragment naming a story the day never held says so, in a live region, and it
waits until the list in hand is the whole list - a story still on its way is not
a story that was never here.

## The frontend stack

Svelte 5, Vite, TypeScript, Tailwind, vitest, Playwright, `json-schema-to-typescript`, and `ajv`.

The spine matches both sibling projects, so tooling knowledge transfers across a one-maintainer estate. The profile is deliberately the leaner of the two siblings: this site renders a small committed JSON payload and needs no query engine, no charting library and no map projection. `ajv` rather than `zod` because it validates against a JSON Schema a contract computes for itself, where `zod` would need a second declaration of every shape.

Runtime inference in the browser is not a stack choice to be weighed; Guardrail #1 forbids it.

## Design rationale

The reader-facing half of this design is driven by one asymmetry: a reader who loses trust does not complain, they simply stop coming back, and nothing in any test suite detects it. So the failure modes that shape the layout are the silent ones - a bookmark that looks healthy but is a year stale, a page that quietly rearranges between two readings, a link that redirects somewhere plausible instead of admitting it is gone.

That is why the plain address is the moving one and dated addresses are the frozen ones, rather than the reverse. The tempting design makes the dated page canonical and the front page a pointer to it; the failure it invites is a front page that lags, which presents as a perfectly healthy site showing last month's news.

The engineering half is driven by arithmetic rather than preference. Segmented date directories were chosen over a flat layout because a flat directory of tens of thousands of entries rewrites a large tree object on every commit. One file per day was chosen over per-item files because compression works far better across a whole day than across many small bodies, and because a per-item file buys nothing an already-fetched day payload does not have.

### Two append paths, and only one of them deduplicates

`idhazh.ledger.extend_ledger_file` writes every row it is handed. `idhazh.evals.writer.append_segment` refuses a row whose address, inputs, words and scorer version it already holds. That looked like one of them being wrong, and it is not: **the two write different kinds of row.** An eval row is a measurement, so re-measuring an item nothing changed about has nothing new to say. A state row is a fact about a run - this feed answered at this hour, this item finished - and a run that runs twice did happen twice. Collapsing those would turn a count of runs into a count of days.

So the blind path stays blind, and each caller that owns a repeat is now named next to it. Two of the four ledgers absorb a repeat at read time: `load_seen` and `load_published` keep the earliest of two rows, so a duplicate costs bytes and never moves a date. The health pair does not, and that is stated rather than guarded: `discover.resting` counts failures to decide a quarantine, so a duplicated failure counts twice. Measured on this checkout 2026-08-27, the published ledger held 2,097 rows and 2,097 distinct addresses in the flat file it has since moved off.

**Where the code was already safe, the fix was a sentence and not a guard.** A guard that can never fire is untested branch weight, and it hides which file the guarantee actually lives in. `stages.assemble._published_rows` reads as "everything the day holds" and behaves as "what this run added", and it does that because the plan a later run built has already dropped every published address. Its comment used to claim the filter itself; it now names the upstream facts it depends on, so the next person to widen the plan sees what they would break.

**One path was not safe, and that one was fixed.** The day's run reference counted what the current attempt added rather than what the number introduced, so a replay after a lost manifest write built a payload its own contract rejects - `run 1 items_added disagrees with the items it introduced` - and the day was lost rather than doubled. The count now comes from the assembled day, which is the definition the contract validates against.

### This page became a shape page and an index on 2026-09-23

Five pages came off it. It answered at least six questions at about 26,700 tokens, which made it the heaviest page the routing table could send an agent to once the config, frontend and visuals pages were cut the same day. One section titled "The month search index" had grown to 34 percent of the page and held the whole shell-and-fetch migration under it - the served day's contract, the 116 deleted documents, the topic routes, the day routes and the cap date - so a reader who came to ask what a month shard costs had to read past four route migrations to find out.

The stem keeps the question somebody arrives with - where does a file go, what is a reader's address, and what is a day - and each child keeps one of the others. The cost is real and is the usual one: a ruling whose page nobody can guess now costs a table lookup, where before it cost a long scroll ([../../reference/documentation-structure.md](../../reference/documentation-structure.md)). Authority: Fowler.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A `latest` route alongside `/` | Two moving pointers. A reader bookmarks one and shares the other, and they disagree about which is canonical. |
| A redirect at `/` | A blank first paint and a wasted round trip on the site's most-visited address. |
| A committed pointer file naming the newest day | Derived data committed as fact, and the first thing to go stale after a prune. Deriving it at build time is what makes retention a one-step operation. |
| One file per item | Multiplies requests, defeats compression, and duplicates bytes the day payload already carries. |
| One file per vertical per day | Several sources for one fact, to avoid a trivial client-side filter. |
| A global index of every item ever published | Unbounded growth on the hot path of every page load. Measured 2026-08-26: 45.5 gzipped bytes an entry, so a year at the structural ceiling is 12.7 MB of browse entries before a single vector joins them. |
| A run identifier in the path | One item at two addresses, so the same item is reachable two ways and neither is canonical. |
| A hash in a filename or URL | Unreadable, unspeakable, and unguessable-by-accident rather than unguessable-by-design. On a public repo with a public index it hides nothing, and it costs the reader a path they cannot reason about. An item id is not this: a digest here is 32 or 64 hex characters, an id is sixteen Crockford base32 symbols or the ten decimal digits that preceded them, and it is already the anchor a reader lands on. |
| A per-vertical ordinal in a rendered asset's filename | `ai-03.svg` reads better than `ai-4821903756.svg` and cannot be made correct. The ordinal comes from a counter, every seeding rule reads something a process can observe, and two runs of one day observe different things - which lost a finished day on 2026-08-25 ([one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md)). Speakability is worth less than a name two stories can never share. |
| Rewriting the committed days into the new asset name | Nothing is broken to fix. A path is stored on the payload, so every old day still resolves, and a rewrite would move addresses a reader may already hold in exchange for tidiness. |
| A title-derived slug in a URL | Titles originate in fetched text, and fetched text never becomes a URL (Guardrail #11). |
| Filing the run blocks under `frontend/public/` | Everything in that tree is copied verbatim into the deploy, so they would be served, crawlable, and a second whole copy of every story on a site Pages refuses over 1 GB. |
| A wall-clock `generated_at` on the folded day | Two folds of one set of blocks would emit different bytes, which puts an add/add conflict back on the one file every reader opens. |
| Deduplicating the state ledgers the way the eval ledger does | A state row is a fact about a run, not a measurement. A feed that answered twice answered twice, and collapsing the two rows turns a count of runs into a count of days - which is the number `discover.resting` reads to decide a quarantine. |
| A duplicate-run guard in `build_manifest` to match the one in `build_day` | Unreachable. `RunManifest` refuses a `runs` list in which two runs share an ordinal, so the next number cannot already be taken. The branch would never run and no test could reach it. |
| Reusing the render-failure state to mark a prune | One field carrying two different facts, which is the band-aid Guardrail #5 forbids. |

## See also

- [what-a-published-item-says-about-itself.md](what-a-published-item-says-about-itself.md) - why a story is here, and whose clock its time is.
- [how-a-day-is-ordered-and-what-each-desk-published.md](how-a-day-is-ordered-and-what-each-desk-published.md) - the two orders, and each desk's three counts.
- [what-a-month-shard-holds-and-how-it-reaches-a-browser.md](what-a-month-shard-holds-and-how-it-reaches-a-browser.md) - the search index, its ceilings, and the staging step.
- [the-served-day-and-the-documents-that-stopped-being-written.md](the-served-day-and-the-documents-that-stopped-being-written.md) - what a browser fetches, and what the deleted documents were worth.
- [what-the-site-weighs-and-when-it-stops-fitting.md](what-the-site-weighs-and-when-it-stops-fitting.md) - the 1 GB cap, the instrument, and the runway.
- [retention.md](retention.md) - the other half: what may be deleted, when, and what bounds every collection a run appends to.
- [committing.md](committing.md) - what the push does with a run's block.
- [autotune-content-similarity.md](autotune-content-similarity.md) - when two items are one story, and what the page does about it.
- [../../concepts/placement.md](../../concepts/placement.md) - the one order this payload carries, and the frame a person set over its head.
- [../../concepts/digest.md](../../concepts/digest.md) - what a reader gets and the visual rule this layout serves.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the Assemble stage that writes all of this.
- [../sources/discovery.md](../sources/discovery.md) - where the day's items come from, and the same retire-never-delete discipline applied to sources.
- [../sources/freshness.md](../sources/freshness.md) - the run cadence, where an item's id comes from, and why a day has no cap.
- [../../reference/github-actions.md](../../reference/github-actions.md) - workflow names and exact triggers.
- [frontend.md](frontend.md) - the routes these addresses resolve to.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload contracts and the versioning rules a deletion has to honour.
- [../../concepts/config.md](../../concepts/config.md) - where the retention knobs live and the build-time versus shipped-config rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11) and git hygiene (section 8).
