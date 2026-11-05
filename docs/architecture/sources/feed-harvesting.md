# Isolated feed harvesting

**Last Updated**: 2026-11-04

How do configured feeds become sanitized article candidates?
This build-time path leaves production Python discovery and extraction
unchanged. The [trust boundary](trust-boundary.md) governs fetched data.

## Public entry

The service exports `loadHarvestInputs`, `readHarvestInputs` and
`harvestFeeds`. Load the named planning, source and extraction configuration
before work. Active feed lifecycle status controls enrollment; the planner
does not load taxonomy for tier weights, activation or coverage checks.
The `./fetch-source` package entry exports `createSourceFetcher`, `SourceFetcher`
and the target result and attempt types. The separate `./request-pacing` entry
exports pacing. There is no robots module, forwarding export or policy setting.

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
publisher ID, feed URL/title, lifecycle status and configured feed weight.
They contain no inferred vertical, desk, lens, entity or quality judgment.

Configuration fingerprints retain only validated inputs used by this planner,
including effective scoring policy and source weights. The taxonomy registry
is not an input. Reporting configuration does not change content identity.
Missing feed fields do not renumber later entries. Page canonical tags,
scripts and prose never grant a new fetch destination.

Articles and feed documents use the shared
[resource address rule](../contracts/identity.md#typescript-resource-addresses).
Queries remain part of the address and hash; only the fragment is removed.
`normalize-resource-url.ts` implements the native parser rule.
`article-identity.ts` and `feed-identity.ts` hash its exact serialized result.
The source fetcher initially dispatches that same address and applies the
same normalization before validating every redirect hop. Redirects do not
change the initial identity. No optional cleaner or tracking classifier remains.

Normalization and address safety remain separate responsibilities. Invalid
addresses retain `InvalidArticleUrlError`. Feed offers normalize only
the HTTP scheme spelling before storage, retaining their original query and
fragment as captured evidence. A valid forbidden target retains its normalized
address and hash in its preflight refusal; malformed input has neither.
The final serialized resource address must
pass the same URL format and length contract as downstream payloads before
hashing or dispatch; percent-encoding cannot bypass that bound. Each actual address
passes URL, hostname and explicit-address checks before dispatch.
Impit resolves hostnames; this TypeScript path does not resolve or pin their
addresses and does not protect against DNS rebinding.
No TypeScript entry point retrieves or evaluates robots files. A forbidden
address is never dispatched.

Feedsmith normalizes RSS, Atom, RDF and JSON Feed entries. They retain
categories, authors, offered ordinals and entry-level UTC dates. A feed's
build or update time is not an article publication time. Missing, invalid
or zone-free entry dates remain unknown through admission.
Empty category labels are removed; real labels and repeats remain.
Unrecognized or invalid XML is a typed parse failure, not an empty feed.
RSS enclosures, Atom enclosure links, RDF/other Media RSS content and JSON Feed
attachments retain their MIME types in the current offer only. The enabled
`content_filters.media` rule rejects configured audio/video types and
structured host/path matches before article requests.
Host and path boundaries matter: a news URL mentioning a media host in its
path or query is not a match. Excluded offers retain their original ordinal,
actual title or null, first sight and ordinary article-exclusion accounting.
Public offer fetches and `/plan` share this preflight; standalone article
fetches use the same address checks. A valid supplying feed remains successful.
Media checks use the offered and normalized addresses. A URL embedded in a
query is data, not another target; only an actual HTTP redirect can supply
another destination. The source fetcher checks each such hop before dispatch.
Unsafe targets remain typed fetch refusals, not media exclusions.

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

The source fetcher retains URL, hostname and explicit-address validation,
safe redirects, retries, bounded deadlines and decoded body limits.
Validation occurs before every target dispatch. Feed and article requests
have no robots lookup, permission check, origin cache or separate allowance.
Each actual target dispatch counts, including retries, redirects and secondary
profiles. Validation and parsing add no HTTP request.
The fetch stops at the first decoded stream chunk that takes the running byte
count over `extract.max_body_bytes`. Its diagnostic records that configured
limit and the bytes observed so far as a lower bound; it does not read the rest
of the response or claim its full size.

`harvest.request_headers` supplies primary and nullable secondary native browser
profiles. Firefox is primary; Chrome is secondary.
Impit selects TLS, HTTP/2 and wire-header defaults together. Explicit
`accept` and `accept-language` overrides can select content or language;
the committed profiles use no overrides.
Wire headers have no crawler user-agent suffix or copied browser version.
The wire identity is a browser profile, not an identified crawler with contact
details. This trade-off leaves native headers intact; it does not execute
JavaScript, sign requests, import credentials or guarantee publisher access.

Within the bounded target allowance, exhausted network/status retries or
a successful article body below `recovery_min_body_bytes` can try the secondary
profile once per redirect hop. Only `recoverable_http_statuses` permit HTTP
profile recovery; missing, gone and rate-limited responses do not use it by
default. Each profile keeps the existing status retry rules. Attempt
sequence remains unique; the retry index restarts for a new profile.
Every actual dispatch is counted. A failed recovery preserves an earlier
real short response for normal parsing rather than inventing article text.
This also holds when a secondary redirect ends in a download failure.
An unsafe article redirect always refuses the operation.
Each enabled profile contributes one configured attempt-and-backoff allowance
to the deadline shared by all target reads and article redirect hops.
External cancellation stops the owned target work and prevents later dispatches.
Disabling the secondary profile leaves one target allowance.
The body-size recovery rule never applies to feeds. Short, empty and malformed
feed downloads keep their real HTTP result and separate parse outcome.

`harvest.request_pacing` applies a process-local scheduler to every dispatched
feed and article request, including retries, secondary-profile recovery
and redirect hops. Each request uses its destination domain and, when present,
the curated publisher ID. The domain key groups hostnames by registrable domain
(the domain beneath the public suffix), using the configured private-suffix
policy; a missing publisher ID adds no publisher key. Both keys are acquired
domain first, then publisher. Validation-only refusals do not
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
older than the effective global known-age ceiling also stops before page
requests. Its default is 36 hours, or one positive finite run
override, resolved before work. Equality passes. Trusted publication supplies
age, otherwise captured first sight; absent usable timing remains unknown
and eligible with zero recency. A too-future publication cannot manufacture
freshness. Preflight and [screening](feed-screening.md#gates-and-timing)
use the same captured UTC age clock and rule. Rejected offers retain
discoveries, original ordinals and ordinary exclusion accounting without
becoming technical source failures.

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
codes describe only the actual article operation, with null for unobserved
target facts. Removed permission fields have no placeholders.
Attempt facts retain each actual target dispatch on its dispatch UTC day,
even when the response settles after midnight. HTTP success still requires
extraction and content admission.
Validated work facts feed the run's
[batched health counters](../contracts/feed-ingest-feedback.md#completed-unit-persistence).
Actual work-day clocks are separate from the saved age clock.
Shared Python item-health inputs retain their original format. At the native
input boundary, `robots_denied` and `robots_unreachable` are inapplicable and
cannot exclude an article. Other configured same-day earlier failures still
exclude it; a file containing an inapplicable reason remains usable.

On a pool failure, already-running siblings settle before the caller returns.
Completed feed work and article failures remain available for partial-run
finalization even if a later stage fails. Terminal failures not yet written
remain process-local: abrupt process termination before finalization can lose
them. This path does not provide crash recovery. No normal
response, event export or artifact archives the full parsed/rejected population.
Only selected article text enters the summarizer artifact.

## Design rationale

The TypeScript path fetches only the feed or article targets it needs.
The actual target response determines download success.
URL and explicit-address checks remain; hostname address resolution
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

A source request that fails before a usable response is a local download
failure; sibling work continues. The classifier recognizes the installed
`HTTPError` and `RequestError` families, including their subclasses, rather
than matching exception names or message text. The saved `network` value means
the request failed without a more precise proven cause; it does not claim a
DNS, TLS or timeout diagnosis. Typed timeouts and caller cancellation keep
their existing precedence. Native exceptions remain unchanged, and available
safe error codes are retained. A rejected response has no invented HTTP status
or response evidence. Arbitrary execution errors and unrecognized native
exceptions still fail the operation.
The ordinary `ci.yml` gates job runs the native transport test on Linux with
frozen dependencies as part of the complete service suite.

## Dependencies and cost

Feedsmith 3.0.1 replaces rss-parser and adds JSON Feed and RDF support. Its
XML parser and entity decoder replace the old XML dependency tree.
The existing Defuddle 0.19.5 node entry uses its installed Markdown converter;
LinkeDOM still supplies inert documents. Impit replaces the former HTTP client
and its compression/dispatcher machinery; the address library
retains URL/literal checks. The robots parser dependency is removed.
These dependencies run in the
build-time Bun process and workers, not the published browser bundle.
Resource URL normalization uses the existing runtime parser and adds no
dependency or browser bytes.
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

One shared target-only fetcher keeps direct harvesting, HTTP stages, collection
work and the probe consistent. Removing robots work also removes its
configuration, request category and native evidence fields rather than leaving
a disabled implementation. Address safety, extraction, sanitization, pacing
and the other admission checks remain active.

Early factual refusals avoid downloading work the same admission rule would
reject later. Shared production parsing and bounded native workers preserve
the trust checks while allowing independent requests to make real progress.
Article limits constrain output only; they are not an input truncation policy.

Only the current normalized article address is used to match discovery,
publication and settled-failure keys.
Historical files and keys are not rehashed or rewritten. The
[native history rules](planner-feed-history.md#raw-and-compact-copies)
keep current full-row reads separate from usable historical health fields.
No alternate-policy key lookup is added, so changed address keys can cause
repeat processing without claiming an earlier sighting.

Configured `/short-video` route prefixes identify media offers and reject them
before article requests. Host/path boundaries keep other story routes eligible
without relying on titles or extraction outcomes.

## See also

- [Operator APIs](feed-operator-api.md)
- [Screening](feed-screening.md)
- [Policies](feed-ingest-policies.md)
- [Local checks](../../how-to/run-feed-ingest-plan-test.md)
