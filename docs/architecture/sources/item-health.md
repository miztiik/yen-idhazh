# Item Health

**Last Updated**: 2026-08-23

What every planned item did on every run, where that record lives, and which
failures count against a source. This is item-grain evidence. Feed health is
source-grain evidence.

## Every item, every run, one row

`state/item-health/<YYYY-MM>.csv`, appended by the pipeline. One row is written
for each planned item on each run, whether the item succeeds or fails.

The row carries:

`version, date, run_id, item_id, url_key, canonical_url, vertical, source_id, stage, outcome, code, http_status, source_chars, source_words, summary_words, detail`

The file is append-only and never pruned. The 30-day window is a read-side
parameter. Monthly shards follow `state/seen/` and `state/feed-health/`.

## Stages and outcomes

An item can terminate at one of five stages:

`plan`, `fetch`, `extract`, `summarize`, `publish`

The outcome is either `ok` or `failed`. A successful row has no failure code. A
failed row has one failure code that belongs to its stage.

`route` and `render` are not terminal item-health stages. A render failure
degrades an item and never fails it.

## Failure codes

| Stage | Codes |
| --- | --- |
| `plan` | `not_attempted` |
| `fetch` | `robots_denied`, `robots_unreachable`, `blocked_address`, `http_client_error`, `http_rate_limited`, `http_server_error`, `network_error` |
| `extract` | `no_text`, `too_short` |
| `summarize` | `model_unreachable`, `output_truncated`, `bad_shape`, `length_out_of_range` |
| any failed stage | `unknown` |

`detail` is `str | None`, max 200 characters, and is populated only when
`code = unknown`. It is our sanitized text, never source text. A non-empty
`detail` means "mint a better enum member".

`http_status` belongs only on `fetch` rows.

## What counts against a source

Nine codes never count against a source:

`not_attempted`, `robots_denied`, `robots_unreachable`, `blocked_address`,
`http_rate_limited`, `model_unreachable`, `output_truncated`, `bad_shape`,
`length_out_of_range`

The remaining six can count against the source:

`http_client_error`, `http_server_error`, `network_error`, `no_text`,
`too_short`, `unknown`

The contract carries this as data on the enum side, not as prose only, because a
later source-health reader uses it.

## Design rationale

A failure-only file cannot produce a rate. The ledger writes successes and
failures in one file so a chart can divide failures by all planned items.
Authority: Fowler.

The row stores both `url_key` and `item_id`. `item_id` is a per-day ordinal and
can move between runs. `url_key` is the stable article key. Authority: Fowler.

The row stores `canonical_url`. About 80 bytes buys back the URL that otherwise
expires with a run artifact. Authority: Fowler.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Two files, one for failures and one for word counts | Two schemas and two parses for one row's facts. |
| Store `compression` | It is derived from `summary_words / source_words`. The chart can divide. |
| Reuse `state/scores.csv` | It holds items the scorer measured, not all planned items. |
| Persist free-text failure detail as the signal | A chart cannot group free text. |
| Mint `boilerplate`, `paywall`, or `skipped` now | No writer owns those codes yet. |
| Add `attempt`, `recorded_at`, `title`, or `source_url` | No query needs them. `date` and `run_id` already address the row. |

## See also

- [health.md](health.md) - the feed-grain ledger.
- [trust-boundary.md](trust-boundary.md) - how fetched bytes become sanitized text.
- [../contracts/schemas.md](../contracts/schemas.md) - the contract and schema rules.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - logs as evidence, ledgers as records.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3, Rule #11, and section 11.
