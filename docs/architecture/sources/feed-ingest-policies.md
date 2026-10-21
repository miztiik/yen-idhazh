# Feed ingest planning policies

**Last Updated**: 2026-10-21

Which settings does the isolated feed planner apply to a candidate?
The operator edits `config/feed-ingest-plan.json`. This does not change the
production Python planner or its workers.

## Resolve a candidate

Load the authored configuration and `config/taxonomy.json` with
`loadPlanningConfig` before a run. Unknown fields, unknown vertical references,
invalid numbers, and duplicate taxonomy vertical IDs fail loading by name.
The Python reader is `FeedIngestConfig` in
`backend/idhazh/contracts/knobs/feed_ingest.py`; call `validate_verticals` with
`PlanningTaxonomy` after validation. The TypeScript copies are in
`packages/common-contracts/src/schemas/config.schema.ts` and `policy.schema.ts`.
These are authored settings, not a persisted policy ledger.

Call `resolvePolicy` with the loaded configuration and the feed's configured
vertical, its subject grouping. Resolution applies global screening and scoring
settings, then that vertical's partial patch, then the optional run
`freshness_hours`. That last value changes only the maximum age for this run.
Missing nested penalty coefficients inherit individually. Omitted fields inherit;
zero is a value where allowed; null is not an inheritance instruction.
Returned values do not share mutable objects with the loaded configuration.

The global minimum is 180 words for an article and 60 words for an abstract.
The maximum age is 24 hours, separate from the 18-hour recency half-life that
affects ranking. Word minima are positive integers; age and half-life are
positive finite numbers. Recency weight, authority weight, allowances, bonuses,
and penalty coefficients are nonnegative, with allowances and bonuses integral.
An absent run freshness value preserves the resolved vertical cutoff.
These are configuration defaults, not measured editorial optima.

## What a vertical can change

`vertical_overrides` maps configured vertical IDs to partial `triage` and
`curate` policies. It can change word minima, maximum age, recency half-life and
weight, source authority weight, source allowance and its three evidence-backed
bonuses, and each named coefficient in `mmr_weights`.

The independent penalties cover source, source kind, parent domain, original
vertical, assigned desk, lens, event type, event cluster, entity, and repeated
coverage. Their meaning and evidence owners remain in
[taxonomy](../../concepts/taxonomy.md) and
[story similarity](../publishing/autotune-content-similarity.md).
Source kind has only a configurable diversity penalty, initially at most
0.05 score points. It cannot choose an age or word threshold.

A desk is where a story is published, not the feed's vertical. The existing
desk floor, ceiling, and placement settings remain independent. An unknown desk
stays unknown. Lens matcher weights, event matching, event-cluster grouping, and
entity/watchlist rules also retain their existing owners. Resolving a policy
does not invent these labels or implement their later scoring consumers.

## Global-only settings

Harvest concurrency, timeout, user agent, and blocked feed categories stay
global. Blocked HTTP statuses are also global, not a vertical eligibility patch.
Portfolio-wide article limit, share limits, minimum source target, cap relaxation
order, and exploration share apply to the whole selection. A null article limit
means no additional run-wide cap. Partition settings, storage prefixes and
compression, and metrics windows are not candidate policies.

`workflow_reporting.enabled` defaults to false and controls only the external
reporting adapter. It must not disable planning, events, metrics, or ledger
writes. Its removal condition is recorded beside the key in configuration and
on its Python and TypeScript declarations: remove the key, adapter, tests, and
workflow invocation together when development reporting is no longer needed.
This row does not add that adapter.

## Design rationale

Typed patches keep per-candidate choices separate from whole-portfolio limits.
Changing one vertical cannot assign contradictory global limits to a shared
selection. Adding a taxonomy vertical and its planning patch needs configuration
edits only; a new algorithm still needs code. No label-specific branches or
expression language are used.

The bounded policy tests compare exact resolved values under single-field
changes, preserve other verticals, and check run precedence and inheritance.
The config binding test compares Python and TypeScript fields, types,
constraints, and vocabularies. These checks prove policy resolution, not article
admission, final ranking, or CLI/API execution.

## See also

- [Configuration concepts](../../concepts/config.md)
- [Local gates](../../how-to/run-the-gates.md)
- [Contract schemas](../contracts/schemas.md)
