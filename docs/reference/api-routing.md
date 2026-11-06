# First-party API routing

**Last Updated**: 2026-11-06

How this repository names HTTP operations and distinguishes them from an
upstream native protocol. Each API's native contracts own its payloads;
this page owns the shared route convention.

## Dated verb-noun operations

Every first-party operation uses `/api/{YYYY-MM-DD}/{verb-noun-operation}`.
The date is a declared protocol constant, never the request date or a value
computed from the clock. Operation names are lowercase, hyphen-separated and
start with a verb: `evaluate-summary-hhem`, `get-hhem-health` and
`get-summary-evaluator-schema` are examples. Health and schema operations
follow the same convention; framework defaults are not exceptions.

A breaking HTTP change advances the affected route family. Its writers,
real clients, readiness probes, OpenAPI and tests switch together.
Retired paths return HTTP 404, without permanent aliases or redirects.
Matching is exact, including the absence of a trailing slash. A wrong method
on an existing path retains the framework's HTTP 405 refusal.

HTTP route dates, application payload schema dates, scoring schema dates,
package release versions and external protocol versions are separate
identities. A new URL does not change score fields, calculations,
CloudEvents `specversion`, event identity or historical recording bytes.
Each changed payload family follows its own declared compatibility rule.

## Current evaluator family

The `summary-evaluator` HTTP protocol uses the fixed date `2026-11-05`.
Its constants live in
`services/hhem-evaluator/src/hhem_evaluator/contracts/base.py` and
`unieval_router.py`. The distribution and import package retain their current
HHEM names independently of the API title.

Table A - Evaluator operations

| Id | Method | Path | Availability |
| --- | --- | --- | --- |
| A1 | POST | `/api/2026-11-05/evaluate-summary-hhem` | Only with HHEM enabled. |
| A2 | GET | `/api/2026-11-05/get-hhem-health` | Only with HHEM enabled. |
| A3 | POST | `/api/2026-11-05/evaluate-summary-unieval` | Only with UniEval enabled. |
| A4 | GET | `/api/2026-11-05/get-unieval-health` | Only with UniEval enabled. |
| A5 | GET | `/api/2026-11-05/get-summary-evaluator-health` | Always registered; HTTP 200 requires every enabled scorer to be ready. |
| A6 | GET | `/api/2026-11-05/get-summary-evaluator-schema` | Always registered; no interactive documentation UI. |

The application schema is `2026-11-06`, HHEM's scoring schema remains
`2026-11-02`, and native UniEval's scoring schema remains `2026-11-04`.
The [application reference](fastapi-server.md) owns current-only validation,
local refusals and listener settings.

## Upstream native-protocol exception

The existing llama-server owns `/v1/chat/completions`, `/completions`,
`/apply-template`, `/props`, `/health`, `/metrics`, `/tokenize` and `/v1/models`.
These paths implement its external native protocol, not a first-party route
family. Callers use the native server directly at the committed
`model_server.base_url`; they do not add evaluator aliases or translate these
paths into repository-dated operations.

The exception does not apply to a first-party wrapper or to framework default
routes. Any other first-party deviation requires a routing decision before
implementation.

## See also

- [fastapi-server.md](fastapi-server.md) - evaluator listener and live application contract.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - HHEM scoring contract.
- [unieval-api.md](unieval-api.md) - native UniEval scoring contract.
- [summary-evaluation-workflow.md](summary-evaluation-workflow.md) - direct native generation and evaluator clients.
