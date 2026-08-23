# Item Health

**Last Updated**: 2026-08-23

What every planned item did on every run, where that record lives, and which
failures count against a source. This is item-grain evidence. Feed health is
source-grain evidence.

## Every item, every run, one row

`state/item-health/<YYYY-MM>.csv`, appended by Assemble once per run. One row is
written for each planned item on each run, whether the item succeeds or fails.

The row carries:

`version, date, run_id, item_id, url_key, canonical_url, vertical, source_id, stage, outcome, code, http_status, source_chars, source_words, summary_words, detail, fetch_ms, extract_ms, summarize_ms`

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

## See also

- [health.md](health.md) - the feed-grain ledger.
- [trust-boundary.md](trust-boundary.md) - how fetched bytes become sanitized text.
- [../contracts/schemas.md](../contracts/schemas.md) - the contract and schema rules.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - logs as evidence, ledgers as records.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3, Rule #11, and section 11.
