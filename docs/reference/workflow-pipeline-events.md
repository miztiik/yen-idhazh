# Phased workflow events

**Last Updated**: 2026-11-05

Which saved events does the independent inference and evaluation workflow read?

## Saved file contract

`.github/scripts/ai-pipeline.ts` writes the named `PIPELINE_EVENTS_PATH` JSONL
file. Each nonempty file contains one structured event per line. A trailing
newline is allowed; blank records, invalid JSON, invalid context and malformed
application data fail the phase with a code and line number. An absent input
file fails evaluation. An empty file selects no work. Neither case starts
inference.

The envelope follows the shared
[identity contract](../architecture/contracts/identity.md#4-native-typescript-event-and-operation-metadata).
The workflow selects `/workflows/ai-pipeline` from its local
`.github/scripts/declare-workflow-event-source.ts`, without a source registry.
Project data version `2026-11-03` is attached to `PipelineEventDataSchema`;
CloudEvents `specversion` remains `1.0`. This is a current-only reader with no
aliases, old-format reader, identity conversion or backfill.
The [native support matrix](../architecture/contracts/identity.md#native-api-support)
also identifies this non-HTTP producer and the upload inventory. Native API
support does not convert the workflow's saved application payload or its
foreign evaluator protocol into a different transport.

Table A - workflow application data

| ID | Path | Meaning |
| --- | --- | --- |
| A1 | `data.result` | The complete original application payload, including saved source text, structured summary and existing measurements. |
| A2 | `data.durationMs` | Rounded milliseconds since the preceding log event in the current phase. This is a log gap, not an operation duration. |
| A3 | `data.cumulativeMs` | Rounded milliseconds on the existing pipeline counter. Loading a saved file resumes from its last value, excludes the gap between phase processes and resets the next log gap. |

`read-pipeline-events.ts` validates the named file and selects
`type === "OUTPUT_STRUCTURED"`. Evaluation consumes `data.result`, without
rewriting any saved identity, occurrence time, carrier or payload.
The step summary reads the same saved identity and measurement paths.
Console diagnostics contain safe identifiers, counts, measurements and failure
codes, not source text, titles, URLs, prompts, model output or raw exceptions.

## Evaluation handoff

Each phase invocation creates a fresh execution root. Each saved input gets a
separate evaluation operation inside that phase. Its input link identifies
that input's saved producer, even when inputs came from different executions.
The explicit operation context stays in the workflow; events carry its W3C
carrier. No trace runtime or extra artifact is created.

`prepare-evaluation-request.ts` constructs the unchanged Python evaluator
request from the saved source identifier, headline, extracted source text and
analytic synthesis. Its separate `correlationId` is a new UUIDv4, not the
native execution identifier. The Python response remains a foreign protocol:
quality scores come from `response.metrics`, and machine measurements come
from `response.event.payload.serverTelemetry`. The native workflow records
those returned values without relabeling the foreign event.

Failed inference outputs remain skipped. A failed evaluator request remains
a failed evaluation target and causes the phase to fail after its batch report.
The workflow uploads only its existing application and server-log artifacts.

## Offline verification

Prepare the common package's locked dependencies and the workflow's existing
inference dependencies, then run
`bun test ./.github/scripts/test/workflow-handoff.test.ts`. The functional cases call the
same production writer, reader, selector, request builder and response reader.
They cover unchanged saved handoff, distinct occurrences, per-input links,
foreign measurement readback, resumed counters and explicit malformed-input
failure. They do not dispatch a live model or evaluator.

The three named recordings under `tests/fixtures/typescript-metadata/` use fixed
replacement text and machine labels. Token, memory, CPU and evaluator numbers
come from an existing successful workflow recording; these redacted fixtures
are protocol evidence, not a performance benchmark. Saved native identities
belong to the current fixture, not converted historical events.

## Design rationale

Independent phase processes do not form one enclosing operation. A new phase
therefore has a fresh root and links each input separately. Existing counters
remain measurements of logging progress; metadata does not turn them into
recorded spans. The foreign UUID stays separate because its Python consumer
has not changed.

## See also

- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) - shared identity and propagation meanings.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md#independent-typescript-packages-and-services) - focused native checks.
- [../../.github/workflows/ai-pipeline-tests.yml](../../.github/workflows/ai-pipeline-tests.yml) - offline handoff gate and manual live phases.
