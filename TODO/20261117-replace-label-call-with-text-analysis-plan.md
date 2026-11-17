# Replace the first model call with the text-analysis service

**Last Updated**: 2026-11-17
**Level**: 5 - the model-call structure and a new recipient of article text.

## 0. Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The model reads every article twice. On 66 captured articles the first call (labels, proposed figures, named mentions) took 3.67 h of 7.04 h of model time and fed a chart planner that published no chart. The local text-analysis service returns the same names and places with exact offsets in seconds. After this plan the model reads each article once and the first call's code is gone. Dropping the call saves its decode (1.78 h, 25%), because the remaining call then reads the article |
| A2 | Hard scope - in | Every workflow that runs the work stage starts the service as a sidecar through one shared action. The work stage calls its existing API over HTTP once per item and times it like fetch and extract. Names and places become entity and place elements, and regex quantity rows the service labels date, time or ordinal are dropped. One model call per item, prompts cleaned, no sentence address in model-facing text. The first call's code, prompt, settings, tests and present-tense docs are deleted. The run's prompt stamp counts `visuals.enabled_kinds`, and the unused `summarize.asks_for_a_visual_plan` setting is removed |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | 1. Article text sent anywhere but the committed loopback `text_analysis.base_url`. 2. After rows #2 and #3 are live, the first scheduled run shows an out-of-memory kill, lowest free memory under 1 GiB, or two lost shards (before the service, 4 of the last 8 runs lost one shard and none lost two, so one lost shard is not a trigger). 3. A persisted shape beyond those rows #1, #3 and #4 name, or a third model call |
| A5 | Chosen strategy | Use the service as it is: its existing request and response, three fields read per mention, nothing new persisted. Cells and readers before the writer; the swap (row #3) before the deletion (row #4), so a revert stays cheap |
| A6 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 4 |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

Table B - Out of scope and its cost

| ID | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Code-built chart candidates that the model picks among | The model still drafts chart plans and the existing validator checks them; no chart is guaranteed | A measured need |
| B2 | Why no chart has published in production | Charts stay near zero | The pending row of `20261110-restore-visual-publication-plan.md` |
| B3 | A language check, a stored analysis, other service features | A non-English article goes through the English model and yields few names; nothing from the service is kept beyond the elements built from it | A consumer that needs it |
| B4 | A subject link for scatter and bubble | Both stay enabled but cannot validate, because only the first call wrote the link | A code rule that links a figure to its subject |
| B5 | Counting analysis time where the month fold sums elapsed time (`backend/idhazh/retention.py`, `backend/utilities/measure_ledgers.py`) | A folded month omits analysis time, under 0.1 percent of an item's time (an estimate); the first such month folds in 2028 | The next change to the fold, which needs its own version stamp |

## 1. Status Reckoner

Table C - Status Reckoner

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Make room for the analysis step | - | A | DONE | probable-chainsaw | own pull request | nested session |
| C2 | 2 | Start the service in the digest job | - | A | DONE | miniature-chainsaw | own pull request | nested session |
| C3 | 3 | Replace the first call with the service | 1, 2 | B | IN-FLIGHT | reimagined-system | own pull request | nested session |
| C4 | 4 | Delete what the first call served | 3, 5 | C | PENDING | - | - | - |
| C5 | 5 | Start the service in every workflow that runs the work stage | - | B | PENDING | - | - | - |

## 2. Row #1 - Make room for the analysis step

- **Scope:** `ItemHealthRow` records `analyze_ms` as a named stage and accepts the summary slot alone, the config names the service and maps its labels, and the console reads the new stage. Nothing calls the service yet.
- **Files touched:**
  - New: `backend/idhazh/contracts/knobs/text_analysis.py`
  - Code: `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/extract.py`, `backend/idhazh/contracts/item_health.py`, `backend/idhazh/telemetry/record.py`, `config/idhazh.json`
  - Tests: `backend/tests/contracts/test_app_config.py`, `backend/tests/contracts/test_ledger_columns.py`, `backend/tests/contracts/test_two_call_ledgers.py`, `backend/tests/contracts/test_panel_queries.py`, `backend/tests/test_item_records.py`
  - Frontend: `frontend/src/lib/server/ledger-rows.ts`, `frontend/src/lib/charts/series.ts`, `frontend/src/lib/console/duration-cohort.ts`, `frontend/src/lib/console/series-tokens.ts`, `frontend/src/lib/console/queries/pipelines.ts`, `frontend/tests/support/telemetry-row.ts`, `frontend/scripts/build-canary.mjs`, `frontend/tests/duration-cohort.spec.ts`
  - Docs: `docs/architecture/sources/item-health.md`
- **Acceptance gates:** Local: the shared selector over the named backend contract tests and `duration-cohort.spec.ts`; ruff and mypy over `backend/`. CI: the complete suite.
- **Oracle:** An `ItemHealthRow` with only the `summary` slot loads and a row written before this change still loads; `ITEM_HEALTH_COLUMNS` equals the contract's columns; `durationCohort` keeps rows with and without `analyze_ms`, and keeps one that carries it only when the stages plus the gap equal the elapsed time. It cannot settle that a writer fills the cell (row #3).
- **Decisions:**

Table D - Row #1 decisions

| ID | Decision |
| --- | --- |
| D1 | `text_analysis` config: `base_url` (default `http://127.0.0.1:3020`, loopback-checked like `model_server.base_url`, no environment override, a test pins its port to the service's listener port), `language` (default `en`, also read by the sidecar step so one value decides the wheel), `request_timeout_seconds` (default 60) |
| D2 | `elements.label_kinds` maps a service label to `entity`, `place` or `not_quantity`. Default: PERSON, ORG, NORP, PRODUCT, EVENT to entity; GPE, LOC, FAC to place; DATE, TIME, ORDINAL to not_quantity; any other label is ignored, so a new use is a config line |
| D3 | `analyze_ms` is nullable and joins `NAMED_STAGE_MS` beside fetch and extract; old rows are null. The summary slot may fill without the label slot, which row #3 relies on; rows with both slots stay valid (Fowler) |
| D4 | The console's duration cohort and its query list `analyze_ms` as a stage and read an absent value as zero; otherwise the cohort drops every row that carries it |

## 3. Row #2 - Start the service in the digest job

- **Scope:** Each work shard installs the service's locked environment and one English model wheel, starts the service on its committed address before the model server, waits for its health route, and stops it after the work step. Inline steps in `digest.yml`, no new file.
- **Files touched:** `.github/workflows/digest.yml`, `.github/actions/model-server/action.yml`, `backend/idhazh/contracts/knobs/council.py`, `docs/reference/github-actions.md`
- **Acceptance gates:** Local: none; a workflow declaration cannot be run, and the project has no workflow linter or workflow-file test. CI: the pull request's own checks.
- **Oracle:** The next scheduled run's log shows the service ready before the model server and stopped after the work step, and a shard whose service failed to start still completes its work step. It cannot settle memory under real articles (OBS-1).
- **Observation OBS-1** (after rows #2 and #3 are live; row #3 is `DONE` only after this reading and OBS-2): per shard, read the lowest free memory (`os_mem_available_min_bytes` in its item-health rows), the most the model server and Python held at once (the "What memory this shard used" step) and the mean `analyze_ms`. Baseline: the same readings for Actions run 44121930049, the first scheduled run after the memory fix of 2026-11-17 and before row #2. An out-of-memory kill, lowest free memory under 1 GiB (an estimate), or two lost shards in one run (before the service, 4 of the last 8 runs lost one and none lost two) stops the plan (trigger 2); the choices are the service's `sm` profile (one line in `config/text-analysis/settings.json`) or splitting the work stage.
- **Decisions:**

Table E - Row #2 decisions

| ID | Decision |
| --- | --- |
| E1 | A sidecar beside the model server, not a separate job. It is called only in the fetch loop, which ends before the first model request, so analysis never overlaps decode |
| E2 | One wheel: the step reads `text_analysis.language` from `config/idhazh.json` and the profile from the service's own `languages.<language>.default_profile` with `jq`, then sets `TEXT_ANALYSIS_LANGUAGE` and `TEXT_ANALYSIS_PROFILE`; unset, the prepare script installs every profile for English and Chinese |
| E3 | The steps sit between "What machine this job drew" and the model-server action. The start step is `continue-on-error`, readiness is polled on `GET /api/2026-11-08/get-spacy-health` for at most 60 s, the stop step runs `if: always()`, and the service log is uploaded with the runtime log |
| E4 | The environment is the service's own locked project (`uv sync --project services/text_analysis/spacy --frozen`, uv pinned as in `.github/workflows/ner-tests.yml`), started with `python -m text_analysis --root "$GITHUB_WORKSPACE"`; nothing is cached |
| E5 | The memory statement in the model-server action and the council knob description ("no room for a second", 14.31 GiB) is replaced by the 2026-11-16 reading: one model server plus the job's Python peaked at 10.04 to 11.62 GiB of 15.61 GiB |

## 4. Row #3 - Replace the first call with the service

- **Scope:** After each item is extracted the work stage asks the service for entities; the model reads the article once and writes the summary and, when code finds a chart reachable, the visual plan; the first call is no longer dispatched.
- **Files touched:**
  - New: `backend/idhazh/ask_text_analysis.py`, `backend/tests/test_text_analysis_client.py`
  - Renamed to say what it does: `backend/idhazh/stages/two_calls.py`
  - Code: `backend/idhazh/stages/work.py`, `backend/idhazh/classify/calls.py`, `backend/idhazh/classify/dag.py`, `backend/idhazh/classify/plan_visual_request.py`, `backend/idhazh/elements.py`, `backend/idhazh/telemetry/census.py`, `backend/idhazh/telemetry/spans.py`, `backend/idhazh/contracts/summary.py`, `backend/idhazh/contracts/knobs/text_analysis.py`, `backend/utilities/replay_article_calls.py`, `config/idhazh.json`, `config/prompts/write-digest-summary.txt`, `config/prompts/plan-visual.txt`
  - Tests: `backend/tests/test_classify.py`, `backend/tests/test_elements.py`, `backend/tests/test_fingerprint.py`, `backend/tests/test_spans.py`, `backend/tests/test_item_records.py`, `backend/tests/test_telemetry.py`, `backend/tests/test_chart_vocabulary.py`, `backend/tests/test_visual_attempts.py`, `backend/tests/test_capture_root.py`, `backend/tests/test_replay_article_calls.py`, `backend/tests/contracts/test_decoder_grammar.py`, `backend/tests/pipeline/_builders.py`, `backend/tests/pipeline/test_work_records.py`
  - Docs: `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/model-boundary.md`, `docs/architecture/extraction/elements.md`, `docs/architecture/sources/trust-boundary.md`, `docs/reference/retained-article-verification.md`
- **Acceptance gates:** Local: the shared selector over the named backend tests; ruff and mypy over `backend/`. Tests drive a loopback server the test owns and a fake model server; nothing reaches a real service. CI: the complete suite. Merge gate, held by the maintainer: row #2's Oracle has been read in a scheduled digest run on the workflow then on main (row #5's, when it merges first). The loaded service adds about 0.74 GiB (an estimate) to every shard; the memory fix leaves hosts with the AMX instruction set 3.79 to 5.01 GiB lowest free (Actions run 44121930049), against 0.20 before.
- **Oracle:** One item against the stand-ins: exactly one model request, its prompt holds no `[s` sentence address and none of the first call's text; mentions become elements whose excerpts are re-sliced from `Article.text`; quantity rows the service labels date, time or ordinal are gone; a closed port, a hung socket and a malformed reply each publish the item with the regex-only table and a warning; `analyze_ms` is in the item's named time and not in `queue_wait_ms`; the item-health row carries only the `summary` slot; the prompt stamp moves when `visuals.enabled_kinds` moves. It cannot settle whether summaries read as well without the first call's reply (OBS-2).
- **Observation OBS-2** (the first two scheduled runs after this row; this row is `DONE` only after this reading and OBS-1): read the summary-evaluation columns of `docs/concepts/summary-metrics.md` beside the prior seven days. Revert this row when they fall outside that range; no tolerance is named because day-to-day noise can exceed a small effect.
- **Decisions:**

Table F - Row #3 decisions

| ID | Decision |
| --- | --- |
| F1 | The request is the existing `POST {base_url}/api/2026-11-08/run-ner-spacy` with `text` = `Article.text`, `language` and `features` = `["entities"]`. The pipeline reads `label`, `start_char` and `end_char` of each mention; the excerpt is re-sliced from `Article.text`, and a mention whose returned text differs is dropped. No new contract and no stored analysis |
| F2 | One synchronous call per item in the fetch loop, after the article is known OK, inside an `analyze` span; `_FetchedWorkItem` carries the mentions to the model loop. Any failure (closed port, timeout, malformed reply) degrades the item to the regex-only table and logs why. No retry, no thread. The deadline is `text_analysis.request_timeout_seconds`, lowered from 60 to 15 (an estimate: about five times the 2.7 s cold request measured on a hosted runner), so a hung service costs at most 15 s an item, 20 minutes over the busiest shard's 80 items rather than 80. `analyze_ms` is subtracted from `queue_wait_ms` so it stays in the item's time |
| F3 | `element_table` takes the mentions: entity and place elements (`Extractor.MODEL`, as the first call's mentions used; `Element.entity` unset) and regex quantity rows that overlap a `not_quantity` mention dropped. Callers that pass none are unchanged |
| F4 | One call per item. System turn: the summary half, the plan half and the type guide. User turn: fenced title, fenced plain article, the planning menu without its `sentence_id` column and labels map when a chart is reachable, the closing question. No sentence address in any model-facing text (Andre) |
| F5 | The call is recorded in `call_2` so the `summary_*` series stays continuous; the census reads "any slot recorded". `dag.py` keeps only the one-call window check |
| F6 | The prompt stamp built by `calls.prompt_inputs` counts `visuals.enabled_kinds` beside the rendered prompts, the summarize block and the selected types. Dropping the first call's prompt removes bytes from the stamp, never a setting |

## 5. Row #4 - Delete what the first call served

- **Scope:** Delete the first call's request, reply reader, anchoring, budget, prompt, settings, utility, tests and present-tense docs, and remove the summarize setting nothing acts on.
- **Files touched:** (from a search for the names being deleted; re-run at dispatch)
  - Deleted: `backend/idhazh/classify/label_request.py`, `backend/idhazh/classify/read_label_reply.py`, `backend/utilities/measure_two_calls.py`, `config/prompts/generate-labels.txt`, `backend/tests/test_label_request.py`, `backend/tests/test_measure_two_calls.py`
  - Code: `backend/idhazh/classify/calls.py`, `backend/idhazh/measured.py`, `backend/idhazh/summarize.py`, `backend/idhazh/contracts/knobs/prompts.py`, `backend/idhazh/contracts/knobs/summarize.py`, `backend/idhazh/contracts/pipeline_tests.py` (description only), `backend/idhazh/contracts/call_cost.py` (docstring only), `backend/idhazh/contracts/item_health.py` (descriptions only; no column is removed), `backend/utilities/pipeline_test_case_config.py`, `.github/workflows/idhazh-pipeline-tests.yaml` (comment only), `config/idhazh.json`
  - Fixtures: `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `tests/fixtures/gardener/pre-yearly-retention/config/idhazh.json`
  - Tests: `backend/tests/test_classify.py`, `backend/tests/test_summarize.py`, `backend/tests/test_fingerprint.py`, `backend/tests/test_prompt_files.py`, `backend/tests/support/prompts.py`, `backend/tests/test_elements.py`, `backend/tests/test_telemetry.py`, `backend/tests/test_item_records.py`, `backend/tests/test_item_health_provenance.py`, `backend/tests/test_pipeline_artifact_analyzer.py`, `backend/tests/contracts/test_two_call_ledgers.py`, `backend/tests/contracts/test_app_config.py`, `backend/tests/contracts/test_decoder_grammar.py`, `backend/tests/contracts/test_element_table.py`, `backend/tests/pipeline/test_work_records.py`
  - Docs: `docs/architecture/extraction/elements.md`, `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/model-boundary.md`, `docs/architecture/summarize/throughput.md`, `docs/architecture/sources/trust-boundary.md`, `docs/architecture/sources/item-health.md`, `docs/architecture/publishing/console-machine.md`, `docs/concepts/config/model-file.md`, `docs/concepts/config/run-limits.md`, `docs/concepts/config/summary-length.md`, `docs/concepts/config.md`
- **Acceptance gates:** Local: the shared selector over the changed backend tests and `-m contract`; ruff and mypy over `backend/`. CI: the complete suite.
- **Oracle:** A search of `backend/`, `config/`, `docs/`, `frontend/src`, `tests/`, `tools/` and `.github/` for each deleted name finds only history (changelogs, dated benchmark pages) and the kept readers of G2. A config that still spells a removed key is refused with the removed-knob message, and every committed fixture still loads. It cannot settle that no outside reader uses a deleted name; `docs/architecture/contracts/ledger-registry.md` lists the readers.
- **Decisions:**

Table G - Row #4 decisions

| ID | Decision |
| --- | --- |
| G1 | Delete outright: the label request, reply reader, anchoring, budget and sizing constants, prompt file and its `generate_labels` key, the measurement utility, their tests, and the doc sections that present the first call as current design |
| G2 | Keep readable, never written again: the `Element` Tier 2 fields with `label_source` and `ledger_version`, `Extractor.MODEL`, `CallKind.LABEL`, `FailureCode.LABELS_TRUNCATED` and the `label_*` cells |
| G3 | `prompt_files.generate_labels` and `summarize.asks_for_a_visual_plan` are refused by name, the latter pointing at `visuals.enabled_kinds`. The pipeline-test case flag of the same name stays; only the test-case writer's write into the summarize block goes. The stamp test that used the knob is replaced by row #3's `enabled_kinds` test |
| G4 | Dated benchmark pages stay as history. `backend/tests/test_labels.py` is the human faithfulness-label suite and is not touched |

## 6. Row #5 - Start the service in every workflow that runs the work stage

- **Scope:** One shared action installs, starts and stops the service. The digest work job and both pipeline-test jobs use it, so a pipeline test walks the path production walks, and the steps row #2 wrote inline in `digest.yml` move into it unchanged.
- **Files touched:** (from a search of the workflows for the work stage's entry points; the other workflows that start the model server run none)
  - New: `.github/actions/text-analysis-service/action.yml`
  - Code: `.github/workflows/digest.yml`, `.github/workflows/idhazh-pipeline-tests.yaml`
  - Docs: `docs/reference/github-actions.md`
- **Acceptance gates:** Local: none, as for row #2; parse the YAML and read the diff. Hosted: the action's start and stop on a hosted runner from a throwaway branch, answering one real request, with no digest run (a run writes committed data). CI: the pull request's own checks.
- **Oracle:** The hosted run shows the start answering and the stop leaving no process, and a service that will not start still lets the job finish. The next scheduled digest run then logs the same start and stop lines as row #2's Oracle. The pipeline-test jobs are read, not run, because a dispatch runs the real model for hours; their first dispatch shows the same lines. It cannot settle that a pipeline test's items now match production's.
- **Decisions:**

Table H - Row #5 decisions

| ID | Decision |
| --- | --- |
| H1 | One action with a `mode` input, `start` or `stop`. A composite action cannot run after its caller's later steps, so each workflow calls it a second time with `if: always()`. Start is setup-uv, install and start, every step `continue-on-error` as row #2 wrote them; stop signals the service's process group. Row #2's rules (E2 to E4) and its log lines move unchanged |
| H2 | A caller keeps two `uses` lines. The service log goes where the job already collects its logs: the `runtime-log-<shard>` artifact for digest, the test-case and retained output folders for pipeline tests |
