# Isolated feed harvesting

**Last Updated**: 2026-11-02

How do configured feeds become sanitized article candidates?
This build-time path leaves production Python discovery and extraction
unchanged. The [trust boundary](trust-boundary.md) governs fetched data.

## Public entry

The service exports `loadHarvestInputs`, `readHarvestInputs` and
`harvestFeeds`. Load the named planning, source, shared kind/tier and
extraction configuration before work. The taxonomy contributes active source
kinds and numeric tier weights, not vertical policy or article labels.

The actual harvester accepts validated context plus an optional recorded
source-response boundary. Ordinary execution uses Playwright Chromium.
The listener owns one lazy browser process. Each execution owns a temporary
context that shares only its site-issued cookies, and each logical attempt
owns a page. Independent executions do not share cookies. Direct harvesting
owns its browser unless supplied one; the probe CLI shares its browser across
its targets. Awaited cleanup releases pages, contexts and owned processes on
completion, cancellation, eviction, collection release and listener shutdown.

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

Every initial article request loses its entire query string and fragment. This includes
required article identifiers: a query-dependent article can stop working.
`harvest.tidy_urls` enables additional cleanup before that removal, including
unwrapping supported redirect addresses. Setting it to false does not preserve
article queries. Feeds and robots downloads bypass this cleanup and retain
their request parameters. Feed identity and Python discovery remain unchanged.

`article-url.ts` exports `cleanArticleUrl`, the shared article cleanup policy.
`article-identity.ts` hashes its exact serialized result as `url_key` and retains
that result as `canonical_url`. The permitted fetcher uses the same policy for
the initial article request and any non-browser robots permission check. Redirects do not change
the initial identity. The lower-level `http-request-target.ts` applies the
optional cleaner; it does not hash addresses.

Cleanup and network permission remain separate responsibilities. Invalid
article addresses retain `InvalidArticleUrlError`. Feed offers normalize only
the HTTP scheme spelling before storage, retaining their original query and
fragment as historical evidence. The final serialized article address must
pass the same URL format and length contract as downstream payloads before
hashing or dispatch; percent-encoding cannot bypass that bound. Each transformed address
passes URL, hostname and explicit-address checks before dispatch.
Chromium resolves hostnames; this TypeScript path does not resolve or pin their
addresses and does not protect against DNS rebinding.
Browser navigation does not fetch or enforce robots files. Non-browser
transports retain robots evidence and the article `enforce` policy.
An unsafe transformed address is never dispatched.

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
safe redirects, retries, bounded deadlines and decoded body limits.
Validation occurs before dispatch. Browser requests do not look up or enforce
robots files, including for redirects and resource origins; their robots
permission, status, failure and response evidence remain null.
Non-browser transports retain origin-cached robots checks. Safe feed targets and feed
redirect hops are attempted even when robots permission is denied or unknown.
`harvest.article_robots_policy` selects `enforce` or `observe` for articles
and their redirect hops. Missing settings default to `enforce`; committed
planner configuration uses `observe`. This setting has no effect on browser
requests. In non-browser `observe`, denied or unknown robots
permission does not block a safe article request. Actual retry and redirect dispatches
each count; cache reuse adds no request.
After a response completes, decoded HTTP bytes must fit
`extract.max_body_bytes`. The final UTF-8 parser input, including a rendered
article document, must separately fit that same limit. Evidence names
`completed-response` or `parser-input`; `decoded_bytes` always measures the
HTTP body, never the rendered document. This is not an early transfer cutoff
or a browser-memory bound. A decoding or completion failure remains a failure;
an available prefix is never returned as a successful response.

`harvest.request_headers` is an allowlisted header map, default `{}`.
Chromium supplies its own browser headers. The non-browser robots parser matches general
`User-agent: *` rules, not browser-specific groups. There is no secondary
profile or fallback transport. Older fingerprint-shaped configuration fails
validation instead of being converted.
A non-browser denied or unknown robots result is retained across redirects. It blocks an
article only when that article uses `enforce`; it does not block a safe feed
request or an article in `observe`.

`harvest.browser.headless` defaults to true. The document deadline starts
at first document dispatch; `harvest.browser.document_timeout_ms` defaults
to 30000 ms, an initial estimate rather than measured performance.
Per-request timeouts, retries and backoff remain separate. Non-browser robots work has
its own requests and origin cache; startup and robots waiting have cancellation
owners. A failed robots check becomes unknown and is cached for the execution.
Robots resources use an explicit mode that does not request robots recursively.

The browser request gate is installed before page execution. Redirects,
scripts, fetch requests, cross-origin frames, dedicated workers and preflights
pass URL, hostname and literal-address checks before dispatch. Optional
configured pacing applies only when enabled.
Browser-generated parameters survive; only the initial article address uses
identity cleanup. Unsafe destinations refuse the operation. Unsolicited
popups, service workers and WebSockets are blocked. Chromium starts with
`--disable-shared-workers`: pausing a SharedWorker target does not prevent
its initial script download. This mandatory browser control disables creation
before a page can download that script; it is not a page-script override.
Any other root target that cannot be gated is closed before execution and
reports `network` with `ERR_UNSUPPORTED_BROWSER_TARGET`.
Browser subprocesses receive only startup, temporary-directory and locale
environment values, not repository credentials. Sandboxing remains enabled.

## Design rationale

Ubuntu restricts unprivileged user namespaces for downloaded browser binaries.
The source workflows prepare a fresh job-owned browser installation and load
AppArmor profiles attached only to its full Chromium and headless-shell
executable paths. These profiles grant `userns` using Chromium's documented
`flags=(unconfined)` form; they do not disable AppArmor or change the global
namespace restriction. No profile covers a repository path, wildcard executable
or unrelated program. The real Linux oracle still requires active Seccomp-BPF
sandboxing. See the [upstream sandbox setup](https://raw.githubusercontent.com/chromium/chromium/main/docs/security/apparmor-userns-restrictions.md).

## Browser response handling

Feeds return the completed original network body, not the
browser's XML viewer. Narrow response-header continuation permits inline
reading of download-like XML while evidence retains original headers.
Articles return rendered HTML through the existing inert parser and sanitizer.
Existing content roots are readiness hints, not new admission rules.
There is no global network-idle wait or fixed sleep. Actual short content
goes to ordinary extraction checks; descriptions and invented prose never
replace it. If the original document has completed but its content root remains
empty at the rendering deadline, its actual markup still goes to extraction.
A page that depends on a disabled SharedWorker can therefore yield no article
text; a completed HTTP request alone is not collection success.

`harvest.browser.challenge_selectors` names interstitial signals. An explicit
challenge header or unresolved configured selector produces
`challenge-unresolved`, even with HTTP 200. Automatic navigation and site
cookies can proceed until the document deadline. No credentials, persistent
profile, proxy, solver or human challenge step is introduced. Browser execution
alone does not demonstrate readable content or live publisher recovery.

Browser favicon downloads are refused before dispatch or request accounting.
This includes the default `/favicon.ico` and addresses declared by icon links;
an icon refusal therefore cannot become a failed feed or document attempt.
Document navigation remains admitted; unrelated image and script requests
are not suppressed just because their address ends in `.ico`. Normal navigation, page scripts,
rendering and temporary cookies provide browser behavior; no fake pointer
movement, random interaction, stealth modification or challenge bypass is used.

`harvest.request_pacing` applies a process-local scheduler to every dispatched
feed and article request, including resources, retries and redirect
hops. Each request uses its destination domain and, when present,
the curated publisher ID. The domain key groups hostnames by registrable domain
(the domain beneath the public suffix), using the configured private-suffix
policy; a missing publisher ID adds no publisher key. Both keys are acquired
domain first, then publisher. Cache hits and validation-only refusals do not
dispatch and use no slot.
The committed `harvest.request_pacing.enabled` is false: requests bypass these
queues and report zero pacing wait. The delays and jitter apply only if pacing
is explicitly enabled. Non-browser robots requests also use that setting.

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
prose and byline. This inert parsing step never executes scripts or loads
resources; browser loading has already finished.
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

The browser follows ordinary navigation without requesting robots files.
Previously, every browser page and resource entered the robots checker;
the first resource origin's result could populate the enclosing document's
robots evidence. Removing that browser lookup removes the unrelated evidence,
its wait and its enforcement, rather than relabelling a resource check as a
document check. Non-browser transports retain their separate permission policy.
URL and explicit-address checks remain; hostname address resolution
and socket pinning do not. Browser request interception checks each
destination before dispatch, including requests that page JavaScript creates.
Unsupported child targets are refused before execution because observing their
requests afterward would not protect the request boundary.

Playwright replaces the fingerprint-only client so actual page JavaScript and
temporary cookies can recover public content without a second transport.
Chromium owns response decompression. Reading its completed original body
preserves completion failures but gives up the former decoded-stream cutoff.
Separate admission of the rendered parser input prevents DOM expansion from
bypassing the existing limit; neither check bounds browser memory.
Resource failures remain visible without converting optional assets into
document refusals or source penalties.
Only main-document navigation adds article redirect evidence or changes its
final attempted address. A background resource redirect cannot fail the
document. HTTP 204 and 205 resources have no body, so Chromium's `ERR_ABORTED`
completion for them is successful HTTP work, not an article network failure.

The separate `source-transport-test.yml` workflow runs the actual browser
modules under Linux Bun, checks active Chromium sandboxing, and records the
candidate SHA, host and installation time. Bounded loopback cases are not
evidence of live publisher recovery.
Production CI keeps its existing full-candidate checks.

## Dependencies and cost

Feedsmith 3.0.1 replaces rss-parser and adds JSON Feed and RDF support. Its
XML parser and entity decoder replace the old XML dependency tree.
The existing Defuddle 0.19.5 node entry uses its installed Markdown converter;
LinkeDOM still supplies inert documents. Playwright replaces the former HTTP
client; the address and robots libraries
retain URL/literal checks and rule parsing. These dependencies run in the
build-time Bun process and workers, not the published browser bundle.
TidyURL 1.18.3 adds its bundled URL-cleaning rules and no runtime dependencies
for request-target cleanup. Its installed bytes remain build-time only.
Playwright 1.62.1 provides real browser navigation, JavaScript and cookies.
Its costs are the matching Chromium installation, native runtime dependencies,
startup time and browser memory. The separate workflow measures installation
time and host resources; no earlier native-client measurement describes this
browser. Browser binaries are install-time dependencies, never committed or
shipped to the published site.
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

For non-browser transports, robots results are evidence, not a veto for a safe feed target. The committed
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
