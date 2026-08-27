# Known defects

**Last Updated**: 2026-08-27

Two defects remain open. Defect 2 still needs engineering work before a person
can label it: the queue does not carry the evidence the labeller must judge,
leaks the score stratum through its order, and can mix pipeline fingerprints.
It then needs 60 human labels and 10 run-days under one scorer and one pipeline
fingerprint. Defect 15 loses the difference between a missing timing and a real
zero inside the frontend loader, although the chart avoids making a false claim
from that loss today.

Closed rows were removed on 2026-08-27 after checking their current production
code, regression tests and canonical docs. Git history holds their execution
record; the living docs hold the rules they established.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Rule #4).

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - QUEUE INCOMPLETE; 0 of 60 labels; 0 of 10 current-pipeline run-days, and 10 has never been reached** |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 4 | **OPEN - no current reader-facing symptom** |

## 2 - The faithfulness thresholds have no labelled error rate (OPEN)

No current threshold has a measured human error rate. Re-cutting the bands is a
Level-5 reader-facing decision, so no threshold moves until the evidence exists
(Rule #10).

The label contract, deterministic decile draw and human-paced CLI exist in
`backend/idhazh/contracts/label_row.py`, `backend/idhazh/evals/labels.py` and
`backend/utilities/label_queue.py`. The queue is not ready for labelling:

- `state/scores.csv` carries neither the exact summary nor the extracted source
  text. The CLI prints a missing-summary fallback and never shows the article
  the verdict must judge.
- `labels.draw()` returns one decile after another. That order exposes the score
  stratum even though the score itself is hidden.
- `labels.eligible()` filters on `scorer_version` only. It can mix pipeline
  fingerprints while the current collection rule requires one fixed pair.

Measured 2026-08-27 from the committed ledger and current code: no
`state/labels.csv` is committed, so the label count is 0. The active scorer is
`hhem-2.1-open@8e4a2e6e;weights-841b70e0;metrics-3;bands=0.80/0.50;lead=0.30`.
The latest 116 score rows use that scorer with the retired Qwen3-8B summarizer.
The current config uses Qwen3.5-9B, and the summarizer weight digest is part of
the pipeline fingerprint. No committed run-day therefore belongs to the
current scorer and current pipeline together.

Closing steps, in order:

1. Join the draw to a frozen local evidence package containing the exact source
   and summary text plus the source digest. Keep article bodies local and
   uncommitted.
2. Globally shuffle the selected rows and select one pipeline fingerprint. A
   proposal to mix fingerprints as reported strata changes the calibration
   rule and needs owner approval.
3. Draw and label 60 rows, six per HHEM decile. Keep the score, band,
   counterweights, model identity, fingerprint and running tally hidden.
4. Collect 10 distinct run-days under one `scorer_version` and one
   `pipeline_fingerprint`. **Ten has never been reached.** Over the same ledger,
   the longest run of consecutive run-days under a single pair is 3 -
   `2026-08-24` to `2026-08-26`, under fingerprint `969b1917...d2b945` - and the
   stamp has moved four times across the five scored run-days the ledger holds.
   So this step is not a waiting period, and it does not close on its own. The
   reset mechanism, the measured rate and the two ways out are stated once, in
   [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).
5. Re-test the cuts by stratum. Move a threshold only when the labels support
   the new cut.

The canonical measurement contract and the current implementation gaps live in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md).

## 15 - Missing and zero stage timings collapse together (OPEN)

`frontend/src/routes/console/+page.server.ts` returns `0` when `median()` gets
an empty sample. All four stage timing fields therefore lose the difference
between "not measured" and "measured as zero" before the chart sees them.

No reader-facing false statement remains today. `StageTimings.svelte` treats a
non-positive value as a gap and says when no time was recorded. That repair
reconstructs absence from the value; it does not preserve the fact.

The structural fix is still Level 4:

1. Make `median()` return `null` for an empty sample.
2. Change `StageTimingDay` in `frontend/src/lib/charts/series.ts` to carry
   `number | null` for all four stages.
3. Preserve null through `frontend/src/routes/console/+page.server.ts` and read
   it directly in `frontend/src/lib/components/StageTimings.svelte`.
4. Pin both a missing timing and a real zero in
   `frontend/tests/console.spec.ts`.
5. Update the stage-timing contract in
   [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md).

This is not a persisted-contract migration. `StageTimingDay` is a hand-written
prerender input, not a Pydantic model or a committed payload.

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the label and calibration contract.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console timing surface.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - how closed rows leave this file.
