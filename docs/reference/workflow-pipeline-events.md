# Inference workflow events

**Last Updated**: 2026-11-11

Which saved events does the independent inference workflow write and read?

This page owns `ai-pipeline.ts` and its `analytic_synthesis` payload.
The separate [summary-generator caller](summary-generator-caller.md) retains
its own full-analysis and summary-only products; those are not aliases for this
saved experiment format.

## Saved file contract

`.github/scripts/ai-pipeline.ts` writes the named `PIPELINE_EVENTS_PATH` JSONL
file. Each nonempty file contains one structured event per line. A trailing
newline is allowed; blank records, invalid JSON, invalid context and malformed
application data fail the phase with a code and line number. An absent input
file fails the saved-input reader. An empty file selects no saved work.
The retired `--phase=eval` invocation fails with `EVALUATION_RETIRED` before
configuration reads, file writes or inference. Unknown phase selections fail
with `INVALID_PIPELINE_PHASE`; the default and `--phase=infer` retain generation.

The envelope follows the shared
[identity contract](../architecture/contracts/identity.md#4-native-typescript-event-and-operation-metadata).
The workflow selects `/workflows/ai-pipeline` from its unchanged exported
`WORKFLOW_EVENT_SOURCE` declaration in `.github/scripts/ai-pipeline.ts`,
without a source registry or a declaration-only redirect.
Project data version `2026-11-03` is attached to `PipelineEventDataSchema`;
CloudEvents `specversion` remains `1.0`. This is a current-only reader with no
aliases, old-format reader, identity conversion or backfill.
The [native support matrix](../architecture/contracts/identity.md#native-api-support)
also identifies this non-HTTP producer and the upload inventory. Native API
support does not convert the workflow's saved application payload into a
different transport.

Table A - workflow application data

| ID | Path | Meaning |
| --- | --- | --- |
| A1 | `data.result` | The complete original application payload, including saved source text, structured summary and existing measurements. |
| A2 | `data.durationMs` | Rounded milliseconds since the preceding log event in the current phase. This is a log gap, not an operation duration. |
| A3 | `data.cumulativeMs` | Rounded milliseconds on the existing pipeline counter. Loading a saved file resumes from its last value, excludes the gap between phase processes and resets the next log gap. |

`tools/ai-pipeline-experiment/read-pipeline-events.ts` validates the named file and selects
`type === "OUTPUT_STRUCTURED"`, without
rewriting any saved identity, occurrence time, carrier or payload.
The step summary reads the same saved identity and measurement paths.
Console diagnostics contain safe identifiers, counts, measurements and failure
codes, not source text, titles, URLs, prompts, model output or raw exceptions.

## Generation ownership

Each invocation creates a fresh execution root. Generation operations retain
their explicit contexts and W3C carriers. Saved generation readback preserves
each producer and occurrence, including results from different executions.
The inference program remains generation-only; its retired evaluation phase
and legacy coverage report are not restored. After confirmed generator exit,
the workflow's [private native scoring caller](pipeline-summary-evaluation.md)
reads the saved source/summary pairs and reports HHEM and UniEval results.

The inference workflow uploads `pipeline-events.jsonl` and `llama-server.log`.
Existing historical event files are not rewritten or deleted. Non-generation
event results remain opaque application data, not a request to run a retired
evaluator or a source of new scores.

## Offline verification

Prepare the common package's locked dependencies and the workflow's existing
inference dependencies, then run
`bun test ./tools/ai-pipeline-experiment/test/workflow-handoff.test.ts`. The functional cases call the
same production writer, reader, selector and generation report.
They cover distinct occurrences, unchanged producer identity, resumed counters,
explicit malformed-input failure and retired-phase refusal before generation.
They do not dispatch a live model or evaluator.

The test imports the source declaration from the writer it already exercises.
The reader retains only a type-only dependency on that writer. No separate
experiment package or manifest is needed; private event files and their
identities keep their existing locations and meanings.

The named `tests/fixtures/typescript-metadata/workflow-output-event.json` recording
uses fixed replacement text and machine labels. Its token, memory and CPU
readings come from an existing successful workflow recording; this redacted
fixture is protocol evidence, not a performance benchmark. Saved native
identities belong to that fixture, not converted historical events.

## Design rationale

Retiring an audit must not turn its invocation into inference or relabel its
old metrics as another scorer's results. Explicit phase refusal prevents both.
Generation keeps the saved product, source identity and actual measurements.
Existing counters describe logging progress; metadata does not turn them into
recorded spans.

## See also

- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) - shared identity and propagation meanings.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md#independent-typescript-packages-and-services) - focused native checks.
- [../../.github/workflows/ai-pipeline-tests.yml](../../.github/workflows/ai-pipeline-tests.yml) - manual inference and native scoring.
- [summary-generator-caller.md](summary-generator-caller.md) - independent full-analysis and summary-only caller capture.
- [summary-evaluation-workflow.md](summary-evaluation-workflow.md) - retained native scorer comparison.
- [pipeline-summary-evaluation.md](pipeline-summary-evaluation.md) - native scoring after saved inference.
