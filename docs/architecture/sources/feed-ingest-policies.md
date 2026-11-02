# Feed ingest planning policies

**Last Updated**: 2026-11-02

Which settings does the isolated planner apply to a candidate?
`config/feed-ingest-plan.json` supplies one global policy. The production
Python planner, source catalog and taxonomy retain their separate behavior.

## Resolve a candidate

Load and validate authored configuration before work. Resolve any run override
into an independent effective configuration before fetching, screening,
selection and reporting. Returned policies share no mutable objects with
listener settings or other requests. Zero is a value where permitted; null is
not an inheritance instruction.

`curate_articles.global_age_ceiling_hours` defaults to 36 hours of known age
for every feed. One optional positive finite run value replaces that ceiling;
the report shows its effective value and whether configuration or the run
supplied it. Equality passes. Unknown age remains eligible with null timing
evidence and zero recency; it is not proof of freshness.
[Screening](feed-screening.md#gates-and-timing) owns the timing rule and
matching pre-download check.

There are no vertical overrides or source-tier windows/weights in this
planner. Active lifecycle status still governs source enrollment.
The same `triage.min_words` raw technical minimum applies to every article.
It is not the retained-word scoring curve and must not use its count.

Current configuration uses stamp `2026-11-02`. Older authored planner
configurations and unsupported controls fail validation, not conversion.
Retired bucket, share, relaxation, exposure and reserved-exploration controls
are errors by field name, not aliases or silently ignored settings.

## Global controls and evidence

Harvest concurrency, request controls, structured URL exclusions, blocked
categories and HTTP statuses apply to all feeds. `curate_articles.article_limit`
is the maximum number of distinct eligible URLs selected, default 100.
There is no source reservation or hard diversity cap. Partition settings
assign already chosen articles; they cannot change eligibility or capacity.

The [curation calculation](feed-curation.md#fixed-score-preparation) consumes:

- `curate_articles.source_authority_weight`, default 1.0, times `source.weight`.
- Existing `triage.recency_weight` and `triage.recency_half_life_hours`,
  default 0.6 points and 18 hours.
- `curate_articles.source_reliability_penalty_enabled`, default true, with the existing
  `collect.reliability_floor` of 0.5 and `collect.reliability_window_days`
  of 30 days. Unmeasured history contributes zero adjustment, not a measured
  zero pass fraction.
- The cached retained-paragraph score configured by `curate_articles.substance`.
  [Substance measurement](article-substance-scoring.md) owns its paragraph
  thresholds, continuous length curve, density and headline controls.
- `curate_articles.diversity.lambda_domain` and `.lambda_feed`, default
  0.04 and 0.02 points per squared prior count, and `.novelty_bonus`,
  default 0.15 points for a feed's first winner.
- `curate_articles.website_grouping.include_private_suffixes`, used when
  resolving canonical URL website identities.

These settings are active, global and validated at load. There is no
retained-word admission minimum. The existing recency and reliability keys
remain their only authorities; no duplicate curation setting substitutes for
them. Each chosen row records the five actual signed adjustments.

Publisher IDs remain configured or null metadata, not selection penalty
keys. Website groups come from validated canonical URLs. No headline,
length, byline or feed category creates an inferred classification or factual
quality verdict.

## Design rationale

One effective global policy makes every candidate comparable without subject
labels or source allocations. Source weight expresses the configured prior;
measured substance and technical delivery have separate meanings. Soft
feed/website penalties change order without leaving eligible URL slots unused.
Changing configuration changes behavior without a source edit.

## See also

- [Screening](feed-screening.md)
- [Curation](feed-curation.md)
- [Ledger fields](../../reference/feed-planner-ledgers.md)
- [Configuration](../../concepts/config.md)
