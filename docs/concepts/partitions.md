# Partitions

**Last Updated**: 2026-10-04
A **partition** is one file holding one period of a collection that grows. The
directory is the collection and the name says the period - `<YYYY-MM>` for a month,
`<YYYY>/<MM>/<DD>` for a day. A reader opens the periods its window names and skips
the rest. A writer appends to the period its own date names and leaves the rest
alone.

**A month is the usual unit here and it is not the only one.** Eleven collections
partition by **day** instead, and the first two below are the same series - the
state ledger is derived from the published tree:

| Collection | Writer |
| --- | --- |
| `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `stages.assemble.stage_assemble` |
| `state/raw/published/<YYYY>/<MM>/<DD>/` | `ledger.append_published`, through `ledger.persist` |
| `state/day-metrics/<YYYY>/<MM>/<DD>.json` | `telemetry.publish.day_metrics.write` |
| `state/raw/visual-prunes/<YYYY>/<MM>/<DD>/` | the gardener's `visual-prune` task, through `ledger.persist` |
| `state/raw/feed-retirements/<YYYY>/<MM>/<DD>/` | `telemetry.source_health.file_retirements`, through `ledger.persist` |
| `state/raw/counterfactual-scores/<YYYY>/<MM>/<DD>/` | `stages.plan`, through `ledger.persist` |
| `state/content-similarity-judge/scored-pairs/<YYYY>/<MM>/<DD>.csv` | `ledger.append_story_similarity_pairs`, from the collecting job |
| `state/content-similarity-judge/fitted-thresholds/<YYYY>/<MM>/<DD>.csv` | `ledger.append_fitted_thresholds`, from the collecting job |
| `state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv` | `ledger.append_council_shard_outcomes`, from the collecting job |
| `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv` | `council.metrics_sink.collect_judge_metrics`, from the collecting job |
| `state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv` | `stages.score_merge_line_holdout`, from a person's own machine |

Every rule on this page reads the same with "day" in place of "month": a writer
appends to the day its own date names, a reader opens the days its window names,
and a closed day is rewritten only by a correction that targets it. The grain
follows what the reader asks for and what a removal has to take away, not the
calendar.

Why a collection partitions at all - and why several here deliberately do not - is
[the shard rule](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window)
in the contracts doc. This page is the other half: what the layout obliges a writer
to do once it exists.

## What counts as a month name

**A real calendar month, spelled in ASCII, seven characters wide.** `2025-01` is a
partition. `2025-1`, `2025-00`, `2025-13`, `0000-01` and `2025-01` written in
Arabic-Indic digits are not. One function decides it for every collection on this
page - `idhazh.month_partition.is_month_stem` - and every directory reader is
`month_partition.month_files`.

**A name it does not recognise is left alone.** It is not deleted and it is not a
fault. These directories are the top of their own tree, and a root is allowed to
hold something that is not the partitioned collection at all. The stricter rule -
below a dated level an unreadable name raises - belongs to the published day tree,
where everything under a year directory is written by `assemble.day_dir` and nothing
else (`retention.dated_days`).

**It is one function because it used to be three, and they disagreed.** Measured on
this checkout on 2026-09-08, before the fix:

| Stem | `retention` | `evals.writer` | the month summaries' reader |
| --- | --- | --- | --- |
| `2025-01` | a month | a month | a month |
| `2025-00` | a stray | **a month** | **a month** |
| `2025-13` | a stray | **a month** | **a month** |
| `0000-01` | a stray | **a month** | **a month** |
| `2025-01` in Arabic-Indic digits | a stray | **a month** | **a month** |

So `2025-13.csv` was left alone in `state/feed-health/` and was summarised and then
**deleted** in `state/scores/` - one name,
two dispositions, and the destructive one landing on the ledger that holds the evidence
behind every published quality claim. The `history` job of `idhazh-gardener.yml` force-pushes `main`
([../../CLAUDE.md](../../CLAUDE.md) section 8), so a file it removed would not come
back. The committed guard covered `notes.csv`, which every reader already refused.

**The ASCII clause is not decoration.** `str.isdigit` and `int` both accept another
script's numerals, so a stem in Arabic-Indic digits reads as January 2025 to a naive
check while a writer names its own file `2025-01`. That is two files
claiming one month, and a fold would summarise over one of them. CPython's date parser
happens to refuse that stem today, but through how it compiles its digit class rather
than through anything this rule asked for, and a detail is not a rule - so the check is
written out, and `backend/tests/gardener/tasks/test_telemetry_aggregate_task.py::test_a_file_that_is_not_a_month_shard_is_never_a_candidate`
holds the one reader left to it.

Authority: Guardrail #5 - a structural fix rather than a third copy of the rule.

## What counts as a day file

**Three segments of ASCII digits that spell a real date, and a `.csv` below them.**
`idhazh.day_partition.day_files` is the one walk, and `day_partition.days_in_window`
names the days a cover of `n` days asks for - both ends, so a cover of `n` returns
`n + 1` dates.

**Here a name the walk cannot place stops the read**, which is the one place the day
rule is stricter than the month rule above. A month directory is the top of its own
tree and may hold something that is not the collection at all. Below a year
directory, every name is written by one `append_*` and by nothing else, so a name
the walk cannot read means something else is writing there - and a walk that passed
over it would leave rows unread and unmentioned.

The ASCII clause is the same clause for the same reason, and it was not always
written out: `\d` in a Python pattern matches another script's numerals, so the walk
this replaced accepted a day stem in Arabic-Indic digits and left the refusal to
`date.fromisoformat` one level further down. An empty directory never reaches that
level, so an empty month directory named in another script's digits survived every
read. `backend/tests/test_day_partition.py` holds every day-tree reader to the rule,
as `test_a_file_that_is_not_a_month_shard_is_never_a_candidate` does one grain over.

Authority: Guardrail #5, 2026-09-11. `day_partition` is a **peer** of `month_partition`
rather than a replacement: both grains are live, so both modules are.

## Every committed path is one of three classes, and no path is in two

A partition says which period a file holds. **A class says who may write it, and
how two runs writing at once end.** Both are properties of the layout, so both
are on this page, and the classes are declared in
[`backend/idhazh/path_classes.py`](../../backend/idhazh/path_classes.py) rather than in a
workflow string - a list a workflow carries is a list the tests keep a second
copy of.

| Class | What the name means | How a race on it ends |
| --- | --- | --- |
| **written-once** | the filename carries `<run_id>-<attempt>-<job>-<shard>`, or is a `file_id` the ledger door mints for one writer, so it names exactly one writer. Nothing rewrites it or deletes it except retention, the closed-day fold and a compaction | two writers cannot name one file, so there is no race to settle |
| **derived** | the content is a function of other jobs' output. It is handed back to the tip before the rebase and rebuilt against it | the rebuild wins. It is never text-merged and never settled by who wrote it |
| **union-safe** | append-only rows, `merge=union`, **and a named read-side property that makes a repeat change no answer** | both sides land whole, and the reader settles them |

**A union-safe path with no such property is a derived path written badly**, so
the property is named rather than assumed. A council or judge row qualifies
because one row is one measurement of one thing on one day, and says nothing
about any other row. `state/seen` and `state/published` qualified too, because
their readers keep the earliest stamp and the earliest publication date per
address, until they moved under `state/raw/`, where every file is written once.
The merge driver concatenates whatever it is handed, so a
path that cannot name the sentence does not get the driver.

**The three classes are closed, and that is what makes the layout survive the
repository growing.** A path that appears after this page was written gets a
class, not a redesign: it either names its writer, or it is rebuilt from the tip,
or its repeat changes no answer. There is no fourth thing a committed file can
be, so a new path is one line in `idhazh.path_classes` and at most one migration.

**A derived path may never be declared owned**, and that rule is what keeps the
other two honest. Settling one in favour of a single writer deletes the other
writer's rows and exits 0 - three written-once inputs all land intact while the
file derived from them quietly loses half its content, and no gate can see it.
What the push does with each class is
[in committing.md](../architecture/publishing/committing.md#a-conflicted-path-is-settled-by-who-wrote-it-never-by-which-side-it-came-from).

`backend/tests/contracts/test_path_classes.py` holds the three sets pairwise
disjoint and covering every path a production stage writes. It enumerates the
writers from `idhazh.path_classes` itself and never from the tree, so its cost does not
rise with what the pipeline has piled up (`CLAUDE.md` Guardrail #12).

Authority: Fowler and Carmack, converged, 2026-09-22.

## The day directory is the ledger, and the settlement moves to the reader

**Every ledger more than one job writes files its rows in a day directory, and
every file in it carries its writer's name.** `state/<ledger>/<YYYY>/<MM>/<DD>/`
holds one `<run_id>-<attempt>-<job>-<shard>.csv` per writer, spelled once in
`ledger.segment_name`. Two writers cannot name one file, so two runs pushing at
once cannot collide on it - which is the whole reason the shape exists.

A ledger that goes through the ledger door has the same property one level down:
`state/raw/<ledger>/<YYYY>/<MM>/<DD>/` holds one file per write, the door mints
its name, and the writer's identity is inside the file
([../architecture/contracts/persistence.md](../architecture/contracts/persistence.md)).
The item-health, summary-quality-evals and host-fingerprint ledgers moved there; what follows on
this page is about the CSV day trees.

**Since 2026-09-22 there is no head above it.** A producer writes the final day
path directly, and `state/segments/` is gone. The shape used to be a staging
directory a later fold read into a `<DD>.csv` head, which meant every ledger had
one path that two runs of one day both computed bytes for. Now the day directory
*is* the ledger: the only thing that changed at the cutover was the parent.

`idhazh.day_shards` is the walk, and a day is a `<DD>/` directory and nothing
else. `day_shards.shard_files(root, days=...)` yields every file of the newest
`days` recorded days, and **the cover counts days rather than files**, so a day
of five writers is still one day. `day_shards.date_of` reads the date off the
three directory names above the file and opens nothing. A `<DD>.csv` beside a
month's day directories is a name no writer spells, so the walk refuses it with
every other stray.

**The settlement is a read, not a write.** `day_shards.settled_rows` runs the
three cases a compaction ran into a head - join, supersede, repeat - and the
gardener's closed-day fold calls the same code, so there is one fold rather than one per
ledger. Ascending attempt is the order, so a correction always arrives after
what it corrects, and the tie-break is the path relative to the ledger root:
`settled.csv` has the same basename in every day directory, and a reader
spanning two days would otherwise have no total order at all.

**`settled.csv` is the one name in a day directory that is not a writer's.** It
is what a closed-day fold leaves behind, and it reads at attempt 0 - a writer's
attempt is the run's own `GITHUB_RUN_ATTEMPT`, which starts at 1, so 0 is a
place no writer can take. It is also the right place: its rows have already won
a settlement, and a straggler beside it is later. The fold is what stops one
file per writer per day becoming unbounded growth, and what it costs is covered
by the fixed-size input rule in [CLAUDE.md](../../CLAUDE.md) Guardrail #12.
A tree whose task settles months holds one more: a closed month's `settled.csv`
in the month's own folder, the one file a month folder may hold. It reads at
attempt 0 too, so a file a re-run adds to that month later is settled after it.

**`before-partition.csv` is the other.** It is what the 2026-09-22 migration
wrote, one per day, because a committed head is many runs already merged and so
has no writer identity to stamp. It reads at attempt 0 beside `settled.csv` and
it sorts first. Removal condition: it goes when the oldest committed day is
newer than the migration date.

**A day directory holding no readable file stops the read.** That is the same
rule as the stray above and not a new one: a day nothing wrote has no directory,
so an empty one is a writer that made the directory and lost its rows. Reading
it as a day that recorded nothing would draw an empty panel on a passing build.

**`day_partition.day_files` is not taught the directory shape, on purpose.** It
keeps its callers over the union-safe ledgers - the judge's and the council's
day files - which stay one file a day, and its loud refusal of
a directory is the tripwire that catches a ledger arriving in the new shape
without a plan.

Authority: Fowler, 2026-09-22.

## How a collection changes grain

Move only named files or periods. Build their new layout in a temporary run
directory, read it through the production reader, and compare every row by its
UTC day before replacing the source. An invalid date stops the move. A failed
read-back leaves the source intact. Delete a completed one-off utility and its
tests when no current operation needs it; git keeps the cutover code.

Changing grain is different from [a correction](#a-correction-to-a-closed-month),
which rewrites one partition and leaves the layout alone.

## The freeze rule

**A closed month is rewritten only when a correction targets it. Every other run
touches the current partition alone.**

A partition is **closed** when the writer's own date no longer falls in it. Not
"old" and not "past retention" - closed the moment the calendar moves on, which for
a daily pipeline is the first run of the next month.

The rule binds writes to time partitions, not reads. A closed partition is
still opened when `day_partition.days_in_window` names it. What bounds reads is
[CLAUDE.md](../../CLAUDE.md) Guardrail #12, not whether a partition is closed.

Authority: owner, 2026-09-06.

## The partitioned collections

| Collection | Path pattern | Writer | What makes a partition closed |
| --- | --- | --- | --- |
| Eval ledger | `state/raw/summary-quality-evals/<YYYY>/<MM>/<DD>/`, packed under `state/compact/summary-quality-evals/` | `evals.writer.file_measurements`, through `ledger.persist` | Partitioned by **day** since 2026-09-13, and filed through the ledger door since it moved. It files each row by the row's own `date`, so a day is closed once no row being written names it. A run either side of midnight writes two day files and neither is wrong. Every write is a file of its own, so two runs never collide on one, and a packing task makes each finished day one file. It had a monthly mirror under `frontend/public/scores/` until 2026-09-16; nothing fetched it, so there is no published grain to keep in step. |
| Item health | `state/raw/item-health/<YYYY>/<MM>/<DD>/`, packed under `state/compact/item-health/` | `ledger.persist`, from `stages.record` and `stages.assemble` | Partitioned by **day** since 2026-09-13, and filed through the ledger door since it moved. Each write files its own rows under the day those rows name, as a file of its own, so two runs never collide on one. Closed once the run's date leaves the day. |
| Feed health | `state/raw/feed-health/<YYYY>/<MM>/<DD>/`, packed under `state/compact/feed-health/` | `stages.plan`, through `ledger.persist` | Partitioned by **day** since 2026-09-13, and filed through the ledger door since it moved. The plan stage writes the run's own digest date and nothing else, as a file of its own, so two runs never collide on one, and a second attempt at one plan job replaces its first attempt's file. Closed once the run's date leaves the day. Its compaction makes each finished day one file, and the loader refuses one that keeps fewer month files than the widest console read opens. It had a monthly mirror under `frontend/public/feed-health/` until 2026-09-16; nothing fetched it, so there is no published grain to keep in step. |
| Seen addresses | `state/raw/seen/<YYYY>/<MM>/<DD>/`, packed under `state/compact/seen/` | `ledger.append_seen`, through `ledger.persist` | Partitioned by **day** since 2026-09-13, and filed through the ledger door since it moved. The plan job files under the run's own digest date and nothing else, as a file of its own, so two runs never collide on one, and a second attempt at one plan job replaces its first attempt's file. Closed once the run's date leaves the day. Its compaction makes each finished day one file, and the loader refuses one that keeps fewer days than `collect.seen_window_days`. It has no published mirror at all, so unlike the two health ledgers there is no second grain anywhere near it. |
| Counterfactual scores | `state/raw/counterfactual-scores/<YYYY>/<MM>/<DD>/`, packed under `state/compact/counterfactual-scores/` | `stages.plan`, through `ledger.persist` | Partitioned by **day** since 2026-09-14, and filed through the ledger door since it moved. The plan stage writes the run's own digest date and nothing else, so the day closes when the day's last run finishes. Every write is a file of its own, so two runs never collide on one, and its compaction makes each finished day one file. Its only reader will open a trailing window, `lens_weights.window_days`, and the loader refuses a compaction that keeps less. |
| Telemetry projection | `frontend/public/telemetry/<YYYY-MM>.csv` | `telemetry.publish.public_telemetry.publish` | It writes only the months a caller names as changed, and rewrites a named month only when its projected bytes differ from the committed shard - so a closed month is neither read nor rewritten once nothing targets it. Frozen since row 19 of the constant-cost-reads plan (#484). |
| Folded item health | `state/item-health-summary/<YYYY-MM>.csv` | `retention.compact_month`, written by `ledger.write_item_health_summary` | Written once, when the item-health month passes the `full-grain` series of `config/gardener/telemetry-aggregate.json` (14 months). It stays **monthly** while the ledger below it files by day, because it summarises a month and a day file of a month's totals is a shape nothing consumes - so the summary is where the two grains meet, reading the month's days through `ledger.load_days` and writing one file. Closed the moment it is written; the rows it summarises go later, when the item-health compaction's `monthly_window` passes, and nothing writes the summary again. No file is committed yet. |
| Search index | `frontend/public/assist/index/<YYYY-MM>.json` and `<YYYY-MM>.bin` | `assemble.rebuild_search_index` | It is derived whole from the committed days of that month, so the month is closed once no day inside it changes. `stages.assemble.stage_assemble` rebuilds only `month_of(plan.date)`. |
| Published addresses | `state/raw/published/<YYYY>/<MM>/<DD>/`, packed under `state/compact/published/` | `ledger.append_published`, through `ledger.persist` | Partitioned by **day**, not by month, and filed through the ledger door since it moved. The caller hands the date and the writer files that day alone, as a file of its own, so a day is closed once the run's date leaves it. Its read carries `collect.published_window_days`, which the committed config sets to `-1` - the cover is open, and the partition is what a finite value would have to skip. **A finite value must be strictly wider than `collect.seen_window_days`**, and `CollectConfig` refuses one that is not: an undated address whose sight row expires the same week reads as first-seen-today and republishes as new. |
| Day metrics | `state/day-metrics/<YYYY>/<MM>/<DD>.json` | `telemetry.publish.day_metrics.write` | Partitioned by **day**. One record per published day, mirroring the published tree it is derived from, and closed the moment that day is. The site opens only the dates a page names, so nothing walks the tree. |
| Visual prunes | `state/raw/visual-prunes/<YYYY>/<MM>/<DD>/` | the gardener's `visual-prune` task, through `ledger.persist` | Partitioned by **day**, and one of the two collections here whose read will never carry a window - the question is the whole series. It files by day anyway, for the two things the grain buys with no read time at all: every pass files a file of its own, so two passes never write one path and the tree needs no merge driver, and taking a day back off the record is one `rm` of that day's folder. It moved under `state/raw/` on 2026-09-28, from `<YYYY>/<MM>/<DD>.csv` day files that carried a `merge=union` line. Closed once the pass's date leaves the day. |
| Feed retirements | `state/raw/feed-retirements/<YYYY>/<MM>/<DD>/` | `telemetry.source_health.file_retirements`, through `ledger.persist` | Partitioned by **day** since 2026-09-28, where it was one flat file, `state/feed-retirements.csv`. A retirement files under the day the address was retired, so a day is closed once the run's date leaves it. It is the other collection here whose read never carries a window: a retirement is permanent for one address, so the reader opens every file. The grain buys it what it buys the cleanup record above. |
| Scored pairs | `state/content-similarity-judge/scored-pairs/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day**, and the first collection here that nests one directory deeper than `state/` - the whole adaptive merge line hangs off `state/content-similarity-judge/`, so a commit step stages one prefix. A day is closed once its pairs have been folded into the score record, which happens once. The shape, the path and the header ship ahead of the step that appends to them (Guardrail #3). |
| Fitted thresholds | `state/content-similarity-judge/fitted-thresholds/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day** for the reason its sibling is, and unlike that sibling its read does carry a window: the step-change guard takes a median over the newest `step_change_window_rows` written rows, and `assemble` looks back `applied_lookback_days` for a line to apply. Closed once the run's date leaves the day. |
| Council shard outcomes | `state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day**, and it is the one collection here whose day is **not** the day its writer ran: a row files by the digest date it judged, so one night's run appends to every date its plan covered and a day is closed once no later night still names it. Nested one directory deeper than `state/` for the reason the adaptive merge line is - everything the council records about itself hangs off one prefix, so a commit step stages one path. Two directory levels and no more: the day inventory globs one level and two, so a third would be invisible to it and the miss would be silent. The shape, the path and the header ship ahead of the step that appends to them (Guardrail #3). |
| Content-similarity judge metrics | `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day**, and it files by the digest date the shard judged rather than the day the run started - the same grain as the council record beside it, so a reader holding one night's units of work against one night's readings opens one day file in each. Nested one directory deeper than `state/` under a prefix named for the judge rather than the venue it ran in: what a reading is ABOUT decides where it is filed, never what executed it, so this ledger stays put on the day the council stops hosting this judge. Two directory levels and no more, for the reason the council record gives. The shape, the path and the header ship ahead of the step that appends to them (Guardrail #3). |
| Merge-line holdout scores | `state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv` | `stages.score_merge_line_holdout`, run by a person | Partitioned by **day**, filing by the day the line was scored - not by either of the two dates the labelled pair names, which the holdout row carries itself. One row a day, for the reason the fitted line files by day: a read that carries a window over the newest rows, and one `rm` to take a day's reading back off the record. It sits under the judge's prefix and holds no judge's reading at all: the shipped scoring calls no model, so the row carries no call stamp. Closed once the run's date leaves the day. **No job writes it and no job stages it**: a person runs `idhazh score-merge-line-holdout` and commits the row, the way the marked file beside it is committed. |
| Model validation | `state/<run.trial_state_dirname>/raw/candidate-models/<YYYY>/<MM>/<DD>/` | `stages.qualify_decide` or `stages.decide`, through `ledger.persist` | Partitioned by **day** since 2026-09-18, where it was `state/validation-<date>.csv` at the root of `state/`, and filed through the ledger door since it moved. The old path was a hardcoded string joined to the repository root, so no config could move it and a trial dispatch wrote production state. There is no `state/raw/candidate-models/` tree: the ledger lands under whatever `common.STATE_ROOT` names, which a pipeline-tests dispatch points at `state/pipeline-tests/`, and nothing packs a trial root. Closed once the run's date leaves the day. Two candidates can be dispatched at once, so neither opens a shared file: each run is its own work unit and files its own raw file. |
| Traces | `state/traces/<YYYY>/<MM>/<DD>/` | `telemetry.traces` | Partitioned by **day** the whole time, and a **day directory** since 2026-09-22 - the day used to be a prefix on the filename. A trace carries no date cell, so the run id is what says which day it belongs under. It is JSON lines rather than CSV, which is the whole of what it does differently, and the gardener's `traces` task deletes whole files past its window rather than folding them: a trace is a lookup, and a fold of it would invent a total nobody reads. |

The collection with nothing committed is not aspirational. Its writer ships and is
tested; it has not fired, because the oldest committed month is `2026-08` and its age
is fourteen months.

## The last unfrozen partition is frozen now

The telemetry projection `frontend/public/telemetry/<YYYY-MM>.csv` was the one
place in the tree where the layout existed and the rule did not:
`public_telemetry.publish` globbed `state/item-health/` and rewrote every month
it found, on every run, for an answer it already had. Row 19 of the
[constant-cost-reads plan](../../TODO/20260906-constant-cost-reads-plan.md)
closed it in #484: the writer now takes the row above, writing only the months a
caller names as changed and rewriting a named month only when its bytes differ.
What it writes, and how the two freezes compose, is
[in the telemetry doc](../architecture/publishing/telemetry-series.md#published-shards).

## A ledger and its mirror may file at different grains

**The item-health ledger files by day and `frontend/public/telemetry/` files by
month, and neither is a mistake.** They answer different questions, so they take
their grain from different things.

- **A `state/` ledger's grain follows what a run writes and what a removal takes
 away.** A run writes one day, two runs collide on a file only when they are the
 same day, and taking a day back is one `rm` rather than an edit inside a shared
 shard - which no merge driver can express.
- **A `frontend/public/` mirror's grain follows what a browser fetches.** The
 console prices a window in files: `console.window_presets` ends at 90, and
 `WindowControl.svelte` tells the operator how many files a preset costs. At
 month grain the widest preset fetches five; at day grain it would fetch ninety.

**So somebody has to bridge them, and it is the publisher.**
`public_telemetry.publish` folds a month from that month's days, read through
`ledger.load_days`, and the gardener's `telemetry-aggregate` task summarises on
the same boundary. A month's input is at most 31 days, so the bridge is a
ledger-bounded read rather than a growing one.

**A day tree's filenames are an index of which days the ledger holds, and a
bridge reads that index instead of doing calendar arithmetic.**
`source_health._recent_item_health` wants the newest
`source_yield_min_complete_days` dates the ledger actually recorded, which is not
the set a calendar window of the same width names - a gap in the record leaves
the window short, and widening it until it is long enough reads back to the first
run the project made. `ledger.held_days` reads that index from the two compact
indexes and the raw day folders' names, so the newest `keep` days are the answer
and no data file behind them is opened. A month name could not do this: it says
only that the ledger holds records somewhere inside that month.

What the day grain costs, stated rather than implied: the unbounded case of
`public_telemetry.publish` opens about thirty times as many file handles for the
same rows, and every listing of the ledger names one entry a recorded day instead
of one a month. What it buys is the two properties in the first bullet, and a
windowed read that opens exactly the days it names - where a 90-day cover over
month shards opened files holding up to 120 days of rows.

Authority: owner, 2026-09-10; [`20260910-24-day-sharded-ledgers-plan.md`](../../TODO/20260910-24-day-sharded-ledgers-plan.md)
section 0.2.

## The four cases an append-only pattern gets wrong

A pattern that only handles appends is a trap, so each of these has an answer here.

### A correction to a closed month

Rewrite that month, and only that month. This is the one thing the freeze rule
permits, and it is the whole reason the rule says "only when a correction targets it"
rather than "never".

Two constraints make a correction a deliberate act rather than an ordinary write.
A commit that removes rows from a shard, rebased onto a tip that added some, is a
rebase git cannot apply - so the removal stops the push rather than landing
half-done. Until 2026-09-19 `.gitattributes` set a union merge driver on
`state/**/*.csv` and the same rebase resolved by keeping both sides, which was
worse: the removal silently did not happen. And a shard's header is checked
against the contract
before any append, so a rewrite that changes the shape has to move every month at once.
A correction therefore ships as a committed one-shot utility under
`backend/utilities/`, not as an ad-hoc script. It takes named input files.
A utility whose input layout no longer exists is deleted with the layout.

### A deletion

Two kinds, and they are not the same operation.

and a compaction unlinks a door ledger's month file. Evaluation IDs never age
**A whole partition ages out.** `telemetry-aggregate` removes an expired
published copy, and a compaction unlinks an expired month from its ledger.
Evaluation IDs never age out. The partition is the unit, nothing
is edited, and the freeze rule has no opinion because there is no month left to
rewrite. What bounds each collection is
[the state-tree section](../architecture/publishing/retention.md#what-bounds-the-committed-state-tree)
of the publishing doc.

**Rows go from a partition that stays.** That is a correction and it takes the path
above. Taking a day off the site must also update its search entries and derived
published data without removing neighbouring days.
[Unpublishing a day](../architecture/publishing/retention.md#unpublishing-a-day)
has no implemented command.

### A late arrival

A row whose date falls in a month that is not the run's own. `ledger.persist`
handles it by construction, because it files each row under the day its own
`date` names rather than the run's. `ledger.write_segment` does the same. Every `ledger.append_*` is handed one
date and appends to that month, so its
caller decides: hand it a date in a closed month and it has performed a correction.

A derived partition needs no special case. The search index is rebuilt from the days
on disk, so
[a deleted day needs no cleanup](../architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md#the-shard-is-derived-so-retention-needs-nothing) -
the next rebuild simply writes a shard that no longer names it. The obligation that
remains is the one the layout doc states: every writer of a committed day payload owes
its month a rebuild.

### A row that moves between months

Nothing moves. A row's partition is a function of its own `date`, and a date does not
change. Where a date really does change, that is a removal from the old month and an
append to the new one - two corrections, both under the first case, and never an
in-place move. Nothing in the tree does this today.

## What is not partitioned

Naming these is what makes the pattern honest about its own coverage. It is not a
commitment to convert any of them.

| Collection | Path | Writer | Why not |
| --- | --- | --- | --- |
| Source health view | `frontend/public/source-health.json` | `telemetry.publish.source_health` | One document, rewritten whole each run. Row 20 of the constant-cost-reads plan bounded the read behind it to the recorded dates it needs (#485), so it no longer walks all history to write the same document. |
| Training corpus | `corpus/corpus.jsonl`, `corpus/corpus.meta.json`, `corpus/holdout.txt` | `idhazh.corpus`, rolled by `backend/utilities/data_wrangler.py` | A rolling training window bounded by `finetune.corpus_rows` and by the corpus squash in `idhazh-gardener.yml`, not by a calendar. Deliberately given no union merge driver, because the union of two rolls holds evicted rows again. |
| Published days | `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `stages.assemble.stage_assemble` | Partitioned by **day**, and listed here because it is the tree the day grain came from rather than because it is unpartitioned. A day is frozen the moment it is written. The month partitions above are keyed off this tree, and so is the published ledger. |

## Design rationale

**The page was `month-partitions.md` until 2026-09-11, and only its title was
wrong.** It covered both grains from its first revision, so a reader looking for
the day rule was sent past the page that held it - which is the failure
[`../../CLAUDE.md`](../../CLAUDE.md) section 5 names. Four collections file by
day today and five state ledgers are moving to that grain, so a page titled for
months was about to describe the minority.

Keeping the old name and extending the page was the alternative. It was refused
because the extension is what makes the title wrong: 14 links in 7 files stay
correct either way and a link repoint is mechanical, while a title nobody trusts
is not repaired by anything. What it cost: every link had to move in one commit,
and a clone taken before it has a `month-partitions.md` that no longer exists.
Authority: `CLAUDE.md` section 5, 2026-09-11.

## See also

- [../../CLAUDE.md](../../CLAUDE.md) Guardrail #12 - every read must have a fixed-size input.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window) - why a ledger partitions at all, and which reads carry a window.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md#published-shards) - the published projection of item health, one file a month.
- [../architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md](../architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md#the-month-search-index) - the month search index, its ceilings, and what an unpublish owes each grain.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the fastest-growing collection, and what would move it to a shorter period.
- [../reference/repository-layout.md](../reference/repository-layout.md) - what each top-level directory holds and who writes it.
- [../reference/data-growth.md](../reference/data-growth.md) - where growing work is heading, what a replacement owes before the old path goes, and the shortcuts that are not answers.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #12 (nothing costs more as the repository grows) and section 11 (schema versioning).
