# How multilingual text analysis runs

**Last Updated**: 2026-11-08

How one independently started local service turns validated English or Chinese
text into selected linguistic evidence without persisting source text or
coupling the runtime to a pipeline.

## One service, one bounded listener

`services/text_analysis/spacy/` is an installable Python package composed through
the neutral [`local_api_host`](../local-api-host.md). It owns the dated
text-analysis routes, settings, health, errors, feature extraction, process
pool and CloudEvents data. The host owns the guarded loopback listener,
bounded body reader, trace middleware, OpenAPI route and lifespan ordering.

The service reads the one committed
`config/text-analysis/settings.json`. A request may select only a declared
language, profile and ordered feature list. It cannot supply a package, URL,
path, executable or model destination.

The API writes no result, event or source file. Results leave through HTTP and
validated CloudEvents leave through stderr. The manual workflow may redirect
those streams into its runner-owned evidence directory.

The workflow owns that persisted evidence contract. Its receipt records only
the immutable run identity, conclusion and semantic cleanup. The exact
validated request, ready health response and selected analysis response stay in
three separate native payload files. Trace correlation and lifecycle metadata
stay only in the bounded `events.jsonl` stream.

## Admission precedes executor submission

The parent process owns one event-loop `CapacityLimiter` and one
`ProcessPoolExecutor`. Both use `max_concurrent_requests`, initially two.

For each valid enabled request, the parent:

1. creates a unique limiter lease;
2. acquires it without waiting;
3. submits the strict command immediately;
4. inserts the active record without an intervening await; and
5. awaits the wrapped future through a shielded completion task.

A missing token returns `429 BUSY`; no executor backlog or service queue is
created. The lease is released only after the process future finishes.
Accepted work may finish after its HTTP caller disconnects.

The pool uses the `spawn` multiprocessing context. It has no initializer,
private worker inspection, replacement generation or custom queue protocol.
`BrokenProcessPool`, executor transport failure and an invalid worker outcome
latch health to `failed` and stop admission. The pool is not repaired.

## Each process owns one lazy model

Each executor process holds at most one `(language, profile)` spaCy model.
Matching work reuses it and reports zero model-load time. A different key
releases the previous model before loading the new one.

Startup verifies the configured spaCy distribution without loading model
weights. The selected model is loaded only inside an executor process. Its
installed package version, model metadata and language must match the committed
settings. Missing or incompatible model identity returns request-level
`MODEL_UNAVAILABLE`.

English and Chinese expose `sm`, `md` and `lg`; `md` is the configured default.
Chinese does not declare noun-phrase support. Tamil remains a valid request
language but is disabled, so it returns `LANGUAGE_UNAVAILABLE` before profile
resolution or executor admission.

## Feature failures stay local

The process runs the selected spaCy document analysis once, then evaluates
features in request order. Completed siblings survive an isolated feature
post-processing failure:

- a missing model capability produces feature-level `FEATURE_UNAVAILABLE`;
- an isolated extractor/post-processing exception produces feature-level
  `FEATURE_FAILED`;
- shared document analysis, worker outcome or executor failure produces
  request-level `ANALYSIS_FAILED`.

One completed sibling makes the result `partial` with HTTP 200. If every
requested feature fails locally, the result is `failed` with HTTP 422. Neither
feature-level code changes service health. Request-level executor or process
failure does.

Every returned span carries exact source text and zero-based half-open Python
code-point offsets. The verification probe converts the original source once
per response and uses the same code-point array for every occurrence check.

## Compact English outputs reuse the document

Named Entities groups native mentions by configured case normalization and
mapped presentation type. It preserves the first source spelling and every
source-ordered occurrence; labels outside the mapping remain available in raw
entities. These presentation types are not a classification taxonomy.

Important Terms runs YAKE's native candidate generation, statistical feature
calculations and configured deduplication metric. `PhraseMatcher` anchors the
ranked token patterns in the original spaCy document, with pattern documents
made by the tokenizer rather than another model invocation. Matching phrases
are deduplicated before the final configured limit; ties use first source
position. An unanchored selected phrase fails only Important Terms. Empty
candidates and a zero maximum produce successful empty lists.

The executor passes the freshly validated feature settings into extraction;
they do not live in the spaCy model cache. English's optional default override
selects these outputs, while an omitted override inherits global defaults.
Chinese's raw features, default order and model behavior remain unchanged.

## Relations are configured dependency evidence

Relation extraction visits source-ordered `VERB` and `AUX` actions. It collects
configured actor and object dependency subtrees, follows recursive conjunctions,
treats passive subjects as objects, and attaches configured time and place
entities from the same sentence. Duplicate spans collapse by offsets. An action
without an explicit actor produces no relation.

This is sentence-local syntactic evidence. It does not resolve pronouns,
implied subjects, semantic roles or cross-sentence relations.

## Lifecycle, tracing and privacy

Trace propagation is enabled only for this service. Each request receives a
fresh API span inside the accepted W3C trace, and every response carries that
operation. The request's terminal event uses the exact same carrier. Health and
schema requests emit no request event.

Service lifecycle and request diagnostics use the shared CloudEvents 1.0
envelope with source `/services/text-analysis`. Event data contains only safe
identity, feature-status, capacity, timing and fixed error-code fields. It
contains no request text, returned evidence, model URL, header, process ID,
path or exception. Executor processes discard third-party stdout/stderr so
model-library output cannot bypass the validated parent event writer.

A diagnostic delivery failure does not replace completed feature data or add a
public API code. It latches service health to `failed`; later requests are not
admitted.

Shutdown disables admission, best-effort cancels unstarted futures and runs
`executor.shutdown(wait=True, cancel_futures=True)` in a thread. Pool shutdown
and completion-task joining share one absolute configured deadline. The host
emits `stopped` only after confirmed pool exit. A timeout or cleanup failure
fails the lifespan so the external owner can terminate the exact process group.

## Dependency boundary

spaCy supplies the maintained tokenization, tagging, dependency parsing,
entities and model package interface; the selected model wheel is the dominant
download and resident-memory cost. The manual workflow therefore installs one
selected profile, while production preparation may install all enabled
profiles. AnyIO supplies immediate capacity admission without a custom queue.
HTTPX is verification-only. The service adds no Torch or transformer runtime.
YAKE supplies English article phrase ranking. Its Python package and transitive
statistical/tokenization dependencies add installation bytes and time, but no
model download or published JavaScript. The manifest and frozen lock own that
cost; no additional extraction dependency is introduced.

## Design rationale

Standard executor processes already supply the required CPU isolation and
concurrency. A custom worker protocol, queue or automatic repair would add
ownership, cancellation and recovery states without serving the initial
two-request contract.

Keeping the implementation's manifest, environment and verification tools
together leaves the parent directory available for other implementations
without sharing a project. Physical project location does not change the
Python package name, HTTP family or committed settings location.

Selectable features keep expensive or verbose data caller-controlled, while
feature-local errors preserve useful siblings. Keeping timings out of HTTP
results prevents diagnostic state from becoming application data; the traced
event remains the one operational record.

YAKE's convenience method turns calculation exceptions into an empty list.
This service invokes the library's native statistical stages directly so
calculation failures reach `FEATURE_FAILED` instead of looking like successful
no-candidate output. Candidate generation, scoring and similarity remain
library-owned; the service owns source evidence and its public result limit.

Live validation remains strict even as old evidence stays readable. A separate
retained reader recognizes the initial health shape, preserving recorded global
defaults and unknown limits without modifying files. Missing new settings
options use native defaults but never replace a historical feature selection.

## See also

- [Text-analysis API reference](../../reference/text-analysis-api.md)
- [First-party API routing](../../reference/api-routing.md)
- [Run the text-analysis verification](../../how-to/run-spacy-tests.md)
- [Contracts and schemas](../contracts/schemas.md)
- [Repository layout](../../reference/repository-layout.md)
