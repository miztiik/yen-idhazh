# Reduce Bun test work

**Last Updated**: 2026-10-31
**Level**: 2 - change test coverage and shared test inputs without changing runtime behavior.

## 0 - Operating contract

Table A

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Prove the API and CLI work without repeating whole planner runs for validation, formatting, storage and policy checks. |
| A2 | In scope | Planner Bun tests, their recorded inputs, dead test helpers, unnecessary Git setup, duplicate file writes/readbacks, and directly related gate documentation. |
| A3 | Required entry-point coverage | At completion of both phases, keep exactly one successful recorded API execution and one successful recorded CLI execution per suite run, as defined in Table D. Short tests of independent failure boundaries remain at their own stage. |
| A4 | Chosen strategy | Delete the oversized comparison and redundant full-run cases; give deterministic rules recorded inputs and exercise their real native implementations at the smallest useful boundary. The existing test tiers in [section 13](../CLAUDE.md#13-test-coverage-policy) define those boundaries. |
| A5 | Inspection scope | Tables E and F name the complete removal and simplification list. Test filenames in those tables are relative to `services/feed-ingest-plan/test/`. Helper-only callers retain their behavior checks. |
| A6 | Runtime prerequisite | Apply this cleanup to the integrated collection, parser-admission, cancellation-output and named-history-reader repairs and the current delivered handoff contract. Do not restore an obsolete snapshot, availability sidecar, intermediate Git publication, delivery checksum, durable replay or reopening capability. Preserve added repair regressions for behavior that the current contract retains. |
| A7 | Contract boundary | Change no production payload, schema, configuration default, public API or CLI behavior. New recordings use existing native models, not a new aggregate fixture format. |
| A8 | Escalation | Stop if a proposed removal loses a distinct safety or data-preservation check, needs a mocked stage, or requires changing runtime behavior or a persisted contract. Name the missing check and the smallest real boundary that can prove it. |
| A9 | Current status | Execution is active. The status reckoner records each phase; the second phase starts after the first phase is delivered. Production dispatch remains outside this plan. |
| A10 | Execution | Execute per docs/how-to/execute-a-plan.md. Parallel N = 1 because both phases change shared test inputs and coverage. One maintainer coordinates a separate nested implementation session for each phase, verifies its changes and checks, and delivers the phases sequentially. |

Table B

| Id | Out of scope | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Planner implementation and production runs | This work reduces test work, not production collection time; production verification remains a separate task. | A defect in runtime behavior, handled separately from test retirement. |
| B2 | Non-planner Bun suites, Python suites and frontend tests | Their existing checks and CI cost remain. This plan does not claim repository-wide test reduction. | A demonstrated dependency on a helper changed here. |
| B3 | A new native selector, reporter integration or test framework | Native local selection remains explicit; the shared launcher still does not execute Bun. | A separate tooling task with its own selection and reporting contract. |
| B4 | Exhaustive entry-point permutations | Every policy, failure and storage combination will no longer run through a fresh API or CLI process. Their deterministic rules remain covered below the entry points. | A distinct transport or process failure that the retained small checks cannot detect. |

## 1 - Status reckoner

Table C

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Keep minimum entry-point coverage | - | A | PENDING | - | - | - |
| C2 | 2 | Move remaining checks to their own boundaries | 1 | B | PENDING | - | - | - |

## 2 - Test change inventory

Table D - Required entry-point tests

| Id | New test | Real execution and acceptance |
| --- | --- | --- |
| D1 | `one recorded API request writes a valid selected artifact` in `plan-entry-points.test.ts` | Use the real supervised child and workflow HTTP client with recorded source responses. Send one top-level plan request. Require a valid successful response, a nonempty selected artifact with actual text, matching selected metadata, and release of the exact owned child/listener. Keep one progress-before-completion observation, not a progress matrix. |
| D2 | `one awaited CLI invocation writes one valid result` in the same file | Start one real Bun child that calls the existing awaited CLI entry with its real argument parser and output writer. Supply recorded source transport through the test wrapper. Require exit zero, one valid JSON result on stdout and the actual selected artifact. Do not duplicate parsing, printing or planning in the wrapper. |
| D3 | Configuration coverage | Use one valid configuration for each entry point: API with partitioning enabled and CLI with partitioning disabled. Verify their basic assignment/result shape once. Keep strategy mathematics and invalid controls in the existing small tests, not an API-by-CLI configuration matrix. |
| D4 | Size limit | Use the named RSS, HTML and transport recordings with only enough articles to produce a real result. Do not append content-filter, history, replay, alternate-partition or repeated-persistence runs to either test. |

Table E - Delete these existing tests in their entirety

| Id | File | Test | Retained proof |
| --- | --- | --- | --- |
| E1 | `plan-api.test.ts` | `actual API and awaited CLI compose the same recorded plan and disclose the same audit limit` | Table D and the current stage, live-handoff, partition, filtering and storage checks. Delete the complete declaration and body; do not split, rename or repackage it. |
| E2 | `plan-api.test.ts` | `a listener keeps first-seen evidence stable across UTC midnight` | Recorded discovery/timing checks in `triage.test.ts`, `early-age.test.ts`, `health-fields.test.ts` and F9. |
| E3 | `plan-engine.test.ts` | `real composition separates run and selection clocks and reads native dispatches with exact choices` | Table D plus the existing clock, metadata, screening and packing checks. |
| E4 | `plan-engine.test.ts` | `freshness equality is admitted; a smaller override really rejects; empty is not complete` | Existing age-boundary checks and F22's real empty-output check. |
| E5 | `plan-engine.test.ts` | `zero selected articles still persist every parsed refusal without article text` | F2's stage-level refusal persistence and F22's empty artifact. |
| E6 | `plan-engine.test.ts` | `persisted discovery wins for undated articles; empty history does not prove absence` | Existing discovery/history readers and F9; no repeated complete runs to advance the clock. |
| E7 | `plan-engine.test.ts` | `invalid controls, disabled runs, inactive ledgers and unavailable named history fail before fetching` | F6, F36, current lifecycle/history checks, and native writer lifecycle checks. |
| E8 | `plan-engine.test.ts` | `real dispatch persistence failure leaves earlier files but emits no storage completion` | F5, F7 and F29, plus the small run-outcome checks defined in J2. |
| E9 | `plan-cli.test.ts` | `real CLI process refuses disabled or invalid requests without Python or network` | F36's real request parser and error-description checks; no repeated cold CLI processes for values a pure parser can refuse. |
| E10 | `plan-cli.test.ts` | `the awaited entrypoint records configured selection counts, signed ages and global discovery` | D2 for awaiting/output; existing timing, policy and discovery checks for the three looped scenarios. |
| E11 | `plan-cli.test.ts` | `a real selected-metadata write failure prints an explicit partial run instead of success` | Stage-level storage refusal and run-result validation in F5, F7 and J2. |
| E12 | `progress.test.ts` | `live progress precedes completion and the structured event stream stays sparse and body-free` | D1's ordering observation; event-model/report checks and existing recorded extraction-warning checks. Delete the file if empty. |
| E13 | `feed-ingest-plan-http-client.test.ts` | `the client retains verified output and batch health while its caller keeps the listener` | D1 uses the real client; F18 checks the saved handoff without planning again. Keep the separate disabled-listener failure check. |
| E14 | `feed-ingest-plan-supervisor.test.ts` | `separate child preserves prepared identity, native files and live batch health` | D1 carries the real successful child boundary. Preserve independent startup, ownership and cancellation checks. |
| E15 | `operation-logging.test.ts` | `composed document failures include addresses without success leaks or duplicate persistence` | F25-F28 and the existing publisher/sanitizer checks; no extra full plan for logging alone. |
| E16 | `collection-http.test.ts` | `HTTP collection completes all feeds before global selection; partition enabled=true` | D1 exercises the enabled route path; the small collection completion check still protects global completeness. |
| E17 | `collection-http.test.ts` | `HTTP collection completes all feeds before global selection; partition enabled=false` | D2 exercises the bypass path. Remove both generated variants, not just one loop value. |
| E18 | `collection-http.test.ts` | `valid empty feed completes a truthful empty output without partition requests` | Existing empty-feed parsing checks and F22; no extra full planner execution. |
| E19 | `curate.test.ts` | `empty writes have no invented files and real failures cannot report completion` | `packages/ledger-file-writer/test/parquet-parity.test.ts`, `persist-ledger.test.ts`, and F22. This case tests the shared writer, not curation. |

Table F - Simplify these tests, retaining the stated rule

| Id | File | Existing test | Smaller real check |
| --- | --- | --- | --- |
| F1 | `article-failure-retention.test.ts` | `terminal HTTP, DNS, TLS, timeout, robots and extraction failures survive zero-selection finalization once` | Use one bounded input setup and the recorded terminal cases at fetch/parse/retention boundaries. Read actual rejected Parquet and check every recorded outcome field and deduplication. Remove the fresh-fixture/full-plan loop. |
| F2 | `article-failure-retention.test.ts` | `harvest and screening refusals both survive the same zero-selection run` | Give the real persistence stage a complete recorded batch containing both refusal stages; require both native rows and an empty selected artifact. Do not harvest a whole feed again. |
| F3 | `article-failure-retention.test.ts` | `a successful retry leaves no stale rejection and keeps selected identity and content` | Exercise the recorded retry and its real terminal capture once, then verify retention/identity from that result. Do not select, partition and finalize another whole run. |
| F4 | `article-failure-retention.test.ts` | `observed denial retains actual terminal target failures in one all-failed batch` | Keep observed robots facts and actual target-error fields at the fetch/capture boundary, with native readback; no complete planner run. |
| F5 | `article-failure-retention.test.ts` | `completed failures survive a later selected-ledger write failure` | Prewrite actual rejected rows, obstruct the real selected-output destination, and exercise persistence only. Require the prior bytes to survive and the write failure to remain explicit. |
| F6 | `plan-api.test.ts` | `health is explicit; disabled, malformed, oversized and unknown controls cannot fetch` | Keep one small HTTP refusal/health check; put the field-value matrix in native request/config validation. Require zero source work. |
| F7 | `plan-api.test.ts` | `a required source write failure returns an API error, not proven planning completion` | Use native stage inputs and a real filesystem obstruction. Check the stage error, retained siblings and public partial-result semantics; remove the extra capture fixture, progress-driven mutations and repeated top-level plans. |
| F8 | `plan-api.test.ts` | `one listener retains durable seen receipts from an output root outside the checkout` | Use overlapping standalone document requests and the real parser pool with the current live handoff. Keep bounded admission, independent identities and current work accounting without complete plans or inflated HTML. Drop obsolete durability/replay assertions when their contract is retired. |
| F9 | `plan-api.test.ts` | `a later dispatch failure does not lose discovery already persisted by this listener` | Retain a bounded check that collection completion writes discovery and a later persistence failure leaves those bytes unchanged. Use the delivered live document/stage references and their actual UTC work dates; do not recreate restart recovery or saved-response replay. Retire the old case if the runtime cutover already removed it. |
| F10 | `article-url-cleanup.test.ts` | `query variants retain their offer ordinals and downloads but produce only one selected key` | Parse the recorded offers, perform their bounded fetch/capture, then invoke selection once. Keep ordinals and canonical-key deduplication; omit finalization. |
| F11 | `article-url-cleanup.test.ts` | `scheme cleanup retains accepted offers while an oversized cleaned address is refused` | Use identity normalization, the permitted fetcher and recorded feed parsing directly. Keep the no-dispatch assertion for the oversized address; no whole plan. |
| F12 | `early-age.test.ts` | `real planning records early losses once in native health counters without fetching stale pages` | Drive early admission and collection completion with recorded stale offers. Verify discovery and actual health counters at that stage; remove the CLI run. |
| F13 | `early-age.test.ts` | `empty RSS and Atom category labels never become invalid selected metadata or artifact labels` | Parse the named format recordings and pass their normalized labels through the real candidate/selected models. Remove fetching and the CLI run. |
| F14 | `feed-first-use.test.ts` | `fresh HTTP runs reload observed partial failure counts through rest and confirmed recovery retirement` | Feed recorded check results through the real lifecycle reducer and native save/reload boundary. Test configured rest/recovery boundaries without a complete HTTP plan for every counter increment. |
| F15 | `feed-first-use.test.ts` | `real recorded transport failures count for first-use rest without qualifying as confirmed retirement` | Capture one real recorded transport failure and apply the lifecycle calculation directly. Keep unknown completeness and the absence of confirmed retirement. |
| F16 | `feed-lifecycle-http.test.ts` | `concurrent snapshots each apply actual work once; late publication preserves both runs without sidecars` | Apply one recorded check to each independent baseline, write real native rows, and deliver them in reverse order through real local Git origins. Keep both immutable results; remove the seed plan and both collection runs. |
| F17 | `failure-evidence.test.ts` | `groups actual failure rows by subject, reason, status and attribution` | Render declared recorded health/result inputs directly. Keep grouping, missing-cause distinctions and escaping; do not run the planner to obtain a base row. |
| F18 | `feed-ingest-plan-outputs.test.ts` | `actual HTTP output retains selected text separately from its strict metadata manifest` | Consume the captured result and actual native files from G1. Test handoff, body separation and recovery packaging without another HTTP plan. |
| F19 | `feed-ingest-plan-outputs.test.ts` | `one real result and every native file stay unchanged through both report modes` | Render the same recorded result in both modes and retain one byte/value immutability check. Remove exact total-table counts, incidental phrase checks and extra history calculations. |
| F20 | `feed-ingest-plan-outputs.test.ts` | `uses actual selected identities and rejects inconsistent counts, assignments and foreign paths` | Drive output creation and validation from the declared captured result plus deliberate invalid mutations. No fresh selection/partition run. |
| F21 | `feed-ingest-plan-outputs.test.ts` | `refuses mismatched counts, damaged bytes and missing actual files` | Create one native file from recorded rows using the shared writer; keep actual corruption/removal checks. Do not harvest or plan to get that file. |
| F22 | `feed-ingest-plan-outputs.test.ts` | `zero selections have an explicit empty ledger and an actual empty artifact` | Invoke the real output/persistence boundary with an empty declared batch. Keep the actual artifact and explicit empty result; remove the CLI invocation. |
| F23 | `request-report.test.ts` | `sorts request rows by article requests, feed requests, then name with unknown values last` | Render the existing request-row recordings directly; no base planner run or extra health summary. |
| F24 | `request-report.test.ts` | `sorts feed results by admitted and chosen articles, and exclusions by count then reason` | Use recorded health/result inputs and the real renderer. Keep ordering, totals and unavailable-value semantics. |
| F25 | `operation-logging.test.ts` | `standalone document work logs failure addresses only and persistence logs one real write` | Keep one representative real document failure and one real persistence failure boundary, using the delivered handoff. Remove obsolete journal replay checks and successful content/selection/partition permutations already covered elsewhere. |
| F26 | `operation-logging.test.ts` | `failed redirected feeds identify the requested URL and final dispatched target` | Drive the real recorded fetch operation only and inspect its published event. |
| F27 | `operation-logging.test.ts` | `feed byte cutoffs include the limit and observed lower bound in failure events` | Exercise one bounded response stream at the fetch/logging boundary, not a full run. |
| F28 | `operation-logging.test.ts` | `robots byte cutoffs identify the feed but never claim its target request was dispatched` | Exercise the real robots/fetch boundary and keep the no-target-dispatch and observed-limit checks. |
| F29 | `feed-ingest-plan-supervisor.test.ts` | `partial planning retains completed-file diagnostics and the original failure` | Supply real completed native files, then cause a short real child/request failure. Verify diagnostics, original error and listener release without harvesting another selected result. Do not substitute a fake server response. |
| F30 | `collection-work.test.ts` | `large feeds retain every rejection without per-offer collection snapshots or rejected HTTP requests` | Keep multiple feeds, a bounded rejected tail, exact terminal accounting and no hot-path snapshot/dispatch for rejected offers. Use direct collection operations and only enough admitted work to expose the state/concurrency rule; remove the full plan and surplus article parsing. |
| F31 | `collection-work.test.ts` | `explicit health reads capture current collection work without allowing premature selection` | Keep the existing short stage sequence with minimal recorded inputs. Do not add selection, partition or a completed plan. |
| F32 | `collection-work.test.ts` | `cancellation drains owned requests and retains partial accounting without selecting unfinished work` | Start bounded collection work, cancel through its real owner and verify drain, partial health and refused selection at that boundary. No top-level full planner run. |
| F33 | `run-policy.test.ts` | `the private child boundary preserves isolated age policies and fences different effective controls` | Use a declared startup recording and the real restore/validation code; do not create unused listeners, origins or planning output. |
| F34 | `feed-ingest-plan-supervisor.test.ts` | `startup rejects executable runtime members, unknown controls and non-loopback listeners` | Validate a declared startup recording directly. No child, port reservation or generated planner repository is needed for schema refusal. |
| F35 | `feed-ingest-plan-report.test.ts` | `absent progress stays unavailable and zero counts do not certify publication` | Format recorded progress and hardware rows directly. Remove hardware collection/persistence from a report-formatting case; hardware API tests retain that responsibility. |
| F36 | `plan-cli.test.ts` | `CLI blanks are absent; typed API strings, nulls, unknown fields and invalid numbers refuse` | Keep native parser/config refusal tables and effective-setting bindings. Remove assertions pinning current tunable defaults to literal values; compare effective settings to their declared configuration inputs. |
| F37 | `curate.test.ts` | `actual selected Parquet has exactly metadata columns while the same choice retains artifact text` | Make this a small metadata-projection/artifact-model check against the chosen values. Native writer/reader tests own Parquet columns and bytes. Remove the duplicate Parquet write and double decoding. |
| F38 | `partition.test.ts` | `uneven real curated selections have exact greedy assignments and lower spread than round robin` | Keep the exact recorded assignments, work totals and order independence with in-memory declared inputs. Remove native writes/readbacks from this mathematics check. |
| F39 | `partition.test.ts` | `equal work, fewer articles, empty selection and none keep exact selected identities` | Keep bounded input vectors and actual packing results; do not generate a ledger just to supply an empty array or equal work. |
| F40 | `partition.test.ts` | `missing content, duplicate URLs and invalid ranks are refused without mutation` | Validate and pack declared recorded inputs directly; keep refusal and immutability without fixture writes. |
| F41 | `partition.test.ts` | `packing retains actual timing, accounting dates and text rather than reconstructing a dispatch payload` | Compare real packing output to the original in-memory item. Native serialization has its own coverage. |
| F42 | `partition.test.ts` | `configured screening, curation and packing preserve chosen originals` | Compose those real functions against bounded recorded inputs without the helper's unconditional metadata write. |

Table G - Shared input and dead-code changes

| Id | Change | Required invariant |
| --- | --- | --- |
| G1 | Capture the response, health, selected artifact and every actual planner ledger's rows from the same verified D1 execution before its generated directory is cleaned. Store separate named recordings under `tests/fixtures/feed-ingest-plan/entry-points/`; use the five `.rows.json` paths listed in row 1. Give downstream tests actual native files through `planner-output-recordings.ts`, using the real shared writer and rebuilding receipts from its actual results. | Load recordings inside tests. Validate public recordings with their existing response/artifact models and each row transcript with its existing ledger row model's array schema. Do not reconstruct missing discovery or rejection facts from summary counts. No invented successful response, new aggregate fixture schema, extra fixture-generation planner run or dependency on another test having run first. |
| G2 | Separate recorded inputs from full planning in `plan-recordings.ts`. Remove the unused content-filter-plan helper after E1. Keep minimal local revision setup only where a test actually reads Git history. | No README, bare origin, remote registration or push for ordinary API, parser, renderer or policy setup. Do not weaken a named-history proof or Git security control to avoid setup. |
| G3 | Extract `fixtureGit` into `fixture-git.ts` and update every actual importer listed in row 2. | A Git helper must not import the planner, start a listener or produce application output. Use only each test's own generated repository. |
| G4 | Change `publicationRecording()` to prepare real native files and required local Git origins, without calling the whole planner. | Keep genuine delivery, refusal, consent, artifact recovery and cleanup tests. Native file provenance and completed/partial result shapes remain validated. Use the current `sourcePath`/`targetPath` delivery inputs, not retired delivery checksums or byte-count handoff fields; native envelope, row, content-digest and row-count validation remain. |
| G5 | Give `recordedPlannerProcess()` and the new CLI wrapper only the authored inputs each process check needs. | Successful full planning is reserved for Table D. Startup/ownership failures and cancellation still use real child processes where that process boundary is the failure being tested. |
| G6 | Separate in-memory partition inputs into `partition-recordings.ts`; keep native writer/history helpers in `partition-fixtures.ts`. | Pure mathematics does not write files or discover history. Actual writer/reader tests still use real Parquet. |
| G7 | Delete unused `compaction-recording.ts` after checking named callers. | The current `logical-completion.test.ts` uses native rows directly and must retain its actual compaction checks. Do not claim removal of this unused generator saves active test runtime. |
| G8 | Replace the obsolete extended-timeout advice in the gate notes with the selected native commands and actual timeout policy. | No timeout increase, added sleep, skip or retry stands in for removing repeated work. |

Table H - Keep these distinct checks

| Id | Surface | Failure that must remain detectable |
| --- | --- | --- |
| H1 | `harvest-safety.test.ts`, `article-robots-policy.test.ts`, `robots-entry-points.test.ts` | Unsafe destinations, redirect/robots mistakes, request cancellation, secret leakage and incorrect retry/byte-limit behavior. |
| H2 | `parser-deadline.test.ts` and the parser-admission repair regression | Queued/running worker cancellation, deadline enforcement, worker replacement, bounded admission and listener responsiveness. Fold the latter into D1 or a short pool/stage check, not another full plan. |
| H3 | `raw-day-members.test.ts`, `ledger-history.test.ts`, `health-fields.test.ts`, `history-window.test.ts`, `planning-health.test.ts` | Exact named Git input, stale or incomplete history, corrupt/foreign bytes, partial fields and incorrect UTC windows. |
| H4 | `feed-lifecycle.test.ts`, `feed-lifecycle-history.test.ts`, `feed-reliability.test.ts`, `saved-reliability.test.ts`, `article-source-outcome.test.ts` | Incorrect rest/retirement, double-counted retained snapshots, fabricated completeness and selection mistaken for source quality. Preserve current live outcome accounting, not retired private-journal recovery. |
| H5 | `logical-completion.test.ts` and the shared native writer/reader suites | Lost attempts, incorrect compaction keys, wrong row/column types, content in metadata and invalid format acceptance. |
| H6 | Remaining supervisor/HTTP-client checks | Stopping an unrelated listener, wrong child identity, failed startup, owner disappearance, failure to drain/reap, and transport errors reported as success. |
| H7 | `feed-ingest-plan-finalization.test.ts`, delivery and host-file validation checks | Wrong Git delivery, lost recovery output, success on cancellation, consent/provenance failure and deletion outside the generated run directory. |
| H8 | Existing screening, curation, policy and packing rules | Wrong admission, ranking, source/topic limits, timing, assignments or mutation. Remove their incidental setup, not the rules. |

## 3 - Row #1 - Keep minimum entry-point coverage

- **Scope:** Deliver Table D, delete every case in Table E, and keep short request/outcome checks in the affected files.
- **Files touched:**
  - `services/feed-ingest-plan/test/plan-entry-points.test.ts` (new)
  - `services/feed-ingest-plan/test/planner-cli-recording.ts` (new)
  - `services/feed-ingest-plan/test/planner-server-recording.ts`
  - `services/feed-ingest-plan/test/planner-process-recordings.ts`
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-cli.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/progress.test.ts` (delete when empty)
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-http-client.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `tests/fixtures/feed-ingest-plan/entry-points/response.json` (new recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/health.json` (new recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json` (new recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/discovered-articles.rows.json` (new native row recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json` (new native row recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json` (new native row recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json` (new native row recording)
  - `tests/fixtures/feed-ingest-plan/entry-points/plan-runs.rows.json` (new native row recording)
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261031-reduce-bun-test-work-plan.md`
- **Acceptance gates:**
  - Local: inspect `npm --prefix .\frontend run test:changed -- --list`; do not execute its Python/frontend fallback as proof of Bun coverage.
  - Local: run `bun run --cwd .\services\feed-ingest-plan check`.
  - Local: run `bun run --cwd .\services\feed-ingest-plan test .\test\plan-entry-points.test.ts .\test\plan-api.test.ts .\test\plan-cli.test.ts .\test\plan-engine.test.ts .\test\collection-http.test.ts .\test\feed-ingest-plan-http-client.test.ts .\test\feed-ingest-plan-supervisor.test.ts .\test\operation-logging.test.ts .\test\curate.test.ts`.
  - Local: preserve declared deadlines, capture actual executed counts and case times, and check that the removed full-run bodies have no alternate name or location.
  - CI: the full existing merge-candidate gates remain authoritative; do not require another local full suite.
- **Oracle:** D1 and D2 each produce an actual valid saved result, with one recorded plan start per execution; the complete E1 body is absent. This cannot settle live-source reliability, production collection speed or all entry-point permutations.

Table I - Row 1 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | The comparison test is deleted in its entirety, not moved into smaller timeout windows. | Plan scope, E1. |
| I2 | Put only basic execution/output assertions in the new entry-point tests; deterministic rules retain their own tests. | [Test coverage policy](../CLAUDE.md#13-test-coverage-policy). |
| I3 | The test child wrappers call real runtime functions and use only recorded external source responses. | [Real fixtures and trust boundary](../CLAUDE.md#1-adaptive-guardrails-read-first-every-session). |

Table J - Small checks retained in row 1

| Id | Check | Distinct failure |
| --- | --- | --- |
| J1 | Native request/config parsing and public error description in `plan-cli.test.ts` and `plan-api.test.ts`. | Invalid controls accepted or unsafe failure details exposed. |
| J2 | Small completed/partial/failed run-result checks in `plan-engine.test.ts`, using existing recorded row/result models and the real summary/response validation. | An unsuccessful recorded result described as complete, or saved result/identity disagreement. These are result-boundary checks, not claims that every orchestration failure was exercised. |

Table K - Row 1 rejected alternatives

| Id | Option | Why rejected | Cost of taking it | Authority |
| --- | --- | --- | --- | --- |
| K1 | Split the old comparison body across tests. | It retains the repeated work and violates E1. | The same planning, parsing and storage work remains; measure its actual case times from the runner output. | Plan scope. |
| K2 | Remove all failure, history and worker checks. | A successful entry-point run cannot detect the distinct failures in Table H. | Lost reader-safety, data-preservation and process-ownership coverage. | Existing safety boundaries and test tiers. |
| K3 | Fake an API or CLI success. | It proves the replacement response, not the capability. | Real transport, parsing, file output and process behavior are no longer exercised. | Existing real-fixture requirement. |

## 4 - Row #2 - Move remaining checks to their own boundaries

- **Scope:** Implement Table F and Table G without discarding Table H's distinct protections, then document and measure the final selected suite.
- **Files touched:**
  - `services/feed-ingest-plan/test/planner-output-recordings.ts` (new)
  - `services/feed-ingest-plan/test/fixture-git.ts` (new)
  - `services/feed-ingest-plan/test/partition-recordings.ts` (new)
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `services/feed-ingest-plan/test/publication-recordings.ts`
  - `services/feed-ingest-plan/test/planner-process-recordings.ts`
  - `services/feed-ingest-plan/test/partition-fixtures.ts`
  - `services/feed-ingest-plan/test/compaction-recording.ts` (delete if still unused)
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-url-cleanup.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/collection-work.test.ts`
  - `services/feed-ingest-plan/test/early-age.test.ts`
  - `services/feed-ingest-plan/test/feed-first-use.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-http.test.ts`
  - `services/feed-ingest-plan/test/failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
  - `services/feed-ingest-plan/test/request-report.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-cli.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-report.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/run-policy.test.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `services/feed-ingest-plan/test/partition.test.ts`
  - `services/feed-ingest-plan/test/raw-day-members.test.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `services/feed-ingest-plan/test/logical-completion.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-history.test.ts`
  - `tests/fixtures/feed-ingest-plan/entry-points/response.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/health.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/discovered-articles.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/plan-runs.rows.json`
  - `docs/how-to/run-the-gates.md`
  - `docs/reference/agent-notes/gates-and-builds.md`
  - `TODO/20261031-reduce-bun-test-work-plan.md`
- **Acceptance gates:**
  - Local: inspect the shared selection, then run the service's native check and the explicit changed test files from this row, together with `plan-entry-points.test.ts`. Do not interpret the shared launcher as Bun coverage.
  - Local: run actual Parquet/SQLite/Git/worker/loopback checks where Table H requires them. Reuse an unchanged valid check record instead of launching an overlapping run.
  - Local: record the revision, named selection, host, total wall time, actual case times and completed/failed/filtered counts outside the repository. Do not invent a speed percentage or compare unlike selections.
  - Local: inspect the named test files and helpers for remaining full-run construction; only Table D may complete successful whole-planner journeys. Short real failure-boundary attempts remain explicit and must not harvest a whole corpus.
  - Local: confirm no test reads a growing committed tree, no test relies on another test's output, and no shared helper silently provides a successful result.
  - CI: run the existing full merge-candidate gates once. Confirm retained native writer, history, process, delivery and safety tests actually execute.
- **Oracle:** Each F entry retains its named failure rule using real bounded inputs, while downstream helpers create no complete planning run and ordinary inputs create no unused remote. Table D remains the only successful whole-planner coverage. This cannot certify production runtime or erase the cost of genuine native/process failure checks.

Table L - Row 2 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | A renderer, validator or publisher receives recorded output at its own input boundary; it does not regenerate that output by planning. | [Test tiers and bounded input](../CLAUDE.md#13-test-coverage-policy). |
| L2 | Required native and Git/process boundaries stay real; only repeated setup and unrelated upstream work disappear. | Table H. |
| L3 | Case counts come from actual runner reports; loops inside one case are accounted for separately. | [Measurement discipline](../CLAUDE.md#1-adaptive-guardrails-read-first-every-session). |
| L4 | Rename a simplified test when its old title claims a full planner execution or Parquet work that it no longer performs. | Plain, accurate names; Table F. |

Table M - Row 2 rejected alternatives

| Id | Option | Why rejected | Cost of taking it | Authority |
| --- | --- | --- | --- | --- |
| M1 | Generate a fresh planner result in every downstream fixture. | It keeps the work this plan removes. | Repeated source parsing, history reads, native writes and setup on each case. | Plan scope. |
| M2 | Share one writable repository or result directory between tests. | It makes outcomes depend on order and concurrent writes. | Cross-test contamination and false passes; each test needs an isolated writable surface. | Existing isolation and atomic-work principles. |
| M3 | Raise timeouts, add retries or skip the remaining slow cases. | None removes repeated work or proves the retained rule. | Delayed failures or missing coverage; inspect the actual remaining case cost instead. | Plan scope and existing gates. |

## See also

- [Author a plan](../docs/how-to/author-a-plan.md)
- [Execute a plan](../docs/how-to/execute-a-plan.md)
- [Run the gates](../docs/how-to/run-the-gates.md#independent-typescript-packages-and-services)
- [Operator API boundaries](../docs/architecture/sources/feed-operator-api.md)
- [Engineering contract](../CLAUDE.md#13-test-coverage-policy)
