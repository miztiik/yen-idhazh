# Browser transport and request pacing

**Last Updated**: 2026-11-01

**Level**: 5 - transport design, destination validation and diagnostic contracts.

## 0 - Operating contract

Table A - scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Use browser-like TLS connections, reduce request bursts, and retain enough failure evidence to diagnose refused feed and article requests. |
| A2 | Hard scope - in | Three dependent PRs: replace Undici completely with Impit and remove DNS-rebinding machinery; add shared domain/publisher pacing; verify the completed Impit-only pipeline from this branch. Firefox becomes primary. TypeScript contracts and JSONL/stage APIs follow the new design rather than retaining obsolete transport assumptions. |
| A3 | Removal scope | Remove all address-pinning implementation from the TypeScript source-download path: project-controlled hostname DNS resolution, repeated DNS checks, validated-address transport arguments, socket pinning, injected resolver plumbing, dedicated tests and current documentation claims. Retain URL syntax, scheme, credential, explicit local/literal-address, redirect, identity and sanitizer checks. These retained checks do not provide DNS-rebinding protection. |
| A4 | Delivery order | PR 1 -> PR 2 -> PR 3. PR 1 replaces and removes Undici in the same change. No migration switch, dual implementation, compatibility facade, fallback, strangler pattern or deferred removal. One completed successful Impit pipeline run from this branch satisfies live verification; no baseline comparison or mandatory second run. |
| A5 | Plan status | AUTHOR-AND-STOP. This file does not install project dependencies, change application code, dispatch a workflow or open PRs. |
| A6 | ESCALATE triggers | 1. Before implementing Level-5 changes, complete design consultation and plan authorization. 2. If any repository rule, header policy, schema, API, test or transport abstraction restricts useful Impit capability, bring the exact conflict, proposed change, benefit and cost to the decision surface; do not disable the capability or preserve an obsolete limitation silently. 3. Stop before editing `CLAUDE.md` or `AGENTS.md`; neither is included. 4. Surface unresolved TLS verification, cancellation, byte-limit or redirect behavior. 5. Surface browser execution, robots-policy, proxy or feed-population changes. 6. If pacing would exceed the runner's six-hour job limit, report a viable schedule and its trade-off. |
| A7 | Chosen strategy | Build the actual APIs around Impit's supported capabilities. Reuse useful boundaries, but replace obsolete signatures and assumptions instead of forcing native behavior through an Undici-shaped adapter. Keep feed parsing and extraction unchanged unless evidence requires a separately surfaced change. |
| A8 | Execution | Execute per `docs/how-to/execute-a-plan.md`: one maintainer carries the plan; parallel N = 1 because the PRs share transport, configuration and tests; consult a persona where two implementation choices differ materially; honor the ESCALATE triggers. AUTHOR-AND-STOP until execution is authorized. |
| A9 | Live-run safety | The current manual workflow delivers metadata to `main`. PR 3 adds an explicit no-delivery mode before branch validation. A validation run retains verified artifacts without committing repository data. This is a delivery control, not a transport migration switch. Normal workflow delivery remains unchanged. |
| A10 | Evidence ownership | Current behavior: `docs/architecture/sources/feed-harvesting.md`, `docs/architecture/sources/feed-operator-api.md`, `docs/architecture/sources/feed-failure-diagnostics.md` and `docs/architecture/sources/feed-plan-runner.md`. Test commands: `docs/how-to/run-the-gates.md`. |

Table B - scope exclusions

| ID | What is out | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | A Playwright implementation or browser pool | JavaScript challenges may still return 403 | Runner evidence that Impit fails, followed by a separate browser-runtime design |
| B2 | Changes to Python extraction, published pages or model processing | Other producers retain their existing HTTP behavior | A separate request naming those producers |
| B3 | Proxies, third-party fetch services, cookie import or login | Network-address blocks and authenticated content remain unresolved | A separate destination and credential design |
| B4 | Replacing Defuddle, Feedsmith or sanitizer behavior | Extraction and feed-format failures remain distinct from transport failures | Evidence of a parser defect, handled as its own change |
| B5 | Guaranteed removal of every 403 | A publisher can refuse either transport | Actual runner response evidence; no success-shaped fallback |
| B6 | Raw HTML/XML, article text and body samples in any diagnostic output | Response prose cannot be inspected; troubleshooting uses status, headers, URLs and attempt facts | A separate diagnostic-content request; this plan removes existing body dumps rather than moving them |
| B7 | Library-version assertion tests | Dependency release numbers are not test assertions | Behavioral regressions only; manifests and lockfiles still provide reproducible installs |

## 1 - Status Reckoner

Table C - PR-shaped tasks

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Replace Undici completely with Impit and failure evidence | - | A | BLOCKED | impit-transport-and-evidence | #1874 | - |
| C2 | 2 | Space requests across domains and publishers | 1 | B | PENDING | - | - | - |
| C3 | 3 | Verify the completed Impit-only branch pipeline | 2 | C | PENDING | - | - | - |

## 2 - Shared implementation contracts

Table D - declarations before implementation

| ID | Contract | Required behavior |
| --- | --- | --- |
| D1 | Outbound HTTP boundary | One native Impit source-download boundary accepts validated URLs, configured native profiles/settings, abort signals and decoded-byte limits. Responses retain actual status, body, redirect location and bounded response evidence. Redesign `HarvestTransport` where necessary; no Undici-compatible facade, dispatcher emulation or legacy-only parameters. Source HTTP uses this boundary; loopback stage-API calls retain their independently required HTTP behavior. |
| D2 | DNS removal | Apply A3 throughout the TypeScript source-download path. Remove `ResolveAddresses`, `resolveAddresses`, `validateTarget`, `ResolvedAddress`, `createPinnedDispatcher` and all pinning/resolver arguments, helpers and dedicated tests. Keep `validateTargetName` and its explicit-address checks. DNS failures originate in Impit and retain an available typed code. The validation attempt means URL validation, not successful DNS resolution. |
| D3 | Native profiles | Add a browser selection to each configured request profile. Primary is Firefox; secondary is Chrome. Impit selects the corresponding built-in TLS profile. Remove fixed browser-version strings and legacy navigation-header bundles that conflict with native fingerprint defaults. Supported explicit overrides must have a current purpose. Check whether the appended crawler identity changes native browser behavior; surface a conflict under A6 rather than force an incompatible header. Robots matching and wire identity remain consistent with the settled policy. |
| D4 | Direct replacement | Impit is the only source HTTP implementation as soon as PR 1 lands. Delete Undici imports, direct dependency, implementation, dispatcher helpers, dedicated tests and current documentation claims together. Do not create `http_transport`, a temporary adapter, a shadow run or a hidden native-failure fallback. Breaking request/config changes are allowed; stale authored inputs fail with named validation errors rather than silently selecting old behavior. |
| D5 | Response evidence | Declare one native `HttpResponseEvidenceSchema` in `packages/common-contracts/src/schemas/http-response-evidence.schema.ts`. Fields: nullable `content_type`; nullable nonnegative integer `decoded_bytes`; nullable nonnegative integer `declared_content_length`; configured allowlisted, bounded `selected_headers`; `headers_truncated` listing truncated header names; request-profile identifier. No `transport` field: the application has one source transport. Preserve an observed response status even if reading its body later fails. Never persist a false zero when bytes were not measured. |
| D6 | Diagnostic settings | Add `harvest.response_diagnostics` with `header_names` and `max_header_value_chars`. Initial headers: `content-type`, `content-length` and `retry-after`, with 256 characters per header value. Failed-operation metadata is always logged; no new switch disables required evidence. Reject authorization, cookie and credential-related header names at configuration load. Sanitize header values and retain truncation indicators. Do not add a body-sample knob. |
| D7 | Body-free failure artifact | Remove raw HTML/XML and all body/text samples from the existing optional diagnostic artifact. Keep the existing dump flag as the artifact-enable control and document that it now writes metadata only. Project `FetchedDocument` into a separately validated body-free metadata model before serialization; do not set `body` to null as a substitute for removing the field. Omit `run_id` and `transport` from diagnostic records, nested documents, observations and attempts; the filename carries run identity. Retain other safe metadata, hashes, parent references and ordered observations/attempts. Ordinary pipeline identity and ledger keys are not removed by this diagnostic projection. Successful content remains in memory for parsing and selected output; this removes diagnostic dumping only. |
| D8 | Evidence readers | Every failed network attempt logs its actual response status, content type, allowlisted headers, request profile and requested, final-attempted and failed URL evidence. Terminal fetch/parse failures carry the same evidence without fabricating a response for pre-dispatch or parse failures. Preserve robots, primary and secondary failures separately. Keep event identity and dispatched-request counting through validated projections. Do not introduce redundant `run_id` or `transport` fields in the new failure details. Apply the existing diagnostic URL policy: remove credentials, query values and fragments; omit signed URLs. Surface any conflict with required troubleshooting under A6. |
| D9 | Contract changes | Declare the new TypeScript configuration, diagnostic and request contracts before readers/writers. Breaking changes are allowed: update active callers, fixtures and consumers together; remove obsolete aliases, old transport defaults and migration-only code. Stamp changed native contracts and append changelogs. For persisted ledgers a later run actually needs, name the exact read-side transition and surface a release-blocking conflict under A6; do not silently discard required history. Current-only stage/artifact/config shapes need no legacy transport readers. No Python planner copy, compatibility facade or unused schema. |
| D10 | Pacing configuration | Add `harvest.request_pacing` with `enabled`, `domain_delay_ms`, `publisher_delay_ms` and `jitter_ms`. Initial estimate: enabled; a 1000 ms base delay for both domain and publisher; independent nonnegative jitter from 0 through 500 ms. The first admitted request needs no initial delay. Zero values provide an explicit no-delay setting. Validate nonnegative finite integer milliseconds. Declare the enable switch's removal condition. |
| D11 | Pacing identity | Domain means the registrable domain computed with the existing `tldts` dependency and configured private-suffix policy; use the normalized hostname when no registrable domain exists. A non-null curated `publisher_id` adds a second independent key. A null publisher creates no shared null-publisher key. Neither key is inferred from article prose or HTTP body text. |
| D12 | Pacing rule | For either shared key, permit one source request at a time. After that request's body closes or fails, the next request waits for its configured base delay plus sampled jitter. Apply both applicable keys; do not choose one instead of the other. This spaces completed source requests, not only top-level feed operations. Retries, secondary profiles, robots downloads and redirect hops participate. Cache hits and validation-only refusals do not consume a request slot. |
| D13 | Pacing ownership and timers | One listener shares pacing across collections and standalone document requests. A standalone CLI/probe owns one scheduler per invocation. Source identity comes from `documentWork` and the configured feed. Redirects use the destination domain and supplying publisher. Queue/cooldown waits are abortable and outside HTTP-attempt timers. Each attempt carries measured `pacing_wait_ms`; the terminal record carries their sum as `pacing_time_ms` and a captured `pacing_settings` object with the effective D10 fields. Validation/cache-only attempts have zero measured pacing wait. Null means unmeasured, not zero. Network `duration_ms` excludes pacing and backoff; enclosing fetch elapsed time includes them. Release keys on every outcome and remove idle state. |
| D14 | Scheduler mechanism | Use the open-source `bottleneck` package for keyed single-request queues, with one shared domain group and one shared publisher group. Acquire them in a fixed order. Hold both applicable keys through the actual response read and its cooldown, so nested scheduling cannot admit bursts. Cancellation must settle queued promises and release all held keys; scheduler shutdown must drain or cancel only its owned work. Verify those properties before retaining this choice. Its beneficiary is shared request pacing; its cost is one JavaScript dependency and queue state, with no browser bundle or native binary. |
| D15 | Later browser transport | Keep an adapter-neutral response/attempt contract, manual redirect handling, decoded-byte limits, cancellation and lifecycle ownership. Add only lifecycle hooks that Impit actually needs now. A later Playwright adapter must route every browser request, including redirects and subresources, through permission, pacing and accounting controls. Do not add a browser mode, fake adapter, dependency or automatic 403 escalation now. |
| D16 | Verification identity | The workflow receipt names immutable code SHA, effective configuration, profiles, host, run and attempt. Diagnostic records use the filename for run identity and omit redundant transport labels. Evidence must match the Impit-only candidate containing PRs 1 and 2; a default-branch run does not certify this branch. One successful completed run is sufficient. |
| D17 | Diagnostic URLs | `requested_url` names the original operation input; `final_attempted_url` names its last dispatched target; `failed_url` names the actual request that failed, including a robots URL when the robots request failed. Attempts retain their own `request_url` and profile. Redirect history retains ordered sanitized requested destinations and actual status codes. Before dispatch, final/failed request URLs are null; a parse failure does not invent a failed HTTP request. |
| D18 | Diagnostic filename | Generate `raw-document-contents-<UTC-day>-<numeric-run-id>-<attempt>.jsonl` using validated execution identity only. The UTC day and numeric run component come from `context.run_id`; attempt comes from `context.writer.attempt`. Do not duplicate the date by appending the full date-prefixed run identity. Replace the fixed filename constant with one shared filename builder used by writing, packaging, permission lists, upload outputs and finish verification. Recalculate artifact-root length validation for the generated filename. Example: `raw-document-contents-2026-11-01-41289308580-1.jsonl`. |
| D19 | Native capability assessment | Review Impit's native fingerprint selection, HTTP/2 and HTTP/3 controls, default headers, decompression/streams, cancellation, timeouts, redirects, cookies and lifecycle against the actual API. Use useful native defaults and configuration without copying Undici limitations. Do not add every optional feature speculatively. Surface each blocked useful capability with the exact repository constraint, proposed contract/code change, cost and recommendation. No silent disablement or narrowing. |

## 3 - Row #1 - Replace Undici completely with Impit and failure evidence

- **Scope:** Replace Undici completely in the real source-download APIs, remove its pinning machinery and implementation debris, make Firefox primary, and write body-free failure evidence.
- **Files touched:**
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `packages/feed-probe/bun.lock`
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/http-response-evidence.schema.ts` (new)
  - `packages/common-contracts/src/schemas/harvest-diagnostics.schema.ts`
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/raw-document-failure.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/common-contracts/test/http-response-evidence.test.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/transport.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/impit-transport.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/safe-target.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/http-request-target.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-diagnostics.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/logging/structured-logger.ts`
  - `services/feed-ingest-plan/src/dump-raw-document-failure.ts`
  - `services/feed-ingest-plan/src/selected-artifact-path.ts`
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts`
  - `services/feed-ingest-plan/scripts/finish-run-output.ts`
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `.github/workflows/source-transport-test.yml`
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/impit-transport.test.ts` (new)
  - `packages/feed-probe/src/feed-probe.ts`
  - `packages/feed-probe/test/feed-probe.test.ts`
  - `packages/feed-probe/test/feed-probe-cli.test.ts`
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/trust-boundary.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261101-browser-transport-request-pacing-plan.md`
- **Acceptance gates:** On Linux, inspect shared selection; run native `check` for common contracts, service and probe, then combined changed contract, transport, harvest, robots, logging, failure-retention and probe tests. Exercise the real Impit client under Bun on Linux with bounded generated loopback responses in the separate `source-transport-test.yml` workflow; ordinary source tests use recorded responses. Verify API deadline completion without adding an immediate socket-close latency gate; report separately any unfinished native work that outlives the configured attempt budget. Audit source/probe manifests, lockfiles, imports, helpers, assertions and current docs for Undici and pinning debris. Explain a transitive dependency rather than class it as unrelated silently; surface any required replacement. Production CI stays unchanged and runs the full candidate suite with supervised API/CLI, workers and required persisted readers.
- **Oracle:** The real Impit adapter reads generated compressed response streams, refuses an oversized decoded body at cutoff, cancels a stalled response and returns a redirect without following it; the real API then preserves the exact observed status and bounded failure evidence without feeding failure HTML to the parser. This proves transport behavior and evidence boundaries, not access to a live publisher.

Table E - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| E1 | Implement D1-D9 and D15-D19 in the actual APIs. Update routing/contracts when native capabilities require it; keep existing XML/HTML parsers and sanitizers. No transport migration stage or switch. | Direct replacement design |
| E2 | Delete the dedicated pinned-dispatcher test and DNS-rebinding/pending-injected-DNS test. Retain byte-limit, cancellation, URL/literal-address, robots, redirect, extraction and request-accounting behavior tests. Native DNS failures remain ordinary transport failures. | Removal scope A3 |
| E3 | Update resolver-bearing fixtures and callers instead of retaining dead resolver injection for old tests. Do not delete complete mixed-purpose test files. | Structural deletion |
| E4 | Use Impit's documented fingerprints and native header behavior. Verify actual wire behavior; surface any crawler-identity or header policy conflict instead of disabling useful native behavior. | Native-profile contract D3 |
| E5 | Package release numbers belong in manifests/lockfiles, not passing assertions. Measure installed native bytes and installation time on the runner and document the dependency's transport beneficiary. | Dependency and test scope |
| E6 | Preserve legacy Python statements in the shared trust-boundary page when still true; explicitly distinguish the changed TypeScript path. Do not claim DNS-rebinding protection remains in this path. | Documentation accuracy |
| E7 | Failure metadata belongs in JSONL and the optional metadata-only artifact; no raw body or sample belongs in either. Extend the logger through a validated metadata projection, not by removing its general sensitive-field filter. | Diagnostic contract D5-D9 and D17-D18 |
| E8 | Assert diagnostic serialization omits body, `run_id` and `transport` fields recursively, retains complete ordered attempts and effective pacing data, and uses one filename builder. Verify no active source-download implementation, caller, helper or dedicated test retains address pinning or Undici. | Removal and diagnostic contracts |

Table F - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | Add Impit only to a separate experiment | Does not implement the API capability | Another integration pass through all actual source-download callers | Requested scope |
| F2 | Delete all safety and extraction tests with the transport | Removes unrelated behavior coverage | Rebuild the retained boundary tests and risk silent regressions | Removal scope A3 |
| F3 | Print complete response headers, bodies or body samples | Can expose secrets and retains the diagnostic content this change removes | A separate logging and artifact-safety design | Diagnostic contract |
| F4 | Keep a transitional Undici adapter or migration switch | Leaves the dual implementation and removal debt this plan excludes | Two code paths, parity work and a later cleanup change | Direct replacement D4 |

## 4 - Row #2 - Space requests across domains and publishers

- **Scope:** Apply configurable, jittered pacing to every outbound source request across the real APIs, bulk harvester and standalone probe.
- **Files touched:**
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `packages/feed-probe/bun.lock`
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/request-pacing.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/transport.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `packages/feed-probe/src/feed-probe.ts`
  - `services/feed-ingest-plan/test/request-pacing.test.ts` (new)
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/article-robots-policy.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `packages/feed-probe/test/feed-probe.test.ts`
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `TODO/20261101-browser-transport-request-pacing-plan.md`
- **Acceptance gates:** Local: inspect shared test selection; run affected native type checks and combine pacing, harvest-safety, article-robots, collection-HTTP, logging and probe tests. Use real queue primitives and recorded source responses. Drive the jitter calculation with supplied random inputs; use broad real-clock tolerances only for scheduler integration. CI: full suite and representative concurrent standalone/collection API coverage.
- **Oracle:** Two requests sharing either domain or non-null publisher never overlap and never start before the earlier request's completion plus its configured cooldown; unrelated keys can progress while one key waits. Cancellation creates no source dispatch or stranded key, and retry/redirect/profile request counts remain exact. This proves pacing behavior, not that a publisher will stop returning 403.

Table G - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| G1 | Implement D10-D14 at the actual source-dispatch boundary, not as a sleep around a feed loop. Reuse existing publisher facts and domain parsing. | Requested pacing scope |
| G2 | Per-listener pacing is shared even though run observations and source reservations remain isolated. Scheduler state is process-local and is never a new ledger. | Concurrency and persistence separation |
| G3 | Test shared domain/different publishers, shared publisher/different domains, null publishers, redirects, robots cache hits, retries, secondary requests, cancellation and disabled/zero settings at their lowest suitable tier. | Pacing failure mechanisms |
| G4 | Measure pacing wait separately from network-attempt time and retry backoff. Preserve total elapsed time and actual UTC event instants. Waiting is not a source failure or another fetch attempt. | Timing contract D13 |
| G5 | The initial delay values are estimates, not measured optimal values. Record runner cost before changing them; do not reduce them merely to manufacture a green run. | Config-driven behavior |
| G6 | Verify the D14 library arrangement meets the oracle, particularly cancellation and dual-key ordering. If it does not, consult on a replacement queue arrangement rather than ship a custom hidden fallback. | Queue correctness |

Table H - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | One global request delay | Serializes independent publishers unnecessarily | Longer runs; measure lost concurrency on the configured source list | Domain/publisher scope |
| H2 | Domain OR publisher as a single chosen key | Either cross-domain publisher bursts or same-domain bursts remain | A weaker traffic policy with explicitly priced publisher coverage | Pacing contract D12 |
| H3 | Delay only the first feed request | Articles, retries and redirects can still burst | Another dispatch-boundary implementation later | Requested outcome |
| H4 | Persist request locks or scheduling timestamps | Adds shared-run reservations and stale recovery work | A new persisted scheduler contract and migration | Process-local design |

## 5 - Row #3 - Verify the completed Impit-only branch pipeline

- **Scope:** Add safe branch-validation delivery controls, complete one successful actual Impit-only pipeline run from this branch, and close the plan only when no Undici or pinning implementation debris remains.
- **Files touched:**
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/finalize-run-output.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-delivery-result.ts`
  - `services/feed-ingest-plan/scripts/finish-run-output.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts`
  - `services/feed-ingest-plan/test/plan-entry-points.test.ts`
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `packages/feed-probe/bun.lock`
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/transport.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/impit-transport.test.ts` (introduced in PR 1)
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-failure-diagnostics.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261101-browser-transport-request-pacing-plan.md`
- **Acceptance gates:** Local before dispatch: native checks, workflow/finalization tests and actual supervised API/CLI fixture composition. CI: full candidate suite. Live: push the Impit-only candidate containing PRs 1 and 2 and no-delivery controls; dispatch `feed-ingest-plan-test.yml` with `--ref` naming this branch, diagnostic artifact enabled and metadata delivery disabled. Read its SHA/configuration, response/report, selected artifact, health, metadata-only failures, pacing/attempt evidence and shutdown. One completed successful run suffices; no baseline or mandatory second run. Failed runs require correction and another candidate run. Audit final source/probe dependencies, callers, tests and docs for debris; CI verifies the final merge candidate.
- **Oracle:** This branch completes collection, parsing, selection, configured partitioning, local persistence, artifact verification and shutdown using Impit and pacing, with D16 identity and no metadata commit. Undici, migration switches, pinned dispatchers and resolver injection are already absent. Functional boundary tests remain green. This proves completed integration and clean removal, not universal publisher access.

Table I - decisions

| ID | Decision | Authority |
| --- | --- | --- |
| I1 | Add a workflow boolean `deliver_metadata`, default true. False means validate and package actual local output without Git delivery; logs and reports explicitly say delivery was not requested. Preserve current failed-run recovery packaging and normal true-mode checks. A skipped commit is not reported as a successful commit. | Live-run safety A9 |
| I2 | Execute one completed successful Impit pipeline run on this branch. Use configured feed population and effective limits; surface any proposed reduction. Record actual refusals, pacing settings/wait, network durations and attempts. No baseline comparison, dual run or mandatory second success. | Branch verification D16 |
| I3 | If the pipeline fails, fix it in the intended implementation and repeat necessary verification. Do not restore Undici, add a fallback or retain a disabled old path. A completed run with typed source refusals is distinct from a failed pipeline. | Direct replacement |
| I4 | PR 1 already removes Undici and regenerates affected lockfiles. PR 3 verifies no remaining implementation debt: old imports/helpers, selectors, wrappers, resolver arguments, dedicated assertions, dead fixtures or inaccurate current docs. Retain generic stream, cancellation, status, redirect, robots, recovery and accounting tests. | Clean final state |
| I5 | Search source/probe dependency closure and current code/docs for Undici references. A surviving direct or transitive runtime dependency needs a named replacement or a surfaced conflict, not an exemption hidden in the plan. Distinguish unrelated producers and immutable Git history; do not delete unrelated systems. | No transport debris |
| I6 | If runner 403 evidence remains unresolved, report the selected profile, actual status/type, safe headers and failed request address. These facts alone do not prove a browser challenge. Price a separate Playwright adapter under D15. Do not automatically launch a browser, send text elsewhere, suppress failures or fabricate success. | Browser scope B1 |
| I7 | Keep live-run receipts outside the repository; place the current transport/runtime findings and dependency costs in the living transport docs. The plan tracks PR completion, not a growing run log. | Evidence and documentation ownership |

Table J - rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Test branch code through the normal metadata-writing workflow | Can change default-branch data during a migration check | Normal data delivery and its recovery responsibilities, requiring a separate dispatch decision | Live-run safety |
| J2 | Keep both transports, even temporarily | Leaves a migration stage and cleanup debt | Two implementations, parity work and a deferred removal change | Direct replacement A4 |
| J3 | Add Playwright now as an automatic 403 fallback | Browser execution, subresources and lifecycle have not been designed | Browser binaries, runner install/runtime cost and a separate request-authority/accounting design | Browser scope B1 |
| J4 | Demand that every source returns 200 | A publisher can refuse valid clients independently of pipeline correctness | A separate source-access investigation, not a stronger migration test | Verification limits |

## 6 - Diagnostic field example

Table K - example interpretation

| ID | Example | Meaning |
| --- | --- | --- |
| K1 | The JSON below | Illustrative metadata-only terminal failure, not a measured result or full schema fixture. It includes every phase in order: URL validation, robots and two target profiles. Real output retains matching observations and other safe identifiers through D7-D8 projections. |
| K2 | Absent response | Response fields are null or an empty header map when unavailable. No HTTP status, failed request URL or duration is invented. |
| K3 | Removed fields | No raw content, body sample, redundant `run_id` or `transport` fields in diagnostic records or nested metadata. Existing body digest metadata may remain. |

```json
{
  "schema_version": "2026-11-01",
  "document_kind": "feed",
  "request_id": "36922de9-ab15-4f96-b5ae-039cc72a2a5b",
  "attempt": 1,
  "feed_id": "configured-feed",
  "publisher_id": null,
  "operation": "fetch",
  "failed_at": "2026-11-01T08:33:00Z",
  "failure_reason": "http",
  "requested_url": "https://feed.example/feed",
  "final_attempted_url": "https://feed.example/feed",
  "failed_url": "https://feed.example/feed",
  "http_status": 403,
  "content_type": "text/html; charset=UTF-8",
  "selected_headers": {
    "content-type": "text/html; charset=UTF-8",
    "content-length": "6163"
  },
  "headers_truncated": [],
  "request_profile": "chrome",
  "decoded_bytes": 6163,
  "declared_content_length": 6163,
  "redirects": [],
  "robots": "allowed",
  "robots_http_status": 200,
  "robots_failure": null,
  "error_code": null,
  "body_limit": null,
  "pacing_time_ms": 2200,
  "pacing_settings": {
    "enabled": true,
    "domain_delay_ms": 1000,
    "publisher_delay_ms": 1000,
    "jitter_ms": 500
  },
  "attempts": [
    {
      "phase": "validation",
      "sequence": 0,
      "retry": 0,
      "duration_ms": 77,
      "backoff_ms": 0,
      "retry_total_ms": 0,
      "http_status": null,
      "failure": null,
      "error_code": null,
      "request_profile": null,
      "request_url": null,
      "content_type": null,
      "selected_headers": {},
      "pacing_wait_ms": 0
    },
    {
      "phase": "robots",
      "sequence": 1,
      "retry": 0,
      "duration_ms": 77,
      "backoff_ms": 0,
      "retry_total_ms": 0,
      "http_status": 200,
      "failure": null,
      "error_code": null,
      "request_profile": "firefox",
      "request_url": "https://feed.example/robots.txt",
      "content_type": "text/plain; charset=utf-8",
      "selected_headers": {},
      "pacing_wait_ms": 0
    },
    {
      "phase": "target",
      "sequence": 2,
      "retry": 0,
      "request_profile": "firefox",
      "request_url": "https://feed.example/feed",
      "http_status": 403,
      "content_type": "text/html; charset=UTF-8",
      "selected_headers": {},
      "failure": "http",
      "error_code": null,
      "duration_ms": 90,
      "backoff_ms": 0,
      "retry_total_ms": 0,
      "pacing_wait_ms": 1000
    },
    {
      "phase": "target",
      "sequence": 3,
      "retry": 0,
      "request_profile": "chrome",
      "request_url": "https://feed.example/feed",
      "http_status": 403,
      "content_type": "text/html; charset=UTF-8",
      "selected_headers": {
        "content-type": "text/html; charset=UTF-8",
        "content-length": "6163"
      },
      "failure": "http",
      "error_code": null,
      "duration_ms": 91,
      "backoff_ms": 0,
      "retry_total_ms": 0,
      "pacing_wait_ms": 1200
    }
  ]
}
```

## 7 - Execution checklist

1. Resolve the Level-5 implementation design before code work. Do not edit protected instruction files.
2. Carry each Status Reckoner row in its own PR; dependent work uses the preceding candidate code. Do not fan out edits to shared configuration, transport or tests.
3. At each row, refresh the exact deletion-reference inventory and add newly found live callers to that row before editing. New transport modules must each answer one narrow question.
4. Keep related manifest and lockfile changes together; run checks through the documented native package runners after shared selection.
5. PR 1 removes Undici completely; PR 3 certifies one successful Impit-only branch run and a debris-free final tree. Keep all failures visible and distinguish publisher refusal, local transport failure and pipeline failure.
6. Stop after authoring this plan. Implementation and workflow execution are separate actions.
