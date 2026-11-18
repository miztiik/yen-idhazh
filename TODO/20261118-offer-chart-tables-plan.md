# Offer the model tables of figures instead of an element menu

**Last Updated**: 2026-11-18
**Level**: 5 - the chart question the model is asked, and the meaning of one persisted reason.

## 0. Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | No chart has published on any day checked since 2026-09-14, and no article the model was asked about in the four complete runs after the one-call change got one. The model has to pair names with figures itself and answer with a long plan made of element ids. After this plan, code lists small tables of name-and-figure rows copied from the article; the model decides whether a chart is worth drawing, which form, which row the story turns on, and the title |
| A2 | Hard scope - in | A builder of name-and-figure tables from an article's text and elements, with no model in it (row 1). The one model call shows those tables and answers `why`, `type`, `focus`, `title` and `caption`; code builds the existing plan from the answer, so the validator, the replacement ladder and the compiler run unchanged (row 2). Everything only the id menu served is deleted (row 3). One model call, no new knob. Two contracts move and nothing else: the meaning of `not_reachable` (E5, persisted) and `VisualPlan.confidence` becoming optional (E3, not persisted) |
| A3 | Hard scope - out | Table B |
| A4 | New and deleted files | New: `backend/idhazh/classify/pair_names_with_figures.py` and `backend/tests/test_pair_names_with_figures.py`, both in row 1. No file is deleted whole. Rows 2 and 3 remove more lines than they add; each pull request states its diffstat |
| A5 | ESCALATE triggers | 1. Row 1 finds fewer than 4 tables worth a chart across the saved articles (an estimate: below it, supply and not the prompt is the limit): stop and report; row 2 waits for the user's answer. 2. A contract change beyond E3 and E5, a second model call, a different model or a larger window. 3. Article text reaching anything but the committed model server, or a table cell outside the fence. 4. After row 2, the first three scheduled runs together ask 20 or more articles about a chart and none reaches the validator as a typed plan |
| A6 | Chosen strategy | Code supplies figures the model can check; the model makes the choice (Andre) |
| A7 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 4; the rows form one chain, so one is ready at a time |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table B - Out of scope and its cost

| ID | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Offering line, slope, scatter, bubble, pie, stacked bar and histogram; the validator and compiler keep supporting them | Stories of those shapes draw nothing. Pie and stacked bar need a stated whole code cannot find, line and slope need date-and-figure tables, scatter and bubble need each figure's subject; none has published since 2026-09-14 either | One more table shape added to the builder, once row 1's check shows name-and-figure tables yield real charts |
| B2 | Shortening the summary half of the system turn | About 165 tokens (an estimate) stay in a turn the server reads once a shard; the summary is the product, so a cut needs its own before-and-after comparison | A summary comparison on the same articles |

## 1. Status Reckoner

Table C - Status Reckoner

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Build name-and-figure tables from an article | - | A | PENDING | - | - | - |
| C2 | 2 | Let the model choose among the tables | 1 | B | PENDING | - | - | - |
| C3 | 3 | Delete what only the id menu served | 2 | C | PENDING | - | - | - |

## 2. Row #1 - Build name-and-figure tables from an article

- **Scope:** A function with no model in it turns one article's text and element table into tables of name-and-figure rows. Nothing calls it yet.
- **Files touched:** New: `backend/idhazh/classify/pair_names_with_figures.py`, `backend/tests/test_pair_names_with_figures.py`. Nothing else: it reads the table, the text and `visuals` as they are.
- **Acceptance gates:** Local: the new test file; ruff and mypy over `backend/`. CI: the complete suite.
- **Oracle:** In memory, with no model and no network. One table of four rows: the wind page (four countries, four figures in MW, across three sentences). No table: a repeated name that hides a pair (`Germany is in Europe. Denmark said Germany built 1,200 MW.`), two names then two figures (`Denmark and Germany approved 1,200 and 900 MW.`), a name with a line break or `|`, a name longer than `visuals.max_label_characters`, figures with no unit, two units in one run, a run under the floor or one row over the ceiling, a run in which a name repeats, `visuals.enabled_kinds` empty, and `visuals.enabled_types` holding neither bar nor dot. Then once, in a scratch script that is not committed: rebuild each chart-asking article of digest runs 44259308561, 44232477603 and 44223473759 from its saved prompt (the `captures-*` artifacts, retained to 2027-02-16; a prompt holds the article and its element rows), build the tables, and list every table in the pull request beside its sentences. The worker marks each table twice: pairing right or wrong (read off the sentence), and worth a chart or not (at least `visuals.min_chart_points` figures of one kind compared across names); the user may overrule any mark. Wrong pairings must be zero; one found is fixed by tightening the rule, and the check is run again. It cannot settle that the model picks well from the tables, or pairing in a sentence whose figure belongs to a referent the service did not label ("it", "the firm"); the count worth a chart decides trigger 1.
- **Decisions:**

Table D - Row #1 decisions

| ID | Decision |
| --- | --- |
| D1 | Pairing, one sentence at a time. A sentence is clean when its names and figures alternate - name, figure, name, figure - in equal numbers, and each name takes the figure right after it; any other sentence pairs nothing. Names are every occurrence of an entity or place element's words in the text, matched on whole words, because a repeat is not an element and the table alone would hide it. Figures are quantity elements that do not sit inside a name. A wrong pair is worse than a missed one, so there is no distance limit and no figure-before-name reading: each would be a new rule, added only if the check shows real tables lost without it |
| D2 | A table is a maximal run of consecutive sentences that are each clean, hold at least one pair, and whose figures all share one unit that is not null (a byline or a page number has none). A sentence outside those conditions ends the run. A run is kept only when its names are all different and its row count is at least `visuals.min_chart_points` and at most the smaller of `visuals.max_chart_points` and the plan's limit on ids in one channel; over the ceiling the run is refused whole, never trimmed (Andre) |
| D3 | Every table is offered as the enabled types among bar and dot: the two forms whose marks are one name and one figure and that need no stated whole. Both mean purpose `comparison`. A test pins each to the validator's role table. The offer is therefore one line for the request, and no table carries its own forms. None enabled means no table |
| D4 | A cell is offered only when it is one line, holds no `|`, is unchanged by `sanitize`, and, for a name, is no longer than `visuals.max_label_characters`: the compiler refuses or cuts anything else, and a line break or `|` would let a name forge a row. A row carries its name element (the first occurrence) and its figure element so code can build a plan later; the model is shown only the row code, the name's words and the figure's words. Row codes r1, r2, ... run across all tables in article order |

## 3. Row #2 - Let the model choose among the tables

- **Scope:** The one model call shows the tables after the article and the model answers `why`, `type`, `focus`, `title` and `caption`; code builds the existing plan from the answer, and the validator, replacement ladder and compiler run unchanged.
- **Files touched:** (from a search for the names being replaced; re-run at dispatch)
  - Code: `backend/idhazh/classify/plan_visual_request.py`, `backend/idhazh/classify/calls.py`, `backend/idhazh/classify/dag.py`, `backend/idhazh/stages/summarize_one_item.py`, `backend/idhazh/visual_planner.py` (docstrings and the gate's rationale), `backend/idhazh/contracts/visual.py`, `backend/idhazh/contracts/visual_decision.py`, `backend/idhazh/measured.py` (descriptions), `backend/utilities/prove_the_entry.py`, `config/prompts/plan-visual.txt`, `config/prompts/continue-summary.txt`
  - Fixtures, edited and none added: `tests/fixtures/completions/summarize-and-plan/cut-in-the-plan.json`, `tests/fixtures/completions/summarize-and-plan/summary-and-plan.json`, `tests/fixtures/completions/summarize-and-plan/wind-summary-and-plan.json`
  - Tests: `backend/tests/test_classify.py`, `backend/tests/test_chart_vocabulary.py`, `backend/tests/test_prompt_files.py`, `backend/tests/test_summarize.py`, `backend/tests/test_visual_planner.py`, `backend/tests/test_visual_attempts.py`, `backend/tests/test_fingerprint.py`, `backend/tests/test_spans.py`, `backend/tests/test_replay_article_calls.py`, `backend/tests/contracts/test_decoder_grammar.py`, `backend/tests/contracts/test_visual_plan.py`, `backend/tests/contracts/test_app_config.py`, `backend/tests/support/prompts.py`, `backend/tests/pipeline/_builders.py`, `backend/tests/pipeline/test_published_charts.py`, `backend/tests/pipeline/test_work_records.py`, `backend/tests/pipeline/test_work_analysis.py`, `backend/tests/pipeline/test_degrade.py`, `backend/tests/pipeline/test_census_prefers_the_record.py`, `backend/tests/pipeline/test_work_health_payload.py`
  - Docs: `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/throughput.md`, `docs/architecture/summarize/model-boundary.md`, `docs/architecture/extraction/elements.md`, `docs/architecture/sources/trust-boundary.md`, `docs/architecture/publishing/visuals.md`, `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`, `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`, `docs/architecture/publishing/where-every-drawn-figure-came-from.md`, `docs/reference/retained-article-verification.md`
- **Acceptance gates:** Local: the shared selector over the changed tests and the pipeline test directory; `-m contract`; ruff and mypy over `backend/`. CI: the complete suite, browser job included.
- **Oracle:** The real work stage against a loopback model the test owns, on the wind page: the one request holds the four rows (`r1 | Denmark | 1200 MW` to `r4 | Ireland | 410 MW`) and no element id; a recorded reply of bar with focus `r1` publishes a chart whose marks cite exactly those rows' elements, with Denmark emphasised; a `none` with stray fields publishes the summary and no chart and carries its `why` as the rationale; a chart answer with no focus, one with a digit in its title and one with an empty title each publish the summary and no chart and name the rule; a place name written as an instruction sits in the request only between fence markers (it also appears in the article block); the run's prompt stamp moves when the table wording moves. It cannot settle that a real model picks sensibly or that summaries read the same; OBS-1 reads both.
- **Observation OBS-1** (the first three scheduled runs after this row, read together): from item-health rows, the items with `run_visual_decision` true (asked); from the visual-attempt ledger (`state/raw/visual-design-attempts/`), the attempts with a `planned_type` (a typed plan reached the validator) and those in state `rendered`. Baseline: the same readings for the four complete runs after the one-call change (Actions runs 44212498730, 44223473759, 44232477603, 44259308561). 20 or more asked with none typed stops the plan (trigger 4). Summaries: the summary-evaluation columns of `docs/concepts/summary-metrics.md` for those runs beside the prior seven days; revert this row when a reading falls outside the prior seven days' range. No tolerance is named because day-to-day noise can exceed a small effect.
- **Decisions:**

Table E - Row #2 decisions

| ID | Decision |
| --- | --- |
| E1 | Reply: `visual` holds `why`, `type`, `focus`, `title`, `caption` after `summary`, which still decodes first so a cut reply keeps it. Every key is present and null when unused. `type` is `none` or an offered form; `focus` is an offered row code or null; the three prose fields keep the plan's own length bounds. `none` is final: nothing else is read, no plan is built, and `why` is the rationale. `why` comes first because with thinking off it is the model's only room to reason (a guess OBS-1 tests). With no table offered the call asks for the summary alone, as today (Andre) |
| E2 | Request: the tables follow the article in one fenced block, one line per row (`r1 | Denmark | 1200 MW`), then one line written by code naming the forms on offer. The system turn keeps one short block of chart rules, identical for every article so the cached start of the prompt never changes; the numeric chart guide goes. The rules say: write the reason in words with no digits; choose a chart only when the item is about how the figures in one table compare across names; choose none for separate facts, passing mentions, and figures that measure different things for different names; check the table against the item and not the summary; never write a figure that is not in the table; the title is short, factual and has no digits; one worked chart answer and one worked none answer (Andre) |
| E3 | Plan: code builds a complete `VisualPlan` from a chart answer: decision `visual`, purpose `comparison`, the chosen form, category = the table's name elements and quantity = its figure elements in row order, every other channel empty, no declared whole, no labels, annotations = the focus row's figure (the compiler needs exactly one emphasised mark and code never guesses it), the element ids those cite, the model's title and caption, and the vocabulary stamp. `VisualPlan.confidence` becomes optional, with a changelog line: nothing reads it and the model no longer writes it. The plan is not persisted, so nothing migrates |
| E4 | A chart answer is refused by a named rule, so `failed_field` and `failed_rule` say which, when it has no `focus`, when its title is empty after `sanitize`, or when `why`, `title` or `caption` holds a digit: the validator's numeral check only proves a numeral appears among the cited figures, not that it belongs to the row it names. The item publishes with its summary and no chart |
| E5 | A table built means the plan is asked for; none built means it is left off, recorded as `not_reachable`. That value now means no table was on offer; before this change it meant no choice over the elements could have validated. The enum's comment, the `VisualDecision` changelog and the docs say so; no field, value or column is added or removed, and rows written before keep the old meaning |
| E6 | The window check bounds the offered tables from what the builder can emit (one token a character: a token spans at least one character) and not from the old per-row rate, and the contract test keeps the longest article the cap allows inside the window. The run's prompt stamp renders the user turn with one fixed example table, so a change to the table wording moves it; it still counts `visuals.enabled_kinds` and the selected types |

## 4. Row #3 - Delete what only the id menu served

- **Scope:** Starts after OBS-1 has been read and does not call for a revert, because these deletions are what would make a revert of row #2 expensive. Remove the id menu, the reply shape that cited ids, the numeric chart guide, the old gate and everything else a search shows only they served; keep the validator, the ladder, the compiler and `VisualPlan`.
- **Files touched:** (from a search for the names being deleted; re-run at dispatch)
  - Code: `backend/idhazh/classify/plan_visual_request.py`, `backend/idhazh/classify/calls.py`, `backend/idhazh/visual_planner.py`, `backend/idhazh/contracts/visual.py`, `backend/idhazh/measured.py`, `backend/utilities/measure_budgets.py`
  - Tests: `backend/tests/test_classify.py`, `backend/tests/test_chart_vocabulary.py`, `backend/tests/test_prompt_files.py`, `backend/tests/test_visual_planner.py`, `backend/tests/test_measure_budgets.py`, `backend/tests/contracts/test_visual_plan.py`, `backend/tests/contracts/test_decoder_grammar.py`
  - Docs: `docs/architecture/publishing/visuals.md`; `docs/reference/benchmarks/two-call-re-read.md`, `docs/reference/benchmarks/instructions-in-front.md` and `docs/reference/benchmarks/two-call-window-sizing.md` (pointers only); `TODO/20261110-restore-visual-publication-plan.md` (its pending row names files already deleted, and the menu)
- **Acceptance gates:** Local: the shared selector over the changed tests; `-m contract`; ruff and mypy over `backend/`. CI: the complete suite.
- **Oracle:** A search of `backend/`, `config/`, `docs/`, `frontend/src`, `tests/`, `tools/` and `.github/` for each deleted name finds only history (changelogs, dated benchmark pages), and the validator, ladder and compiler test modules pass with no change to their assertions. It cannot settle that no reader outside the repository uses a deleted name; `docs/architecture/contracts/ledger-registry.md` lists the readers of persisted data.
- **Decisions:**

Table F - Row #3 decisions

| ID | Decision |
| --- | --- |
| F1 | Keep `VisualPlan`, the validator, the replacement ladder, the compiler and the vocabulary tables: the drawn figure's trust rests on them and only the model's route to them moved |
| F2 | Delete a name only when a search after row #2 finds no reader. Expected: the id menu and its columns, the id-citing reply shape with its reader of older replies, the numeric chart guide, the old gate (`reachable_types`, `plan_is_reachable`) with its tests, the worst-case-reply arithmetic with its measured record, and the per-row menu rate |
| F3 | Sections that present the id menu or the old gate as current design are deleted, not archived; dated benchmark pages keep their history and gain a pointer; the other chart plan's pending row is corrected to the new design |
