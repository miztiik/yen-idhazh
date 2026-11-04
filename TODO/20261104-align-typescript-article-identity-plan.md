# Align TypeScript article identity

**Last Updated**: 2026-11-04
**Level**: 5 - identity and persisted TypeScript contracts.

## 0. Operating contract

Table A - Operating contract

| ID | Field | Value |
| --- | --- | --- |
| A1 | Intent | Give TypeScript callers one clear article identity, preserve the URL needed to fetch that article, and keep separate input occurrences from overwriting one another. |
| A2 | In scope | TypeScript feed-planner HTTP APIs, their orchestration clients, native contracts and implementation; the rejection-column type change; optional readable selected URLs in response artifacts; related offline recordings, tests, lockfiles and living docs. |
| A3 | Out of scope | Table B defines the boundaries, their costs and what would bring them into another change. |
| A4 | State | Sequential PR delivery. All delivery rows start pending. Naming alternatives are in Table C; C1 is the spelling used by this plan. |
| A5 | Baseline | Investigated commit `14a1dc8d240ee7e94a9b20cb7ba98e3bb64b5d7c`; current main at dispatch preparation is `8cc6a1db4c81ecf69243cac2e59632043c588da7`. Start row 1 from the current default branch. Preserve the intervening collection-retention and server-logging fixes, and update inventories against each row's actual base. |
| A6 | Strategy | Full URL SHA-256 for articles; a captured UUIDv4 for each input occurrence; explicit API-to-storage projections. Architecture consultation: Fowler. The lifetime remains the existing live-process lifetime, not a new restart store. |
| A7 | PR shape | Each delivery row is one independently verified PR. Order: row 1 -> row 2 -> row 3. Shared schemas, implementation and recordings make these rows serial. Parallel N = 4 remains the execution ceiling, not a requirement to overlap shared files. |
| A8 | ESCALATE triggers | 1. Pause before Level-5 implementation until execution is explicitly requested. 2. Surface any required Python, published-site or foreign-contract change. 3. Surface any new durable admission store, restart/replay promise or caller idempotency key. 4. Surface a need to change a historical file or the existing family-specific read rules. |
| A9 | Execution | Execute per docs/how-to/execute-a-plan.md: one coordinator carries the plan; one nested app session owns each row and its PR; deliver rows 1 -> 2 -> 3 as dependent PRs without waiting for a merge; consult a persona only where two answers would lead to different code; honor the ESCALATE triggers in section 0. Leave the PRs open for review and retain their worktrees. |

### Scope boundaries

Table B - What stays outside these PRs

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Python normalization, public digest IDs and frontend links | Python's query-encoding defect and vertical-prefixed public IDs remain. This plan does not establish cross-language normalization parity. | A separate producer-and-reader change covering Python contracts, publication and links. |
| B2 | Removing foreign publication fields from TypeScript read copies | TypeScript still reads the native publication identifier and URL key to interpret existing publication and failure evidence. | Changing the foreign writer and all its readers together; not a TypeScript API rename. |
| B3 | Renaming the article-address column throughout retained planner storage | API and storage names intentionally differ at one explicit projection boundary. | A storage-naming requirement worth changing discovery, selection, history, compaction and artifact consumers for naming alone. |
| B4 | Clustering, URL alias registries and a new logical-report identity | Different URLs can remain separate article records. This work does not provide semantic duplicate detection or guarantee that every alternate URL is retained. | A separately scoped clustering or URL-independent continuity requirement with an actual reader. |
| B5 | Request journals, response caches, restart recovery and automatic HTTP-request replay | A new process cannot recover live references. A repeated direct submission is new work, not an exactly-once retry. | A requirement for lost-response recovery or durable replay, with its storage and ownership design. |
| B6 | Rewriting historical data or adding old-field aliases | Incompatible current-format inputs remain explicit refusals or evidence gaps under the existing native rules. | A separately specified compatibility requirement; never silent rehashing or null-fill migration. |
| B7 | The independent experiment in `.github/scripts/ai-pipeline.ts` and `.github/workflows/ai-pipeline-tests.yml` | Its URL library and behavior remain separate from the operator APIs. | A request to change that independent path. Shared dependency lock updates do not migrate it. |
| B8 | A new sanitized-text revision field or update-detection policy | URL identity alone does not detect changed reporting at an already seen address. | A version/revisit feature with a named producer and consumer. |
| B9 | Editing `CLAUDE.md` or `AGENTS.md` | No contract-wide policy changes are included. | A separate explicit instruction to edit those files. |

### Naming choice

Table C - Names for one input occurrence

| ID | Name | Meaning and benefit | Cost or ambiguity |
| --- | --- | --- | --- |
| C1 | **Recommended: retain `candidate_id`** | One candidate input captured for a run, from either a feed entry or a direct URL request. It remains the same through processing, including after selection or refusal. This name is already used by the native pipeline. | Its meaning and allocation must change as specified in D3; retaining a name does not retain the faulty positional seed. |
| C2 | `screen_candidate_id` | Names a candidate specifically for the screening stage. | Too narrow: the same identity is needed before screening for fetch/parse and afterward for selection, entity evidence and retained failures. |
| C3 | `intake_id` | Names entry into processing without tying it to a source. | Adds vocabulary and renames an established field without fixing anything that C1 cannot fix. |
| C4 | `submission_id` | Clear for a direct submission and usable for a collector-submitted feed entry. | Can suggest that every entry arrived through a separate external submission API. |
| C5 | `input_id` | Short and source-neutral. | Can be mistaken for a feed document, a stage payload or the article itself. |

Recommendation: C1 keeps the established term; fix allocation and the public alias instead of renaming the whole pipeline.

### Exact field changes

Table D - Authoritative field map

| ID | Current field or behavior | Proposed field or behavior | Ledger(s) | Ledger column(s) and effect | Owning row |
| --- | --- | --- | --- | --- | --- |
| D1 | Article API identity has several spellings | `article_id` means the complete 64-character lowercase hexadecimal SHA-256 of UTF-8 `canonical_url`. It identifies an address, not article text or a news event. No feed, publisher, taxonomy, run or model value enters this hash. | `discovered-articles`, `selected-articles`, `rejected-articles` | `url_key`: retain the name and full digest; new rows use Table F's URL bytes. | 1 establishes the URL bytes; 3 establishes API spelling |
| D2 | The article cleaner drops every query; the feed identity helper decodes and rejoins query values | Apply Table F before hashing. The TypeScript copy of the query-encoding defect is included; the Python implementation is not. | `discovered-articles`, `selected-articles`, `rejected-articles` | `url_key`: corrected values in new rows. `selected-articles.canonical_url`: retain the query. No historical rewrite. | 1 |
| D3 | Native `candidate_id` and the separate `offer_id` spelling in public and held feed offers | Retain the native name. Rename the offer spelling to C1 and validate all occurrences with a new `CandidateIdSchema`: lowercase hyphenated UUIDv4. Remove `deriveCandidateId`; Table G defines allocation and lifetime. | `rejected-articles` | `candidate_id`: same column name, new captured value/type; exact null rule in D5. Other changed fields are in live/API/stage payloads, not additional ledger columns. | 2 |
| D4 | Every direct URL input falls back to original feed-entry ordinal zero, although no feed entry exists | Keep the original nonnegative `entry_ordinal` for feed entries. Use null for direct inputs in candidate and fetched-document records. The collision example is G9; the feed-entry schema itself still requires its original ordinal. | None | `entry_ordinal` is a private candidate/document field, not a current planner ledger column. | 2 |
| D5 | The rejection column permits a nullable SHA-256 occurrence value | Store D3's field as a required, non-null UUID for terminal article rows. Settle by run, attempt and that field; remove the now-invalid null-identity settlement fallback. Feed-level transient refusals have no candidate and do not become terminal article rows. | `rejected-articles` | `candidate_id`: nullable SHA-256 -> required UUIDv4. Logical settlement key stays `run_id`, `attempt`, `candidate_id`; its nullable fallback is removed. `url_key` stays the full address digest. | 2 |
| D6 | Generic fetched documents and operation observations call either a feed or article hash `article_id` | Use `document_id` for this generic URL key. Add D3's field to the captured document and matching observations: required for an article, null for a feed. Recompute the document hash from its canonical URL and check observation agreement. | None | Fields change in live documents, observations and private failure artifacts, not ledger columns. | 2 adds capture; 3 fixes generic naming |
| D7 | Fetch and parse responses expose different identity subsets | Use the discriminated response shapes in Table E. A response never exposes both generic and article spellings for the same key. | None | API fields only. | 2 and 3 |
| D8 | Selection and partition response `articles[].url_key` | Emit `articles[].article_id` through a strict API projection. Other selected metadata retains its existing meaning. Do not add a second public ID or expose article text. | `selected-articles` is the source, not a rename target | `url_key` and `canonical_url` remain unchanged column names. Only the API key changes. | 3 |
| D9 | Plan response `selected_url_keys` and `assignments[].url_key` | Emit `selected_article_ids` and `assignments[].article_id`. HTTP, CLI and saved response use one schema; the verifier compares them with storage values. Do not introduce a third spelling, `url_id`. | None; `plan-runs` is unchanged | These are response-only fields, not columns in `plan-runs`. Its existing `selected_count` and artifact-path column remain unchanged. | 3 |
| D10 | Planner discovery, selected and rejected rows, selected-text artifact and history use `url_key` | Retain that storage field and its full-digest representation. D8/D9 are projections, not ledger renames. Do not add the candidate key to selected metadata merely for symmetry. | `discovered-articles`, `selected-articles`, `rejected-articles` | Each retains `url_key`. `selected-articles` also retains its existing `canonical_url`. | Unchanged storage names |
| D11 | Foreign publication read copies contain `item_id` and `url_key` | Retain both in `metrics/publication-evidence.ts` and their existing readers. These identify a public digest item and a full address key respectively. Neither becomes another public TypeScript article field. | `published`, `item-health` (read only) | `item_id`, `url_key`: no rename, type change or rewrite. Public digest JSON remains a separate unchanged input. | Unchanged foreign boundary |
| D12 | Taxonomy and provenance | No new vertical-prefixed identifier. Keep feed, publisher and category facts as metadata. There is no TypeScript public-item-ID generator to remove in this planner. | `selected-articles`, `feed-health-state` (unchanged) | Selected `feed_id`, `publisher_id`, `categories` and health `feed_id` retain their existing meanings. No taxonomy column is added to an identity. | Constraint on all rows |
| D13 | `harvest.tidy_urls` and planner use of `tidy-url` | Remove this identity-changing option from native config/schema and remove the planner dependency. Delete its unused request-target helper. Refresh affected locks; B7 remains untouched. | None | Config and dependency changes, not ledger columns. | 1 |
| D14 | Schema and API date stamps | Update affected native schema versions and changelogs using the execution UTC date. Advance `PLANNER_PROTOCOL_VERSION` for wire changes and update current route docs/callers together; no old-name alias route. | `discovered-articles`, `selected-articles`, `rejected-articles`, where changed | `schema_version` is file metadata, not a renamed row column. No `plan-runs` or health-column change is required by the response option. | Each affected row |
| D15 | Real article entity records already contain `article_id` | Retain that article key and apply D3 to their candidate field. Their diagnostic stays private. | None | Private entity artifact fields, not committed ledger columns. | 2 |
| D16 | CloudEvents occurrence IDs, operation metadata, body digests and health endpoint keys | Retain their separate meanings and algorithms. Do not reuse any of them as D1 or D3. | `feed-health-state`, `plan-runs` and existing writer metadata (unchanged) | No rename to `endpoint_key`, `run_id`, `attempt` or file identities. Operation/event/body fields remain separate non-ledger identities. | Unchanged |
| D17 | Transient refusal nullability | Require D3 for every captured article input's refusal, including invalid source-entry URLs. Keep canonical URL and address key null when no valid address exists; use the existing missing-fields refusal, not an invented hash. Feed refusals keep article fields null. | `feed-health-state` receives existing grouped evidence | `rejection_counts[]` retains its shape. Malformed-entry refusals are not terminal fetch/extraction rows in `rejected-articles`. | 2 |
| D18 | Combined output has no per-request URL-display option | Add validated config `response.include_selected_urls`, default false, and optional boolean request override `include_selected_urls`. CLI accepts `--include-selected-urls` as true, or explicit `true`/`false` with a space or `=`. Explicit request values override config; absence uses config. Capture the effective value in `FeedPlanResult.include_selected_urls`, outside its persisted run row. | None | No new column in `plan-runs` or any other ledger. This option changes response presentation only. | 3 |
| D19 | The small combined response returns hashes without their readable URLs | Run-summary responses return the effective D18 boolean in HTTP, CLI and saved `response.json`; the separate pre-run error shape stays unchanged. When true, require `assignments[].canonical_url` for every selected assignment and verify its hash equals that entry's D9 article key. When false, omit the URL field, not null-fill it. Zero selections keep an empty array. | `selected-articles` is the existing in-memory source | No new column or Parquet read. Reuse its existing `canonical_url` and `url_key` pair; the selected-text JSON artifact already includes that pair without D18. | 3 |

### Public API result

Table E - Final wire contract, relative to the current dated API prefix

| ID | Surface | Required identity result | Request and storage constraints |
| --- | --- | --- | --- |
| E1 | `POST /fetch`, feed branch | Configured `feed_id` plus generic D6 key; no article or candidate field. | Feed request still uses configured feed identity, never an article ID. |
| E2 | `POST /fetch`, article branch | D1 and D3, with existing `feed_id` and canonical URL metadata. | A feed-derived request supplies D3 and its existing producing-feed-parse link. A direct request supplies its existing authorized URL and optional collection reference, not a caller-chosen candidate value. |
| E3 | `POST /parse`, feed branch | Add configured `feed_id` and generic D6 key. Each existing `offers[]` entry exposes D1 and D3 instead of its old occurrence spelling. | The `offers` array remains a list of feed offers, not a new entity or endpoint. Original feed positions remain captured privately. |
| E4 | `POST /parse`, article branch | Add D1 and D3, including on an extraction refusal after a valid article fetch. | Parse input remains exactly one held-fetch link. It accepts no copied article ID, candidate ID, URL or new replay control. |
| E5 | `POST /select-articles` and `POST /partition-articles` | Apply D8. | Strict public row schema rejects the storage-only spelling. The server-owned stage batch remains the authority for later work. |
| E6 | `POST /plan`, CLI output and saved `response.json` | Apply D9/D18/D19; order, counts, uniqueness, ranks, assignments and optional readable URLs must reconcile. | Resolve the display option once and carry it to output without rerunning selection or reading Parquet. Do not rename retained columns. |
| E7 | Persistence, collections, health and safe delivery | Existing operation references, receipts, counters and resource handles stay unchanged. | Do not add article identifiers to aggregate responses that do not return articles. Do not rename unrelated health or resource keys. |

### URL identity rule

Table F - Conservative URL protocol

| ID | Rule | Required behavior |
| --- | --- | --- |
| F1 | Serialization | Use the runtime's existing standard `URL` parser, after the current input trim and HTTP scheme acceptance. Validate the existing URL format and length bounds before and after serialization. Keep target permission checks separate from syntactic identity and before any request. Do not build a query parser. |
| F2 | Resource distinction | Preserve the query, parameter order, repeated keys, blank values, encoded delimiters and plus signs as serialized by `URL`. Do not decode/rejoin with string concatenation or mutate through `URLSearchParams`. Preserve `www`, non-root trailing slashes, path case and the HTTP/HTTPS distinction. |
| F3 | Fragment | Remove only the fragment from HTTP resource identity. Keep the existing refusal of fragments in canonical payloads; replace query-and-fragment refusals with fragment-only validation. |
| F4 | Tracking and wrappers | Preserve every query initially, including tracking-looking names. Do not unwrap URLs embedded in a query. Different addresses can be grouped later without guessing which parameters the source needs. This gives up automatic tracking collapse and library-specific wrapper extraction. |
| F5 | Dispatch | Hash and initially dispatch the same normalized resource URL. For a syntactically valid but forbidden target, retain its normalized identity in the explicit preflight refusal and make no request. Preserve queries on redirects; validate every actual hop. Record redirect destinations as evidence without changing the initial article key. A wrapper is an ordinary URL unless its server redirects; it cannot grant an unchecked nested destination. |
| F6 | Repeatability | Normalization is idempotent and is a declared identity protocol, not a per-run configuration knob. The hash input excludes text and classification. Feed-document hashing uses the same conservative query preservation; configured feed slugs and health endpoint keys remain separate. |
| F7 | Evidence | Relevant URI distinctions: [RFC 3986 query component](https://www.rfc-editor.org/rfc/rfc3986.html#section-3.4) and [equivalence rules](https://www.rfc-editor.org/rfc/rfc3986.html#section-6). These rules do not claim that URL identity detects semantic copies or URL reuse. |

### Input occurrence rule

Table G - Capture once, carry unchanged

| ID | Boundary | Required behavior |
| --- | --- | --- |
| G1 | Allocation | Use the existing native cryptographic UUID facility through one `createCandidateId` helper. Allocate at the input boundary, before preflight or a source request, not in each later stage. Allocation does not depend on operation or event UUIDs. |
| G2 | Feed entry | Allocate once when constructing the captured offer for its original feed entry. Retain the value in that live offer and pass it to preparation, fetch, parse, screening, selection accounting and rejection recording. Re-preparing that same held input does not allocate again. Apply the same rule to the existing standalone harvester. |
| G3 | Direct URL | Allocate once for each admitted direct fetch request and attach it to the held document before downstream work. Distinct direct URLs in one collection/feed retain distinct values. Fresh submissions of the same URL also retain distinct values while sharing D1. |
| G4 | Transport retry and failure | A fetch's internal retries keep its captured value. Fetch failure, extraction failure, private entities and the terminal rejection refer to that same input. A recovered retry does not leave a terminal failure row. |
| G5 | Authority | Validate live producing-operation links, membership, claim, configuration, run, attempt, URL and captured identity together. A correctly spelled UUID alone grants no permission. Records may not change their captured source or article between stages. |
| G6 | Lifetime | Retain values in existing live offers, held documents and stage payloads. Do not add a durable admission file or ledger. Existing saved current payloads retain their stored value when read; this does not add an execution-replay loader. Consumed fetch/parse references still refuse reuse. |
| G7 | Fresh work versus replay | A new feed parse or direct request is new input. A process restart starts new work. No promise of recovering an ID after a lost response, of reopening a consumed parse, or of retaining allocation across a restart is added. |
| G8 | Choice ties | Preserve the existing direct lexical tie rule on the captured occurrence field after D3. The same captured batch retains its ordering; a genuinely new candidate set can choose another exactly tied representative. Do not change scores, diversity or URL-deduplication rules as part of this change. |
| G9 | Existing collision example | In an example collection with run `2026-11-04-1` and a configured feed `science`, direct URLs `https://example.test/a` and `https://example.test/b` both fall back to ordinal 0, the first feed-entry position. Both therefore receive `SHA256("2026-11-04-1\nscience\n0")`. Their article-address hashes differ, but the result map is keyed by the candidate value: storing the second replaces the first. This is equal hash input, not a cryptographic collision. See `services/feed-ingest-plan/src/api/parse-operation.ts:127,180,210`. |

### Storage, versions and verification

Table H - Compatibility and verification contract

| ID | Concern | Required handling |
| --- | --- | --- |
| H1 | Native planner versions | Follow the [family's current-format and historical-field rules](../docs/architecture/sources/planner-feed-history.md#raw-and-compact-copies). Current full-row readers/writers and delivery change together. Historical field-based health reads keep their existing support. Do not extend full-row refusal to independent usable health fields. |
| H2 | Affected declarations | Stamp config and article-identity-bearing candidate/discovery/selected declarations for row 1; input-bearing candidate, rejection, screened, stage, operation, private-entity and raw-failure declarations for row 2; config, response, operation, raw-failure and protocol declarations for row 3 where their output changed. Update application payload metadata when it carries changed fields, not CloudEvents `specversion` or occurrence allocation. Leave generic file layouts and unaffected run/health row schemas unchanged. |
| H3 | API/storage mapping | Validate both sides of D8/D9. Use one narrow projection module, including a reverse projection only where the internal orchestrator needs the native row type. Do not maintain a second handwritten selection model with different rules or emit both keys. |
| H4 | Current recordings | Regenerate the named entry-point recordings from the real offline API recorder using `IDHAZH_CAPTURE_PLANNER_RECORDINGS=1`, then unset it before normal checks. Use the existing [recording procedure](../docs/how-to/run-the-gates.md#independent-typescript-packages-and-services). Do not manufacture UUIDs, schema stamps, timings or success outcomes by patching a saved recording. |
| H5 | Retired fixtures and plans | Leave the old `tests/fixtures/contracts/feed-ingest-article-assessment/one-observation.json`, `tests/fixtures/contracts/feed-ingest-dispatch/one-article.json` and `tests/fixtures/contracts/feed-ingest-editorial-selection/one-article.json` outside the current-format cutover. Their shapes are already retired. Other matches in `TODO/20261012-65.2-summary-fidelity-judge-plan.md`, `TODO/20261101-diversity-aware-top-k-selection-plan.md`, `TODO/20261103-standardize-typescript-metadata-plan.md` and `TODO/unsupervised-topic-detection-event-clustering.md` are not new API authority. Do not perform a global word replacement through them. |
| H6 | Local checks | Inspect the shared selector with `npm run test:changed -- --list` from `frontend`; run native package/service checks and the row's focused cases per [the gate guide](../docs/how-to/run-the-gates.md#independent-typescript-packages-and-services). Record revision, selected inputs and results outside the repository. No Python development gate, external fetch or live data-writing workflow is added. |
| H7 | CI | Existing full merge-candidate CI is authoritative. A full local application suite is not required for this plan-only change or before every implementation push. A side-effecting manual workflow is not an acceptance gate. |
| H8 | Documentation | Implemented rules go to the owning living pages, not this plan alone: [identity](../docs/architecture/contracts/identity.md), [harvesting](../docs/architecture/sources/feed-harvesting.md), [operator APIs](../docs/architecture/sources/feed-operator-api.md), [native history](../docs/architecture/sources/planner-feed-history.md) and [ledger fields](../docs/reference/feed-planner-ledgers.md). Keep this file as the execution instrument, not a second permanent definition. |

## 1. Status Reckoner

Table I - Delivery rows

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | 1 | Preserve resource URLs before hashing and dispatch | - | A | PENDING | - | - | - |
| I2 | 2 | Capture a distinct identity for every article input | 1 | B | PENDING | - | - | - |
| I3 | 3 | Expose consistent article identities across APIs | 2 | C | PENDING | - | - | - |

## 2. Row #1 - Preserve resource URLs before hashing and dispatch

**Scope:** Implement D2/D13 and Table F for the native TypeScript path without changing Python or the independent experiment.

**Tasks:**
1. Replace destructive article and feed-document normalization with one standard-parser-based resource normalizer; keep the existing public-name and per-hop safety checks.
2. Remove D13's obsolete branch, configuration and planner dependency, including its transitive lock entries where no other beneficiary needs them.
3. Update affected canonical-URL validators and native schema metadata, then capture current offline recordings and update the owning docs.

**Files touched:**
- `TODO/20261104-align-typescript-article-identity-plan.md`
- `config/feed-ingest-plan.json`
- `packages/common-contracts/src/version.ts`
- `packages/common-contracts/src/schemas/config.schema.ts`
- `packages/common-contracts/src/schemas/candidate.schema.ts`
- `packages/common-contracts/src/schemas/discovered-article.schema.ts`
- `packages/common-contracts/src/schemas/selected-article.schema.ts`
- `packages/common-contracts/src/schemas/planner-operation.schema.ts`
- `packages/common-contracts/test/config.test.ts`
- `packages/common-contracts/test/article-identity-compatibility.test.ts`
- `packages/common-contracts/test/selected-article.test.ts`
- `services/feed-ingest-plan/package.json`
- `services/feed-ingest-plan/bun.lock`
- `services/typescript-api/bun.lock`
- `packages/feed-probe/bun.lock`
- `services/feed-ingest-plan/src/harvest-feeds/normalize-resource-url.ts` (new)
- `services/feed-ingest-plan/src/harvest-feeds/article-url.ts`
- `services/feed-ingest-plan/src/harvest-feeds/article-identity.ts`
- `services/feed-ingest-plan/src/harvest-feeds/feed-identity.ts`
- `services/feed-ingest-plan/src/harvest-feeds/http-request-target.ts` (delete when unused)
- `services/feed-ingest-plan/src/harvest-feeds/fetch-source.ts`
- `services/feed-ingest-plan/src/harvest-feeds/prepare-article.ts`
- `services/feed-ingest-plan/src/api/fetch-operation.ts`
- `services/feed-ingest-plan/src/api/feed-offers.ts`
- `services/feed-ingest-plan/src/api/document-state.ts`
- `services/feed-ingest-plan/src/run-health.ts`
- `services/feed-ingest-plan/test/article-url-cleanup.test.ts`
- `services/feed-ingest-plan/test/harvest.test.ts`
- `services/feed-ingest-plan/test/harvest-safety.test.ts`
- `services/feed-ingest-plan/test/harvest-recordings.ts`
- `services/feed-ingest-plan/test/article-source-outcome.test.ts`
- `services/feed-ingest-plan/test/article-failure-retention.test.ts`
- `services/feed-ingest-plan/test/file-baseline-recording.ts`
- `tests/fixtures/feed-ingest-plan/harvest-url-cleanup.json`
- `tests/fixtures/feed-ingest-plan/harvest-responses.json`
- `tests/fixtures/feed-ingest-plan/report-events.json`
- `tests/fixtures/feed-ingest-plan/entry-points/response.json`
- `tests/fixtures/feed-ingest-plan/entry-points/health.json`
- `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json`
- `tests/fixtures/feed-ingest-plan/entry-points/discovered-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/plan-runs.rows.json`
- `docs/architecture/contracts/identity.md`
- `docs/architecture/sources/feed-harvesting.md`
- `docs/architecture/sources/feed-operator-api.md`
- `docs/architecture/sources/planner-feed-history.md`
- `docs/how-to/run-feed-ingest-plan-test.md`

**Acceptance gates:**
- **Local:** H6; `bun run check` in common-contracts, ledger-file-writer, feed-ingest-plan, typescript-api and feed-probe after their affected local dependency graphs are current. In common-contracts, run `config.test.ts`, `article-identity-compatibility.test.ts` and `selected-article.test.ts`; in the planner run `article-url-cleanup.test.ts`, `harvest.test.ts`, `harvest-safety.test.ts`, `article-source-outcome.test.ts`, `file-baseline.test.ts` and `plan-entry-points.test.ts` in one native test invocation. Add the actual affected caller cases selected by H6, not an unconditional local full suite.
- **Behavior:** Named vectors cover meaningful queries, encoded ampersands/equal signs, duplicate keys, order, blank values, plus signs, fragments, mixed scheme spelling and serialized URL bounds. The recorder supplies exact query-bearing request URLs; a missing recording fails instead of contacting the web.
- **CI:** H7, including ordinary current-format round trips, native file integrity and composed-listener checks.

**Oracle:** A recorded pair differing only in a resource-identifying query produces distinct canonical addresses, digests and initial dispatched targets; the encoded-delimiter case remains distinct from the decoded two-parameter case, for both article and feed-document identity. This proves byte-level distinction, not whether two addresses tell the same story.

**Decisions**

Table J - Row 1 decisions

| ID | # | Decision | Authority |
| --- | --- | --- | --- |
| J1 | 1 | Implement all of Table F, not only removal of the final query-clearing assignment. The existing optional cleaner can also transform a resource before that assignment. | Architecture; current `article-url.ts:21-28` and `http-request-target.ts:5-16` |
| J2 | 2 | Include the TypeScript feed-document helper: `feed-identity.ts:27-34` repeats decoded-query string joining. Its identities need not match the still-unchanged Python helper. | Architecture; B1 and D2 |
| J3 | 3 | Use the native parser already present. No new dependency or tracking classifier is needed; accepting extra address records is safer than collapsing distinct required parameters. | Architecture; F1/F4 |
| J4 | 4 | Native full-row identity versions may change; historical field-based health support must not shrink as a side effect. | Native family contract; H1 |
| J5 | 5 | Form syntactic identity before a target-permission refusal. A forbidden target still has an address; an invalid URL does not. This preserves actionable refusal evidence without relaxing target checks or hashing malformed input. | Architecture; F1/F5 and D17 |

**Rejected alternatives**

Table K - Row 1 alternatives

| ID | # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- | --- |
| K1 | 1 | Retain aggressive cleanup and restore the original query afterward | A transformation can unwrap a URL or change more than the query; restoring bytes afterward can attach them to a different resource. | A documented library transformation contract plus adversarial vectors proving each allowed transformation before enabling it. | Architecture |
| K2 | 2 | Add a tracking-parameter denylist now | A name that is tracking on one site can identify a resource on another. It is not required for address correctness. | Source-specific equivalence rules, declared configuration and recordings for each enabled rule. | Architecture |
| K3 | 3 | Fix the Python cleaner in this PR | That would cross B1 and expand the publication/read-side contract. | A separate Python-and-publication PR, with its native and dependent gates. | Scope boundary |

## 3. Row #2 - Capture a distinct identity for every article input

**Scope:** Implement D3-D5, D6's candidate capture and D15 through existing native producers, current schemas, claims and terminal recording.

**Tasks:**
1. Declare the new scalar and input-bearing shapes before their producers; allocate once at the boundaries in Table G.
2. Carry the captured value through every native consumer, use the direct-input ordinal rule, and remove all later-stage fallback allocation or derivation.
3. Update terminal-row settlement, private diagnostics, current fixtures and current-format refusal tests together; do not add a durable input store.

**Files touched:**
- `TODO/20261104-align-typescript-article-identity-plan.md`
- `packages/common-contracts/src/index.ts`
- `packages/common-contracts/src/version.ts`
- `packages/common-contracts/src/create-candidate-id.ts` (new)
- `packages/common-contracts/src/schemas/primitives.ts`
- `packages/common-contracts/src/schemas/candidate.schema.ts`
- `packages/common-contracts/src/schemas/rejection.schema.ts`
- `packages/common-contracts/src/schemas/rejected-article.schema.ts`
- `packages/common-contracts/src/schemas/screened-article.schema.ts`
- `packages/common-contracts/src/schemas/planner-stage.schema.ts`
- `packages/common-contracts/src/schemas/planner-operation.schema.ts`
- `packages/common-contracts/src/schemas/article-entities.schema.ts`
- `packages/common-contracts/src/schemas/raw-document-failure.schema.ts`
- `packages/common-contracts/test/article-identity-compatibility.test.ts`
- `packages/common-contracts/test/planner-diagnostics.test.ts`
- `packages/common-contracts/test/rejection.test.ts`
- `packages/common-contracts/test/screened-article.test.ts`
- `packages/ledger-file-writer/src/row-identity.ts`
- `packages/ledger-file-writer/test/planner-recordings.ts`
- `packages/ledger-file-writer/test/planner-stored-file.test.ts`
- `packages/ledger-file-writer/test/rejected-article-replay.test.ts`
- `services/feed-ingest-plan/src/api/operation-context.ts`
- `services/feed-ingest-plan/src/api/stage-store.ts`
- `services/feed-ingest-plan/src/api/document-operations.ts`
- `services/feed-ingest-plan/src/api/document-response.schema.ts`
- `services/feed-ingest-plan/src/api/feed-offer-state.ts`
- `services/feed-ingest-plan/src/api/feed-offers.ts`
- `services/feed-ingest-plan/src/api/fetch-operation.ts`
- `services/feed-ingest-plan/src/api/parse-operation.ts`
- `services/feed-ingest-plan/src/api/collection-operation.ts`
- `services/feed-ingest-plan/src/api/collection-batch.ts`
- `services/feed-ingest-plan/src/harvest-feeds/harvest-types.ts`
- `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
- `services/feed-ingest-plan/src/harvest-feeds/prepare-article.ts`
- `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
- `services/feed-ingest-plan/src/harvest-feeds/record-rejection.ts`
- `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
- `services/feed-ingest-plan/src/harvest-feeds/document-observation.ts`
- `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
- `services/feed-ingest-plan/src/logging/progress-logger.ts`
- `services/feed-ingest-plan/src/recognize-article-entities.ts`
- `services/feed-ingest-plan/src/record-article-entities.ts`
- `services/feed-ingest-plan/src/record-harvest-failures.ts`
- `services/feed-ingest-plan/src/reporting/failure-evidence-markdown.ts`
- `services/feed-ingest-plan/src/run-health.ts`
- `services/feed-ingest-plan/src/run-feed-plan.ts`
- `services/feed-ingest-plan/src/screen-article-candidates/screening-input.ts`
- `services/feed-ingest-plan/src/screen-article-candidates/triage-gates.ts`
- `services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts`
- `services/feed-ingest-plan/src/curate-article-portfolio/select-diverse-articles.ts`
- `services/feed-ingest-plan/src/select-articles.ts`
- `services/feed-ingest-plan/test/article-entities-workflow.test.ts`
- `services/feed-ingest-plan/test/article-failure-retention.test.ts`
- `services/feed-ingest-plan/test/article-source-outcome.test.ts`
- `services/feed-ingest-plan/test/collection-recordings.ts`
- `services/feed-ingest-plan/test/collection-http.test.ts`
- `services/feed-ingest-plan/test/collection-work.test.ts`
- `services/feed-ingest-plan/test/curate.test.ts`
- `services/feed-ingest-plan/test/diverse-selection.test.ts`
- `services/feed-ingest-plan/test/early-age.test.ts`
- `services/feed-ingest-plan/test/file-baseline-recording.ts`
- `services/feed-ingest-plan/test/harvest.test.ts`
- `services/feed-ingest-plan/test/harvest-recordings.ts`
- `services/feed-ingest-plan/test/harvest-safety.test.ts`
- `services/feed-ingest-plan/test/observation-recordings.ts`
- `services/feed-ingest-plan/test/parser-deadline.test.ts`
- `services/feed-ingest-plan/test/partition-recordings.ts`
- `services/feed-ingest-plan/test/plan-engine.test.ts`
- `services/feed-ingest-plan/test/planner-diagnostics.test.ts`
- `services/feed-ingest-plan/test/report-native-evidence.test.ts`
- `services/feed-ingest-plan/test/triage.test.ts`
- `tests/fixtures/contracts/fetched-document/refused.json`
- `tests/fixtures/feed-ingest-plan/screening-cases.json`
- `tests/fixtures/feed-ingest-plan/report-events.json`
- `tests/fixtures/feed-ingest-plan/entry-points/response.json`
- `tests/fixtures/feed-ingest-plan/entry-points/health.json`
- `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json`
- `tests/fixtures/feed-ingest-plan/entry-points/discovered-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/plan-runs.rows.json`
- `docs/architecture/contracts/identity.md`
- `docs/architecture/sources/feed-operator-api.md`
- `docs/architecture/sources/feed-curation.md`
- `docs/architecture/sources/planner-run-diagnostics.md`
- `docs/architecture/sources/planner-feed-history.md`
- `docs/reference/diversity-metrics.md`
- `docs/reference/feed-planner-ledgers.md`

**Acceptance gates:**
- **Local:** H6; native checks in common-contracts, ledger-file-writer and feed-ingest-plan. In common-contracts run the four listed contract test files together. In the writer run `planner-stored-file.test.ts` and `rejected-article-replay.test.ts`. In the planner run `collection-http.test.ts`, `collection-work.test.ts`, `article-failure-retention.test.ts`, `article-entities-workflow.test.ts`, `diverse-selection.test.ts`, `triage.test.ts`, `plan-engine.test.ts` and `plan-entry-points.test.ts` together, adding changed caller cases from H6.
- **Contract:** Current captured-input reads retain their values; retired offer fields, old positional digest values and invalid UUID spellings fail. Feed refusals have no article candidate. Article observations, entity records and terminal rows agree with the captured input. Preserve existing claim/configuration/run checks and cancellation cleanup.
- **CI:** H7; actual native rejection write/readback and compaction retain distinct terminal inputs without fabricating a replay guarantee.

**Oracle:** Through the actual local API with recorded sources, two direct URLs admitted to the same collection and feed yield two retained results and two distinct captured input values; each value is unchanged through its fetch retries, parse and terminal diagnostics. Fresh submissions of one URL share the article key but not the input value. This does not certify restart recovery or exactly-once handling of repeated HTTP submissions.

**Decisions**

Table L - Row 2 decisions

| ID | # | Decision | Authority |
| --- | --- | --- | --- |
| L1 | 1 | Apply C1 and Table G. The existing fallback in `parse-operation.ts:127` assigns the same position to unrelated direct inputs; the collection stores successful results under that occurrence value. Keeping the established name does not mean keeping that allocation algorithm. | Architecture; `parse-operation.ts:210` |
| L2 | 2 | Capture at admission rather than independently inside preparation, fetch failure and parsing. Ordinary parsing remains one-shot and no new request replay is introduced. | Architecture; existing live-document contract in `feed-operator-api.md` |
| L3 | 3 | Stop validating occurrence identity by recomputing the previous positional digest. Validate the new scalar plus its captured membership and ownership. Feed positions remain provenance, not identity. | Architecture; D3/D4 and G5 |
| L4 | 4 | Update the native terminal column's type and its settlement validation in the same PR, without renaming the column. Do not send a UUID into a schema still expecting a SHA digest. | Native writer contract; D5 |
| L5 | 5 | Preserve G8 explicitly; fresh allocation is not a promise of the same representative after a new capture. | Architecture; existing exact-score tie mechanism |

**Rejected alternatives**

Table M - Row 2 alternatives

| ID | # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- | --- |
| M1 | 1 | Identify each input by its article key | Two feed entries or direct requests for one address are separate processing/accounting inputs. | Losing per-input failures and provenance, or adding another discriminator later. | Architecture |
| M2 | 2 | Hash a tagged run/feed/position tuple for every input | Direct requests have no original feed position. A fresh request still needs an allocated sequence or token. | A retained direct-submission discriminator, a specified tuple encoding and separate validation; useful only if reconstruction from that tuple is required. | Architecture |
| M3 | 3 | Reuse an event or operation ID | That makes event emission or a later fetch operation change the identity of the admitted input. | An additional durable mapping and stricter occurrence-reuse contract; neither is needed for Table G. | Architecture |
| M4 | 4 | Persist a restart journal to retain allocation | It would contradict the current live-only API and cross B5. | Storage, retention, claim/reopen and lost-response contracts plus failure tests. | Scope boundary |

## 4. Row #3 - Expose consistent article identities across APIs

**Scope:** Complete D6-D9, D18/D19 and Table E, including consistent article references, optional readable response URLs and strict API/storage projection.

**Tasks:**
1. Split feed and article response identities, add the captured identities to parse results, and correct generic document/observation naming.
2. Introduce the one projection in H3 for selection/partitioning and consume it in the real orchestrator.
3. Cut over the combined response, CLI/saved response, assignments and verifier together.
4. Implement D18/D19 from the existing selected rows, without a new URL list, ledger field or lookup. Preserve current selection and persistence behavior; update current recordings and the living API reference.

**Files touched:**
- `TODO/20261104-align-typescript-article-identity-plan.md`
- `config/feed-ingest-plan.json`
- `packages/common-contracts/src/version.ts`
- `packages/common-contracts/src/schemas/config.schema.ts`
- `packages/common-contracts/src/schemas/planner-operation.schema.ts`
- `packages/common-contracts/src/schemas/planner-response.schema.ts`
- `packages/common-contracts/src/schemas/raw-document-failure.schema.ts`
- `packages/common-contracts/test/config.test.ts`
- `packages/common-contracts/test/planner-diagnostics.test.ts`
- `packages/common-contracts/test/metadata-flow.test.ts`
- `services/feed-ingest-plan/src/api/article-identity-projection.ts` (new)
- `services/feed-ingest-plan/src/api/plan-request.ts`
- `services/feed-ingest-plan/src/api/document-response.schema.ts`
- `services/feed-ingest-plan/src/api/stage-response.schema.ts`
- `services/feed-ingest-plan/src/api/routes/stages.route.ts`
- `services/feed-ingest-plan/src/api/fetch-operation.ts`
- `services/feed-ingest-plan/src/api/parse-operation.ts`
- `services/feed-ingest-plan/src/api/document-state.ts`
- `services/feed-ingest-plan/src/api/feed-offers.ts`
- `services/feed-ingest-plan/src/harvest-feeds/document-observation.ts`
- `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
- `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
- `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
- `services/feed-ingest-plan/src/run-feed-plan.ts`
- `services/feed-ingest-plan/scripts/feed-ingest-plan-verification.ts`
- `services/feed-ingest-plan/test/operation-logging.test.ts`
- `services/feed-ingest-plan/test/harvest.test.ts`
- `services/feed-ingest-plan/test/parser-deadline.test.ts`
- `services/feed-ingest-plan/test/article-source-outcome.test.ts`
- `services/feed-ingest-plan/test/planner-diagnostics.test.ts`
- `services/feed-ingest-plan/test/plan-api.test.ts`
- `services/feed-ingest-plan/test/plan-entry-points.test.ts`
- `services/feed-ingest-plan/test/plan-cli.test.ts`
- `services/feed-ingest-plan/test/plan-engine.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-report.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-http-client.test.ts`
- `services/feed-ingest-plan/test/collection-http.test.ts`
- `services/feed-ingest-plan/test/collection-recordings.ts`
- `services/feed-ingest-plan/test/file-baseline-recording.ts`
- `services/typescript-api/test/api-composition.test.ts`
- `tests/fixtures/contracts/fetched-document/refused.json`
- `tests/fixtures/feed-ingest-plan/report-events.json`
- `tests/fixtures/feed-ingest-plan/entry-points/response.json`
- `tests/fixtures/feed-ingest-plan/entry-points/health.json`
- `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json`
- `tests/fixtures/feed-ingest-plan/entry-points/discovered-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json`
- `tests/fixtures/feed-ingest-plan/entry-points/plan-runs.rows.json`
- `docs/architecture/contracts/identity.md`
- `docs/architecture/sources/feed-operator-api.md`
- `docs/architecture/sources/feed-plan-runner.md`
- `docs/architecture/sources/feed-partitioning.md`
- `docs/architecture/sources/planner-run-diagnostics.md`
- `docs/reference/feed-planner-ledgers.md`
- `docs/reference/typescript-api-server.md`
- `docs/how-to/run-feed-ingest-plan-test.md`

**Acceptance gates:**
- **Local:** H6; native checks in common-contracts, feed-ingest-plan and typescript-api. In common-contracts run `config.test.ts`, `planner-diagnostics.test.ts`, `metadata-flow.test.ts` and `article-identity-compatibility.test.ts`; in the planner run `plan-api.test.ts`, `plan-entry-points.test.ts`, `plan-cli.test.ts`, `collection-http.test.ts`, `plan-engine.test.ts`, `file-baseline.test.ts`, `feed-ingest-plan-outputs.test.ts` and `operation-logging.test.ts` together; in the composed server run `api-composition.test.ts`. Include other actually changed caller cases from H6.
- **Contract:** Check each Table E branch. Reject retired public keys and ambiguous feed/article combinations. D18 accepts typed API booleans only; test missing, explicit true/false, config override, CLI bare/value forms and invalid/repeated controls. D19 validates all-or-none URL presence, exact URL/hash agreement, partial and empty outcomes. Toggle the option over the same captured native result in lower-tier tests: chosen rows, ranks, assignments and ledger data must not change.
- **Bounded integration:** Reuse the existing successful API entry-point journey with D18 enabled and the existing CLI journey with its default disabled; assert the actual saved JSON output as well as the response. Do not add a second whole-planner run for every flag/state combination. Preserve existing reference claims, body privacy and foreign publication fixture reads.
- **CI:** H7; API/CLI responses, requested URLs, actual Parquet and selected text reconcile through H3. URL inclusion introduces no source fetch, Parquet lookup or routine progress/log output.

**Oracle:** The existing recorded API journey exposes one consistent article value and, when requested, the exact readable URL from each selected row; response assignments map bijectively and in order to native Parquet and artifact entries. The existing CLI journey preserves omission by default. Feed results never label a feed as an article, and no new public item identifier appears. This proves response/storage agreement, not semantic deduplication or Python normalization parity.

**Decisions**

Table N - Row 3 decisions

| ID | # | Decision | Authority |
| --- | --- | --- | --- |
| N1 | 1 | Apply E6 as well as the per-article endpoints: `PlannerRunResponseSchema` and `summarizePlan` also expose article-address identities. | Architecture; `planner-response.schema.ts:48-51` and `run-feed-plan.ts:409-420` |
| N2 | 2 | Keep D10/D11. The former is a native storage boundary; the latter is a foreign publication read contract, not an alternate API name. | Architecture; `publication-evidence.ts:9-19` |
| N3 | 3 | The real article-entity key retains D1's meaning; only generic document identity receives D6's name. Do not blindly replace every occurrence of the existing article field. | Architecture; D6/D15 |
| N4 | 4 | Keep request links authoritative. Returning resource identity does not make copied identifiers a new way to authorize parsing or persistence. | Existing operator ownership contract; E4/E7 |
| N5 | 5 | Use the existing assignments array for D19, including when partitioning is disabled and worker assignment is null. Selected metadata and its JSON artifact already contain the readable URL; `summarizePlan` currently drops it. No external fetch or Parquet correlation is needed. | `selected-article.schema.ts:32-35,79-81`; `run-feed-plan.ts:410-420` |
| N6 | 6 | Put D18's default under native response settings, not the external workflow-reporting adapter. Resolve once and carry the value through the real API, CLI and saved-response writer. Do not add a run-ledger column for a display choice. | `FeedWorkflowReportingConfigSchema` is external reporting; `PlanRunRowSchema` retains execution results |
| N7 | 7 | Default D18 off to avoid enlarging every summary and unnecessarily copying query strings. Enabling it is a projection over the same selected data, not another selection path. Its schema description names removal of the option and conditional projection together if readable URLs become mandatory or unsupported. | Architecture; D18/D19 |

**Rejected alternatives**

Table O - Row 3 alternatives

| ID | # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- | --- |
| O1 | 1 | Return storage and API spellings together | It preserves the ambiguity and creates two fields that can disagree. | An alias lifecycle and validation on every reader, with no new capability. | Architecture |
| O2 | 2 | Rename every retained URL column and foreign public identifier | Naming alone does not require changing all stored and foreign contracts. | The wider B1-B3 producer/read-side migration and dependent gates. | Scope boundary |
| O3 | 3 | Convert article addresses to allocated UUIDs | Allocation does not decide which URLs are equal and introduces a lookup requirement. | An identity allocator, storage, alias evidence and concurrency/recovery rules while retaining URL keys for deduplication. | Architecture |
| O4 | 4 | Use the third address-key spelling named in D9 | It identifies no new thing and weakens consistency with article-returning APIs. | Another request/response vocabulary change and updated clients, without new identity behavior. | Architecture |
| O5 | 5 | Always return the readable URL in combined summaries | Simple, but increases every response and copies query strings when they were not requested. | Make the field required in the public contract and accept the additional output/exposure for every run. | Architecture |
| O6 | 6 | Add a parallel URL array or a lookup registry | A parallel array adds another order-alignment invariant; a registry adds storage and reads when the selected rows already have the pair. | Cross-array validation or a registry writer, retention and lookup contract, instead of one conditional field on existing assignments. | Architecture |

## See also

- [Plan authoring](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Native API contract](../docs/architecture/sources/feed-operator-api.md)
- [Native ledger fields](../docs/reference/feed-planner-ledgers.md)
- [Focused gate commands](../docs/how-to/run-the-gates.md#independent-typescript-packages-and-services)
