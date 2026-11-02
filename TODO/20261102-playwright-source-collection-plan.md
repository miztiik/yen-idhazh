# Collect sources with Playwright

**Last Updated**: 2026-11-02
**Level**: 5 - source browser execution, request policy and diagnostic contracts.

## 0 - Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Recover blocked public feeds and usable public article text through the existing planner, with particular attention to Substack access. |
| A2 | Hard scope - in | Replace Impit with Playwright for robots, feeds and articles; update the dependent feed probe; retain all configured sources and existing eligibility rules; reuse parsing, sanitization, selection, partitioning and output delivery. |
| A3 | Hard scope - out | Table B prices the exclusions. |
| A4 | Branch isolation | Implement on `playwright-source-collection`. Keep code off `main` until row 3 is complete. Existing final delivery may append completed ledger and host metadata to `main`; this is not a code merge. Never operate in the main checkout. |
| A5 | Run controls | Preserve the existing manual inputs and article-limit meaning. `article_limit` limits selected output after collection; it is not a download count or a time limit. Do not add article caps, restrict the planner to Substack or shorten runs before observing a duration problem. |
| A6 | Chosen strategy | One real Chromium download implementation, shared by existing consumers, with temporary browser sessions and checked browser-generated requests. Architecture consultation informs Table D; Tables D and E declare the implementation contract. |
| A7 | ESCALATE triggers | 1. Pause before implementation until this Level-5 plan is authorized for execution. 2. Stop before editing `CLAUDE.md` or `AGENTS.md`. 3. Surface any browser request path that cannot be checked before dispatch, unavailable sandboxing or loss of original response failure evidence. 4. Surface a proposed proxy, solver, human step, persistent browser profile, new source filter, download cap or changed robots policy. 5. Surface a measured duration problem with its cause and proposed remedy; do not silently reduce coverage. 6. If the job cannot finish within the platform's six-hour job limit, name a viable design and its trade-off. 7. Remaining targeted Substack blocks or unexplained non-Substack regressions prevent claiming replacement success. |
| A8 | Execution | Execute per `docs/how-to/execute-a-plan.md`: one maintainer coordinates nested sessions, parallel N = 1 because all rows share the experimental source boundary; advance through the dependencies without partial code merges; consult only for a material unresolved design choice; merge only after row 3 establishes readiness. |
| A9 | PR boundary | One coherent replacement PR contains rows 1 and 2, with row 3 supplying real-run evidence before merge. Separate commits may distinguish source behavior from workflow integration; neither increment lands on `main` alone. |
| A10 | Documentation | Record technical requirements and reasons on their owning pages during implementation. This plan alone does not change the running system. |

Table B - Exclusions and their cost

| Id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Impit fallback, hybrid routing and per-site client selection | Every source pays browser overhead, including sources that need no JavaScript. | Observed browser cost that warrants a separate routing decision. |
| B2 | Human challenge-solving, account login, imported cookies, proxies and external solving services | Some public endpoints may remain blocked; subscriber-only content is not recovered. | A separate capability and trust-boundary decision, not an automatic recovery path. |
| B3 | Preserving the native decoded-stream cutoff | Chromium can download or allocate more than the admission limit before refusal. | Evidence that completed-body admission is insufficient, followed by a priced browser-loading design. |
| B4 | Production Python transport, source inventory edits, editorial changes and site UI work | This replacement does not change the Python pipeline or repair unrelated source/content problems. | A separately identified dependency on the requested browser capability. |
| B5 | New benchmarking infrastructure and mandatory paired live runs | Results show observed runtime, not an isolated causal speed comparison. | A measured cost question whose answer would change the next implementation. |
| B6 | Backward-compatible transport execution or configuration conversion | Old fingerprint-shaped configuration fails validation rather than selecting a legacy client. | A separately identified live consumer that requires conversion. Existing readable ledger data is not deliberately broken. |

## 1 - Status reckoner

Table C - Work sequence

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Replace source downloads with owned browser sessions | - | A | PENDING | probable-fishstick | - | - |
| C2 | 2 | Exercise the branch through the existing manual workflow | 1 | B | PENDING | probable-fishstick | - | - |
| C3 | 3 | Observe recovery and establish main-merge readiness | 1, 2 | C | PENDING | probable-fishstick | - | - |

## 2 - Browser and evidence contracts

Table D - Browser behavior and configuration

| Id | Subject | Required behavior |
| --- | --- | --- |
| D1 | Dependency and runtime | Add exact `playwright` version `1.62.1`, matching the existing frontend lock, to the service only. Its beneficiary is actual browser JavaScript, navigation and cookie handling. Its costs are browser installation, native runtime dependencies, startup time and browser memory; measure installation/run time rather than inventing byte or speed figures. Use its matching Chromium, not an unrelated installed browser. |
| D2 | Ownership | The listener owns one lazy browser process. Each execution's permitted fetcher owns one non-persistent context; each logical attempt owns a page. Requests in that execution reuse site-issued cookies. Independent executions do not share cookies. Direct harvesting/probing owns its runtime unless one is supplied; the probe CLI shares its owned browser across its targets. Add awaited transport disposal and close pages, contexts and owned processes on success, failure, cancellation, eviction, collection release and shutdown. WeakMap eviction is not cleanup. |
| D3 | Isolation | Keep Chromium sandboxing enabled, remove repository credentials from the browser child environment and expose no host bindings. Do not import a browser profile or credentials, persist storage state, enable downloads or attach to a personal browser. Block service workers, WebSockets and unsolicited popup navigation. Site-issued cookies remain temporary and are neither logged nor committed. |
| D4 | Request admission | Browser-owned HTTP(S) requests, including redirects, scripts, XHR/fetch, frames, worker requests and preflights, must pass the existing URL/name/literal-address checks before dispatch. Apply existing robots policy, pacing and accounting. Install the gate before a page or child target can send traffic. Use Playwright with the narrow Chromium DevTools Protocol interception needed for redirect/child-target coverage; do not implement a general protocol framework. Refuse an ungated path rather than observing it after dispatch. |
| D5 | Robots and pacing | Reuse the origin-keyed robots cache and existing article enforce-or-observe setting; safe feed requests retain their current observe behavior. Robots work and its browser resources have an explicit mode that does not recursively request robots permission. Acquire pacing for each HTTP request and release it at that request's settlement, not after rendering its parent page. A parent must not hold the slot needed by its robots check or resources. Keep existing cooldown/jitter and retry/backoff settings. |
| D6 | Navigation identity | Preserve initial article cleanup, canonical hashing and stored article identity. Do not apply that identity cleanup to browser-generated resource URLs or follow-up navigation: their functional query parameters must survive. Validate these destinations before dispatch and redact diagnostic URLs with the existing helper. Keep original status/header evidence for every navigation; do not manufacture a successful response. |
| D7 | Feed and robots bodies | Return the completed final network body, not the browser's XML viewer, `innerText` or a rendered HTML wrapper. If a browser would treat XML/text as a download, use a narrowly scoped response-header continuation to permit inline reading while retaining original headers as evidence. Do not replace response bodies. An unresolved HTML challenge is not XML or an empty permissive robots file. |
| D8 | Article bodies | Let site JavaScript run, then pass the rendered HTML through the existing inert worker parser and sanitizer. Use existing content-root settings as readiness hints, not new editorial gates. Do not wait for global network idleness or add a fixed sleep. Return actual short content for existing extraction checks; never substitute a teaser, description or invented article. |
| D9 | Challenge outcome | Allow automatic navigation and cookie changes within the document deadline. Detect an explicit challenge response header or configured interstitial selector; do not mistake every 403 for a challenge. An unresolved challenge is a typed failure even when its actual status is 200. A completed page is not proof of readable content: normal feed parsing and article extraction must also succeed. Never forge cookies or claim that browser automation guarantees access. |
| D10 | Minimal configuration | In the existing harvest config, replace fingerprint/recovery settings in `request_headers` with the existing allowlisted header map, default `{}`. Add `browser.headless`, default `true`; `browser.document_timeout_ms`, default `30000`; and `browser.challenge_selectors`, initially `#challenge-form`, `#challenge-running` and `#cf-challenge-running`. These are configurable readiness signals, not a bypass guarantee. The document timeout is an initial estimate of thirty seconds, not a measured target. Keep the existing per-request timeout, concurrency, parser deadline and pacing values initially. The browser deadline starts at first target dispatch and bounds subsequent resource waits and navigation. Browser startup and robots work retain explicit cancellation ownership. |
| D11 | Size admission | Keep the existing `extract.max_body_bytes` value. After a response completes, refuse an oversized decoded body; before parsing, separately refuse oversized UTF-8 parser input, including a rendered DOM. Do not claim early transfer termination or a browser-memory bound. A response read, decoding or original completion error remains a failure even when the available prefix is below the limit. |
| D12 | Unchanged consumers | The same implementation serves `/plan`, document fetch/parse APIs, direct harvesting and the standalone probe. Loopback calls between planner stages and the existing Git delivery APIs retain their ordinary HTTP behavior; they are not website downloads and do not become browser navigation. Keep production enablement defaults unchanged. |

Table E - Contract and diagnostic changes

| Id | Shape | Change and read behavior |
| --- | --- | --- |
| E1 | Configuration | Set the authored config/schema version to `2026-11-02` with a technical changelog. Reject the old nested fingerprint/recovery object explicitly. Do not add a transport selector, source list, article cap or compatibility converter. |
| E2 | Response evidence | Extend `request_profile` with `chromium`; new writes use it. Existing `firefox` and `chrome` values remain readable evidence labels, not client choices. Keep `decoded_bytes` about the HTTP body, never the rendered DOM. Use null when the browser cannot establish a measurement. Reuse the existing safe header projection and exclude cookies, tokens, credentials and signed URLs. |
| E3 | Body-limit evidence | Add `limit_stage`: `decoded-stream`, `completed-response` or `parser-input`. The first identifies existing evidence; missing historical values retain that meaning. Browser writes use the applicable completed-response or parser-input value and measured bytes. Keep the configured limit and observed-byte fields; remove claims that every refusal stopped a stream. |
| E4 | Challenge failure | Add `challenge-unresolved` to the native fetch-failure vocabulary and propagate it through diagnostics, reports, probe results and refusal handling. Replace the duplicate vocabulary in the stage schema with the shared declaration. Preserve the observed HTTP status. Existing broad item-health categories use `unknown` with this exact detail; do not invent a Python category or label a challenge as an empty article. |
| E5 | Request attempts and work facts | Add nullable `request_role`: `document` or `resource`, with null for validation-only or unavailable historical evidence. Preserve unique ordered sequences and matching attempt observations. Count actual browser dispatches once under their initiating robots/feed/article work, including redirect hops and background requests. Pre-dispatch refusals and cache reuse count zero. Interrupted or unobservable work reports partial/unknown coverage, not invented complete totals. |
| E6 | Failure attribution | Resource failures remain visible but cannot alone become an article/feed document refusal or a source-reliability penalty. Terminal document status and final attempted document URL cannot be overwritten by an unrelated asset. Unsafe destinations remain explicit policy refusals. Ordinary optional-resource failure may degrade a page without discarding usable article text. |
| E7 | Versioning boundary | Stamp changed operation, event, diagnostics and probe/stage wrappers where their embedded meaning changes, with newest-first technical changelogs. Keep existing TypeScript authority and existing ledger read rules. Do not change the five planner Parquet layouts or their stamps merely to describe browser internals, and do not reopen already-unsupported captures. No Python planner model or frontend contract copy is introduced. |

## 3 - Row #1 - Replace source downloads with owned browser sessions

- **Scope:** Implement Tables D and E in the existing source-download boundary and its consumers, removing the native fingerprint client rather than adding a second execution mode.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/version.ts`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/http-response-evidence.schema.ts`
  - `packages/common-contracts/src/schemas/harvest-diagnostics.schema.ts`
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/document-work.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/src/schemas/feed-probe.schema.ts`
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `packages/common-contracts/test/http-response-evidence.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/common-contracts/test/article-identity-compatibility.test.ts`
  - `packages/common-contracts/test/browser-transport-contract.test.ts` (new)
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `services/feed-ingest-plan/src/harvest-feeds/impit-transport.ts` (delete)
  - `services/feed-ingest-plan/src/harvest-feeds/playwright-transport.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/browser-runtime.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/browser-request-gate.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/browser-document-response.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/source-response-evidence.ts` (new, extracted from the existing projection)
  - `services/feed-ingest-plan/src/harvest-feeds/transport.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/classify-transport-failure.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-diagnostics.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/collection-operation.ts`
  - `services/feed-ingest-plan/src/api/routes/collection.route.ts`
  - `services/feed-ingest-plan/src/api/selection-operation.ts`
  - `services/feed-ingest-plan/src/api/partition-operation.ts`
  - `services/feed-ingest-plan/src/api/persistence-operation.ts`
  - `services/feed-ingest-plan/src/api/record-standalone-run.ts`
  - `services/feed-ingest-plan/src/attribute-ingest-outcomes.ts`
  - `services/feed-ingest-plan/src/run-health.ts`
  - `packages/feed-probe/bun.lock`
  - `packages/feed-probe/src/feed-probe.ts`
  - `packages/feed-probe/src/cli.ts`
  - `packages/feed-probe/test/feed-probe.test.ts`
  - `packages/feed-probe/test/feed-probe-cli.test.ts`
  - `services/feed-ingest-plan/test/impit-transport.test.ts` (delete)
  - `services/feed-ingest-plan/test/playwright-transport.test.ts` (new)
  - `services/feed-ingest-plan/test/impit-loopback-source.cjs` (delete)
  - `services/feed-ingest-plan/test/browser-loopback-source.cjs` (new)
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/transport-failure.test.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-robots-policy.test.ts`
  - `services/feed-ingest-plan/test/robots-entry-points.test.ts`
  - `services/feed-ingest-plan/test/network-failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/request-pacing.test.ts`
  - `services/feed-ingest-plan/test/browser-lifecycle.test.ts` (new)
  - `services/feed-ingest-plan/test/browser-request-policy.test.ts` (new)
  - `tests/fixtures/feed-ingest-plan/harvest-header-recovery.json` (remove with its obsolete helper and dedicated recovery assertions)
  - `.github/workflows/source-transport-test.yml`
  - `backend/tests/workflows/test_source_transport_workflow.py` (update existing workflow assertions only)
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/trust-boundary.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261102-playwright-source-collection-plan.md`
- **Implementation order:** Declare E before new readers/writers; extract the shared response projection and request admission; add the real browser implementation; wire awaited disposal through existing state owners and callers; replace native-specific classification/tests/dependencies together. Retain the recorded-response boundary for ordinary offline suites. Do not add a second proof-of-concept path.
- **Acceptance gates:** Inspect `npm --prefix frontend run test:changed -- --list`. Run the declared `check` commands in common-contracts, the service and feed-probe. Run changed contract tests and the focused service/probe tests listed above in combined native selections. Keep the full application suite in merge-candidate CI. Add the service script `browser:install` with `playwright install --with-deps chromium`, using the locally locked CLI. Extend the existing Linux source-transport workflow to call it and run the real browser oracle; update its existing Python assertion without adding Python tooling or a local Python prerequisite.
- **Acceptance gates:** Real Chromium cases use bounded generated loopback documents and named recorded content, never external sites. Reuse the native fixture server's relevant completed, compressed, stalled and truncated responses. Add a scripted cookie-and-navigation case, rendered content, raw XML, download-like XML, unresolved challenges, policy-checked redirects/resources/frames/workers, exact dispatch accounting and owned cleanup. Keep any loopback admission seam internal to the fixture boundary, with no production unsafe-address switch.
- **Oracle:** The real planner fetch/parse chain, driven by Chromium and a local scripted source, acquires a site-issued cookie, follows checked navigation, parses actual XML and extracts sanitized rendered article text; the same path refuses unsafe follow-up requests before dispatch, retains real interrupted-response failures and disposes its browser resources. This proves browser integration and policy enforcement, not acceptance by a live publisher.
- **Decisions:**

Table F - Source implementation decisions

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | D and E replace obsolete native-client assumptions; do not force browser navigation into the old manual-response loop. Keep the existing permitted fetcher as the policy entry. | Architecture consultation; actual transport and robots-policy callers. |
| F2 | Use one browser implementation and one protocol-specific request gate. Extract only the existing policy/projection seams needed by that implementation. | A6 and D4; avoid a general transport framework. |
| F3 | Make state eviction and release await resource disposal, updating the named stage-registration callers rather than launching untracked cleanup promises. Preserve concurrent execution ownership. | D2; current state registry and listener cleanup. |
| F4 | Replace early-cutoff assertions with completed-response and parser-input admission assertions. Keep original completion/decoding-failure cases. | D11 and E3; Playwright returns complete response buffers. |
| F5 | Readable historical evidence labels and existing ledger readers do not constitute an Impit execution fallback. Keep them where they avoid unrelated data breakage. | E2 and E7. |
| F6 | Existing completed Impit plan references are historical context, not executable dependencies. Do not rewrite unrelated plan status to claim this browser work is done. | Documentation single-snapshot rule; this plan owns unfinished browser work. |

- **Rejected alternatives:**

Table G - Source alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Playwright HTTP request helpers or a separate raw HTTP fetch after obtaining cookies | They do not prove that the download uses the real browser network/session behavior. | Another client path, cookie transfer and independent fingerprint behavior to measure. | A2 and D1. |
| G2 | Fulfill intercepted responses with reconstructed successful bodies to retain streaming | A partial or failed original response can become a successful synthetic document. | A loading mechanism that preserves original decoded completion/error semantics, with dedicated proof. | D11; native response-failure oracle. |
| G3 | Give the page's full rendering lifetime one pacing slot | Its scripts or robots checks can wait for the slot held by their parent. | A redesigned scheduler and evidence showing no dependency deadlocks. | D5. |
| G4 | Treat an asset 403 or HTTP 200 challenge as a document outcome | It confuses background requests, real article access and source reliability. | Separate evidence sufficient to justify that attribution; ordinary HTTP status is insufficient. | E4-E6. |

## 4 - Row #2 - Exercise the branch through the existing manual workflow

- **Scope:** Adapt the existing manual planner workflow on the experimental branch, keeping its controls, supervised APIs, reports, uploads and final metadata delivery.
- **Files touched:**
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `docs/how-to/run-feed-ingest-plan-test.md`
  - `docs/reference/github-actions.md`
  - `TODO/20261102-playwright-source-collection-plan.md`
- **Acceptance gates:** Invoke row 1's `browser:install` script before collection, without an unpinned package download. Preserve the sparse checkout's real dependencies and supplied execution SHA through startup, output verification and finalization. Use the existing workflow test to check installation/order and unchanged input/output ownership; run it with affected finalization/supervisor tests. Full-suite CI remains authoritative.
- **Oracle:** The workflow definition installs the service's locked browser before invoking the unchanged real planner supervisor, preserves branch execution identity and routes only completed registered metadata through the existing finalizer. This proves runnable wiring and delivery ownership, not that any live Substack endpoint succeeds.
- **Decisions:**

Table H - Workflow decisions

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | Reuse the existing workflow filename with branch-specific content. Later dispatch uses `gh workflow run feed-ingest-plan-test.yml --ref playwright-source-collection`. Do not dispatch during plan authoring. | Existing default-branch workflow registration and manual-dispatch behavior. |
| H2 | Keep `contents: write` for final ledger delivery. Do not replace or retarget `safe_persist_data`, suppress its confirmation or add an artifact-only fake-success path. | A4; existing publisher and finalization contracts. |
| H3 | Keep the existing article-limit controls and full configured source population; do not introduce browser-mode, source-selection or diagnostic-run inputs. Keep the platform job timeout. | A2, A5 and B1. |
| H4 | On eventual merge, the same browser installation remains necessary for the new source implementation. No duplicate temporary pipeline or permanent second client needs removal. | Single implementation and workflow reuse. |

- **Rejected alternatives:**

Table I - Workflow alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | A new manually dispatched workflow that exists only on the experiment branch | Manual registration requires a workflow on the default branch. | A default-branch registration change or a separately maintained branch-push entry. | Existing manual workflow and platform dispatch requirement. |
| I2 | New collection caps or Substack-only planner inputs | They change selection/workload behavior before an actual duration problem is established. | Another contract and sampling policy, followed by validation on the full inventory. | A5. |
| I3 | Copy workflow orchestration, reports or Git delivery into browser-specific scripts | The existing implementation already owns those responsibilities. | Duplicate process, report and delivery behavior to keep in step. | A2; existing supervisor/finalizer boundaries. |

## 5 - Row #3 - Observe recovery and establish main-merge readiness

- **Scope:** Observe the real branch workflow, record what recovered and what remains blocked, then establish whether the single replacement PR is ready for main.
- **Files touched:**
  - `docs/reference/source-browser-evidence.md` (new, only when actual results exist)
  - `docs/how-to/run-feed-ingest-plan-test.md` (link to current evidence)
  - `TODO/20261102-playwright-source-collection-plan.md`
- **Acceptance gates:** No new application test is introduced by this evidence-only row. Verify unchanged focused test records from rows 1 and 2 and the full suite on the merge candidate. Resolve any implementation defect in its owning row and rerun checks selected for the actual fix; do not repeat an unchanged test record.
- **Named live observation:** After the branch is pushed and its offline checks pass, dispatch H1 with the existing controls. The run writes real metadata, so it is an observation with side effects, not a repeatable automated test gate. Verify its exact code SHA, effective config, run/attempt, host fingerprint, completed planner output, delivery receipt and uploaded selected article text.
- **Named live observation:** Use per-feed results to identify actual feed parsing and public article extraction for previously blocked Substack cases. A skipped/resting feed, a successful non-Substack article, a cookie appearing or HTTP 200 alone does not establish recovery. Do not reset shared lifecycle data to make a run look successful. Where resting state hides a required case, use the existing read-only feed-probe operation and its existing explicit target controls on the same candidate/runtime, or observe the next eligible planner run; label this additional evidence separately and retain the planner's full-inventory requirement.
- **Named live observation:** Record current elapsed time and browser installation cost with the actual runner/host and effective workload. Memory or transfer quantities that were not measured remain unavailable. List remaining challenge, paywall, network and extraction failures separately; distinguish pipeline regressions from existing source failures. Do not claim a causal speed comparison from different workload/host conditions.
- **Oracle:** A completed real candidate run yields parsed feeds and usable public article text for the targeted formerly blocked Substack cases while processing the configured inventory through the same browser implementation and producing valid selected output and confirmed metadata delivery. This is evidence for that candidate and run, not a guarantee of future publisher access.
- **Decisions:**

Table J - Merge and evidence decisions

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Offline tests certify software behavior; the named observation establishes whether the requested live capability exists. Green tests alone cannot substitute for Substack recovery. | Row 1 oracle and row 3 oracle answer different questions. |
| J2 | Keep the code branch unmerged while targeted public Substack access remains unproven or non-Substack regressions remain unexplained. Report the failing layer and priced next action; do not silently introduce a solver, fallback or source exclusion. | A4, A7 and B1-B2. |
| J3 | Merge the complete replacement only after its evidence and required CI support it; preserve existing production enablement defaults. Use normal non-history-rewriting Git operations and preserve concurrent immutable data additions. | A9; existing delivery and Git contracts. |
| J4 | Keep one current evidence reading under the reference page; link the actual run/artifacts and conditions. Do not copy article bodies, cookies or superseded readings into documentation. | Existing documentation and measurement rules. |

- **Rejected alternatives:**

Table K - Evidence alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Merge after a browser-only page demonstration | It leaves real planner extraction, policy, output and dependent consumers unproven. | A later integration pass and another candidate run to establish the requested capability. | A2 and row 3 oracle. |
| K2 | Require universal zero failures or invent a throughput threshold | Publisher availability varies, and no such numerical threshold defines this experiment. | A separately agreed acceptance target and comparable measurements sufficient to judge it. | Existing per-item degradation and A5. |
| K3 | Declare success because other sources fill the selected-article limit | It can conceal complete Substack failure. | Direct per-source parsing/extraction evidence for the blocked cases. | A1 and J1. |
