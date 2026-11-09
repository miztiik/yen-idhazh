# Refine text-analysis reports

**Last Updated**: 2026-11-09

**Level**: 3 - caller reports and workflow artifact delivery; native APIs stay unchanged.

## 0 - Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Make native analysis results explainable and independently downloadable, then add concurrent GLiNER article classification. |
| A2 | Hard scope - in | Native source display; provider configuration and result tables; independent provider artifacts; caller-concurrent NER/classification in the dependent outcome. |
| A3 | Hard scope - out | Table B records the exclusions and their costs. |
| A4 | ESCALATE triggers | 1. Native API, model, runtime or persisted-contract changes. 2. Source rewriting or a new inference call outside the assigned outcome. 3. A changed operator-controlled destination or trust boundary. |
| A5 | Chosen strategy | Reuse native contracts and saved native files; pure report projections change presentation, not inference evidence. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md; parallel N = 1 because both outcomes share the caller/report surface; the coordinator registers and lands the dependent stack. |

Table B - Scope exclusions

| Id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Provider source, settings and model changes | Existing provider behavior and serialized model access remain unchanged. | A separate design task naming the required native behavior. |
| B2 | Synthetic live checks and inference retries | The report does not establish recognition quality or throughput. | A separately specified evaluation with its own inputs and decision. |
| B3 | Classification in the first outcome | The first report explicitly says classification was not requested. | Complete the dependent classification outcome. |

## 1 - Status Reckoner

Table C - Outcomes

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Explain provider results and deliver separate artifacts | - | A | DONE (implemented) | bookish-fortnight | - | - |
| C2 | 2 | Collect and report GLiNER article classification | 1 | B | DONE (implemented) | concurrent-gliner-classification | - | - |

## 2 - Row #1 Explain provider results and deliver separate artifacts

- **Scope:** Present unchanged source, provider configuration, count-sorted entity tables and native term rankings, and deliver complete independent provider reports with replayable native evidence.
- **Files touched:**
  - `.github/workflows/ci.yml`
  - `.github/workflows/ner-tests.yml`
  - `tools/text-analysis-caller/collect_results.py`
  - `tools/text-analysis-caller/run_analysis.py`
  - `tools/text-analysis-caller/render_report.py`
  - `tools/text-analysis-caller/render_tables.py`
  - `tools/text-analysis-caller/render_entities.py`
  - `tools/text-analysis-caller/render_configuration.py`
  - `tools/text-analysis-caller/render_features.py`
  - `tools/text-analysis-caller/write_reports.py`
  - `tools/text-analysis-caller/test_reports.py`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/how-to/run-ner-api-tests.md`
  - `docs/reference/github-actions.md`
  - `TODO/20261109-refine-text-analysis-reports-plan.md`
- **Acceptance gates:** Local: all 15 pure in-memory assertions pass; caller-only ruff and strict import-skipping mypy pass; the shared selector lists full ordinary CI coverage. Native sanitized HTML wraps long words and retains displayed spacing/line breaks; saved requests retain exact CR/LF. Recorded native results regenerate without provider imports. Susan: SHIPS, no material presentation issues. Ordinary CI also runs the pure report assertions; its full suite remains a landing prerequisite.
- **Oracle:** For fixed native inputs, combined and standalone provider sections are identical, every group/occurrence/score is preserved, configured types remain visible, and only the entity display order changes. This cannot establish model quality, Linux model readiness or concurrent inference.

Table D - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| D1 | Use native inline code and escaped character references for soft wrapping; never insert source wrap newlines or rely on inline CSS. | Native Markdown rendering contract |
| D2 | Retain spaCy's existing groups and case rule; group GLiNER mentions only by exact text and requested label. Sort groups by count descending, earliest position, then original order. | Native evidence and report presentation contracts |
| D3 | Render every configured/requested type separately, including empty, not-requested and failed states. Keep optional raw spaCy features. | Report presentation contract |
| D4 | Keep term response order, rank and native YAKE scores; explain score direction and show existing settings without adding caps. | Native term contract |
| D5 | Save exact validated provider settings beside native requests/responses. Reuse identical provider sections for combined and standalone reports. | Native settings and report delivery contracts |
| D6 | Capture the UTC artifact date once near job start; upload each provider independently, including available files after failure. | Workflow delivery contract |

Table E - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Rewrite source lines or inject CSS | Changes source presentation semantics or depends on stripped styling. | A changed source-display contract and another native rendering investigation. | Native Markdown rendering contract |
| E2 | Merge aliases, relabel entities or aggregate confidence | Invents evidence not returned by the providers. | A separately declared inference or normalization feature. | Native evidence contract |
| E3 | Upload only one combined report | Couples provider delivery and leaves oversized summaries without independent complete reports. | Independent provider packaging would still need to be added. | Workflow delivery contract |

## 3 - Row #2 Collect and report GLiNER article classification

- **Scope:** Make caller-concurrent NER and classification requests through the existing routes for the same source and loaded model, using active taxonomy desk as single-label and lenses/events as multi-label tasks, and retain native classification artifacts and a classification report.
- **Files touched:**
  - `tools/text-analysis-caller/collect_results.py`
  - `tools/text-analysis-caller/run_analysis.py`
  - `tools/text-analysis-caller/render_report.py`
  - `tools/text-analysis-caller/render_configuration.py`
  - `tools/text-analysis-caller/write_reports.py`
  - `tools/text-analysis-caller/test_reports.py`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/how-to/run-ner-api-tests.md`
  - `docs/reference/github-actions.md`
  - `TODO/20261109-refine-text-analysis-reports-plan.md`
- **Acceptance gates:** Run bounded caller checks and pure classification/report assertions, including active-taxonomy selection and actual overlapping caller requests. Keep native provider access unchanged. Observe the existing manual Linux workflow if native execution evidence is needed; no synthetic live-check suite. Required CI owns the full suite.
- **Oracle:** Saved native requests select the same unchanged source, preserve active taxonomy definitions and task cardinalities, and the report reproduces every returned classification ID and native score; caller requests overlap without requiring concurrent model execution. This cannot establish classification quality or a throughput improvement.

Table F - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | Use existing NER and classification routes and the already-loaded model; concurrency belongs to the caller, not provider internals. | Native operation and process boundaries |
| F2 | Offer current active taxonomy definitions only, with desk single-label and lenses/events multi-label. | Taxonomy and native classification contracts |
| F3 | Keep classification request/response files native and reuse the first outcome's independent GLiNER artifact/report delivery. | Native evidence and report delivery contracts |

Table G - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Add another model, route or provider concurrency mechanism | Caller concurrency does not require changing serialized native model access. | A separate runtime design and model-resource decision. | Native process boundary |
| G2 | Duplicate taxonomy labels in caller configuration | A copied vocabulary can drift from active publication targets. | A new ownership and synchronization contract. | Taxonomy contract |
