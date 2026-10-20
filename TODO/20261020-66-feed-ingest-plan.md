# Plan 66 - Feed ingest plan engine

**Last Updated**: 2026-10-20
**Level**: 4 (structural: replaces Python plan subprocess cascade with modular TypeScript services on Bun, pre-fetches full article text, decouples telemetry, enrolls rejections and dispatches as Parquet ledgers, and registers them in config/ledgers.json)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

### Table A - Operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The existing plan stage in digest.yml executes 7 synchronous Python subprocess invocations, creating runner network bottlenecks, high cold-start overhead, and thin-URL blindness where stubs and paywalled links are ranked only to fail during work inference. This plan replaces the planning stage with modular, asynchronous TypeScript services on the Bun runtime, pre-fetches article text to eliminate worker network calls, decouples host telemetry, and writes binary-compatible Parquet dispatch and rejection tables enrolled in config/ledgers.json for automated compaction. |
| A2 | Hard scope - in | - Modular topology: packages/common-contracts, services/host-fingerprints, services/host-probes, services/file-identities, and services/feed-ingest-plan.<br>- Pre-fetching article text in plan (Fat Plan) with linkedom and Defuddle, capturing feed item category tags with graceful fallback to empty array.<br>- Dedicated configuration file: config/feed-ingest-plan.json decentralizing thresholds (min words per article/abstract), timeouts, freshness profiles, normalization rules, and MMR lambdas.<br>- Multi-stage triage gate recording typed drop reasons into an enrolled Parquet ledger under state/raw/feed-ingest-plan/rejections/.<br>- Enrolling feed-ingest-plan and feed-ingest-rejections into config/ledgers.json with grain raw-and-compact for automated gardener compaction.<br>- Set-aware portfolio curation (MMR) with source-kind freshness half-life decay, source opportunity normalization, 3-axis quality separation, and soft concentration caps.<br>- Contextual bin-packing partitioner placed behind a --partition-strategy feature flag.<br>- Dual-mode execution (Hono REST API daemon and one-shot CLI) with structured JSONL event logging.<br>- RFC 9562 UUIDv8 (clock-first) file_id and UUIDv5 unit_id minting matching docs/architecture/contracts/identity.md and FileEnvelope footer metadata.<br>- Isolated CI test workflow (.github/workflows/feed-ingest-plan-test.yml) with 4 user-overrideable inputs, GitHub workflow annotations (::notice::), and step summary reporting. |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Decomposed micro-service architecture running on Bun and Hono, using strict YYYY-MM-DD calendar versioning, action-oriented domain vocabulary (Table E), and parity testing against PyArrow and DuckDB before workflow cutover. Aligned with Fowler (contracts, architecture) and Carmack (runtime, I/O latency) advisor roles in CLAUDE.md section 14. |
| A6 | Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Group A runs first to establish common contracts and ledger enrollment. Groups B, C, D, E, F, and G follow in dependency order. |
| A7 | Driving principle | Complete separation of concerns: host telemetry does not live in the feed planner; identity minting and Parquet serialization are isolated services; curation is independent of runner partitioning; all state ledgers are registered for automated compaction; and production workflows are never edited until isolated CI gates pass. |

### Table B - Hard scope - out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Modifications to .github/workflows/digest.yml | Production workflow continues using existing Python plan until cutover PR | Successful verification in .github/workflows/feed-ingest-plan-test.yml |
| B2 | Moving or renaming config/sources.json | Feed configuration remains at repository root | An owner ruling on repository-wide configuration restructuring |
| B3 | Modifying Python backend/idhazh/stages/work.py | Work shards continue to consume Parquet dispatch tables via existing contracts | A dedicated worker migration plan |
| B4 | Phase 2 rolling metrics (Shannon entropy, Gini coefficient, 7-day repetition curves) | Multi-day diversity metrics are deferred to Phase 2; raw triage and curation counters are captured in Phase 1 | Completion of Phase 1 dispatch pipeline and landing of Row #12 |
| B5 | Llama-server execution during plan stage | Plan stage performs deterministic heuristic curation and text extraction; no local LLM inference in plan | A requirement for semantic LLM classification prior to sharding |

### Table C - ESCALATE triggers

| # | Trigger | Action |
| --- | --- | --- |
| C1 | Parquet file generated by parquet-wasm fails PyArrow or DuckDB deserialization in Python | STOP and surface immediately: schema or footer metadata mismatch |
| C2 | Feed harvesting failure rate exceeds 40% across active sources in config/sources.json | PAUSE and inspect runner DNS, proxy, or upstream connectivity |
| C3 | Runner memory consumption in services/feed-ingest-plan exceeds 1.5 GB during pre-fetch | STOP: evaluate concurrency pool size and DOM streaming limits |
| C4 | Downstream matrix workers report missing columns or schema incompatibility | REVERT to Python plan stage and log exact missing PyArrow types |

---

## 1. Domain Vocabulary Specification

### Table E - Two-Word Action Vocabulary

To comply with schemas.md ("One word per thing, in every identifier"), generic terms are replaced by explicit two-word action pairs:

| Pipeline Phase | Option 1: Verb-Noun (Recommended) | Option 2: Noun-Verb | Operational Meaning |
| :--- | :--- | :--- | :--- |
| **Ingestion** | `harvest-feeds` | `feed-harvest` | Concurrently polls RSS/Atom feeds, parses item `<category>` tags, canonicalizes URLs, and extracts clean DOM text. |
| **Funnel** | `screen-candidates` | `candidate-triage` | Evaluates word-count floors, paywalls, genre freshness windows, and emits typed rejections to Parquet. |
| **Ranking** | `curate-portfolio` | `portfolio-curate` | Normalizes source opportunity, applies set-aware MMR penalties, enforces soft caps, and selects target articles. |
| **Sharding** | `partition-shards` | `shard-partition` | Groups curated items by word/token weight using greedy bin-packing into balanced worker packets. |
| **Storage** | `seal-ledger` | `ledger-seal` | Mints UUIDv8/v5 identities, serializes Arrow tables to Snappy Parquet, attaches FileEnvelope, and writes to disk. |

---

## 2. Configuration Decentralization

Rather than adding planner knobs to `config/idhazh.json`, a dedicated configuration document `config/feed-ingest-plan.json` is created.

### Configuration Schema (`config/feed-ingest-plan.json`)

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
    "freshness_profiles": {
      "reporting": { "half_life_hours": 14, "max_age_hours": 36 },
      "announcement": { "half_life_hours": 20, "max_age_hours": 48 },
      "government": { "half_life_hours": 40, "max_age_hours": 72 },
      "research": { "half_life_hours": 120, "max_age_hours": 336 },
      "analysis": { "half_life_hours": 72, "max_age_hours": 168 },
      "community": { "half_life_hours": 48, "max_age_hours": 120 }
    }
  },
  "curate": {
    "base_source_allowance": 3,
    "bonus_uncovered_event": 1,
    "bonus_underrepresented_desk": 1,
    "bonus_unique_evidence": 1,
    "soft_caps": {
      "max_source_share": 0.10,
      "max_parent_domain_share": 0.15,
      "max_event_cluster_items": 2,
      "min_distinct_sources": 12,
      "min_distinct_source_kinds": 3,
      "relaxation_order": ["source_kind", "distinct_sources", "source_share"]
    },
    "mmr_weights": {
      "lambda_source": 0.25,
      "lambda_domain": 0.15,
      "lambda_topic": 0.10,
      "lambda_event": 0.30,
      "lambda_coverage": 0.10
    },
    "exploration_slot_share": 0.08
  },
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
  }
}
```

---

## 3. Status Reckoner

### Table D - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Shared contracts, schemas, and identity types | - | A | PENDING | - | - | - |
| 2 | Ledger registration and gardener compaction configuration | 1 | A | PENDING | - | - | - |
| 3 | Dedicated feed ingest plan configuration file | 1 | A | PENDING | - | - | - |
| 4 | Host hardware and environment identity service | 1 | B | PENDING | - | - | - |
| 5 | Host CPU and memory profiling service | 1 | B | PENDING | - | - | - |
| 6 | Dedicated identity minting and Parquet sealing service | 1 | B | PENDING | - | - | - |
| 7 | RSS/Atom feed harvest and DOM text extraction | 3 | B | PENDING | - | - | - |
| 8 | Candidate triage screening with Parquet rejection ledger | 7 | C | PENDING | - | - | - |
| 9 | Set-aware editorial portfolio curation | 8 | D | PENDING | - | - | - |
| 10 | Contextual bin-packing partitioner with feature flag | 9 | E | PENDING | - | - | - |
| 11 | Core plan engine entrypoint, dual-mode runner, and sealing | 6, 10 | F | PENDING | - | - | - |
| 12 | Isolated CI test workflow and verification suite | 4, 5, 11 | G | PENDING | - | - | - |
| 13 | Phase 2 rolling diversity metrics and repetition audit | 11 | H | PENDING | - | - | - |

---

## 4. Row #1 - Shared contracts, schemas, and identity types

- **Scope:** Define shared Zod contracts, calendar-versioned API interfaces (`"2026-10-20"`), typed drop reason enumerations, structured JSONL event logging definitions, and `FileEnvelope` schemas in `packages/common-contracts`.
- **Files touched:**
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
- **Acceptance gates:** `bun test` in `packages/common-contracts/`; valid typecheck under strict TypeScript.
- **Oracle:** All schemas round-trip valid JSON fixtures with zero schema coercion errors; `API_VERSION` strictly equals `"2026-10-20"` (date-stamp string).

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use date-stamp string `"2026-10-20"` for `version` fields across all contracts, matching CLAUDE.md section 11 and schemas.md | Fowler, CLAUDE.md section 11 |
| 2 | Enforce strict Zod validation without silent stripping for candidate inputs, dispatches, and rejections | Fowler |
| 3 | Define `DropReason` as an explicit enum with 13 typed drop causes | Andre |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Semver or integer versioning (e.g. `20261020`) | Violates repository persistence contract requiring date-stamp strings (`YYYY-MM-DD`) | Contract schema incompatibility | Fowler |
| 2 | Storing schemas in Python and compiling to TypeScript | Adds build-time toolchain dependencies between Python and TypeScript monorepo packages | 2 additional build steps in CI | Carmack |

---

## 5. Row #2 - Ledger registration and gardener compaction configuration

- **Scope:** Register the `feed-ingest-plan` family with its `dispatches` and `rejections` ledgers in `config/ledgers.json` with `grain: "raw-and-compact"`, and create gardener compaction configurations in `config/gardener/`.
- **Files touched:**
  - `config/ledgers.json`
  - `config/gardener/compact-feed-ingest-plan.json`
  - `config/gardener/compact-feed-ingest-rejections.json`
  - `docs/architecture/contracts/ledger-registry.md`
- **Acceptance gates:** Validate `config/ledgers.json` against `schemas/ledgers.schema.json`; run Python ledger registry validation tests.
- **Oracle:** `python -m idhazh test-ledgers` confirms `feed-ingest-plan` and `rejections` are registered, have valid door prefixes, and compaction configs load without error.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Enroll both dispatches and rejections in `config/ledgers.json` under family `feed-ingest-plan` | Fowler, persistence.md |
| 2 | Store rejections as Parquet files under `state/raw/feed-ingest-plan/rejections/` with `FileEnvelope` footers | Fowler |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Storing rejections as raw `.jsonl` files outside the ledger door | Bypasses gardener compaction automation; cannot be queried alongside enrolled Parquet tables | Manual deletion scripts and lack of compaction | Fowler |

---

## 6. Row #3 - Dedicated feed ingest plan configuration file

- **Scope:** Create `config/feed-ingest-plan.json` containing all tunable knobs for feed harvesting, candidate screening, word-count floors, genre freshness profiles, MMR weights, and partition defaults.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
- **Acceptance gates:** Zod validation test asserts `config/feed-ingest-plan.json` parses successfully with all required blocks.
- **Oracle:** Modifying `min_words_article` in `config/feed-ingest-plan.json` alters the triage threshold without any code edits (CLAUDE.md Guardrail #6).

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Decentralize planner configuration into titled `config/feed-ingest-plan.json` rather than bloating `idhazh.json` | Fowler, CLAUDE.md section 1a |
| 2 | Make article and abstract word count thresholds configurable variables with defaults 180 and 60 | Reader |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Hardcoding word count limits in TypeScript source code | Violates CLAUDE.md Guardrail #6 (no hard coding) | Code changes required for editorial adjustments | Fowler |

---

## 7. Row #4 - Host hardware and environment identity service

- **Scope:** Implement `services/host-fingerprints` as an independent Bun microservice and CLI exposing `GET /api/2026-10-20/fingerprint` to inspect CPU model, cores, L3 cache, and runner environment.
- **Files touched:**
  - `services/host-fingerprints/package.json`
  - `services/host-fingerprints/tsconfig.json`
  - `services/host-fingerprints/src/index.ts`
  - `services/host-fingerprints/src/api/server.ts`
  - `services/host-fingerprints/src/inspect/cpu-model.ts`
  - `services/host-fingerprints/src/inspect/runner-env.ts`
  - `services/host-fingerprints/test/fingerprint.test.ts`
- **Acceptance gates:** `bun test` in `services/host-fingerprints/`; `curl http://127.0.0.1:8082/api/2026-10-20/fingerprint` returns 200 with valid schema.
- **Oracle:** Output contains valid non-empty `cpu_model`, `logical_cores > 0`, and matches `HostFingerprintResponseSchema`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Decouple host fingerprinting completely from feed planning | Fowler |
| 2 | Parse `/proc/cpuinfo` directly on Linux with graceful fallback on macOS/Windows development environments | Carmack |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Invoking Python `host_telemetry_control.py` via subprocess | Retains Python startup latency and subprocess churn in CI | 400ms to 800ms runner latency per step | Carmack |

---

## 8. Row #5 - Host CPU and memory profiling service

- **Scope:** Implement `services/host-probes` as an independent Bun microservice and CLI exposing `/api/2026-10-20/sample` to measure CPU utilization (user, system, idle, iowait) and memory metrics (`/proc/meminfo`, `/proc/vmstat`).
- **Files touched:**
  - `services/host-probes/package.json`
  - `services/host-probes/tsconfig.json`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/server.ts`
  - `services/host-probes/src/probe/cpu-sampler.ts`
  - `services/host-probes/src/probe/memory-probe.ts`
  - `services/host-probes/test/probe.test.ts`
- **Acceptance gates:** `bun test` in `services/host-probes/`; periodic sampling test confirms delta calculations.
- **Oracle:** Returns memory total, free, available in KB, and non-negative CPU percentages summing to 100 within 1% rounding error.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use differential `/proc/stat` delta sampling rather than blocking sleep calls | Carmack |
| 2 | Expose both HTTP REST endpoint (`/api/2026-10-20/sample`) and one-shot CLI (`--sample`) | Fowler |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Bundling CPU/memory sampling inside the feed ingest process | Violates single responsibility principle; prevents probing during work and assemble stages | Tightly coupling telemetry to one stage | Fowler |

---

## 9. Row #6 - Dedicated identity minting and Parquet sealing service

- **Scope:** Implement `services/file-identities` as an independent service and shared utility for RFC 9562 UUIDv8 `file_id` (48-bit Unix ms clock-first), UUIDv5 `unit_id` (namespace `github.com/miztiik/yen-idhazh`), and `apache-arrow` + `parquet-wasm` Snappy serialization with `FileEnvelope` footer metadata per `docs/architecture/contracts/identity.md`.
- **Files touched:**
  - `services/file-identities/package.json`
  - `services/file-identities/tsconfig.json`
  - `services/file-identities/src/index.ts`
  - `services/file-identities/src/api/server.ts`
  - `services/file-identities/src/uuid/unit-id.ts`
  - `services/file-identities/src/uuid/file-id.ts`
  - `services/file-identities/src/parquet/arrow-builder.ts`
  - `services/file-identities/src/parquet/wasm-serializer.ts`
  - `services/file-identities/src/parquet/envelope-footer.ts`
  - `services/file-identities/test/uuid.test.ts`
  - `services/file-identities/test/parquet-parity.test.ts`
- **Acceptance gates:** `bun test` in `services/file-identities/`; parity check confirming generated Parquet is readable by `pyarrow` in Python test script.
- **Oracle:** Generated Parquet footer contains valid JSON `FileEnvelope` with `content_sha256` matching raw row hash, and UUIDv8 sorts chronologically.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use `apache-arrow` + `parquet-wasm` with Snappy compression | Carmack, schemas.md |
| 2 | Implement bit-exact RFC 9562 UUIDv8 clock-first layout matching Python `filenames.py` | Fowler, identity.md contract |
| 3 | Embed `FileEnvelope` as key-value metadata in Parquet file footer | Fowler, persist.py contract |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Pure JavaScript `hyparquet` | Read-focused library; writing complex nested/list columns and footer metadata lacks WASM speed | Higher latency and incomplete footer support | Carmack |
| 2 | Python subprocess for Parquet writing | Re-introduces Python dependency and subprocess latency in plan stage | 1.2s to 2.5s overhead per batch write | Carmack |

---

## 10. Row #7 - RSS/Atom feed harvest and DOM text extraction

- **Scope:** Implement `services/feed-ingest-plan/src/harvest-feeds/` to concurrently poll 110+ feeds from `config/sources.json` using `feedsmith`, capture feed item `category` tags (defaulting to `[]` when absent), canonicalize URLs, and pre-fetch raw HTML via `linkedom` + `Defuddle` to extract clean text, author, lead, and word count.
- **Files touched:**
  - `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/url-cleaner.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/dom-extractor.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; harvest dry-run across 5 sample RSS/Atom feeds produces valid candidate objects with `categories` array and `content_text`.
- **Oracle:** Pre-fetched article text contains >0 words for valid articles, captures author attribution when present, and extracts all XML category elements into `categories: string[]` or defaults to `[]` when missing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Pre-fetch full article HTML during plan stage (Fat Plan) | Carmack, eliminates worker HTTP latency |
| 2 | Extract and normalize RSS/Atom `<category>` elements into candidate records with graceful fallback to `[]` | Andre, category grounding |
| 3 | Read `config/sources.json` at root without changing its path | Fowler |
| 4 | Bound DOM extraction concurrency to 24 with 6,000ms socket timeout | Carmack |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Thin Plan (storing only RSS titles/snippets) | Causes worker stragglers, paywall failures in inference shards, and clickbait mis-ranking | Flaky inference runs and idle LLM compute | Carmack |
| 2 | Headless browser (Puppeteer/Playwright) | Extremely heavy resource footprint in 4 vCPU CI runners | 10x memory and 5x execution time | Carmack |

---

## 11. Row #8 - Candidate triage screening with Parquet rejection ledger

- **Scope:** Implement `services/feed-ingest-plan/src/screen-candidates/` to screen harvested candidates against viability gates (word count floor, paywall detection, category exclusions, freshness decay), and write every rejected item as an enrolled Parquet file to `state/raw/feed-ingest-plan/rejections/<YYYY>/<MM>/<DD>/<file_id>.parquet`.
- **Files touched:**
  - `services/feed-ingest-plan/src/screen-candidates/triage-gates.ts`
  - `services/feed-ingest-plan/src/screen-candidates/freshness-decay.ts`
  - `services/feed-ingest-plan/src/screen-candidates/category-guard.ts`
  - `services/feed-ingest-plan/src/screen-candidates/rejection-sealer.ts`
  - `services/feed-ingest-plan/test/triage.test.ts`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; rejection sealer test asserts that dropped items produce valid Parquet tables with `FileEnvelope` metadata.
- **Oracle:** Every candidate with word count < `min_words` (from config) or HTTP status in [401, 403, 429] is dropped with corresponding typed `DropReason`; rejections file opens cleanly in `pyarrow.parquet.read_table`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Calibrate exponential freshness half-life decay by source kind from config: Reporting (14h/36h max), Announcement (20h/48h max), Govt (40h/72h max), Research (120h/336h max), Analysis (72h/168h max), Community (48h/120h max) | Editor, Andre |
| 2 | Persist all rejections to Parquet under `state/raw/feed-ingest-plan/rejections/` | Fowler, complete auditability |
| 3 | Read minimum word count floors from `config/feed-ingest-plan.json` | Reader |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Dropping items silently without recording rejection reason | Leaves yield loss unobservable; impossible to diagnose feed starvation in CI | Opaque pipeline behavior | Fowler |
| 2 | Storing rejections in uncompacted JSONL | Breaks gardener automated compaction policy | Bypasses ledger door | Fowler |

---

## 12. Row #9 - Set-aware editorial portfolio curation

- **Scope:** Implement `services/feed-ingest-plan/src/curate-portfolio/` to normalize source opportunity (base K=3 + dynamic allowances), execute set-aware MMR re-ranking with soft concentration caps and ordered relaxation, separate quality axes, and output an un-sharded editorial manifest (`*-manifest.json`).
- **Files touched:**
  - `services/feed-ingest-plan/src/curate-portfolio/quota-normalizer.ts`
  - `services/feed-ingest-plan/src/curate-portfolio/quality-decoupler.ts`
  - `services/feed-ingest-plan/src/curate-portfolio/carrier-cluster.ts`
  - `services/feed-ingest-plan/src/curate-portfolio/mmr-portfolio.ts`
  - `services/feed-ingest-plan/src/curate-portfolio/manifest-builder.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; curation test confirms that no single source exceeds 10% of planned items unless relaxation triggered.
- **Oracle:** Max single-source share <= 0.10, max domain share <= 0.15, min distinct sources >= 12 (when yield permits); relaxation order strictly follows: `source_kind` -> `distinct_sources` -> `source_share`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Limit source intake before global pool to K=3 base + dynamic bonus for uncovered event cluster, underrepresented desk, or unique primary evidence | Editor |
| 2 | Separate 3 quality axes: operational reliability, article intrinsic quality, and marginal portfolio contribution | Fowler |
| 3 | Allocate 8% of planned slots for qualifying underrepresented long-tail sources | Editor, Andre |
| 4 | Persist un-sharded editorial manifest (`*-manifest.json`) containing pure ratings and rankings before partitioning | Fowler |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Pure top-N global score sorting | Concentrates digest into 1 to 2 high-volume wire feeds | Loss of publisher and topical diversity | Editor |
| 2 | Hard diversity equality quotas | Fails to publish best coverage during breaking news events with limited publisher coverage | Publishing low-quality fillers to meet quotas | Editor |

---

## 13. Row #10 - Contextual bin-packing partitioner with feature flag

- **Scope:** Implement `services/feed-ingest-plan/src/partition-shards/` to distribute curated articles across worker shards, controllable via `--partition-strategy=bin-pack|round-robin|none`.
- **Files touched:**
  - `services/feed-ingest-plan/src/partition-shards/shard-packer.ts`
  - `services/feed-ingest-plan/src/partition-shards/bin-pack.ts`
  - `services/feed-ingest-plan/src/partition-shards/round-robin.ts`
  - `services/feed-ingest-plan/test/partition.test.ts`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; partition test verifies that bin-packing minimizes variance of total word counts across shards.
- **Oracle:** When `partitionStrategy == "bin-pack"`, standard deviation of shard total word counts is lower than round-robin; when `partitionStrategy == "none"`, all items have `shard = 0`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Place partitioning behind feature flag `--partition-strategy=bin-pack|round-robin|none` | Fowler |
| 2 | Use Largest-Fit-Decreasing greedy bin-packing using article `word_count` by default | Carmack |
| 3 | Retain the `shard: int32` column in the final dispatch Parquet for backward compatibility with Python workers | Fowler |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Requiring Python workers to partition on read without a `shard` column | Requires modifying existing Python `work.py` code; breaks backward compatibility | Higher risk and cross-language coordination | Fowler |
| 2 | Naive round-robin partitioning | Causes worker stragglers where one shard takes 12 minutes on long articles while others finish in 40s | Runner idle time and billable minutes | Carmack |

---

## 14. Row #11 - Core plan engine entrypoint, dual-mode runner, and sealing

- **Scope:** Implement `services/feed-ingest-plan/src/index.ts` and `api/server.ts` supporting dual-mode execution (Hono REST API daemon on `/api/2026-10-20/plan` and one-shot CLI `--cli`), call `services/file-identities` to seal the Parquet dispatch table into `/state/raw/feed-ingest-plan/dispatches/<YYYY>/<MM>/<DD>/<file_id>.parquet`, and emit GitHub Action outputs.
- **Files touched:**
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/tsconfig.json`
  - `services/feed-ingest-plan/src/index.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/routes/plan.route.ts`
  - `services/feed-ingest-plan/src/api/routes/health.route.ts`
  - `services/feed-ingest-plan/src/seal-ledger/plan-sealer.ts`
  - `services/feed-ingest-plan/src/logging/structured-logger.ts`
  - `services/feed-ingest-plan/test/plan-cli.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; one-shot CLI execution test verifies that file is written to `/state/raw/feed-ingest-plan/dispatches/` and JSONL telemetry is printed to stdout.
- **Oracle:** CLI execution prints `shards=<N>`, `matrix=[...]`, and `plan_file_path=<path>` to GitHub outputs format; Parquet file exists at path with size > 0.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Store dispatch tables under `state/raw/feed-ingest-plan/dispatches/` | Fowler |
| 2 | Support dual-mode: long-lived Hono API daemon with `--serve` and one-shot CLI execution with `--cli` | Fowler |
| 3 | Emit structured JSONL telemetry logs with `elapsed_ms` and `step_elapsed_ms` | Carmack |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keeping legacy directory name `/state/raw/run-plan/` | Fails domain-driven naming standards; does not describe payload contents | Retaining confusing legacy path names | Fowler |
| 2 | Unstructured console logging | Makes debugging and CI log filtering (`jq`) fragile and slow | Difficult incident diagnosis in CI | Carmack |

---

## 15. Row #12 - Isolated CI test workflow and verification suite

- **Scope:** Create `.github/workflows/feed-ingest-plan-test.yml` with 4 clean UI inputs, and verification scripts in `packages/common-contracts/test/` to spin up services, execute test plan runs, verify Parquet binary compatibility with Python `pyarrow`, write GitHub workflow annotations (`::notice::`), and generate step summary reports without touching production `digest.yml`.
- **Files touched:**
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `packages/common-contracts/test/verify-parquet.ts`
  - `packages/common-contracts/test/verify-python-parity.py`
  - `packages/common-contracts/test/generate-step-summary.ts`
- **Acceptance gates:** Trigger workflow via `workflow_dispatch` on GitHub Actions; verify 100% green run across all steps.
- **Oracle:** `verify-python-parity.py` successfully reads generated dispatch and rejection Parquet tables with `pyarrow.parquet.read_table`, confirms row counts > 0, extracts `FileEnvelope` footer metadata, and asserts `categories` list column loads without error; GitHub step summary contains formatted yield and drop breakdown.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Create isolated test workflow `feed-ingest-plan-test.yml` rather than modifying `digest.yml` directly | Fowler |
| 2 | Include explicit Python parity test steps asserting `pyarrow.parquet.read_table` compatibility for both dispatches and rejections | Carmack, Fowler |
| 3 | Expose only 4 meaningful inputs with defaults: `date`, `article_limit`, `shards`, and `partition_strategy` | Reader, Fowler |
| 4 | Emit `::notice::` workflow annotations and Markdown table to `$GITHUB_STEP_SUMMARY` modeled on `.github/scripts/ai-pipeline.ts` | Jony, Susan |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Editing `.github/workflows/digest.yml` directly during development | High blast radius; breaks daily publication runs if untested TS code fails | Breaking live production pipeline | Fowler |
| 2 | Exposing 15+ micro-knobs in GitHub Actions UI | Clutters operator UI with brittle low-level parameters | Operator cognitive overload | Reader |

---

## 16. Row #13 - Phase 2 rolling diversity metrics and repetition audit

- **Scope:** Implement post-plan metrics aggregation computing Effective Number of Sources ($N_{\text{eff}} = \exp(H)$), Gini coefficients of published items by source, source-kind entropy, lost diversity by stage, and rolling 7-day cross-day event fingerprint similarity curves.
- **Files touched:**
  - `services/feed-ingest-plan/src/metrics/diversity-metrics.ts`
  - `services/feed-ingest-plan/src/metrics/fingerprint-dedup.ts`
  - `services/feed-ingest-plan/src/metrics/metrics-recorder.ts`
  - `services/feed-ingest-plan/test/metrics.test.ts`
  - `docs/reference/diversity-metrics.md`
- **Acceptance gates:** `bun test` in `services/feed-ingest-plan/`; metric tests verify Shannon entropy and Gini calculations against known mathematical distributions.
- **Oracle:** $N_{\text{eff}}$ strictly equals $\exp(-\sum p_i \ln p_i)$; Gini coefficient equals 0 for perfectly uniform distribution and approaches 1 for monopoly distribution.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Defer advanced rolling metrics computation to Phase 2; Phase 1 captures raw triage and curation counters | Fowler, owner directive |
| 2 | Persist metrics to `/state/raw/diversity-audit/` using standard `FileEnvelope` format | Fowler |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Blocking Phase 1 dispatch pipeline on Phase 2 rolling metric implementation | Delays performance gains and thin-URL fix of the Fat Plan | Prolongs Python plan bottleneck | Fowler |

---

## See also

- [../docs/architecture/contracts/identity.md](../docs/architecture/contracts/identity.md) - UUIDv5/v8 and deterministic identifier grammar.
- [../docs/architecture/contracts/persistence.md](../docs/architecture/contracts/persistence.md) - persistence and FileEnvelope contracts.
- [../docs/architecture/contracts/schemas.md](../docs/architecture/contracts/schemas.md) - schema rules and contract definitions.
- [../config/sources.json](../config/sources.json) - canonical source registry.
- [../config/ledgers.json](../config/ledgers.json) - state ledger catalog and compaction enrollment.
- [../docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - execution contract.
