# Remove robots checks from TypeScript ingestion

**Last Updated**: 2026-11-02

**Level**: 5 - source request behavior and native API, diagnostic and ledger contracts.

## 0 - Operating contract

Table A - scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Intent | TypeScript ingestion fetches feeds and articles without retrieving, parsing or enforcing robots files, while all unrelated checks remain active. |
| A2 | Hard scope - in | Planner HTTP and package APIs; the shared source fetcher and its probe callers; native configuration, events, stages, diagnostics, saved Parquet records, request accounting, reports, fixtures, tests and current documentation. |
| A3 | Delivery | Two dependent PRs. First make required-field history reads independent of the stored row-version date. Then remove robots behavior and its contracts together in one complete change. Each PR includes its own tests and documentation. |
| A4 | Removal rule | Delete robots-only code. In mixed code, remove only robots behavior and retain general URL, transport, retry, parsing, failure, history, lifecycle and reporting work. No disable flag, alternate implementation, compatibility alias, historical decoder or deferred cleanup. |
| A5 | Historical data | Leave existing raw files, compact files and indexes unchanged. Reuse valid required fields; report missing or invalid fields as specific gaps without failing planning. Do not migrate, rewrite, delete or fill historical records. |
| A6 | Chosen strategy | Separate stored-file integrity from current-row compliance; then make the shared TypeScript fetch path target-only. Contracts are declared in Table E and Table F before their callers change. |
| A7 | ESCALATE triggers | 1. A proposed change alters Python behavior, shared Python record formats or published-site controls. 2. Source URL validation, redirect validation, sanitization, body limits or operator-controlled destinations would weaken. 3. Reading history would require an older file-envelope decoder or guessed field meaning. 4. A required consumer cannot use the declared current format without a new compatibility path. 5. Editing `CLAUDE.md` or `AGENTS.md` is proposed. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer coordinates one nested session per PR in dependency order; parallel N = 1 because both PRs share contracts, tests and documentation; merge only after required checks pass; honor A7. |
| A9 | Measurement | Do not promise a runtime saving. Offline request traces prove removal; the next ordinary planner run supplies an observation of elapsed collection time, request counts and source outcomes, not a merge gate. Do not dispatch a workflow that commits data merely to validate this plan. |

Table B - exclusions

| Id | What is out | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Python fetching, its robots policy, its configuration and its saved records | Python retains its existing access rules and measurements. | A separate change naming that producer. |
| B2 | Removing robots vocabulary from Python-owned contracts copied into TypeScript, or from the production console | Those active Python readers still need that vocabulary. | A change to the Python format and its real consumers. |
| B3 | Pacing settings, work-pool sizes, parser concurrency and transport replacement | Existing serialization, queue waits and network behavior remain except that robots work no longer enters them. | A separate pacing or scheduling request. |
| B4 | Historical file conversion, cleanup or index repair | Historical bytes can retain removed columns; only usable projected evidence contributes. | A separate data-maintenance task. |
| B5 | New diagnostic metrics, run-wide pacing attribution or new dashboard surfaces | Removal does not quantify the separate cost of pacing. | A request for those measurements and their contracts. |
| B6 | Edits to completed historical plans, unrelated Python fixtures or the Python robots CI job | Those records and checks continue to describe the separate pipeline. | A concrete active dependency on the removed TypeScript behavior. |

## 1 - Status Reckoner

Table C - PR-shaped outcomes

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Read health history by required fields across row-version dates | - | A | DONE | shiny-fiesta | - | - |
| C2 | 2 | Remove robots behavior from TypeScript ingestion end-to-end | 1 | B | DONE | didactic-succotash | - | Remove typescript robots checks |

## 2 - API and data contracts

Table D - TypeScript API impact

| Id | Surface | Required result |
| --- | --- | --- |
| D1 | Dated HTTP API | In PR 2, set `PLANNER_API_PREFIX` from the protocol date in F1. Update active clients and readiness checks together. All route suffixes below use that prefix. No old-prefix alias. |
| D2 | `POST /fetch` | No automatic robots request for a feed, article or redirect. Public response keys stay unchanged; the fetch-failure vocabulary loses the retired values in E3. Private fetched documents follow E2 and E4. |
| D3 | `POST /parse` | Remains network-free and consumes the existing live fetch reference. Public response keys remain unchanged. Internal observations and diagnostics use the reduced contracts. |
| D4 | `POST /plan` | Uses the same target-only fetch path. Public run-result keys remain unchanged; saved health/rejection output and the behavior of collection change. |
| D5 | `POST /feed-health-state` | Both `summarize` and `record` return health rows and request reports without the fields in E5 and E6. Availability and reliability reuse required historical columns under F6. |
| D6 | `POST /select-articles` | Returns the reduced request report. General earlier-failure, publication and content exclusions remain. Earlier robots-only failures cannot cause a TypeScript exclusion. Selected-article metadata is unchanged. |
| D7 | `POST /partition-articles` | Public request, assignments and article metadata remain unchanged. Its private batch contains the updated health/report shapes. |
| D8 | `POST /persist-selected-articles` | Receipt and selected-text artifact shapes remain unchanged. Rejected records use the reduced current schema and actual native file validation. |
| D9 | `POST /collections`, `/collections/exists`, `/collections/complete`, `/collections/cancel`, `/collections/finalize`, `/collections/release` | Lifecycle controls and response keys remain unchanged. Work settlement, partial output and failure finalization use target-only attempts and revised records. |
| D10 | `POST /safe-persist-data` | Delivery request and receipt shapes remain unchanged. Validate new output against current native contracts before delivery. No historical file modification is added. |
| D11 | `GET /health` on planner and delivery listeners | Readiness payloads remain unchanged. Listener and supervisor use the same dated prefix from D1. |
| D12 | Source-fetch and harvest package APIs | Replace the `./robots-policy` export with `./fetch-source`. Export `createSourceFetcher` and `SourceFetcher` instead of `createPermittedFetcher` and `PermittedFetcher`. Keep `FetchResult` and attempt measurement types with their reduced fields. Expose pacing from its own `./request-pacing` module, not through the source fetcher. Update `harvestFeeds` and every direct caller; keep no forwarding export. |
| D13 | `probeFeed`, `feedProbe`, probe CLI and machine reports | Shared-fetcher callers also stop robots work. Preserve feed validity, readability, paywall evidence, bounded sampling and body-free output. Update result/report versions and diagnostics; do not keep an independent robots path. |
| D14 | `renderPlanMarkdown` and workflow summary adapter | Remove retired request columns, coverage categories and failure details. Preserve actual target status, partial coverage, terminal-failure grouping and the separate delivery receipt. |

Table E - field and behavior removals

| Id | Contract area | Required change |
| --- | --- | --- |
| E1 | Planner configuration | Remove `harvest.article_robots_policy` from the authored config and its schema. Do not replace it with an off mode or another flag. Current authored inputs with the removed key fail normal strict configuration validation. |
| E2 | Fetch results, observations, diagnostics, rejection evidence, network failure details and failed-document metadata | Remove `robots`, `robots_failure`, `robots_http_status` and `robots_response_evidence` wherever present. Do not emit null placeholders or fabricate allowed permission. |
| E3 | Native failure vocabulary | Remove `robots-denied` and `robots-unknown` from `FetchFailureSchema`, and `robots_denied` and `robots_unreachable` from TypeScript-native diagnostic/output choices. Reuse `FetchFailureSchema` in harvest observations instead of maintaining its duplicate enum. Shared Python item-health vocabulary remains intact under B2. |
| E4 | Attempts and in-memory work facts | Remove `robots` from `FetchAttempt.phase` and `DocumentWorkFact.request_phase`; keep `validation` and `target`. Preserve actual dispatch counts, ordering, cause identity, target timing, backoff and pacing evidence. |
| E5 | Planner health records | Remove `permission` and `robots_requests`; remove `robots_denied` from `outcome` and `robots` from `check_result`. Remove their production, classification and denominator branches. Completeness depends only on the remaining declared counters. |
| E6 | Request reports | Remove `robots_requests` and `coverage.robots_requests`, plus the third request category from summaries, aggregation, completeness checks and Markdown. Missing retired counters cannot make feed/article accounting incomplete. |
| E7 | Failure logging and optional diagnostic artifact | Remove robots-specific response/cutoff attribution, including `body_limit_source`, whose distinction disappears. Preserve actual feed/article `body_limit`, native response evidence, sanitized addresses, profiles and terminal failures. Preserve body-free projection and optional artifact lifecycle. |
| E8 | Shared earlier-failure inputs | Keep the general same-day earlier-failure check. Define one `PlannerItemFailureCodeSchema` by narrowing the shared item-health vocabulary to exclude the two retired underscore-form reasons in E3. Use it for native planner/probe output and exclusion maps. Validate shared authored input and saved Python records with their existing schemas, then project eligible codes at the input boundary. Other configured failure reasons still exclude articles. Do not reject an entire history file because it contains an inapplicable robots reason. |
| E9 | Source-fetch implementation | Delete robots retrieval, parsing, matching, per-origin cache, wait helpers, separate robots allowance and suspend/resume logic used only around that wait. Keep target URL cleanup, validation on every hop, retry/backoff, native profiles, target deadline, cancellation, body limits and existing pacing. Target failures and returned evidence must describe target work only. |

Table F - versions, ledgers and history

| Id | Declaration | Required rule |
| --- | --- | --- |
| F1 | Protocol date | `2026-11-02`. Use this date for changed native payload/config metadata and construct the dated HTTP prefix in D1 from it. |
| F2 | Changed contract stamps | Update `FEED_HEALTH_STATE_VERSION`, `PARSED_FEED_BATCH_VERSION`, `FEED_OUTCOME_PAYLOAD_VERSION`, `FEED_PROBE_VERSION`, `FEED_INGEST_EVENT_VERSION`, `OPERATION_VERSION`, `RAW_DOCUMENT_FAILURE_VERSION`, `CANDIDATE_REJECTION_VERSION` and `REJECTED_ARTICLE_VERSION`. Update version/changelog metadata on configuration, diagnostics and request reports; declare changed work-fact metadata. Append concise shape-change entries, not approval records. |
| F3 | Private selected and partitioned batches | Add `SELECTED_FEED_BATCH_VERSION` for their changed health/report payloads. Stop using the unchanged selected-article record version as their format stamp. No legacy batch reader. |
| F4 | Changed committed ledgers | Only `feed-health-state` and `rejected-articles` lose physical columns. The registered writer derives their Parquet layout from current native schemas; remove obsolete columns, not their values alone. Update file validation, digest and round-trip expectations at their existing boundaries. |
| F5 | Unchanged stored formats | Do not change discovery, selected-article metadata, selected-text artifact or plan-run record formats. Keep the existing file-envelope format version: its framing does not change. No new ledger, reservation file or per-request journal. |
| F6 | Required-field historical reads | A stored row-version date alone does not disqualify an intact file. Verify the supported envelope, registered ledger, file identity, named membership and digest over every actual stored column before projection. Each use validates only its required columns. Extra historical columns are ignored by that use, not by integrity verification. Missing, invalid or conflicting required facts produce explicit per-use gaps and partial evidence. Unknown values do not become zero. |
| F7 | Strict current-file consumers | Full-row reads, new writes, compaction, publication and current-run delivery still require the complete current schema and stamp. Preserve the typed unsupported-format result these consumers already use. Separating this from F6 must not make a strict consumer permissive or modify historical bytes. |
| F8 | Historical enum values | A retired value in a required historical field is a field gap, not an instruction to translate it. Valid saved lifecycle/reliability fields remain usable independently. Missing calculations keep the existing bounded recovery and unknown-state rules. |
| F9 | Preserved accounting | Count each actual target dispatch, including retries, redirects and secondary profiles, once in its feed/article category on its actual UTC work day. Validation and parsing add no HTTP request. One terminal article rejection is not multiplied by attempt count. Preserve logical feed checks, technical admissions, selection counts and independent history windows. |

## 3 - Row #1 - Read health history by required fields across row-version dates

- **Scope:** Ship a permanent separation between verified stored bytes and current full-row validation so historical health calculations survive unrelated schema changes.
- **CI cleanup:** Remove stale test references to the deleted native-transport workflow. Python runtime behavior and stored formats remain unchanged.
- **Files touched:**
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/ledger-file-writer/src/read-planner-file.ts`
  - `packages/ledger-file-writer/test/rejected-article-compatibility.test.ts` (move to the next path)
  - `packages/ledger-file-writer/test/planner-stored-file.test.ts` (new path)
  - `services/feed-ingest-plan/src/read-ledger-history/read-planner-history.ts`
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `docs/reference/feed-planner-ledgers.md`
  - `docs/architecture/sources/planner-feed-history.md`
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_source_transport_workflow.py` (delete)
  - `TODO/20261102-remove-typescript-robots-checks-plan.md`
- **Acceptance gates - local:** Inspect the shared selector with `npm run test:changed -- --list` from `frontend`. Run `check` in common contracts, the ledger writer and the planner. In common contracts select `test/rejection.test.ts`; in the writer combine `test/planner-stored-file.test.ts`, `test/planner-publication.test.ts`, `test/planner-maintenance-unsupported.test.ts`; in the service combine `test/health-fields.test.ts`, `test/planning-health.test.ts`, `test/history-window.test.ts`, `test/file-baseline.test.ts` and `test/ledger-history.test.ts`. Use each package's declared runner and retain the selection/results.
- **Acceptance gates - CI:** Full merge-candidate suites, strict writer/publication/maintenance checks and existing Python-owned contract bindings. No new live workflow or repository-history scan.
- **Acceptance gates - test inventory:** Run backend lint and type checking, then combine `backend/tests/workflows/test_triggers.py`, `backend/tests/workflows/test_pinned_versions.py` and `backend/tests/workflows/test_workflow_inputs.py` in one focused pytest invocation. Retain the unchanged TypeScript results.
- **Oracle:** For a generated, integrity-valid health file, changing only its valid row-version date must preserve the same usable field projections; removing a required field must degrade only its consumer, while a strict full-row read still refuses a non-current schema and the file bytes remain unchanged. This does not establish that missing historical values can be recovered or that source fetching is faster.

Table G - implementation tasks and decisions

| Id | # | Task | Decision basis |
| --- | --- | --- | --- |
| G1 | 1 | Remove current-row-version equality from stored-envelope validation and stored-file loading. Keep current-envelope and all integrity checks. | F6; a field projection has no full-row consumer. |
| G2 | 2 | Enforce row-version equality in `PlannerFileEnvelopeSchema` and strict `readPlannerParquet`, preserving `PlannerUnsupportedFormatError` for strict consumers. | F7; publication and maintenance depend on that typed result. |
| G3 | 3 | Remove the extra health row-version gate in `readStoredPlannerDay`. Preserve captured-input caching, raw/compact membership, endpoint identity, conflict checks and independent field gaps. | The current gate runs before field selection; F6 replaces that admission rule. |
| G4 | 4 | Update the existing generated-file tests and rename the writer test to describe stored-file integrity. Cover raw and compact input, extra/missing columns, valid saved deadlines/rates, partial counters and unchanged bytes. | Reuse the existing field-reader test tier; no historical decoder or production-data fixture is needed. |
| G5 | 5 | Update the two current history references to distinguish F6 from F7. | Each read rule needs one current definition, not an old-format exception list. |
| G6 | 6 | Remove the deleted native-transport workflow from the named test inventory and delete its dedicated workflow-only test. | CI must read existing named files; native source tests remain in the service suite. |

Table H - rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Decision basis |
| --- | --- | --- | --- | --- |
| H1 | Reject every earlier row-version date before projection | Discards valid fields without checking what the consumer needs. | Loses supported saved decisions until new history accumulates; configured windows determine the duration. | F6 |
| H2 | Add version-specific readers, migration or null-fill | Preserves formats rather than selecting measured facts. | Additional schema/decoder paths and tests, plus a separate data operation if bytes are rewritten. | A4-A5 |
| H3 | Relax strict writers/publication together with history | Could publish or compact a row that does not meet its declared current shape. | A separate storage/publication contract redesign and integrity review. | F7 |

## 4 - Row #2 - Remove robots behavior from TypeScript ingestion end-to-end

- **Scope:** Remove robots work and its native contracts from every shared TypeScript ingestion entry point without removing unrelated checks or changing existing ledger files.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/version.ts`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/document-work.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health-fields.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health-state.schema.ts`
  - `packages/common-contracts/src/schemas/feed-probe.schema.ts`
  - `packages/common-contracts/src/schemas/harvest-diagnostics.schema.ts`
  - `packages/common-contracts/src/schemas/planner-item-failure.schema.ts` (new)
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/planner-request-report.schema.ts`
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/src/schemas/raw-document-failure.schema.ts`
  - `packages/common-contracts/src/schemas/rejected-article.schema.ts`
  - `packages/common-contracts/src/schemas/rejection.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/common-contracts/test/request-report.test.ts`
  - `packages/ledger-file-writer/test/planner-recordings.ts`
  - `packages/ledger-file-writer/test/planner-stored-file.test.ts`
  - `packages/ledger-file-writer/test/rejected-article-replay.test.ts`
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts` (move to the next path and remove E9)
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-source.ts` (new path)
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-diagnostics.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-types.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/prepare-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/record-rejection.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/src/api/parse-operation.ts`
  - `services/feed-ingest-plan/src/availability/feed-lifecycle.ts`
  - `services/feed-ingest-plan/src/article-source-outcome.ts`
  - `services/feed-ingest-plan/src/attribute-ingest-outcomes.ts`
  - `services/feed-ingest-plan/src/health-row.ts`
  - `services/feed-ingest-plan/src/load-plan-inputs.ts`
  - `services/feed-ingest-plan/src/run-health.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/feed-reliability-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-exclusion-evidence.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/request-summary.ts`
  - `services/feed-ingest-plan/src/record-harvest-failures.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/screening-input.ts`
  - `services/feed-ingest-plan/src/reporting/aggregate-feed-results.ts`
  - `services/feed-ingest-plan/src/reporting/failure-evidence-markdown.ts`
  - `services/feed-ingest-plan/src/reporting/request-report-markdown.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts`
  - `services/feed-ingest-plan/test/article-robots-policy.test.ts` (delete after retaining independent target tests)
  - `services/feed-ingest-plan/test/robots-entry-points.test.ts` (delete after moving the target-only entry assertions)
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-source-outcome.test.ts`
  - `services/feed-ingest-plan/test/article-url-cleanup.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/collection-recordings.ts`
  - `services/feed-ingest-plan/test/collection-work.test.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `services/feed-ingest-plan/test/early-age.test.ts`
  - `services/feed-ingest-plan/test/feed-first-use.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-http-client.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/file-baseline-recording.ts`
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `services/feed-ingest-plan/test/network-failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/partition-recordings.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-entry-points.test.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `services/feed-ingest-plan/test/report-native-evidence.test.ts`
  - `services/feed-ingest-plan/test/request-pacing.test.ts`
  - `services/feed-ingest-plan/test/request-report.test.ts`
  - `packages/feed-probe/bun.lock`
  - `packages/feed-probe/src/feed-probe.ts`
  - `packages/feed-probe/src/feed-probe-report.ts`
  - `packages/feed-probe/test/feed-probe.test.ts`
  - `packages/feed-probe/test/feed-probe-cli.test.ts`
  - `tests/fixtures/feed-ingest-plan/article-robots-policy.json` (delete robots-only vectors; retain any shared target vectors before deletion)
  - `tests/fixtures/feed-ingest-plan/article-terminal-failures.json`
  - `tests/fixtures/feed-ingest-plan/feed-health-row.json`
  - `tests/fixtures/feed-ingest-plan/harvest-responses.json`
  - `tests/fixtures/feed-ingest-plan/harvest-safety.json`
  - `tests/fixtures/feed-ingest-plan/harvest-url-cleanup.json`
  - `tests/fixtures/feed-ingest-plan/health-field-history.json`
  - `tests/fixtures/feed-ingest-plan/screening-cases.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/discovered-articles.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/health.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/plan-runs.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/response.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
  - `docs/architecture/sources/feed-availability.md`
  - `docs/architecture/sources/feed-curation.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/planner-feed-history.md`
  - `docs/architecture/sources/trust-boundary.md` (TypeScript subsection only)
  - `docs/how-to/run-feed-ingest-plan-test.md`
  - `docs/reference/feed-planner-ledgers.md`
  - `TODO/20261102-remove-typescript-robots-checks-plan.md`
- **Acceptance gates - local:** Inspect the shared selector from `frontend` as in Row #1. Run `check` in common contracts, the ledger writer, the planner and the probe. In common contracts combine `test/config.test.ts`, `test/rejection.test.ts` and `test/request-report.test.ts`. In the writer combine `test/planner-stored-file.test.ts`, `test/rejected-article-replay.test.ts` and `test/planner-publication.test.ts`. In the probe combine its two existing test modules. In the service combine `test/harvest.test.ts`, `test/harvest-safety.test.ts`, `test/request-pacing.test.ts`, `test/article-failure-retention.test.ts`, `test/health-fields.test.ts`, `test/history-window.test.ts`, `test/request-report.test.ts`, `test/report-native-evidence.test.ts`, `test/operation-logging.test.ts`, `test/plan-api.test.ts`, `test/plan-entry-points.test.ts`, `test/feed-ingest-plan-supervisor.test.ts` and `test/feed-ingest-plan-http-client.test.ts` in one invocation. Add changed callers' existing selected cases when the selector or compiler identifies a real dependency. Retain the selected inputs and results.
- **Acceptance gates - CI:** Full merge-candidate suites; native Impit loopback coverage on Linux; current output validation, publication and maintenance; unchanged Python-owned contract bindings. No live publisher request is a test or merge gate.
- **Oracle:** For the same bounded recorded feed/article inputs, actual transport invocations through direct harvest, standalone fetch/parse, the real planning API and the probe contain only the required feed/article targets and their real retries/redirects; saved feed/article request counters equal those target dispatches and all retired output fields are absent. This proves removal and accounting, not faster live execution or guaranteed publisher access.

Table I - implementation tasks and decisions

| Id | # | Task | Decision basis |
| --- | --- | --- | --- |
| I1 | 1 | Declare E1-E8 and F2-F5 in native contracts first. Add the scoped failure schema and private-batch stamp without changing the Python-owned declarations. | Contracts and unchanged-record separation. |
| I2 | 2 | Apply E9 and D12 to the existing shared fetcher, exports and every caller. Keep native transport and pacing as separate existing units; do not move execution into HTTP route files. | One source-fetch path, no retired wrapper. |
| I3 | 3 | Wire D1-D11 through active HTTP clients, supervisors and current batch handling. Replace the supervisor's hard-coded prefix with the shared constant. | The dated route identifies the current request/response contract. |
| I4 | 4 | Apply E4-E6 and F9 to work accumulation, feed classification, article capture, reliability inputs and request-history summaries. | Counts describe actual target work, not removed permission work. |
| I5 | 5 | Apply E8 at shared-input boundaries and retain the general checks in pre-download admission and screening. Preserve original shared config and Python file bytes. | Mixed-purpose checks remain; only the retired reasons lose their TypeScript effect. |
| I6 | 6 | Apply E2, E7 and D13-D14 to diagnostic projection, failed input metadata, probe reports and workflow Markdown. Reuse the declared shapes rather than independent field lists. | No null placeholders, misleading response provenance or duplicate accounting. |
| I7 | 7 | Remove `robots-parser` from the service manifest and regenerate both affected lockfiles with the package manager. Delete robots-only tests/helpers/vectors; retain target safety, retry, cancellation, URL, pacing and reporting assertions from mixed files. | No orphan dependency, feature flag, legacy export or reduced non-robots coverage. |
| I8 | 8 | Update the current subsystem docs, native field tables and API inventory. Limit trust-boundary edits to the TypeScript subsection; retain Python policy. Recapture the named entry-point transcript set through its existing capture path, not hand-invented outputs. | Current rules and same-run fixtures must match actual execution. |

Table J - required test evidence

| Id | Tier | Required evidence |
| --- | --- | --- |
| J1 | Unit/integration | Capture every attempted recorded-transport invocation before fixture lookup. An accidental robots request must not disappear merely because it has no fixture and observe-mode error handling continues. Assert exact target request sequences, not only successful parsing. |
| J2 | Unit/integration | Preserve unsafe-address and redirect refusal, URL identity/cleanup, retry and profile recovery, cancellation, target timeouts, decoded-byte cutoff, sanitizer and content checks. Retain the existing pacing guarantees with no robots work. |
| J3 | API integration | Reuse the representative real loopback planner and standalone fetch/parse journeys. Verify reduced response contracts, body-free diagnostics, unchanged reference lifetime and no parse-time requests. Old dated routes have no alias. |
| J4 | Contract/integration | Current health and rejected Parquet files have exactly the declared remaining columns, current stamps and canonical digests. Current full-row readers reject stale/extra fields; historical field readers retain usable evidence under Row #1. |
| J5 | Unit/integration | Feed/article totals, their independent coverage and `counts_complete` do not require a removed counter. Include known zero, null/missing values, retries, redirects, failures and UTC day attribution. Terminal rejection rows remain distinct from attempt counts. |
| J6 | Integration | A validated shared history input containing an earlier robots reason does not prevent TypeScript fetching or screening; an otherwise identical applicable non-robots failure still does. Other pre-download exclusions remain intact. |
| J7 | Contract/report integration | Probe JSON, raw failure metadata, network-failure details and Markdown contain no retired fields or request categories. Actual target status, response evidence, pacing data and partial-history notices remain. Check shape and meaning, not incidental wording or geometry. |
| J8 | Fixture/process integration | Regenerate the named entry-point outputs from the real recorded-source API test using the capture procedure in `docs/how-to/run-the-gates.md`. Verify metadata/text agreement and finalization with current native files. Do not modify production ledgers or use live sources. |
| J9 | Closure inspection | Search the affected current TypeScript path for the retired module, exports, dependency, config key and fields. Classify remaining matches: negative tests and shared Python input vocabulary are valid; executable robots retrieval, native output placeholders and old API aliases are not. Do not convert this into a growing-tree test. |

Table K - rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Decision basis |
| --- | --- | --- | --- | --- |
| K1 | Keep an off/observe mode or a dormant checker | Leaves a second behavior and its dependency/contracts after removal. | Permanent configuration, branches and tests for a capability that is no longer required. | A1, A4 |
| K2 | Delete general failure, lifecycle or safety checks with the robots branches | Removes useful non-robots behavior. | More repeated failures, incorrect counters or weakened destination/content controls; separate design and tests would be needed. | A4, E8-E9 |
| K3 | Remove shared Python vocabulary or global console measurements | Changes a separate active producer and its readers. | A cross-language format change, publication updates and broader consumer work. | B1-B2 |
| K4 | Split the removal into separately merged schema/runtime/report PRs | Leaves running callers and writers with incompatible current shapes between merges. | Temporary compatibility or broken intermediate releases. | A3-A4 |
| K5 | Rewrite historical health/rejection files to the new format | Alters recorded evidence and adds a data operation to a code removal. | A separately specified bounded conversion, index verification and data-loss recovery procedure. | A5, F6 |
