# When a feed is rested, retired, or kept out

**Last Updated**: 2026-09-23

The knobs that decide how long a run keeps asking a feed that answers badly,
when an address is given up on, and what keeps a link out of the candidate pool
before anything is fetched. They are a curator's controls rather than a tuner's:
each one changes which sources a day is built from. What a knob is, and what is
not one, is [../config.md](../config.md).

## Source-lifecycle surface

Six `collect` knobs landed on 2026-09-02 with **no reader**, and that was
deliberate. They name four different questions that one knob had been answering
on its own, so the changes that moved the behaviour onto them were reviewable as
behaviour rather than as a knob and a rule at once.

**Five of the six now have one.** `availability_strikes_before_rest` decides
every rest, `feed_http_410_runs_before_retirement` decides when an address is
retired, the two recheck cadences are answered by the run itself - nothing about
a refusal is persisted, so the next run asks the host again - and
`source_yield_min_complete_days` is the published record's span.
`availability_rest_runs` is the one still unread.

| Knob | Default | What it decides |
| --- | --- | --- |
| `availability_strikes_before_rest` | 5 | Results counting against a feed before a run stops asking it, and how many runs that rest then lasts. |
| `availability_rest_runs` | 5 | Nothing yet. It names the length of a rest, which today comes from the knob above. |
| `feed_http_410_runs_before_retirement` | 5 | Distinct runs that must each read `410 Gone` from one address before that address is retired. |
| `robots_denied_recheck_runs` | 1 | Runs to wait before asking `robots.txt` again after a refusal. |
| `robots_unreachable_recheck_runs` | 1 | The same, after a `robots.txt` we could not read at all. |
| `source_yield_min_complete_days` | 30 | Complete days of item-health evidence a per-source yield judgement needs before it may be made - and, since 2026-09-03, how far back the published source-health record reads. |
| `source_yield_alarm_point` | 0.5 | The yield below which a run names a source on its own summary. A flag for a person; it moves nothing on its own. |
| `source_yield_alarm_min_decisions` | 30 | Addresses a source must have decided before its yield may raise that flag. |
| `source_quality_dwell_days` | 14 | Running days under the alarm point before a source retires itself. A bad week cannot retire anything. |
| `source_quality_auto_retire` | `false` | Whether a completed dwell files a retirement, or only draws the countdown. Delete this flag once one real retirement has been reviewed and accepted. |

**`quarantine_after_failures` was removed on 2026-09-03**, and a config still
spelling it is refused with a message naming `availability_strikes_before_rest`.
Both names carried 5 in the committed file and 3 in the tuned fixture, so moving
the reader could not move a decision - that is what made it a rename rather than
a change of behaviour.

**`availability_rest_runs` stays unread on purpose.** `discover.resting` takes
one number and spends it twice: how many strikes start a rest, and how many
skipped runs end it. Splitting it into two is a change to the rest rule, not a
rename, so it did not travel with the rename. Setting this knob today changes
nothing.

**The two recheck cadences are one number in two knobs, and they still earn
both.** A refusal is a publisher's stated policy; an unreadable `robots.txt` is
our own failed read. One name for both means an edit meant for one silently moves
the other, which is the defect this whole block exists to undo.

**`source_yield_min_complete_days` is a floor on making a judgement, not a
threshold on yield.** Below it any yield number is an estimate rather than a
measurement (Guardrail #10), and no source may be demoted on one. Since 2026-09-03 it
is also the span the published source-health record reads, because how far back
to look and how much is enough are one question, and a second knob would be a
second answer to it. What the window is for is
[../../architecture/sources/health.md](../../architecture/sources/health.md).

**The two alarm knobs are a third question, and they are not that floor.** They
decide when a run says out loud that a source answers cleanly and returns almost
nothing - the `scmp-news` shape, where every other signal read healthy for a
fortnight. `source_yield_alarm_point` is a threshold on a ratio, not a clamp:
`reliability_floor` is the lowest a factor may reach, and calling this one a
floor too is how the two get confused. `source_yield_alarm_min_decisions` counts
decisions a source made, where `source_yield_min_complete_days` counts days of
record - a busy source clears the first in four days and a weekly one may never
clear it, which is the right answer for both. Measured 2026-09-06 over 144
sources and 13 complete days: with the evidence knob at 30 the alarm names three
sources and no false positive; at 1 it also names `cnn-world` on 1 of 7, a
working feed. Both numbers and what they cost are in
[../../architecture/sources/health.md](../../architecture/sources/health.md).

## A curator may declare a feed publishes abstracts

`config.sources` can declare `form: "abstract"` on a feed. That is a curator's
fact about the feed, not a detector over page text. NBER uses it; arXiv and SSRN
should use the same field if those feeds are added. What the declaration then
stops is a short-item rejection, in
[summary-length.md](summary-length.md#what-extraction-records-and-what-it-refuses).

## An address may be kept out before anything is fetched

`collect.blocked_url_markers` is a list of case-insensitive substrings that keep
an address out of the candidate pool. It defaults to empty, because the entries
are a source-curation decision and belong in `config/` rather than in the
contract (Guardrail #6). What it is for, and why the control cannot live at the
faithfulness score, is
[../../architecture/sources/discovery.md](../../architecture/sources/discovery.md).

An address that failed today is a different question, and its knob is a memory
rather than a guard: `collect.settled_failure_codes` is on
[run-limits.md](run-limits.md#a-guard-is-not-a-limit-and-its-name-has-to-say-so),
with the rest of the vocabulary that separates a guard from an alarm.

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [../feed.md](../feed.md) - what a feed is, and what a source registers.
- [../../architecture/sources/health.md](../../architecture/sources/health.md) - what `availability_strikes_before_rest` decides, and what the yield window costs.
- [../../architecture/sources/discovery.md](../../architecture/sources/discovery.md) - the scoring these knobs sit around.
- [../../architecture/sources/freshness.md](../../architecture/sources/freshness.md) - the run cadence, and which failures are worth retrying today.
- [../../reference/source-yield.md](../../reference/source-yield.md) - the measured yield each source has returned.
