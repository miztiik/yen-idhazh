# Feed candidate screening

**Last Updated**: 2026-10-24

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
The public harvesting result includes observations for terminal failures too.
Build the keyed screening input only from entries with a candidate, not entries
with a rejection. Screening preserves the full public observation, including
robots, extraction, paywall evidence and failure availability.

The caller supplies a bounded list of settled seen rows, written by the plan
stage under the existing seen ledger, or explicitly marks that evidence
unavailable. An available empty list is not the same as unavailable history.
Available means supplied validated rows, not proof of complete history.
For a genuinely new undated item, the caller must create and supply its real
first-sight row at the run instant after resolving history. An absent URL in an
arbitrary bounded list cannot establish that the item has never been seen.
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

Before any article request, the isolated TypeScript harvester checks
`harvest.url_exclusions` in `config/feed-ingest-plan.json`. Each validated rule
names a host, a path prefix and whether subdomains are included. Hosts compare
without case; subdomains must end at a dot boundary. Paths compare with case
and match the prefix itself or its descendants at a slash boundary. A root
prefix matches all paths on that host. Queries and fragments do not participate.
Rule paths have no trailing slash except the root and cannot contain a query,
fragment or dot segment.

The committed `fool.com` rule includes subdomains and `/the-ascent` descendants.
It keeps affiliate-product pages out without rejecting unrelated articles that
mention that address in a query. Other reporting on the host stays eligible.
This preserves the editorial exclusion, not a new assessment of article quality.
Changing or removing that editorial scope needs owner review.

The harvester and the planning audit use one pure structured matcher. A match
retains `BLOCKED_URL_MARKER`, the existing `fool.com/the-ascent/` detail and the
unchanged canonical URL hash. It records no attempted article fetch. The rule
also applies when harvesting is called without publication or failure history.
This correction changes only the isolated TypeScript path. Python still reads
its existing marker configuration; URL identity and query cleanup are unchanged.

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
