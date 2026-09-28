# The gardener's knobs and declarations

**Last Updated**: 2026-09-28

What the gardener may delete and rewrite, and how each of its tasks is declared.
Two inputs, both under `config/`: the gardener's own knobs in
`config/idhazh_gardener.json`, and one declaration per task in
`config/gardener/<task>.json`. How the gardener runs is
[../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md);
what a knob is at all is [../config.md](../config.md).

## `config/idhazh_gardener.json`

| Knob | Committed | What it decides |
| --- | --- | --- |
| `version` | `2026-09-27` | The UTC day this file's shape last changed |
| `attempts` | `6` | How many times one shard may try to push before it gives up with exit 3 |
| `shards` | `5` | The most shards a wake splits into. Fewer run when there are fewer tasks |

**`attempts` must be above `shards`.** Every shard of a wake pushes to one
branch at once, so the last one to land has lost a race to every other shard
first. `attempts - shards` is how many outside or failed pushes one wave can
absorb, and at `attempts == shards` that is none. The loader refuses the pair
naming both values.

## One declaration a task

A task is named by its file: `config/gardener/seen.json` declares the task
`seen`. A missing `config/gardener/` means no tasks. One ships today,
`corpus-squash`, the one `history` task (below).
**There is no index file and no `name` key**, so a task can never be listed under
one name and filed under another.

Every declaration carries these keys, whatever its kind:

| Key | Type | What it says |
| --- | --- | --- |
| `lifecycle_status` | `active`, `paused` or `retired`, no default | `active` runs at every wake. `paused` does not run and keeps its claim. `retired` never runs again, and its declaration stays as the record of how far back its tree reached |
| `kind` | `retention`, `collection`, `compaction` or `history` | Which member reads the rest of the file, and which module may serve it |
| `window` | `{unit: days, value}`, `{unit: months, value}` or `{unit: forever}` | How far back the task keeps what it owns. `value` is at least 1, so no window includes today, and `forever` carries no value |
| `dry_run` | `bool`, no default | True reports what a live pass would take and takes nothing |
| `max_deletes_per_run` | a count, or `null` | The most one pass deletes. `null` is no ceiling and `0` is a survey. A collection pruned through GitHub's API spends a request a delete, so `null` there can use up the token's hourly allowance on one backlog |
| `owns` or `owns_everything_else_under` | a list of folders | Exactly one of the two. `owns` names repository-relative folders; the second is the complement: every folder under its roots that no other task owns and no ledger family claims |
| `appends_to` | a list of ledger names, default `[]` | The ledgers a task files a report of its own into, through the ledger door: one new raw file under the wake's day, on a dry run too, because a report is what a dry run is for. Appending is not owning: the door mints each file's name, so it can overwrite nothing, and the runner refuses a report anywhere else before anything is staged |

Each kind adds its own keys, and a key on the wrong kind is refused by name:

| Kind | Its own keys |
| --- | --- |
| `retention` | `series`, one window per series, for `scores` and `telemetry-aggregate` alone |
| `collection` | none yet |
| `compaction` | `ledger` (required); `raw_index_keep_days` (90), `daily_keep_days` (45), `monthly_window` (13 months), `max_periods_per_run` (8), `max_raw_files_per_period` (2000), `compact_after_hours` (24) |
| `history` | `every_days`, how many whole days apart two rewrites may run. Its `window` is whole days and nothing else, because the squash cuts history at 00:00 UTC on the day that many days back |

## The one declaration that ships: `corpus-squash`

`config/gardener/corpus-squash.json` is the corpus squash, which
`.github/workflows/prune.yml` runs in its own job and never in the matrix.

| Key | Committed | What it decides |
| --- | --- | --- |
| `window` | `{unit: days, value: 60}` | How many days of history a squash keeps |
| `every_days` | `30` | How many whole days apart two squashes may run |
| `owns` | `["corpus"]` | The one file the task writes, `corpus/corpus.meta.json`, sits under it |
| `dry_run` | `false` | The squash has run live since 2026-08-28 by owner decision (`CLAUDE.md` section 8), so the declaration transcribes a live squash rather than starting one |

Both numbers were `finetune.prune_keep_days` and `finetune.prune_every_days` until
2026-09-28. They moved here because the squash is the only thing that reads them,
and a copy left in `config/idhazh.json` is now refused by name, pointing here.

**Every other declaration ships `dry_run: true`**, and a contract test holds the
committed tree to that, naming `corpus-squash` as its one exception with the
decision beside it. A task earns its first deletion from a person reading its
records, so turning one live is an edit to that list, never a side effect of the
change that added the task.

## What the loader refuses

The declarations are validated as one set, never one at a time. Each refusal
names the file an operator edits and the rule it broke.

| Refused | Why |
| --- | --- |
| A file whose name is not lower-case words joined by hyphens | The name is the task |
| Two tasks that own one folder, or a folder inside the other's, whatever their status | Both would delete in it. A retired task keeps its claim |
| More than one task using the complement form | Each would claim what the other claims |
| An owned entry that is a file | A shard checks out folders, so a file would match nothing |
| `seen` keeping less than `collect.seen_window_days` | The planner still reads those days |
| `counterfactual-scores` keeping less than `lens_weights.window_days` | A reader still opens those days |
| A `telemetry-aggregate` series keeping less than the `observability` key it covers, a series no key covers, or a `telemetry-aggregate` with no series | The series would delete what the knob keeps |
| `series` on any other task | One task keeps several series |
| A compaction not called `compact-<ledger>` | One compaction a ledger, found by name |
| `raw_index_keep_days` below `daily_keep_days` | The daily period may still need the index to rebuild a file |
| A `monthly_window` that leaves less than one whole month after `daily_keep_days` | A month absorbed that late would go before a reader reached it |
| A ledger in `ledger.published` whose compaction keeps its months forever | A reader's first request would grow with the archive |
| A published ledger whose two periods reach back less than the widest `console.window_presets` | The widest span the console offers would have days no file holds |
| A compaction reaching back less far than the task that limited its ledger before it moved | The two periods are the ledger's retention now, and a shorter pair silently cuts it |

**The two refusals that need the task modules are the runner's**: a declaration
no module serves, and a module no declaration uses. **The deletion of a folder**
is refused by the commit loop, where the deletions are known.

## Design rationale

**2026-09-27: a month is counted where it is hardest to pass.** A comparison of
days against months cannot be answered once: fourteen months hold between 424
and 428 days depending on where they fall. So a window that deletes is counted at
the fewest days its months can hold, and a window that is needed at the most,
and the answer never depends on the day the build ran. The same unit against the
same unit compares the numbers. The period pair reaches back `daily_keep_days`
plus its `monthly_window`, and "one whole month" is 31 days (Fowler and Carmack).

**2026-09-27: a compaction's floor is the task that limited the ledger.** Once a
ledger moves under the two roots, the task that kept its old tree is retired and
keeps its declaration, so its window is the one record of how far back the ledger
reached. For `item-health` that is the `full-grain` series of
`telemetry-aggregate`, not the `aggregate` series, which covers the summary.
Five cases: a bounded floor against a bounded pair compares; a bounded floor
against a pair kept forever passes; a floor kept forever against a bounded pair is
refused, because a person chose never to delete that ledger; forever against
forever passes; and a ledger no task ever limited has no floor.

## See also

- [../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md) - how a wake runs.
- [retention-ages.md](retention-ages.md) - the `observability` ages a series is held to.
- [../config.md](../config.md) - what makes a value a knob.
