# Feed candidate screening

**Last Updated**: 2026-10-21

Which harvested articles pass the isolated planner's screening checks?
This stage does not change production planning or fetch any content.

## Inputs and result

Call `screenArticleCandidates` from
`services/feed-ingest-plan/src/screen-article-candidates/triage-gates.ts`.
It accepts one serializable candidate batch plus a rejection-ledger write
context. The caller supplies the validated planning configuration and taxonomy,
the existing `collect.max_future_hours` setting from `config/idhazh.json`,
one fixed UTC run instant, run identity and optional freshness override.
The stage validates these inputs again before writing.

Harvest observations are keyed by candidate ID. HTTP status and paywall evidence
are nullable; a missing observation is unavailable, not HTTP success or proof of
no paywall. Only observed failures cause these gates to reject. Admitted results
retain the observation and its nulls, not a claim that unknown checks passed.
Terminal harvest failures are not candidates and must not be offered again.
An observation for an ID outside the supplied batch fails by name.

The caller supplies a bounded list of settled seen rows, written by the plan
stage under the existing seen ledger, or explicitly marks that evidence
unavailable. An available empty list is not the same as unavailable history.
The focused reader validates the existing `SeenRow` fields from
`backend/idhazh/contracts/seen.py`: version, URL key, first-sight UTC instant and
first-sight run. It joins by the candidate's canonical URL key. Conflicting
settled rows fail. This stage neither
loads history nor creates a first sight from the latest fetch.

The result contains admitted candidates, typed rejection rows and the shared
writer's sealing result. Each admitted entry preserves the candidate, including
its harvested policy snapshot, and separately carries the effective resolved
policy, timing evidence and recency bonus. No candidate identity, source facts,
labels or harvested policy is rewritten. The later engine owns loading settled
history and constructing downstream assessments.

## Gates and timing

Policies resolve through the existing
[vertical policy resolver](feed-ingest-policies.md). Word thresholds use source
form, article or abstract, never source kind. Gate precedence is paywall or
configured HTTP block, configured category, word minimum, then maximum age.
Categories compare whole tags after trimming and case folding, not substrings.
The first failed gate emits one terminal rejection.

Age uses a trustworthy feed date, otherwise persisted first sight. A feed date
exactly at the configured future tolerance remains trustworthy; a later one
does not. Age exactly equal to the resolved cutoff is admitted. Greater age
records the measured hours and the cutoff. An unknown time stays null and earns
zero recency bonus; an undated repeated fetch cannot restart its age.

Recency scoring is independent of admission. It uses the effective policy's
weight and half-life with negative ages clamped to zero. A run freshness
override changes only the cutoff, not the half-life or authored configuration.
The timing source is transiently explicit as `published_at`, `first_seen`, or
`unknown`. The existing persisted assessment vocabulary cannot describe first
sight. Do not serialize it as `fetched_at`; a future assessment writer must
resolve that contract boundary before claiming persisted first-sight evidence.

## Rejection persistence

The caller supplies the trusted rejection registration, ledger settings, writer
identity and state output root. Prefix and raw compression must agree with the
planning configuration. The public `@idhazh/ledger-file-writer` API owns atomic
Parquet writes, file identity and row identity. The rejection date and coverage
come from the fixed UTC run instant, not a candidate's earlier fetch date.
A failed, invalid or skipped write cannot return successful screening.
An empty rejection batch returns the writer's explicit empty result.

## Design rationale

First sight is existing persisted evidence, not another candidate field.
Keeping it separate prevents repeated fetches from renewing old undated stories.
The named fixtures hold the small TypeScript seen read copy to the existing
field set and exercise settled rows without scanning committed state.

Real shared-writer output is read back with TypeScript WASM and Arrow against
bounded recorded screening cases. This checks rejection reason, details,
identity and UTC coverage. It does not execute or certify the current Python
reader. No test invokes Python, fetches the network or replaces the writer
with a test double.

## See also

- [Freshness and first sight](freshness.md)
- [Configuration concepts](../../concepts/config.md)
- [Ledger persistence](../contracts/persistence.md)
- [Local gates](../../how-to/run-the-gates.md)
