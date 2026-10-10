# Host telemetry through serialized events

**Last Updated**: 2026-10-10

## What is implemented

The isolated contracts, native Rust storage and read-only verifier do not change
production collectors or shared ledger readers. Rust now renders and atomically
files real host records. Host collection is not implemented at this increment.
The corrected host row removes the legacy CPU count and frequency columns.
The candidate reads finite historical schemas without inventing measurements:
old hashes retain algorithm 1, legitimate observed averages survive, and
unmeasured corrected counts stay null.

## Process boundary

`host_events.py` declares session manifests, process identities, source coverage,
window cells, legacy memory artifact records and lifecycle messages. Every event
has a schema date, session, emitter sequence and operator-owned identity.
`host_output.py` declares immutable host write plans and completions. A completion
carries the existing publication receipt shape; it is evidence, not permission.

`host_event_files.py` reads and publishes only named files under one bounded
session root. Commands and responses are immutable. Identical retries reuse
their evidence. Conflicting IDs, out-of-order commands and foreign targets fail.
Completed messages retire only after consumption and their configured retry
window. Active windows, pending events, total events, bytes and reads are bounded.
Abort and shutdown resolve opening commands without silently dropping evidence.

Memory collection defaults on. The manifest carries one strict Boolean; disabled
memory cells are null and diagnosed separately from CPU and load readings.
This candidate control does not yet turn off production Python instruments.

## Exact-byte verification

`host_output_verify.py` verifies named JSONL or Parquet files without rewriting
them. It checks the original canonical row hash before legacy normalization.
It also checks the entire physical file hash, row identities, work-unit UUID5,
clock-derived UUID8, immutable planned paths, and invocation identity.
The logical producer remains `telemetry.silicon`; a native codec name is not a
different producer.

The finite native pairs are `idhazh_rust.ledger.parquet` with Parquet and
`idhazh_rust.ledger.json_lines` with JSONL. Native output is accepted only for
corrected raw host records. The envelope retains its existing key set.
Parquet's `created_by` must name its actual engine/version. A Python-rendered
Parquet file with a renamed native writer is refused.

`host_parquet_admission.py` checks actual page bodies before Arrow decodes rows.
The admitted raw-host profile has one row and flat string/int64/float64 columns.
PLAIN and the writers' PLAIN-dictionary/RLE-dictionary encodings are supported;
dictionary cardinality and page counts are bounded. None, raw Snappy and Zstd
must match actual bounded decoded sizes. Footer claims do not establish bounds.
The decode-byte cap bounds payload, not process RSS or all allocator overhead.

The native crate separates contracts, configuration, canonical JSON, logical
schema and in-memory codecs. Only the Parquet codec imports native Arrow/Parquet
types. Both codecs use the explicit corrected 40-column host/identity schema.
Parquet uses one-row V1 groups, PLAIN encoding, statistics and no dictionary or
auxiliary indexes. None, Snappy and Zstd pass the same candidate verifier on the
actual Rust bytes. JSONL uses `.json`, envelope-first ASCII rows and LF.

The Rust test harness and `codec-fixture` executable generate named files under
`backend/var/`; Python reads those same files and their physical receipts. The
fixture executable serves these cross-language tests, not production collection.
Missing native binaries or harness evidence fail rather than skip.

## Raw-file storage

`ledger/store.rs` prepares every day group through the real codecs before the
first target write. It accepts one corrected whole host row per day, keeps the
row's ranked identity, and rejects a conflicting day or invocation. Empty
batches and paused or retired raw families write nothing, including maintenance
jobs. Nested trial prefixes change only the outer path.

The store exposes its immutable plan before publication. The plan names each
file, actual write clock and expected canonical hash. A changed probe, target
or clock event uses the successor predicate and a strictly later actual
millisecond. The clock helper waits only within its caller's deadline; it never
invents a timestamp. Identical retries retain the original plan.

`fs/atomic.rs` stages bytes beside the destination. Basic replacement uses a
rename. Immutable raw publication uses a no-clobber hard link from the staged
file, then removes only its own temporary file. This keeps concurrent writers
from replacing a conflicting UUID filename. Unsupported hard links fail.
Identical complete bytes are an idempotent retry.

Paths validate the raw day grammar and reject traversal, reserved device names,
escaping symlinks and Windows junctions. A leaf file cannot be a symlink.
Containment assumes operator-controlled directories; it does not promise safety
against hostile concurrent directory swaps or power-loss durability.

Publication is atomic per file, not per batch. A later I/O error reports the
earlier completed files and their actual whole-byte hashes. The native
`storage-fixture` and Cargo harness file multiple days in all four codec settings;
Python independently verifies those exact bytes, without re-encoding.

Rust 1.95.0 and all dependencies are pinned/locked. On Windows, a clean cached
offline all-target development build took 152.040 seconds; the development
fixture executable was 23,662,080 bytes. These are not Linux production costs
or release-size measurements. The 102 locked registry packages occupied
10,176,946 cached archive bytes. Arrow/Parquet serve native files; serde serves
closed exchange contracts; SHA-256 and Ryu serve canonical identity bytes.

## Configuration and verification command

`config/host-telemetry-experiment.json` supplies collection, capture, exchange
and verification limits. It declares no production state root. Callers validate
its sections with `CollectionControls`, `HostEventLimits`, `HostCaptureLimits`
and `VerificationLimits`. Session manifests supply finite named inputs/outputs,
workers and windows. Tunable intervals and byte limits are not source constants.

`backend/utilities/verify_host_output.py` accepts a workspace root, independently
expected target root/invocation, named plan/completion files and explicit
verification limits. It returns verified physical hashes and completeness,
or a named refusal. It neither collects nor publishes.

## Design rationale

Fowler ruled that disjoint modules can be written in parallel after their tested
prerequisite contracts. The owner integrates one whole row before main merges;
dependent leaf branches are not independent release units.

Fowler approved sharing compilation of the nine fixed native contract
expressions when repeated receipt validation made local recovery checks costly.
Each expression has one standard-library initialization slot. Unknown expressions
remain uncached. The predicates, error results and every validation call remain;
the registry cannot grow from input. Original-result and concurrent-reuse tests
hold this structural change separately from receipt behaviour.

A forged compressed-string fixture exposed allocation before an old
post-decode check. Bounded actual-page admission fixes that boundary. Apache
Thrift supplies compact-protocol primitives and cramjam supplies bounded raw
Snappy decoding; shared Python ledger codecs remain unchanged.

Production cutover and historical replacement require the later explicit
evidence-based decisions. Contracts and green tests cannot grant either.

## See also

- [Host measurements](../../reference/host-metrics.md)
- [Persistence](../contracts/persistence.md)
- [Run the gates](../../how-to/run-the-gates.md)
