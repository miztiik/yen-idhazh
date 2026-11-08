# Improve spaCy text analysis

**Last Updated**: 2026-11-08 UTC
**Level**: 5 - public payloads, configuration and HTTP compatibility.

## 0. Operating contract

**Table A**

| Id | Field | Value |
| --- | --- | --- |
| A1 | Goal | Return grouped Named Entities and ranked Important Terms for English articles, with exact source occurrences and explicit feature failures. |
| A2 | In scope | Correct Unicode evidence validation; implement the core outputs; rename the dated spaCy routes; update their actual readers and configuration. Existing raw features, Chinese defaults, model profiles and runtime behavior remain intact. |
| A3 | Strategy | Reuse the existing spaCy document, native feature-result envelope and feature-local error handling. YAKE supplies phrase ranking; no additional model, result wrapper or recovery system. |
| A4 | Hosting boundary | Preserve `text_analysis.create_api_component.create_app(settings: ServiceSettings) -> FastAPI` and its component/router/lifespan/OpenAPI surfaces. The neutral assembler owns one listener for the independent routers, reusing `text_analysis.load_service_settings.load_service_settings(root).listener` from the existing configuration. Do not implement another assembler or host configuration here. |
| A5 | Escalate | Stop if the work requires a new model, classifier, taxonomy/proposal contract, listener, hosting-settings file, host rewrite or change to Chinese behavior. |
| A6 | Execution | Execute per `docs/how-to/execute-a-plan.md`; parallel N = 1 because the rows share the probe, workflow and API documentation. Delegate rows to nested isolated workers and merge only after their required CI passes. |

**Table B - Work kept elsewhere**

| Id | Outside this plan | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Taxonomy assignment and new-label discovery | This spaCy API does not produce semantic topic assignments or label proposals. The existing classification flow continues to own them. | A defined shared classification result consumed here, not another classifier or vocabulary. |
| B2 | GLiNER model selection and neutral cohosting | This plan does not deliver the other API or its assembly. | A specific interface change coordinated with that work. |
| B3 | New presentation, semantic events and benchmarks | No new dashboard, resolved quote/event output or model-quality claim. | A separately specified consumer or capability requirement. |

Classification authority remains `config/taxonomy.json` and
[classification.md](../docs/concepts/classification.md) /
[taxonomy.md](../docs/concepts/taxonomy.md). Its entries evolve; do not create a
private dictionary or code enum. The unfinished classification/proposal work
remains in [the article-classification plan](20260910-23-article-classification-plan.md),
including "Call 1 labels: desk, lenses, article kind", "Confidence is a masked
probability over the label's whole span" and "A vertical is proposed into a
channel and promoted by a person". No entropy measure or threshold is added here.

## 1. Status reckoner

**Table C**

| Id | # | Outcome | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Correct Unicode evidence validation | - | A | DONE | jubilant-waffle | - | Unicode evidence reader |
| C2 | 2 | Deliver the compact English spaCy API | 1 | B | PENDING | - | - | - |

## 2. Evidence reader

### Row #1 - Correct Unicode evidence validation

- **Scope:** Make the real probe validate Python code-point offsets correctly, including text after non-BMP characters.
- **Files touched:**
  - `services/text_analysis/spacy/scripts/probe-text-analysis.ts`
  - `services/text_analysis/spacy/scripts/validate-evidence-spans.ts` (new)
  - `services/text_analysis/spacy/scripts/validate-evidence-spans.test.ts` (new)
  - `.github/workflows/ner-tests.yml`
  - `docs/how-to/run-spacy-tests.md`
- **Acceptance gates:** Locally run only the named model-free Bun test and whitespace check. Run that same test in the existing spaCy workflow; keep application/model execution in its registered CI gate.
- **Oracle:** The actual helper used by the probe accepts correct original-source spans after a non-BMP character and rejects incorrect spans. This proves offset handling, not recognition quality.

**Table D - Implementation decisions**

| Id | Decision | Reason |
| --- | --- | --- |
| D1 | Convert the source to code points once per response and reuse it for span checks. | JavaScript string indexes are UTF-16 units; Python offsets are code points. |
| D2 | Extract only the span check needed by the actual caller. | Test real validation without importing or starting the whole probe. |

## 3. Core API

### Row #2 - Deliver the compact English spaCy API

- **Scope:** Implement the grouped entity and phrase outputs, language-specific defaults, configured limits and implementation-specific routes as one coherent public API change.
- **Files touched:**
  - `services/text_analysis/spacy/src/text_analysis/declare_api_contracts.py`
  - `services/text_analysis/spacy/src/text_analysis/declare_service_settings.py`
  - `services/text_analysis/spacy/src/text_analysis/load_service_settings.py`
  - `services/text_analysis/spacy/src/text_analysis/create_api_component.py`
  - `services/text_analysis/spacy/src/text_analysis/extract_features.py`
  - `services/text_analysis/spacy/src/text_analysis/run_analysis.py`
  - `services/text_analysis/spacy/src/text_analysis/manage_models.py`
  - `services/text_analysis/spacy/src/text_analysis/group_named_entities.py` (new)
  - `services/text_analysis/spacy/src/text_analysis/rank_important_terms.py` (new)
  - `services/text_analysis/spacy/pyproject.toml`
  - `services/text_analysis/spacy/uv.lock`
  - `config/text-analysis/settings.json`
  - `services/text_analysis/spacy/scripts/probe-text-analysis.ts`
  - `services/text_analysis/spacy/tests/test_named_entities.py` (new)
  - `services/text_analysis/spacy/tests/test_important_terms.py` (new)
  - `services/text_analysis/spacy/tests/test_api_contracts.py` (new)
  - `services/text_analysis/spacy/tests/test_spacy_verification.py`
  - `.github/workflows/ner-tests.yml`
  - `docs/reference/text-analysis-api.md`
  - `docs/reference/api-routing.md`
  - `docs/architecture/text-analysis/text-analysis-api.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** Locally inspect the shared test selection, check whitespace and verify the updated frozen lock without installing the service. In the existing workflow run named offline unittest files, then the real API probe. Require an English `md` run and an unchanged-behavior Chinese `md` run against the same immutable candidate. CI owns the full suite.
- **Oracle:** Real feature execution returns unique entity groups and ranked phrases with exact source spans, respects the configured term maximum, and preserves completed siblings when one feature fails. This proves software behavior, not model or phrase-ranking accuracy.

### Contract and implementation order

1. Declare the new native payloads and settings before extraction logic; extend the real TypeScript reader in step with them. Keep `AnalysisResult`, `FeatureResult`, `EvidenceSpan` and the existing raw feature contracts.
2. Add `named_entities` with `data.entities`: entries have `text`, `type` and nonempty `occurrences` of `EvidenceSpan`. Group by configured name normalization and mapped type; preserve the first source spelling and every occurrence. Order groups and occurrences by source position. This is document-local grouping, not entity identity resolution.
3. Add `important_terms` with `data.terms`: entries have `text`, finite nonnegative `score` and nonempty `occurrences` of `EvidenceSpan`. Use YAKE's ascending score order, then first source position for ties. Match candidates back to the original spaCy document using `PhraseMatcher`; deduplicate matching phrases before the final limit. No candidates, or a configured zero limit, is a completed empty result. A selected candidate without valid source evidence fails that feature with `FEATURE_FAILED`; never invent offsets or replace failure with an empty success.
4. Dispatch the real implementations from the existing extractor. Pass validated settings into extraction rather than retaining them in the model cache. Extend capability checks so both new features are English-only and missing NER/sentence capabilities use the existing feature error.
5. Add optional `languages.en.default_features`, selecting the two new outputs in order. An omitted language override inherits the existing global defaults, so Chinese selection remains unchanged. Health exposes resolved `default_features` per language and `important_terms_limit` for supported English output; unsupported/legacy limits remain unknown, not invented values.
6. Switch the native handlers, health, schema, probe and docs to the routes in Table E together. Preserve the existing application factory, `app.state.component`, host/event state, lifespan, trace guards and native OpenAPI customization for neutral assembly.

**Table E - Fixed HTTP family**

| Id | Method | Path |
| --- | --- | --- |
| E1 | POST | `/api/2026-11-08/run-ner-spacy` |
| E2 | GET | `/api/2026-11-08/get-spacy-health` |
| E3 | GET | `/api/2026-11-08/get-spacy-schema` |

The HTTP date is a protocol constant, not the request date. Retire the former
analysis, health and schema paths with 404, without aliases or redirects.
Wrong-method behavior remains unchanged. HTTP, payload and settings schema
versions remain separate identities.

### Configuration and compatibility

- `named_entities.ignore_case` defaults to `true`. `named_entities.label_map` defaults to `PERSON -> person`, `ORG -> organization`, and `GPE/LOC -> location`. These are NER presentation types, not another classification taxonomy. Unmapped mentions remain available through the existing raw `entities` feature.
- `important_terms` supplies YAKE settings: `max_results = 25`, `max_phrase_words = 3`, `deduplication_threshold = 0.9`, `deduplication_method = seqm`, `window_size = 1`, and library English stopwords. The result maximum follows the reference's term control, not a quality target; the other defaults follow the ranker. Declare and validate them in settings rather than passing hidden literals. Reject invalid types/ranges; zero results intentionally suppresses only the term list.
- Use the existing `allowed_features`, supported-feature lists and per-language defaults rather than new enable switches. Keep all existing raw features selectable. Do not change input text, body bounds, spaCy/model versions, listener settings, capacity or process ownership.
- Advance each changed native schema with its date/changelog. Read previous settings with the declared new-option defaults and unchanged previous feature selection. Historical health without the added per-language fields uses its recorded global defaults; historical limits stay absent/unknown. Existing native request/result/event payloads remain readable and are not rewritten.

YAKE is the only new extraction dependency: it supplies article phrase ranking,
adds Python installation dependencies, and adds no model download or published
JavaScript. Update the manifest and frozen lock together.

### Failure behavior and checks

Reuse `FEATURE_UNAVAILABLE` and `FEATURE_FAILED`. Completed siblings survive;
the current partial/all-failed and request/process policies remain intact. No
replacement model, retry chain, silent empty fallback or new recovery state.

Use standard unittest with minimal in-memory documents/configuration and real
feature code. Cover repeated names, source mapping, ranking/limits, empty output,
legacy reads, English defaults and unchanged Chinese behavior. Keep the current
artifact contract; add no disk fixtures or network tests. Extend the live probe's
existing happy path rather than creating another pipeline or browser matrix.
Do not restore retired workflow-declaration tests or their reading harness;
verify actual programs and API boundaries instead.
