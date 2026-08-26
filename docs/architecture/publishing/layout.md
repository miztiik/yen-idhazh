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

**Sharding by month does not by itself bound the browse index.** At 45.5 bytes an entry, 300 KB buys about 6,700 entries - a fortnight at the observed rate and eight days at the structural ceiling. A month shard is over 300 KB at every rate measured, so a shard granularity and an index budget have to be chosen together rather than one after the other.

**The gzip window settles long before a shard does.** Over the same corpus, per-item gzipped bytes barely move between a quarter of the blob and all of it: 249.6 to 249.8 for the vectors, and 47.3 down to 45.5 for the browse entries. So the compression argument above is about a per-item body of hundreds of bytes, not about a shard of hundreds of kilobytes - any shard past about 70 KB already gets the full ratio.
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
- [../../concepts/config.md](../../concepts/config.md) - where the retention knobs live and the build-time versus shipped-config rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11) and git hygiene (section 8).
