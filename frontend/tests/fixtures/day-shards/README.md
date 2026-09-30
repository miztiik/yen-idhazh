# One day tree of writer-owned files, for the server-side walk

`item-health/2026/09/18/` is a day: two writer files, each named
`<run_id>-<attempt>-<job>-<shard>.csv`, which is the shape every state ledger
more than one job writes is in. There is no head above a day, so a `<DD>.csv`
beside these directories is a name no writer spells. The console now reads the
article record from its packed files, so this tree stands for the ledgers that
still file by day - feed health, the span rollup and the similarity judge's two
trees - which share the one walk.

Committed rather than built in a temporary directory, because the shape is the
thing under test and a fixture a person can open is the cheapest description of
it. An EMPTY day directory is not here: git does not carry an empty directory,
so the test that proves the walk refuses one builds it on the spot.
