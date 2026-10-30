# Isolated feed harvesting

**Last Updated**: 2026-10-30

How do configured feeds become sanitized article candidates?
This build-time path leaves production Python discovery and extraction
unchanged. The [trust boundary](trust-boundary.md) governs fetched data.

## Public entry

The service exports `loadHarvestInputs`, `readHarvestInputs` and
`harvestFeeds`. Load the named planning, source, shared kind/tier and
extraction configuration before work. The taxonomy contributes active source
kinds and numeric tier weights, not vertical policy or article labels.

The actual harvester accepts validated context plus an optional recorded
transport/resolver boundary. Ordinary execution uses the installed Undici
request API and operating-system resolver. The response remains pinned to
validated addresses. Each request dispatcher closes after success or refusal.

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
passes public-address validation, DNS checks, the applicable robots policy
and pinned dispatch before use. An unsafe transformed address is never dispatched.

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

The permitted fetcher retains public-address validation, socket pinning,
robots evidence, safe redirects, retries, bounded deadlines and decoded
body limits. Validation occurs before dispatch. Feeds and feed redirect hops
always require allowed robots permission. `harvest.article_robots_policy`
selects `enforce` or `observe` for articles and their redirect hops. Missing
settings default to `enforce`; committed planner configuration uses `observe`.
In `observe`, denied or unknown robots permission does not block a safe article
request. Actual retry and redirect dispatches
each count; cache reuse adds no request.

`harvest.request_headers` supplies primary and nullable secondary navigation
profiles. Both feed and article targets use them; robots downloads do not.
Each wire user agent keeps the configured crawler identity and adds its
profile's distinct browser signature. Robots matching uses that same crawler
product, checked against the actual wire value. Profiles cannot replace it.
These headers do not provide browser execution or bot signing.
A denied or unknown robots result stops feed requests and articles in `enforce`
mode before any target profile is sent.

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
to the deadline shared by target DNS and all article redirect hops. Robots
work has a separate allowance: one configured retry sequence, including its
attempt timeouts and backoff. Waiting for robots does not consume target time
or abort its signal. Each new origin has that same bounded robots allowance;
success and settled failures are cached by origin for this fetcher. A failed
check becomes unknown and is not started again for each article. External
cancellation cancels both target work and robots waiting.
Disabling the secondary profile leaves one target allowance.
The body-size recovery rule never applies to feeds. Short, empty and malformed
feed downloads keep their real HTTP result and separate parse outcome.

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

## Dependencies and cost

Feedsmith 3.0.1 replaces rss-parser and adds JSON Feed and RDF support. Its
XML parser and entity decoder replace the old XML dependency tree.
The existing Defuddle 0.19.5 node entry uses its installed Markdown converter;
LinkeDOM still supplies inert documents. Undici, address and robots
libraries retain transport control. These dependencies run in the
build-time Bun process and workers, not the published browser bundle.
TidyURL 1.18.3 adds its bundled URL-cleaning rules and no runtime dependencies
for request-target cleanup. Its installed bytes remain build-time only.
No new HTTP client, parser framework or profiler is introduced.
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

User-directed policy change, 2026-10-29 UTC: article robots permission is
advisory in the committed planner settings. Retain the robots verdict, HTTP
status and underlying failure, then attempt the safe article address and let
the actual response determine download success or rejection. Feeds remain
enforced. Separate configured allowances prevent an unavailable robots file
from consuming the article's chance to respond. This changes neither address
safety nor extraction, sanitization and content admission.

Early factual refusals avoid downloading work the same admission rule would
reject later. Shared production parsing and bounded native workers preserve
the trust checks while allowing independent requests to make real progress.
Article limits constrain output only; they are not an input truncation policy.

User-directed policy change, 2026-10-30 UTC: only the current cleaned article
address is used to match discovery, publication and settled-failure keys.
Older recorded keys remain unchanged and do not link to the current address;
this avoids extra history reads and alternate-policy checks, but can repeat
processing for an address whose older key differs.

## See also

- [Operator APIs](feed-operator-api.md)
- [Screening](feed-screening.md)
- [Policies](feed-ingest-policies.md)
- [Local checks](../../how-to/run-feed-ingest-plan-test.md)
