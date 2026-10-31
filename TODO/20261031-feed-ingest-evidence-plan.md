# Feed ingest incident evidence

**Last Updated**: 2026-10-31
**Level**: 5 for the robots policy correction approved by the user on 2026-10-31 UTC; 2 for investigation fixes within existing diagnostic shapes. Other persisted-shape or fetch-policy changes stop for maintainer approval.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 because all topics share the evidence review and living documentation; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Correct the robots-check blocking policy to the user's intent, then investigate saved feed-ingest failures without inventing their causes. |
| A2 | Hard scope - in | - Implement the approved robots policy in row #1.<br>- Inspect the named run evidence and current `origin/main` code for malformed feed parsing, empty article extraction and feed/article HTTP 403 or 404 outcomes.<br>- Separate configured media exclusions from article extraction failures using recorded offers, URLs, response facts and current rules.<br>- Add bounded offline tests and update the owning source documentation without changing persisted shapes. |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Apply the user-approved robots correction, then trace each saved outcome through its request, parser or filter, typed result and saved evidence; investigation fixes preserve other policy and persisted shapes (Fowler for contracts and process safety; Editor rules any source-selection decision). |
| A6 | Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 because the investigations share evidence and documentation. |

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Raising the response-size limit or reading beyond the existing cutoff | Large responses remain incomplete, while the current reader avoids unbounded downloads | A separate policy decision supported by measured response-size and resource-cost evidence |
| B2 | Adding blanket URL-substring video filtering or retrying actual target HTTP refusals under a new policy | Ordinary stories may be excluded or a refusal may be repeated without evidence it can recover | A user-approved policy change with bounded tests and a named safety reason |
| B3 | Adding or changing persisted diagnostic fields or schema versions | Some causes may remain unavailable until the existing fields can express them | Maintainer approval of the new shape and its reader/version migration under CLAUDE.md section 11 |
| B4 | Changing configured source endpoints or source membership based only on HTTP status | A feed may remain unavailable or keep its current address until authoritative source evidence exists | Evidence in the saved run or existing source records that establishes the intended endpoint; consult Editor if source selection changes |
| B5 | Reconstructing missing historical response bodies or parser causes | The exact cause of an old malformed response cannot be established | A bounded, recorded response body for that exact request, supplied as a fixture without external network access |

Table C - when to stop

| # | Trigger | Required action |
| --- | --- | --- |
| C1 | A fix needs a new persisted field, a new diagnostic vocabulary outside the existing contract, or a migration | Stop before implementation and request maintainer approval; do not alter the contract in this row |
| C2 | The exact historical response or request target is absent | Record the cause as unknown; do not infer it from status, URL wording or current policy |
| C3 | A proposed fix changes fetch policy beyond the approved correction in row #1, retry behavior, response limits, media policy or source membership | Stop and surface the policy choice with evidence and cost |
| C4 | A test would need a live source request | Replace it with a recorded response or a bounded generated fixture; no test may use the network |

## 1. Status Reckoner

Table D - rows

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Attempt safe targets despite robots checker results | - | A | PENDING | - | - | - |
| 2 | Resolve remaining feed-ingest evidence gaps | 1 | B | PENDING | - | - | - |

## 2. Attempt safe targets despite robots checker results

### Row #1 - Attempt safe targets despite robots checker results
- **Scope:** Make the planner attempt safe feed and article targets when its robots checker fails or reports denial, including redirect hops, while preserving the checker result as evidence.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/test/article-robots-policy.test.ts`
  - `services/feed-ingest-plan/test/robots-entry-points.test.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
- **Acceptance gates:**
  - Local: run the shared test selector from `frontend/` with `npm run test:changed -- --list`, then use its applicable checks.
  - Local: run the four named service test files and the service/common-contract type checks from the planner gate guide.
  - CI: full required checks on the merge candidate.
- **Oracle:** Recorded failed and denied robots results still lead to target dispatch under the planner's committed settings for both feeds and articles; the same results remain in diagnostics and unsafe targets are never dispatched. This proves dispatch policy, not whether a historical robots denial was a false positive or whether a source will accept the request.
- **Decisions**

  Table E - approved robots correction

  | # | Decision | Authority |
  | --- | --- | --- |
  | E1 | Robots checker failures and reported denials must not veto safe target requests in the planner's committed configuration; retain the check result rather than rewriting it as allowed | User-directed correction, 2026-10-31 UTC |
  | E2 | Use the existing article `observe` policy to record allowed, denied and unknown results without blocking; keep opt-in `enforce` behavior. Feeds observe results without blocking, as they have no separate enforcement setting | Fowler, implementing E1 without a new knob or persisted field |
  | E3 | Apply the same behavior through standalone fetch APIs and `/plan`, including safe redirects. Keep address validation, DNS pinning, actual target HTTP failures, byte limits, cancellation and extraction admission unchanged | Fowler; user approval applies only to robots-based blocking |
  | E4 | Replace the earlier local documentation and tests that said a reported denial must always block; that wording misread the user's intent. Inspect the existing uncommitted robots patch before integrating it; it is not a merged fix | User-directed correction, 2026-10-31 UTC |

- **Rejected alternatives**

  Table F - robots alternatives

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | F1 | Always block when the checker reports denial | Does not meet the user's instruction to try the target despite reported false positives | Eligible targets remain unattempted; taking this option needs a new user decision | User-directed correction, 2026-10-31 UTC |
  | F2 | Remove robots checking or record a denied result as allowed | Discards the evidence needed to investigate false positives | Loss of permission and retrieval evidence, plus changed diagnostic meaning | Fowler |

## 3. Resolve remaining feed-ingest evidence gaps

### Row #2 - Resolve remaining feed-ingest evidence gaps
- **Scope:** Trace the malformed-feed cases, the eleven empty article extractions and the HTTP 403/404 outcomes from saved run `41101711878` through current request, parsing, media filtering and health attribution; fix only a demonstrated defect within current policy and contracts.
- **Investigation checklist:**

  Table G - unresolved evidence

  | # | Item | Required finding |
  | --- | --- | --- |
  | G1 | B5 - malformed feed | Inspect the recorded HTTP 202 and parser outcome. Establish whether the exact response body and parser evidence survive. If not, report the cause as unknown; do not infer malformed content or expose parser exception text. |
  | G2 | B6 - empty extraction | Trace the eleven empty article outcomes: compare the ten short-video routes with the configured host/path and media metadata filters, then trace the remaining outcome separately through fetch and extraction. State whether each was excluded before article fetch or reached extraction; do not treat empty text alone as proof of extractor failure. |
  | G3 | B7 - HTTP refusals | Trace the 20 article HTTP 403 outcomes, 46 feed HTTP 403 outcomes and two feed HTTP 404 outcomes to their safe requested/final URLs, robots evidence, configured endpoint and actual response. Report the observed status separately from its unproven cause; do not add retries or claim a paywall from status alone. |
  | G4 | Earlier fixes | Re-check prior merged quality-attribution and safe-URL diagnostics fixes against current remote code; do not duplicate them unless a regression is shown. Robots behavior is assigned to row #1. |
- **Files touched:**
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
  - `tests/fixtures/feed-ingest-plan/article-terminal-failures.json`
- **Acceptance gates:**
  - Local: `bun run --cwd services/feed-ingest-plan check`.
  - Local: `bun run --cwd services/feed-ingest-plan test`.
  - Local: `git diff --check`; confirm there are no `[DEBUG]` markers in changed files.
  - CI: planner service checks and tests on the exact merge candidate.
  - Report: give each B5-B7 item a status and cite its retained evidence; distinguish a code fix from a historical evidence gap.
- **Oracle:** For every historical outcome with retained evidence, the operation, safe request target, response or parse result, and typed saved cause agree; a missing response or target remains explicitly unknown. This cannot establish the cause of an incident whose original response body or request evidence was not saved.
- **Decisions**

  Table H - decisions

  | # | Decision | Authority |
  | --- | --- | --- |
  | H1 | Treat HTTP status as an observed response, not proof of paywall, endpoint defect or publisher-wide cause | Existing diagnostics policy; maintainer |
  | H2 | Check configured media evidence before diagnosing an empty extraction; do not add a blanket `video` substring rule | Existing media policy; Editor for any source-selection change |
  | H3 | Keep parser and transport causes in the existing safe diagnostic contract; never persist exception messages or fetched text | Fowler; CLAUDE.md Guardrails #3 and #11 |
  | H4 | Preserve the robots policy established by row #1 and configured response limits | User-directed correction, 2026-10-31 UTC; existing response-limit policy |

- **Rejected alternatives**

  Table I - rejected alternatives

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | I1 | Infer that every empty result is a short-video exclusion or extraction defect | The empty result alone does not distinguish an excluded offer, an unavailable response body or an extractor outcome | A source-by-source false-classification check against retained offers and responses | Editor |
  | I2 | Retry or replace an endpoint after a 403/404 without source evidence | Status alone does not establish why a request failed or whether another address is intended | A verified endpoint record and a bounded recovery test; any policy change needs user approval | Maintainer |
  | I3 | Persist the parser exception message to reveal malformed-feed causes | Exception text can contain fetched input and would cross the trust boundary | A safe, finite parser-cause vocabulary and its schema migration | Fowler; maintainer approval required |
