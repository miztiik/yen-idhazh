# Why a losing push rebuilds rather than rebases

**Last Updated**: 2026-10-09

Run `35896533328` exposed the wrong abstraction: a shallow assemble checkout
rebased across a squash merge and reported 111 add/add conflicts, including
code and documentation the job never wrote. Deepening every checkout would
pay for history without making a data producer own those paths.

## A candidate is a tree, not a patch

The owner-approved publisher builds a private index from fresh main, applies
only independently declared, confirmed operations, verifies their actual blobs
and modes, and creates a candidate with that main as its sole parent.
The checkout's HEAD, index, sparse patterns and foreign files never move.
No reset, checkout, stash, broad staging or text conflict settlement is needed.
Shallow clones stay shallow; ordinary publication never force-pushes.

Reparenting is not permission to overwrite a changed target. Immutable identities
refuse different committed bytes. Conditional replacements and deletions require
their source entries to remain unchanged, unless the caller owns an explicitly
bounded preparation scope. Gardener skips an entire stale shard. Council never
reruns judges. Digest ASSEMBLE rebuilds derived files from fresh named inputs and
completed artifacts, without rerunning models or unioning rolled corpus snapshots.

## See also

- [committing.md](committing.md) - the request, policies, outcomes and retry controls.
- [one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md) - retain the already-published asset.
- [../../reference/github-actions.md](../../reference/github-actions.md) - collecting jobs and ordinary pushers.
