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

## Design rationale

The owner authorized this migration on 2026-10-20 as part of Plan 66.
Readers expand before configuration and consumers migrate. Closed live lookups
are removed only after their consumers move. Historical read rules stay.
No committed archive payload is rewritten.

## Verification

`backend/tests/contracts/test_source_classification_history.py` reads named
historical payload fixtures and checks the open identifier shapes. The fixture
`tests/fixtures/source-classification/legacy-ledger-rows.json` preserves old
numeric tier cells and source-kind strings.

## See also

- [../contracts/schemas.md](../contracts/schemas.md)
- [../../concepts/taxonomy.md](../../concepts/taxonomy.md)
