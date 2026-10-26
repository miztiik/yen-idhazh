# Selecting an editorial portfolio

**Last Updated**: 2026-10-26

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
When enabled, measured feed reliability reduces only the authority part:

```text
factor = max(configured reliability floor, productive / attempted)
reliability adjustment = -authority * (1 - factor)
```

The numerator and denominator follow the native feed-read rules, not article
quality or publication yield. Missing reliability produces a null adjustment
and no ranking change. A disabled known adjustment is zero. Request spend
never becomes a ranking penalty.

## Opportunity before selection

Canonical URL duplicates cannot buy more allowance. Candidates are ordered
by numeric priority with the supplied candidate identity breaking ties.
Each feed receives its configured base allowance plus at most one declared
unique-primary-evidence bonus. The witness must be absent from other feeds'
admitted evidence; no story group is inferred.

Candidates beyond that allowance receive a grouped quota exclusion.
Vertical, desk, lens, event, entity and carrier-group allowances are not
planner decisions in this format.

## Marginal choices and concentration

Each choice recomputes remaining candidates against the actual chosen set.
The retained numeric adjustments cover feed reliability, publisher exposure,
source kind and parent domain. Source kind has no admission, authority or
quota shortcut. An unavailable domain or publisher produces a null component,
not a fabricated no-overlap measurement.

Configured source and parent-domain shares bound the planned count.
The minimum-distinct-source preference and source-share cap relax only in
their configured order. The parent-domain cap does not silently disappear.
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

Only the declared metadata projection is committed. Article text remains
in the separate artifact. [Table B](../../reference/feed-planner-ledgers.md#b-selected-articles)
owns the complete field list. Partitioning adds assignments without
reranking or replacing this selection.

## Design rationale

Compact contributions explain why a chosen article ranked where it did
without preserving a second classification or audit system. Known zero
and unavailable evidence remain distinct through JSON and Parquet readback.

## See also

- [Screening](feed-screening.md)
- [Feed history](planner-feed-history.md)
- [Partitioning](feed-partitioning.md)
- [Planning completion](feed-ingest-audit.md)
