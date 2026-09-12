# Adaptive Pruning

**Last Updated**: 2026-09-13

One question, asked of every file this project writes:

> **When this artefact is old, what does a reader lose if it goes?**

The answer picks one of four policies. **Adaptive** is the load-bearing word:
every store answers that question for itself and carries its own age, because an
age that is right for one store is wrong for the next. This page says what the
four policies are, which one governs a given artefact, and what the register does
not name.

[growing-reads.md](growing-reads.md) is the companion, not a duplicate. It asks
what a **read** may open, and its answer is a **cover** - the bound a reader
declares out loud, such as "the last 90 days" or "only the files this run wrote".
This page asks what a **write** is allowed to keep. A cover makes a shard cheap
to read; a policy is what stops the shards piling up behind it.

**The module is `backend/idhazh/retention.py` and the concept is adaptive
pruning.** The module is what deletes; this is the rule it obeys.

## The five properties

Every deletion here obeys all five. Each has an address, because a property with
no address is advice.

**1. Age decides, never size.** A size trigger deletes most on the day the reader
has most to read. The byte instruments print and fail rather than delete:
`retention.site_budget_mb` is the alarm, `retention.pages_hard_cap_mb` is the cap
past which the step stops, and neither removes a file. The one store bounded by a
count instead of an age is `corpus/`, and it is the exception that shows the
reason - nothing renders it, links to it or serves it, so there is no day on
which evicting from it costs a reader anything.

**2. Nothing goes while a live read can still select it.** A config that would
delete a month the console can still ask for fails validation rather than
deleting quietly. `ObservabilityConfig.refuse_windows_shorter_than` is the check.
It counts the month files a console read opens, and compares every window against
that count rather than against the window's own length - because a month is not
thirty days. The browser's copy of a ledger is held to the same rule: it and the
ledger it copies must age together.

**3. What replaces it is written and read back before the original goes.** The
score fold writes `state/score-archive/<YYYY-MM>.json`, reads it back through its
contract, and reconciles it field by field against a second reading of the shard
before anything is unlinked. A fold that wrote a summary nobody re-read would
trade an unreadable month for an unread one.

**4. A fuse bounds one run.** `retention.max_deletes_per_run` is 200, against the
491 rendered visuals committed on 2026-09-13 - so a policy that selected every
picture on disk would still take three runs to finish. An off-by-one in a date
parse cannot eat the archive in one pass. It can only leave a backlog the next
run continues, which is the fuse working rather than failing.

**In steady state the fuse is nowhere near the bound, and the one case that
would reach it is a window somebody narrows.** 25.5 visuals arrive a published
day, so 25.5 age out a day once a window reaches back that far, against five
runs a day at 200 files each - 1,000 deletes a day of capacity, and the heaviest
single day on record is 43. Narrowing a window is the move that drops a whole
span in at once rather than a day at a time: taking `retention.image_months`
from 13 to 6 would open about 5,400 candidates, which is six days of draining.

**5. Every pass leaves a row, including the pass that deleted nothing.** The
visual prune appends to `state/visual-prunes/` on every run, and the row carries
`skipped_by_fuse` beside `deleted`. The fuse caps `deleted`, so on its own that
number reads the same on a run that cleared its backlog and on a runaway one.
Only the pair says which, and the day the policy starts working is then visible
in a committed file rather than in a job log nobody kept.

## The four policies

| Policy | The artefact | What goes, what stays | What the reader loses |
| --- | --- | --- | --- |
| **Fold** | a ledger | the full-grain shard goes, a durable aggregate stays | the per-item detail, never the daily total |
| **Delete** | a lookup | the shard goes, nothing replaces it | nothing - outside its window it answered no question |
| **Delete** | an asset | the file goes, the story that named it stays | the picture, never the item |
| **Keep** | a record | nothing goes, at any age | nothing |

**A ledger** is append-only within its window, folds to a durable aggregate, and
is never edited in place at full grain. That last clause is the narrow one:
a ledger IS corrected, by a later row rather than by a rewrite
([partitions.md](partitions.md#the-freeze-rule)).

**Three verbs across four policies, because a lookup and an asset delete for
opposite reasons.** A lookup goes because nothing reads it any more. An asset
goes because every reader downloads it and the item survives without it.

## Which policy governs a given artefact

Three questions, in order. They answer for a store nobody has created yet, which
is the only kind of rule worth writing here.

**1. Does a run append to it?** If a run rewrites the whole file instead, there is
no retention question and there never will be: a file rewritten whole cannot
grow. Source a person writes is not this either - it grows at review speed.

**2. What does a reader lose when the oldest entry goes?** This is the question,
and the three answers are the three policies that act:

- A number somebody will cite -> **fold**. Keep the total, drop the grain.
- Nothing, because no read reaches past a window -> **delete**, and the age is
  the read's own cover rather than a number chosen here.
- The fact that something happened -> **keep**. Age is not a reason.

**3. Is it an asset a reader downloads?** Then it deletes on bytes alone,
whatever answer 2 gave, as long as the item that named it survives. This is the
only place where the cost rather than the reader picks the policy, and the Pages
ceiling is why (`CLAUDE.md` Guardrail #2).

**A published copy is not a fifth policy.** It takes the same answer its source
took, and a knob of its own. Where the source is a ledger we hold, the two
numbers must match and the config refuses them if they do not. Both ways round
are broken: a published month whose source was folded away is a rate nobody can
check against the rows behind it, and a source month with no published copy is a
window the console draws as a gap.

Reach for a clock last. Which cover is honest, and why a clock is usually the
wrong one, is
[growing-reads.md](growing-reads.md#deciding-it-for-a-collection-this-page-does-not-list).

## The register, 2026-09-12

**An artefact missing from this table has no policy rather than a default one.**
Answer the three questions above where the store is created, and add its row in
the same commit.

No test asserts this table, and that is a decision with a reason under
[Design rationale](#design-rationale). What closes the gap instead is one
command, so the difference between what it prints and what this table names is a
line to run rather than an act of memory:

```powershell
git ls-tree --name-only HEAD state/ corpus/ frontend/public/
```

That command prints what is committed today. Five rows below have no committed
instance yet, because the run that writes each has not written one. **A row with
no file is not a mistake; a file with no row is.**

**Every full-grain window in the `state/` table below is 14 months today, and
every aggregate age is null, meaning never.** The knob is what governs rather
than that sentence, and
[config.md](config.md#every-store-names-its-own-cleanup-age) is where each number
is set and argued. It is stated once here so that reading a row does not cost a
second page. **`retention.image_months` is 13 and is not one of them** - 14 there
is the count of month shards a console read opens, and no read opens a visual
([why 13 and not 14](#why-13-and-why-the-bytes-did-not-choose-it)).

### `state/` - what one run leaves for the next

| Artefact | Policy | Age | Why that policy |
| --- | --- | --- | --- |
| `state/seen/` | Delete (lookup) | `collect.seen_window_days` | `ledger.load_seen` opens the shards that window names and nothing else, so an older shard answers no question anybody asks |
| `state/feed-health/` | Delete (lookup) | `observability.feed_health_keep_months` | a per-feed-per-run record, not a total worth keeping. The quarantine reads 31 days and the console reaches 367 inclusive days, a year and a day |
| `state/traces/` | Delete (lookup) | `observability.trace_window_days` | a trace is what an operator opens to see one recent run step by step. No committed instance yet |
| `state/item-health/` | **Fold** -> `state/telemetry-aggregate/` | `observability.item_health_full_grain_months` | every console rate divides by this census, so the daily totals have to outlive the per-item grain |
| `state/scores/` | **Fold** -> `state/score-archive/` | `observability.scores_full_grain_months` | it is the evidence behind every published quality claim, so the summary is written, read back and reconciled first |
| `state/telemetry-aggregate/` | Keep | `observability.item_health_aggregate_keep_months`, null | the fold costs a measured 63.8 bytes a row over four stages - about 93 KB a year against the shard's 77 MB - and deleting it would make a year-over-year comparison unanswerable. No committed instance yet |
| `state/score-archive/` | Keep | `observability.score_archive_keep_months`, null | the same argument. No committed instance yet |
| `state/score-index/` | Keep | none, deliberately | an identity set carrying no date. It is what stops an old measurement being scored again as if it were new |
| `state/published/` | Keep | none - the **read** carries the cover, `collect.published_window_days` | forgetting an address republishes it as new |
| `state/day-metrics/` | Keep | none of its own | about 13 KB a day, measured 2026-09-12 over 23 committed days, and the only place a band count or an extraction census survives the fold above |
| `state/span-rollup/` | Keep | none of its own | the committed record a trace is not. No committed instance yet |
| `state/visual-prunes/` | Keep | none | it is property 5 - the record of what the prune did, including the runs it did nothing |
| `state/runtime-counters.csv` | Keep | none of its own | one appended file. The month boundary is first drawn in the published copy |
| `state/feed-retirements.csv` | Keep | never | it carries no time window at all. A run that forgot a retired address would start asking a dead one again |
| `state/fingerprints.csv` | Keep | none | one stamp a run |
| `state/day-validations.csv` | Keep | none | one receipt a day, from `idhazh validate-days` |
| `state/labels.csv` | **Keep, always** | never | the only ground truth here, and the one file in `state/` a person wrote rather than a machine. No committed instance yet |
| `state/validation-2026-08-22.csv` | **No policy, and no writer** | none | see below |

### `corpus/` - the rolling training window

| Artefact | Policy | Age | Why that policy |
| --- | --- | --- | --- |
| `corpus/corpus.jsonl` | Delete (eviction) | `finetune.corpus_rows`, a row count | the one store bounded by a count rather than an age, because no reader can reach it |
| `corpus/corpus.meta.json` | Keep | none | the census of the window above |
| `corpus/holdout.txt` | Keep | none | the ids held out of training |

The bytes those rows add to **git history** are a separate problem with a separate
answer, and `CLAUDE.md` section 8 owns it: history is append-only, so bounding the
repository means rewriting it, which is the one force-push exception in this
project and what it costs is stated there.

### `frontend/public/` - what a reader downloads

| Artefact | Policy | Age | Why that policy |
| --- | --- | --- | --- |
| `frontend/public/digest/<Y>/<M>/<D>/digest.json`, `run.json` | **Keep, always** | never | the record that a day happened. The archive is the product, so age is not a reason to remove any of it |
| `frontend/public/digest/<Y>/<M>/<D>/*.svg` | Delete (asset) | `retention.image_months`, **13** | the item survives without its picture, which is what makes a visual the one published thing safe to remove. Not because it is the bigger half - it is not: 491 visuals weighing 6,244,624 bytes against 24,543,254 bytes of day payload in the same tree on 2026-09-13 |
| `frontend/public/telemetry/` | Delete (projection) | `observability.public_telemetry_keep_months` | the browser's copy of `state/item-health/`, refused at any value but its source's |
| `frontend/public/scores/` | Delete (projection) | `observability.public_scores_keep_months` | the browser's copy of `state/scores/`, refused at any value but its source's |
| `frontend/public/feed-health/` | Delete (projection) | `observability.public_feed_health_keep_months` | the browser's copy of `state/feed-health/`, refused at any value but its source's |
| `frontend/public/run-days/` | Delete | `observability.public_run_days_keep_months` | a reduction of the day payloads to counts. It has no state ledger to be paired with |
| `frontend/public/day-metrics/` | Delete | `observability.public_day_metrics_keep_months` | bounds the published copy without claiming to bound the ledger, which has no age of its own |
| `frontend/public/machine/` | Delete | `observability.public_machine_keep_months` | the source is one appended CSV, so the copy is where a month boundary first exists |
| `frontend/public/span-rollup/` | Delete | `observability.public_span_rollup_keep_months` | the record starts 2026-09-06, so for its first year this deletes nothing |
| `frontend/public/console/band.json` | Keep | none needed | one file, rewritten whole each run. Question 1 stops here |
| `frontend/public/source-health.json` | Keep | none needed | one file, rewritten whole each run |
| `frontend/public/assist/index/` | **No policy** | none | see below |

## What the register found on its first pass

Two entries have no policy. They are rows rather than gaps because that is the
whole value of writing the register down.

**`frontend/public/assist/index/` accumulates and nothing bounds it.**
`assist.search_months` looks like an age and is not - it is a read cover, the
number of month shards a search fetches, and a shard outside it is downloaded by
nobody and deleted by nobody. Measured 2026-09-12 on this checkout: 5,090,914
bytes over the two committed months, so about 2.5 MB a month, or roughly 30 MB a
year against the 1 GB Pages ceiling. That is not urgent and it is not nothing.
The three questions answer it - a run appends, and no read reaches past
`assist.search_months` widened by `assist.search_min_days` - so its honest policy
is delete, with an age of its own. Nobody has set one, so the row reads none.

**`state/validation-2026-08-22.csv` has no writer.** Four rows under a header,
recording one day's model qualification, at the root of `state/` where nothing
else sits loose. No code names it and no reader opens it. It is not deleted here
because deleting a record is a decision for whoever owns model qualification, not
a tidy-up.

## Design rationale

### Why 13, and why the bytes did not choose it

`retention.image_months` was `-1` until 2026-09-13 - no age window at all - so
this is the first age this project has put on a published asset rather than a
tightening of one. `retention.dry_run` stays `true`, so the window names days
and removes none of them; the deletion is a separate commit, and it lands that
way round so that the first evidence of what the window selects arrives before
the deletion rather than after it.

**The window is an archive policy and not a cap defence, and the measurement is
what says so.** Rendered visuals arrive at 324,580 bytes a published day, which
is 10.7 percent of what the whole site adds in a day. At that rate 390 days of
them stand at 120.7 MiB for ever - 11.8 percent of the 1 GiB ceiling - and with
no window at all they would take 3,308 published days, about nine years, to fill
the cap on their own. The reading, its spread and the two-hop argument that lets
a payload-tree rate be spent against a built-site cap are
[measurements-site.md](../reference/measurements-site.md#what-a-published-day-adds-in-rendered-visuals-2026-09-13).

**Between 12, 13 and 14 months the byte budget does not choose.** They stand
111.4, 120.7 and 130.0 MiB apart-to-end, so the whole range is 18.6 MiB, 1.8
percent of the cap. One spread on the daily rate carried across the same window
is 47.6 MiB, which is 5.1 months of window - the instrument is five times too
blunt to resolve a two-month difference, so no number here can separate them.
That leaves the owner's 13 (O8 and C20 of
[../../TODO/20260902-visual-planner-pseudo-plan.md](../../TODO/20260902-visual-planner-pseudo-plan.md)),
now derived rather than asserted. Carmack, 2026-09-13.

**14 was available and was refused, because its reason does not travel.**
Fourteen is the count of month shards a console read can open
([config.md](config.md#why-14-and-not-13)), and no console read opens a visual -
so copying it here would be the number with its reason left behind. There is no
read cover on a visual at all: every published day is kept for ever and a reader
can open any of them, which is why this row's licence comes from the other
clause - the item survives without its picture.

**A month is 30 days to this knob.** `retention.cutoff` is
`today - timedelta(days=months * 30)`, so 13 is 390 days and not thirteen
calendar months - 5.7 days short. The error runs in the safe direction: the
window holds slightly less than the table above would suggest, never more. It is
recorded rather than fixed, because changing what a month means moves what every
window selects and that is a decision of its own.

**Re-take the rate when it would change something, not on a date.** The read is
one bounded pass over the dated directories and costs seconds, so the trigger is
a threshold: visuals a day or bytes a visual moving more than one spread, or the
first visual that is not an SVG - 12,716 bytes a visual is an all-SVG figure, and
a raster family would move every row of the arithmetic above at once.

**The module keeps the name `retention.py` and the concept is documented as
adaptive pruning.** "Intelligent" claims a property that code reading a date does
not have, and "compaction" is borrowed from log-structured storage where it means
something else (O9, `CLAUDE.md` section 0b).

**The register carries no test, and that is a decision rather than an omission.**
Three shapes were available. A walk of `state/`, `corpus/` and
`frontend/public/` compared against this table checks committed data to ask
whether a document is complete, which `CLAUDE.md` section 13 gives three fates and
none of them is a pytest module - and it would pass while the `Policy` column
went stale, since a name appearing is not a policy still being right. The one
previous guard of that shape here enumerated twelve approved paths, covered two
collections out of nineteen, and was deleted the day it shipped
([../reference/agent-notes/gates-and-builds.md](../reference/agent-notes/gates-and-builds.md),
2026-09-06). Deriving the table from code moves the list rather than removing it,
and several stores build their paths outside `ledger.py` - `evals/writer.py`,
`publish_day_metrics.py` and `telemetry.py` each hold their own - so the
generator is a subsystem rather than a row of one plan. What is left is a named
rule with a printed command, which is section 13's third fate and is checked at
review. Fowler, 2026-09-12.

**Sharding is what makes a fold safe enough to switch on.** A month kept in one
file per month is folded by writing one file and unlinking one file, so an
interrupted run leaves either the shard or the aggregate and never half of
either. Deletion without that property is a partial write nobody can undo.
Why a ledger partitions at all is
[the shard rule](../architecture/contracts/schemas.md#a-ledger-partitions-only-when-its-read-carries-a-window).

**`state/labels.csv` is never deleted at any age**, and neither is a day payload.
A human faithfulness label is the only ground truth this project holds, and the
day payload is the record that a day happened. Both are evidence rather than
measurement, and evidence does not expire.

## Rejected alternatives

- **One global age for every store.** It governed `state/item-health/` and nothing
  else, while three other stores had no age at all - so a number that said
  nothing about them was read as if it did. Replaced 2026-09-02 by one knob per
  store, and a config still spelling the old name is refused by name rather than
  ignored ([config.md](config.md#every-store-names-its-own-cleanup-age)).
- **Deleting a day payload to defend the Pages ceiling.** Rejected because the
  payload is the archive, not because it is small - and the measurement says it
  is not small. On this checkout, 2026-09-13: 24,543,254 bytes of day payload
  against 6,244,624 bytes of rendered visual, so the text is about four times the
  pictures in the committed tree. What makes the built site the larger problem is
  everything the build adds on top of the payload - 7,027,075 bytes of payload
  tree against a 128,064,853-byte built site on 2026-08-27, eighteen times larger
  - so a visual is deletable because the item survives without it, never because
  it weighs more.
- **Merging the alarm and the cap into one number.** One number can be a warning
  nobody can ignore or a failure that arrives with no notice, never both.
  `retention.site_budget_mb` prints, `retention.pages_hard_cap_mb` stops.

## See also

- [config.md](config.md#every-store-names-its-own-cleanup-age) - where every age
  in the register is set, and the argument for each number.
- [growing-reads.md](growing-reads.md) - the companion question: what a read may
  open, where this page is what a write may keep.
- [partitions.md](partitions.md) - the layout that makes a fold one atomic file
  operation.
- [telemetry.md](telemetry.md) and [evaluation.md](evaluation.md) - the two
  ledgers that fold, and what each is evidence of.
- [../reference/repository-layout.md](../reference/repository-layout.md) - where
  a directory lives, where this page is what happens to what is in it over time.
- [../reference/measurements.md](../reference/measurements.md) - the instrument
  log the site-size figures are quoted from.
- [../architecture/publishing/console-payloads.md](../architecture/publishing/console-payloads.md) -
  the published copies and the windows the console draws over them.
- [../how-to/fine-tune-a-model.md](../how-to/fine-tune-a-model.md) - the corpus
  window, its two schedules, and what the history prune costs.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2 (the Pages ceiling),
  Guardrail #12 (nothing costs more as the repository grows), section 8 (the one
  force-push exception), section 13 (what a test may read).
