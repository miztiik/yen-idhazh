# Host telemetry through serialized events

**Last Updated**: 2026-10-13

## Current ownership

Rust is the sole host CPU/memory collector and raw host-file writer for measured
pipeline jobs. Python sends structured events, writes the complete item-health
census, verifies native receipts, and owns shared readers, compaction and publishing.
Digest plan/work/assemble, bench and encoder probes, gardener task shards and
council result saving use the workflow-owned Rust lifecycle.

The Python collectors, shadow comparison path, exposed implementation selector
and automatic fallback are removed. An invocation without a bound native session
is uninstrumented: host cells are unavailable, never fabricated zeroes or Python
readings. Item work, its health record and the waiting heartbeat continue. A
selected native session with missing inputs or failed output fails explicitly;
it cannot degrade into a different collector.

The logical producer name `telemetry.silicon` is a stable persisted identity, not
a module to execute. Removing the old Python module does not rename historical
work units. Finite legacy readers remain: old fingerprints keep algorithm 1,
legitimate observed averages survive, and unmeasured corrected counts stay null.

## Process boundary

`host_events.py` declares dated session manifests, process identities, source
coverage, window cells and lifecycle messages. `host_output.py` declares immutable
write plans and completions. A completion carries a publication receipt; it is
evidence, not permission.

`host_event_files.py` reads and publishes named files under one bounded session
root. Commands and responses are immutable. Identical retries reuse evidence;
conflicting IDs, out-of-order commands and foreign targets fail. Consumed messages
retire only after their configured retry window. Active windows, pending events,
total events, bytes and reads remain bounded. Abort/shutdown preserve evidence.

Memory defaults on. `observability.memory_profiling_enabled` is the shared setting;
`--memory-profiling on|off` is the process override. Measured workflow dispatches
accept `inherit`, `on` or `off`. The effective Boolean is written into the named
native config and manifest before collection. Off performs no process-status,
machine-memory, memory-cgroup or Python-population reads and creates no memory
artifacts. CPU, load, identity, timing, lifecycle and heartbeat stay active.
The memory-bandwidth copy retains its separate controls.

## Native production boundaries

The workflow builds the pinned crate and starts `d7_host_telemetry.py`. The wrapper
owns the producer, monitor and cancellation boundary; readiness precedes events.
The command router and `job_machine.record` consume only the bound native session.
Returned host paths come from physically verified write plans/completions and are
added to each producer's existing exact publication receipt, never a state-tree
scan. A failed native producer cannot select a Python writer.

Rust window results supply item-health host cells. Success, scoring, work failure
and cancellation use the same close boundary. Duplicate closes reuse the first
result. YAML owns process lifetime; the complete item-health writer stays Python.
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

`config/host-telemetry-experiment.json` supplies native collection, capture, exchange
and verification limits. It declares no production state root. Callers validate
its sections with `CollectionControls`, `HostEventLimits`, `HostCaptureLimits`
and `VerificationLimits`. Session manifests supply finite named inputs/outputs,
workers and windows. Tunable intervals and byte limits are not source constants.
`config/host-telemetry-lifecycle.json` retains only the live command deadline and
output-byte cap. These are unchanged runtime bounds, not comparison calibration.
The shared default is `observability.memory_profiling_enabled` in
`config/idhazh.json`; native scratch config carries its already resolved value.

`backend/utilities/verify_host_output.py` accepts a workspace root, independently
expected target root/invocation, named plan/completion files and explicit
verification limits. It returns verified physical hashes and completeness,
or a named refusal. It neither collects nor publishes.

## Reply retention and cancellation

The latest consumed host reply group remains available while a job runs, even
after its ordinary retry window expires. A valid successor or session stop
releases that protection; failed admission does not discard the predecessor.
The limit and consumed-only retirement rules do not change. Producer cancellation
unwinds owned-process cleanup, and a producer termination failure cannot bypass
native monitor cleanup. Council controls use its selected `--config-root`.
No shadow session or competing Python probe/clock writer remains.

## Functionality evidence

The one-time artifact-only comparison workflow and its Python reference collectors
are retired after accepted Ubuntu all-family/control/publication evidence.
Normal CI still builds the pinned Rust crate and runs its module tests,
cross-language codec/read fixtures and real process-lifecycle regressions.
Those tests exercise functionality over bounded generated or recorded inputs;
they do not validate the changing production archive on every pull request.

CPU/hash corrections use independently known fixture results, not equality to
retired Python CPU semantics. Python and Rust encoded files are verified under
their truthful engine/container provenance, never relabelled to claim native bytes.

## Completed historical maintenance and recovery

The approved one-time Python conversion completed on 2026-10-13: 308 manifested
files, 815 settled host records, 587 work records and an unchanged dashboard.
The conversion preserved original allocation clocks, settlement winner/key/attempt,
v1 fingerprint labels, legitimate frequency averages and truthful container
provenance. Installed readers and the dashboard publisher reconciled the exact
approved bounded inputs. This was Parquet-to-Parquet maintenance, not Python
host collection or a Git-history rewrite.

The one-time inventory/dry-run/apply machinery, migration-only configuration and
its tests are removed from active main. Shared codecs, finite versioned readers,
physical/page/footer validation and normal generated functionality tests remain.
Archive manifests, row counts and report hashes stay out of recurring pytest.

Verified original bytes, the immutable dated plan/events, exact approval/report
and maintenance receipt remain in the task-owned ignored transaction directory.
An independently verified copy is retained outside the target checkout.
The completed transaction is
`be1c177b5cac6b28f6b6f09fb57b8dac593acb188552c9353768d7ac227caf98`.
Do not delete these recovery artifacts as source-code cleanup.

If recovery is needed, use the preserved maintenance worktree or frozen revision
`d156864a5bce5df2a44eff972bce8f740023f48a`, not the current application code.
Its `utilities.migrate_host_fingerprints` command takes the original manifest,
validated D16 bundle, original dated approval and explicit target checkout.
Use the same inputs with `--apply --rollback` to restore verified originals.
Keep the local checkout offline for the entire recovery window. The old/new
byte checks refuse a third state; never replace a foreign Git lock or reclaim
ownership merely because a lock is old. Physical target identity and unchanged
Git state remain part of that frozen recovery procedure.

Each replacement is atomic; the batch is not a multi-file filesystem transaction
or a power-loss durability claim. Moving repository commits do not invalidate
the historical report: its hashes bind approved file/evidence bytes, not a demand
that main stop changing.

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

Fowler ruled that starting the resource monitor cannot restart one emitter's
ordering inside a session already used by a standalone probe. The monitor's
empty history is not an ordering exception. Separate host and resource sessions
preserve H1/H9 without filtering evidence, fabricating populations or editing
the native collector; the host probe-to-clock raw/receipt chain stays intact.

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
