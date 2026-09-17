# Prune a collection

**Last Updated**: 2026-09-17

How do I delete the old members of a collection, safely, without taking the
whole backlog in one go?

Two commands, one core. `idhazh telemetry prune` takes day files out of a store
under `state/`. `backend/utilities/prune_artifacts.py` takes members out of a
collection GitHub holds for us. Both delete one member at a time, both stop at a
ceiling, and both say where the next pass resumes. What "atomic" means here and
why a range is not one is in
[../concepts/atomic-deletes.md](../concepts/atomic-deletes.md).

## Before you start

| You need | Why |
| --- | --- |
| A clean working tree | a live pass deletes committed files, and you want the diff to be only that |
| `GITHUB_TOKEN` in the environment, with `actions:write` | only for the GitHub collections. It is never read from a file and never printed |
| The output of a dry run | it is the default, and it is the list you are agreeing to |

## Prune a collection GitHub holds

### 1. See what the window selects

```
python backend/utilities/prune_artifacts.py --collection workflow-artifacts
```

`--dry-run` is on by default, so this deletes nothing. It prints one line per
member it would take, then one line saying whether there is more.

The age comes from `prune.collections.workflow-artifacts.retain_days` in
`config/idhazh.json` and the ceiling from `max_deletes_per_run` beside it. Pass
`--older-than-days` or `--max-deletes` to override either for one run.

### 2. Read the last line before you read the list

| Last line says | What it means | What to do |
| --- | --- | --- |
| `the collection is exhausted` | nothing else is inside the window | one live pass finishes the job |
| `the ceiling of N stopped this pass at <id>` | there is more | run it again after the live pass, until the line changes |
| `a delete failed at <id>` | the members above it are gone | fix the cause, then run it again - it retries that member |

### 3. Delete

```
python backend/utilities/prune_artifacts.py --collection workflow-artifacts --no-dry-run
```

Repeat until the last line says the collection is exhausted. Each run is the
same shape and the same cost whatever the backlog is - that is what the ceiling
is for.

### 4. Keep the record, if something else needs it

```
python backend/utilities/prune_artifacts.py --collection workflow-runs --no-dry-run \
  --record backend/var/prune/workflow-runs.json
```

`--record` writes the pass as a `collection-prune-row` payload
(`schemas/collection-prune-row.schema.json`). Nothing reads it by default; it is
there for a workflow that wants to upload or commit what a pass did.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | the pass ended cleanly, whether it exhausted the collection or stopped at its ceiling |
| 1 | a delete failed. The members before it are gone and the report names the one to retry |
| 2 | an argument was refused - an unknown collection, a bad day, a repository that is not `owner/name` |

## Prune day files out of a store

```
idhazh telemetry prune --target item-health --since 2026-08-24 --until 2026-08-26
```

Both ends are named and both are inclusive, so `--since X --until X` is one day.
`--dry-run` is on by default here too, and `--no-dry-run` is the second word.

`--max-deletes` bounds a pass. Its default is every day the range names, so a
range you typed is taken whole unless you ask for a smaller bite:

```
idhazh telemetry prune --target scores --since 2025-01-01 --until 2025-12-31 \
  --no-dry-run --max-deletes 30
```

Which stores this may be pointed at, which two are refused by name, and why
`scores` and `score-index` are pruned as a pair are in
[../architecture/publishing/retention.md](../architecture/publishing/retention.md#a-named-prune-one-store-one-range-of-days-2026-09-16).

## Failure modes

| What you see | What happened | What to do |
| --- | --- | --- |
| `GITHUB_TOKEN is not set` | the token is not exported | export one with `actions:write` for this repository. Never put it in a file |
| `--repo takes owner/name` | the slug is wrong or `GITHUB_REPOSITORY` is unset | pass `--repo miztiik/yen-idhazh` |
| `a prune takes the name of a store, not ...` | a path was passed where a name belongs | pass a name. There is no argument on either command a path can travel through |
| `published is refused: ...` | you named a store that must not forget | read the reason in the message. It is a decision, not an oversight |
| `since is after until` | the two ends are swapped | the oldest day comes first |
| the same members print on every run | the pass is a dry run | add `--no-dry-run` |

## See also

- [../concepts/atomic-deletes.md](../concepts/atomic-deletes.md) - what atomic means here, and why a range is not one.
- [../architecture/publishing/retention.md](../architecture/publishing/retention.md) - what bounds each tree, and which store carries which window.
- [../concepts/config.md](../concepts/config.md) - every knob, including the `prune` block.
- [run-the-gates.md](run-the-gates.md) - the checks to run after a change to either command.
