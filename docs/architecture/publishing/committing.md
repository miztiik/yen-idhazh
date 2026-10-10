# How completed output reaches the repository

**Last Updated**: 2026-10-10

Start here when an agent adds a workflow that commits generated files.
Gardener, council, digest and the additional clients below use one publisher:
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
Gardener task ownership and its explicitly declared `appends_to` ledgers are
separate write permissions. A dry-run report can therefore land without granting
the task authority over another ledger.

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
derived set. Rebuilding retains the original producer's plan/config-derived
shard count. The final site build imports both public files and its raw state,
indexes and index-named compact heads from one observed published tip. An import
validates all named local files first and refuses foreign changes.

Input windows include the planning readers' configured seen and published
boundaries, not only the console's shorter window. With unbounded published
history, raw days start at the existing configured `first_ledger_year`; all
packed heads come from the three validated indexes. No raw archive walk is
needed. Permanent readers likewise receive their index-named older heads.

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

Encoder comparison uses `encoder_publish.py`. Collection still runs when
`commit_readings` is false; only publication is skipped. The adapter confirms
the downloaded pair set, the generated manifest and two reading files, and
logs named by the selected config slugs. Other dataset files are not staged.
The ignore rule allows logs only under `corpus/encoder-comparison-1/logs/`;
scratch logs elsewhere remain ignored.
Reused pairs retain unselected saved readings. These comparison files are
replaceable: unrelated main changes can be kept, but a changed target refuses
the whole stale comparison with exit 1. Artifacts remain available on refusal.
The publisher uses the caller's commit message unchanged, with no added
attribution tags.

## The deadline bounds retries

`config/push-retry.json` supplies monotonic job deadlines and configured backoff.
An optional limit counts actual pushes, not preparation/fetch iterations.
Candidates have one parent: the fetched main used to build them. Ordinary
non-force pushes name the candidate SHA and main explicitly, with `--no-thin`.
A failed or uncertain push is verified against **all** exact operations; one
matching record does not prove publication.
After fresh-base preparation, completion is checked again. An empty operation
set returns `no-changes`; operations already present return `already-on-main`.
Neither creates an empty commit or spends a push attempt.

Results distinguish `landed`, `already-on-main`, `no-changes`, `stale`, `lost`,
`integrity-refused`, `refused` and `preparation-failure`, with candidate/base/tip,
push count, refusal paths and preparation status. Integrity exits 2.
Unpublished council/digest work exits 1. Gardener deliberately warns and exits
0 for stale/lost work, meaning SKIPPED rather than published; refusal exits 3.
Producer failure remains separate: gardener may publish completed diagnostics
after exceeding its download ceiling and still exits 1.
A fetch failure before a candidate is built is preparation failure, not proof
that main rejected a push. Gardener preserves its logged crash/exit-1 path.

## Adopting the publisher in another workflow

1. Reuse an adapter when its policy fits. See
   [`gardener_publish.py`](../../../backend/utilities/gardener_publish.py),
   [`council_publish.py`](../../../backend/utilities/council_publish.py),
   [`digest_publish.py`](../../../backend/utilities/digest_publish.py),
   [`record_publish.py`](../../../backend/utilities/record_publish.py) for
   measure, validate and vector backfill, and
   [`pipeline_test_publish.py`](../../../backend/utilities/pipeline_test_publish.py),
   or [`encoder_publish.py`](../../../backend/utilities/encoder_publish.py) for
   a comparison's replaceable files.
   These already cover more than the three daily workflows.
2. Declare the writer's owned paths and ledger prefixes independently of its
   output. Use the ledger registry's
   [`staging.staged_path`](../../../backend/idhazh/ledger/staging.py) where it
   applies. Do not grant blanket `state` permission.
3. Observe the real producer inside
   [`completed_writes.collect`](../../../backend/idhazh/completed_writes.py).
   Keep completed writes even on failure. Record the executed `WriterIdentity`;
   [`publication_evidence.save`, `read`, `identified` and `confirmed`](../../../backend/utilities/publication_evidence.py)
   retain receipts, check raw identities and construct confirmed writes.
   A receipt proves bytes, not permission.
4. Build
   [`PublicationRequest`](../../../backend/utilities/publication_request.py)
   with exact hashes, independent write/delete permissions and the actual
   source data revision in `source_tip`. Keep the executed code revision in
   the identity. A deletion needs its source `Entry` and completion proof.
5. Choose recovery from the workflow's intent. `Write.immutable=True` retains
   completed bytes and refuses a different committed file at that name.
   Mutable writes and deletions reject a changed source baseline, as gardener
   does. Derived output can use `prepare` with declared `preparation_scopes`
   to rebuild only named inputs on a fresh base; digest's
   `inventory_preparation` and
   [`digest_assemble.preparation`](../../../backend/utilities/digest_assemble.py)
   are working examples.
   Do not rerun models or merge generated text.
6. Load `config/push-retry.json` with
   [`push_retry.load_retry`](../../../backend/utilities/push_retry.py), then
   call `publish(request, repo=..., retry=...)` in the one core. Do not add a
   Git push loop. Keep producer failure separate from publication status:
   completed diagnostics can land while failed work still exits nonzero.
7. Test through a real local bare origin, not a fake Git result. Cover a stale
   source, foreign staged files, sparse checkout and immutable collisions.
   Start with
   [`test_shared_publisher.py`](../../../backend/tests/gardener/test_shared_publisher.py)
   and
   [`test_publication.py`](../../../backend/tests/council/test_publication.py).

Machine recording is a separate adoption step. Follow
[host-metrics](../../reference/host-metrics.md); adding the publisher does not
enable the expensive memory copy. Only jobs selected by its config knob copy.

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
