# Feed ledger simplification

**Last Updated**: 2026-10-31
**Level**: 5 - persisted health contract and planner execution design; execution authorized by the user on 2026-10-31 UTC.
**Status**: Cutover merged after green merge-candidate CI. Cleanup is implemented and locally verified; cleanup CI and live production verification remain.

## 0 - Operating contract

Table A

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Keep timed feed recovery and retirement in existing health Parquet output without availability sidecars or intermediate Git commits. |
| A2 | In scope | TypeScript planner lifecycle, real HTTP stage calls, concurrent snapshot decisions, partial-data behavior, saved run calculations, and planner-owned compatibility removal. |
| A3 | Strategy | Read saved per-feed calculations from existing health Parquet, reconstruct only unavailable calculations, apply this run's actual work, and publish immutable results through existing finalization. |
| A4 | Confirmed concurrency decision | Concurrent runs are allowed. Decisions can precede another run's publication. Do not introduce workflow serialization, remote reservations, or an enrollment gate. |
| A5 | Confirmed format decision | Breaking changes are allowed. No migrations or legacy compatibility are requested. Preserve historical files; current readers diagnose refused formats and retain usable sibling evidence. |
| A6 | JSON cleanup | Remove the availability state/enrollment JSON files, their contracts and all readers/writers. Never recreate the paths deleted from remote main. Delete the dedicated availability configuration file; retain its policy controls in the existing planning configuration. HTTP JSON messages are transport payloads, not replacement state files. |
| A7 | Escalation | The user approved the fields and snapshot semantics below. Surface any compatibility dependency outside the TypeScript planner, any proposed extra runtime commit, or any claimed cross-process exactly-once guarantee. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md; the user authorized sequential implementation, gated PR delivery and a live production planner dispatch on 2026-10-31 UTC. One delivery session carries all rows; no additional sessions or multi-agent workflow. |
| A9 | Cutover boundary | Rows 1 and 2 are tasks in the same cutover PR, not separately deployable PRs. Merge only their complete candidate; do not leave a runtime that depends on the deleted JSON files. Row 3 is the subsequent cleanup PR. |
| A10 | Production proof | After both deliveries land, dispatch the existing feed-planner workflow at the delivered production revision. Inspect its actual health Parquet, selection, finalization, diagnostics and Git publication; dispatch acceptance or a skipped green job is not completion. |

Table B

| Id | Out of scope | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Cross-process exclusive feed ownership | Independent runs can check the same feed; unpublished work can be repeated after interruption. | Explicit approval for shared ownership writes or another shared coordination mechanism. |
| B2 | Unrelated Python or published-site compatibility | Those consumers retain their own format rules. | An identified dependency and user approval to expand cleanup. |
| B3 | Recovery of deleted lifecycle evidence | A feed with no surviving usable evidence has unknown state; no exact old counter or retirement decision can be invented. | A separately approved retention change; compaction alone does not delete the facts. |

## 1 - Status reckoner

Table C

| Id | Row | Title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Record and consume ledger lifecycle snapshots | - | A | DONE | feed-ledger-delivery | #1842 | - |
| C2 | 2 | Switch concurrent HTTP planning and remove availability publication | 1 | B | DONE | feed-ledger-delivery | #1842 | - |
| C3 | 3 | Remove planner legacy branches and obsolete delivery machinery | 2 | C | READY FOR MERGE | feed-ledger-delivery | - | - |

## 2 - Approved health contract

- **Scope:** Add the missing lifecycle information to the existing `feed-health-state` ledger; do not create another ledger.

Table D

| Id | Added column | Meaning and consumer |
| --- | --- | --- |
| D1 | `check_request_id` | Identity of this row's actual logical check; deduplicate identical completed evidence and refuse conflicting copies. Null on carry-forward-only rows. |
| D2 | `check_result` | Distinguish valid parsed feed, confirmed target HTTP failure, other HTTP failure, timeout, robots result, uncertain transport, local failure, and interruption. This is not download-only `outcome`. Null when this row performed no check. |
| D3 | `rest_until` | UTC deadline used by collection preflight and feed fetch eligibility. |
| D4 | `first_confirmed_failure_at` | UTC start of the current confirmed source-failure episode; used by the retirement age test. |
| D5 | `failed_recovery_checks` | Saved count of qualifying confirmed failures after recovery rests; used by the retirement count test. Nullable when evidence is insufficient. |
| D6 | `retired_at` | UTC instant of a proven retirement decision. |
| D7 | `retirement_reason` | Typed reason accompanying retirement; never inferred from missing history. |
| D8 | `availability_updated_at` | UTC instant of the actual check that last changed the carried lifecycle calculation; copying it into a later run does not advance it. |
| D9 | `availability_complete` | Boolean: whether the feed's saved rest/retirement calculation is fully supported. It does not mean the feed is reachable. Known individual values remain usable when this is false; see Table O. |

Table E

| Id | Existing columns | Treatment |
| --- | --- | --- |
| E1 | `availability`, `strikes` | Reuse for this run's computed status and failure streak; nullable streak remains unknown rather than zero. |
| E2 | `status`, `last_failure_code`, `checked_at`, `date` | Retain actual HTTP outcome, diagnostic and work time; do not relabel a carried snapshot as a new check. |
| E3 | `run_id`, `attempt`, `feed_id`, `endpoint_key` | Retain execution and endpoint identity. |
| E4 | `reliability.*`, `counts_complete`, request and article counters | Reuse saved reliability counts, fractions, covered dates and completeness. Update from actual new work at finish; never sum rolling fractions. No second reliability state file or new reliability completeness column. |
| E5 | `rested_runs` | Remove; hours replace skipped-run counting. |

Table F

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | All configured active feeds enter preflight; valid current rest or retirement evidence can skip work, but no separate enrollment is required. Preserve existing draft/retired catalog handling. | User-directed scope, 2026-10-31 UTC; exact catalog status predicate must not be broadened silently. |
| F2 | Use the saved calculations first, following Table N. Reconstruct only missing or unusable calculations from the already selected health records; do not recount history for every API. Valid zeroes and supported null values are not missing fields. | User-directed saved-calculation reuse, 2026-10-31 UTC. |
| F3 | Parallel snapshots are not atomic global counters. Two runs reading a streak of zero can each save a streak of one. Retain both immutable rows; never add their cumulative snapshots together. Select the newest coherent evidence, using actual check order, not push order. | User-approved snapshot semantics, 2026-10-31 UTC. |
| F4 | An ambiguous order or conflicting calculation is incomplete, not permission to fabricate a failure count or automatic retirement. Preserve both rows and diagnose the uncertainty. | Partial-data requirement. |
| F5 | If a supported saved decision says wait until a later UTC time, wait. If no supported decision is available, an active feed may be checked. Missing reliability is labelled unknown, not successful or reliable. Only supported retirement evidence, or catalog retirement, stops a feed as retired. Missing unrelated columns must not erase a known decision. | User-directed partial-data tolerance; no invented healthy result or retirement. |
| F6 | A valid parsed feed, including empty, resets its episode. Keep the existing five-failure rest threshold, 24-hour rest and recovery spacing, and retirement requiring seven qualifying recovery failures plus 36 hours from first confirmed failure. Only confirmed target HTTP 404/410/5xx advances retirement; interruption does not. | Preserve requested #1836 capability and existing policy values. |
| F7 | Save a computed/carry-forward lifecycle row for every active catalog feed in ordinary run output, including skipped or dynamically retired feeds. Counters remain zero only for known skipped work; absent accounting remains null. No new check identity is invented for a carried row. | User requires computed data to be retained for the next run. |
| F8 | Count the same check only once if its record exists in both a raw file and a compacted file. Copy supported decisions into ordinary later-run rows even when checking was skipped. If all supporting records disappear, save unknown values rather than guessing. | Bounded reads and partial-data requirement. |
| F9 | Current-format validation is not a migration. Old formats are refused with diagnostics; current-format field gaps affect only the relevant calculation. Unexpected code errors still propagate. | User-directed breaking-format cleanup. |
| F10 | Only `safe_persist_data` may commit or push TypeScript planner output. Health recording writes Parquet locally; the existing final delivery submits completed files together. Fetch, parse, collection, summary, selection and lifecycle updates make no Git commits. | User-directed single publication path, 2026-10-31 UTC. |

## 3 - Row 1 - Record and consume ledger lifecycle snapshots

- **Scope:** Implement Table D and its saved-calculation readers, reducer, writer and API reporting as the first task of the atomic cutover PR defined in A9.
- **Files touched:**
  - `packages/common-contracts/src/schemas/feed-health-state.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health-fields.schema.ts`
  - `packages/common-contracts/src/version.ts`
  - `packages/common-contracts/src/observation-order.ts` (shared clock grouping; existing behavior retained)
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-feed-health-fields.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/health-summary.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-feed-history.ts`
  - `services/feed-ingest-plan/src/availability/feed-lifecycle.ts` (new pure calculation module)
  - `services/feed-ingest-plan/src/availability/feed-availability-view.ts` (new body-free calculation view)
  - `services/feed-ingest-plan/src/health-row.ts` (new shared carried-row construction)
  - `services/feed-ingest-plan/src/read-ledger-history/saved-calculation.ts` (new recorded-time selection)
  - `services/feed-ingest-plan/src/read-ledger-history/feed-lifecycle-history.ts` (new independent lifecycle reuse and recovery)
  - `services/feed-ingest-plan/src/read-ledger-history/feed-reliability-history.ts` (new independent reliability reuse and rolling updates)
  - `services/feed-ingest-plan/src/read-ledger-history/read-health-capture.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-planner-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/raw-day-members.ts`
  - `services/feed-ingest-plan/src/run-health.ts`
  - `services/feed-ingest-plan/src/api/prepare-planning-health.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state-operation.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state.schema.ts`
  - `services/feed-ingest-plan/src/record-plan-run.ts`
  - `services/feed-ingest-plan/src/reporting/feed-rest-markdown.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-feed-history.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-history.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle.test.ts` (new)
  - `services/feed-ingest-plan/test/feed-lifecycle-history.test.ts` (new)
  - `docs/architecture/sources/planner-feed-history.md`
  - `docs/architecture/sources/feed-availability.md`
  - `docs/reference/feed-planner-ledgers.md`
  - `CLAUDE.md`
- **Acceptance gates:** Local selector from `frontend`: `npm run test:changed -- --list`, then the selected native planner/common-contract tests and type checks named in `docs/how-to/run-the-gates.md`. Its independent TypeScript section excludes Python-backed selector execution as a planner prerequisite. Full suite on the merge candidate belongs to CI. Real fixtures must prove saved availability/reliability is reused, only unavailable calculations are reconstructed, true/false completeness cases, first use, corrupt sibling files, current-format refusal, skipped carry-forward, empty-feed reset, UTC deadlines, expired reliability-window contributions, and raw/monthly overlap across a month boundary.
- **Oracle:** Finalize real health Parquet, load it in a fresh planner, and reuse the saved availability/reliability values without reconstructing unchanged history; one missing calculation invokes only its own bounded recovery. This does not prove atomic failure counts across independent runners.
- **Verified scope:** Shared clock grouping now requires only its actual clock fields. Generic non-planner payloads and their compatibility rules are unchanged.

Table G

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Native TypeScript contract owns all new columns; stamp and changelog the current format. Reader and writer ship together because old formats are explicitly not supported. | User-directed clean break. |
| G2 | Keep lifecycle completeness separate from request-count and reliability completeness; retain computed values instead of treating one damaged field as an empty history. | User-directed partial-data behavior. |
| G3 | Record the breaking-format ruling in the owning living docs and amend conflicting planner compatibility wording in the same delivery. | Repository contract section 0. |
| G4 | Loading saved measurements does not mean recomputing them. At finish, update calculations with this run's known work; preserve their actual covered dates and diagnose unknown changes to a rolling window. | User-directed reuse and final update. |

Table H

| Id | Rejected alternative | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Another state ledger or JSON sidecar | Adds a second lifecycle authority and new persistence paths. | Additional writer, reader, retention and consistency rules. | User-directed scope. |
| H2 | Rebuild every calculation from full historical events | Repeats work and makes reads grow with history. | A separately priced bounded replay design and more retained evidence. | User requires saved calculations. |

## 4 - Row 2 - Switch concurrent HTTP planning and remove availability publication

- **Scope:** Complete the atomic cutover PR by connecting saved ledger calculations to all planning APIs, deleting JSON-dependent availability code, and keeping stage transport on real HTTP.
- **Files touched:**
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/collection-operation.ts`
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/src/api/parse-operation.ts`
  - `services/feed-ingest-plan/src/api/prepare-planning-health.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state-operation.ts`
  - `services/feed-ingest-plan/src/api/selection-operation.ts`
  - `services/feed-ingest-plan/src/availability/feed-availability.ts` (delete after replacement)
  - `services/feed-ingest-plan/src/availability/availability-config.ts` (delete after moving policy validation to the existing planning configuration contract)
  - `services/feed-ingest-plan/src/load-plan-inputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-http-client.ts`
  - `services/feed-ingest-plan/scripts/finalize-run-output.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/policy.test.ts`
  - `services/feed-ingest-plan/test/feed-availability-store.test.ts` (delete)
  - `services/feed-ingest-plan/test/feed-availability-transitions.test.ts` (replace with Row 1 coverage)
  - `services/feed-ingest-plan/test/feed-lifecycle-http.test.ts` (new)
  - `services/feed-ingest-plan/test/plan-test-server.ts` (new shared real loopback fixture)
  - `services/feed-ingest-plan/test/raw-day-members.test.ts`
  - `services/feed-ingest-plan/test/publication-recordings.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-policy-report.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts`
  - `packages/ledger-file-writer/test/planner-recordings.ts`
  - `tests/fixtures/feed-ingest-plan/health-field-history.json`
  - `config/feed-availability.json` (delete)
  - `config/feed-ingest-plan.json`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-availability.md`
  - `docs/architecture/publishing/committing.md`
- **Acceptance gates:** Same local selector and CI division as Row 1. Real ephemeral loopback listener and recorded source responses; generated local Git origin for publication. No external source requests or mocks. Start with no availability JSON files and prove no path is recreated. Demonstrate two independent runs from the same saved baseline, late publication, partial cancellation, saved-statistics reuse across API calls, and retained sibling output.
- **Oracle:** A real HTTP collection uses saved calculations, fetches/parses, and finalizes updated health through the existing safe publisher without any prior Git commit or availability JSON read/write; both concurrent run outputs survive publication. This does not promise a single check per feed across processes.

Table I

| Id | API | New responsibility; removed responsibility |
| --- | --- | --- |
| I1 | `POST /plan` | Orchestrate through real HTTP, reuse saved calculations, update them with this run's known work, and finalize known partial output; no availability commit queue. |
| I2 | `POST /collections` | Preflight catalog feeds using saved ledger calculations loaded by Table N; retain skip/carry-forward decisions for finalization; no enrollment read or state initialization. |
| I3 | `POST /fetch` | Apply this run's eligibility decision, record actual fetch evidence and classify terminal failures; no remote reservation. |
| I4 | `POST /parse` | Classify parsed validity and update the run's lifecycle calculation; preserve parser deadline and typed cancellation; no remote parse claim. |
| I5 | `POST /feed-health-state` | `summarize` returns this run's stored calculation; `record` finalizes updated availability/reliability and known partial values in health Parquet. Neither commits; final delivery uses F10. |
| I6 | Selection and partition APIs | Consume the same captured health calculation; preserve complete-collection selection and disabled-partition behavior. No in-process substitute for stage HTTP calls. |

Table J

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Remove `runtime.stage_fetch` fallback to `app.fetch`; internal planning calls use the actual configured loopback listener. Bump the dated HTTP route prefix if the response contract breaks; no old-prefix alias. | User-directed real HTTP design and no legacy compatibility. |
| J2 | Move the retained rest/recovery policy controls into the existing planning configuration and delete the standalone availability configuration, loader and state/enrollment/CAS controls. Preserve the safe publisher and current-format private SQLite operation replay. | User-directed JSON cleanup and single publication path; no replacement state file or renamed sidecar. |
| J3 | Interrupted/unpublished work does not create a source failure. Save known diagnostics and computed partial state during existing failure finalization whenever the process remains able to do so. | User-directed tolerance and retention of computations. |

Table K

| Id | Rejected alternative | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Serialized workflow or feed-wave ownership publication | Contradicts permitted overlapping runs or adds commits before work. | Queued runs or extra Git round trips. | User-directed concurrency ruling. |
| K2 | Sum saved cumulative streaks from parallel runs | Double-counts shared baseline evidence. | Exact reconciliation would require an explicit evidence-inclusion/replay contract, not arithmetic on snapshots. | User-approved snapshot semantics. |

## 5 - Row 3 - Remove planner legacy branches and obsolete delivery machinery

- **Scope:** Remove unused #1836 sidecar machinery and planner-owned old-format readers, tests and docs without deleting unrelated #1836 capabilities or historical data.
- **Files touched:** Provisional inventory from the architecture investigation; verify every listed path and all symbol references before execution, and add discovered callers to this row rather than deleting shared functionality blindly.
  - `packages/common-contracts/src/version.ts`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/schemas/feed-availability-state.schema.ts` (delete)
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `packages/common-contracts/src/schemas/discovered-article.schema.ts`
  - `packages/common-contracts/src/schemas/selected-article.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health-state.schema.ts`
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/test/feed-availability-state.test.ts` (delete)
  - `packages/common-contracts/test/article-identity-compatibility.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/data-delivery/src/compare-and-swap-data-contract.ts` (delete only if no remaining consumer)
  - `packages/data-delivery/src/safe-persist-data.ts`
  - `packages/data-delivery/src/index.ts`
  - `packages/data-delivery/test/safe-persist-data.test.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/operation-context.ts`
  - `services/feed-ingest-plan/src/api/operation-store.ts`
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/api/parse-operation.ts`
  - `services/feed-ingest-plan/test/feed-reliability.test.ts`
  - `services/feed-ingest-plan/test/article-source-outcome.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
  - `docs/reference/feed-planner-ledgers.md`
  - `docs/architecture/sources/planner-feed-history.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-availability.md`
  - `docs/architecture/publishing/committing.md`
  - `CLAUDE.md`
  - `.github/agents/fowler.agent.md`
  - `packages/ledger-file-writer/src/read-planner-file.ts`
  - `packages/ledger-file-writer/src/ledger-types.ts`
  - `packages/ledger-file-writer/src/registration.ts`
  - `packages/ledger-file-writer/test/planner-maintenance.test.ts`
  - `packages/ledger-file-writer/test/reader-integrity.test.ts`
  - `packages/ledger-file-writer/test/rejected-article-compatibility.test.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-url.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-identity.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/feed-identity.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/legacy-article-identity.ts` (delete after preserving current feed identity)
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/test/operation-format.test.ts`
  - `tests/fixtures/feed-ingest-plan/report-events.json`
- **Verified dependency boundary:** Generic non-planner file envelopes, host contracts, Python compatibility and published corpus formats remain unchanged. Removed availability/CAS APIs had no other consumers. Current feed identity still uses its existing normalization; it is not an old article reader.
- **Acceptance gates:** Same local selector and CI division as Row 1. Current-schema round trips succeed; old planner schemas and old operation receipts refuse with explicit diagnostics; current idempotent replay still avoids repeating completed work. Search the named planner/common-contract/delivery/doc inventory for removed sidecar, enrollment, CAS and legacy-format symbols; classify surviving current helpers by their actual consumer.
- **Oracle:** All current planner API journeys use one current format and ledger-only lifecycle, with no reachable sidecar publisher or old-format recovery path. This does not certify unrelated APIs outside the named scope.

Table L

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Interpret compatibility cleanup as TypeScript planner-owned code and shared contracts it owns. Surface any cross-language/shared API dependency before removal. | User asks for confusion to be surfaced; wording does not authorize arbitrary repository-wide deletion. |
| L2 | Retain current-format operation idempotency, independent parser deadline, global collection, age policies, disabled-worker assignment, partial output and diagnostics. These are capabilities, not old-version compatibility. | Preserve #1836 functionality. |
| L3 | Split purely structural deletions from behavioral old-format refusal into separate commits within the PR. Do not add a dual-format rollout. | User-directed clean break and architecture advisor's two-hat discipline. |
| L4 | Amend planner-specific migration language in the engineering contract and advisor instructions; do not weaken unrelated payload families. | User-directed no-migration exception; repository contract section 0. |
| L5 | Remote commit `f2303b44bbb477d2497b4ad7a785033137863840` removed the two availability state/enrollment JSON files. Remove their code dependencies rather than restoring them, reconstructing them, or treating their absence as permission to initialize another store. | Verified remote deletion and user-directed cleanup, 2026-10-31 UTC. |

Table M

| Id | Rejected alternative | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Revert #1836 wholesale | Removes requested HTTP orchestration, parser limits, policy controls and diagnostics. | Reimplement those capabilities separately. | User asks to retain functionality. |
| M2 | Delete every helper containing the word legacy | A filename can contain current identity/error helpers used by current APIs. | Audit actual branches and consumers; remove only obsolete behavior. | Precise cleanup requirement. |

## 6 - Saved health read and finish

Table N

| Id | Step | Input and behavior |
| --- | --- | --- |
| N1 | Capture available input once | History preparation selects current remote main once. Use the existing publication inventory, compact-period lists and exact raw-day Git membership to stage only the configured health dates/periods. The bounds remain the configured lifecycle/reliability windows and `health_period_limit`; no full repository or history scan and no availability JSON reads. |
| N2 | Read the existing health ledger | Read `state/raw/feed-ingest-plan/feed-health-state/YYYY/MM/DD/<uuid>.parquet` and the selected files under `state/compact/feed-ingest-plan/feed-health-state/`. Raw and compact bytes belong to the same captured revision. File caching is scoped to this capture. |
| N3 | Reuse saved calculations | For each catalog feed/address, select the newest coherent saved availability and reliability calculation. Read its saved columns directly, including existing reliability counts, fractions, covered dates and completeness. Do not derive a second answer from all old check results when a usable saved answer exists. |
| N4 | Recover only unavailable calculations | If a calculation is absent or unusable, use the corresponding known check facts in this already bounded input. Recover only that calculation, not unrelated metrics. With insufficient evidence, retain known values and explicit unknowns; do not fabricate zeros, successful checks or retirement. This is not an old-format migration. |
| N5 | Keep the run's calculation | Reuse this run-owned calculation across HTTP API calls. A rest deadline still needs a current UTC comparison; that comparison is not a history recount. Other runs can publish meanwhile, without changing this run's captured input or blocking it. |
| N6 | Update at finish | Apply this run's actual completed checks and request/article accounting once. Update availability and reliability for their defined periods, then save the results and completeness flags. When a rolling reliability period changes, adjust only known entering/leaving contributions; missing contributions remain diagnosed and incomplete rather than an exact invented total. Do not relabel unchanged old measurements as covering newer dates. |
| N7 | Save and publish once through the existing path | Health recording writes finalized Parquet for this run, including supported calculations for skipped feeds. The existing finalizer submits its completed metadata files to `safe_persist_data`; no fetch/parse/summary state commit, replacement JSON store, or extra lifecycle-only commit. |

Table O

| Id | `availability_complete` value | Example and consequence |
| --- | --- | --- |
| O1 | `true` | A valid parsed feed resets its known failure episode; status is eligible and streak is zero. Earlier missing failure history cannot invalidate that observed reset. |
| O2 | `true` | A supported saved streak plus this run's confirmed failure establishes a rest deadline. The feed waits until that UTC time. |
| O3 | `false` | No usable prior lifecycle calculation or enough check evidence exists. The feed remains unknown and may be checked if active in the catalog. |
| O4 | `false` | A supported rest deadline survives, but the recovery count is unavailable. Keep the deadline and wait; do not guess the count or establish retirement from it. |
| O5 | `false` | Required outcome ordering is ambiguous or check evidence conflicts. Preserve the records and diagnosis; do not pretend the whole calculation is known. |

Table P

| Id | Plain-language rule | What is saved |
| --- | --- | --- |
| P1 | The same check may appear in an original file and a packed file; count it once. | One logical check's contribution, with its existing identity and actual work time. |
| P2 | A skipped feed still needs its last supported decision in the next run's report. | Copy its calculation into ordinary health output, with no new check or request count. |
| P3 | If every usable record disappears, there is no evidence from which to recover the decision. | Explicit unknown values and diagnostics, not guessed health or restored JSON files. |
