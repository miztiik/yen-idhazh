# Which order a saved observation clock proves

**Last Updated**: 2026-10-23

Native feed-health `checked_at` and keyed-request `PlannerOperation.created_at`
retain the precision their producer actually captured. The field-specific
`RecordedInstant` type accepts UTC whole seconds and UTC milliseconds.
The project's global `Timestamp` type remains whole-second UTC text.

## Text, precision and compatibility

A legacy value such as `2026-10-23T00:45:05Z` is kept byte-for-byte. It establishes
the recorded second, not an invented millisecond offset within that second.
A genuinely captured millisecond value such as
`2026-10-23T00:45:05.123Z` retains exactly three fractional digits.
New precision must use the new native contract stamp; it is not written under
an older declaration.

The models keep strings, not a datetime object that reformats an old payload
on read. Legacy strings are never padded to `.000Z`, restamped or rebuilt from
today's clock. Compatible old raw files and old request records remain readable.
Native schema versions and changelogs name the field evolution.

## One captured instant through keyed execution

The producer captures one UTC instant. Ordinary existing event and pipeline
fields can still use their established whole-second spelling. Health checks
retain the supplied captured precision.

The keyed request stores that same captured instant in its existing
`created_at`. Execution restores it from that exact string, retaining whether
it was coarse or precise. A completed replay returns the stored response; it
does not capture a new request clock. An interrupted keyed plan remains
incomplete rather than being silently executed under a new time.

The existing SQLite journal stores the native request as JSON in its existing
`record` text column. This field evolution adds no SQL column, table, history
snapshot or alternate authority. Retry attempts and genuine new fetch/parse
observations retain their existing measurement behavior.

## Intervals, not invented tie order

Whole-second text admits the interval from that second up to the next second.
Millisecond text admits the interval from that millisecond up to the next
millisecond. The lower bound is included and the upper bound is excluded.

One observation is definitely later only when its admitted interval is wholly
after the other's. A legacy whole-second observation and a precise observation
inside that second overlap. Equal precise values and frozen clocks overlap too.
More digits do not create an order when no order was measured.

Readers use only these saved logical values. They never infer chronology from
UUID magnitude, list arrival, original file-write time, compactor time or an
own-listener sequence. Stable identifiers may order presentation inside a tied
set, but they do not make an order-sensitive lifecycle decision true.
The feed-query example compares parsed UTC values, not mixed-precision text.
Its latest recorded lower bound is the greatest interval start, not proof of
which overlapping check happened last. It never rewrites the saved strings.

Availability counts are bounded over all orders admitted by the intervals.
An exact failure/skip count is returned only when its bounds agree. Rest is
applied only when proved; an order-dependent unresolved result is explicitly
unknown. Order-insensitive observations, such as a set containing only failed
reads, can still support a decision.
Unknown availability alone does not withhold an allowed source. The console
keeps that limitation visible without counting it as a withheld source.

The Python reader's legacy HTTP 410 fold similarly uses only runs proved to
follow every productive read; known permanent retirements are honored.
Conflicting latest permission answers with overlapping times are unavailable,
not fabricated consent or a fabricated robots failure.
The TypeScript planner's permanent retirement authority is instead its
[curated source registry](../sources/planner-feed-history.md).

## Compaction preservation

The same logical rows and original row identities must produce the same
decisions as raw files and as daily, monthly and yearly compact files.
Compaction copies the saved strings without adding, discarding or normalizing
their precision. File-envelope `written_at_ms` describes physical persistence,
not the check instant, and is never a missing ordering field.

Existing fixture cases exercise reversed opaque run IDs, precise later checks,
legacy equal seconds, frozen precise clocks, mixed precision, order-insensitive
failures and known retirement. Both native implementations read actual packed
files; no mock or network fixture supplies a verdict.

## Design rationale

Owner approval, kumarsnaveen_microsoft, 2026-10-23, "Bug 1 - A1": use the
existing `checked_at` and keyed-request `created_at` fields with field-specific
precision, compatible original-string reads and narrow Python/TypeScript
capture/reader changes. No global timestamp relaxation, new column, state file
or identifier scheme is authorized. Local Python execution and packages are
not part of validation; existing CI remains authoritative for native Python.

The frontend and TypeScript planner share the framework-free observation-order
source module in the existing common-contracts package to keep one TypeScript
interpretation. No dependency is added. Only that pure helper enters the browser,
not Zod or Node-specific schema modules.
