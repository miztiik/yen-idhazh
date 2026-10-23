# Which native feed history the isolated planner uses

**Last Updated**: 2026-10-23

The TypeScript planner reads the feed-health and feed-retirement files written
by the existing pipeline. It writes the same native rows for its own feed reads.
It does not treat planner source-run audit records as feed-health history.
The [native health rules](health.md) own rest, endpoint retirement and reliability.
The [runner](feed-plan-runner.md) owns the captured UTC clock and stage order.

## Named history and incomplete inventories

`inputs.feed_health_days` and `inputs.feed_retirement_days` name UTC days,
compact indexes and either raw files or a raw index. The existing native reader
checks file identities, schemas, digests and byte counts. Yearly files take
precedence over monthly, daily and raw files. A shared file cache prevents
reading a month or year again for each named day. Higher attempts replace
earlier attempts of the same native work unit.

Health uses the newest 31 **native represented days**. Reliability uses the
newest `collect.reliability_window_days` represented days. This matches
`ledger_files.held_days`: a raw day holding files or a nonempty daily index
contributes its day; a nonempty monthly or yearly index contributes every
calendar day of that period, including days whose read returns no rows.
It is neither a trailing calendar cutoff nor a filter keeping only row-bearing
days. Duplicate feed/run results settle with the native preference: a read
carrying usable links wins; otherwise the later check wins.

Within a native day, the TypeScript reader orders runs by the recorded UTC
check time. Exact raw files supply their original millisecond write time when checks have the same
second; it never substitutes a compactor's write clock. Without that original
raw clock, the recorded second is the only time key. Numeric execution is the
final deterministic tie-break when the time keys agree.
This fixes repeated listener requests whose random numeric run IDs are not
chronological. Existing Python `load_health` still orders by numeric execution
alone; its runtime is unchanged here. Mixed-producer ordering in that reader,
and unrecoverable same-second order in compacted records with opaque IDs,
remain explicit compatibility gaps rather than a claim of full parity.

The isolated workflow stages the three registered compact indexes and their
named files. It also checks individual raw UTC-day directories within
`daily_keep_days` from each ledger's existing gardener config. This is a
discovery bound, not a health window or retirement expiry. Explicit authored
older inputs remain included. The selector uses raw presence and native compact
cover metadata before slicing its day count; it does not infer represented
days from row presence after reading.

Neither this discovery method nor an arbitrary supplied list proves that it
contains every old, unindexed raw file. The result therefore reports
`retirement_inventory_complete: false`. It honors every supplied retirement
without an age cutoff. A missing day stays missing, not known empty. Fewer
recorded health days than requested report unavailable coverage; observations
that do exist remain usable and keep their actual counts.

Full discovery uses the same native raw and compact files and their indexes.
Existing publication-inventory entries and exact producer receipts can name
files already recorded there. Reading existing feed-health entries does not
authorize adding retirement entries or changing the publisher. Those producer
and inventory-role decisions still require owner approval.
No parallel history file or second authority is required. The coordinated
inventory-selector follow-up must prove which permitted native inputs it
covers while preserving missing evidence. This increment does not claim
complete external inventory discovery or full feed-history parity.

One listener also retains its own exact durable native file receipts between
requests, including writes completed before a later stage fails. Their paths
are relative to the actual configured output root, not the checkout; readback
rejects traversal, escaping links, wrong ledgers, days and native identities.
Health receipts retain the newest configured count of recorded days, including
calendar gaps. Retirement receipts retain state for current configured
endpoints without a time expiry. No directory scan is used for this readback.
Receipts are observations, not proof that an unavailable external day was empty.

## Feed decisions and native writes

Retirement is decided before rest. Only HTTP 410 results with an observed
endpoint key count toward automatic retirement; a usable successful feed read
clears that endpoint's 410 record. Other failures, permission refusals, empty
reads and rests do not clear it. A retirement retains the distinct deciding
run IDs and is written before the run's health rows. A configured URL edit
has a different SHA256 endpoint key and does not inherit an old retirement.
An older row without a key is never assigned today's address.

Rest follows `collect.availability_strikes_before_rest` for both the strike
threshold and the number of skipped runs, matching production.
`collect.availability_rest_runs` remains unread, as it is in the Python rule.
A rest and a robots result neither add nor clear a strike. A productive read
clears it. A rest ends after its recorded skip count reaches the threshold.

Resting and retired active feeds produce an unrequested feed outcome with
explicit history evidence, no invented HTTP failure and no network request.
Draft and curated-retired sources retain `SOURCE_INACTIVE`.
Native skipped rows say whether the cause was rest, HTTP 410 retirement,
sustained low-yield retirement or inactive source configuration.
Health `items` counts distinct usable offered links, including links later
rejected by article rules; it is not the raw XML-entry or published count.
Native versions remain `2026-09-02T20:00` for health and `2026-09-17` for
retirement. Compatible older rows retain their versions and unavailable fields.
No historical payload is restamped.

## Evidence is not a new ranking policy

Each feed event records the observed productive reads, evidence-bearing
attempts, raw success fraction, requested recorded-day count and actual day
bounds. Rest and permission refusals are outside the denominator. No
evidence-bearing read means unavailable reliability, not a fabricated success.
The current run's persisted feed read joins this measurement, matching the
Python plan stage's read-after-write order. Lifecycle decisions still use only
the earlier record. Current observations do not turn missing older days into
known empty days or prove that the supplied inventory is complete.
`production_factor` also exposes the native fraction clamped to
`collect.reliability_floor`; it is not multiplied into portfolio scores.
Source-run audit summaries receive the measured fraction, attempts and
recorded-day count even when that source supplied no eligible article.

The daily published evidence reads only the captured UTC day's native
item-health rows, matching `ledger.rows.load_source_counts`: successful
outcomes count once per URL key. Failed attempts do not count. An available,
known-empty day supports zero; unavailable coverage exposes only an observed
lower bound, not a claim of zero publications. This is distinct from the
current planning attempt's `SourceRunRecord.published_count`, which remains
null until a publication observer supplies its result.
Both native item-health projections pin their independent supported stamp,
`2026-10-20`; a planner contract or event revision cannot silently widen it.

Feed events carry this evidence through the existing stage payload and its
versioned reader. The API/CLI summary includes coverage and native file
receipts. The isolated workflow verifies and commits the exact health and
retirement output files beside the existing planner outputs.

## Design rationale

The portfolio's approved score, diversity penalties and quotas remain
unchanged. Applying the Python reliability multiplier or daily source ceiling
would change selection policy, not merely supply missing evidence. Those
choices require an explicit owner decision. A missing inventory is an input
limitation to repair, not evidence that a feed is healthy or that an old
endpoint has become eligible.
