# Observation Lookup

**Last Updated**: 2026-10-03

How evaluation membership stays exact without reading the full history of recorded IDs.

## Measurement identity

One observation is the canonical JSON encoding of
`(url_key, output_digest, scorer_version)`, hashed with SHA-256. The article key,
summary output and scorer identify the measurement. Pipeline version, date, run
and item slot do not. A changed output or scorer is a new measurement; a later
run of the same measurement is not. This prevents duplicate measurements, not
duplicate news stories, and does not shorten the life of a summary.

## Physical layout

The lookup and pending inputs live under `state/summary-quality-evals-index/`:

```text
lookup/root.json
lookup/nodes/<first-two-digest-digits>/<content-digest>.json
lookup/nodes/<first-two-digest-digits>/<content-digest>.sqlite
incoming/<batch-id>.json
```

One fixed root names the current tree and pins its key fields and physical settings.
Routing pages are JSON with at most 16 children. Leaves are SQLite files. Both are
content-addressed: their names come from their SHA-256 bytes, and reads verify the
digest. Observation IDs and applied batch receipts occupy separate namespaces in
the same tree. A receipt records which input batch was applied and its accepted
output; it is not another evaluation row.

The routing key is a SHA-256 digest of the namespace and identity. Its 64
hexadecimal digits limit routing to at most 64 steps. Each step selects only the
children needed by the incoming keys. A membership query reads only those leaves
and uses SQLite's primary-key B-tree, not a scan of historical IDs.

## Bounds and costs

[config/observation-lookup.json](../../../config/observation-lookup.json) sets
`max_leaf_bytes` to 262144 bytes (256 KiB) and `sqlite_page_bytes` to 4096 bytes
(4 KiB). These are provisional chosen bounds, not benchmark results. The leaf cap
must hold at least four SQLite pages and be a whole multiple of the page size.
An overflowing leaf splits on the next routing digit. An entry that cannot fit
alone fails rather than exceeding the cap.

The persisted root supplies the settings for later reads and writes. Editing
config does not repartition an existing tree. Routing pages have bounded child
counts and are also checked against the root's node byte limit when read.

Python's standard-library SQLite adds no package dependency. A read copies a
bounded leaf into SQLite memory. An update rebuilds the touched leaves and their
ancestors; Git records the changed SQLite files as binary blobs. This bounds
membership work for a fixed incoming batch, not repository size or all Git work.
A full checkout or fetch can still grow with repository history.

There is no day or month fold, age deletion, or look-back window for membership.
Compacting evaluation rows does not forget their IDs.

## Local atomicity

The writer takes a local SQLite lock and writes new nodes before atomically
replacing `root.json`. A changed tree must have a new generation. Existing entries
cannot be replaced with different values.

The local `.transaction.json` names the old and new generations and only the
created and superseded nodes. Recovery removes the superseded nodes if the new
root landed, or the created nodes if the old root remains. A node shared by both
generations survives either outcome; a split can reuse an existing leaf as a
child. A different generation fails. Recovery does not walk the tree to discover
files. The lock and transaction are local coordination files, not published
lookup nodes.

The six persisted envelopes are declared in
[observation_lookup.py](../../../backend/idhazh/contracts/observation_lookup.py)
and listed in [schemas.md](schemas.md).

## Publication across jobs

The producer seals the original rows and writer identity in
`backend/var/evaluation-inputs/batches/<batch-id>.json`. Its per-job manifest,
`backend/var/evaluation-inputs/<run-id>/<job>-<shard>.json`, names those batches
and the paths prepared from them. Both are ignored local files. The batch ID
binds the original identity and payload digest; it does not name a lookup
generation.

Before the final publication, preparation commits missing batches to
`incoming/<batch-id>.json` through an isolated, sparse shared clone. This leaves
the producer's checkout untouched. The clone materializes only named inputs
and the routes needed to check their committed receipts. A local, uncommitted
receipt is not proof of publication. A group containing new inputs costs about
one extra Git commit; already pending or receipted inputs need no extra inbox
commit. Git fetch cost is still separate from bounded membership work.

Preparation applies the original batches against the current root and accepts
only unseen measurement IDs. Accepted raw rows, changed lookup nodes and root,
batch receipts, and deletion of the corresponding pending inputs land in one
commit. A batch with no new measurements still gets a receipt. Replay preserves
the batch's original run, attempt, job and shard; the output producer gets a
batch-specific suffix so its files remain distinct.

Raw files are first staged under the ignored batch directory. Before any raw
file or index node enters the state tree, its exact path is recorded for retry.
A local receipt names the staged output. If a process stops before the lookup
receipt lands, recovery removes only that batch's abandoned raw files and
rechecks its full input. A committed receipt keeps its accepted output. Partial
multi-day writes follow the same rule; recovery does not list historical files.

A rejected push must read the winner's root and reapply the original batches.
The [shared preparation hook](../publishing/committing.md#preparation-names-this-attempts-derived-files)
restores the previous attempt's named derived paths, rebases, runs any producer
regeneration, then prepares again. It never text-merges lookup generations.
A concurrency group that drops jobs is not part of this protocol.

After an inbox push succeeds, a failed final publication leaves durable pending
input or a committed receipt if another attempt already applied it. A matching
receipt prevents a second row write. Receipt output paths record provenance at
acceptance; compaction may later replace those files. Replay does not recreate
them merely because they are gone.

A missing root with existing evaluation history stops the writer and requires
the [explicit migration](../../how-to/migrate-observation-lookup.md). Routine
writing never scans history as a fallback.

## See also

- [../../how-to/migrate-observation-lookup.md](../../how-to/migrate-observation-lookup.md) - approved cutover and named pending-batch recovery.
- [persistence.md](persistence.md) - evaluation rows and their storage owner.
- [../publishing/committing.md](../publishing/committing.md) - commit and push retries.
- [../../../CLAUDE.md](../../../CLAUDE.md) - fixed-size inputs for repository reads.
