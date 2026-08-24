# Known defects

**Last Updated**: 2026-08-24

Ten defects found while shipping and re-reading the freshness, identity, health
and evaluation work. None was in that scope.

**Seven are closed.** Defect 8 is closed on the item copy and open on the day's
band bar. Defect 10 now has the instrument it was missing and keeps its number.
Defect 2 is a Level 5 consultation, not a task.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision; each row is a defect with its evidence and where the fix landed.

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 1 | The published band ignores two of its own counterweights | 2 | FIXED - PR #18 |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - consultation** |
| 3 | `/evals` and `/console` answer the same question twice | 3 | FIXED - PR #30 |
| 4 | `EmptyDay` points at a notice that is not on the page | 1 | FIXED - PR #14 |
| 5 | The home page bakes the build date and calls it today | 2 | FIXED - PR #14 |
| 6 | Duplicate eval rows inflate the ledger | 2 | FIXED - 2026-08-24 |
| 7 | Affiliate marketing pages pass the faithfulness bar | 3 | FIXED - 2026-08-24 |
| 8 | Reader-facing confidence copy says too little | 2 | **PARTLY FIXED - the band bar is open** |
| 9 | The push loop loses a whole day when the tree is dirty | 2 | FIXED - 2026-08-24 |
| 10 | The `route` job hits its 60-minute timeout every run | 3 | **INSTRUMENTED - awaiting rows** |

## 2 - The faithfulness thresholds have no labelled error rate (OPEN)

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
   one tag. **This mints a new persisted surface and needs sign-off before it is
   built (Rule #3, section 6).**
3. Collect at least 10 distinct run-days at one `scorer_version` and one
   `pipeline_fingerprint`.
4. Re-test the cuts by stratum against the labels.

`evaluation.spot_checks_per_week` is already 10, and the spot-check has never
run. The missing instrument is labels, not more rows.

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

## 10 - The `route` job hits its 60-minute timeout every run (INSTRUMENTED)

`digest.yml` gives `route` `timeout-minutes: 60`. It sits close to that bound and
has crossed it twice:

| Run | `route` | Outcome |
| --- | --- | --- |
| `32661273335` | 2026-08-23 | cancelled at the timeout |
| `32671663130` | 2026-08-24T00:26:36Z | cancelled after 60 min |
| `32701966659` | 2026-08-24T09:24:36Z -> 10:15:50Z | **succeeded in 51 min** |

The third run corrects the first reading of this defect. It is not "the timeout
fires every run"; it is "the job finishes at 51 to 60+ minutes against a 60
minute bound", so whether a day gets its visuals depends on which side of the
line that run lands. Three observations, one model, no controlled variable -
this is a symptom, not yet a measurement.

`route` carries `continue-on-error` and `assemble` runs on `always()`, so the
day publishes either way - by design, a dead router must not stop publication.
The cost of a crossing is silent: items publish without the visuals the router
would have chosen, and nothing on the page says so.

Three questions, and they are different: what actually drives the spread (item
count? article length? a slow first load?), whether the 4B router is too slow
for the item count at this budget, and whether 60 minutes is the right budget.
None should be answered by raising the number until it stops going red (Rule #2:
the budget is the platform, not a preference).

**The instrument now exists and the number has not moved.** Every committed run
manifest carries `items_routed` and `route_ms`. Read `route_ms` against the job's
own wall-clock in the Actions log: a stage total far below the job total says the
fixed cost is what sits near the bound, not the model. Revisit when several days
of manifests exist ([`docs/reference/measurements.md`](../docs/reference/measurements.md)).

## What closed, and where it went

| # | Defect | Fix |
| --- | --- | --- |
| 1 | `band()` read `unsupported_numbers` and the two faithfulness thresholds and nothing else; `lead_coverage` and `hedge_dropped` never reached the band a reader sees. Evidence: `ai-03` published as `high` with lead coverage 0.00. | Row 19, PR #18. One band function. A failed counterweight caps at `medium`. `evaluation.lead_coverage_min` is a `config/` knob. The open question - cap or outvote - resolved as cap. |
| 3 | Both routes rendered per-day band counts from `state/scores.csv`. Two surfaces reading one ledger disagree the first time one changes how it counts. | Row 18, PR #30. `/console` owns the band trend. `/evals/` stays as a prerendered page that links on, so a bookmark still works without JavaScript (`CLAUDE.md` section 3 keeps the route). |
| 4 | `EmptyDay.svelte` told the reader "the run notice above says which it was" while rendering with nothing above it. | Row 20, PR #14. The copy now names only what a reader can see. |
| 5 | `+page.server.ts` computed `new Date()` and every route is prerendered, so the build date was frozen into the HTML and called today. It also passed `latest={null}`, suppressing the one link that would rescue the reader. | Row 20, PR #14. The date comes from the payload the page renders. The latest-day link is restored. |
| 6 | The eval writer appended every row a run handed it. Four rows on 2026-08-23 are byte-identical re-observations of items the day before, because `state/published.csv` had no record of 2026-08-22 and the next run re-summarized them. The doc had always said an item whose inputs did not change writes no row at all. | 2026-08-24. The writer refuses a row whose address, pipeline fingerprint, output digest and scorer version all match a row already in the file, and de-duplicates inside one batch as well. The four historical rows stay: they are honest history, and rewriting an append-only ledger to tidy a denominator is the band-aid. Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 7 | `cnn-world` syndicated three `fool.com/the-ascent/` affiliate credit-card pages into the `world` vertical. They scored 0.92 to 0.95 and published as `high`, because short declarative marketing prose is trivially entailed. | 2026-08-24. `collect.blocked_url_markers`, a config-driven list of case-insensitive address substrings that never enter the pool. Default empty; the entry `fool.com/the-ascent/` lives in `config/idhazh.json`. Applied after the feed-health row is written, so what a feed offered and what the pool accepted stay separate facts. Recorded in [`docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md). |
| 8 | `medium` printed "Mostly matches the source" - a grade a reader can do nothing with. Both things that cap an item at `medium` were computed and neither reached the page. | 2026-08-24. `score.verdict()` returns the band and the one reason together; `band()` is a wrapper with no logic. `DigestItem.band_reason` is a closed identifier and the site owns the sentence. A day published before this renders exactly as it did. Browser-smoked at 420px across `/`, a day, a vertical, the archive and the empty state. |
| 9 | Both commit steps in `digest.yml` ran `git pull --rebase --autostash`. A rebase will not start on a dirty tree, and run `32671663130` lost a finished day to one CRLF file. | 2026-08-24. Each loop prints what is dirty and discards it before the rebase; untracked files are left alone; `--autostash` is gone. A workflow contract test pins the shape in both jobs. CI does not run `digest.yml`, so the next change there still needs a dispatched run. |
| 10 | `route` lands between 51 and 60+ minutes against a 60-minute bound, and nothing recorded what it spent. | 2026-08-24, instrumented not closed. `Route.route_ms` per item; `RunRecord.items_routed` and `RunRecord.route_ms` on every committed manifest. `route_ms` is null when the router never ran, which is not zero. The number stays at 60 until several days of manifests exist (Rule #2). |

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what the bands claim.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the surfaces in 3, 4 and 5.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - what happens to this file when a row closes.
