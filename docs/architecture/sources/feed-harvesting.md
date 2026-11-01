# Isolated feed harvesting

**Last Updated**: 2026-11-01

How do configured feeds become sanitized article candidates?
This build-time path leaves production Python discovery and extraction
unchanged. The [trust boundary](trust-boundary.md) governs fetched data.

## Public entry

The service exports `loadHarvestInputs`, `readHarvestInputs` and
`harvestFeeds`. Load the named planning, source, shared kind/tier and
extraction configuration before work. The taxonomy contributes active source
kinds and numeric tier weights, not vertical policy or article labels.

The actual harvester accepts validated context plus an optional recorded
source-response boundary. Ordinary execution uses native Impit. One fetcher
reuses one client per configured browser profile; each request owns its
cancellation signal and releases its response reader on completion or refusal.
Impit has no public client-close API. No dispatcher or resolver adapter remains.

Independent feeds overlap within configured bounds. Article work can start
after its supplying feed is parsed. Native workers perform the production
feed XML parsing, DOM extraction and sanitization without blocking the listener's event loop.
Parsing saved bytes makes no network request.

## Inputs and identity

Candidates retain sanitized content, canonical URL identity, original offered
ordinal and configured source facts. Those facts include nullable curated
publisher ID, kind, form, tier, feed weight and applied tier weight.
They contain no inferred vertical, desk, lens, entity or quality judgment.

Configuration fingerprints retain the actual content-affecting inputs.
Reporting configuration does not change harvested content identity.
Missing feed fields do not renumber later entries. Page canonical tags,
scripts and prose never grant a new fetch destination.

Every article loses its entire query string and fragment. This includes
required article identifiers: a query-dependent article can stop working.
`harvest.tidy_urls` enables additional cleanup before that removal, including
unwrapping supported redirect addresses. Setting it to false does not preserve
article queries. Feeds and robots downloads bypass this cleanup and retain
their request parameters. Feed identity and Python discovery remain unchanged.

`article-url.ts` exports `cleanArticleUrl`, the shared article cleanup policy.
`article-identity.ts` hashes its exact serialized result as `url_key` and retains
that result as `canonical_url`. The permitted fetcher uses the same policy for
robots permission and each dispatched article hop. Redirects do not change
the initial identity. The lower-level `http-request-target.ts` applies the
optional cleaner; it does not hash addresses.

Cleanup and network permission remain separate responsibilities. Invalid
article addresses retain `InvalidArticleUrlError`. Feed offers normalize only
the HTTP scheme spelling before storage, retaining their original query and
fragment as historical evidence. The final serialized article address must
pass the same URL format and length contract as downstream payloads before
hashing or dispatch; percent-encoding cannot bypass that bound. Each transformed address
passes URL, hostname and explicit-address checks before dispatch.
Impit resolves hostnames; this TypeScript path does not resolve or pin their
addresses and does not protect against DNS rebinding.
Robots results are retained as evidence; article `enforce` policy may stop an
article before target dispatch. An unsafe transformed address is never
dispatched.

Feedsmith normalizes RSS, Atom, RDF and JSON Feed entries. They retain
categories, authors, offered ordinals and entry-level UTC dates. A feed's
build or update time is not an article publication time. Missing, invalid
or zone-free entry dates remain unknown through admission.
Empty category labels are removed; real labels and repeats remain.
Unrecognized or invalid XML is a typed parse failure, not an empty feed.
RSS enclosures, Atom enclosure links, RDF/other Media RSS content and JSON Feed
attachments retain their MIME types in the current offer only. The enabled
`content_filters.media` rule rejects configured audio/video types and
structured host/path matches before article or article-robots requests.
Host and path boundaries matter: a news URL mentioning a media host in its
path or query is not a match. Excluded offers retain their original ordinal,
actual title or null, first sight and ordinary article-exclusion accounting.
Public offer fetches and `/plan` share this preflight; standalone article
fetches use the same address checks. A valid supplying feed remains successful.
Both the offered address and the configured cleaned request target are checked,
so a known URL wrapper cannot hide a media destination. This adds no request
and never adds a second identity policy. Unsafe cleaned targets remain
typed fetch refusals, not media exclusions.

## Request and extraction controls

`harvest.fetch_timeout_ms` remains 6000 ms per HTTP attempt in the committed
configuration. It is not a deadline for the whole download or parse operation.
`harvest.parse_timeout_ms` is the separate parse-request deadline, including
time waiting for a worker. Its 10000 ms default is unmeasured, not a measured
parser speed target. Finished work returns immediately and clears its timer.
Expiry removes a queued request or terminates its assigned native worker;
later work receives a replacement worker. Cancellation applies to the one
request, not the shared pool. The caller that created a pool retains ownership
of its lifetime.

Feed XML and article HTML use this same worker boundary. A parse deadline
records `parser-timeout`; cancellation records `parser-cancelled`; a worker
failure records `parser-failed`. These are local parser failures, never
evidence that a source should retire. Malformed feed data retains its distinct
`malformed-feed` result.

The permitted fetcher retains URL, hostname and explicit-address validation,
robots evidence, safe redirects, retries, bounded deadlines and decoded
body limits. Validation occurs before dispatch. Safe feed targets and feed
redirect hops are attempted even when robots permission is denied or unknown.
`harvest.article_robots_policy` selects `enforce` or `observe` for articles
and their redirect hops. Missing settings default to `enforce`; committed
planner configuration uses `observe`. In `observe`, denied or unknown robots
permission does not block a safe article request. Actual retry and redirect dispatches
each count; cache reuse adds no request.
The fetch stops at the first decoded stream chunk that takes the running byte
count over `extract.max_body_bytes`. Its diagnostic records that configured
limit and the bytes observed so far as a lower bound; it does not read the rest
of the response or claim its full size.

`harvest.request_headers` supplies primary and nullable secondary native browser
profiles. Firefox is primary; Chrome is secondary. Robots use the primary
profile. Impit selects TLS, HTTP/2 and wire-header defaults together. Explicit
`accept` and `accept-language` overrides can select content or language;
the committed profiles use no overrides.
Wire headers have no crawler user-agent suffix or copied browser version.
Impit does not expose its native user-agent for permission matching, so the
robots parser checks general `User-agent: *` rules, not browser-specific groups.
The wire identity is a browser profile, not an identified crawler with contact
details. This trade-off leaves native headers intact; it does not execute
JavaScript, sign requests, import credentials or guarantee publisher access.
A denied or unknown robots result is retained across redirects. It blocks an
article only when that article uses `enforce`; it does not block a safe feed
request or an article in `observe`.

Within the bounded target allowance, exhausted network/status retries or
a successful article body below `recovery_min_body_bytes` can try the secondary
profile once per redirect hop. Only `recoverable_http_statuses` permit HTTP
profile recovery; missing, gone and rate-limited responses do not use it by
default. Each profile keeps the existing status retry rules. Attempt
sequence remains unique; the retry index restarts for a new profile.
Every actual dispatch is counted. A failed recovery preserves an earlier
real short response for normal parsing rather than inventing article text.
This also holds when a secondary redirect ends in a download failure.
An unsafe article redirect always refuses the operation. Denied or unknown
permission on a safe redirect follows the document's robots policy.
Each enabled profile contributes one configured attempt-and-backoff allowance
to the deadline shared by all target reads and article redirect hops. Robots
work has a separate allowance: one configured retry sequence, including its
attempt timeouts and backoff. Waiting for robots does not consume target time
or abort its signal. Each new origin has that same bounded robots allowance;
success and settled failures are cached by origin for this fetcher. A failed
check becomes unknown and is not started again for each article. External
cancellation cancels both target work and robots waiting.
Disabling the secondary profile leaves one target allowance.
The body-size recovery rule never applies to feeds. Short, empty and malformed
feed downloads keep their real HTTP result and separate parse outcome.

`harvest.request_pacing` applies a process-local scheduler to every dispatched
robots, feed and article request, including retries, secondary-profile recovery
and redirect hops. Each request uses its destination domain and, when present,
the curated publisher ID. The domain key groups hostnames by registrable domain
(the domain beneath the public suffix), using the configured private-suffix
policy; a missing publisher ID adds no publisher key. Both keys are acquired
domain first, then publisher. Cache hits and validation-only refusals do not
dispatch and use no slot.

The first request for a key has no initial delay. After the application request
settles with content or failure, the next request waits for that key's configured
base delay plus independently sampled jitter. A slot covers application request
settlement and cooldown, not the physical lifetime of native work that may
continue after timeout. Cancellation settles the caller's queued wait or ends
cooldown without dispatching a cancelled request. Queue waits do not consume an
HTTP attempt timer; measured queue wait is kept on the attempt, and the total
fetch elapsed time includes it. `duration_ms` excludes both queue wait and
retry backoff.

The listener shares one scheduler across collection and standalone document
requests. A direct harvester or probe call owns one for its invocation; the
standalone probe CLI shares one across the targets it processes. The open-source
`bottleneck` package supplies the keyed single-request queues. It benefits
shared domain and publisher pacing and adds one JavaScript dependency plus
in-memory queue state; it adds no browser bundle or native binary. Idle keyed
queues expire, and listener shutdown cancels only its own application work.
The configured 1000 ms base delays and 0..500 ms jitter are initial estimates,
not measured optimum values. Zero delays are supported.

Structured configured URL exclusions, real publication history and settled
item failures can refuse a page before download. A dated entry strictly
older than the effective global freshness cutoff also stops before page
and robots requests. Equality remains admitted. An unavailable or too-future
date retains the later first-sight or unknown-time path.

A missing title retains page-title recovery. Actual HTML extraction keeps
prose and byline but never executes scripts or loads page resources.
Defuddle's node entry produces Markdown with asynchronous source fetches
disabled and a rejecting resource-fetch callback. The sanitizer runs after
Markdown conversion as well as on decoded DOM text before conversion.
The chosen article's [numeric content measurements](feed-screening.md#gates-and-timing)
are taken between those two sanitizer passes; final text is still fully scrubbed.
If that result is too short, semantic HTML elements
can supply actual page prose; a `semantic-dom-fallback` warning records its
use. `harvest.semantic_fallback` configures ordered content roots, removed
elements, paragraph elements, minimum root/paragraph characters and metadata
sources. A short teaser does not hide a later substantial content root.
Nested blocks and repeated paragraphs contribute their text once; block
boundaries retain paragraph separation, including when the selected root
is itself a prose block. Consent, ad, sharing and comment elements
are removed before roots are measured.

Title and author recovery read actual page metadata before the primary
extractor can mutate it. Empty metadata values do not stop later sources.
Descriptions never enter the body or increase its word count. No invented
title, article or default URL fills a failed extraction.
Missing, empty and refused extraction remain distinct from successful work.
The [screening stage](feed-screening.md) applies admission to parsed candidates.

## Work facts and failures

The harvester returns candidates and terminal outcomes. During `/plan`, the
caller collects completed article-fetch and extraction failures in memory.
Its `finally` block writes them through the registered `rejected-articles`
ledger writer, including when a later stage fails. Standalone fetch and parse
write their terminal failures to local ledger files at stage completion;
the private fetch receipt is not their sole store.
Writing a local ledger file is separate from
[verified Git delivery](feed-ingest-audit.md#what-is-checked-and-written).
Only terminal outcomes are retained, not each retry or successful article.
The offered candidate and URL identities stay unchanged; missing addresses
never gain invented identities. Article HTTP status and low-level failure
codes remain separate from observed robots permission, status and failure,
with null for unobserved values.
Observed-mode success is not a rejection solely because robots denied access
or could not be read. The terminal article status, failure and low-level code
describe the actual article operation, never its robots check. Earlier robots
warnings remain visible across article redirects; attempt facts retain each
actual robots and target dispatch. HTTP success still requires extraction and
content admission.
Validated work facts feed the run's
[batched health counters](../contracts/feed-ingest-feedback.md#completed-unit-persistence).
Actual work-day clocks are separate from the saved age clock.

On a pool failure, already-running siblings settle before the caller returns.
Completed feed work and article failures remain available for partial-run
finalization even if a later stage fails. Terminal failures not yet written
remain process-local: abrupt process termination before finalization can lose
them. This path does not provide crash recovery. No normal
response, event export or artifact archives the full parsed/rejected population.
Only selected article text enters the summarizer artifact.

## Design rationale

The robots checker can be wrong or unavailable. Attempting a safe feed target
keeps that evidence separate from the publisher's actual response. Keep the
robots verdict, status and retrieval failure, but let the target response
decide whether the feed fetch succeeded. Article `enforce` remains an explicit
option. URL and explicit-address checks remain; hostname address resolution
and socket pinning do not. Manual redirects keep each destination subject to
those remaining checks before dispatch.

Native defaults keep TLS verification enabled, use HTTP/2 where supported,
and decode gzip, Brotli and deflate streams. HTTP/3 is opt-in and is not
requested; no measured source need justifies adding a control for it.
No proxy, persistent cookie jar or weaker TLS fallback is enabled.
Each request passes the existing attempt budget to Impit's native timeout.
This is a total connection-through-body deadline, not a headers-only timeout.
The public JavaScript API has no separate connect-only or read-only timeout.
Before headers arrive, Impit has no supported immediate native cancellation
API. The request keeps ownership until headers arrive or that native timeout
expires; early cancellation can wait up to the attempt budget plus settlement
overhead. It never returns early while that native request remains active.
After headers arrive, caller cancellation aborts the owned native signal.
The body reader keeps ownership until the native stream observes that abort;
it does not leave the read loop early on the caller signal. A cancelled result
is never returned as successful content. Failed reads also await stream cleanup.
The existing application deadline still bounds response reading.
Request cancellation and failed-reader cleanup must not replace the observed
status and byte count.
A proven decoded cutoff remains the primary failure if later cancellation or
stream cleanup also fails. Combined errors retain the cleanup cause and any
available safe code without exposing exception messages.
API completion and native response termination are different events.
The transport test keeps Impit under Bun and uses a genuine Node source to
check decoded-byte limits, cancellation, native deadlines and response evidence.
Native total-body timeout is checked separately from caller cancellation.
An unfinished response can remain active after its native deadline; an API
failure does not prove physical response termination. The public API has no
bounded disposal acknowledgement for that error path. Pacing slots follow
application request settlement and configured cooldown, not physical native
response termination. Network activity may therefore overlap after a timeout,
even though application requests sharing a pacing key do not overlap.
Streamed native errors may be untyped; their messages are not used to invent
a timeout class or safe error code.
The separate `source-transport-test.yml` workflow runs this same native
API test on Linux and records the actual candidate SHA.
Production CI keeps its existing full-candidate checks.

## Dependencies and cost

Feedsmith 3.0.1 replaces rss-parser and adds JSON Feed and RDF support. Its
XML parser and entity decoder replace the old XML dependency tree.
The existing Defuddle 0.19.5 node entry uses its installed Markdown converter;
LinkeDOM still supplies inert documents. Impit replaces the former HTTP client
and its compression/dispatcher machinery; the address and robots libraries
retain URL/literal checks and rule parsing. These dependencies run in the
build-time Bun process and workers, not the published browser bundle.
TidyURL 1.18.3 adds its bundled URL-cleaning rules and no runtime dependencies
for request-target cleanup. Its installed bytes remain build-time only.
Impit's beneficiary is native browser TLS and HTTP fingerprints with bounded
decoded response reads. Its Linux x64 native binary occupies 10,581,792 bytes
(about 10.1 MiB). Service and probe installation took 2 seconds on a GitHub
Linux x64 runner, after shared publication packages were installed. The host
reported four logical CPUs and about 16 GiB RAM.
Native binaries are install-time
dependencies, never committed or shipped to the published site.
The remaining `undici-types` dependency is type declarations required by
Bun/Node types, not a runtime HTTP client. No runtime Undici dependency remains
in the service or probe lockfile. No parser framework or profiler is introduced.
The pinned Bun runtime's native Markdown parser measures labels and lists
without another package. Turndown 7.2.4, already installed by Defuddle, is now
declared directly for semantic-recovery measurement. It adds no installed
runtime bytes to this dependency tree. Its type declarations are build-only.
Neither parser nor converter executes page scripts or fetches resources.

## Design rationale

Run finalization writes harvest failures independently of selected-output
persistence, so a later stage failure need not discard completed failures.
Passing those rows through parsed, selected and partitioned batches would not
add restart recovery: `StageStore` holds those batches in a bounded in-memory
`Map`, not on disk.

Robots results are evidence, not a veto for a safe feed target. The committed
article setting also observes them; explicit article `enforce` remains
available. Retain the verdict, HTTP status and retrieval failure, then use
the actual target response to determine fetch success or rejection. Separate
configured allowances prevent a failed robots read from consuming the target's
request allowance. Address safety, extraction, sanitization and admission do
not change.

Early factual refusals avoid downloading work the same admission rule would
reject later. Shared production parsing and bounded native workers preserve
the trust checks while allowing independent requests to make real progress.
Article limits constrain output only; they are not an input truncation policy.

Only the current cleaned article address is used to match discovery,
publication and settled-failure keys.
Older recorded keys remain unchanged and do not link to the current address;
this avoids extra history reads and alternate-policy checks, but can repeat
processing for an address whose older key differs.

Configured `/short-video` route prefixes identify media offers and reject them
before article requests. Host/path boundaries keep other story routes eligible
without relying on titles or extraction outcomes.

## See also

- [Operator APIs](feed-operator-api.md)
- [Screening](feed-screening.md)
- [Policies](feed-ingest-policies.md)
- [Local checks](../../how-to/run-feed-ingest-plan-test.md)
