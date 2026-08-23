# Feed Health and Quarantine

**Last Updated**: 2026-08-23

What every feed did on every run, where that record lives, and how a run decides on its own to stop asking a dead source. Nothing on this page ever edits `config/sources.json`: a person owns the source list, and a run owns the evidence about it.

## Every feed, every run, one row

`state/feed-health/<YYYY-MM>.csv`, appended by the Collect stage. One row per feed per run, carrying the run id, the date, the feed id, the outcome, the HTTP status, how many items came back, and a short detail.

It is written **whether the run publishes or not**. The days a source is worth measuring on are the days the run went badly, and a ledger that only records good runs measures nothing.

Monthly shards, because a read looks back 31 days - just enough that a quarantine decided on the first of the month can still see the failures that caused it.

## Six outcomes, deliberately coarser than HTTP

What a later decision needs is whether the address is worth asking again. `403` and `404` answer that the same way; `503` answers it differently.

| Outcome | What it means | Counts against the feed |
| --- | --- | --- |
| `ok` | The feed answered and parsed | **Only if it returned zero items** |
| `robots_denied` | `robots.txt` said no | No |
| `blocked` | We were refused | Yes |
| `permanent` | Gone, and staying gone | Yes |
| `transient` | Timed out, or the host was briefly unwell | Yes |
| `skipped` | We did not ask - the feed was resting | No |

Two of those rows carry the whole design.

**A `200` that parses to no entries counts as a failure.** The most common way a feed dies is not a 500. It is a silent reshape that still returns 200 and an empty list. An empty answer costs the digest exactly the articles a refusal would, so it is measured the same way.

**A robots refusal never counts.** The source is working exactly as it asked to be treated. Quarantining it would be us punishing a site for saying no, and the pipeline honouring `robots.txt` is the pipeline working correctly.

## Quarantine is a rest, not a retirement

A feed that has failed its last `quarantine_after_failures` (5) attempts is not asked on the next run. That is a rest.

**The rest ends on its own.** Once a feed has been skipped five times it is asked again regardless of its record. A source that came back is live on that very run; a source that is still dead costs one request per cycle instead of one per run.

**A rest is transparent.** A `skipped` row neither adds a strike nor clears one, so the count picks up where it left off when the feed is next asked. Without that, a rest would erase the evidence that caused it.

Both counters read the same knob because there is only one question here - how much evidence is enough. A second number would be a second answer to it.

The `skipped` row exists for one reason: a quarantine that writes nothing can never lift, because the failures that caused it stay the newest thing on record forever. The skip has to be recorded for the rest to end.

Feed health cannot explain why a planned article failed after discovery. That
belongs to the item-health ledger, which records one row per planned item per
run. See [item-health.md](item-health.md).

## Per-source yield is not measurable yet

Feed health can say whether a source answered. It cannot yet say whether that
source yields publishable items over time. That denominator is different: one
source can answer cleanly and still produce planned items that fail at fetch,
extract or summarize.

Per-source item yield needs at least 30 days of `state/item-health/` rows. The
ledger started on 2026-08-23, so the rubric is blocked until that window exists.
Do not retire or demote a source by item-yield rule before then. Until the
window exists, any source-yield threshold is an estimate, not a measurement.

## The run never edits the source list

Retirement is a person moving a feed into the `retired` key of `config/sources.json`. Quarantine is a run declining to ask, based on rows it wrote itself.

Keeping those separate is what makes a bad afternoon survivable. A run that could edit config would, over one bad week, quietly delete sources nobody voted to remove - and the diff would be authored by a robot at 06:20 on a Sunday.

## Two readers, one record

- **The planning step** reads the recent tail to decide which feeds to skip this run.
- **The console** reads the same rows to show which sources are broken. It names only feeds that failed at least once; a list that names all seventy sources hides the four that matter. See [../publishing/frontend.md](../publishing/frontend.md).

They read the same file so they can never disagree about what a feed did.

## Design rationale

The record came before the quarantine, and that order was the point: you cannot quarantine what you never measured. A rule that skips a feed after five failures is worthless without five recorded failures to read, and writing the rule first would have meant inventing the evidence.

Making a zero-item `200` a failure is the finding that justifies the whole ledger. Every other failure mode is visible in a log line at the moment it happens. A feed that quietly stops carrying entries looks healthy in every single run and is only visible as a shape across runs, which is exactly what a ledger is for.

The self-lifting rest is there because the alternative was tested by imagination and failed: a quarantine that only a human can lift is a deletion with extra steps, and the human who has to lift it will not be reading a CSV on a Sunday.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A run that edits `config/sources.json` | A robot deleting sources a person curated, in a commit nobody reviewed. |
| A quarantine only a human can lift | A deletion with extra steps. A source that recovers stays dead until someone reads a CSV. |
| Counting a robots refusal as a failure | Punishing a site for saying no, and quarantining a source that is behaving correctly. |
| Treating a zero-item `200` as success | The most common way a feed dies would be invisible, and the ledger would only catch the failures that were already obvious. |
| A separate knob for "skips before retry" | Two numbers answering one question. When they drift apart nobody remembers which was meant. |
| Logging feed results instead of committing them | A log is gone with the run. The next run needs to read what the last four did (Rule #1). |
| Recording only failures | You cannot tell "failed five times out of five" from "failed five times out of two hundred" without the successes. |

## See also

- [discovery.md](discovery.md) - the source list this measures, and its lifecycle rules.
- [freshness.md](freshness.md) - the other two ledgers under `state/`, and what they answer.
- [item-health.md](item-health.md) - the item-grain ledger that records planned item outcomes.
- [trust-boundary.md](trust-boundary.md) - what happens to the bytes a healthy feed returns.
- [../publishing/frontend.md](../publishing/frontend.md) - the console that renders this record.
- [../../concepts/config.md](../../concepts/config.md) - where `quarantine_after_failures` lives.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - degrade rather than fail, which is why a dead feed never fails a run.
