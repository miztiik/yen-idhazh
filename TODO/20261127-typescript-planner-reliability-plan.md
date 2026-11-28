# TypeScript planner failures and host identity

**Last Updated**: 2026-11-28

**Level**: 5 for rejection publication ownership; levels 2 and 3 for the independent corrections.

## 0 - Operating contract

Table A - intent and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Prevent avoidable repeated requests to rate-limited sources, preserve failure causes, count selection decisions correctly, and record the actual job on its host fingerprint. |
| A2 | Hard scope - in | Preserve typed failure evidence; make TypeScript source admission honor rate limits; separate selection totals from technical admission counts; verify the host job through delivery; seal one rejection file for each completed combined TypeScript planner attempt. Keep Python planning and digest worker inputs unchanged. |
| A3 | Incident evidence | Run `45986418578`, job `140463098651`, attempt `1`, code `fb63be4e800f5eb6a316669197fefa0a0b0bbd5a`, and output commit `7e05262c6514390d6242d513bc3cb9dd09af06de`. The planner completed. The runner log and committed rows are the evidence, not a reconstruction from current defaults. |
| A4 | Chosen strategy | Reuse native diagnostics and keyed request scheduling; capture the actual workflow identity; let the TypeScript planner seal run-owned rejections while the publisher delivers exact bytes. |
| A5 | ESCALATE triggers | 1. Pause before changing Parquet row shapes, historical files, standalone API behavior, or the fetched-data trust boundary. 2. Pause if pacing cannot preserve bounded execution and useful source coverage without a new scheduling design. 3. Treat continuing source failures as separate findings; do not broaden source policy or add cross-run state. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

Table B - explicit boundaries

| ID | What is out | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Reconstructing discarded historical causes or rewriting old host rows | The incident's generic lines remain unattributed individually, and historical host labels remain as written. | Original same-attempt evidence, or a separately approved historical correction that preserves immutable provenance. |
| B2 | Rewriting past rejection files or changing standalone write ownership | Historical attempts can still have multiple files; explicit standalone operations continue to own their own receipts. | A separate compatibility and recovery design with a bounded migration input. |
| B3 | Coordinating limits across runners, changing the source catalog, or changing access policy | This planner cannot prevent another process from consuming a shared quota. Permanent source refusals still need source-specific decisions. | Destination-level dispatch evidence of remaining rate limits after local pacing, or confirmed recurring access refusals and an authorized source alternative. |

## 1 - Status Reckoner

Table C - delivery rows

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Preserve the cause of failed planner work | - | A | DONE | - | - | - |
| C2 | 2 | Enforce source cooldown on outbound requests | 1 | B | DONE | - | - | - |
| C3 | 3 | Record the actual planner host job and task | - | A | DONE | laughing-tribble | - | 18d7ffc0-0d39-4d21-90f0-d9884a33281f |
| C4 | 4 | Count selection exclusions without counting technical refusals twice | - | A | DONE | improved-journey | - | cdc20e6b-0134-4e01-8163-83ac80090104 |
| C5 | 5 | Seal completed planner rejections once before delivery | 3 | B | PENDING | - | - | - |

## 2 - Row #1 - Preserve the cause of failed planner work

- **Scope:** Retain the source or planner failure that actually happened in the existing workflow log and mirror, separately from listener and HTTP request failures.
- **Files touched:**
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/schemas/planner-workflow-failure.schema.ts` (new)
  - `services/feed-ingest-plan/scripts/read-feed-api-diagnostic.ts`
  - `services/feed-ingest-plan/scripts/supervise-feed-api-task.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/logging/structured-logger.ts`
  - `services/feed-ingest-plan/test/relay-feed-api-events.test.ts`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/reference/serve-pipeline-apis.md`
- **Acceptance gates:** Locally use the shared changed-test selector, native checks and `relay-feed-api-events.test.ts`; CI runs the affected native suites. On a scheduled run after landing, group failures by cause and destination. Record first-party failures separately from publisher refusals and open a named follow-up for recurring types that are not addressed by row #2.
- **Oracle:** For a recorded source 429 followed by success, a terminal feed failure, a stage failure and a real Hono request exception, the real relay emits one correctly classified record per failed occurrence to stderr and its mirror. The original safe facts, occurrence and trace survive; hostile headers, URLs and bodies do not. This cannot identify the original events already discarded in A3.

Table D - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| D1 | The feed workflow's child-log adapter replaced 431 failed progress records from A3 outside the typed terminal-article format with `module_failed / API_OPERATION_FAILED`. The broad fallback originated in the shared-hosting split, where terminal article events were the only planner progress shape relayed with full native detail. No `typescript_api_request_failed` event was present. Keep the shared host's actual HTTP exception path separate. | Attempt log; `read-feed-api-diagnostic.ts`; hosting change #1931 |
| D2 | Declare one current-only, version-stamped `planner.workflow-failure` event with typed variants for failed dispatch, document failure (feed or article), policy refusal, history gap and planner-stage failure. Carry the original occurrence, trace, operation, run and validated attempt. For a failed dispatch, keep document kind, feed ID, publisher ID if known, opaque document identity, normalized destination domain, observed HTTP status, typed failure, available safe transport error code and retry/attempt ordinal. For other variants retain only the applicable known scope, identity and safe cause token; represent unavailable facts explicitly. Pass the validated event through the existing writer; keep terminal article diagnostics and true server request failures unchanged. | Existing planner logging and server event contracts |
| D3 | The producer supplies the typed facts, never a guess from an error message. Match run and attempt to the owned task. Do not copy raw headers, URL paths or queries, exception text or response bodies. Keep invalid diagnostic evidence visible under its existing refusal code. No new ledger columns or widening of the generic lifecycle event. | Fetched-data trust boundary; native diagnostic validation |

Table E - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Silence the lines or keep only terminal article failures | Retries that later succeed, source refusals, history and internal failures would still be invisible. | A separate diagnostic surface would need equivalent per-occurrence evidence to recover that information. | Incident scope |

## 3 - Row #2 - Enforce source cooldown on outbound requests

- **Scope:** Enable the existing source pacing for the planner, and prevent it and its retries from continuing to send requests to a source that just returned 429.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/planner-workflow-failure.schema.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-source.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/impit-transport.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/read-retry-after.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/request-pacing.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/transport.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/request-pacing.test.ts`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/architecture/sources/feed-harvesting.md`
- **Acceptance gates:** Locally use the shared changed-test selector, native checks and `request-pacing.test.ts` plus `harvest-safety.test.ts`; CI runs the affected native suites. On the first scheduled run with both rows landed, read the observed attempts, cooldown decisions, selected count, job duration and terminal 429s by affected source. Compare to F1, accounting for actual request volume and content coverage. Do not dispatch a publishing workflow as a check.
- **Oracle:** A recorded 429 followed by queued same-domain and same-publisher work produces no matching dispatch before the applicable cooldown expires; a different key continues. Cover both header formats, absent or invalid headers, cancellation and a window beyond the remaining operation budget. Recheck that feeds, article retries and redirects count only actual dispatches. This proves admission behavior, not a publisher's undisclosed quota.

Table F - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| F1 | The incident's `57cddbe8-e4db-8c53-9e5e-c2126f1db30e.parquet` rejection batch and log have 66 terminal article 429s: 60 from one feed and 6 from another. Both feed downloads succeeded. All affected articles recorded pacing disabled and no wait. Each URL could retry independently without consulting `Retry-After` or slowing its siblings. Re-derive feed IDs and counts from the rejection file and retry settings from the run revision. | A3; committed rejection and health rows; `fetch-source.ts` |
| F2 | Use the existing domain/publisher keys and queues for feeds, articles, retries and redirects. Turn on the existing checked-in pacing control. Update both applicable keys' earliest dispatch time before releasing the slot after a 429. Use the actual target's valid `Retry-After` delay or UTC date as a minimum, even if response-body reading later fails. With absent or malformed guidance, use the existing configured exponential backoff per key, starting at its initial delay, capped at its last configured retry delay, and reset on successful response or idle-key expiry. Apply the longest of the applicable reserved times and ordinary pacing. No profile switch on 429. | Native source transport and pacing contracts; RFC 9110 Retry-After |
| F3 | Acquire the existing shared network dispatch permit after keyed admission, not while waiting for a source. Keep bounded operation deadlines and retry counts; do not dispatch early to fit them. Preserve an observed 429 if there is no safe retry window. A queued document that runs out of budget before dispatch keeps the existing timeout result with no invented HTTP status, plus typed cooldown evidence and zero dispatched work. Keep expiry local to the scheduler; no change to run selection or publication. | Existing transport accounting, cancellation and runner bounds |
| F4 | Before row #5, collection retained terminal download or extraction failures ahead of selection, then selection persistence wrote post-parse decisions separately. A3 and manual run `45891277775`, output commit `e48504e7eff93b997ed39bb82fb5728e842f7628`, each produced both files with no repeated candidate identity. Both files went in the same commit, so the first local write was not a remote checkpoint. | Collection and persistence code; committed Parquet |

Table G - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Toggle pacing alone, or grow the per-URL retry delays | Fixed spacing does not honor a source's wait instruction. Independent retry delays still let requests to sibling URLs through. | Fewer bursts at the cost of slower harvesting, without a shared embargo or a predictable recovery rule. | A3 dispatch path; F2 |

## 4 - Row #3 - Record the actual planner host job and task

- **Scope:** Build the host writer identity from the trusted workflow job at startup and verify it independently against the Parquet row and footer before delivery.
- **Files touched:**
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-host-fingerprint.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-host-verification.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-metadata.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-current-files.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-delivery-result.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-api.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-client.ts`
  - `services/feed-ingest-plan/scripts/create-feed-api-app.ts`
  - `services/feed-ingest-plan/scripts/finalize-run-output.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts`
  - `services/feed-ingest-plan/scripts/finish-run-output.ts`
  - `services/feed-ingest-plan/test/article-entities-workflow.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-host.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `services/feed-ingest-plan/test/host-output-recordings.ts`
  - `services/feed-ingest-plan/test/host-recordings.ts`
  - `services/feed-ingest-plan/test/safe-persist-http.test.ts`
  - `docs/reference/host-metrics.md`
- **Acceptance gates:** Locally use the shared changed-test selector, native checks and the named host, workflow, finalization and Safe Persist HTTP tests; CI runs the affected native suites. On the next scheduled digest after landing, compare the actual job and runner to the host Parquet and verify that the changed file reached the default branch. Do not rerun A3 or rewrite its ledger.
- **Oracle:** The existing native capture, readback and delivery validation produce a host file with the exact caller job, run, attempt, revision and task, and reject a different job even if its own receipt and file agree. The manual caller retains its identity and the separate Python plan is not admitted as this job's host. This cannot relabel a historical row.

Table H - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | `hostWriter` supplied the manual job's `isolated-plan` value to both job and task for A3. Record validated `GITHUB_JOB` as `job` and `task_name` for the one planner task per job: `plan-typescript` in digest and `isolated-plan` in the manual workflow. Keep pipeline `feed-ingest-plan`, shard and producer unchanged. Missing or invalid job identity fails the workflow adapter, not standalone CLI/API consumers. | Job metadata and saved host footer; host identity contract |
| H2 | Pass independently validated job identity into capture, verification, artifact preparation, cleanup and the delivery child's private startup. Do not derive the expected job from the receipt, HTTP request body or filename. Keep the existing legacy read allowance only for the matching invocation; no fallback to the manual job for new digest writes. | Existing private startup and exact-file verification boundary |

Table I - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Correct the label in the report or hard-code the digest job in the shared writer | A report would leave the underlying join wrong; a second hard code would make the manual caller wrong again. | Every new caller would need another label override, with no ledger-level check. | H1 and H2 |

## 5 - Row #4 - Count selection exclusions without counting technical refusals twice

- **Scope:** Report selection decisions and technical admission refusals separately so a source-attributed refusal cannot inflate a selection total.
- **Files touched:**
  - `services/feed-ingest-plan/src/reporting/selection-exclusions-markdown.ts`
  - `services/feed-ingest-plan/test/failure-evidence.test.ts`
  - `docs/how-to/run-feed-ingest-plan-test.md`
- **Acceptance gates:** Locally use the shared changed-test selector, native checks and `failure-evidence.test.ts`; CI runs the affected native suite. On the next authorized manual run that writes a report, compare the affected rows in "Why articles were not selected" with its saved response and rejection receipts. Do not dispatch a publishing workflow just to verify the report.
- **Oracle:** For a recorded technical refusal and selection decision with the same reason, differing totals for another reason, and a technical-only partial result, render exactly the recorded ordinary exclusions in the selection total and retain the separate technical evidence. Neither input is mutated. This cannot count unique stories or recover an unrecorded decision.

Table J - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| J1 | A3's detailed ledger has 231 candidate decisions for `PAYWALL_OR_BLOCKED`. The feed-health rows have 231 source-attributed technical refusals and 231 selection decisions for that reason, matching by feed. The manual report listed 510 exclusions for 255 detailed decisions by summing both measures. This is report double-counting, not a duplicate produced by the two Parquet writes. | F4; `run-health.ts`, `select-articles.ts`, `selection-exclusions-markdown.ts`; manual report artifact `15152336516` |
| J2 | Use existing `subject`, `stage` and `attribution`. Count only ordinary article exclusions (`attribution: null`) in the selection total. Keep source-attributed screening refusals visible as technical-admission evidence with their own counts and an explicit note that the measures are not additive. Keep network and extraction failures in Needs attention. Do not fill missing selection evidence from technical counts. No change to ledger rows, technical pass-rate inputs, or request accounting. | Feed planner ledger reference and current article-admission reader |

Table K - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Deduplicate by URL, add both counts, or take the larger count per reason | Different captures of a shared URL are different decisions; two measures without candidate-level pairing cannot be combined into an exact count. | A separate unique-URL question or a new candidate-level combined measure would require its own contract and denominator. | F4 and J1 |

## 6 - Row #5 - Seal completed planner rejections once before delivery

- **Scope:** Have the combined TypeScript planner settle its complete rejection output once per attempt and retain diagnostic or recovery evidence without publishing partial rejection rows as completed output.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `services/feed-ingest-plan/src/api/collection-contracts.ts`
  - `services/feed-ingest-plan/src/api/collection-operation.ts`
  - `services/feed-ingest-plan/src/api/persistence-operation.ts`
  - `services/feed-ingest-plan/src/api/routes/stages.route.ts`
  - `services/feed-ingest-plan/src/api/stage-response.schema.ts`
  - `services/feed-ingest-plan/src/record-harvest-failures.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-current-files.ts`
  - `services/feed-ingest-plan/scripts/finalize-run-output.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/publishing/committing.md`
  - `docs/reference/feed-planner-ledgers.md`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** Locally use the shared changed-test selector and focused native plan, collection, failure retention, and finalization tests; CI runs the affected suites. Observe the first scheduled digest using the new revision. Do not trigger a data-writing run as a check.
- **Oracle:** Drive a real owned plan with a harvest failure and a screening refusal. Read one final Parquet file with both outcomes, including distinct captures of a shared URL; replay the same finalization without changing bytes. Exercise conflicting decisions, zero rows, failed selection, standalone calls, and unconfirmed delivery. Failed planning earns no final rejection receipt; delivery retry preserves exact bytes and does not refetch. This cannot protect temporary evidence if the runner disappears before any upload or push.

Table L - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| L1 | Defer rejection writes only for the combined run's proven owned collection. The collection and persistence stage responses distinguish deferred rejection output explicitly from empty output; never return a false empty receipt. Standalone stage responses and individual writes keep their current shape and behavior. Use server-owned captured decisions, not rows supplied by a workflow request. | Fowler review; existing collection ownership |
| L2 | The combined collection finalizer seals validated harvest and selection decisions only when planning completes. Settle by `(run_id, attempt, candidate_id)`: collapse identical copies, refuse contradictory rows, and keep different offers of one URL. Use stable order and the existing explicit empty receipt when there are no rows. The combined response retains `files.rejected_articles`; current readers still accept historical multi-file receipts. Do not change Parquet columns or deduplicate by URL. | Existing rejection identity and receipt contracts |
| L3 | Failed or cancelled planning does not publish a completed rejection file. Preserve available diagnostic evidence separately from canonical rejection rows; do not withdraw valid independent run or host records. When Git delivery is unconfirmed, reuse the existing exact-file recovery package and publish only verified metadata as recovery evidence, without adding scheduled article-text upload. Delivery checks remote bytes or retries that package, not the planner. | Existing verification and safe delivery boundaries |

Table M - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Merge rejection files in the publisher | The publisher would need planning identity and lifecycle rules, and would silently accept contradictory stage ownership unless it replicated those rules. | Another owner for the rejection decision and another verification path to maintain. | L1 and L2 |
| M2 | Publish partial rejection files as completed output | A failure would change selection statistics without anyone being able to tell from the rejection receipt. | A separate persisted partial-outcome contract and reader behavior. | L3 |
