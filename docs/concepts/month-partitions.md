# Month Partitions

**Last Updated**: 2026-09-06

A **month partition** is one file named `<YYYY-MM>` holding one calendar month of a
collection that grows. The directory is the collection, the stem is the month. A
reader opens the months its window names and skips the rest. A writer appends to the
month its own date names and leaves the rest alone.

Why a collection partitions at all - and why several here deliberately do not - is
[the shard rule](../architecture/contracts/schemas.md#a-ledger-shards-by-month-only-when-its-read-carries-a-window)
in the contracts doc. This page is the other half: what the layout obliges a writer
to do once it exists.

## The freeze rule

**A closed month is rewritten only when a correction targets it. Every other run
touches the current partition alone.**

A partition is **closed** when the writer's own date no longer falls in it. Not
"old" and not "past retention" - closed the moment the calendar moves on, which for
a daily pipeline is the first run of the next month.

The rule binds writes, not reads. A closed partition is still opened: `evals.writer.append`
checks the header of every committed shard before it writes one, and
`ledger.shards_in_window` opens every stem a reader's window names. What bounds reads
is `CLAUDE.md` Rule #12, not this page.

Authority: owner, 2026-09-06.

## The partitioned collections

| Collection | Path pattern | Writer | What makes a partition closed |
| --- | --- | --- | --- |
| Eval ledger | `state/scores/<YYYY-MM>.csv` | `evals.writer.append` | It files each row by the row's own `date`, so a month is closed once no row being written names a date inside it. A run either side of midnight writes two shards and neither is wrong. |
| Item health | `state/item-health/<YYYY-MM>.csv` | `ledger.append_item_health` | It takes one date and appends to that month alone, filtering against `ITEM_HEALTH_KEY` in that one shard. Closed once the run's date leaves the month. |
| Feed health | `state/feed-health/<YYYY-MM>.csv` | `ledger.append_health` | The same one-date append, then it settles that one shard against `FEED_HEALTH_KEY`. The current month is the only file it rewrites. |
| Seen addresses | `state/seen/<YYYY-MM>.csv` | `ledger.append_seen` | The same one-date append. Closed once the run's date leaves the month. |
| Folded item health | `state/telemetry-aggregate/<YYYY-MM>.csv` | `retention.fold_month`, written by `ledger.write_telemetry_aggregate` | Written once, when the item-health month passes `observability.item_health_full_grain_months` (14). Closed the moment it is written - the shard it summarises is gone, so there is nothing left to append. No file is committed yet. |
| Score archive | `state/score-archive/<YYYY-MM>.json` | `evals.archive`, driven by `retention.prune_scores` | Written once, when the scores month passes `observability.scores_full_grain_months` (14), and only after it reconciles against a second reading of the shard. Closed the moment it is written. No file is committed yet. |
| Search index | `frontend/public/assist/index/<YYYY-MM>.json` and `<YYYY-MM>.bin` | `assemble.rebuild_search_index` | It is derived whole from the committed days of that month, so the month is closed once no day inside it changes. `cli.stage_assemble` rebuilds only `month_of(plan.date)`. |

The two collections with nothing committed are not aspirational. Both writers ship and
both are tested; neither has fired, because the oldest committed month is `2026-08` and
both ages are fourteen months.

## Partitioned in layout, not yet frozen

| Collection | Path pattern | Writer | Closed rule |
| --- | --- | --- | --- |
| Telemetry projection | `frontend/public/telemetry/<YYYY-MM>.csv` | `publish_telemetry.publish` | **None today.** It globs `state/item-health/` and rewrites every month it finds, on every run. |

That is [audit finding 11](../reference/data-growth-audit.md), and it is the one place
in the tree where the layout exists and the rule does not. The shape of what it should
write is [in the telemetry doc](../architecture/publishing/telemetry-series.md#published-shards);
what it costs is that an ordinary run pays for every month the project has ever
published, for an answer it already had.

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
[the state-tree section](../architecture/publishing/layout.md#what-bounds-the-committed-state-tree)
of the publishing doc.

**Rows go from a partition that stays.** That is a correction and it takes the path
above. Taking one published day back off the site is the worked case, and the eleven
artefacts it owes - three of them month-grain - are
[designed but not built](../architecture/publishing/layout.md#unpublishing-a-day-a-range-or-a-month-the-design-2026-09-06).

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
| Published addresses | `state/published.csv` | `ledger.append_published` | Published is forever, so the read carries no window and every shard would be opened anyway. |
| Pipeline fingerprints | `state/fingerprints.csv` | `fingerprint.append_new`, from `cli.stage_assemble` | "Has this exact input run before" carries no window. Never pruned. |
| Runtime counters | `state/runtime-counters.csv` | `ledger.append_runtime_counters` | Read one run at a time by an audit with no time bound, and the slowest-growing ledger here. |
| Feed retirements | `state/feed-retirements.csv` | `ledger.append_retirements` | A retirement is permanent for one address. A run that forgot one would start asking a dead server again. |
| Visual prunes | `state/visual-prunes.csv` | `ledger.append_visual_prunes` | One row a run, and the question has no time bound. |
| Model validation | `state/validation-<YYYY-MM-DD>.csv` | `evals.writer.append_validation`, path from `evals.golden` | Dated, not partitioned: one file per validation, which is a one-off rather than a series. |
| Source health view | `frontend/public/source-health.json` | `publish_source_health` | One document, rewritten whole each run. The growing read behind it is [audit finding 12](../reference/data-growth-audit.md). |
| Training corpus | `corpus/corpus.jsonl`, `corpus/corpus.meta.json`, `corpus/holdout.txt` | `idhazh.corpus`, rolled by `backend/utilities/data_wrangler.py` | A rolling training window bounded by `finetune.corpus_rows` and by `prune.yml`, not by a calendar. Deliberately not `merge=union`, because the union of two rolls holds evicted rows again. |
| Published days | `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `cli.stage_assemble` | Partitioned by **day**, not by month - the same rule one level finer, and a day is frozen the moment it is written. The month partitions above are keyed off this tree. |

## See also

- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md#a-ledger-shards-by-month-only-when-its-read-carries-a-window) - why a ledger shards by month at all, and which reads carry a window.
- [../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md#published-shards) - the published projection of item health, one file a month.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md#the-month-search-index) - the month search index, its ceilings, and what an unpublish owes each grain.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the fastest-growing collection, and what would move it to a shorter period.
- [../reference/repository-layout.md](../reference/repository-layout.md) - what each top-level directory holds and who writes it.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #12 (nothing costs more as the repository grows) and section 11 (schema versioning).
