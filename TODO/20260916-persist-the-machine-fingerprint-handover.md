# Persist the machine fingerprint, and finish judging the two candidate models

**Last Updated**: 2026-09-17

**Closed.** Every row this file opened on 2026-09-16 has landed, been ruled on, or
been declined by the owner. It is the record of what happened, not a queue of
work. Two questions are still open and each one says so below.

**This is not where to look up how any of it works now.** `docs/` is the memory
(CLAUDE.md Guardrail #4); every row below names the page that owns its facts. What
this page keeps is the sequence and the rulings - who decided what, on which day,
and for what reason.

## What was wrong

Every job in `digest.yml` measured the machine it drew and wrote a row into
`state/host-fingerprint/<YYYY>/<MM>/<DD>.csv`. No commit step named that path, so
the row went to the bin with the runner: `git ls-files state/host-fingerprint*`
returned nothing at all. The instrument reported success, the log line printed the
machine, and the store stayed empty. `state/span-rollup` had failed the same way
for nine days, and the guard written after it could not see this one, because it
was scoped to one source file.

## What landed

| Row | What it asked for | What happened | Where it lives now |
| --- | --- | --- | --- |
| R1a | The work job must stage the ledger it writes | Landed 2026-09-16. `state/host-fingerprint` is in the work job's `commit-and-push.sh` call, a header-only day file is committed so `git add` under `set -euo pipefail` cannot abort the step on a fresh clone, and assemble's refresh set names the path | [`docs/reference/host-metrics.md`](../docs/reference/host-metrics.md) |
| R1b | `dedupe-ledgers` must settle it | Landed 2026-09-16. `state/host-fingerprint` and `state/span-rollup` both joined `ledger.keyed_paths`. A job runs on one machine, so two rows under one `(date, run_id, job, shard)` are one machine written down twice | [`docs/concepts/telemetry.md`](../docs/concepts/telemetry.md) |
| R1c | Only the `work` job recorded anything | Landed 2026-09-17, and the answer was every job rather than the two that run a model: `plan`, `work` and `assemble` each probe, and each stages the row. A run is only as fast as its slowest job, and until that day the two jobs either side cost time nobody could attribute. `ServerJob` now holds `plan`, `work`, `assemble`, `visuals` and `runtime` | [`docs/reference/host-metrics.md`](../docs/reference/host-metrics.md) |
| The parity test | A test that reads the ledger side and the staging side, derived rather than hand-written | Landed 2026-09-16 as [`backend/tests/workflows/test_ledger_staging.py`](../backend/tests/workflows/test_ledger_staging.py), and finished on 2026-09-17: the three hand-written lists that preceded it were deleted, and the trace sink they covered is derived too. A store is filled by an `append_*` call or by a file sink opened on its own path helper; both count, because both die with the runner | [`docs/reference/github-actions.md`](../docs/reference/github-actions.md) |
| R2 | `measure.yml` must record its machine, under `state/pipeline-tests/` | Landed 2026-09-17. The `runtime` job probes, and `measure.yml` pushes for the first time - one row under `state/pipeline-tests/host-fingerprint/`, with the permission raised on that one job rather than at workflow level. The split was the owner's, 2026-09-16: bench rows beside production rows would mean every console panel filtering by job for ever | [`docs/reference/host-metrics.md`](../docs/reference/host-metrics.md), [`docs/reference/github-actions.md`](../docs/reference/github-actions.md) |
| R4 | Read the three outstanding bench draws and record them | Landed 2026-09-16. All four dispatches of that day are on the lottery page with the processor beside each number | [`docs/reference/benchmarks/the-processor-lottery.md`](../docs/reference/benchmarks/the-processor-lottery.md) |
| R5a | Which hardware console panels to build | Approved and landed 2026-09-17. Three panels shipped, and the pooled read rate was deleted rather than kept beside them: measured over the committed counters ledger, **86 of the 90 runs that name a processor drew more than one kind**, so the bold figure an operator was most likely to quote was a number about neither machine | [`docs/concepts/console-design.md`](../docs/concepts/console-design.md), [`docs/architecture/publishing/console.md`](../docs/architecture/publishing/console.md) |
| R5b | Keep the summary text in the bench artifact | **Approved, and landed 2026-09-17.** Four dispatches had proved a candidate wrote something different and left nothing to read. Five articles times the repeats times two candidates is about 29 KB at the median against a 500 MB artifact ceiling, so it needs no retention knob and has none | [`docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) |
| R6 | The `browser` CI job flaked on `item-visual.spec.ts` | Fixed 2026-09-16. The drawing-width oracle waits a rendering frame rather than a round trip | - |
| R6 | `series.ts` read `cpu_model` by column index | Fixed 2026-09-16. Every published telemetry cell is found by its column name, so a column can move | [`docs/architecture/publishing/telemetry-series.md`](../docs/architecture/publishing/telemetry-series.md) |

## What was ruled and is still being delivered

**R3 - join `item-health` to the fingerprint. Approved; not on `main` as this was
written.** The fingerprint key is `(date, run_id, job, shard)` and `ItemHealthRow`
carried `run_id` and `shard` and no `job`, so the two could not be joined at all.
Three options were priced: a `fingerprint` pointer column, a `job` column
completing the natural key, or copying the 27 machine columns onto every item row.
The third was refused outright - a second copy that can disagree with the first.
The pick is the `job` column, and `runner_name` retires from `ItemHealthRow` with
it, because the fingerprint row already holds it.

Check where it stands in one line:

```powershell
$py -c "from idhazh.contracts.item_health import ItemHealthRow as I; print('job' in I.csv_columns())"
```

`False` means it has not landed yet. It was `False` on 2026-09-17.

## What is still open

| id | Question | State |
| --- | --- | --- |
| R5c | Whether `measure.yml` and `validate.yml` should share more than the scratch-config block. The composite action `.github/actions/candidate-config` shipped as the first step | **Answered 2026-09-17.** The rule, the next block worth extracting, what stays duplicated and what a bench must never share with production are in [`docs/reference/github-actions.md`](../docs/reference/github-actions.md#design-rationale) |
| R5d | Whether to adopt either candidate model | **Not approved and not delivered.** `config/idhazh.json` still names `models/qwen3.5-9b-q4km.json`, the incumbent. [`docs/reference/models.md`](../docs/reference/models.md) holds each candidate's readings, and [`docs/reference/benchmarks/what-the-draft-head-is-worth.md`](../docs/reference/benchmarks/what-the-draft-head-is-worth.md) says what the draft-head runs did and did not settle |

## What the owner declined

**Freezing the bench corpus text. Declined 2026-09-16.** The bench refetches every
article on every repeat, and a news page edited inside a multi-hour job costs the
run that repeat: on 2026-09-15 it happened to two of five articles on both of two
dispatches. Freezing repeat 1's text and replaying it would keep those readings,
and `idhazh qualify` already works that way. The owner's reason for saying no:
**text changing is how the real world works.** A bench that never meets an edited
page measures a world the pipeline does not run in. So the drop stays, `problems`
names it `input_drift_dropped`, and the lost readings are the price of measuring
the live web - recorded beside the behaviour in
[`docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md).

This is a decision, not a deferral. Re-opening it needs a new ruling, not an
implementer who thinks a freeze looks tidier.

## What this cost, worth carrying forward

**A guard scoped to a file cannot see a writer in another file, and a second
file-scoped guard is the same defect a second time.** The rollup guard read
`stages/work.py` and was blind to a probe that runs from `cli.py`. The fix written
on 2026-09-16 was a second guard reading `telemetry/silicon.py`, and it was
retired on 2026-09-17 with the three hand-written ledger lists both guards
consumed. What replaced them names no file: it takes the stores from the path
helpers the store modules export and charges each one to the job whose
`python -m idhazh <verb>` step reaches its writer.

## See also

- [`CLAUDE.md`](../CLAUDE.md) - the contract.
- [`docs/reference/host-metrics.md`](../docs/reference/host-metrics.md) - every fingerprint column, where it comes from, and why almost none of them are enums.
- [`docs/reference/github-actions.md`](../docs/reference/github-actions.md) - which workflows push to `main`, and the test that holds a job to staging what it writes.
- [`docs/reference/benchmarks/the-processor-lottery.md`](../docs/reference/benchmarks/the-processor-lottery.md) - every draw with its processor, and the hypotheses each with the measurement that would settle it.
- [`docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - the runbook this work serves.
- [`docs/reference/agent-notes.md`](../docs/reference/agent-notes.md) - the environment traps this work met, each recorded where a later agent will look for it.
