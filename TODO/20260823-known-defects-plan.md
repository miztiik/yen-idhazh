# Known defects

**Last Updated**: 2026-08-26

Seventeen defects found while shipping and re-reading the freshness, identity,
health and evaluation work, plus the console charts and the retrieval eval. None
was in the scope that found it. Defects 11 and 12 were found by running the gates
and by opening the published day in a browser, not by reading code; 13 and 14 the
same way, 15 by redrawing a chart that had to work around it, 16 by asking what
could ever make the new embeddings merge rule fire, and 17 by a query generator
that returned nothing.

**Fourteen are closed.** Defect 8 is closed on the item copy and on the day's band
bar. **Two are open.** Defect 2 has its instrument built and is waiting on human
labels and calendar time, which no amount of engineering closes. Defect 15 costs
a reader nothing today, so it was filed rather than fixed. Defects 16 and 17
were both Level 5 and belonged to the owner; both were answered on 2026-08-26.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision; each row is a defect with its evidence and where the fix landed.

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 1 | The published band ignores two of its own counterweights | 2 | FIXED - PR #18 |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN, INSTRUMENT BUILT - 0 of 60 labels, 1 of 10 run-days, and the 9B adoption resets the run-days again** |
| 3 | `/evals` and `/console` answer the same question twice | 3 | FIXED - PR #30 |
| 4 | `EmptyDay` points at a notice that is not on the page | 1 | FIXED - PR #14 |
| 5 | The home page bakes the build date and calls it today | 2 | FIXED - PR #14 |
| 6 | Duplicate eval rows inflate the ledger | 2 | FIXED - 2026-08-24 |
| 7 | Affiliate marketing pages pass the faithfulness bar | 3 | FIXED - 2026-08-24 |
| 8 | Reader-facing confidence copy says too little | 2 | **PARTLY FIXED - the band bar is open** |
| 9 | The push loop loses a whole day when it races another commit | 3 | CLOSED EARLY, REOPENED 2026-08-25, FIXED - 2026-08-25 |
| 10 | The `route` job hits its 60-minute timeout | 3 | FIXED - 2026-08-24 |
| 11 | A second run of a day overwrites the first run's charts | 3 | FIXED - 2026-08-24 |
| 12 | One quantity could fill three bars of a published chart | 2 | FIXED - 2026-08-24 |
| 13 | One stage is 2600x the others, so a linear timing axis answers for one of four | 2 | FIXED - 2026-08-25 |
| 14 | The canary day has no scored item, so the compression chart is only ever tested empty | 2 | FIXED - 2026-08-25 |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 4 | **OPEN - no reader-facing symptom** |
| 16 | The published item carries revision machinery no run can trigger | 5 | **DECIDED 2026-08-26 - the fields stay reserved, PR #141** |
| 17 | Three declared taxonomy dimensions are empty on every published item | 5 | **BUILT 2026-08-26 - PR #145 (lenses, events), PR #148 (entities)** |

## 16 - The published item carries revision machinery no run can trigger (DECIDED)

Found 2026-08-26 while asking what could ever make the new embeddings merge rule
fire. PR #114 made a day prefer a re-summarized item's newer vector. That rule is
right, and it is unreachable, because the text the vector tracks cannot change.

**Three things, each checked against the code.**

`backend/idhazh/contracts/digest_day.py` lines 112 to 123 declare `updated_at`
and `updated_by_run`; lines 131 to 137 bind the two together, and line 257 checks
that a revising run was recorded. Nothing in `backend/idhazh/` or
`frontend/src/` ever sets either one. `frontend/src/lib/payload/types.ts` lines
49 to 51 declare both and no component reads them.
`backend/idhazh/assemble.py` line 370 `run_that_wrote()` is the join the fields
exist for, and its only callers are `backend/tests/test_pipeline.py` lines 1089
to 1103.

`backend/idhazh/assemble.py` line 248 is
`fresh = [item for item in items if item.item_id not in already]`. An item the
day already holds is dropped whole, so the day keeps run 1's words.

That line is the second gate, not the first. `backend/idhazh/cli.py` line 220
loads `state/published.csv` and line 234 hands it to the plan;
`backend/idhazh/rank.py` line 246 drops any candidate whose address is already
published. So the producer has no path to a revision at all. The plan stage
refuses to re-plan the item, and assemble would drop it if it arrived by some
other route.

**Measured on this checkout, 2026-08-26.** Six committed day payloads, 2001
items. All 2001 carry the `updated_at` key and 1109 carry `updated_by_run`. **Not
one has ever been non-null.** The fields have never held a value.

**The doc is not the defect.**
[`docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md)
line 56 says "A revision is visible or it does not happen." Beside its
neighbours - "Membership only grows", "An item is never removed, demoted or
hidden because someone read it" - it reads as a design rule rather than a claim
about shipped code, and the rule holds: the system never revises, so it never
revises silently. What is wrong is narrower. A published contract carries two
fields, an invariant and a join helper for an event the producer cannot emit,
and one of those fields now sits in 2001 committed items forever.

**Level 5** (CLAUDE.md section 6), so it is recorded and not fixed. The two ways
out are not two implementations of one fix. They are two answers to one product
question: will yen-idhazh ever rewrite words a reader may already have read?

- **Make revision real.** This reverses the published-ledger skip rule, which is
  load-bearing in three places: `rank.plan_vertical` uses it to stop a repeat
  that a freshness window cannot stop, `cli.py` line 1192 writes it, and
  [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) line 338 rests
  the eval denominator on it - the four duplicate rows of 2026-08-23 exist
  because that ledger was empty. It also changes what a shared link shows after
  it was shared.
- **Delete the two fields.** Measured: `DigestItem` is `extra="forbid"`, so a
  model with the two fields removed rejects **all 2001** committed items -
  `extra_forbidden` on `updated_at`, and on `updated_by_run` for the 1109 that
  carry it. That needs a read-side migration stripping two keys from every day
  forever, for a field that never carried a value, or a rewrite of six committed
  payloads.

**Rulings.**

Reader, asked whether a shared link may change after it was shared: the answer
is not "never". It is that a reader must not be made to doubt their own memory.
A page that revises and says so is fine. A page that never revises is fine. A
page that improves the wording quietly is the one that costs the trust. The
system is in the second state today, so nothing is being taken from a reader
while this sits open.

Fowler, asked for the contract shape: two rulings that both hold, which is why
this is a decision and not a task. Name the consumer (worldview 14) - there is no
writer, no reader and no dashboard, so the delete-first instinct says the fields
should not exist. But contract is the last step of expand-migrate-contract
(worldview 5), available only once no live payload carries the field, and here
every one does. The right shape is known and the sequence that reaches it is
blocked by 2001 committed items.

**What to do meanwhile: nothing.** The cost of leaving it open is not paid by a
reader. It is that the next person reads the contract, sees an invariant about
revisions, and believes the pipeline can produce one.

**Decided 2026-08-26 by the owner: the fields stay, and the promise is corrected
instead (PR #141).** Neither way out was taken, because the row's own evidence
says deletion buys a reader nothing and costs a read-side migration plus a
rewrite of 2,121 committed items. What was actually wrong is the sentence, so
that is what changed. `layout.md` now says an item's words are written once, by
the run that introduced it, and keeps "a revision is visible" as the rule a
revision would have to meet. `updated_at` and `updated_by_run` say "reserved" in
their own descriptions and name the three gates. The named trigger that would
revive revision is a summarizer model swap
([`20260825-qwen35-9b-adoption-plan.md`](20260825-qwen35-9b-adoption-plan.md)) -
a better summarizer is the one event that makes published words worth
rewriting.

Two tests now pin it, because prose is what drifted: a published address is
never planned again, and a second run carrying different words for an item the
day already holds changes neither the words nor either field. The first gate had
no test at all before this.

Recorded in
[`docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md).

## 13 - One stage is 2600x the others, so a linear timing axis answers for one of four (FIXED)

Found 2026-08-25 while putting the console charts on a real coordinate system
(PR #93). Measured on the committed ledger: `summarize` runs 110.6 s, `score`
3.2 s, `fetch` 516 ms, `extract` 42 ms. The extent is 42 ms to 110.6 s, which
`.nice(4)` rounds out to 0-150 s, so three of the four stage lines sit on the
baseline and 26% of the plot is empty above the highest one. The chart can
answer "is summarize getting slower" and cannot answer it for anything else.

The padded linear domain was ruled deliberately for that chart and is correct
for stages of comparable size, so this is not a regression to revert. The two
candidate fixes were a log y axis - `logAxis` already exists in
`frontend/src/lib/charts/frame.ts` and the compression chart uses it - or one
small multiple per stage. Choosing between them was a Jony call, because it is a
question about what the chart is for, not about the maths.

**Fixed 2026-08-25 with the log y axis.** Jony ruled one chart, four lines, all
four stages: the four series are the same quantity, in the same unit, over the
same items, so small multiples would say every stage matters equally and could
never show a crossing. Measured on the same four values after the change:
`summarize` 81.4% of the plot height, `score` 50.2%, `fetch` 35.2%, `extract`
12.9%, against 78.1 / 2.15 / 0.38 / 0.03 before. Deleting `extract` was refused,
and the refusal is the rule that came out of the row: a series is deleted when it
carries no information, never when the axis is failing to show the information
it carries. `/console/` first-load JavaScript went from 63,943 B to 64,438 B,
495 B for the decade furniture and the gap handling. Recorded in
[`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md).

## 14 - The canary day has no scored item, so the compression chart is only ever tested empty (FIXED)

Found 2026-08-25 while redrawing the compression scatter (PR #97). The browser
suite runs against the canary day, and that day carried no scored item, so the
chart's populated state - the band zone, the truncation diamond, the point
marks, the y domain - had no coverage at all. Everything the suite proved about
that chart was proved about an empty window. The live chart draws 1166 points;
the tested one drew none.

**Fixed 2026-08-25.** `build_canary_day.py` now writes eight rows through
`idhazh.evals.writer.append` - the writer the pipeline appends with, so the
contract validates every field and the column order is the contract's, not a
hand-rolled copy of it. The rows are shaped for the chart: 38 to 6100 source
words spans four decades of log x axis and puts a mark under each of the four
configured target zones, two items carry the truncation flag, and all three
confidence bands appear. The published item and the ledger row take their band
from one `score.verdict` call, so the digest and the console cannot disagree
about what an item scored.

The empty rendering is still proved: `a window holding no scored item says so
rather than drawing an empty plot` pans off the scored days and asserts the
sentence and zero marks. `a missing ledger costs the page a section, never the
page` was the one existing test the fixture change invalidated; it is now `an
empty section costs the page that section, never the page` and points at the
failed-item list, which is the section the canary telemetry leaves with nothing
to show.

The builder stays idempotent, which is what
[../docs/reference/agent-notes.md](../docs/reference/agent-notes.md) asks for:
three consecutive runs produced a byte-identical `scores.csv`
(sha256 `18ef24f9c3e6684e`, 4682 bytes, measured 2026-08-25 on Windows 11), and
`backend/tests/test_canary_day.py` pins both halves of that - a fresh state
directory writes the same bytes every time, and a second append to a directory
that survived the clear adds nothing.

## 15 - A stage that did not run and a stage that took no time arrive as the same zero (OPEN)

Found 2026-08-25 while redrawing the stage timings on a decade axis (PR #109).
`frontend/src/routes/console/+page.server.ts` builds one `StageTimingDay` per
day, and its median helper answers an empty sample with a number:
`if (values.length === 0) return 0;`. So a day the scorer never ran on arrives
as `scoreMs: 0` - the same value that field carries when the scorer did run and
took no measurable time. Two facts become one number, and nothing downstream can
separate them again.

**It is wider than the score line.** All four stages call that helper:
`fetchMs: median(nums('fetch_ms'))`, and the same for `extract_ms`,
`summarize_ms` and `score_ms`. Each one turns "not measured" into zero.

The score line has a second way in. `nums()` drops a null before the median is
taken; the score list does not. `Number(row.score_ms ?? 0) || 0` keeps a missing
measurement in the sample as a zero, so a day of scored rows carrying no
`score_ms` medians to zero without passing through an empty sample at all.

The day filter inherits the blindness. `day.fetchMs > 0 || ...` drops a day
where nothing was measured, and cannot tell that day from one where all four
stages genuinely finished inside half a millisecond.

**Neither ledger is at fault.** `ItemHealthRow.fetch_ms`, `extract_ms` and
`summarize_ms` are `int | None` with a null default, so an item-health row says
"not measured" exactly. An item the scorer skipped writes no eval row at all, so
`state/scores.csv` says it by the row's absence. Both persisted layers keep the
distinction. The loader spends it.

**No reader sees this today, and nobody should re-fix that.** PR #109 made the
chart treat a non-positive value as a gap: the line breaks, it is never clamped
to the axis floor, and the loss is named in type under the legend - `No time
recorded for score on 1 day in this window.` Before that, a zero on a decade
axis drew a plunge saying the stage got a thousand times faster, which is a
false statement made by the chart itself. That symptom is closed. See
[`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md).

So this is a contract weakness, not a visible bug. The chart rebuilds a
distinction the payload threw away, and it only succeeds because a real stage
timing is never zero in practice. The next reader of that field has to rebuild
it from the same clue, and will probably forget.

**The shape of the fix, recorded and not implemented.** Give the four fields the
type the ledgers already have. `median()` returns `null` on an empty sample,
`StageTimingDay` carries `number | null`, the loader passes the null through, and
the chart reads it instead of inferring absence from `<= 0`. Absence then
survives the whole path instead of being guessed at every stop.

**The cost, checked rather than assumed.** `StageTimingDay` is hand-written in
`frontend/src/lib/charts/series.ts`. It is not a Pydantic model, nothing
generates it into `schemas/`, and the console route is prerendered, so no
committed payload carries it. CLAUDE.md section 11 does not reach it: the fix
needs no `version` date-stamp, no `changelog` entry and no read-side migration.
What it does cost is four files and a rule every later consumer must follow, and
that is why it was filed instead of folded into the chart work that found it.

**Level 4** (CLAUDE.md section 6). The fix touches `series.ts`,
`+page.server.ts`, `StageTimings.svelte` and `frontend/tests/console.spec.ts`,
plus the rendering paragraph in
[`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md).
Four files and structural: it changes how absence travels, not one call site.
Not Level 5 - no persisted contract moves and no reader-facing promise moves.
Not Level 3 - every consumer reads that shape, so it is not a local fix.

## 17 - Three declared taxonomy dimensions are empty on every published item (BUILT)

Found 2026-08-26 while building the retrieval eval. Its free query tier builds
queries from entity slugs carried by three or more items, and it built none.

**Measured over the committed payloads**, all six days under
`frontend/public/digest/`: 1889 items, and 0 of them carry a non-empty `lenses`,
`events` or `entities`. Per day - 2026-08-21: 4 items, 2026-08-22: 10,
2026-08-23: 147, 2026-08-24: 731, 2026-08-25: 724, 2026-08-26: 273. Every column
is zero on every row. The keys are present on each item as empty arrays, so the
shape ships and only the values are missing.

**Nothing writes them, and nothing ever did.** `to_article` in
`backend/idhazh/extract.py` builds the only ok article and passes none of the
three; `_failed` in the same file does the same for a failed one. All three are
declared `default_factory=list` in `backend/idhazh/contracts/article.py`, so the
omission is legal and silent. `to_digest_item` in `backend/idhazh/assemble.py`
then copies the empty lists onto the published item. No prompt is involved:
neither file in `backend/idhazh/prompts/` contains the word lens, event or
entity. This is an unbuilt feature, not a regression.

**Two more dead wires found on the same trail.** `config/watchlist.json` declares
`"entities": []`, so the ceiling on items that could gain an entity is zero
whatever the matcher. `backend/idhazh/cli.py` hands `plan_vertical` a hardcoded
empty `watchlist_keys`, so `watchlist_bonus` has never moved a score - the
watchlist term of the ranking formula is dead arithmetic, and `PlannedItem`
persists a `watchlist_hit` field that is always false. `EntityDef.aliases` is
declared in `backend/idhazh/contracts/watchlist.py` and read nowhere.

**The vocabulary would fire, but the match rule is the design.** Measured
2026-08-26 over our own published title, summary and key points. A word-boundary
match on the words inside each lens id hits 167 of 1889 items, 8.8 percent -
`china` 94, `markets` 69, `cyber` 11, `ai-roi` 2. An event id as a word hits 438
items, 23.2 percent. Both are floors, not proposals.

The spread matters more than either number. Substring instead of word-boundary
gives 200 items; matching `market` instead of `markets` gives 335, 17.7 percent;
and dropping the two-letter guard so `ai-roi` may match on `ai` gives 1666 items,
88.2 percent, because `ai` sits inside `said` and `remains`. One unstated choice
moves the answer tenfold and turns a filter into noise. The rule is a curated
artifact, and it has nowhere to live in config today.

**Level 5** (CLAUDE.md section 6). Assigning a tag needs a rule, and no config
contract has anywhere to put one: `LensDef` carries `id`, `display_name` and a
lifecycle, `EventDef` carries `id` and `display_name`. The measured spread says
the rule cannot be derived from the id, so it must be written down, and writing
it down changes a persisted config shape and pulls in section 11. Beyond that the
work is a matcher plus tests, a wiring commit, a curated watchlist, and the
`watchlist_keys` wiring - and that last one reorders every future day, because a
0.5 bonus that starts firing is a live ranking change.

**How it runs is settled; where it runs is not.** Four places agree the tagger is
deterministic, uses no model and costs no extra request: `discovery.md`, the
`LensId` docstring in `backend/idhazh/contracts/taxonomy.py`, Fowler's recorded
ruling 1 in [`20260815-digest-pipeline-plan.md`](20260815-digest-pipeline-plan.md),
and that same plan-doc's stage diagram, which marks the plan job "(no model)".
Nothing in the repository proposes asking a model.

The site is the open question and the two candidates cost different contracts.
[`docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md)
says "a tag, applied after the fetch", which puts the matcher on sanitized
article text at Extract, where `Article` already holds the fields and nothing new
is persisted. The stage diagram says "rank + tag lens/entity" inside the plan job,
which sees the feed title alone and would need three new fields on `PlannedItem`,
making `run-plan` a second contract to version. Picking one is the consultation
this row waits on.

Andre, consulted 2026-08-26, ruled out the third option: do not ask the
summarizer for the tags. A tag decides what a reader is shown under a filter, so
a page picking its own tags is fetched text steering a control (Rule #11), and it
adds decode tokens to the stage that already dominates the run. Whichever
deterministic site is chosen, the matcher runs after `sanitize` and may only emit
a member of a closed enum - a hostile page can then win a tag we already publish,
and can never invent one.

Fowler, consulted 2026-08-26, added a third outcome. Before asking how to build
the tagger, ask whether the surface should exist: three fields, two schemas, a
frontend type and two vocabularies are rent paid daily by a feature with no
reader-facing consumer today. So the consultation weighs three options - tag at
Extract, tag in the plan job, or delete the dimensions. Deleting is also a
breaking change needing a read-side migration, so it is the same class of work,
not the cheap way out.

Diagnosis recorded in
[`docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md),
with the measured zero also noted on
[`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md),
which had called the same controls "mostly-zero".

**Built 2026-08-26. The owner answered both questions: wire lenses and events
(PR #145), and build entities (PR #148).** So neither the delete option nor the
design-row option was taken.

The rule is one sentence, and the second half is the load-bearing part: **a tag
is assigned when one of its curated terms appears in the item's words as a
whole-word phrase, case-folded, and nothing is derived from the tag's id or its
display name.** Terms live in `config/taxonomy.json` under `keywords` and in
`config/watchlist.json` under `aliases`, so tuning them is not a code change.

**Where it runs is settled: the worker, on the extracted article, after
`sanitize`.** The stage diagram in
[`20260815-digest-pipeline-plan.md`](20260815-digest-pipeline-plan.md) said the
plan job, which sees the feed title alone and would need three new fields on
`PlannedItem`; it was corrected in the same commit. Andre's ruling holds - no
model is asked, and the vocabulary is keyed by a closed enum, so a hostile page
can win a tag we already publish and can never invent one.

**Measured, and the measurement changed the answer twice.** A first keyword
draft using bare `research` and `study` put the research event on 34.7 percent
of real articles; curated phrases moved it to 12.4 percent. Five of thirty-five
candidate entities matched nothing at all and were cut. Final coverage over 121
real article payloads: lenses 25.6 percent, events 57.9 percent, entities 31.4
percent, no single tag above 22.3 percent.

**The number the row existed for: the retrieval eval's free query tier goes from
0 queries to 25**, covering 616 of 2,237 committed items. That is what the
corpus supports - no committed payload was rewritten, so the tier reports zero
until new days land.

**`watchlist_bonus` is no longer dead arithmetic.** `watchlist_keys` is now the
candidates whose feed title matches an entity alias. This reorders every future
day and no past one.

Recorded in
[`docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md),
[`docs/concepts/config.md`](../docs/concepts/config.md) and
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md).

## 2 - The faithfulness thresholds have no labelled error rate (INSTRUMENT BUILT)

The old saturation premise is closed and false. Measured 2026-08-24 on the
committed ledger, `state/scores.csv` at n=447, the recorded `band` column says
285/81/81 (`high`/`medium`/`low`). Re-banding those same rows with today's
`band()` and today's `EvaluationConfig` gives 258/108/81, or 57.7% / 24.2% /
18.1%. Twenty-seven rows move from `high` to `medium`: 11 on lead coverage
alone, 11 on a dropped hedge alone, and 5 on both. The same 27 as at n=156 - the
gap is a fixed historical residue, not a rate that grows.

The threshold question is still open for four different reasons:

- There are no human labels, so no cut has a measured error rate behind it.
- The evidence base is thin on distinct run-days.
- Five source URLs appear under two different `pipeline_fingerprint` values - the
  only two the ledger held when this was measured; there are five now. Every one
  moved downward: -0.105, -0.595, -0.114, -0.079 and -0.034. That
  uniform shift points at a producer change in a way scattered noise would not.
- The recorded `band` column predates the counterweight caps and must be
  re-banded before it is read as a distribution.

Level 5 still applies. The thresholds are a reader-facing promise, so re-cutting
them needs measured label error, not a cleaner-looking bar (Rule #10).

Closing steps, in order:

1. Add the re-band utility so a stale `band` column is not mistaken for the live
   distribution. Done.
2. Draw 60 human-label rows: 6 per `hhem` decile, deterministic by hash. Label
   from the summary plus source URL, with `hhem` and `band` hidden. Record one
   binary answer, "does this assert anything the article does not support?", plus
   one tag. **Done 2026-08-24.** `LabelRow` in `backend/idhazh/contracts/`,
   `state/labels.csv`, the deterministic draw in `backend/idhazh/evals/labels.py`,
   and a human-paced CLI at `backend/utilities/label_queue.py`. The draw fills all
   ten deciles with no shortfall on today's ledger. Recorded in
   [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md).
3. Collect at least 10 distinct run-days at one `scorer_version` and one
   `pipeline_fingerprint`. **1 of 10, and the best ever reached is 3 of 10.**
   Measured 2026-08-27 over `state/scores.csv` at commit `5d8ba60`: 2,232 rows
   from 18 runs across 5 scored run-days carry 5 distinct fingerprints and 4
   distinct scorer versions. The live pair is 116 rows on `2026-08-26` alone, at
   `hhem-2.1-open@8e4a2e6e;weights-841b70e0;metrics-3;bands=0.80/0.50;lead=0.30`
   and fingerprint `f0d4ecc7...9ad669`. The longest streak in the ledger's whole
   history is `2026-08-24` to `2026-08-26` under `969b1917...d2b945`, which is
   where the stale "1 of 10, 731 eligible rows on 2026-08-24" figure came from.
   **Adopting Qwen3.5-9B-Q4_K_M (commit `5d8ba60`, 2026-08-27) moves
   `model_sha256`, so the next run mints a sixth fingerprint and this count
   restarts at zero again.** The reset mechanism and its measured rate are stated
   once, in
   [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).
4. Label the 60 rows. **0 of 60**, and `state/labels.csv` does not exist. Worse,
   the decile draw can only fill 38 of 60 from the live instrument's 116 rows,
   short in 7 of the 10 deciles - so the pool has to grow before 60 is even
   drawable. Human work. No AI judge, and the contract has
   nowhere to put one.
5. Re-test the cuts by stratum against the labels.

**This row cannot close on engineering.** Steps 3 and 4 are a human prerequisite
and a calendar prerequisite. Anyone reading this later: the instrument is built
and nothing about it entitles a threshold to move.

One risk is no longer a risk. It is measured. The pipeline fingerprint moved four
times across five scored run-days (2026-08-27, `state/scores.csv` at `5d8ba60`),
the scorer version moved three times over the same five days, and no
(`scorer_version`, `pipeline_fingerprint`) pair has ever held for more than three
consecutive run-days. Ten consecutive days under one pair is not merely hard
while the pipeline is under active change - it has never happened. The
falsifiable relaxation is "10 run-days at one `scorer_version`, with
`pipeline_fingerprint` recorded per row and reported as a stratum" - the threshold
belongs to the scorer, and a producer change is a covariate rather than a
disqualification. The other answer is to freeze the pipeline for ten days and pay
for the window in shipped improvements. Both change this plan's text, so both are
the owner's call.

`evaluation.spot_checks_per_week` is already 10, and the spot-check has never
run. The missing instrument was labels, not more rows. The instrument now exists;
the labels do not.

## 6 - Duplicate eval rows inflate the ledger (FIXED)

Four rows on 2026-08-23 in `state/scores.csv` are byte-identical re-observations
of items published the day before, by `output_digest` and `hhem`. That disagreed
with [evaluation.md](../docs/concepts/evaluation.md), which says an item whose
inputs did not change writes no row at all.

The cause was not the planner. `state/published.csv` carries no rows for
2026-08-22, so the next day's plan had no record of those addresses and
re-summarized them. The dedupe works today; the append path did not.

Fixed at the writer, and the rule stayed. See the closing table.

## 7 - Affiliate marketing pages pass the faithfulness bar (FIXED)

Three `fool.com/the-ascent/` credit-card affiliate landing pages published in
the `world` vertical on 2026-08-23 and 2026-08-24. They scored 0.924, 0.947 and
0.932 HHEM and recorded `high`. Their feed was `cnn-world`, a working news feed
syndicating a partner's promotional pages.

The summaries may be faithful. That is the point: no faithfulness threshold
detects this at any cut. A page of short declarative marketing sentences is easy
to entail, so raising the bar rewards the wrong source. The control belongs at
collect, before anything is spent on the item.

## 8 - Reader-facing confidence copy says too little (PARTLY FIXED)

Reader found two surface problems while reviewing defect 2.

- The `medium` band should say what is missing rather than "mostly matches the
  source". **Fixed.**
- The top band bar prints counts nobody can act on. **Still open.** That is an
  aggregate visual, not an item's copy, and what it should say instead is a
  Jony and Reader question that nothing here has answered.

Reader's summary: "If someone re-cuts for the sake of the bar looking less
green, that is tuning a number so a chart looks humbler, which is the opposite
of honesty."

## 9 - The push loop loses a whole day when it races another commit (FIXED)

**Closed on 2026-08-24 while the loop still could not loop. Reopened 2026-08-25.**
The first close removed one trigger and called the class removed. It did not:
the loop kept dying on the first race it could not text-merge, and run
`32772221068` lost a finished day to it a day later. Level 2 was also wrong; the
repair is Level 3.

`digest.yml`, steps `Commit what the plan saw` and `Commit the day`. The work is
committed, then pushed. A push that loses a race is meant to rebase and try
again, three times.

**What the first pass fixed.** The loop ran `git pull --rebase --autostash origin
main`. Any unstaged change in the checkout was stashed, and when it failed to
reapply the step exited 1 and the whole day's work was discarded after plan,
four shards and assemble had all succeeded. Evidence: run `32671663130`,
2026-08-24, dying with `error: cannot rebase: You have unstaged changes.` The
dirty file was `docs/concepts/design-system.md`, whose blob was CRLF against a
`text eol=lf` attribute, so every Linux checkout saw it modified before the job
did anything. PR #44 removed that trigger; the autostash went with it.

**What it missed, twice over.**

First, `set -e` and one unguarded command. `git pull --rebase origin main` was
the only command in the loop with no guard, so a rebase that conflicted ended
the script where it stood - inside attempt 1. There was no attempt 2, the
three-attempt message never printed, and the checkout was left mid-rebase.
Measured 2026-08-25 against a scripted local origin, git 2.55.0, bash 5.3.15.

Second, and this is the actual defect: the base was stale. `actions/checkout@v6`
in `assemble` carries no `ref`, so it takes main's tip at trigger time, and the
workflow's own comment measures a run at 164-184 min. Assemble always rebuilt
the day from a base up to three hours old and then asked `git merge-file` to
reconcile two derived payloads. Fixing only the guard would not have published
run `32772221068`: attempt 2 dies two lines further down at `git checkout -- .`,
which fails on unmerged paths, and the conflict is deterministic - the same
commit rebased onto the same tip conflicts all three times.

**Fixed structurally, three ways.**

- **Every command in the loop is guarded**, and a rebase it cannot finish is
  aborted so the next attempt starts on a checkout with no rebase in progress.
- **The append-only ledgers union.** Every file under `state/` carries
  `merge=union` in `.gitattributes`. Two runs that both appended are not in
  disagreement, so the union of both sides is the merge. That is what the plan
  job needs: it records what it saw and cannot rebuild it.
- **Assemble refreshes its base and rebuilds.** On a rejected push the loop
  hands the derived paths back to origin's tip and runs `python -m idhazh
  assemble` again against it. `stage_assemble` already loads the previous day
  and appends - it IS the conflict resolver, and it was being run once against a
  stale base. The refresh names `digest.json` and `run.json` one file at a time
  and never the day's directory: the routes artifact unpacks this run's rendered
  charts into that directory and no producer in the assemble job can make them
  again (defect 11). `frontend/public/telemetry/` is a full rewrite of
  `state/item-health/`, so it is regenerated rather than unioned.

**Evidence this time.** `backend/tests/test_workflows.py` executes the script
against real local repositories, no network and no mocks. The hard case scripts
an origin that gains BOTH another run of the same day and an unrelated pull-
request merge while the job works, then asserts the day published: five items
from two runs in `digest.json`, run 3 recorded as run 3 rather than a second run
2, and both sides' rows exactly once in `state/published.csv`,
`state/scores.csv` and `state/item-health/<YYYY-MM>.csv` - two of which append
blind, so a rebuild on its own last attempt would show seven rows for five
items. The rendered chart survives, the pull request is untouched, and the
checkout ends with no rebase in progress. Both falsified on 2026-08-25 by
removing the fix and watching the same tests fail.

Recorded in
[`docs/reference/github-actions.md`](../docs/reference/github-actions.md).

**Still open, and named rather than folded in:** `build_manifest` and
`build_day` disagree about run identity. That is its own Level-4 row.

## 10 - The `route` job hits its 60-minute timeout (FIXED)

**Measured 2026-08-24**, `ubuntu-latest` 4 vCPU, run `32742672105`. The reading in
the first two versions of this row was wrong twice. It is not "the timeout fires
every run", and it is not a spread nobody can explain.

| What | Value |
| --- | --- |
| Fixed cost - checkout, Python, cache, llama-server start, install, artifacts | 47 s |
| `Route and render` step | 3155 s (52.6 min) |
| Items routed | 149 |
| Per-item | mean 21.0 s, min 8.1 s, max 56.0 s, n=148 |
| Kinds | 15 chart, 134 none, **0 diagram** |

The fixed cost is 1.5% of the job. Model loading does not own the time. Per-item
inference does, and nine calls in ten produce nothing.

**The real defect is an arithmetic inconsistency, not a slow model.**
`(3600 - 47) / 21.0` is 169 routable items. `run.safety_ceiling_per_run` is 200.
Those two numbers have never agreed. The runs that fit did so because about a
quarter of the plan had no `OK` summary and was skipped, so improving the
summarizer breaks the router. Five of the last eight runs were cancelled at the
bound, and a cancellation reads 60.3 because that is where the runner stopped it,
not because anything was measured there.

Fixed structurally, three ways, none of them the timeout:

- **The model is not asked a question already answered.** A chart's bars index
  the article's own facts and must share one unit, so the widest chart an item
  can carry is its largest unit group. Below `min_chart_points` the answer is
  `none` whatever the model says. `reachable_kinds()` decides that before the
  request is built, and the skip is a payload field (`asked_the_model`) plus a
  manifest count (`items_prefiltered`), never an inference from prose.
- **The router has its own request budget.** It had been borrowing
  `run.shard_timeout_minutes` - 150 minutes against a 60-minute job, so it could
  never fire. `visuals.request_timeout_minutes` defaults to 2.0, from the
  measured 56.0 s worst item, doubled.
- **The stage warns before the bound.** `run.route_budget_minutes`, default 40.
  A router cancelled at its bound publishes a day with no visuals and says
  nothing about it.

**The gate yields nothing on the default config, and that is deliberate.** A
diagram is always reachable while `diagram` is in `visuals.enabled_kinds`, so no
item is skipped. Turning the arm off would clear the bound immediately - 0
diagrams in 149 routed and 0 in 586 published - but nothing committed says *why*
it is zero, because `to_route` folds a rejected diagram into `none`. The router
now logs the draft kind beside the final kind, so one run separates "the model
never picks it" from "our own floor rejects it". Measure, then descope. Not the
reverse.

**One live correctness bug fell out of this.** `ChartPoint.fact_index` was
bounds-checked and never deduplicated, so a draft naming index 3 three times
produced a publishable chart of one number under three invented labels - every
value true, the comparison fabricated. Found by Carmack and Andre independently
while ruling on the gate. Fixed in the same commit, and it is what makes the
gate's proof exact rather than approximate.

## 11 - A second run of a day overwrites the first run's charts (FIXED)

Found by opening the published day in a browser and counting, 2026-08-24. The
committed digest declares **32 rendered visuals** and the day's directory holds
**18 SVG files**. Nothing was missing: **fourteen paths were each claimed by two
different items.**

`digest/2026/08/24/india-01.svg` is referenced by both:

| Item | Its alt text |
| --- | --- |
| Indian stock markets open higher on blue-chip buying amid global cues | Bar chart. 2026 30; 2026 77,744.15; 2026 225; 2026 77,540.83. |
| Defence Stocks Rise on Indigenous Procurement Push | Bar chart. 15% 15 %; 9% 9 %; 194% 194 %; 39% 39 %. |

One of those two showed a chart drawn from the other article's numbers, under
alt text describing figures that were not in the picture. Every value in the
chart was true and the picture belonged to another story - the same class of
failure as defect 12, and the more serious of the two because the numbers are
not even about the same subject.

The cause is `ordinals` in `stage_route`, a per-process counter. The day ran four
times on 2026-08-24. Each run started at 1 and overwrote the previous run's file,
while the digest kept every run's items and every run's path.

Fixed at the writer. Numbering continues from the highest `<vertical>-<NN>`
already in the day's directory, so run 3 starts where run 1 stopped. That keeps
the `<vertical>-<NN>` shape the contract fixes - no hash in any published path -
and needs no handshake between `route` and `assemble`, which run in different
jobs. Carmack raised the same counter as the reason not to shard the route job;
it turned out to be biting already, across runs rather than across shards.

## 12 - One quantity could fill three bars of a published chart (FIXED)

`ChartPoint.fact_index` was bounds-checked and never deduplicated. A draft naming
index 3 three times passed every control: `same_unit_bars` grouped all three
under one unit, the width check saw three bars, and a chart of one number under
three invented labels published with alt text reading "2025 4,200 tonne; 2024
4,200 tonne; 2023 4,200 tonne".

Found by Carmack and Andre independently while ruling on defect 10's gate.
[`docs/architecture/publishing/visuals.md`](../docs/architecture/publishing/visuals.md)
said this failure was unreachable, and it was not.

Fixed at `to_route`: a draft that repeats a `fact_index` routes to nothing. That
is also what makes defect 10's reachability gate exact rather than approximate,
and the proof is an exhaustive test over every index subset.

## What closed, and where it went

| # | Defect | Fix |
| --- | --- | --- |
| 1 | `band()` read `unsupported_numbers` and the two faithfulness thresholds and nothing else; `lead_coverage` and `hedge_dropped` never reached the band a reader sees. Evidence: `ai-03` published as `high` with lead coverage 0.00. | Row 19, PR #18. One band function. A failed counterweight caps at `medium`. `evaluation.lead_coverage_min` is a `config/` knob. The open question - cap or outvote - resolved as cap. |
| 3 | Both routes rendered per-day band counts from `state/scores.csv`. Two surfaces reading one ledger disagree the first time one changes how it counts. | Row 18, PR #30. `/console` owns the band trend. `/evals/` stays as a prerendered page that links on, so a bookmark still works without JavaScript (`CLAUDE.md` section 3 keeps the route). |
| 4 | `EmptyDay.svelte` told the reader "the run notice above says which it was" while rendering with nothing above it. | Row 20, PR #14. The copy now names only what a reader can see. |
| 5 | `+page.server.ts` computed `new Date()` and every route is prerendered, so the build date was frozen into the HTML and called today. It also passed `latest={null}`, suppressing the one link that would rescue the reader. | Row 20, PR #14. The date comes from the payload the page renders. The latest-day link is restored. |
| 6 | The eval writer appended every row a run handed it. Four rows on 2026-08-23 are byte-identical re-observations of items the day before, because `state/published.csv` had no record of 2026-08-22 and the next run re-summarized them. The doc had always said an item whose inputs did not change writes no row at all. | 2026-08-24. The writer refuses a row whose address, pipeline fingerprint, output digest and scorer version all match a row already in the file, and de-duplicates inside one batch as well. The four historical rows stay: they are honest history, and rewriting an append-only ledger to tidy a denominator is the band-aid. Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 7 | `cnn-world` syndicated three `fool.com/the-ascent/` affiliate credit-card pages into the `world` vertical. They scored 0.92 to 0.95 and published as `high`, because short declarative marketing prose is trivially entailed. | 2026-08-24. `collect.blocked_url_markers`, a config-driven list of case-insensitive address substrings that never enter the pool. Default empty; the entry `fool.com/the-ascent/` lives in `config/idhazh.json`. Applied after the feed-health row is written, so what a feed offered and what the pool accepted stay separate facts. Recorded in [`docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md). |
| 8 | `medium` printed "Mostly matches the source" - a grade a reader can do nothing with. Both things that cap an item at `medium` were computed and neither reached the page. | 2026-08-24. `score.verdict()` returns the band and the one reason together; `band()` is a wrapper with no logic. `DigestItem.band_reason` is a closed identifier and the site owns the sentence. A day published before this renders exactly as it did. Browser-smoked at 420px across `/`, a day, a vertical, the archive and the empty state. **Closed fully 2026-08-24** by deleting the day-level band bar, which still printed the retracted sentence at the top of the page - above the item that had abandoned it. Recorded in [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md). |
| 9 | Both commit steps in `digest.yml` ran `git pull --rebase --autostash`. A rebase will not start on a dirty tree, and run `32671663130` lost a finished day to one CRLF file. | 2026-08-24. Each loop prints what is dirty and discards it before the rebase; untracked files are left alone; `--autostash` is gone. A workflow contract test pins the shape in both jobs. CI does not run `digest.yml`, so the next change there still needs a dispatched run. |
| 10 | `route` lands between 51 and 60+ minutes against a 60-minute bound, and nothing recorded what it spent. | 2026-08-24. Measured on run `32742672105`: 47 s fixed cost, a 3155 s stage, 149 items at 21.0 s each, 15 charts and 134 nothings. Per-item inference owns the time and 90% of it produces nothing, so the router now decides an item on its own facts when no enabled kind could survive, gets a request timeout of its own instead of borrowing the summarizer's 150-minute one, and warns at `run.route_budget_minutes`. A live bug fell out of the ruling: `fact_index` was never deduplicated, so one quantity could fill three bars and publish a fabricated comparison. Recorded in [`docs/architecture/publishing/visuals.md`](../docs/architecture/publishing/visuals.md) and [`docs/reference/measurements.md`](../docs/reference/measurements.md). |
| 13 | Four stage timings shared one linear y axis, so the slowest stage set the domain and the other three drew flat on the baseline. Measured: 78.1 / 2.15 / 0.38 / 0.03 percent of the plot height. | 2026-08-25. One chart, four lines, a decade y axis: 81.4 / 50.2 / 35.2 / 12.9 percent on the same values. Decade gridlines labelled across ms to s, unlabelled stubs at the eight steps inside each decade, a zero drawn as a gap and never clamped to the axis floor, and the legend sorted by the newest day descending. The padded linear rule stands for series of comparable size and yields at two decades of drawn extent. Recorded in [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md). |

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what the bands claim.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the surfaces in 3, 4 and 5.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - what happens to this file when a row closes.
