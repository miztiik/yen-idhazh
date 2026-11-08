# GLiNER2 API plan

**Last Updated**: 2026-11-08
**Level**: 5 - new native API and model-configuration contracts.

## 0 - Operating contract

**Table A - Intent and boundaries**

| Id | Field | Value |
| --- | --- | --- |
| A1 | Intent | Add independent local NER and text-classification operations through GLiNER2, alongside spaCy on one existing FastAPI listener and machine. |
| A2 | Status | Execution in progress. The two PRs below are dependent; implementation and merge status are tracked in Table F. |
| A3 | API location | `services/text_analysis/gliner/`, with the import package `gliner_api`. No new files directly under `services/text_analysis/`. |
| A4 | Model configuration | `config/text-analysis/gliner/settings.json` declares dated schema metadata, enablement, `model.repo` and `model.base_url`. The repository is a full model identifier; the base URL is the configured Hub download endpoint. Compatible weights change at the next fresh API start through this file, never through source code, an HTTP selector or environment destination override. |
| A5 | Runtime | Use local `gliner2.AutoExtractor`, not the original NER-only `gliner` runtime or a hosted inference client. Keep one loaded model and native CPU threading. Do not add worker replicas, a one-thread cap or process-global CPU tuning. No checkpoint is fixed in this plan or code. |
| A6 | Hosting authority | Reuse `config/text-analysis/settings.json` through the existing spaCy settings loader. Its listener and shutdown bounds already supply the FastAPI transport settings. Do not create another host/port configuration, model server, hosting distribution or test-settings file. |
| A7 | Hard scope - in | - Native NER and classification JSON contracts.<br>- Config-selected local weights, real readiness and stderr CloudEvents.<br>- One neutral assembly of independent provider applications.<br>- Current taxonomy definitions as classification input data.<br>- Minimal API functionality checks only. |
| A8 | Hard scope - out | Table B prices the exclusions; it does not remove the shared future classification/discovery requirement. |
| A9 | ESCALATE triggers | 1. If a new contract/runtime decision falls outside Tables A-E.<br>2. If the coordinated spaCy factory, native routes or listener authority change: refresh this plan, not that provider's implementation.<br>3. If the configured checkpoint cannot perform a promised task or load safely from the configured endpoint: surface the capability issue, never substitute another checkpoint or silently clip input.<br>4. If the independent dependency sets cannot share the job environment: price compatible releases before introducing another deployment.<br>5. If completing the API requires a new taxonomy, uncertainty policy or pipeline operation. |
| A10 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 because the PRs depend on the same API/hosting boundary; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

**Table B - Exclusions**

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | spaCy feature changes, file moves and route renaming | This change depends on its stable public hosting interface. | The separate spaCy plan; this plan only consumes that interface. |
| B2 | A private topic dictionary or fixed classification enum | Label selection must receive current authoritative definitions. | No duplicate is needed; extend the existing taxonomy instead. |
| B3 | Unlisted-label promotion and an entropy threshold | The API supplies extraction/classification results, not a new proposal or assignment policy. | Shared work in the existing article-classification plan. |
| B4 | News ingestion, ranking, publishing, pipeline tests and benchmarks | No end-to-end news or throughput claim is made. | A separate requested integration or decision-changing measurement. |
| B5 | Hot reload, model SHA/revision pins and test mode controls | Model changes apply on a fresh start; mutable upstream weights can change behavior. | A changed model-selection/lifecycle requirement. Ordinary dependency locks remain. |

**Table C - API contracts**

| Id | Boundary | Declaration |
| --- | --- | --- |
| C1 | Version | Use a declared UTC date-of-creation stamp in `/api/<date-style-version>/`. The initial proposal is `2026-11-08`; update it before first release if creation occurs on a later UTC day. It is not recalculated per request, model change or test run. |
| C2 | Operations | Under C1: `POST run-ner-gliner`, `POST classify-text-gliner`, `GET get-gliner-health`, `GET get-gliner-schema`. Health/schema are ordinary native operations, not another server. |
| C3 | NER request/result | Request: nonblank, exact UTF-8 `text` and a nonempty unique ordered `labels` list of entity-type strings. Result: only `entities`, with `text`, `label`, `start_char`, `end_char`, `score`. Source offsets are zero-based, half-open Python Unicode code-point indexes; slicing must reproduce the mention. Scores must be finite and in the native confidence range. Empty predictions are valid, not an error fallback. |
| C4 | Classification request/result | Request: exact `text` and named `tasks`; each task supplies `labels` as an ID-to-definition mapping and `multi_label` as a boolean. Use the native SDK schema, not prompt construction or a private classifier. Return `classifications`, mapping each task to a list of selected `{id, score}` entries; single-label tasks have at most one entry. Every returned ID must belong to that request's label set. This is model inference, not automatic assignment of published article fields. |
| C5 | Validation/errors | Declare strict Pydantic request, result, health, event and settings models before handlers. Reject unsupported selectors, invalid input and malformed native output with fixed JSON `error` containing `code`, `message`, `retryable`; never dump source input, exception text or model internals. Reuse existing body/host/origin guards and status conventions. |
| C6 | Health | HTTP 200 requires an actually loaded model and available promised operations. Other states return 503 with safe status/error data. Creating a pool, finding a package or seeing a cached filename is not readiness. |
| C7 | Diagnostics | Reuse CloudEvents 1.0 and W3C trace transport. GLiNER owns its source/type/data vocabulary; emit only validated stderr records. Keep text, mentions, labels/definitions, URLs, headers, PIDs, paths and raw exceptions out of diagnostics. No operational metadata is added to C3/C4 bodies. |
| C8 | Input size/chunks | Reuse the existing bounded request reader and native model input checks; do not add the arbitrary label count/character caps from the earlier draft. Native long-text helpers use overlapping word chunks and document offsets; their defaults are not minimum article lengths or global input limits. Do not mirror those defaults into new configuration without a demonstrated need. Detect unsupported input rather than silently truncate it. |
| C9 | Optional prediction tuning | Add only a native prediction setting actually needed by the implementation, in A4 and its native validator. Do not copy every SDK default. Span/confidence inclusion required by the response contract is an output-shape control, not a switch that may break the contract. |

**Table D - Shared label ownership**

| Id | Subject | Responsibility |
| --- | --- | --- |
| D1 | Authoritative vocabulary | `config/taxonomy.json` is the evolving source. Callers build C4 input from the current configured entries and definitions, preserving order; the API carries no second vocabulary or code-level membership list. |
| D2 | Hierarchy | Feed `vertical` remains source identity/provenance. Assigned `desk` uses the same configured vertical vocabulary but has a different purpose. Lenses are cross-cutting themes; events describe what happened. Their multiplicity and ranking effects belong to the classification/ranking contract, not this API. |
| D3 | Lifecycle | Only active entries are offered for new assignment. Draft entries are not assignment targets. Retired entries remain readable historically but are excluded from new choices. Adding or retiring a label changes configuration data, not this API/schema/test code. |
| D4 | Entities and terms | `config/watchlist.json` is a separate entity registry. NER may extract an unwatched name or topic phrase; that value is evidence, not an automatically active taxonomy ID. The spaCy plan owns grouped entities and Important Terms. |
| D5 | Existing classification | The current local encoder assignment remains intact. This API does not replace it or change ingestion, article identity, rank or publication. The future classification caller may use the native capability through the shared contract. |
| D6 | Future work | Refer to `TODO/20260910-23-article-classification-plan.md` by the titles "Call 1 labels: desk, lenses, article kind", "Confidence is a masked probability over the label's whole span", and "A vertical is proposed into a channel and promoted by a person". Do not create a competing proposal payload, ledger or entropy measure. Low entropy needs a specified probability distribution and does not alone establish novelty/correctness. |

**Table E - Stable hosting surface**

| Id | Surface | Contract |
| --- | --- | --- |
| E1 | spaCy factory | `text_analysis.create_api_component.create_app(settings: ServiceSettings) -> FastAPI`, under `services/text_analysis/spacy/src/text_analysis/create_api_component.py`. Its plan preserves the public factory; do not perform its move here. |
| E2 | Existing settings | `text_analysis.load_service_settings.load_service_settings(root)` returns the native service settings. Reuse its listener host, port, body bounds, read deadline and shutdown deadline. This reads transport configuration, not another provider's model state. |
| E3 | Composition | Preserve the complete native application surfaces: component hooks/refusals, host settings/events, service identity, `app.router.lifespan_context`, host-added health/schema routes and each native OpenAPI builder. The component router alone is not the complete API. |
| E4 | Neutral assembly | One shared FastAPI application/listener; separate provider routers, models and results. Keep request guards and one receiving trace operation. Use typed public bindings and native framework composition; do not rewrite paths, inspect worker internals or merge model state. |
| E5 | Environment | Keep provider manifests independent. Prepare compatible locked dependencies in the existing job's environment with native package-manager commands; check compatibility. Do not add GLiNER logic/model dependencies to spaCy merely to assemble the server. |
| E6 | Delivery prerequisite | The spaCy relocation is on its planning session's branch, not yet available on the implementation base. Row 2 waits until that layout and the stable E1 interface are delivered on its base. Do not repeat the relocation or write against the old root layout. |

## 1 - Status Reckoner (PR execution status)

**Table F - PR order**

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 1 | Delivering the native GLiNER2 API | - | A | DONE | musical-waddle | - | GLiNER2 API delivery |
| F2 | 2 | Integrating the independent APIs on the existing listener | 1 | B | PENDING | - | - | - |

## 2 - Row #1 - Delivering the native GLiNER2 API

- **Scope:** Deliver real config-selected local NER/classification handlers, strict native contracts, readiness and stderr diagnostics.
- **Files touched:**
  - `services/text_analysis/gliner/pyproject.toml`
  - `services/text_analysis/gliner/uv.lock`
  - `services/text_analysis/gliner/src/gliner_api/__init__.py`
  - `services/text_analysis/gliner/src/gliner_api/declare_api_contracts.py`
  - `services/text_analysis/gliner/src/gliner_api/load_settings.py`
  - `services/text_analysis/gliner/src/gliner_api/load_model.py`
  - `services/text_analysis/gliner/src/gliner_api/create_api_component.py`
  - `services/text_analysis/gliner/src/gliner_api/extract_entities.py`
  - `services/text_analysis/gliner/src/gliner_api/classify_text.py`
  - `services/text_analysis/gliner/src/gliner_api/emit_events.py`
  - `services/text_analysis/gliner/scripts/prepare_model.py`
  - `services/text_analysis/gliner/tests/test_api.py`
  - `config/text-analysis/gliner/settings.json`
  - `.github/workflows/ner-tests.yml`
  - `docs/architecture/text-analysis/gliner-api.md`
  - `docs/reference/gliner-api.md`
  - `docs/reference/api-routing.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates - local:** Verify the named lock without installing models; inspect the existing changed-test selection. Follow the text-analysis no-local-provider-execution rule.
- **Acceptance gates - CI:** Prepare the configured model outside tests; applicable package lint/type checks; one focused API test file through `uv run --project services/text_analysis/gliner --frozen --extra model --group dev pytest services/text_analysis/gliner/tests/test_api.py`. Test configuration/request/result boundaries with minimal in-memory inputs, and real prepared-model ASGI request/response behavior without network access or model mocks. No news-pipeline, quality, benchmark, model-swap or profile matrix.
- **Oracle (decisive check):** Real native NER/classification requests return only valid labels, source spans and confidence data, with readiness tied to the prepared model; configuration is passed to the native loader rather than selected by code. This cannot establish prediction accuracy or universal checkpoint compatibility.

**Table G - Implementation decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Load compatible assets through the configured Hub SDK endpoint and native local factory. Model identity is required configuration data; no code default, revision/SHA pin or model-name list. Never send article text to a hosted client. | Model/configuration responsibility |
| G2 | Use one cached model with native CPU threading and standard framework offloading. Reuse existing host/body/trace infrastructure; do not build a worker framework, repair loop or parameter registry. | Architecture responsibility |
| G3 | Delegate schema-based classification, label descriptions and long-text processing to the local SDK. Normalize output once at the API boundary; unsupported capabilities/input and invalid output fail explicitly. | Native API responsibility |
| G4 | Keep model-library noise out of stderr through supported library controls; only the validated event writer emits diagnostics. Keep operational state out of response bodies. | Process/privacy responsibility |
| G5 | Dependencies benefit the native inference/API feature: local SDK and CPU tensor runtime, existing FastAPI/Pydantic/host, and verification-only HTTPX/pytest. Model/runtime assets dominate installation and memory cost; use compatible frozen dependencies and CPU wheels, not GPU packages by default. | Dependency responsibility |

**Table H - Rejected alternatives**

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Original NER-only runtime for both operations | Does not provide the selected classification capability. | A separate classifier/runtime integration. | Capability contract |
| H2 | Private taxonomy or source-bound checkpoint | Breaks evolving label/model configuration. | Coupled vocabulary/model releases and duplicated ownership. | Configuration responsibility |
| H3 | Fake inference, multiple checkpoints or a bespoke test-mode configuration | Adds complexity without the requested API functionality check. | A separately requested evaluation or lifecycle test with a named purpose. | Verification scope |

## 3 - Row #2 - Integrating the independent APIs on the existing listener

- **Scope:** Assemble the complete native provider applications in the existing API-functional workflow without another listener/configuration or changes to spaCy's model/feature implementation.
- **Files touched:**
  - `services/local_api_host/src/local_api_host/compose_api.py`
  - `services/local_api_host/src/local_api_host/compose_applications.py`
  - `services/text_analysis/hosting/serve_apis.py`
  - `services/text_analysis/gliner/tests/test_api.py`
  - `.github/workflows/ner-tests.yml`
  - `docs/architecture/local-api-host.md`
  - `docs/architecture/text-analysis/gliner-api.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-ner-api-tests.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates - local:** E6 must be satisfied before dispatch; refresh E1-E3 against that implementation base. No local model execution.
- **Acceptance gates - CI:** Reuse existing host regression checks and the focused API file. The existing `spacy_ner_test` job prepares both providers on one machine and verifies actual API requests/readiness/diagnostics through the shared application. Preserve spaCy's own required checks. Do not add workflow-file-content tests, a second startup/reconfiguration journey, additional model downloads for comparison, or a pipeline test.
- **Oracle:** Both native APIs retain their routes, schemas, lifecycle and guarded request behavior in one application; neither provider gains the other's model state or response fields. This does not prove faster elapsed time or news-pipeline integration.

**Table I - Integration decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | The neutral helper consumes public application/hosting surfaces, not private provider code. The thin assembly file alone imports both factories and E2; neither provider imports the other. No separate hosting distribution. | Coordinated hosting responsibility |
| I2 | Reuse the existing listener and native API route constants. Preserve every host-added health/schema operation, OpenAPI customization and lifecycle; detect collisions and cleanup failures explicitly. | Transport/process responsibility |
| I3 | Test API input, result, readiness and failure behavior only. Prepare assets before the test and use real inference; reuse existing guard/trace checks. No `server_module`, `apis`, `swap_probe_repo`, test-settings file or pipeline-level harness. | Verification scope |
| I4 | Native definitions are built from the authoritative configured vocabularies for classification requests; current entries are not copied into code or assertions. Keep D2-D6 assignment/discovery responsibilities outside these API handlers. | Shared classification responsibility |

**Table J - Rejected integration alternatives**

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Another host/port file, model server or inference machine | Duplicates the existing hosting authority. | Another deployment/configuration/lifecycle to maintain. | Hosting intent |
| J2 | Add GLiNER state or topic rules to spaCy | Couples independently evolving providers. | Shared model/feature releases and changed spaCy behavior. | Provider independence |
| J3 | Private proposal payload or entropy filter | Duplicates shared unfinished classification work. | Resolve the existing proposal/uncertainty contract first. | Shared classification responsibility |

## See also

- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Gate commands](../docs/how-to/run-the-gates.md)
- [API routing](../docs/reference/api-routing.md)
- [Neutral host](../docs/architecture/local-api-host.md)
- [Taxonomy](../docs/concepts/taxonomy.md)
- [Current classification](../docs/concepts/classification.md)
- [Article-classification plan](20260910-23-article-classification-plan.md)
- [Repository layout](../docs/reference/repository-layout.md)
