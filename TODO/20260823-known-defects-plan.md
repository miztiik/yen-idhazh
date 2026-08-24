# Known defects

**Last Updated**: 2026-08-23

Eight defects found while shipping and re-reading the freshness, identity,
health and evaluation work. None was in that scope.

**Four defects are fixed and merged.** Defect 1 closed as row 19 (PR #18),
defect 3 as row 18 (PR #30), and defects 4 and 5 as row 20 (PR #14). Defects 2,
6, 7 and 8 stay open.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision; each row is a defect with its evidence and where the fix landed.

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 1 | The published band ignores two of its own counterweights | 2 | FIXED - PR #18 |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN** |
| 3 | `/evals` and `/console` answer the same question twice | 3 | FIXED - PR #30 |
| 4 | `EmptyDay` points at a notice that is not on the page | 1 | FIXED - PR #14 |
| 5 | The home page bakes the build date and calls it today | 2 | FIXED - PR #14 |
| 6 | Duplicate eval rows inflate the ledger | 2 | **OPEN** |
| 7 | Affiliate marketing pages pass the faithfulness bar | 3 | **OPEN** |
| 8 | Reader-facing confidence copy says too little | 2 | **OPEN** |
| 9 | The push loop loses a whole day when the tree is dirty | 2 | **OPEN** |
| 10 | The `route` job hits its 60-minute timeout every run | 3 | **OPEN** |

## 2 - The faithfulness thresholds have no labelled error rate (OPEN)

The old saturation premise is closed and false at n=156. Measured 2026-08-23 on
the committed ledger, `state/scores.csv`, the recorded `band` column says
112/19/25 (`high`/`medium`/`low`). Re-banding those same rows with today's
`band()` and today's `EvaluationConfig` gives 85/46/25, or 54.5% / 29.5% /
16.0%. Twenty-seven rows move from `high` to `medium`: 11 on lead coverage
alone, 11 on a dropped hedge alone, and 5 on both.

The threshold question is still open for four different reasons:

- There are no human labels, so no cut has a measured error rate behind it.
- The evidence base is one run. `run_id` `2026-08-23-3` owns 137 of 156 rows.
- Five source URLs appear under both committed `pipeline_fingerprint` values.
  Every one moved downward: -0.105, -0.595, -0.114, -0.079 and -0.034. That
  uniform shift points at a producer change in a way scattered noise would not.
- The recorded `band` column predates the counterweight caps and must be
  re-banded before it is read as a distribution.

Level 5 still applies. The thresholds are a reader-facing promise, so re-cutting
them needs measured label error, not a cleaner-looking bar (Rule #10).

Closing steps, in order:

1. Add the re-band utility so a stale `band` column is not mistaken for the live
   distribution. Done in this row.
2. Draw 60 human-label rows: 6 per `hhem` decile, deterministic by hash. Label
   from the summary plus source URL, with `hhem` and `band` hidden. Record one
   binary answer, "does this assert anything the article does not support?", plus
   one tag.
3. Collect at least 10 distinct run-days at one `scorer_version` and one
   `pipeline_fingerprint`.
4. Re-test the cuts by stratum against the labels.

`evaluation.spot_checks_per_week` is already 10, and the spot-check has never
run. The missing instrument is labels, not more rows.

## 6 - Duplicate eval rows inflate the ledger (OPEN)

Rows 12-15 in `state/scores.csv` are byte-identical re-observations of rows 2-4
and 6 by `output_digest` and `hhem`. That disagrees with
[evaluation.md](../docs/concepts/evaluation.md), which says an item whose inputs
did not change writes no row at all.

This is out of scope here. The likely fix belongs to the skip or append path:
when the pipeline fingerprint and published words match, the run should write no
new eval row.

## 7 - Affiliate marketing pages pass the faithfulness bar (OPEN)

Rows 100 and 101 in `state/scores.csv` are `fool.com` credit-card affiliate
landing pages in the `world` vertical. They scored 0.924 and 0.947 HHEM and
recorded `high`.

The summaries may be faithful. That is the point: no faithfulness threshold
detects this at any cut. A page of short declarative marketing sentences is easy
to entail, so raising the bar rewards the wrong source. This is a collect/extract
defect, not an evaluation-band defect.

## 8 - Reader-facing confidence copy says too little (OPEN)

Reader found two surface problems while reviewing defect 2. Do not fix them in
this row.

- The `medium` band should say what is missing rather than "mostly matches the
  source".
- The top band bar prints counts nobody can act on.

Reader's summary: "If someone re-cuts for the sake of the bar looking less
green, that is tuning a number so a chart looks humbler, which is the opposite
of honesty."

## 9 - The push loop loses a whole day when the tree is dirty (OPEN)

`digest.yml`, step `Commit the day`. The day payload is committed, then pushed.
If the push races another commit to `main`, the loop runs
`git pull --rebase --autostash origin main`. Any unstaged change in the checkout
is stashed, and if it fails to reapply, the step exits 1 and **the whole day's
work is discarded** after plan, four shards and assemble all succeeded.

Evidence: run `32671663130`, 2026-08-24. Plan and all four shards succeeded,
assemble built the day, and the step died with `error: cannot rebase: You have
unstaged changes.` The dirty file was `docs/concepts/design-system.md`, whose
blob was CRLF against a `text eol=lf` attribute, so every Linux checkout saw it
modified before the job did anything. Fixed by PR #44, which removes that
trigger.

The loop is still fragile to the next dirty file. Its own comment assumes the
opposite: "the day payload touches paths nobody edits by hand, so there is
nothing here for a rebase to conflict with". Section 1a says degrade, do not
fail; losing a day to a counter of working-tree noise is the opposite.

The day's payload is already committed by the time the rebase runs, so anything
still unstaged is noise and could be discarded before the pull. That is a
deliberate change to a production workflow that CI does not exercise, so it
needs its own consideration rather than a quiet edit.

## 10 - The `route` job hits its 60-minute timeout every run (OPEN)

`digest.yml` gives `route` `timeout-minutes: 60`. Two consecutive runs were
cancelled at exactly that bound:

| Run | `route` started | Outcome |
| --- | --- | --- |
| `32661273335` | 2026-08-23 | cancelled at the timeout |
| `32671663130` | 2026-08-24T00:26:36Z | cancelled after 60 min |

`route` carries `continue-on-error` and `assemble` runs on `always()`, so the
day still publishes - by design, a dead router must not stop publication. But a
timeout that fires every run is not a degradation any more; it is the normal
path, and it means routing and rendering never finish. Items publish without the
visuals the router would have chosen.

Two questions, and they are different: whether the 4B router is too slow for the
item count at this budget, and whether 60 minutes is the right budget. Neither
should be answered by raising the number until it stops going red (Rule #2: the
budget is the platform, not a preference).

## What closed, and where it went

| # | Defect | Fix |
| --- | --- | --- |
| 1 | `band()` read `unsupported_numbers` and the two faithfulness thresholds and nothing else; `lead_coverage` and `hedge_dropped` never reached the band a reader sees. Evidence: `ai-03` published as `high` with lead coverage 0.00. | Row 19, PR #18. One band function. A failed counterweight caps at `medium`. `evaluation.lead_coverage_min` is a `config/` knob. The open question - cap or outvote - resolved as cap. |
| 3 | Both routes rendered per-day band counts from `state/scores.csv`. Two surfaces reading one ledger disagree the first time one changes how it counts. | Row 18, PR #30. `/console` owns the band trend. `/evals/` stays as a prerendered page that links on, so a bookmark still works without JavaScript (`CLAUDE.md` section 3 keeps the route). |
| 4 | `EmptyDay.svelte` told the reader "the run notice above says which it was" while rendering with nothing above it. | Row 20, PR #14. The copy now names only what a reader can see. |
| 5 | `+page.server.ts` computed `new Date()` and every route is prerendered, so the build date was frozen into the HTML and called today. It also passed `latest={null}`, suppressing the one link that would rescue the reader. | Row 20, PR #14. The date comes from the payload the page renders. The latest-day link is restored. |

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what the bands claim.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the surfaces in 3, 4 and 5.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - what happens to this file when a row closes.
