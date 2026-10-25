# Feed and article failure diagnostics

**Last Updated**: 2026-10-25

Which operation failed, what evidence survives it, and which durations were
actually measured? This is the isolated TypeScript planner's diagnostic
contract, not a claim of complete parity with production Python extraction.
[Harvesting](feed-harvesting.md) owns the request and extraction controls.

## One observation through every boundary

`HarvestDiagnostics` is declared in
`backend/idhazh/contracts/feed_ingest_diagnostics.py`; its strict TypeScript
copy lives in `packages/common-contracts/src/schemas/harvest-diagnostics.schema.ts`.
The existing recursive contract binding compares the nested shape,
nullability, defaults and vocabularies. There is no Python process in the
planner or its native tests.

One diagnostic object travels through the article observation, rejection
`details.diagnostics`, article assessment and typed decision event. Feed
outcomes carry the same object as their feed rejection. Live completion and
rejection events also carry `diagnostics`. Curation keeps the original
measurement rather than measuring harvesting again.
Screening and curation rejections retain the same original diagnostic object,
including successful fetch and extraction measurements before a later refusal.

Table A

| Id | Field | Meaning |
| --- | --- | --- |
| A1 | `http_status` | Last received target HTTP status, including a redirect or headers received before body failure. Null if no target responded. Never the robots-file status. |
| A2 | `robots` | Permission for the checked target: allowed, denied or unknown. Null before permission was checked, including an unsafe redirect destination. |
| A3 | `fetch_failure` | Exact terminal fetch cause: HTTP, timeout, unsafe target, DNS, network, robots denied, robots unknown, body size or redirect cycle. |
| A4 | `robots_failure`, `robots_http_status` | The cached robots lookup's cause and last HTTP status. These distinguish a denied rule from an unreachable or unsafe robots document without inventing a target response. |
| A5 | `error_code` | An available OS, TLS or Undici error token. The wire format admits only uppercase letters, digits and underscores, up to 64 characters. No exception message, URL, header or local path is copied. |
| A6 | `extraction_failure` | Missing document root, DOM depth overflow, empty extracted content or missing title. Successful body extraction with no title remains distinguishable from empty text. |
| A7 | `failure_code` | The existing Python item-health vocabulary where meanings match, including the selected measured extraction signal. A signal on a successful extraction is not itself a terminal refusal. Unmatched conditions use `unknown`, with their exact typed `detail`, rather than pretending to be a network failure. |
| A8 | `stopped_stage`, `detail` | The failed operation (`fetch`, `extract` or feed `parse`) and its fixed cause token. Feed parsing distinguishes malformed input from a successfully parsed empty feed. No fetched prose reaches this field. |
| A9 | `fetch_ms` | Measured milliseconds around that item's complete permitted fetch, including DNS, robots lookup or cache wait, retries, backoff, redirects and body reading. |
| A10 | `extract_ms` | Measured milliseconds around the synchronous article extractor, including typed failures. Null if extraction was not attempted. |
| A11 | `warnings` | A bounded set of warning kinds. Currently `malformed-json-ld` identifies invalid publisher metadata without declaring the article failed. |
| A12 | `quality` | Measured source/body words, independent publisher length, native shape signals, configured consequence and actual implementation fingerprints. Null before extraction or on historical rows. [Extraction quality](extraction-quality.md) owns each meaning and its unavailable readings. |

Null means unavailable or unperformed; zero milliseconds means a real
measurement rounded below one millisecond. Inactive feeds, invalid entry
identity and pre-download age refusals have null diagnostics, not zero fetch
and extraction times. Feed parsing retains its separately measured
`parse_duration_ms` on the feed outcome.

Existing rejection `details.http_status` and article observation status cells
are projections of the same fetch result, not independent requests.
`EXTRACT_FAILED` identifies typed extractor errors; `EXTRACT_EMPTY` identifies
empty text. Missing title alone retains `MISSING_REQUIRED_FIELDS`. An absent
feed title cannot override a real fetch failure's diagnostic cause.
The `network_error` production category covers DNS and deadline failures;
`fetch_failure` and `error_code` retain the narrower cause. Exact HTTP codes
remain intact: HTTP 404 means not found, 429 means rate limited, and 503 means
service unavailable.

## Clocks and warnings

Live `durationMs` is nullable. Feed and article completion records measure
their own enclosing operation. An event without an operation measurement
carries null; it never borrows the time since another worker's event.
`elapsedMs` is time since the run's progress logger started.

Audit `step_elapsed_ms` remains elapsed wall time since the stage began, not
an individual article's duration. The JSONL envelope exposes it as
`stepElapsedMs`. Its `durationMs` is the stage's elapsed time only for a stage
completion; feed and harvest-decision durations use the recorded operation
measurements. Later decisions do not claim to have timed harvesting again.

The existing JSON-LD parser removes malformed script nodes from its parsed
document before Defuddle runs, and records a malformed-metadata warning without
copying publisher input. Valid JSON-LD remains available to the project parser
and Defuddle. A completed article emits
`ARTICLE_EXTRACTION_WARNING` at `WARN` with source and candidate identity,
and retains the warning in its diagnostic object even if extraction succeeds.
Defuddle 0.19.5 has no supported logger callback. This change neither replaces
its parser nor patches or suppresses the global console; removing malformed
scripts prevents its parser from retrying and logging them. Its debug option
stays off.

Undici's decompression interceptor remains experimental. That warning concerns
dependency stability, not an article failure. The mature built-in zlib codecs
alone are not an equivalent replacement for the interceptor's HTTP content
encoding and stream lifecycle handling; this phase does not redesign transport
or weaken decoded byte limits, abort handling or address pinning.

## Historical records

Rejections, article assessments and planner events advance to `2026-10-23`;
source-run vocabulary and its stamp are unchanged. Python ledger declarations carry their
changelog entries; TypeScript owns the event changelog.
Earlier rejection and assessment rows without diagnostics migrate with null
diagnostics; existing historical diagnostics gain null quality. Nothing
reconstructs a missing HTTP status, error token or duration from a broad old
rejection reason. The existing publication-time migration is unchanged.
Source-run predecessors retain their counts and recorded completion proof.

The native Parquet reader validates old files against their original column
shape and physical digest before migrating them. Logical record commitments
also use the original shape and stamp. A current row with actual new
diagnostics cannot be encoded as an old proof that would discard them.
Historical event reads validate the old envelope and nested payload before
upgrading the stamps and applying null defaults.

## Remaining production differences

No granular DNS, connect, TLS, first-byte, body, robots or retry timing is
reported separately. The current transport supplies no such measurements;
the complete fetch duration must not be divided into invented socket phases.
Intermediate retry error history is not retained; the terminal cause and last
received status are retained.

The [quality contract](extraction-quality.md) records the remaining extractor
differences, missing sibling-host measurement and worker-owned token/cap
measurements. Recording a shape signal and rejecting an article for it remain
different behaviors. This change does not alter ranking, workers or production
cutover.

## Operation failure attribution

Each failed fetch, parse or request-attempt observation keeps its existing
`failure_code` and records whether the evidence belongs to the source, the
pipeline or remains unresolved. This describes the observed operation; it
does not diagnose intent, prove a paywall or blame a publisher-wide problem.

**Table A**

| Id | Evidence | Attribution |
| --- | --- | --- |
| A1 | A fetch or dispatched target attempt reports typed `http` failure with HTTP 401, 403, 404 or 410; or its robots rule denies the request | `source` |
| A2 | Article extraction reports typed `empty-content`; a feed parser reports its typed `malformed-feed` failure | `source` |
| A3 | Local target validation rejects an unsafe address, the configured body limit stops a response, or the extractor reports its depth limit | `pipeline` |
| A4 | Other HTTP failures (including 408 and 429), DNS, network, timeout, redirect-loop, missing document root/title or any untyped exception | `unresolved` |

HTTP 403 is an observed refusal for that article request only. It is not proof
that the article is paywalled or that the publisher has failed generally.
The selected HTTP codes mean access was refused or the target was absent;
they do not identify why. Other client-error codes do not establish source
responsibility. A missing root or title can be an extractor fault, so it does
not establish source responsibility either. The existing `empty-content`
outcome establishes failed technical extraction only, not poor editorial
quality. No new word-count, suitability or semantic test supplies attribution.
Retries keep separate attempt rows and their own request counts. Their shared
fetch event identifies one article operation; counting article opportunities
must not count each retry as another article.

A successful article parse has no failure attribution. The later
`ArticleAssessment.extraction_outcome` reports `success` only when extraction
produced measured words, `failed` for a failed or empty extraction,
`not_attempted` when extraction did not run, and `unavailable` otherwise. A
model failure after usable extraction does not change that extraction result
or make the source responsible.

## Design rationale

Owner direction (kumarsnaveen, 2026-10-22): improve failure detail and remove
technical debt rather than preserve an inferior consumer interface.
One typed diagnostic object replaces loss-prone partial mappings. Separate
extraction rejection reasons remove the false claim that a successful HTTP
fetch failed. Native validation adapts existing cases and recordings only;
no test cases, Python runtime dependency or test tooling are added.
The Python failure-category subset uses string literals so the native Arrow
writer can derive its column type without broadening the accepted vocabulary.

The page is separate because harvesting owns request behavior while this page
owns the evidence that crosses its boundaries.
