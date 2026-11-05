# Track corpus hydration attempts and outcomes

**Last Updated**: 2026-11-05
**Level**: 5 for the new persisted contract; authoring only.

## 0 - Operating contract

Table A - Scope and execution.

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Make it possible to distinguish a completed corpus harvest, a cadence skip, an empty harvest and a failed attempt without interpreting a green digest run as proof. |
| A2 | Hard scope - in | Record invoked scheduled harvest outcomes through the existing ledger writer; preserve the current sampling cadence; provide a bounded operator status command; wire publication, compaction, retention and tests. |
| A3 | Chosen strategy | Add one observation ledger beside the existing corpus metadata, not a second scheduling authority. This is a proposed contract; Fowler owns any unresolved architecture decision during execution. |
| A4 | ESCALATE triggers | 1. Pause before implementing the Level-5 contract. 2. Surface any change to sampling, cadence, existing corpus shapes, publication failure policy or public explorer consent. 3. Surface any need to change the publisher's identity or replay protocol. |
| A5 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`; parallel N = 4, with the rows below dependent because they share registration and documentation. |

Table B - Scope exclusions and their costs.

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Collecting every article between harvest dates | The corpus remains a periodic sample, not a complete weekly archive. | A separate sampling and artifact-retention design. |
| B2 | Dashboard, notifications and public explorer publication | Operators use the status command and Actions logs rather than a new visual surface or automatic alert. | A separate operator-surface request and publication decision. |
| B3 | Historical attempt backfill | Attempts before the ledger ships remain unknown; metadata and Git history cannot reconstruct every failure or skip. | A separately bounded import with explicit provenance and available historical logs. |
| B4 | Durable records after runner termination or an unsuccessful publication push | A killed process or refused push can leave no committed terminal row; absence is unknown, never success. | A separate workflow-level reconciliation design using actual workflow status. |
| B5 | Manual refill, backfill and history-cleanup operations | The ledger initially answers scheduled digest harvesting only. | An explicit extension defining each operation's identity and outcome semantics. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 1 - Status Reckoner

Table C - Implementation sequence; each row is one meaningful PR.

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Declare and read hydration observations | - | A | PENDING | - | - | - |
| C2 | 2 | Record and publish actual harvest outcomes | 1 | B | PENDING | - | - | - |

## 2 - Row #1 - Declare and read hydration observations

- **Scope:** Ship the registered observation contract, bounded status reader and retention wiring before any production writer emits a row.
- **Files touched:**
  - `backend/idhazh/contracts/corpus_hydration.py` (new)
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/idhazh/telemetry/corpus_hydration.py` (new)
  - `backend/utilities/corpus_hydration_status.py` (new)
  - `config/ledgers.json`
  - `config/gardener/compact-corpus-hydrations.json` (new)
  - `config/idhazh_gardener.json`
  - `backend/tests/test_corpus_hydration.py` (new)
  - `backend/tests/contracts/test_gardener_config.py`
  - `docs/architecture/contracts/state-ledgers.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/how-to/fine-tune-a-model.md`
  - `TODO/20261105-corpus-hydration-ledger-plan.md`
- **Acceptance gates:** Local: from `frontend/`, run `npm run test:changed -- --list`, then `npm run test:changed`; retain the selector's inputs and result. CI: the selected full backend, registry parity, schema and gardener gates on the merge candidate. Use in-memory rows for unit tests and generated named Parquet files for persistence integration; no new disk fixtures or network tests.
- **Oracle:** Write known observations through `ledger.persist`, compact them, and read the same explicit UTC date range; every distinct run/attempt survives exactly once with unchanged outcome and counters. This proves identity and storage, not that any production harvest or push happened.

Table D - Verified findings and proposed contract.

| Id | Decision or finding | Authority or evidence |
| --- | --- | --- |
| D1 | The digest has eight scheduled UTC slots: 00:20, 02:20, 06:20, 10:20, 14:20, 18:20, 20:20 and 22:20. A wake is an opportunity to check, not a harvest promise. | `.github/workflows/digest.yml`, schedule and assemble job; checked against live main on 2026-11-05. |
| D2 | The harvest is due after seven digest-date days by current config. A due invocation reads only that run's accepted article-summary pairs, not all intervening days. | `config/idhazh.json`, `finetune.harvest_every_days`; `backend/idhazh/corpus.py::harvest_is_due`; `backend/idhazh/stages/harvest.py::stage_harvest`. |
| D3 | Live metadata recorded a harvest on 2026-11-05 after 2026-10-29. Committed growth was 93 rows, from 1,793 to 1,886 against the configured 2,000-row cap. | Observation on 2026-11-05: `corpus/corpus.meta.json` on main; commits `4580a199231c75336b23fc948f14d68a8cc5d5c9` and `9b8fac238621213ab70b5664d3fbd0c641ad42dc`; producing Actions runs `41945029386` and `41956049047`. This is dated evidence, not an acceptance target. |
| D4 | The later run correctly logged not-due with the same harvested date; its next configured due date was 2026-11-12. Overlapping earlier runs both harvested and their publication replay combined distinct rows. | Actions run `42047650626`, harvest step at 2026-11-05T17:07:03Z; earlier runs and commits in D3; `backend/utilities/digest_assemble.py`. |
| D5 | The current durable status is a census and schedule checkpoint, not an attempt ledger. `harvested_date` means harvest day; `last_run` means history-cleanup day. Neither a green workflow nor a successful not-due step proves new rows were added. | `backend/idhazh/contracts/corpus.py::CorpusMeta`; `backend/idhazh/contracts/ledger_name.py`; harvest step has `continue-on-error: true`. |
| D6 | Proposed ledger name is `corpus-hydrations`, its enum member is `CORPUS_HYDRATIONS`, and its row contract is `CorpusHydration`. Use a standalone raw-and-compact family with explorer consent false and the normal file envelope. | Follow `docs/architecture/contracts/ledger-registry.md`; no public surface is needed for recording. |
| D7 | Proposed row fields: `date` (digest UTC day), `started_at` and `finished_at` (UTC instants), `outcome` (`harvested`, `empty`, `not_due`, `failed`), `harvested_date_before`, `harvested_date_after`, `next_due_date` (nullable UTC days), `every_days` (positive integer), `forced` (boolean), `window_limit` (positive integer), `rows_before`, `eligible_rows`, `added_rows`, `evicted_rows`, `rows_after` (nullable nonnegative integers), and `fault` (nullable closed vocabulary). Stamp and changelog the native model; do not copy envelope identity fields into it. | Proposed contract; existing `CorpusMeta` and `finetune` settings remain unchanged. |
| D8 | Counters describe the producer-local window, not the final branch after concurrent publication replay. Added means unique incoming identities absent locally; evicted means unique rows removed by the cap. On completed harvests, enforce `rows_after = rows_before + added_rows - evicted_rows`, within `window_limit`. | `backend/idhazh/corpus.py::roll`; existing offered-minus-kept logging can include duplicate rejection, so it is not an eviction oracle. |
| D9 | `empty` means a due harvest completed with no eligible pairs; it does not mean a missing items directory. `harvested` means eligible pairs existed even if deduplication added none. Preserve current checkpoint advancement after a completed empty harvest. | Preserve harvest behavior while making its outcome explicit; `backend/idhazh/corpus.py::harvest`. |
| D10 | Not-due rows have zero work counters and unchanged known size. Failed rows keep only observed facts; unavailable counters and invalid/unreadable checkpoint dates are null, never invented zeros. Fault vocabulary: `input_missing`, `invalid_payload`, `io_error`, `raised`; store no exception text, article content, URLs or absolute paths. | Proposed safe diagnostic boundary; existing logs carry detailed failures through repository logging rules. |
| D11 | Preserve actual retries as separate observations: business key `(date, run_id, attempt)` using envelope identity; duplicate copies of the same observation settle once. Do not let generic highest-attempt settlement erase earlier actual attempts: exercise the supported producer-part identity when needed and test it explicitly. | Existing `ledger.persist` work-unit identity and settlement in `ledger/keys.py`; changing their shared protocol requires escalation, not a ledger-specific workaround. |
| D12 | The operator command requires `--from YYYY-MM-DD --through YYYY-MM-DD`, reads only those named days and the named corpus metadata, and prints JSON with the latest observed attempt, latest observed completed harvest in range, checkpoint, and computed next due date. Missing history reports unknown; no attempt on an expected day is not automatically failure. | Reuse `ledger_files.load_days`; bound all reads without scanning state or corpus article text. Validate real dates and reject reversed ranges. |
| D13 | Metadata remains the only scheduling authority. Compute next due from its observed harvest day and the recorded cadence; if no prior harvest exists, report due now for the requested digest day; if metadata is invalid, report unknown and a command error. | Avoid a second schedule checkpoint that can disagree with production. Historical ledger observations do not override current metadata. |
| D14 | Adopt the standard new-ledger retention declaration and named gardener task; add all required registry, key/model, staging and retention-test entries together. Mark the staged writer as not yet wired until Row #2. | Onboarding checklist in `docs/architecture/contracts/ledger-registry.md`; no new custom retention policy. Record rationale on the existing corpus and ledger pages; their narrow questions remain unchanged. |

Table E - Rejected alternatives.

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Extend corpus metadata with an attempt history | Mixes the scheduling checkpoint with an accumulating log and still requires concurrent-write handling. | A metadata migration plus a separate retention and concurrency design. | Proposed architecture choice; Fowler resolves a disputed alternative. |
| E2 | Parse Actions logs as the authoritative ledger | Retention and wording changes make history incomplete and brittle. | An authenticated API collector, bounded log retention and a reconciliation contract. | Findings D3-D5. |
| E3 | Use aggregate corpus growth as a per-attempt counter | Concurrent replay and deduplication mean branch growth is not one producer's result. | A transaction receipt generated inside publication replay, with a separate persisted contract. | Finding D4 and counter semantics D8. |

## 3 - Row #2 - Record and publish actual harvest outcomes

- **Scope:** File the real harvest result for every reached invocation, including cadence skips and recoverable failures, and preserve that evidence in normal digest publication.
- **Files touched:**
  - `backend/idhazh/corpus.py`
  - `backend/idhazh/stages/harvest.py`
  - `backend/idhazh/telemetry/corpus_hydration.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/utilities/digest_publish.py`
  - `backend/utilities/digest_assemble.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_corpus_harvest.py`
  - `backend/tests/test_corpus_hydration.py`
  - `backend/tests/workflows/test_digest_publication.py`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/workflows/test_ledger_door_jobs.py`
  - `docs/how-to/fine-tune-a-model.md`
  - `docs/architecture/contracts/state-ledgers.md`
  - `TODO/20261105-corpus-hydration-ledger-plan.md`
- **Acceptance gates:** Local: run the shared changed-test selector as in Row #1, covering real harvest execution and generated local Git publication repositories. CI: full applicable backend, workflow, schema and registry gates. After merge, observe the next scheduled assembly without dispatching a data-writing run as a test; inspect its exact run/attempt ledger row, committed path and Actions step. If evidence is absent, investigate publication before claiming the harvest succeeded.
- **Oracle:** Drive real minimal in-memory pairs through due, not-due, empty, duplicate-only and invalid-input boundaries; in integration, publish two overlapping runs with a retry and confirm the ledger retains each observed attempt exactly once while corpus replay keeps the union within the existing cap. Failure injection uses invalid concrete inputs or an invalid temporary destination, not patched business logic. This cannot prove survival after process termination or a push that never lands.

Table F - Producer and publication decisions.

| Id | Decision | Authority or evidence |
| --- | --- | --- |
| F1 | Obtain real counts from the existing harvest and roll, retaining their current public return behavior for existing callers. Record after outcomes are known; never estimate growth from offered rows or rewrite corpus content for telemetry. | Row #1 contract; `backend/idhazh/corpus.py` and existing harvest tests. |
| F2 | Use the actual workflow run, attempt, assemble job, shard and commit identity from the normal publisher. File through the shared writer and completed-write collector, then grant assemble staging authority through the registry. | `backend/utilities/digest_publish.py::run`, `backend/idhazh/ledger/staging.py`; ledger paths must not be constructed by the producer. |
| F3 | Log and re-raise producer errors after filing available failure evidence; an unexpected exception is classified as `raised`, not converted into a successful return. A recording failure must itself be visible and must not hide an original harvest exception. Keep the existing workflow-level non-blocking harvest policy. | Existing harvest step and publisher's completed-write collection in `finally`; observation does not authorize changing delivery policy. |
| F4 | Missing required input on a due harvest is `failed`; an available run directory with no eligible pairs is `empty`. Check cadence before demanding items so a legitimate not-due invocation remains a skip. | Outcome definitions D9-D10; distinguish unavailable evidence from a real empty result. |
| F5 | The new raw files travel with assemble's normal publication, including recorded harvest failures when later publication succeeds. Existing immutable-ledger conflict handling must preserve both runs' observations. Keep corpus replay and its producer-local counter semantics separate. | `backend/utilities/digest_assemble.py`; use real local repositories to verify the final committed files, not only pre-push files. |
| F6 | A success row records local harvest completion; its presence on main proves that observation was committed, not that all eligible pairs survived a later concurrent roll. Status output labels this distinction. Missing terminal evidence stays unknown. | Scope exclusion B4 and decision D8; no success-shaped fallback. |
| F7 | Preserve the configured cadence, existing quality filters, deduplication, checkpoint advancement, rolling cap and history-cleanup meaning. No field change to existing corpus row or metadata contracts is required. | The requested capability is observation, not a sampling or training redesign. |

Table G - Rejected alternatives.

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Fail digest publication whenever harvesting fails | Changes delivery policy rather than making its result visible. | A separate decision about withholding otherwise valid digest output. | Existing non-blocking workflow behavior. |
| G2 | Move harvesting into a separate scheduled workflow | A fresh runner lacks the article text the original scorer read. | Download retained run artifacts under a bounded collection policy or re-fetch and re-score each source. | `docs/how-to/fine-tune-a-model.md`, harvest location rationale. |
| G3 | Write a success row whenever the workflow is green | A successful skip adds nothing and a tolerated harvest failure can leave the workflow green. | No sound implementation; success requires the actual producer outcome. | Verified findings D4-D5. |
