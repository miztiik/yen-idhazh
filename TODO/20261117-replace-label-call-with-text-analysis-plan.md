# Replace the first model call with the local text-analysis service

**Last Updated**: 2026-11-17
**Level**: 5 - persisted shapes, the model-call structure and a new recipient of article text. Row #2 is Level 3, rows #3, #4, #6 and #7 Level 4, rows #1, #5 and #8 Level 5. Rows #7 and #8 are gated by data (Table D).
**Table C amended 2026-11-17**: rows C11 and C12 were added (the prompt stamp counts `visuals.enabled_kinds`; `summarize.asks_for_a_visual_plan` is removed). Authorization of execution is read against the table as it now stands.

## 0. Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The model reads every article twice. The first call (quantity measures, entity links, missed figures, named mentions) is the larger share of model time and feeds a chart planner that has published no chart, while the local text-analysis service returns names, places and number types with exact character offsets in seconds. After this plan the model reads each article once, the service is called over HTTP and timed like every other step, and everything that served the first call is deleted |
| A2 | Hard scope - in | The digest work job runs the service as a sidecar; one HTTP call per item in the fetch loop with a closed outcome and a degrade on every failure; a per-item `items/<item_id>.analysis.json` holding labels and offsets only; regex quantity rows that the service labels date, time or ordinal are dropped and entity and place elements are cut at stored offsets; one model call per item with cleaned prompts and no sentence address in model-facing text; deletion of the first call's code, prompt, settings, accounting branches, utilities, tests and doc sections with every historical payload still readable; a run's prompt stamp that counts the setting that turns chart planning off, and the removal of a summarize setting nothing acts on; what the model is shown for the chart decision is built and bounded by code, first as a cleaner menu, then as code-built candidates behind an offline gate; the analysis step on the console beside fetch and extract |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | 1. Article text addressed to anything other than the committed loopback `text_analysis.base_url`, or any service-returned or fetched text reaching a prompt unfenced, a path, a shell argument or a URL (Guardrail 11). 2. Observation OBS-1 reads lowest available memory below 1.0 GiB on any shard, an out-of-memory kill, or two or more lost shards of eight. 3. Row #7's gate reads STOP (Table D). 4. A persisted shape or knob beyond Table C is needed. 5. A third model call, a different model, a larger context window, or a thread, process or async task that overlaps analysis with model decode. 6. A row removes, disables or narrows a type in `visuals.enabled_types`. 7. Observation OBS-2 shows summary quality outside the prior range (the revert is a person's call, not a row) |
| A5 | Chosen strategy | A sidecar on the service's committed default profile, called only in the fetch loop; contracts and readers before writers; the behaviour commit (one call) before the deletion commit so the revert stays cheap; chart candidates built offline and gated before any model-facing change. Rulings: Fowler (contracts, boundary, test tiers), Carmack (runtime), Andre (prompts, evaluation) |
| A6 | Contracts | Table C names every persisted shape and knob this plan moves. Authorizing execution signs off exactly those; anything else stops the row (trigger 4). No edit to `CLAUDE.md` is proposed: its Guardrail 11 names `model_server.base_url`, and the same control (a committed, loopback-checked address) is applied to `text_analysis.base_url` |
| A7 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 4 |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table B - Out of scope and its cost

| ID | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Diagnosing why no chart has published in production | Charts stay near zero after this plan lands. The cost removal does not depend on it | The pending roll-up row of the plan `20261110-restore-visual-publication-plan.md` ("Prove generated numeric visuals reach publication and the reader"); row #7's report is evidence for it |
| B2 | Removing or narrowing any chart type in config, validator or renderer | None: all nine types stay there. Scatter and bubble cannot validate once the first call is gone, because their per-measure subject link (`Element.entity`) was written only by that call and `refuse_relationship` refuses a plan without it. After row #8 only types a code-built candidate can prove are drawn (decision T5); row #8 stops for a person to confirm that coverage (trigger 6) | A code rule that links a figure to its subject, and a builder rule per type, each proven by an offline gate like row #7's |
| B3 | Retiring chart drawing under the registered kill line | The line keeps being read on the console; this plan neither trips nor moves it | A person's reading of the console's `Charts` table against the line in `docs/architecture/publishing/what-drawing-costs-and-what-has-been-retired-for-it.md` |
| B4 | A `Server-Timing` response header from the service | The ledger holds client wall time only; the service's own stderr log holds the analysis and model-load split | A decision that needs the wire/analysis split, priced by comparing `analyze_ms` with the service log over one scheduled run |
| B5 | Analysis in any language but one | Items from feeds declared in another language get no names or places | A feed declared in a language the service enables, its wheel prepared by the sidecar action, and its own evaluation |
| B6 | Other service features (relations, noun phrases, tokens, important terms), head-noun units, measure phrases | No measure wording and no unit repair beyond dropping rows that are not quantities | A named consumer plus an offline gate |
| B7 | Tightening gate 1 so that unitless numbers are not comparable | The model is still asked about items it will decline | Row #7's report showing candidates exist only where units agree |
| B8 | A pre-run of summary quality before the behaviour commit | The effect is read from the first scheduled runs after row #5; the rollback is a revert | None needed: the change is reversible |
| B9 | Splitting the work stage so the service is stopped before the model server starts | None while OBS-1 holds | OBS-1 tripping (ESCALATE trigger 2) |

Table C - Persisted shapes and knobs this plan moves

| ID | Shape or knob | Says now | Must say | Read-side rule |
| --- | --- | --- | --- | --- |
| C1 | `TextAnalysis`, new contract `backend/idhazh/contracts/text_analysis.py`; run artifact `items/<item_id>.analysis.json` | Does not exist | `version`, `item_id`, `url_key`, `outcome` (closed: ok, skipped_language, unreachable, timed_out, busy, failed, rejected, gave_up), `model` (profile, package, model_version, spacy_version; null unless ok), `source_text_hash` and `source_text_length` of the `Article.text` analysed, `mentions` (closed label vocabulary, start, end) and `sentences` (start, end). No text of any kind. Offsets inside the text, ordered, not overlapping | New family: no old payloads. A run directory without the file reads as "no analysis". Registered in `CONTRACTS` with a frozen fixture |
| C2 | `ItemHealthRow` | The `summary` slot is refused unless the `label` slot is filled ("a second call is recorded only after a first"); no analysis cells | Trailing nullable cells `analyze_ms` and `analysis_outcome` (the C1 vocabulary); `ItemStage.ANALYZE`, non-terminal and absent from `TERMINAL_STAGES`; the `summary` slot may fill alone; the flat five stay the sum over recorded calls; `model_calls` counts recorded calls | Old rows: new cells null; rows with both slots stay valid; the `label` cells are never written again. One changelog line; the frontend column list and the canary writer move in the same change |
| C3 | `Summary` | `call_1` first call, `call_2` second | No field change. The only call (kind `summarize_and_plan`) is recorded in `call_2`; `call_1` is null on new payloads and holds the label call on old ones | The positional flattening into `label_*` and `summary_*` cells already places it in `summary_*`. Readers that treat slot 1 as "a call was recorded" change to "any slot recorded" |
| C4 | `Extractor` in `backend/idhazh/contracts/element.py` | `regex`, `model` | Adds `ner`: a deterministic local model proposed the location and code cut the characters | Old tables unchanged. Tier 2 fields and the `label_source` and `ledger_version` pair stay readable |
| C5 | `AppConfig.text_analysis`, new `TextAnalysisConfig` in `backend/idhazh/contracts/knobs/text_analysis.py` and `config/idhazh.json` | Absent | `base_url` (default `http://127.0.0.1:3020`, loopback-checked, its port equal to the service listener port in `config/text-analysis/settings.json`), `language` (default `en`), `request_timeout_seconds` (default 60), `give_up_after_failures` (default 2; removal condition: two weeks of scheduled runs without a `gave_up` outcome) | An absent block takes the defaults. `prompt_files.generate_labels` is refused by name when row #6 removes it |
| C6 | `ElementsConfig.label_kinds` in `backend/idhazh/contracts/knobs/extract.py` | Absent | One map from service label to use: `entity`, `place` or `not_quantity`. Committed default: PERSON, ORG, NORP, PRODUCT, EVENT to entity; GPE, LOC, FAC to place; DATE, TIME, ORDINAL to not_quantity; every other label has no use | The default lives in the contract |
| C7 | `FeedDef.language` in `backend/idhazh/contracts/sources.py` and `config/sources.json` | Absent | A two-letter lowercase code, default `en`, declared by a curator and never inferred from fetched text | Absent reads as `en`; every committed feed line states it |
| C8 | `PipelineInputs` in `backend/idhazh/contracts/fingerprint.py` | Every input that can move an output: model, runtime, prompts, schema, turn markers, extractor and sanitizer versions; no text-analysis input | A nullable `text_analysis` input: the language, profile, package and model version the service reports for the configured language at shard start; null when the service did not answer | Old manifests lack it and read as null. The console's settings-moved comparison reads the fields generically |
| C9 | `VisualsConfig.candidate_span_characters` and `candidates_per_item` (row #7) | Absent | Defaults 300 and 3; both stamped into a `candidate_rules_version` the report prints | An absent value takes the default |
| C10 | `NoneReason` and `VisualDecision` (row #8 only) | `not_reachable`, `model_declined`, `validation_failed` and the other current members | Appends `no_candidate`; `VisualDecision` gains a nullable `candidate_rules_version` | Old decisions unchanged; the frontend vocabulary copy moves in the same change |
| C11 | `PipelineInputs.prompt_sha256`, built by `calls.prompt_inputs` (row #5) | Hashes the rendered prompts, the whole `summarize` block and, when `visuals.type_selection_enabled` is true, the selected chart types. It does not count `visuals.enabled_kinds`, the only setting that turns chart planning off | Also counts `visuals.enabled_kinds`, so a run with planning off stamps differently from one with it on, and dropping the first call's prompt removes bytes from the stamp and never a setting | No field changes. The digest moves on the first run after the row, as it already does whenever a prompt moves; old manifests are unchanged and the settings-moved comparison marks that day |
| C12 | `SummarizeConfig.asks_for_a_visual_plan` in `backend/idhazh/contracts/knobs/summarize.py` and `config/idhazh.json` (row #6) | A summarize setting, default true, that no code acts on since summary length stopped being limited; only the stamp includes it, through the block dump | Removed. The pipeline-test case flag of the same name in `config/pipeline-tests.json` and `backend/idhazh/contracts/pipeline_tests.py` stays; the test-case writer stops writing it into the summarize block and still empties `visuals.enabled_kinds` | A config that still spells it is refused by name and pointed at `visuals.enabled_kinds`; the committed config and the frozen config fixtures drop the key |

Table D - Row #7 gate on the fixed set (estimates carried from the evaluation ruling; the reading replaces them)

| ID | Check | Reads |
| --- | --- | --- |
| D1 | Every candidate rebuilt as a plan validates and compiles | All, no exception |
| D2 | A reviewer labels 30 candidates blind; at least 27 pair correctly (names belong to the numbers beside them and all numbers measure one thing) | 27 of 30 |
| D3 | Candidates appear only on articles gate 1 admits | No exception |
| D4 | Chart-worthy articles, labelled blind from the articles with at least three same-unit figures plus 20 others, are at least 5% of the set | PASS needs 5% or more |
| D5 | Recall of the chart-worthy articles is at least 50% | PASS needs 50% or more |

Gate result. PASS: D1 to D5 hold and row #8 may be dispatched. STOP-A: D4 is under 5%, a data limit that reads the same quantity as the 5% limb of the registered kill line; ESCALATE (trigger 3) so a person chooses between retiring chart drawing and continuing; the pairing is never widened past one sentence and no chart is forced. STOP-B: D4 holds but D2 or D5 fails; the model-drafted path stays, the pairing rule may be tightened once, and the result is then surfaced (trigger 3).

## 1. Status Reckoner

Table E - Status Reckoner

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Declare the shapes the analysis step moves | - | A | PENDING | - | - | - |
| E2 | 2 | Start the text-analysis service as a sidecar in the digest work job | 1 | B | PENDING | - | - | - |
| E3 | 3 | Read the analysis step on the console | 1 | B | PENDING | - | - | - |
| E4 | 4 | Call the service for every item in the fetch loop | 1, 3 | C | PENDING | - | - | - |
| E5 | 5 | Read each article once | 2, 4 | D | PENDING | - | - | - |
| E6 | 6 | Delete what the first call served | 5 | E | PENDING | - | - | - |
| E7 | 7 | Measure code-built chart candidates offline | 5 | F | PENDING | - | - | - |
| E8 | 8 | Let the model pick among proven candidates | 6, 7 | G | PENDING - starts only when Table D reads PASS and a person confirms its type coverage (trigger 6) | - | - | - |

## 2. Row #1 - Declare the shapes the analysis step moves

- **Scope:** Declare, version and mirror the shapes and knobs of Table C rows C1 to C8 so every reader lands before any writer; nothing calls the service.
- **Files touched:**
  - `backend/idhazh/contracts/text_analysis.py` (new)
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/knobs/text_analysis.py` (new)
  - `backend/idhazh/contracts/knobs/extract.py`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/sources.py`
  - `backend/idhazh/contracts/element.py`
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/contracts/summary.py`
  - `backend/idhazh/contracts/fingerprint.py`
  - `backend/idhazh/fingerprint.py`
  - `config/idhazh.json`
  - `config/sources.json`
  - `tests/fixtures/contracts/text-analysis/ok.json` (new frozen specification)
  - `backend/tests/contracts/test_text_analysis.py` (new)
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_ledger_columns.py`
  - `backend/tests/contracts/test_element_table.py`
  - `backend/tests/contracts/test_two_call_ledgers.py`
  - `backend/tests/test_item_records.py`
  - `backend/tests/test_fingerprint.py`
  - `frontend/src/lib/server/ledger-rows.ts`
  - `frontend/src/lib/charts/series.ts`
  - `frontend/tests/support/telemetry-row.ts`
  - `frontend/scripts/build-canary.mjs`
  - `docs/architecture/sources/item-health.md`
  - `docs/architecture/extraction/elements.md`
  - `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** Local: the shared selector over the changed backend contract tests (`-m contract`) and the frontend ledger-rows spec; ruff and mypy over `backend/`. CI: the complete suite. Record the selected inputs and results.
- **Oracle:** The contract suite. A `TextAnalysis` fixture round-trips; a payload with an offset past `source_text_length`, an unknown label, overlapping mentions, an unordered list or any text field is refused. An `ItemHealthRow` carrying only the `summary` slot loads with `model_calls` of 1, and a row written before this change (both slots) still loads. `ITEM_HEALTH_COLUMNS` equals the contract's columns and the canary writes both new columns. It cannot settle that any writer fills the cells (rows #4 and #5).
- **Decisions:**

Table F - Row #1 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| F1 | `TextAnalysis` carries labels and offsets only. The producer re-slices `Article.text` for every mention and compares it with the text the service returned; the artifact stores neither. The label vocabulary is the service model's closed set; a mention outside it is dropped by the producer rather than failing the item | Fowler, Andre |
| F2 | `sentences` are the service's own spans, stored for candidate adjacency and quotes. `Element.sentence_index` keeps its regex meaning because the same splitter feeds the not-prose gate and committed evaluation metrics | Fowler |
| F3 | The new cells and stage are appended and non-terminal; a failed analysis is a degrade recorded in `analysis_outcome`, never a `FailureCode` | Fowler |
| F4 | The single model call goes in `call_2` so the `summary_*` series stays continuous across the change and the `label_*` series simply ends | CLAUDE.md section 10 |
| F5 | `language` is a feed property declared by a curator. Inferring it from fetched text would let a page steer control flow | Fowler, CLAUDE.md Guardrail 11 |
| F6 | `base_url` is a committed value with no environment override, loopback-checked at config load, with a test pinning its port to the service listener port | Fowler, CLAUDE.md Guardrail 11 |
| F7 | Every knob in C5 has a default; `give_up_after_failures` carries its removal condition | CLAUDE.md Guardrail 6 |
| F8 | The service's identity is a run input because a different model changes names, places and the rows dropped; each artifact also records the identity of the reply that produced it | Fowler |

- **Rejected alternatives:**

Table G - Row #1 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Record the analysis as a `CallKind` in the call slots | Token numbers, `model_calls` and both sum rules would absorb a call that has no tokens | Rewriting the slot rules and every reader that pools the flat five | Fowler |
| G2 | Store mention and sentence text in the artifact | Persists fetched text for no reader and enlarges every item | One field per record; priced by the artifact size over one scheduled day | Fowler |
| G3 | Record the service's identity only in each artifact | A service upgrade or a profile change would move outputs without moving the run's recorded inputs, and artifacts expire | A health request at shard start and one nullable field; taken if the settings-moved comparison proves noisy | Fowler |
| G4 | Detect the language from the article text | A fetched page would steer control flow | A deterministic detector, a new `Article` field and its own evaluation | Fowler |

## 3. Row #2 - Start the text-analysis service as a sidecar in the digest work job

- **Scope:** Each work shard installs the service's locked environment and one English model wheel, starts the service on its committed loopback address before the model server, waits until it answers, and stops it after the work step; nothing in the pipeline calls it yet.
- **Files touched:**
  - `.github/actions/text-analysis-sidecar/action.yml` (new)
  - `.github/workflows/digest.yml`
  - `.github/actions/model-server/action.yml`
  - `backend/idhazh/contracts/knobs/council.py`
  - `docs/reference/github-actions.md`
  - `docs/architecture/text-analysis/text-analysis-api.md`
- **Acceptance gates:** Local: none can run a workflow declaration, and the project has no workflow linter or workflow-file test; review the new action against `.github/actions/model-server/action.yml`'s conventions and run ruff over `backend/` for the knob description edit. CI: the pull request's own checks. The behaviour is proved by OBS-1, not by a dispatch that writes committed data.
- **Oracle:** On the next scheduled run each shard's log shows, in order: the host probe, the service ready with its warm-up request answered, the model server ready, the work step, the service stopped. A shard whose start step failed still completes its work step. It cannot settle memory under real articles (OBS-1) or that the pipeline reaches the service (row #4).
- **Observation OBS-1** (read once rows #2 and #4 are both live; this row is `DONE` only after the reading passes): per shard, read from "What memory this shard used" the lowest available memory, the most memory the service and the model server held at once and the service's peak resident memory; read the step durations of preparation and readiness; read mean and maximum `analyze_ms` from the item-health rows. Baseline: the 2026-11-16 scheduled run (Actions run 43901478491) had a lowest available memory of 3.66 GiB on its worst shard, before any sidecar. Keep the default profile when every shard's lowest available memory is at least 2.0 GiB, mean `analyze_ms` is at most 3 s, maximum at most 45 s and preparation at most 30 s. Between 1.0 and 2.0 GiB, set the service's English `default_profile` to `sm` in `config/text-analysis/settings.json`. Below 1.0 GiB, with any out-of-memory kill, or with two or more lost shards of eight, ESCALATE (trigger 2). The thresholds are estimates carried from the runtime ruling; the reading replaces them.
- **Decisions:**

Table H - Row #2 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | Sidecar in the work job, started before the model server and stopped after "Work the shard". The stage calls it only inside the fetch loop, which finishes before the first model request, so analysis never overlaps decode | Carmack, Fowler |
| H2 | One wheel only. The action reads `text_analysis.language` from `config/idhazh.json` and the profile from the service's own `languages.<language>.default_profile` in `config/text-analysis/settings.json` with `jq`, then sets `TEXT_ANALYSIS_LANGUAGE` and `TEXT_ANALYSIS_PROFILE`. With neither set the prepare script installs every configured profile for English and Chinese. The pipeline pins no profile | Carmack, Fowler |
| H3 | Start step is `continue-on-error`; readiness is bounded at 60 s and proved with one warm-up request; the stop step runs `if: always()`; the service log is uploaded with the runtime log | Carmack |
| H4 | The action sits between "What machine this job drew" and the model-server action, so the host probe runs first and the service holds its memory before the model server takes its own | Carmack |
| H5 | The environment is the service's own locked project: `uv sync --project services/text_analysis/spacy --frozen`, the prepare script and `python -m text_analysis --root "$GITHUB_WORKSPACE"` both run through `uv run --project services/text_analysis/spacy --no-sync`, with the uv version pinned as in `.github/workflows/ner-tests.yml` | Carmack |
| H6 | The memory statement in the model-server action and the same figure in the council knob description are replaced by the figures of the 2026-11-16 scheduled run: one model server peaks well under the earlier statement and a second server still does not fit | Carmack |

- **Rejected alternatives:**

Table I - Row #2 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | A pre-work job per shard that analyzes and hands payloads to the work job | A second runner start and install per shard plus a handoff shape, for a memory risk the 2026-11-16 reading does not show | One runner start per shard and a new persisted handoff; priced by timing one pre-work job | Carmack |
| I2 | Split `stage_work` into an analyze phase (model server down) and a summarize phase (service stopped) | Needs per-item payloads between phases and a stage redesign | A stage-split row plus a state shape; priced by OBS-1 | Carmack, Fowler |
| I3 | Cache the uv environment and the wheel | Saves seconds per shard, and a 382 MB entry competes with the model weights entry inside the shared cache budget | Measured preparation time above 30 s in OBS-1 | Carmack |
| I4 | Pin the `sm` profile | Gives up accuracy for memory the job has | One line in the service settings, taken by OBS-1 | Carmack |
| I5 | Have the pipeline spawn or import the service | Breaks the HTTP-only boundary and puts process lifecycle into `backend/` | A supervisor in `backend/` with orphan and port-race handling | Fowler |

## 4. Row #3 - Read the analysis step on the console

- **Scope:** The console's per-stage time, item time split and slowest-articles reads accept `analyze_ms` as a named stage beside fetch and extract, treating its absence on older rows as zero, so the reader lands before the writer in row #4 puts the stage into the item's named time.
- **Files touched:**
  - `frontend/src/lib/console/duration-cohort.ts`
  - `frontend/src/lib/console/queries/pipelines.ts`
  - `frontend/src/lib/console/pipelines/stage-timings.ts`
  - `frontend/src/lib/console/pipelines/slowest-articles.ts`
  - `frontend/src/lib/console/pipelines/item-time-split.ts`
  - `frontend/src/lib/console/series-tokens.ts`
  - `frontend/src/lib/charts/series.ts`
  - `frontend/tests/duration-cohort.spec.ts`
  - `frontend/tests/time-split.spec.ts`
  - `frontend/tests/console-stage-timing-days.spec.ts`
  - `frontend/tests/console-panel-queries.spec.ts`
  - `frontend/tests/console-pipelines-native.spec.ts`
  - `frontend/tests/support/pipelines-ledgers.ts`
  - `frontend/tests/support/reduction-input.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `docs/architecture/publishing/console-machine.md`
- **Acceptance gates:** Local: the shared selector over the named frontend specs and `backend/tests/contracts/test_panel_queries.py`; svelte-check. One browser smoke of the Pipelines page on a representative window per `docs/how-to/run-the-gates.md` ("Smoke-test a published-site change by hand"), plus a window whose data file is empty. CI: the complete suite. Review the changed view against `docs/concepts/design-system.md`.
- **Oracle:** `durationCohort` keeps a row that has no `analyze_ms`, and keeps a row that carries it only when the named stages plus the gap equal the elapsed time; a window holding only old rows renders as before. It cannot settle how the analysis step looks beside real data (the first scheduled run after row #4).
- **Decisions:**

Table J - Row #3 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| J1 | `durationCohort` currently drops any row whose stage cells are not all finite or whose stages plus gap differ from the elapsed time; an absent `analyze_ms` is read as zero so old rows stay in the cohort | Fowler |
| J2 | The "Label call" detail stays while any day in the window carries it and shows nothing otherwise; the summary-call series is continuous across the change (row #1 decision F4) | CLAUDE.md section 10 |
| J3 | The analysis step takes its own series token; placement and colour are decided on the changed view, not by a new component | Jony, Susan |

- **Rejected alternatives:**

Table K - Row #3 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Leave the cohort unchanged and let analysis time fall into `stage_gap_ms` | The step would be unnamed, and the cohort would flag rows as inconsistent once row #4 names it | A wrong gap series on the console for as long as it stays | Fowler |
| K2 | Remove the Label call detail now | Old days in the window still carry it | Deleting it after the retention window passes, priced by the oldest label-bearing day in the ledger | Fowler |

## 5. Row #4 - Call the service for every item in the fetch loop

- **Scope:** After each item is fetched and extracted, the work stage asks the service over HTTP for entities and sentences, validates the reply against `Article.text`, writes `items/<item_id>.analysis.json`, records `analyze_ms` and the outcome as a named stage, and never fails the item on any analysis failure.
- **Files touched:**
  - `backend/idhazh/analysis/__init__.py` (new)
  - `backend/idhazh/analysis/ask_text_analysis.py` (new)
  - `backend/idhazh/analysis/ask_service_identity.py` (new)
  - `backend/idhazh/analysis/read_analysis_reply.py` (new)
  - `backend/idhazh/analysis/stop_after_failures.py` (new)
  - `backend/idhazh/stages/analyze_item.py` (new)
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/telemetry/record.py`
  - `backend/idhazh/telemetry/spans.py`
  - `backend/utilities/item_health_provenance.py`
  - `backend/tests/support/text_analysis_server.py` (new loopback stand-in)
  - `backend/tests/test_text_analysis_client.py` (new)
  - `backend/tests/test_spans.py`
  - `backend/tests/test_item_records.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `docs/architecture/extraction/how-the-pipeline-asks-the-text-analysis-service.md` (new)
  - `docs/architecture/sources/trust-boundary.md`
  - `docs/architecture/sources/item-health.md`
- **Acceptance gates:** Local: the shared selector over the new client tests and the named pipeline tests; ruff and mypy over `backend/`. Tests drive a loopback HTTP server the test owns and replay one response built in memory from the service's response contract; no fixture file is added and nothing reaches a real service. CI: the complete suite.
- **Oracle:** One article driven through `stage_work` against the stand-in: the stored artifact holds the offsets the reply held and no text; `analyze_ms` is in `NAMED_STAGE_MS` and is not in `queue_wait_ms`, so `item_total_ms` still equals the named stages plus the gap; a closed port, a socket that never answers (the deadline) and a 429 each publish the item with the matching outcome; after `give_up_after_failures` consecutive counted failures the next item records `gave_up` and opens no connection; no analysis request is sent after the first model request; the run's inputs carry the identity the stand-in reported at shard start. It cannot settle real service latency or memory (OBS-1).
- **Decisions:**

Table L - Row #4 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| L1 | One stdlib `urllib` call that never raises and returns an attempt record; no new HTTP dependency | Carmack, CLAUDE.md Guardrail 8 |
| L2 | The request is `POST {base_url}/api/2026-11-08/run-ner-spacy` with `text` = `Article.text`, `language` = `text_analysis.language` and `features` = `["entities", "sentences"]`; `model_profile` is omitted | Fowler, Carmack |
| L3 | The reply is read by a small hand-written reader in `backend/` (the pipeline never imports the service). Both features must be complete. Every mention's returned text must equal `Article.text[start:end]` or the whole analysis is `failed`. The returned text is discarded after the check | Fowler, Andre |
| L4 | Counted failures are unreachable, timed_out, busy and failed. `rejected` (another 4xx) and `skipped_language` are per-item and neither count nor trip the breaker; only an `ok` resets it. A 429 is never retried because the service has no queue and accepted work may hold a lease | Carmack |
| L5 | The call sits in `stage_work`'s fetch loop after the article is known OK and before the item is queued for the model loop. It is synchronous: no thread, executor or async task. `_FetchedWorkItem` carries `analyze_ms`; the queue-wait expression subtracts it; `analyze_ms` joins `NAMED_STAGE_MS` (row #3 has already taught the reader) | Carmack, Fowler |
| L6 | An item whose feed language differs from `text_analysis.language` sends nothing and records `skipped_language` with `analyze_ms` of 0. The feed is found once per shard from `settings.sources.known_feeds()` by `source_id` | Fowler |
| L7 | The router rule: `work.py` calls `analyze_item` and holds no analysis logic; each new module answers one question named in its first sentence | CLAUDE.md section 1a |
| L8 | The shared test settings builders point `text_analysis.base_url` at a port the test owns, so no test can reach a service that happens to run on the developer's machine | CLAUDE.md section 12 |
| L9 | The existing stage-done record with `stage` set to `analyze` carries the outcome and `analyze_ms` as the row's cells do, so a log line and a persisted payload agree; the span is `SpanName.ANALYZE` with the existing outcome and status attributes | CLAUDE.md section 1b |
| L10 | At shard start one `GET {base_url}/api/2026-11-08/get-spacy-health` reads the identity the service holds for the configured language and passes it into the run's inputs (C8); an unanswered request leaves it null and changes nothing else | Fowler |

- **Rejected alternatives:**

Table M - Row #4 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Overlap analysis with the fetch of the next item on a thread | Contaminates model time and adds concurrency to a stage that has none | A worker thread, ordering tests and a shared recorder; priced by the fetch-loop time per shard | Fowler, Andre |
| M2 | Request all six features | Most of the 223 KB response is the token list the pipeline does not read | Parsing and discarding it; priced by response size over one article | Fowler |
| M3 | Retry a busy or timed-out request | An abandoned analysis may still hold a service lease, so a retry can hold two | A bounded retry with backoff; priced by how often OBS-1 sees `busy` | Carmack |
| M4 | A 20 s fixed timeout | Too short for the largest article the extractor allows and for the first request after the model loads | Lost analyses on long articles; priced by the max `analyze_ms` in OBS-1 | Carmack |

## 6. Row #5 - Read each article once

- **Scope:** The model reads each item once and writes the summary and, when code finds a chart reachable, the visual plan; names and places come from the stored analysis, the element table drops rows the service labels date, time or ordinal, and the chart evidence handed to the model is the cleaner menu.
- **Files touched:**
  - `backend/idhazh/stages/two_calls.py` renamed to `backend/idhazh/stages/read_article_once.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/stages/common.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/dag.py`
  - `backend/idhazh/classify/plan_visual_request.py`
  - `backend/idhazh/elements.py`
  - `backend/idhazh/visual_planner.py`
  - `backend/idhazh/summarize.py`
  - `backend/idhazh/telemetry/census.py`
  - `backend/utilities/replay_article_calls.py`
  - `config/idhazh.json`
  - `config/prompts/write-digest-summary.txt`
  - `config/prompts/plan-visual.txt`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_elements.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `backend/tests/test_visual_attempts.py`
  - `backend/tests/test_item_records.py`
  - `backend/tests/test_telemetry.py`
  - `backend/tests/test_spans.py`
  - `backend/tests/test_capture_root.py`
  - `backend/tests/test_replay_article_calls.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
  - `docs/architecture/extraction/elements.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/reference/retained-article-verification.md`
- **Acceptance gates:** Local: the shared selector over the named backend tests (the classify, planner, element, work-record and decoder-grammar groups); ruff and mypy over `backend/`. CI: the complete suite. This row and the pending row of the plan `20261110-restore-visual-publication-plan.md` share `backend/tests/pipeline/_builders.py` and `backend/tests/pipeline/test_work_records.py`; whichever lands second rebases, and neither changes the other's contract.
- **Oracle:** One item against a fake model server: exactly one request arrives; its prompt holds no `[s` sentence address and none of the first job's text; the planning menu has the columns `element_id, kind, span_excerpt, value, unit` and no labels map; a table whose elements carry no subject link never offers scatter or bubble; the same text yields no date, time or ordinal quantity row when its analysis labels them and keeps them when it has no analysis; the item-health row carries only the `summary` slot and passes its validator; the prompt stamp covers the prompts the request sends and every setting that can move an output, and one test shows it moves when `visuals.enabled_kinds` moves while no other input does. It cannot settle whether summaries read worse without the first call's reply in context (OBS-2).
- **Observation OBS-2** (the first two scheduled runs after this row; this row is `DONE` only after the reading): read the summary-evaluation columns of `docs/concepts/summary-metrics.md` and the mean `summarize_ms` per item for those days beside the prior seven days' day-to-day range. Report model time per item before and after, and charts per article that has a code-found candidate once row #7 reports it, each with its baseline and no threshold. When new days fall outside the prior range on two or more summary-evaluation columns, revert this row (trigger 7); the noise of a seven-day range can exceed a small effect, and the report says so rather than naming a tolerance.
- **Decisions:**

Table N - Row #5 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| N1 | One call. System turn: the summary half, the plan half and the generated type and role guide. User turn: a fenced title, the fenced plain article (no sentence address, no JSON escaping), then, only when gate 1 admits a type, the planning menu, then the closing question. Reply `{summary, visual}` with the summary decoded first and the plan fields off the grammar when no type is reachable | Andre |
| N2 | The planning menu keeps `element_id, kind, span_excerpt, value, unit` and loses `sentence_id` and the labels map. Sentence addresses stay out of every model-facing string; offsets and `sentence_index` stay in persisted data for troubleshooting | Andre, Fowler |
| N3 | The element table is the regex quantities and dates minus rows that overlap an analysed mention whose `label_kinds` use is `not_quantity`, plus entity and place elements cut at stored mention offsets with `Extractor.NER`. `elements.max_per_article` and `candidates_found` apply as before | Fowler |
| N4 | An analysis outcome other than `ok` leaves the table regex-only and the item is processed normally | Fowler |
| N5 | Gate 1 (`reachable_types`) excludes scatter and bubble while no element carries a subject link, the precondition `refuse_relationship` enforces, so the guide and grammar never offer a type no plan can satisfy. Nothing is removed from config, validator or renderer | Plan scope, derived from `refuse_relationship` |
| N6 | The rule-derived measure hint is not shown to the model; the planner re-reads the sentence | Andre |
| N7 | The call's cost is recorded in slot 2 (C3). Census readers change from "slot 1 recorded" to "any slot recorded" | CLAUDE.md section 10 |
| N8 | Window sizing (`fits_the_window`) sizes one call: the system turn, the article, the menu and the decode budget. The label output budget and label menu rows leave the arithmetic; the worker re-derives every figure the row quotes against the code that will run before relying on it | Carmack |
| N9 | The two-node call graph in `dag.py` is removed. The replay utility reads an optional retained `analysis.json` beside the retained article; an absent file means regex-only | Plan scope |
| N10 | The module and its entry point are renamed for what they now do; no name in surviving code says first call or two calls (row #6 finishes the search) | CLAUDE.md section 1a |
| N11 | The stamp built by `calls.prompt_inputs` counts `visuals.enabled_kinds` beside the rendered prompts, the summarize block and the selected chart types, because it is the one setting that turns chart planning off and an output moves with it (C11) | Plan scope |

- **Rejected alternatives:**

Table O - Row #5 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Keep the first call only for items whose gate admits a chart | Keeps the wrong-kind and lost-mention defects and the model-steered first call for those items | The saving shrinks to the items that skip it; priced by item-health `label_ms` over the days before this row | Plan scope |
| O2 | Show the model a measure phrase derived from a dependency parse | Generic phrases the planner can re-read from the sentence | A service feature for head nouns plus an offline gate | Andre |
| O3 | Put names and places into the prompt | Adds tokens and puts mention text into a model channel | Fenced rows through `untrusted_block` with a row-count test; priced by tokens per item | Andre, Fowler |
| O4 | Make the visual a separate small call on a shared prefix | A second call for candidate-bearing items and a cache dependency | One extra request per such item; priced by row #7's candidate count | Andre |

## 7. Row #6 - Delete what the first call served

- **Scope:** Delete the first call's request, reply reader, anchoring, budget, prompt, settings, accounting branches, utilities, tests and doc sections, rename every surviving name that still says first call, two calls or label call, remove the summarize setting nothing acts on (C12), and keep every historical payload readable.
- **Files touched:** (from a search of `backend/`, `config/`, `docs/`, `frontend/`, `tests/`, `tools/` and `.github/` for the names below; it is re-run at dispatch)
  - `backend/idhazh/classify/label_request.py` (delete)
  - `backend/idhazh/classify/read_label_reply.py` (delete)
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/measured.py`
  - `backend/idhazh/contracts/knobs/prompts.py`
  - `backend/idhazh/contracts/knobs/summarize.py`
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/contracts/knobs/finetune.py`
  - `backend/idhazh/contracts/pipeline_tests.py` (description text only)
  - `backend/idhazh/contracts/call_cost.py`
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/contracts/element.py`
  - `backend/utilities/measure_two_calls.py` (delete)
  - `backend/utilities/measure_budgets.py`
  - `backend/utilities/pipeline_test_case_config.py`
  - `.github/workflows/idhazh-pipeline-tests.yaml` (comment only)
  - `config/idhazh.json`
  - `config/prompts/generate-labels.txt` (delete)
  - `config/prompts/continue-summary.txt` (renamed for what it is)
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/gardener/pre-yearly-retention/config/idhazh.json`
  - `backend/tests/test_label_request.py` (delete)
  - `backend/tests/test_measure_two_calls.py` (delete)
  - `backend/tests/test_classify.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_prompt_files.py`
  - `backend/tests/support/prompts.py`
  - `backend/tests/test_telemetry.py`
  - `backend/tests/test_item_records.py`
  - `backend/tests/test_item_health_provenance.py`
  - `backend/tests/test_pipeline_artifact_analyzer.py`
  - `backend/tests/contracts/test_two_call_ledgers.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_retention_knobs.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `backend/tests/contracts/test_element_table.py`
  - `backend/tests/contracts/test_ledger_columns.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/tests/test_elements.py`
  - `frontend/src/lib/data/token-deviation-query.ts`
  - `frontend/tests/support/telemetry-row.ts`
  - `docs/architecture/extraction/elements.md`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/architecture/sources/trust-boundary.md`
  - `docs/architecture/sources/item-health.md`
  - `docs/architecture/contracts/determinism.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/console-machine.md`
  - `docs/concepts/classification.md`
  - `docs/concepts/growing-reads.md`
  - `docs/concepts/config/model-file.md`
  - `docs/concepts/config/run-limits.md`
  - `docs/concepts/config/summary-length.md`
  - `docs/concepts/config.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
  - `docs/concepts/console-design/what-the-quality-and-source-panels-draw.md`
  - `docs/concepts/console-design/the-rules-every-console-chart-obeys.md`
  - `docs/how-to/analyze-a-pipeline-artifact.md`
  - `docs/how-to/fine-tune-a-model.md`
  - `docs/reference/pipeline-cost.md`
  - `docs/reference/retained-article-verification.md`
  - `docs/reference/benchmarks/instructions-in-front.md`
  - `docs/reference/benchmarks/two-call-re-read.md`
  - `docs/reference/benchmarks/two-call-window-sizing.md`
  - `docs/reference/benchmarks/how-often-the-truncation-cap-bites.md`
  - `docs/reference/benchmarks/what-a-judge-pair-costs.md`
- **Acceptance gates:** Local: the shared selector over the changed backend tests and `-m contract`; ruff and mypy over `backend/`; the frontend ledger-rows and telemetry specs. CI: the complete suite.
- **Oracle:** A search of `backend/`, `config/`, `docs/`, `frontend/src`, `tests/`, `tools/` and `.github/` for each deleted or renamed name returns only history (changelogs, benchmark pages marked retired) and the historical readers named in decision P2. A payload that still carries `prompt_files.generate_labels` is refused with the removed-knob message, and a config that still carries `summarize.asks_for_a_visual_plan` is refused the same way with a message pointing at `visuals.enabled_kinds`. The pipeline-test writer still empties `visuals.enabled_kinds` for a case whose flag is false and writes nothing into the summarize block. The test that showed a summarize setting no prompt file names still moves the stamp is replaced by the `enabled_kinds` test of row #5, since no such setting remains. Every fixture under `tests/fixtures/contracts/` that carried label cells, Tier 2 fields or `Extractor.MODEL` still loads. It cannot settle that no external consumer reads a deleted name; `docs/architecture/contracts/ledger-registry.md` is the register of readers it checks.
- **Decisions:**

Table P - Row #6 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| P1 | Delete outright: the label request, reply reader, budget and sizing constants, prompt file and its `generate_labels` key, anchoring and mention grouping, proposed-figure code, the measurement utility and its tests, any fixture that holds a label reply, and the doc sections that describe the first call as present design. The reply reader has one caller (the label parser) and no stage reads a captured reply | Fowler |
| P2 | Keep readable, never written again: `Element` Tier 2 fields with `label_source` and `ledger_version`; `Extractor.MODEL`; `CallKind.LABEL`; `FailureCode.LABELS_TRUNCATED`; the `label_*` cells of `ItemHealthRow` and their retired-heading map | Fowler, CLAUDE.md section 10 |
| P3 | `backend/tests/test_labels.py` is the human faithfulness-label suite and is not touched. The symbol search also matches the encoder-judgment and story-dataset modules that use `label_source` for a different feature; they are not touched | Plan scope, derived from reading both suites |
| P4 | Benchmark pages that recorded a measurement of the two-call design stay as history with one line marking the design retired; present-tense pages are rewritten around one call and the service | Fowler |
| P5 | Deleting follows the behaviour commit (row #5) and OBS-2, so the revert path stays cheap until the reading is in | Fowler |
| P6 | The console's prompt-reuse reading changes meaning at the change: with one call per item only the shared system turn is reused, so the cached share steps down on that date without a regression. The page that explains the panel says so | Fowler |
| P7 | `summarize.asks_for_a_visual_plan` is deleted: no code acts on it, and the stamp counts the real switch, `visuals.enabled_kinds` (C11, row #5). The pipeline-test case flag of the same name stays, and only the test-case writer's write into the summarize block goes. A config that still spells the removed setting is refused by name with `refuse_a_removed_knob`, and the two frozen config fixtures drop the key | Plan scope |

- **Rejected alternatives:**

Table Q - Row #6 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Delete in the behaviour commit | A revert would also restore deleted code, tests and docs | One larger revert; priced by the diff size of this row | Fowler |
| Q2 | Remove the label cells and the retired enum members | Old committed rows would stop loading (CLAUDE.md section 10) | A read-side migration of every committed ledger | Fowler |
| Q3 | Keep `summarize.asks_for_a_visual_plan` and stamp it | A stamped setting nothing acts on moves the fingerprint on a value no output depends on, while the setting that does move an output stays uncounted | None beyond a stale knob; priced by the number of files that name it | Plan scope |

## 8. Row #7 - Measure code-built chart candidates offline

- **Scope:** Build the candidate builder as a pure function over the element table, the stored analysis and `Article.text`, and an operator tool that reports over a fixed set of retained articles how many have a candidate and whether each candidate pairs correctly; nothing in the work stage calls it.
- **Files touched:**
  - `backend/idhazh/visual_candidates.py` (new)
  - `backend/utilities/measure_chart_candidates.py` (new)
  - `backend/idhazh/contracts/knobs/visuals.py`
  - `config/idhazh.json`
  - `backend/tests/test_visual_candidates.py` (new)
  - `docs/architecture/publishing/how-chart-candidates-are-built-and-gated.md` (new)
  - `docs/how-to/measure-chart-candidates.md` (new)
- **Acceptance gates:** Local: the shared selector over `backend/tests/test_visual_candidates.py`; ruff and mypy over `backend/`. CI: the complete suite. The report runs as an operator tool over inputs named on its command line and is read against Table D as an observation, not as a CI gate: it needs retained artifacts, not the network.
- **Oracle:** Table D's checks on the fixed set. Unit tests use in-memory tables: a candidate is a `VisualPlan` that `validate_plan` and `can_compile` accept; members share one analysed sentence span, alternate name and number without a newline between them, stay within `candidate_span_characters`, and agree on unit with a unit present (two absent units never agree). It cannot settle whether readers want the charts it finds.
- **Decisions:**

Table R - Row #7 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| R1 | A candidate is minted only from the validator's own tables and kept only if `validate_plan` and `can_compile` accept it; the builder reads no word of the article beyond offsets and labels already validated | Fowler, Andre |
| R2 | Pairing is strict one-sentence adjacency using the service's sentence spans, never unit agreement alone. No analysis means no candidates | Andre, Fowler |
| R3 | The fixed set is the retained `items-<shard>` artifacts of scheduled runs named on the command line, read through the existing retained-input helpers, at least 300 articles, each used once. The tool prints counts and identities only, never article text | Andre |
| R4 | Both denominators are reported once: articles with a code-found candidate, and all articles gate 1 admits | Andre |
| R5 | The pairing knobs of C9 are stamped into a `candidate_rules_version` the report prints | CLAUDE.md Guardrail 6 |
| R6 | The gate and its three results live in Table D in section 0, where the Reckoner and the ESCALATE triggers read them | Andre |
| R7 | Version 1 mints bar and dot candidates only (a name beside a figure). Line and slope need a date-to-figure rule, pie and stacked bar a stated whole, histogram a proof of one variable, scatter and bubble a subject link; each needs its own builder rule and offline gate before it is minted | Andre |

- **Rejected alternatives:**

Table S - Row #7 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| S1 | Build the model-facing pick first | Rests on a rule that found a candidate in about one article in sixty-six on a preview over a small captured set, and every looser pairing read false | A reply contract and a builder wired before the yield is known; priced by Table D | Andre |
| S2 | Pair across sentences by unit agreement | Unit agreement passes two absent units, and the looser pairings read false | False charts; priced by D2 on a looser rule | Andre |
| S3 | Measure on the 66 captured articles again | A fixed, larger, retained set is repeatable and shows variance | None: it is the same tool on fewer inputs | Andre |

## 9. Row #8 - Let the model pick among proven candidates

- **Scope:** For an item with at least one candidate the model replies with a candidate id or none, code writes the plan and the title from the candidate's own spans, and the model-drafted plan path is removed; for an item with none, the model is not asked about a chart. Starts only when Table D reads PASS, and stops at dispatch for a person to confirm the type coverage of decision T5 (trigger 6).
- **Files touched:** (known now; re-derived by name search at dispatch because `NoneReason` is mirrored widely)
  - `backend/idhazh/visual_candidates.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/plan_visual_request.py`
  - `backend/idhazh/stages/read_article_once.py`
  - `backend/idhazh/visual_planner.py`
  - `backend/idhazh/contracts/visual_decision.py`
  - `backend/idhazh/contracts/visual.py`
  - `backend/idhazh/contracts/visual_telemetry.py`
  - `backend/idhazh/telemetry/visual_attempts.py`
  - `backend/idhazh/telemetry/events.py`
  - `backend/idhazh/render/write.py`
  - `config/prompts/plan-visual.txt`
  - `config/idhazh.json`
  - `tests/fixtures/contracts/visual-decision/none.json`
  - `backend/tests/contracts/test_visual_outcomes.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/test_visual_candidates.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `docs/architecture/publishing/visuals.md`
  - `docs/concepts/telemetry.md`
- **Acceptance gates:** Local: the shared selector over the named groups and `-m contract`; the frontend vocabulary binding test for the new `NoneReason` member; one browser smoke of a published chart. CI: the complete suite.
- **Oracle:** The reply grammar is an enum of the item's minted ids or none and is rebuilt per item; a pick outside the enum is unparseable; the plan that code mints from a pick is rerun through `validate_plan` and `can_compile`; a canary article that carries a fence marker, a forged candidate line or overlapping offsets cannot add a row, change an id or reach a path. It cannot settle that readers value the chart.
- **Decisions:**

Table T - Row #8 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| T1 | Reply `visual` is `{"pick": <c1..cK>}` with K at most `candidates_per_item`, or `{"pick": "none", "declined_because": <closed enum>}`; the closed values are figures_unrelated, not_a_comparison, qualified_or_estimated, summary_covers_it and other | Andre |
| T2 | Code writes purpose, type, encodings in pair order, the cited ids, a fixed `why` and the title; the caption is null. The title is built from the candidate's own category spans ("A, B and C, in the unit"), and above the label limit reads "A, B and N more" | Andre |
| T3 | Candidates are rendered by one function inside one `untrusted_block`, each quoting its own sentence; a test asserts the row count. Labels reach the prompt only as a closed subset; mention text is at most `visuals.max_label_characters` | Andre, Fowler |
| T4 | An item with no candidate is not asked about a chart: `none_reason` is `no_candidate` and the plan fields stay off the grammar | Fowler |
| T5 | The pick path draws only the types row #7's builder mints (R7). The validator and renderer keep all nine, and each further type enters when its builder rule and offline gate exist; the coverage is confirmed by a person at dispatch because it narrows what is drawn (trigger 6) | Andre |

- **Rejected alternatives:**

Table U - Row #8 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U1 | A bounded model-written title | A free-text channel to readers under fetched text; `numerals_matched` checks digits, not meaning | A schema bound, the digit check and render-time sanitizing; priced by reviewer reading of code titles in this row's pull request | Andre chose code titles; Fowler held the bounded model title as the alternative |
| U2 | Keep the model-drafted path beside the pick path | Two ways to draw one chart and two sets of rules | The plan half, the type guide and the encoding grammar stay in the prompt; priced by tokens per item | Fowler |
