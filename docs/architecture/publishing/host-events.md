# Host telemetry through serialized events

**Last Updated**: 2026-10-11

## What is implemented

The isolated contracts, native Rust producers/storage and read-only verifier do
not change production collectors or shared ledger readers. Rust now collects,
renders and atomically files real probe, target and clock host records.
The isolated resource monitor now returns item-window cells and exports legacy
job-memory and runtime server-status artifacts. Production invocation remains
unchanged; this is not the single-writer cutover.
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

## Resource windows and memory artifacts

The CLI routes `monitor` to live sampling and `resource-replay` to bounded recorded
captures. `event-send` publishes a validated command; `event-wait` waits for
readiness or the matching acknowledgement/result. A window wait that expires
returns typed incomplete cells, without invoking Python collection. Invalid
messages and foreign process identities remain faults, not successful timeouts.
An uncorrelated `protocol.fault` fails every wait in that session, including
readiness. A correlated fault fails only its selected command. Before returning
a matching success, the client validates the bounded list of already-visible
results; UUID filename order cannot hide a session-wide fault. Exhausted scan
budgets fail explicitly rather than certifying an unchecked success.
`monitor-cleanup` uses Linux process start ticks and a pinned process descriptor
to signal only the operator's monitor, with a bounded termination grace.

The process sampler brackets readings with PID/start-tick identity. Window worker
memory belongs to the registered Python worker, never the Rust monitor. Job
memory remains all readable `python*` processes; it is neither that worker alone
nor a workload-subtree sum. Exited targets have unavailable readings; a reused
closing PID is an explicit identity fault, including when memory is off.

Each active window holds its opening snapshot, previous CPU counters and running
minima/maxima. CPU mean remains the whole-window counter difference, not a mean of
sample percentages. Decimal rounding matches Python's binary-float rounding.
CPU extrema include periodic differences and the whole-window mean. Available
memory minima include both endpoints; server HWM uses only the two endpoints.
Major faults use the endpoint counter difference, with null on reset. Zero
resource interval selects endpoints only. Overlapping windows keep independent
snapshots and monotonic deadlines; missed wakes do not invent samples.

Job samples retain the configured legacy cadence. Runtime status retains its
separate one-second cadence. Job sampling ends when its selected process exits;
window CPU/load results and explicit unavailable memory evidence continue.
Rust streams plain `rss-samples.jsonl` and
`python-procs.jsonl`, with the unchanged kilobyte keys and at most three argv
fields. `server-rss-samples.jsonl` keeps the legacy `VmRSS`/`VmHWM` string mapping;
`cgroup-memory-peak.txt` retains the final available peak. Events wrap typed
sample/rollcall bodies; legacy files have no envelope fields. Existing Python
summary readers can consume those files directly.

Memory off performs no status, meminfo, memory-cgroup or Python-population reads,
does not extract major faults from stat, and creates no memory artifacts. CPU,
load, identity, window heartbeat and lifecycle continue. Completed windows retain
valid CPU/load cells and disabled memory diagnostics, rather than an incomplete
whole window.

The event history has finite total and retained budgets. Consumed command/reply
pairs retire only after their refreshed retry window; retired IDs retain bounded
conflict evidence. Failed reads also consume their reserved byte allowance.
Ordinary traffic and new consumption files reserve room for failure and complete
shutdown. Consumption duplicates count toward physical files and stored bytes,
not as new logical events. A refused consumption write is explicit backpressure;
it does not mark the message consumed. Exact retries preserve immutable bytes.
Normal closes retain room for a future fault, stop and stopped event, plus each
remaining open window. Startup and window admission also check that shutdown
payloads fit the result-size cap.
Only a bounded batch with every listed incomplete window and `monitor.stopped`
can spend the final drain reservation. The monitor checks the entire batch's
capacity and immutable destinations before publication, then commits its stopped
state only after every file was published. This is not filesystem batch atomicity:
an I/O failure remains explicit and can leave an immutable completed prefix.
A live protocol fault stops the monitor after explicit incomplete results.
Cancellation flushes incomplete windows and `monitor.stopped`, correlated to the
session's readiness event when no stop command exists; atomic completed results
survive. Kernel termination that cannot run cleanup remains the
operator's diagnosed-unavailable path, not fabricated completion.

The named resource fixture compares the same captures, process population,
windows and artifact records against unchanged Python readers. Generated proc
trees also drive the real monitor subprocess with memory on and off. Linux-only
tests cover real task exit, pinned-PID cleanup and signal cancellation; Windows
fixture success does not claim those Linux tests passed. Live scheduler and IPC
cost still require the artifact-only experiment.

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

## Bounded historical inventory and dry-run

`utilities.migrate_host_fingerprints` now prepares real replacement candidates
without writing historical files. It is a maintenance codec, not a CPU collector.
The unchanged Python collectors and production readers remain unchanged.

Supply a `HistoryManifest` from `idhazh.contracts.host_migration`. Its schema is
available through `HistoryManifest.json_schema()`. The manifest requires:

- `version: "2026-10-11"`, a UTC `converted_at`, and the maintenance `invocation`
  with producer `utilities.migrate_host_fingerprints` and the converting git SHA.
- Inclusive `range_start` and `range_end`, both before the conversion day.
- A finite `roots` list. Each root names its `state_root`, production or trial
  `kind`, and tier-first host `prefix`. Production uses `["host-fingerprint"]`;
  a trial adds its explicitly named segments before that final segment.
- `closed_periods`, naming each root, exact `covers` and `daily`, `monthly` or
  `yearly` grain. Every indexed entry, including empty and lost periods, must be
  included. A complete month or year must fit inside the operator's range.
- `sources`, naming every selected physical `path`, root, kind, exact original
  SHA-256 and byte count. Raw, compact, raw-index and set-aside sources name
  their closed period. Compact files, indexes, views and receipts declare their
  exact source-path `dependencies`; raw files have no dependencies.
- An `isolated_root` under `backend/var/`, outside all historical state roots.

Source kinds are `raw`, `compact`, `raw_index`, `compact_index`, `view`, `receipt`
and `set_aside`. The tool never discovers files recursively. An operator pins a
named source list, including every selected probe, clock and superseded attempt,
before running it. Unlisted later files require a fresh manifest. Completeness
means this exact manifest was reconciled, not that all history was discovered.

From `backend/`, with the repository's Python development environment:

```powershell
python -m utilities.migrate_host_fingerprints `
  --workspace-root (Resolve-Path ..).Path `
  --manifest backend/var/history-manifest.json
```

The command defaults to dry-run. `--apply` fails explicitly: application is not
implemented here. The manifest and all source paths resolve under the supplied
workspace; persisted paths remain relative and POSIX-separated.

The command reads exactly two repository-owned configuration files, resolved
from the utility's location, not the operator's workspace or environment.
`history_migration_limits` in `config/host-history-migration.json` caps roots,
closed periods, manifest bytes and the complete bundle. It contains no copied
verification defaults. `verification_limits` in
`config/host-telemetry-experiment.json` caps files, individual and aggregate source
bytes, rows, footer/decode bytes, JSON depth and Thrift items. Every source read
is bounded and hash-checked.
`HistoryLimits` validates the combined effective inputs before reading history.
Missing files or invalid bounds refuse the dry-run without source or config
writes. The shared experiment file retains only native settings; Rust still
rejects unknown sections and does not read the migration-only file.
The full batch and existing retry targets validate before any bundle is created.
Physical root and file identities reject case aliases and repeated hard-linked
sources or destinations. Existing ancestors also establish separation when the
isolated directory does not yet exist. Original path labels are not rewritten;
distinct case-sensitive roots stay distinct. Symlinks and junctions are refused.
Missing destination names follow the existing parent's case rules. On Windows,
those rules come from read-only directory attributes, not universal lowercasing.
Missing or unreadable sources, hash drift, unknown/mixed schemas, unsafe paths,
receipt disagreement and incomplete compact/index dependencies fail by name.
Present set-aside files receive `unresolved`, never a successful skipped-file
diagnosis. Lost periods remain lost; empty periods remain empty.
An index loss day that also has compact rows is a contradiction, not a marker
to repair. Loss, expiry and set-aside markers remain exact, including periods
with only unread files set aside and no surviving rows.

JSONL and bounded flat historical Parquet use the existing maintenance codecs.
Parquet admits actual V1 page bodies and finite dictionaries before Arrow decodes
rows; none, Snappy and Zstd retain their actual compression. Unsupported page
profiles fail, rather than weakening decode bounds. No new Rust output is
re-encoded: already corrected files are explicitly excluded from replacement.
Footer row counts must equal the bounded row-group sum before page decoding,
and the actual decoded row count afterward. Contradictions refuse the entire
source batch without a bundle or historical writes.

Each legacy candidate preserves its path, UUID5 work unit, UUID8 file identity,
allocation clock, attempts and original producer/git lineage. The canonical row
digest is checked before the shared legacy normalizer runs. Historical hashes
retain algorithm 1 only when present; legitimate positive observed averages
survive. The exact discarded old counts/frequencies and every null field are
reported. Old counts and maximum frequencies never become corrected readings.
Both original and normalized unions pass the existing whole-row settlement
function; keys, winners, attempts and cardinality must agree.
When compact input dependencies are declared, they must cover the complete
original `built_from` count and settle to the same rows, including discarded
legacy CPU values. Partial or contradictory input claims fail. Compact-only
history instead records no surviving inputs and retains its original count;
that does not claim recovery or independent proof of retired source bytes.

The immutable bundle lives at `<isolated_root>/<scope_hash>/<evidence_hash>/`.
It contains the manifest, report, verified raw/compact/index candidate bytes and
retained original receipts. The report records original/replacement envelopes,
physical and canonical hashes, identities/keys, nulls, averages, index changes,
source dependencies and estimated read/candidate bytes. `scope_hash` binds the
entire operator manifest. `evidence_hash` binds the validated report and limits;
the derived bundle path and the hash itself are excluded from that preimage.
Exact partial retries reuse bytes. Different bytes at a candidate path fail.
The report is published last. New evidence generations do not overwrite old ones.
This is per-file atomic visibility, not a multi-file or power-loss guarantee.
The read estimate counts the two source passes; manifest/retry-target reads and
bundle verification are additional I/O. The candidate estimate includes the
manifest and candidate receipt but excludes the final report; the enforced
bundle byte cap includes every artifact, including that report.

`candidate-maintenance-receipt.json` gives the replacement target paths and
candidate physical hashes under the maintenance invocation. It is a planned
receipt shape, not proof that historical paths already hold those bytes.
Old invocation receipts remain historical evidence. No source is retired;
future application must verify original-byte backups and a writer/compactor/
publisher quiet window before replacing any source.

The initial reader mode is `candidate_reader`. Raw, compact and index candidates
can be `candidate_complete`. Actual published `machine/<YYYY-MM>.csv` and
`console/band.json` sources are validated through their existing contracts, but
their replacements and associated receipts are explicitly `deferred`. There are
no fabricated future-consumer calls or copied views described as rebuilt.
`historical_readiness` remains `blocked`, even for a complete fixture inventory.
After shared schemas and consumers migrate, the same closed manifest must run
against those actual consumers, freeze view/receipt bytes in a new evidence
generation, and satisfy the historical evidence gate before application.

The artifact-only workflow can run these bounded, generated-file tests before
its verdict; no test scans committed archives or installs tools:

```powershell
python -m pytest -n 0 tests/contracts/test_host_migration.py `
  tests/test_host_fingerprint_migration.py
```

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

Fowler ruled on 2026-10-11 that the initial historical fixture dry-run must not
pull future consumer migration forward or invent its output. Explicit deferred
view and receipt statuses retain that dependency while real file and index
candidates complete now. The later migrated-consumer rerun costs one bounded
reconciliation pass and is required before historical readiness, not a new
permission request. The page stays whole: these controls govern the same
host-event output and evidence boundary, not a separate maintenance subsystem.

## See also

- [Host measurements](../../reference/host-metrics.md)
- [Persistence](../contracts/persistence.md)
- [Run the gates](../../how-to/run-the-gates.md)
