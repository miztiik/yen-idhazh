# Feed ingest incident evidence

**Last Updated**: 2026-10-31
**Level**: 2 for fixes within existing behavior and diagnostic shapes. Any persisted-shape or fetch-policy change is Level 5 and stops for maintainer approval.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 because all topics share the evidence review and living documentation; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The saved feed-ingest run contains malformed-feed, empty-extraction and HTTP refusal outcomes whose available evidence does not establish their specific causes; investigate each against the current code and repair only defects proven by bounded evidence. |
| A2 | Hard scope - in | - Inspect the named run evidence and current `origin/main` code for malformed feed parsing, empty article extraction and feed/article HTTP 403 or 404 outcomes.<br>- Separate configured media exclusions from article extraction failures using recorded offers, URLs, response facts and current rules.<br>- Make only fixes that restore existing intended behavior or improve diagnostics within existing contracts; add bounded offline tests and update the owning source documentation.<br>- Keep the work on these remaining investigations; reopen earlier fixes only if this evidence proves a regression. |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Trace each saved outcome through its request, parser or filter, typed result and saved evidence; fix only a reproduced code defect without changing policy or persisted shapes (Fowler for contracts and process safety; Editor rules any source-selection decision). |
| A6 | Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 because the investigations share evidence and documentation. |

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Raising the response-size limit or reading beyond the existing cutoff | Large responses remain incomplete, while the current reader avoids unbounded downloads | A separate policy decision supported by measured response-size and resource-cost evidence |
| B2 | Ignoring an explicit robots denial, adding blanket URL-substring video filtering, or retrying HTTP refusals under a new policy | A prohibited request may be sent, ordinary stories may be excluded, or a refusal may be repeated without evidence it can recover | A user-approved policy change with bounded tests and a named safety reason |
| B3 | Adding or changing persisted diagnostic fields or schema versions | Some causes may remain unavailable until the existing fields can express them | Maintainer approval of the new shape and its reader/version migration under CLAUDE.md section 11 |
| B4 | Changing configured source endpoints or source membership based only on HTTP status | A feed may remain unavailable or keep its current address until authoritative source evidence exists | Evidence in the saved run or existing source records that establishes the intended endpoint; consult Editor if source selection changes |
| B5 | Reconstructing missing historical response bodies or parser causes | The exact cause of an old malformed response cannot be established | A bounded, recorded response body for that exact request, supplied as a fixture without external network access |

Table C - when to stop

| # | Trigger | Required action |
| --- | --- | --- |
| C1 | A fix needs a new persisted field, a new diagnostic vocabulary outside the existing contract, or a migration | Stop before implementation and request maintainer approval; do not alter the contract in this row |
| C2 | The exact historical response or request target is absent | Record the cause as unknown; do not infer it from status, URL wording or current policy |
| C3 | A proposed fix changes robots enforcement, retry behavior, response limits, media policy or source membership | Stop and surface the policy choice with evidence and cost |
| C4 | A test would need a live source request | Replace it with a recorded response or a bounded generated fixture; no test may use the network |

## 1. Status Reckoner

Table D - rows

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Resolve remaining feed-ingest evidence gaps | - | A | PENDING | - | - | - |

## 2. Resolve remaining feed-ingest evidence gaps

### Row #1 - Resolve remaining feed-ingest evidence gaps
- **Scope:** Trace the malformed-feed cases, the eleven empty article extractions and the HTTP 403/404 outcomes from saved run `41101711878` through current request, parsing, media filtering and health attribution; fix only a demonstrated defect within current policy and contracts.
- **Investigation checklist:**

  Table E - unresolved evidence

  | # | Item | Required finding |
  | --- | --- | --- |
  | E1 | B5 - malformed feed | Inspect the recorded HTTP 202 and parser outcome. Establish whether the exact response body and parser evidence survive. If not, report the cause as unknown; do not infer malformed content or expose parser exception text. |
  | E2 | B6 - empty extraction | Trace the eleven empty article outcomes: compare the ten short-video routes with the configured host/path and media metadata filters, then trace the remaining outcome separately through fetch and extraction. State whether each was excluded before article fetch or reached extraction; do not treat empty text alone as proof of extractor failure. |
  | E3 | B7 - HTTP refusals | Trace the 20 article HTTP 403 outcomes, 46 feed HTTP 403 outcomes and two feed HTTP 404 outcomes to their safe requested/final URLs, robots evidence, configured endpoint and actual response. Report the observed status separately from its unproven cause; do not add retries or claim a paywall from status alone. |
  | E4 | Earlier fixes | Treat the prior quality-attribution, safe-URL diagnostics and robots behavior fixes as closed unless this evidence demonstrates a regression. |
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

  Table F - decisions

  | # | Decision | Authority |
  | --- | --- | --- |
  | F1 | Treat HTTP status as an observed response, not proof of paywall, endpoint defect or publisher-wide cause | Existing diagnostics policy; maintainer |
  | F2 | Check configured media evidence before diagnosing an empty extraction; do not add a blanket `video` substring rule | Existing media policy; Editor for any source-selection change |
  | F3 | Keep parser and transport causes in the existing safe diagnostic contract; never persist exception messages or fetched text | Fowler; CLAUDE.md Guardrails #3 and #11 |
  | F4 | Preserve explicit robots denial and configured response limits | Maintainer policy |

- **Rejected alternatives**

  Table G - rejected alternatives

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | G1 | Infer that every empty result is a short-video exclusion or extraction defect | The empty result alone does not distinguish an excluded offer, an unavailable response body or an extractor outcome | A source-by-source false-classification check against retained offers and responses | Editor |
  | G2 | Retry or replace an endpoint after a 403/404 without source evidence | Status alone does not establish why a request failed or whether another address is intended | A verified endpoint record and a bounded recovery test; any policy change needs user approval | Maintainer |
  | G3 | Persist the parser exception message to reveal malformed-feed causes | Exception text can contain fetched input and would cross the trust boundary | A safe, finite parser-cause vocabulary and its schema migration | Fowler; maintainer approval required |
