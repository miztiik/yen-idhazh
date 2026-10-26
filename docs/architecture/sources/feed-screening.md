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
word minimum and the maximum age retain their precedence. Category matching
uses whole trimmed, case-folded tags. One first failed gate produces one
terminal exclusion.

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

## See also

- [Policies](feed-ingest-policies.md)
- [Curation](feed-curation.md)
- [Harvesting](feed-harvesting.md)
- [Ledger fields](../../reference/feed-planner-ledgers.md)
