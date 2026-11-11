# GLiNER controls and event reporting

**Last Updated**: 2026-11-10
**Level**: 5 - configuration and native request/result contracts.

## 0 - Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Configure native entity extraction, optionally return metadata, and report linked event candidates through the existing API and caller. |
| A2 | Hard scope - in | - One implementation PR for the existing API, caller and reports.<br>- The native controls and record template in Tables C and D.<br>- Existing saved-artifact compatibility and independent classification.<br>- A separate model assessment using existing tools, not another application feature. |
| A3 | Hard scope - out | Table B records the exclusions and their costs. |
| A4 | Chosen strategy | Wire existing SDK capabilities into existing code. Reuse its schema types, cutoff, output controls and natural records. Add only caller configuration/loading and a focused event renderer; no extraction framework or staged rollout. Andre owns extraction wording; Fowler owns native-contract compatibility. |
| A5 | ESCALATE triggers | 1. Resolve the Level-5 contract proposal before implementation, especially C3's native metadata behavior.<br>2. Surface any required SDK/model change, lost record capability, custom output transformation or expansion beyond Table B.<br>3. Native execution stays within the allowed Linux boundary in the gate guide. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A7 | Baseline | Named provider/caller files match default-branch commit `fda53b64133f8b9afbf2691f23028b600f12f211`. The pinned SDK is `gliner2==2.1.0`, source commit `b86d35c02f2c1a4d9840ea50197bd1b6d13b031e`. Recheck those files before execution. |

Table B - Scope boundaries

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Article clustering, duplicate decisions and published payloads | Event evidence does not yet influence article grouping or publication. | A separate grouping contract and labelled article-pair evaluation. |
| B2 | Model replacement, dependency upgrades and benchmark tooling | No general quality, speed or memory improvement is promised. | The separate model assessment and a specific model/runtime decision; use existing preparation and reporting first. |
| B3 | Another model stage, coreference, normalized dates and event-status inference | Participants, relative dates and negated or planned actions can remain uncertain. | A demonstrated failure and a separately priced capability. |
| B4 | Custom metadata stripping, unique-name API output and cross-type overlap removal | Native aggregate scores and repeated or differently typed mentions remain visible. | An explicit selection/projection contract that prices its information loss. |
| B5 | New endpoints, services, workflow inputs and local provider execution | Configuration remains committed; real inference evidence requires the existing allowed Linux path. | A concrete unmet operator requirement or the canonical execution process, not a bypass. |

Table C - Contracts used by the implementation

| Id | Surface | Required behavior |
| --- | --- | --- |
| C1 | Provider settings | Add `entity_confidence_threshold: 0.8`, a strict finite number in inclusive `[0, 1]`, and `overlap_policy: disallow`. Apply the cutoff through native entity configuration only, not the shared extraction threshold or a cleanup pass. Explicit per-label thresholds override the default, including zero; absent/null thresholds use the default. `flat` aliases the chosen overlap policy; `allow` is its opposite. The currently published base configuration already uses `flat`. Native overlap selection is per type, not cross-type exclusivity. |
| C2 | API output controls | Add independent strict request booleans `include_confidence` and `include_spans`, both default false, and pass them to the existing `extract_long` call. Keep the route and `result` envelope. Accept the SDK's text-only, score-only, span-only and rich leaf representations across existing task families, retaining scalar/list/null forms and entity attributes. Long-operation relations remain head/tail objects, not short-operation tuple arrays. |
| C3 | Native record correction | Validate record-level `confidence` separately from requested fields and preserve it. Native long extraction can retain this aggregate score, and boundary relation scores, even when leaf confidence is disabled; do not promise that the flag removes every score. Validate present aggregate scores as finite values in the confidence range. Reject record-field names `confidence`, `label` and `text` before inference because native formatting can overwrite/drop them; leave ordinary structures unaffected. Permit successful omission of requested record-mode roots when the pinned decoder emits no records, without inserting empty arrays. Other required roots and unknown-key checks remain strict. Refuse record requests when the loaded model lacks that capability. |
| C4 | Caller configuration | Add `config/text-analysis/caller.json`, declared and loaded by `CallerAnalysisSettings` in `tools/text-analysis-caller/load_caller_settings.py`. Reuse native `SchemaInput` for its `schema`, plus dated `version`/`changelog` and C2's controls. This caller accepts entities and the optional `events` structure from Table D; classification stays separate. Entity descriptions reference exactly the existing presentation-label offering, preserving order; no fallback or second source-tag mapping. The committed reporting configuration explicitly requests detailed evidence. Removing that structure, and omitting the empty structures section, restores entity-only extraction; no second enable flag is needed. |
| C5 | Person wording | Put this in `schema.entities.person.description`: `Names of specific individual people. Exclude generic groups, occupations, standalone job titles, pronouns, organizations and publications.` Also describe named organizations, explicitly including publications, and named geographic places. Store descriptions in C4's configuration. These guide the model; they are not correctness guarantees or restrictions on generic event participants. |
| C6 | Saved evidence and reporting | Keep historical entity-only/classification artifacts readable. Explicit output flags select a strict profile; flagless native artifacts can be historical-rich or current-compact, recognized by complete leaf shape before validation, never exception fallback. Preserve repeated text when offsets are absent; never reconstruct positions or scores. Keep offset-based source/duplicate/exclusivity checks when offsets exist. Render metadata only when present and aggregate scores separately. Add candidate rows with Table D's roles, intact native bindings/order and unique table/row IDs. Preserve independent classification and identical standalone/combined GLiNER sections. Distinguish not requested, successful empty/omitted records, failure and malformed evidence. Replay remains standard-library-only and uses saved data, not current configuration. |
| C7 | Versioning | Separate settings-shape versioning from the unchanged route date in the existing settings loader. Read the exact old settings shape with its former native defaults before writing the new dated shape; reject unknown versions and malformed current files. Update affected analysis metadata/changelogs and direct settings readers together. Add no wire-version field or migration framework, and never rewrite saved evidence. |

Table D - Native event template

| Id | Field | Native declaration | Description |
| --- | --- | --- | --- |
| D1 | `action` | `dtype: str`, `cardinality: required_one` | The verbatim action or event trigger for this candidate. |
| D2 | `actors` | `dtype: list`, `cardinality: zero_or_more` | Participants performing the action, not those affected. |
| D3 | `objects` | `dtype: list`, `cardinality: zero_or_more` | Participants or things affected by the action. |
| D4 | `times` | `dtype: list`, `cardinality: zero_or_more` | Time expressions belonging to this event, not unrelated dates or publication metadata. |
| D5 | `places` | `dtype: list`, `cardinality: zero_or_more` | Locations belonging to this event, not unrelated places or datelines. |

The template uses native `mode: natural`, anchored on D1, with `exclusive: false` for each field. It supplies linked candidates, not independently extracted lists or verified completed events. Store these declarations in C4's configuration.

## 1 - Status Reckoner

Table E - Delivery

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Wire native controls and event reporting | - | A | DONE | vigilant-fortnight | - | GLiNER controls and events |
| E2 | 2 | Check model alternatives with existing tools | 1 | B | DONE | solid-tribble | - | GLiNER model suitability |

## 2 - One implementation PR

### Row #1 - Wire native controls and event reporting

- **Scope:** Deliver Tables C and D together in one PR, updating readers and contracts before their writers within the same change.
- **Files touched:**
  - `.github/workflows/ci.yml`
  - `config/text-analysis/gliner/settings.json`
  - `config/text-analysis/caller.json` (new)
  - `services/text_analysis/gliner/src/gliner_api/declare_api_contracts.py`
  - `services/text_analysis/gliner/src/gliner_api/declare_analysis_contracts.py`
  - `services/text_analysis/gliner/src/gliner_api/load_settings.py`
  - `services/text_analysis/gliner/src/gliner_api/load_model.py`
  - `services/text_analysis/gliner/src/gliner_api/analyze_text.py`
  - `services/text_analysis/gliner/src/gliner_api/create_api_component.py`
  - `services/text_analysis/gliner/src/gliner_api/validate_analysis_results.py`
  - `services/text_analysis/gliner/tests/test_api.py`
  - `tools/text-analysis-caller/load_caller_settings.py` (new)
  - `tools/text-analysis-caller/collect_results.py`
  - `tools/text-analysis-caller/collect_classifications.py`
  - `tools/text-analysis-caller/run_analysis.py`
  - `tools/text-analysis-caller/capture_events.py`
  - `tools/text-analysis-caller/project_gliner_analysis.py`
  - `tools/text-analysis-caller/render_entities.py`
  - `tools/text-analysis-caller/render_classifications.py`
  - `tools/text-analysis-caller/render_configuration.py`
  - `tools/text-analysis-caller/render_gliner_events.py` (new)
  - `tools/text-analysis-caller/render_report.py`
  - `tools/text-analysis-caller/test_reports.py`
  - `docs/reference/gliner-api.md`
  - `docs/architecture/text-analysis/gliner-api.md`
  - `docs/how-to/run-ner-api-tests.md`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261110-gliner-controls-and-events-plan.md`
- **Acceptance gates:**
  - Local: the existing `python tools/text-analysis-caller/test_reports.py`, documented caller-only Ruff/mypy checks with `--follow-imports=skip`, and `npm --prefix frontend run test:changed -- --list`. No local provider install, import, lint, type-check or startup.
  - Controlled Linux: wire the existing model-free provider tests and configured lint/type checks into the existing CI workflow using the frozen provider environment, without model weights or inference in that check. Extend the existing contract tests with real SDK schema construction and minimal in-memory payloads. Cover native threshold preparation, strict settings/flags, C2's representations, C3's correction, role-binding preservation, historical replay and metadata absence. Reuse current tests; no new suite, internal mocks or edge-case fixture files.
  - Required CI: candidate checks pass. Keep transport, lifecycle, diagnostics, spaCy behavior and independent classification intact.
  - Native observation: use the existing Linux reporting path on the exact candidate after applicable checks pass, reusing a matching run if available. Require a nonempty native event result from multi-action text; inspect source slices and field/record metadata, then regenerate the saved report without inference. This observation is not an accuracy benchmark or substitute for tests.
  - Review one representative operator report with Susan before merging. Missing roles must remain empty, metadata must remain optional, source markup must be escaped, and no sentence indexes may be invented.
  - Update the owning guides in the same PR, keeping the provider generic and caller definitions in one documented place. If native evidence cannot be obtained, name the missing evidence rather than claiming end-to-end success.
- **Oracle:** The existing caller produces one combined entity/event extraction response plus its independent classification response, and saved replay preserves native values, event associations and outcomes with or without leaf metadata; this does not prove event accuracy or improved article deduplication.

Table F - Implementation decisions

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | Use native schema configuration and SDK controls, not another cleaner, prompt layer, endpoint or inference pass. | Andre; Fowler. |
| F2 | Keep all application changes atomic in one PR. Compatibility stays in the existing readers/loaders; no staged migration or separate refactoring PR is needed. | Simplest complete delivery; C6-C7. |
| F3 | Add the event structure to the existing extraction request; keep classification separate and persist explicit output flags in both requests. Saved requests already retain the configured schema, so no additional caller-config artifact is needed. | Fowler; existing caller/artifact contract. |
| F4 | Fix metadata and empty-result validation generically for supported record modes, not only the configured structure name. Keep small shared validation helpers in the existing modules; do not introduce a validation framework. | Fowler; pinned native decoder behavior. |
| F5 | Run provider checks on the existing CI Linux runner and keep the existing manual native reporting observation separate. Reuse the locked project and current tooling rather than introducing another execution service or running the provider on the developer host. | Canonical execution boundary; existing CI and reporting paths. |

Table G - Rejected implementation alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Separate rollout PRs and helper layers for every control | The same existing API/caller/reporting path can change together. | More intermediate compatibility states, handoffs and review overhead without another user capability. | KISS; atomic delivery. |
| G2 | Post-filter entities, strip native aggregate scores or zip independent event-role lists | It duplicates SDK behavior, changes evidence or loses event associations. | New selection/projection/binding contracts and their correctness tests. | Andre; Fowler. |

## 3 - Separate model check

### Row #2 - Check model alternatives with existing tools

- **Scope:** Establish whether an alternative preserves the required tasks and improves the supplied example, without replacing the configured model or building evaluation tooling.
- **Files touched:**
  - `config/text-analysis/gliner/settings.json` (comparison revisions only; final selection unchanged)
  - `docs/reference/gliner-api.md`
  - `TODO/20261110-gliner-controls-and-events-plan.md`
- **Acceptance gates:**
  - Check native record capability before downloading or running an alternative; an incompatible model is not a complete replacement even if its person extraction looks better.
  - For eligible candidates, use the same complete source from evidence run `42873000881`, ordered labels/descriptions, native thresholds, SDK, long-text settings and detailed output. Use existing preparation/reporting on allowed Linux; no new harness or workflow.
  - Run any measurement alone and identify actual hardware/revisions. Retain the current final model selection and keep article bodies/weights out of committed documentation. Report missing evidence plainly; one article cannot establish general quality.
- **Oracle:** Each eligibility or example-output conclusion is backed by the relevant native configuration or a matched existing-path observation; the result cannot establish a universally best checkpoint.

Table H - Model decisions

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | This check does not block the implementation PR and does not authorize a model replacement. Reuse source evidence or matching runs before doing more work. | Separate model/runtime decision; measurement discipline. |
| H2 | Treat the public demo as a comparison lead, not proof of equal settings, source coverage or record capability. | Andre. |

Table I - Rejected model alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Replace the model from a clean-looking demo result | Its processing and complete-task compatibility are not established by that output. | A matched native comparison and a model-selection decision. | Andre. |
| I2 | Build a benchmark framework for this PR | Existing configuration and reporting can answer the immediate example question. | Additional contracts, maintained tooling and labelled evaluation data for broader claims. | YAGNI. |

## See also

- [Plan authoring](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Native API contract](../docs/reference/gliner-api.md)
- [Native API architecture](../docs/architecture/text-analysis/gliner-api.md)
- [Shared reporting procedure](../docs/how-to/run-ner-api-tests.md)
- [Saved-report replay and caller checks](../docs/how-to/run-spacy-tests.md)
- [Gate ownership](../docs/how-to/run-the-gates.md)
