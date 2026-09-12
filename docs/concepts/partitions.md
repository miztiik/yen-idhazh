# Partitions

**Last Updated**: 2026-09-11

A **partition** is one file holding one period of a collection that grows. The
directory is the collection and the name says the period - `<YYYY-MM>` for a month,
`<YYYY>/<MM>/<DD>` for a day. A reader opens the periods its window names and skips
the rest. A writer appends to the period its own date names and leaves the rest
alone.

**A month is the usual unit here and it is not the only one.** Four collections
partition by **day** instead, and the first two below are the same series - the
state ledger is derived from the published tree:

| Collection | Writer |
| --- | --- |
| `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `cli.stage_assemble` |
| `state/published/<YYYY>/<MM>/<DD>.csv` | `ledger.append_published` |
| `state/day-metrics/<YYYY>/<MM>/<DD>.json` | `publish_day_metrics.write` |
| `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` | `ledger.append_visual_prunes` |

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
check while `ledger.append_seen` names its own file `2025-01`. That is two files
claiming one month, and a fold would summarise over one of them. CPython's date parser
happens to refuse that stem today, but through how it compiles its digit class rather
than through anything this rule asked for, and a detail is not a rule - so the check is
written out, and `backend/tests/test_retention.py::test_the_month_readers_all_agree_on_what_a_month_is`
holds all four readers to it.

Authority: Guardrail #5 - a structural fix rather than a third copy of the rule. Found while
[re-measuring the state prunes](../architecture/publishing/layout.md#the-state-prunes-were-already-constant-cost-and-the-premise-that-said-otherwise-was-wrong-2026-09-08),
2026-09-08.

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

## The freeze rule

**A closed month is rewritten only when a correction targets it. Every other run
touches the current partition alone.**

A partition is **closed** when the writer's own date no longer falls in it. Not
"old" and not "past retention" - closed the moment the calendar moves on, which for
a daily pipeline is the first run of the next month.

The rule binds writes, not reads. A closed partition is still opened: `evals.writer.append`
checks the header of every committed shard before it writes one, and
`ledger.shards_in_window` opens every stem a reader's window names. What bounds reads is
[growing-reads.md](growing-reads.md) - the cover a read declares, and `CLAUDE.md` Guardrail #12
behind it.

Authority: owner, 2026-09-06.

## The partitioned collections

| Collection | Path pattern | Writer | What makes a partition closed |
| --- | --- | --- | --- |
| Eval ledger | `state/scores/<YYYY-MM>.csv` | `evals.writer.append` | It files each row by the row's own `date`, so a month is closed once no row being written names a date inside it. A run either side of midnight writes two shards and neither is wrong. |
| Item health | `state/item-health/<YYYY-MM>.csv` | `ledger.append_item_health` | It takes one date and appends to that month alone, filtering against `ITEM_HEALTH_KEY` in that one shard. Closed once the run's date leaves the month. |
| Feed health | `state/feed-health/<YYYY-MM>.csv` | `ledger.append_health` | The same one-date append, then it settles that one shard against `FEED_HEALTH_KEY`. The current month is the only file it rewrites. |
| Seen addresses | `state/seen/<YYYY-MM>.csv` | `ledger.append_seen` | The same one-date append. Closed once the run's date leaves the month. |
| Telemetry projection | `frontend/public/telemetry/<YYYY-MM>.csv` | `publish_telemetry.publish` | It writes only the months a caller names as changed, and rewrites a named month only when its projected bytes differ from the committed shard - so a closed month is neither read nor rewritten once nothing targets it. Frozen since row 19 of the constant-cost-reads plan (#484). |
| Folded item health | `state/telemetry-aggregate/<YYYY-MM>.csv` | `retention.fold_month`, written by `ledger.write_telemetry_aggregate` | Written once, when the item-health month passes `observability.item_health_full_grain_months` (14). Closed the moment it is written - the shard it summarises is gone, so there is nothing left to append. No file is committed yet. |
| Score archive | `state/score-archive/<YYYY-MM>.json` | `evals.archive`, driven by `retention.prune_scores` | Written once, when the scores month passes `observability.scores_full_grain_months` (14), and only after it reconciles against a second reading of the shard. Closed the moment it is written. No file is committed yet. |
| Search index | `frontend/public/assist/index/<YYYY-MM>.json` and `<YYYY-MM>.bin` | `assemble.rebuild_search_index` | It is derived whole from the committed days of that month, so the month is closed once no day inside it changes. `cli.stage_assemble` rebuilds only `month_of(plan.date)`. |
| Published addresses | `state/published/<YYYY>/<MM>/<DD>.csv` | `ledger.append_published` | Partitioned by **day**, not by month. The caller hands the date and the writer appends to that day alone, so a day is closed once the run's date leaves it. Its read carries `collect.published_window_days`, which the committed config sets to `-1` - the cover is open, and the partition is what a finite value would have to skip. **A finite value must be strictly wider than `collect.seen_window_days`**, and `CollectConfig` refuses one that is not: an undated address whose sight row expires the same week reads as first-seen-today and republishes as new. |
| Day metrics | `state/day-metrics/<YYYY>/<MM>/<DD>.json` | `publish_day_metrics.write` | Partitioned by **day**. One record per published day, mirroring the published tree it is derived from, and closed the moment that day is. The site opens only the dates a page names, so nothing walks the tree. |
| Visual prunes | `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` | `ledger.append_visual_prunes` | Partitioned by **day**, and the one collection here whose read will never carry a window - the question is the whole series. It files by day anyway, for the two things the grain buys with no read time at all: two runs collide on a file only when they are the same day, and taking a day back off the record is one `rm` rather than an edit inside a shared file, which `merge=union` cannot express. |

The two collections with nothing committed are not aspirational. Both writers ship and
both are tested; neither has fired, because the oldest committed month is `2026-08` and
both ages are fourteen months.

## The last unfrozen partition is frozen now

The telemetry projection `frontend/public/telemetry/<YYYY-MM>.csv` was the one
place in the tree where the layout existed and the rule did not:
`publish_telemetry.publish` globbed `state/item-health/` and rewrote every month
it found, on every run, for an answer it already had. That was
[audit finding 11](../reference/data-growth-audit.md), and row 19 of the
[constant-cost-reads plan](../../TODO/20260906-constant-cost-reads-plan.md)
closed it in #484: the writer now takes the row above, writing only the months a
caller names as changed and rewriting a named month only when its bytes differ.
What it writes, and how the two freezes compose, is
[in the telemetry doc](../architecture/publishing/telemetry-series.md#published-shards).

## The four cases an append-only pattern gets wrong

A pattern that only handles appends is a trap, so each of these has an answer here.

### A correction to a closed month

Rewrite that month, and only that month. This is the one thing the freeze rule
permits, and it is the whole reason the rule says "only when a correction targets it"
rather than "never".

Two constraints make a correction a deliberate act rather than an ordinary write.
`.gitattributes` sets `merge=union` on `state/**/*.csv`, so a commit that removes rows
from a shard, rebased onto a tip that added some, resolves by keeping both sides - the
removal silently does not happen. And a shard's header is checked against the contract
before any append, so a rewrite that changes the shape has to move every month at once.
A correction therefore ships as a committed one-shot utility under `backend/utilities/`,
not as an ad-hoc script; `migrate_published_ledger.py` and `migrate_score_ledger.py` are
the worked examples.

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
| Pipeline fingerprints | `state/fingerprints.csv` | `fingerprint.append_new`, from `cli.stage_assemble` | "Has this exact input run before" carries no window. Never pruned. |
| Runtime counters | `state/runtime-counters.csv` | `ledger.append_runtime_counters` | Read one run at a time by an audit with no time bound, and the slowest-growing ledger here. |
| Feed retirements | `state/feed-retirements.csv` | `ledger.append_retirements` | A retirement is permanent for one address. A run that forgot one would start asking a dead server again. |
| Day validations | `state/day-validations.csv` | `cli.stage_validate_days`, through `cli._record_receipts` | A receipt file, read once a run. No window, so a partition would open every file anyway. |
| Model validation | `state/validation-<YYYY-MM-DD>.csv` | `evals.writer.append_validation`, path from `evals.golden` | Dated, not partitioned: one file per validation, which is a one-off rather than a series. |
| Source health view | `frontend/public/source-health.json` | `publish_source_health` | One document, rewritten whole each run. The read behind it was [audit finding 12](../reference/data-growth-audit.md); row 20 of the constant-cost-reads plan bounded it to the recorded dates it needs (#485), so it no longer walks all history to write the same document. |
| Training corpus | `corpus/corpus.jsonl`, `corpus/corpus.meta.json`, `corpus/holdout.txt` | `idhazh.corpus`, rolled by `backend/utilities/data_wrangler.py` | A rolling training window bounded by `finetune.corpus_rows` and by `prune.yml`, not by a calendar. Deliberately not `merge=union`, because the union of two rolls holds evicted rows again. |
| Published days | `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `cli.stage_assemble` | Partitioned by **day**, and listed here because it is the tree the day grain came from rather than because it is unpartitioned. A day is frozen the moment it is written. The month partitions above are keyed off this tree, and so is `state/published/`. |

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
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #12 (nothing costs more as the repository grows) and section 11 (schema versioning).
