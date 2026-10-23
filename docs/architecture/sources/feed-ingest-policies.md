# Feed ingest planning policies

**Last Updated**: 2026-10-23

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
entity/watchlist rules retain their existing owners. Resolving a policy does
not invent labels.

## Headline observations and their consumers

The native harvest reads the named `config/taxonomy.json`,
`config/watchlist.json`, and `config/sources.json` files that the operator
curates. The service settings name the watchlist file explicitly. Its input
fingerprint includes the validated aliases, lens terms and weights, lifecycle
states, and optional salience feeds. An alias or weight edit changes the next
run without a source edit.

The original sanitized feed headline, not the fetched article body or a
fallback page title, supplies planning lens and entity matches. The matcher
uses the existing Python `tag.py` rule: lowercase ASCII words, punctuation
converted to spaces, and whole-phrase matching. Only explicit curated terms
match; ids and display names supply no aliases. Retired entries do not match;
draft entries retain the Python deterministic match rule. All matched ids are
sorted and retained. The strongest positive-weight lens is recorded separately,
with the larger lens id winning an equal-weight tie, as in `stages/plan.py`.

Known headline matches fill `candidate.labels.lenses` and `entities`, with
`sanitized-feed-headline` origin and a matcher version. No match is a known
empty list. No original headline or no supplied vocabulary is unknown, not a
negative observation. Assigned desk, event types and event cluster remain
unknown; a headline match is not a later full-article tag or classifier verdict.
Publisher, parent domain, operational history, primary evidence and prior
coverage also remain unknown unless their existing evidence owner supplies them.

These lists now reach the existing MMR lens and entity repetition penalties.
MMR selects the next article after subtracting configured overlap penalties.
Its formula, coefficients, source allowances, quotas and caps are unchanged.
Replacing unknown lists with real matching lists can change selection order:
an article repeating a previously selected headline theme or entity can lose
to a different article under the same coefficients. The existing recorded
harvest/portfolio cases prove this change while keeping recency and authority
components identical. Zero coefficients still disable that influence.

Optional salience feeds use the same per-run permitted fetcher and response
cache as article sources. DNS, address, redirect, robots, timeout and body
limits remain in that fetcher. Parsed links are canonicalized only as vote
identities, never requested, used as paths, or admitted as new candidates.
Their readings do not add article-source outcomes, rejection rows, or sources
to an audit denominator.

Each existing candidate records per-feed votes and availability. A failed,
inactive, unconfigured, or unobserved optional input carries a reason and a
null vote, not a false vote. A successfully parsed empty feed is a measured
negative. The combined front-page observation is known only when every
configured feed was read successfully. Partial successful votes remain visible
beside failed readings without claiming complete coverage.

Candidate and dispatch contracts independently advance to `2026-10-23`.
Old candidates migrate with null planning observations; old dispatches retain
their separate selection version and migrate their nested content. Historical
logical proofs encode the original candidate and dispatch stamps and omit
only the absent new observations. They refuse to discard a measured new
observation. Existing diagnostic and exclusion fields are not changed.

The API/CLI summary exposes these observations and names their actual
consumer. Selected dispatches retain them beside the full article. There is
**no native salience-vote, watchlist-bonus, or lens-weight-bonus consumer**.
The best weighted lens and votes are audit evidence only, not extra score
terms. This is real headline input wiring, not full Python ranking parity.
Python's base ranking and the approved native recency-plus-authority formula
remain different. The smallest further change needs an owner decision naming
the intended vote consumer; do not add a bonus or repurpose primary evidence
or coverage to consume it.

## Global-only settings

Harvest concurrency, timeout, user agent, and blocked feed categories stay
global. Blocked HTTP statuses are also global, not a vertical eligibility patch.
Portfolio-wide article limit, share limits, minimum source target, cap relaxation
order, and exploration share apply to the whole selection. A null article limit
means no additional run-wide cap. Partition settings, storage prefixes and
compression, and metrics windows are not candidate policies.

`workflow_reporting.enabled` defaults to true and controls only the external
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
