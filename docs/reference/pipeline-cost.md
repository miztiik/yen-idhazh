# What the Pipeline Costs to Run

**Last Updated**: 2026-10-10

Where current runtime measurements live and how to use them when sizing work. This page does not keep a history of production runs or duplicate model readings.

## Current sources

| Question | Source |
| --- | --- |
| Which model runs, and what was measured for it? | [models.md](models.md), then that model's dossier |
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

Retake model-dependent readings in CI when the subject changes. Do not copy a value from this page into a gate or silently shorten content to make a context window fit.

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
4. Put model-specific readings on the model's page. Put a reproducible benchmark under `docs/reference/benchmarks/`, named for its question.
5. Replace the previous reading of that quantity. Keep current rationale on the page whose behavior it governs; git holds the old result.

## See also

- [models.md](models.md) - configured and candidate models.
- [github-actions.md](github-actions.md) - measurement workflows.
- [site-weight.md](site-weight.md) - deployed bytes and transfer bytes.
- [documentation-structure.md](documentation-structure.md) - where readings and rationale belong.
- [../architecture/summarize/throughput.md](../architecture/summarize/throughput.md) - model-call scheduling.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - changing the model.
- [../concepts/telemetry.md](../concepts/telemetry.md) - the measurement records.
