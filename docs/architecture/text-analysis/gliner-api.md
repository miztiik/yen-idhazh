# How the native GLiNER2 API runs

**Last Updated**: 2026-11-09

How one local model turns exact source text and caller-defined labels into
validated entities or classifications without becoming an article pipeline.

## Independent provider, existing transport

`services/text_analysis/gliner/` contains the independent `gliner_api` package.
Its `create_api_component.create_app(settings, transport, root=...)` factory
returns a complete FastAPI application. `settings` is the provider's validated
configuration; `transport` is the neutral host's `HostSettings`, populated from
the existing `text_analysis.load_service_settings.load_service_settings(root)`
listener settings. The factory imports no spaCy model or feature code.

The [local API host](../local-api-host.md) supplies loopback and Origin guards,
bounded UTF-8 body reading, W3C receiving operations, native health/schema
routes and lifespan cleanup. The provider owns its router, model lifecycle,
application results, refusal bodies and CloudEvents.

`services/text_analysis/hosting/serve_apis.py` is the thin assembly: it alone
imports both native factories and the existing settings loader. It builds the
complete spaCy application, passes its public transport binding to GLiNER,
and delegates both to the neutral complete-application composer. Both API
families retain their declared paths, health payloads, native schemas and
lifespans on the same configured listener. Neither provider imports the other
or receives its model state. This assembly is a script, not another package,
configuration hierarchy or model server.

## Prepare, then load once

The one committed `config/text-analysis/gliner/settings.json` supplies a full
Hub repository identifier and HTTPS download endpoint. Preparation downloads
that configured snapshot through the Hub SDK. Startup resolves only the
prepared local cache and passes its complete local directory to
`gliner2.AutoExtractor.from_pretrained` on CPU.

Requests cannot supply a model, revision, destination or executable. Environment
variables cannot replace the configured download endpoint. No hosted inference
client receives source text. Neither source code nor the schema enumerates
compatible model names. A configuration change takes effect after preparing
its assets and starting a fresh application; there is no hot reload.

Each application retains one actually loaded model. Native calls use standard
framework thread offloading and serialize access to that instance. The tensor
runtime retains its native CPU threading; there are no worker replicas,
process pools or thread caps. Health becomes ready only after native loading
and verification of both promised operation interfaces. Missing or incompatible
assets leave an observable failed provider, not an apparently ready cache.

The runtime, not the HTTP caller, owns each completion task and model lease.
Cancelling a caller cancels only its wait: accepted native work retains the
lock until its thread finishes and its terminal diagnostic is delivered.
Completion exceptions are consumed even when the caller disappears. Native
model loading has the same owned-task protection.

Shutdown stops admission and waits for all accepted completions, diagnostics
and model ownership under one absolute existing shutdown deadline before
dropping the model. It does not cancel still-running native threads or release
their leases to obtain an apparent clean exit. A missed deadline fails the
lifespan so the external process owner can stop it.

## Native operations, strict results

NER delegates long input to the SDK's overlapping word chunks and document
offset remapping. Confidence and span inclusion are mandatory output controls.
The API validates finite native confidence, requested label membership and
exact slicing against the original Python Unicode string. It never repairs an
offset, clips source text or manufactures a prediction.

Classification passes named tasks, ID-to-definition mappings and single- or
multi-label selection directly to the SDK's schema-based operation. Native
long-text classification merges chunk selections; retained confidence is a
native chunk aggregate, not a newly calibrated document probability.
Single-label output contains at most one selection. Every returned ID must
belong to that request, and every requested task must survive normalization.

The SDK may append terminal punctuation during its own preprocessing. The
transport still passes the exact request string and validates all returned
mentions against it. Unsupported native input fails explicitly rather than
being silently truncated.

Callers build current active definitions from
[the authoritative taxonomy](../../concepts/taxonomy.md). The API owns no second
vocabulary, article assignment, rank rule, proposal ledger or novelty policy.
NER evidence is not automatic promotion into a configured registry.

## Fail-closed diagnostics

Every provider stderr record is a validated CloudEvents 1.0 envelope with the
native source and W3C carrier. Request events contain only the operation,
terminal status and fixed failure code. They contain no source, mentions,
label definitions, URLs, headers, process IDs, paths or exception text.
Operational fields never enter processing response bodies.

The native SDK can warn before substituting dummy preprocessing input. A
model-library logging handler therefore refuses WARNING and ERROR records
without reading or formatting their diagnostic text. Lower-level raw records
are discarded. An operation-local diagnostic record retains the refusal even
if native exception handling catches the first raised exception. A later
operation receives fresh state; startup controls do not accumulate handlers.
Supported progress and narrowly scoped warning controls prevent library output
from bypassing the provider's event writer without altering the root logger or
another provider's diagnostics.

The SDK already excludes a related encoder compatibility notice but does not
recognize the newer TorchScript deprecation message. Native model construction
filters only that known `FutureWarning` from the TorchScript module. The
previous warning policy is restored after loading; other messages, categories
and modules are not suppressed. Native diagnostic refusal remains unchanged.

This is deliberately conservative: a warning can refuse otherwise usable
native input. It is safer than publishing an empty success after native
preprocessing failed. Ordinary empty predictions remain valid when no native
failure occurred. Event-delivery failure is also explicit and makes enabled
provider health fail.

## Dependency cost

GLiNER2 supplies native schemas, extraction and chunk merging. The CPU tensor
runtime, transformer libraries and configured weights dominate installation
and resident-memory cost, so inference stays in the optional `model` extra.
FastAPI, Pydantic and the neutral host reuse existing transport and validation
behavior. HTTPX is also used by the external reporting caller; pytest, Ruff and
mypy support development checks.

The development group uses the sibling text-analysis package only for the
existing settings-loader binding and locked compatibility resolution. It does
not create a production dependency on that provider's model or feature logic.
The manual reporting workflow uses this one prepared development environment
for both providers and installs only its selected spaCy wheel plus the
configured GLiNER snapshot. Its caller sends one NER request for the same
source as the spaCy request, without invoking classification. The API does
not write the report or artifacts. Native manifests and locks remain
independent.

## Design rationale

Native schemas and chunking keep model behavior in its maintained SDK rather
than a second classifier or tokenizer. One cached CPU model makes ownership
and cleanup explicit without another worker protocol. Strict boundary
normalization and conservative diagnostic refusal prevent native fallback or
malformed output from looking like useful application data.

## See also

- [Exact GLiNER API contract](../../reference/gliner-api.md)
- [First-party routing](../../reference/api-routing.md)
- [Local API host](../local-api-host.md)
- [Shared API reporting](../../how-to/run-ner-api-tests.md)
- [Gate commands](../../how-to/run-the-gates.md)
- [Repository layout](../../reference/repository-layout.md)
