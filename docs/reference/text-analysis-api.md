# Text-analysis API reference

**Last Updated**: 2026-11-11

The exact routes, settings, request/result fields, errors and diagnostic
vocabularies exposed by the local multilingual text-analysis service.

## Routes

All spaCy paths use the fixed first-party family `/api/2026-11-08`.

Table A - Native spaCy routes

| Id | Method | Path | Result |
| --- | --- | --- | --- |
| A1 | `POST` | `/api/2026-11-08/run-ner-spacy` | Selected feature result or safe request error |
| A2 | `GET` | `/api/2026-11-08/get-spacy-health` | Configured readiness and capabilities |
| A3 | `GET` | `/api/2026-11-08/get-spacy-schema` | Current OpenAPI document |

Routes match exactly. There are no trailing-slash aliases, redirects or
interactive documentation pages. Unknown paths return 404; wrong methods
retain `Allow`. The former `2026-11-07` analysis, health and schema paths
return 404 without aliases or redirects.

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

English defaults to `named_entities`, `important_terms`, `relations`. An explicit
`features` list replaces these defaults rather than extending them. Chinese inherits the
global order: `relations`, `entities`, `sentences`, `document_metrics`.
Omitting a language override inherits that recorded global order.

The feature vocabulary is:

- `entities`
- `sentences`
- `relations`
- `noun_phrases`
- `linguistic_tokens`
- `document_metrics`
- `named_entities`
- `important_terms`

The two compact features are English-only. Tamil is declared but unavailable.
Chinese retains its raw features except `noun_phrases`.

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

### Named Entities

`named_entities.data.entities` contains `text`, `type` and nonempty
`occurrences` of evidence spans. Grouping uses the configured case rule and
mapped type, preserves the first original spelling and every source occurrence,
and orders both groups and occurrences by source position. This is
document-local grouping, not cross-document identity or topic classification.
Unmapped labels remain available through raw `entities`.

### Important Terms

`important_terms.data.terms` contains `text`, finite nonnegative `score` and
nonempty `occurrences`. YAKE supplies statistical phrase scores; lower scores
rank first, with first source position breaking ties. Scores are not confidence
or model-quality claims.

Candidate tokens match the original document across whitespace tokens.
Pattern tokenization does not rerun the model. Matching phrases are deduplicated
and ordered by score/source before native similarity filtering. Filtering stops
as soon as the configured maximum of distinct selected patterns is filled;
each selected pattern still retains all source occurrences. The displayed text preserves the
first source spelling. A selected candidate without an exact source occurrence
fails only this feature with `FEATURE_FAILED`; there is no fabricated offset
or substring repair. No candidates or a configured zero maximum returns a
completed empty list.

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
  features, resolved `default_features`, `important_terms_limit` and
  package/version profile declarations

HTTP 200 requires `ready`; every other status uses 503. Health never loads a
model and never reports worker PIDs, queue depth or loaded-model state.
Each current language capability requires both added fields. Enabled English
with Important Terms support declares its configured nonnegative limit; other
capabilities declare `null`. Disabled language defaults are empty.

## Production settings

`config/text-analysis/settings.json` is strict and has no workflow block.

| Setting | Initial value or rule |
| --- | --- |
| `version` | `2026-11-09` with newest-first changelog |
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

Table B - Compact English feature settings

| Id | Setting | Default and meaning |
| --- | --- | --- |
| B1 | `named_entities.ignore_case` | `true`; case-fold names when forming groups |
| B2 | `named_entities.label_map` | `PERSON -> person`, `ORG -> organization`, `GPE/LOC -> location`; unmapped labels remain raw |
| B3 | `important_terms.max_results` | `25`; maximum returned terms, with `0` selecting an empty successful list |
| B4 | `important_terms.max_phrase_words` | `3`; positive maximum candidate phrase width |
| B5 | `important_terms.deduplication_threshold` | `0.9`; finite similarity threshold from `0` through `1` |
| B6 | `important_terms.deduplication_method` | `seqm`; native choices are `seqm`, `jaro`, `levs` |
| B7 | `important_terms.window_size` | `1`; positive statistical co-occurrence window |
| B8 | `important_terms.stopwords` | `null` uses library English stopwords; a custom nonempty distinct list replaces them |
| B9 | `languages.en.default_features` | `named_entities`, `important_terms`, `relations`; an omitted override inherits global defaults |

Every option is validated by the native settings model. There is no second
enable-switch system, model selection or classification registry for these
outputs.

## Read compatibility

Current schemas advance independently of the fixed HTTP date and package
release. Changed feature-bearing declarations and live health use
`2026-11-09`; unchanged raw evidence, result envelopes and service-event
definitions retain their original schema metadata.

Settings versions `2026-11-07`, `2026-11-08` and `2026-11-09` remain readable. Missing new
options receive the declared defaults, while a missing language override
preserves the file's recorded global feature order and version.

New live health must contain complete current capabilities. The separate
`read_retained_native_evidence` reader accepts exact current or initial health
shapes. Initial health uses its recorded global defaults; its absent term
limits stay unknown rather than being filled from current settings. Mixed or
partial new fields are rejected. Existing request/result/event payloads remain
readable and retained files are not rewritten. The verification receipt has
its own unchanged version and changelog.

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
- [Run text analysis and inspect results](../how-to/run-spacy-tests.md)
- [First-party API routing](api-routing.md)
- [Local API host](../architecture/local-api-host.md)
