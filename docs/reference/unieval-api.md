# UniEval evaluation API

**Last Updated**: 2026-11-09

Which requests, applicable scores and settings belong to the local API.
The [architecture](../architecture/evaluation/unieval-api.md) defines score
meaning, complete-source processing and process ownership.

## Native ownership and routes

`services/summary_evaluator/src/summary_evaluator/unieval/contracts/` owns
the native Pydantic contracts and on-demand schemas. Their version is
`2026-11-08` for requests and effective controls, and `2026-11-09` for results
and measured errors.
Health, model identity, work and genuine recordings retain `2026-11-04`.
Private worker packets use their separate `2026-11-09` version and require the
resolved relevance skip and dimension-bound measurements. Live producers and consumers change together.
Frozen readers preserve original four-score and `2026-11-08` applicable-score results without
rewriting their versions, hashes or meaning; invalid current data never selects
an older reader. Genuine recordings remain unchanged. There are no old-route aliases.
There is no result store, polling API or published-data contract.

The comparison workflow starts separate HHEM and native UniEval APIs.
Full-source and source-window checks remain part of this native calculation,
not the retired legacy coverage service. Independent-reference relevance keeps
its meaning but runs only when selected and a reference is supplied.

Table A - Native operations

| Id | Route | Meaning |
| --- | --- | --- |
| A1 | `POST /api/2026-11-05/evaluate-summary-unieval` | Perform one synchronous evaluation of every applicable dimension. |
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
| B2 | `reference_summary_text` | Omittable independent reference for the same source. Supplied null or blank text is invalid; exact UTF-8 bytes are preserved. The API generates or substitutes no reference. |
| B3 | `consistency_source_mode` | Omittable `full_source_prompt` or `all_source_windows`; omission uses the committed `full_source_prompt` default. Windows require an explicit request or committed configuration selection. |
| B4 | `request_id`, `correlation_id` | Omittable native UUIDv4 strings; supplied spelling is retained. The API creates its own execution identity. |
| B5 | `evaluate_relevance` | Omittable strict boolean; omission uses validated `scoring.evaluate_relevance`, default false. Explicit false overrides a configured true. Reference presence never selects work. |

Fluency, coherence and consistency remain required. Disabled relevance takes
precedence over reference absence. Enabled relevance without a reference is
also skipped, not a failed evaluation.

Default `full_source_prompt` compares each native summary sentence with the
complete unchanged source, then averages every completed sentence score.
Explicit `all_source_windows` scores every sentence against every planned
original-source span, then averages per-sentence maxima. Both leave the other
dimensions unchanged; neither permits clipping, a shortened summary or an
automatic retry in another mode. Coherence remains one complete-source and
complete-summary question even with explicit consistency windows.

## Body-free result

Table C - Output

| Id | Field | Meaning |
| --- | --- | --- |
| C1 | `version`, `status` | Current version and `complete`, `partial` or `failed`. Complete requires every applicable numeric score and no errors, including three scores with an authorized relevance skip. |
| C2 | `execution_id`, `request_id`, `correlation_id` | Actual request identity and nullable unresolved caller identities. |
| C3 | `reference_summary_sha256` | SHA-256 of every valid supplied reference's exact UTF-8 bytes, even when unused. Null when reference is absent or input is not validated; the hash alone is not scoring evidence. |
| C4 | `model`, `worker` | Configured/loaded immutable asset and tokenizer revisions, reference-code revision, observed runtime versions and the actual owned worker identity. Null until observed. |
| C5 | `effective_settings` | Resolved relevance boolean, mode, prompt allowance, source target/overlap, finite plan limits and effective source budget. |
| C6 | `scores` | Nullable finite `fluency`, `coherence`, `consistency` and `relevance`, each from zero to one. No scoring-time rounding or overall aggregate. |
| C7 | `work` | Per-dimension planned/completed counts, summary-sentence count, source-character count and complete source-span plan. Span offsets are zero-based, end-exclusive Unicode code-point offsets into the original source. |
| C8 | `timings_ms` | Nullable queue-wait, scoring and total durations, in milliseconds measured with a monotonic clock. |
| C9 | `errors` | Closed safe codes, nullable dimension and zero-based comparison index, fixed message and paired nullable `input_tokens`/`allowed_tokens`. Measured refusals count the actual complete assembled input and exceed the configured allowance. Both fields may be absent for historical or unmeasured errors; absence is not reconstructed. No text or raw exception is included. |
| C10 | `relevance_skip_reason` | Required nullable `disabled` or `reference_not_supplied`. A skip has no relevance score, plan, completed comparison or relevance error. Attempted relevance failures and invalid requests have no skip reason. |

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

The authored config family is version `2026-11-08`, current-only: old inline
question settings are refused rather than retained as another active default.
Its `prompt_files` values are safe relative POSIX `.txt` paths under `prompts/`
in the invocation's `config/` root. The loader reads the four declared files,
preserves all UTF-8 whitespace, and builds the existing effective `prompts`
model before placeholder validation, worker handoff or model input hashing.
Effective scoring settings use `2026-11-08`; recordings retain `2026-11-04`.
No file path is hashed as though it changed question wording.

`scoring.max_input_tokens` is an operator resource allowance for each complete
assembled question/text input, including special tokens. The
[token-policy rationale](../architecture/evaluation/unieval-api.md#design-rationale)
distinguishes it from the upstream constructor default and advisory tokenizer
metadata; none is a fixed architectural context maximum.

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

The capture/replay boundary reads frozen original requests and controls, then
selects an explicit current four-score execution. It does not add selection to
old recordings or change their captured prompt hashes.

## Safe refusal and failures

Existing native body, media, origin/host, input-read, queue and process
policies apply. A reserved input is bounded before it is read.
Input-size and plan-limit refusals use HTTP 400, queue admission uses HTTP 429,
unready/stopping service uses HTTP 503, model/protocol failures use HTTP 500
and the complete evaluation deadline uses HTTP 504.

`SUMMARY_SENTENCE_TOO_LONG`, `COHERENCE_INPUT_TOO_LONG`,
`RELEVANCE_INPUT_TOO_LONG` and `CONSISTENCY_INPUT_TOO_LONG` identify complete
inputs that do not fit, preserving the affected dimension, comparison index
and actual token count against its configured allowance. The internal
`MODEL_INPUT_TOO_LONG` predictor refusal is mapped at the comparison boundary;
it is never returned as an unidentified public size error.
`WINDOW_BUDGET_INSUFFICIENT` instead means that the summary-sentence question
fits but original-character source windows cannot reserve positive progress
and required overlap. It has no oversized-input measurement.
An oversized summary-sentence question remains `SUMMARY_SENTENCE_TOO_LONG`
for consistency planning. The
[token-policy rationale](../architecture/evaluation/unieval-api.md#design-rationale)
defines which complete input is counted.
`WINDOW_LIMIT_EXCEEDED` and
`COMPARISON_LIMIT_EXCEEDED` refuse excessive plans rather than omit work.
Input-size failures leave affected scores null; other admissible dimensions
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
| E4 | `planned` | Current request identity/metadata, `effective_settings`, required nullable `relevance_skip_reason`, native `work` and `errors`. |
| E5 | `prediction` | Current request identity/metadata, `dimension`, `index`, `sentence_index`, `source_index`, `score` and `error`. Existing indexing and reduction are unchanged. |
| E6 | `finished` | Current request identity and the same issued evaluation metadata; it does not manufacture per-item work. |

The single [native operation contract](../architecture/contracts/identity.md)
owns metadata fields and codec rules. The parent validates exact operation,
execution and generation equality before accepting existing plan/progress
rules; repeated or crossed replies fail the real protocol validator.
The parent derives selection from its validated request and settings, rejecting
changed controls, unauthorized skips and any relevance work for a skipped dimension.
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
