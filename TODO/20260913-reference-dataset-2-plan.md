# Build and sample `corpus/reference-dataset-2`

**Last Updated**: 2026-09-13
**Level**: 5 - new persisted records and a local utility configuration.

## 0. Operating contract

Table A - Operating contract

| ID | Field | Value |
| --- | --- | --- |
| A1 | Intent | Preserve every supplied URL, extract its full sanitized article prose, record each result and its provenance, and support a later balanced classification sample. |
| A2 | Input | The current working copy of [REFERENCE_SET_1_URLS.txt](REFERENCE_SET_1_URLS.txt). It is the source for this task, including its uncommitted edits. Do not substitute the published archive or the existing classifier dataset. |
| A3 | In scope | A dataset-local config; backend utility reuse; JSON arrays and metadata; resumable extraction; stored totals; deterministic sample selection; fixture-based tests; documentation. |
| A4 | Out of scope | Running a classifier, writing labels or summaries, training, changing the published site, scheduling a workflow, or replacing `corpus/reference-dataset-1/`. |
| A5 | Config boundary | All utility settings live in `corpus/reference-dataset-2/config.json`. Do not add fields to `AppConfig`, edit `config/idhazh.json`, or change the old reference builder's defaults. The local file is schema-validated. |
| A6 | Code ownership | Extend the existing backend reference-dataset utility and reuse its suitable helpers. No utility code under `corpus/`, no new HTTP client, no copied extractor, and no parallel implementation of URL identity. |
| A7 | Execution | One step at a time, parallel N = 1, because the user wants to inspect and authorize individual steps. This delivery writes this plan only. Every implementation and data-producing step remains pending. |
| A8 | Stop conditions | Pause before a new persisted shape is approved; before bulk fetching until the pilot is accepted; if existing helpers cannot meet the trust boundary or full-text requirement; before any global-config change; before changing the existing frozen dataset; or before a measured cost exceeds the accepted pilot estimate by three times. |
| A9 | Publication | `corpus/` is not part of the site. Committing article bodies to this public repository makes those bodies publicly readable; obtain approval before publishing the collected text in git. Respect robots rules and paywalls. |
| A10 | Successor | Classification is the final step of this work and is deliberately not a row here. It starts after step 12 hands over, under [Article classification plan](20260910-23-article-classification-plan.md). Nothing in this plan writes a label, a desk or any model verdict. |

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md), with the user-directed execution override in Table A: parallel N = 1, authorize one step at a time, and AUTHOR-AND-STOP for this delivery. Creating this plan authorizes no code change, network fetch, commit, push, or merge.

### Proposed tree

```text
backend/
|-- utilities/
|   `-- build_reference_dataset.py       extend the existing tool
`-- idhazh/contracts/
    `-- reference_dataset.py            extend with local-config and record models

schemas/                                generated, not hand-written

corpus/
|-- reference-dataset-1/                 existing frozen dataset; unchanged
`-- reference-dataset-2/
    |-- config.json                     all settings for this utility
    |-- README.md                       purpose, provenance and usage limits
    |-- urls.txt                        supplied URL snapshot
    |-- manifest.json                   array; one record per input URL line
    |-- manifest.meta.json              input identity and stored totals
    |-- scratch/                        ignored trial data and checkpoints
    |   `-- <run-id>/items/<url_key>.json
    |-- extractions/
    |   `-- <run-id>/
    |       |-- articles.json           array; one result per manifest record
    |       `-- metadata.json           dates, versions, settings and totals
    `-- selections/
        `-- <selection-id>/
            |-- urls.json               array; selected identities and URLs
            `-- metadata.json           selection settings and allocation totals
```

`corpus/reference-dataset-2/` is this plan's new collection. `corpus/reference-dataset-1/` is the existing frozen hand-label set, with its own datasheet, rows, splits and article files. They are numbered siblings and separate collections, and nothing in this plan reads, writes into, or renames the first.

Create each directory only when its first real file is needed. Dataset paths are resolved from the explicitly supplied local config, not from the current shell directory. Run names come from the utility, and item filenames come only from recomputed `url_key`. Neither a label nor fetched prose may supply a path.

### Existing implementation to reuse

Table B - Existing implementation

| ID | Existing surface | Use and limit |
| --- | --- | --- |
| B1 | [build_reference_dataset.py](../backend/utilities/build_reference_dataset.py) | Reuse `registrable_domain`, suitable round-robin selection logic, and atomic writing. Add a separate URL-input command family; preserve the existing archive-based commands. |
| B2 | [discover.py](../backend/idhazh/discover.py), `canonicalise`; [contracts/base.py](../backend/idhazh/contracts/base.py), `derive_url_key` | Normalize addresses and derive the existing stable identity. Preserve the originally supplied address separately. |
| B3 | [fetch.py](../backend/idhazh/fetch.py) | Reuse address checks, public-address protection, robots handling, bounded HTTP reads and retry behavior. `FetchResult` already distinguishes a truncated response body. |
| B4 | [extract.py](../backend/idhazh/extract.py) | Reuse `is_paywalled` and `extract_text`. The latter runs trafilatura and the sanitizer without the model's token truncation. It excludes tables and comments. |
| B5 | [contracts/reference_dataset.py](../backend/idhazh/contracts/reference_dataset.py), [contracts/article.py](../backend/idhazh/contracts/article.py) | Reuse existing field names and scalar types, not the entire models: a supplied URL has no mandatory feed, item id, rank score or human label. |
| B6 | [config/taxonomy.json](../config/taxonomy.json), [config/sources.json](../config/sources.json) | Read the existing vertical vocabulary and source declarations. Do not copy taxonomy definitions into local config or infer an article's true subject from its URL. |
| B7 | [contracts/corpus.py](../backend/idhazh/contracts/corpus.py) | Follow the existing `rows` total and `verticals` count-map convention. Do not call an extraction date a training harvest date. |
| B8 | [test_reference_dataset.py](../backend/tests/test_reference_dataset.py), [test_contracts.py](../backend/tests/test_contracts.py) | Extend the existing tests. Use bounded fixtures and temporary output roots; never make pytest walk the real collected articles. |

The current builder's `_usable_text` discards failure reasons and its `fetch_articles` writes separate text files. Reuse the lower-level fetch and extraction functions for the new output, rather than wrapping that lossy result or changing its old callers silently.

### Local configuration

The following names are proposed additions to the local schema, not fields that already exist in global config. Use the existing contract date stamp and changelog conventions. Record the fully resolved local settings in each run's metadata so later edits to the config cannot change what an earlier result claims to have used.

Table C - Local configuration

| ID | Local key | Initial value or rule |
| --- | --- | --- |
| C1 | `version` | The date-stamped version of the new local-config contract. |
| C2 | `input_file` | `corpus/reference-dataset-2/urls.txt`, relative to the repository root. |
| C3 | `taxonomy_file` | `config/taxonomy.json`, read-only, relative to the repository root. |
| C4 | `sources_file` | `config/sources.json`, read-only, relative to the repository root. |
| C5 | `extract` | Reuse `ExtractConfig` validation and defaults for the network settings consumed by `fetch.fetch`. Read no application settings through `config.load()`. Do not apply its model-input truncation setting to saved text. |
| C6 | `request_delay_seconds` | Reuse the existing reference utility's field name. Put the agreed value in the local file, not in a loop literal or global config. |
| C7 | `selection.rows_per_domain_target` | `20`, configurable. The initial allocation per group; a larger pool may exceed it when filling shortages. |
| C8 | `selection.rows_max` | `1000`, configurable. A hard total cap, not a promise to produce this many rows. |
| C9 | `selection.fill_shortfall` | `true`, configurable. Transfer places unavailable in small groups to groups with remaining articles. |
| C10 | `selection.group_by` | `publisher`, approved by the owner on 2026-09-13. `source_domain` and `host` remain available as explicit alternatives. |
| C11 | `selection.publisher_disambiguation` | The ordered parts appended to a publisher key that is not unique, default `["registered_name", "public_suffix", "host"]`. A unique key is never lengthened. |
| C12 | `selection.generic_host_labels` | Leftmost labels that name a subdomain rather than an outlet, so the key falls back to the registered name. Added after the first real import read `newsletter.semianalysis.com` as `newsletter`. |

`publisher` is the outlet name taken from the address rather than the registered domain. Drop a leading `www.`. When the host carries a label to the left of its registered domain, take that leftmost label, so `aleximas.substack.com` gives `aleximas`. Otherwise take the name part of the registered domain, so `theverge.com` gives `theverge` and `bbc.co.uk` gives `bbc`. Case-fold it, replace each run of characters that are not letters or digits with one hyphen, and trim the ends. That is the slug rule `idhazh/classify/calls.py` already applies to element names; share that helper rather than copy it, and refuse a key that normalises to nothing instead of writing an empty group. Under this rule `economictimes.indiatimes.com` and `timesofindia.indiatimes.com` are two publishers instead of one `indiatimes.com`, and every newsletter on a shared platform keeps its own allocation.

Two different hosts can still produce one key: `news.bbc.co.uk` and `news.ycombinator.com` both start at `news`. Lengthen only the keys that actually collide, and only as far as uniqueness needs - the registered name first (`news-bbc`, `news-ycombinator`), then the public suffix, then the whole host, in the order `selection.publisher_disambiguation` gives. Every key that is already unique keeps its short form.

Publisher keys are derived once, over the frozen manifest, and recorded in `manifest.meta.json` as a key-to-hosts map. Every later stage reads that map and none recomputes it. Without that freeze, adding one host later could silently rename an earlier publisher, because a key whose length depends on who else is in the pool is not a stable identity.

`source_domain` stays on every row as the registered name, because it is the unit the existing classifier dataset separates its splits on. A publisher-based sample does not change that rule and is not proof that a future development and test split is independent.

### Record shapes

All three row collections are ordinary JSON arrays, not JSONL and not a metadata object disguised as the first row. Declare their list types and row types with the project's native validation tools before writing them. Metadata references the generated schema for its collection. Generated schema files remain under `schemas/`; settings remain local to the dataset.

Table D - Record shapes

| ID | Record | Fields and meaning |
| --- | --- | --- |
| D1 | Manifest row | `version`, `source_line`, `source_url`, `canonical_url`, `url_key`, `source_domain`, `host`, `publisher`, nullable `source_id`, nullable `vertical`. `source_line` preserves the input position, `publisher` carries the frozen outlet key, and the other identity and category names reuse the project vocabulary. |
| D2 | Extraction row | Manifest identity fields plus `text`, `article_words`, `article_sha256`, `fetched_at`, `extracted_at`, `extractor_version`, `sanitizer_version`, `status`, `failure_code`, `failure_detail`. Reuse existing status and failure vocabularies where their meanings match. |
| D3 | Selection row | `version`, `url_key`, `source_url`, `canonical_url`, `source_domain`, `host`, `publisher`, nullable `vertical`, `article_sha256`. Link to one named extraction through the metadata; do not copy its full text. |
| D4 | Common metadata | `version`, collection schema reference, `rows`, `verticals`, count maps by domain, host and publisher, the publisher key-to-hosts map, input path and checksum, output checksum, and the fully resolved local settings. New provenance fields are declared once rather than borrowed under a false meaning. |
| D5 | Extraction metadata | Start and finish timestamps, manifest checksum, extractor and sanitizer versions, and overall, per-domain and per-publisher attempt/result counts. Each successful row keeps its actual extraction timestamp across resume. |
| D6 | Selection metadata | Extraction checksum, grouping field, requested and selected totals, overall shortage, and per-group available, selected, extra and shortage counts. |

An unknown category is `null`, not `unknown` inserted into the taxonomy. Populate `source_id` and `vertical` only when source configuration provides an unambiguous association; a hostname shared by feeds in different verticals is not such an association. `vertical` is source context, never a human or model reference label. Do not create `desk` or any classification output in this work.

Save untruncated sanitized article prose, not raw HTML and not the capped `Article.text` produced for model inference. Preserve paragraph breaks. A download stopped by its byte limit must not become a successful full-text record. Refused or failed results carry `text: null` and a typed reason; use null rather than fabricated word counts or extraction timestamps where no extraction took place. UTF-8 files use LF; JSON escaping can preserve source characters while keeping serialized files ASCII.

### Stored totals and selection rule

Table E - Stored totals

| ID | Stage | Counts that must be stored |
| --- | --- | --- |
| E1 | Import | Input URL rows, unique `url_key` count, equivalent-URL count, counts by registered domain, host and publisher, the publisher key-to-hosts map, every key that needed lengthening and what it was lengthened with, counts by vertical, and unassigned category count. Invalid input is reported with line numbers and blocks manifest creation rather than disappearing. |
| E2 | Extraction | Manifest rows, unique URLs attempted, successful and failed unique URLs, input rows covered by each outcome, pending URLs during a partial run, and failure-code counts. Separate attempts from unique identities so retries never inflate the pool. |
| E3 | Selection | Available unique successful articles, requested sample size, selected unique articles, unfilled places, and allocation per configured group. |

Let `target` be `selection.rows_per_domain_target`, `cap` be `selection.rows_max`, and `groups` be the number of groups represented by valid manifest identities. The requested sample size is `min(cap, target * groups)`. Keep groups with zero successful extractions in the accounting; their missing places may be filled elsewhere. The cap does not by itself require filling beyond the group targets when no group is short.

1. Group unique successful extraction records by the configured `group_by` field, reading the frozen publisher key from the record when that field is `publisher`. Sort group names, then sort each group's candidates by `url_key`.
2. Select in rounds, one unused article per nonempty group per round, until each reaches `target`, exhausts its pool, or the requested total is reached. The overall cap wins when not every group can receive its target.
3. If `fill_shortfall` is true, continue the rounds over groups with unused articles until the requested total is reached or the entire usable pool is exhausted. Record allocations above `target` as extra; do not hide which groups received them.
4. If `fill_shortfall` is false, stop after the initial allocation. A shortage is a reported result, not a reason to invent rows or duplicate an article.
5. Persist the actual selected identities and measured totals. Read the output back to compute verification counts; never report two values calculated from the same expected count as independent confirmation.

The manifest and full extraction pool are never reduced by selection settings. This pass neither filters by publication date nor applies the old builder's per-domain hard cap. Re-running the same selection against identical extraction bytes and local settings returns the same selected array. A different selection gets a different output directory; it never rewrites an earlier sample.

## 1. Status Reckoner

Table F - Status Reckoner

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 1 | Approve local dataset layout and meanings | - | A | DONE (approved 2026-09-13; name `reference-dataset-2`, grouping `publisher`) | - | direct | - |
| F2 | 2 | Snapshot and inventory the supplied URLs | 1 | B | DONE | refdata2 | direct | - |
| F3 | 3 | Define local config and record schemas | 2 | C | DONE | refdata2 | direct | - |
| F4 | 4 | Build the manifest, publisher keys and totals | 3 | D | DONE | refdata2 | direct | - |
| F5 | 5 | Add resumable extraction through existing helpers | 4 | E | DONE | refdata2 | direct | - |
| F6 | 6 | Run and review a small extraction pilot | 5 | F | DONE (run 2026-09-13; the bulk fetch waits on the review) | refdata2 | direct | - |
| F7 | 7 | Validate the utility with offline tests | 6 | G | DONE (tests shipped with each step; the pilot's one gap closed) | refdata2 | direct | - |
| F8 | 8 | Extract the full URL list | 7 | H | DONE (1,345 articles of 1,661; 52.5 min) | refdata2 | direct | - |
| F9 | 9 | Export extraction arrays and metadata | 8 | I | DONE | refdata2 | direct | - |
| F10 | 10 | Verify and freeze the extraction | 9 | J | DONE (zero faults) | refdata2 | direct | - |
| F11 | 11 | Select the configurable classification sample | 10 | K | DONE (1,000 articles, 52 publishers) | refdata2 | direct | - |
| F12 | 12 | Verify the selection and hand over | 11 | L | DONE | refdata2 | direct | - |
| F13 | 13 | Clean publisher furniture from the text | 10 | M | DONE (owner decision B3, 2026-09-13; 44,380 words removed) | refdata2 | direct | - |

## 2. Step 1 - Approve the local layout and meanings

- **Scope:** Confirm the tree, JSON-array format, local settings, grouping field, requested-size formula, full-text meaning and public-storage boundary before implementation. Approved on 2026-09-13.
- **Files touched:** This plan only if an approved choice changes it.
- **Acceptance gates:** Explicit user approval of those meanings; no application checks or network activity.
- **Oracle:** Two different newsletter hosts on one platform get separate allocations, because `selection.group_by` is `publisher` and their leftmost labels differ.
- **Decisions:** The owner approved this plan on 2026-09-13, named the collection `corpus/reference-dataset-2/`, and set grouping to the publisher prefix rather than the registered domain, with a colliding key lengthened only when it is not unique. Backend code and dataset-local settings are owner decisions of the same date; no value of 20 or 1000 is embedded in utility logic.
- **Rejected alternatives:** A global-config extension would affect the regular pipeline for an occasional operator task; the owner refused it on 2026-09-13. Grouping on the registered domain was refused the same day because it merges every newsletter on a shared platform into one allocation.

## 3. Step 2 - Snapshot and inventory the supplied URLs

- **Scope:** Create an unchanged input snapshot and dataset description without fetching an article.
- **Files touched:** `corpus/reference-dataset-2/urls.txt`, `corpus/reference-dataset-2/README.md`, `.gitignore`, `docs/reference/repository-layout.md`, this plan's own status row.
- **Acceptance gates:** Use a dedicated named branch and worktree for implementation per [ship-a-pr.md](../docs/how-to/ship-a-pr.md); snapshot the source working file, not its HEAD revision. Check input and snapshot checksums, LF, URL validity and exact duplicates. Record current counts rather than inheriting a count from chat.
- **Oracle:** Reading the snapshot reproduces every supplied URL in the same order; the source file's bytes remain unchanged.
- **Decisions:** Ignore this dataset's scratch subtree specifically; preserve durable outputs. Add the new collection to the repository-layout page before generating data into it.
- **Rejected alternatives:** Moving or rewriting the original input could lose the user's uncommitted changes or break its existing references; retain it as the source of the snapshot.

## 4. Step 3 - Define local config and record schemas

- **Scope:** Declare the local configuration, collection arrays, metadata and per-item checkpoints with fixture-backed validation before their writers.
- **Files touched:** `backend/idhazh/contracts/reference_dataset.py`, `backend/idhazh/contracts/export.py`, `backend/tests/test_contracts.py`, `backend/tests/test_reference_dataset.py`, `corpus/reference-dataset-2/config.json`, `schemas/reference-dataset-config.schema.json`, `schemas/reference-dataset-manifest.schema.json`, `schemas/reference-dataset-extractions.schema.json`, `schemas/reference-dataset-selection.schema.json`, `schemas/reference-dataset-metadata.schema.json`, contract fixtures under `tests/fixtures/contracts/reference-dataset-config/`, `tests/fixtures/contracts/reference-dataset-manifest/`, `tests/fixtures/contracts/reference-dataset-extractions/`, `tests/fixtures/contracts/reference-dataset-selection/` and `tests/fixtures/contracts/reference-dataset-metadata/`, `docs/how-to/measure-a-classifier.md`, this plan's own status row. Each new fixture directory holds the minimum real passing and refusing cases for its shape, named before the step starts.
- **Acceptance gates:** Approve the final schema diff; stamp each new exported shape and changelog; regenerate rather than hand-edit schemas. Validate at least two different local target/cap settings, invalid settings, nullable source metadata, both extraction outcomes, and JSON round trips. Use the shared local-check selector and the existing contract tests; CI owns full-suite checks when a PR is authorized.
- **Oracle:** A local config and a manifest for an unconfigured source validate without an `AppConfig` load, fake feed id or taxonomy edit; an unknown field is refused.
- **Decisions:** Array schemas are generated from declared native list models. Reuse existing scalar and failure types. The metadata model distinguishes phases and refuses inconsistent phase-specific counts. The checkpoint uses the same extraction-row shape, not a private unvalidated dictionary. Config paths are relative to the repository root rather than to the config file, because the project's shared relative-path type forbids a `..` segment and a stored `..` stops meaning the same thing when a file moves (`CLAUDE.md` section 2).
- **Rejected alternatives:** Inheriting the whole `Article` or `ReferenceDatasetRow` would require invented ranks, feeds, publication dates or labels. Declaring only the needed shape avoids those false facts.

## 5. Step 4 - Build the manifest and store totals

- **Scope:** Add an explicit URL-input mode to the existing reference-dataset utility and write the complete manifest with its publisher keys and count metadata.
- **Files touched:** `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, `tests/fixtures/reference-dataset/url-inputs.txt`, `tests/fixtures/reference-dataset/url-source-config.json`, `corpus/reference-dataset-2/manifest.json`, `corpus/reference-dataset-2/manifest.meta.json`, `docs/how-to/measure-a-classifier.md`, this plan's own status row.
- **Acceptance gates:** Keep the existing `plan`, `fetch`, `split` and `verify` behavior unchanged. The new mode takes an explicit local config path. Exercise equivalent addresses, source hosts shared by different verticals, unknown sources, malformed input and execution from a different shell directory. Exercise publisher derivation on a multi-tenant newsletter host, a two-part public suffix, a leading `www.`, two hosts whose leftmost labels collide, and a host that normalises to nothing. Run focused tests before continuing.
- **Oracle:** Every valid input line appears exactly once in manifest order; equivalent URLs retain their input rows and share one recomputed identity. Two hosts that the registered domain would merge appear as two publishers, and a colliding pair is lengthened only as far as uniqueness needs while every other key stays short. Independently read output totals match the array.
- **Decisions:** `source_url` preserves the original address; `canonical_url` and `url_key` use the project's existing functions. Publisher keys are derived here, recorded in `manifest.meta.json`, and read from there by every later stage. The slug helper in `idhazh/classify/calls.py` is shared rather than copied. No archive read, date cutoff, domain quota or training-overlap filter changes this manifest.
- **Rejected alternatives:** Calling the existing archive `plan` would select a different source set and apply a hard per-domain cap; neither is the requested import.

## 6. Step 5 - Add resumable extraction through existing helpers

- **Scope:** Fetch manifest identities through the existing protected network boundary and save a typed result for each attempted URL.
- **Files touched:** `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, real bounded fetch/extraction fixtures selected from `tests/fixtures/` and named before coding, `corpus/reference-dataset-2/scratch/<run-id>/items/<url_key>.json`, `docs/how-to/measure-a-classifier.md`, this plan's own status row.
- **Acceptance gates:** Reuse robots checks, paywall detection, configured retry/delay behavior, capped download reads, trafilatura and sanitization. Test success, robots refusal, paywall, empty extraction, response byte truncation, interruption and resume offline. Validate cached records and their input/config provenance rather than accepting a file merely because it exists.
- **Oracle:** Interrupt after a saved result, then resume: that result retains identical text, digest and timestamps; unfinished work completes; no successful unique URL is fetched twice.
- **Decisions:** Save each result with temporary-file-plus-rename. Refuse a truncated response as full text. Reuse only checkpoints with matching input and extraction settings; no page-controlled path, shell argument or new fetch URL is admitted.
- **Rejected alternatives:** The existing `_usable_text` discards failure reasons. Using it unchanged would lose the per-URL accounting this task requires.

## 7. Step 6 - Run and review a small extraction pilot

- **Scope:** Run the new utility against an explicit small subset of the supplied list, inspect the real results and obtain approval for bulk fetching.
- **Files touched:** `corpus/reference-dataset-2/scratch/pilot/` holding the subset, local pilot config, typed results and report; `corpus/reference-dataset-2/README.md`; this plan's own status row.
- **Acceptance gates:** Use the same backend code as the full run. Choose different hosts, including a long article and unconfigured sources; inspect both ends of extracted prose and paragraph breaks. Record any encountered refusals honestly. Record elapsed time, bytes, machine class and date; label the full-run forecast an estimate. Stop for user review.
- **Oracle:** A manually checked long article retains its ending in saved text, and each pilot URL has either its own result or an explicit pending state. A failure never appears as successful empty text.
- **Decisions:** Pilot size is an explicit input selection, not a baked-in number. Keep the full manifest intact. A site unavailable in the pilot remains unavailable; do not substitute an unrequested source to improve the success rate. Run 2026-09-13 over 8 publishers: 5 articles kept, 3 typed failures (one paywall, one page with no prose, one unreachable `robots.txt`), 28.7 s wall on a Windows developer box with a 1 s request delay. It found one defect - a robots refusal recorded no reason - which was fixed and re-proved against the live site.
- **Rejected alternatives:** A successful HTTP status alone does not prove article extraction, and a short excerpt cannot prove the full-text requirement.

## 8. Step 7 - Validate the utility with offline tests

- **Scope:** Close gaps found in the pilot and prove the import, extraction, resume and metadata behavior using fixed fixtures.
- **Files touched:** `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, the bounded fixtures selected or captured in steps 4 to 6, `docs/how-to/measure-a-classifier.md`, this plan's own status row.
- **Acceptance gates:** No test uses the open web or scans collected articles. Run `npm --prefix frontend run test:changed -- --list`, then applicable focused pytest, ruff and mypy checks per [run-the-gates.md](../docs/how-to/run-the-gates.md). Regenerate schemas only if a contract changes and review that change first. Preserve the old reference builder's fixture results.
- **Oracle:** Given successful, failed and equivalent input URLs, the exported row counts and unique-identity counts reconcile independently; changing a recorded total to a wrong value makes verification fail.
- **Decisions:** Extend the existing test module; the reusable utility already lives in the backend and needs no later move out of scratch. CI runs the full suite on an authorized merge candidate, not once per data batch.
- **Rejected alternatives:** A real-archive test grows with the dataset and confuses data hygiene with code behavior; use an operator verification command for real outputs.

## 9. Step 8 - Extract the full URL list

- **Scope:** Process every valid identity in the frozen manifest after pilot approval, retaining successful and failed results.
- **Files touched:** `corpus/reference-dataset-2/scratch/<run-id>/items/<url_key>.json`, `corpus/reference-dataset-2/README.md`, this plan's own status row.
- **Acceptance gates:** Run against the approved local config and explicit manifest. Save progress after each result, respect network limits and report counts as work proceeds. Bound retries through existing settings; retain terminal failures rather than retrying them forever. Do not follow article hyperlinks or use model output to choose URLs.
- **Oracle:** Every unique manifest identity reaches one final result, and another normal resume makes zero article requests for that completed run.
- **Decisions:** Process the full supplied pool. Selection settings apply only to the later selection step. Stop and price any material cost overrun against the pilot before continuing.
- **Rejected alternatives:** Limiting this fetch pass to the intended classification sample would discard the reserve needed to fill domain shortages later.

## 10. Step 9 - Export extraction arrays and metadata

- **Scope:** Build ordinary JSON deliverables from validated checkpoints without making a network request.
- **Files touched:** `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, `corpus/reference-dataset-2/extractions/<run-id>/articles.json`, `corpus/reference-dataset-2/extractions/<run-id>/metadata.json`, `docs/how-to/measure-a-classifier.md`, this plan's own status row.
- **Acceptance gates:** Write one result per input manifest record, including failures and equivalent URL aliases. Checkpoint reuse may avoid a fetch but may not remove an input row. Emit LF, validate complete arrays, calculate counts from actual records, and write output checksums. Refuse a complete export while any manifest identity is pending.
- **Oracle:** Every exported identity and status joins to its saved checkpoint, and every manifest source line joins to exactly one output row. No metadata count is accepted without an independent output read.
- **Decisions:** Export atomically and write metadata last. Keep failure text null. Each row records the actual attempt/extraction dates; the export date is not substituted for either.
- **Rejected alternatives:** One growing JSON-array rewrite after every HTTP request repeatedly processes all prior results. Per-item checkpoints followed by one explicit export avoid that cost.

## 11. Step 10 - Verify and freeze the extraction

- **Scope:** Validate the real output once through the operator utility and record the frozen input for later sampling.
- **Files touched:** `corpus/reference-dataset-2/README.md`, `docs/how-to/measure-a-classifier.md`, this plan's own status row; repair extraction outputs only by rerunning their declared writer.
- **Acceptance gates:** Verify schemas, input/output checksums, line coverage, unique identities, text digests, word counts, failure counts and unassigned categories. Re-export from saved records without network access and compare bytes. Report any unresolved access failures and ask before committing article bodies. Keep earlier frozen outputs unchanged if an explicit refetch is later requested.
- **Oracle:** A changed text byte or missing result fails verification, while an unchanged offline re-export reproduces the arrays and metadata describing the original run.
- **Decisions:** Checkpoints exist to recover interrupted work. Delete them only after verified durable results can reconstruct or replace that recovery function; scratch cleanup must not be required for correctness.
- **Rejected alternatives:** Re-fetching to verify changes the source observation and cannot prove that the saved run was correct.

## 12. Step 11 - Select the configurable classification sample

- **Scope:** Extend the backend utility to select unique successful articles under the approved local selection settings and write the sample plus allocation totals.
- **Files touched:** `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, `corpus/reference-dataset-2/selections/<selection-id>/urls.json`, `corpus/reference-dataset-2/selections/<selection-id>/metadata.json`, `docs/how-to/measure-a-classifier.md`, this plan's own status row. Build small allocation cases in the existing test module rather than creating a second collected dataset.
- **Acceptance gates:** Prove the selection rule with unequal pools, an empty-success group, insufficient total supply, equivalent input URLs, a cap reached before all targets, all three grouping modes, and a publisher pair that needed lengthening. Change target, cap and fill behavior through local config only. Record all requested and actual totals, including zero allocations.
- **Oracle:** With three groups holding 1, 5 and 5 usable articles, target 2 and cap 6, fill enabled selects 6 distinct articles with the small group contributing 1 and a larger group exceeding 2; fill disabled selects 5. Changing cap to 4 selects at most 4. These are test parameters, never production literals.
- **Decisions:** Reuse the existing round-robin approach, keeping its legacy hard-cap behavior intact for old commands. Recompute `url_key`, never select failures, and write no classification verdict.
- **Rejected alternatives:** Reusing `rows_per_domain_max` as a soft target would change an existing setting's meaning; alphabetical first-N selection would favor the first domains in the list.

## 13. Step 12 - Verify the selection and hand over

- **Scope:** Prove the frozen selection can be reproduced and handed to a later classification step without changing any existing evaluation or training collection.
- **Files touched:** `backend/utilities/build_reference_dataset.py`, `backend/tests/test_reference_dataset.py`, `corpus/reference-dataset-2/README.md`, `docs/how-to/measure-a-classifier.md`, this plan's own status row.
- **Acceptance gates:** Independently join each selected key and text digest to the named extraction, verify the configured total bound and per-group allocation, and reproduce the chosen array from the recorded settings. Document implemented commands and failure/resume behavior. Run only checks needed for the files that changed; no application suite for documentation-only closure.
- **Oracle:** The same frozen pool and settings produce byte-identical selected URL records; changing the live local config does not change verification of an earlier selection's recorded settings.
- **Decisions:** Deliver a count summary and paths to the manifest, extraction and selection. Classification is the step after this one and runs under its own plan, never inside this one. Before any later use as a held-out classifier benchmark, separately check training/reference overlap and source separation under [measure-a-classifier.md](../docs/how-to/measure-a-classifier.md). Collection alone does not authorize that use or produce human labels.
- **Rejected alternatives:** Treating this sample as the existing frozen classifier dataset would mix two independently built sets and invalidate comparisons; promotion or replacement needs its own approval.

## See also

- [Article classification plan](20260910-23-article-classification-plan.md) - later labels and measurements; not authorization to execute those rows here.
- [Measure a classifier](../docs/how-to/measure-a-classifier.md) - existing reference builder and evaluation separation.
- [Taxonomy](../docs/concepts/taxonomy.md) - the vocabulary and lifecycle rules.
- [Contract schemas](../docs/architecture/contracts/schemas.md) - declaration, generation, versioning and compatibility.
- [Repository layout](../docs/reference/repository-layout.md) - code, data and publication ownership.
- [Run the gates](../docs/how-to/run-the-gates.md) - local selection, focused checks and CI.
