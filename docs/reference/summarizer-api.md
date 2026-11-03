# Summarizer API and private events

**Last Updated**: 2026-11-03

Which requests, results and private event records does the independent
TypeScript summarizer expose?

## Entry points

`services/summarizer/src/start-api-server.ts` starts the HTTP API.
`services/summarizer/src/execute-cli-pipeline.ts` runs one CLI request.
Both load the producer reference from the committed
`config/typescript-event-sources.json`, written by this repository.
That reference identifies the event producer; it is not a fetch destination.

The selected model and its destination still come from the existing Python
configuration loader. Environment values cannot replace the model or the
committed `model_server.base_url`.

The service installs `@idhazh/common-contracts` as a local dependency. This adds
the shared identifier and carrier libraries, plus their Zod 4 validation
dependency, to the service installation only. The service keeps Zod 3 for its
application validators. Its compiler resolves the shared TypeScript source
exports directly. No browser dependency, tracing provider or exporter is added.

## Commands and results

`POST /api/summarize` requires `system_prompt` and at least one of `url` or
`input_text`. When both source fields are present, direct text remains the
fallback for failed URL extraction. Optional `server_url` and `model_name`
must match the selected configuration; they do not choose another destination
or model.

Success remains `{ "success": true, "data": <complete structured summary> }`.
The summary retains its source audit, prompts, source text, raw model output,
classification, token readings and swap readings. Invalid request fields return
HTTP 400; execution failures return HTTP 500. `GET /health` and
`GET /api/diagnostics` retain their existing responses.

An optional valid `traceparent`/`tracestate` request carrier gives the HTTP
operation its enclosing context. The service derives a child; an absent or
invalid carrier starts a fresh execution. Response carrier headers identify
that request's pipeline operation. They do not change the response body or
create a retry or authorization guarantee.

The CLI starts a fresh execution and writes its complete result as JSON on
standard output. Diagnostics go to standard error and contain only identifiers,
event types, counts, codes or measurements.

## Private event records

Each request has its own event bus and history. `getEventHistory()` returns a
copy, including when concurrent requests share an incoming execution.
`pipeline-events.jsonl` remains the named private application output. Requests
append their events in occurrence order; a private job report receives only
its own request's history.

The event family version is `2026-11-03`; its stamp and changelog are exported
from `services/summarizer/src/schemas/pipeline-event.schema.ts`. Its envelope
uses the [shared event and operation contract](../architecture/contracts/identity.md#4-native-typescript-event-and-operation-metadata).
Event types are unchanged. `OUTPUT_STRUCTURED` stores the complete validated
summary directly under `data`.

Creation and saved-event reading pass the real service data validator to the
shared envelope helper. No Zod schema crosses major versions. The named-file
reader rejects a malformed envelope or application value and reports its line;
it never silently drops a record or allocates a replacement occurrence.
Readers accept only this current format, without aliases, migration or backfill.

Extraction callbacks carry their supplied context. A fetch retains one
operation through its callbacks; parsing links to that completed fetch.
Inference uses a nested operation, links to extracted input when available,
and retains its context through dispatch and completion. Carriers are not
injected into source fetches, and the model-server request protocol is unchanged.

The JSONL file and job report contain private domain data, including prompts
and model output. Console diagnostics do not dump these events. No separate
trace file is written.

## Recorded verification

The event and model-boundary cases use real entry points, application
validators and loopback transports. The named
`tests/fixtures/typescript-metadata/summarizer-model-response.json` contains
saved model text, token counts and timing readings from a successful run,
presented in the existing chat response envelope. It is not new inference.

The cases prove distinct occurrences in one operation, unchanged saved
application values, CLI result readback, concurrent HTTP history isolation,
failure behavior and the source-header boundary. They do not establish model
quality or live model availability.

## Design rationale

Private event data stays complete because result readers use the full summary.
Retaining that application output does not require placing source or model
content in diagnostic metadata or console logs.

## See also

- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) -
  shared identifiers and carrier semantics.
- [../architecture/summarize/model-boundary.md](../architecture/summarize/model-boundary.md) -
  the model request boundary.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md#independent-typescript-packages-and-services) -
  native preparation and check commands.
