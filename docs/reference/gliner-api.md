# Native GLiNER2 API reference

**Last Updated**: 2026-11-10

The exact routes, payloads, settings and safe diagnostic vocabulary of the
independent local GLiNER2 provider.

## Routes

The fixed creation-date family is `/api/2026-11-08`, declared once as
`API_VERSION` in `gliner_api.declare_api_contracts`. It does not follow the
request clock, model identity or package release.

Table A - Native operations

| Id | Method | Path | Result |
| --- | --- | --- | --- |
| A1 | POST | `/api/2026-11-08/analyze-text-gliner` | Request-validated native extraction JSON |
| A2 | GET | `/api/2026-11-08/get-gliner-health` | Genuine provider availability |
| A3 | GET | `/api/2026-11-08/get-gliner-schema` | Native OpenAPI, without an interactive UI |

Matching is exact. Unknown and trailing-slash paths return 404; wrong methods
return 405 with `Allow`. The existing text-analysis settings supply the
listener, body byte limit, absolute read deadline and shutdown deadline.
Host and Origin guards run before body reading. Every response receives the
host's W3C carrier rather than trace fields in its JSON body.

## Requests and results

All live objects reject undeclared fields and coercion. Text is nonblank valid
UTF-8 and is preserved exactly.

Analysis requests require `text` and `schema`, with independent optional
`include_confidence` and `include_spans` booleans. Both default to false and
reject coercion. `schema` uses the pinned
GLiNER2 `SchemaInput` object grammar, not JSON Schema, chat messages or a field
string shorthand. Its optional sections are `entities`, `classifications`,
`structures`, `relations` and `entity_attributes`; at least one extraction or
classification section is required. The native schema owns their options.

```json
{
  "text": "Mira bought a bicycle in Paris.",
  "include_confidence": true,
  "include_spans": true,
  "schema": {
    "entities": ["person", "location"],
    "classifications": [
      {"task": "category", "labels": ["purchase", "other"], "multi_label": false}
    ],
    "structures": {
      "purchase": {
        "fields": [
          {"name": "buyer", "dtype": "str"},
          {"name": "item", "dtype": "str"},
          {"name": "place", "dtype": "str"}
        ]
      }
    }
  }
}
```

Entity and relation types accept native ordered lists or mappings with
descriptions/configuration. Classifications accept ordered task definitions
with list labels or ID-to-definition mappings. Label offerings are nonempty,
distinct and nonblank; mapped definitions are also nonblank. A singleton
offering is valid, using the SDK's public classification builder rather than
its stricter JSON label minimum. Classification task names, structure names
and relation names cannot overlap or use the reserved native output keys
`entities` and `relation_extraction`. Record field names cannot repeat.
Structures using a native record mode also reject `confidence`, `label` and
`text` as field names: native formatting treats these as metadata and could
overwrite or discard a record. Ordinary structures keep their existing field
grammar. Record-mode requests require the loaded model's native record
capability; accepting a schema alone does not establish that capability.
Event roles are caller-defined record fields, not a service vocabulary.

Successful responses have exactly `result`, containing the native JSON
object. Entity output is a type-to-mention mapping under `entities`;
classifications use their task names at the root and native
`{label, confidence}` selections or lists; structures use root record lists;
relations group native `head`/`tail` span pairs under `relation_extraction`.
Native scalar, list and nullable fields retain their representation.
Choice fields contain distinct offered selections, which need not occur in the source.

With both controls false, native leaves are text; confidence alone adds a
score object, spans alone adds source positions, and both retain rich leaves.
Classification follows its native label/string or scored-label representation.
Entity attributes remain attached, including their native selection metadata.
Record-level and boundary-relation aggregate `confidence` can remain even
when leaf confidence is disabled. The API preserves these scores separately;
`include_confidence=false` does not mean every score is removed.
Every present confidence must be finite in `[0, 1]`.
Span `start` and `end` are zero-based, half-open
Python Unicode code-point offsets whose original source slice equals `text`.
Without offsets, source-backed text must still occur verbatim in the input;
this membership check does not assign a position or constrain offered choices.
Returned task names, label IDs, record fields, choices, entity attributes and
relations must belong to the request. Missing required tasks, invalid
cardinality, duplicate selections and damaged spans fail explicitly.
Successful native record-mode decoding may omit an empty structure root;
it stays omitted, without an inserted array. Other task roots remain required.
Duplicate and exclusive occurrence checks use native offsets when present.
Repeated compact text remains separate evidence when positions are absent.
The API does not repair or manufacture evidence. Valid empty native
collections remain empty.

The direct SDK `extract_long` operation owns overlapping chunks, global
offsets and confidence merging. Single-label classification has at most one
selection; multi-label chunk selections can retain the strongest label below
the native threshold. Scores are not calibrated document probabilities or
an abstention guarantee. No extra source, label-count or token cap is added
beyond the existing body bound and native input refusals.

Analysis payload metadata and the current settings shape are `2026-11-10`;
the route family and unchanged payload families retain their dates. No
wire-version field is added. Saved reporting evidence is read by its declared
request fields and complete leaf shape, never rewritten or retried as an
older shape after current validation fails.

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
model and expose direct long-text analysis.

## Settings

`config/text-analysis/gliner/settings.json` is declared by `GlinerSettings`.
The settings-shape date is independent of the route date. The exact
`2026-11-08` shape remains readable with its former native entity cutoff
of `0.5` and loaded-architecture overlap default. It cannot contain current
control fields. Current files use the new dated shape; unknown dates,
unknown keys and malformed current values fail without a previous-reader
fallback. Saved settings bytes are never rewritten.

Table C - Configuration ownership

| Id | Field | Rule |
| --- | --- | --- |
| C1 | `version`, `changelog` | Current dated shape, unique descending change dates |
| C2 | `enabled` | Boolean; default enabled |
| C3 | `model.repo` | Required full Hub identifier; compatible names are not enumerated |
| C4 | `model.base_url` | Required HTTPS download endpoint without credentials, query or fragment |
| C5 | `logging.level` | `INFO`, `WARNING` or `ERROR`; default `INFO` |
| C6 | `logging.max_event_bytes` | Positive event byte limit; default `4096` |
| C7 | `entity_confidence_threshold` | Strict finite number in inclusive `[0, 1]`; default `0.8`, applied only through native per-entity configuration |
| C8 | `overlap_policy` | `disallow` by default; `flat` aliases it and `allow` retains overlaps |

Absent or null per-label entity thresholds use the configured default.
Explicit thresholds override it, including zero. Descriptions, dtype and
offering order are retained; the shared native extraction threshold and
classification settings are unchanged. There is no cleanup pass. Native
overlap selection operates within each entity type, not across types.

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
