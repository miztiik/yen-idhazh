# Native GLiNER2 API reference

**Last Updated**: 2026-11-08

The exact routes, payloads, settings and safe diagnostic vocabulary of the
independent local GLiNER2 provider.

## Routes

The fixed creation-date family is `/api/2026-11-08`, declared once as
`API_VERSION` in `gliner_api.declare_api_contracts`. It does not follow the
request clock, model identity or package release.

Table A - Native operations

| Id | Method | Path | Result |
| --- | --- | --- | --- |
| A1 | POST | `/api/2026-11-08/run-ner-gliner` | Scored exact source mentions |
| A2 | POST | `/api/2026-11-08/classify-text-gliner` | Requested classification IDs and native scores |
| A3 | GET | `/api/2026-11-08/get-gliner-health` | Genuine provider availability |
| A4 | GET | `/api/2026-11-08/get-gliner-schema` | Native OpenAPI, without an interactive UI |

Matching is exact. Unknown and trailing-slash paths return 404; wrong methods
return 405 with `Allow`. The existing text-analysis settings supply the
listener, body byte limit, absolute read deadline and shutdown deadline.
Host and Origin guards run before body reading. Every response receives the
host's W3C carrier rather than trace fields in its JSON body.

## Requests and results

All live objects reject undeclared fields and coercion. Text is nonblank valid
UTF-8 and is preserved exactly.

NER requests contain only `text` and a nonempty, unique, ordered `labels` array.
Results contain only `entities`, an array of:

- `text`: the exact mention;
- `label`: one requested entity type;
- `start_char` and `end_char`: zero-based, half-open Python Unicode code-point
  offsets whose source slice reproduces `text`;
- `score`: finite native confidence in `[0, 1]`.

An empty prediction array is valid, not a replacement for an inference error.

Classification requests contain only `text` and a nonempty `tasks` object.
Each named task contains a nonempty `labels` mapping from ID to nonblank
definition and a strict `multi_label` boolean. Task and label order are retained.
There is no fixed API membership list. Callers offer current active entries
from `config/taxonomy.json`; draft and retired entries are not new targets.

Results contain only `classifications`, mapping every requested task to an
array of `{id, score}` selections. IDs must belong to that task's request,
scores are finite native confidence in `[0, 1]`, and selections cannot repeat
an ID. Single-label tasks have at most one selection. Native multi-label
selection can retain its strongest label when none clears the SDK's threshold;
it is not an abstention or entropy policy.

Native long-text helpers perform chunking and confidence merging. No additional
character, label-count or arbitrary source-token limit is introduced. Body
limits and explicit native-input failures remain enforced.

## Errors

Every failure has exactly:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The GLiNER request is invalid.",
    "retryable": false
  }
}
```

Table B - Fixed refusal policy

| Id | Code | HTTP | Retryable | Meaning |
| --- | --- | --- | --- | --- |
| B1 | `INVALID_REQUEST` | 422 | no | Invalid body, schema, media, encoding or bounded read |
| B2 | `NOT_FOUND` | 404 | no | Unknown native route |
| B3 | `METHOD_NOT_ALLOWED` | 405 | no | Wrong method, retaining `Allow` |
| B4 | `BODY_TOO_LARGE` | 413 | no | Declared or streamed body exceeds the existing bound |
| B5 | `HOST_FORBIDDEN` | 403 | no | Host is outside the existing loopback binding |
| B6 | `ORIGIN_FORBIDDEN` | 403 | no | A browser Origin was supplied |
| B7 | `SERVICE_DISABLED` | 503 | no | Provider configuration disables inference |
| B8 | `MODEL_UNAVAILABLE` | 503 | yes | No usable prepared model |
| B9 | `INPUT_UNSUPPORTED` | 422 | no | Native input refusal, including conservative warning refusal |
| B10 | `INVALID_RESULT` | 500 | yes | Native output violates its strict result contract |
| B11 | `ANALYSIS_FAILED` | 500 | yes | Native execution failed |
| B12 | `LOGGING_FAILED` | 500 | yes | The validated diagnostic could not be delivered |

Messages come only from the fixed native policy. Input, native diagnostics
and exception text are never included. A damaged result or execution failure
makes enabled provider health fail; it never selects a fallback model.

## Health

Health contains only `enabled`, `status` and nullable fixed `error`.
Status is `loading`, `ready`, `disabled`, `failed` or `stopping`.
Only `ready` has no error and uses HTTP 200. All other states use 503.
Finding a package or cache file is not readiness; startup must load the native
model and expose both promised operations.

## Settings

`config/text-analysis/gliner/settings.json` is declared by `GlinerSettings`.
Its first shape uses the API creation date and a newest-first dated changelog.
This new family has no historical payload to migrate; current readers reject
unknown shape versions instead of trying a permissive previous reader.

Table C - Configuration ownership

| Id | Field | Rule |
| --- | --- | --- |
| C1 | `version`, `changelog` | Current dated shape, unique descending change dates |
| C2 | `enabled` | Boolean; default enabled |
| C3 | `model.repo` | Required full Hub identifier; compatible names are not enumerated |
| C4 | `model.base_url` | Required HTTPS download endpoint without credentials, query or fragment |
| C5 | `logging.level` | `INFO`, `WARNING` or `ERROR`; default `INFO` |
| C6 | `logging.max_event_bytes` | Positive event byte limit; default `4096` |

Prepare the selected assets before a fresh start. Downloads use the configured
endpoint; inference uses only local assets. There are no model revisions,
request selectors, environment destination overrides, private taxonomies,
host/port settings or permanent test-mode controls in this file.

## Events

Each stderr record is one strict CloudEvents 1.0 JSON object with lowercase
UUIDv4 `id`, source `/services/text-analysis/gliner`, UTC `time` ending in `Z`,
`application/json`, `traceparent` and optional canonical `tracestate`.

Service types are `gliner.service.started`, `gliner.service.ready`,
`gliner.service.stopped` and `gliner.service.failed`. Their data is only
`status`, `enabled` and optional fixed `error_code`.

Request types are `gliner.request.completed` and `gliner.request.failed`.
Their data is only `operation`, `status` and optional fixed `error_code`.
The terminal request carrier matches the HTTP response carrier.

No event contains source text, mentions, labels/definitions, URLs, headers,
PIDs, paths or raw exceptions. The
[native architecture](../architecture/text-analysis/gliner-api.md#fail-closed-diagnostics)
owns conservative model-warning refusal and operation isolation.

## See also

- [How the native API runs](../architecture/text-analysis/gliner-api.md)
- [Gate commands](../how-to/run-the-gates.md)
- [First-party routing](api-routing.md)
- [Taxonomy](../concepts/taxonomy.md)
- [Repository layout](repository-layout.md)
