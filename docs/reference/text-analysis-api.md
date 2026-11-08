# Text-analysis API reference

**Last Updated**: 2026-11-08

The exact routes, settings, request/result fields, errors and diagnostic
vocabularies exposed by the local multilingual text-analysis service.

## Routes

All paths use the fixed first-party family `/api/2026-11-07`.

| Method | Path | Result |
| --- | --- | --- |
| `POST` | `/api/2026-11-07/analyze-text` | Selected feature result or safe request error |
| `GET` | `/api/2026-11-07/get-text-analysis-health` | Configured readiness and capabilities |
| `GET` | `/api/2026-11-07/get-text-analysis-schema` | Current OpenAPI document |

Routes match exactly. There are no trailing-slash aliases, redirects or
interactive documentation pages. Unknown paths return 404; wrong methods
retain `Allow`.

The default listener is `127.0.0.1:3020`. Browser `Origin`, duplicate `Host`
and any host outside that binding are refused before body reading. Every
response carries the operation `traceparent` and optional canonical
`tracestate`.

## Analyze request

The JSON object is strict.

| Field | Required | Values |
| --- | --- | --- |
| `text` | yes | Nonblank Unicode preserved exactly; the body is never trimmed or truncated |
| `language` | yes | `en`, `zh`, `ta` |
| `model_profile` | no | `sm`, `md`, `lg`; omission selects the language's configured default |
| `features` | no | Nonempty unique ordered names from the feature vocabulary |

The default feature order is `relations`, `entities`, `sentences`,
`document_metrics`.

The feature vocabulary is:

- `entities`
- `sentences`
- `relations`
- `noun_phrases`
- `linguistic_tokens`
- `document_metrics`

Tamil is declared but unavailable. Chinese supports every feature except
`noun_phrases`.

## Analyze result

The strict root fields are `status`, `language`, `model` and `features`.
`model` carries the actual `profile`, package, model version and spaCy version.
Trace, queue, process, service identity and timing fields are absent.

Each feature result has `feature`, `status`, nullable typed `data` and nullable
`error`. A complete feature has data and no error. A failed feature has no data
and one matching feature error.

`status` is:

- `complete` when every selected feature completed;
- `partial` when completed and failed features coexist; or
- `failed` when every selected feature failed locally.

Complete and partial results use HTTP 200. An all-feature failure uses HTTP 422.
Request-level failures use the separate error result.

### Evidence spans

Entity mentions, sentences, relations and noun phrases use exact `text`,
`start_char`, `end_char` and `sentence_index`. Offsets are zero-based,
half-open Unicode code-point indexes. Entity mentions add `label`.

Relations contain one `action`, nonempty `actors`, and possibly empty
`objects`, `times` and `places`, all from the same sentence.

Linguistic tokens contain text, offsets, sentence index and nullable `lemma`,
`part_of_speech`, `dependency`, `head_index` and `morphology`.

Document metrics contain source code-point and UTF-8 byte counts, token,
sentence and entity counts, plus nullable `relation_count`. Relation count is
null when relations were not selected or their feature calculation failed.

## Request errors

Every request-level error is:

```json
{
  "error": {
    "code": "BUSY",
    "message": "The text-analysis service is busy.",
    "retryable": true,
    "feature": null
  }
}
```

| Code | HTTP | Retryable | Fixed message |
| --- | ---: | --- | --- |
| `INVALID_REQUEST` | 422 | no | `The text-analysis request is invalid.` |
| `BODY_TOO_LARGE` | 413 | no | `The request body is too large.` |
| `HOST_FORBIDDEN` | 403 | no | `The request Host header is not accepted.` |
| `ORIGIN_FORBIDDEN` | 403 | no | `Browser Origin requests are not accepted.` |
| `SERVICE_DISABLED` | 503 | no | `The text-analysis service is disabled.` |
| `BUSY` | 429 | yes | `The text-analysis service is busy.` |
| `LANGUAGE_UNAVAILABLE` | 422 | no | `The selected language is not available.` |
| `UNSUPPORTED_MODEL_PROFILE` | 422 | no | `The selected model profile is not supported.` |
| `UNSUPPORTED_FEATURE` | 422 | no | `The selected feature is not supported.` |
| `MODEL_UNAVAILABLE` | 503 | yes | `The selected model is not available.` |
| `ANALYSIS_FAILED` | 500 | yes | `The text analysis failed.` |

Feature-level errors use the same detail shape with the affected feature:

| Code | Retryable | Fixed message |
| --- | --- | --- |
| `FEATURE_UNAVAILABLE` | no | `The selected feature is not available.` |
| `FEATURE_FAILED` | yes | `The selected feature failed.` |

## Health

Health returns:

- `enabled`
- `status`: `ready`, `disabled`, `failed` or `stopping`
- `active_requests`
- `max_concurrent_requests`
- `pool_ready`
- configured spaCy version
- default and allowed features
- ordered language capabilities with enablement, default profile, supported
  features and package/version profile declarations

HTTP 200 requires `ready`; every other status uses 503. Health never loads a
model and never reports worker PIDs, queue depth or loaded-model state.

## Production settings

`config/text-analysis/settings.json` is strict and has no workflow block.

| Setting | Initial value or rule |
| --- | --- |
| `version` | `2026-11-07` with newest-first changelog |
| `enabled` | `true` |
| listener | `127.0.0.1:3020` |
| maximum body | `1,048,576` bytes |
| body-read deadline | `5,000` milliseconds |
| graceful shutdown | `15,000` milliseconds |
| `max_concurrent_requests` | `2`; schema permits one or two |
| `spacy_version` | `3.8.18` |
| model versions | `3.8.0` |
| logging | `INFO`, maximum event size `4,096` bytes |

Each enabled language declares exact `sm`, `md` and `lg` package versions and
HTTPS wheel destinations. Requests and environment variables cannot replace a
destination. The preparation script selects one configured language/profile
for workflow use, or all enabled profiles when no selection is supplied.

## CloudEvents

Every nonblank stderr record is one strict CloudEvents 1.0 JSON object:

- lowercase UUIDv4 `id`
- source `/services/text-analysis`
- UTC second or millisecond `time` ending in `Z`
- `application/json`
- valid `traceparent` and optional canonical `tracestate`
- typed service or request data

Service types are:

- `text-analysis.service.started`
- `text-analysis.service.ready`
- `text-analysis.service.stopped`
- `text-analysis.service.failed`

Request types are:

- `text-analysis.request.completed`
- `text-analysis.request.partial`
- `text-analysis.request.failed`

Request data carries language and resolved model identity when available,
requested feature names and statuses, active/capacity counts, nonnegative
`model_load_ms`, `analysis_ms` and `total_ms`, result status and fixed error
codes. It never carries source/evidence text, spans, model URLs, headers,
process IDs, paths or exceptions.

## See also

- [How multilingual text analysis runs](../architecture/text-analysis/text-analysis-api.md)
- [Run the text-analysis verification](../how-to/run-spacy-tests.md)
- [First-party API routing](api-routing.md)
- [Local API host](../architecture/local-api-host.md)
