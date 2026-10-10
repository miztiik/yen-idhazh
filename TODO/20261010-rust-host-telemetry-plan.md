# Corrected Rust host telemetry through structured events

**Last Updated**: 2026-10-10

**Level**: 5 for corrected CPU semantics, versioned fingerprints, exchanges, reader migration and historical rewriting ([CLAUDE.md section 6](../CLAUDE.md#6-correction-levels)). Fowler approves the design and documentation only; implementation and adoption remain separately gated.

## 0. Operating contract

Table A - operating contract

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Replace Python host collection and raw host-file production with independently tested, modular Rust processes, corrected CPU measurements and versioned fingerprints, without losing readable history or changing ledger ownership. |
| A2 | Hard scope - in | Table E inventories instruments. Build Table AC's real modules with Table AN's replacement schema and Table AO's identity rules from the outset; expose a true memory off switch; test isolated Rust output against unchanged Python references for unchanged behaviour and independent fixtures for corrections; migrate backend/frontend consumers; dry-run then, after later user approval, rewrite inventoried historical files once; cut over and remove superseded collectors. |
| A3 | Hard scope - out | Table B prices exclusions. |
| A4 | ESCALATE triggers | Table C. The user settled the design and authorized implementation, PRs and merges on 2026-10-10. Fowler is the plan approval and architectural ambiguity authority. Implementation permission does not bypass D16's later evidence-based cutover and historical-write decisions. |
| A5 | Chosen strategy | Fowler: Parallel Change and Expand-Migrate-Contract at the reader boundary, then explicit single-writer cutover. The first adopted implementation is corrected Rust, not a compatibility-first release. YAML owns process lifetime; Rust writes raw host records; Python owns full item-health, shared compaction and publishing. No bindings or cross-language in-process calls. |
| A6 | Execution | Autonomous orchestrator per [execute-a-plan.md](../docs/how-to/execute-a-plan.md). Parallel N = 4; actual dispatch follows dependencies and disjoint file lists, not an assumed four-way split. Measuring rows run alone. |
| A7 | Status | Implementation authorized on 2026-10-10. Design row D1 is DONE (Fowler, 2026-10-10); implementation, evidence, adoption and maintenance rows advance through Table D. Source inspected at `2d9648936`; reconcile callers against the execution checkout and merge newer trunk changes only when needed. No Rust evidence or speed claim exists yet. |
| A8 | Worktree placement | New worktrees go under the repository sibling `../yen-idhazh.worktrees/`. The plan checkout is `rust-host-profiling-investigation`; do not edit shared main. Paths in tracked documents remain relative. |
| A9 | Ownership | After cutover Rust alone writes the migrated raw host ledger. Python remains the complete item-health writer and the shared compact-ledger/publishing owner. A Python host verifier reads Rust files and receipts without re-encoding, copying or re-filing them. Cross-language communication is serialized; normal calls between Rust modules are allowed. |
| A10 | Documentation | This page alone records the approved future design. Do not edit authoritative behaviour docs during authoring. Each implementation row updates its named living docs only when its behaviour lands; closure distils and removes this plan. |
| A11 | Next execution sequence | After a separate instruction to implement: 1 -> 2 -> 10 -> 11 -> 12 -> 3 -> 4 -> 15 -> 5 -> (13 + 14) -> 6 -> 8 -> 16 -> 7 -> 17 -> 9. Rows 13/14 are one schema-and-consumer merge unit with one owner; neither merges or becomes DONE alone. D16 requires later user cutover and exact historical-inventory decisions based on evidence; cutover permission alone does not authorize D17. |
| A12 | Modularity | One Cargo crate, with the questions, Python counterparts and per-module tests in Table AC. The CLI only routes commands, codecs only handle logical schemas/bytes, and producers never mint paths or envelopes. No empty modules, catch-all implementation files or extra crates without a concrete consumer. |
| A13 | Ambiguity and evolution | Consult the Fowler custom advisor when ambiguity changes the implementation. Prefer structural fixes and narrow, reusable contract boundaries that support long-term evolution; do not substitute a local workaround or speculative framework for the requested capability. |
| A14 | Implemented delivery partition | Fowler, 2026-10-10: parallelize disjoint modules within the active row after its real prerequisite checkpoint. Leaf worktrees explicitly depend on that candidate; the owner integrates them into one row PR, owns shared scaffolding and this Reckoner, and serializes expensive gates. Do not merge dependent leaf PRs independently into main or claim four ready rows. |

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan; parallel N = 4 subject to dependencies and disjoint file lists; measuring rows run alone; consult Fowler on architectural ambiguity; AUTO-merge on green gates within the implementation scope authorized on 2026-10-10; honor Table C and D16.

Table B - exclusions and their cost

| ID | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Porting the summarizer, scorer, publisher, complete item ledger or shared compaction/history engine | Python and its dependencies remain. Rust owns raw host output, not every pipeline output. | A separately requested port with named consumers and output contracts. |
| B2 | Python allocation/stack profiling | OS resident-memory readings cannot attribute allocations to Python objects or call stacks. | A separate profiler requirement and supported Python instrumentation; a Rust sidecar cannot observe allocator events from RSS alone. |
| B3 | Memory target-population correction or a new bandwidth method | E19 retains all readable Python processes; Rust is not counted as Python. The copy remains its existing separately controlled instrument. CPU corrections are IN scope, not deferred here. | A separate request with population/method fixtures and consumer costs. |
| B4 | Competing Python/Rust writers for the same host work unit | A single-writer cutover must be explicit; shadow output cannot be written into the production ledger. | A bounded artifact-only shadow run with separate roots, never two production writers. |
| B5 | Reusing a publishing trial workflow as the experiment | A new small workflow must be maintained until adoption. | Removal of its write/publish capability and proof that every output root is ephemeral. |
| B6 | Migrating unrelated encoder `RUSAGE_SELF` measurements | Those tools retain process-local benchmark semantics and Python instrumentation. | A separate request identifying the measured process and the consumers affected. |
| B7 | Porting CPU corrections back into Python collectors | The unchanged reference remains a truthful legacy instrument. Read/input adapters may convert its shape, never invent corrected CPU measurements. | A separate request for a Python producer change; no such change is needed for Rust replacement. |
| B8 | Cloud metadata opt-out, new memory attribution or recovery of missing hardware history | Existing placement and memory meanings stay; historical unmeasured facts stay unknown. | A separately priced capability with sources and consumers; replay cannot recover readings never taken. |

Table C - stop conditions

| ID | Trigger | Required response |
| --- | --- | --- |
| C1 | D16 has not recorded the later production decision | Continue the authorized implementation, isolated evidence, reader migration and inactive integration. Do not cut over production writers or apply historical maintenance until the corresponding D16 permission exists. Fowler's approval is not user adoption permission. |
| C2 | A change exceeds the settled Tables AN/AO schema, source, null or identity semantics | Pause for Level 5 scope consultation. Implement the already approved CPU/schema/fingerprint migration without reopening the user's settled design. |
| C3 | Per-item boundaries cannot be supplied without changes beyond the later event adapter | Name the required changes and cost; do not substitute job-wide samples or pretend YAML can infer the boundary. |
| C4 | The experiment requires a production push, deploy, state write, credentials or external model/feed service | Redesign the experiment or obtain explicit authorization; no automatic workflow dispatch during authoring. |
| C5 | An input/reader/caller search finds additional integration files | Update the affected row's exact file list and dependencies before dispatch. |
| C6 | Unchanged-field comparison needs wider tolerances, altered memory populations or hidden reference calls to pass | Report the difference; never relax bounds after seeing Rust results or add dummy Python processes. Corrected CPU/hash fields use independent fixtures, not a blanket Python-parity gate. |
| C7 | A scope change, unresolved advisor conflict or cost overrun fires the execution contract | Follow [handle-scope-change.md](../docs/how-to/handle-scope-change.md). |
| C8 | A Rust file needs false Python provenance or Python re-encoding to pass a reader | Stop. Use the isolated candidate oracle, then Row 13's finite writer/container/version mapping. Verify the same native Rust bytes throughout. |
| C9 | Historical inventory expands, a source hash changes, an unknown schema appears or an output/receipt/view cannot reconcile | Stop maintenance before replacing the affected batch. Refresh the bounded manifest and dry-run; obtain approval for changed write scope. Never scan/rewrite git history or delete unread source data. |

## 1. Status Reckoner

Table D - authoritative execution queue

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Approve corrected design and documentation only | - | A | DONE | rust-host-profiling-investigation | - | Fowler |
| D2 | 2 | Declare exchanges and a read-only host-output verifier | 1 | B | DONE | rust-host-telemetry-delivery | - | owner; disjoint exchange/verifier workers |
| D10 | 10 | Render compatible host files through tested Rust codecs | 2 | C | DONE | rust-d10-native-codecs | - | rust-d10-native-codecs |
| D11 | 11 | Persist host files through tested Rust storage modules | 10 | D | DONE | rust-d11-storage | - | owner; disjoint identity/path and atomic workers |
| D12 | 12 | Produce verified receipts and recover completed writes | 11 | E | DONE | rust-d12-receipts | - | owner; native receipt/recovery leaf |
| D3 | 3 | Produce machine probe and clock events in Rust | 12 | F | PENDING | - | - | - |
| D4 | 4 | Produce window and job resource events in Rust | 3 | D | PENDING | - | - | - |
| D15 | 15 | Build bounded historical inventory and dry-run migration | 4 | E | PENDING | - | - | - |
| D5 | 5 | Verify corrected Rust in an artifact-only YAML workflow | 15 | E | PENDING | - | - | - |
| D13 | 13 | Migrate shared schemas and readers before writers | 5 | F | PENDING | - | - | - |
| D14 | 14 | Migrate contracted backend and frontend consumers | 5 | F | PENDING | - | - | - |
| D6 | 6 | Add inactive event emitters at real production boundaries | 13, 14 | F | PENDING | - | - | - |
| D8 | 8 | Expose and test the independent memory off control | 6 | G | PENDING | - | - | - |
| D16 | 16 | Record later user cutover and historical-write decisions | 8, 5, 14, 15 | H | PENDING | - | - | - |
| D7 | 7 | Switch instrumented producers through events | 16 | I | PENDING | - | - | - |
| D17 | 17 | Rewrite the approved historical manifest once | 7, 15, 16 | J | PENDING | - | - | - |
| D9 | 9 | Remove superseded collectors and temporary duplication | 7, 8, 17 | K | PENDING | - | - | - |

## 2. Row #1 - Approve corrected design and documentation only

- **Scope:** Record Fowler's approval of the settled corrected design, module ownership, migration, controls and execution gates for a documentation commit only.
- **Files touched:** `TODO/20261010-rust-host-telemetry-plan.md`.
- **Acceptance gates - local:** Read the complete plan against named sources and itself; verify Tables AN/AO and AC/AE, all links and exact caller lists; run `python backend/utilities/doc_load.py TODO/20261010-rust-host-telemetry-plan.md` before/after and the documentation-only selector. Fowler approves architecture under the user's delegated authority.
- **Acceptance gates - CI:** None; this row is design consultation.
- **Oracle:** Every inventoried instrument has a named producer, consumer, disable behaviour and migration row; this establishes scope, not Rust correctness or performance.

### Current source inventory, not the corrected output declaration

Table E - enumerated capability inventory

| ID | Capability | Current result and meaning | Producer evidence | Current off control |
| --- | --- | --- | --- | --- |
| E1 | CPU identity | Model name, vendor, family, model number, stepping and microcode. | [silicon.py](../backend/idhazh/telemetry/silicon.py), `read_row` | F1 only. |
| E2 | CPU counts | `cores` takes the first reported physical-core count; `threads` counts parsed MHz entries, not online processors or target allowance. Replace both under AN, never copy them into corrected counts. | `silicon.read_row` | F1 only. |
| E3 | L3 cache | First matching level in cpu0's sysfs cache directories, converted to bytes; unavailable is null. | `silicon.cache_bytes` | F1 only. |
| E4 | Instruction-set facts | Sorted watched CPU features, space joined; derive the vocabulary from `WATCHED_FLAGS`, not a repeated count. These are hardware facts, not operator switches. | [host_fingerprint.py](../backend/idhazh/contracts/host_fingerprint.py); `silicon.watched_flags` | F1 only; no per-feature switches. |
| E5 | Legacy fingerprint | AO declares algorithm 1's exact keys/bytes and algorithm 2's corrected hardware-only identity. Historical hashes remain version 1, never recomputed from incomplete records. | `silicon.fingerprint_of` | F1 only. |
| E6 | CPU frequency observations | `_cpuinfo_fields` stores `cpu MHz` only in `clocks`, not `fields`. Thus `read_row`'s `fields.get("cpu MHz")` yields null here; `mhz_max` does NOT reliably capture a first observation. `mhz_at_probe` averages parsed clocks; AN allows only legitimate historical averages to migrate. | `silicon._cpuinfo_fields`, `silicon.read_row` | F1 only. |
| E7 | Machine uptime | First uptime value in seconds; missing, malformed or zero currently becomes null. | `silicon.boot_seconds` | F1 only. |
| E8 | Cloud placement | VM size, location, zone and fault domain from link-local metadata; unavailable placement leaves nulls. | `silicon.placement` | F1; F5 is an internal-only test seam. |
| E9 | Runner label | The platform's runner label, not a CPU identity or scheduling guarantee. | [host.py](../backend/idhazh/telemetry/host.py), `runner_name` | F1 for the host row. |
| E10 | Measurement context | UTC probe timestamp, contract version, date, run, job and shard; these connect the host record to item records. | `silicon.read_row`; [HostFingerprintRow](../backend/idhazh/contracts/host_fingerprint.py) | F1 for the host row; item census/join fields remain. |
| E11 | Memory-copy bandwidth | Two buffers, cache-aware size, three timed copies, median positive GiB/s counting read plus write. Default floor means at least 1 GiB held across two buffers. | `silicon.probe_buffer_mib`, `silicon.memcpy_gib_s` | F1, F2 or F3; F4 only sizes the copy. |
| E12 | Weight-load time | `model_load_ms` decoded from the server's load-start/load-finish log lines; missing logs give null. | `silicon.model_load_ms`, `file_job_clock` | F1 only; no independent load-clock flag. |
| E13 | Job elapsed time | Integer `job_seconds` from the supplied UTC start stamp and finish instant; unavailable stamp gives null. | `silicon.job_seconds`, `file_job_clock` | F1 only; no independent elapsed-clock flag. |
| E14 | Server prompt counters | Server-reported prompt tokens and seconds, independent of item-ledger arithmetic; missing series are null and fractional token counts are refused. | `silicon.server_prompt_totals`, `file_job_clock` | F1 only in this collector; a server with metrics disabled supplies no counters. |
| E15 | Per-item CPU/load | Whole-window busy/steal counter deltas, busy extrema and closing one-minute load. Window covers model work plus optional scoring, not fetching. | `host.Watch`; [work.py](../backend/idhazh/stages/work.py), model loop | F6 disables only periodic samples, not endpoint readings. |
| E16 | Per-item model memory/faults | Llama resident, anonymous resident, high-water resident memory and major-fault delta; selected server once per shard, not a sum of descendants. | `host.llama_server_pid`, `host.Watch` | No true off flag today. F6 is partial only. |
| E17 | Per-item Python memory | Closing resident and anonymous resident memory of the Python worker itself, not the monitor or every Python process. | `host.read_now`, `host.Watch` | No true off flag today. F6 is partial only. |
| E18 | Per-item machine memory | Closing available/total/cached RAM, free/total swap and minimum available RAM over the item's samples/endpoints. | `host.HostCells`, `host.Watch` | No true off flag today. F6 is partial only. |
| E19 | Job memory samples and process rollcall | Llama RSS/HWM; all readable `python*` processes, including the Python sampler itself; RAM/commit/cgroup readings; sample JSONL, process JSONL and peak summary. This is a different target population from E17. | [memory_sampler.py](../backend/utilities/memory_sampler.py), `sample_once`, `sample`, `summarize` | F7 controls cadence, not off; YAML currently starts it explicitly. |
| E20 | Runtime-sweep memory observations | Owned server status sampled each second and cgroup peak in the sweep result; distinct from item cells and host-record columns. | [runtime_sweep.py](../backend/utilities/runtime_sweep.py), server lifecycle | No config off switch for this sampler today. |

### Current switches, partial controls and misleading substitutes

Table F - control inventory

| ID | Control and default | What off actually does | What it does not do |
| --- | --- | --- | --- |
| F1 | `observability.host_fingerprint = true` | False writes neither probe nor clock host rows. | Does not stop E15 to E20, the item-health census or traces. |
| F2 | `observability.host_fingerprint_bandwidth_jobs = ["runtime"]` | An empty list disables copying everywhere; an unlisted job records probe size zero and bandwidth null. | Does not disable identity, placement, timestamps or clocks. |
| F3 | `observability.host_fingerprint_bandwidth_floor_mib = 512` | Zero disables copying even for selected jobs. | Does not disable other host cells. |
| F4 | `observability.host_fingerprint_bandwidth_cache_multiple = 2` | No off value; values below one are refused. | This is a sizing setting, not another disable switch. |
| F5 | Internal `silicon.read_row(ask_placement=True)` parameter | False skips metadata in that direct caller. | Not a public config/YAML/CLI off flag; ordinary pipeline invocation still asks placement. |
| F6 | `logging.waiting_heartbeat_seconds = 30` | Zero stops heartbeat ticks and periodic item sampling; opening/closing reads remain. | Does not turn memory sampling off. Negative config values are refused. |
| F7 | Job sampler `--every = 15` seconds | Changes the interval. No supported off value; zero is not an off switch. | Does not disable sampling. It starts immediately and runs until the supplied process disappears. |
| F8 | `observability.telemetry_publish = true` | False leaves the item-health CSV projection at its previous published state. | Does not stop collection or ledger persistence. |
| F9 | `observability.tracing_enabled = true` | False disables the separate trace instrument. | Does not disable host rows or memory collection. |
| F10 | Count answer for the host record | One public Boolean off flag, plus two settings that can disable only copying: F1 to F3. | The other controls do not constitute independent per-capability off flags. No public true memory-sampling off flag exists on this baseline. |

### Included corrections and explicitly excluded changes

Table G - opportunities and compatibility cost

| ID | Applies to | Improvement | Benefit and cost | Disposition |
| --- | --- | --- | --- | --- |
| G1 | E15 to E18 | Keep running extrema/counters instead of accumulating sample lists. | Bounded monitor memory per active window; preserve the existing whole-window mean and endpoint rules exactly. Applies in Python too; Rust does not make it automatic. | Include in Row 4 only with exact snapshot replay parity. |
| G2 | E15 to E20 | One Rust monitor with independent state for concurrent windows and explicit PID/start-time identities. | Fewer monitor processes/timers; avoids measuring Rust or silently following PID reuse. Event latency and resource use must be measured. | Include protocol safety in Row 4; preserve each instrument's existing target-selection policy. |
| G3 | E16 to E20 | A true memory-sampling switch independent of CPU, host identity, bandwidth and heartbeat. | Removes memory reads/artifacts without removing the census; adds one tested control. | Rust control is built in Rows 10/3/4 and exposed across config/CLI/YAML in Row 8 BEFORE D16 or cutover; default on. |
| G4 | E2, E5, E6 | Replace misleading CPU columns and explicitly version hardware fingerprints. | Truthful topology, target allowance and frequency; contract/read/consumer migration and one approved historical rewrite cost. | Included and settled by the user on 2026-10-10. Tables AN/AO are the sole semantics declaration. First adopted Rust is corrected. |
| G5 | E19 | Replace all-Python population with a workload subtree. | Would exclude unrelated/self-sampler memory but change established artifact meaning. | Out of scope, not a post-parity approval item. Record natural population differences; do not manufacture a Python sampler in Rust runs. |
| G6 | E8 | Cloud metadata opt-out. | Would avoid a request but add a public control and change collection. | Out of scope. Existing request policy remains; bounded diagnostics do not add an opt-out. |
| G7 | E11 | Checked allocation, observable allocation failure and a non-elidable native copy benchmark. | Prevents overflow, crash-shaped failures and compiler removal of unused copies. The large copy is already native C in Python, so Rust alone promises no gain. | Preserve size, repeats, timing region and read/write accounting in Row 3; a different bandwidth method is a separate experiment. |
| G8 | All events | Readiness, bounded backpressure, idempotent command/result files and shutdown evidence. | Makes monitor failure visible and recoverable; adds a small file protocol and build/toolchain cost. | Include in Rows 2 to 5 and 10 to 12; no generic event bus or permanent second implementation. |
| G9 | Host file output | Separate schema, codecs, store, producers and observations behind narrow Rust modules. | Allows independent tests and isolates engine changes, as the Python ledger already does; adds no language bindings or extra framework. | Required Table AC decomposition; each implementing row ships its modules' tests. |

### Approved event-only boundary

Table H - settled exchange contracts

| ID | Contract surface | Declaration and invariant | Consumer |
| --- | --- | --- | --- |
| H1 | Common event envelope | Date-stamped `version`; `kind`; UUID `event_id`; nullable `reply_to`; `date`, `run_id`, `attempt`, `job`, `shard`; UUID `session_id`; `emitter_id`; increasing integer `sequence`; UTC `emitted_at`; discriminated, typed `body`. Declare once under `backend/idhazh/contracts/host_events.py`. | Rust collector/store/monitor and Python read-only verifier/client. |
| H2 | Schema and number rules | Refuse unknown event fields/kinds/versions, nonfinite floats and conflicting identities. Protocol IDs/counts/ticks use whole integers, rejecting booleans, numeric strings, fractions and overflow; attempt starts at one, shard at zero, PID is positive. Current public validators retain their existing acceptance rules. | Exchange validators and parity tests. |
| H3 | Process identity | Target references carry PID plus procfs process start ticks; readiness records machine boot identity. Verify before/after reads; never silently follow PID reuse. Preserve E16's selected-server rule and E19's all-Python memory population. AN defines CPU allowance targets independently. | Resource monitor and CPU probe. |
| H4 | Window identity | Body carries an operator-derived `window_id` and existing `item_id`; each window belongs to one registered emitter/session. Several registered workers/windows may overlap without sharing endpoints or extrema. | Monitor and worker health writer. |
| H5 | Host result | Body nests AN's corrected host row, typed CPU source/coverage/target diagnostics and references to H15 completion evidence. Probe/target/clock consume their own attempt's immutable plan and latest whole row. A target enrichment follows AN's distinct capture rule; clock never remeasures CPU facts. | Read-only verifier and publisher; Rust store writes host files. |
| H6 | Window result | Declare `HostWindowCells` using the exact keys/types derived from `HostCells.cells()` and bound to `ItemHealthRow`. Status is `complete` or `incomplete`, with typed unavailable reasons outside the cells. Memory off yields null memory/fault cells but valid CPU/load cells; abort without endpoints yields null cells. | Python's complete health writer before seal. |
| H7 | Legacy sample artifacts | Declare typed job-sample and process-rollcall bodies matching E19's current JSONL records; keep kilobytes there and bytes in H6. Export the existing filenames, fields and summary semantics from events. Do not add envelope keys to the legacy records. | Existing artifact readers and summary. |
| H8 | State machine | Register -> registered; begin -> opening snapshot -> begun; end -> closing snapshot -> result; abort -> incomplete result. Healthy work begins after ACK; bounded ACK failure follows H11/J5's diagnosed-unavailable path rather than blocking work forever. Seal health only after result or explicit instrument failure. | Event client and monitor. |
| H9 | Duplicate/order rules | An identical retried command retains ID/sequence and returns the same ACK/result. A reused ID with different content, end-before-begin or wrong target is a protocol fault. Ordering is per emitter. Storage retries reuse the immutable write plan; see Table AE for file/hash/collision rules. | Bounded command reader, Rust store and tests. |
| H10 | Clocks | UTC describes instants. The monitor's monotonic clock controls cadence/deadlines; never subtract a Rust `Instant` from a Python monotonic value. Preserve the existing source of each published duration. | Monitor, clock decoder and parity driver. |
| H11 | Failure rules | Missing optional instruments yield null plus typed diagnostics. Invalid events/files refuse verification. A bounded instrument timeout permits diagnosed unavailable cells and preserves work/census; work/config/store/protocol failures stay explicit. Missing required experiment evidence fails. No silent Python fallback after adoption. | CLI verifier, worker and workflow. |
| H12 | Event ownership | Rust producers collect; Rust codecs render; Rust store atomically persists host files; Rust emits completed-file evidence. Python verifies those same files/receipts and may publish them, but never re-renders/re-files migrated host output. Window cells return before Python's full health seal; no partial competing health ledger or post-hoc patch. | Existing publishing and health paths. |
| H13 | Language boundary | Producers/consumers exchange serialized files. Python serializes lifecycle events and consumes results without Rust/FFI imports. Isolated Python additions are exchange/verification/test modules, not edits to reference collection or shared readers. Those stay unchanged until Row 13 and later integration. | YAML launchers, verifier and stage adapters. |
| H14 | Session manifest and diagnostics | Declare named inputs, operator identities, expected workers/windows, CPU target selection, concurrency and limits. Unavailable reasons are `missing`, `malformed`, `permission_denied`, `pid_exited`, `pid_reused`, `disabled`, `timed_out`, `snapshot_changed`, `incomplete_coverage`; protocol faults are separate. Unlimited quota uses AN's persisted state, not an unavailable reason. No unrestricted body maps. | Manifest loader and consumers. |
| H15 | Host write plan and completion | A typed immutable plan declares event/attempt, target root, rows, schema/format/compression, per-day timestamp, logical unit/file IDs, expected canonical hash and planned relative path. Completion carries the existing `PublicationReceipt` shape with physical-byte hashes plus the triggering event ID. Ledger row identity and publication invocation identity are distinct and checked independently. | Rust persistence/recovery, read-only verifier and publisher. |
| H16 | Rust provenance candidate | Preserve the `FileEnvelope` key set. Finite pairs are Parquet with `idhazh.ledger.parquet` or `idhazh_rust.ledger.parquet`, and JSONL with `idhazh.ledger.json_lines` or `idhazh_rust.ledger.json_lines`. Native writers are allowed only for AN's corrected host schema and raw tier; Python remains compact writer. Record actual engine versions and native `created_by`. AN pins candidate dates; Row 13 later installs the same mapping in shared readers, including footer-only paths. | Candidate file oracle, then shared readers. |

Table I - command/result vocabulary

| ID | Command or startup | Required response | Body purpose |
| --- | --- | --- | --- |
| I1 | Monitor startup | `monitor.ready` | Session/boot identity and supported contract version; no measurement claim. |
| I2 | `host.probe`, `host.target`, `host.clock` | `host.result` or typed `instrument.skipped`/`protocol.fault` | Operator context, collection controls and captured inputs; AN defines target enrichment; H5 output. |
| I3 | `worker.register` | `worker.registered` | H3 targets and H4 window allowance. |
| I4 | `window.begin` | `window.begun` | Opening snapshot ACK before model work while healthy; bounded failure follows H8/H11. |
| I5 | `window.end`, `window.abort` | `window.result` | H6 cells with explicit complete/incomplete status and diagnostics. |
| I6 | `monitor.stop` | `monitor.stopped` | Drain completed results, abort unresolved windows explicitly, flush evidence and exit. |

Table J - file transport and starting experiment settings

| ID | Property | Rule |
| --- | --- | --- |
| J1 | Address | Operator-owned run root under `backend/var/host-events/<run>/<attempt>/<job>/<shard>/<session>/`, with named inputs, inbox and results. Export artifacts and test state to sibling task-owned directories. No production state root by default. |
| J2 | Publication | UTF-8 JSON with LF, sibling temp-file then same-filesystem rename. Commands/results are immutable; conflicting existing content fails. Result filenames derive only from validated operator IDs. |
| J3 | Read bounds | Use one named manifest and finite session directories. Cap proc/sysfs text bytes, CPU-ID range/cardinality, cgroup ancestry/mount entries, process count and named log captures in config; limit exhaustion yields incomplete coverage, never a truncated valid count. Recovery reads only H15 paths; own-probe lookup is one declared day/unit/attempt with a file-count cap. No history scans. Validate virtual-filesystem targets separately from ordinary path escape checks; approved cpufreq policy links may resolve only inside the sysfs CPU root. |
| J4 | Limits | Manifest lists expected workers/windows and concurrency. Bound active windows to declared concurrency and pending events to four times registered workers plus active-window allowance, plus eight lifecycle slots. Starting caps are 64 KiB command and 256 KiB result. Add explicit total-session event/byte limits and safe completed-message retirement; a retained ACK/result cannot grow without bound or disappear before its retry/recovery window ends. Exhaustion applies backpressure then an explicit fault, never drops data. |
| J5 | Cadence/deadlines | Transport polling starts at 50 ms, readiness at 10 s and ACK/drain at 5 s; these are tunable experiment values, not fixed production thresholds. Resource cadence preserves each instrument including F6 endpoint-only mode. A begin/result timeout diagnoses incomplete instrument coverage and permits work/census under H11; the no-work-before-ACK rule applies only while the monitor is healthy, never an indefinite work stall. |
| J6 | Configuration | Add a dedicated config file for experiment limits; propagate selected existing collection settings in typed events. No source literals for tunable limits, no article/model-output text in command paths or bodies. |
| J7 | Cleanup | YAML tracks the monitor PID and logs, verifies readiness, requests shutdown and uses bounded grace before terminating only that PID. An `always()` step is best-effort under cancellation; atomic completed results survive, interrupted windows remain incomplete. |

Table K - Row 1 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| K1 | YAML orchestrates jobs; Python executes the stages. Rust sampling must share the observed job/runner and run as separate processes/steps. | User event-only requirement; Fowler; [digest.yml](../.github/workflows/digest.yml), probe/server/sampler/work steps. |
| K2 | Existing `item.start` occurs before fetching and finished spans arrive too late. Real model-window begin/end events are missing and require the later adapter. | Fowler; [work.py](../backend/idhazh/stages/work.py), Watch construction and both health-sealing branches. |
| K3 | Corrected schema and truthful Rust provenance both require migration. `_opened` requires the Python codec's exact name; `read_footer` currently only validates envelope metadata. Row 13 covers both and legacy normalization; Row 14 covers live consumers before cutover. | [persist.py](../backend/idhazh/ledger/persist.py), `_opened`, `read_footer`, `render_renamed`; [FileEnvelope](../backend/idhazh/contracts/file_envelope.py); Fowler. |
| K4 | Use Tables E/F as a dated source inventory, not a promise that every capability has its own flag. Re-derive the CPU-feature and cell counts before execution. | Named producer/contract predicates. |
| K5 | Follow the Python separation of codec, schema, identity, paths, persistence and producers, without copying its entire compaction engine or making the CLI a dumping ground. | User modularity requirement; Table AC. |
| K6 | APPROVED for a documentation commit. The user's design confirmation is complete; Fowler is the assigned plan authority. Guardrail #3 (contracts before logic), #9 (tests with behaviour) and section 11 (old payloads remain readable) are satisfied by the planned sequence, not yet implemented. | Fowler, 2026-10-10; user delegation. |
| K7 | Correction Level 5 is priced by this complete breakdown. Use separate structural and behavioural commits inside a row when needed; a row is an outcome, not permission to mix hats. No automatic Carmack or further design-confirmation gate. | Fowler; settled user scope. |

Table L - Row 1 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | PyO3, ctypes or an in-process Rust extension | Violates the requested inter-language boundary. | Owner approval to change that boundary plus ABI/wheel/crash-isolation maintenance. | User; Fowler. |
| L2 | A separate GitHub job or only a post-work probe | Different runner, or no observations of the missing item window. | Same-runner process orchestration or a different measurement scope approved by the owner. | Fowler; workflow scheduling and Watch lifecycle. |
| L3 | Redis, RPC or a generic plugin/event framework | Adds service/process contracts with no consumer beyond this bounded instrument. | Demonstrate a consumer that cannot use the finite file protocol, then price operations and failure modes. | Fowler. |

## 3. Row #2 - Declare exchanges and a read-only host-output verifier

- **Scope:** Ship the approved exchange contracts, isolated corrected/legacy candidate models, bounded readers and a read-only verifier without changing existing collectors, shared models/readers or production invocation.
- **Files touched:**
  - `backend/idhazh/contracts/host_events.py`
  - `backend/idhazh/contracts/host_output.py`
  - `backend/idhazh/telemetry/host_event_files.py`
  - `backend/idhazh/telemetry/host_output_verify.py`
  - `backend/idhazh/telemetry/host_parquet_admission.py`
  - `backend/utilities/verify_host_output.py`
  - `backend/tests/contracts/test_host_events.py`
  - `backend/tests/contracts/test_host_output.py`
  - `backend/tests/test_host_output_verify.py`
  - `backend/tests/test_host_event_files.py`
  - `backend/tests/test_host_parquet_admission.py`
  - `pyproject.toml`
  - `tests/fixtures/host-events/manifest.json`
  - `tests/fixtures/host-events/cpu-snapshots.json`
  - `tests/fixtures/host-events/fingerprint-versions.json`
  - `config/host-telemetry-experiment.json`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Shared selector; contract/verifier tests with real generated files. Candidate host/legacy models in `host_output.py` implement AN/AO independently of the unchanged public model; compare unchanged fields/types to it. Validate original stored-byte digests before normalization, RowIdentity, AN versions and H16 pairs. Refuse malformed/conflicting/out-of-root files and forged receipts.
- **Acceptance gates - CI:** Existing full suites plus named contract/verifier tests; this row neither builds Rust nor claims unchanged full-ledger readers accept its provenance.
- **Oracle:** Verification reads the supplied bytes and validates their typed rows/envelope/physical hashes without altering any host file; it cannot establish a Rust collector exists or grant permission to publish.

Table M - Row 2 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| M1 | Implement Tables H to J and AN/AO in isolated candidate models; verifier neither collects nor persists host rows and cannot manufacture Rust output through Python collection. Consolidate candidates into shared contracts only in Row 13. | Approved Row 1; Fowler. |
| M2 | Verify the existing logical host producer/unit, attempt, payload and exact physical-file evidence; Rust producers/store perform actual enrichment/publication in later rows. | [silicon.py](../backend/idhazh/telemetry/silicon.py); H15. |
| M3 | Use recorded inputs/generated files. Separate current container decoding and measurement validation from prospective envelope validation; preserve existing readers during the isolated experiment. | H13/H16; C8. |
| M4 | Test declared schemas, versions and writer/container combinations explicitly; no unrestricted provenance regex or file-reencoding proxy. | Table AE; current `_opened` refusal. |
| M5 | Admit actual Parquet pages before native row decoding. Bound page headers, bodies, dictionary cardinality and decoded bytes for the concrete flat raw-host profile; verify none, raw Snappy and Zstd against actual body sizes. Footer size claims and checks after Arrow allocation are not bounds. Maintain the original bytes for engine decoding. | Fowler, 2026-10-10; generated forged-footer compressed-string evidence exposed allocation before refusal. |

Table N - Row 2 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Python re-files Rust host rows or patches sealed health files | Hides a missing Rust persistence module or introduces a competing writer. | Change the requested ownership or migrate the full item-health contract explicitly; neither is this row. | User; Fowler; H12. |

## 4. Row #3 - Produce machine probe and clock events in Rust

- **Scope:** Ship real Rust probe/target/clock producers using corrected CPU/fingerprint semantics, with unchanged-field reference comparison and independent corrected-input fixtures.
- **Files touched:**
  - `backend/rust/host-telemetry/Cargo.toml`
  - `backend/rust/host-telemetry/Cargo.lock`
  - `backend/rust/host-telemetry/rust-toolchain.toml`
  - `backend/rust/host-telemetry/src/main.rs`
  - `backend/rust/host-telemetry/src/cli.rs`
  - `backend/rust/host-telemetry/src/lib.rs`
  - `backend/rust/host-telemetry/src/producers/job_probe.rs`
  - `backend/rust/host-telemetry/src/producers/job_clock.rs`
  - `backend/rust/host-telemetry/src/producers/target_probe.rs`
  - `backend/rust/host-telemetry/src/fingerprint.rs`
  - `backend/rust/host-telemetry/src/probe_inputs/cpu.rs`
  - `backend/rust/host-telemetry/src/probe_inputs/topology.rs`
  - `backend/rust/host-telemetry/src/probe_inputs/allowance.rs`
  - `backend/rust/host-telemetry/src/probe_inputs/frequency.rs`
  - `backend/rust/host-telemetry/src/probe_inputs/placement.rs`
  - `backend/rust/host-telemetry/src/probe_inputs/bandwidth.rs`
  - `backend/rust/host-telemetry/tests/fingerprint.rs`
  - `backend/rust/host-telemetry/tests/probe_inputs.rs`
  - `backend/rust/host-telemetry/tests/cpu_measurements.rs`
  - `backend/rust/host-telemetry/tests/job_producers.rs`
  - `backend/rust/host-telemetry/tests/cli.rs`
  - `backend/rust/host-telemetry/tests/probe_clock.rs`
  - `backend/tests/contracts/test_host_event_rust_parity.py`
  - `tests/fixtures/host-events/probe-clock.json`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Cargo tests/fmt/clippy and shared selector. Independent CPU fixtures cover sparse/duplicate/offline IDs, topology gaps, SMT/multiple sockets, affinity versus online IDs, nested v1/v2 quotas/cpusets, fractional/unlimited/unreadable allowance, namespace-hidden ancestors, PID reuse, hotplug races, absent/partial/invalid frequency, unit conversions and the E6 source defect. Hash tests cover both AO versions and exclusion of quota/affinity/frequency. Replay unchanged metadata/cache/copy/clocks/counters against recorded Python.
- **Acceptance gates - CI:** Locked Rust build precedes cross-language tests; current silicon fixtures, isolated Rust-file/schema/receipt tests and frontend bindings. Snapshot tests access neither network nor Cargo downloads. Routine Rust preparation already landed in Row 10.
- **Oracle:** Actual persisted Rust rows satisfy AN/AO's independent vectors and unchanged fields match recorded Python inputs under AE; this proves neither live bandwidth equality nor a runtime speed gain.

Table O - Row 3 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| O1 | Preserve E1/E3/E4/E7 to E14; REPLACE E2/E5/E6 with AN/AO. New Rust emits only corrected schema and algorithm 2 when identifying facts exist (otherwise a null hash/version). Legacy read support is not a compatibility-first producer. | Settled user correction intent; Fowler. |
| O2 | Consider `serde`, `serde_json` and `sha2` for typed JSON/hash work, plus a maintained minimal HTTP client for link-local metadata. Lock dependencies and report beneficiary, build time and binary cost before adding them. No custom HTTP stack. | Fowler; open-source-first rule. |
| O3 | Keep copy allocation/timing/accounting; checked sizes, fallible allocation and observable copy results prevent dead-copy elimination. Serialize AO and AE canonical bytes explicitly; serde defaults alone do not prove Python-compatible JSON. Memory collection off does not turn the separately controlled copy off. | E11; G7; AN/AO. |
| O4 | Route commands in the CLI; `job_probe`/`job_clock` build typed payloads and call the Rust store. Producers do not import codecs, allocate envelopes or build paths. Their contract tests compare probe/full-clock files, not just JSON results. | Table AC; user modularity requirement. |

Table P - Row 3 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| P1 | Release compatibility-first Rust, copy legacy CPU defects or duplicate old/new columns | Fails the settled corrected replacement intent and prolongs misleading data. | Another approved product direction; the chosen replacement already prices fixtures, reader migration and history rewriting. | User, 2026-10-10. |
| P2 | Change the bandwidth algorithm alongside CPU corrections | Adds an unrelated measurement change. | Separate method comparison and consumer semantics; not needed for this replacement. | G7; user scope. |

## 5. Row #4 - Produce window and job resource events in Rust

- **Scope:** Add the real Rust monitor, legacy memory artifacts and runtime server-status results with bounded window state and explicit lifecycle/failure evidence.
- **Files touched:**
  - `backend/rust/host-telemetry/src/main.rs`
  - `backend/rust/host-telemetry/src/cli.rs`
  - `backend/rust/host-telemetry/src/producers/job_samples.rs`
  - `backend/rust/host-telemetry/src/sampling/process.rs`
  - `backend/rust/host-telemetry/src/sampling/machine.rs`
  - `backend/rust/host-telemetry/src/windows/reduce.rs`
  - `backend/rust/host-telemetry/src/monitor/session.rs`
  - `backend/rust/host-telemetry/src/transport/files.rs`
  - `backend/rust/host-telemetry/src/transport/bounds.rs`
  - `backend/rust/host-telemetry/tests/process_sampling.rs`
  - `backend/rust/host-telemetry/tests/machine_sampling.rs`
  - `backend/rust/host-telemetry/tests/transport.rs`
  - `backend/rust/host-telemetry/tests/job_samples.rs`
  - `backend/rust/host-telemetry/tests/windows.rs`
  - `backend/rust/host-telemetry/tests/process_lifecycle.rs`
  - `backend/tests/test_host_event_resource_parity.py`
  - `tests/fixtures/host-events/resource-windows.json`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Cargo and selected Python tests; exact same-population memory-on replay of E15 to E20. Test memory off with read-denying proc/memory paths: CPU/load, heartbeat and identity continue; no memory/fault reads or artifacts occur. Cover fault resets, endpoint-only mode, overlap, duplicate/order faults, capacity and shutdown.
- **Acceptance gates - CI:** Linux process-lifecycle tests, PID reuse/exit, signal/cancellation cleanup, legacy artifact/import validation and current `test_host_readings.py`/`test_memory_sampler.py` fixtures.
- **Oracle:** The same snapshots and event windows produce equal typed cells/artifact records with memory bounded by declared active windows; this cannot settle scheduler/IPC effects on a live workload.

Table Q - Row 4 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| Q1 | Preserve each source's target population, cadence and endpoint/HWM/fault arithmetic. H6 reads the registered Python worker, never Rust's own PID. | E15 to E20; approved H3/H6. |
| Q2 | Replace unbounded sample arrays only where running statistics reproduce the old result exactly. The legacy artifact sample stream remains available to its consumers. | G1; compatibility fixtures. |
| Q3 | Distinguish unavailable readings from protocol/identity faults; memory-off windows are complete for CPU/load with disabled memory diagnostics, not wholly incomplete. Validate target identity using `stat` start ticks without extracting major faults when memory is off. | H8 to H11; AN. |

Table R - Row 4 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| R1 | Sum a workload subtree or add dummy Python processes to make totals match | Changes or conceals E19's existing population. | A separately requested memory-population correction; natural collector-process differences are reported, not hidden. | Fowler; B3/C6. |

## 6. Row #5 - Verify corrected Rust in an artifact-only YAML workflow

- **Scope:** Run both independent implementations against bounded fixtures and the same live Linux workload, retaining only expiring artifacts and no production edits or publishing.
- **Files touched:**
  - `.github/workflows/rust-host-telemetry.yml`
  - `backend/utilities/compare_host_telemetry.py`
  - `backend/utilities/host_telemetry_workload.py`
  - `backend/tests/workflows/test_rust_host_telemetry_workflow.py`
  - `backend/tests/test_compare_host_telemetry.py`
  - `config/host-telemetry-experiment.json`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Shared selector and generated workflow/input tests; refuse unsafe permissions, default production roots, absent evidence and collectors that delegate back to Python. Confirm every workload and input is bounded and local.
- **Acceptance gates - CI:** Locked pinned Rust on stock `ubuntu-latest`; independent AN/AO vectors and historical dry-run fixtures; unchanged-field deterministic replay and same-target live comparison; native file/schema/receipt tests, off-control read tests, failure/cleanup and artifact upload under `always()`. Existing Python collectors/public contracts/readers are unchanged throughout isolated evidence.
- **Oracle:** Independent corrected-input truth plus exact unchanged-field replay and predeclared live bounds validate the intended Rust implementation in isolated roots; this does not approve adoption, all production workloads or a general speedup.

Table S - Row 5 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| S1 | Separate YAML steps within one job: prepare/capture -> Rust probe/store -> start monitor -> reference/workload -> close/drain -> Rust clock/store -> read-only file/receipt comparison -> stop/upload. Initial driver supplies windows; reference Python persists only into its separate generated root. | User event boundary; K1/K2; H12. |
| S2 | Workflow permissions are `contents: read`; checkout credentials are disabled. No publishing/land/push/deploy steps, secrets, feeds or remote model services. Pin actions/toolchain using repository conventions; retention starts at seven days. | Discard-only intent; C4. |
| S3 | Python-reference, Rust-result, event, generated state, corpus and frontend roots are all task-owned and separate. No trial-root alias that still writes production state. Verify writer evidence contains only those roots. | [measure.yml](../.github/workflows/measure.yml), `Commit the machine this bench drew`, demonstrates why existing trials are not ephemeral. |
| S4 | The manifest classifies every field as unchanged, corrected or context/physical metadata. Unchanged deterministic fields compare exactly; calibrate live clock/RSS/CPU-load skew using repeated references before Rust results and freeze numeric bounds/sample counts. Corrected AN/AO values use independent fixtures, never Python equality or blanket exclusion. Missing required evidence fails; D16 reviews measured noise and bounds. | Guardrail #10; C6; user evidence decision. |
| S5 | Capture each implementation's actual process population. Removing the Python sampler changes E19 in a live run; replay exact populations and report the live difference separately, never count Rust as Python. | E19/G5. |
| S6 | Report compile time, executable bytes, startup, monitor CPU/RSS, event ACK latency, workload wall time and sample coverage. Paired runs separate instrument cost from workload variation; no invented gain threshold. | Fowler; exploration is a requested capability, not conditional on a claimed speedup. |
| S7 | Table AE compares exact canonical/identity vectors for the SAME declared bytes, not old/new full-row equality or native/PyArrow physical equality. Current shared Python readers are expected to reject corrected Rust files before Row 13. Report candidate-reader success by name; no re-encoding proxy. | C8; isolated reader-before-writer migration. |
| S8 | Build and retain the SAME crate/modules intended for adoption; generated roots end in the same relative `state/raw/host-fingerprint/` tree and AO key/path logic. No production `state`, compact/public output, reference-source edits or separate throwaway Rust implementation. | User, 2026-10-10. |

Table T - Row 5 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T1 | Dispatch the existing measure workflow as the parity gate | It commits trial host state to main and may run a different workload. | Remove its publication path and prove isolated roots, or keep the small dedicated workflow. | S3; source workflow. |

## 7. Row #6 - Add inactive event emitters at real production boundaries

- **Scope:** Add optional structured window/job events and result consumption at current measurement boundaries, keeping Python authoritative and the new path inactive by default.
- **Files touched:**
  - `backend/idhazh/telemetry/host_event_client.py`
  - `backend/idhazh/telemetry/job_machine.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/contracts/knobs/observability.py`
  - `config/idhazh.json`
  - `backend/tests/test_host_event_client.py`
  - `backend/tests/pipeline/test_work_host_events.py`
  - `backend/tests/test_job_machine.py`
  - `backend/tests/contracts/test_app_config.py`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Shared selector; real file-event client tests; both health-sealing branches, scoring/no-scoring/failure/cancellation windows, duplicate closes and target exits. Default path remains identical to current Python behaviour.
- **Acceptance gates - CI:** Full existing suites; Linux same-target shadow comparison without production publication. The event-only adapter returns before record/commit; health is never amended later.
- **Oracle:** Event windows match the actual Watch boundaries and inactive mode preserves existing output; this does not establish acceptable enabled-path latency or authorize cutover.

Table U - Row 6 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| U1 | Temporary `observability.host_event_shadow = false` enables artifact-only event comparison. It never selects a second production writer. Default mode has no event I/O/waits. Shared schema adapters normalize legacy output without changing the Python collector's measurements; remove shadow wiring in Row 9. | Guardrail #6; AN legacy migration. |
| U2 | Emit begin at Watch opening and end before both health seals, including success, scoring, failed summary and cancellation; preserve Python heartbeat independently when Rust replaces Watch. Register the actual worker/server and send AN's target enrichment before profiled work when a target exists. YAML owns Rust lifetime; no inference from fetch/item-start or late traces. | K2; `work.py` lines 488/576/628; AN. |
| U3 | Match the existing `job_machine.record` scope, UTC start and error policy. Rust file receipts must be verified before any gardener/council publisher stages them; shadow files stay in an isolated root and cannot be submitted as production writes. | [job_machine.py](../backend/idhazh/telemetry/job_machine.py); H12. |

Table V - Row 6 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| V1 | Never add events to Python and infer item boundaries from artifacts | End artifacts do not reveal when to take an opening sample. | A different job-only measurement scope or a new stage-envelope contract, both requiring owner approval. | User/Fowler; C3. |

## 8. Row #7 - Switch instrumented producers through events

- **Scope:** After D16 explicitly permits cutover, adopt the corrected Rust implementation through events with one raw host writer and exact publishing receipts in a dedicated reversible behavioural change.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/measure.yml`
  - `.github/workflows/encoder-comparison.yml`
  - `.github/workflows/idhazh-gardener.yml`
  - `.github/workflows/llm-council.yml`
  - `.github/actions/model-server/action.yml`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/telemetry/job_machine.py`
  - `backend/idhazh/telemetry/host_event_client.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/utilities/digest_publish.py`
  - `backend/utilities/record_publish.py`
  - `backend/utilities/gardener_publish.py`
  - `backend/utilities/council_publish.py`
  - `backend/utilities/runtime_sweep.py`
  - `backend/utilities/model_runtime.py`
  - `backend/utilities/verify_host_output.py`
  - `backend/tests/workflows/test_worker_ledgers.py`
  - `backend/tests/workflows/test_a_job_that_plans_nothing_records_its_machine.py`
  - `backend/tests/workflows/test_extra_publishers.py`
  - `backend/tests/workflows/test_model_server_jobs.py`
  - `backend/tests/test_job_machine.py`
  - `backend/tests/test_model_runtime.py`
  - `backend/tests/pipeline/test_work_host_events.py`
  - `docs/reference/host-metrics.md`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** D16 cutover approval, Rows 13/14 readers/consumers and Row 8 controls must be complete. Reconcile callers under C5; test real native-file receipts, enabled integration latency, true memory-off across every family and absence of competing host writers. No automatic workflow dispatch.
- **Acceptance gates - CI:** Existing full suites, named workflow coverage tests, contract/Arrow/CSV/frontend checks and fixture pipeline. Observe next authorized scheduled run for each migrated family; do not trigger a publishing workflow merely to certify this row.
- **Oracle:** Every named instrumented family produces AN/AO-corrected host records and unchanged-scope resource results through one writer with verified receipts; fixtures cannot establish an unobserved scheduled family's live timing.

Table W - Row 7 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| W1 | Cover digest plan/work/assemble, runtime bench and encoder probe, gardener `run-tasks`, and council `save_council_results`. The job enum is not an instruction to instrument unmeasured planning/judging/history jobs. | [host-metrics.md](../docs/reference/host-metrics.md); current YAML/callers. |
| W2 | One-shot probe/clock/store and persistent monitor are same-job commands. Python emits lifecycle events and consumes cells/verified host-file receipts. Rust alone persists host rows; Python still seals full health records and compacts/publishes. | User; H12/H13. |
| W3 | Close/drain/verify before health seal, record and publisher commit. Keep a probe half-row usable if clock fails; preserve attempts and whole-row enrichment. Use Row 13's reader for the same Rust file, never a Python-reencoded replacement. | H12; Table AE; existing publishing boundary. |
| W4 | Separate cutover from deletion and historical maintenance. Reverting cutover restores legacy collection behind the migrated input adapter, not old readers that cannot consume new data. Historical write rollback uses D17's byte backups, not a git-history rewrite. No silent reference fallback or permanent implementation selector. | Fowler; two-hat discipline; AN. |

Table X - Row 7 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| X1 | Enable Rust everywhere while leaving Python collecting/writing too | Races, duplicate units and ambiguous observed populations. | A time-bounded artifact-only shadow experiment; never competing production writers. | H12; S5. |

## 9. Row #8 - Expose and test the independent memory off control

- **Scope:** Expose AN's already built Rust memory control through validated per-run/per-pipeline configuration, CLI and YAML before adoption, with every affected producer and memory-dependent consumer tested.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/observability.py`
  - `config/idhazh.json`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/telemetry/host_event_client.py`
  - `backend/idhazh/telemetry/job_machine.py`
  - `backend/rust/host-telemetry/src/config.rs`
  - `backend/rust/host-telemetry/src/cli.rs`
  - `backend/rust/host-telemetry/src/producers/job_samples.rs`
  - `backend/rust/host-telemetry/src/monitor/session.rs`
  - `backend/rust/host-telemetry/src/sampling/process.rs`
  - `backend/rust/host-telemetry/src/sampling/machine.rs`
  - `.github/workflows/digest.yml`
  - `.github/workflows/measure.yml`
  - `.github/workflows/encoder-comparison.yml`
  - `.github/workflows/idhazh-gardener.yml`
  - `.github/workflows/llm-council.yml`
  - `.github/workflows/rust-host-telemetry.yml`
  - `.github/actions/model-server/action.yml`
  - `backend/utilities/runtime_sweep.py`
  - `backend/utilities/measure_llm.py`
  - `backend/tests/test_measure_llm.py`
  - `backend/tests/test_runtime_sweep.py`
  - `backend/tests/workflows/test_model_server_jobs.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/pipeline/test_work_host_events.py`
  - `backend/tests/test_host_event_resource_parity.py`
  - `backend/rust/host-telemetry/tests/windows.rs`
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/lib/server/machine-counters.ts`
  - `frontend/src/lib/charts/machine.ts`
  - `frontend/src/lib/console/machine/memory-held.ts`
  - `frontend/src/lib/components/MemoryBoard.svelte`
  - `frontend/src/lib/console/machine/MemoryHeldPanel.svelte`
  - `frontend/tests/console-memory-board.spec.ts`
  - `frontend/tests/console-memory-held.spec.ts`
  - `frontend/tests/memory-held.spec.ts`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `docs/reference/host-metrics.md`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Shared selector/Rust and focused frontend unavailable-memory tests; master host switch, copy jobs/floor, heartbeat zero and memory control independently and combined. Read-denying fixtures prove no memory-specific procfs/cgroup reads, RSS/fault extraction, sampler launch or stale-memory artifact reuse when off. CLI precedence, invalid strings, missing values and YAML propagation fail by name.
- **Acceptance gates - CI:** Full config/window/workflow suites; default-on reference parity; false keeps CPU/identity/census and fills optional memory cells with null rather than zero. Memory-dependent benchmark requests must report unavailable/refuse qualification rather than manufacture a zero peak.
- **Oracle:** Toggling the approved switch changes only the declared memory instruments/read activity while default on remains equivalent; it does not implement allocator profiling.

Table Y - Row 8 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| Y1 | AN alone declares the control/default/precedence and off paths. Rust builds it before isolated evidence; this row exposes it at every launcher before D16. CPU corrections are not ported into Python. | User memory decision; G3; AN. |
| Y2 | Keep F1 to F9 otherwise unchanged. Preserve independent heartbeat and separately controlled bandwidth. Memory consumers report unavailable or refuse memory-dependent qualification; no zeros, stale-artifact fallback or whole-census suppression. | Current control meanings; H11. |
| Y3 | State the knob's default, beneficiary and retirement condition where declared: remove only if memory collection is removed, with consumer impact approved. This is a capability control, not a permanent second implementation. | Guardrail #6; Fowler. |
| Y4 | Before cutover, exercising the enabled Rust path is artifact-only. A memory-off request on an inactive legacy production path must refuse BEFORE collection, not silently run Python memory reads. Default-on legacy production behaviour remains unchanged. After cutover the same control selects Rust memory-off without refusal. | AN; no promised post-adoption control fix. |
| Y5 | `machine.memoryBoard` currently filters items by memory presence before computing its load/busy series. Separate eligibility: memory-off retains CPU/load items with empty memory marks and unavailable qualification. A drawing scale/runner-size reference is not a measured memory total or proof that a larger model fits. `memoryHeld` may show no memory days, but must say unavailable rather than quiet/zero. | Direct memory-board/held consumer inspection; AN13. |

Table Z - Row 8 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Z1 | Treat heartbeat zero, tracing off or publishing off as memory off | Endpoint reads and/or underlying collection still run. | A real control with the read-activity and output tests in this row. | Table F; source predicates. |

## 10. Row #9 - Remove superseded collectors and temporary duplication

- **Scope:** After the approved historical rewrite and successful observed migrated families, delete superseded collectors and temporary wiring; if adoption is rejected, close the experiment by its separately recorded disposition instead.
- **Files touched:**
  - `backend/idhazh/telemetry/silicon.py`
  - `backend/idhazh/telemetry/host.py`
  - `backend/idhazh/telemetry/job_machine.py`
  - `backend/idhazh/contracts/host_fingerprint.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/contracts/knobs/observability.py`
  - `config/idhazh.json`
  - `backend/utilities/memory_sampler.py`
  - `backend/utilities/runtime_sweep.py`
  - `backend/utilities/model_runtime.py`
  - `backend/utilities/measure_judge_call.py`
  - `backend/tests/test_silicon.py`
  - `backend/tests/test_host_readings.py`
  - `backend/tests/test_memory_sampler.py`
  - `backend/tests/contracts/test_host_event_rust_parity.py`
  - `backend/tests/test_host_event_resource_parity.py`
  - `backend/tests/test_compare_host_telemetry.py`
  - `backend/tests/workflows/test_rust_host_telemetry_workflow.py`
  - `backend/tests/test_job_machine.py`
  - `backend/tests/test_model_runtime.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/contracts/test_machine_panels.py`
  - `backend/tests/conftest.py`
  - `backend/tests/workflows/test_bench_targets.py`
  - `backend/tests/workflows/test_plan_handoff.py`
  - `backend/tests/workflows/_harness.py`
  - `backend/idhazh/ledger/staging.py`
  - `docs/reference/host-metrics.md`
  - `docs/reference/models/ornith-1.5-9b-q5km.md`
  - `docs/architecture/publishing/telemetry-series.md`
  - `docs/architecture/publishing/host-events.md`
  - `docs/concepts/config/retention-ages.md`
  - `.github/workflows/rust-host-telemetry.yml`
  - `backend/utilities/compare_host_telemetry.py`
  - `backend/utilities/host_telemetry_workload.py`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Search each deleted symbol/path across code/tests/config/docs and update the exact list before dispatch. Preserve still-used helpers by naming their live callers, not deleting whole modules blindly. Distil current rules and repair all links.
- **Acceptance gates - CI:** Full suites; the retained independent fixture/contract tests cover Rust without requiring deleted collectors. Assert no temporary selector or competing old collector remains on migrated paths.
- **Oracle:** All migrated paths use one collector and one writer, and every deleted symbol has no live consumer; this cannot establish an unrelated helper is obsolete without its caller search.

Table AA - Row 9 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AA1 | Observation covers at least seven UTC days and every Table W family plus enabled/disabled controls; elapsed time alone does not satisfy coverage. D16 accepts this starting policy or records evidence-based changes. No obsolete collector is removed before its real caller coverage. | Fowler; bounded transition. |
| AA2 | Keep shared Python codecs/persistence, compact/history readers, AN legacy read migrations and other producers. Remove only superseded host collection/write paths and temporary shadow duplication. Keep Rust/module/cross-language fixture tests; keep the bounded maintenance utility if needed for resumability, not a recurring archive rewriter. | User; H12; caller search. |
| AA3 | Rollback restores cleanup before cutover while retaining migrated readers. If not adopted, do not start D17; retain unchanged Python measurement behaviour and record the user's disposition of candidates/adapters and additive experiment files. | Fowler; reversible changes. |
| AA4 | Delete this plan after distillation and closure; do not keep completed migration history in TODO or create a second tracking page. | [distill-a-plan.md](../docs/how-to/distill-a-plan.md). |

Table AB - Row 9 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AB1 | Keep both collectors and a selector indefinitely | Doubles maintenance and leaves ambiguous ownership after the experiment ends. | A new named consumer and approved permanent dual-implementation contract. | Fowler; user replacement intent. |

## 11. Row #10 - Render compatible host files through tested Rust codecs

- **Scope:** Ship AN's corrected Rust contract/schema/config and canonical codecs with individual tests, producing real native bytes without filesystem persistence or host observations.
- **Files touched:**
  - `backend/rust/host-telemetry/Cargo.toml`
  - `backend/rust/host-telemetry/Cargo.lock`
  - `backend/rust/host-telemetry/rust-toolchain.toml`
  - `backend/rust/host-telemetry/src/bin/codec-fixture.rs`
  - `backend/rust/host-telemetry/src/lib.rs`
  - `backend/rust/host-telemetry/src/contracts/host.rs`
  - `backend/rust/host-telemetry/src/contracts/events.rs`
  - `backend/rust/host-telemetry/src/contracts/file_envelope.rs`
  - `backend/rust/host-telemetry/src/contracts/write_plan.rs`
  - `backend/rust/host-telemetry/src/config.rs`
  - `backend/rust/host-telemetry/src/canonical_json.rs`
  - `backend/rust/host-telemetry/src/ledger/schema.rs`
  - `backend/rust/host-telemetry/src/codec/parquet.rs`
  - `backend/rust/host-telemetry/src/codec/jsonl.rs`
  - `backend/rust/host-telemetry/tests/contracts.rs`
  - `backend/rust/host-telemetry/tests/config.rs`
  - `backend/rust/host-telemetry/tests/schema.rs`
  - `backend/rust/host-telemetry/tests/canonical_json.rs`
  - `backend/rust/host-telemetry/tests/parquet.rs`
  - `backend/rust/host-telemetry/tests/jsonl.rs`
  - `backend/tests/contracts/test_rust_host_file_parity.py`
  - `tests/fixtures/host-events/file-parity.json`
  - `.github/workflows/ci.yml`
  - `frontend/scripts/test-scope.ts`
  - `frontend/scripts/run-checks.ts`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `frontend/scripts/tests/run-checks.test.mjs`
  - `docs/how-to/run-the-gates.md`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Cargo fmt/clippy/test for each module; selected Python tests consume actual Rust codec bytes. Compare declared field/type/vocabulary sets, canonical JSON/hash vectors, schemas, footer metadata and all configured raw codecs. New selector preparation builds the crate before parity tests; no missing-binary skip.
- **Acceptance gates - CI:** Locked, pinned Rust preparation followed by offline Cargo/module and Python container/contract tests. Reference Python codecs read the actual Rust files using the candidate envelope validator; full current-reader acceptance remains Row 13.
- **Oracle:** Rust-rendered files decode to matching host/identity rows and exact canonical hashes under equivalent schemas, with truthful native provenance; this cannot establish atomic persistence or collection timing.

### Module responsibilities and tests

Table AC - one crate with narrow modules

| ID | Rust module, under `src/` | Question it owns; Python reference | Module-specific real fixture tests | Implementing row |
| --- | --- | --- | --- | --- |
| AC1 | `contracts/host.rs`, `contracts/events.rs`, `contracts/file_envelope.rs`, `contracts/write_plan.rs` | What typed values cross boundaries? AN/AO's corrected row, existing row identity and H1 to H16. No collectors, clocks or engines. | `contracts.rs`: candidate field/type parity, defaults/nulls, schema versus hash versions and invalid identities. | 10 |
| AC2 | `config.rs` | Which finite format/compression/collection/transport settings apply? Include AN's memory control from the first build. | `config.rs`: nondefault values, disable combinations, invalid/unsupported settings and read bounds. | 10; 8 exposes launchers |
| AC3 | `ledger/schema.rs` | Which ordered logical columns exist? [arrow_schema.py](../backend/idhazh/ledger/arrow_schema.py) and `persist.file_columns`: host fields first, only missing identity fields appended. | `schema.rs`: field order/type/nullability, empty-row schema, no duplicate identity names. Declare only types consumed by this port; refuse unsupported shapes explicitly. | 10 |
| AC4 | `canonical_json.rs` | Which bytes define content identity? [json_lines.py](../backend/idhazh/ledger/json_lines.py), `row_line`/`rows_bytes`. No clock or file I/O. | `canonical_json.rs`: sorted keys, LF, ASCII escapes including non-BMP Unicode, floats/exponents/negative zero, nulls and exact SHA-256 vectors. | 10 |
| AC5 | `codec/parquet.rs` | How do logical columns/rows/metadata become Parquet bytes and return? [parquet.py](../backend/idhazh/ledger/parquet.py). This module alone imports native Arrow/Parquet engine types. | `parquet.rs`: real files, schema/nullability, empty batches, metadata/statistics, compression, corruption refusal and cross-engine decode. | 10 |
| AC6 | `codec/jsonl.rs` | How does configured JSONL output encode/decode? Existing JSONL envelope-first representation; reuse AC4 canonical bytes. | `jsonl.rs`: first-line envelope, row ordering, exact canonical lines, malformed/truncated input. | 10 |
| AC7 | `ledger/identity.rs`, `ledger/filenames.rs` | What identity and raw-file name belong to one write? `WriterIdentity` and [filenames.py](../backend/idhazh/ledger/filenames.py). No clocks or directories read here. | `identity.rs`, `filenames.rs`: exact UUID5/UUID8 vectors, highest attempts, real millisecond ordering/collisions. | 11 |
| AC8 | `ledger/paths.rs` | Where may a declared raw host file go? [paths.py](../backend/idhazh/ledger/paths.py) and its registry prefixes. No observations, codecs or permission granted by a receipt. | `paths.rs`: generated roots, nested/trial prefixes, day/tier rules, traversal, escaping symlink/junction cases. | 11 |
| AC9 | `fs/atomic.rs` | How does one file become visible whole? [atomic_write.py](../backend/idhazh/atomic_write.py), destination-local temp then rename. No ledger naming or schema logic. | `atomic.rs`: whole-file visibility, real rename failure, preserved old file and scoped temp cleanup. | 11 |
| AC10 | `ledger/envelope.rs` | Which footer/header metadata describes these rows and this native writer? `persist._envelope` plus `FileEnvelope`. | `envelope.rs`: exact fields/optional keys, canonical versus physical hashes, truthful writer/version, day/identity contradictions. | 11 |
| AC11 | `ledger/store.rs` | How are validated raw host rows planned, rendered and atomically filed? [persist.py](../backend/idhazh/ledger/persist.py). Coordinates AC3 to AC10; never reads host procfs or imports producer code. | `store.rs`: empty batch, paused/retired gate, bad third day, preserved row identities, partial I/O failure and conflicting destination. | 11 |
| AC12 | `receipts.rs` | Which exact completed bytes are evidenced, and how is an interrupted write recovered? `PublicationReceipt`, publisher evidence and H15. | `receipts.rs`: physical hashes, stale/forged evidence, planned-path membership, crash-point recovery and logical idempotence. | 12 |
| AC13 | `producers/job_probe.rs`, `producers/target_probe.rs`, `producers/job_clock.rs` | Which corrected whole row does the job produce? Early probe, AN target enrichment and late clock share the store/unit; producers build no paths/envelopes. | `job_producers.rs`: real whole files, absent target/clock, identity continuity, duplicate events and receipts. | 3 |
| AC14 | `fingerprint.rs` | Which static hardware facts define AO algorithm 2? Legacy algorithm 1 is a read/test reference, not new Rust emission. Use AC4. | `fingerprint.rs`: exact versioned vectors, Unicode/nulls and affinity/quota/frequency invariance. | 3 |
| AC15 | `probe_inputs/cpu.rs`, `probe_inputs/topology.rs`, `probe_inputs/allowance.rs`, `probe_inputs/frequency.rs`, `probe_inputs/placement.rs`, `probe_inputs/bandwidth.rs` | How is each AN one-shot observation obtained? Separate topology, target allowance and frequency from orchestration/persistence; preserve placement/copy meaning. | `probe_inputs.rs`, `cpu_measurements.rs`: independent captured OS edge cases, stable snapshots, units, bounded sources and non-elidable copies. | 3 |
| AC16 | `sampling/process.rs`, `sampling/machine.rs` | What process/machine readings exist now? Existing host and memory-sampler readers; verify target identity. | `process_sampling.rs`, `machine_sampling.rs`: generated proc trees, units, exit/reuse, permissions and exact selected populations. | 4 |
| AC17 | `windows/reduce.rs`, `monitor/session.rs` | How do samples become independent lifecycle results? `Watch` reductions and approved window events; sampling and event routing are distinct. | `windows.rs`, `process_lifecycle.rs`: endpoints, means/extrema, overlap, abort, cadence and shutdown; unit reductions need no monitor process. | 4 |
| AC18 | `transport/files.rs`, `transport/bounds.rs` | How are bounded immutable messages transferred? H8 to H14. Reuse AC9 publication; transport does not reinterpret ledger files. | `transport.rs`: size/capacity, duplicate/conflict, order, ACK/readiness and escaping roots. | 4 |
| AC19 | `producers/job_samples.rs` | Which legacy sample/rollcall artifacts are emitted from approved observations? Existing job sampler; share sampling/reduction and atomic helpers. | `job_samples.rs`: sample-record/rollcall shape, cadence, totals and unchanged artifact consumers. | 4 |
| AC20 | `cli.rs`, `main.rs`, `lib.rs` | Which command routes to which real producer/monitor? Existing CLI convention; main is routing only, lib declares/reexports modules only. | `cli.rs`: real subprocess commands, generated roots, bad input and exit-code propagation. No implementation logic asserted by CLI-only tests. | 3; 4 extends routes |

Table AD - dependency boundaries

| ID | Rule | Enforcement |
| --- | --- | --- |
| AD1 | Contracts/config/logical schema at the bottom; canonical serializer shared by codecs and identity checks; atomic I/O independent of host observations. | Module tests plus a bounded source-boundary check over the named module files. |
| AD2 | Store -> schemas/identity/envelope/paths/codecs/atomic; producers -> observations/contracts/store; CLI -> producers/monitor. Never store -> producers or codec -> filesystem. | Refuse direct Arrow/Parquet imports outside AC5 and forbidden reverse dependencies. Keep tests at each seam; normal Rust calls inside the crate are allowed. |
| AD3 | Monitor -> sampling/reduction/transport; legacy sample producer reuses those components. It does not turn resource cells into a second item-health ledger. | Snapshot/window tests and complete-health integration tests. |
| AD4 | Create a module only when its real code and named tests land; a router contains dispatch only. No file-length quota substitutes for a single-question boundary. | Review each module's first sentence and test ownership before merge. |

### File compatibility and persistence rules

Table AE - output contract to freeze

| ID | Property | Required behaviour and source |
| --- | --- | --- |
| AE1 | Measurement schema | AN replaces legacy CPU columns in the new schema; AO versions fingerprints. Small native Rust models compare to the candidate corrected schema, then shared contracts. Unchanged fields keep their existing units/defaults; no runtime Python schema exporter. |
| AE2 | Physical versus logical equality | Equal declared canonical bytes produce equal digests; equal AO preimages produce equal fingerprints; equal identity seeds/clocks produce equal UUIDs. Different corrected/legacy serialized rows are NOT forced to match digests or files. Native Parquet bytes may differ from PyArrow; validate logical types/order/nullability, values and truthful engine metadata. Physical receipt hashes cover the actual whole file. |
| AE3 | Provenance migration | Current `FileEnvelope.writer` permits Python-style names and `persist._opened` additionally requires the exact Python codec name. Do not forge those names. H16 declares truthful candidates; isolated decoding uses existing container adapters plus prospective envelope validation. Row 13 expands explicit writer/container pairs and version handling, then tests unchanged `load`/`load_stored` calls against the same Rust files. |
| AE4 | Configured formats | Support the current `parquet` and `json` setting, raw compression choices and declared host prefix. JSONL stays envelope-first ASCII canonical rows. Unsupported settings fail by name, never silently fall back. Compact files/indices remain Python-owned; no unused Rust compact writer. |
| AE5 | Identity | AO declares the exact namespace/preimages/UUID bits and path grammar once. Logical producer identity is separate from native codec provenance. Validate rank/day/identity contradictions before writing; unchanged algorithms do not mean byte-identical old/new output. |
| AE6 | Probe/target/clock ordering | Whole-row enrichment shares unit/attempt. Different content needs a strictly later actual epoch millisecond than previous output; bounded wait or refusal, never synthetic time or a filename nonce. Identical retries keep the immutable plan. Original probe/target capture times do not become file-write clocks. |
| AE7 | Raw lifecycle gate | Mirror the actual `persist` predicate: paused/retired raw families accept no new rows regardless of the job label. The documentation's maintenance exception is not present in the raw writer predicate; do not import it into Rust. Compact/history maintenance remains the existing Python consumer's responsibility. |
| AE8 | Failure boundary | Validate/render every day group before the first target write; an invalid third day leaves no earlier files. Atomic publication is per file, not a multi-file transaction; later I/O failure may leave earlier completed files, all included in recovery evidence. No power-loss durability promise is implied. |
| AE9 | Collision and recovery | Plan exact IDs/paths/timestamps and expected canonical hashes before target publication; emit completion afterward. Verify only planned files and actual bytes/envelopes/rows on recovery. Same path/ID with different content is a diagnosed conflict, not overwrite or success. Evidence loss must not omit an earlier completed file. |
| AE10 | Publisher verification | Existing receipts are evidence, never authority. Verify invocation run/attempt/job/shard/git revision, logical producer/unit, declared output roots and physical-byte hashes; independently retain existing publication permissions. The verifier cannot turn arbitrary files into authorized writes. |

Table AF - Row 10 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AF1 | Table AC is a required module/test map, not an empty scaffold. Keep Arrow/Parquet crate APIs confined to its codec and choose maintained native crates with locked versions and documented beneficiary/build/binary costs. | User; Fowler; Python codec boundary. |
| AF2 | Move routine Rust toolchain/preparation/selection here, its first implementation row. Add focused Cargo and cross-language fixture checks before a test requires a binary. | Tests ship with each module; existing CI/selector. |
| AF3 | Build both configured codecs; use the explicit host logical schema, not infer from the first row or scan repository contracts at runtime. | Current `file_columns`/Arrow rules; AE4. |

Table AG - Row 10 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AG1 | One `main.rs`/`events.rs` containing codecs, I/O, observations and dispatch | Hides seams and makes per-module tests and engine swaps costly. | An approved change of modularity intent; no technical reason requires it. | User. |
| AG2 | Demand byte-identical PyArrow and native Parquet output | Physical encoding and engine metadata legitimately differ. | Pin/replicate engine encoding instead of native Rust; logical compatibility and truthful provenance are the useful gate. | Existing `writer_version` meaning; Fowler. |

## 12. Row #11 - Persist host files through tested Rust storage modules

- **Scope:** Ship the identity/path/envelope/atomic/store modules using the real codecs, with raw-host-only persistence and exact failure/identity tests.
- **Files touched:**
  - `backend/rust/host-telemetry/src/lib.rs`
  - `backend/rust/host-telemetry/src/contracts/host.rs` (forward existing UUID helpers to the single identity implementation)
  - `backend/rust/host-telemetry/src/bin/storage-fixture.rs` (real stored-file cross-language fixture consumer)
  - `backend/rust/host-telemetry/src/ledger/identity.rs`
  - `backend/rust/host-telemetry/src/ledger/filenames.rs`
  - `backend/rust/host-telemetry/src/ledger/paths.rs`
  - `backend/rust/host-telemetry/src/ledger/envelope.rs`
  - `backend/rust/host-telemetry/src/ledger/store.rs`
  - `backend/rust/host-telemetry/src/fs/atomic.rs`
  - `backend/rust/host-telemetry/tests/identity.rs`
  - `backend/rust/host-telemetry/tests/filenames.rs`
  - `backend/rust/host-telemetry/tests/paths.rs`
  - `backend/rust/host-telemetry/tests/envelope.rs`
  - `backend/rust/host-telemetry/tests/atomic.rs`
  - `backend/rust/host-telemetry/tests/store.rs`
  - `backend/tests/test_rust_host_store_parity.py`
  - `tests/fixtures/host-events/storage-parity.json`
  - `frontend/scripts/test-scope.ts`
  - `frontend/scripts/run-checks.ts`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `frontend/scripts/tests/run-checks.test.mjs`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Each listed module's Cargo tests and selected Python fixture parity; create actual files in generated roots. Cover empty/multiple-day input, invalid last group, identity collisions, wrong root, paused families, file conflicts, rename failures and partial completion.
- **Acceptance gates - CI:** Linux atomic-write/visibility/lifecycle tests and native-codec/current-container cross-read; each completed file's schema/content/identity validates. Match platform-specific cleanup limits explicitly rather than claiming Windows tests establish Linux semantics.
- **Oracle:** Persisting declared rows writes only complete correctly identified files at planned paths, refuses invalid batches before any write and exposes partial I/O completion; it cannot establish producer measurements or publication authority.

Table AH - Row 11 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AH1 | Implement AC7 to AC11 and AE4 to AE9; the store coordinates lower modules without importing host or producer logic. | User; verified Python separation. |
| AH2 | Raw-host output is the concrete storage consumer. Do not port compact/index/retention engines simply to resemble the Python directory tree. Existing compaction must later read Rust raw files. | A2/B1; Fowler. |
| AH3 | The basic atomic module owns whole-file visibility; the store owns immutable raw-file collision/plan rules. Tests cover both without broad catches or silently overwritten conflicts. | AE8/AE9. |

Table AI - Row 11 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AI1 | A producer constructs filenames or calls a Parquet engine directly | Duplicates identity/path rules and bypasses schema/lifecycle/atomic safeguards. | Demonstrate a store contract that cannot serve that producer and revise it; bypassing it is not the fix. | Python ledger door; user modularity. |

## 13. Row #12 - Produce verified receipts and recover completed writes

- **Scope:** Ship Rust completed-file receipts and restart recovery, with a read-only Python consumer compatible with the existing publisher's independent permissions.
- **Files touched:**
  - `backend/rust/host-telemetry/src/lib.rs`
  - `backend/rust/host-telemetry/src/receipts.rs`
  - `backend/rust/host-telemetry/src/contracts/host.rs`
  - `backend/rust/host-telemetry/src/contracts/patterns.rs` (bounded unchanged-predicate compilation, Fowler)
  - `backend/rust/host-telemetry/src/bin/receipts-fixture.rs`
  - `backend/rust/host-telemetry/src/ledger/store.rs`
  - `backend/rust/host-telemetry/src/ledger/paths.rs`
  - `backend/rust/host-telemetry/tests/receipts.rs`
  - `backend/idhazh/telemetry/host_output_verify.py`
  - `backend/utilities/verify_host_output.py`
  - `backend/tests/test_host_output_verify.py`
  - `backend/tests/test_rust_host_receipts.py`
  - `tests/fixtures/host-events/publication-parity.json`
  - `frontend/scripts/test-scope.ts`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `frontend/scripts/tests/run-checks.test.mjs`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Rust receipt/recovery tests and selected Python read-only/publisher-boundary tests. Verify forged/stale/foreign receipts, canonical-versus-physical hashes, publication-between-receipts failure and immutable retry plan.
- **Acceptance gates - CI:** Real subprocess interruption at named filesystem stages followed by bounded recovery; no ledger modification by the Python verifier. Exercise existing publisher byte/identity/scope validation against generated output without publishing.
- **Oracle:** Every completed planned file is evidenced once logically and checked independently against actual bytes and permissions, including after interruption; it cannot promise a multi-file transaction or perform a production commit.

Table AJ - Row 12 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AJ1 | Rust records completed host-file evidence; Python may translate/retain invocation evidence under its existing transient receipt directory, but never rewrites a host target. | H12/H15; [publication_evidence.py](../backend/utilities/publication_evidence.py). |
| AJ2 | Use the existing `PublicationReceipt` field set. Wrapper invocation identity and raw logical producer identity differ intentionally; verify both, never conflate them or grant scope from receipt contents. | [PublicationReceipt](../backend/idhazh/contracts/publication_receipt.py); current publisher predicates. |
| AJ3 | Recovery names only immutable planned paths and checks footer/row/physical hashes. A completed file with missing receipt is recoverable evidence, not permission to adopt an unrelated file from a day directory. | AE9/AE10. |

Table AK - Row 12 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AK1 | A Python persistence wrapper manufactures the final files or hashes substitute canonical content for physical bytes | Does not test Rust persistence and bypasses existing publisher byte checks. | Change the requested ownership and publisher contract explicitly; this port uses Rust files as produced. | User; AE2. |

## 14. Row #13 - Migrate shared schemas and readers before writers

- **Scope:** After isolated evidence, land AN's replacement shared schema with legacy input/read migration and H16's strict provenance mapping before production writer cutover, without changing Python CPU collectors.
- **Files touched:**
  - `backend/idhazh/contracts/file_envelope.py`
  - `backend/idhazh/contracts/host_fingerprint.py`
  - `backend/idhazh/contracts/host_output.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/ledger/persist.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/ledger/ledger_files.py`
  - `backend/utilities/migrate_host_fingerprints.py`
  - `backend/tests/ledger/test_persist.py`
  - `backend/tests/ledger/test_arrow_schema.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/test_host_fingerprint_migration.py`
  - `backend/tests/test_host_fingerprint_migration.py`
  - `backend/tests/contracts/test_host_output.py`
  - `backend/tests/contracts/test_rust_host_file_parity.py`
  - `backend/tests/test_rust_host_reader_compatibility.py`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/reference/host-metrics.md`
  - `docs/architecture/publishing/host-events.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** A11's separate implementation instruction is required; D1 settles design only, without another design-confirmation gate. Selected schema/Arrow/CSV/reader tests read exact Row 5 native files through `load`/`load_stored`, footer/raw settlement and generated compaction. Legacy files/unchanged Python constructors normalize through AN without invented counts. Verify original digests before normalization; mixed/unknown schemas and writer/container mismatches fail.
- **Acceptance gates - CI:** Full contract/ledger suites, native/Python cross-read fixtures, metadata/footer and projected CSV/frontend comparisons. Test `render_renamed`: a file re-rendered by Python must record Python's actual writer/version, preserving original row identity but not false codec provenance.
- **Oracle:** Existing ledger APIs and compaction correctly consume both older Python and approved Rust host files, while rejecting unknown writers or mismatched containers; this does not authorize production Rust emission before Row 7.

Table AL - Row 13 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AL1 | Install AN/AO and H16 together: newest-first date changelogs, input/read migration and finite writer/container/schema/tier pairs. Rust/raw is host-only; existing Python writer/other-ledger behaviour stays. No catch-all native writer regex, unknown columns or fake source measurements. | D1; C2/C8; section 11. |
| AL2 | Keep container detection based on file bytes; separately validate producer provenance against the approved finite container-writer pairs. Existing native `created_by`/`writer_version` remain truthful. | `parquet.read`, `persist._opened`; AE3. |
| AL3 | Isolated evidence leaves public models/readers unchanged. Here consolidate candidates into shared corrected/legacy contracts, update verifier/maintenance imports, and remove candidate overrides. Preserve old canonical digest checking and legacy constructor support for unchanged Python collectors; normalized output uses the corrected shape with version-1 hashes and unknown corrected counts. | H13/H16; AN; reader-before-writer. |
| AL4 | Preserve shared codecs/persistence used by other producers. Fix only the writer-name assumptions tightly coupled to consuming the port's files; re-run the exact caller search before dispatch. | C5; B1. |
| AL5 | Rows 13/14 ship together: schema removal, its read migration, frontend hand-copy and actual consumers share one behavioural compatibility risk. One owner applies both; run combined gates before merge and mark both DONE in that change. Candidate consolidation/dead-code refactoring is a separate structural commit, not mixed into the schema change. | Fowler; section 11 and two-hat discipline. |

Table AM - Row 13 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AM1 | Claim `idhazh.ledger.parquet` in Rust output so unchanged `_opened` accepts it | False provenance; the footer would attribute native Rust bytes to a Python module. | Explicit truthful provenance mapping/reader expansion as this row, not forged metadata. | C8; user real Rust output intent. |
| AM2 | Drop writer/container checking altogether | Loses an existing file-boundary refusal. | Demonstrate and approve a replacement finite validation rule; AL2 already supplies one. | Current envelope/read contract. |

### Single corrected measurement and control declaration

Table AN - target schema, sources, nulls and snapshot rules

| ID | Surface | Settled declaration |
| --- | --- | --- |
| AN1 | Versions and shape | Target host-row, event and envelope schema stamps are `2026-10-10`, not fingerprint algorithm numbers. Declare candidates in Row 2, native models in Row 10 and shared contracts in Row 13, with changelogs. A later schema date updates this declaration/fixtures before emission; unchanged semantics need no new design decision. New output removes `cores`, `threads`, `mhz_max`, `mhz_at_probe`. Keep baseline field order otherwise; insert nullable `fingerprint_version` after fingerprint, replace old counts with AN2 to AN6 then `cpu_target_measured_at`, and replace old frequencies with AN7 then AN8. Added nullable fields default to null; baseline defaults stay. JSON Schema is computed on demand, not checked in. |
| AN2 | `cpu_physical_cores` | Nullable int64, >= 1. Count unique `(physical_package_id, core_id)` pairs for ALL validated OS-visible ONLINE CPU IDs from each ID's sysfs `topology` files. Require nonnegative IDs, complete coverage and consistent sibling/package/core relationships. Missing, duplicate-conflicting or partial topology -> null with reason; never take first-CPU `cpu cores`, product-page counts or frequency cardinality. This is visible online topology, not promised bare-metal silicon capacity. |
| AN3 | `cpu_logical_processors` | Nullable int64, >= 1. Cardinality of the validated cpulist in `/sys/devices/system/cpu/online`, independent of frequency availability. Parse sparse ranges with checked bounds and no duplicate/overlapping IDs; verify IDs belong to the visible CPU inventory. Missing/malformed/changed online set -> null; never count MHz entries, use a process's cpuset or infer from physical cores. |
| AN4 | `cpu_allowed_processors` | Nullable int64, >= 1. At the target-capture instant, count ONLINE IDs intersected with `sched_getaffinity(target_pid)` and its effective cpuset. Resolve the target's `/proc/<pid>/cgroup` and `/proc/<pid>/mountinfo`, mount roots and namespaces; v2 uses `cpuset.cpus.effective`, v1 intersects nonempty inherited `cpuset.cpus` through visible ancestors. No cpuset controller is a verified unrestricted cpuset, not a missing file guessed unrestricted. Missing effective scope, hidden constraints, conflicting masks or an empty intersection -> null with reason. Never use the Rust monitor's mask or a requested server thread count. |
| AN5 | `cpu_quota_cores` | Nullable finite float64, > 0. Resolve the SAME target's CPU controller. v2 parses `cpu.max` (`max <positive period>` or positive quota/period); v1 parses `cpu.cfs_quota_us` (`-1` unlimited) and positive `cpu.cfs_period_us`. Effective allowance is the minimum finite quota/period across the complete visible ancestry, including hybrid controllers where both apply. Do not round fractional cores or clamp this field to affinity; it is a separate constraint. Missing/malformed/permission-denied/namespace-hidden ancestry -> null, not unlimited. All verified ancestors unlimited/no applicable controller -> null with AN6 unlimited. |
| AN6 | `cpu_quota_state` | Nullable string with finite vocabulary `finite`, `unlimited`, `unavailable`. `finite` iff AN5 is present; other states require null AN5. `unavailable` is an attempted but unreadable/missing target constraint; null state means no target measurement (including migrated history). This companion makes unlimited different from unknown without infinity, zero or duplicate numeric fields. |
| AN7 | `cpu_observed_mhz` | Nullable finite float64, > 0. Arithmetic mean of valid positive finite `cpu MHz` values associated with unique ONLINE processor IDs in one captured `/proc/cpuinfo`. Missing/invalid readings do not become zero; no valid values -> null. Partial valid frequency coverage may produce a mean, with valid/online counts in typed H5 diagnostics. Duplicate processor records or a changed online snapshot invalidate the frequency reading. It is an observed sample, never advertised or sustained-load frequency and never a processor-count source. |
| AN8 | `cpu_reported_max_mhz` | Nullable finite float64, > 0. Maximum of reported hardware `cpuinfo_max_freq` in each sysfs cpufreq policy covering ALL online CPUs, converted from kHz by division by 1000. Validate policy CPU membership, full coverage, values and overlaps. No driver/full reported source -> null with reason. Do not use observed `cpu MHz`, `scaling_cur_freq`, `scaling_max_freq`, the sample maximum or nominal marketing frequency as a replacement. |
| AN9 | Target and capture times | For server work/runtime jobs target is the actual selected model server; without a server it is the actual profiled Python stage/job worker. Operator/YAML supplies PID/start ticks; E19 memory population stays separate. Affinity is that selected Linux task's mask at capture, not an aggregate over unrelated threads/workers. Early probe without a target emits null AN4/AN5/AN6. First registered target's `host.target` enriches the whole row under the same unit/attempt, recording nullable UTC `cpu_target_measured_at` and AN4 to AN6 only. Freeze that labelled capture rather than silently refreshing it on each window/restart; conflicting shard targets fault. Preserve original `measured_at` machine/frequency instant and AO hash; never infer future affinity from YAML flags. Clock only fills baseline clock cells. |
| AN10 | Snapshot validity | Bracket online IDs and target start ticks/cgroup/masks and ancestor constraints before/after reads; retry at most once, then null affected fields with `snapshot_changed`. AN2 cannot exceed AN3; AN4 cannot exceed the matching snapshot's logical count. Retain original online IDs in typed H5 source evidence so target enrichment can compare snapshots; if that evidence is unavailable or changed, null AN4 rather than match it to the earlier count. Target quota may remain independently valid. Sequential reads are not kernel-atomic. Missing topology/target never erases independent facts. J3 supplies bounds. Reject Boolean/string numbers, count fractions, NaN/infinity, overflow, invalid states and contradictions. |
| AN11 | Legacy input/read migration | Recognize declared pre-AN schemas and the exact unstamped constructor shape emitted by unchanged `silicon.py`, BEFORE base auto-stamping. Validate original file digests/identity first. Normalize row version to AN1, remove old keys, preserve v1 hash and unchanged cells. Copy only legitimate finite positive historical `mhz_at_probe` averages; never turn old maximum/core/thread values into corrected readings. Unmeasured counts/allowance/reported maximum/target time stay null. Reject unknown/mixed input rather than dropping arbitrary fields. Keep source versions/discarded values in the maintenance manifest. While `silicon.file_machine_row` still logs `row.mhz_at_probe`, provide ONLY a temporary read-only legacy getter in the input adapter; it is not a model field or JSON Schema/Arrow/CSV column and has no new consumer. Remove it with the legacy producer in Row 9. |
| AN12 | Memory control and precedence | Declare `observability.memory_profiling_enabled = true` once in shared configuration; it means OS memory/fault collection, not allocator profiling. CLI `--memory-profiling on` or `off` overrides loaded config for that invocation. YAML dispatch input uses `inherit`, `on`, `off`; inherit omits the CLI override. Resolve one Boolean before any instrument starts and propagate it in typed events and effective-config evidence, including per-run scratch configs and all downstream sweep workers. No environment-only alternate key or truthy-string interpretation. |
| AN13 | Memory-off paths | False skips E16 to E20's process/machine RSS/anonymous/HWM, major-fault and RAM/swap/commit collection, periodic and endpoint reads, job rollcall/sample artifacts, runtime RSS thread and applicable `measure_llm` memory events/peak capture. CPU/load reads, `/proc/<pid>/stat` start-tick identity checks, cgroup CPU quota/cpuset, UTC timing, heartbeat and mandatory item census remain. Emit null optional memory/fault cells and typed `disabled`; absent artifacts are explained, never stale/zero memory. Memory-dependent qualification refuses or reports unavailable; CPU/timing-only reporting can still run. Synthetic bandwidth retains F2/F3's separate controls and may allocate/copy when memory collection is off. |

Table AO - fingerprint and ledger identity declaration

| ID | Identity | Exact rule and evidence |
| --- | --- | --- |
| AO1 | Fingerprint algorithm 1 | Nullable integer `fingerprint_version` accepts only 1 or 2 and is null iff fingerprint is null. Historical hashes use 1; missing hashes get no algorithm label or synthetic digest. Preserve the existing hash. Exact original keys: `cpu_vendor`, `cpu_family`, `cpu_model_number`, `cpu_stepping`, `cpu_model`, `cores`, `threads`, `l3_cache_bytes`, `flags`; every key is included, absent optional facts are JSON null (`silicon.fingerprint_of`). |
| AO2 | Fingerprint algorithm 2 | New Rust emits `fingerprint_version = 2` with exact keys `cpu_vendor`, `cpu_family`, `cpu_model_number`, `cpu_stepping`, `cpu_model`, `l3_cache_bytes`, `flags`: static OS-visible hardware-class facts. Exclude online counts/topology, affinity/cpuset/quota, both frequencies, microcode, placement, memory, timing and run/writer fields. The version is only a row label, not a hash-object key. Require at least one successfully sourced nonempty model/vendor, valid family/model-number/stepping, positive L3 size or nonempty watched flags; otherwise hash/version are null. Null values and empty default flags do not establish an identity. |
| AO3 | Fingerprint bytes | Both algorithms use compact JSON with lexicographically sorted ASCII keys, explicit nulls, `ensure_ascii=True`, no spaces and NO trailing LF for the fingerprint object. Strings retain exact decoded text, without Unicode normalization; watched flags keep baseline sorted space-joined spelling. SHA-256 of UTF-8 bytes, first 16 lowercase hex characters. These small vectors match Python `json.dumps(..., sort_keys=True, separators=(",", ":"))`, not serde defaults. |
| AO4 | Consumer identity | Group/cache/colour/compare by `(fingerprint_version, fingerprint)`, never the digest alone. Render algorithm labels for historical versus corrected classes. Version-1 and version-2 rows are not evidence of the same physical machine even if a digest/model label matches; no synthetic cross-version linkage. Date-stamped row/envelope schemas and integer fingerprint algorithms are separate concepts. |
| AO5 | UUID5 work unit | Preserve `filenames.NAMESPACE = uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")`. UUID5 name bytes are UTF-8 `ledger\|covers\|run_id\|job\|shard\|producer`, with ordinary decimal shard and lowercase enum values. Host ledger is `host-fingerprint`; logical producer is `telemetry.silicon` for probe/target/clock. No attempt, language name, fingerprint/schema version or clock enters the unit seed. Row key remains `date`, `run_id`, `job`, `shard` (`ledger/keys.py`). |
| AO6 | UUID8 filename | Source correction: this checkout's UUID8 filename is CLOCK/WORK-UNIT addressed, not payload-content addressed. Preserve `filenames.file_id`: SHA-256 over UTF-8 `<canonical lowercase unit UUID>\|<attempt decimal>\|<actual epoch ms decimal>`; `rand_a = big_endian(digest[0:2]) & (2^12-1)`, `rand_b = big_endian(digest[2:10]) & (2^62-1)`. Pack low 48 clock bits at bits 80+, version `8` at 76+, `rand_a` at 64+, RFC variant `10` at 62+, then `rand_b`. Equal seed/clock -> equal filename; different content requires a later actual clock under AE6, not overwrite or forced equality. Do not invent a payload-seeded algorithm. |
| AO7 | Content and physical digests | `content_sha256` is SHA-256 of stored rows INCLUDING identity cells as canonical sorted-key ASCII JSON lines, each with LF, in stored order (`json_lines.rows_bytes`). It reflects corrected payload and algorithm/schema labels; the envelope is excluded. Envelope records truthful native writer/engine metadata separately; physical receipt SHA-256 covers ALL actual encoded bytes, including envelope/engine metadata. None of these hashes is interchangeable with the fingerprint or UUID8 seed. |
| AO8 | Roots and paths | Production is the SAME `state/raw/host-fingerprint/<YYYY>/<MM>/<DD>/<file_id>.parquet` tree (`.json` for configured envelope-first JSONL), not Rust/job/shard folders. Job/shard distinguish units. Dates come from row UTC `date`; registry prefix is `["host-fingerprint"]`. Trial prefixes remain tier-first `state/raw/<trial segments>/host-fingerprint/...`. Experiment substitutes only its task-owned root, preserving relative tree/key grammar. Python compact paths stay `state/compact/<prefix>/<daily\|monthly\|yearly>/...`, with `index/<period>.json`. Sources: `paths.raw_path`, `compact_path`, `overlay_registry`, `config/ledgers.json`. |

## 15. Row #14 - Migrate contracted backend and frontend consumers

- **Scope:** Deliver the contracted backend/Arrow/CSV/index/publish and frontend reader, fleet, machine/page/card/canary migrations together with Row 13, without correcting legacy Python collectors.
- **Files touched:**
  - `backend/idhazh/contracts/host_fingerprint.py`
  - `backend/idhazh/contracts/machine_panels.py`
  - `backend/idhazh/ledger/persist.py`
  - `backend/idhazh/telemetry/publish/machine.py`
  - `backend/idhazh/telemetry/publish/console_band.py`
  - `backend/utilities/build_canary_day.py`
  - `backend/tests/ledger/_fixtures.py`
  - `backend/tests/ledger/test_arrow_schema.py`
  - `backend/tests/ledger/test_persist.py`
  - `backend/tests/ledger/test_raw_files.py`
  - `backend/tests/ledger/test_ledger_files.py`
  - `backend/tests/ledger/test_published_columns.py`
  - `backend/tests/contracts/test_column_readers.py`
  - `backend/tests/contracts/test_frontend_field_set.py`
  - `backend/tests/contracts/test_frontend_vocabularies.py`
  - `backend/tests/contracts/test_machine_join.py`
  - `backend/tests/contracts/test_machine_panels.py`
  - `backend/tests/contracts/test_ledger_index.py`
  - `backend/tests/contracts/test_ledger_door_fixture.py`
  - `backend/tests/test_console_payloads_producer.py`
  - `backend/tests/pipeline/test_publish_window.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/test_silicon.py`
  - `backend/tests/test_job_machine.py`
  - `tests/fixtures/contracts/host-fingerprint-row/a-machine-that-reported-nothing.json`
  - `tests/fixtures/contracts/host-fingerprint-row/every-reading-taken.json`
  - `tests/fixtures/contracts/host-fingerprint-row/the-clock-a-job-kept.json`
  - `frontend/src/lib/server/host-fingerprint.ts`
  - `frontend/src/lib/server/machine-counters.ts`
  - `frontend/src/lib/charts/fleet.ts`
  - `frontend/src/lib/charts/machine-colour.ts`
  - `frontend/src/lib/charts/machine-cards.ts`
  - `frontend/src/lib/charts/machine.ts`
  - `frontend/src/lib/charts/machine-split.ts`
  - `frontend/src/lib/console/machine/article-cost.ts`
  - `frontend/src/lib/console/machine/processor-lost.ts`
  - `frontend/src/lib/components/MachineCard.svelte`
  - `frontend/src/lib/components/ShardBoard.svelte`
  - `frontend/src/lib/components/MemoryBoard.svelte`
  - `frontend/src/lib/console/machine/MachineCardsPanel.svelte`
  - `frontend/src/lib/console/machine/FleetDots.svelte`
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte`
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/scripts/build-canary.mjs`
  - `frontend/tests/support/machine-rows.ts`
  - `frontend/tests/console-machine.spec.ts`
  - `frontend/tests/console-machine-data.spec.ts`
  - `frontend/tests/console-machine-page.spec.ts`
  - `frontend/tests/console-machine-cards.spec.ts`
  - `frontend/tests/console-machine-panels.spec.ts`
  - `frontend/tests/console-machine-split.spec.ts`
  - `frontend/tests/console-shard-board.spec.ts`
  - `frontend/tests/console-memory-board.spec.ts`
  - `frontend/tests/platform-mix.spec.ts`
  - `frontend/tests/console-article-cost.spec.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/ledger-rows.spec.ts`
  - `frontend/tests/ledger-ranges.spec.ts`
  - `docs/reference/host-metrics.md`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/architecture/publishing/telemetry-series.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Combined Rows 13/14 selector and focused backend contract/Arrow/CSV/compaction/publish tests, then selected frontend pure/browser tests and machine-route smoke against generated mixed-version/native fixtures. Every AN/AO column gets a real `COLUMN_READERS` beneficiary and hand-copy type/order test. Null history, missing/partial files, both algorithms, off memory and old Python constructor tests must pass without weakening them.
- **Acceptance gates - CI:** Full existing suites plus generated raw -> compact -> indexes -> disk/browser projection and canary pipelines. Read actual native Rust output; do not modify committed `state/` or `frontend/public/` to make tests pass. All shared-copy and consumer checks pass in the same merge as schema removal.
- **Oracle:** Every named consumer reads contracted corrected/legacy-normalized records, keeps algorithms distinct and surfaces unknown values instead of silently deriving wrong counts; this does not recover missing historical facts or authorize a historical write.

Table AP - Row 14 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AP1 | `host-fingerprint.ts` currently hand-copies fields/order and normalizes numbers; `machine-counters.ts` carries old cores; `fleet.ts` and `machine-colour.ts` group raw hashes; page/card/canary paths consume these. Move all to AN/AO together, with no new-schema legacy numeric aliases. Existing legacy shape is admitted only at the explicit versioned read boundary. | Direct caller/source inspection; Fowler. |
| AP2 | Whole-machine `/proc/stat` busy share stays whole-machine. `article-cost.ts` uses validated online logical processors, NOT affinity/quota, labelled host busy processor-seconds, not target CPU consumption. `machine.ts`/ShardBoard/MemoryBoard use online logical processors for load comparisons, not physical cores/quota; rename internal count properties and visible labels accordingly. Unknown counts withhold qualification. A load exceeding that denominator suggests pressure, not proof of CPU-only queuing: Linux load also includes uninterruptible tasks. | E15/AN; direct denominator callers. |
| AP3 | Cards/page draw all six corrected fields with units and unknown states, plus quota state/target time. Fleet identity includes algorithm version and never fuses v1/v2 by model name. Frequency is sample average versus reported maximum, never sustained rate. Historical v1 cards keep legitimate average and unknown corrected counts. | User corrections; AO4; named surfaces. |
| AP4 | Keep `MachineShardRow` publication grain/columns and item-health key unchanged; those folds use CPU model/clocks and nullable memory, not the removed host CPU columns. Update tightly coupled fold/query assumptions and test exact CSV headers, Arrow column order/nullability, identity retention and index rows/bytes/lost/set-aside markers. No broad generic-ledger rewrite. | `publish/machine.py`, `console_band.py`, `arrow_schema.py`, indexes. |
| AP5 | `slice-query.ts` already DESCRIBEs the union and projects absent columns as NULL; keep it. Each host read boundary requests finite legacy input columns plus corrected columns, and normalizes versions BEFORE consumers. Direct slice callers (cards, fleet, PlatformMixPanel) reuse that normalization too; otherwise historical averages/version labels disappear. No legacy columns in new files or generic query rewrite. Test `ledger-disk.ts` -> `slice-reader.ts` -> `slice-query.ts`; preserve the fixed legacy door corpus as legacy coverage, add generated corrected/native cases, and update current-canary selectors to corrected columns. | Direct `statementFor`/`rowsFor` and caller inspection; section 11. |
| AP6 | Rows 13/14 are one delivery, not parallel workers despite table hints. Keep all legacy Python collection algorithms unchanged; adapt their constructor/read shape and test expectations only. Source files that merely carry the ledger may need no edit if tests prove they derive the new shape; C5 records precise touched-list reductions/additions before dispatch. | Fowler; settled isolation/producer boundary. |
| AP7 | `machine-colour.machineKeys` currently links name-only rows to a unique digest, and `machine-split` passes shard-index -> bare hash maps. Replace that fallback with explicit versioned identity through every caller. Name-only rows remain an unknown/coarse group, never inferred v1/v2 members; a model string matching cannot establish continuity. | Direct resolver/split call sites; AO4. |

Table AQ - Row 14 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AQ1 | Only rename producer fields and leave cards/denominators/legacy normalization unchanged | Draws wrong capacity or loses old average/version labels, even when the query correctly returns absent columns as null. | Reader/consumer migration in the same delivery, as AP1 to AP5. | User; section 11. |
| AQ2 | Add old/new duplicate columns or recover corrected counts from old frequency cardinality | Conceals missing measurement and preserves misleading labels. | Separate approved meaning and actual historical source evidence; neither exists. | User; AN11. |

## 16. Row #15 - Build bounded historical inventory and dry-run migration

- **Scope:** Implement the one-off host-history migration planner and dry-run verifier against bounded manifests/generated fixtures before isolated evidence, without changing historical files.
- **Files touched:**
  - `backend/idhazh/contracts/host_migration.py`
  - `backend/utilities/migrate_host_fingerprints.py`
  - `backend/tests/contracts/test_host_migration.py`
  - `backend/tests/test_host_fingerprint_migration.py`
  - `tests/fixtures/host-events/history-migration.json`
  - `config/host-telemetry-experiment.json`
  - `.github/workflows/rust-host-telemetry.yml`
  - `docs/how-to/migrate-host-telemetry.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Generated raw/compact/JSONL/Parquet/index/view fixtures exercise AN11, v1 preservation, valid average retention and null unmeasured fields. Dry-run has read-only historical access and writes reports/candidates only under a declared isolated root. Reject unknown files/versions, source-hash drift, missing metadata, unsafe paths and inconsistent inventories; never silently skip them.
- **Acceptance gates - CI:** Named bounded dry-run fixtures before Row 5's verdict, including probe/clock duplicates, attempts, compact-only history, lost/empty periods, mixed legacy revisions, restart points and bad final batch. No test scans committed archives.
- **Oracle:** A fixed manifest yields a complete validated replacement/reconciliation report without altering source bytes; it cannot prove an unlisted historical file exists or authorize applying the report.

Table AR - Row 15 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AR1 | Inventory consumes an explicit operator range/root list and caps file count/bytes/periods per batch. Record exact source path, physical/canonical hashes, container, envelope/row versions, row/settled-key counts, original identities, compact dependencies/index entries and affected published view paths. Inventory production and declared trial roots separately, including present set-aside files as diagnosed unresolved sources. No unrestricted recursive corpus scan or recovery claim for already lost periods. | User historical rewrite decision; Guardrail #12. |
| AR2 | Default is dry-run. Candidate model/reader is Row 2's isolated AN model until Row 13 consolidates it. Use Python maintenance codecs only for HISTORICAL conversion; never re-encode new Rust files to pass compatibility tests. Report exact dropped legacy values and preserved legitimate average/hash/identity data. | AN11; H12; user maintenance boundary. |
| AR3 | Raw replacement preserves path/file_id, original allocation clock, unit/attempt/job/shard/covers/producer lineage and row rank, because AO6 does not hash payload. It is a one-time existing-file conversion, not normal `persist`. Restamp schemas, canonical digest and actual Python codec/engine; the original identity/git revision remains historical lineage, while the maintenance receipt/manifest records converting revision/time and original provenance/bytes. Preserve compact period paths/row identities and update footer digests/index rows/bytes without changing loss/set-aside/expiry markers. | Direct filename/persist/index predicates; no content-addressing assumption. |
| AR4 | Reconcile every manifested raw and compact physical file, INCLUDING superseded probe/attempt files; retain whole-row settlement/key cardinality, clocks and duplicates' ranking. Rebuild only affected bounded machine/console derived views with the migrated consumer code. Receipts containing rewritten paths acquire replacement physical hashes under a maintenance invocation; retain old invocation receipts as historical evidence in the migration bundle, never misrepresent them as current-byte proof. | User explicit raw/compact/metadata/keys/receipts/views requirement. |
| AR5 | Dry-run reports source/output hashes, original-versus-normalized identities/keys, all null mappings, retained averages, changed index/view bytes, source retirement/backup policy and estimated batch cost. Stop on ambiguous original provenance or unreconciled dependency. Present this exact manifest/report to D16; authorization is tied to its hash and scope. | Fowler; user later write approval. |
| AR6 | D15's initial fixture dry-run precedes D5. After the combined Rows 13/14 delivery, repeat the dry-run against actual migrated consumers to freeze view/receipt bytes and the bounded historical manifest before D16. Isolated evidence never calls an unimplemented future consumer or writes managed history. Use closed, explicitly inventoried periods; later files require fresh scope review, not automatic inclusion. | Execution dependencies; Fowler. |

Table AS - Row 15 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AS1 | Leave history migrate-on-read forever | Conflicts with the settled one-time replacement-schema rewrite. Read migration is a transition/safety net, not the final maintenance outcome. | Another explicit user decision; current plan includes D17. | User, 2026-10-10. |
| AS2 | Rewrite archives during evidence collection or infer missing topology/frequency from today's machine | Violates isolated evidence and invents history. | Explicit later write approval plus original historical measurements; current facts cannot substitute. | User; AN11. |

## 17. Row #16 - Record later user cutover and historical-write decisions

- **Scope:** Present isolated correctness/resource evidence and dry-run inventory, then record explicit user permissions separately for production cutover and the exact one-time historical rewrite.
- **Files touched:** `TODO/20261010-rust-host-telemetry-plan.md`.
- **Acceptance gates - local:** Evidence contains crate revision/toolchain, independent CPU/hash vectors, unchanged-field comparisons/noise, memory-off no-read proofs, event latency/failure coverage, native file/receipt validation, combined consumer tests and D15's bounded dry-run hash. Record user decision/date/scope; absence of either permission blocks its corresponding write row.
- **Acceptance gates - CI:** None; green suites and Fowler design approval cannot replace this user decision.
- **Oracle:** Explicit recorded permissions match the supplied evidence and exact production/maintenance scope; this cannot itself prove collector correctness or perform any write.

Table AT - Row 16 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AT1 | This is the only planned later adoption decision; do not ask again for already settled CPU/hash/memory design. The user may approve cutover and the exact history manifest together, approve cutover only and postpone history, request evidence repair or reject adoption. D17 stays pending until its explicit permission exists. | User, 2026-10-10; Fowler delegated design-only authority. |
| AT2 | Performance is evidence, not an invented mandatory speedup. Acceptable semantics, bounded instrumentation, truthful provenance and working controls are required; wider-than-effect noise is reported with instrument cost. Do not hide correction differences under a parity verdict. | Guardrail #10; intended capability. |

Table AU - Row 16 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AU1 | Treat the documentation commit, D1 or workflow green status as adoption/history permission | Confuses design approval with irreversible data effects. | The explicit later user decision required here; no advisor override. | User. |

## 18. Row #17 - Rewrite the approved historical manifest once

- **Scope:** After explicit D16 historical-scope approval, apply D15's validated manifest once with source-byte backups, fail-safe resumability and complete raw/compact/index/receipt/view reconciliation.
- **Files touched:**
  - `backend/utilities/migrate_host_fingerprints.py`
  - `backend/idhazh/contracts/host_migration.py`
  - `backend/tests/test_host_fingerprint_migration.py`
  - `docs/how-to/migrate-host-telemetry.md`
  - `docs/reference/host-metrics.md`
  - `TODO/20261010-rust-host-telemetry-plan.md`
- **Acceptance gates - local:** Separate approved maintenance execution, NOT an implementation test over production history. Re-run dry-run on exact manifest hashes before apply; stage all targets before any replacement; preflight dependencies/identities and publication exclusions. Generated fault/restart fixtures verify rollback and idempotence. Explicit maintenance output targets come from the approved manifest, never a glob in `Files touched`.
- **Acceptance gates - CI:** Utility/contract tests use only generated bounded files. Actual maintenance validation reads only manifested paths and dependent indexes/views, verifies new schemas/native-reader compatibility, v1 labels/retained averages/nulls, logical settlement, footer/physical hashes and current receipts. No workflow dispatch, push or git-history rewrite is implied.
- **Oracle:** Every approved source is either untouched or fully replaced/reconciled with verified completion evidence and recoverable original bytes; this cannot establish missing historical hardware facts or a multi-file filesystem transaction.

Table AV - Row 17 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| AV1 | Apply requires explicit manifest hash/scope approval and an operator-controlled writer/compactor/publisher quiet window. Prepare destination-local files, source backups and an immutable transaction journal in a task-owned maintenance root. Validate every staged file before the first replacement; compare source hashes again immediately before each rename. No original is deleted before a verified backup exists. | Fowler process safety; D16 historical permission. |
| AV2 | Atomicity is per-file only. Keep publishers out until a bounded batch's raw/compact dependencies, index rows/bytes and views reconcile. Journal planned/replaced/verified states plus expected old/new hashes; on restart accept exact old or exact new bytes, refuse a third state, complete the batch or restore all affected source/index/view bytes. A cancelled batch never publishes mixed authoritative views. No power-loss durability claim. | AE8/AE9; real filesystem constraints. |
| AV3 | Preserve original rank/keys and v1 identity, not misleading CPU values. Current corrected Rust output is outside the legacy rewrite set and is read as produced. Maintenance uses Python shared codecs with truthful new provenance; it does not resurrect Python CPU collectors or alter git history. | AN11/AO; user ownership. |
| AV4 | Closure verifies manifested physical files, compact/index lineage and expiry/loss markers, receipts, regenerated views and unchanged settled counts/clocks. Record exact completion/rollback bundle and approval in this plan until distillation. Keep read migration for older external fixtures/backups; final managed history is replacement-schema data, not indefinitely untouched legacy files. | User history outcome; section 11. |

Table AW - Row 17 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AW1 | Rename/rewrite files without updating digests/index sizes/receipts/views | Leaves readers or publishers validating stale byte evidence and can silently lose source rows. | Full manifest reconciliation and journalled application, already required here. | User; Fowler. |
| AW2 | Reuse normal raw `persist` to rewrite history or mint new identities for every migrated source | Changes ordering/attempt ownership and can duplicate work units; raw lifecycle gates are not a maintenance rewrite contract. | Dedicated bounded conversion/application under explicit maintenance approval. | Verified raw predicate; AO. |

## See also

- [Fowler advisor](../.github/agents/fowler.agent.md) - architecture and safe change sequence.
- [Host measurement reference](../docs/reference/host-metrics.md) - current consumers, collection and controls.
- [Item-health contract](../docs/architecture/sources/item-health.md) - mandatory census and resource fields.
- [Persistence contract](../docs/architecture/contracts/persistence.md) - writer identity and settlement.
- [Author a plan](../docs/how-to/author-a-plan.md) - row structure and author-and-stop.
- [Run the gates](../docs/how-to/run-the-gates.md) - selected local checks and CI ownership.
