# Migrate the Observation Lookup

**Last Updated**: 2026-10-03

How to cut existing evaluation history over to the exact lookup and recover a
named pending batch. This procedure is project-specific because it publishes
the evaluation ledger described in [observation-lookup.md](../architecture/contracts/observation-lookup.md).

## Approve the live cutover first

Obtain operator approval for an interval that excludes older evaluation
writers, their retries and evaluation compaction. Keep that exclusion across
the final source snapshot, migration, publication of the migrated state and
code merge. Old-revision replays must not write legacy CSV IDs afterward.
An unknown set of running jobs is not a safe cutover condition. This procedure
does not authorize pausing or cancelling them.

Use the approved code and a complete state snapshot, including legacy index
CSVs and all raw and compact evaluation files and metadata. Run from the
repository root with the project Python environment. The state path must be
direct, without parent traversal, symbolic links or directory junctions.

## Migrate the named state directory

```sh
PYTHONPATH=backend python backend/utilities/migrate_observation_lookup.py --state-dir state
```

`--state-dir` is required. The destination is derived as
`state/summary-quality-evals-index/lookup/`; there is no output-path flag.
`--existing` defaults to `refuse`, so an existing lookup is not overwritten.

The pass preserves every validated legacy CSV digest and adds the current
measurement key recomputed from every raw and compact evaluation row. It
validates source paths, contracts, coverage and source stability, builds the
lookup beside the source, then publishes the complete directory atomically.
Only after verification does it remove the legacy CSVs. It never rewrites
evaluation bytes. This is an explicit full-history operation, not routine
membership work.

Read the JSON result: it reports rows read, distinct IDs, the generation, and
`written_paths` and `removed_paths` relative to the named state directory.
Publish the lookup and legacy CSV removals together under the agreed cutover.
Keep the writer and compaction exclusion until that publication and the code
merge are complete.

## Resume interrupted CSV cleanup

If the lookup directory landed but cleanup did not finish, retain it and run:

```sh
PYTHONPATH=backend python backend/utilities/migrate_observation_lookup.py --state-dir state --existing verify
```

This verifies the remaining source IDs against the existing root and completes
CSV cleanup. It does not rebuild, extend or reset that root. The root's settings
are schema-validated, but are not compared with current config or repartitioned.
A changed key, missing required ID or changing source stops the pass. Keep the
lookup and remaining sources, restore the approved exclusion, and resolve the
reported mismatch before retrying. Do not delete the root to bypass a refusal.

## Recover a named pending batch

Use this after migration, from a clean dedicated checkout tracking
`origin/main`, with permission to push. Obtain the exact 64-hex batch ID from
`state/summary-quality-evals-index/incoming/<batch-id>.json` or the producing
job's saved input. Do not scan evaluation history or invent a replacement run
identity. Recovery uses the sealed batch's original writer identity.

The following shell commands configure the paired preparation hook, then run
the shared commit helper. Replace the batch-ID placeholder. Use a shell with
`REFRESH_PATHS`, `REGENERATE_COMMAND` and `DROP_RACED_ASSETS_COMMAND` unset.

```sh
BATCH_ID='<64-hex-batch-id>'
export PYTHONPATH=backend
export PREPARED_PATHS_FILE=backend/var/evaluation-inputs/recovery-paths.json
export PREPARE_COMMAND="python backend/utilities/prepare_evaluation_publication.py --state-dir state --batch-id ${BATCH_ID} --paths-file ${PREPARED_PATHS_FILE}"
export COMMIT_MESSAGE="Record recovered evaluation measurements"
export NOTHING_STAGED_MESSAGE="Evaluation batch is already published"
export PUSH_FAILED_MESSAGE="Could not publish recovered evaluation measurements"
python backend/utilities/commit_and_push.py state/summary-quality-evals-index/lookup/root.json
```

Preparation can push a missing input batch; it is not a dry run. The helper
regenerates the ignored JSON path list on every attempt and commits the accepted
rows, lookup changes, receipt and pending-input deletion together. The root
argument supplies the required initial stage path; the fresh path list supplies
the other exact files and deletions. A matching committed receipt prevents a
second row write. Once its pending input is gone, recovery is a no-op even after
compaction has replaced the receipt's original output files.

Normal workflow preparation uses `--inputs <per-job-manifest>` and
`--attempt <run-attempt>` instead of `--batch-id`. These input modes are mutually
exclusive. `--batch-id` may be repeated for a named group; `--paths-file` is
required and must not be the input manifest. `--config-dir` is an optional
repository-relative override. The shared helper owns retry timing and the
commit identity; do not supply a new batch identity through environment values.

## See also

- [../architecture/contracts/observation-lookup.md](../architecture/contracts/observation-lookup.md) - identity, bounds and publication guarantees.
- [../architecture/publishing/committing.md](../architecture/publishing/committing.md) - preparation pairs and push failure handling.
- [../concepts/growing-reads.md](../concepts/growing-reads.md) - why this explicit migration reads all history.
