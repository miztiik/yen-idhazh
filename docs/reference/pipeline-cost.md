# What the Pipeline Costs to Run

**Last Updated**: 2026-10-25

Where current runtime measurements live and how to use them when sizing work. This page does not keep a history of production runs or duplicate model readings.

## Current sources

| Question | Source |
| --- | --- |
| Which model runs, and what settings does it use? | [Model configuration](../concepts/config/model-file.md) |
| What did an item cost? | Item-health rows, defined in [item health](../architecture/sources/item-health.md) |
| What machine ran a job, and what did the job cost? | Host-fingerprint rows, defined in [host metrics](host-metrics.md) |
| Which sub-step took time? | Span rollups and recent traces, defined in [telemetry](../concepts/telemetry.md) |
| Which files contain those rows? | [Ledger registry](../architecture/contracts/ledger-registry.md) |
| What limits work today? | `config/idhazh.json`, the active model configuration and [run limits](../concepts/config/run-limits.md) |
| How much does the published site weigh? | [site-weight.md](site-weight.md) |
| How productive are the feeds? | [source-yield.md](source-yield.md) |

Read configuration for the current limit. Do not size a run from an old benchmark's item count, model name or timeout.

## Inference throughput

Prefill is the model reading uncached prompt tokens. Decode is the model generating output tokens. Keep them separate: article length and reply length spend different parts of the runtime.

- Compute a pooled rate from total tokens divided by total measured time, not the average of per-item rates.
- Exclude reused prompt tokens from evaluated-token throughput. Keep cache reuse as a separate measure.
- Compare the same model, runtime settings, input geometry and cache state. A different article mix can change the rate without changing the engine.
- Group by host capabilities when hardware differs. Preserve per-shard results so a slow host does not disappear into the mean.
- Record failed and interrupted work as well as successful requests. A rate over survivors is not the cost of completing a run.

### The ledger and the server agree about the read rate

Use independent server counters to check per-request timing totals. Match the run, shard, attempt and request population first. Retries, warmups and interrupted requests can make the two populations differ.

[reconcile_prefill.py](../../backend/utilities/reconcile_prefill.py) compares the recorded populations. The runtime captures under `tests/fixtures/runtime/` define the counter semantics the parser supports. A derived rate cannot independently validate the same inputs it was computed from.

## What a work shard costs

Size against the slowest credible shard, not only the median. Include model loading, article preparation, both model calls, scoring, file writes and commit work. State which parts were directly timed and which were estimated.

### Where the work job's bound comes from

The automatic item allocation is bounded by the configured run ceiling and parallelism. Check the actual dispatch as well: a manual run can choose different inputs.

`run.shard_timeout_minutes` is the job's configured limit. GitHub kills a job at six hours regardless of that setting. A design that exceeds the platform limit needs less work per job or a different implementation; a larger timeout cannot make it fit.

Changing parallelism also changes model downloads, initialization and available runner slots. A run that overlaps the next consumes capacity even when it no longer queues that run behind one concurrency group.

Do not infer remaining time from the first few items if the worker processes shorter prompts first. Preserve the measured input distribution when forecasting the tail.

## How much of the runner's memory a run needs

A process's resident set is not the memory demand of the whole job. Mapped weights, shared pages, the operating system and other processes prevent that substitution.

- Across separate runner hosts, report each shard and the maximum. Do not sum them into a fictitious single machine.
- On one host, compare process samples taken at the same instant. Adding independent high-water marks does not measure a simultaneous peak.
- Do not subtract summed resident sets from advertised RAM and call the result headroom. Resident sets include reclaimable file-backed pages and can count shared pages twice.
- Use the operating system's total and available memory to describe machine pressure. Preserve the within-item minimum available memory when an average would hide the tightest point.
- Do not stack process resident memory, page cache and available memory as disjoint parts. They overlap.
- Report swap and anonymous memory separately when available. Leave an unsupported reading absent rather than substituting zero.

[The machine chart rules](../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) apply the same definitions to the operator surface.

## Token budgets

A token count belongs to a tokenizer and its input bytes, not to a workstation. Record the model identity, tokenizer, prompt template, schema and input conditions. A model change invalidates readings derived from its vocabulary.

Budget-bearing readings live in [measured.py](../../backend/idhazh/measured.py), with the subject and method that make them checkable. Validate them with:

```text
python backend/utilities/measure_budgets.py check
```

Each record keeps its value, date, measured model digest, method and remeasurement
instructions. The digest identifies the weights that produced the reading; it
must not be loaded from the current model selection, which can change without
remeasurement. Historical comparisons and design discussion do not belong in
the record.

Retake model-dependent readings in CI when the subject changes. Do not copy a value from this page into a gate or silently shorten content to make a context window fit.

`measure_budgets.py read` dates a reading with the current UTC day, not the
host's local day. `--taken-on YYYY-MM-DD` keeps the date the operator supplies.

## Visual-retention activation reading

On 2026-10-25 UTC, the real `gardener run-task visual-prune` command ran
locally against the 65 committed digest days at revision `25ca19ad8`.
Run `2026-10-25-13`, attempt 1, surveyed with `dry_run: true`; attempt 2
ran with the proposed `dry_run: false`. Both selected UTC dates 2025-09-22
through 2025-09-29, before the kept-day boundary of 2025-09-30. Both found
zero candidates. The live report recorded zero deleted files, zero files
held by the ceiling, no tripped fuse and zero reclaimed bytes. This is
local activation evidence, not a production workflow run.

Completed builds before and after the live pass each measured 199,199,056
deployed bytes (190.0 MiB), 671 files and 22,043 items. The change was zero
bytes, as expected for zero deletions. Both used `npm run build`, the fixed
`BUILD_VERSION` from that revision, and
`python -m idhazh site-weight --site-tree frontend/build`; source-tree size
was not used. Locally generated gardener and host reports were kept outside
the checkout before either build, so they did not change the compared corpus.
`check-publication` passed for all 65 committed days before and after the pass.

The size command estimated 885 published days to the 800 MiB warning and
1,210 to the 1,024 MiB cap, using 9,037 bytes per item and the configured
80-item input. These are the instrument's estimates, not a measured future
growth rate. No section 0 escalation trigger was observed in this local run.
The production gardener wake, its landed report and repeated publication
and built-size checks remain required before closing the activation plan.

## What to measure next

The user deferred further work on the reported two-call slowdown and adoption
of two simultaneous model requests per worker. Neither deferral is a finding
that the current cost is acceptable or that concurrency helps. Reopening either
needs a current measurement using the active model and runtime, matched inputs,
and named runner hardware. Historical readings from a retired model do not
settle these questions. The `parallel-summarization` case in
`config/pipeline-tests.json` remains disabled.

Keep an open measurement in the active plan only when it changes the next decision. Name the question, inputs, method and cost. Do not carry a permanent table of resolved questions, retired jobs or experiments nobody will run.

For reader latency, measure the actual browser path under a named network and CPU profile. A localhost fetch is not a reader's wait. For a runtime or memory decision, measure on the production runner; another machine provides only a labelled provisional estimate.

## How to add a reading

1. State the decision the reading will inform and the comparison that could change it.
2. Use fixed inputs or paired cases where possible. Record failures and the full population.
3. Record value, units, spread, method and date. Durations and memory need hardware and runtime details. Token counts need tokenizer identity; byte counts need format and compression settings.
4. Put model settings in its config file. Put reproducible runtime readings under `docs/reference/benchmarks/`, named for the question they answer.
5. Replace the previous reading of that quantity. Keep current rationale on the page whose behavior it governs; git holds the old result.

## See also

- [github-actions.md](github-actions.md) - which workflows exist and what they run.
- [site-weight.md](site-weight.md) - deployed bytes and transfer bytes.
- [documentation-structure.md](documentation-structure.md) - where readings and rationale belong.
- [../architecture/summarize/throughput.md](../architecture/summarize/throughput.md) - model-call scheduling.
- [../concepts/config/model-file.md](../concepts/config/model-file.md) - model identity and runtime settings.
- [../concepts/telemetry.md](../concepts/telemetry.md) - the measurement records.
