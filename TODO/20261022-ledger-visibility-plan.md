# Compact ledgers without site rebuilds

**Last Updated**: 2026-10-22
**Level**: 5 - approved design; execution authorized by kumarsnaveen on 2026-10-22 UTC.

## 0. Operating contract

**Table A - Operating contract**

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Make every explicitly enabled ledger discoverable and queryable from its committed compact indexes without waiting for a Pages build. |
| A2 | Hard scope - in | Finish the staging-script rename; add explicit explorer consent; derive one validated lookup; read existing compact indexes and Parquet directly; remove browser raw discovery and build-time raw listings; stop telemetry-only commits from publishing Pages; update affected documentation and tests. |
| A3 | Hard scope - out | Table B states the exclusions and their costs. |
| A4 | Flattening | Flatten the lookup used by code only. Preserve family groups in `config/ledgers.json`, family-wide lifecycle controls, backend ledger names, storage paths and Parquet row structures. Owner ruling: kumarsnaveen, 2026-10-22 UTC. |
| A5 | Data source | Read compact data only. New raw files wait for packing. Use the existing `ledger.archive_base_url` as the direct repository source, not merely as an older-data fallback. No directory API or new raw manifest. Owner ruling: kumarsnaveen, 2026-10-22 UTC. |
| A6 | Dates | Preserve the existing configurable 365-day custom-date reach and existing preset shortcuts. The draft's proposed 90-day query cap is rejected. Owner ruling: kumarsnaveen, 2026-10-22 UTC. |
| A7 | Consent migration | Add the mandatory field defined in Table F, seed it from exact membership in the existing publication list, migrate all consumers, then delete the old list. Registration, consent and available data remain separate facts. |
| A8 | Persisted shapes | Change authored configuration only. Do not change `CompactIndex`, `CompactEntry`, Parquet envelopes, row contracts, raw writer formats or retention. Configuration follows the exemption in [CLAUDE.md section 11](../CLAUDE.md#11-schema-versioning). |
| A9 | ESCALATE triggers | Stop for a storage move or rename; changed family lifecycle or retention; a new or changed persisted payload; additional publication consent; raw discovery or a directory API; credentials or another destination; loss of the approved date range; an unresolved conflict with an owning document; or an execution-contract escalation. Return the finding and options to the owner before proceeding. |
| A10 | Chosen strategy | Keep the grouped registry as authority; derive a flat catalog; use the existing three compact indexes as the complete file-discovery mechanism. Owner scope rulings are above; Fowler's construction ruling is recorded in Table H. |
| A11 | Existing work | The authoring checkout contains uncommitted staging-script rename edits. They are not delivered by this plan commit and do not make a row DONE. Adopt and verify them under Row 1 without reverting unrelated work. |
| A12 | Execution | Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A13 | PR phases | Each reckoner row is one PR outcome. The rows are serial because they change shared readers and their authority; the pool width does not permit overlapping edits. Update each surface's owning doc with its code, then complete the bounded documentation reconciliation in Row 6. |

**Table B - Exclusions and their costs**

| Id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Raw-file discovery, new raw-day manifests and GitHub directory APIs | The explorer cannot show a new row before packing commits it. | An owner decision that pre-packing freshness is worth writer coordination or API limits. |
| B2 | Flattening registry JSON or moving nested ledger folders | Family grouping and nested physical paths remain. | A separate migration decision covering family controls and old-path compatibility. |
| B3 | Making every console page a live repository reader | Existing non-explorer panels retain their staged or build-time snapshots until another legitimate site publication. | A separate request to change those panels' data source and freshness. |
| B4 | Removing all compact copies from Pages | Copies used by existing console panels still occupy site bytes. Removing raw copies does not remove this cost. | Migration of those readers, with their own coverage and transport checks. |
| B5 | Rewriting stored data or removing historical raw-index contracts | Historical contract readers and fixtures may remain, but no browser raw-discovery path remains. | A separately justified contract-retirement change. |
| B6 | A new browser fixture matrix, extra journeys or UI redesign | Coverage is representative, not every ledger/state/layout combination. | A distinct failure mechanism or an owner-approved design change. |

## 1. Status Reckoner

**Table C - PR phases**

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Complete the publication-staging rename | - | A | DONE | ledger-staging-rename | - | Ledger staging rename |
| C2 | 2 | Declare explorer consent and the validated catalog | 1 | B | DONE | ledger-consent-catalog | - | Ledger consent catalog |
| C3 | 3 | Bind every frontend ledger path to its catalog | 2 | C | PENDING | - | - | - |
| C4 | 4 | Read compact repository data directly in the explorer | 3 | D | PENDING | - | - | - |
| C5 | 5 | Remove raw staging and duplicate publication policy | 4 | E | PENDING | - | - | - |
| C6 | 6 | Reconcile documentation with the delivered behavior | 5 | F | PENDING | - | - | - |

## 2. Row #1 - Complete the publication-staging rename

- **Scope:** Finish the approved script rename and its live references without changing staged output.
- **Files touched:**
  - `frontend/package.json`
  - `frontend/scripts/copy-visuals.mjs` (rename source)
  - `frontend/scripts/stage-publication.mjs` (rename destination)
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/scripts/raw-listed-through.mjs`
  - `frontend/scripts/payload-ceilings.mjs`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/lib/payload/project.ts`
  - `frontend/tests/asset-base.spec.ts`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `frontend/tests/support/feed-ledgers.ts`
  - `backend/idhazh/contracts/digest_view.py`
  - `docs/architecture/publishing/console-payloads.md`
  - `docs/architecture/publishing/console-site-size.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/architecture/publishing/the-served-day-and-the-documents-that-stopped-being-written.md`
  - `docs/architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
  - `TODO/20260906-data-growth-research.md`
  - `TODO/20260910-25-placement-plan.md`
  - `TODO/20261020-66-feed-ingest-plan.md`
- **Acceptance gates:** Locally, inspect the shared selector from `frontend/` with `npm run test:changed -- --list`; use one selected run covering `ledger-copy.spec.ts` and `asset-base.spec.ts`, plus `node --test scripts/tests/test-scope.test.mjs`. Confirm no operational reference invokes the old filename. Preserve dated historical statements as history. CI supplies the merge-candidate checks; do not run a second local full suite.
- **Oracle:** The existing real staging fixture produces the same paths and payload/Parquet bytes before and after the rename, with only the listing's actual staging instant excluded from metadata comparison. This proves a rename, not direct-repository freshness.

**Table D - Decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| D1 | Keep one script owning cleanup and the generated static tree; payload selection and ledger selection already have their own modules. Do not split it. | Supplied design; verified script and package entry point. |
| D2 | Treat inherited edits as candidate work, not delivered work. Stage only this row's actual changes after verification. | Owner's author-only request; [git hygiene](../CLAUDE.md#8-git-hygiene). |
| D3 | Update current code/doc pointers found by the filename search. Do not rewrite historical evidence merely to erase an old spelling. | [Documentation structure](../docs/reference/documentation-structure.md). |

**Table E - Rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Split public-payload and ledger staging into new commands | No independent caller needs the split, and cleanup still owns one output tree. | Another command boundary, package wiring and output-parity coverage. | Supplied design. |
| E2 | Commit all inherited edits with the plan | They are implementation work and have not been accepted as a completed row. | Verification of the code change and explicit implementation authorization. | Current owner request. |

## 3. Row #2 - Declare explorer consent and the validated catalog

- **Scope:** Declare explicit explorer consent and use one validated flat catalog while preserving family ownership and current data delivery.
- **Files touched:**
  - `config/ledgers.json`
  - `backend/idhazh/contracts/ledgers.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_frontend_vocabularies.py`
  - `frontend/src/lib/data/ledger-catalog.ts` (new)
  - `frontend/src/lib/data/configured-catalog.ts` (new)
  - `frontend/src/lib/console/explorer/registry.ts`
  - `frontend/src/lib/console/explorer/LedgerList.svelte`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/scripts/ledger-prefixes.mjs`
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/scripts/test-groups.ts`
  - `frontend/tests/ledger-catalog.spec.ts` (new)
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/console-data-explorer-examples.spec.ts`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/publishing/data-explorer-state.md`
- **Acceptance gates:** Locally, use the shared selector for the new catalog logic spec and existing ledger-copy/example specs; run the named registry and frontend-binding backend tests and applicable lint/type checks. Add the spec to the explicit group inventory. Use the named committed registry and bounded generated mutations, not a new fixture matrix. CI runs the full applicable suites once on the merge candidate.
- **Oracle:** Exact-set parity holds between the existing publication list and consented raw-and-compact entries, while omitted/non-boolean consent, duplicate names and unsafe/overlapping prefixes are refused. This proves migration policy and validation, not data availability.

**Table F - Configuration and catalog decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | Add `publish_to_data_explorer` to every `LedgerEntry` as a required strict boolean with no default. Seed true exactly for the current `ledger.published` members and false for every other registered entry. Do not turn a member count into an invariant. | Supplied design; owner approved conversion with no expansion of consent. |
| F2 | True permits explorer offering and querying; false does neither. True does not assert that files exist. Reject true on a grain the compact reader cannot query. A paused or retired family may still have readable, consented historical data. | Separation of registration, consent, lifecycle and availability. |
| F3 | `parseLedgerCatalog(payload: unknown): LedgerCatalog` is pure. The catalog exposes read-only `families`, derived `entries`, `get(name)` and `require(name)`. Entries carry `name`, normalized `prefix`, `grain` and the consent field; family metadata remains grouped. Normalize a checked segment list to a relative POSIX prefix once. | Fowler construction ruling, 2026-10-22 UTC. |
| F4 | Validate family metadata, real onboarding dates, name/grain vocabularies, required fields, prefix grammar, duplicate families/ledgers, family-to-prefix agreement, raw-and-compact prefix endings and prefix overlap before building the lookup. Never infer a folder from an unknown name. Hold frontend field use and vocabularies to the backend models with named binding tests. | Existing `LedgersConfig` validators; [registry contract](../docs/architecture/contracts/ledger-registry.md). |
| F5 | Keep family lifecycle, claim protection, the backend `LedgerName` enum and `paths.py`'s already-derived registry unchanged. Flattening adds no second persisted registry and moves no data. | Owner's flat-lookup-only ruling; existing family-status rationale. |
| F6 | Keep the old publication list only as an explicit migration bridge. Build selection reads consent and refuses disagreement with that list; Row 5 removes the bridge after every consumer has moved. | Reader-before-removal migration; removal condition is Row 5. |
| F7 | `ledger-prefixes.mjs` and the browser adapter reuse the pure parser rather than independently validating prefixes. `configured-catalog.ts` imports the named committed JSON by relative path with a JSON import attribute, then invokes the same parser; it imports no browser or server-only module. | Fowler construction ruling; native Node and Vite consumers. |
| F8 | Filter offered examples and selected ledgers by consent, and remove a newly disabled selection with a notice rather than running it invisibly. Do not describe this UI policy as secrecy: the repository is public. | Supplied consent design; existing saved-question and link behavior. |

**Table G - Rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Flatten the authored JSON and repeat status on each ledger | A family-wide pause could become contradictory per-ledger settings. | A separately approved config migration and a replacement for the single family control. | Owner chose runtime flattening; existing documented rationale. |
| G2 | Default missing consent to false | A forgotten declaration would load instead of identifying the missing decision. | An owner reversal of the explicit required-field design. | Supplied design. |
| G3 | Determine which ledgers exist by scanning state folders | It misses registered ledgers before their first successful write and grows with stored history. | A replacement for registry completeness and claim protection, not merely a faster scan. | [Registry design rationale](../docs/architecture/contracts/ledger-registry.md#design-rationale). |

## 4. Row #3 - Bind every frontend ledger path to its catalog

- **Scope:** Replace handwritten frontend names and folder mappings with the validated catalog without changing which existing data source answers a request.
- **Files touched:**
  - `frontend/src/lib/data/ledger-catalog.ts`
  - `frontend/src/lib/data/configured-catalog.ts`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/ledger-reach.ts`
  - `frontend/src/lib/data/page-keeper.ts`
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/data/ledger-columns.ts`
  - `frontend/src/lib/data/ledger.ts`
  - `frontend/src/lib/server/ledger-disk.ts`
  - `frontend/src/lib/console/explorer/registry.ts`
  - `frontend/src/lib/console/explorer/column-groups.ts`
  - `frontend/src/lib/console/explorer/ColumnList.svelte`
  - `frontend/src/lib/console/recording.ts`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/tests/ledger-catalog.spec.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/ledger-lifecycle.spec.ts`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/similarity-ledgers.spec.ts`
  - `frontend/tests/explorer-column-groups.spec.ts`
  - `frontend/tests/console-data-explorer-address.spec.ts`
  - `frontend/tests/support/door-page/door.ts`
  - `frontend/tests/support/explorer-page/explorer.ts`
  - `frontend/tests/support/ledger-lifecycle.ts`
  - `backend/tests/contracts/test_frontend_index_shapes.py`
  - `backend/tests/contracts/test_frontend_vocabularies.py`
  - `backend/utilities/council_matrix.py`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
- **Acceptance gates:** Locally, select the affected logic specs and named binding tests through the gate guide, including plain-Node recording/disk imports and nested-prefix reads; run type checks. Verify each keeper construction site and every changed path-helper caller. The existing raw/two-source tests still pass here because Row 4, not this row, changes explorer data behavior. CI supplies full coverage.
- **Oracle:** For each ledger in the named registry, catalog-based paths equal the previous valid paths, while a generated safe name absent from the old compiled list resolves only through its supplied catalog. This proves path compatibility and dynamic membership, not repository transport.

**Table H - Reader construction decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | Add required `readonly catalog: LedgerCatalog` to `PageKeeper`; construct it with `pageKeeper(source, openEngine, catalog)`. Do not mutate its catalog after construction or use an ambient runtime registry. Preserve the existing name-taking facade functions. | Fowler construction ruling, 2026-10-22 UTC. |
| H2 | Frontend `LedgerName` becomes a string whose validity is catalog membership. Resolve it before I/O; preserve the API's explicit invalid-request handling. Remove `LEDGER_NAMES` and `LEDGER_FOLDERS` only after every consumer has migrated. Backend enum validation remains closed. | Fowler ruling; owner approved removal of duplicate lookups, not backend registration. |
| H3 | Pure folder, index, data-path and fault-path helpers take the catalog explicitly. `ledgerFolder(catalog, name)` requires the registered entry and returns its normalized prefix. Other paths compose checked period/date literals with that prefix. | Existing path grammar; Fowler ruling. |
| H4 | Ordinary panel and disk keepers receive the configured catalog. The explorer receives the catalog fetched for its source. All use the same parser, not separate hardcoded lists. | Fowler ruling. |
| H5 | `setAsideSentence` accepts an optional trailing catalog, defaulting only to `configuredCatalog` for normal panel callers. The explorer always supplies its session catalog. This keeps recording helpers usable in plain Node without `$app` or browser globals. | Fowler ruling. |
| H6 | Link parsing, stored selections, examples and column grouping use names from the relevant catalog. Column grouping receives that catalog explicitly; it does not decide ledger identity from arbitrary dotted text. | Verified consumers of the old name array. |
| H7 | Keep index locations computed: `compact/<registered-prefix>/index/<period>.json`, with the three existing periods. Add no per-ledger index URL, filename override or generated registry file. | Existing `CompactIndex` layout; owner-provided feed-health examples. |
| H8 | The council matrix's own `LEDGER_NAMES` is a different, local set and is not renamed. Search hits in earlier plans are updated only where they remain instructions to future work; historical references stay historical under Row 6. | Verified search distinguishes the backend utility from the retired frontend exports. |

**Table I - Rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Generate another compiled frontend ledger-name union | An old page would still reject a newly registered name. | Another generated artifact and a site rebuild on registration. | Fowler ruling; dynamic-discovery intent. |
| I2 | Pass unvalidated paths or cast fetched names into the old union | It hides the actual membership and folder checks. | Explicit validation and a type model that admits current registry names. | Fowler ruling. |
| I3 | Thread a separate registered entry through every facade call | The keeper already binds source, cache and request lifetime. | Wider caller churn without another reader capability. | Fowler construction ruling. |

## 5. Row #4 - Read compact repository data directly in the explorer

- **Scope:** Make the explorer read its current consented registry and compact files directly, without a site rebuild, raw discovery or silent source fallback.
- **Files touched:**
  - `CLAUDE.md`
  - `config/appearance.json`
  - `backend/idhazh/contracts/knobs/console.py`
  - `backend/idhazh/contracts/knobs/ledger.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/test_appearance_config.py`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/lib/data/ledger.ts`
  - `frontend/src/lib/data/page-keeper.ts`
  - `frontend/src/lib/data/fetched-bytes.ts`
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/data/ledger-columns.ts`
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `frontend/src/lib/data/raw-day-index.ts` (remove browser reader)
  - `frontend/src/lib/data/site-window.ts`
  - `frontend/src/lib/console/explorer/registry.ts`
  - `frontend/src/lib/console/explorer/LedgerList.svelte`
  - `frontend/src/lib/console/explorer/status.ts`
  - `frontend/src/lib/console/explorer/days-read.ts`
  - `frontend/src/lib/console/waiting.ts`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/src/routes/console/data-explorer/+page.ts`
  - `frontend/src/app.d.ts`
  - `frontend/vite.config.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/ledger-lifecycle.spec.ts`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/appearance-config.spec.ts`
  - `frontend/tests/console-waiting.spec.ts`
  - `frontend/tests/console-data-explorer-address.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `frontend/tests/explorer-boundary.spec.ts`
  - `frontend/tests/support/explorer-page/explorer.ts`
  - `frontend/tests/support/ledger-lifecycle.ts`
  - `frontend/tests/support/panel-drivers/pipelines.ts`
  - `backend/tests/contracts/test_frontend_index_shapes.py`
  - `docs/architecture/publishing/data-explorer-state.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/how-to/query-a-ledger-from-the-console.md`
- **Acceptance gates:** Locally, use one shared-selector run for changed logic and the existing explorer journey, plus named config/copy-binding tests and type checks. Keep file selection, invalid consent, lost/empty periods, exact byte limits and stale-view cleanup at logic/integration tier using real Parquet. Extend the existing browser journey, not the browser inventory. Perform the section 12 integrated-browser smoke and a representative operator-surface review before merge; Susan assesses the changed surface, not a new layout matrix. CI supplies full-suite and transport-boundary checks.
- **Oracle:** Keep one compiled site unchanged, update only a generated repository fixture's registry and packed data, then Refresh and run the existing journey: it offers a newly consented runtime name and returns its new rows without a rebuild or raw/API request. This proves decoupling from Pages, not an immediate global freshness guarantee from GitHub's caches.

**Table J - Direct-read contract**

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Keep `ledger.archive_base_url` in committed `config/idhazh.json`. With a non-empty value, use it as the explorer's sole repository source for both `config/ledgers.json` and `state/compact/<prefix>/...`, including newly packed days. The current raw-content origin remains unchanged. | Owner chose direct existing indexes, not a second manifest. |
| J2 | An explicitly empty archive base retains intentional site/local-fixture mode. A repository error must not switch to an older site copy. Normal `slice()` and `ledgerReach()` panel readers keep their existing source. | Fowler ruling; no silent fallback or unrequested panel migration. |
| J3 | Read the registry on open and Refresh from the chosen source with no HTTP-cache reuse. Build-time configuration supplies knobs and the destination, not the explorer's current ledger membership. Remove `__PUBLISHED_LEDGERS__` from explorer selection. Validate consent again for every request, not only in the list. | Current build constant and same-origin registry would otherwise preserve the visibility gap. |
| J4 | Each selected ledger starts with its existing daily, monthly and yearly indexes. Use the existing coarsest-file selection, one coverage per UTC day, and filter wider files on `covers`. No daily directory probing, no backward filename guesses, no new index-location fields. | Verified compaction and query contracts. |
| J5 | The explorer has one catalog and one compact source per read session. Refresh fences in-flight old work, drops its keeper/catalog together and fetches new metadata; it never executes SQL automatically. Direct repository Parquet uses fetched buffers only, with no engine-readable source address, and is re-fetched without HTTP-cache reuse after Refresh even when row count and file size are unchanged. | Existing keeper lifetime and transport boundary; Fowler ruling. |
| J6 | Track created ledger views per engine, independently of the current catalog. Drop previously owned views before preparing the current selection, including removed, disabled and deselected names. Keep request serialization. | Verified old name-array view cleanup would miss a vanished entry. |
| J7 | Fetch and classify the three indexes: all absent means no compact record is available; a partial set, malformed index, wrong ledger/period, missing named file or byte mismatch produces a named failure, never a quiet result. Preserve explicit empty and lost periods and set-aside reporting. Metadata changing during a read may require Refresh; do not invent a consistent answer. | Existing index contract and direct-source failure handling. |
| J8 | Remove raw planning and the old site/archive split from explorer readers. Retire `RawListedThrough`, `ArchiveTier`, `UnansweredDays`, raw-only `unpackedDays`, their browser controls/notes and tests of the removed behavior. Keep shared compact gap, cutoff, date-bound and boundary coverage. `siteKeepsFrom` remains for staging; remove `siteMayHaveTrimmed` after its final consumer moves. | Owner chose compact-only; removal is a behavior change, not just a rename. |
| J9 | Keep the existing configurable byte, row, SQL and date limits. Add `console.explorer_max_files`, a positive integer defaulting to 128 unique Parquet candidates per question, exposed as `max_files` and passed as `AskOptions.maxFiles`. Count empty-view source files too; apply the shared preflight before query or automatic column-rail data fetches. Add the runtime refusal `{ kind: 'too-many-files', files, max }` and a named consent refusal `{ kind: 'ledger-not-enabled', ledger }`; neither changes a persisted payload. Reuse selection and pricing rather than adding another discovery pass. | Supplied design's file-count bound; current query limits; owner retained the 365-day reach. |
| J10 | Offer a consented ledger even when it has not packed data yet, with an honest unavailable/not-packed result. State that the newest data waits for packing. Do not claim that a missing file proves zero rows, that every selected day is available, or that the current UTC day has finished packing. | Owner accepted the packing delay. |
| J11 | Update CLAUDE.md section 4's public-directory-only wording in this same PR to permit the existing committed-config origin for registered, consented compact payloads. Preserve static publication, no runtime backend, sanitization and operator-controlled destinations. Record the owner-directed exception with its date and name in the owning architecture rationale. | Owner's direct-repository decision; existing archive reads already conflict with that literal wording. |
| J12 | No new dependency, authentication flow, polling service, generated global file list or extra browser journey is needed. The existing engine and read-only statement boundary stay intact. | Verified existing fetch, catalog and query-engine components. |

**Table K - Rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Make repository reads an older-date fallback only | It cannot find newer data or a ledger absent from the site's compiled list. | A primary direct-source path, which this row supplies. | Verified existing `planLedger` predicate and owner intent. |
| K2 | Find raw Parquet by counting backward through dates | Dates do not reveal the generated writer filenames. | Committed fresh listings or a rate-limited directory API, both declined for this plan. | Owner's compact-only decision. |
| K3 | Add a new manifest or explicit index URLs to each entry | The prefix and existing period grammar already determine every compact index address. | Another stored shape or repeated locations to validate and keep synchronized. | Owner's index-first proposal; Fowler ruling. |
| K4 | Reduce every question to 90 days | The compact-only design does not need a raw-folder scan, and this removes existing date access. | Owner approval to give up older custom dates. | Owner retained the current 365-day range. |
| K5 | Fall back to the site silently on a repository error | It can answer with stale data while appearing fresh. | Explicit approval for a visible degraded mode and separate coverage. | Fowler ruling; project error-handling contract. |

## 6. Row #5 - Remove raw staging and duplicate publication policy

- **Scope:** Delete obsolete raw staging and the old allowlist while ensuring telemetry-only data commits do not publish Pages.
- **Files touched:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/knobs/ledger.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/cli.py`
  - `backend/utilities/publish_decision.py`
  - `backend/utilities/build_canary_day.py`
  - `backend/utilities/digest_assemble.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/contracts/test_panel_queries.py`
  - `backend/tests/workflows/test_publish_decision.py`
  - `backend/tests/test_canary_packing.py`
  - `frontend/scripts/stage-publication.mjs`
  - `frontend/scripts/build-canary.mjs`
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/scripts/ledger-prefixes.mjs`
  - `frontend/scripts/payload-ceilings.mjs`
  - `frontend/scripts/bundle-gate.mjs`
  - `frontend/scripts/raw-listed-through.mjs` (remove)
  - `frontend/scripts/test-groups.ts`
  - `frontend/tests/raw-listed-through.spec.ts` (remove)
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/payload-ceilings.spec.ts`
  - `frontend/tests/support/feed-ledgers.ts`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/app.d.ts`
  - `frontend/vite.config.ts`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/gardener/pre-yearly-retention/config/idhazh.json`
  - `docs/architecture/publishing/committing.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** Locally, select ledger-copy/payload logic and tooling inventory checks, and run the named config, panel, canary and publication-decision tests with applicable lint/type checks. Use real temporary Git repositories for push-range decisions. Confirm the staged fixture has no raw tree and its compact-dependent panels remain covered. CI supplies full coverage; do not dispatch a data-writing live workflow as a gate.
- **Oracle:** A real temporary Git history containing only raw/compact telemetry changes produces `publish=false`, while a verified digest-publication or site-code change still produces the appropriate publish decision, and the real staging fixture contains no raw files. This proves trigger and output boundaries, not that GitHub will never enqueue the lightweight decision job.

**Table L - Cleanup and publication decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Delete `ledger.published` and its schema field after the migration bridge has proved exact parity. Every remaining staging, retention-validation, published-column, bundle-weight and panel-coverage consumer derives its eligible set from the validated consent field. Do not leave a compatibility default, second list or global-production-registry shortcut for caller-supplied config roots. | Verified consumers include `config.py`, `cli.py`, bundle gates and named tests. |
| L2 | Delete the raw-day walk/listing builder and raw file copying from `ledgerCopy`. Delete `raw-listed-through.mjs`, its spec and inventory entry, and `__RAW_LISTED_THROUGH__`. Remove `__SITE_WINDOW_DAYS__` if no browser reader remains; keep the build's actual compact-copy window. | Owner wants no build-time directory discovery for explorer data. |
| L3 | Keep index-driven compact staging needed by current panels, using the same consent-derived set and existing copy limits. Retain its incomplete-index and missing-data behavior. Do not replace it with a scan or claim that all published compact bytes have been removed. | Table B's non-explorer-reader boundary. |
| L4 | In `publish_decision.py`, exclude changes confined to `state/raw/` and `state/compact/` from the site-build input decision, including mixed changes with docs or other existing non-inputs. Preserve decisions for real published digest changes, site code, explicit manual publication and unavailable change ranges. The deciding workflow may wake and exit; build and deploy must not run for telemetry alone. | Owner's explicit telemetry-only publication requirement; verified current `is_build_input` counts state paths. |
| L5 | Keep this rule in the existing decision program; do not add a second workflow path filter or event mechanism. Runtime-only registry edits may be tested separately, but are not permission to suppress publication for other config changes. | Verified Pages workflow delegates the decision to one program. |
| L6 | Remove raw-specific assumptions from canary construction and delivery tests while retaining real compact fixtures, backend raw storage/packing coverage and any historical contract readers. An obsolete browser-copy test is not a reason to delete a historical persisted model. | Table A's unchanged storage contracts; owner rejected an extra fixture matrix. |
| L7 | Correct the archive-base field description: it now selects the explorer's direct compact source. Retain no environment-variable destination. Check fixture copies of authored app configuration when the old field is removed. | Verified config fields and fixture search. |

**Table M - Rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Remove every compact file from Pages now | Existing panel readers still need those copies. | Their own source migration and browser/transport verification. | Owner scope; Table B. |
| M2 | Trigger site publication whenever telemetry lands | It rebuilds unchanged explorer code to copy data the explorer now reads directly. | Repeated build/deploy work with no explorer freshness benefit. | Owner explicitly rejected telemetry-triggered site publishing. |
| M3 | Suppress every change under all data or config directories | Some files still feed real published pages and build-time configuration. | Migration of those consumers or acceptance of stale pages; neither was requested. | Verified publication and build readers. |

## 7. Row #6 - Reconcile documentation with the delivered behavior

- **Scope:** Make the affected documentation and still-active plan instructions describe one consistent flat-lookup, compact-only explorer design.
- **Files touched:**
  - `CLAUDE.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/ledger-lifecycle.md`
  - `docs/architecture/contracts/state-ledgers.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/publishing/console-payloads.md`
  - `docs/architecture/publishing/console-site-size.md`
  - `docs/architecture/publishing/committing.md`
  - `docs/architecture/publishing/data-explorer-state.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/architecture/publishing/idhazh-gardener.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/architecture/publishing/llm-council.md`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/telemetry.md`
  - `docs/how-to/query-a-ledger-from-the-console.md`
  - `docs/reference/data-growth.md`
  - `docs/reference/repository-layout.md`
  - `tests/fixtures/raw-day-listing/README.md`
  - `TODO/20260823-known-defects-plan.md`
  - `TODO/20261011-65-summary-fidelity-judge-plan.md`
  - `TODO/20261011-summary-fidelity-judge-review-record.md`
  - `TODO/20261012-65.2-summary-fidelity-judge-plan.md`
  - `TODO/20261012-summary-quality-scorer-contracts-design.md`
  - `TODO/20261012-summary-fidelity-judge-hard-look-record.md`
  - `TODO/20261020-66-feed-ingest-plan.md`
- **Acceptance gates:** Documentation only: run `doc_load.py` on the explicitly named changed pages, inspect direct link/anchor findings, and run the documentation selection/whitespace check. Search this fixed inventory for live instructions referring to the removed allowlist, frontend name/folder arrays, raw listings, older-only archive fallback and the old staging filename. No application suite or browser matrix is required for this row.
- **Oracle:** Following the operator how-to and registry onboarding instructions reaches the delivered code without asking for a duplicate list, a site rebuild, a raw listing or an unapproved scope change. This checks documentary agreement, not transport or packing availability already covered by earlier rows.

**Table N - Documentation tasks and retained reasons**

| Id | Decision | Authority |
| --- | --- | --- |
| N1 | Retain the reason for family grouping: one lifecycle decision controls the whole family, while an address belongs to one ledger. State explicitly that the lookup, not JSON or physical storage, is flat. | Existing registry rationale; owner chose flat lookup only. |
| N2 | Define registry consent once in `ledger-registry.md`; link to it elsewhere. Remove instructions to maintain the old publication list or the handwritten frontend name/folder copies. Keep onboarding of the backend enum, real row contracts and compaction tasks. | Existing onboarding contract; Rows 2 and 3. |
| N3 | Let the written-question page own direct compact discovery and failure semantics; let the panel page own retained staged-panel delivery. Explain that three existing compact indexes are sufficient, while a raw directory path would not reveal generated filenames. | Owner's index-first choice; verified existing raw/compact naming reason. |
| N4 | Update the how-to and state page for Refresh, current consent, packed-through dates, packing delay, configured date/query limits and explicit repository errors. Remove obsolete raw/two-source messages, not the independent empty/lost/missing distinctions. | Owner's compact-only and date-range rulings. |
| N5 | Document telemetry-only non-publication and the remaining staged compact copies. Do not promise a measured speedup, a specific byte saving or immediate GitHub cache propagation without measurements. | Owner's build-cost goal; [measurement rule](../CLAUDE.md#1-adaptive-guardrails-read-first-every-session). |
| N6 | Preserve past measurements, test references and completed deliveries as historical evidence only when they still have a reader. Correct still-active instructions in overlapping plans by row title, not a mutable row number. Do not alter another plan's completed status or silently reduce its feed-ledger delivery scope. | [Plan authoring](../docs/how-to/author-a-plan.md); existing feed-planning delivery. |
| N7 | Apply the documentation split/delete/merge test to changed pages and repair their direct links. Each code row already updates its owning page; this row closes cross-document contradictions rather than delaying documentation until the end. Do not restate project rules in domain-neutral process docs. | [Documentation structure](../docs/reference/documentation-structure.md). |
| N8 | At closure, put durable decisions in the owning docs and remove the completed plan per the execution contract. Leave no private design artifact as the sole authority. | [Execution closure](../docs/how-to/execute-a-plan.md#closure). |

**Table O - Rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Keep the design only in this plan or the session artifact | A later contributor starts at `docs/`, not this conversation. | Reconstructing the behavior and its reasons from temporary material. | Owner explicitly requested documentation work. |
| O2 | Rewrite current docs now as if the feature already shipped | This is an author-only delivery; the implementation is still pending. | Implementing and verifying the corresponding row first. | Current owner request and prepare-plan contract. |
| O3 | Erase every historical occurrence of an old identifier | It rewrites evidence rather than fixing instructions. | A justified change to each historical claim; none is required for the new reader. | Documentation routing and single-snapshot rules. |
