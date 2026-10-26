# Feed candidate screening

**Last Updated**: 2026-10-26

Which parsed articles can reach numeric selection?
Screening validates the complete server-owned candidate batch, current
technical observations, settled first sight and the global policy. It
fetches nothing and writes no rejection ledger.

## Inputs and result

Candidate identities must match their supplying run, correlation and offered
ordinal. Observations are keyed by those identities; an observation without
a candidate fails validation. A missing observation is unknown, not HTTP
success or proof of no paywall. Terminal harvest failures are not admitted
again as candidates.

The result contains admitted candidates and transient terminal exclusions.
Only admitted candidates increment the selection-opportunity denominator in
health C26. Exclusions are reduced to grouped counts by feed, subject, stage,
reason and supported attribution. No full rejected population is committed
or returned as an audit export.

## Gates and timing

Structured URL restrictions, actual publication exclusions and settled item
failures remain real inputs. The permitted fetch path checks them before
article download where possible; screening rechecks them for independently
parsed articles. An unavailable external history does not manufacture a
publication or failure.

Paywall or configured HTTP blocks, category exclusions, the form-specific
word minimum and the maximum age retain their relative precedence. Category matching
uses whole trimmed, case-folded tags. One first failed gate produces one
terminal exclusion.

After category admission, the enabled `content_filters` apply media addresses,
opening press-release markers, then link-heavy content before the existing
form-specific word minimum and age gate. These are heuristic exclusions, not
model quality scores. Media can stop earlier at
[harvest preflight](feed-harvesting.md#inputs-and-identity).

The opening sample is the first configured number of extracted Markdown
characters, 600 by default. Configured markers match without case sensitivity
and with word boundaries. A marker after that sample, or only part of a longer
word, does not match. The transient result records the marker's configuration
index and actual sample length, not source text.

Link density is linked-label characters divided by total extracted Markdown
characters, rounded to two decimal places. Rejection is strictly above the
configured limit, 0.40 by default. Thus 400 or 404 linked-label characters in
1,000 Markdown characters both round to 0.40 and pass this rule; 405 round to
0.41 and fail it. A second branch rejects more than 10 actual list items only
when the extracted word count is below 150. Both limits are configurable.
Equality at 10 items or 150 words passes that branch. This does not replace
the existing article and abstract word minima.

The native Markdown parser counts decoded label text, including image alt
text once, and actual list items. Formatting delimiters, escaped syntax and
code examples are not label characters or list items. This replaces the
prototype's fragile regular expression with parser-defined labels while
retaining its image inclusion and exact rounded-threshold behavior.
Measurement uses the chosen article Markdown before final URL scrubbing,
never navigation from the whole page. For semantic recovery, the existing
converter produces measurement Markdown from exactly the retained paragraphs;
the recovered plain prose and its word count do not change. Only numeric
counts and the rounded fraction cross into screening. No raw destination,
measurement Markdown or rejected-body population is logged or committed.
Missing historical observation evidence stays unavailable; screening does
not recalculate a false zero from URL-scrubbed text.

Age uses a trustworthy publication time, otherwise the earliest known global
first sight by URL key. A timestamp exactly at the future tolerance is
trusted; one beyond it is not. Age equal to the cutoff passes. Unknown time
stays null with no invented recency bonus.

The parsed batch's saved age clock is D19. A later feedback refresh uses D22
without changing that age clock. Signed age can be negative for an admitted
near-future publication; only the ranking calculation floors it at zero.
The selected metadata retains its actual timing basis and timestamp.

## Rejection persistence

There is no standalone rejection write. A run records grouped exclusions in
its actual UTC work-day health rows. Missing measurements remain unavailable.
Native selected output and the text artifact are finalized later from the
same chosen result.

## Design rationale

Admission and ranking share one public selection operation, but keep distinct
denominators. A stale or technically rejected candidate is not a new admitted
opportunity. The global first-sight join prevents another feed or fetch from
renewing an undated article's age.
Content exclusions retain successful feed downloads/parses, original offered
ordinals, first sight and actual request spend. Their grouped health reason
has no source-failure attribution. Numeric selection and quotas are unchanged.

## See also

- [Policies](feed-ingest-policies.md)
- [Curation](feed-curation.md)
- [Harvesting](feed-harvesting.md)
- [Ledger fields](../../reference/feed-planner-ledgers.md)
