# Handover: the confidence band has never been checked against a person

**Last Updated**: 2026-08-28

Defect 2 of [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md) is
the only open row in that file, and it is the last thing standing between the
published site and a claim it can support. This handover states the problem, the
verified facts, and the options. It does not choose between the open ones.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision except where it says the owner already made one.

## The problem, in the reader's words

Every published item carries a confidence chip. The site says:

> Every summary is checked against the article it came from. Where the check
> went badly, the item says so.

and stamps each item **"Matches the source"** or **"Mostly matches the source"**
(`frontend/src/lib/bands.ts`).

**No part of that promise has been checked against a human.** A cross-encoder
gives each summary a number, `score.verdict()` cuts it at 0.80 and 0.50, and the
site prints a phrase in English that a reader will act on. Nobody has ever
established that items above 0.80 match their source more often than items
below it. The cut could sit at 0.60 or 0.95 and every page would look equally
confident.

This is a Rule #10 problem on the surface a reader actually sees: an unmeasured
number is justifying a design, and the design is a sentence we tell strangers.

Three defects closed on 2026-08-27 were the same shape one layer down - a column
that looked like a measurement and was not. `hhem_delta` read exactly 0.0 on
2,232 of 2,232 rows because the scorer was handed one string twice. A column
pair read as a truncation rate was two different counters on one string, wrong
by a factor of fourteen. Both were found by measuring rather than by reading.
The band is the same risk at the reader-facing end and has not been measured.

## What answering it buys

One of three outcomes, and all three are worth having.

| Outcome | What follows |
| --- | --- |
| 0.80 separates well | The promise stands, and for the first time something backs it |
| 0.80 is too generous | Move the cut, or soften the copy. Readers stop being told "matches the source" about summaries that do not |
| The score does not separate at all | **Delete the chip.** A label that means nothing is worse than no label |

The third cannot currently be ruled out. That is the argument for doing the work.

## Verified facts, 2026-08-28

Re-verify each one before building on it. Numbers in this repository go stale in
days, and every claim below has a command next to it for that reason.

| Fact | How to re-check |
| --- | --- |
| The counting rule is settled: run-days count at one `scorer_version`, and `pipeline_fingerprint` is a reported stratum. **Owner decision, 2026-08-27, shipped in PR #190.** | `git log --oneline --grep="Calibrate at one scorer"` |
| 450 eligible rows, 2 of 10 run-days, and the draw fills **60 of 60** with no decile short | `python backend/utilities/label_queue.py` |
| **0 labels.** No `state/labels.csv` is committed | `git ls-files state/labels.csv` |
| **Nothing reads a label.** `LabelRow` is touched only by its contract, the schema export, the draw, the recording CLI and tests | `git grep -l LabelRow -- backend frontend/src` |
| 26 of the 60 drawn rows predate the `source_digest` column and can never be proved against their article | the `labellable` line of the same tool |
| Evidence artifacts exist and are downloadable: 4 shards, about 315 KB, `retention-days: 14` | `gh api repos/miztiik/yen-idhazh/actions/runs/<id>/artifacts` |

## The gap

The instrument is built at both ends and hollow in the middle.

| Step | State |
| --- | --- |
| Draw a stratified, order-safe, deterministic sample | Built. `labels.draw()` |
| Show a person the evidence with the score hidden | Built. `label_queue.py --label` |
| Record verdicts in a typed append-only ledger | Built. `labels.append()` |
| **Read those verdicts and say whether 0.80 is right** | **Does not exist** |
| 60 labellable rows in front of it | 34 today, and none of them local |

Every function in `backend/idhazh/evals/labels.py` produces labels - `draw`,
`shortfalls`, `append`, `recorded`. None consumes one. A previous session
described the analysis as if it were runnable; it is not, and that error is
recorded here so the next agent does not inherit it.

## What a person is asked to do

Not automated, and it may not be. CLAUDE.md section 0a forbids an LLM judge: a
model that shares the failure modes of the thing it judges is not a measurement.

`python backend/utilities/label_queue.py --label --labeller <name>` shows one
article and one summary at a time with the score, the band, the counterweights,
the model identity and the running tally hidden. The person answers one
question - *does this summary assert anything the article does not support?* -
and tags an unsupported verdict as `invented_fact`, `wrong_number` or
`overstated`. Each tag names a defect with a different fix.

The row lands in `state/labels.csv` beside `hhem_at_label` and `band_at_label`.
**That pairing is the measurement.** Sixty rows of "the machine said high, the
person said unsupported" is the only thing that can locate the cut.

## Options

### Decided already

**The counting rule.** Run-days count at one `scorer_version`; the pipeline
fingerprint is reported per stratum, and a stratum under
`evaluation.label_min_stratum_rows` may not move a threshold. Owner decision,
2026-08-27. The rejected alternative - freeze the pipeline for ten days - was
declined because the claim it buys expires at the next prompt change. Recorded
in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).
**Do not reopen this without the owner.**

### Open: what to do about the hollow middle

**Option 1 - build the analysis first, then label.** Write the consumer of
`state/labels.csv`: verdict against band per stratum, the error rate of each
band, and what each candidate cut would cost. It is testable today against
synthetic labels, before a single real one exists, so it does not wait on
anybody. Then the labelling is roughly ninety minutes of one person's time and
it buys an answer.

- Cost: one Level-3 change, plus tests. No new persisted contract - `LabelRow`
  already carries everything the analysis reads.
- Risk: the analysis is written before anyone has seen a real label, so its
  output shape may need one revision.
- This is the recommended order. Labelling into a ledger nothing reads risks
  spending a person's attention on a sample a later draw supersedes.

**Option 2 - label first, analyse by hand.** Download the evidence, label the 34
labellable rows, and read the result off a spreadsheet.

- Cost: nothing to build.
- Risk: 34 is not 60 and the deciles will be uneven, so the result is weaker
  than the draw was designed to give. A hand analysis is also not reproducible,
  which is the thing `docs/` exists to prevent.

**Option 3 - soften the copy and stop making the claim.** Change the chip to say
what was actually measured rather than "matches the source", and drop the
"every summary is checked" sentence until something backs it.

- Cost: one frontend change plus a browser smoke (CLAUDE.md section 12).
- Buys: the unverified claim goes away today, for free.
- Loses: the reader also loses a signal that may well be a good one. This is a
  retreat, not a measurement, and it should be labelled as one wherever it lands.
- Level 5 either way, because the chip is a reader-facing promise.

**Option 4 - delete the chip.** Only defensible once measured. Do not take this
one on suspicion; that would be replacing an unmeasured claim with an unmeasured
retraction.

Options 1 and 3 are not exclusive. Softening the copy while the measurement is
built is the conservative combination, and it is what a reader would ask for.

## Practical notes for whoever picks this up

- **Read `docs/reference/agent-notes.md` before improvising any shell or git
  trick.** It is long and it has already caught several traps in this area.
- **Download the evidence before labelling.** `gh run download <runId> --repo
  miztiik/yen-idhazh --name evidence-<shard> --dir backend/var/evidence/<date>/`.
  Four shards per run. `retention-days: 14`, so a run older than a fortnight is
  gone and its rows can never be labelled.
- **The 26 unlabellable rows are permanent.** They were scored before
  `source_digest` existed, so nothing can prove which article text the scorer
  read. Do not fill them in by guessing; the whole point of the digest is that a
  disagreement measures scorer error and not a premise mismatch.
- **Every new row is labellable.** `source_digest` has been written on every row
  since 2026-08-27, so the pool improves on its own with each published day.
- **Adding a field to any contract model breaks
  `test_contracts.py::test_fixture_round_trips_byte_identically`**, because
  `to_json` dumps every field and the committed fixture does not carry the new
  key. Add it to the fixture in canonical sorted-key order in the same commit.
  Ruff, mypy and the targeted module all pass without it; only the full suite
  catches it.
- **`METRICS_VERSION` and the band values live inside `scorer_version`.** Moving
  a threshold mints a new scorer version and restarts the run-day count. That is
  correct and deliberate: a cut cannot move halfway through a collection.

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the calibration contract, the settled counting rule, and what a pooled draw gives up.
- [`docs/how-to/label-the-faithfulness-queue.md`](../docs/how-to/label-the-faithfulness-queue.md) - the operator procedure.
- [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md) - defect 2, the row this handover serves.
- [`docs/reference/agent-notes.md`](../docs/reference/agent-notes.md) - the traps that make a command lie.
