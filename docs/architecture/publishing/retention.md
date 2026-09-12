# Retention

**Last Updated**: 2026-09-10

What may be deleted, when, and what bounds every collection a run appends to.
Unpublishing a day, the state tree's own ceilings, and the score shards that
turn into summaries once they age out.

[layout.md](layout.md) is the other half and owns what a run **writes** - the day
artifact, the item's facts, the month search index and the routes a reader
reaches. This page owns what happens to all of it afterwards. A person arrives
holding one question or the other: how is a day published, or what happens to it
when it is old.

The rule underneath every section here is `CLAUDE.md` Guardrail #12 - nothing costs
more as the repository grows - and the reason retention has a page at all is that
a deletion promise is a promise to a reader
([../../concepts/digest.md](../../concepts/digest.md)).

Retention exists to bound the **published site**, which has a hard ceiling. It does nothing for repository size: deleting a committed file leaves the blob in history forever, and rewriting history is forbidden ([../../../CLAUDE.md](../../../CLAUDE.md) section 8). Anything that must not grow the repository must not be committed at all.

The levers are ordered, and deletion is the last one:

1. **Encode efficiently.** Images are the overwhelming majority of the bytes; the encoding choice alone moves the ceiling by years.
2. **Honour the visual rule.** "Nothing" is the common and correct answer ([../../concepts/digest.md](../../concepts/digest.md)), so most items carry no image at all.
3. **Serve the drawings from somewhere else.** `visuals.asset_base_url`, below. The bytes still exist and every link still works; they stop being ours to fit under the cap.
4. **Then, and only if still needed, prune.**

After the first two, the knob may never need to be switched on. That is the intended outcome, not a fallback.

What the job may do: delete rendered visuals older than a configured age, never on a size trigger, dry-run by default, refusing to act above a maximum-deletions fuse, in its own scheduled workflow that can never take the daily digest down with it. A pruned visual is a **distinct state from a failed render** - "we could not make this" and "we made it and threw it away" are different facts, and one field must not mean both.

What it must never touch: a day's JSON payload, a date directory, the eval ledger, the golden fixtures including retired ones, the injection canaries, or any schema changelog. The ledger and the fixtures are three orders of magnitude smaller than the images and are the only reason a year-over-year quality claim can be interpreted at all.

Two promises to the reader, both non-negotiable: **the window is stated before anything is deleted**, on the archive page and on the missing-day page; and a pruned day lands in the designed missing state, **never a silent redirect to today**. A reader who cannot distinguish a dead link from a live one has lost the ability to trust any link.

The archive states it in its own header from 2026-08-27, and **the sentence names what is actually deleted**. The knob is `retention.image_months` and the job it drives may remove a rendered chart and nothing else, so "Charts older than N months are deleted. Every story and every link stays." is the promise, and "Nothing here is deleted." is what ships today at `image_months: -1`. **The archive is now the only page that states it.** The footer carried a copy on every page from 2026-08-31 and lost it on 2026-09-09: it was read off the newest day, so a page a reader already held was rewritten each time one published, for a sentence about a job that has never deleted anything. The archive's copy stays because that is the page where deletion could matter to the reader looking at it, and because the promise above is that the window is stated **before** anything is deleted - one page stating it is what that asks for, and one page cannot disagree with itself.

## Unpublishing a day, a range or a month: the design (2026-09-06)

**Designed, not built. Nothing below ships yet.** The request is an operator
command that takes a day back off the site - one date, a range of dates, or a
whole month - and the reason it is written down before it is written is that
`retention.prune` cannot be stretched into it. That function selects files by
suffix, deletes rendered charts only, and is explicitly forbidden from touching
a day's payload or its date directory. Unpublishing is the opposite operation
and it needs its own name.

**A published day is eleven things, and a command that misses one leaves a
reader on a broken page.** The daily publish stages exactly this set, so this
set is what an unpublish has to answer for:

| Artefact | Grain | What an unpublish owes it |
| --- | --- | --- |
| `frontend/public/digest/<Y>/<M>/<D>/digest.json` | day | remove |
| `frontend/public/digest/<Y>/<M>/<D>/run.json` | day | remove |
| `frontend/public/digest/<Y>/<M>/<D>/*.svg` | day | remove |
| `frontend/public/assist/index/<Y>-<M>.json` and `.bin` | month | **rebuild**, never edit |
| `frontend/public/telemetry/<Y>-<M>.csv` | month | rewrite without the day's rows |
| `frontend/public/source-health.json` | whole site | rebuild |
| `state/published/<Y>/<M>/<D>.csv` | day | remove |
| `state/scores/<Y>-<M>.csv` | month | rewrite without the day |
| `state/item-health/<Y>-<M>.csv` | month | rewrite without the day |
| `state/runtime-counters.csv` | append-only | rewrite without the day |
| `corpus/corpus.jsonl` | rolling window | rewrite without the day |

The month-grain rows are the trap. Three of them are shards a later run appends
to, so a command that deletes the shard takes the neighbouring days with it, and
a command that leaves it alone publishes telemetry for a day that no longer
exists. The index is worse: it is derived, and `assemble.rebuild_search_index`
already regenerates a whole month from the days present - so the index needs a
rebuild call rather than an edit, and it is the one artefact that repairs itself
correctly for free.

**`state/seen/` and `state/fingerprints.csv` are deliberately absent from that
table.** They record that a URL was *seen*, not that it was published. Removing
a day's rows there would let the next run rediscover every story it just
unpublished, which turns one operator command into a loop.

**The reader-facing half is already designed and must not be re-decided.** This
page's retention rules bind an unpublished day exactly as they bind a pruned
one: the day lands in the designed missing state, never a silent redirect to
today, and the archive's own header says what happened. Today that header reads
"Nothing here is deleted.", which is true and would stop being true - so the
sentence is part of the change, not a follow-up to it.

**What it costs, stated rather than implied.** `prune.yml` force-pushes `main`
on a schedule ([../../../CLAUDE.md](../../../CLAUDE.md) section 8), so once a
squash passes over the range, the unpublished day's bytes are gone from history
as well as from the tree. Before that boundary an unpublish is a normal commit
and is revertible; after it, it is permanent. That is an argument for the
command writing what it removed into its own commit message, and for it never
running on a schedule.

**The command carries no threshold of its own, and may not grow one.** It takes
the dates an operator names and nothing else - no "older than", no "down to N
megabytes", no day count written into the code. Every bound this repository
honours is already a key in `config/` with a contract behind it
([../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #6): `retention.image_months`,
`retention.max_deletes_per_run`, `retention.site_budget_mb`, and the
`observability.*_keep_months` family that bounds the ledgers a day writes into,
all at 14 months today. A number in the source that decides what to delete is
the defect, whatever the number is.

If a scheduled variant is ever wanted, it reuses that shape rather than minting
a figure: months as an integer, `-1` meaning never, defaulting to never, and the
same `dry_run` and `max_deletes_per_run` guards `retention.prune` already
answers to. **It would also have to clear a higher bar than the manual command.**
The manual one removes a day somebody decided was wrong; a scheduled one removes
a day nobody looked at, and the archive's own header would have to say so before
the first run.

**Nothing forces this yet.** Measured 2026-09-05: 16 committed days, and the
site's ceiling is a function of the prerendered dated routes named in the
follow-up above rather than of any day's payload - so deleting days is not the
lever that buys room, and sizing this command against `site_budget_mb` would be
solving the wrong problem with the destructive tool. The command is worth having
for a day published in error - a bad extraction, a source that asked to be
removed - and that is a different need from bounding the site.


## The valve: the drawings can be served from somewhere else (2026-09-06)

`visuals.asset_base_url` is one config key with two effects, and it ships empty, which means this site.

Name an absolute `https://` prefix and `frontend/scripts/copy-visuals.mjs` stops staging the rendered drawings into the bundle, while `ItemVisual.svelte` asks that prefix for them instead. They are one key because two would let the bundle keep a copy of every drawing the page is asking a host for, and the valve would move nothing. The page's own `connect-src` is derived from the same key for the same reason: `'self'` is what makes exfiltration from a planted instruction a browser-level impossibility, so it is also what refuses an off-origin drawing, and an operator who has to edit it by hand gets a site that fetches nothing and says why only in a console no reader opens.

**What it buys, measured 2026-09-06 on an node 24.12.0, over the 17 committed days.** Shut, the built site is 685 files and 111,255,143 bytes. Open, it is 309 files and 106,474,222 bytes. So it removes 376 drawings and **4,780,921 bytes, which is 4.3 percent of the site** - about seven weeks of headroom at the 16,641,956 bytes a published day this page measures below, against a cap the same measurement puts at about 2026-10-22.

**Say the small number first: 4.3 percent is not the answer to the cap.** The prerendered dated routes are 39.5 percent and they are what the cap date is a function of. This valve is worth having because it is one config edit and it costs nothing shut, not because it is the lever that saves the site. Anyone reaching for it as the fix has read the wrong number.

**What it costs open, also measured.** The candidate host caches for five minutes, so a repeat reader refetches a drawing the bundle would have served from cache - real on a slow connection, and the reason the reading experience never waits on it: a drawing arrives after the sentence that repeats its numbers, and the page is complete without it. `connect-src` gains that one origin, computed at build time from our own config; no payload field, no model output and no fetched text can reach it (Guardrail #11), and the path is still matched by `publishedVisual` before either half is joined.

**The carrier does not move, only the URL.** The drawing is fetched as text and inlined, exactly as it is today. An `img` would be the obvious way to point at another host and it is refused: an SVG inside an `img` is a separate document, reads none of the page's custom properties, and comes back with the colours the renderer baked in - black axis type on a near-black card in the dark theme. That was removed on 2026-09-05 and moving bytes is not a reason to bring it back. Cross-origin `fetch` returns text, and text inlined into our document is themed by our stylesheet whichever host sent it.

**Shut is proven, not assumed.** At the default the whole built tree is byte-identical to one built without the valve: 685 files, 111,255,143 bytes, zero differing hashes over two builds at a pinned `BUILD_VERSION`, same hardware and date. The join is written `${__ASSET_BASE_URL__ || base}` so the minifier folds an empty constant away rather than shipping a branch. A release valve that changes the default output is not a valve, it is a change.

**Whoever opens it puts the same `digest/` tree at that prefix first.** Nothing in the pipeline uploads it, and nothing checks that it is there. The day payloads and the month index are staged either way: they are read from this origin, and they are not what the ceiling is about.

## The cleanup says what it did not clear (2026-09-06)

Every run appends one row to `state/visual-prunes.csv` describing the cleanup pass over the rendered visuals - the policy in force, the cutoff it drew, what it found, what it took, what the fuse held back, the oldest day still carrying a picture, and the payload tree before and after. `VisualPruneRow` is the contract.

**`skipped_by_fuse` is the field the row exists for, and it is the one nobody would have added.** `deleted` looks like the answer and cannot be one: `retention.max_deletes_per_run` caps it at 200, so it reads 200 on a run that has just cleared its backlog and 200 on a run that has twenty more passes to go. Only the pair separates them. A run that deleted 200 and skipped none is finished; a run that deleted 200 and skipped 4,000 is not, and nothing else on the row would say so.

**It means the same thing on a dry run as on a live one**: the candidates the fuse would not have let that run reach. It is deliberately not "everything still there afterwards". Every run that ships today is a dry run - `image_months` is -1 and the step passes `--dry-run` - so counting the deletions a dry run declined to make would set `skipped_by_fuse` equal to `candidates_found` on every row this project will ever write, and the field would say nothing at all. That is the same failure `deleted` already has, arrived at from the other side. `dry_run` is the cell that says nothing was deleted, and the arithmetic reads it: on a live run `deleted + skipped_by_fuse` is `candidates_found` exactly, and on a dry run it falls short by what a live run would have taken. The contract refuses a row that breaks either rule.

**The two byte figures are the tree the cleanup walks, not the published site.** Those are two different trees - eighteen times apart when they were last measured together - so the row names the one it read. The site is measured by `idhazh site-weight` against the built bundle, and never here.

**The row lands on every run, including the runs where the policy is off and nothing is a candidate.** A ledger written only when something was deleted has no baseline: its first row would arrive on the day the deletion started working, with nothing to compare it against.

One file rather than month shards, because the question it answers - is the backlog shrinking - carries no time bound, so every shard would be opened anyway ([../contracts/schemas.md](../contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window)). It ships with its header committed for the reason `state/feed-retirements.csv` does: `commit-and-push.sh` runs `git add "$@"` under `set -euo pipefail`, so a path that appears only on the first interesting run would abort the whole commit step before then. The step that writes it commits through a call that stages `state` whole, which already covers it.

**Two things have to move with the deletion when plan 13 switches it on**, and neither is done here. The commit call after the cleanup step stages `state` and `frontend/public/telemetry`, so a deleted picture under `frontend/public/digest/` would be removed from the runner and never from the repository - `git add` records a removal only for a path it is handed. And the paragraph above about a scheduled workflow of its own has to be met or re-decided: the cleanup currently rides in the assemble job's `prune-state` step, which is safe only while it deletes nothing.

## Follow-up: the dated route trees are what decides the cap date (2026-08-27)

**Recorded, not fixed. No row has addressed it.**

The prerendered dated routes are **50,598,258 bytes, 39.5 percent of the published site** - measured 2026-08-27 on an node 24.12.0, over the six committed days and 2,237 items ([../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md#what-is-left-and-where-it-is)). They were 65,197,022 bytes and 44.4 percent before PR #171 narrowed the staged payload.

That is **twelve prerendered documents per published day**: six HTML pages - the all-topics page and one per vertical - and their six `__data.json` twins. Every published day adds twelve more, forever, and nothing else on the site grows per day at anything like that rate. So this is the number the 1 GB cap date is a function of: at 16,641,956 bytes a published day the site reaches the cap on about 2026-10-22, and about 39.5 percent of each of those days is this.

The three levers this page already names - encode efficiently, honour the visual rule, then prune - were all argued about images. **None of them touches an HTML document.** Whatever answers this is a fourth thing, and it has not been designed. What is written down here is the measurement, so the next person starts from a number rather than a feeling.

## What bounds the committed state tree

`state/` is the other tree that grows every run, and it is bounded separately, because what it costs is a checkout rather than a deploy. Re-measured on this checkout 2026-08-31, over the nine days the ledgers then held:

| File | Bytes | Share of `state/` | Bounded by |
| --- | --- | --- | --- |
| `state/seen/<YYYY-MM>.csv` | 2,904,221 | 37.2 percent | `collect.seen_window_days` |
| `state/scores/<YYYY-MM>.csv` | 2,700,019 | 34.6 percent | `observability.scores_full_grain_months` - **archived and deleted from 2026-09-03, and the deletion is in dry run** |
| `state/item-health/<YYYY-MM>.csv` | 1,409,945 | 18.0 percent | `observability.item_health_full_grain_months` - folded, and the fold is in dry run |
| `state/published/<YYYY>/<MM>/<DD>.csv` | 384,448 | 4.9 percent | `collect.published_window_days`, committed at `-1` - so nothing bounds it today, and the day files are what a finite cover would skip |
| everything else | 416,995 | 5.3 percent | small enough not to ask |

Total 7,815,628 bytes over 8 files. **All three of the ledgers this table exists to watch moved inside a day**, and the shares moved further than the bytes did, so the shares are the ones to re-take rather than to quote. Against 2026-08-30: `state/` as a whole fell 17.6 percent, because `state/seen/` shed its address column and fell 43.8 percent from 5,166,315. `state/scores.csv` grew 14.4 percent from 2,359,230 in the same day - so its share went from 24.9 to 34.6 percent while it was the only file nobody had touched, and it is now 204,202 bytes short of being the largest file in the tree.

**The fold covers `state/item-health/`, its browser copy, and `state/feed-health/`.** A month older than `observability.item_health_full_grain_months` is read whole, folded to one row per `(date, stage)` in `state/telemetry-aggregate/<YYYY-MM>.csv`, the full-grain shard is deleted, and `frontend/public/telemetry/<YYYY-MM>.csv` goes with it - in that order, with the aggregate read back before the shard is unlinked, so a fold that cannot be written leaves both files where they were. Fourteen months, and the fourteenth is not spare: `console.max_window_days` is 366, `ledger.shards_in_window` walks 367 inclusive days, and a window ending on the first of a month starts on the last day of another - so a read can open 14 month files. The knob carried 13 until 2026-09-02, because the check behind it compared `13 * 30` against 366 rather than against the shards that window selects. Measured over all 146,097 end dates of one 400-year Gregorian cycle, 13 deletes a shard the console still opens on 3,636 of them, 2.5 percent ([../../concepts/config.md](../../concepts/config.md#why-14-and-not-13)).

**Feed health is deleted rather than folded, and that is a decision.** `state/feed-health/<YYYY-MM>.csv` is one row per feed per run. The quarantine reads 31 days and the console reaches at most 366, so no summary of a month past `observability.feed_health_keep_months` has a reader - and a shape nothing consumes, persisted for ever, is the cost of inventing one. `state/feed-retirements.csv` sits beside that directory and is never a candidate: it carries no time window, and a run that forgot a retired address would start asking a dead one again.

**`state/visual-prunes.csv` is bounded by arithmetic rather than by a rule.** Counted 2026-09-06 from rows a real pass wrote: 105 bytes for the row the shipped policy produces and 125 for a live pass over a 300-picture backlog. Serializing a row is deterministic, so the spread is zero. Five scheduled runs a day is 1,825 rows a year, which is about 187 KB a year against a `state/` tree already measured in megabytes - the smallest thing in it by a wide margin. Nothing deletes from it, and asking it whether the backlog is shrinking across more than one year is the whole reason it is kept.

**The step ships in dry run, and that is what makes it safe to have written at all.** `idhazh prune-state` logs every file a live run would remove and removes none of them. The reason is `.github/workflows/prune.yml`: it squashes and force-pushes `main` on a schedule, so a state file deleted here stops being recoverable from history once that prune passes over it (`CLAUDE.md` section 8) - `git revert` is not a recovery path for a file older than `finetune.prune_keep_days`. Turning the deletion on is a one-line commit somebody takes after a scheduled run has printed the list.

**Measured on this checkout on 2026-09-03, that list is empty and stays empty for a year.** Every committed shard is inside its own window, so a live run today would remove nothing at all. The first file any store loses is `state/seen/2026-08.csv` on **2026-11-30**, through the 90-day sight window; the first files the fourteen-month rules take are on **2027-10-01**, when `2026-08` falls below fourteen months and four files go together - `state/item-health/2026-08.csv`, `frontend/public/telemetry/2026-08.csv`, `state/feed-health/2026-08.csv` and `state/scores/2026-08.csv`. Reading committed files against a fixed calendar is deterministic, so the spread is zero.

**A score month is summarised before it is deleted, and that is the one deletion here with a summary in front of it.** `state/scores/` is the evidence behind every published quality claim, and until 2026-09-07 `evals.writer` refused a repeat measurement by reading those rows - so deleting a month outright would erase the evidence AND make every measurement in that month scoreable again as if it were new. A month past `observability.scores_full_grain_months` therefore becomes `state/score-archive/<YYYY-MM>.json` first: the shard's SHA-256 and row count, one digest per distinct measurement it held, and one cohort per (date, run, row version, model, pipeline, scorer) carrying counts, ten faithfulness deciles, three bands, the boolean signal counts, the cut counts, the premise-digest counts and `{n, sum, sum_squares, min, max}` for every numeric column. The file is written temp-then-rename, read back through its contract, and reconciled field by field against a second reading of the shard; only then is the shard unlinked.

**The writer reads the identities rather than the rows, and that costs 76 bytes a measurement.** A repeat is refused against `state/score-index/<YYYY-MM>.csv` - a ten-character stamp, a comma, the observation digest and a newline - and the rows are not opened at all. Measured on this checkout on 2026-09-07 over 7,710 measurements in two shards: 572.3 KB of index against 6,174.4 KB of rows, 10.8 times smaller, and 820.0 bytes a row against a fixed 76. Both figures are file sizes, so the spread is zero. Nothing is forgotten and no clock is involved: `OBSERVATION_KEY` carries no date, so a January measurement re-taken in February is still the same measurement. A live index is dropped only once the archive that supersedes it is on disk, so the two records of one month never both exist and neither is ever the last one removed.

**An index that fell behind its shard is repaired by deleting it, and nothing detects that state on its own.** Detecting it means reading the rows, which is the cost this file exists to remove, so the pair is kept in step by the two writers instead: `append` writes the rows and their identities in one call, and a month with no index is filled from its rows once. The only way to fall behind is therefore rows appended by something that never maintained the index - which is what a long-lived branch meets when it merges a `main` older than this file, and what happened here: the scheduled pipeline added 74 rows to the September shard while this work was open. Delete that month's index and the next run rebuilds it. Leaving it costs what this writer already declares: it under-reports, so those measurements are taken a second time and `idhazh dedupe-ledgers` settles the repeats against `OBSERVATION_KEY`.

**Measured 2026-09-03** on an (build 26200), CPython 3.14.2, over both committed shards, three reads each:

| Shard | Rows | Cohorts | Source bytes | Archive bytes | Archive as a share |
| --- | --- | --- | --- | --- | --- |
| `2026-08` | 4,110 | 35 | 3,215,734 | 430,009 | 13.4 percent |
| `2026-09` | 1,225 | 10 | 1,050,921 | 127,281 | 12.1 percent |
| both | 5,335 | 45 | 4,266,655 | 557,290 | **13.1 percent** |

Three reads of each shard gave byte-identical archives, so the spread is zero - reading a committed file is deterministic. **What the 13.1 percent means: 87 percent of the bytes go, and a row shrinks from 782 to 858 bytes of CSV to 104 bytes of archive.** Two thirds of what is left is the digest index - 68.8 and 69.3 percent of the two archives - which is the price of keeping the dedupe exact and is what Decision 2 of the plan bought deliberately.

**In years.** The ledger grew 4,266,655 bytes over the 12 published days from 2026-08-22 to 2026-09-02, which is 355,555 bytes a published day and 130 MB a year, with nothing bounding it (444.6 rows a day on average, 10 on the thinnest day and 731 on the fullest, so read the rate as the mean of a wide spread rather than as a constant). With this rule the item-level part stops growing at fourteen months - about 151 MB - and only the archive keeps going, at 46,441 bytes a published day and **17.0 MB a year**. The archive needs 8.9 years to reach the size those fourteen months of shards already are; the raw ledger reached it in fourteen months. That is **7.7 years of headroom for every one the store used to spend**, and the fourteen-month part stops growing at all.

**A thin month summarises LARGER than it held, and that is not a defect.** The digest index scales with rows and the block of moments is a fixed cost per cohort, so a twelve-row month pays the second and barely earns the first. Fourteen-month-old months are the full ones, which is why the direction that matters is the one measured above. `backend/tests/test_retention.py` pins it at a run's worth of rows rather than at a figure, because a figure taken here would go stale the next time a column is added.


**Measured on this checkout, 2026-08-30.** Folding the committed `state/item-health/2026-08.csv` - 4,167 rows over six published days, 1,270,452 bytes - gives 24 aggregate rows and 1,531 bytes: **829.8 times smaller**, 63.8 bytes an aggregate row, 255.2 bytes a published day, 93,136 bytes a year against the shard's 77,285,830. Four rows a day and not five, because `plan` wrote no row that month.

Three things make it the one ledger the fold reaches, and each of them is why the other two need a decision of their own rather than a copy of this one:

- Its rows carry a `stage`, which is what the aggregate is keyed on. A `seen` row is an address and a timestamp; a `scores.csv` row is a faithfulness measurement. Neither folds to `(date, stage)`.
- It shards by month, so a fold is a whole file appearing and a whole file going. `state/scores.csv` is one file, and bounding it means either sharding it - a change across four readers, `payload.ts`, `model-work.ts`, `drift.py` and `label_queue.py` - or rewriting it in place.
- It is a measurement whose totals are worth keeping. `state/seen/` is a lookup, read only through `collect.seen_window_days`, so a shard past that window answers nothing and its honest retention is deletion rather than a fold. **That is what it now gets**, in the same step as the fold: `retention.prune_seen` deletes every seen shard *older* than the oldest month `ledger.shards_in_window(today, seen_window_days)` names - the reader's own helper, so the keep-set cannot drift from what the planner opens. `state/feed-health/` is the same argument reaching the same answer for a different reason: its rows are per-feed-per-run evidence rather than a lookup, and no reader asks a month older than the window for anything. The same day the sight ledger also shed `canonical_url`, which no reader had ever opened: 2,800,881 bytes of 5,705,102 over 25,036 rows, **49.1 percent of the file**, leaving about 356 KB a published day and roughly 32 MB across a full 90-day window.

**Older than the oldest month kept, never merely outside the window.** The two rules read the same on the scheduled path and come apart the moment the prune is handed a date in the past - `--date` takes whatever it is given, and a window drawn around last January puts every shard since outside it, the live one included. Deleting below the window's floor instead makes the retained set a superset of the read set for every date rather than for today's. Measured over the 366 anchor dates from 2026-01-01 at the committed 90-day window: what survives reaches back **90 to 120 days, so the margin over what the planner reads is 0 to 30 days** - zero where the window's oldest day is already the first of a month, thirty where it is the last, because a whole shard is kept either way.

**What this does not do, stated plainly: it does not bound the `/console/` document.** That page was linear in items at a measured 50.45 gzipped bytes an item and crossed its 301,580-byte ceiling on published day 16, because the compression scatter inlined every row `state/scores.csv` had ever held. Both halves of that are closed - the plot moved to a windowed seed over the telemetry projection on 2026-08-29, and the scatter itself became a per-day count of three bins on 2026-08-30 - so the page no longer grows a mark an item. The fold was never an answer to it either way: the two problems share a file and share nothing else.

The aggregate is kept forever by default. `observability.item_health_aggregate_keep_months` is null, and the contract refuses a value at or below `item_health_full_grain_months` - so a month is never deleted before it has been folded. `observability.score_archive_keep_months` stands in the same relation to `scores_full_grain_months`, and is null for the same reason.

**What is deliberately lost when a score month is archived**, and what survives, because a policy that only lists what it keeps is not a policy:

| Lost | Survives |
| --- | --- |
| Looking one item up by its address or its id | Every total and rate the cohorts carry |
| Drawing that month into the human label queue | The distribution, as ten faithfulness deciles and three bands |
| Re-banding those rows under new thresholds | Ranges and spread, from `{n, sum, sum_squares, min, max}` per column |
| An exact percentile | Boolean signal counts, cut counts and premise-digest counts |
| Correlating two columns against each other | Exact dedupe, through the sorted observation digests |
| Any slice the cohort key does not name | The shard's own SHA-256 and row count |

Authority: Andre, under Guardrail #10 - a claim about an archived month has to be one the archive can still support.

## `state/scores/` shards by month, and that bounds nothing on its own (2026-08-31)

**The eval ledger moved from `state/scores.csv` to `state/scores/<YYYY-MM>.csv` on
2026-08-31.** The migration is a split and nothing else: 3,509 rows, one month,
2,700,019 bytes before and after, every cell compared by name across both
revisions. Say what it did not do first, because the section this replaces was
right about it: **sharding is not a bound.** Nothing is deleted, nothing is
folded, and the tree grows at the same rate it grew yesterday.

What it buys is that the two things which could bound it are now possible. A
retention rule can take a whole month the way `state/item-health/` already does,
instead of rewriting a file that `merge=union` will not let anyone rewrite. And a
reader that wants a window can skip whole files - `payload.ts` has a shared
`readShards` helper now, which `state/item-health/` was already using and this
ledger could not.

**The reader half landed on 2026-09-09.** `readShards(dir, months)` opens the
newest `months` shards and nothing older. The default is `shardMonths(90)`, which
is five - a month is at least 28 days, so the rule rounds up, and 90 is where
`console.window_presets` ends. `evalRows`, `itemHealthRows`, `feedResults` and
`loadSpanRollup` are all thin wrappers over it, so all four inherit the cover.
Pass `-1` to read every month and say beside the call why
([growing-reads.md](../../concepts/growing-reads.md)). The listing still names
every shard - one directory entry a month - because the newest stem cannot be
derived from today's date for a ledger whose last run was two months ago.

It also shrinks what one commit touches. Every run appended to a single file, so
git stored a new blob of the whole ledger several times a day; it now stores a
new blob of the current month.

**The cost was named in advance and it was accurate.** The change touched
`evals/writer.py`, `cli.py`, the `drift.yml` inline program, four utilities, the
canary builder, `payload.ts`, `commit-and-push.sh`'s staged list,
`REFRESH_PATHS`, the closed-world path map and the merge-driver test in
`test_workflows.py`, nine test modules, a fixture tree, and a migration of the
committed file. It is a Level 4 change taken on an owner instruction, against a
file that is not yet costing anything measurable.

One promise had to be defended explicitly. `writer.append` dedupes against
`OBSERVATION_KEY` across **every** shard, not the one being written, because an
observation is the same measurement whichever month it is re-taken in - a dedupe
scoped to the current month would let January's row come back in February and
turn a count over the ledger into a count of times the pipeline looked. The
header check moved ahead of the dedupe for the same reason: a corrupt shard is
corrupt whatever the call had to say, and checking after the dedupe let a stale
header survive an append that returned zero.

### What the ledger is made of, and the three narrowings not taken

Measured 2026-08-31 on the committed file: 3,544 rows over nine days and 30 runs,
35 columns, 2,728,991 bytes; 770 bytes a row, 303,221 bytes a published day,
about 111 MB a year. There is no cap on `state/` the way there is a 1 GB cap on
the published site, so the runway is not a date - the cost is a checkout, paid by
every `plan`, `work`, `assemble` and CI job, several times a day.

What each reader needs, and how far back:

| Reader | What it needs | How far back |
| --- | --- | --- |
| `payload.ts` -> `model-work.ts` | per-**day** figures only | `console.max_window_days`, 366 |
| `backend/idhazh/drift.py` | per-item, per-domain | `recent_days` plus `baseline_days`, 35 days on the scheduled path |
| `backend/utilities/label_queue.py` | per-item, at the live `scorer_version` and `pipeline_fingerprint` | `evaluation.label_min_run_days`, 10 run-days |
| `backend/idhazh/evals/writer.py` | one row per `OBSERVATION_KEY`, to refuse a repeat | for ever |

**Twenty-four percent of every cell byte is derivable from `run_id`.** Four
columns are constant within a run - measured over all 30 committed runs, **none
varies**:

| Column | Distinct values | Runs that vary | Bytes | Share |
| --- | --- | --- | --- | --- |
| `scorer_version` | 5 | 0 of 30 | 288,448 | 10.6 percent |
| `pipeline_fingerprint` | 7 | 0 of 30 | 230,360 | 8.5 percent |
| `model_id` | 2 | 0 of 30 | 59,328 | 2.2 percent |
| `version` | 6 | 0 of 30 | 46,286 | 1.7 percent |

`scorer_version` alone is a 99-character string repeated 3,544 times to say one
of five things, and `RunRecord` **already carries** `scorer_version` and
`pipeline_fingerprints`, so two of the four are duplicated onto a committed
manifest today. `date` is a strict prefix of `run_id` on 3,544 of 3,544 rows, for
another 38,984 bytes. Together: **663,406 bytes, 24.3 percent, 111 MB a year to
84 MB.**

**This corrects the previous version of this section**, which said the one column
that looks like waste - `scorer_version` - could not move because `label_queue`
selects the live instrument by it. It can move: a per-run side table answers that
selection exactly, because the value never varies inside a run. What it costs is
real and is why it was not taken here: **a row stops being self-describing.**
Reading one today tells you which scorer produced it without opening anything
else, and that is a property somebody chose. 26 MB a year is not obviously worth
trading it for.

Two smaller narrowings, also measured and also not taken:

- **Ten columns no committed-file reader opens** - `attempt`, `hhem_full`,
 `hhem_delta`, `compression`, `extraction_suspect`, `determinism_violation`,
 `scored_at`, `evidential_density`, `speculative_density`, `self_repetition` -
 are 379,095 bytes, 13.9 percent. **"No reader" is not "delete" here.** This
 ledger is evidence, unlike `state/seen/`, which is a lookup: Guardrail #10 turns on
 being able to re-read a measurement to defend a design, and four of these got
 written descriptions on 2026-08-30. Deleting evidence a day after documenting
 it is churn.
- **`source_url` and `title`** are 643,696 bytes, 23.6 percent - the largest pair
 in the file - and both are read. `drift` names a domain from the first;
 `evals/evidence.py` and `label_queue` both open the second. This is where the
 `PublishedRow` and `SeenRow` narrowings do not repeat: those two dropped a
 column nobody opened, and this ledger has none.

**What would change the answer.** The console learning to read a daily aggregate,
which makes a short full-grain window enough; `state/` acquiring a measured
ceiling the way the published site has one; or the file passing a size where a
checkout is measurably slower. Sharding is what makes the first two cheap when
somebody wants them.

## See also

- [layout.md](layout.md) - what a run writes, and the addresses a reader reaches.
- [../../concepts/config.md](../../concepts/config.md) - the retention knobs and their defaults.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - Guardrail #12's escape hatch, and what a growing read has to declare.
- [../../reference/measurements-site.md](../../reference/measurements-site.md) - the site's weight, its growth rate and the alarm point.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings and what to do when one fires.
- [../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the runner is the architecture) and Guardrail #12 (nothing costs more as the repository grows).
