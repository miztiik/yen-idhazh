# Publish task performance through TypeScript Host Probes

**Last Updated**: 2026-11-25
**Level**: 5 for the new ledger contract and the breaking host write shape.

## 0 - Operating contract

Table A - Scope and execution.

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Let any trusted pipeline record how its named work performed through one TypeScript API, without putting execution measurements in the machine fingerprint. |
| A2 | Hard scope - in | Task Performance and one TypeScript writer; one fingerprint per actual runner job and a probe per named task in each migrated workflow. Include model serving, Council preparation, judge shards and settlement, and gardener. Register publishing, compaction, cleanup and Data Explorer; migrate affected readers without losing digest item or shard diagnostics. Remove obsolete code, tests, docs and provably obsolete live ledger data after manual production verification. |
| A3 | Chosen strategy | Fowler: extend the existing Host Probes service and collectors, not replace them. Add only the durable recording operation; record one terminal observation per named task with ordinary settlement. Keep hardware captures separate. |
| A4 | ESCALATE triggers | 1. Stop if a real caller needs independent closes under one task key, all attempts, a whole-CI clock, or a rewrite of retained evidence. 2. Stop before deleting a path or switching off rollback if a dispatched proof, caller, reader or receipt is missing. 3. Surface changes to authority, consent, retention, platform limits or the trust boundary. |
| A5 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 4; honor the dependencies below. Coordinate with the main project session, use nested isolated sessions for authorized rows, and land verified changes to remote `main`. Row #7's manual dispatch evidence is required before Row #8 starts. |

Table B - Exclusions and their costs.

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | A whole-CI clock or all-attempts history | The new ledger answers how long named work took and shows the latest recorded attempt, not checkout-to-report time or every retry. No active reader will request the obsolete job clock. | A named consumer and a separately defined measurement boundary or attempt-retention decision. |
| B2 | Deleting useful historical readings, backfilling them under invented identities, or rewriting Git history | Some retained physical files can still contain dead clock cells alongside useful hardware or prompt readings. Do not rewrite mixed files solely to strip those cells. The cleanup removes obsolete-only files when normal retention or supersession permits; retained facts continue to read. | A separately reviewed bounded repack or evidence-preserving import for mixed files. |
| B3 | Porting the generic Python reader, publisher or gardener compactor to TypeScript | Python still validates and packs committed data; it does not collect host measurements or write new probe rows. | A separate shared-infrastructure migration and contract-ownership decision. |
| B4 | An arbitrary metric map, per-poll or per-article rows in the new ledger, or a new dashboard | New measurements need a typed addition. Item measurements still live in `item-health`; detailed samples stay private. | A named consumer, a defined measurement, and storage and browser-read limits for that work. |
| B5 | Deleting optional machine diagnostics or changing the hardware hash | Existing capture-time runnable capacity, placement, uptime, frequency and opt-in benchmark results remain available. None is a task or model clock. | A reader inventory and an approved retirement or move for each diagnostic; keep existing hash inputs and values compatible. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 1 - Status Reckoner

Table C - Implementation sequence.

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Declare and pack task performance records | - | A | DONE | task-performance-contract | - | Task Performance contract |
| C2 | 2 | Record one completed task through TypeScript Host Probes | 1 | B | DONE | task-performance-recording | - | Task Performance recording |
| C3 | 3 | Record digest tasks and model-server sessions | 2 | C | DONE | digest-task-performance | - | Digest Task Performance |
| C4 | 4 | Record Council and gardener tasks | 3 | D | DONE | council-and-gardener-performance | - | Council and gardener performance |
| C5 | 5 | Migrate console and audit readers and retire the live CI clock | 4 | E | DONE | task-performance-readers | - | Task Performance readers |
| C6 | 6 | Build TypeScript parity for item and shard probes | 4 | F | DONE | typescript-probe-parity | - | TypeScript probe parity |
| C7 | 7 | Switch host collection to TypeScript and narrow fingerprints | 5, 6 | G | PENDING | - | - | - |
| C8 | 8 | Remove Python host collection and its rollout option | 7 | H | PENDING | - | - | - |

## 2 - Row #1 - Declare and pack task performance records

- **Scope:** Register a flat, typed ledger and its reader, compaction, retention and explorer support before any production writes.
- **Files touched:**
  - `backend/idhazh/contracts/task_performance.py` (new)
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/staging.py`
  - `packages/common-contracts/src/schemas/task-performance.schema.ts` (new)
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `packages/common-contracts/src/index.ts`
  - `config/ledgers.json`
  - `config/idhazh.json`
  - `config/gardener/compact-task-performance.json` (new)
  - `config/gardener/config/idhazh_gardener.json`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_native_typescript_bindings.py`
  - `backend/tests/contracts/test_task_performance.py` (new)
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction_lifecycle.py`
  - `packages/common-contracts/test/task-performance.test.ts` (new)
  - `frontend/tests/ledger-catalog.spec.ts`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:** Local: use the shared changed-test selector in `docs/how-to/run-the-gates.md`; bind the Python and Zod field order, types, nullability, vocabularies and version and exercise the compactor on named temporary Parquet inputs. CI: current backend, native package, explorer catalog and payload-budget checks. No production write or cleanup is a test gate.
- **Oracle:** Pack subjects in the same run and shard under distinct task names, including a higher attempt for just one task and a late file reopening a packed period; the ordinary reader returns each named task once and keeps the latest recorded attempt for that task alone. This does not prove a caller actually measured its work.

Table D - Persisted contract and decisions.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| D1 | Display name **Task Performance**; registry ID and prefix `task-performance`, enum `TASK_PERFORMANCE`, standalone `raw-and-compact` family. | Registry naming and onboarding rules. |
| D2 | `TaskPerformanceRow` is a Pydantic contract with one dated, strict Zod binding for the TypeScript writer. Declare the implementation day's UTC version, changelog and read rule in the same change. Do not make a second authority or port the compactor. | `CLAUDE.md` sections 1a and 10; existing host snapshot binding. |
| D3 | Required fields: `version`; `date` (the UTC accounting day supplied by the workflow, not derived from the process start); `run_id`, `pipeline_name`, `task_name`, `shard` using the existing execution types; `task_kind` (`workflow-task`, `model-serving`, `judge`); `outcome` (`success`, `error`, `cancelled`). The shared writer stamps the normal `attempt`, `unit_id` and other file/row identity. The HTTP writer derives overlapping row fields from context; it never accepts competing copies. | Fowler; `file_envelope.py` and `packages/ledger-file-writer/src/row-identity.ts`. |
| D4 | Optional fields default to null: `subject_id` (existing bounded task-name vocabulary; required for a configured serving profile or judge); `started_at`, `finished_at` (actual UTC instants; ordered if both observed); `host_unit_id` (UUID of a verified same-run, same-attempt hardware capture); `elapsed_ms` (finite nonnegative duration of the named work, required for `workflow-task` and `judge`, absent for `model-serving`). Missing hardware or unobserved instants never supply fabricated values. | Profile and Council boundaries; the hardware reference keeps parent runner attribution exact when the serving task has its own name. |
| D5 | Optional profile summary fields: `machine_cpu_busy_pct`, `machine_cpu_steal_pct` (finite in 0-100, whole measured interval); `machine_memory_available_min_kib`, `worker_rss_peak_kib` (safe nonnegative integers; the latter is the largest RSS sampled in the interval, not lifetime peak); `worker_cpu_time_ms` (finite nonnegative process CPU time). Only a closed Host Probes profile supplies them. No samples, PIDs, process names, trace payloads, argv or paths in the row. | `services/host-probes/src/task-profile/profile-schema.ts`; smallest summary with a named operator use. |
| D6 | Optional serving fields: `model_load_ms`, `server_prompt_seconds` (finite nonnegative), `server_prompt_tokens` (safe nonnegative integer). Only `model-serving` may set them; require at least one actual reading. Rate requires both totals from the one row and positive prompt time. Do not add up separate windows or derive server totals from item rows. | Runtime independent of the item-health audit; `backend/utilities/reconcile_prefill.py`. |
| D7 | Optional phase-cost fields: `model_calls`, `tokens_in`, `tokens_out` (safe nonnegative integers), `model_seconds` (finite nonnegative wall time inside calls). Only `workflow-task` or `judge` may set them, using the completed phase's reported facts. They are not the server's cumulative prompt totals. Unknown is null, not zero; refuse unrelated fields and nonfinite values on both language boundaries. | `backend/idhazh/contracts/council_run_record.py`; use real phase readings without redefining their units. |
| D8 | Business key `(date, run_id, pipeline_name, task_name, shard)`. `task_name` identifies the work from the workflow or task config and is not a closed pipeline enum; `task_kind` says what the numbers mean, not which task it is. Only one terminal row per key and attempt. Never use a different kind or subject to make two rows under the same key appear independent. A different window needs an actual distinct task name. | Fowler; `backend/idhazh/ledger/raw_files.py::settle_rows` picks a file before applying row keys. |
| D9 | Keep the highest attempt that filed a terminal row for that task; a closed error or cancellation can be recorded, while a killed job with no closed measurement writes nothing. Compare recorded attempt at a read/join; never silently use an old attempt's reading for new hardware. | Ordinary settlement; no additional global file-selection rule. |
| D10 | Adopt the standard live retention and exact cleanup policy from the registry's onboarding checklist, including late-file repacking and normal expiry. Add explicit Data Explorer consent for these numeric, non-content fields, the index budget based on the configured retention bound, and the named compaction task. Stage only through normal reader and publisher inventory. | `docs/architecture/contracts/ledger-registry.md#onboarding-and-offboarding`; `config/gardener/compact-host-fingerprint.json` as the adjacent policy. |

Table E - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| E1 | `execution-performance` | Covers the same data, but makes the unit less clear to operators. | Rename the registry, prefix and readers together before the first write. | Fowler. |
| E2 | `task-runtime` | Sounds like wall time only; CPU, RAM and counters also belong. | Same rename, with less descriptive discovery in Data Explorer. | Fowler. |
| E3 | Separate runtime and model ledgers | Makes cross-task reads and lifecycle registration separate even though they share the same producer. | Additional registration, compaction, staging and joins for each new family. | One shared ledger required. |
| E4 | Independently appended observations sharing a task name | Row tags alone cannot prevent sibling loss before row settlement. The current callers have distinct measured tasks. | Change raw/compact settlement and replay rules across periods; name a real duplicate task window before doing so. | Fowler critique; Council configured phase names and gardener's configured task names fit the existing identifier contract. |

## 3 - Row #2 - Record one completed task through TypeScript Host Probes

- **Scope:** Reuse the existing TypeScript Host Probes service and start/stop collectors; add one versioned recording operation inside that service, not another probe API or listener.
- **Files touched:**
  - `services/host-probes/package.json`
  - `services/host-probes/bun.lock`
  - `services/host-probes/src/config.ts`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/server.ts`
  - `services/host-probes/src/api/create-machine-app.ts`
  - `services/host-probes/src/api/serve-machine-apis.ts`
  - `services/host-probes/src/api/create-probe-event.ts`
  - `services/host-probes/src/api/record-task-performance-route.ts` (new)
  - `services/host-probes/src/persist-task-performance.ts` (new)
  - `services/host-probes/test/native-events.test.ts`
  - `services/host-probes/test/record-task-performance.test.ts` (new)
  - `services/host-probes/test/serve-machine-apis.test.ts`
  - `docs/reference/host-probe-api.md`
  - `docs/architecture/publishing/committing.md`
- **Acceptance gates:** Local: shared selector and native route/Parquet cases with a private job root; use real writer and named files. CI: validate both standalone and composed listeners and consume the exact emitted Parquet with the Row #1 Python reader.
- **Oracle:** File two named tasks through the real handler, discard one reply, restart the listener with that same private root and repeat that request; the verified receipt is unchanged, a changed payload conflicts, and both tasks pack. This cannot recover a measurement that never closed or a root that was lost.

Table F - Recording contract.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| F1 | Add `POST /api/<release-date>/record-task-performance` with the UTC release date. Strict JSON: `date`, `writer` (`run_id`, `attempt`, `pipeline_name`, `task_name`, `shard`, `git_sha`, no caller `producer` or `job`), and `measurement` (the D3-D7 measurement fields, not version or execution identity). Validate the run, attempt, revision, pipeline and shard against the trusted launch context, and the date against the caller's admitted accounting days. New writes use `job: null` and fixed `producer: "host-probes"`. Use the service's preselected job-local state root and registry. | Fowler; `create-machine-app.ts` already composes the native APIs. |
| F2 | Reuse `start-task-profile` and `stop-task-profile` for CPU, memory and elapsed time; they currently return a profile but do not write Parquet. Send the closed summary or typed model/phase evidence to F1. Keep `sample-host` and existing transient callers unchanged. The recording handler neither opens arbitrary logs nor scrapes a URL, and never uses request latency as task time. | `services/host-probes/src/api/server.ts`; `docs/reference/host-probe-api.md`. |
| F3 | Only one writer instance owns a job-local root. Serialize check-and-write per task key and attempt. Read that exact ledger/day in that private root to verify a completed row. An equal normalized replay returns its existing receipt; unequal content returns 409 without replacement. Recover by delivering known bytes, not reconstructing a write in an empty root. | The shared writer's file ID includes its write time; compaction alone does not make the route idempotent. |
| F4 | Success returns `status: "written"`, validated `row` and completed `files` receipts. Return `status: "disabled"` for the master switch, or `status: "skipped"` for a paused/retired family, with `row: null` and no files. Invalid, oversized and persistence-failed requests fail explicitly. Keep the configured body bound, native safe events and loopback boundary; do not add a second opt-out flag. Publication is a separate action with independent authority, not an API effect. | Existing Host Probes, fingerprint, ledger and publisher contracts. |
| F5 | Reuse `observability.host_telemetry_enabled` for the master control. The trusted startup input for an instrumented job enables the existing `task_profile.enabled` setting and derives its two memory settings from existing memory control. Keep defaults for standalone and unrelated callers. Disabling sampling alone does not disable recording an independently measured model or phase result. No request overrides these switches. | `services/host-probes/src/config.ts`; one control per capability. |

Table G - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| G1 | Add no recording operation and write on existing stop | Stop currently has a live profile handle and transient callers; a model-only result or a write retry must not require a live profile. | Version and expand stop to accept durable-write intent and a second input path, or spread writers across callers. | Keep collection compatible and one durable writer. |
| G2 | Accept untyped metrics, a destination or a log path in the request | The generic service would own caller-specific collection and an unsafe input boundary. | A new trust boundary and arbitrary query/retention rules; no named consumer requires them. | Existing native command bounds. |

## 4 - Row #3 - Record digest tasks and model-server sessions

- **Scope:** Drive the new writer with real digest work and model-server facts, and pass verified receipts through the existing publisher.
- **Files touched:**
  - `.github/actions/machine-apis/action.yml` (new)
  - `.github/actions/model-server/action.yml`
  - `.github/workflows/digest.yml`
  - `backend/idhazh/telemetry/machine_api.py` (new, client only)
  - `backend/idhazh/llm/serving_metrics.py` (new)
  - `backend/idhazh/telemetry/silicon.py`
  - `backend/utilities/digest_publish.py`
  - `backend/utilities/model_runtime.py`
  - `backend/utilities/publication_evidence.py`
  - `backend/tests/contracts/test_publication_receipt.py`
  - `backend/tests/workflows/test_digest_publication.py`
  - `backend/tests/test_silicon.py`
  - `backend/tests/test_serving_metrics.py` (new)
  - `docs/architecture/summarize/model-boundary.md`
  - `docs/architecture/publishing/committing.md`
  - `docs/reference/host-metrics.md`
- **Acceptance gates:** Local: shared selector, native-to-publisher handoff and bounded recorded or in-memory metrics inputs. CI: same-source local Git publication and contract gates on the merge candidate. Obtain live model receipt evidence through Row #7's authorized manual dispatch, not a production write as a PR test.
- **Oracle:** Publish a real native output file through the ordinary digest publisher for `work` and its serving task; both appear with matching execution context and the original paired server counters, while an incorrect identity or mismatched byte hash is refused. The test cannot establish that a given live model build emits usable load timing.

Table H - Producer and delivery decisions.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| H1 | Run the shared machine listener on the measured runner and use Host Probes to measure the named `plan`, `work` and `assemble` work windows after its instrument is ready. Use a distinct `serve-summarizer` task on a work shard; never label checkout-to-report seconds as its elapsed time. Pass a verified parent host reference from the single opening fingerprint before model startup when present; don't capture twice during rollout. A missing fingerprint does not block performance recording. | `digest.yml`: separate runner jobs and pre-checkout clock; D8 requires distinct names. |
| H2 | Use the model-start action and the trusted local model launcher to supply actual weight-load timing and one final `/metrics` reading from that same instance before teardown. Move the bounded parser out of fingerprint collection. Missing actual load boundaries remain null; neither time to readiness nor the CI clock is a substitute. The text-analysis service times its own separate model, not these weights. | `backend/utilities/model_runtime.py::start_server`; `silicon.py::model_load_ms`; `services/text_analysis/spacy/src/text_analysis/manage_models.py::load_selected_model`. |
| H3 | Register each receipt with exact relative path, bytes and expected full writer identity, including pipeline/task. Check a supplied host reference against the verified capture for the same runner and attempt. Permit only the declared recording task's raw prefix. The existing publisher's legacy job comparison must not become a wildcard for model tasks. Receipt data is evidence, not permission to stage files. | `backend/utilities/publication_evidence.py::identified`; `docs/architecture/publishing/committing.md`. |
| H4 | Keep old production reads and host measurements available during rollout. If old and new records both need server facts, reuse the same captured reading; do not measure twice. A model exit without readable metrics is an explicit missing observation, not a fabricated report or a changed digest outcome. | Reader-first migration; preserve independent measurement provenance. |

Table I - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| I1 | Let Host Probes parse model logs or report its own readiness time | The host service does not own the model process and readiness includes more than loading. | Runtime-specific branches in the shared writer and a measurement that cannot be compared to the old one. | Model launcher owns its own interval. |

## 5 - Row #4 - Record Council and gardener tasks

- **Scope:** Use the existing TypeScript probes on each actual Council runner and named Council/gardener task, preserving the original publication and trial boundaries.
- **Files touched:**
  - `.github/workflows/llm-council.yml`
  - `.github/workflows/idhazh-gardener.yml`
  - `backend/idhazh/council/session.py`
  - `backend/utilities/council_publish.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/telemetry/machine_api.py` (introduced in Row #3)
  - `backend/utilities/publication_evidence.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/council/test_publication.py`
  - `backend/tests/gardener/test_runner.py`
  - `docs/architecture/publishing/llm-council.md`
  - `docs/architecture/publishing/idhazh-gardener.md`
- **Acceptance gates:** Local: shared selector, named Council artifact and real gardener publication fixtures. CI: active versus paused routing, exact allowed paths, partial failure and late compaction. Use Row #7's manual dispatches for live evidence.
- **Oracle:** Match the actual workflow runner identities to their captures and the named task outcomes to their closed probes. For the example with a preparation runner, five judge runners and a settlement runner, all seven work-runner captures must survive; separately match any real control runner. Test a skipped matrix part (no invented row), paused output (no publish) and a gardener compaction that records its own probe only after that pass. This does not prove observations survive a killed runner or an unsuccessful publication.

Table J - Other task identities and permissions.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| J1 | Council uses `prepare-<tenant>`, `judge-<tenant>` and `settle-<tenant>` for the existing measured steps, and `serve-<tenant>` only for jobs with a server. Validate the composed names at configuration/intake; use actual judged day and work part, not the settlement job's shard for judge work. | `config/llm_council.json`; `backend/idhazh/council/session.py`; D8. |
| J2 | Start and stop Host Probes around each actual Council task, including non-judge steps, and reuse Council's existing model-call costs rather than measuring those again. Map completed and nothing-to-do to `success`, stopped-on-deadline to `cancelled`, and failed to `error`. Keep Council's own outcome, verdicts and coverage in its existing records. | `CouncilRunRecord` and the caller's actual task bounds. |
| J3 | A Council matrix worker publishes nothing. Give the collector only named receipt files with the expected date, tenant/task, shard, attempt and revision from its existing work plan. Active tasks follow Council settlement and paused tasks remain in the trial root. The new family grants no power to publish another tenant's output. | `council_publish.py`; existing Council selection, artifact and permission rules. |
| J4 | Gardener uses each configured task name, starts and stops Host Probes around `_run_one`, and records the completed result after that work in a private output root. The shard publisher adds only verified append paths, separately from task-owned updates/deletions; a refusal must not leak an eligible receipt. A compaction cannot compact its own newly recorded row in the pass being measured. | `backend/idhazh/gardener/runner.py`; the scheduler's fixed input and write authority. |
| J5 | One opening fingerprint per runner job that actually starts for an enabled attempt, not one per workflow or machine type. Wire the TypeScript path before changing the default in Row #7. Council records `draw`, every started matrix cell, and `save_council_results`, plus the current separate `job_bounds` runner. Preserve the matrix tenant/day/part identity for each judge capture. A single runner can close multiple named probes; all refer to its own capture where available. The day file may contain the combined rows, not a merged hardware record. Apply the same rule to actual runner jobs in the other migrated workflows. | `.github/workflows/llm-council.yml`; physical jobs and task windows are different units. |

Table K - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| K1 | Reuse `council-run-records` as the common ledger or give each Council phase one generic job name | Its domain coverage contract is not general, and one generic name would overwrite different tenants or steps. | Breaking Council consumers or a new identity/settlement mechanism, with no benefit over real task names. | Fowler; existing measured phase boundaries. |
| K2 | Count only Council work phases, not a separately provisioned control runner | It would omit an actual runner and task. | A smaller collection scope and explicitly documented unmeasured setup jobs. | J5; scope choice to confirm before execution. |

## 6 - Row #5 - Migrate console and audit readers and retire the live CI clock

- **Scope:** Read serving evidence from committed compact data and preserve hardware counts and prompt speed while removing the obsolete runner clock from active displays, queries and the offline report.
- **Files touched:**
  - `config/appearance.json`
  - `backend/idhazh/contracts/knobs/console.py`
  - `backend/idhazh/telemetry/publish/console_band.py`
  - `backend/utilities/reconcile_prefill.py`
  - `backend/utilities/measure_ledgers.py`
  - `backend/utilities/build_canary_day.py`
  - `frontend/scripts/stage-publication.mjs`
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/lib/console/queries/machine.ts`
  - `frontend/src/lib/console/machine/query-groups.ts`
  - `frontend/src/lib/console/machine/records.ts`
  - `frontend/src/lib/console/machine/counters.ts`
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte`
  - `frontend/src/lib/charts/fleet.ts`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/tests/console-canary-host-halves.spec.ts`
  - `frontend/tests/console-chrome.spec.ts`
  - `frontend/tests/console-host-spans.spec.ts`
  - `frontend/tests/console-machine-data.spec.ts`
  - `frontend/tests/console-machine.spec.ts`
  - `frontend/tests/console-panel-queries.spec.ts`
  - `frontend/tests/platform-mix.spec.ts`
  - `frontend/tests/support/machine-rows.ts`
  - `frontend/tests/support/reduction-input.ts`
  - `tests/fixtures/console/machine/platformMixQuery.json`
  - `tests/fixtures/platform-mix/door-answer-26-to-28-september.json`
  - `backend/tests/contracts/test_panel_queries.py`
  - `backend/tests/test_console_payloads_producer.py`
  - `backend/tests/test_measure_ledgers.py`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/concepts/console-design.md`
  - `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`
- **Acceptance gates:** Local: shared selector with existing machine logic and console browser journey; smoke Hardware and Data Explorer with integrated browser tools, inspect for new errors or unexpected 404s, verify missing performance data preserves hardware, and review the changed operator surface before merge. CI: real build, published columns and budget, selected native read and console journey checks. Verify the first normal packed output before turning off the old producers; the historic fallback stays.
- **Oracle:** The same bounded mixed-history input yields the same hardware jobs and server-based speed in the browser and in the independent audit. A performance row for another attempt must not fill a missing speed; overlap counts once; the live `Seconds` field and job-time example are gone. This does not establish that operators prefer the removed display.

Table L - Reader and compatibility decisions.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| L1 | The deployed graph shows only counts. Selecting a day opens the job table, where **Seconds** is visible at the right (horizontal scroll may be needed); it is not a series or a separate chart. The host conflict check, saved Data Explorer job-time example and offline ledger report also read the field. None is needed for counts, prompt speed or article timing. | Production Hardware drilldown observed on 23 Nov 2026; `PlatformMixPanel.svelte`, `fleet.ts`, `counters.ts`, `config/appearance.json`, `measure_ledgers.py`. |
| L2 | Remove the table's Seconds column, saved job-time example in config and defaults, and old runner-duration report in `measure_ledgers.py`; preserve the tool's other reports. Remove the corresponding visual layout, projections, fixtures, explanatory docs and tests of the removed behavior. Do not substitute profile elapsed time. Finish the writer and legacy code cleanup in Row #8. | `silicon.py::job_seconds` defines the old window; L1 defines its actual consumers. |
| L3 | Read named, consented compact files through existing static publication. For new speed use the serving row attached to that exact host `unit_id`, run and attempt; never join on CPU model, kind, or reporting job alone. Keep unmatched hardware visible and speed unavailable. If several serving scopes match in future, select the declared `serve-summarizer` scope for digest, not a mixture. | Existing fleet chart measures recorded jobs, not unique machines. Data Explorer already permits registered-ledger joins. |
| L4 | For an older stamped host row with no corresponding new serving observation, continue reading its historical prompt pair from that same row. When new evidence exists, use it alone, even if one metric is unknown. Apply the same fallback in the band producer, audit and throughput example. The saved SQL supplies nullable legacy columns with a typed, zero-row `UNION ALL BY NAME` branch so an all-new window still binds; assert no phantom observations. This is the read-side migration; no copying or rewriting historical facts. | Avoid double counting current overlap, requiring retired physical columns or inventing legacy identities. |
| L5 | Keep the meaning of the `host-fingerprint` count, CPU/L3 comparisons and item-health timing/resource charts unchanged. Capturing previously unrecorded runner jobs legitimately adds rows, not fabricated machines. Remove task/model fields from hardware conflict checks only after the performance reader independently validates its own data. Retain only compatibility tests still needed by supported rows. | `docs/architecture/publishing/console-machine.md`; no broader redesign. |

Table M - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| M1 | Keep the Seconds display by substituting task elapsed time | It would silently change what the number means and invalidate historical comparison. | A separately approved, clearly labelled task-duration visual and a new baseline. | L1-L2. |
| M2 | Backfill the full archive into the new ledger before switching reads | The old rows do not always carry exact server or task identities, and the console can retain the readings without translating them into new facts. | Approved bounded import, explicit provenance, overlap checks and independent validation before deleting any old column. | B2; Fowler review. |

## 7 - Row #6 - Build TypeScript parity for item and shard probes

- **Scope:** Match the existing digest's per-item CPU/RAM and private shard diagnostic behavior with TypeScript probes before removing Python collection.
- **Files touched:**
  - `services/host-probes/src/config.ts`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/task-command-schema.ts`
  - `services/host-probes/src/api/task-profile-route.ts`
  - `services/host-probes/src/task-profile/task-collector.ts`
  - `services/host-probes/src/task-profile/process-collector.ts`
  - `services/host-probes/src/task-profile/profile-schema.ts`
  - `services/host-probes/src/probe/memory-probe.ts`
  - `services/host-probes/src/diagnostics/shard-memory.ts` (new)
  - `services/host-probes/test/probe.test.ts`
  - `services/host-probes/test/item-window-profile.test.ts` (new)
  - `config/host-probes.json`
  - `backend/idhazh/telemetry/machine_api.py` (introduced in Row #3)
  - `backend/idhazh/telemetry/item_heartbeat.py`
  - `backend/idhazh/stages/work.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/pipeline/test_work_health_payload.py`
  - `backend/tests/test_host_readings.py`
  - `docs/reference/host-probe-api.md`
  - `docs/reference/host-metrics.md`
- **Acceptance gates:** Local: shared selector, explicit proc-input/profile cases and existing item-health integration. CI: paired real-process Linux coverage, including a reused PID, zero periodic polls, memory disabled, a worker failure and missing OS readings. Validate using the real TypeScript client path without dispatching a production data-writing workflow.
- **Oracle:** A named observation sequence filed through the TypeScript watch and existing digest item recorder produces the current item-health values with the same units, windows and unknown behavior. The shard exporter retains readings independently of any one item. It cannot make a one-off coincident CPU measurement across two live collectors share the same underlying ticks.

Table N - Probe ownership and compatibility.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| N1 | Digest opens and closes the same item work window, while actual worker and optional server PIDs are still alive and pinned to kernel start ticks. Keep the application heartbeat separate. The parity mode uses the existing configured heartbeat interval for interior polls (zero means endpoints only); compute busy/steal across the whole interval and preserve Python's busy low/high rule from adjacent periodic polls plus the whole window. Match the old counter accounting, invalid/reset behavior and rounding; absent steal stays unknown. Do not repurpose generic rolling samples. | `backend/idhazh/stages/work.py`; `backend/idhazh/telemetry/host.py::Watch`. |
| N2 | Capture closing load average, process RSS/anonymous RSS, server lifetime peak using the available endpoints, server major fault delta, RAM cache and total/free swap plus available-RAM minimum. Keep the existing item-health field names, byte units and no-reading behavior. Profiling errors and absent PIDs leave unavailable cells, not forced zeros and not a failed article. Memory off leaves CPU and heartbeat on. | Existing `HostCells` and `ItemHealthRow`; reuse the TypeScript PID-pinned collector where it already measures the same fact. |
| N3 | Keep private shard diagnostics (`rss-samples.jsonl`, `python-procs.jsonl`, `memory-peak.txt`) and the current aggregate intent. Collect committed RAM, process counts and RAM, and current/peak memory for the selected runner group through bounded Linux reads. Keep process details out of the HTTP response and both ledgers, and preserve the existing artifact audience and retention. Raw model counters remain a model artifact. | `backend/utilities/memory_sampler.py` and the digest's artifact steps; no task-performance row for every item or poll. |
| N4 | Keep the existing generic task profile contract usable. Add the new item projection as an explicit versioned mode with the existing observability and memory controls. Wire it behind the `typescript` rollout selection; Row #7 changes the default. No second instrument measures the same item in normal operation. | Avoid breaking current planner/evaluation callers while matching the digest. |

Table O - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| O1 | Replace item readings with one shard profile or its rolling CPU peaks | They describe a different time window and would change Hardware's existing item comparisons. | Retire or redefine the published item fields and charts with an explicit decision. | Existing item-window contract. |

## 8 - Row #7 - Switch host collection to TypeScript and narrow fingerprints

- **Scope:** Move remaining host callers to TypeScript, emit hardware-only captures, and keep a reversible rollout selection until production evidence supports removing it.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/llm-council.yml`
  - `.github/workflows/idhazh-gardener.yml`
  - `.github/workflows/encoder-comparison.yml`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/telemetry/host.py`
  - `backend/idhazh/telemetry/host_control.py`
  - `backend/idhazh/telemetry/item_heartbeat.py`
  - `backend/idhazh/telemetry/task_telemetry.py`
  - `backend/idhazh/telemetry/silicon.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/contracts/host_fingerprint.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/ledger/persist.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/tasks/_reopened_month.py`
  - `backend/utilities/council_publish.py`
  - `backend/utilities/digest_publish.py`
  - `backend/utilities/gardener_shards.py`
  - `backend/utilities/host_telemetry_control.py`
  - `backend/utilities/memory_profiling_control.py`
  - `backend/utilities/memory_sampler.py`
  - `backend/utilities/compare_summary_encoders.py`
  - `backend/utilities/measure_llm.py`
  - `backend/utilities/measure_judge_call.py`
  - `backend/utilities/replay_article_calls.py`
  - `backend/utilities/build_canary_day.py`
  - `frontend/src/lib/console/machine/host-types.ts`
  - `frontend/src/lib/data/host-fingerprint.ts`
  - `frontend/src/lib/console/queries/shared.ts`
  - `packages/common-contracts/src/schemas/host-fingerprint.schema.ts`
  - `packages/common-contracts/test/host-fingerprint.test.ts`
  - `services/host-fingerprints/src/api/server.ts`
  - `services/host-fingerprints/src/api/fingerprint-response.ts`
  - `services/host-fingerprints/src/config.ts`
  - `services/host-fingerprints/src/collect-fingerprint.ts`
  - `services/host-fingerprints/src/persist-fingerprint.ts`
  - `services/host-fingerprints/test/fingerprint-persistence.test.ts`
  - `services/host-fingerprints/test/fingerprint.test.ts`
  - `services/host-fingerprints/test/fixture.ts`
  - `services/host-probes/src/api/create-machine-app.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-host-fingerprint.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-host-verification.ts`
  - `services/feed-ingest-plan/scripts/capture-workflow-machine-task.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-host.test.ts`
  - `tests/fixtures/host-fingerprints/host-schema.json`
  - `backend/tests/contracts/test_host_fingerprint_snapshot.py`
  - `backend/tests/contracts/test_gardener_plan.py`
  - `backend/tests/contracts/test_machine_join.py`
  - `backend/tests/test_host_history_reading.py`
  - `backend/tests/test_host_readings.py`
  - `backend/tests/test_host_telemetry_control.py`
  - `backend/tests/test_job_machine.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_memory_sampler.py`
  - `backend/tests/test_silicon.py`
  - `backend/tests/pipeline/test_publish_window.py`
  - `backend/tests/workflows/test_a_job_that_plans_nothing_records_its_machine.py`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/council/test_publication.py`
  - `backend/tests/gardener/test_runner.py`
  - `frontend/tests/console-canary-host-halves.spec.ts`
  - `frontend/tests/console-host-spans.spec.ts`
  - `frontend/tests/ledger-rows.spec.ts`
  - `frontend/tests/recorded-slices.spec.ts`
  - `docs/reference/host-metrics.md`
  - `docs/reference/host-probe-api.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/how-to/evaluate-content-similarity-judge.md`
- **Acceptance gates:** Local: shared selector, old/new Parquet and receipts, a bounded gardener proof selection and exact scope/migration checks. CI: field bindings, mixed-version packing, site projections, no-plan and Linux parity cases. After the verified merge to remote `main`, manually dispatch and verify P5-P7. Do not wait for a scheduled run. Failed, skipped or missing proof blocks Row #8, not the merger of this reversible row.
- **Oracle:** The same close sequence on TypeScript yields one hardware-only capture plus its separate performance reading, and two distinct generic tasks never collapse into one machine. A packed mixed-version input retains every historically present timing value, while an all-new input has no timing columns in its physical host file. This cannot recover readings already unknown or expired.

Table P - Hardware and removal rules.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| P1 | New stamp and dated capture response: keep the existing machine capture fields and stamp/identity, except `job_seconds` and the three serving fields in D6. These four names are absent, not null, in new TypeScript hardware replies, CLI input and new TypeScript raw files. Keep hardware hash inputs unchanged. Remove the closing host write in `typescript` mode; explicit rollback uses the old stamp until Row #8. | Host API owns hardware; Rows #3 and #5 displace the old work. |
| P2 | Keep the stamped old read contract and a separate latest, strict hardware write shape. A mixed daily/monthly/yearly period may write the full compatibility columns to preserve old facts, with the original row timestamps and stamps; a new-only period chooses the hardware shape. Refuse unknown shapes and any operation that would lose a historical value before deleting inputs. Do not rewrite existing archives just to remove columns. | `HostFingerprintRow` version rules; existing compaction writes one schema per file. |
| P3 | Fix host settlement and correlation for `pipeline_name` plus `task_name` when present, and legacy `job` when not. Preserve known digest job aliases for old readers; do not guess a pipeline for an ambiguous legacy row. Verify that the reported affinity/quota describe the intended target, not a differently restricted listener; otherwise leave those readings unavailable. | `HOST_FINGERPRINT_KEY` is currently job-only; `services/host-fingerprints/src/inspect/cpu-capacity.ts` reads self. |
| P4 | Switch only after Row #5's reader migration and Row #6's measurement parity and receipt checks. Replace workflow and local call sites with TypeScript commands; a Python pipeline may be a client but must no longer collect in `typescript` mode. Select `typescript` by default via the existing workflow control; keep `python` only as an explicit rollback for this row. Keep `off` and selective memory/fingerprint controls. Never fall back silently. | Caller inventory includes digest, Council, gardener, visuals CLI, encoder comparison and named benchmark/canary utilities. |
| P5 | Manually dispatch Digest on an authorized accounting day with a normal complete publication, and LLM Council for a day and active judge with actual work. Verify the run revision, completed jobs, the planned/started runner identities and per-task output against J5. Do not overwrite a production digest with a reduced test run or count an empty/paused Council run as proof of judge publication. Verify changed encoder and feed planner workflow callers with their bounded manual/artifact paths; use `commit_readings: false` for the encoder proof. | Workflow dispatch inputs and existing caller scopes. Run real work once and record run links, attempts, matched rows, missing expected rows and receipts. |
| P6 | After the writer runs, manually dispatch gardener with a default-off `telemetry_proof` selector. Admit only active `compact-host-fingerprint` and `compact-task-performance` tasks, reject combining it with `force`, and skip the history job even if otherwise due. Bound verification to exact eligible periods: use a past accounting day for packed proof, and verify current-day raw receipts without changing compaction age or retention. Verify the named compact files and indexes before checking the deployed reader; dispatch publication rather than waiting for a scheduled deployment if it has not run. | Current gardener dispatch does not suppress a due history job merely by leaving `force` false; readers depend on committed packed data, not green status alone. |
| P7 | Compare the dispatched records to the expected runner/task manifest. Confirm no legacy clock in new fingerprint output, independent model prompt evidence, Council fanout coverage, and item/shard parity. Confirm on deployed Hardware that counts and Speed remain while the obsolete Seconds field is gone. Retain the explicit rollback until these proofs pass. | Manual cutover acceptance, separate from deterministic PR gates. |

Table Q - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Drop columns in place, remove Python first, or key by null legacy job | Deletes historical evidence during packing, leaves live measurements missing, or loses one generic task to another. | Historical repair, broken downstream reads and a rollback spanning producer, schema and console. | Reader before writer; Fowler and upstream/downstream review. |
| Q2 | Migrate the whole compactor or retire all optional capture diagnostics now | Neither is necessary for TypeScript to own these APIs and writes. | A second shared infrastructure migration or loss of validated measurements still used by operator callers. | Scope exclusions B3 and B5. |

## 9 - Row #8 - Remove Python host collection and its rollout option

- **Scope:** After the manual proofs pass, remove old acquisition, rollback, obsolete tests and docs, and any live ledger files shown to be obsolete.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/llm-council.yml`
  - `.github/workflows/idhazh-gardener.yml`
  - `.github/workflows/encoder-comparison.yml`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/telemetry/host.py`
  - `backend/idhazh/telemetry/host_control.py`
  - `backend/idhazh/telemetry/item_heartbeat.py`
  - `backend/idhazh/telemetry/task_telemetry.py`
  - `backend/idhazh/telemetry/silicon.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/utilities/digest_publish.py`
  - `backend/utilities/host_telemetry_control.py`
  - `backend/utilities/memory_sampler.py`
  - `backend/utilities/memory_profiling_control.py`
  - `backend/tests/test_host_telemetry_control.py`
  - `backend/tests/test_host_readings.py`
  - `backend/tests/test_job_machine.py`
  - `backend/tests/test_memory_sampler.py`
  - `backend/tests/test_silicon.py`
  - `backend/tests/pipeline/test_work_health_payload.py`
  - `backend/tests/workflows/test_a_job_that_plans_nothing_records_its_machine.py`
  - `docs/reference/host-metrics.md`
  - `docs/reference/host-probe-api.md`
- **Acceptance gates:** Local: shared selector plus exact inventory of the removed commands, readers, tests and docs. Verify Row #7's manually dispatched successful runs and production data before starting this row. CI: retained hardware/model reads, TypeScript producer, telemetry-off and item-health behavior. Run any live cleanup through the bounded, named policy in R3 only after proving its delete set.
- **Oracle:** No inventoried caller needs a Python collector, the old runner clock or its rollout mode. Opt-out still emits no telemetry. Compare supported hardware and model rows before and after approved cleanup; values and identities still read, and only the proved-obsolete files disappear. This cannot recover an old unpublished file or preserve an untracked external CLI caller.

Table R - Retirement decisions.

| ID | Decision | Authority or evidence |
| --- | --- | --- |
| R1 | Re-run the tracked inventory before removing code. Require the named replacements and passing P5-P7 evidence before removing the Python mode. Keep useful heartbeat code, model-source adapters and compatibility only for supported retained data. | Manual production proof, not merely absence of an error in a workflow. |
| R2 | End with `typescript` and `off`. Delete superseded Python acquisition, commands, settings and workflow branches. Remove the whole-CI clock from active visuals, queries, code, docs, tests and their authored fixtures; no ongoing legacy report or schema field exposes it. Validate original retained Parquet integrity before projecting only supported hardware and model facts. Keep compatibility and parity tests for those retained facts, not expectations for the removed clock. Unrelated text-analysis load timing remains. | Level-5 retirement gate and scope; do not delete raw files solely to remove an unused field. |
| R3 | Inventory only named telemetry periods using registered indexes and completed receipts. Remove obsolete-only or superseded raw/compact files through existing compaction/expiry and its verified delete list. Preserve any file still needed for Hardware, prompt speed, audits or current coverage; no broad ledger deletion or Git history rewrite. Remove a legacy registration only if the inventory finds a retired unused family. The old design's two proposed ledgers were never registered. If the verified delete set is empty, record that result and make no data deletion. | B2, standard retention and confirmed publisher declarations. |

Table S - Alternatives reviewed.

| ID | Option | Why not chosen | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| S1 | Keep both production collectors indefinitely | A known-quiet fallback permits drift and makes the selected measurement source unclear. | Maintain two instruments and parity tests for every field, caller and control indefinitely. | TypeScript owns the future host collection path. |
