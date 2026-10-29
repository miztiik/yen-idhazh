# Recover saved article keys

**Last Updated**: 2026-10-29

Which saved addresses let the current planner recognize an earlier article key?
Article identity uses the [shared article cleanup](feed-harvesting.md#inputs-and-identity).
For each offered address, the planner derives its previous key as well as its
current key. It also recovers saved addresses from selected metadata and from
published digest items joined to actual publication rows by item ID. A selected
row alone never proves publication.

## Bounded reads

Reads cover the union of configured discovery and publication UTC windows,
today, and dates in explicitly named discovery files. The workflow stages those
selected days, their compact representations, and named published digest files;
it forwards complete selected-day membership at a pinned Git revision.
No directory or repository migration walk is performed.

Associations exist only within one capture. Earlier first-sight timestamps
remain earlier when a current key is appended lazily to its original UTC day.
Publication and settled-failure exclusions report the actual matched stored key.
Original rows, published keys, feed attribution and offer ordinals are preserved.
Repeated offers can still download separately; selection retains at most one
winner per current key. This is not a request cache.

## Missing or ambiguous evidence

A saved address must reproduce its declared key using the legacy policy, the
current policy, the alternate `tidy_urls` setting, or the exact saved string.
Ambiguous associations are excluded rather than linked across destinations.
Missing or corrupt joins produce body-free `article_identity_history_gap`
diagnostics and incomplete recovery while valid siblings remain usable.
An unsafe alternate-policy address contributes no association and cannot replace
the safe current-policy target.

A hash-only older query variant with no recoverable saved address cannot be
recognized from another offer. The planner does not invent an address or claim
complete historical deduplication. No durable alias ledger, historical rewrite
or Python discovery change is introduced.

## Design rationale

The approved 2026-10-29 UTC cleanup keeps requests and stored article identity
consistent without changing the existing publication join. Bounded saved-address
recovery preserves useful old-key evidence at the cost of leaving unrecoverable
hash-only variants unknown. Compatible old TypeScript stamps remain readable
without changing their recorded meaning; the
[exact accepted stamps](../../reference/feed-planner-ledgers.md#article-cleanup-compatibility)
do not reopen earlier incompatible formats.

## See also

- [Planner history](planner-feed-history.md)
- [Ledger reference](../../reference/feed-planner-ledgers.md)
