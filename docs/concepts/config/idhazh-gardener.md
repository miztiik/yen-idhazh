# The gardener's knobs and declarations

**Last Updated**: 2026-10-04

What the gardener may delete and rewrite, and how each of its tasks is declared.
Two inputs, both under `config/`: the gardener's own knobs in
`config/idhazh_gardener.json`, and one declaration per task in
`config/gardener/<task>.json`. How the gardener runs is
[../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md);
what a knob is at all is [../config.md](../config.md).

## `config/idhazh_gardener.json`

| Knob | Committed | What it decides |
| --- | --- | --- |
| `version` | `2026-10-03` | The UTC day this file's shape last changed |
| `attempts` | `6` | How many times one shard may try to push before it gives up with exit 3 |
| `shards` | `5` | The most shards a wake splits into. Fewer run when there are fewer tasks |
| `task_names` | Named list in the file | The declarations to read under `config/gardener/`. Empty means no tasks. Missing named files and repeated names are refused. |
| `max_downloaded_mb` | `128` | The most file content one shard may download for its tasks, in megabytes of 1024 x 1024 bytes, before the shard exits 1. A shard checks out only its code and config, so this is the day and month folders its tasks read. Its tasks still run and its record still lands; the number is an alarm, and it is an estimate. Its first reset is to about twice the largest `downloaded_bytes` the first thirty scheduled wakes record ([why 128](../../architecture/publishing/idhazh-gardener.md#what-a-shard-downloads)) |

**`attempts` must be above `shards`.** Every shard of a wake pushes to one
branch at once, so the last one to land has lost a race to every other shard
first. `attempts - shards` is how many outside or failed pushes one wave can
absorb, and at `attempts == shards` that is none. The loader refuses the pair
naming both values.

## One declaration a task

A task is named by its file: `config/gardener/traces.json` declares the task
`traces`. `task_names` in `config/idhazh_gardener.json` names the files to read. Nineteen ship today:
six `retention` tasks, two `collection` tasks, ten `compaction` tasks (below)
and `corpus-squash`, the one `history` task (below).
There is no `name` key inside a declaration. Both plan writers open the same
named list, so adding an unrelated file cannot change a wake's plan.

Every declaration carries these keys, whatever its kind:

| Key | Type | What it says |
| --- | --- | --- |
| `lifecycle_status` | `active`, `paused` or `retired`, no default | `active` runs at every wake. `paused` does not run and keeps its claim. `retired` never runs again, and its declaration stays as the record of how far back its tree reached |
| `kind` | `retention`, `collection`, `compaction` or `history` | Which member reads the rest of the file, and which module may serve it |
| `window` | `{unit: days, value}`, `{unit: months, value}` or `{unit: forever}` | How far back the task keeps what it owns. `value` is at least 1, so no window includes today, and `forever` carries no value |
| `lookback` | a count, optional | Extra earlier periods a scheduled pass checks beyond the period that just expired. Defaults to 7 days or 2 months; the pass reports only the periods it names |
| `dry_run` | `bool`, no default | True reports what a live pass would take and takes nothing |
| `max_deletes_per_run` | a count, or `null` | The most one pass deletes. `null` is no ceiling and `0` is a survey. A collection pruned through GitHub's API spends a request a delete, so `null` there can use up the token's hourly allowance on one backlog |
| `owns` or `owns_everything_else_under` | a list of folders | Exactly one of the two. `owns` names repository-relative folders; the second is the complement: every folder under its roots that no other task owns and no ledger family claims |
| `reads` | a list of folders, default `[]` | Folders the task reads and does not own. Their file names are listed for it from the commit, whichever shard it lands in, and it may fetch and open their files; it never writes or deletes there. A task that asks about a folder it neither owns nor reads is refused rather than answered empty. A folder it owns, or one inside or around one, is refused here, and the complement task declares none |
| `appends_to` | a list of ledger names, default `[]` | The ledgers a task files a report of its own into, through the ledger door: one new raw file under the wake's day, on a dry run too, because a report is what a dry run is for. Appending is not owning: the door mints each file's name, so it can overwrite nothing, and the runner refuses a report anywhere else before anything is staged |

Each kind adds its own keys, and a key on the wrong kind is refused by name:

| Kind | Its own keys |
| --- | --- |
| `retention` | `series`, one window per series, for one task alone: `telemetry-aggregate` keeps `full-grain`, `aggregate` and `public-copy`. `fold`, `{after_days, dry_run, settles_months}`, on a task that owns a CSV day tree - a tree that files one small file per writer under each day's folder: once `after_days` whole days have passed since a day ended (default 1), its files become one `settled.csv`. With `settles_months` (default `false`), once `after_days` whole days have passed since a month ended, every file of that month becomes one `settled.csv` in the month's folder. The fold has a `dry_run` of its own because it changes no answer a reader gets ([how it runs](../../architecture/publishing/idhazh-gardener.md#the-closed-day-fold)) |
| `collection` | `collection` (required): `workflow-artifacts` or `workflow-runs`, the GitHub collection it deletes from, and the file is named for it. Its `window` is whole days and nothing else, because a pass counts a member's age in days |
| `compaction` | `ledger` and the ten keys in [the table below](#the-keys-of-a-compaction), each required: none has a default, so the file holds every number a pass runs with. Its `window` is always `{unit: forever}` and its `max_deletes_per_run` always `null`: the periods are how far back it keeps, and `max_periods_per_run` is its budget, spent on days, months and years separately |
| `history` | `every_days`, how many whole days apart two rewrites may run; `push_attempts`, how many pushes one run makes in all, at least 1; `push_retry_delay_seconds`, how long a run waits after a refused push before it squashes again, at least 0. None of the three has a default. Its `window` is whole days and nothing else, because the squash cuts history at 00:00 UTC on the day that many days back |

## The retention declarations that ship

Each deletes what it owns past its window, and each ships `dry_run: true`. The
windows were keys in `config/idhazh.json` until 2026-09-28 and moved here with
no value changed, because each task is the only thing that reads its number.
No current task carries a `fold` block. Feed-health is packed through the
ledger door, and the evaluation ID lookup uses JSON and SQLite, so neither is a
CSV day tree. The generic fold remains available to a future retention task
that owns a registered CSV day tree.
The digest workflow ran that same fold live on every run until the gardener
took it over, and a fold changes no answer a reader gets. No current task sets
`fold.settles_months`. The [evaluation ID lookup](../../architecture/contracts/observation-lookup.md)
has no retention declaration: its IDs never expire, and it has no day/month fold.
Why each tree gets the age it has is
[retention-ages.md](retention-ages.md#every-tree-names-its-own-cleanup-age).

| Task | Owns | Window | Why that window |
| --- | --- | --- | --- |
| `telemetry-aggregate` | `state/item-health-summary`, `frontend/public/telemetry` | 14 months: `full-grain` 14 months, `aggregate` forever, `public-copy` 14 months | a 366-day console read can open 14 month files; the summary is what a year-over-year claim reads, and it is written from the item-health ledger through the ledger door before `compact-item-health` can delete the month's rows; the browser's copy ages with its source. It `reads` `state/raw/item-health` and `state/compact/item-health`, which `compact-item-health` owns, so it finds its due months whichever shard it lands in |
| `traces` | `state/traces` | 7 days | an item inspection reads recent trace detail; item health keeps its stage measurements |
| `trials` | everything under `state` that no other task owns and no ledger claims | 90 days | nothing reads a trial's rows, and 90 days is the artifact retention used everywhere else |
| `digest-fragments` | `state/digest-fragments` | 390 days | 30 days times `retention.image_months`, the window the archive page states; past it a run's block of a day is a second copy nothing reads |
| `visual-prune` | `frontend/public/digest` | 390 days, at most 200 files a pass | the same stated window. It deletes rendered charts only, and files a report of every pass into `visual-prunes` |

## The compaction declarations that ship

Each moves one ledger's rows out of its raw files into one file a day and then
one file a month, and deletes what it moved. A declaration that sets
`monthly_keep_days` also packs each finished year's month files into one file a
year. Three of the eleven set it, `compact-summary-quality-evals`,
`compact-candidate-models` and `compact-published`, whose `monthly_keep_days`
(93) is how many whole days
after a UTC year ends each waits to pack that year. Each ledger's own
`monthly_keep_days` sets its wait, a ledger the site publishes included, and the
loader checks only that the value can take effect: at least `daily_keep_days`
plus 32 days. How a pass runs is
[../../architecture/publishing/ledger-compaction.md](../../architecture/publishing/ledger-compaction.md).
Seven pack live - `compact-item-health`, `compact-host-fingerprint`,
`compact-counterfactual-scores`, `compact-candidate-models`, `compact-seen`,
`compact-published` and `compact-feed-health` - and the other four ship
`dry_run: true`. Each owns its
ledger's two folders,
`state/raw/<ledger>` and `state/compact/<ledger>`. Six set
`month_deletes_dry_run` to `false`, so `compact-item-health` and
`compact-host-fingerprint` delete what their monthly windows drop, and a
`dry_run` turned `false` later turns a window live with it.
`compact-counterfactual-scores`, `compact-candidate-models`, `compact-seen`,
`compact-published` and `compact-feed-health` set it to `true`:
packing runs live in the change that moves a ledger to the door, because it
writes every row into a coarser file before it deletes one, and the window only
reports what it would delete ([the two switches](#the-keys-of-a-compaction)).

| Task | Ledger | Keeps | Why |
| --- | --- | --- | --- |
| `compact-gardener` | `gardener`, the gardener's own record | day files for 45 to 76 days, then 13 month files | no task limited this ledger before it moved, so nothing sets a floor |
| `compact-visual-prunes` | `visual-prunes`, the picture cleanup's report of every pass | the same as `compact-gardener` | the same |
| `compact-feed-retirements` | `feed-retirements`, the addresses the pipeline stopped fetching | day files for 45 to 76 days, then 60 month files | a retirement the window deletes is a feed the pipeline asks for again, so it keeps five years (owner, 2026-09-27). The price: an address retired more than 60 months ago is asked for once more, and is retired again if it is still gone |
| `compact-counterfactual-scores` | `counterfactual-scores`, what another lens weight would have scored | day files for 45 to 76 days, then 2 month files | its floor is the 90-day console preset. One month reaches back only 73 days at the shortest, while two reach back at least 104. It packs live and its window only reports, as the 30-day window on its CSV did |
| `compact-candidate-models` | `candidate-models`, the verdicts on candidate models | day files for 45 to 76 days, then every month file until its year is packed 93 days after it ends, then one year file for ever | a verdict is why a model was adopted or refused, so none is dropped, and nothing deleted its CSV either. It packs live and its window only reports. Only a qualification writes it, under its trial root, which nothing packs |
| `compact-seen` | `seen`, the first sight of every address | day files for 45 to 76 days, then 2 month files | its floor is `collect.seen_window_days`, 90 days, the days the collector reads. 45 days and the fewest days 2 months can hold reach back 104 days; 1 month would reach only 73. It packs live and its window only reports. The prune verb refuses it: a day taken out of it lets the next run find every address that day held as new |
| `compact-published` | `published`, every address a digest carried | day files for 45 to 76 days, then every month file until its year is packed 93 days after it ends, then one year file for ever | `collect.published_window_days` is -1, which reads every day, so the loader refuses any window that drops a month. It packs live. The prune verb refuses it: it is the guard against publishing one story twice |
| `compact-item-health` | `item-health`, the census | day files for 31 to 62 days, then 15 month files | its floor is the `full-grain` series of `telemetry-aggregate`, 14 months, and a month is summarised before this can delete it. It packs live, with `daily_keep_days` 31: the shortest wait no GitHub re-run can outlast ([why 31](../../architecture/publishing/ledger-compaction.md#design-rationale)) |
| `compact-summary-quality-evals` | `summary-quality-evals`, the eval ledger | day files for 45 to 76 days, then every month file until its year is packed `monthly_keep_days` after it ends, then one year file for ever | every eval row is kept for ever and nothing summarises a month, so it may pack a month or a year and never drops one |
| `compact-host-fingerprint` | `host-fingerprint`, the machine record | day files for 31 to 62 days, then 14 month files | its floor is `public_machine_keep_months`, 14 months, because the published machine shard is folded from this ledger; its CSV was kept the same 14 months. It packs live, with `daily_keep_days` 31, as `compact-item-health` does |
| `compact-feed-health` | `feed-health`, what every feed did on every run | day files for 45 to 76 days, then 14 month files | its floor is the widest console read, 366 days, which can open 14 month files, and its CSV was kept the same 14 months. It packs live and its window only reports. Nothing older is summarised, because no older total has a reader |

**The last four are the ledgers the console reads**, and the console reads their
packed files and nothing newer. `compact-item-health`,
`compact-host-fingerprint` and `compact-feed-health` pack live, so a finished
day reaches the console within about 48 hours. `compact-summary-quality-evals` only reports, so the console shows its
days up to the day its migration ran
([../../architecture/contracts/persistence.md](../../architecture/contracts/persistence.md#moving-a-ledger-onto-the-door)).

### The keys of a compaction

Each declaration writes every one of these, and the loader refuses one that
leaves a key out, naming it. Nothing is filled in from code, so the file a
person reads holds every number a pass runs with.

| # | Key | What it sets |
| --- | --- | --- |
| 1 | `dry_run` | Whether a pass changes any file. `true` reports every path a live pass would write and delete, and changes nothing |
| 2 | `month_deletes_dry_run` | Whether a live pass only reports what `monthly_window` would delete. `true` keeps every month file past the window and every raw day in a month past it, and packs those days and months like the rest; the pass's record counts the kept files in `selected` and not in `deleted`. `false` lets the window delete them |
| 3 | `daily_keep_days` | How many days after a UTC month ends it is absorbed into its month file. At least 31 |
| 4 | `monthly_window` | How long a month file survives once its month is absorbed: `{unit: months, value}`, `{unit: days, value}` or `{unit: forever}` |
| 5 | `monthly_keep_days` | How many whole days after a UTC year ends its month files are packed into one year file, kept for ever. `null` packs no year. Set, it needs a `monthly_window` of forever and at least `daily_keep_days` plus 32 |
| 6 | `max_periods_per_run` | The most days, and separately the most months and the most years, one pass packs |
| 7 | `max_raw_files_per_period` | The most raw files one period is built from in one pass. A day holding more is refused and kept |
| 8 | `compact_after_days` | How many whole days after a UTC day ends before it may be packed, counted from 00:00 UTC on the day after it |
| 9 | `prune_refusal` | Whether `idhazh telemetry prune` may take a range of days out of the ledger. `null` lets it; a sentence refuses the ledger, and the command prints that sentence as the reason. `compact-summary-quality-evals` gives one, because every eval row is kept for ever ([how the prune reads it](../../how-to/prune-a-collection.md)) |

**Two switches, because packing loses no row and the monthly window does.** A
pass packs a raw day into a day file, a month of day files into a month file
and a year of month files into a year file, and deletes only files whose rows it
has just written into the coarser one. The monthly window deletes rows. So
`dry_run` decides whether a pass changes anything, and `month_deletes_dry_run`
whether the window's deletions are among the changes: a ledger can pack live
while its window only reports, and a person turns the window live after reading
what it would take. With `dry_run` `true` a pass changes nothing either way.

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
fold's as well as the task's own, and every compaction's
`month_deletes_dry_run`, which is live only while its task's own `dry_run` is
`false` too. It names the live ones as its exceptions, each with the decision
beside it: `corpus-squash`'s `dry_run`, the `dry_run` and the
`month_deletes_dry_run` of `compact-item-health` and
`compact-host-fingerprint`, the `dry_run` of `compact-counterfactual-scores`,
`compact-candidate-models`, `compact-seen`, `compact-published` and
`compact-feed-health`. A task
earns its first deletion from a person reading its records, so turning one live
is an edit to that list, never a side effect of the change that added the task.

## What the loader refuses

The declarations are validated as one set, never one at a time. Each refusal
names the file an operator edits and the rule it broke.

| Refused | Why |
| --- | --- |
| A file whose name is not lower-case words joined by hyphens | The name is the task |
| Two tasks that own one folder, or a folder inside the other's, whatever their status | Both would delete in it. A retired task keeps its claim |
| More than one task using the complement form | Each would claim what the other claims |
| An owned entry that is a file | A shard lists the files under each folder a task owns, so a file would list nothing |
| The declaration that governs `seen`, `counterfactual-scores` or `published` keeping less than the days `collect.seen_window_days`, `lens_weights.window_days` or `collect.published_window_days` reads back: its retention task while the ledger is on CSV, its compaction once it moves | A reader still opens those days. `collect.published_window_days` is `-1`, which reads every day, so nothing may delete `published`. A ledger no declaration governs is deleted by nothing, so it meets every floor |
| `telemetry-aggregate` with no series, a series that is not one of its trees, or one of its trees with no series | A tree with no window is a tree nothing bounds |
| A task's `window` that differs from its `full-grain` series, or a ceiling on a task that keeps series | One number is spelled once; a ceiling could stop a month's summary part way through |
| An `aggregate` series that does not keep longer than the `full-grain` series beside it | A month would be deleted before it was ever summarised |
| A `public-copy` series that is not equal to the `full-grain` series | The copy is the browser's copy of that ledger |
| The compaction that governs `feed-health`, a `full-grain` series or a `public-copy` series keeping fewer month files than the widest console read selects | A panel blanks for a month that ran |
| The declaration that governs the host-fingerprint ledger - its compaction - keeping less than `observability.public_machine_keep_months` | The published machine shard is folded from that ledger, so a source month deleted while its published month is kept is a shard nothing can rebuild |
| `digest-fragments` or `visual-prune` keeping anything but 30 days times `retention.image_months`, or anything but forever when that is `-1` | The archive page states that window to a reader |
| `series` on any other task | One task keeps several series |
| `fold.settles_months` beside a `window` of days | A settled month's file names no day, so a window of days would take it whole once the month's first day aged out, and with it the rows of every later day the window still keeps |
| A compaction not called `compact-<ledger>` | One compaction a ledger, found by name |
| A compaction that leaves out any key in [the table above](#the-keys-of-a-compaction) | Nothing fills a setting in from code, so a missing one is named rather than guessed |
| A key that a declaration's kind does not have, such as a misspelt or renamed key | Nothing would read it. The loader names it, so a person sees which line to change |
| A collection task not called `<collection>.json`, or whose `window` is not whole days | One task a collection, found by name; a pass counts a member's age in days |
| A compaction whose `window` is not `{unit: forever}`, or whose `max_deletes_per_run` is not `null` | Its two periods are how far back it keeps and `max_periods_per_run` is its budget. A second window would be a number nothing reads, and a ceiling could stop a month half absorbed |
| `daily_keep_days` below 31 | GitHub lets a failed run be re-run for 30 days, into the day it first wrote, so a month absorbed sooner could still be reached by one |
| `monthly_keep_days` set beside a `monthly_window` that is not forever | The window would delete a month file before its year is packed, and the year file would miss that month's rows |
| `monthly_keep_days` below `daily_keep_days` plus 32 | A year is packed only once its next January is absorbed, one wake after that January's `daily_keep_days` have passed, so a smaller value changes nothing |
| A ledger in `ledger.published` whose compaction keeps its months forever and packs no year | A reader's first request would grow with the archive. Packing years bounds it: the month files last only until their year is packed, and the yearly index grows by one entry a year |
| A published ledger whose periods reach back less than the widest `console.window_presets` | The widest span the console offers would have days no file holds |
| A compaction reaching back less far than a series that still summarises its ledger's months | The two periods are the ledger's retention now, and a month they delete before the series is done with it is a month the summary never holds |

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

**A floor belongs to a ledger, and is held against whichever declaration
deletes it.** A reader's knob, the widest console read and the published machine
shard each say how far back a ledger must reach. Each is checked against the
declaration that governs the ledger: its compaction once it files under the two
roots, else the retention task that owns its folder. A ledger neither governs is
deleted by nothing, so it meets every floor; refusing it instead would make every
fixture garden carry declarations that test nothing. So moving a ledger changes
no rule here.

**A compaction also reaches as far back as a series that summarises its
ledger's months.** For `item-health` that is the `full-grain` series of
`telemetry-aggregate`, not the `aggregate` series, which covers the summary.
Five cases: a bounded floor against a bounded pair compares; a bounded floor
against a pair kept forever passes; a floor kept forever against a bounded pair is
refused, because a person chose never to delete that ledger; forever against
forever passes; and a ledger no task ever limited has no floor. How long a moved
ledger's CSV was kept is not a declaration: `CSV_LEDGERS` in
`backend/utilities/ledger_migration/csv_layouts.py` records it, and its test holds every
moved ledger's committed compaction to it, so no retired retention task stays
behind owning a folder nothing writes.

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

**Every setting a compaction runs with is written in its declaration.** A
default in code is a number a person reading the file cannot see, so no key of
a compaction has one, and the loader refuses a declaration that leaves a key out
by its name, as `CLAUDE.md` Guardrail #3 asks of a configuration file. Keeping
the defaults and writing only the keys that differ would leave the numbers out
of the file again. The keys every kind shares to say what a task owns and
reads, `owns` or its complement form, `reads` and `appends_to`, follow the
shared rules above, because none of them is a number a pass runs with.

## See also

- [../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md) - how a wake runs.
- [retention-ages.md](retention-ages.md) - where every cleanup age lives, and why each tree keeps what it keeps.
- [../config.md](../config.md) - what makes a value a knob.
