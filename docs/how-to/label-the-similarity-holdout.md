# Label the Similarity Holdout

**Last Updated**: 2026-10-08

Read pairs of articles the merge line has to decide between, and record whether
each pair is one news event or two. The marks are saved through the ledger door
as the `holdout-pairs` ledger, under
`state/raw/content-similarity-judge/holdout-pairs/`, and the gardener packs them
under `state/compact/content-similarity-judge/holdout-pairs/`. They are the
fixed floor every fitted merge line has to stay above.

The rule the floor guards is in
[../architecture/publishing/autotune-content-similarity.md](../architecture/publishing/autotune-content-similarity.md).
This page is how a mark gets made.

## What the holdout is for

The merge line fits itself off a model's own verdicts. A line fitted that way
cannot certify itself: if the judge drifts, the record drifts with it and the
fit reports that everything is fine. The holdout is the outside reading. It is
produced by a different labeller, outside the nightly loop, and nothing in the
pipeline writes it - so a line that drops below a pair marked as two stories is
a fact somebody can see rather than a number arguing for itself.

The `false` rows are the load-bearing ones. A pair marked as two stories that
sits above the line is a story the reader never gets to see.

**What it holds today.** 200 pairs, marked by `claude-opus-4.6` on 2026-09-19:
196 one story, 4 two stories. All four two-story marks are one news cluster - a
lake being renamed, carried by two different companies - so the floor currently
rests on one story rather than on a spread of news. They sit on the ledger door
under `content-similarity-judge/holdout-pairs`, copied there from the one CSV
file they were kept in before, which is gone
([persistence.md](../architecture/contracts/persistence.md)).

## Get a draw

The sheet is built from **drawn pairs**, not from the published days directly. A
drawn pair carries the two articles' address keys and the score the pass gave
them, which is what lets the sheet sort by distance from the line.

`idhazh council-prepare` writes one draw a day, under
`backend/var/council/<date>/selection/<judge>/`
([run-the-pipeline.md](run-the-pipeline.md)). It runs the selection step of every
tenant registered in `council.tenants`, so it writes nothing until the
content-similarity judge's slug is in that list. That tree is not committed, so
a fresh clone has none of it and you draw the days you want first:

```powershell
python -m idhazh council-prepare --date 2026-09-18 --run-id 2026-09-19-1
```

Any tree of CSVs carrying `date`, `pair_key`, `left_url_key`, `right_url_key`
and `composite_score` will do - the tool reads every `*.csv` in a `selection`
slot under `--draw-root`, so pointing it at `backend/var/council` covers every
day drawn so far. It reads the selection slot and nothing else because a night
leaves its verdicts and its instrument rows in the same tree, and those carry no
score. Name the draw CSVs and every published UTC day needed to resolve their
two sides. The harvest joins on that named population, and a mark whose pair is not in the draw you
hand it is a mark that is not saved.

## Draw a sheet

Read-only apart from the two files it writes. It calls no model and opens no
socket:

```powershell
python backend/utilities/sample_sheet.py --draw-root backend/var/council --line 0.94 `
  --draw <selection.csv> --day 2026-09-01
```

| Flag | Default | What it is |
| --- | --- | --- |
| `--draw-root` | required | Base path for the named draw files. |
| `--draw` | required, repeatable | CSV path relative to `--draw-root`. |
| `--day` | required, repeatable | Published UTC day to read, `YYYY-MM-DD`. Name both sides of a pair across midnight. |
| `--labels` | required with `--harvest`, repeatable | JSON label batch relative to `--out`. |
| `--line` | required | The merge line the bands are measured against. `assemble.same_story.floor_min` is what a day was grouped at unless a fit has moved it. |
| `--digest-root` | `frontend/public/digest` | Where the published days are, so a pair's two articles can be resolved to a title and a summary. |
| `--out` | `test-results/similarity-pairs-to-label` | Where `pairs.json` and `pairs.md` are written. Refused inside `frontend/public/` or `frontend/build/`, because the sheet quotes untrusted text and a published one would put it on the site. |
| `--corridor` | `0.02` | How wide either side of the line counts as "just". |
| `--total` | `200` | How many pairs the sheet carries. |
| `--harvest` | unset | Switches to harvest mode; see below. |
| `--state-root` | `state` | The state root a harvest saves the marks under. |
| `--labeller` | unset | Required with `--harvest`. |
| `--labelled-on` | unset | Required with `--harvest`: the UTC day the marks were made, `YYYY-MM-DD`. |
| `--run-id` | unset | Required with `--harvest`: the run the saved file names as its writer, `<YYYY-MM-DD>-<number>`. |
| `--commit` | unset | Required with `--harvest`: the full commit SHA of the checkout, as `git rev-parse HEAD` prints it. |

It prints what it resolved and what it refused:

```text
INFO:idhazh:sample_sheet resolved 1197 pairs, refused {'no-article': 0,
'no-score': 0, 'already-drawn': 1607}, wrote 200 to test-results/...
```

`already-drawn` is normal and large - 1,607 of the 2,804 rows over 29 days were
one pair arriving twice. A pair whose two articles sit on different published
days is drawn on both of those days, so the same `pair_key` shows up once a day
and the second copy is dropped. `no-article` means the published day no longer
carries one of the two addresses.

`pairs.md` is the one to read. `pairs.json` carries the same pairs as data.

## How the pairs are chosen

Three rules, and all three exist because a benchmark drawn badly measures the
draw rather than the line.

- **`band_of` files each pair against the line.** At or above it and within
  `--corridor`, `just-above`; at or above and further, `well-above`; below and
  within the corridor, `just-below`; below and further, `well-below`. A score
  exactly on the line is `just-above`, because the pass refuses on
  `score < floor_min` - a pair at the line merges.
- **`select` round-robins the four bands, corridor first.** Not a quota: the
  bands are never evenly filled - 771 of 1,197 unique pairs over 29 days were
  well below the line and 105 just above it - so a quota hands the sheet to
  whichever band the draw happened to favour, and spends nothing on an empty
  one.
- **`_spread_order` bisects the two outer bands.** They are ordered so that any
  prefix still covers the whole score range: the first pick is the middle of the
  band, the next two are its quarters. Nearest-first everywhere gave a sheet
  running 0.9187 to 0.9719, and a benchmark whose easiest case is a hundredth
  from its hardest cannot tell a wrong model from a genuinely ambiguous pair.

There is no seed. Ties break on `pair_key`, so two runs over one draw write the
same sheet and a labeller can be handed a diff.

## Read the summaries, not the headlines

**This is the step that has already cost a round of work.** The score the mark
grades is built over `f"{title}. {summary}"`, and the summary is about seven
eighths of what the encoder reads. A mark made from two headlines is judging
less information than the pass did, which measures the wrong thing.

The first 200 pairs were labelled from headlines alone. Relabelled against the
full summaries, **eight of the twelve two-story marks were wrong**, and the
failures all have the same shape: the headlines describe different things and
the bodies describe one thing.

| The headlines | What the summaries showed |
| --- | --- |
| `Argentina fans react to Messi's retirement` against the retirement itself | The "reaction" piece opens on the retirement announcement and carries the same facts. One story. |
| `India awaits US tariff terms` against `India finalizes US trade pact` | The two headlines contradict each other. Both bodies write up the same official's same remarks. One story. |
| `Dolly Parton's Legacy Lives On` against the death report | The "legacy" piece is an obituary, opening on the death announcement. One story. |

The four marks that survived the relabelling are all one shape: a rename against
the request that preceded it, or one company's rename against another's. Those
events really are distinct.

So read both summaries in `pairs.md` before marking anything. A shared topic is
not a shared story, and two headlines that disagree are not two stories.

The sheet prints each pair's score and band above the two articles. They are
there so you can see which calls are close to the line; the mark is about the
two articles and not about the number.

## Write the marks

The sheet does not collect the marks. Write them beside it, in one or more
`labels-batch-<n>.json` files inside `--out`:

```json
{ "by_pair_key": { "0f3a...": true, "91c7...": false } }
```

`true` means the two articles report the same news event. **The values are JSON
booleans, not strings** - `"false"` in quotes is a non-empty string and harvests
as `true`. A pair you left out of the file produces no row at all, which is what
makes a sheet that comes back short stay short rather than getting filled in
with a guess.

## Harvest them back

```powershell
python backend/utilities/sample_sheet.py --draw-root backend/var/council --line 0.94 `
  --draw <selection.csv> --day 2026-09-01 --labels labels-batch-01.json `
  --harvest --labeller claude-opus-4.6 --labelled-on 2026-09-19 `
  --run-id 2026-09-19-1 --commit <full-commit-sha>
```

It saves the marks the named batches hold through the ledger door, as one file
under `state/raw/content-similarity-judge/holdout-pairs/<YYYY>/<MM>/<DD>/` for
the `--labelled-on` day. `--labelled-on` fills `marked_on` on every mark it
saves. `--labeller` reaches the `note` column with the pair's score beside it,
because a mark is worth what its labeller is worth and a row that does not say
cannot be argued with later.

`--run-id` and `--commit` name the file's writer, and the harvest refuses to run
without either. A person runs it, so the file's job is `operator`, at attempt 1
and shard 0. `--run-id` is `<date>-<a number>`, and `--commit` is the full commit
SHA of the checkout, which `git rev-parse HEAD` prints, so the file points back
to the code that saved the marks. `--harvest` takes no path: an older spelling
that named the CSV file to write is refused rather than read as a folder.

**The join is on `pair_key`, against the named drawn population and never
against the sheet in hand.** A mark belongs to a pair, not to a slot: harvesting
from the sheet meant that re-drawing it, or changing how pairs are chosen,
silently dropped every mark whose pair no longer made the cut - one selection
change turned 200 labelled pairs into 129. The benchmark accumulates instead.

**A harvest adds marks, and rewrites none.** Name the batches labelled since
the last harvest. A batch named again saves its marks again under the new day,
which is harmless: a pair is read once, with the mark it was given last, so a
corrected mark replaces the one it corrects. A harvest that finds no label saves
nothing.

**A mark counts for `similarity.holdout_reach_days` after the day it was filed
under** - 730 days in `config/idhazh.json`. Both readers, the scoring verb below
and the console's holdout panel, read that many days back and no more, so the
read stays the same size however long the ledger grows. A mark filed before that
stops counting until somebody harvests it again or widens the knob.

It prints what landed, and what did not:

```text
INFO:idhazh:sample_sheet harvested 200 labelled pairs into
raw/content-similarity-judge/holdout-pairs/2026/09/19/<file>.parquet, 0 labels
matched no drawn pair
```

A non-zero tail count means a `pair_key` in a batch file is not in this draw.
Widen `--draw-root` rather than editing the batch.

**Nothing schedules it.** A person labels when they choose rather than when a day
publishes, so no workflow runs the harvest and no job stages what it writes.
Commit the raw file yourself. The console reads the marks once the gardener has
packed their day, within about two days of the day they are filed under.

## Score the line against them

```powershell
python -m idhazh score-merge-line-holdout --date 2026-09-21 `
  --run-id 2026-09-21-35534060762 --labeller claude-opus-4.6 `
  --commit <full-commit-sha>
```

It counts what the merge line in force does to every marked pair filed inside the
reach of its `--date`, and writes one row into
`state/raw/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>/`,
which the gardener packs under
`state/compact/content-similarity-judge/merge-line-holdout-scores/`:
the line, the four cells, how many pairs it could not score, and how many marks
say two stories. It reads each day of its reach from whichever file holds it, so
it sees a mark as soon as a harvest saves it. `--labeller` is the same name the harvest was given, and
`--run-id` is `<date>-<a number>` - the row has to say which run took the
reading. `--commit` is the full commit SHA of the checkout that took it, which
`git rev-parse HEAD` prints, so the door file's envelope points back to the code
that wrote it. The verb refuses to run without it.

**Nothing schedules it.** The marks change when somebody labels more pairs
rather than when a day publishes, so no workflow runs this verb and no job
stages what it writes. Commit the raw file yourself, the way you commit the
marks.

**It writes nothing when fewer than half the marks can be scored.** Retention
deletes published days the marks still name, and four cells counted over
a handful of surviving pairs read as a line that got almost everything right.
The verb exits 1 and prints how many it resolved.

| What you see | What happened |
| --- | --- |
| `resolved N of M marked pairs, and a reading means nothing below K` | Retention has taken the days most marks name. Nothing to fix in the file; the comparison has aged out. |
| `labeller=X appears in none of the N marks' notes` | The name does not match what the harvest wrote. Check `--labeller`. |
| `the highest pair marked as two stories now scores A and HOLDOUT_TWO_STORY_MAX declares B` | New marks, or new weights, have moved the hardest pair. Retake the constant in `backend/idhazh/contracts/knobs/placement.py`. |

`/console/judgement/` prints the newest row under the holdout panel once the
gardener has packed its day, within about two days of the date it is filed
under, and says the line has not been scored where there is none.

## The mark spelling

A mark is saved as a true or false flag, never as text. The batch file is where
a spelling can go wrong: its values are JSON booleans.

| What you see | What happened |
| --- | --- |
| A row you marked `false` arrives as `true` | The batch file quoted the value. JSON booleans, not strings. |
| Fewer rows than marks | The draw did not carry that pair. Widen `--draw-root` and harvest again. |
| `harvested 0 labelled pairs into no file` | The harvest found no label in the batches named. Nothing was saved, and the marks already on record are untouched. |

## Two things a mark is not

**It is not a verdict the fit reads.** Nothing that moves the line consumes the
marks. One verb reads them - `score-merge-line-holdout`, above, which reports how
the line stands against the marks and changes nothing. The console's holdout
panel draws the marks, scores each one against the published days it names, and
reports the gap between the highest two-story mark and the line in force
([../concepts/console-design/the-rules-every-console-chart-obeys.md](../concepts/console-design/the-rules-every-console-chart-obeys.md#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score)).

**It is not a rate over a day.** The sheet is band-stratified by construction, so
a share taken off it describes the sheet. The committed 200 are 50 well-below,
49 just-below, 51 just-above and 50 well-above; a rate about a real day has to be
weighted back to that day's own band populations.

## See also

- [../architecture/publishing/autotune-content-similarity.md](../architecture/publishing/autotune-content-similarity.md) - what the line decides, how it moves, and what the current marks say about it.
- [label-the-faithfulness-queue.md](label-the-faithfulness-queue.md) - the other labelling loop, over summaries rather than pairs.
- [run-the-pipeline.md](run-the-pipeline.md) - producing a day, and the `council-prepare` verb that writes the draw.
- [../reference/repository-layout.md](../reference/repository-layout.md) - where the marks sit under `state/`, and who writes them.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - `SimilarityHoldoutPair`, the shape of one row.
