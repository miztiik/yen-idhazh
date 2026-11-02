# Feed ingest planning policies

**Last Updated**: 2026-11-02

Which settings does the isolated planner apply to a candidate?
`config/feed-ingest-plan.json` supplies one global policy. The production
Python planner, source catalog and taxonomy retain their separate behavior.

## Resolve a candidate

Load and validate the authored planning configuration before work.
`resolvePolicy` applies global screening and scoring settings. Tier windows
are resolved separately and a run freshness cutoff can only tighten them.
Zero is a value where permitted;
null is not an inheritance instruction. Returned policies do not share
mutable objects with their configuration.

There are no vertical overrides or vertical-specific admission, authority,
allowance or grouping rules. Numeric tier weights still
come from the shared curated catalog. Loading that catalog does not restore
vertical decisions or infer story labels.

The same word minimum applies to every parsed article. Tier age steps and
recency half-life remain separate settings. The validated TypeScript
configuration owns defaults; it has no Python planner mirror.

The current configuration stamp is `2026-11-02`; older authored planner
configurations fail validation rather than being converted. It declares
`curate_articles.global_age_ceiling_hours`, `diversity` and `substance` in
preparation for a later selection change. These blocks are global-only and
excluded from the current effective candidate policy. They do not yet change
age admission, scoring, allocation or selected output.

The prepared age ceiling is 36 hours of known age. Diversity declares squared
website/feed count coefficients and a first-use feed bonus. Substance declares
a retained-word ramp, full-credit interval and long-form floor, name/number
density, headline deductions and paragraph retention thresholds. Their bounds,
curve order, distinct lowercase stop words and Unicode punctuation expressions
are validated at load. Retained-word settings describe scoring, never a new
admission minimum. The existing raw technical minimum, recency coefficients,
reliability floor and history window remain unchanged.

## Global controls and evidence

Harvest concurrency, request controls, structured URL exclusions, blocked
categories and HTTP statuses apply to all feeds. Portfolio count, source and
domain shares, minimum distinct sources, relaxation order and exploration
share govern the complete selection. Partition controls govern assignments,
not admission.

Numeric ranking uses recency, configured feed authority and the retained
article-pass, publisher and canonical website-group adjustments.
Each applied component is recorded in the compact selected metadata.
See [curation](feed-curation.md) for the calculation.

Publisher IDs remain configured or null. Primary-document identities and
website groups come from validated canonical URLs. No headline, article length,
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
