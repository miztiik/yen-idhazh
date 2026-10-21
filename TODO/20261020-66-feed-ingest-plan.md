# Plan 66 - Feed ingest plan engine

**Last Updated**: 2026-10-20
**Level**: 5 (source-kind/tier and persisted-contract migration requires owner approval before execution; the later planner implementation follows the approved contracts)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

---

## 0. Operating contract

### Owner correction - TypeScript-only development and verification

Owner ruling, 2026-10-21: the remaining Plan 66 implementation introduces no
Python tests, invokes no Python from TypeScript tests or development commands,
and installs no Python packages in the isolated workflow created by this plan.
This supersedes every Python execution or new Python-test requirement below.
Existing merged backend work and existing repository-wide CI remain unchanged.
Persisted format compatibility remains required, using TypeScript validation,
real Parquet readback, and bounded recorded schema, identity and canonical-byte
fixtures. These checks do not claim execution of the Python reader.
Do not relocate a Python helper to another directory to evade this ruling.
Record this separation in the owning persistence documentation before closure.

### Separate gate repair - 2026-10-21

Cross-row oracle correction, 2026-10-21: Row #12 found that Row #7 includes
`workflow_reporting` in its planning-input fingerprint. Changing optional
reporting therefore changes policy fingerprints and ledger content, contrary
to the existing reporting-independence requirement. The original Row #7
owner corrects only its already named loader, harvest test and harvesting
page: exclude reporting-only controls from the planning fingerprint while
retaining their actual configuration for the external reporting adapter.
Verify report flag/removal text substitutions leave the fingerprint alone
and a genuine planning knob still changes it. Rows #11 and #12 integrate the
tested follow-up; neither edits the loader concurrently. This changes no
persisted field or format and is not a CI repair.

Reviewed follow-up `9341af4d7512dc99fd6097aa4bac5863ce0334fa`
changes only those three paths. Strict TypeScript and nine harvest tests
passed. The substitution checks preserve reporting settings in the returned
configuration, leave both reporting-only changes out of the fingerprint,
and detect a real age-policy change. Row #12 still verifies the separate
two-run ledger-digest comparison after integrating this head.

Row #12 subsequently integrated that head and reported identical dispatch,
selection and rejection content digests across real reporting-off and
reporting-on runs. Its ten adapter/native tests passed; final strict checks
and runner/audit integration remain open. CI on the harvest follow-up passed
scope, site, browser and robots. Its backend gate passed 7249 tests and
failed only the same two schedule assertions below. No merge is authorized
while that required gate remains red.

Row #6 merge blocker: CI run 39644823082 at writer head
`bed0e6cc3080898644024a99200ec6a882a1dd1b` passes its TypeScript writer,
site, browser and robots checks. The repository backend gate passes 7249 tests
and fails two existing schedule checks after unrelated main commit
`12b276024` adds digest runs at 00:20, 20:20 and 22:20 UTC.
`backend/tests/workflows/test_triggers.py` still declares five approved hours
and a history-rewrite overlap measurement for that earlier schedule.
No writer code caused these failures. Keep Row #6 unmerged while CI is red.
Restoring the earlier schedule gives up the three added runs; retaining them
requires a separate measured schedule-safety repair and owner authorization
for changes outside this TypeScript plan. Neither was authorized when the
owner was unavailable. Do not add Python tests or silently change production
scheduling to clear this blocker.

Delivery continuation, 2026-10-21: the owner directed continued autonomous
implementation after this blocker was reported. Row #6 implementation and
review are complete; its merge remains blocked. Row #4 can build in an
isolated child on the reviewed writer branch without merging either change.
Keep the writer head stable, merge updated main before final verification,
and retain serialized green-only merges. The separate digest-schedule session
owns the schedule repair; do not duplicate it in a plan row.

Owner correction, 2026-10-21: do not fix CI issues; other agents own them.
Build the remaining rows and keep them ready while those repairs proceed.
An unrelated failed check blocks merge, not isolated implementation.

Owner-directed scope change: repair the existing query-door EXPLAIN fixture
check in a separate PR from main, not as a Plan 66 row. CI run 39608009522
for PR #1607 passed 7185 backend tests and failed only
`test_additional_answer_fixtures_are_recomputed_with_duckdb`: native DuckDB
changed its plan drawing, not the query's meaning. Check EXPLAIN fields and
plan meaning while retaining every other exact answer comparison, the
unchanged browser fixture and real browser EXPLAIN support. Do not change
production behavior or dependency ranges. Rows #2, #3 and #5, their
implementation and all row statuses remain unchanged.

### Table A - Operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Build an isolated Bun/TypeScript planner that checks article text before selection, keeps host telemetry separate, and writes Python-readable, managed Parquet ledgers. Production planning and worker network calls remain unchanged until a separately approved cutover; this plan makes prefetched text available in dispatches but does not change the existing worker's consumption path. |
| A2 | Hard scope - in | - Modular topology: packages/common-contracts, packages/ledger-file-writer, services/host-fingerprints, services/host-probes, and services/feed-ingest-plan.<br>- Pre-fetching full article text with linkedom and Defuddle, capturing feed item category tags with an empty array only when tags are absent.<br>- Dedicated configuration file: config/feed-ingest-plan.json for word-count thresholds, timeouts, age cutoff, recency scoring, normalization rules, and MMR weights.<br>- Candidate screening with typed drop reasons in state/raw/feed-ingest-plan/rejections/.<br>- Enrolling dispatches and rejections into config/ledgers.json for automated gardener compaction.<br>- Set-aware portfolio curation with weak configurable source-kind influence, source opportunity normalization, separate quality axes, and soft concentration caps.<br>- Configurable article partitioning.<br>- Planner REST API and one-shot CLI with structured JSONL event logging.<br>- Shared TypeScript ledger writer usable by any API or CLI, following the Python identity, envelope, digest, and atomic-write contracts.<br>- Isolated CI workflow with the inputs in Table R and optional reporting outside the production modules. |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Bun services with shared contract and ledger-writing packages, calendar versioning, the stage names in Table E, and Python reader compatibility before any writer or workflow cutover. The owner selected the shared ledger package; other design choices remain plan proposals, not advisor rulings. |
| A6 | Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md after explicit implementation approval. Parallel N = 4 is a ceiling, not a requirement. Dispatch by Depends-on and disjoint Files touched, not group letters: Row #15 precedes #1; #2 precedes explorer readers in #16; #16 precedes the writer in #6; #14 precedes #12; #13 follows #12. |
| A7 | Driving principle | Host telemetry stays outside the planner. Identity creation and Parquet writing live in one reusable package with no planner or GitHub dependency. Curation is independent of partitioning. GitHub annotations and summaries live in a removable reporting adapter. Production workflows stay unchanged during this plan. |
| A8 | State ledger layout | Every registered ledger writes raw files under `state/raw/<ledger-prefix>/` and compacted files under `state/compact/<ledger-prefix>/`. Resolve the prefix from config/ledgers.json; it can contain more than one folder. No ledger writes directly under `state/<ledger-prefix>/`. |
| A9 | Config-only extension | Row #15 removes fixed kind/tier membership from contracts and code. Row #3 declares per-vertical planning overrides, separate from publication desk controls. After that one migration, adding kind/tier/vertical/desk entries or changing their declared settings needs configuration changes only; new algorithms or extraction formats still need implementation. |
| A10 | Ledger format, not example syntax | Every ledger introduced by this plan is typed Parquet through the shared writer, under its registered raw/compact prefix. JSON examples describe authored configuration only; TypeScript objects describe validation only. Neither authorizes JSON or JSONL row-ledger files under state. Existing contracted JSON indexes/listings retain their specified formats. Structured JSONL logs are not persisted ledger artifacts. |
| A10 | Explorer delivery | Row #16 makes every feed-ingest-plan ledger queryable through `console/data-explorer`; host-fingerprint is already published. Registration alone is not publication. The repository and static explorer are public, and publication exposes the actual Parquet columns, including dispatch article text. No implicit metadata-only projection or dropped ledger. |

### Table B - Hard scope - out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Modifications to .github/workflows/digest.yml | Production workflow continues using existing Python plan until cutover PR | Successful verification in .github/workflows/feed-ingest-plan-test.yml |
| B2 | Moving or renaming config/sources.json | Feed configuration remains at repository root | An owner ruling on repository-wide configuration restructuring |
| B3 | Modifying Python backend/idhazh/stages/work.py | Existing work consumes RunPlan and still fetches articles; the new dispatch ledger is not a drop-in worker input. Python ledger readback certifies storage compatibility only, not elimination of worker fetches. | A dedicated worker adapter/migration and production cutover plan |
| B4 | Phase 2 metrics within the Phase 1 delivery | Phase 1 captures source/article evidence and computes available per-run planning metrics. Published counts, lead selection, and cross-day publication metrics cannot be inferred from a plan. Phase 2 remains in this plan as Row #13, after Phase 1; it is not omitted from the overall capability. | Complete the Phase 1 evidence ledgers and then the post-publication reader in Row #13 |
| B5 | Llama-server execution during plan stage | Plan stage performs deterministic heuristic curation and text extraction; no local LLM inference in plan | A requirement for semantic LLM classification prior to sharding |

### Table C - ESCALATE triggers

| # | Trigger | Action |
| --- | --- | --- |
| C1 | Parquet file generated by parquet-wasm fails PyArrow or DuckDB deserialization in Python | STOP and surface immediately: schema or footer metadata mismatch |
| C2 | Feed harvesting failure rate exceeds 40% across active sources in config/sources.json | PAUSE and inspect runner DNS, proxy, or upstream connectivity |
| C3 | Runner memory consumption in services/feed-ingest-plan exceeds 1.5 GB during pre-fetch | STOP: evaluate concurrency pool size and DOM streaming limits |
| C4 | Isolated compatibility checks report missing columns or schema incompatibility | STOP the isolated integration and record the exact contract/type mismatch. Production remains on the Python planner; do not describe ledger readback as a worker cutover. |
| C5 | Implementation changes a source-classification type, adds/changes a persisted row contract, or adds a TypeScript writer provenance value to FileEnvelope | PAUSE for owner approval under CLAUDE.md section 6, Level 5; plan-only approval is not implementation approval. Land compatible Python/frontend readers before new writers. |

---

## 1. Domain Vocabulary Specification

### Table E - Stage names

| # | Pipeline phase | Action and module directory | Job |
| --- | --- | --- | --- |
| E1 | Ingestion | `harvest-feeds` | Poll RSS/Atom feeds, capture category tags, canonicalize URLs, and extract article text. |
| E2 | Screening | `screen-article-candidates` | Apply word-count, paywall, category, and maximum-age checks; record typed rejections. |
| E3 | Curation | `curate-article-portfolio` | Normalize source opportunity, penalize repeated coverage, and select articles within soft concentration limits. |
| E4 | Partitioning | `partition-article-shards` | Balance selected articles across workers by estimated work. |
| E5 | Storage | `seal-article-ledger` | Planner-specific adapter that passes rows and writer context to the shared ledger package; contains no generic serialization logic. |

### Table T - Independent terms, owners, and selection controls

| # | Term | Canonical owner | Config control and boundary |
| --- | --- | --- | --- |
| T1 | Source / feed | FeedDef in backend/idhazh/contracts/sources.py | A configured feed entry, identified by source_id. Its weight, status, allowance, and source-concentration penalty are independent controls. Preserve feed identity; do not use source_id as publisher identity. |
| T2 | Publisher | The outlet rule in docs/architecture/publishing/autotune-content-similarity.md | Group carrier evidence by the recorded outlet, not by feed count; retain the separate configured parent-domain concentration limit. Two feeds from one publisher are not two independent publishers. |
| T3 | Vertical | docs/concepts/taxonomy.md, A vertical is a partition | The source feed's configured subject grouping. `vertical_overrides` controls its planning thresholds/weights; `lambda_vertical` controls portfolio saturation by this grouping. Do not rename or overwrite it when an article is filed elsewhere. |
| T4 | Desk | docs/concepts/taxonomy.md, A desk is where the day published the story | Actual publication placement, using the same ID vocabulary as verticals but a separate field. Its existing configured floor/ceiling and placement rules are independent of vertical planning policy. `lambda_desk` can act only on a validated assigned desk; unavailable desk evidence is recorded as unavailable, not copied from vertical. |
| T5 | Lens | docs/concepts/taxonomy.md, A lens is a question asked of items already collected | Cross-cutting theme membership comes from the configured lens matcher. Each lens's existing weight and the separate `lambda_lens` saturation coefficient are configurable. Do not call a lens a topic, desk, or vertical in the new contract. |
| T6 | Event type | docs/concepts/taxonomy.md, An event is what happened | The configured class of occurrence, such as a release or acquisition. Use event_types in new assessment payloads and the independent `lambda_event_type` coefficient. Existing payload fields named events retain their compatibility spelling. Sharing an event type does not establish a duplicate story. |
| T7 | Event cluster | docs/architecture/publishing/autotune-content-similarity.md | One particular occurrence grouped from recorded story evidence. Its matching settings, `lambda_event_cluster`, and cluster-item limit are independent of event-type settings. Repetition metrics compare these occurrences, not every item labelled release. |
| T8 | Entity | EntityDef in backend/idhazh/contracts/watchlist.py | A named organisation or followed subject. Its configured aliases and existing watchlist bonus remain separate from the new `lambda_entity` portfolio-saturation coefficient. Sharing an entity is neither an event-type match nor proof of one story. |
| T9 | Source kind / tier | Table N and its owning registry | Publisher description and configured authority weight respectively. Keep their controls separate from all article labels; kind remains weak and neither value chooses the article's vertical, desk, lenses, or event cluster. |
| T10 | Audit event | Table J | A pipeline observation, not a content event type. New audit envelopes use audit_event_type as the observation discriminator; event_id is the audit record identity, never the article's event-cluster ID. |
| T11 | Feed category | Feed parser and Table G candidate fields | Keep the feed's own category strings as categories. They are not automatically taxonomy labels; any conversion to lenses, event types, or entities requires the named configured matcher and its evidence. |
| T12 | Independent tuning | Table O and the existing taxonomy/watchlist configuration | Vary one dimension's coefficient or rule without silently changing another's configuration or recorded identity. Selection outcomes can change because the terms combine, but evidence remains separate. Keep unavailable terms explicit; do not invent a desk or model classification to make a knob appear active. |
| T13 | Label saturation calculation | Row #9's declared portfolio terms | For each newly separated vertical, assigned-desk, lens, event-type, or entity term, use the fraction of already selected articles sharing at least one value of that same dimension, multiplied by its coefficient. Count a selected article once even if several values match; an empty selected set contributes zero. Unknown labels have unavailable evidence and no contribution, distinct from a known empty label set. |

---

## 2. Configuration Decentralization

Rather than adding planner knobs to `config/idhazh.json`, a dedicated configuration document `config/feed-ingest-plan.json` is created.

### Configuration Schema (`config/feed-ingest-plan.json`)

### Table F - Source-kind influence

| # | Rule | Meaning |
| --- | --- | --- |
| F1 | Available before fetching | `config/sources.json` already assigns each feed a `kind`. BBC World is `reporting`, Google Research is `research`, and Google DeepMind is `announcement`. `FeedDef.kind` reads this configuration; the planner does not infer it from an article. |
| F2 | Weak evidence | The label is a judgement that can become stale. Similar sources may be labelled differently, especially government reporting and announcements. Do not require manual reclassification of every source for a run to work. The durable design constraint is in docs/architecture/sources/discovery.md, Design rationale. |
| F3 | Configurable influence | Use `mmr_weights.lambda_source_kind` only for a small diversity penalty. Multiply it by the fraction of the selected portfolio with the candidate's source kind; an empty portfolio has zero penalty. The proposed default bounds the penalty at 0.05 score points; it is provisional, not a measured optimum. Zero removes this influence completely. |
| F4 | No kind-based eligibility | Source kind sets neither maximum article age nor word-count thresholds. It cannot require a minimum number of kinds, reject an article by itself, or override measured availability, article evidence, and duplicate rules. Resolve age and recency settings from the vertical planning policy in Table O, with the run override in Table R. |
| F5 | Labels can change | Source labels and summarization's article labels remain distinct. Do not persist a source label as an inferred article classification. Table N makes source labels and tier membership configuration data; contracts validate identifier shapes and registry references, not an enumerated member list. |
| F6 | Format is separate | Text and video describe content format, not publisher kind or article subject. Keep the concepts separate. This plan does not add video extraction or assume that today's format vocabulary is complete; adding a format later changes its contract and extraction path explicitly. |

```json
{
  "version": "2026-10-20",
  "harvest": {
    "concurrency": 24,
    "fetch_timeout_ms": 6000,
    "user_agent": "Mozilla/5.0 (compatible; YenIdhazhBot/2026.10; +https://github.com/miztiik/yen-idhazh)",
    "blocked_categories": ["links", "show types", "podcasts", "video", "galleries"]
  },
  "triage": {
    "min_words_article": 180,
    "min_words_abstract": 60,
    "blocked_http_statuses": [401, 403, 429],
    "max_age_hours": 24,
    "recency_half_life_hours": 18,
    "recency_weight": 0.6
  },
  "curate": {
    "article_limit": null,
    "source_authority_weight": 1.0,
    "base_source_allowance": 3,
    "bonus_uncovered_event_cluster": 1,
    "bonus_underrepresented_vertical": 1,
    "bonus_unique_evidence": 1,
    "soft_caps": {
      "max_source_share": 0.10,
      "max_parent_domain_share": 0.15,
      "max_event_cluster_items": 2,
      "min_distinct_sources": 12,
      "relaxation_order": ["distinct_sources", "source_share"]
    },
    "mmr_weights": {
      "lambda_source": 0.25,
      "lambda_source_kind": 0.05,
      "lambda_domain": 0.15,
      "lambda_vertical": 0.10,
      "lambda_desk": 0.10,
      "lambda_lens": 0.10,
      "lambda_event_type": 0.0,
      "lambda_event_cluster": 0.30,
      "lambda_entity": 0.0,
      "lambda_coverage": 0.10
    },
    "exploration_slot_share": 0.08
  },
  "vertical_overrides": {},
  "partition": {
    "default_strategy": "bin-pack",
    "default_shards": 4,
    "min_shards": 1,
    "max_shards": 8
  },
  "seal": {
    "dispatches_prefix": ["feed-ingest-plan", "dispatches"],
    "rejections_prefix": ["feed-ingest-plan", "rejections"],
    "compression": "snappy"
  },
  "workflow_reporting": {
    "enabled": false
  },
  "metrics": {
    "rolling_window_days": 7,
    "overlap_windows_days": [1, 3, 7],
    "top_source_counts": [1, 5, 10]
  }
}
```

---

## 3. Status Reckoner

### Table D - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Shared contracts, schemas, and identity types | 15 | A | DONE | supreme-train (plan-66-row-1) | - | 4729606a-ce50-4812-a45f-f4ac7314311b |
| 2 | Ledger registration and gardener compaction configuration | 1 | A | DONE | crispy-spoon (plan-66-row-2) | - | 6f739fa3-8ef9-40a7-830d-e1cc57927a46 |
| 3 | Dedicated feed ingest plan configuration file | 1 | A | DONE | vigilant-lamp (plan-66-row-3) | - | d8340612-ab74-49e7-99ac-19d9ce30e427 |
| 4 | Host hardware and environment identity service | 6 | B | IN-FLIGHT | curly-parakeet | - | bd6fe115-c522-4078-bb9f-e7c0e5eceb60 |
| 5 | Host CPU and memory profiling service | 1 | B | DONE | congenial-parakeet (plan-66-row-5) | - | c8de7d9d-dd55-4123-87fe-66095cc2aed5 |
| 6 | Reusable TypeScript ledger file writer | 1, 2, 16 | B | DONE | fictional-tribble | - | c1194122-86e6-45b4-85e9-e1bb61dbdca6 |
| 7 | RSS/Atom feed harvest and DOM text extraction | 3, 6 | B | IN-FLIGHT | redesigned-doodle | - | da505804-6ce7-4f03-aa0b-25bab323ba53 |
| 8 | Candidate triage screening with Parquet rejection ledger | 6, 7 | C | IN-FLIGHT | scaling-memory | - | d50de7c8-1c6a-4074-a390-25a077ae0ba8 |
| 9 | Set-aware editorial portfolio curation | 8 | D | IN-FLIGHT | bookish-carnival | - | 34c330c1-9d30-4222-8fa6-4e28e58a165e |
| 10 | Contextual bin-packing partitioner with feature flag | 9 | E | IN-FLIGHT | Session `86a9018f-dadb-4181-b82c-ca7fe9347116` builds on tested harvest foundation; integrates tested curation before final checks; historical completion proof remains unresolved below | - | - |
| 11 | Core plan engine entrypoint, dual-mode runner, and sealing | 6, 10 | F | IN-FLIGHT | plan-66-api-cli-runner | - | ec780a10-5ab0-4ad7-a4e1-c36db811fbd7 |
| 12 | Isolated CI test workflow and verification suite | 4, 5, 11, 14 | G | IN-FLIGHT | isolated workflow child | - | 31c9fcf0-3abc-41ff-a70e-624a4b419ee0 |
| 13 | Phase 2 publication reconciliation and rolling diversity metrics | 12, 14 | H | IN-FLIGHT | publication observer child; independent history/publication modules first; shared metrics wait for Row 14 handoff | - | 79cc9244-f9d2-4223-905f-69fa0221f706 |
| 14 | Phase 1 source-run audit and three-axis evidence | 11 | G | IN-FLIGHT | audit recorder child | - | f197c411-a156-460a-a772-f5205c11be1d |
| 15 | Config-driven source registries and compatible readers | - | A | DONE | fluffy-adventure (feed-registry-migration) | - | f7f18c64-813b-4a13-b421-1cd67b951db6 |
| 16 | Public data-explorer enrollment and nested ledger delivery | 2 | B | DONE | reimagined-enigma | - | 2b6ac0cc-60a2-4c13-a67a-8d8ec21a4fc1 |

---

## 4. Row #1 - Shared contracts, schemas, and identity types

- **Scope:** Declare persisted rows and typed stage/audit events in Python first, bind the small TypeScript copies to those contracts, and add reader support for the proposed TypeScript writer provenance before any TypeScript writer emits files.
- **Files touched:**
  - `backend/idhazh/contracts/file_envelope.py`
  - `backend/idhazh/contracts/feed_ingest_candidate.py`
  - `backend/idhazh/contracts/feed_ingest_dispatch.py`
  - `backend/idhazh/contracts/feed_ingest_rejection.py`
  - `backend/idhazh/contracts/feed_ingest_source_run.py`
  - `backend/idhazh/contracts/feed_ingest_article_assessment.py`
  - `backend/idhazh/contracts/feed_ingest_diversity.py`
  - `backend/idhazh/contracts/feed_ingest_editorial_selection.py`
  - `backend/idhazh/contracts/feed_ingest_event.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/tests/contracts/test_feed_ingest_contracts.py`
  - `backend/tests/ledger/test_typescript_writer.py`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/contracts/persistence.md`
  - `packages/common-contracts/package.json`
  - `packages/common-contracts/tsconfig.json`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/version.ts`
  - `packages/common-contracts/src/schemas/source.schema.ts`
  - `packages/common-contracts/src/schemas/candidate.schema.ts`
  - `packages/common-contracts/src/schemas/dispatch.schema.ts`
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `packages/common-contracts/src/schemas/rejection.schema.ts`
  - `packages/common-contracts/src/schemas/telemetry.schema.ts`
  - `packages/common-contracts/src/schemas/partition.schema.ts`
  - `packages/common-contracts/src/schemas/source-run.schema.ts`
  - `packages/common-contracts/src/schemas/article-assessment.schema.ts`
  - `packages/common-contracts/src/schemas/diversity.schema.ts`
  - `packages/common-contracts/src/schemas/editorial-selection.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/test/rejection.test.ts`
- **Acceptance gates:** Local: use the shared test selector, strict TypeScript checks, and focused Python/TypeScript contract tests. CI: the full suite, including the older-envelope read fixtures.
- **Oracle:** Named binding tests compare Python and TypeScript fields, vocabularies, and footer metadata; the Python reader accepts the declared TypeScript provenance and still reads older files. This does not prove the TypeScript Parquet engine writes compatible bytes; Row #6 does that.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Keep Pydantic as the source of persisted contracts; TypeScript copies are strict, hand-written, and bound by field-set and vocabulary tests. Version and changelog persisted changes under CLAUDE.md section 11. | CLAUDE.md sections 1a and 11; schemas.md |
| 2 | Enforce strict Zod validation without silent stripping for candidate inputs, dispatches, and rejections | Plan proposal |
| 3 | Declare the rejection record and reason vocabulary in Table G in Python, with strict TypeScript copies and binding tests; record all terminal rejections, not only screening failures. | Owner request; schemas.md |
| 4 | Keep source_id, vertical, nullable assigned desk, lens IDs, content event types, event-cluster identity, and entity IDs as distinct typed fields in the new candidate/assessment contracts. Record label/matcher origin and version; do not fill one dimension by copying another. Preserve existing payload field spellings through explicit readers rather than a repository-wide rename. | Owner selected Table T's independent terminology |
| 4 | Declare Table J's event envelope and typed payload variants before stage emitters. Keep the event contract independent of its audit recorder and optional GitHub adapter. | CLAUDE.md Guardrail #3 and section 1a |

### Table G - Rejection record contract

| # | Requirement | Contract |
| --- | --- | --- |
| G1 | Version and ownership | `CandidateRejectionRecord` is declared in `backend/idhazh/contracts/feed_ingest_rejection.py` as a Pydantic Contract with version `"2026-10-20"` and a changelog entry. Its TypeScript copy below is not the source of truth. Integer `20261020` is not a valid persisted version. |
| G2 | Stage | Use the exact action names in Table E, not a second `harvest`/`triage`/`curate` vocabulary. Each reason must be valid for the stage that actually rejects the input. |
| G3 | Feed-level failure | A failed request or empty/corrupt feed may have no article. Use `subject: "feed"`, the configured `feed_url`, and null article identity/title fields. Never manufacture an article URL or hash. Article-level failures use `subject: "article"` and require the canonical URL, recomputed URL key, and title, except that `MISSING_REQUIRED_FIELDS` preserves whichever fields are actually available. Both variants have the same nullable Parquet columns. |
| G4 | Details | Use a fixed typed details struct, not `z.record(z.unknown())`. Numeric observations are finite and use the units in their names. Add a typed field through the versioned contract when another rejection needs it; do not turn logs or source text into unbounded maps. |
| G5 | Time and coverage | `rejected_at` is an ISO-8601 UTC instant ending in `Z`; `date` is its UTC day. The run's correlation identity remains separate from article identity. The ledger writer supplies its normal row identity cells. |
| G6 | One terminal result | Every rejected feed or candidate gets one terminal rejection per attempt, with the deciding reason and measurements. A candidate admitted to curation and later cut is recorded there, not falsely recorded as a screening failure. Retries use normal ledger attempt settlement. |
| G7 | Before classification | `STALE_MAX_AGE_EXCEEDED` records the actual resolved age cutoff. `STALE_HALF_LIFE_DECAY` is retained from the requested reason vocabulary but has no enabled emission rule: the current proposal uses decay for ranking, not a separate rejection threshold. Enabling it needs an explicit policy and configured threshold; never substitute it for an age rejection. |
| G8 | History rules | `DUPLICATE_CANONICAL_URL` needs actual duplicate evidence, not first sight alone. `ROLLING_HISTORY_REPEAT` requires a published-history match and records its configured lookback; it is not synonymous with having fetched the URL. Do not add a seven-day constant to code. |
| G9 | Required evidence | HTTP failures require `http_status`; timeouts require `timeout_ms`; stubs require `words_found` and `words_required`; age rejections require `age_hours` and `max_age_hours`. Quota and ranking cuts require the deciding observed value and limit. Add reason-specific validation beyond the base field checks below. |
| G10 | Per-source versus per-file | Rejection rows carry `source_id`; one run file may contain several sources. Per-source totals belong in the source-run ledger in Table I, not a directory or file per source. Counts, source status, and reasons are typed Parquet columns or list/struct cells, never extra FileEnvelope footer keys or JSON strings inside Parquet. |
| G11 | No invented limits | `DESK_QUOTA_EXCEEDED`, `KIND_QUOTA_EXCEEDED`, and `PUBLICATION_BUDGET_EXCEEDED` are recognized diagnostic reasons, not permission to introduce those caps. They may be emitted only by a named enabled rule that actually refused the item; kind caps remain disabled by Table F. Lack of a lead slot is not a publication rejection. |
| G12 | Candidate identity | Mint candidate_id from validated run identity, source ID, and parsed-entry ordinal before article-field validation. It distinguishes two offered entries with the same URL and remains available when required article fields are missing. Feed-level failures have null candidate_id. Logical row keys include source, candidate identity or feed subject, stage, and observation phase where applicable. Settle the highest complete attempt for the run/source/phase before counting its rows; never mix an earlier attempt's leftover candidates into a later attempt. |

```ts
import { z } from "zod";

export const DropReasonSchema = z.enum([
  "SOURCE_INACTIVE",
  "FETCH_FAILED",
  "FETCH_FAILED_HTTP",
  "FETCH_TIMEOUT",
  "PAYWALL_OR_BLOCKED",
  "FEED_PARSE_FAILED",
  "FEED_EMPTY",
  "MISSING_REQUIRED_FIELDS",
  "CATEGORY_EXCLUDED",
  "STUB_CONTENT",
  "STALE_MAX_AGE_EXCEEDED",
  "STALE_HALF_LIFE_DECAY",
  "DUPLICATE_CANONICAL_URL",
  "EVENT_CLUSTER_SIMILARITY",
  "SOURCE_QUOTA_EXCEEDED",
  "DESK_QUOTA_EXCEEDED",
  "KIND_QUOTA_EXCEEDED",
  "MMR_PORTFOLIO_CUTOFF",
  "REPLACED_BY_CARRIER",
  "PUBLICATION_BUDGET_EXCEEDED",
  "ROLLING_HISTORY_REPEAT",
]);

export type DropReason = z.infer<typeof DropReasonSchema>;

const nonNegative = z.number().finite().nonnegative();
const positive = z.number().finite().positive();
const urlKey = z.string().regex(/^[0-9a-f]{64}$/);

export const RejectionDetailsSchema = z.object({
  http_status: z.number().int().min(100).max(599).nullable().default(null),
  timeout_ms: positive.nullable().default(null),
  words_found: nonNegative.int().nullable().default(null),
  words_required: positive.int().nullable().default(null),
  age_hours: nonNegative.nullable().default(null),
  max_age_hours: positive.nullable().default(null),
  observed_value: z.number().finite().nullable().default(null),
  limit: z.number().finite().nullable().default(null),
  matched_url_key: urlKey.nullable().default(null),
  history_window_days: positive.int().nullable().default(null),
}).strict();

export const CandidateRejectionRecordSchema = z.object({
  version: z.literal("2026-10-20"),
  date: z.string().date(),
  correlation_id: z.string().min(1),
  source_id: z.string().min(1),
  feed_url: z.string().url(),
  subject: z.enum(["feed", "article"]),
  candidate_id: z.string().min(1).nullable(),
  url_key: urlKey.nullable(),
  canonical_url: z.string().url().nullable(),
  title: z.string().nullable(),
  categories: z.array(z.string()),
  stage: z.enum([
    "harvest-feeds",
    "screen-article-candidates",
    "curate-article-portfolio",
  ]),
  drop_reason: DropReasonSchema,
  details: RejectionDetailsSchema,
  rejected_at: z.string().datetime(),
}).strict().superRefine((record, context) => {
  const hasArticle = record.subject === "article";
  if (hasArticle === (record.candidate_id === null)) {
    context.addIssue({
      code: "custom",
      path: ["candidate_id"],
      message: hasArticle ? "Required for a candidate" : "Must be null for a feed",
    });
  }
  for (const field of ["url_key", "canonical_url", "title"] as const) {
    if (
      (!hasArticle && record[field] !== null) ||
      (hasArticle && record.drop_reason !== "MISSING_REQUIRED_FIELDS" &&
        record[field] === null)
    ) {
      context.addIssue({
        code: "custom",
        path: [field],
        message: hasArticle ? "Required for an article" : "Must be null for a feed",
      });
    }
  }
  if (record.date !== record.rejected_at.slice(0, 10)) {
    context.addIssue({
      code: "custom",
      path: ["date"],
      message: "Must match the UTC rejection day",
    });
  }
});

export type CandidateRejectionRecord =
  z.infer<typeof CandidateRejectionRecordSchema>;
```

### Table S - Feed rejection example: one logical Parquet row

| # | Column | Parquet value type | Example value |
| --- | --- | --- | --- |
| S1 | version | string | 2026-10-20 |
| S2 | date | string, UTC day | 2026-10-20 |
| S3 | correlation_id | string | 2026-10-20-123456789 |
| S4 | source_id | string | fixture-feed |
| S5 | feed_url | string | https://example.org/feed.xml |
| S6 | subject | string, contract vocabulary | feed |
| S7 | candidate_id | nullable string | null |
| S8 | url_key | nullable string | null |
| S9 | canonical_url | nullable string | null |
| S10 | title | nullable string | null |
| S11 | categories | list of strings | empty list |
| S12 | stage | string, contract vocabulary | harvest-feeds |
| S13 | drop_reason | string, contract vocabulary | FEED_EMPTY |
| S14 | details | typed struct | every declared nullable observation is null |
| S15 | rejected_at | string, UTC instant | 2026-10-20T19:40:00Z |
| S16 | Writer identity columns | the shared ledger's declared types | supplied by the writer, not fabricated by the fixture |

### Table H - Rejection gates

| # | Gate | Expected result |
| --- | --- | --- |
| H1 | Python/TypeScript binding | Equal field sets, reason and stage vocabularies, defaults, nullable fields, and nested detail types. Reject numeric versions, unknown fields, wrong-stage reasons, missing required evidence, and non-UTC timestamps. |
| H2 | Feed failure | Generated fixtures distinguish inactive sources, HTTP/non-HTTP failures, timeouts, invalid XML, and valid empty feeds. Each has a typed feed-level reason and null article fields. A malformed candidate retains its available fields under the missing-fields reason, without a fabricated URL or hash. |
| H3 | Article failure | A short real fixture article produces `STUB_CONTENT` with actual words found and configured words required; its canonical URL and hash agree with Python's identity function. |
| H4 | Persistence | Build the Table S feed example and an article rejection with the real shared writer. Assert `.parquet` data-file names and Parquet file bytes, then read through the Python ledger reader, retaining typed details and canonical digests. No JSON/JSONL rejection data file is written; contracted index/listing files are not row-ledger data. |
| H5 | Pipeline coverage | Harvest, screening, and curation each persist terminal rejections through the shared package. Sum admitted and rejected inputs per stage without double-counting a candidate dropped earlier. |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Semver or integer versioning (e.g. `20261020`) | Conflicts with the persisted date-stamp contract | Requires an owner-approved contract and reader migration | CLAUDE.md section 11 |
| 2 | Independent Zod definitions as the source of persisted shapes | Creates a second authority that can drift from Python readers | Requires changing the contract ownership rule and migrating every affected reader | CLAUDE.md section 1a; schemas.md |

---

## 5. Row #2 - Ledger registration and gardener compaction configuration

- **Scope:** Register editorial selections, dispatches, rejections, source-run summaries, article assessments, and diversity readings as separate ledgers in the feed-ingest-plan family, plus their gardener compaction configurations.
- **Settlement:** Preserve the original run and attempt identity for every feed-ingest-plan row until complete-attempt selection. The existing ledger settlement drops lower attempts before applying business keys, so add a feed-ingest-only settlement path that retains attempts and deduplicates within each `(run_id, attempt)` by the declared business key. Support trusted declared dotted paths for nested fields such as `content.candidate_id`; do not change settlement for other ledgers.
- **Files touched:**
  - `config/ledgers.json`
  - `config/idhazh_gardener.json`
  - `config/gardener/compact-feed-ingest-plan-dispatches.json`
  - `config/gardener/compact-feed-ingest-plan-editorial-selections.json`
  - `config/gardener/compact-feed-ingest-plan-rejections.json`
  - `config/gardener/compact-feed-ingest-plan-source-runs.json`
  - `config/gardener/compact-feed-ingest-plan-article-assessments.json`
  - `config/gardener/compact-feed-ingest-plan-diversity.json`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/arrow_schema.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/ledger/staging.py`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_ledger_name.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`
  - `backend/tests/ledger/test_arrow_schema.py`
  - `backend/tests/ledger/test_feed_ingest_ledgers.py`
  - `backend/tests/contracts/test_frontend_index_shapes.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/workflows/test_ledger_door_jobs.py`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/persistence.md`
  - `config/appearance.json`
  - `frontend/src/lib/server/config.ts`
  - `docs/reference/benchmarks/address-length-on-pages.md`
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `backend/tests/council/_imports.py`
- **Acceptance gates:** Local: shared test selector and focused `backend/tests/contracts/test_ledger_registry.py` / `test_ledger_name.py` cases. CI: full suite. Load the authored configuration through the repository's existing registry readers, not a new generated schema file. Verify attempts and their original identities survive raw settlement and real compact/read/repack cycles; a newer partial attempt must not erase an older complete attempt, and nested dispatch keys must settle correctly. Map UUID fields to their JSON string representation in Arrow and test a UUID round-trip through the schema adapter. Preserve every other ledger's existing settlement behavior. Keep the unchanged `frontend/tests/console-data-explorer-address.spec.ts` green: with 31 ledgers the editor cap decreases from 6942 to 6855 characters, 87 characters (about 1.3 percent), to keep all-ledger share links inside the measured 8192-byte request limit.
- **Oracle:** Registry fixtures confirm every declared feed-ingest ledger has its row contract, settlement key, valid prefix, and compaction configuration. The TypeScript envelope vocabulary agrees with Python, and the council's bounded dependency inventory includes the new row contracts without relaxing its import boundary. The registry description retains its meaning while fitting the unchanged payload ceiling and twice-gzipped-size assertion. A bounded retry fixture with an earlier attempt containing candidates A and B and a later partial attempt containing only A retains both attempts through compaction; complete-attempt selection can choose the later attempt without inheriting B. A later complete empty attempt is represented by explicit source-run evidence, not inferred from missing dispatch rows. This does not prove a TypeScript writer can encode that contract; Row #6 verifies it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Enroll each ledger declared in Table I, Table L, and Table P under family `feed-ingest-plan`; register its row contract, settlement key, prefix, and compaction task before writing. Use `source-runs`, `article-assessments`, `diversity`, and `editorial-selections` as the new suffixes beneath the family prefix. | Owner requested the complete audit and managed retention; persistence.md |
| 2 | Store rejections as Parquet files under `state/raw/feed-ingest-plan/rejections/` with `FileEnvelope` footers | Plan proposal |
| 3 | Add the new ledger-name members and row/settlement bindings, and enroll every compaction declaration in config/idhazh_gardener.json's explicit task_names list. A declaration file alone does not schedule a task. Use each full ledger prefix with slashes replaced by hyphens for the compaction name. | Verified ledger registry, keys.py, and gardener task manifest |
| 4 | Add every new ledger to staging.py REGISTRY and the frontend LEDGER_NAMES/LEDGER_FOLDERS bindings. Name the planned TypeScript writer explicitly, with no production digest commit labels while the isolated workflow is its only caller. Registry vocabulary/path bindings land here; public delivery lands in Row #16 before writers. | ledger-registry.md onboarding; existing finite staging table |
| 5 | Enroll the tasks in the named gardener retention test inventory and use the approved live chain: compact_after_days 1, daily_keep_days 45, monthly_keep_days 93, monthly_window forever, yearly_keep_months 36, yearly_prune_enable true. Follow the existing dry-run-to-live approval rule; do not invent a separate retention policy for planner text or audit rows. | ledger-registry.md onboarding; owner-approved retention chain |
| 6 | Feed-ingest settlement preserves each original run/attempt and deduplicates rows only within that attempt by its declared business key; trusted dotted paths may name nested fields. Existing ledgers retain their current settlement. Table J selects the complete attempt later: an incomplete newer attempt cannot erase an older complete attempt, while an explicitly recorded complete empty attempt supersedes it. Test raw settlement and real compact/read/repack cycles. UUID contract fields use their JSON string representation in Arrow, so the reader validates their version after loading. | Table G candidate identity; reader-before-writer settlement contract; Pydantic JSON serialization |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Storing rejections as raw `.jsonl` files outside the ledger door | Bypasses the chosen Parquet audit and gardener compaction | Separate enrollment and lifecycle handling | Owner selected Parquet for this plan |

---

## 6. Row #3 - Dedicated feed ingest plan configuration file

- **Scope:** Create `config/feed-ingest-plan.json` with global policies and typed per-vertical planning overrides, and resolve each candidate's screening/scoring settings by Table O before execution.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `backend/idhazh/contracts/knobs/feed_ingest.py`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/policy.schema.ts`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/tsconfig.json`
  - `services/feed-ingest-plan/bun.lock`
  - `backend/tests/contracts/test_feed_ingest_config.py`
  - `services/feed-ingest-plan/src/config/resolve-policy.ts`
  - `services/feed-ingest-plan/test/policy.test.ts`
  - `docs/architecture/sources/feed-ingest-policies.md`
- **Acceptance gates:** Local: shared selector, strict TypeScript checks, Python/TypeScript config-reader binding, and policy fixtures. CI: full suite. Add a vertical in taxonomy and a matching planning patch without editing source; verify the exact resolved policy for that vertical, unchanged policies for other verticals, run-override precedence, invalid references, and inherited fields.
- **Oracle:** Identical candidate context under configurations differing in one policy field resolves to the expected effective values, with other verticals unchanged. This proves policy resolution, not final admission or ranking; Rows #8 and #9 verify those behavior changes once their real stages exist.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Decentralize planner configuration into titled `config/feed-ingest-plan.json` rather than bloating `idhazh.json` | Plan proposal; CLAUDE.md section 1a |
| 2 | Make article and abstract word count thresholds configurable variables with defaults 180 and 60 | Plan proposal |
| 3 | Resolve the age cutoff by Table R; keep source-kind influence limited to Table F's configurable selection penalty. Neither setting requires an article classification from summarization. | Owner clarification; FeedDef.kind |
| 4 | `workflow_reporting.enabled` defaults to false. It controls only the external reporting adapter. Removal condition: delete this key, its adapter, tests, and workflow invocation together when development reporting is no longer needed. | Owner request; default proposed for development-only reporting |
| 5 | Declare Table O's planning policies and Table T's independent dimensions before logic. Keep canonical definitions on their owning pages; update the plan's new names consistently, without renaming historical payload keys. Do not implement a generic rules language, label-specific branches, or arbitrary expression evaluation. | Owner selected distinct, independently configurable terms |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Hardcoding word count limits in TypeScript source code | Violates CLAUDE.md Guardrail #6 (no hard coding) | Code changes required for editorial adjustments | CLAUDE.md Guardrail #6 |

---

## 7. Row #4 - Host hardware and environment identity service

- **Scope:** Implement `services/host-fingerprints` as an independent Bun API and CLI that collects the existing HostFingerprintRow and persists it through the shared ledger writer to the existing host-fingerprint ledger when host telemetry is enabled.
- **Files touched:**
  - `services/host-fingerprints/package.json`
  - `services/host-fingerprints/bun.lock`
  - `services/host-fingerprints/tsconfig.json`
  - `services/host-fingerprints/src/config.ts`
  - `services/host-fingerprints/src/index.ts`
  - `services/host-fingerprints/src/api/server.ts`
  - `services/host-fingerprints/src/api/routes/fingerprint.route.ts`
  - `services/host-fingerprints/src/persist-fingerprint.ts`
  - `services/host-fingerprints/src/collect-fingerprint.ts`
  - `services/host-fingerprints/src/inspect/cpu-model.ts`
  - `services/host-fingerprints/src/inspect/runner-env.ts`
  - `services/host-fingerprints/src/inspect/cpu-topology.ts`
  - `services/host-fingerprints/src/inspect/cpu-capacity.ts`
  - `services/host-fingerprints/src/inspect/hardware-identity.ts`
  - `services/host-fingerprints/src/inspect/bounded-input.ts`
  - `services/host-fingerprints/src/inspect/placement.ts`
  - `services/host-fingerprints/src/inspect/copy-bandwidth.ts`
  - `services/host-fingerprints/test/fixture.ts`
  - `services/host-fingerprints/test/fingerprint.test.ts`
  - `services/host-fingerprints/test/fingerprint-persistence.test.ts`
  - `packages/common-contracts/src/schemas/host-fingerprint.schema.ts`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/test/host-fingerprint.test.ts`
  - `config/host-fingerprints.json`
  - `tests/fixtures/host-fingerprints/linux-inputs.json`
  - `tests/fixtures/host-fingerprints/host-schema.json`
  - `.github/workflows/ci.yml` (named Bun service checks and tests)
  - `docs/reference/host-metrics.md`
- **Acceptance gates:** Local: inspect the shared selector without launching Python-backed groups, run strict TypeScript checks, bounded Linux input fixtures, API/CLI persistence tests, and recorded HostFingerprintRow compatibility checks in TypeScript. Existing repository CI remains authoritative for its unchanged suites. Verify configured-off behavior, null unavailable measurements, atomic-write failure propagation, and retry settlement without rewriting historical files.
- **Oracle:** An API or CLI collection creates a valid HostFingerprintRow in the registered ledger, and TypeScript Parquet readback returns it with the expected pipeline/task/run/shard identity and recorded schema; invalid requests and failed writes cannot return persisted success. This does not certify Linux hardware collection from a Windows fixture run or execute the Python reader.

Preflight: the listed TypeScript host schema is new, not an existing import.
Include its public export and a named TypeScript recorded-schema check when pricing the
supporting paths before dispatch. The service also needs a lockfile, authored
listener/read controls, and bounded recorded Linux inputs. Preserve the
existing fingerprint algorithm and observability controls; a nullable field
does not authorize skipping its collector.

Supporting scope for the existing service: the lockfile owns its install;
validated listener/read controls belong in its named config; bounded input,
topology, capacity and identity units keep collection out of routing code.
The public contract export and TypeScript fixture checks must cover the full
host row, not a field-stripping projection. The named fixture files hold
bounded Linux readings and recorded schema expectations. CI adds Bun service
checks only, with no new Python setup or test invocation. These paths implement
the existing host-service scope, not new persisted fields or a new algorithm.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Decouple host fingerprinting completely from feed planning | Plan proposal |
| 2 | Parse `/proc/cpuinfo` directly on Linux with graceful fallback on macOS/Windows development environments | Plan proposal |
| 3 | Persist to the caller's state root under `raw/host-fingerprint/<YYYY>/<MM>/<DD>/<file_id>.parquet`; the production root is `state/`. Keep existing compaction under `state/compact/host-fingerprint/` and the existing registry entry, following Table A's state ledger layout. | Owner correction; host-metrics.md; config/ledgers.json |
| 4 | Use `POST /api/2026-10-20/fingerprint` for collection plus persistence and the same operation from the CLI. Return the recorded row and repository-relative file paths only after the write succeeds. Keep GET health or inspection requests free of file-write side effects. | Plan proposal implementing owner-required persistence |
| 5 | Reuse the existing HostFingerprintRow contract, versioned fingerprint algorithm, nullable measurements, and observability controls. Caller-supplied pipeline/task/run/shard context is validated separately from hardware data. Missing observations stay null, never invented values. | host-metrics.md; HostFingerprintRow |
| 6 | Reuse the package from Row #6; do not embed another Parquet writer in the service. The caller remains responsible for committing returned files. The isolated verification workflow uses a run-local state root so it does not commit trial machine records to production. | Owner request; persistence.md |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Invoking Python `host_telemetry_control.py` via subprocess | Retains another runtime in the TypeScript collection path | Compare paired runner timings to price the startup cost; no timing has been measured for this plan | Plan proposal |

---

## 8. Row #5 - Host CPU and memory profiling service

- **Scope:** Implement `services/host-probes` as an independent Bun microservice and CLI exposing `/api/2026-10-20/sample` to measure CPU utilization (user, system, idle, iowait, steal) and memory metrics (`/proc/meminfo`, `/proc/vmstat`). Read the sampling interval and loopback listener settings from `config/host-probes.json`; keep Linux input parsing separate from sampling and request handling.
- **Files touched:**
  - `services/host-probes/package.json`
  - `services/host-probes/tsconfig.json`
  - `services/host-probes/bun.lock`
  - `services/host-probes/src/config.ts`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/server.ts`
  - `services/host-probes/src/probe/proc-reader.ts`
  - `services/host-probes/src/probe/cpu-sampler.ts`
  - `services/host-probes/src/probe/memory-probe.ts`
  - `services/host-probes/src/probe/sample-host.ts`
  - `services/host-probes/test/probe.test.ts`
  - `config/host-probes.json`
  - `tests/fixtures/host-probes/meminfo.txt`
  - `tests/fixtures/host-probes/vmstat.txt`
  - `docs/reference/host-metrics.md`
- **Acceptance gates:** Strict TypeScript check and `bun test` in `services/host-probes/`; recorded `/proc` fixtures cover parsing and periodic sampling confirms delta calculations. On non-Linux systems or when counters are reset or unchanged, return unavailable CPU percentages with a reason rather than a fabricated zero reading.
- **Oracle:** Returns memory total, free, and available in KB, and nonnegative CPU percentages for user (including nice), system (including irq and softirq), idle, iowait, and steal that sum to 100 within 1% rounding error. Exclude guest counters already included in user/nice totals.
- **Shared-file coordination:** Row #4 also edits `docs/reference/host-metrics.md`. Do not run Row #4 concurrently with Row #5 while both are active; if Row #4 becomes ready first, record Row #5 as an additional dependency before dispatch.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use differential `/proc/stat` delta sampling rather than blocking sleep calls | Plan proposal |
| 2 | Expose both HTTP REST endpoint (`/api/2026-10-20/sample`) and one-shot CLI (`--sample`) | Plan proposal |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Bundling CPU/memory sampling inside the feed ingest process | Couples reusable collection to one stage | Extract the collector before another stage can use it | Plan proposal |

---

## 9. Row #6 - Reusable TypeScript ledger file writer

- **Scope:** Implement `packages/ledger-file-writer` as an importable TypeScript package that any API or CLI can use to validate registered ledger rows, create identifiers, attach envelope metadata, and atomically write raw or compact Parquet files.
- **Files touched:**
  - `packages/ledger-file-writer/package.json`
  - `packages/ledger-file-writer/tsconfig.json`
  - `packages/ledger-file-writer/bun.lock`
  - `packages/ledger-file-writer/src/index.ts`
  - `packages/ledger-file-writer/src/uuid/unit-id.ts`
  - `packages/ledger-file-writer/src/uuid/file-id.ts`
  - `packages/ledger-file-writer/src/parquet/arrow-builder.ts`
  - `packages/ledger-file-writer/src/parquet/wasm-serializer.ts`
  - `packages/ledger-file-writer/src/parquet/envelope-footer.ts`
  - `packages/ledger-file-writer/src/parquet/row-digest.ts`
  - `packages/ledger-file-writer/src/ledger-types.ts`
  - `packages/ledger-file-writer/src/row-schema.ts`
  - `packages/ledger-file-writer/src/registration.ts`
  - `packages/ledger-file-writer/src/row-identity.ts`
  - `packages/ledger-file-writer/src/ledger-paths.ts`
  - `packages/ledger-file-writer/src/atomic-file.ts`
  - `packages/ledger-file-writer/src/render-ledger-file.ts`
  - `packages/ledger-file-writer/src/persist-raw.ts`
  - `packages/ledger-file-writer/src/persist-compact.ts`
  - `packages/ledger-file-writer/src/persist-ledger.ts`
  - `packages/ledger-file-writer/test/uuid.test.ts`
  - `packages/ledger-file-writer/test/parquet-parity.test.ts`
  - `packages/ledger-file-writer/test/persist-ledger.test.ts`
  - `tests/fixtures/ledger-file-writer/host-fingerprint-row.json`
  - `tests/fixtures/ledger-file-writer/feed-ingest-dispatch-row.json`
  - `tests/fixtures/ledger-file-writer/dispatch-arrow-schema.json`
  - `.github/workflows/ci.yml` (named TypeScript package checks and tests)
  - `docs/architecture/contracts/identity.md`
  - `docs/architecture/contracts/persistence.md`
- **Acceptance gates:** Local: inspect the shared selector without launching Python-backed groups, run strict TypeScript checks and package tests with real Parquet readback against bounded recorded compatibility fixtures. CI executes the named Bun checks and tests. Exercise two distinct registered ledger contracts through the same public interface, including raw and compact writes, zero rows, nullable/list fields, invalid rows, and an interrupted write. Compare the nested dispatch Parquet schema against `tests/fixtures/ledger-file-writer/dispatch-arrow-schema.json`, an independently recorded list of native column types and nullability, including nested/list children and identity columns. The host-fingerprint case narrows to writer-identity collision fields and does not claim full hardware-row validation or retention; that coverage belongs to Row #4.
- **Oracle:** TypeScript reads the actual Parquet footer, validates its envelope and native columns, reconstructs stored rows, and recomputes their canonical digest. Recorded fixtures independently pin schema, canonical bytes and identifiers to the existing contract. This does not execute the Python reader, prove speed or require byte-identical output from different Parquet engines.
- **Preflight correction:** The identity page currently names a TypeScript implementation under `packages/common-contracts/src/identity/` that does not exist. The writer owns the new implementation. Correct that page's namespace and hash-bit descriptions against `backend/idhazh/ledger/filenames.py`; do not change the Python identity algorithm. The package lock and bounded recorded fixtures support the declared package and compatibility checks.

Canonical-byte preflight: sorted `JSON.stringify` is not Python's row
serialization. A fixed comparison produced Python numbers `1.0`,
`1e-07`, `1e+20`, and `-0.0`, while Node produced `1`, `1e-7`,
`100000000000000000000`, and `0`. Python also escapes non-ASCII text.
Use the declared scalar types and actual stored rows to reproduce those bytes.
Include these values, Unicode, nested lists, and nulls in the canonical-byte
vector; do not change the Python digest rules or reject valid floats to pass it.

Identity-page preflight also found two unrelated identities described as one:
the older `.github/scripts/ai-pipeline.ts` event helper returns an `evt_`
UUID string, while the declared `FeedIngestEvent.event_id` is a SHA-256
hexadecimal string in both languages. Distinguish these existing contracts
when correcting the identity page. Do not copy the older helper into planner
events or change their declared type. Rejections do not declare an event ID,
and correlation IDs are not undeclared file-envelope metadata.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Evaluate `apache-arrow` + `parquet-wasm` for Parquet writing; use the configured ledger compression rather than a caller-specific constant. Beneficiary: every TypeScript ledger producer. Record install size, loaded WASM memory, and runner time before dependency adoption. | Plan proposal; persistence.md |
| 2 | Match Python `filenames.py` for UUIDv5 unit identity and UUIDv8 file identity, including generic pipeline/task context. | identity.md; filenames.py |
| 3 | Write separate UTF-8 key-value entries matching `FileEnvelope.as_metadata`, not one JSON object. Preserve renamed metadata keys, optional-key omission, and zero-padded attempt/shard strings. Read row count from the Parquet footer, not an extra envelope key. | file_envelope.py; persistence.md |
| 4 | Hash the stored rows, including stamped identity cells, in file order using the exact canonical JSON-lines bytes from `json_lines.rows_bytes`: sorted object keys, ASCII escaping, compact separators, and one LF per row. It is neither a hash of Parquet bytes nor an unspecified raw-row hash. Test Unicode, nested values, floats, and nullable cells against the recorded canonical-byte vector. | persist.py; json_lines.py |
| 5 | Accept ledger, row contract, rows, output root, UTC coverage period, writer context, and ledger settings. Derive paths and identifiers inside the package. Keep feed selection, HTTP serving, and GitHub reporting outside it. Use temporary-file-plus-rename writes. | Owner selection: shared package; persistence.md |
| 6 | Validation checks row and envelope contracts before writing. TypeScript tests read actual Parquet through WASM and Arrow, then check the footer and typed columns against bounded compatibility fixtures. The owner override prevents executing Python from this package's test and CI paths, so these checks do not claim current Python reader execution. Neither check encrypts, signs, or makes a file tamper-proof. | Clarification of the package contract; owner override |
| 7 | Raw writes stamp row identity; compact writes preserve original row identity and record the compactor only in the envelope. Accept tier, period, and source-file count under the existing persistence rules; do not embed a compaction schedule or retention policy in the package. | persistence.md |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A standalone ledger-writing HTTP service | TypeScript reuse needs an import, not another running process | Server lifecycle, request validation, and filesystem authorization; worthwhile only if non-TypeScript remote callers need it | Owner selected the shared package |
| 2 | Python subprocess for each Parquet write | Keeps an extra runtime in every caller's write path | Measure paired runner writes to price startup and serialization; no timing has been measured for this plan | Plan proposal |
| 3 | One JSON-serialized FileEnvelope value in the footer | The current reader expects separate declared metadata entries | Requires an owner-approved envelope migration across readers; unnecessary for TypeScript reuse | file_envelope.py; persistence.md |

---

## 10. Row #7 - RSS/Atom feed harvest and DOM text extraction

- **Scope:** Implement `services/feed-ingest-plan/src/harvest-feeds/` to concurrently poll configured feeds, extract article text and categories, and persist feed-level or article-level fetch rejections using the contract in Table G.
- **Files touched:**
  - `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/url-cleaner.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/dom-extractor.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/record-rejection.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-types.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/transport.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/safe-target.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/sanitize-text.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/load-harvest-inputs.ts`
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `tests/fixtures/feed-ingest-plan/harvest-rss.xml`
  - `tests/fixtures/feed-ingest-plan/harvest-atom.xml`
  - `tests/fixtures/feed-ingest-plan/harvest-article.html`
  - `tests/fixtures/feed-ingest-plan/harvest-responses.json`
  - `tests/fixtures/feed-ingest-plan/harvest-safety.json`
  - `docs/architecture/sources/feed-harvesting.md`
- **Acceptance gates:** Local: shared selector and `bun test` over named recorded RSS/Atom and HTML fixtures, with no external network. Verify valid candidates, categories, text, and typed fetch/parse failures. CI: full suite. Live-source availability is an observation of a separately dispatched isolated run, not a repeatable test gate.
- **Oracle:** Pre-fetched article text contains >0 words for valid articles, captures author attribution when present, and extracts all XML category elements into `categories: string[]` or defaults to `[]` when missing.

Preflight: the service manifest currently declares only common-contracts.
Price and name its manifest/lock changes for the approved DOM and feed
libraries, recorded RSS/Atom/HTML fixture files, and the owning documentation
before dispatch. The existing trust-boundary page also requires safe target
validation before requests, robots permission, and sanitization. Include the
bounded modules and fixtures needed to preserve those controls; DOM extraction
must not load page resources. Do not substitute extraction success for these
independent safety requirements.

Supporting scope: the manifest and lock add the approved DOM extraction
libraries, a mature feed parser, and any mature transport/address/robots
libraries needed to preserve the existing controls. Record each dependency's
benefit and installed cost. The named helpers separate target validation,
robots permission, sanitization and authored input loading from routing.
Read existing extraction byte/retry controls rather than inventing constants.
Fixtures are named recorded RSS, Atom, HTML, response and safety inputs, not
network tests. The owning harvesting page documents the isolated path without
changing production extraction. No shared schema or CI workflow edits belong
to this row: its Bun checks run locally, and the isolated workflow belongs to
Row #12. Row #4 alone owns its named Bun CI addition, avoiding a shared-file
collision while these rows are built.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Pre-fetch full article HTML during plan stage to make extracted text available before selection | Plan proposal |
| 2 | Extract and normalize RSS/Atom `<category>` elements into candidate records; use `[]` only when categories are absent, not when parsing fails. | Plan proposal |
| 3 | Read `config/sources.json` at root without changing its path | Plan proposal |
| 4 | Read extraction concurrency and timeout from the configuration in section 2 | Plan proposal |
| 5 | Preserve every source field named by SRC-01 in Table M: tier, vertical, weight, kind, form, title, URL, and lifecycle status. Resolve status before fetching; record inactive sources without issuing a request. Preserve the source configuration snapshot used by the run for later denominators. | Owner checklist |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Storing only RSS titles/snippets | Leaves article viability unknown until workers fetch the pages | Later HTTP failures and incomplete selection evidence | Plan proposal |
| 2 | Headless browser extraction | Adds a browser runtime where static DOM extraction is proposed | Measure peak memory, extraction success, and elapsed time on the same bounded article fixtures before changing the extraction path | Plan proposal |

---

## 11. Row #8 - Candidate triage screening with Parquet rejection ledger

- **Scope:** Implement `services/feed-ingest-plan/src/screen-article-candidates/` to apply word-count, paywall, category, and maximum-age checks, and pass rejected rows to the shared ledger writer.
- **Files touched:**
  - `services/feed-ingest-plan/src/screen-article-candidates/triage-gates.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/freshness-decay.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/category-guard.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/rejection-sealer.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/screening-input.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/seen-evidence.ts`
  - `services/feed-ingest-plan/test/triage.test.ts`
  - `tests/fixtures/feed-ingest-plan/screening-cases.json`
  - `tests/fixtures/feed-ingest-plan/seen-evidence.json`
  - `docs/architecture/sources/feed-screening.md`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; generated rejection files pass TypeScript Parquet readback and recorded contract checks. Cover the configured word-count and HTTP rules plus Table R freshness boundaries with one fixed UTC clock, including undated articles and invalid overrides. Execute Table O's vertical-specific threshold substitution against this real screening stage, not only the resolver.
- **Oracle:** Each rejected fixture has the expected typed reason, and changing only the freshness override changes admission at the stated age boundary without changing the ranking half-life. This does not settle editorial quality or live-source availability.

Preflight: candidates contain publication and fetch instants, but not persisted
first sight. Table R requires the existing first-sight evidence for undated or
untrustworthy feed dates. Name the bounded seen-ledger input and URL-key join
before dispatch; a repeated fetch must not reset an undated article's age.
Preserve the existing future-date tolerance when deciding whether to trust
the feed date. Price reader and fixture supporting paths rather than adding
an undeclared candidate field.

Supporting scope: screening consumes a validated candidate batch, actual
transient HTTP/paywall observations from harvesting, and a caller-supplied
bounded list of settled SeenRow payloads. `seen-evidence.ts` validates the
existing seen fields and joins by `url_key`; it does not invent a new
persisted shape or scan history. The later engine owns loading that bounded
history from raw and compact files. Missing observations remain unknown.
Read the existing future-date tolerance from authored configuration.
The named fixtures and screening page cover repeated undated sightings,
exact cutoff boundaries, configured checks and real rejection persistence.
Row #7 owns the manifest and lock; Row #8 integrates that dependency foundation
before final checks instead of editing either file concurrently.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Apply the same policy resolver in CLI and API execution. A vertical override may alter the feed grouping's age or word threshold; changing source kind does not alter either. Keep the original feed vertical separate from any desk assigned later by summarization. | Owner selected vertical_overrides and separate desk controls |
| 2 | Persist all rejections to Parquet under `state/raw/feed-ingest-plan/rejections/` through the reusable writer | Plan proposal |
| 3 | Read minimum word count floors from `config/feed-ingest-plan.json` | Plan proposal |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Dropping items silently without recording rejection reason | Leaves yield loss unobservable; impossible to diagnose feed starvation in CI | Opaque pipeline behavior | Plan proposal |
| 2 | Storing rejections in uncompacted JSONL | Leaves retention outside the enrolled ledger lifecycle | Separate retention and query support | Plan proposal |

---

## 12. Row #9 - Set-aware editorial portfolio curation

- **Scope:** Implement `services/feed-ingest-plan/src/curate-article-portfolio/` to normalize source opportunity, select the portfolio, persist terminal curation rejections, and write unsharded editorial selections through the registered Parquet ledger in Table P.
- **Files touched:**
  - `services/feed-ingest-plan/src/curate-article-portfolio/quota-normalizer.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/quality-decoupler.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/carrier-cluster.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/mmr-portfolio.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/record-rejection.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/portfolio-input.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/story-evidence.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `tests/fixtures/feed-ingest-plan/portfolio-cases.json`
  - `docs/architecture/sources/feed-curation.md`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; bounded fixtures check the configured concentration limits and relaxation order. Vary only the source-kind coefficient: zero must remove its penalty; increasing it changes only the declared diversity term. Relabelling a source must not change screening eligibility or introduce a required-kind count. Execute Table O's vertical-specific scoring substitution against this real curation stage and compare exact components and selected identities. Vary each Table T dimension independently, including same lens/different event cluster, same event type/different occurrence, same entity/different story, and unavailable desk evidence.
- **Oracle:** Source/domain shares and relaxation follow configuration, and the source-kind penalty equals the bounded term in Table F, including the zero-weight case. This does not prove that a subjective source label is correct or that the proposed coefficient is editorially optimal.

Preflight: candidates carry labels and article text, but no semantic vectors.
Reuse only the existing same-story rules whose inputs are available; record
unavailable similarity evidence rather than claiming a vector comparison.
Cross-outlet groups must satisfy the rule for every pair, not merely form a
chain of matching neighbours. Publisher identity is the recorded masthead,
not the feed ID; parent-domain concentration remains a separate control.
Name the matcher, fixture and owning-doc supporting paths before dispatch.

Supporting scope: `portfolio-input.ts` validates already screened candidates
and explicitly supplied operational, timing, publisher and story evidence.
`story-evidence.ts` applies only the existing same-story rules supported by
those inputs; absent vectors are not a fabricated semantic comparison.
The named fixture and curation page define stable hand-computable selections,
separate quality axes, each penalty and evidence availability. No new
persisted contract or label inference is authorized. Row #7 owns the service
manifest and lock; integrate its stable dependency foundation and Row #8's
actual admitted-result boundary before final composed checks, without
concurrent edits to those files.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Limit source intake before global pool to the configured base allowance plus bonuses for an uncovered event cluster, underrepresented vertical, or unique primary evidence. Desk placement remains separate and is not inferred to grant a bonus. | Owner terminology clarification |
| 2 | Separate 3 quality axes: operational reliability, article intrinsic quality, and marginal portfolio contribution | Plan proposal |
| 3 | Allocate 8% of planned slots for qualifying underrepresented long-tail sources | Plan proposal |
| 4 | Persist the selected article identities, estimated work, scores, and editorial order as unsharded Parquet rows under Table P before partitioning. Do not create an unmanaged JSON file under state/raw. | Owner correction; persistence and compaction contracts |
| 5 | Apply source kind only through Table F's weak configurable term. Keep measured source reliability, article quality, and portfolio contribution separate from that label. | Owner direction |
| 6 | After viability screening, rank candidates within each source and admit at most the configured base allowance plus earned bonuses before global selection. Award each configured bonus type at most once per source per run, backed by distinct evidence for uncovered event clusters, underrepresented verticals, or unique primary evidence. Repeated copies cannot raise the allowance. Persist excluded candidates with the source-cap reason and the actual allowance. | NRM-01; owner requested high-volume normalization |
| 7 | Use Table T's separate source, parent-domain, vertical, assigned-desk, lens, event-type, event-cluster, entity, and coverage terms with their own coefficients. Known labels come from named validated inputs/matchers, not an invented pre-summarization classification. Record unavailable terms explicitly and use no contribution from them in the total. Event-type and entity saturation start at zero as configurable tuning defaults; implement and test their real terms, not placeholders. Apply configured soft caps with recorded relaxation; kind has no quota to relax. | Owner requested independent config controls |
| 8 | Record all carrier source identities for a cluster, distinct outlet count, chosen representative, similarity method/version, and duplicate evidence. Reuse the existing same-story rules where inputs are available; never label independently written coverage as independent verification of the underlying claim. A suppressed carrier records its replacement identity. | CRD-01; autotune-content-similarity.md |
| 9 | Source-volume fixture: adding repeated low-quality or duplicate items from one feed does not raise its allowance or displace other qualifying feeds. Check stable ties, bonus evidence, cap relaxations, and minority-source exploration slots against exact selected identities. | NRM-01 acceptance oracle |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Pure top-N global score sorting | Does not directly control source, vertical, or lens concentration | Compare those separate shares on the same bounded candidate fixture to price the loss | Plan proposal |
| 2 | Hard diversity equality quotas | Can exclude the best available coverage when few publishers cover an event | Can require weaker articles to fill quotas; evaluate on bounded coverage fixtures | Plan proposal |

---

## 13. Row #10 - Contextual bin-packing partitioner with feature flag

- **Scope:** Read the unsharded editorial selection ledger, allocate its exact selected articles to workers without rescoring, and write the dispatch ledger using the configured partition strategy.
- **Files touched:**
  - `services/feed-ingest-plan/src/partition-article-shards/shard-packer.ts`
  - `services/feed-ingest-plan/src/partition-article-shards/bin-pack.ts`
  - `services/feed-ingest-plan/src/partition-article-shards/round-robin.ts`
  - `services/feed-ingest-plan/src/partition-article-shards/read-editorial-selection.ts`
  - `services/feed-ingest-plan/src/partition-article-shards/partition-input.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-period.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-parquet.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/complete-attempt.ts`
  - `packages/common-contracts/src/schemas/ledger-index.schema.ts`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/test/ledger-index.test.ts`
  - `packages/ledger-file-writer/src/index.ts`
  - `packages/ledger-file-writer/test/reader-integrity.test.ts`
  - `services/feed-ingest-plan/test/partition.test.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `services/feed-ingest-plan/test/partition-fixtures.ts`
  - `tests/fixtures/feed-ingest-plan/ledger-history.json`
  - `docs/architecture/sources/feed-partitioning.md`
  - `docs/architecture/contracts/persistence.md`
- **Acceptance gates:** Local: shared selector and `bun test` over bounded uneven, equal-work, empty, and fewer-items-than-shards fixtures. Verify deterministic assignments, configured shard bounds, and the selected-to-dispatched identity/rank bijection. CI: full suite. Greedy bin-packing is a heuristic, not proof of minimum variance for every input.
- **Oracle:** A hand-computable uneven-work fixture produces the expected greedy assignment and lower work spread than round-robin; equal-work fixtures may tie. With strategy `none`, all items have worker assignment zero and the effective dispatch count is one. These checks do not prove optimal packing or actual worker elapsed-time balance.

Preflight: editorial selections do not contain article text or titles, while
dispatches require the complete validated candidate. Name the candidate input
and join it to settled selections by candidate identity, checking source and
policy consistency. Do not reconstruct content from a selection row or fetch
it again from the web. The shared writer is not a settled ledger reader;
price the raw/compact reader and candidate-input supporting paths before
dispatch. Worker assignment stays separate from the writer's identity shard.

Initial construction and historical replay are different inputs. Initial
construction receives the current run's validated selection write result and
harvested candidates before dispatches and source completion exist. Requiring
dispatch-completion evidence there would make a cycle. Historical replay
selects a proven complete attempt and gets full content from recorded
dispatches; selections alone can reproduce allocation, not recover text.
Raw and compact readers preserve original row identities and planning
attempts. They use explicitly named days or files and the existing index
precedence: yearly, monthly, daily, then raw. A known empty period differs
from lost or missing evidence. No repository history scan or network refetch
can substitute for either input.

Supporting scope: the named history modules read actual Parquet through the
existing Arrow/WASM libraries, validate envelopes and original row identity,
resolve one named day's compact indexes or explicitly supplied raw files,
and validate the completion evidence those inputs can actually prove. The shared
index schemas are small TypeScript copies of the existing raw/compact
contracts, held to bounded recorded field, vocabulary and validation
fixtures. They do not execute or read Python source during tests. The
generated history tests exercise raw, daily, monthly and yearly files,
empty/lost/missing periods, incomplete retries and preserved original
identities. No new persisted field or schema meaning is introduced.
`partition-input.ts` validates current selections and supplied full candidate
content without requiring future completion evidence. The owning partition
page records the distinction and reader behavior. Row #7 owns the manifest
and lock, including the existing Arrow/WASM runtime dependencies; this row
integrates that foundation before final checks and does not edit those files
concurrently. No writer implementation, frontend import, Python source or
production workflow change belongs to this row.

Reader integrity reuses the writer's existing canonical serialization:
the package entry point may export `digestRows`, its logical field/type
declarations, and the existing `describeObjectSchema` and
`appendIdentityColumns` helpers. The named public-import test proves digest
agreement over actual Parquet readback. This is an export-only addition,
not a writer implementation or stored-format change; do not deep-import
private modules or duplicate canonical serialization in the reader.

STOP-AND-SURFACE, 2026-10-21: compact rows retain original run, attempt and
unit identity, but not original raw-file membership or row order. Completion
evidence names original file digests, and the writer hashes rows in input
order. Packing can also settle duplicate occurrences. Consequently a reader
cannot generally reproduce each recorded raw-file digest after raw removal.
Current compact-file integrity and matching aggregate counts do not prove
the original file commitments. Fowler confirmed this contract gap.
The coordinator requested owner approval for a versioned logical-attempt
commitment, with the existing Python declaration updated but never executed;
alternatives were retaining referenced raw files or preserving full raw-file
provenance through packing. The unavailable-user response selected none.
Do not self-authorize a contract change or report packed replay as verified.
Current-run partition construction and bounded reader implementation can
continue. Historical completion proof remains an explicit unresolved part
of this row, not a silent scope reduction.

STOP-AND-SURFACE, 2026-10-21: the dispatch contract also requires content and
selection dates and policies to be equal. Curation preserves the actual
fetch day and harvested policy in content, and records the decision day and
effective screening policy in selection. A freshness override or a fetch
before UTC midnight followed by selection after midnight can therefore
produce valid stage output that the current dispatch contract rejects.
The coordinator requested approval to keep identity, source and labels
equal while permitting the two genuine date/policy records, including a
limited existing Python declaration update without execution. The
unavailable-user response selected no option; no contract change is
authorized. Row #9 adds real composition regressions. Row #10 must report
the boundary explicitly, not falsify fetched content, discard the override
or claim those cases work. Same-day, same-policy construction can continue.
This does not inherently
block a live freshness override: harvesting already accepts run overrides,
so the runner must pass the same override to harvest and screening and one
captured UTC instant through all stages. Independently supplied content
harvested under a different policy or UTC day remains unrepresentable.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Place partitioning behind feature flag `--partition-strategy=bin-pack|round-robin|none` | Plan proposal |
| 2 | Use greedy bin-packing of articles ordered by decreasing `word_count` | Plan proposal |
| 3 | Match the Python contract's Arrow type for the `shard` column; do not infer compatibility from the column name alone. | persistence.md; arrow_schema.py |
| 4 | Resolve the selected run/attempt's editorial rows through the ledger reader, whether raw or compact. Partitioning preserves the selected identity set and editorial ranks; only worker assignment and work totals may differ. | Owner editorial-ledger correction |
| 5 | With strategy `none`, accept an omitted shard count or explicit one, resolve the effective count to one, and reject an explicit larger count before harvesting. Keep worker assignment separate from the ledger writer's identity shard. | Consistent Table R request/output contract |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Requiring Python workers to partition on read without a `shard` column | Requires modifying existing Python `work.py` code; breaks backward compatibility | Higher risk and cross-language coordination | Plan proposal |
| 2 | Round-robin as the only strategy | Balances article counts rather than estimated work | Measure shard elapsed-time spread on one bounded workload to compare strategies; no runner timing has been measured for this plan | Plan proposal |

---

## 14. Row #11 - Core plan engine entrypoint, dual-mode runner, and sealing

- **Scope:** Implement the planner REST API and CLI, pass the resolved freshness request through screening, and call the shared ledger package from the storage adapter in Table E to persist dispatches and return structured result paths.
- **Files touched:**
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `services/feed-ingest-plan/tsconfig.json`
  - `services/feed-ingest-plan/src/index.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/routes/plan.route.ts`
  - `services/feed-ingest-plan/src/api/routes/health.route.ts`
  - `services/feed-ingest-plan/src/api/plan-request.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/load-plan-inputs.ts`
  - `services/feed-ingest-plan/src/resolve-run-context.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence.ts`
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `services/feed-ingest-plan/src/seal-article-ledger/plan-sealer.ts`
  - `services/feed-ingest-plan/src/logging/structured-logger.ts`
  - `services/feed-ingest-plan/src/logging/stage-assessments.ts`
  - `services/feed-ingest-plan/test/plan-cli.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `config/feed-ingest-plan-service.json`
  - `docs/architecture/sources/feed-plan-runner.md`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; CLI/API fixture tests cover the same age filter, automatically derived UTC date, and Python-readable dispatch output. No core module writes GitHub annotations, step summaries, or GitHub output files.
- **Oracle:** Given the same bounded inputs and fixed UTC clock, CLI and API select the same article identities and return valid dispatch paths and shard assignments. This does not prove live-feed performance.

Supporting scope: keep the entry point and HTTP routes as routing only.
`run-feed-plan.ts` composes the real stages; named loaders resolve explicit
config, ledger and bounded seen-evidence inputs; the context module captures
one UTC instant and validates run/attempt/partition controls before fetching.
Use the same freshness override in harvesting and screening. Named authored
service settings govern listener, input limits and feature enablement, not
an undeclared environment-only destination. Row #7's manifest ownership has
ended at its pushed handoff; Row #11 owns the service manifest and lock from
this point, including Hono's stated API-routing benefit and installation cost.
No other row edits those files concurrently. Row #10 still owns its named
history modules; do not edit them from this row.

The runner emits existing typed stage events with genuine membership,
measurements and unavailable evidence for Row #14. Before the audit recorder
exists, dispatch persistence is not audited completion: never emit a
plan-complete source snapshot or return complete success without all required
audit writes. Build real composition now, not a success-shaped placeholder.
The audit timing, top-count and packed-completion contract questions remain
explicit integration dependencies. No new persisted contract or Python
change is authorized by this supporting scope.

First-sight integration uses `collect.seen_window_days` from the existing
configuration and the same bounded-day meaning as the freshness page.
Within its already named modules, Row #11 may consume transient named
per-day index/file inputs through Row #10's reader. Only verified rows or
known-empty evidence for every required UTC day establishes absence within
that window. Missing, lost or expired history cannot establish a new sight;
arbitrary available rows still do not prove absence. Preserve the earliest
genuine settled sight for each URL key. After complete-window proof only,
write newly encountered keys through the existing seen contract and public
writer before screening uses them; failed or skipped persistence cannot
masquerade as a recorded first sight. No global-history claim or new
persisted input format is authorized. Named real native-window cases belong
in the already scoped engine tests and owning runner documentation.

The long-lived API must retain its own successful seen-write receipts within
the configured UTC window so a later request does not reuse a stale
known-empty inventory and reset first sight. Coordinate overlapping requests
at that read/write boundary. Only genuine durable receipts extend the named
history; neither a failed write nor process memory proves missing days.
A fresh process still requires current caller-supplied inventory. Keep this
coordination in the already named runner/API modules, or name an additional
helper before editing it.

Listener review follow-up: after the UTC day advances, previously accepted
named days can age out of the window. The listener must not treat that aging
as newly invalid authored input and abort every later request. Retain only
still-relevant named evidence and durable own receipts; a newly required day
without evidence stays missing, so it cannot establish a new first sight.
Direct invocation still rejects invalid authored day bounds. Verify a real
cross-midnight pair of requests before closing this listener behavior.

Reviewed runner increment `65c4e68abf87f2aad1980c07be09ecccf4b3bb77`
implements this path with actual native seen writes before screening, earliest
settled observations, serialized API requests and durable receipt retention
after a later dispatch failure. Its strict TypeScript and 18 named tests
passed. Retired historical sources now retain their snapshot and receive an
inactive outcome with explicit run-context policy rather than a fabricated
current vertical policy. Rows #12 and #14 integrate this tested interface.
This accepts the implementation increment, not audited completion or merge.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Store dispatch tables under `state/raw/feed-ingest-plan/dispatches/` using the shared package | Plan proposal; owner selected package reuse |
| 2 | Support dual-mode: long-lived Hono API daemon with `--serve` and one-shot CLI execution with `--cli` | Plan proposal |
| 3 | Emit structured JSONL events with `elapsed_ms` and `step_elapsed_ms`; keep GitHub formatting outside the planner. The storage adapter adds planner context, not generic writing logic. | Owner request |
| 4 | Emit Table J's typed stage-membership and assessment events for Row #14. Record source normalization and each marginal selection step, not only the final portfolio. Row #14 integrates the recorder and final completion write before the API/CLI reports a complete audited plan; optional reporting is never on that success path. | Three-axis audit and lost-diversity metrics |
| 5 | Expose `POST /api/2026-10-20/plan` and `GET /api/2026-10-20/health`; validate the same request contract used by the CLI before executing the pipeline. | SRV-01; calendar-version contract |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keeping the new dispatches in `state/raw/run-plan/` without a reader migration | A new payload under an existing ledger name can be mistaken for the old shape | Price and approve a versioned RunPlan migration before reusing that path | Plan proposal; CLAUDE.md section 11 |
| 2 | Unstructured console logging | Makes CI event processing depend on incidental message text | A separate parser and fragile reporting | Plan proposal |

---

## 15. Row #12 - Isolated CI test workflow and verification suite

- **Scope:** Create `.github/workflows/feed-ingest-plan-test.yml` with the inputs in Table R, TypeScript-only compatibility checks, and a separate optional GitHub reporting adapter; leave production `digest.yml` unchanged. Do not install Python packages or invoke Python.
- **Files touched:**
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `.github/scripts/feed-ingest-plan-outputs.ts`
  - `.github/scripts/feed-ingest-plan-report.ts`
  - `.github/scripts/tests/feed-ingest-plan-report.test.ts`
  - `.github/scripts/tests/feed-ingest-plan-outputs.test.ts`
  - `.github/scripts/tests/feed-ingest-plan-workflow.test.ts`
  - `.github/scripts/feed-ingest-plan-verification.ts`
  - `tests/fixtures/feed-ingest-plan/report-events.json`
  - `docs/how-to/run-feed-ingest-plan-test.md`
- **Acceptance gates:** Local: shared test selector and fixture-driven workflow/reporting tests. CI: full suite and the isolated workflow's compatibility checks. Reporting enabled/disabled runs over identical fixtures must produce identical ledger content digests; disabled reporting produces no annotations or summary. Cover zero dispatches or zero rejections as valid outcomes, not failed count assertions.
- **Oracle:** `feed-ingest-plan-verification.ts` reads actual dispatch and rejection files, validates envelopes and rows, compares recorded fixture identities and canonical row digests, and checks native list-column types; adapter tests check escaped annotations and summaries separately. No Python runtime or packages are required. This cannot settle Python-reader execution, real feed availability or hosted-runner speed.

Supporting scope: independent reporting implementation can consume existing
typed events while the runner is being built. Final output conversion and
workflow verification still depend on Rows #11 and #14; no invented result
or successful placeholder substitutes for them. The named script tests
separate required execution outputs from optional annotations and summaries
and inspect only the named isolated workflow. The bounded event fixture
uses the existing event contract. The owning how-to documents invocation,
actual evidence and remaining audit integration requirements.

Row #11 owns the service manifest and lock; coordinate dependency needs
there, never edit them concurrently. Reuse Row #10's public canonical
integrity functions and real Parquet reader rather than a second serializer.
The isolated workflow does not commit generated state or invoke the
production publisher. It must include compact indexes and their named
files, not substitute a raw-only checkout or scan accumulated history.

Report isolation uses the same actual produced files before and after each
disabled/enabled report invocation. Every file, including source records,
must retain identical bytes and content digests. Independent planning runs
record different real elapsed durations and completion file IDs, so their
source-file digests cannot be an equality oracle. Verify both runs' full
native source records and completion proof without dropping fields; retain
the independent-run equality checks for deterministic stage and metric
content. Do not replace measured clocks or normalize persisted records.
Reviewed workflow head `39fabddeb9c84521050551bf7d0ff5fbdb4b2c31` implements
native source-row and original complete-attempt verification after the single
actual CLI call. Its generated publication fixture joins actual selected
identities to native published rows, a matching digest and settled health,
then invokes the real observer and verifies its written files. The same-result
report check preserves every output byte; both independent runs retain full
source proof. Twenty focused tests passed, including the actual inline
TypeScript check within its original timeout. The full-audit final gate and
default-off controls remain unchanged.

### Table R - Workflow inputs and freshness behavior

| # | Input or rule | Contract |
| --- | --- | --- |
| R1 | `freshness_hours` | Positive finite number; workflow default `24`, matching the current `collect.max_age_hours` cutoff. Accept values such as `12` or `18` as explicit overrides. This replaces the date input; it is not a ranking half-life. |
| R2 | `article_limit` | Optional strict positive integer run-wide selection cap; omit/leave blank to use global curate.article_limit. Its proposed default is null, matching the existing Python optional cap: no additional run cap, not zero articles. A supplied value overrides only this run. Source allowances and viability rules still apply. |
| R3 | `shards` | Optional strict positive integer; use partition.default_shards and enforce min_shards/max_shards. Strategy none follows Row #10's one-worker rule. Persist and return the resolved count rather than asking later consumers to recompute it. |
| R4 | `partition_strategy` | One of bin-pack, round-robin, none; omit to use partition.default_strategy. Reject unknown values before harvesting. |
| R5 | Override precedence | A supplied freshness value replaces the effective age cutoff for this run only, after the candidate's vertical planning policy is resolved under Table O. Without it, use the vertical override if present, otherwise the global cutoff. Never rewrite configuration or change the resolved recency half-life; source kind affects neither setting. |
| R6 | Clock and article age | Capture one UTC instant at run start; derive the ledger date from it. Preserve Python's effective publication-time rule: trustworthy feed date, otherwise persisted first sight. A newly undated item gets first sight now. Accept age equal to the cutoff; reject greater age with a typed reason. |
| R7 | Invalid input | Reject zero, negatives, non-numeric values, NaN, and infinity by field name before harvesting; integer controls also reject fractions. Workflow/CLI adapters distinguish an omitted/blank optional input from a supplied invalid value and parse numeric strings before the shared typed validator. API callers supply typed numbers. |
| R8 | Existing behavior evidence | `config/idhazh.json`, `CollectConfig`, and `rank.too_old` use a 24-hour maximum age. The separate `recency_half_life_hours` value is 18 hours and changes ranking only. |

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Create isolated test workflow `feed-ingest-plan-test.yml` rather than modifying `digest.yml` directly | Plan proposal |
| 2 | Verify actual Parquet rows, native columns, envelope and digest through TypeScript and recorded compatibility fixtures. No Python install or invocation. Use Row #6's public writer and readback checks. | Owner ruling, 2026-10-21 |
| 3 | Expose only the four inputs declared in Table R; derive the run date internally in UTC. | Owner request |
| 4 | `.github/scripts/feed-ingest-plan-report.ts` alone formats `::notice::` annotations and Markdown for `$GITHUB_STEP_SUMMARY` from structured planner events. Escape workflow-command control characters and untrusted source strings. Invoke it as a separate workflow step only when the reporting config enables it. Core modules do not import it. | Owner request |
| 5 | Keep required shard/matrix/path output conversion in `.github/scripts/feed-ingest-plan-outputs.ts`, separate from optional reporting, so disabling or deleting the report cannot break execution outputs. | Owner request; separation of concerns |
| 6 | Use sparse checkout for the isolated workflow, with a named path inventory containing config, services, packages, relevant state inputs, recorded compatibility fixtures, scripts, and dependency manifests/locks. Include compact indexes and the named compact files serving the bounded history window; raw-only checkout is insufficient after compaction. Verify TypeScript compatibility and history reads without Python. | GIT-01; owner ruling, 2026-10-21 |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Editing `.github/workflows/digest.yml` directly during development | Risks daily publication before compatibility is established | A production cutover and rollback plan | Plan proposal |
| 2 | Exposing low-level tuning settings in GitHub Actions UI | Duplicates configuration and obscures the run controls | More inputs to maintain and reconcile with configuration | Plan proposal |
| 3 | Formatting GitHub annotations or summaries inside harvesting, screening, curation, partitioning, or the shared writer | Makes development reporting part of production behavior | Core source changes to disable or remove reporting | Owner request |

---

## 16. Row #13 - Phase 2 publication reconciliation and rolling diversity metrics

- **Scope:** Join planning evidence to actual published items and leads, complete source-run publication observations, and compute every metric in Table L per run and over the configured rolling window.
- **Files touched:**
  - `services/feed-ingest-plan/src/metrics/publication-outcomes.ts`
  - `services/feed-ingest-plan/src/metrics/publication-evidence.ts`
  - `services/feed-ingest-plan/src/metrics/publication-metrics.ts`
  - `services/feed-ingest-plan/src/metrics/planning-populations.ts`
  - `services/feed-ingest-plan/src/metrics/history-window.ts`
  - `services/feed-ingest-plan/src/metrics/diversity-metrics.ts`
  - `services/feed-ingest-plan/src/metrics/fingerprint-dedup.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/headline-figures.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/story-evidence.ts`
  - `services/feed-ingest-plan/src/metrics/metrics-recorder.ts`
  - `services/feed-ingest-plan/test/metrics.test.ts`
  - `services/feed-ingest-plan/test/publication-outcomes.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `tests/fixtures/feed-ingest-plan/publication-evidence.json`
  - `docs/architecture/sources/feed-ingest-audit.md`
  - `docs/reference/diversity-metrics.md`
- **Acceptance gates:** Local: shared selector, strict TypeScript checks, contract fixtures, and focused metrics/reconciliation tests. CI: full suite. Cover repeated runs in one UTC day, retries, zero-publish runs, source-kind changes, known-empty versus missing days, missing event evidence, packed history, and each metric's arithmetic using generated bounded fixtures.
- **Oracle:** Hand-computable fixtures produce every Table L reading with the declared denominator and window; missing evidence stays unavailable instead of turning into zero, and no selected article is counted as published without publication evidence. This does not validate a model's opinion of article quality or prove that event matching has no false matches.

Implementation sequence, 2026-10-21: start the already named
`publication-outcomes.ts`, `history-window.ts`, `fingerprint-dedup.ts` and
their two named publication/history tests independently. They consume
explicit bounded evidence and existing contracts, not a future audit-success
claim. Rows #12 and #14 remain prerequisites for full integration and
acceptance. While Row #14 writes shared metrics and documentation, this row
does not edit `diversity-metrics.ts`, `metrics-recorder.ts`, `metrics.test.ts`,
`feed-ingest-audit.md` or `diversity-metrics.md`. Obtain its tested API and
file-ownership handoff before the remaining integration. Name any additional
contract-copy or fixture path before editing it. This sequence does not
change a persisted meaning or count selected articles as published.

Supporting scope: `publication-evidence.ts` validates small read-only
projections of the existing published, item-health and digest-day records,
including recorded run references and lead identities. The named bounded
fixture binds those projections to their existing wire fields and is loaded
inside tests. It declares no new stored payload and requires no backend
execution. Missing compatible cross-day event evidence remains unavailable.

Event arithmetic may consume bounded transient projections of the existing
`StorySimilarityPair` records joined to named published articles. Validate
sorted URL keys and their recorded pair identity, agreement in both judging
orders, usable status and compatible recorded scorer/judge configuration.
Require every pair decision needed by the measured sets; missing, unclear
or incompatible evidence makes the event reading unavailable. Use the
existing same-source and figure-conflict safeguards before positive matches
and complete-link grouping, not local cluster identifiers as global events.
Extract the existing ASCII figure comparison unchanged into the named
`headline-figures.ts` helper and reuse it from `story-evidence.ts`; preserve
current curation behavior and its focused checks. These projections add no
stored payload, new matcher policy or model invocation.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use the existing published ledger, ItemHealthRow, and the named day's DigestDay as publication evidence. PublishedRow supplies URL identity and item ID; DigestDay supplies source ID and the actual leads. Join by recorded URL/item/run identity, not title or URL guesses. ItemHealthRow without publication confirmation is not publication evidence. | Existing contracts; owner requested actual publication metrics |
| 2 | Persist diversity readings under `state/raw/feed-ingest-plan/diversity/`, and completed source observations under the source-run prefix in Table I, through the shared writer. Register both before writing; compaction uses the corresponding compact prefixes. | Owner ledger layout |
| 3 | Deduplicate retries first. Attribute an item to its recorded publishing run when that evidence exists. For older items with no provable run match, report day-level results with run attribution unavailable; never assign them to whichever plan ran last. | Correct run-level denominators |
| 4 | Read only the UTC days required by `rolling_window_days + max(rolling_window_days, overlap_windows_days...)`; the defaults require fourteen named days to evaluate seven days of novelty against each day's prior seven. Resolve compact indexes and only the files serving those days. No archive/tree/history scan. | CLAUDE.md Guardrail #12 |
| 5 | A rolling reading covers the configured consecutive UTC calendar days through `as_of` on the current day; label the current day as partial until its UTC end. A known-empty day contributes zero items; an unobserved day makes history-dependent metrics unavailable with coverage counts. Never average daily ratios to obtain a window ratio. | UTC rules; truthful missing-data behavior |
| 6 | Match events using recorded identity/fingerprint evidence and the declared similarity method/version, not ephemeral within-run cluster numbers. Preserve figure-conflict and same-story safety rules from autotune-content-similarity.md. Missing or incompatible event evidence cannot prove novelty or zero repetition. | Existing similarity contract |
| 7 | This is a post-publication observer with explicit bounded inputs, not a new publication gate. Test against real recorded publication fixtures without editing work.py or digest.yml. A later production cutover must wire its invocation after publication; the isolated workflow exercises it on a generated published fixture. | Preserves this plan's production-workflow boundary |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Treating selected counts as published counts | A selected item can fail work, be replaced, or never reach a committed day | Requires actual publication reconciliation; no planner-only proxy can settle it | Owner requested three-axis evidence |
| 2 | Blocking dispatch on completion of multi-day metrics | Couples selection delivery to an independent historical analysis | Carry forward Phase 1 evidence, then build this read-only observer in Phase 2 | Phase boundary retained from owner checklist |

---

## 17. Row #14 - Phase 1 source-run audit and three-axis evidence

- **Scope:** Persist per-source run summaries and per-article decision evidence, and compute the Table L metrics whose inputs exist at planning time without fabricating later publication outcomes.
- **Files touched:**
  - `services/feed-ingest-plan/src/metrics/source-run-summary.ts`
  - `services/feed-ingest-plan/src/metrics/article-assessments.ts`
  - `services/feed-ingest-plan/src/metrics/stage-membership.ts`
  - `services/feed-ingest-plan/src/metrics/diversity-metrics.ts`
  - `services/feed-ingest-plan/src/metrics/metrics-recorder.ts`
  - `services/feed-ingest-plan/src/index.ts`
  - `services/feed-ingest-plan/test/source-run-summary.test.ts`
  - `services/feed-ingest-plan/test/article-assessments.test.ts`
  - `services/feed-ingest-plan/test/metrics.test.ts`
  - `docs/architecture/sources/feed-ingest-audit.md`
  - `docs/reference/diversity-metrics.md`
- **Acceptance gates:** Local: inspect the shared selector without launching Python-backed groups, run strict TypeScript checks, audit unit/contract tests, and TypeScript Parquet readback. Existing repository CI retains its unchanged suites. Reconcile stage counts and reasons, include inactive and zero-yield sources, retain source snapshots, verify unavailable later-stage fields, and run known-distribution metric fixtures.
- **Oracle:** Each source/run observation and article assessment reconciles exactly with its input stage records, terminal rejections, and editorial selection rows, and all emitted planning metrics reproduce from those records. This does not prove publication or semantic article quality.

Preflight decision required before full completion wiring: authored `metrics.top_source_counts`
accepts every positive integer, but `DiversityMetricRow.top_k` admits only
`1`, `5`, and `10`. The defaults agree. Either restrict configuration to this
declared vocabulary, which gives up other configured counts, or obtain owner
approval to open the persisted field and update both language readers and
binding tests. Never omit an unsupported configured count without an error.

Timing preflight: the existing assessment clock vocabulary has
`published_at`, `fetched_at` and `unavailable`, but screening also uses
persisted `first_seen` evidence. An unavailable clock cannot retain its
timestamp or age under the existing validator. Calling first sight a fetch
time would be false. Screening also retains signed age for a trusted
slightly future publication time, while persisted assessment age is
nonnegative. Before wiring complete audit records, resolve how these real
measurements are represented; do not silently discard them or change a
persisted meaning. The stage's exact transient evidence remains available
to the recorder while this contract question is unresolved.

Implementation sequence, 2026-10-21: Fowler confirmed that real membership,
source-summary calculations, assessment translation, metric arithmetic and
durable assessment/diversity writes can proceed without changing a persisted
meaning. Before any Row #14 write for an attempt, preflight all supplied exact
timing and configured counts. A first-seen clock, signed negative age or
unsupported top-k refuses the whole recording request by name; do not
discard its measurement, clamp it or write only the supported subset.
Current supported configuration and representable observations can exercise
the real path. This does not authorize narrowing the promised full audit.

`source-run-summary.ts` first returns genuine internal summary values, not a
new persisted pending phase. `metrics-recorder.ts` returns actual written
assessment/diversity receipts, never audited completion. Source completion
stays blocked until the timing/count and packed-proof questions are settled.
Partially durable files remain incomplete-attempt artifacts after a failure.
The recorder consumes actual stage results alongside existing typed events
because the event assessment alone cannot carry the unsupported exact timing.
It introduces no second persisted event shape.

Incremental completion clarification, 2026-10-21: missing original packed
file proof does not prevent proving a newly written raw attempt. After the
publication observer increment, the metrics owner may seal a representable
current attempt using the existing `SourceRunRecord.plan_complete` phase:
verify all five required ledgers natively, aggregate the three rejection
file sets into one rejection receipt, and attach the exact source count
and shared completion evidence before writing source records. Unsupported
timing or configured counts must still refuse the entire batch before
audit writes. This is not permission to claim packed historical proof,
full audit acceptance, or changed persisted meaning.
The runner owner prepares only the existing source-run registration in
`services/feed-ingest-plan/src/load-plan-inputs.ts`, its existing loader
test and runner documentation. The metrics owner retains exclusive write
ownership of recorder, source-summary, metrics tests and audit documentation;
that sealing increment starts after its current observer checkpoint.
After source-file readback, the producer must pass its actual named files
through the existing complete-attempt selector. Proven completion of that
representable current run is distinct from accepting the whole plan or
proving packed history. Return that evidence for a later runner/workflow
integration; do not retain an unconditional pending result once the actual
run has every required write and proof. Caller status changes stay with
their existing owners after the tested producer handoff.
Head `45f8778bd546f7f5ec13c4c6c17edebe19d6303d` implements this current-raw
producer path, including native source readback and exact-attempt selection.
The runner owner now integrates it normally and exposes proven planning
completion separately from the unfinished full audit. The workflow stays
based on the runner, verifies returned source files and completion evidence,
and exercises publication observation only with a bounded generated published
fixture. Neither integration claims real production publication or complete
packed history.
Reviewed caller head `60d97e779738121ae550cc8315ad7327d4b88f21` exposes
`planning_complete: true` only with the producer's exact verified completion.
That planning result returns HTTP 200 and CLI exit 0, while
`audited_complete` stays false. Native API/CLI coverage independently reloads
the named files and selects the same run, attempt and correlation; source-write
failure returns no successful summary. Strict TypeScript and 11 caller tests
passed. PR #1624 merged into the runner branch, not main, at 21:25:33 UTC.
The workflow's separate full-audit gate remains unsuccessful while that
broader audit is incomplete; generated publication evidence does not bypass it.

Row #11 currently owns `src/index.ts`; Row #14 does not edit that file
concurrently. Publish the tested recorder API from its own module, coordinate
the exact in-memory result type with Row #11, then let the runner owner wire
it in a separate integration increment. The final acceptance gates remain
open; helper arithmetic and safe refusal are not a complete audit.

Reviewed recorder increment `244435367dade47c9600894cd0506f7d6ee38662`
is delivered in PR #1621. Strict TypeScript and 15 named audit tests passed;
native readback verified actual assessment and diversity receipts. Its
whole-request preflight retains exact timing for rejected candidates as
well as admitted candidates. It still writes no source-complete record.
The runner owner now integrates this exact recorder through the existing
entrypoint/composition modules, exposes actual files and receipts, and keeps
audited completion false. Unsupported observations fail explicitly rather
than bypass the recorder. Row #13 owns the shared metrics, tests and owning
documentation after this tested handoff; the runner does not edit those
files concurrently.
This final head includes the reviewed UTC rollover correction by normal
merge; it changes no recorder source or API from `ad26e1f90`.

Runner integration `524aafda05caefce05bb1cb0cf76d7539c5bd51a` now awaits
the recorder in the real CLI and API after dispatch persistence. Its
summary exposes actual assessment and diversity files, receipts and
internal source summaries. Native readback through both entrypoints
verified row counts and content digests. Strict TypeScript, 10 API/CLI
tests and 11 base-engine tests passed. Supported runs still report audit
pending; unsupported timing or counts fail before any audit write and
produce no result summary. Row #12 now integrates this tested entrypoint
and verifies its returned files, rather than calling the recorder again.
The workflow owner reports 19 named tests passing after that integration,
including native metric receipts, missing-file refusal, unsupported counts,
known-empty assessments and report-on/off ledger digest equality. Reviewed
head `c3428c33c2eca90a603ad2ef01b8ab2c4c7f0ab6` is delivered in ready
PR #1622 against the runner branch. Required CI and the remaining complete
audit/observer integration remain acceptance gates. PR #1621 is merged into
its runner base, not into main; this does not close the full audit row.
PR #1622 CI found a new dependency error before backend tests:
`packages/common-contracts/test/verify-parquet.ts` imports the writer and
planner runtime, but the shared-contract check installs only its own
dependencies. This is part of Row #12, not the unrelated schedule failure.
The workflow owner relocates that executable verifier to
`.github/scripts/feed-ingest-plan-verification.ts`, updates its callers and
retains the recorded-byte oracle. The common-contract package must check
independently; do not add runtime dependencies or alter CI to hide this error.
Corrective head `4810599a6e9a46fafebbfae7d73dc6924ee58528` restores that
boundary. An isolated shared-contract install, check and 39 tests passed
without writer or service dependencies. Hosted run `39675379776` then
passed shared-contract bindings, site, browser, robots and scope. Its only
remaining failures are the same two unrelated schedule assertions; 7249
backend tests passed. The new dependency regression is resolved, but the
candidate is not green for merge.
The independent schedule repair, PR #1623, passed all required checks and
merged into main as `5e65c0dad0335fa4cfbdc9a8285471f9cfe314ac`. The owner
directed dependent delivery to resume. Update the writer candidate normally
against repaired main, resolve its merge conflict without changing unrelated
work, and land the dependency chain only after each required candidate is
green. Earlier red runs remain historical evidence, not a current repair veto.

Row #13's shared integration adds
`services/feed-ingest-plan/src/metrics/publication-metrics.ts` to separate
publication calculations from per-run planning calculations. It consumes
bounded, named publication files and digest evidence plus existing proven
attempt memberships. The separate
`services/feed-ingest-plan/src/metrics/planning-populations.ts` reconstructs
those memberships from existing complete attempts, checks stage/candidate
identity, terminal losses and source attribution, and performs no new
completion inference. Retry selection precedes attribution; rolling
populations come from actual recorded rows, not averaged daily ratios or
unchecked caller lists. Packed publication membership can support publication
readings independently of missing original planning completion proof.
Source publication counts require an actual complete source attempt.
An observer running on a later UTC day must not backdate its observation
to satisfy the existing same-day source-record constraint; that write
stays explicitly unavailable until its contract can represent the truth.

Publication review of tested increment `a58752dfd` initially questioned the
health retry key. Reading the owning contract corrected that premise:
an item-health row records one terminal outcome, not each processing stage.
No multi-stage fixture or key change is justified by that concern alone.
The publication owner checks native retry settlement before changing the
join. The review also checks whether the projection wrongly refuses a
digest whose run completes after its named UTC day.
Tested event increment `4e9ccfa2c` removes that extra date restriction and
uses compatible recorded pair decisions for real event arithmetic; 35
focused tests passed. Review found one remaining publication-loader issue:
a compact index's set-aside-file notice must not become complete historical
coverage. The owner is adding that missing-evidence case before acceptance.
Observer checkpoint `cc137c08a` includes durable native publication metrics
and settled planning populations; 49 focused tests passed. Review requires
one further identity check before source publication completion or a
selection-to-publication comparison: every published URL and primary source
must be a subset of that run's proven selections. Merely finding its source
in the snapshot is insufficient. Missing planning proof may still support
independent publication readings, never invented stage or source completion.
Source observations also retain the proven planning attempt. Before any
source-producing observer write, its writer attempt must match that retained
attempt. A mismatch would write contradictory row identities and make later
complete-attempt reads fail. The owner is adding native refusal coverage;
independent diversity-only observations need not reuse the planning attempt.
Reviewed head `45f8778bd546f7f5ec13c4c6c17edebe19d6303d` implements both
identity checks before observer writes. Its publication fixture now obtains
complete planning records from the actual producer, not manufactured source
records. Strict TypeScript and 62 focused tests passed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Store three distinct axes under Table I; do not multiply them into one opaque quality score. A feed's fetch failures are not evidence that an otherwise valid article is uninformative. | CRQ-01; owner questions |
| 2 | Record one source-run observation for every configured source, including inactive, skipped, unavailable, and zero-selection sources. Use the lifecycle snapshot from that run, not today's edited source list. | Owner per-source audit example |
| 3 | Per-run arithmetic, including entropy, concentration, and Gini where its declared basis is available, is cheap and ships in Phase 1. Publication and history-dependent readings remain explicitly unavailable until Row #13 supplies their evidence. | Owner requested no unjustified metric omissions |
| 4 | Structured events are the input to this recorder; GitHub reports consume its outputs separately. Turning reporting off cannot remove audit rows or alter selection. | Owner separation-of-concerns ruling |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Only recording dropped articles | Cannot explain eligible sources that received no slots or compare denominators across stages | Add the per-source summary and stage evidence declared here | Owner audit requirement |
| 2 | Putting per-source counters in FileEnvelope metadata | One file can hold several sources, and the envelope refuses undeclared keys | A needless envelope migration; ordinary typed Parquet rows already support the question | Existing FileEnvelope contract |

### Table I - Audit row shapes and the three axes

| # | Record or axis | Fields and meaning |
| --- | --- | --- |
| I1 | SourceRunRecord | One row per source/run/attempt/observation phase in `state/raw/feed-ingest-plan/source-runs/`. Fields: version, date, correlation_id, source_id, source metadata snapshot, status, fetch_status, parse_status, parsed_count, harvested_count, fresh_count, duplicate_count, eligible_count, normalized_count, selected_count, published_count, lead_count, drop_reasons, observation_phase, observed_at. Normal writer identity columns include run_id and attempt. |
| I2 | Status and availability | Source status uses its owning lifecycle vocabulary. Fetch status distinguishes not requested, success, HTTP failure, network failure, and timeout. Parse status distinguishes not attempted, success, valid empty feed, and failure. Counts are nonnegative integers. Unfinished-stage counts are null; confirmed zero is zero. Inactive status is not a failed HTTP request. |
| I3 | Typed drop counts | `drop_reasons` is a Parquet list of structs `{subject, stage, reason: DropReason, count}`. No JSON-serialized dictionary and no second reason vocabulary. Each count is derived from terminal rejections. The subject separates feed decisions from candidate drops, so an inactive/failed feed is never counted as a nonexistent rejected article. |
| I4 | Observation phases | Phase 1 writes a plan-complete snapshot with publication/lead counts null only after Table J's required files are durable. Row #13 appends a publication-complete observation with the same plan identity and verified outcomes; no file is updated in place. Choose the highest complete planning attempt first, then its latest complete publication observation if present. Never combine a newer plan with an older attempt's publication counts. |
| I5 | Operational reliability | Record attempted/fetched/parsed feed outcomes, HTTP/timeout/parse/empty distinctions, fetch/parse durations in milliseconds, last observed failure, and the bounded-history success fraction used for selection. Keep the fraction's attempts denominator and measured window. A resting feed has no attempted fetch. |
| I6 | ArticleAssessmentRecord | One row per source candidate and decision stage in `state/raw/feed-ingest-plan/article-assessments/`. Store source ID, candidate_id, nullable article identity for malformed input, stage, admitted/rejected/selected decision, reason, time, policy version, and the separate evidence/score fields in I7 and I8. Preserve stage membership so pre/post-stage source counts can be recomputed without recounting a candidate's retries. |
| I7 | Article quality | Timeliness: effective publication time, clock source, age and cutoff. Substance: extracted word count, source form, extraction outcome, and word threshold. Attribution: author/byline present and canonical publisher identity. Suitability: paywall, category, form, and required-field checks. Record informative/suitability model verdicts only when a versioned evaluator actually supplies them; word count and source tier are not semantic quality verdicts. Otherwise the verdict and evaluator version remain null, with an explicit not-assessed status. |
| I8 | Portfolio contribution | At each greedy choice record base article score, each separately named Table T penalty with evidence-availability status, marginal score, current source allowance and its bonus evidence, distinct carrier outlets, representative/replacement identity, exploration-slot flag, and any cap relaxation used. Pure article quality stays separate from penalties that depend on already selected articles. |
| I9 | Count reconciliation | Record which ordered stage produced each count. Terminal first drops do not overlap: input equals admitted plus terminal rejections for each stage. `duplicate_count` is a declared subset, not another term to add to that equation. Candidate instances may share URL identity across sources; distinguish those from globally deduplicated selected articles. |
| I10 | Source publication credit | Count each actual published article once for its recorded primary source. Preserve other carrier source identities as separate coverage evidence; do not credit one article as several published articles. A lead count is a subset of published items, not an exclusion count. |

### Table J - Stage events and complete-attempt evidence

| # | Contract | Rule |
| --- | --- | --- |
| J1 | FeedIngestEvent | Declare a Python event model with strict TypeScript copies: version, event_id, correlation_id, run_id, attempt, sequence, UTC occurred_at, Table E stage, audit_event_type, source_id and candidate_id where applicable, elapsed_ms, step_elapsed_ms, and a typed payload. Use discriminated payload variants for feed outcome, candidate decision, portfolio choice, and stage completion; no arbitrary map or JSON string payload. Audit observation types are not content event types or event clusters. |
| J2 | Consumers | Stage boundaries exchange the declared candidate/selection/dispatch payloads. Table J events carry decision evidence for the Row #14 recorder and the optional external report; full article text remains in the content/dispatch payload, not decision logs. Events retain the policy/config identity and the fields required by Table I; reporting does not add evidence that audit depends on. |
| J3 | Final write and failure | Row #14 seals assessment/metric files and then writes all source plan-complete snapshots together in one final source-runs raw write. Each snapshot carries the same typed list of required ledger file identities, digests, and row counts for the attempt, plus the expected source count. This includes editorial selections, dispatches, and rejections. A zero-row raw write produces no file, so record an explicit zero count/empty file list. Failed writes cannot emit completion or return complete success. |
| J4 | Retry and compact reads | A complete attempt has the expected source snapshot set and its recorded file evidence; partial newer attempts do not displace it. Resolve the highest complete attempt before joining any candidate rows, including when it selected zero items. Compaction preserves these attempt identities and completion evidence; after raw removal, resolve the recorded rows through compact indexes rather than requiring old raw paths to exist. Failure/interruption fixtures must prove this rule without mocks. |

### Table K - Operator reason names mapped to the single typed vocabulary

| # | Requested name | Persisted reason or behavior |
| --- | --- | --- |
| K1 | inactive | SOURCE_INACTIVE; feed-level, no request |
| K2 | fetch_failed | FETCH_FAILED, FETCH_FAILED_HTTP, or FETCH_TIMEOUT, according to observed failure |
| K3 | parse_failed / empty_feed | FEED_PARSE_FAILED / FEED_EMPTY, distinguished in rows and counters |
| K4 | too_old / missing_required_fields | STALE_MAX_AGE_EXCEEDED / MISSING_REQUIRED_FIELDS |
| K5 | duplicate_url / duplicate_story | DUPLICATE_CANONICAL_URL / EVENT_CLUSTER_SIMILARITY; retain evidence and the surviving identity |
| K6 | source_cap | SOURCE_QUOTA_EXCEEDED, with allowance and observed count |
| K7 | desk_cap / kind_cap | DESK_QUOTA_EXCEEDED / KIND_QUOTA_EXCEEDED only for an actually enabled cap. No kind cap is enabled in this plan; desk saturation is a soft penalty rather than an invented rejection rule. |
| K8 | below_score_cutoff | MMR_PORTFOLIO_CUTOFF, with marginal score, selection cutoff, and deciding penalties |
| K9 | replaced_by_carrier | REPLACED_BY_CARRIER, with the chosen representative's identity |
| K10 | publication_budget | PUBLICATION_BUDGET_EXCEEDED only when an enabled publication limit actually refuses an item. No new production budget is introduced by an audit reason. |

### Table L - Required metrics, per-run and rolling definitions

| # | Metric | Calculation and availability |
| --- | --- | --- |
| L1 | Active-source coverage | Distinct active sources with at least one eligible candidate divided by distinct active sources in the run's source snapshot. In a rolling window, use distinct sources active at least once and those with eligible items while active. Phase 1 per run; Phase 2 rolling. |
| L2 | Selection coverage | Distinct sources with selected items divided by distinct sources with eligible items, using the same run/window and primary-source attribution. Phase 1 per run; Phase 2 rolling. |
| L3 | Effective number of sources | For source shares p, compute exp(-sum(p * ln(p))) over nonzero shares. Selected, published and lead bases use unique primary-source articles. Preselection stage bases use unique candidate identities, preserving distinct source-carrier instances as required by I9; do not deduplicate URLs before measuring the deduplication loss. A nonempty uniform N-source fixture yields N; a monopoly yields one. Define zero for an empty item set. Phase 1 selected and stage bases; Phase 2 actual published/leads bases and rolling windows. |
| L4 | Top-source concentration | Sort primary-source article counts descending and divide the configured top-1, top-5, and top-10 sums by total articles. Phase 1 selected; Phase 2 published and rolling, without counting retries or carrier aliases twice. |
| L5 | Gini coefficient of published items by source | Use every source active in the measured source snapshots, including those with zero published items. For sorted counts x, compute sum over ordered source pairs of abs(x_i - x_j), divided by 2 * source_count * sum(x). Phase 2 actual published per-run and rolling. Phase 1 may emit the same instrument with basis selected, never label it published. |
| L6 | Source-kind distribution | Counts and shares by the source-kind snapshot used for the item, with an explicit unknown bucket if no label was recorded. Eligible bases count unique source-candidate identities; selected and published bases count unique primary-source articles, never carrier aliases. Preserve observed labels; do not reinterpret historical items using current config or inferred article genre. Phase 1 eligible/selected; Phase 2 published and rolling. Measurement does not turn kind into a selection gate. |
| L7 | Lost diversity by stage | Compute effective-source count before and after freshness, URL/story deduplication, ranking/normalization, portfolio selection, and published lead selection; record both values and their signed difference. Leads are a subset, so reduced lead diversity is not a claim that the rest were unpublished. Phase 1 available planning stages; Phase 2 publication/leads and rolling. |
| L8 | Event repetition rate | Fraction of unique published articles whose event matches a published event within the preceding configured seven UTC days, using recorded matching evidence/version and excluding same-run duplicates from the historical match. Phase 2 per run and rolling; unavailable rather than zero if complete event evidence is missing. |
| L9 | Cross-day source and event repetition | For each configured prior 1-, 3-, and 7-day window, report source-set and event-set intersection counts and Jaccard overlap: intersection divided by union. Compare each run's published sets with the preceding UTC days. For a rolling reading, union the current sets and their corresponding historical reference sets first, then compute intersection and union; do not average run ratios. Phase 2. |
| L10 | Novel-source contribution | Published article count and share whose primary source had no published article in the preceding configured seven UTC days. Evaluate novelty against history before the article's publishing UTC day; same-day repeat runs do not repeatedly create novelty events. Phase 2 per-run and rolling, deduplicated by article identity. |
| L11 | Metric row and missing data | DiversityMetricRow records metric enum, basis, run/window identity, UTC as_of and boundaries, dimension/stage, value, numerator/denominator where relevant, item/source sample counts, history coverage, algorithm/config version, and availability reason. Use null with empty-denominator, incomplete-history, missing-publication, or missing-event-evidence reasons; never NaN, infinity, or selected-as-published fallback. |
| L12 | Aggregation and fixtures | Recompute each metric from settled row identities and stage memberships over the requested window. Cover uniform, monopolized, zero-yield, multi-carrier, repeated-run, changed-source-status, missing-history, and known-empty fixtures. Record only current readings per metric/window key; Git retains superseded results. |

### Table M - Requested-task coverage and explicit replacements

| # | Task ID | Planned delivery or replacement | Phase |
| --- | --- | --- | --- |
| M1 | TRI-01 | Rows #7 and #8: typed harvest, age, viability, and duplicate decisions; Row #9 records curation losses before partitioning. | 1 |
| M2 | REJ-01 | Rows #1, #2, #6, #8: typed Parquet rejections replace the older JSONL proposal. Table I adds per-source summaries rather than replacing individual rejection evidence. | 1 |
| M3 | CUR-01 | Row #9: independently configured source, domain, vertical, assigned-desk, lens, content-event-type, event-cluster, entity, weak-kind, and coverage terms; unavailable labels are not fabricated. | 1 |
| M4 | CUR-02 | Row #9: configured source/domain/cluster caps and source diversity target. The earlier kind quota and kind-relaxation step are removed by the owner's weak-kind ruling; remaining relaxation follows config. | 1 |
| M5 | PAR-01 | Rows #9, #10, #11: registered unsharded editorial-selection Parquet and sharded dispatch Parquet, both compacted and retained through the gardener. No loose editorial JSON. | 1 |
| M6 | HRV-01 | Row #7: concurrent HTML fetch and real text extraction, categories, and typed extraction/fetch failures. | 1 |
| M7 | SRV-01 | Row #11: planner API and CLI. API calendar version is `2026-10-20`, not numeric `20261020`. | 1 |
| M8 | SRV-02 | Row #4: independent host fingerprint API/CLI and persistence in the existing host ledger. | 1 |
| M9 | SRV-03 | Row #5: independent host CPU/memory sampling API/CLI. | 1 |
| M10 | SRV-04 | Row #6: owner-selected shared `packages/ledger-file-writer` replaces the standalone identity API. | 1 |
| M11 | DIR-01 | Rows #2 and #11: raw dispatches under the registered feed-ingest-plan prefix, compacted under the corresponding compact prefix. | 1 |
| M12 | CI-01 | Row #12: isolated compatibility and audit verification, no production workflow cutover. | 1 |
| M13 | SRC-01 | Row #15 opens the registry-backed kind/tier contracts; Row #7 preserves all listed source metadata and its lifecycle snapshot, without moving config/sources.json. | 1 |
| M14 | FRS-01 | Replaced by Table F, Table O, and Table R: global age/recency defaults, optional per-vertical planning overrides, then an explicit run age override. Source kind is a weak configurable diversity term, not an age-window selector; actual publication desk controls remain separate. | 1 |
| M15 | NRM-01 | Row #9: base per-source allowance plus evidence-backed event-cluster, vertical, and primary-evidence bonuses before global selection; volume-amplification fixture. | 1 |
| M16 | CRQ-01 | Row #14 and Table I: persisted separate operational, article, and portfolio evidence; unperformed semantic evaluation is explicitly not assessed. | 1 |
| M17 | CRD-01 | Row #9: carrier identities, distinct outlets, grouping evidence, chosen representative, and replacement reasons. Row #13 measures cross-day repetition from actual published evidence. | 1 and 2 |
| M18 | GIT-01 | Row #12: named sparse-checkout inventory includes requested code/config paths and every TypeScript verification, recorded-fixture and compact-history dependency; no Python packages or invocation. | 1 |
| M19 | EXP-01 | Row #9: configured exploration share, currently 8 percent of planned slots, only among candidates passing the declared viability checks; no quality bypass. | 1 |
| M20 | MTR-01 | Row #14 computes available per-run readings now; Row #13 completes actual publication, lead, and rolling entropy/Gini/stage readings under Table L. | 1 and 2 |
| M21 | MTR-02 | Row #13: all configured cross-day source/event overlap and novelty readings, with explicit missing-evidence handling. | 2 |

---

## 18. Row #15 - Config-driven source registries and compatible readers

- **Scope:** Replace closed source-kind/tier memberships and named scoring branches with registry-backed identifiers, while preserving historical payload values and current reader behavior before any new producer emits new identifiers.
- **Files touched:**
  - `config/taxonomy.json`
  - `config/idhazh.json`
  - `backend/idhazh/config.py`
  - `backend/idhazh/source_classification.py`
  - `backend/idhazh/contracts/taxonomy.py`
  - `backend/idhazh/contracts/knobs/collect.py`
  - `backend/idhazh/contracts/sources.py`
  - `backend/idhazh/contracts/watchlist.py`
  - `backend/idhazh/contracts/article.py`
  - `backend/idhazh/contracts/digest_day.py`
  - `backend/idhazh/contracts/digest_view.py`
  - `backend/idhazh/contracts/digest_run_fragment.py`
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/contracts/run_plan.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/rank.py`
  - `backend/idhazh/discover.py`
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/stages/common.py`
  - `backend/tests/conftest.py`
  - `backend/tests/contracts/test_source_classification_binding.py`
  - `backend/tests/contracts/test_source_classification_history.py`
  - `backend/tests/contracts/test_panel_queries.py`
  - `backend/tests/council/_imports.py`
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_degrade.py`
  - `backend/tests/pipeline/test_desk_field.py`
  - `backend/tests/pipeline/test_publish_window.py`
  - `backend/tests/test_canaries.py`
  - `backend/tests/test_corpus.py`
  - `backend/tests/test_discover.py`
  - `backend/tests/test_elements.py`
  - `backend/tests/test_evals.py`
  - `backend/tests/test_extract.py`
  - `backend/tests/test_extraction_health.py`
  - `backend/tests/test_leading_stories.py`
  - `backend/tests/test_order_of_the_day.py`
  - `backend/tests/test_plan.py`
  - `backend/tests/test_publish_source_health.py`
  - `backend/tests/test_rank.py`
  - `backend/tests/test_source_dwell.py`
  - `backend/tests/test_source_health.py`
  - `backend/tests/test_tag.py`
  - `backend/utilities/build_canary_day.py`
  - `backend/utilities/data_wrangler.py`
  - `backend/utilities/probe_feeds.py`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/source-classification/legacy-ledger-rows.json`
  - `frontend/src/lib/payload/types.ts`
  - `frontend/src/lib/payload/project.ts`
  - `frontend/src/lib/bands.ts`
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/tests/item-meta.spec.ts`
  - `docs/architecture/sources/source-classification.md`
  - `docs/architecture/sources/discovery.md`
  - `docs/concepts/taxonomy.md`
  - `docs/concepts/placement.md`
  - `docs/architecture/contracts/schemas.md`
  - `TODO/20261020-66-feed-ingest-plan.md`
- **Acceptance gates:** Local: shared selector, named affected contract/scoring/assembly tests, frontend field/vocabulary binding, and one representative published-page smoke. CI: full suite. Compare baseline outputs before/after the registry migration using the existing named fixtures. Without editing code, extend a copied configuration with a new kind and a new numeric tier ID; prove loading, scoring, publishing, and reader display accept them. Reject missing weights, unregistered live references, invalid overrides, and duplicate registry IDs by name.
- **Oracle:** Existing configured kinds/tiers produce the same scores, publication labels, and lead eligibility, and old payload fixtures remain readable; adding a registered kind or tier requires only configuration edits and passes the same pipeline/readers. This does not prove a new kind label is accurate or create a new extraction/scoring algorithm.

Reconciled against main on 2026-10-20: `frontend/src/lib/bands.ts` owns kind
labels and display filters; `frontend/src/lib/source-kinds.ts` does not exist.
`docs/architecture/sources/source-classification.md` is a new living page.
There is no root `AGENTS.md`; `CLAUDE.md` and `docs/agents/bootstrap.md` route
the work. Owner authorization covers this row's Level 5 migration. This worker
opens a ready-for-review PR and does not merge or start another row.
The frontend reads the committed registry in `bands.ts`; its server config
needs no change. Historical gardener and ranking fixtures remain unchanged.

### Authorized CI correction and closure

Implementation and selected local gates pass. Repository-wide CI stopped at
nine existing lint errors in `.github/scripts/serve-evaluator.py` before running
the full backend suite. On 2026-10-20, the owner authorized a separate lint-only
commit in this PR to correct that script without changing its behavior. This
is the sole approved scope addition; no later plan row starts. The correction
and directly dependent contract bindings pass the full CI suite, site, browser
and robots checks. Row #15 is delivered for review; this worker does not merge.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Adopt Table N's registry contracts and Table O's policy boundary. This is the one-time contract migration that makes later membership and parameter changes config-only. It is part of Plan 66, not deferred to a separate redesign. | Owner requested A3 and A4 within Plan 66 |
| 2 | Migrate existing Python readers and frontend consumers before shared TypeScript contracts or writers depend on the open identifiers. Keep numeric tier cells and existing kind spellings, preserving Arrow int64/string types. Version/changelog affected persisted contracts; test old rows without rewriting the committed archive. | CLAUDE.md sections 6 and 11 |
| 3 | Move the existing collect tier weights into the taxonomy registry with identical values. Remove the live fixed-name TierWeights reader and duplicate config authority in the same change. Explicit legacy readers may normalize historical config fixtures; if both old and new weights are supplied and disagree, refuse them rather than choose silently. | Single source of truth; current config parity |
| 4 | Preserve the existing publisher warnings and announcement lead safeguards through explicit registry properties, not equality checks against kind names. These remain existing publication/display behavior, not new planner rejection gates. Add a new kind by setting those declared properties in config. | Existing assemble.py and bands.ts behavior |
| 5 | Preserve genuine historical fixtures. Where a fixture is an authored current-config example, update it; where it represents a legacy input, keep its original bytes and update the reader/test expectation instead. Every legacy normalization has a named fixture. | Reader-before-writer compatibility |
| 6 | Before dispatch, repeat the bounded named-file reference search for SourceKind, SourceTier, TierWeights, tier_weights, and frontend kind-label maps; reconcile this file list with any changes that landed after authoring. Do not leave a hidden closed reader or name-specific scoring branch behind. | Author-a-plan rename/move rule |
| 7 | Expand -> Migrate -> Contract in separate behavioral commits: first expand Python/frontend readers with legacy normalization and binding/history fixtures; then migrate current config/scoring/display consumers while preserving baseline behavior; contract obsolete live enum/name lookups only after those consumers have moved. Keep historical payload read adapters. TypeScript writers follow in later dependent rows. Any Extract Function/Move Function preparation is a separate structural commit, not mixed into these behavioral changes. | CLAUDE.md section 11; reader-before-writer compatibility and two-hat discipline |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Remove only the enums from the new TypeScript planner | Existing Python payload readers, fixed tier-weight lookup, lead logic, and frontend label maps would still reject or mishandle new values | Migrate those named consumers before emitting a new identifier | Owner requested end-to-end config-only extension |
| 2 | Eliminate source kind and tier information entirely | Removes useful provenance, configurable authority weights, and existing publisher disclosures | Requires an owner-approved change to those reader guarantees, not just a parser change | Preserve current behavior while opening membership |
| 3 | Store executable scoring expressions in configuration | Adds an interpreter and an instruction surface when typed values already express the requested variation | New expression validation, security, debugging, and compatibility costs | KISS; no new algorithm requested |

### Table N - Open source-classification contracts

| # | Contract | Declaration and compatibility |
| --- | --- | --- |
| N1 | Configuration owner | Extend the existing `config/taxonomy.json` with `source_kinds`, `source_tiers`, `default_source_kind`, and `default_entity_tier`. It already owns desk/vertical membership; do not create an independent enum or a second registry in the planner. Configuration readers validate the fields they compute on. |
| N2 | Source kind identifier | Replace the closed SourceKind enum with a validated open slug. A live source must reference a declared active kind; new membership is a registry edit. Historical payload readers validate the slug without requiring today's registry to retain it as active. |
| N3 | SourceKindDefinition | Fields: id, display_name, status, retired_on, show_on_item, counts_as_reporting, and requires_reporting_for_lead. The last three are explicit booleans, not inferred from an ID. Seed the existing entries with the current label/display and lead-rule behavior. The configured default supplies an omitted kind on new source configuration and is recorded as a configured default, not an inferred article fact. |
| N4 | Source tier identifier | Replace the closed SourceTier enum with a strict positive integer ID. Preserve existing persisted IDs 1, 2, and 3; a new ID such as 4 does not require a code member. IDs carry no ordinal meaning and no arithmetic score; look up the configured weight. |
| N5 | SourceTierDefinition | Fields: id, display_name, status, retired_on, and finite weight in [0, 1]. Seed IDs 1/2/3 with the current weights 1.0/0.6/0.3. `curate.source_authority_weight` scales this term; zero removes its scoring effect without discarding the provenance field. A missing weight is a named config error, never an implicit default. |
| N6 | Defaults and cross-references | Registry IDs must be unique. Validate source kind/tier references, the configured omitted-kind default, the watchlist entity-tier default, and vertical planning-policy keys before fetching. Validate lens, content-event-type, and entity references against their own named registries; do not treat them as one combined label set. Contract modules do not read config themselves; the loader passes validated registry values to consumers. |
| N7 | Display and legacy history | Build the small frontend kind-label/display map from the committed registry and bind it to the Python config reader. Replace the fixed SourceKind union and hardcoded map. A historical unregistered label remains readable, displays its stored identifier with an explicit unknown-registry state, and is not silently converted to reporting. No runtime backend is introduced. |
| N8 | Reproducible scores | Record the source classification values, applied tier weight, effective vertical planning policy, separate known article labels and assigned desk, and config digests in run/assessment evidence. Historical recorded ratings are not recalculated against today's edited registry. Registry membership is not a persisted schema enum. |
| N9 | Scope of config-only behavior | Adding/renaming display labels, adding IDs, assigning sources, changing weights, and setting existing policy fields is config-only after migration. Stable IDs are retired rather than reused. Adding a new kind of score, evidence, or extraction format still requires a declared contract and implementation. |

### Table O - Effective vertical planning policy and separate desk controls

| # | Contract | Rule |
| --- | --- | --- |
| O1 | FeedScreeningPolicy | Typed fields cover positive integer article/abstract minimum words, positive finite maximum age and recency half-life, and a nonnegative finite recency weight. Existing global triage values remain the defaults; an empty vertical_overrides map preserves current proposed behavior. |
| O2 | FeedCurationPolicy | Typed fields cover source_authority_weight, per-source base allowance and bonus amounts, and each separately named Table T penalty coefficient. Use the existing global curate values as defaults. Kind has only the weak coefficient from Table F, never a kind-specific admission rule. |
| O3 | VerticalPolicyOverride | `vertical_overrides` maps IDs from taxonomy.verticals to partial triage/curate planning policies. Unknown IDs or fields fail config loading. A newly configured vertical with no override inherits global values automatically; no source or vertical name appears in a code branch. Do not retain the misleading desk_overrides key as an alias for this new, unshipped configuration. |
| O4 | Availability and distinct controls | Before summarization, resolve the planning override using the configured feed vertical. Actual assigned desk remains separate and can be unknown. Its existing configured floor/ceiling and placement rules operate once a desk is available, never as a renamed vertical rule. Record both fields; do not rerun earlier admission retroactively. |
| O5 | Precedence | Global defaults, then the matching vertical planning patch, then explicitly allowed run overrides. Merge typed fields; for nested coefficient objects, inherit missing coefficients individually. Omitted means inherit; zero is a real value where allowed. Null does not silently reset a field. |
| O6 | Override boundary | Candidate-specific screening and scoring settings may vary by feed vertical. Harvest concurrency/timeouts, final portfolio-wide share limits/targets, partitioning, reporting, metrics windows, and ledger storage remain global. They are not resolved once per candidate, which would give one portfolio contradictory limits. Desk placement, lens weights, content-event matching, event-cluster grouping, and entity/watchlist settings retain their distinct owners and meanings. |
| O7 | Version and validation | Declare the Python policy models under contracts/knobs/feed_ingest.py and strict TypeScript copies in the named shared policy/config modules, with binding tests. These are authored config shapes, not a new persisted policy document. A stored effective-policy snapshot is part of its declaring persisted assessment contract and follows its version/migration rules. |
| O8 | Substitution tests | Change only one vertical's maximum age or word threshold and verify its admission changes. Change only its authority coefficient or an allowed penalty and verify the declared component changes, with other vertical policies unchanged. Independently vary lens, entity, content-event-type, and event-cluster coefficients. For actual desk changes, use a recorded assigned-desk fixture and the real placement/selection consumer; preserve its original vertical. Add a new kind/tier through config and compare CLI/API results under the same resolved policy and fixed UTC clock. |

### Table P - Managed unsharded editorial selection

| # | Contract | Rule |
| --- | --- | --- |
| P1 | Artifact and owner | `EditorialSelectionRow`, declared in backend/idhazh/contracts/feed_ingest_editorial_selection.py, stores selected article identity, source_id, original vertical, nullable assigned desk, separate known Table T labels, editorial rank, estimated partition work, base ratings, marginal score/penalties, and policy/config identity. It has no worker assignment. Ordinary ledger writer shard metadata remains writer provenance, not a partition decision. |
| P2 | Raw path | Register the prefix `["feed-ingest-plan", "editorial-selections"]`; the shared writer stores immutable Parquet under `state/raw/feed-ingest-plan/editorial-selections/<YYYY>/<MM>/<DD>/<file_id>.parquet`. Do not write a loose JSON manifest alongside it. |
| P3 | Compaction and retention | Register the matching gardener task, add it to the explicit task_names manifest, and use the compact prefix under `state/compact/feed-ingest-plan/editorial-selections/`. Use the configured raw-to-daily-to-monthly-to-yearly retention chain. Absorbed raw files are removed only after compact writes/indexes land successfully; later expiry follows the task's retention settings. No separate cleanup script or permanent unowned file. |
| P4 | Partition input | Resolve the chosen run/attempt's selection through the shared ledger reader, whether raw or compact. Read ranks and work estimates without scoring again. Initial dispatch construction receives the validated harvested-content payload; a later full dispatch replay uses recorded content from the dispatch ledger. Missing content is reported as unavailable, never fetched again silently. Assert a bijection between selected article identities and all dispatch rows across shards, with no missing, duplicated, or added article. |
| P5 | Storage discipline | Reuse recorded assessment/selection fields by identity; do not duplicate full article text merely to preserve a ranking. The editorial ledger alone can reproduce worker allocation from work estimates, not recover article text. No unmanaged state JSON is a dependency of replay. Source-run observations distinguish a legitimate empty selection from missing selection evidence. |
| P6 | Acceptance | TypeScript reads real raw and compact selection fixtures with valid envelopes/digests and recorded compatibility expectations. Replay partitioning from compact data; rankings remain unchanged and incomplete writes preserve readable original evidence. Existing merged gardener coverage remains unchanged; add no Python tests. |

---

## 19. Row #16 - Public data-explorer enrollment and nested ledger delivery

- **Scope:** Publish every feed-ingest-plan ledger's actual columns for `console/data-explorer` and correct nested-family path resolution before the TypeScript writers land, without changing the existing explorer design or adding a runtime backend.
- **Files touched:**
  - `config/idhazh.json`
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/scripts/ledger-prefixes.mjs`
  - `frontend/scripts/payload-ceilings.mjs`
  - `frontend/scripts/raw-listed-through.mjs`
  - `frontend/scripts/copy-visuals.mjs`
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/raw-listed-through.spec.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/console-data-explorer.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `frontend/tests/support/feed-ledgers.ts`
  - `frontend/tests/payload-ceilings.spec.ts`
  - `backend/tests/contracts/test_page_ceilings.py`
  - `.github/workflows/ci.yml`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
- **Acceptance gates:** Local: shared selector, generated-state flat/nested ledger-copy fixtures, focused query-door tests, and one representative explorer journey, not a browser case per ledger. CI: full suite and site-size gate. Verify allowlist enrollment for all new ledger names, correct raw/daily/monthly/yearly/index paths, missing versus known-empty data, and raw-listing coverage after compaction. Use fixtures and the real build/query path, not mocks or external network.
- **Oracle:** A generated nested feed-ingest-plan ledger is staged under its registered prefix, fetched and queried through the real door with its typed columns intact; a flat host-fingerprint fixture still resolves unchanged. This proves enrollment/path/query compatibility, not the eventual site size or live-run query latency.

Preflight correction: the raw-listing reader has its own named test module,
`frontend/tests/raw-listed-through.spec.ts`. Keep its flat-ledger and
copied-module default-path checks, and add nested-prefix coverage there rather
than leaving this direct reader outside the row's checks. Any test that copies
the module must copy its named configuration dependencies too.

Execution scope correction: `console-data-explorer.spec.ts` now checks only
chrome selection in the logic tier. Its existing real query/chart journey is
`console-data-explorer-still.spec.ts`; extend that journey rather than adding a
second browser case. `ledger-prefixes.mjs` owns shared registry-prefix
validation, and `support/feed-ledgers.ts` generates and stages bounded real
Python-contract fixtures for the copy, door and browser checks.

CI scope correction: the six published ledgers need payload ceilings at their
registered nested index paths. Keep the existing longest-index bound check,
using the shared registry and compaction-task name builders rather than flat
names. The bundle gate uses `ledgerFolders` for absent-ledger checks as well;
a ledger with compact or raw files but no compact index still fails.

The coordinator approved these coupled supporting paths on 2026-10-21:
`backend/tests/contracts/test_page_ceilings.py`,
`frontend/scripts/payload-ceilings.mjs`,
`frontend/tests/payload-ceilings.spec.ts`, and `.github/workflows/ci.yml`.
The browser job installs the existing backend dev extra for the real fixture's
native DuckDB schema check, as the site and backend gate jobs already do.
This adds install time and disk for the existing dev dependencies, including
numeric libraries; that incremental runner cost is not measured. It adds no
published bytes, dependency group, mock or substitute journey.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Add dispatches, rejections, source-runs, article-assessments, diversity, and editorial-selections to ledger.published using their registered ledger names, not their folder strings. Host-fingerprint is already published. The public registry list and the published allowlist are distinct controls; appearing in the list alone does not make a ledger queryable. | Owner requested all ledgers in console/data-explorer; verified route/build wiring |
| 2 | Resolve build-side source paths, published target paths, compact indexes, and raw listings from the committed registry prefix. Correct published-ledgers.mjs's flat compact/<ledger> assumption and raw-listed-through.mjs's first-level-only traversal; align these with Row #2's browser LEDGER_FOLDERS bindings and slice-reader resolution. Reject invalid prefixes at the trusted config boundary; fetched source/article text never supplies a path. | Verified nested-family delivery gaps; CLAUDE.md Guardrails #11 and #12 |
| 3 | Publication copies actual Parquet bytes and exposes all stored columns, including full article text in dispatches. The repository is already public; this is not a new disclosure approval gate and does not authorize silently removing text or substituting an undeclared projection. | Owner's full-ledger intent; verified public repository and byte-copy behavior |
| 4 | Retain the existing configured site publication window and explorer limits: explorer_max_fetch_bytes is currently 67,108,864 bytes (64 MiB), reach_days is 365, and the published window follows the widest console preset (current defaults include 90 days). A reach setting does not promise that every historical day is staged. Measure real staged bytes and bounded queries when data exists; if the configured limit or the 1 GB site boundary prevents the intended delivery, stop and surface the measured cost and a concrete alternative. Do not guess performance, silently truncate columns, drop a ledger, or broaden limits without review. | Existing delivery controls; CLAUDE.md Guardrails #2, #10 and #12 |
| 5 | Land this reader/delivery support before Row #6's writers. Keep the existing explorer route and query interaction; no per-ledger bespoke page, second query engine, or production workflow cutover. | Reader-before-writer compatibility; bounded owner request |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Assume config/ledgers.json registration publishes the data | The registry can list a ledger absent from ledger.published, and flat build paths cannot find nested compact files | Explicit allowlist enrollment and prefix-aware site staging are required to query it | Verified explorer/build wiring |
| 2 | Publish only metadata without declaring another shape | Hides real columns despite the all-ledger request and creates an undeclared consumer contract | Owner-approved projection contract, producer, enrollment, retention, and tests; not needed for the current request | Owner's full-ledger intent; Guardrail #3 |

---

## See also

- [../docs/architecture/contracts/identity.md](../docs/architecture/contracts/identity.md) - UUIDv5/v8 and deterministic identifier grammar.
- [../docs/architecture/contracts/persistence.md](../docs/architecture/contracts/persistence.md) - persistence and FileEnvelope contracts.
- [../docs/architecture/contracts/schemas.md](../docs/architecture/contracts/schemas.md) - schema rules and contract definitions.
- [../config/sources.json](../config/sources.json) - canonical source registry.
- [../config/ledgers.json](../config/ledgers.json) - state ledger catalog and compaction enrollment.
- [../docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - execution contract.
