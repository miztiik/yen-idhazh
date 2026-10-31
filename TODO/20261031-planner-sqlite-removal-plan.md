# Remove planner SQLite and delivery-file checksums

**Last Updated**: 2026-10-31
**Level**: 5 - planner execution design and the shared file-delivery contract.

## 0 - Operating contract

Table A

| Id | Field | Value |
| --- | --- | --- |
| A1 | Purpose | Remove the planner's private SQLite journal and extra delivery-file checksums while retaining the HTTP stages, existing outputs and optional failure diagnostics. |
| A2 | In scope | Both `safe_persist_data` destinations; all planner SQLite consumers; obsolete checksum, replay and reopening code, cases and documentation; a failure-only raw-document JSONL artifact. |
| A3 | Strategy | Deliver two sequential PRs: remove delivery checksums first, then replace the journal with live document handoff and wire failure-only artifact output. |
| A4 | Preserved behavior | Real loopback HTTP; validated stage payloads and events; independent live requests; fetch permissions, robots, redirects, retry, deadlines and byte limits; cancellation; selection; partitioning; actual UTC work accounting; metadata ledgers; the selected-articles full-text artifact. |
| A5 | Diagnostic boundary | Append failed raw-document JSON only when `dump_raw_document_contents` is true. Never dump successful documents, substitute extracted text, retain successful downloads for later debugging, or use the dump as execution state. |
| A6 | Work limits | No new tests, fixtures, dependencies, brokers, storage framework, benchmark or local test run. Remove obsolete cases and adjust existing support code affected by the contract changes. Existing CI configuration remains unchanged. |
| A7 | Escalation | Stop before changing unrelated hashes, ledger formats, public response fields, source permissions, independent API support or the content-retention requirement. Stop if another consumer requires an old journal or checksum input. Do not modify `CLAUDE.md`. |
| A8 | Execution | Author-and-stop. Both rows are design-level work; implementation starts only after execution is requested. Parallel N = 1 because PR 2 depends on PR 1. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates only where useful; keep parallel N = 1 because the PRs are sequential; honor the escalation triggers in Table A. AUTHOR-AND-STOP until execution is requested.

Table B

| Id | Out of scope | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Native Git object hashes, article identities, ledger digests and other non-delivery validation hashes | Those existing contracts and checks remain. This is not a repository-wide removal of hashing. | A separately scoped contract change naming the affected readers. |
| B2 | Restart recovery, replay and deterministic re-execution | A new process cannot recover old document or stage references. | A separate recovery capability with a retained storage destination. |
| B3 | Successful raw-document archives or downstream replacement content | A successful download is not retained solely to diagnose a later failure. | A separate content-retention requirement. |
| B4 | Changes to the native Python pipeline or published site | Those execution paths remain unchanged. | A concrete dependency discovered during this work. |
| B5 | Rewriting historical plans or retained data | Earlier descriptions and old journal files remain historical records, not current readers or runtime dependencies. | A separate cleanup request naming the exact files. |

## 1 - Status reckoner

Table C

| Id | Row | Title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Remove delivery-file checksum requirements | - | A | PENDING | - | - | - |
| C2 | 2 | Remove planner SQLite and add failure-only raw-document output | 1 | B | PENDING | - | - | - |

## 2 - Tasks by API

Table D

| Id | PR | API or surface | Removed | Added or preserved |
| --- | --- | --- | --- | --- |
| D1 | 1 | `safe_persist_data`, both destinations | Required `files[].sha256`, `DeliverySha256Schema`, delivery checksum calculation and comparison | Trusted completed-file inputs; existing path, permission, regular-file and collision checks |
| D2 | 1 | Persistence callers, existing support code and docs | Delivery-only checksum generation and forwarding; hash-only cases and claims | Updated typed callers and documented file handoff |
| D3 | 2 | `/fetch`, `/parse` | SQLite journal, saved-response replay and reopening recovery | Temporary in-memory handoff; existing HTTP references, validation and events |
| D4 | 2 | `/plan`, collection APIs | Keyed-plan replay and SQLite dependencies | Existing HTTP stage sequence, run isolation and cancellation |
| D5 | 2 | `/select-articles`, `/feed-health-state` | Restoration of request and source evidence from SQLite | Live run evidence, existing ledger-history reads and actual UTC accounting |
| D6 | 2 | `/partition-articles`, `/persist-selected-articles` | No output capability | Existing assignments, metadata ledgers and full-text selected artifact |
| D7 | 2 | Raw-document failure handling, config and workflow | Unconditional raw-content persistence | Default-off config flag, a `true`/`false` dropdown, and local append of failed raw-document JSON only |
| D8 | 2 | Artifact finalization | Debug-file checksum requirement | Close the writer; pass the completed file to artifact-directory persistence; upload only when enabled and a file exists; never include it in Git delivery |
| D9 | 2 | Planner contracts, existing support code and docs | Obsolete journal types, SQLite-only replay/reopening cases and current runtime claims | The live-handoff and failure-dump contract; no new tests |

## 3 - Failure-dump contract

Table E

| Id | Control | Contract |
| --- | --- | --- |
| E1 | Config | Add native boolean `dump_raw_document_contents`, default `false`, to `config/feed-ingest-plan-service.json` and `ServiceSettingsSchema`. |
| E2 | Workflow input | Add `dump_raw_document_contents` with `type: choice`, options `'false'` and `'true'`, and default `'false'`. It is a dropdown, not a checkbox or `type: boolean` input. |
| E3 | Startup wiring | Pass the selected value through `DUMP_RAW_DOCUMENT_CONTENTS`; accept exactly `true` or `false`, then explicitly convert to a native boolean. Never use truthiness or silently accept another string. Apply the value only to the invocation's effective settings. |
| E4 | File | Use `raw-document-contents.jsonl` under the existing private `inputs.artifact_root/<run_id>/<attempt>/` directory. Build and validate the relative path from the existing run identity, never document text. The artifact root must leave room for this filename. |
| E5 | Write behavior | Create the file on the first failed document only. Append one compact JSON object and a newline per failure. Serialize concurrent appends through one live writer so records cannot interleave. Do not collect failed bodies in an array for final serialization. |
| E6 | Failure content | Record the actual raw-document JSON and failure, for any document-failure reason. Preserve unavailable content as unavailable; do not invent content, fetch again or replace it with extracted text. Requests without a resolved document keep their existing body-free error handling. |
| E7 | Delivery | Drain and close the append writer before handing the completed file to `safe_persist_data` with `destination.kind: "artifact-directory"`. Declare only the exact diagnostic target path as permitted. No expected hash or end-of-run checksum is supplied. |
| E8 | Upload and cleanup | Upload a separate debug artifact only when the flag is true and the file exists. Zero failed documents requires no debug artifact. Retain available diagnostics after a failed collection; cleanup must not run ahead of artifact preparation or upload. |
| E9 | Isolation | Raw content never enters normal HTTP responses, structured logs, commit inventories, selected-article metadata, public pages or startup controls. Do not include credentials or request headers. Diagnostic data is never read to resume execution. |
| E10 | Write errors | Report append, preparation and upload errors explicitly while preserving the original document failure and any completed normal output. Do not silently drop a record or replace an earlier failure with a success-shaped result. |

Table F

| Id | Record field | Native declaration and meaning |
| --- | --- | --- |
| F1 | `schema_version` | The new diagnostic contract's date stamp. Declare the record in `packages/common-contracts/src/schemas/raw-document-failure.schema.ts` before adding the writer. |
| F2 | `document_kind` | `feed` or `article`; reuse the existing fetched-item vocabulary. |
| F3 | `request_id` | The validated identifier of the failing document operation. |
| F4 | `operation` | The existing document operation, `fetch` or `parse`, that observed the failure. |
| F5 | `failed_at` | The actual recorded UTC failure instant, using the existing event instant type. |
| F6 | `failure_reason` | The actual reported failure code or reason, not a newly inferred classification. |
| F7 | `document` | The existing validated native raw-document payload. Its body can be null when no body was obtained. Do not serialize the retired `PlannerOperation` journal wrapper or unrelated configuration. |

## 4 - Row 1 - Remove delivery-file checksum requirements

- **Scope:** Remove extra file-checksum requirements from both shared delivery destinations and update their current callers without changing file permissions or native data formats.
- **Files touched:**
  - `packages/data-delivery/src/safe-persist-data-contract.ts`
  - `packages/data-delivery/src/safe-persist-data.ts`
  - `packages/data-delivery/src/index.ts`
  - `packages/data-delivery/test/safe-persist-data.test.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-metadata.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `docs/architecture/publishing/committing.md`
  - `docs/architecture/contracts/schemas.md`
  - `TODO/20261031-planner-sqlite-removal-plan.md`
- **Commit order:** Change the delivery contract, implementation, callers and affected support code together. Keep mechanical moves separate from behavior changes if a move is needed.
- **Implementation:** Delete the checksum input schema, exports and delivery-only calculations. Remove the duplicate whole-file checksum comparison and return field in the metadata handoff adapter; retain native row, envelope and execution validation. Artifact collision checks compare actual bytes without a checksum. Git continues to generate and compare its own object identities. Preserve the existing destination-specific result types and immutable-output behavior.
- **Acceptance gates - local:** Use `bun run check` from `packages/data-delivery` and `services/feed-ingest-plan`; run `git diff --check`. No local test run, new test case or new fixture.
- **Acceptance gates - CI:** Existing `ci.yml` gates remain authoritative and unchanged. Adjust or remove obsolete checksum expectations so retained cases still use the current input contract.
- **Oracle:** Current callers hand only completed file paths and independently permitted destinations, and no delivery path asks for or computes an expected whole-file checksum. This does not remove native ledger validation or guarantee that a producer never changes a handed-over file.

Table G

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Remove the extra checksum contract from both destinations in one PR, rather than retaining a separate artifact-only schema. | Plan scope |
| G2 | Keep containment, symlink, executable-file, permission and immutable-collision refusals. Trusting file content does not grant broader destination permissions. | Existing delivery contract |
| G3 | Do not remove Git object identities, canonical ledger digests or unrelated hashing helpers. | Table B |
| G4 | Delivery inputs are in-process requests, not payloads a later run loads. Update all current callers together; do not add a checksum compatibility mode. | Existing delivery API |

Table H

| Id | Alternative | Why rejected | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| H1 | Compute an expected checksum only at finalization | Retains the requirement this PR removes. | Another full-file calculation and caller/API checksum coordination. | Table D |
| H2 | Rewrite artifact copying as a streaming subsystem | Not required for simple failure-only JSONL output. | Additional shared-copy code and lifecycle work beyond this removal. | Table A |
| H3 | Remove destination safety checks along with checksums | File content and destination authority are different questions. | A broader file-delivery safety contract change. | Existing delivery contract |

## 5 - Row 2 - Remove planner SQLite and add failure-only raw-document output

- **Scope:** Remove the request journal end-to-end, preserve the live HTTP pipeline and its outputs, and add only the default-off failure-dump capability in Tables E and F.
- **Files touched:**
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/raw-document-failure.schema.ts` (new)
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/test/schema-binding.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/common-contracts/test/article-identity-compatibility.test.ts`
  - `services/feed-ingest-plan/src/api/operation-store.ts` (delete)
  - `services/feed-ingest-plan/src/api/plan-operation.ts` (delete)
  - `services/feed-ingest-plan/src/api/restore-source-health.ts` (delete)
  - `services/feed-ingest-plan/src/api/operation-contracts.ts`
  - `services/feed-ingest-plan/src/api/operation-context.ts`
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/src/api/parse-operation.ts`
  - `services/feed-ingest-plan/src/api/collection-operation.ts`
  - `services/feed-ingest-plan/src/api/selection-operation.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state-operation.ts`
  - `services/feed-ingest-plan/src/api/stage-store.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/routes/plan.route.ts`
  - `services/feed-ingest-plan/src/api/routes/document.route.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/run-health.ts`
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `services/feed-ingest-plan/src/selected-artifact-path.ts`
  - `services/feed-ingest-plan/src/dump-raw-document-failure.ts` (new)
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts`
  - `services/feed-ingest-plan/scripts/finalize-run-output.ts`
  - `services/feed-ingest-plan/scripts/finish-run-output.ts`
  - `services/feed-ingest-plan/test/operation-format.test.ts` (delete)
  - `services/feed-ingest-plan/test/article-source-outcome.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/robots-entry-points.test.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
  - `tests/fixtures/contracts/planner-operation/started.json` (delete)
  - `config/feed-ingest-plan-service.json`
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `.gitignore`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/reference/feed-planner-ledgers.md`
  - `docs/architecture/contracts/recorded-instants.md`
  - `TODO/20261031-planner-sqlite-removal-plan.md`
- **Commit order:** Move any still-used utility or type out of a module being deleted in a structural commit. Follow with one complete behavior cutover: native contracts, live callers, diagnostics, workflow wiring, obsolete support-code removal and living docs. Do not land a stub or dual storage implementation.
- **Live handoff:** Reuse the current bounded stage/run memory rather than introducing another persistence layer. Claim a fetched reference before work, preserve its run/feed/offer/correlation context, and release its downloaded body after parsing succeeds or fails. Schedule fetch/parse work within existing configured capacity; never cap the number of input articles or evict a reference still needed by active work.
- **Health:** Keep actual work facts and source outcomes in live body-free run state. Health and selection read that state and the existing retained ledgers, not saved request receipts. Keep original UTC fetch dates, partial request accounting, warnings, rejected rows and grouped causes after releasing a raw body.
- **Replay removal:** Remove `PlannerOperationSchema`, `PlannerOperation`, `PLANNER_OPERATION_VERSION`, `PreparedOperation`, journal-only fingerprints and the journal's source-membership recovery. Keep the still-used request, fetched-document, attempt and observation declarations in the shared schema file. Retired `Idempotency-Key` requests fail explicitly as unsupported before work. Missing or consumed document references return the existing missing-reference error; concurrent ownership conflicts retain the existing conflict error. No completed-response cache, reopen loader or automatic re-execution replaces the journal.
- **Diagnostics:** Implement Tables E and F with one small append helper. Record a failed raw input before releasing it, using the failure the API actually observed. No extracted-text fallback or successful-body archive. Preserve existing body-free logging and public response behavior.
- **Workflow:** Carry the dropdown selection into the child through validated effective settings. Return only body-free diagnostic path/control outputs. Prepare any existing diagnostic file before early-return paths in artifact finalization, including failed collection paths. Invoke artifact-directory delivery separately from metadata delivery, then upload the debug artifact at the end. Await applicable upload completion before cleanup.
- **Existing support code:** Delete SQLite-only format and reopening cases and the retired fixture/binding. Remove replay portions of mixed cases without deleting independent extraction, robots, UTC accounting, source-outcome, discovery or immutable-finalization coverage. Do not add replacement cases, fixtures or test tooling.
- **Documentation:** Replace current journal/replay promises with the live-handoff lifetime and failure-only flag/file contract. Keep time precision and ledger behavior that do not depend on the journal. Remove runtime journal ignore entries when their producer is gone; ensure diagnostic output remains under ignored private artifact paths. Preserve historical data and completed plan descriptions.
- **Acceptance gates - local:** Use `bun run check` from `packages/common-contracts` and `services/feed-ingest-plan`; inspect the workflow input and strict string-to-boolean conversion; run `git diff --check`. No local test run or live workflow dispatch.
- **Acceptance gates - CI:** Existing `ci.yml` gates remain unchanged. This PR adds no cases or fixture matrix; retired code and support inputs must no longer depend on the journal.
- **Oracle:** The real HTTP plan has no SQLite import, journal opening, request replay or saved-receipt recovery; its existing selection, partitioning, health and full-text handoff remain wired, and only failed raw documents can reach the gated diagnostic artifact. This does not promise recovery after a killed process or retention of successful original downloads for later investigation.

Table I

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Keep the HTTP/event boundaries; replace only the private journal and its consumers. | Architecture |
| I2 | Keep raw bodies only while current work needs them. Preserve extracted text through selection, partitioning and selected-artifact writing. | Existing stage/output contracts |
| I3 | Store diagnostic data by local append, then hand the closed file to the hash-free artifact destination. Do not change the file after handoff. | Tables E and F |
| I4 | Use an explicit `true`/`false` dropdown with default `false`; native configuration remains boolean. | Table E |
| I5 | Update current readers/writers together. Old journal formats are no longer read or migrated; retained ledger formats are unchanged. | Current planner contract |

Table J

| Id | Alternative | Why rejected | Cost to take it | Authority |
| --- | --- | --- | --- | --- |
| J1 | Replace SQLite with persisted JSON receipts | Recreates journal/recovery work without the database. | Another state-file format, reader, cleanup and replay path. | Table A |
| J2 | Archive every raw document when debugging | The dump is failure-only. | Successful-content storage and a broader diagnostic artifact. | Table E |
| J3 | Retain successful originals or substitute extracted text to diagnose later failures | Changes the raw-document dump and retention requirement. | More retained data or a different diagnostic payload. | Table B |
| J4 | Replace HTTP stages with direct execution calls | Removes the API/event architecture rather than the unwanted storage. | A separate stage-transport and consumer change. | Existing API contract |
