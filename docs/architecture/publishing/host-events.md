# Host telemetry through serialized events

**Last Updated**: 2026-10-13

How the Rust host-fingerprint instrument collects, stores and hands measurements
to the Python pipeline, and what that boundary costs. Field meanings and the
operator's controls are defined in [Host measurements](../../reference/host-metrics.md).

## What is implemented

Rust is the default host collector and sole raw host writer on the selected native
paths in content refresh, measurements, encoder scoring, gardener task shards and
council result saving. It collects probe/target/clock facts and item-window
CPU/load/memory results. Python still writes the complete item-health census,
verifies native files/receipts, and owns shared ledger readers, compaction and
publication. This is not a port of the complete application to Rust.

The explicit `legacy` choice retains Python collection; `off` disables both
collectors. Cleanup and removal of rollback have not happened. The optional
shadow comparison boundary also remains, but is not the production default.
Native failure never automatically selects legacy collection.

Shared readers admit the native writer's real container provenance and normalize
declared legacy rows without Python re-encoding. The corrected schema separates
hardware topology, target allowance and observed/reported frequency. Historical
hashes retain algorithm 1, legitimate averages survive, and unmeasured corrected
facts remain null. The approved historical rewrite is complete for its bounded
scope; its backup/recovery tooling remains separate from live collection.

## Capabilities and trade-offs

Table A - engineering boundaries

| ID | Choice or capability | Benefit | Cost or limit |
| --- | --- | --- | --- |
| A1 | Separate Rust processes and structured file events | No Python/Rust in-process bindings; explicit versioned inputs and results | Process startup, event serialization, bounded waits and cleanup still cost time. Rust does not imply a measured speedup. |
| A2 | Validated Linux sources and declared process targets | Distinguish machine topology from the model/worker's allowed CPU capacity; reject reused process IDs | Live collection requires Linux `/proc` and `/sys`. Restricted, raced or incomplete source reads remain unavailable. |
| A3 | Versioned hardware fingerprint | Stable grouping without treating changing quota, affinity or frequency as new hardware | The hash is not a unique machine ID. Algorithm-1 and algorithm-2 values must not be grouped as one generation. |
| A4 | Whole-window host counters and periodic extrema | Preserve CPU/load observations beside item work, including with memory off | Host-wide busy/load is not CPU attribution to one model. Sampling can miss events between reads. |
| A5 | OS memory and major page-fault counters | Observe RSS, available memory, swap and storage-backed page misses | No allocator/stack/per-region profiling; high-water marks are process-lifetime observations, and samples are not exact item-local peaks. |
| A6 | Optional cache-sized copy benchmark | Record the actual buffer and a memory-copy rate under explicit job selection | Two allocated buffers and timed copies consume RAM/bandwidth. The memory-observation switch does not disable this separate benchmark. |
| A7 | Immutable native raw files and independently verified receipts | One writer per invocation; retry/recovery keep the original native bytes | Atomic visibility is per file, not a batch or power-loss guarantee. Corruption, foreign identity or exceeded budgets refuse publication. |
| A8 | Build once in the digest plan job | Work shards and assemble reuse one checked executable instead of compiling it again | Artifact upload/download and checksum verification remain. A source/platform mismatch fails, not a rebuild. Other measured workflows still build in their instrumented jobs. |
| A9 | Independent whole-instrument and memory controls | Disable all host collection without losing real work, health records or progress logs; or keep CPU/load while disabling memory | Disabled readings are unavailable, not zero. Memory-dependent decisions lose evidence; existing history is not erased. |
| A10 | Explicit retained Python rollback | A run can select legacy without reverting the new readers or historical conversion | It retains two implementations and their maintenance cost. Legacy CPU semantics are not corrected Rust semantics; no silent fallback is permitted. |

The system does not promise sustained CPU frequency, instruction/cache-hit
profiling, historical recovery of facts never measured, or an overall pipeline
speedup. Functionality and byte/identity evidence establish correctness within
these boundaries; fresh cost measurements are needed for a performance claim.

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

Resolve the [whole-instrument and memory controls](../../reference/host-metrics.md#controls-and-precedence)
before any build, download or collector startup. The effective native memory
Boolean is frozen into the named scratch config and session manifest. Memory-off
results carry null memory cells and disabled reasons while CPU/load remains active.
Whole-instrument off starts no Rust or Python host collector; only the joined
waiting-log timer remains around item work. Ordinary work/publication evidence is
still required, but no native host receipt is consumed. An explicit native receipt
in off mode is refused rather than published.

## Production lifecycle and binary reuse

The workflow owns the Python producer and Rust monitor lifetime. The wrapper
creates the producer behind a gate, records its PID/start-tick identity, prepares
the session, waits for monitor readiness, then releases work. `HostEventClient`
registers only the worker and model server declared in that session. A job with
no declared server stays server-less even if another model server exists.

Python sends probe, optional target enrichment, window and clock commands.
Native window results supply item-health host cells before the record is sealed.
Success, scoring, failed work and cancellation use the same close/abort boundary;
duplicate closes reuse the first result. Native setup, protocol or receipt errors
remain explicit and cannot trigger Python collection.

Publishers consume the verified native file list alongside their ordinary writes.
They independently check the expected invocation, target registry, hashes and
publication permission. A raw host writer receipt is not permission to stage an
unrelated file. Gardener/council collecting jobs do not claim to measure their
separate planner or judging jobs.

For content refresh, `plan` builds the release executable once through
[`d7-host-telemetry`](../../../.github/actions/d7-host-telemetry/action.yml).
The immutable run artifact includes that binary and its SHA-256 checksum.
Work shards and assemble use
[`download-host-telemetry`](../../../.github/actions/download-host-telemetry/action.yml)
to check native-input/platform identity, verify the bytes and restore executable
permission. They neither run Cargo nor prepare a toolchain.

The identity covers crate sources, Cargo manifest/lock, pinned toolchain, runner
OS and architecture; it does not require repository HEAD to remain fixed.
A retried consumer can use its plan's artifact from an earlier attempt of the
same run. Changed native inputs, another run/platform or corrupt bytes refuse
reuse. This is per-run reuse, not a release distribution or a guarantee that
other measured workflows share one build. Whole-instrument off skips the upload
and download as well as compilation.

Legacy runs use the retained Python collector. `host_event_shadow`, default false,
is an isolated comparison path, not production ownership: it keeps Python cells
authoritative and does not publish native shadow roots. Neither selecting legacy
nor disabling instrumentation changes the migrated readers or old data.

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
The shared default is `observability.memory_profiling_enabled` in
`config/idhazh.json`; native scratch config carries its already resolved value.

`backend/utilities/verify_host_output.py` accepts a workspace root, independently
expected target root/invocation, named plan/completion files and explicit
verification limits. It returns verified physical hashes and completeness,
or a named refusal. It neither collects nor publishes.

## Artifact-only Linux comparison

Run this migration experiment only by explicit `workflow_dispatch`. It does not
run automatically on pull requests, pushes or schedules. Normal CI retains the
fixture-backed Rust module and cross-language functionality tests. Production
uses Rust by default; this optional comparison workflow is not a recurring
production or archive-quality gate. Its tools remain alongside the retained
Python rollback path until that cleanup is explicitly resumed.

The latest consumed host reply group remains available while a job runs, even
after its ordinary retry window expires. A valid successor or session stop
releases that protection; failed admission does not discard the predecessor.
The limit and consumed-only retirement rules do not change. Producer cancellation
unwinds owned-process cleanup, and a producer termination failure cannot bypass
native monitor cleanup. Council controls use its selected `--config-root`.
Shadow sessions still keep the authoritative Python probe and clock writes.

`.github/workflows/rust-host-telemetry.yml` uses one stock `ubuntu-latest`
job with read-only repository permissions, credential-free checkout and seven-day
artifacts. It does not call `measure.yml`, publish, migrate history or write
production state. Its separate steps build/test the pinned crate, run independent
CPU/hash and unchanged-input replay plus historical dry-run fixtures, measure the
release build, prepare references, store the Rust probe, start the monitor, run
paired workloads, drain, store the clock, compare the same files, and always
clean up/upload. Dependency preparation happens before tests. The same native
crate supplies fixture and live results; no collector delegates to Python.

`utilities.compare_host_telemetry` routes the finite session operations. A new,
explicit `backend/var/` workspace holds distinct reference, native raw-state,
native-artifact, event, generated-state, corpus and frontend roots. Links,
junctions, escapes, overlapping roots and production-root spellings fail.
Reference rows use the existing Python decoders and raw-file writer only under
`reference/state/`; native output preserves `state/raw/host-fingerprint/`
grammar. Neither shared Python collectors nor readers change.

The driver records the actual workflow attempt in both writers. Its resource
`manifest.json` and standalone `host-manifest.json` have distinct session IDs,
event roots and host/resource result emitters, while sharing the declared job,
revision, boot identity, effective controls and real worker/CPU target. Both
probe and clock use the same host session and native raw root; retained commands,
sequences, predecessor IDs and completion references are checked. Resource
readiness/window counters cannot collide with a standalone result counter.

`config/host-telemetry-comparison.json` owns comparison-only counts, pacing,
intervals, deadlines, inventories and numeric bounds. The strict native experiment
configuration remains unchanged. Format, compression and cache sizing come from
the existing application config. Four reference runs precede every live Rust result;
their measured spread freezes each varying field's numeric allowance under a
predeclared ceiling. Excess noise refuses the run, never widens the ceiling.
Deterministic unchanged cells compare exactly. Corrected CPU facts rely on named
independent declared-input fixtures and validated live source diagnostics, not
equality to obsolete Python CPU columns. Canonical and identity tests use the
same declared row bytes, not physical native/PyArrow equality.

One real Python worker keeps a touched 32-MiB allocation and hashes it 128 times
per run. Each run has a declared seven-second minimum wall duration so legacy
second-resolution sample clocks have unambiguous interior coverage. This pacing
is part of the bounded fixture, not a speed measurement adjustment. Five-second
sampling respects native immutable retry retention; an unsafe faster cadence
is refused before capture instead of changing native budgets. Two pairs
alternate reference instrumentation and native-only instrumentation; native-only
runs create no substitute Python sampler. Captures retain actual Python PID/start
identities, sample/rollcall totals and per-window coverage. Population differences
are reported separately: the Rust monitor is not a Python process.

The bounded release measurement checks the actual checkout revision, pinned
toolchain and declared target root. Its retained executable size/hash must match
the binary used by the comparison; build output and elapsed time have committed
caps. No compilation result is accepted merely because its supplied SHA agrees.

The versioned `HostEvidenceReport` retains build wall time/executable bytes/hash,
startup, monitor CPU/RSS, ACK latency, workload and reference-instrument costs,
frozen bounds, every field classification/comparison, sample coverage, populations,
fixture case names and physical artifact hashes. Missing build, reference,
receipt, window, population, drain or coverage evidence fails. The bounded
verifier and shared `load`/`load_stored` readers verify the same original native
bytes. Verification compares inventory hashes
before/after and never re-encodes a native file. Received resource events preserve
native JSON bytes and must keep session identity, increasing emitter order,
triggering worker/window commands and a drain with no aborted windows. Sample
totals preserve the unchanged legacy HWM-or-RSS rule, including zero-HWM fallback;
that is independent of corrected window memory precedence.
Unreadable optional executable or argument metadata does not remove readable
Python memory from this population. Reference argument captures retain only the
program and the existing three argument fields, never the full command line.

Always-run cleanup names only recorded owned worker, sampler and monitor targets,
checks PID/start identity, and verifies termination within the existing drain
bound. Partial preparation can stop its recorded worker without a completed
manifest. `cleanup.json` is separate termination evidence. An actual Linux stage
integration and partial-failure cleanup test run in this workflow; Windows tests
exercise explicit refusals, not live Linux certification.
Response waits check the recorded worker identity and surface bounded worker and
sampler logs when it stops. The dedicated Linux tests retain their task-owned
workspace under the uploaded test directory, including failed-stage diagnostics.
Incomplete native timeout replies are retained as received and fail the required
acknowledgement; they are never accepted as healthy windows. The live monitor
retires validated, consumed events after their retry window before admitting the
next sample, keeping active windows protected and shutdown capacity reserved.

The merged D5 evidence report never authorizes adoption or
history replacement, asserts a general speedup, or substitutes for the exact
consumer and production gates.

## Bounded historical inventory and dry-run

`utilities.migrate_host_fingerprints` now prepares real replacement candidates
without writing historical files. It is a maintenance codec, not a CPU collector.
The unchanged Python collectors remain unchanged; migrated readers consume the
candidate output without Python re-encoding.

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
- `legacy_raw_evidence`, when a compact repair needs an original CSV row, pins
  its bytes and Git commit/path. The verifier resolves that exact path in the
  commit tree and requires its blob ID to match the evidence, not only the
  evidence bytes' computed blob hash.
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

The command defaults to dry-run. `--apply` requires the exact manifest, validated
D16 bundle, a dated `HistoryApplyApproval`, and an offline local checkout. The
transaction core stages destination-local outputs, verifies source-byte
backups, records immutable planned/replaced/verified journal events, rechecks
each source immediately before its per-file atomic replacement, and supports
exact-byte restart or rollback. It never accepts a third source state.

The approval records existing unattended user authority, D16/D7 revisions, the
three exact evidence hashes and the physical target directory identity. It is
not a signature service or another permission request. The maintenance context
refuses known or unresolved local writers, holds the existing OS publication-lock
primitive, and exclusively owns the actual Git index lock, including in linked
worktrees. It rechecks target identity, HEAD, index bytes and exact lock ownership
before staging or replacing files. Release removes only its own exact index lock;
the OS-lock inode remains. Neither an index lock nor a process snapshot prevents
arbitrary file writes: the operator must keep this checkout offline for the whole
apply/recovery window. Ubuntu CI has a separate filesystem and needs no shared lease.

```powershell
python -m utilities.migrate_host_fingerprints --apply `
  --workspace-root (Resolve-Path ..).Path `
  --manifest backend/var/history-manifest.json `
  --bundle-root backend/var/approved-d16-bundle `
  --approval backend/var/d17-approval.json
```

Repeat the same command and approval to resume exact old/new states. Add
`--rollback` to restore verified original bytes; a third state is never overwritten.
Manifest, bundle and approval may be explicitly named outside the target checkout;
historical writes still come only from validated relative manifested paths.
After an abrupt process kill, a surviving index lock requires operator recovery.
Hold the same OS maintenance lock, validate the owner contract and physical
checkout/evidence/Git bindings, and prove the recorded PID/start time no longer
identifies a live process before removing that exact lock. Never reclaim by age
or remove a foreign, changed or ambiguous lock.

The public journal and rollback entry points require a live validated maintenance
context. Internal generated fixtures without a context admit only a temporary
child outside any Git checkout; Windows short-name aliases resolve to the same
physical temporary root. Per-file atomicity is not a multi-file or
power-loss durability claim. D16's complete raw/compact/index/receipt/view
reconciliation and its exact approved manifest remain prerequisites;
implementation tests are not application evidence.
Installed reconciliation verifies every physical hash and backup, settlement
rank and keys, replacement schemas and index rows/bytes. It projects only the
approved installed inputs and reruns the real ledger reader and dashboard
publisher against D16's recorded result. Unrelated data from later runs is not
part of that historical replay.
Settlement winners retain their source, key and attempt. D16's original ranked
identity is mapped through that winner's exact recorded normalized identity,
including approved legacy compact unit-ID repairs; demanding the erroneous
legacy ID after conversion would reject the intended migration.

The approved offline rewrite completed on 2026-10-13: 308 manifested files,
815 settled host records, 587 work records and an unchanged dashboard. Original
bytes, approval, report, maintenance receipt and completion events remain under
the task-owned ignored transaction root. This is a completed bounded maintenance
operation, not a recurring archive-quality gate or a rewrite of Git history.

The command reads exactly two repository-owned configuration files, resolved
from the utility's location, not the operator's workspace or environment.
`history_migration_limits` in `config/host-history-migration.json` caps roots,
closed periods, manifested sources, per-file and aggregate history rows,
manifest bytes and the complete bundle. Its 512-source, 128-row/file and
4096-row aggregate ceilings are independent of `verification_limits.max_files`
and `max_rows`, which continue to cap an individual host output plan and file.
This lets one explicitly bounded history manifest cover its complete input
set without widening the D5 write-plan contract. It contains no copied
verification defaults. `verification_limits` in
`config/host-telemetry-experiment.json` caps individual and aggregate source
bytes, footer/decode bytes, JSON depth and Thrift items. Every source read is
bounded and hash-checked.
`HistoryLimits` validates the combined effective inputs before reading history.
`offline_maintenance.command_timeout_seconds` in the migration-only configuration
bounds local Git/process-inspection commands independently of native readiness;
Windows CIM startup is not a Rust readiness measurement.
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
The Windows API branch uses an explicit platform check; Linux does not load
Windows-only APIs.
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
A physical compact Parquet file may represent a packed zero-row period when its
envelope and index agree. Its empty chunks and page totals remain bounded and
validated; `empty` and `lost` index markers are not converted to packed files.
Zero-row raw inputs remain refused, and producer verification retains its
existing one-row requirement.

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

Console view inputs use the retained `ConsoleBand` contract, including its known
historical schema dates. The retired `frontend/public/machine/*.csv` projection
has no current reader contract and is refused before any bundle write. This
refusal does not retire source bytes or make a manifested file reconciled.
An affected historical batch remains blocked until its exact dependencies are
resolved; unrelated validated batches can proceed.
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

`HistoryReport` version `2026-10-12` records production cutover separately from
historical readiness. A successful migrated-consumer replay can make only the
historical decision ready. This report cannot certify production cutover and
keeps its production decision `blocked`; replay and elapsed time cannot satisfy
that gate. D7 separately verifies all-family, single-writer Ubuntu evidence before
the workflow defaults select Rust. Python remains an explicit temporary rollback
until cleanup, never a silent native-failure fallback.

The artifact-only workflow can run these bounded, generated-file tests before
its verdict; no test scans committed archives or installs tools:

```powershell
python -m pytest -n 0 tests/contracts/test_host_migration.py `
  tests/test_host_fingerprint_migration.py
```

The exact historical-data replay is a one-time operator activity outside pytest,
not an application, production or recurring CI step. Offline Python conversion
and reader replay may run on the development machine; Ubuntu remains the target
for live Rust process evidence. Preserve the exact manifest, report and candidates
in the task-owned maintenance directory. The approved apply replaces history
only after verified backups and destination-local staging are complete.
Report hashes bind one evidence generation, not the latest repository commit;
compare changed report fields and candidate data before accepting a new generation.
Normal tests use generated fixtures to cover functionality, not archive quality.
After the rewrite, remove one-time checks and any migration-only utility or tests
with no remaining recovery caller. Retain fixture tests for shared codecs,
versioned readers and any recovery code still in use.

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
