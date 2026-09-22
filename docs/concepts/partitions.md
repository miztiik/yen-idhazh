# Partitions

**Last Updated**: 2026-09-22
A **partition** is one file holding one period of a collection that grows. The
directory is the collection and the name says the period - `<YYYY-MM>` for a month,
`<YYYY>/<MM>/<DD>` for a day. A reader opens the periods its window names and skips
the rest. A writer appends to the period its own date names and leaves the rest
alone.

**A month is the usual unit here and it is not the only one.** Ten collections
partition by **day** instead, and the first two below are the same series - the
state ledger is derived from the published tree:

| Collection | Writer |
| --- | --- |
| `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `stages.assemble.stage_assemble` |
| `state/published/<YYYY>/<MM>/<DD>.csv` | `ledger.append_published` |
| `state/day-metrics/<YYYY>/<MM>/<DD>.json` | `telemetry.publish.day_metrics.write` |
| `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` | `ledger.append_visual_prunes` |
| `state/counterfactual-scores/<YYYY>/<MM>/<DD>.csv` | `ledger.append_counterfactual_scores` |
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
fault. These directories are the top of their own store, and a root is allowed to
hold something that is not the partitioned collection at all. The stricter rule -
below a dated level an unreadable name raises - belongs to the published day tree,
where everything under a year directory is written by `assemble.day_dir` and nothing
else (`retention._dated_days`).

**It is one function because it used to be three, and they disagreed.** Measured on
this checkout on 2026-09-08, before the fix:

| Stem | `retention` | `evals.writer` | `evals.archive` |
| --- | --- | --- | --- |
| `2025-01` | a month | a month | a month |
| `2025-00` | a stray | **a month** | **a month** |
| `2025-13` | a stray | **a month** | **a month** |
| `0000-01` | a stray | **a month** | **a month** |
| `2025-01` in Arabic-Indic digits | a stray | **a month** | **a month** |

So `2025-13.csv` was left alone in `state/feed-health/` and was summarised into
`state/score-archive/2025-13.json` and then **deleted** in `state/scores/` - one name,
two dispositions, and the destructive one landing on the store that holds the evidence
behind every published quality claim. `prune.yml` force-pushes `main`
([../../CLAUDE.md](../../CLAUDE.md) section 8), so a file it removed would not come
back. The committed guard covered `notes.csv`, which every reader already refused.

**The ASCII clause is not decoration.** `str.isdigit` and `int` both accept another
script's numerals, so a stem in Arabic-Indic digits reads as January 2025 to a naive
check while `evals.writer.append` names its own file `2025-01`. That is two files
claiming one month, and a fold would summarise over one of them. CPython's date parser
happens to refuse that stem today, but through how it compiles its digit class rather
than through anything this rule asked for, and a detail is not a rule - so the check is
written out, and `backend/tests/retention/test_telemetry_fold.py::test_the_month_readers_all_agree_on_what_a_month_is`
holds all four readers to it.

Authority: Guardrail #5 - a structural fix rather than a third copy of the rule.

## What counts as a day file

**Three segments of ASCII digits that spell a real date, and a `.csv` below them.**
`idhazh.day_partition.day_files` is the one walk, and `day_partition.days_in_window`
names the days a cover of `n` days asks for - both ends, so a cover of `n` returns
`n + 1` dates.

**Here a name the walk cannot place stops the read**, which is the one place the day
rule is stricter than the month rule above. A month directory is the top of its own
store and may hold something that is not the collection at all. Below a year
directory, every name is written by one `append_*` and by nothing else, so a name
the walk cannot read means something else is writing there - and a walk that passed
over it would leave rows unread and unmentioned.

The ASCII clause is the same clause for the same reason, and it was not always
written out: `\d` in a Python pattern matches another script's numerals, so the walk
this replaced accepted a day stem in Arabic-Indic digits and left the refusal to
`date.fromisoformat` one level further down. An empty directory never reaches that
level, so an empty month directory named in another script's digits survived every
read. `backend/tests/test_day_partition.py` holds every day-tree reader to the rule,
as `test_the_month_readers_all_agree_on_what_a_month_is` does one grain over.

Authority: Guardrail #5, 2026-09-11. `day_partition` is a **peer** of `month_partition`
rather than a replacement: both grains are live, so both modules are.

## A day can be a directory, and the settlement moves to the reader

**Where more than one job writes one ledger, the day is a directory and every
file in it carries its writer's name.** `state/<ledger>/<YYYY>/<MM>/<DD>/` holds
one `<run_id>-<attempt>-<job>-<shard>.csv` per writer, spelled once in
`ledger._segment_name`. Two writers cannot name one file, so two runs pushing at
once cannot collide on it - which is the whole reason the shape exists.

`idhazh.day_shards` is the walk, and it reads **both** shapes: a `<DD>.csv` day
file and a `<DD>/` day directory are each one recorded day.
`day_shards.shard_files(root, days=...)` yields every file of the newest `days`
recorded days, and **the cover counts days rather than files**, so a day of five
writers is still one day. `day_shards.date_of` reads the date off either shape
without opening the file.

**The settlement is a read, not a write.** `day_shards.settled_rows` runs the
three cases a compaction ran into a head - join, supersede, repeat - and
`stages.compact` calls the same code, so there is one fold rather than one per
ledger. Ascending attempt is the order, so a correction always arrives after
what it corrects, and the tie-break is the path relative to the ledger root:
`settled.csv` has the same basename in every day directory, and a reader
spanning two days would otherwise have no total order at all.

**`settled.csv` is the one name in a day directory that is not a writer's.** It
is what a closed-day fold leaves behind, and it reads at attempt 0 - a writer's
attempt is the run's own `GITHUB_RUN_ATTEMPT`, which starts at 1, so 0 is a
place no writer can take. It is also the right place: its rows have already won
a settlement, and a straggler beside it is later.

**A day directory holding no readable file stops the read.** That is the same
rule as the stray above and not a new one: a day nothing wrote has no directory,
so an empty one is a writer that made the directory and lost its rows. Reading
it as a day that recorded nothing would draw an empty panel on a passing build.

**`day_partition.day_files` is not taught the directory shape, on purpose.** It
keeps its callers over `state/published/` and `state/visual-prunes/`, which stay
one file a day, and its loud refusal of a directory is the tripwire that catches
a store arriving in the new shape without a plan.

Authority: Fowler, 2026-09-22.

## How a collection changes grain

**One utility moves a store from month files to day files, and it refuses to write a
tree it cannot read back.** `backend/utilities/migrate_to_day_shards.py` takes
`--directory`, the store, and `--date-column`, the cell that says which day a row
belongs to. Each ledger's own change runs it once on its own directory; committing the
utility migrates nothing.

It builds the whole day tree in a temporary directory beside the store, walks it with
`day_partition.day_files` - the pipeline's own reader rather than a second opinion - and
compares it row for row against what came out of the month shards. Only then does it
rename the year directories into place and unlink the month shards. **A migration that
writes an empty tree and unlinks its source is a delete with exit 0**, so the read-back
is the point and the ordering is the guarantee.

**A row it cannot place stops the run before a byte is written.** An empty date cell and
a date cell that is not a date are what a real ledger eventually holds - a run
interrupted mid-append, a header migration half applied - and a skipped row is a
measurement that stops having happened.

**A store holding a month shard and anything else is refused**, and that is not
tidiness. `day_files` refuses a name it cannot place, so a month shard sitting beside a
year directory stops every read of that store: a half-migrated store is already
unreadable by the pipeline. The repair is a restore from the trunk rather than a second
pass, because a second pass cannot know which rows the first one had already moved.

**Which cell names the day, and why `state/seen/` files by `first_seen_run`.** The day
is the cell's first ten characters, and the cell is either exactly those ten or
continues with `-`. A run id is `<date>-<n>`, so filing by `first_seen_run` reproduces
`ledger.append_seen`'s own filing exactly. A wall-clock stamp is `<date>T<time>Z`, and
the `T` is refused - `first_seen_at` crosses midnight independently of the run its row
belongs to, so a tree filed by it would disagree with the writer that built it. One
clause makes that choice mechanical instead of leaving it to a comment.

Changing grain is a different operation from [a correction](#a-correction-to-a-closed-month),
which rewrites one partition and leaves the layout alone. Both ship as a committed
one-shot utility under `backend/utilities/` for the same reason: a fork or a stale
branch can then reproduce the exact cutover this repository ran.

Authority: Guardrail #5, 2026-09-13.

## The freeze rule

**A closed month is rewritten only when a correction targets it. Every other run
touches the current partition alone.**

A partition is **closed** when the writer's own date no longer falls in it. Not
"old" and not "past retention" - closed the moment the calendar moves on, which for
a daily pipeline is the first run of the next month.

The rule binds writes, not reads. A closed partition is still opened:
`day_partition.days_in_window` opens every date a reader's window names, and
`evals.writer.recorded_observations` reads every index partition there is. What
bounds reads is [growing-reads.md](growing-reads.md) - the cover a read declares,
and `CLAUDE.md` Guardrail #12 behind it. **`evals.writer.append` was the example
here until 2026-09-13** and is not one any more: it checked the header of every
committed shard before writing, and at day grain that would have cost one more
open a day for ever, so its cover is now the one or two days it writes.

Authority: owner, 2026-09-06.

## The partitioned collections

| Collection | Path pattern | Writer | What makes a partition closed |
| --- | --- | --- | --- |
| Eval ledger | `state/scores/<YYYY>/<MM>/<DD>.csv` | `evals.writer.append` | Partitioned by **day** since 2026-09-13. It files each row by the row's own `date`, so a day is closed once no row being written names it. A run either side of midnight writes two day files and neither is wrong. The day grain buys what it buys for `state/item-health/`: two runs collide on a file only when they are the same day, and taking a day back is one `rm`. It had a monthly mirror under `frontend/public/scores/` until 2026-09-16; nothing fetched it, so there is no published grain to keep in step. |
| Score index | `state/score-index/<YYYY>/<MM>/<DD>.csv` | `evals.writer.append`, refilled by `refresh_index` | Partitioned by **day** since 2026-09-13, and it files by the ledger's day rather than a grain of its own: `refresh_index` fills a partition with no index from the partition beside it, so two grains in one relationship would be a mapping somebody maintains. Its rows carry no date at all, which is why the committed history was **regenerated** by `idhazh rebuild-score-index` rather than split - nothing in the file said which day a row belonged to. Closed when the day beside it is. |
| Item health | `state/item-health/<YYYY>/<MM>/<DD>.csv` | `ledger.append_item_health` | Partitioned by **day** since 2026-09-13. It takes one date and appends to that day alone, filtering against `ITEM_HEALTH_KEY` in that one file. Closed once the run's date leaves the day. The day grain buys the two things `state/published/` buys: two runs collide on a file only when they are the same day, and taking a day back is one `rm` rather than an edit inside a shared shard, which no merge driver can express. |
| Feed health | `state/feed-health/<YYYY>/<MM>/<DD>.csv` | `ledger.append_health` | Partitioned by **day** since 2026-09-13. The same one-date append, then it settles that one day file against `FEED_HEALTH_KEY`. Closed once the run's date leaves the day. The day grain buys what it buys for `state/item-health/`: two runs collide on a file only when they are the same day, and taking a day back is one `rm` rather than an edit inside a shared shard. It had a monthly mirror under `frontend/public/feed-health/` until 2026-09-16; nothing fetched it, so there is no published grain to keep in step. |
| Seen addresses | `state/seen/<YYYY>/<MM>/<DD>.csv` | `ledger.append_seen` | Partitioned by **day** since 2026-09-13. The same one-date append, and the date is the run's own digest date - which is why `first_seen_run[:10]` names the file every row inside it sits in. Closed once the run's date leaves the day. It has no published mirror at all, so unlike the two health ledgers there is no second grain anywhere near it. |
| Counterfactual scores | `state/counterfactual-scores/<YYYY>/<MM>/<DD>.csv` | `ledger.append_counterfactual_scores` | Partitioned by **day** since 2026-09-14. The plan stage appends the run's own digest date and nothing else, so the day closes when the day's last run finishes. It is the one collection here whose day file is created even when the run has no rows for it: the plan job's commit step names the directory, and `git add` under `set -e` aborts on a path that is not there. Its only reader opens a trailing window, and `retention.prune_counterfactual_scores` deletes what falls below it. |
| Telemetry projection | `frontend/public/telemetry/<YYYY-MM>.csv` | `telemetry.publish.public_telemetry.publish` | It writes only the months a caller names as changed, and rewrites a named month only when its projected bytes differ from the committed shard - so a closed month is neither read nor rewritten once nothing targets it. Frozen since row 19 of the constant-cost-reads plan (#484). |
| Folded item health | `state/telemetry-aggregate/<YYYY-MM>.csv` | `retention.compact_month`, written by `ledger.write_telemetry_aggregate` | Written once, when the item-health month passes `observability.item_health_full_grain_months` (14). It stays **monthly** while the ledger below it files by day, because it summarises a month and a day file of a month's totals is a shape nothing consumes - so the fold is where the two grains meet, reading at most 31 day files and writing one. Closed the moment it is written; the days it summarises are gone, so there is nothing left to append. No file is committed yet. |
| Score archive | `state/score-archive/<YYYY-MM>.json` | `evals.archive`, driven by `retention.prune_scores` | Written once, when the scores month passes `observability.scores_full_grain_months` (14), and only after it reconciles against a second reading of that month's day files. It stays **monthly** while the ledger below it files by day, for the reason the folded item health gives: it summarises a month. Closed the moment it is written. No file is committed yet. |
| Search index | `frontend/public/assist/index/<YYYY-MM>.json` and `<YYYY-MM>.bin` | `assemble.rebuild_search_index` | It is derived whole from the committed days of that month, so the month is closed once no day inside it changes. `stages.assemble.stage_assemble` rebuilds only `month_of(plan.date)`. |
| Published addresses | `state/published/<YYYY>/<MM>/<DD>.csv` | `ledger.append_published` | Partitioned by **day**, not by month. The caller hands the date and the writer appends to that day alone, so a day is closed once the run's date leaves it. Its read carries `collect.published_window_days`, which the committed config sets to `-1` - the cover is open, and the partition is what a finite value would have to skip. **A finite value must be strictly wider than `collect.seen_window_days`**, and `CollectConfig` refuses one that is not: an undated address whose sight row expires the same week reads as first-seen-today and republishes as new. |
| Day metrics | `state/day-metrics/<YYYY>/<MM>/<DD>.json` | `telemetry.publish.day_metrics.write` | Partitioned by **day**. One record per published day, mirroring the published tree it is derived from, and closed the moment that day is. The site opens only the dates a page names, so nothing walks the tree. |
| Visual prunes | `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` | `ledger.append_visual_prunes` | Partitioned by **day**, and the one collection here whose read will never carry a window - the question is the whole series. It files by day anyway, for the two things the grain buys with no read time at all: two runs collide on a file only when they are the same day, and taking a day back off the record is one `rm` rather than an edit inside a shared file, which its own `merge=union` line cannot express. |
| Scored pairs | `state/content-similarity-judge/scored-pairs/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day**, and the first collection here that nests one directory deeper than `state/` - the whole adaptive merge line hangs off `state/content-similarity-judge/`, so a commit step stages one prefix. A day is closed once its pairs have been folded into the score record, which happens once. The shape, the path and the header ship ahead of the step that appends to them (Guardrail #3). |
| Fitted thresholds | `state/content-similarity-judge/fitted-thresholds/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day** for the reason its sibling is, and unlike that sibling its read does carry a window: the step-change guard takes a median over the newest `step_change_window_rows` written rows, and `assemble` looks back `applied_lookback_days` for a line to apply. Closed once the run's date leaves the day. |
| Council shard outcomes | `state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day**, and it is the one collection here whose day is **not** the day its writer ran: a row files by the digest date it judged, so one night's run appends to every date its plan covered and a day is closed once no later night still names it. Nested one directory deeper than `state/` for the reason the adaptive merge line is - everything the council records about itself hangs off one prefix, so a commit step stages one path. Two directory levels and no more: the day inventory globs one level and two, so a third would be invisible to it and the miss would be silent. The shape, the path and the header ship ahead of the step that appends to them (Guardrail #3). |
| Content-similarity judge metrics | `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv` | none yet | Partitioned by **day**, and it files by the digest date the shard judged rather than the day the run started - the same grain as the council record beside it, so a reader holding one night's units of work against one night's readings opens one day file in each. Nested one directory deeper than `state/` under a prefix named for the judge rather than the venue it ran in: what a reading is ABOUT decides where it is filed, never what executed it, so this store stays put on the day the council stops hosting this judge. Two directory levels and no more, for the reason the council record gives. The shape, the path and the header ship ahead of the step that appends to them (Guardrail #3). |
| Merge-line holdout scores | `state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv` | `stages.score_merge_line_holdout`, run by a person | Partitioned by **day**, filing by the day the line was scored - not by either of the two dates the labelled pair names, which the holdout row carries itself. One row a day, for the reason the fitted line files by day: a read that carries a window over the newest rows, and one `rm` to take a day's reading back off the record. It sits under the judge's prefix and holds no judge's reading at all: the shipped scoring calls no model, so the row carries no call stamp. Closed once the run's date leaves the day. **No job writes it and no job stages it**: a person runs `idhazh score-merge-line-holdout` and commits the row, the way the marked file beside it is committed. |
| Model validation | `state/<run.trial_state_dirname>/validation/<YYYY>/<MM>/<DD>.csv` | `stages.compact.stage_compact`, folding the segment `stages.qualify_decide` or `stages.decide` writes | Partitioned by **day** since 2026-09-18, where it was `state/validation-<date>.csv` at the root of `state/`. The old path was a hardcoded string joined to the repository root, so no config could move it and a trial dispatch wrote production state. Closed once the run's date leaves the day. Two candidates can be dispatched at once, so neither opens the day file: each writes its own segment and the fold settles them against `VALIDATION_KEY`. |

The two collections with nothing committed are not aspirational. Both writers ship and
both are tested; neither has fired, because the oldest committed month is `2026-08` and
both ages are fourteen months.

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

## A store and its mirror may file at different grains

**`state/item-health/` files by day and `frontend/public/telemetry/` files by
month, and neither is a mistake.** They answer different questions, so they take
their grain from different things.

- **A `state/` store's grain follows what a run writes and what a removal takes
 away.** A run writes one day, two runs collide on a file only when they are the
 same day, and taking a day back is one `rm` rather than an edit inside a shared
 shard - which no merge driver can express.
- **A `frontend/public/` mirror's grain follows what a browser fetches.** The
 console prices a window in files: `console.window_presets` ends at 90, and
 `WindowControl.svelte` tells the operator how many files a preset costs. At
 month grain the widest preset fetches five; at day grain it would fetch ninety.

**So somebody has to bridge them, and it is the publisher.**
`public_telemetry.publish` folds a month from that month's day files through
`day_partition.days_by_month`, and `retention.prune_telemetry` folds and deletes
on the same boundary. A month's input is at most 31 files, so the bridge is a
store-bounded read rather than a growing one.

**A day tree's filenames are an index of which days the store holds, and a
bridge reads that index instead of doing calendar arithmetic.**
`source_health._recent_item_health` wants the newest
`source_yield_min_complete_days` dates the ledger actually recorded, which is not
the set a calendar window of the same width names - a gap in the record leaves
the window short, and widening it until it is long enough reads back to the first
run the project made. Every day file's name IS a recorded date, so the newest
`keep` names are the answer and nothing behind them is opened. A month name could
not do this: it says only that the store holds records somewhere inside that
month.

What the day grain costs, stated rather than implied: the unbounded case of
`public_telemetry.publish` opens about thirty times as many file handles for the
same rows, and every listing of the store names one entry a recorded day instead
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
A correction therefore ships as a committed one-shot utility under `backend/utilities/`,
not as an ad-hoc script; `migrate_published_ledger.py` and `migrate_to_day_shards.py` are
the worked examples. A utility whose input layout no longer exists is deleted with
the layout: `migrate_feed_health.py` and `migrate_score_ledger.py` both went that way
in September 2026, and the item-health widener followed them once `widen_ledger_header.py`
could re-file any store from a command line.

### A deletion

Two kinds, and they are not the same operation.

**A whole partition ages out.** `retention.prune_seen`, `prune_feed_health`,
`prune_telemetry` and `prune_scores` unlink a file. The partition is the unit, nothing
is edited, and the freeze rule has no opinion because there is no month left to
rewrite. What bounds each collection is
[the state-tree section](../architecture/publishing/retention.md#what-bounds-the-committed-state-tree)
of the publishing doc.

**Rows go from a partition that stays.** That is a correction and it takes the path
above. Taking one published day back off the site is the worked case, and the eleven
artefacts it owes - three of them month-grain - are
[designed but not built](../architecture/publishing/retention.md#unpublishing-a-day-a-range-or-a-month-the-design-2026-09-06).

### A late arrival

A row whose date falls in a month that is not the run's own. `evals.writer.append`
handles it by construction, because it routes on the row's date rather than on the
run's. Every `ledger.append_*` is handed one date and appends to that month, so its
caller decides: hand it a date in a closed month and it has performed a correction.

A derived partition needs no special case. The search index is rebuilt from the days
on disk, so
[a deleted day needs no cleanup](../architecture/publishing/layout.md#the-shard-is-derived-so-retention-needs-nothing) -
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
| Feed retirements | `state/feed-retirements.csv` | `ledger.append_retirements` | A retirement is permanent for one address. A run that forgot one would start asking a dead server again. |
| Day validations | `state/day-validations.csv` | `stages.validate_days.stage_validate_days`, through `stages.validate_days._record_receipts` | A receipt file, read once a run. No window, so a partition would open every file anyway. |
| Source health view | `frontend/public/source-health.json` | `telemetry.publish.source_health` | One document, rewritten whole each run. Row 20 of the constant-cost-reads plan bounded the read behind it to the recorded dates it needs (#485), so it no longer walks all history to write the same document. |
| Training corpus | `corpus/corpus.jsonl`, `corpus/corpus.meta.json`, `corpus/holdout.txt` | `idhazh.corpus`, rolled by `backend/utilities/data_wrangler.py` | A rolling training window bounded by `finetune.corpus_rows` and by `prune.yml`, not by a calendar. Deliberately given no union merge driver, because the union of two rolls holds evicted rows again. |
| Published days | `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `stages.assemble.stage_assemble` | Partitioned by **day**, and listed here because it is the tree the day grain came from rather than because it is unpartitioned. A day is frozen the moment it is written. The month partitions above are keyed off this tree, and so is `state/published/`. |

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

- [growing-reads.md](growing-reads.md) - the other half of this page: what a growing collection obliges a reader to declare, and why `-1` is an answer.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window) - why a ledger partitions at all, and which reads carry a window.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md#published-shards) - the published projection of item health, one file a month.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md#the-month-search-index) - the month search index, its ceilings, and what an unpublish owes each grain.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the fastest-growing collection, and what would move it to a shorter period.
- [../reference/repository-layout.md](../reference/repository-layout.md) - what each top-level directory holds and who writes it.
- [../reference/data-growth.md](../reference/data-growth.md) - where growing work is heading, what a replacement owes before the old path goes, and the shortcuts that are not answers.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #12 (nothing costs more as the repository grows) and section 11 (schema versioning).
