# Data Growth

**Last Updated**: 2026-09-20

What this repository requires of work whose cost rises as the archive grows,
where each family of that work is heading, and the shortcuts that look like an
answer and are not.

**This page is the destination, not a description of today's tree.** What is
built now is in the doc that owns each subsystem.
[CLAUDE.md](../../CLAUDE.md) Guardrail #12 refuses a cost that rises because the
repository accumulated more data;
[growing-reads.md](../concepts/growing-reads.md) gives that refusal an address on
the reader's side and [partitions.md](../concepts/partitions.md) gives it one on
the writer's. This page is what the refusal means once a design has to satisfy
it.

## The requirement, written so it can be met

Literal constant time for everything is impossible, and promising it hides the
cases that matter. Reading new text, validating arbitrary input, returning every
matching row, drawing every mark and uploading the complete site each cost what
their own input or output costs. Exact vector ranking is not constant time
either.

The requirement that can be met is narrower:

> An ordinary lookup, append or page interaction must not revisit unrelated
> history.

**The whole cost counts, not the part that was made fast.** Cold loading, index
maintenance, correction, deletion, transfer and output all count. A design that
moves the work to startup has moved it rather than removed it, and a cache-hit
latency quoted as an end-to-end cost is a selection rather than a measurement.

**Ordinary excludes a deliberate rebuild.** A command whose purpose is to
reconstruct may read everything, and says so in its name and its flags. What is
refused is an ordinary run paying that cost because nobody named a bound.

## The ruling

Replace repeated history reconstruction with indexed state, immutable run
outputs, precomputed page facts and explicit changed-partition processing.
**Delete the old reader in the commit its replacement takes over**, or the scan
survives as the path that runs whenever the new one misses.

**A cache in front of an existing scan is not the answer.** Keyed on a date, a
path, a schema stamp or a file time, it is stale the first time a day is
republished, a row is corrected or a knob changes - and the scan it fronts is
still there, still growing, now harder to see.

**Structure first, meaning second.** A change that removes repeated work returns
identical results. A change to what a measurement means, what a reader sees, or
which sources run is a separate commit carrying its own argument. Combined, they
make a rewrite nobody can check.

## Where each family of work is going

This is a set of destinations, not an order of work. Fixed test inputs and local
algorithm fixes land independently of any storage change.

| Family | Decision | What disappears | Honest remaining cost |
| --- | --- | --- | --- |
| Local algorithms | Remove repeated full-history joins, bucket spreading and per-call reconstruction. | Run-by-health scans, copied grouping prefixes, repeated id and date lookups, unread preformatted strings. | One input pass plus the sorting and output the answer needs. No format change is required for these. |
| Operational state | Give operational state exact indexed ownership. | Scan-before-append, global deduplication repair, lifetime lookup loads, union-merge settlement. | Indexed reads and updates, validation of new input, durable commit and transfer. |
| Page facts | Have the producer publish page-ready facts. | Frontend raw-state ingestion, item-level dashboard reduction, whole-day reads taken for a count or a label. | Changed facts and bounded page reads. Maintaining an exact statistic is still real work. |
| Publication reuse | Give publication explicit changed objects and stable code assets. | Clearing and restaging unchanged trees; regenerating every dated page for an ordinary append. | Cold rebuild, template-wide invalidation, and complete Pages packaging and upload. |
| Regression inputs | Replace live-archive test inputs with fixed cases. | Tests that grow with every publish, repeated migration replay, duplicated fixture compilation. | Tests grow with authored behaviour. An explicit current-data audit grows with the data it certifies. |
| Reader-visible limits | Change exact search, story grouping or all-history presentation only against a stated quality contract. | Nothing, until somebody accepts the loss. | Recall loss, pagination changes and lost history are stated and tested, never shipped as an optimisation. |

## What a replacement owes

A new persisted shape or a change of authoritative state is a Level 5 change
under [CLAUDE.md](../../CLAUDE.md) section 6. Deletion and direct cutover are
allowed; losing source evidence, reader content, the meaning of a measurement or
a cached reader's compatibility without saying so is not.

| Concern | The rule | What retires the old path |
| --- | --- | --- |
| Write ownership | Workers emit immutable run results and early failure evidence. One serialised owner applies them under idempotent keys. Serialising publication does not mean serialising inference. | Cancelled work stays recorded, and replayed or overlapping shards settle without line-based repair. |
| Exact lookup | Indexed keys for publication, observations, endpoint events and completed stage results, held in the standard library on the developer and CI side - never a hosted service (Guardrail #1). | Cold restore, update, git delta and largest-file costs measured. An unbounded monolithic blob is refused in favour of bounded partitions under a bounded-fanout catalogue. |
| One source of truth | One authoritative representation per fact. Projections, catalogues and build receipts are derived outputs with a declared owner, not competing stores. | A reader no longer rebuilds a missing index from all history. An absent required generation fails validation or names a degraded state. |
| Catalogues | Fixed-size latest headers and bounded catalogue pages, preserving exact key and date routing. | Cold access reads the lookup path and the requested pages only. A growing root JSON is not a catalogue. |
| Exact summaries | Additive counters, paired sums and exact distinct-member state. Keep the value population wherever a median or a percentile is required. | Corrections and deletions retract the old contribution, and expiry removes the right population. |
| Build identity | Reuse binds to code, schema, reducer, configuration, effective data-root contents, renderer and asset identity. A data revision stays distinct from a code epoch. | A same-size content change, a removed file, a changed knob or a changed renderer invalidates exactly its dependents. A filename, an mtime or a schema date does not. |
| Cutover | Convert owned private data once, comparing records, keys, nulls, declared winner rules, aggregates and output membership. | Old readers, aliases, repair commands and migration-only tests are deleted in that commit. Artefacts already in flight are converted or drained, never assumed upgraded by a repository rewrite. |
| Reader compatibility | Move readers to one coherent revision. Keep an old static address only while a cached or offline reader still needs it. | Existing dated links and cached shells still work. Removing a public address is an accepted reader loss, stated as one. |
| Rollback | Keep one verified previous release for atomic redeployment. No permanent dual-write and no old-code fallback. | Rollback restores a coherent release, never new indexes over old rows. |

**A performance claim reports each cost separately** - cold startup, warm
lookup, changed-input update, correction and deletion, full rebuild, peak memory,
transferred bytes and artefact size - with hardware, date and spread (Guardrail
#10).

**A test proves its own bound by not growing.** Hold code and fixtures fixed, add
unrelated production history, and the selected inputs and the operation counts
must not move.

## Rejected shortcuts

Each row is a fence: the alternative named, and what taking it would cost.

| Shortcut | What it would cost |
| --- | --- |
| Put every date, manifest or key in one JSON file and read it once | Bytes, parse and deserialisation still grow with history. One file is not one unit of work. |
| Replace CSV with one unbounded SQLite blob and call the system constant-time | Indexed queries improve while cold restore, git persistence, file limits and transfer still grow with the whole database. |
| Move the work to a browser worker, a native vector kernel or a parallel job | Latency and responsiveness change. Data-dependent work and transfer do not. |
| Stop vector ranking after K acceptable hits | A later vector can be better, so the result is wrong rather than approximate. Exact bounded selection keeps a heap. |
| Average daily medians to get the window's median | Unequal daily sample counts make that a different statistic. A day-level statistic survives only where it is labelled as one. |
| Sum daily distinct counts, or daily top-source lists | Repeated addresses, and sources crossing a daily rank cutoff, change the window answer. |
| Cap the displayed list and leave the input loading untouched | The DOM shrinks while transfer, memory and preprocessing stay unbounded. |
| Cache by date, path, schema stamp or mtime | Same-date publication, correction, deletion and a changed knob each reuse a stale result. |
| Remove a consistency or migration check before its purpose is gone | Cached browsers and in-flight jobs do not upgrade when repository files are rewritten. Ownership and a verified conversion retire the check; intent does not. |
| Replace every archive test with the small canary day | Large-day, competitor-population and live-audit coverage go with it unless each is deliberately preserved elsewhere. |
| Treat a calendar window or a fixed pixel width as a data-size bound | Neither bounds rows, bytes, runs per day, distinct values or mounted nodes. |
| Promise no full-tree work anywhere while keeping cold builds and Pages uploads | A complete artefact must still be generated, read and uploaded. That is an output-size floor, not debt. |

## See also

- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #12, which this page serves, Guardrail #10 on what a measurement owes, and section 6 on correction levels.
- [../concepts/growing-reads.md](../concepts/growing-reads.md) - the reader's side: the cover a growing read declares, and the reads that still grow.
- [../concepts/partitions.md](../concepts/partitions.md) - the writer's side: what a partitioned layout obliges, and the freeze rule.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window) - why a ledger partitions at all, and which reads carry a window.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the persisted and served outputs these rules apply to.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - focused local selection, and the CI verification that is authoritative.
