# Feed ingest planning policies

**Last Updated**: 2026-10-26

Which settings does the isolated planner apply to a candidate?
`config/feed-ingest-plan.json` supplies one global policy. The production
Python planner, source catalog and taxonomy retain their separate behavior.

## Resolve a candidate

Load and validate the authored planning configuration before work.
`resolvePolicy` applies the global screening and scoring settings, followed
only by the optional run freshness cutoff. Zero is a value where permitted;
null is not an inheritance instruction. Returned policies do not share
mutable objects with their configuration.

There are no vertical overrides or vertical-specific admission, authority,
allowance or grouping rules. Source kinds and numeric tier weights still
come from the shared curated catalog. Loading that catalog does not restore
vertical decisions or infer story labels.

Word minima depend on article or abstract form. Age cutoff and recency
half-life remain separate settings. A freshness override changes only the
cutoff. Exact defaults and validation live in the native knob declaration
and its bound TypeScript copy, not in a second policy ledger.

## Global controls and evidence

Harvest concurrency, request controls, structured URL exclusions, blocked
categories and HTTP statuses apply to all feeds. Portfolio count, source and
domain shares, minimum distinct sources, relaxation order and exploration
share govern the complete selection. Partition controls govern assignments,
not admission.

Numeric ranking uses recency, configured feed authority and the retained
feed-reliability, publisher, source-kind and parent-domain adjustments.
Each applied component is recorded in the compact selected metadata.
See [curation](feed-curation.md) for the calculation.

Publisher IDs remain configured or null. Primary-document identities and
parent domains require explicit evidence. No headline, article length,
byline or feed category creates a vertical, desk, lens, event group, entity
or article-quality verdict.

## Design rationale

A global policy removes a hidden dependency on the source's subject labels.
The same numeric settings now govern every candidate; the shared catalog
continues to supply only the facts the planner actually uses.
Changing configuration changes behavior without a source edit.

## See also

- [Screening](feed-screening.md)
- [Curation](feed-curation.md)
- [Ledger fields](../../reference/feed-planner-ledgers.md)
- [Configuration](../../concepts/config.md)
