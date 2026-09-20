# What decides how much a feed is trusted

**Last Updated**: 2026-09-20

How much weight one feed's stories get against another's, and what would make
that weight fit itself instead of being chosen by hand.

**Status: a stub. Nothing here is built, and no plan builds it yet.** What is
below is the current hand-set state and the shape a fitted version would take.
Anything stated as future is an intention, not a design of record.

## What is hand-set today

Every feed in `config/sources.json` carries a `tier` and a `weight`, and both are
numbers a person chose when the feed was added. Nothing re-reads them against how
that feed has since behaved.

Two knobs in `config/idhazh.json` do watch behaviour, and they alarm rather than
tune: `collect.source_yield_alarm_point` (0.5) and
`collect.source_yield_alarm_min_decisions` (30). They name a source that answers
cleanly and returns almost nothing; what happens next is a person's call.
[../sources/health.md](../sources/health.md) owns that rule.

## Where the design already lives

[../sources/i-feed.md](../sources/i-feed.md) is the design proposal for scoring a
feed on its recent behaviour, and it already carries the row this page would
build: *tune component weights, decay settings and allocation parameters
automatically within tested limits.* **That page owns the scoring design. This
page would own only the fitting** - what moves a weight, how far it may move in a
day, and what stops it moving on noise.

If the two ever say the same thing, this page is the one that is wrong
(`CLAUDE.md` section 5).

## What would have to be true before a weight is fitted

- A settled outcome per feed that is not just yield: a feed can answer cleanly and still be worthless.
- A cover on the read, because feed history grows with every run (`CLAUDE.md` Guardrail #12).
- A floor no fitted weight may cross, so a bad fortnight cannot silently retire a source.

## See also

- [../sources/i-feed.md](../sources/i-feed.md) - the scoring design this page would fit, including the automatic-tuning row it already names.
- [../sources/health.md](../sources/health.md) - what is measured per source today, the yield alarm, and what retires a feed.
- [../sources/discovery.md](../sources/discovery.md) - how a feed's tier and weight reach the ranking arithmetic.
- [llm-council.md](llm-council.md) - the room a fitted weight would be judged in.
- [autotune-content-similarity.md](autotune-content-similarity.md) - the one line that already fits itself, and the shape any other would copy.
