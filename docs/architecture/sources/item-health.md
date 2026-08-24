# Item Health

**Last Updated**: 2026-08-23

What every planned item did on every run, where that record lives, and which
failures count against a source. This is item-grain evidence. Feed health is
source-grain evidence.

## Every item, every run, one row

`state/item-health/<YYYY-MM>.csv`, appended by Assemble once per run. One row is
written for each planned item on each run, whether the item succeeds or fails.

The row carries:

`version, date, run_id, item_id, url_key, canonical_url, vertical, source_id, stage, outcome, code, http_status, source_chars, source_words, summary_words, detail, fetch_ms, extract_ms, summarize_ms, prefill_ms, decode_ms, input_tokens, output_tokens, cached_tokens`

The file is append-only and never pruned. The 30-day window is a read-side
parameter. Monthly shards follow `state/seen/` and `state/feed-health/`.

## Stages and outcomes

An item can terminate at one of five stages:

`plan`, `fetch`, `extract`, `summarize`, `publish`

The outcome is either `ok` or `failed`. A failed row has one failure code that
belongs to its stage. A successful row usually has no code, but may carry an
extract signal: `too_short`, `not_prose` or `boilerplate`.

`route` and `render` are not terminal item-health stages. A render failure
degrades an item and never fails it.

## Failure codes

| Stage | Codes |
| --- | --- |
| `plan` | `not_attempted` |
| `fetch` | `robots_denied`, `robots_unreachable`, `blocked_address`, `http_client_error`, `http_rate_limited`, `http_server_error`, `network_error` |
| `extract` | `no_text`, `too_short`, `not_prose`, `boilerplate`, `paywalled`, `unsupported_form` |
| `summarize` | `model_unreachable`, `output_truncated`, `bad_shape`, `length_out_of_range` |
| any failed stage | `unknown` |

`detail` is `str | None`, max 200 characters, and is populated only when
`code = unknown`. It is written by the classifier, never copied from an article
or summary payload. The write path sanitizes it, strips any spreadsheet formula
prefix, collapses whitespace, and truncates it. A non-empty `detail` means "mint
a better enum member".

`http_status` belongs only on `fetch` rows.

`fetch_ms`, `extract_ms`, and `summarize_ms` are nullable. Null means the stage
did not run, or the row predates timing capture. It is not zero. A zero would be
a measurement.

## What the model cost

`summarize_ms` is wall-clock for the whole request. `prefill_ms` and `decode_ms`
split it the way the runtime charges it: prefill is the model reading the
prompt, decode is it writing the reply, and decode runs at roughly half the
prefill rate because it produces one token at a time. A blended figure cannot
say which of the two made a slow day slow.

All five columns come straight from the runtime's own reply, so nothing here is
our arithmetic. A runtime that reports no timings leaves them null, and the item
still publishes.

A rate needs its token count beside its milliseconds, so both are on the row:

| Read | From |
| --- | --- |
| Prompt tokens the model actually read | `input_tokens - cached_tokens` |
| Prefill tokens per second | `(input_tokens - cached_tokens) / (prefill_ms / 1000)` |
| Decode tokens per second | `output_tokens / (decode_ms / 1000)` |
| Prompt cache hit rate | `cached_tokens / input_tokens` |

`cached_tokens` is what the runtime reused instead of reading. Leaving it in the
prefill count reports a rate the machine never ran at, which is why the console
subtracts it.

**A day is the sum of its rows, never the median of their rates.** A rate is a
ratio, and the workers each did a share of one day: averaging per-item rates
weighs a 60-word release note the same as a 2000-word feature.

The **spread** of the per-item rates is a different statistic and is kept too.
The console draws it as a candle per day, because the worker summarises short
articles before long ones and the two ends of a day drift apart on purpose. Why
that happens, and what a change in either rate is allowed to prove, is
[../summarize/throughput.md](../summarize/throughput.md).

## What counts against a source

Twelve codes never count against a source:

`not_attempted`, `robots_denied`, `robots_unreachable`, `blocked_address`,
`http_rate_limited`, `too_short`, `not_prose`, `boilerplate`,
`model_unreachable`, `output_truncated`, `bad_shape`, `length_out_of_range`

The remaining seven can count against the source:

`http_client_error`, `http_server_error`, `network_error`, `no_text`,
`paywalled`, `unsupported_form`, `unknown`

The contract carries this as data on the enum side, not as prose only, because a
later source-health reader uses it.

`model_unreachable` records our local model server being down. It is
infrastructure failure. It never counts against a source.

## Design rationale

A failure-only file cannot produce a rate. The ledger writes successes and
failures in one file so a chart can divide failures by all planned items.
Authority: Fowler.

Shape is evidence, not a verdict. `too_short`, `not_prose` and `boilerplate`
can appear on an `ok` row because the item published and the signal still matters
to the editor. They never count against a source by default. Only a paywall, an
unsupported form, or genuine missing text stops extract. Authority: Owner
override O3.

The row stores both `url_key` and `item_id`. `item_id` is a per-day ordinal and
can move between runs. `url_key` is the stable article key. Authority: Fowler.

The row stores `canonical_url`. About 80 bytes buys back the URL that otherwise
expires with a run artifact. Authority: Fowler.

Assemble is the only item-health ledger writer. Worker shards already upload one
JSON payload per item through the `items-*` artifact. A per-shard CSV append
would turn a diagnostic row into a rebase race against the publish commit.
Authority: Carmack.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Two files, one for failures and one for word counts | Two schemas and two parses for one row's facts. |
| Store `compression` | It is derived from `summary_words / source_words`. The chart can divide. |
| Reuse `state/scores.csv` | It holds items the scorer measured, not all planned items. |
| Put stage timings on `EvalRow` | `EvalRow` is written only for the scored subset. Slow or failed items would disappear from the operator's timing view. |
| Persist free-text failure detail as the signal | A chart cannot group free text. |
| A `skipped` code | A skip is not one cause. The row records the typed cause instead. |
| Add `attempt`, `recorded_at`, `title`, or `source_url` | No query needs them. `date` and `run_id` already address the row. |
| Parse the throughput out of the runtime log | The log is a CI artifact kept for two days, and a rate nobody can recompute later is not a measurement. The reply already carries the numbers. |
| Store the rates instead of the counts | A stored rate cannot be re-aggregated across a day, a week, or the four workers. Store what was measured; divide on read. |

## See also

- [health.md](health.md) - the feed-grain ledger.
- [../summarize/throughput.md](../summarize/throughput.md) - what the two model rates mean, and why the spread inside a run is wide.
- [trust-boundary.md](trust-boundary.md) - how fetched bytes become sanitized text.
- [../contracts/schemas.md](../contracts/schemas.md) - the contract and schema rules.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - logs as evidence, ledgers as records.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3, Rule #11, and section 11.
