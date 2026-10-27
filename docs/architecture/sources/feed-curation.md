# Selecting an editorial portfolio

**Last Updated**: 2026-10-27

How does the isolated planner choose articles from the admitted batch?
It uses configured numeric rules and explicit factual evidence, not a model
or an inferred subject classification.

## Inputs and independent evidence

Curation receives admitted candidates, their global effective policy,
publication or first-sight timing and current feed history. Publisher IDs
come only from the curated catalog. Parent domains, primary-document
identities and work estimates must be supplied as explicit evidence.
Unknown stays null; source titles and article prose do not fill it.

The base score is the recency contribution plus configured feed authority:
authority coefficient times feed weight times applied tier weight.
When enabled, measured article technical admission reduces only the authority part:

```text
factor = max(configured reliability floor, admitted / (admitted + source refusals))
article-pass adjustment = -authority * (1 - factor)
```

The numerator counts original captures that pass access, extraction, required
fields and minimum words. The denominator adds source-attributed technical
refusals, not publication, age, category, content-policy or selection losses.
Missing or incomplete evidence, or a zero denominator, produces a null
adjustment and no ranking change. A disabled adjustment is zero. RSS-read
reliability governs access/rest separately; it never substitutes for this rate.

## Targets, fresh buffers and older deficits

The saved request's `article_limit`, or the configured default, is a positive
finite safe integer. `curate_articles.feed_quality_tiers` declares each tier's
share, additional fresh buffer and increasing age steps. Configured list order
sets priority; numeric tier IDs do not.

Largest-remainder allocation makes integer targets sum to the requested limit,
breaking ties by tier order. Fresh ceilings round upward from share plus buffer,
never below the allocated target. Counts are based on the requested limit, not
candidate supply. No fixed feed allowance or shortlist trims the complete input.

Choose fresh articles up to each target first, then remaining fresh articles
up to each ceiling. Only then open older steps for tiers below target. Older
articles fill targets, never buffers. Re-enter phase priority after each winner
or permitted relaxation, using the same full selected set and exposure counts.
Shortages do not authorize exceeding ceilings.

Canonical URL carriers stay available until one actually wins. A capped carrier
cannot remove a viable carrier from another feed. Identity breaks score ties;
labels and primary-document evidence buy no additional capacity.

## Marginal choices and concentration

Each choice recomputes remaining candidates against the actual chosen set.
The retained numeric adjustments cover article technical admission, publisher exposure
and website-group exposure. Website groups are recomputed from canonical URLs
using the configured private-suffix rule; supplied hints cannot override
them. Feed kind, form and other classification labels do not affect admission,
authority or ranking. An unavailable group or publisher produces a null
component, not a fabricated no-overlap measurement.

Configured source and website-group shares bound the planned count.
The minimum-distinct-source preference and source-share cap relax only in
their configured order. The website-group cap does not silently disappear.
Exploration reserves its configured final share, rounded down, for viable
feeds not yet represented. It bypasses no admission or cap.

### Publisher exposure adjustment

Genuine published and item-health evidence may link actual publisher
exposure for the current UTC day. Selected rows are never publication
evidence. Missing linkage uses the explicit current-selection fallback,
with a distinct recorded adjustment term. Unknown publisher IDs remain null.

## Persistence and verification

One chosen content population supplies compact metadata and the selected
text artifact. Each article retains its rank, actual base and marginal
scores, signed adjustments, tier/weight, work estimate, timing and the quota
or exploration exceptions used. No full policy, assessment or losing-score
tree is copied.

`feed_limit` records the per-feed share limit computed from requested output.
`freshness_cutoff_at` records the admitted age window against the saved age
clock; unknown age has no invented cutoff. Every unchosen parsed candidate
receives one terminal metadata row in `rejected-articles`, after all permitted
phase changes and relaxations. Screening refusals precede numeric selection;
winning duplicates precede closed older windows, global capacity, distinct-feed,
feed-share, website-share and fresh-ceiling refusals, in that order.

Only the declared metadata projection is committed. Article text remains
in the separate artifact. [Table B](../../reference/feed-planner-ledgers.md#b-selected-articles)
owns the complete field list. Partitioning adds assignments without
reranking or replacing this selection.

## Design rationale

Compact contributions explain why a chosen article ranked where it did
without preserving a second classification or audit system. Known zero
and unavailable evidence remain distinct through JSON and Parquet readback.

### Configured priority review

**Adopted behavior, unchanged:** Keep the numeric selection described above,
including separate article-pass and publisher-exposure adjustments. This
review adds no score term, matcher, config default or persisted field.

Maintainers write watchlist aliases in
[`config/watchlist.json`](../../../config/watchlist.json), theme keywords and
weights in [`config/taxonomy.json`](../../../config/taxonomy.json), and Python
bonus amounts in [`config/idhazh.json`](../../../config/idhazh.json).
The Python [planning stage](../../../backend/idhazh/stages/plan.py) matches
whole-word phrases against feed headlines through
[`tag.py`](../../../backend/idhazh/tag.py), not article bodies. A configured
theme is called a lens in that configuration.

#### Table A - Compared priorities, not approved additions

| Id | Priority | Python behavior | Current TypeScript finding |
| --- | --- | --- | --- |
| A1 | Watchlist attention | Add 0.5 score points once when an alias of any non-retired entity matches; multiple matching entities do not add more. | The retained title is available, but no watchlist match is recorded or scored. An alias hit would show configured attention, not article quality. |
| A2 | Configured theme | Add only the largest positive weight among matched non-retired themes, not their sum. | Original feed categories are retained strings, not recorded matches to curated themes. No theme bonus or inferred classification is present. |
| A3 | Repeated canonical URL | Add 0.25 score points once when multiple carriers supply the same canonical URL; further carriers add nothing. | Feed IDs and URL identities are available before duplicate removal, but no carrier witness or bonus is retained. Repeated carriage measures syndication of one address, not independent reporting or story agreement. |

The [Python score](../../../backend/idhazh/rank.py) applies those rules.
The [current TypeScript selection](../../../services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts)
does not. Its [maintainer-authored config](../../../config/feed-ingest-plan.json)
sets the authority coefficient to 1.0 and the maximum recency contribution to
0.6 score points. Copying Python's 0.5 or 0.25 points can change selection;
those amounts are not neutral or approved TypeScript defaults.

The [candidate](../../../packages/common-contracts/src/schemas/candidate.schema.ts)
retains title, categories, article text and feed facts.
[Additional article evidence](../../../packages/common-contracts/src/schemas/planner-stage.schema.ts)
contains only parent domain, primary-evidence identities and estimated work.
Missing matches or carrier witnesses are not measured zeroes.
[Selected metadata](../../reference/feed-planner-ledgers.md#b-selected-articles)
records actual adjustments as `term` and `value`; accepting a term name does
not approve its meaning.

**Recommendation, not approval:** Keep current ranking while the priority
decision is pending. This gives watchlist, theme and repeated-URL inputs no
extra priority; it does not close the remaining priority work.
Before adding a term, obtain approval for its exact input and matching rule,
independent meaning, config maintainer and default, no-double-counting rule,
score evidence and current-reader-before-writer sequence. No proposed priority
term, matcher or default has approval. Front-page votes, inferred
classifications and a wholesale Python-ranking port are not authorized by
this comparison.

## See also

- [Screening](feed-screening.md)
- [Feed history](planner-feed-history.md)
- [Partitioning](feed-partitioning.md)
- [Planning completion](feed-ingest-audit.md)
