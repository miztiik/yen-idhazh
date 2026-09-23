# Label the Similarity Holdout

**Last Updated**: 2026-09-21

Read pairs of articles the merge line has to decide between, and record whether
each pair is one news event or two. The marks land in
`state/content-similarity-judge/holdout-pairs.csv`, which is the fixed floor every fitted
merge line has to stay above.

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
rests on one story rather than on a spread of news.

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
score. **Point it at all of them, not at one day.** The harvest joins on the
whole population it can resolve, and a mark whose pair is not in the draw you
hand it is a mark that does not reach the file.

## Draw a sheet

Read-only apart from the two files it writes. It calls no model and opens no
socket:

```powershell
python backend/utilities/sample_sheet.py --draw-root backend/var/council --line 0.94
```

| Flag | Default | What it is |
| --- | --- | --- |
| `--draw-root` | required | The tree of drawn-pair CSVs to read. |
| `--line` | required | The merge line the bands are measured against. `assemble.same_story.floor_min` is what a day was grouped at unless a fit has moved it. |
| `--digest-root` | `frontend/public/digest` | Where the published days are, so a pair's two articles can be resolved to a title and a summary. |
| `--out` | `test-results/similarity-pairs-to-label` | Where `pairs.json` and `pairs.md` are written. Refused inside `frontend/public/` or `frontend/build/`, because the sheet quotes untrusted text and a published one would put it on the site. |
| `--corridor` | `0.02` | How wide either side of the line counts as "just". |
| `--total` | `200` | How many pairs the sheet carries. |
| `--harvest` | unset | Switches to harvest mode; see below. |
| `--labeller` | unset | Required with `--harvest`. |
| `--labelled-on` | unset | Required with `--harvest`. |

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
  --harvest state/content-similarity-judge/holdout-pairs.csv `
  --labeller claude-opus-4.6 --labelled-on 2026-09-19
```

`--labelled-on` fills both `version` and `marked_on`. `--labeller` reaches the
`note` column with the pair's score beside it, because a mark is worth what its
labeller is worth and a row that does not say cannot be argued with later.

**The join is on `pair_key`, against the whole drawn population and never
against the sheet in hand.** A mark belongs to a pair, not to a slot: harvesting
from the sheet meant that re-drawing it, or changing how pairs are chosen,
silently dropped every mark whose pair no longer made the cut - one selection
change turned 200 labelled pairs into 129. The benchmark accumulates instead.

**The harvest writes the whole file, so check what came out before you keep it.**
It is a rewrite and not an append, and with no labels at all it writes an empty
file. Harvest to a scratch path first and diff it against the committed one
unless the draw you handed it covers every mark already on record.

It prints what landed, and what did not:

```text
INFO:idhazh:sample_sheet harvested 200 labelled pairs to
state/content-similarity-judge/holdout-pairs.csv, 0 labels matched no drawn pair
```

A non-zero tail count means a `pair_key` in a batch file is not in this draw.
Widen `--draw-root` rather than editing the batch.

## Score the line against them

```powershell
python -m idhazh score-merge-line-holdout --date 2026-09-21 `
  --run-id 2026-09-21-35534060762 --labeller claude-opus-4.6
```

It counts what the merge line in force does to every marked pair and writes one
row into
`state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv`:
the line, the four cells, how many pairs it could not score, and how many marks
say two stories. `--labeller` is the same name the harvest was given, and
`--run-id` is `<date>-<a number>` - the row has to say which run took the
reading.

**Nothing schedules it.** The marked file changes when somebody labels more
pairs rather than when a day publishes, so no workflow runs this verb and no job
stages what it writes. Commit the row yourself, the way you commit the marks.

**It writes nothing when fewer than half the marks can be scored.** Retention
deletes published days the marked file still names, and four cells counted over
a handful of surviving pairs read as a line that got almost everything right.
The verb exits 1 and prints how many it resolved.

| What you see | What happened |
| --- | --- |
| `resolved N of M marked pairs, and a reading means nothing below K` | Retention has taken the days most marks name. Nothing to fix in the file; the comparison has aged out. |
| `labeller=X appears in none of the N marks' notes` | The name does not match what the harvest wrote. Check `--labeller`. |
| `the highest pair marked as two stories now scores A and HOLDOUT_TWO_STORY_MAX declares B` | New marks, or new weights, have moved the hardest pair. Retake the constant in `backend/idhazh/contracts/knobs/placement.py`. |

`/console/judgement/` prints the newest row under the holdout panel, and says
the line has not been scored where there is none.

## The mark spelling

The harvest writes `true` and `false`. The reader accepts any case and any
surrounding space, and **refuses any other spelling rather than reading it as
false** - comparing against one spelling would read every other spelling as
`false`, which is the load-bearing mark, and a file read that way becomes all
two-story pairs and a floor that refuses every merge without erroring.

| What you see | What happened |
| --- | --- |
| `same_story is 'yes', and a mark has to be one of ['false', 'true']` | A hand edit used a spelling the reader does not know. Write `true` or `false`. |
| A row you marked `false` arrives as `true` | The batch file quoted the value. JSON booleans, not strings. |
| Fewer rows than marks | The draw did not carry that pair. Widen `--draw-root` and harvest again. |
| An empty file | The harvest found no labels. It writes the whole file, so restore it from git. |

## Two things a mark is not

**It is not a verdict the fit reads.** Nothing that moves the line consumes this
file. One verb reads it - `score-merge-line-holdout`, above, which reports how
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
- [../reference/repository-layout.md](../reference/repository-layout.md) - why the holdout file is one of two committed `state/` files nothing generated.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - `SimilarityHoldoutPair`, the shape of one row.
