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

Health uses the newest 31 **recorded days**, not 31 calendar days. Reliability
uses the newest `collect.reliability_window_days` recorded days. A gap between
two recorded days does not shorten either record. Duplicate feed/run results
settle with the native preference: a read carrying usable links wins; otherwise
the later check wins. Run numbers sort numerically.

The isolated workflow stages the three registered compact indexes and their
named files. It also checks individual raw UTC-day directories within
`daily_keep_days` from each ledger's existing gardener config. This is a
discovery bound, not a health window or retirement expiry. Explicit authored
older inputs remain included. The reader selects actual recorded health days
after staging, rather than counting absent calendar days as recorded ones.

Neither this discovery method nor an arbitrary supplied list proves that it
contains every old, unindexed raw file. The result therefore reports
`retirement_inventory_complete: false`. It honors every supplied retirement
without an age cutoff. A missing day stays missing, not known empty. Fewer
recorded health days than requested report unavailable coverage; observations
that do exist remain usable and keep their actual counts.

Full current-state discovery still needs one authoritative, seeded snapshot
maintained from real production writes. Its follow-up must use reviewed named
legacy files, preserve missing coverage, and combine new observations with
fresh main on each publication retry. This increment does not claim that
integration or complete feed-history parity.

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
