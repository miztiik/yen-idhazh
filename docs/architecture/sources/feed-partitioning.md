# How selected articles receive worker assignments

**Last Updated**: 2026-10-21

How does the isolated feed planner allocate exactly the articles that editorial
curation selected, without fetching content again or changing its ratings?

## Current-run construction

`readCurrentSelections` receives the actual result of `curateArticles`, the
selection result of `persistPortfolio`, the original harvested candidates and
the current writer and planning context. It reads the named selection Parquet
files from the caller's output root. Their digests, rows, identities and counts
must agree with the write result and the current curation rows. Empty curation
has an explicit empty write result and requires no file.

The adapter checks that curation retained each selected original candidate.
`preparePartitionInput` joins those candidates to selections by candidate
identity. It refuses missing or repeated content, repeated ranks, a different
run or correlation, and differences in the dispatch contract's shared fields.
It never creates a title or article text from a selection row. Initial
construction does not require dispatch or source-run completion records:
those records do not exist yet.

Capture one UTC clock and pass the same requested freshness override to
harvesting and screening. Existing records whose selection day or effective
policy differs from the original candidate remain a named validation failure.
The partitioner does not alter either record to satisfy the dispatch schema.
The independent-input limitation is described in
[feed-curation.md](feed-curation.md).

## Allocation and persistence

`resolvePartitionRequest` validates `config/feed-ingest-plan.json`'s partition
settings and optional strategy and shard count. A runner calls it before
harvesting. Non-`none` counts must fall within the configured minimum and
maximum; an omitted count uses the configured default. Strategy `none`
accepts an omitted count or explicit one, always uses one worker and refuses
an explicit larger count even if it is otherwise within the configured bounds.

`partitionArticles` keeps output in editorial-rank order. `bin-pack` visits
articles in decreasing recorded `estimated_work`, then editorial rank, then
candidate identity, and assigns each to the least-loaded worker. Equal worker
loads use the lowest worker number. Curation supplies the estimated word work;
partitioning does not rescore it. `round-robin` assigns successive editorial
ranks to successive workers. `none` assigns every article to worker zero.
Empty workers remain present in the returned work totals.

Each dispatch retains the exact selection, rank and original candidate.
Its nested `PartitionAssignment` records the strategy, worker number and
effective worker count. `persistDispatches` uses the public ledger writer and
registered Parquet settings. Worker assignment never changes the writer's
provenance shard. A paused ledger is an explicit error, not a successful empty
write.

## Named history and proof

`readLedgerDay` consumes one named UTC day, explicitly supplied compact index
paths, and either an explicit list of raw files or one named raw-day index.
It performs no directory walk, repository scan or network fetch. A supplied
empty raw-file list is an explicit statement by the caller that its bounded
input is empty; absence of a raw input is missing history, not an empty day.
Callers that cannot establish a complete list must report unavailable history.

For the requested day, yearly entries take precedence over monthly entries,
then daily entries, then raw files. Overlapping compact periods produce a
notice and only the coarser file is read. A packed file must agree with its
index's byte size and row count. Empty and lost entries do not fall through
to leftover raw files. A file beside an entry that declares no file is refused.
A missing packed file, an expired year, and a lost day remain distinct from a
known empty day. Missing named indexes and files produce explicit notices;
invalid indexes or files raise errors rather than becoming empty history.

`readLedgerParquet` uses native Parquet/WASM and Arrow. It validates the
declared physical column types, envelope, file and unit identifiers, canonical
ordered-row digest, contract rows and original row identities. Compact files
keep each original run, attempt and unit; the compactor's identity is only in
the envelope. Neither reader settles away older attempts.

`selectCompleteAttempt` requires source outcomes for the expected source count
and checks each required ledger commitment against its verified original raw
file, including digest and count. Within a run, a newer incomplete retry does
not displace a proven older attempt. An explicitly completed zero-selection
attempt is valid evidence, not a missing selection file. Historical full text
comes from that attempt's recorded dispatches. `readHistoricalSelections`
checks their exact selection identity and rank correspondence before preparing
the original content for allocation.

**Packed history cannot generally prove an original raw-file commitment.**
Compact rows lack the original raw-file membership and row order, and packing
can remove duplicate occurrences. A compact file's own verified digest and
aggregate counts do not repair that loss. The attempt result is explicitly
`unverifiable` when referenced original files are unavailable, never verified
replay. If original files were retained, the caller can supply that named raw
evidence independently. Completing packed replay needs an owner-approved
persisted-contract decision; this implementation changes no stored meaning.

## Design rationale

Editorial choice and worker allocation answer different questions. Keeping the
selected identities and scores fixed makes a strategy change affect only
allocation, not coverage. Greedy packing estimates work; it does not prove
optimal balance or equal worker elapsed times.

Current construction and historical replay use different evidence because
requiring future completion records would prevent creating the first dispatch.
Historical proof remains strict because trusting recorded hashes without
reproducing them would make incomplete history look complete.

The bounded tests use real current curation, native raw and compact writes,
hand-computable work totals and recorded index contract fields. All new checks
are TypeScript-only, with no network or backend process. Native readback is
not a claim that the current Python reader was executed.

## See also

- [Feed curation](feed-curation.md)
- [Ledger persistence](../contracts/persistence.md)
- [Ledger compaction](../publishing/ledger-compaction.md)
- [Running the gates](../../how-to/run-the-gates.md)
