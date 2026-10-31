# Feed ingest incident evidence

**Last Updated**: 2026-10-31
**Level**: 5 for robots permission behavior; 2 for investigation fixes within existing evidence shapes.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one maintainer carries both sequential phases; keep parallel N = 1 because both phases share the evidence review and living documentation; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor ESCALATE triggers in section 0.

Table A - operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Attempt safe feed and article targets despite robots-check denials or failures, then resolve historical feed-ingest evidence gaps without inventing causes. |
| A2 | Hard scope - in | Apply the robots behavior in phase 1; inspect saved run `41101711878` and current code for feed parsing, empty extraction, configured media exclusions and target HTTP failures; fix only a demonstrated defect within existing policy and contracts. |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Preserve robots results as evidence, attempt safe targets, then trace each historical outcome through its retained request, parse, filter and health records. |
| A6 | Execution | One maintainer carries the plan; phases run in order and each phase with real changes gets its own pull request. |

Table B - excluded work

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Raising response-size limits or reading beyond the existing cutoff | Some responses remain incomplete; bounded downloads remain predictable. | Separate policy decision with measured response-size and resource-cost evidence. |
| B2 | Blanket URL-substring media filtering, new target retries, or endpoint changes | Some false exclusions or recoverable failures may remain. | Source evidence and a separately settled policy change. |
| B3 | New persisted fields, diagnostic vocabularies or migrations | Missing historical detail remains unavailable. | A separately approved contract and read-side migration. |
| B4 | Reconstructing absent historical bodies, URLs or parser exceptions | Exact causes for old outcomes may remain unknown. | Exact bounded evidence for the original request. |

Table C - escalation triggers

| Id | Trigger | Required action |
| --- | --- | --- |
| C1 | A fix requires a new persisted shape, diagnostic vocabulary or migration. | Stop before implementation and surface the contract change. |
| C2 | An exact historical body, parser cause or request target is absent. | Record the cause as unknown; do not infer it from status, URL wording or current policy. |
| C3 | A fix changes target retry behavior, response limits, media policy or source membership. | Stop before implementation and surface the policy change. |
| C4 | A test needs a live source request. | Replace it with a recorded response or bounded generated input. |

## 1. Status Reckoner

Table D - phase status

| Id | Phase | Depends-on | Status | Pull request |
| --- | --- | --- | --- | --- |
| D1 | Attempt safe targets despite robots results | - | IN-FLIGHT | - |
| D2 | Resolve historical feed-ingest evidence gaps | D1 | PENDING | - |

## 2. Attempt safe targets despite robots results

### Phase 1 - Attempt safe targets despite robots results

- **Scope:** Safe eligible feed targets and article targets in `observe` proceed despite denied or unknown robots results, including safe redirect hops. Explicit article `enforce` remains unchanged; preserve robots evidence and all other request safeguards.
- **Files touched:**
  - `TODO/20261031-feed-ingest-evidence-plan.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/architecture/sources/feed-harvesting.md`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-robots-policy.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/robots-entry-points.test.ts`
- **Acceptance gates:**
  - Local: inspect `npm run test:changed -- --list` from `frontend/`; run relevant planner and common-contract checks and focused tests.
  - CI: planner service checks and tests on the exact merge candidate.
- **Oracle:** Recorded denied and failed robots results still dispatch safe targets for eligible feeds and observed articles while retaining the robots result; actual target refusals remain failures, replays do not dispatch, and resting, retired or unsafe targets do not dispatch.

**Decisions**

Table E - target request behavior

| Id | Decision | Authority |
| --- | --- | --- |
| E1 | Denied or unknown robots results do not veto safe target requests; retain the result without recording it as allowed. | Settled feed-ingest behavior |
| E2 | Articles retain the configured `observe` and opt-in `enforce` modes; feeds observe because they have no separate enforcement setting. | Existing configuration and policy boundary |
| E3 | Apply the behavior to bulk harvesting, standalone fetch APIs and `/plan`, including safe redirects. Keep address checks, DNS pinning, redirect safety, retries, timeouts, byte limits, cancellation and extraction admission unchanged. | Existing transport boundary |

**Rejected alternatives**

Table F - robots alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | Block every target when robots denies access. | Eligible targets remain unattempted when the checker is wrong. | A separate policy decision and reduced target coverage. | Settled feed-ingest behavior |
| F2 | Remove robots checks or rewrite denied results as allowed. | The permission and retrieval evidence would be lost or falsified. | Loss of evidence needed to distinguish checker results from target responses. | Evidence contract |

## 3. Resolve historical feed-ingest evidence gaps

### Phase 2 - Resolve historical feed-ingest evidence gaps

- **Scope:** Trace the malformed-feed result, eleven empty article extractions and feed/article HTTP failures from saved run `41101711878`; fix only a demonstrated defect within current policy and contracts.

**Investigation checklist:**

Table G - required findings

| Id | Item | Required finding |
| --- | --- | --- |
| G1 | Feed response with HTTP 202 | Determine whether the exact body, response type and parser evidence survive; otherwise report the parser cause as unknown. |
| G2 | Eleven empty article outcomes | Compare retained article offers, configured host/path rules and metadata filters; distinguish preflight exclusion from completed target fetch and extraction. |
| G3 | Article and feed HTTP 403/404 | Separate safe requested and attempted targets, robots evidence and target status; status alone does not establish a paywall, endpoint defect or publisher-wide cause. |
| G4 | Earlier fixes | Verify the existing scoped media rules, quality attribution and safe-URL diagnostics; do not duplicate them. |

- **Inspection targets; change only for a proven defect:**
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `services/feed-ingest-plan/src/harvest-feeds/parse-feed.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-parser-worker.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-parser-pool.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/media-filter.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/prepare-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-diagnostics.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-source-outcome.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-http.test.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `services/feed-ingest-plan/test/saved-reliability.test.ts`
  - `tests/fixtures/feed-ingest-plan/article-terminal-failures.json`
- **Acceptance gates:**
  - Local: `bun run --cwd services/feed-ingest-plan check` and focused tests for any code change.
  - Local: `git diff --check`; confirm changed files contain no temporary debug logging.
  - CI: planner service checks and tests on the exact merge candidate if files change.
  - Report: derive B5-B7 counts from retained records; cite what each record proves and what is unavailable.
- **Oracle:** Each retained outcome agrees with its typed target, response or parse result; a missing request target, body or parser cause remains explicitly unknown.

**Decisions**

Table H - evidence handling

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | HTTP status is an observed response, not proof of the underlying cause. | Existing diagnostics policy |
| H2 | Check configured media evidence before diagnosing an empty extraction; do not add blanket `video` matching. | Existing media policy |
| H3 | Keep parser and transport causes within the existing safe diagnostic contract; do not persist exception text or fetched text. | Existing trust boundary |
| H4 | Keep the robots behavior and response limits established in phase 1. | Phase dependency |

**Rejected alternatives**

Table I - evidence alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Infer that every empty result is a media exclusion or extractor defect. | The saved result cannot identify an absent offer or response body. | Exact retained offer and response evidence for each outcome. | Evidence contract |
| I2 | Retry or replace an endpoint after a 403/404 without source evidence. | Status alone does not establish the failure cause or intended address. | A verified endpoint record and bounded recovery evidence. | Existing fetch policy |
| I3 | Persist parser exception text to reveal malformed-feed causes. | Exception text can contain fetched input. | A safe finite cause vocabulary and a contract migration. | Existing trust boundary |

## 4. Phase 1 execution record

Table J - recorded inputs and results

| Id | Input or check | Result |
| --- | --- | --- |
| J1 | Recorded robots denial, HTTP failure and timeout followed by safe feed targets and redirects. | Bulk, standalone and redirect tests dispatched safe target requests and retained the first robots result. |
| J2 | Real loopback `/plan` with robots denial and feed target HTTP 200 or 403. | The saved row retained permission, target status and both request counts; the successful feed check remained valid and the target 403 remained a failure. |
| J3 | Five focused planner test files. | 31 tests passed; the set covered article policy, replay, cancellation, unsafe targets, request logging, failure retention and feed lifecycle. |
| J4 | Planner and shared-contract type checks; shared-contract tests and schema binding. | All passed. |
| J5 | `npm run test:changed -- --list` from `frontend/`; `git diff --check`; changed-path scan for temporary debug logging. | The selector listed shared/full coverage; whitespace checks passed; no debug markers were found. Full CI remains pending on the pull request candidate. |
