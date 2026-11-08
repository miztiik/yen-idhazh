# UniEval evaluation API

**Last Updated**: 2026-11-08

Which requests, results and settings belong to the local four-score API.
The [architecture](../architecture/evaluation/unieval-api.md) defines score
meaning, complete-source processing and process ownership.

## Native ownership and routes

`services/summary_evaluator/src/summary_evaluator/unieval/contracts/` owns
the native Pydantic contracts and on-demand schemas. Their version is
`2026-11-04` for native scoring and recordings. Private worker packets use
their separate `2026-11-08` version. They are transient, current-only contracts: producers and
consumers change together, without old-route aliases or historical readers.
There is no result store, polling API or published-data contract.

The comparison workflow starts separate HHEM and native UniEval APIs.
Full-source and source-window checks remain part of this native calculation,
not the retired legacy coverage service. Independent-reference relevance is unchanged.

Table A - Native operations

| Id | Route | Meaning |
| --- | --- | --- |
| A1 | `POST /api/2026-11-05/evaluate-summary-unieval` | Perform one synchronous four-dimension evaluation. |
| A2 | `GET /api/2026-11-05/get-unieval-health` | Observe this component's actual model, worker, queue and failure state. |
| A3 | `GET /api/2026-11-05/get-summary-evaluator-health` | This UniEval application's readiness and identity; other scorer slots are disabled. |

`config/summary-evals/api.json` owns `listeners.unieval` and logging. Select
`--routes unieval` for this independent process. Disabled
operation routes return HTTP 404 and no model/configuration is loaded.
The API prefix is a protocol path, not another listener. The
[routing convention](api-routing.md) separates its date from the unchanged
native UniEval scoring schema.

## Request

Unknown fields, explicit null controls, numeric coercion and blank text are
refused. Text validation does not trim or replace inputs.

Table B - Inputs

| Id | Field | Contract |
| --- | --- | --- |
| B1 | `source_text`, `summary_text` | Required nonblank UTF-8 source and generated summary. |
| B2 | `reference_summary_text` | Required independent reference summary for the same source. The API does not generate or substitute it. |
| B3 | `consistency_source_mode` | Omittable `all_source_windows` or `full_source_prompt`; omission uses the committed scoring default. |
| B4 | `request_id`, `correlation_id` | Omittable native UUIDv4 strings; supplied spelling is retained. The API creates its own execution identity. |

`all_source_windows` scores every summary sentence against every planned
source span, then averages per-sentence maxima. `full_source_prompt` retains
native full-source consistency. Both leave the other dimensions unchanged;
neither permits input clipping or a shortened summary.

## Body-free result

Table C - Output

| Id | Field | Meaning |
| --- | --- | --- |
| C1 | `version`, `status` | Current version and `complete`, `partial` or `failed`. Complete requires all four valid dimensions and no errors. |
| C2 | `execution_id`, `request_id`, `correlation_id` | Actual request identity and nullable unresolved caller identities. |
| C3 | `reference_summary_sha256` | SHA-256 of exact reference UTF-8 bytes after valid input; null before validation. |
| C4 | `model`, `worker` | Configured/loaded immutable asset and tokenizer revisions, reference-code revision, observed runtime versions and the actual owned worker identity. Null until observed. |
| C5 | `effective_settings` | Resolved mode, prompt allowance, source target/overlap, finite plan limits and effective source budget. |
| C6 | `scores` | Nullable finite `fluency`, `coherence`, `consistency` and `relevance`, each from zero to one. No scoring-time rounding or overall aggregate. |
| C7 | `work` | Per-dimension planned/completed counts, summary-sentence count, source-character count and complete source-span plan. Span offsets are zero-based, end-exclusive Unicode code-point offsets into the original source. |
| C8 | `timings_ms` | Nullable queue-wait, scoring and total durations, in milliseconds measured with a monotonic clock. |
| C9 | `errors` | Closed safe codes, nullable dimension/index and fixed message. No exception, raw validation value, source passage or model body. |

A numeric dimension requires every planned comparison and its observed
model/worker. Partial retains completed dimensions when required work fails.
Failed has no completed dimension. Error HTTP responses still use this native
result; clients must validate and retain them rather than discard their body.

## Settings and preparation

`config/summary-evals/unieval-evaluator/settings.json` owns the selected assets,
question-file paths, answer tokens, source-processing defaults, queue, request
and worker deadlines.
The selected listener/logging snapshot is supplied by the app, not duplicated
in the evaluator file. The named file is loaded once per invocation.

The authored config family is version `2026-11-07`, current-only: old inline
question settings are refused rather than retained as another active default.
Its `prompt_files` values are safe relative POSIX `.txt` paths under `prompts/`
in the invocation's `config/` root. The loader reads the four declared files,
preserves all UTF-8 whitespace, and builds the existing effective `prompts`
model before placeholder validation, worker handoff or model input hashing.
The effective settings and all scoring/recording contracts retain `2026-11-04`.
No file path is hashed as though it changed question wording.

Table D - Native question files

| Id | `prompt_files` key | Default path and plain placeholders |
| --- | --- | --- |
| D1 | `fluency` | `prompts/evaluate-fluency.txt`; `{summary}` |
| D2 | `coherence` | `prompts/evaluate-coherence.txt`; `{summary}`, `{source}` |
| D3 | `consistency` | `prompts/evaluate-consistency.txt`; `{summary}`, `{source}` |
| D4 | `relevance` | `prompts/evaluate-relevance.txt`; `{summary}`, `{reference}` |

The default files have no final newline, matching the original inline strings.
`prompts.positive_answer` and `prompts.negative_answer` remain in JSON.
Unknown substitutions, conversions and format specifications fail before
scoring. Paths are validated before text is read; absent files and invalid
UTF-8 fail by the named file, without logging its contents.
These questions belong to native UniEval, not the independent generator or
the source-coverage worker's pinned upstream question construction.

The config contains the immutable model revision and finite file list.
`assets.sentences` declares the pinned sentence archive, digest, language,
named files and download bound. Scoring uses only prepared local files.
The model-extra adds NLTK for native sentence boundaries; the resource
dependency group supplies the tokenizer and splitter without Torch.

The [run guide](../how-to/run-unieval-evaluation-api.md) owns preparation and
execution commands. The committed API listener is not another evaluator setting.
Cache paths remain local operator configuration, never HTTP controls.

`scripts/capture-unieval-recordings.py` runs the real selected model on the
named project-authored inputs and captures identity-bound predictions.
Ordinary tests run real tokenizer planning, reduction, API and process
handling while replaying only that recorded prediction boundary. They open
no network listener and download no resources. Prepare the required named
files before testing; a missing preparation is a failure, not a skip.
The Windows asyncio/socket-guard limitation in the
[gate guide](../how-to/run-the-gates.md#independent-python-service-contracts)
still applies to ASGI cases.

## Safe refusal and failures

Existing native body, media, origin/host, input-read, queue and process
policies apply. A reserved input is bounded before it is read.
Context and plan-limit refusals use HTTP 400, queue admission uses HTTP 429,
unready/stopping service uses HTTP 503, model/protocol failures use HTTP 500
and the complete evaluation deadline uses HTTP 504.

`SUMMARY_SENTENCE_TOO_LONG`, `COHERENCE_INPUT_TOO_LONG`,
`RELEVANCE_INPUT_TOO_LONG` and `CONSISTENCY_INPUT_TOO_LONG` identify complete
prompts that do not fit. `WINDOW_LIMIT_EXCEEDED` and
`COMPARISON_LIMIT_EXCEEDED` refuse excessive plans rather than omit work.
Context failures leave affected scores null; other admissible dimensions
can finish. A real computed zero is never a missing-value marker.

Shutdown closes admission and joins the exact owned worker. A blocked or
failed worker is stopped, not replaced by an automatic retry daemon.
Original evaluation and cleanup errors remain separate. Shared diagnostic
file failure follows the server's warning-only mirror policy.

## Current private worker packets

Table E - Issued worker operations

| Id | Kind | Fields and operation |
| --- | --- | --- |
| E1 | `bootstrap` | Current private `version`, frozen `settings` and required `operation_metadata` for the actual service-load operation. |
| E2 | `ready`, `startup_failed` | Current private `version`, the unchanged ready/error fields and that same required load metadata. Readiness still requires the actual owned worker/model identity. |
| E3 | `evaluate` | Current private `version`, `execution_id`, `generation`, native `request` and required metadata for the actual worker evaluation child of the receiving request. |
| E4 | `planned` | Current request identity/metadata, `effective_settings`, native `work` and `errors`. |
| E5 | `prediction` | Current request identity/metadata, `dimension`, `index`, `sentence_index`, `source_index`, `score` and `error`. Existing indexing and reduction are unchanged. |
| E6 | `finished` | Current request identity and the same issued evaluation metadata; it does not manufacture per-item work. |

The single [native operation contract](../architecture/contracts/identity.md)
owns metadata fields and codec rules. The parent validates exact operation,
execution and generation equality before accepting existing plan/progress
rules; repeated or crossed replies fail the real protocol validator.
Producers and consumers upgrade together after old owned processes are
retired, without live old-packet fallback or historical rewriting.
Complete command metadata and escaping contribute to derived command bounds.
Every reply remains inside `worker.max_reply_bytes`; byte-pipe JSON has no
record newline. Trace observations do not create or erase numeric scores.

## See also

- [../architecture/evaluation/unieval-api.md](../architecture/evaluation/unieval-api.md) - complete-source calculation and limitations.
- [../how-to/run-unieval-evaluation-api.md](../how-to/run-unieval-evaluation-api.md) - preparation, serving and real recording commands.
- [summary-evaluator-api.md](summary-evaluator-api.md) - listener, component selection and CloudEvents.
- [summary-evaluation-workflow.md](summary-evaluation-workflow.md) - separate workflow orchestration.
- [../architecture/contracts/identity.md](../architecture/contracts/identity.md) - native request and occurrence identity.
