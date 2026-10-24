# Feed-ingest feedback

How do measured feed and article costs affect the next planner selection?

**Last Updated**: 2026-10-24

**Status**: Contract proposal; no feedback score or state writer is deployed.
The user approved separate hardware and request measures, automatic score use
after evidence qualifies, replacement of RSS reliability in the isolated
TypeScript planner, the configurable provisional score settings below, and
counting only supported source-side failures as waste. Producer fields and the
remaining D4-D5 details still need owner approval before implementation.

## Scope

This contract covers nonsemantic access, extraction and work-cost evidence.
It does not assess truth, news value, article quality or story novelty. A
technical failure changes a source's operational evidence only when its cause
is supported; a pipeline failure is not a source failure.

The historical review used compact Parquet files for seven named UTC days,
2026-10-16 through 2026-10-22: item-health, feed-health and host-fingerprint,
plus the October 22 source-run file. The backend gardener writes compacted
files from raw ledger records; the review did not count both copies. See
[ledger compaction](../publishing/ledger-compaction.md). The records contain
CPU and process-memory readings, but not article-attributed CPU time,
memory-time, a complete HTTP request count or historical publisher IDs. They
describe machine use, not which publisher caused it or how much was waste.

## Observation proposal

Keep unlike measurements separate until each has a declared unit and can be
linked to the work that caused it.

- **CPU**: exclusive operation CPU time in milliseconds, summed across cores.
  Host CPU busy percentage is not article CPU time.
- **Memory**: attributable private memory in byte-milliseconds. A process RSS
  snapshot is not the amount of memory used by one article.
- **Requests**: actual outbound HTTP requests as an integer count. Count each
  dispatched redirect or retry once. DNS checks, replayed responses and API
  calls are not outbound requests.

Each observation needs a stable event identity, source and run identity,
attempt, correlation, UTC event time, producer revision, outcome, and
attribution: `source`, `pipeline` or `unresolved`. A publisher identity is
included only when the producer recorded a confirmed curated ID. Do not fill
historical gaps from today's source catalog.

Count an operation's cost as waste only when it failed to produce usable
material for a supported source-side reason. Keep costs from successful
operations, pipeline failures and unresolved causes as evidence, but do not
deduct them from a publisher. A failed article alone does not prove its CPU,
memory or requests were wasted by the source. Shared setup costs stay at their
actual scope and are not copied onto each article.

Use distinct keys for article opportunities, operations and HTTP requests.
Retries increase request work, not the number of article opportunities.
Replaying an observation does not add support. A genuinely repeated operation
retains its real additional cost.

## Proposed score

For each supported measure, sum the raw wasted amount and total attributable
amount before dividing. Do not average article ratios.

```text
component_waste = wasted_amount / total_amount
component_waste is in [0, 1]

penalty = min(1, sum(component_weight * component_waste))
priority = editorial_priority - (source_authority_contribution * penalty)
```

The proposed component weights are one third each for CPU, memory and requests.
These are simple provisional weights, not values calibrated by the historical
records. The value 1 means all measured work in that component was classified
as waste; it is the normalization endpoint, not a historical percentile.
The combined penalty cannot exceed 1.

Do not mix raw CPU, memory and request values. Normalize each component first.
An unavailable component remains `null` and is not given extra weight through
renormalization. If no component has supported evidence, the combined penalty
is `null` and makes no score change. A measured zero is different: it requires
a known nonzero denominator and no observed waste.

The score change applies only to the source-authority contribution. It keeps
the curated source weight and tier. It replaces the existing RSS reliability
penalty; it does not add a second operational penalty. Unknown or insufficient
evidence does not demote a source. Once configured evidence rules pass, the
supported penalty applies automatically.

## Provisional evidence settings

The owner approved these provisional configuration values. They are policy
defaults, not measurements learned from the historical records:

- A seven-day window of closed UTC days.
- At least 20 distinct measured article opportunities for a component.
- At least 80 percent coverage of attempted opportunities for that component.
- Equal one-third weights for CPU, memory and requests.

Below the support or coverage requirement, preserve the readings as
unqualified evidence and do not apply that component. The historical CPU,
memory and retry fields cannot calibrate these settings: CPU and memory are
not source-attributed waste, and retry fields are not a complete request
census.

## State and settlement proposal

Use one serialized writer and the existing registered ledger. Do not add
another permanent retirement authority or discover history by walking a
growing directory. Pin the code and policy used for a decision while reading
the latest compatible state.

Settle each event once by its stable identity. A correction replaces the
earlier contribution for that identity and signal. A failed commit does not
advance the state checkpoint. Missing or incompatible state stays unknown; it
does not become an empty history or clear a restriction. A bounded catch-up
limit, overlapping-run behavior and exact checkpoint fields remain open in
the plan's D4 decision.

## Acceptance examples

- Replaying the same request event adds no request cost or article support.
- Three actual retry requests add three requests but remain one article
  opportunity.
- A pipeline parser failure retains its cost without lowering publisher
  priority.
- A known denominator with no waste records zero; a missing denominator is
  unknown.
- If only requests have supported evidence, CPU and memory stay `null`; their
  missing values do not increase the request weight.
- If all supported components are fully wasted, the penalty is 1 and the
  operational part of priority is reduced to zero.
- An unknown historical publisher remains unknown rather than inheriting
  today's feed mapping.

## Open contract decisions

- D3: define the producer fields and exact operation-to-cost bindings. The
  source-side failure rule and provisional window, support, coverage and
  component weights are approved.
- D4: set the bounded catch-up limit, correction key and checkpoint fields.
- D5: set the evidence rules that trigger automatic use of a score, plus the
  separate limits and authority for trials, restrictions, recovery and polling.
- D6: the 0.25 coefficient and replacement of feed crowding are approved; the
  exact exposure normalization and history fallback remain open in the
  curation contract.
No implementation may treat these proposals as approved behavior.

## Design rationale

The owner asked for a score that can reduce priority when measured operational
waste is high, with the combined penalty capped at 1. Separate units are
required because machine work and network requests are different facts. A
normalized score can combine them only after the evidence identifies both the
cost and the work that caused it. Historical host readings alone cannot support
that attribution.

Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: count cost as waste only
when an operation fails to produce usable material for a supported source-side
reason. Keep CPU, memory and request costs separate, normalize each before
combining, and apply the penalty automatically only after evidence qualifies.
Use configurable provisional defaults of a seven-day UTC window, 20 distinct
article opportunities, 80 percent measured coverage and equal one-third
component weights. These values are not calibrated by the historical data.

## See also

- [Publisher identity](publisher-identity.md) - curated publisher IDs and
  historical unknowns.
- [Source curation](../sources/feed-curation.md) - selection score and
  publisher exposure.
- [I Feed](../sources/i-feed.md) - proposed source feedback and allocation.
- [Operator requests](../sources/feed-operator-api.md) - fetch, parse and
  selection request behavior.
- [Schema ownership](schemas.md) - persisted payload owners and migrations.
