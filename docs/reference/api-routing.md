# First-party API routing

**Last Updated**: 2026-11-08

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
Matching is exact, including the absence of a trailing slash. Wrong methods
retain the owning handler's existing refusal; a route change does not change
method dispatch.

HTTP route dates, application payload schema dates, scoring schema dates,
package release versions and external protocol versions are separate
identities. A new URL does not change score fields, calculations,
CloudEvents `specversion`, event identity or historical recording bytes.
Each changed payload family follows its own declared compatibility rule.

## Current evaluator family

The `summary-evaluator` HTTP protocol uses the fixed date `2026-11-05`.
Its constants live in
`services/summary_evaluator/src/summary_evaluator/shared/contracts/api_paths.py`
and `unieval/unieval_router.py`. The installed distribution and import package
are `summary_evaluator`; their release date remains independent of the HTTP date.

Table A - Evaluator operations

| Id | Method | Path | Availability |
| --- | --- | --- | --- |
| A1 | POST | `/api/2026-11-05/evaluate-summary-hhem` | Only with HHEM enabled. |
| A2 | GET | `/api/2026-11-05/get-hhem-health` | Only with HHEM enabled. |
| A3 | POST | `/api/2026-11-05/evaluate-summary-unieval` | Only with UniEval enabled. |
| A4 | GET | `/api/2026-11-05/get-unieval-health` | Only with UniEval enabled. |
| A5 | GET | `/api/2026-11-05/get-summary-evaluator-health` | Always registered; HTTP 200 requires every enabled scorer to be ready. |
| A6 | GET | `/api/2026-11-05/get-summary-evaluator-schema` | Always registered; no interactive documentation UI. |

The application schemas are `2026-11-07`, HHEM's scoring
schema remains `2026-11-02`, and native UniEval's scoring schema remains `2026-11-04`.
Coverage operations and selection are retired without aliases or scorer
fallbacks; their HTTP paths use the normal unknown-route refusal.
The [application reference](summary-evaluator-api.md) owns strict live
validation, narrow previous-shape readers, local refusals and listener settings.

## Current generator family

The independent generator uses the same fixed HTTP date, `2026-11-05`.
Its constants live in `services/summary-generator/src/api/api-paths.ts`.
Its payload date is separately `2026-11-06`.

Table B - Generator operations

| Id | Method | Path | Availability |
| --- | --- | --- | --- |
| B1 | POST | `/api/2026-11-05/generate-summary` | Prepared text and an optional complete system-prompt override. |
| B2 | GET | `/api/2026-11-05/get-summary-generator-health` | Process/configuration availability, without machine or model-readiness claims. |

The former `/api/summarize`, `/health` and `/api/diagnostics` operations are
removed, not redirected. The [generator reference](summary-generator-api.md)
owns input/result validation, safe refusals and its independent listener.

## Current host and shared family

The host operations and shared process health use the fixed HTTP date
`2026-11-05`. Their existing exported constants remain the caller authority in
`services/host-fingerprints/src/api/server.ts`,
`services/host-probes/src/api/server.ts` and
`services/serve-pipeline-apis/src/declare-api-identity.ts` (re-exported by
`api-startup.ts`). Shared hosting mounts the
same native handlers; it does not wrap their payloads or select another module
from a request.

Table C - Host and shared operations

| Id | Method | Path | Meaning |
| --- | --- | --- | --- |
| C1 | POST | `/api/2026-11-05/capture-host-fingerprint` | Capture and persist the native hardware row, or return the configured disabled result. |
| C2 | GET | `/api/2026-11-05/get-host-fingerprint-health` | Read the fingerprint instrument's enablement without capture or writes. |
| C3 | GET | `/api/2026-11-05/sample-host` | One native CPU/RAM sampling interval. |
| C4 | POST | `/api/2026-11-05/start-task-profile` | Start a profile for the supplied PID and kernel start ticks. |
| C5 | POST | `/api/2026-11-05/stop-task-profile` | Close or read the retained result for its genuine profile handle. |
| C6 | POST | `/api/2026-11-05/measure-cache-latency` | Run the configured optional cache instrument, without a task handle. |
| C7 | GET | `/api/2026-11-05/get-api-health` | Read the exact shared process identity, not a native module's readiness. |

The old host operations and unversioned shared `/health` return HTTP 404,
without aliases or redirects. Native host operations retain HTTP 405 and
`Allow` for wrong methods. Shared health retains its existing POST fallback
to native dispatch, which returns HTTP 404 rather than process identity.
The HTTP date does not restamp hardware, task-profile, cache or event schemas,
change measurements or rewrite recordings. Planner and delivery operations
remain separate native route families.

Shared readiness still compares the private nonce, spawned PID, configured
port, group, modules and enablement with the uncached HTTP identity, then runs
the selected module's additional native checks. Each process advertises only
its selected module; machine operations remain one group on their configured
listener and are absent from planning. Its
[listener reference](serve-pipeline-apis.md) owns lifetime and cleanup.
The [hardware reference](host-metrics.md), [profile reference](host-probe-api.md)
and [cache reference](host-cache-probes.md) own measurements and payloads.

## Current planner and delivery family

Planning and delivery reuse the fixed `PLANNER_API_PREFIX`, `/api/2026-11-07`,
from `packages/common-contracts/src/version.ts`. Their named suffix maps,
`PLANNER_API_PATHS` and `DELIVERY_API_PATHS`, live in
`packages/common-contracts/src/declare-feed-api-paths.ts`.
Routers mount suffixes beneath the prefix; callers append the prefix and suffix
once. These are protocol constants, not a runtime date or destination registry.

Table D - Planner and delivery operations

| Id | Method | Path | Native work |
| --- | --- | --- | --- |
| D1 | GET | `/api/2026-11-07/get-feed-planner-health` | Planner availability and captured native identity. |
| D2 | POST | `/api/2026-11-07/plan-feed-ingestion` | Complete planning, report capture and collection release. |
| D3 | POST | `/api/2026-11-07/fetch-document` | Bounded acquisition with explicit byte-cutoff evidence. |
| D4 | POST | `/api/2026-11-07/parse-document` | Consume one held fetch and report prepared article word limits. |
| D5 | POST | `/api/2026-11-07/start-feed-collection` | Capture one collection's execution and inputs. |
| D6 | POST | `/api/2026-11-07/check-feed-collection` | Inspect an ambiguous startup outcome without granting ownership. |
| D7 | POST | `/api/2026-11-07/complete-feed-collection` | Settle required work and expose its completed parsed result. |
| D8 | POST | `/api/2026-11-07/cancel-feed-collection` | Abort and drain owned work while retaining completed partial evidence. |
| D9 | POST | `/api/2026-11-07/finalize-feed-collection` | Capture settled status, failures and timings without releasing references. |
| D10 | POST | `/api/2026-11-07/release-feed-collection` | Release finalized execution state after dependent reads. |
| D11 | POST | `/api/2026-11-07/update-feed-health` | Record or summarize the current operation's health. |
| D12 | POST | `/api/2026-11-07/select-articles` | Select completed input; the existing suffix is unchanged. |
| D13 | POST | `/api/2026-11-07/partition-articles` | Assign selected work; the existing suffix is unchanged. |
| D14 | POST | `/api/2026-11-07/persist-selected-articles` | Write selected metadata and text; the existing suffix is unchanged. |
| D15 | GET | `/api/2026-11-07/get-data-delivery-health` | Captured native delivery identity, independent of planner health. |
| D16 | POST | `/api/2026-11-07/persist-data` | Existing verified metadata adapter and atomic safe delivery. |

The required nullable `body_limit` and article `word_limit` response fields use
this current route family. Previous dated routes return HTTP 404; current
writers and clients validate the fields explicitly, without response defaults.

The former suffixes `health`, `plan`, `fetch`, `parse`, `collections` and its
`exists`, `complete`, `cancel`, `finalize` and `release` children,
`feed-health-state` and `safe-persist-data` return HTTP 404.
GET on POST-only operations and POST on native health retain HTTP 404.
Hono's existing HEAD handling for health is unchanged.
Planning and delivery do not mount one another's native health operation.
The native readiness reader selects health by startup group after the separate
shared process check; captured nonce, PID, port, group, module enablement and
planner execution controls still have to match.

HTTP names do not change saved `safe_persist_data`, the `feed-health-state`
ledger, failure-operation values, schema dates, receipts or recording bytes.
The [operator API reference](../architecture/sources/feed-operator-api.md)
owns document/reference lifetime, collection order, failure retention and
delivery validation. The
[runner reference](../architecture/sources/feed-plan-runner.md)
owns the real stage HTTP composition and its supervised clients.

## Current text-analysis family

The independent Python text-analysis service uses the fixed HTTP date
`2026-11-07`. Its constants live in
`services/text_analysis/src/text_analysis/declare_api_contracts.py`.

Table E - Text-analysis operations

| Id | Method | Path | Meaning |
| --- | --- | --- | --- |
| E1 | POST | `/api/2026-11-07/analyze-text` | Extract the selected ordered linguistic features. |
| E2 | GET | `/api/2026-11-07/get-text-analysis-health` | Read configured capacity and language/profile/feature capabilities without loading a model. |
| E3 | GET | `/api/2026-11-07/get-text-analysis-schema` | Read the current OpenAPI document without an interactive UI. |

The application and settings schema date is `2026-11-07`. The package release,
spaCy version and model versions are separate identities. Unknown and previous
paths return 404 without aliases. Wrong methods retain `Allow`.
The [text-analysis reference](text-analysis-api.md) owns request, result,
feature-error, health and event fields.

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

- [summary-evaluator-api.md](summary-evaluator-api.md) - evaluator listener and live application contract.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - HHEM scoring contract.
- [unieval-api.md](unieval-api.md) - native UniEval scoring contract.
- [summary-evaluation-workflow.md](summary-evaluation-workflow.md) - direct native generation and evaluator clients.
- [summary-generator-api.md](summary-generator-api.md) - prepared-text generation and its independent listener.
- [serve-pipeline-apis.md](serve-pipeline-apis.md) - shared process identity and owned-child lifetime.
- [feed-operator-api.md](../architecture/sources/feed-operator-api.md) - planner and delivery operations and native control flow.
- [text-analysis-api.md](text-analysis-api.md) - multilingual extraction routes and payloads.
