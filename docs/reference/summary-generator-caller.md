# Summary generator callers

**Last Updated**: 2026-11-06

Which analysis and summary-only outputs does the independent private caller
retain outside the generation API?

## Two caller products

The private package is `summary-generator-tests` under
`.github/scripts/summary-generator-tests/`. Its manifest declares `check`,
`test`, `cli` and `summary` commands.

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

## Preparation and prompts

Both caller products acquire one operator-supplied URL or direct text outside
HTTP. A failed URL may use supplied direct text; a failed URL with no fallback
fails the invocation. The real extractor constructs an existing JSDOM instance
for Defuddle, with scripts and extra resources disabled, and closes its window
after success or failure. Fetch callbacks retain one operation; parsing links
to that completed fetch. Trace headers are not sent to the source.

Preparation preserves the original source audit and applies the configured word
cap before generation. The summary API itself has no hidden word cap.

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
| B1 | `max_input_words` | `6000` source words; retains the existing preparation cap and truncation marker. |
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
Its step summary is caller-owned. The saved event uses the shared metadata
envelope, with nested response validation against the API contract.
Its data version/changelog is `2026-11-06`, with current-only reading.
Input hashes and supplied prompt hashes are checked against their captured text;
the API response and caller carriers must belong to the same request trace.
Absent native usage stays `null`; actual zero counts remain zero counts.
No missing classification, score or machine reading is fabricated.

## Full-analysis saved events

The full-analysis CLI still writes its complete JSON result to stdout and its
named `pipeline-events.jsonl` privately. Each request has its own event bus and
history; reports receive that request's history only.
`OUTPUT_STRUCTURED.data` remains the complete validated analysis object.

Its event family remains `2026-11-03`, declared in
`contracts/pipeline-event.schema.ts`. Moving the producer does not restamp
the saved format or rewrite historical `/services/summarizer` occurrences.
The current-format reader retains their original source, UUID, UTC time,
carrier and data. Malformed envelopes or application values fail by line,
without silently dropping a record or allocating a replacement occurrence.

The full-analysis report retains classifications, source text, prompts, raw
model output and existing measurements. Native measurements keep their legacy
saved-value rules; the summary-only product has its own nullable usage contract.
Private captures are not published site data.

## Offline verification

`analysis-events.test.ts` and `analysis-runtime.test.ts` compose the real CLI,
orchestrator, validators, event writer/reader and report with named native
recordings. `extract-content.test.ts` uses the real readable-article fixture,
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

## See also

- [summary-generator-api.md](summary-generator-api.md) - the pure HTTP product.
- [workflow-pipeline-events.md](workflow-pipeline-events.md) - the older phased experiment's distinct saved payload.
- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) - shared metadata and independent producer identities.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md#independent-typescript-packages-and-services) - frozen native checks.
