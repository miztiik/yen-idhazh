# Rename the shared pipeline API service

**Last Updated**: 2026-11-05
**Level**: 3 - move the service and its cross-package, workflow and evaluation callers together; preserve behavior.

## 0. Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Give the shared local pipeline API server a name that describes its purpose rather than its implementation language. |
| A2 | Hard scope - in | - Move the complete service and align its package identity.<br>- Repair callers, workflow inputs, test selection and existing tests.<br>- Rename the service reference page and repair its links, commands and active-plan pointers.<br>- Preserve all existing operations and process-lifetime behavior. |
| A3 | Hard scope - out | Table B prices the excluded work. |
| A4 | Chosen strategy | One atomic rename PR, following the existing [listener contract](../docs/reference/serve-pipeline-apis.md); no architecture or payload redesign. |
| A5 | ESCALATE triggers | 1. Any required route, payload, protocol identifier, producer identity or saved-data change.<br>2. Any proposed runtime redesign, dependency upgrade or change outside the listed rename surfaces.<br>3. Concurrent work that changes the same service or its callers and cannot be retained by updating this inventory. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the row directly; parallel N = 1 because the move and caller updates form one reversible outcome; honor the ESCALATE triggers in section 0. Stop with an open PR; do not merge. |
| A7 | PR shape | One rename-only PR containing the move, all caller and gate updates, existing regression coverage and current documentation. No intermediate broken-path PR. |

Table B - Exclusions and their cost

| Id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Renaming wire identifiers, event producer URIs, configuration filenames or evidence filenames | Some existing machine-facing identifiers retain technology-based names; previous readers and observations keep their current meaning. | A separate contract review covering every affected writer, reader and compatibility rule. |
| B2 | Moving native operation logic into this package, replacing the server or changing dependencies | The existing composition and direct caller imports remain; this change improves naming, not architecture. | A separately scoped requirement with a measured defect or missing capability. |
| B3 | Published-site changes | No reader-facing layout or behavior changes, and no new browser journey. | A change that actually affects the published site. |
| B4 | Editing CLAUDE.md or AGENTS.md | Existing policy text stays unchanged; the rename does not require either file to change. | A separate explicit request to edit the relevant file. |

Table C - Names that move

| Id | Surface | Source name | Destination |
| --- | --- | --- | --- |
| C1 | Service directory | `services/typescript-api/` | `services/serve-pipeline-apis/` |
| C2 | Private package identity | `@idhazh/typescript-api` | `@idhazh/serve-pipeline-apis` |
| C3 | Canonical reference page | `docs/reference/typescript-api-server.md` | `docs/reference/serve-pipeline-apis.md` |
| C4 | Human-facing reference title | Shared TypeScript API server | Serve pipeline APIs |
| C5 | CI preparation step | Prepare composed TypeScript API dependencies | Prepare pipeline API dependencies |
| C6 | CI server-check step | Composed TypeScript APIs and owned server lifetime | Pipeline APIs and owned server lifetime |

Table D - Compatibility retained

| Id | Surface | Required invariant |
| --- | --- | --- |
| D1 | HTTP and private control | Keep route paths, request/response shapes, startup and readiness packets, group names, exports, error codes, enablement and cancellation behavior unchanged. Retain the `typescript_api` and `TYPESCRIPT_API` protocol identifiers and their existing derived event/error values. |
| D2 | Event provenance | Keep `config/typescript-event-sources.json` unchanged, including its `/services/typescript-api` producer URI. It identifies the same producer; it is not a source-file lookup or fetch destination. Existing `/fixtures/typescript-api` test producer URIs are also identifiers, not stale imports. |
| D3 | Configuration and task evidence | Keep `config/hono-server.json`, listener settings, log/evidence filenames, contract versions and saved meanings unchanged. |
| D4 | Dependency graph | Keep dependency declarations, locked versions, integrity data and package export entry points unchanged; refresh only the moved package identity in its lockfile with the existing package manager. |
| D5 | Existing work | Update only rename-related paths and labels in the other active plan; do not change its row status, scope or design. |

## 1. Status Reckoner

Table E - Delivery outcome

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Rename the shared pipeline API service without changing behavior | - | A | IN-FLIGHT | literate-telegram | - | - |

## 2. Rename and caller repair

### Row #1 - Rename the shared pipeline API service without changing behavior

- **Scope:** Ship the name mapping in Table C across the complete service, its callers, checks and documentation while retaining Table D.

**Task order:**

1. Recheck the working tree and search tracked and authored files for the source directory, package name and reference-page name in Table C. Reconcile this inventory with concurrent changes before moving files.
2. Move the complete tracked service tree, update the manifest identity and purpose description, and refresh its lockfile without dependency upgrades. Change human-facing service comments and error messages to describe pipeline APIs; do not change protocol literals.
3. Repair planner, delivery, reporting and evaluation imports, including the evaluation helper's direct dependency import. Preserve their existing import patterns and operation implementations.
4. Repair every install command, working directory, sparse-checkout entry, fixed workflow-test inventory and test-selector rule. Update the existing selector tests for the destination path with both path separators, and update the workflow tests alongside renamed step labels.
5. Move the canonical reference page, update current cross-links and commands, including this plan's live links, and repair the active identity plan's path references. State the service's purpose first: it serves existing pipeline operations on one local listener for the lifetime of a task. In the reference page's existing design rationale, explain D2 without adding approval history.
6. Run the named checks below, inspect remaining source-name matches against Table D and this plan's move inventory, and submit the move and all repairs as one PR. Keep the same operations, tests and failure guarantees; add no forwarding directory or alternate implementation.

**Files touched - service moves:**

- `services/typescript-api/package.json` -> `services/serve-pipeline-apis/package.json`
- `services/typescript-api/bun.lock` -> `services/serve-pipeline-apis/bun.lock`
- `services/typescript-api/tsconfig.json` -> `services/serve-pipeline-apis/tsconfig.json`
- `services/typescript-api/src/api-startup.ts` -> `services/serve-pipeline-apis/src/api-startup.ts`
- `services/typescript-api/src/create-api-app.ts` -> `services/serve-pipeline-apis/src/create-api-app.ts`
- `services/typescript-api/src/index.ts` -> `services/serve-pipeline-apis/src/index.ts`
- `services/typescript-api/src/load-settings.ts` -> `services/serve-pipeline-apis/src/load-settings.ts`
- `services/typescript-api/src/read-api-readiness.ts` -> `services/serve-pipeline-apis/src/read-api-readiness.ts`
- `services/typescript-api/src/read-server-evidence.ts` -> `services/serve-pipeline-apis/src/read-server-evidence.ts`
- `services/typescript-api/src/server-evidence.ts` -> `services/serve-pipeline-apis/src/server-evidence.ts`
- `services/typescript-api/src/supervise-api-task.ts` -> `services/serve-pipeline-apis/src/supervise-api-task.ts`
- `services/typescript-api/src/write-server-event.ts` -> `services/serve-pipeline-apis/src/write-server-event.ts`
- `services/typescript-api/test/api-composition.test.ts` -> `services/serve-pipeline-apis/test/api-composition.test.ts`
- `services/typescript-api/test/profile-api-server-recording.ts` -> `services/serve-pipeline-apis/test/profile-api-server-recording.ts`
- `services/typescript-api/test/profile-report-recording.ts` -> `services/serve-pipeline-apis/test/profile-report-recording.ts`
- `services/typescript-api/test/profile-retention.test.ts` -> `services/serve-pipeline-apis/test/profile-retention.test.ts`
- `services/typescript-api/test/recorded-machine-api.ts` -> `services/serve-pipeline-apis/test/recorded-machine-api.ts`
- `services/typescript-api/test/server-events.test.ts` -> `services/serve-pipeline-apis/test/server-events.test.ts`
- `services/typescript-api/test/write-server-events.ts` -> `services/serve-pipeline-apis/test/write-server-events.ts`

**Files touched - callers and gates:**

- `.github/scripts/summary-eval-tests/machine-task.ts`
- `.github/workflows/ci.yml`
- `.github/workflows/feed-ingest-plan-test.yml`
- `.github/workflows/summary-eval-tests.yml`
- `backend/tests/workflows/test_ci_selection.py`
- `frontend/scripts/test-scope.ts`
- `frontend/scripts/tests/test-scope.test.mjs`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-report.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-server-artifacts.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-server-report.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts`
- `services/feed-ingest-plan/scripts/safe-persist-http-client.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-host.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
- `services/feed-ingest-plan/test/planner-server-recording.ts`
- `services/feed-ingest-plan/test/safe-persist-http.test.ts`
- `services/hhem-evaluator/tests/host-profile-bridge.ts`
- `services/hhem-evaluator/tests/test_manual_workflow.py`

**Files touched - documentation and plan pointers:**

- `docs/reference/typescript-api-server.md` -> `docs/reference/serve-pipeline-apis.md`
- `docs/architecture/contracts/identity.md`
- `docs/architecture/sources/feed-operator-api.md`
- `docs/architecture/sources/feed-plan-runner.md`
- `docs/how-to/run-feed-ingest-plan-test.md`
- `docs/how-to/run-hhem-evaluation-api.md`
- `docs/how-to/run-the-gates.md`
- `docs/reference/host-metrics.md`
- `docs/reference/host-probe-api.md`
- `docs/reference/repository-layout.md`
- `docs/reference/summary-evaluation-workflow.md`
- `TODO/20261104-align-typescript-article-identity-plan.md`
- `TODO/20261105-serve-pipeline-apis-plan.md`

**Acceptance gates:**

Table F - Local checks and CI checks

| Id | Where | Check and required result |
| --- | --- | --- |
| F1 | Local | Inspect the shared selector with `npm run test:changed -- --list` from `frontend/`. Follow [native-service gate selection](../docs/how-to/run-the-gates.md#independent-typescript-packages-and-services); do not run a Python-backed full suite as a TypeScript prerequisite. Record the selected inputs and results. |
| F2 | Local | Run the destination package's declared `check` and `test` scripts and the planner's `check` script. Prepare missing dependencies through their existing locked installation sequence. The moved package's refreshed lock must support a frozen install with no dependency-version changes. |
| F3 | Local | In the planner, run one declared test invocation selecting `test/feed-ingest-plan-supervisor.test.ts`, `test/safe-persist-http.test.ts`, `test/feed-ingest-plan-workflow.test.ts`, `test/feed-ingest-plan-report.test.ts`, `test/feed-ingest-plan-finalization.test.ts`, `test/feed-ingest-plan-host.test.ts` and `test/feed-ingest-plan-delivery.test.ts`. Existing success, refusal, cleanup and evidence assertions must retain their meaning. |
| F4 | Local | From `frontend/`, run `npm run check:tooling` and `node --test scripts/tests/test-scope.test.mjs`. The destination service must select the existing native gate for both path separators and must not silently become documentation-only. |
| F5 | Local | Run the existing caller-launcher TypeScript compiler command from the `ci.yml` evaluator job against the machine helper and host-schema bridge. Run the targeted changed Python workflow test and the evaluator's `tests/test_manual_workflow.py` and `tests/test_host_profile_reader_parity.py` using their existing development environments and gate guide. |
| F6 | Local | Search for retired directory/package/reference names; no active file lookup, import, install, sparse input or documentation link may retain one. Review intentional identifier matches under Table D. Check links on the moved reference page and its listed callers, and inspect the rename diff for dropped files, dependency churn or unrelated edits. |
| F7 | CI | Require the normal full merge-candidate suite once. It must install from the destination directory and retain the existing planner, shared-server, workflow-selection and isolated evaluator checks. The evaluator's actual machine-child integration remains required on Linux; a Windows skip is not proof of that process boundary. |
| F8 | Next normal use, not a merge gate | Observe normal startup, shutdown and retained server evidence in the next existing planner and evaluation executions. A missing-module failure means a missed caller or installation path; correct that path without changing the protocol. Do not dispatch a data-writing workflow solely to prove the rename. |

- **Oracle:** The existing real shared-port check in the moved `test/api-composition.test.ts` must return the same native fingerprint, sample, fetch and parse results and release its listener; it must pass before and after the move by design. A stale dependency path or missing moved module must fail compilation or the named caller checks, not be hidden by an alias. This check cannot prove hosted workflow execution; F7 and F8 cover that separately.

**Decisions:**

Table G - Implementation decisions

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Use Table C consistently for source locations, package metadata and human-facing service labels; retain the machine-facing compatibility boundary in Table D. | Naming rule in CLAUDE.md section 1a and the existing listener and identity contracts. |
| G2 | Deliver the service move with all callers, fixed sparse inputs and gate updates in the same PR; one reverse rename can undo the change. | Existing caller imports and workflow inventories. |
| G3 | Reuse and update existing integration and selector tests rather than adding an all-repository name-scanning test or a new test harness. | Existing focused checks; CLAUDE.md sections 9 and 13. |
| G4 | Keep the reference page whole: its route groups, process lifetime and current-task evidence answer one listener-contract question. Repair links instead of leaving a forwarding page. | Existing reference-page scope and documentation split test. |
| G5 | No runtime redesign or persisted-shape change is needed for this move; no specialist ruling is required unless an escalation trigger fires. | CLAUDE.md section 6 and the current package composition. |

**Rejected alternatives:**

Table H - Alternatives and their cost

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Split the folder move, caller fixes and CI updates into separate PRs | Intermediate commits would retain imports or installation paths that no longer exist. | Compatibility indirection and an extra removal change, without a separate useful outcome. | Existing imports and workflow install/sparse inputs. |
| H2 | Keep a source-directory alias or symlink | It leaves two names for the same service and can conceal a missed caller. | An additional supported path, packaging work and cross-platform coverage until removal. | Single-purpose rename scope and existing direct callers. |
| H3 | Rename all protocol and producer identifiers with the directory | A source-location rename does not require readers to adopt a different protocol identity. | Inventory every affected validator and consumer, define compatibility for saved observations, and complete a separate contract review. | Existing listener and identity contracts. |
| H4 | Keep the old private package identity | Package diagnostics would still report the technology-based name after the directory move. | Continued naming ambiguity; changing it now requires only manifest identity and lock metadata updates. | Existing private package manifest and lockfile. |

## See also

- [Service listener contract](../docs/reference/serve-pipeline-apis.md)
- [Repository directory map](../docs/reference/repository-layout.md)
- [Named local and CI checks](../docs/how-to/run-the-gates.md)
- [Plan execution contract](../docs/how-to/execute-a-plan.md)
