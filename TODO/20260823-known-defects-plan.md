# Known defects - one open

**Last Updated**: 2026-08-23

Five defects found while shipping the freshness, identity and health set on
2026-08-22. None was in that scope.

**Four of the five are now fixed and merged.** Defect 1 closed as row 19
(PR #18), defect 3 as row 18 (PR #30), and defects 4 and 5 as row 20 (PR #14).
Defect 2 stays open.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision; each row is a defect with its evidence and where the fix landed.

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 1 | The published band ignores two of its own counterweights | 2 | FIXED - PR #18 |
| 2 | The faithfulness bands are saturated | 5 | **OPEN** |
| 3 | `/evals` and `/console` answer the same question twice | 3 | FIXED - PR #30 |
| 4 | `EmptyDay` points at a notice that is not on the page | 1 | FIXED - PR #14 |
| 5 | The home page bakes the build date and calls it today | 2 | FIXED - PR #14 |

## 2 - The faithfulness bands are saturated (OPEN)

Measured 2026-08-23 on the committed ledger, `state/scores.csv`: 19 rows, **all
nineteen band `high`**, observed `hhem` range 0.9225 to 0.9784 against a
`band_high_min` far below it. A classifier with one class is not classifying,
and the confidence signal on the page is currently decoration.

Level 5: the thresholds are a reader-facing promise, so re-cutting them is a
design consultation, not an edit. It also needs more rows than nineteen before
any new cut is honest (Rule #10).

**Row 19 fixed the half that was a bug** without touching the thresholds. A
summary with zero lead coverage can no longer publish as `high`: `band()`
absorbed `counterweight_band()`, and a failed counterweight now caps the band at
`medium` rather than forcing `low`. Re-banding the 19 committed rows moved four
of them from `high` to `medium` (`ai-03` and `ai-04`, twice each). The
thresholds themselves still need evidence this project does not have yet.

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
