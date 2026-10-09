# How completed output reaches the repository

**Last Updated**: 2026-10-09

Gardener, council and digest use one ordinary publisher:
[`backend/utilities/publish_to_repo.py`](../../../backend/utilities/publish_to_repo.py).
It builds a private candidate on fetched `main`, not a commit or rebase in the
caller's checkout. HEAD, the caller's index and sparse patterns do not move.
The workflows are described in [GitHub Actions](../../reference/github-actions.md).

## Evidence is not permission

An internal `PublicationRequest` carries the existing `WriterIdentity`, the
actual source data revision, independent write/delete declarations, confirmed
write hashes and modes, and source entries for completed deletions.
Declarations come from tasks, the ledger registry or registered tenants.
`state`, `state/raw` and `state/compact` are refused as permissions.

The version `2026-10-09` `PublicationReceipt` holds only identity and exact
`relative-path -> SHA256` writes. It is an invocation artifact under `backend/var`,
not a publication ledger or authority to stage anything. Raw envelopes must
identify the run, attempt, job, shard and code revision that actually executed.

Every retry checks worktree evidence, filtered Git blobs and candidate entries.
Only mode `100644` is accepted. Literal paths, whole-segment permissions,
symlink/junction parents, executable/submodule conversions, disjoint operations
and the absence of foreign candidate changes are checked before pushing.
Pre-staged files never ride along.

## The caller owns recovery policy

| Caller | What a newer main permits |
| --- | --- |
| Gardener | Reapply exact operations only while every target matches its source; otherwise skip the whole shard, including its record. Never rerun tasks. |
| Council | Reparent completed immutable bytes; refuse a different committed blob at the same UUID. Mutable tenant files need unchanged baselines. Never merge text or rerun judges. |
| Digest PLAN/WORK | Preserve raw files and replay only named inventory changes through the existing inventory writer. Imported tip state is a baseline, not generated output. |
| Digest ASSEMBLE | Preserve completed raw/fragments/items, retain an already-published asset for the same item, and regenerate the complete derived set against fresh named inputs. No model regeneration. |

ASSEMBLE rolls actual incoming completed corpus rows into the latest corpus with
`corpus.roll`, deduplication, the configured row window and a checked census.
Two rolled snapshots are never unioned. A failed rebuild publishes no partial
derived set. The final site build reads the observed published tip's named
inventory inputs. Permanent readers also receive older compact heads named by
their three existing indexes; they are not reduced to a calendar window.

The collecting council job serves any number of judges/shards. Later tenants
and dates still run after a task failure; completed output can land while that
task failure keeps the job red. No tenants means no row and no commit.
Sparse tenant inputs are resolved separately, from named paths/periods/indexes
in the chosen source tree; an unavailable blob is an error, not absence.

Measurement, qualification and vector backfill are the additional genuine
clients, through `record_publish.py`. Each observes its real producer and has a
separate concrete declaration; none retains another publication engine.
Pipeline tests are a fourth additional client: `pipeline_test_publish.py`
checks exact downloaded artifacts, executed raw identities and independently
declared case roots before invoking the same publisher. Empty artifacts publish
nothing; committed UUID collisions and foreign local bytes are refused.

## The deadline bounds retries

`config/push-retry.json` supplies monotonic job deadlines and configured backoff.
An optional limit counts actual pushes, not preparation/fetch iterations.
Candidates have one parent: the fetched main used to build them. Ordinary
non-force pushes name the candidate SHA and main explicitly, with `--no-thin`.
A failed or uncertain push is verified against **all** exact operations; one
matching record does not prove publication.

Results distinguish `landed`, `already-on-main`, `no-changes`, `stale`, `lost`,
`integrity-refused`, `refused` and `preparation-failure`, with candidate/base/tip,
push count, refusal paths and preparation status. Integrity exits 2.
Unpublished council/digest work exits 1. Gardener deliberately warns and exits
0 for stale/lost work, meaning SKIPPED rather than published; refusal exits 3.
Producer failure remains separate: gardener may publish completed diagnostics
after exceeding its download ceiling and still exits 1.

## Design rationale

Owner-approved on 2026-10-09: reuse gardener's private-index, exact-change,
sparse-safe publication, with three actual policies rather than a generic
framework. Rebase, broad staging/restoration and text conflict resolution were
removed because they could discard foreign work or publish bytes no producer
confirmed. The optional bounded preparation callback belongs to the caller;
the core has no pipeline switches, models or audit ledger.

## See also

- [The gardener](idhazh-gardener.md) - task ownership, sparse budgets and outcomes.
- [The council](llm-council.md) - one collecting job and tenant boundaries.
- [One visual, one file](one-visual-one-file-and-the-race-between-two-runs.md) - raced assets.
