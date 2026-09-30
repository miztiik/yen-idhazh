# The gardener's knobs and declarations

**Last Updated**: 2026-09-29

What the gardener may delete and rewrite, and how each of its tasks is declared.
Two inputs, both under `config/`: the gardener's own knobs in
`config/idhazh_gardener.json`, and one declaration per task in
`config/gardener/<task>.json`. How the gardener runs is
[../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md);
what a knob is at all is [../config.md](../config.md).

## `config/idhazh_gardener.json`

| Knob | Committed | What it decides |
| --- | --- | --- |
| `version` | `2026-09-28` | The UTC day this file's shape last changed |
| `attempts` | `6` | How many times one shard may try to push before it gives up with exit 3 |
| `shards` | `5` | The most shards a wake splits into. Fewer run when there are fewer tasks |
| `max_cone_mb` | `768` | The most the folders one shard owns may weigh, in megabytes of 1024 x 1024 bytes, before the shard exits 1. Its tasks still run and its record still lands; the number is an alarm, and it is an estimate ([why 768](../../architecture/publishing/idhazh-gardener.md#what-a-shards-folders-weigh)) |

**`attempts` must be above `shards`.** Every shard of a wake pushes to one
branch at once, so the last one to land has lost a race to every other shard
first. `attempts - shards` is how many outside or failed pushes one wave can
absorb, and at `attempts == shards` that is none. The loader refuses the pair
naming both values.

## One declaration a task

A task is named by its file: `config/gardener/seen.json` declares the task
`seen`. A missing `config/gardener/` means no tasks. Seventeen ship today: eleven
`retention` tasks, two `collection` tasks, three `compaction` tasks (below) and
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
| `retention` | `series`, one window per series, for two tasks alone: `telemetry-aggregate` keeps `full-grain`, `aggregate` and `public-copy`, and `scores` keeps `full-grain` and `archive`. `fold`, `{after_days, dry_run}`, on a task that owns a CSV day tree - a tree that files one small file per writer under each day's folder: once `after_days` whole days have passed since a day ended (default 1), its files become one `settled.csv`. The fold has a `dry_run` of its own because it changes no answer a reader gets ([how it runs](../../architecture/publishing/idhazh-gardener.md#the-closed-day-fold)) |
| `collection` | `collection` (required): `workflow-artifacts` or `workflow-runs`, the GitHub collection it deletes from, and the file is named for it. Its `window` is whole days and nothing else, because a pass counts a member's age in days |
| `compaction` | `ledger` (required); `raw_index_keep_days` (90), `daily_keep_days` (45), `monthly_window` (13 months), `max_periods_per_run` (8), `max_raw_files_per_period` (2000), `compact_after_days` (1). Its `window` is always `{unit: forever}` and its `max_deletes_per_run` always `null`: the two periods are how far back it keeps, and `max_periods_per_run` is its budget |
| `history` | `every_days`, how many whole days apart two rewrites may run; `push_attempts`, how many pushes one run makes in all, at least 1; `push_retry_delay_seconds`, how long a run waits after a refused push before it squashes again, at least 0. None of the three has a default. Its `window` is whole days and nothing else, because the squash cuts history at 00:00 UTC on the day that many days back |

## The retention declarations that ship

Each deletes what it owns past its window, and each ships `dry_run: true`. The
windows were keys in `config/idhazh.json` until 2026-09-28 and moved here with
no value changed, because each task is the only thing that reads its number.
Four of them also fold the closed days of the CSV day trees they own, and that
fold ships live, `fold.dry_run: false`: `scores` (its `score-index`),
`feed-health`, `counterfactual-scores` and `span-rollup`. The item-health, scores
and host-fingerprint rows moved to the ledger door, so no fold reads them.
The digest workflow ran that same fold live on every run until the gardener
took it over, and a fold changes no answer a reader gets.
Why each tree gets the age it has is
[retention-ages.md](retention-ages.md#every-tree-names-its-own-cleanup-age).

| Task | Owns | Window | Why that window |
| --- | --- | --- | --- |
| `telemetry-aggregate` | `state/item-health-summary`, `frontend/public/telemetry` | 14 months: `full-grain` 14 months, `aggregate` forever, `public-copy` 14 months | a 366-day console read can open 14 month files; the summary is what a year-over-year claim reads, and it is written from the item-health ledger through the ledger door before `compact-item-health` can delete the month's rows; the browser's copy ages with its source |
| `scores` | `state/score-index`, `state/score-archive` | 14 months: `full-grain` 14 months, `archive` forever | an index day goes once an archive covers its month. It builds no archive now: the archive was built from the CSV day files, which moved to the ledger door, so `compact-scores` stays report-only until an archive is built from the door's rows |
| `feed-health` | `state/feed-health` | 14 months | the same 14; deleted rather than summarised, because no older total has a reader |
| `host-fingerprint` | `state/host-fingerprint` | 14 months | retired: its module is deleted and nothing runs it. The declaration stays because its window is the floor `compact-host-fingerprint` must reach, and the published machine shard is folded from that ledger, so it keeps at least `public_machine_keep_months` |
| `seen` | `state/seen` | 90 days | at least `collect.seen_window_days`, the days the collector reads |
| `counterfactual-scores` | `state/counterfactual-scores` | 30 days | at least `lens_weights.window_days`, the days a reader opens |
| `traces` | `state/traces` | 7 days | a trace is opened to see one recent run, and the span rollup is the record that stays |
| `span-rollup` | `state/span-rollup` | forever | nobody has said how long a span total is wanted, so it keeps every month. The task exists so the tree's closed days are folded, and no old cleanup ever deleted from it |
| `trials` | everything under `state` that no other task owns and no ledger claims | 90 days | nothing reads a trial's rows, and 90 days is the artifact retention used everywhere else |
| `digest-fragments` | `state/digest-fragments` | 390 days | 30 days times `retention.image_months`, the window the archive page states; past it a run's block of a day is a second copy nothing reads |
| `visual-prune` | `frontend/public/digest` | 390 days, at most 200 files a pass | the same stated window. It deletes rendered charts only, and files a report of every pass into `visual-prunes` |

## The compaction declarations that ship

Each moves one ledger's rows out of its raw files into one file a day and then
one file a month, and deletes what it moved. How a pass runs is
[../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md#the-compaction).
Each ships `dry_run: true`, and each owns its ledger's two folders,
`state/raw/<ledger>` and `state/compact/<ledger>`.

| Task | Ledger | Keeps | Why |
| --- | --- | --- | --- |
| `compact-gardener` | `gardener`, the gardener's own record | the defaults: day files for 45 to 76 days, then 13 month files | no task limited this ledger before it moved, so nothing sets a floor, and the owner kept the defaults (2026-09-27) |
| `compact-visual-prunes` | `visual-prunes`, the picture cleanup's report of every pass | the defaults | the same |
| `compact-feed-retirements` | `feed-retirements`, the addresses the pipeline stopped fetching | day files for 45 to 76 days, then 60 month files | a retirement the window deletes is a feed the pipeline asks for again, so it keeps five years (owner, 2026-09-27). The price: an address retired more than 60 months ago is asked for once more, and is retired again if it is still gone |
| `compact-item-health` | `item-health`, the census | day files for 45 to 76 days, then 15 month files | its floor is the `full-grain` series of `telemetry-aggregate`, 14 months, and a month is summarised before this can delete it |
| `compact-scores` | `scores`, the eval ledger | day files for 45 to 76 days, then 15 month files | its floor is the `full-grain` series of `scores`, 14 months. It stays report-only until the score archive is built from the door's rows |
| `compact-host-fingerprint` | `host-fingerprint`, the machine record | day files for 45 to 76 days, then 14 month files | its floor is the retired `host-fingerprint` window, 14 months, which `public_machine_keep_months` holds |

**The last three are the ledgers the console reads**, and the console reads their
packed files, so until a person turns them on it shows data up to the day their
migration ran ([../../architecture/contracts/persistence.md](../../architecture/contracts/persistence.md#moving-a-ledger-onto-the-door)).

## The collection declarations that ship

Each deletes members of one collection GitHub keeps for this repository - never
a file in it - past its window, and each ships `dry_run: true`. Each owns no
folder, so `owns` is `[]`. The ages and ceilings were `prune.collections` in
`config/idhazh.json` until 2026-09-28 and moved here with no value changed; a
`prune` block left there is now refused by name, pointing here. How a pass runs
is
[../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md#the-collection-tasks).

| Task | Collection | Window | At most, a pass |
| --- | --- | --- | --- |
| `workflow-artifacts` | the files workflow runs upload. 612 of them held 1,063 MB on 2026-09-17 | 30 days | 50 |
| `workflow-runs` | the runs themselves, each with its logs. 3,551 of them on 2026-09-17 | 90 days | 50 |

**The ceiling is also a request budget.** A pass spends one request to list
each page of 100 members and one request a delete, and the token Actions hands
a run has an hourly allowance, so the ceiling bounds what one wake spends of it.

## The history declaration: `corpus-squash`

`config/gardener/corpus-squash.json` is the corpus squash, which the `history`
job of `.github/workflows/idhazh-gardener.yml` runs on its own and never in the
matrix.

| Key | Committed | What it decides |
| --- | --- | --- |
| `window` | `{unit: days, value: 60}` | How many days of history a squash keeps |
| `every_days` | `30` | How many whole days apart two squashes may run |
| `push_attempts` | `3` | How many pushes one run makes in all. Git refuses a push when `main` moved after the run read it, and each refusal is followed by the whole squash again on the new tip. After the last refusal the run is not recorded, so the squash is due again at the next daily wake |
| `push_retry_delay_seconds` | `60` | How long a run waits after a refused push before it fetches `main` and squashes again |
| `owns` | `["corpus"]` | The one file the task writes, `corpus/corpus.meta.json`, sits under it |
| `dry_run` | `false` | The squash has run live since 2026-08-28 by owner decision (`CLAUDE.md` section 8), so the declaration transcribes a live squash rather than starting one |

Both numbers were `finetune.prune_keep_days` and `finetune.prune_every_days` until
2026-09-28. They moved here because the squash is the only thing that reads them,
and a copy left in `config/idhazh.json` is now refused by name, pointing here.

**Three pushes a minute apart is an estimate, and one number decides whether it
fits.** A run pays for its clone and its install once, then for one whole squash
a push and one wait before each push after the first. So three pushes fit the
history job's 30 minutes only while one squash takes under about 8 minutes on
the runner. A squash replays every commit after its boundary - about 4,800 when
the window is full, at September 2026's rate of about 80 commits a day - and that
replay has not been timed on a runner. The first due run's step time is the
measurement that settles it. A job stopped at its timeout has pushed nothing and
recorded nothing, so the squash is due again at the next wake, as after a last
refused push. The person's ruling of 2026-09-29 added the two keys.

**Every other switch ships `dry_run: true`**, and a contract test holds the
committed tree to that. It finds every `dry_run` a declaration carries, a
fold's as well as the task's own, and names the live ones as its exceptions,
each with the decision beside it: `corpus-squash`'s `dry_run` and the six
`fold.dry_run` switches above. A task earns its first deletion from a person
reading its records, so turning one live is an edit to that list, never a side
effect of the change that added the task.

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
| `telemetry-aggregate` or `scores` with no series, a series that is not one of its trees, or one of its trees with no series | A tree with no window is a tree nothing bounds |
| A task's `window` that differs from its `full-grain` series, or a ceiling on a task that keeps series | One number is spelled once; a ceiling could stop a month's summary part way through |
| An `aggregate` or `archive` series that does not keep longer than the `full-grain` series beside it | A month would be deleted before it was ever summarised |
| A `public-copy` series that is not equal to the `full-grain` series | The copy is the browser's copy of that ledger |
| A `feed-health` window, a `full-grain` series or a `public-copy` series under the month files the widest console read selects | A panel blanks for a month that ran |
| The retired `host-fingerprint` declaration keeping less than `observability.public_machine_keep_months` | The published machine shard is folded from the host-fingerprint ledger, and that window is the floor its compaction must reach |
| `digest-fragments` or `visual-prune` keeping anything but 30 days times `retention.image_months`, or anything but forever when that is `-1` | The archive page states that window to a reader |
| `series` on any other task | One task keeps several series |
| A compaction not called `compact-<ledger>` | One compaction a ledger, found by name |
| A collection task not called `<collection>.json`, or whose `window` is not whole days | One task a collection, found by name; a pass counts a member's age in days |
| `raw_index_keep_days` below `daily_keep_days` | The daily period may still need the index to rebuild a file |
| A compaction whose `window` is not `{unit: forever}`, or whose `max_deletes_per_run` is not `null` | Its two periods are how far back it keeps and `max_periods_per_run` is its budget. A second window would be a number nothing reads, and a ceiling could stop a month half absorbed |
| `daily_keep_days` below 31 | GitHub lets a failed run be re-run for 30 days, into the day it first wrote, so a month absorbed sooner could still be reached by one |
| A ledger in `ledger.published` whose compaction keeps its months forever | A reader's first request would grow with the archive |
| A published ledger whose two periods reach back less than the widest `console.window_presets` | The widest span the console offers would have days no file holds |
| A compaction reaching back less far than the task that limited its ledger before it moved | The two periods are the ledger's retention now, and a shorter pair silently cuts it |

**The refusals that need the task modules are the runner's**: a declaration no
module serves, a module no declaration uses, and a history task handed to it
rather than to `backend/utilities/corpus_history.py`. **The deletion of a folder**
is refused by the commit loop, where the deletions are known.

## Design rationale

**A month is counted where it is hardest to pass.** A comparison of
days against months cannot be answered once: fourteen months hold between 424
and 428 days depending on where they fall. So a window that deletes is counted at
the fewest days its months can hold, and a window that is needed at the most,
and the answer never depends on the day the build ran. The same unit against the
same unit compares the numbers. The period pair reaches back `daily_keep_days`
plus its `monthly_window` (Fowler and Carmack).

**A compaction's floor is the task that limited the ledger.** Once a
ledger moves under the two roots, the task that kept its old tree is retired and
keeps its declaration, so its window is the one record of how far back the ledger
reached. For `item-health` that is the `full-grain` series of
`telemetry-aggregate`, not the `aggregate` series, which covers the summary.
Five cases: a bounded floor against a bounded pair compares; a bounded floor
against a pair kept forever passes; a floor kept forever against a bounded pair is
refused, because a person chose never to delete that ledger; forever against
forever passes; and a ledger no task ever limited has no floor.

**A cleanup age lives in the declaration of the task that deletes by
it.** Eleven keys left `config/idhazh.json` - the ledger ages, the trial window,
the picture cleanup's fuse and the one dry run every pass shared - because each
had one reader and that reader is now a task. The rules that tied them together
moved with them: the summary pairs, the published copy, the machine source and
the console window are checked here when the declarations load, and the four
published ages that stayed in `observability` keep theirs in `config.load`. A
moved key left in the app config is refused by name, pointing at its
declaration, rather than read as a second spelling somebody has to hold in
step. `retention.image_months` stays where it is, because the archive page
states it to a reader, and the loader holds both picture windows to it (Fowler).

**A compaction's month window leaves no gap to refuse.** The loader
used to refuse a `monthly_window` that left less than one whole month after
`daily_keep_days`, because a window counted from a month's end could drop the
month before it was absorbed. The window now counts from the month's absorption -
month M goes when the month `monthly_window` later is absorbed - so a month is
always absorbed before it can go, and the rule went with the gap it guarded
(Fowler and Carmack).

**A compaction has no window and no ceiling of its own.** `window` and
`max_deletes_per_run` are fixed on the type, to forever and null, rather than
left for a declaration to set. A compaction never read either: its two periods
are how far back it keeps, and `max_periods_per_run` is its budget. A value there
would be a second spelling of a number that lives in another key (Fowler).

## See also

- [../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md) - how a wake runs.
- [retention-ages.md](retention-ages.md) - where every cleanup age lives, and why each tree keeps what it keeps.
- [../config.md](../config.md) - what makes a value a knob.
