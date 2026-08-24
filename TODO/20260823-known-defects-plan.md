# Known defects

**Last Updated**: 2026-08-24

Twelve defects found while shipping and re-reading the freshness, identity,
health and evaluation work. None was in that scope. Defects 11 and 12 were found
by running the gates and by opening the published day in a browser, not by
reading code.

**Ten are closed.** Defect 8 is closed on the item copy and on the day's band
bar. Defect 2 has its instrument built and is waiting on human labels and
calendar time, which no amount of engineering closes.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision; each row is a defect with its evidence and where the fix landed.

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 1 | The published band ignores two of its own counterweights | 2 | FIXED - PR #18 |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **INSTRUMENT BUILT - 0 of 60 labels, 1 of 10 run-days** |
| 3 | `/evals` and `/console` answer the same question twice | 3 | FIXED - PR #30 |
| 4 | `EmptyDay` points at a notice that is not on the page | 1 | FIXED - PR #14 |
| 5 | The home page bakes the build date and calls it today | 2 | FIXED - PR #14 |
| 6 | Duplicate eval rows inflate the ledger | 2 | FIXED - 2026-08-24 |
| 7 | Affiliate marketing pages pass the faithfulness bar | 3 | FIXED - 2026-08-24 |
| 8 | Reader-facing confidence copy says too little | 2 | **PARTLY FIXED - the band bar is open** |
| 9 | The push loop loses a whole day when the tree is dirty | 2 | FIXED - 2026-08-24 |
| 10 | The `route` job hits its 60-minute timeout | 3 | FIXED - 2026-08-24 |
| 11 | A second run of a day overwrites the first run's charts | 3 | FIXED - 2026-08-24 |
| 12 | One quantity could fill three bars of a published chart | 2 | FIXED - 2026-08-24 |

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
- Five source URLs appear under both committed `pipeline_fingerprint` values.
  Every one moved downward: -0.105, -0.595, -0.114, -0.079 and -0.034. That
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
   `pipeline_fingerprint`. **1 of 10.** Measured 2026-08-24: 731 eligible rows,
   all on `2026-08-24`, all under fingerprint `969b1917...d2b945`, at scorer
   `hhem-2.1-open@6a30c896;weights-cffb0b41;metrics-3;bands=0.80/0.50;lead=0.30`.
4. Label the 60 rows. **0 of 60.** Human work. No AI judge, and the contract has
   nowhere to put one.
5. Re-test the cuts by stratum against the labels.

**This row cannot close on engineering.** Steps 3 and 4 are a human prerequisite
and a calendar prerequisite. Anyone reading this later: the instrument is built
and nothing about it entitles a threshold to move.

One risk worth surfacing now. The pipeline fingerprint moved at least twice in
three days, so ten consecutive days under one fingerprint may be unreachable
while the pipeline is under active change. The falsifiable relaxation is "10
run-days at one `scorer_version`, with `pipeline_fingerprint` recorded per row and
reported as a stratum" - the threshold belongs to the scorer, and a producer
change is a covariate rather than a disqualification. That would change this
plan's text, so it is the owner's call.

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

## 9 - The push loop loses a whole day when the tree is dirty (FIXED)

`digest.yml`, steps `Commit what the plan saw` and `Commit the day`. The work is
committed, then pushed. If the push races another commit to `main`, the loop ran
`git pull --rebase --autostash origin main`. Any unstaged change in the checkout
is stashed, and if it fails to reapply, the step exits 1 and **the whole day's
work is discarded** after plan, four shards and assemble all succeeded.

Evidence: run `32671663130`, 2026-08-24. Plan and all four shards succeeded,
assemble built the day, and the step died with `error: cannot rebase: You have
unstaged changes.` The dirty file was `docs/concepts/design-system.md`, whose
blob was CRLF against a `text eol=lf` attribute, so every Linux checkout saw it
modified before the job did anything. PR #44 removed that trigger; this row
removes the class.

Both loops were fixed, not only the one that failed. The plan job's loop has the
same shape and loses the sight and health ledgers when it hits it.

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

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what the bands claim.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the surfaces in 3, 4 and 5.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - what happens to this file when a row closes.
