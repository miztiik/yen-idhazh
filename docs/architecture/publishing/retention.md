# Retention

**Last Updated**: 2026-10-08

What the app may delete, what must survive, and the safeguards before deletion.
[layout.md](layout.md) owns publication. The [gardener](idhazh-gardener.md)
owns scheduled cleanup; its [task declarations](../../concepts/config/idhazh-gardener.md)
own the active windows, deletion ceilings and dry-run settings.

## Deletion rules

- Read retention policy from config. A site-size warning is not permission to delete data, and a size forecast is not a deletion schedule.
- Use UTC boundaries. Decide age from the period being retained, not when the job woke. Delete only below the retention floor, so a pass using a past date cannot delete newer data.
- A scheduled pass reads the period that just expired and the configured number of earlier periods. Its report describes only that fixed window, not the full backlog. Use `idhazh gardener run-task` with inclusive `--from` and `--to` dates or months to drain older periods.
- If a backlog exists when a fixed window is introduced, drain it once with a known inclusive range. The scheduled task does not scan the archive to find older periods.
- Keep every period a supported reader can request. Compare calendar windows at their actual partition boundaries; do not approximate every month as thirty days.
- Respect each task's ownership, lifecycle status, dry-run setting and deletion ceiling. Do not assume all tasks have the same mode.
- Review the dry-run list before enabling deletion. Enabling a task is an explicit configuration decision, not a side effect of adding it.
- Write and validate any required summary before removing its source files. A failed write or reconciliation leaves the source intact.
- Deletion is atomic per file or collection member, not per whole range. An interrupted pass reports what happened and where it stopped; it does not promise to restore earlier deletions.

Removing a committed file bounds the live tree, not its Git history. Only the
gardener's `history` job has standing permission to rewrite that history under
[CLAUDE.md section 8](../../../CLAUDE.md). Once the rewrite removes the old
history, a revert cannot recover the deleted data.

## Published days and visuals

The `visual-prune` task removes rendered visuals only. It must not remove a day's
payload, its directory, evaluation records, fixtures, canaries or schema history.
Other ledgers have their own retention tasks; visual cleanup is not authority to
delete them.

`retention.image_months` controls the published visual-retention promise, with
`-1` meaning no age-based visual deletion. The gardener declaration must match
that promise. Visual pruning is currently a dry run; inspect
[visual-prune.json](../../../config/gardener/visual-prune.json) before assuming
that a pass deletes anything.

State the visual window on the archive before enabling deletion. Say what the
policy permits, not that a deletion has already happened. Stories and their links
remain. Distinguish a pruned visual from a failed render, and keep the story
readable without either. A missing day must use the designed missing state,
never silently redirect to today.

Prefer reducing unnecessary published bytes before deleting reader content.
Measure the actual deployed bundle through the
[site-weight rules](../../reference/site-weight.md); cleaning a source tree is
not a measurement of the site's size.

## Unpublishing a day

There is no implemented command to unpublish a day, range or month. Do not use
visual pruning or telemetry pruning as a substitute. A removal must account for
the day, its search entries and derived published data without deleting its
neighbouring days. The `seen` ledger must not be cleared to make that removal:
forgetting those addresses would let the next run rediscover them.

## What bounds the committed state tree

Sharding makes bounded reads and deletions possible; it does not bound growth by
itself. Each collection needs an explicit policy. Current values and the readers
that constrain them belong to
[retention ages](../../concepts/config/retention-ages.md) and the
[gardener declarations](../../concepts/config/idhazh-gardener.md).

| Collection | Required behavior |
| --- | --- |
| Seen addresses | Keep the planner's full read window. Delete only older days, using the same window rule as the reader. |
| Published identities | Preserve the information that prevents duplicate publication. The manual prune refuses this ledger. |
| Item health | Write and validate the required day-and-stage summary before deleting an aged source month and its published copy. |
| Feed health | Delete expired records when no reader needs them; do not invent an unused aggregate. Feed retirements have a separate policy so cleanup does not revive retired sources. |
| Summary-quality evals | Keep every row. `compact-summary-quality-evals` may pack rows but never drops a period. |
| Raw and compact ledgers | Follow the ledger's compaction declaration. A legacy task's retirement must not silently shorten the period retained. |
| Trial records and other task-owned data | Follow the owning declaration, not a blanket cleanup of `state/`. |

An aggregate must outlive the full-detail data it replaces. A summary can be
larger than a very small source partition; that alone does not make it invalid.
Claims about aggregated data must stay within what the aggregate preserves.

### Eval rows

Every eval row is kept for ever, and a monthly figure is computed from the rows
when a chart draws it
([../../concepts/evaluation.md](../../concepts/evaluation.md#design-rationale)).

## A named prune: one ledger, one range of days

`idhazh telemetry prune` removes an explicitly selected range of days from one
ledger the door files: the days' raw files, and their rows out of every packed
file that holds them.
The current supported targets are listed by `idhazh telemetry prune --help`; the
target is a ledger name, never a path. This command does not unpublish a day or
rebuild the site's derived payloads.

```text
idhazh telemetry prune --target <ledger> --since <YYYY-MM-DD> --until <YYYY-MM-DD>
```

- Both ends are inclusive. Equal endpoints select one day.
- Dry run is the default and reports the selected paths. `--no-dry-run` permits deletion.
- `--max-deletes` bounds a pass and reports where to resume. Without it, the supplied range sets the default bound.
- `published` and `seen` are refused because forgetting their records permits repeat publication or discovery.
- A ledger the door files (`raw-and-compact` in `config/ledgers.json`) is a target unless its compaction declaration's `prune_refusal` gives a reason, which the command prints as its refusal. A pass deletes the days' raw files and rebuilds each daily, monthly or yearly file that holds them without their rows; a file left with no row stays as an empty file. A live pass also takes `--run-id` and `--commit`, which each rebuilt file names as its writer.
- `summary-quality-evals` is refused by its declaration: every eval row is kept for ever.
- Do not point the command at unsupported raw trees or file layouts. Their owning tasks decide retention.

The procedure and failure handling are in
[prune a collection](../../how-to/prune-a-collection.md). The per-member deletion
guarantee is in [atomic deletes](../../concepts/atomic-deletes.md).

## The cleanup says what it did not clear

Every visual-prune pass writes a `VisualPruneRow`, including dry runs and passes
with no candidates. It records the policy, cutoff, candidates, deletions,
`skipped_by_fuse`, remaining visual coverage and the named candidate window's
before-and-after byte totals. The report is written through the shared ledger writer under
`state/raw/visual-prunes/`; the task declares that report in `appends_to`.

`skipped_by_fuse` counts candidates held back by the deletion ceiling, on both
live and dry runs. It is not every file left after a dry run. On a live pass,
`deleted + skipped_by_fuse` equals `candidates_found`; on a dry run, the
difference is what a live pass would have deleted. The contract validates this.

`candidates_found` and the byte totals cover only the named candidate days;
`oldest_kept` checks only the first day still kept. Older backlog is not counted
on every wake. Use an explicit inclusive date range to drain it. Commit
removals with their report so the repository does not retain files the pass
says it deleted. Run cleanup through the gardener, separately from digest
assembly.

## External visual assets

`visuals.asset_base_url` can serve existing rendered assets from another host.
Empty means this site. A configured HTTPS prefix controls both where the browser
fetches drawings and whether the build includes those drawings; deriving both
from one value avoids publishing a duplicate copy.

The operator must publish the matching `digest/` assets at that prefix first.
The pipeline does not upload them. Derive the permitted origin from committed
config, validate the visual path, and allow the browser fetch on the asset host.
Keep SVGs inlined for theme styling rather than moving them into an `img` whose
document cannot read the page's theme tokens. Failed visuals must not block text.

Moving assets changes hosting and caching costs, not which stories are retained.
It is not a reason to prerender new charts; new rendering follows the
[UI-shell policy](../../concepts/ui-shell.md#rendering-policy).

## A collection GitHub holds: artifacts and workflow runs

`workflow-artifacts` and `workflow-runs` are separate gardener tasks. Their
declarations set the age, ceiling and dry-run mode. Each API deletion costs a
request, so the ceiling also limits work against GitHub's request allowance.
Use the same per-member failure and resume rules as file cleanup.

Pipeline-test prose remains in expiring artifacts, while its committed telemetry
retains measurements. The numbers cannot reconstruct the fetched article or the
model's answer after the artifact expires. Re-fetching a changed page is not a
replay of the original evidence. Artifact retention comes from the upload step
and the collection's cleanup policy, within GitHub's supported limits.

## Design rationale

- Retention follows reader needs and declared age windows, not old size snapshots or predicted cap dates.
- Scheduled cleanup reads a fixed window: the latest expired period plus its configured lookback. A report counts that window; an operator names an inclusive range to drain older backlog, rather than making every wake scan it.
- Visual-prune byte totals and coverage describe its named candidate days, and `oldest_kept` reads the first day in the kept window. This keeps the report cost fixed as the archive grows.
- Summaries are verified before deletion because the history rewrite can make a mistaken deletion permanent.
- Preserving observation identities prevents archival from turning repeat measurements into new evidence.
- Dry runs, deletion ceilings and progress reports let an operator inspect and finish bounded cleanup.
- A reader must know whether a visual was removed, a render failed or a day never existed. Those states must not share one misleading message.

## See also

- [layout.md](layout.md) - what a run publishes and the addresses readers use.
- [idhazh-gardener.md](idhazh-gardener.md) - how scheduled maintenance runs.
- [../../concepts/config/idhazh-gardener.md](../../concepts/config/idhazh-gardener.md) - task ownership, windows and safeguards.
- [../../concepts/config/retention-ages.md](../../concepts/config/retention-ages.md) - why each collection keeps its window.
- [../../how-to/prune-a-collection.md](../../how-to/prune-a-collection.md) - manual operation and failure handling.
- [../../reference/site-weight.md](../../reference/site-weight.md) - deployed size limits and warnings.
- [../../../CLAUDE.md](../../../CLAUDE.md) - history-rewrite authority and bounded-work requirements.
