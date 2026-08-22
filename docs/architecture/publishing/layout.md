# Published Layout

**Last Updated**: 2026-08-20

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
frontend/public/digest/<YYYY>/<MM>/<DD>/<vertical>-<NN>.webp  optional visual
state/scores.csv                                        the ledger - one path, never published twice
```

```
/                          the newest published day, rendered inline    moving
/<YYYY-MM-DD>/             that day, every vertical                     canonical
/<YYYY-MM-DD>/<vertical>/  that day, one vertical - a projection        canonical
/<YYYY-MM-DD>/#<vertical>-<NN>   an item anchor
/archive/                  every surviving day                          moving
/evals/                    the dashboard                                moving
```

**One day directory is the deletion atom.** Nothing outside it points into its interior except the append-only ledger, which is what makes pruning a single operation with no second edit.

**No hash appears in any path, filename or URL.** An item is addressed by its vertical and its ordinal within the day - `ai-03` - which is predictable, derivable without a lookup, free of fetched text, and speakable. Identity for dedupe is a field on the payload, not a segment of a path: paths are for humans and for globs, identity is for the contract.

**`latest` and `archive` are derived at build time** from the directory listing, never committed. A committed pointer is exactly the file that goes stale after a prune or a raced deploy.

## The day is one artifact, shared by everyone

The pipeline may run several times in one day. The rule that governs what that means starts from a fact about the medium: **there is one published payload, and every reader gets the same bytes.** Reading is private and per-device; ordering is public and global. Ordering can therefore never depend on who has read what.

- **The published order is global, deterministic and identical for every reader.** It is a pure function of the ranking inputs, and no reader's behaviour changes it. Two people opening the same dated URL see the same items in the same order, always.
- **An item is never removed, demoted or hidden because someone read it.** One person having read an item says nothing about the thousands who have not. This is the behaviour of every working news front page: the story stays where its importance puts it, read or unread.
- **Read-state is a client-side mark and nothing more.** It may change how an item looks. It may never change where an item sits, whether it appears, or how it ranks. The only exception is a filter the reader switches on themselves, and it is off by default.
- **"New" is a property of the item, not of the reader.** An item is new because a later run introduced it, which is true for everybody and needs no storage to assert. It is never a diff against a remembered last-visit time, which would be a claim that evaporates the moment a browser is cleared.
- **Membership only grows, and the cap is a day cap.** Several runs produce one day of the configured size, not several days' worth.
- **A revision is visible or it does not happen.** If a later run changes an item's summary text, that item says so. Silently improving wording under someone who already read it makes them doubt their own memory, and their trust in the summaries is the entire product.
- **No run identifier appears in any data path or any reader URL.** It lives in the run manifest and in the page footer.

The returning reader is protected by the read mark and by the run-scoped "new" grouping - both of which work identically for everyone - rather than by freezing an order, which cannot be done in a shared artifact without rendering a different page per person.

## One file per day

A day is one JSON payload carrying every item. A vertical route is a filter over that same payload, never a second file.

The consequence worth protecting: **rendering any page costs at most two requests, no matter how old the archive is.** Any scheme whose request count or index size grows with total history is rejected on sight, at any granularity. A per-item file multiplies requests and defeats compression - a small body never warms the gzip dictionary, where a whole day reaches the measured prose ratio. A global index of everything ever published grows without bound on the hot path.

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

Runtime inference in the browser is not a stack choice to be weighed; Holy Law #1 forbids it.

## Design rationale

The reader-facing half of this design is driven by one asymmetry: a reader who loses trust does not complain, they simply stop coming back, and nothing in any test suite detects it. So the failure modes that shape the layout are the silent ones - a bookmark that looks healthy but is a year stale, a page that quietly rearranges between two readings, a link that redirects somewhere plausible instead of admitting it is gone.

That is why the plain address is the moving one and dated addresses are the frozen ones, rather than the reverse. The tempting design makes the dated page canonical and the front page a pointer to it; the failure it invites is a front page that lags, which presents as a perfectly healthy site showing last month's news.

The engineering half is driven by arithmetic rather than preference. Segmented date directories were chosen over a flat layout because a flat directory of tens of thousands of entries rewrites a large tree object on every commit. One file per day was chosen over per-item files because compression works far better across a whole day than across many small bodies, and because a per-item file buys nothing an already-fetched day payload does not have.

Retention was demoted to third lever after the byte arithmetic showed that encoding and the existing visual rule together move the ceiling from months to years. A policy that deletes a reader's archive to reclaim a fraction of a percent of the bytes would have been solving the wrong problem.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A `latest` route alongside `/` | Two moving pointers. A reader bookmarks one and shares the other, and they disagree about which is canonical. |
| A redirect at `/` | A blank first paint and a wasted round trip on the site's most-visited address. |
| A committed pointer file naming the newest day | Derived data committed as fact, and the first thing to go stale after a prune. Deriving it at build time is what makes retention a one-step operation. |
| One file per item | Multiplies requests, defeats compression, and duplicates bytes the day payload already carries. |
| One file per vertical per day | Several sources for one fact, to avoid a trivial client-side filter. |
| A global index of every item ever published | Unbounded growth on the hot path of every page load. |
| Re-ranking a day on a later run | Contradicts the memory of a reader who already read it. |
| A run identifier in the path | One item at two addresses, so the same item is reachable two ways and neither is canonical. |
| A hash in a filename or URL | Unreadable, unspeakable, and unguessable-by-accident rather than unguessable-by-design. On a public repo with a public index it hides nothing, and it costs the reader a path they cannot reason about. |
| A title-derived slug in a URL | Titles originate in fetched text, and fetched text never becomes a URL (Holy Law #11). |
| Deleting text alongside images under one retention knob | Text is a fraction of a percent of the bytes. |
| Reusing the render-failure state to mark a prune | One field carrying two different facts, which is the band-aid Holy Law #5 forbids. |

## See also

- [../../concepts/digest.md](../../concepts/digest.md) - what a reader gets and the visual rule this layout serves.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the Assemble stage that writes all of this.
- [../sources/discovery.md](../sources/discovery.md) - where the day's items come from, and the same retire-never-delete discipline applied to sources.
- [../contracts/schemas.md](../contracts/schemas.md) - the payload contracts and the versioning rules a deletion has to honour.
- [../../concepts/config.md](../../concepts/config.md) - where the retention knobs live and the build-time versus shipped-config rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11) and git hygiene (section 8).
