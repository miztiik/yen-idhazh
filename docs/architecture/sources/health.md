# Feed Health and Quarantine

**Last Updated**: 2026-09-02

What every feed did on every run, where that record lives, and how a run decides on its own to stop asking a dead source. Nothing on this page ever edits `config/sources.json`: a person owns the source list, and a run owns the evidence about it.

## From item outcome to feed rest or retirement

An item never enters quarantine or retirement. It either publishes or stops at
a stage, and its item-health row becomes evidence about the feed. A run may
rest a feed. Only a person may retire one.

```text
FEED READ (one feed-health row)
|
+-- ok with items -> clear strike streak -> ask next run
+-- robots_denied -> no strike -> ask next run
+-- skipped -> keep strike streak -> count one rested run
`-- blocked / permanent / transient / ok with zero items -> add one strike

CONFIGURED LIMIT = collect.quarantine_after_failures (currently 5)

LIMIT CONSECUTIVE STRIKES -> REST FEED
REST FEED -> write LIMIT skipped rows -> RETRY
RETRY SUCCEEDS -> clear strike streak -> LIVE NOW
RETRY FAILS -> REST CYCLE RESUMES

PLANNED ITEM (one item-health row)
|
+-- published ----------------------> positive source-yield evidence
+-- source-owned failure -----------> negative source-yield evidence
`-- pipeline-owned or neutral ------> does not count against the source

SOURCE-YIELD EVIDENCE -> NO AUTOMATIC ACTION TODAY

HUMAN SOURCE REVIEW (after at least 30 days of evidence)
|
+-- keep active
+-- lower weight and observe
`-- move from `feeds` to `retired`; set `status: retired` and `retired_on`
```

## Every feed, every run, one row

`state/feed-health/<YYYY-MM>.csv`, appended by the Collect stage. One row per feed per run, carrying the run id, the date, the feed id, the outcome, the HTTP status, how many items came back, and a short detail.

It is written **whether the run publishes or not**. The days a source is worth measuring on are the days the run went badly, and a ledger that only records good runs measures nothing.

Monthly shards, because a read looks back 31 days - just enough that a quarantine decided on the first of the month can still see the failures that caused it.

## Fourteen cells, and five of them are empty on every row so far

The row gained `endpoint_key`, `robots_outcome`, `robots_checked_at`, `robots_status` and `target_attempted` on 2026-09-02. They are appended at the end of the header, and nothing reads any of them yet.

| Cell | What it answers |
| --- | --- |
| `endpoint_key` | Which address was asked. The sha256 of the configured feed URL, so a feed whose URL is edited is a different endpoint with no inherited record. |
| `robots_outcome` | What the site's own `robots.txt` said: `allowed`, `denied`, or `unreachable` when we could not establish permission at all. |
| `robots_checked_at` | When permission was established, so a recheck cadence has a clock. |
| `robots_status` | What `robots.txt` itself answered with, when there was a status. |
| `target_attempted` | Whether the feed address itself was requested. False for a run that stopped at `robots.txt` or rested the feed. |

**The record could not previously say which address it asked.** `feed_id` names a
line of curated config, not a URL, so an address that changed and an address that
died looked the same to every later read - and a run cannot stop asking a dead
address without being able to say which address it means.

**And a refusal read as a failed read.** `robots_denied` says the site declined,
but the row carried no evidence of the check itself, so nothing downstream could
tell "the site said no" apart from "we did not get that far".

**Every one of the 6,433 rows written before that day carries five empty cells.**
Not a zero, and not an identity recomputed from today's `config/sources.json`: the
configured URL may have moved since a row was written, and a guessed endpoint
would file a later retirement against the wrong address. An empty cell says the
older run never looked, which is the only honest thing it can say.

The rewrite is `backend/utilities/migrate_feed_health.py`, and it ran in the same
commit as the contract change because `ledger.require_matching_header` compares
the committed header to the contract's column list exactly - a widened contract
against an unmigrated shard stops the next scheduled run at its first append. It
is safe to re-run: a shard already on the wide header is reported and skipped.

Measured on this Windows developer checkout, 2026-09-02: 6,433 rows across two
shards, 585,437 bytes before the widening and 617,756 after, so five empty cells
per row cost 32,319 bytes - 5.5 percent of the ledger. Reading a committed file
is deterministic, so the spread is zero.

## A run may rest a feed; only an address is ever retired automatically

`state/feed-retirements.csv` is where a run will file an address the server has
reported permanently gone. It ships with its header and no rows, because the
commit step stages every path a job owns in one call and a path that is not in
the checkout aborts the whole step ([../contracts/schemas.md](../contracts/schemas.md)).
Nothing writes it yet.

One row is one endpoint: the feed, the endpoint key, the day, the run that
decided, the cause, and the runs whose results evidence it.

**`http_410` is the only cause the enum admits**, and that is the design rather
than a starting point. A 403, a 404, a paywall, a transient failure and an empty
feed all say something about today; only `410 Gone` is the server saying the
address is not coming back. Retiring on anything softer removes unique primary or
regional reporting over one bad week, and nothing here puts it back without a
person noticing it went.

The record is keyed on the endpoint and not on the feed, so renaming a feed in
curated config cannot make its dead address eligible again, and editing that
feed's URL produces a different key that is eligible from a clean record.

## Six knobs name the questions the one knob used to answer

| Knob | Default | The question |
| --- | --- | --- |
| `collect.availability_strikes_before_rest` | 5 | How much evidence before a run stops asking? |
| `collect.availability_rest_runs` | 5 | How long is a rest? |
| `collect.feed_http_410_runs_before_retirement` | 5 | How many distinct runs must read `410` before an address is retired? |
| `collect.robots_denied_recheck_runs` | 1 | How long before asking `robots.txt` again after a refusal? |
| `collect.robots_unreachable_recheck_runs` | 1 | The same, after a `robots.txt` we could not read. |
| `collect.source_yield_min_complete_days` | 30 | How many complete days of item-health evidence before a yield judgement may be made at all? |

**Nothing reads any of them yet.** `collect.quarantine_after_failures` still
decides every rest, and both it and `availability_strikes_before_rest` carry 5.
The names land before the behaviour so the changes that move the behaviour are
reviewable as behaviour, rather than as a knob and a rule at once.

The two recheck cadences are separate because they are different facts: a refusal
is a publisher's stated policy and an unreadable `robots.txt` is our own failed
read. One number for both would mean an edit meant for one silently moved the
other.

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

Retirement of a **source** is a person moving a feed into the `retired` key of `config/sources.json`. Quarantine is a run declining to ask, based on rows it wrote itself. Retirement of an **address** is a third thing, and it is a row under `state/` for the same reason quarantine is: a run may write evidence about curation and may never write curation.

Keeping those separate is what makes a bad afternoon survivable. A run that could edit config would, over one bad week, quietly delete sources nobody voted to remove - and the diff would be authored by a robot at 06:20 on a Sunday.

## Two readers, one record

- **The planning step** reads the recent tail to decide which feeds to skip this run.
- **The console** reads the same rows to show which sources are broken. It names only feeds that failed at least once; a list that names all seventy sources hides the four that matter. See [../publishing/frontend.md](../publishing/frontend.md).

They read the same file so they can never disagree about what a feed did.

## The broken list needs its denominator

Naming only the broken feeds is the right list and half an answer. Four broken
feeds out of eight is a collapse; four out of two hundred is a Tuesday; and the
page drew both identically. So the console states the other half in one
sentence above the list - **how many feeds have never failed, out of how many
were asked, over how many runs** - and names the clean ones behind a
disclosure.

`reliability()` in `frontend/src/lib/feed-health.ts` is that rule, and it reads
the same `failing()` the quarantine reads, so the two halves of the section
cannot disagree about what a failure is. Three facts it settles:

- **A feed nobody has asked is in neither count.** A record of nothing but
  `skipped` rows is a rest, not a clean run of reads, and counting it as clean
  is how a dead feed joins the reliable list.
- **A polite refusal is not a failure**, here as everywhere else. A source
  honouring its own `robots.txt` has not broken.
- **The span is the whole record, not the page's window.** The streak beside
  each feed is already read that way, because the pipeline rests on the whole
  count. Two spans in one section is the defect the shared window exists to
  remove.

**A shallow record says so instead of printing a claim.** Two runs deep, "has
never failed" means "did not fail twice". Under `console.min_attempts_for_rate`
runs the sentence prints the same counts and says the record is too shallow to
read as reliability - the same knob, and the same question, as the stage rates
one section above.

Measured 2026-09-01 over the committed ledger: 5,291 rows, 182 feeds asked, 34
runs, **156 of 182 have never failed**, and 26 have. The 26 are why the list
also gained `console.feed_rows`, a cap of ten with the remainder stated in one
sentence: a ranking is read from the top and its tail is a number, never
another page of rows.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A ranked "ten most reliable feeds" | Every key it could rank on ties. A feed is read once a run, so a feed that never failed has answered on every run it was asked, and the record is about 34 runs deep. `collect.max_per_source` is 2, so what a feed may carry is capped as well. A top ten of a hundred-and-fifty-way tie is charting a constant. |
| Rank by items yielded | It counts entries in a feed, so it ranks the firehose rather than the reliable. |
| A share instead of a count | The number an operator acts on is how many feeds are named below, not a percentage. `156 of 182` carries both. |

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
| Backfilling `endpoint_key` from today's `config/sources.json` | The configured URL may have moved since a row was written, so the guess would file a later retirement against an address that never failed. |
| Inserting the five new columns beside the ones they relate to | The header guard compares the whole list, and an appended column is what keeps the old header a readable prefix of the new one. A cell inserted in the middle moves every historical value one place right under a reader that maps by position. |
| Retiring an address on 403, 404, a paywall, an empty feed or zero yield | None of them says the address is permanently gone, and each would eventually remove unique primary or regional reporting. |
| Logging feed results instead of committing them | A log is gone with the run. The next run needs to read what the last four did (Rule #1). |
| Recording only failures | You cannot tell "failed five times out of five" from "failed five times out of two hundred" without the successes. |

## See also

- [discovery.md](discovery.md) - the source list this measures, and its lifecycle rules.
- [freshness.md](freshness.md) - the other two ledgers under `state/`, and what they answer.
- [item-health.md](item-health.md) - the item-grain ledger that records planned item outcomes.
- [trust-boundary.md](trust-boundary.md) - what happens to the bytes a healthy feed returns.
- [../publishing/frontend.md](../publishing/frontend.md) - the console that renders this record.
- [../../concepts/config.md](../../concepts/config.md) - where `quarantine_after_failures` and the six knobs beside it live.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - degrade rather than fail, which is why a dead feed never fails a run.
