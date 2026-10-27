# Source classification

**Last Updated**: 2026-10-20

How source kinds and authority tiers remain readable when their membership changes.
Feed discovery is described in [discovery.md](discovery.md).

## Recorded identifiers

A source kind describes the publisher. A source tier identifies its authority
weight. Neither assigns an article's vertical, publication desk, lens or event.

Recorded kinds are open slugs. Recorded tiers are strict positive integers.
Existing tier cells remain integers and existing kind cells remain strings,
including in Parquet. A historical payload does not need membership in the
current registry. Its recorded score is not recalculated.

An omitted kind on an old published item still means `reporting`; an omitted
tier on an old entity feed still means `1`. These are historical read rules,
not the defaults for newly loaded configuration.
Rewriting an old taxonomy retains the absence of registry fields that its
writer did not record; it does not add empty registries or null defaults.

## Design rationale

The maintainer authorized this migration on 2026-10-20 as part of Plan 66.
Readers expand before configuration and consumers migrate. Closed live lookups
are removed only after their consumers move. Historical read rules stay.
No committed archive payload is rewritten.

An active feed must use a tier that is active in the taxonomy, because its
weight is part of source ranking. A new tier therefore needs a registered
active ID and numeric weight before any active feed can use it; configuration
loading refuses an unregistered tier instead of guessing.

## Live configuration

`config/taxonomy.json`, edited by maintainers, owns `source_kinds`,
`source_tiers`, `default_source_kind` and `default_entity_tier`. Kind entries
declare `display_name`, lifecycle, `show_on_item`, `counts_as_reporting` and
`requires_reporting_for_lead`. Tier entries declare a display name, lifecycle
and a finite weight from zero to one. Stable IDs are retired, never reused.

The loader checks unique registry IDs, active live references, configured
defaults and source vertical references before fetching. It supplies omitted
kind and entity-tier defaults from that registry and binds tier weights to the
ranking configuration. Contract modules never open configuration files.

Current configuration has no `collect.tier_weights`. The explicit historical
reader retains the old named weight block and its omitted-field defaults, but
refuses a conflict with a supplied registry. Those fixed defaults describe
historical input only. It never writes that legacy block back. Missing live
weights fail by tier ID. The feed probe uses configured defaults for an
unregistered address; corpus reconstruction resolves retired feed IDs too and
uses the lowest configured active weight only for an unknown historical feed.

A new kind or numeric tier needs configuration edits only. The existing weights
remain 1.0, 0.6 and 0.3 for IDs 1, 2 and 3. New IDs have no numeric ordering
meaning. An announcement still needs reporting on its subject before it may
lead; those two properties now come from the registry, not kind-name branches.
Unknown historical kinds cannot count as reporting and need corroborating
reporting before leading.

The browser builds its label and display map from that same committed
registry. Unknown historical kinds show their stored ID with an explicit
"unregistered source kind" label. Retired kinds keep their configured label.
There is no runtime server.

Planning policy overrides belong to the later planner-configuration row, not
this migration. No extraction format, article labels or production workflow
changes here.

## Verification

`backend/tests/contracts/test_source_classification_history.py` reads named
historical payload fixtures and checks the open identifier shapes. The fixture
`tests/fixtures/source-classification/legacy-ledger-rows.json` preserves old
numeric tier cells and source-kind strings.

`test_source_classification_binding.py` checks Python/TypeScript fields,
registry-driven labels, configuration-only extension through the real ranker
and publication adapter, defaults and named configuration refusals.

## See also

- [../contracts/schemas.md](../contracts/schemas.md)
- [../../concepts/taxonomy.md](../../concepts/taxonomy.md)
