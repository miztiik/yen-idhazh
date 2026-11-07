# Summary generator API

**Last Updated**: 2026-11-06

Which prepared inputs, summary results and listener controls does the independent
TypeScript generation API expose?

## Entry point and ownership

`services/summary-generator/src/start-api-server.ts` starts the Bun listener.
The standard `Request`/`Response` handler and shared native transport also run
under Node/tsx. Only the listener adapter calls Bun APIs.
The API generates a summary from supplied text. It does not fetch a URL,
shorten input, classify attitudes, sample the machine or write private reports.
The [independent caller](summary-generator-caller.md) owns those workflow tasks.
The published site does not call this development API.

The actual emitter selects `/services/summary-generator` from its own
`src/declare-event-source.ts`. Each call creates a request-local operation,
deriving a child from a valid incoming W3C carrier or starting a fresh root.
Its response carries that operation's `traceparent` and optional `tracestate`.
The [identity contract](../architecture/contracts/identity.md#native-api-support)
owns the shared envelope and producer semantics.

## Operations

Table A - Generator operations

| Id | Method | Path | Meaning |
| --- | --- | --- | --- |
| A1 | POST | `/api/2026-11-05/generate-summary` | Generate one independent structured summary. |
| A2 | GET | `/api/2026-11-05/get-summary-generator-health` | Return `{status: "ok", version: "2026-11-06"}` for process/configuration availability, not model readiness. |

Paths match exactly, without a trailing slash. Retired `/api/summarize`,
`/health` and `/api/diagnostics` paths return HTTP 404 with no alias or redirect.
A wrong method on a current path returns HTTP 405 and its `Allow` header.
Native model readiness remains the upstream server's own operation.

## Request and response

`input_text` is required and nonblank. An optional nonblank `system_prompt`
replaces the configured default completely. Whitespace is checked for
blankness but is not removed from either value sent to the model.
Omitting the override does not require the caller to copy the default.

Only those two fields are accepted. URL acquisition, model/destination
overrides, conversations, sessions and history are not API inputs.
Every request builds fresh system and user messages and makes one native
generation call. A running model or native prefix cache may be reused;
no previous answer or conversation is carried into the next request.

Success is `{success: true, data, prompt_sha256, prompt_source, usage}`.

Table B - Successful response

| Id | Field | Meaning |
| --- | --- | --- |
| B1 | `data.headline` | Nonempty summary headline. |
| B2 | `data.executive_summary` | Nonempty summary text. |
| B3 | `data.key_points` | Nonempty text entries; an empty array is allowed. |
| B4 | `prompt_sha256` | SHA-256 of the exact effective system prompt's UTF-8 bytes. |
| B5 | `prompt_source` | `default` or `override`. |
| B6 | `usage.prompt_tokens` | Actual nonnegative native input count, or `null` when absent. |
| B7 | `usage.completion_tokens` | Actual nonnegative native output count, or `null` when absent. |

Native usage fields take precedence over available native timing counts.
Missing counts never become zero. Summary data contains no classifications,
source audit, prompts, raw model reply, token measurements or machine readings.
Native completion, final-content and output validation fail rather than
accepting an incomplete answer or inventing a missing summary field.

The API payload version and changelog are declared in
`src/schemas/summary-result.schema.ts` as `2026-11-06`, separately from the
fixed HTTP date. The current response and private caller reader switch together;
older HTTP products are not compatibility modes.

## Refusals and transport

Failures return `{error: <safe message>, code: <safe code>}` with the same
request-local carrier. Raw exception text and native response bodies are not
error messages.

Table C - Failure codes

| Id | HTTP status | Code | Boundary |
| --- | --- | --- | --- |
| C1 | 400 | `INVALID_REQUEST` | Malformed JSON, blank text or unsupported input fields. |
| C2 | 413 | `REQUEST_TOO_LARGE` | Incoming JSON or the assembled native request exceeds its configured UTF-8 byte allowance. |
| C3 | 408 | `REQUEST_BODY_TIMEOUT` | Incoming body consumption exceeds its configured deadline. |
| C4 | 500 | `GENERATE_SUMMARY_FAILED` | Native transport, representation, decoding or summary validation fails. |
| C5 | 404 | `NOT_FOUND` | No current operation matches the path. |
| C6 | 405 | `METHOD_NOT_ALLOWED` | The current operation does not accept that method. |

The shared transport uses native `fetch` with redirects refused. Ambient proxy
destinations are refused before dispatch; source text goes only to the committed
native destination. It validates
the JSON representation, bounds response bytes, decodes UTF-8 strictly and
keeps the selected model's deadline through complete consumption and decoding.
Caller cancellation propagates to the native request. Refused or cancelled
bodies are cancelled without waiting indefinitely for cleanup.
HTTP submits the entire prepared text; a model/context refusal is a failure,
not a shortened-input retry.

## Committed settings

`config/summary-generator/api.json` is schema-validated before serving.
Paths name one file under `prompts/` in the selected config root; absolute
paths, URLs, backslashes and parent traversal are refused. Prompt files must
be valid UTF-8 and nonblank; their exact text is retained.

Table D - API defaults

| Id | Setting | Default and consequence |
| --- | --- | --- |
| D1 | `hostname`, `port` | Loopback `127.0.0.1`, port `9932`; the adapter and caller derive addresses from this one declaration. |
| D2 | `prompt_file` | `prompts/generate-summary.txt`; summary instructions only. |
| D3 | `max_request_bytes` | `1048576` bytes, one MiB; larger incoming JSON returns HTTP 413. |
| D4 | `max_native_request_bytes` | `1048576` bytes, one MiB; larger assembled native requests return HTTP 413 before dispatch. |
| D5 | `max_native_response_bytes` | `1048576` bytes, one MiB; larger native replies fail generation. |
| D6 | `body_read_timeout_ms` | `5000` milliseconds, five seconds; stalled incoming bodies return HTTP 408. |
| D7 | `logging.level` | `INFO`; higher severities suppress lower-level diagnostics. |
| D8 | `logging.max_event_bytes` | `4096` bytes, four KiB; bounds body-free diagnostic envelopes. |

The adapter's idle timeout is disabled because application/model deadlines
already own these waits. Its pre-handler body ceiling uses JavaScript's exact
integer byte capacity so the configured handler can return JSON refusals and
trace carriers instead of a framework-only empty response.

The selected model, deadline and destination still come from the existing
Python request-declaration exporter and committed `model_server.base_url`.
Environment values cannot select a different model or destination.
Native request JSON, sampling and template dictionaries remain open pass-through;
only application-owned messages and decoding controls are protected locally.
Native server flags, verbosity and metrics stay in the selected model file.

API diagnostics contain only operation identities, safe codes, elapsed time
and effective-prompt digests, never source bodies, prompts, raw replies or secrets.
The API writes no `pipeline-events.jsonl` or step summary.

## Offline verification

The declared checks and recorded-boundary commands are in
[the gate guide](../how-to/run-the-gates.md#independent-typescript-packages-and-services).
`summary-api.test.ts` exercises the actual handler with standard in-memory
requests and recorded native responses. It covers fresh calls, prompt identity,
long input, configured listener/logging changes, exact byte limits and one byte
over, cancellation, deadlines, safe failures and absent usage.
No test listener, model download or new inference is involved.

## Design rationale

Summary generation and full analysis ask different questions. Sharing native
request assembly, final-answer reading and bounded transport keeps their model
boundary consistent without making source acquisition, classifications or
reports part of HTTP. The native server may cache a prefix; independent requests
still contain only their own complete system and user turns.

## See also

- [summary-generator-caller.md](summary-generator-caller.md) - preparation, full analysis and private reports.
- [api-routing.md](api-routing.md) - fixed first-party route dates.
- [../architecture/summarize/model-boundary.md](../architecture/summarize/model-boundary.md) - model and content ownership.
- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) - producer identities and carriers.
