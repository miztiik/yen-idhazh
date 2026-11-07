# Source-coverage evaluation API

**Last Updated**: 2026-11-07

Which prepared inputs, unchanged legacy metrics and safe failures belong to
the explicitly selected coverage operation in `summary_evaluator`.
The [calculation reference](../architecture/evaluation/source-coverage.md)
owns retrieval order, rounding and method differences.

## Selection and native routes

`config/summary-evals/api.json` owns the distinct `listeners.coverage` binding,
with default loopback port 3012. The comparison workflow starts only separate HHEM
and native UniEval APIs. Select `--routes coverage`
only for a run that needs the legacy method; an unselected component
reads no coverage configuration/resources and constructs no controller or worker.

Table A - Operations

| Id | Method and path | Meaning |
| --- | --- | --- |
| A1 | `POST /api/2026-11-05/evaluate-summary-coverage` | Return complete legacy metrics for supplied prepared text. |
| A2 | `GET /api/2026-11-05/get-summary-coverage-health` | Observe the actual model, owned process, queue and safe failure state. |
| A3 | `GET /api/2026-11-05/get-summary-evaluator-health` | This coverage API's readiness and application identity; other scorers are disabled. |

The first-party HTTP date remains `2026-11-05`. Coverage's transient native
contracts are independently stamped `2026-11-07` under
`source_coverage/contracts/`. The old `/v1/evaluate`, camelCase request aliases
are removed, not redirected. The selected coverage API now owns its own configured
listener and lifetime; stopping it does not restart another scorer.

## Request and result

The request contains exactly required nonblank UTF-8 `source_text` and
`summary_text`. Unknown fields, explicit null and numeric coercion fail.
It carries no URL, title, runner/shard identity, request UUID or reference summary.
Text validation does not trim inputs; the legacy calculation retains its own
unchanged preparation rules.

Success is `{status: "success", metrics: ...}`. Metrics retain
`overall_consistency`, `coherence`, `fluency`, `document_chunks_total`,
`document_chunks_covered`, `chunk_coverage_percent`, `sentence_breakdown` and
optional `uncovered_sections`, including their existing nested links and evidence.
No server event, hardware measurement or report metadata is added.
Historical optional evidence remains readable without inventing missing fields.

Every returned native dimension batch must have the requested cardinality,
requested dimension and finite probability before reduction. A missing batch,
missing key or nonfinite value fails `INVALID_MODEL_OUTPUT`; an actual zero
remains valid. No completed dimension becomes partial coverage success.

## Prepared resources and ownership

`config/summary-evals/unieval-evaluator/coverage.json` declares the exact legacy
code/model/tokenizer pins, finite asset inventories, sentence archive, preparation
limits and worker/queue deadlines. Preparation resolves named assets before
serving; the child loads only verified local resources.

The upstream loader has no revision parameter. Its private offline cache maps
the committed repository name to the verified immutable snapshot. Loaded model,
tokenizer and code identities are checked before readiness, without using native
UniEval's pin as a substitute for legacy provenance.

Coverage owns one bounded queue and model process. Adding it to the default
two-scorer invocation adds resident model memory and another process; it does not
share an in-memory model. Its failure does not erase completed HHEM or native
UniEval work. Parent loss, cancellation and shutdown stop the exact owned child
and confirm its exit within the declared bounds.

The [capture guide](../how-to/capture-source-coverage-calls.md) owns actual
preparation/capture commands. The real `verify-coverage-worker.py` utility uses
one named input, the actual child and bounded byte pipes without a listener.
It reports actual readiness/completion/owned exit and does not replace Linux
model-free or ordinary CI gates.

## Fixed safe failures

Failure is `{error: {code, type: "api_error", message}}` through the shared safe
renderer. Messages come only from the closed native policy, not exceptions,
validation input or model text.

Table B - Runtime failures

| Id | Failure | HTTP status |
| --- | --- | --- |
| B1 | `QUEUE_FULL` | 429, with the configured retry delay. |
| B2 | `QUEUE_TIMEOUT`, stopping or not-ready service | 503; no score or input read for an unready worker. |
| B3 | `EVALUATION_TIMEOUT` | 504; the active owned child is stopped. |
| B4 | Invalid model output, model or worker failure | 500; no partial metrics. |
| B5 | Existing JSON/media/host/origin/body-read refusals | Their unchanged 400/403/408/413/415 policy. |

The caller preserves its completion event and report. New machine readings are
uncollected/unavailable, never zero. Historical server telemetry remains readback
evidence, not a new measurement.

## See also

- [../architecture/evaluation/source-coverage.md](../architecture/evaluation/source-coverage.md) - exact retained calculation.
- [summary-evaluator-api.md](summary-evaluator-api.md) - shared settings and diagnostics.
- [unieval-api.md](unieval-api.md) - separate independent-reference native method.
- [workflow-pipeline-events.md](workflow-pipeline-events.md) - caller-owned saved handoff and report.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md#independent-python-service-contracts) - truthful offline/Linux verification.
