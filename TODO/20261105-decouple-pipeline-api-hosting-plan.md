# Decouple shared pipeline API hosting

**Last Updated**: 2026-11-05
**Level**: 5 - change core hosting dependencies and private startup controls.

## 0. Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Let a pipeline serve its own local APIs without installing another pipeline's implementation or reading its configuration. |
| A2 | Hard scope - in | - Keep the existing shared hosting package and one listener per active task.<br>- Separate common process controls from native API setup.<br>- Remove feed dependencies from machine-only execution.<br>- Preserve real measurements, failure reporting, shutdown and retained evidence.<br>- Update callers, installation, tests and current documentation together. |
| A3 | Hard scope - out | Table B prices the excluded work. |
| A4 | Chosen strategy | One atomic PR using existing Hono composition, Bun process controls and Zod validation; Fowler's construction ruling places native assembly in the existing API packages. |
| A5 | PR shape | One reversible outcome, with a structural commit followed by a configuration-and-caller commit; each carries its related tests. Do not merge an intermediate dependency cut. |
| A6 | ESCALATE triggers | 1. Any required change to public API behavior, saved measurement meaning, committed payloads or existing evidence shapes beyond Table D.<br>2. A dependency cycle, weakened native validation or loss of original or cleanup failures.<br>3. A need for a new runtime, third-party library, dynamic loader or changed trust boundary.<br>4. Concurrent work that changes the listed interfaces or moves the same tests. |
| A7 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 because hosting, native assembly and caller migration share one dependency cut; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

Table B - Exclusions and their cost

| Id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Delete shared hosting and start separate native listeners | Common lifetime code remains, but both workflows keep one controlled listener rather than gaining extra processes, ports and cleanup paths. | A requirement for independently deployed API lifetimes that justifies migrating readiness, cancellation, reporting and both workflows. |
| B2 | Arbitrary API loading from YAML, HTTP input or module discovery | A new API still needs an implemented native assembly, explicit startup wiring and tests; editing workflow YAML alone cannot add an API. | A separately reviewed extension requirement with a trusted registration format and a concrete consumer. |
| B3 | Combine Python generation or scoring with the Bun listener | The summary workflow still manages its Python model server separately; this PR removes feed coupling, not runtime boundaries. | A cross-runtime design covering model lifetime, resource controls, validation and failure reporting. |
| B4 | Change orchestration or move feed execution into hardware APIs | GitHub Actions and the existing TypeScript runner continue to sequence the feed stages. | A demonstrated sequencing requirement that those existing components cannot meet. |
| B5 | Published-site changes, ledger redesign or dependency upgrades | Reader behavior, saved pipeline data and locked third-party versions stay unchanged. | A separate requirement with its affected contracts and readers identified. |
| B6 | Edit CLAUDE.md or AGENTS.md | Policy files stay unchanged; no policy exception is part of this design. | A separate explicit request for the relevant policy change. |

Table C - Responsibility destinations

| Id | Responsibility | Destination and rule |
| --- | --- | --- |
| C1 | Listener, common health identity, request lifetime and awaited close | Keep `services/serve-pipeline-apis/src/create-api-app.ts`; accept a native-built application instead of importing native handlers. |
| C2 | Parent and child process lifetime | Replace the feed-owned `services/feed-ingest-plan/scripts/http-child-lifetime.ts` with `services/serve-pipeline-apis/src/supervise-http-child.ts` and `services/serve-pipeline-apis/src/run-http-child.ts`. Separate the parent and child responsibilities; leave no forwarding export. |
| C3 | Feed API assembly and child entry | Add `services/feed-ingest-plan/scripts/create-feed-api-app.ts` and `services/feed-ingest-plan/scripts/serve-feed-apis.ts`. Planning composes existing feed operations with C4; delivery composes the existing safe-persist handler. The entry dispatches; native modules perform the work. |
| C4 | Machine API assembly, child entry and supervisor adapter | Add `services/host-probes/src/api/create-machine-app.ts`, `services/host-probes/src/api/serve-machine-apis.ts` and `services/host-probes/src/api/supervise-machine-api-task.ts`. Compose existing fingerprint and probe implementations; do not move their operation logic. |
| C5 | Native private startup and readiness | Add `services/feed-ingest-plan/scripts/read-feed-api-startup.ts`, `services/feed-ingest-plan/scripts/read-feed-api-readiness.ts` and `services/host-probes/src/api/read-machine-api-startup.ts`. Keep common identity comparison in the shared readiness module; keep planner runtime and delivery health checks in the feed package. |
| C6 | Native failure conversion | Add `services/feed-ingest-plan/scripts/capture-feed-api-failure.ts` and `services/host-probes/src/api/capture-machine-api-failure.ts`. Feed conversion retains the existing planner capture helpers; machine conversion has no feed import. |
| C7 | Native diagnostic projection | Add `services/feed-ingest-plan/scripts/read-feed-api-diagnostic.ts` and `services/host-probes/src/api/read-machine-api-diagnostic.ts`. Feed projection composes machine projection with feed events and delivery completion. |
| C8 | Concrete profile validation in server evidence | Add `services/host-probes/src/api/create-machine-server-evidence.ts`, binding the shared evidence-schema constructor to the existing native profile schema. Feed reporting and the summary helper use this validated binding. |
| C9 | Feed workflow sequencing | Retain `services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts`, `services/feed-ingest-plan/src/run-feed-plan.ts` and the existing Actions step order. They prepare the run, sequence HTTP stage calls and retain outputs; the shared host does not orchestrate them. |
| C10 | Summary workflow sequencing | Retain `.github/scripts/summary-eval-tests/summary_eval_pipeline/phases.py`; its machine helper uses C4. Generation and scoring remain on their existing Python API. |

Table D - Configuration and compatibility brief

| Id | Surface | Declared rule |
| --- | --- | --- |
| D1 | Dependency direction | The shared package depends only on common-contracts, Hono and Zod at runtime, plus its existing development tools. Host-probes adds explicit dependencies on the shared package, host-fingerprints and the existing locked Hono version for native composition. Feed-ingest-plan declares the shared package, host-probes and host-fingerprints used by its retained native callers. No reverse native dependency remains in shared source, tests, fixtures, manifests or locks. |
| D2 | Common supervision configuration | Move `supervision` from `config/feed-ingest-plan-service.json` to `config/hono-server.json`. Retain the current waits: `readiness_timeout_ms = 30000` bounds readiness, `shutdown_timeout_ms = 10000` bounds graceful close, and `forced_exit_timeout_ms = 5000` bounds forced-exit confirmation and existing diagnostic draining. Read them from the shared settings schema; do not keep a feed fallback or second authority. |
| D3 | Listener and native limits | Retain the existing shared address and idle-timeout settings. Body and private-control byte limits still come from the applicable native configuration; preserve their current selection rules rather than adding a duplicate shared knob. |
| D4 | Private startup | Shared declarations cover common host controls and readiness identity. Native declarations cover complete startup packets and native failure codecs. Current callers and children cut over together: these are same-run private packets, not restart stores. Composed tasks capture D2 under `server.supervision`; remove the obsolete nested feed value. Reject missing controls by name. |
| D5 | Protocol identity | Retain current readiness and failure event strings, child-kind error prefixes, producer identifiers, health paths and planning/machine/delivery group meanings. Source entry paths become explicit trusted caller choices, never fields in HTTP input or configuration. A new task-group vocabulary would require its own contract change. |
| D6 | Server evidence | Preserve filenames, fields, current version, log naming, group vocabulary and existing read compatibility, including defaulting absent `reported_profiles` to an empty list. Parameterizing the profile validator does not change saved evidence. Do not replace native profile validation with arbitrary JSON. |
| D7 | Failures | Preserve planner error codes, safe frames, execution context, cancellation classification and original-plus-cleanup causes through the existing feed helpers. Machine handling retains safe coded process failures and both causes without importing or copying planner capture machinery. Preserve current codes in retained evidence, including compatibility names. |
| D8 | Diagnostics | Preserve body-free live events, append-only optional mirrors, the safe unavailable-mirror warning and shutdown-only profile capture. Profile deduplication retains native operation identity; a successful profile is not emitted again as an error or measurement dump. |
| D9 | Existing operation results | Preserve native routes, request/response meaning, enablement, feed stage-origin binding, actual fingerprint writes, sample/profile contents, delivery behavior and Python phase receipt meanings. No committed ledger or historical-file migration is required. |
| D10 | New schema work | Declare the private controls and typed library boundaries before changing readers or writers. The authored configuration move needs no new persisted contract family. A wire-shape change not already described here fires A6 rather than silently reusing a version. |

Table E - Minimal library boundaries

| Id | Boundary | Required input and result |
| --- | --- | --- |
| E1 | Hosted application | Native construction provides `fetch`, awaited `close` and its configured request-body bound. Shared construction provides cancellation, the configured origin and existing request-idle/activity facilities. Native assembly binds those facilities to the existing planner and delivery hooks. |
| E2 | Supervised child | Require a statically selected entry, validated native startup, common controls, expected identity, a readiness callback and the task request. Remove the implicit shared native entry. Keep private pipes, finite waits, exact-child ownership, parent-loss handling and diagnostic draining. |
| E3 | Failure policy | Pass typed error creation, capture, cleanup retention and startup-failure serialization at the existing lifecycle decision points. Feed policy creates `PlanError` before native capture where a code must survive. Do not introduce an error registry or a generic clone of planner diagnostics. |
| E4 | Readiness | Shared code checks private readiness, spawned PID, nonce, configured port, modules, enablement and uncached shared HTTP health. Feed code additionally validates native planner/delivery identity and captured runtime controls before the request can run. |
| E5 | Diagnostic decoder | A native decoder returns one typed result: ignored, invalid, safe server event, or validated profile with its operation identity. Shared logging handles only that result; raw diagnostic text cannot supply paths, event producers, headers or message bodies. Invalid diagnostics remain visible warnings. |
| E6 | Evidence reader/writer | Construct the common evidence model with the native profile schema and pass that model to shared retention/readback. Return types retain the native profile type. Keep envelope declarations in the shared package and profile semantics in their existing native module. |
| E7 | Composition method | Use ordinary Hono application composition and explicit source imports. These are typed in-process construction arguments; only validated JSON-shaped payloads cross the child pipe or stage HTTP boundary. There is no plugin protocol, service locator or code loader. |

## 1. Status Reckoner

Table F - Delivery outcome

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 1 | Serve native pipeline APIs without feed-dependent hosting | - | A | IN-FLIGHT | independent-api-hosting | - | - |

## 2. Independent hosting and native composition

### Row #1 - Serve native pipeline APIs without feed-dependent hosting

- **Scope:** Deliver Tables C-E as one PR so both existing workflows retain their operations while machine-only use no longer needs feed code or configuration.

**Task order:**

1. Reconcile this inventory with the current branch and published changes. Search each moved module, export and test filename before editing. The earlier service rename is not part of this dependency refactor.
2. Declare the shared controls and E1-E6 types. Replace native imports in the shared startup, readiness, evidence and event modules with the declared inputs. In the structural commit, native callers pass their existing validated controls and retain current configuration and packet layouts; apply D2-D4 only at step 7.
3. Extract C2 with its real process behavior intact. Wire native failure policies at every existing failure and cleanup point, including private startup failure and forced child close; do not convert everything to plain `Error`.
4. Build C3-C8 in the existing native packages. Reuse the current operation implementations. Remove native execution from the shared entry; delete that entry instead of keeping an unused dispatcher or barrel. Repair manifest exports and all callers in the same commit.
5. Relocate native integration coverage to its actual packages. Split the mixed composition and diagnostic tests by responsibility without repeating cases. Preserve feed report/artifact assertions in the feed package and real machine-worker cases in host-probes; shared tests must not import native services.
6. Refresh affected locks with the existing package manager, without dependency upgrades. Complete the structural commit with its tests before moving configuration authority.
7. Apply D2-D4 to current writers and readers together. Remove the feed configuration read from the summary helper, including its profile-stop deadline calculation. Remove that configuration from summary preparation and its generated fixtures. Update both workflows and CI installation order to the new dependency direction.
8. Add G7's isolated checks and the focused machine test. Keep ordinary integration tests usable in the normal checkout; physical source absence is a property of the isolated CI checkout, not a reason to skip a test in the normal suite.
9. Update the named living docs, their existing design rationale and the active identity plan's moved test pointer and corresponding package command. Keep the completed rename inventory as history; do not rewrite it into a second active plan.
10. Run Table G, record selected inputs and results, inspect native dependency removal and submit the single PR. Do not dispatch a data-writing workflow to prove the refactor.

**Files touched - shared library:**

- `services/serve-pipeline-apis/package.json`
- `services/serve-pipeline-apis/bun.lock`
- `services/serve-pipeline-apis/src/api-startup.ts`
- `services/serve-pipeline-apis/src/create-api-app.ts`
- `services/serve-pipeline-apis/src/index.ts` - delete after moving native execution.
- `services/serve-pipeline-apis/src/load-settings.ts`
- `services/serve-pipeline-apis/src/read-api-readiness.ts`
- `services/serve-pipeline-apis/src/read-server-evidence.ts`
- `services/serve-pipeline-apis/src/server-evidence.ts`
- `services/serve-pipeline-apis/src/supervise-api-task.ts`
- `services/serve-pipeline-apis/src/write-server-event.ts`
- `services/feed-ingest-plan/scripts/http-child-lifetime.ts` -> `services/serve-pipeline-apis/src/supervise-http-child.ts`
- `services/serve-pipeline-apis/src/run-http-child.ts` - extract the child half.

**Files touched - native construction and current callers:**

- `services/feed-ingest-plan/package.json`
- `services/feed-ingest-plan/bun.lock`
- `services/feed-ingest-plan/src/config/service-settings.ts`
- `services/feed-ingest-plan/scripts/create-feed-api-app.ts`
- `services/feed-ingest-plan/scripts/serve-feed-apis.ts`
- `services/feed-ingest-plan/scripts/read-feed-api-startup.ts`
- `services/feed-ingest-plan/scripts/read-feed-api-readiness.ts`
- `services/feed-ingest-plan/scripts/capture-feed-api-failure.ts`
- `services/feed-ingest-plan/scripts/read-feed-api-diagnostic.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts`
- `services/feed-ingest-plan/scripts/safe-persist-http-client.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-report.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-server-artifacts.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-server-report.ts`
- `services/host-probes/package.json`
- `services/host-probes/bun.lock`
- `services/host-probes/src/api/create-machine-app.ts`
- `services/host-probes/src/api/serve-machine-apis.ts`
- `services/host-probes/src/api/supervise-machine-api-task.ts`
- `services/host-probes/src/api/read-machine-api-startup.ts`
- `services/host-probes/src/api/capture-machine-api-failure.ts`
- `services/host-probes/src/api/read-machine-api-diagnostic.ts`
- `services/host-probes/src/api/create-machine-server-evidence.ts`
- `.github/scripts/summary-eval-tests/machine-task.ts`
- `.github/scripts/summary-eval-tests/summary_eval_pipeline/model_selection.py`
- `config/hono-server.json`
- `config/feed-ingest-plan-service.json`

**Files touched - tests and native recordings:**

- `services/serve-pipeline-apis/test/api-composition.test.ts` -> `services/feed-ingest-plan/test/serve-feed-apis.test.ts` - retain feed composition here; place machine-only cases in the named machine test.
- `services/serve-pipeline-apis/test/profile-retention.test.ts` -> `services/feed-ingest-plan/test/retain-api-profiles.test.ts`
- `services/serve-pipeline-apis/test/recorded-machine-api.ts` -> `services/host-probes/test/serve-recorded-machine-api.ts`
- `services/serve-pipeline-apis/test/profile-api-server-recording.ts` -> `services/host-probes/test/run-recorded-machine-api-child.ts`
- `services/serve-pipeline-apis/test/profile-report-recording.ts` -> `services/host-probes/test/report-recorded-task-profile.ts`
- `services/serve-pipeline-apis/test/server-events.test.ts` - retain generic writer cases; move native cases to the named machine event test.
- `services/serve-pipeline-apis/test/write-server-events.ts`
- `services/serve-pipeline-apis/test/supervise-http-child.test.ts`
- `services/serve-pipeline-apis/test/run-host-lifetime.ts`
- `services/serve-pipeline-apis/test/check-api-dependencies.test.ts`
- `services/host-probes/test/serve-machine-apis.test.ts`
- `services/host-probes/test/record-machine-api-events.test.ts`
- `services/host-probes/test/check-machine-api-dependencies.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-host.test.ts`
- `services/feed-ingest-plan/test/safe-persist-http.test.ts`
- `services/feed-ingest-plan/test/planner-server-recording.ts`
- `services/hhem-evaluator/tests/host-profile-bridge.ts`
- `services/hhem-evaluator/tests/test_manual_workflow.py`
- `services/hhem-evaluator/tests/test_pipeline_preparation.py`
- `frontend/scripts/tests/test-scope.test.mjs`

**Files touched - workflow wiring and living documentation:**

- `.github/workflows/ci.yml`
- `.github/workflows/feed-ingest-plan-test.yml`
- `.github/workflows/summary-eval-tests.yml`
- `docs/reference/serve-pipeline-apis.md`
- `docs/reference/summary-evaluation-workflow.md`
- `docs/reference/host-probe-api.md`
- `docs/reference/repository-layout.md`
- `docs/architecture/sources/feed-plan-runner.md`
- `docs/architecture/sources/feed-operator-api.md`
- `docs/how-to/run-feed-ingest-plan-test.md`
- `docs/how-to/run-hhem-evaluation-api.md`
- `docs/how-to/run-the-gates.md`
- `TODO/20261104-align-typescript-article-identity-plan.md`
- `TODO/20261105-decouple-pipeline-api-hosting-plan.md`

**Acceptance gates:**

Table G - Local checks, CI checks and observations

| Id | Where | Check and required result |
| --- | --- | --- |
| G1 | Local | Inspect `npm run test:changed -- --list` from `frontend/`; use [independent native gate selection](../docs/how-to/run-the-gates.md#independent-typescript-packages-and-services). Record the selected paths, commands, results and tested source. Do not run a Python-backed full suite as a native development prerequisite. |
| G2 | Local | Run declared `check` scripts in the shared host, host-probes and feed-ingest-plan after their changed dependency graphs are prepared. Run the shared package's declared test script and one host-probes invocation selecting the new machine/dependency/event tests. Frozen installs must resolve the new acyclic graph without unrelated version changes. |
| G3 | Local | In feed-ingest-plan, use one declared test invocation selecting the moved composition/profile tests and existing supervisor, safe-persist, workflow, host, delivery, report and finalization tests. Retain one-port behavior, disabled planning, native health checks, actual outputs, shutdown reports and artifacts. |
| G4 | Local | Generic lifecycle and native adapter cases preserve occupied-port refusal, wrong readiness identity, early exit, readiness timeout, cancellation, parent-pipe loss, bounded forced exit, diagnostic draining and original-plus-cleanup failure retention. Use real children and recorded source/process inputs; do not add mocks or external-network calls. |
| G5 | Local | Run the existing caller-launcher compiler command from the evaluator CI job against the summary helper and native profile bridge. Run evaluator preparation/workflow/profile-reader tests in their existing environment, plus Ruff on changed Python inputs. Verify the prepared runtime contains the named machine configuration and no feed service configuration. |
| G6 | Local | Run `node --test scripts/tests/test-scope.test.mjs` from `frontend/`. Replace the retired lifetime path and include the native entries in the existing case for both path separators. Existing prefix selection already covers these packages; add no new test group or broad rule. Inspect remaining moved-name matches and changed documentation links. |
| G7 | CI, existing evaluator job | Add an isolated sparse checkout at `backend/var/checks/api-host-isolation`. Initially include only the common-contracts package, shared package and their named configuration/test inputs; assert that native service directories are absent, then perform a frozen install, type check and shared tests. Expand the same checkout with the ledger writer, fingerprint/probe packages, summary machine helper, their named config files and recorded host fixtures, but never feed source or feed configuration. Install that closure and run the focused machine/dependency cases against real source entries. Keep the normal evaluator job and its existing full suite; add no job matrix. |
| G8 | CI | On Linux, require real fingerprint output, real profile start/stop and shutdown-only report retention from G7. Verify expected child identity, listener release, worker exit, actual evidence and native profile validation. An all-skipped or Windows-only result does not certify these process boundaries. |
| G9 | CI | Require the normal full merge-candidate suite once. Preserve all relocated native cases in their normal package commands and keep the evaluator compiler, Python compatibility and workflow checks. Do not remove coverage because it left the shared package. |
| G10 | Next normal use, not a merge gate | Observe the next existing feed and summary executions: check readiness, final server evidence, final profiles and available log artifacts. Correct a missed staging or entry path without changing protocol identifiers. Do not trigger a workflow that writes pipeline data merely to obtain this observation. |

- **Oracle:** The isolated machine check in G7-G8 must complete a real fingerprint/profile task when feed source and feed configuration are physically absent. Pair it with generated Bun dependency metadata over a fixed list of shared exports, the native machine entry and the summary helper: shared graphs must contain no native service implementation; machine graphs must contain no feed package. The absence assertion or dependency check must reject the current coupled implementation; the real behavior checks must pass before and after the refactor. This oracle cannot establish hosted feed delivery, model scoring quality or performance improvement.

**Decisions:**

Table H - Construction and delivery decisions

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | Keep shared hosting, but make native packages construct their applications and controls. The current inverse dependency is removed rather than hidden behind lazy imports. | Fowler construction ruling; current manifests and shared startup/supervisor imports. |
| H2 | C4 belongs in host-probes because it already manages sampling and profiles; adding fingerprint composition there needs no extra service package. Fingerprint implementation remains independent. | Fowler construction ruling; existing native package dependency directions. |
| H3 | D2 has one configuration authority because machine use must not load feed settings merely to obtain process deadlines. This is a cutover of current authored inputs, not a historical-data migration. | Current summary helper reads the feed service schema for supervision; Fowler construction ruling. |
| H4 | E3 preserves planner failures at the native boundary. Passing arbitrary new errors to existing planner capture would replace lifecycle codes with the generic planning failure code. | Existing `withPlannerFailure` behavior and C2's direct `PlanError` use. |
| H5 | Keep the native profile model in its existing module and bind it through E6. Its refinements depend on native configuration and process-reader vocabularies, not merely a field list. | Existing profile-schema imports; Fowler construction ruling. |
| H6 | Preserve diagnostic projection as a typed native function, including shutdown profiles. Removing native imports from the logger must not remove failed operation visibility or final measurements. | Existing shared event writer, profile-retention test and native report readers. |
| H7 | A new API supplies a real native assembly and the fixed E1-E6 construction inputs. This is reusable hosting, not a promise that workflow configuration can create an API. | Existing Hono composition facilities; Fowler construction ruling. |
| H8 | Use Bun's existing JSON dependency metadata for named entries, and execute source entries separately. Do not execute a bundle and assume worker URL paths remain correct after bundling. | Installed Bun build capability and existing profile-worker startup. |
| H9 | Retain bounded inputs: named exports and entries for dependency checks, named sparse inputs for isolation, and generated run directories for artifacts. No committed-tree walk or production-corpus scan is introduced. | CLAUDE.md sections 1 and 13; existing fixed workflow inventories. |
| H10 | Keep one PR because the reverse import edges, native child entries, error policies and validators must change together. Two commits separate the structural change from the final configuration cutover without publishing a broken intermediate deployment. | Fowler construction ruling; shared package and caller dependency graph. |
| H11 | Record implemented architecture in the existing living pages. Keep the shared reference whole: it still answers one question about a task's listener, lifetime and evidence. Update the active identity plan's test location, not its design or status. | Existing reference-page scope and documentation split rule. |
| H12 | Reuse existing Hono, Bun and Zod; introduce no third-party library or runtime framework. Host-probes gains the shared-host and fingerprint dependency closure, while machine-only workflows stop installing feed code. Browser cost is unchanged; no size or speed improvement is claimed. The isolated CI preparation proves the distinct missing-dependency failure. | Existing dependencies and the distinct source-absence failure mechanism. |

**Rejected alternatives:**

Table I - Alternatives and their cost

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Delete shared hosting | It repeats lifetime controls and adds listener/process coordination without improving the selected shared-host outcome. | Separate native supervisors plus migrations of readiness, cancellation, logs, evidence, ports and both workflow callers. | Fowler construction ruling; current common lifetime behavior. |
| I2 | Change only eager imports to lazy imports | The manifest, startup schemas, supervision settings, errors, profile validation and tests would still depend on native feed code. | Retain those dependencies or perform the same native-boundary extraction later; laziness alone cannot pass the isolation oracle. | Current direct imports and dependency declarations. |
| I3 | Move the profile schema wholesale into common-contracts | It carries native configuration and process-reader vocabulary with it, widening a shared package for no new reader. | Move that vocabulary and its validation together, audit every profile reader and update native contract tests; E6 avoids that migration. | Existing profile schema and Fowler construction ruling. |
| I4 | Store opaque profile JSON or drop profile capture | A clean import graph would conceal invalid or lost shutdown measurements. | Define and migrate a different evidence contract, change readers and accept weaker validation or missing final samples. | Current evidence model and real profile-retention coverage. |
| I5 | Add a plugin registry or another composition package | Existing static construction meets the actual callers; another layer would add registration, configuration and packaging contracts. | Define those contracts, maintain another package or loader and test registration failures before any API gains behavior. | Existing Hono facilities and Fowler construction ruling. |
| I6 | Ship the host extraction, native moves and caller repairs in separate PRs | Their shared imports and private packet readers cannot be independently cut over without extra compatibility code. | Temporary aliases or parallel entry paths, repeated lock/CI changes and a removal PR; no separate deployed capability justifies them. | Current dependency cut and single-task listener contract. |
| I7 | Rename protocol identifiers while extracting the host | Those identifiers are compatibility values, not source module lookups. | Inventory every reader, version affected shapes and define old-value compatibility for no hosting benefit. | Existing listener/evidence contracts and D5. |
