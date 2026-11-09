# Summary generator callers

**Last Updated**: 2026-11-09

Which analysis and summary-only outputs does the independent private caller
retain outside the generation API?

## Two caller products

The private package is `summary-generator-tests` under
`tools/summary-generator-caller/`. Its manifest declares `check`,
`test`, `cli` and `summary` commands.

All caller contracts stay under `tools/summary-generator-caller/contracts/`.
The orchestrator imports request/result schemas directly; reporting imports
result/event types directly; measurement collection imports its telemetry type
directly. There is no export-only schema module. The private package's local
dependency is `file:../../packages/common-contracts`; its package identity,
command names and locked dependency versions are unchanged.

Table A - Entry points and products

| Id | Entry point | Product |
| --- | --- | --- |
| A1 | `run.ts`, through `bun run cli` | Full analysis: source audit, summary, sentiment/stance classifications, raw output, prompts, native timing/token and existing swap measurements. |
| A2 | `run-summary-api.ts`, through `bun run summary` | The validated summary-only API response, preparation audit, prompt/input digests and actual API/caller carriers; classification and machine readings are explicitly `not_collected`. |
| A3 | `wait-summary-api.ts <owned-pid>` | Configuration-health readiness for the owned generator, using the declared listener and workflow wait settings; no model-readiness claim. |

Both products select `/workflows/summary-generator-tests` from their own
`declare-event-source.ts`. The API's `/services/summary-generator` is a different
producer. Neither identity is a fetch destination or a source-registry entry.
The older `ai-pipeline.ts` experiment keeps its separate `analytic_synthesis`
product and [saved handoff](workflow-pipeline-events.md).
Both `ai-pipeline-tests.yml` and `yen-ai-pipeline.yml` remain distinct workflows.
After confirmed generator exit, their [private native scoring phase](pipeline-summary-evaluation.md)
evaluates saved summary text without changing either caller product or the API.

## Preparation and prompts

Both caller products acquire one operator-supplied URL or direct text outside
HTTP. A supplied URL takes precedence; omit it to use direct text without fetching.
A failed URL may use supplied direct text; a failed URL with no fallback fails
the invocation. The real extractor constructs an existing JSDOM instance
for Defuddle, with scripts and extra resources disabled, and closes its window
after success or failure. Fetch callbacks retain one operation; parsing links
to that completed fetch. Trace headers are not sent to the source.

Preparation preserves the original source audit and applies the configured word
cap to extracted, direct or fallback text before generation, not to raw HTML.
Byte and model-context limits remain independent. The summary API itself has
no hidden word cap.

Full analysis reads `prompts/request-json.txt` as its default base and
`prompts/analyze-article.txt` as its instruction suffix. The existing `PROMPT`
environment override replaces only the base; composition keeps the exact
two-newline separator and existing classifications.
Its raw result extends the API's pure summary fields once, without duplicating
those declarations.

The summary-only caller sends only prepared `input_text` and an optional complete
`SYSTEM_PROMPT`. A blank workflow input omits the override; the API resolves its
configured default. A supplied nonblank override is passed exactly, without
appending analysis instructions or a second model call.

## Settings and capture

`config/summary-generator/workflow.json` owns caller controls independently of
listener settings. `CONFIG_ROOT` selects the named committed config root; model
and destination still come from the Python request-declaration exporter.
Environment `MODEL_NAME` and `SERVER_URL` do not replace them.

Table B - Caller controls

| Id | Setting | Default and meaning |
| --- | --- | --- |
| B1 | `max_input_words` | `20000` source words, increased from `6000`; retains the original source audit and existing truncation marker. |
| B2 | `base_prompt_file`, `analysis_prompt_file` | `prompts/request-json.txt`, `prompts/analyze-article.txt`; full-analysis composition only. |
| B3 | `max_native_request_bytes`, `max_native_response_bytes` | One MiB each; full analysis uses the shared native transport, and the summary-only caller bounds its API request/result. |
| B4 | `body_read_timeout_ms` | Five seconds for summary API response/health-body consumption. |
| B5 | `heartbeat_ms` | Ten seconds between the full-analysis caller's existing waiting diagnostics. |
| B6 | `extraction_timeout_ms` | Fifteen seconds for the source fetch. |
| B7 | `min_html_bytes`, `min_content_characters` | `100` HTML bytes and `50` extracted characters; refuse insubstantial extraction before choosing a fallback. |
| B8 | `api_startup_timeout_ms`, `api_poll_interval_ms` | Thirty seconds overall and one-second polling for configuration health. |
| B9 | `output_directory` | `backend/var/summary-generator-tests`, relative to the repository; private summary-only capture and report output. |
| B10 | `logging.level`, `logging.max_event_bytes` | `INFO` and four KiB; body-free caller diagnostics. |

The summary-only caller writes named `summary-response.json`,
`summary-events.jsonl` and `summary-report.md` files with temp-file-plus-rename.
Its body-free failure diagnostic distinguishes transport timeouts from API failures.
Its step summary is caller-owned. The saved event uses the shared metadata
envelope, with nested response validation against the API contract.
Its data version/changelog is `2026-11-07`. The reader also accepts
`2026-11-06` captures without changing their version, identity or original
contents; their omitted `result.model` remains unknown.
Input hashes and supplied prompt hashes are checked against their captured text;
the API response and caller carriers must belong to the same request trace.
Absent native usage stays `null`; actual zero counts remain zero counts.
No missing classification, score or machine reading is fabricated.

The report separates configured `model_name` from the API's server-reported
`result.model`. A missing reported name is labelled as not reported, never
replaced with the configured name. The [API contract](summary-generator-api.md#request-and-response)
owns the reported name's meaning and validation.

## Full-analysis saved events

The full-analysis CLI still writes its complete JSON result to stdout and its
named `pipeline-events.jsonl` privately. Each request has its own event bus and
history; reports receive that request's history only.
`OUTPUT_STRUCTURED.data` remains the complete validated analysis object.

The full-analysis result and event contracts are `2026-11-07`, declared in
`contracts/analysis-result.schema.ts` and `contracts/pipeline-event.schema.ts`.
Their shared metrics contract writes that date at `token_metrics.version` in
results and structured-output events, and `tokenMetrics.version` in completed
inference events. New writes require that stamp and the complete current shape.
Readers also accept unversioned numeric metrics from the earlier format, retaining
the original source, UUID, UTC time, carrier and data, including historical
`/services/summarizer` occurrences. They never restamp or rewrite a recording,
infer missing data from a historical zero, or use legacy reading to accept an
invalid current or unsupported version. Malformed values fail by line.

The full-analysis report retains classifications, source text, prompts, raw
model output and existing measurements. Missing native counts use the corresponding
timing count when available, then `null`; a reported zero takes precedence over
that fallback. An independently reported total survives missing component counts;
otherwise a total requires both counts. Missing stage times and token rates stay
`null`. A reported rate survives missing counts or times; deriving a rate requires
an available count and positive native stage time. The measured whole-request
duration remains available but never replaces native completion time.
Reports and notices display null measurements as `Not reported`, and actual
zeroes numerically. Legacy reports show values as recorded with a warning that
zeroes may mean unavailable data and stage times may include historical
whole-request substitutions. Private captures are not published site data.

## Offline verification

Caller cases live under `tools/summary-generator-caller/test/`, including
`prepare-api-input.test.ts` for the shared source-word ceiling and independent
transport byte limits. Native API cases remain under
`services/summary-generator/test/`.

`analysis-events.test.ts` and `analysis-runtime.test.ts` compose the real CLI,
orchestrator, validators, event writer/reader and report with named native
recordings. `token-metrics.test.ts` checks in-memory missing, zero and partial
measurements, strict current writes, lossless historical reads and report labels.
`extract-content.test.ts` uses the real readable-article fixture,
one recorded main-document request and actual JSDOM parsing/closure.
`summary-workflow.test.ts` runs the actual summary caller against the real
recorded-boundary API handler and reads back its response, event and report.
These cases open no test listener and do not claim live source/model availability
or summary quality.

## Design rationale

Preparation and reporting belong to the caller because their inputs and outputs
are not the summary HTTP product. Keeping one extractor and one native
transport preserves source fallback, input shortening and full-analysis
measurements without making every summary request pay for them.
The explicit JSDOM peer fixes the parser's native-instance contract; extraction
dependencies install only with the private caller, not the API or site.

One nested metrics version identifies the same changed shape in results and
both metrics-bearing events without duplicating application-version fields.
Legacy readers preserve recorded values because an old zero cannot establish
whether the native server reported it. A future change outside metrics needs
its own applicable version rather than borrowing this stamp.

## See also

- [summary-generator-api.md](summary-generator-api.md) - the pure HTTP product.
- [workflow-pipeline-events.md](workflow-pipeline-events.md) - the older phased experiment's distinct saved payload.
- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) - shared metadata and independent producer identities.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md#independent-typescript-packages-and-services) - frozen native checks.
