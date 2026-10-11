# Host telemetry through serialized events

**Last Updated**: 2026-10-10

## What is implemented

The isolated contracts, native Rust producers/storage and read-only verifier do
not change production collectors or shared ledger readers. Rust now collects,
renders and atomically files real probe, target and clock host records.
Resource windows and production invocation are not implemented at this increment.
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

## Probe, target and clock collection

The thin native CLI routes `probe`, `target` and `clock` commands. `invocation.rs`
binds a validated manifest and command to finite named inputs, an isolated output
root and retained native results. `job_probe`, `target_probe` and `job_clock`
produce whole rows through the existing store and receipt modules; they do not
import codecs or mint file paths/envelopes.

Probe inputs read bounded proc/sysfs topology, logical CPU IDs, policy frequency,
selected-process affinity, cgroup constraints, cache and uptime. Physical topology
and target allowance remain separate. Observed MHz is a validated complete mean;
reported hardware maximum is independently covered. Missing or raced sources
yield null with a typed reason. One early unknown target can be enriched by a
labelled whole-row capture; clock collection never remeasures CPU facts.

`hierarchy.rs` proves cgroup ancestry with actual kernel filesystem evidence.
Matching fd-derived namespace/root identities establish source alignment, not
host-initial identity. A pinned genuine cgroup2 root has `cgroup.procs` and an
exact ENOENT lookup for `cgroup.events`; non-root groups have that marker even in
a remounted cgroup namespace. A genuine v1 root positively exposes `release_agent`
metadata; nothing executes or changes it. Mount/device evidence rejects covering
substitutions. Unproved roots, denied reads or changed context leave quota
unavailable even if a visible quota is finite. Bounded `cgroup.subtree_control`
evidence establishes controller applicability rather than guessing from absence.
Valid v2 partitions use the target effective cpuset, not intersections with
parent effective sets; v1 inheritance retains its separate rules.

Live and recorded captures pass the same reducers and brackets. Recorded hierarchy
evidence is explicit; ordinary generated files cannot masquerade as kernel proof.
The hardware-only algorithm-2 hash excludes quota, affinity, online topology,
frequency and microcode. Fixed link-local metadata uses the minimal HTTP-only
`ureq` client; copy bandwidth retains fallible allocation, three timed copies and
observable results. Copy selection remains independent of memory collection.

Before publishing raw bytes, the CLI retains the intended result, its diagnostics
and exact write plan. An interrupted retry consumes this intent without recapture,
synthetic timestamps or extra files. Only actual completed-file evidence permits
publishing the result. Native tests interrupt real CLI processes at five stages in
JSON and all three Parquet compression settings, then verify the same bytes.

The named `probe-clock.json` fixture supplies independent corrected CPU/hash truth.
Python compares unchanged identity, cache, uptime and clocks against its unchanged
instruments and verifies native files without re-encoding. Locked dependencies add
six packages, 410,532 cached archive bytes and no prior version changes. The whole
MSVC development executable measured 25,457,664 bytes; this is neither a dependency
size delta nor a Linux release-cost claim. Actual Linux cost remains experiment
evidence, not a conclusion from fixture equality.

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

## Completed-file evidence and recovery

`receipts.rs` retains the immutable event plan before the first raw publication.
After each completed file it writes an immutable cumulative snapshot named
`<event>.completed-<count>.json`. The existing publication receipt shape keeps
the wrapper invocation distinct from the raw row's logical producer.

Recovery reads only that retained plan, its planned files and at most one
receipt name per planned file. It checks actual native bytes, metadata and rows.
A lost later receipt cannot erase an earlier completion. An existing complete
planned file with no receipt is recoverable; a promised missing file, foreign
identity, changed bytes or a later snapshot that drops earlier writes is refused.
Evidence roots cannot alias the target, reserved state/raw roots or escaping
symlinks/junctions.

Recovery may write missing evidence snapshots, but does not publish target files.
An explicit retry files only the same immutable plan. The Python verifier is
read-only. It rejects a receipt that omits an already completed planned file,
including publication between two receipt snapshots. Its `--receipt-only`
output is the validated existing `PublicationReceipt` shape; downstream
publisher permissions remain independent.

The real `receipts-fixture` process exits at named filesystem checkpoints.
Native and Python tests restart it across plan, publication and receipt stages.
Generated-repository tests run existing publisher scope, changed-byte and Git
filter checks against those same native files, without staging or pushing them
in this repository.

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

Production cutover and historical replacement are authorized for unattended
delivery after their evidence/readiness gates. Contracts and green tests alone
do not establish that evidence or permit skipping backups and quiet windows.

## See also

- [Host measurements](../../reference/host-metrics.md)
- [Persistence](../contracts/persistence.md)
- [Run the gates](../../how-to/run-the-gates.md)
