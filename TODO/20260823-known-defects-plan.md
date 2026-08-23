# Known defects - open

**Last Updated**: 2026-08-23

Five defects found while shipping the freshness, identity and health set on
2026-08-22. None was in that scope. Each was re-checked against the tree on
2026-08-23 and still holds unless noted.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision; each row is a defect with its evidence and where the fix would land.

**Four of the five now have fix rows** in
[`20260823-item-telemetry-and-brief-tier-plan.md`](20260823-item-telemetry-and-brief-tier-plan.md):
defect 1 is its row 19, defect 3 is row 18, and defects 4 and 5 are row 20.

**Defect 2 stays here and is deliberately not scheduled.** Re-cutting a
reader-facing threshold is Level 5, and the ledger holds 19 rows. Row 19 fixes
the half that is a bug - a summary with zero lead coverage can no longer publish
as `high` - without touching the thresholds, which need evidence this project
does not have yet (Rule #10).

| # | Defect | Level | Where |
| --- | --- | --- | --- |
| 1 | The published band ignores two of its own counterweights | 2 | `backend/idhazh/evals/score.py` |
| 2 | The faithfulness bands are saturated | 5 | `config/idhazh.json`, `docs/concepts/evaluation.md` |
| 3 | `/evals` and `/console` answer the same question twice | 3 | `frontend/src/routes/` |
| 4 | `EmptyDay` points at a notice that is not on the page | 1 | `frontend/src/lib/components/EmptyDay.svelte` |
| 5 | The home page bakes the build date and calls it today | 2 | `frontend/src/routes/+page.server.ts` |

## 1 - The published band ignores two of its own counterweights

`band()` checks `unsupported_numbers` and the two faithfulness thresholds and
nothing else. `lead_coverage` and `hedge_dropped` are measured, written to the
eval row, and never reach the band a reader sees. `counterweight_band()` does
read them, but `cli.py` only calls it when no eval row exists.

Evidence: `ai-03` published as `high` with lead coverage 0.00.

Open question: whether a low counterweight should outvote a high faithfulness
score, or only cap it at `medium`. Item 1 cannot be settled without item 2.

## 2 - The faithfulness bands are saturated

Measured 2026-08-23 on the committed ledger, `state/scores.csv`: 10 rows, **all
ten band `high`**, observed `hhem` range 0.9225 to 0.9784 against a
`band_high_min` far below it. A classifier with one class is not classifying,
and the confidence signal on the page is currently decoration.

Level 5: the thresholds are a reader-facing promise, so re-cutting them is a
design consultation, not an edit. It also needs more rows than ten before any
new cut is honest (Rule #10).

## 3 - `/evals` and `/console` answer the same question twice

Both routes render per-day band counts from `state/scores.csv`. Two surfaces
reading one ledger will disagree the first time one of them changes how it
counts. Needs a ruling on which surface owns the band trend before either is
touched.

## 4 - `EmptyDay` points at a notice that is not on the page

`EmptyDay.svelte` tells the reader "the run notice above says which it was". On
the home page it is rendered with nothing above it, so the sentence points at
empty space - the exact moment a reader is deciding whether the site is broken.

## 5 - The home page bakes the build date and calls it today

`+page.server.ts` computes `new Date()`, and every route is prerendered
(`+layout.server.ts`), so the value is frozen into the HTML at build time. A day
after a deploy with no new run, the home page reads "Nothing was published for
*the build date*" - a date that is not today.

It also passes `latest={null}`, which suppresses the one link that would rescue
the reader. The archive link still renders.

This supersedes the older form of this defect ("the home page renders the latest
day, not today"). The code changed underneath it; the failure moved rather than
closing.

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what the bands claim.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the surfaces in 3, 4 and 5.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - what happens to this file when a row closes.
