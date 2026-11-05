# Planner run diagnostics

**Last Updated**: 2026-11-04

What evidence remains when a planner run fails?
The existing response and report retain safe execution context. A separate
private JSONL file, with one JSON object per line, retains recognized article
names. Neither output is a committed ledger or a new error history.

## Safe execution context

[`PlannerFailureSchema`](../../../packages/common-contracts/src/schemas/planner-failure.schema.ts)
declares the shared failure projection. It records the operation, runtime
error category, an allowlisted cause, an optional operating system code,
the original project-relative source file and line, and run, attempt and
code-revision identity. Known execution and operation identifiers are
`execution.traceId` and `execution.spanId`. An unavailable identifier is null;
a known execution does not imply a known receiving operation.
A later reader or cleanup wrapper preserves those identifiers, including
unknown values. Its own operation is not the failed operation.

The boundary captures the first available project frame from the original
exception. Library-only or unavailable locations remain null. Consumers do
not infer a filename from an error category. Exception messages, raw stacks,
article text, request headers, credentials, signed addresses and absolute
paths are not copied into this projection.

The same value travels through stage refusals, the public planner result,
structured failed events and the downloaded Markdown report. The first
failure remains primary when cancellation, health recording, result writing
or listener cleanup also fails. Related causes are bounded; `omitted_causes`
states how many could not be retained.

`diagnostics.failure` in `config/feed-ingest-plan-service.json` controls the
capture cost. Defaults read at most 16,384 stack characters and retain at
most three related causes. The native protocol caps the projection to fit
the existing structured-event limits. Missing identity before startup or
validation is explicitly unavailable, not a new invented execution.

## Available files

Table A

| Id | Output | Where it goes | Content |
| --- | --- | --- | --- |
| A1 | Existing `response.json` | Normal run archive as `<run>-<attempt>-response.json` | Body-free run outcome or safe execution error |
| A2 | Existing Markdown report | Normal run archive and job summary | Readable failure context; no entity names or exception messages |
| A3 | `article-entities-<UTC-day>-<numeric-run-id>-<attempt>.jsonl` | Separate `article-entities-<run>-<attempt>` archive | Private recognized names and completeness evidence |
| A4 | Existing optional raw-document diagnostic | Its existing separate archive | [Body-free failed-input metadata](feed-operator-api.md#failure-only-raw-document-artifact), not entity content |

The [manual workflow](../../how-to/run-feed-ingest-plan-test.md#saved-output-and-failures)
prepares exact paths, lists actual upload files and requires returned upload
identities before cleanup. A file that was not written is not reported as
successful output. Available files remain uploadable after later planner
failure. These files do not prove summarization or publication.

## Recognized article names

[`ArticleEntitiesSchema`](../../../packages/common-contracts/src/schemas/article-entities.schema.ts)
owns each JSONL record. Records carry `run_id`, `attempt`, `traceId`,
`git_sha`, `article_id`, `candidate_id`, `feed_id` and actual UTC
`observed_at`. The article key is its URL hash; the candidate is the same
[captured input UUID](../contracts/identity.md#typescript-captured-article-inputs)
held before extraction. It is not recomputed from run, feed or position.
Source text never selects a filename.

Recognition runs immediately after article extraction. It reads the original
resolved title and the complete sanitized extracted body, not downloaded HTML,
lowercased comparison text or only retained opening paragraphs. The existing
Compromise dependency supplies its public `people()`, `places()` and
`organizations()` APIs. All three queries reuse each unmodified title/body
document. The library's text output retains name case and internal formatting
while excluding sentence-edge punctuation.

Each name states `kind` (`person`, `place` or `organization`) and `scope`
(`title` or `body`). A repeated name is distinct by kind and scope. Names do
not enter progress logs, scoring, technical eligibility checks, selected
metadata or the five planner ledgers. Proper-noun counts are not named
entity recognition.

One attempted article parse produces one record, including an empty name
array. If parsing cannot supply sanitized text, the available title can still
be analyzed and body evidence is marked unavailable. Inputs rejected before
article parsing do not provide extracted text.

`diagnostics.named_entities` supplies validated output limits. Defaults allow
256 distinct names per article and a maximum JavaScript string length of
160 units per name. Output limits do not shorten the text being analyzed.
Whole overlong names are omitted rather than cut into partial names.

Table B

| Id | Evidence | Meaning |
| --- | --- | --- |
| B1 | `title_status`, `body_status` | Each scope was processed, unavailable or failed |
| B2 | `status = complete` | Available title and body were processed without output omissions; recognition is rule-based, not proof that every real name was found |
| B3 | `status = truncated` | Complete input was processed but output limits omitted names |
| B4 | `status = incomplete` | At least one scope was missing or failed; available names remain useful |
| B5 | `omitted_entities` | Distinct names omitted by the total-name limit |
| B6 | `oversized_entities` | Names omitted because their string length exceeded the configured limit |
| B7 | `failure` | Optional shared safe failure context for an analysis error |

The existing default-off service gate controls development execution. The
manual workflow enables its own invocation and generates this requested
artifact without another dispatch switch. No model or new dependency is
added, and no published surface changes.

## Writer lifetime and compatibility

Both private JSONL outputs share an exclusive, serialized writer. Validated
lines first go to a `.part` file. Drain keeps only the complete written
prefix, synchronizes and closes it, then renames it to the final filename.
An unfinished file is never packaged as completed output. An append failure
can leave a valid closed prefix, while the run still reports the failure.
An empty writer creates no file.

Collection finalization, standalone completion and listener shutdown drain
owned writers. Shutdown settles active requests before closing diagnostic
output. The run/attempt directory stays under the authored artifact root;
the workflow uses the existing artifact-directory persistence helper and
does not add a retention policy.

The entity family uses `2026-11-04`. Its reader requires that explicit version
and rejects missing or unknown versions without conversion. TypeScript owns
this private format; Python does not read it.

The saved response contract now lives in
[`PlannerRunResponseSchema`](../../../packages/common-contracts/src/schemas/planner-response.schema.ts).
The saved result retains its execution `traceId`, actual output receipts,
selected identities, assignments, its required health outcome and optional
failure evidence. Health is the actual successful report, an explicit report
failure, or null without eligible completed input. A later report, release,
local save or child-shutdown failure changes the request failure, not completed
planning facts or the saved run row. Independently completed files and report
data remain available.
The response does not retain live stage references. Reports can read completed
files after the listener stops; saved identifiers do not reopen work.
The existing `response.json` also carries an execution error when no complete
HTTP outcome was produced; no second failure file or parser is introduced.

## Design rationale

Attach safe context to the existing response so a failed request, log and
downloaded report retain the same cause. Use approved categories and source
locations rather than copying free-form exception text.

Use the shared [operation identifiers](../contracts/identity.md#4-native-typescript-event-and-operation-metadata)
to name the actual failed work. Do not copy a prior input's operation identity
onto a later delivery or cleanup failure.

Keep recognized names in a separate private artifact because they carry
article content. Recognize before selection so later failure cannot erase
available evidence, and never feed these names back into admission or ranking.

## See also

- [Planner runner](feed-plan-runner.md) - execution and shutdown.
- [Operator APIs](feed-operator-api.md) - body-free responses and private inputs.
- [Manual planner checks](../../how-to/run-feed-ingest-plan-test.md) - upload and cleanup.
