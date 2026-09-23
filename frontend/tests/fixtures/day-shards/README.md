# One day tree of writer-owned files, for the server-side walk

`item-health/2026/09/18/` is a day: two writer files, each named
`<run_id>-<attempt>-<job>-<shard>.csv`, which is the shape every state ledger
more than one job writes is in. There is no head above a day, so a `<DD>.csv`
beside these directories is a name no writer spells. `host-fingerprint/` holds a
day directory too, because the reader that asks which days a record opened has
to report one date for a day however many files the day holds.

Committed rather than built in a temporary directory, because the shape is the
thing under test and a fixture a person can open is the cheapest description of
it. An EMPTY day directory is not here: git does not carry an empty directory,
so the test that proves the walk refuses one builds it on the spot.
