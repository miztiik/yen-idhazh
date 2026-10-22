# Isolated feed harvesting

**Last Updated**: 2026-10-21

How the TypeScript planner turns configured RSS/Atom entries into sanitized
article candidates and records refusals. This path is separate from production
discovery and extraction. It does not change production scheduling or workers.
The [trust boundary](trust-boundary.md) owns address, robots and text controls.

## Public entry

`@idhazh/feed-ingest-plan/harvest-feeds` exports `loadHarvestInputs`,
`readHarvestInputs` and `harvestFeeds`. Load the authored planner configuration,
taxonomy, sources and extraction settings before starting a run. File paths
are explicit inputs; loading does not search directories.

`harvestFeeds(inputs, context, destination, boundary?)` takes the validated
inputs, writer identity, correlation identity and rejection destination.
`boundary` supplies the transport and address resolver for recorded replay;
ordinary callers omit it to use Undici and the operating system resolver.
The transport imports the installed `undici/index.js` request API explicitly.
Bun's bare shim lacks a real dispatcher; the installed fetch adapter also
fails on live response streams with an `isAborted` error and can stop servicing
deadline timers. The request API avoids that adapter. Its supplied decompression
interceptor handles compressed bodies before the decoded byte cap; it is marked
experimental by Undici and adds no dependency. Validated socket DNS remains
pinned, redirects remain manual, and a per-request dispatcher is destroyed
after success or refusal rather than waiting for graceful draining.
Offline tests consume actual recorded-body streams, check decoded byte limits
and aborted-stream destruction, and open/close the real dispatcher without a
socket. Live verification is separate and externally supervised.
The destination takes the registered rejection prefix and ledger settings,
not a second path policy. Rejections are actual Parquet through
`@idhazh/ledger-file-writer`. A failed write rejects the operation. A paused
or retired rejection registration also refuses completion when rows need to
be written; an empty rejection set needs no file.

The result contains `candidates`, `rejections`, `rejection_files`, the validated
`inputs` and `config`, `feed_outcomes`, and `articles`. Each `articles` element has exactly one
candidate or rejection, plus its `observation`. `HarvestObservationSchema`,
`HarvestArticleResultSchema` and their types are public exports.

An observation has `candidate_id`, `http_status`, `robots`, `fetch_failure`,
`paywall`, `paywall_evidence`, `extraction` and `observed_at`.
HTTP status is the actual target response, or null when no target responded.
Paywall is a boolean only after HTML was read, otherwise null. Its evidence
names publisher JSON-LD, a configured marker, no match, or not observed.
Robots is allowed, denied, unknown, or null before permission was established.
Extraction is success, empty, failed, or not attempted. The observation is
transient serializable data, not an added persisted candidate field.

Build a screening observation record by selecting the successful `articles`
and indexing their complete observations by `candidate_id`. Rejected entries
also have observations, but do not belong in a successful-candidate record.
There is no separate partial observation shape or invented successful status.

`feed_outcomes` contains one validated existing `FeedOutcomePayload` per
configured source, including inactive sources. It retains the source snapshot,
actual fetch and parse outcomes, parsed entry count, successful candidate count,
measured fetch and parse durations in milliseconds, and feed rejection reason.
Inactive sources were not requested or parsed, so their counts and durations
are null. Empty parsed feeds have zero counts. Failed parsing does not claim
a parsed count. The engine, not harvesting, adds the later event envelope.

Screening consumes the actual HTTP/paywall cells without fetching again.
It supplies settled prior `seen` rows separately when an undated article needs
its original first-seen instant. Harvesting neither reads that ledger nor
pretends that the fetch time is a publication time.

## Inputs and identity

The loader reads the fields it computes on from `config/feed-ingest-plan.json`,
`config/taxonomy.json`, `config/sources.json` and the `extract` section of
`config/idhazh.json`. Concurrency, timeout and request identity come from the
planner configuration. Byte limits, retries, backoff and paywall markers come
from the existing extraction configuration.

Source snapshots retain source ID, feed URL, title, vertical, kind, tier,
form, lifecycle status, source weight and the applied registry tier weight.
The returned source input also retains `retired_on`. Inactive sources receive
`SOURCE_INACTIVE` without a network request.
Non-retired sources require active registered kind and tier entries. Retired
sources may retain historical classifications, but a source snapshot still
requires its genuine registered tier weight; a missing historical tier is an
explicit input error before any requests start, never a fabricated weight.
This follows the existing source-classification rule that stable identifiers
are retired rather than reused and a missing live weight is a named config
error. Retired kinds and verticals need not remain current registry members.

The configuration fingerprint is SHA-256 of the UTF-8 JSON serialization of
the validated planner configuration excluding `workflow_reporting`, relevant registry fields, source list and
extraction controls, in that order. Each candidate carries that fingerprint
and its resolved vertical policy. All unknown editorial labels remain null.
Reporting settings remain available in the returned configuration, but neither
their enabled flag nor removal text changes content identity or ledger digests.
Content and policy settings still change the fingerprint.

Candidate identity uses the shared run/source/original-entry-ordinal hash.
A missing field does not renumber later siblings. URL identity follows the
existing discovery rules and shared `deriveUrlKey`. The original feed entry
URL is the request input; a page's links, canonical tags and scripts never
supply a new request target.

Feed categories include repeated, namespace-qualified and nested text values,
including Atom `term` attributes. Absence is an empty array. Invalid XML or an
unrecognized feed is a parse rejection, not an empty feed. Entry dates are
normalized to UTC, with the feed's declared date as a fallback. No declared
date means null.

## Request and extraction controls

Each run has one robots cache per normalized origin. Both the request header
and rule evaluation use the configured identity. The isolated planner's
configured header identifies `YenIdhazhBot` inside its compatible wrapper;
the robots product is that same crawler, not `Mozilla` and not another allowed
crawler. Production retains its separate `yen-idhazh/1.0` identity unchanged.

Every request validates the scheme, credentials, hostname and all resolved
addresses. Undici receives only those pinned public addresses at socket
lookup. Redirects are manual: each destination receives address and robots
checks before its target is requested. Robots-file redirects receive address
checks, while their resulting document still governs the original origin.
Redirect cycles refuse. One configured deadline bounds DNS, permission,
retries, redirects and body reading.
Oversized bodies refuse without losing an HTTP status already observed.

Robots 2xx responses supply rules; 4xx other than 429 supply no restrictions.
429, 5xx, failed requests and unsafe addresses leave permission unknown and
refuse the target. Repeated groups, longest matches, allow-on-tie, wildcards,
end anchors and percent encoding have bounded recorded cases.
Unreserved percent octets are normalized before the mature parser evaluates
paths; encoded reserved separators remain encoded.

Linkedom creates an inert DOM. Defuddle runs synchronously with async fetching
disabled and a refusing fetch function. Page resources cannot load. The
extractor keeps full usable prose and author attribution, not feed snippets.
The sanitizer follows `idhazh-sanitizer-3` from the existing trust boundary.
It removes machinery, not ordinary English instructions. There is no model
call, prompt construction, shell execution or page-derived filename here.
Missing document roots and DOM recursion overflow produce a typed extraction
failure and rejection without aborting sibling articles. Empty content remains
a distinct empty result. Unexpected programming failures still surface.

## Dependencies and cost

These are installed package-file bytes measured on Windows x64 with Bun 1.3.13,
excluding each package's nested dependencies. They are not compressed download
sizes, process memory or production runner measurements. All remain outside
the published browser bundle. Transitive packages are pinned in `bun.lock`.

Table A

| Id | Package | Beneficiary | Installed bytes |
| --- | --- | --- | ---: |
| A1 | defuddle 0.19.5 | Main article and author extraction | 2756053 |
| A2 | linkedom 0.18.13 | Inert HTML DOM without resource loading | 909684 |
| A3 | rss-parser 3.13.0 | RSS/Atom parsing through its XML parser | 1873872 |
| A4 | undici 7.16.0 | HTTP, TLS, decompression, aborts and pinned socket lookup | 1469822 |
| A5 | ipaddr.js 2.5.0 | Public address classification | 64424 |
| A6 | robots-parser 3.0.1 | Robots group and rule evaluation | 46257 |
| A7 | zod 4.6.7 | Runtime validation of authored inputs and transient evidence | 6148944 |
| A8 | apache-arrow 21.2.0 | Shared writer and later real planner ledger readers | 5818996 |
| A9 | parquet-wasm 0.9.0 | Shared writer and real TypeScript Parquet readback | 16264816 |
| A10 | Local common-contracts | Existing candidate, rejection, source and identity validation | 81841 |
| A11 | Local ledger-file-writer | Existing atomic Parquet persistence and identity | 84658 |

Arrow, Parquet and Zod reuse the writer's adopted versions. Their runtime
classification also serves later bounded history readers; this harvest does
not implement those readers. The local package figures describe this checkout,
not new copies of their dependencies.

## Verification

Run from `services/feed-ingest-plan`:

```powershell
bun run check
bun test test\harvest.test.ts test\harvest-safety.test.ts --timeout 30000
```

The tests read the five named `harvest-*` fixtures under
`tests/fixtures/feed-ingest-plan/` and the named authored configuration files.
The response replay refuses an unrecorded request. No test uses live sources
or Python. Real writer output is read through TypeScript Arrow and Parquet;
this is not a claim that a Python reader executed.

The shared selector remains unchanged. Its broader Python-backed selections
are not local commands for this isolated TypeScript row. The later isolated
workflow owns CI integration.

## See also

- [Discovery](discovery.md)
- [Trust boundary](trust-boundary.md)
- [Run the gates](../../how-to/run-the-gates.md)
